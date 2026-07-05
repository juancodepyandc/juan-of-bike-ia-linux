#!/usr/bin/env python
"""Aurora /aurora-env — verify the environment can actually run the system.

Checks every external dependency the rescue toolchain + agent system rely
on, in a single shot, with PASS / WARN / FAIL per check. No fixes — this
is a diagnose-only tool. Prints a single line per check + a summary.

Checks (each independent, none aborts the run):
   1. Python version >= 3.12         (mesh tooling uses 3.12+ stdlib)
   2. Node version >= 22             (--experimental-strip-types --test)
   3. trimesh + numpy + Pillow       (mesh quality / bake / diagnostic)
   4. Disk free >= 10 GiB on repo    (Aurora outputs can be ~50 MB / mesh)
   5. Bridge HTTP /api/health        (rescue endpoints rely on it)
   6. Ollama HTTP 11434 /api/tags    (LLM-driven flows)
   7. ComfyUI HTTP 8188 (port-only)  (FLUX reference generation)
   8. Git repo OK                    (`git rev-parse --is-inside-work-tree`)
   9. core.hooksPath = .claude/git-hooks
  10. .claude/agents directory has >= 30 .md files
  11. Aurora core scripts present   (tracker/coverage/watchdog/query/rescue/pipeline)

Exit 0 when all PASS or WARN, 1 if any FAIL.

Usage:
    python .claude/hooks/aurora_env_check.py
    python .claude/hooks/aurora_env_check.py --json
"""

from __future__ import annotations

import argparse
import json
import shutil
import socket
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]


class Check:
    __slots__ = ("name", "level", "detail")

    def __init__(self, name: str) -> None:
        self.name = name
        self.level = "FAIL"
        self.detail = ""

    def to_dict(self) -> dict:
        return {"name": self.name, "level": self.level, "detail": self.detail}

    def __repr__(self) -> str:
        marker = {"PASS": "ok  ", "WARN": "warn", "FAIL": "FAIL"}.get(self.level, "????")
        return f"  [{marker}] {self.name:<28} {self.detail}"


def run(cmd: list[str], timeout: int = 10) -> tuple[int, str, str]:
    proc = subprocess.run(
        cmd, cwd=str(REPO_ROOT),
        capture_output=True, timeout=timeout, check=False,
    )
    return (
        proc.returncode,
        (proc.stdout or b"").decode("utf-8", errors="replace"),
        (proc.stderr or b"").decode("utf-8", errors="replace"),
    )


def check_python() -> Check:
    c = Check("python_version")
    v = sys.version_info
    c.detail = f"{v.major}.{v.minor}.{v.micro}"
    if (v.major, v.minor) >= (3, 12):
        c.level = "PASS"
    else:
        c.level = "FAIL"
        c.detail += " (need >= 3.12)"
    return c


def check_node() -> Check:
    c = Check("node_version")
    rc, out, _ = run(["node", "--version"])
    if rc != 0:
        c.level = "FAIL"
        c.detail = "node not found in PATH"
        return c
    raw = out.strip().lstrip("v")
    c.detail = f"v{raw}"
    try:
        major = int(raw.split(".")[0])
        if major >= 22:
            c.level = "PASS"
        else:
            c.level = "FAIL"
            c.detail += " (need >= 22 for --experimental-strip-types --test)"
    except (ValueError, IndexError):
        c.level = "WARN"
        c.detail += " (could not parse major version)"
    return c


def check_python_deps() -> Check:
    c = Check("python_mesh_deps")
    missing: list[str] = []
    found: list[str] = []
    for module, label in (("trimesh", "trimesh"), ("numpy", "numpy"), ("PIL", "Pillow")):
        try:
            mod = __import__(module)
            ver = getattr(mod, "__version__", "?")
            found.append(f"{label}={ver}")
        except ImportError:
            missing.append(label)
    if missing:
        c.level = "FAIL"
        c.detail = f"missing: {', '.join(missing)} (pip install {' '.join(missing)})"
    else:
        c.level = "PASS"
        c.detail = ", ".join(found)
    return c


def check_disk_free() -> Check:
    c = Check("disk_free")
    try:
        usage = shutil.disk_usage(str(REPO_ROOT))
        free_gib = usage.free / (1024 ** 3)
        c.detail = f"{free_gib:.1f} GiB free"
        if free_gib >= 10:
            c.level = "PASS"
        elif free_gib >= 2:
            c.level = "WARN"
            c.detail += " (low for 3D outputs)"
        else:
            c.level = "FAIL"
            c.detail += " (need >= 2 GiB for safe operations)"
    except OSError as exc:
        c.level = "FAIL"
        c.detail = f"disk_usage failed: {exc}"
    return c


def check_http(name: str, url: str, timeout: float = 3.0,
               ok_levels: tuple[str, ...] = ("PASS",)) -> Check:
    c = Check(name)
    try:
        with urllib.request.urlopen(url, timeout=timeout) as r:
            c.level = ok_levels[0]
            c.detail = f"{url} → {r.status}"
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        c.level = "WARN" if "WARN" in ok_levels else "FAIL"
        c.detail = f"{url} unreachable: {str(exc)[:80]}"
    return c


def check_port_open(name: str, host: str, port: int) -> Check:
    """For services where we don't have an HTTP probe (e.g. ComfyUI's /
    landing might be HTML)."""
    c = Check(name)
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(2.0)
    try:
        s.connect((host, port))
        s.close()
        c.level = "PASS"
        c.detail = f"{host}:{port} accepting connections"
    except (ConnectionRefusedError, socket.timeout, OSError) as exc:
        c.level = "WARN"  # downstream services optional for unit tests
        c.detail = f"{host}:{port} closed ({str(exc)[:60]})"
    return c


def check_git() -> Check:
    c = Check("git_repo")
    rc, out, _ = run(["git", "rev-parse", "--is-inside-work-tree"])
    if rc == 0 and out.strip() == "true":
        c.level = "PASS"
        c.detail = "inside a git work tree"
    else:
        c.level = "FAIL"
        c.detail = "not a git work tree"
    return c


def check_hooks_path() -> Check:
    c = Check("git_hooks_path")
    rc, out, _ = run(["git", "config", "--get", "core.hooksPath"])
    val = out.strip()
    if rc == 0 and val == ".claude/git-hooks":
        c.level = "PASS"
        c.detail = ".claude/git-hooks (Aurora hooks active)"
    else:
        c.level = "WARN"
        c.detail = (
            f"set to '{val or '(unset)'}' — run "
            "`git config core.hooksPath .claude/git-hooks` to enable"
        )
    return c


def check_aurora_scripts() -> Check:
    """Every script referenced by selftest gates must be present. Catches
    botched checkouts or accidental deletions before downstream gates
    fail in confusing ways."""
    c = Check("aurora_scripts")
    required = {
        # Tracker layer
        ".claude/hooks/track_agent_dispatch.py": "tracker write hook",
        ".claude/hooks/tracker_health.py": "stale-task watchdog + archive",
        ".claude/hooks/tracker_query.py": "dispatch query",
        ".claude/hooks/agent_metrics.py": "per-lead aggregates",
        ".claude/hooks/agent_coverage.py": "declared-vs-dispatched",
        ".claude/hooks/aurora_watchdog.py": "consolidated ops view",
        # 3D toolchain attribution
        "application/python-services/tracker_helper.py": "Python → tracker bridge",
        "application/python-services/score_history.py": "score event log",
        "application/python-services/auto_rescue_mesh.py": "rescue chain",
        "application/python-services/aurora_3d_pipeline.py": "end-to-end pipeline",
    }
    missing: list[str] = []
    for rel, _label in required.items():
        if not (REPO_ROOT / rel).is_file():
            missing.append(rel)
    if missing:
        c.level = "FAIL"
        c.detail = f"missing {len(missing)}/{len(required)}: {missing[0]}" + (
            f" (+{len(missing) - 1} more)" if len(missing) > 1 else ""
        )
    else:
        c.level = "PASS"
        c.detail = f"all {len(required)} core scripts present"
    return c


def check_agents_dir() -> Check:
    c = Check("agents_directory")
    d = REPO_ROOT / ".claude" / "agents"
    if not d.is_dir():
        c.level = "FAIL"
        c.detail = "missing .claude/agents/"
        return c
    md_count = sum(
        1 for p in d.iterdir()
        if p.suffix == ".md" and p.name not in ("README.md", "EXAMPLES.md")
    )
    c.detail = f"{md_count} agent .md files"
    if md_count >= 30:
        c.level = "PASS"
    elif md_count >= 10:
        c.level = "WARN"
        c.detail += " (expected >= 30 in v78+)"
    else:
        c.level = "FAIL"
        c.detail += " (expected >= 30)"
    return c


def main() -> int:
    parser = argparse.ArgumentParser(description="Aurora environment readiness")
    parser.add_argument("--json", action="store_true",
                        help="Emit JSON instead of human-readable output")
    args = parser.parse_args()
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
    except (AttributeError, ValueError):
        pass

    checks: list[Check] = [
        check_python(),
        check_node(),
        check_python_deps(),
        check_disk_free(),
        check_http("bridge_health", "http://127.0.0.1:3001/api/health", timeout=3.0),
        check_http("ollama_tags", "http://127.0.0.1:11434/api/tags",
                   timeout=2.0, ok_levels=("PASS", "WARN")),
        check_port_open("comfyui_port", "127.0.0.1", 8188),
        check_git(),
        check_hooks_path(),
        check_agents_dir(),
        check_aurora_scripts(),
    ]

    if args.json:
        sys.stdout.write(json.dumps(
            {"checks": [c.to_dict() for c in checks]},
            indent=2, ensure_ascii=True,
        ) + "\n")
    else:
        sys.stdout.write("[aurora-env] running 11 environment checks...\n")
        for c in checks:
            sys.stdout.write(repr(c) + "\n")
        fails = sum(1 for c in checks if c.level == "FAIL")
        warns = sum(1 for c in checks if c.level == "WARN")
        passes = sum(1 for c in checks if c.level == "PASS")
        if fails:
            sys.stdout.write(
                f"\n[aurora-env] FAIL — {fails} fail, {warns} warn, {passes} pass\n"
            )
        else:
            sys.stdout.write(
                f"\n[aurora-env] OK — {warns} warn, {passes} pass "
                f"(warnings non-blocking)\n"
            )

    return 1 if any(c.level == "FAIL" for c in checks) else 0


if __name__ == "__main__":
    sys.exit(main())
