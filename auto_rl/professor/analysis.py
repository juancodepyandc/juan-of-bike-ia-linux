"""Understanding an exam, not only its verdict: what failed, why, and what the next cycle should change.

It runs where the examiner's output was downloaded (the PC, for the autopilot). It reads the graded answers of
the base, of the adapter the candidate continues and of the candidate, rebuilds each graded item from its
generator or its pinned source to know what the grader accepted, and reports per skill:

- the movement against the base and against the previous adapter;
- a taxonomy of the candidate's errors: empty or cut answers, a right answer buried in a verbose one, a
  difference of letter case only, JSON wrapped under one key, then the grader's own reason;
- signs that an error is the exam's rather than the model's (the checks made by hand on 12 November that
  found several grader defects): many failures that contain the accepted answer, or that differ by case only;
- the items the candidate broke, with examples, and for label tasks the shift of the predicted labels
  (cycle 2 called neutral financial sentences "positive");
- the link with what was trained (the trainer's curriculum): trained skills that did not move, untrained
  skills that moved (side effects).

Recommendations for the next cycle name skills only. No exam item, answer or prompt leaves this module towards
training, so the next gate stays unseen.
"""
from __future__ import annotations

import json
import re
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path

from .records import read_json

#: Shares and counts behind the flags (chosen from the 12 November reviews; see the master document, 1.36).
VERBOSE_SHARE, CASE_SHARE, WRAPPED_SHARE, MIN_ERRORS = 0.4, 0.3, 0.3, 5
#: A trained skill below this accuracy that does not move in two analysed cycles is dropped from training.
STUCK_BELOW, STUCK_GAIN, STUCK_P = 0.85, 0.02, 0.2
WATCH_DROP = 0.03
#: Reasons that describe the form of an answer rather than its content.
FORM_FAILURES = ("vide", "coupee_par_le_budget", "reponse_juste_mais_verbeuse", "casse_seulement", "json_emballe_sous_une_cle",
                 "no_number", "no_option_letter", "no_label", "no_final_answer", "several_letters", "several_labels",
                 "conflicting_marked_letters", "arguments_not_json", "not_a_tool_args_object", "call_without_name", "no_code",
                 "no_query", "overlong", "not_a_pointer", "not_a_verify_action", "empty")
EXAMPLES = 3


def _norm(text):
    text = unicodedata.normalize("NFKC", str(text or "")).lower()
    return re.sub(r"\s+", " ", re.sub(r"[^\w\s%.,-]", " ", text)).strip()


def _rows(folder):
    path = Path(folder) / "results.jsonl"
    rows = {}
    if not path.is_file():
        return rows
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            row = json.loads(line)
        except ValueError:                               # a cut last line
            continue
        rows[row["id"]] = row
    return rows


class Items:
    """Exam items rebuilt from their identifiers: a generator family, or a pinned source loaded once."""

    def __init__(self, library=None):
        self.library, self._sources = library, {}

    def get(self, item_id):
        from . import generators, generators_domain  # noqa: F401  (registers the families)
        parts = str(item_id).split(":")
        try:
            if parts[0] == "gen":
                name, subskill, index = parts[1], parts[-2], int(parts[-1])
                return generators.generate(name, ":".join(parts[2:-2]), index, subskill)
            source = parts[1]
            if source not in self._sources:
                from .sources import load_source
                train, exam = load_source(source)
                self._sources[source] = {item["id"]: item for item in exam + train}
            return self._sources[source].get(item_id)
        except Exception:                                # a source that cannot load leaves the reason as the grader's
            return None


def _lower(value):
    if isinstance(value, str):
        return value.lower()
    if isinstance(value, dict):
        return {key: _lower(inner) for key, inner in value.items()}
    if isinstance(value, list):
        return [_lower(inner) for inner in value]
    return value


def categorize(item, row):
    """Why one answer is wrong, from the most telling cause to the grader's own reason."""
    from .graders import grade
    output = row.get("output") or ""
    if row.get("status") not in (None, "graded"):
        return "non_note"
    if not output.strip():
        return "vide"
    if row.get("cut"):
        return "coupee_par_le_budget"
    grader = (item or {}).get("grader") or {}
    kind = grader.get("type")
    if kind == "text":
        answers = [_norm(answer) for answer in grader.get("answers") or [] if str(answer).strip()]
        if answers and any(answer in _norm(output) for answer in answers):
            return "reponse_juste_mais_verbeuse"
    if kind in ("tool_call", "json") and item is not None:
        try:
            relaxed = {**item, "grader": _lower(grader)}
            if grade(relaxed, output.lower())["correct"]:
                return "casse_seulement"
        except Exception:
            pass
    if kind == "json" and item is not None:
        try:
            parsed = json.loads(re.sub(r"^```(?:json)?\s*|\s*```$", "", output.strip()))
            if isinstance(parsed, dict) and len(parsed) == 1:
                inner = next(iter(parsed.values()))
                if grade(item, json.dumps(inner, ensure_ascii=False))["correct"]:
                    return "json_emballe_sous_une_cle"
        except Exception:
            pass
    reason = str(row.get("reason") or "inconnue")
    return re.split(r"[:\s]", reason, maxsplit=1)[0] or "inconnue"


def _accuracy(rows, ids):
    graded = [rows[i] for i in ids if i in rows and rows[i].get("status", "graded") == "graded"]
    return (sum(bool(r.get("correct")) for r in graded) / len(graded)) if graded else None


def _trained(curriculum):
    """Examples each skill received in the cycle's curriculum (replay included)."""
    planned = ((curriculum or {}).get("plan") or {}).get("skills") or {}
    return {name: int(entry.get("selected") or 0) for name, entry in planned.items()}


def analyse(folder, *, curriculum=None, library=None, items=None):
    """Report of one examiner output folder (the one holding ``aurora_professor/verdict_N.json``)."""
    folder = Path(folder)
    found = sorted(folder.rglob("verdict_*.json"))
    if not found:
        raise ValueError(f"no verdict in {folder}")
    verdict = json.loads(found[-1].read_text(encoding="utf-8"))
    gate = found[-1].parent / f"gate_{verdict['cycle']}"
    models = {name: _rows(gate / name) for name in ("base", "previous", "candidate")}
    if not models["candidate"]:
        raise ValueError(f"no graded answers in {gate}")
    items = items or Items(library)
    trained = _trained(curriculum)
    versus = (verdict.get("versus_previous") or {}).get("skills") or {}
    by_skill = defaultdict(list)
    for item_id, row in models["candidate"].items():
        by_skill[row["skill"]].append(item_id)
    skills = {}
    for skill, ids in sorted(by_skill.items()):
        candidate = models["candidate"]
        wrong = [i for i in ids if not candidate[i].get("correct")]
        categories, examples = Counter(), defaultdict(list)
        for item_id in wrong:
            category = categorize(items.get(item_id), candidate[item_id])
            categories[category] += 1
            if len(examples[category]) < EXAMPLES:
                examples[category].append({"id": item_id, "output": (candidate[item_id].get("output") or "")[:240]})
        base_wrong_same = Counter()
        for item_id in ids:
            row = models["base"].get(item_id)
            if row is not None and not row.get("correct"):
                base_wrong_same[categorize(items.get(item_id), row)] += 1
        broken = [i for i in ids if models["previous"].get(i, {}).get("correct") and not candidate[i].get("correct")]
        fixed = [i for i in ids if models["previous"].get(i) is not None and not models["previous"][i].get("correct")
                 and candidate[i].get("correct")]
        entry = {"items": len(ids), "base": _accuracy(models["base"], ids), "previous": _accuracy(models["previous"], ids),
                 "candidate": _accuracy(candidate, ids), "trained_examples": trained.get(skill, 0),
                 "versus_previous_p": (versus.get(skill) or {}).get("mcnemar_p"),
                 "errors": dict(categories.most_common()), "examples": dict(examples),
                 "base_errors": dict(base_wrong_same.most_common()),
                 "broken_by_candidate": len(broken), "fixed_against_previous": len(fixed),
                 "broken_examples": [{"id": i, "output": (candidate[i].get("output") or "")[:240]} for i in broken[:EXAMPLES]]}
        labels = _label_shift(items, ids, models)
        if labels:
            entry["labels"] = labels
        entry["flags"] = _flags(skill, entry)
        skills[skill] = entry
    report = {"kind": "aurora_professor_analysis", "cycle": verdict["cycle"], "student": (verdict.get("student") or {}).get("tag"),
              "verdict": verdict.get("verdict"), "versus_previous": (verdict.get("versus_previous") or {}).get("verdict"),
              "trained": trained, "skills": skills}
    report["side_effects"] = side_effects(report)
    return report


def _label_shift(items, ids, models):
    """For label tasks: how often each label was answered by each model, against the expected labels."""
    expected, said = Counter(), {name: Counter() for name in models}
    for item_id in ids:
        item = items.get(item_id)
        grader = (item or {}).get("grader") or {}
        if grader.get("type") != "label":
            return None
        expected[str(grader.get("answer") or "?").lower()] += 1
        for name, rows in models.items():
            row = rows.get(item_id)
            if row is not None:
                said[name][_norm(row.get("output"))[:20] or "vide"] += 1
    return {"expected": dict(expected), **{name: dict(counter.most_common(6)) for name, counter in said.items() if counter}}


def _flags(skill, entry):
    flags = []
    errors, total = entry["errors"], sum(entry["errors"].values())
    if total >= MIN_ERRORS:
        if errors.get("reponse_juste_mais_verbeuse", 0) / total >= VERBOSE_SHARE:
            flags.append("concision : la bonne réponse est souvent noyée dans une réponse trop longue "
                         "(à entraîner, ou correcteur trop strict à relire)")
        if errors.get("casse_seulement", 0) / total >= CASE_SHARE:
            flags.append("correcteur à relire : beaucoup d'échecs ne diffèrent que par la casse")
        if errors.get("json_emballe_sous_une_cle", 0) / total >= WRAPPED_SHARE:
            flags.append("format : le JSON est emballé sous une clé au lieu de suivre le schéma")
        if (errors.get("vide", 0) + errors.get("coupee_par_le_budget", 0)) / total >= 0.2:
            flags.append("réponses vides ou coupées par le budget de tokens : budget ou consigne à revoir")
    # Both models failing the same way on the form of the answer (no number, no letter, unreadable JSON...) points at the
    # instruction or the grader; failing on the content (a wrong number, a wrong letter) is the model's weakness.
    base_errors = entry["base_errors"]
    shared = sum(min(base_errors.get(name, 0), errors.get(name, 0)) for name in FORM_FAILURES)
    if total >= MIN_ERRORS and shared / total >= 0.5:
        flags.append("base et candidat échouent surtout sur la forme de la réponse : consigne ou correcteur à vérifier")
    if entry["previous"] is not None and entry["candidate"] is not None and entry["previous"] - entry["candidate"] >= WATCH_DROP:
        flags.append(f"baisse de {100 * (entry['previous'] - entry['candidate']):.1f} points contre l'adaptateur précédent")
    return flags


def side_effects(report):
    """Skills that moved without being trained, and trained skills that did not move."""
    moved, stuck = [], []
    for skill, entry in report["skills"].items():
        if entry["previous"] is None or entry["candidate"] is None:
            continue
        delta = entry["candidate"] - entry["previous"]
        if not entry["trained_examples"] and abs(delta) >= WATCH_DROP:
            moved.append({"skill": skill, "delta": round(delta, 4)})
        if entry["trained_examples"] and delta < STUCK_GAIN and entry["candidate"] < STUCK_BELOW:
            stuck.append({"skill": skill, "delta": round(delta, 4), "examples": entry["trained_examples"]})
    return {"untrained_moved": moved, "trained_stuck": stuck}


def recommend(reports):
    """Next-cycle advice from the analysed cycles of one student, newest last. Skills only.

    ``exclude``: trained in each of the last two analysed cycles, still below 85 %, without a gain of 2 points
    against the previous adapter: the budget goes to skills that respond (as code.trace on 12 November).
    Skills near their ceiling stay trained: a floor keeps what was won.
    """
    if not reports:
        return {"exclude": [], "priority": [], "concision": [], "review_grader": [], "watch": []}
    last = reports[-1]
    stuck = [{s["skill"] for s in r.get("side_effects", {}).get("trained_stuck", [])} for r in reports[-2:]]
    exclude = sorted(set.intersection(*stuck)) if len(stuck) == 2 else []
    skills = last["skills"]
    priority = sorted((name for name, entry in skills.items() if entry["candidate"] is not None and name not in exclude),
                      key=lambda name: skills[name]["candidate"])[:3]
    concision = sorted(name for name, entry in skills.items() if any(f.startswith("concision") for f in entry["flags"]))
    review = sorted(name for name, entry in skills.items() if any("correcteur" in f for f in entry["flags"]))
    watch = sorted({m["skill"] for m in last.get("side_effects", {}).get("untrained_moved", []) if m["delta"] < 0}
                   | {name for name, entry in skills.items() if any(f.startswith("baisse") for f in entry["flags"])})
    return {"exclude": exclude, "priority": priority, "concision": concision, "review_grader": review, "watch": watch}


def summary_lines(report, advice=None):
    """French lines for the interface and the events of the autopilot."""
    lines = []
    for skill, entry in report["skills"].items():
        if entry["candidate"] is None:
            continue
        def pct(value):
            return "non mesuré" if value is None else f"{100 * value:.1f} %"
        movement = f"{pct(entry['base'])} → {pct(entry['candidate'])}"
        if entry["previous"] is not None:
            movement += f" (précédent {pct(entry['previous'])})"
        top = ", ".join(f"{name} {count}" for name, count in list(entry["errors"].items())[:2]) or "aucune erreur"
        lines.append(f"{skill} : {movement} ; erreurs : {top}" + (f" ; {entry['flags'][0]}" if entry["flags"] else ""))
    if advice:
        for key, label in (("exclude", "retirés de l'entraînement (bloqués deux cycles)"), ("concision", "à entraîner à la concision"),
                           ("review_grader", "correcteur à relire"), ("watch", "à surveiller")):
            if advice.get(key):
                lines.append(f"{label} : {', '.join(advice[key])}")
    return lines


def load_curriculum(folder):
    found = sorted(Path(folder).rglob("curriculum.json")) if folder else []
    return read_json(found[-1], None) if found else None
