"""Genera respaldo SQL mediante mysqldump desde la raíz del backend."""

import argparse
import getpass
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from datetime import datetime, timezone


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mysqldump", help="Ruta al ejecutable mysqldump.exe")
    args = parser.parse_args()
    root = Path.cwd()
    if not (root / "app" / "config.py").is_file():
        raise SystemExit("Ejecuta desde la raíz del backend, junto a app.")

    executable = args.mysqldump or shutil.which("mysqldump")
    if not executable:
        candidates = sorted(Path("C:/Program Files/MySQL").glob("*/bin/mysqldump.exe"))
        if candidates:
            executable = str(candidates[-1])
    if not executable:
        raise SystemExit(
            "No se encontró mysqldump. Indica su ruta con --mysqldump "
            "o instala las herramientas oficiales del cliente MySQL."
        )

    sys.path.insert(0, str(root))
    from app.config import DB_HOST, DB_PORT, DB_NAME

    username = input("Usuario administrador de RDS: ").strip()
    password = getpass.getpass("Contraseña de RDS (entrada oculta): ")
    folder = root / "respaldos_rds"
    folder.mkdir(exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S-%f")
    temporary = folder / f"{DB_NAME}_{stamp}.sql.incompleto"
    destination = temporary.with_suffix("")
    child_environment = os.environ.copy()
    child_environment["MYSQL_PWD"] = password
    password = None
    command = [
        executable, "--host", DB_HOST, "--port", str(DB_PORT),
        "--user", username, "--single-transaction", "--quick",
        "--routines", "--triggers", "--events", "--hex-blob",
        "--no-tablespaces", "--set-gtid-purged=OFF",
        "--default-character-set=utf8mb4", DB_NAME,
    ]
    try:
        with temporary.open("xb") as output:
            result = subprocess.run(command, stdout=output, stderr=subprocess.PIPE,
                                    env=child_environment, check=False)
    finally:
        child_environment.pop("MYSQL_PWD", None)
    if result.returncode:
        print(result.stderr.decode("utf-8", errors="replace"))
        raise SystemExit(
            f"Respaldo fallido. Archivo incompleto conservado en {temporary}"
        )
    if temporary.stat().st_size == 0:
        raise SystemExit("El archivo generado está vacío. Revisa el cliente MySQL.")
    temporary.rename(destination)
    digest = hashlib.sha256()
    with destination.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    manifest = {
        "archivo": destination.name,
        "esquema": DB_NAME,
        "generado_utc": datetime.now(timezone.utc).isoformat(),
        "bytes": destination.stat().st_size,
        "sha256": digest.hexdigest(),
        "restauracion_verificada": False,
    }
    with destination.with_suffix(".manifest.json").open("x", encoding="utf-8") as output:
        json.dump(manifest, output, ensure_ascii=False, indent=2)
    print(f"Respaldo generado en {destination}")
    print("Conserva SQL y manifiesto en almacenamiento privado.")
    print("Pendiente: restaurar en una copia aislada y comparar datos.")


if __name__ == "__main__":
    main()
