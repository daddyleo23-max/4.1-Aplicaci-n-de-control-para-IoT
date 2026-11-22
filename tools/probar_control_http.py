"""Prueba control exclusivo sobre una unidad NUEVA de software, sin hardware."""
from contextlib import contextmanager
import getpass
import json
from pathlib import Path
import secrets
import time
from websockets.sync.client import connect
from websockets.exceptions import ConnectionClosed
from probar_admin_http import request, BASE


def main():
    print('Destino:',BASE,'· unidad NUEVA sin hardware. La caducidad real tarda unos 45 s.')
    email=input('Correo del administrador de la aplicación: ').strip()
    password=getpass.getpass('Contraseña de aplicación (entrada oculta): ')
    code, login=request('POST','/auth/login',{'correo':email,'password':password})
    password=None
    if code!=200 or login.get('usuario',{}).get('rol')!='ADMINISTRADOR':
        raise SystemExit('No se pudo iniciar sesión como administrador.')
    admin=login['access_token']; tokens=[admin]; leases=[]; results=[]
    suffix=secrets.token_hex(6); buyer_id=unit=model=None
    report={'destino':BASE,'resultados':results,'unidad_sin_hardware':True}
    def record(label,okay):
        results.append({'prueba':label,'correcto':bool(okay)})
        print(label+(': CORRECTO' if okay else ': INCORRECTO'))
        if not okay:raise RuntimeError(label)
    def check(label,expected,method,path,body=None,token=None):
        code,data=request(method,path,body,token)
        print(f'{label}: HTTP {code} (esperado {expected})')
        results.append({'prueba':label,'http':code,'correcto':code==expected})
        if code!=expected:raise RuntimeError(str(data.get('detail',label)))
        return data
    def buyer_login():
        row=check('Login comprador de prueba',200,'POST','/auth/login',{'correo':buyer_email,'password':buyer_password})
        tokens.append(row['access_token']);return row['access_token']
    def reserve(token):
        data=check('Reservar unidad nueva',201,'POST',f'/vehiculos/{unit}/control/reservar',token=token)
        leases.append((data['id_control'],token));return data['id_control']
    def wait_free(token,label):
        limit=time.monotonic()+12
        while time.monotonic()<limit:
            code,data=request('GET',f'/vehiculos/{unit}/control',token=token)
            if code==200 and not data['reservada']:
                record(label,True);return
            time.sleep(.25)
        record(label,False)
    @contextmanager
    def channel(lease,token):
        with connect(BASE.replace('http','ws',1)+f'/ws/control/{lease}',open_timeout=10,close_timeout=3) as ws:
            ws.send(json.dumps({'tipo':'autenticar','token':token}))
            data=json.loads(ws.recv(timeout=10))
            record('Canal exclusivo autorizado',data['tipo']=='control_autorizado' and data['id_vehiculo']==unit)
            yield ws
    def closed(ws,label,timeout=10):
        limit=time.monotonic()+timeout
        while time.monotonic()<limit:
            try:ws.recv(timeout=max(.1,limit-time.monotonic()))
            except ConnectionClosed:
                record(label,True);return
        record(label,False)
    try:
        model=check('Crear modelo privado',201,'POST','/admin/modelos',{'nombre':'Control HTTP '+suffix},admin)['id_modelo']
        body={'nombre':'Control HTTP '+suffix,'id_modelo':model,'identificador_unidad':'CTL-'+suffix,
              'descripcion':'Sólo software de prueba, sin hardware','microcontrolador':''}
        unit=check('Crear unidad sin hardware',201,'POST','/admin/unidades',body,admin)['id_vehiculo']
        report.update(id_modelo=model,id_unidad=unit)
        record('Unidad nueva distinta del montacargas 1',unit!=1)
        for name,number in [('DETENER',13),('ADELANTE',1)]:
            check('Capacidad de prueba '+name,201,'POST',f'/admin/modelos/{model}/capacidades',{'nombre':name,'codigo':number},admin)
            check('Crear comando '+name,201,'POST',f'/vehiculos/{unit}/comandos',{'nombre':name,'codigo':number},admin)
        commands=check('Catálogo unidad nueva',200,'GET',f'/vehiculos/{unit}/comandos',token=admin)['comandos']
        ids={c['nombre']:c['id_comando'] for c in commands}
        buyer_email='control-'+suffix+'@example.invalid';buyer_password=secrets.token_urlsafe(24)
        buyer_id=check('Crear comprador de prueba',201,'POST','/admin/clientes',
                       {'nombre':'Control HTTP '+suffix,'correo':buyer_email,'password':buyer_password},admin)['id_usuario']
        report['id_comprador']=buyer_id
        check('Asignar sólo unidad nueva',200,'POST',f'/admin/unidades/{unit}/asignar',{'id_usuario':buyer_id},admin)
        first=buyer_login();second=buyer_login()
        doc={'id_vehiculo':unit,'nombre':'Control demo '+suffix,'pasos':[{'id_comando':ids['ADELANTE'],'duracion_ms':10000,'pausa_ms':0}]}
        demo=check('Demo privada de prueba',201,'POST','/mis-demos',doc,first)['id_demo']
        check('Movimiento sin reserva rechazado',409,'POST',f'/vehiculos/{unit}/movimientos',{'id_comando':ids['ADELANTE']},first)
        check('Reserva sin login rechazada',401,'POST',f'/vehiculos/{unit}/control/reservar')
        check('Admin no adquiere unidad vendida',403,'POST',f'/vehiculos/{unit}/control/reservar',token=admin)
        lease=reserve(first)
        check('Movimiento sin canal rechazado',409,'POST',f'/vehiculos/{unit}/movimientos',{'id_comando':ids['ADELANTE']},first)
        check('Segunda sesión bloqueada',409,'POST',f'/vehiculos/{unit}/control/reservar',token=second)
        check('Otra sesión no cierra reserva',403,'POST',f'/control/{lease}/cerrar',token=second)
        with channel(lease,first) as ws:
            ws.send(json.dumps({'tipo':'renovar'}))
            record('Renovación por WS',json.loads(ws.recv(timeout=10))['tipo']=='control_renovado')
            with connect(BASE.replace('http','ws',1)+f'/ws/control/{lease}',open_timeout=10) as extra:
                extra.send(json.dumps({'tipo':'autenticar','token':first}))
                closed(extra,'Segundo canal rechazado sin reemplazar al primero')
            check('Movimiento aceptado del titular',201,'POST',f'/vehiculos/{unit}/movimientos',{'id_comando':ids['ADELANTE']},first)
            check('Otra sesión no mueve',409,'POST',f'/vehiculos/{unit}/movimientos',{'id_comando':ids['ADELANTE']},second)
            check('DETENER del titular',201,'POST',f'/vehiculos/{unit}/movimientos',{'id_comando':ids['DETENER']},first)
            check('Demo con reserva',202,'POST',f'/vehiculos/{unit}/demos/{demo}/iniciar',token=first)
            check('Otra sesión no cancela demo',409,'POST',f'/vehiculos/{unit}/demos/cancelar',token=second)
            check('DETENER interrumpe demo',201,'POST',f'/vehiculos/{unit}/movimientos',{'id_comando':ids['DETENER']},first)
            check('Cierre explícito',200,'POST',f'/control/{lease}/cerrar',token=first)
            closed(ws,'Canal cerrado al liberar')
        wait_free(second,'Reserva libre tras cierre')
        lease=reserve(second)
        with channel(lease,second):pass
        wait_free(first,'Desconexión solicita DETENER y libera')
        lease=reserve(first)
        with channel(lease,first) as ws:
            check('Logout titular',200,'POST','/auth/logout',token=first)
            closed(ws,'Logout cierra canal')
        wait_free(second,'Logout solicita DETENER y libera')
        lease=reserve(second)
        with channel(lease,second) as ws:
            print('Esperando caducidad real sin renovar (hasta 55 segundos)…')
            closed(ws,'Caducidad cierra canal',55)
        wait_free(second,'Caducidad solicita DETENER y libera')
        record('No se recrea reserva desde un movimiento',request('POST',f'/vehiculos/{unit}/movimientos',{'id_comando':ids['ADELANTE']},second)[0]==409)
        print('Comprobaciones HTTP/WS de control completadas.')
    finally:
        cleanup=[]
        for lease,token in leases:
            try:
                code,_=request('POST',f'/control/{lease}/cerrar',token=token)
                cleanup.append({'reserva':lease,'http':code})
            except Exception:cleanup.append({'reserva':lease,'error':True})
        if buyer_id:
            try:
                code,_=request('POST',f'/admin/clientes/{buyer_id}/actualizar',
                    {'nombre':'Control HTTP '+suffix,'correo':buyer_email,'activo':False},admin)
                cleanup.append({'comprador_inactivo':code==200})
            except Exception:cleanup.append({'comprador_inactivo':False})
        # La unidad asignada se conserva por integridad histórica; modelo privado y comprador inactivo.
        report['nota']='Modelo privado y unidad de software asignada conservados; comprador de prueba desactivado. No se modifica unidad 1.'
        report['limpieza']=cleanup
        for token in tokens:
            try:request('POST','/auth/logout',token=token)
            except Exception:pass
        folder=Path.cwd()/'respaldos_rds';folder.mkdir(exist_ok=True)
        target=folder/('control_http_'+suffix+'.json')
        target.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
        print('Informe guardado en',target)


if __name__=='__main__':main()
