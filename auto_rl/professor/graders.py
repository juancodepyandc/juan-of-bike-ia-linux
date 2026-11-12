"""Deterministic graders: no model judge, no loss-derived score, no partial credit by length.

Every grader returns ``{"correct": bool, "score": float, "parsed": ..., "reason": str}``.
``correct`` drives the paired statistics; ``score`` is a continuous companion
(equal to ``correct`` unless the metric is naturally continuous).
"""
from __future__ import annotations

import json
import math
import os
import re
import secrets
import sqlite3
import subprocess
import sys
import tempfile
import unicodedata
from collections import Counter

LETTERS = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
_NUMBER = r"[-+\u2212]?(?:\d[\d\u00a0\u202f ,.'’]*\d|\d|\.\d+)(?:[eE][-+]?\d+)?(?:\s*/\s*\d+)?"   # ".4" is a number


def _result(correct, reason, parsed=None, score=None):
    return {"correct": bool(correct), "score": float(correct if score is None else score),
            "parsed": parsed, "reason": reason}


def strip_reasoning(text):
    """Drop finished reasoning blocks. An unfinished block means no answer was given."""
    text = re.sub(r"<think>.*?</think>", "", str(text), flags=re.S)
    if "<think>" in text:
        return ""
    return text.strip()


# --- multiple choice -------------------------------------------------------

def grade_mcq(output, grader):
    """Accept one unambiguous option letter; reject lists of letters and prose guesses."""
    count = int(grader.get("options", 4))
    valid = LETTERS[:count]
    text = strip_reasoning(output)
    text = re.sub(r"[*_`]", "", text).strip()
    if not text:
        return _result(False, "empty")
    strict = re.fullmatch(rf"\(?([{valid}{valid.lower()}])\)?\s*[.):]?", text)
    if strict:
        choice = strict.group(1).upper()
        return _result(choice == grader["answer"], "single_letter", choice)
    if re.search(rf"(?<![A-Za-z])\(?([{valid}])\)?\s*(?:,|/|\bou\b|\bor\b|\bet\b|\band\b)\s*\(?([{valid}])\)?(?![A-Za-z])", text):
        return _result(False, "several_letters")            # "A, B", "A) ou B)": a hedge, not an answer
    # Marker words in any case, the letter itself in upper case: "the answer is a guess: B" names B, not "a".
    marked = re.findall(rf"(?i:r[ée]ponse|answer|option|choix|correcte?)\s*(?i:finale|final|correcte?|is|est|:|=|\s)*\s*:?\s*\(?([{valid}])\)?(?![A-Za-z0-9])",
                        text)
    if marked:
        if len(set(marked)) > 1:
            return _result(False, "conflicting_marked_letters", sorted(set(marked)))
        return _result(marked[0] == grader["answer"], "marked_letter", marked[0])
    lead = re.match(rf"\(?([{valid}])\)?\s*(?:[.):,]|$|\n|\s+[-\u2013\u2014]\s)", text)
    if lead:
        choice = lead.group(1)
        return _result(choice == grader["answer"], "leading_letter", choice)
    return _result(False, "no_option_letter")


# --- numbers ---------------------------------------------------------------

def parse_numbers(token):
    """Return every plausible reading of a number written with FR or EN separators."""
    raw = token.strip().replace("\u2212", "-").replace("\u00a0", " ").replace("\u202f", " ")
    raw = raw.replace("'", "").replace("’", "")
    fraction = re.fullmatch(r"([-+]?[\d ,.]+?)\s*/\s*(\d+)", raw)
    if fraction:
        return [n / int(fraction.group(2)) for n in parse_numbers(fraction.group(1)) if int(fraction.group(2))]
    raw = raw.replace(" ", "")
    if not re.search(r"\d", raw):
        return []
    readings = set()
    if "," in raw and "." in raw:
        decimal = "," if raw.rfind(",") > raw.rfind(".") else "."
        other = "." if decimal == "," else ","
        readings.add(raw.replace(other, "").replace(decimal, "."))
    elif "," in raw:
        readings.add(raw.replace(",", "."))            # French decimal comma
        if re.fullmatch(r"[-+]?\d{1,3}(,\d{3})+(?:[eE][-+]?\d+)?", raw):
            readings.add(raw.replace(",", ""))         # English thousands separator
    elif raw.count(".") > 1:
        readings.add(raw.replace(".", ""))             # 1.234.567
    else:
        readings.add(raw)
    values = []
    for reading in readings:
        try:
            value = float(reading)
        except ValueError:
            continue
        if math.isfinite(value):
            values.append(value)
    return values


def extract_final_number(text):
    """Number after the last explicit final-answer marker, else the last number written."""
    text = strip_reasoning(text)
    markers = list(re.finditer(r"####|r[ée]ponse\s+finale\s*:?|final\s+answer\s*:?|the\s+answer\s+is\s*:?|la\s+r[ée]ponse\s+est\s*:?|\\boxed\{",
                               text, flags=re.I))
    if markers:
        # A final-answer marker followed by no number is an unfinished answer, not a pointer to an earlier number
        # (an answer cut by its token budget after "Final answer: $" was graded on the last number of its work).
        found = re.search(_NUMBER, text[markers[-1].end():])
        return found.group(0) if found else None
    found = re.findall(_NUMBER, text)
    return found[-1] if found else None


def numbers_match(candidates, expected, rel_tol, abs_tol, percent_ok=False):
    """Equal within the item's tolerances; with ``percent_ok`` a ratio and its percentage are the same answer.

    The rescaled readings use the relative tolerance only: with an absolute one, target / 100 of any ratio
    below 0.5 was within 0.005 of 0, and "Final answer: 0" passed 272 ConvFinQA items (review, 2026-11-12).
    """
    for value in candidates:
        for target in expected:
            if math.isclose(value, target, rel_tol=rel_tol, abs_tol=abs_tol):
                return True
            if percent_ok and target and any(math.isclose(value, option, rel_tol=rel_tol, abs_tol=0.0)
                                             for option in (target * 100, target / 100)):
                return True
    return False


def grade_numeric(output, grader):
    token = extract_final_number(output)
    if token is None:
        return _result(False, "no_number")
    expected = parse_numbers(str(grader["answer"]))
    if not expected:
        raise ValueError(f"Unparseable reference number: {grader['answer']!r}")
    # Tolerances are explicit per item; the default is exact up to floating-point noise.
    ok = numbers_match(parse_numbers(token), expected, grader.get("rel_tol", 1e-9),
                       grader.get("abs_tol", 1e-6), grader.get("percent_ok", False))
    return _result(ok, "number_compared", token.strip())


# --- short text ------------------------------------------------------------

def normalize_answer(text):
    """SQuAD-style normalization extended to French articles and elisions."""
    text = unicodedata.normalize("NFKC", str(text)).casefold()
    text = re.sub(r"\b(?:l|d|j|n|s|c|qu|m|t)['’]", " ", text)
    text = "".join(c if c.isalnum() or c.isspace() else " " for c in text)
    words = [w for w in text.split() if w not in {"a", "an", "the", "le", "la", "les", "un", "une", "des", "du", "de"}]
    return " ".join(words)


def token_f1(prediction, reference):
    p, r = normalize_answer(prediction).split(), normalize_answer(reference).split()
    if not p or not r:
        return float(p == r)
    common = sum((Counter(p) & Counter(r)).values())
    if not common:
        return 0.0
    precision, recall = common / len(p), common / len(r)
    return 2 * precision * recall / (precision + recall)


def _literal(text):
    """Case and spacing folded, every symbol, sign and word order kept."""
    text = unicodedata.normalize("NFKC", str(text)).casefold().strip()
    return re.sub(r"\s+", "", text.rstrip(".").strip())


def grade_text(output, grader):
    """Exact match after normalization, or a short answer that is almost the reference.

    With ``literal`` the answer must equal one reference with only case and spacing folded: brackets,
    signs and word order are the answer (BBH dyck words, arithmetic, word sorting), so a bag-of-words
    comparison that drops them graded an empty answer correct (review, 2026-11-12).
    """
    text = strip_reasoning(output)
    if grader.get("literal"):
        first = next((line for line in text.splitlines() if line.strip()), "")
        wanted = {_literal(reference) for reference in grader["answers"]}
        ok = bool(first.strip()) and (_literal(first) in wanted or _literal(text) in wanted)
        return _result(ok, "literal", first.strip()[:80])
    first = next((line for line in text.splitlines() if line.strip()), "")
    best, parsed = 0.0, first.strip()
    for candidate in {text, first}:
        for reference in grader["answers"]:
            if normalize_answer(candidate) == normalize_answer(reference) and normalize_answer(reference):
                return _result(True, "exact", candidate.strip(), 1.0)
            best = max(best, token_f1(candidate, reference))
    return _result(best >= grader.get("f1_threshold", 0.8), "token_f1", parsed, best)


def grade_label(output, grader):
    """Closed-set classification: exactly one label of the set may be named.

    With ``pattern`` the set is open (for example every ``CWE-<n>`` identifier):
    exactly one distinct identifier may appear in the answer.
    """
    if grader.get("pattern"):
        named = sorted({m.upper() for m in re.findall(grader["pattern"], strip_reasoning(output), flags=re.I)})
        if len(named) != 1:
            return _result(False, "no_label" if not named else "several_labels", named)
        return _result(named[0] == grader["answer"].upper(), "label", named[0])
    text = normalize_answer(strip_reasoning(output))
    padded = f" {text} "
    named = [label for label in grader["labels"] if f" {normalize_answer(label)} " in padded]
    # A label that is a prefix of another one (CWE-79 / CWE-798) is disambiguated
    # by the word boundary above, so two matches really are two claimed labels.
    if len(named) != 1:
        return _result(False, "no_label" if not named else "several_labels", named)
    if re.search(rf"\b(?:not|no|never|non|pas|isn t|n est pas|ne pas)\s+(?:\w+\s+)?{re.escape(normalize_answer(named[0]))}\b", text):
        return _result(False, "negated_label", named)       # "not positive" claims nothing
    return _result(named[0] == grader["answer"], "label", named[0])


# --- chrF (translation) ----------------------------------------------------

def chrf(hypothesis, reference, order=6, beta=2.0):
    """Character n-gram F-score (Popovic 2015), whitespace-insensitive, pure Python."""
    def grams(text, n):
        text = re.sub(r"\s+", " ", text.strip())
        compact = text.replace(" ", "")
        return Counter(compact[i:i + n] for i in range(len(compact) - n + 1))
    precisions, recalls = [], []
    for n in range(1, order + 1):
        h, r = grams(hypothesis, n), grams(reference, n)
        if not h or not r:
            continue
        overlap = sum((h & r).values())
        precisions.append(overlap / sum(h.values()))
        recalls.append(overlap / sum(r.values()))
    if not precisions:
        return 0.0
    p, r = sum(precisions) / len(precisions), sum(recalls) / len(recalls)
    if p + r == 0:
        return 0.0
    return (1 + beta ** 2) * p * r / (beta ** 2 * p + r)


def grade_chrf(output, grader):
    text = strip_reasoning(output)
    score = max(chrf(text, reference) for reference in grader["references"])
    # A translation padded with commentary is penalised by chrF precision already;
    # an answer several times longer than the reference is not a translation.
    longest = max(len(reference) for reference in grader["references"])
    if len(text) > 3 * longest + 80:
        return _result(False, "overlong", None, score)
    return _result(score >= grader.get("threshold", 0.5), "chrf", None, score)


# --- JSON ------------------------------------------------------------------

def parse_single_json(output):
    """The whole answer must be one JSON document, optionally inside one code fence.

    This mirrors the mission gateway, which refuses trailing data after the root
    value instead of executing the first object of a concatenated stream.
    """
    text = strip_reasoning(output)
    fenced = re.fullmatch(r"```(?:json)?\s*\n?(.*?)\n?```", text, flags=re.S)
    if fenced:
        text = fenced.group(1).strip()

    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError("duplicate key")
            result[key] = value
        return result

    def constant(_):
        raise ValueError("non-finite number")
    return json.loads(text, object_pairs_hook=pairs, parse_constant=constant)


def _fold(text):
    text = unicodedata.normalize("NFD", unicodedata.normalize("NFKC", text).casefold())
    return re.sub(r"[^0-9a-z]+", " ", "".join(c for c in text if unicodedata.category(c) != "Mn")).strip()


def json_equal(left, right, *, unordered=frozenset(), path="", fold=False):
    """Typed deep equality; ints and floats compare by value, booleans never as numbers.

    ``fold`` compares strings without case, accents or punctuation (labels), never numbers or types.
    """
    if isinstance(left, bool) or isinstance(right, bool):
        return type(left) is bool and type(right) is bool and left == right
    if isinstance(left, (int, float)) and isinstance(right, (int, float)):
        return math.isclose(left, right, rel_tol=1e-9, abs_tol=1e-9)
    if type(left) is not type(right):
        return False
    if isinstance(left, dict):
        return left.keys() == right.keys() and all(
            json_equal(v, right[k], unordered=unordered, path=f"{path}/{k}", fold=fold) for k, v in left.items())
    if isinstance(left, list):
        if len(left) != len(right):
            return False
        if path in unordered:
            remaining = list(right)
            for value in left:
                match = next((i for i, other in enumerate(remaining)
                              if json_equal(value, other, unordered=unordered, path=path + "/*", fold=fold)), None)
                if match is None:
                    return False
                remaining.pop(match)
            return True
        return all(json_equal(a, b, unordered=unordered, path=f"{path}/{i}", fold=fold) for i, (a, b) in enumerate(zip(left, right)))
    if isinstance(left, str):
        return _fold(left) == _fold(right) if fold else left.strip() == right.strip()
    return left == right


def grade_json(output, grader):
    try:
        value = parse_single_json(output)
    except (ValueError, RecursionError) as exc:
        return _result(False, f"invalid_json:{type(exc).__name__}")
    unordered = frozenset(grader.get("unordered", ()))
    for expected in grader["accept"]:
        if json_equal(value, expected, unordered=unordered, fold=grader.get("fold", False)):
            return _result(True, "json_equal")
    return _result(False, "json_differs")


def grade_tool_call(output, grader):
    """Hermes/Qwen style calls: every expected call present with equal arguments, nothing extra."""
    text = strip_reasoning(output)
    blocks = re.findall(r"<tool_call>\s*(.*?)\s*</tool_call>", text, flags=re.S)
    calls = []
    try:
        for block in blocks:
            calls.append(parse_single_json(block))
        if not blocks:
            value = parse_single_json(text)
            calls = value if isinstance(value, list) else [value]
    except (ValueError, RecursionError) as exc:
        return _result(False, f"invalid_call_json:{type(exc).__name__}")
    normalized = []
    for call in calls:
        if not isinstance(call, dict) or not isinstance(call.get("name"), str):
            return _result(False, "call_without_name")
        arguments = call.get("arguments", call.get("parameters", {}))
        if isinstance(arguments, str):
            try:
                arguments = json.loads(arguments)
            except ValueError:
                return _result(False, "arguments_not_json")
        normalized.append({"name": call["name"], "arguments": arguments})
    expected = grader["calls"]
    if len(normalized) != len(expected):
        return _result(False, "call_count", [c["name"] for c in normalized])
    remaining = list(expected)
    for call in normalized:
        match = next((i for i, other in enumerate(remaining) if json_equal(call, other)), None)
        if match is None:
            return _result(False, "call_differs", [c["name"] for c in normalized])
        remaining.pop(match)
    return _result(True, "calls_equal", [c["name"] for c in normalized])


def grade_mission_action(output, grader):
    """One mission action validated by the production argument contract, then compared."""
    try:
        value = parse_single_json(output)
    except (ValueError, RecursionError) as exc:
        return _result(False, f"invalid_json:{type(exc).__name__}")
    if not isinstance(value, dict) or set(value) != {"tool", "args"}:
        return _result(False, "not_a_tool_args_object")
    from agi_core.mission_protocol import validate_args
    try:
        validate_args(value["tool"], value["args"])
    except (ValueError, KeyError, TypeError) as exc:
        return _result(False, "contract_rejected:" + str(exc)[:80], value.get("tool"))
    for expected in grader["accept"]:
        if value["tool"] == expected["tool"] and json_equal(value["args"], expected["args"]):
            return _result(True, "action_equal", value["tool"])
    return _result(False, "action_differs", value["tool"])


def grade_pointer(output, grader):
    """An RFC 6901 pointer is right when it resolves to the requested value."""
    from agi_core.json_evidence import equal, pointer
    text = strip_reasoning(output).strip()
    # The skill is locating the field: a pointer wrapped in a code fence, quotes or
    # {"pointer": ...} is read as the pointer. Two different pointers are no answer.
    fenced = re.findall(r"```[A-Za-z0-9_-]*[ \t]*\n?(.*?)```", text, flags=re.S)
    if fenced:
        text = fenced[-1].strip()
    try:
        candidate = parse_single_json(text)
    except (ValueError, RecursionError):
        lines = [line.strip().strip("`\"'") for line in text.splitlines() if line.strip()]
        rooted = sorted({line for line in lines if line.startswith("/")})
        candidate = rooted[0] if len(rooted) == 1 else (lines[0] if len(lines) == 1 else None)
    if isinstance(candidate, dict) and set(candidate) == {"pointer"}:
        candidate = candidate["pointer"]
    if not isinstance(candidate, str) or "\n" in candidate:
        return _result(False, "not_a_pointer")
    try:
        value = pointer(grader["document"], candidate)
    except ValueError as exc:
        return _result(False, "unresolved:" + str(exc)[:60], candidate)
    # Value equality proves the pointer is usable; a location-specific question
    # additionally lists the only pointers that designate the requested field.
    allowed = grader.get("pointers")
    return _result(equal(value, grader["value"]) and (not allowed or candidate in allowed), "pointer_resolved", candidate)


def grade_evidence(output, grader):
    """A verify action is right when the production comparator accepts it and every
    required saved field is bound to a real receipt."""
    try:
        value = parse_single_json(output)
    except (ValueError, RecursionError) as exc:
        return _result(False, f"invalid_json:{type(exc).__name__}")
    if not isinstance(value, dict) or value.get("tool") != "verify" or not isinstance(value.get("args"), dict):
        return _result(False, "not_a_verify_action")
    checks = value["args"].get("checks")
    if not isinstance(checks, list) or not checks or not all(isinstance(check, dict) for check in checks):
        return _result(False, "no_check")
    # The mission executor accepts several checks on the same file as well as one check
    # holding every binding: both are graded alike, each check through the production comparator.
    from agi_core.json_evidence import compare_evidence
    from agi_core.mission_protocol import validate_checks
    bound, expressions = [], []
    try:
        validate_checks(checks)
        for check in checks:
            if check["kind"] != "json_evidence" or check["path"] != grader["path"]:
                return _result(False, "wrong_check_or_path")
            report = compare_evidence(grader["saved"], check["bindings"], grader["receipts"], check.get("expressions", ()))
            if not report["passed"]:
                return _result(False, "binding_or_expression_failed")
            bound += [binding["path"] for binding in report["bindings"]]
            expressions += list(check.get("expressions", ()))
    except (ValueError, KeyError, TypeError) as exc:
        return _result(False, "contract_rejected:" + str(exc)[:80])
    # Binding a whole array or object by equality also grounds its leaves.
    missing = sorted(path for path in grader["required_paths"]
                     if not any(path == b or path.startswith(b + "/") or b == "" for b in bound))
    if missing:
        return _result(False, "unbound_fields", missing)
    # A demanded quantity needs a predicate that holds on the saved file and
    # fails on each counterexample: a tautology such as ``1 == 1`` is not a check.
    from agi_core.json_predicates import evaluate_json_expression
    for counterexample in grader.get("quantity_counterexamples", ()):
        rejected = False
        for expression in expressions:
            try:
                rejected = rejected or evaluate_json_expression(expression, counterexample) is False
            except ValueError:
                rejected = True
        if not rejected:
            return _result(False, "missing_quantity_expression")
    return _result(True, "evidence_accepted")


# --- instruction following -------------------------------------------------

def _words(text):
    return re.findall(r"[0-9A-Za-zÀ-ÖØ-öø-ÿ]+(?:['’-][0-9A-Za-zÀ-ÖØ-öø-ÿ]+)*", text)


#: Function words of French: a unit without any of them is not a French sentence.
_FRENCH = re.compile(r"(?i)(?<![0-9A-Za-zÀ-ÿ])(?:le|la|les|l['’]|un|une|des|du|de|d['’]|et|à|au|aux|en|pour|par|sur|avec|dans|ton|ta|tes|"
                     r"ce|cet|cette|ces|qui|que|qu['’]|ne|n['’]|pas|plus|chaque|avant|après|sans|sous|entre|si|s['’]|se|tout|toute)(?![0-9A-Za-zÀ-ÿ])")


def grade_constraints(output, grader):
    """Programmatic checks of explicit formatting instructions, all of which must hold."""
    text = strip_reasoning(output).strip()
    if not text:
        return _result(False, "empty")
    failed = []
    for rule in grader["rules"]:
        kind = rule["kind"]
        if kind == "bullets":
            ok = len([l for l in text.splitlines() if re.match(r"\s*(?:[-*•]|\d+[.)])\s+\S", l)]) == rule["count"]
        elif kind == "max_words":
            ok = len(_words(text)) <= rule["count"]
        elif kind == "min_words":
            ok = len(_words(text)) >= rule["count"]
        elif kind == "sentences":
            ok = len([s for s in re.split(r"(?<=[.!?…])\s+", text) if s.strip()]) == rule["count"]
        elif kind == "include":
            ok = all(normalize_answer(w) in normalize_answer(text) for w in rule["words"])
        elif kind == "exclude":
            ok = not any(re.search(rf"(?<![0-9A-Za-zÀ-ÿ]){re.escape(w)}(?![0-9A-Za-zÀ-ÿ])", text, flags=re.I) for w in rule["words"])
        elif kind == "starts_with":
            ok = text.startswith(rule["text"])
        elif kind == "ends_with":
            ok = text.endswith(rule["text"])
        elif kind == "uppercase":
            ok = text == text.upper() and any(c.isalpha() for c in text)
        elif kind == "lowercase":
            ok = text == text.lower() and any(c.isalpha() for c in text)
        elif kind == "json_keys":
            try:
                value = parse_single_json(text)
                ok = isinstance(value, dict) and set(value) == set(rule["keys"])
            except (ValueError, RecursionError):
                ok = False
        elif kind == "lines":
            ok = len([l for l in text.splitlines() if l.strip()]) == rule["count"]
        elif kind == "content":
            # Each unit (bullet, line, JSON value) must be a real French sentence of a few words, not a placeholder.
            if rule["unit"] == "values":
                try:
                    value = parse_single_json(text)
                    units = [v for v in value.values()] if isinstance(value, dict) else []
                except (ValueError, RecursionError):
                    units = []
                units = [u if isinstance(u, str) else "" for u in units]
            elif rule["unit"] == "bullets":
                units = [re.sub(r"^\s*(?:[-*•]|\d+[.)])\s+", "", l) for l in text.splitlines() if re.match(r"\s*(?:[-*•]|\d+[.)])\s+\S", l)]
            else:
                units = [l for l in text.splitlines() if l.strip()][rule.get("skip", 0):]
            ok = bool(units) and all(len(_words(u)) >= rule.get("min_words", 4) and _FRENCH.search(u) for u in units)
        elif kind == "language_fr":
            ok = len(re.findall(r"\b(?:le|la|les|des|est|et|une|un|dans|pour|que|qui|avec|sur|pas|du)\b", text, flags=re.I)) >= rule.get("minimum", 3)
        else:
            raise ValueError(f"Unknown constraint: {kind}")
        if not ok:
            failed.append(kind)
    total = len(grader["rules"])
    return _result(not failed, "constraints", failed, (total - len(failed)) / total)


def grade_contains(output, grader):
    """Controlled-vocabulary check: every required term present, no forbidden term."""
    text = " " + normalize_answer(strip_reasoning(output)) + " "
    missing = [group for group in grader["required"]
               if not any(f" {normalize_answer(term)} " in text for term in group)]
    forbidden = [term for term in grader.get("forbidden", ()) if f" {normalize_answer(term)} " in text]
    total = max(1, len(grader["required"]))
    if len(strip_reasoning(output)) > grader.get("max_chars", 600):
        return _result(False, "overlong")
    unattached = []
    if grader.get("phrases"):
        # Each object as one phrase (its count and colour next to its noun), and in the given order when it matters:
        # with terms alone, swapped counts passed 104/104 items and an inverted relation 150/150 (review, 2026-11-12).
        plain = " " + re.sub(r"[^0-9a-zà-ÿ]+", " ", unicodedata.normalize("NFKC", strip_reasoning(output)).casefold()) + " "
        positions = []
        for pattern in grader["phrases"]:
            found = re.search(pattern, plain)
            if not found:
                unattached.append(pattern)
            positions.append(found.start() if found else -1)
        if not unattached and grader.get("ordered") and positions != sorted(positions):
            unattached.append("order")
    ok = not missing and not forbidden and not unattached
    return _result(ok, "terms", {"missing": missing, "forbidden": forbidden, "unattached": bool(unattached)},
                   (total - len(missing)) / total if not forbidden and not unattached else 0.0)


# --- executable answers ----------------------------------------------------

def extract_code(output, language="python"):
    """Last fenced block if any, else the raw answer."""
    text = strip_reasoning(output)
    blocks = re.findall(r"```[ \t]*([A-Za-z0-9_+-]*)[ \t]*\n(.*?)```", text, flags=re.S)
    if blocks:
        preferred = [body for lang, body in blocks if lang.lower() in {language, "py", "python3", "sql", "sqlite"} or not lang]
        return (preferred or [body for _, body in blocks])[-1].strip("\n")
    unfinished = re.search(r"```[ \t]*[A-Za-z0-9_+-]*[ \t]*\n(.*)\Z", text, flags=re.S)
    return (unfinished.group(1) if unfinished else text).strip("\n")


def _limits():
    """POSIX resource limits for generated programs; best effort elsewhere."""
    try:
        import resource
    except ImportError:
        return None

    def apply():
        resource.setrlimit(resource.RLIMIT_CPU, (20, 20))
        resource.setrlimit(resource.RLIMIT_FSIZE, (16 * 2 ** 20, 16 * 2 ** 20))
        try:
            resource.setrlimit(resource.RLIMIT_AS, (4 * 2 ** 30, 4 * 2 ** 30))
        except (ValueError, OSError):
            pass
        os.setsid()
    return apply


def run_python(program, timeout=20):
    """Run untrusted generated code in a throwaway directory and a bounded child process.

    This is process isolation, not a security sandbox: use it on disposable
    machines (the cloud examiners), never on a workstation holding private data.
    """
    if os.environ.get("AURORA_PROFESSOR_ALLOW_CODE_EXECUTION") != "1":
        raise RuntimeError("Executing generated code requires AURORA_PROFESSOR_ALLOW_CODE_EXECUTION=1 on a disposable machine")
    with tempfile.TemporaryDirectory(prefix="aurora_exam_") as folder:
        path = os.path.join(folder, "program.py")
        with open(path, "w", encoding="utf-8") as stream:
            stream.write(program)
        env = {"PATH": os.environ.get("PATH", ""), "HOME": folder, "TMPDIR": folder,
               "PYTHONDONTWRITEBYTECODE": "1", "PYTHONIOENCODING": "utf-8"}
        try:
            done = subprocess.run([sys.executable, "-I", path], cwd=folder, env=env, stdin=subprocess.DEVNULL,
                                  stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout,
                                  preexec_fn=_limits() if os.name != "nt" else None)
        except subprocess.TimeoutExpired:
            return False, "timeout", ""
        return done.returncode == 0, done.stderr.decode("utf-8", "replace")[-300:], done.stdout.decode("utf-8", "replace")


def _as_module(code):
    """Run the answer as an imported module: its ``if __name__ == "__main__":`` block (its own unittest.main(),
    a CLI ``sys.exit(main())``) must not end the process before the exam's tests."""
    return ("import sys as __aurora_sys, types as __aurora_types\n"
            "__aurora_module = __aurora_types.ModuleType('aurora_candidate')\n"
            "__aurora_module.__dict__.update({k: v for k, v in globals().items() if not k.startswith('__aurora')})\n"
            "__aurora_module.__name__ = 'aurora_candidate'\n"
            "__aurora_sys.modules['aurora_candidate'] = __aurora_module\n"
            f"exec(compile({code!r}, 'candidate.py', 'exec'), __aurora_module.__dict__)\n"
            "globals().update({k: v for k, v in __aurora_module.__dict__.items() if not k.startswith('__')})\n")


def grade_python_tests(output, grader):
    """Correct only if the tests ran to their last line: exit status 0 alone was satisfied by an answer that
    called sys.exit(0), raise SystemExit, os._exit(0) or unittest.main() before them (review, 2026-11-12)."""
    code = extract_code(output)
    if not code.strip():
        return _result(False, "no_code")
    entry = grader.get("entry_point")
    candidates = []
    if not entry or re.search(rf"^\s*def\s+{re.escape(entry)}\s*\(", code, flags=re.M):
        candidates.append(code)
    if grader.get("prompt"):
        candidates.append(grader["prompt"] + "\n" + code)
    if not candidates:
        candidates.append(code)
    last = "not_run"
    marker = "AURORA_TESTS_COMPLETED_" + secrets.token_hex(8)
    for candidate in candidates:
        ok, error, stdout = run_python(grader.get("setup", "") + "\n" + _as_module(candidate) + "\n\n" + grader["tests"]
                                       + f"\n\nprint({marker!r}, flush=True)\n", timeout=grader.get("timeout", 20))
        if ok and stdout.rstrip().endswith(marker):
            return _result(True, "tests_passed")
        if ok:
            last = "exited_before_the_tests_ended"
            continue
        last = error.strip().splitlines()[-1][:120] if error.strip() else "failed"
    return _result(False, "tests_failed:" + last)


def grade_python_output(output, grader):
    """Predicted program output must equal the output measured when the item was built."""
    text = strip_reasoning(output)
    fenced = re.fullmatch(r"```[a-z]*\s*\n?(.*?)\n?```", text.strip(), flags=re.S)
    if fenced:
        text = fenced.group(1)
    lines = [line.rstrip() for line in text.strip().splitlines()]
    expected = [line.rstrip() for line in grader["stdout"].strip().splitlines()]
    return _result(lines == expected, "stdout_equal", "\n".join(lines)[:120])


def run_sql(context, query, limit=200000):
    """Execute against a fresh in-memory SQLite database with a bounded step budget."""
    connection = sqlite3.connect(":memory:")
    try:
        steps = [0]

        def guard():
            steps[0] += 1
            return 1 if steps[0] > limit // 1000 else 0
        connection.set_progress_handler(guard, 1000)
        connection.executescript(context)
        cursor = connection.execute(query)
        rows = cursor.fetchmany(2000)
        return [tuple(row) for row in rows]
    finally:
        connection.close()


def _sql_rows_equal(left, right, ordered):
    def norm(row):
        return tuple(round(v, 6) if isinstance(v, float) else v for v in row)
    left, right = [norm(r) for r in left], [norm(r) for r in right]
    if ordered:
        return left == right
    return Counter(map(repr, left)) == Counter(map(repr, right))


def grade_sql(output, grader):
    query = extract_code(output, "sql").strip().rstrip(";")
    if not query:
        return _result(False, "no_query")
    if re.search(r"\b(?:attach|pragma|load_extension)\b", query, flags=re.I):
        return _result(False, "forbidden_statement")
    query = query.split(";")[0]
    try:
        rows = run_sql(grader["context"], query)
    except (sqlite3.Error, sqlite3.Warning) as exc:
        return _result(False, "sql_error:" + str(exc)[:80])
    expected = [tuple(row) for row in grader["rows"]]
    return _result(_sql_rows_equal(rows, expected, grader.get("ordered", False)), "rows_compared")


# --- LaTeX answers (MATH benchmark) ----------------------------------------

def last_boxed(text):
    start = text.rfind("\\boxed")
    if start < 0:
        start = text.rfind("\\fbox")
        if start < 0:
            return None
    brace = text.find("{", start)
    if brace < 0:
        return None
    depth = 0
    for index in range(brace, len(text)):
        if text[index] == "{":
            depth += 1
        elif text[index] == "}":
            depth -= 1
            if depth == 0:
                return text[brace + 1:index]
    return None


def normalize_latex(answer):
    """String normalization of the MATH benchmark (Hendrycks et al.), kept deterministic."""
    text = str(answer).strip().replace("\n", "").replace("\\!", "")
    text = text.replace("\\\\", "\\").replace("tfrac", "frac").replace("dfrac", "frac")
    text = text.replace("\\left", "").replace("\\right", "").replace("^{\\circ}", "").replace("^\\circ", "")
    text = text.replace("\\$", "").replace("$", "").replace("\\%", "").replace("%", "")
    text = re.sub(r"\\text\{\s*([^}]*)\}", r"\1", text)
    text = re.sub(r"\\(?:mbox|mathrm|textbf)\{\s*([^}]*)\}", r"\1", text)
    text = re.sub(r"(?<![0-9])\.(\d)", r"0.\1", text)
    if "=" in text and len(text.split("=")[0]) <= 2:
        text = text.split("=", 1)[1]
    text = re.sub(r"\\sqrt\s*(\w)", r"\\sqrt{\1}", text)
    text = re.sub(r"\\frac\s*(\d)\s*(\d)", r"\\frac{\1}{\2}", text)
    text = text.replace(" ", "").rstrip(".")
    simple = re.fullmatch(r"(-?\d+)/(\d+)", text)
    if simple:
        text = f"\\frac{{{simple.group(1)}}}{{{simple.group(2)}}}"
    if text == "0.5":
        text = "\\frac{1}{2}"
    return re.sub(r"^\\frac\{(-?\d+)\}\{1\}$", r"\1", text)


def grade_latex(output, grader):
    text = strip_reasoning(output)
    candidate = last_boxed(text)
    if candidate is None:
        marker = re.search(r"(?:r[ée]ponse\s+finale|final\s+answer)\s*:?\s*(.+)", text, flags=re.I)
        candidate = marker.group(1).strip() if marker else None
    if candidate is None:
        return _result(False, "no_final_answer")
    left, right = normalize_latex(candidate), normalize_latex(grader["answer"])
    if left == right:
        return _result(True, "latex_equal", candidate[:80])
    a, b = parse_numbers(left), parse_numbers(right)
    if a and b and re.fullmatch(r"[-+0-9.,]+", left) and re.fullmatch(r"[-+0-9.,]+", right):
        return _result(numbers_match(a, b, 1e-9, 1e-9), "latex_numeric", candidate[:80])
    return _result(False, "latex_differs", candidate[:80])


GRADERS = {
    "mcq": grade_mcq, "numeric": grade_numeric, "text": grade_text, "label": grade_label,
    "chrf": grade_chrf, "json": grade_json, "tool_call": grade_tool_call,
    "mission_action": grade_mission_action, "pointer": grade_pointer, "evidence": grade_evidence,
    "constraints": grade_constraints, "contains": grade_contains,
    "python_tests": grade_python_tests, "python_output": grade_python_output,
    "sql": grade_sql, "latex": grade_latex,
}


def grade(item, output):
    """Grade one model answer. Grader faults are raised, never turned into a score."""
    grader = item["grader"]
    if grader["type"] not in GRADERS:
        raise ValueError(f"Unknown grader type: {grader['type']}")
    return GRADERS[grader["type"]](output if isinstance(output, str) else "", grader)
