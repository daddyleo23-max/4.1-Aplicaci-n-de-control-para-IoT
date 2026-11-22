"""Paquete específico para el estado parcial 019; no contiene datos ni secretos."""
from pathlib import Path
import zipfile


def main():
    root=Path(__file__).resolve().parents[1]
    target=root.parent/'recuperacion_019_mysql.zip'
    with zipfile.ZipFile(target,'w',zipfile.ZIP_DEFLATED) as z:
        for name in ('recuperar_control_019.py','migrar_copia_rds.py','probar_control_empresa_sql.py'):
            z.write(root/'tools'/name,name)
        z.write(root/'tools/fuentes_recuperacion_019/019_original.sql','fuentes_recuperacion_019/019_original.sql')
        for name in ('015_api_control_comprador.up.sql','016_soporte_operativo.up.sql'):
            z.write(root/'sql/migrations'/name,'fuentes_recuperacion_019/'+name)
        for name in ('019_control_empresa.up.sql','020_catalogo_resumen.up.sql'):
            z.write(root/'sql/migrations'/name,name)
        z.write(root/'docs/recuperacion-019.md','LEEME.md')
        z.writestr('LEEME.txt','''Reparación del estado parcial 019. Extraer en C:\\recuperacion_019.
Mantener backend detenido. Ejecutar desde C:\\practica_2_6_iot:
.\\.venv\\Scripts\\python.exe C:\\recuperacion_019\\recuperar_control_019.py --copia "iot_prueba_20261121_205613_303067" --informe "C:\\practica_2_6_iot\\respaldos_rds\\migracion_019_20261122-182248-235666.json" --aplicar
Pide admin y contraseña de RDS, no el correo de la aplicación.
Valida el estado conocido antes de ejecutar DDL. No desactiva llaves foráneas.
No repetir la migración original 019. No ejecutar020 ni pruebas si falla.
Conservar respaldo previo SQL y manifiesto. Ver LEEME.md para detalles.
''')
    print(target)

if __name__=='__main__':main()
