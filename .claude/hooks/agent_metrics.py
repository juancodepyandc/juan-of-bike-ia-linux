#!/usr/bin/env python
"""Aurora dispatch metrics — per-lead aggregates derived from the tracker.

Reads `.claude/agent-tracker/state.json` (live) +
`.claude/agent-tracker/history/tasks-*.json` (archived) and computes:

  - count of dispatches per lead
  - count by status (done / blocked / in_progress)
  - average duration (seconds) for closed tasks
  - last verdict (timestamp + status) per lead
  - global health (success rate across all leads)

Output: JSON. Designed for piping into the dashboard, the bridge endpoint,
and the self-test. Stdlib-only.

Usage:
    python .claude/hooks/agent_metrics.py
    python .claude/hooks/agent_metrics.py --pretty   # human-readable table
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean


REPO_ROOT = Path(__file__).resolve().parents[2]
TRACKER = REPO_ROOT / ".claude" / "agent-tracker" / "state.json"
HISTORY_DIR = REPO_ROOT / ".claude" / "agent-tracker" / "history"


def parse_iso(stamp: str | None) -> datetime | None:
    if not stamp:
        return None
    try:
        return datetime.fromisoformat(stamp.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        return None


def collect_tasks() -> list[dict]:
    tasks: list[dict] = []
    if TRACKER.is_file():
        try:
            data = json.loads(TRACKER.read_text(encoding="utf-8"))
            tasks.extend(data.get("tasks") or [])
        except (OSError, json.JSONDecodeError):
            pass
    if HISTORY_DIR.is_dir():
        for archive in sorted(HISTORY_DIR.glob("tasks-*.json")):
            try:
                data = json.loads(archive.read_text(encoding="utf-8"))
                tasks.extend(data.get("tasks") or [])
            except (OSError, json.JSONDecodeError):
                continue
    return tasks


def compute_metrics(tasks: list[dict]) -> dict:
    by_lead: dict[str, dict] = {}
    for t in tasks:
        lead = t.get("lead") or "unknown"
        bucket = by_lead.setdefault(lead, {
            "count": 0, "done": 0, "blocked": 0, "in_progress": 0,
            "durations_s": [], "last_finished_at": None,
            "last_status": None, "last_verdict": None,
        })
        bucket["count"] += 1
        status = t.get("status") or "unknown"
        if status in ("done", "blocked", "in_progress"):
            bucket[status] += 1
        started = parse_iso(t.get("started_at"))
        finished = parse_iso(t.get("finished_at"))
        if started and finished:
            bucket["durations_s"].append((finished - started).total_seconds())
        if finished and (
            bucket["last_finished_at"] is None
            or parse_iso(bucket["last_finished_at"]) < finished
        ):
            bucket["last_finished_at"] = t.get("finished_at")
            bucket["last_status"] = status
            bucket["last_verdict"] = (t.get("verdict") or "")[:120]

    leads_out: dict[str, dict] = {}
    for lead, b in by_lead.items():
        durations = b["durations_s"]
        leads_out[lead] = {
            "count": b["count"],
            "done": b["done"],
            "blocked": b["blocked"],
            "in_progress": b["in_progress"],
            "avg_duration_s": round(mean(durations), 2) if durations else None,
            "max_duration_s": round(max(durations), 2) if durations else None,
            "min_duration_s": round(min(durations), 2) if durations else None,
            "last_finished_at": b["last_finished_at"],
            "last_status": b["last_status"],
            "last_verdict": b["last_verdict"],
        }

    total = sum(b["count"] for b in by_lead.values())
    done = sum(b["done"] for b in by_lead.values())
    blocked = sum(b["blocked"] for b in by_lead.values())
    success_rate = round(done / max(1, done + blocked), 3) if (done or blocked) else None

    return {
        "schema": "aurora.metrics.v1",
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "total_dispatches": total,
        "global_done": done,
        "global_blocked": blocked,
        "global_success_rate": success_rate,
        "leads": leads_out,
    }


def render_pretty(metrics: dict) -> str:
    lines = [
        f"Aurora dispatch metrics — generated {metrics['generated_at']}",
        f"Total dispatches: {metrics['total_dispatches']}  "
        f"(done={metrics['global_done']}, blocked={metrics['global_blocked']}, "
        f"success={metrics['global_success_rate']})",
        "",
        f"{'lead':<32} {'#':>4} {'done':>4} {'blk':>4} {'avg':>6} {'last':>20}",
        "-" * 75,
    ]
    leads = sorted(
        metrics["leads"].items(),
        key=lambda kv: (-kv[1]["count"], kv[0]),
    )
    for name, m in leads:
        avg = f"{m['avg_duration_s']:.1f}s" if m["avg_duration_s"] is not None else "-"
        last = (m["last_finished_at"] or "-")[:19]
        lines.append(
            f"{name:<32} {m['count']:>4} {m['done']:>4} {m['blocked']:>4} "
            f"{avg:>6} {last:>20}"
        )
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Aurora dispatch metrics")
    parser.add_argument("--pretty", action="store_true",
                        help="Print human-readable table instead of JSON")
    args = parser.parse_args()
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
    except (AttributeError, ValueError):
        pass

    tasks = collect_tasks()
    metrics = compute_metrics(tasks)
    if args.pretty:
        sys.stdout.write(render_pretty(metrics))
    else:
        sys.stdout.write(json.dumps(metrics, indent=2, ensure_ascii=False) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
