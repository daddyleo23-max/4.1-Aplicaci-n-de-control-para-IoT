"""Sesiones de exhibición: reserva SQL, pulsos acotados y cierre conservador."""
import asyncio
from collections import defaultdict, deque
from datetime import datetime, timezone
import logging
import secrets
import time

from fastapi import HTTPException
import pymysql

from app.session_security import token_hash
from app.services.procedimiento_service import ProcedimientoService
from app.services.demo_service import demo_service
from app.services.websocket_manager import manager

logger = logging.getLogger(__name__)


class GuestService:
    def __init__(self):
        self.repository = ProcedimientoService()
        self.ready = False
        self.sockets = set()
        self.awaiting_socket = {}
        self.interrupts = {}
        self.creation_attempts = defaultdict(deque)
        self.command_attempts = defaultdict(deque)

    def query(self, name, parameters=(), *, write=False):
        try:
            method = (self.repository.ejecutar_consulta_transaccional if write
                      else self.repository.ejecutar_consulta)
            return method(name, parameters)
        except pymysql.MySQLError as error:
            if error.args[0] in (1644, 1062, 1213, 1205):
                raise HTTPException(409, "La unidad está ocupada o la configuración no permite esta operación.") from error
            raise HTTPException(503, "El servicio de exhibición no está disponible temporalmente.") from error

    async def db(self, name, parameters=(), *, write=False):
        return await asyncio.to_thread(self.query, name, parameters, write=write)

    def context(self, token, *, allow_closed=False):
        if not isinstance(token, str) or not 20 <= len(token) <= 200:
            raise HTTPException(401, "Sesión de Invitado requerida.")
        rows = self.query("sp_invitado_identificar" if allow_closed else "sp_invitado_obtener", (token_hash(token),))
        if not rows:
            raise HTTPException(401, "Sesión de Invitado vencida, cerrada o no válida.")
        return rows[0]

    def rate_limit(self, key, *, command=False):
        now = time.monotonic()
        buckets = self.command_attempts if command else self.creation_attempts
        window, limit = (1, 4) if command else (60, 10)
        if len(buckets) > 1000:
            for old in list(buckets):
                if not buckets[old] or buckets[old][-1] <= now - window:
                    del buckets[old]
        if len(buckets) >= 1000 and key not in buckets:
            raise HTTPException(429, "Intenta nuevamente más tarde.")
        values = buckets[key]
        while values and values[0] <= now - window:
            values.popleft()
        if len(values) >= limit:
            raise HTTPException(429, "Espera antes de enviar otra solicitud.", headers={"Retry-After": str(window)})
        values.append(now)

    async def publish(self, row):
        event = {key: row[key] for key in ("id_vehiculo", "id_comando", "comando", "codigo")}
        event.update(tipo="movimiento", timestamp=datetime.now(timezone.utc).isoformat())
        await asyncio.wait_for(manager.enviar_a_vehiculo(row["id_vehiculo"], event), timeout=3)

    async def stop_unlocked(self, session_id):
        row = (await self.db("sp_invitado_detener", (session_id,), write=True))[0]
        await self.publish(row)
        return row

    async def reserve(self, unit_id, client):
        self.rate_limit(client)
        if not self.ready:
            raise HTTPException(503, "Se están recuperando las reservas. Intenta nuevamente.")
        async with demo_service.bloqueo:
            task = demo_service.tareas.get(unit_id)
            if task is not None and not task.done():
                raise HTTPException(409, "La unidad está ejecutando una demo.")
            token = secrets.token_urlsafe(32)
            row = (await self.db("sp_invitado_reservar", (unit_id, token_hash(token)), write=True))[0]
            session_id = row["id_sesion_invitado"]
            try:
                await self.stop_unlocked(session_id)
            except BaseException:
                await self.db("sp_invitado_cerrar", (session_id, "REVOCADA"), write=True)
                raise
            self.awaiting_socket[session_id] = time.monotonic()
            return token

    async def close(self, session_id, reason, actor=None):
        interrupt = self.interrupts.get(session_id)
        if interrupt:
            interrupt[0].set()
        async with demo_service.bloqueo:
            rows = await self.db("sp_invitado_sesion_id", (session_id,))
            if not rows or not rows[0]["reserva_pendiente"]:
                return
            if actor is None:
                await self.db("sp_invitado_cerrar", (session_id, reason), write=True)
            else:
                await self.db("sp_invitado_cerrar_admin", (actor, session_id), write=True)
            # Ante error se conserva DETENIENDO. El barrido volverá a intentarlo.
            await self.stop_unlocked(session_id)
            await self.db("sp_invitado_liberar", (session_id,), write=True)
            self.awaiting_socket.pop(session_id, None)
            self.command_attempts.pop(session_id, None)

    async def move(self, token, command_id):
        context = await asyncio.to_thread(self.context, token)
        session_id = context["id_sesion_invitado"]
        if session_id not in self.sockets:
            raise HTTPException(409, "Conecta el canal WebSocket de la prueba antes de enviar comandos.")
        commands = await self.db("sp_invitado_comandos", (token_hash(token),))
        command = next((item for item in commands if item["id_comando"] == command_id), None)
        if command is None:
            raise HTTPException(403, "El comando no está permitido en esta prueba.")
        previous = self.interrupts.get(session_id)
        if previous:
            if command["nombre"] != "DETENER":
                raise HTTPException(409, "Espera a que termine el pulso actual.")
            previous[0].set()
            await asyncio.wait_for(previous[1].wait(), timeout=5)
            return {"id_comando": command_id, "comando": "DETENER", "parada_solicitada": True}
        if command["nombre"] != "DETENER":
            self.rate_limit(session_id, command=True)
        if demo_service.bloqueo.locked():
            raise HTTPException(409, "Otra operación está finalizando. Intenta nuevamente.")
        interrupt, done = asyncio.Event(), asyncio.Event()
        self.interrupts[session_id] = (interrupt, done)
        async def pulse():
            try:
                async with demo_service.bloqueo:
                    try:
                        row = (await self.db("sp_invitado_mover", (token_hash(token), command_id), write=True))[0]
                        await self.publish(row)
                        if row["comando"] != "DETENER":
                            try:
                                await asyncio.wait_for(interrupt.wait(), timeout=max(0, row["pulso_ms"]) / 1000)
                            except asyncio.TimeoutError:
                                pass
                    finally:
                        await self.stop_unlocked(session_id)
                return {"id_comando": command_id, "comando": row["comando"], "parada_solicitada": True}
            finally:
                self.interrupts.pop(session_id, None)
                done.set()

        # El trabajo SQL en un hilo puede continuar tras cancelar su await.
        # Se espera el pulso completo, incluida su parada, antes de propagar la cancelación.
        task = asyncio.create_task(pulse())
        cancelled = False
        while True:
            try:
                result = await asyncio.shield(task)
                break
            except asyncio.CancelledError:
                if task.cancelled():
                    raise
                cancelled = True
                interrupt.set()
        if cancelled:
            raise asyncio.CancelledError
        return result

    async def worker(self):
        while True:
            try:
                if not self.ready:
                    rows = await self.db("sp_invitado_reservas_actuales")
                    for row in rows:
                        await self.close(row["id_sesion_invitado"], "REINICIO")
                    self.ready = True
                rows = await self.db("sp_invitado_pendientes")
                for row in rows:
                    await self.close(row["id_sesion_invitado"], "EXPIRADA")
                for session_id, started in list(self.awaiting_socket.items()):
                    if time.monotonic() - started >= 20:
                        await self.close(session_id, "DESCONECTADA")
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.warning("No se completó el cierre de una reserva; permanece bloqueada y se reintentará.")
            await asyncio.sleep(1)

    async def shutdown(self):
        self.ready = False
        for interrupt, _ in self.interrupts.values():
            interrupt.set()
        rows = await self.db("sp_invitado_reservas_actuales")
        for row in rows:
            await self.close(row["id_sesion_invitado"], "REINICIO")


guest_service = GuestService()
