import asyncio
import unittest
from unittest.mock import AsyncMock, Mock, patch
import pymysql
from fastapi import HTTPException
from app.models import MovimientoRequest
from app.services.control_service import ControlService
from app.services.demo_service import demo_service
from app.services.procedimiento_service import ProcedimientoService

SESSION={'rol':'USUARIO','id_sesion':5,'id_usuario':2}
COMMANDS=[{'id_comando':1,'nombre':'ADELANTE','codigo':1,'activo':1},
          {'id_comando':2,'nombre':'ATRAS','codigo':2,'activo':1},
          {'id_comando':3,'nombre':'GIRAR_IZQUIERDA','codigo':3,'activo':1},
          {'id_comando':4,'nombre':'GIRAR_DERECHA','codigo':4,'activo':1},
          {'id_comando':13,'nombre':'DETENER','codigo':13,'activo':1}]

class CombinedControlTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.service=ControlService()
        self.service.lease=AsyncMock(return_value={'id_control':10})
        self.service.db=AsyncMock(return_value=COMMANDS)
        self.service.publish=AsyncMock()
        self.service.close=AsyncMock()
        self.service.repository.ejecutar_transaccion=Mock()
        demo_service.bloqueo=asyncio.Lock();demo_service.tareas={}
    async def test_pair_is_guarded_and_written_atomically_then_published_once(self):
        result=await self.service.move(SESSION,7,1,secondary_id=3)
        operations=self.service.repository.ejecutar_transaccion.call_args.args[0]
        self.assertEqual(operations,[('sp_capacidad_exigir',(7,1)),('sp_capacidad_exigir',(7,3)),
            ('sp_control_mover',(10,5,7,3)),('sp_control_mover',(10,5,7,1))])
        self.assertEqual([c['comando'] for c in result['comandos']],['ADELANTE','GIRAR_IZQUIERDA'])
        self.service.publish.assert_awaited_once()
    async def test_reverse_right_pair(self):
        result=await self.service.move(SESSION,7,2,secondary_id=4)
        self.assertEqual(result['comando'],'ATRAS')
        self.assertEqual(result['comandos'][1]['comando'],'GIRAR_DERECHA')
    async def test_opposed_movement_invalid_or_foreign_command_never_writes(self):
        for primary,other in [(1,2),(3,4),(1,999),(1,1)]:
            with self.assertRaises(HTTPException):await self.service.move(SESSION,7,primary,secondary_id=other)
        self.service.repository.ejecutar_transaccion.assert_not_called()
        self.service.publish.assert_not_awaited()
    async def test_disabled_component_rejected(self):
        self.service.db.return_value=[{**c,'activo':0} if c['id_comando']==3 else c for c in COMMANDS]
        with self.assertRaises(HTTPException):await self.service.move(SESSION,7,1,secondary_id=3)
        self.service.repository.ejecutar_transaccion.assert_not_called()
    async def test_sql_failure_never_publishes_pair(self):
        self.service.repository.ejecutar_transaccion.side_effect=pymysql.OperationalError(1644,'capability changed')
        with self.assertRaises(HTTPException) as error:await self.service.move(SESSION,7,1,secondary_id=3)
        self.assertEqual(error.exception.status_code,409)
        self.service.publish.assert_not_awaited()
    async def test_reservation_and_socket_checks_happen_before_writes(self):
        self.service.lease.side_effect=HTTPException(403,'not owner')
        with self.assertRaises(HTTPException):await self.service.move(SESSION,7,1,secondary_id=3)
        self.service.db.assert_not_awaited()
        self.service.repository.ejecutar_transaccion.assert_not_called()
    async def test_stop_wins_over_secondary_field(self):
        self.service.db.side_effect=[COMMANDS,[{'id_vehiculo':7,'id_comando':13,'comando':'DETENER','codigo':13}]]
        result=await self.service.move(SESSION,7,13,secondary_id=3)
        self.assertEqual(result['comando'],'DETENER')
        self.service.repository.ejecutar_transaccion.assert_not_called()
    def test_schema_keeps_existing_request_and_adds_positive_optional_id(self):
        self.assertIsNone(MovimientoRequest(id_comando=1).id_comando_giro)
        self.assertEqual(MovimientoRequest(id_comando=1,id_comando_giro=3).id_comando_giro,3)
        with self.assertRaises(ValueError):MovimientoRequest(id_comando=1,id_comando_giro=-1)

class AtomicBatchTests(unittest.TestCase):
    def test_failure_of_second_component_rolls_back_all_changes(self):
        cursor=Mock();cursor.__enter__=Mock(return_value=cursor);cursor.__exit__=Mock(return_value=False)
        cursor.nextset.return_value=False
        cursor.execute.side_effect=[None,pymysql.OperationalError(1644,'second rejected')]
        connection=Mock();connection.cursor.return_value=cursor
        with patch('app.services.procedimiento_service.get_connection',return_value=connection):
            with self.assertRaises(pymysql.MySQLError):
                ProcedimientoService().ejecutar_transaccion([('sp_control_mover',(10,5,7,3)),('sp_control_mover',(10,5,7,1))])
        connection.rollback.assert_called_once();connection.commit.assert_not_called();connection.close.assert_called_once()
