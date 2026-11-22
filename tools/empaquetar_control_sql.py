"""Entrega 015: base SQL para exclusividad por sesión, sin activar reservas en HTTP."""
from pathlib import Path
import zipfile
root=Path(__file__).resolve().parents[1]
target=root.parent/'entrega_015_reservas_comprador_sql.zip'
with zipfile.ZipFile(target,'w',zipfile.ZIP_DEFLATED) as z:
    z.write(root/'sql/migrations/014_reservas_comprador.up.sql','014_reservas_comprador.up.sql')
    for name in ('migrar_copia_rds.py','probar_control_sql.py','probar_reservas_sql.py'):
        z.write(root/'tools'/name,name)
    z.writestr('LEEME.txt','''Entrega 015: base SQL 014 de reservas por sesión del comprador.
Requiere copia aislada con 001–013 y respaldo verificado; no usar en producción.
Aplicar 014 con migrar_copia_rds.py incluido. No repetir si existe error parcial.
Ejecutar probar_control_sql.py --copia NOMBRE_COPIA desde C:\\practica_2_6_iot.
Pide las credenciales de RDS, crea datos NUEVOS transaccionales y hace ROLLBACK.
No envía peticiones de movimiento ni controla hardware. No crea sesiones permanentes.
Conserva versiones anteriores y verifica regresión de Invitado.
Este paquete NO cambia frontend ni backend. No activa todavía la exclusividad
HTTP/WSS: esa integración requiere otro bloque y pruebas de cierre/DETENER.
La liberación SQL es sólo un protocolo interno: el servicio deberá solicitar
DETENER y cancelar demos ANTES de llamarla. La prueba SQL no acredita parada.
Ante reversión, conservar esquema/historial y usar backend anterior; no borrar
ni reutilizar IDs. Revisar reservas antes de retirar una versión futura del servicio.
''')
print(target)
