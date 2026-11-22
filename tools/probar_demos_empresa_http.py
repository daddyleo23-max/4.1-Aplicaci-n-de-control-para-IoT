"""Demos de empresa: permisos y fin con DETENER en unidades NUEVAS sin hardware."""
from contextlib import contextmanager
import getpass
import json
from pathlib import Path
import secrets
import time
from websockets.sync.client import connect
from probar_admin_http import request, BASE


def main():
    print('Destino:',BASE,'· sólo unidades NUEVAS de software, sin hardware.')
    mail=input('Correo administrador de la aplicación: ').strip()
    password=getpass.getpass('Contraseña de aplicación (entrada oculta): ')
    code,login=request('POST','/auth/login',{'correo':mail,'password':password});password=None
    if code!=200 or login.get('usuario',{}).get('rol')!='ADMINISTRADOR':raise SystemExit('Login rechazado.')
    admin=login['access_token'];tokens=[admin];results=[];suffix=secrets.token_hex(6)
    unit=other=model=None;buyers=[];leases=[]
    report={'destino':BASE,'resultados':results,'sin_hardware':True}
    def check(label,expected,method,path,body=None,token=admin):
        code,data=request(method,path,body,token)
        print(f'{label}: HTTP {code} (esperado {expected})');results.append({'prueba':label,'http':code,'correcto':code==expected})
        if code!=expected:raise RuntimeError(str(data.get('detail',label)))
        return data
    def record(label,okay):
        print(label+(': CORRECTO' if okay else ': INCORRECTO'));results.append({'prueba':label,'correcto':bool(okay)})
        if not okay:raise RuntimeError(label)
    def buyer(label):
        email='demo-'+label+'-'+suffix+'@example.invalid';secret=secrets.token_urlsafe(24);name='Demo '+label+' '+suffix
        uid=check('Crear comprador '+label,201,'POST','/admin/clientes',{'nombre':name,'correo':email,'password':secret})['id_usuario']
        buyers.append((uid,name,email))
        token=check('Login comprador '+label,200,'POST','/auth/login',{'correo':email,'password':secret},None)['access_token'];tokens.append(token)
        return uid,token
    @contextmanager
    def channel(path,token,kind):
        with connect(BASE.replace('http','ws',1)+path,open_timeout=10,close_timeout=3) as ws:
            ws.send(json.dumps({'tipo':'autenticar','token':token}))
            record('Canal autorizado',json.loads(ws.recv(timeout=10))['tipo']==kind)
            yield ws
    def finished(ws):
        deadline=time.monotonic()+12
        while time.monotonic()<deadline:
            event=json.loads(ws.recv(timeout=max(.1,deadline-time.monotonic())))
            if event.get('tipo')=='demo_error':raise RuntimeError('La demo reportó error.')
            if event.get('tipo')=='demo_fin':
                record('Fin incluye solicitud explícita de DETENER',event.get('comando')=='DETENER' and event.get('codigo')==13)
                return
        raise RuntimeError('No llegó demo_fin.')
    try:
        model=check('Modelo privado nuevo',201,'POST','/admin/modelos',{'nombre':'Empresa HTTP '+suffix})['id_modelo']
        caps={}
        for name,code in [('DETENER',13),('ADELANTE',1)]:
            caps[name]=check('Capacidad '+name,201,'POST',f'/admin/modelos/{model}/capacidades',{'nombre':name,'codigo':code})['id_capacidad']
        bodies=[];commands=[]
        for n in (1,2):
            body={'nombre':f'Empresa HTTP {suffix} {n}','id_modelo':model,'identificador_unidad':f'EMP-{suffix}-{n}','descripcion':'Software sin hardware','microcontrolador':''}
            uid=check('Unidad nueva '+str(n),201,'POST','/admin/unidades',body)['id_vehiculo'];bodies.append((uid,body))
            record('Unidad nueva distinta de unidad 1',uid!=1)
            commands.append({name:check('Comando '+name,201,'POST',f'/admin/unidades/{uid}/comandos',{'id_capacidad':cap})['id_comando'] for name,cap in caps.items()})
        unit,other=bodies[0][0],bodies[1][0];report.update(id_modelo=model,id_unidad=unit,id_otra_unidad=other)
        doc={'id_vehiculo':unit,'nombre':'Empresa '+suffix,'descripcion':'Secuencia de fábrica de prueba',
             'pasos':[{'id_comando':commands[0]['ADELANTE'],'duracion_ms':100,'pausa_ms':0}]}
        demo=check('Crear demo de empresa',201,'POST','/mis-demos',doc)['id_demo'];report['id_demo_empresa']=demo
        detail=check('Recuperar demo y pasos',200,'GET',f'/mis-demos/{demo}')
        record('Tipo EMPRESA sin propietario privado',detail['demo']['tipo']=='EMPRESA' and detail['demo']['id_propietario'] is None)
        rev=detail['demo']['revision']
        edited={**doc,'revision':rev,'pasos':[{'id_comando':commands[0]['DETENER'],'duracion_ms':10,'pausa_ms':0},*doc['pasos']]}
        check('Editar orden de demo de empresa',200,'POST',f'/mis-demos/{demo}/guardar',edited)
        check('Revisión antigua rechazada',409,'POST',f'/mis-demos/{demo}/guardar',edited)
        check('Comando de otra unidad rechazado',409,'POST','/mis-demos',{**doc,'nombre':'Rechazada '+suffix,'pasos':[{'id_comando':commands[1]['ADELANTE'],'duracion_ms':100,'pausa_ms':0}]})
        stored=check('Verificar orden persistido',200,'GET',f'/mis-demos/{demo}')
        record('Orden y duración guardados',[(p['orden'],p['id_comando']) for p in stored['pasos']]==[(1,commands[0]['DETENER']),(2,commands[0]['ADELANTE'])])
        company=check('Empresa reserva unidad',201,'POST',f'/vehiculos/{unit}/control/reservar')['id_control'];leases.append((company,admin))
        before=check('Historial individual antes',200,'GET',f'/vehiculos/{unit}/historial')['historial']
        with channel(f'/ws/control/{company}',admin,'control_autorizado') as ws:
            check('Ejecutar demo como empresa',202,'POST',f'/vehiculos/{unit}/demos/{demo}/iniciar')
            finished(ws)
            state=check('Estado final consultado',200,'GET',f'/vehiculos/{unit}/estado')
            record('Estado final es DETENER',state['id_comando']==commands[0]['DETENER'])
            after=check('Historial individual después',200,'GET',f'/vehiculos/{unit}/historial')['historial']
            record('Pasos y cierre de demo no se convierten en movimientos individuales',before==after)
        check('Cerrar primera reserva empresa',200,'POST',f'/control/{company}/cerrar')
        long_doc={**doc,'revision':stored['demo']['revision'],'pasos':[{'id_comando':commands[0]['ADELANTE'],'duracion_ms':10000,'pausa_ms':0}]}
        updated=check('Preparar demo larga para prioridad STOP',200,'POST',f'/mis-demos/{demo}/guardar',long_doc)
        company=check('Empresa reserva para STOP',201,'POST',f'/vehiculos/{unit}/control/reservar')['id_control'];leases.append((company,admin))
        with channel(f'/ws/control/{company}',admin,'control_autorizado') as ws:
            check('Iniciar demo larga',202,'POST',f'/vehiculos/{unit}/demos/{demo}/iniciar')
            deadline=time.monotonic()+10
            while time.monotonic()<deadline:
                event=json.loads(ws.recv(timeout=max(.1,deadline-time.monotonic())))
                if event.get('tipo')=='demo_movimiento':break
            else:raise RuntimeError('No inició el paso de la demo larga.')
            check('DETENER interrumpe demo de empresa',201,'POST',f'/vehiculos/{unit}/movimientos',{'id_comando':commands[0]['DETENER']})
            until=time.monotonic()+10
            cancelled=False
            while time.monotonic()<until:
                event=json.loads(ws.recv(timeout=max(.1,until-time.monotonic())))
                if event.get('tipo')=='demo_cancelada':cancelled=True;break
            record('Cancelación de empresa recibida sin pasos posteriores',cancelled)
        check('Cerrar reserva tras STOP',200,'POST',f'/control/{company}/cerrar')
        check('Restaurar secuencia corta',200,'POST',f'/mis-demos/{demo}/guardar',{**edited,'revision':updated['revision']})
        owner_id,owner=buyer('A');_,outsider=buyer('B')
        check('Asignar unidad con demo de fábrica',200,'POST',f'/admin/unidades/{unit}/asignar',{'id_usuario':owner_id})
        record('Comprador conserva demo de empresa',any(d['id_demo']==demo and d['tipo']=='EMPRESA' for d in check('Listar demos del comprador',200,'GET',f'/mis-demos?id_vehiculo={unit}',token=owner)['demos']))
        current=check('Comprador consulta fábrica',200,'GET',f'/mis-demos/{demo}',token=owner)
        check('Comprador no edita fábrica',403,'POST',f'/mis-demos/{demo}/guardar',{**edited,'revision':current['demo']['revision']},owner)
        check('Comprador no impone tipo de empresa',422,'POST','/mis-demos',{**doc,'tipo':'EMPRESA'},owner)
        private=check('Comprador crea demo privada',201,'POST','/mis-demos',{**doc,'nombre':'Privada '+suffix},owner)['id_demo']
        detail=check('Tipo privado consultado',200,'GET',f'/mis-demos/{private}',token=owner)
        record('Demo privada ligada al comprador',detail['demo']['tipo']=='PRIVADA' and detail['demo']['id_propietario']==owner_id)
        check('Empresa no accede a demo privada vendida',404,'GET',f'/mis-demos/{private}')
        check('Empresa no edita unidad vendida',403,'POST',f'/mis-demos/{demo}/guardar',{**edited,'revision':current['demo']['revision']})
        check('Comprador ajeno no consulta fábrica',404,'GET',f'/mis-demos/{demo}',token=outsider)
        check('Comprador ajeno no consulta privada',404,'GET',f'/mis-demos/{private}',token=outsider)
        lease=check('Comprador reserva su unidad',201,'POST',f'/vehiculos/{unit}/control/reservar',token=owner)['id_control'];leases.append((lease,owner))
        with channel(f'/ws/control/{lease}',owner,'control_autorizado') as ws:
            check('Comprador ejecuta demo de empresa con reserva',202,'POST',f'/vehiculos/{unit}/demos/{demo}/iniciar',token=owner)
            finished(ws)
            check('Liberar control del comprador',200,'POST',f'/control/{lease}/cerrar',token=owner)
        check('Sin sesión no consulta demos',401,'GET',f'/mis-demos?id_vehiculo={unit}',token=None)
    finally:
        cleanup=[]
        for lease,token in leases:
            try:request('POST',f'/control/{lease}/cerrar',token=token)
            except Exception:pass
        for uid,name,email in buyers:
            try:
                code,_=request('POST',f'/admin/clientes/{uid}/actualizar',{'nombre':name,'correo':email,'activo':False},admin)
                cleanup.append({'comprador':uid,'inactivo':code==200})
            except Exception:cleanup.append({'comprador':uid,'inactivo':False})
        if other:
            try:
                code,_=request('POST',f'/admin/unidades/{other}/actualizar',{**bodies[1][1],'activo':False},admin)
                cleanup.append({'unidad_secundaria':other,'inactivo':code==200})
            except Exception:cleanup.append({'unidad_secundaria':other,'inactivo':False})
        for token in tokens:
            try:request('POST','/auth/logout',token=token)
            except Exception:pass
        report['limpieza']=cleanup
        report['nota']='Modelo privado/unidad asignada conservados con demos para auditoría; compradores de prueba inactivos. No se mueve unidad 1.'
        folder=Path.cwd()/'respaldos_rds';folder.mkdir(exist_ok=True)
        target=folder/('demos_empresa_'+suffix+'.json');target.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8');print('Informe guardado en',target)
    if any(not row['inactivo'] for row in cleanup):raise RuntimeError('Revisar limpieza de fixtures en el informe.')
    print('Comprobaciones de demos de empresa completadas.')


if __name__=='__main__':main()
