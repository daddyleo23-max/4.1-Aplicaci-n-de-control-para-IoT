from datetime import datetime, timedelta, timezone
import secrets

from fastapi import APIRouter, Depends, Response, Request
from pydantic import BaseModel, Field

from app.passwords import hash_password, verify_password
from app.session_security import require_session, token_hash
from app.services.procedimiento_service import ProcedimientoService


router = APIRouter(prefix="/auth", tags=["Autenticación 4.3"])
service = ProcedimientoService()
DUMMY_HASH = hash_password(secrets.token_urlsafe(32))


class LoginRequest(BaseModel):
    correo: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=1, max_length=256)


def public_user(row: dict) -> dict:
    return {key: row[key] for key in ("id_usuario", "nombre", "correo", "rol")}


@router.post("/login", summary="Iniciar sesión de aplicación",
             responses={401: {"description": "Credenciales inválidas o cuenta inactiva"},
                        429: {"description": "Límite de intentos; Retry-After indica segundos de espera"}})
def login(data: LoginRequest, response: Response, request: Request):
    from fastapi import HTTPException

    from app.login_limits import login_limiter
    login_limiter.check(request.client.host if request.client else "unknown", data.correo)
    response.headers["Cache-Control"] = "no-store"
    rows = service.ejecutar_consulta(
        "sp_auth_buscar_usuario", (data.correo.strip().lower(),),
    )
    user = rows[0] if rows else None
    valid = verify_password(data.password, user["password_hash"] if user else DUMMY_HASH)
    if user is None or not valid or not user["activo"]:
        raise HTTPException(401, "Credenciales inválidas.",
                            headers={"Cache-Control": "no-store"})
    token = secrets.token_urlsafe(32)
    expires = datetime.now(timezone.utc) + timedelta(hours=1)
    result = service.ejecutar_consulta_transaccional(
        "sp_auth_crear_sesion",
        (user["id_usuario"], token_hash(token), expires.replace(tzinfo=None)),
    )
    if not result or result[0]["creadas"] != 1:
        raise HTTPException(401, "La cuenta no está disponible.")
    return {
        "access_token": token,
        "token_type": "bearer",
        "expires_at": expires.isoformat(),
        "usuario": public_user(user),
    }


@router.get("/me")
def me(response: Response, session: dict = Depends(require_session)):
    response.headers["Cache-Control"] = "no-store"
    return {"usuario": public_user(session)}


@router.post("/logout")
def logout(response: Response, session: dict = Depends(require_session)):
    service.ejecutar_transaccion([
        ("sp_auth_revocar_sesion", (session["id_sesion"],)),
    ])
    response.headers["Cache-Control"] = "no-store"
    return {"mensaje": "Sesión cerrada."}
