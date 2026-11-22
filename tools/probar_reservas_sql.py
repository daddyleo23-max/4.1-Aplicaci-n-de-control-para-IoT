"""Probar reservas 011 con datos transaccionales desechables. No mueve hardware."""
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
    suffix = secrets.token_hex(8)

    def record(label, okay):
        results.append({"prueba": label, "correcto": bool(okay)})
        print(label + (": CORRECTO" if okay else ": INCORRECTO"))
        if not okay:
            raise RuntimeError(label)

    with connection.cursor() as cursor:
        cursor.execute("SET time_zone = '+00:00'")

        def call(name, params=()):
            cursor.execute("CALL " + name + "(" + ",".join(["%s"] * len(params)) + ")", params)
            rows = cursor.fetchall()
            while cursor.nextset():
                pass
            return rows

        def reject(label, name, params):
            cursor.execute("SAVEPOINT antes_rechazo")
            try:
                call(name, params)
            except (pymysql.OperationalError, pymysql.IntegrityError) as error:
                if error.args[0] not in (1644, 1062):
                    raise
                cursor.execute("ROLLBACK TO SAVEPOINT antes_rechazo")
                record(label, True)
            else:
                record(label, False)
            finally:
                cursor.execute("RELEASE SAVEPOINT antes_rechazo")

        def reject_sql(label, statement, params):
            cursor.execute("SAVEPOINT antes_cambio")
            try:
                cursor.execute(statement, params)
            except pymysql.OperationalError as error:
                if error.args[0] != 1644:
                    raise
                cursor.execute("ROLLBACK TO SAVEPOINT antes_cambio")
                record(label, True)
            else:
                record(label, False)
            finally:
                cursor.execute("RELEASE SAVEPOINT antes_cambio")

        cursor.execute("INSERT INTO usuarios(nombre,correo,password_hash,rol) VALUES(%s,%s,%s,'ADMINISTRADOR')",
                       ("Prueba reservas", "reserva-" + suffix + "@example.invalid", "SIN_HASH_VALIDO"))
        actor = cursor.lastrowid
        cursor.execute("INSERT INTO modelos(nombre,publico) VALUES(%s,1)", ("Reservas SQL " + suffix,))
        model = cursor.lastrowid
        cursor.execute("INSERT INTO vehiculos(nombre,id_modelo,identificador_unidad,estado_comercial) "
                       "VALUES(%s,%s,%s,'EXHIBICION')", ("Reserva SQL", model, "RES-" + suffix))
        unit = cursor.lastrowid
        cursor.execute("INSERT INTO comandos(id_vehiculo,nombre,codigo) VALUES(%s,'DETENER',13)", (unit,))
        stop = cursor.lastrowid
        cursor.execute("INSERT INTO comandos(id_vehiculo,nombre,codigo) VALUES(%s,'POWER',11)", (unit,))
        power = cursor.lastrowid
        cursor.execute("INSERT INTO vehiculos(nombre,id_modelo,identificador_unidad,estado_comercial) "
                       "VALUES(%s,%s,%s,'EXHIBICION')", ("Otra reserva SQL", model, "RES-OTRA-" + suffix))
        other_unit = cursor.lastrowid
        cursor.execute("INSERT INTO comandos(id_vehiculo,nombre,codigo) VALUES(%s,'DETENER',13)", (other_unit,))
        other_stop = cursor.lastrowid
        key_a = hashlib.sha256(secrets.token_bytes(32)).digest()
        key_b = hashlib.sha256(secrets.token_bytes(32)).digest()
        params = (actor, unit, True, 15, 300, json.dumps([stop]))
        reject("Reserva sin configuración rechazada", "sp_invitado_reservar", (unit, key_a))
        for label, duration, pulse, commands in (
            ("Falta DETENER rechazada", 15, 300, [power]),
            ("Comando ajeno rechazado", 15, 300, [other_stop]),
            ("Comandos duplicados rechazados", 15, 300, [stop, stop]),
            ("Identificadores de texto rechazados", 15, 300, [str(stop)]),
            ("Duración fuera de rango rechazada", 121, 300, [stop]),
            ("Pulso fuera de rango rechazado", 15, 501, [stop]),
        ):
            reject(label, "sp_invitado_configurar", (actor, unit, True, duration, pulse, json.dumps(commands)))
        call("sp_invitado_configurar", params)
        record("Configuración limitada a DETENER guardada", True)
        first = call("sp_invitado_reservar", (unit, key_a))[0]
        session = first["id_sesion_invitado"]
        context = call("sp_invitado_obtener", (key_a,))
        record("Sesión temporal activa", len(context) == 1 and context[0]["id_vehiculo"] == unit
               and 0 <= context[0]["segundos_restantes"] <= 15)
        commands = call("sp_invitado_comandos", (key_a,))
        record("Sólo comando autorizado visible", [row["id_comando"] for row in commands] == [stop])
        reject("Segunda reserva rechazada", "sp_invitado_reservar", (unit, key_b))
        reject("Cambio de límites durante reserva rechazado", "sp_invitado_configurar", params)
        reject("Liberación sin cierre rechazada", "sp_invitado_liberar", (session,))
        reject_sql("Edición de unidad reservada rechazada", "UPDATE vehiculos SET nombre='Cambio rechazado' WHERE id_vehiculo=%s", (unit,))
        reject_sql("Edición de comando reservado rechazada", "UPDATE comandos SET activo=0 WHERE id_comando=%s", (stop,))
        reject_sql("Retiro de modelo reservado rechazado", "UPDATE modelos SET publico=0 WHERE id_modelo=%s", (model,))
        reject_sql("Asignación durante reserva rechazada",
                   "INSERT INTO asignaciones(id_vehiculo,id_usuario,asignado_por,inicio_utc) VALUES(%s,%s,%s,UTC_TIMESTAMP(6))",
                   (unit, actor, actor))
        # Adelanta únicamente la caducidad de esta sesión de prueba, sin esperar.
        cursor.execute("UPDATE sesiones_invitado SET inicio_utc=UTC_TIMESTAMP(6)-INTERVAL 20 SECOND, "
                       "expira_utc=UTC_TIMESTAMP(6)-INTERVAL 1 SECOND WHERE id_sesion_invitado=%s", (session,))
        record("Sesión vencida sin acceso", not call("sp_invitado_obtener", (key_a,)))
        record("Sesión vencida sin comandos", not call("sp_invitado_comandos", (key_a,)))
        reject("Caducidad no libera antes de DETENER", "sp_invitado_reservar", (unit, key_b))
        pending = call("sp_invitado_pendientes")
        record("Caducidad detectada para cierre", any(row["id_sesion_invitado"] == session for row in pending))
        call("sp_invitado_cerrar", (session, "EXPIRADA"))
        cursor.execute("SELECT estado FROM reservas_control WHERE id_vehiculo=%s", (unit,))
        record("Reserva conserva bloqueo durante detención", cursor.fetchone()["estado"] == "DETENIENDO")
        reject("Nueva reserva durante detención rechazada", "sp_invitado_reservar", (unit, key_b))
        # Comprobación del estado SQL; no se ha enviado DETENER a un vehículo físico.
        call("sp_invitado_liberar", (session,))
        second = call("sp_invitado_reservar", (unit, key_b))[0]["id_sesion_invitado"]
        record("Nueva reserva tras cierre completo", second != session)
        call("sp_invitado_cerrar", (second, "CANCELADA"))
        record("Cancelación revoca token", not call("sp_invitado_obtener", (key_b,)))
        call("sp_invitado_liberar", (second,))
        cursor.execute("UPDATE comandos SET activo=0 WHERE id_comando=%s", (stop,))
        key_c = hashlib.sha256(secrets.token_bytes(32)).digest()
        reject("Reserva sin DETENER activo rechazada", "sp_invitado_reservar", (unit, key_c))
        cursor.execute("UPDATE comandos SET activo=1 WHERE id_comando=%s", (stop,))
        cursor.execute("INSERT INTO usuarios(nombre,correo,password_hash,rol) VALUES(%s,%s,%s,'USUARIO')",
                       ("Comprador SQL", "reserva-comprador-" + suffix + "@example.invalid", "SIN_HASH_VALIDO"))
        buyer = cursor.lastrowid
        cursor.execute("INSERT INTO asignaciones(id_vehiculo,id_usuario,asignado_por,inicio_utc) VALUES(%s,%s,%s,UTC_TIMESTAMP(6))",
                       (unit, buyer, actor))
        reject("Unidad con propietario rechazada", "sp_invitado_reservar", (unit, key_c))
        reject("Configuración de unidad asignada rechazada", "sp_invitado_configurar", params)
        cursor.execute("SELECT COUNT(*) AS n FROM sesiones_invitado WHERE id_vehiculo=%s AND fin_utc IS NOT NULL", (unit,))
        record("Historial de sesiones conservado", cursor.fetchone()["n"] == 2)
        cursor.execute("SELECT COUNT(*) AS n FROM auditoria WHERE tipo_recurso='vehiculo' AND id_recurso=%s "
                       "AND accion IN ('RESERVAR_INVITADO','CERRAR_INVITADO','LIBERAR_INVITADO')", (str(unit),))
        record("Reservas y cierres auditados sin tokens", cursor.fetchone()["n"] == 6)
    return suffix


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
            cursor.execute("SELECT version FROM migraciones_iot WHERE version='011_reservas_invitados'")
            if cursor.fetchone() is None:
                raise RuntimeError("Aplica primero la migración 011 en la copia.")
        exercise(connection, results)
    finally:
        connection.rollback()
        report["datos_de_prueba_revertidos"] = True
        connection.close()
        report["nota"] = "AUTO_INCREMENT puede avanzar tras ROLLBACK. No prueba recepción física de DETENER."
        folder = root / "respaldos_rds"
        folder.mkdir(exist_ok=True)
        target = folder / ("reservas_sql_" + stamp + ".json")
        target.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        print("Informe guardado en", target)
        print("ROLLBACK ejecutado. Los registros de prueba no se conservan.")
    print("Comprobaciones SQL de reservas completadas.")


if __name__ == "__main__":
    main()
