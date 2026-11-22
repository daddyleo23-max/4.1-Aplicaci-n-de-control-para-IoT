"""Recovery must stop on unknown/failed states and preserve FK/DDL ordering."""
from pathlib import Path
import sys
import unittest
from unittest.mock import Mock, patch
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'tools'))
import recuperar_control_019 as recovery


class Recovery019Tests(unittest.TestCase):
    def setUp(self):
        self.cursor=Mock()
        self.initial={'version_registrada':False,'id_vehiculo_nullable':True,
                      'fk_control_unidad_presente':True,'filas_sin_unidad':0,'rutinas_pendientes':[]}
        self.valid={**self.initial,'id_vehiculo_nullable':False}
        self.registered={**self.valid,'version_registrada':True}
        self.data={'usuarios':{'filas':2,'sha256':'inmutable'}}

    def run_repair(self, state=None):
        with patch.object(recovery,'inspect',side_effect=[dict(state or self.initial),self.valid,self.registered]),patch.object(recovery,'all_data',return_value=self.data):
            report={'acciones':[]}
            recovery.recover(self.cursor,'iot_prueba_20261122_000019_000001',{}, {},report)
        return report

    def test_fk_dropped_before_modify_and_recreated_before_registration(self):
        report=self.run_repair()
        statements=[c.args[0] for c in self.cursor.execute.call_args_list]
        self.assertLess(statements.index('ALTER TABLE sesiones_control DROP FOREIGN KEY fk_control_unidad'), statements.index('ALTER TABLE sesiones_control MODIFY id_vehiculo INT NOT NULL'))
        self.assertTrue(statements[2].startswith('ALTER TABLE sesiones_control ADD CONSTRAINT'))
        self.assertTrue(statements[-1].startswith('INSERT INTO migraciones_iot'))
        self.assertTrue(report['estado_previo']['fk_control_unidad_presente'])
        self.assertTrue(report['datos_conservados'])

    def test_resume_after_fk_drop_does_not_drop_again(self):
        self.run_repair({**self.initial,'fk_control_unidad_presente':False})
        statements=[c.args[0] for c in self.cursor.execute.call_args_list]
        self.assertFalse(any('DROP FOREIGN KEY' in s for s in statements))
        self.assertIn('MODIFY id_vehiculo INT NOT NULL',statements[0])

    def test_data_change_prevents_version_registration(self):
        with patch.object(recovery,'inspect',side_effect=[dict(self.initial),self.valid]),patch.object(recovery,'all_data',side_effect=[self.data,{}]):
            with self.assertRaisesRegex(RuntimeError,'Cambios de datos'):
                recovery.recover(self.cursor,'copy',{}, {},{'acciones':[]})
        self.assertFalse(any(c.args[0].startswith('INSERT INTO migraciones_iot') for c in self.cursor.execute.call_args_list))

    def test_ddl_failure_stops_before_fk_recreation_and_version(self):
        def execute(statement,*args):
            if 'MODIFY id_vehiculo' in statement:raise RuntimeError('DDL failure')
        self.cursor.execute.side_effect=execute
        with patch.object(recovery,'inspect',return_value=dict(self.initial)),patch.object(recovery,'all_data',return_value=self.data):
            with self.assertRaisesRegex(RuntimeError,'DDL failure'):
                recovery.recover(self.cursor,'copy',{}, {},{'acciones':[]})
        statements=[c.args[0] for c in self.cursor.execute.call_args_list]
        self.assertEqual(len(statements),2)
        self.assertFalse(any('INSERT' in s or 'ADD CONSTRAINT' in s for s in statements))

    def test_registered_valid_state_has_no_writes(self):
        with patch.object(recovery,'inspect',return_value=self.registered),patch.object(recovery,'all_data',return_value=self.data):
            recovery.recover(self.cursor,'copy',{}, {},{'acciones':[]})
        self.cursor.execute.assert_not_called()

    def test_corrected_fresh_migration_adds_fk_after_nullability(self):
        text=(Path(__file__).resolve().parents[2]/'sql/migrations/019_control_empresa.up.sql').read_text()
        self.assertLess(text.index('MODIFY id_vehiculo INT NOT NULL'),text.index('ADD CONSTRAINT fk_control_unidad'))

    def test_sources_cover_seven_target_routines_and_unmodified_move_stop(self):
        _,old,target=recovery.load_sources()
        self.assertEqual(len(target),7)
        self.assertIn('sp_control_detener',old)
        self.assertIn('sp_control_mover',old)
        self.assertTrue(set(target)<=set(old))
