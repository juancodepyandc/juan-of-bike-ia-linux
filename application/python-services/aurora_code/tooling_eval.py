#!/usr/bin/env python3
"""Aurora Code WS14 tooling evaluator.

Creates isolated venvs outside application/.venv, installs approved tools,
measures an A/B fixture, keeps useful tools and removes useless ones.
"""

from __future__ import annotations

import json
import os
import pathlib
import re
import shutil
import subprocess
import sys
import time
from difflib import SequenceMatcher
from typing import Any


SCHEMA = "aurora.code.tooling-eval/1"
APPROVED = {
    "pypi": {
        "python-slugify": "8.0.4",
    },
}
REACT_ACTIONS = ["search_pkg", "install_dep", "run_tests"]


def workspace_root() -> pathlib.Path:
    return pathlib.Path(__file__).resolve().parents[2]


def default_venv_root() -> pathlib.Path:
    override = os.environ.get("AURORA_CODE_TOOLING_VENVS", "").strip()
    if override:
        return pathlib.Path(override).expanduser()
    return pathlib.Path.home() / ".local" / "share" / "auroraia" / "venvs" / "code-auto-tools"


def app_venv_path() -> pathlib.Path:
    return workspace_root() / ".venv"


def tail(text: str, limit: int = 1200) -> str:
    return text[-limit:] if len(text) > limit else text


def slug(text: str) -> str:
    safe = re.sub(r"[^a-zA-Z0-9_.-]+", "-", text.strip().lower())
    safe = re.sub(r"-{2,}", "-", safe).strip("-._")
    return safe[:80] or "tool"


def run(cmd: list[str], cwd: pathlib.Path | None = None, timeout: int = 120) -> dict[str, Any]:
    started = time.time()
    try:
        proc = subprocess.run(
            cmd,
            cwd=str(cwd) if cwd else None,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
        return {
            "ok": proc.returncode == 0,
            "code": proc.returncode,
            "stdout": proc.stdout or "",
            "stderr": proc.stderr or "",
            "seconds": round(time.time() - started, 3),
            "command": " ".join(cmd),
        }
    except subprocess.TimeoutExpired as exc:
        return {
            "ok": False,
            "code": 124,
            "stdout": exc.stdout or "",
            "stderr": (exc.stderr or "") + "\ntimeout",
            "seconds": round(time.time() - started, 3),
            "command": " ".join(cmd),
        }


def venv_python(venv: pathlib.Path) -> pathlib.Path:
    return venv / ("Scripts/python.exe" if os.name == "nt" else "bin/python")


def naive_slugify(text: str) -> str:
    value = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return re.sub(r"-{2,}", "-", value)


def score(actual: str, expected: str) -> int:
    if actual == expected:
        return 100
    return round(100 * SequenceMatcher(None, actual, expected).ratio())


def fixture_for(name: str | None) -> tuple[str, str]:
    if name == "slugify_no_gain":
        return "clean-product-2026", "clean-product-2026"
    return "Crème brûlée — Été 2026!", "creme-brulee-ete-2026"


def run_slugify_tool(py: pathlib.Path, text: str) -> dict[str, Any]:
    code = "import sys\nfrom slugify import slugify\nprint(slugify(sys.argv[1]))"
    result = run([str(py), "-c", code, text], timeout=30)
    result["value"] = (result["stdout"] or "").strip()
    return result


def blocked_report(candidate: dict[str, Any], reason: str) -> dict[str, Any]:
    return {
        "id": str(candidate.get("id") or "candidate"),
        "registry": str(candidate.get("registry") or ""),
        "packageName": str(candidate.get("packageName") or ""),
        "version": candidate.get("version"),
        "venvPath": None,
        "baselineScore": 0,
        "toolScore": 0,
        "improvement": 0,
        "decision": "blocked",
        "reason": reason,
        "removed": True,
        "actions": [],
    }


def evaluate_candidate(candidate: dict[str, Any], root: pathlib.Path, timeout_s: int) -> dict[str, Any]:
    registry = str(candidate.get("registry") or "")
    package = str(candidate.get("packageName") or "")
    version = str(candidate.get("version") or APPROVED.get(registry, {}).get(package) or "")
    candidate_id = str(candidate.get("id") or f"{registry}-{package}")
    if registry not in APPROVED or package not in APPROVED[registry]:
        return blocked_report(candidate, "Outil absent du registre approuve WS14.")
    if version != APPROVED[registry][package]:
        return blocked_report(candidate, "Version non approuvee pour evaluation reproductible.")

    venv = root / slug(candidate_id)
    if venv.exists():
        shutil.rmtree(venv)
    root.mkdir(parents=True, exist_ok=True)

    text, expected = fixture_for(candidate.get("scenario"))
    baseline_value = naive_slugify(text)
    baseline_score = score(baseline_value, expected)
    create = run([sys.executable, "-m", "venv", str(venv)], timeout=60)
    if not create["ok"]:
        shutil.rmtree(venv, ignore_errors=True)
        return {
            **blocked_report(candidate, "Creation du venv isole impossible."),
            "decision": "unavailable",
            "stderrTail": tail(create["stderr"]),
        }

    py = venv_python(venv)
    install_spec = f"{package}=={version}"
    install = run([
        str(py),
        "-m",
        "pip",
        "install",
        "--disable-pip-version-check",
        "--no-input",
        install_spec,
    ], timeout=timeout_s)
    if not install["ok"]:
        shutil.rmtree(venv, ignore_errors=True)
        return {
            **blocked_report(candidate, "Installation pip impossible dans le venv isole."),
            "decision": "unavailable",
            "installCommand": install["command"],
            "stdoutTail": tail(install["stdout"]),
            "stderrTail": tail(install["stderr"]),
        }

    tool = run_slugify_tool(py, text)
    tool_score = score(str(tool.get("value") or ""), expected) if tool["ok"] else 0
    improvement = tool_score - baseline_score
    min_gain = int(candidate.get("minGain") or 1)
    keep = improvement >= min_gain

    marker = {
        "schemaVersion": SCHEMA,
        "candidate": candidate_id,
        "package": package,
        "version": version,
        "baselineScore": baseline_score,
        "toolScore": tool_score,
        "improvement": improvement,
        "keptAt": time.time() if keep else None,
    }
    if keep:
        (venv / "aurora_tooling_eval.json").write_text(json.dumps(marker, indent=2), encoding="utf-8")
    else:
        shutil.rmtree(venv, ignore_errors=True)

    return {
        "id": candidate_id,
        "registry": registry,
        "packageName": package,
        "version": version,
        "venvPath": str(venv) if keep else None,
        "baselineScore": baseline_score,
        "toolScore": tool_score,
        "improvement": improvement,
        "decision": "kept" if keep else "removed",
        "reason": "Gain A/B reel mesure." if keep else "Gain A/B insuffisant; outil retire proprement.",
        "removed": not keep,
        "installCommand": install["command"],
        "actions": REACT_ACTIONS,
        "stdoutTail": tail((install["stdout"] or "") + "\n" + (tool.get("stdout") or "")),
        "stderrTail": tail((install["stderr"] or "") + "\n" + (tool.get("stderr") or "")),
    }


def build_report(candidates: list[dict[str, Any]], timeout_ms: int) -> dict[str, Any]:
    root = default_venv_root()
    timeout_s = max(15, min(180, int(timeout_ms / 1000)))
    reports = [evaluate_candidate(candidate, root, timeout_s) for candidate in candidates]
    return {
        "schemaVersion": SCHEMA,
        "createdAt": int(time.time() * 1000),
        "venvRoot": str(root),
        "appVenvPath": str(app_venv_path()),
        "appVenvInstallForbidden": True,
        "candidates": reports,
    }


def proof_candidates() -> list[dict[str, Any]]:
    return [
        {
            "id": "proof-python-slugify-kept",
            "registry": "pypi",
            "packageName": "python-slugify",
            "version": "8.0.4",
            "scenario": "slugify_gain",
            "reason": "Preuve DoD: slug Unicode meilleur que baseline naive.",
            "minGain": 5,
        },
        {
            "id": "proof-python-slugify-removed",
            "registry": "pypi",
            "packageName": "python-slugify",
            "version": "8.0.4",
            "scenario": "slugify_no_gain",
            "reason": "Preuve DoD: outil inutile quand la baseline suffit.",
            "minGain": 5,
        },
    ]


def main() -> int:
    if len(sys.argv) > 1 and sys.argv[1] == "--proof":
        report = build_report(proof_candidates(), 120_000)
        print(json.dumps(report, ensure_ascii=False))
        return 0 if all(c["decision"] in ("kept", "removed") for c in report["candidates"]) else 2

    try:
        payload = json.loads(sys.stdin.read() or "{}")
    except Exception as exc:
        print(json.dumps({"schemaVersion": SCHEMA, "error": f"JSON invalide: {exc}"}))
        return 2
    candidates = payload.get("candidates") or []
    if not isinstance(candidates, list) or not candidates:
        print(json.dumps({"schemaVersion": SCHEMA, "error": "candidates requis"}))
        return 2
    timeout_ms = int(payload.get("timeoutMs") or payload.get("timeout_ms") or 90_000)
    report = build_report(candidates, timeout_ms)
    print(json.dumps(report, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
