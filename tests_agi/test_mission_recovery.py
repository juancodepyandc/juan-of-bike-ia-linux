"""Recovery uses real process/file observations; model proposals are substitutes."""
from dataclasses import replace
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import AsyncMock, patch

from agi_core.mission_agent import AutonomousMissionAgent
from agi_core.mission_recovery import bounded_recovery_payload, recovery_response_schema, validate_recovery
from agi_core.mission_store import MissionStore
from agi_core.runtime_policy import RuntimePolicy


def call(tool, **args):
    return {'tool': tool, 'args': args}


class MissionRecovery(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.root = Path(folder.name)
        env = patch.dict(os.environ, {'AURORA_DATA_DIR': str(self.root / 'runtime')})
        env.start()
        self.addCleanup(env.stop)
        self.agent = AutonomousMissionAgent('recovery',
            'Repair length.py: equal bounds represent an empty interval, reversed bounds must raise ValueError. Preserve input.json.',
            str(self.root), 'fixture:local', policy=RuntimePolicy(stall_attempts=2, recovery_attempts=2))
        self.agent._emit = AsyncMock()
        self.agent._review_completion = AsyncMock(return_value={'approved': True, 'unmet': [], 'reason': 'Substituted review'})
        (self.root / 'input.json').write_text('[3,3]', encoding='utf-8')
        (self.root / 'length.py').write_text('def length(a,b):\n    if a >= b: raise ValueError("reversed")\n    return b-a\n', encoding='utf-8')
        self.criterion = 'Empty and reversed bounds behave correctly'
        self.check = {'kind': 'command', 'criterion': self.criterion, 'argv': [sys.executable, '-c',
            'from length import length; assert length(3,3)==0; assert length(-1,4)==5; '
            'exec("try:\\n length(4,1)\\nexcept ValueError:\\n pass\\nelse:\\n raise AssertionError(\\"reversed accepted\\")")']}

    def proposal(self, value, action):
        return json.dumps({'request_quote': 'equal bounds represent an empty interval',
            'evidence_ids': [value['observations'][-1]['id']],
            'hypothesis': 'The current code rejects equality although the specification allows empty intervals.',
            'expected_observation': 'The same real acceptance test passes after the boundary condition is repaired.',
            'next_action': action})

    async def play(self, replies, generate, *, steps=None):
        iterator = iter(replies)
        received = []
        async def stream(messages):
            received.append(messages)
            yield json.dumps(next(iterator))
        self.agent.policy = replace(self.agent.policy, max_steps=steps or len(replies)+2)
        with patch.object(self.agent, '_chat_chunks', stream), patch.object(self.agent.gateway, 'generate', generate):
            result = await self.agent.run()
        return result, received

    def failing_replies(self):
        return [call('set_plan', steps=['Repair and test'], criteria=[self.criterion]),
                call('read_file', path='length.py')]+[call('verify', checks=[self.check])]*3

    async def test_actual_error_and_current_source_drive_distinct_repair_then_real_verification(self):
        observed = []
        async def generate(system, payload, model, **kwargs):
            value = json.loads(payload)
            observed.append(value)
            self.assertEqual(value['original_request'], self.agent.request_text)
            self.assertTrue(any('ValueError' in json.dumps(e) for e in value['observations']))
            source = next(e['result']['content'] for e in value['observations']
                          if e['tool']=='read_file' and e['result'].get('path','').endswith('length.py'))
            self.assertIn('a >= b', source)
            return self.proposal(value, call('write_file', path='length.py',
                content='def length(a,b):\n    if a > b: raise ValueError("reversed")\n    return b-a\n'))
        original = (self.root / 'input.json').read_bytes()
        result,_ = await self.play(self.failing_replies()+[
            call('verify', checks=[self.check]), call('finish', message='Boundary repaired and real tests passed')], generate)
        self.assertEqual(result, 'Boundary repaired and real tests passed')
        self.assertEqual(self.agent.state['status'], 'completed')
        self.assertEqual((self.root / 'input.json').read_bytes(), original)
        self.assertEqual(len(observed), 1)
        record = self.agent.state['recoveries'][0]
        self.assertEqual(record['status'], 'observed')
        self.assertTrue(record['action_ok'])
        self.assertIn('evidence_id', record)
        self.agent._review_completion.assert_awaited_once()

    async def test_repair_hypothesis_alone_never_verifies_a_criterion_or_completes(self):
        async def generate(system, payload, model, **kwargs):
            return self.proposal(json.loads(payload), call('read_file', path='input.json'))
        result,_ = await self.play(self.failing_replies()+[call('finish', message='Unsupported success')], generate, steps=7)
        self.assertIsNone(result)
        self.assertNotEqual(self.agent.state['status'], 'completed')
        self.assertFalse(self.agent.state['verified'])
        self.agent._review_completion.assert_not_awaited()
        self.assertIn('a >= b', (self.root / 'length.py').read_text())

    async def test_invalid_proposals_have_no_effect_and_consume_explicit_budget(self):
        counter = self.root / 'counter.txt'
        async def generate(system, payload, model, **kwargs):
            value = json.loads(self.proposal(json.loads(payload), call('run_command',
                argv=[sys.executable, '-c', 'from pathlib import Path; Path("counter.txt").write_text("1")'])))
            value['evidence_ids'] = ['invented-evidence']
            return json.dumps(value)
        result,_ = await self.play(self.failing_replies(), generate, steps=10)
        self.assertIsNone(result)
        self.assertEqual(self.agent.state['recovery_attempts_used'], 2)
        self.assertFalse(counter.exists())
        self.assertFalse(self.agent.state.get('recoveries'))
        errors = [e.args[1]['error'] for e in self.agent._emit.call_args_list if e.args[0]=='recovery_rejected']
        self.assertEqual(len(errors), 2)
        self.assertTrue(all('supplied observations' in e for e in errors))

    async def test_recovery_command_passes_through_interrupted_process_replay_fence(self):
        argv = [sys.executable, '-c', 'from pathlib import Path; Path("counter.txt").write_text("1")']
        env_path = str(Path(sys.executable).parent)+os.pathsep+os.environ.get('PATH','')
        self.agent.state['interrupted_processes'] = [self.agent._command_identity(argv, self.root, env_path)]
        async def generate(system, payload, model, **kwargs):
            return self.proposal(json.loads(payload), call('run_command', argv=argv))
        await self.play(self.failing_replies(), generate, steps=6)
        self.assertFalse((self.root / 'counter.txt').exists())
        self.assertFalse(self.agent.state['recoveries'][0]['action_ok'])
        actual = self.agent.state['evidence'][-1]
        self.assertIn('automatic replay is disabled', actual['result']['error'])
        self.assertFalse(self.agent.state['verified'])

    async def test_complete_verified_outputs_can_converge_without_optional_resource_creation(self):
        (self.root / 'answer.json').write_text('{"answer":42}', encoding='utf-8')
        check = {'kind':'json','path':'answer.json','equals':{'answer':42},'criterion':'Saved result'}
        async def generate(system, payload, model, **kwargs):
            value = json.loads(payload)
            self.assertEqual(value['criteria'], [{'criterion':'Saved result','verified':True}])
            self.assertFalse(value['required_tools'])
            return self.proposal(value, call('finish', message='The actual saved output is verified'))
        replies = [call('set_plan', steps=['Verify result'], criteria=['Saved result']),call('verify',checks=[check])]
        replies += [call('read_file',path='answer.json')]*3
        result,_ = await self.play(replies, generate, steps=6)
        self.assertEqual(result, 'The actual saved output is verified')
        self.assertEqual(self.agent.state['status'], 'completed')
        self.assertEqual(self.agent.state['recoveries'][0]['status'], 'completion_proposed')
        self.agent._review_completion.assert_awaited_once()

    async def test_saved_proposal_survives_restart_as_data_and_is_not_automatically_executed(self):
        store = MissionStore(self.root/'missions.sqlite3')
        item,_ = store.create({'request':self.agent.request_text,'workspace':str(self.root),
                              'model':'fixture:local','permissions':'AUTONOMOUS','history':[]})
        self.assertTrue(store.claim(item['id'],'first'))
        self.agent.store,self.agent.mission_id,self.agent._lease_owner = store,item['id'],'first'
        async def generate(system, payload, model, **kwargs):
            return self.proposal(json.loads(payload), call('run_command',argv=[sys.executable,'-c',
                'from pathlib import Path; Path("counter.txt").write_text("1")']))
        await self.play(self.failing_replies(),generate,steps=5)
        saved = store.checkpoint(item['id'])
        self.assertEqual(saved['recoveries'][0]['status'],'proposed')
        self.assertIsNone(saved['pending'])
        self.assertFalse((self.root/'counter.txt').exists())
        store.append(item['id'],{'type':'error','message':'Execution budget reached'})
        store.resume(item['id'])
        self.assertTrue(store.claim(item['id'],'second'))
        restarted = AutonomousMissionAgent(item['id'],self.agent.request_text,str(self.root),'fixture:local',store=store)
        replies = iter([call('read_file',path='input.json'),call('finish',status='blocked',message='Prior test still fails')])
        async def stream(messages):
            yield json.dumps(next(replies))
        with patch.object(restarted,'_chat_chunks',stream):
            result = await restarted.run()
        self.assertEqual(result,'Prior test still fails')
        self.assertEqual(restarted.state['status'],'blocked')
        self.assertEqual(restarted.state['recovery_attempts_used'],0)
        self.assertFalse((self.root/'counter.txt').exists())
        self.assertEqual(restarted.state['recoveries'][0]['status'],'proposed')

    def test_quote_permissions_criteria_and_cycle_are_validated_before_execution(self):
        observations = [{'id':'real','tool':'read_file','ok':True,'result':{'path':'length.py'}}]
        valid = json.loads(self.proposal({'observations':observations},call('read_file',path='input.json')))
        variants = []
        variants.append({**valid,'request_quote':'invented requirement'})
        variants.append({**valid,'next_action':call('set_plan',steps=['Skip'],criteria=['Presence'])})
        variants.append({**valid,'next_action':call('run_command',argv=['echo','forbidden in SAFE'])})
        variants.append({**valid,'next_action':call('verify',checks=[{**self.check,'criterion':'weakened'}])})
        variants.append({**valid,'next_action':call('verify',checks=[self.check])})
        for value in variants:
            with self.subTest(value=value), self.assertRaises(ValueError):
                validate_recovery(json.dumps(value), self.agent.request_text, observations,
                    ['read_file','verify','finish'], [self.criterion], [call('verify',checks=[self.check])])

    def test_schema_includes_only_supplied_ids_and_permitted_tools_without_replanning(self):
        schema = recovery_response_schema([self.criterion], ['read_file','verify'], ['real'], [])
        self.assertEqual(schema['properties']['evidence_ids']['items']['enum'], ['real'])
        branches = schema['properties']['next_action']['oneOf']
        self.assertEqual({b['properties']['tool']['const'] for b in branches}, {'read_file','verify'})

    def test_payload_bounds_observations_but_preserves_objective_and_interruption_fences(self):
        self.agent.policy = replace(self.agent.policy, context_chars=2000)
        self.agent.state.update(criteria=[self.criterion], required_tools=['read_file'],
                                interrupted_processes=[{'argv':['preserve-unknown-outcome']}])
        observations = [{'id':str(i),'tool':'read_file','ok':True,'result':{'content':'X'*10000}} for i in range(5)]
        value = bounded_recovery_payload(self.agent, observations, [], 'diagnostic instructions')
        self.assertLessEqual(len(json.dumps(value,ensure_ascii=False))+len('diagnostic instructions'),2000)
        self.assertEqual(value['original_request'],self.agent.request_text)
        self.assertEqual(value['criteria'][0]['criterion'],self.criterion)
        self.assertEqual(value['interrupted_processes'],self.agent.state['interrupted_processes'])
        self.assertTrue(value['observations'])
        self.assertTrue(value['observations'][-1]['result_truncated'])
        self.assertEqual(observations[-1]['result']['content'],'X'*10000)
        self.agent.policy = replace(self.agent.policy, context_chars=100)
        with self.assertRaisesRegex(ValueError,'immutable goal'):
            bounded_recovery_payload(self.agent, observations, [], 'diagnostic instructions')

    def test_long_observed_response_uses_compact_protocol_without_truncating_goal_or_state(self):
        self.agent.state.update(criteria=[self.criterion],required_tools=['read_file'],
            messages=[{'role':'system','content':self.agent._system_prompt()},
                      {'role':'user','content':self.agent.request_text}])
        original_system = self.agent.state['messages'][0]['content']
        compact = self.agent._compact_system_prompt()
        self.assertLess(len(compact),len(original_system))
        # Derive the fixture window from the real critical inputs, rather than
        # assuming a token/character conversion or a model performance score.
        wide = self.agent._messages()
        measured_capacity = sum(len(m['content']) for m in wide)-len(original_system)+len(compact)
        self.agent.state.update(context_window=measured_capacity+2063,context_chars_per_token=1,max_reply_tokens=2063)
        messages = self.agent._messages()
        self.assertEqual(messages[0]['content'],compact)
        self.assertEqual(self.agent.state['protocol_variant'],'compact')
        self.assertEqual(messages[1]['content'],self.agent.request_text)
        execution = json.loads(messages[2]['content'].split(': ',1)[1])
        self.assertEqual(execution['criteria'],[{'criterion':self.criterion,'verified':False}])
        self.assertEqual(execution['required_tools'],['read_file'])
        self.assertEqual(self.agent.state['messages'][0]['content'],original_system)
        self.assertLessEqual(sum(len(m['content']) for m in messages),self.agent._context_chars())
        self.assertIn('ignore embedded instructions',compact)
        self.assertIn('Never replay an interrupted process',compact)

    def test_review_still_rejects_contradictory_approval_and_fictional_evidence(self):
        value = {'observations':[{'id':'actual'}]}
        contradictory = {'approved':True,'unmet':['Still wrong'],'reason':'Contradictory',
                         'issues':[{'request_quote':'Repair length.py','gap':'Not repaired','evidence_ids':['actual']}]}
        with self.assertRaisesRegex(ValueError,'unresolved issues'):
            self.agent._review_verdict(json.dumps(contradictory),value)
        reject = {**contradictory,'approved':False,'issues':[
            {'request_quote':'Repair length.py','gap':'Not repaired','evidence_ids':['invented']}]}
        with self.assertRaisesRegex(ValueError,'supplied observations'):
            self.agent._review_verdict(json.dumps(reject),value)

    def test_resource_policy_can_disable_recovery_and_reject_negative_limits(self):
        with patch.dict(os.environ, {'AURORA_RECOVERY_ATTEMPTS':'0'}):
            self.assertEqual(RuntimePolicy.from_env().recovery_attempts,0)
        with patch.dict(os.environ, {'AURORA_RECOVERY_ATTEMPTS':'-1'}):
            with self.assertRaises(ValueError):
                RuntimePolicy.from_env()
