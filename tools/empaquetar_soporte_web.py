"""Entrega 018: interfaz de consentimiento y listas de soporte."""
from pathlib import Path
import runpy
import zipfile
from empaquetar_inventario_prueba import build_backend
root=Path(__file__).resolve().parents[1]
runpy.run_path(str(root/'tools/empaquetar_frontend_prueba.py'),run_name='__main__')
backend=build_backend(root)
target=root.parent/'entrega_018_soporte_web.zip'
with zipfile.ZipFile(target,'w',zipfile.ZIP_DEFLATED) as z:
    z.write(root/'sql/migrations/017_listas_soporte_web.up.sql','017_listas_soporte_web.up.sql')
    z.write(root/'tools/migrar_copia_rds.py','migrar_copia_rds.py')
    z.write(root.parent/'frontend_4_3_prueba.zip','frontend_4_3_prueba.zip')
    with zipfile.ZipFile(backend) as source:
        for name in source.namelist():z.writestr('backend/'+name,source.read(name))
    z.writestr('LEEME.txt','''Entrega 018 / SQL017: consentimiento y soporte desde web.
1. Aplicar SQL017 con ejecutor incluido sobre copia con 001–016 verificadas.
Sólo añade dos SP de consulta, sin modificar tablas ni datos históricos.
2. Detener backend8001. Copiar CONTENIDO de backend/ a C:\\practica_4_3_pruebas.
Reiniciar con iniciar_prueba.py --copia NOMBRE_COPIA.
3. Detener frontend8080. Extraer frontend_4_3_prueba.zip en su carpeta y reiniciar.
4. Ctrl+F5. Comprador: Mis vehículos → Autorizar soporte. Seleccionar administrador,
alcance (por defecto SÓLO MONITOREO), 1–30 minutos y Conceder permiso.
5. Otra pestaña/ventana, administrador: Mi cuenta → Soporte autorizado →
Control de soporte → Adquirir control. El permiso operativo es necesario.
6. Comprador: Revocar permiso. El administrador debe perder control/canal.
La prueba de interfaz puede limitarse a adquirir/liberar: no requiere mover.
Monitoreo sigue separado. No hay demos privadas para soporte. La hora de
vencimiento se muestra en Ciudad de México. Actualizar permisos renueva la lista.
No publicar todavía. Credenciales sólo en memoria; sin .env ni claves en ZIP.
''')
print(target)
