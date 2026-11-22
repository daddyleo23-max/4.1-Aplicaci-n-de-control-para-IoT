"""Inventario de publicación Windows: sólo lectura, sin .env ni credenciales.
No modifica servicios, Caddy, base de datos ni archivos de la aplicación.
"""
from datetime import datetime, timezone
import json
from pathlib import Path
import platform
import re
import subprocess
import urllib.error
import urllib.request


POWERSHELL = r'''
$ErrorActionPreference = 'Stop'
$processes = @(Get-CimInstance Win32_Process)
$ports = @(Get-NetTCPConnection -State Listen -ErrorAction SilentlyContinue | Where-Object { $_.LocalPort -in @(80,443,8000,8001,8080) })
$listeners = @($ports | ForEach-Object {
    $listener = $_
    $owner = $processes | Where-Object { $_.ProcessId -eq $listener.OwningProcess } | Select-Object -First 1
    [PSCustomObject]@{ puerto=$listener.LocalPort; direccion=$listener.LocalAddress; pid=$listener.OwningProcess; proceso=$owner.Name; ejecutable=$owner.ExecutablePath }
})
$caddy = @($processes | Where-Object { $_.Name -ieq 'caddy.exe' } | ForEach-Object {
    $config = $null
    if ($_.CommandLine -match '(?i)--config(?:=|\s+)(?:"([^"]+)"|([^\s]+))') {
        if ($Matches[1]) { $config=$Matches[1] } else { $config=$Matches[2] }
    }
    [PSCustomObject]@{ pid=$_.ProcessId; ejecutable=$_.ExecutablePath; archivo_configurado=$config }
})
$services = @(Get-CimInstance Win32_Service | Where-Object { $_.Name -match '(?i)caddy|uvicorn|iot|fastapi' -or $_.DisplayName -match '(?i)caddy|uvicorn|fastapi' } | Select-Object Name,State,StartMode)
[PSCustomObject]@{ listeners=$listeners; caddy=$caddy; servicios=$services } | ConvertTo-Json -Depth 6 -Compress
'''


def local_api(port):
    result = {'puerto':port}
    try:
        with urllib.request.urlopen(f'http://127.0.0.1:{port}/openapi.json',timeout=5) as response:
            spec=json.load(response)
        paths=spec.get('paths',{})
        result.update(disponible=True, version=spec.get('info',{}).get('version'),
                      titulo=spec.get('info',{}).get('title'),rutas_http=len(paths),
                      administracion='/admin/resumen' in paths,
                      reserva_control='/vehiculos/{id_vehiculo}/control/reservar' in paths)
    except (OSError, ValueError, urllib.error.URLError):
        result['disponible']=False
    return result


def as_list(value):
    if value is None:return []
    return value if isinstance(value,list) else [value]


def caddy_summary(path):
    """Publica sólo direcciones de escucha/proxy, nunca el contenido del Caddyfile."""
    result={'archivo':str(path)}
    try:
        text=path.read_text(encoding='utf-8-sig')
    except (OSError,UnicodeError):
        result['legible']=False;return result
    lines=[line.split('#',1)[0].strip() for line in text.splitlines()]
    sites=[];proxies=[]
    address=r'(?:https?://)?(?:localhost|(?:[A-Za-z0-9-]+\.)+[A-Za-z0-9-]+|\[[0-9A-Fa-f:]+\])(?::\d+)?'
    for line in lines:
        if line.endswith('{'):
            candidate=line[:-1].strip()
            if re.fullmatch(address+r'(?:\s*,\s*'+address+r')*',candidate):sites.append(candidate)
        if line.startswith('reverse_proxy '):
            for candidate in line.removeprefix('reverse_proxy ').rstrip('{').split():
                if re.fullmatch(address,candidate):proxies.append(candidate)
    result.update(legible=True,sitios=sites,destinos_proxy=proxies,
                  tls_internal=any(re.match(r'^tls\s+internal(?:\s|$)',line) for line in lines))
    return result


def main():
    if platform.system()!='Windows':raise SystemExit('Ejecuta esta herramienta en la instancia Windows, no en otro equipo.')
    print('Diagnóstico de publicación: sólo lectura; no se leen .env ni contraseñas.')
    operation=subprocess.run(['powershell.exe','-NoProfile','-NonInteractive','-Command',POWERSHELL],
                             capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=45,check=False)
    if operation.returncode:
        raise SystemExit('No se pudo consultar procesos/puertos de Windows. Ejecuta en PowerShell como administrador. No se modificó nada.')
    try:inventory=json.loads(operation.stdout.lstrip('\ufeff'))
    except ValueError:raise SystemExit('Windows no devolvió el inventario esperado. No se modificó nada.')
    for key in ('listeners','caddy','servicios'):inventory[key]=as_list(inventory.get(key))
    candidates=[Path('C:/Caddy/Caddyfile'),Path('C:/Program Files/Caddy/Caddyfile'),
                Path('C:/practica_2_6_iot/Caddyfile')]
    for process in inventory['caddy']:
        if process.get('ejecutable'):candidates.append(Path(process['ejecutable']).parent/'Caddyfile')
        if process.get('archivo_configurado'):candidates.append(Path(process['archivo_configurado']))
    unique={str(path.resolve()).lower():path for path in candidates if path.is_absolute() and path.is_file()}
    report={'fecha_utc':datetime.now(timezone.utc).isoformat(),'solo_lectura':True,
            'windows':inventory,'api_local':[local_api(p) for p in (8000,8001)],
            'caddyfiles_encontrados':[caddy_summary(path) for path in unique.values()],
            'no_incluye':'No lee .env, contraseñas, tokens, contenido completo de Caddyfile ni líneas completas de comandos.'}
    folder=Path.cwd()/'respaldos_rds';folder.mkdir(exist_ok=True)
    target=folder/('diagnostico_publicacion_'+datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')+'.json')
    target.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(report,ensure_ascii=False,indent=2))
    print('Informe guardado en',target)
    print('No se detuvieron procesos ni se modificaron configuración o base de datos.')


if __name__=='__main__':main()
