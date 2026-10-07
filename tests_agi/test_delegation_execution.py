"""Recorded role execution: real worker loops/files, substituted model replies."""
from dataclasses import replace
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import AsyncMock, patch

from agi_core.context import create_agent
from agi_core.mission_agent import AutonomousMissionAgent, _stable_observation
from agi_core.llm_gateway import LLMGateway
from agi_core.mission_protocol import tool_response_schema
from agi_core.mission_store import MissionStore


class DelegationExecution(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        folder=tempfile.TemporaryDirectory();self.addCleanup(folder.cleanup)
        self.root=Path(folder.name)
        environment=patch.dict(os.environ,{'AURORA_DATA_DIR':str(self.root/'runtime')})
        environment.start();self.addCleanup(environment.stop)
        create_agent('NamedRole','Use the actual CSV input','fixture:local','AUTONOMOUS','execution-test')
        self.agent=AutonomousMissionAgent('execution','Use NamedRole to compute actual CSV aggregates',str(self.root),'fixture:local')
        self.agent.policy=replace(self.agent.policy,request_audit=False,recovery_attempts=0)
        self.agent.state['plan']=['Delegate and verify']
        self.agent._emit=AsyncMock()
        (self.root/'input.csv').write_text('label,value\nfirst,10\nsecond,20\nthird,-5\n')
        self.check={'kind':'csv_json','path':'input.csv','json_path':'summary.json','row_field':'rows','sum_fields':{'sum':'value'}}

    def child_replies(self, *, correct=True):
        criterion='Saved aggregates match the actual input'
        replies=[{'tool':'set_plan','args':{'steps':['Compute and verify'],'criteria':[criterion]}},
                 {'tool':'inspect_csv','args':{'path':'input.csv'}},
                 {'tool':'write_file','args':{'path':'summary.json','content':json.dumps({'rows':3,'sum':25 if correct else 26})}},
                 {'tool':'verify','args':{'checks':[{**self.check,'criterion':criterion}]}},
                 *[{'tool':'finish','args':{'message':'Actual worker result'}} for _ in range(3)]]
        streams={};contexts=[]
        async def stream(child,messages):
            contexts.append(child.additional_context)
            iterator=streams.setdefault(id(child),iter(replies))
            yield json.dumps(next(iterator))
        return patch.object(AutonomousMissionAgent,'_chat_chunks',stream),contexts

    async def prove(self, **fields):
        return await self.agent.tools.execute('verify',{'checks':[{'kind':'delegation',**fields}]})

    async def test_context_override_is_inherited_by_generic_and_named_workers(self):
        parent = AutonomousMissionAgent('context','Inspect',str(self.root),'fixture:local',context_tokens=8192)
        seen = []
        async def observe(child):
            seen.append((child.context_tokens,child.gateway.context_tokens))
            return {'status':'fixture'}
        with patch.object(parent,'_worker_report',side_effect=observe):
            await parent._run_sub_agent('Inspect only')
            await parent._spawn_task('Inspect only','NamedRole')
        self.assertEqual(seen,[(8192,8192),(8192,8192)])

    async def test_definition_and_generic_worker_do_not_prove_named_role_execution(self):
        definition=await self.agent.tools.execute('verify',{'checks':[{'kind':'agent','name':'NamedRole'}]})
        self.assertTrue(definition['passed'])
        self.assertFalse((await self.prove(agent='NamedRole'))['passed'])
        scripted,contexts=self.child_replies()
        review=AsyncMock(return_value={'approved':True,'unmet':[],'reason':'Substituted review'})
        with scripted,patch.object(AutonomousMissionAgent,'_review_completion',review):
            generic=await self.agent._execute('spawn_agent',{'task':'Compute summary.json','checks':[self.check]})
            self.assertTrue(generic['passed'])
            self.assertFalse((await self.prove(agent='NamedRole'))['passed'])
            self.assertTrue((await self.prove(agent=''))['passed'])
            named=await self.agent._execute('spawn_agent',{'agent':'NamedRole','task':'Compute summary.json','checks':[self.check]})
            self.assertTrue(named['passed'])
            proof=await self.prove(agent='NamedRole',tasks=['Compute summary.json'],execution_id=named['execution_id'])
            self.assertTrue(proof['passed'])
            self.assertEqual(proof['checks'][0]['observed'][0]['worker_statuses'],['completed'])
            self.assertTrue(any('Reusable role, subordinate to this task: Use the actual CSV input' in c for c in contexts))
            self.assertFalse((await self.prove(agent='NamedRole',tasks=['An unrelated task']))['passed'])
            self.assertFalse((await self.prove(agent='NamedRole',execution_id='invented'))['passed'])
            reused=await self.agent._execute('spawn_agent',{'agent':'NamedRole','task':'Compute summary.json','checks':[self.check]})
            self.assertTrue(reused['reused'])
            self.assertEqual(reused['execution_id'],named['execution_id'])
            self.assertEqual(len(self.agent.state['delegation_records']),2)
            self.assertEqual(proof,await self.prove(agent='NamedRole',tasks=['Compute summary.json'],execution_id=named['execution_id']))

    async def test_failed_actual_worker_and_failed_acceptance_do_not_prove_execution(self):
        scripted,_=self.child_replies(correct=False)
        with scripted,self.assertRaisesRegex(RuntimeError,'unverified completion'):
            await self.agent._execute('spawn_agent',{'agent':'NamedRole','task':'Compute summary.json','checks':[self.check]})
        self.assertFalse(self.agent.state['delegation_records'])
        self.assertFalse((await self.prove(agent='NamedRole'))['passed'])

    async def test_command_acceptance_is_not_replayed_by_proof_or_checkpoint_reload(self):
        command={'kind':'command','argv':[sys.executable,'-c',
            'from pathlib import Path; p=Path("counter.txt");p.write_text(str(int(p.read_text())+1) if p.exists() else "1")']}
        worker=AsyncMock(return_value={'status':'completed','report':'Substituted worker','goal':'Inspect'})
        with patch.object(self.agent,'_spawn_task',worker):
            result=await self.agent._execute('spawn_agent',{'agent':'NamedRole','task':'Inspect','checks':[command]})
            self.assertTrue(result['passed'])
            self.assertTrue((await self.prove(agent='NamedRole'))['passed'])
            self.assertTrue((await self.prove(agent='NamedRole'))['passed'])
            store=MissionStore(self.root/'missions.sqlite3')
            item,_=store.create({'request':self.agent.request_text,'workspace':str(self.root),'model':self.agent.model,'permissions':'AUTONOMOUS'})
            store.save_checkpoint(item['id'],self.agent.state)
            self.agent.state=MissionStore(self.root/'missions.sqlite3').checkpoint(item['id'])
            self.assertTrue((await self.prove(agent='NamedRole'))['passed'])
        self.assertEqual(worker.await_count,1)
        self.assertEqual((self.root/'counter.txt').read_text(),'1')

    async def test_unknown_role_and_circular_delegation_check_are_rejected_without_launch(self):
        before=(self.root/'input.csv').read_bytes()
        with self.assertRaisesRegex(ValueError,'not found'):
            await self.agent._execute('spawn_agent',{'agent':'Missing','task':'Compute','checks':[self.check]})
        with patch.object(self.agent,'_spawn_task',AsyncMock()) as worker,self.assertRaisesRegex(ValueError,'after spawn_agent'):
            await self.agent._execute('spawn_agent',{'agent':'NamedRole','task':'Compute','checks':[{'kind':'delegation','agent':'NamedRole'}]})
        worker.assert_not_awaited()
        self.assertFalse(self.agent.state['delegation_records'])
        self.assertEqual((self.root/'input.csv').read_bytes(),before)

    async def test_legacy_receipt_is_observed_without_replaying_or_accepting_definition_only(self):
        receipt={'id':'old_real_execution','tool':'spawn_agent','ok':True,'result':{
            'agent':'NamedRole','passed':True,'workers':[{'task':'Compute','status':'completed'}],
            'verification':{'checks':[]}}}
        self.agent.state['evidence'].append(receipt)
        self.agent.state.pop('delegation_records')
        with patch.object(self.agent,'_spawn_task',AsyncMock(side_effect=AssertionError('Replay'))) as worker:
            proof=await self.prove(agent='NamedRole')
            self.assertTrue(proof['passed'])
            self.assertEqual(proof['checks'][0]['observed'][0]['execution_id'],'legacy_old_real_execution')
            receipt['ok']=False
            self.assertFalse((await self.prove(agent='NamedRole'))['passed'])
        worker.assert_not_awaited()

    async def test_request_audit_rejects_generic_worker_then_accepts_actual_requested_role(self):
        self.agent.policy=replace(self.agent.policy,request_audit=True)
        self.agent.request_text='Use NamedRole with spawn_agent to compute input.csv into summary.json and prove the actual named-role execution and source aggregates.'
        data_criterion='Saved data matches the source'
        role_criterion='The requested NamedRole actually executed the delegated task'
        data_check={**self.check,'criterion':data_criterion}
        role_check={'kind':'delegation','agent':'NamedRole','criterion':role_criterion}
        replies=iter([
            {'tool':'set_plan','args':{'steps':['Delegate and verify'],'criteria':[data_criterion,role_criterion],'required_tools':['spawn_agent']}},
            {'tool':'spawn_agent','args':{'task':'Compute summary.json','checks':[{**self.check,'criterion':role_criterion}]}},
            {'tool':'verify','args':{'checks':[data_check]}},
            {'tool':'finish','args':{'message':'Generic worker claimed sufficient'}},
            {'tool':'spawn_agent','args':{'agent':'NamedRole','task':'Compute summary.json','checks':[{**self.check,'criterion':role_criterion}]}},
            {'tool':'finish','args':{'message':'Named role actually ran'}},
            {'tool':'finish','args':{'message':'Audited named role and data'}}])
        async def parent_stream(messages):yield json.dumps(next(replies))
        payloads=[]
        async def generate(gateway,system,payload,model,**kwargs):
            value=json.loads(payload)
            if role_criterion in value['criteria']:
                payloads.append(value)
                return json.dumps({'tool':'verify','args':{'checks':[data_check,role_check]}})
            return json.dumps({'tool':'verify','args':{'checks':[{**self.check,'criterion':value['criteria'][0]}]}})
        children,_=self.child_replies()
        review=AsyncMock(return_value={'approved':True,'unmet':[],'reason':'Substituted review'})
        with children,patch.object(self.agent,'_chat_chunks',parent_stream),patch.object(LLMGateway,'generate',generate), \
             patch.object(AutonomousMissionAgent,'_review_completion',review):
            self.assertEqual(await self.agent.run(),'Audited named role and data')
        self.assertEqual(self.agent.state['status'],'completed')
        self.assertEqual([r['agent'] for r in self.agent.state['delegation_records']],['','NamedRole'])
        self.assertEqual([p['delegations'][-1]['agent'] for p in payloads],['','NamedRole'])
        outcomes=[e.args[1]['passed'] for e in self.agent._emit.call_args_list if e.args[0]=='request_audit_result' and not e.args[1].get('worker')]
        self.assertEqual(outcomes,[False,True])
        self.assertEqual(json.loads((self.root/'summary.json').read_text()),{'rows':3,'sum':25})

    def test_decoding_offers_execution_proof_only_after_delegation(self):
        schema=tool_response_schema(['Actual execution'])
        for branch in schema['oneOf']:
            tool=branch['properties']['tool']['const']
            if tool not in {'verify','spawn_agent'}:continue
            checks=branch['properties']['args']['properties']['checks']['items']['anyOf']
            self.assertEqual(any(c['properties']['kind']['const']=='delegation' for c in checks),tool=='verify')

    def test_execution_identity_is_not_new_result_progress(self):
        first={'passed':True,'execution_id':'first-run','agent':'NamedRole','workers':[{'status':'completed'}]}
        second={**first,'execution_id':'second-run'}
        self.assertEqual(_stable_observation(first),_stable_observation(second))
        self.assertNotEqual(_stable_observation(first),_stable_observation({**second,'passed':False}))

    async def test_real_worker_receives_output_bindings_without_parent_delegation_criterion(self):
        parent_criterion='The parent delegation has completed using the named role'
        self.agent.state['criteria']=[parent_criterion]
        acceptance={**self.check,'criterion':parent_criterion}
        children,contexts=self.child_replies()
        review=AsyncMock(return_value={'approved':True,'unmet':[],'reason':'Substituted review'})
        with children,patch.object(AutonomousMissionAgent,'_review_completion',review):
            result=await self.agent._execute('spawn_agent',{'agent':'NamedRole','task':'Compute summary.json','checks':[acceptance]})
        self.assertTrue(result['passed'])
        self.assertTrue(contexts)
        self.assertTrue(all(parent_criterion not in context for context in contexts))
        self.assertTrue(all('"row_field": "rows"' in context and '"sum_fields": {"sum": "value"}' in context for context in contexts))
        self.assertEqual(acceptance['criterion'],parent_criterion)

    async def test_worker_rejects_parent_execution_proof_before_other_check_effects(self):
        child=AutonomousMissionAgent('worker','Compute the saved aggregates',str(self.root),'fixture:local',depth=1)
        child.state.update(plan=['Compute'],criteria=['Saved aggregates match the input'])
        forbidden={'kind':'delegation','agent':'NamedRole','criterion':child.state['criteria'][0]}
        command={'kind':'command','argv':[sys.executable,'-c','from pathlib import Path;Path("unexpected.txt").write_text("1")'],
                 'criterion':child.state['criteria'][0]}
        with patch.object(child,'_run_process',AsyncMock()) as process,self.assertRaisesRegex(PermissionError,'Only the parent'):
            await child._execute('verify',{'checks':[command,forbidden]})
        process.assert_not_awaited()
        self.assertFalse((self.root/'unexpected.txt').exists())

    async def test_worker_audit_decoding_and_preflight_exclude_its_own_delegation(self):
        child=AutonomousMissionAgent('worker','Compute the saved aggregates',str(self.root),'fixture:local',depth=1)
        child.state.update(plan=['Compute'],criteria=['Saved aggregates match the input'])
        schemas=[]
        async def generate(system,payload,model,**kwargs):
            schemas.append(kwargs['response_format'])
            self.assertIn('Parent criterion labels',system)
            return json.dumps({'tool':'verify','args':{'checks':[{'kind':'delegation','agent':'NamedRole','criterion':child.state['criteria'][0]}]}})
        with patch.object(child.gateway,'generate',generate),patch.object(child,'_emit',AsyncMock()), \
             self.assertRaisesRegex(PermissionError,'Worker audit'):
            await child._propose_completion_audit()
        checks=schemas[0]['oneOf'][0]['properties']['args']['properties']['checks']['items']['anyOf']
        self.assertFalse(any(c['properties']['kind']['const']=='delegation' for c in checks))
        allowed=tool_response_schema(child.state['criteria'],allow_delegation_checks=False)
        verify=next(b for b in allowed['oneOf'] if b['properties']['tool']['const']=='verify')
        checks=verify['properties']['args']['properties']['checks']['items']['anyOf']
        self.assertFalse(any(c['properties']['kind']['const']=='delegation' for c in checks))
