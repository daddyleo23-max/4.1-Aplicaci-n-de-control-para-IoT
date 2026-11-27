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
    def test_late_movement_does_not_restart_after_stop(self):
        _,cursor=translate(self.event(comando='DETENER'),1,set(),now=101)
        command,_=translate(self.event(),1,{'ADELANTE'},now=101,last=cursor)
        self.assertEqual(command,'X')

    def test_demo_steps_and_all_terminal_events(self):
        self.assertEqual(translate(self.event(tipo='demo_movimiento'),1,{'ADELANTE'},now=101)[0],'W')
        for kind in ['demo_fin','demo_error','demo_cancelada']:
            self.assertEqual(translate({'tipo':kind,'id_vehiculo':1},1,set())[0],'X')
    def test_confirmed_functions_and_unverified_actions(self):
        expected={'ATRAS':'S','GIRAR_IZQUIERDA':'A','GIRAR_DERECHA':'D','SUBIR_HORQUILLA':'E','BAJAR_HORQUILLA':'Q','SONIDO':'N'}
        for name,letter in expected.items():
            self.assertEqual(translate(self.event(comando=name),1,{name},now=101)[0],letter)
        for name in ('LUCES','VELOCIDAD','POWER','DEMO'):
            self.assertEqual(translate(self.event(comando=name),1,{name},now=101)[0],'X')
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
        await self.exercise(0)

    async def test_slow_pong_does_not_end_valid_channel(self):
        await self.exercise(.85)

    async def test_manual_is_renewed_beyond_one_second_without_repeating_start(self):
        writes = await self.exercise(0, hold_after=1.25)
        self.assertEqual(writes.count('C W 0'),1)
        self.assertGreaterEqual(writes.count('R'),5)

    async def test_demo_stops_at_duration_and_is_not_renewed_during_pause(self):
        writes = await self.exercise(0, hold_after=.4, demo_ms=50)
        start=writes.index('C W 50')
        self.assertIn('X',writes[start+1:-1])
        self.assertNotIn('R',writes)

    async def test_temporary_reservation_failure_stops_without_replaying_on_recovery(self):
        writes = await self.exercise(0, hold_after=2, transient_error=True)
        self.assertEqual(writes.count('C W 0'),1)
        last_arm=len(writes)-1-writes[::-1].index('ARM')
        self.assertNotIn('R',writes[last_arm+1:])
        self.assertEqual(writes[-1],'X')

    async def exercise(self, latency, hold_after=0, demo_ms=None, transient_error=False):
        import asyncio, json, time
        from types import SimpleNamespace
        from unittest.mock import patch
        from puente_usb import relay, ApiFailure
        writes=[]
        class Out:
            serial=None
            def send(self, command): writes.append(command)
        class API:
            origin='https://example.invalid';token='local-test-token-only'
            calls=0
            def call(self,path):
                self.calls+=1
                if transient_error and self.calls==2: raise ApiFailure('Prueba de timeout',transient=True)
                return {'reservada':True,'estado':'ACTIVA'}
        class WS:
            async def send(self,data):pass
            async def recv(self):return json.dumps({'tipo':'estado_inicial','id_vehiculo':1})
            async def ping(self):
                future=asyncio.get_running_loop().create_future()
                asyncio.get_running_loop().call_later(latency,future.set_result,None)
                return future
            def __aiter__(self):return self.events()
            async def events(self):
                await asyncio.sleep(latency+.25)
                yield json.dumps({'tipo':'demo_movimiento' if demo_ms else 'movimiento','id_vehiculo':1,'comando':'ADELANTE','duracion_ms':demo_ms,'timestamp':datetime.now(timezone.utc).isoformat()})
                await asyncio.sleep(hold_after)
        class Connection:
            async def __aenter__(self):return WS()
            async def __aexit__(self,*args):pass
        with patch('websockets.asyncio.client.connect',return_value=Connection()):
            with self.assertRaisesRegex(RuntimeError,'cerró el canal'):
                await relay(API(),SimpleNamespace(unidad=1,permitir=['ADELANTE']),Out())
        self.assertIn('ARM',writes);self.assertIn(f'C W {demo_ms or 0}',writes);self.assertEqual(writes[-1],'X')
        return writes

class MotionTests(unittest.TestCase):
    def test_manual_has_no_fixed_one_second_limit(self):
        from puente_usb import Motion
        motion=Motion();motion.begin('E',now=1)
        self.assertFalse(motion.expired(now=100))
        self.assertTrue(motion.renewable())
    def test_timed_demo_expires_and_never_renews(self):
        from puente_usb import Motion
        motion=Motion();motion.begin('W',1500,now=10)
        self.assertFalse(motion.expired(now=11.49))
        self.assertTrue(motion.expired(now=11.5))
        self.assertFalse(motion.renewable())
    def test_stop_clears_manual_and_a_new_step_replaces_old_deadline(self):
        from puente_usb import Motion
        motion=Motion();motion.begin('W',100,now=10);motion.begin('E',0,now=10.05)
        self.assertFalse(motion.expired(now=11))
        motion.clear();self.assertFalse(motion.renewable())
        self.assertIsNone(motion.command)

class ApiErrors(unittest.TestCase):
    def test_login_401_has_specific_diagnostic(self):
        import urllib.error
        from unittest.mock import patch
        from puente_usb import API
        error=urllib.error.HTTPError('https://example.invalid/auth/login',401,'Unauthorized',{},None)
        with patch('urllib.request.urlopen',side_effect=error) as call:
            with self.assertRaisesRegex(RuntimeError,'Login rechazado'):
                API('https://example.invalid').call('/auth/login',{'correo':'local@example.invalid','password':'test-only'})
        error.close()
        self.assertEqual(call.call_args.kwargs['timeout'],10)
    def test_control_timeout_stays_short(self):
        from unittest.mock import patch
        from puente_usb import API
        with patch('urllib.request.urlopen',side_effect=TimeoutError) as call:
            with self.assertRaisesRegex(RuntimeError,'/vehiculos/1/control'):
                API('https://example.invalid').call('/vehiculos/1/control')
        self.assertEqual(call.call_args.kwargs['timeout'],3.0)

class LauncherTests(unittest.TestCase):
    def test_launcher_preserves_explicit_activation_and_confirmed_commands(self):
        import json, os, shutil, subprocess, tempfile
        from pathlib import Path
        if not shutil.which('bash'): self.skipTest('El lanzador es para Linux/bash')
        script=Path(__file__).with_name('iniciar_puente.sh')
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            fake=root/'python-local-test'
            fake.write_text('#!/usr/bin/env python3\nimport os,sys,json\nif sys.argv[1:2] != ["-c"]:\n open(os.environ["IOT_TEST_ARGS"],"w").write(json.dumps(sys.argv[1:]))\n')
            fake.chmod(0o700)
            env={**os.environ,'IOT_BRIDGE_PYTHON':str(fake),'IOT_TEST_ARGS':str(root/'args.json')}
            for flags in ([],['--activar']):
                subprocess.run(['bash',str(script),*flags],env=env,check=True,capture_output=True,text=True)
                args=json.loads((root/'args.json').read_text())
                self.assertEqual('--activar' in args,bool(flags))
                self.assertIn('GIRAR_IZQUIERDA',args)
                self.assertIn('SONIDO',args)
                self.assertNotIn('POWER',args)
                self.assertNotIn('VELOCIDAD',args)
                self.assertEqual(args[args.index('--unidad')+1],'1')

if __name__=='__main__': unittest.main()
