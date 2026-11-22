# Activación del proxy público 4.3

Estado previo confirmado por el alumno: backend definitivo8002 devuelve4.3.0,
health/db conectadoTrue, vehiculo_iot_43 y MySQL8.4.9. La clonación íntegra fue
aprobada en publicacion_base_20261122-192805-949141.json.

La API pública sigue detrás de C:\caddy\Caddyfile.prod y proxy8000. Se prepara
cambio exclusivo de destino a8002. El frontend de GitHub Pages aún requiere
publicar el commit de sesiones después de comprobar la API pública nueva.

## Ejecutar en la instancia Windows

Mantener abiertas las terminales de Caddy, backend definitivo8002 y backend
anterior8000 (este último permite reversión). Extraer activar_proxy_4_3.zip en
C:\publicacion_4_3. Desde C:\practica_2_6_iot:

```powershell
.\.venv\Scripts\python.exe C:\publicacion_4_3\gestionar_proxy_4_3.py activar
```

No pide contraseña RDS ni cambia MySQL. Sí cambia el destino de la API pública.
Antes compara Caddyfile con configuración activa, guarda respaldo, comprueba
8002 y el HTTPS anterior, verifica que el cambio nativo sólo modifica el dial
8000→8002 y valida con el caddy.exe instalado. Luego recarga sin detener Caddy,
comprueba versión4.3.0 y base definitiva vía HTTPS y persiste el Caddyfile.
Si falla la comprobación/persistencia, intenta restaurar proxy y archivo
anteriores; si no puede confirmar esa reversión lo indica expresamente.

Éxito esperado: «API HTTPS verificada:4.3.0 · vehiculo_iot_43 · conectadoTrue».
Compartir sólo salida/informe del plan, no archivos privados de configuración.
Los respaldos y JSON nativos de Caddy pueden contener información privada y
permanecen en respaldos_rds, excluidos del repositorio/hosting.

El script conserva certificado, sitio, cabeceras y demás directivas. Rechaza
varios destinos coincidentes, proxy no reconocido, administración fuera de
loopback/deshabilitada o cambios ajenos. No habilita el administrador de Caddy,
no desactiva verificación TLS y no instala certificados. No lee .env.

Para preparar sin activar se admite `preparar`. Para volver al backend anterior:

```powershell
.\.venv\Scripts\python.exe C:\publicacion_4_3\gestionar_proxy_4_3.py revertir --plan "RUTA_DEL_PLAN_GENERADO\plan_proxy_4_3.json"
```

Usar la ruta exacta impresa por la activación. La reversión sólo procede si la
configuración coincide con ese despliegue; no sobrescribe cambios desconocidos.
La API8000 debe mantenerse abierta. No ejecutar otra activación a ciegas si falla.

## Comprobación pública posterior

Después de activar y publicar el frontend se ejecutará:

```powershell
.\.venv\Scripts\python.exe C:\publicacion_4_3\probar_publicacion_4_3.py
```

Pide correo/contraseña del administrador de APLICACIÓN. Usa HTTPS/WSS público,
unidades NUEVAS de software y comprueba exclusividad, DETENER, demos, catálogo,
resumen, auditoría y límites. No mueve unidad1 ni confirma recepción física.
Conserva registros de prueba privados/inactivos y un informe JSON sin tokens.

## Verificación y límites

142 pruebas unitarias correctas. Ensayo con Caddy oficial2.11.9 local y dos
backends HTTP desechables: activación, persistencia, reversión explícita,
reversión por fallo de salud pública y por persistencia parcial, y rechazo de
cambios concurrentes. El ensayo local de recarga fue HTTP; no se presenta como
prueba pública WSS/TLS. La URL pública anterior se comprobó separadamente con
TLS válido y versión1.0.0. La ejecución Windows y el recorrido HTTPS/WSS nuevo
se confirmarán con el informe del alumno.

Se usa recarga y validación conforme a la [documentación oficial de Caddy](https://caddyserver.com/docs/command-line#caddy-reload).
La recarga también puede cerrar canales WS; realizar el cambio sin operaciones
activas y adquirir una nueva reserva después, como requiere el flujo normal.
