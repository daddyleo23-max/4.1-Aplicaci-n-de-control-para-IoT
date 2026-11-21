
import asyncio
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.encoders import jsonable_encoder
import pymysql

from app.services.procedimiento_service import ProcedimientoService
from app.services.websocket_manager import manager
from app.resource_security import sessions_enabled, check_socket_access

router = APIRouter(tags=["WebSocket"])
servicio = ProcedimientoService()


@router.websocket("/ws/vehiculos/{id_vehiculo}")
async def websocket_vehiculo(
    websocket: WebSocket,
    id_vehiculo: int,
):
    try:
        if sessions_enabled():
            await websocket.accept()
            scheme, _, token = websocket.headers.get("Authorization", "").partition(" ")
            if scheme.lower() != "bearer" or not token:
                message = await asyncio.wait_for(websocket.receive_json(), timeout=10)
                if not isinstance(message, dict) or message.get("tipo") != "autenticar":
                    raise HTTPException(401, "Autenticación requerida.")
                token = message.get("token")
            if not isinstance(token, str) or not 20 <= len(token) <= 200:
                raise HTTPException(401, "Token inválido.")
            await asyncio.to_thread(check_socket_access, token, id_vehiculo)
            websocket.state.session_token = token
        await manager.conectar(id_vehiculo, websocket)
        vehiculos = servicio.ejecutar_consulta(
            "sp_obtener_vehiculo",
            (id_vehiculo,),
        )

        if not vehiculos or not vehiculos[0]["activo"]:
            await websocket.send_json({
                "tipo": "error",
                "mensaje": "El vehículo no existe o está inactivo.",
            })
            await websocket.close(code=1008)
            return

        estados = servicio.ejecutar_consulta(
            "sp_obtener_estado",
            (id_vehiculo,),
        )

        await websocket.send_json(
            jsonable_encoder({
                "tipo": "estado_inicial",
                "id_vehiculo": id_vehiculo,
                "estado": estados[0] if estados else None,
            })
        )

        while True:
            if sessions_enabled():
                await asyncio.to_thread(check_socket_access, websocket.state.session_token, id_vehiculo)
                try:
                    await asyncio.wait_for(websocket.receive_text(), timeout=2)
                except asyncio.TimeoutError:
                    continue
            else:
                await websocket.receive_text()

    except (HTTPException, ValueError, asyncio.TimeoutError):
        await websocket.close(code=1008)

    except WebSocketDisconnect:
        print(f"WebSocket desconectado para vehículo {id_vehiculo}")

    except pymysql.MySQLError as error:
        print(f"Error MySQL en WebSocket: {error}")
        try:
            await websocket.send_json({
                "tipo": "error",
                "mensaje": "No fue posible consultar la base de datos.",
            })
            await websocket.close(code=1011)
        except Exception:
            pass

    finally:
        manager.desconectar(id_vehiculo, websocket)
