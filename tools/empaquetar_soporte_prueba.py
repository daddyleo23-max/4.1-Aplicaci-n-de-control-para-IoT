"""Paquete incremental de consentimiento temporal de diagnóstico."""
from pathlib import Path
import zipfile
from empaquetar_inventario_prueba import build_backend

root = Path(__file__).resolve().parents[1]
backend = build_backend(root)
target = root.parent / 'entrega_014_soporte_diagnostico.zip'
with zipfile.ZipFile(target, 'w', zipfile.ZIP_DEFLATED) as archive:
    archive.write(root/'sql/migrations/013_soporte_diagnostico.up.sql','013_soporte_diagnostico.up.sql')
    for name in ('migrar_copia_rds.py','probar_admin_http.py','probar_soporte_http.py'):
        archive.write(root/'tools'/name,name)
    with zipfile.ZipFile(backend) as source:
        for name in source.namelist():
            archive.writestr('backend/'+name,source.read(name))
    archive.writestr('LEEME.txt', '''Soporte de diagnóstico (entrega 014, migración SQL 013).
Aplicar sólo en copia RDS con migraciones 001 a 012 completas y respaldo verificado.
Aplicar 013 con migrar_copia_rds.py incluido. No repetir ante error parcial.
Detener backend 8001; reemplazar archivos con backend/ e iniciar como antes.
Ejecutar probar_soporte_http.py desde C:\\practica_2_6_iot.
Pide administrador y comprador dueño de unidad 1. No envía movimientos.
El comprador autoriza por 1 minuto al administrador concreto. Revisa REST y
WS y revoca al terminar. Si falla antes, intenta revocar y conserva informe.
Requiere que el administrador no tenga un permiso previo vigente en unidad 1.
Este permiso sólo habilita estado, historial, comandos y WSS; no demos ni
movimientos. No hay nueva interfaz en esta entrega. Soporte operativo y
reserva exclusiva de sesiones de comprador se implementarán posteriormente.
Reversión conservadora: revocar permisos, volver al backend anterior y
conservar tabla/auditoría; no borrar historial ni modificar SP originales.
''')
print(target)
