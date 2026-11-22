"""Prepara una unidad NUEVA sin hardware para comprobar la interfaz de Invitado."""
import argparse
from datetime import datetime, timezone
import getpass
import json
from pathlib import Path
import secrets

from probar_admin_http import BASE, request


def execute(admin, report, save, retire=False):
    def check(method, path, body=None, expected=200):
        code, data = request(method, path, body, admin)
        print(f"{method} {path}: HTTP {code}")
        if code != expected:
            raise RuntimeError(f"HTTP {code}: {data.get('detail', 'Respuesta inesperada')}")
        return data

    if retire:
        model_id, unit_id = report.get('id_modelo'), report.get('id_unidad')
        if not model_id or not unit_id or unit_id == 1:
            raise RuntimeError('El informe no identifica una unidad de prueba válida.')
        # Verificar ambos registros antes de efectuar cambios con IDs del informe.
        def find(path, key, identity, value):
            offset = 0
            while True:
                rows = check('GET', f'{path}?limite=100&offset={offset}')[key]
                found = next((row for row in rows if row[identity] == value), None)
                if found:
                    return found
                if len(rows) < 100:
                    raise RuntimeError('No se encontró el registro de prueba.')
                offset += 100
        unit = find('/admin/unidades', 'unidades', 'id_vehiculo', unit_id)
        model = find('/admin/modelos', 'modelos', 'id_modelo', model_id)
        if (not report.get('nombre_modelo', '').startswith('Invitado web ')
                or model['nombre'] != report['nombre_modelo']
                or unit['identificador_unidad'] != report['unidad']['identificador_unidad']
                or unit['id_modelo'] != model_id or unit.get('id_propietario')):
            raise RuntimeError('Los registros cambiaron o tienen propietario; no se modificaron.')
        check('POST', f'/admin/unidades/{unit_id}/invitados/cerrar')
        check('POST', f'/admin/modelos/{model_id}/publicacion', {'publico': False})
        check('POST', f'/admin/unidades/{unit_id}/actualizar', {**report['unidad'], 'activo': False})
        check('POST', f'/admin/modelos/{model_id}/actualizar',
              {'nombre': report['nombre_modelo'], 'descripcion': 'Prueba web finalizada', 'activo': False})
        report['estado'] = 'RETIRADA'
        save()
        return

    name = report['nombre_modelo']
    model_id = check('POST', '/admin/modelos',
                     {'nombre': name, 'descripcion': 'Prueba de interfaz, sin hardware'}, 201)['id_modelo']
    report['id_modelo'] = model_id
    save()
    unit_body = {'nombre': name, 'id_modelo': model_id,
                 'identificador_unidad': 'WEB-INV-' + report['sufijo'],
                 'descripcion': 'Unidad de software sin hardware asociado', 'microcontrolador': ''}
    report['unidad'] = unit_body
    unit_id = check('POST', '/admin/unidades', unit_body, 201)['id_vehiculo']
    report['id_unidad'] = unit_id
    save()
    if unit_id == 1:
        raise RuntimeError('Se esperaba una unidad nueva distinta de la unidad 1; se detuvo la preparación.')
    ids = []
    for name, code in [('DETENER', 13), ('ADELANTE', 1)]:
        check('POST', f'/admin/modelos/{model_id}/capacidades', {'nombre': name, 'codigo': code}, 201)
        check('POST', f'/vehiculos/{unit_id}/comandos',
              {'nombre': name, 'codigo': code, 'descripcion': 'Prueba web sin hardware'}, 201)
    rows = check('GET', f'/vehiculos/{unit_id}/comandos')['comandos']
    for name in ('DETENER', 'ADELANTE'):
        ids.append(next(row['id_comando'] for row in rows if row['nombre'] == name))
    check('POST', f'/admin/modelos/{model_id}/publicacion', {'publico': True})
    check('POST', f'/admin/unidades/{unit_id}/exhibicion', {'habilitada': True})
    check('POST', f'/admin/unidades/{unit_id}/invitados',
          {'habilitada': True, 'duracion_s': 60, 'pulso_ms': 100, 'comandos': ids})
    code, data = request('GET', f'/catalogo/{model_id}/unidades')
    if code != 200 or not any(row['id_vehiculo'] == unit_id and row['disponible'] for row in data.get('unidades', [])):
        raise RuntimeError('No se confirmó la disponibilidad pública de la unidad nueva.')
    report['estado'] = 'LISTA'
    save()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--retirar', type=Path, help='Informe de la unidad preparada que se desea retirar')
    args = parser.parse_args()
    print('Destino:', BASE, '· Sólo unidad NUEVA de software, sin hardware.')
    if args.retirar:
        target = args.retirar
        report = json.loads(target.read_text(encoding='utf-8'))
        if report.get('destino') != BASE:
            raise SystemExit('El destino del informe no corresponde al backend de pruebas.')
    else:
        suffix = secrets.token_hex(6)
        folder = Path.cwd() / 'respaldos_rds'
        folder.mkdir(exist_ok=True)
        target = folder / ('invitado_web_' + suffix + '.json')
        report = {'destino': BASE, 'sufijo': suffix, 'nombre_modelo': 'Invitado web ' + suffix,
                  'estado': 'PREPARANDO', 'fecha_utc': datetime.now(timezone.utc).isoformat()}
    email = input('Correo del administrador de la aplicación: ').strip()
    password = getpass.getpass('Contraseña de aplicación (entrada oculta): ')
    code, login = request('POST', '/auth/login', {'correo': email, 'password': password})
    password = None
    if code != 200 or login.get('usuario', {}).get('rol') != 'ADMINISTRADOR':
        raise SystemExit('No se pudo iniciar sesión como administrador.')
    admin = login['access_token']

    def save():
        target.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')

    try:
        save()
        execute(admin, report, save, retire=bool(args.retirar))
        print('Unidad retirada.' if args.retirar else 'Lista: recarga la web y abre el catálogo o Administración → Unidades.')
        print('Estado:', report['estado'])
    except Exception as error:
        report['ultimo_error'] = str(error)
        save()
        raise SystemExit('Preparación incompleta. Conserva el informe y comparte la salida antes de repetir: ' + str(error))
    finally:
        try:
            request('POST', '/auth/logout', token=admin)
        finally:
            print('Informe guardado en', target)


if __name__ == '__main__':
    main()
