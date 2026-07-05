#!/usr/bin/env python3
"""Render a self-contained HTML dashboard for the AuroraIA-v2 multi-agent tracker.

Reads `.claude/agent-tracker/state.json` + `.claude/agent-tracker/history/*.json` +
`.claude/agents/*.md`. Writes `.claude/agent-tracker/dashboard.html` — a single file
with inlined CSS, no external assets, openable in any browser.

The dashboard shows:
- Header: schema version, last_commit, last_commit_at, session_goal
- Leads grid: each lead is a card with its sub-agents and how many leads consume it
- Recent tasks timeline: last 30 tasks (current + last archive) with lead, status, brief, duration
- Stats footer: total agents, total tasks across history, success/blocked counts

Dark theme, monospace font, one HTML file, no JS frameworks. The point is durable
observability without spinning up a server.
"""

from __future__ import annotations

import html
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
TRACKER = REPO_ROOT / ".claude" / "agent-tracker" / "state.json"
HISTORY_DIR = REPO_ROOT / ".claude" / "agent-tracker" / "history"
AGENTS_DIR = REPO_ROOT / ".claude" / "agents"
DASHBOARD = REPO_ROOT / ".claude" / "agent-tracker" / "dashboard.html"

FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)


def parse_frontmatter(text: str) -> dict[str, str]:
    match = FRONTMATTER_RE.match(text)
    if not match:
        return {}
    out: dict[str, str] = {}
    for line in match.group(1).splitlines():
        if ":" not in line or line.lstrip().startswith("#"):
            continue
        key, _, val = line.partition(":")
        out[key.strip()] = val.strip()
    return out


def load_state() -> dict:
    if not TRACKER.exists():
        return {}
    try:
        return json.loads(TRACKER.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def load_recent_history(n_files: int = 3) -> list[dict]:
    if not HISTORY_DIR.is_dir():
        return []
    files = sorted(HISTORY_DIR.glob("tasks-*.json"), reverse=True)[:n_files]
    out: list[dict] = []
    for f in files:
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            out.extend(data.get("tasks", []))
        except (OSError, json.JSONDecodeError):
            continue
    return out


def load_agent_descriptions() -> dict[str, str]:
    descriptions: dict[str, str] = {}
    if not AGENTS_DIR.is_dir():
        return descriptions
    for md in AGENTS_DIR.glob("*.md"):
        if md.name in {"README.md", "EXAMPLES.md"}:
            continue
        fm = parse_frontmatter(md.read_text(encoding="utf-8"))
        if "name" in fm and "description" in fm:
            descriptions[fm["name"]] = fm["description"][:140]
    return descriptions


def fmt_status_class(status: str) -> str:
    return {"in_progress": "ip", "done": "ok", "blocked": "ko"}.get(status, "")


def fmt_duration(started: str | None, finished: str | None) -> str:
    if not started or not finished:
        return "—"
    try:
        a = datetime.fromisoformat(started.replace("Z", "+00:00"))
        b = datetime.fromisoformat(finished.replace("Z", "+00:00"))
        sec = (b - a).total_seconds()
        if sec < 60:
            return f"{sec:.0f}s"
        if sec < 3600:
            return f"{sec / 60:.0f}m"
        return f"{sec / 3600:.1f}h"
    except (ValueError, AttributeError):
        return "—"


def render_leads_grid(state: dict, descriptions: dict[str, str]) -> str:
    leads = state.get("leads") or {}
    cards: list[str] = []
    for lead_name in sorted(leads):
        body = leads[lead_name] or {}
        sub_agents = body.get("sub_agents") or []
        delegates_to = body.get("delegates_to") or []
        consumed_by = body.get("consumed_by") or []
        desc = descriptions.get(lead_name, "")

        sub_html = ""
        if sub_agents:
            items = "".join(
                f'<li><code>{html.escape(s)}</code><span class="sd">{html.escape(descriptions.get(s, ""))}</span></li>'
                for s in sub_agents
            )
            sub_html = f'<ul class="sub">{items}</ul>'

        edges = []
        if delegates_to:
            edges.append(f'→ {", ".join(html.escape(d) for d in delegates_to)}')
        if consumed_by:
            edges.append(f'consumed by {len(consumed_by)} lead(s)')
        edges_html = (
            f'<div class="edges">{" · ".join(edges)}</div>' if edges else ""
        )

        cards.append(
            f'<article class="lead">'
            f'<header><h3>{html.escape(lead_name)}</h3>'
            f'<span class="badge">{len(sub_agents)} sub</span></header>'
            f'<p class="desc">{html.escape(desc)}</p>'
            f'{edges_html}{sub_html}</article>'
        )
    return '<section class="leads-grid">' + "".join(cards) + "</section>"


def render_tasks_timeline(state: dict, history_tasks: list[dict]) -> str:
    tasks = list(history_tasks) + list(state.get("tasks") or [])
    tasks = tasks[-30:]
    if not tasks:
        return '<p class="muted">No tasks yet.</p>'
    rows: list[str] = []
    for t in reversed(tasks):
        status = t.get("status", "?")
        meta = t.get("metadata") or {}
        run_id = meta.get("run_id") or ""
        delta = meta.get("score_delta")
        if isinstance(delta, (int, float)):
            delta_class = "ok" if delta > 0 else ("ko" if delta < 0 else "")
            delta_str = f'<code class="{delta_class}">{"+" if delta > 0 else ""}{delta}</code>'
        else:
            delta_str = '<span class="muted">—</span>'
        rows.append(
            f'<tr class="{fmt_status_class(status)}">'
            f'<td><code>{html.escape(t.get("id", "?"))}</code></td>'
            f'<td><code>{html.escape(t.get("lead", "?"))}</code></td>'
            f'<td>{html.escape(status)}</td>'
            f'<td>{html.escape((t.get("brief") or "")[:80])}</td>'
            f'<td>{html.escape(fmt_duration(t.get("started_at"), t.get("finished_at")))}</td>'
            f'<td><code>{html.escape(str(run_id)[:24])}</code></td>'
            f'<td>{delta_str}</td>'
            f'<td>{html.escape((t.get("verdict") or "")[:50])}</td>'
            f'</tr>'
        )
    return (
        '<table class="tasks"><thead><tr><th>id</th><th>lead</th>'
        '<th>status</th><th>brief</th><th>duration</th>'
        '<th>run_id</th><th>Δscore</th><th>verdict</th>'
        '</tr></thead><tbody>' + "".join(rows) + "</tbody></table>"
    )


def render_stats(state: dict, history_tasks: list[dict], descriptions: dict[str, str]) -> str:
    all_tasks = list(history_tasks) + list(state.get("tasks") or [])
    done = sum(1 for t in all_tasks if t.get("status") == "done")
    blocked = sum(1 for t in all_tasks if t.get("status") == "blocked")
    in_flight = sum(1 for t in all_tasks if t.get("status") == "in_progress")
    leads_count = len(state.get("leads") or {})
    crosscut_count = len(state.get("crosscut") or [])
    total_agents = len(descriptions)
    return (
        '<section class="stats">'
        f'<div><span>{total_agents}</span>agents</div>'
        f'<div><span>{leads_count}</span>leads</div>'
        f'<div><span>{crosscut_count}</span>crosscut</div>'
        f'<div><span>{len(all_tasks)}</span>tasks total</div>'
        f'<div class="ok"><span>{done}</span>done</div>'
        f'<div class="ko"><span>{blocked}</span>blocked</div>'
        f'<div class="ip"><span>{in_flight}</span>in-flight</div>'
        '</section>'
    )


def render_metrics_section(metrics: dict) -> str:
    leads = metrics.get("leads") or {}
    if not leads:
        return ""
    rows = []
    sorted_leads = sorted(leads.items(), key=lambda kv: (-kv[1]["count"], kv[0]))
    for name, m in sorted_leads:
        avg = m["avg_duration_s"]
        avg_str = f"{avg:.1f}s" if avg is not None else "—"
        last_at = (m["last_finished_at"] or "—")[:19]
        last_st = m["last_status"] or "—"
        success = (
            f"{(m['done'] / max(1, m['done'] + m['blocked'])) * 100:.0f}%"
            if (m["done"] or m["blocked"]) else "—"
        )
        rows.append(
            f'<tr><td><code>{html.escape(name)}</code></td>'
            f'<td>{m["count"]}</td>'
            f'<td class="ok">{m["done"]}</td>'
            f'<td class="ko">{m["blocked"]}</td>'
            f'<td>{html.escape(success)}</td>'
            f'<td>{html.escape(avg_str)}</td>'
            f'<td>{html.escape(last_st)}</td>'
            f'<td>{html.escape(last_at)}</td></tr>'
        )
    success_global = metrics.get("global_success_rate")
    success_global_str = (
        f"{success_global * 100:.1f}%" if success_global is not None else "—"
    )
    header = (
        '<p class="meta">total dispatches '
        f'<code>{metrics.get("total_dispatches", 0)}</code> · '
        f'global success <code>{html.escape(success_global_str)}</code></p>'
    )
    return (
        f'<h2>Per-lead dispatch metrics</h2>{header}'
        '<table class="tasks"><thead><tr><th>lead</th><th>#</th>'
        '<th>done</th><th>blk</th><th>success</th><th>avg dur</th>'
        '<th>last status</th><th>last finished</th></tr></thead><tbody>'
        + "".join(rows) + "</tbody></table>"
    )


def render_3d_runs_section(run_index: dict | None) -> str:
    if not run_index or not run_index.get("ok"):
        return ""
    runs = run_index.get("runs") or []
    standalones = run_index.get("standalones") or []
    if not runs and not standalones:
        return ""

    lines: list[str] = ['<h2>Recent 3D runs</h2>']
    lines.append(
        f'<p class="meta">'
        f'<code>{len(runs)}</code> grouped runs · '
        f'<code>{len(standalones)}</code> standalone files in '
        f'<code>application/output/3d/</code></p>'
    )

    if runs:
        rows = []
        for run in runs[:8]:
            mtime = (run.get("latest_mtime_iso") or "—")[:19]
            file_count = len(run.get("files") or [])
            size_kb = run.get("total_size_bytes", 0) / 1024
            roles = sorted({f.get("role", "?") for f in run.get("files") or []})
            roles_str = ", ".join(roles)
            mesh_score = "—"
            for f in run.get("files") or []:
                if f.get("role") == "mesh" and f.get("score"):
                    mesh_score = str(f["score"].get("overall_score", "—"))
                    break
            rows.append(
                f'<tr><td><code>{html.escape(run["run_id"])}</code></td>'
                f'<td>{html.escape(mtime)}</td>'
                f'<td>{file_count}</td>'
                f'<td>{size_kb:,.0f} KB</td>'
                f'<td>{html.escape(roles_str)}</td>'
                f'<td>{html.escape(mesh_score)}</td></tr>'
            )
        lines.append(
            '<table class="tasks"><thead><tr><th>run id</th><th>latest</th>'
            '<th>files</th><th>size</th><th>roles</th><th>score</th>'
            '</tr></thead><tbody>' + "".join(rows) + "</tbody></table>"
        )

    if standalones:
        baked = [f for f in standalones if f.get("role") in ("baked", "reshaped", "rescue")]
        viewers = [f for f in standalones if f.get("role") == "viewer"]
        if baked:
            lines.append('<h3 style="margin-top:14px;font-size:12px;color:#79c0ff">'
                         f'Rescued meshes ({len(baked)})</h3>')
            items = "".join(
                f'<li><code>{html.escape(f["name"])}</code> '
                f'<span class="sd">{f.get("role", "?")} · '
                f'{f.get("size_bytes", 0) / 1024:,.0f} KB</span></li>'
                for f in baked[:8]
            )
            lines.append(f'<ul class="sub">{items}</ul>')
        if viewers:
            lines.append('<h3 style="margin-top:14px;font-size:12px;color:#79c0ff">'
                         f'Viewers ({len(viewers)})</h3>')
            items = "".join(
                f'<li><code>{html.escape(f["name"])}</code></li>'
                for f in viewers[:5]
            )
            lines.append(f'<ul class="sub">{items}</ul>')

    return "".join(lines)


def load_score_history() -> list[dict] | None:
    """Pull top-N rescue runs with chronological event lists. Soft-fails
    if score_history.py is missing or the log is empty."""
    try:
        sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent
                              / "application" / "python-services"))
        from score_history import load_events, top_runs  # type: ignore
        summaries = top_runs(n=8)
        if not summaries:
            return []
        out: list[dict] = []
        for s in summaries:
            events = list(reversed(load_events(run_id=s["run_id"])))
            stages = [e.get("overall_score") for e in events if isinstance(e.get("overall_score"), (int, float))]
            out.append({**s, "stage_scores": stages})
        return out
    except Exception:  # noqa: BLE001 — dashboard must always render
        return None


def load_score_trend() -> dict | None:
    try:
        sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent
                              / "application" / "python-services"))
        from score_history import compute_trend  # type: ignore
        return compute_trend()
    except Exception:  # noqa: BLE001
        return None


def load_tracker_health(stale_min: int = 30) -> dict | None:
    try:
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        from tracker_health import compute_health, load_state  # type: ignore
        return compute_health(load_state(), stale_min)
    except Exception:  # noqa: BLE001
        return None


def load_agent_coverage() -> dict | None:
    try:
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        from agent_coverage import compute_coverage  # type: ignore
        return compute_coverage()
    except Exception:  # noqa: BLE001
        return None


def render_coverage_section(coverage: dict | None) -> str:
    if not coverage or not coverage.get("total_declared"):
        return ""
    declared = coverage["total_declared"]
    dispatched = coverage["total_dispatched"]
    dead = coverage["total_dead"]
    pct = coverage["coverage_pct"]
    pct_class = "ok" if pct >= 50 else ("ip" if pct >= 20 else "ko")

    # Top 5 most-dispatched
    rows = (coverage.get("by_lead") or [])[:5]
    most_used: list[str] = []
    for r in rows:
        last = (r.get("last_dispatch_at") or "—")[:19]
        most_used.append(
            f'<li><code>{html.escape(r["name"])}</code> · '
            f'<span class="sd">{r["role"]}'
            + (f' / {html.escape(r["parent_lead"])}' if r.get("parent_lead") else '')
            + '</span> · '
            f'<code>{r["dispatch_count"]} disp.</code> · '
            f'<span class="sd">{html.escape(last)}</span></li>'
        )

    dead_names = (coverage.get("dead") or [])[:8]
    dead_str = ", ".join(f"<code>{html.escape(n)}</code>" for n in dead_names)
    if len(coverage.get("dead") or []) > 8:
        dead_str += f' <span class="muted">… +{len(coverage["dead"]) - 8} more</span>'

    return (
        '<h2>Agent coverage</h2>'
        f'<p class="meta">'
        f'<code>{declared}</code> declared · '
        f'<code class="ok">{dispatched}</code> dispatched · '
        f'<code class="ko">{dead}</code> dead · '
        f'<code class="{pct_class}">{pct}%</code> coverage</p>'
        '<h3 style="margin-top:10px">Most-dispatched</h3>'
        f'<ul class="sub">{"".join(most_used)}</ul>'
        + (f'<h3 style="margin-top:10px">Dead set ({len(coverage.get("dead") or [])})</h3>'
           f'<p class="meta">{dead_str}</p>' if dead_names else "")
    )


def render_tracker_health_banner(health: dict | None) -> str:
    if not health:
        return ""
    in_flight = health.get("in_progress_count", 0)
    stale = health.get("stale_count", 0)
    if in_flight == 0 and stale == 0:
        return ""
    if stale == 0:
        return (
            f'<p class="meta" style="margin-top:6px">'
            f'tracker: <code>{in_flight}</code> task(s) in flight · '
            f'<code class="ok">no stale work</code></p>'
        )
    items = "".join(
        f'<li><code>{html.escape(t["lead"])}</code> · '
        f'<code class="ko">{t["age_minutes"]:.1f}m</code> · '
        f'<span class="sd">{html.escape(t["brief"][:80])}</span></li>'
        for t in (health.get("stale_tasks") or [])[:5]
    )
    return (
        f'<p class="meta" style="margin-top:6px">'
        f'tracker: <code>{in_flight}</code> in flight · '
        f'<code class="ko">{stale}</code> stale '
        f'(>{health.get("stale_threshold_min", 30)} min)</p>'
        f'<ul class="sub" style="margin:4px 0 0 8px">{items}</ul>'
    )


def render_score_trend_banner(trend: dict | None) -> str:
    if not trend or not trend.get("total_runs"):
        return ""
    pr = int((trend.get("promote_rate") or 0) * 100)
    md = trend.get("mean_delta") or 0
    md_str = f"+{md}" if md > 0 else str(md)
    md_class = "ok" if md > 0 else ("ko" if md < 0 else "muted")
    axes = trend.get("axis_lifts") or {}
    axes_str = ", ".join(f"{k}({v})" for k, v in list(axes.items())[:4]) if axes else "—"
    return (
        '<p class="meta" style="margin-top:8px">'
        f'rescue trend: <code>{trend["promoted_runs"]}/{trend["total_runs"]}</code> runs promoted '
        f'<code>({pr}%)</code> · mean delta <code class="{md_class}">{md_str}</code> · '
        f'best <code class="ok">+{trend.get("best_delta", 0)}</code> · '
        f'axes lifted: <code>{html.escape(axes_str)}</code>'
        '</p>'
        f'{_render_axis_lifts_bars(axes, trend.get("total_runs", 1))}'
    )


def _render_axis_lifts_bars(axes: dict, total_runs: int) -> str:
    """Horizontal SVG bars showing which mesh axes the rescue chain
    actually fixes most often. Each axis bar is sized as
    lift_count / total_runs, with the count + denominator inline."""
    if not axes or not total_runs:
        return ""
    rows = []
    bar_max = 200  # px
    for axis, count in list(axes.items())[:6]:
        try:
            ratio = max(0.0, min(1.0, float(count) / float(total_runs)))
        except (TypeError, ZeroDivisionError):
            continue
        width = max(2, int(bar_max * ratio))
        pct = int(ratio * 100)
        label = html.escape(str(axis))
        rows.append(
            f'<div style="display:flex;align-items:center;gap:8px;margin:2px 0;font-size:11px">'
            f'<code style="min-width:140px;color:#a5d6ff">{label}</code>'
            f'<svg width="{bar_max}" height="10" viewBox="0 0 {bar_max} 10" '
            f'style="vertical-align:middle">'
            f'<rect x="0" y="0" width="{bar_max}" height="10" fill="#21262d" rx="2"/>'
            f'<rect x="0" y="0" width="{width}" height="10" fill="#7ee787" rx="2"/>'
            f'</svg>'
            f'<span class="muted">{count}/{total_runs} ({pct}%)</span>'
            f'</div>'
        )
    return (
        '<div style="margin:8px 0 12px 0;padding:8px;background:#0d1117;'
        'border:1px solid #30363d;border-radius:6px">'
        '<p class="meta" style="margin:0 0 6px 0">Axis lifts (% of runs where '
        'this axis was rescued)</p>'
        + "".join(rows) + "</div>"
    )


def render_score_progression_section(runs: list[dict] | None, trend: dict | None = None) -> str:
    if not runs:
        return ""
    rows: list[str] = []
    for run in runs:
        run_id = run.get("run_id") or "?"
        kind = run.get("subject_kind") or "—"
        initial = run.get("initial_score")
        final = run.get("final_score")
        delta = run.get("score_delta", 0)
        stage_scores = run.get("stage_scores") or []

        spark_svg = _render_sparkline(stage_scores)
        delta_class = "ok" if delta and delta > 0 else ("ko" if delta and delta < 0 else "")
        delta_str = f"+{delta}" if isinstance(delta, (int, float)) and delta > 0 else str(delta)
        rows.append(
            f'<tr>'
            f'<td><code>{html.escape(run_id)}</code></td>'
            f'<td>{html.escape(kind)}</td>'
            f'<td>{initial if initial is not None else "—"}</td>'
            f'<td>{final if final is not None else "—"}</td>'
            f'<td class="{delta_class}">{html.escape(delta_str)}</td>'
            f'<td>{run.get("events_count", 0)}</td>'
            f'<td>{spark_svg}</td>'
            f'</tr>'
        )
    return (
        '<h2>Score progression (rescue chain)</h2>'
        f'<p class="meta">top {len(runs)} runs by final overall_score · '
        f'sparkline = chronological per-stage score</p>'
        f'{render_score_trend_banner(trend)}'
        '<table class="tasks"><thead><tr><th>run id</th><th>kind</th>'
        '<th>initial</th><th>final</th><th>delta</th><th>events</th>'
        '<th>progression</th></tr></thead><tbody>'
        + "".join(rows) + "</tbody></table>"
    )


def _render_sparkline(scores: list[float], width: int = 120, height: int = 24) -> str:
    if not scores or len(scores) < 2:
        if scores:
            return f'<span class="muted">{scores[0]}</span>'
        return '<span class="muted">—</span>'
    pad = 2
    inner_w = width - 2 * pad
    inner_h = height - 2 * pad
    n = len(scores)
    pts = []
    for i, s in enumerate(scores):
        x = pad + (inner_w * i / max(1, n - 1))
        y = pad + inner_h - (inner_h * max(0.0, min(100.0, float(s))) / 100.0)
        pts.append(f"{x:.1f},{y:.1f}")
    poly = " ".join(pts)
    last_color = "#7ee787" if scores[-1] >= scores[0] else "#ff7b72"
    last_x, last_y = pts[-1].split(",")
    return (
        f'<svg width="{width}" height="{height}" viewBox="0 0 {width} {height}" '
        f'style="vertical-align:middle">'
        f'<polyline points="{poly}" fill="none" stroke="{last_color}" stroke-width="1.5"/>'
        f'<circle cx="{last_x}" cy="{last_y}" r="2" fill="{last_color}"/>'
        f'</svg>'
    )


def load_run_index() -> dict | None:
    """Run mesh_run_index.py via subprocess (no scoring — too slow for the
    dashboard regen). Soft-fail if the script crashes."""
    try:
        sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent
                              / "application" / "python-services"))
        from mesh_run_index import index_runs  # type: ignore
        target = REPO_ROOT / "application" / "output" / "3d"
        return index_runs(target)
    except Exception:  # noqa: BLE001 — dashboard must always render
        return None


def render_html(state: dict, history_tasks: list[dict], descriptions: dict[str, str], metrics: dict | None = None, run_index: dict | None = None, score_runs: list[dict] | None = None, score_trend: dict | None = None, tracker_health: dict | None = None, coverage: dict | None = None) -> str:
    last_commit = state.get("last_commit") or "—"
    last_commit_at = state.get("last_commit_at") or "—"
    session_goal = state.get("session_goal") or "—"
    schema = state.get("schema_version") or "?"
    css = """
    *{box-sizing:border-box}
    body{font-family:ui-monospace,SFMono-Regular,Menlo,Monaco,Consolas,monospace;
         background:#0d1117;color:#e6edf3;margin:0;padding:24px;line-height:1.45}
    h1,h2,h3{margin:0}
    h1{font-size:18px;color:#7ee787}
    h2{font-size:14px;color:#79c0ff;margin:24px 0 12px;border-bottom:1px solid #30363d;padding-bottom:6px}
    h3{font-size:13px;color:#d2a8ff}
    .meta{color:#8b949e;font-size:12px;margin-top:4px}
    .meta code{background:#161b22;padding:2px 6px;border-radius:4px}
    .stats{display:grid;grid-template-columns:repeat(auto-fit,minmax(110px,1fr));
           gap:12px;margin:16px 0}
    .stats div{background:#161b22;border:1px solid #30363d;border-radius:6px;
               padding:10px 12px;text-align:center}
    .stats span{display:block;font-size:24px;color:#e6edf3;font-weight:600}
    .stats .ok span{color:#7ee787}
    .stats .ko span{color:#ff7b72}
    .stats .ip span{color:#d29922}
    .leads-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(280px,1fr));gap:12px}
    .lead{background:#161b22;border:1px solid #30363d;border-radius:6px;padding:12px}
    .lead header{display:flex;justify-content:space-between;align-items:center}
    .lead .badge{background:#1f6feb;color:#fff;font-size:10px;padding:2px 8px;border-radius:10px}
    .lead .desc{font-size:11px;color:#8b949e;margin:6px 0 8px}
    .lead .edges{font-size:10px;color:#8b949e;margin-bottom:6px}
    .lead .sub{margin:0;padding-left:16px;font-size:11px}
    .lead .sub li{margin:2px 0}
    .lead .sub code{color:#79c0ff}
    .lead .sub .sd{color:#6e7681;display:block;font-size:10px;margin-left:4px}
    table.tasks{width:100%;border-collapse:collapse;font-size:11px;margin-top:8px}
    table.tasks th,table.tasks td{text-align:left;padding:5px 8px;
                                  border-bottom:1px solid #21262d;vertical-align:top}
    table.tasks th{color:#79c0ff;background:#0d1117}
    table.tasks tr.ok td:nth-child(3){color:#7ee787}
    table.tasks tr.ko td:nth-child(3){color:#ff7b72}
    table.tasks tr.ip td:nth-child(3){color:#d29922}
    table.tasks code{color:#a5d6ff}
    table.tasks td.ok{color:#7ee787}
    table.tasks td.ko{color:#ff7b72}
    code.ok{color:#7ee787}
    code.ko{color:#ff7b72}
    code.muted{color:#6e7681}
    .muted{color:#6e7681}
    .footer{margin-top:24px;color:#6e7681;font-size:11px}
    """
    body = (
        f'<h1>Aurora multi-agent tracker — {html.escape(schema)}</h1>'
        f'<p class="meta">last commit <code>{html.escape(last_commit)}</code> at '
        f'<code>{html.escape(last_commit_at)}</code></p>'
        f'<p class="meta">goal: {html.escape(session_goal)}</p>'
        f'{render_stats(state, history_tasks, descriptions)}'
        f'{render_tracker_health_banner(tracker_health)}'
        f'{render_metrics_section(metrics) if metrics else ""}'
        f'{render_coverage_section(coverage)}'
        f'<h2>Leads</h2>{render_leads_grid(state, descriptions)}'
        f'{render_3d_runs_section(run_index)}'
        f'{render_score_progression_section(score_runs, score_trend)}'
        f'<h2>Recent tasks (last 30)</h2>{render_tasks_timeline(state, history_tasks)}'
        f'<p class="footer">Generated {datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")} '
        f'from <code>.claude/agent-tracker/state.json</code> + history.</p>'
    )
    return (
        f'<!doctype html><html lang="en"><head><meta charset="utf-8">'
        f'<title>Aurora agent dashboard</title><style>{css}</style></head>'
        f'<body>{body}</body></html>'
    )


def load_metrics() -> dict | None:
    """Try to compute metrics via agent_metrics.compute_metrics(). Soft-fail
    on import errors so the dashboard still renders without metrics."""
    try:
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        from agent_metrics import collect_tasks, compute_metrics  # type: ignore
        return compute_metrics(collect_tasks())
    except Exception:  # noqa: BLE001 — dashboard must always render
        return None


def main() -> int:
    state = load_state()
    history_tasks = load_recent_history()
    descriptions = load_agent_descriptions()
    metrics = load_metrics()
    run_index = load_run_index()
    score_runs = load_score_history()
    score_trend = load_score_trend()
    tracker_health = load_tracker_health()
    coverage = load_agent_coverage()
    if not state and not descriptions:
        sys.stderr.write("[aurora-dashboard] no tracker state and no agents — nothing to render\n")
        return 1
    html_text = render_html(state, history_tasks, descriptions, metrics, run_index, score_runs, score_trend, tracker_health, coverage)
    DASHBOARD.parent.mkdir(parents=True, exist_ok=True)
    DASHBOARD.write_text(html_text, encoding="utf-8")
    sys.stdout.write(str(DASHBOARD) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
