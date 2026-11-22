import unittest
from unittest.mock import AsyncMock,patch
from fastapi import HTTPException
from app.services.demo_service import DemoService
from app.services.websocket_manager import manager
from app.routers import editor_demos


class CompanyPermissions(unittest.TestCase):
    def test_buyer_cannot_edit_visible_company_demo(self):
        data=editor_demos.DemoDocument(id_vehiculo=1,nombre='Fábrica',revision=1,pasos=[{'id_comando':1,'duracion_ms':100}])
        with patch.object(editor_demos,'resource_context',return_value={'activo':1,'id_propietario':5}),patch.object(editor_demos,'visible_demo',return_value={'tipo':'EMPRESA'}),patch.object(editor_demos.service,'ejecutar_consulta_transaccional') as save:
            with self.assertRaises(HTTPException) as error:editor_demos.save_document(data,{'rol':'USUARIO','id_usuario':5},1)
        self.assertEqual(error.exception.status_code,403);save.assert_not_called()
    def test_client_cannot_override_demo_type(self):
        from pydantic import ValidationError
        with self.assertRaises(ValidationError):
            editor_demos.DemoDocument(id_vehiculo=1,nombre='Fábrica',tipo='EMPRESA',pasos=[{'id_comando':1,'duracion_ms':100}])


class DemoCompletion(unittest.IsolatedAsyncioTestCase):
    async def test_normal_completion_stops_before_fin_without_individual_history(self):
        service=DemoService();actions=[]
        def query(name,args):
            return [{'nombre':'DETENER','activo':1,'id_comando':13,'codigo':13}] if name=='sp_obtener_comandos_vehiculo' else []
        def transaction(operations):actions.extend(operations)
        events=[]
        async def publish(unit,event):
            events.append(event)
            if event['tipo']=='demo_fin':self.assertEqual(actions[-1],('sp_actualizar_estado',(1,13,0)))
        step={'id_comando':1,'comando':'ADELANTE','codigo':1,'orden':1,'duracion_ms':0,'pausa_ms':0}
        with patch('app.resource_security.sessions_enabled',return_value=True),patch.object(service.servicio,'ejecutar_consulta',side_effect=query),patch.object(service.servicio,'ejecutar_transaccion',side_effect=transaction),patch.object(manager,'enviar_a_vehiculo',side_effect=publish):
            await service._ejecutar(1,1,[step])
        self.assertEqual(events[-1]['tipo'],'demo_fin')
        self.assertEqual(events[-1]['comando'],'DETENER')
        self.assertEqual(events[-1]['codigo'],13)
        self.assertNotIn('sp_registrar_historial',[name for name,args in actions])

    async def test_failed_stop_does_not_emit_success(self):
        service=DemoService();publish=AsyncMock()
        with patch.object(service.servicio,'ejecutar_consulta',return_value=[]),patch.object(manager,'enviar_a_vehiculo',publish):
            okay=await service._detener_seguro(1,1,'demo_fin')
        self.assertFalse(okay)
        self.assertEqual(publish.call_args.args[1]['tipo'],'demo_error')

    async def test_admin_movement_uses_exclusive_control_service(self):
        from types import SimpleNamespace
        from app.routers import movimientos
        from app.models import MovimientoRequest
        from app.services.control_service import control_service
        session={'rol':'ADMINISTRADOR','id_sesion':5,'id_usuario':1}
        request=SimpleNamespace(state=SimpleNamespace(session=session))
        with patch('app.resource_security.sessions_enabled',return_value=True), patch.object(control_service,'move',AsyncMock(return_value={'ok':True})) as move, patch.object(movimientos,'_registrar_movimiento',AsyncMock()) as bypass:
            result=await movimientos.registrar_movimiento(1,MovimientoRequest(id_comando=13),request)
        self.assertEqual(result,{'ok':True})
        move.assert_awaited_once_with(session,1,13)
        bypass.assert_not_awaited()
