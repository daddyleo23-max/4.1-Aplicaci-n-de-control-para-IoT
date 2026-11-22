# Puesta en servicio y recuperación 4.3

**Si 019 falló con ERROR1832, no repetirla:** seguir [recuperación específica](recuperacion-019.md). La versión de 019 de la entrega inicial022 tenía el orden FK/NOT NULL incorrecto.

Estado: preparado para validar en copia. La URL pública no fue actualizada ni
comprobada en esta entrega. Las pruebas locales usan MariaDB 12.3.2 sobre un
esquema reconstruido; el destino real es MySQL 8.4.9 en RDS. Aprobar RDS es
obligatorio antes de promover. No presentar resultados locales como AWS.

## Entrega 022 en Windows

Extraer `entrega_022_cierre_4_3.zip` en `C:\entrega_022`. Cerrar pruebas y
liberar controles/Invitados; detener backend 8001 con Ctrl+C. Mantener intacto el
backend original. Desde `C:\practica_2_6_iot`:

```powershell
& {
    $dump = Get-ChildItem 'C:\mysql-tools' -Filter mysqldump.exe -Recurse | Select-Object -First 1 -ExpandProperty FullName
    $mysql = Get-ChildItem 'C:\mysql-tools' -Filter mysql.exe -Recurse | Select-Object -First 1 -ExpandProperty FullName
    .\.venv\Scripts\python.exe C:\entrega_022\respaldar_rds.py --mysqldump "$dump" --copia 'iot_prueba_20261121_205613_303067'
    if ($LASTEXITCODE -ne 0) { throw "Paso fallido: no se ejecutan los siguientes." }
    .\.venv\Scripts\python.exe C:\entrega_022\migrar_copia_rds.py --mysql "$mysql" --sql 'C:\entrega_022\019_control_empresa.up.sql' --copia 'iot_prueba_20261121_205613_303067'
    if ($LASTEXITCODE -ne 0) { throw "Paso fallido: no se ejecutan los siguientes." }
    .\.venv\Scripts\python.exe C:\entrega_022\migrar_copia_rds.py --mysql "$mysql" --sql 'C:\entrega_022\020_catalogo_resumen.up.sql' --copia 'iot_prueba_20261121_205613_303067'
    if ($LASTEXITCODE -ne 0) { throw "Paso fallido: no se ejecutan los siguientes." }
    .\.venv\Scripts\python.exe C:\entrega_022\probar_control_empresa_sql.py --copia 'iot_prueba_20261121_205613_303067'
    if ($LASTEXITCODE -ne 0) { throw "Paso fallido: no se ejecutan los siguientes." }
}
```

Cada comando SQL/respaldo pide **usuario admin de RDS**, no correo de la app.
Ante fallo, parar y conservar informe: DDL puede quedar aplicado parcialmente.
No usar `--force` ni repetir a ciegas. El ejecutor comprueba versiones/tablas y
reservas vacías; compara datos de las seis tablas originales y procedimientos.
La comparación no sustituye respaldo de todas las tablas nuevas.

Copiar contenido de `C:\entrega_022\backend` dentro de
`C:\practica_4_3_pruebas`, sustituyendo archivos. Arrancar en otra terminal:

```powershell
cd C:\practica_4_3_pruebas
C:\practica_2_6_iot\.venv\Scripts\python.exe .\iniciar_prueba.py --copia 'iot_prueba_20261121_205613_303067'
```

Desde la terminal de herramientas:

```powershell
cd C:\practica_2_6_iot
.\.venv\Scripts\python.exe C:\entrega_022\probar_cierre_4_3_http.py
```

Este último pide **correo/contraseña del administrador de la aplicación**.
Crea modelo/unidad NUEVOS sin hardware y los deja privados/inactivos. No opera
unidad 1. Verifica reservas de empresa, dos sesiones administrativas, demo,
DETENER, catálogo, resumen, auditoría y HTTP 429 de login. No repetir muchas
veces seguidas: límite de login 60 s. Si falla, conservar el informe de limpieza.

Tras aprobar, detener frontend 8080, extraer `frontend_4_3_prueba.zip` dentro de
`C:\frontend_4_3_pruebas`, reiniciar `iniciar_frontend.py` como antes y Ctrl+F5.
Ahora **empresa también pulsa Adquirir control antes de movimientos o demos**.
El modo MONITOREO de soporte sigue sin habilitar operaciones.

## Promoción al servicio público

1. Validar los informes de RDS y el recorrido UI completo. Repetir restauración
   del respaldo actualizado en otra base aislada; conservar dump y manifiesto
   fuera de GitHub y del hosting.
2. Identificar el arranque vigente del backend original, su directorio, el
   Caddyfile y dominio/certificado. No sustituir Caddy por una configuración
   inventada ni deshabilitar TLS para evitar errores.
3. Elegir el esquema definitivo. La copia contiene fixtures y cuentas de
   pruebas; no convertirla automáticamente en producción. Si se migra
   `vehiculo_iot`, preparar ejecutor de promoción con respaldo propio, inventario
   actual, precondiciones y las versiones faltantes en orden. El ejecutor
   `migrar_copia_rds.py` sólo autoriza copias y no debe quitarse esa protección.
4. Respaldar backend/Caddy/configuración y esquema definitivo. Reservas cerradas,
   usuarios desconectados y ventana de actualización; detener escritor anterior.
5. Instalar código aprobado y dependencias en el servidor original. Variables:
   `DB_HOST`, `DB_PORT`, `DB_USER`, `DB_PASSWORD`, `DB_NAME`, `IOT_AUTH_MODE=sesiones`;
   `API_KEY` sólo para compatibilidad anterior. Usar `iot_api` con EXECUTE sobre
   el esquema elegido, no ejecutar el backend con la cuenta SQL admin.
6. Un solo worker Uvicorn en loopback detrás del proxy vigente; conservar
   WebSocket upgrade, HTTPS/WSS y CORS de GitHub Pages. Confiar cabeceras de proxy
   únicamente desde Caddy local para que el límite por dirección no sea evadible.
7. Generar frontend público con `tools/preparar_frontend_publico.py --api URL_HTTPS`.
   Revisar su configuración y publicar contenido sobre el repositorio original.
   El ZIP de pruebas apunta a localhost y no es el artefacto de producción.
8. Validar desde la URL pública: Admin → Comprador → Invitado, exclusividad,
   expiración, demo/DETENER, WSS/reconexión, historial, CORS, teléfono y escritorio.
   Completar P01–P17 y rondas de compañeros. Registrar URL/fecha/versiones reales.

## Recuperación

Antes de abrir el servicio al público, la recuperación preferida es restaurar
el snapshot/dump completo **en un esquema aislado** y arrancar código anterior
contra esa copia, comprobando integridad y privilegios. No restaurar encima del
original sin plan de conservación de escrituras posteriores.

019 conserva historial de reservas y añade unidad explícita; quitarla después
de crear reservas de empresa perdería información porque no hay asignación a
la cual reconstruirla. No se ofrece DOWN destructivo automático. Para volver
al servicio anterior tras uso real, primero detener operaciones, conservar
historial, restaurar copia de respaldo y reconciliar cambios posteriores.
020 sólo cambia lectura: el resumen anterior está en 003 y la rutina nueva de
catálogo puede conservarse aunque el código anterior no la use. No borrar
migraciones registradas para simular reversión. Esta limitación es deliberada.

La detención aquí comprobada es solicitud procesada por backend/SQL/WS; la
recepción y movimiento físicos requieren el dispositivo y supervisión.
