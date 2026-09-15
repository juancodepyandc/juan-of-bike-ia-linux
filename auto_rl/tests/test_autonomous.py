import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import torch
from safetensors.torch import save_file
from auto_rl.autonomous_train import diagnose,correction,supervise
from auto_rl.config import defaults
from auto_rl.storage import atomic_json,read_json,file_hash


class AutonomousTests(unittest.TestCase):
    def test_corrections_are_bounded_and_never_change_audit_or_model_identity(self):
        c=defaults('3d')
        oom=diagnose('torch.OutOfMemoryError: CUDA out of memory')
        self.assertEqual(correction(c,oom,1),{'offload_saved_tensors':True})
        self.assertIsNone(correction(c,oom,2))
        numeric=diagnose('Gradients toujours non finis après 12 réductions du facteur FP16')
        self.assertLess(correction(c,numeric,1)['train_learning_rate'],c['train_learning_rate'])
        self.assertIsNone(correction(c,numeric,3))
        for msg in ['empreinte incompatible','run rm -rf /','A new unrecognized exception']:
            self.assertEqual(diagnose(msg)['action'],'stop')
        self.assertEqual(diagnose('',-9)['action'],'stop')

    def test_supervisor_recovers_cuda_error_without_assistant_or_changing_data(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)/'inputs';root.mkdir()
            save_file({'weights':torch.zeros(3)},str(root/'initial.safetensors'))
            save_file({'chosen':torch.ones(3),'rejected':torch.zeros(3),'cond':torch.ones(1)},str(root/'pair.safetensors'))
            records=[{'split':'train','tensors':'pair.safetensors'},{'split':'validation','tensors':'pair.safetensors'}]
            calls=[]
            class Attempt:
                def __init__(self,args,stdout,**kwargs):
                    c=read_json(args[args.index('--config')+1]);calls.append(c)
                    self.returncode=1 if len(calls)==1 else 0
                    self.pid=999999999
                    if self.returncode:stdout.write('CUDA out of memory\n');stdout.flush()
                    else:
                        out=Path(args[args.index('--output')+1]);out.mkdir()
                        save_file({'weights':torch.ones(3)*.01},str(out/'candidate.safetensors'))
                        metrics={'completed_epochs':3,'best_validation_loss':.69,'termination_reason':'time_limit',
                                 'candidate_sha256':file_hash(out/'candidate.safetensors')}
                        atomic_json(out/'training_metrics.json',metrics)
                    assert 'PYTHONPATH' in kwargs['env']
                def poll(self):return self.returncode
            config=defaults('3d');output=Path(d)/'output';before=file_hash(root/'pair.safetensors')
            with patch('auto_rl.autonomous_train.subprocess.Popen',Attempt):
                result=supervise(config,records,root,output,1800,lambda _:None)
            self.assertEqual(len(calls),2)
            self.assertTrue(calls[1]['offload_saved_tensors'])
            self.assertEqual(calls[0]['generation'],calls[1]['generation'])
            self.assertEqual(calls[0]['models'],calls[1]['models'])
            self.assertEqual(result['completed_epochs'],3)
            self.assertEqual(result['corrections'][0]['code'],'cuda_memory')
            self.assertEqual(file_hash(root/'pair.safetensors'),before)
            self.assertEqual(read_json(output/'autonomy.json')['promotion'],'audit_required')

    def test_unknown_error_stops_after_one_attempt(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)/'inputs';root.mkdir()
            save_file({'weights':torch.zeros(3)},str(root/'initial.safetensors'))
            (root/'pair.safetensors').write_bytes(b'fixture')
            class Failed:
                pid=999999999;returncode=1
                def __init__(self,args,stdout,**kwargs):stdout.write('Unknown exception\n');stdout.flush()
                def poll(self):return 1
            with patch('auto_rl.autonomous_train.subprocess.Popen',Failed) as factory:
                with self.assertRaisesRegex(RuntimeError,'Aucune sauvegarde'):
                    supervise(defaults('3d'),[{'tensors':'pair.safetensors'}],root,Path(d)/'output',1800,lambda _:None)
            record=read_json(Path(d)/'output/autonomy.json')
            self.assertEqual(len(record['attempts']),1)
            self.assertEqual(record['stopped_reason'],'unknown')


if __name__=='__main__':unittest.main()
