# Localizar luces y sonido del motor, separados del claxon

Firmware temporal con los pines comprobados DS=5, latch=18, reloj=19. No anuncia READY IOT43 y no debe ejecutarse el puente mientras esté cargado. Compilar/cargar con Arduino IDE en la placa real; no se ha ejecutado automáticamente sobre el hardware.

Detener el puente y apagar el vehículo durante la carga. Abrir el monitor a 115200 y seleccionar Nueva línea. Al probar, mantener ruedas motrices libres, sin carga y el interruptor al alcance; un botón de función desconocida podría activar una función que siga después de soltar. No hay barrido automático.

Sólo admite canales aún no identificados: **1, 5, 8, 9, 11, 14, 16**. Bloquea los ya conocidos para no prolongar por accidente el claxon/apagado, una dirección o la demo autónoma.

- `C 5` y Enter: sólo canal 5 HIGH durante 250 ms, luego todas LOW.
- `L 5` y Enter: sólo canal 5 HIGH durante 3 s, luego todas LOW.
- `F 5` y Enter: sólo canal 5 HIGH durante 5 s, luego todas LOW.
- `S`: todas LOW inmediatamente; no necesita Enter. No garantiza cancelar una función autónoma del mando.

El 5 es ejemplo: usar el número concreto que se está comprobando. Primero probar C y observar las luces. Esperar que termine y al menos un segundo antes de otra prueba. Si se prueba L o F, observar tanto DURANTE el pulso como DESPUÉS del mensaje LIBERADO. Anotar exactamente qué sucede; no afirmar duración correcta sin observarlo.

No usar `T`, no activar todos los canales ni probar largas sobre canal 4 o 10. Si el vehículo actúa sin orden o no se detiene, apagarlo. Al terminar volver a cargar el firmware de integración antes de usar la web.

| Canal | Corto 250 ms | Largo 3 s + soltar | Largo 5 s + soltar |
|---|---|---|---|
| 1 | | | |
| 5 | | | |
| 8 | | | |
| 9 | | | |
| 11 | | | |
| 14 | | | |
| 16 | | | |
