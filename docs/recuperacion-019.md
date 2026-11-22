# Recuperación del fallo parcial 019 — 22 de noviembre de 2026

El alumno obtuvo ERROR1832 en la línea que cambia id_vehiculo a NOT NULL. El
DDL anterior ya había añadido la columna y su FK y completado el backfill.
La migración no llegó a sustituir las rutinas ni a registrar 019. 020 rechazó
las versiones previas incompletas. La prueba SQL posterior falló porque aún
operaban las rutinas anteriores; su ROLLBACK revirtió fixtures, aunque puede
haber avanzado AUTO_INCREMENT. El respaldo previo sí se generó.

La causa es el orden del DDL de la entrega022. La corrección para instalaciones
nuevas crea la FK después del NOT NULL. No se debe repetir el SQL completo
sobre la instalación parcial porque la columna ya existe.

Para el estado parcial se usa recuperar_control_019.py:

- Comprueba nombre de copia, informe previo fallido, hash del SQL ORIGINAL y
  conservación de las seis tablas/procedimientos originales respecto al informe.
- Exige exactamente versiones001–018 (o019 completa para no repetir), tablas
  previstas, reservas vacías, columnas y FK conocidas, referencias válidas,
  parámetros de rutinas y cuerpos iguales a fuentes anteriores o corregidas.
- Sólo si reconoce el estado, completa backfill pendiente, retira la FK
  conocida antes de cambiar nulabilidad, cambia a NOT NULL y recrea la misma FK.
  Nunca usa FOREIGN_KEY_CHECKS=0.
- Completa únicamente las rutinas pendientes. Compara hashes de datos de TODAS
  las tablas (exceptúa registro de migraciones y la columna cuyo backfill se
  espera). Registra019 solamente después de verificar estructura, rutinas y datos.
- Si se interrumpe, conserva informe y permite reconocer pasos ya completados;
  un estado desconocido falla sin intentar adivinar reparaciones.

## Uso en Windows

Mantener detenido backend8001 y todas las pruebas. Extraer
`recuperacion_019_mysql.zip` en `C:\recuperacion_019`. Ejecutar desde
`C:\practica_2_6_iot`, donde está la configuración original de conexión.
No copiar las líneas de formato Markdown que rodean los comandos.

Primero se puede diagnosticar sin cambiar nada:

```powershell
.\.venv\Scripts\python.exe C:\recuperacion_019\recuperar_control_019.py --copia 'iot_prueba_20261121_205613_303067' --informe 'C:\practica_2_6_iot\respaldos_rds\migracion_019_20261122-182248-235666.json' --diagnostico
```

Para diagnosticar y completar exclusivamente el estado conocido en un comando:

```powershell
.\.venv\Scripts\python.exe C:\recuperacion_019\recuperar_control_019.py --copia 'iot_prueba_20261121_205613_303067' --informe 'C:\practica_2_6_iot\respaldos_rds\migracion_019_20261122-182248-235666.json' --aplicar
```

Pide usuario **admin de RDS** y contraseña SQL. No pide correo de aplicación.
Esperar «019 registrada» y «Datos de todas las tablas conservados: True».
Ante error conservar informe, no repetir019/020 ni iniciar backend nuevo.
Después de revisar ese resultado se podrá aplicar020 y ejecutar la prueba SQL
con los archivos ya entregados. La recuperación no intenta avanzar a020 ni
lanza pruebas automáticamente, para evitar la cascada observada.

Conservar el respaldo previo
`iot_prueba_20261121_205613_303067_20261122-182236-131166.sql` y su manifiesto.
No se modifica el esquema original vehiculo_iot ni se borran tablas/datos.

## Verificación realizada

- 132 pruebas unitarias correctas, incluyendo orden FK/ALTER, reanudación,
  interrupción y rechazo de cambios de datos antes de registrar versión.
- Estado parcial reconstruido y recuperación verificada en MariaDB12.3.2.
- MySQL8.4.13 oficial, local: ERROR1832 reproducido con FK activa, datos e
  sql_mode=NO_ENGINE_SUBSTITUTION. Recuperación completa, hashes conservados,
  FK restaurada y segunda ejecución sin DDL.
- Instalación nueva de019 corregida y020 comprobada en MySQL8.4.13; las
  18 pruebas SQL de empresa pasaron con ROLLBACK.
- La validación en RDS/MySQL8.4.9 del alumno sigue pendiente. No se presume
  cuál es su sql_mode; el ensayo cubre el modo que reproduce el error.

Referencia oficial del error: [MySQL ER_FK_COLUMN_CANNOT_CHANGE](https://dev.mysql.com/doc/mysql-errors/8.0/en/server-error-reference.html).
