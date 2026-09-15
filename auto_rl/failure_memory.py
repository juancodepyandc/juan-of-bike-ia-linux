"""Durable hard-negative memory shared by every Aurora training backend.

Only failures observed on training subjects are replayed.  Held-out audit
subjects never enter this file, so replay improves the candidate without
leaking the validation set into training.
"""
from __future__ import annotations

import copy
import time
from pathlib import Path

from .storage import atomic_json, digest, read_json


def _json_safe(value):
    """Return a bounded JSON-compatible copy of a task or judge payload."""
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(v) for v in value]
    return str(value)


def _signature(task):
    if task.get("failure_signature"):
        return str(task["failure_signature"])
    return digest({
        "family": task.get("family"),
        "prompt": " ".join(str(task.get("prompt", "")).split()).casefold(),
        "image": task.get("image"),
    })


def _score_key(entry):
    score = entry.get("worst_score")
    return float(score) if isinstance(score, (int, float)) else -1.0


def _path(state, module):
    folder = Path(state) / "failure_memory"
    folder.mkdir(parents=True, exist_ok=True)
    return folder / (str(module) + ".json")


def record_failure(state, module, task, row=None, *, error=None, run_id=None, limit=256):
    """Persist one training failure and merge repeated observations.

    This function is deliberately best-effort: inability to write diagnostics
    must never hide the measured training result or its original exception.
    """
    if task.get("split") != "train":
        return False
    try:
        path = _path(state, module)
        entries = read_json(path, [])
        if not isinstance(entries, list):
            entries = []
        task_copy = _json_safe(copy.deepcopy(task))
        if task_copy.get("base_prompt"):
            # Do not append a new diagnostic to the same prompt on every
            # continuous cycle; retain the original task as the anchor.
            task_copy["prompt"] = task_copy["base_prompt"]
        judge = _json_safe((row or {}).get("judge", {}))
        score = judge.get("score") if isinstance(judge, dict) else None
        signature = _signature(task_copy)
        now = time.time()
        existing = next((item for item in entries if item.get("signature") == signature), None)
        if existing is None:
            existing = {
                "schema": 1,
                "signature": signature,
                "module": module,
                "task": task_copy,
                "attempts": 0,
                "first_seen_at": now,
            }
            entries.append(existing)
        existing["task"] = task_copy
        existing["attempts"] = int(existing.get("attempts", 0)) + 1
        existing["last_seen_at"] = now
        existing["run_id"] = run_id
        existing["worst_score"] = min(
            [x for x in (existing.get("worst_score"), score) if isinstance(x, (int, float))],
            default=None,
        )
        existing["last_judge"] = judge
        if error:
            existing["last_error"] = str(error)[:2000]
        # Keep the state bounded while retaining the worst and most recent
        # cases.  The radical profile can override this limit.
        entries.sort(key=lambda item: (_score_key(item), -item.get("last_seen_at", 0.0)))
        atomic_json(path, entries[: max(1, int(limit))])
    except Exception:
        return False
    return True


def replay_tasks(tasks, config, state):
    """Replace a few ordinary training subjects with observed hard cases."""
    count=int(config['train_tasks'])
    limit=min(int(config.get('failure_replay_tasks',4)), max(0,count//2))
    if limit<=0:return tasks
    train=copy.deepcopy(tasks[:count]);audit=tasks[count:]
    audit_families={t.get('family') for t in audit if t.get('family')}
    audit_signatures={_signature(t) for t in audit}
    entries=read_json(_path(state,config['module']),[])
    if not isinstance(entries,list):return tasks
    entries=[e for e in entries if isinstance(e,dict) and isinstance(e.get('task'),dict)]
    entries.sort(key=lambda e:(_score_key(e),-e.get('last_seen_at',0)))
    used=set();replayed=0
    for entry in entries:
        task=copy.deepcopy(entry['task'])
        if task.get('split')!='train' or task.get('family') in audit_families:continue
        if task.get('base_prompt'):task['prompt']=task.pop('base_prompt')
        signature=_signature(task)
        if signature in used or signature in audit_signatures:continue
        if task.get('image') and not Path(task['image']).is_file():continue
        # Keep the exact instruction: appending diagnostics corrupts speech,
        # image/text alignment and the conditioning of diffusion generators.
        used.add(signature)
        match=next((i for i,t in enumerate(train) if _signature(t)==signature),None)
        slot=match if match is not None else count-1-replayed
        task.update(split='train',origin='observed_failure_replay',
                    failure_signature=signature,failure_attempts=entry.get('attempts',1))
        task['id']='failure_'+signature[:16]
        train[slot]=task
        replayed+=1
        if replayed>=limit:break
    # Never shorten the training slice and accidentally move an audit subject
    # into it. A conflicting legacy record is ignored, not relabelled.
    if len({t['id'] for t in train+audit})!=len(tasks):return tasks
    return train+audit
