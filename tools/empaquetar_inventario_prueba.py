"""Preparar la entrega 009 sin incluir secretos, respaldos ni bytecode."""
from pathlib import Path
import runpy
import zipfile


def build_backend(root):
    backend_target = root.parent / "backend_4_3_prueba.zip"
    with zipfile.ZipFile(backend_target, "w", zipfile.ZIP_DEFLATED) as archive:
        for path in sorted((root / "backend").rglob("*")):
            if path.is_file() and (path.suffix == ".py" or path.name in {"requirements.txt", "README.md"}):
                archive.write(path, path.relative_to(root / "backend").as_posix())
    return backend_target


def main():
    root = Path(__file__).resolve().parents[1]
    runpy.run_path(str(root / "tools/empaquetar_frontend_prueba.py"), run_name="__main__")
    backend_target = build_backend(root)
    target = root.parent / "entrega_009_inventario.zip"
    with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.write(root / "sql/migrations/009_inventario_unidades.up.sql", "009_inventario_unidades.up.sql")
        for name in ("migrar_copia_rds.py", "probar_admin_http.py", "probar_inventario_http.py"):
            archive.write(root / "tools" / name, name)
        with zipfile.ZipFile(backend_target) as backend:
            for name in backend.namelist():
                archive.writestr("backend/" + name, backend.read(name))
        archive.write(root.parent / "frontend_4_3_prueba.zip", "frontend_4_3_prueba.zip")
    print(target)


if __name__ == "__main__":
    main()
