"""Soporte operativo sobre una unidad NUEVA sin hardware; no opera la unidad 1."""
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
    print('Destino:',BASE,'· unidad NUEVA sin hardware. La prueba de caducidad dura aproximadamente 1 minuto.')
    email=input('Correo del administrador de la aplicación: ').strip()
    password=getpass.getpass('Contraseña de aplicación (entrada oculta): ')
    code,login=request('POST','/auth/login',{'correo':email,'password':password})
    password=None
    if code!=200 or login.get('usuario',{}).get('rol')!='ADMINISTRADOR':raise SystemExit('Login de administrador rechazado.')
    admin=login['access_token']; admin_id=login['usuario']['id_usuario']; tokens=[admin]
    results=[]; leases=[]; permissions=[]; owner=None; unit=buyer=None
    suffix=secrets.token_hex(6)
    report={'destino':BASE,'resultados':results,'sin_hardware':True}
    def record(label,okay):
        print(label+(': CORRECTO' if okay else ': INCORRECTO'))
        results.append({'prueba':label,'correcto':bool(okay)})
        if not okay:raise RuntimeError(label)
    def check(label,expected,method,path,body=None,token=None):
        code,data=request(method,path,body,token)
        print(f'{label}: HTTP {code} (esperado {expected})')
        results.append({'prueba':label,'http':code,'correcto':code==expected})
        if code!=expected:raise RuntimeError(str(data.get('detail',label)))
        return data
    def consent(operational):
        row=check('Consentimiento operativo' if operational else 'Consentimiento sólo diagnóstico',201,
                  'POST',f'/vehiculos/{unit}/soporte',{'id_administrador':admin_id,'minutos':1,'operativo':operational},owner)
        permissions.append(row['id_permiso'])
        record('Alcance explícito conservado',row['alcance']==('OPERATIVO' if operational else 'MONITOREO'))
        return row['id_permiso']
    def reserve(token):
        row=check('Reserva exclusiva',201,'POST',f'/vehiculos/{unit}/control/reservar',token=token)
        leases.append((row['id_control'],token));return row['id_control']
    @contextmanager
    def channel(lease,token):
        with connect(BASE.replace('http','ws',1)+f'/ws/control/{lease}',open_timeout=10,close_timeout=3) as ws:
            ws.send(json.dumps({'tipo':'autenticar','token':token}))
            row=json.loads(ws.recv(timeout=10))
            record('Canal autorizado de la reserva',row.get('tipo')=='control_autorizado' and row.get('id_vehiculo')==unit)
            yield ws
    def closed(ws,label):
        limit=time.monotonic()+12
        while time.monotonic()<limit:
            try:ws.recv(timeout=max(.1,limit-time.monotonic()))
            except ConnectionClosed:record(label,True);return
        record(label,False)
    def free():
        limit=time.monotonic()+12
        while time.monotonic()<limit:
            code,row=request('GET',f'/vehiculos/{unit}/control',token=owner)
            if code==200 and not row['reservada']:record('Reserva liberada después de DETENER',True);return
            time.sleep(.25)
        record('Reserva liberada después de DETENER',False)
    try:
        model=check('Modelo privado de prueba',201,'POST','/admin/modelos',{'nombre':'Soporte HTTP '+suffix},admin)['id_modelo']
        unit=check('Unidad nueva de software',201,'POST','/admin/unidades',
                   {'nombre':'Soporte HTTP '+suffix,'id_modelo':model,'identificador_unidad':'SUP-'+suffix,
                    'descripcion':'Prueba de API sin hardware','microcontrolador':''},admin)['id_vehiculo']
        report.update(id_unidad=unit,id_modelo=model)
        record('La unidad no es el montacargas 1',unit!=1)
        for name,number in [('DETENER',13),('ADELANTE',1)]:
            check('Capacidad de prueba '+name,201,'POST',f'/admin/modelos/{model}/capacidades',{'nombre':name,'codigo':number},admin)
            check('Registrar '+name,201,'POST',f'/vehiculos/{unit}/comandos',{'nombre':name,'codigo':number},admin)
        cmds=check('Comandos de prueba',200,'GET',f'/vehiculos/{unit}/comandos',token=admin)['comandos']
        ids={c['nombre']:c['id_comando'] for c in cmds}
        mail='soporte-'+suffix+'@example.invalid'; secret=secrets.token_urlsafe(24)
        buyer=check('Comprador de prueba',201,'POST','/admin/clientes',{'nombre':'Soporte HTTP '+suffix,'correo':mail,'password':secret},admin)['id_usuario']
        report['id_comprador']=buyer
        owner=check('Login dueño de prueba',200,'POST','/auth/login',{'correo':mail,'password':secret})['access_token'];tokens.append(owner)
        check('Asignar sólo unidad nueva',200,'POST',f'/admin/unidades/{unit}/asignar',{'id_usuario':buyer},admin)
        demo=check('Demo privada protegida',201,'POST','/mis-demos',{'id_vehiculo':unit,'nombre':'Privada '+suffix,
             'pasos':[{'id_comando':ids['ADELANTE'],'duracion_ms':100,'pausa_ms':0}]},owner)['id_demo']
        check('Sin consentimiento no reserva',403,'POST',f'/vehiculos/{unit}/control/reservar',token=admin)
        check('Administrador no se autoautoriza',403,'POST',f'/vehiculos/{unit}/soporte',
              {'id_administrador':admin_id,'minutos':1,'operativo':True},admin)
        consent(False)
        check('Diagnóstico no permite reservar',403,'POST',f'/vehiculos/{unit}/control/reservar',token=admin)
        buyer_lease=reserve(owner)
        permission=consent(True)
        check('Soporte no toma reserva del dueño',409,'POST',f'/vehiculos/{unit}/control/reservar',token=admin)
        check('Liberar reserva del dueño',200,'POST',f'/control/{buyer_lease}/cerrar',token=owner)
        lease=reserve(admin)
        check('Soporte sin canal no mueve',409,'POST',f'/vehiculos/{unit}/movimientos',{'id_comando':ids['ADELANTE']},admin)
        with channel(lease,admin) as ws:
            check('Dueño no controla simultáneamente',409,'POST',f'/vehiculos/{unit}/control/reservar',token=owner)
            check('Movimiento manual de soporte',201,'POST',f'/vehiculos/{unit}/movimientos',{'id_comando':ids['ADELANTE']},admin)
            check('DETENER de soporte',201,'POST',f'/vehiculos/{unit}/movimientos',{'id_comando':ids['DETENER']},admin)
            check('Soporte no ejecuta demo privada',403,'POST',f'/vehiculos/{unit}/demos/{demo}/iniciar',token=admin)
            check('Revocar desde el dueño',200,'POST',f'/vehiculos/{unit}/soporte/{permission}/revocar',token=owner)
            closed(ws,'Revocación cierra canal de soporte')
        free()
        check('Soporte revocado no mueve',403,'POST',f'/vehiculos/{unit}/movimientos',{'id_comando':ids['ADELANTE']},admin)
        # Capacidad efectiva de volver a controlar desde la cuenta propietaria.
        buyer_lease=reserve(owner)
        check('Liberar control recuperado',200,'POST',f'/control/{buyer_lease}/cerrar',token=owner)
        consent(True);lease=reserve(admin)
        with channel(lease,admin):pass
        free()
        permission=consent(True);lease=reserve(admin)
        with channel(lease,admin) as ws:
            print('Esperando caducidad del permiso con renovación WS cada 5 s (hasta 75 s)…')
            limit=time.monotonic()+75
            stopped=False
            while time.monotonic()<limit:
                try:
                    ws.send(json.dumps({'tipo':'renovar'}))
                    ws.recv(timeout=5)
                    time.sleep(5)
                except ConnectionClosed:
                    stopped=True;break
            record('Permiso vencido cierra aunque se renueve el canal',stopped)
        free()
        check('Permiso vencido no adquiere',403,'POST',f'/vehiculos/{unit}/control/reservar',token=admin)
        audit=check('Auditoría de soporte',200,'GET','/admin/auditoria?limite=100',token=admin)
        rows=audit.get('eventos',audit.get('auditoria',[]))
        actions={r['accion'] for r in rows if str(r.get('id_recurso'))==str(unit)}
        record('Consentimiento y reserva auditados',{'AUTORIZAR_SOPORTE_OPERATIVO','RESERVAR_SOPORTE','CERRAR_SOPORTE','LIBERAR_SOPORTE'}<=actions)
    finally:
        cleanup=[]
        for lease,token in leases:
            try:code,_=request('POST',f'/control/{lease}/cerrar',token=token);cleanup.append({'control':lease,'http':code})
            except Exception:cleanup.append({'control':lease,'error':True})
        if owner and unit:
            for permission in permissions:
                try:request('POST',f'/vehiculos/{unit}/soporte/{permission}/revocar',token=owner)
                except Exception:pass
        if buyer:
            try:
                code,_=request('POST',f'/admin/clientes/{buyer}/actualizar',{'nombre':'Soporte HTTP '+suffix,'correo':mail,'activo':False},admin)
                cleanup.append({'comprador_inactivo':code==200})
            except Exception:cleanup.append({'comprador_inactivo':False})
        report['limpieza']=cleanup
        report['nota']='Unidad de software asignada y modelo privado conservados por historial; comprador de prueba desactivado. Unidad 1 sin cambios.'
        for token in tokens:
            try:request('POST','/auth/logout',token=token)
            except Exception:pass
        folder=Path.cwd()/'respaldos_rds';folder.mkdir(exist_ok=True)
        target=folder/('soporte_operativo_'+suffix+'.json')
        target.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8');print('Informe guardado en',target)
    print('Comprobaciones de soporte operativo completadas.')


if __name__=='__main__':main()
