# Montacargas IoT · Control, monitoreo y administración

Plataforma individual 4.1–4.3 en el repositorio original: HTML5, Bootstrap 5,
CSS, JavaScript modular, FastAPI, REST/WS y MySQL/RDS.

- **CONTROL:** joystick, botones compatibles, DETENER, demos y reserva exclusiva.
- **MONITOREO:** último estado, diez movimientos individuales e indicadores separados de API, RDS y sesión WS.
- **ADMINISTRACIÓN:** modelos/capacidades, unidades/comandos, compradores, asignaciones, dashboard, demos de empresa, soporte consentido y auditoría.
- **Comprador:** sus unidades, demos privadas y demos de empresa de sólo lectura.
- **Invitado:** catálogo publicado y prueba temporal de exhibición con límites.

## Estado real

La ampliación está validada sobre la copia aislada de RDS con migraciones
001–020. El alumno confirmó recuperación019, migración020, 18 pruebas SQL y
la prueba HTTP/WS de cierre completa (`cierre_4_3_3f0411c5de52.json`). El backend
activo devuelve4.3.0 y el frontend muestra dashboard e inventario; el filtro
MONT deja sólo MONT-001. **La publicación pública de4.3 y sus pruebas finales
siguen pendientes**.

[Hosting original](https://daddyleo23-max.github.io/4.1-Aplicaci-n-de-control-para-IoT/)
no se presenta como versión 4.3 aprobada. El `js/config.js` raíz conserva modo
anterior hasta la puesta en servicio; los ZIP de prueba habilitan sesiones y
API localhost 8001. No subir ese ZIP de pruebas a GitHub Pages.

## Documentación y ejecución

Si la entrega022 falló en 019 con ERROR1832, usar la [recuperación específica](docs/recuperacion-019.md); no repetir la migración completa sobre el estado parcial.

- [Arquitectura, ER y roles](docs/arquitectura-4.3.md)
- [Inventario de contratos antes/después](docs/inventario-contratos-4.3.md)
- [Contratos HTTP/WS](docs/contratos-4.3.md) y [OpenAPI generado](docs/openapi-4.3.json)
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
