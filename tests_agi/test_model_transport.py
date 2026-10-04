"""Actual HTTP streaming against a temporary Ollama protocol fixture, no inference."""
import json
import unittest
from unittest.mock import patch
from aiohttp import web
from agi_core.llm_gateway import LLMGateway


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
        self.assertEqual(metrics[0]['tokens_per_second'],20)
        self.assertEqual(metrics[0]['prompt_eval_count'],23)

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
