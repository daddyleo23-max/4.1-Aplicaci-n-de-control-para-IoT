"""Puente de la sesión de monitoreo al ESP32. Por defecto NO abre el puerto USB."""
import argparse
import asyncio
from datetime import datetime, timezone
import getpass
import json
import time
import urllib.error
import urllib.request
from urllib.parse import urlsplit

COMMANDS = {'ADELANTE':'W','ATRAS':'S','GIRAR_IZQUIERDA':'A','GIRAR_DERECHA':'D',
            'SUBIR_HORQUILLA':'E','BAJAR_HORQUILLA':'Q','LUCES':'L','SONIDO':'N','VELOCIDAD':'V','DETENER':'X'}
STOP_EVENTS = {'demo_fin','demo_cancelada','demo_error'}


def translate(event, unit, allowed, *, now=None, last=0):
    """Nunca ejecutar estado_inicial, eventos de otra unidad ni una cola atrasada."""
    if not isinstance(event, dict) or event.get('id_vehiculo') != unit:
        return None, last
    kind = event.get('tipo')
    if kind in STOP_EVENTS:
        return 'X', last
    if kind not in ('movimiento','demo_movimiento'):
        return None, last
    name = event.get('comando')
    if name == 'DETENER':
        return 'X', last
    try:
        date = datetime.fromisoformat(event['timestamp'].replace('Z','+00:00'))
        if date.tzinfo is None: return 'X', last
        timestamp = date.timestamp()
    except (KeyError, ValueError, TypeError, AttributeError):
        return 'X', last
    age = (time.time() if now is None else now) - timestamp
    if age < -1 or age > 2 or timestamp <= last:
        return 'X', last
    if name not in allowed or name not in COMMANDS:
        return 'X', timestamp
    return COMMANDS[name], timestamp


class API:
    def __init__(self, origin): self.origin, self.token = origin.rstrip('/'), ''
    def call(self, path, body=None):
        headers = {'Accept':'application/json'}
        if self.token: headers['Authorization'] = 'Bearer ' + self.token
        if body is not None: headers['Content-Type'] = 'application/json'
        request = urllib.request.Request(self.origin+path,
            data=json.dumps(body).encode() if body is not None else None, headers=headers)
        try:
            with urllib.request.urlopen(request, timeout=2) as response:
                return json.load(response)
        except urllib.error.HTTPError as error:
            raise RuntimeError(f'API HTTP {error.code}; revisa la sesión y los permisos.') from None
        except (urllib.error.URLError, TimeoutError):
            raise RuntimeError('No se pudo consultar la API con HTTPS válido.') from None


class Output:
    def __init__(self, port=None): self.serial, self.port, self.verified = None, port, False
    async def open(self):
        if not self.port:
            print('SIMULACIÓN: no se abre ni se escribe en el puerto USB.')
            return
        import serial
        self.serial = serial.Serial(self.port,115200,timeout=.2,write_timeout=.3,exclusive=True)
        # Muchas placas reinician al abrir USB. Esperar sólo al protocolo nuevo.
        end = time.monotonic()+5
        while time.monotonic()<end:
            line = await asyncio.to_thread(self.serial.readline)
            if line.strip() == b'READY IOT43/1':
                self.verified = True
                return
        self.close()
        raise RuntimeError('El ESP32 no tiene el firmware USB IOT43/1. No se habilita movimiento.')
    def send(self, command):
        if self.serial and self.verified: self.serial.write((command+'\n').encode())
        elif self.serial: raise RuntimeError('Firmware sin identificar; no se envían órdenes.')
        elif command not in ('H','X'): print('SIMULACIÓN USB:',command)
    def close(self):
        if self.serial:
            try:
                if self.verified: self.serial.write(b'X\nDISARM\n')
            finally: self.serial.close(); self.serial = None; self.verified = False


async def relay(api, args, output):
    from websockets.asyncio.client import connect
    origin = urlsplit(api.origin)
    url = 'wss://'+origin.netloc+'/ws/vehiculos/'+str(args.unidad)
    state = {'lease':False,'checked':0.0,'pong':0.0,'command':False}
    def stop():
        output.send('X'); state['command'] = False
    async with connect(url, open_timeout=8, ping_interval=None, max_queue=1, max_size=32768) as ws:
        await ws.send(json.dumps({'tipo':'autenticar','token':api.token}))
        initial = json.loads(await asyncio.wait_for(ws.recv(),5))
        if initial.get('tipo')!='estado_inicial' or initial.get('id_vehiculo')!=args.unidad:
            raise RuntimeError('No se autorizó el canal de la unidad.')
        stop()
        print('Canal autorizado. No se reproduce el estado anterior.')
        async def watch_lease():
            while True:
                data = await asyncio.to_thread(api.call,f'/vehiculos/{args.unidad}/control')
                state['lease'] = data.get('reservada') is True and data.get('estado')=='ACTIVA'
                state['checked'] = time.monotonic()
                if not state['lease']: stop()
                await asyncio.sleep(.3)
        async def ping():
            while True:
                pong = await ws.ping()
                await asyncio.wait_for(pong,.75)
                state['pong'] = time.monotonic()
                await asyncio.sleep(.2)
        def live():
            now = time.monotonic()
            return state['lease'] and now-state['checked']<1.2 and now-state['pong']<1
        async def heartbeat():
            was_live = False
            while True:
                healthy = live()
                if healthy:
                    if not was_live: output.send('ARM')
                    output.send('H')
                else: stop()
                was_live = healthy
                await asyncio.sleep(.15)
        async def serial_feedback():
            while True:
                if output.serial:
                    line = await asyncio.to_thread(output.serial.readline)
                    if line.strip() in (b'WATCHDOG STOP',b'LIMIT STOP'):
                        print('ESP32:',line.decode().strip(),'; se requiere una orden nueva.')
                else: await asyncio.sleep(.2)
        async def receive():
            last = 0
            async for raw in ws:
                command, last = translate(json.loads(raw),args.unidad,set(args.permitir)|{'DETENER'},last=last)
                if command is None: continue
                if command=='X' or not live(): stop(); continue
                output.send('C '+command)
                print('Orden nueva:',command)
        tasks = [asyncio.create_task(f()) for f in (watch_lease,ping,heartbeat,receive,serial_feedback)]
        try:
            done, _ = await asyncio.wait(tasks,return_when=asyncio.FIRST_COMPLETED)
            for task in done: task.result()
        finally:
            stop()
            for task in tasks: task.cancel()
            await asyncio.gather(*tasks,return_exceptions=True)


async def main(args):
    api = API(args.api)
    email = input('Correo del comprador dueño: ').strip()
    password = getpass.getpass('Contraseña de aplicación (oculta): ')
    result = await asyncio.to_thread(api.call,'/auth/login',{'correo':email,'password':password})
    password = None
    api.token = result.get('access_token','')
    if not api.token: raise RuntimeError('No se obtuvo una sesión válida.')
    output = Output(args.puerto if args.activar else None)
    try:
        own = await asyncio.to_thread(api.call,'/mis-vehiculos')
        if args.unidad not in [u['id_vehiculo'] for u in own.get('vehiculos',[])]:
            raise RuntimeError('La cuenta debe ser propietaria de la unidad física.')
        await output.open()
        await relay(api,args,output)
    finally:
        output.close()
        try: await asyncio.to_thread(api.call,'/auth/logout',{})
        except Exception: pass
        api.token = ''


def arguments():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--api',default='https://34.194.45.28')
    parser.add_argument('--unidad',type=int,default=1)
    parser.add_argument('--puerto',default='/dev/ttyUSB0')
    parser.add_argument('--activar',action='store_true',help='Activa USB; exige el firmware nuevo y área de prueba preparada.')
    parser.add_argument('--permitir',nargs='+',choices=sorted(set(COMMANDS)-{'DETENER'}),default=['ADELANTE'])
    args = parser.parse_args()
    origin = urlsplit(args.api)
    if origin.scheme!='https' or not origin.hostname or origin.username or origin.password or origin.path not in ('','/') or origin.query or origin.fragment:
        parser.error('--api debe ser un origen HTTPS sin credenciales ni rutas.')
    if args.unidad<1: parser.error('Unidad inválida.')
    return args

if __name__=='__main__':
    try: asyncio.run(main(arguments()))
    except KeyboardInterrupt: print('\nPuente detenido; salidas desactivadas.')
    except Exception as error: raise SystemExit(str(error))
