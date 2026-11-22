"""Comprueba consentimiento de diagnóstico sin enviar movimientos."""
import getpass
import json
from pathlib import Path
import secrets
from websockets.sync.client import connect
from websockets.exceptions import ConnectionClosed
from probar_admin_http import request, BASE


def main():
    tokens = []
    permission = None
    owner = None
    results = []
    def check(label, expected, method, path, body=None, token=None):
        code, data = request(method, path, body, token)
        print(f'{label}: HTTP {code} (esperado {expected})')
        results.append({'prueba': label, 'http': code, 'correcto': code == expected})
        if code != expected:
            raise RuntimeError(str(data.get('detail', label)))
        return data
    def login(label):
        email = input(f'Correo {label}: ').strip()
        password = getpass.getpass('Contraseña de aplicación (entrada oculta): ')
        data = check('Login ' + label, 200, 'POST', '/auth/login', {'correo': email, 'password': password})
        tokens.append(data['access_token'])
        return data
    try:
        admin = login('Administrador')
        buyer = login('comprador dueño de unidad 1')
        if admin['usuario']['rol'] != 'ADMINISTRADOR' or buyer['usuario']['rol'] != 'USUARIO':
            raise RuntimeError('Los roles de las cuentas no corresponden a la prueba.')
        owner = buyer['access_token']
        check('Admin sin consentimiento', 403, 'GET', '/vehiculos/1/estado', token=admin['access_token'])
        check('Admin no puede autoautorizarse', 403, 'POST', '/vehiculos/1/soporte',
              {'id_administrador': admin['usuario']['id_usuario'], 'minutos': 1}, admin['access_token'])
        data = check('Consentimiento del comprador', 201, 'POST', '/vehiculos/1/soporte',
                     {'id_administrador': admin['usuario']['id_usuario'], 'minutos': 1}, owner)
        permission = data['id_permiso']
        for suffix in ('estado', 'historial', 'comandos'):
            check('Diagnóstico ' + suffix, 200, 'GET', '/vehiculos/1/' + suffix, token=admin['access_token'])
        # Cuerpo vacío: la dependencia de autorización debe rechazar antes de ejecutar el handler.
        check('Soporte no permite movimientos', 403, 'POST', '/vehiculos/1/movimientos', {}, admin['access_token'])
        with connect(BASE.replace('http','ws',1) + '/ws/vehiculos/1', open_timeout=10) as ws:
            ws.send(json.dumps({'tipo':'autenticar','token':admin['access_token']}))
            if json.loads(ws.recv(timeout=10)).get('tipo') != 'estado_inicial':
                raise RuntimeError('No se recibió estado autorizado por WSS.')
            results.append({'prueba':'WSS autorizado','correcto':True})
            print('WSS autorizado: CORRECTO')
            check('Revocar consentimiento', 200, 'POST', f'/vehiculos/1/soporte/{permission}/revocar', token=owner)
            permission = None
            try:
                ws.recv(timeout=8)
            except ConnectionClosed:
                results.append({'prueba':'WSS cerrado tras revocación','correcto':True})
                print('WSS cerrado tras revocación: CORRECTO')
            else:
                raise RuntimeError('WSS no se cerró tras revocación.')
        check('REST rechazado tras revocar', 403, 'GET', '/vehiculos/1/estado', token=admin['access_token'])
        print('Comprobaciones de diagnóstico completadas. No se enviaron movimientos.')
    finally:
        if permission and owner:
            try:
                code, _ = request('POST', f'/vehiculos/1/soporte/{permission}/revocar', token=owner)
                results.append({'prueba':'Revocación de limpieza','http':code,'correcto':code==200})
            except Exception:
                results.append({'prueba':'Revocación de limpieza','correcto':False})
        for token in tokens:
            try:
                request('POST', '/auth/logout', token=token)
            except Exception:
                results.append({'prueba':'Logout de limpieza','correcto':False})
        folder = Path.cwd()/'respaldos_rds'
        folder.mkdir(exist_ok=True)
        target = folder/('soporte_http_' + secrets.token_hex(6) + '.json')
        target.write_text(json.dumps({'destino':BASE,'resultados':results},indent=2),encoding='utf-8')
        print('Informe guardado en',target)


if __name__ == '__main__':
    main()
