import unittest
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pymysql

from app import session_security
from app.routers import administracion, cuenta


class OwnershipTests(unittest.TestCase):
    def setUp(self):
        app = FastAPI()
        app.include_router(administracion.router)
        app.include_router(cuenta.router)
        self.client = TestClient(app)
        self.headers = {"Authorization": "Bearer " + "x" * 43}

    def test_my_vehicles_uses_authenticated_user(self):
        with patch.object(session_security.service, "ejecutar_consulta",
                          return_value=[{"id_usuario": 8, "rol": "USUARIO"}]), patch.object(
            cuenta.service, "ejecutar_consulta", return_value=[],
        ) as query:
            response = self.client.get("/mis-vehiculos?id_usuario=99", headers=self.headers)
        self.assertEqual(response.status_code, 200)
        query.assert_called_once_with("sp_usuario_mis_vehiculos", (8,))

    def test_buyer_cannot_assign_unit(self):
        with patch.object(session_security.service, "ejecutar_consulta",
                          return_value=[{"id_usuario": 8, "rol": "USUARIO"}]):
            response = self.client.post("/admin/unidades/1/asignar", headers=self.headers,
                                        json={"id_usuario": 8})
        self.assertEqual(response.status_code, 403)

    def test_actor_id_comes_from_session(self):
        with patch.object(session_security.service, "ejecutar_consulta",
                          return_value=[{"id_usuario": 4, "rol": "ADMINISTRADOR"}]), patch.object(
            administracion.service, "ejecutar_consulta_transaccional",
            return_value=[{"id_vehiculo": 1, "id_propietario": 8}],
        ) as assign:
            response = self.client.post("/admin/unidades/1/asignar", headers=self.headers,
                                        json={"id_usuario": 8, "id_actor": 99})
        self.assertEqual(response.status_code, 200)
        assign.assert_called_once_with("sp_admin_asignar_unidad", (4, 1, 8))

    def test_sql_validation_becomes_conflict(self):
        with patch.object(session_security.service, "ejecutar_consulta",
                          return_value=[{"id_usuario": 4, "rol": "ADMINISTRADOR"}]), patch.object(
            administracion.service, "ejecutar_consulta_transaccional",
            side_effect=pymysql.OperationalError(1644, "Comprador inexistente o inactivo"),
        ):
            response = self.client.post("/admin/unidades/1/asignar", headers=self.headers,
                                        json={"id_usuario": 999})
        self.assertEqual(response.status_code, 409)
