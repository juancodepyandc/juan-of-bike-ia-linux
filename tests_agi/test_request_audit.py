"""Separate checker context over real files/processes; all model replies substituted."""
from dataclasses import replace
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import AsyncMock, patch

from agi_core.mission_agent import AutonomousMissionAgent
from agi_core.runtime_policy import RuntimePolicy


def call(tool, **args):
    return {'tool':tool,'args':args}


class RequestAudit(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        folder=tempfile.TemporaryDirectory();self.addCleanup(folder.cleanup)
        self.root=Path(folder.name)
        env=patch.dict(os.environ,{'AURORA_DATA_DIR':str(self.root/'runtime')})
        env.start();self.addCleanup(env.stop)
        self.agent=AutonomousMissionAgent('audit',
            'Read input.csv, save summary.json with integer rows and sum of value, preserving input.csv bytes.',
            str(self.root),'fixture:local',policy=RuntimePolicy(request_audit=True,recovery_attempts=0))
        self.agent._emit=AsyncMock()
        self.agent._review_completion=AsyncMock(return_value={'approved':True,'unmet':[],'reason':'Substituted review'})
        self.raw=b'label,value\r\nfirst,17\r\nsecond,-28\r\nthird,64\r\nfourth,23\r\nfifth,80\r\nsixth,-17\r\n'
        (self.root/'input.csv').write_bytes(self.raw)
        self.criterion='The saved aggregates match the actual input'
        self.check={'kind':'csv_json','path':'input.csv','json_path':'summary.json','row_field':'rows',
                    'sum_fields':{'sum':'value'},'criterion':self.criterion}
        self.plan=call('set_plan',steps=['Read, compute and verify'],criteria=[self.criterion])
        self.wrong={'rows':6,'sum':122}
        self.correct={'rows':6,'sum':139}
        self.literal={'kind':'json','path':'summary.json','equals':self.wrong,'criterion':self.criterion}

    async def play(self,replies,generate,steps=None):
        iterator=iter(replies)
        async def stream(messages):
            yield json.dumps(next(iterator))
        self.agent.policy=replace(self.agent.policy,max_steps=steps or len(replies)+4)
        with patch.object(self.agent,'_chat_chunks',stream),patch.object(self.agent.gateway,'generate',generate):
            return await self.agent.run()

    def initial(self,data,check):
        return [self.plan,call('read_file',path='input.csv'),call('write_file',path='summary.json',content=json.dumps(data)),
                call('verify',checks=[check]),call('finish',message='Premature proposal')]

    async def test_false_positive_literal_is_falsified_from_source_then_repaired_and_audited(self):
        payloads=[]
        async def generate(system,payload,model,**kwargs):
            value=json.loads(payload);payloads.append(value)
            self.assertEqual(value['original_request'],self.agent.request_text)
            self.assertNotIn('proposed_answer',value)
            self.assertNotIn('verified',value)
            self.assertNotIn('expected',payload)
            self.assertNotIn('"sum": 122',payload)
            self.assertNotIn('"sum": 139',payload)
            schema=next(info for info in value['observed_files'] if info['path'].endswith('summary.json'))
            self.assertEqual(schema['json_fields'],{'rows':'integer','sum':'integer'})
            source=next(info for info in value['observed_files'] if info['path'].endswith('input.csv'))
            self.assertEqual(source['csv_columns'],['label','value'])
            return json.dumps(call('verify',checks=[self.check]))
        replies=self.initial(self.wrong,self.literal)+[
            call('write_file',path='summary.json',content=json.dumps(self.correct)),
            call('verify',checks=[self.check]),call('finish',message='Corrected actual aggregate'),
            call('finish',message='Audited and current')]
        result=await self.play(replies,generate)
        self.assertEqual(result,'Audited and current')
        self.assertEqual(self.agent.state['status'],'completed')
        self.assertEqual(len(payloads),2)
        audit_results=[e.args[1]['passed'] for e in self.agent._emit.call_args_list if e.args[0]=='request_audit_result']
        self.assertEqual(audit_results,[False,True])
        failed=next(e for e in self.agent.state['evidence'] if e['tool']=='verify' and not e['ok'])
        self.assertEqual(failed['result']['checks'][0]['expected'],self.correct)
        self.assertEqual((self.root/'input.csv').read_bytes(),self.raw)
        self.assertEqual(json.loads((self.root/'summary.json').read_text()),self.correct)
        self.agent._review_completion.assert_awaited_once()

    async def test_failed_independent_check_cannot_be_bypassed_by_finishing_again(self):
        generate=AsyncMock(return_value=json.dumps(call('verify',checks=[self.check])))
        replies=self.initial(self.wrong,self.literal)+[call('finish',message='Unsupported success')]*3
        self.assertIsNone(await self.play(replies,generate,steps=9))
        self.assertEqual(self.agent.state['status'],'failed')
        self.assertFalse(self.agent.state['request_audit']['passed'])
        self.assertFalse(self.agent.state['verified'])
        self.agent._review_completion.assert_not_awaited()
        generate.assert_awaited_once()

    async def test_invalid_auditor_does_not_execute_an_action_or_drop_required_criteria(self):
        generate=AsyncMock(return_value=json.dumps(call('verify',checks=[{**self.check,'criterion':'weakened'}])))
        replies=self.initial(self.wrong,self.literal)+[call('finish',message='Try again')]*2
        self.assertIsNone(await self.play(replies,generate,steps=7))
        self.assertEqual(self.agent.state['status'],'failed')
        self.assertNotIn('request_audit',self.agent.state)
        self.assertEqual(self.agent.state['action_count'],4)
        self.assertEqual(self.agent.state['criteria'],[self.criterion])
        self.agent._review_completion.assert_not_awaited()

    async def test_pure_audit_cache_rechecks_hashes_and_does_not_accept_external_same_sum_changes(self):
        generate=AsyncMock(return_value=json.dumps(call('verify',checks=[self.check])))
        await self.play(self.initial(self.correct,self.check),generate,steps=6)
        self.assertTrue(self.agent.state['request_audit']['passed'])
        self.assertTrue(await self.agent._completion_audit_current())
        (self.root/'input.csv').write_bytes(self.raw.replace(b'first,',b'changed-label,'))
        self.assertFalse(await self.agent._completion_audit_current())
        generate.assert_awaited_once()

    async def test_command_audit_is_not_automatically_replayed_for_cache_checks(self):
        command={'kind':'command','criterion':self.criterion,'argv':[sys.executable,'-c',
            'import csv,json; from pathlib import Path; values=list(csv.DictReader(open("input.csv",newline=""))); '
            'actual=json.load(open("summary.json")); assert actual=={"rows":len(values),"sum":sum(int(v["value"]) for v in values)}; '
            'p=Path("counter.txt");p.write_text(str(int(p.read_text())+1) if p.exists() else "1")']}
        generate=AsyncMock(return_value=json.dumps(call('verify',checks=[command])))
        await self.play(self.initial(self.correct,self.check),generate,steps=6)
        self.assertEqual((self.root/'counter.txt').read_text(),'1')
        self.assertTrue(await self.agent._completion_audit_current())
        self.assertTrue(await self.agent._completion_audit_current())
        self.agent.state['action_count']+=1
        self.assertFalse(await self.agent._completion_audit_current())
        self.assertEqual((self.root/'counter.txt').read_text(),'1')

    async def test_safe_auditor_schema_excludes_commands_and_runtime_rejects_forged_command(self):
        self.agent.permissions='SAFE';self.agent._plan(self.plan['args'])
        received=[]
        async def generate(system,payload,model,**kwargs):
            received.append(kwargs['response_format'])
            return json.dumps(call('verify',checks=[{'kind':'command','criterion':self.criterion,'argv':[sys.executable,'-c',
                'from pathlib import Path;Path("forbidden.txt").write_text("1")']}]))
        with patch.object(self.agent.gateway,'generate',generate),self.assertRaises(PermissionError):
            await self.agent._propose_completion_audit()
        self.assertFalse((self.root/'forbidden.txt').exists())
        schema=received[0]
        self.assertEqual(len(schema['oneOf']),1)
        checks=schema['oneOf'][0]['properties']['args']['properties']['checks']['items']['anyOf']
        self.assertFalse(any(c['properties']['kind']['const']=='command' for c in checks))

    async def test_unknown_interrupted_command_remains_fenced_in_the_independent_check(self):
        argv=[sys.executable,'-c','from pathlib import Path;Path("forbidden.txt").write_text("1")']
        command={'kind':'command','criterion':self.criterion,'argv':argv}
        env_path=str(Path(sys.executable).parent)+os.pathsep+os.environ.get('PATH','')
        self.agent.state['interrupted_processes']=[self.agent._command_identity(argv,self.root,env_path)]
        generate=AsyncMock(return_value=json.dumps(call('verify',checks=[command])))
        await self.play(self.initial(self.correct,self.check),generate,steps=6)
        self.assertFalse(self.agent.state['request_audit']['passed'])
        self.assertFalse((self.root/'forbidden.txt').exists())
        self.assertFalse(self.agent.state['verified'])
        self.agent._review_completion.assert_not_awaited()

    async def test_blocked_completion_and_explicit_disabled_policy_do_not_request_extra_model_calls(self):
        generate=AsyncMock(side_effect=AssertionError('Unexpected audit'))
        self.assertEqual(await self.play([self.plan,call('finish',status='blocked',message='Missing input')],generate), 'Missing input')
        self.assertEqual(self.agent.state['status'],'blocked')
        self.agent.state.update(messages=[],criteria=[],verified=[],plan=[],iteration=0,status='running')
        self.agent.policy=replace(self.agent.policy,request_audit=False)
        replies=self.initial(self.wrong,self.literal)
        self.assertEqual(await self.play(replies,generate),'Premature proposal')
        generate.assert_not_awaited()

    def test_request_audit_configuration_is_explicit(self):
        for value,expected in [('0',False),('1',True)]:
            with self.subTest(value=value),patch.dict(os.environ,{'AURORA_REQUEST_AUDIT':value}):
                self.assertIs(RuntimePolicy.from_env().request_audit,expected)
        for value in ['2','true','-1']:
            with self.subTest(value=value),patch.dict(os.environ,{'AURORA_REQUEST_AUDIT':value}),self.assertRaises(ValueError):
                RuntimePolicy.from_env()
