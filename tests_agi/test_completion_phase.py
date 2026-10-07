"""Completion remains a proposal; rejected reviews allow real repairs."""
from dataclasses import replace
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import AsyncMock, patch

from agi_core.mission_agent import AutonomousMissionAgent
from agi_core.mission_store import MissionStore
from agi_core.llm_gateway import ModelIncompleteAnswer


class CompletionPhase(unittest.IsolatedAsyncioTestCase):
    async def test_audit_exhaustion_stops_once_and_preserves_saved_verified_work(self):
        with tempfile.TemporaryDirectory() as folder,patch.dict(os.environ,{'AURORA_DATA_DIR':str(Path(folder)/'runtime')}):
            path=Path(folder)/'answer.txt';path.write_bytes(b'observed result\n')
            agent=AutonomousMissionAgent('exhaustion','Save and verify answer.txt',folder,'fixture:local')
            agent._emit=AsyncMock()
            agent.state.update(plan=['Save and verify'],criteria=['Saved content is correct'],
                               verified=['Saved content is correct'],last_change=1,last_verify=2)
            async def proposal(messages):
                yield json.dumps({'tool':'finish','args':{'message':'Saved content verified'}})
            with patch.object(agent,'_chat_chunks',proposal),patch.object(agent,'_propose_completion_audit',
                    AsyncMock(side_effect=ModelIncompleteAnswer('Model context exhausted without an answer'))) as audit:
                self.assertIsNone(await agent.run())
            self.assertEqual(audit.await_count,1)
            self.assertEqual(agent.state['status'],'failed')
            self.assertEqual(agent.state['verified'],['Saved content is correct'])
            self.assertEqual(path.read_bytes(),b'observed result\n')
    async def test_rejected_review_is_persisted_then_repaired_and_verified_before_completion(self):
        with tempfile.TemporaryDirectory() as folder,patch.dict(os.environ,{'AURORA_DATA_DIR':str(Path(folder)/'runtime')}):
            root=Path(folder);store=MissionStore(root/'mission.sqlite3')
            goal='Write the value 25 to answer.txt and verify the saved value'
            item,_=store.create({'request':goal,'workspace':folder,'model':'fixture:local','permissions':'AUTONOMOUS'})
            agent=AutonomousMissionAgent(item['id'],goal,folder,'fixture:local',store=store)
            agent.policy=replace(agent.policy,request_audit=False,recovery_attempts=0)
            agent._emit=AsyncMock()
            criterion='The saved value equals the requested value'
            replies=iter([
                {'tool':'set_plan','args':{'steps':['Write and verify'],'criteria':[criterion]}},
                {'tool':'write_file','args':{'path':'answer.txt','content':'15'}},
                {'tool':'verify','args':{'checks':[{'kind':'file','path':'answer.txt','criterion':criterion}]}},
                {'tool':'finish','args':{'message':'Premature completion'}},
                {'tool':'write_file','args':{'path':'answer.txt','content':'25'}},
                {'tool':'verify','args':{'checks':[{'kind':'text','path':'answer.txt','equals':'25','criterion':criterion}]}},
                {'tool':'finish','args':{'message':'Current saved value verified'}}])
            schemas=[];persisted=[]
            async def chat(messages,model,**kwargs):
                schemas.append(kwargs['response_format'])
                if agent.state.get('completion_review_gap'):
                    persisted.append(store.checkpoint(item['id'])['completion_review_gap'])
                yield json.dumps(next(replies))
            async def review(message):
                correct=(root/'answer.txt').read_text()=='25'
                return {'approved':correct,'unmet':[] if correct else ['Saved value is 15, requested 25'],
                        'reason':'Actual saved content checked by test fixture'}
            with patch.object(agent.gateway,'chat_chunks',chat),patch.object(agent,'_review_completion',review):
                self.assertEqual(await agent.run(),'Current saved value verified')
            selected=lambda index:[b['properties']['tool']['const'] for b in schemas[index]['oneOf']]
            self.assertEqual(selected(3),['finish'])
            self.assertIn('write_file',selected(4))
            self.assertIn('verify',selected(5))
            self.assertEqual(selected(6),['finish'])
            self.assertTrue(persisted and all(persisted))
            self.assertEqual(agent.state['status'],'completed')
            self.assertNotIn('completion_review_gap',store.checkpoint(item['id']))
            self.assertEqual((root/'answer.txt').read_text(),'25')
