import os
import unittest
from unittest.mock import patch

from fastapi import APIRouter, Depends, FastAPI
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from app import resource_security, session_security
from app.routers import websocket


class ResourceAccessTests(unittest.TestCase):
    def setUp(self):
        self.mode = patch.dict(os.environ, {"IOT_AUTH_MODE": "sesiones"})
        self.mode.start()
        self.addCleanup(self.mode.stop)
        app = FastAPI()
        router = APIRouter(dependencies=[Depends(resource_security.authorize_resources)])

        @router.get("/vehiculos/{id_vehiculo}/estado")
        def state(id_vehiculo: int):
            return {"id_vehiculo": id_vehiculo}

        @router.get("/vehiculos/{id_vehiculo}")
        def vehicle(id_vehiculo: int):
            return {"id_vehiculo": id_vehiculo}

        @router.get("/demos/{id_demo}/movimientos")
        def steps(id_demo: int):
            return {"id_demo": id_demo}

        app.include_router(router)
        app.include_router(websocket.router)
        self.client = TestClient(app)
        self.headers = {"Authorization": "Bearer " + "x" * 43}
        self.unit = {"id_vehiculo": 1, "activo": 1, "id_propietario": 5,
                     "estado_comercial": "ASIGNADO"}
        self.context = patch.object(resource_security.service, "ejecutar_consulta",
                                    return_value=[self.unit])
        self.context.start()
        self.addCleanup(self.context.stop)

    def test_swagger_declares_bearer_for_protected_routes(self):
        schema = self.client.get("/openapi.json").json()
        security = schema["paths"]["/vehiculos/{id_vehiculo}/estado"]["get"]["security"]
        self.assertIn({"HTTPBearer": []}, security)

    def identity(self, user=5, role="USUARIO"):
        return patch.object(session_security.service, "ejecutar_consulta",
                            return_value=[{"id_usuario": user, "rol": role, "id_sesion": 1}])

    def test_api_key_alone_does_not_bypass_session(self):
        response = self.client.get("/vehiculos/1/estado", headers={"X-API-Key": "old"})
        self.assertEqual(response.status_code, 401)

    def test_owner_reads_state(self):
        with self.identity():
            response = self.client.get("/vehiculos/1/estado", headers=self.headers)
        self.assertEqual(response.status_code, 200)

    def test_other_buyer_cannot_read_state(self):
        with self.identity(6):
            response = self.client.get("/vehiculos/1/estado", headers=self.headers)
        self.assertEqual(response.status_code, 403)

    def test_admin_inventory_access_does_not_allow_operation(self):
        with self.identity(4, "ADMINISTRADOR"):
            self.assertEqual(self.client.get("/vehiculos/1", headers=self.headers).status_code, 200)
            self.assertEqual(self.client.get("/vehiculos/1/estado", headers=self.headers).status_code, 403)

    def test_demo_id_resolves_its_unit(self):
        with self.identity(6):
            response = self.client.get("/demos/1/movimientos", headers=self.headers)
        self.assertEqual(response.status_code, 403)
        resource_security.service.ejecutar_consulta.assert_called_with("sp_acceso_recurso", ("demo", 1))

    def test_other_buyer_websocket_closed_before_state(self):
        with self.identity(6):
            with self.client.websocket_connect("/ws/vehiculos/1") as socket:
                socket.send_json({"tipo": "autenticar", "token": "x" * 43})
                with self.assertRaises(WebSocketDisconnect) as rejected:
                    socket.receive_json()
        self.assertEqual(rejected.exception.code, 1008)

    def test_owner_websocket_receives_state(self):
        with self.identity(), patch.object(websocket.servicio, "ejecutar_consulta",
                                         side_effect=[[{"activo": 1}], [{"id_vehiculo": 1}]]):
            with self.client.websocket_connect("/ws/vehiculos/1") as socket:
                socket.send_json({"tipo": "autenticar", "token": "x" * 43})
                self.assertEqual(socket.receive_json()["tipo"], "estado_inicial")
