"""Reuse measured training generations only under an identical contract."""
from pathlib import Path
import os
import shutil
from .storage import digest, file_hash, read_json, atomic_json


def key(task, seed, generation, weights):
    return digest({'task':{k:v for k,v in task.items() if not k.startswith('failure_')},
                   'seed':seed,'generation':generation,'weights':weights,'version':1})


def lookup(state, identifier, latent=False):
    try:
        entry=read_json(Path(state)/'rollout_cache'/(identifier+'.json'),{})
        row=entry.get('row',{})
        artifact=Path(row['artifact'])
        if not artifact.resolve().is_relative_to((Path(state)/'runs').resolve()):return None
        if file_hash(artifact)!=row['sha256']:return None
        if latent and file_hash(artifact.with_suffix('.latent.safetensors'))!=entry.get('latent_sha256'):return None
        # Recomputed by the caller: changed judges must not reuse old scores.
        return row
    except (OSError,ValueError,KeyError,TypeError):
        return None


def save(state, identifier, row, latent=False):
    entry={'row':row}
    if latent:entry['latent_sha256']=file_hash(Path(row['artifact']).with_suffix('.latent.safetensors'))
    atomic_json(Path(state)/'rollout_cache'/(identifier+'.json'),entry)


def materialize(row,target,latent=False):
    """Link immutable measured outputs into this run without duplicating bytes."""
    source=Path(row['artifact']);target=Path(target);target.parent.mkdir(parents=True,exist_ok=True)
    pairs=[(source,target)]
    if latent:pairs.append((source.with_suffix('.latent.safetensors'),target.with_suffix('.latent.safetensors')))
    for src,dst in pairs:
        if src.resolve()==dst.resolve():continue
        dst.unlink(missing_ok=True)
        try:os.link(src,dst)
        except OSError:shutil.copy2(src,dst)
    return {**row,'artifact':str(target),'reused_from':str(source)}
