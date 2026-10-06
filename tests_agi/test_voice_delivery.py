"""Voice HTTP delivery contracts; synthesis/transcription engines are fixtures."""
import importlib.util
import io
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from flask import Flask

ROOT = Path(__file__).resolve().parents[1]


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


with patch.dict(sys.modules, {'flask_cors': SimpleNamespace(CORS=lambda *a, **k: None)}):
    BRIDGE = load('_test_voice_bridge', ROOT/'application/bridge_server.py')
with patch.dict(sys.modules, {'bridge_server': BRIDGE}):
    VOICE = load('_test_voice_routes', ROOT/'application/routes/voice_bp_routes.py')


class VoiceDeliveryTests(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.workspace = Path(folder.name)
        self.voices = self.workspace/'output/voix/test'
        self.voices.mkdir(parents=True)
        patches = [patch.object(VOICE, 'WORKSPACE', str(self.workspace)),
                   patch.object(VOICE, 'sortie_module', return_value=str(self.voices))]
        for item in patches:
            item.start()
            self.addCleanup(item.stop)
        app = Flask(__name__)
        app.register_blueprint(VOICE.voice_bp)
        self.client = app.test_client()

    def synthesize(self, argv, **kwargs):
        output = Path(argv[argv.index('--output')+1])
        output.write_bytes(argv[argv.index('--text')+1].encode())
        return json.dumps({'ok': True, 'engine': 'fixture'}).encode()

    def test_each_synthesis_keeps_its_own_audio_with_same_clock(self):
        with patch.object(VOICE.subprocess, 'check_output', side_effect=self.synthesize), \
                patch.object(VOICE.time, 'time', return_value=1234):
            first = self.client.post('/api/voice/tts', json={'text':'first'}).json
            second = self.client.post('/api/voice/tts', json={'text':'second'}).json
        self.assertTrue(first['ok'] and second['ok'])
        self.assertNotEqual(first['audio_url'], second['audio_url'])
        self.assertEqual(self.client.get(first['audio_url']).data, b'first')
        self.assertEqual(self.client.get(second['audio_url']).data, b'second')

    def test_explicit_audio_path_is_confined_and_missing_does_not_fall_back(self):
        (self.voices/'legacy.wav').write_bytes(b'legacy')
        for path in ('../outside.wav', '/etc/passwd', 'test/missing.wav'):
            with self.subTest(path=path):
                response = self.client.get('/api/voice/tts-audio', query_string={'file':path})
                self.assertEqual(response.status_code, 404)
        self.assertEqual(self.client.get('/api/voice/tts-audio').data, b'legacy')

    def test_transcription_inputs_are_unique_and_cleaned(self):
        observed = []
        def transcribe(argv, **kwargs):
            source = Path(argv[argv.index('--audio')+1])
            self.assertTrue(source.is_absolute())
            self.assertTrue(source.is_file())
            observed.append((source, source.read_bytes()))
            return b'{"ok":true,"text":"fixture transcription"}\n'
        with patch.object(VOICE.subprocess, 'check_output', side_effect=transcribe):
            for audio in (b'first audio', b'second audio'):
                response = self.client.post('/api/voice/stt', data={'audio':(io.BytesIO(audio),'voice.wav')})
                self.assertEqual(response.status_code, 200, response.json)
        self.assertNotEqual(observed[0][0], observed[1][0])
        self.assertEqual([data for _, data in observed], [b'first audio', b'second audio'])
        self.assertTrue(all(not path.exists() for path, _ in observed))
