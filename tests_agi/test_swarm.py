import asyncio
import unittest
from unittest import mock

from agi_core.swarm import SwarmSupervisor


class SwarmTests(unittest.IsolatedAsyncioTestCase):
    async def test_concurrent_missions_keep_identity_workspace_and_memory(self):
        supervisor = SwarmSupervisor()
        arrivals = 0
        both_started = asyncio.Event()
        executions = []

        async def query(situation):
            nonlocal arrivals
            arrivals += 1
            if arrivals == 2:
                both_started.set()
            await asyncio.wait_for(both_started.wait(), timeout=1)
            return [f'memory for {situation}']

        async def generate(system, prompt, on_token, model):
            await asyncio.sleep(0)
            token = f'{model}: {prompt}'
            await on_token(token)
            return token

        class Agent:
            def __init__(self, **kwargs):
                self.values = kwargs
                executions.append(kwargs)

            async def run(self):
                return f"result for {self.values['mission_id']}"

        first_memory = mock.Mock(query_experience=mock.AsyncMock(side_effect=query), embed_experience=mock.AsyncMock())
        second_memory = mock.Mock(query_experience=mock.AsyncMock(side_effect=query), embed_experience=mock.AsyncMock())
        with mock.patch('agi_core.swarm.llm.generate_stream', side_effect=generate), \
             mock.patch('agi_core.swarm.AutonomousMissionAgent', Agent), \
             mock.patch('agi_core.swarm.global_bus.publish', new_callable=mock.AsyncMock) as publish:
            await asyncio.gather(
                supervisor.run_mission('first', 'first request', '/tmp/first', 'first-model', 'SAFE', first_memory),
                supervisor.run_mission('second', 'second request', '/tmp/second', 'second-model', 'STANDARD', second_memory),
            )
        self.assertEqual({item['mission_id'] for item in executions}, {'first', 'second'})
        for item in executions:
            identity = item['mission_id']
            self.assertEqual(item['workspace'], f'/tmp/{identity}')
            self.assertEqual(item['model'], f'{identity}-model')
            self.assertIn(f'Objectif original : {identity} request', item['request_text'])
        for identity, memory in [('first', first_memory), ('second', second_memory)]:
            memory.embed_experience.assert_awaited_once()
            values = memory.embed_experience.await_args.kwargs
            self.assertEqual(values['outcome'], f'result for {identity}')
            self.assertEqual(values['metadata']['mission_id'], identity)
            events = [call.args[1]['event'] for call in publish.await_args_list if call.args[1]['mission_id'] == identity]
            tokens = [event['content'] for event in events if event['type'] == 'token']
            self.assertTrue(any(f'{identity}-model:' in token for token in tokens))
            other = 'second' if identity == 'first' else 'first'
            self.assertFalse(any(f'{other}-model:' in token for token in tokens))

    async def test_error_retains_its_mission_id(self):
        with mock.patch('agi_core.swarm.llm.generate_stream', side_effect=RuntimeError('fixture failure')), \
             mock.patch('agi_core.swarm.global_bus.publish', new_callable=mock.AsyncMock) as publish:
            await SwarmSupervisor().run_mission('failed', 'request', '/tmp', 'model', 'SAFE')
        last = publish.await_args.args[1]
        self.assertEqual(last['mission_id'], 'failed')
        self.assertEqual(last['event']['type'], 'error')
        self.assertEqual(last['event']['error'], 'fixture failure')


if __name__ == '__main__':
    unittest.main()
