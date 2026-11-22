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

    def test_operational_permission_is_a_separate_query(self):
        def query(name,args):
            return [{'id_permiso':1}] if name=='sp_soporte_acceso' else []
        with patch('app.resource_security.service.ejecutar_consulta',side_effect=query):
            check_unit_access(self.admin,self.unit,diagnostic=True)
            with self.assertRaises(HTTPException):
                check_unit_access(self.admin,self.unit,operational=True)

    def test_operational_permission_does_not_grant_generic_access(self):
        with patch('app.resource_security.service.ejecutar_consulta',return_value=[{'id_permiso':1}]):
            check_unit_access(self.admin,self.unit,operational=True)
            with self.assertRaises(HTTPException):
                check_unit_access(self.admin,self.unit)

    def test_default_consent_keeps_diagnostic_scope(self):
        from app.routers.soporte import Consent,grant
        with patch('app.routers.soporte.owner'),patch('app.routers.soporte.write',return_value=[{'id_permiso':7}]) as write:
            result=grant(Consent(id_administrador=4,minutos=1),1,{'id_usuario':5})
            self.assertEqual(result['alcance'],'MONITOREO')
            self.assertEqual(write.call_args.args[0],'sp_soporte_conceder')

    def test_operational_consent_requires_explicit_flag(self):
        from app.routers.soporte import Consent,grant
        with patch('app.routers.soporte.owner'),patch('app.routers.soporte.write',return_value=[{'id_permiso':7}]) as write:
            result=grant(Consent(id_administrador=4,minutos=1,operativo=True),1,{'id_usuario':5})
            self.assertEqual(result['alcance'],'OPERATIVO')
            self.assertEqual(write.call_args.args[0],'sp_soporte_conceder_operativo')
