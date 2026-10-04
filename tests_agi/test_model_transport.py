"""Actual HTTP streaming against a temporary Ollama protocol fixture, no inference."""
import json
import tempfile
from pathlib import Path
import unittest
from unittest.mock import AsyncMock, patch
from aiohttp import web
from agi_core.llm_gateway import LLMGateway
from agi_core.mission_agent import AutonomousMissionAgent


class ModelTransportTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.received,self.lines = [],[]
        async def chat(request):
            self.received.append(await request.json())
            response = web.StreamResponse(headers={'Content-Type':'application/x-ndjson'})
            await response.prepare(request)
            for line in self.lines:
                await response.write((json.dumps(line)+'\n').encode())
            await response.write_eof()
            return response
        app = web.Application()
        app.router.add_post('/api/chat',chat)
        async def running_models(request):
            return web.json_response({'models':[
                {'name':'other:local','context_length':8192}, {'name':'fixture:local','context_length':4096}]})
        app.router.add_get('/api/ps',running_models)
        self.runner = web.AppRunner(app)
        await self.runner.setup()
        site = web.TCPSite(self.runner,'127.0.0.1',0)
        await site.start()
        port = site._server.sockets[0].getsockname()[1]
        self.gateway = LLMGateway(f'http://127.0.0.1:{port}')

    async def asyncTearDown(self):
        await self.runner.cleanup()

    async def test_native_options_and_measured_usage_cross_real_http(self):
        self.lines = [{'message':{'content':'Observed answer'}},
                      {'done':True,'eval_count':10,'eval_duration':500000000,'prompt_eval_count':23}]
        metrics = []
        with patch.dict('os.environ',{'AURORA_MODEL_OPTIONS':'{}'}):
            chunks = [c async for c in self.gateway.chat_chunks([{'role':'user','content':'Test'}], 'fixture:local',on_metrics=metrics.append)]
        self.assertEqual(''.join(chunks),'Observed answer')
        self.assertEqual(self.received[0]['options'],{})
        self.assertNotIn('format',self.received[0])
        self.assertEqual(metrics[0]['tokens_per_second'],20)
        self.assertEqual(metrics[0]['prompt_eval_count'],23)

    async def test_mission_action_uses_structured_output_over_real_transport(self):
        self.lines = [{'message':{'content':'{"tool":"finish","args":{"message":"Done"}}'}}, {'done':True}]
        with tempfile.TemporaryDirectory() as workspace:
            agent = AutonomousMissionAgent('test','Answer the request',workspace,'fixture:local')
            agent.gateway = self.gateway
            response = ''.join([c async for c in agent._chat_chunks([{'role':'user','content':'Test'}])])
        self.assertEqual(json.loads(response)['tool'],'finish')
        schema = self.received[0]['format']
        for branch in schema['oneOf']:
            self.assertEqual(set(branch['required']),{'tool','args'})
            self.assertEqual(branch['properties']['args']['type'],'object')
            self.assertFalse(branch['additionalProperties'])
            self.assertFalse(branch['properties']['args']['additionalProperties'])

    async def test_decoding_schema_uses_current_criteria_and_filters_disallowed_worker_tools(self):
        self.lines = [{'message':{'content':'{"tool":"finish","args":{"message":"Done"}}'}},{'done':True}]
        with tempfile.TemporaryDirectory() as workspace:
            agent = AutonomousMissionAgent('test','Inspect',workspace,'fixture:local','SAFE',depth=1)
            agent.gateway = self.gateway
            agent.state['criteria'] = ['Exact content']
            _ = [c async for c in agent._chat_chunks([{'role':'user','content':'Test'}])]
        schema = self.received[0]['format']
        selected = [b['properties']['tool']['const'] for b in schema['oneOf']]
        self.assertNotIn('spawn_agent',selected)
        self.assertNotIn('write_file',selected)
        verify = next(b for b in schema['oneOf'] if b['properties']['tool']['const']=='verify')
        checks = verify['properties']['args']['properties']['checks']['items']['anyOf']
        self.assertTrue(all('criterion' in c['required'] for c in checks))
        self.assertTrue(all(c['properties']['criterion']['enum']==['Exact content'] for c in checks))
        self.assertNotIn('command',[c['properties']['kind']['const'] for c in checks])

    async def test_decoding_verification_targets_unverified_criteria_first(self):
        self.lines = [{'message':{'content':'{"tool":"finish","args":{"message":"Done"}}'}},{'done':True}]
        with tempfile.TemporaryDirectory() as workspace:
            agent = AutonomousMissionAgent('test','Inspect',workspace,'fixture:local')
            agent.gateway = self.gateway
            agent.state.update(criteria=['Already checked','Still missing'],verified=['Already checked'])
            _ = [c async for c in agent._chat_chunks([{'role':'user','content':'Test'}])]
        verify = next(b for b in self.received[0]['format']['oneOf'] if b['properties']['tool']['const']=='verify')
        checks = verify['properties']['args']['properties']['checks']['items']['anyOf']
        self.assertTrue(all(c['properties']['criterion']['enum']==['Still missing'] for c in checks))

    async def test_completion_review_keeps_verdict_schema_through_generate(self):
        verdict = {'approved':True,'unmet':[],'reason':'Observed evidence','issues':[]}
        self.lines = [{'message':{'content':json.dumps(verdict)}}, {'done':True}]
        with tempfile.TemporaryDirectory() as workspace:
            agent = AutonomousMissionAgent('test','Answer the request',workspace,'fixture:local')
            agent.gateway = self.gateway
            self.assertEqual(await agent._review_completion('Done'),verdict)
        schema = self.received[0]['format']
        approve,reject = schema['oneOf']
        for branch in (approve,reject):
            self.assertEqual(set(branch['required']),{'approved','unmet','reason','issues'})
        self.assertIs(approve['properties']['approved']['const'],True)
        self.assertEqual(approve['properties']['unmet'],{'const':[]})
        self.assertEqual(approve['properties']['issues'],{'const':[]})
        self.assertIs(reject['properties']['approved']['const'],False)
        self.assertEqual(reject['properties']['unmet']['minItems'],1)
        self.assertEqual(reject['properties']['issues']['minItems'],1)

    async def test_context_window_uses_the_selected_loaded_runner(self):
        self.assertEqual(await self.gateway.running_context_window('fixture:local'),4096)
        self.assertIsNone(await self.gateway.running_context_window('missing:local'))

    async def test_invented_review_requirement_is_rechecked_and_not_treated_as_user_instruction(self):
        with tempfile.TemporaryDirectory() as workspace:
            agent = AutonomousMissionAgent('test','If interrupted, write a recovery note',workspace,'fixture:local')
            reject = {'approved':False,'unmet':['Wait for the original script'],'reason':'Invented requirement',
                      'issues':[{'request_quote':'Wait for the original script','gap':'Not waited','evidence_ids':[]}]}
            approve = {'approved':True,'unmet':[],'reason':'Recovery permitted by the actual request','issues':[]}
            agent.gateway.generate = AsyncMock(side_effect=[json.dumps(reject),json.dumps(approve)])
            with patch.object(agent,'_emit',AsyncMock()) as emit:
                self.assertEqual(await agent._review_completion('Recovery note written'),approve)
            self.assertEqual(agent.gateway.generate.await_count,2)
            calls = agent.gateway.generate.call_args_list
            self.assertIn('quote an actual request requirement',calls[1].args[0])
            self.assertEqual(emit.call_args.args[0],'review_recheck')

    async def test_grounded_wrong_content_remains_rejected_after_recheck(self):
        with tempfile.TemporaryDirectory() as workspace:
            agent = AutonomousMissionAgent('test','Write the value 25',workspace,'fixture:local')
            agent.state['evidence'] = [{'id':'actual','tool':'read_file','ok':True,'result':{'content':'15'}}]
            reject = {'approved':False,'unmet':['Wrong value'],'reason':'Current content is 15',
                      'issues':[{'request_quote':'the value 25','gap':'Observed 15','evidence_ids':['actual']}]}
            agent.gateway.generate = AsyncMock(return_value=json.dumps(reject))
            self.assertEqual(await agent._review_completion('Done'),reject)
            self.assertEqual(agent.gateway.generate.await_count,2)

    async def test_hallucinated_evidence_id_or_conflicting_approval_never_passes(self):
        with tempfile.TemporaryDirectory() as workspace:
            agent = AutonomousMissionAgent('test','Write the value 25',workspace,'fixture:local')
            issue = {'request_quote':'the value 25','gap':'No verified value','evidence_ids':['invented']}
            for verdict in ({'approved':False,'unmet':['Gap'],'reason':'Bad source','issues':[issue]},
                            {'approved':True,'unmet':['Gap'],'reason':'Conflict','issues':[issue]},
                            {'approved':False,'unmet':['Gap'],'reason':'Ungrounded','issues':[]}):
                with self.subTest(verdict=verdict):
                    agent.gateway.generate = AsyncMock(return_value=json.dumps(verdict))
                    with self.assertRaises(ValueError):
                        await agent._review_completion('Done')

    async def test_large_review_evidence_is_bounded_and_marked_over_real_transport(self):
        verdict = {'approved':False,'unmet':['Missing proof'],'reason':'Truncated observation',
                   'issues':[{'request_quote':'Preserve this original objective','gap':'Missing proof','evidence_ids':[]}]}
        self.lines = [{'message':{'content':json.dumps(verdict)}},{'done':True}]
        with tempfile.TemporaryDirectory() as workspace:
            agent = AutonomousMissionAgent('test','Preserve this original objective',workspace,'fixture:local')
            agent.gateway = self.gateway
            agent.state.update(context_window=4096,context_chars_per_token=1,max_reply_tokens=300,
                               evidence=[{'id':'actual','tool':'run_command','ok':True,'result':{'output':'x'*60000}}])
            result = await agent._review_completion('Proposed result')
        self.assertFalse(result['approved'])
        messages = self.received[0]['messages']
        self.assertLessEqual(sum(len(m['content']) for m in messages),agent._context_chars())
        value = json.loads(messages[1]['content'])
        self.assertEqual(value['original_request'],'Preserve this original objective')
        self.assertTrue(value['observations'][0]['result_truncated'])

    async def test_review_reads_current_deliverable_instead_of_assuming_old_write_metadata(self):
        verdict = {'approved':False,'unmet':['Wrong saved field'],'reason':'Observed actual JSON',
                   'issues':[{'request_quote':'consommation','gap':'Saved consumption instead','evidence_ids':[]}]}
        self.lines = [{'message':{'content':json.dumps(verdict)}},{'done':True}]
        with tempfile.TemporaryDirectory() as workspace:
            path = Path(workspace)/'answer.json'
            path.write_text('{"consumption":136}')
            agent = AutonomousMissionAgent('test','Save a JSON field named consommation',workspace,'fixture:local')
            agent.gateway = self.gateway
            agent.state['evidence'] = [{'id':'old','tool':'write_file','ok':True,'result':{'path':str(path),'bytes':20,'sha256':'old'}}]
            result = await agent._review_completion('Saved the requested output')
            value = json.loads(self.received[0]['messages'][1]['content'])
            actual = next(e for e in value['observations'] if e['tool']=='read_file')
            self.assertEqual(actual['result']['content'],path.read_text())
            self.assertNotEqual(actual['result']['sha256'],'old')
            self.assertFalse(result['approved'])

    async def test_truncated_model_stream_cannot_be_a_complete_answer(self):
        self.lines = [{'message':{'content':'Partial response'}}]
        with self.assertRaisesRegex(RuntimeError,'complete answer'):
            async for _ in self.gateway.chat_chunks([{'role':'user','content':'Test'}],'fixture:local'):
                pass

    async def test_model_error_is_not_reinterpreted_as_an_answer(self):
        self.lines = [{'error':'Model unavailable'}]
        with self.assertRaisesRegex(RuntimeError,'Model unavailable'):
            async for _ in self.gateway.chat_chunks([{'role':'user','content':'Test'}],'fixture:local'):
                pass
