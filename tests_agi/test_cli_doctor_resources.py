"""Doctor reuses measured resources without booting the bridge or its services."""
import ast
import datetime
import json
import os
from pathlib import Path
import subprocess
import sys
from types import ModuleType, SimpleNamespace
import unittest
from unittest.mock import Mock, patch


ROOT = Path(__file__).resolve().parents[1]


def doctor_function(name='cli_doctor'):
    source = ROOT / 'application' / 'routes' / 'cli_bp_routes.py'
    function = next(node for node in ast.parse(source.read_text(encoding='utf-8')).body
                    if isinstance(node, ast.FunctionDef) and node.name == name)
    function.decorator_list = []
    namespace = {'os': os, 'WORKSPACE': '/fixture/unused/workspace',
        'g': SimpleNamespace(cli_key_rec={'label': 'fixture'}),
        'requests': SimpleNamespace(RequestException=ConnectionError, get=Mock(return_value=SimpleNamespace(ok=True,
            json=lambda: {'models': [{'name': 'observed:small', 'size': 5 * 1024 ** 3}]}))),
        'subprocess': SimpleNamespace(check_output=Mock(return_value='16384\n')),
        'psutil': SimpleNamespace(virtual_memory=Mock(return_value=SimpleNamespace(
            total=30 * 1024 ** 3, available=27 * 1024 ** 3))),
        'OLLAMA_URL': 'http://fixture.invalid', 'COMFYUI_URL': 'http://fixture.invalid',
        '_comfyui_is_ready': Mock(return_value=False),
        '_ext_default_model': Mock(return_value='observed:small'),
        '_ext_default_model_diagnostics': Mock(return_value={'selection': 'automatic'}),
        '_CLI_PERMISSION_LEVELS': ['SAFE', 'STANDARD', 'AUTONOMOUS', 'FULL'],
        '_CLI_VERSION': 'fixture', '_cli_discover_mcp': Mock(return_value=[]),
        '_cli_discover_skills': Mock(return_value=[]), 'jsonify': lambda value: value,
        'request': SimpleNamespace(get_json=Mock(return_value={})),
        '_secrets': SimpleNamespace(token_hex=lambda count: 'fixture'), 'datetime': datetime,
        '_CLI_DYNAMIC_AGENTS_PATH': '/fixture/unused/agents.json',
        '_cli_load_json': Mock(return_value={'agents': []}), '_cli_save_json': Mock(),
        '_cli_load_context_for_workspace': Mock(return_value={
            'mcp_tools_count': 0, 'skills_count': 0, 'connections_count': 0}),
        'Response': lambda stream, **kwargs: SimpleNamespace(stream=stream),
        'stream_with_context': lambda stream: stream}
    exec(compile(ast.Module(body=[function], type_ignores=[]), str(source), 'exec'), namespace)
    return namespace


class DoctorResourceTests(unittest.TestCase):
    def setUp(self):
        self.namespace = doctor_function()
        bus = ModuleType('agi_core.bus')
        bus.probe_sync = Mock(return_value={'ok': True, 'mission_ready': True})
        self.modules = patch.dict(sys.modules, {'agi_core.bus': bus})
        self.modules.start()
        self.addCleanup(self.modules.stop)

    def test_doctor_passes_existing_gpu_and_ram_measurements_to_selection(self):
        result = self.namespace['cli_doctor']()
        self.assertTrue(result['ready'])
        self.assertEqual(result['hardware'], {'ram_gb': 30.0,
            'ram_available_gb': 27.0, 'vram_total_gb': 16.0})
        self.assertEqual(result['default_model'], 'observed:small')
        self.namespace['requests'].get.assert_called_once()
        self.namespace['subprocess'].check_output.assert_called_once()
        self.namespace['_ext_default_model'].assert_called_once_with(
            models=[{'name': 'observed:small', 'size': 5 * 1024 ** 3}],
            resources={'ram_total_bytes': 30 * 1024 ** 3, 'nvidia_vram_bytes': 16 * 1024 ** 3})

    def test_driver_failure_is_not_treated_as_available_vram(self):
        self.namespace['subprocess'].check_output.side_effect = subprocess.CalledProcessError(1, ['nvidia-smi'])
        result = self.namespace['cli_doctor']()
        self.assertFalse(result['gpu_ready'])
        self.assertEqual(result['hardware']['vram_total_gb'], 0)
        resources = self.namespace['_ext_default_model'].call_args.kwargs['resources']
        self.assertEqual(resources['nvidia_vram_bytes'], 0)

    def test_model_refusal_does_not_report_ready_missions(self):
        self.namespace['_ext_default_model'].side_effect = ValueError('Aucun modèle admissible')
        result = self.namespace['cli_doctor']()
        self.assertFalse(result['ready'])
        self.assertEqual(result['default_model'], '')
        self.assertIn({'name': 'Modèle de mission', 'ok': False,
                       'detail': 'Aucun modèle admissible'}, result['checks'])

    def test_missing_memory_measurement_remains_unknown(self):
        self.namespace['psutil'].virtual_memory.side_effect = OSError('unavailable')
        result = self.namespace['cli_doctor']()
        self.assertIsNone(result['hardware']['ram_gb'])
        self.assertIsNone(result['hardware']['ram_available_gb'])
        self.assertIsNone(self.namespace['_ext_default_model'].call_args.kwargs['resources']['ram_total_bytes'])


class DirectRouteModelSelectionTests(unittest.TestCase):
    def test_default_refusal_is_json_503_before_inference_or_agent_write(self):
        for name in ('cli_chat', 'cli_dynamic_agent_create'):
            for failure in (ValueError('Aucun modèle admissible'), ConnectionError('Ollama indisponible')):
                with self.subTest(route=name, failure=type(failure).__name__):
                    namespace = doctor_function(name)
                    namespace['_ext_default_model'].side_effect = failure
                    result, status = namespace[name]()
                    self.assertEqual(status, 503)
                    self.assertEqual(result, {'ok': False, 'error_kind': 'model_unavailable', 'error': str(failure)})
                    namespace['_cli_load_context_for_workspace'].assert_not_called()
                    namespace['_cli_save_json'].assert_not_called()

    def test_empty_default_is_refused_instead_of_using_a_hidden_fallback(self):
        for name in ('cli_chat', 'cli_dynamic_agent_create'):
            with self.subTest(route=name):
                namespace = doctor_function(name)
                namespace['_ext_default_model'].return_value = ''
                result, status = namespace[name]()
                self.assertEqual(status, 503)
                self.assertEqual(result['error_kind'], 'model_unavailable')
                self.assertTrue(result['error'])

    def test_explicit_model_bypasses_automatic_selection(self):
        for name in ('cli_chat', 'cli_dynamic_agent_create'):
            with self.subTest(route=name):
                namespace = doctor_function(name)
                namespace['request'].get_json.return_value = {'model': 'chosen:exact'}
                result = namespace[name]()
                namespace['_ext_default_model'].assert_not_called()
                if name == 'cli_dynamic_agent_create':
                    self.assertEqual(result['agent']['model'], 'chosen:exact')
                    namespace['_cli_save_json'].assert_called_once()
                else:
                    self.assertTrue(hasattr(result, 'stream'))


class ChatFailureTests(unittest.TestCase):
    def test_upstream_errors_and_incomplete_streams_are_explicit(self):
        for failure in ('http', 'model', 'incomplete'):
            with self.subTest(failure=failure):
                namespace = doctor_function('cli_chat')
                namespace['json'] = json
                upstream = Mock()
                if failure == 'http':
                    upstream.raise_for_status.side_effect = RuntimeError('404 model not found')
                    upstream.iter_lines.return_value = []
                elif failure == 'model':
                    upstream.iter_lines.return_value = [b'{"error":"model failed"}']
                else:
                    upstream.iter_lines.return_value = [b'{"message":{"content":"partial"}}']
                namespace['requests'].post = Mock(return_value=upstream)
                events = [json.loads(line.removeprefix('data: ').strip())
                          for line in namespace['cli_chat']().stream]
                self.assertEqual(events[-1]['type'], 'error')
                self.assertFalse(any(event['type'] == 'done' for event in events))
                upstream.close.assert_called_once()

    def test_complete_stream_has_tokens_and_completion(self):
        namespace = doctor_function('cli_chat')
        namespace['json'] = json
        upstream = Mock()
        upstream.iter_lines.return_value = [b'{"message":{"content":"answer"}}', b'{"done":true}']
        namespace['requests'].post = Mock(return_value=upstream)
        events = [json.loads(line.removeprefix('data: ').strip())
                  for line in namespace['cli_chat']().stream]
        self.assertEqual([e['type'] for e in events], ['token', 'done'])
        upstream.close.assert_called_once()
