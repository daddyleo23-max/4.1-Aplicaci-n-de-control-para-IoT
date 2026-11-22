"""Cambio de proxy y pruebas públicas, sin incluir configuración real ni secretos."""
from pathlib import Path
import zipfile
root=Path(__file__).resolve().parents[1]
target=root.parent/'activar_proxy_4_3.zip'
with zipfile.ZipFile(target,'w',zipfile.ZIP_DEFLATED) as z:
    for name in ('gestionar_proxy_4_3.py','probar_publicacion_4_3.py','probar_cierre_4_3_http.py','probar_admin_http.py'):
        z.write(root/'tools'/name,name)
    z.write(root/'docs/proxy-publico-4.3.md','LEEME.md')
    z.writestr('LEEME.txt','''Extraer en C:\\publicacion_4_3. Mantener abiertos Caddy y backends8000/8002.
Desde C:\\practica_2_6_iot ejecutar:
.\\.venv\\Scripts\\python.exe C:\\publicacion_4_3\\gestionar_proxy_4_3.py activar
Este paso cambia API pública a8002 tras respaldar, comparar y validar.
Si falla la comprobación se intenta revertir. Conservar salida y no repetir a ciegas.
Esperado: API HTTPS verificada4.3.0, vehiculo_iot_43, conectadoTrue.
No pide credenciales RDS. Mantener backend8002 y Caddy abiertos tras el éxito.
Enviar resultado para publicar el frontend actualizado en GitHub Pages.
Prueba pública posterior incluida: probar_publicacion_4_3.py (cuenta de aplicación).
Ver LEEME.md para respaldo privado, comportamiento de recarga y reversión.
''')
print(target)
