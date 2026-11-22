"""Entrega020: capacidades integradas; usa SQL018 ya validada, sin migración nueva."""
from pathlib import Path
import runpy
import zipfile
from empaquetar_inventario_prueba import build_backend
root=Path(__file__).resolve().parents[1]
runpy.run_path(str(root/'tools/empaquetar_frontend_prueba.py'),run_name='__main__')
backend=build_backend(root)
target=root.parent/'entrega_020_capacidades_web.zip'
with zipfile.ZipFile(target,'w',zipfile.ZIP_DEFLATED) as z:
    for name in ('probar_admin_http.py','probar_capacidades_http.py','probar_control_http.py','probar_invitados_http.py','probar_soporte_operativo_http.py','preparar_invitado_web.py'):
        z.write(root/'tools'/name,name)
    z.write(root.parent/'frontend_4_3_prueba.zip','frontend_4_3_prueba.zip')
    with zipfile.ZipFile(backend) as source:
        for name in source.namelist():z.writestr('backend/'+name,source.read(name))
    z.writestr('LEEME.txt','''Entrega020: API e interfaz de capacidades. Requiere SQL018 validada.
NO necesita otra migración. Primero probar backend, después sustituir frontend.
1. Liberar controles y detener backend8001 con Ctrl+C.
2. Copiar CONTENIDO de backend/ a C:\\practica_4_3_pruebas y reiniciar como antes.
3. Desde C:\\practica_2_6_iot ejecutar probar_capacidades_http.py de esta entrega.
Pide administrador de app; crea modelos/unidad NUEVOS sin hardware, comprueba
permisos, desactivación, rechazo de demos/movimientos y preservación de IDs.
No opera unidad1. Al terminar conserva historial privado con registros inactivos.
4. Tras aprobar, detener frontend8080, extraer su ZIP en su carpeta y reiniciar.
Ctrl+F5. Administración → Modelos → Capacidades. Unidades → Comandos.
No renombrar códigos usados para simular funciones no implementadas en hardware.
Los comandos se agregan desde capacidades reales del modelo, sin copiar IDs.
Las rutas POST anteriores mantienen sus cuerpos/respuestas y exigen capacidad
previamente configurada. No crean funciones ajenas al modelo ni alteran códigos.
Los scripts anteriores de fixtures que crean modelos nuevos deben crear primero
sus capacidades. Se incluyen actualizados para la nueva API; no usar versiones
antiguas de entregas anteriores contra este backend para crear esas fixtures.
La validación se aplica al movimiento y a las demos (editor/inicio/cada paso)
y al pulso Invitado en la transacción de escritura. DETENER conserva prioridad.
La actualización no confirma funciones ni parada físicas del firmware.
Mantener un proceso Uvicorn y no publicar aún en GitHub Pages.
''')
print(target)
