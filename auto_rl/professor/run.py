"""Roles of the professor loop, runnable on one machine or split across two.

    python -m auto_rl.professor.run diagnose --student qwen2.5:7b --work RUN     # examiner
    python -m auto_rl.professor.run train    --student qwen2.5:7b --work RUN --diagnosis RUN/diagnosis.json   # trainer
    python -m auto_rl.professor.run verify   --student qwen2.5:7b --work RUN --adapter RUN/training/adapter   # examiner
    python -m auto_rl.professor.run cycle    --student qwen3:0.6b --profile smoke --work RUN                  # rehearsal

The trainer only ever reads ``diagnosis.json``: aggregate scores and question
hashes. Exam items stay on the examiner. No role promotes a model: ``verify``
writes a verdict, and installation is a separate, explicit step.
"""
from __future__ import annotations

import argparse
import json
import os
import platform
import time
from pathlib import Path

from . import SCHEMA
from .records import atomic_json, digest, file_hash, read_json
from .compare import compare
from .evaluate import evaluate, read_results
from .inference import hardware, library_versions
from .students import resolve
from .suites import Library, MODULES, build_exam, build_pool, exam_blocklist, skills
from .weakness import build_curriculum, profile, skill_weights, subskill_weights

PROFILES = {
    # Rehearsal on a CPU or a small GPU: proves the mechanics, too small to certify a module.
    "smoke": {"diagnostic_per_skill": 12, "gate_per_skill": 16, "pool_per_skill": 60, "curriculum": 320,
              "mine_per_skill": 8, "max_tokens": 1024, "max_prompt_tokens": 1400, "batch_size": 4, "accumulate": 2,
              "epochs": 2.0, "eval_batch": 8, "eval_every": 10, "row_limit": 1500, "min_items": 60},
    "standard": {"diagnostic_per_skill": 60, "gate_per_skill": 100, "pool_per_skill": 1200, "curriculum": 6000,
                 "mine_per_skill": 40, "max_tokens": 1536, "max_prompt_tokens": 3072, "batch_size": 4, "accumulate": 4,
                 "epochs": 2.0, "eval_batch": 8, "eval_every": 50, "row_limit": None, "min_items": 200},
    "full": {"diagnostic_per_skill": 150, "gate_per_skill": 250, "pool_per_skill": 4000, "curriculum": 20000,
             "mine_per_skill": 80, "max_tokens": 2048, "max_prompt_tokens": 4096, "batch_size": 4, "accumulate": 4,
             "epochs": 2.0, "eval_batch": 8, "eval_every": 100, "row_limit": None, "min_items": 400},
}
#: Free-form skills kept in every curriculum so drills do not erode fluent answers.
REPLAY = ("conversation.instruct_fr", "business.advice", "cyber.defense", "code.polyglot")
#: Graders that execute generated programs; excluded unless explicitly allowed.
EXECUTING = ("python_tests",)


def status(payload):
    """One machine-readable line per event, for remote log followers."""
    print("AURORA_STATUS " + json.dumps(payload, ensure_ascii=False), flush=True)


def settings(args):
    config = {**PROFILES[args.profile], "profile": args.profile, "student": resolve(args.student),
              "modules": sorted(set(args.modules.split(","))) if args.modules else sorted(MODULES),
              "skills": sorted(set(args.skills.split(","))) if args.skills else None,
              "cycle": args.cycle, "budget_seconds": args.budget_minutes * 60 if args.budget_minutes else None,
              "four_bit": args.four_bit, "export": args.export,
              "allow_execution": os.environ.get("AURORA_PROFESSOR_ALLOW_CODE_EXECUTION") == "1"}
    for name in ("diagnostic_per_skill", "gate_per_skill", "curriculum", "epochs", "learning_rate", "rank", "max_tokens"):
        value = getattr(args, name, None)
        if value is not None:
            config[name] = value
    unknown = set(config["modules"]) - set(MODULES)
    if unknown:
        raise SystemExit(f"Unknown modules: {sorted(unknown)}; known: {sorted(MODULES)}")
    return config


def open_student(config, adapter=None):
    from .inference import TransformersStudent
    entry = config["student"]
    return TransformersStudent(entry["hf"], revision=entry.get("revision"), four_bit=config["four_bit"], adapter=adapter,
                               max_prompt_tokens=config["max_prompt_tokens"], thinking=False,
                               token=os.environ.get("HF_TOKEN") or None)


def _exam(config, role, library):
    items, notes = build_exam(role, config[f"{role}_per_skill"], modules=config["modules"], cycle=config["cycle"],
                              library=library, only=config["skills"])
    if not config["allow_execution"]:
        skipped = sorted({item["skill"] for item in items if item["grader"]["type"] in EXECUTING})
        items = [item for item in items if item["grader"]["type"] not in EXECUTING]
        notes["skipped_no_execution"] = skipped
    return items, notes


def _context(config):
    return {"schema": SCHEMA, "student": config["student"], "profile": config["profile"], "modules": config["modules"],
            "skills": config["skills"],
            "cycle": config["cycle"], "hardware": hardware(), "versions": library_versions(),
            "python": platform.python_version(), "host": platform.node(), "created_at": time.time()}


def diagnose(config, work, student=None, library=None):
    """Examiner: measure the base model and publish weak points plus the exam blocklist."""
    work = Path(work)
    library = library or Library(row_limit=config["row_limit"])
    student = student or open_student(config)
    items, notes = _exam(config, "diagnostic", library)
    status({"phase": "diagnose", "items": len(items)})
    receipt = evaluate(student, items, work / "diagnosis", batch_size=config["eval_batch"], label="diagnostic",
                       progress=status, budget_seconds=config["budget_seconds"])
    catalogue = skills(config["modules"], config["skills"])
    report = {**_context(config), "kind": "aurora_professor_diagnosis", "complete": receipt["complete"],
              "summary": receipt["summary"], "weak_points": profile(receipt["summary"], catalogue),
              "exam": {"suite_sha256": receipt["suite_sha256"], "results_sha256": receipt["results_sha256"], "notes": notes},
              "blocklist": exam_blocklist(modules=config["modules"], library=library, only=config["skills"])}
    atomic_json(work / "diagnosis.json", report)
    return report


def train_role(config, work, diagnosis, student=None, library=None):
    """Trainer: build a curriculum aimed at the measured weak points and fit an adapter."""
    from .train import train
    work = Path(work)
    library = library or Library(row_limit=config["row_limit"])
    student = student or open_student(config)
    if diagnosis["student"]["hf"] != config["student"]["hf"]:
        raise ValueError("This diagnosis describes another student")
    weak = diagnosis["weak_points"]
    pool, pool_notes = build_pool(config["pool_per_skill"], modules=config["modules"], blocklist=diagnosis["blocklist"],
                                  library=library, subskill_weights=subskill_weights(weak), only=config["skills"])
    # Probe the base model on training items it can be graded on: what it fails goes first.
    probes = []
    for name, items in pool.items():
        gradable = [item for item in items if item.get("grader") and (config["allow_execution"] or item["grader"]["type"] not in EXECUTING)]
        probes += gradable[:config["mine_per_skill"]]
    mined = {}
    if probes:
        status({"phase": "mine", "items": len(probes)})
        evaluate(student, probes, work / "mine", batch_size=config["eval_batch"], label="mine", progress=status,
                 budget_seconds=config["budget_seconds"] and config["budget_seconds"] * 0.15)
        mined = {row["id"]: bool(row["correct"]) for row in read_results(work / "mine") if row["status"] == "graded"}
    weights = skill_weights(weak, [name for name in pool if name not in REPLAY])
    chosen, plan = build_curriculum(pool, weights, config["curriculum"], mined=mined, replay_skills=REPLAY)
    atomic_json(work / "curriculum.json", {"kind": "aurora_professor_curriculum", "plan": plan, "weights": weights,
                                           "pool": pool_notes, "mined": {"probed": len(mined), "failed": sum(not v for v in mined.values())},
                                           "diagnosis_sha256": digest({k: diagnosis[k] for k in ("summary", "exam")})})
    status({"phase": "train", "examples": len(chosen)})
    knobs = {k: config[k] for k in ("max_tokens", "batch_size", "accumulate", "epochs", "eval_every", "learning_rate", "rank") if k in config}
    if config["student"].get("attention_only"):
        knobs["attention_only"] = True
    receipt = train(student, chosen, work / "training", config=knobs, progress=status,
                    budget_seconds=config["budget_seconds"] and config["budget_seconds"] * 0.6)
    return receipt


def verify(config, work, adapter, student=None, library=None, base_done=False):
    """Examiner: paired exam of base and candidate on this cycle's unseen gate."""
    work = Path(work)
    library = library or Library(row_limit=config["row_limit"])
    items, notes = _exam(config, "gate", library)
    gate = work / f"gate_{config['cycle']}"
    if not base_done:
        student = student or open_student(config)
        status({"phase": "gate_base", "items": len(items)})
        evaluate(student, items, gate / "base", batch_size=config["eval_batch"], label="gate_base", progress=status,
                 budget_seconds=config["budget_seconds"] and config["budget_seconds"] * 0.45)
        student.attach(adapter)
    status({"phase": "gate_candidate", "items": len(items)})
    evaluate(student, items, gate / "candidate", batch_size=config["eval_batch"], label="gate_candidate", progress=status,
             budget_seconds=config["budget_seconds"] and config["budget_seconds"] * 0.45)
    base_rows, candidate_rows = read_results(gate / "base"), read_results(gate / "candidate")
    common = {r["id"] for r in base_rows if r["status"] == "graded"} & {r["id"] for r in candidate_rows if r["status"] == "graded"}
    # Complete means both models met every item; a prompt over the context budget is skipped for both alike.
    complete = {r["id"] for r in base_rows} == {r["id"] for r in candidate_rows} == {item["id"] for item in items}
    result = compare([r for r in base_rows if r["id"] in common], [r for r in candidate_rows if r["id"] in common],
                     gate={"min_items": config["min_items"]})
    if not complete and result["verdict"] == "promote":
        result["verdict"] = "inconclusive"
        result["reasons"].insert(0, "the gate exam was not finished for both models")
    adapter = Path(adapter)
    weights = next((p for p in sorted(adapter.glob("adapter_model.*")) if p.is_file()), None)
    training = read_json(adapter.parent / "train_receipt.json", {})
    verdict = {**_context(config), "kind": "aurora_professor_verdict", **result, "exam_complete": complete,
               "exam": {"items": len(items), "graded_both": len(common), "notes": notes,
                        "base_receipt": read_json(gate / "base" / "exam_receipt.json", {}).get("results_sha256"),
                        "candidate_receipt": read_json(gate / "candidate" / "exam_receipt.json", {}).get("results_sha256"),
                        "suite_sha256": read_json(gate / "base" / "exam_receipt.json", {}).get("suite_sha256")},
               "adapter_sha256": file_hash(weights) if weights else None,
               "training": {k: training.get(k) for k in ("steps", "stopped", "selected_step", "initial_dev_loss",
                                                         "selected_dev_loss", "examples", "data_sha256", "trainable_parameters")},
               # A rehearsal student is not called by any module: its verdict can never authorise an installation.
               "promotable": result["verdict"] == "promote" and complete and bool(config["student"]["production"])}
    atomic_json(work / f"verdict_{config['cycle']}.json", verdict)
    wanted = config.get("export", "promote")
    if wanted == "always" or (wanted == "promote" and verdict["promotable"]):
        # Files Ollama can load. A failed conversion is recorded in the receipt and never changes the verdict.
        from .export import export
        status({"phase": "export"})
        try:
            from huggingface_hub import snapshot_download
            snapshot = snapshot_download(config["student"]["hf"], revision=config["student"].get("revision"),
                                         allow_patterns=["*.json"], token=os.environ.get("HF_TOKEN") or None)
            receipt = export(config["student"], adapter, work / "export", base_snapshot=snapshot)
            status({"phase": "export", "files": sorted(receipt["files"]), "errors": receipt["errors"]})
        except Exception as exc:
            atomic_json(work / "export" / "export_receipt.json", {"kind": "aurora_professor_export", "files": {},
                                                                 "errors": {"export": f"{type(exc).__name__}: {str(exc)[:600]}"}})
    return verdict


def cycle(config, work):
    """Whole loop on one machine (rehearsal): same files and same separation as the split roles."""
    work = Path(work)
    library = Library(row_limit=config["row_limit"])
    student = open_student(config)
    share = dict(config)
    if config["budget_seconds"]:
        share["budget_seconds"] = config["budget_seconds"] * 0.2
    diagnosis = diagnose(share, work, student, library)
    items, _ = _exam(config, "gate", library)
    status({"phase": "gate_base", "items": len(items)})
    evaluate(student, items, work / f"gate_{config['cycle']}" / "base", batch_size=config["eval_batch"], label="gate_base",
             progress=status, budget_seconds=share["budget_seconds"])
    train_role(config, work, diagnosis, student, library)
    return verify(share, work, work / "training" / "adapter", student, library, base_done=True)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("role", choices=("probe", "diagnose", "train", "verify", "cycle"))
    parser.add_argument("--student", default="qwen3:0.6b", help="Ollama tag or Hugging Face id listed in students.py")
    parser.add_argument("--profile", choices=sorted(PROFILES), default="standard")
    parser.add_argument("--modules", help="Comma-separated subset of: " + ", ".join(sorted(MODULES)))
    parser.add_argument("--skills", help="Comma-separated skill names for a targeted cycle (default: every skill of the modules)")
    parser.add_argument("--work", type=Path)
    parser.add_argument("--cycle", type=int, default=0, help="Selects a fresh, disjoint gate exam")
    parser.add_argument("--diagnosis", type=Path)
    parser.add_argument("--adapter", type=Path)
    parser.add_argument("--budget-minutes", type=float)
    parser.add_argument("--four-bit", action=argparse.BooleanOptionalAction, default=None)
    parser.add_argument("--export", choices=("promote", "always", "never"), default="promote",
                        help="Convert the adapter to GGUF after verification (default: only when promotable)")
    for name, kind in (("diagnostic_per_skill", int), ("gate_per_skill", int), ("curriculum", int), ("epochs", float),
                       ("learning_rate", float), ("rank", int), ("max_tokens", int)):
        parser.add_argument("--" + name.replace("_", "-"), type=kind)
    args = parser.parse_args(argv)
    if args.role == "probe":
        print(json.dumps({"hardware": hardware(), "versions": library_versions()}, indent=2))
        return 0
    if args.work is None:
        parser.error("--work is required")
    config = settings(args)
    args.work.mkdir(parents=True, exist_ok=True)
    if args.role == "diagnose":
        result = diagnose(config, args.work)
        summary = {"complete": result["complete"], "macro_accuracy": result["summary"]["overall"]["macro_accuracy"],
                   "weakest": [(w["skill"], round(w["accuracy"], 3)) for w in result["weak_points"][:8]]}
    elif args.role == "train":
        if args.diagnosis is None:
            parser.error("train requires --diagnosis from the examiner")
        receipt = train_role(config, args.work, json.loads(args.diagnosis.read_text(encoding="utf-8")))
        summary = {k: receipt[k] for k in ("steps", "stopped", "initial_dev_loss", "selected_dev_loss", "elapsed_seconds")}
    elif args.role == "verify":
        if args.adapter is None:
            parser.error("verify requires --adapter")
        result = verify(config, args.work, args.adapter)
        summary = {"verdict": result["verdict"], "reasons": result["reasons"], "overall": result["overall"], "promotable": result["promotable"]}
    else:
        result = cycle(config, args.work)
        summary = {"verdict": result["verdict"], "reasons": result["reasons"], "overall": result["overall"], "promotable": result["promotable"]}
    print("AURORA_RESULT " + json.dumps(summary, ensure_ascii=False), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
