"""Prepare one 30-minute Kaggle session and audit its returned 3D candidate."""
from __future__ import annotations
import argparse
import os
from pathlib import Path
import shutil
import time
import uuid
from .config import ROOT,STATE,read_config
from .storage import Status,read_json,atomic_json,assert_unchanged,file_hash,exclusive_lock


def run(source_id,audit_base_id):
    source=(STATE/'runs'/source_id).resolve()
    baseline=(STATE/'runs'/audit_base_id).resolve()
    if not source.is_relative_to(STATE/'runs') or not baseline.is_relative_to(STATE/'runs'):
        raise ValueError('Cycle source invalide')
    old=read_json(source/'config.json')
    if old['module']!='3d':raise ValueError('Préférences 3D requises')
    c=read_config(source/'config.json')
    # Keep the measured generation profile exactly, including omitted defaults.
    c['generation']=old['generation']
    for key in ('resume_run','resume_audit','initial_adapter','prepared_tasks'):c.pop(key,None)
    c.update(module='3d',state_dir=str(STATE),execution='hybrid',mode='auto',cycles=1,
             auto_refill=False,autonomous_3d=True,kaggle_timeout_seconds=2700,
             kaggle_max_session=False,kaggle_epochs=10000,early_stopping_patience=20,
             checkpoint_every=1,max_hours=2,fallback_on_quota=False)
    session_id='3d-autonome-'+time.strftime('%Y%m%d-%H%M%S')+'-'+uuid.uuid4().hex[:6]
    session=STATE/'runs'/session_id
    journal=STATE/'autonomous_3d.json'
    started=time.monotonic();status=None
    def check():
        if (session/'stop_signal.txt').exists() or (STATE/'autonomous_3d.stop').exists():
            from .runner import Cancelled
            raise Cancelled('Session autonome arrêtée à la demande')
        if time.monotonic()-started>5400:raise RuntimeError('Délai de préparation et retour Kaggle dépassé')
        if shutil.disk_usage(STATE).free<12*2**30:raise RuntimeError('Réserve disque atteinte')
    with exclusive_lock(STATE/'campaign.lock'):
        (STATE/'autonomous_3d.stop').unlink(missing_ok=True)
        session.mkdir(parents=True)
        status=Status(STATE,session_id,'3d')
        record={'run_id':session_id,'pid':os.getpid(),'phase':'preparing','training_seconds':1800,
                'execution':'kaggle','source_run':source_id,'started_at':time.time(),
                'audit_in_budget':False,'interventions_required':False}
        atomic_json(journal,record)
        try:
            with exclusive_lock(STATE/'cycle.lock'):
                status.update('preflight','Session 3D autonome : vérification des préférences mesurées…')
                assert_unchanged(read_json(source/'base_manifest.json'))
                atomic_json(session/'config.json',c)
                shutil.copy2(source/'base_manifest.json',session/'base_manifest.json')
                shutil.copytree(source/'tasks',session/'tasks')
                shutil.copytree(source/'preferences',session/'preferences')
                preferences=read_json(session/'preferences/preferences.json')
                if not {'train','validation'} <= {r['split'] for r in preferences}:
                    raise ValueError('Séparation apprentissage et validation manquante')
                from safetensors.torch import load_file
                import torch
                for pref in preferences:
                    file=session/'preferences'/pref['tensors']
                    if not file.resolve().is_relative_to(session/'preferences'):
                        raise ValueError('Chemin de préférence incompatible')
                    tensors=load_file(str(file))
                    if set(tensors)!={'chosen','rejected','cond'} or not all(torch.isfinite(t).all() for t in tensors.values()):
                        raise ValueError('Préférence 3D non finie ou incomplète')
                atomic_json(session/'input_manifest.json',{p.name:file_hash(p) for p in (session/'preferences').iterdir() if p.is_file()})
                from .backends import local_snapshot
                from .cloud import train_on_kaggle
                model=local_snapshot(c['models']['3d'])
                files=[(p,p.name) for p in (session/'preferences').iterdir() if p.is_file()]
                record['phase']='training';atomic_json(journal,record)
                remote,_=train_on_kaggle(c,session,files,{'model_revision':Path(model).name,'module':'3d'},status,check)
                (session/'trained').mkdir()
                for target in (session/'candidate.safetensors',session/'trained/candidate.safetensors'):
                    shutil.copy2(remote/'candidate.safetensors',target)
                for name in ('training_metrics.json','autonomy.json'):
                    shutil.copy2(remote/name,session/name)
                assert_unchanged(read_json(session/'base_manifest.json'))
                record.update(phase='trained',metrics=read_json(session/'training_metrics.json'),
                              candidate_sha256=file_hash(session/'candidate.safetensors'))
                atomic_json(journal,record)
                # The baseline is a cache, never new training supervision.
                report=read_json(baseline/'report.json')
                if report and report['generation']==c['generation']:
                    for row in report['base']:
                        if row['sha256']!=file_hash(row['artifact']):raise ValueError('Rendu de base sauvegardé modifié')
                        name=f"{row['task_id']}_graine_{row['seed']}.evaluation.json"
                        atomic_json(session/'audit/base'/name,row)
            check()
            elapsed=record['metrics']['elapsed_seconds']
            status.update('audit_pending',f'Apprentissage terminé après {elapsed/60:.1f} minutes ; audit local du candidat…')
            c.update(resume_run=session_id,resume_audit=True,autonomous_3d=False,max_hours=2)
            atomic_json(session/'audit_config.json',c)
            record['phase']='auditing';atomic_json(journal,record)
            from .runner import run_cycles
            outcome=run_cycles(c)
            final=read_json(STATE/'status.json')
            record.update(phase='complete' if outcome==0 else 'stopped',audit_run_id=final['run_id'],
                          audit_outcome=final['phase'],finished_at=time.time())
            atomic_json(journal,record)
            return outcome
        except BaseException as exc:
            import traceback
            (session/'supervisor_error.log').write_text(traceback.format_exc())
            record.update(phase='stopped',error=str(exc),finished_at=time.time())
            atomic_json(journal,record)
            status.update('error',str(exc),waiting_validation=False)
            return 1


def main():
    p=argparse.ArgumentParser();p.add_argument('command',choices=['run','status','stop'])
    p.add_argument('--source',default='3d-20260913-040637-aed4f0')
    p.add_argument('--baseline',default='3d-20260913-160516-061501');a=p.parse_args()
    if a.command=='status':
        import json
        print(json.dumps(read_json(STATE/'autonomous_3d.json',{}),ensure_ascii=False,indent=2));return 0
    if a.command=='stop':
        (STATE/'autonomous_3d.stop').write_text('STOP')
        state=read_json(STATE/'status.json',{})
        if state.get('module')=='3d' and state.get('phase') not in {'accepted','rejected','error','cancelled'}:
            (STATE/'runs'/state['run_id']/'stop_signal.txt').write_text('STOP')
        return 0
    return run(a.source,a.baseline)

if __name__=='__main__':raise SystemExit(main())
