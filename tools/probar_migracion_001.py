"""Prueba transaccional de migración 001 sobre la copia aislada."""

import argparse
from datetime import datetime, timezone
import getpass
import json
from pathlib import Path
import re
import sys
import uuid


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--copia", required=True)
    args = parser.parse_args()
    if not re.fullmatch(r"iot_prueba_\d{8}_\d{6}_\d{6}", args.copia):
        raise SystemExit("Indica la copia de prueba.")
    root = Path.cwd()
    sys.path.insert(0, str(root))
    import pymysql
    from app.config import DB_HOST, DB_PORT, DB_NAME

    if args.copia == DB_NAME:
        raise SystemExit("Esta prueba requiere una base distinta a la usada por FastAPI.")
    username = input("Usuario administrador de RDS: ").strip()
    password = getpass.getpass("Contraseña de RDS (entrada oculta): ")
    connection = pymysql.connect(
        host=DB_HOST, port=DB_PORT, database=args.copia,
        user=username, password=password, charset="utf8mb4",
        cursorclass=pymysql.cursors.DictCursor, autocommit=False,
    )
    password = None
    results = []
    suffix = uuid.uuid4().hex
    try:
        with connection.cursor() as cursor:
            cursor.execute("SET time_zone = '+00:00'")
            for role in ("ADMINISTRADOR", "USUARIO", "USUARIO"):
                number = len(results)
                cursor.execute(
                    "INSERT INTO usuarios(nombre,correo,password_hash,rol) VALUES(%s,%s,%s,%s)",
                    ("Prueba migración", f"prueba-{suffix}-{number}@example.invalid",
                     "CUENTA_DE_PRUEBA_SIN_HASH_VALIDO", role),
                )
                results.append({"prueba": "Alta transaccional " + role,
                                "correcto": True, "id": cursor.lastrowid})
            admin, buyer_a, buyer_b = [item["id"] for item in results]
            cursor.execute("INSERT INTO modelos(nombre) VALUES(%s)", ("Prueba-" + suffix,))
            model = cursor.lastrowid
            cursor.execute(
                "INSERT INTO vehiculos(nombre,modelo,id_modelo,identificador_unidad) "
                "VALUES(%s,%s,%s,%s)",
                ("Unidad de prueba", "Prueba", model, "PRUEBA-" + suffix),
            )
            vehicle = cursor.lastrowid
            assignment_sql = (
                "INSERT INTO asignaciones(id_vehiculo,id_usuario,asignado_por,inicio_utc) "
                "VALUES(%s,%s,%s,UTC_TIMESTAMP(6))"
            )
            cursor.execute(assignment_sql, (vehicle, buyer_a, admin))
            assignment = cursor.lastrowid
            results.append({"prueba": "Asignación vigente", "correcto": True})
            cursor.execute("SAVEPOINT antes_de_duplicado")
            try:
                cursor.execute(assignment_sql, (vehicle, buyer_b, admin))
            except pymysql.IntegrityError as error:
                if error.args[0] != 1062:
                    raise
                cursor.execute("ROLLBACK TO SAVEPOINT antes_de_duplicado")
                results.append({"prueba": "Segundo propietario vigente rechazado",
                                "correcto": True})
            else:
                raise RuntimeError("Se permitió un segundo propietario vigente.")
            cursor.execute(
                "UPDATE asignaciones SET fin_utc=UTC_TIMESTAMP(6) WHERE id_asignacion=%s",
                (assignment,),
            )
            cursor.execute(assignment_sql, (vehicle, buyer_b, admin))
            results.append({"prueba": "Reasignación tras cerrar propiedad anterior",
                            "correcto": True})
            cursor.execute("CALL sp_obtener_vehiculo(%s)", (vehicle,))
            rows = cursor.fetchall()
            while cursor.nextset():
                pass
            if len(rows) != 1 or rows[0]["id_vehiculo"] != vehicle:
                raise RuntimeError("El procedimiento existente no devolvió la unidad.")
            results.append({"prueba": "Consulta por procedimiento existente",
                            "correcto": True})
    finally:
        connection.rollback()
        connection.close()
    report = {
        "copia": args.copia,
        "fecha_utc": datetime.now(timezone.utc).isoformat(),
        "resultados": results,
        "datos_de_prueba_revertidos": True,
        "nota": "Las secuencias AUTO_INCREMENT pueden avanzar tras ROLLBACK.",
    }
    folder = root / "respaldos_rds"
    folder.mkdir(exist_ok=True)
    destination = folder / f"prueba_001_{suffix}.json"
    with destination.open("x", encoding="utf-8") as output:
        json.dump(report, output, ensure_ascii=False, indent=2)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    print(f"Informe guardado en {destination}")


if __name__ == "__main__":
    main()
