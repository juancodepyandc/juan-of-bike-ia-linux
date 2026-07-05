#!/usr/bin/env python
"""Aurora /aurora-handoff — generate a single-page HANDOFF.md summarizing the
current state of the system for the next contributor (or future-you).

Pulls together:
  - HEAD commit + branch + delta vs origin/main
  - Last N commits with v-tagged headlines
  - Snapshot of /aurora-self-test gates (just runs it, copies the output)
  - In-flight + recent done tasks from the tracker
  - 3D run index (grouped runs + standalones)
  - Active scheduled /loop jobs (best-effort)
  - Pending todos surfaced from the task list

Writes to HANDOFF.md at repo root. Idempotent — safe to regenerate at any
time. Designed to be the first thing the next session reads.

Usage:
    python .claude/hooks/aurora_handoff.py
    python .claude/hooks/aurora_handoff.py --stdout   # print, don't write
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
HANDOFF = REPO_ROOT / "HANDOFF.md"


def run(cmd: list[str], timeout: int = 30) -> tuple[int, str, str]:
    proc = subprocess.run(
        cmd, cwd=str(REPO_ROOT),
        capture_output=True, timeout=timeout, check=False,
    )
    out = (proc.stdout or b"").decode("utf-8", errors="replace")
    err = (proc.stderr or b"").decode("utf-8", errors="replace")
    return proc.returncode, out, err


def section_header() -> str:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    return (
        "# AuroraIA-v2 — handoff snapshot\n\n"
        f"_Generated {now} by `python .claude/hooks/aurora_handoff.py` "
        f"(`/aurora-handoff`)._\n\n"
        "**Read this first** when picking up the project. Regenerate after "
        "every significant work session.\n\n"
    )


def section_head() -> str:
    rc, out, _ = run(["git", "rev-parse", "--abbrev-ref", "HEAD"])
    branch = out.strip() if rc == 0 else "?"
    rc2, out2, _ = run(["git", "rev-parse", "--short=7", "HEAD"])
    sha = out2.strip() if rc2 == 0 else "?"
    rc3, out3, _ = run(["git", "log", "-1", "--pretty=format:%s"])
    subject = out3.strip() if rc3 == 0 else "?"
    rc4, out4, _ = run(["git", "log", "-1", "--pretty=format:%cI"])
    date = out4.strip() if rc4 == 0 else "?"

    rc_fetch, _, _ = run(["git", "fetch", "origin", "main"], timeout=20)
    if rc_fetch == 0:
        rc_anc, _, _ = run([
            "git", "merge-base", "--is-ancestor", "HEAD", "origin/main",
        ])
        pushed = "yes" if rc_anc == 0 else "**NO — push first**"
    else:
        pushed = "?"

    return (
        "## HEAD\n\n"
        f"- branch: `{branch}`\n"
        f"- HEAD:   `{sha}` — {subject}\n"
        f"- date:   {date}\n"
        f"- pushed to origin/main: {pushed}\n\n"
    )


def section_recent_commits(n: int = 12) -> str:
    rc, out, _ = run([
        "git", "log", f"-{n}",
        "--pretty=format:%h\t%cs\t%s",
    ])
    if rc != 0 or not out.strip():
        return "## Recent commits\n\n_(git log failed)_\n\n"
    lines = ["## Recent commits", ""]
    for raw in out.splitlines():
        try:
            sha, date, subject = raw.split("\t", 2)
        except ValueError:
            continue
        m = re.match(r"^(v\d+[a-z]+(?:-\w+)?)\s*[:—-]\s*(.+)$", subject)
        if m:
            lines.append(f"- `{sha}` _{date}_ **{m.group(1)}** — {m.group(2)}")
        else:
            lines.append(f"- `{sha}` _{date}_ {subject}")
    lines.append("")
    return "\n".join(lines)


def section_self_test() -> str:
    # Skip when invoked from a selftest gate to avoid infinite recursion
    # (handoff → selftest → gate_handoff_render → handoff → …).
    import os as _os
    if _os.environ.get("AURORA_HANDOFF_SKIP_SELFTEST") == "1":
        return (
            "## Self-test snapshot\n\n"
            "_(skipped: handoff invoked from selftest gate)_\n\n"
        )
    script = REPO_ROOT / ".claude" / "hooks" / "aurora_selftest.py"
    if not script.is_file():
        return "## Self-test\n\n_(aurora_selftest.py missing)_\n\n"
    rc, out, _ = run([sys.executable, str(script)], timeout=300)
    verdict = "PASS" if "PASS" in out else "FAIL" if "FAIL" in out else "?"
    body_lines = [
        "## Self-test snapshot",
        "",
        f"verdict: **{verdict}** (return code {rc})",
        "",
        "```",
    ]
    # Keep just the gate lines + summary.
    for line in out.splitlines():
        if line.startswith("[aurora-self-test]") or line.lstrip().startswith("["):
            body_lines.append(line)
    body_lines.append("```")
    body_lines.append("")
    return "\n".join(body_lines)


def section_tracker() -> str:
    tracker = REPO_ROOT / ".claude" / "agent-tracker" / "state.json"
    if not tracker.is_file():
        return "## Agent tracker\n\n_(no tracker)_\n\n"
    try:
        state = json.loads(tracker.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return "## Agent tracker\n\n_(tracker unreadable)_\n\n"
    tasks = state.get("tasks") or []
    in_flight = [t for t in tasks if t.get("status") == "in_progress"]
    done = [t for t in tasks if t.get("status") == "done"]
    blocked = [t for t in tasks if t.get("status") == "blocked"]

    lines = [
        "## Agent tracker",
        "",
        f"- schema: `{state.get('schema_version', '?')}`",
        f"- last_commit: `{state.get('last_commit', '—')}`",
        f"- session_goal: {state.get('session_goal', '—')}",
        f"- tasks: {len(in_flight)} in-flight, {len(done)} done, {len(blocked)} blocked",
        "",
    ]
    if in_flight:
        lines.append("### In-flight\n")
        for t in in_flight[-5:]:
            lines.append(
                f"- `{t.get('id', '?')}` **{t.get('lead', '?')}** — "
                f"{(t.get('brief') or '')[:80]}"
            )
        lines.append("")
    if done:
        lines.append("### Recent done\n")
        for t in done[-5:]:
            lines.append(
                f"- `{t.get('id', '?')}` **{t.get('lead', '?')}** — "
                f"{(t.get('verdict') or 'ok')[:80]}"
            )
        lines.append("")
    if blocked:
        lines.append("### Blocked\n")
        for t in blocked[-5:]:
            lines.append(
                f"- `{t.get('id', '?')}` **{t.get('lead', '?')}** — "
                f"{(t.get('verdict') or '?')[:80]}"
            )
        lines.append("")
    return "\n".join(lines)


def section_3d_runs() -> str:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent
                          / "application" / "python-services"))
    try:
        from mesh_run_index import index_runs  # type: ignore
    except ImportError:
        return "## 3D runs\n\n_(mesh_run_index unavailable)_\n\n"
    target = REPO_ROOT / "application" / "output" / "3d"
    idx = index_runs(target)
    if not idx.get("ok"):
        return "## 3D runs\n\n_(index failed)_\n\n"
    runs = idx.get("runs") or []
    standalones = idx.get("standalones") or []
    lines = [
        "## 3D runs",
        "",
        f"- {len(runs)} grouped runs · {len(standalones)} standalone files",
        "",
    ]
    for run in runs[:5]:
        files = run.get("files") or []
        roles = sorted({f.get("role", "?") for f in files})
        lines.append(
            f"- **{run['run_id']}** ({run.get('latest_mtime_iso', '?')[:19]}) — "
            f"{len(files)} files, roles: {', '.join(roles)}"
        )
    if standalones:
        baked = [s for s in standalones if s.get("role") in ("baked", "reshaped", "rescue")]
        if baked:
            lines.append("")
            lines.append(f"_Rescued meshes ({len(baked)}):_ "
                         + ", ".join(f"`{s['name']}`" for s in baked[:5])
                         + (" …" if len(baked) > 5 else ""))
    lines.append("")
    return "\n".join(lines)


def section_workflows() -> str:
    return (
        "## Useful commands\n\n"
        "```bash\n"
        "/aurora-self-test          # 17 gates, ~9s\n"
        "/aurora-ship-it            # 4 gates: selftest + TS + tree clean + pushed\n"
        "/aurora-validate           # frontmatter + tracker + KNOWN_AGENTS\n"
        "/aurora-test               # 15 hook unit tests, ~0.7s\n"
        "/aurora-dashboard          # render dashboard.html\n"
        "/aurora-handoff            # regenerate this file\n"
        "/aurora-route-test \"<3D prompt>\"  # which pipeline?\n"
        "/aurora-mesh-validate \"<glb>\" \"<prompt>\"  # autonomous validate\n"
        "/aurora-mesh-rescue ...    # full rescue chain\n"
        "python bridge_doctor.py --check-only   # is the bridge alive?\n"
        "python bridge_doctor.py    # respawn local bridge\n"
        "```\n\n"
    )


def section_watchdog() -> str:
    """Embed the live consolidated ops snapshot — tracker health + rescue
    trend + top runs. Read-only; ~200ms; degrades gracefully if any
    aggregator is missing."""
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    try:
        from aurora_watchdog import collect_watchdog  # type: ignore
    except ImportError:
        return ""
    try:
        w = collect_watchdog(stale_min=30, recent=0, top=5)
    except Exception:  # noqa: BLE001 — handoff must always render
        return ""

    lines = ["## Live ops snapshot", ""]
    health = w.get("health") or {}
    if health:
        in_flight = health.get("in_progress_count", 0)
        stale = health.get("stale_count", 0)
        marker = "OK" if stale == 0 else f"**WARN: {stale} stale**"
        lines.append(f"- tracker: `{in_flight}` in-flight · `{stale}` stale "
                     f"(>{health.get('stale_threshold_min', 30)} min) · {marker}")
        for t in (health.get("stale_tasks") or [])[:3]:
            lines.append(f"  - **{t['lead']}** {t['age_minutes']:.1f}m  "
                         f"`{t['brief'][:60]}`")

    metrics = w.get("metrics_summary") or {}
    if metrics:
        sr = metrics.get("global_success_rate")
        sr_str = f"{sr * 100:.1f}%" if sr is not None else "—"
        lines.append(f"- dispatches: `{metrics.get('total_dispatches', 0)}` total · "
                     f"global success `{sr_str}`")

    trend = w.get("trend") or {}
    if trend.get("total_runs"):
        pr = int((trend.get("promote_rate") or 0) * 100)
        md = trend.get("mean_delta", 0)
        axes = trend.get("axis_lifts") or {}
        axes_str = ", ".join(f"{k}({v})" for k, v in list(axes.items())[:3]) if axes else "—"
        lines.append(
            f"- rescue trend: `{trend['promoted_runs']}/{trend['total_runs']}` promoted "
            f"(`{pr}%`) · mean delta `{md:+}` · axes lifted: `{axes_str}`"
        )

    runs = w.get("top_runs") or []
    if runs:
        lines.append("")
        lines.append("### Top runs by final score")
        lines.append("")
        for r in runs[:5]:
            initial = r.get("initial_score")
            final = r.get("final_score")
            delta = r.get("score_delta", 0)
            lines.append(
                f"- `{r['run_id']}` ({r.get('subject_kind', '?')}): "
                f"{initial!s} → **{final!s}** (Δ {delta:+}, "
                f"{r.get('events_count', 0)} events)"
            )
    lines.append("")
    return "\n".join(lines)


def section_known_state() -> str:
    return (
        "## What's reliably true today\n\n"
        "- **5 OOD categories at Meshy-grade**: Cat 1 91.3 · Cat 2 93.4 · Cat 3 99.5 · "
        "Cat 4 99.4 · Cat 5 98.8 — average **96.5/100** all watertight, files under "
        "`application/output/3d/v80x_*/`. Achieved via the 6-tour closure: manifold rescue "
        "stage, kind-aware reshape (max_distortion 0.55 for organic kinds), 4 articulated "
        "motion presets, motion vocab 22 → 42 fixtures.\n"
        "- **38 agents** Opus 4.7 (1 master + 11 leads + 24 sub + 2 crosscut), see `AGENT_SYSTEM.md`.\n"
        "- **6 hooks** auto-track every Agent dispatch in `.claude/agent-tracker/state.json`.\n"
        "- **Python tooling writes tracker entries** via `tracker_helper.record_dispatch()`\n"
        "  with `metadata` (run_id, kind, score_delta, final_mesh) — auto_rescue → "
        "`3d-quality-rescuer`, full pipeline → `3d-lead`.\n"
        "- **33-gate self-test** + **4-gate ship-it**, **32 TS tests**, ~140 Python tests.\n"
        "- **19 bridge endpoints** for 3D toolchain (`/api/3d/*` × 14) + agents introspection.\n"
        "- **32 slash commands** with a script-resolution linter.\n"
        "- **TS client** `application/src/services/meshRescue.ts` at full parity.\n"
        "- **Detect → surface → self-heal watchdog**: `tracker_health` flags stale work, "
        "`aurora_watchdog` consolidates the four signals, `/aurora-archive-stale` auto-archives.\n"
        "- **Rescue chain stages** (in order, each opt-in based on failed_axes):\n"
        "  1. bake_vertex_colors — color richness (every Cat needed it: +20)\n"
        "  2. mesh_postprocess --auto-fix — manifold (Cat 4: 40→100, +9.4)\n"
        "  3. mesh_reshape (kind-aware) — silhouette aspect (Cat 2: 50→80, +9)\n"
        "- **42 motion fixtures** parity TS↔Python (was 22). 45 motion presets including "
        "v80v additions: character.climb, character.spin, creature.roar, mechanism.vibrate.\n"
        "- **Score history** (`application/output/3d/score_history.jsonl`) feeds dashboard "
        "sparklines + trend banner + per-axis effectiveness bars + watchdog top-runs.\n"
        "- **Coverage report** (`/aurora-coverage`) surfaces dead agents.\n"
        "- **Tracker query** (`/aurora-tracker-query` + `GET /api/agents/dispatches`) closes the audit chain.\n"
        "- **Pre-commit gate** active when `git config core.hooksPath .claude/git-hooks` set.\n"
        "- **CI template** at `.claude/ci/validate-agents.yml.template` covers all of the above.\n\n"
    )


def render() -> str:
    return (
        section_header()
        + section_head()
        + section_watchdog()
        + section_self_test()
        + section_tracker()
        + section_3d_runs()
        + section_recent_commits()
        + section_workflows()
        + section_known_state()
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Aurora handoff doc generator")
    parser.add_argument("--stdout", action="store_true",
                        help="Print to stdout instead of writing HANDOFF.md")
    args = parser.parse_args()
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
    except (AttributeError, ValueError):
        pass

    text = render()
    if args.stdout:
        sys.stdout.write(text)
        return 0

    HANDOFF.write_text(text, encoding="utf-8")
    sys.stdout.write(f"wrote {HANDOFF} ({len(text):,} chars)\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
