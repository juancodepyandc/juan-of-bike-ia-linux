"""Professor autopilot: keeps improving the local models the application calls, one verified cycle at a time.

It runs on the PC, where the Kaggle credential and Ollama live. Each ``tick`` advances the loop by one step
and returns; ``run`` calls it every few minutes, and a restart (bridge, PC, update) resumes from the state
file. Kaggle holds both machines of the professor: each cycle has its own trainer kernel and a separate
examiner kernel. Colab has no launch API and stays a manual option (the notebooks).

A cycle continues the best installable adapter of a student on fresh exercises aimed at its measured weak
points; the examiner grades the base, that adapter and the new one on the same unseen gate, which covers
every module of the tag. A verdict is delivered only if ``installable_problems`` finds nothing, and the
installer activates it only if it wins the same paired exam again as served by Ollama. Otherwise the model
in use stays. Nothing here weakens a gate: the autopilot only chains the steps the command line offers.

    python -m auto_rl.professor.autopilot status
    python -m auto_rl.professor.autopilot run [--no-activate] [--students qwen2.5:7b,qwen2.5-coder:7b]
    python -m auto_rl.professor.autopilot stop
    python -m auto_rl.professor.autopilot resume --student qwen2.5:7b      # after a pause
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import time
from pathlib import Path

from .install import STATE
from .records import atomic_json, read_json

AUTOPILOT = STATE / "autopilot"
STATE_FILE = AUTOPILOT / "state.json"
STOP_FILE = AUTOPILOT / "STOP"
LOG_FILE = AUTOPILOT / "runner.log"
SCHEMA = 1

#: Production students that fit two T4s, in the order they take turns.
STUDENTS = ("qwen2.5:7b", "qwen2.5-coder:7b")

#: What each student trains and how, from the measured cycles of 11-12 November 2026 (master document, 1.36).
POLICY = {
    "qwen2.5:7b": {
        # Skills whose training moved the gate (format instructions, prompt direction, Cowork in cycle 4), with the
        # sentiment labels kept as a floor. French free-form answers coincided with the sentiment regression of
        # cycle 2; translation and knowledge did not move after a thousand examples each.
        "skills": ("business.sentiment", "conversation.format_fr", "cowork.extract_fields", "cowork.extract_qa_fr",
                   "cowork.json_schema", "cowork.tool_call", "media.prompt_spec", "media.prompt_translate"),
        "overrides": {"replay": "business.advice", "curriculum": "2600", "epochs": "1.3"},
        "gate_per_skill": 120,
    },
    "qwen2.5-coder:7b": {
        # Python and SQL on the student's own verified answers; code.trace gained 1.3 points for 800 examples,
        # and training grounded reports coincided with the evidence regression of cycle 1.
        "skills": ("code.python", "code.sql", "mission.action", "mission.evidence", "mission.pointer"),
        "overrides": {"replay": "", "self_worked": "code.python,code.sql", "curriculum": "3000", "epochs": "1.3"},
        "gate_per_skill": 100,
    },
}

#: GPU seconds a step may use, with a margin over the real runs (trainers 65-90 min, three-model exams
#: 87-165 min, diagnoses 10-20 min).
NEEDS = {"diagnose": 2700, "train": 7200, "verify": 16200}
BUDGET_MINUTES = {"diagnose": 60, "train": 150, "verify": 330}
TICK_SECONDS = 300
#: A runner that has not written its heartbeat for this long is considered gone (longer while it installs).
STALE_SECONDS, BUSY_STALE_SECONDS = 900, 6 * 3600
#: Consecutive cycles without an installable verdict, or failed kernels, before a student pauses.
STALL_AFTER = 2
#: Delay before trying again to reach Ollama or install.
RETRY_SECONDS = 1800
EVENTS_KEPT = 200
RUNNING = {"queued", "running"}
IN_FLIGHT = {"diagnosing": "diagnose", "training": "train", "examining": "verify"}


def slug(student):
    return re.sub(r"[^a-z0-9]+", "-", student.lower()).strip("-")


# -- state ------------------------------------------------------------------------------------------------
def load():
    state = read_json(STATE_FILE, None) or {}
    state.setdefault("schema", SCHEMA)
    state.setdefault("enabled", False)
    state.setdefault("activate", True)
    state.setdefault("students", {})
    state.setdefault("order", list(STUDENTS))
    state.setdefault("turn", 0)
    state.setdefault("events", [])
    return state


def save(state):
    state["updated_at"] = time.time()
    atomic_json(STATE_FILE, state)


def note(state, student, message, **data):
    """Event shown by the interface (French, like the rest of the user-facing text)."""
    state["events"].append({"at": time.time(), "student": student, "message": message, **data})
    del state["events"][:-EVENTS_KEPT]


def track(state, student):
    """One student's pipeline. ``phase`` is where its kernels are; ``deliveries`` what waits for the PC."""
    return state["students"].setdefault(student, {
        "phase": "new", "cycle": None, "next_cycle": 0, "best_cycle": None, "installed_cycle": None,
        "kernel": None, "launched_at": None, "modules": None, "resume_phase": None, "until": None, "why": None,
        "deliveries": [], "deliver_after": None, "rejected_in_a_row": 0, "failures_in_a_row": 0, "history": []})


def runner_alive(state, now=None):
    runner = state.get("runner") or {}
    if not runner.get("heartbeat"):
        return False
    limit = BUSY_STALE_SECONDS if runner.get("busy") else STALE_SECONDS
    return (now or time.time()) - runner["heartbeat"] < limit


# -- the outside world (tests replace these two objects) ---------------------------------------------------
class Kaggle:
    """Kaggle calls the autopilot makes, through the launcher of the professor."""

    def __init__(self):
        from . import kaggle_runner
        self.runner = kaggle_runner

    def owner(self):
        return self.runner.whoami()

    def quota(self):
        from datetime import timezone
        view = self.runner._api().quota_view()
        gpu = view.gpu_quota
        remaining = max(0.0, (gpu.total_time_allowed - gpu.time_used - gpu.time_reserved).total_seconds())
        refresh = getattr(view, "quota_refresh_time", None)
        if hasattr(refresh, "timestamp") and refresh.tzinfo is None:
            refresh = refresh.replace(tzinfo=timezone.utc)      # Kaggle states the renewal in UTC (2026-11-14 00:00:00)
        return {"remaining_seconds": remaining, "refresh_at": refresh.timestamp() if hasattr(refresh, "timestamp") else None}

    def reference(self, owner, role, student, cycle):
        return f"{owner}/{self.runner.kernel_name(role, student, cycle)[0]}"

    def cycles(self, owner, student):
        """Cycles that have a kernel, per role, from one listing of the account's kernels."""
        slugs, page = set(), 1
        while page <= 10:
            listed = self.runner._api().kernels_list(user=owner, search="aurora-professeur", page_size=100, page=page) or []
            slugs |= {str(getattr(item, "ref", "")).split("/")[-1] for item in listed}
            if len(listed) < 100:
                break
            page += 1
        found = {}
        for role in ("train", "verify"):
            base = self.runner.kernel_name(role, student, 0)[0]
            found[role] = {0 if name == base else int(name[len(base) + 2:]) for name in slugs
                           if name == base or (name.startswith(base + "-c") and name[len(base) + 2:].isdigit())}
        return found

    def status(self, reference):
        return self.runner.state(reference)["status"]

    def verdict(self, reference, folder):
        """Only the verdict file of an examiner output (its latest run may also be a diagnosis)."""
        folder = Path(folder)
        if folder.exists():
            shutil.rmtree(folder)
        folder.mkdir(parents=True)
        self.runner._api().kernels_output(reference, path=str(folder), file_pattern=r".*verdict_\d+\.json", force=True, quiet=True)
        found = sorted(folder.rglob("verdict_*.json"))
        return json.loads(found[-1].read_text(encoding="utf-8")) if found else None

    def curriculum(self, reference, folder):
        """Only the curriculum of a trainer output: what it really trained, skill by skill."""
        folder = Path(folder)
        if folder.exists():
            shutil.rmtree(folder)
        folder.mkdir(parents=True)
        self.runner._api().kernels_output(reference, path=str(folder), file_pattern=r".*curriculum\.json", force=True, quiet=True)
        found = sorted(folder.rglob("curriculum.json"))
        return json.loads(found[-1].read_text(encoding="utf-8")) if found else None

    def trained_modules(self, reference, folder):
        """Modules a finished trainer really trained, from its curriculum (the exam must cover them too)."""
        from .suites import skills as catalogue
        planned = ((self.curriculum(reference, folder) or {}).get("plan") or {}).get("skills") or {}
        known = catalogue()
        return sorted({known[name]["module"] for name in planned if name in known})

    def fetch(self, reference, folder):
        """The whole output, checked file by file against the manifest the kernel wrote."""
        folder = Path(folder)
        if folder.exists():
            shutil.rmtree(folder)
        return self.runner.fetch(reference, folder)

    def publish(self, owner, training, student, extra, note):
        return self.runner.publish_adapter(owner, training, student=student, extra=extra, note=note)

    def launch(self, folder, owner, role, student, **options):
        metadata = self.runner.write_kernel(folder, owner, role, student=student, **options)
        self.runner.launch(folder, timeout_seconds=options["budget_minutes"] * 60 + 1500)
        return metadata["id"]


class Installer:
    """The PC side: the installer of the professor and its exam through Ollama."""

    def __init__(self, url):
        self.url = url

    def check_ollama(self):
        from .install import installed_tags
        installed_tags(self.url)

    def installed_cycles(self, student):
        """Installed reinforced cycles of a tag, each with whether it is the active one."""
        from .install import _state, full_tag
        entry = _state().get(full_tag(student)) or {}
        found = {}
        for name in entry.get("candidates") or {}:
            match = re.search(r"-aurora-renforce-c(\d+)$", name)
            if match:
                found[int(match.group(1))] = name == entry.get("active")
        return found

    def install(self, folder):
        from .install import install
        return install(folder, url=self.url, per_skill=60)

    def activate(self, tag, candidate):
        from .install import activate
        return activate(tag, url=self.url, candidate=candidate)


# -- planning -----------------------------------------------------------------------------------------------
def served(student):
    from .students import resolve
    return list(resolve(student).get("modules") or [])


def plan(student, diagnosis=None, exclude=()):
    """Modules and skills of a cycle: the served modules, plus those the previous cycle trained.

    ``exclude`` are skills the analysis of the last two exams found stuck (trained, below 85 %, not moving).
    """
    from .suites import skills as catalogue
    policy = POLICY.get(student, {})
    modules = sorted(set(served(student)) | set((diagnosis or {}).get("trained_modules") or []))
    known = catalogue(modules)
    wanted = [name for name in policy.get("skills", ()) if name in known and name not in set(exclude)]
    return {"modules": modules, "skills": wanted or None, "overrides": dict(policy.get("overrides", {})),
            "gate_per_skill": policy.get("gate_per_skill", 120)}


def _folder(student, cycle, name):
    return AUTOPILOT / slug(student) / f"c{cycle}" / name


def _wait_for_quota(state, student, entry, kaggle, step, now, resume_phase):
    """True when the weekly GPU quota covers ``step``; otherwise the pipeline waits for the renewal."""
    quota = kaggle.quota()
    state["quota"] = {**quota, "read_at": now}
    if quota["remaining_seconds"] >= NEEDS[step]:
        return False
    until = quota.get("refresh_at") or now + 24 * 3600
    if until <= now:                                    # renewal announced but not visible yet: ask again in an hour
        until = now + 3600
    entry.update(phase="waiting_quota", resume_phase=resume_phase, until=until, why=step)
    note(state, student, f"quota Kaggle insuffisant pour « {step} » ({int(quota['remaining_seconds'])} s sur {NEEDS[step]} s "
                         "nécessaires) : reprise après son renouvellement")
    return True


def rebuild_diagnosis(source, cycle, path):
    """The candidate's diagnosis an examiner older than ``diagnosis_next`` did not write, rebuilt from its verdict.

    Same function and blocklist as the examiner (``run.next_diagnosis`` over the exam families it graded): only
    aggregate scores, and the next cycle still needs a later gate than the one these scores come from.
    """
    from .run import next_diagnosis
    from .suites import Library, exam_blocklist
    found = sorted(Path(source).rglob(f"verdict_{cycle}.json"))
    if not found:
        raise ValueError(f"no verdict_{cycle}.json to rebuild the diagnosis from")
    verdict = json.loads(found[-1].read_text(encoding="utf-8"))
    from .suites import skills as catalogue
    known = catalogue()
    modules = sorted(verdict.get("modules") or {known[name]["module"] for name in verdict["skills"] if name in known})
    blocklist = exam_blocklist(modules=modules, library=Library(), only=sorted(verdict["skills"]))
    atomic_json(path, next_diagnosis(verdict, blocklist))
    return path


def stall(state, student, entry, why):
    entry.update(phase="stalled", why=why, kernel=None)
    note(state, student, f"en pause : {why} ; « reprendre » relance ce modèle")
    return "stalled"


# -- steps --------------------------------------------------------------------------------------------------
def discover(state, student, entry, kaggle, installer):
    """Read what already exists on Kaggle and on the PC: the latest cycle, the best installable one, a kernel in flight."""
    from .run import installable_problems
    owner = state["owner"]
    cycles = kaggle.cycles(owner, student)
    latest = max(cycles["train"] | cycles["verify"], default=None)
    best = None
    for cycle in sorted(cycles["verify"], reverse=True):
        verdict = kaggle.verdict(kaggle.reference(owner, "verify", student, cycle), _folder(student, cycle, "verdict"))
        if verdict and verdict.get("cycle") == cycle and not installable_problems(verdict):
            best = cycle
            break
    entry.update(phase="ready", cycle=latest, best_cycle=best, kernel=None,
                 next_cycle=0 if latest is None else latest + 1)
    if latest is not None:
        role = "verify" if latest in cycles["verify"] else "train"
        reference = kaggle.reference(owner, role, student, latest)
        status = kaggle.status(reference)
        if status in RUNNING:
            entry.update(phase="examining" if role == "verify" else "training", kernel=reference, launched_at=time.time())
        elif role == "train" and status == "complete":
            entry.update(phase="trained", modules=kaggle.trained_modules(reference, _folder(student, latest, "curriculum")))
        elif role == "train":
            entry["next_cycle"] = latest                 # a failed trainer: the same cycle is tried again
        elif status != "complete":
            entry["phase"] = "trained"                   # a failed exam is sat again, it is not a rejection
        elif latest != best:
            entry["rejected_in_a_row"] = 1               # its verdict was read above and does not allow an installation
    installed = installer.installed_cycles(student)
    entry["installed_cycle"] = max((cycle for cycle, active in installed.items() if active), default=None)
    if best is not None and best not in installed:
        entry["deliveries"] = [best]
    note(state, student, f"état retrouvé : dernier cycle {latest}, meilleur cycle installable {best}, "
                         f"cycles installés sur ce PC {sorted(installed) or 'aucun'}")
    return "discovered"


def start_cycle(state, student, entry, kaggle, now):
    """Publish the best adapter with its diagnosis and launch the trainer of the next cycle."""
    owner = state["owner"]
    best, cycle = entry["best_cycle"], entry["next_cycle"]
    if best is None:
        # No adapter to continue: measure the base model first, then train a new adapter on that diagnosis.
        if _wait_for_quota(state, student, entry, kaggle, "diagnose", now, "ready"):
            return "waiting_quota"
        options = plan(student)
        reference = kaggle.launch(_folder(student, cycle, "diagnose_kernel"), owner, "diagnose", student,
                                  modules=",".join(options["modules"]), cycle=cycle, budget_minutes=BUDGET_MINUTES["diagnose"])
        entry.update(phase="diagnosing", cycle=cycle, kernel=reference, launched_at=now, modules=options["modules"])
        note(state, student, f"cycle {cycle} : diagnostic du modèle de base lancé ({reference})")
        return "launched"
    if _wait_for_quota(state, student, entry, kaggle, "train", now, "ready"):
        return "waiting_quota"
    source = _folder(student, best, "kernel")
    if not (source / "aurora_professor_manifest.json").is_file():
        kaggle.fetch(kaggle.reference(owner, "verify", student, best), source)
    diagnosis_path = source / "aurora_professor" / f"diagnosis_next_{best}.json"
    training = source / "aurora_professor" / "training"
    if not (training / "adapter").is_dir():
        return stall(state, student, entry, f"la sortie de l'examinateur du cycle {best} n'a pas d'adaptateur à prolonger")
    if not diagnosis_path.is_file():
        rebuild_diagnosis(source, best, diagnosis_path)
    excluded = (entry.get("advice") or {}).get("exclude") or []
    options = plan(student, json.loads(diagnosis_path.read_text(encoding="utf-8")), exclude=excluded)
    if excluded:
        note(state, student, f"cycle {cycle} : retirés de l'entraînement car bloqués deux cycles de suite : {', '.join(excluded)}")
    dataset = kaggle.publish(owner, training, student, [diagnosis_path], f"cycle {cycle} {student}")
    reference = kaggle.launch(_folder(student, cycle, "train_kernel"), owner, "train", student, modules=",".join(options["modules"]),
                              skills=",".join(options["skills"]) if options["skills"] else None, cycle=cycle,
                              budget_minutes=BUDGET_MINUTES["train"], overrides=options["overrides"], continue_adapter=True,
                              dataset_sources=[dataset])
    entry.update(phase="training", cycle=cycle, kernel=reference, launched_at=now, modules=options["modules"])
    note(state, student, f"cycle {cycle} : entraînement lancé, il prolonge le cycle {best} ({reference})")
    return "launched"


def start_fresh_training(state, student, entry, kaggle, now):
    """After a base diagnosis: train a new adapter from the base model on it."""
    owner, cycle = state["owner"], entry["cycle"]
    if _wait_for_quota(state, student, entry, kaggle, "train", now, "diagnosed"):
        return "waiting_quota"
    found = sorted(_folder(student, cycle, "diagnosis").rglob("diagnosis.json"))
    if not found:
        return stall(state, student, entry, f"le diagnostic du cycle {cycle} n'a pas été retrouvé")
    options = plan(student, json.loads(found[0].read_text(encoding="utf-8")))
    reference = kaggle.launch(_folder(student, cycle, "train_kernel"), owner, "train", student, modules=",".join(options["modules"]),
                              skills=",".join(options["skills"]) if options["skills"] else None, cycle=cycle,
                              budget_minutes=BUDGET_MINUTES["train"], overrides=options["overrides"], diagnosis=found[0])
    entry.update(phase="training", kernel=reference, launched_at=now, modules=options["modules"])
    note(state, student, f"cycle {cycle} : entraînement d'un nouvel adaptateur lancé ({reference})")
    return "launched"


def start_exam(state, student, entry, kaggle, now):
    owner, cycle = state["owner"], entry["cycle"]
    if _wait_for_quota(state, student, entry, kaggle, "verify", now, "trained"):
        return "waiting_quota"
    options = plan(student)
    modules = sorted(set(entry.get("modules") or []) | set(options["modules"]))
    reference = kaggle.launch(_folder(student, cycle, "verify_kernel"), owner, "verify", student, modules=",".join(modules),
                              cycle=cycle, budget_minutes=BUDGET_MINUTES["verify"],
                              overrides={"gate_per_skill": str(options["gate_per_skill"])})
    entry.update(phase="examining", kernel=reference, launched_at=now, modules=modules)
    note(state, student, f"cycle {cycle} : examen lancé, base, cycle précédent et candidat sur la même tranche inédite ({reference})")
    return "launched"


def conclude(state, student, entry, kaggle):
    """Read the verdict of a finished exam: it decides the next starting point and what the PC may install."""
    from .run import installable_problems
    cycle = entry["cycle"]
    folder = _folder(student, cycle, "kernel")
    kaggle.fetch(entry["kernel"], folder)
    found = sorted(folder.rglob("verdict_*.json"))
    verdict = json.loads(found[-1].read_text(encoding="utf-8")) if found else None
    problems = installable_problems(verdict) if verdict else ["aucun verdict dans la sortie de l'examinateur"]
    overall = (verdict or {}).get("overall") or {}
    entry["history"].append({"cycle": cycle, "at": time.time(), "verdict": (verdict or {}).get("verdict"), "problems": problems,
                             "macro_gain": overall.get("macro_gain"), "macro_gain_ci": overall.get("macro_gain_ci"),
                             "versus_previous": ((verdict or {}).get("versus_previous") or {}).get("verdict")})
    entry.update(phase="ready", kernel=None, next_cycle=cycle + 1)
    understand(state, student, entry, kaggle, folder, cycle)
    if problems:
        entry["rejected_in_a_row"] += 1
        note(state, student, f"cycle {cycle} : non installable, le modèle en place reste ({'; '.join(problems)[:300]})")
        if entry["rejected_in_a_row"] >= STALL_AFTER:
            return stall(state, student, entry, f"{entry['rejected_in_a_row']} cycles de suite sans amélioration vérifiée")
        return "rejected"
    entry.update(best_cycle=cycle, rejected_in_a_row=0)
    entry["deliveries"] = [cycle]                     # a newer verified cycle replaces any older one waiting
    note(state, student, f"cycle {cycle} : verdict installable (gain macro {overall.get('macro_gain', 0) * 100:+.1f} points) ; "
                         "le prochain cycle le prolongera")
    return "concluded"


def understand(state, student, entry, kaggle, folder, cycle):
    """Analyse the finished exam beyond its verdict and keep the advice for the next cycle (skills only).

    A failed analysis (a source that does not load on the PC, for example) is reported and never blocks the loop.
    """
    from . import analysis
    try:
        curriculum = kaggle.curriculum(kaggle.reference(state["owner"], "train", student, cycle), _folder(student, cycle, "curriculum"))
        report = analysis.analyse(folder, curriculum=curriculum)
    except Exception as exc:
        note(state, student, f"cycle {cycle} : analyse des résultats impossible ({type(exc).__name__}: {str(exc)[:200]})")
        return None
    atomic_json(_folder(student, cycle, "analysis.json"), report)
    compact = {"cycle": cycle, "side_effects": report["side_effects"],
               "skills": {name: {key: value for key, value in skill.items() if key in ("base", "previous", "candidate", "flags", "trained_examples")}
                          for name, skill in report["skills"].items()}}
    entry["analyses"] = (entry.get("analyses") or [])[-3:] + [compact]
    entry["advice"] = analysis.recommend(entry["analyses"])
    for line in analysis.summary_lines(report, entry["advice"])[:12]:
        note(state, student, f"cycle {cycle} : {line}")
    return report


def follow(state, student, entry, kaggle, now):
    status = kaggle.status(entry["kernel"])
    if status in RUNNING:
        return "running"
    role, cycle = IN_FLIGHT[entry["phase"]], entry["cycle"]
    if status != "complete":
        entry["failures_in_a_row"] += 1
        note(state, student, f"cycle {cycle} : le kernel {entry['kernel']} s'est terminé en « {status} »")
        entry.update(phase={"diagnose": "ready", "train": "ready", "verify": "trained"}[role], kernel=None)
        if role in ("diagnose", "train"):
            entry["next_cycle"] = cycle                  # the same, still unseen, cycle is tried again
        if entry["failures_in_a_row"] >= STALL_AFTER:
            return stall(state, student, entry, f"{entry['failures_in_a_row']} kernels de suite ont échoué")
        return "failed"
    entry["failures_in_a_row"] = 0
    if role == "diagnose":
        kaggle.fetch(entry["kernel"], _folder(student, cycle, "diagnosis"))
        entry.update(phase="diagnosed", kernel=None)
        note(state, student, f"cycle {cycle} : diagnostic terminé")
        return "advanced"
    if role == "train":
        entry.update(phase="trained", kernel=None)
        note(state, student, f"cycle {cycle} : entraînement terminé")
        return "advanced"
    return conclude(state, student, entry, kaggle)


def deliver(state, student, entry, kaggle, installer, now):
    """Install the newest verified cycle on the PC; activate it only if it wins the exam as served by Ollama."""
    from .install import full_tag
    cycle = entry["deliveries"][-1]
    try:
        installer.check_ollama()
    except Exception as exc:
        entry.update(deliver_after=now + RETRY_SECONDS, why=f"Ollama injoignable : {type(exc).__name__}: {str(exc)[:160]}")
        note(state, student, f"cycle {cycle} : Ollama injoignable, livraison reportée")
        return "waiting_ollama"
    folder = _folder(student, cycle, "kernel")
    if not (folder / "aurora_professor_manifest.json").is_file():
        kaggle.fetch(kaggle.reference(state["owner"], "verify", student, cycle), folder)
    runner = state.setdefault("runner", {})
    runner["busy"] = f"{student} : examen du cycle {cycle} tel que servi par Ollama"
    save(state)
    try:
        installed = installer.install(folder)
    except Exception as exc:
        entry.update(deliver_after=now + RETRY_SECONDS, why=f"installation : {type(exc).__name__}: {str(exc)[:200]}")
        note(state, student, f"cycle {cycle} : installation impossible ({type(exc).__name__}: {str(exc)[:200]})")
        return "waiting_ollama"
    finally:
        runner["busy"] = None
    deployment = (installed.get("deployment") or {}).get("verdict")
    activated = deployment == "promote" and state.get("activate", True)
    if activated:
        installer.activate(full_tag(student), installed["candidate_tag"])
        entry["installed_cycle"] = cycle
    entry["history"].append({"cycle": cycle, "at": time.time(), "installed": True, "activated": activated,
                             "deployment": deployment, "candidate_tag": installed.get("candidate_tag")})
    entry.update(deliveries=[], deliver_after=None, why=None)
    if activated:
        note(state, student, f"cycle {cycle} : installé, examen tel que servi gagné, {full_tag(student)} sert désormais le modèle renforcé")
    else:
        note(state, student, f"cycle {cycle} : installé à côté du modèle en place, non activé (examen tel que servi : {deployment})")
    return "delivered"


def tick(state, kaggle, installer, *, now=None):
    """Advance the loop by one step. Returns what happened, for the log and the tests."""
    now = now or time.time()
    if not state.get("enabled"):
        return "disabled"
    if not state.get("owner"):
        state["owner"] = kaggle.owner()
    order = list(state.get("order") or STUDENTS)
    entries = {name: track(state, name) for name in order}
    for name, entry in entries.items():               # first sight of a student: read what exists
        if entry["phase"] == "new":
            return discover(state, name, entry, kaggle, installer)
    for name, entry in entries.items():               # what the PC can install now may change the model in use
        if entry["deliveries"] and now >= (entry.get("deliver_after") or 0):
            return deliver(state, name, entry, kaggle, installer, now)
    for name, entry in entries.items():               # one kernel at a time: the weekly quota is shared
        if entry["phase"] in IN_FLIGHT:
            return follow(state, name, entry, kaggle, now)
    for offset in range(len(order)):
        name = order[(state.get("turn", 0) + offset) % len(order)]
        entry = entries[name]
        if entry["phase"] == "stalled" or (entry["phase"] == "waiting_quota" and now < (entry.get("until") or 0)):
            continue
        if entry["phase"] == "waiting_quota":
            entry["phase"] = entry.get("resume_phase") or "ready"
        state["turn"] = (order.index(name) + 1) % len(order)
        if entry["phase"] == "trained":
            return start_exam(state, name, entry, kaggle, now)
        if entry["phase"] == "diagnosed":
            return start_fresh_training(state, name, entry, kaggle, now)
        if entry["phase"] == "ready":
            return start_cycle(state, name, entry, kaggle, now)
    return "idle"


# -- runner -------------------------------------------------------------------------------------------------
def run(*, url="http://127.0.0.1:11434", activate=True, students=None, once=False, kaggle=None, installer=None, sleep=time.sleep):
    """Loop until ``stop``; every result is saved, so a new runner continues where this one stopped."""
    AUTOPILOT.mkdir(parents=True, exist_ok=True)
    state = load()
    if runner_alive(state) and (state.get("runner") or {}).get("pid") != os.getpid():
        raise SystemExit(f"Un autopilote tourne déjà (processus {state['runner'].get('pid')})")
    if STOP_FILE.exists():
        STOP_FILE.unlink()
    state.update(enabled=True, activate=activate, ollama_url=url)
    if students:
        state["order"] = list(students)
    state["runner"] = {"pid": os.getpid(), "started_at": time.time(), "heartbeat": time.time(), "busy": None}
    note(state, None, "autopilote démarré")
    save(state)
    kaggle = kaggle or Kaggle()
    installer = installer or Installer(url)
    while True:
        if STOP_FILE.exists():
            state = load()
            state.update(enabled=False, runner=None)
            note(state, None, "autopilote arrêté ; un kernel déjà lancé sur Kaggle continue et sera suivi au redémarrage")
            save(state)
            return "stopped"
        try:
            result = tick(state, kaggle, installer)
        except Exception as exc:                          # one failed step must not end a weekly loop
            result = "error"
            note(state, None, f"erreur : {type(exc).__name__}: {str(exc)[:400]}")
        state.setdefault("runner", {})["heartbeat"] = time.time()
        state["last_result"] = result
        save(state)
        if once:
            return result
        if result in ("discovered", "advanced", "concluded", "delivered", "rejected"):
            continue                                       # the next step may follow at once
        waited = 0
        while waited < TICK_SECONDS and not STOP_FILE.exists():
            sleep(15)
            waited += 15
            if waited % 60 == 0:
                state["runner"]["heartbeat"] = time.time()
                save(state)


def stop():
    AUTOPILOT.mkdir(parents=True, exist_ok=True)
    STOP_FILE.write_text(str(time.time()), encoding="utf-8")
    state = load()
    note(state, None, "arrêt demandé")
    save(state)
    return {"stopping": True}


def resume(student):
    """After a pause: the student's state is read again from Kaggle and the PC at the next step."""
    state = load()
    entry = track(state, student)
    entry.update(phase="new", rejected_in_a_row=0, failures_in_a_row=0, why=None)
    note(state, student, "repris : l'état sera relu sur Kaggle et sur ce PC")
    save(state)
    return entry


def status():
    """What the interface shows: the runner, the quota, one line per student and the last events."""
    state = load()
    alive = runner_alive(state)
    keys = ("phase", "cycle", "best_cycle", "installed_cycle", "kernel", "until", "why", "deliveries", "rejected_in_a_row", "advice")
    return {"enabled": bool(state.get("enabled")), "running": alive,
            "busy": (state.get("runner") or {}).get("busy") if alive else None,
            "activate": state.get("activate", True), "owner": state.get("owner"), "quota": state.get("quota"),
            "students": {name: {**{key: entry.get(key) for key in keys}, "last": (entry.get("history") or [None])[-1]}
                         for name, entry in state["students"].items()},
            "events": state["events"][-30:], "updated_at": state.get("updated_at"), "last_result": state.get("last_result")}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("command", choices=("status", "run", "tick", "stop", "resume"))
    parser.add_argument("--ollama-url", default="http://127.0.0.1:11434")
    parser.add_argument("--no-activate", action="store_true", help="install verified models beside the current ones, never switch the tag")
    parser.add_argument("--students", help="comma-separated tags (default: " + ", ".join(STUDENTS) + ")")
    parser.add_argument("--student", help="resume: the student to restart after a pause")
    args = parser.parse_args(argv)
    students = [name.strip() for name in args.students.split(",") if name.strip()] if args.students else None
    if args.command == "status":
        result = status()
    elif args.command == "stop":
        result = stop()
    elif args.command == "resume":
        if not args.student:
            parser.error("resume requires --student")
        result = resume(args.student)
    else:
        result = run(url=args.ollama_url, activate=not args.no_activate, students=students, once=args.command == "tick")
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
