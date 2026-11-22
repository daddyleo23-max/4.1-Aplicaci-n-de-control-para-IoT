import asyncio
from contextlib import closing
from pathlib import Path
import sqlite3
import unittest
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pymysql

from app import session_security
from app.routers import administracion, catalogo


class CatalogTests(unittest.TestCase):
    def setUp(self):
        app = FastAPI()
        app.include_router(administracion.router)
        app.include_router(catalogo.router)
        self.client = TestClient(app)
        self.headers = {"Authorization": "Bearer " + "x" * 43}

    def test_anonymous_read_uses_only_public_response_fields(self):
        row = {"id_modelo": 3, "nombre": "Montacargas", "descripcion": "RC",
               "unidades_exhibicion": 1, "correo": "private@example.invalid", "id_propietario": 5}
        with patch.object(catalogo.service, "ejecutar_consulta", side_effect=[[row], [{"nombre":"DETENER","descripcion":"Parada","codigo":13,"id_propietario":5}]]) as query:
            response = self.client.get("/catalogo?limite=10&offset=20")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(set(response.json()["modelos"][0]), {
            "id_modelo", "nombre", "descripcion", "unidades_exhibicion", "capacidades",
        })
        self.assertEqual(query.call_args_list[0].args, ("sp_catalogo_modelos", (10, 20)))
        self.assertEqual(response.json()["modelos"][0]["capacidades"], [{"nombre":"DETENER","descripcion":"Parada","codigo":13}])

    def test_empty_catalog_is_not_a_connection_error(self):
        with patch.object(catalogo.service, "ejecutar_consulta", return_value=[]):
            response = self.client.get("/catalogo")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["modelos"], [])

    def test_pagination_rejects_invalid_values(self):
        for path in ("/catalogo?limite=101", "/catalogo?offset=-1", "/catalogo?limite=0"):
            self.assertEqual(self.client.get(path).status_code, 422)

    def test_database_error_is_sanitized(self):
        with patch.object(catalogo.service, "ejecutar_consulta",
                          side_effect=pymysql.OperationalError(2003, "private host")):
            response = self.client.get("/catalogo")
        self.assertEqual(response.status_code, 503)
        self.assertNotIn("private host", response.text)

    def test_publication_requires_authentication(self):
        self.assertEqual(self.client.post("/admin/modelos/3/publicacion", json={"publico": True}).status_code, 401)

    def test_buyer_cannot_publish_or_change_exhibition(self):
        with patch.object(session_security.service, "ejecutar_consulta",
                          return_value=[{"id_usuario": 5, "rol": "USUARIO"}]):
            for path, body in (("/admin/modelos/3/publicacion", {"publico": True}),
                               ("/admin/unidades/1/exhibicion", {"habilitada": True})):
                self.assertEqual(self.client.post(path, headers=self.headers, json=body).status_code, 403)

    def test_publication_actor_is_taken_from_session(self):
        with patch.object(session_security.service, "ejecutar_consulta",
                          return_value=[{"id_usuario": 4, "rol": "ADMINISTRADOR"}]), patch.object(
            administracion.service, "ejecutar_consulta_transaccional", return_value=[{"id_modelo": 3}],
        ) as query:
            response = self.client.post("/admin/modelos/3/publicacion", headers=self.headers, json={"publico": True})
        self.assertEqual(response.status_code, 200)
        query.assert_called_once_with("sp_admin_publicar_modelo", (4, 3, True))

    def test_assigned_exhibition_guard_becomes_conflict(self):
        with patch.object(session_security.service, "ejecutar_consulta",
                          return_value=[{"id_usuario": 4, "rol": "ADMINISTRADOR"}]), patch.object(
            administracion.demo_service, "bloqueo", asyncio.Lock(),
        ), patch.object(administracion.service, "ejecutar_consulta_transaccional",
                        side_effect=pymysql.OperationalError(1644, "Una unidad asignada no puede destinarse a exhibicion")):
            response = self.client.post("/admin/unidades/1/exhibicion", headers=self.headers, json={"habilitada": True})
        self.assertEqual(response.status_code, 409)

    def test_publication_rejects_unknown_fields(self):
        with patch.object(session_security.service, "ejecutar_consulta",
                          return_value=[{"id_usuario": 4, "rol": "ADMINISTRADOR"}]):
            response = self.client.post("/admin/modelos/3/publicacion", headers=self.headers,
                                        json={"publico": True, "id_actor": 99})
        self.assertEqual(response.status_code, 422)


class CatalogQueryPrivacyTests(unittest.TestCase):
    def test_query_excludes_private_models_and_counts_only_unassigned_exhibition(self):
        # Ejecuta el SELECT de la migración en SQLite con datos desechables.
        # Esto comprueba sus filtros; la instalación y los SP se prueban en MySQL/RDS.
        sql = (Path(__file__).resolve().parents[2] / "sql/migrations/010_catalogo_publico.up.sql").read_text()
        query = sql.split("CREATE PROCEDURE sp_catalogo_modelos", 1)[1].split("BEGIN", 1)[1].split("END$$", 1)[0]
        query = query.replace("p_limite", ":limite").replace("p_offset", ":offset").strip()
        with closing(sqlite3.connect(":memory:")) as db:
            db.executescript('''
                CREATE TABLE modelos(id_modelo INTEGER,nombre TEXT,descripcion TEXT,activo INTEGER,publico INTEGER);
                CREATE TABLE vehiculos(id_vehiculo INTEGER,id_modelo INTEGER,activo INTEGER,estado_comercial TEXT);
                CREATE TABLE asignaciones(id_vehiculo INTEGER,fin_utc TEXT);
                INSERT INTO modelos VALUES(1,'Publicado','RC',1,1),(2,'Privado','',1,0),(3,'Inactivo','',0,1);
                INSERT INTO vehiculos VALUES(1,1,1,'EXHIBICION'),(2,1,1,'ASIGNADO'),(3,1,0,'EXHIBICION'),
                    (4,1,1,'EXHIBICION'),(5,1,1,'DISPONIBLE'),(6,2,1,'EXHIBICION'),(7,1,1,'EXHIBICION');
                INSERT INTO asignaciones VALUES(4,NULL),(7,'2026-01-01');
            ''')
            rows = db.execute(query, {"limite": 20, "offset": 0}).fetchall()
        self.assertEqual(rows, [(1, "Publicado", "RC", 2)])


if __name__ == "__main__":
    unittest.main()
