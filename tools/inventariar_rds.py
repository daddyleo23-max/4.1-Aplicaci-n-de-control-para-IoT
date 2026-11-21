"""Ejecutar desde la raíz del backend, junto a la carpeta app."""

import json
import argparse
import getpass
import sys
from datetime import datetime, timezone
from pathlib import Path


def main():
    root = Path.cwd()
    if not (root / "app" / "database.py").is_file():
        print("Ejecuta este script desde la carpeta que contiene app/database.py.")
        return 1
    sys.path.insert(0, str(root))
    from app.database import get_connection
    parser = argparse.ArgumentParser(description="Consultar metadatos de RDS.")
    parser.add_argument("--administrador", action="store_true",
                        help="Usar temporalmente una cuenta con acceso al esquema.")
    arguments = parser.parse_args()

    queries = {
        "servidor": "SELECT DATABASE() AS esquema, VERSION() AS version_mysql",
        "tablas": """SELECT TABLE_NAME, TABLE_TYPE, ENGINE
            FROM information_schema.TABLES WHERE TABLE_SCHEMA = DATABASE()
            ORDER BY TABLE_NAME""",
        "columnas": """SELECT TABLE_NAME, ORDINAL_POSITION, COLUMN_NAME,
            COLUMN_TYPE, IS_NULLABLE, COLUMN_DEFAULT, COLUMN_KEY, EXTRA
            FROM information_schema.COLUMNS WHERE TABLE_SCHEMA = DATABASE()
            ORDER BY TABLE_NAME, ORDINAL_POSITION""",
        "relaciones": """SELECT TABLE_NAME, CONSTRAINT_NAME, COLUMN_NAME,
            REFERENCED_TABLE_NAME, REFERENCED_COLUMN_NAME
            FROM information_schema.KEY_COLUMN_USAGE
            WHERE TABLE_SCHEMA = DATABASE()
            ORDER BY TABLE_NAME, CONSTRAINT_NAME, ORDINAL_POSITION""",
        "indices": """SELECT TABLE_NAME, INDEX_NAME, NON_UNIQUE,
            SEQ_IN_INDEX, COLUMN_NAME FROM information_schema.STATISTICS
            WHERE TABLE_SCHEMA = DATABASE()
            ORDER BY TABLE_NAME, INDEX_NAME, SEQ_IN_INDEX""",
        "procedimientos": """SELECT ROUTINE_NAME, ROUTINE_TYPE,
            SQL_DATA_ACCESS, SECURITY_TYPE, ROUTINE_DEFINITION
            FROM information_schema.ROUTINES WHERE ROUTINE_SCHEMA = DATABASE()
            ORDER BY ROUTINE_NAME""",
        "parametros": """SELECT SPECIFIC_NAME, ORDINAL_POSITION,
            PARAMETER_MODE, PARAMETER_NAME, DTD_IDENTIFIER
            FROM information_schema.PARAMETERS
            WHERE SPECIFIC_SCHEMA = DATABASE()
            ORDER BY SPECIFIC_NAME, ORDINAL_POSITION""",
        "vistas": """SELECT TABLE_NAME, VIEW_DEFINITION
            FROM information_schema.VIEWS WHERE TABLE_SCHEMA = DATABASE()
            ORDER BY TABLE_NAME""",
        "triggers": """SELECT TRIGGER_NAME, EVENT_MANIPULATION,
            EVENT_OBJECT_TABLE, ACTION_TIMING, ACTION_STATEMENT
            FROM information_schema.TRIGGERS
            WHERE TRIGGER_SCHEMA = DATABASE() ORDER BY TRIGGER_NAME""",
        "restricciones": """SELECT tc.TABLE_NAME, tc.CONSTRAINT_NAME,
            cc.CHECK_CLAUSE
            FROM information_schema.TABLE_CONSTRAINTS AS tc
            JOIN information_schema.CHECK_CONSTRAINTS AS cc
              ON cc.CONSTRAINT_SCHEMA = tc.CONSTRAINT_SCHEMA
             AND cc.CONSTRAINT_NAME = tc.CONSTRAINT_NAME
            WHERE tc.CONSTRAINT_SCHEMA = DATABASE()
            ORDER BY tc.TABLE_NAME, tc.CONSTRAINT_NAME""",
    }
    result = {"generado_utc": datetime.now(timezone.utc).isoformat()}
    if arguments.administrador:
        import pymysql
        from app.config import DB_HOST, DB_PORT, DB_NAME

        username = input("Usuario administrador de RDS: ").strip()
        password = getpass.getpass("Contraseña de RDS (entrada oculta): ")
        connection = pymysql.connect(
            host=DB_HOST, port=DB_PORT, database=DB_NAME,
            user=username, password=password, charset="utf8mb4",
            cursorclass=pymysql.cursors.DictCursor, connect_timeout=5,
        )
        password = None
    else:
        connection = get_connection()
    try:
        with connection.cursor() as cursor:
            for name, query in queries.items():
                cursor.execute(query)
                result[name] = cursor.fetchall()
                print(f"{name}: {len(result[name])} registros de metadatos")
            if not result["tablas"]:
                print("AVISO: inventario incompleto. Esta cuenta no ve tablas.")
                print("Repite con --administrador y una cuenta con acceso al esquema.")
            result["ddl_tablas"] = []
            for table in result["tablas"]:
                if table["TABLE_TYPE"] != "BASE TABLE":
                    continue
                name = table["TABLE_NAME"].replace("`", "``")
                cursor.execute("SHOW CREATE TABLE `" + name + "`")
                definition = cursor.fetchone()
                result["ddl_tablas"].append({
                    "tabla": table["TABLE_NAME"],
                    "ddl": definition["Create Table"],
                })
            print(f"ddl_tablas: {len(result['ddl_tablas'])} definiciones")
    finally:
        connection.close()

    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S-%f")
    destination = root / f"inventario_rds_{stamp}.json"
    with destination.open("x", encoding="utf-8") as output:
        json.dump(result, output, ensure_ascii=False, indent=2, default=str)
    print(f"Inventario guardado en {destination}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
