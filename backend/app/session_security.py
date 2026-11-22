"""Identidad de sesión para las rutas nuevas de Administración."""

import hashlib

from fastapi import HTTPException, Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.services.procedimiento_service import ProcedimientoService


bearer = HTTPBearer(auto_error=False)
service = ProcedimientoService()


def token_hash(token: str) -> bytes:
    return hashlib.sha256(token.encode("utf-8")).digest()


def require_session(
    credentials: HTTPAuthorizationCredentials | None = Security(bearer),
) -> dict:
    if credentials is None or not 20 <= len(credentials.credentials) <= 200:
        raise HTTPException(401, "Sesión requerida.", headers={"WWW-Authenticate": "Bearer"})
    rows = service.ejecutar_consulta(
        "sp_auth_obtener_sesion", (token_hash(credentials.credentials),),
    )
    if not rows:
        guest = service.ejecutar_consulta("sp_invitado_obtener", (token_hash(credentials.credentials),))
        if guest:
            raise HTTPException(403, "La sesión de Invitado sólo permite las rutas de exhibición.")
        raise HTTPException(401, "Sesión vencida o revocada.",
                            headers={"WWW-Authenticate": "Bearer"})
    return rows[0]


def require_admin(session: dict = Security(require_session)) -> dict:
    if session["rol"] != "ADMINISTRADOR":
        raise HTTPException(403, "Se requiere el rol Administrador.")
    return session
