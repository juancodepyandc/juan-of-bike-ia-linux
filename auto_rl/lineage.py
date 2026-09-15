"""Select a verified parent without mistaking a rejected experiment for a release."""
from pathlib import Path
import math
from .config import STATE, LABELS
from .storage import read_json, file_hash, digest, assert_unchanged, atomic_json


def candidate_record(module, run_id, state=STATE):
    root=(Path(state)/'runs').resolve();run=(root/run_id).resolve()
    if run.parent!=root:raise ValueError('Identifiant du parent invalide')
    c=read_json(run/'config.json',{})
    if c.get('module')!=module:raise ValueError('Le parent appartient à un autre module')
    weights=run/'candidate.safetensors';report=read_json(run/'report.json',{})
    metrics=read_json(run/'training_metrics.json',{})
    sha=file_hash(weights)
    expected=report.get('candidate_sha256') or metrics.get('candidate_sha256')
    if not expected:
        expected=read_json(run/'autonomy.json',{}).get('candidate_sha256')
    if not expected or expected!=sha:raise ValueError('Empreinte du candidat absente ou différente')
    manifest=read_json(run/'base_manifest.json')
    if not manifest:raise ValueError('Empreinte de la base absente')
    assert_unchanged(manifest)
    loss=metrics.get('best_validation_loss')
    comparable=None
    if isinstance(loss,(int,float)) and math.isfinite(loss):
        prefs=read_json(run/'preferences/preferences.json',[])
        validation=[]
        for pref in prefs:
            if pref.get('split')!='validation':continue
            pref=dict(pref)
            if pref.get('tensors'):
                tensor=(run/'preferences'/pref['tensors']).resolve()
                if not tensor.is_relative_to(run/'preferences'):raise ValueError('Préférence hors du cycle')
                pref['tensors']=file_hash(tensor)
            validation.append(pref)
        if validation:
            comparable=digest({'validation':validation,'base':digest(manifest),
                               'algorithm':c.get('trainer'),'beta':c.get('dpo_beta'),
                               'sft':c.get('sft_weight',0),'anchor':c.get('anchor_penalty'),
                               'reference':metrics.get('reference_sha256','original'),
                               'rank':c['rank'],'layers':c['max_layers']})
    return {'run_id':run_id,'adapter':str(weights),'sha256':sha,'config':c,
            'base_fingerprint':digest(manifest),'validation_loss':loss if comparable else None,
            'validation_contract':comparable,'updated_at':(run/'config.json').stat().st_mtime,
            'eligible':bool(report.get('gate',{}).get('eligible')),
            'audit_contract':digest({'base':digest(manifest),'generation':report.get('generation'),
                                     'tasks':[(r.get('prompt'),r.get('seed')) for r in report.get('base',[])]}) if report.get('base') else None,
            'base_gain_points':report.get('gate',{}).get('base_gain_points')}


def choices(module,state=STATE):
    results=[]
    for path in (Path(state)/'runs').glob('*/candidate.safetensors'):
        try:
            c=read_json(path.parent/'config.json',{})
            if c.get('module')==module:results.append(candidate_record(module,path.parent.name,state))
        except (OSError,ValueError,RuntimeError,KeyError,TypeError):continue
    return sorted(results,key=lambda r:r['updated_at'],reverse=True)


def choose(module, selection='best', state=STATE):
    if module not in LABELS:raise ValueError('Module inconnu')
    if selection=='base':return None
    if selection in {'best','validated'}:
        from .runtime import validated_record
        record=validated_record(module,state)
        if record:return {**record,'selection_reason':'champion_validated'}
        if selection=='validated':raise ValueError('Aucun champion validé disponible')
    if selection in {'best','best_candidate'}:
        pool=[r for r in choices(module,state) if r['validation_contract']]
        if not pool:
            historical=[r for r in choices(module,state) if r['audit_contract'] and isinstance(r['base_gain_points'],(int,float))]
            if not historical:return None
            cohort=historical[0]['audit_contract']
            record=max((r for r in historical if r['audit_contract']==cohort),key=lambda r:r['base_gain_points'])
            return {**record,'selection_reason':'historical_audit_exploratory','experimental':True,
                    'requires_new_audit':True}
        # Different validation sets are not a leaderboard. Use the latest
        # comparable cohort and choose its lowest held-out loss, never audit score.
        cohort=pool[0]['validation_contract']
        record=min((r for r in pool if r['validation_contract']==cohort),key=lambda r:(r['validation_loss'],r['updated_at']))
        return {**record,'selection_reason':'best_comparable_validation','experimental':True}
    from .runtime import validated_record
    current=validated_record(module,state)
    if current and current['run_id']==selection:return {**current,'selection_reason':'pinned_validated','experimental':False}
    return {**candidate_record(module,selection,state),'selection_reason':'explicit_candidate','experimental':True}


def prepare(c, run, manifest):
    """Pin parent identity at cycle start and retain every earlier weight file."""
    if 'training_start' not in c:return None
    parent=choose(c['module'],c['training_start'],Path(c['state_dir']))
    record={'schema':1,'original_model':c['models'][c['module']],
            'original_fingerprint':digest(manifest),'parent_run_id':None,
            'parent_sha256':None,'selection':c['training_start'],'experimental':False}
    if parent:
        previous=parent['config']
        if parent['base_fingerprint']!=digest(manifest):raise ValueError('La base du parent est incompatible')
        for key in ('rank','max_layers','trainer'):
            if previous[key]!=c[key]:raise ValueError('Parent incompatible : '+key)
        if previous['models'][c['module']]!=c['models'][c['module']]:raise ValueError('Modèle du parent incompatible')
        import shutil
        pinned=Path(run)/'parent.safetensors'
        shutil.copy2(parent['adapter'],pinned)
        if file_hash(pinned)!=parent['sha256']:raise ValueError('Le parent a changé pendant sa copie')
        c['initial_adapter']=str(pinned)
        record.update(parent_run_id=parent['run_id'],parent_sha256=parent['sha256'],
                      selection_reason=parent['selection_reason'],experimental=parent.get('experimental',False))
    else:c.pop('initial_adapter',None)
    atomic_json(Path(run)/'lineage.json',record)
    return record
