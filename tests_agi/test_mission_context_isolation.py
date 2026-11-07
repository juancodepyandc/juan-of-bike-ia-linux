"""Prevent unrelated saved content from becoming mission control instructions."""
import hashlib
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from uuid import uuid4
from agi_core.mission_agent import AutonomousMissionAgent
from agi_core.mission_tools import MissionTools
from agi_core.mission_protocol import ARG_SCHEMAS


class MissionContextIsolation(unittest.IsolatedAsyncioTestCase):
    def test_full_protocol_does_not_autoload_skill_bodies_or_saved_tasks(self):
        subject = SimpleNamespace(workspace='workspace', request_text='Inspect current data', mission_id='mission',
                                  permissions='STANDARD', additional_context='', _domain_guidance=lambda:'')
        with patch('agi_core.mission_agent._cli_load_context_for_workspace', side_effect=AssertionError('Implicit catalog injection')):
            prompt=AutonomousMissionAgent._system_prompt(subject)
        self.assertIn('read_skill',prompt)
        self.assertIn('subordinate',prompt)
        self.assertNotIn('Project skills:',prompt)
        self.assertNotIn('Reusable roles:',prompt)

    async def test_selected_skill_is_actual_bounded_content_and_changes_its_hash(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);name=uuid4().hex;body=uuid4().hex
            skill=root/'.aurora/skills'/name/'SKILL.md';skill.parent.mkdir(parents=True)
            skill.write_text(body)
            calls=[]
            agent=SimpleNamespace(workspace=directory, _require_tool=calls.append, policy=SimpleNamespace(output_chars=12))
            tools=MissionTools(agent,root,'python')
            result=await tools.execute('read_skill',{'name':name})
            self.assertEqual(result['content'],body[:12]);self.assertTrue(result['truncated'])
            self.assertEqual(result['sha256'],hashlib.sha256(body.encode()).hexdigest())
            skill.write_text(body+'!')
            changed=await tools.execute('read_skill',{'name':name})
            self.assertNotEqual(changed['sha256'],result['sha256'])
            with self.assertRaisesRegex(ValueError,'not discovered'):
                await tools.execute('read_skill',{'name':'../unlisted'})
            self.assertEqual(calls,['read_skill']*3)

    def test_every_native_tool_can_be_declared_required_without_schema_loss(self):
        names=ARG_SCHEMAS['set_plan']['properties']['required_tools']['items']['enum']
        for name in ('browser_action','inspect_image','inspect_browser','mcp_catalog','read_mcp_resource','get_mcp_prompt','close_mcp_session','read_skill'):
            self.assertIn(name,names)

    def test_mcp_facts_persist_without_reexecuting_or_certifying(self):
        retained=[]
        agent=SimpleNamespace(policy=SimpleNamespace(output_chars=12000), _remember_resource=lambda *args:retained.append(args))
        tools=MissionTools(agent,Path('.'),'python')
        result={'kind':'tools','items':[{'name':'observed-tool','inputSchema':{'type':'object'}}],'next_cursor':None}
        self.assertIs(tools.remember_mcp('mcp_catalog',{'server':'observed-server','kind':'tools'},result),result)
        kind,identity,facts=retained[-1]
        self.assertEqual(kind,'mcp_observation');self.assertIn('observed-tool',facts['summary'])
        self.assertIn('not a fresh query',facts['scope']);self.assertNotIn('inputSchema',facts['summary'])
        contents={'result':{'contents':[{'uri':'observed://data','text':'x'*2000}]}}
        tools.remember_mcp('read_mcp_resource',{'server':'observed-server','uri':'observed://data'},contents)
        self.assertTrue(retained[-1][2]['summary_truncated']);self.assertLessEqual(len(retained[-1][2]['summary']),750)
