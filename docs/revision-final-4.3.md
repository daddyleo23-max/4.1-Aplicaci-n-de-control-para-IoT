# Revisión de requisitos 4.3 — 22 de noviembre de 2026

Revisión del enunciado conservado en los adjuntos, código local y resultados
aportados por el alumno. No constituye una nueva ejecución sobre AWS ni una
validación del despliegue público. No se modificó código ni base de datos.

## Base comprobada

- Respaldo original restaurado en copia aislada y comparación de conteos y procedimientos.
- Migraciones hasta 018 sobre `iot_prueba_20261121_205613_303067`.
- Login, expiración/logout, propiedad, permisos REST/WS y rechazo de acceso cruzado.
- Modelos/unidades/clientes, asignaciones, bajas lógicas y auditoría.
- Capacidades por modelo y comandos por unidad, identidad conservada y validación al ejecutar.
- Demos privadas y de empresa, edición con revisión, persistencia, cancelación y DETENER.
- Reservas exclusivas de comprador, Invitado y soporte; cierres por desconexión, revocación y caducidad.
- Consentimiento de soporte diagnóstico u operativo y separación de demos privadas.
- Indicadores independientes y conservación del historial de diez movimientos individuales.

La entrega 021 fue aprobada por el alumno con el informe
`demos_empresa_1e4ce21b54e6.json`: incluyó fin con DETENER, historial individual
sin pasos internos, cancelación, aislamiento y ejecución por el comprador.
La captura posterior confirma menú y listado de Demos de empresa. No demuestra
por sí sola pruebas físicas, móvil ni publicación de 4.3.

## Pendientes confirmados de implementación

| Requisito | Hallazgo | Cierre necesario |
| --- | --- | --- |
| Exclusividad general; 10.2, 12.4 | El administrador sobre unidad activa sin comprador pasa por `_registrar_sesion_admin` y comprueba reserva libre, pero no adquiere una reserva ligada a su sesión. El bloqueo de tareas serializa operaciones sin establecer un titular exclusivo. | Extender exclusividad a esta operación y probar dos sesiones administrativas, además de las regresiones de Invitado, comprador, soporte y demos. |
| 10.1 | `PublicModel` y `showPublicCatalog` ofrecen nombre, descripción y conteo de exhibición; no ofrecen capacidades ni fotos/assets del modelo. | Incorporar capacidades publicables y assets apropiados sin datos privados; mantener la disponibilidad real de la vista de unidades. |
| 6.1 | Resumen muestra cinco contadores; falta demos, disponibilidad efectiva para prueba y tablas resumidas/filtros/accesos dentro del resumen. Exhibición no equivale a disponibilidad para reservar. | Completar métricas reales y navegación del dashboard. |
| 7.2; 4.4 | Modelos y compradores cargan hasta 100 registros sin búsqueda/paginación de interfaz; otras listas y selectores también usan ese límite. El catálogo público sí pagina. | Búsqueda de modelos y navegación completa de listas/selectores para evitar registros inaccesibles. |
| 11.4, prompt maestro | Existe límite de reservas y pulsos de Invitado, pero `/auth/login` no tiene control de tasa en la aplicación ni hay evidencia revisada de uno equivalente en el proxy. | Establecer y probar límite de intentos de autenticación; documentar alcance de los límites. |
| 5.1 | La pestaña tercera se llama MI CUENTA incluso para Administrador. | Mostrar ADMINISTRACIÓN para Admin y conservar denominación adecuada para comprador/visitante. |

Bootstrap 5 ya está incluido en `index.html`; no se registra como dependencia
faltante. La revisión visual completa y accesibilidad siguen pendientes de la
versión final, conforme a la decisión de cerrar funciones antes del diseño.

## Documentación y entrega pendientes

- Actualizar README: actualmente presenta dos vistas y autenticación antigua con API key.
- Consolidar inventario antes/después, contratos REST/WS, roles, variables de entorno,
  Swagger con ejemplos y códigos, diagrama ER final y recuperación UP/DOWN.
  Hay documentación y diagramas parciales en `plan-4.3.md`, pero son un historial
  de entregas con estados pendientes antiguos; no equivalen a un documento final actualizado.
- Preparar matriz P01–P17 con evidencia identificada; conservar resultados reales y
  marcar No ejecutado donde corresponda. No repetir indiscriminadamente pruebas aprobadas.
- Realizar las rondas colaborativas de las tres plataformas con compañeros y sus
  conclusiones; no se sustituyen por pruebas automáticas locales.
- Verificar móvil físico, escritorio, accesibilidad, reconexión y recorrido público
  Admin → Usuario → Invitado de la versión final.
- Registrar limitaciones y evidencia física sólo si existe autorización y supervisión.
  Los eventos backend/WS no acreditan movimiento físico.

## Publicación pendiente

El repositorio local está 22 commits por delante de la referencia local
`origin/main` al revisar. No se consultó ni actualizó esa referencia remota.
`js/config.js` conserva `sessionAuth: false` para el despliegue anterior; los
paquetes de prueba habilitan sesiones con API local en 8001.

Preparar respaldo actualizado y plan de puesta en servicio/recuperación;
seleccionar expresamente el esquema definitivo, comprobar permisos mínimos,
configuración FastAPI/Caddy, HTTPS/WSS, CORS y configuración frontend de sesiones.
Después publicar y validar desde la URL pública. La copia aislada aprobada no
implica que el servicio público ya ejecute la versión 4.3. Evitar publicar la
configuración de localhost o aplicar migraciones de nuevo sin diagnóstico.

## Orden recomendado

1. Cerrar exclusividad administrativa y control de intentos de login.
2. Completar catálogo, dashboard y acceso completo a listas.
3. Revisar diseño/responsive y documentación final.
4. Preparar puesta en servicio, publicar y validar HTTPS/WSS desde móvil y escritorio.
5. Completar matriz colaborativa y evidencias de entrega.

No se asigna porcentaje exacto: faltan bloques verificables de implementación,
publicación y evaluación colaborativa, de esfuerzo distinto. La base funcional
está avanzada y las pruebas aprobadas siguen siendo evidencia útil.

## Actualización: implementación local de entrega 022

Los seis pendientes de implementación de esta revisión tienen cambios locales:
reserva de empresa (SQL019), límites de login, catálogo con capacidades/asset
SVG, dashboard (SQL020), listas completas con búsqueda/paginación y nombre de
pestaña por rol. El asset está en catálogo; no desplaza el mando.

Se actualizan README, arquitectura/ER, contratos y plan de despliegue. La matriz
colaborativa queda como plantilla con No ejecutado; no se inventan resultados.
Las comprobaciones locales no cierran todavía los pendientes RDS/Windows,
publicación HTTPS/WSS, teléfono físico, compañeros y dispositivo supervisado.
Ver `despliegue-4.3.md` antes de aplicar esta entrega.


## Actualización: validación real de copia y preparación de publicación

019 recuperada,020 aprobada,18 pruebas SQL y comprobación HTTP/WS completa
aprobadas por el alumno. Backend4.3.0 y frontend actualizado confirmados;
búsqueda MONT-001 deja una fila. Los pendientes de implementación anteriores
quedan validados en la copia RDS. No implica promoción del esquema original,
publicación, pruebas de teléfono público ni rondas con compañeros.


## Actualización: frontend y API publicados

GitHub Pages construido y versión4.3 accesible en el hosting original. API HTTPS
4.3.0 conectada a vehiculo_iot_43 y catálogo comprobado desde navegador, sin
errores de consola. CORS y rechazos anónimos REST/WSS comprobados. Los pendientes
actuales son el recorrido público autenticado, teléfono físico, evidencias
finales y rondas de compañeros; ver verificacion-publica-4.3.md.


## Actualización: prueba pública autenticada aprobada

El informe citado por el alumno cierre_4_3_0c48517ad035.json confirma las44
comprobaciones HTTPS/WSS de empresa mediante Caddy. El pendiente genérico de
WS autorizado/control/demo público queda verificado para ese escenario. Se
mantienen teléfono real, recorridos por roles Comprador/Invitado, evidencias y
rondas de compañeros; no se afirma prueba física del vehículo.
