"""Capacidades: prueba HTTP en unidad NUEVA sin hardware."""
import getpass
import json
from pathlib import Path
import secrets
from probar_admin_http import BASE, request


def main():
    print('Destino:',BASE,'· modelo/unidad NUEVOS, sin hardware.')
    mail=input('Correo administrador de la aplicación: ').strip()
    password=getpass.getpass('Contraseña de aplicación (entrada oculta): ')
    code,login=request('POST','/auth/login',{'correo':mail,'password':password});password=None
    if code!=200 or login.get('usuario',{}).get('rol')!='ADMINISTRADOR':raise SystemExit('Login rechazado.')
    token=login['access_token'];suffix=secrets.token_hex(6);name='Capacidades HTTP '+suffix
    model=other=unit=buyer=None;results=[];cleanup=[]
    report={'destino':BASE,'resultados':results,'sin_hardware':True}
    def check(label,expected,method,path,body=None,auth=token):
        code,data=request(method,path,body,auth)
        print(f'{label}: HTTP {code} (esperado {expected})')
        results.append({'prueba':label,'http':code,'correcto':code==expected})
        if code!=expected:raise RuntimeError(str(data.get('detail',label)))
        return data
    def record(label,okay):
        results.append({'prueba':label,'correcto':bool(okay)});print(label+(': CORRECTO' if okay else ': INCORRECTO'))
        if not okay:raise RuntimeError(label)
    try:
        model=check('Modelo privado',201,'POST','/admin/modelos',{'nombre':name})['id_modelo']
        other=check('Modelo ajeno',201,'POST','/admin/modelos',{'nombre':name+' B'})['id_modelo']
        report.update(id_modelo=model,id_modelo_ajeno=other)
        def cap(m,n,c,active=True):return check('Capacidad '+n,201,'POST',f'/admin/modelos/{m}/capacidades',{'nombre':n,'codigo':c,'activo':active})['id_capacidad']
        stop=cap(model,'DETENER',13);forward=cap(model,'ADELANTE',1);off=cap(model,'LUCES',7,False);foreign=cap(other,'DETENER',13)
        caps=f'/admin/modelos/{model}/capacidades'
        check('Código duplicado rechazado',409,'POST',caps,{'nombre':'OTRA','codigo':1})
        check('Nombre inválido rechazado',422,'POST',caps,{'nombre':'nombre no valido','codigo':14})
        body={'nombre':name,'id_modelo':model,'identificador_unidad':'CAP-'+suffix,'descripcion':'Software sin hardware','microcontrolador':''}
        unit=check('Unidad nueva',201,'POST','/admin/unidades',body)['id_vehiculo'];report['id_unidad']=unit
        record('No es unidad 1',unit!=1)
        commands=f'/admin/unidades/{unit}/comandos'
        stop_id=check('Crear DETENER',201,'POST',commands,{'id_capacidad':stop})['id_comando']
        forward_id=check('Crear ADELANTE',201,'POST',commands,{'id_capacidad':forward})['id_comando']
        edit=commands+f'/{forward_id}/actualizar';capedit=caps+f'/{forward}/actualizar'
        check('Capacidad ajena rechazada',409,'POST',commands,{'id_capacidad':foreign})
        check('Capacidad inactiva rechazada',409,'POST',commands,{'id_capacidad':off})
        check('Ruta anterior no elude el modelo',409,'POST',f'/vehiculos/{unit}/comandos',{'nombre':'MUSICA','codigo':14})
        check('DETENER activo protegido',409,'POST',commands+f'/{stop_id}/actualizar',{'id_capacidad':stop,'activo':False})
        check('Identidad del comando protegida',409,'POST',edit,{'id_capacidad':stop})
        check('Código usado protegido',409,'POST',capedit,{'nombre':'ADELANTE','codigo':2})
        check('Capacidad usada no se desactiva',409,'POST',capedit,{'nombre':'ADELANTE','codigo':1,'activo':False})
        doc={'id_vehiculo':unit,'nombre':'Demo '+suffix,'pasos':[{'id_comando':forward_id,'duracion_ms':100,'pausa_ms':0}]}
        demo=check('Guardar demo compatible',201,'POST','/mis-demos',doc)['id_demo']
        check('Desactivar comando',200,'POST',edit,{'id_capacidad':forward,'activo':False})
        check('Desactivar capacidad',200,'POST',capedit,{'nombre':'ADELANTE','codigo':1,'activo':False})
        check('Movimiento deshabilitado rechazado',403,'POST',f'/vehiculos/{unit}/movimientos',{'id_comando':forward_id})
        check('Demo incompatible rechazada antes de iniciar',409,'POST',f'/vehiculos/{unit}/demos/{demo}/iniciar')
        check('Editor rechaza función inactiva',409,'POST','/mis-demos',{**doc,'nombre':'Rechazada '+suffix})
        check('Activación sin capacidad rechazada',409,'POST',edit,{'id_capacidad':forward})
        check('Ruta anterior respeta capacidad inactiva',409,'POST',f'/comandos/{forward_id}/actualizar',{'nombre':'ADELANTE','codigo':1,'activo':True})
        check('Reactivar capacidad',200,'POST',capedit,{'nombre':'ADELANTE','codigo':1})
        check('Reactivar comando',200,'POST',edit,{'id_capacidad':forward,'descripcion':'Verificado'})
        check('Movimiento compatible aceptado',201,'POST',f'/vehiculos/{unit}/movimientos',{'id_comando':forward_id})
        check('DETENER aceptado',201,'POST',f'/vehiculos/{unit}/movimientos',{'id_comando':stop_id})
        check('Demo compatible inicia',202,'POST',f'/vehiculos/{unit}/demos/{demo}/iniciar')
        # No hay pausas de temporización: el resto de consultas permite completar la demo breve.
        buyer_mail='cap-'+suffix+'@example.invalid';secret=secrets.token_urlsafe(24)
        buyer=check('Comprador de prueba',201,'POST','/admin/clientes',{'nombre':name,'correo':buyer_mail,'password':secret})['id_usuario']
        buyer_token=check('Login comprador',200,'POST','/auth/login',{'correo':buyer_mail,'password':secret},None)['access_token']
        check('Sin sesión rechazado',401,'GET',caps,auth=None)
        check('Comprador no edita capacidades',403,'POST',caps,{'nombre':'ATRAS','codigo':2},buyer_token)
        check('Comprador no administra comandos',403,'GET',commands,auth=buyer_token)
        request('POST','/auth/logout',token=buyer_token)
        rows=check('Catálogo final',200,'GET',commands)['comandos']
        record('IDs conservados', {r['id_comando'] for r in rows}=={stop_id,forward_id})
        audit=check('Auditoría',200,'GET','/admin/auditoria?limite=100')['eventos']
        record('Cambios auditados',{'GUARDAR_CAPACIDAD','GUARDAR_COMANDO_UNIDAD'}<={r['accion'] for r in audit})
    finally:
        operations=[]
        if unit:operations.append((f'/admin/unidades/{unit}/actualizar',{**body,'activo':False}))
        if model:operations.append((f'/admin/modelos/{model}/actualizar',{'nombre':name,'activo':False}))
        if other:operations.append((f'/admin/modelos/{other}/actualizar',{'nombre':name+' B','activo':False}))
        if buyer:operations.append((f'/admin/clientes/{buyer}/actualizar',{'nombre':name,'correo':buyer_mail,'activo':False}))
        for path,body in operations:
            try:code,_=request('POST',path,body,token);cleanup.append({'ruta':path,'correcto':code==200})
            except Exception:cleanup.append({'ruta':path,'correcto':False})
        try:request('POST','/auth/logout',token=token)
        except Exception:pass
        report['limpieza']=cleanup
        folder=Path.cwd()/'respaldos_rds';folder.mkdir(exist_ok=True)
        target=folder/('capacidades_http_'+suffix+'.json');target.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
        print('Informe guardado en',target)
    if any(not r['correcto'] for r in cleanup):raise RuntimeError('Revisar limpieza de registros en el informe.')
    print('Comprobaciones HTTP de capacidades completadas. Registros privados e inactivos.')


if __name__=='__main__':main()
