# Puente USB para el montacargas 4.3

Estado: implementación inicial. Veinticuatro pruebas Python y seis pruebas de botones pasan, incluida recepción de una orden nueva y parada al cerrar el canal con conexiones simuladas. El firmware todavía debe compilarse para la placa concreta, cargarse y comprobarse físicamente. No se ha abierto ni escrito el puerto físico durante el desarrollo.

## Recorrido

Navegador del comprador → reserva y canal de control existentes → FastAPI → canal de monitoreo autenticado de la unidad → puente Python en Linux → USB → ESP32 → 74HC595/PC817 → mando RC.

El puente inicia una sesión separada del mismo comprador propietario y escucha `/ws/vehiculos/1`. No adquiere ni renueva la reserva del navegador. No requiere nuevas rutas, migraciones, claves compartidas ni cambios en el backend. No utiliza las unidades de software para mover hardware.

## Primera comprobación: sin salida USB

Arrancar el backend público y Caddy con las instrucciones habituales. En Linux:

```bash
cd /home/daddyleo/Documents/Codex/2026-11-06/ho/outputs/control-iot
python3 hardware/puente_usb.py --unidad 1
```

Introducir `comprador.prueba@example.com` y su contraseña de aplicación. En el sitio, iniciar sesión con ese comprador, seleccionar MONT-001 y adquirir control. Un toque de ADELANTE debe imprimir `SIMULACIÓN USB: C W` en la terminal. Soltar y DETENER deben ser procesados sin movimiento real por este puente. Ctrl+C lo cierra. Nunca se imprime el token ni se guarda la contraseña. La simulación no abre el puerto serie.

Dependencias si faltan: crear un entorno virtual e instalar `hardware/requirements.txt`. En el equipo comprobado ya están pyserial 3.5 y websockets 15.0.1. Se detectó `/dev/ttyUSB0`, adaptador CP2102; volver a verificar si cambia de puerto.

## Preparación física, después de aprobar la simulación

1. Conservar el sketch original. El firmware nuevo está en `Montacargas_USB_43/Montacargas_USB_43.ino`. Se corrigió el mapa para coincidir con el sketch numérico aportado: GPIO5 (DS), GPIO19 (SHCP/reloj) y GPIO18 (STCP/latch), incluidas las pausas de 20 microsegundos entre bytes y el retorno de latch a LOW. El archivo ESP32 usado inicialmente como referencia tenía otros pines y no correspondía al cableado confirmado. Se confirmaron únicamente número 2=avance (bit 1) y número 3=retroceso (bit 2). El firmware IOT43/6 incluye el mapa ampliado de canales confirmados que se detalla al final; cualquier función no identificada solicita STOP. DETENER pone todas las salidas en LOW. No se conservaron las asignaciones de giro/horquilla del archivo de referencia equivocado. La alimentación debe estar estable antes de una nueva prueba física.
2. Compilar y cargar desde Arduino IDE con la placa y puerto reales. Durante la carga y el primer ensayo, mantener el vehículo sin posibilidad de desplazamiento y con acceso a su interruptor de alimentación.
3. Comprobar que aparece `READY IOT43/6` al reiniciar. Cerrar el monitor serie antes de usar el puente: sólo un programa debe abrir el puerto.
4. Para el primer ensayo físico, activar explícitamente:

```bash
python3 hardware/puente_usb.py --unidad 1 --puerto /dev/ttyUSB0 --activar
```

El puente espera pasivamente el saludo del firmware nuevo. Muestra un aviso al abrir el puerto y espera 20 segundos: pulsar EN/RESET en ese momento (no BOOT). Si no recibe el saludo, cierra sin escribir órdenes. No escribe mensajes de comprobación al firmware antiguo: podría interpretar letras como órdenes. La apertura del puerto puede reiniciar el ESP32.

Por defecto sólo se reenvían ADELANTE y DETENER. Verificar un pulso corto y una parada antes de habilitar otras funciones. Para incluir retroceso, ya confirmado en el programa numérico, usar `--permitir ADELANTE ATRAS`. Las funciones no identificadas requieren primero confirmar y configurar su salida física en el firmware; `--permitir` por sí solo no los habilita en la placa. POWER y la demo autónoma del mando no se reenvían en esta primera versión.

## Límites y recuperación

- Estado inicial, historial y órdenes de otra unidad no se reproducen. Órdenes atrasadas, duplicadas, sin fecha con zona horaria o no permitidas producen STOP.
- El puente comprueba la reserva activa por REST y la conexión por ping/pong. Si pierde vigencia, conectividad, autorización o ocurre un error, deja de mantener el movimiento y solicita STOP por USB. La sesión del puente se cierra al salir.
- El firmware arranca con todas las salidas a cero. Necesita ARM y heartbeat. Si pasan 800 ms sin heartbeat, detiene y desarma las salidas. No usa `delay()` para los pulsos, de modo que STOP puede interrumpirlos.
- IOT43/6 ya no corta cada movimiento al segundo: C W 0 representa movimiento manual renovable con R cada 150 ms mientras las comprobaciones de red y reserva estén vigentes. Si deja de llegar R, el movimiento se libera tras 900 ms; si falta H, el watchdog detiene y desarma tras 800 ms. Una parada borra la orden: recuperar la red no la reproduce. Las demos reciben duración explícita de 1..10000 ms y no se renuevan; se liberan durante sus pausas.
- Se esperan hasta 3 s para el ping WSS y las consultas de control, con una vigencia máxima de 3.5 s para las comprobaciones. El watchdog USB de 800 ms y la renovación de movimiento de 900 ms son independientes de ese presupuesto de red.
- Una pérdida de red tarda en detectarse; el watchdog no equivale a una parada instantánea desde que se corta Internet. La distancia de frenado y la respuesta real requieren medición.
- `APPLIED` sólo indica aplicación de las salidas GPIO. No demuestra desplazamiento, frenado físico, posición ni recepción por radio. El indicador WSS de la web sigue representando la conexión del navegador.
- Antes de desconectar, usar DETENER y cerrar el puente. Desconectar USB no sustituye el interruptor del vehículo. No se ha verificado aquí una entrada hardware de deshabilitación de los 74HC595 durante reinicios o fallos eléctricos.

Pruebas sin hardware:

```bash
python3 -m unittest discover -s hardware -p 'test_*.py' -v
```


## Mapa observado con el diagnóstico (26 de noviembre)

| Canal | Bit | Función | Protocolo USB |
|---|---|---|---|
| 2 | 1 | Adelante | C W 0 |
| 3 | 2 | Atrás | C S 0 |
| 4 | 3 | Claxon, pulso de 250 ms | C N 0 |
| 6 | 5 | Cambiar velocidad (pulso 250 ms) | C V 0 |
| 7 | 6 | Subir pala | C E 0 |
| 12 | 11 | Giro izquierdo | C A 0 |
| 13 | 12 | Giro derecho | C D 0 |
| 15 | 14 | Bajar pala | C Q 0 |

Corrección posterior del alumno: canal 12=izquierda y canal 13=derecha. Canal 6=velocidad confirmada (bit 5), pulso corto de 250 ms; canal 10=demo autónoma (bit 9), identificada pero no habilitada porque soltar el botón no garantiza cancelarla. Luces, encendido/apagado y demo autónoma no se habilitan. El claxon ignora repeticiones mientras su pulso esté activo y exige un segundo antes de otro toque; no tiene pulsación larga.

El firmware actualizado se identifica como READY IOT43/6. El puente exige esa versión para no confundirlo con el firmware anterior de pines o canales distintos. Primero cargar y comprobar con vehículo apagado. Después de una prueba de avance/STOP satisfactoria, se pueden incluir las funciones confirmadas mediante:

```bash
python3 hardware/puente_usb.py --unidad 1 --puerto /dev/ttyUSB0 --activar --diagnostico --permitir ADELANTE ATRAS GIRAR_IZQUIERDA GIRAR_DERECHA SUBIR_HORQUILLA BAJAR_HORQUILLA SONIDO VELOCIDAD
```

El puente sigue permitiendo por defecto únicamente ADELANTE y DETENER. Comprobar cada función física por separado, no una demo completa. La versión IOT43/6 sustituye el límite fijo de un segundo por una renovación manual de 900 ms; conserva el watchdog de 800 ms y añade duración explícita para cada paso de demo. La corrección de mapa no equivale a una prueba física ya aprobada.


Para los lanzadores preconfigurados de Windows y Linux, consultar [ARRANQUE.md](ARRANQUE.md).

La versión IOT43/6 añade velocidad confirmada por el alumno. No informa un nivel numérico de velocidad: solicita el cambio del mando y no presupone cuántos niveles hay ni cuál estaba seleccionado. El puente y el firmware deben actualizarse juntos.


## Si el monitor muestra READY pero el puente no lo detecta

Con vehículo apagado y monitor serie cerrado, comprobar únicamente USB, sin login ni acceso a AWS:

```bash
python3 hardware/puente_usb.py --puerto /dev/ttyUSB0 --comprobar-usb
```

Pulsar EN/RESET cuando indique que abrió el puerto. Muestra trazas de arranque conocidas, la versión recibida y distingue silencio de USB de un firmware diferente. Acumula fragmentos de lectura hasta completar una línea. No envía ARM ni movimientos; sólo libera las salidas al cerrar si identificó la versión correcta. No aumentar la activación ni repetir la carga sin revisar ese diagnóstico.
