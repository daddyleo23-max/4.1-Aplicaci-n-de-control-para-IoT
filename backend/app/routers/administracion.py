from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field, field_validator
import pymysql

from app.passwords import hash_password
from app.session_security import require_admin
from app.services.procedimiento_service import ProcedimientoService
from app.services.demo_service import demo_service
import asyncio


router = APIRouter(prefix="/admin", tags=["Administración 4.3"])
service = ProcedimientoService()


class ModelRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    nombre: str = Field(min_length=1, max_length=100)
    descripcion: str = Field(default="", max_length=500)


class ClientRequest(BaseModel):
    nombre: str = Field(min_length=1, max_length=120)
    correo: str = Field(min_length=3, max_length=254, pattern=r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
    password: str = Field(min_length=12, max_length=256)

    @field_validator("nombre", "correo", mode="before")
    @classmethod
    def normalize_text(cls, value):
        return value.strip() if isinstance(value, str) else value

    @field_validator("correo")
    @classmethod
    def normalize_email(cls, value):
        return value.lower()


class UnitConfiguration(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    id_modelo: int = Field(gt=0)
    identificador_unidad: str = Field(min_length=1, max_length=80)


class AssignmentRequest(BaseModel):
    id_usuario: int = Field(gt=0)


class UnitRequest(UnitConfiguration):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    nombre: str = Field(min_length=1, max_length=80)
    descripcion: str = Field(default="", max_length=255)
    microcontrolador: str = Field(default="", max_length=50)


class UnitUpdate(UnitRequest):
    activo: bool


class ModelUpdate(ModelRequest):
    activo: bool


class ModelPublication(BaseModel):
    model_config = ConfigDict(extra="forbid")
    publico: bool


class ExhibitionConfiguration(BaseModel):
    model_config = ConfigDict(extra="forbid")
    habilitada: bool


class ClientUpdate(BaseModel):
    nombre: str = Field(min_length=1, max_length=120)
    correo: str = Field(min_length=3, max_length=254, pattern=r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
    activo: bool

    @field_validator("nombre", "correo", mode="before")
    @classmethod
    def normalize_text(cls, value):
        return value.strip() if isinstance(value, str) else value

    @field_validator("correo")
    @classmethod
    def normalize_email(cls, value):
        return value.lower()


def create(procedure, parameters):
    try:
        return service.ejecutar_consulta_transaccional(procedure, parameters)[0]
    except pymysql.IntegrityError as error:
        if error.args[0] == 1062:
            raise HTTPException(409, "Ya existe un registro con ese nombre, correo o identificador.") from error
        raise
    except pymysql.OperationalError as error:
        if error.args[0] == 1644:
            raise HTTPException(409, str(error.args[1])) from error
        raise


@router.get("/resumen")
def summary(session: dict = Depends(require_admin)):
    return service.ejecutar_consulta("sp_admin_resumen")[0]


@router.get("/modelos")
def models(limite: int = Query(20, ge=1, le=100),
           offset: int = Query(0, ge=0), session: dict = Depends(require_admin)):
    return {"modelos": service.ejecutar_consulta("sp_admin_listar_modelos", (limite, offset)),
            "limite": limite, "offset": offset}


@router.post("/modelos", status_code=201)
def create_model(data: ModelRequest, session: dict = Depends(require_admin)):
    return create("sp_admin_crear_modelo",
                  (session["id_usuario"], data.nombre, data.descripcion))


@router.get("/clientes")
def clients(limite: int = Query(20, ge=1, le=100),
            offset: int = Query(0, ge=0), session: dict = Depends(require_admin)):
    return {"clientes": service.ejecutar_consulta("sp_admin_listar_clientes", (limite, offset)),
            "limite": limite, "offset": offset}


@router.post("/clientes", status_code=201)
def create_client(data: ClientRequest, session: dict = Depends(require_admin)):
    return create("sp_admin_crear_cliente",
                  (session["id_usuario"], data.nombre, data.correo, hash_password(data.password)))


@router.get("/unidades")
def units(limite: int = Query(20, ge=1, le=100),
          offset: int = Query(0, ge=0), session: dict = Depends(require_admin)):
    return {"unidades": service.ejecutar_consulta("sp_admin_listar_unidades", (limite, offset)),
            "limite": limite, "offset": offset}


@router.post("/unidades/{id_vehiculo}/configurar", deprecated=True)
def configure_unit(id_vehiculo: int, data: UnitConfiguration,
                   session: dict = Depends(require_admin)):
    raise HTTPException(409, "Utiliza /admin/unidades/{id_vehiculo}/actualizar con los datos completos de la unidad.")


@router.post("/unidades", status_code=201)
def create_unit(data: UnitRequest, session: dict = Depends(require_admin)):
    return create("sp_admin_crear_unidad", (
        session["id_usuario"], data.nombre, data.id_modelo, data.identificador_unidad,
        data.descripcion, data.microcontrolador,
    ))


@router.post("/unidades/{id_vehiculo}/actualizar")
async def update_unit(id_vehiculo: int, data: UnitUpdate,
                      session: dict = Depends(require_admin)):
    if id_vehiculo <= 0:
        raise HTTPException(422, "El identificador debe ser positivo.")
    async with demo_service.bloqueo:
        task = demo_service.tareas.get(id_vehiculo)
        if task is not None and not task.done():
            raise HTTPException(409, "Espera o cancela la demo antes de editar la unidad.")
        return await asyncio.to_thread(create, "sp_admin_actualizar_unidad", (
            session["id_usuario"], id_vehiculo, data.nombre, data.id_modelo,
            data.identificador_unidad, data.descripcion, data.microcontrolador, data.activo,
        ))


@router.post("/unidades/{id_vehiculo}/asignar")
def assign_unit(id_vehiculo: int, data: AssignmentRequest,
                session: dict = Depends(require_admin)):
    return create("sp_admin_asignar_unidad",
                  (session["id_usuario"], id_vehiculo, data.id_usuario))


@router.post("/unidades/{id_vehiculo}/exhibicion")
async def set_exhibition(id_vehiculo: int, data: ExhibitionConfiguration,
                         session: dict = Depends(require_admin)):
    if id_vehiculo <= 0:
        raise HTTPException(422, "El identificador debe ser positivo.")
    async with demo_service.bloqueo:
        task = demo_service.tareas.get(id_vehiculo)
        if task is not None and not task.done():
            raise HTTPException(409, "Espera o cancela la demo antes de configurar exhibición.")
        return await asyncio.to_thread(create, "sp_admin_marcar_exhibicion",
                                       (session["id_usuario"], id_vehiculo, data.habilitada))


@router.post("/modelos/{id_modelo}/actualizar")
def update_model(id_modelo: int, data: ModelUpdate,
                 session: dict = Depends(require_admin)):
    return create("sp_admin_actualizar_modelo",
                  (session["id_usuario"], id_modelo, data.nombre, data.descripcion, data.activo))


@router.post("/modelos/{id_modelo}/publicacion")
def publish_model(id_modelo: int, data: ModelPublication,
                  session: dict = Depends(require_admin)):
    if id_modelo <= 0:
        raise HTTPException(422, "El identificador debe ser positivo.")
    return create("sp_admin_publicar_modelo", (session["id_usuario"], id_modelo, data.publico))


@router.post("/clientes/{id_usuario}/actualizar")
def update_client(id_usuario: int, data: ClientUpdate,
                  session: dict = Depends(require_admin)):
    return create("sp_admin_actualizar_cliente",
                  (session["id_usuario"], id_usuario, data.nombre, data.correo, data.activo))


@router.get("/auditoria")
def audit(limite: int = Query(20, ge=1, le=100),
          offset: int = Query(0, ge=0), session: dict = Depends(require_admin)):
    return {"eventos": service.ejecutar_consulta("sp_admin_listar_auditoria", (limite, offset)),
            "limite": limite, "offset": offset}
