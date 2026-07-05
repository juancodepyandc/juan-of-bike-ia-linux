#!/usr/bin/env python
"""Aurora multi-agent system master self-test.

Runs every gate that protects the architecture, in order, and produces a
single PASS/FAIL verdict. Designed for `/aurora-self-test`, CI, and ad-hoc
verification after a refactor.

Gates (each one is allowed to fail without aborting the run — the report
collects every failure so the user fixes them all in one pass):

  1. validate_agents      — frontmatter + tracker + KNOWN_AGENTS coherence
  2. test_hooks           — 15 unit tests on the 6 hooks
  3. test_route_test      — 13 routing tests
  4. bridge_doctor        — diagnose bridge health
  5. agents_list_endpoint — bridge GET /api/agents/list returns >=N agents
  6. route_test_endpoint  — bridge POST /api/3d/route-test returns valid JSON
  7. dashboard_render     — aurora_dashboard.py produces a non-empty .html

Total runtime ~3-4 s on a healthy system.

Exit codes: 0 = all green, 1 = any failure. Output is human-readable +
machine-parseable (one line per gate).
"""

from __future__ import annotations

import json
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
BRIDGE_HEALTH = "http://127.0.0.1:3001/api/health"
BRIDGE_AGENTS_LIST = "http://127.0.0.1:3001/api/agents/list"
BRIDGE_ROUTE_TEST = "http://127.0.0.1:3001/api/3d/route-test"
EXPECTED_AGENT_FLOOR = 30  # safety floor — current is 37, won't drop below 30


class Gate:
    __slots__ = ("name", "ok", "detail")

    def __init__(self, name: str) -> None:
        self.name = name
        self.ok = False
        self.detail = ""

    def __repr__(self) -> str:
        marker = "ok " if self.ok else "FAIL"
        return f"  [{marker}] {self.name:<22} {self.detail}"


def run(cmd: list[str], timeout: int = 30) -> tuple[int, str, str]:
    proc = subprocess.run(
        cmd, cwd=str(REPO_ROOT),
        capture_output=True, timeout=timeout, check=False,
    )
    out = (proc.stdout or b"").decode("utf-8", errors="replace")
    err = (proc.stderr or b"").decode("utf-8", errors="replace")
    return proc.returncode, out, err


def gate_validate_agents() -> Gate:
    g = Gate("validate_agents")
    rc, out, err = run([sys.executable, ".claude/hooks/validate_agents.py"])
    g.ok = rc == 0
    g.detail = (out.strip() or err.strip()).splitlines()[-1] if (out or err) else ""
    return g


def gate_test_hooks() -> Gate:
    g = Gate("test_hooks")
    rc, out, err = run([sys.executable, ".claude/hooks/test_hooks.py"])
    g.ok = rc == 0
    last = (err.strip() or out.strip()).splitlines()[-1] if (out or err) else ""
    g.detail = last
    return g


def gate_test_route_test() -> Gate:
    g = Gate("test_route_test")
    rc, out, err = run([sys.executable, "application/scripts/test_route_test.py"])
    g.ok = rc == 0
    last = (err.strip() or out.strip()).splitlines()[-1] if (out or err) else ""
    g.detail = last
    return g


def gate_bridge_doctor() -> Gate:
    g = Gate("bridge_doctor")
    rc, out, _ = run([sys.executable, "bridge_doctor.py", "--check-only"])
    g.ok = rc == 0
    g.detail = out.strip().splitlines()[-1] if out else ""
    return g


def gate_agents_list_endpoint() -> Gate:
    g = Gate("agents_list_endpoint")
    try:
        with urllib.request.urlopen(BRIDGE_AGENTS_LIST, timeout=5) as r:
            data = json.loads(r.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError) as exc:
        g.detail = f"unreachable: {exc}"
        return g
    count = data.get("agent_count", 0)
    if not data.get("ok") or count < EXPECTED_AGENT_FLOOR:
        g.detail = f"ok={data.get('ok')} count={count} (floor={EXPECTED_AGENT_FLOOR})"
        return g
    g.ok = True
    g.detail = f"agent_count={count}, leads={len(data.get('leads') or {})}"
    return g


def gate_route_test_endpoint() -> Gate:
    g = Gate("route_test_endpoint")
    body = json.dumps({"prompt": "boitier PC quartz fume obsidienne"}).encode("utf-8")
    req = urllib.request.Request(
        BRIDGE_ROUTE_TEST, data=body,
        headers={"Content-Type": "application/json"}, method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            data = json.loads(r.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError) as exc:
        g.detail = f"unreachable: {exc}"
        return g
    routing = data.get("routing") or {}
    if not data.get("ok") or not routing.get("dreamgaussianPreferred"):
        g.detail = f"ok={data.get('ok')} dgPreferred={routing.get('dreamgaussianPreferred')}"
        return g
    g.ok = True
    g.detail = f"dgPreferred={routing['dreamgaussianPreferred']} (Cat 1 fix verified)"
    return g


def gate_metrics() -> Gate:
    g = Gate("metrics_derivation")
    rc, out, err = run([sys.executable, ".claude/hooks/agent_metrics.py"])
    if rc != 0:
        g.detail = (err.strip() or out.strip()).splitlines()[-1] if (out or err) else ""
        return g
    try:
        data = json.loads(out)
    except json.JSONDecodeError as exc:
        g.detail = f"invalid JSON: {exc}"
        return g
    if data.get("schema") != "aurora.metrics.v1":
        g.detail = f"unexpected schema: {data.get('schema')}"
        return g
    g.ok = True
    total = data.get("total_dispatches", 0)
    rate = data.get("global_success_rate")
    rate_str = f"{rate * 100:.0f}%" if rate is not None else "—"
    g.detail = f"total_dispatches={total}, success={rate_str}"
    return g


def gate_motion_baker_self_test() -> Gate:
    g = Gate("motion_baker_13_cases")
    try:
        with urllib.request.urlopen(
            "http://127.0.0.1:3001/api/3d/motion-self-test", timeout=30,
        ) as r:
            data = json.loads(r.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError) as exc:
        g.detail = f"unreachable: {exc}"
        return g
    out = data.get("stdout", "")
    if not data.get("ok") or "SELF_TEST_OK" not in out:
        g.detail = f"FAIL ok={data.get('ok')} rc={data.get('returncode')}"
        return g
    g.ok = True
    g.detail = out.strip().splitlines()[-1] if out else "ok"
    return g


def gate_motion_parser_self_test() -> Gate:
    g = Gate("motion_parser_17_cases")
    try:
        with urllib.request.urlopen(
            "http://127.0.0.1:3001/api/3d/motion-parser-self-test", timeout=30,
        ) as r:
            data = json.loads(r.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError) as exc:
        g.detail = f"unreachable: {exc}"
        return g
    out = data.get("stdout", "")
    if not data.get("ok") or "PARSER_SELF_TEST_OK" not in out:
        g.detail = f"FAIL ok={data.get('ok')} rc={data.get('returncode')}"
        return g
    g.ok = True
    g.detail = out.strip().splitlines()[-1] if out else "ok"
    return g


def gate_motion_parity() -> Gate:  # gate name kept stable; fixture count grows over time
    g = Gate("motion_parity_fixtures")
    try:
        with urllib.request.urlopen(
            "http://127.0.0.1:3001/api/3d/motion-parity", timeout=30,
        ) as r:
            data = json.loads(r.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError) as exc:
        g.detail = f"unreachable: {exc}"
        return g
    if not data.get("ok"):
        g.detail = (
            f"parity FAIL: rc={data.get('returncode')} "
            f"summary={data.get('summary')}"
        )
        return g
    g.ok = True
    g.detail = data.get("summary") or "ok"
    return g


def gate_auto_rescue_endpoint() -> Gate:
    g = Gate("auto_rescue_endpoint")
    ref = REPO_ROOT / "application" / "output" / "3d" / "juan_bike_1777509822533_reference.png"
    mesh = REPO_ROOT / "application" / "output" / "3d" / "juan_bike_1777509822533_mesh.glb"
    if not ref.is_file() or not mesh.is_file():
        g.ok = True
        g.detail = "skipped (no Cat 1 ref/mesh)"
        return g
    body = json.dumps({
        "mesh": "output/3d/juan_bike_1777509822533_mesh.glb",
        "reference": "output/3d/juan_bike_1777509822533_reference.png",
        "prompt": "boitier PC quartz fume translucide obsidienne",
        "output_dir": "output/3d/rescue_selftest",
    }).encode("utf-8")
    req = urllib.request.Request(
        "http://127.0.0.1:3001/api/3d/auto-rescue", data=body,
        headers={"Content-Type": "application/json"}, method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=300) as r:
            data = json.loads(r.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError) as exc:
        g.detail = f"unreachable: {exc}"
        return g
    if not data.get("ok"):
        g.detail = f"endpoint returned ok=False: {data}"
        return g
    rescue = data.get("rescue") or {}
    if rescue.get("schema") != "aurora.auto_rescue.v1":
        g.detail = f"unexpected schema: {rescue.get('schema')}"
        return g
    delta = rescue.get("score_delta", 0)
    if delta < 15.0:
        g.detail = f"rescue score delta too small: {delta} (expected >=15)"
        return g
    g.ok = True
    g.detail = (
        f"score_delta={delta:+}, "
        f"final={rescue.get('final_score')}, "
        f"audit_stages={len(rescue.get('audit_trail') or [])}"
    )
    return g


def gate_tracker_health_endpoint() -> Gate:
    g = Gate("tracker_health_endpoint")
    try:
        with urllib.request.urlopen(
            "http://127.0.0.1:3001/api/agents/health?stale_min=30", timeout=15,
        ) as r:
            data = json.loads(r.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError) as exc:
        g.detail = f"unreachable: {exc}"
        return g
    if not data.get("ok"):
        g.detail = f"endpoint returned ok=False: {data}"
        return g
    health = data.get("health") or {}
    if health.get("schema") != "aurora.tracker_health.v1":
        g.detail = f"unexpected schema: {health.get('schema')}"
        return g
    g.ok = True
    g.detail = (
        f"in_flight={health.get('in_progress_count')}, "
        f"stale={health.get('stale_count')}"
    )
    return g


def gate_dispatches_endpoint() -> Gate:
    g = Gate("dispatches_endpoint")
    try:
        with urllib.request.urlopen(
            "http://127.0.0.1:3001/api/agents/dispatches?lead=3d-quality-rescuer&limit=3",
            timeout=10,
        ) as r:
            data = json.loads(r.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError) as exc:
        g.detail = f"unreachable: {exc}"
        return g
    if not data.get("ok"):
        g.detail = f"endpoint returned ok=False: {data}"
        return g
    qry = data.get("query") or {}
    if qry.get("schema") != "aurora.tracker_query.v1":
        g.detail = f"unexpected schema: {qry.get('schema')}"
        return g
    g.ok = True
    g.detail = f"matches={qry.get('match_count', 0)}"
    return g


def gate_mesh_logic_unit() -> Gate:
    """Run the lightweight mesh-decision unit tests:
       - test_mesh_quality_score    (5-axis scorer per-axis logic)
       - test_auto_validate_mesh    (retry decisions)
       - test_mesh_color_diagnostic (lossy stage detection)
       - test_mesh_run_index        (output/3d scanner)

    Skips the heavy chain tests (test_auto_rescue / test_bake_vertex_colors /
    test_viewer_compare / test_batch_rescue, ~19s combined) because the
    auto_rescue_endpoint gate already exercises that path end-to-end on
    Cat 1. Total wall time ~8s. The point is per-axis decision coverage
    that the happy-path endpoint test can't reach."""
    g = Gate("mesh_logic_unit")
    rc, out, err = run([
        sys.executable, "-m", "unittest",
        "application.python-services.test_mesh_quality_score",
        "application.python-services.test_auto_validate_mesh",
        "application.python-services.test_mesh_color_diagnostic",
        "application.python-services.test_mesh_run_index",
    ], timeout=60)
    g.ok = rc == 0
    last = (err.strip() or out.strip()).splitlines()[-1] if (out or err) else ""
    g.detail = last
    return g


def gate_attribution_unit() -> Gate:
    """Run the fast python-services tests that cover the attribution
    chain: tracker_helper.record_dispatch (with metadata) and
    score_history (append/load/top/trend). Pre-commit doesn't run these
    — only validate_agents + test_hooks — so a regression in
    tracker_helper or score_history would slip past unless this gate
    runs them. Total wall time ~0.05s (no mesh imports)."""
    g = Gate("attribution_unit")
    rc, out, err = run([
        sys.executable, "-m", "unittest",
        "application.python-services.test_tracker_helper",
        "application.python-services.test_score_history",
        "application.python-services.test_glb_animation_injector",
        "application.python-services.test_bake_to_texture",
        "application.python-services.test_mesh_part_split",
        "application.python-services.test_aurora_3d_mcp",
    ], timeout=90)
    g.ok = rc == 0
    last = (err.strip() or out.strip()).splitlines()[-1] if (out or err) else ""
    g.detail = last
    return g


def gate_ts_tests() -> Gate:
    """Run the TS test suite via node --experimental-strip-types --test.
    Pre-commit catches regressions on commit; this gate makes the
    standalone selftest equivalent."""
    g = Gate("ts_tests")
    test_path = REPO_ROOT / "application" / "src" / "__tests__" / "meshRescue.test.ts"
    if not test_path.is_file():
        g.detail = "meshRescue.test.ts not found"
        return g
    rc, out, err = run([
        "node", "--experimental-strip-types", "--test",
        "application/src/__tests__/meshRescue.test.ts",
        "application/src/__tests__/meshStagePriority.test.ts",
    ], timeout=60)
    if rc != 0:
        # Last informative line of stderr (or stdout) for triage.
        last = (err.strip() or out.strip()).splitlines()[-1] if (out or err) else ""
        g.detail = last or f"exit {rc}"
        return g
    g.ok = True
    # Pull the "tests N" line out of node:test summary if present.
    summary = ""
    for line in (out or "").splitlines():
        if "tests " in line and not line.lstrip().startswith("✔"):
            summary = line.strip().lstrip("ℹ ").strip()
            break
    g.detail = summary or "ts tests passed"
    return g


def gate_dispatches_unit() -> Gate:
    g = Gate("dispatches_unit")
    rc, out, err = run([
        sys.executable, "-m", "unittest",
        "discover", "-s", ".claude/hooks", "-p", "test_tracker_query.py",
    ])
    g.ok = rc == 0
    last = (err.strip() or out.strip()).splitlines()[-1] if (out or err) else ""
    g.detail = last
    return g


def gate_coverage_unit() -> Gate:
    g = Gate("coverage_unit")
    rc, out, err = run([
        sys.executable, "-m", "unittest",
        "discover", "-s", ".claude/hooks", "-p", "test_agent_coverage.py",
    ])
    g.ok = rc == 0
    last = (err.strip() or out.strip()).splitlines()[-1] if (out or err) else ""
    g.detail = last
    return g


def gate_coverage_endpoint() -> Gate:
    g = Gate("coverage_endpoint")
    try:
        with urllib.request.urlopen(
            "http://127.0.0.1:3001/api/agents/coverage", timeout=15,
        ) as r:
            data = json.loads(r.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError) as exc:
        g.detail = f"unreachable: {exc}"
        return g
    if not data.get("ok"):
        g.detail = f"endpoint returned ok=False: {data}"
        return g
    cov = data.get("coverage") or {}
    if cov.get("schema") != "aurora.coverage.v1":
        g.detail = f"unexpected schema: {cov.get('schema')}"
        return g
    declared = cov.get("total_declared", 0)
    if declared < 30:  # we have 38; sanity check that .md walking works
        g.detail = f"too few agents declared: {declared}"
        return g
    g.ok = True
    g.detail = (
        f"declared={declared}, dispatched={cov.get('total_dispatched')}, "
        f"coverage={cov.get('coverage_pct')}%"
    )
    return g


def gate_watchdog_endpoint() -> Gate:
    g = Gate("watchdog_endpoint")
    try:
        with urllib.request.urlopen(
            "http://127.0.0.1:3001/api/agents/watchdog?recent=4&top=3", timeout=20,
        ) as r:
            data = json.loads(r.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError) as exc:
        g.detail = f"unreachable: {exc}"
        return g
    if not data.get("ok"):
        g.detail = f"endpoint returned ok=False: {data}"
        return g
    w = data.get("watchdog") or {}
    if w.get("schema") != "aurora.watchdog.v1":
        g.detail = f"unexpected schema: {w.get('schema')}"
        return g
    g.ok = True
    g.detail = (
        f"in_flight={(w.get('health') or {}).get('in_progress_count', '?')}, "
        f"recent={len(w.get('recent_dispatches') or [])}, "
        f"top={len(w.get('top_runs') or [])}"
    )
    return g


def gate_watchdog_render() -> Gate:
    g = Gate("watchdog_render")
    rc, out, err = run([sys.executable, ".claude/hooks/aurora_watchdog.py"])
    if rc != 0:
        g.detail = (err.strip() or out.strip()).splitlines()[-1] if (out or err) else ""
        return g
    try:
        data = json.loads(out)
    except (ValueError, TypeError):
        g.detail = "watchdog returned non-JSON"
        return g
    if data.get("schema") != "aurora.watchdog.v1":
        g.detail = f"unexpected schema: {data.get('schema')}"
        return g
    expected = {"health", "recent_dispatches", "trend", "top_runs", "metrics_summary"}
    missing = expected - set(data.keys())
    if missing:
        g.detail = f"missing keys: {sorted(missing)}"
        return g
    g.ok = True
    g.detail = (
        f"in_flight={(data.get('health') or {}).get('in_progress_count', '?')}, "
        f"recent={len(data.get('recent_dispatches') or [])}, "
        f"top={len(data.get('top_runs') or [])}"
    )
    return g


def gate_tracker_health_unit() -> Gate:
    g = Gate("tracker_health_unit")
    rc, out, err = run([
        sys.executable, "-m", "unittest",
        "discover", "-s", ".claude/hooks", "-p", "test_tracker_health.py",
    ])
    g.ok = rc == 0
    last = (err.strip() or out.strip()).splitlines()[-1] if (out or err) else ""
    g.detail = last
    return g


def gate_score_history_endpoint() -> Gate:
    g = Gate("score_history_endpoint")
    try:
        with urllib.request.urlopen(
            "http://127.0.0.1:3001/api/3d/score-history?top=5", timeout=15,
        ) as r:
            data = json.loads(r.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError) as exc:
        g.detail = f"unreachable: {exc}"
        return g
    if not data.get("ok"):
        g.detail = f"endpoint returned ok=False: {data}"
        return g
    history = data.get("history") or {}
    if "top" not in history:
        g.detail = f"missing 'top' key: {history}"
        return g
    g.ok = True
    g.detail = f"top runs returned: {len(history.get('top') or [])}"
    return g


def gate_run_index_endpoint() -> Gate:
    g = Gate("run_index_endpoint")
    try:
        with urllib.request.urlopen(
            "http://127.0.0.1:3001/api/3d/run-index", timeout=60,
        ) as r:
            data = json.loads(r.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError) as exc:
        g.detail = f"unreachable: {exc}"
        return g
    if not data.get("ok"):
        g.detail = f"endpoint returned ok=False: {data}"
        return g
    idx = data.get("index") or {}
    if idx.get("schema") != "aurora.run_index.v1":
        g.detail = f"unexpected schema: {idx.get('schema')}"
        return g
    g.ok = True
    g.detail = (
        f"runs={idx.get('run_count')}, "
        f"standalones={idx.get('standalone_count')}"
    )
    return g


def gate_mesh_compare_endpoint() -> Gate:
    g = Gate("mesh_compare_endpoint")
    orig = REPO_ROOT / "application" / "output" / "3d" / "juan_bike_1777509822533_mesh.glb"
    baked = REPO_ROOT / "application" / "output" / "3d" / "cat1_baked.glb"
    if not orig.is_file() or not baked.is_file():
        g.ok = True
        g.detail = "skipped (no Cat 1 orig/baked)"
        return g
    body = json.dumps({
        "left": "output/3d/juan_bike_1777509822533_mesh.glb",
        "right": "output/3d/cat1_baked.glb",
        "kind": "pc_tower",
    }).encode("utf-8")
    req = urllib.request.Request(
        "http://127.0.0.1:3001/api/3d/mesh-compare", data=body,
        headers={"Content-Type": "application/json"}, method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            data = json.loads(r.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError) as exc:
        g.detail = f"unreachable: {exc}"
        return g
    if not data.get("ok"):
        g.detail = f"endpoint returned ok=False: {data}"
        return g
    cmp_result = data.get("comparison") or {}
    if cmp_result.get("schema") != "aurora.mesh_compare.v1":
        g.detail = f"unexpected schema: {cmp_result.get('schema')}"
        return g
    g.ok = True
    g.detail = (
        f"winner={cmp_result.get('winner')}, "
        f"overall_delta={cmp_result.get('overall_delta')}"
    )
    return g


def gate_viewer_html_endpoint() -> Gate:
    g = Gate("viewer_html_endpoint")
    baked = REPO_ROOT / "application" / "output" / "3d" / "cat1_baked.glb"
    if not baked.is_file():
        g.ok = True
        g.detail = "skipped (no Cat 1 baked)"
        return g
    body = json.dumps({
        "mesh": "output/3d/cat1_baked.glb",
        "output": "output/3d/cat1_viewer_selftest.html",
        "title": "Cat 1 selftest",
    }).encode("utf-8")
    req = urllib.request.Request(
        "http://127.0.0.1:3001/api/3d/viewer-html", data=body,
        headers={"Content-Type": "application/json"}, method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            data = json.loads(r.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError) as exc:
        g.detail = f"unreachable: {exc}"
        return g
    if not data.get("ok"):
        g.detail = f"endpoint returned ok=False: {data}"
        return g
    viewer = data.get("viewer") or {}
    if viewer.get("schema") != "aurora.viewer.v1":
        g.detail = f"unexpected schema: {viewer.get('schema')}"
        return g
    g.ok = True
    g.detail = f"viewer html {viewer.get('size_bytes')} bytes"
    return g


def gate_bake_colors_endpoint() -> Gate:
    g = Gate("bake_colors_endpoint")
    ref = REPO_ROOT / "application" / "output" / "3d" / "juan_bike_1777509822533_reference.png"
    mesh = REPO_ROOT / "application" / "output" / "3d" / "juan_bike_1777509822533_mesh.glb"
    if not ref.is_file() or not mesh.is_file():
        g.ok = True
        g.detail = "skipped (no Cat 1 ref/mesh)"
        return g
    body = json.dumps({
        "mesh": "output/3d/juan_bike_1777509822533_mesh.glb",
        "reference": "output/3d/juan_bike_1777509822533_reference.png",
        "output": "output/3d/cat1_baked_selftest.glb",
        "kind": "pc_tower",
    }).encode("utf-8")
    req = urllib.request.Request(
        "http://127.0.0.1:3001/api/3d/bake-colors", data=body,
        headers={"Content-Type": "application/json"}, method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=180) as r:
            data = json.loads(r.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError) as exc:
        g.detail = f"unreachable: {exc}"
        return g
    if not data.get("ok"):
        g.detail = f"endpoint returned ok=False: {data}"
        return g
    bake_result = data.get("bake") or {}
    if bake_result.get("schema") != "aurora.color_bake.v1":
        g.detail = f"unexpected schema: {bake_result.get('schema')}"
        return g
    n_colors = bake_result.get("baked_unique_colors", 0)
    if n_colors < 1000:
        g.detail = f"bake produced only {n_colors} unique colors (expected >1000)"
        return g
    g.ok = True
    g.detail = f"baked {n_colors} unique colors (Cat 1 rescue)"
    return g


def gate_color_diagnostic_endpoint() -> Gate:
    g = Gate("color_diagnostic_endpoint")
    ref = REPO_ROOT / "application" / "output" / "3d" / "juan_bike_1777509822533_reference.png"
    mesh = REPO_ROOT / "application" / "output" / "3d" / "juan_bike_1777509822533_mesh.glb"
    if not ref.is_file() or not mesh.is_file():
        g.ok = True
        g.detail = "skipped (no Cat 1 ref/mesh)"
        return g
    body = json.dumps({
        "reference": "output/3d/juan_bike_1777509822533_reference.png",
        "mesh": "output/3d/juan_bike_1777509822533_mesh.glb",
    }).encode("utf-8")
    req = urllib.request.Request(
        "http://127.0.0.1:3001/api/3d/color-diagnostic", data=body,
        headers={"Content-Type": "application/json"}, method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            data = json.loads(r.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError) as exc:
        g.detail = f"unreachable: {exc}"
        return g
    if not data.get("ok"):
        g.detail = f"endpoint returned ok=False: {data}"
        return g
    diag = data.get("diagnostic") or {}
    if diag.get("schema") != "aurora.color_diagnostic.v1":
        g.detail = f"unexpected schema: {diag.get('schema')}"
        return g
    g.ok = True
    g.detail = (
        f"stage_lost={diag.get('stage_lost')}, "
        f"loss={diag.get('color_loss_ratio_ref_to_mesh')}"
    )
    return g


def gate_auto_validate_endpoint() -> Gate:
    g = Gate("auto_validate_endpoint")
    cat1 = REPO_ROOT / "application" / "output" / "3d" / "juan_bike_1777509822533_mesh.glb"
    if not cat1.is_file():
        g.ok = True
        g.detail = "skipped (no Cat 1 mesh)"
        return g
    body = json.dumps({
        "mesh_path": "output/3d/juan_bike_1777509822533_mesh.glb",
        "prompt": "boitier PC quartz fume translucide obsidienne acajou",
        "pipeline": "hunyuan3d",
    }).encode("utf-8")
    req = urllib.request.Request(
        "http://127.0.0.1:3001/api/3d/auto-validate", data=body,
        headers={"Content-Type": "application/json"}, method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            data = json.loads(r.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError) as exc:
        g.detail = f"unreachable: {exc}"
        return g
    if not data.get("ok"):
        g.detail = f"endpoint returned ok=False: {data}"
        return g
    val = data.get("validation") or {}
    if val.get("schema") != "aurora.auto_validate.v1":
        g.detail = f"unexpected schema: {val.get('schema')}"
        return g
    kind = (val.get("extraction") or {}).get("kind")
    next_pipe = (val.get("next_action") or {}).get("next_pipeline")
    g.ok = True
    g.detail = f"kind={kind}, next={next_pipe} (Cat 1 fix loop closed)"
    return g


def gate_mesh_score_endpoint() -> Gate:
    g = Gate("mesh_score_endpoint")
    cat1 = REPO_ROOT / "application" / "output" / "3d" / "juan_bike_1777509822533_mesh.glb"
    if not cat1.is_file():
        g.ok = True
        g.detail = "skipped (no Cat 1 mesh)"
        return g
    body = json.dumps({
        "mesh_path": "output/3d/juan_bike_1777509822533_mesh.glb",
        "kind": "pc_tower",
    }).encode("utf-8")
    req = urllib.request.Request(
        "http://127.0.0.1:3001/api/3d/mesh-score", data=body,
        headers={"Content-Type": "application/json"}, method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            data = json.loads(r.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError) as exc:
        g.detail = f"unreachable: {exc}"
        return g
    if not data.get("ok"):
        g.detail = f"endpoint returned ok=False: {data}"
        return g
    score = data.get("score") or {}
    if score.get("schema") != "aurora.mesh_quality.v1":
        g.detail = f"unexpected schema: {score.get('schema')}"
        return g
    g.ok = True
    g.detail = (
        f"overall={score['overall_score']}, "
        f"retry={score['retry_recommended']}, "
        f"failed_axes={score['failed_axes']}"
    )
    return g


def gate_changelog_in_sync() -> Gate:
    g = Gate("changelog_in_sync")
    rc, out, err = run([sys.executable, ".claude/hooks/gen_changelog.py", "--check"])
    g.ok = rc == 0
    if not g.ok:
        g.detail = (err.strip() or out.strip()).splitlines()[-1] if (out or err) else ""
        return g
    g.detail = "CHANGELOG.md matches git log"
    return g


def gate_visual_audit_honest() -> Gate:
    """Run mesh_visual_audit on the 5 OOD categories. Reports the gap
    between the proxy quality_score and the honest visual_grade so it
    cannot be hidden again. Always passes (this is signal, not gate),
    detail field shows the gap per category."""
    g = Gate("visual_audit_honest")
    # v80af: prefer the *_split_k4 variants (UV+materials+textures+parts=4,
    # visual_grade 100). Fall back to *_textured (visual_grade 80) then to
    # raw baked (visual_grade ≤ 20). Each gate run picks the best available
    # so we never silently regress.
    def _pick3(split: str, textured: str, baked: str) -> str:
        for cand in (split, textured, baked):
            if (REPO_ROOT / cand).is_file():
                return cand
        return baked
    cats = [
        ("Cat1", _pick3(
            "application/output/3d/v80x_cat1_test/cat1_test_split_k4.glb",
            "application/output/3d/v80x_cat1_test/cat1_test_mesh_textured.glb",
            "application/output/3d/v80x_cat1_test/cat1_test_mesh_baked.glb")),
        ("Cat2", _pick3(
            "application/output/3d/v80x_cat2_perso_mv/cat2_perso_mv_split_k4.glb",
            "application/output/3d/v80x_cat2_perso_mv/cat2_perso_mv_mesh_textured.glb",
            "application/output/3d/v80x_cat2_perso_mv/cat2_perso_mv_mesh_reshaped.glb")),
        ("Cat3", _pick3(
            "application/output/3d/v80x_cat3_meca/cat3_meca_split_k4.glb",
            "application/output/3d/v80x_cat3_meca/cat3_meca_mesh_textured.glb",
            "application/output/3d/v80x_cat3_meca/cat3_meca_mesh_baked.glb")),
        ("Cat4", _pick3(
            "application/output/3d/v80x_cat4_objet_mv/cat4_objet_mv_split_k4.glb",
            "application/output/3d/v80x_cat4_objet_mv/cat4_objet_mv_mesh_textured.glb",
            "application/output/3d/v80x_cat4_objet_mv/cat4_objet_mv_mesh_baked.glb")),
        ("Cat5", _pick3(
            "application/output/3d/v80x_cat5_jellopus/cat5_jellopus_split_k4.glb",
            "application/output/3d/v80x_cat5_jellopus/cat5_jellopus_mesh_textured.glb",
            "application/output/3d/v80x_cat5_jellopus/cat5_jellopus_mesh_baked.glb")),
    ]
    sys.path.insert(0, str(REPO_ROOT / "application" / "python-services"))
    try:
        from mesh_visual_audit import audit  # type: ignore
    except ImportError as exc:
        g.detail = f"audit import failed: {exc}"
        return g
    parts: list[str] = []
    for label, rel in cats:
        path = REPO_ROOT / rel
        if not path.is_file():
            parts.append(f"{label}=missing")
            continue
        r = audit(path)
        if r.get("ok"):
            parts.append(f"{label}={r['visual_grade']}")
        else:
            parts.append(f"{label}=err")
    g.ok = True
    g.detail = " ".join(parts) + " (visual_grade /100; honest audit)"
    return g


def gate_motion_files_present() -> Gate:
    """Lock down the v80z/v80aa motion injection results — every rigged
    *_anim*.glb produced by glb_animation_injector must still have a
    valid animations array with ≥1 channel. Catches a future change to
    the injector that silently strips animations on existing outputs."""
    g = Gate("motion_files_present")
    expected = [
        ("Cat 2 walk", "application/output/3d/cat2_perso_mv_RIGGED_walking_anim_v3.glb",  8),
        ("Cat 3 rot",  "application/output/3d/cat3_meca_RIGGED_rotating_v2_anim.glb",     1),
        ("Cat 4 rot",  "application/output/3d/cat4_objet_RIGGED_rotating_v2_anim.glb",    1),
        ("Cat 5 mot",  "application/output/3d/cat5_jellopus_RIGGED_anim.glb",             1),
    ]
    issues: list[str] = []
    summary: list[str] = []
    import struct as _s
    for label, rel_path, min_channels in expected:
        path = REPO_ROOT / rel_path
        if not path.is_file():
            issues.append(f"{label}: missing {rel_path}")
            continue
        try:
            with open(path, "rb") as f:
                f.seek(12)
                json_len, _ = _s.unpack("<II", f.read(8))
                gltf = json.loads(f.read(json_len).rstrip(b"\x00"))
        except (OSError, ValueError) as exc:
            issues.append(f"{label}: parse error — {exc}")
            continue
        anims = gltf.get("animations") or []
        n_chan = sum(len(a.get("channels") or []) for a in anims)
        if not anims:
            issues.append(f"{label}: animations=0 (regression!)")
        elif n_chan < min_channels:
            issues.append(f"{label}: only {n_chan} channels (expected ≥{min_channels})")
        else:
            summary.append(f"{label}={n_chan}ch")
    if issues:
        g.detail = "; ".join(issues)
        return g
    g.ok = True
    g.detail = " ".join(summary)
    return g


def gate_handoff_render() -> Gate:
    """Verify aurora_handoff.py renders cleanly to stdout. Catches
    breakage in any embedded section (watchdog snapshot, tracker block,
    3D run index, known_state) before it taints HANDOFF.md on next regen.

    Sets AURORA_HANDOFF_SKIP_SELFTEST=1 so the embedded `## Self-test`
    section short-circuits (otherwise handoff → selftest → gate_handoff
    → handoff infinite recursion)."""
    g = Gate("handoff_render")
    import os as _os
    env = {**_os.environ, "AURORA_HANDOFF_SKIP_SELFTEST": "1"}
    try:
        proc = subprocess.run(
            [sys.executable, ".claude/hooks/aurora_handoff.py", "--stdout"],
            cwd=str(REPO_ROOT), capture_output=True, timeout=60, check=False,
            env=env,
        )
    except subprocess.TimeoutExpired:
        g.detail = "handoff render timed out"
        return g
    out = (proc.stdout or b"").decode("utf-8", errors="replace")
    err = (proc.stderr or b"").decode("utf-8", errors="replace")
    if proc.returncode != 0:
        last = (err.strip() or out.strip()).splitlines()[-1] if (out or err) else ""
        g.detail = last or f"exit {proc.returncode}"
        return g
    required = (
        "# AuroraIA-v2 — handoff snapshot",
        "## HEAD",
        "## Live ops snapshot",
        "## Agent tracker",
        "## What's reliably true today",
    )
    missing = [s for s in required if s not in out]
    if missing:
        g.detail = f"missing sections: {missing}"
        return g
    g.ok = True
    g.detail = f"{len(out):,} chars, {len(required)} sections"
    return g


def gate_dashboard_render() -> Gate:
    g = Gate("dashboard_render")
    rc, _, err = run([sys.executable, ".claude/hooks/aurora_dashboard.py"])
    if rc != 0:
        g.detail = err.strip().splitlines()[-1] if err else ""
        return g
    out_path = REPO_ROOT / ".claude" / "agent-tracker" / "dashboard.html"
    if not out_path.is_file():
        g.detail = "dashboard.html not produced"
        return g
    size = out_path.stat().st_size
    if size < 2000:
        g.detail = f"dashboard.html suspiciously small: {size} bytes"
        return g
    body = out_path.read_text(encoding="utf-8")
    has_score_section = "Score progression" in body
    has_sparkline = "<polyline" in body or "no rescue events" in body
    has_coverage = "Agent coverage" in body
    has_axis_lifts = "Axis lifts" in body or '"axis_lifts": {}' in body
    if not has_score_section:
        g.detail = "dashboard missing 'Score progression' section"
        return g
    if not has_sparkline:
        g.detail = "dashboard score progression section has no sparklines"
        return g
    if not has_coverage:
        g.detail = "dashboard missing 'Agent coverage' section"
        return g
    if not has_axis_lifts:
        g.detail = "dashboard missing axis-lifts chart"
        return g
    g.ok = True
    g.detail = f"{size} bytes (score+coverage+axis-lifts)"
    return g


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
    except (AttributeError, ValueError):
        pass

    sys.stdout.write("[aurora-self-test] running 35 gates...\n")
    gates = [
        gate_validate_agents(),
        gate_test_hooks(),
        gate_test_route_test(),
        gate_bridge_doctor(),
        gate_agents_list_endpoint(),
        gate_route_test_endpoint(),
        gate_mesh_score_endpoint(),
        gate_auto_validate_endpoint(),
        gate_color_diagnostic_endpoint(),
        gate_bake_colors_endpoint(),
        gate_auto_rescue_endpoint(),
        gate_mesh_compare_endpoint(),
        gate_viewer_html_endpoint(),
        gate_run_index_endpoint(),
        gate_score_history_endpoint(),
        gate_tracker_health_endpoint(),
        gate_tracker_health_unit(),
        gate_watchdog_render(),
        gate_watchdog_endpoint(),
        gate_coverage_endpoint(),
        gate_coverage_unit(),
        gate_dispatches_endpoint(),
        gate_dispatches_unit(),
        gate_attribution_unit(),
        gate_mesh_logic_unit(),
        gate_ts_tests(),
        gate_motion_baker_self_test(),
        gate_motion_parser_self_test(),
        gate_motion_parity(),
        gate_metrics(),
        gate_changelog_in_sync(),
        gate_dashboard_render(),
        gate_handoff_render(),
        gate_motion_files_present(),
        gate_visual_audit_honest(),
    ]
    for g in gates:
        sys.stdout.write(repr(g) + "\n")
    failed = [g for g in gates if not g.ok]
    if failed:
        sys.stdout.write(f"\n[aurora-self-test] FAIL — {len(failed)}/{len(gates)} gate(s) failed.\n")
        return 1
    sys.stdout.write(f"\n[aurora-self-test] PASS — all {len(gates)} gates green.\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
