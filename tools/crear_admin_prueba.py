"""Comprobar sesiones y crear el primer administrador en la copia de RDS."""

import argparse
from datetime import datetime, timedelta, timezone
import getpass
import hashlib
import re
import secrets
import sys
from pathlib import Path


def call(cursor, procedure, parameters):
    cursor.execute(
        "CALL " + procedure + "(" + ", ".join(["%s"] * len(parameters)) + ")",
        parameters,
    )
    rows = cursor.fetchall()
    while cursor.nextset():
        pass
    return rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--copia", required=True)
    args = parser.parse_args()
    if not re.fullmatch(r"iot_prueba_\d{8}_\d{6}_\d{6}", args.copia):
        raise SystemExit("Indica la base de prueba restaurada.")
    sys.path.insert(0, str(Path.cwd()))
    import pymysql
    from app.config import DB_HOST, DB_PORT, DB_NAME

    if args.copia == DB_NAME:
        raise SystemExit("Se requiere una copia diferente a la base de FastAPI.")
    db_user = input("Usuario administrador de RDS: ").strip()
    db_password = getpass.getpass("Contraseña de RDS (entrada oculta): ")
    connection = pymysql.connect(
        host=DB_HOST, port=DB_PORT, database=args.copia,
        user=db_user, password=db_password, charset="utf8mb4",
        cursorclass=pymysql.cursors.DictCursor, autocommit=False,
    )
    db_password = None
    try:
        with connection.cursor() as cursor:
            cursor.execute("SET time_zone = '+00:00'")
            cursor.execute(
                "SELECT version FROM migraciones_iot "
                "WHERE version='002_sesiones_auditoria'"
            )
            if not cursor.fetchone():
                raise SystemExit("Falta la migración 002.")
            cursor.execute("SELECT id_usuario FROM usuarios WHERE rol='ADMINISTRADOR' LIMIT 1")
            if cursor.fetchone():
                raise SystemExit("Ya existe un administrador. Se conservó la cuenta existente.")

            name = input("Nombre del administrador de la aplicación: ").strip()
            email = input("Correo para iniciar sesión: ").strip().lower()
            if not 1 <= len(name) <= 120 or not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", email) or len(email) > 254:
                raise SystemExit("Nombre o correo inválido.")
            password = getpass.getpass("Nueva contraseña de la aplicación (mínimo 12 caracteres): ")
            confirmation = getpass.getpass("Repite la nueva contraseña: ")
            if password != confirmation or not 12 <= len(password) <= 256:
                raise SystemExit("Las contraseñas deben coincidir y tener de 12 a 256 caracteres.")
            salt = secrets.token_bytes(16)
            digest = hashlib.scrypt(password.encode("utf-8"), salt=salt, n=16384, r=8, p=1)
            encoded = "scrypt$16384$8$1$" + salt.hex() + "$" + digest.hex()
            password = confirmation = None
            cursor.execute(
                "INSERT INTO usuarios(nombre,correo,password_hash,rol) "
                "VALUES(%s,%s,%s,'ADMINISTRADOR')", (name, email, encoded),
            )
            user_id = cursor.lastrowid
            token_digest = hashlib.sha256(secrets.token_bytes(32)).digest()
            expires = (datetime.now(timezone.utc) + timedelta(hours=1)).replace(tzinfo=None)
            created = call(cursor, "sp_auth_crear_sesion", (user_id, token_digest, expires))
            if not created or created[0]["creadas"] != 1:
                raise RuntimeError("Falló la creación de sesión.")
            rows = call(cursor, "sp_auth_obtener_sesion", (token_digest,))
            if len(rows) != 1 or rows[0]["id_usuario"] != user_id:
                raise RuntimeError("Falló la lectura de sesión válida.")
            session_id = rows[0]["id_sesion"]
            call(cursor, "sp_auth_revocar_sesion", (session_id,))
            if call(cursor, "sp_auth_obtener_sesion", (token_digest,)):
                raise RuntimeError("La sesión revocada sigue autorizada.")
            print("Prueba SQL: creación, lectura y revocación de sesión correctas.")
            cursor.execute(
                "INSERT INTO auditoria(id_actor,accion,tipo_recurso,id_recurso,resultado,fecha_utc) "
                "VALUES(%s,'CREAR_ADMIN_INICIAL','usuario',%s,'ACEPTADO',UTC_TIMESTAMP(6))",
                (user_id, str(user_id)),
            )
        connection.commit()
        print(f"Administrador de la aplicación creado en {args.copia}.")
        print("La sesión de comprobación quedó revocada.")
        print("Siguiente paso: probar login HTTP en el backend aislado de 4.3.")
    except BaseException:
        connection.rollback()
        raise
    finally:
        connection.close()


if __name__ == "__main__":
    main()
