"""Adaptive per-project_type validators for the aurora code-loop.

Each validator takes a pack_dir (Path) and returns a dict:
    {ok: bool, score: float [0..1], flags: list[str], info: dict}

Some validators run the project (npm install + build, python --help, curl
an Express endpoint, etc.). They are best-effort: a runtime failure
contributes flags but never crashes the loop.
"""
from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
import time
from pathlib import Path


def _free_port() -> int:
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    p = s.getsockname()[1]
    s.close()
    return p


def _run(cmd: list[str], cwd: Path, timeout: float, env: dict | None = None,
            shell: bool = False) -> dict:
    """Run a command. On Windows, npm/node/npx/pip live as .cmd shims that
    plain CreateProcess does not resolve; pass shell=True for those.
    """
    try:
        if shell:
            cmd_str = subprocess.list2cmdline(cmd)
            proc = subprocess.run(cmd_str, cwd=str(cwd), capture_output=True,
                                    text=True, timeout=timeout,
                                    env=env or os.environ.copy(), shell=True)
        else:
            proc = subprocess.run(cmd, cwd=str(cwd), capture_output=True, text=True,
                                    timeout=timeout, env=env or os.environ.copy())
        return {"rc": proc.returncode, "stdout": proc.stdout[-2000:], "stderr": proc.stderr[-2000:]}
    except subprocess.TimeoutExpired:
        return {"rc": -1, "stdout": "", "stderr": "TIMEOUT"}
    except FileNotFoundError as e:
        return {"rc": -2, "stdout": "", "stderr": f"NOT_FOUND: {e}"}


def _is_windows() -> bool:
    return sys.platform.startswith("win")


# ---------------------------------------------------------------------------
# static_web*: rely on the loop's CDP screenshot + runtime report. Adds
# stricter checks: console errors and exceptions count, canvas presence for
# 3D/game/sim, body content length.
# ---------------------------------------------------------------------------

def validate_static_web(pack_dir: Path, runtime_report: dict | None,
                          project_type: str) -> dict:
    flags: list[str] = []
    score_components: list[float] = []
    info = {"runtime_report_available": runtime_report is not None}
    if runtime_report and runtime_report.get("ok"):
        errs = runtime_report.get("exceptions", [])
        console_errs = runtime_report.get("console_errors", [])
        failed = runtime_report.get("failed_requests", [])
        canvas = runtime_report.get("canvas_present", False)
        body_len = runtime_report.get("body_text_len", 0)
        info.update({
            "exceptions": len(errs),
            "console_errors": len(console_errs),
            "failed_requests": len(failed),
            "canvas": canvas,
            "body_len": body_len,
        })
        if errs:
            flags.append(f"runtime_exceptions:{len(errs)}")
            score_components.append(max(0.0, 1.0 - len(errs) * 0.25))
        else:
            score_components.append(1.0)
        if len(console_errs) > 2:
            flags.append(f"console_errors:{len(console_errs)}")
            score_components.append(max(0.3, 1.0 - len(console_errs) * 0.1))
        else:
            score_components.append(1.0)
        if len(failed) > 0:
            flags.append(f"failed_requests:{len(failed)}")
            score_components.append(max(0.4, 1.0 - len(failed) * 0.2))
        else:
            score_components.append(1.0)
        if project_type in ("static_web_3d", "static_web_game", "static_web_sim", "static_web_2d"):
            if not canvas:
                flags.append("expected_canvas_missing")
                score_components.append(0.4)
            else:
                score_components.append(1.0)
        if body_len < 80 and project_type not in ("static_web_3d", "static_web_game", "static_web_sim"):
            flags.append("body_too_short")
            score_components.append(0.6)
        else:
            score_components.append(1.0)
    else:
        flags.append("runtime_report_missing")
        score_components.append(0.4)
    avg = sum(score_components) / max(1, len(score_components))
    return {"ok": not flags, "score": round(avg, 3), "flags": flags, "info": info}


# ---------------------------------------------------------------------------
# react_vite: npm install + npm run build, serve dist/, the CDP screenshot
# in the main loop will then probe the built output.
# ---------------------------------------------------------------------------

def validate_react_vite(pack_dir: Path) -> dict:
    """Isolate the project to a temp dir outside any parent tsconfig before
    running install + build. Otherwise tsc walks up and compiles the parent
    repo's src/ (saw 30+ errors from AuroraIA-v2 main app leaking in)."""
    import shutil
    import tempfile
    project = pack_dir / "project"
    pkg = project / "package.json"
    flags: list[str] = []
    info: dict = {}
    if not pkg.exists():
        flags.append("no_package_json")
        return {"ok": False, "score": 0.2, "flags": flags, "info": info}

    tmp_root = Path(tempfile.mkdtemp(prefix="aurora_react_build_"))
    work = tmp_root / "proj"
    shutil.copytree(project, work)
    info["isolated_dir"] = str(work)
    install = _run(["npm", "install", "--silent", "--no-audit", "--no-fund",
                     "--prefer-offline", "--loglevel=error"], work, timeout=240,
                     shell=_is_windows())
    info["install"] = {"rc": install["rc"], "stderr_tail": install["stderr"][-400:]}
    if install["rc"] != 0:
        flags.append("npm_install_failed")
        info["install_stderr"] = install["stderr"][-600:]
        return {"ok": False, "score": 0.3, "flags": flags, "info": info}
    build = _run(["npm", "run", "build", "--silent"], work, timeout=180,
                   shell=_is_windows())
    info["build"] = {"rc": build["rc"],
                       "stderr_tail": build["stderr"][-1200:],
                       "stdout_tail": build["stdout"][-400:]}
    if build["rc"] != 0:
        flags.append("vite_build_failed")
        return {"ok": False, "score": 0.45, "flags": flags, "info": info}
    dist = work / "dist"
    if not (dist / "index.html").exists():
        flags.append("no_dist_index")
        return {"ok": False, "score": 0.55, "flags": flags, "info": info}
    # copy dist back into the pack so the loop can serve it
    final_dist = project / "dist"
    if final_dist.exists():
        import shutil as _sh
        _sh.rmtree(final_dist, ignore_errors=True)
    import shutil as _sh
    _sh.copytree(dist, final_dist)
    info["dist_index"] = str(final_dist / "index.html")
    return {"ok": True, "score": 0.9, "flags": flags, "info": info}


# ---------------------------------------------------------------------------
# python_cli: run with --help, then a smoke invocation with --dry-run if
# supported. Capture exit codes and output presence.
# ---------------------------------------------------------------------------

def validate_python_cli(pack_dir: Path) -> dict:
    project = pack_dir / "project"
    py_files = list(project.glob("*.py")) + list(project.glob("**/*.py"))
    flags: list[str] = []
    info: dict = {}
    if not py_files:
        flags.append("no_py_files")
        return {"ok": False, "score": 0.2, "flags": flags, "info": info}
    main_py = next((p for p in py_files if p.name in ("main.py", "cli.py", "app.py")), py_files[0])
    info["main"] = str(main_py.relative_to(project))
    help_run = _run([sys.executable, str(main_py), "--help"], project, timeout=30)
    info["help"] = {"rc": help_run["rc"], "out_len": len(help_run["stdout"])}
    if help_run["rc"] != 0:
        flags.append("help_nonzero_exit")
    if len(help_run["stdout"]) < 30:
        flags.append("help_output_too_short")
    if "usage" not in help_run["stdout"].lower() and "options" not in help_run["stdout"].lower():
        flags.append("help_no_usage_or_options")
    score = max(0.0, 1.0 - len(flags) * 0.18)
    return {"ok": not flags, "score": round(score, 3), "flags": flags, "info": info}


# ---------------------------------------------------------------------------
# node_express: npm install, spawn server on free port, curl GET /, kill.
# ---------------------------------------------------------------------------

def validate_node_express(pack_dir: Path) -> dict:
    import urllib.request
    project = pack_dir / "project"
    pkg = project / "package.json"
    flags: list[str] = []
    info: dict = {}
    if not pkg.exists():
        flags.append("no_package_json")
        return {"ok": False, "score": 0.2, "flags": flags, "info": info}
    install = _run(["npm", "install", "--silent", "--no-audit", "--no-fund",
                     "--prefer-offline", "--loglevel=error"], project, timeout=180,
                     shell=_is_windows())
    info["install"] = {"rc": install["rc"]}
    if install["rc"] != 0:
        flags.append("npm_install_failed")
        return {"ok": False, "score": 0.3, "flags": flags, "info": info}
    port = _free_port()
    env = os.environ.copy()
    env["PORT"] = str(port)
    entry = None
    pkg_json = json.loads(pkg.read_text(encoding="utf-8"))
    main_field = pkg_json.get("main") or "index.js"
    for cand in (main_field, "server.js", "app.js", "index.js"):
        if (project / cand).exists():
            entry = cand
            break
    if not entry:
        flags.append("no_entry_file")
        return {"ok": False, "score": 0.35, "flags": flags, "info": info}
    info["entry"] = entry
    if _is_windows():
        proc = subprocess.Popen(subprocess.list2cmdline(["node", entry]),
                                  cwd=str(project), env=env, shell=True,
                                  stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    else:
        proc = subprocess.Popen(["node", entry], cwd=str(project), env=env,
                                  stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    try:
        time.sleep(1.5)
        ok = False
        for path in ("/", "/api/health", "/health", "/api"):
            try:
                with urllib.request.urlopen(f"http://127.0.0.1:{port}{path}", timeout=3) as r:
                    info["probe"] = {"path": path, "status": r.status}
                    if 200 <= r.status < 500:
                        ok = True
                        break
            except Exception:
                continue
        if not ok:
            flags.append("no_response_on_known_paths")
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=4)
        except subprocess.TimeoutExpired:
            proc.kill()
    score = 0.85 if not flags else max(0.4, 0.85 - 0.2 * len(flags))
    return {"ok": not flags, "score": round(score, 3), "flags": flags, "info": info}


# ---------------------------------------------------------------------------
# native_electron / native_python_gui: only structural checks (we don't
# launch a desktop window from this loop).
# ---------------------------------------------------------------------------

def validate_native(pack_dir: Path, project_type: str) -> dict:
    project = pack_dir / "project"
    flags: list[str] = []
    info: dict = {}
    if project_type == "native_electron":
        for f in ("main.js", "package.json", "index.html"):
            if not (project / f).exists():
                flags.append(f"missing_{f}")
        pkg = project / "package.json"
        if pkg.exists():
            try:
                p = json.loads(pkg.read_text(encoding="utf-8"))
                if "electron" not in (p.get("dependencies", {}) | p.get("devDependencies", {})):
                    flags.append("electron_not_in_deps")
                if "main" not in p:
                    flags.append("no_main_in_pkg")
            except Exception:
                flags.append("invalid_package_json")
    elif project_type == "native_python_gui":
        py_files = list(project.glob("*.py"))
        if not py_files:
            flags.append("no_py_files")
        else:
            txt = py_files[0].read_text(encoding="utf-8", errors="ignore")
            if "tkinter" not in txt and "PyQt" not in txt and "kivy" not in txt:
                flags.append("no_known_gui_lib_imported")
    score = max(0.0, 1.0 - len(flags) * 0.2)
    return {"ok": not flags, "score": round(score, 3), "flags": flags, "info": info}


# ---------------------------------------------------------------------------
# Dispatcher
# ---------------------------------------------------------------------------

def validate(project_type: str, pack_dir: Path,
              runtime_report: dict | None = None) -> dict:
    if project_type == "react_vite":
        return validate_react_vite(pack_dir)
    if project_type == "python_cli":
        return validate_python_cli(pack_dir)
    if project_type == "node_express":
        return validate_node_express(pack_dir)
    if project_type in ("native_electron", "native_python_gui"):
        return validate_native(pack_dir, project_type)
    return validate_static_web(pack_dir, runtime_report, project_type)


# ---------------------------------------------------------------------------
# Complexity floor: per-type minimum file count and content size to refuse
# "2-file portfolio" simplistic outputs.
# ---------------------------------------------------------------------------

MIN_FILES: dict[str, int] = {
    "static_web": 2,
    "static_web_3d": 1,        # often 1 big HTML with three.js
    "static_web_game": 1,      # often 1 big canvas HTML
    "static_web_sim": 1,
    "static_web_2d": 1,
    "static_web_dataviz": 2,
    "static_web_edu": 2,
    "react_vite": 5,           # index.html, main.tsx, App.tsx, vite.config, package.json
    "python_cli": 1,
    "node_express": 3,         # index.js, package.json, maybe routes
    "native_electron": 4,      # main.js, preload.js, renderer.js, package.json, index.html
    "native_python_gui": 1,
}

MIN_TOTAL_BYTES: dict[str, int] = {
    "static_web": 3500,
    "static_web_3d": 4500,
    "static_web_game": 5000,
    "static_web_sim": 4500,
    "static_web_2d": 3500,
    "static_web_dataviz": 4000,
    "static_web_edu": 4500,
    "react_vite": 4500,
    "python_cli": 1200,
    "node_express": 2500,
    "native_electron": 3000,
    "native_python_gui": 1500,
}


def complexity_check(pack_dir: Path, project_type: str, files_count: int) -> dict:
    flags = []
    min_files = MIN_FILES.get(project_type, 1)
    min_bytes = MIN_TOTAL_BYTES.get(project_type, 2000)
    project = pack_dir / "project"
    total = 0
    if project.exists():
        for p in project.rglob("*"):
            if p.is_file():
                total += p.stat().st_size
    if files_count < min_files:
        flags.append(f"too_few_files:{files_count}<{min_files}")
    if total < min_bytes:
        flags.append(f"output_too_small:{total}B<{min_bytes}B")
    return {"flags": flags, "files": files_count, "total_bytes": total,
              "needs_expansion": bool(flags)}
