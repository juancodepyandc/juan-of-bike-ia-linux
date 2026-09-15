#!/usr/bin/env python3
"""ephemeral_tool_sandbox.py — Environnement d'execution d'outils ephemeres avec nettoyage automatique.

Permet aux agents (Conversation, Cyber, Academique, Cowork) d'installer temporairement des outils,
d'executer des calculs ou analyses specialisees, de recuperer les fichiers produits, puis de
desinstaller et purger l'environnement pour eviter toute surcharge de l'hote.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any, Dict, List, Optional


class EphemeralToolSandbox:
    def __init__(self, name: str, base_dir: Optional[str] = None, auto_cleanup: bool = True):
        self.name = name
        self.auto_cleanup = auto_cleanup
        self.timestamp = int(time.time() * 1000)
        self.root_dir = Path(base_dir) if base_dir else Path(tempfile.gettempdir()) / f"aurora_ephemeral_{name}_{self.timestamp}"
        self.pkg_dir = self.root_dir / "packages"
        self.work_dir = self.root_dir / "workspace"
        self.output_dir = self.root_dir / "output"

    def __enter__(self):
        self.setup()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.auto_cleanup:
            self.cleanup()

    def setup(self) -> None:
        self.pkg_dir.mkdir(parents=True, exist_ok=True)
        self.work_dir.mkdir(parents=True, exist_ok=True)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def install_packages(self, packages: List[str], timeout_s: int = 180) -> Dict[str, Any]:
        if not packages:
            return {"ok": True, "installed": []}
        
        cmd = [
            sys.executable, "-m", "pip", "install",
            "--no-warn-script-location",
            "--target", str(self.pkg_dir),
            *packages
        ]
        
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout_s)
        return {
            "ok": proc.returncode == 0,
            "installed": packages if proc.returncode == 0 else [],
            "stdout": proc.stdout,
            "stderr": proc.stderr,
            "returncode": proc.returncode,
        }

    def execute_script(self, script_code: str, env_vars: Optional[Dict[str, str]] = None, timeout_s: int = 120) -> Dict[str, Any]:
        script_file = self.work_dir / "ephemeral_task.py"
        script_file.write_text(script_code, encoding="utf-8")
        
        env = os.environ.copy()
        existing_pp = env.get("PYTHONPATH", "")
        env["PYTHONPATH"] = f"{self.pkg_dir}:{existing_pp}" if existing_pp else str(self.pkg_dir)
        env["AURORA_OUTPUT_DIR"] = str(self.output_dir)
        if env_vars:
            env.update(env_vars)

        start = time.time()
        proc = subprocess.run(
            [sys.executable, str(script_file)],
            cwd=str(self.work_dir),
            env=env,
            capture_output=True,
            text=True,
            timeout=timeout_s
        )
        elapsed = time.time() - start

        produced_files = []
        for p in self.output_dir.glob("**/*"):
            if p.is_file():
                produced_files.append({
                    "name": p.name,
                    "relpath": str(p.relative_to(self.output_dir)),
                    "size": p.stat().st_size,
                    "path": str(p),
                })

        return {
            "ok": proc.returncode == 0,
            "stdout": proc.stdout,
            "stderr": proc.stderr,
            "returncode": proc.returncode,
            "elapsed_s": round(elapsed, 3),
            "produced_files": produced_files,
        }

    def cleanup(self) -> bool:
        try:
            if self.root_dir.exists():
                shutil.rmtree(self.root_dir, ignore_errors=True)
            return True
        except Exception:
            return False


def run_ephemeral_tool(
    name: str,
    packages: Optional[List[str]] = None,
    script_code: str = "",
    cleanup: bool = True,
    timeout_s: int = 180,
) -> Dict[str, Any]:
    with EphemeralToolSandbox(name=name, auto_cleanup=cleanup) as sandbox:
        install_res = sandbox.install_packages(packages or [], timeout_s=timeout_s)
        if not install_res["ok"]:
            return {
                "ok": False,
                "error": f"Echec installation paquets: {install_res['stderr']}",
                "install_details": install_res,
            }
        
        exec_res = sandbox.execute_script(script_code, timeout_s=timeout_s)
        return {
            "ok": exec_res["ok"],
            "stdout": exec_res["stdout"],
            "stderr": exec_res["stderr"],
            "produced_files": exec_res["produced_files"],
            "elapsed_s": exec_res["elapsed_s"],
            "cleaned_up": cleanup,
        }


def main():
    parser = argparse.ArgumentParser(description="Execution d'outil ephemere avec isolation et nettoyage automatique.")
    parser.add_argument("--name", type=str, default="ephemeral_job")
    parser.add_argument("--packages", nargs="*", default=[])
    parser.add_argument("--script", type=str, default="")
    parser.add_argument("--script-file", type=str, default=None)
    parser.add_argument("--no-cleanup", action="store_true")
    parser.add_argument("--timeout", type=int, default=180)
    args = parser.parse_args()

    code = args.script
    if args.script_file and Path(args.script_file).exists():
        code = Path(args.script_file).read_text(encoding="utf-8")

    result = run_ephemeral_tool(
        name=args.name,
        packages=args.packages,
        script_code=code,
        cleanup=not args.no_cleanup,
        timeout_s=args.timeout,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
