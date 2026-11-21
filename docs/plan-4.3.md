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
