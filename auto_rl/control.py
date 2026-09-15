"""Durable single-owner training control shared by the web page and CLI.

A stop is cooperative: finish the current train/export/audit cycle, then stop.
No remote kernel is killed by this controller. Continuous mode uses bounded
jobs and waits for quota; audit rejection is a result, not a controller error.
"""
from __future__ import annotations
import argparse
import contextlib
import fcntl
import json
import os
from pathlib import Path
import signal
import subprocess
import time
import uuid
from .config import ROOT, STATE, PYTHON, LABELS, defaults, validate
from .storage import atomic_json, read_json, exclusive_lock

TERMINAL = {'complete', 'stopped', 'error', 'interrupted'}


def cleanup_transients(run):
    """Remove only interrupted write markers after a cycle boundary.

    Candidate weights, metrics, reports, previews and logs are durable results;
    pending downloads and atomic-write remnants are not training data and must
    not accumulate across cycles.
    """
    run = Path(run)
    if not run.is_dir():
        return
    for pattern in ('*.pending.*', '*.tmp', '*.part', '*.partial', 'stop_signal.txt'):
        for path in run.rglob(pattern):
            try:
                if path.is_file() or path.is_symlink():
                    path.unlink()
            except OSError:
                pass


def failure_details(code, current, log_path, session_id):
    """Explain a hard exit even when Python could not write an exception."""
    detail={'exit_code':code, 'last_step':current.get('status'), 'log':str(log_path)}
    if current.get('phase') == 'error':
        message=current.get('status') or 'Erreur du cycle'
    elif code < 0:
        name=signal.Signals(-code).name
        message=f'Processus interrompu par {name} (code {code}).'
        if code == -9:
            try:
                journal=subprocess.run(['journalctl','--user','-u','aurora-training-'+session_id+'.service',
                                        '--no-pager','-n','15'],capture_output=True,text=True,timeout=5).stdout
                if 'OOM killer' in journal or 'oom-kill' in journal:
                    message='Mémoire RAM épuisée : Linux a arrêté le processus (OOM killer, SIGKILL).'
            except (OSError, subprocess.TimeoutExpired):
                pass
    else:
        message=f'Le processus a échoué (code {code}).'
    try:
        with Path(log_path).open('rb') as log:
            log.seek(0,2);log.seek(max(0,log.tell()-6000))
            detail['log_tail']=log.read().decode(errors='replace')
    except OSError:
        detail['log_tail']='Journal indisponible'
    detail['message']=message
    return detail


@contextlib.contextmanager
def control_lock(state):
    Path(state).mkdir(parents=True, exist_ok=True)
    with (Path(state)/'control.lock').open('a+') as file:
        fcntl.flock(file, fcntl.LOCK_EX)
        try: yield
        finally: fcntl.flock(file, fcntl.LOCK_UN)


def process_identity(pid):
    try:
        fields = Path(f'/proc/{int(pid)}/stat').read_text().rsplit(')', 1)[1].split()
        return fields[19] if fields[0] != 'Z' else None
    except (OSError, ValueError, TypeError, IndexError):
        return None


def alive(record):
    identity = process_identity(record.get('pid'))
    return bool(identity and (not record.get('process_identity') or identity == record['process_identity']))


def snapshot(state=STATE):
    state = Path(state)
    record = read_json(state/'control.json', {})
    now = time.time()
    if record:
        record = dict(record)
        if record.get('phase') == 'error' and not record.get('diagnostic'):
            last=next((row for row in reversed(record.get('history',[]))
                       if isinstance(row,dict) and isinstance(row.get('exit_code'),int)
                       and row.get('exit_code',0)<0),None)
            if last:
                logs=state/'control_sessions'/str(record.get('session_id',''))
                log_path=sorted(logs.glob('cycle_*.log'))[-1] if logs.is_dir() and list(logs.glob('cycle_*.log')) else logs/'cycle_latest.log'
                record['diagnostic']=failure_details(last['exit_code'],read_json(state/'status.json',{}),log_path,record.get('session_id',''))
        active = record.get('phase') not in TERMINAL
        pending = record.get('phase') == 'starting' and now-record['started_at'] < 60
        if active and not alive(record) and not pending:
            record.update(phase='interrupted', error='Le superviseur ne tourne plus. Les résultats déjà écrits sont conservés.')
            record.setdefault('finished_at', record.get('heartbeat_at', now))
        record['active'] = record.get('phase') not in TERMINAL
        record['elapsed_seconds'] = max(0, (now if record['active'] else record.get('finished_at', now))-record['started_at'])
        command = read_json(state/'control_command.json', {})
        if command.get('session_id') == record.get('session_id') and command.get('command_id') != record.get('consumed_command'):
            record['requested'] = command
    return record


def options(data):
    if not isinstance(data, dict):
        raise ValueError('Options JSON requises')
    if set(data) - {'module', 'mode', 'training_minutes','training_start','strategy'}:
        raise ValueError('Option de contrôle inconnue')
    module, mode, minutes = data.get('module', '3d'), data.get('mode', 'once'), data.get('training_minutes', 30)
    if not isinstance(module,str) or not isinstance(mode,str) or module not in LABELS or mode not in {'once', 'continuous'}:
        raise ValueError('Module ou mode inconnu')
    if isinstance(minutes, bool) or not isinstance(minutes, int) or not 10 <= minutes <= 600:
        raise ValueError('Budget Kaggle : entier entre 10 et 600 minutes par cycle, dans le quota disponible')
    import re
    parent=data.get('training_start','best');strategy=data.get('strategy','radical-v3')
    if not isinstance(parent,str) or not re.fullmatch(r'[a-zA-Z0-9_-]{1,100}',parent):raise ValueError('Parent invalide')
    if strategy not in {'standard','radical-v2','radical-v3'}:raise ValueError('Stratégie inconnue')
    return {'module': module, 'mode': mode, 'training_minutes': minutes,'training_start':parent,'strategy':strategy}


def launch(session_id, state):
    # A user service survives bridge reloads and enforces the tested RAM limit.
    argv = ['systemd-run', '--user', '--quiet', '--collect',
            '--unit=aurora-training-'+session_id, '--property=MemoryHigh=24G',
            '--property=MemoryMax=26G', '--property=MemorySwapMax=24G',
            '--property=WorkingDirectory='+str(ROOT),
            str(PYTHON), '-m', 'auto_rl.control', 'worker', '--session', session_id,
            '--state', str(state)]
    result = subprocess.run(argv, capture_output=True, text=True, timeout=20)
    if result.returncode:
        raise RuntimeError('Démarrage du service impossible : '+result.stderr[-1000:])


def start(data, state=STATE):
    spec = options(data)
    state = Path(state)
    with control_lock(state):
        # If the previous supervisor was killed by the host OOM killer, its
        # finally block could not remove the inference lease. Recover that
        # lease before starting a new cycle so Aurora never stays needlessly
        # without its serving model.
        from .resources import recover_inference_service
        try:
            recover_inference_service(state)
        except (OSError, RuntimeError):
            pass
        old = snapshot(state)
        if old.get('active'):
            raise RuntimeError('Un entraînement est déjà actif ; utiliser le changement de module ou l’arrêt propre')
        with exclusive_lock(state/'campaign.lock'), exclusive_lock(state/'cycle.lock'):
            if old:
                atomic_json(state/'control_history'/(old['session_id']+'.json'), old)
            session_id = uuid.uuid4().hex
            record = {**spec, 'schema': 1, 'session_id': session_id, 'phase': 'starting',
                      'started_at': time.time(), 'completed_cycles': 0, 'history': []}
            atomic_json(state/'control.json', record)
            try:
                launch(session_id, state)
            except Exception as exc:
                atomic_json(state/'control.json', {**record, 'phase': 'error', 'error': str(exc), 'finished_at': time.time()})
                raise
    return snapshot(state)


def request(action, data=None, state=STATE):
    if action not in {'stop', 'switch'}:
        raise ValueError('Commande inconnue')
    spec = options(data) if action == 'switch' else {}
    state = Path(state)
    with control_lock(state):
        record = snapshot(state)
        if not record.get('active'):
            raise RuntimeError('Aucune session contrôlée en cours')
        command = {**spec, 'session_id': record['session_id'], 'command_id': uuid.uuid4().hex,
                   'action': action, 'requested_at': time.time()}
        atomic_json(state/'control_command.json', command)
    return command


def cycle_config(spec, number, state=STATE):
    # Reuse the tested local generation profiles, never their old resume flags.
    profile = read_json(Path.home()/'Bureau/Aurora_Entrainement.json', {})
    c = defaults(spec['module'])
    for override in (profile.get('common', {}), profile.get('overrides', {}).get(spec['module'], {})):
        for key, value in override.items():
            if key in {'generation', 'models'}:
                c[key].update(value)
            else:
                c[key] = value
    for key in ('resume_run', 'resume_audit', 'initial_adapter', 'prepared_tasks'):
        c.pop(key, None)
    c.update(module=spec['module'], state_dir=str(state), execution='hybrid', stage='full',
             mode='auto', cycles=1, fallback_on_quota=False, kaggle_max_session=False,
             training_budget_seconds=spec['training_minutes']*60,
             kaggle_timeout_seconds=spec['training_minutes']*60+900,
             seed=defaults()['seed']+number*100003,
             audit_partition_seed=defaults()['seed'],
             autonomous_3d=spec['module']=='3d')
    c['training_start']=spec.get('training_start','best')
    if spec.get('strategy','radical-v3') in {'radical-v2','radical-v3'}:
        from .strategy import apply
        apply(c)
    from .lineage import choose
    parent=choose(c['module'],c['training_start'],state)
    if parent:
        # Preserve adapter layout and exact parent bytes; changing layout requires
        # an explicit adapter expansion, never a silent reset to zero.
        for key in ('rank','max_layers','trainer'):c[key]=parent['config'][key]
        c['training_start']=parent['run_id']
    if c['trainer'] == 'preference_lora':
        c.update(kaggle_epochs=10000, checkpoint_every=1)
        if spec.get('strategy','radical-v3') not in {'radical-v2','radical-v3'}:
            c['early_stopping_patience'] = 20
    c['eval_tasks'] = max(c['eval_tasks'], c['auto_min_tasks'])
    from .storage import digest
    contract=digest({key:c.get(key) for key in ('module','train_tasks','eval_tasks','models','generation','audit_partition_seed','curriculum_version')})
    c['control_curriculum_key']=contract
    cached=Path(state)/'control_curricula'/(contract+'.json')
    if c['module'] not in {'code','conversation','cyber','cowork','learning'} and cached.is_file():
        c['prepared_tasks']=str(cached)
    return validate(c)


def pending(state, record):
    command = read_json(Path(state)/'control_command.json', {})
    if command.get('session_id') == record['session_id'] and command.get('command_id') != record.get('consumed_command'):
        return command
    return {}


def apply_boundary(state, record):
    # The request and boundary share one lock: a late stop cannot be lost to
    # completion or to a module switch. Commands are bound to a unique session.
    with control_lock(state):
        command = pending(state, record)
        if command:
            record['consumed_command'] = command['command_id']
            if command['action'] == 'stop':
                record.update(phase='stopped', finished_at=time.time())
            else:
                record.update(options({k: command[k] for k in ('module', 'mode', 'training_minutes','training_start','strategy') if k in command}))
                record.update(phase='running', module_started_at=time.time(), module_cycles=0)
        elif record.get('module_cycles', 0) and record['mode'] == 'once':
            record.update(phase='complete', finished_at=time.time())
        atomic_json(Path(state)/'control.json', record)
    return record['phase'] not in TERMINAL


def worker(session_id, state=STATE):
    state = Path(state)
    record = read_json(state/'control.json', {})
    if record.get('session_id') != session_id or record.get('phase') != 'starting':
        raise ValueError('Démarrage périmé')
    record.update(pid=os.getpid(), process_identity=process_identity(os.getpid()), phase='running',
                  heartbeat_at=time.time(), module_started_at=time.time(), module_cycles=0)
    child = None

    def save(**fields):
        record.update(heartbeat_at=time.time(), **fields)
        atomic_json(state/'control.json', record)

    def on_signal(signum, frame):
        # SIGTERM aimed at the supervisor is also cooperative. Systemd's own
        # forced shutdown cannot promise a remote checkpoint: report interruption.
        atomic_json(state/'control_command.json', {'session_id': session_id, 'command_id': uuid.uuid4().hex,
                    'action': 'stop', 'requested_at': time.time()})
    signal.signal(signal.SIGTERM, on_signal)
    signal.signal(signal.SIGINT, on_signal)
    try:
        # start() releases this lock after launching the service.
        for attempt in range(40):
            try:
                guard = exclusive_lock(state/'campaign.lock'); guard.__enter__(); break
            except RuntimeError:
                time.sleep(.1)
        else:
            raise RuntimeError('Une campagne utilise déjà le moteur')
        try:
            save()
            while apply_boundary(state, record):
                spec = {k: record[k] for k in ('module', 'mode', 'training_minutes','training_start','strategy') if k in record}
                c = cycle_config(spec, record['completed_cycles'], state)
                from .cloud import quota, QuotaUnavailable, quota_error
                q = quota()
                if q['remaining_seconds'] < 1500:
                    if record['mode'] != 'continuous':
                        raise QuotaUnavailable('Quota Kaggle insuffisant pour une session et sa sauvegarde')
                    save(phase='waiting_quota', quota=q, next_quota_check_at=time.time()+300)
                    for _ in range(150):
                        if pending(state, record): break
                        time.sleep(2)
                        save()
                    continue
                if pending(state, record): continue
                folder = state/'control_sessions'/session_id
                index = record['completed_cycles']+1
                config_path = folder/f'cycle_{index:04d}.json'
                atomic_json(config_path, c)
                cycle_started = time.time()
                with (folder/f'cycle_{index:04d}.log').open('a') as log:
                    child = subprocess.Popen([str(PYTHON), '-m', 'auto_rl.cli', 'run', '--config', str(config_path)],
                                             cwd=ROOT, stdout=log, stderr=subprocess.STDOUT)
                    save(phase='running', child_pid=child.pid, cycle_started_at=cycle_started,
                         current_run_id=None, quota=q)
                    local_failure=None
                    interruption_at=None
                    while child.poll() is None:
                        current = read_json(state/'status.json', {})
                        own = current.get('pid') == child.pid
                        command = pending(state, record)
                        if command and own and current.get('run_id'):
                            # The supervisor owns the control file, but the
                            # cycle subprocess owns the actual work.  Pass a
                            # durable boundary signal in every phase.  A
                            # completed Kaggle job still leaves its id in the
                            # status while the local audit runs, so checking
                            # job_id here would make stop requests disappear.
                            stop_file = state/'runs'/str(current['run_id'])/'stop_signal.txt'
                            stop_file.parent.mkdir(parents=True, exist_ok=True)
                            stop_file.write_text(command['action'])
                        if own and not current.get('job_id'):
                            step_seconds=time.time()-current.get('step_started_at',current.get('phase_started_at',time.time()))
                            if step_seconds > c.get('local_step_timeout_seconds',1200):
                                local_failure=f'Étape locale sans résultat depuis {int(step_seconds)} s : '+current.get('status','')
                            if current.get('phase') in {'preflight','curriculum','loading','self_play','training'} and time.time()-cycle_started > c.get('local_preparation_seconds',3600):
                                local_failure='Préparation PC trop longue ; résultats conservés pour reprise, aucun job Kaggle lancé.'
                        if local_failure:
                            if interruption_at is None:
                                child.send_signal(signal.SIGINT);interruption_at=time.time()
                            elif time.time()-interruption_at>15:
                                child.kill()
                        save(phase='stop_requested' if command.get('action')=='stop' else 'switch_requested' if command else 'running',
                             current_run_id=current.get('run_id') if own else None)
                        time.sleep(2)
                current = read_json(state/'status.json', {})
                current = current if current.get('pid') == child.pid else {}
                row = {'module': spec['module'], 'run_id': current.get('run_id'),
                       'outcome': current.get('phase', 'error'), 'started_at': cycle_started,
                       'finished_at': time.time(), 'exit_code': child.returncode}
                record['history'] = (record['history']+[row])[-100:]
                record['completed_cycles'] += 1
                record['module_cycles'] += 1
                code = child.returncode
                pending_command = pending(state, record)
                # A cooperative stop/switch deliberately makes the cycle
                # return 130.  It is a successful control boundary, not a
                # failed training run; apply_boundary will consume it below.
                if code and current.get('phase') == 'cancelled' and pending_command:
                    code = 0
                child = None
                if code:
                    if record['mode']=='continuous' and quota_error(current.get('status', '')):
                        record['module_cycles'] = 0
                        save(phase='waiting_quota')
                        continue
                    details=failure_details(code,current,folder/f'cycle_{index:04d}.log',session_id)
                    if local_failure:details['message']=local_failure
                    save(diagnostic=details,child_pid=None)
                    if current.get('run_id'):
                        run=state/'runs'/current['run_id']
                        atomic_json(run/'diagnostic.json',details)
                        current.update(phase='error',status=details['message'],diagnostic=details,updated_at=time.time())
                        atomic_json(run/'status.json',current);atomic_json(state/'status.json',current)
                    raise RuntimeError(details['message'])
                # The marker is only a boundary signal.  Keep the cancellation
                # reason in status.json and remove the marker so a retained run
                # is clean and cannot be cancelled accidentally if inspected
                # later.
                if current.get('run_id'):
                    cleanup_transients(state/'runs'/str(current['run_id']))
                curriculum=state/'runs'/str(current.get('run_id'))/'tasks/curriculum.json'
                cached=state/'control_curricula'/(c['control_curriculum_key']+'.json')
                if curriculum.is_file() and not cached.exists():
                    atomic_json(cached,read_json(curriculum))
                save(phase='running', child_pid=None)
        finally:
            guard.__exit__(None, None, None)
        return 0
    except Exception as exc:
        save(phase='error', error=str(exc), finished_at=time.time())
        return 1
    finally:
        if child is None or child.poll() is not None:
            from .resources import recover_inference_service
            recover_inference_service(state)
        # A live child is never advertised as stopped. On an unexpected monitor
        # failure keep its identity visible; locks prevent a second training job.
        if child and child.poll() is None:
            save(phase='interrupted', error='Supervision interrompue ; cycle encore actif', child_pid=child.pid)


def main():
    parser = argparse.ArgumentParser(description='Contrôler les cycles Aurora, arrêt après sauvegarde et audit')
    parser.add_argument('command', choices=['start', 'stop', 'switch', 'status', 'worker'])
    parser.add_argument('--module', choices=LABELS, default='3d')
    parser.add_argument('--continuous', action='store_true')
    parser.add_argument('--minutes', type=int, default=30)
    parser.add_argument('--from-model',default='best',dest='training_start')
    parser.add_argument('--strategy',choices=['standard','radical-v2','radical-v3'],default='radical-v3')
    parser.add_argument('--session'); parser.add_argument('--state', default=str(STATE))
    a = parser.parse_args()
    if a.command == 'worker': return worker(a.session, Path(a.state))
    data = {'module': a.module, 'mode': 'continuous' if a.continuous else 'once', 'training_minutes': a.minutes,
            'training_start':a.training_start,'strategy':a.strategy}
    result = start(data) if a.command=='start' else request(a.command, data) if a.command in {'stop','switch'} else snapshot()
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__': raise SystemExit(main())
