"""Diagnosticar y completar únicamente los triggers pendientes de 011."""
import argparse
from datetime import datetime, timezone
import getpass
import hashlib
import json
from pathlib import Path
import re
import sys

from migrar_copia_rds import BASE_TABLES, quote, snapshot


VERSION = "011_reservas_invitados"
PREVIOUS = [
    "001_base_administracion", "002_sesiones_auditoria", "003_gestion_comercial",
    "004_asignaciones", "005_acceso_recursos", "006_edicion_auditoria",
    "007_editor_demos", "008_corregir_orden_pasos", "009_inventario_unidades",
    "010_catalogo_publico",
]
NEW_TABLES = {"configuracion_invitados", "comandos_invitado", "sesiones_invitado", "reservas_control"}
TABLES = BASE_TABLES | NEW_TABLES | {"migraciones_iot", "usuarios", "modelos", "asignaciones", "sesiones", "auditoria"}


def normalize(value):
    # El motor puede omitir comentarios de línea al guardar ROUTINE_DEFINITION.
    lines = [line for line in (value or "").splitlines() if not line.lstrip().startswith("--")]
    return re.sub(r"\s+", " ", "\n".join(lines)).strip()


def definitions(sql):
    procedures = {}
    triggers = {}
    for statement in sql.split("$$"):
        match = re.search(r"\bCREATE PROCEDURE\s+(sp_invitado_\w+)\b", statement)
        if match:
            body = statement[re.search(r"\bBEGIN\b", statement[match.end():]).start() + match.end():].strip()
            procedures[match.group(1)] = body
        match = re.search(r"\bCREATE TRIGGER\s+(tr_reserva_\w+)\s+BEFORE\s+(UPDATE|INSERT)\s+ON\s+(\w+)", statement)
        if match:
            definition = statement[match.start():].strip()
            body = definition[re.search(r"\bBEGIN\b", definition).start():]
            triggers[match.group(1)] = {"statement": definition, "body": body,
                                       "table": match.group(3), "event": match.group(2)}
    if len(procedures) != 7 or len(triggers) != 5:
        raise RuntimeError("La fuente SQL no contiene las siete rutinas y cinco triggers esperados.")
    return procedures, triggers


def inspect(cursor, schema, procedures, triggers):
    cursor.execute("SHOW FULL TABLES WHERE Table_type = 'BASE TABLE'")
    tables = {list(row.values())[0] for row in cursor.fetchall()}
    if tables != TABLES:
        raise RuntimeError("La copia no tiene exactamente las tablas esperadas del estado parcial 011.")
    cursor.execute("SELECT version FROM migraciones_iot ORDER BY version")
    versions = [row["version"] for row in cursor.fetchall()]
    if versions not in (PREVIOUS, PREVIOUS + [VERSION]):
        raise RuntimeError("El registro de migraciones no corresponde a 001–010 o 001–011.")
    for table in sorted(NEW_TABLES):
        cursor.execute("SELECT COUNT(*) AS n FROM " + quote(table))
        if cursor.fetchone()["n"] != 0:
            raise RuntimeError("La base de reservas ya contiene datos. Requiere revisión antes de recuperar DDL.")
    cursor.execute("SELECT ROUTINE_NAME, ROUTINE_DEFINITION FROM information_schema.ROUTINES "
                   "WHERE ROUTINE_SCHEMA=%s AND ROUTINE_NAME LIKE 'sp_invitado_%%'", (schema,))
    actual = {row["ROUTINE_NAME"]: row["ROUTINE_DEFINITION"] for row in cursor.fetchall()}
    if set(actual) != set(procedures) or any(normalize(actual[name]) != normalize(body) for name, body in procedures.items()):
        raise RuntimeError("Las rutinas existentes no coinciden con la fuente 011. No se reemplazaron.")
    cursor.execute("SELECT TRIGGER_NAME,EVENT_OBJECT_TABLE,EVENT_MANIPULATION,ACTION_TIMING,ACTION_STATEMENT "
                   "FROM information_schema.TRIGGERS WHERE TRIGGER_SCHEMA=%s", (schema,))
    actual = {row["TRIGGER_NAME"]: row for row in cursor.fetchall()}
    if set(actual) - set(triggers):
        raise RuntimeError("Hay triggers adicionales que requieren revisión.")
    for name, row in actual.items():
        expected = triggers[name]
        if (row["EVENT_OBJECT_TABLE"] != expected["table"] or row["EVENT_MANIPULATION"] != expected["event"]
            or row["ACTION_TIMING"] != "BEFORE" or normalize(row["ACTION_STATEMENT"]) != normalize(expected["body"])):
            raise RuntimeError("Un trigger existente difiere de la fuente 011. No se reemplazó.")
    missing = sorted(set(triggers) - set(actual))
    if VERSION in versions and missing:
        raise RuntimeError("011 figura aplicada pero faltan triggers. Revisa ese registro inconsistente.")
    cursor.execute("SELECT @@log_bin AS binary_logging, @@log_bin_trust_function_creators AS trust_creators")
    return {"version_registrada": VERSION in versions, "triggers_presentes": sorted(actual),
            "triggers_pendientes": missing, "parametros": cursor.fetchone()}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--copia", required=True)
    parser.add_argument("--informe", required=True)
    parser.add_argument("--diagnostico", action="store_true")
    args = parser.parse_args()
    if not re.fullmatch(r"iot_prueba_\d{8}_\d{6}_\d{6}", args.copia):
        raise SystemExit("Se requiere la copia aislada.")
    source = Path(__file__).with_name("011_reservas_invitados.up.sql")
    prior = json.loads(Path(args.informe).read_text(encoding="utf-8-sig"))
    if (prior.get("copia") != args.copia or prior.get("archivo_sql") != source.name
        or prior.get("sql_sha256") != hashlib.sha256(source.read_bytes()).hexdigest()
        or prior.get("datos_y_procedimientos_conservados") is not True):
        raise SystemExit("El informe previo no corresponde a esta copia y fuente SQL conservada.")
    procedures, triggers = definitions(source.read_text(encoding="utf-8"))
    sys.path.insert(0, str(Path.cwd()))
    import pymysql
    from app.config import DB_HOST, DB_PORT, DB_NAME
    if args.copia == DB_NAME:
        raise SystemExit("La recuperación requiere la copia, no la base original.")
    username = input("Usuario administrador de RDS: ").strip()
    password = getpass.getpass("Contraseña de RDS (entrada oculta): ")
    connection = pymysql.connect(host=DB_HOST, port=DB_PORT, user=username, password=password,
        database=args.copia, charset="utf8mb4", autocommit=True,
        cursorclass=pymysql.cursors.DictCursor, connect_timeout=5)
    password = None
    report = {"copia": args.copia, "solo_diagnostico": args.diagnostico, "triggers_creados": []}
    try:
        with connection.cursor() as cursor:
            report["estado_previo"] = inspect(cursor, args.copia, procedures, triggers)
            print(json.dumps(report["estado_previo"], ensure_ascii=False, indent=2))
            report["antes"] = snapshot(cursor, args.copia)
            pending = report["estado_previo"]["triggers_pendientes"]
            settings = report["estado_previo"]["parametros"]
            if args.diagnostico:
                print("Diagnóstico terminado. No se ejecutó DDL ni se registró 011.")
            elif pending and settings["binary_logging"] and not settings["trust_creators"]:
                raise RuntimeError("Falta habilitar log_bin_trust_function_creators en el grupo de parámetros de RDS. No se ejecutó DDL.")
            else:
                for name in pending:
                    cursor.execute(triggers[name]["statement"])
                    report["triggers_creados"].append(name)
                    print("Trigger creado:", name)
                state = inspect(cursor, args.copia, procedures, triggers)
                if state["triggers_pendientes"]:
                    raise RuntimeError("Siguen pendientes triggers. 011 no se registró.")
                report["despues"] = snapshot(cursor, args.copia)
                if report["antes"] != report["despues"]:
                    raise RuntimeError("Hay diferencias en los datos o procedimientos originales. 011 no se registró.")
                if not state["version_registrada"]:
                    cursor.execute("INSERT INTO migraciones_iot(version) VALUES(%s)", (VERSION,))
                report["estado_final"] = inspect(cursor, args.copia, procedures, triggers)
                report["datos_y_procedimientos_conservados"] = True
                print("Recuperación completada. Cinco triggers verificados y 011 registrada.")
                print("Datos y procedimientos conservados: True")
    except Exception as error:
        report["error"] = str(error)
        raise
    finally:
        connection.close()
        folder = Path.cwd() / "respaldos_rds"
        folder.mkdir(exist_ok=True)
        stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S-%f")
        target = folder / ("recuperacion_011_" + stamp + ".json")
        target.write_text(json.dumps(report, ensure_ascii=False, default=str, indent=2), encoding="utf-8")
        print("Informe guardado en", target)


if __name__ == "__main__":
    main()
