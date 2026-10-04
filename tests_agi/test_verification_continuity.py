"""Fresh file/definition proofs across real effects; model replies are substitutes."""
from dataclasses import replace
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import AsyncMock, patch

from agi_core.mission_agent import AutonomousMissionAgent


def call(tool, **args):
    return {'tool':tool,'args':args}


class VerificationContinuity(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.root = Path(folder.name)
        env = patch.dict(os.environ,{'AURORA_DATA_DIR':str(self.root/'runtime')})
        env.start()
        self.addCleanup(env.stop)
        self.agent = AutonomousMissionAgent('continuity','Inspect, change and verify the supplied files',str(self.root),'fixture:local')
        self.agent._emit = AsyncMock()
        self.agent._review_completion = AsyncMock(return_value={'approved':True,'unmet':[],'reason':'Model substitute'})
        (self.root/'a.txt').write_text('A',encoding='utf-8')
        (self.root/'b.txt').write_text('B',encoding='utf-8')
        self.a = {'kind':'text','path':'a.txt','equals':'A','criterion':'A content'}
        self.b = {'kind':'file','path':'b.txt','criterion':'B file'}

    async def play(self, replies):
        received = []
        iterator = iter(replies)
        async def stream(messages):
            received.append(messages)
            yield json.dumps(next(iterator))
        self.agent.policy = replace(self.agent.policy,max_steps=len(replies))
        with patch.object(self.agent,'_chat_chunks',stream):
            result = await self.agent.run()
        return result,received

    def plan(self, *criteria):
        return call('set_plan',steps=['Inspect and verify'],criteria=list(criteria))

    async def test_readonly_subprocess_retains_proofs_after_real_revalidation(self):
        result,_ = await self.play([
            self.plan('A content','B file'),call('verify',checks=[self.a,self.b]),
            call('run_command',argv=[sys.executable,'-c','from pathlib import Path; print(Path("a.txt").read_text())']),
            call('finish',message='Current proofs retained')])
        self.assertEqual(result,'Current proofs retained')
        self.assertEqual(set(self.agent.state['verified']),{'A content','B file'})
        refresh = next(c.args[1] for c in self.agent._emit.call_args_list if c.args[0]=='verification_refresh')
        self.assertEqual(set(refresh['preserved']),{'A content','B file'})
        self.assertTrue(all(c['unchanged'] for c in refresh['checks']))
        self.assertEqual(self.agent.state['last_change'],self.agent.state['last_verify'])

    async def test_changed_bytes_invalidate_even_a_still_passing_presence_check(self):
        _,received = await self.play([
            self.plan('A content','B file'),call('verify',checks=[self.a,self.b]),
            call('run_command',argv=[sys.executable,'-c','from pathlib import Path; Path("b.txt").write_text("changed")']),
            call('finish',message='Stale claim')])
        self.assertEqual(self.agent.state['verified'],['A content'])
        self.agent._review_completion.assert_not_awaited()
        refresh = next(c.args[1] for c in self.agent._emit.call_args_list if c.args[0]=='verification_refresh')
        changed = next(c for c in refresh['checks'] if c['criterion']=='B file')
        self.assertTrue(changed['passed'])
        self.assertFalse(changed['unchanged'])
        self.assertIn('B file',received[-1][-1]['content'])

    async def test_an_unrelated_new_file_does_not_erase_a_proved_result(self):
        result,_ = await self.play([
            self.plan('A content'),call('verify',checks=[self.a]),
            call('write_file',path='notes.txt',content='Actual note'),call('finish',message='Result and note saved')])
        self.assertEqual(result,'Result and note saved')
        self.assertEqual((self.root/'notes.txt').read_text(),'Actual note')
        self.assertEqual(self.agent.state['output_checks'],[self.a])

    async def test_a_changed_csv_source_invalidates_a_matching_saved_aggregate(self):
        (self.root/'input.csv').write_text('label,value\nx,1\ny,2\n',encoding='utf-8')
        (self.root/'summary.json').write_text('{"rows":2,"sum":3}',encoding='utf-8')
        check = {'kind':'csv_json','path':'input.csv','json_path':'summary.json','row_field':'rows',
                 'sum_fields':{'sum':'value'},'criterion':'Source and output'}
        await self.play([
            self.plan('Source and output'),call('verify',checks=[check]),
            call('write_file',path='input.csv',content='label,value\nchanged,1\ny,2\n')])
        self.assertFalse(self.agent.state['verified'])
        refresh = next(c.args[1] for c in self.agent._emit.call_args_list if c.args[0]=='verification_refresh')
        self.assertTrue(refresh['checks'][0]['passed'])
        self.assertFalse(refresh['checks'][0]['unchanged'])

    async def test_a_mixed_command_proof_is_not_replayed_or_partially_preserved(self):
        command = {'kind':'command','criterion':'A content','argv':[sys.executable,'-c',
            'from pathlib import Path; p=Path("counter.txt"); p.write_text(str(int(p.read_text())+1) if p.exists() else "1")']}
        await self.play([
            self.plan('A content'),call('verify',checks=[self.a,command]),
            call('run_command',argv=[sys.executable,'-c','print("inspection")'])])
        self.assertEqual((self.root/'counter.txt').read_text(),'1')
        self.assertFalse(self.agent.state['verified'])
        self.assertFalse(self.agent.state['check_proofs'])

    async def test_pure_checks_in_a_command_batch_observe_the_final_files(self):
        self.agent._plan({'steps':['Measure'],'criteria':['A content']})
        command = {'kind':'command','criterion':'A content','argv':[sys.executable,'-c',
            'from pathlib import Path; Path("a.txt").write_text("changed"); Path("counter.txt").write_text("1")']}
        result = await self.agent._execute('verify',{'checks':[self.a,command]})
        self.assertFalse(result['passed'])
        self.assertFalse(result['checks'][0]['passed'])
        self.assertEqual(result['checks'][0]['observed'],'changed')
        self.assertTrue(result['checks'][0]['refreshed_after_commands'])
        self.assertEqual((self.root/'counter.txt').read_text(),'1')

    async def test_command_verification_invalidates_an_earlier_other_criterion(self):
        command = {'kind':'command','criterion':'B file','argv':[sys.executable,'-c',
            'from pathlib import Path; Path("a.txt").write_text("changed")']}
        await self.play([self.plan('A content','B file'),call('verify',checks=[self.a]),call('verify',checks=[command])])
        self.assertEqual(self.agent.state['verified'],['B file'])
        self.assertFalse(self.agent.state['check_proofs'])

    async def test_legacy_verified_state_without_fingerprints_is_invalidated(self):
        self.agent.state.update(criteria=['A content'],verified=['A content'],output_checks=[self.a])
        self.agent.state.pop('check_proofs')
        await self.agent._refresh_verified(5)
        self.assertFalse(self.agent.state['verified'])
        self.assertFalse(self.agent.state['output_checks'])

    async def test_failed_check_discards_its_old_fingerprint(self):
        self.agent._plan({'steps':['Measure'],'criteria':['A content']})
        good = await self.agent._execute('verify',{'checks':[self.a]})
        self.agent._record_verification(good,1)
        wrong = await self.agent._execute('verify',{'checks':[{**self.a,'equals':'wrong'}]})
        self.agent._record_verification(wrong,2)
        self.assertFalse(self.agent.state['verified'])
        self.assertFalse(self.agent.state['check_proofs'])
        await self.agent._refresh_verified(3)
        self.assertFalse(self.agent.state['verified'])

    async def test_builtin_discovery_and_inspection_respect_permissions_and_worker_depth(self):
        items = await self.agent._execute('list_tools',{'query':'create_skill'})
        self.assertTrue(any(x['name']=='create_skill' and x['origin']=='builtin' for x in items))
        definition = await self.agent._execute('inspect_tool',{'name':'create_skill'})
        self.assertEqual(set(definition['arguments']['required']),{'name','description','instructions'})
        self.assertIn('kind=skill',definition['description'])
        self.agent._plan({'steps':['Inspect'],'criteria':['Contract understood']})
        with self.assertRaisesRegex(ValueError,'direct JSON call'):
            await self.agent._execute('run_tool',{'name':'create_skill','argv':[]})
        self.agent.permissions = 'SAFE'
        items = await self.agent._execute('list_tools',{'query':'create_skill'})
        self.assertFalse(any(x['name']=='create_skill' for x in items))
        with self.assertRaises(PermissionError):
            await self.agent._execute('inspect_tool',{'name':'create_skill'})
        self.agent.permissions,self.agent.depth = 'AUTONOMOUS',1
        items = await self.agent._execute('list_tools',{})
        self.assertFalse(any(x['name']=='spawn_agent' for x in items))

    async def test_skill_discovery_and_checks_measure_real_bytes_and_retain_resource_references(self):
        self.agent._plan({'steps':['Save and inspect'],'criteria':['Skill exists']})
        args = {'name':'AuditRows','description':'Read a table','instructions':'Première\r\nligne'}
        created = await self.agent._execute('create_skill',args)
        path = Path(created['path']); original = path.read_bytes()
        info = await self.agent._execute('list_skills',{})
        skill = next(s for s in info['skills'] if s['name']=='AuditRows')
        self.assertEqual(skill['sha256'],hashlib.sha256(original).hexdigest())
        self.assertEqual(skill['file'],str(path))
        check = {'kind':'skill','name':'AuditRows','criterion':'Skill exists'}
        first = await self.agent._execute('verify',{'checks':[check]})
        self.assertTrue(first['passed'])
        self.agent._record_verification(first,1)
        path.write_bytes(original+b'Additional text\n')
        await self.agent._refresh_verified(2)
        self.assertFalse(self.agent.state['verified'])
        self.assertEqual(path.read_bytes(),original+b'Additional text\n')
        self.agent.state['messages'] = [{'role':'system','content':'protocol'},{'role':'user','content':'Original goal'}]
        self.assertIn('AuditRows',json.dumps(self.agent._messages()))
        self.assertIn('known_resources',json.dumps(self.agent._messages()))

    async def test_a_missing_skill_is_not_reported_as_verified(self):
        result = await self.agent._execute('verify',{'checks':[{'kind':'skill','name':'missing'}]})
        self.assertFalse(result['passed'])
        self.assertIsNone(result['checks'][0]['observed'])
