# Plan de ampliación 4.3

## Base verificada

Inventario de RDS recibido el 21 de noviembre de 2026. Esquema
`vehiculo_iot`, MySQL 8.4.9, seis tablas InnoDB y 21 procedimientos
`SQL SECURITY DEFINER`, definidos por `admin@%`.
La cuenta `iot_api@%` tiene EXECUTE en el esquema.

| Tabla existente | Uso y relaciones |
| --- | --- |
| vehiculos | Unidad física identificada por id_vehiculo. modelo es texto. |
| comandos | Comandos de cada unidad. Nombre y código únicos por unidad. |
| estado_vehiculo | Estado único por vehículo y referencia al comando. |
| historial_comandos | Registros por vehículo y comando. Orden por fecha_hora e id_historial descendentes. |
| demos | Cabecera de secuencia vinculada a una unidad. |
| demo_movimientos | Pasos vinculados a demo y comando. Orden único dentro de cada demo. |

Los procedimientos de eliminación actuales ejecutan DELETE. La ampliación
administrativa necesita baja lógica de unidades y comandos para conservar
historial. La compatibilidad de los procedimientos se revisará en la copia de
prueba antes de preparar cambios.

## Diseño propuesto para revisión

Los nombres siguientes son propuestas de tablas y campos.

| Componente | Propuesta |
| --- | --- |
| Cuentas y clientes | usuarios con identificador, correo único, nombre, hash de contraseña, rol validado y activo. El comprador utiliza la misma cuenta que su ficha de cliente. |
| Sesiones | sesiones con usuario, hash del token, caducidad y revocación. Login y logout validados por FastAPI. |
| Modelos | modelos con nombre, descripción, activo y capacidades. |
| Unidades | Extender vehiculos con id_modelo, identificador comercial único y estado comercial. Mantener id_vehiculo como ID de CONTROL y MONITOREO. |
| Propiedad | asignaciones con fechas de inicio y fin para mantener historial. Una relación de propiedad vigente única por unidad, protegida por restricción y transacción. |
| Capacidades | capacidades_modelo como catálogo del modelo. comandos mantiene el enlace de cada comando con su unidad física. Validar ambos niveles al ejecutar. |
| Demos | Extender demos con propietario y tipo empresa/privada. Reutilizar demo_movimientos y validar que cada comando pertenezca al vehículo de la secuencia. |
| Reservas | Una reserva operativa vigente por unidad, compartida por Usuario, soporte e Invitado. Adquisición transaccional con bloqueo por unidad y expiración. |
| Invitados | Sesión temporal con token almacenado como hash, unidad de exhibición, caducidad, comandos permitidos y estado. |
| Soporte | Autorización explícita del comprador con administrador, unidad, vigencia y revocación. |
| Auditoría | Actor, acción, recurso, resultado y fecha UTC. Redactar secretos y datos privados innecesarios. |

Los vehículos actuales requieren clasificación comercial explícita. El primer
administrador se creará con un comando de servidor y contraseña introducida
localmente. El diseño definitivo y los scripts SQL se preparan después de
obtener el DDL exacto y validar el respaldo en una copia.

## Autorización y ejecución

FastAPI validará identidad, rol, unidad y reserva antes de cada acción.
Usuario ve sus unidades. Invitado recibe catálogo público y una sesión de
exhibición. Administrador gestiona inventario y usa soporte operativo mediante
permiso explícito.

WSS necesita autenticar y autorizar suscripciones. Cambios de dueño, expiración
y revocación deben cerrar acceso y liberar o detener reservas. La API key
compartida actual requiere un plan de transición para que no permita eludir
los nuevos permisos. Los clientes web y el firmware se revisan antes de
desactivar o restringir el mecanismo anterior.

Las reservas vencidas y desconexiones requieren detención en el servidor y
un temporizador de seguridad en firmware para cubrir cortes completos de red.
La confirmación física se probará con el circuito disponible.

## Entregas y comprobaciones

1. Respaldo SQL con tablas, datos, procedimientos y metadatos de integridad.
   Restauración en una base aislada y comparación de conteos y relaciones.
2. Migraciones versionadas revisadas sobre el DDL real. Aplicación en prueba,
   validaciones de integridad y plan de recuperación por respaldo.
3. Backend modular con cuentas, sesiones y permisos por recurso.
   Verificación de 401/403, aislamiento entre compradores y WSS autorizado.
4. Administración con inventario, clientes, asignaciones y métricas reales.
5. Mis vehículos y editor de demos persistentes con pasos ordenados.
6. Invitados, soporte, reservas exclusivas, caducidad y DETENER.
7. Regresión de CONTROL/MONITOREO, publicación en el repositorio original y
   pruebas cruzadas de las tres plataformas con la matriz de la consigna.

## Datos pendientes

- Validación de las migraciones en la copia restaurada. El respaldo y el DDL
  exacto ya se recibieron y revisaron.
- Copia actual del backend de Windows Server para contrastarla con el código local.
- Clasificación comercial y propietario inicial de la unidad 1.
- Nombre y correo del primer administrador cuando se prepare su alta.

El respaldo vehiculo_iot_20261121-203540-777513.sql se restauró en
iot_prueba_20261121_205613_303067. La ejecución compartida por el usuario
confirma conteos iguales en origen y copia y los mismos nombres de los
21 procedimientos. Se conservaron 13 comandos, nueve pasos, dos demos,
un estado, 306 registros de historial y un vehículo.

Esta comprobación cubre restauración, conteos y presencia de procedimientos.
Las pruebas de integridad referencial, comparación de definiciones y regresión
de APIs sobre la copia se realizarán al validar las migraciones.

## Migración 001 preparada

`sql/migrations/001_base_administracion.up.sql` añade usuarios, modelos,
asignaciones y el registro de migración. Extiende vehiculos con id_modelo,
identificador_unidad y estado_comercial. El estado inicial PENDIENTE permite
clasificar la unidad después de revisar propietario y uso de exhibición.
Las nuevas tablas empiezan vacías.

`tools/migrar_copia_rds.py` acepta únicamente copias con el formato generado
por la verificación del respaldo. Exige las seis tablas originales, captura
los valores de sus columnas actuales y las definiciones de procedimientos
antes y después, y guarda el resultado fuera del contenido público.

La migración 001 se ejecutó en iot_prueba_20261121_205613_303067.
La salida compartida por el usuario confirma código MySQL 0 y comparación
de datos y procedimientos conservados=True. Las diez tablas esperadas están
presentes. El informe del servidor es migracion_001_20261121-210425-084695.json.
El usuario ejecutó probar_migracion_001.py y compartió siete resultados
correctos: altas transaccionales de un administrador y dos compradores,
asignación, rechazo de propietario vigente duplicado, reasignación y consulta
por sp_obtener_vehiculo. Las filas de prueba se revirtieron. Informe
prueba_001_bfe8960a23dd409eadac0c6b500bcaa1.json.
Ante DDL parcial, revisar los
objetos creados. Para recuperar el entorno de prueba se puede restaurar el
respaldo en otra copia nueva mediante verificar_respaldo_rds.py y conservar la
copia fallida para diagnóstico. La reversión conserva el respaldo original
como fuente de recuperación. Las etapas posteriores tienen pendiente sesiones,
capacidades, soporte, invitados, reservas, auditoría y metadatos de demos.

La propuesta 002 añade sesiones revocables con hashes de tokens y auditoría
de acciones. Se ejecutó en la copia con código MySQL 0 y conservación
de datos/procedimientos originales confirmada por el usuario.
Se crearon sesiones, auditoria y los cuatro procedimientos sp_auth_*.
Informe migracion_002_20261121-212018-297435.json.
El ZIP backend_revision_4_3.zip fue revisado e incorporado en backend/.
main.py contiene CORS para el origen GitHub Pages. Los módulos de movimientos
y ejecución de demos coinciden con la copia local. config.py y database.py se
reutilizaron de la copia local y requieren contraste antes del despliegue.

Se prepararon /auth/login, /auth/me y /auth/logout, hashes scrypt con sal
individual y sesiones de una hora con tokens opacos y hash SHA256 en RDS.
La creación de sesión y su auditoría se confirman en una transacción.
La autenticación usa los procedimientos sp_auth_* de la migración 002.

Siete pruebas locales pasaron con el acceso a datos sustituido por dobles
controlados. Cubren hashes, credenciales erróneas, cuenta inactiva, ausencia
de sesión, sesión rechazada por el repositorio, creación y cierre.
La validación SQL de expiración/revocación y las pruebas de integración real
permanecen pendientes. Las dependencias instaladas para esta revisión local
pueden diferir de las versiones del requirements.txt recibido del servidor.

Esta entrega prepara autenticación. Los endpoints REST/WSS anteriores todavía
usan su esquema de acceso original y quedan pendientes de autorización por
recurso. El despliegue de la plataforma multiusuario requiere completar esa
transición, el control de intentos de login, la provisión del administrador y
el aislamiento probado antes de habilitar usuarios externos.

El usuario creó el primer administrador de aplicación en la copia mediante
crear_admin_prueba.py. Reportó creación, lectura y revocación de sesión SQL
correctas y cuenta confirmada. Las pruebas HTTP están pendientes.

El paquete backend de prueba se inicia con iniciar_prueba.py y enlaza
127.0.0.1:8001. Carga el .env existente y selecciona la copia por argumento.
La cuenta iot_api requiere EXECUTE explícito en esa copia para llamar sus
procedimientos; habilitar_prueba_rds.py concede ese permiso al esquema de prueba.

El usuario confirmó HTTP 200 de login y resultados esperados de /auth/me,
/auth/logout y rechazo 401 al volver a usar la sesión revocada en el backend
aislado. La integración básica de autenticación está comprobada con RDS.

Se preparó la migración 003 con consultas de resumen, modelos, compradores y
unidades y altas de modelos y compradores con auditoría transaccional.
Las rutas /admin requieren require_admin. La suite local acumula trece pruebas
correctas con repositorios simulados, incluidas respuestas 401, 403, 409 y 422.
El usuario ejecutó 003 en la copia y reportó código MySQL 0 y conservación
de datos/procedimientos originales=True. Informe
migracion_003_20261121-214759-525694.json. Las pruebas HTTP de Administración
están pendientes de realizar con el paquete backend de prueba actualizado.
El usuario confirmó GET de resumen, unidades y modelos con HTTP 200, altas
de modelo y comprador correctas, login del comprador, /auth/me con rol USUARIO
y rechazo 403 en /admin/resumen.

La migración 004 y sus rutas están preparadas para configurar modelo e
identificador de una unidad, asignarla/reasignarla y consultar /mis-vehiculos.
Las escrituras se confirman junto con auditoría. El procedimiento de asignación
bloquea la fila de unidad y comprueba comprador activo y propietario vigente.
El usuario ejecutó SQL 004 en la copia y reportó código MySQL 0 y
conservación de datos y procedimientos originales=True. Informe
migracion_004_20261121-220924-791526.json. Las comprobaciones HTTP de
configuración y asignación fueron realizadas por el usuario. Modelo 3
Montacargas RC, comprador 5 y unidad 1 con identificador MONT-001.
El GET /mis-vehiculos autenticado como comprador devolvió esa unidad
con estado ASIGNADO. Queda pendiente comprobar otro comprador sin unidades
y completar autorización en rutas operativas REST y WSS.
El usuario confirmó un segundo comprador con /mis-vehiculos vacío.

Se preparó 005_acceso_recursos y el modo IOT_AUTH_MODE=sesiones, activado por
iniciar_prueba.py. Las rutas anteriores requieren sesión y comprueban la unidad
de vehículos, comandos, demos y pasos. La API key por sí sola se rechaza en
este modo. El administrador conserva inventario pero requiere soporte futuro
para operar una unidad asignada. El CRUD de demos permanece restringido al
administrador hasta incorporar propiedad privada de demos.

El socket acepta Authorization Bearer o un primer mensaje
{"tipo":"autenticar","token":"TOKEN_DE_SESION"}. Valida antes del estado inicial,
revalida cada dos segundos y antes de enviar eventos. La revocación o pérdida
de propiedad cierra el acceso. El frontend y firmware actuales requieren la
adaptación de autenticación antes del despliegue público de este modo.

La suite local de 24 pruebas pasó con repositorios simulados. Las nuevas
comprobaciones HTTP y WSS reales están pendientes de aplicar SQL 005.
El usuario aplicó SQL 005 con código MySQL 0 y conservación=True. Después de
corregir la declaración HTTPBearer en Swagger confirmó 403 al consultar
/vehiculos/1/estado como Comprador B y 200 como comprador propietario.
La comprobación real del socket autenticado continúa pendiente.

Se preparó 006 para edición/baja lógica de modelos y compradores y consulta
de auditoría. La desactivación de un comprador revoca sus sesiones dentro
de la misma transacción. Desactivar un modelo con unidades activas se rechaza.
La ejecución MySQL y las pruebas HTTP de 006 están pendientes.
El usuario aplicó SQL 006 y confirmó código MySQL 0 y conservación=True.
Informe migracion_006_20261121-232408-192388.json.
Se preparó probar_admin_http.py para las comprobaciones de 006 por HTTP:
crear/duplicar/desactivar modelo, crear/desactivar comprador, revocar su sesión
y comprobar la auditoría. Crea registros de prueba identificables y los deja
inactivos al completar exitosamente la secuencia. La ejecución está pendiente.
El usuario ejecutó probar_admin_http.py y confirmó todas las comprobaciones,
incluidas respuestas 201/409/200 en modelos, creación y desactivación del
comprador, rechazo 403 en auditoría, revocación 401 y cuatro acciones
persistidas en auditoría. Informe http_admin_d62c162e21b0.json.
Se preparó probar_acceso_wss.py para completar la validación real de
aislamiento REST/WSS y cierre del socket al revocar una sesión.
El usuario compartió la ejecución correcta de probar_acceso_wss.py.
Se verificaron cuentas distintas, propiedad de la unidad 1, lista vacía
del segundo comprador, GET de estado/historial/comandos con 200 para dueño
y 403 para Comprador B, WSS rechazado antes del estado para Comprador B,
estado inicial WSS para dueño, logout y cierre del socket tras revocación.
Informe prueba_wss_20261122-010410-849588.json.

Siguiente bloque funcional: demos privadas con propietario, listado filtrado,
editor de pasos compatible con comandos de la unidad y guardado atómico.
La siguiente migración deberá preservar las dos demos existentes como demos
de empresa, mantener los nueve pasos actuales y validar que la reasignación
de un vehículo no exponga demos privadas de su propietario anterior.

## Entrega 007 preparada

007_editor_demos añade tipo EMPRESA/PRIVADA, propietario y revisión.
Los registros previos reciben tipo EMPRESA y revisión 1. Los tres procedimientos
sp_editor_* resuelven visibilidad y guardan cabecera y secuencia en la misma
transacción, con comprobación de usuario y propiedad y bloqueo de la unidad.
El guardado rechaza revisiones antiguas, comandos inactivos o ajenos y demos
anidadas. La API protege edición mientras hay una demo ejecutándose en el
proceso actual.

Límites iniciales elegidos para el editor: 100 pasos, 10000 ms por movimiento,
5000 ms por pausa y 120000 ms por secuencia. Son límites de software
conservadores configurados para esta entrega y deben contrastarse con el
hardware antes de ejecutar físicamente secuencias.

Rutas preparadas: GET/POST /mis-demos, GET /mis-demos/{id_demo} y
POST /mis-demos/{id_demo}/guardar. La consulta exige id_vehiculo.
Las rutas previas de edición individual de pasos, en modo sesiones, remiten
al editor de secuencia completa para mantener revisiones y propiedad.
La consulta previa de demos y el inicio de ejecución filtran visibilidad.

La suite de 34 pruebas locales pasó. probar_editor_demos.py está preparado
para crear, leer, editar y desactivar una demo privada de DETENER sin iniciar
su ejecución; verifica ocultación al segundo comprador, conflicto de revisión
y rechazo de un comando ajeno conservando la secuencia guardada.
La comprobación real descubrió una inversión de id_comando/orden al insertar
pasos. La migración 008 reemplaza sp_editor_guardar_demo y corrige 007 para
instalaciones nuevas. Se conservó el índice único de orden por demo.

## Validación real de la corrección 008

El usuario confirmó código MySQL 0 y conservación de datos/procedimientos.
La prueba reanudada sobre demo 3 pasó guardado completo, ocultación al otro
comprador, rechazo de revisión antigua, rechazo de comando incompatible,
conservación de secuencia y desactivación de la demo de prueba.
Informes del servidor: migracion_008_20261122-014130-719759.json y
prueba_editor_8080db762b0d.json.

## Interfaz 4.3 en preparación para pruebas aisladas

La vista Mi cuenta integra login, menú por rol, resumen, modelos, compradores,
configuración y asignación de unidades, auditoría, vehículos del comprador
y editor visual de demos. La selección de unidad conecta control/monitoreo
mediante sesión Bearer y autenticación del primer mensaje del WebSocket.
Las credenciales y tokens se mantienen solamente en memoria de la pestaña.
Cambiar de cuenta limpia catálogo e historial y cierra el socket previo.

El paquete frontend_4_3_prueba.zip usa localhost:8001 y modo sesiones.
El config.js del repositorio conserva el modo API key de producción hasta
publicar el backend de sesiones. La interfaz nueva aún requiere validación
con las cuentas reales en el servidor Windows. Quedan pendientes los demás
requisitos 4.3, la regresión de ejecución y el despliegue final.

Comprobaciones locales de interfaz: sintaxis de todos los módulos JavaScript,
ZIP íntegro y sin auth.local.js, pantalla de acceso en escritorio y viewport
390 px sin desbordamiento, error de conexión recuperable al enviar el login
con el backend apagado. La revisión horizontal posterior quedó interrumpida
por desconexión del servidor de vista previa. No se verificaron formularios
autenticados localmente contra el servidor Windows.

## Validación del frontend comunicada por el usuario

El usuario compartió capturas de login administrador, resumen, modelos,
unidades, compradores y auditoría con datos reales de la copia. Como comprador
propietario confirmó listado MONT-001, carga del control y demos. Confirmó
crear una demo desde la web, modificar la duración, recuperar el cambio y
ejecutarla con evento DEMO finalizada. Comprador B conserva lista vacía.
El historial de diez individuales sigue el contrato previo: los pasos internos
de demos no se insertan como individuales. La consigna 9.5 exige respetarlo.
Los ajustes visuales se posponen por indicación del usuario.

## Entrega 009 de inventario preparada

La revisión de requisitos 7.2/7.5 y P02 detectó que faltaba el alta de unidad
comercial desde la aplicación. 009 crea sp_admin_crear_unidad y
sp_admin_actualizar_unidad y amplía la consulta administrativa con descripción
y microcontrolador originales. No altera las seis tablas ni los 21 SP previos.
El identificador sigue protegido por el UNIQUE de 001. Alta/edición y auditoría
se confirman en una misma transacción. El campo modelo legacy conserva hasta
80 caracteres; la referencia id_modelo y nombre_modelo comercial es completa.

POST /admin/unidades registra nombre, id_modelo, identificador_unidad,
descripcion y microcontrolador y devuelve id_vehiculo con HTTP 201.
POST /admin/unidades/{id}/actualizar recibe además activo, realiza edición
completa y baja lógica con HTTP 200. Admin y validación Pydantic protegen ambas.
La UI incorpora Nueva unidad, Editar, estado activo/inactivo y búsqueda sobre
las 100 unidades cargadas. La paginación REST preexistente se conserva;
la navegación de páginas y filtros completos siguen pendientes en la UI.

Las unidades nuevas no heredan comandos ni declaran conectividad física.
Una unidad asignada conserva modelo y estado activo; la baja de unidades
vendidas requiere completar la detención/reservas y el flujo comercial.
No se cambia el modelo de unidades con comandos/demos sin revisar capacidades.
Se rechaza editar durante una demo en ejecución. La ruta antigua /configurar
queda obsoleta y responde 409 hacia el documento completo. En modo sesiones
las escrituras legacy /vehiculos remiten a /admin/unidades para impedir
eludir estas validaciones. El modo legacy conserva su comportamiento.

43 pruebas locales del backend pasaron, incluidas nueve de inventario.
La validación SQL real de 009 queda pendiente. probar_inventario_http.py crea
un modelo, dos unidades y un comprador nuevos; comprueba duplicados,
persistencia, permisos, bajas, rechazo de asignación inactiva y auditoría.
Deja los registros nuevos inactivos y no modifica la unidad 1 ni sus comandos.
Guarda resultados privados en respaldos_rds y cierra las sesiones de prueba.

Recuperación ante DDL parcial: conservar informe del ejecutor y examinar los
procedimientos nuevos y sp_admin_listar_unidades antes de reintentar. La
definición anterior de listado está en 003_gestion_comercial.up.sql; restaurar
sólo esa rutina con el backend/frontend anterior permite volver a la versión
previa. No ejecutar 003 completa sobre una base ya migrada. La migración no
cambia filas, pero no se confía en ROLLBACK para deshacer sus CREATE/DROP.

## Validación real de 009

El usuario confirmó migracion_009_20261122-025030-188422.json, MySQL 0 y datos
y procedimientos conservados. Ejecutó probar_inventario_http.py y pasó todos
los resultados previstos: altas, edición, duplicados, conservación tras rechazo,
401/403, bajas lógicas de unidades nuevas 3 y 4, rechazo de asignación inactiva
y auditoría. Informe http_inventario_257cb1811281.json. Confirmó actualizar el
frontend y ver Nueva unidad, Editar, búsqueda y unidades de prueba inactivas.

## Entrega 010 de catálogo preparada

Primer bloque de Invitados (requisito 10.1). Añade modelos.publico con valor
inicial 0 y publicación explícita por administrador. No publica registros
existentes durante la migración. POST /admin/modelos/{id}/publicacion recibe
publico; POST /admin/unidades/{id}/exhibicion recibe habilitada. Esta última
exige unidad activa sin propietario y modelo activo publicado. Conserva los
historiales y registra ambas operaciones junto con la auditoría en transacción.
La configuración de exhibición se rechaza durante una demo en ejecución.

GET /catalogo es anónimo y paginado. Sólo devuelve id_modelo, nombre,
descripcion y unidades_exhibicion de modelos activos publicados. Su conteo
excluye unidades inactivas, estados distintos a EXHIBICION y cualquier unidad
con asignación vigente, incluso si su estado comercial fuera inconsistente.
El conteo representa inventario comercial; no confirma hardware conectado ni
reservas disponibles. El esquema Pydantic evita filtrar columnas privadas.

La interfaz incorpora Explorar catálogo público en Mi cuenta, Publicar/Retirar
en Modelos y Usar/Retirar exhibición en unidades activas sin propietario.
El catálogo permite navegar páginas y avisa que las pruebas de control todavía
no están disponibles. Las reservas exclusivas, los tokens temporales, el reloj,
comandos limitados, soporte y detención por caducidad continúan pendientes.
La unidad 1 permanece asignada al comprador; no se cambia su clasificación.

53 pruebas locales pasaron. Incluyen contrato público sin campos privados,
permisos, sanitización de errores, paginación y ejecución del SELECT real del
catálogo sobre una base SQLite desechable para comprobar filtros. Esto no
verifica instalación de procedimientos ni bloqueos de MySQL. La migración
010 y probar_catalogo_http.py requieren ejecución real en la copia de RDS.
El script crea un modelo y una unidad nuevos, comprueba publicación/retiro,
conteos, rechazo de exhibición privada/asignada y auditoría. Comprueba que la
unidad 1 sigue asignada antes de intentar la operación que debe rechazarse,
y que el inventario de esa unidad permanece idéntico después. No envía
movimientos. Los registros nuevos quedan privados e inactivos al finalizar.

Recuperación ante DDL parcial: conservar el informe y revisar la existencia
de modelos.publico y de las nuevas rutinas antes de repetir el SQL. El backend
y frontend anteriores pueden restaurarse conservando la columna adicional;
el listado administrativo previo está definido en 003. No eliminar registros
ni volver a ejecutar migraciones anteriores completas. El despliegue público
de esta ampliación continúa pendiente de completar el flujo de Invitados.

## Ejecución real 010 y corrección del script

El usuario aplicó 010 con MySQL 0 y conservación=True. Informe
migracion_010_20261122-031031-050600.json. probar_catalogo_http.py pasó todas
las comprobaciones funcionales, incluidas publicación/retiro, conteos,
privacidad, rechazo de exhibición de unidad 1 asignada sin cambios, bajas
de unidad/modelo y auditoría. Informe http_catalogo_eec461b73ebc.json.

El script terminó con error de limpieza porque su bloque finally repetía
la baja de la unidad después de haber desactivado el modelo. La rutina 009
exige modelo activo y esa escritura redundante puede responder 409.
La corrección registra las bajas exitosas y evita repetirlas. No modifica
el backend ni necesita repetir las migraciones. Tres pruebas de regresión
con estado controlado verifican la secuencia completa y la comprobación de
resultados anteriores sin escrituras de inventario. La suite suma 56 pruebas.

La opción --verificar-informe consulta los IDs del informe anterior y guarda
un archivo .estado_verificado.json con publicación/actividad del modelo y
actividad, estado comercial y ausencia de propietario de la unidad de prueba.
Sólo inicia/cierra una sesión y lee inventario; no crea ni modifica esos
registros. La confirmación real del estado final está pendiente de esta lectura.
