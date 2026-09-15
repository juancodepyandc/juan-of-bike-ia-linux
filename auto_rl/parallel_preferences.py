"""Use available Kaggle GPUs for comparable, predeclared training trials."""
import argparse
import json
import math
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
from .storage import atomic_json,read_json,file_hash,digest


def select_result(results):
    eligible=[r for r in results if r.get('verified') and isinstance(r.get('validation_loss'),(int,float)) and math.isfinite(r['validation_loss'])]
    if not eligible:raise RuntimeError('Aucun essai Kaggle n’a produit un candidat fini et vérifié')
    if len({r['validation_contract'] for r in eligible})!=1:raise ValueError('Essais non comparables : validation différente')
    return min(eligible,key=lambda r:(r['validation_loss'],r['trial']))


def train(c,records,root,out,seconds,callback):
    import torch
    from .autonomous_train import stop_child
    root,out=Path(root),Path(out)
    count=min(2,torch.cuda.device_count())
    if count<1:raise RuntimeError('Aucun GPU Kaggle disponible')
    # Both trials see identical data, initialization and validation noise. The
    # sole predeclared difference is learning rate. Audit is never consulted.
    contract=digest({'records':records,'initial_sha256':file_hash(root/'initial.safetensors'),
                     'validation_noise':[7281+i for i,r in enumerate(records) if r['split']=='validation'],
                     'objective':{k:c.get(k) for k in ('sft_weight','dpo_beta','anchor_penalty','reference_policy')}})
    visible=os.environ.get('CUDA_VISIBLE_DEVICES','').split(',')
    children=[];started=time.monotonic();deadline=started+seconds
    try:
        for trial in range(count):
            folder=out/f'gpu_trial_{trial}';folder.mkdir(parents=True,exist_ok=True)
            config={**c,'train_learning_rate':c['train_learning_rate']*(.5 if trial else 1)}
            atomic_json(folder/'config.json',config)
            log=(folder/'trial.log').open('w')
            env={**os.environ,'CUDA_VISIBLE_DEVICES':visible[trial] if len(visible)>=count and visible[trial] else str(trial),
                 'PYTHONPATH':str(Path(__file__).resolve().parents[1])+os.pathsep+os.environ.get('PYTHONPATH','')}
            child=subprocess.Popen([sys.executable,'-u','-m','auto_rl.parallel_preferences','--config',str(folder/'config.json'),
                                    '--root',str(root),'--out',str(folder),'--seconds',str(max(1,seconds-10))],
                                   stdout=log,stderr=subprocess.STDOUT,start_new_session=True,env=env)
            children.append((trial,folder,child,log))
        seen={}
        while any(child.poll() is None for _,_,child,_ in children):
            if time.monotonic()>=deadline:
                for _,_,child,_ in children:stop_child(child)
                break
            for trial,folder,child,_ in children:
                progress=read_json(folder/'progress.json',{})
                if progress and progress!=seen.get(trial):
                    seen[trial]=progress
                    callback({**progress,'trial':trial+1,'parallel_trials':count,
                              'training_elapsed_seconds':time.monotonic()-started})
            time.sleep(1)
        results=[]
        for trial,folder,child,_ in children:
            metrics=read_json(folder/'training_metrics.json',{})
            weights=folder/'candidate.safetensors'
            recorded=metrics.get('candidate_sha256') or read_json(folder/'autonomy.json',{}).get('candidate_sha256')
            verified=weights.is_file() and recorded==file_hash(weights) and child.returncode==0
            if verified:
                from safetensors.torch import load_file
                verified=all(torch.isfinite(t).all().item() for t in load_file(str(weights)).values())
            results.append({'trial':trial,'validation_loss':metrics.get('best_validation_loss'),
                            'validation_contract':contract,'verified':verified,'exit_code':child.returncode,
                            'weights':str(weights),'metrics':metrics})
        best=select_result(results)
        shutil.copy2(best['weights'],out/'candidate.safetensors')
        metrics={**best['metrics'],'candidate_sha256':file_hash(out/'candidate.safetensors'),
                 'parallel_trials':count,'selected_trial':best['trial']+1,'selection_rule':'lowest_identical_validation_loss',
                 'validation_contract':contract,'elapsed_seconds':time.monotonic()-started}
        atomic_json(out/'training_metrics.json',metrics)
        atomic_json(out/'trial_selection.json',{'trials':results,'selected_trial':best['trial']+1,'final_audit_used':False})
        return metrics
    finally:
        for _,_,child,log in children:
            stop_child(child);log.close()


def main():
    p=argparse.ArgumentParser();p.add_argument('--config',required=True);p.add_argument('--root',required=True)
    p.add_argument('--out',required=True);p.add_argument('--seconds',required=True,type=float);a=p.parse_args()
    root,out=Path(a.root),Path(a.out);c=read_json(a.config);records=read_json(root/'preferences.json')
    callback=lambda row:atomic_json(out/'progress.json',row)
    if c['module']=='3d':
        from .autonomous_train import supervise
        supervise(c,records,root,out,a.seconds,callback)
    else:
        from .preference_train import train_preferences
        train_preferences(c,records,root,out,10000,a.seconds,callback)


if __name__=='__main__':main()
