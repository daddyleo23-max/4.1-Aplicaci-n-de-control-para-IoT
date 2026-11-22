"""Pruebas 010 en localhost:8001. No envía movimientos ni abre reservas."""
from datetime import datetime, timezone
import getpass
import json
from pathlib import Path
import secrets

from probar_admin_http import BASE, request


def main():
    print("Destino de prueba:", BASE)
    email = input("Correo del administrador de la aplicación: ").strip()
    password = getpass.getpass("Contraseña de aplicación (entrada oculta): ")
    status, login = request("POST", "/auth/login", {"correo": email, "password": password})
    password = None
    if status != 200 or login.get("usuario", {}).get("rol") != "ADMINISTRADOR":
        raise SystemExit("No se pudo iniciar sesión como administrador.")
    token = login["access_token"]
    model_id = unit_id = None
    suffix = secrets.token_hex(6)
    name = "Catalogo HTTP " + suffix
    results = []
    report = {"destino": BASE, "resultados": results}
    unit_body = None

    def check(label, expected, method, path, body=None, auth=None):
        status, data = request(method, path, body, auth)
        results.append({"prueba": label, "esperado": expected, "obtenido": status,
                        "correcto": status == expected})
        print(f"{label}: HTTP {status} (esperado {expected})")
        if status != expected:
            raise RuntimeError(f"{label}: {data.get('detail', 'Respuesta inesperada')}")
        return data

    def find_model():
        data = check("Consultar catálogo sin sesión", 200, "GET", "/catalogo?limite=100")
        allowed = {"id_modelo", "nombre", "descripcion", "unidades_exhibicion"}
        safe = all(set(row) == allowed for row in data["modelos"])
        results.append({"prueba": "Contrato público sin datos privados de inventario", "correcto": safe})
        if not safe:
            raise RuntimeError("El catálogo contiene campos fuera del contrato público.")
        return next((row for row in data["modelos"] if row["id_modelo"] == model_id), None)

    def verify(label, condition):
        results.append({"prueba": label, "correcto": bool(condition)})
        print(label + (": CORRECTO" if condition else ": INCORRECTO"))
        if not condition:
            raise RuntimeError(label)

    try:
        model_id = check("Crear modelo privado de prueba", 201, "POST", "/admin/modelos",
                         {"nombre": name, "descripcion": "Prueba de catálogo 010"}, token)["id_modelo"]
        report["id_modelo_prueba"] = model_id
        verify("Modelo nuevo oculto al público", find_model() is None)
        unit_body = {"nombre": "Unidad catálogo " + suffix, "id_modelo": model_id,
                     "identificador_unidad": "CAT-" + suffix,
                     "descripcion": "Registro de prueba sin hardware asociado", "microcontrolador": ""}
        unit_id = check("Crear unidad de prueba", 201, "POST", "/admin/unidades", unit_body, token)["id_vehiculo"]
        report["id_unidad_prueba"] = unit_id
        check("Rechazar exhibición de modelo privado", 409, "POST",
              f"/admin/unidades/{unit_id}/exhibicion", {"habilitada": True}, token)
        check("Rechazar publicación sin sesión", 401, "POST",
              f"/admin/modelos/{model_id}/publicacion", {"publico": True})
        check("Publicar modelo", 200, "POST", f"/admin/modelos/{model_id}/publicacion", {"publico": True}, token)
        model = find_model()
        verify("Modelo visible y unidad disponible fuera de exhibición", model is not None and model["unidades_exhibicion"] == 0)
        check("Marcar unidad de prueba para exhibición", 200, "POST",
              f"/admin/unidades/{unit_id}/exhibicion", {"habilitada": True}, token)
        model = find_model()
        verify("Una unidad de exhibición contada", model is not None and model["unidades_exhibicion"] == 1)
        units = check("Consultar inventario privado", 200, "GET", "/admin/unidades?limite=100", auth=token)["unidades"]
        owned = next((row for row in units if row["id_vehiculo"] == 1 and row["id_propietario"] is not None), None)
        if owned is None:
            raise RuntimeError("La prueba espera que la unidad 1 continúe asignada. Revisa el inventario antes de continuar.")
        check("Rechazar exhibición de unidad 1 asignada", 409, "POST",
              "/admin/unidades/1/exhibicion", {"habilitada": True}, token)
        after = check("Verificar inventario tras rechazo", 200, "GET", "/admin/unidades?limite=100", auth=token)
        verify("Unidad 1 conservada sin cambios", next(row for row in after["unidades"] if row["id_vehiculo"] == 1) == owned)
        check("Retirar modelo del catálogo", 200, "POST", f"/admin/modelos/{model_id}/publicacion", {"publico": False}, token)
        verify("Modelo retirado deja de ser público", find_model() is None)
        check("Retirar exhibición de prueba", 200, "POST", f"/admin/unidades/{unit_id}/exhibicion", {"habilitada": False}, token)
        check("Desactivar unidad de prueba", 200, "POST", f"/admin/unidades/{unit_id}/actualizar",
              {**unit_body, "activo": False}, token)
        check("Desactivar modelo de prueba", 200, "POST", f"/admin/modelos/{model_id}/actualizar",
              {"nombre": name, "descripcion": "Prueba finalizada", "activo": False}, token)
        check("Rechazar publicación de modelo inactivo", 409, "POST",
              f"/admin/modelos/{model_id}/publicacion", {"publico": True}, token)
        audit = check("Consultar auditoría", 200, "GET", "/admin/auditoria?limite=100", auth=token)
        found = {(row["accion"], str(row["id_recurso"])) for row in audit["eventos"]}
        verify("Publicación y exhibición auditadas", {("PUBLICAR_MODELO", str(model_id)), ("EXHIBICION_UNIDAD", str(unit_id))} <= found)
    finally:
        cleanup = []
        operations = []
        if model_id:
            operations.append((f"/admin/modelos/{model_id}/publicacion", {"publico": False}))
        if unit_id:
            operations.append((f"/admin/unidades/{unit_id}/actualizar", {**unit_body, "activo": False}))
        if model_id:
            operations.append((f"/admin/modelos/{model_id}/actualizar",
                               {"nombre": name, "descripcion": "Prueba finalizada", "activo": False}))
        for path, body in operations:
            try:
                code, _ = request("POST", path, body, token)
                cleanup.append({"ruta": path, "http": code, "correcto": code == 200})
            except Exception:
                cleanup.append({"ruta": path, "correcto": False})
        try:
            request("POST", "/auth/logout", token=token)
        except Exception:
            pass
        report["limpieza"] = cleanup
        report["fecha_utc"] = datetime.now(timezone.utc).isoformat()
        folder = Path.cwd() / "respaldos_rds"
        folder.mkdir(exist_ok=True)
        target = folder / ("http_catalogo_" + suffix + ".json")
        target.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        print("Informe guardado en", target)
        if any(not item["correcto"] for item in cleanup):
            raise RuntimeError("Revisa la limpieza de los registros nuevos en el informe.")
    print("Comprobaciones del catálogo completadas. Registros nuevos privados e inactivos.")


if __name__ == "__main__":
    main()
