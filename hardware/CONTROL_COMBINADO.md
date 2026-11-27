# Avance y giro simultáneos

Requiere frontend actualizado, backend con control_compuesto=true y firmware IOT43/6. Dos dedos controlan ambos joysticks. Soltar uno conserva el otro; soltar ambos, cambiar de pestaña o perder ventana solicita DETENER. Watchdog y renovación permanecen activos. No se reproducen órdenes al reconectar.

## Windows

Detener sólo backend8002 con Ctrl+C. Respaldar los cuatro archivos que contiene el ZIP de actualización. Extraer el ZIP y copiar app sobre C:\practica_4_3_publica\app conservando rutas. No reemplazar .env. Arrancar con el lanzador habitual iniciar_publicacion.py. No necesita migración SQL.

Comprobar en PowerShell:

    (Invoke-RestMethod 'http://127.0.0.1:8002/').control_compuesto
    (Invoke-RestMethod 'https://34.194.45.28/').control_compuesto

Ambos deben devolver True. POST movimientos admite el opcional id_comando_giro. Valida ambos comandos y capacidades, registra ambos en una transacción y publica una lista comandos en un solo evento. El historial conserva dos componentes individuales y el estado individual final es avance/retroceso. No representa medición física de ambos ejes. Un backend anterior sigue recibiendo comandos individuales.

## ESP32 y Linux

Cargar hardware/Montacargas_USB_43/Montacargas_USB_43.ino mediante Arduino IDE; cerrar monitor serie.

    python3 hardware/puente_usb.py --puerto /dev/ttyUSB0 --comprobar-usb

Pulsar EN cuando lo solicite. Debe anunciar READY IOT43/6. Luego:

    bash hardware/iniciar_puente.sh --activar

Adquirir control en la web actualizada y probar con ruedas libres y sin carga. Compilación, carga y pruebas físicas quedan por realizar manualmente.

## Luces / sonido de máquina

Primero puede cargarse temporalmente Diagnostico_Pulsaciones_ESP32 y seguir su LEEME. No ejecutar puente con ese sketch. Sólo canales desconocidos 1,5,8,9,11,14,16: C 5 pulso250ms, L 5 tres segundos, F 5 cinco segundos; S libera inmediatamente. Observar después de LIBERADO. No prolongar canal4 (claxon/apagado) ni10 (demo). Anotar canal y resultado; luces/sonido de máquina siguen sin habilitarse hasta confirmarlos. Después cargar IOT43/6.
