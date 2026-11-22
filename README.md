# Montacargas IoT · Control, monitoreo y administración

Plataforma individual 4.1–4.3 en el repositorio original: HTML5, Bootstrap 5,
CSS, JavaScript modular, FastAPI, REST/WS y MySQL/RDS.

- **CONTROL:** joystick, botones compatibles, DETENER, demos y reserva exclusiva.
- **MONITOREO:** último estado, diez movimientos individuales e indicadores separados de API, RDS y sesión WS.
- **ADMINISTRACIÓN:** modelos/capacidades, unidades/comandos, compradores, asignaciones, dashboard, demos de empresa, soporte consentido y auditoría.
- **Comprador:** sus unidades, demos privadas y demos de empresa de sólo lectura.
- **Invitado:** catálogo publicado y prueba temporal de exhibición con límites.

## Estado real

**4.3 publicada en el hosting original y conectada a la API HTTPS de AWS.**

- [Aplicación pública](https://daddyleo23-max.github.io/4.1-Aplicaci-n-de-control-para-IoT/#cuenta)
- [Swagger público](https://34.194.45.28/docs)
- Backend4.3.0 en loopback8002, Caddy80/443 y esquema definitivo `vehiculo_iot_43` (MySQL8.4.9).

Migraciones001–020, recuperación019, restauración íntegra y pruebas SQL/HTTP de
la copia fueron aprobadas por el alumno. La versión publicada se comprobó en
navegador: carga de módulos/asset, API y RDS disponibles, catálogo consultado
sin errores de consola. También se verificaron CORS,401 sin sesión y rechazo
WSS de un token inválido. El alumno aprobó además la prueba pública autenticada
de empresa/control/demo (`cierre_4_3_0c48517ad035.json`), a través de HTTPS/WSS
y Caddy. [Evidencia pública](docs/verificacion-publica-4.3.md).

**Pendientes de evaluación:** recorridos de Comprador e Invitado desde la
interfaz pública, comprobación en teléfono físico y rondas P01–P17 con compañeros. Las pruebas
anteriores en localhost no sustituyen esos escenarios. No se afirma ejecución
física del vehículo por recibir eventos del servidor.

El `js/config.js` raíz usa sesiones y API pública. Los ZIP de prueba apuntan a
localhost8001 y no deben subirse a GitHub Pages. Mantener Caddy y el backend8002
funcionando durante el uso público; el arranque actual es manual en Windows.

## Documentación y ejecución

Si la entrega022 falló en 019 con ERROR1832, usar la [recuperación específica](docs/recuperacion-019.md); no repetir la migración completa sobre el estado parcial.

- [Arquitectura, ER y roles](docs/arquitectura-4.3.md)
- [Inventario de contratos antes/después](docs/inventario-contratos-4.3.md)
- [Contratos HTTP/WS](docs/contratos-4.3.md) y [OpenAPI generado](docs/openapi-4.3.json)
- [Cambio y reversión del proxy público](docs/proxy-publico-4.3.md)
- [Preparación de la base y backend definitivos](docs/publicacion-4.3.md)
- [Migraciones, instrucciones Windows, despliegue y recuperación](docs/despliegue-4.3.md)
- [Matriz de evaluación P01–P17 y rotaciones](docs/matriz-4.3.md)
- [Revisión de pendientes y estado de cierre](docs/revision-final-4.3.md)
- [Historial de implementación y resultados](docs/plan-4.3.md)
- [Referencia del funcionamiento anterior 4.1–4.2](docs/referencia-4.1-4.2.md)

Variables del servidor: `DB_HOST`, `DB_PORT`, `DB_USER`, `DB_PASSWORD`, `DB_NAME`,
`IOT_AUTH_MODE`; `API_KEY` pertenece al modo anterior. Sus valores y respaldos
no se publican. El navegador nunca se conecta directamente a MySQL.

Con dependencias de `backend/requirements.txt` instaladas:

```bash
PYTHONPATH=backend python -m unittest discover -s backend/tests -q
python tools/exportar_contratos_4_3.py
```

Para Windows/RDS y frontend 8080 seguir el documento de despliegue. Los scripts
HTTP crean unidades nuevas sin hardware y conservan evidencia privada. Los
ensayos de control deben ejecutarse secuencialmente. Para pruebas físicas,
usar sólo funciones verificadas y un entorno supervisado.

## Límites de la verificación

El backend y sus tareas requieren un solo proceso. Un WS del navegador no
prueba conexión del microcontrolador. Un acuse SQL/HTTP no confirma movimiento
físico. Las capturas locales no sustituyen teléfono real, HTTPS/WSS público ni
las pruebas de tres plataformas con compañeros. Los fixtures de prueba deben
identificarse antes de elegir datos para la entrega final.
