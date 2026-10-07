"""Filesystem discovery and research progress without models or media engines."""
from dataclasses import replace
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import AsyncMock, patch

from agi_core.mission_agent import AutonomousMissionAgent
from agi_core.mission_tools import TextFormatError


class EnvironmentDiscovery(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.root = Path(self.folder.name)
        self.workspace = self.root/'requested-output'
        self.workspace.mkdir()
        self.services = self.root/'services'
        self.services.mkdir()
        self.env = patch.dict(os.environ, {'AURORA_DATA_DIR':str(self.root/'runtime')})
        self.env.start()
        self.agent = AutonomousMissionAgent('mis_discovery', 'Créer un modèle 3D', str(self.workspace), 'fixture:local')
        self.agent._emit = AsyncMock()
        self.agent.tools.services = self.services

    async def asyncTearDown(self):
        self.env.stop()
        self.folder.cleanup()

    async def test_initial_discovery_reads_sources_without_importing_or_running_them(self):
        (self.services/'scene_3d.py').write_text('"""Generate a 3D scene using an explicit output directory."""\nraise RuntimeError("Do not import during discovery")\n')
        await self.agent._observe_environment()
        tools = self.agent.state['environment']['source_tools']
        self.assertEqual(tools[0]['name'], 'scene_3d.py')
        self.assertEqual(tools[0]['availability'], 'source_present_not_runtime_verified')
        self.assertEqual(self.agent._runtime_paths()['script_execution_directory'], str(self.workspace))
        self.assertEqual(list(self.workspace.iterdir()), [])
        self.agent.state['messages'] = [{'role':'system','content':self.agent._system_prompt()},
                                        {'role':'user','content':self.agent.request_text}]
        self.assertIn('scene_3d.py', json.dumps(self.agent._messages()))
        reviewed = self.agent._review_payload('Cannot create anything', [], 'Review the original request')
        self.assertIn('scene_3d.py', reviewed['available_source_tools'])

    async def test_multitoken_discovery_finds_capabilities_without_exact_prompt_matching(self):
        (self.services/'mesh_export.py').write_text('"""Create a mesh and export GLB geometry."""\n')
        (self.services/'csv_total.py').write_text('"""Compute CSV totals."""\n')
        result = self.agent.tools.inventory('find mesh export GLB for my requested object')
        self.assertEqual(result[0]['name'], 'mesh_export.py')
        self.assertTrue(Path(result[0]['path']).is_file())
        self.assertNotIn('csv_total.py', [item['name'] for item in result])

    async def test_missing_path_reports_real_parent_and_does_not_create_a_fake_file(self):
        target = 'not-created-yet/scene.blend'
        info = await self.agent._execute('inspect_path', {'path':target})
        self.assertFalse(info['exists'])
        self.assertEqual(info['nearest_existing_parent'], str(self.workspace))
        with self.assertRaises(FileNotFoundError) as failure:
            await self.agent._execute('inspect_csv', {'path':target})
        self.assertIn(str(self.workspace), str(failure.exception))
        self.assertIn('inspect_path', str(failure.exception))
        self.assertFalse((self.workspace/target).exists())
        with self.assertRaises(PermissionError):
            await self.agent._execute('inspect_path', {'path':'../outside'})

    async def test_binary_assets_are_not_parsed_as_csv_or_text_regardless_of_filename(self):
        for name in ('scene.blend', 'misleading.csv'):
            (self.workspace/name).write_bytes(b'BINARY\x00\x01\xffcontent')
            for tool in ('read_file', 'inspect_csv'):
                with self.subTest(name=name, tool=tool):
                    with self.assertRaisesRegex(TextFormatError, 'Binary input'):
                        await self.agent._execute(tool, {'path':name})
            observed = await self.agent._execute('inspect_path', {'path':name})
            self.assertEqual(observed['bytes'], len(b'BINARY\x00\x01\xffcontent'))
        (self.workspace/'table.data').write_text('name,count\nactual,4\n')
        table = await self.agent._execute('inspect_csv', {'path':'table.data','integer_columns':['count']})
        self.assertEqual(table['integer_columns']['count']['sum'], 4)

    async def test_non_utf8_diagnostic_excerpt_preserves_bytes_but_cannot_be_used_as_csv(self):
        (self.workspace/'unknown-encoding.txt').write_bytes(b'text\r\n\xff')
        observed = await self.agent._execute('read_file', {'path':'unknown-encoding.txt'})
        self.assertIn('non_utf8_lossy_excerpt', observed['encoding_status'])
        self.assertIn('\r\n', observed['content'])
        with self.assertRaises(TextFormatError):
            await self.agent._execute('inspect_csv', {'path':'unknown-encoding.txt'})

    async def test_script_relative_output_uses_the_requested_workspace(self):
        (self.services/'export.py').write_text('from pathlib import Path\nPath("generated.asset").write_bytes(b"actual result")\n')
        await self.agent._execute('set_plan', {'steps':['Execute the inspected exporter'],
                                               'criteria':['An asset is saved in the requested workspace']})
        info = await self.agent._execute('inspect_tool', {'name':'export.py'})
        self.assertEqual(info['execution_directory'], str(self.workspace))
        await self.agent._execute('run_tool', {'name':'export.py'})
        self.assertEqual((self.workspace/'generated.asset').read_bytes(), b'actual result')
        self.assertFalse((self.services/'generated.asset').exists())
        listing = await self.agent._execute('list_files', {})
        self.assertEqual(listing[0]['path'], str(self.workspace/'generated.asset'))
        self.assertEqual(listing[0]['relative_path'], 'generated.asset')

    async def test_research_needs_a_plan_and_cannot_bypass_the_executor(self):
        self.assertNotIn('search_web', self.agent._available_tools())
        self.assertNotIn('fetch_url', self.agent._available_tools())
        with patch.object(self.agent.tools, 'fetch', AsyncMock()) as fetch:
            for tool,args in [('search_web',{'query':'missing library interface'}), ('fetch_url',{'url':'https://example.org'})]:
                with self.assertRaisesRegex(ValueError, 'Set a plan'):
                    await self.agent._execute(tool, args)
            fetch.assert_not_awaited()

    def search_page(self, order=('one','two')):
        return {'content':''.join('<a class="result__a" href="https://example.org/'+word+'">'+word+'</a>' for word in order),
                'retrieved_at':123.0}

    async def test_identical_research_reuses_observations_and_explicit_refresh_is_possible(self):
        await self.agent._execute('set_plan', {'steps':['Research the missing export API'], 'criteria':['A consulted source supports the export API']})
        with patch.object(self.agent.tools, 'fetch', AsyncMock(return_value=self.search_page())) as fetch:
            first = await self.agent._execute('search_web', {'query':'export API'})
            cached = await self.agent._execute('search_web', {'query':'  EXPORT   api '})
            self.assertTrue(cached['cached'])
            self.assertEqual(first['results'], cached['results'])
            self.assertEqual(fetch.await_count, 1)
            await self.agent._execute('search_web', {'query':'export API','refresh':True})
            self.assertEqual(fetch.await_count, 2)
        with self.assertRaises(ValueError):
            await self.agent._execute('search_web', {'query':'export API','refresh':'true'})

    async def test_reworded_queries_and_reordered_links_do_not_hide_stagnation(self):
        self.agent.policy = replace(self.agent.policy, stall_attempts=2, recovery_attempts=0, max_steps=10)
        await self.agent._execute('set_plan', {'steps':['Find the missing technique'], 'criteria':['A source has been consulted']})
        calls = iter({'tool':'search_web','args':{'query':f'new wording {i}'}} for i in range(10))
        async def chunks(messages):
            yield json.dumps(next(calls))
        pages = [self.search_page(order) for order in [('one','two'),('two','one')]*5]
        with patch.object(self.agent, '_chat_chunks', chunks),patch.object(self.agent.tools, 'fetch', AsyncMock(side_effect=pages)):
            await self.agent.run()
        self.assertEqual(self.agent.state['action_count'], 4)
        self.assertEqual(self.agent.state['status'], 'failed')
        self.assertEqual(sorted(self.agent.state['research_urls']), ['https://example.org/one','https://example.org/two'])
        self.assertTrue(any(c.args[0]=='stagnation_notice' for c in self.agent._emit.await_args_list))

    async def test_invented_filenames_do_not_hide_repeated_missing_input(self):
        self.agent.policy = replace(self.agent.policy, stall_attempts=2, recovery_attempts=0, max_steps=10)
        calls = iter({'tool':'inspect_csv','args':{'path':f'invented-{i}.blend'}} for i in range(10))
        async def chunks(messages):
            yield json.dumps(next(calls))
        with patch.object(self.agent, '_chat_chunks', chunks):
            await self.agent.run()
        self.assertEqual(self.agent.state['action_count'], 3)
        self.assertEqual(self.agent.state['status'], 'failed')
        self.assertFalse(list(self.workspace.iterdir()))
