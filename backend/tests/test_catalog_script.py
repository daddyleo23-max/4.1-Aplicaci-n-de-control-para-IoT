"""Regresión del orden de limpieza del script HTTP, con estado controlado."""
from contextlib import redirect_stdout
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))
import probar_catalogo_http as script
sys.path.pop(0)


class CatalogScriptTests(unittest.TestCase):
    def setUp(self):
        self.model = None
        self.unit = None
        self.calls = []
        self.original = {"id_vehiculo": 1, "id_propietario": 5, "activo": 1,
                         "estado_comercial": "ASIGNADO", "id_modelo": 3}

    def request(self, method, path, body=None, token=None):
        self.calls.append((method, path))
        route = path.split("?", 1)[0]
        if route == "/auth/login":
            return 200, {"access_token": "test-token", "usuario": {"rol": "ADMINISTRADOR"}}
        if route == "/auth/logout":
            return 200, {}
        if route == "/admin/modelos" and method == "POST":
            self.model = {**body, "id_modelo": 8, "activo": 1, "publico": 0}
            return 201, {"id_modelo": 8}
        if route == "/admin/modelos" and method == "GET":
            return 200, {"modelos": [self.model]}
        if route == "/admin/unidades" and method == "POST":
            self.unit = {**body, "id_vehiculo": 6, "activo": 1,
                         "estado_comercial": "DISPONIBLE", "id_propietario": None}
            return 201, {"id_vehiculo": 6}
        if route == "/admin/unidades" and method == "GET":
            return 200, {"unidades": [dict(self.unit), dict(self.original)]}
        if route == "/admin/modelos/8/publicacion":
            if token is None:
                return 401, {}
            if body["publico"] and not self.model["activo"]:
                return 409, {}
            self.model["publico"] = int(body["publico"])
            return 200, {}
        if route == "/admin/unidades/1/exhibicion":
            return 409, {}
        if route == "/admin/unidades/6/exhibicion":
            if body["habilitada"] and not self.model["publico"]:
                return 409, {}
            self.unit["estado_comercial"] = "EXHIBICION" if body["habilitada"] else "DISPONIBLE"
            return 200, {}
        if route == "/admin/unidades/6/actualizar":
            if not self.model["activo"]:
                return 409, {"detail": "Modelo inexistente o inactivo"}
            self.unit.update(body)
            self.unit["estado_comercial"] = "INACTIVO"
            return 200, {}
        if route == "/admin/modelos/8/actualizar":
            if not body["activo"] and self.unit["activo"]:
                return 409, {}
            self.model.update(body)
            return 200, {}
        if route == "/catalogo":
            rows = []
            if self.model and self.model["publico"] and self.model["activo"]:
                rows = [{key: self.model[key] for key in ("id_modelo", "nombre", "descripcion")}]
                rows[0]["unidades_exhibicion"] = int(self.unit["estado_comercial"] == "EXHIBICION")
            return 200, {"modelos": rows}
        if route == "/admin/auditoria":
            return 200, {"eventos": [{"accion": "PUBLICAR_MODELO", "id_recurso": "8"},
                                     {"accion": "EXHIBICION_UNIDAD", "id_recurso": "6"}]}
        raise AssertionError((method, path))

    def test_successful_run_does_not_deactivate_unit_twice(self):
        with tempfile.TemporaryDirectory() as folder, patch.object(script, "request", self.request), patch(
            "builtins.input", return_value="admin@example.invalid",
        ), patch.object(script.getpass, "getpass", return_value="test-password"), patch.object(
            script.Path, "cwd", return_value=Path(folder),
        ), redirect_stdout(io.StringIO()):
            script.main()
            report = json.loads(next((Path(folder) / "respaldos_rds").glob("*.json")).read_text())
        self.assertEqual(self.calls.count(("POST", "/admin/unidades/6/actualizar")), 1)
        self.assertTrue(all(item["correcto"] for item in report["resultados"]))
        self.assertEqual(report["limpieza"], [])
        self.assertFalse(self.unit["activo"])
        self.assertFalse(self.model["activo"])
        self.assertEqual(self.model["publico"], 0)

    def verify_previous(self, active):
        self.model = {"id_modelo": 8, "nombre": "Catalogo HTTP prueba", "publico": 0, "activo": 0}
        self.unit = {"id_vehiculo": 6, "id_modelo": 8, "identificador_unidad": "CAT-prueba",
                     "activo": active, "estado_comercial": "DISPONIBLE" if active else "INACTIVO",
                     "id_propietario": None}
        with tempfile.TemporaryDirectory() as folder, patch.object(script, "request", self.request), patch(
            "builtins.input", return_value="admin@example.invalid",
        ), patch.object(script.getpass, "getpass", return_value="test-password"), redirect_stdout(io.StringIO()):
            report = Path(folder) / "previous.json"
            report.write_text(json.dumps({"destino": script.BASE, "id_modelo_prueba": 8, "id_unidad_prueba": 6}))
            script.verify_report(report)

    def test_verify_previous_report_does_not_modify_inventory(self):
        self.verify_previous(active=0)
        self.assertEqual([path for method, path in self.calls if method == "POST"], ["/auth/login", "/auth/logout"])

    def test_verify_detects_incomplete_state_without_modifying_it(self):
        with self.assertRaisesRegex(RuntimeError, "requieren revisión"):
            self.verify_previous(active=1)
        self.assertEqual([path for method, path in self.calls if method == "POST"], ["/auth/login", "/auth/logout"])


if __name__ == "__main__":
    unittest.main()
