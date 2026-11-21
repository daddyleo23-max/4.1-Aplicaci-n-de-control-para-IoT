from fastapi import Depends
from app.security import verificar_api_key

from fastapi import APIRouter, HTTPException
import pymysql

from app.services.procedimiento_service import ProcedimientoService

router = APIRouter(tags=["Vehículos"])
servicio = ProcedimientoService()


@router.get("/vehiculos")
def obtener_vehiculos():
    try:
        vehiculos = servicio.ejecutar_consulta("sp_obtener_vehiculos")

        return {
            "total": len(vehiculos),
            "vehiculos": vehiculos,
        }

    except pymysql.MySQLError as error:
        print(f"Error al consultar vehículos: {error}")
        raise HTTPException(
            status_code=500,
            detail="No fue posible consultar los vehículos.",
        ) from error


@router.get("/vehiculos/{id_vehiculo}", summary="Obtener vehículo por ID")
def obtener_vehiculo(id_vehiculo: int):
    if id_vehiculo <= 0:
        raise HTTPException(
            status_code=422,
            detail="El identificador debe ser positivo.",
        )

    try:
        vehiculos = servicio.ejecutar_consulta("sp_obtener_vehiculos")

        for vehiculo in vehiculos:
            if vehiculo.get("id_vehiculo") == id_vehiculo:
                return vehiculo

        raise HTTPException(
            status_code=404,
            detail="No se encontró el vehículo solicitado.",
        )

    except pymysql.MySQLError as error:
        print(f"Error al consultar vehículo: {error}")
        raise HTTPException(
            status_code=500,
            detail="No fue posible consultar el vehículo.",
        ) from error



# CRUD de vehículos: usa los procedimientos almacenados existentes.
from app.models import VehiculoCrearRequest, VehiculoActualizarRequest
from app.services.procedimiento_service import ProcedimientoService as _ProcedimientoService
_crud_vehiculos = _ProcedimientoService()

@router.post(
    "/vehiculos",
    status_code=201,
    summary="Crear vehículo",
    dependencies=[Depends(verificar_api_key)],
)
def crear_vehiculo(datos: VehiculoCrearRequest):
    try:
        _crud_vehiculos.ejecutar_transaccion([
            ("sp_crear_vehiculo", (datos.nombre, datos.modelo, datos.descripcion, datos.microcontrolador))
        ])
        return {"mensaje": "Vehículo creado correctamente."}
    except pymysql.MySQLError as error:
        print(f"Error al crear vehículo: {error}")
        raise HTTPException(status_code=400, detail="No fue posible crear el vehículo; revisa los datos enviados.") from error

@router.post(
    "/vehiculos/{id_vehiculo}/actualizar",
    summary="Actualizar vehículo",
    dependencies=[Depends(verificar_api_key)],
)
def actualizar_vehiculo(id_vehiculo: int, datos: VehiculoActualizarRequest):
    if id_vehiculo <= 0:
        raise HTTPException(status_code=422, detail="El identificador debe ser positivo.")
    try:
        _crud_vehiculos.ejecutar_transaccion([
            ("sp_actualizar_vehiculo", (id_vehiculo, datos.nombre, datos.modelo, datos.descripcion, datos.microcontrolador, datos.activo))
        ])
        return {"mensaje": "Vehículo actualizado correctamente.", "id_vehiculo": id_vehiculo}
    except pymysql.MySQLError as error:
        print(f"Error al actualizar vehículo: {error}")
        raise HTTPException(status_code=400, detail="No fue posible actualizar el vehículo.") from error

@router.post("/vehiculos/{id_vehiculo}/eliminar", summary="Eliminar vehículo", dependencies=[Depends(verificar_api_key)])
def eliminar_vehiculo(id_vehiculo: int):
    if id_vehiculo <= 0:
        raise HTTPException(status_code=422, detail="El identificador debe ser positivo.")
    try:
        _crud_vehiculos.ejecutar_transaccion([("sp_eliminar_vehiculo", (id_vehiculo,))])
        return {"mensaje": "Solicitud de eliminación ejecutada.", "id_vehiculo": id_vehiculo}
    except pymysql.MySQLError as error:
        print(f"Error al eliminar vehículo: {error}")
        raise HTTPException(status_code=400, detail="No fue posible eliminar el vehículo; puede tener registros relacionados.") from error
