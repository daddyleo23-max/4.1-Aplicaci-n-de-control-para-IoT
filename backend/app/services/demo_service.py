import asyncio
from datetime import datetime, timezone

from fastapi import HTTPException

from app.services.procedimiento_service import ProcedimientoService
from app.services.websocket_manager import manager


class DemoService:
    def __init__(self):
        self.servicio = ProcedimientoService()
        self.tareas: dict[int, asyncio.Task] = {}
        self.bloqueo = asyncio.Lock()

    async def iniciar(self, id_vehiculo: int, id_demo: int, control=None) -> dict:
        vehiculos = await asyncio.to_thread(
            self.servicio.ejecutar_consulta,
            "sp_obtener_vehiculo",
            (id_vehiculo,),
        )
        if not vehiculos:
            raise HTTPException(404, "El vehículo no existe.")
        if not vehiculos[0]["activo"]:
            raise HTTPException(403, "El vehículo está inactivo.")

        demos = await asyncio.to_thread(
            self.servicio.ejecutar_consulta,
            "sp_obtener_demos",
            (id_vehiculo,),
        )
        demo = next(
            (item for item in demos if item["id_demo"] == id_demo),
            None,
        )
        if demo is None:
            raise HTTPException(
                404, "La demo no existe o no pertenece a este vehículo."
            )
        if not demo["activo"]:
            raise HTTPException(403, "La demo está inactiva.")

        movimientos = await asyncio.to_thread(
            self.servicio.ejecutar_consulta,
            "sp_obtener_movimientos_demo",
            (id_demo,),
        )
        if not movimientos:
            raise HTTPException(400, "La demo no tiene movimientos.")

        async with self.bloqueo:
            actual = self.tareas.get(id_vehiculo)
            if actual is not None and not actual.done():
                raise HTTPException(
                    409, "Ya hay una demo ejecutándose en este vehículo."
                )
            from app.resource_security import sessions_enabled
            if sessions_enabled():
                import pymysql
                commands = await asyncio.to_thread(self.servicio.ejecutar_consulta, 'sp_obtener_comandos_vehiculo', (id_vehiculo,))
                if not any(c['nombre'] == 'DETENER' and c['activo'] for c in commands):
                    raise HTTPException(409, 'Configura DETENER activo antes de ejecutar demos.')
                try:
                    await asyncio.to_thread(self.servicio.ejecutar_transaccion,
                                            ([("sp_control_exigir", control)] if control else [("sp_reserva_exigir_libre", (id_vehiculo,))]) +
                                            [("sp_capacidad_exigir", (id_vehiculo, step["id_comando"])) for step in movimientos])
                except pymysql.MySQLError as error:
                    if error.args[0] in (1644, 1205, 1213):
                        raise HTTPException(409, "La demo contiene comandos deshabilitados o la unidad tiene una reserva incompatible.") from error
                    raise

            tarea = asyncio.create_task(
                self._ejecutar(id_vehiculo, id_demo, movimientos, control=control)
            )
            self.tareas[id_vehiculo] = tarea

        return {
            "mensaje": "La demo se inició.",
            "id_vehiculo": id_vehiculo,
            "id_demo": id_demo,
            "movimientos_programados": len(movimientos),
        }

    async def cancelar(self, id_vehiculo: int) -> dict:
        async with self.bloqueo:
            tarea = self.tareas.get(id_vehiculo)
            if tarea is None or tarea.done():
                raise HTTPException(
                    404, "No hay una demo en ejecución para este vehículo."
                )
            tarea.cancel()

        return {
            "mensaje": "Se solicitó cancelar la demo.",
            "id_vehiculo": id_vehiculo,
        }

    async def _ejecutar(
        self, id_vehiculo: int, id_demo: int, movimientos: list[dict], control=None
    ) -> None:
        try:
            await manager.enviar_a_vehiculo(
                id_vehiculo,
                self._evento("demo_inicio", id_vehiculo, id_demo),
            )

            estados = await asyncio.to_thread(
                self.servicio.ejecutar_consulta,
                "sp_obtener_estado",
                (id_vehiculo,),
            )
            conectado = estados[0]["conectado"] if estados else 0

            for movimiento in movimientos:
                # Usar una transacción para confirmar el cambio de estado.
                from app.services.control_service import complete
                from app.resource_security import sessions_enabled
                await complete(asyncio.to_thread(
                    self.servicio.ejecutar_transaccion,
                    ([("sp_control_exigir", control)] if control else []) +
                    ([("sp_capacidad_exigir", (id_vehiculo, movimiento["id_comando"]))]
                     if sessions_enabled() and movimiento['comando'] != 'DETENER' else []) + [(
                        "sp_actualizar_estado",
                        (
                            id_vehiculo,
                            movimiento["id_comando"],
                            conectado,
                        ),
                    )],
                ))

                await manager.enviar_a_vehiculo(
                    id_vehiculo,
                    {
                        **self._evento(
                            "demo_movimiento", id_vehiculo, id_demo
                        ),
                        "id_demo_movimiento": movimiento.get(
                            "id_demo_movimiento"
                        ),
                        "orden": movimiento["orden"],
                        "id_comando": movimiento["id_comando"],
                        "comando": movimiento["comando"],
                        "codigo": movimiento["codigo"],
                        "duracion_ms": movimiento["duracion_ms"],
                        "pausa_ms": movimiento["pausa_ms"],
                    },
                )

                await asyncio.sleep(movimiento["duracion_ms"] / 1000)
                if movimiento["pausa_ms"]:
                    await asyncio.sleep(movimiento["pausa_ms"] / 1000)

            # Completar la secuencia incluye solicitar STOP, sin historial individual.
            await self._detener_seguro(id_vehiculo, id_demo, "demo_fin")

        except asyncio.CancelledError:
            await self._detener_seguro(
                id_vehiculo, id_demo, "demo_cancelada"
            )
            raise
        except Exception:
            await self._detener_seguro(
                id_vehiculo, id_demo, "demo_error"
            )
        finally:
            tarea = asyncio.current_task()
            async with self.bloqueo:
                if self.tareas.get(id_vehiculo) is tarea:
                    self.tareas.pop(id_vehiculo, None)

    async def _detener_seguro(
        self, id_vehiculo: int, id_demo: int, tipo_evento: str
    ) -> bool:
        try:
            comandos = await asyncio.to_thread(
                self.servicio.ejecutar_consulta,
                "sp_obtener_comandos_vehiculo",
                (id_vehiculo,),
            )
            detener = next(
                (c for c in comandos if c["nombre"] == "DETENER" and c["activo"]),
                None,
            )

            if detener is not None:
                estados = await asyncio.to_thread(
                    self.servicio.ejecutar_consulta,
                    "sp_obtener_estado",
                    (id_vehiculo,),
                )
                conectado = estados[0]["conectado"] if estados else 0

                from app.services.control_service import complete
                await complete(asyncio.to_thread(
                    self.servicio.ejecutar_transaccion,
                    [(
                        "sp_actualizar_estado",
                        (id_vehiculo, detener["id_comando"], conectado),
                    )],
                ))

                evento = {
                    **self._evento(tipo_evento, id_vehiculo, id_demo),
                    "comando_seguridad": "DETENER",
                    "id_comando": detener["id_comando"],
                    "comando": "DETENER",
                    "codigo": detener["codigo"],
                }
            else:
                raise RuntimeError("No se encontró DETENER activo.")

            await manager.enviar_a_vehiculo(id_vehiculo, evento)
            return True

        except Exception:
            await manager.enviar_a_vehiculo(
                id_vehiculo,
                self._evento("demo_error", id_vehiculo, id_demo),
            )
            return False

    @staticmethod
    def _evento(tipo: str, id_vehiculo: int, id_demo: int) -> dict:
        return {
            "tipo": tipo,
            "id_vehiculo": id_vehiculo,
            "id_demo": id_demo,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }


demo_service = DemoService()
