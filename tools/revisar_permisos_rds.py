"""Ejecutar junto a app desde la raíz del backend en Windows Server."""

import getpass
import json
import sys
from datetime import datetime, timezone
from pathlib import Path


def main():
    root = Path.cwd()
    if not (root / "app" / "config.py").is_file():
        raise SystemExit("Ejecuta desde C:\\practica_2_6_iot.")
    sys.path.insert(0, str(root))
    import pymysql
    from app.config import DB_HOST, DB_PORT, DB_NAME, DB_USER

    username = input("Usuario administrador de RDS: ").strip()
    password = getpass.getpass("Contraseña de RDS (entrada oculta): ")
    connection = pymysql.connect(
        host=DB_HOST, port=DB_PORT, database=DB_NAME,
        user=username, password=password, charset="utf8mb4",
        cursorclass=pymysql.cursors.DictCursor, connect_timeout=5,
    )
    password = None
    report = {"cuenta_configurada_backend": DB_USER, "cuentas": []}
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT User, Host, plugin, account_locked, password_expired "
                "FROM mysql.user WHERE User = %s", (DB_USER,),
            )
            for account in cursor.fetchall():
                cursor.execute("SHOW GRANTS FOR %s@%s",
                               (account["User"], account["Host"]))
                account["permisos"] = [list(row.values())[0] for row in cursor.fetchall()]
                report["cuentas"].append(account)
            cursor.execute(
                "SELECT ROUTINE_NAME, DEFINER, SECURITY_TYPE "
                "FROM information_schema.ROUTINES "
                "WHERE ROUTINE_SCHEMA = DATABASE() ORDER BY ROUTINE_NAME"
            )
            report["definidores_procedimientos"] = cursor.fetchall()
    finally:
        connection.close()
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S-%f")
    destination = root / f"permisos_rds_{stamp}.json"
    with destination.open("x", encoding="utf-8") as output:
        json.dump(report, output, ensure_ascii=False, indent=2, default=str)
    print(f"Informe guardado en {destination}")


if __name__ == "__main__":
    main()
