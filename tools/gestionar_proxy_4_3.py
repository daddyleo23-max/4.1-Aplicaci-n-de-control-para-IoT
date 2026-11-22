"""Preparar/activar/revertir el proxy4.3, conservando TLS y configuración real.
No muestra contenido de Caddyfile, JSON de Caddy, credenciales ni variables.
"""
import argparse
import copy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import subprocess
import urllib.request
from urllib.parse import urlsplit

OLD='127.0.0.1:8000'
NEW='127.0.0.1:8002'


def sha(data):return hashlib.sha256(data).hexdigest()
def json_sha(data):return sha(json.dumps(data,sort_keys=True,separators=(',',':')).encode())


def fetch_json(url):
    request=urllib.request.Request(url,headers={'Accept':'application/json','Cache-Control':'no-cache'})
    opener=urllib.request.build_opener(urllib.request.ProxyHandler({}))
    with opener.open(request,timeout=10) as response:
        if urlsplit(response.geturl()).scheme!=urlsplit(url).scheme or urlsplit(response.geturl()).netloc!=urlsplit(url).netloc:
            raise RuntimeError('La comprobación redirigió a otro origen o protocolo.')
        return json.load(response)


def api_check(base, version='4.3.0', database='vehiculo_iot_43', getter=fetch_json):
    info=getter(base.rstrip('/')+'/openapi.json')['info']['version']
    health=getter(base.rstrip('/')+'/health/db')
    if info!=version or health.get('conectado') is not True or health.get('base_datos')!=database:
        raise RuntimeError('La API no devuelve la versión y base de datos esperadas.')
    return {'version':info,'conectado':True,'base_datos':database}


def change_text(data):
    bom=data.startswith(b'\xef\xbb\xbf')
    text=data.decode('utf-8-sig')
    pattern=r'(?m)^([ \t]*reverse_proxy[ \t]+)127\.0\.0\.1:8000(?=[ \t]*(?:\{|#|\r?$))'
    result,n=re.subn(pattern,lambda m:m[1]+NEW,text)
    if n!=1:raise RuntimeError('No hay exactamente un reverse_proxy directo a8000. No se adivina ni modifica otra configuración.')
    return (b'\xef\xbb\xbf' if bom else b'')+result.encode('utf-8')


def change_native(config):
    result=copy.deepcopy(config);count=0
    def visit(value):
        nonlocal count
        if isinstance(value,dict):
            if value.get('handler')=='reverse_proxy':
                for upstream in value.get('upstreams',[]):
                    if upstream.get('dial')==OLD:upstream['dial']=NEW;count+=1
            for child in value.values():visit(child)
        elif isinstance(value,list):
            for child in value:visit(child)
    visit(result)
    if count!=1:raise RuntimeError('La configuración adaptada no tiene un único destino de proxy esperado.')
    return result


def admin_address(config):
    admin=config.get('admin',{})
    if admin.get('disabled'):raise RuntimeError('La administración de Caddy está deshabilitada; no se activa por este script.')
    listen=admin.get('listen','localhost:2019')
    parts=urlsplit('http://'+listen)
    if parts.hostname not in ('localhost','127.0.0.1','::1') or not parts.port or parts.username or parts.password or parts.path or parts.query or parts.fragment:
        raise RuntimeError('Se requiere administración HTTP de Caddy en loopback; no se usa un destino remoto.')
    return listen,'http://'+listen+'/config/'


class Caddy:
    def __init__(self,exe,workdir,folder):self.exe=str(exe);self.workdir=workdir;self.folder=folder
    def run(self,arguments,data=None,label='caddy'):
        operation=subprocess.run([self.exe,*arguments],input=data,capture_output=True,cwd=self.workdir,timeout=45,check=False)
        # Native config stays only in memory; logs may be private, never included in stdout.
        if operation.stderr:(self.folder/(label+'.privado.log')).write_bytes(operation.stderr)
        if operation.returncode:raise RuntimeError('Caddy no completó '+label+'. Revisa el registro privado; no compartas configuraciones o claves.')
        return operation.stdout
    def adapt(self,data):
        return json.loads(self.run(['adapt','--config','-','--adapter','caddyfile'],data,label='adaptar'))
    def validate(self,path):self.run(['validate','--config',str(path)],label='validar')
    def reload(self,path,address):self.run(['reload','--config',str(path),'--address',address],label='recargar')


def save(path,data):path.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')


def prepare(source,exe,folder,origin,getter=fetch_json,api_getter=fetch_json):
    original=source.read_bytes();candidate=change_text(original)
    folder.mkdir(parents=True,exist_ok=False)
    driver=Caddy(exe,source.parent,folder)
    native=driver.adapt(original);new_native=driver.adapt(candidate)
    expected=change_native(native)
    if new_native!=expected:raise RuntimeError('El cambio altera algo más que el destino8000→8002; no se permite.')
    listen,admin_url=admin_address(native)
    if getter(admin_url)!=native:raise RuntimeError('La configuración activa de Caddy difiere del archivo; no se sobrescribe el estado vivo.')
    local=api_check('http://127.0.0.1:8002',getter=api_getter)
    previous=api_check(origin,'1.0.0','vehiculo_iot',getter=api_getter)
    old_file=folder/'Caddyfile.anterior';old_file.write_bytes(original)
    candidate_file=folder/'Caddyfile.preparado';candidate_file.write_bytes(candidate)
    native_file=folder/'configuracion-nueva.privada.json';save(native_file,new_native)
    old_native_file=folder/'configuracion-anterior.privada.json';save(old_native_file,native)
    driver.validate(native_file)
    manifest={'version':1,'origen_publico':origin,'config_original':str(source),'caddy':str(exe),
              'respaldo':str(old_file),'candidato':str(candidate_file),'nativo_nuevo':str(native_file),
              'nativo_anterior':str(old_native_file),'sha_original':sha(original),'sha_candidato':sha(candidate),
              'sha_nativo_original':json_sha(native),'sha_nativo_candidato':json_sha(new_native),
              'admin_address':listen,'admin_url':admin_url,'api_local_verificada':local,
              'api_publica_anterior':previous,'destino_anterior':OLD,'destino_nuevo':NEW,'estado':'PREPARADO'}
    path=folder/'plan_proxy_4_3.json';save(path,manifest)
    print('Candidato validado: único cambio de proxy8000→8002.')
    print('TLS y demás directivas: conservados. Configuración activa todavía sin cambios.')
    print('Plan y respaldo privados:',path)
    return path


def checked_files(plan):
    if plan.get('version')!=1 or plan.get('destino_anterior')!=OLD or plan.get('destino_nuevo')!=NEW:
        raise RuntimeError('El plan no corresponde a este cambio de proxy.')
    source=Path(plan['config_original']);old=Path(plan['respaldo']).read_bytes();new=Path(plan['candidato']).read_bytes()
    old_native=json.loads(Path(plan['nativo_anterior']).read_text(encoding='utf-8'))
    new_native=json.loads(Path(plan['nativo_nuevo']).read_text(encoding='utf-8'))
    if sha(old)!=plan['sha_original'] or sha(new)!=plan['sha_candidato'] or json_sha(old_native)!=plan['sha_nativo_original'] or json_sha(new_native)!=plan['sha_nativo_candidato']:
        raise RuntimeError('Un archivo preparado cambió; no se aplica el plan.')
    if change_text(old)!=new or change_native(old_native)!=new_native:raise RuntimeError('El plan contiene modificaciones no autorizadas por este preparador.')
    listen,url=admin_address(old_native)
    if (listen,url)!=(plan['admin_address'],plan['admin_url']):raise RuntimeError('El destino de administración cambió; no se conecta.')
    return source,old,new,old_native,new_native


def write_existing(path,data):
    # Preserve the existing Windows file's ACL. The validated candidate is already
    # serving before persistence; a failure invokes rollback with the exact backup.
    with path.open('r+b') as f:
        f.seek(0);f.write(data);f.truncate();f.flush()
        import os
        os.fsync(f.fileno())


def activate(path,getter=fetch_json,api_getter=fetch_json):
    plan=json.loads(path.read_text(encoding='utf-8'))
    source,old,new,old_native,new_native=checked_files(plan)
    if source.read_bytes()!=old or getter(plan['admin_url'])!=old_native:
        raise RuntimeError('El archivo o la configuración activa cambiaron desde la preparación; no se recarga.')
    api_check('http://127.0.0.1:8002',getter=api_getter)
    driver=Caddy(plan['caddy'],source.parent,path.parent)
    driver.validate(Path(plan['nativo_nuevo']))
    attempted=False;persistence_started=False
    try:
        attempted=True
        driver.reload(Path(plan['nativo_nuevo']),plan['admin_address'])
        if getter(plan['admin_url'])!=new_native:raise RuntimeError('Caddy no confirma la configuración nueva.')
        result=api_check(plan['origen_publico'],getter=api_getter)
        if source.read_bytes()!=old:raise RuntimeError('El Caddyfile cambió durante la recarga; revisar antes de persistir.')
        persistence_started=True
        write_existing(source,new)
        plan.update(estado='ACTIVADO',api_publica=result)
        save(path,plan)
        scheme=urlsplit(plan['origen_publico']).scheme.upper()
        print('Proxy público activado: '+scheme+'→127.0.0.1:8002.')
        print('API '+scheme+' verificada:4.3.0 · vehiculo_iot_43 · conectadoTrue.')
        print('Caddyfile original actualizado; respaldo conservado. Mantén abierta la terminal del backend8002.')
    except Exception as error:
        plan['error_activacion']=str(error)
        if attempted:
            try:
                driver.reload(Path(plan['nativo_anterior']),plan['admin_address'])
                if getter(plan['admin_url'])!=old_native:raise RuntimeError('No se pudo verificar la configuración anterior.')
                contents=source.read_bytes()
                if contents!=old:
                    if contents!=new and not persistence_started:raise RuntimeError('Archivo cambiado por otro proceso: no se sobrescribe automáticamente.')
                    write_existing(source,old)
                plan['estado']='REVERTIDO'
                print('La comprobación falló; se restauraron el proxy y el archivo anteriores.')
            except Exception as rollback:
                plan['estado']='REVISAR_REVERSION';plan['error_reversion']=str(rollback)
                print('Reversión pendiente de revisión. Conserva el respaldo y ambos backends abiertos.')
        save(path,plan)
        raise RuntimeError('Activación no completada. Estado e informe: '+str(path)) from error
    print('Informe:',path)


def revert(path,getter=fetch_json):
    plan=json.loads(path.read_text(encoding='utf-8'));source,old,new,old_native,new_native=checked_files(plan)
    if source.read_bytes()!=new or getter(plan['admin_url'])!=new_native:
        raise RuntimeError('El despliegue cambió; no se fuerza una reversión sobre cambios desconocidos.')
    driver=Caddy(plan['caddy'],source.parent,path.parent)
    driver.validate(Path(plan['nativo_anterior']));driver.reload(Path(plan['nativo_anterior']),plan['admin_address'])
    if getter(plan['admin_url'])!=old_native:raise RuntimeError('No se confirmó la reversión; conservar ambos backends.')
    write_existing(source,old);plan['estado']='REVERTIDO';save(path,plan)
    print('Configuración anterior restaurada; el backend8000 debe seguir abierto. Informe:',path)


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('accion',choices=['preparar','activar','revertir'])
    p.add_argument('--plan');p.add_argument('--config',default='C:/caddy/Caddyfile.prod');p.add_argument('--caddy',default='C:/caddy/caddy.exe')
    p.add_argument('--origen-publico',default='https://34.194.45.28');args=p.parse_args()
    origin=args.origen_publico.rstrip('/');url=urlsplit(origin)
    if url.scheme!='https' or not url.hostname or url.username or url.password or url.path or url.query or url.fragment:
        raise SystemExit('Se requiere origen HTTPS sin rutas ni credenciales.')
    if args.plan:
        path=Path(args.plan).resolve(strict=True)
        prepared=json.loads(path.read_text(encoding='utf-8'))
        prepared_origin=urlsplit(prepared['origen_publico'])
        if prepared_origin.scheme!='https' or not prepared_origin.hostname or prepared_origin.username or prepared_origin.password or prepared_origin.path or prepared_origin.query or prepared_origin.fragment:
            raise SystemExit('El plan no corresponde a un origen HTTPS válido.')
        if Path(prepared['caddy']).resolve()!=Path(args.caddy).resolve(strict=True) or Path(prepared['config_original']).resolve()!=Path(args.config).resolve(strict=True):
            raise SystemExit('El plan pertenece a otro ejecutable o Caddyfile; no se ejecuta.')
    elif args.accion=='revertir':
        raise SystemExit('Indica --plan con el informe de activación.')
    else:
        source=Path(args.config).resolve(strict=True);exe=Path(args.caddy).resolve(strict=True)
        folder=Path.cwd()/'respaldos_rds'/('proxy_43_'+datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S-%f'))
        path=prepare(source,exe,folder,origin)
    if args.accion=='revertir':revert(path)
    elif args.accion=='activar':activate(path)

if __name__=='__main__':main()
