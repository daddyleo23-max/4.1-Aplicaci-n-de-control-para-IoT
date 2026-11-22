"""Entrega 016: API de reserva exclusiva del comprador en copia RDS."""
from pathlib import Path
import zipfile
from empaquetar_inventario_prueba import build_backend
root=Path(__file__).resolve().parents[1]
backend=build_backend(root)
target=root.parent/'entrega_016_control_api.zip'
with zipfile.ZipFile(target,'w',zipfile.ZIP_DEFLATED) as z:
    z.write(root/'sql/migrations/015_api_control_comprador.up.sql','015_api_control_comprador.up.sql')
    for name in ('migrar_copia_rds.py','probar_admin_http.py','probar_control_http.py','probar_invitados_http.py'):
        z.write(root/'tools'/name,name)
    with zipfile.ZipFile(backend) as source:
        for name in source.namelist():z.writestr('backend/'+name,source.read(name))
    z.writestr('LEEME.txt','''Entrega 016 / SQL 015: exclusividad operativa del comprador.
1. Aplicar SQL 015 en copia con 001–014 validadas y respaldo verificado.
2. Detener backend 8001. Copiar CONTENIDO de backend/ a C:\\practica_4_3_pruebas.
3. Reiniciar con iniciar_prueba.py --copia NOMBRE_COPIA. Un solo proceso Uvicorn.
4. Desde C:\\practica_2_6_iot ejecutar probar_control_http.py.
Pide sólo administrador de la aplicación. Crea un comprador y una unidad NUEVOS
sin hardware y comprueba movimientos/eventos y caducidad real (unos 45 s).
Nunca asocia hardware al identificador CTL generado ni mueve la unidad 1.
El modelo privado y la unidad asignada se conservan por historial. El comprador
nuevo se desactiva al terminar; el informe no guarda tokens ni contraseñas.
No interrumpir mientras verifica la caducidad. Si falla conservar informe y salida.
No incluye frontend actualizado: el comprador requiere reservar y conectar
/ws/control/{id_control}; la web anterior aún no hace ese recorrido y recibirá
409 al intentar mover. El monitoreo sigue disponible. Tras validar la API se
integra la reserva en la interfaz. No publicar esta etapa en GitHub Pages.
Nuevas rutas:
GET /vehiculos/{id}/control
POST /vehiculos/{id}/control/reservar
POST /control/{id_control}/cerrar
WS /ws/control/{id_control}: primer mensaje autenticar/token; renovar cada <45 s.
Sólo la sesión titular con canal conectado puede mover/iniciar/cancelar demos.
Cierre procesa cancelación de demo y DETENER antes de liberar; fallo conserva
DETENIENDO. El worker reintenta y recupera reservas al arrancar. Ningún evento
confirma recepción física: el firmware debe imponer sus propios límites seguros.
Reversión: cerrar y verificar ausencia de reservas del comprador ANTES de volver
al backend anterior. Conservar SQL/historial; no DROP ni liberaciones manuales.
''')
print(target)
