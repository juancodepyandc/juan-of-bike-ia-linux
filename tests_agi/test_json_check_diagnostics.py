"""JSON key-set diagnostics use saved files and preserve every supplied check."""
import hashlib
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import AsyncMock, patch

from agi_core.mission_agent import AutonomousMissionAgent
from agi_core.mission_protocol import tool_response_schema


class JSONCheckDiagnostics(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        folder=tempfile.TemporaryDirectory();self.addCleanup(folder.cleanup)
        self.root=Path(folder.name)
        environment=patch.dict(os.environ,{'AURORA_DATA_DIR':str(self.root/'runtime')})
        environment.start();self.addCleanup(environment.stop)
        self.agent=AutonomousMissionAgent('json-diagnostics','Verify saved rows and sum',str(self.root),'fixture:local')
        self.agent._emit=AsyncMock()
        self.agent._plan({'steps':['Verify saved values and complete format'],'criteria':['Saved result']})
        self.path=self.root/'summary.json'

    async def verify(self,data,**expectations):
        self.path.write_text(json.dumps(data),encoding='utf-8')
        before=self.path.read_bytes()
        result=await self.agent._execute('verify',{'checks':[{'kind':'json','path':'summary.json',
            'criterion':'Saved result',**expectations}]})
        self.assertEqual(self.path.read_bytes(),before)
        self.assertEqual(result['checks'][0]['observed_sha256'],hashlib.sha256(before).hexdigest())
        self.assertFalse(self.agent.state['process_observations'])
        return result

    async def test_partial_keys_fail_despite_true_expression_then_complete_keys_pass(self):
        data={'rows':5,'sum':163}
        failed=await self.verify(data,keys=['rows'],expressions=['data["rows"] == 5'])
        self.assertFalse(failed['passed'])
        item=failed['checks'][0]
        self.assertEqual(item['expression_results'],[{'expression':'data["rows"] == 5','passed':True}])
        keys=item['keys_result']
        self.assertFalse(keys['passed'])
        self.assertEqual(keys['requested'],['rows'])
        self.assertEqual(keys['observed'],['rows','sum'])
        self.assertEqual(keys['missing'],[])
        self.assertEqual(keys['unexpected'],['sum'])
        self.assertIn('exact complete',keys['reason'])
        complete=await self.verify(data,keys=['sum','rows'],expressions=['data["rows"] == 5'])
        self.assertTrue(complete['passed'])
        self.assertTrue(complete['checks'][0]['keys_result']['passed'])
        self.assertEqual(complete['checks'][0]['keys_result']['requested'],['sum','rows'])
        expression_only=await self.verify(data,expressions=['data["rows"] == 5'])
        self.assertTrue(expression_only['passed'])
        self.assertNotIn('keys_result',expression_only['checks'][0])

    async def test_missing_and_unexpected_keys_are_distinguished(self):
        result=await self.verify({'sum':163,'rows':5},keys=['rows','total'],expressions=['data["rows"] == 5'])
        self.assertFalse(result['passed'])
        keys=result['checks'][0]['keys_result']
        self.assertEqual(keys['observed'],['rows','sum'])
        self.assertEqual(keys['missing'],['total'])
        self.assertEqual(keys['unexpected'],['sum'])
        self.assertIn('total',keys['reason'])
        self.assertIn('sum',keys['reason'])

    async def test_matching_keys_never_override_failed_values_types_or_expressions(self):
        data={'rows':5,'sum':163}
        variants=[{'equals':{'rows':5,'sum':164}}, {'types':{'rows':'string'}},
                  {'expressions':['data["sum"] == 164']}]
        for expectation in variants:
            with self.subTest(expectation=expectation):
                result=await self.verify(data,keys=['rows','sum'],**expectation)
                self.assertFalse(result['passed'])
                self.assertTrue(result['checks'][0]['keys_result']['passed'])
        wrong_boolean=await self.verify({'rows':True,'sum':163},keys=['rows','sum'],types={'rows':'integer'})
        self.assertFalse(wrong_boolean['passed'])

    async def test_non_objects_fail_even_with_an_empty_requested_key_set(self):
        for data in ([],['rows'],None,True,5,1.5,'rows'):
            with self.subTest(data=data):
                result=await self.verify(data,keys=[])
                self.assertFalse(result['passed'])
                keys=result['checks'][0]['keys_result']
                self.assertFalse(keys['passed'])
                self.assertEqual(keys['requested'],[])
                self.assertIsNone(keys['observed'])
                self.assertIsNone(keys['missing'])
                self.assertIsNone(keys['unexpected'])
                self.assertIn('JSON object',keys['reason'])
        empty_object=await self.verify({},keys=[])
        self.assertTrue(empty_object['passed'])

    async def test_malformed_keys_remain_errors_instead_of_partial_set_checks(self):
        for keys in ('rows',None,{},[1],['rows','rows']):
            with self.subTest(keys=keys):
                result=await self.verify({'rows':5,'sum':163},keys=keys,expressions=['data["rows"] == 5'])
                self.assertFalse(result['passed'])
                item=result['checks'][0]
                self.assertIn('distinct strings',item['error'])
                self.assertNotIn('keys_result',item)
                self.assertNotIn('expression_results',item)

    def test_native_descriptions_and_both_prompts_explain_exact_keys_and_expression_only(self):
        schema=tool_response_schema(['Saved result'],['verify'])
        branches=schema['oneOf'][0]['properties']['args']['properties']['checks']['items']['anyOf']
        for branch in branches:
            if branch['properties']['kind']['const']!='json':continue
            description=branch['properties']['keys']['description']
            self.assertIn('complete',description)
            self.assertIn('omit keys',description)
        for prompt in (self.agent._system_prompt(),self.agent._compact_system_prompt()):
            self.assertIn('exact complete',prompt)
            self.assertIn('omit keys',prompt)
