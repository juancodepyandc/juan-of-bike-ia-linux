"""Native intent fields are constrained; transport responses are fixtures."""
import importlib.util
import json
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('_test_motion_classifier', ROOT/'application/python-services/motion_intent_classifier.py')
CLASSIFIER = importlib.util.module_from_spec(spec)
with patch.dict(sys.modules, {'llm_disponible': SimpleNamespace(resoudre_modele=lambda *a, **k: 'fixture:local')}):
    spec.loader.exec_module(CLASSIFIER)


class IntentTransportTests(unittest.TestCase):
    def test_request_constrains_fields_consumed_by_normalizer_and_keeps_override(self):
        import io
        observed = []
        def respond(request, **kwargs):
            observed.append(json.loads(request.data))
            return io.BytesIO(json.dumps({'message':{'content':json.dumps({
                'category':'fan_pwm','confidence':0.95,'rationale':'Fixture',
                'mechanical_anim':{'axis':'Y','rpm':30}})}}).encode())
        with patch.object(CLASSIFIER.urllib.request, 'urlopen', side_effect=respond):
            result = CLASSIFIER.classify('fan','rotate slowly around Y','fixture:local')
        payload = observed[0]
        self.assertEqual(payload['format']['required'], ['category','confidence','rationale'])
        self.assertEqual(set(payload['format']['properties']['category']['enum']), CLASSIFIER.CATEGORIES)
        self.assertEqual(payload['messages'][0]['content'], CLASSIFIER.SYSTEM_PROMPT)
        self.assertIn('rotate slowly around Y', payload['messages'][1]['content'])
        self.assertEqual(result['category'],'fan_pwm')
        self.assertEqual(result['mechanical_anim']['axis'],'Y')
        self.assertEqual(result['model'],'fixture:local')

    def test_offline_fallback_does_not_claim_model_confidence(self):
        import urllib.error
        with patch.object(CLASSIFIER.urllib.request, 'urlopen', side_effect=urllib.error.URLError('fixture offline')):
            result = CLASSIFIER.classify('fan', model='fixture:local')
        self.assertEqual(result['model'],'fallback:regex')
        self.assertEqual(result['confidence'],0)
