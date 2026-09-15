"""Regression: failed self-play can become supervised training without redoing it."""
import json
import shutil
import tempfile
import unittest
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import patch
import torch
from auto_rl.config import defaults
from auto_rl.curriculum import build_tasks
from auto_rl.judges import ConversationJudge
from auto_rl.lora import LowRankAdapter
from auto_rl.storage import atomic_json, digest, file_hash, fingerprint


class ResumeTests(unittest.TestCase):
    def test_cached_rollouts_supervision_and_fresh_audit(self):
        from auto_rl.preference_cycle import execute_preference_cycle
        with tempfile.TemporaryDirectory() as directory:
            state = Path(directory)
            c = defaults('conversation')
            c.update(state_dir=str(state), mode='auto', execution='local', train_tasks=3,
                     eval_tasks=8, rollouts_per_task=2, local_epochs=1, minimum_free_gb=0,
                     resume_run='failed-run')
            tasks = build_tasks(c)
            old = state / 'runs/failed-run'
            (old / 'preferences').mkdir(parents=True)
            (old / 'self_play').mkdir()
            atomic_json(old / 'config.json', c)
            atomic_json(old / 'tasks/curriculum.json', tasks)
            base = state / 'base.safetensors';base.write_bytes(b'test base fingerprint')
            manifest = fingerprint([base])
            atomic_json(old / 'base_manifest.json', manifest)
            generation_id = digest({'hardware':{'gpu':'test GPU','torch':torch.__version__,'cuda':torch.version.cuda},
                                    'generation':c['generation'],'base':digest(manifest)})
            audited = []

            class Backend:
                suffix = '.txt'
                def __init__(self, *args):
                    self.model = torch.nn.Sequential(torch.nn.Linear(32,32))
                    self.adapter = LowRankAdapter(self.model,c['rank'],c['max_layers'],c['seed'])
                def close(self):self.adapter.close()
                def generate(self, task, seed, path, feedback=None):
                    if task['split'] != 'audit':
                        raise AssertionError('Training outputs must be reused from disk')
                    audited.append(task['id'])
                    Path(path).write_text(json.dumps(task['expected_json']))

            initial = Backend();initial.adapter.save(old/'preferences/initial.safetensors');initial.close()
            judge = ConversationJudge()
            for i, task in enumerate(tasks[:c['train_tasks']]):
                for j in range(c['rollouts_per_task']):
                    seed = c['seed'] + i*100+j
                    artifact = old/'self_play'/f"{task['id']}_graine_{seed}.txt"
                    artifact.write_text('{"answers":[]}')
                    atomic_json(artifact.with_suffix('.evaluation.json'), {
                        'task_id':task['id'],'prompt':task['prompt'],'seed':seed,
                        'artifact':str(artifact),'sha256':file_hash(artifact),
                        'generation_digest':generation_id,'judge':judge.score(artifact,task)})

            def train(config, records, root, output, *args):
                self.assertEqual(len(records),3)
                self.assertEqual({r['split'] for r in records},{'train','validation'})
                self.assertTrue(all(r['chosen_origin']=='verified_executable_oracle' for r in records))
                self.assertTrue(all(r['chosen_score']==1 and r['rejected_score']==0 for r in records))
                shutil.copy2(root/'initial.safetensors',output/'candidate.safetensors')
                return {'completed_epochs':1,'test_fixture':True}

            with ExitStack() as stack:
                stack.enter_context(patch('auto_rl.backends.resolve_paths',return_value={'conversation':str(base)}))
                stack.enter_context(patch('auto_rl.backends.make_backend',side_effect=Backend))
                stack.enter_context(patch('auto_rl.judges.make_judge',return_value=judge))
                stack.enter_context(patch('auto_rl.preference_train.train_preferences',side_effect=train))
                stack.enter_context(patch('auto_rl.results.publish_shortcuts',return_value=str(state)))
                stack.enter_context(patch('auto_rl.resources.release_idle_comfy',return_value=True))
                stack.enter_context(patch('torch.cuda.is_available',return_value=True))
                stack.enter_context(patch('torch.cuda.get_device_name',return_value='test GPU'))
                for method in ('reset_peak_memory_stats','synchronize','empty_cache'):
                    stack.enter_context(patch('torch.cuda.'+method))
                stack.enter_context(patch('torch.cuda.max_memory_allocated',return_value=0))
                outcome = execute_preference_cycle(c)
            self.assertEqual(outcome,'REJECT')  # Identical audit outputs never promote.
            self.assertEqual(len(audited),32)
            self.assertFalse((state/'registry/conversation.json').exists())
            # A process dying after training must resume its immutable candidate,
            # reuse the generated artifacts and recompute their current judges.
            from auto_rl.storage import read_json
            completed=read_json(state/'status.json')['run_id']
            c.update(resume_run=completed,resume_audit=True)
            with ExitStack() as stack:
                stack.enter_context(patch('auto_rl.backends.resolve_paths',return_value={'conversation':str(base)}))
                stack.enter_context(patch('auto_rl.backends.make_backend',side_effect=Backend))
                stack.enter_context(patch.object(Backend,'generate',side_effect=AssertionError('Cached audit must be reused')))
                stack.enter_context(patch('auto_rl.judges.make_judge',return_value=judge))
                train_mock=stack.enter_context(patch('auto_rl.preference_train.train_preferences',side_effect=AssertionError('Do not retrain')))
                stack.enter_context(patch('auto_rl.results.publish_shortcuts',return_value=str(state)))
                stack.enter_context(patch('auto_rl.resources.release_idle_comfy',return_value=True))
                stack.enter_context(patch('torch.cuda.is_available',return_value=True))
                stack.enter_context(patch('torch.cuda.get_device_name',return_value='test GPU'))
                stack.enter_context(patch('torch.cuda.empty_cache'))
                self.assertEqual(execute_preference_cycle(c),'REJECT')
                train_mock.assert_not_called()


if __name__ == '__main__':unittest.main()
