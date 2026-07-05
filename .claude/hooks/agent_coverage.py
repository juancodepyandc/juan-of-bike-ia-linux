#!/usr/bin/env python
"""Aurora agent coverage report — declared vs dispatched.

Walks every `.claude/agents/<name>.md` and counts how many tracker
dispatches the agent has accumulated across `state.json` + history
archives. Surfaces 'dead' agents — declared in the architecture but
never actually used. The complement of agent_metrics.py (which only
reports agents that already have ≥1 dispatch).

Schema: aurora.coverage.v1.

   {
     "schema": "aurora.coverage.v1",
     "generated_at": "...",
     "total_declared": 38,
     "total_dispatched": 5,
     "coverage_pct": 13.2,
     "by_lead": [
       {"name": "3d-quality-rescuer", "role": "sub", "lead": "3d-lead",
        "dispatch_count": 5, "last_dispatch_at": "2026-04-30T..."},
       ...
     ],
     "dead": ["conversation-pipeline-tuner", "voice-tts-stt-tuner", ...]
   }

Usage:
    python .claude/hooks/agent_coverage.py
    python .claude/hooks/agent_coverage.py --pretty
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
AGENTS_DIR = REPO_ROOT / ".claude" / "agents"
TRACKER = REPO_ROOT / ".claude" / "agent-tracker" / "state.json"
HISTORY_DIR = REPO_ROOT / ".claude" / "agent-tracker" / "history"

FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)


def _parse_frontmatter(text: str) -> dict[str, str]:
    m = FRONTMATTER_RE.match(text)
    if not m:
        return {}
    out: dict[str, str] = {}
    for line in m.group(1).splitlines():
        if ":" not in line or line.lstrip().startswith("#"):
            continue
        k, _, v = line.partition(":")
        out[k.strip()] = v.strip()
    return out


def _declared_agents() -> list[str]:
    if not AGENTS_DIR.is_dir():
        return []
    out: list[str] = []
    for md in sorted(AGENTS_DIR.glob("*.md")):
        if md.name in {"README.md", "EXAMPLES.md"}:
            continue
        fm = _parse_frontmatter(md.read_text(encoding="utf-8"))
        name = fm.get("name") or md.stem
        out.append(name)
    return out


def _agent_role_from_state(state: dict) -> dict[str, tuple[str, str]]:
    """Returns {agent_name: (role, parent_lead)}.

    role ∈ {"orchestrator", "lead", "sub", "crosscut", "unknown"}
    parent_lead is the parent lead's name for sub-agents, otherwise "".
    """
    out: dict[str, tuple[str, str]] = {}
    leads = state.get("leads") or {}
    for lead_name, body in leads.items():
        out[lead_name] = ("lead", "")
        for sub in (body or {}).get("sub_agents") or []:
            out[sub] = ("sub", lead_name)
    for cc in state.get("crosscut") or []:
        if cc not in out:
            out[cc] = ("crosscut", "")
    if "aurora-orchestrator" not in out:
        out["aurora-orchestrator"] = ("orchestrator", "")
    return out


def _collect_dispatches() -> dict[str, list[dict]]:
    """Returns {agent_name: [task_entries]} across state.json + history."""
    by_agent: dict[str, list[dict]] = {}
    if TRACKER.is_file():
        try:
            data = json.loads(TRACKER.read_text(encoding="utf-8"))
            for t in data.get("tasks") or []:
                by_agent.setdefault(t.get("lead") or "?", []).append(t)
        except (OSError, json.JSONDecodeError):
            pass
    if HISTORY_DIR.is_dir():
        for archive in sorted(HISTORY_DIR.glob("tasks-*.json")):
            try:
                data = json.loads(archive.read_text(encoding="utf-8"))
                for t in data.get("tasks") or []:
                    by_agent.setdefault(t.get("lead") or "?", []).append(t)
            except (OSError, json.JSONDecodeError):
                continue
    return by_agent


def compute_coverage(state: dict | None = None) -> dict:
    if state is None:
        state = json.loads(TRACKER.read_text(encoding="utf-8")) if TRACKER.is_file() else {}
    declared = _declared_agents()
    role_map = _agent_role_from_state(state)
    by_agent = _collect_dispatches()

    rows: list[dict] = []
    dispatched = 0
    for name in declared:
        tasks = by_agent.get(name) or []
        last_at: str | None = None
        for t in tasks:
            ts = t.get("finished_at") or t.get("started_at")
            if ts and (last_at is None or ts > last_at):
                last_at = ts
        role, parent = role_map.get(name, ("unknown", ""))
        if tasks:
            dispatched += 1
        rows.append({
            "name": name,
            "role": role,
            "parent_lead": parent,
            "dispatch_count": len(tasks),
            "last_dispatch_at": last_at,
        })
    rows.sort(key=lambda r: (-r["dispatch_count"], r["name"]))
    dead = [r["name"] for r in rows if r["dispatch_count"] == 0]
    coverage_pct = round(100.0 * dispatched / max(1, len(declared)), 1)
    return {
        "schema": "aurora.coverage.v1",
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "total_declared": len(declared),
        "total_dispatched": dispatched,
        "total_dead": len(dead),
        "coverage_pct": coverage_pct,
        "by_lead": rows,
        "dead": dead,
    }


def render_pretty(report: dict) -> str:
    lines = [
        f"Aurora agent coverage — {report['generated_at']}",
        f"Declared: {report['total_declared']}  · "
        f"Dispatched: {report['total_dispatched']}  · "
        f"Dead: {report['total_dead']}  · "
        f"Coverage: {report['coverage_pct']}%",
        "",
        f"{'agent':<32} {'role':<12} {'parent':<24} {'#':>4}  {'last':>20}",
        "-" * 100,
    ]
    for r in report["by_lead"]:
        last = (r["last_dispatch_at"] or "-")[:19]
        lines.append(
            f"{r['name']:<32} {r['role']:<12} {(r['parent_lead'] or '-'):<24} "
            f"{r['dispatch_count']:>4}  {last:>20}"
        )
    if report["dead"]:
        lines.append("")
        lines.append(f"Dead agents ({len(report['dead'])}): "
                     + ", ".join(report["dead"][:8])
                     + (" ..." if len(report["dead"]) > 8 else ""))
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Aurora agent coverage report")
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args()
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
    except (AttributeError, ValueError):
        pass

    report = compute_coverage()
    if args.pretty:
        sys.stdout.write(render_pretty(report))
    else:
        sys.stdout.write(json.dumps(report, indent=2, ensure_ascii=True) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
