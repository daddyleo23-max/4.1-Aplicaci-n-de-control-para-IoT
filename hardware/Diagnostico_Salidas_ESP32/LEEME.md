# Identificar canales del mando

Sketch independiente: reemplaza temporalmente al firmware del puente. No ejecutar `puente_usb.py` con este diagnóstico cargado. No anuncia READY IOT43/6 y no entiende su protocolo.

Pines confirmados: DS GPIO5; STCP/latch GPIO18; SHCP/reloj GPIO19. Mantiene la secuencia de escritura de dos bytes del programa funcional, con 20 microsegundos entre bytes y latch HIGH→LOW.

1. Detener el puente y apagar el vehículo durante la carga. No cambiar el cableado para esta prueba.
2. Abrir `Diagnostico_Salidas_ESP32.ino` en Arduino IDE, seleccionar la misma placa y puerto, compilar y cargar. Este sketch requiere comprobación en esa placa; no se ha compilado ni cargado automáticamente desde el agente.
3. Abrir monitor serie a 115200 baudios y seleccionar **Nueva línea** o **Ambos NL/CR**. Si no aparece el encabezado, pulsar EN/RESET.
4. Con ruedas motrices libres, sin carga y acceso al interruptor, probar manualmente un número 1..16 y Enter. Sólo un canal va HIGH durante 250 ms. Después todos vuelven LOW; el programa rechaza nuevas selecciones durante el pulso y los siguientes 500 ms. No hace barridos ni guarda órdenes para ejecutarlas después.
5. Anotar la respuesta. No dejar botones físicos presionados mientras se prueban las salidas añadidas. Apagar el vehículo si actúa sin orden o no se detiene.

`S` pone las salidas LOW inmediatamente y no necesita Enter. No hay `T`, modos de todos HIGH ni pulsación larga.

LOW significa soltar las salidas según la lógica positiva del montaje probado; no es una confirmación física de parada. Un botón con función de alternancia (encendido, luces, velocidad o demo del mando) puede mantener su efecto después del pulso. La demo autónoma puede seguir moviendo el vehículo aunque se liberen las salidas: usar el interruptor si fuera necesario. Si un canal no responde con un toque corto, anotar **sin respuesta con 250 ms**; no concluir automáticamente que está sin conectar.

Diez cables conectados no aseguran que correspondan a canales 1..10. Hay 16 posiciones posibles entre los dos registros; conservar la numeración del programa anterior. Los números 2=avance y 3=retroceso se comunicaron previamente; reconfirmar con alimentación estable.

| Número enviado | Respuesta observada |
|---|---|
| 1 | |
| 2 | Avance confirmado |
| 3 | Retroceso confirmado |
| 4 | Claxon |
| 5 | |
| 6 | Velocidad confirmada |
| 7 | Subir pala |
| 8 | |
| 9 | |
| 10 | Demo autónoma del mando |
| 11 | |
| 12 | Giro izquierdo (corregido) |
| 13 | Giro derecho (corregido) |
| 14 | |
| 15 | Bajar pala |
| 16 | |

Entregar la lista observada antes de habilitar más funciones en el firmware de integración. El puente no debe ejecutarse hasta volver a cargar su firmware correcto.
