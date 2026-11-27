import unittest
from types import SimpleNamespace
from unittest.mock import patch
from puente_usb import read_keyring, save_keyring

class KeyringTests(unittest.TestCase):
    def setUp(self): self.args=SimpleNamespace(api='https://example.test/',unidad=1)
    @patch('puente_usb.shutil.which',return_value='/usr/bin/secret-tool')
    @patch('puente_usb.subprocess.run')
    def test_store_uses_stdin_not_command_arguments(self,run,which):
        run.return_value.returncode=0
        save_keyring(self.args,'owner@example.test','test-only-secret')
        self.assertNotIn('test-only-secret',run.call_args.args[0])
        self.assertEqual(run.call_args.kwargs['input'],'test-only-secret')
        self.assertIn('https://example.test',run.call_args.args[0])
    @patch('puente_usb.shutil.which',return_value=None)
    @patch('puente_usb.subprocess.run')
    def test_missing_keyring_falls_back_without_running_command(self,run,which):
        self.assertIsNone(read_keyring(self.args,'owner@example.test'));run.assert_not_called()
    @patch('puente_usb.shutil.which',return_value='/usr/bin/secret-tool')
    @patch('puente_usb.subprocess.run')
    def test_lookup_returns_value_only_on_success(self,run,which):
        run.return_value=SimpleNamespace(returncode=0,stdout='test-secret\n')
        self.assertEqual(read_keyring(self.args,'owner@example.test'),'test-secret')
        run.return_value=SimpleNamespace(returncode=1,stdout='error')
        self.assertIsNone(read_keyring(self.args,'owner@example.test'))
