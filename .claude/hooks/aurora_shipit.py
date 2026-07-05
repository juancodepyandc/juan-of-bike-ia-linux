#!/usr/bin/env python
"""Aurora /aurora-ship-it — pre-ship verification.

Runs every gate that matters before shipping a commit + checks the working
tree state. Single PASS/FAIL with human-readable detail for each gate.

Gates (additive over /aurora-self-test):
  1-17. All /aurora-self-test gates (lint, hooks tests, route tests, bridge
        endpoints, metrics, changelog, dashboard).
  18.   git working tree is clean of code changes (only session artifacts).
  19.   HEAD is reachable from origin/main (i.e. pushed).
  20.   meshRescue.ts node --test passes (13 tests).

Exit 0 if all green, 1 otherwise. Output mirrors aurora_selftest's table
format so the user can spot which gate failed at a glance.
"""

from __future__ import annotations

import json
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
SESSION_ARTIFACT_PATHS = (
    ".claude/agent-tracker/state.json",
    ".claude/settings.local.json",
    ".claude/scheduled_tasks.lock",
    ".claude/scheduled_tasks.json",
    ".claude/bridge.out.log",
    ".claude/agent-tracker/dashboard.html",
)


class Gate:
    __slots__ = ("name", "ok", "detail")

    def __init__(self, name: str) -> None:
        self.name = name
        self.ok = False
        self.detail = ""

    def __repr__(self) -> str:
        marker = "ok " if self.ok else "FAIL"
        return f"  [{marker}] {self.name:<28} {self.detail}"


def run(cmd: list[str], timeout: int = 60) -> tuple[int, str, str]:
    proc = subprocess.run(
        cmd, cwd=str(REPO_ROOT),
        capture_output=True, timeout=timeout, check=False,
    )
    out = (proc.stdout or b"").decode("utf-8", errors="replace")
    err = (proc.stderr or b"").decode("utf-8", errors="replace")
    return proc.returncode, out, err


def gate_self_test() -> Gate:
    # 35-gate self-test takes 4-5 minutes on a healthy box — the heavy hitters
    # are the 3D bridge endpoints (mesh_score, bake_colors, auto_rescue,
    # auto_validate) which run real Hunyuan3D / DreamGaussian / blender ops,
    # plus the cold-start of `node --experimental-strip-types --test` which
    # compiles ts on the fly. The previous 60 s / 240 s timeouts both crashed
    # the wrapper. 480 s is comfortable headroom.
    g = Gate("self_test_35_gates")
    rc, out, _ = run([sys.executable, ".claude/hooks/aurora_selftest.py"], timeout=480)
    g.ok = rc == 0 and "PASS" in out
    last = [line for line in out.splitlines() if "PASS" in line or "FAIL" in line]
    g.detail = last[-1].strip() if last else "(no output)"
    return g


def gate_ts_tests() -> Gate:
    # Same cold-start risk as selftest — node strip-types compiles TS on first
    # invocation which can take 30-60 s. 120 s headroom.
    g = Gate("typescript_meshRescue")
    rc, out, err = run([
        "node", "--experimental-strip-types", "--test",
        "application/src/__tests__/meshRescue.test.ts",
    ], timeout=120)
    g.ok = rc == 0
    last = [line for line in (err.strip() or out.strip()).splitlines()
            if "pass" in line.lower() or "fail" in line.lower()]
    g.detail = last[-1].strip() if last else "(no output)"
    return g


def gate_tree_clean() -> Gate:
    g = Gate("git_tree_clean")
    rc, out, _ = run(["git", "-C", str(REPO_ROOT), "status", "--porcelain"])
    if rc != 0:
        g.detail = "git status failed"
        return g
    dirty: list[str] = []
    for line in out.splitlines():
        if not line.strip():
            continue
        path = line[3:].strip()
        if path in SESSION_ARTIFACT_PATHS:
            continue
        if line.startswith("??"):
            # Untracked is fine — won't be wiped by anything.
            continue
        dirty.append(path)
    if dirty:
        g.detail = f"dirty: {dirty[:3]}{' …' if len(dirty) > 3 else ''}"
        return g
    g.ok = True
    g.detail = "no code changes (only session artifacts allowed)"
    return g


def gate_pushed() -> Gate:
    g = Gate("head_pushed_to_origin")
    rc_fetch, _, err_fetch = run(["git", "-C", str(REPO_ROOT), "fetch", "origin", "main"], timeout=30)
    if rc_fetch != 0:
        g.detail = f"git fetch failed: {err_fetch.strip()[:120]}"
        return g
    rc, _, _ = run([
        "git", "-C", str(REPO_ROOT),
        "merge-base", "--is-ancestor", "HEAD", "origin/main",
    ])
    if rc != 0:
        g.detail = "HEAD not reachable from origin/main — push first"
        return g
    rc2, out, _ = run(["git", "-C", str(REPO_ROOT), "rev-parse", "--short=7", "HEAD"])
    sha = out.strip()
    g.ok = True
    g.detail = f"HEAD {sha} on origin/main"
    return g


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
    except (AttributeError, ValueError):
        pass

    sys.stdout.write("[aurora-ship-it] running pre-ship gates...\n")
    gates = [
        gate_self_test(),
        gate_ts_tests(),
        gate_tree_clean(),
        gate_pushed(),
    ]
    for g in gates:
        sys.stdout.write(repr(g) + "\n")
    failed = [g for g in gates if not g.ok]
    if failed:
        sys.stdout.write(
            f"\n[aurora-ship-it] BLOCK — {len(failed)}/{len(gates)} gate(s) failed.\n"
        )
        return 1
    sys.stdout.write(
        f"\n[aurora-ship-it] GO — all {len(gates)} pre-ship gates green.\n"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
