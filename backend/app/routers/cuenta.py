from fastapi import APIRouter, Depends

from app.session_security import require_session
from app.services.procedimiento_service import ProcedimientoService


router = APIRouter(tags=["Mi cuenta 4.3"])
service = ProcedimientoService()


@router.get("/mis-vehiculos")
def my_vehicles(session: dict = Depends(require_session)):
    return {"vehiculos": service.ejecutar_consulta(
        "sp_usuario_mis_vehiculos", (session["id_usuario"],),
    )}
