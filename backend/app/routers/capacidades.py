"""Capacidades del modelo y comandos por unidad; sólo Administración."""
import asyncio
from fastapi import APIRouter, Depends, HTTPException, Path
from pydantic import BaseModel, ConfigDict, Field, ValidationError
import pymysql
from app.session_security import require_admin
from app.services.procedimiento_service import ProcedimientoService
from app.services.demo_service import demo_service
from app.services.control_service import complete

router=APIRouter(tags=['Capacidades y comandos 4.3'])
service=ProcedimientoService()


class Capability(BaseModel):
    model_config=ConfigDict(extra='forbid',str_strip_whitespace=True)
    nombre: str=Field(min_length=1,max_length=60,pattern=r'^[A-Z][A-Z0-9_]*$')
    codigo: int=Field(ge=1,le=65535)
    descripcion: str=Field(default='',max_length=255)
    activo: bool=True


class UnitCommand(BaseModel):
    model_config=ConfigDict(extra='forbid',str_strip_whitespace=True)
    id_capacidad: int=Field(gt=0)
    descripcion: str=Field(default='',max_length=255)
    activo: bool=True


def unit_context(unit):
    rows=service.ejecutar_consulta('sp_obtener_vehiculo',(unit,))
    if not rows:raise HTTPException(404,'Unidad no encontrada.')
    return rows[0]


def validate_model(model):
    # Listar paginadamente conserva los contratos reales existentes.
    offset=0
    while True:
        rows=service.ejecutar_consulta('sp_admin_listar_modelos',(100,offset))
        if any(row['id_modelo']==model for row in rows):return
        if len(rows)<100:raise HTTPException(404,'Modelo no encontrado.')
        offset+=100


def write(name,args):
    try:return service.ejecutar_consulta_transaccional(name,args)[0]
    except pymysql.MySQLError as error:
        if error.args[0] in (1644,1062,1205,1213):
            raise HTTPException(409,'Cambio incompatible: revisa capacidades, códigos, DETENER y reservas activas.') from error
        raise HTTPException(503,'No se pudo guardar la configuración.') from error


async def save_capability(model,capability,data,session):
    async with demo_service.bloqueo:
        for unit,task in list(demo_service.tareas.items()):
            if not task.done() and (await asyncio.to_thread(unit_context,unit))['id_modelo']==model:
                raise HTTPException(409,'Cancela las demos del modelo antes de editar capacidades.')
        return await complete(asyncio.to_thread(write,'sp_capacidad_guardar',
            (session['id_usuario'],model,capability,data.nombre,data.codigo,data.descripcion,data.activo)))


async def save_command(unit,command,data,session):
    async with demo_service.bloqueo:
        task=demo_service.tareas.get(unit)
        if task and not task.done():raise HTTPException(409,'Cancela la demo antes de editar comandos.')
        return await complete(asyncio.to_thread(write,'sp_capacidad_comando_guardar',
            (session['id_usuario'],unit,command,data.id_capacidad,data.descripcion,data.activo)))


@router.get('/admin/modelos/{id_modelo}/capacidades')
def capabilities(id_modelo: int=Path(gt=0),session: dict=Depends(require_admin)):
    validate_model(id_modelo)
    return {'capacidades':service.ejecutar_consulta('sp_capacidad_listar',(id_modelo,))}


@router.post('/admin/modelos/{id_modelo}/capacidades',status_code=201)
async def create(data: Capability,id_modelo: int=Path(gt=0),session: dict=Depends(require_admin)):
    return await save_capability(id_modelo,None,data,session)


@router.post('/admin/modelos/{id_modelo}/capacidades/{id_capacidad}/actualizar')
async def update(data: Capability,id_modelo: int=Path(gt=0),id_capacidad: int=Path(gt=0),session: dict=Depends(require_admin)):
    return await save_capability(id_modelo,id_capacidad,data,session)


@router.get('/admin/unidades/{id_vehiculo}/comandos')
def commands(id_vehiculo: int=Path(gt=0),session: dict=Depends(require_admin)):
    unit=unit_context(id_vehiculo)
    return {'id_modelo':unit['id_modelo'],
            'comandos':service.ejecutar_consulta('sp_capacidad_comandos_unidad',(id_vehiculo,)),
            'capacidades':service.ejecutar_consulta('sp_capacidad_listar',(unit['id_modelo'],)) if unit['id_modelo'] else []}


@router.post('/admin/unidades/{id_vehiculo}/comandos',status_code=201)
async def add_command(data: UnitCommand,id_vehiculo: int=Path(gt=0),session: dict=Depends(require_admin)):
    return await save_command(id_vehiculo,None,data,session)


@router.post('/admin/unidades/{id_vehiculo}/comandos/{id_comando}/actualizar')
async def edit_command(data: UnitCommand,id_vehiculo: int=Path(gt=0),id_comando: int=Path(gt=0),session: dict=Depends(require_admin)):
    return await save_command(id_vehiculo,id_comando,data,session)


async def legacy_save(unit,command,data,session):
    context=await asyncio.to_thread(unit_context,unit)
    caps=await asyncio.to_thread(service.ejecutar_consulta,'sp_capacidad_listar',(context['id_modelo'],)) if context['id_modelo'] else []
    cap=next((c for c in caps if c['codigo']==data.codigo and c['nombre'].upper()==data.nombre.strip().upper()),None)
    if not cap:raise HTTPException(409,'Configura primero esa capacidad en el modelo desde Administración.')
    try:
        validated=UnitCommand(id_capacidad=cap['id_capacidad'],descripcion=data.descripcion,activo=getattr(data,'activo',True))
    except ValidationError as error:
        raise HTTPException(422,'La descripción admite como máximo 255 caracteres.') from error
    return await save_command(unit,command,validated,session)
