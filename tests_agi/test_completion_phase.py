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


class CompletionPhase(unittest.IsolatedAsyncioTestCase):
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
