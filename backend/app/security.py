import secrets

from fastapi import HTTPException, Security, Request
from fastapi.security import APIKeyHeader

from app.config import API_KEY

_esquema = APIKeyHeader(name="X-API-Key", auto_error=False)


def verificar_api_key(request: Request, api_key: str | None = Security(_esquema)) -> None:
    from app.resource_security import sessions_enabled
    if sessions_enabled():
        if getattr(request.state, "session", None) is None:
            raise HTTPException(401, "Sesión requerida.")
        return
    if not api_key:
        raise HTTPException(status_code=401, detail="Falta la API key.")
    if not API_KEY or not secrets.compare_digest(api_key, API_KEY):
        raise HTTPException(status_code=403, detail="API key inválida.")
