# Puente USB para el montacargas 4.3

Estado: implementación inicial. Doce pruebas Python pasan, incluida recepción de una orden nueva y parada al cerrar el canal con conexiones simuladas. El firmware todavía debe compilarse para la placa concreta, cargarse y comprobarse físicamente. No se ha abierto ni escrito el puerto físico durante el desarrollo.

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

1. Conservar el sketch original. El firmware nuevo está en `Montacargas_USB_43/Montacargas_USB_43.ino`. Mantiene GPIO21 (DS), GPIO18 (SHCP) y GPIO19 (STCP), como el archivo ESP32 existente.
2. Compilar y cargar desde Arduino IDE con la placa y puerto reales. Durante la carga y el primer ensayo, mantener el vehículo sin posibilidad de desplazamiento y con acceso a su interruptor de alimentación.
3. Comprobar que aparece `READY IOT43/1` al reiniciar. Cerrar el monitor serie antes de usar el puente: sólo un programa debe abrir el puerto.
4. Para el primer ensayo físico, activar explícitamente:

```bash
python3 hardware/puente_usb.py --unidad 1 --puerto /dev/ttyUSB0 --activar
```

El puente espera pasivamente el saludo del firmware nuevo. Si no lo recibe en cinco segundos, cerrar y volver a abrir o reiniciar la placa durante esa espera. No escribe mensajes de comprobación al firmware antiguo: podría interpretar letras como órdenes. La apertura del puerto puede reiniciar el ESP32.

Por defecto sólo se reenvían ADELANTE y DETENER. Verificar un pulso corto y una parada antes de habilitar otras funciones. Los demás comandos se habilitan expresamente con `--permitir` después de verificar su cableado y respuesta. POWER y la demo autónoma del mando no se reenvían en esta primera versión.

## Límites y recuperación

- Estado inicial, historial y órdenes de otra unidad no se reproducen. Órdenes atrasadas, duplicadas, sin fecha con zona horaria o no permitidas producen STOP.
- El puente comprueba la reserva activa por REST y la conexión por ping/pong. Si pierde vigencia, conectividad, autorización o ocurre un error, deja de mantener el movimiento y solicita STOP por USB. La sesión del puente se cierra al salir.
- El firmware arranca con todas las salidas a cero. Necesita ARM y heartbeat. Si pasan 800 ms sin heartbeat, detiene y desarma las salidas. No usa `delay()` para los pulsos, de modo que STOP puede interrumpirlos.
- Hay un límite adicional de un segundo por orden continua de movimiento. No se reproduce automáticamente una orden después de una parada. Las demos con pasos mayores pueden detenerse antes de su duración configurada: verificar secuencias breves en esta primera fase.
- Se esperan hasta 3 s para el ping WSS y las consultas de control, con una vigencia máxima de 3.5 s para las comprobaciones. El watchdog USB de 800 ms y el límite de un segundo por movimiento son independientes de ese presupuesto de red.
- Una pérdida de red tarda en detectarse; el watchdog no equivale a una parada instantánea desde que se corta Internet. La distancia de frenado y la respuesta real requieren medición.
- `APPLIED` sólo indica aplicación de las salidas GPIO. No demuestra desplazamiento, frenado físico, posición ni recepción por radio. El indicador WSS de la web sigue representando la conexión del navegador.
- Antes de desconectar, usar DETENER y cerrar el puente. Desconectar USB no sustituye el interruptor del vehículo. No se ha verificado aquí una entrada hardware de deshabilitación de los 74HC595 durante reinicios o fallos eléctricos.

Pruebas sin hardware:

```bash
python3 -m unittest discover -s hardware -p 'test_*.py' -v
```
