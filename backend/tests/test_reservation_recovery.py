from pathlib import Path
import sys
import unittest
from unittest.mock import Mock

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))
import recuperar_reservas_011 as recovery
from migrar_copia_rds import check_trigger_configuration
sys.path.pop(0)


class ReservationRecoveryTests(unittest.TestCase):
    def setUp(self):
        self.sql = (Path(__file__).resolve().parents[2] / "sql/migrations/011_reservas_invitados.up.sql").read_text()
        self.procedures, self.triggers = recovery.definitions(self.sql)

    def cursor(self, *, versions=None, stored_procedures=None, stored_triggers=None, counts=None):
        cursor = Mock()
        cursor.fetchall.side_effect = [
            [{"table": name} for name in recovery.TABLES],
            [{"version": name} for name in (versions or recovery.PREVIOUS)],
            [{"ROUTINE_NAME": name, "ROUTINE_DEFINITION": body}
             for name, body in (stored_procedures or self.procedures).items()],
            stored_triggers or [],
        ]
        cursor.fetchone.side_effect = ([{"n": n} for n in (counts or [0, 0, 0, 0])]
                                     + [{"binary_logging": 1, "trust_creators": 0}])
        return cursor

    def test_source_contains_only_five_trigger_statements_for_recovery(self):
        self.assertEqual(len(self.procedures), 7)
        self.assertEqual(len(self.triggers), 5)
        self.assertTrue(all(item["statement"].startswith("CREATE TRIGGER") for item in self.triggers.values()))
        self.assertTrue(all("CREATE TABLE" not in item["statement"] for item in self.triggers.values()))

    def test_normalization_accepts_removed_comments(self):
        self.assertEqual(recovery.normalize("BEGIN\n -- comentario\n SELECT 1;\nEND"),
                         recovery.normalize("BEGIN SELECT 1; END"))
        self.assertNotEqual(recovery.normalize("BEGIN SELECT 1; END"), recovery.normalize("BEGIN SELECT 2; END"))

    def test_partial_state_detects_all_pending_triggers(self):
        state = recovery.inspect(self.cursor(), "copy", self.procedures, self.triggers)
        self.assertEqual(state["triggers_pendientes"], sorted(self.triggers))
        self.assertFalse(state["version_registrada"])

    def test_changed_procedure_is_not_silently_replaced(self):
        changed = {**self.procedures, "sp_invitado_liberar": "BEGIN SELECT 99; END"}
        with self.assertRaisesRegex(RuntimeError, "rutinas existentes"):
            recovery.inspect(self.cursor(stored_procedures=changed), "copy", self.procedures, self.triggers)

    def test_reservation_data_prevents_recovery(self):
        with self.assertRaisesRegex(RuntimeError, "contiene datos"):
            recovery.inspect(self.cursor(counts=[1, 0, 0, 0]), "copy", self.procedures, self.triggers)

    def test_completed_migration_cannot_be_missing_guards(self):
        with self.assertRaisesRegex(RuntimeError, "faltan triggers"):
            recovery.inspect(self.cursor(versions=recovery.PREVIOUS + [recovery.VERSION]),
                             "copy", self.procedures, self.triggers)

    def test_unrelated_trigger_is_rejected(self):
        with self.assertRaisesRegex(RuntimeError, "adicionales"):
            recovery.inspect(self.cursor(stored_triggers=[{"TRIGGER_NAME": "unexpected"}]),
                             "copy", self.procedures, self.triggers)

    def test_preflight_stops_before_ddl_with_rds_restriction(self):
        cursor = Mock()
        cursor.fetchone.return_value = {"binary_logging": 1, "trust_creators": 0}
        with self.assertRaisesRegex(SystemExit, "No se ejecutó el SQL"):
            check_trigger_configuration(cursor, self.sql)
        self.assertEqual(cursor.execute.call_count, 1)
        self.assertTrue(cursor.execute.call_args.args[0].startswith("SELECT"))

    def test_preflight_accepts_enabled_parameter(self):
        cursor = Mock()
        cursor.fetchone.return_value = {"binary_logging": 1, "trust_creators": 1}
        check_trigger_configuration(cursor, self.sql)

    def test_non_trigger_migration_does_not_query_parameter(self):
        cursor = Mock()
        check_trigger_configuration(cursor, "CREATE TABLE example(id INT);")
        cursor.execute.assert_not_called()


if __name__ == "__main__":
    unittest.main()
