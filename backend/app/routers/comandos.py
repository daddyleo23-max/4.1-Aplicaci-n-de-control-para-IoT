from fastapi import Depends
from app.security import verificar_api_key

from fastapi import APIRouter, HTTPException
import pymysql

from app.services.procedimiento_service import ProcedimientoService

router = APIRouter(tags=["Comandos y estado"])
servicio = ProcedimientoService()


@router.get("/vehiculos/{id_vehiculo}/comandos")
def obtener_comandos(id_vehiculo: int):
    try:
        comandos = servicio.ejecutar_consulta(
            "sp_obtener_comandos_vehiculo",
            (id_vehiculo,),
        )

        return {
            "id_vehiculo": id_vehiculo,
            "total": len(comandos),
            "comandos": comandos,
        }

    except pymysql.MySQLError as error:
        print(f"Error al consultar comandos: {error}")
        raise HTTPException(
            status_code=500,
            detail="No fue posible consultar los comandos.",
        ) from error


@router.get("/vehiculos/{id_vehiculo}/estado")
def obtener_estado(id_vehiculo: int):
    try:
        estados = servicio.ejecutar_consulta(
            "sp_obtener_estado",
            (id_vehiculo,),
        )

        if not estados:
            raise HTTPException(
                status_code=404,
                detail="No se encontró el estado del vehículo.",
            )

        return estados[0]

    except pymysql.MySQLError as error:
        print(f"Error al consultar estado: {error}")
        raise HTTPException(
            status_code=500,
            detail="No fue posible consultar el estado.",
        ) from error


# CRUD de comandos.
from app.models import ComandoCrearRequest, ComandoActualizarRequest
from app.services.procedimiento_service import ProcedimientoService as _ProcedimientoService
_crud_comandos = _ProcedimientoService()

@router.post(
    "/vehiculos/{id_vehiculo}/comandos",
    status_code=201,
    summary="Crear comando",
    dependencies=[Depends(verificar_api_key)],
)
def crear_comando(id_vehiculo: int, datos: ComandoCrearRequest):
    if id_vehiculo <= 0:
        raise HTTPException(status_code=422, detail="El identificador debe ser positivo.")
    try:
        _crud_comandos.ejecutar_transaccion([
            ("sp_crear_comando", (id_vehiculo, datos.nombre, datos.codigo, datos.descripcion))
        ])
        return {"mensaje": "Comando creado correctamente.", "id_vehiculo": id_vehiculo}
    except pymysql.MySQLError as error:
        print(f"Error al crear comando: {error}")
        raise HTTPException(status_code=400, detail="No fue posible crear el comando; verifica el vehículo y los datos.") from error

@router.post(
    "/comandos/{id_comando}/actualizar",
    summary="Actualizar comando",
    dependencies=[Depends(verificar_api_key)],
)
def actualizar_comando(id_comando: int, datos: ComandoActualizarRequest):
    if id_comando <= 0:
        raise HTTPException(status_code=422, detail="El identificador debe ser positivo.")
    try:
        _crud_comandos.ejecutar_transaccion([
            ("sp_actualizar_comando", (id_comando, datos.nombre, datos.codigo, datos.descripcion, datos.activo))
        ])
        return {"mensaje": "Comando actualizado correctamente.", "id_comando": id_comando}
    except pymysql.MySQLError as error:
        print(f"Error al actualizar comando: {error}")
        raise HTTPException(status_code=400, detail="No fue posible actualizar el comando.") from error

@router.post("/comandos/{id_comando}/eliminar", summary="Eliminar comando", dependencies=[Depends(verificar_api_key)])
def eliminar_comando(id_comando: int):
    if id_comando <= 0:
        raise HTTPException(status_code=422, detail="El identificador debe ser positivo.")
    try:
        _crud_comandos.ejecutar_transaccion([("sp_eliminar_comando", (id_comando,))])
        return {"mensaje": "Solicitud de eliminación ejecutada.", "id_comando": id_comando}
    except pymysql.MySQLError as error:
        print(f"Error al eliminar comando: {error}")
        raise HTTPException(status_code=400, detail="No fue posible eliminar el comando; puede tener registros relacionados.") from error
