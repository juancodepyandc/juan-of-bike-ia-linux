"""Assemble exams and training pools from sources and generators.

Three kinds of item sets exist and never mix:

* ``diagnostic`` exam  – steers the curriculum (which skills are weak);
* ``gate`` exam        – decides promotion; a fresh slice for every cycle;
* training pool        – the only items a trainer may learn from.

The examiner publishes aggregate scores and the *hashes* of its questions. The
trainer drops every pool item whose question hash is on that blocklist, so a
question shared by two datasets cannot leak from the exam into training.
"""
from __future__ import annotations

from collections import defaultdict

from . import generators, generators_domain  # noqa: F401  (registers the families)
from .records import rank, validate_item
from .sources import SOURCES, load_source

#: Aurora modules covered by text students, and what each one stands for.
MODULES = {
    "missions": "Missions, CLI et agent : actions JSON, reçus, pointeurs, comptes rendus fondés",
    "code": "Code : fonctions Python, correction de bugs, SQL, traçage, autres langages",
    "conversation": "Conversation : connaissances et raisonnement en français, lecture, traduction, consignes",
    "academy": "Academy : sciences, mathématiques, médecine, culture générale",
    "cyber": "Cyber : connaissances défensives, classification CWE, renseignement sur la menace",
    "business": "Business : calcul financier, lecture de rapports, sentiment",
    "cowork": "Cowork : extraction de documents, appels d'outils, JSON conforme à un schéma",
    "media": "Image, Dessin, Vidéo, Animation : compréhension et traduction des demandes visuelles",
    "engineering": "3D et Simulation : volumes, masses, tolérances, cinématique, unités",
}


def skills(modules=None):
    """Catalogue ``skill -> {module, train_sources, exam_sources, generator}``."""
    catalogue = defaultdict(lambda: {"module": None, "train_sources": [], "exam_sources": [], "generator": False})
    for name, spec in SOURCES.items():
        entry = catalogue[spec["skill"]]
        entry["module"] = spec["module"]
        if spec["role"] == "train" or spec["split_share"] is not None:
            entry["train_sources"].append(name)
        if spec["role"] == "exam":
            entry["exam_sources"].append(name)
    for name, spec in generators.FAMILIES.items():
        entry = catalogue[name]
        entry["module"], entry["generator"] = spec["module"], True
    # MetaMathQA feeds two skills; its hard half has no source of its own name.
    catalogue["academy.math_hard"]["train_sources"].append("metamath")
    chosen = {skill: entry for skill, entry in catalogue.items() if not modules or entry["module"] in modules}
    return dict(sorted(chosen.items()))


def stratified(items, count, seed, cycle=0):
    """Round-robin over sub-skills in a seeded order; ``cycle`` selects a fresh slice.

    Slices of successive cycles are disjoint until a sub-skill runs out of items,
    in which case its items are reused and the caller is told through ``reused``.
    """
    groups = defaultdict(list)
    for item in items:
        groups[item.get("subskill")].append(item)
    if not groups or count <= 0:
        return [], False
    per_group = -(-count // len(groups))
    reused, lanes = False, []
    for name in sorted(groups, key=str):
        ordered = sorted(groups[name], key=lambda item: rank(item["id"], seed))
        start = cycle * per_group
        if start + per_group > len(ordered) and cycle > 0:
            reused = True
            start %= max(1, len(ordered))
        lanes.append(ordered[start:] + ordered[:start])
    chosen, depth = [], 0
    while len(chosen) < count and any(depth < len(lane) for lane in lanes):
        for lane in lanes:
            if depth < len(lane) and len(chosen) < count:
                chosen.append(lane[depth])
        depth += 1
    return chosen, reused


class Library:
    """Lazy cache of loaded sources so one process downloads each dataset once."""

    def __init__(self, revisions=None, row_limit=None):
        self.revisions, self.row_limit, self._cache = revisions or {}, row_limit, {}
        self.errors = {}

    def load(self, name):
        if name not in self._cache:
            try:
                self._cache[name] = load_source(name, revisions=self.revisions, limit=self.row_limit)
            except Exception as exc:                       # an unreachable dataset must not fake an empty skill
                self.errors[name] = f"{type(exc).__name__}: {str(exc)[:200]}"
                self._cache[name] = ([], [])
        return self._cache[name]

    def exam_family(self, skill, catalogue):
        items = []
        for name in catalogue[skill]["exam_sources"]:
            items += [item for item in self.load(name)[1] if item["skill"] == skill]
        return items

    def train_family(self, skill, catalogue):
        items = []
        for name in catalogue[skill]["train_sources"]:
            items += [item for item in self.load(name)[0] if item["skill"] == skill]
        return items


def _generated(skill, role, count):
    family = generators.FAMILIES[skill]
    per = -(-count // len(family["subskills"]))
    built = [generators.generate(skill, role, index, subskill)
             for subskill in family["subskills"] for index in range(per)]
    return sorted(built, key=lambda item: rank(item["id"], role))[:count] if count < len(built) else built


def build_exam(role, per_skill, *, modules=None, cycle=0, library=None, seed="aurora-exam"):
    """Exam items of one role. Returns ``(items, notes)``; ``notes`` reports reuse and gaps."""
    if role not in ("diagnostic", "gate"):
        raise ValueError("An exam role is diagnostic or gate")
    library = library or Library()
    catalogue = skills(modules)
    items, notes = [], {"reused": [], "empty": [], "skills": {}}
    for skill, entry in catalogue.items():
        chosen = []
        if entry["generator"]:
            chosen = _generated(skill, "diagnostic" if role == "diagnostic" else f"gate:{cycle}", per_skill)
        elif entry["exam_sources"]:
            family = [item for item in library.exam_family(skill, catalogue) if item["exam_role"] == role]
            chosen, reused = stratified(family, per_skill, f"{seed}:{role}", cycle if role == "gate" else 0)
            if reused:
                notes["reused"].append(skill)
        if not chosen:
            if entry["generator"] or entry["exam_sources"]:
                notes["empty"].append(skill)
            continue
        notes["skills"][skill] = len(chosen)
        for item in chosen:
            exam_item = {k: v for k, v in item.items() if k != "target"}
            items.append(validate_item(exam_item, training=False))
    notes["source_errors"] = dict(library.errors)
    return items, notes


def exam_blocklist(*, modules=None, library=None):
    """Short hashes of every question of the exam families (both roles), for the trainer."""
    library = library or Library()
    catalogue = skills(modules)
    hashes = set()
    for skill, entry in catalogue.items():
        for item in library.exam_family(skill, catalogue):
            hashes.add(item["question_hash"][:20])
    return sorted(hashes)


def build_pool(per_skill, *, modules=None, blocklist=(), library=None, seed="aurora-pool", subskill_weights=None):
    """Training pool per skill, after removing every blocklisted question.

    ``subskill_weights`` (skill -> {subskill: weight}) shifts the generator
    budget toward the sub-skills the diagnosis found weak.
    """
    library = library or Library()
    catalogue = skills(modules)
    blocked = set(blocklist)
    pool, removed = {}, 0
    for skill, entry in catalogue.items():
        items = []
        if entry["generator"]:
            family = generators.FAMILIES[skill]
            weights = (subskill_weights or {}).get(skill) or {}
            total = sum(weights.get(s, 1.0) for s in family["subskills"])
            for subskill in family["subskills"]:
                share = max(4, round(per_skill * weights.get(subskill, 1.0) / total))
                items += [generators.generate(skill, "train", index, subskill) for index in range(share)]
        elif entry["train_sources"]:
            family = library.train_family(skill, catalogue)
            items, _ = stratified(family, per_skill, seed)
        kept = [item for item in items if item["question_hash"][:20] not in blocked]
        removed += len(items) - len(kept)
        if kept:
            pool[skill] = [validate_item(item, training=True) for item in kept]
    return pool, {"removed_by_blocklist": removed, "source_errors": dict(library.errors)}
