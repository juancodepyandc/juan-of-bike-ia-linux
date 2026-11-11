"""Paired comparison of a base model and a candidate on the same unseen items.

The verdict is pre-registered in ``GATE``: it does not look at the training loss
and it cannot be passed by a single lucky skill. Pure Python, deterministic.
"""
from __future__ import annotations

import math
import random
from collections import defaultdict

#: Promotion rule, fixed before any result is seen.
GATE = {
    "min_items": 200,              # below this an exam cannot support a promotion
    "min_gain": 0.02,              # macro-average accuracy gain over skills
    "confidence": 0.95,            # paired bootstrap interval on that gain must exclude zero
    "max_skill_drop": 0.08,        # no skill may lose more than this ...
    "skill_drop_min_items": 30,    # ... when it has at least this many items
    "regression_alpha": 0.05,      # nor regress significantly (exact McNemar)
    "max_empty_rate_increase": 0.02,
    "bootstrap_samples": 4000,
}


def wilson(successes, total, z=1.96):
    """Wilson score interval for a proportion; ``(0, 1)`` when nothing was observed."""
    if total <= 0:
        return 0.0, 1.0
    p = successes / total
    denominator = 1 + z * z / total
    centre = (p + z * z / (2 * total)) / denominator
    margin = z * math.sqrt(p * (1 - p) / total + z * z / (4 * total * total)) / denominator
    return max(0.0, centre - margin), min(1.0, centre + margin)


def mcnemar_exact(base_only, candidate_only):
    """Two-sided exact McNemar p-value from the discordant pairs."""
    n = base_only + candidate_only
    if n == 0:
        return 1.0
    k = min(base_only, candidate_only)
    tail = sum(math.comb(n, i) for i in range(k + 1)) / 2 ** n
    return min(1.0, 2 * tail)


def pair(base_rows, candidate_rows):
    """Align graded rows by item; refuse silently different exams."""
    base = {row["id"]: row for row in base_rows if row.get("status", "graded") == "graded"}
    candidate = {row["id"]: row for row in candidate_rows if row.get("status", "graded") == "graded"}
    if set(base) != set(candidate):
        missing = len(set(base) ^ set(candidate))
        raise ValueError(f"Base and candidate were not graded on the same items ({missing} differ)")
    pairs = []
    for item_id in sorted(base):
        b, c = base[item_id], candidate[item_id]
        if b["skill"] != c["skill"]:
            raise ValueError(f"Item {item_id} changed skill between runs")
        pairs.append({"id": item_id, "module": b["module"], "skill": b["skill"], "subskill": b.get("subskill"),
                      "base": bool(b["correct"]), "candidate": bool(c["correct"]),
                      "base_empty": not str(b.get("output") or "").strip(),
                      "candidate_empty": not str(c.get("output") or "").strip()})
    return pairs


def _macro(pairs_by_skill, side):
    values = [sum(p[side] for p in group) / len(group) for group in pairs_by_skill.values() if group]
    return sum(values) / len(values) if values else 0.0


def _bootstrap(pairs_by_skill, samples, confidence, seed):
    """Paired bootstrap of the macro-average gain, resampling items within each skill."""
    rng = random.Random(seed)
    groups = [[(p["candidate"] - p["base"]) for p in group] for group in pairs_by_skill.values() if group]
    gains = []
    for _ in range(samples):
        total = 0.0
        for group in groups:
            n = len(group)
            total += sum(group[rng.randrange(n)] for _ in range(n)) / n
        gains.append(total / len(groups))
    gains.sort()
    alpha = (1 - confidence) / 2
    return gains[int(alpha * (samples - 1))], gains[int((1 - alpha) * (samples - 1))]


def _table(pairs):
    n = len(pairs)
    base, candidate = sum(p["base"] for p in pairs), sum(p["candidate"] for p in pairs)
    lost = sum(p["base"] and not p["candidate"] for p in pairs)
    won = sum(p["candidate"] and not p["base"] for p in pairs)
    return {"items": n, "base_correct": base, "candidate_correct": candidate,
            "base_accuracy": base / n if n else None, "candidate_accuracy": candidate / n if n else None,
            "gain": (candidate - base) / n if n else None, "fixed": won, "broken": lost,
            "mcnemar_p": mcnemar_exact(lost, won),
            "base_ci95": list(wilson(base, n)), "candidate_ci95": list(wilson(candidate, n))}


def compare(base_rows, candidate_rows, *, gate=None, seed=20261111):
    """Return per-skill tables and a verdict: ``promote``, ``reject`` or ``inconclusive``."""
    gate = {**GATE, **(gate or {})}
    pairs = pair(base_rows, candidate_rows)
    by_skill, by_module, by_subskill = defaultdict(list), defaultdict(list), defaultdict(list)
    for p in pairs:
        by_skill[p["skill"]].append(p)
        by_module[p["module"]].append(p)
        by_subskill[(p["skill"], p["subskill"])].append(p)
    macro_base, macro_candidate = _macro(by_skill, "base"), _macro(by_skill, "candidate")
    low, high = _bootstrap(by_skill, gate["bootstrap_samples"], gate["confidence"], seed) if pairs else (0.0, 0.0)
    skills = {skill: _table(group) for skill, group in sorted(by_skill.items())}
    reasons, regressions = [], []
    for skill, table in skills.items():
        significant = table["gain"] < 0 and table["mcnemar_p"] < gate["regression_alpha"]
        large = table["items"] >= gate["skill_drop_min_items"] and table["gain"] < -gate["max_skill_drop"]
        if significant or large:
            regressions.append(skill)
    empty_base = sum(p["base_empty"] for p in pairs) / len(pairs) if pairs else 0.0
    empty_candidate = sum(p["candidate_empty"] for p in pairs) / len(pairs) if pairs else 0.0
    gain = macro_candidate - macro_base
    if len(pairs) < gate["min_items"]:
        verdict = "inconclusive"
        reasons.append(f"only {len(pairs)} graded items; {gate['min_items']} are required")
    elif regressions:
        verdict = "reject"
        reasons.append("regression on: " + ", ".join(regressions))
    elif empty_candidate - empty_base > gate["max_empty_rate_increase"]:
        verdict = "reject"
        reasons.append(f"empty answers rose from {empty_base:.3f} to {empty_candidate:.3f}")
    elif high < 0:
        verdict = "reject"
        reasons.append("the candidate is significantly worse overall")
    elif gain >= gate["min_gain"] and low > 0:
        verdict = "promote"
        reasons.append(f"macro gain {gain:+.4f}, {int(gate['confidence'] * 100)}% interval [{low:+.4f}, {high:+.4f}] excludes zero, no skill regressed")
    else:
        verdict = "inconclusive"
        reasons.append(f"macro gain {gain:+.4f} with interval [{low:+.4f}, {high:+.4f}] does not meet the pre-registered rule "
                       f"(gain >= {gate['min_gain']} and lower bound > 0)")
    return {"verdict": verdict, "reasons": reasons, "gate": gate,
            "overall": {**_table(pairs), "macro_base": macro_base, "macro_candidate": macro_candidate,
                        "macro_gain": gain, "macro_gain_ci": [low, high],
                        "empty_rate_base": empty_base, "empty_rate_candidate": empty_candidate},
            "modules": {module: _table(group) for module, group in sorted(by_module.items())},
            "skills": skills,
            "subskills": {f"{skill} / {sub}": _table(group) for (skill, sub), group in sorted(by_subskill.items(), key=lambda kv: (kv[0][0], str(kv[0][1])))},
            "regressions": regressions}
