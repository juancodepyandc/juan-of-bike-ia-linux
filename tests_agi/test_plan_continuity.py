"""Observed replanning and repeated generation must preserve actual progress."""
from copy import deepcopy
import asyncio
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import AsyncMock, patch

from agi_core.mission_agent import AutonomousMissionAgent
from agi_core.mission_tools import digest_file


class PlanContinuity(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.root = Path(self.folder.name).resolve()
        self.env = patch.dict(os.environ,{'AURORA_DATA_DIR':str(self.root/'runtime')})
        self.env.start()
        self.agent = AutonomousMissionAgent('mis_continuity','Create the requested asset',str(self.root),'fixture:local')
        self.agent._emit = AsyncMock()
        self.plan = {'steps':['Inspect and execute the actual exporter'],'criteria':['Requested asset conforms']}
        await self.agent._execute('set_plan',self.plan)
        self.agent.state.update(verified=['Requested asset conforms'],last_verify=4,
                                output_checks=[{'kind':'file','path':'saved.asset'}],
                                check_proofs={'Requested asset conforms':{'hash':'observed'}},
                                request_audit={'passed':True,'number':4})

    async def asyncTearDown(self):
        self.env.stop()
        self.folder.cleanup()

    async def test_existing_plan_cannot_reset_progress_or_weaken_criteria(self):
        before = deepcopy(self.agent.state)
        self.assertNotIn('set_plan',self.agent._available_tools())
        self.assertIn('revise_plan',self.agent._available_tools())
        result = await self.agent._execute('set_plan',self.plan)
        self.assertTrue(result['reused'])
        self.assertEqual(self.agent.state,before)
        self.assertEqual(self.agent._emit.await_count,1)
        for replacement in ({**self.plan,'criteria':['Any file exists']},{**self.plan,'steps':['Start over']}):
            with self.assertRaisesRegex(ValueError,'already accepted'):
                await self.agent._execute('set_plan',replacement)
        self.assertEqual(self.agent.state,before)

    async def test_revision_requires_fresh_execution_evidence_and_preserves_proofs(self):
        observed = await self.agent._execute('inspect_path',{'path':'.'})
        self.agent.state['evidence'] = [{'id':'ev_inspection','tool':'inspect_path','ok':True,'result':observed,'action_number':5}]
        self.agent.state['action_count'] = 5
        preserved = {k:deepcopy(self.agent.state[k]) for k in ('criteria','verified','output_checks','check_proofs','last_verify','request_audit','required_tools')}
        revision = {'steps':['Use the observed exporter path'],'reason':'The actual script directory differs from the guess','evidence_ids':['ev_inspection']}
        result = await self.agent._execute('revise_plan',revision)
        self.assertFalse(result['changed'])
        self.assertEqual({k:self.agent.state[k] for k in preserved},preserved)
        with self.assertRaisesRegex(ValueError,'fresh tool evidence'):
            await self.agent._execute('revise_plan',{**revision,'steps':['A differently worded plan']})
        with self.assertRaisesRegex(ValueError,'fresh tool evidence'):
            await self.agent._execute('revise_plan',{**revision,'evidence_ids':['invented']})
        self.assertEqual(self.agent._progress_observation('set_plan',self.plan,{},True),
                         self.agent._progress_observation('revise_plan',revision,result,True))

    async def test_images_reuse_unchanged_bytes_and_new_generations_preserve_previous_files(self):
        self.agent.tools.services = self.root/'services'
        self.agent.tools.services.mkdir()
        (self.agent.tools.services/'image_module_engine.py').write_text('"""Fixture source identity."""\n')
        async def generate(argv,**kwargs):
            target = Path(argv[-1]);target.mkdir(parents=True)
            (target/'image.png').write_bytes(b'fixture image bytes')
        with patch.object(self.agent,'_run_process',AsyncMock(side_effect=generate)) as process:
            first = await self.agent._execute('generate_image',{'prompt':'Requested reference'})
            reused = await self.agent._execute('generate_image',{'prompt':'Requested reference'})
            self.assertTrue(reused['reused']);self.assertFalse(reused['changed'])
            self.assertEqual(process.await_count,1)
            another = await self.agent._execute('generate_image',{'prompt':'Requested reference','regenerate':True})
            self.assertNotEqual(first['path'],another['path'])
            self.assertEqual(digest_file(Path(first['path'])),first['sha256'])
            Path(another['path']).write_bytes(b'external modification')
            fresh = await self.agent._execute('generate_image',{'prompt':'Requested reference'})
            self.assertFalse(fresh['reused']);self.assertEqual(process.await_count,3)
            self.assertEqual(Path(another['path']).read_bytes(),b'external modification')
            with self.assertRaisesRegex(ValueError,'escapes'):
                await self.agent._execute('generate_image',{'prompt':'Requested reference','folder':'../outside'})
        self.agent.state['evidence'] = [{'tool':'generate_image','ok':True,'result':first}]
        self.agent.state['resources'] = {}
        await self.agent._observe_environment()
        self.assertEqual(next(iter(self.agent.state['resources'].values()))['path'],first['path'])

    async def test_inspected_script_paths_remain_available_after_history_compaction(self):
        self.agent.tools.services = self.root/'services'
        self.agent.tools.services.mkdir()
        (self.agent.tools.services/'export.py').write_text('import argparse\np=argparse.ArgumentParser()\np.add_argument("--output-dir")\n')
        info = await self.agent._execute('inspect_tool',{'name':'export.py'})
        self.agent.state['messages'] = [{'role':'system','content':self.agent._compact_system_prompt()},{'role':'user','content':self.agent.request_text}]
        self.assertIn(info['path'],str(self.agent._messages()))
        self.assertIn('--output-dir',str(self.agent._messages()))

    async def test_interrupted_generation_cannot_bypass_replay_guard_with_a_new_directory(self):
        self.agent.tools.services = self.root/'services'
        self.agent.tools.services.mkdir()
        (self.agent.tools.services/'image_module_engine.py').write_text('"""Fixture engine."""\n')
        with patch.object(self.agent,'_run_process',AsyncMock(side_effect=asyncio.CancelledError)) as process:
            with self.assertRaises(asyncio.CancelledError):
                await self.agent._execute('generate_image',{'prompt':'Requested reference'})
            with self.assertRaisesRegex(RuntimeError,'automatic replay is disabled'):
                await self.agent._execute('generate_image',{'prompt':'Requested reference','regenerate':True})
            self.assertEqual(process.await_count,1)
