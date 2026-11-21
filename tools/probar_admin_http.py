"""Comprobaciones HTTP de administración sobre FastAPI de prueba en 8001."""

from datetime import datetime, timezone
import getpass
import json
from pathlib import Path
import secrets
import urllib.error
import urllib.request


BASE = "http://127.0.0.1:8001"


def request(method, path, body=None, token=None):
    headers = {"Accept": "application/json"}
    if token:
        headers["Authorization"] = "Bearer " + token
    data = None
    if body is not None:
        headers["Content-Type"] = "application/json"
        data = json.dumps(body).encode("utf-8")
    operation = urllib.request.Request(BASE + path, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(operation, timeout=15) as response:
            return response.status, json.load(response)
    except urllib.error.HTTPError as error:
        return error.code, json.load(error)


def main():
    print("Destino de prueba:", BASE)
    email = input("Correo del administrador de la aplicación: ").strip()
    password = getpass.getpass("Contraseña de la aplicación (entrada oculta): ")
    status, login = request("POST", "/auth/login", {"correo": email, "password": password})
    password = None
    if status != 200 or login.get("usuario", {}).get("rol") != "ADMINISTRADOR":
        raise SystemExit("No se pudo iniciar sesión como administrador.")
    admin_token = login["access_token"]
    results = []
    buyer_token = None

    def check(label, expected, method, path, body=None, token=None):
        status, data = request(method, path, body, token)
        results.append({"prueba": label, "esperado": expected, "obtenido": status,
                        "correcto": status == expected})
        print(f"{label}: HTTP {status} (esperado {expected})")
        if status != expected:
            detail = data.get("detail", "Respuesta inesperada")
            raise RuntimeError(f"{label}: {detail}")
        return data

    suffix = secrets.token_hex(6)
    model_name = "Prueba HTTP " + suffix
    client_email = "prueba-" + suffix + "@example.invalid"
    client_password = secrets.token_urlsafe(24)
    report = {"destino": BASE, "resultados": results}
    try:
        model = check("Crear modelo", 201, "POST", "/admin/modelos",
                      {"nombre": model_name, "descripcion": "Prueba automatizada 006"},
                      admin_token)
        model_id = model["id_modelo"]
        report["id_modelo_prueba"] = model_id
        check("Rechazar modelo duplicado", 409, "POST", "/admin/modelos",
              {"nombre": model_name}, admin_token)
        check("Editar y desactivar modelo", 200, "POST",
              f"/admin/modelos/{model_id}/actualizar",
              {"nombre": model_name, "descripcion": "Prueba finalizada", "activo": False},
              admin_token)
        buyer = check("Crear comprador", 201, "POST", "/admin/clientes",
                      {"nombre": "Comprador HTTP " + suffix,
                       "correo": client_email, "password": client_password},
                      admin_token)
        buyer_id = buyer["id_usuario"]
        report["id_comprador_prueba"] = buyer_id
        buyer_login = check("Login comprador", 200, "POST", "/auth/login",
                            {"correo": client_email, "password": client_password})
        buyer_token = buyer_login["access_token"]
        check("Auditoría restringida al comprador", 403, "GET", "/admin/auditoria",
              token=buyer_token)
        check("Desactivar comprador", 200, "POST",
              f"/admin/clientes/{buyer_id}/actualizar",
              {"nombre": "Comprador HTTP " + suffix,
               "correo": client_email, "activo": False}, admin_token)
        check("Sesión revocada tras desactivación", 401, "GET", "/auth/me",
              token=buyer_token)
        check("Login de comprador inactivo", 401, "POST", "/auth/login",
              {"correo": client_email, "password": client_password})
        audit = check("Consultar auditoría", 200, "GET", "/admin/auditoria?limite=100",
                      token=admin_token)
        expected_actions = {
            ("CREAR_MODELO", "modelo", str(model_id)),
            ("ACTUALIZAR_MODELO", "modelo", str(model_id)),
            ("CREAR_CLIENTE", "usuario", str(buyer_id)),
            ("ACTUALIZAR_CLIENTE", "usuario", str(buyer_id)),
        }
        found = {(row["accion"], row["tipo_recurso"], str(row["id_recurso"]))
                 for row in audit["eventos"]}
        audit_ok = expected_actions <= found
        results.append({"prueba": "Persistencia de cuatro acciones en auditoría",
                        "correcto": audit_ok})
        if not audit_ok:
            raise RuntimeError("Faltan acciones esperadas en auditoría.")
        print("Acciones verificadas en auditoría.")
    finally:
        # Cerrar las sesiones obtenidas incluso si falla una comprobación.
        for token in (buyer_token, admin_token):
            if token:
                try:
                    request("POST", "/auth/logout", token=token)
                except Exception:
                    pass
        report["fecha_utc"] = datetime.now(timezone.utc).isoformat()
        folder = Path.cwd() / "respaldos_rds"
        folder.mkdir(exist_ok=True)
        destination = folder / ("http_admin_" + suffix + ".json")
        with destination.open("x", encoding="utf-8") as output:
            json.dump(report, output, ensure_ascii=False, indent=2)
        print("Informe guardado en", destination)
        print("Los registros de prueba creados se conservan para auditoría.")
    print("Todas las comprobaciones HTTP terminaron correctamente.")


if __name__ == "__main__":
    main()
