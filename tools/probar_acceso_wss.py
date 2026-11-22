"""Verificación REST/WSS de dos compradores en el backend local de prueba."""

from datetime import datetime, timezone
import getpass
import json
import time
from pathlib import Path
import urllib.error
import urllib.request

from websockets.exceptions import ConnectionClosed
from websockets.sync.client import connect


BASE = "http://127.0.0.1:8001"
SOCKET = "ws://127.0.0.1:8001/ws/vehiculos/1"


def http(method, path, token=None, body=None):
    headers = {"Accept": "application/json"}
    if token:
        headers["Authorization"] = "Bearer " + token
    data = None
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request(BASE + path, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            return response.status, json.load(response)
    except urllib.error.HTTPError as error:
        return error.code, json.load(error)


def login(label, default_email):
    print(label)
    email = input(f"Correo [{default_email}]: ").strip() or default_email
    password = getpass.getpass("Contraseña de aplicación (entrada oculta): ")
    status, payload = http("POST", "/auth/login", body={"correo": email, "password": password})
    password = None
    if status != 200:
        raise RuntimeError(f"{label}: login HTTP {status}")
    if payload["usuario"]["rol"] != "USUARIO":
        raise RuntimeError("La prueba requiere una cuenta con rol USUARIO.")
    return payload["access_token"], payload["usuario"]["id_usuario"]


def main():
    results = []
    tokens = []

    def record(label, success):
        results.append({"prueba": label, "correcto": success})
        print(label + ": " + ("CORRECTO" if success else "INCORRECTO"))
        if not success:
            raise RuntimeError(label)

    try:
        owner, owner_id = login("Comprador dueño de la unidad 1", "comprador.prueba@example.com")
        tokens.append(owner)
        other, other_id = login("Comprador B sin unidades", "comprador.b@example.com")
        tokens.append(other)
        record("Las cuentas son distintas", owner_id != other_id)
        status, payload = http("GET", "/mis-vehiculos", owner)
        record("El dueño tiene asignada la unidad 1",
               status == 200 and any(v["id_vehiculo"] == 1 for v in payload.get("vehiculos", [])))
        status, payload = http("GET", "/mis-vehiculos", other)
        record("Comprador B sin asignaciones", status == 200 and payload.get("vehiculos") == [])
        for path in ("/vehiculos/1/estado", "/vehiculos/1/historial", "/vehiculos/1/comandos"):
            record("REST dueño " + path, http("GET", path, owner)[0] == 200)
            record("REST comprador B " + path, http("GET", path, other)[0] == 403)
        with connect(SOCKET, open_timeout=10, close_timeout=3) as socket:
            socket.send(json.dumps({"tipo": "autenticar", "token": other}))
            try:
                socket.recv(timeout=10)
            except ConnectionClosed as error:
                record("WSS comprador B rechazado antes de recibir estado",
                       error.rcvd is not None and error.rcvd.code == 1008)
            else:
                record("WSS comprador B rechazado antes de recibir estado", False)
        with connect(SOCKET, open_timeout=10, close_timeout=3) as socket:
            socket.send(json.dumps({"tipo": "autenticar", "token": owner}))
            payload = json.loads(socket.recv(timeout=10))
            record("WSS dueño recibe estado inicial",
                   payload.get("tipo") == "estado_inicial" and payload.get("id_vehiculo") == 1)
            record("Logout del dueño", http("POST", "/auth/logout", owner)[0] == 200)
            closed = False
            deadline = time.monotonic() + 10
            while time.monotonic() < deadline:
                try:
                    socket.recv(timeout=max(.1, deadline - time.monotonic()))
                except ConnectionClosed as error:
                    closed = error.rcvd is not None and error.rcvd.code == 1008
                    break
                except TimeoutError:
                    break
            record("Socket del dueño cerrado tras revocar sesión", closed)
    finally:
        for token in tokens:
            try:
                http("POST", "/auth/logout", token)
            except Exception:
                pass
        report = {"fecha_utc": datetime.now(timezone.utc).isoformat(), "resultados": results}
        folder = Path.cwd() / "respaldos_rds"
        folder.mkdir(exist_ok=True)
        destination = folder / ("prueba_wss_" + datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S-%f") + ".json")
        with destination.open("x", encoding="utf-8") as output:
            json.dump(report, output, ensure_ascii=False, indent=2)
        print("Informe guardado en", destination)
    print("Comprobaciones de acceso REST y WSS completadas.")


if __name__ == "__main__":
    main()
