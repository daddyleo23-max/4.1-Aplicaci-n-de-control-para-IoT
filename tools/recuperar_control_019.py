"""Recupera exclusivamente el estado parcial conocido de 019 en una copia aislada.
Sin --aplicar sólo diagnostica. Requiere backend detenido y respaldo pre019.
No desactiva FOREIGN_KEY_CHECKS ni toca el esquema original.
"""
import argparse
from datetime import datetime, timezone
import getpass
import hashlib
import json
from pathlib import Path
import re
import sys

from migrar_copia_rds import TABLES_011, quote, snapshot

VERSION = '019_control_empresa'
PREVIOUS = ['001_base_administracion', '002_sesiones_auditoria', '003_gestion_comercial', '004_asignaciones', '005_acceso_recursos', '006_edicion_auditoria', '007_editor_demos', '008_corregir_orden_pasos', '009_inventario_unidades', '010_catalogo_publico', '011_reservas_invitados', '012_api_invitados', '013_soporte_diagnostico', '014_reservas_comprador', '015_api_control_comprador', '016_soporte_operativo', '017_listas_soporte_web', '018_capacidades_modelo']
EXPECTED_TABLES = TABLES_011 | {'permisos_soporte', 'sesiones_control', 'capacidades_modelo'}
ROOT = Path(__file__).resolve().parent


def normalize(value):
    lines = [line.split('--', 1)[0] for line in (value or '').splitlines()]
    return re.sub(r'\s+', ' ', '\n'.join(lines)).strip()


def procedures(text):
    result = {}
    for statement in text.split('$$'):
        match = re.search(r'CREATE PROCEDURE\s+(sp_control_\w+)\s*\((.*?)\)\s*SQL SECURITY DEFINER\s*(BEGIN.*END)\s*$', statement, re.S)
        if match:
            result[match[1]] = {'statement':statement[match.start():].strip(), 'body':match[3],
                              'parameters':[tuple(p.strip().lower().split()) for p in match[2].split(',') if p.strip()]}
    return result


def load_sources():
    original = ROOT / 'fuentes_recuperacion_019' / '019_original.sql'
    fixed = ROOT / '019_control_empresa.up.sql'
    if not fixed.exists():fixed = ROOT.parent / 'sql/migrations/019_control_empresa.up.sql'
    sources = []
    for name in ('015_api_control_comprador.up.sql','016_soporte_operativo.up.sql'):
        path = ROOT / 'fuentes_recuperacion_019' / name
        if not path.exists():path = ROOT.parent / 'sql/migrations' / name
        sources.append(path.read_text(encoding='utf-8'))
    old = {}
    for text in sources:old.update(procedures(text))
    expected = procedures(fixed.read_text(encoding='utf-8'))
    if len(expected) != 7 or not set(expected) <= set(old):
        raise RuntimeError('Fuentes de rutinas incompletas; no se conecta ni modifica RDS.')
    return original, old, expected


def all_data(cursor, schema, tables):
    """Hash por tabla, nunca datos ni tokens en el informe. Sólo excluye el backfill previsto."""
    result = {}
    for table in sorted(tables - {'migraciones_iot'}):
        cursor.execute('SELECT COLUMN_NAME FROM information_schema.COLUMNS WHERE TABLE_SCHEMA=%s AND TABLE_NAME=%s ORDER BY ORDINAL_POSITION',(schema,table))
        columns = [r['COLUMN_NAME'] for r in cursor.fetchall() if not (table=='sesiones_control' and r['COLUMN_NAME']=='id_vehiculo')]
        cursor.execute("SELECT COLUMN_NAME FROM information_schema.KEY_COLUMN_USAGE WHERE TABLE_SCHEMA=%s AND TABLE_NAME=%s AND CONSTRAINT_NAME='PRIMARY' ORDER BY ORDINAL_POSITION",(schema,table))
        order = [r['COLUMN_NAME'] for r in cursor.fetchall()]
        if not order:raise RuntimeError('Tabla sin clave primaria; revisar antes de comparar.')
        cursor.execute('SELECT '+','.join(map(quote,columns))+' FROM '+quote(table)+' ORDER BY '+','.join(map(quote,order)))
        digest=hashlib.sha256();count=0
        for row in cursor:
            digest.update(json.dumps(row,default=str,sort_keys=True,ensure_ascii=False).encode()+b'\n');count+=1
        result[table]={'filas':count,'sha256':digest.hexdigest()}
    return result


def inspect(cursor, schema, old, expected):
    cursor.execute("SHOW FULL TABLES WHERE Table_type='BASE TABLE'")
    if {list(r.values())[0] for r in cursor.fetchall()} != EXPECTED_TABLES:
        raise RuntimeError('Tablas distintas del estado 018/019 esperado. No se recupera automáticamente.')
    cursor.execute('SELECT version FROM migraciones_iot ORDER BY version')
    versions=[r['version'] for r in cursor.fetchall()]
    if versions not in (PREVIOUS, PREVIOUS+[VERSION]):
        raise RuntimeError('Se requieren exactamente migraciones 001–018 o 001–019; no repetir migraciones.')
    registered=VERSION in versions
    cursor.execute('SELECT COUNT(*) AS n FROM reservas_control')
    if cursor.fetchone()['n']:raise RuntimeError('Hay reservas. Mantén backend detenido y revisa cierres antes de recuperar.')
    cursor.execute("SELECT COLUMN_NAME,COLUMN_TYPE,IS_NULLABLE FROM information_schema.COLUMNS WHERE TABLE_SCHEMA=%s AND TABLE_NAME='sesiones_control' AND COLUMN_NAME IN ('id_vehiculo','id_asignacion')",(schema,))
    columns={r['COLUMN_NAME']:r for r in cursor.fetchall()}
    if set(columns)!={'id_vehiculo','id_asignacion'} or any(re.sub(r'\(\d+\)','',columns[k]['COLUMN_TYPE'].lower()) != typ for k,typ in [('id_vehiculo','int'),('id_asignacion','bigint')]) or columns['id_asignacion']['IS_NULLABLE']!='YES':
        raise RuntimeError('Columnas distintas del estado parcial conocido. No se modificaron.')
    cursor.execute("SELECT k.CONSTRAINT_NAME,k.COLUMN_NAME,k.REFERENCED_TABLE_SCHEMA,k.REFERENCED_TABLE_NAME,k.REFERENCED_COLUMN_NAME,r.DELETE_RULE,r.UPDATE_RULE FROM information_schema.KEY_COLUMN_USAGE k JOIN information_schema.REFERENTIAL_CONSTRAINTS r ON r.CONSTRAINT_SCHEMA=k.CONSTRAINT_SCHEMA AND r.CONSTRAINT_NAME=k.CONSTRAINT_NAME AND r.TABLE_NAME=k.TABLE_NAME WHERE k.TABLE_SCHEMA=%s AND k.TABLE_NAME='sesiones_control' AND (k.COLUMN_NAME='id_vehiculo' OR k.CONSTRAINT_NAME='fk_control_unidad')",(schema,))
    foreign=cursor.fetchall()
    if foreign:
        if len(foreign)!=1:raise RuntimeError('Hay restricciones adicionales sobre la columna; requiere revisión.')
        fk=foreign[0]
        if (fk['CONSTRAINT_NAME'],fk['COLUMN_NAME'],fk['REFERENCED_TABLE_SCHEMA'],fk['REFERENCED_TABLE_NAME'],fk['REFERENCED_COLUMN_NAME']) != ('fk_control_unidad','id_vehiculo',schema,'vehiculos','id_vehiculo') or fk['DELETE_RULE'] not in ('RESTRICT','NO ACTION') or fk['UPDATE_RULE'] not in ('RESTRICT','NO ACTION'):
            raise RuntimeError('La FK existente no coincide; no se elimina ninguna restricción.')
    cursor.execute('SELECT COUNT(*) AS n FROM sesiones_control c LEFT JOIN vehiculos v ON v.id_vehiculo=c.id_vehiculo WHERE c.id_vehiculo IS NOT NULL AND v.id_vehiculo IS NULL')
    if cursor.fetchone()['n']:raise RuntimeError('Referencias de unidad huérfanas; detener recuperación.')
    if not registered:
        cursor.execute('SELECT COUNT(*) AS n FROM sesiones_control c LEFT JOIN asignaciones a ON a.id_asignacion=c.id_asignacion WHERE a.id_asignacion IS NULL OR (c.id_vehiculo IS NOT NULL AND c.id_vehiculo<>a.id_vehiculo)')
        if cursor.fetchone()['n']:raise RuntimeError('Hay reservas históricas no reconstruibles por asignación; requiere revisión.')
    cursor.execute('SELECT COUNT(*) AS n FROM sesiones_control WHERE id_vehiculo IS NULL')
    nulls=cursor.fetchone()['n']
    cursor.execute("SELECT ROUTINE_NAME,ROUTINE_DEFINITION,SECURITY_TYPE FROM information_schema.ROUTINES WHERE ROUTINE_SCHEMA=%s AND ROUTINE_NAME LIKE 'sp_control_%%'",(schema,))
    actual={r['ROUTINE_NAME']:r for r in cursor.fetchall()}
    if set(actual)-set(old):raise RuntimeError('Hay rutinas de control desconocidas; revisar antes de sustituir.')
    for name in set(old)-set(expected):
        row=actual.get(name)
        if not row or row['SECURITY_TYPE']!='DEFINER' or normalize(row['ROUTINE_DEFINITION'])!=normalize(old[name]['body']):
            raise RuntimeError('La rutina no modificada '+name+' no coincide con la fuente previa.')
    pending=[]
    for name, target in expected.items():
        row=actual.get(name)
        if row is None:
            pending.append(name);continue
        if row['SECURITY_TYPE']!='DEFINER' or normalize(row['ROUTINE_DEFINITION']) not in {normalize(old[name]['body']), normalize(target['body'])}:
            raise RuntimeError('La rutina '+name+' difiere de ambas fuentes verificadas; no se reemplaza.')
        cursor.execute('SELECT PARAMETER_MODE,PARAMETER_NAME,DTD_IDENTIFIER FROM information_schema.PARAMETERS WHERE SPECIFIC_SCHEMA=%s AND SPECIFIC_NAME=%s AND ORDINAL_POSITION>0 ORDER BY ORDINAL_POSITION',(schema,name))
        parameters=[(r['PARAMETER_MODE'].lower(),r['PARAMETER_NAME'].lower(),re.sub(r'\b(tinyint|smallint|mediumint|int|bigint)\(\d+\)',r'\1',r['DTD_IDENTIFIER'].lower())) for r in cursor.fetchall()]
        if parameters!=target['parameters']:raise RuntimeError('Parámetros inesperados en '+name)
        if normalize(row['ROUTINE_DEFINITION'])!=normalize(target['body']):pending.append(name)
    if registered and (nulls or not foreign or columns['id_vehiculo']['IS_NULLABLE']!='NO' or pending):
        raise RuntimeError('019 registrada pero incompleta. Requiere revisión específica.')
    return {'version_registrada':registered,'id_vehiculo_nullable':columns['id_vehiculo']['IS_NULLABLE']=='YES',
            'fk_control_unidad_presente':bool(foreign),'filas_sin_unidad':nulls,'rutinas_pendientes':pending}


def recover(cursor, schema, old, expected, report):
    state=inspect(cursor,schema,old,expected)
    report['estado_previo']=dict(state)
    print(json.dumps(state,ensure_ascii=False,indent=2))
    before=all_data(cursor,schema,EXPECTED_TABLES);report['datos_antes']=before
    if state['version_registrada']:
        print('019 ya está completa; no se aplicaron cambios.');return
    if state['filas_sin_unidad']:
        cursor.execute('UPDATE sesiones_control c JOIN asignaciones a ON a.id_asignacion=c.id_asignacion SET c.id_vehiculo=a.id_vehiculo WHERE c.id_vehiculo IS NULL')
    if state['id_vehiculo_nullable']:
        # MySQL requires dropping the referencing constraint BEFORE changing nullability.
        if state['fk_control_unidad_presente']:
            cursor.execute('ALTER TABLE sesiones_control DROP FOREIGN KEY fk_control_unidad')
            report['acciones'].append('FK conocida retirada antes del cambio de nulabilidad')
        cursor.execute('ALTER TABLE sesiones_control MODIFY id_vehiculo INT NOT NULL')
        report['acciones'].append('id_vehiculo completada como NOT NULL')
        state['fk_control_unidad_presente']=False
    if not state['fk_control_unidad_presente']:
        cursor.execute('ALTER TABLE sesiones_control ADD CONSTRAINT fk_control_unidad FOREIGN KEY(id_vehiculo) REFERENCES vehiculos(id_vehiculo) ON DELETE RESTRICT')
        report['acciones'].append('FK de unidad recreada y validada')
    for name in state['rutinas_pendientes']:
        cursor.execute('DROP PROCEDURE IF EXISTS '+quote(name))
        cursor.execute(expected[name]['statement'])
        report['acciones'].append('Rutina verificada: '+name)
    final=inspect(cursor,schema,old,expected)
    if final['id_vehiculo_nullable'] or not final['fk_control_unidad_presente'] or final['filas_sin_unidad'] or final['rutinas_pendientes']:
        raise RuntimeError('Persisten pendientes; 019 no se registra.')
    after=all_data(cursor,schema,EXPECTED_TABLES);report['datos_despues']=after
    if before!=after:raise RuntimeError('Cambios de datos inesperados; 019 no se registra. Revisar informe.')
    cursor.execute('INSERT INTO migraciones_iot(version) VALUES(%s)',(VERSION,))
    report['estado_final']=inspect(cursor,schema,old,expected)
    report['datos_conservados']=True
    print('Recuperación completada: FK, columna y siete rutinas verificadas; 019 registrada.')
    print('Datos de todas las tablas conservados: True')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--copia',required=True);parser.add_argument('--informe',required=True)
    group=parser.add_mutually_exclusive_group()
    group.add_argument('--aplicar',action='store_true');group.add_argument('--diagnostico',action='store_true')
    args=parser.parse_args()
    if not re.fullmatch(r'iot_prueba_\d{8}_\d{6}_\d{6}',args.copia):raise SystemExit('Se requiere copia aislada.')
    original,old,expected=load_sources()
    prior=json.loads(Path(args.informe).read_text(encoding='utf-8-sig'))
    if (prior.get('copia')!=args.copia or prior.get('archivo_sql')!='019_control_empresa.up.sql'
        or prior.get('sql_sha256')!=hashlib.sha256(original.read_bytes()).hexdigest()
        or prior.get('mysql_exit_code')!=1 or prior.get('datos_y_procedimientos_conservados') is not True):
        raise SystemExit('El informe no corresponde al fallo conocido de 019; no se conecta a RDS.')
    sys.path.insert(0,str(Path.cwd()))
    from app.config import DB_HOST,DB_PORT,DB_NAME
    import pymysql
    if args.copia==DB_NAME:raise SystemExit('No se permite recuperar el esquema original configurado.')
    user=input('Usuario administrador de RDS: ').strip();password=getpass.getpass('Contraseña de RDS (entrada oculta): ')
    connection=pymysql.connect(host=DB_HOST,port=DB_PORT,user=user,password=password,database=args.copia,
        charset='utf8mb4',autocommit=True,cursorclass=pymysql.cursors.DictCursor,connect_timeout=5);password=None
    report={'copia':args.copia,'solo_diagnostico':not args.aplicar,'acciones':[],'informe_previo':Path(args.informe).name}
    try:
        with connection.cursor() as c:
            c.execute("SET time_zone='+00:00'")
            report['estado_previo']=inspect(c,args.copia,old,expected)
            # A rolled-back SQL test can advance AUTO_INCREMENT; row hashes remain unchanged.
            if snapshot(c,args.copia)!=prior['despues']:
                raise RuntimeError('Los datos originales cambiaron desde el informe; revisar antes de recuperar.')
            if not args.aplicar:
                print(json.dumps(report['estado_previo'],ensure_ascii=False,indent=2))
                print('Sólo diagnóstico: no se ejecutó DDL ni se registró 019.')
            else:recover(c,args.copia,old,expected,report)
    except Exception as error:
        report['error']=str(error);raise
    finally:
        connection.close()
        folder=Path.cwd()/'respaldos_rds';folder.mkdir(exist_ok=True)
        target=folder/('recuperacion_019_'+datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S-%f')+'.json')
        target.write_text(json.dumps(report,default=str,ensure_ascii=False,indent=2),encoding='utf-8')
        print('Informe guardado en',target)

if __name__=='__main__':main()
