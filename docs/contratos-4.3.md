# Contratos HTTP 4.3

Generados del código. Swagger contiene parámetros, cuerpos, esquemas y respuestas.
La autorización por unidad también se aplica en dependencias; un candado de Swagger no sustituye probar el acceso.
La ejecución real sobre RDS y la URL pública se registra por separado.

| Método | Ruta | Operación |
| --- | --- | --- |
| GET | `/` | Inicio |
| GET | `/vehiculos` | Obtener Vehiculos |
| POST | `/vehiculos` | Crear vehículo |
| GET | `/vehiculos/{id_vehiculo}` | Obtener vehículo por ID |
| POST | `/vehiculos/{id_vehiculo}/actualizar` | Actualizar vehículo |
| POST | `/vehiculos/{id_vehiculo}/eliminar` | Eliminar vehículo |
| GET | `/vehiculos/{id_vehiculo}/comandos` | Obtener Comandos |
| POST | `/vehiculos/{id_vehiculo}/comandos` | Crear comando |
| GET | `/vehiculos/{id_vehiculo}/estado` | Obtener Estado |
| POST | `/comandos/{id_comando}/actualizar` | Actualizar comando |
| POST | `/comandos/{id_comando}/eliminar` | Eliminar comando |
| GET | `/vehiculos/{id_vehiculo}/historial` | Obtener Historial |
| GET | `/vehiculos/{id_vehiculo}/demos` | Obtener Demos |
| POST | `/vehiculos/{id_vehiculo}/demos` | Crear demo |
| GET | `/demos/{id_demo}/movimientos` | Obtener Movimientos Demo |
| POST | `/demos/{id_demo}/movimientos` | Agregar movimiento a demo |
| POST | `/vehiculos/{id_vehiculo}/demos/{id_demo}/iniciar` | Iniciar Demo |
| POST | `/vehiculos/{id_vehiculo}/demos/cancelar` | Cancelar Demo |
| POST | `/demos/{id_demo}/actualizar` | Actualizar demo |
| POST | `/demos/{id_demo}/eliminar` | Eliminar demo |
| POST | `/demo-movimientos/{id_demo_movimiento}/actualizar` | Actualizar movimiento de demo |
| POST | `/demo-movimientos/{id_demo_movimiento}/eliminar` | Eliminar movimiento de demo |
| POST | `/vehiculos/{id_vehiculo}/movimientos` | Registrar Movimiento |
| POST | `/auth/login` | Iniciar sesión de aplicación |
| GET | `/auth/me` | Me |
| POST | `/auth/logout` | Logout |
| GET | `/admin/resumen` | Summary |
| GET | `/admin/modelos` | Models |
| POST | `/admin/modelos` | Create Model |
| GET | `/admin/clientes` | Clients |
| POST | `/admin/clientes` | Create Client |
| GET | `/admin/unidades` | Units |
| POST | `/admin/unidades` | Create Unit |
| POST | `/admin/unidades/{id_vehiculo}/configurar` | Configure Unit |
| POST | `/admin/unidades/{id_vehiculo}/actualizar` | Update Unit |
| POST | `/admin/unidades/{id_vehiculo}/asignar` | Assign Unit |
| POST | `/admin/unidades/{id_vehiculo}/exhibicion` | Set Exhibition |
| POST | `/admin/modelos/{id_modelo}/actualizar` | Update Model |
| POST | `/admin/modelos/{id_modelo}/publicacion` | Publish Model |
| POST | `/admin/clientes/{id_usuario}/actualizar` | Update Client |
| GET | `/admin/auditoria` | Audit |
| GET | `/mis-vehiculos` | My Vehicles |
| GET | `/mis-demos` | List Demos |
| POST | `/mis-demos` | Create Demo |
| GET | `/mis-demos/{id_demo}` | Get Demo |
| POST | `/mis-demos/{id_demo}/guardar` | Update Demo |
| GET | `/catalogo` | Catalog |
| GET | `/admin/unidades/{id_vehiculo}/invitados` | Configuration |
| POST | `/admin/unidades/{id_vehiculo}/invitados` | Configure |
| POST | `/admin/unidades/{id_vehiculo}/invitados/cerrar` | Admin Close |
| GET | `/catalogo/{id_modelo}/unidades` | Exhibition Units |
| POST | `/invitados/sesiones` | Reserve |
| GET | `/invitados/sesion` | Current |
| POST | `/invitados/movimientos` | Move |
| POST | `/invitados/sesion/cerrar` | Close |
| POST | `/vehiculos/{id_vehiculo}/soporte` | Grant |
| GET | `/vehiculos/{id_vehiculo}/soporte` | List Permissions |
| POST | `/vehiculos/{id_vehiculo}/soporte/{id_permiso}/revocar` | Revoke |
| GET | `/soporte/administradores` | Administrators |
| GET | `/admin/soporte` | My Support |
| GET | `/vehiculos/{id_vehiculo}/control` | Status |
| POST | `/vehiculos/{id_vehiculo}/control/reservar` | Reserve |
| POST | `/control/{id_control}/cerrar` | Close |
| GET | `/admin/modelos/{id_modelo}/capacidades` | Capabilities |
| POST | `/admin/modelos/{id_modelo}/capacidades` | Create |
| POST | `/admin/modelos/{id_modelo}/capacidades/{id_capacidad}/actualizar` | Update |
| GET | `/admin/unidades/{id_vehiculo}/comandos` | Commands |
| POST | `/admin/unidades/{id_vehiculo}/comandos` | Add Command |
| POST | `/admin/unidades/{id_vehiculo}/comandos/{id_comando}/actualizar` | Edit Command |
| GET | `/health/db` | Comprobar Base Datos |

## Canales WS

| Canal | Identidad y uso |
| --- | --- |
| `/ws/vehiculos/{id}` | Autenticar token; propietario, empresa sobre inventario o soporte diagnóstico autorizado. Estado inicial/eventos; no concede reserva de control. |
| `/ws/control/{id_control}` | Autenticar token del titular; un canal por reserva; `renovar` mantiene vigencia mientras identidad y permiso sigan vigentes. |
| `/ws/invitados` | Autenticar token temporal; sólo unidad reservada y comandos de exhibición. |

Verificar la ruta de Invitado en el router y usar los scripts entregados; nunca enviar tokens en la URL.
