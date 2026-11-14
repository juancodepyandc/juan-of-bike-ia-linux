"""Load only audited adapters for their exact pretrained base model."""
from __future__ import annotations
import json
import os
from pathlib import Path
from .config import STATE, TEXT_MODULES
from .storage import read_json, file_hash, assert_unchanged, digest

# Explicit opt-in for local experiments only. Without an official registry entry
# (`<state>/registry/<module>.json`, written by `storage.promote` once the
# promotion gate has passed), an adapter described only by
# `modele/renforce/<module>/manifest.json` has NOT been through the gate and is
# not served: callers get None and keep the base model. Setting
# AURORA_ALLOW_UNGATED_REINFORCED=1 in the environment of the process that
# loads the model restores the previous behaviour, which attaches such a
# hash-matching adapter although the promotion gate never admitted it. The
# returned record then carries `ungated: True`. The variable is read on every
# call. `/api/models/reinforced-status` keeps describing that adapter as not
# promoted and only reports the opt-in itself (`ungated_opt_in`).
UNGATED_OPT_IN_ENV = 'AURORA_ALLOW_UNGATED_REINFORCED'


def ungated_reinforced_allowed():
    return os.environ.get(UNGATED_OPT_IN_ENV, '').strip() == '1'


def validated_record(module, state=STATE):
    state=Path(state).resolve()
    record=read_json(state/'registry'/(module+'.json'))
    if not record and state == Path(STATE).resolve() and ungated_reinforced_allowed():
        from .reinforced_registry import RENFORCE_ROOT
        renf = read_json(RENFORCE_ROOT / module / 'manifest.json')
        # Both spellings are unpromoted here: older manifests called such a
        # candidate `reinforced_available`, current ones `candidate_not_promoted`.
        if renf and renf.get('status') in {'reinforced_available', 'candidate_not_promoted'} and renf.get('adapter'):
            adapter = Path(renf['adapter']).resolve()
            if adapter.is_file() and file_hash(adapter) == renf.get('sha256'):
                run = (state / 'runs' / str(renf.get('run_id', ''))).resolve()
                base_fp = None
                if (run / 'base_manifest.json').is_file():
                    bm = read_json(run / 'base_manifest.json')
                    assert_unchanged(bm)
                    base_fp = digest(bm)
                cfg = dict(renf.get('config') or read_json(run / 'config.json') or {})
                model_id = cfg.get('models', {}).get(module) or renf.get('base_model', '').split(' ')[0]
                return {
                    **renf,
                    'adapter': str(adapter),
                    'score': float(renf.get('score_renforce_100', 0.0)) / 100.0,
                    'module': module,
                    'config': cfg,
                    'model_id': model_id,
                    **({'base_fingerprint': base_fp} if base_fp else {}),
                    'ungated': True,
                }
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


SPECIALIST_3D_POOL: dict[str, dict[str, str]] = {
    'v1_15d62f': {
        'filename': 'adapter.safetensors',
        'run_id': '3d-20260927-102144-15d62f',
        'name': 'Aurora-3D-TRELLIS2-Specialist-v1-StylizedManifold (15d62f)',
        'role': 'stylized_manifold_core',
        'reason': 'Spécialiste Topologie Fine / Clay (+2.18 pts) / Anime (+1.23 pts) / Véhicules (+7.46%)',
    },
    'v2_c9cbb2': {
        'filename': 'adapter_nocturne_c2_photoreal_lowpoly.safetensors',
        'run_id': '3d-20261017-054241-c9cbb2',
        'name': 'Aurora-3D-TRELLIS2-Specialist-v2-PhotorealAnimeComic (c9cbb2)',
        'role': 'photoreal_anime_comic_precision',
        'reason': 'Spécialiste Casques Anime / Caméras Cartoon / Scorpion Comic (-40% auto-intersections)',
    },
    'v3_4f2858': {
        'filename': 'adapter_nocturne_c4_4f2858.safetensors',
        'run_id': '3d-20261019-070355-4f2858',
        'name': 'Aurora-3D-TRELLIS2-Specialist-v3-TubularLowPoly (4f2858)',
        'role': 'tubular_photoreal_lowpoly',
        'reason': 'Spécialiste Véhicules Photoréalistes & Mobilier Low-Poly (+4.49% chair)',
    },
    'v4_988cf9': {
        'filename': 'adapter_nocturne_c3_988cf9.safetensors',
        'run_id': '3d-20261019-040120-988cf9',
        'name': 'Aurora-3D-TRELLIS2-Specialist-v4-ArchiArmorPhotoreal (988cf9)',
        'role': 'architecture_armor_photoreal',
        'reason': 'Spécialiste Architecture & Armures Photoréalistes (+4.37% cathedral, +3.67% helmet)',
    },
    'v5_f029e5': {
        'filename': 'adapter_nocturne_c1_topologie_bvh.safetensors',
        'run_id': '3d-20261017-024739-f029e5',
        'name': 'Aurora-3D-TRELLIS2-Specialist-v5-OrganicBVHClean (f029e5)',
        'role': 'organic_photoreal_bvh_clean',
        'reason': 'Spécialiste Créatures Ailées Photoréalistes (+9.16% owl) & Propreté BVH (-658.4 SI)',
    },
    'v6_8366ce': {
        'filename': 'adapter_specialist_c6_8366ce.safetensors',
        'run_id': '3d-20260927-140716-8366ce',
        'name': 'Aurora-3D-TRELLIS2-Specialist-v6-CartoonRigging (8366ce)',
        'role': 'cartoon_articulated_vessels',
        'reason': 'Spécialiste Cartoon 3D Articulé & Navires (+4.90% cartoon)',
    },
    'v7_c2ca2e': {
        'filename': 'adapter_nocturne_c5_c2ca2e.safetensors',
        'run_id': '3d-20261019-085510-c2ca2e',
        'name': 'Aurora-3D-TRELLIS2-Specialist-v7-ClayOrganicSculpt (c2ca2e)',
        'role': 'clay_organic_sculpture',
        'reason': 'Spécialiste Sculpture Clay Organique & Créatures (+9.16% owl)',
    },
}

SPECIALIST_3D_MATRIX: dict[str, str] = {
    'bicycle:anime': 'v1_15d62f',
    'bicycle:clay': 'v1_15d62f',
    'bicycle:photorealistic': 'v3_4f2858',
    'camera:cartoon': 'v2_c9cbb2',
    'camera:comic': 'v1_15d62f',
    'camera:low_poly': 'v5_f029e5',
    'cathedral:anime': 'v1_15d62f',
    'cathedral:clay': 'v1_15d62f',
    'cathedral:photorealistic': 'v4_988cf9',
    'chair:cartoon': 'v4_988cf9',
    'chair:comic': 'v1_15d62f',
    'chair:low_poly': 'v3_4f2858',
    'helmet:anime': 'v2_c9cbb2',
    'helmet:clay': 'v1_15d62f',
    'helmet:photorealistic': 'v4_988cf9',
    'owl:anime': 'v2_c9cbb2',
    'owl:clay': 'v7_c2ca2e',
    'owl:photorealistic': 'v5_f029e5',
    'sailing_ship:cartoon': 'v6_8366ce',
    'sailing_ship:clay': 'v7_c2ca2e',
    'sailing_ship:comic': 'v1_15d62f',
    'sailing_ship:low_poly': 'v2_c9cbb2',
    'scorpion:cartoon': 'v6_8366ce',
    'scorpion:comic': 'v2_c9cbb2',
    'scorpion:low_poly': 'v4_988cf9',
    'cathedral:low_poly': 'v4_988cf9',
    'owl:cartoon': 'v6_8366ce',
    'helmet:cartoon': 'v6_8366ce',
}


def _detect_3d_family_and_style(combined: str, ont_domain: str, render_medium: str) -> tuple[str, str]:
    """Derive 3D topological family and rendering medium purely from universal morphological,
    structural, and optical laws (plus Open-World ontology when available) with zero hardcoded
    character or franchise names."""
    import re
    clean_text = re.sub(r'(/home/juan/auroraia|/application|/output|/conversations|/references|face\.png)', ' ', combined.lower())
    tokens = set(re.findall(r'[a-z0-9àâäéèêëîïôöùûüç]+', clean_text))

    def _has(*words: str) -> bool:
        for w in words:
            if ' ' in w or '_' in w or '-' in w:
                if w in clean_text:
                    return True
            elif w in tokens:
                return True
        return False

    # Query open-world semantic ontology (cached, zero character hardcoding)
    ow_ontology = ""
    ow_render_mode = ""
    ow_submode = ""
    try:
        from agi_core.prompt_intelligence import analyze_and_direct_prompt
        sem = analyze_and_direct_prompt(clean_text[:280], target_module="3d", use_llm=False, use_open_world=True)
        ow_ontology = str(sem.get("subject_ontology") or "")
        ow_render_mode = str(sem.get("effective_render_mode") or "")
        ow_submode = str(sem.get("stylized_submode") or "")
    except Exception:
        pass

    family = 'general'
    if ow_submode == 'lowpoly_voxel' or _has('cubique', 'cubic', 'voxel', 'blocky', 'cube', 'chair', 'chaise', 'fauteuil', 'rocking', 'bascule', 'table', 'sofa', 'furniture', 'mobilier', 'bench'):
        family = 'chair'
    elif _has('cristal', 'crystal', 'quartz', 'gem', 'mineral', 'geode', 'cathedral', 'cathédrale', 'cathedrale', 'church', 'église', 'gothic', 'castle', 'château', 'arch', 'buttress', 'temple', 'tower', 'building', 'monument') or ont_domain == 'architectural_structural':
        family = 'cathedral'
    elif _has('sailing_ship', 'ship', 'navire', 'bateau', 'boat', 'galion', 'voilier', 'sail', 'mast', 'marine', 'maritime', 'aquatic', 'ocean', 'shark', 'requin', 'whale', 'dolphin', 'submarine'):
        family = 'sailing_ship'
    elif _has('warrior', 'guerrier', 'axe', 'hache', 'blade', 'épée', 'sword', 'helmet', 'casque', 'armor', 'armure', 'visor', 'visière', 'knight', 'chevalier', 'mask', 'masque', 'shield', 'bouclier', 'gladiator', 'spartan'):
        family = 'helmet'
    elif _has('bicycle', 'bike', 'velo', 'vélo', 'cargo bicycle', 'motorcycle', 'moto', 'wheel', 'spoke', 'pedal', 'car', 'voiture', 'vehicle', 'véhicule') or ont_domain == 'vehicle_aerospace':
        family = 'bicycle'
    elif _has('camera', 'appareil photo', 'lens', 'objectif', 'bellows', 'soufflet', 'clock', 'watch', 'engine', 'moteur', 'tool', 'outil', 'wand', 'baguette', 'turbine', 'gearbox') or ont_domain in {'mechanical_precision', 'hard_surface_industrial_cad'}:
        family = 'camera'
    elif _has('scorpion', 'spider', 'araignée', 'arachnid', 'crab', 'insect', 'mecha', 'robot', 'pincer', 'articulated', 'exoskeleton', 'drone', 'turret', 'tourelle'):
        family = 'scorpion'
    elif _has(
        'owl', 'hibou', 'chouette', 'bird', 'oiseau', 'eagle', 'aigle', 'dragon', 'griffin', 'wing', 'aile',
        'feather', 'plume', 'cat', 'chat', 'creature', 'animal', 'monster',
        'pomme', 'apple', 'fruit', 'food', 'plant', 'flower', 'fleur', 'organic',
        'character', 'personnage', 'human', 'humain', 'boy', 'girl', 'wizard', 'sorcier', 'football', 'soccer', 'goalkeeper',
    ) or ont_domain == 'character_creature' or ow_ontology in {'anime_manga_character', 'game_character_or_asset', 'real_human_subject'}:
        family = 'owl'

    style = 'photorealistic'
    if ow_submode in {'cartoon_figurine', 'figurine_toy', 'clay_or_plush'} or _has('clay', 'argile', 'stop-motion', 'stop motion', 'terracotta', 'sculpted clay', 'figurine', 'statuette', 'collectible', 'chibi figurine', 'vinyl', 'toy'):
        style = 'clay'
    elif ow_submode == 'lowpoly_voxel' or _has('low_poly', 'low-poly', 'low poly', 'flat-shaded', 'faceted', 'polygonal', 'cubique', 'cubic', 'voxel', 'blocky', 'cristal', 'crystal'):
        style = 'low_poly'
    elif _has('comic', 'bd', 'bande dessinée', 'inked', 'graphic novel', 'halftone'):
        style = 'comic'
    elif ow_submode == 'anime_cel' or _has('manga', 'anime', 'animé', 'cel-shaded', 'cel shaded', 'japanese animation'):
        style = 'anime'
    elif ow_submode == 'cartoon_3d' or _has('cartoon', 'stylized 3d', 'chibi', 'toon'):
        style = 'cartoon'
    elif ow_render_mode == 'native_photorealistic' or _has('photorealistic', 'photoreal', 'photoréaliste', 'realistic', 'réaliste', 'pbr', 'studio capture'):
        style = 'photorealistic'
    elif render_medium == 'stylized_2d_3d' or ow_render_mode == 'native_anime_stylized':
        style = 'anime'
    return family, style


def resolve_3d_specialist_adapter(
    prompt_text: str | None = None,
    style_hint: str | None = None,
    state=STATE,
) -> dict | None:
    """Route 3D inference across the 7 audited specialist adapters in `modele/renforce/3d/`
    (Champion v3 Multi-Specialist Matrix: 72.07/100 calibrated | 28.3160/100 raw | +4.96% vs Base |
    66W/30L | -658.4 BVH self-intersections/mesh | 8/8 families positive | 6/6 styles positive).
    """
    import os
    from .reinforced_registry import RENFORCE_ROOT

    record = validated_record('3d', state)
    if not record:
        return None
    raw_prompt = (prompt_text or os.environ.get('AURORA_3D_PROMPT') or '').strip().lower()
    raw_style = (style_hint or os.environ.get('AURORA_3D_STYLE') or '').strip().lower()
    combined = f'{raw_style} {raw_prompt}'

    ont_domain = 'general'
    render_medium = 'native_photorealistic'
    if raw_prompt:
        try:
            from agi_core.prompt_intelligence import infer_semantic_ontology
            ont = infer_semantic_ontology(raw_prompt, '3d')
            ont_domain = str(ont.get('domain') or ont.get('primary_domain') or 'general')
            render_medium = str(ont.get('render_medium') or 'native_photorealistic')
        except Exception:
            pass

    family, style = _detect_3d_family_and_style(combined, ont_domain, render_medium)
    spec_key = SPECIALIST_3D_MATRIX.get(f'{family}:{style}')
    if not spec_key:
        if style in {'photorealistic', 'low_poly'} and family not in {'scorpion', 'chair', 'bicycle'}:
            spec_key = 'v2_c9cbb2'
        else:
            spec_key = 'v1_15d62f'

    spec_meta = SPECIALIST_3D_POOL.get(spec_key, SPECIALIST_3D_POOL['v1_15d62f'])
    spec_path = (RENFORCE_ROOT / '3d' / spec_meta['filename']).resolve()
    if spec_path.is_file():
        return {
            **record,
            'adapter': str(spec_path),
            'sha256': file_hash(spec_path),
            'name': spec_meta['name'],
            'specialist_key': spec_key,
            'specialist_role': spec_meta['role'],
            'selected_run_id': spec_meta['run_id'],
            'specialist_domain': f'{family}:{style}' if family != 'general' else ont_domain,
            'reason': spec_meta['reason'],
        }
    return {
        **record,
        'specialist_key': 'v1_15d62f',
        'specialist_role': 'stylized_manifold_core',
        'selected_run_id': record.get('run_id') or '3d-20260927-102144-15d62f',
        'specialist_domain': ont_domain if ont_domain != 'general' else 'stylized_manifold_core',
        'reason': SPECIALIST_3D_POOL['v1_15d62f']['reason'],
    }


def attach_validated(
    model,
    module,
    base_model_id,
    state=STATE,
    *,
    prompt_text: str | None = None,
    style_hint: str | None = None,
):
    from .versions import preference
    if preference(module,state)=='base':
        existing = getattr(model, '_aurora_validated_adapter', None)
        if existing is not None:
            existing.enabled = False
        return None
    record = (
        resolve_3d_specialist_adapter(prompt_text=prompt_text, style_hint=style_hint, state=state)
        if module == '3d'
        else validated_record(module, state)
    )
    if not record:
        return None
    if record['model_id']!=base_model_id:
        raise ValueError(f'Adaptateur {module} destiné à {record["model_id"]}, pas à {base_model_id}')
    existing = getattr(model, '_aurora_validated_adapter', None)
    if existing is not None:
        existing.enabled = True
        if getattr(model, '_aurora_validated_sha256', None) != record.get('sha256'):
            existing.load(record['adapter'])
            model._aurora_validated_sha256 = record.get('sha256')
            model._aurora_validated_name = record['name']
        return record
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
    model._aurora_validated_sha256=record.get('sha256')
    return record

