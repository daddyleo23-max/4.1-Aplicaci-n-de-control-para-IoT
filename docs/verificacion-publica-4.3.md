# Publicación y comprobación pública4.3 — 22 de noviembre de2026

Publicado en el repositorio original, rama main, GitHub Pages desde raíz.
Primera compilación4.3 confirmada: a30fceeb2a690951b2f1d193181f7be8fb57a175,
estado built sin error. Las actualizaciones de este documento no cambian los
contratos de la aplicación.

| Comprobación observada | Resultado |
| --- | --- |
| API HTTPS pública |4.3.0 |
| RDS desde API | conectadoTrue, vehiculo_iot_43, MySQL8.4.9 |
| Frontend publicado | sessionAuth:true y API pública; no localhost |
| Navegador, desde GitHub Pages | indicadores API/RDS disponibles y pantalla de cuenta |
| Catálogo público | modelo publicado, capacidades ADELANTE/DETENER, unidad de exhibición y SVG cargado |
| Consola al consultar catálogo | sin errores observados |
| Preflight POST con Origin de GitHub Pages | permitido para el origen exacto |
| Administración sin sesión |401 |
| WSS con token inválido | conexión disponible, cierre1008 sin entregar estado |

![Catálogo público consultado desde GitHub Pages](capturas-publicas/catalogo-4.3.jpg)

Estas son pruebas reales de la URL pública, fuera de las rondas de compañeros.
El modelo visible está identificado como prueba de interfaz sin hardware; no se
le atribuye movimiento físico. No se reservaron unidades ni enviaron movimientos
durante esta comprobación del agente. No se ingresaron contraseñas de aplicación.

Faltan recorridos autenticados Admin/Usuario/Invitado, control/demo y WS autorizado,
verificación en teléfono real y rondas colaborativas. El alumno puede ejecutar
`probar_publicacion_4_3.py` desde su servidor para comprobar HTTPS/WSS autenticado
sobre unidades NUEVAS de software; solicita credenciales de aplicación en entrada
oculta y conserva reporte sin tokens.

El frontend y backend se recuperaron después de una pausa del laboratorio. Un502
se debió a backend8002 no disponible durante ese periodo; al arrancarlo de nuevo
se comprobó la API4.3 y la misma base definitiva. No se repitieron migraciones ni
se cambió de nuevo el proxy.
