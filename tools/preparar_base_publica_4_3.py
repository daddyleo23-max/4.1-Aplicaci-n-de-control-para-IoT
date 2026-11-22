"""Restaurar la copia 4.3 aprobada en vehiculo_iot_43, sin tocar vehiculo_iot.
Requiere backend de pruebas8001 detenido; no elimina ni sobrescribe esquemas.
"""
import argparse
from datetime import datetime, timezone
import getpass
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import socket
import subprocess
import sys

from migrar_copia_rds import quote, TABLES_011

TARGET = 'vehiculo_iot_43'
TABLES = TABLES_011 | {'permisos_soporte','sesiones_control','capacidades_modelo'}
VERSIONS = ['001_base_administracion', '002_sesiones_auditoria', '003_gestion_comercial', '004_asignaciones', '005_acceso_recursos', '006_edicion_auditoria', '007_editor_demos', '008_corregir_orden_pasos', '009_inventario_unidades', '010_catalogo_publico', '011_reservas_invitados', '012_api_invitados', '013_soporte_diagnostico', '014_reservas_comprador', '015_api_control_comprador', '016_soporte_operativo', '017_listas_soporte_web', '018_capacidades_modelo', '019_control_empresa', '020_catalogo_resumen']


def find_client(name, supplied):
    if supplied:
        result=Path(supplied).resolve(strict=True)
        if not result.is_file():raise RuntimeError('El cliente indicado no es un archivo.')
        return str(result)
    candidate=shutil.which(name)
    if candidate:return candidate
    options=sorted(Path('C:/mysql-tools').rglob(name+'.exe'))
    if not options:raise RuntimeError('No se encontró '+name+'. Usa --'+name+' con su ruta.')
    return str(options[0])


def digest(value):
    return hashlib.sha256(json.dumps(value,default=str,ensure_ascii=False,sort_keys=True).encode()).hexdigest()


def profile(cursor, schema):
    cursor.execute('SELECT TABLE_NAME FROM information_schema.TABLES WHERE TABLE_SCHEMA=%s AND TABLE_TYPE=%s ORDER BY TABLE_NAME',(schema,'BASE TABLE'))
    names=[r['TABLE_NAME'] for r in cursor.fetchall()]
    if set(names)!=TABLES:raise RuntimeError('El esquema '+schema+' no tiene exactamente las 19 tablas previstas.')
    cursor.execute('SELECT COUNT(*) AS n FROM information_schema.EVENTS WHERE EVENT_SCHEMA=%s',(schema,))
    if cursor.fetchone()['n']:raise RuntimeError('Hay eventos programados; requieren revisión antes de clonar.')
    cursor.execute('SELECT COUNT(*) AS n FROM information_schema.VIEWS WHERE TABLE_SCHEMA=%s',(schema,))
    if cursor.fetchone()['n']:raise RuntimeError('Hay vistas no previstas; requieren revisión antes de clonar.')
    result={'tablas':{}}
    for table in names:
        cursor.execute("SELECT COLUMN_NAME FROM information_schema.KEY_COLUMN_USAGE WHERE TABLE_SCHEMA=%s AND TABLE_NAME=%s AND CONSTRAINT_NAME='PRIMARY' ORDER BY ORDINAL_POSITION",(schema,table))
        order=[r['COLUMN_NAME'] for r in cursor.fetchall()]
        if not order:raise RuntimeError('Tabla sin PK; requiere revisión.')
        cursor.execute('SELECT * FROM '+quote(schema)+'.'+quote(table)+' ORDER BY '+','.join(map(quote,order)))
        sha=hashlib.sha256();n=0
        for row in cursor:
            sha.update(json.dumps(row,default=str,ensure_ascii=False,sort_keys=True).encode()+b'\n');n+=1
        cursor.execute('SELECT COLUMN_NAME,COLUMN_TYPE,IS_NULLABLE,COLUMN_DEFAULT,EXTRA,GENERATION_EXPRESSION,CHARACTER_SET_NAME,COLLATION_NAME FROM information_schema.COLUMNS WHERE TABLE_SCHEMA=%s AND TABLE_NAME=%s ORDER BY ORDINAL_POSITION',(schema,table))
        columns=cursor.fetchall()
        cursor.execute('SELECT INDEX_NAME,NON_UNIQUE,SEQ_IN_INDEX,COLUMN_NAME,SUB_PART,INDEX_TYPE FROM information_schema.STATISTICS WHERE TABLE_SCHEMA=%s AND TABLE_NAME=%s ORDER BY INDEX_NAME,SEQ_IN_INDEX',(schema,table))
        indices=cursor.fetchall()
        cursor.execute('SELECT AUTO_INCREMENT FROM information_schema.TABLES WHERE TABLE_SCHEMA=%s AND TABLE_NAME=%s',(schema,table))
        result['tablas'][table]={'filas':n,'datos_sha256':sha.hexdigest(),'columnas_sha256':digest(columns),
                                'indices_sha256':digest(indices),'auto_increment':cursor.fetchone()['AUTO_INCREMENT']}
    cursor.execute('SELECT ROUTINE_NAME,ROUTINE_TYPE,ROUTINE_DEFINITION,SECURITY_TYPE,DEFINER,SQL_MODE FROM information_schema.ROUTINES WHERE ROUTINE_SCHEMA=%s ORDER BY ROUTINE_NAME',(schema,))
    routines=cursor.fetchall()
    if not routines or any(r['ROUTINE_DEFINITION'] is None for r in routines):raise RuntimeError('No se pueden verificar todas las rutinas.')
    for row in routines:
        if re.search(r'`?'+re.escape(schema)+r'`?\s*\.',row['ROUTINE_DEFINITION']):
            raise RuntimeError('Una rutina referencia explícitamente su esquema; revisar antes de clonar.')
    result['rutinas']={'cantidad':len(routines),'sha256':digest(routines)}
    cursor.execute('SELECT SPECIFIC_NAME,ORDINAL_POSITION,PARAMETER_MODE,PARAMETER_NAME,DTD_IDENTIFIER FROM information_schema.PARAMETERS WHERE SPECIFIC_SCHEMA=%s ORDER BY SPECIFIC_NAME,ORDINAL_POSITION',(schema,))
    result['parametros_sha256']=digest(cursor.fetchall())
    cursor.execute('SELECT TRIGGER_NAME,EVENT_MANIPULATION,EVENT_OBJECT_TABLE,ACTION_TIMING,ACTION_STATEMENT,DEFINER,SQL_MODE FROM information_schema.TRIGGERS WHERE TRIGGER_SCHEMA=%s ORDER BY TRIGGER_NAME',(schema,))
    triggers=cursor.fetchall();result['triggers']={'cantidad':len(triggers),'sha256':digest(triggers)}
    cursor.execute('SELECT k.TABLE_NAME,k.CONSTRAINT_NAME,k.COLUMN_NAME,k.REFERENCED_TABLE_SCHEMA,k.REFERENCED_TABLE_NAME,k.REFERENCED_COLUMN_NAME,r.UPDATE_RULE,r.DELETE_RULE FROM information_schema.KEY_COLUMN_USAGE k JOIN information_schema.REFERENTIAL_CONSTRAINTS r ON r.CONSTRAINT_SCHEMA=k.CONSTRAINT_SCHEMA AND r.CONSTRAINT_NAME=k.CONSTRAINT_NAME AND r.TABLE_NAME=k.TABLE_NAME WHERE k.TABLE_SCHEMA=%s ORDER BY k.TABLE_NAME,k.CONSTRAINT_NAME,k.ORDINAL_POSITION',(schema,))
    keys=cursor.fetchall()
    for key in keys:
        if key['REFERENCED_TABLE_SCHEMA']!=schema:raise RuntimeError('Existe una FK a otro esquema; requiere revisión.')
        key['REFERENCED_TABLE_SCHEMA']='ESQUEMA_PROPIO'
    result['fk_sha256']=digest(keys)
    cursor.execute('SELECT t.TABLE_NAME,t.CONSTRAINT_NAME,t.CONSTRAINT_TYPE,t.ENFORCED,c.CHECK_CLAUSE FROM information_schema.TABLE_CONSTRAINTS t LEFT JOIN information_schema.CHECK_CONSTRAINTS c ON c.CONSTRAINT_SCHEMA=t.CONSTRAINT_SCHEMA AND c.CONSTRAINT_NAME=t.CONSTRAINT_NAME WHERE t.TABLE_SCHEMA=%s ORDER BY t.TABLE_NAME,t.CONSTRAINT_NAME',(schema,))
    result['restricciones_sha256']=digest(cursor.fetchall())
    return result


def run_client(arguments, password, **kwargs):
    env=os.environ.copy();env['MYSQL_PWD']=password
    try:return subprocess.run(arguments,env=env,check=False,stderr=subprocess.PIPE,**kwargs)
    finally:env.pop('MYSQL_PWD',None)


def clone(connection, source, app_user, password, mysql, mysqldump, folder):
    report={'origen':source,'destino':TARGET,'destino_creado':False,'verificado':False}
    stamp=datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S-%f')
    manifest=folder/('publicacion_base_'+stamp+'.json')
    try:
        print('Verificando versiones, reservas y estructura del origen...',flush=True)
        with connection.cursor() as c:
            c.execute("SET time_zone='+00:00'")
            c.execute('SELECT SCHEMA_NAME FROM information_schema.SCHEMATA WHERE SCHEMA_NAME=%s',(TARGET,))
            if c.fetchone():raise RuntimeError('vehiculo_iot_43 ya existe. No se sobrescribió; revisar el informe anterior.')
            c.execute('SELECT version FROM '+quote(source)+'.migraciones_iot ORDER BY version')
            if [r['version'] for r in c.fetchall()]!=VERSIONS:raise RuntimeError('Se requieren migraciones001–020 completas en origen.')
            c.execute('SELECT COUNT(*) AS n FROM '+quote(source)+'.reservas_control')
            if c.fetchone()['n']:raise RuntimeError('La copia conserva reservas; deben cerrarse antes del respaldo.')
            c.execute("SELECT COUNT(*) AS n FROM mysql.user WHERE User=%s AND Host='%%'",(app_user,))
            if c.fetchone()['n']!=1 or app_user.lower() in ('root','admin'):
                raise RuntimeError('No se identificó la cuenta limitada del backend; no se crearon usuarios ni se otorgaron permisos.')
            report['antes']=profile(c,source)
            c.execute('SHOW CREATE DATABASE '+quote(source));definition=c.fetchone()['Create Database']
            # Options only; do not copy a USE or create the source schema.
            options=definition[definition.index('/*!'):] if '/*!' in definition else ''
        backup=folder/(source+'_prepublicacion_'+stamp+'.sql')
        connection_args=['--host',connection.host,'--port',str(connection.port),'--user',connection.user.decode() if isinstance(connection.user,bytes) else connection.user]
        print('Generando respaldo privado de la copia aprobada...',flush=True)
        with backup.open('xb') as output:
            operation=run_client([mysqldump,*connection_args,'--single-transaction','--quick','--routines','--triggers','--events','--hex-blob','--no-tablespaces','--set-gtid-purged=OFF','--column-statistics=0','--default-character-set=utf8mb4',source],password,stdout=output)
        report['respaldo']=backup.name
        if operation.returncode or not backup.stat().st_size:
            raise RuntimeError('Falló el respaldo; no se creó el destino. Conservar el archivo para revisión privada.')
        sha=hashlib.sha256()
        with backup.open('rb') as f:
            for chunk in iter(lambda:f.read(1024*1024),b''):sha.update(chunk)
        report['respaldo_sha256']=sha.hexdigest()
        with connection.cursor() as c:
            if profile(c,source)!=report['antes']:raise RuntimeError('El origen cambió durante el respaldo. Detener sus escritores antes de continuar.')
            c.execute('CREATE DATABASE '+quote(TARGET)+' '+options);report['destino_creado']=True
        print('Restaurando en el esquema nuevo '+TARGET+'...',flush=True)
        with backup.open('rb') as f:
            operation=run_client([mysql,*connection_args,'--database',TARGET,'--default-character-set=utf8mb4','--binary-mode'],password,stdin=f,stdout=subprocess.DEVNULL)
        if operation.returncode:raise RuntimeError('Restauración incompleta. El destino se conserva para diagnóstico; no repetir ni borrarlo.')
        with connection.cursor() as c:
            print('Comparando todos los datos y objetos restaurados...',flush=True)
            report['origen_despues']=profile(c,source);report['copia']=profile(c,TARGET)
            if report['antes']!=report['origen_despues'] or report['antes']!=report['copia']:
                raise RuntimeError('La comparación no coincide. No se habilitó la cuenta API sobre el destino.')
            c.execute('GRANT EXECUTE ON '+quote(TARGET)+'.* TO %s@%s',(app_user,'%'))
            report['cuenta_backend']=app_user;report['permiso']='EXECUTE';report['verificado']=True
        print('Base pública preparada:',TARGET)
        print('Datos, columnas, índices, FK, rutinas, parámetros y triggers: COINCIDEN')
        print('Origen conservado sin cambios: True')
        print('Cuenta limitada del backend habilitada sólo con EXECUTE sobre el nuevo esquema.')
        print('Caddy y el servicio público anterior NO se modificaron.')
    except Exception as error:
        report['error']=str(error);raise
    finally:
        manifest.write_text(json.dumps(report,default=str,ensure_ascii=False,indent=2),encoding='utf-8')
        print('Informe guardado en',manifest)
    return report


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--origen',required=True)
    p.add_argument('--mysql');p.add_argument('--mysqldump');args=p.parse_args()
    if not re.fullmatch(r'iot_prueba_\d{8}_\d{6}_\d{6}',args.origen):raise SystemExit('Indica la copia de pruebas aprobada, no el esquema original.')
    try:
        with socket.create_connection(('127.0.0.1',8001),timeout=1):pass
    except OSError:pass
    else:raise SystemExit('Detén SOLO el backend de pruebas8001 con Ctrl+C antes de respaldar. No detengas8000 ni Caddy.')
    mysql=find_client('mysql',args.mysql);dump=find_client('mysqldump',args.mysqldump)
    sys.path.insert(0,str(Path.cwd()))
    from app.config import DB_HOST,DB_PORT,DB_USER,DB_NAME
    if TARGET in (args.origen,DB_NAME):raise SystemExit('El destino debe ser un esquema nuevo distinto del origen y del esquema original.')
    import pymysql
    user=input('Usuario administrador de RDS: ').strip();password=getpass.getpass('Contraseña de RDS (entrada oculta): ')
    db=pymysql.connect(host=DB_HOST,port=DB_PORT,user=user,password=password,database=args.origen,charset='utf8mb4',autocommit=True,cursorclass=pymysql.cursors.DictCursor,connect_timeout=5)
    folder=Path.cwd()/'respaldos_rds';folder.mkdir(exist_ok=True)
    try:clone(db,args.origen,DB_USER,password,mysql,dump,folder)
    finally:db.close();password=None

if __name__=='__main__':main()
