# Montacargas IoT · Control y monitoreo

Aplicación web responsiva del montacargas que reutiliza la API FastAPI existente e integra dos vistas:

- **Práctica 4.1.1 · Aplicación de control para IoT:** mando con dos joysticks, botones, DETENER y secuencias DEMO. En teléfono horizontal el mando ocupa el área principal.
- **Práctica 4.2 · Aplicación de monitoreo para IoT:** último movimiento reportado, hasta diez movimientos individuales persistidos y tres indicadores independientes para WSS, API AWS y Amazon RDS.

[Abrir la aplicación publicada en GitHub Pages](https://daddyleo23-max.github.io/4.1-Aplicaci-n-de-control-para-IoT/)

**Verificación:** CONTROL se probó desde computadora y teléfono con la API activa. En MONITOREO se comprobaron los eventos de un cliente externo, la presentación del historial y la reconexión. Queda por comprobar el historial vacío y documentar MONITOREO en un teléfono físico con la última versión publicada.

## Estado de integración

Se configuraron como referencia la API `https://34.194.45.28`, el vehículo `1`, el health check `/health/db` y el WebSocket `wss://34.194.45.28/ws/vehiculos/1`. Los contratos locales revisados indican estos recursos:

- `GET /`, `GET /health/db`
- `GET /vehiculos/1`, `GET /vehiculos/1/comandos`, `GET /vehiculos/1/demos`
- `POST /vehiculos/1/movimientos` con `{"id_comando": n}`
- `POST /vehiculos/1/demos/{id_demo}/iniciar`
- `POST /vehiculos/1/demos/cancelar`
- `WS /ws/vehiculos/1`

Las rutas de escritura requieren `X-API-Key`. En `localhost`, el proyecto puede cargarla desde `js/auth.local.js`, archivo excluido de Git. En otros hosts, exige HTTPS y muestra un campo para que el usuario escriba la clave para esa pestaña: se guarda solo en memoria y se elimina al recargar/cerrar. La clave nunca debe agregarse al código, a `config.js`, al repositorio ni compartirse en el chat. Quien controla el navegador que la introduce puede inspeccionarla; el formulario evita publicar una clave preconfigurada, pero no sustituye una autenticación por usuario en el backend. CORS debe permitir exactamente el origen desplegado.

El catálogo de comandos se lee de la API y cada control se enlaza por el nombre activo devuelto; los códigos no están hardcodeados. El mando web replica el modelo nuevo: joystick izquierdo para avanzar/retroceder, joystick derecho para girar, y botones para velocidad, luces, horquilla y DEMO. El botón combinado envía LUCES al pulsarlo corto y solo enviará MÚSICA si la API publica un comando separado MUSICA/MUSIC. El botón central envía SONIDO como claxon en pulsación corta; la pulsación larga de encendido permanece deshabilitada en el frontend porque POWER está desactivado en el firmware compartido.

En una consulta al servidor activo se confirmó el catálogo de 13 registros para el vehículo 1. El comando 12 MODO_CRUCE se desactivó desde Swagger y se conservaron sus datos e historial. Los demás nombres e IDs permanecen: 1 ADELANTE, 2 ATRAS, 3 GIRAR_IZQUIERDA, 4 GIRAR_DERECHA, 5 SUBIR_HORQUILLA, 6 BAJAR_HORQUILLA, 7 LUCES, 8 SONIDO, 9 VELOCIDAD, 10 DEMO, 11 POWER y 13 DETENER. La DEMO 1 (Demo principal) tiene nueve pasos y no usa el comando 12. La API también devuelve una DEMO 2 activa con nombre string; debe revisarse antes de presentarla.

El sketch ESP32 compartido asigna pulsos temporizados a los comandos. En ese archivo `POWER` está deshabilitado, `DEMO` debe iniciarse mediante su endpoint dedicado y las salidas se liberan al recibir DETENER o perder WSS/Wi-Fi. La interfaz marca POWER como no verificado para ese firmware y no presenta luces o velocidad como estado físico confirmado. El sketch aún no se ha probado en el circuito.

## Ampliación 4.2: MONITOREO

La práctica 4.2 amplía esta misma aplicación y repositorio con las vistas CONTROL y MONITOREO. CONTROL mantiene el mando, DETENER y DEMO. MONITOREO consulta el estado e historial mediante los GET existentes y comparte una sola sesión WSS con CONTROL. No requiere conexión física del ESP32 ni cambios en FastAPI, RDS o procedimientos almacenados.

### Módulos

- `index.html`: estructura común, indicadores, navegación CONTROL/MONITOREO y tabla semántica.
- `js/config.js`: URL de API, WSS, ID de vehículo y timeout.
- `js/api-client.js`: cliente Fetch existente; incluye `vehicleState()` (`GET /vehiculos/{id}/estado`) y `vehicleHistory()` (`GET /vehiculos/{id}/historial`).
- `js/websocket-client.js`: conexión WSS única, reconexión progresiva y distribución de eventos a ambas vistas.
- `js/monitoring.js`: sincronización inicial y al volver a la vista; actualiza la tarjeta con estado/eventos del mismo vehículo y reconcilia la tabla mediante historial REST solo tras movimiento individual.
- `js/connection-status.js`: indicadores independientes de salud de API y diagnóstico RDS; WSS indica la sesión del navegador, no presencia física.

### Contratos confirmados

- Estado: `GET /vehiculos/1/estado`, campos observados `id_vehiculo`, `vehiculo`, `id_comando`, `comando`, `codigo`, `conectado`, `fecha_actualizacion`.
- Historial: `GET /vehiculos/1/historial`, hasta diez movimientos con `id_historial`, `id_vehiculo`, `comando`, `codigo`, `fecha_hora` y `origen`.
- WSS: `wss://34.194.45.28/ws/vehiculos/1`. Los eventos `movimiento` desencadenan reconciliación REST. Eventos DEMO pueden actualizar la tarjeta, no las filas individuales.
- Los GET de estado e historial devuelven fechas sin sufijo de zona. Se contrastó `fecha_actualizacion` con el evento WSS del mismo instante: el valor REST corresponde a UTC sin sufijo, por lo que el frontend lo interpreta como UTC y lo presenta en `America/Mexico_City`. Los eventos WSS con offset se convierten desde el offset recibido.
- RDS se marca disponible solo con el diagnóstico real de `/health/db`. Ninguna vista convierte una respuesta HTTP o evento WSS en confirmación de movimiento físico.

### Ejecución y comprobación

Desde la carpeta del proyecto inicia un servidor local compatible con módulos ES usando `python3 -m http.server 8080 --bind 127.0.0.1` y abre `http://127.0.0.1:8080`. El origen `127.0.0.1:8080` está permitido por CORS; otro puerto como `8083` puede mostrar la interfaz, pero la API bloqueará las consultas del navegador. También se puede publicar el mismo repositorio en GitHub Pages. Entra en MONITOREO para cargar estado e historial; ejecuta un movimiento desde CONTROL u otra sesión WSS y comprueba que la tarjeta cambia y que la tabla se resincroniza desde la API. Prueba además historial vacío, más de diez registros, evento de otro vehículo, DEMO, pérdida y reconexión WSS, red móvil/escritorio y el cliente WSS independiente. Las pruebas físicas del ESP32 quedan fuera de 4.2.

No se almacena API key en módulos públicos ni se necesita una clave para los GET de monitoreo. No publiques `js/auth.local.js`; está excluido por `.gitignore`. Las rutas de assets y módulos son relativas para GitHub Pages.

## Estructura

```text
control-iot/
├── assets/favicon.svg
├── css/styles.css
├── js/
│   ├── api-client.js
│   ├── auth-session.js
│   ├── auth.local.example.js
│   ├── config.js
│   ├── connection-status.js
│   ├── joystick.js
│   ├── main.js
│   ├── monitoring.js
│   ├── ui.js
│   └── websocket-client.js
├── tools/escuchar_ws.py
└── index.html
```

## Ejecución local

Sirve esta carpeta con un servidor estático local y abre su URL HTTPS/HTTP local. Por ejemplo, con Python: `python -m http.server 8080`. La API de AWS debe permitir CORS desde el origen local; GitHub Pages requerirá además autorizar el origen publicado.

El indicador de AWS consulta `/`; el de RDS consulta `/health/db`, que devuelve el resultado real de la conexión MySQL. El indicador WebSocket se basa exclusivamente en la conexión WSS del navegador. Ninguno confirma que un motor físico haya actuado.

## Escuchar eventos WSS desde una terminal Linux

El proyecto incluye `tools/escuchar_ws.py`, adaptado del cliente de consola de la práctica 2.5. Es una segunda conexión independiente: escucha los eventos del vehículo 1 e imprime cada mensaje JSON. No manda comandos REST ni controla el carrito.

Desde la carpeta del proyecto, en una terminal:

```bash
python3 tools/escuchar_ws.py
```

Si Python indica que falta `websockets`, crea un entorno aislado e instala esa dependencia:

```bash
python3 -m venv .venv-ws
source .venv-ws/bin/activate
python -m pip install websockets
python tools/escuchar_ws.py
```

Deja esa terminal escuchando. Abre la página web en el navegador y pulsa una función; el evento que publique la API aparecerá en la terminal. Al conectarse también debe llegar el estado inicial si el servidor lo tiene implementado. Pulsa `Ctrl+C` para cerrar el cliente. Una respuesta HTTP y un evento confirman la comunicación con el backend, no movimiento físico del montacargas.

## Pruebas de integración verificadas

Se observaron los eventos con `tools/escuchar_ws.py` en una conexión independiente del navegador:

- Movimientos manuales desde la página: ADELANTE, giros, horquilla, luces, sonido y velocidad publicaron eventos correlacionados con sus IDs y códigos.
- DETENER manual: el servidor publicó `movimiento` con el comando 13.
- DEMO 1: se publicaron `demo_inicio`, los nueve pasos en orden y `demo_fin`.
- Cancelación de DEMO 1: al cancelar durante la secuencia, se recibió `demo_cancelada` con `comando_seguridad: DETENER`.
- Joystick: al arrastrar hacia ADELANTE y soltar, se recibieron primero ADELANTE y después DETENER. Se serializó el envío REST para preservar ese orden.
- Vista LAN: el catálogo de 13 comandos y las DEMOs cargan tras autorizar el origen CORS; también se revisó el diseño con un viewport de 390 × 844 CSS px.

Estas pruebas comprueban la comunicación y el estado lógico del backend. El estado inicial WSS reportó `conectado: 0`; no se verificó movimiento físico del vehículo. La vista móvil se revisó con un viewport emulado, pero aún falta probarla en un teléfono real.

## Publicación en GitHub Pages

El sitio usa rutas relativas para funcionar bajo la subruta del repositorio. Para completar la publicación, habilita GitHub Pages para la rama `main` y la carpeta raíz (`/(root)`). La API debe permitir en CORS el origen HTTPS publicado de Pages; de lo contrario, el navegador bloqueará las consultas y comandos aunque la API funcione en Swagger.

En `localhost`, la clave puede cargarse desde `js/auth.local.js`, que Git ignora. En un sitio HTTPS, el usuario la introduce en el panel de autorización y queda solo en memoria durante esa pestaña. No agregues la clave al código, al repositorio ni a las capturas.
