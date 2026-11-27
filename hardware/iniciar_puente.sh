#!/usr/bin/env bash
# Configuración local sin contraseñas. Por defecto sólo simula.
set -euo pipefail
DIRECTORIO_PUENTE="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
PYTHON_PUENTE="${IOT_BRIDGE_PYTHON:-python3}"
if ! "$PYTHON_PUENTE" -c 'import serial; import websockets.asyncio.client' >/dev/null 2>&1; then
  echo 'Faltan pyserial o websockets en el Python seleccionado.' >&2
  echo "Instala hardware/requirements.txt en un entorno virtual y selecciona su Python con IOT_BRIDGE_PYTHON." >&2
  exit 1
fi
printf '%s\n' 'Puente para MONT-001: avance, retroceso, ambos giros, pala, velocidad y claxon corto.'
printf '%s\n' 'La activación USB exige --activar y firmware READY IOT43/5. Sin esa opción sólo simula.'
exec "$PYTHON_PUENTE" "$DIRECTORIO_PUENTE/puente_usb.py" \
  --api https://34.194.45.28 --unidad 1 --puerto /dev/ttyUSB0 --diagnostico \
  --permitir ADELANTE ATRAS GIRAR_IZQUIERDA GIRAR_DERECHA SUBIR_HORQUILLA BAJAR_HORQUILLA SONIDO VELOCIDAD "$@"
