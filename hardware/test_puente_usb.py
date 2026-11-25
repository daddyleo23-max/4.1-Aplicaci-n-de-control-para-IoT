import unittest
from datetime import datetime, timezone
from puente_usb import translate, Output

class ProtocolTests(unittest.TestCase):
    def event(self, **changes):
        event = dict(tipo='movimiento',id_vehiculo=1,comando='ADELANTE',timestamp=datetime.fromtimestamp(100,timezone.utc).isoformat())
        return {**event,**changes}
    def test_only_fresh_authorized_unit(self):
        self.assertEqual(translate(self.event(),1,{'ADELANTE'},now=101),('W',100))
        self.assertEqual(translate(self.event(id_vehiculo=2),1,{'ADELANTE'},now=101),(None,0))
    def test_never_replay_initial_state(self):
        self.assertEqual(translate(self.event(tipo='estado_inicial'),1,{'ADELANTE'},now=101),(None,0))
    def test_stale_duplicate_future_and_naive_dates_stop(self):
        for event,now,last in [(self.event(),104,0),(self.event(),101,100),(self.event(),98,0),
                               (self.event(timestamp='1970-01-01T00:01:40'),101,0)]:
            self.assertEqual(translate(event,1,{'ADELANTE'},now=now,last=last)[0],'X')
    def test_unsupported_and_disabled_commands_stop(self):
        self.assertEqual(translate(self.event(comando='POWER'),1,{'ADELANTE'},now=101)[0],'X')
        self.assertEqual(translate(self.event(comando='ATRAS'),1,{'ADELANTE'},now=101)[0],'X')
    def test_stop_does_not_need_timestamp_or_allowlist(self):
        self.assertEqual(translate({'tipo':'movimiento','id_vehiculo':1,'comando':'DETENER'},1,set())[0],'X')
    def test_demo_steps_and_all_terminal_events(self):
        self.assertEqual(translate(self.event(tipo='demo_movimiento'),1,{'ADELANTE'},now=101)[0],'W')
        for kind in ['demo_fin','demo_error','demo_cancelada']:
            self.assertEqual(translate({'tipo':kind,'id_vehiculo':1},1,set())[0],'X')
    def test_unknown_firmware_is_never_written_even_on_exit(self):
        class Port:
            def write(self, data): raise AssertionError('No debe escribir al firmware anterior')
            def close(self): pass
        output=Output();output.serial=Port()
        with self.assertRaises(RuntimeError): output.send('H')
        output.close()
    def test_simulation_never_opens_serial(self):
        import asyncio
        output=Output();asyncio.run(output.open());output.send('C W');output.close()
        self.assertIsNone(output.serial)


class RelayTests(unittest.IsolatedAsyncioTestCase):
    async def test_live_event_is_forwarded_then_stop_on_disconnect(self):
        import asyncio, json, time
        from types import SimpleNamespace
        from unittest.mock import patch
        from puente_usb import relay
        writes=[]
        class Out:
            serial=None
            def send(self, command): writes.append(command)
        class API:
            origin='https://example.invalid';token='local-test-token-only'
            def call(self,path):return {'reservada':True,'estado':'ACTIVA'}
        class WS:
            async def send(self,data):pass
            async def recv(self):return json.dumps({'tipo':'estado_inicial','id_vehiculo':1})
            async def ping(self):
                future=asyncio.get_running_loop().create_future();future.set_result(None);return future
            def __aiter__(self):return self.events()
            async def events(self):
                await asyncio.sleep(.2)
                yield json.dumps({'tipo':'movimiento','id_vehiculo':1,'comando':'ADELANTE','timestamp':datetime.now(timezone.utc).isoformat()})
        class Connection:
            async def __aenter__(self):return WS()
            async def __aexit__(self,*args):pass
        with patch('websockets.asyncio.client.connect',return_value=Connection()):
            await relay(API(),SimpleNamespace(unidad=1,permitir=['ADELANTE']),Out())
        self.assertIn('ARM',writes);self.assertIn('C W',writes);self.assertEqual(writes[-1],'X')

if __name__=='__main__': unittest.main()
