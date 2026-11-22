import asyncio
import unittest
from unittest.mock import AsyncMock, patch
from fastapi import HTTPException
from app.services.control_service import ControlService, complete
from app.services.demo_service import demo_service

SESSION={'rol':'USUARIO','id_sesion':5,'id_usuario':2}
LEASE={'id_control':10,'id_sesion':5,'id_vehiculo':7,'cierre_pendiente':False}
STOP={'id_comando':13,'id_vehiculo':7,'nombre':'DETENER','comando':'DETENER','codigo':13,'activo':1}


class ControlTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.service=ControlService()
        self.service.ready=True
        self.service.db=AsyncMock(return_value=[])
        self.service.publish=AsyncMock()
        demo_service.bloqueo=asyncio.Lock()
        demo_service.tareas={}

    async def test_no_socket_no_movement(self):
        self.service.db.return_value=[LEASE]
        with self.assertRaises(HTTPException) as error:
            await self.service.move(SESSION,7,13)
        self.assertEqual(error.exception.status_code,409)
        self.assertNotIn('sp_control_mover',[call.args[0] for call in self.service.db.call_args_list])

    async def test_other_session_cannot_borrow_lease(self):
        self.service.db.return_value=[LEASE]
        with self.assertRaises(HTTPException):
            await self.service.lease({**SESSION,'id_sesion':6},7)

    async def test_unknown_role_cannot_reserve(self):
        with self.assertRaises(HTTPException):
            await self.service.reserve({**SESSION,'rol':'INVITADO'},7)
        self.service.db.assert_not_awaited()

    async def test_recovery_blocks_new_reservations(self):
        self.service.ready=False
        with self.assertRaises(HTTPException) as error:
            await self.service.reserve(SESSION,7)
        self.assertEqual(error.exception.status_code,503)

    async def test_stop_failure_keeps_reservation(self):
        self.service.db.return_value=[LEASE]
        self.service.stop=AsyncMock(side_effect=RuntimeError('stop unavailable'))
        with self.assertRaises(RuntimeError):
            await self.service.close(10,'CANCELADA')
        names=[call.args[0] for call in self.service.db.call_args_list]
        self.assertIn('sp_control_cerrar',names)
        self.assertNotIn('sp_control_liberar',names)

    async def test_publish_failure_keeps_reservation(self):
        async def db(name,args=(),write=False):
            return [STOP] if name=='sp_control_detener' else [LEASE]
        self.service.db.side_effect=db
        self.service.publish.side_effect=RuntimeError('event unavailable')
        with self.assertRaises(RuntimeError):
            await self.service.close(10,'CANCELADA')
        self.assertNotIn('sp_control_liberar',[c.args[0] for c in self.service.db.call_args_list])

    async def test_close_orders_stop_before_release(self):
        actions=[]
        async def db(name,args=(),write=False):
            actions.append(name)
            return [STOP] if name=='sp_control_detener' else [LEASE]
        self.service.db.side_effect=db
        async def publish(row):actions.append('event')
        self.service.publish.side_effect=publish
        await self.service.close(10,'CANCELADA')
        self.assertLess(actions.index('sp_control_cerrar'),actions.index('sp_control_detener'))
        self.assertLess(actions.index('event'),actions.index('sp_control_liberar'))

    async def test_stale_close_does_not_touch_new_lease(self):
        self.service.db.return_value=[{**LEASE,'id_control':11}]
        await self.service.close(10,'CANCELADA')
        self.assertEqual([c.args[0] for c in self.service.db.call_args_list],['sp_control_reservas'])

    async def test_cancelled_sql_waits_until_completion(self):
        started=asyncio.Event(); finish=asyncio.Event(); done=[]
        async def sql():
            started.set();await finish.wait();done.append('sql')
        task=asyncio.create_task(complete(sql()))
        await started.wait();task.cancel();await asyncio.sleep(0)
        self.assertFalse(task.done())
        finish.set()
        with self.assertRaises(asyncio.CancelledError):await task
        self.assertEqual(done,['sql'])

    async def test_close_waits_demo_before_stop(self):
        started=asyncio.Event();completed=[]
        async def demo():
            try:
                started.set();await asyncio.Event().wait()
            finally:completed.append('demo')
        task=asyncio.create_task(demo());await started.wait()
        demo_service.tareas[7]=task
        self.service.db.return_value=[LEASE]
        async def stop(control):
            self.assertEqual(completed,['demo'])
        self.service.stop=AsyncMock(side_effect=stop)
        await self.service.close(10,'CANCELADA')
        self.assertTrue(task.done())

    async def test_cancelled_acquisition_finishes_sql_then_closes(self):
        started=asyncio.Event();finish=asyncio.Event()
        async def db(name,args=(),write=False):
            if name=='sp_control_adquirir':
                started.set();await finish.wait();return [LEASE]
            return [STOP]
        self.service.db.side_effect=db
        self.service.stop=AsyncMock()
        self.service.close=AsyncMock()
        task=asyncio.create_task(self.service.reserve(SESSION,7))
        await started.wait();task.cancel();await asyncio.sleep(0)
        self.assertFalse(task.done())
        self.service.close.assert_not_awaited()
        finish.set()
        with self.assertRaises(asyncio.CancelledError):await task
        self.service.close.assert_awaited_once_with(10,'CANCELADA')

    async def test_concurrent_close_is_processed_once(self):
        started=asyncio.Event();finish=asyncio.Event()
        self.service.db.return_value=[LEASE]
        async def stop(control):
            started.set();await finish.wait()
        self.service.stop=AsyncMock(side_effect=stop)
        first=asyncio.create_task(self.service.close(10,'CANCELADA'))
        await started.wait()
        second=asyncio.create_task(self.service.close(10,'DESCONECTADA'))
        await asyncio.sleep(0);finish.set();await asyncio.gather(first,second)
        self.service.stop.assert_awaited_once_with(10)
        calls=[c.args[0] for c in self.service.db.call_args_list]
        self.assertEqual(calls.count('sp_control_liberar'),1)
