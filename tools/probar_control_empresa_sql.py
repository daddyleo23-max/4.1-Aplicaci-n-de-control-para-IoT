"""019: dos administradores distintos, caducidad y cierre; fixtures con ROLLBACK."""
import argparse
from datetime import datetime, timezone
import getpass
import hashlib
import json
from pathlib import Path
import re
import secrets
import sys


def exercise(connection, results):
    import pymysql
    with connection.cursor() as c:
        def record(label, okay=True):
            results.append({'prueba':label,'correcto':bool(okay)})
            print(label+(': CORRECTO' if okay else ': INCORRECTO'))
            if not okay:raise RuntimeError(label)
        def call(name,args=()):
            c.callproc(name,args);rows=c.fetchall()
            while c.nextset():pass
            return rows
        def reject(label,name,args):
            c.execute('SAVEPOINT negativa')
            try:call(name,args)
            except pymysql.MySQLError as error:
                if error.args[0]!=1644:raise
                c.execute('ROLLBACK TO SAVEPOINT negativa');record(label)
            else:record(label,False)
            finally:c.execute('RELEASE SAVEPOINT negativa')
        suffix=secrets.token_hex(8)
        accounts=[];sessions=[]
        for role in ('ADMINISTRADOR','ADMINISTRADOR','USUARIO'):
            c.execute('INSERT INTO usuarios(nombre,correo,password_hash,rol) VALUES(%s,%s,%s,%s)',('Empresa SQL',secrets.token_hex(8)+'@example.invalid','SIN_HASH_VALIDO',role))
            accounts.append(c.lastrowid)
            c.execute('INSERT INTO sesiones(id_usuario,token_hash,creada_utc,expira_utc) VALUES(%s,%s,UTC_TIMESTAMP(6),TIMESTAMPADD(HOUR,1,UTC_TIMESTAMP(6)))',(accounts[-1],hashlib.sha256(secrets.token_bytes(32)).digest()))
            sessions.append(c.lastrowid)
        c.execute('INSERT INTO modelos(nombre) VALUES(%s)',('Empresa SQL '+suffix,));model=c.lastrowid
        c.execute("INSERT INTO vehiculos(nombre,id_modelo,identificador_unidad,estado_comercial) VALUES(%s,%s,%s,'DISPONIBLE')",('Empresa SQL',model,'SQL-'+suffix));unit=c.lastrowid
        reject('Sin DETENER no reserva empresa','sp_control_adquirir',(sessions[0],unit))
        c.execute('INSERT INTO comandos(id_vehiculo,nombre,codigo,activo) VALUES(%s,%s,13,1)',(unit,'DETENER'))
        reject('Comprador sin propiedad no reserva inventario','sp_control_adquirir',(sessions[2],unit))
        first=call('sp_control_adquirir',(sessions[0],unit))[0]['id_control'];record('Administrador A reserva inventario')
        call('sp_control_exigir',(first,sessions[0],unit));record('Titular autorizado')
        reject('Administrador B no adquiere simultáneamente','sp_control_adquirir',(sessions[1],unit))
        reject('Administrador B no usa reserva A','sp_control_exigir',(first,sessions[1],unit))
        reject('Reserva no se libera sin cierre','sp_control_liberar',(first,))
        call('sp_control_renovar',(first,sessions[0],unit));record('Renovación de empresa')
        c.execute('UPDATE sesiones_control SET expira_utc=TIMESTAMPADD(SECOND,-1,UTC_TIMESTAMP(6)) WHERE id_control=%s',(first,))
        reject('Caducidad invalida operación','sp_control_exigir',(first,sessions[0],unit))
        record('Worker detecta caducidad de empresa',next(r for r in call('sp_control_reservas') if r['id_control']==first)['cierre_pendiente'])
        reject('Caducidad no roba reserva','sp_control_adquirir',(sessions[1],unit))
        call('sp_control_cerrar',(first,'EXPIRADA'))
        reject('DETENIENDO sigue bloqueando','sp_control_adquirir',(sessions[1],unit))
        call('sp_control_detener',(first,));call('sp_control_liberar',(first,));record('Cierre y DETENER antes de liberar')
        second=call('sp_control_adquirir',(sessions[1],unit))[0]['id_control'];record('Administrador B reserva tras liberar')
        call('sp_control_cerrar',(first,'CANCELADA'));call('sp_control_exigir',(second,sessions[1],unit));record('Cierre atrasado no afecta reserva nueva')
        c.execute('UPDATE sesiones SET revocada_utc=UTC_TIMESTAMP(6) WHERE id_sesion=%s',(sessions[1],))
        reject('Logout invalida reserva empresa','sp_control_exigir',(second,sessions[1],unit))
        record('Worker detecta logout',next(r for r in call('sp_control_reservas') if r['id_control']==second)['cierre_pendiente'])
        call('sp_control_cerrar',(second,'REVOCADA'));call('sp_control_detener',(second,));call('sp_control_liberar',(second,))
        c.execute('SELECT accion FROM auditoria WHERE tipo_recurso=%s AND id_recurso=%s',('vehiculo',str(unit)))
        record('Acciones de empresa auditadas',{'RESERVAR_EMPRESA','CERRAR_EMPRESA','LIBERAR_EMPRESA'}<={r['accion'] for r in c.fetchall()})


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--copia',required=True);args=parser.parse_args()
    if not re.fullmatch(r'iot_prueba_\d{8}_\d{6}_\d{6}',args.copia):raise SystemExit('Indica la copia aislada.')
    sys.path.insert(0,str(Path.cwd()))
    from app.config import DB_HOST,DB_PORT
    import pymysql
    user=input('Usuario administrador de RDS: ').strip();password=getpass.getpass('Contraseña de RDS (entrada oculta): ')
    db=pymysql.connect(host=DB_HOST,port=DB_PORT,user=user,password=password,database=args.copia,charset='utf8mb4',cursorclass=pymysql.cursors.DictCursor,autocommit=False,connect_timeout=5);password=None
    results=[]
    try:exercise(db,results)
    finally:
        db.rollback();db.close()
        folder=Path.cwd()/'respaldos_rds';folder.mkdir(exist_ok=True)
        target=folder/('empresa_sql_'+datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S-%f')+'.json')
        target.write_text(json.dumps({'copia':args.copia,'resultados':results,'rollback_ejecutado':True},ensure_ascii=False,indent=2),encoding='utf-8')
        print('ROLLBACK ejecutado. Informe guardado en',target)

if __name__=='__main__':main()
