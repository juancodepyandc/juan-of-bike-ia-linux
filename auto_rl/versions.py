"""Readable provenance for base, latest candidate and audited production version."""
from pathlib import Path
import time
from .config import STATE, LABELS, defaults
from .storage import read_json, atomic_json, exclusive_lock


def preference(module, state=STATE):
    if module not in LABELS: raise ValueError('Module inconnu')
    value = read_json(Path(state)/'inference_preferences.json', {}).get(module, 'base')
    return value if value in {'base', 'validated'} else 'base'


def select(module, version, state=STATE):
    if not isinstance(module,str) or not isinstance(version,str) or module not in LABELS or version not in {'base', 'validated'}:
        raise ValueError('Choisir la base officielle ou la dernière version validée')
    if version == 'validated':
        from .runtime import validated_record
        if not validated_record(module, state): raise ValueError('Aucune version validée disponible pour ce module')
    with exclusive_lock(Path(state)/'inference_preferences.lock'):
        values = read_json(Path(state)/'inference_preferences.json', {})
        values[module] = version
        atomic_json(Path(state)/'inference_preferences.json', values)
    return {'module': module, 'version': version, 'applies': 'next_generation'}


def summary(run):
    from .control import alive
    report = read_json(run/'report.json', {})
    status = read_json(run/'status.json', {})
    gate = report.get('gate', {})
    phase = status.get('phase', 'unknown')
    active = alive(status) and phase not in {'accepted','rejected','cancelled','error','remote_complete'}
    if not active and phase not in {'accepted','rejected','cancelled','error','remote_complete'}:
        phase = 'rejected' if report and not gate.get('eligible') else 'audit_pending' if (run/'candidate.safetensors').exists() else 'interrupted'
    def mean_seconds(branch):
        values = [r['seconds'] for r in report.get(branch, []) if isinstance(r.get('seconds'), (int,float))]
        return sum(values)/len(values) if values else None
    metrics = read_json(run/'training_metrics.json', {})
    return {'run_id': run.name, 'phase': phase, 'active': active,
            'updated_at': status.get('updated_at', run.stat().st_mtime),
            'candidate': (run/'candidate.safetensors').is_file(),
            'gain_points': gate.get('gain_points'), 'ci95_gain_points': gate.get('ci95_gain_points'),
            'base_gain_points':gate.get('base_gain_points'),'parent_gain_points':gate.get('parent_gain_points',gate.get('gain_points')),
            'lineage':report.get('lineage') or read_json(run/'lineage.json',{}),
            'regressions':gate.get('regressions',[]),'strict_audit':gate.get('strict',False),
            'reasons': gate.get('reasons', []), 'eligible': gate.get('eligible', False),
            'base_seconds': mean_seconds('base'), 'candidate_seconds': mean_seconds('candidate'),
            'cached_timings': any(not Path(r.get('artifact','')).is_relative_to(run) for branch in ('base','candidate') for r in report.get(branch,[])),
            'training_seconds': metrics.get('elapsed_seconds'),
            'elapsed_seconds': report.get('elapsed_seconds', status.get('elapsed_seconds')),
            'status': status.get('status'), 'has_report': bool(report)}


def modules(state=STATE):
    from .runtime import validated_record
    state = Path(state)
    runs = {}
    for config in (state/'runs').glob('*/config.json'):
        try:
            module = read_json(config, {}).get('module')
            if module in LABELS: runs.setdefault(module, []).append(config)
        except (OSError, ValueError, AttributeError): continue
    result = []
    for module, label in LABELS.items():
        candidates = sorted(runs.get(module, []), key=lambda p:p.stat().st_mtime, reverse=True)
        latest = summary(candidates[0].parent) if candidates else None
        candidate = next((p.parent for p in candidates if (p.parent/'candidate.safetensors').is_file()), None)
        error = None
        try: validated = validated_record(module, state)
        except (ValueError, OSError, KeyError, TypeError, RuntimeError) as exc:
            validated = None; error = str(exc)
        result.append({'module': module, 'label': label, 'base_model': defaults(module)['models'][module],
                       'latest_run': latest, 'latest_candidate': summary(candidate) if candidate else None,
                       'validated': bool(validated), 'validation_error': error,
                       'validated_model': {k: validated.get(k) for k in ('run_id','version','name','score','sha256')} if validated else None,
                       'selection': preference(module, state)})
    return result
