"""Autorización por unidad para la ampliación multiusuario."""

import os

from fastapi import HTTPException, Request, Security
from fastapi.security import HTTPAuthorizationCredentials
from app.session_security import require_session, bearer
from app.services.procedimiento_service import ProcedimientoService


service = ProcedimientoService()


def check_socket_access(token, unit_id):
    from fastapi.security import HTTPAuthorizationCredentials
    session = require_session(HTTPAuthorizationCredentials(scheme="Bearer", credentials=token))
    check_unit_access(session, resource_context("vehiculo", unit_id))
    return session


def sessions_enabled():
    return os.getenv("IOT_AUTH_MODE", "legacy") == "sesiones"


def resource_context(kind, identifier):
    if identifier <= 0:
        raise HTTPException(422, "El identificador debe ser positivo.")
    rows = service.ejecutar_consulta("sp_acceso_recurso", (kind, identifier))
    if not rows:
        raise HTTPException(404, "Recurso no encontrado.")
    return rows[0]


def check_unit_access(session, unit, inventory=False):
    if session["rol"] == "ADMINISTRADOR":
        if inventory:
            return
        if unit["id_propietario"] is None and unit["activo"]:
            return
        raise HTTPException(403, "La unidad requiere autorización operativa de su comprador.")
    if unit["activo"] and unit["id_propietario"] == session["id_usuario"]:
        return
    raise HTTPException(403, "No tienes acceso a esta unidad.")


async def authorize_resources(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Security(bearer),
):
    if not sessions_enabled():
        return
    session = require_session(credentials)
    request.state.session = session
    route = request.scope["route"].path
    params = request.path_params
    is_admin = session["rol"] == "ADMINISTRADOR"
    write = request.method != "GET"
    inventory_route = route in {
        "/vehiculos", "/vehiculos/{id_vehiculo}",
        "/vehiculos/{id_vehiculo}/actualizar", "/vehiculos/{id_vehiculo}/eliminar",
    }
    if write and (route.startswith("/demos/") or route.startswith("/demo-movimientos/")
                  or route == "/vehiculos/{id_vehiculo}/demos"):
        raise HTTPException(409, "Guarda la secuencia completa mediante el editor /mis-demos.")
    # Las bajas de unidades y comandos requieren conservar el historial.
    if write and route in {"/vehiculos/{id_vehiculo}/eliminar", "/comandos/{id_comando}/eliminar"}:
        raise HTTPException(409, "Utiliza la actualización con activo=false para la baja lógica.")
    # La edición privada de demos se incorporará con su modelo de propiedad.
    admin_write = write and route not in {
        "/vehiculos/{id_vehiculo}/movimientos",
        "/vehiculos/{id_vehiculo}/demos/{id_demo}/iniciar",
        "/vehiculos/{id_vehiculo}/demos/cancelar",
    }
    if (route == "/vehiculos" or admin_write) and not is_admin:
        raise HTTPException(403, "Se requiere el rol Administrador para esta operación.")
    mapping = (("id_vehiculo", "vehiculo"), ("id_comando", "comando"),
               ("id_demo", "demo"), ("id_demo_movimiento", "paso"))
    expected_unit = None
    for field, kind in mapping:
        if field not in params:
            continue
        unit = resource_context(kind, int(params[field]))
        if kind in ("demo", "paso"):
            if kind == "paso":
                raise HTTPException(409, "Utiliza el editor de secuencias.")
            visible = service.ejecutar_consulta(
                "sp_editor_detalle_demo", (session["id_usuario"], int(params[field])),
            )
            if not visible:
                raise HTTPException(404, "Demo no encontrada o sin acceso.")
        if expected_unit is not None and unit["id_vehiculo"] != expected_unit:
            raise HTTPException(403, "Los recursos pertenecen a unidades diferentes.")
        expected_unit = unit["id_vehiculo"]
        check_unit_access(session, unit, inventory=inventory_route or admin_write)
