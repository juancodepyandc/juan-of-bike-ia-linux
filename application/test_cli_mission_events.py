import importlib
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import threading
import unittest
from unittest import mock

from flask import Flask


class MissionEventTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.directory = tempfile.TemporaryDirectory()
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        with mock.patch.dict(os.environ, {'XDG_DATA_HOME': cls.directory.name}), mock.patch('threading.Thread.start'):
            cls.routes = importlib.import_module('routes.cli_bp_routes')
        cls.app = Flask(__name__)
        cls.app.register_blueprint(cls.routes.cli_bp)

    @classmethod
    def tearDownClass(cls):
        cls.directory.cleanup()

    def setUp(self):
        self.mission = {'id': 'fixture', 'status': 'planning', 'events': [],
                        'started_at': 10.0, 'finished_at': None, 'steps': [], 'errors': []}
        patch = mock.patch.object(self.routes, '_CLI_MISSIONS', {'fixture': self.mission})
        patch.start()
        self.addCleanup(patch.stop)

    def receive(self, events):
        connection = mock.MagicMock()
        connection.__enter__.return_value = connection
        connection.connect.side_effect = [None, ConnectionError('end of fixture')]
        connection.makefile.return_value = io.StringIO(''.join(json.dumps({
            'event_type': 'mission.event', 'payload': {'mission_id': 'fixture', 'event': event},
        }) + '\n' for event in events))
        with mock.patch.object(self.routes.socket, 'socket', return_value=connection), \
             mock.patch.object(self.routes.time, 'sleep', side_effect=KeyboardInterrupt), \
             mock.patch.object(self.routes.time, 'time', return_value=20.0):
            with self.assertRaises(KeyboardInterrupt):
                self.routes._ipc_mission_listener()

    def test_completion_updates_status_and_elapsed_time(self):
        self.receive([{'type': 'mission_complete', 'result': 'done', 'ts': 19.0}])
        self.assertEqual(self.mission['status'], 'completed')
        self.assertEqual(self.mission['finished_at'], 20.0)
        self.assertEqual(self.mission['result'], 'done')
        with self.app.test_request_context():
            response = self.routes.cli_mission_status.__wrapped__('fixture')
        self.assertEqual(response.get_json()['elapsed_seconds'], 10.0)

    def test_error_records_failure_for_both_error_fields(self):
        for field in ['error', 'message']:
            with self.subTest(field=field):
                self.mission.update(status='planning', errors=[], events=[])
                self.receive([{'type': 'error', field: 'fixture failure'}])
                self.assertEqual(self.mission['status'], 'failed')
                self.assertEqual(len(self.mission['errors']), 1)

    def test_terminal_stream_closes_without_heartbeat(self):
        self.receive([{'type': 'mission_complete', 'result': 'done'}])
        with self.app.test_request_context(), mock.patch.object(self.routes.time, 'sleep', side_effect=AssertionError('stream did not terminate')):
            response = self.routes.cli_mission_stream.__wrapped__('fixture')
            try:
                chunks = list(response.response)
            finally:
                response.close()
        self.assertEqual(len(chunks), 2)
        self.assertIn('mission_complete', chunks[-1])

    def test_malformed_event_is_not_added_to_stream(self):
        self.receive([None, [], {}, {'type': []}, {'type': 'token', 'content': 'valid'}])
        self.assertEqual(self.mission['events'], [{'type': 'token', 'content': 'valid'}])

    def test_late_events_do_not_reopen_completed_mission(self):
        self.receive([{'type': 'mission_complete', 'result': 'done'}, {'type': 'step_start', 'step': 'late'}])
        self.assertEqual(self.mission['status'], 'completed')
        self.assertEqual(len(self.mission['events']), 1)

    def test_remote_client_receives_terminal_event_over_http(self):
        remote = Path(__file__).resolve().parents[2] / 'aurora-remote-cli'
        sys.path.insert(0, str(remote))
        temporary = Path(self.directory.name)
        with mock.patch.dict(os.environ, {'XDG_CONFIG_HOME': str(temporary), 'XDG_DATA_HOME': str(temporary)}), \
             mock.patch('pathlib.Path.home', return_value=temporary):
            from aurora_cli.client import AuroraClient
        from werkzeug.serving import make_server
        self.receive([{'type': 'mission_complete', 'result': 'contract result'}])
        server = make_server('127.0.0.1', 0, self.app)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        client = AuroraClient(server_url=f'http://127.0.0.1:{server.server_port}', api_key='fixture-key')
        stream = client.mission_stream('fixture')
        try:
            self.assertEqual(next(stream)['result'], 'contract result')
            with self.assertRaises(StopIteration):
                next(stream)
            status = client.mission_status('fixture')
            self.assertEqual(status['status'], 'completed')
            self.assertEqual(status['elapsed_seconds'], 10.0)
        finally:
            stream.close()
            client.close()
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)
        self.assertFalse(thread.is_alive())


if __name__ == '__main__':
    unittest.main()
