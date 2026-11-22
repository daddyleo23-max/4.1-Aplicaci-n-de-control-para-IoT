"""Catálogo comercial público. La operación del vehículo exige otra autorización."""
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field
import pymysql

from app.services.procedimiento_service import ProcedimientoService

router = APIRouter(tags=["Catálogo público 4.3"])
service = ProcedimientoService()


class PublicModel(BaseModel):
    id_modelo: int
    nombre: str
    descripcion: str
    unidades_exhibicion: int = Field(ge=0)


class CatalogResponse(BaseModel):
    modelos: list[PublicModel]
    limite: int
    offset: int


@router.get("/catalogo", response_model=CatalogResponse)
def catalog(limite: int = Query(20, ge=1, le=100), offset: int = Query(0, ge=0)):
    """Modelos publicados. El conteo de exhibición no confirma conexión física."""
    try:
        return {"modelos": service.ejecutar_consulta("sp_catalogo_modelos", (limite, offset)),
                "limite": limite, "offset": offset}
    except pymysql.MySQLError as error:
        raise HTTPException(503, "El catálogo no está disponible temporalmente.") from error
