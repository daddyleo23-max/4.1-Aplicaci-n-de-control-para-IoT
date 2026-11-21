"""Restaurar un SQL de respaldar_rds.py en una base nueva de prueba."""

import argparse
from datetime import datetime, timezone
import getpass
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--respaldo", required=True)
    parser.add_argument("--mysql", required=True)
    args = parser.parse_args()
    backup = Path(args.respaldo).resolve(strict=True)
    manifest = json.loads(backup.with_suffix(".manifest.json").read_text(encoding="utf-8"))
    digest = hashlib.sha256()
    with backup.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    if digest.hexdigest() != manifest["sha256"]:
        raise SystemExit("El SHA256 del respaldo no coincide con su manifiesto.")

    sys.path.insert(0, str(Path.cwd()))
    import pymysql
    from app.config import DB_HOST, DB_PORT, DB_NAME

    if manifest["esquema"] != DB_NAME:
        raise SystemExit("El respaldo corresponde a otro esquema.")
    username = input("Usuario administrador de RDS: ").strip()
    password = getpass.getpass("Contraseña de RDS (entrada oculta): ")
    connection = pymysql.connect(
        host=DB_HOST, port=DB_PORT, database=DB_NAME, user=username,
        password=password, charset="utf8mb4",
        cursorclass=pymysql.cursors.DictCursor, connect_timeout=5,
    )
    target = "iot_prueba_" + datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S_%f")
    report = {"origen": DB_NAME, "copia": target, "respaldo": backup.name}
    try:
        with connection.cursor() as cursor:
            cursor.execute("SHOW CREATE DATABASE " + quote(DB_NAME))
            definition = cursor.fetchone()["Create Database"]
            # Conservar las opciones originales de charset/collation.
            options = definition[definition.index("/*!"):] if "/*!" in definition else ""
            cursor.execute("CREATE DATABASE " + quote(target) + " " + options)
        print(f"Base de prueba creada: {target}")
        environment = os.environ.copy()
        environment["MYSQL_PWD"] = password
        password = None
        try:
            with backup.open("rb") as source:
                result = subprocess.run(
                    [args.mysql, "--host", DB_HOST, "--port", str(DB_PORT),
                     "--user", username, "--database", target,
                     "--default-character-set=utf8mb4", "--binary-mode"],
                    stdin=source, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
                    env=environment, check=False,
                )
        finally:
            environment.pop("MYSQL_PWD", None)
        if result.returncode:
            print(result.stderr.decode("utf-8", errors="replace"))
            raise SystemExit(f"Restauración fallida. Copia conservada para diagnóstico: {target}")
        with connection.cursor() as cursor:
            report["tablas_origen"] = inventory(cursor, DB_NAME)
            report["tablas_copia"] = inventory(cursor, target)
            for label, schema in (("procedimientos_origen", DB_NAME), ("procedimientos_copia", target)):
                cursor.execute(
                    "SELECT ROUTINE_NAME FROM information_schema.ROUTINES "
                    "WHERE ROUTINE_SCHEMA=%s ORDER BY ROUTINE_NAME", (schema,)
                )
                report[label] = [row["ROUTINE_NAME"] for row in cursor.fetchall()]
        report["conteos_coinciden"] = report["tablas_origen"] == report["tablas_copia"]
        report["procedimientos_coinciden"] = report["procedimientos_origen"] == report["procedimientos_copia"]
        destination = backup.with_name(backup.stem + ".verificacion.json")
        with destination.open("x", encoding="utf-8") as output:
            json.dump(report, output, ensure_ascii=False, indent=2)
        print(json.dumps(report, ensure_ascii=False, indent=2))
        print(f"Informe guardado en {destination}")
        print("Los conteos del origen corresponden al momento de esta comprobación.")
        print("La copia de prueba queda disponible para las migraciones.")
    finally:
        connection.close()


def quote(identifier):
    return "`" + identifier.replace("`", "``") + "`"


def inventory(cursor, schema):
    cursor.execute(
        "SELECT TABLE_NAME FROM information_schema.TABLES "
        "WHERE TABLE_SCHEMA=%s AND TABLE_TYPE='BASE TABLE' ORDER BY TABLE_NAME",
        (schema,),
    )
    tables = [row["TABLE_NAME"] for row in cursor.fetchall()]
    counts = {}
    for table in tables:
        cursor.execute("SELECT COUNT(*) AS total FROM " + quote(schema) + "." + quote(table))
        counts[table] = cursor.fetchone()["total"]
    return counts


if __name__ == "__main__":
    main()
