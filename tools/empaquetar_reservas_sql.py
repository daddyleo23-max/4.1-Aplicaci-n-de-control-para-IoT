"""Empaquetar sólo la base SQL 011 y su prueba transaccional."""
from pathlib import Path
import zipfile


def main():
    root = Path(__file__).resolve().parents[1]
    target = root.parent / "entrega_011_reservas_sql.zip"
    with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.write(root / "sql/migrations/011_reservas_invitados.up.sql", "011_reservas_invitados.up.sql")
        for name in ("migrar_copia_rds.py", "probar_reservas_sql.py"):
            archive.write(root / "tools" / name, name)
        archive.writestr("LEEME.txt", """Entrega 011: capa de datos de reservas de Invitado.
Aplicar primero en la copia aislada mediante migrar_copia_rds.py.
Después ejecutar probar_reservas_sql.py --copia NOMBRE_DE_LA_COPIA desde C:\\practica_2_6_iot.
Las credenciales solicitadas son las del administrador de RDS.
La prueba crea datos transaccionales y termina con ROLLBACK.
No envía movimientos ni confirma detención física. AUTO_INCREMENT puede avanzar.
Este paquete no reemplaza backend ni frontend y no habilita control de Invitado.
""")
    print(target)


if __name__ == "__main__":
    main()
