import unittest
from unittest.mock import Mock,patch
from fastapi import FastAPI
from fastapi.testclient import TestClient
from app import session_security
from app.routers import capacidades
from app.services.procedimiento_service import ProcedimientoService


class CapabilityRoutes(unittest.TestCase):
    def setUp(self):
        app=FastAPI();app.include_router(capacidades.router);self.client=TestClient(app)
        self.headers={'Authorization':'Bearer '+'x'*43}
    def test_requires_admin_for_every_write(self):
        with patch.object(session_security.service,'ejecutar_consulta',return_value=[{'id_usuario':5,'rol':'USUARIO'}]):
            for path,body in [('/admin/modelos/1/capacidades',{'nombre':'ADELANTE','codigo':1}),('/admin/unidades/1/comandos',{'id_capacidad':1})]:
                self.assertEqual(self.client.post(path,json=body,headers=self.headers).status_code,403)
    def test_missing_session_rejected(self):
        self.assertEqual(self.client.get('/admin/unidades/1/comandos').status_code,401)
    def test_invalid_function_name_and_description(self):
        with patch.object(session_security.service,'ejecutar_consulta',return_value=[{'id_usuario':4,'rol':'ADMINISTRADOR'}]):
            self.assertEqual(self.client.post('/admin/modelos/1/capacidades',json={'nombre':'not valid','codigo':1},headers=self.headers).status_code,422)
            self.assertEqual(self.client.post('/admin/unidades/1/comandos',json={'id_capacidad':1,'descripcion':'x'*256},headers=self.headers).status_code,422)


class TransactionGuards(unittest.TestCase):
    def connection(self):
        connection=Mock();cursor=Mock();cursor.nextset.return_value=False
        cursor.fetchall.return_value=[{'id_comando':8}]
        connection.cursor.return_value.__enter__=Mock(return_value=cursor)
        connection.cursor.return_value.__exit__=Mock(return_value=False)
        return connection,cursor
    def test_guard_and_write_share_one_transaction(self):
        connection,cursor=self.connection()
        with patch('app.services.procedimiento_service.get_connection',return_value=connection):
            result=ProcedimientoService().ejecutar_consulta_transaccional('sp_control_mover',(10,5,1,8),[('sp_capacidad_exigir',(1,8))])
        self.assertEqual(result,[{'id_comando':8}])
        self.assertIn('sp_capacidad_exigir',cursor.execute.call_args_list[0].args[0])
        self.assertIn('sp_control_mover',cursor.execute.call_args_list[1].args[0])
        connection.commit.assert_called_once();connection.rollback.assert_not_called()
    def test_failing_guard_prevents_write_and_rolls_back(self):
        connection,cursor=self.connection();cursor.execute.side_effect=RuntimeError('incompatible')
        with patch('app.services.procedimiento_service.get_connection',return_value=connection):
            with self.assertRaises(RuntimeError):
                ProcedimientoService().ejecutar_consulta_transaccional('sp_control_mover',(10,5,1,8),[('sp_capacidad_exigir',(1,8))])
        self.assertEqual(cursor.execute.call_count,1)
        connection.rollback.assert_called_once();connection.commit.assert_not_called()


class CapabilityExecutionSafety(unittest.IsolatedAsyncioTestCase):
    async def test_manual_operation_requires_stop(self):
        from app.routers import movimientos
        from app.models import MovimientoRequest
        from fastapi import HTTPException
        def query(name,args):
            if name=='sp_obtener_vehiculo':return [{'activo':1}]
            return [{'id_comando':8,'nombre':'ADELANTE','activo':1}]
        with patch('app.resource_security.sessions_enabled',return_value=True),patch.object(movimientos.servicio,'ejecutar_consulta',side_effect=query):
            with self.assertRaises(HTTPException) as error:
                await movimientos._registrar_movimiento(1,MovimientoRequest(id_comando=8))
        self.assertEqual(error.exception.status_code,409)

    async def test_demo_requires_stop_before_creating_task(self):
        from app.services.demo_service import DemoService
        from fastapi import HTTPException
        service=DemoService()
        def query(name,args):
            if name=='sp_obtener_vehiculo':return [{'activo':1}]
            if name=='sp_obtener_demos':return [{'id_demo':1,'activo':1}]
            if name=='sp_obtener_movimientos_demo':return [{'id_comando':8}]
            return [{'nombre':'ADELANTE','activo':1}]
        with patch('app.resource_security.sessions_enabled',return_value=True),patch.object(service.servicio,'ejecutar_consulta',side_effect=query):
            with self.assertRaises(HTTPException) as error:
                await service.iniciar(1,1)
        self.assertEqual(error.exception.status_code,409)
        self.assertFalse(service.tareas)
