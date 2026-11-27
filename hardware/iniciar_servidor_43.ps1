# Arranque manual e idempotente. No modifica Caddy, la BD ni las credenciales.
[CmdletBinding()]
param([string]$ApiPublica = 'https://34.194.45.28')
$ErrorActionPreference = 'Stop'
$pythonIoT = 'C:\practica_2_6_iot\.venv\Scripts\python.exe'
$backendIoT = 'C:\practica_4_3_publica\iniciar_publicacion.py'
$caddyIoT = 'C:\caddy\caddy.exe'
$configIoT = 'C:\caddy\Caddyfile.prod'
foreach ($rutaIoT in @($pythonIoT, $backendIoT, $caddyIoT, $configIoT)) {
    if (-not (Test-Path -LiteralPath $rutaIoT -PathType Leaf)) { throw "Falta el archivo: $rutaIoT" }
}
$uriIoT = [Uri]$ApiPublica
if ($uriIoT.Scheme -ne 'https' -or $uriIoT.UserInfo -or $uriIoT.Query -or $uriIoT.Fragment -or $uriIoT.AbsolutePath -ne '/') {
    throw 'ApiPublica debe ser un origen HTTPS sin credenciales ni rutas.'
}
$ApiPublica = $ApiPublica.TrimEnd('/')
$escuchaIoT = Get-NetTCPConnection -LocalPort 8002 -State Listen -ErrorAction SilentlyContinue
if (-not $escuchaIoT) {
    Write-Host 'Abriendo backend definitivo en otra ventana...'
    $comandoBackendIoT = @'
Set-Location 'C:\practica_4_3_publica'
& 'C:\practica_2_6_iot\.venv\Scripts\python.exe' '.\iniciar_publicacion.py'
'@
    Start-Process -FilePath "$PSHOME\powershell.exe" -ArgumentList @('-NoExit', '-Command', $comandoBackendIoT) | Out-Null
} else {
    Write-Host 'El puerto 8002 ya esta ocupado; se comprueba sin duplicar ni matar procesos.'
}
$backendListoIoT = $false
$intentosIoT = if ($escuchaIoT) { 1 } else { 12 }
for ($intentoIoT = 0; $intentoIoT -lt $intentosIoT; $intentoIoT++) {
    try {
        $contratoIoT = Invoke-RestMethod 'http://127.0.0.1:8002/openapi.json' -TimeoutSec 4
        if ($contratoIoT.info.version -ne '4.3.0') { throw 'Version distinta de 4.3.0.' }
        $backendListoIoT = $true
        break
    } catch {
        if ($escuchaIoT) { break }
        Start-Sleep -Seconds 2
    }
}
if (-not $backendListoIoT) {
    throw 'El backend local no responde como 4.3.0. Revisa su ventana; si esta bloqueado, detenlo con Ctrl+C y vuelve a ejecutar. No se alteraron procesos existentes.'
}
$baseIoT = Invoke-RestMethod 'http://127.0.0.1:8002/health/db' -TimeoutSec 15
if (-not $baseIoT.conectado -or $baseIoT.base_datos -ne 'vehiculo_iot_43') {
    throw 'La base definitiva no esta conectada. Revisa RDS y la ventana del backend.'
}
Write-Host 'Backend 4.3.0 y RDS vehiculo_iot_43: correctos.'
if (-not (Get-Process -Name caddy -ErrorAction SilentlyContinue)) {
    Write-Host 'Validando la configuracion existente de Caddy...'
    & $caddyIoT validate --config $configIoT --adapter caddyfile
    if ($LASTEXITCODE -ne 0) { throw 'Caddy no valido su configuracion. No se modifica el archivo.' }
    $comandoCaddyIoT = @'
Set-Location 'C:\caddy'
& '.\caddy.exe' run --config 'C:\caddy\Caddyfile.prod' --adapter caddyfile
'@
    Start-Process -FilePath "$PSHOME\powershell.exe" -ArgumentList @('-NoExit', '-Command', $comandoCaddyIoT) | Out-Null
    Start-Sleep -Seconds 3
} else {
    Write-Host 'Caddy ya esta ejecutandose; no se abre otro ni se recarga su configuracion.'
}
try {
    $publicoIoT = Invoke-RestMethod "$ApiPublica/openapi.json" -TimeoutSec 15
    $basePublicaIoT = Invoke-RestMethod "$ApiPublica/health/db" -TimeoutSec 15
    if ($publicoIoT.info.version -ne '4.3.0' -or -not $basePublicaIoT.conectado -or $basePublicaIoT.base_datos -ne 'vehiculo_iot_43') {
        throw 'El destino publico no coincide con el backend definitivo.'
    }
} catch {
    throw "Backend local correcto, pero fallo la verificacion publica. Revisa Caddy, IP publica y red. Detalle: $($_.Exception.Message)"
}
Write-Host 'HTTPS publico verificado. Mantener abiertas las ventanas de backend y Caddy.' -ForegroundColor Green
Write-Host 'Ahora iniciar el puente USB desde Linux. No hacen falta los puertos de prueba 8000/8001/8080.'
