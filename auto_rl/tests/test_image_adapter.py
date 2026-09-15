import tempfile
import json
from pathlib import Path
import unittest
from unittest.mock import patch
import torch
from safetensors.torch import load_file
from auto_rl.adapters import WeightSubspace
from auto_rl.comfy_backend import export_comfy_lora
from auto_rl.surrogate import optimize
from auto_rl.config import defaults
from auto_rl.storage import atomic_json

class ImageAdapterTests(unittest.TestCase):
    def test_validated_graph_is_compatible_idempotent_and_does_not_mutate_input(self):
        from auto_rl.image_runtime import apply_validated_workflow
        model=torch.nn.Sequential(torch.nn.Linear(32,32,bias=False))
        adapter=WeightSubspace(model,rank=2,max_layers=1)
        graph={'12':{'class_type':'UnetLoaderGGUF','inputs':{'unet_name':'base.gguf'}},
               '26':{'class_type':'CFGGuider','inputs':{'model':['12',0]}},
               'other':{'class_type':'UNETLoader','inputs':{'unet_name':'other.gguf'}}}
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);weights=root/'weights.safetensors';adapter.save(weights)
            record={'adapter':str(weights),'sha256':'abc','config':{'trainer':'surrogate_es','comfy_unet':'/models/base.gguf'}}
            with patch('auto_rl.image_runtime.validated_record',return_value=record), patch('auto_rl.image_runtime.ROOT',root), patch('auto_rl.versions.preference',return_value='validated'):
                transformed=apply_validated_workflow(graph)
                self.assertEqual(transformed['26']['inputs']['model'],['aurora_trained_image_12',0])
                self.assertEqual(graph['26']['inputs']['model'],['12',0])
                self.assertEqual(apply_validated_workflow(transformed),transformed)
                self.assertNotIn('aurora_trained_image_other',transformed)
            with patch('auto_rl.versions.preference',return_value='base'):
                self.assertEqual(apply_validated_workflow(transformed),graph)
                self.assertIn('aurora_trained_image_12',transformed)
            with patch('auto_rl.image_runtime.validated_record',return_value=None):
                self.assertEqual(apply_validated_workflow(graph),graph)
        adapter.close()

    def test_training_workflow_never_automatically_uses_production_adapter(self):
        import sys
        from auto_rl.config import ROOT
        sys.path.insert(0,str(ROOT/'application/python-services'))
        from flux_reference_synth import build_workflow
        with patch('auto_rl.image_runtime.apply_validated_workflow',side_effect=AssertionError('audit contamination')):
            graph=build_workflow('test',seed=1,trained_adapter=False)
            self.assertEqual(graph['26']['inputs']['model'],['12',0])

    def test_comfy_weights_have_exact_same_delta(self):
        m=torch.nn.Sequential(torch.nn.Linear(32,64,bias=False))
        adapter=WeightSubspace(m,rank=2,max_layers=1,seed=4)
        adapter.set_vector(torch.tensor([.2,-.1]))
        x=torch.randn(3,32)
        adapter.enabled=False;base=m(x)
        adapter.enabled=True;changed=m(x)
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'lora.safetensors';export_comfy_lora(adapter,p)
            w=load_file(str(p))
            down=w['diffusion_model.0.lora_down.weight'];up=w['diffusion_model.0.lora_up.weight']
            torch.testing.assert_close(changed-base,x@down.T@up.T)
            self.assertEqual(float(w['diffusion_model.0.alpha']),2)
        adapter.close()

    def test_remote_optimizer_writes_bounded_compatible_weights(self):
        m=torch.nn.Sequential(torch.nn.Linear(32,32,bias=False));a=WeightSubspace(m,rank=2,max_layers=1)
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);out=root/'out';out.mkdir();a.save(root/'initial.safetensors')
            rows=[{'vector':[x,y],'reward':.5+x-y} for x,y in [(-.1,0),(.1,0),(0,-.1),(0,.1),(-.1,-.1),(.1,.1)]]
            atomic_json(root/'observations.json',rows)
            c=defaults('image');c.update(rank=2,max_layers=1)
            optimize(c,root,out,lambda row:None)
            a.load(out/'candidate.safetensors')
            self.assertLessEqual(float(a.vector().norm()),c['trust_radius']+1e-5)
            self.assertTrue(torch.isfinite(a.vector()).all())
        a.close()

if __name__=='__main__':unittest.main()
