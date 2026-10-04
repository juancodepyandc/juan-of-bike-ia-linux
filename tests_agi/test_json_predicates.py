"""Predicates measure saved values; they do not execute Python or certify semantics."""
import hashlib
import json
import os
from pathlib import Path
import random
import sys
import tempfile
import unittest
from unittest.mock import AsyncMock, patch

from agi_core.mission_agent import AutonomousMissionAgent
from agi_core.mission_protocol import tool_response_schema, validate_checks
from agi_core.mission_tools import strict_json


class JSONPredicates(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.root = Path(folder.name)
        env = patch.dict(os.environ,{'AURORA_DATA_DIR':str(self.root/'runtime')})
        env.start()
        self.addCleanup(env.stop)
        self.agent = AutonomousMissionAgent('predicates','Verify the saved calculations',str(self.root),'fixture:local')
        self.agent._emit = AsyncMock()
        self.agent._plan({'steps':['Check actual saved values'],'criteria':['Calculation']})
        self.path = self.root/'answer.json'

    async def check(self, data, expressions):
        self.path.write_text(json.dumps(data),encoding='utf-8')
        return await self.agent._execute('verify',{'checks':[{'kind':'json','path':'answer.json',
            'expressions':expressions,'criterion':'Calculation'}]})

    async def test_budget_is_not_the_actual_consumption(self):
        data = {'a':18,'b':0,'pieces':162,'consommation':163}
        expressions = ['data["consommation"] == 9 * data["a"] + 20 * data["b"]',
                       'data["pieces"] == 9 * data["a"] + 8 * data["b"]',
                       '0 <= data["consommation"] <= 163']
        bad = await self.check(data,expressions)
        self.assertFalse(bad['passed'])
        self.assertEqual([e['passed'] for e in bad['checks'][0]['expression_results']],[False,True,True])
        self.assertEqual(bad['checks'][0]['observed'],data)
        self.assertTrue((await self.check({**data,'consommation':162},expressions))['passed'])

    async def test_relations_use_varied_inputs_and_exact_saved_values(self):
        rng = random.Random(164)
        for _ in range(8):
            coefficient,a,b = (rng.randint(1,99) for _ in range(3))
            data = {'inputs':[a,b],'total':coefficient*a-b,'half':a/2}
            expressions = [f'data["total"] == {coefficient} * data["inputs"][0] - data["inputs"][1]',
                           'data["half"] == data["inputs"][0] / 2']
            with self.subTest(data=data):
                self.assertTrue((await self.check(data,expressions))['passed'])
                self.assertFalse((await self.check({**data,'total':data['total']+1},expressions))['passed'])

    async def test_null_lists_unary_chains_and_short_circuit_are_pure(self):
        expressions = ['data["path"] == [] and data["cost"] == None',
                       'not (data["n"] < 0) and -data["n"] == 0',
                       'data["n"] == 0 or 10 / data["n"] > 1',
                       '+data["x"] // 2 == 2 and data["x"] % 2 == 1',
                       '0 < data["x"] < 10']
        result = await self.check({'path':[],'cost':None,'n':0,'x':5},expressions)
        self.assertTrue(result['passed'])
        self.assertFalse(self.agent.state['process_observations'])

    async def test_untrusted_expressions_cannot_call_access_attributes_or_mutate(self):
        marker = self.root/'marker'
        marker.write_text('preserve')
        expressions = ['__import__("os").system("echo bad")','data.__class__',
            'False and open("marker","w")','[x for x in data]',
            '(lambda: True)()','data["x"] ** 999999999','"x" * 999999999',
            '(data := True)','True | False','data["x"] << 1000000000']
        for expression in expressions:
            with self.subTest(expression=expression):
                result = await self.check({'x':1},[expression])
                self.assertFalse(result['passed'])
                record = result['checks'][0]
                self.assertTrue('error' in record or any('error' in e for e in record.get('expression_results',[])))
        self.assertEqual(marker.read_text(),'preserve')
        self.assertFalse(self.agent.state['process_observations'])

    async def test_missing_fields_bad_syntax_truthiness_and_nonfinite_numbers_fail(self):
        expressions = ['data["missing"] == 1','data["n"]','data["x"] + 1 > 0',
            'data["x"] > 0','data["x"] == 1','1 / 0 == 1','data["x"] ==',
            '1e999 > 0','data["items"][True] == 1']
        for expression in expressions:
            with self.subTest(expression=expression):
                self.assertFalse((await self.check({'x':True,'n':1,'items':[1]},[expression]))['passed'])

    async def test_changed_bytes_invalidate_a_still_passing_relation(self):
        result = await self.check({'a':1,'b':2},['data["a"] + data["b"] == 3'])
        self.agent._record_verification(result,1)
        self.assertEqual(self.agent.state['verified'],['Calculation'])
        self.path.write_text('{"a":2,"b":1}')
        await self.agent._refresh_verified(2)
        self.assertFalse(self.agent.state['verified'])
        self.assertFalse(self.agent.state['check_proofs'])

    async def test_mixed_batch_relations_measure_files_after_command_mutation(self):
        self.path.write_text('{"a":2,"total":4}')
        result = await self.agent._execute('verify',{'checks':[
            {'kind':'json','path':'answer.json','expressions':['data["total"] == 2 * data["a"]'],'criterion':'Calculation'},
            {'kind':'command','argv':[sys.executable,'-c',
                'from pathlib import Path; Path("answer.json").write_text(\'{"a":2,"total":5}\')'],'criterion':'Calculation'}]})
        self.assertFalse(result['passed'])
        self.assertTrue(result['checks'][0]['refreshed_after_commands'])
        self.assertEqual(result['checks'][0]['observed_sha256'],hashlib.sha256(self.path.read_bytes()).hexdigest())

    async def test_contract_accepts_expressions_alone_and_rejects_empty_or_wrong_types(self):
        good = {'kind':'json','path':'answer.json','expressions':['data["a"] == 2'],'criterion':'Calculation'}
        validate_checks([good])
        for expressions in ([],[1],[''],['   ']):
            with self.subTest(expressions=expressions), self.assertRaises(ValueError):
                validate_checks([{**good,'expressions':expressions}])
        self.path.write_text('{"a":2}')
        for expressions in ([],[1],[''],['   ']):
            result = await self.agent._execute('verify',{'checks':[{**good,'expressions':expressions}]})
            self.assertFalse(result['passed'])
        for expression in ('data["a"] ==','False and open("marker","w")','data.__class__','1e999 == 1e999'):
            with self.subTest(expression=expression), self.assertRaises(ValueError):
                validate_checks([{**good,'expressions':[expression]}])

    def test_native_schema_can_require_predicates_with_one_exact_criterion(self):
        schema = tool_response_schema(['Calculation'])
        for action in schema['oneOf']:
            if action['properties']['tool']['const'] not in {'verify','spawn_agent'}:
                continue
            variants = action['properties']['args']['properties']['checks']['items']['anyOf']
            predicate = next(v for v in variants if 'expressions' in v['required'])
            self.assertEqual(predicate['properties']['expressions']['minItems'],1)
            self.assertEqual(predicate['required'].count('criterion'),1)

    def test_scientific_overflow_is_not_a_finite_json_number(self):
        for raw in ('{"x":1e999}','[-1e999]','1e999','NaN','Infinity'):
            with self.subTest(raw=raw), self.assertRaises(ValueError):
                strict_json(raw)
