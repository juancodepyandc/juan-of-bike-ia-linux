import json
import hashlib
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest

from agi_core.json_evidence import compare_evidence, pointer
from agi_core.mission_protocol import validate_checks, PURE_CHECKS
from agi_core.mission_tools import MissionTools


class EvidenceBindings(unittest.TestCase):
    def setUp(self):
        self.receipts = {
            'observed-page': {'ok': True, 'tool': 'browser_action',
                              'result': {'title': 'Actual page', 'text': 'Open project\nCurrent resources'}},
            'observed-resource': {'ok': True, 'tool': 'read_mcp_resource',
                                  'result': {'text': json.dumps({'workers': 0})}},
        }

    def test_saved_fields_require_actual_observed_values(self):
        bindings = [{'path': '/title', 'evidence_id': 'observed-page', 'source_pointer': '/result/title'},
                    {'path': '/labels', 'evidence_id': 'observed-page', 'source_pointer': '/result/text', 'relation': 'text_in'},
                    {'path': '/workers', 'evidence_id': 'observed-resource', 'source_pointer': '/result/text',
                     'decode_json': True, 'value_pointer': '/workers'}]
        actual = {'title': 'Actual page', 'labels': ['Open project', 'Current resources'], 'workers': 0}
        self.assertTrue(compare_evidence(actual, bindings, self.receipts)['passed'])
        for key, forged in [('title', 'Invented page'), ('labels', ['Invented label']), ('workers', False)]:
            with self.subTest(key=key):
                self.assertFalse(compare_evidence({**actual, key: forged}, bindings, self.receipts)['passed'])

    def test_missing_failed_or_assertion_receipts_cannot_ground_a_claim(self):
        binding = [{'path': '', 'evidence_id': 'source', 'source_pointer': '/result'}]
        for receipts in ({}, {'source': {'ok': False, 'result': 'x'}},
                         {'source': {'ok': True, 'tool': 'write_file', 'result': 'x'}},
                         {'source': {'ok': True, 'tool': 'verify', 'result': 'x'}}):
            with self.subTest(receipts=receipts), self.assertRaises(ValueError):
                compare_evidence('x', binding, receipts)

    def test_json_decoding_is_explicit_and_strict(self):
        binding = [{'path': '', 'evidence_id': 'source', 'source_pointer': '/result', 'decode_json': True}]
        for text in ('{"x":1,"x":2}', '{"x":1e999}', 'NaN'):
            with self.subTest(text=text), self.assertRaises(ValueError):
                compare_evidence({}, binding, {'source': {'ok': True, 'tool': 'read_mcp_resource', 'result': text}})
        with self.assertRaises(ValueError):
            compare_evidence('x', [{**binding[0], 'decode_json': False, 'value_pointer': '/x'}],
                             {'source': {'ok': True, 'tool': 'read_mcp_resource', 'result': '{"x":"x"}'}})

    def test_pointer_escaping_and_bounds_do_not_execute_expressions(self):
        self.assertEqual(pointer({'a/b': {'~': [5]}}, '/a~1b/~0/0'), 5)
        for path in ('/missing', '/a~2', '/00', '/-1', '__import__("os")'):
            with self.subTest(path=path), self.assertRaises(ValueError):
                pointer([0], path)

    def test_pointer_feedback_explains_syntax_and_actual_nesting_without_values(self):
        with self.assertRaisesRegex(ValueError, 'Binding path:.*RFC 6901'):
            compare_evidence({}, [{'path':'items[0]', 'evidence_id':'observed-page',
                                   'source_pointer':'/result/title'}], self.receipts)
        with self.assertRaises(ValueError) as caught:
            pointer({'result':{'private_value':'never expose this value'}}, '/title')
        self.assertIn('result', str(caught.exception))
        self.assertNotIn('never expose this value', str(caught.exception))

    def test_empty_or_duplicate_bindings_and_unmatched_text_are_rejected(self):
        binding = {'path': '', 'evidence_id': 'observed-page', 'source_pointer': '/result/text', 'relation': 'text_in'}
        for bindings in ([], [binding, binding]):
            with self.assertRaises(ValueError):
                compare_evidence('x', bindings, self.receipts)
        for value in ('', [], [1]):
            with self.subTest(value=value), self.assertRaises(ValueError):
                compare_evidence(value, [binding], self.receipts)


class NativeEvidenceVerification(unittest.IsolatedAsyncioTestCase):
    async def test_native_verifier_reads_actual_saved_bytes_and_keeps_provenance(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target = root/'result.json'
            target.write_text(json.dumps({'title':'Observed'}))
            state = {'criteria':['Correspondence'], 'evidence':[
                {'id':'receipt', 'tool':'browser_action', 'ok':True, 'result':{'title':'Observed'}}]}
            agent = SimpleNamespace(state=state, policy=SimpleNamespace(output_chars=12000),
                                    _file_path=lambda path:root/path)
            tools = MissionTools(agent,root,'python')
            check = {'kind':'json_evidence','path':'result.json','criterion':'Correspondence','bindings':[
                {'path':'/title','evidence_id':'receipt','source_pointer':'/result/title'}]}
            validate_checks([check],state['criteria'])
            result = await tools.execute('verify',{'checks':[check]})
            self.assertTrue(result['passed'])
            self.assertEqual(result['checks'][0]['observed_sha256'],hashlib.sha256(target.read_bytes()).hexdigest())
            self.assertEqual(result['checks'][0]['bindings'][0]['source_tool'],'browser_action')
            target.write_text(json.dumps({'title':'Invented'}))
            failed = await tools.execute('verify',{'checks':[check]})
            self.assertFalse(failed['passed'])
            self.assertNotEqual(failed['checks'][0]['observed_sha256'],result['checks'][0]['observed_sha256'])
            state['evidence'][0]['ok'] = False
            self.assertFalse((await tools.execute('verify',{'checks':[check]}))['passed'])

    def test_preflight_rejects_malformed_bindings_before_any_worker(self):
        self.assertIn('json_evidence',PURE_CHECKS)
        for bindings in ([],['string'],[{'path':'','evidence_id':'receipt','source_pointer':'/a~2'}],
                         [{'path':'','evidence_id':'receipt','source_pointer':'','decode_json':1}]):
            with self.subTest(bindings=bindings), self.assertRaises(ValueError):
                validate_checks([{'kind':'json_evidence','path':'output.json','bindings':bindings}])
