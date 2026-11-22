"""Entrega 019 / SQL018: base de capacidades del modelo."""
from pathlib import Path
import zipfile
root=Path(__file__).resolve().parents[1]
target=root.parent/'entrega_019_capacidades_sql.zip'
with zipfile.ZipFile(target,'w',zipfile.ZIP_DEFLATED) as z:
    z.write(root/'sql/migrations/018_capacidades_modelo.up.sql','018_capacidades_modelo.up.sql')
    for name in ('migrar_copia_rds.py','probar_capacidades_sql.py'):
        z.write(root/'tools'/name,name)
    z.writestr('LEEME.txt','''Entrega 019 / SQL018: capacidades del modelo y comandos de unidad.
Aplicar sólo en copia con 001–017 verificadas, conservando respaldo e informe.
No operar ni ejecutar otras pruebas mientras se compara la conservación.
El ejecutor rechaza unidades sin modelo o códigos/nombres ambiguos ANTES de DDL.
No repetir ante error parcial: compartir informe y salida.
La tabla nueva deriva las capacidades del catálogo actual, sin inventar funciones.
No altera IDs ni filas de comandos, estado, historial ni procedimientos originales.
Probar: probar_capacidades_sql.py --copia NOMBRE_COPIA desde C:\\practica_2_6_iot.
Pide credenciales RDS y usa sólo fixtures nuevas transaccionales con ROLLBACK.
No envía movimientos a ningún hardware. AUTO_INCREMENT puede avanzar.
La edición protege códigos/nombres usados, DETENER activo y reservas en curso.
No incluye cambio de backend ni frontend. La validación de ejecución por
capacidades y los formularios se integrarán tras comprobar este bloque en RDS.
Configurar una capacidad no implementa ni confirma firmware del hardware.
Reversión conservadora: mantener backend anterior y conservar tabla/metadatos;
no eliminar ni volver a numerar comandos o historial.
''')
print(target)
