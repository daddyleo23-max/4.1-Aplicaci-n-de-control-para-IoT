import unittest
from unittest.mock import patch
from fastapi import FastAPI
from fastapi.testclient import TestClient
from app import session_security
from app.routers import soporte


class SupportListTests(unittest.TestCase):
    def setUp(self):
        app=FastAPI();app.include_router(soporte.router)
        self.client=TestClient(app)
        self.headers={'Authorization':'Bearer '+'x'*43}
    def identity(self,role):
        return patch.object(session_security.service,'ejecutar_consulta',return_value=[{'id_usuario':4,'rol':role,'id_sesion':10}])
    def test_lists_require_session(self):
        for path in ('/soporte/administradores','/admin/soporte'):
            self.assertEqual(self.client.get(path).status_code,401)
    def test_buyer_sees_administrator_choices(self):
        with self.identity('USUARIO'),patch.object(soporte.service,'ejecutar_consulta',return_value=[{'id_administrador':8,'nombre':'Empresa'}]):
            response=self.client.get('/soporte/administradores',headers=self.headers)
        self.assertEqual(response.status_code,200)
        self.assertEqual(response.headers['Cache-Control'],'no-store')
        self.assertEqual(response.json()['administradores'][0]['id_administrador'],8)
    def test_buyer_cannot_list_admin_support(self):
        with self.identity('USUARIO'):
            self.assertEqual(self.client.get('/admin/soporte',headers=self.headers).status_code,403)
    def test_admin_cannot_supply_another_admin_id(self):
        with self.identity('ADMINISTRADOR'),patch.object(soporte.service,'ejecutar_consulta',return_value=[]) as query:
            response=self.client.get('/admin/soporte?id_administrador=999',headers=self.headers)
        self.assertEqual(response.status_code,200)
        query.assert_called_once_with('sp_soporte_mis_permisos',(4,))
        self.assertEqual(response.headers['Cache-Control'],'no-store')
