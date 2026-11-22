"""Entrega021: gestión de demos de empresa y cierre seguro, sin SQL adicional."""
from pathlib import Path
import runpy
import zipfile
from empaquetar_inventario_prueba import build_backend
root=Path(__file__).resolve().parents[1]
runpy.run_path(str(root/'tools/empaquetar_frontend_prueba.py'),run_name='__main__')
backend=build_backend(root)
target=root.parent/'entrega_021_demos_empresa.zip'
with zipfile.ZipFile(target,'w',zipfile.ZIP_DEFLATED) as z:
    for name in ('probar_admin_http.py','probar_demos_empresa_http.py'):
        z.write(root/'tools'/name,name)
    z.write(root.parent/'frontend_4_3_prueba.zip','frontend_4_3_prueba.zip')
    with zipfile.ZipFile(backend) as source:
        for name in source.namelist():z.writestr('backend/'+name,source.read(name))
    z.writestr('LEEME.txt','''Entrega021: demos de empresa. Requiere copia con SQL001–018; SIN migración nueva.
1. Liberar controles y detener backend8001 con Ctrl+C.
2. Copiar CONTENIDO de backend/ a C:\\practica_4_3_pruebas y reiniciar como antes.
3. Desde C:\\practica_2_6_iot ejecutar probar_demos_empresa_http.py de esta entrega.
Pide sólo administrador de app; crea modelo y unidades NUEVOS de software, sin
hardware. No opera unidad1 ni altera las demos originales de ella.
Verifica tipo EMPRESA, revisiones/orden, permisos tras asignar a comprador,
privacidad de demos privadas, fin con solicitud DETENER sin historial de pasos
y prioridad de DETENER durante demo de empresa. No confirma ejecución física.
Modelo privado/unidad asignada se conservan por auditoría; compradores nuevos
se desactivan. La unidad secundaria no asignada queda inactiva.
4. Tras aprobar, detener frontend8080, extraer su ZIP en su carpeta y reiniciar.
Ctrl+F5. Administrador → Demos de empresa → unidad activa sin comprador → editor.
Comprador consulta EMPRESA de sólo lectura y crea/edita PRIVADA en su unidad.
Las demos inactivas no ofrecen Seleccionar en control. El editor muestra
estado vacío si no existen comandos compatibles habilitados.
El fin normal emite demo_fin sólo tras procesar solicitud DETENER; los pasos y
ese cierre no se insertan en historial individual. El STOP manual sí se registra.
No hay cambios de firmware ni publicación automática en GitHub Pages.
''')
print(target)
