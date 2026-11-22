import unittest
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pymysql

from app import session_security
from app.routers import editor_demos


class DemoEditorTests(unittest.TestCase):
    def setUp(self):
        app = FastAPI()
        app.include_router(editor_demos.router)
        self.client = TestClient(app)
        self.headers = {"Authorization": "Bearer " + "x" * 43}
        self.session_patch = patch.object(
            session_security.service, "ejecutar_consulta",
            return_value=[{"id_usuario": 5, "rol": "USUARIO"}],
        )
        self.session_patch.start()
        self.addCleanup(self.session_patch.stop)
        self.data = {
            "id_vehiculo": 1, "nombre": "Demo propia",
            "pasos": [{"id_comando": 1, "duracion_ms": 1000, "pausa_ms": 100}],
        }

    def test_empty_sequence_rejected(self):
        self.data["pasos"] = []
        self.assertEqual(self.client.post("/mis-demos", headers=self.headers, json=self.data).status_code, 422)

    def test_total_time_limit(self):
        self.data["pasos"] *= 100
        self.data["pasos"][0]["duracion_ms"] = 10000
        self.assertEqual(self.client.post("/mis-demos", headers=self.headers, json=self.data).status_code, 422)

    def test_save_uses_authenticated_actor(self):
        with patch.object(editor_demos, "resource_context", return_value={
            "id_propietario": 5, "activo": 1,
        }), patch.object(editor_demos.service, "ejecutar_consulta_transaccional",
                          return_value=[{"id_demo": 3, "revision": 1}]) as save:
            response = self.client.post("/mis-demos", headers=self.headers, json=self.data)
        self.assertEqual(response.status_code, 201)
        self.assertEqual(save.call_args.args[1][0], 5)
        self.assertIsNone(save.call_args.args[1][1])

    def test_unowned_unit_rejected(self):
        with patch.object(editor_demos, "resource_context", return_value={
            "id_propietario": 6, "activo": 1,
        }):
            response = self.client.post("/mis-demos", headers=self.headers, json=self.data)
        self.assertEqual(response.status_code, 403)

    def test_hidden_demo_returns_404(self):
        with patch.object(editor_demos.service, "ejecutar_consulta", return_value=[]):
            response = self.client.get("/mis-demos/3", headers=self.headers)
        self.assertEqual(response.status_code, 404)

    def test_revision_conflict_is_409(self):
        self.data["revision"] = 1
        with patch.object(editor_demos, "resource_context", return_value={
            "id_propietario": 5, "activo": 1,
        }), patch.object(editor_demos.service, "ejecutar_consulta", return_value=[{"id_demo": 3, "tipo": "PRIVADA", "id_propietario": 5}]), patch.object(
            editor_demos.service, "ejecutar_consulta_transaccional",
            side_effect=pymysql.OperationalError(1644, "La demo cambió"),
        ):
            response = self.client.post("/mis-demos/3/guardar", headers=self.headers, json=self.data)
        self.assertEqual(response.status_code, 409)
