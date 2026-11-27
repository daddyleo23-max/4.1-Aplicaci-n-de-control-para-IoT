# Arranque preparado: servidor Windows y puente Linux

Son dos computadoras: el servidor EC2 Windows ejecuta FastAPI/Caddy; la computadora Linux conectada por USB ejecuta el puente. GitHub Pages sirve la página sin servidor frontend local. Los scripts no instalan servicios permanentes ni cambian claves, migraciones o configuración de red.

## 1. Firmware Arduino

Abrir de nuevo el archivo `Montacargas_USB_43/Montacargas_USB_43.ino` para evitar compilar una pestaña con una versión anterior. Seleccionar la placa real y el puerto, compilar y cargar con el vehículo apagado y el puente detenido. El monitor serie a 115200 debe mostrar `READY IOT43/5`; luego cerrarlo antes de usar el puente.

Mapa: 2 avance, 3 retroceso, 4 claxon corto, 7 subir pala, 12 izquierda, 13 derecha, 15 bajar pala. Pines: DS=5, STCP=18, SHCP=19. Sólo un movimiento a la vez; claxon 250 ms con separación mínima de un segundo; movimiento manual renovable mientras haya reserva y conexión vigentes; watchdog USB de 800 ms y renovación de movimiento de 900 ms. No se habilitan luces, sonido largo ni demo autónoma. Velocidad usa el canal 6 con un pulso de 250 ms y separación mínima de un segundo. Las demos de la web son secuencias del servidor y cada paso usa su duración recibida, con máximo de 10 segundos. Las pausas liberan las salidas.

El firmware requiere compilación y prueba en la placa real. No se ha cargado ni ejecutado automáticamente en hardware.

## 2. PowerShell en el servidor Windows

Iniciar laboratorio/EC2 y esperar que RDS esté disponible. Copiar `iniciar_servidor_43.ps1` a `C:\iniciar_servidor_43.ps1`. Abrir PowerShell de Windows y ejecutar:

```powershell
& C:\iniciar_servidor_43.ps1
```

El script comprueba las rutas existentes, abre el backend en otra consola si 8002 está libre y verifica versión/base. Si hay un proceso que no responde, se detiene con un mensaje; no mata procesos ni inicia duplicados. Abre Caddy sólo si no existe, valida la configuración existente y comprueba el destino público por HTTPS. Mantener abiertas las dos ventanas de servicios. No cambiar políticas de ejecución del equipo; si PowerShell bloquea el archivo, proporcionar el error para resolverlo en el contexto del laboratorio.

Se conserva `https://34.194.45.28`; si cambia la IP pública, hay que revisar también Caddy y la configuración de la página/puente. Pasar otra IP a este script no actualiza automáticamente los otros componentes.

El script se revisó estáticamente en Linux; la ejecución real en Windows queda por comprobar con su salida.

## 3. Terminal de Linux

Desde el repositorio:

```bash
cd /home/daddyleo/Documents/Codex/2026-11-06/ho/outputs/control-iot
bash hardware/iniciar_puente.sh
```

Ese comando simula todas las funciones confirmadas sin abrir el USB. Para activar físicamente, después de cargar y comprobar el firmware correcto:

```bash
bash hardware/iniciar_puente.sh --activar
```

Introduce correo y contraseña de aplicación del propietario de MONT-001 (no las credenciales de RDS). Cuando aparezca que abrió `/dev/ttyUSB0`, pulsa EN/RESET para que el puente identifique el firmware. La terminal debe quedar abierta. No se guardan ni imprimen credenciales.

Conservar ruedas motrices libres y sin carga en la primera prueba. En la página iniciar sesión como propietario, elegir MONT-001 y adquirir control. Probar primero avance y DETENER, después cada función por separado. El script permite sólo los comandos confirmados; no puede encender el mando/vehículo físicamente. Si una función queda activa o actúa sin orden, apagar el vehículo y detener el puente.

## 4. Cierre

Pulsar DETENER, liberar control y cerrar el puente con Ctrl+C. Después apagar el vehículo. Si se termina la sesión, parar backend y Caddy con Ctrl+C en sus respectivas ventanas y finalizar el laboratorio según sus reglas. No repetir migraciones al volver a arrancar.


## Mantener pulsado y red intermitente (IOT43/5)

Los botones Subir y Bajar de la página envían movimiento al presionar y DETENER al soltar, cancelar, perder el foco o cambiar de pestaña. Recargar la página para obtener esta actualización. El control espera a que termine un STOP pendiente antes de aceptar otro movimiento y descarta movimientos encolados que fueron reemplazados.

El firmware debe actualizarse a IOT43/5 para que funcione con el puente actual. El canal USB exige una renovación de movimiento manual cada 900 ms y heartbeat cada 800 ms; el puente envía esas señales sólo con verificaciones recientes. No se reenvían repetidamente peticiones de movimiento al servidor para mantener la pala.

Si una consulta de reserva falla temporalmente, el puente solicita STOP y vuelve a comprobar la reserva; no reanuda la orden anterior. Los errores de permisos y los cierres WSS siguen cerrando el puente. Si la red se pierde antes de poder verificarse el fallo, existe el plazo de detección de hasta 3.5 s más el tiempo del watchdog; no equivale a una parada física instantánea. Soltar en la web depende también de la latencia REST/WSS.

Pruebas locales: `python3 -m unittest discover -s hardware -p 'test_*.py' -q` y `node --test hardware/test_hold_command.mjs`. No sustituyen la compilación para la placa y una prueba física supervisada de mantener/soltar.
