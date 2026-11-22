from pathlib import Path
import sys,unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'tools'))
import gestionar_proxy_4_3 as proxy


class ProxyConfigurationTests(unittest.TestCase):
    def test_only_expected_directive_changes_with_crlf_and_bom(self):
        original=b'\xef\xbb\xbf# comment 127.0.0.1:8000\r\nexample.com {\r\n\treverse_proxy 127.0.0.1:8000 {\r\n header_up X-Test value\r\n }\r\n}\r\n'
        changed=proxy.change_text(original)
        self.assertEqual(changed,original.replace(b'\treverse_proxy 127.0.0.1:8000',b'\treverse_proxy 127.0.0.1:8002'))

    def test_comment_alone_does_not_authorize_a_change(self):
        with self.assertRaises(RuntimeError):proxy.change_text(b'# reverse_proxy 127.0.0.1:8000\n')

    def test_multiple_proxies_are_rejected(self):
        with self.assertRaises(RuntimeError):proxy.change_text(b'reverse_proxy 127.0.0.1:8000\nreverse_proxy 127.0.0.1:8000\n')

    def test_other_port_is_not_accepted(self):
        with self.assertRaises(RuntimeError):proxy.change_text(b'reverse_proxy 127.0.0.1:80001\n')

    def test_native_change_preserves_tls_and_does_not_mutate_original(self):
        data={'apps':{'tls':{'certificates':{'load_files':[{'certificate':'existing.pem','key':'existing.key'}]}},'http':{'servers':{'one':{'routes':[{'handle':[{'handler':'reverse_proxy','upstreams':[{'dial':proxy.OLD}]}]}]}}}}}
        old_hash=proxy.json_sha(data);changed=proxy.change_native(data)
        self.assertEqual(proxy.json_sha(data),old_hash)
        self.assertEqual(data['apps']['tls'],changed['apps']['tls'])
        self.assertEqual(changed['apps']['http']['servers']['one']['routes'][0]['handle'][0]['upstreams'][0]['dial'],proxy.NEW)

    def test_dial_outside_reverse_proxy_is_not_changed(self):
        with self.assertRaises(RuntimeError):proxy.change_native({'dial':proxy.OLD})

    def test_remote_admin_rejected(self):
        for address in ('example.com:2019','127.0.0.1:2019@evil.com:2019','127.0.0.1:2019/path'):
            with self.subTest(address=address),self.assertRaises(RuntimeError):proxy.admin_address({'admin':{'listen':address}})

    def test_disabled_admin_not_reenabled(self):
        with self.assertRaises(RuntimeError):proxy.admin_address({'admin':{'disabled':True}})

    def test_loopback_admin_supported(self):
        self.assertEqual(proxy.admin_address({}),('localhost:2019','http://localhost:2019/config/'))

    def test_health_mismatch_is_rejected(self):
        def fake(url):
            return {'info':{'version':'4.3.0'}} if url.endswith('/openapi.json') else {'conectado':True,'base_datos':'vehiculo_iot'}
        with self.assertRaises(RuntimeError):proxy.api_check('https://example.invalid',getter=fake)
