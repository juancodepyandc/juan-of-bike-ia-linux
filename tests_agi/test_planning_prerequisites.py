"""Prevent the observed image loop without launching a model or media engine."""
from dataclasses import replace
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import AsyncMock, patch

from agi_core.mission_agent import AutonomousMissionAgent, CHANGE_TOOLS


class PlanningPrerequisites(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.env = patch.dict(os.environ, {'AURORA_DATA_DIR':str(Path(self.folder.name)/'runtime')})
        self.env.start()
        self.agent = AutonomousMissionAgent('mis_planning', 'Generate an image of an otter',
                                            self.folder.name, 'fixture:local')
        self.agent._emit = AsyncMock()

    async def asyncTearDown(self):
        self.env.stop()
        self.folder.cleanup()

    async def test_native_decoding_excludes_effects_until_a_plan_is_accepted(self):
        schemas = []
        async def chunks(messages, model, **kwargs):
            schemas.append(kwargs['response_format'])
            yield '{}'
        with patch.object(self.agent.gateway, 'chat_chunks', chunks):
            _ = [c async for c in self.agent._chat_chunks([])]
            await self.agent._execute('set_plan', {'steps':['Generate and inspect the image'],
                                                  'criteria':['A generated image is delivered']})
            _ = [c async for c in self.agent._chat_chunks([])]
        selected = lambda schema: {b['properties']['tool']['const'] for b in schema['oneOf']}
        before, after = map(selected, schemas)
        self.assertFalse(before & CHANGE_TOOLS)
        self.assertTrue({'set_plan','inspect_runtime','finish'} <= before)
        self.assertIn('generate_image', after)
        self.agent.permissions = 'SAFE'
        self.assertNotIn('generate_image', self.agent._available_tools())

    async def test_executor_still_refuses_effects_even_if_model_ignores_decoding(self):
        with patch.object(self.agent, '_run_process', AsyncMock()) as process:
            with self.assertRaisesRegex(ValueError, 'Set a plan'):
                await self.agent._execute('generate_image', {'prompt':'an otter'})
            process.assert_not_awaited()

    async def test_recovery_can_establish_missing_plan_without_erasing_existing_criteria(self):
        self.agent.state['evidence'] = [{'id':'ev_missing_plan','tool':'generate_image','ok':False,
            'result':{'error':'Set a plan and measurable acceptance criteria before executing actions'}}]
        payloads = []
        async def generate(system, payload, model, **kwargs):
            payloads.append(kwargs['response_format'])
            return json.dumps({'request_quote':'Generate an image of an otter',
                'evidence_ids':['ev_missing_plan'], 'hypothesis':'The required plan is missing',
                'expected_observation':'The plan is accepted before generation',
                'next_action':{'tool':'set_plan','args':{'steps':['Generate then inspect'],
                    'criteria':['A generated image is delivered']}}})
        with patch.object(self.agent.gateway, 'generate', generate):
            proposal = await self.agent._recover_stagnation([])
        self.assertEqual(proposal['next_action']['tool'], 'set_plan')
        self.assertEqual(self.agent.state['plan'], [])  # Proposal has no effects.
        await self.agent._execute('set_plan', proposal['next_action']['args'])
        with patch.object(self.agent.gateway, 'generate', generate):
            self.assertIsNone(await self.agent._recover_stagnation([]))
        self.assertEqual(self.agent.state['criteria'], ['A generated image is delivered'])

    async def test_varying_image_folders_does_not_hide_the_same_prerequisite_failure(self):
        self.agent.policy = replace(self.agent.policy, stall_attempts=2, recovery_attempts=0, max_steps=10)
        calls = iter({'tool':'generate_image','args':{'prompt':'an otter','folder':f'image_{i}'}}
                     for i in range(10))
        async def chunks(messages):
            yield json.dumps(next(calls))
        with patch.object(self.agent, '_chat_chunks', chunks),patch.object(self.agent, '_run_process', AsyncMock()) as process:
            await self.agent.run()
        process.assert_not_awaited()
        self.assertEqual(self.agent.state['action_count'], 3)
        self.assertEqual(self.agent.state['status'], 'failed')
        last_error = next(c.args[1] for c in reversed(self.agent._emit.await_args_list) if c.args[0]=='error')
        self.assertIn('Repeated actions', last_error['message'])
