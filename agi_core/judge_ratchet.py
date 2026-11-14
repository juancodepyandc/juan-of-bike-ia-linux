"""Durable, process-safe audit levels shared by representative and semantic judges."""
from __future__ import annotations

from contextlib import contextmanager
import json
import os
import re
from pathlib import Path

from auto_rl.storage import atomic_json

DEFAULT_STATE = Path(__file__).resolve().parents[1] / "modele/renforce/judge_ratchet_state.json"
BASE_LEVEL = 75


@contextmanager
def _locked(path):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.with_suffix(path.suffix + ".lock").open("a+b") as stream:
        if os.name == "nt":
            import msvcrt
            if os.fstat(stream.fileno()).st_size == 0:
                stream.write(b"\0")
                stream.flush()
            stream.seek(0)
            msvcrt.locking(stream.fileno(), msvcrt.LK_LOCK, 1)
        else:
            import fcntl
            fcntl.flock(stream.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            stream.seek(0)
            if os.name == "nt":
                msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(stream.fileno(), fcntl.LOCK_UN)


def judge_ratchet(*, advance=False, path=None):
    """Never reset corrupt state or claim an increment that was not persisted."""
    is_default = path is None or Path(path).resolve() == DEFAULT_STATE.resolve()
    path = Path(path) if path is not None else DEFAULT_STATE
    with _locked(path):
        state = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
        if not isinstance(state, dict):
            raise ValueError("Invalid judge ratchet state; preserved for inspection")
        level = state.get("ratchet_level", BASE_LEVEL)
        runs = state.get("history_runs", 0)
        if type(level) is not int or type(runs) is not int or level < 0 or runs < 0:
            raise ValueError("Invalid judge ratchet counters; preserved for inspection")
        if is_default:
            sibling_report = path.parent / "representative_judge_report.json"
            if sibling_report.exists():
                try:
                    rep_obj = json.loads(sibling_report.read_text(encoding="utf-8"))
                    rep_ratchet = rep_obj.get("progressive_judge_ratchet") if isinstance(rep_obj, dict) else None
                    if isinstance(rep_ratchet, dict):
                        rep_lvl = rep_ratchet.get("ratchet_level")
                        rep_runs = rep_ratchet.get("history_runs")
                        if type(rep_lvl) is int and rep_lvl > level:
                            level = rep_lvl
                        if type(rep_runs) is int and rep_runs > runs:
                            runs = rep_runs
                except Exception:
                    pass
        level = max(BASE_LEVEL, level)
        if advance:
            level += 1
            runs += 1
            state.update(ratchet_level=level, history_runs=runs)
            atomic_json(path, state)
        return {
            **state, "ratchet_level": level, "history_runs": runs,
            # Growing evidence requirement remains strict after physical thresholds saturate.
            "required_holdout_cases": level + 1,
            "max_unverified_claims": 0,
            "max_error_probability": 1.0 / (level + 1),
        }


# Canonical definition of the gate. Any other import path (agi_core.anti_hallucination_guard,
# used by the local judges) must re-export this function instead of carrying its own copy.
def judge_independent_holdout_evidence(records, *, ratchet=None):
    """Conservative audit gate; asserted model scores cannot replace observed cases.

    This checks the audit contract, not the truth of arbitrary third-party claims.
    The caller must supply independent, previously unseen executed test cases.
    """
    ratchet = judge_ratchet() if ratchet is None else ratchet
    required = ratchet["required_holdout_cases"]
    valid = []
    seen = set()
    invalid = 0
    for record in records:
        if (not isinstance(record, dict) or record.get("independent_holdout") is not True
                or record.get("executed") is not True or type(record.get("passed")) is not bool
                or not re.fullmatch(r"[a-f0-9]{64}", str(record.get("case_sha256", "")))
                or not re.fullmatch(r"[a-f0-9]{64}", str(record.get("receipt_sha256", "")))):
            invalid += 1
            continue
        identity = record["case_sha256"]
        if identity in seen:
            invalid += 1
            continue
        seen.add(identity)
        valid.append(record)
    failures = sum(not r["passed"] for r in valid)
    return {"passed": len(valid) >= required and failures == 0 and invalid == 0,
            "ratchet_level": ratchet["ratchet_level"], "required_holdout_cases": required,
            "observed_cases": len(valid), "failed_cases": failures, "unverified_or_duplicate_cases": invalid,
            "scope": "Independent holdout receipt contract; does not certify general intelligence or unseen inputs"}
