from fastapi import Depends
from app.security import verificar_api_key
from fastapi import APIRouter, HTTPException
import pymysql

from app.services.procedimiento_service import ProcedimientoService
from app.services.demo_service import demo_service
from app.resource_security import sessions_enabled
from fastapi import Request

router = APIRouter(tags=["Historial y demos"])
servicio = ProcedimientoService()


@router.get("/vehiculos/{id_vehiculo}/historial")
def obtener_historial(id_vehiculo: int):
    try:
        historial = servicio.ejecutar_consulta(
            "sp_obtener_historial",
            (id_vehiculo,),
        )

        # Devolver como máximo los 10 registros más recientes.
        historial = historial[:10]

        return {
            "id_vehiculo": id_vehiculo,
            "total": len(historial),
            "historial": historial,
        }

    except pymysql.MySQLError as error:
        print(f"Error al consultar historial: {error}")
        raise HTTPException(
            status_code=500,
            detail="No fue posible consultar el historial.",
        ) from error


@router.get("/vehiculos/{id_vehiculo}/demos")
def obtener_demos(id_vehiculo: int, request: Request):
    try:
        if sessions_enabled():
            demos = servicio.ejecutar_consulta(
                "sp_editor_listar_demos", (request.state.session["id_usuario"], id_vehiculo),
            )
        else:
            demos = servicio.ejecutar_consulta("sp_obtener_demos", (id_vehiculo,))

        return {
            "id_vehiculo": id_vehiculo,
            "total": len(demos),
            "demos": demos,
        }

    except pymysql.MySQLError as error:
        print(f"Error al consultar demos: {error}")
        raise HTTPException(
            status_code=500,
            detail="No fue posible consultar las demos.",
        ) from error


@router.get("/demos/{id_demo}/movimientos")
def obtener_movimientos_demo(id_demo: int):
    try:
        movimientos = servicio.ejecutar_consulta(
            "sp_obtener_movimientos_demo",
            (id_demo,),
        )

        return {
            "id_demo": id_demo,
            "total": len(movimientos),
            "movimientos": movimientos,
        }

    except pymysql.MySQLError as error:
        print(f"Error al consultar movimientos: {error}")
        raise HTTPException(
            status_code=500,
            detail="No fue posible consultar los movimientos.",
        ) from error


@router.post("/vehiculos/{id_vehiculo}/demos/{id_demo}/iniciar", status_code=202, dependencies=[Depends(verificar_api_key)])
async def iniciar_demo(id_vehiculo: int, id_demo: int):
    return await demo_service.iniciar(id_vehiculo, id_demo)


@router.post("/vehiculos/{id_vehiculo}/demos/cancelar", dependencies=[Depends(verificar_api_key)])
async def cancelar_demo(id_vehiculo: int):
    return await demo_service.cancelar(id_vehiculo)


# CRUD de demos y movimientos de demo.
from app.models import (
    DemoCrearRequest, DemoActualizarRequest,
    MovimientoDemoCrearRequest, MovimientoDemoActualizarRequest,
)
from app.services.procedimiento_service import ProcedimientoService as _ProcedimientoService
_crud_demos = _ProcedimientoService()

@router.post(
    "/vehiculos/{id_vehiculo}/demos",
    status_code=201,
    summary="Crear demo",
    dependencies=[Depends(verificar_api_key)],
)
def crear_demo(id_vehiculo: int, datos: DemoCrearRequest):
    if id_vehiculo <= 0:
        raise HTTPException(status_code=422, detail="El identificador debe ser positivo.")
    try:
        _crud_demos.ejecutar_transaccion([
            ("sp_crear_demo", (id_vehiculo, datos.nombre, datos.descripcion))
        ])
        return {"mensaje": "Demo creada correctamente.", "id_vehiculo": id_vehiculo}
    except pymysql.MySQLError as error:
        print(f"Error al crear demo: {error}")
        raise HTTPException(status_code=400, detail="No fue posible crear la demo; verifica el vehículo y los datos.") from error

@router.post(
    "/demos/{id_demo}/actualizar",
    summary="Actualizar demo",
    dependencies=[Depends(verificar_api_key)],
)
def actualizar_demo(id_demo: int, datos: DemoActualizarRequest):
    if id_demo <= 0:
        raise HTTPException(status_code=422, detail="El identificador debe ser positivo.")
    try:
        _crud_demos.ejecutar_transaccion([
            ("sp_actualizar_demo", (id_demo, datos.nombre, datos.descripcion, datos.activo))
        ])
        return {"mensaje": "Demo actualizada correctamente.", "id_demo": id_demo}
    except pymysql.MySQLError as error:
        print(f"Error al actualizar demo: {error}")
        raise HTTPException(status_code=400, detail="No fue posible actualizar la demo.") from error

@router.post("/demos/{id_demo}/eliminar", summary="Eliminar demo", dependencies=[Depends(verificar_api_key)])
def eliminar_demo(id_demo: int):
    if id_demo <= 0:
        raise HTTPException(status_code=422, detail="El identificador debe ser positivo.")
    try:
        _crud_demos.ejecutar_transaccion([("sp_eliminar_demo", (id_demo,))])
        return {"mensaje": "Solicitud de eliminación ejecutada.", "id_demo": id_demo}
    except pymysql.MySQLError as error:
        print(f"Error al eliminar demo: {error}")
        raise HTTPException(status_code=400, detail="No fue posible eliminar la demo; puede tener movimientos relacionados.") from error

@router.post(
    "/demos/{id_demo}/movimientos",
    status_code=201,
    summary="Agregar movimiento a demo",
    dependencies=[Depends(verificar_api_key)],
)
def agregar_movimiento_demo(id_demo: int, datos: MovimientoDemoCrearRequest):
    if id_demo <= 0:
        raise HTTPException(status_code=422, detail="El identificador debe ser positivo.")
    try:
        _crud_demos.ejecutar_transaccion([
            ("sp_agregar_movimiento_demo", (id_demo, datos.id_comando, datos.orden, datos.duracion_ms, datos.pausa_ms))
        ])
        return {"mensaje": "Movimiento agregado a la demo.", "id_demo": id_demo, "orden": datos.orden}
    except pymysql.MySQLError as error:
        print(f"Error al agregar movimiento a demo: {error}")
        raise HTTPException(status_code=400, detail="No fue posible agregar el movimiento; verifica la demo y el comando.") from error

@router.post(
    "/demo-movimientos/{id_demo_movimiento}/actualizar",
    summary="Actualizar movimiento de demo",
    dependencies=[Depends(verificar_api_key)],
)
def actualizar_movimiento_demo(id_demo_movimiento: int, datos: MovimientoDemoActualizarRequest):
    if id_demo_movimiento <= 0:
        raise HTTPException(status_code=422, detail="El identificador debe ser positivo.")
    try:
        _crud_demos.ejecutar_transaccion([
            ("sp_actualizar_movimiento_demo", (id_demo_movimiento, datos.id_comando, datos.orden, datos.duracion_ms, datos.pausa_ms))
        ])
        return {"mensaje": "Movimiento de demo actualizado.", "id_demo_movimiento": id_demo_movimiento}
    except pymysql.MySQLError as error:
        print(f"Error al actualizar movimiento de demo: {error}")
        raise HTTPException(status_code=400, detail="No fue posible actualizar el movimiento.") from error

@router.post("/demo-movimientos/{id_demo_movimiento}/eliminar", summary="Eliminar movimiento de demo", dependencies=[Depends(verificar_api_key)])
def eliminar_movimiento_demo(id_demo_movimiento: int):
    if id_demo_movimiento <= 0:
        raise HTTPException(status_code=422, detail="El identificador debe ser positivo.")
    try:
        _crud_demos.ejecutar_transaccion([("sp_eliminar_movimiento_demo", (id_demo_movimiento,))])
        return {"mensaje": "Solicitud de eliminación ejecutada.", "id_demo_movimiento": id_demo_movimiento}
    except pymysql.MySQLError as error:
        print(f"Error al eliminar movimiento de demo: {error}")
        raise HTTPException(status_code=400, detail="No fue posible eliminar el movimiento.") from error
