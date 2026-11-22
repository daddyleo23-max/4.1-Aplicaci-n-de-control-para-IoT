"""Entrega 012: API de Invitado para probar en localhost y copia RDS."""
from pathlib import Path
import zipfile

from empaquetar_inventario_prueba import build_backend


def main():
    root = Path(__file__).resolve().parents[1]
    backend = build_backend(root)
    target = root.parent / "entrega_012_invitados_api.zip"
    with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.write(root / "sql/migrations/012_api_invitados.up.sql", "012_api_invitados.up.sql")
        for name in ("migrar_copia_rds.py", "probar_admin_http.py", "probar_invitados_http.py"):
            archive.write(root / "tools" / name, name)
        with zipfile.ZipFile(backend) as source:
            for name in source.namelist():
                archive.writestr("backend/" + name, source.read(name))
        archive.writestr("LEEME.txt", """Entrega 012: API de Invitado, todavía sin nueva interfaz.
1. Aplicar SQL 012 con el ejecutor sobre la copia aislada, conservando el informe.
2. Actualizar C:\\practica_4_3_pruebas con backend y reiniciar en 8001.
3. Ejecutar probar_invitados_http.py desde C:\\practica_2_6_iot.
El test pide el administrador de la aplicación. Crea una unidad NUEVA sin
hardware, prueba peticiones/eventos y deja sus registros privados e inactivos.
No controla el montacargas 1. No demuestra recepción ni parada física.
Mantener un único proceso Uvicorn, como en iniciar_prueba.py.
El frontend permanece en la versión anterior hasta validar esta API.
""")
    print(target)


if __name__ == "__main__":
    main()
