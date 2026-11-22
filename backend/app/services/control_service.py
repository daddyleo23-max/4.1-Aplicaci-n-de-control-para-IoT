"""Exclusividad de comprador: una reserva SQL y un canal por sesión/unidad."""
import asyncio
from contextlib import suppress
from datetime import datetime, timezone
import logging
import time
import pymysql
from fastapi import HTTPException
from app.services.procedimiento_service import ProcedimientoService
from app.services.demo_service import demo_service
from app.services.websocket_manager import manager

logger = logging.getLogger(__name__)


async def complete(coro):
    """Un hilo SQL no se detiene cancelando su await: esperar antes de parar/liberar."""
    task = asyncio.create_task(coro)
    cancelled = False
    while True:
        try:
            value = await asyncio.shield(task)
            break
        except asyncio.CancelledError:
            if task.cancelled():
                raise
            cancelled = True
    if cancelled:
        raise asyncio.CancelledError
    return value


class ControlService:
    def __init__(self):
        self.repository = ProcedimientoService()
        self.ready = False
        self.sockets = {}
        self.awaiting = {}
        self.closures = {}

    async def db(self, name, args=(), write=False):
        method = self.repository.ejecutar_consulta_transaccional if write else self.repository.ejecutar_consulta
        try:
            return await asyncio.to_thread(method, name, args)
        except pymysql.MySQLError as error:
            if error.args[0] in (1644, 1062, 1205, 1213):
                raise HTTPException(409, 'Reserva incompatible, vencida o en proceso de cierre.') from error
            raise HTTPException(503, 'No se pudo consultar el servicio de control.') from error

    async def publish(self, row):
        await asyncio.wait_for(manager.enviar_a_vehiculo(row['id_vehiculo'],
            {**row, 'tipo':'movimiento', 'timestamp':datetime.now(timezone.utc).isoformat()}),timeout=3)

    async def stop(self, control):
        row = (await self.db('sp_control_detener',(control,),True))[0]
        await self.publish(row)

    async def reserve(self, session, unit):
        if session['rol'] != 'USUARIO':
            raise HTTPException(403, 'La reserva requiere una cuenta de comprador propietaria.')
        if not self.ready:
            raise HTTPException(503, 'Se están recuperando las reservas de control.')
        async def create():
            async with demo_service.bloqueo:
                task = demo_service.tareas.get(unit)
                if task and not task.done():
                    raise HTTPException(409,'La unidad ejecuta una demo; cancélala antes de reservar.')
                row = (await self.db('sp_control_adquirir',(session['id_sesion'],unit),True))[0]
                self.awaiting[row['id_control']] = time.monotonic()
                try:
                    await self.stop(row['id_control'])
                except BaseException:
                    await self.db('sp_control_cerrar',(row['id_control'],'REVOCADA'),True)
                    raise
                return row
        task = asyncio.create_task(create())
        try:
            return await asyncio.shield(task)
        except asyncio.CancelledError:
            # Recuperar también la reserva que SQL pudiera haber confirmado durante la cancelación.
            try:
                row = await complete_task(task)
                await self.close(row['id_control'],'CANCELADA')
            finally:
                raise

    async def context(self, control, session, active=True):
        rows = await self.db('sp_control_contexto',(control,session['id_sesion']))
        if not rows:
            raise HTTPException(403,'La reserva pertenece a otra sesión.')
        row = rows[0]
        if active:
            await self.db('sp_control_exigir',(control,session['id_sesion'],row['id_vehiculo']),True)
        return row

    async def lease(self, session, unit):
        rows = await self.db('sp_control_reservas')
        row = next((r for r in rows if r['id_vehiculo']==unit and r['id_sesion']==session['id_sesion']),None)
        if not row or row['id_control'] not in self.sockets:
            raise HTTPException(409,'Reserva la unidad y conecta su canal de control antes de operar.')
        await self.context(row['id_control'],session)
        return row

    async def close(self, control, reason):
        task = self.closures.get(control)
        if task is None:
            task = asyncio.create_task(self._close(control,reason))
            self.closures[control] = task
        try:
            await complete_task(task)
        finally:
            if task.done() and self.closures.get(control) is task:
                self.closures.pop(control,None)

    async def _close(self, control, reason):
        async with demo_service.bloqueo:
            rows = await self.db('sp_control_reservas')
            row = next((r for r in rows if r['id_control']==control),None)
            if row is None:
                return
            await self.db('sp_control_cerrar',(control,reason),True)
            demo = demo_service.tareas.get(row['id_vehiculo'])
            if demo and not demo.done():
                demo.cancel()
        # La demo necesita el mismo bloqueo para finalizar. Esperarla fuera del bloqueo.
        if demo and not demo.done():
            with suppress(asyncio.CancelledError):
                await demo
        async with demo_service.bloqueo:
            # Fallar STOP/publicación conserva DETENIENDO para el barrido.
            await self.stop(control)
            await self.db('sp_control_liberar',(control,),True)
            self.awaiting.pop(control,None)
            ws = self.sockets.pop(control,None)
        if ws:
            with suppress(Exception):
                await ws.close(code=1000)

    async def move(self, session, unit, command_id):
        lease = await self.lease(session,unit)
        control = lease['id_control']
        async def execute():
            commands = await self.db('sp_obtener_comandos_vehiculo',(unit,))
            command = next((c for c in commands if c['id_comando']==command_id and c['activo']),None)
            if not command:
                raise HTTPException(404,'Comando no encontrado o inactivo.')
            if command['nombre']=='DEMO':
                raise HTTPException(400,'Utiliza el endpoint específico para iniciar una demo.')
            while True:
                demo = None
                async with demo_service.bloqueo:
                    running = demo_service.tareas.get(unit)
                    if running and not running.done():
                        if command['nombre'] != 'DETENER':
                            raise HTTPException(409,'Cancela la demo antes de enviar otro movimiento.')
                        running.cancel()
                        demo = running
                    else:
                        # Revalidar en SQL dentro de la misma transacción del movimiento.
                        row = (await self.db('sp_control_mover',(control,session['id_sesion'],unit,command_id),True))[0]
                        await self.publish(row)
                        return {'mensaje':'Movimiento registrado correctamente.',**row}
                if demo:
                    with suppress(asyncio.CancelledError):
                        await demo
        task = asyncio.create_task(execute())
        try:
            return await asyncio.shield(task)
        except asyncio.CancelledError:
            try:
                with suppress(Exception):
                    await complete_task(task)
                await self.close(control,'CANCELADA')
            finally:
                raise
        except Exception as error:
            if not isinstance(error,HTTPException) or error.status_code>=500:
                with suppress(Exception):
                    await self.close(control,'REVOCADA')
            raise

    async def worker(self):
        while True:
            try:
                rows = await self.db('sp_control_reservas')
                if not self.ready:
                    for row in rows:
                        await self.close(row['id_control'],'REINICIO')
                    self.ready = True
                else:
                    for row in rows:
                        control = row['id_control']
                        if row['cierre_pendiente']:
                            await self.close(control,'EXPIRADA')
                        elif control in self.awaiting and time.monotonic()-self.awaiting[control]>=20:
                            await self.close(control,'DESCONECTADA')
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.warning('Una reserva de comprador sigue bloqueada; se reintentará su parada.')
            await asyncio.sleep(1)

    async def shutdown(self):
        self.ready = False
        for row in await self.db('sp_control_reservas'):
            await self.close(row['id_control'],'REINICIO')


async def complete_task(task):
    cancelled = False
    while True:
        try:
            result = await asyncio.shield(task)
            break
        except asyncio.CancelledError:
            if task.cancelled():
                raise
            cancelled = True
    if cancelled:
        raise asyncio.CancelledError
    return result


control_service = ControlService()
