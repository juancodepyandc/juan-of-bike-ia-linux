"""Parent acceptance checks over real files/processes; no model inference."""
import asyncio
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import AsyncMock, patch

from agi_core.context import create_agent
from agi_core.mission_agent import AutonomousMissionAgent
from agi_core.runtime_policy import RuntimePolicy
from agi_core.mission_protocol import tool_response_schema


class DelegationContracts(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.root = Path(self.folder.name)
        self.agent = AutonomousMissionAgent('contract','Audit the data',str(self.root),'fixture:local')
        self.agent._emit = AsyncMock()
        self.agent.state['plan'] = ['Delegate and verify the saved result']
        self.source = self.root/'input.csv'
        self.source.write_bytes(b'label,value\r\n"first, row",10\r\nsecond,20\r\nthird,-5\r\n')
        self.check = {'kind':'csv_json','path':'input.csv','json_path':'summary.json',
                      'row_field':'rows','sum_fields':{'sum':'value'}}

    def result_file(self, value):
        (self.root/'summary.json').write_text(json.dumps(value),encoding='utf-8')

    async def verify(self, check=None):
        return await self.agent.tools.execute('verify',{'checks':[check or self.check]})

    def test_shared_check_schemas_require_each_criterion_once_in_both_tools(self):
        for criterion in ('Criterion A','Criterion B'):
            schema = tool_response_schema([criterion])
            for branch in schema['oneOf']:
                if branch['properties']['tool']['const'] not in {'spawn_agent','verify'}:
                    continue
                args = branch['properties']['args']
                self.assertIn('checks',args['required'])
                for check in args['properties']['checks']['items']['anyOf']:
                    self.assertEqual(check['required'].count('criterion'),1)
                    self.assertEqual(check['properties']['criterion']['enum'],[criterion])

    async def test_declared_delegation_cannot_be_replaced_by_an_unrelated_role_check(self):
        self.result_file({'rows':3,'sum':25})
        check = {**self.check,'criterion':'Result exists'}
        replies = iter([
            {'tool':'set_plan','args':{'steps':['Delegate'], 'criteria':['Result exists'],'required_tools':['spawn_agent']}},
            {'tool':'spawn_agent','args':{'task':'Audit'}},  # Rejected before launch.
            {'tool':'verify','args':{'checks':[check]}},
            *[{'tool':'finish','args':{'message':'Fictional delegation'}} for _ in range(3)]])
        received = []
        async def chat(messages):
            received.append(messages)
            yield json.dumps(next(replies))
        with patch.object(self.agent,'_chat_chunks',chat), patch.object(self.agent,'_spawn_task',AsyncMock()) as worker, \
             patch.object(self.agent,'_review_completion',AsyncMock(return_value={'approved':True,'unmet':[],'reason':'Model substitute'})) as review:
            self.assertIsNone(await self.agent.run())
        worker.assert_not_awaited()
        review.assert_not_awaited()
        self.assertEqual(self.agent.state['status'],'failed')
        self.assertNotIn('spawn_agent',self.agent.state['executed_tools'])
        progress = received[3][-1]['content']
        self.assertIn('"pending_tools": ["spawn_agent"]',progress)
        self.assertNotIn('Propose finish',progress)

    def test_action_variants_are_complete_and_mutually_exclusive(self):
        schema = tool_response_schema(['Correct data'])
        for name,choices in (('run_command',{'argv','command'}),('spawn_agent',{'task','tasks'})):
            branches = [b['properties']['args'] for b in schema['oneOf'] if b['properties']['tool']['const']==name]
            self.assertEqual(len(branches),2)
            for args in branches:
                self.assertNotIn('oneOf',args)
                present = choices&args['properties'].keys()
                self.assertEqual(len(present),1)
                self.assertTrue(present<=set(args['required']))
        plan = next(b['properties']['args'] for b in schema['oneOf'] if b['properties']['tool']['const']=='set_plan')
        self.assertIn('required_tools',plan['required'])

    def test_decoding_requires_a_concrete_json_or_text_expectation(self):
        schema = tool_response_schema(['Measured output'])
        for action in schema['oneOf']:
            if action['properties']['tool']['const'] not in {'verify','spawn_agent'}:
                continue
            checks = action['properties']['args']['properties']['checks']['items']['anyOf']
            for kind,fields in (('json',{'equals','keys','types'}),('text',{'equals','contains'})):
                branches = [c for c in checks if c['properties']['kind']['const']==kind]
                self.assertTrue(branches)
                for branch in branches:
                    self.assertTrue(fields & set(branch['required']))
                    self.assertNotIn('anyOf',branch)
                    self.assertFalse(branch['additionalProperties'])

    async def test_named_worker_receives_contract_without_replacing_task(self):
        task = 'Count all data rows'
        seen = []
        async def child_run(child, *, worker=False):
            seen.append(child)
            child.state['status'] = 'blocked'
            return 'No saved output yet'
        with patch.dict(os.environ,{'AURORA_DATA_DIR':str(self.root/'runtime')}):
            create_agent('reader','Read only','fixture:local','SAFE','contract')
            with patch.object(AutonomousMissionAgent,'run',child_run):
                await self.agent._execute('spawn_agent',{'task':task,'agent':'reader','checks':[self.check]})
        self.assertEqual(seen[0].request_text,task)
        self.assertEqual(seen[0].permissions,'SAFE')
        self.assertIn('"json_path": "summary.json"',seen[0].additional_context)
        self.assertIn('Read only',seen[0].additional_context)

    async def test_identical_or_conflicting_skill_creation_preserves_validations_and_bytes(self):
        skill_path = '.aurora/skills/Audit/SKILL.md'
        criterion = 'Skill exists'
        args = {'name':'Audit','description':'CSV audit','instructions':'Première\r\nligne'}
        check = {'kind':'file','path':skill_path,'criterion':criterion}
        replies = iter([
            {'tool':'set_plan','args':{'steps':['Create a skill'],'criteria':[criterion]}},
            {'tool':'create_skill','args':args},
            {'tool':'verify','args':{'checks':[check]}},
            {'tool':'create_skill','args':args},
            {'tool':'create_skill','args':{**args,'instructions':'Different instructions'}},
            {'tool':'finish','args':{'message':'Original skill preserved'}}])
        snapshots = []
        async def chat(messages):
            if (self.root/skill_path).exists():
                snapshots.append(((self.root/skill_path).read_bytes(),(self.root/skill_path).stat().st_mtime_ns))
            yield json.dumps(next(replies))
        with patch.object(self.agent,'_chat_chunks',chat), \
             patch.object(self.agent,'_review_completion',AsyncMock(return_value={'approved':True,'unmet':[],'reason':'Model substitute'})):
            self.assertEqual(await self.agent.run(),'Original skill preserved')
        self.assertTrue(all(s==snapshots[0] for s in snapshots))
        self.assertIn('Première\r\nligne'.encode(),snapshots[0][0])
        self.assertNotIn(b'\r\r\n',snapshots[0][0])
        events = [e for e in self.agent.state['evidence'] if e['tool']=='create_skill']
        self.assertEqual([e['ok'] for e in events],[True,True,False])
        self.assertEqual([e['result']['changed'] for e in events],[True,False,False])
        self.assertEqual(self.agent.state['last_change'],2)
        self.assertEqual(self.agent.state['verified'],[criterion])

    async def test_reusing_saved_role_never_overwrites_or_changes_the_registry(self):
        args = {'name':'reader','role':'Inspect rows'}
        with patch.dict(os.environ,{'AURORA_DATA_DIR':str(self.root/'runtime')}):
            first = await self.agent._execute('create_agent',args)
            registry = self.root/'runtime/dynamic_agents.json'
            before = (registry.read_bytes(),registry.stat().st_mtime_ns)
            second = await self.agent._execute('create_agent',args)
            conflict = await self.agent._execute('create_agent',{**args,'role':'Overwrite'})
            self.assertEqual((registry.read_bytes(),registry.stat().st_mtime_ns),before)
        self.assertTrue(first['changed'])
        self.assertTrue(second['passed'])
        self.assertFalse(second['changed'])
        self.assertFalse(conflict['passed'] or conflict['changed'])

    async def test_parent_inference_retains_acceptance_facts_before_large_worker_reports(self):
        self.agent.policy = RuntimePolicy(output_chars=2000)
        check = {**self.check,'criterion':'Measured result'}
        replies = iter([
            {'tool':'set_plan','args':{'steps':['Delegate'],'criteria':['Measured result']}},
            {'tool':'spawn_agent','args':{'task':'Audit','checks':[check]}},
            {'tool':'finish','args':{'message':'Measured result'}}])
        received = []
        async def chat(messages):
            received.append(messages)
            yield json.dumps(next(replies))
        async def worker(task, name='', *, acceptance_checks=()):
            self.result_file({'rows':3,'sum':25})
            return {'status':'completed','report':'large data '*20000,'goal':task}
        with patch.object(self.agent,'_chat_chunks',chat), patch.object(self.agent,'_spawn_task',worker), \
             patch.object(self.agent,'_review_completion',AsyncMock(return_value={'approved':True,'unmet':[],'reason':'Model substitute'})):
            self.assertEqual(await self.agent.run(),'Measured result')
        latest = received[-1][-1]['content']
        self.assertIn('"verification"',latest)
        self.assertIn('"expected": {"rows": 3, "sum": 25}',latest)
        self.assertIn('[truncated;',latest)
        self.assertLessEqual(len(latest),self.agent.policy.output_chars+300)

    async def test_csv_output_is_measured_from_source_not_guessed_constants(self):
        before = self.source.read_bytes()
        for value,expected in [({'rows':3,'sum':25},True),({'rows':2,'sum':15},False),
                               ({'rows':3,'sum':True},False),({'rows':3.0,'sum':25},False),
                               ({'rows':3,'sum':25,'extra':1},False)]:
            with self.subTest(value=value):
                self.result_file(value)
                result = await self.verify()
                self.assertEqual(result['passed'],expected)
                self.assertEqual(result['checks'][0]['expected'],{'rows':3,'sum':25})
        self.assertEqual(self.source.read_bytes(),before)

    async def test_csv_field_mapping_bom_multiline_and_multiple_integer_columns(self):
        raw = b'\xef\xbb\xbflabel;amount;other\r\n"two\r\nlines";12;3\r\nx;-4;5\r\n'
        self.source.write_bytes(raw)
        self.result_file({'n':2,'total':8,'bonus':8})
        check = {**self.check,'row_field':'n','sum_fields':{'total':'amount','bonus':'other'},'delimiter':';',
                 'source_sha256':hashlib.sha256(raw).hexdigest()}
        self.assertTrue((await self.verify(check))['passed'])
        self.assertFalse((await self.verify({**check,'source_sha256':'unobserved'}))['passed'])
        self.assertEqual(self.source.read_bytes(),raw)

    async def test_csv_invalid_data_or_output_never_passes(self):
        self.result_file({'rows':3,'sum':25})
        for raw in (b'label,value,value\nx,1,2\n',b'label,value\nx,wrong\n',b'label,value\nx,1,extra\n'):
            with self.subTest(raw=raw):
                self.source.write_bytes(raw)
                self.assertFalse((await self.verify())['passed'])
        self.source.write_bytes(b'value\n1\n')
        for raw in ('{"rows":1,"sum":1,"sum":2}','{"rows":1,"sum":NaN}','{"rows":1,"sum":1e10000}'):
            with self.subTest(raw=raw):
                (self.root/'summary.json').write_text(raw,encoding='utf-8')
                self.assertFalse((await self.verify())['passed'])

    async def test_csv_checks_are_bounded_and_confined_under_safe_permissions(self):
        self.agent.permissions = 'SAFE'
        self.result_file({'rows':3,'sum':25})
        self.assertTrue((await self.verify())['passed'])
        self.assertFalse((await self.verify({**self.check,'json_path':'../outside.json'}))['passed'])
        self.agent.policy = RuntimePolicy(output_chars=2)
        self.assertFalse((await self.verify())['passed'])

    async def test_contract_is_validated_before_any_worker_starts(self):
        worker = AsyncMock()
        invalid = [[],[{**self.check,'json_path':3}],[{**self.check,'row_field':'sum'}],
                   [{**self.check,'sum_fields':{'sum':4}}],[{'kind':'command','argv':[]}],
                   [{'kind':'text','path':'summary.json'}],[{'kind':'file','path':'summary.json','unexpected':1}]]
        with patch.object(self.agent,'_spawn_task',worker):
            with self.assertRaises(ValueError):
                await self.agent._execute('spawn_agent',{'task':'Audit'})
            for checks in invalid:
                with self.subTest(checks=checks), self.assertRaises(ValueError):
                    await self.agent._execute('spawn_agent',{'task':'Audit','checks':checks})
        worker.assert_not_awaited()

    async def test_completed_worker_with_wrong_csv_fails_parent_acceptance(self):
        async def bad_worker(task, name='', *, acceptance_checks=()):
            # Reproduce the actual observed bug in a real Python process.
            code = "import csv,json; r=csv.DictReader(open('input.csv',newline='')); next(r); v=list(r); json.dump({'rows':len(v),'sum':sum(int(x['value']) for x in v)},open('summary.json','w'))"
            subprocess.run([sys.executable,'-c',code],cwd=self.root,check=True,capture_output=True)
            return {'status':'completed','goal':task,'report':'Claimed correct: 2 rows, sum 15'}
        with patch.object(self.agent,'_spawn_task',bad_worker):
            result = await self.agent._execute('spawn_agent',{'task':'Audit','checks':[self.check]})
        self.assertFalse(result['passed'])
        self.assertEqual(result['workers'][0]['status'],'completed')
        self.assertEqual(result['verification']['checks'][0]['expected'],{'rows':3,'sum':25})
        self.assertEqual(result['verification']['checks'][0]['observed'],{'rows':2,'sum':15})
        self.assertFalse(self.agent.state['delegations'])

    async def test_accepted_pure_delegation_is_reused_until_input_or_output_changes(self):
        calls = []
        async def worker(task, name='', *, acceptance_checks=()):
            calls.append(task)
            code = "import csv,json; v=list(csv.DictReader(open('input.csv',newline=''))); json.dump({'rows':len(v),'sum':sum(int(x['value']) for x in v)},open('summary.json','w'))"
            subprocess.run([sys.executable,'-c',code],cwd=self.root,check=True,capture_output=True)
            return {'status':'completed','goal':task,'report':'Measured result'}
        args = {'task':'Audit','checks':[self.check]}
        with patch.object(self.agent,'_spawn_task',worker):
            first = await self.agent._execute('spawn_agent',args)
            self.assertTrue(first['passed'])
            before = (self.root/'summary.json').stat().st_mtime_ns
            second = await self.agent._execute('spawn_agent',args)
            self.assertTrue(second['reused'])
            self.assertFalse(second['changed'])
            self.assertEqual((self.root/'summary.json').stat().st_mtime_ns,before)
            self.assertEqual(len(calls),1)
            with self.source.open('ab') as stream:
                stream.write(b'fourth,2\r\n')
            third = await self.agent._execute('spawn_agent',args)
            self.assertFalse(third['reused'])
            self.assertEqual(third['verification']['checks'][0]['observed'],{'rows':4,'sum':27})
            self.assertEqual(len(calls),2)

    async def test_delegation_command_checks_are_never_automatically_reused(self):
        worker = AsyncMock(return_value={'status':'completed','report':'Observed','goal':'Inspect'})
        args = {'task':'Inspect','checks':[{'kind':'command','argv':[sys.executable,'-c','print("actual")'],'contains':'actual'}]}
        with patch.object(self.agent,'_spawn_task',worker):
            first = await self.agent._execute('spawn_agent',args)
            second = await self.agent._execute('spawn_agent',args)
        self.assertTrue(first['passed'] and second['passed'])
        self.assertFalse(second['reused'])
        self.assertEqual(worker.await_count,2)

    async def test_saved_agent_check_observes_current_definition(self):
        with patch.dict(os.environ,{'AURORA_DATA_DIR':str(self.root/'runtime')}):
            check = {'kind':'agent','name':'reader'}
            self.assertFalse((await self.verify(check))['passed'])
            create_agent('reader','Read data','fixture:local','SAFE','contract')
            first = await self.verify(check)
            self.assertTrue(first['passed'])
            registry = self.root/'runtime/dynamic_agents.json'
            data = json.loads(registry.read_text(encoding='utf-8'))
            data['agents'][0]['role'] = 'Changed role'
            registry.write_text(json.dumps(data),encoding='utf-8')
            second = await self.verify(check)
            self.assertNotEqual(first['checks'][0]['observed_sha256'],second['checks'][0]['observed_sha256'])

    async def test_parent_uses_acceptance_checks_even_when_model_review_would_approve(self):
        criterion = 'Saved aggregates match the source'
        check = {**self.check,'criterion':criterion}
        replies = iter([
            {'tool':'set_plan','args':{'steps':['Delegate'], 'criteria':[criterion]}},
            {'tool':'spawn_agent','args':{'task':'Audit to summary.json','checks':[check]}},
            {'tool':'finish','args':{'message':'Wrong claimed result'}},
            {'tool':'write_file','args':{'path':'summary.json','content':'{"rows":3,"sum":25}'}},
            {'tool':'verify','args':{'checks':[check]}},
            {'tool':'finish','args':{'message':'Corrected and measured result'}}])
        async def chat(messages):
            yield json.dumps(next(replies))
        async def worker(task, name='', *, acceptance_checks=()):
            self.result_file({'rows':2,'sum':15})
            return {'status':'completed','report':'Wrong but confident','goal':task}
        with patch.object(self.agent,'_chat_chunks',chat), patch.object(self.agent,'_spawn_task',worker), \
             patch.object(self.agent,'_review_completion',AsyncMock(return_value={'approved':True,'unmet':[],'reason':'Model substitute'})) as review:
            self.assertEqual(await self.agent.run(),'Corrected and measured result')
        self.assertEqual(review.await_count,1)
        self.assertEqual(self.agent.state['status'],'completed')
        self.assertIn(check,self.agent.state['output_checks'])

    async def test_successful_delegation_validation_marks_criterion_after_worker_effects(self):
        criterion = 'Measured result'
        check = {**self.check,'criterion':criterion}
        replies = iter([
            {'tool':'set_plan','args':{'steps':['Delegate'], 'criteria':[criterion],
                                      'required_tools':['spawn_agent','inspect_csv']}},
            {'tool':'spawn_agent','args':{'task':'Audit to summary.json','checks':[check]}},
            {'tool':'finish','args':{'message':'Measured delegated result'}}])
        async def chat(messages):
            yield json.dumps(next(replies))
        async def worker(task, name='', *, acceptance_checks=()):
            self.result_file({'rows':3,'sum':25})
            return {'status':'completed','report':'Measured','goal':task,'executed_tools':['inspect_csv']}
        with patch.object(self.agent,'_chat_chunks',chat), patch.object(self.agent,'_spawn_task',worker), \
             patch.object(self.agent,'_review_completion',AsyncMock(return_value={'approved':True,'unmet':[],'reason':'Model substitute'})):
            self.assertEqual(await self.agent.run(),'Measured delegated result')
        self.assertEqual(self.agent.state['verified'],[criterion])
        self.assertEqual(self.agent.state['last_change'],self.agent.state['last_verify'])
        self.assertEqual(self.agent.state['output_checks'],[check])
        self.assertEqual(set(self.agent.state['executed_tools']),{'spawn_agent','inspect_csv'})
