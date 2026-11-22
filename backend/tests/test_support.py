import unittest
from unittest.mock import patch
from fastapi import HTTPException
from app.resource_security import check_unit_access
from app.routers.soporte import owner


class SupportTests(unittest.TestCase):
    unit = {'id_vehiculo': 1, 'id_propietario': 5, 'activo': 1}
    admin = {'rol': 'ADMINISTRADOR', 'id_usuario': 4}

    def test_consent_only_allows_diagnostics(self):
        with patch('app.resource_security.service.ejecutar_consulta', return_value=[{'id_permiso': 1}]):
            check_unit_access(self.admin, self.unit, diagnostic=True)
            with self.assertRaises(HTTPException) as error:
                check_unit_access(self.admin, self.unit)
            self.assertEqual(error.exception.status_code, 403)

    def test_no_consent_denies_diagnostics(self):
        with patch('app.resource_security.service.ejecutar_consulta', return_value=[]):
            with self.assertRaises(HTTPException):
                check_unit_access(self.admin, self.unit, diagnostic=True)

    def test_other_buyer_cannot_use_support(self):
        with patch('app.resource_security.service.ejecutar_consulta') as query:
            with self.assertRaises(HTTPException):
                check_unit_access({'rol': 'USUARIO', 'id_usuario': 6}, self.unit, diagnostic=True)
            query.assert_not_called()

    def test_inactive_unit_denies_support(self):
        with patch('app.resource_security.service.ejecutar_consulta') as query:
            with self.assertRaises(HTTPException):
                check_unit_access(self.admin, {**self.unit, 'activo': 0}, diagnostic=True)
            query.assert_not_called()

    def test_only_owner_can_grant(self):
        with patch('app.routers.soporte.resource_context', return_value=self.unit):
            owner({'rol': 'USUARIO', 'id_usuario': 5}, 1)
            for actor in (self.admin, {'rol': 'USUARIO', 'id_usuario': 6}):
                with self.assertRaises(HTTPException):
                    owner(actor, 1)
