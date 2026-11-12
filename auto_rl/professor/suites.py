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
from .pins import DATASETS
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


def skills(modules=None, only=None):
    """Catalogue ``skill -> {module, train_sources, exam_sources, generator}``.

    ``only`` restricts the catalogue to named skills (a targeted cycle); replay
    skills without an exam stay available to the curriculum when their module is selected.
    """
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
    if only:
        unknown = set(only) - set(catalogue)
        if unknown:
            raise ValueError(f"Unknown skills: {sorted(unknown)}")
        chosen = {skill: entry for skill, entry in chosen.items()
                  if skill in only or not (entry["generator"] or entry["exam_sources"])}
    return dict(sorted(chosen.items()))


#: Positions reserved for each cycle in the layout of a gate family. A cycle may ask for any number of
#: items up to this slot: slices of different cycles are then disjoint whatever each one asked for. With
#: positions ``cycle * count`` a cycle asking 100 items after cycles of 150 reused 100 items uncounted.
GATE_SLOT = 150


def stratified(items, count, seed, cycle=0, slot=None):
    """Round-robin over sub-skills in a seeded order; ``cycle`` selects the next slice of that order.

    The whole family is laid out once (one item of each sub-skill in turn, until every sub-skill is
    exhausted) and cycle ``c`` takes positions ``[c * step, c * step + count)`` with ``step = slot or count``:
    the slices of successive cycles are disjoint by construction, whatever the sizes of the sub-skills.
    When the family runs out, the slice is completed with items an earlier cycle used; the second value
    is how many of them there are (0 while every item is new).
    """
    if slot is not None and count > slot:
        raise ValueError(f"A cycle may take at most {slot} items per skill from a gate family; {count} were asked")
    groups = defaultdict(list)
    for item in items:
        groups[item.get("subskill")].append(item)
    if not groups or count <= 0:
        return [], 0
    lanes = [sorted(groups[name], key=lambda item: rank(item["id"], seed)) for name in sorted(groups, key=str)]
    sequence = [lane[depth] for depth in range(max(map(len, lanes))) for lane in lanes if depth < len(lane)]
    start = cycle * (slot or count)
    if cycle > 0 and start >= len(sequence):              # nothing new is left: the whole slice was seen before
        offset = start % len(sequence)
        chosen = (sequence[offset:] + sequence[:offset])[:count]
        return chosen, len(chosen)
    chosen = sequence[start:start + count]
    refill = sequence[:min(start, count - len(chosen))] if cycle > 0 else []
    return chosen + refill, len(refill)


class Library:
    """Lazy cache of loaded sources so one process downloads each dataset once."""

    def __init__(self, revisions=None, row_limit=None):
        # Verified, pinned dataset revisions by default: both machines read identical data.
        self.revisions, self.row_limit, self._cache = DATASETS if revisions is None else revisions, row_limit, {}
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


#: How many indices are tried per needed item before a generated sub-skill is declared exhausted.
SEARCH_FACTOR = 12
#: Earlier gates looked at when counting reuse (the deployment exam uses cycle numbers above 1000).
EARLIER_GATES = 32


def _distinct(skill, role, count, avoid=frozenset()):
    """Up to ``count`` generated items with distinct prompts, those absent from ``avoid`` first.

    Some families have small parameter spaces (about 18 distinct prompts for one format sub-skill):
    counting a repeated prompt twice inflates the number of items and the confidence of a verdict.
    Returns ``(items, reused)`` where ``reused`` counts the items whose prompt is in ``avoid``.
    """
    family = generators.FAMILIES[skill]
    per = -(-count // len(family["subskills"]))
    fresh, again = [], []
    for subskill in family["subskills"]:
        seen, lane, spare = set(), [], []
        for index in range(per * SEARCH_FACTOR):
            item = generators.generate(skill, role, index, subskill)
            if item["question_hash"] in seen:
                continue
            seen.add(item["question_hash"])
            (spare if item["question_hash"] in avoid else lane).append(item)
            if len(lane) >= per:
                break
        fresh += lane
        again += spare[:max(0, per - len(lane))]
    order = lambda item: rank(item["id"], role)
    chosen = sorted(fresh, key=order)[:count]
    chosen += sorted(again, key=order)[:count - len(chosen)]
    return chosen, sum(item["question_hash"] in avoid for item in chosen)


def _earlier_prompts(skill, cycle):
    """Prompts the diagnostic exam and the gates before ``cycle`` may have used.

    Each earlier exam is recomputed with the current rule, plus the indices the first version of this
    module took (``[0, ceil(slot / sub-skills))`` of each sub-skill), so the gates of the November runs
    are covered as well.
    """
    family = generators.FAMILIES[skill]
    per = -(-GATE_SLOT // len(family["subskills"]))

    def first_version(role):
        return {generators.generate(skill, role, index, subskill)["question_hash"]
                for subskill in family["subskills"] for index in range(per)}
    used = first_version("diagnostic") | {item["question_hash"] for item in _distinct(skill, "diagnostic", GATE_SLOT)[0]}
    for earlier in range(min(cycle, EARLIER_GATES)):
        role = f"gate:{earlier}"
        used |= first_version(role) | {item["question_hash"] for item in _distinct(skill, role, GATE_SLOT, used)[0]}
    return used


def _generated(skill, role, count, cycle=0):
    if role == "diagnostic":
        return _distinct(skill, "diagnostic", count)
    return _distinct(skill, f"gate:{cycle}", count, _earlier_prompts(skill, cycle))


def build_exam(role, per_skill, *, modules=None, cycle=0, library=None, seed="aurora-exam", only=None):
    """Exam items of one role. Returns ``(items, notes)``; ``notes`` reports reuse and gaps."""
    if role not in ("diagnostic", "gate"):
        raise ValueError("An exam role is diagnostic or gate")
    library = library or Library()
    catalogue = skills(modules, only)
    items, notes = [], {"reused": [], "reused_items": {}, "unusable": {}, "empty": [], "skills": {}}
    for skill, entry in catalogue.items():
        chosen = []
        reused = 0
        if entry["generator"]:
            if role == "gate" and per_skill > GATE_SLOT:
                raise ValueError(f"A cycle may take at most {GATE_SLOT} items per skill from a gate family; {per_skill} were asked")
            chosen, reused = _generated(skill, role, per_skill, cycle)
        elif entry["exam_sources"]:
            family = [item for item in library.exam_family(skill, catalogue) if item["exam_role"] == role]
            chosen, reused = stratified(family, per_skill, f"{seed}:{role}", cycle if role == "gate" else 0,
                                        slot=GATE_SLOT if role == "gate" else None)
        if reused:                                         # counted, so a verdict can say how much of its exam is not new
            notes["reused"].append(skill)
            notes["reused_items"][skill] = reused
        # Items whose reference no correct answer can match stay in the layout but never in an exam.
        unusable = [item for item in chosen if item.get("unusable")]
        if unusable:
            notes["unusable"][skill] = len(unusable)
            chosen = [item for item in chosen if not item.get("unusable")]
        if not chosen:
            if entry["generator"] or entry["exam_sources"]:
                notes["empty"].append(skill)
            continue
        notes["skills"][skill] = len(chosen)
        for item in chosen:
            exam_item = {k: v for k, v in item.items() if k != "target"}
            items.append(validate_item(exam_item, training=False))
    # Only the exam sources of this exam: a training source the same library failed to load is not an exam gap.
    exam_names = {name for entry in catalogue.values() for name in entry["exam_sources"]}
    notes["source_errors"] = {name: error for name, error in library.errors.items() if name in exam_names}
    return items, notes


def exam_blocklist(*, modules=None, library=None, only=None):
    """Short hashes of every question of the exam families (both roles), for the trainer."""
    library = library or Library()
    catalogue = skills(modules, only)
    hashes = set()
    for skill, entry in catalogue.items():
        for item in library.exam_family(skill, catalogue):
            hashes.add(item["question_hash"][:20])
    return sorted(hashes)


#: Index offset between the generated training items of successive cycles (far above any pool size).
POOL_STRIDE = 1_000_000


def build_pool(per_skill, *, modules=None, blocklist=(), library=None, seed="aurora-pool", subskill_weights=None, only=None,
               sizes=None, cycle=0):
    """Training pool per skill, after removing every blocklisted question.

    ``subskill_weights`` (skill -> {subskill: weight}) shifts the generator
    budget toward the sub-skills the diagnosis found weak. ``sizes`` (skill ->
    count) enlarges the pool of a skill whose curriculum share exceeds
    ``per_skill``, so the weakest skills are not capped by the default pool.
    ``cycle`` draws exercises the earlier cycles did not use: new generated items,
    and the next slice of each public source (a source that runs out is named in ``reused``).
    """
    library = library or Library()
    catalogue = skills(modules, only)
    blocked = set(blocklist)
    pool, removed, reused = {}, 0, []
    for skill, entry in catalogue.items():
        items = []
        wanted = max(per_skill, (sizes or {}).get(skill, 0))
        if entry["generator"]:
            family = generators.FAMILIES[skill]
            weights = (subskill_weights or {}).get(skill) or {}
            total = sum(weights.get(s, 1.0) for s in family["subskills"])
            for subskill in family["subskills"]:
                share = max(4, round(wanted * weights.get(subskill, 1.0) / total))
                # Distinct exercises only (prompt and answer): a sub-skill with 24 possible prompts produced 334 items,
                # many of them exact copies (review, 2026-11-12). The development split groups equal prompts (train.py).
                seen, lane = set(), []
                for index in range(share * SEARCH_FACTOR):
                    item = generators.generate(skill, "train", cycle * POOL_STRIDE + index, subskill)
                    key = (item["question_hash"], item["target"])
                    if key not in seen:
                        seen.add(key)
                        lane.append(item)
                        if len(lane) >= share:
                            break
                items += lane
        elif entry["train_sources"]:
            family = library.train_family(skill, catalogue)
            items, again = stratified(family, wanted, seed, cycle)
            if again:
                reused.append(skill)
        kept = [item for item in items if item["question_hash"][:20] not in blocked]
        removed += len(items) - len(kept)
        if kept:
            pool[skill] = [validate_item(item, training=True) for item in kept]
    return pool, {"removed_by_blocklist": removed, "source_errors": dict(library.errors), "cycle": cycle, "reused": reused}
