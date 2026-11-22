"""Preparación de base/backend público; conserva servicios originales."""
from pathlib import Path
import zipfile

root=Path(__file__).resolve().parents[1]
target=root.parent/'publicacion_4_3.zip'
with zipfile.ZipFile(target,'w',zipfile.ZIP_DEFLATED) as z:
    for name in ('preparar_base_publica_4_3.py','migrar_copia_rds.py','diagnosticar_publicacion_4_3.py'):
        z.write(root/'tools'/name,name)
    for path in sorted((root/'backend/app').rglob('*.py')):
        z.write(path,'backend_publico/'+path.relative_to(root/'backend').as_posix())
    for name in ('iniciar_publicacion.py','requirements.txt'):
        z.write(root/'backend'/name,'backend_publico/'+name)
    z.write(root/'docs/publicacion-4.3.md','LEEME.md')
    z.writestr('LEEME.txt','''Publicación4.3 — primero preparar base definitiva.
Extraer en C:\\publicacion_4_3. Detener SOLO backend de pruebas8001 con Ctrl+C.
Conservar Caddy y backend original8000 funcionando.
Desde C:\\practica_2_6_iot ejecutar:
.\\.venv\\Scripts\\python.exe C:\\publicacion_4_3\\preparar_base_publica_4_3.py --origen "iot_prueba_20261121_205613_303067"
Pide admin/contraseña RDS. Crea vehiculo_iot_43 desde la copia aprobada.
Respalda, restaura y compara datos y estructura; no sobrescribe bases existentes.
No vuelve a aplicar migraciones, no borra datos ni cambia cuentas de aplicación.
Al aprobar, seguir LEEME.md para arrancar backend nuevo8002.
Este paquete aún no recarga Caddy ni publica frontend; prepara su cambio revisable.
''')
print(target)
