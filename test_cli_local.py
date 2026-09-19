import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest import mock


class LocalCliTests(unittest.TestCase):
    def test_local_entry_uses_shared_client_and_loopback_url(self):
        root = Path(__file__).resolve().parent
        remote = root.parent / 'aurora-remote-cli'
        self.assertTrue((remote / 'aurora_cli' / 'client.py').is_file())
        spec = importlib.util.spec_from_file_location('aurora_local_entry', root / 'aurora_cli.py')
        entry = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(entry)
        with tempfile.TemporaryDirectory() as directory:
            temporary = Path(directory)
            with mock.patch.dict(os.environ, {
                'XDG_CONFIG_HOME': str(temporary / 'config'),
                'XDG_DATA_HOME': str(temporary / 'data'),
            }), mock.patch('pathlib.Path.home', return_value=temporary), mock.patch.object(sys, 'path', [str(remote), *sys.path]):
                import httpx
                from aurora_cli import config
                from aurora_cli.client import AuroraClient
                config.save({'server_url': 'https://remote.example', 'api_key': 'fixture-key'})
                requests = []

                def handle(request):
                    requests.append(request)
                    return httpx.Response(200, json={'ok': True, 'server_version': '1.0.0'})

                def cli_main():
                    client = AuroraClient()
                    try:
                        self.assertTrue(client.version()['ok'])
                    finally:
                        client.close()

                cli = types.ModuleType('aurora_cli.cli')
                cli.main = cli_main
                with mock.patch.dict(sys.modules, {'aurora_cli.cli': cli}), mock.patch('httpx.HTTPTransport', return_value=httpx.MockTransport(handle)):
                    entry.main()
                self.assertEqual(str(requests[0].url), 'http://127.0.0.1:3001/api/cli/version')
                self.assertEqual(requests[0].headers['authorization'], 'Bearer fixture-key')
                saved = json.loads(config.CONFIG_FILE.read_text())
                self.assertEqual(saved['server_url'], 'https://remote.example')


if __name__ == '__main__':
    unittest.main()
