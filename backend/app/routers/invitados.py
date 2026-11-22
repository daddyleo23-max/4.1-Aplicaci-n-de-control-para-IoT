import asyncio
from datetime import timezone
import json
import logging

from fastapi import APIRouter, Depends, HTTPException, Request, Response, Security, WebSocket, WebSocketDisconnect
from fastapi.encoders import jsonable_encoder
from fastapi.security import HTTPAuthorizationCredentials
from pydantic import BaseModel, ConfigDict, Field, StrictInt, model_validator

from app.resource_security import sessions_enabled
from app.session_security import bearer, require_admin, token_hash
from app.services.guest_service import guest_service
from app.services.demo_service import demo_service
from app.services.websocket_manager import manager

router = APIRouter(tags=["Invitados 4.3"])
logger = logging.getLogger(__name__)


def enabled():
    if not sessions_enabled():
        raise HTTPException(503, "Las pruebas temporales no están habilitadas.")


def guest_token(credentials: HTTPAuthorizationCredentials | None = Security(bearer)):
    if credentials is None or not 20 <= len(credentials.credentials) <= 200:
        raise HTTPException(401, "Sesión de Invitado requerida.")
    return credentials.credentials


def context_public(row):
    expires = row["expira_utc"]
    if expires.tzinfo is None:
        expires = expires.replace(tzinfo=timezone.utc)
    return {"rol": "INVITADO", "id_sesion_invitado": row["id_sesion_invitado"],
            "id_vehiculo": row["id_vehiculo"], "expires_at": expires,
            "segundos_restantes": row["segundos_restantes"], "pulso_ms": row["pulso_ms"]}


class GuestReservation(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id_vehiculo: int = Field(gt=0)


class GuestMovement(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id_comando: int = Field(gt=0)


class GuestConfiguration(BaseModel):
    model_config = ConfigDict(extra="forbid")
    habilitada: bool
    duracion_s: int = Field(ge=15, le=120)
    pulso_ms: int = Field(ge=50, le=500)
    comandos: list[StrictInt] = Field(min_length=1, max_length=10)

    @model_validator(mode="after")
    def unique_commands(self):
        if len(set(self.comandos)) != len(self.comandos) or any(value <= 0 for value in self.comandos):
            raise ValueError("Selecciona comandos positivos sin duplicados.")
        return self


@router.get("/admin/unidades/{id_vehiculo}/invitados")
async def configuration(id_vehiculo: int, session: dict = Depends(require_admin)):
    if id_vehiculo <= 0:
        raise HTTPException(422, "El identificador debe ser positivo.")
    rows = await guest_service.db("sp_invitado_configuracion", (id_vehiculo,))
    if not rows:
        return {"configurada": False, "comandos": []}
    row = rows[0]
    return {"configurada": True, "habilitada": bool(row["habilitada"]),
            "duracion_s": row["duracion_s"], "pulso_ms": row["pulso_ms"],
            "comandos": json.loads(row["comandos"]) if row["comandos"] else []}


@router.post("/admin/unidades/{id_vehiculo}/invitados")
async def configure(id_vehiculo: int, data: GuestConfiguration, session: dict = Depends(require_admin)):
    if id_vehiculo <= 0:
        raise HTTPException(422, "El identificador debe ser positivo.")
    async with demo_service.bloqueo:
        task = demo_service.tareas.get(id_vehiculo)
        if task is not None and not task.done():
            raise HTTPException(409, "Cancela la demo antes de configurar la prueba.")
        await guest_service.db("sp_invitado_configurar", (session["id_usuario"], id_vehiculo,
            data.habilitada, data.duracion_s, data.pulso_ms, json.dumps(data.comandos)), write=True)
    return {"mensaje": "Configuración de Invitado guardada."}


@router.post("/admin/unidades/{id_vehiculo}/invitados/cerrar")
async def admin_close(id_vehiculo: int, session: dict = Depends(require_admin)):
    rows = await guest_service.db("sp_invitado_reservas_actuales")
    for row in rows:
        if row["id_vehiculo"] == id_vehiculo:
            await guest_service.close(row["id_sesion_invitado"], "REVOCADA", actor=session["id_usuario"])
    return {"mensaje": "La unidad no tiene una reserva de Invitado pendiente."}


@router.get("/catalogo/{id_modelo}/unidades")
async def exhibition_units(id_modelo: int, response: Response):
    response.headers["Cache-Control"] = "no-store"
    if id_modelo <= 0:
        raise HTTPException(422, "El identificador debe ser positivo.")
    rows = await guest_service.db("sp_invitado_unidades", (id_modelo,))
    units = [{"id_vehiculo": row["id_vehiculo"], "nombre": row["nombre"],
              "duracion_s": row["duracion_s"], "pulso_ms": row["pulso_ms"],
              "ocupada": bool(row["ocupada"]),
              "disponible": not row["ocupada"] and guest_service.ready and sessions_enabled()}
             for row in rows]
    return {"unidades": units}


@router.post("/invitados/sesiones", status_code=201, dependencies=[Depends(enabled)])
async def reserve(data: GuestReservation, request: Request, response: Response):
    response.headers["Cache-Control"] = "no-store"
    token = await guest_service.reserve(data.id_vehiculo, request.client.host if request.client else "desconocido")
    row = await asyncio.to_thread(guest_service.context, token)
    commands = await guest_service.db("sp_invitado_comandos", (token_hash(token),))
    return {"access_token": token, "token_type": "bearer", **context_public(row), "comandos": commands}


@router.get("/invitados/sesion", dependencies=[Depends(enabled)])
async def current(response: Response, token: str = Depends(guest_token)):
    response.headers["Cache-Control"] = "no-store"
    row = await asyncio.to_thread(guest_service.context, token)
    commands = await guest_service.db("sp_invitado_comandos", (token_hash(token),))
    return {**context_public(row), "comandos": commands}


@router.post("/invitados/movimientos", status_code=201, dependencies=[Depends(enabled)])
async def move(data: GuestMovement, response: Response, token: str = Depends(guest_token)):
    response.headers["Cache-Control"] = "no-store"
    try:
        return await guest_service.move(token, data.id_comando)
    except asyncio.TimeoutError as error:
        raise HTTPException(503, "No se confirmó el procesamiento de la parada solicitada.") from error


@router.post("/invitados/sesion/cerrar", dependencies=[Depends(enabled)])
async def close(response: Response, token: str = Depends(guest_token)):
    response.headers["Cache-Control"] = "no-store"
    row = await asyncio.to_thread(guest_service.context, token, allow_closed=True)
    await guest_service.close(row["id_sesion_invitado"], "CANCELADA")
    return {"mensaje": "Sesión finalizada y reserva liberada.", "parada_solicitada": True}


@router.websocket("/ws/invitados")
async def guest_socket(websocket: WebSocket):
    attached = False
    session_id = unit_id = None
    try:
        enabled()
        await websocket.accept()
        message = await asyncio.wait_for(websocket.receive_json(), timeout=10)
        if not isinstance(message, dict) or message.get("tipo") != "autenticar":
            raise HTTPException(401, "Autenticación requerida.")
        token = message.get("token")
        row = await asyncio.to_thread(guest_service.context, token)
        session_id, unit_id = row["id_sesion_invitado"], row["id_vehiculo"]
        if session_id in guest_service.sockets:
            raise HTTPException(409, "La sesión ya tiene un canal de control.")
        guest_service.sockets.add(session_id)
        attached = True
        guest_service.awaiting_socket.pop(session_id, None)
        websocket.state.auth_kind = "guest"
        websocket.state.session_token = token
        await manager.conectar(unit_id, websocket)
        state = await guest_service.db("sp_obtener_estado", (unit_id,))
        await websocket.send_json(jsonable_encoder({"tipo": "estado_inicial", "id_vehiculo": unit_id,
            "estado": state[0] if state else None, **context_public(row)}))
        while True:
            await asyncio.to_thread(guest_service.context, token)
            try:
                await asyncio.wait_for(websocket.receive_text(), timeout=1)
            except asyncio.TimeoutError:
                pass
    except WebSocketDisconnect:
        pass
    except (HTTPException, ValueError, asyncio.TimeoutError):
        try:
            await websocket.close(code=1008)
        except Exception:
            pass
    except Exception:
        try:
            await websocket.close(code=1011)
        except Exception:
            pass
    finally:
        if attached:
            manager.desconectar(unit_id, websocket)
            guest_service.sockets.discard(session_id)
            try:
                await guest_service.close(session_id, "DESCONECTADA")
            except Exception:
                logger.warning("La reserva desconectada queda pendiente de detención y se reintentará.")
