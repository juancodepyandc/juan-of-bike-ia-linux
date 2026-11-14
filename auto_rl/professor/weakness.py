"""From measured errors to a targeted curriculum.

The diagnosis says where the student fails (per skill and sub-skill, with
uncertainty). The curriculum then spends the training budget where the error
is largest, keeps a floor on every skill so nothing is forgotten, and puts the
training items the student actually got wrong first.
"""
from __future__ import annotations

from collections import defaultdict

from .records import rank

#: Share of the budget spread evenly over all trainable skills, whatever their score.
FLOOR_SHARE = 0.25
#: Share reserved for fluent free-form answers, so targeted drills do not erode style.
REPLAY_SHARE = 0.15
#: Exponent on the error rate: 1 is proportional, larger focuses harder on the worst skills.
FOCUS = 1.5


def error_rate(correct, items):
    """Posterior mean error with a uniform prior: small samples are pulled toward 0.5."""
    return (items - correct + 1) / (items + 2)


def profile(summary, catalogue):
    """Ranked weak points: one row per skill with its sub-skills, weakest first."""
    rows = []
    for skill, entry in summary["skills"].items():
        info = catalogue.get(skill, {})
        subs = []
        for key, sub in summary["subskills"].items():
            if key.startswith(skill + " / "):
                subs.append({"subskill": key[len(skill) + 3:], "items": sub["items"], "accuracy": sub["accuracy"],
                             "error": error_rate(sub["correct"], sub["items"])})
        rows.append({"skill": skill, "module": entry["module"], "items": entry["items"], "accuracy": entry["accuracy"],
                     "ci95": entry["ci95"], "error": error_rate(entry["correct"], entry["items"]),
                     "trainable": bool(info.get("generator") or info.get("train_sources")),
                     "subskills": sorted(subs, key=lambda s: -s["error"])})
    return sorted(rows, key=lambda row: -row["error"])


def skill_weights(weak_points, available, *, focus=FOCUS, floor=FLOOR_SHARE):
    """Budget share per trainable skill: an even floor plus a part proportional to error**focus.

    Skills that are trainable but were not examined (train-only knowledge
    sources) receive the floor only.
    """
    examined = {row["skill"]: row["error"] for row in weak_points}
    names = sorted(available)
    if not names:
        return {}
    need = {name: examined.get(name, 0.0) ** focus for name in names}
    total = sum(need.values())
    weights = {}
    for name in names:
        targeted = need[name] / total if total else 1 / len(names)
        weights[name] = floor / len(names) + (1 - floor) * targeted
    return weights


def subskill_weights(weak_points, *, focus=FOCUS):
    """Relative weight of each sub-skill inside its skill, from the diagnostic errors."""
    result = {}
    for row in weak_points:
        if row["subskills"]:
            result[row["skill"]] = {sub["subskill"]: max(0.05, sub["error"]) ** focus for sub in row["subskills"]}
    return result


def _composition(items):
    """How many chosen items each sub-skill received: the curriculum states what it really trains on."""
    counts = defaultdict(int)
    for item in items:
        counts[str(item.get("subskill"))] += 1
    return dict(sorted(counts.items()))


def build_curriculum(pool, weights, total, *, mined=None, replay_skills=(), seed="aurora-curriculum"):
    """Pick ``total`` training items.

    ``mined`` maps item id -> bool (did the base model answer it correctly when
    it was probed on the training pool?). Items it failed come first, then
    unprobed items, then items it already solves.
    """
    mined = mined or {}
    replay = [name for name in replay_skills if name in pool]
    drill = [name for name in pool if name not in replay]
    replay_budget = int(total * REPLAY_SHARE) if replay else 0
    drill_budget = total - replay_budget
    drill_weights = {name: weights.get(name, 0.0) for name in drill}
    scale = sum(drill_weights.values()) or 1.0
    chosen, plan = [], {}

    def priority(item):
        state = mined.get(item["id"])
        return (0 if state is False else 1 if state is None else 2, rank(item["id"], seed))
    for name in drill:
        quota = round(drill_budget * drill_weights[name] / scale)
        ordered = sorted(pool[name], key=priority)
        picked = ordered[:quota]
        plan[name] = {"requested": quota, "selected": len(picked), "available": len(ordered),
                      "known_failures_included": sum(mined.get(i["id"]) is False for i in picked),
                      "subskills": _composition(picked)}
        chosen += picked
    # Replay is a share of what is really trained: drill quotas a skill cannot fill (self-worked skills keep only
    # verified answers) must not leave replay at 20-27 % of the curriculum instead of the declared 15 %.
    drilled = len(chosen)
    replay_budget = min(replay_budget, round(drilled * REPLAY_SHARE / (1 - REPLAY_SHARE))) if replay else 0
    for name in replay:
        quota = replay_budget // len(replay)
        picked = sorted(pool[name], key=lambda item: rank(item["id"], seed))[:quota]
        plan[name] = {"requested": quota, "selected": len(picked), "available": len(pool[name]), "replay": True}
        chosen += picked
    counts = defaultdict(int)
    for item in chosen:
        counts[item["module"]] += 1
    chosen.sort(key=lambda item: rank(item["id"], seed + ":order"))
    return chosen, {"skills": plan, "modules": dict(counts), "total": len(chosen)}
