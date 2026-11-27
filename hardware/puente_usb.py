"""Puente de la sesión de monitoreo al ESP32. Por defecto NO abre el puerto USB."""
import argparse
import asyncio
from datetime import datetime, timezone
import getpass
import json
import ssl
import time
import urllib.error
import urllib.request
from urllib.parse import urlsplit

COMMANDS = {'ADELANTE':'W','ATRAS':'S','GIRAR_IZQUIERDA':'A','GIRAR_DERECHA':'D',
            'SUBIR_HORQUILLA':'E','BAJAR_HORQUILLA':'Q','SONIDO':'N','VELOCIDAD':'V','DETENER':'X'}
STOP_EVENTS = {'demo_fin','demo_cancelada','demo_error'}
PING_TIMEOUT_S = 3.0
LEASE_TIMEOUT_S = 3.0
FRESH_LINK_S = 3.5


def translate(event, unit, allowed, *, now=None, last=0):
    """Nunca ejecutar estado_inicial, eventos de otra unidad ni una cola atrasada."""
    if not isinstance(event, dict) or event.get('id_vehiculo') != unit:
        return None, last
    kind = event.get('tipo')
    if kind in STOP_EVENTS or (kind=='movimiento' and event.get('comando')=='DETENER') or (kind=='demo_movimiento' and event.get('comando')=='DETENER'):
        # STOP siempre se atiende y marca el orden temporal: un movimiento anterior
        # que llegue tarde no debe volver a arrancar después de esa parada.
        try:
            date=datetime.fromisoformat(event['timestamp'].replace('Z','+00:00'))
            if date.tzinfo: last=max(last,date.timestamp())
        except (KeyError,ValueError,TypeError,AttributeError): pass
        return 'X', last
    if kind not in ('movimiento','demo_movimiento'):
        return None, last
    name = event.get('comando')
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


class Motion:
    """Una orden manual se renueva; un paso de demo siempre tiene vencimiento."""
    def __init__(self): self.clear()
    def clear(self): self.command, self.deadline = None, None
    def begin(self, command, duration_ms=0, *, now=None):
        self.command = command
        self.deadline = (time.monotonic() if now is None else now)+duration_ms/1000 if duration_ms else None
    def expired(self, *, now=None):
        return self.deadline is not None and (time.monotonic() if now is None else now)>=self.deadline
    def renewable(self): return self.command is not None and self.deadline is None


class ApiFailure(RuntimeError):
    def __init__(self, message, *, transient=False):
        super().__init__(message); self.transient = transient


class API:
    def __init__(self, origin): self.origin, self.token = origin.rstrip('/'), ''
    def call(self, path, body=None):
        headers = {'Accept':'application/json'}
        if self.token: headers['Authorization'] = 'Bearer ' + self.token
        if body is not None: headers['Content-Type'] = 'application/json'
        request = urllib.request.Request(self.origin+path,
            data=json.dumps(body).encode() if body is not None else None, headers=headers)
        try:
            with urllib.request.urlopen(request, timeout=10 if path in ('/auth/login','/mis-vehiculos') else LEASE_TIMEOUT_S) as response:
                return json.load(response)
        except urllib.error.HTTPError as error:
            if path == '/auth/login' and error.code == 401:
                raise ApiFailure('Login rechazado (HTTP 401): revisa el correo y la contraseña de APLICACIÓN del comprador; no uses las credenciales de RDS.') from None
            raise ApiFailure(f'{path}: API HTTP {error.code}; revisa la sesión y los permisos.', transient=error.code in (429,502,503,504)) from None
        except TimeoutError:
            raise ApiFailure(f'{path}: la API agotó el tiempo de espera; comprueba el backend y Caddy.', transient=True) from None
        except urllib.error.URLError as error:
            if isinstance(error.reason,ssl.SSLCertVerificationError):
                raise ApiFailure(f'{path}: no se pudo validar el certificado HTTPS. No se desactiva TLS.') from None
            if isinstance(error.reason,TimeoutError):
                raise ApiFailure(f'{path}: se agotó el tiempo para conectar con la API.', transient=True) from None
            raise ApiFailure(f'{path}: no se pudo conectar a la API ({type(error.reason).__name__}). Revisa servidor, red e IP pública.', transient=True) from None


class Output:
    def __init__(self, port=None):
        self.serial, self.port, self.verified = None, port, False
        self.last = None
    async def open(self):
        if not self.port:
            print('SIMULACIÓN: no se abre ni se escribe en el puerto USB.')
            return
        import serial
        self.serial = serial.Serial(self.port,115200,timeout=.2,write_timeout=.3,exclusive=True)
        # Muchas placas reinician al abrir USB. Esperar sólo al protocolo nuevo.
        print(f'Puerto {self.port} abierto a 115200. Pulsa EN/RESET ahora (no BOOT); espero READY IOT43/5 durante 20 s.',flush=True)
        end = time.monotonic()+20
        while time.monotonic()<end:
            line = await asyncio.to_thread(self.serial.readline)
            if line.strip() == b'READY IOT43/5':
                self.verified = True
                print('Firmware IOT43/5 identificado; salidas todavía detenidas.',flush=True)
                return
        self.close()
        raise RuntimeError('No se recibió READY IOT43/5 durante la espera. Esto no demuestra que falte el firmware. Cierra el monitor serie y pulsa EN/RESET cuando el puente indique que abrió el puerto.')
    def send(self, command):
        if self.serial and self.verified: self.serial.write((command+'\n').encode())
        elif self.serial: raise RuntimeError('Firmware sin identificar; no se envían órdenes.')
        elif command not in ('H','R') and command != self.last: print('SIMULACIÓN USB:',command)
        if command not in ('H','R'): self.last = command
    def close(self):
        if self.serial:
            try:
                if self.verified: self.serial.write(b'X\nDISARM\n')
            finally: self.serial.close(); self.serial = None; self.verified = False


async def relay(api, args, output):
    from websockets.asyncio.client import connect
    origin = urlsplit(api.origin)
    url = 'wss://'+origin.netloc+'/ws/vehiculos/'+str(args.unidad)
    state = {'lease':False,'checked':0.0,'pong':0.0,'armed':False}
    motion = Motion()
    def stop():
        output.send('X'); motion.clear()
    async with connect(url, open_timeout=8, ping_interval=None, max_queue=1, max_size=32768) as ws:
        await ws.send(json.dumps({'tipo':'autenticar','token':api.token}))
        initial = json.loads(await asyncio.wait_for(ws.recv(),5))
        if initial.get('tipo')!='estado_inicial' or initial.get('id_vehiculo')!=args.unidad:
            raise RuntimeError('No se autorizó el canal de la unidad.')
        stop()
        print('Canal autorizado. No se reproduce el estado anterior.')
        async def watch_lease():
            while True:
                try:
                    data = await asyncio.to_thread(api.call,f'/vehiculos/{args.unidad}/control')
                except ApiFailure as error:
                    state['lease'] = False; state['checked'] = 0; stop()
                    if not error.transient: raise
                    print('Reserva sin verificar: STOP. Se reintentará sin reanudar la orden anterior.')
                    await asyncio.sleep(1)
                    continue
                reserved = data.get('reservada') is True and data.get('estado')=='ACTIVA'
                if reserved != state['lease'] or not state['checked']:
                    print('Reserva:', 'ACTIVA' if reserved else 'sin control activo; adquiere control desde la web.')
                state['lease'] = reserved
                state['checked'] = time.monotonic()
                if not state['lease']: stop()
                await asyncio.sleep(.8)
        async def ping():
            while True:
                started = time.monotonic()
                pong = await ws.ping()
                try:
                    await asyncio.wait_for(pong,PING_TIMEOUT_S)
                except asyncio.TimeoutError:
                    raise RuntimeError('No llegó la respuesta al ping WSS en 3 s. Se solicita STOP y se cierra el puente; revisar latencia/servidor.') from None
                state['pong'] = time.monotonic()
                latency = state['pong']-started
                if getattr(args,'diagnostico',False) and latency>=.5:
                    print('Latencia WSS:',round(latency,2),'s')
                await asyncio.sleep(.5)
        def live():
            now = time.monotonic()
            return state['lease'] and now-state['checked']<FRESH_LINK_S and now-state['pong']<FRESH_LINK_S
        async def heartbeat():
            while True:
                healthy = live()
                if healthy:
                    if not state['armed']:
                        output.send('ARM'); state['armed'] = True
                    output.send('H')
                    if motion.expired():
                        stop(); print('Paso de demo terminado; salidas liberadas durante la pausa.')
                    elif motion.renewable(): output.send('R')
                else:
                    stop(); state['armed'] = False
                await asyncio.sleep(.15)
        async def serial_feedback():
            while True:
                if output.serial:
                    line = await asyncio.to_thread(output.serial.readline)
                    if line.strip() in (b'WATCHDOG STOP',b'LEASE STOP',b'STEP STOP'):
                        if line.strip()==b'WATCHDOG STOP':
                            stop(); state['armed'] = False
                        print('ESP32:',line.decode().strip(),'; salida liberada, no se repite la orden anterior.')
                else: await asyncio.sleep(.2)
        async def receive():
            last = 0
            async for raw in ws:
                event = json.loads(raw)
                if getattr(args,'diagnostico',False) and isinstance(event,dict):
                    # No imprimir la trama completa: puede contener datos innecesarios.
                    print('Evento recibido:',event.get('tipo'),'unidad:',event.get('id_vehiculo'),'comando:',event.get('comando'))
                    if event.get('timestamp'):
                        try:
                            date=datetime.fromisoformat(event['timestamp'].replace('Z','+00:00'))
                            if date.tzinfo: print('Antigüedad del evento (s):',round(time.time()-date.timestamp(),3))
                        except (ValueError,TypeError,AttributeError): pass
                command, last = translate(event,args.unidad,set(args.permitir)|{'DETENER'},last=last)
                if command is None: continue
                if command=='X' or not live():
                    if getattr(args,'diagnostico',False):
                        print('STOP:', 'DETENER, límite o evento rechazado.' if command=='X' else 'reserva o verificación de enlace sin vigencia.')
                    stop(); continue
                duration = 0
                is_demo = event.get('tipo')=='demo_movimiento'
                if is_demo:
                    duration = event.get('duracion_ms')
                    if type(duration) is not int or not 1<=duration<=10000:
                        stop(); print('STOP: duración de demo inválida.'); continue
                    stop()  # Cancelar el paso previo antes de comenzar otro; nunca dejar su temporizador pendiente.
                if not state['armed']:
                    output.send('ARM'); output.send('H'); state['armed'] = True
                if command not in ('N','V'): motion.begin(command,duration)
                output.send(f'C {command} {duration}')
                print('Orden nueva:',command,'(pulso corto)' if command in ('N','V') else ('paso '+str(duration)+' ms') if is_demo else '(manual hasta DETENER)')
            closed = getattr(ws,'close_code',None)
            raise RuntimeError(f'El servidor cerró el canal WSS (código {closed}). STOP solicitado; no se reconecta ni reproduce órdenes.')
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
    parser.add_argument('--diagnostico',action='store_true',help='Muestra reserva y tipo de eventos, sin tokens ni contraseñas.')
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
    except Exception as error: raise SystemExit('Puente detenido: '+(str(error) or type(error).__name__))
