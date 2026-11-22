"""Validación 009 en localhost:8001. Crea sólo registros nuevos identificables."""
from datetime import datetime, timezone
import getpass
import json
from pathlib import Path
import secrets

from probar_admin_http import request, BASE


def main():
    print("Destino de prueba:", BASE)
    email = input("Correo del administrador de la aplicación: ").strip()
    password = getpass.getpass("Contraseña de aplicación (entrada oculta): ")
    status, login = request("POST", "/auth/login", {"correo": email, "password": password})
    password = None
    if status != 200 or login.get("usuario", {}).get("rol") != "ADMINISTRADOR":
        raise SystemExit("No se pudo iniciar sesión como administrador.")
    admin = login["access_token"]
    buyer_token = None
    buyer_id = None
    model_id = None
    suffix = secrets.token_hex(6)
    results = []
    documents = {}
    pending_units = set()
    model_name = "Inventario HTTP " + suffix
    buyer_email = "inventario-" + suffix + "@example.invalid"
    buyer_name = "Comprador inventario " + suffix
    report = {"destino": BASE, "resultados": results, "unidades_creadas": []}

    def check(label, expected, method, path, body=None, token=None):
        status, data = request(method, path, body, token)
        results.append({"prueba": label, "esperado": expected, "obtenido": status,
                        "correcto": status == expected})
        print(f"{label}: HTTP {status} (esperado {expected})")
        if status != expected:
            raise RuntimeError(f"{label}: {data.get('detail', 'Respuesta inesperada')}")
        return data

    try:
        model_id = check("Crear modelo de prueba", 201, "POST", "/admin/modelos",
                         {"nombre": model_name, "descripcion": "Validación inventario 009"}, admin)["id_modelo"]
        for index in (1, 2):
            body = {"nombre": "Unidad de prueba " + str(index), "id_modelo": model_id,
                    "identificador_unidad": f"QA-{suffix}-{index}",
                    "descripcion": "Registro de inventario, sin hardware asociado",
                    "microcontrolador": ""}
            unit_id = check(f"Registrar unidad {index}", 201, "POST", "/admin/unidades",
                            body, admin)["id_vehiculo"]
            documents[unit_id] = body
            pending_units.add(unit_id)
            report["unidades_creadas"].append(unit_id)
        first, second = report["unidades_creadas"]
        check("Rechazar identificador duplicado al crear", 409, "POST", "/admin/unidades",
              documents[first], admin)
        changed = {**documents[first], "nombre": "Unidad editada " + suffix, "activo": True}
        check("Editar unidad", 200, "POST", f"/admin/unidades/{first}/actualizar", changed, admin)
        documents[first] = {key: value for key, value in changed.items() if key != "activo"}
        check("Rechazar identificador duplicado al editar", 409, "POST",
              f"/admin/unidades/{second}/actualizar",
              {**documents[second], "identificador_unidad": changed["identificador_unidad"], "activo": True}, admin)
        units = check("Recuperar inventario", 200, "GET", "/admin/unidades?limite=100", token=admin)
        indexed = {unit["id_vehiculo"]: unit for unit in units["unidades"]}
        persisted = (indexed[first]["nombre"] == changed["nombre"]
                     and indexed[second]["identificador_unidad"] == documents[second]["identificador_unidad"])
        results.append({"prueba": "Persistencia de edición y rechazo sin cambios", "correcto": persisted})
        if not persisted:
            raise RuntimeError("El inventario no conserva los valores esperados.")
        print("Edición persistida y rechazo sin cambios: CORRECTO")
        buyer_password = secrets.token_urlsafe(24)
        buyer_id = check("Crear comprador de prueba", 201, "POST", "/admin/clientes",
                         {"nombre": buyer_name, "correo": buyer_email, "password": buyer_password}, admin)["id_usuario"]
        buyer_token = check("Login comprador", 200, "POST", "/auth/login",
                            {"correo": buyer_email, "password": buyer_password})["access_token"]
        buyer_password = None
        check("Rechazar alta sin sesión", 401, "POST", "/admin/unidades", documents[first])
        check("Rechazar alta del comprador", 403, "POST", "/admin/unidades", documents[first], buyer_token)
        check("Rechazar edición del comprador", 403, "POST", f"/admin/unidades/{first}/actualizar",
              {**documents[first], "activo": False}, buyer_token)
        for unit_id in (first, second):
            check(f"Baja lógica unidad {unit_id}", 200, "POST", f"/admin/unidades/{unit_id}/actualizar",
                  {**documents[unit_id], "activo": False}, admin)
            pending_units.discard(unit_id)
        check("Rechazar asignación de unidad inactiva", 409, "POST",
              f"/admin/unidades/{first}/asignar", {"id_usuario": buyer_id}, admin)
        units = check("Verificar conservación tras baja", 200, "GET", "/admin/unidades?limite=100", token=admin)
        indexed = {unit["id_vehiculo"]: unit for unit in units["unidades"]}
        retained = all(indexed[key]["activo"] == 0 and indexed[key]["estado_comercial"] == "INACTIVO"
                       for key in (first, second))
        results.append({"prueba": "Unidades conservadas e inactivas", "correcto": retained})
        if not retained:
            raise RuntimeError("La baja lógica no coincide con lo esperado.")
        audit = check("Consultar auditoría", 200, "GET", "/admin/auditoria?limite=100", token=admin)
        found = {(row["accion"], str(row["id_recurso"])) for row in audit["eventos"]}
        audited = all((action, str(key)) in found for key in (first, second)
                      for action in ("CREAR_UNIDAD", "ACTUALIZAR_UNIDAD"))
        results.append({"prueba": "Altas y bajas registradas en auditoría", "correcto": audited})
        if not audited:
            raise RuntimeError("Faltan acciones de inventario en auditoría.")
        print("Conservación y auditoría de unidades: CORRECTO")
    finally:
        cleanup = []
        operations = [(f"/admin/unidades/{key}/actualizar", {**documents[key], "activo": False})
                      for key in pending_units]
        if buyer_id:
            operations.append((f"/admin/clientes/{buyer_id}/actualizar",
                               {"nombre": buyer_name, "correo": buyer_email, "activo": False}))
        if model_id:
            operations.append((f"/admin/modelos/{model_id}/actualizar",
                               {"nombre": model_name, "descripcion": "Prueba finalizada", "activo": False}))
        for path, body in operations:
            try:
                code, _ = request("POST", path, body, admin)
                cleanup.append({"ruta": path, "http": code, "correcto": code == 200})
            except Exception:
                cleanup.append({"ruta": path, "correcto": False})
        for token in (buyer_token, admin):
            if token:
                try:
                    request("POST", "/auth/logout", token=token)
                except Exception:
                    pass
        report["limpieza"] = cleanup
        report["fecha_utc"] = datetime.now(timezone.utc).isoformat()
        folder = Path.cwd() / "respaldos_rds"
        folder.mkdir(exist_ok=True)
        target = folder / ("http_inventario_" + suffix + ".json")
        target.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        print("Informe guardado en", target)
        if any(not item["correcto"] for item in cleanup):
            raise RuntimeError("Revisa la limpieza de los registros nuevos en el informe.")
    print("Comprobaciones de inventario completadas. Registros de prueba conservados e inactivos.")


if __name__ == "__main__":
    main()
