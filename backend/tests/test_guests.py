import asyncio
from datetime import datetime, timedelta, timezone
import os
import unittest
from unittest.mock import AsyncMock, Mock, patch

from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from app import session_security
from app.routers import invitados, administracion
from app.services.guest_service import GuestService
from app.services.demo_service import demo_service


CONTEXT = {"id_sesion_invitado": 10, "id_vehiculo": 7, "pulso_ms": 100,
           "expira_utc": datetime.now(timezone.utc) + timedelta(seconds=60), "segundos_restantes": 59}
STOP = {"id_comando": 80, "id_vehiculo": 7, "nombre": "DETENER", "codigo": 13, "activo": 1}


class GuestRoutesTests(unittest.TestCase):
    def setUp(self):
        self.mode = patch.dict(os.environ, {"IOT_AUTH_MODE": "sesiones"})
        self.mode.start()
        self.addCleanup(self.mode.stop)
        app = FastAPI()
        app.include_router(invitados.router)
        app.include_router(administracion.router)
        self.client = TestClient(app)
        self.headers = {"Authorization": "Bearer " + "x" * 43}

    def test_creation_is_public_but_cannot_set_duration_or_permissions(self):
        with patch.object(invitados.guest_service, "reserve", new_callable=AsyncMock) as reserve:
            response = self.client.post("/invitados/sesiones", json={"id_vehiculo": 7, "duracion_s": 999})
        self.assertEqual(response.status_code, 422)
        reserve.assert_not_awaited()

    def test_creation_returns_token_once_and_no_private_identity(self):
        with patch.object(invitados.guest_service, "reserve", AsyncMock(return_value="x" * 43)), patch.object(
            invitados.guest_service, "context", return_value=CONTEXT,
        ), patch.object(invitados.guest_service, "db", AsyncMock(return_value=[STOP])):
            response = self.client.post("/invitados/sesiones", json={"id_vehiculo": 7})
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.headers["Cache-Control"], "no-store")
        self.assertEqual(response.json()["rol"], "INVITADO")
        self.assertNotIn("token_hash", response.text)

    def test_missing_guest_bearer_rejected(self):
        self.assertEqual(self.client.get("/invitados/sesion").status_code, 401)
        self.assertEqual(self.client.post("/invitados/movimientos", json={"id_comando": 80}).status_code, 401)

    def test_guest_token_cannot_be_used_for_administration(self):
        def query(name, params):
            return [] if name == "sp_auth_obtener_sesion" else [CONTEXT]
        with patch.object(session_security.service, "ejecutar_consulta", side_effect=query):
            response = self.client.get("/admin/resumen", headers=self.headers)
        self.assertEqual(response.status_code, 403)

    def test_buyer_cannot_enable_trial(self):
        with patch.object(session_security.service, "ejecutar_consulta",
                          return_value=[{"id_usuario": 5, "rol": "USUARIO"}]):
            response = self.client.post("/admin/unidades/7/invitados", headers=self.headers,
                json={"habilitada": True, "duracion_s": 15, "pulso_ms": 100, "comandos": [80]})
        self.assertEqual(response.status_code, 403)

    def test_trial_configuration_rejects_unsafe_limits_and_duplicate_commands(self):
        with patch.object(session_security.service, "ejecutar_consulta",
                          return_value=[{"id_usuario": 4, "rol": "ADMINISTRADOR"}]):
            for override in ({"duracion_s": 121}, {"pulso_ms": 501}, {"comandos": [80, 80]}, {"comandos": ["80"]}):
                response = self.client.post("/admin/unidades/7/invitados", headers=self.headers,
                    json={"habilitada": True, "duracion_s": 15, "pulso_ms": 100, "comandos": [80], **override})
                self.assertEqual(response.status_code, 422)

    def test_guest_cannot_choose_vehicle_in_movement(self):
        response = self.client.post("/invitados/movimientos", headers=self.headers,
                                    json={"id_comando": 80, "id_vehiculo": 1})
        self.assertEqual(response.status_code, 422)

    def test_legacy_mode_does_not_enable_guest_reservations(self):
        with patch.dict(os.environ, {"IOT_AUTH_MODE": "legacy"}):
            response = self.client.post("/invitados/sesiones", json={"id_vehiculo": 7})
        self.assertEqual(response.status_code, 503)

    def test_second_socket_cannot_close_first_trial(self):
        with patch.object(invitados.guest_service, "context", return_value=CONTEXT), patch.object(
            invitados.guest_service, "sockets", {10},
        ), patch.object(invitados.guest_service, "close", new_callable=AsyncMock) as close:
            with self.client.websocket_connect("/ws/invitados") as socket:
                socket.send_json({"tipo": "autenticar", "token": "x" * 43})
                with self.assertRaises(WebSocketDisconnect) as result:
                    socket.receive_json()
        self.assertEqual(result.exception.code, 1008)
        close.assert_not_awaited()


class GuestLifecycleTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.service = GuestService()
        self.lock = patch.object(demo_service, "bloqueo", asyncio.Lock())
        self.lock.start()
        self.addCleanup(self.lock.stop)

    async def test_failed_stop_keeps_reservation_and_never_calls_release(self):
        self.service.db = AsyncMock(side_effect=[[{"reserva_pendiente": 1}], []])
        self.service.stop_unlocked = AsyncMock(side_effect=HTTPException(503, "STOP pendiente"))
        with self.assertRaises(HTTPException):
            await self.service.close(10, "EXPIRADA")
        self.assertEqual([call.args[0] for call in self.service.db.await_args_list],
                         ["sp_invitado_sesion_id", "sp_invitado_cerrar"])

    async def test_completed_old_session_does_not_stop_a_new_trial(self):
        self.service.db = AsyncMock(return_value=[{"reserva_pendiente": 0}])
        self.service.stop_unlocked = AsyncMock()
        await self.service.close(10, "DESCONECTADA")
        self.service.stop_unlocked.assert_not_awaited()

    async def test_successful_close_stops_before_release(self):
        order = []
        async def db(name, params=(), **kwargs):
            order.append(name)
            return [{"reserva_pendiente": 1}] if name == "sp_invitado_sesion_id" else []
        async def stop(session):
            order.append("STOP")
        self.service.db, self.service.stop_unlocked = db, stop
        await self.service.close(10, "EXPIRADA")
        self.assertEqual(order, ["sp_invitado_sesion_id", "sp_invitado_cerrar", "STOP", "sp_invitado_liberar"])

    async def test_movement_requires_live_guest_socket(self):
        self.service.context = Mock(return_value=CONTEXT)
        with self.assertRaises(HTTPException) as result:
            await self.service.move("x" * 43, 80)
        self.assertEqual(result.exception.status_code, 409)

    async def test_forbidden_command_never_reaches_writer(self):
        self.service.context = Mock(return_value=CONTEXT)
        self.service.sockets.add(10)
        self.service.db = AsyncMock(return_value=[STOP])
        with self.assertRaises(HTTPException) as result:
            await self.service.move("x" * 43, 81)
        self.assertEqual(result.exception.status_code, 403)
        self.assertEqual(self.service.db.await_args.args[0], "sp_invitado_comandos")

    async def test_stop_interrupts_pulse_without_waiting_for_a_new_command(self):
        self.service.context = Mock(return_value=CONTEXT)
        self.service.sockets.add(10)
        self.service.db = AsyncMock(return_value=[STOP])
        interrupt, done = asyncio.Event(), asyncio.Event()
        done.set()
        self.service.interrupts[10] = (interrupt, done)
        result = await self.service.move("x" * 43, 80)
        self.assertTrue(interrupt.is_set())
        self.assertTrue(result["parada_solicitada"])

    async def test_creation_rate_limit(self):
        for _ in range(10):
            self.service.rate_limit("local-client")
        with self.assertRaises(HTTPException) as result:
            self.service.rate_limit("local-client")
        self.assertEqual(result.exception.status_code, 429)

    async def test_token_is_stored_as_hash(self):
        self.service.ready = True
        self.service.db = AsyncMock(return_value=[{"id_sesion_invitado": 10}])
        self.service.stop_unlocked = AsyncMock()
        token = await self.service.reserve(7, "local-client")
        parameters = self.service.db.await_args.args[1]
        self.assertEqual(parameters, (7, session_security.token_hash(token)))
        self.assertNotEqual(parameters[1], token)

    async def test_http_cancellation_waits_for_sql_then_stop(self):
        self.service.context = Mock(return_value=CONTEXT)
        self.service.sockets.add(10)
        entered, finish_sql = asyncio.Event(), asyncio.Event()
        command = {**STOP, "id_comando": 81, "nombre": "ADELANTE"}
        order = []
        async def db(name, params=(), **kwargs):
            if name == "sp_invitado_comandos":
                return [command]
            entered.set()
            await finish_sql.wait()
            order.append("SQL")
            return [{"id_vehiculo": 7, "id_comando": 81, "comando": "ADELANTE", "codigo": 1, "pulso_ms": 0}]
        async def stop(session):
            order.append("STOP")
        self.service.db = db
        self.service.publish = AsyncMock()
        self.service.stop_unlocked = stop
        request = asyncio.create_task(self.service.move("x" * 43, 81))
        await asyncio.wait_for(entered.wait(), timeout=1)
        request.cancel()
        await asyncio.sleep(0)
        self.assertNotIn("STOP", order)
        finish_sql.set()
        with self.assertRaises(asyncio.CancelledError):
            await request
        self.assertEqual(order, ["SQL", "STOP"])
        self.assertFalse(self.service.interrupts)


if __name__ == "__main__":
    unittest.main()
