import unittest
from unittest.mock import patch
from fastapi import HTTPException
from fastapi.testclient import TestClient
from fastapi import FastAPI
from app.login_limits import LoginLimiter
from app.routers import autenticacion


class LoginLimitTests(unittest.TestCase):
    def test_account_limit_applies_across_addresses_and_expires(self):
        now = [1.0]
        limiter = LoginLimiter(clock=lambda: now[0])
        for i in range(12):
            limiter.check(str(i), 'Cuenta@EXAMPLE.COM')
        with self.assertRaises(HTTPException) as error:
            limiter.check('new', 'cuenta@example.com')
        self.assertEqual(error.exception.status_code, 429)
        self.assertEqual(error.exception.headers['Retry-After'], '60')
        now[0] += 60
        limiter.check('new', 'cuenta@example.com')

    def test_ip_limit_applies_across_accounts(self):
        limiter = LoginLimiter()
        for i in range(30):
            limiter.check('one-address', str(i))
        with self.assertRaises(HTTPException):
            limiter.check('one-address', 'another')
        limiter.check('other-address', 'another')

    def test_storage_is_bounded_without_eviction_bypass(self):
        limiter = LoginLimiter(max_keys=3)
        limiter.check('one', 'a')
        limiter.check('one', 'b')
        with self.assertRaises(HTTPException):
            limiter.check('one', 'c')
        self.assertLessEqual(len(limiter.buckets), 3)

    def test_rejected_attempt_never_queries_database(self):
        app = FastAPI(); app.include_router(autenticacion.router)
        limiter = LoginLimiter()
        for _ in range(12):
            limiter.check('testclient', 'a@example.com')
        with patch('app.login_limits.login_limiter', limiter), patch.object(autenticacion.service, 'ejecutar_consulta') as query:
            response = TestClient(app).post('/auth/login', json={'correo':'a@example.com','password':'incorrecta'})
        self.assertEqual(response.status_code, 429)
        self.assertIn('Retry-After', response.headers)
        query.assert_not_called()
