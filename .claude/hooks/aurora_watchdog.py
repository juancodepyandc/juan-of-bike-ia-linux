#!/usr/bin/env python
"""Aurora consolidated ops view — one terminal screen, four signals.

Designed as the user's daily ops glance. Bundles four read-only probes:

  1. Tracker health    (in_progress / stale tasks > N min)
  2. Recent dispatches (last K tracker entries with lead, status, verdict)
  3. Rescue trend      (promote rate, mean delta, axis lifts)
  4. Top runs          (best N runs by final score with progression)

All four are pure aggregators over existing state — no side effects,
no bridge restart, ~200ms total. The point is "show me everything
in flight without spinning up the dashboard". The dashboard remains
the durable visual; this is the CLI summary for shells & tunnels.

Schema: aurora.watchdog.v1.

Usage:
    python .claude/hooks/aurora_watchdog.py
    python .claude/hooks/aurora_watchdog.py --pretty
    python .claude/hooks/aurora_watchdog.py --stale-min 60 --recent 8 --top 5
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]


def _import_lib():
    """Soft-import the various aggregators. Each may fail independently."""
    sys.path.insert(0, str(REPO_ROOT / ".claude" / "hooks"))
    sys.path.insert(0, str(REPO_ROOT / "application" / "python-services"))
    refs = {}
    try:
        from tracker_health import compute_health, load_state  # type: ignore
        refs["compute_health"] = compute_health
        refs["load_tracker_state"] = load_state
    except ImportError:
        pass
    try:
        from agent_metrics import collect_tasks, compute_metrics  # type: ignore
        refs["collect_tasks"] = collect_tasks
        refs["compute_metrics"] = compute_metrics
    except ImportError:
        pass
    try:
        from score_history import compute_trend, load_events, top_runs  # type: ignore
        refs["compute_trend"] = compute_trend
        refs["load_events"] = load_events
        refs["top_runs"] = top_runs
    except ImportError:
        pass
    return refs


def collect_watchdog(stale_min: int = 30, recent: int = 6, top: int = 5) -> dict:
    refs = _import_lib()
    out: dict = {"schema": "aurora.watchdog.v1"}

    if "load_tracker_state" in refs and "compute_health" in refs:
        state = refs["load_tracker_state"]()
        out["health"] = refs["compute_health"](state, stale_min)
        out["recent_dispatches"] = list(reversed(state.get("tasks") or []))[:recent]
    else:
        out["health"] = None
        out["recent_dispatches"] = []

    if "compute_trend" in refs:
        out["trend"] = refs["compute_trend"]()
    else:
        out["trend"] = None

    if "top_runs" in refs:
        out["top_runs"] = refs["top_runs"](n=top)
    else:
        out["top_runs"] = []

    if "compute_metrics" in refs and "collect_tasks" in refs:
        out["metrics_summary"] = {
            "total_dispatches": refs["compute_metrics"](
                refs["collect_tasks"]()).get("total_dispatches", 0),
            "global_success_rate": refs["compute_metrics"](
                refs["collect_tasks"]()).get("global_success_rate"),
        }
    else:
        out["metrics_summary"] = None
    return out


def render_pretty(w: dict) -> str:
    lines = ["Aurora watchdog — consolidated ops view", "=" * 50, ""]

    health = w.get("health") or {}
    in_flight = health.get("in_progress_count", 0)
    stale = health.get("stale_count", 0)
    stale_marker = "OK" if stale == 0 else f"WARN ({stale} stale)"
    lines.append(f"[1/4] Tracker health: in_flight={in_flight}  {stale_marker}")
    for t in (health.get("stale_tasks") or [])[:5]:
        lines.append(f"      stale  [{t['lead']:<24}] "
                     f"{t['age_minutes']:>6.1f}m  {t['brief'][:60]}")
    lines.append("")

    metrics = w.get("metrics_summary") or {}
    success_rate = metrics.get("global_success_rate")
    success_str = f"{success_rate * 100:.1f}%" if success_rate is not None else "—"
    lines.append(f"[2/4] Dispatches: total={metrics.get('total_dispatches', 0)}  "
                 f"success={success_str}")
    for t in w.get("recent_dispatches", []):
        lines.append(
            f"      {t.get('finished_at', '?')[:19]}  "
            f"[{t.get('status', '?'):<11}] "
            f"{t.get('lead', '?'):<24}  "
            f"{(t.get('verdict') or '')[:60]}"
        )
    lines.append("")

    trend = w.get("trend") or {}
    if trend.get("total_runs"):
        pr = int((trend.get("promote_rate") or 0) * 100)
        md = trend.get("mean_delta", 0)
        lines.append(f"[3/4] Rescue trend: {trend['promoted_runs']}/{trend['total_runs']} promoted "
                     f"({pr}%) · mean delta {md:+} · best {trend.get('best_delta', 0):+}")
        axes = trend.get("axis_lifts") or {}
        if axes:
            lines.append("      axes lifted: " + ", ".join(
                f"{k}({v})" for k, v in list(axes.items())[:5]))
    else:
        lines.append("[3/4] Rescue trend: no events logged yet")
    lines.append("")

    runs = w.get("top_runs") or []
    lines.append(f"[4/4] Top {len(runs)} runs by final score:")
    for r in runs:
        lines.append(
            f"      {r['run_id']:<28} {r['subject_kind']:<12} "
            f"{r['initial_score']!s:>5} -> {r['final_score']!s:>5}  "
            f"(delta {r['score_delta']:+}, {r['events_count']} events)"
        )
    if not runs:
        lines.append("      (no runs)")
    lines.append("")

    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Aurora consolidated watchdog")
    parser.add_argument("--stale-min", type=int, default=30, dest="stale_min")
    parser.add_argument("--recent", type=int, default=6)
    parser.add_argument("--top", type=int, default=5)
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args()
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
    except (AttributeError, ValueError):
        pass

    w = collect_watchdog(args.stale_min, args.recent, args.top)
    if args.pretty:
        sys.stdout.write(render_pretty(w))
    else:
        sys.stdout.write(json.dumps(w, indent=2, ensure_ascii=True, default=str) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
