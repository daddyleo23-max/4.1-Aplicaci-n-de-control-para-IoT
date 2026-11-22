"""Entrega 017 / SQL016: soporte operativo consentido y exclusivo."""
from pathlib import Path
import zipfile
from empaquetar_inventario_prueba import build_backend
root=Path(__file__).resolve().parents[1]
backend=build_backend(root)
target=root.parent/'entrega_017_soporte_operativo.zip'
with zipfile.ZipFile(target,'w',zipfile.ZIP_DEFLATED) as z:
    z.write(root/'sql/migrations/016_soporte_operativo.up.sql','016_soporte_operativo.up.sql')
    for name in ('migrar_copia_rds.py','probar_admin_http.py','probar_soporte_operativo_http.py'):
        z.write(root/'tools'/name,name)
    with zipfile.ZipFile(backend) as source:
        for name in source.namelist():z.writestr('backend/'+name,source.read(name))
    z.writestr('LEEME.txt','''Entrega 017 / SQL 016: soporte operativo explícito, primero sobre copia.
1. Liberar reservas en la aplicación y detener backend 8001 con Ctrl+C.
2. Aplicar 016 con migrar_copia_rds.py incluido sobre copia con 001–015 validadas.
El ejecutor rechaza reservas activas. Si falla DDL no repetir: revisar informe.
Se agregan columnas y se reemplazan SÓLO las rutinas de control añadidas en 014.
Se conservan las 21 originales. No requiere nuevos triggers ni privilegios.
3. Copiar CONTENIDO de backend/ a C:\\practica_4_3_pruebas y reiniciar 8001.
4. Ejecutar probar_soporte_operativo_http.py desde C:\\practica_2_6_iot.
Pide sólo administrador de la aplicación. Crea comprador, modelo privado y
unidad NUEVOS sin hardware; no opera unidad 1. Comprueba exclusividad,
revocación, desconexión y caducidad real de 1 minuto mientras renueva WS.
Conserva unidad asignada/modelo privados por historial y desactiva comprador.
No publica tokens ni contraseñas en el informe. No confirma movimiento físico.
API soporte existente: POST /vehiculos/{id}/soporte admite operativo=true
explícito; omitirlo conserva MONITOREO. Sólo el dueño puede conceder/revocar.
Permiso limitado al administrador y asignación elegidos, 1–30 minutos.
Reserva/canal/renovación/cierre usan las mismas rutas del comprador.
Permite movimientos manuales, NO demos privadas ni edición ni cambio de dueño.
Retirar/expirar el consentimiento invalida SQL y provoca cierre/DETENER.
No incluye nueva interfaz: tras validar API se integrará consentimiento web.
La interfaz del comprador de la entrega anterior sigue funcionando.
Mantener un proceso Uvicorn. No publicar aún en GitHub Pages.
Reversión conservadora: cerrar todas las reservas, revocar permisos operativos
y volver al backend anterior manteniendo columnas/historial. No DROP automático.
''')
print(target)
