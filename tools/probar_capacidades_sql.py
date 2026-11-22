"""Prueba capacidades018 en transacción, con unidades NUEVAS y sin hardware."""
import argparse
from datetime import datetime, timezone
import getpass
import json
from pathlib import Path
import re
import secrets
import sys


def exercise(connection,results):
    import pymysql
    suffix=secrets.token_hex(8)
    with connection.cursor() as q:
        q.execute("SET time_zone='+00:00'")
        def record(label,okay=True):
            results.append({'prueba':label,'correcto':bool(okay)})
            print(label+(': CORRECTO' if okay else ': INCORRECTO'))
            if not okay:raise RuntimeError(label)
        def call(name,args=()):
            q.callproc(name,args);rows=q.fetchall()
            while q.nextset():pass
            return rows
        def reject(label,name,args):
            q.execute('SAVEPOINT rechazo')
            try:call(name,args)
            except pymysql.MySQLError as e:
                if e.args[0] not in (1644,1062):raise
                q.execute('ROLLBACK TO SAVEPOINT rechazo');record(label)
            else:record(label,False)
            finally:q.execute('RELEASE SAVEPOINT rechazo')
        q.execute("INSERT INTO usuarios(nombre,correo,password_hash,rol) VALUES('Capacidad SQL',%s,'SIN_HASH','ADMINISTRADOR')",(suffix+'@example.invalid',));admin=q.lastrowid
        q.execute('INSERT INTO modelos(nombre) VALUES(%s)',('Capacidad SQL '+suffix,));model=q.lastrowid
        q.execute('INSERT INTO modelos(nombre) VALUES(%s)',('Otro modelo SQL '+suffix,));other=q.lastrowid
        def capability(model,name,code,active=True):
            return call('sp_capacidad_guardar',(admin,model,None,name,code,'Prueba de software',active))[0]['id_capacidad']
        stop=capability(model,'DETENER',13);forward=capability(model,'ADELANTE',1);inactive=capability(model,'LUCES',7,False)
        foreign=capability(other,'DETENER',13)
        record('Capacidades por modelo creadas',len(call('sp_capacidad_listar',(model,)))==3)
        reject('Código duplicado rechazado','sp_capacidad_guardar',(admin,model,None,'OTRA',1,'',True))
        reject('Nombre duplicado rechazado','sp_capacidad_guardar',(admin,model,None,'ADELANTE',2,'',True))
        q.execute("INSERT INTO vehiculos(nombre,id_modelo,identificador_unidad,estado_comercial) VALUES('Capacidad SQL',%s,%s,'DISPONIBLE')",(model,'CAP-'+suffix));unit=q.lastrowid
        def command(cap,active=True):return call('sp_capacidad_comando_guardar',(admin,unit,None,cap,'Prueba sin hardware',active))[0]['id_comando']
        stop_id=command(stop);forward_id=command(forward)
        record('Comandos de unidad creados desde capacidades')
        reject('Capacidad de otro modelo rechazada','sp_capacidad_comando_guardar',(admin,unit,None,foreign,'',True))
        reject('Capacidad inactiva no se activa en unidad','sp_capacidad_comando_guardar',(admin,unit,None,inactive,'',True))
        reject('Comando duplicado rechazado','sp_capacidad_comando_guardar',(admin,unit,None,forward,'',True))
        call('sp_capacidad_exigir',(unit,forward_id));record('Comando habilitado válido')
        reject('Capacidad usada conserva código','sp_capacidad_guardar',(admin,model,forward,'ADELANTE',2,'',True))
        reject('Capacidad usada conserva nombre','sp_capacidad_guardar',(admin,model,forward,'ATRAS',1,'',True))
        reject('Comando no cambia de identidad','sp_capacidad_comando_guardar',(admin,unit,forward_id,stop,'',True))
        reject('Capacidad con comando activo no se desactiva','sp_capacidad_guardar',(admin,model,forward,'ADELANTE',1,'',False))
        reject('DETENER de unidad activa no se desactiva','sp_capacidad_comando_guardar',(admin,unit,stop_id,stop,'',False))
        row=call('sp_capacidad_comando_guardar',(admin,unit,forward_id,forward,'Descripción editada',True))[0]
        record('Edición conserva ID',row['id_comando']==forward_id)
        call('sp_capacidad_comando_guardar',(admin,unit,forward_id,forward,'Inactivo',False))
        reject('Comando inactivo no ejecutable','sp_capacidad_exigir',(unit,forward_id))
        call('sp_capacidad_guardar',(admin,model,forward,'ADELANTE',1,'Deshabilitada',False))
        reject('No reactiva comando con capacidad deshabilitada','sp_capacidad_comando_guardar',(admin,unit,forward_id,forward,'',True))
        record('Compatibilidad refleja capacidad inactiva',not next(r for r in call('sp_capacidad_comandos_unidad',(unit,)) if r['id_comando']==forward_id)['compatible'])
        call('sp_capacidad_guardar',(admin,model,forward,'ADELANTE',1,'Habilitada',True))
        call('sp_capacidad_comando_guardar',(admin,unit,forward_id,forward,'Habilitado',True))
        # Reserva real de comprador creada sólo dentro de esta transacción.
        q.execute("INSERT INTO usuarios(nombre,correo,password_hash,rol) VALUES('Comprador SQL',%s,'SIN_HASH','USUARIO')",('c-'+suffix+'@example.invalid',));buyer=q.lastrowid
        q.execute('INSERT INTO asignaciones(id_vehiculo,id_usuario,asignado_por,inicio_utc) VALUES(%s,%s,%s,UTC_TIMESTAMP(6))',(unit,buyer,admin))
        q.execute('INSERT INTO sesiones(id_usuario,token_hash,creada_utc,expira_utc) VALUES(%s,%s,UTC_TIMESTAMP(6),UTC_TIMESTAMP(6)+INTERVAL 1 HOUR)',(buyer,secrets.token_bytes(32)));session=q.lastrowid
        lease=call('sp_control_adquirir',(session,unit))[0]['id_control']
        reject('Unidad reservada no permite editar comando','sp_capacidad_comando_guardar',(admin,unit,forward_id,forward,'Cambio durante reserva',True))
        reject('Modelo reservado no permite editar capacidad','sp_capacidad_guardar',(admin,model,forward,'ADELANTE',1,'Cambio durante reserva',True))
        call('sp_control_cerrar',(lease,'CANCELADA'));call('sp_control_detener',(lease,));call('sp_control_liberar',(lease,))
        rows=call('sp_capacidad_comandos_unidad',(unit,));record('Catálogo e IDs conservados',len(rows)==2 and {r['id_comando'] for r in rows}=={stop_id,forward_id})
        q.execute("SELECT COUNT(*) AS n FROM auditoria WHERE id_actor=%s AND accion IN ('GUARDAR_CAPACIDAD','GUARDAR_COMANDO_UNIDAD')",(admin,))
        record('Cambios de capacidades y comandos auditados',q.fetchone()['n']>=8)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--copia", required=True)
    args = parser.parse_args()
    if not re.fullmatch(r"iot_prueba_\d{8}_\d{6}_\d{6}", args.copia):
        raise SystemExit("Indica la copia aislada de prueba.")
    root = Path.cwd()
    sys.path.insert(0, str(root))
    import pymysql
    from app.config import DB_HOST, DB_PORT, DB_NAME
    if args.copia == DB_NAME:
        raise SystemExit("La copia debe ser distinta de la base original del backend.")
    username = input("Usuario administrador de RDS: ").strip()
    password = getpass.getpass("Contraseña de RDS (entrada oculta): ")
    connection = pymysql.connect(host=DB_HOST, port=DB_PORT, user=username, password=password,
        database=args.copia, charset="utf8mb4", autocommit=False,
        cursorclass=pymysql.cursors.DictCursor, connect_timeout=5)
    password = None
    results = []
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S-%f")
    report = {"copia": args.copia, "resultados": results, "sin_envio_a_hardware": True}
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT version FROM migraciones_iot WHERE version='018_capacidades_modelo'")
            if cursor.fetchone() is None:
                raise RuntimeError("Aplica primero la migración 018 en la copia.")
        exercise(connection, results)
    finally:
        connection.rollback()
        report["datos_de_prueba_revertidos"] = True
        connection.close()
        report["nota"] = "AUTO_INCREMENT puede avanzar tras ROLLBACK. No prueba recepción física de DETENER."
        folder = root / "respaldos_rds"
        folder.mkdir(exist_ok=True)
        target = folder / ("capacidades_sql_" + stamp + ".json")
        target.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        print("Informe guardado en", target)
        print("ROLLBACK ejecutado. Los registros de prueba no se conservan.")
    print("Comprobaciones SQL de capacidades completadas.")


if __name__ == "__main__":
    main()
