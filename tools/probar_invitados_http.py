"""Prueba real de la API de Invitado en 8001 con una unidad nueva sin hardware."""
from datetime import datetime, timezone
from contextlib import contextmanager
import getpass
import json
from pathlib import Path
import secrets
import time

from websockets.sync.client import connect
from websockets.exceptions import ConnectionClosed
from probar_admin_http import request, BASE


def main():
    print("Destino:", BASE, "· prueba sobre una unidad NUEVA sin hardware asociado")
    email = input("Correo del administrador de la aplicación: ").strip()
    password = getpass.getpass("Contraseña de aplicación (entrada oculta): ")
    status, login = request("POST", "/auth/login", {"correo": email, "password": password})
    password = None
    if status != 200 or login.get("usuario", {}).get("rol") != "ADMINISTRADOR":
        raise SystemExit("No se pudo iniciar sesión como administrador.")
    admin = login["access_token"]
    results, tokens = [], []
    model_id = unit_id = None
    suffix = secrets.token_hex(6)
    name = "Invitados HTTP " + suffix
    unit_body = None
    report = {"destino": BASE, "resultados": results, "unidad_de_prueba_sin_hardware": True}

    def record(label, okay):
        results.append({"prueba": label, "correcto": bool(okay)})
        print(label + (": CORRECTO" if okay else ": INCORRECTO"))
        if not okay:
            raise RuntimeError(label)

    def check(label, expected, method, path, body=None, token=None):
        code, data = request(method, path, body, token)
        print(f"{label}: HTTP {code} (esperado {expected})")
        results.append({"prueba": label, "esperado": expected, "obtenido": code, "correcto": code == expected})
        if code != expected:
            raise RuntimeError(f"{label}: {data.get('detail', 'Respuesta inesperada')}")
        return data

    def original_unit():
        offset = 0
        while True:
            data = check("Consultar inventario", 200, "GET", f"/admin/unidades?limite=100&offset={offset}", token=admin)
            found = next((row for row in data["unidades"] if row["id_vehiculo"] == 1), None)
            if found:
                return found
            if len(data["unidades"]) < 100:
                raise RuntimeError("La unidad 1 no aparece en el inventario esperado.")
            offset += 100

    def reserve():
        data = check("Reservar unidad de prueba", 201, "POST", "/invitados/sesiones", {"id_vehiculo": unit_id})
        tokens.append(data["access_token"])
        record("Reserva limitada a la unidad nueva", data["id_vehiculo"] == unit_id and data["rol"] == "INVITADO")
        return data["access_token"]

    def wait_released(label):
        limit = time.monotonic() + 10
        while time.monotonic() < limit:
            code, data = request("GET", f"/catalogo/{model_id}/unidades")
            row = next((row for row in data.get("unidades", []) if row["id_vehiculo"] == unit_id), None)
            if code == 200 and row and not row["ocupada"]:
                record(label, True)
                return
            time.sleep(0.25)
        record(label, False)

    @contextmanager
    def socket(token):
        with connect(BASE.replace("http", "ws", 1) + "/ws/invitados", open_timeout=10, close_timeout=3) as ws:
            ws.send(json.dumps({"tipo": "autenticar", "token": token}))
            first = json.loads(ws.recv(timeout=10))
            record("WebSocket inicial del Invitado", first["tipo"] == "estado_inicial" and first["id_vehiculo"] == unit_id)
            yield ws

    try:
        original = original_unit()
        model_id = check("Crear modelo de prueba", 201, "POST", "/admin/modelos",
                         {"nombre": name, "descripcion": "Validación de API de Invitado"}, admin)["id_modelo"]
        report["id_modelo_prueba"] = model_id
        check("Publicar modelo de prueba", 200, "POST", f"/admin/modelos/{model_id}/publicacion", {"publico": True}, admin)
        unit_body = {"nombre": "Unidad Invitado " + suffix, "id_modelo": model_id,
                     "identificador_unidad": "INV-" + suffix, "descripcion": "Sólo prueba de servidor, sin hardware",
                     "microcontrolador": ""}
        unit_id = check("Crear unidad de prueba", 201, "POST", "/admin/unidades", unit_body, admin)["id_vehiculo"]
        report["id_unidad_prueba"] = unit_id
        if unit_id == 1:
            raise RuntimeError("La unidad de prueba no puede ser la unidad 1.")
        for command, code in (("DETENER", 13), ("ADELANTE", 1), ("POWER", 11)):
            check("Registrar comando de prueba " + command, 201, "POST", f"/vehiculos/{unit_id}/comandos",
                  {"nombre": command, "codigo": code, "descripcion": "Prueba de API, sin hardware"}, admin)
        commands = check("Consultar comandos de prueba", 200, "GET", f"/vehiculos/{unit_id}/comandos", token=admin)["comandos"]
        ids = {row["nombre"]: row["id_comando"] for row in commands}
        check("Marcar exhibición", 200, "POST", f"/admin/unidades/{unit_id}/exhibicion", {"habilitada": True}, admin)
        check("Configurar prueba de 15 segundos", 200, "POST", f"/admin/unidades/{unit_id}/invitados",
              {"habilitada": True, "duracion_s": 15, "pulso_ms": 100,
               "comandos": [ids["DETENER"], ids["ADELANTE"]]}, admin)
        check("Reservas sin autenticación de movimiento", 401, "POST", "/invitados/movimientos", {"id_comando": ids["DETENER"]})
        token = reserve()
        check("Comando sin WebSocket rechazado", 409, "POST", "/invitados/movimientos", {"id_comando": ids["DETENER"]}, token)
        with socket(token) as ws:
            check("Segunda reserva rechazada", 409, "POST", "/invitados/sesiones", {"id_vehiculo": unit_id})
            check("Invitado fuera de Administración", 403, "GET", "/admin/resumen", token=token)
            check("Invitado fuera de unidad 1", 403, "GET", "/vehiculos/1/estado", token=token)
            check("Comando no permitido rechazado", 403, "POST", "/invitados/movimientos", {"id_comando": ids["POWER"]}, token)
            check("Control normal bloqueado durante reserva", 409, "POST", f"/vehiculos/{unit_id}/movimientos",
                  {"id_comando": ids["DETENER"]}, admin)
            check("Pulso limitado sobre unidad de prueba", 201, "POST", "/invitados/movimientos", {"id_comando": ids["ADELANTE"]}, token)
            events = [json.loads(ws.recv(timeout=5)), json.loads(ws.recv(timeout=5))]
            record("Eventos del pulso y DETENER recibidos", [row.get("comando") for row in events] == ["ADELANTE", "DETENER"])
            with connect(BASE.replace("http", "ws", 1) + "/ws/invitados", open_timeout=10, close_timeout=3) as extra:
                extra.send(json.dumps({"tipo": "autenticar", "token": token}))
                try:
                    extra.recv(timeout=5)
                except ConnectionClosed as error:
                    record("Segundo canal de la misma sesión rechazado", error.rcvd is not None and error.rcvd.code == 1008)
                else:
                    record("Segundo canal de la misma sesión rechazado", False)
            check("Primer canal conserva su sesión", 200, "GET", "/invitados/sesion", token=token)
            check("Cerrar prueba", 200, "POST", "/invitados/sesion/cerrar", token=token)
        check("Token cerrado rechazado", 401, "GET", "/invitados/sesion", token=token)
        wait_released("Reserva liberada tras cancelación")
        token = reserve()
        with socket(token):
            pass
        wait_released("Desconexión cierra y libera reserva")
        check("Token desconectado rechazado", 401, "GET", "/invitados/sesion", token=token)
        token = reserve()
        with socket(token):
            deadline = time.monotonic() + 22
            status = 200
            while status == 200 and time.monotonic() < deadline:
                time.sleep(0.5)
                status, _ = request("GET", "/invitados/sesion", token=token)
            record("Caducidad real rechaza token", status == 401)
            wait_released("Caducidad solicita parada y libera reserva")
        record("Unidad 1 conservada sin cambios", original_unit() == original)
        audit = check("Consultar auditoría", 200, "GET", "/admin/auditoria?limite=100", token=admin)
        actions = {row["accion"] for row in audit["eventos"] if str(row["id_recurso"]) == str(unit_id)}
        record("Reserva, cierre y liberación auditados", {"RESERVAR_INVITADO", "CERRAR_INVITADO", "LIBERAR_INVITADO"} <= actions)
    finally:
        cleanup = []
        for token in tokens:
            try:
                code, _ = request("POST", "/invitados/sesion/cerrar", token=token)
                cleanup.append({"operacion": "Cerrar sesión de prueba", "http": code, "correcto": code == 200})
            except Exception:
                cleanup.append({"operacion": "Cerrar sesión de prueba", "correcto": False})
        operations = []
        if model_id:
            operations.append((f"/admin/modelos/{model_id}/publicacion", {"publico": False}))
        if unit_id and unit_id != 1:
            operations.append((f"/admin/unidades/{unit_id}/actualizar", {**unit_body, "activo": False}))
        if model_id:
            operations.append((f"/admin/modelos/{model_id}/actualizar", {"nombre": name, "descripcion": "Prueba finalizada", "activo": False}))
        for path, body in operations:
            try:
                code, _ = request("POST", path, body, admin)
                cleanup.append({"ruta": path, "http": code, "correcto": code == 200})
            except Exception:
                cleanup.append({"ruta": path, "correcto": False})
        try:
            request("POST", "/auth/logout", token=admin)
        except Exception:
            pass
        report["limpieza"] = cleanup
        report["fecha_utc"] = datetime.now(timezone.utc).isoformat()
        folder = Path.cwd() / "respaldos_rds"
        folder.mkdir(exist_ok=True)
        target = folder / ("http_invitados_" + suffix + ".json")
        target.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        print("Informe guardado en", target)
        if any(not row["correcto"] for row in cleanup):
            raise RuntimeError("Hay limpieza pendiente. Revisa el informe; las reservas incompletas permanecen bloqueadas.")
    print("Comprobaciones de API de Invitado completadas. Registros de prueba privados e inactivos.")


if __name__ == "__main__":
    main()
