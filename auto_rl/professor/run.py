"""Roles of the professor loop, runnable on one machine or split across two.

    python -m auto_rl.professor.run diagnose --student qwen2.5:7b --work RUN     # examiner
    python -m auto_rl.professor.run train    --student qwen2.5:7b --work RUN --diagnosis RUN/diagnosis.json   # trainer
    python -m auto_rl.professor.run verify   --student qwen2.5:7b --work RUN --adapter RUN/training/adapter   # examiner
    python -m auto_rl.professor.run cycle    --student qwen3:0.6b --profile smoke --work RUN                  # rehearsal

A later cycle continues the adapter instead of starting again. ``verify`` also writes
``diagnosis_next_N.json``, the scores of the trained candidate on the gate it just sat:

    python -m auto_rl.professor.run train  --cycle 1 --work RUN1 --diagnosis RUN/diagnosis_next_0.json --init-adapter RUN/training/adapter
    python -m auto_rl.professor.run verify --cycle 1 --work RUN1 --adapter RUN1/training/adapter --previous-adapter RUN1/training/init_adapter

The trainer only ever reads a diagnosis: aggregate scores and question hashes.
Exam items stay on the examiner. No role promotes a model: ``verify`` writes a
verdict, and installation is a separate, explicit step.
"""
from __future__ import annotations

import argparse
import json
import os
import platform
import re
import shutil
import time
from pathlib import Path

from . import SCHEMA
from .records import atomic_json, digest, file_hash, read_json
from .compare import GATE, compare
from .evaluate import evaluate, read_results
from .inference import hardware, library_versions
from .students import resolve
from .suites import Library, MODULES, build_exam, build_pool, exam_blocklist, skills, stratified
from .weakness import build_curriculum, profile, skill_weights, subskill_weights

PROFILES = {
    # Rehearsal on a CPU or a small GPU: proves the mechanics, too small to certify a module.
    "smoke": {"diagnostic_per_skill": 12, "gate_per_skill": 16, "pool_per_skill": 60, "curriculum": 320,
              "mine_per_skill": 8, "self_worked_per_skill": 8, "max_tokens": 640, "max_prompt_tokens": 1400, "batch_size": 2, "accumulate": 4,
              "epochs": 2.0, "eval_batch": 8, "eval_every": 10, "row_limit": 1500, "min_items": 60},
    "standard": {"diagnostic_per_skill": 60, "gate_per_skill": 100, "pool_per_skill": 1200, "curriculum": 6000,
                 "mine_per_skill": 40, "self_worked_per_skill": 250, "max_tokens": 1536, "max_prompt_tokens": 3072, "batch_size": 4, "accumulate": 4,
                 "epochs": 2.0, "eval_batch": 8, "eval_every": 50, "row_limit": None, "min_items": 200},
    "full": {"diagnostic_per_skill": 150, "gate_per_skill": 150, "pool_per_skill": 4000, "curriculum": 20000,
             "mine_per_skill": 80, "self_worked_per_skill": 500, "max_tokens": 2048, "max_prompt_tokens": 4096, "batch_size": 4, "accumulate": 4,
             "epochs": 2.0, "eval_batch": 8, "eval_every": 100, "row_limit": None, "min_items": 400},
}
#: Free-form skills kept in every curriculum so drills do not erode fluent answers.
REPLAY = ("conversation.instruct_fr", "business.advice", "cyber.defense", "code.polyglot")
#: Graders that execute generated programs; excluded unless explicitly allowed.
EXECUTING = ("python_tests",)
#: Skills whose reference targets give a result without the work that leads to it (source sentences then a
#: number, or a formula then a number). Trained on such targets on 2026-11-12, a 7B student stopped computing
#: step by step: -14 and -15 points on report questions, no gain on financial arithmetic, verdict "reject".
#: For these skills the only training targets are the student's OWN worked answers that the grader verified.
SELF_WORKED = ("business.finqa", "business.fin_math", "engineering.calc")


def status(payload):
    """One machine-readable line per event, for remote log followers."""
    print("AURORA_STATUS " + json.dumps(payload, ensure_ascii=False), flush=True)


def _names(text, default, option):
    """A comma-separated list of skills for an explicit trainer choice; ``None`` keeps the default."""
    if text is None:
        return tuple(default)
    names = tuple(sorted({name.strip() for name in text.split(",") if name.strip()}))
    known = set(REPLAY) if option == "--replay" else set(skills())
    unknown = set(names) - known
    if unknown:
        raise SystemExit(f"{option}: unknown skills {sorted(unknown)}; known: {sorted(known)}")
    return names


def settings(args):
    config = {**PROFILES[args.profile], "profile": args.profile, "student": resolve(args.student),
              "modules": sorted(set(args.modules.split(","))) if args.modules else sorted(MODULES),
              "skills": sorted(set(args.skills.split(","))) if args.skills else None,
              "cycle": args.cycle, "budget_seconds": args.budget_minutes * 60 if args.budget_minutes else None,
              "four_bit": args.four_bit, "export": args.export,
              "allow_execution": os.environ.get("AURORA_PROFESSOR_ALLOW_CODE_EXECUTION") == "1",
              "replay": _names(args.replay, REPLAY, "--replay"),
              "self_worked": _names(args.self_worked, SELF_WORKED, "--self-worked")}
    for name in ("diagnostic_per_skill", "gate_per_skill", "curriculum", "epochs", "learning_rate", "rank", "max_tokens",
                 "batch_size", "accumulate", "mine_per_skill", "pool_per_skill", "self_worked_per_skill"):
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
    report = {**_context(config), "kind": "aurora_professor_diagnosis",
              "complete": receipt["complete"] and not notes["source_errors"] and not notes.get("skipped_no_execution"),
              "summary": receipt["summary"], "weak_points": profile(receipt["summary"], catalogue),
              "exam": {"suite_sha256": receipt["suite_sha256"], "results_sha256": receipt["results_sha256"], "notes": notes},
              "blocklist": exam_blocklist(modules=config["modules"], library=library, only=config["skills"])}
    atomic_json(work / "diagnosis.json", report)
    return report


def mining_probes(pool, per_skill, allow_execution=False):
    """Training items the base model is asked before training, spread over the sub-skills of each skill.

    A generated pool is ordered sub-skill by sub-skill: on the first GPU run, probing only its head asked
    40 questions of one sub-skill per family, so the known failures put first in the curriculum all came from it.
    """
    probes = []
    for items in pool.values():
        gradable = [item for item in items if item.get("grader") and (allow_execution or item["grader"]["type"] not in EXECUTING)]
        probes += stratified(gradable, per_skill, "aurora-mine")[0]
    return probes


def adapter_hash(adapter):
    """Hash of an adapter's weight file, the identity used by verdicts, diagnoses and receipts."""
    weights = next((p for p in sorted(Path(adapter).glob("adapter_model.*")) if p.is_file()), None)
    return file_hash(weights) if weights else None


def keep_verified_answers(pool, worked, rows):
    """Replace the pool of each self-worked skill by the student's own answers that the grader verified.

    ``worked`` maps a skill to the training items the student was asked; ``rows`` are the graded
    results. An item is kept only with the student's full answer as its target; a skill without any
    verified answer leaves the pool, because a target without its work is worse than no example.
    """
    notes = {}
    for name, group in worked.items():
        # An answer the token budget cut is not a complete worked answer, even when its grade is correct.
        answers = {row["id"]: row["output"].strip() for row in rows
                   if row["skill"] == name and row.get("status", "graded") == "graded" and row["correct"] and not row.get("cut")
                   and (row["output"] or "").strip()}
        graded = {row["id"] for row in rows if row["skill"] == name}
        verified = [{**item, "target": answers[item["id"]]} for item in group if item["id"] in answers]
        notes[name] = {"asked": len(group), "answered": sum(item["id"] in graded for item in group), "verified": len(verified)}
        if verified:
            pool[name] = verified
        else:
            del pool[name]
    return notes


def train_role(config, work, diagnosis, student=None, library=None, init_adapter=None):
    """Trainer: build a curriculum aimed at the measured weak points and fit an adapter.

    With ``init_adapter`` the cycle continues that adapter. The diagnosis must then describe the
    same adapter (it comes from the examiner's last gate), the probes question the model as it is
    now, and the starting adapter is kept beside the new one so the examiner can compare the two.
    """
    from .train import train
    work = Path(work)
    library = library or Library(row_limit=config["row_limit"])
    student = student or open_student(config)
    if diagnosis["student"]["hf"] != config["student"]["hf"]:
        raise ValueError("This diagnosis describes another student")
    described = (diagnosis.get("basis") or {}).get("adapter_sha256")
    given = adapter_hash(init_adapter) if init_adapter else None
    if not diagnosis.get("complete", True):
        raise ValueError("This diagnosis is incomplete (unfinished exam, missing source or skills not examined): "
                         "its weak points would leave out what it did not measure")
    # Every part of the diagnosis measured on a gate counts, merged parts included.
    measured = [str((diagnosis.get("basis") or {}).get("exam", ""))]
    measured += [str((part.get("measured_on") or {}).get("exam", "")) for part in diagnosis.get("merged_from") or []]
    gates = [int(found.group(1)) for found in (re.fullmatch(r"gate:(\d+)", name) for name in measured) if found]
    if gates and config["cycle"] <= max(gates):
        # Its curriculum was steered by scores on that gate: examining it there again would not be an unseen exam.
        raise ValueError(f"This diagnosis was measured on gate {max(gates)}: the next cycle must use cycle "
                         f">= {max(gates) + 1}, not {config['cycle']}")
    if (init_adapter and not given) or described != given:
        raise ValueError("The diagnosis and the starting adapter do not match: a diagnosis of the base model trains a new "
                         "adapter, and a diagnosis of a trained candidate continues exactly that adapter (--init-adapter)")
    weak = diagnosis["weak_points"]
    # Size each pool for its expected share of the curriculum, so a very weak skill is not capped by the default pool.
    catalogue = skills(config["modules"], config["skills"])
    replay = tuple(config.get("replay", REPLAY))
    self_worked_skills = tuple(config.get("self_worked", SELF_WORKED))
    trainable = [name for name, entry in catalogue.items() if (entry["generator"] or entry["train_sources"]) and name not in REPLAY]
    expected = skill_weights(weak, trainable)
    sizes = {name: int(1.2 * config["curriculum"] * share) + 8 for name, share in expected.items()}
    # The examiner's blocklist, plus the exam families this trainer can rebuild itself from the same pinned public
    # sources: an examiner and a trainer of different code versions must not let an exam question through.
    blocklist = set(diagnosis["blocklist"]) | set(exam_blocklist(modules=config["modules"], library=library))
    exam_sources = {name for entry in skills(config["modules"]).values() for name in entry["exam_sources"]}
    missing = sorted(exam_sources & set(library.errors))
    if missing:
        # A source that failed to load contributes no hash: its exam questions could then reach the corpus.
        raise ValueError("Exam sources could not be loaded, so the trainer cannot exclude their questions: "
                         + "; ".join(f"{name}: {library.errors[name]}" for name in missing))
    pool, pool_notes = build_pool(config["pool_per_skill"], modules=config["modules"], blocklist=blocklist,
                                  library=library, subskill_weights=subskill_weights(weak), only=config["skills"], sizes=sizes,
                                  cycle=config["cycle"])
    train_sources = {name for skill, entry in catalogue.items() for name in entry["train_sources"]}
    lost = sorted(train_sources & set(library.errors))
    if lost:
        # A training source that failed to load would silently remove its skill from the curriculum.
        raise ValueError("Training sources could not be loaded: " + "; ".join(f"{name}: {library.errors[name]}" for name in lost))
    for name in set(REPLAY) - set(replay):              # free-form skills left out of this cycle by an explicit choice
        pool.pop(name, None)
    for name in self_worked_skills:
        if name in pool and not any(item.get("grader") and (config["allow_execution"] or item["grader"]["type"] not in EXECUTING)
                                    for item in pool[name]):
            # Seen on 2026-11-12: MBPP training items carried no tests, so code.python silently left the curriculum.
            raise ValueError(f"{name} is trained on verified answers only, but none of its training items can be graded here"
                             + ("" if config["allow_execution"] else " (its grader runs code: set AURORA_PROFESSOR_ALLOW_CODE_EXECUTION=1)"))
    # Probe the model as it is now on training items it can be graded on: what it fails goes first.
    probes = mining_probes({name: items for name, items in pool.items() if name not in self_worked_skills},
                           config["mine_per_skill"], config["allow_execution"])
    # Self-worked skills: many more questions are asked, and only the answers the grader verifies become targets.
    worked = {name: mining_probes({name: pool[name]}, config["self_worked_per_skill"], config["allow_execution"])
              for name in pool if name in self_worked_skills}
    asked = probes + [item for group in worked.values() for item in group]
    mined, rows = {}, []
    if asked:
        if init_adapter:
            student.attach(init_adapter)
        status({"phase": "mine", "items": len(asked)})
        evaluate(student, asked, work / "mine", batch_size=config["eval_batch"], label="mine", progress=status,
                 budget_seconds=config["budget_seconds"] and config["budget_seconds"] * (0.3 if worked else 0.15))
        rows = [row for row in read_results(work / "mine") if row["status"] == "graded"]
        mined = {row["id"]: bool(row["correct"]) for row in rows}
        student.detach()
    self_worked = keep_verified_answers(pool, worked, rows)
    weights = skill_weights(weak, [name for name in pool if name not in REPLAY])
    chosen, plan = build_curriculum(pool, weights, config["curriculum"], mined=mined, replay_skills=replay)
    atomic_json(work / "curriculum.json", {"kind": "aurora_professor_curriculum", "plan": plan, "weights": weights,
                                           "pool": {**pool_notes, "blocklist": {"from_examiner": len(set(diagnosis["blocklist"])),
                                                                               "total": len(blocklist)}},
                                           "mined": {"probed": len(mined), "failed": sum(not v for v in mined.values())},
                                           "diagnosis_sha256": digest({k: diagnosis[k] for k in ("summary", "exam")}),
                                           "cycle": config["cycle"], "continued_from": given, "self_worked": self_worked,
                                           "realised": {"total": len(chosen), "replay_share": round(sum(item["skill"] in replay for item in chosen)
                                                                                                 / max(1, len(chosen)), 4)},
                                           "choices": {"replay": list(replay), "self_worked": list(self_worked_skills),
                                                       "skills": config["skills"]}})
    status({"phase": "train", "examples": len(chosen)})
    knobs = {k: config[k] for k in ("max_tokens", "batch_size", "accumulate", "epochs", "eval_every", "learning_rate", "rank") if k in config}
    if config["student"].get("attention_only"):
        knobs["attention_only"] = True
    if not init_adapter and (work / "training" / "init_adapter").exists():
        shutil.rmtree(work / "training" / "init_adapter")  # a fresh cycle continues nothing: no leftover may pose as "previous"
    if init_adapter:
        # The examiner compares the new adapter with the one it continues, on the same unseen items. The copy is made
        # BEFORE training: training writes work/training/adapter, which may be the very folder being continued.
        kept = work / "training" / "init_adapter"
        staged = work / "training" / ".init_adapter.tmp"
        if staged.exists():
            shutil.rmtree(staged)
        staged.mkdir(parents=True)
        for path in sorted(Path(init_adapter).glob("adapter_*")):      # configuration and weights, nothing else of that folder
            if path.is_file() and path.suffix in {".json", ".safetensors", ".bin"}:
                shutil.copy2(path, staged / path.name)
        if adapter_hash(staged) != given:
            raise ValueError("The starting adapter changed while it was being copied")
        if kept.exists():
            shutil.rmtree(kept)
        staged.replace(kept)
        init_adapter = kept
    receipt = train(student, chosen, work / "training", config=knobs, progress=status, init_adapter=init_adapter,
                    budget_seconds=config["budget_seconds"] and config["budget_seconds"] * (0.55 if worked else 0.6))
    return receipt


def next_diagnosis(verdict, blocklist):
    """Diagnosis of the trained candidate, read from the gate it just sat: where the next cycle starts.

    Only aggregate scores leave the examiner, as for a first diagnosis. The gate of the next cycle is
    a different slice, so steering the next curriculum with these scores does not touch its exam.
    """
    examined = sorted(verdict["skills"])          # in a verdict, ``skills`` holds the per-skill tables
    catalogue = skills(verdict["modules"], examined)

    def entry(table, module):
        return {"items": table["items"], "correct": table["candidate_correct"], "accuracy": table["candidate_accuracy"],
                "ci95": table["candidate_ci95"], "module": module}
    summary = {"skills": {name: entry(table, catalogue[name]["module"]) for name, table in verdict["skills"].items()},
               "subskills": {key: entry(table, catalogue[key.split(" / ")[0]]["module"]) for key, table in verdict["subskills"].items()}}
    overall = verdict["overall"]
    summary["overall"] = {**entry(overall, None), "macro_accuracy": overall["macro_candidate"],
                          "skipped": verdict["exam"]["items"] - verdict["exam"]["graded_both"]}
    carried = ("schema", "student", "profile", "modules", "cycle", "hardware", "versions", "python", "host", "created_at")
    return {**{key: verdict[key] for key in carried}, "skills": examined,
            "kind": "aurora_professor_diagnosis", "complete": verdict["exam_complete"],
            "basis": {"model": "candidate", "exam": f"gate:{verdict['cycle']}", "adapter_sha256": verdict["adapter_sha256"],
                      "verdict": verdict["verdict"]},
            "summary": summary, "weak_points": profile(summary, catalogue),
            "exam": {"suite_sha256": verdict["exam"]["suite_sha256"], "results_sha256": verdict["exam"]["candidate_receipt"],
                     "notes": verdict["exam"]["notes"]},
            "blocklist": sorted(blocklist)}


def merge_diagnoses(primary, extra):
    """One diagnosis for a cycle that spans modules examined separately (same student, disjoint skills).

    ``primary`` keeps its identity: if it describes a trained candidate, the result still names that
    adapter. Scores taken from ``extra`` are listed in ``merged_from`` with what they were measured on,
    so a curriculum never hides that part of its steering comes from another exam.
    """
    if primary["student"]["hf"] != extra["student"]["hf"]:
        raise ValueError("These diagnoses describe different students")
    overlap = set(primary["summary"]["skills"]) & set(extra["summary"]["skills"])
    if overlap:
        raise ValueError(f"Both diagnoses examine {sorted(overlap)}: nothing to merge for these skills")
    modules = sorted(set(primary["modules"]) | set(extra["modules"]))
    summary = {"skills": {**primary["summary"]["skills"], **extra["summary"]["skills"]},
               "subskills": {**primary["summary"]["subskills"], **extra["summary"]["subskills"]}}
    tables = summary["skills"].values()
    items, correct = sum(t["items"] for t in tables), sum(t["correct"] for t in tables)
    summary["overall"] = {"items": items, "correct": correct, "accuracy": correct / items if items else None,
                          "macro_accuracy": sum(t["accuracy"] for t in tables) / len(summary["skills"]),
                          "skipped": primary["summary"]["overall"].get("skipped", 0) + extra["summary"]["overall"].get("skipped", 0)}
    examined = sorted(summary["skills"])
    return {**primary, "modules": modules, "skills": examined, "complete": bool(primary["complete"] and extra["complete"]),
            "summary": summary, "weak_points": profile(summary, skills(modules, examined)),
            "blocklist": sorted(set(primary["blocklist"]) | set(extra["blocklist"])),
            "merged_from": [{"modules": extra["modules"], "skills": sorted(extra["summary"]["skills"]),
                             "measured_on": (extra.get("basis") or {"model": "base"}), "exam": extra["exam"]}]}


def installable_problems(verdict, config=None):
    """Why a verdict cannot authorise an installation (empty when it can). The installer applies the same rule.

    A continued candidate must also have sat the same items as the adapter it continues, all of them, without
    being worse or regressing on any skill: a cut or missing comparison is not a comparison.
    """
    problems = []
    if verdict.get("verdict") != "promote":
        problems.append(f"verdict « {verdict.get('verdict')} » : seul « promote » autorise une installation")
    if not verdict.get("exam_complete"):
        problems.append("examen incomplet")
    production = (config or {}).get("student", {}).get("production") if config else None
    if production is None:
        from .students import resolve
        try:
            production = resolve(verdict["student"]["tag"])["production"]
        except KeyError:
            production = False
    if not production:
        problems.append("cet élève n'est appelé par aucun module de l'application")
    if (verdict.get("gate") or {}).get("min_items", 0) < GATE["min_items"]:
        problems.append(f"examen de répétition : moins de {GATE['min_items']} items exigés")
    continued = ((verdict.get("training") or {}).get("continued_from") or {}).get("adapter_sha256")
    versus = verdict.get("versus_previous")
    if continued:
        if not versus:
            problems.append("l'adaptateur que ce candidat prolonge n'a pas passé le même examen")
        else:
            if not versus.get("complete"):
                problems.append("la comparaison avec l'adaptateur précédent est incomplète")
            if versus.get("adapter_sha256") != continued:
                problems.append("l'adaptateur comparé n'est pas celui que ce candidat prolonge")
            if versus.get("verdict") == "reject" or versus.get("regressions"):
                problems.append("ce candidat est moins bon que l'adaptateur qu'il prolonge, ou régresse sur une compétence : "
                                "livrer le cycle précédent")
    return problems


def verify(config, work, adapter, student=None, library=None, base_done=False, previous=None):
    """Examiner: paired exam of base and candidate on this cycle's unseen gate.

    ``previous`` is the adapter the candidate continues: it sits the same items, and the verdict says
    whether the continuation is measurably better than what it started from (``versus_previous``).
    """
    work = Path(work)
    library = library or Library(row_limit=config["row_limit"])
    previous = None if base_done else previous
    continued = ((read_json(Path(adapter).parent / "train_receipt.json", {}) or {}).get("continued_from") or {}).get("adapter_sha256")
    if previous and adapter_hash(previous) != continued:
        raise ValueError("The previous adapter given is not the one this candidate continues (train receipt): "
                         f"{adapter_hash(previous)} != {continued}")
    items, notes = _exam(config, "gate", library)
    gate = work / f"gate_{config['cycle']}"
    share = config["budget_seconds"] and config["budget_seconds"] * 0.9 / (3 if previous else 2)
    if not base_done:
        student = student or open_student(config)
        status({"phase": "gate_base", "items": len(items)})
        evaluate(student, items, gate / "base", batch_size=config["eval_batch"], label="gate_base", progress=status,
                 budget_seconds=share)
        if previous:
            student.attach(previous)
            status({"phase": "gate_previous", "items": len(items)})
            evaluate(student, items, gate / "previous", batch_size=config["eval_batch"], label="gate_previous", progress=status,
                     budget_seconds=share)
            student.detach()
        student.attach(adapter)
    status({"phase": "gate_candidate", "items": len(items)})
    evaluate(student, items, gate / "candidate", batch_size=config["eval_batch"], label="gate_candidate", progress=status,
             budget_seconds=share)
    base_rows, candidate_rows = read_results(gate / "base"), read_results(gate / "candidate")
    common = {r["id"] for r in base_rows if r["status"] == "graded"} & {r["id"] for r in candidate_rows if r["status"] == "graded"}
    # Complete means both models met every item; a prompt over the context budget is skipped for both alike.
    wanted = {item["id"] for item in items}
    finished = {r["id"] for r in base_rows} == {r["id"] for r in candidate_rows} == wanted
    # A source that failed to load changes the gate's composition and the positions of later slices.
    # A skill left out because generated code may not run here is not examined at all: the exam is not complete.
    skipped = notes.get("skipped_no_execution") or []
    complete = finished and not notes["source_errors"] and not skipped
    result = compare([r for r in base_rows if r["id"] in common], [r for r in candidate_rows if r["id"] in common],
                     gate={"min_items": config["min_items"]})
    if not complete and result["verdict"] == "promote":
        result["verdict"] = "inconclusive"
        result["reasons"].insert(0, "the gate exam was not finished for both models" if not finished else
                                 "exam sources failed to load: " + ", ".join(sorted(notes["source_errors"])) if notes["source_errors"] else
                                 "skills not examined without code execution: " + ", ".join(skipped))
    versus = None
    if previous:
        previous_rows = read_results(gate / "previous")
        shared = common & {r["id"] for r in previous_rows if r["status"] == "graded"}
        against = compare([r for r in previous_rows if r["id"] in shared], [r for r in candidate_rows if r["id"] in shared],
                          gate={"min_items": config["min_items"]})
        versus = {"adapter_sha256": adapter_hash(previous), "complete": complete and {r["id"] for r in previous_rows} == wanted,
                  **{key: against[key] for key in ("verdict", "reasons", "overall", "skills", "regressions")}}
    adapter = Path(adapter)
    training = read_json(adapter.parent / "train_receipt.json", {})
    verdict = {**_context(config), "kind": "aurora_professor_verdict", **result, "exam_complete": complete,
               "exam": {"items": len(items), "graded_both": len(common), "notes": notes,
                        "base_receipt": read_json(gate / "base" / "exam_receipt.json", {}).get("results_sha256"),
                        "candidate_receipt": read_json(gate / "candidate" / "exam_receipt.json", {}).get("results_sha256"),
                        "suite_sha256": read_json(gate / "base" / "exam_receipt.json", {}).get("suite_sha256")},
               "adapter_sha256": adapter_hash(adapter),
               # Present only when the candidate continues an earlier adapter: the same items, previous against candidate.
               "versus_previous": versus,
               "training": {k: training.get(k) for k in ("steps", "stopped", "selected_step", "initial_dev_loss",
                                                         "selected_dev_loss", "examples", "data_sha256", "trainable_parameters",
                                                         "continued_from")},
               "promotable": False}
    verdict["not_installable"] = installable_problems(verdict, config)
    verdict["promotable"] = not verdict["not_installable"]
    atomic_json(work / f"verdict_{config['cycle']}.json", verdict)
    # Where the candidate is still weak: the starting point of the next cycle, as aggregate scores only.
    atomic_json(work / f"diagnosis_next_{config['cycle']}.json",
                next_diagnosis(verdict, exam_blocklist(modules=config["modules"], library=library, only=config["skills"])))
    wanted = config.get("export", "promote")
    if wanted == "always" or (wanted == "promote" and verdict["promotable"]):
        # Files Ollama can load. A failed conversion is recorded in the receipt and never changes the verdict.
        from .export import export
        status({"phase": "export"})
        try:
            from huggingface_hub import snapshot_download
            # The examiner has just loaded these weights: the full snapshot is in its cache, at the pinned revision.
            snapshot = snapshot_download(config["student"]["hf"], revision=config["student"].get("revision"),
                                         token=os.environ.get("HF_TOKEN") or None)
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
    parser.add_argument("role", choices=("probe", "diagnose", "train", "verify", "cycle", "rediagnose", "merge"))
    parser.add_argument("--student", default="qwen3:0.6b", help="Ollama tag or Hugging Face id listed in students.py")
    parser.add_argument("--profile", choices=sorted(PROFILES), default="standard")
    parser.add_argument("--modules", help="Comma-separated subset of: " + ", ".join(sorted(MODULES)))
    parser.add_argument("--skills", help="Comma-separated skill names for a targeted cycle (default: every skill of the modules)")
    parser.add_argument("--work", type=Path)
    parser.add_argument("--cycle", type=int, default=0, help="Selects a fresh, disjoint gate exam")
    parser.add_argument("--diagnosis", type=Path)
    parser.add_argument("--adapter", type=Path)
    parser.add_argument("--extra-diagnosis", type=Path, help="merge: diagnosis of other modules of the same student, added to --diagnosis")
    parser.add_argument("--replay", help="train: free-form skills kept as replay (comma-separated; empty for none; default: "
                                         + ",".join(REPLAY) + ")")
    parser.add_argument("--self-worked", help="train: skills trained only on the student's own verified answers (default: "
                                              + ",".join(SELF_WORKED) + ")")
    parser.add_argument("--init-adapter", type=Path, help="train: continue this adapter (needs the examiner's diagnosis_next file)")
    parser.add_argument("--previous-adapter", type=Path, help="verify: the adapter the candidate continues, examined on the same items")
    parser.add_argument("--budget-minutes", type=float)
    parser.add_argument("--four-bit", action=argparse.BooleanOptionalAction, default=None)
    parser.add_argument("--export", choices=("promote", "always", "never"), default="promote",
                        help="Convert the adapter to GGUF after verification (default: only when promotable)")
    for name, kind in (("diagnostic_per_skill", int), ("gate_per_skill", int), ("curriculum", int), ("epochs", float),
                       ("learning_rate", float), ("rank", int), ("max_tokens", int), ("batch_size", int), ("accumulate", int),
                       ("mine_per_skill", int), ("pool_per_skill", int), ("self_worked_per_skill", int)):
        parser.add_argument("--" + name.replace("_", "-"), type=kind)
    args = parser.parse_args(argv)
    if args.role == "probe":
        print(json.dumps({"hardware": hardware(), "versions": library_versions()}, indent=2))
        return 0
    if args.work is None:
        parser.error("--work is required")
    config = settings(args)
    args.work.mkdir(parents=True, exist_ok=True)
    if args.role == "merge":
        if not args.diagnosis or not args.extra_diagnosis:
            parser.error("merge requires --diagnosis and --extra-diagnosis")
        result = merge_diagnoses(json.loads(args.diagnosis.read_text(encoding="utf-8")),
                                 json.loads(args.extra_diagnosis.read_text(encoding="utf-8")))
        atomic_json(args.work / "diagnosis_merged.json", result)
        summary = {"modules": result["modules"], "weakest": [(w["skill"], round(w["accuracy"], 3)) for w in result["weak_points"][:8]]}
    elif args.role == "rediagnose":
        # Rebuild the candidate's diagnosis from a verdict already written (no model is loaded).
        verdict = read_json(args.work / f"verdict_{config['cycle']}.json", None)
        if not verdict or verdict.get("kind") != "aurora_professor_verdict":
            parser.error(f"no verdict_{config['cycle']}.json in --work")
        if args.diagnosis:
            blocklist = json.loads(args.diagnosis.read_text(encoding="utf-8"))["blocklist"]
        else:
            blocklist = exam_blocklist(modules=verdict["modules"], library=Library(row_limit=config["row_limit"]), only=verdict["skills"])
        result = next_diagnosis(verdict, blocklist)
        atomic_json(args.work / f"diagnosis_next_{config['cycle']}.json", result)
        summary = {"basis": result["basis"], "weakest": [(w["skill"], round(w["accuracy"], 3)) for w in result["weak_points"][:8]]}
    elif args.role == "diagnose":
        result = diagnose(config, args.work)
        summary = {"complete": result["complete"], "macro_accuracy": result["summary"]["overall"]["macro_accuracy"],
                   "weakest": [(w["skill"], round(w["accuracy"], 3)) for w in result["weak_points"][:8]]}
    elif args.role == "train":
        if args.diagnosis is None:
            parser.error("train requires --diagnosis from the examiner")
        receipt = train_role(config, args.work, json.loads(args.diagnosis.read_text(encoding="utf-8")),
                             init_adapter=args.init_adapter)
        summary = {k: receipt[k] for k in ("steps", "stopped", "initial_dev_loss", "selected_dev_loss", "elapsed_seconds")}
    elif args.role == "verify":
        if args.adapter is None:
            parser.error("verify requires --adapter")
        result = verify(config, args.work, args.adapter, previous=args.previous_adapter)
        summary = {"verdict": result["verdict"], "reasons": result["reasons"], "overall": result["overall"], "promotable": result["promotable"]}
    else:
        result = cycle(config, args.work)
        summary = {"verdict": result["verdict"], "reasons": result["reasons"], "overall": result["overall"], "promotable": result["promotable"]}
    print("AURORA_RESULT " + json.dumps(summary, ensure_ascii=False), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
