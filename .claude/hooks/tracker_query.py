#!/usr/bin/env python
"""Aurora tracker query — filter dispatches by lead / run_id / status / date.

Closes the audit chain: given a run_id, return every tracker entry that
touched it (the 3d-lead pipeline entry + every 3d-quality-rescuer entry,
linked by metadata.run_id). Or filter by lead alone, or by status, or
since a given ISO timestamp.

Walks state.json + history archives.

Schema: aurora.tracker_query.v1.

Usage:
    python .claude/hooks/tracker_query.py --run-id cat5_jellopus_mesh
    python .claude/hooks/tracker_query.py --lead 3d-quality-rescuer --status done
    python .claude/hooks/tracker_query.py --since 2026-04-30T00:00:00Z --pretty
    python .claude/hooks/tracker_query.py --run-id cat5 --limit 20
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
TRACKER = REPO_ROOT / ".claude" / "agent-tracker" / "state.json"
HISTORY_DIR = REPO_ROOT / ".claude" / "agent-tracker" / "history"


def _parse_iso(stamp: str | None) -> datetime | None:
    if not stamp:
        return None
    try:
        return datetime.fromisoformat(stamp.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        return None


def _all_tasks(tracker_path: Path = TRACKER) -> list[dict]:
    out: list[dict] = []
    if tracker_path.is_file():
        try:
            data = json.loads(tracker_path.read_text(encoding="utf-8"))
            out.extend(data.get("tasks") or [])
        except (OSError, json.JSONDecodeError):
            pass
    if HISTORY_DIR.is_dir():
        for archive in sorted(HISTORY_DIR.glob("tasks-*.json")):
            try:
                data = json.loads(archive.read_text(encoding="utf-8"))
                out.extend(data.get("tasks") or [])
            except (OSError, json.JSONDecodeError):
                continue
    return out


def query(*, run_id: str | None = None, lead: str | None = None,
          status: str | None = None, since: str | None = None,
          limit: int | None = None,
          tasks: list[dict] | None = None) -> dict:
    """Return tracker entries matching the conjunction of all provided
    filters. AND-semantics across filters; OR is not supported on
    purpose (callers can union two queries themselves)."""
    pool = tasks if tasks is not None else _all_tasks()
    since_dt = _parse_iso(since) if since else None
    out: list[dict] = []
    for t in pool:
        if lead and t.get("lead") != lead:
            continue
        if status and t.get("status") != status:
            continue
        if run_id:
            meta_rid = (t.get("metadata") or {}).get("run_id")
            if meta_rid != run_id and run_id not in (t.get("brief") or ""):
                continue
        if since_dt:
            ref = _parse_iso(t.get("finished_at") or t.get("started_at"))
            if not ref or ref < since_dt:
                continue
        out.append(t)
    # Newest first.
    out.sort(key=lambda t: (t.get("finished_at") or t.get("started_at") or ""), reverse=True)
    if limit is not None and limit > 0:
        out = out[:limit]
    return {
        "schema": "aurora.tracker_query.v1",
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "filters": {
            "run_id": run_id, "lead": lead,
            "status": status, "since": since, "limit": limit,
        },
        "match_count": len(out),
        "tasks": out,
    }


def render_pretty(result: dict) -> str:
    f = result["filters"]
    filt_str = ", ".join(f"{k}={v}" for k, v in f.items() if v is not None) or "(no filters)"
    lines = [
        f"Tracker query — {result['generated_at']}",
        f"Filters: {filt_str}",
        f"Matches: {result['match_count']}",
        "",
    ]
    for t in result["tasks"]:
        meta = t.get("metadata") or {}
        rid = meta.get("run_id") or "—"
        delta = meta.get("score_delta")
        delta_str = f"Δ{delta:+}" if isinstance(delta, (int, float)) else ""
        lines.append(
            f"  [{(t.get('finished_at') or '?')[:19]}] "
            f"{t.get('status', '?'):<11} {t.get('lead', '?'):<24} "
            f"run_id={rid:<24} {delta_str:<8} "
            f"{(t.get('verdict') or '')[:60]}"
        )
    if not result["tasks"]:
        lines.append("  (no matches)")
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Aurora tracker query")
    parser.add_argument("--run-id", default=None, dest="run_id")
    parser.add_argument("--lead", default=None)
    parser.add_argument("--status", choices=["in_progress", "done", "blocked"],
                        default=None)
    parser.add_argument("--since", default=None,
                        help="ISO timestamp (e.g. 2026-04-30T00:00:00Z)")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args()
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
    except (AttributeError, ValueError):
        pass

    result = query(
        run_id=args.run_id, lead=args.lead, status=args.status,
        since=args.since, limit=args.limit,
    )
    if args.pretty:
        sys.stdout.write(render_pretty(result))
    else:
        sys.stdout.write(json.dumps(result, indent=2, ensure_ascii=True) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
