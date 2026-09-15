import ast
import json
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch
import torch
from auto_rl.cloud import safe_extract, build_kernel
from auto_rl.config import defaults, validate, TEXT_MODULES
from auto_rl.curriculum import build_tasks, validate_tasks, shortest_paths, topo, flatten, csv_totals, cidr
from auto_rl.judges import ConversationJudge, CodeJudge
from auto_rl.lora import LowRankAdapter
from auto_rl.storage import file_hash


class ReliabilityTests(unittest.TestCase):
    def test_repeated_prompts_do_not_make_an_automatic_audit_large_enough(self):
        from auto_rl.evaluation import promotion_gate
        base=[{'task_id':str(i),'prompt':f'Subject {i%4}', 'seed':41,
               'generation_digest':'same','peak_vram_gb':1,
               'judge':{'score':.2,'valid':True}} for i in range(8)]
        candidate=[{**row,'judge':{'score':.3,'valid':True}} for row in base]
        c=defaults('code');c['mode']='auto'
        gate=promotion_gate(base,base,candidate,c)
        self.assertFalse(gate['eligible'])
        self.assertIn('Audit trop petit pour une promotion automatique',gate['reasons'])

    def test_task_families_are_reserved_for_all_text_modules(self):
        for module in TEXT_MODULES:
            c=defaults(module);c.update(train_tasks=18,eval_tasks=8)
            tasks=build_tasks(c)
            self.assertFalse({t['family'] for t in tasks[:18]} & {t['family'] for t in tasks[18:]})
            self.assertEqual(tasks,build_tasks(c))
            self.assertTrue(all(len(t['cases'])>=6 for t in tasks))

    def test_leak_is_rejected(self):
        c=defaults('code');tasks=build_tasks(c)
        tasks[-1]={**tasks[0],'id':'other'}
        with self.assertRaisesRegex(ValueError,'Fuite'):validate_tasks(tasks,c)

    def test_oracle_edges(self):
        self.assertEqual(shortest_paths({'n':4,'edges':[[0,1,5],[0,1,0],[1,2,3]],'start':0}),[0,0,3,None])
        self.assertEqual(topo({'n':3,'edges':[[0,1],[1,0]]}),[])
        self.assertEqual(flatten({'a/b':{'~':[]}}),{'/a~1b/~0':[]})
        self.assertEqual(csv_totals('account,cents\n"a,b",7\n"a,b",-3\n'),{'a,b':4})
        self.assertEqual(cidr({'networks':['10.1.2.3/8','::1/128'],'addresses':['10.255.255.255','::1','11.0.0.0','x']}),[True,True,False,False])

    def test_json_score_does_not_reward_success_string(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'answer.txt';p.write_text('SUCCESS')
            j=ConversationJudge();t={'expected_json':{'answers':[1,2,3]}}
            self.assertEqual(j.score(p,t)['score'],0)
            p.write_text('{"answers":[1,9,3]}')
            self.assertAlmostEqual(j.score(p,t)['score'],2/3)

    def test_bootstrap_syntax_and_no_local_credentials(self):
        with tempfile.TemporaryDirectory() as d:
            with patch.object(Path,'read_text',side_effect=AssertionError('must not read credentials')):
                build_kernel(Path(__file__).resolve().parents[1],d,defaults('code'),'job','hash')
            script=(Path(d)/'train.py').read_text();ast.parse(script)
            self.assertNotIn('HF_TOKEN',script)
            self.assertIn('aurora_result.zip',script)

    def test_zip_escape_and_size_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'bad.zip'
            with zipfile.ZipFile(p,'w') as z:z.writestr('../escape','bad')
            with self.assertRaises(ValueError):safe_extract(p,Path(d)/'out')
            with zipfile.ZipFile(p,'w') as z:z.writestr('data','12345')
            with self.assertRaises(ValueError):safe_extract(p,Path(d)/'out',max_bytes=4)

    def test_weight_training_preserves_base_and_round_trips(self):
        model=torch.nn.Sequential(torch.nn.Linear(32,32),torch.nn.ReLU(),torch.nn.Linear(32,32))
        base={k:v.clone() for k,v in model.state_dict().items()}
        adapter=LowRankAdapter(model,rank=4,max_layers=2)
        x=torch.randn(3,32);original=model(x).detach().clone()
        opt=torch.optim.AdamW(adapter.parameters(),lr=.03)
        for _ in range(3):
            opt.zero_grad();model(x).square().mean().backward();opt.step()
        changed=model(x).detach().clone()
        self.assertFalse(torch.equal(original,changed))
        self.assertTrue(all(torch.equal(v,model.state_dict()[k]) for k,v in base.items()))
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'adapter.safetensors';adapter.save(path);adapter.close()
            restored=LowRankAdapter(model,rank=4,max_layers=2);restored.load(path)
            torch.testing.assert_close(model(x),changed)
            restored.enabled=False;torch.testing.assert_close(model(x),original)
            restored.close()

    def test_all_cloud_option_fails_before_allocating_gpu(self):
        c=defaults('3d');c['execution']='kaggle_only'
        with self.assertRaisesRegex(ValueError,'hybride'):validate(c)

    def test_real_code_sandbox_rejects_fake_success(self):
        from auto_rl.sandbox import Sandbox
        sandbox=Sandbox();sandbox.check()
        judge=CodeJudge(sandbox)
        task={'function':'solve','cases':[{'args':[[1,2]]}]*6,'expected':[[2,1]]*6}
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'code.py';p.write_text('def solve(data):\n return "SUCCESS"\n')
            self.assertEqual(judge.score(p,task)['score'],0)
            p.write_text('def solve(data):\n return data[::-1]\n')
            self.assertEqual(judge.score(p,task)['score'],1)

if __name__=='__main__':unittest.main()
