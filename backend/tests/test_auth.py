import unittest
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.passwords import hash_password, verify_password
from app.routers import autenticacion
from app import session_security


class AuthenticationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.encoded = hash_password("Prueba temporal de autenticación")

    def setUp(self):
        application = FastAPI()
        application.include_router(autenticacion.router)
        self.client = TestClient(application)
        self.user = {
            "id_usuario": 1, "nombre": "Cuenta de prueba",
            "correo": "test@example.invalid", "rol": "USUARIO",
            "activo": 1, "password_hash": self.encoded,
        }

    def test_password_hashes_use_distinct_salts(self):
        self.assertNotEqual(self.encoded, hash_password("Prueba temporal de autenticación"))
        self.assertTrue(verify_password("Prueba temporal de autenticación", self.encoded))
        self.assertFalse(verify_password("Otra contraseña", self.encoded))
        self.assertFalse(verify_password("Cualquiera", "hash inválido"))

    def test_missing_session_rejected(self):
        self.assertEqual(self.client.get("/auth/me").status_code, 401)

    def test_invalid_credentials_rejected(self):
        with patch.object(autenticacion.service, "ejecutar_consulta", return_value=[self.user]):
            result = self.client.post("/auth/login", json={
                "correo": self.user["correo"], "password": "Incorrecta",
            })
        self.assertEqual(result.status_code, 401)

    def test_inactive_user_rejected(self):
        self.user["activo"] = 0
        with patch.object(autenticacion.service, "ejecutar_consulta", return_value=[self.user]):
            result = self.client.post("/auth/login", json={
                "correo": self.user["correo"], "password": "Prueba temporal de autenticación",
            })
        self.assertEqual(result.status_code, 401)

    def test_login_stores_hash_and_commits(self):
        with patch.object(autenticacion.service, "ejecutar_consulta", return_value=[self.user]), patch.object(
            autenticacion.service, "ejecutar_consulta_transaccional", return_value=[{"creadas": 1}],
        ) as create:
            result = self.client.post("/auth/login", json={
                "correo": self.user["correo"], "password": "Prueba temporal de autenticación",
            })
        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.headers["Cache-Control"], "no-store")
        payload = result.json()
        stored_hash = create.call_args.args[1][1]
        self.assertEqual(stored_hash, session_security.token_hash(payload["access_token"]))
        self.assertNotIn("password_hash", payload["usuario"])

    def test_revoked_or_expired_session_rejected(self):
        with patch.object(session_security.service, "ejecutar_consulta", return_value=[]):
            result = self.client.get("/auth/me", headers={"Authorization": "Bearer " + "x" * 43})
        self.assertEqual(result.status_code, 401)

    def test_logout_uses_authenticated_session(self):
        session = {key: self.user[key] for key in ("id_usuario", "nombre", "correo", "rol")}
        session["id_sesion"] = 7
        with patch.object(session_security.service, "ejecutar_consulta", return_value=[session]), patch.object(
            autenticacion.service, "ejecutar_transaccion",
        ) as revoke:
            result = self.client.post("/auth/logout", headers={"Authorization": "Bearer " + "x" * 43})
        self.assertEqual(result.status_code, 200)
        revoke.assert_called_once_with([("sp_auth_revocar_sesion", (7,))])


if __name__ == "__main__":
    unittest.main()
