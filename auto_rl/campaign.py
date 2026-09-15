"""Resume a bounded sequence of training modules from one small JSON profile."""
from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from .config import ROOT, STATE, LABELS, TEXT_MODULES, defaults, validate
from .storage import atomic_json, read_json, exclusive_lock


def run_campaign(path, remaining_hours=None):
    profile=json.loads(Path(path).read_text())
    modules=profile.get('modules',list(LABELS))
    if not isinstance(modules,list) or not modules or any(m not in LABELS for m in modules):
        raise ValueError('Liste de modules invalide')
    hours=float(profile.get('max_total_hours',12))
    if remaining_hours is not None:
        hours=min(hours,remaining_hours)
    if not 0 < hours <= 72:
        raise ValueError('La campagne doit durer de 0 à 72 heures')
    journal=STATE/'campaign.json'
    stop=STATE/'campaign.stop'
    previous=read_json(journal,{})
    old_profile=previous.get('profile',{})
    entries=previous.get('modules',{}) if old_profile==profile else {
        m:e for m,e in previous.get('modules',{}).items()
        if m in modules and e.get('outcome') in {'accepted','rejected'}
        and old_profile.get('common',{})==profile.get('common',{})
        and old_profile.get('overrides',{}).get(m,{})==profile.get('overrides',{}).get(m,{})
        and old_profile.get('revision')==profile.get('revision')}
    report={'profile':profile,'modules':entries,'pid':os.getpid(),'phase':'running','started_at':time.time()}
    deadline=time.monotonic()+hours*3600
    with exclusive_lock(STATE/'campaign.lock'):
        if previous:
            archive=STATE/'campaign_history';archive.mkdir(exist_ok=True)
            atomic_json(archive/(str(time.time_ns())+'.json'),previous)
        stop.unlink(missing_ok=True)
        for module in modules:
            if entries.get(module,{}).get('outcome') in {'accepted','rejected'}:
                continue
            if stop.exists() or time.monotonic()>=deadline:
                report['phase']='stopped';break
            c=defaults(module)
            c.update(profile.get('common',{}))
            for key,value in profile.get('overrides',{}).get(module,{}).items():
                if key in {'models','generation'}:
                    c[key].update(value)
                else:
                    c[key]=value
            c['module']=module
            c['state_dir']=str(STATE)
            if c['mode']=='auto':c['eval_tasks']=max(c['eval_tasks'],c['auto_min_tasks'])
            c['max_hours']=min(c['max_hours'],max(.01,(deadline-time.monotonic())/3600))
            prior = entries.get(module, {})
            if module in TEXT_MODULES and prior.get('outcome') == 'error' and prior.get('run_id'):
                old_run = STATE / 'runs' / prior['run_id']
                old_config = read_json(old_run / 'config.json', {})
                keys = ('module','models','generation','rank','max_layers','seed','train_tasks','eval_tasks')
                if (all(old_config.get(k) == c.get(k) for k in keys)
                        and (old_run / 'tasks/curriculum.json').is_file()
                        and (old_run / 'preferences/initial.safetensors').is_file()):
                    c['resume_run'] = prior['run_id']
            validate(c)
            configs=STATE/'profiles';configs.mkdir(parents=True,exist_ok=True)
            config=configs/(module+'.json');atomic_json(config,c)
            entries[module]={'outcome':'running','started_at':time.time()}
            report['current_module']=module;atomic_json(journal,report)
            logs=STATE/('campaign-'+module+'.log')
            print(f'Aurora : {LABELS[module]} — journal {logs}',flush=True)
            with logs.open('a') as out:
                child=subprocess.Popen([sys.executable,'-u','-m','auto_rl.cli','run','--config',str(config)],cwd=ROOT,stdout=out,stderr=subprocess.STDOUT)
                while child.poll() is None:
                    if stop.exists() or time.monotonic()>=deadline:
                        status=read_json(STATE/'status.json',{})
                        if status.get('pid')==child.pid:
                            run=STATE/'runs'/status['run_id']
                            (run/'stop_signal.txt').write_text('STOP')
                        try:child.wait(timeout=45)
                        except subprocess.TimeoutExpired:child.terminate();child.wait(timeout=15)
                        report['phase']='stopped'
                        break
                    time.sleep(2)
            status=read_json(STATE/'status.json',{})
            entries[module]={'outcome':status.get('phase','error') if status.get('pid')==child.pid else 'error',
                             'run_id':status.get('run_id') if status.get('pid')==child.pid else None,
                             'message':status.get('status',''), 'exit_code':child.returncode,'finished_at':time.time(),'log':str(logs)}
            atomic_json(journal,report)
            if report['phase']=='stopped':break
        else:
            report['phase']='complete' if all(e['outcome'] in {'accepted','rejected'} for e in entries.values()) else 'completed_with_errors'
        report['finished_at']=time.time();atomic_json(journal,report)
    return 0 if report['phase']=='complete' else 1


def recover_campaign(path):
    """One retry of failures after the active campaign, within its time budget.

    A user stop, another profile, or another campaign cancels this follow-up.
    Completed audits (including rejected candidates) are never retrained here.
    """
    profile=json.loads(Path(path).read_text())
    original=read_json(STATE/'campaign.json',{})
    expected_pid=original.get('pid')
    current=original
    end=original.get('started_at',time.time())+float(profile.get('max_total_hours',12))*3600
    while time.time()<end:
        if (STATE/'campaign.stop').exists():return 0
        current=read_json(STATE/'campaign.json',{})
        if current.get('pid')!=expected_pid or current.get('profile')!=profile:return 0
        try:os.kill(expected_pid,0)
        except (ProcessLookupError,TypeError):break
        time.sleep(5)
    remaining=(end-time.time())/3600
    if current.get('phase')=='completed_with_errors' and remaining>.01:
        return run_campaign(path,remaining_hours=remaining)
    return 0


def main():
    p=argparse.ArgumentParser(description='Aurora : campagne PC → Kaggle → audit local')
    p.add_argument('command',choices=['run','status','stop','recover'],nargs='?',default='run')
    p.add_argument('--config',default=str(Path.home()/'Bureau/Aurora_Entrainement.json'))
    a=p.parse_args()
    if a.command=='status':print(json.dumps(read_json(STATE/'campaign.json',{}),ensure_ascii=False,indent=2));return 0
    if a.command=='stop':STATE.mkdir(parents=True,exist_ok=True);(STATE/'campaign.stop').write_text('STOP');return 0
    if a.command=='recover':return recover_campaign(a.config)
    return run_campaign(a.config)

if __name__=='__main__':raise SystemExit(main())
