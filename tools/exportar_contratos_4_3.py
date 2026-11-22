"""Exporta contratos del código sin conectar a RDS ni incluir credenciales."""
import json
from pathlib import Path
import sys
root=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(root/'backend'))
from app.main import app
schema=app.openapi()
folder=root/'docs';folder.mkdir(exist_ok=True)
(folder/'openapi-4.3.json').write_text(json.dumps(schema,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
lines=['# Contratos HTTP 4.3','',
       'Generados del código. Swagger contiene parámetros, cuerpos, esquemas y respuestas.',
       'La autorización por unidad también se aplica en dependencias; un candado de Swagger no sustituye probar el acceso.',
       'La ejecución real sobre RDS y la URL pública se registra por separado.','',
       '| Método | Ruta | Operación |','| --- | --- | --- |']
for path,methods in schema['paths'].items():
 for method,operation in methods.items():
  if method.upper() in {'GET','POST','PUT','PATCH','DELETE'}:
   lines.append(f"| {method.upper()} | `{path}` | {operation.get('summary','')} |")
lines+=['','## Canales WS','',
        '| Canal | Identidad y uso |','| --- | --- |',
        '| `/ws/vehiculos/{id}` | Autenticar token; propietario, empresa sobre inventario o soporte diagnóstico autorizado. Estado inicial/eventos; no concede reserva de control. |',
        '| `/ws/control/{id_control}` | Autenticar token del titular; un canal por reserva; `renovar` mantiene vigencia mientras identidad y permiso sigan vigentes. |',
        '| `/ws/invitados` | Autenticar token temporal; sólo unidad reservada y comandos de exhibición. |','',
        'Verificar la ruta de Invitado en el router y usar los scripts entregados; nunca enviar tokens en la URL.']
# Derive guest websocket path from the actual router, avoiding a guessed contract.
from app.routers.invitados import router
for route in router.routes:
 if route.__class__.__name__=='APIWebSocketRoute':
  lines=[line.replace('/ws/invitados',route.path) for line in lines]
(folder/'contratos-4.3.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
print('Contratos guardados en docs/contratos-4.3.md y docs/openapi-4.3.json')
