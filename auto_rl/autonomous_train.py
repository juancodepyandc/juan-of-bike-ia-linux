"""Bounded training supervision, executable on Kaggle without an assistant.

Diagnoses map to reviewed corrections. Logs are data, never shell commands or
generated code. Unknown failures stop rather than weakening validation.
"""
from __future__ import annotations
import argparse
import json
import math
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import time
from .storage import atomic_json,read_json,file_hash,digest


def diagnose(message,returncode=None):
    lower=message.casefold()
    if 'cuda' in lower and ('out of memory' in lower or 'budget vram' in lower):
        return {'code':'cuda_memory','action':'offload_activations',
                'explanation':'Les activations dépassent la mémoire GPU ; les sauvegardes du gradient passent en RAM.'}
    if any(s in lower for s in ('non finie','non finis','non finite','non-finite','nan loss')):
        return {'code':'numerical_instability','action':'rollback_reduce_step',
                'explanation':'Calcul instable ; reprise des meilleurs poids finis, pas de validation d’un résultat non fini.'}
    if any(s in lower for s in ('hash','empreinte','corromp','incompatible','a changé')):
        return {'code':'integrity','action':'stop','explanation':'Poids ou données incompatibles : aucune correction automatique de leur identité.'}
    if returncode in {-9,137}:
        return {'code':'host_memory_or_kill','action':'stop','explanation':'Processus tué ; mémoire hôte ou arrêt externe possibles. La cause ne permet pas une reprise aveugle.'}
    return {'code':'unknown','action':'stop','explanation':'Erreur inconnue ; détails conservés pour diagnostic, sans commande improvisée.'}


def correction(config,diagnosis,repeats):
    """Return a bounded config patch, or None when a remedy is exhausted."""
    action=diagnosis['action']
    if action=='offload_activations' and repeats<=1 and not config.get('offload_saved_tensors'):
        return {'offload_saved_tensors':True}
    if action=='rollback_reduce_step' and repeats<=2:
        return {'train_learning_rate':max(1e-7,config['train_learning_rate']*.25),
                'fp16_initial_scale':max(1.,config.get('fp16_initial_scale',128.)*.125)}
    return None


def stop_child(child):
    if child.poll() is not None:return
    # Only the process group created by this supervisor belongs to the attempt.
    try:os.killpg(child.pid,signal.SIGTERM)
    except ProcessLookupError:return
    try:child.wait(timeout=3)
    except subprocess.TimeoutExpired:
        os.killpg(child.pid,signal.SIGKILL);child.wait(timeout=3)


def supervise(c,records,input_root,output,seconds,callback,check=lambda:None):
    root,output=Path(input_root),Path(output)
    output.mkdir(parents=True,exist_ok=True)
    if c['module']!='3d' or not 1<=seconds<=36000:
        raise ValueError('Budget de session autonome 3D invalide')
    started=time.monotonic();deadline=started+seconds
    report={'schema':1,'budget_seconds':seconds,'attempts':[], 'corrections':[],
            'best_validation_loss':None,'promotion':'audit_required',
            'note':'Diagnostic automatique par règles explicites, sans intervention de Codex ni modification du code.'}
    config=dict(c);best_loss=math.inf;best_weights=root/'initial.safetensors'
    repeats={};global_epoch=0
    child=None
    try:
        for attempt in range(1,13):
            check()
            remaining=deadline-time.monotonic()
            if remaining<8:break
            folder=output/f'attempt_{attempt:02d}';folder.mkdir()
            inputs=folder/'inputs';inputs.mkdir()
            shutil.copy2(best_weights,inputs/'initial.safetensors')
            if config.get('reference_policy')=='parent':
                reference=root/'reference.safetensors' if (root/'reference.safetensors').is_file() else root/'initial.safetensors'
                shutil.copy2(reference,inputs/'reference.safetensors')
            for record in records:
                source=root/record['tensors']
                if not source.resolve().is_relative_to(root.resolve()):raise ValueError('Chemin de préférence invalide')
                shutil.copy2(source,inputs/record['tensors'])
            atomic_json(inputs/'preferences.json',records)
            config.update(checkpoint_every=1,noise_seed_offset=(attempt-1)*100003)
            atomic_json(folder/'config.json',config)
            command=[sys.executable,'-u','-m','auto_rl.autonomous_train','attempt',
                     '--config',str(folder/'config.json'),'--input',str(inputs),
                     '--output',str(folder/'weights'),'--seconds',str(max(1,remaining-5))]
            event={'attempt':attempt,'learning_rate':config['train_learning_rate'],
                   'started_seconds':time.monotonic()-started,'start_weights_sha256':file_hash(best_weights),
                   'optimizer':'reset_from_best_weights','log':str(folder/'attempt.log')}
            report['attempts'].append(event);atomic_json(output/'autonomy.json',report)
            last_epoch=0;last_progress={}
            with (folder/'attempt.log').open('w') as log:
                env={**os.environ,'PYTHONPATH':str(Path(__file__).resolve().parents[1])+os.pathsep+os.environ.get('PYTHONPATH','')}
                child=subprocess.Popen(command,stdout=log,stderr=subprocess.STDOUT,start_new_session=True,env=env)
                while child.poll() is None:
                    check()
                    if time.monotonic()>=deadline:
                        stop_child(child);break
                    progress=read_json(folder/'weights/progress.json',{})
                    if progress.get('epoch',0)>last_epoch:
                        last_epoch=progress['epoch'];last_progress=progress
                        callback({**progress,'epoch':global_epoch+last_epoch,'attempt':attempt,
                                  'autonomous_elapsed_seconds':time.monotonic()-started})
                    time.sleep(1)
            child.poll()
            metrics=read_json(folder/'weights/training_metrics.json',{})
            progress=read_json(folder/'weights/progress.json',last_progress)
            candidate=folder/'weights/candidate.safetensors'
            # The trainer saves candidate BEFORE progress/metrics, so a complete
            # epoch can survive a later crash. Tensors and the score are checked.
            loss=metrics.get('best_validation_loss',progress.get('best_validation_loss'))
            recorded_hash=metrics.get('candidate_sha256',progress.get('candidate_sha256'))
            if (candidate.is_file() and isinstance(loss,(int,float)) and math.isfinite(loss)
                    and recorded_hash==file_hash(candidate)):
                from safetensors.torch import load_file
                import torch
                if all(torch.isfinite(t).all() for t in load_file(str(candidate)).values()) and loss<best_loss:
                    best_loss=loss;best_weights=candidate
                    shutil.copy2(candidate,output/'candidate.safetensors')
                    report.update(best_validation_loss=loss,best_attempt=attempt,
                                  candidate_sha256=file_hash(output/'candidate.safetensors'))
            global_epoch+=metrics.get('completed_epochs',progress.get('epoch',0))
            event.update(exit_code=child.returncode,metrics=metrics,finished_seconds=time.monotonic()-started)
            if time.monotonic()>=deadline:
                event['diagnosis']='time_budget_reached';break
            if child.returncode:
                diagnosis=diagnose((folder/'attempt.log').read_text(errors='replace')[-8000:],child.returncode)
                repeats[diagnosis['code']]=repeats.get(diagnosis['code'],0)+1
                patch=correction(config,diagnosis,repeats[diagnosis['code']])
                event['diagnosis']=diagnosis
                if patch is None:
                    report['stopped_reason']=diagnosis['code'];break
            else:
                diagnosis={'code':'validation_plateau','action':'restore_best_lower_lr',
                           'explanation':'La validation ne progresse plus ; reprise des meilleurs poids avec un pas plus petit et un nouveau bruit d’apprentissage.'}
                patch={'train_learning_rate':max(1e-7,config['train_learning_rate']*.7)}
                if metrics.get('termination_reason')=='time_limit':
                    report['stopped_reason']='time_limit';break
            config.update(patch)
            report['corrections'].append({'after_attempt':attempt,**diagnosis,'changes':patch})
            callback({'epoch':global_epoch,'loss':progress.get('loss',0.),
                      'validation_loss':best_loss if math.isfinite(best_loss) else 0.,'attempt':attempt,
                      'diagnosis':diagnosis,'changes':patch,'autonomous_elapsed_seconds':time.monotonic()-started})
            atomic_json(output/'autonomy.json',report)
        report.update(elapsed_seconds=time.monotonic()-started,completed_epochs=global_epoch,
                      stopped_reason=report.get('stopped_reason','time_limit' if time.monotonic()>=deadline-8 else 'attempt_limit'))
        atomic_json(output/'autonomy.json',report)
        if not (output/'candidate.safetensors').is_file():raise RuntimeError('Aucune sauvegarde entraînée exploitable : '+report['stopped_reason'])
        metrics={'algorithm':'autonomous_flow_matching_DPO','completed_epochs':global_epoch,
                 'best_validation_loss':best_loss,'best_attempt':report['best_attempt'],
                 'requested_training_seconds':seconds,'elapsed_seconds':report['elapsed_seconds'],
                 'corrections':report['corrections'],'stopped_reason':report['stopped_reason'],
                 'note':'Candidat entraîné, audit complet de maillage encore requis.'}
        best_metrics=report['attempts'][report['best_attempt']-1].get('metrics',{})
        for key in ('training_gpu','training_dtype','train_pairs','validation_pairs'):
            if key in best_metrics:metrics[key]=best_metrics[key]
        atomic_json(output/'training_metrics.json',metrics)
        if report['stopped_reason'] in {'integrity','unknown','host_memory_or_kill'}:
            raise RuntimeError('Superviseur arrêté : '+report['stopped_reason']+' ; sauvegarde non promue conservée')
        return metrics
    finally:
        if child:stop_child(child)


def main():
    p=argparse.ArgumentParser();p.add_argument('command',choices=['attempt'])
    for flag in ('config','input','output'):p.add_argument('--'+flag,required=True)
    p.add_argument('--seconds',required=True,type=float);a=p.parse_args()
    from .preference_train import train_preferences
    c=read_json(a.config);output=Path(a.output)
    def progress(row):
        atomic_json(output/'progress.json',row)
    train_preferences(c,read_json(Path(a.input)/'preferences.json'),a.input,output,10000,a.seconds,progress)

if __name__=='__main__':main()
