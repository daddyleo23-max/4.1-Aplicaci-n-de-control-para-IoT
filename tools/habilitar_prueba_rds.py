"""Otorgar EXECUTE a la cuenta existente del backend sobre la copia de prueba."""

import argparse
import getpass
from pathlib import Path
import re
import sys


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--copia", required=True)
    args = parser.parse_args()
    if not re.fullmatch(r"iot_prueba_\d{8}_\d{6}_\d{6}", args.copia):
        raise SystemExit("Indica la copia de prueba.")
    sys.path.insert(0, str(Path.cwd()))
    import pymysql
    from app.config import DB_HOST, DB_PORT, DB_USER, DB_NAME

    if args.copia == DB_NAME:
        raise SystemExit("Selecciona la copia aislada.")
    username = input("Usuario administrador de RDS: ").strip()
    password = getpass.getpass("Contraseña de RDS (entrada oculta): ")
    connection = pymysql.connect(
        host=DB_HOST, port=DB_PORT, user=username, password=password,
        database=args.copia, charset="utf8mb4",
        cursorclass=pymysql.cursors.DictCursor, autocommit=True,
    )
    password = None
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT User,Host FROM mysql.user WHERE User=%s AND Host='%%'",
                           (DB_USER,))
            if not cursor.fetchone():
                raise SystemExit("No existe la cuenta del backend con Host=%. Revisa sus permisos.")
            cursor.execute("SELECT version FROM migraciones_iot ORDER BY version")
            versions = {row["version"] for row in cursor.fetchall()}
            if "002_sesiones_auditoria" not in versions:
                raise SystemExit("Falta la migración 002.")
            cursor.execute(
                "GRANT EXECUTE ON `" + args.copia + "`.* TO %s@%s", (DB_USER, "%"),
            )
            print(f"Permiso EXECUTE concedido a {DB_USER} sobre {args.copia}.")
    finally:
        connection.close()


if __name__ == "__main__":
    main()
