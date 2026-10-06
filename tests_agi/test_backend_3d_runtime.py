"""Bridge paths, current-run delivery and startup failures without AI services."""
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from flask import Flask


ROOT = Path(__file__).resolve().parents[1]


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


# CORS middleware is outside these local Flask/runtime contracts and is not
# installed in the CLI test environment. No bridge startup code is executed.
with patch.dict(sys.modules, {'flask_cors':SimpleNamespace(CORS=lambda app, **kwargs:None)}):
    BRIDGE = load_module('_test_3d_bridge', ROOT/'application/bridge_server.py')
with patch.dict(sys.modules, {'bridge_server': BRIDGE}), patch.dict(os.environ, {'AURORA_VITE_SUPERVISOR': '0'}):
    VITE = load_module('_test_3d_routes', ROOT/'application/routes/vite_bp_routes.py')
    COMFY = load_module('_test_comfy_routes', ROOT/'application/routes/comfy_life_bp_routes.py')


class ThreeDRoutes(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.repo = Path(folder.name)/'repo'
        self.workspace = self.repo/'application'
        self.services = self.workspace/'python-services'
        self.services.mkdir(parents=True)
        workspace_patch = patch.object(VITE, 'WORKSPACE', str(self.workspace))
        workspace_patch.start()
        self.addCleanup(workspace_patch.stop)
        real_run = subprocess.run
        def fixture_command(argv, *args, **kwargs):
            self.assertEqual(Path(argv[1]).resolve().parent, self.services.resolve(), 'Only temporary fixture scripts may execute')
            return real_run(argv, *args, **kwargs)
        commands = patch.object(VITE.subprocess, 'run', side_effect=fixture_command)
        commands.start()
        self.addCleanup(commands.stop)
        app = Flask(__name__)
        app.register_blueprint(VITE.vite_bp)
        self.client = app.test_client()
        for name in ('actor.glb', 'target.glb', 'reference.png'):
            (self.workspace/name).write_bytes(b'fixture input')

    def script(self, name, source=None):
        (self.services/name).write_text(source or 'import json; print(json.dumps({"ok": True}))', encoding='utf-8')

    def test_pipeline_runs_from_application_directory_and_parses_progress(self):
        self.script('aurora_3d_pipeline.py', 'import json,sys\nprint("PROGRESS:fixture")\nprint(json.dumps({"ok":True,"run_id":sys.argv[sys.argv.index("--run-id")+1]}))\n')
        response = self.client.post('/api/3d/run-pipeline', json={'prompt':'fixture','run_id':'run_current'})
        self.assertEqual(response.status_code, 200, response.json)
        self.assertEqual(response.json['pipeline']['run_id'], 'run_current')
        self.assertTrue((self.workspace/'output/3d/generations/run_current').is_dir())
        self.assertFalse((self.workspace/'routes/output').exists())

    def test_composition_resolves_relative_inputs_and_keeps_process_failure(self):
        self.script('scene_composer.py', 'import json,sys\nprint("AURORA_SCENE_RESULT:"+json.dumps({"ok":True}))\n')
        body = {'actor_glb':'actor.glb','target_glb':'target.glb','instruction':'fixture'}
        response = self.client.post('/api/3d/compose-scene', json=body)
        self.assertEqual(response.status_code, 200, response.json)
        self.assertTrue(Path(response.json['output']).resolve().is_relative_to(
            (self.workspace/'output/3d/scenes').resolve()))
        self.script('scene_composer.py', 'import json,sys\nprint("AURORA_SCENE_RESULT:"+json.dumps({"ok":True}))\nsys.exit(9)\n')
        response = self.client.post('/api/3d/compose-scene', json=body)
        self.assertEqual(response.status_code, 500)
        self.assertFalse(response.json['ok'])
        self.assertEqual(response.json['returncode'], 9)

    def test_related_3d_routes_execute_scripts_in_application(self):
        cases = [
            ('mesh_run_index.py','GET','/api/3d/run-index',None),
            ('score_history.py','GET','/api/3d/score-history',None),
            ('mesh_quality_score.py','POST','/api/3d/mesh-score',{'mesh_path':'actor.glb'}),
            ('mesh_compare.py','POST','/api/3d/mesh-compare',{'left':'actor.glb','right':'target.glb'}),
            ('mesh_sharpen.py','POST','/api/3d/mesh-sharpen',{'mesh':'actor.glb','output':'out.glb'}),
            ('three_d_regression_suite.py','POST','/api/3d/regression-suite',{'mesh_map':{'fixture':'actor.glb'}}),
            ('auto_validate_mesh.py','POST','/api/3d/auto-validate',{'mesh_path':'actor.glb','prompt':'fixture'}),
        ]
        for name, method, endpoint, body in cases:
            self.script(name)
            with self.subTest(endpoint=endpoint):
                response = self.client.open(endpoint, method=method, json=body)
                self.assertEqual(response.status_code, 200, response.json)

    def test_motion_routes_import_and_execute_application_helpers(self):
        self.script('motion_parser.py', 'def parse_custom_motion_prompt(prompt):\n    return {"fixture":prompt}\nif __name__ == "__main__":\n    print("PARSER_SELF_TEST_OK")\n')
        self.script('motion_baker.py', 'def compile_motion_payload(motion):\n    return {"fixture":motion}\nif __name__ == "__main__":\n    print("SELF_TEST_OK")\n')
        old_path = sys.path[:]
        try:
            with patch.dict(sys.modules):
                sys.modules.pop('motion_parser',None)
                sys.modules.pop('motion_baker',None)
                compiled = self.client.post('/api/3d/motion-compile',json={'motion':{'fixture':True}})
                self.assertEqual(compiled.status_code,200,compiled.json)
                self.assertEqual(compiled.json['compiled'],{'fixture':{'fixture':True}})
                parsed = self.client.post('/api/3d/motion-resolve-prompt',json={'prompt':'fixture motion'})
                self.assertEqual(parsed.json['resolved'],{'fixture':'fixture motion'})
                for endpoint in ('motion-parser-self-test','motion-self-test'):
                    response = self.client.get('/api/3d/'+endpoint)
                    self.assertEqual(response.status_code,200,response.json)
                    self.assertTrue(response.json['ok'])
        finally:
            sys.path[:] = old_path

    def motion_intent_scripts(self, baker_exit=0):
        self.script('motion_intent_classifier.py', '''import json
print(json.dumps({"schema":"aurora.motion-intent.v1","category":"mechanical_simple","confidence":0.95}))
''')
        self.script('motion_intent_baker.py', '''import json, sys
from pathlib import Path
args = sys.argv
intent = json.loads(Path(args[args.index('--intent')+1]).read_text())
assert intent['category'] == 'mechanical_simple'
source = Path(args[args.index('--input')+1])
output = Path(args[args.index('--output')+1])
output.write_bytes(source.read_bytes() + b' baked fixture')
print(json.dumps({"ok":True,"output":str(output)}))
sys.exit(%d)
''' % baker_exit)

    def test_motion_intent_classifies_with_application_script(self):
        self.motion_intent_scripts()
        response = self.client.post('/api/3d/motion-intent', json={'prompt':'fixture motion'})
        self.assertEqual(response.status_code, 200, response.json)
        self.assertEqual(response.json['intent']['category'], 'mechanical_simple')

    def test_custom_and_auto_motion_execute_classifier_and_baker(self):
        self.motion_intent_scripts()
        for endpoint in ('custom-motion', 'auto-motion-bake'):
            with self.subTest(endpoint=endpoint):
                output = self.workspace/(endpoint+'.glb')
                response = self.client.post('/api/3d/'+endpoint, json={
                    'prompt':'fixture', 'custom_motion_text':'rotate',
                    'input_glb':str(self.workspace/'actor.glb'), 'output_glb':str(output),
                })
                self.assertEqual(response.status_code, 200, response.json)
                self.assertTrue(response.json['bake']['ok'])
                self.assertEqual(output.read_bytes(), b'fixture input baked fixture')
                if endpoint == 'auto-motion-bake':
                    self.assertTrue(response.json['decision']['baked'])
                    self.assertEqual(response.json['glb_path'], str(output))

    def test_failed_motion_process_cannot_report_success(self):
        self.motion_intent_scripts(baker_exit=9)
        for endpoint in ('custom-motion', 'auto-motion-bake'):
            with self.subTest(endpoint=endpoint):
                output = self.workspace/(endpoint+'.glb')
                response = self.client.post('/api/3d/'+endpoint, json={
                    'prompt':'fixture', 'custom_motion_text':'rotate',
                    'input_glb':str(self.workspace/'actor.glb'), 'output_glb':str(output),
                })
                self.assertFalse(response.json['bake']['ok'])
                self.assertEqual(response.json['bake']['returncode'], 9)
                if endpoint == 'auto-motion-bake':
                    self.assertFalse(response.json['decision']['baked'])
                    self.assertEqual(response.json['glb_path'], str(self.workspace/'actor.glb'))

    def test_paths_with_matching_prefix_and_symlinks_are_rejected(self):
        self.script('scene_composer.py')
        outside = self.repo.with_name('repo-other')
        outside.mkdir()
        mesh = outside/'outside.glb'
        mesh.write_bytes(b'outside')
        body = {'actor_glb':str(mesh),'target_glb':'target.glb','instruction':'fixture'}
        self.assertEqual(self.client.post('/api/3d/compose-scene', json=body).status_code, 404)
        try:
            (self.workspace/'link.glb').symlink_to(mesh)
        except OSError:
            return  # Windows may not grant symlink creation to the test process.
        body['actor_glb'] = 'link.glb'
        self.assertEqual(self.client.post('/api/3d/compose-scene', json=body).status_code, 404)

    def test_run_directory_cannot_escape_through_name_or_symlink(self):
        self.script('aurora_3d_pipeline.py')
        for run_id in ('../outside','..','folder/run','folder\\run'):
            with self.subTest(run_id=run_id):
                response = self.client.post('/api/3d/run-pipeline', json={'prompt':'fixture','run_id':run_id})
                self.assertEqual(response.status_code, 400)
        generations = self.workspace/'output/3d/generations'
        generations.mkdir(parents=True)
        try:
            (generations/'escape').symlink_to(self.repo.parent, target_is_directory=True)
        except OSError:
            return
        response = self.client.post('/api/3d/run-pipeline', json={'prompt':'fixture','run_id':'escape'})
        self.assertEqual(response.status_code, 400)


class ExternalDelivery(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.workspace = Path(folder.name)/'application'
        self.output = self.workspace/'output/3d'
        self.output.mkdir(parents=True)
        for attribute, value in (('WORKSPACE', str(self.workspace)), ('_EXT_3D_DIR', str(self.output)), ('_EXT_3D_JOBS', {})):
            mocked = patch.object(BRIDGE, attribute, value)
            mocked.start()
            self.addCleanup(mocked.stop)
        real_run = subprocess.run
        def fixture_command(argv, *args, **kwargs):
            self.assertEqual(Path(argv[1]).resolve().parent, (self.workspace/'python-services').resolve(), 'Only temporary fixture scripts may execute')
            return real_run(argv, *args, **kwargs)
        commands = patch.object(BRIDGE.subprocess, 'run', side_effect=fixture_command)
        commands.start()
        self.addCleanup(commands.stop)

    def job(self):
        BRIDGE._EXT_3D_JOBS['fixture'] = {'run_id':'run_current','prompt':'fixture','force':False,'subject_kind':None}
        return BRIDGE._EXT_3D_JOBS['fixture']

    def test_current_nested_delivery_uses_last_json_after_progress(self):
        services = self.workspace/'python-services'
        services.mkdir()
        (services/'aurora_3d_pipeline.py').write_text('import json,sys\nfrom pathlib import Path\nr=sys.argv[sys.argv.index("--run-id")+1]\np=Path(sys.argv[sys.argv.index("--output-dir")+1])/r/"modele"/"mesh final.glb"\np.parent.mkdir(parents=True)\np.write_bytes(b"glTF fixture")\nprint("PROGRESS:fixture")\nprint(json.dumps({"ok":True,"run_id":r,"final_mesh":str(p),"final_score":90},indent=2))\n', encoding='utf-8')
        job = self.job()
        (self.output/'run_current_old_mesh.glb').write_bytes(b'old root output')
        BRIDGE._ext_3d_worker('fixture')
        self.assertEqual(job['state'], 'done', job)
        self.assertEqual(job['attempts'], 1)
        self.assertEqual(job['glb'], 'run_current/modele/mesh final.glb')
        self.assertIn('mesh%20final.glb', job['glb_url'])

    def test_result_must_name_successful_current_run_and_contained_glb(self):
        mesh = self.output/'run_current/modele/final.glb'
        mesh.parent.mkdir(parents=True)
        mesh.write_bytes(b'glTF fixture')
        result = {'ok':True,'run_id':'run_current','final_mesh':str(mesh)}
        self.assertEqual(BRIDGE._ext_3d_pick_glb('run_current',result), 'run_current/modele/final.glb')
        for bad in (None,{**result,'ok':False},{**result,'run_id':'old'},
                    {**result,'final_mesh':str(self.output/'run_current_old.glb')},
                    {**result,'final_mesh':str(self.workspace/'outside.glb')}):
            with self.subTest(result=bad):
                self.assertIsNone(BRIDGE._ext_3d_pick_glb('run_current',bad))
        outside = self.workspace/'outside.glb'
        outside.write_bytes(b'outside')
        try:
            (mesh.parent/'escape.glb').symlink_to(outside)
        except OSError:
            return
        self.assertIsNone(BRIDGE._ext_3d_pick_glb('run_current',{**result,'final_mesh':str(mesh.parent/'escape.glb')}))

    def test_failed_process_cannot_deliver_old_root_glb(self):
        services = self.workspace/'python-services'
        services.mkdir()
        (services/'aurora_3d_pipeline.py').write_text('import json,sys\nprint(json.dumps({"ok":False,"error":"CUDA driver unavailable"}))\nsys.exit(1)\n', encoding='utf-8')
        job = self.job()
        (self.output/'run_current_mesh.glb').write_bytes(b'old output')
        BRIDGE._ext_3d_worker('fixture')
        self.assertEqual(job['state'], 'failed')
        self.assertIn('CUDA driver unavailable', job['error'])
        self.assertNotIn('glb_url', job)

    def test_existing_run_requires_explicit_recovery(self):
        (self.workspace/'python-services').mkdir()
        (self.workspace/'python-services/aurora_3d_pipeline.py').write_text('raise RuntimeError("must not execute")')
        (self.output/'run_current').mkdir()
        job = self.job()
        with patch.object(BRIDGE.subprocess, 'run') as command:
            BRIDGE._ext_3d_worker('fixture')
        command.assert_not_called()
        self.assertEqual(job['state'], 'failed')
        self.assertIn('reprise explicite', job['error'])

    def test_parser_requires_complete_final_json_and_ignores_progress_excerpts(self):
        result = {'ok':True,'run_id':'current','audit_trail':[{'stage':'fixture'}]}
        output = 'PROGRESS:fake {"ok":true,"run_id":"old"}\n' + json.dumps(result,indent=2) + '\n'
        self.assertEqual(BRIDGE._ext_3d_pipeline_result(output), result)
        self.assertIsNone(BRIDGE._ext_3d_pipeline_result('PROGRESS:fake {"ok":true}\n'))
        self.assertIsNone(BRIDGE._ext_3d_pipeline_result('{"ok":true}\nPROGRESS:still running\n'))
        self.assertIsNone(BRIDGE._ext_3d_pipeline_result('PROGRESS:start\n{"ok":true'))


class ComfyStartup(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.root = Path(folder.name)
        for attribute, value in (('COMFYUI_PATH', str(self.root)), ('_comfyui_process', None),
                                 ('_comfyui_log_thread', None), ('_comfyui_start_result', {'state':'not_started','ready':False})):
            mocked = patch.object(BRIDGE, attribute, value)
            mocked.start()
            self.addCleanup(mocked.stop)
        probe = patch.object(BRIDGE, '_comfyui_is_ready', return_value=False)
        probe.start()
        self.addCleanup(probe.stop)
        helpers = patch.dict(sys.modules, {'comfy_runtime':SimpleNamespace(memory_args=lambda root:[])})
        helpers.start()
        self.addCleanup(helpers.stop)

    def test_process_exit_preserves_code_driver_error_and_bounded_log(self):
        (self.root/'main.py').write_text('import sys\nsys.stdout.write("x"*40000)\nsys.stderr.write("\\nCUDA driver unavailable\\n")\nsys.exit(11)\n', encoding='utf-8')
        self.assertFalse(BRIDGE._start_comfyui())
        outcome = BRIDGE._comfyui_start_diagnostics()
        self.assertEqual(outcome['state'], 'process_exited')
        self.assertEqual(outcome['returncode'], 11)
        self.assertIn('CUDA driver unavailable', outcome['error'])
        self.assertLessEqual((self.root/'aurora_bridge_startup.log').stat().st_size, BRIDGE._COMFYUI_LOG_BYTES)
        self.assertLessEqual(len(outcome['log_tail'].encode('utf-8')), 4096)
        app = Flask(__name__)
        app.register_blueprint(COMFY.comfy_life_bp)
        with patch.object(COMFY, '_start_comfyui', return_value=False):
            response = app.test_client().post('/api/comfyui/start')
        self.assertFalse(response.json['ready'])
        self.assertIn('CUDA driver unavailable', response.json['error'])

    def test_missing_installation_is_explicit_and_does_not_spawn(self):
        with patch.object(BRIDGE.subprocess, 'Popen') as command:
            self.assertFalse(BRIDGE._start_comfyui())
        command.assert_not_called()
        self.assertEqual(BRIDGE._comfyui_start_diagnostics()['state'], 'missing_installation')

    def test_existing_process_is_not_spawned_again_on_startup_timeout(self):
        (self.root/'main.py').write_text('fixture')
        process = SimpleNamespace(poll=lambda:None)
        with patch.object(BRIDGE,'_comfyui_process',process), patch.object(BRIDGE.subprocess,'Popen') as command, \
             patch.object(BRIDGE.time,'monotonic',side_effect=[0,61]):
            self.assertFalse(BRIDGE._start_comfyui())
        command.assert_not_called()
        self.assertEqual(BRIDGE._comfyui_start_diagnostics()['state'], 'startup_timeout')


class ModelSelection(unittest.TestCase):
    def setUp(self):
        self.models = [{'name':'qwen3-coder-next:q4_K_M','size':51_700_000_000},
                       {'name':'qwen3-coder:30b','size':18_000_000_000}]
        clean = patch.dict(os.environ, {'AURORA_DEFAULT_MODEL':''})
        clean.start()
        self.addCleanup(clean.stop)

    def test_no_driver_excludes_large_weights_and_does_not_refetch_tags(self):
        with patch.object(BRIDGE.psutil,'virtual_memory',return_value=SimpleNamespace(total=30*1024**3)), \
             patch.object(BRIDGE.subprocess,'run',side_effect=FileNotFoundError('nvidia-smi')), \
             patch.object(BRIDGE.requests,'get') as request:
            self.assertEqual(BRIDGE._ext_default_model(self.models),'qwen3-coder:30b')
        request.assert_not_called()
        observed = BRIDGE._ext_default_model_diagnostics()
        self.assertEqual(observed['nvidia_vram_bytes'],0)
        self.assertEqual(observed['excluded'][0]['name'],self.models[0]['name'])
        self.assertIn('not measured resident memory',observed['scope'])

    def test_observed_resources_are_reused_without_probes(self):
        with patch.object(BRIDGE.psutil,'virtual_memory') as memory, patch.object(BRIDGE.subprocess,'run') as gpu:
            selected = BRIDGE._ext_default_model(self.models,resources={'ram_total_bytes':64*1024**3,'nvidia_vram_bytes':0})
        self.assertEqual(selected,self.models[0]['name'])
        memory.assert_not_called()
        gpu.assert_not_called()

    def test_explicit_installed_environment_choice_is_preserved(self):
        with patch.dict(os.environ,{'AURORA_DEFAULT_MODEL':self.models[0]['name']}), patch.object(BRIDGE.subprocess,'run') as gpu:
            self.assertEqual(BRIDGE._ext_default_model(self.models),self.models[0]['name'])
        gpu.assert_not_called()
        with patch.dict(os.environ,{'AURORA_DEFAULT_MODEL':'not-installed'}), self.assertRaisesRegex(ValueError,'pas installé'):
            BRIDGE._ext_default_model(self.models)

    def test_all_excluded_candidates_fail_instead_of_reselecting_large_default(self):
        with self.assertRaisesRegex(ValueError,'Aucun modèle'):
            BRIDGE._ext_default_model(self.models[:1],resources={'ram_total_bytes':30*1024**3,'nvidia_vram_bytes':0})
        self.assertNotIn('model',BRIDGE._ext_default_model_diagnostics())

    def test_external_default_failure_returns_explained_503(self):
        with patch.object(BRIDGE,'_ext_auth',return_value=(True,{'origin':'','label':'fixture'},'')), \
             patch.object(BRIDGE,'_ext_origin_for',return_value=True), \
             patch.object(BRIDGE,'_ext_default_model',side_effect=ValueError('No eligible model')):
            response=BRIDGE.app.test_client().get('/api/ext/ping')
        self.assertEqual(response.status_code,503)
        self.assertEqual(response.json['error'],'No eligible model')


if __name__ == '__main__':
    unittest.main()
