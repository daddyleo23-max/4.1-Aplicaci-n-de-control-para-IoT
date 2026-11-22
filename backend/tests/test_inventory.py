import asyncio
import unittest
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pymysql

from app import session_security
from app.routers import administracion


class InventoryTests(unittest.TestCase):
    def setUp(self):
        app = FastAPI()
        app.include_router(administracion.router)
        self.client = TestClient(app)
        self.headers = {"Authorization": "Bearer " + "x" * 43}
        self.body = {"nombre": "Unidad nueva", "id_modelo": 3,
                     "identificador_unidad": "QA-001", "descripcion": "Inventario",
                     "microcontrolador": "ESP32"}
        self.auth = patch.object(session_security.service, "ejecutar_consulta",
                                 return_value=[{"id_usuario": 4, "rol": "ADMINISTRADOR"}])
        self.auth.start()
        self.addCleanup(self.auth.stop)
        # El singleton de ejecución usa un bloqueo nuevo por prueba/event loop.
        self.lock = patch.object(administracion.demo_service, "bloqueo", asyncio.Lock())
        self.lock.start()
        self.addCleanup(self.lock.stop)

    def test_create_uses_authenticated_actor_and_returns_id(self):
        with patch.object(administracion.service, "ejecutar_consulta_transaccional",
                          return_value=[{"id_vehiculo": 9}]) as call:
            response = self.client.post("/admin/unidades", headers=self.headers, json=self.body)
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["id_vehiculo"], 9)
        call.assert_called_once_with("sp_admin_crear_unidad", (
            4, "Unidad nueva", 3, "QA-001", "Inventario", "ESP32",
        ))

    def test_buyer_cannot_create_or_edit(self):
        with patch.object(session_security.service, "ejecutar_consulta",
                          return_value=[{"id_usuario": 5, "rol": "USUARIO"}]):
            for path, body in (("/admin/unidades", self.body),
                               ("/admin/unidades/1/actualizar", {**self.body, "activo": False})):
                response = self.client.post(path, headers=self.headers, json=body)
                self.assertEqual(response.status_code, 403)

    def test_requires_login(self):
        response = self.client.post("/admin/unidades", json=self.body)
        self.assertEqual(response.status_code, 401)

    def test_rejects_unknown_fields_and_invalid_identifiers(self):
        for changed in ({"id_actor": 99}, {"id_modelo": 0},
                        {"identificador_unidad": "  "}, {"nombre": "x" * 81}):
            response = self.client.post("/admin/unidades", headers=self.headers,
                                        json={**self.body, **changed})
            self.assertEqual(response.status_code, 422)

    def test_duplicate_identifier_returns_conflict(self):
        with patch.object(administracion.service, "ejecutar_consulta_transaccional",
                          side_effect=pymysql.IntegrityError(1062, "Duplicate")):
            response = self.client.post("/admin/unidades", headers=self.headers, json=self.body)
        self.assertEqual(response.status_code, 409)

    def test_deactivation_is_a_full_document_update(self):
        with patch.object(administracion.service, "ejecutar_consulta_transaccional",
                          return_value=[{"id_vehiculo": 9}]) as call:
            response = self.client.post("/admin/unidades/9/actualizar", headers=self.headers,
                                        json={**self.body, "activo": False})
        self.assertEqual(response.status_code, 200)
        call.assert_called_once_with("sp_admin_actualizar_unidad", (
            4, 9, "Unidad nueva", 3, "QA-001", "Inventario", "ESP32", False,
        ))

    def test_assigned_unit_guard_becomes_conflict(self):
        with patch.object(administracion.service, "ejecutar_consulta_transaccional",
                          side_effect=pymysql.OperationalError(1644, "Unidad asignada")):
            response = self.client.post("/admin/unidades/9/actualizar", headers=self.headers,
                                        json={**self.body, "activo": False})
        self.assertEqual(response.status_code, 409)

    def test_running_demo_blocks_update_before_database_call(self):
        class RunningTask:
            def done(self):
                return False
        with patch.dict(administracion.demo_service.tareas, {9: RunningTask()}), patch.object(
            administracion.service, "ejecutar_consulta_transaccional",
        ) as call:
            response = self.client.post("/admin/unidades/9/actualizar", headers=self.headers,
                                        json={**self.body, "activo": False})
        self.assertEqual(response.status_code, 409)
        call.assert_not_called()

    def test_old_configuration_cannot_bypass_new_guards(self):
        response = self.client.post("/admin/unidades/9/configurar", headers=self.headers,
                                    json={"id_modelo": 3, "identificador_unidad": "QA-001"})
        self.assertEqual(response.status_code, 409)


if __name__ == "__main__":
    unittest.main()
