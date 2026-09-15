"""Load only audited adapters for their exact pretrained base model."""
from __future__ import annotations
import json
from pathlib import Path
from .config import STATE, TEXT_MODULES
from .storage import read_json, file_hash, assert_unchanged, digest


def validated_record(module, state=STATE):
    state=Path(state).resolve()
    record=read_json(state/'registry'/(module+'.json'))
    if not record:
        return None
    run=(state/'runs'/record['run_id']).resolve()
    if not run.is_relative_to(state/'runs'):
        raise ValueError('Répertoire du modèle invalide')
    adapter=Path(record['adapter']).resolve()
    if not adapter.is_relative_to(run) or file_hash(adapter)!=record['sha256']:
        raise ValueError('Poids validés absents ou modifiés')
    report=read_json(run/'report.json')
    config=read_json(run/'config.json')
    if not report or report.get('module')!=module or not report['gate']['eligible'] or report['candidate_sha256']!=record['sha256']:
        raise ValueError('Le modèle ne dispose pas d’un audit admissible')
    from .evaluation import promotion_gate
    gate=promotion_gate(report['base'],report['champion'],report['candidate'],config,parent=report.get('parent'))
    if not gate['eligible']:
        raise ValueError('Audit insuffisant après recontrôle : '+ '; '.join(gate['reasons']))
    if config['module']!=module or config['models'].get(module) is None:
        raise ValueError('Configuration du modèle incompatible')
    if record.get('report_sha256') and file_hash(run/'report.json')!=record['report_sha256']:
        raise ValueError('Le rapport validé a changé')
    assert_unchanged(read_json(run/'base_manifest.json'))
    return {**record,'module':module,'config':config,'model_id':config['models'][module]}


def catalog(state=STATE, include_base=False):
    result=[]
    for module in sorted(TEXT_MODULES):
        record=None
        try:
            record=validated_record(module,state)
        except (ValueError,OSError,KeyError,TypeError,RuntimeError):
            pass
        if record:
            result.append({'name':f'aurora-rl-{module}:v{record["version"]}',
                           'model':f'aurora-rl-{module}:v{record["version"]}',
                           'module':module,'digest':record['sha256'],'size':Path(record['adapter']).stat().st_size,
                           'details':{'family':'qwen3','parameter_size':'8B + adapter','format':'safetensors','quantization_level':'NF4'},
                           'base_model':record['model_id'],'audit_score':record['score']})
        if include_base:
            from .config import defaults
            from .versions import preference
            base=defaults(module)['models'][module]
            details={'family':'qwen3','parameter_size':'8B','format':'safetensors','quantization_level':'NF4'}
            for suffix in ('base','selected'):
                use_adapter=suffix=='selected' and preference(module,state)=='validated' and bool(record)
                name=f'aurora-rl-{module}:{suffix}'
                result.append({'name':name,'model':name,'module':module,'base_model':base,
                               'digest':record['sha256'] if use_adapter else 'official:'+base,
                               'size':0,'details':details,'selection':'validated' if use_adapter else 'base',
                               'audit_score':record['score'] if use_adapter else None})
    return result


def attach_validated(model,module,base_model_id,state=STATE):
    from .versions import preference
    if preference(module,state)=='base':
        return None
    record=validated_record(module,state)
    if not record:
        return None
    if record['model_id']!=base_model_id:
        raise ValueError(f'Adaptateur {module} destiné à {record["model_id"]}, pas à {base_model_id}')
    from safetensors import safe_open
    with safe_open(record['adapter'],framework='pt',device='cpu') as f:
        meta=f.metadata()
    if meta['kind']=='aurora-lora-v1':
        from .lora import LowRankAdapter
        adapter=LowRankAdapter(model,int(meta['rank']),len(json.loads(meta['targets'])),int(meta['seed']))
    elif meta['kind']=='aurora-weight-subspace-v1':
        from .adapters import WeightSubspace
        adapter=WeightSubspace(model,int(meta['rank']),seed=int(meta['seed']),targets=json.loads(meta['targets']))
    else:
        raise ValueError('Format de poids entraînés inconnu')
    try:
        adapter.load(record['adapter'])
    except BaseException:
        adapter.close();raise
    # Keep hook state alive for as long as the production model is used.
    model._aurora_validated_adapter=adapter
    model._aurora_validated_name=record['name']
    return record
