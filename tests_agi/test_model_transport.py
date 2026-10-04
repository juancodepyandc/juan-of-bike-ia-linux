"""Actual HTTP streaming against a temporary Ollama protocol fixture, no inference."""
import json
import tempfile
from pathlib import Path
import unittest
from unittest.mock import patch
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
        self.assertEqual(set(schema['required']),{'tool','args'})
        self.assertEqual(schema['properties']['args']['type'],'object')
        self.assertFalse(schema['additionalProperties'])

    async def test_completion_review_keeps_verdict_schema_through_generate(self):
        verdict = {'approved':True,'unmet':[],'reason':'Observed evidence'}
        self.lines = [{'message':{'content':json.dumps(verdict)}}, {'done':True}]
        with tempfile.TemporaryDirectory() as workspace:
            agent = AutonomousMissionAgent('test','Answer the request',workspace,'fixture:local')
            agent.gateway = self.gateway
            self.assertEqual(await agent._review_completion('Done'),verdict)
        schema = self.received[0]['format']
        self.assertEqual(set(schema['required']),{'approved','unmet','reason'})
        self.assertEqual(schema['properties']['approved']['type'],'boolean')

    async def test_context_window_uses_the_selected_loaded_runner(self):
        self.assertEqual(await self.gateway.running_context_window('fixture:local'),4096)
        self.assertIsNone(await self.gateway.running_context_window('missing:local'))

    async def test_large_review_evidence_is_bounded_and_marked_over_real_transport(self):
        self.lines = [{'message':{'content':'{"approved":false,"unmet":["Missing proof"],"reason":"Truncated observation"}'}},{'done':True}]
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
        self.lines = [{'message':{'content':'{"approved":false,"unmet":["Wrong saved field"],"reason":"Observed actual JSON"}'}},{'done':True}]
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
