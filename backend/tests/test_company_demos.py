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

    async def test_admin_stop_cancels_demo_before_manual_write(self):
        import asyncio
        from types import SimpleNamespace
        from app.routers import movimientos
        from app.models import MovimientoRequest
        from app.services.demo_service import demo_service
        ended=[];started=asyncio.Event()
        async def demo():
            try:started.set();await asyncio.Event().wait()
            finally:ended.append('demo')
        task=asyncio.create_task(demo());await started.wait()
        async def manual(unit,command):self.assertEqual(ended,['demo']);return {'ok':True}
        request=SimpleNamespace(state=SimpleNamespace(session={'rol':'ADMINISTRADOR'}))
        with patch('app.resource_security.sessions_enabled',return_value=True),patch.object(demo_service,'bloqueo',asyncio.Lock()),patch.object(demo_service,'tareas',{1:task}),patch.object(movimientos.servicio,'ejecutar_consulta',return_value=[{'id_comando':13,'nombre':'DETENER','activo':1}]),patch.object(movimientos,'_registrar_movimiento',side_effect=manual):
            result=await movimientos.registrar_movimiento(1,MovimientoRequest(id_comando=13),request)
        self.assertEqual(result,{'ok':True})
