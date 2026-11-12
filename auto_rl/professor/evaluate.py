"""Examine a student on a fixed item set and write graded, resumable results.

One line per item goes to ``results.jsonl`` as soon as it is graded, so a cloud
session that is cut short can resume without re-running or re-grading anything.
"""
from __future__ import annotations

import hashlib
import json
import time
from collections import defaultdict
from pathlib import Path

from . import graders
from .compare import wilson
from .graders import grade
from .records import atomic_json, digest, file_hash, read_json, suite_digest


#: Production validators the graders call: their content is part of what a grade means.
_VALIDATORS = ("agi_core/mission_protocol.py", "agi_core/json_evidence.py", "agi_core/json_predicates.py")


def run_identity(student, items):
    """What a results file answers for: the model as described (adapter weights included), the exam with each
    item's answer budget, the graders and the production validators they call.

    Resuming is only safe under the same identity: rows written by another adapter in the same folder were
    reused and certified as the new one's answers (review, 2026-11-12).
    """
    root = Path(graders.__file__).resolve().parents[2]
    exam = digest(sorted(([item["id"], item.get("max_new_tokens"), item["messages"], item["grader"]] for item in items),
                         key=lambda entry: entry[0]))
    return {"student": student.describe(), "suite_sha256": suite_digest(items), "exam_sha256": exam,
            "graders_sha256": file_hash(graders.__file__),
            "validators_sha256": {name: file_hash(root / name) for name in _VALIDATORS if (root / name).is_file()}}


def _read(path):
    """Rows of a results file. A last line cut by a killed process is dropped (and regenerated on resume);
    a damaged line anywhere else is an error."""
    rows = []
    if Path(path).is_file():
        lines = [line for line in Path(path).read_text(encoding="utf-8").splitlines() if line.strip()]
        for number, line in enumerate(lines):
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                if number == len(lines) - 1:
                    break
                raise
    return rows


def read_results(folder):
    return _read(Path(folder) / "results.jsonl")


def summarize(rows):
    """Accuracy with Wilson intervals per module, skill and sub-skill (graded rows only)."""
    graded = [row for row in rows if row.get("status", "graded") == "graded"]
    levels = {"modules": defaultdict(list), "skills": defaultdict(list), "subskills": defaultdict(list)}
    for row in graded:
        levels["modules"][row["module"]].append(row)
        levels["skills"][row["skill"]].append(row)
        levels["subskills"][f"{row['skill']} / {row.get('subskill')}"].append(row)

    def table(group):
        n, correct = len(group), sum(bool(r["correct"]) for r in group)
        low, high = wilson(correct, n)
        return {"items": n, "correct": correct, "accuracy": correct / n if n else None, "ci95": [low, high],
                "mean_score": sum(r.get("score", 0.0) for r in group) / n if n else None,
                "module": group[0]["module"] if group else None}
    summary = {name: {key: table(group) for key, group in sorted(groups.items())} for name, groups in levels.items()}
    macro = [entry["accuracy"] for entry in summary["skills"].values() if entry["items"]]
    summary["overall"] = {**table(graded), "macro_accuracy": sum(macro) / len(macro) if macro else None,
                          "skipped": len(rows) - len(graded),
                          "empty_answers": sum(not str(r.get("output") or "").strip() for r in graded)}
    return summary


def evaluate(student, items, folder, *, batch_size=8, label="exam", progress=None, budget_seconds=None):
    """Grade ``items`` with ``student``; returns the summary and writes a receipt."""
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    results_path = folder / "results.jsonl"
    identity = run_identity(student, items)
    recorded = read_json(folder / "run_identity.json", None)
    if results_path.is_file() and (recorded is None or digest(recorded) != digest(identity)):
        # Another model, adapter, exam or grader wrote these rows: keep them aside, never resume from them.
        stale = folder / f"results.stale-{digest(recorded or {})[:12]}.jsonl"
        results_path.replace(stale)
    atomic_json(folder / "run_identity.json", identity)
    done = {row["id"] for row in _read(results_path)}
    pending = [item for item in items if item["id"] not in done]
    started = time.monotonic()
    # Similar answer budgets share a batch so a long task does not slow short ones.
    groups = defaultdict(list)
    for item in pending:
        groups[int(item.get("max_new_tokens", 96))].append(item)
    complete = True
    with results_path.open("a", encoding="utf-8") as stream:
        for tokens in sorted(groups):
            group = groups[tokens]
            for start in range(0, len(group), batch_size * 4):
                if budget_seconds is not None and time.monotonic() - started > budget_seconds:
                    complete = False
                    break
                chunk = group[start:start + batch_size * 4]
                outputs = student.generate([item["messages"] for item in chunk], tokens, batch_size=batch_size)
                for item, output in zip(chunk, outputs):
                    row = {"id": item["id"], "module": item["module"], "skill": item["skill"],
                           "subskill": item.get("subskill"), "source": item.get("source")}
                    if output is None:
                        row.update(status="skipped_prompt_too_long", correct=False, score=0.0, output=None)
                    else:
                        result = grade(item, output)
                        row.update(status="graded", correct=result["correct"], score=result["score"],
                                   reason=result["reason"], output=output[:4000])
                    stream.write(json.dumps(row, ensure_ascii=False) + "\n")
                    stream.flush()                    # one complete line at a time
                if progress:
                    progress({"label": label, "graded": len(_read(results_path)), "total": len(items),
                              "elapsed_seconds": round(time.monotonic() - started, 1)})
            if not complete:
                break
    rows = _read(results_path)
    wanted = {item["id"] for item in items}
    rows = [row for row in rows if row["id"] in wanted]
    summary = summarize(rows)
    receipt = {"kind": "aurora_professor_exam", "label": label, "complete": complete and len(rows) == len(items),
               "items": len(items), "graded_rows": len(rows), "suite_sha256": suite_digest(items),
               "results_sha256": hashlib.sha256(results_path.read_bytes()).hexdigest(),
               "student": student.describe(), "decoding": {"do_sample": False, "batch_size": batch_size},
               "elapsed_seconds": round(time.monotonic() - started, 1), "summary": summary}
    atomic_json(folder / "exam_receipt.json", receipt)
    return receipt
