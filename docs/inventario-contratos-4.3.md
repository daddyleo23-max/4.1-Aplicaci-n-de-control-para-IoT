# Inventario de contratos antes y después

Antes: lectura estática del ZIP original del alumno. No se ejecutó código ni se leyeron secretos.
Después: contratos del código 4.3. Ver ejemplos en Swagger e informes de prueba.
Las rutas reutilizadas conservan función con autorización por sesión/unidad; las bajas destructivas antiguas se rechazan en modo sesiones.

| Antes: método | Ruta | Estado 4.3 |
| --- | --- | --- |
| GET | `/` | Se reutiliza/modifica con autorización y validaciones |
| GET | `/demos/{id_demo}/movimientos` | Se reutiliza/modifica con autorización y validaciones |
| GET | `/health/db` | Se reutiliza/modifica con autorización y validaciones |
| GET | `/vehiculos` | Se reutiliza/modifica con autorización y validaciones |
| GET | `/vehiculos/{id_vehiculo}` | Se reutiliza/modifica con autorización y validaciones |
| GET | `/vehiculos/{id_vehiculo}/comandos` | Se reutiliza/modifica con autorización y validaciones |
| GET | `/vehiculos/{id_vehiculo}/demos` | Se reutiliza/modifica con autorización y validaciones |
| GET | `/vehiculos/{id_vehiculo}/estado` | Se reutiliza/modifica con autorización y validaciones |
| GET | `/vehiculos/{id_vehiculo}/historial` | Se reutiliza/modifica con autorización y validaciones |
| POST | `/comandos/{id_comando}/actualizar` | Se reutiliza/modifica con autorización y validaciones |
| POST | `/comandos/{id_comando}/eliminar` | Se reutiliza/modifica con autorización y validaciones |
| POST | `/demo-movimientos/{id_demo_movimiento}/actualizar` | Se reutiliza/modifica con autorización y validaciones |
| POST | `/demo-movimientos/{id_demo_movimiento}/eliminar` | Se reutiliza/modifica con autorización y validaciones |
| POST | `/demos/{id_demo}/actualizar` | Se reutiliza/modifica con autorización y validaciones |
| POST | `/demos/{id_demo}/eliminar` | Se reutiliza/modifica con autorización y validaciones |
| POST | `/demos/{id_demo}/movimientos` | Se reutiliza/modifica con autorización y validaciones |
| POST | `/vehiculos` | Se reutiliza/modifica con autorización y validaciones |
| POST | `/vehiculos/{id_vehiculo}/actualizar` | Se reutiliza/modifica con autorización y validaciones |
| POST | `/vehiculos/{id_vehiculo}/comandos` | Se reutiliza/modifica con autorización y validaciones |
| POST | `/vehiculos/{id_vehiculo}/demos` | Se reutiliza/modifica con autorización y validaciones |
| POST | `/vehiculos/{id_vehiculo}/demos/cancelar` | Se reutiliza/modifica con autorización y validaciones |
| POST | `/vehiculos/{id_vehiculo}/demos/{id_demo}/iniciar` | Se reutiliza/modifica con autorización y validaciones |
| POST | `/vehiculos/{id_vehiculo}/eliminar` | Se reutiliza/modifica con autorización y validaciones |
| POST | `/vehiculos/{id_vehiculo}/movimientos` | Se reutiliza/modifica con autorización y validaciones |
| WEBSOCKET | `/ws/vehiculos/{id_vehiculo}` | Se reutiliza/modifica con autorización y validaciones |

Operaciones nuevas: autenticación, administración, propiedad, catálogo, capacidades, soporte, Invitado y reservas. Ver [contratos actuales](contratos-4.3.md).

Fuente original: 25 rutas HTTP/WS detectadas (incluye salud y WebSocket). El enunciado menciona 21 APIs; se informa el conteo real sin forzarlo.

Para cuerpos, parámetros y validaciones de las rutas originales se conserva su contrato en los modelos y routers; la versión actual está exportada en openapi-4.3.json. Los informes reproducibles conservan respuestas y códigos sin tokens.
