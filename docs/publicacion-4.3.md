# Puesta en servicio 4.3: configuración real y base definitiva

Diagnóstico del alumno, 22 de noviembre de2026:

| Recurso | Situación comprobada |
| --- | --- |
| Caddy | `C:\caddy\caddy.exe`, PID2376 al diagnosticar; puertos80/443. |
| Configuración activa | `C:\caddy\Caddyfile.prod`. Sitio34.194.45.28. |
| Proxy actual | 127.0.0.1:8000. |
| API original | Puerto8000, versión1.0.0, sin Administración ni reservas. |
| API de pruebas | Puerto8001, versión4.3.0, funciones aprobadas en copia RDS. |
| Frontend de pruebas | Puerto8080. |

Los PID son observaciones, no identificadores para detener procesos después.
No se publica4.3 simplemente cambiando el ZIP del frontend: el proxy aún apunta
a la API anterior.

## Etapa1: preparar la base definitiva

Se crea `vehiculo_iot_43` desde la copia aprobada, con los mismos IDs, cuentas,
asignaciones, demos e historial. Se conserva `vehiculo_iot` y la copia de pruebas.
El script no crea tablas vacías ni vuelve a aplicar20 migraciones. Realiza
respaldo completo, restauración y comparación de las19 tablas, datos, columnas,
índices, AUTO_INCREMENT, restricciones, FK, rutinas/parámetros y triggers.
Otorga únicamente EXECUTE sobre el nuevo esquema a la cuenta limitada ya
configurada en el backend; no crea usuarios SQL. No elimina fixtures ni cuentas.

1. Extraer `publicacion_4_3.zip` en `C:\publicacion_4_3`.
2. Detener sólo backend8001 con Ctrl+C para evitar escrituras mientras se
   respalda. El backend8000 y Caddy continúan funcionando.
3. Ejecutar desde `C:\practica_2_6_iot`:

```powershell
.\.venv\Scripts\python.exe C:\publicacion_4_3\preparar_base_publica_4_3.py --origen "iot_prueba_20261121_205613_303067"
```

Pide admin/contraseña de RDS. Encuentra mysql.exe/mysqldump.exe en las herramientas
instaladas; permite `--mysql` y `--mysqldump` para rutas explícitas.
Esperar base preparada, comparación correcta y origen conservado.
Guarda respaldoSQL y JSON privado bajo `respaldos_rds`. Si existe el destino,
rechaza sobrescritura. Si falla una restauración, deja el destino para revisar;
no repetir ni borrarlo a ciegas.

Los registros de pruebas se conservan identificados para auditoría. Antes de
la demostración pública deben revisarse desde Administración los modelos y
unidades publicados; una unidad de software no acredita hardware conectado.

## Etapa2: arrancar el backend definitivo

Después de aprobar la comparación:

- Copiar el contenido de `backend_publico` a `C:\practica_4_3_publica`.
- Abrir una terminal dedicada y ejecutar:

```powershell
cd C:\practica_4_3_publica
C:\practica_2_6_iot\.venv\Scripts\python.exe .\iniciar_publicacion.py
```

Usa las credenciales locales del archivo original `.env` sin modificarlo;
selecciona explícitamente `vehiculo_iot_43`, modo sesiones, un worker y loopback8002.
Verifica que se importa la carpeta app correcta y el resumen020 antes de servir.
Debe mantenerse abierta esa terminal. Este arranque manual no instala un servicio
automático de Windows; un reinicio/logoff exige arrancarlo de nuevo.

Comprobar desde otra terminal:

```powershell
(Invoke-RestMethod "http://127.0.0.1:8002/openapi.json").info.version
Invoke-RestMethod "http://127.0.0.1:8002/health/db"
```

Esperado:4.3.0, conectadoTrue y base_datos vehiculo_iot_43. Las contraseñas de
aplicación son las mismas que en la copia; no necesitan recrearse.

## Etapa3: preparar y activar el proxy

Pendiente tras validar8002: respaldar Caddyfile.prod y preparar un candidato que
cambie únicamente su destino de8000 a8002, conservando TLS, dominio y directivas.
Validar con el caddy.exe instalado antes de recargar. Conservar configuración
previa para revertir el proxy. No cambiar certificados ni borrar el backend8000.
Después: publicar frontend de sesiones en el repositorio original y verificar
HTTPS/WSS desde la URL pública, teléfono y escritorio.

La configuración en disco del repositorio todavía conserva el modo anterior;
no subir frontend de prueba localhost a GitHub Pages. La publicación requiere
coordinar proxy y frontend y comprobar contratos reales después del cambio.

## Verificación del preparador

Probado con MySQL8.4.13 local: dump/restore real con clientes MySQL, comparación
integral, permisos EXECUTE, restricciones CHECK y rechazo de destino existente
sin sobrescribirlo. El nuevo arranque8002 también se comprobó con la cuenta limitada: versión4.3.0
y health/db sobre vehiculo_iot_43. La ejecución en RDS8.4.9 y el proxy real requieren los
informes del alumno. Ninguna de estas pruebas locales confirma movimiento físico.
