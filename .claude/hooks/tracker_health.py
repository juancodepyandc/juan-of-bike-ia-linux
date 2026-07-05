#!/usr/bin/env python
"""Aurora tracker health probe — detect stale work in flight.

Scans `.claude/agent-tracker/state.json` and reports tasks that have
been `in_progress` for longer than a threshold. This is the "suivi
parallèle" safety net: when several leads run in parallel, any one
that silently stalls (process died, hook never wrote a finish event,
external script wedged) shows up here so the user can decide to
restart, kill, or wait.

Output: aurora.tracker_health.v1 JSON.

   {
     "schema": "aurora.tracker_health.v1",
     "now": "2026-04-30T11:50:00Z",
     "stale_threshold_min": 30,
     "in_progress_count": 2,
     "stale_count": 1,
     "stale_tasks": [{"id": ..., "lead": ..., "started_at": ...,
                      "age_minutes": ..., "brief": ...}],
     "ok": true
   }

The ok flag stays true even if there are stale tasks — the watchdog
reports, it doesn't gate. Callers (dashboard, selftest) decide how
to render the verdict.

Usage:
    python .claude/hooks/tracker_health.py
    python .claude/hooks/tracker_health.py --stale-min 30 --pretty
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
TRACKER = REPO_ROOT / ".claude" / "agent-tracker" / "state.json"
DEFAULT_STALE_MIN = 30


def _now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _parse_iso(stamp: str | None) -> datetime | None:
    if not stamp:
        return None
    try:
        return datetime.fromisoformat(stamp.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        return None


def compute_health(state: dict, stale_threshold_min: int = DEFAULT_STALE_MIN,
                   now: datetime | None = None) -> dict:
    """Pure function: takes a tracker state dict, returns the health report."""
    now = now or datetime.now(timezone.utc)
    tasks = state.get("tasks") or []
    in_progress = [t for t in tasks if t.get("status") == "in_progress"]

    stale: list[dict] = []
    for t in in_progress:
        started = _parse_iso(t.get("started_at"))
        if not started:
            continue
        age_s = (now - started).total_seconds()
        age_min = age_s / 60.0
        if age_min < stale_threshold_min:
            continue
        stale.append({
            "id": t.get("id"),
            "lead": t.get("lead") or "unknown",
            "started_at": t.get("started_at"),
            "age_minutes": round(age_min, 1),
            "brief": t.get("brief") or "",
        })
    stale.sort(key=lambda x: -(x.get("age_minutes") or 0))
    return {
        "schema": "aurora.tracker_health.v1",
        "now": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "stale_threshold_min": stale_threshold_min,
        "in_progress_count": len(in_progress),
        "stale_count": len(stale),
        "stale_tasks": stale,
        "ok": True,
    }


def load_state(path: Path = TRACKER) -> dict:
    if not path.is_file():
        return {"tasks": []}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"tasks": []}


def archive_stale(state: dict, archive_after_min: int,
                  now: datetime | None = None,
                  dry_run: bool = True) -> dict:
    """Mark in_progress tasks older than archive_after_min as `blocked`
    with verdict 'auto-archived (stale Xh)'. Idempotent: a task already
    blocked is left alone. Returns a report of which task ids were
    archived (or would be archived in dry_run mode).

    Caller is responsible for persisting the modified state back to disk.
    """
    now = now or datetime.now(timezone.utc)
    archived: list[dict] = []
    for t in state.get("tasks") or []:
        if t.get("status") != "in_progress":
            continue
        started = _parse_iso(t.get("started_at"))
        if not started:
            continue
        age_min = (now - started).total_seconds() / 60.0
        if age_min < archive_after_min:
            continue
        archived.append({
            "id": t.get("id"),
            "lead": t.get("lead"),
            "age_minutes": round(age_min, 1),
            "brief": t.get("brief") or "",
        })
        if not dry_run:
            t["status"] = "blocked"
            t["finished_at"] = now.strftime("%Y-%m-%dT%H:%M:%SZ")
            verdict = (t.get("verdict") or "")
            tag = f"auto-archived (stale {age_min / 60:.1f}h)"
            t["verdict"] = (f"{verdict}; {tag}" if verdict else tag)[:240]
    return {
        "schema": "aurora.tracker_archive.v1",
        "now": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "archive_after_min": archive_after_min,
        "dry_run": dry_run,
        "archived_count": len(archived),
        "archived_tasks": archived,
    }


def save_state(state: dict, path: Path = TRACKER) -> bool:
    """Atomic write of tracker state. Returns True on success, False on
    soft failure. Never raises."""
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(state, indent=2, ensure_ascii=False),
                       encoding="utf-8")
        import os as _os
        _os.replace(tmp, path)
        return True
    except OSError:
        return False


def render_pretty(report: dict) -> str:
    lines = [
        f"Tracker health — {report['now']}",
        f"in_progress: {report['in_progress_count']} · "
        f"stale (>{report['stale_threshold_min']} min): {report['stale_count']}",
    ]
    for t in report["stale_tasks"]:
        lines.append(
            f"  - [{t['id']}] {t['lead']:<24} "
            f"{t['age_minutes']:>6.1f}m  {t['brief'][:60]}"
        )
    if not report["stale_tasks"]:
        lines.append("  (no stale tasks)")
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Aurora tracker health watchdog")
    parser.add_argument("--state", default=str(TRACKER))
    parser.add_argument("--stale-min", type=int, default=DEFAULT_STALE_MIN,
                        dest="stale_min")
    parser.add_argument("--archive-after-min", type=int, default=None,
                        dest="archive_after_min",
                        help="archive in_progress tasks older than N min "
                             "(default: dry-run preview only)")
    parser.add_argument("--apply", action="store_true",
                        help="actually persist archival changes (default: dry-run)")
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args()
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
    except (AttributeError, ValueError):
        pass

    state_path = Path(args.state)
    state = load_state(state_path)

    # Archival mode: write-side
    if args.archive_after_min is not None:
        archive_report = archive_stale(state, args.archive_after_min,
                                       dry_run=not args.apply)
        if args.apply and archive_report["archived_count"] > 0:
            save_state(state, state_path)
        if args.pretty:
            mode = "applied" if args.apply else "dry-run"
            sys.stdout.write(
                f"Archive ({mode}, threshold {args.archive_after_min} min): "
                f"{archive_report['archived_count']} task(s)\n"
            )
            for t in archive_report["archived_tasks"]:
                sys.stdout.write(
                    f"  - [{t['id']}] {t['lead']:<24} "
                    f"{t['age_minutes']:>6.1f}m  {t['brief'][:60]}\n"
                )
        else:
            sys.stdout.write(json.dumps(archive_report, indent=2, ensure_ascii=True) + "\n")
        return 0

    # Default: read-only health report
    report = compute_health(state, args.stale_min)
    if args.pretty:
        sys.stdout.write(render_pretty(report))
    else:
        sys.stdout.write(json.dumps(report, indent=2, ensure_ascii=True) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
