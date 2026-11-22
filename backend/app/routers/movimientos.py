from fastapi import Depends
from app.security import verificar_api_key
from fastapi import APIRouter, HTTPException, Request
import pymysql


from app.models import MovimientoRequest
from app.services.procedimiento_service import ProcedimientoService
from datetime import datetime, timezone
from app.services.websocket_manager import manager


router = APIRouter(tags=["Movimientos"])
servicio = ProcedimientoService()


@router.post("/vehiculos/{id_vehiculo}/movimientos", status_code=201, dependencies=[Depends(verificar_api_key)])
async def registrar_movimiento(
    id_vehiculo: int,
    movimiento: MovimientoRequest,
    request: Request,
):
    from app.resource_security import sessions_enabled
    from app.services.demo_service import demo_service
    if sessions_enabled() and (request.state.session['rol'] == 'USUARIO' or getattr(request.state, 'support_operation', False)):
        from app.services.control_service import control_service
        return await control_service.move(request.state.session,id_vehiculo,movimiento.id_comando)
    if sessions_enabled():
        async with demo_service.bloqueo:
            return await _registrar_movimiento(id_vehiculo, movimiento)
    return await _registrar_movimiento(id_vehiculo, movimiento)


async def _registrar_movimiento(id_vehiculo, movimiento):
    try:
        # 1. Comprobar que el vehículo exista y esté activo.
        vehiculos = servicio.ejecutar_consulta(
            "sp_obtener_vehiculo",
            (id_vehiculo,),
        )

        if not vehiculos:
            raise HTTPException(
                status_code=404,
                detail="El vehículo no existe.",
            )

        vehiculo = vehiculos[0]

        if not vehiculo["activo"]:
            raise HTTPException(
                status_code=403,
                detail="El vehículo está inactivo.",
            )

        # 2. Comprobar que el comando pertenezca al vehículo.
        comandos = servicio.ejecutar_consulta(
            "sp_obtener_comandos_vehiculo",
            (id_vehiculo,),
        )

        comando = next(
            (
                item for item in comandos
                if item["id_comando"] == movimiento.id_comando
            ),
            None,
        )

        if comando is None:
            raise HTTPException(
                status_code=404,
                detail="El comando no existe para este vehículo.",
            )

        if not comando["activo"]:
            raise HTTPException(
                status_code=403,
                detail="El comando está inactivo.",
            )

        from app.resource_security import sessions_enabled
        if sessions_enabled() and comando['nombre'] != 'DETENER' and not any(
            c['nombre'] == 'DETENER' and c['activo'] for c in comandos
        ):
            raise HTTPException(409, 'Configura DETENER activo antes de operar esta unidad.')

        # 3. No iniciar una demo desde el endpoint individual.
        if comando["nombre"] == "DEMO":
            raise HTTPException(
                status_code=400,
                detail="Utiliza el endpoint específico para iniciar una demo.",
            )

        # 4. Conservar el estado de conexión registrado.
        estados = servicio.ejecutar_consulta(
            "sp_obtener_estado",
            (id_vehiculo,),
        )

        conectado = estados[0]["conectado"] if estados else 0

        # 5. Actualizar estado e historial en una transacción.
        from app.resource_security import sessions_enabled
        guard = [("sp_reserva_exigir_libre", (id_vehiculo,))] if sessions_enabled() else []
        servicio.ejecutar_transaccion(guard + ([("sp_capacidad_exigir", (id_vehiculo, movimiento.id_comando))] if sessions_enabled() and comando["nombre"] != "DETENER" else []) + [
            (
                "sp_actualizar_estado",
                (id_vehiculo, movimiento.id_comando, conectado),
            ),
            (
                "sp_registrar_historial",
                (id_vehiculo, movimiento.id_comando, "MANUAL"),
            ),
        ])
        await manager.enviar_a_vehiculo(
            id_vehiculo,
            {
                "tipo": "movimiento",
                "id_vehiculo": id_vehiculo,
                "id_comando": movimiento.id_comando,
                "comando": comando["nombre"],
                "codigo": comando["codigo"],
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
        )


        return {
            "mensaje": "Movimiento registrado correctamente.",
            "id_vehiculo": id_vehiculo,
            "id_comando": movimiento.id_comando,
            "comando": comando["nombre"],
        }

    except HTTPException:
        raise

    except pymysql.MySQLError as error:
        if error.args[0] in (1644, 1205, 1213):
            raise HTTPException(409, "La unidad tiene una reserva activa o el comando no está habilitado para su modelo.") from error
        print(f"Error de MySQL al registrar movimiento: {error}")
        raise HTTPException(
            status_code=503,
            detail="No fue posible completar la operación en la base de datos.",
        ) from error
