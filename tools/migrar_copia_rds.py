"""Aplicar una migración versionada y comprobar los datos originales en la copia."""

import argparse
from datetime import datetime, timezone
import getpass
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys


BASE_TABLES = {
    "vehiculos", "comandos", "estado_vehiculo",
    "historial_comandos", "demos", "demo_movimientos",
}
TABLES_011 = BASE_TABLES | {"migraciones_iot", "usuarios", "modelos", "asignaciones",
                          "sesiones", "auditoria", "configuracion_invitados",
                          "comandos_invitado", "sesiones_invitado", "reservas_control"}


def quote(name):
    return "`" + name.replace("`", "``") + "`"


def check_trigger_configuration(cursor, sql_text):
    """Preflight para RDS: evitar DDL parcial al crear triggers con binlog."""
    if not re.search(r"\bCREATE\s+TRIGGER\b", sql_text, re.IGNORECASE):
        return
    cursor.execute("SELECT @@log_bin AS binary_logging, "
                   "@@log_bin_trust_function_creators AS trust_creators")
    settings = cursor.fetchone()
    if settings["binary_logging"] and not settings["trust_creators"]:
        raise SystemExit(
            "RDS tiene registro binario activo y log_bin_trust_function_creators=0. "
            "Revisa el grupo de parámetros antes de crear triggers. No se ejecutó el SQL."
        )


def snapshot(cursor, schema):
    data = {"tablas": {}, "procedimientos": []}
    for name in sorted(BASE_TABLES):
        cursor.execute(
            "SELECT COLUMN_NAME FROM information_schema.COLUMNS "
            "WHERE TABLE_SCHEMA=%s AND TABLE_NAME=%s ORDER BY ORDINAL_POSITION",
            (schema, name),
        )
        columns = [item["COLUMN_NAME"] for item in cursor.fetchall()]
        # Al comprobar después del ALTER se comparan las columnas originales.
        if name == "vehiculos":
            columns = [column for column in columns if column not in {
                "id_modelo", "identificador_unidad", "estado_comercial",
            }]
        if name == "demos":
            columns = [column for column in columns if column not in {
                "id_propietario", "tipo", "revision",
            }]
        cursor.execute(
            "SELECT " + ", ".join(map(quote, columns)) +
            " FROM " + quote(schema) + "." + quote(name) +
            " ORDER BY " + quote(columns[0])
        )
        digest = hashlib.sha256()
        count = 0
        for row in cursor:
            digest.update(json.dumps(row, default=str, ensure_ascii=False,
                                     sort_keys=True).encode("utf-8") + b"\n")
            count += 1
        data["tablas"][name] = {"filas": count, "sha256": digest.hexdigest()}
    cursor.execute(
        "SELECT ROUTINE_NAME, ROUTINE_DEFINITION, SECURITY_TYPE, DEFINER "
        "FROM information_schema.ROUTINES WHERE ROUTINE_SCHEMA=%s "
        "ORDER BY ROUTINE_NAME", (schema,),
    )
    data["procedimientos"] = [
        row for row in cursor.fetchall()
        if not row["ROUTINE_NAME"].startswith(("sp_auth_", "sp_admin_", "sp_usuario_", "sp_acceso_", "sp_editor_", "sp_catalogo_", "sp_invitado_", "sp_reserva_", "sp_soporte_", "sp_control_"))
    ]
    return data


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mysql", required=True)
    parser.add_argument("--sql", required=True)
    parser.add_argument("--copia", required=True)
    args = parser.parse_args()
    if not re.fullmatch(r"iot_prueba_\d{8}_\d{6}_\d{6}", args.copia):
        raise SystemExit("Se requiere el nombre de la copia creada por la verificación.")
    sql = Path(args.sql).resolve(strict=True)
    migrations = {
        "001_base_administracion.up.sql": ("001", BASE_TABLES),
        "002_sesiones_auditoria.up.sql": (
            "002", BASE_TABLES | {"migraciones_iot", "usuarios", "modelos", "asignaciones"},
        ),
        "003_gestion_comercial.up.sql": (
            "003", BASE_TABLES | {"migraciones_iot", "usuarios", "modelos",
                                 "asignaciones", "sesiones", "auditoria"},
        ),
        "004_asignaciones.up.sql": (
            "004", BASE_TABLES | {"migraciones_iot", "usuarios", "modelos",
                                 "asignaciones", "sesiones", "auditoria"},
        ),
        "005_acceso_recursos.up.sql": (
            "005", BASE_TABLES | {"migraciones_iot", "usuarios", "modelos",
                                 "asignaciones", "sesiones", "auditoria"},
        ),
        "006_edicion_auditoria.up.sql": (
            "006", BASE_TABLES | {"migraciones_iot", "usuarios", "modelos",
                                 "asignaciones", "sesiones", "auditoria"},
        ),
        "007_editor_demos.up.sql": (
            "007", BASE_TABLES | {"migraciones_iot", "usuarios", "modelos",
                                 "asignaciones", "sesiones", "auditoria"},
        ),
        "008_corregir_orden_pasos.up.sql": (
            "008", BASE_TABLES | {"migraciones_iot", "usuarios", "modelos",
                                 "asignaciones", "sesiones", "auditoria"},
        ),
        "009_inventario_unidades.up.sql": (
            "009", BASE_TABLES | {"migraciones_iot", "usuarios", "modelos",
                                 "asignaciones", "sesiones", "auditoria"},
        ),
    }
    migrations["010_catalogo_publico.up.sql"] = (
        "010", BASE_TABLES | {"migraciones_iot", "usuarios", "modelos",
                             "asignaciones", "sesiones", "auditoria"},
    )
    migrations["011_reservas_invitados.up.sql"] = (
        "011", BASE_TABLES | {"migraciones_iot", "usuarios", "modelos",
                             "asignaciones", "sesiones", "auditoria"},
    )
    migrations["012_api_invitados.up.sql"] = (
        "012", TABLES_011,
    )
    migrations["013_soporte_diagnostico.up.sql"] = ("013", TABLES_011)
    migrations["014_reservas_comprador.up.sql"] = ("014", TABLES_011 | {"permisos_soporte"})
    migrations["015_api_control_comprador.up.sql"] = ("015", TABLES_011 | {"permisos_soporte", "sesiones_control"})
    migrations["016_soporte_operativo.up.sql"] = ("016", TABLES_011 | {"permisos_soporte", "sesiones_control"})
    if sql.name not in migrations:
        raise SystemExit("Este ejecutor admite las migraciones 001 a 016.")
    version, expected_tables = migrations[sql.name]
    root = Path.cwd()
    sys.path.insert(0, str(root))
    import pymysql
    from app.config import DB_HOST, DB_PORT, DB_NAME

    if args.copia == DB_NAME:
        raise SystemExit("La base configurada por FastAPI debe ser distinta de la copia.")
    username = input("Usuario administrador de RDS: ").strip()
    password = getpass.getpass("Contraseña de RDS (entrada oculta): ")
    connection = pymysql.connect(
        host=DB_HOST, port=DB_PORT, user=username, password=password,
        database=args.copia, charset="utf8mb4", autocommit=True,
        cursorclass=pymysql.cursors.DictCursor, connect_timeout=5,
    )
    try:
        with connection.cursor() as cursor:
            cursor.execute("SET time_zone = '+00:00'")
            check_trigger_configuration(cursor, sql.read_text(encoding="utf-8"))
            cursor.execute("SHOW FULL TABLES WHERE Table_type = 'BASE TABLE'")
            names = {list(row.values())[0] for row in cursor.fetchall()}
            if names != expected_tables:
                raise SystemExit(
                    "La copia no tiene el conjunto de tablas previo esperado. "
                    "Si hubo un intento anterior, revisa su resultado antes de continuar."
                )
            if version != "001":
                cursor.execute("SELECT version FROM migraciones_iot ORDER BY version")
                expected_versions = [
                    Path(filename).name.removesuffix(".up.sql")
                    for filename, (number, _) in sorted(migrations.items())
                    if number < version
                ]
                if [row["version"] for row in cursor.fetchall()] != expected_versions:
                    raise SystemExit("La copia no tiene las migraciones previas esperadas.")
            if version == "016":
                cursor.execute("SELECT COUNT(*) AS n FROM reservas_control")
                if cursor.fetchone()["n"]:
                    raise SystemExit("Cierra todas las reservas desde la aplicación antes de aplicar 016.")
            before = snapshot(cursor, args.copia)
        report = {"copia": args.copia, "antes": before,
                  "archivo_sql": sql.name, "sql_sha256": hashlib.sha256(sql.read_bytes()).hexdigest()}
        folder = root / "respaldos_rds"
        folder.mkdir(exist_ok=True)
        stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S-%f")
        destination = folder / f"migracion_{version}_{stamp}.json"
        destination.write_text(json.dumps(report, default=str, ensure_ascii=False, indent=2),
                               encoding="utf-8")
        environment = os.environ.copy()
        environment["MYSQL_PWD"] = password
        password = None
        try:
            with sql.open("rb") as source:
                result = subprocess.run(
                    [args.mysql, "--host", DB_HOST, "--port", str(DB_PORT),
                     "--user", username, "--database", args.copia,
                     "--default-character-set=utf8mb4", "--binary-mode"],
                    stdin=source, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
                    env=environment, check=False,
                )
        finally:
            environment.pop("MYSQL_PWD", None)
        report["mysql_exit_code"] = result.returncode
        with connection.cursor() as cursor:
            report["despues"] = snapshot(cursor, args.copia)
            cursor.execute("SHOW FULL TABLES WHERE Table_type = 'BASE TABLE'")
            report["tablas_finales"] = [list(row.values())[0] for row in cursor.fetchall()]
            if version == "002":
                cursor.execute(
                    "SELECT ROUTINE_NAME FROM information_schema.ROUTINES "
                    "WHERE ROUTINE_SCHEMA=%s AND ROUTINE_NAME LIKE 'sp_auth_%%' "
                    "ORDER BY ROUTINE_NAME", (args.copia,),
                )
                report["procedimientos_auth"] = [
                    row["ROUTINE_NAME"] for row in cursor.fetchall()
                ]
        report["datos_y_procedimientos_conservados"] = report["antes"] == report["despues"]
        destination.write_text(json.dumps(report, default=str, ensure_ascii=False, indent=2),
                               encoding="utf-8")
        print(f"Informe guardado en {destination}")
        print("Código de salida MySQL:", result.returncode)
        print("Datos y procedimientos conservados:", report["datos_y_procedimientos_conservados"])
        print("Tablas finales:", ", ".join(report["tablas_finales"]))
        if version == "002":
            print("Procedimientos de autenticación:", ", ".join(report["procedimientos_auth"]))
        if result.returncode:
            print(result.stderr.decode("utf-8", errors="replace"))
            raise SystemExit("DDL posiblemente parcial. Revisa el informe antes de repetir.")
        if not report["datos_y_procedimientos_conservados"]:
            raise SystemExit("La comparación detectó diferencias que requieren revisión.")
    finally:
        connection.close()


if __name__ == "__main__":
    main()
