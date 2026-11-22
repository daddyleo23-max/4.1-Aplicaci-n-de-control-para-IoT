"""Comprueba SQL 014 con fixtures transaccionales; no envía movimientos."""
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
    with connection.cursor() as cursor:
        cursor.execute("SET time_zone='+00:00'")
        def record(label, okay=True):
            results.append({'prueba':label,'correcto':bool(okay)})
            print(label + (': CORRECTO' if okay else ': INCORRECTO'))
            if not okay:
                raise RuntimeError(label)
        def call(name, args=()):
            cursor.callproc(name,args)
            rows=cursor.fetchall()
            while cursor.nextset():pass
            return rows
        def reject(label, name, args):
            cursor.execute('SAVEPOINT rechazo')
            try:
                call(name,args)
            except pymysql.MySQLError as error:
                if error.args[0] != 1644:
                    raise
                cursor.execute('ROLLBACK TO SAVEPOINT rechazo')
                record(label)
            else:
                record(label,False)
            finally:
                cursor.execute('RELEASE SAVEPOINT rechazo')
        suffix=secrets.token_hex(8)
        def user(role):
            cursor.execute('INSERT INTO usuarios(nombre,correo,password_hash,rol) VALUES(%s,%s,%s,%s)',
                           ('Control SQL',secrets.token_hex(8)+'@example.invalid','SIN_HASH_VALIDO',role))
            return cursor.lastrowid
        admin=user('ADMINISTRADOR'); buyer=user('USUARIO'); other=user('USUARIO')
        cursor.execute('INSERT INTO modelos(nombre) VALUES(%s)',('Control SQL '+suffix,))
        model=cursor.lastrowid
        cursor.execute("INSERT INTO vehiculos(nombre,id_modelo,identificador_unidad,estado_comercial) VALUES(%s,%s,%s,'ASIGNADO')",('Control SQL',model,'CONTROL-'+suffix))
        unit=cursor.lastrowid
        cursor.execute('INSERT INTO asignaciones(id_vehiculo,id_usuario,asignado_por,inicio_utc) VALUES(%s,%s,%s,UTC_TIMESTAMP(6))',(unit,buyer,admin))
        def session(uid):
            cursor.execute('INSERT INTO sesiones(id_usuario,token_hash,creada_utc,expira_utc) VALUES(%s,%s,UTC_TIMESTAMP(6),TIMESTAMPADD(HOUR,1,UTC_TIMESTAMP(6)))',
                           (uid,hashlib.sha256(secrets.token_bytes(32)).digest()))
            return cursor.lastrowid
        first=session(buyer); second=session(buyer); foreign=session(other); administrative=session(admin)
        reject('Falta DETENER rechazada','sp_control_adquirir',(first,unit))
        cursor.execute("INSERT INTO comandos(id_vehiculo,nombre,codigo) VALUES(%s,'DETENER',13)",(unit,))
        reject('Comprador ajeno rechazado','sp_control_adquirir',(foreign,unit))
        reject('Admin sin propiedad rechazado','sp_control_adquirir',(administrative,unit))
        lease=call('sp_control_adquirir',(first,unit))[0]['id_control']
        record('Reserva del propietario creada')
        call('sp_control_exigir',(lease,first,unit));record('Sesión titular autorizada')
        reject('Segunda sesión del mismo comprador rechazada','sp_control_adquirir',(second,unit))
        reject('Segunda sesión no usa reserva ajena','sp_control_exigir',(lease,second,unit))
        reject('Operación sin titular bloqueada','sp_reserva_exigir_libre',(unit,))
        call('sp_control_renovar',(lease,first,unit));record('Renovación del titular')
        reject('Liberación sin cierre rechazada','sp_control_liberar',(lease,))
        cursor.execute('UPDATE sesiones_control SET expira_utc=UTC_TIMESTAMP(6)-INTERVAL 1 SECOND WHERE id_control=%s',(lease,))
        reject('Reserva vencida sin acceso','sp_control_exigir',(lease,first,unit))
        reject('Caducidad no permite robar reserva','sp_control_adquirir',(second,unit))
        record('Caducidad detectada para cierre',any(row['id_control']==lease and row['cierre_pendiente'] for row in call('sp_control_reservas')))
        call('sp_control_cerrar',(lease,'EXPIRADA'))
        reject('Nueva reserva bloqueada durante DETENER','sp_control_adquirir',(second,unit))
        reject('Titular sin acceso durante cierre','sp_control_exigir',(lease,first,unit))
        # Simula sólo el fin del protocolo SQL: el servicio posterior debe procesar DETENER antes de liberar.
        call('sp_control_liberar',(lease,));record('Liberación tras cierre SQL')
        new=call('sp_control_adquirir',(second,unit))[0]['id_control']
        record('Sesión distinta adquiere tras liberación',new!=lease)
        reject('Cierre atrasado no libera reserva nueva','sp_control_liberar',(lease,))
        call('sp_control_cerrar',(lease,'REINICIO'))
        call('sp_control_exigir',(new,second,unit));record('Cierre atrasado conserva titular nuevo')
        cursor.execute('UPDATE sesiones SET revocada_utc=UTC_TIMESTAMP(6) WHERE id_sesion=%s',(second,))
        reject('Logout invalida acceso','sp_control_exigir',(new,second,unit))
        record('Logout detectado para cierre',any(row['id_control']==new and row['cierre_pendiente'] for row in call('sp_control_reservas')))
        call('sp_control_cerrar',(new,'REVOCADA'));call('sp_control_liberar',(new,))
        cursor.execute("SELECT COUNT(*) AS n FROM auditoria WHERE id_actor=%s AND accion IN ('RESERVAR_COMPRADOR','CERRAR_COMPRADOR','LIBERAR_COMPRADOR')",(buyer,))
        record('Reservas y cierres auditados',cursor.fetchone()['n']>=6)
        cursor.execute('SELECT COUNT(*) AS n FROM sesiones_control WHERE id_sesion IN (%s,%s)',(first,second))
        record('Historial de reservas conservado',cursor.fetchone()['n']==2)
        # Comprobar compatibilidad real de las rutinas Invitado anteriores bajo el esquema ampliado.
        from probar_reservas_sql import exercise as guest_exercise
        guest_exercise(connection,results)
        record('Regresión SQL de Invitado completada')


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
            cursor.execute("SELECT version FROM migraciones_iot WHERE version='014_reservas_comprador'")
            if cursor.fetchone() is None:
                raise RuntimeError("Aplica primero la migración 014 en la copia.")
        exercise(connection, results)
    finally:
        connection.rollback()
        report["datos_de_prueba_revertidos"] = True
        connection.close()
        report["nota"] = "AUTO_INCREMENT puede avanzar tras ROLLBACK. No prueba recepción física de DETENER."
        folder = root / "respaldos_rds"
        folder.mkdir(exist_ok=True)
        target = folder / ("control_sql_" + stamp + ".json")
        target.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        print("Informe guardado en", target)
        print("ROLLBACK ejecutado. Los registros de prueba no se conservan.")
    print("Comprobaciones SQL de exclusividad del comprador completadas.")


if __name__ == "__main__":
    main()
