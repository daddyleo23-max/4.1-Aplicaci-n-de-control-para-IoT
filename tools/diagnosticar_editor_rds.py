"""Reproducir guardado de demo de prueba y mostrar el error SQL con ROLLBACK."""

import argparse
import getpass
import json
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
    from app.config import DB_HOST, DB_PORT, DB_NAME

    if args.copia == DB_NAME:
        raise SystemExit("Se requiere la copia aislada.")
    username = input("Usuario administrador de RDS: ").strip()
    password = getpass.getpass("Contraseña de RDS (entrada oculta): ")
    connection = pymysql.connect(
        host=DB_HOST, port=DB_PORT, database=args.copia,
        user=username, password=password, charset="utf8mb4",
        cursorclass=pymysql.cursors.DictCursor, autocommit=False,
    )
    password = None
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT d.id_demo,d.id_vehiculo,d.nombre,d.descripcion,d.revision,"
                "d.id_propietario FROM demos d JOIN usuarios u "
                "ON u.id_usuario=d.id_propietario "
                "WHERE d.tipo='PRIVADA' AND d.nombre LIKE 'Demo privada prueba %%' "
                "AND u.correo=%s ORDER BY d.id_demo DESC LIMIT 1",
                ("comprador.prueba@example.com",),
            )
            demo = cursor.fetchone()
            if not demo:
                raise SystemExit("No se encontró la demo generada por la prueba.")
            cursor.execute(
                "SELECT id_comando FROM comandos WHERE id_vehiculo=%s "
                "AND nombre='DETENER' AND activo=1", (demo["id_vehiculo"],),
            )
            command = cursor.fetchone()
            if not command:
                raise SystemExit("No se encontró DETENER activo.")
            cursor.execute("SHOW CREATE TABLE demo_movimientos")
            print("Definición de pasos:", cursor.fetchone()["Create Table"])
            cursor.execute("SELECT * FROM demo_movimientos WHERE id_demo=%s ORDER BY orden",
                           (demo["id_demo"],))
            print("Demo:", demo["id_demo"], "revisión:", demo["revision"])
            print("Pasos actuales:", json.dumps(cursor.fetchall(), default=str))
            steps = [
                {"id_comando": command["id_comando"], "duracion_ms": 200, "pausa_ms": 100},
                {"id_comando": command["id_comando"], "duracion_ms": 100, "pausa_ms": 0},
            ]
            try:
                cursor.execute(
                    "CALL sp_editor_guardar_demo(%s,%s,%s,%s,%s,%s,%s,%s)",
                    (demo["id_propietario"], demo["id_demo"], demo["id_vehiculo"],
                     demo["revision"], demo["nombre"], demo["descripcion"], True,
                     json.dumps(steps)),
                )
                print("Resultado:", cursor.fetchall())
                while cursor.nextset():
                    pass
            except pymysql.MySQLError as error:
                print("Código MySQL:", error.args[0])
                print("Detalle MySQL:", error.args[1])
    finally:
        connection.rollback()
        connection.close()
        print("ROLLBACK ejecutado. La prueba no confirma cambios.")


if __name__ == "__main__":
    main()
