import unittest
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pymysql

from app import session_security
from app.routers import administracion


class AdminTests(unittest.TestCase):
    def setUp(self):
        app = FastAPI()
        app.include_router(administracion.router)
        self.client = TestClient(app)
        self.headers = {"Authorization": "Bearer " + "x" * 43}
        self.session = {"id_usuario": 4, "rol": "ADMINISTRADOR"}

    def test_missing_session_is_401(self):
        self.assertEqual(self.client.get("/admin/resumen").status_code, 401)

    def test_buyer_is_403(self):
        with patch.object(session_security.service, "ejecutar_consulta",
                          return_value=[{"id_usuario": 5, "rol": "USUARIO"}]):
            response = self.client.get("/admin/resumen", headers=self.headers)
        self.assertEqual(response.status_code, 403)

    def test_admin_summary_queries_real_repository(self):
        with patch.object(session_security.service, "ejecutar_consulta", return_value=[self.session]), patch.object(
            administracion.service, "ejecutar_consulta", return_value=[{"modelos_activos": 3}],
        ) as query:
            response = self.client.get("/admin/resumen", headers=self.headers)
        self.assertEqual(response.json()["modelos_activos"], 3)
        self.assertEqual(response.json()["unidades_prueba_libres"], 0)
        self.assertFalse(response.json()["pruebas_habilitadas"])
        query.assert_called_once_with("sp_admin_resumen")

    def test_duplicate_model_returns_conflict(self):
        with patch.object(session_security.service, "ejecutar_consulta", return_value=[self.session]), patch.object(
            administracion.service, "ejecutar_consulta_transaccional",
            side_effect=pymysql.IntegrityError(1062, "Duplicate"),
        ):
            response = self.client.post("/admin/modelos", headers=self.headers,
                                        json={"nombre": "Montacargas"})
        self.assertEqual(response.status_code, 409)

    def test_client_password_is_hashed_and_actor_comes_from_session(self):
        with patch.object(session_security.service, "ejecutar_consulta", return_value=[self.session]), patch.object(
            administracion.service, "ejecutar_consulta_transaccional",
            return_value=[{"id_usuario": 5}],
        ) as create:
            response = self.client.post("/admin/clientes", headers=self.headers, json={
                "nombre": "Comprador", "correo": "Buyer@example.invalid",
                "password": "Contraseña de prueba",
            })
        self.assertEqual(response.status_code, 201)
        parameters = create.call_args.args[1]
        self.assertEqual(parameters[0], 4)
        self.assertEqual(parameters[2], "buyer@example.invalid")
        self.assertTrue(parameters[3].startswith("scrypt$"))
        self.assertNotIn("password", response.json())

    def test_pagination_limit_validated(self):
        with patch.object(session_security.service, "ejecutar_consulta", return_value=[self.session]):
            response = self.client.get("/admin/unidades?limite=1000", headers=self.headers)
        self.assertEqual(response.status_code, 422)

    def test_buyer_cannot_read_audit(self):
        with patch.object(session_security.service, "ejecutar_consulta",
                          return_value=[{"id_usuario": 5, "rol": "USUARIO"}]):
            response = self.client.get("/admin/auditoria", headers=self.headers)
        self.assertEqual(response.status_code, 403)

    def test_update_client_has_server_actor_and_normalized_email(self):
        with patch.object(session_security.service, "ejecutar_consulta", return_value=[self.session]), patch.object(
            administracion.service, "ejecutar_consulta_transaccional",
            return_value=[{"id_usuario": 5}],
        ) as update:
            response = self.client.post("/admin/clientes/5/actualizar", headers=self.headers, json={
                "nombre": " Comprador ", "correo": "BUYER@example.invalid", "activo": False,
            })
        self.assertEqual(response.status_code, 200)
        update.assert_called_once_with("sp_admin_actualizar_cliente",
                                      (4, 5, "Comprador", "buyer@example.invalid", False))

    def test_model_update_requires_active_flag(self):
        with patch.object(session_security.service, "ejecutar_consulta", return_value=[self.session]):
            response = self.client.post("/admin/modelos/3/actualizar",
                                        headers=self.headers, json={"nombre": "Montacargas"})
        self.assertEqual(response.status_code, 422)
