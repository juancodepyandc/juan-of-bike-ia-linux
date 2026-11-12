"""Item identity, content hashes and deterministic split assignment.

An item is a plain dict so it can cross machines as JSON:

    {"id": "gsm8k:test:12", "module": "academy", "skill": "academy.math_word",
     "subskill": "gsm8k", "lang": "en", "messages": [...], "target": "...",
     "grader": {"type": "numeric", "answer": "18"}, "max_new_tokens": 320}

``target`` exists only in training pools. Exam items carry a grader instead and
never leave the examining machine: only their content hashes do.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import unicodedata
import uuid
from pathlib import Path

ROLES = ("train", "mine", "dev", "diagnostic", "gate")
EXAM_ROLES = ("diagnostic", "gate")
#: Share of an exam family reserved for steering the curriculum. The remainder
#: is the reserve from which every cycle draws a fresh gate.
DIAGNOSTIC_PER_MILLE = 300


def normalize_text(text):
    """Aggressive normalization used only for duplicate and leak detection."""
    text = unicodedata.normalize("NFKC", str(text)).casefold()
    text = "".join(c for c in unicodedata.normalize("NFD", text) if unicodedata.category(c) != "Mn")
    return re.sub(r"[^0-9a-z]+", " ", text).strip()


def content_hash(messages):
    """Hash of what the model is asked, independent of template whitespace and case."""
    asked = " ".join(m["content"] for m in messages if m.get("role") == "user")
    return hashlib.sha256(normalize_text(asked).encode()).hexdigest()


def question_hash(text):
    """Hash of the bare source question, before any prompt template is applied.

    Train and exam prompts deliberately use different wording, so leak
    detection has to compare the underlying question, not the rendered prompt.
    """
    return hashlib.sha256(normalize_text(text).encode()).hexdigest()


def bucket(key, salt="", size=1000):
    """Stable pseudo-random bucket in [0, size) that does not depend on PYTHONHASHSEED."""
    value = hashlib.sha256(f"{salt}\x1f{key}".encode()).digest()
    return int.from_bytes(value[:8], "big") % size


def exam_role(key):
    """Partition one exam family into a steering part and a verification reserve."""
    return "diagnostic" if bucket(key, "aurora-exam-partition") < DIAGNOSTIC_PER_MILLE else "gate"


def rank(key, seed):
    """Deterministic order for sampling without replacement across machines."""
    return hashlib.sha256(f"{seed}\x1f{key}".encode()).hexdigest()


def take(items, count, seed):
    """Seeded sample that is identical on the training and examining machines."""
    ordered = sorted(items, key=lambda item: rank(item["id"], seed))
    return ordered if count is None else ordered[:max(0, count)]


def validate_item(item, *, training):
    """Fail early on malformed items instead of silently grading garbage."""
    for field in ("id", "module", "skill", "messages"):
        if not item.get(field):
            raise ValueError(f"Item is missing {field}: {str(item)[:120]}")
    if not isinstance(item["messages"], list) or item["messages"][-1].get("role") != "user":
        raise ValueError(f"Item {item['id']} must end with a user message")
    if training:
        if not isinstance(item.get("target"), str) or not item["target"].strip():
            raise ValueError(f"Training item {item['id']} has no target")
    elif not isinstance(item.get("grader"), dict) or "type" not in item["grader"]:
        raise ValueError(f"Exam item {item['id']} has no grader")
    return item


def suite_digest(items):
    """Order-independent identity of a set of items, including their graders."""
    lines = sorted(json.dumps({k: item.get(k) for k in ("id", "messages", "grader", "target")},
                              sort_keys=True, ensure_ascii=False) for item in items)
    return hashlib.sha256("\n".join(lines).encode()).hexdigest()


# --- small file helpers, kept local so a cloud bundle carries only this package ----

def atomic_json(path, data):
    """Write JSON through a temporary file and an atomic rename; NaN is refused."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    try:
        with temporary.open("w", encoding="utf-8") as stream:
            json.dump(data, stream, ensure_ascii=False, indent=2, allow_nan=False)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def read_json(path, default=None):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except FileNotFoundError:
        return default


def digest(data):
    return hashlib.sha256(json.dumps(data, sort_keys=True, ensure_ascii=False, allow_nan=False).encode()).hexdigest()


def file_hash(path):
    sha = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            sha.update(block)
    return sha.hexdigest()
