"""Cierre 4.3: exclusividad de empresa, catálogo, resumen y tasa de login.
Sólo crea modelos/unidades NUEVOS de software; no opera el vehículo 1.
"""
from contextlib import contextmanager
from datetime import datetime, timezone
import getpass
import json
from pathlib import Path
import secrets
import time
from websockets.sync.client import connect
from probar_admin_http import request, BASE


def main():
    print('Destino:', BASE, '· modelos y unidad NUEVOS sin hardware.')
    email = input('Correo administrador de la aplicación: ').strip()
    password = getpass.getpass('Contraseña de aplicación (entrada oculta): ')
    code, login = request('POST', '/auth/login', {'correo':email,'password':password})
    if code != 200 or login.get('usuario',{}).get('rol') != 'ADMINISTRADOR':
        raise SystemExit('No se pudo iniciar sesión como administrador.')
    token = login['access_token']
    code, second = request('POST', '/auth/login', {'correo':email,'password':password})
    password = None
    if code != 200: raise SystemExit('No se pudo abrir la segunda sesión.')
    other = second['access_token']
    suffix = secrets.token_hex(6)
    results = []; cleanup = []; leases = []; unit = model = None; commands = {}; body = {}
    report = {'destino':BASE,'fecha_utc':datetime.now(timezone.utc).isoformat(),'sin_hardware':True,'resultados':results,'limpieza':cleanup}
    def check(label, expected, method, path, body=None, auth=token):
        status, data = request(method,path,body,auth)
        print(f'{label}: HTTP {status} (esperado {expected})')
        results.append({'prueba':label,'http':status,'correcto':status==expected})
        if status != expected: raise RuntimeError(str(data.get('detail',label)))
        return data
    def record(label, okay):
        print(label + (': CORRECTO' if okay else ': INCORRECTO'))
        results.append({'prueba':label,'correcto':bool(okay)})
        if not okay: raise RuntimeError(label)
    def reserve(auth=token):
        lease = check('Reserva exclusiva empresa',201,'POST',f'/vehiculos/{unit}/control/reservar',auth=auth)['id_control']
        leases.append((lease,auth)); return lease
    @contextmanager
    def channel(lease, auth=token):
        with connect(BASE.replace('http','ws',1)+f'/ws/control/{lease}',open_timeout=10,close_timeout=3) as ws:
            ws.send(json.dumps({'tipo':'autenticar','token':auth}))
            record('Canal exclusivo autorizado',json.loads(ws.recv(timeout=10))['tipo']=='control_autorizado')
            yield ws
    def wait_free():
        until = time.monotonic()+12
        while time.monotonic()<until:
            status,data=request('GET',f'/vehiculos/{unit}/control',token=token)
            if status==200 and not data['reservada']: return
            time.sleep(.2)
        raise RuntimeError('No se confirmó la liberación de la unidad nueva.')
    try:
        model=check('Crear modelo privado',201,'POST','/admin/modelos',{'nombre':'Cierre HTTP '+suffix,'descripcion':'Prueba de software, sin hardware'})['id_modelo']
        caps={}
        for name,number in [('DETENER',13),('ADELANTE',1)]:
            caps[name]=check('Capacidad '+name,201,'POST',f'/admin/modelos/{model}/capacidades',{'nombre':name,'codigo':number,'descripcion':'Sólo software'})['id_capacidad']
        body={'nombre':'Cierre HTTP '+suffix,'id_modelo':model,'identificador_unidad':'CIERRE-'+suffix,'descripcion':'Unidad nueva sin hardware','microcontrolador':''}
        unit=check('Crear unidad nueva',201,'POST','/admin/unidades',body)['id_vehiculo']
        report.update(id_modelo=model,id_unidad=unit)
        record('No se opera unidad 1',unit!=1)
        commands={name:check('Crear comando '+name,201,'POST',f'/admin/unidades/{unit}/comandos',{'id_capacidad':cap})['id_comando'] for name,cap in caps.items()}
        demo=check('Crear demo de empresa',201,'POST','/mis-demos',{'id_vehiculo':unit,'nombre':'Cierre '+suffix,'pasos':[{'id_comando':commands['ADELANTE'],'duracion_ms':100,'pausa_ms':0}]})['id_demo']
        check('Empresa sin reserva no mueve',409,'POST',f'/vehiculos/{unit}/movimientos',{'id_comando':commands['ADELANTE']})
        check('Empresa sin reserva no inicia demo',409,'POST',f'/vehiculos/{unit}/demos/{demo}/iniciar')
        lease=reserve()
        check('Sin canal no mueve',409,'POST',f'/vehiculos/{unit}/movimientos',{'id_comando':commands['ADELANTE']})
        check('Otra sesión administrativa no reserva',409,'POST',f'/vehiculos/{unit}/control/reservar',auth=other)
        check('Otra sesión no cierra reserva',403,'POST',f'/control/{lease}/cerrar',auth=other)
        with channel(lease) as ws:
            check('Otra sesión no mueve',409,'POST',f'/vehiculos/{unit}/movimientos',{'id_comando':commands['ADELANTE']},other)
            check('Otra sesión no inicia demo',409,'POST',f'/vehiculos/{unit}/demos/{demo}/iniciar',auth=other)
            check('Otra sesión no cancela demo',409,'POST',f'/vehiculos/{unit}/demos/cancelar',auth=other)
            check('Titular mueve',201,'POST',f'/vehiculos/{unit}/movimientos',{'id_comando':commands['ADELANTE']})
            check('DETENER titular',201,'POST',f'/vehiculos/{unit}/movimientos',{'id_comando':commands['DETENER']})
            before=check('Historial antes',200,'GET',f'/vehiculos/{unit}/historial')['historial']
            check('Demo de empresa con reserva',202,'POST',f'/vehiculos/{unit}/demos/{demo}/iniciar')
            until=time.monotonic()+10
            while time.monotonic()<until:
                event=json.loads(ws.recv(timeout=max(.1,until-time.monotonic())))
                if event.get('tipo')=='demo_error':raise RuntimeError('Error de demo.')
                if event.get('tipo')=='demo_fin':
                    record('Demo finaliza solicitando DETENER',event.get('comando')=='DETENER');break
            else:raise RuntimeError('No llegó fin de demo.')
            after=check('Historial después',200,'GET',f'/vehiculos/{unit}/historial')['historial']
            record('Demo no añade pasos al historial individual',before==after)
            check('Cerrar reserva empresa',200,'POST',f'/control/{lease}/cerrar')
        wait_free()
        lease=reserve(other)
        with channel(lease,other): pass
        wait_free();record('Desconexión libera después de DETENER',True)
        check('Publicar modelo',200,'POST',f'/admin/modelos/{model}/publicacion',{'publico':True})
        check('Marcar exhibición',200,'POST',f'/admin/unidades/{unit}/exhibicion',{'habilitada':True})
        check('Configurar Invitado',200,'POST',f'/admin/unidades/{unit}/invitados',{'habilitada':True,'duracion_s':15,'pulso_ms':100,'comandos':list(commands.values())})
        offset=0;found=None
        while True:
            rows=check('Catálogo público paginado',200,'GET',f'/catalogo?limite=20&offset={offset}',auth=None)['modelos']
            found=next((r for r in rows if r['id_modelo']==model),None)
            if found or len(rows)<20:break
            offset+=20
        record('Capacidades públicas sin datos privados',found and {c['nombre'] for c in found['capacidades']}=={'DETENER','ADELANTE'} and not {'correo','id_propietario'}&found.keys())
        before=check('Resumen completo',200,'GET','/admin/resumen')
        record('Métricas demos y disponibilidad reales',before['demos_empresa_activas']>=1 and before['unidades_prueba_libres']>=1 and before['pruebas_habilitadas'])
        lease=reserve()
        check('Reserva de Invitado bloqueada por empresa',409,'POST','/invitados/sesiones',{'id_vehiculo':unit},None)
        after=check('Resumen durante reserva',200,'GET','/admin/resumen')
        record('Disponibilidad descuenta unidad reservada',after['unidades_prueba_libres']==before['unidades_prueba_libres']-1)
        check('Cerrar reserva final',200,'POST',f'/control/{lease}/cerrar');wait_free()
        audit=check('Auditoría de empresa',200,'GET','/admin/auditoria?limite=100')['eventos']
        record('Reserva y liberación de empresa auditadas',{'RESERVAR_EMPRESA','CERRAR_EMPRESA','LIBERAR_EMPRESA'} <= {r['accion'] for r in audit if str(r['id_recurso'])==str(unit)})
        # Last: do not consume the real administrator account's login allowance.
        invalid='inexistente-'+suffix+'@example.invalid'
        limited=False
        for _ in range(13):
            status,_=request('POST','/auth/login',{'correo':invalid,'password':'No es una cuenta real'})
            if status==429: limited=True;break
            if status!=401:raise RuntimeError('Respuesta inesperada al probar tasa de login.')
        record('Login limitado con HTTP 429',limited)
    finally:
        for lease,auth in leases:
            try:request('POST',f'/control/{lease}/cerrar',token=auth)
            except Exception:pass
        operations=[]
        if unit:
            operations += [(f'/admin/unidades/{unit}/invitados',{'habilitada':False,'duracion_s':15,'pulso_ms':100,'comandos':list(commands.values())}),
                           (f'/admin/unidades/{unit}/actualizar',{**body,'activo':False})]
        if model:operations += [(f'/admin/modelos/{model}/publicacion',{'publico':False}),
                                (f'/admin/modelos/{model}/actualizar',{'nombre':'Cierre HTTP '+suffix,'activo':False})]
        for path,document in operations:
            try:status,_=request('POST',path,document,token)
            except Exception:status=0
            cleanup.append({'ruta':path,'http':status,'correcto':status==200})
        for auth in (token,other):
            try:request('POST','/auth/logout',token=auth)
            except Exception:pass
        folder=Path.cwd()/'respaldos_rds';folder.mkdir(exist_ok=True)
        target=folder/('cierre_4_3_'+suffix+'.json');target.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
        print('Informe guardado en',target)
    if not all(r['correcto'] for r in cleanup):raise RuntimeError('Revisar limpieza en el informe antes de repetir.')
    print('Comprobaciones de cierre completadas. Registros de prueba privados e inactivos.')


if __name__=='__main__':main()
