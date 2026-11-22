import json
import asyncio

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field, model_validator
import pymysql

from app.resource_security import check_unit_access, resource_context
from app.session_security import require_session
from app.services.procedimiento_service import ProcedimientoService
from app.services.demo_service import demo_service


router = APIRouter(prefix="/mis-demos", tags=["Editor de demos 4.3"])
service = ProcedimientoService()


class DemoStep(BaseModel):
    id_comando: int = Field(gt=0)
    duracion_ms: int = Field(ge=1, le=10000)
    pausa_ms: int = Field(default=0, ge=0, le=5000)


class DemoDocument(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    id_vehiculo: int = Field(gt=0)
    nombre: str = Field(min_length=1, max_length=80)
    descripcion: str = Field(default="", max_length=255)
    activo: bool = True
    revision: int | None = Field(default=None, ge=1)
    pasos: list[DemoStep] = Field(min_length=1, max_length=100)

    @model_validator(mode="after")
    def validate_total_duration(self):
        if sum(step.duracion_ms + step.pausa_ms for step in self.pasos) > 120000:
            raise ValueError("La secuencia admite como máximo 120000 ms.")
        return self


def visible_demo(session, demo_id):
    rows = service.ejecutar_consulta(
        "sp_editor_detalle_demo", (session["id_usuario"], demo_id),
    )
    if not rows:
        raise HTTPException(404, "Demo no encontrada o sin acceso.")
    return rows[0]


def save_document(data, session, demo_id=None):
    check_unit_access(session, resource_context("vehiculo", data.id_vehiculo))
    if demo_id is not None:
        visible_demo(session, demo_id)
        if data.revision is None:
            raise HTTPException(422, "Se requiere la revisión actual de la demo.")
    parameters = (
        session["id_usuario"], demo_id, data.id_vehiculo, data.revision,
        data.nombre, data.descripcion, data.activo,
        json.dumps([step.model_dump() for step in data.pasos]),
    )
    try:
        return service.ejecutar_consulta_transaccional("sp_editor_guardar_demo", parameters,
            precondiciones=[('sp_capacidad_exigir', (data.id_vehiculo, step.id_comando)) for step in data.pasos])[0]
    except pymysql.OperationalError as error:
        if error.args[0] == 1644:
            raise HTTPException(409, str(error.args[1])) from error
        raise
    except pymysql.IntegrityError as error:
        raise HTTPException(409, "La secuencia contiene referencias incompatibles.") from error


@router.get("")
def list_demos(id_vehiculo: int, session: dict = Depends(require_session)):
    check_unit_access(session, resource_context("vehiculo", id_vehiculo))
    return {"demos": service.ejecutar_consulta(
        "sp_editor_listar_demos", (session["id_usuario"], id_vehiculo),
    )}


@router.get("/{id_demo}")
def get_demo(id_demo: int, session: dict = Depends(require_session)):
    demo = visible_demo(session, id_demo)
    steps = service.ejecutar_consulta("sp_obtener_movimientos_demo", (id_demo,))
    return {"demo": demo, "pasos": steps,
            "duracion_total_ms": sum(step["duracion_ms"] + step["pausa_ms"] for step in steps)}


async def save_when_idle(data, session, demo_id=None):
    async with demo_service.bloqueo:
        task = demo_service.tareas.get(data.id_vehiculo)
        if task is not None and not task.done():
            raise HTTPException(409, "Espera o cancela la demo en ejecución antes de editar.")
        return await asyncio.to_thread(save_document, data, session, demo_id)


@router.post("", status_code=201)
async def create_demo(data: DemoDocument, session: dict = Depends(require_session)):
    return await save_when_idle(data, session)


@router.post("/{id_demo}/guardar")
async def update_demo(id_demo: int, data: DemoDocument, session: dict = Depends(require_session)):
    return await save_when_idle(data, session, id_demo)
