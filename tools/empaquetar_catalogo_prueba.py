"""Preparar catálogo 010 para probar exclusivamente en el entorno aislado."""
from pathlib import Path
import runpy
import zipfile

from empaquetar_inventario_prueba import build_backend


def main():
    root = Path(__file__).resolve().parents[1]
    runpy.run_path(str(root / "tools/empaquetar_frontend_prueba.py"), run_name="__main__")
    backend_path = build_backend(root)
    target = root.parent / "entrega_010_catalogo.zip"
    with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.write(root / "sql/migrations/010_catalogo_publico.up.sql", "010_catalogo_publico.up.sql")
        for name in ("migrar_copia_rds.py", "probar_admin_http.py", "probar_catalogo_http.py"):
            archive.write(root / "tools" / name, name)
        with zipfile.ZipFile(backend_path) as backend:
            for name in backend.namelist():
                archive.writestr("backend/" + name, backend.read(name))
        archive.write(root.parent / "frontend_4_3_prueba.zip", "frontend_4_3_prueba.zip")
    print(target)


if __name__ == "__main__":
    main()
