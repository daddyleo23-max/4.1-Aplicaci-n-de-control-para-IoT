"""Prueba HTTP del guardado de demos privadas en el backend aislado."""

from datetime import datetime, timezone
import argparse
import getpass
import json
from pathlib import Path
import secrets

from probar_admin_http import request


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--demo", type=int, help="Reanudar la prueba sobre una demo propia existente.")
    args = parser.parse_args()
    if args.demo is not None and args.demo <= 0:
        raise SystemExit("El ID de demo debe ser positivo.")
    tokens = []
    results = []
    report = {"resultados": results}

    def check(label, expected, method, path, body=None, token=None):
        status, data = request(method, path, body, token)
        ok = status == expected
        results.append({"prueba": label, "esperado": expected, "obtenido": status, "correcto": ok})
        print(f"{label}: HTTP {status} (esperado {expected})")
        if not ok:
            raise RuntimeError(str(data.get("detail", "Respuesta inesperada")))
        return data

    def login(label, email):
        print(label)
        password = getpass.getpass("Contraseña de aplicación (entrada oculta): ")
        data = check("Login " + label, 200, "POST", "/auth/login",
                     {"correo": email, "password": password})
        token = data["access_token"]
        tokens.append(token)
        return token

    try:
        owner = login("Comprador dueño", "comprador.prueba@example.com")
        other = login("Comprador B", "comprador.b@example.com")
        commands = check("Consultar comandos", 200, "GET", "/vehiculos/1/comandos",
                         token=owner)["comandos"]
        stop = next(command for command in commands
                    if command["nombre"].upper() == "DETENER" and command["activo"])
        payload = {
            "id_vehiculo": 1, "nombre": "Demo privada prueba " + secrets.token_hex(4),
            "descripcion": "Prueba de persistencia del editor",
            "pasos": [{"id_comando": stop["id_comando"], "duracion_ms": 100, "pausa_ms": 0}],
        }
        if args.demo is None:
            created = check("Crear demo privada", 201, "POST", "/mis-demos", payload, owner)
            demo_id = created["id_demo"]
        else:
            demo_id = args.demo
            existing = check("Recuperar demo para reanudar", 200, "GET",
                             f"/mis-demos/{demo_id}", token=owner)
            if not existing["demo"]["nombre"].startswith("Demo privada prueba "):
                raise RuntimeError("Solo se reanudan demos generadas por esta prueba.")
            payload["nombre"] = existing["demo"]["nombre"]
            created = {"revision": existing["demo"]["revision"]}
        report["id_demo_prueba"] = demo_id
        detail = check("Recuperar demo y pasos", 200, "GET", f"/mis-demos/{demo_id}", token=owner)
        if len(detail["pasos"]) != 1 or detail["demo"]["tipo"] != "PRIVADA":
            raise RuntimeError("La demo no conservó tipo y pasos esperados.")
        if args.demo is None and (detail["pasos"][0]["id_comando"] != stop["id_comando"] or detail["pasos"][0]["orden"] != 1):
            raise RuntimeError("Se invirtieron el comando y la posición del paso.")
        check("Ocultar demo a otro comprador", 404, "GET", f"/mis-demos/{demo_id}", token=other)
        payload["revision"] = created["revision"]
        payload["pasos"] = [
            {"id_comando": stop["id_comando"], "duracion_ms": 200, "pausa_ms": 100},
            {"id_comando": stop["id_comando"], "duracion_ms": 100, "pausa_ms": 0},
        ]
        updated = check("Guardar secuencia completa", 200, "POST",
                        f"/mis-demos/{demo_id}/guardar", payload, owner)
        check("Rechazar revisión antigua", 409, "POST",
              f"/mis-demos/{demo_id}/guardar", payload, owner)
        payload["revision"] = updated["revision"]
        valid_steps = payload["pasos"]
        payload["pasos"] = [{"id_comando": 2147483647, "duracion_ms": 100, "pausa_ms": 0}]
        check("Rechazar comando incompatible", 409, "POST",
              f"/mis-demos/{demo_id}/guardar", payload, owner)
        detail = check("Comprobar secuencia tras rechazo", 200, "GET",
                       f"/mis-demos/{demo_id}", token=owner)
        if detail["demo"]["revision"] != updated["revision"] or len(detail["pasos"]) != 2:
            raise RuntimeError("Una petición rechazada alteró la secuencia.")
        if [step["duracion_ms"] for step in detail["pasos"]] != [200, 100]:
            raise RuntimeError("El orden de los pasos no coincide.")
        if [step["orden"] for step in detail["pasos"]] != [1, 2] or any(
            step["id_comando"] != stop["id_comando"] for step in detail["pasos"]
        ):
            raise RuntimeError("No se conservaron los comandos y posiciones solicitados.")
        payload["pasos"] = valid_steps
        payload["activo"] = False
        check("Desactivar demo de prueba", 200, "POST",
              f"/mis-demos/{demo_id}/guardar", payload, owner)
    finally:
        for token in tokens:
            try:
                request("POST", "/auth/logout", token=token)
            except Exception:
                pass
        report["fecha_utc"] = datetime.now(timezone.utc).isoformat()
        folder = Path.cwd() / "respaldos_rds"
        folder.mkdir(exist_ok=True)
        destination = folder / ("prueba_editor_" + secrets.token_hex(6) + ".json")
        with destination.open("x", encoding="utf-8") as output:
            json.dump(report, output, ensure_ascii=False, indent=2)
        print("Informe guardado en", destination)
    print("Comprobaciones del editor completadas.")


if __name__ == "__main__":
    main()
