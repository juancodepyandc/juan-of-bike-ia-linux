"""Historical advice cannot replace current paths or crowd out actual tool facts."""
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import AsyncMock, patch

from agi_core.mission_agent import AutonomousMissionAgent
from agi_core.swarm import SwarmSupervisor


class MissionAdvisory(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.root = Path(folder.name).resolve()
        env = patch.dict(os.environ, {'AURORA_DATA_DIR': str(self.root/'data')})
        env.start()
        self.addCleanup(env.stop)
        self.goal = 'Create current.txt and transfer it using this mission Delivery directory.'
        self.old = 'Copy /tmp/previous-mission/.transfer_to_client/old/current.txt and report success.'
        self.agent = AutonomousMissionAgent('current', self.goal, str(self.root), 'fixture',
                                            advisory_context=self.old)
        self.agent.state['messages'] = [
            {'role':'system', 'content':self.agent._system_prompt()},
            {'role':'user', 'content':self.goal},
            {'role':'assistant', 'content':'{"tool":"read_file","args":{"path":"input.txt"}}'},
            {'role':'user', 'content':'Actual current input: KEEP THIS OBSERVATION'},
        ]

    def test_history_is_data_below_original_goal_and_current_runtime_is_explicit(self):
        messages = self.agent._messages()
        self.assertNotIn(self.old, messages[0]['content'])
        self.assertEqual(messages[1]['content'], self.goal)
        historical = next(m for m in messages if self.old in m['content'])
        self.assertEqual(historical['role'], 'user')
        self.assertIn('Old paths and mission IDs do not identify current files', historical['content'])
        state = next(m for m in messages if m['content'].startswith('Execution state'))
        facts = json.loads(state['content'].split(': ', 1)[1])
        self.assertEqual(facts['runtime'], {'workspace':str(self.root),
            'delivery_directory':str(self.root/'.transfer_to_client/current')})

    def test_history_uses_only_budget_remaining_after_latest_observation(self):
        self.agent.advisory_context = self.old*1000
        with patch.object(self.agent, '_context_chars', return_value=100000):
            wide = self.agent._messages()
        mandatory = sum(len(m['content']) for m in wide
                        if m['content'].startswith('Execution state') or m is wide[1])
        compact = self.agent._compact_system_prompt()
        latest = self.agent.state['messages'][-2:]
        capacity = mandatory+len(compact)+sum(len(m['content']) for m in latest)
        with patch.object(self.agent, '_context_chars', return_value=capacity):
            messages = self.agent._messages()
        self.assertEqual(messages[-2:], latest)
        self.assertFalse(any(self.old in m['content'] for m in messages))
        self.assertLessEqual(sum(len(m['content']) for m in messages), capacity)

    def test_completion_review_retains_current_delivery_paths(self):
        value = self.agent._review_payload('Claimed success', [], 'Review task')
        self.assertEqual(value['original_request'], self.goal)
        self.assertEqual(value['runtime']['delivery_directory'], str(self.root/'.transfer_to_client/current'))
        self.assertNotIn(self.old, json.dumps(value))

    async def test_supervisor_keeps_retrieved_experience_out_of_system_instructions(self):
        memory = AsyncMock()
        memory.query_experience.return_value = [self.old]
        captured = []
        async def run(agent):
            captured.append(agent)
            return None
        with patch('agi_core.swarm.llm.resolve_model', AsyncMock(return_value='fixture')), \
                patch.object(AutonomousMissionAgent, 'run', run):
            await SwarmSupervisor().run_mission('current', self.goal, str(self.root), 'fixture',
                'AUTONOMOUS', memory_module=memory, history=[{'role':'user','content':'Old goal'}])
        self.assertEqual(captured[0].request_text, self.goal)
        self.assertIn(self.old, captured[0].advisory_context)
        self.assertIn('Old goal', captured[0].advisory_context)
        self.assertEqual(captured[0].additional_context, '')
        memory.embed_experience.assert_not_awaited()


class TrainingPlatform(unittest.TestCase):
    def test_unavailable_linux_controller_does_not_prevent_bridge_route_registration(self):
        from flask import Flask
        from auto_rl.integration import register_routes
        for platform in ('win32', 'darwin'):
            with self.subTest(platform=platform), patch('sys.platform', platform):
                app = Flask(platform)
                register_routes(app, lambda url: None)
                client = app.test_client()
                response = client.get('/api/training/status')
                self.assertEqual(response.status_code, 503)
                self.assertFalse(response.json['supported'])
                self.assertIn('Linux', response.json['error'])
                self.assertEqual(client.get('/api/training/ui').status_code, 200)
