"""Aurora code-loop remote/SSH target support.

Lets the loop deploy generated projects to a remote machine (Raspberry Pi,
Linux VPS, LAN server, etc.) over SSH, run validation there, and pull back
logs / screenshots.

Targets live in JSON:
    ~/.aurora_code_targets.json
or `--targets-file <path>` on the loop CLI.

Schema example:
{
  "my-pi": {
    "host":        "192.168.1.42",
    "user":        "pi",
    "port":        22,
    "key_path":    "~/.ssh/id_ed25519",
    "deploy_path": "/home/pi/aurora_deploys",
    "platform":    "raspberry_pi",
    "platform_hints": "Raspberry Pi 4, ARMv7, Python 3.11, RPi.GPIO + picamera2 available, Bookworm OS",
    "preview_url_base": "http://192.168.1.42:8000"
  },
  "wsl-local": {
    "host":        "127.0.0.1",
    "user":        "juan",
    "port":        2222,
    "deploy_path": "/home/juan/aurora_deploys",
    "platform":    "linux_wsl",
    "platform_hints": "Ubuntu WSL2, Python 3.12, no GPIO"
  },
  "vps": {
    "host":        "vps.example.com",
    "user":        "ubuntu",
    "deploy_path": "/var/www/aurora",
    "platform":    "linux_x86",
    "platform_hints": "Ubuntu 24, Node 20, Python 3.12, public ip, nginx terminate"
  }
}

Uses the platform OpenSSH client (`ssh` / `scp`) via subprocess. No extra
Python dependency is required.
"""
from __future__ import annotations

import json
import os
import subprocess
from dataclasses import dataclass, field
from pathlib import Path


DEFAULT_TARGETS_FILE = Path.home() / ".aurora_code_targets.json"


@dataclass
class Target:
    name: str
    host: str
    user: str
    deploy_path: str
    port: int = 22
    key_path: str | None = None
    platform: str = "linux_x86"
    platform_hints: str = ""
    preview_url_base: str | None = None
    extra: dict = field(default_factory=dict)

    def ssh_args(self) -> list[str]:
        args = ["-p", str(self.port),
                 "-o", "StrictHostKeyChecking=accept-new",
                 "-o", "ConnectTimeout=10",
                 "-o", "ServerAliveInterval=15"]
        if self.key_path:
            args += ["-i", self.key_path]
        return args

    def remote(self) -> str:
        return f"{self.user}@{self.host}"


def load_targets(path: Path | None = None) -> dict[str, Target]:
    path = path or DEFAULT_TARGETS_FILE
    if not path.exists():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    return {
        name: Target(name=name, **{k: v for k, v in cfg.items() if k != "name"})
        for name, cfg in data.items()
    }


def save_targets(targets: dict[str, Target], path: Path | None = None) -> None:
    path = path or DEFAULT_TARGETS_FILE
    out = {}
    for name, t in targets.items():
        d = {"host": t.host, "user": t.user, "deploy_path": t.deploy_path,
              "port": t.port, "platform": t.platform,
              "platform_hints": t.platform_hints}
        if t.key_path:
            d["key_path"] = t.key_path
        if t.preview_url_base:
            d["preview_url_base"] = t.preview_url_base
        if t.extra:
            d["extra"] = t.extra
        out[name] = d
    path.write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")


# ---------------------------------------------------------------------------
# SSH primitives
# ---------------------------------------------------------------------------

def ssh_run(target: Target, command: str, timeout: float = 60.0,
              capture: bool = True) -> dict:
    """Run a shell command on the remote. Returns dict {rc, stdout, stderr}."""
    cmd = ["ssh"] + target.ssh_args() + [target.remote(), command]
    try:
        proc = subprocess.run(cmd, capture_output=capture, text=True, timeout=timeout)
        return {"rc": proc.returncode,
                  "stdout": (proc.stdout or "")[-4000:] if capture else "",
                  "stderr": (proc.stderr or "")[-2000:] if capture else "",
                  "cmd": command}
    except subprocess.TimeoutExpired:
        return {"rc": -1, "stdout": "", "stderr": "TIMEOUT", "cmd": command}


def scp_push(target: Target, local_path: Path, remote_subpath: str,
               recurse: bool = True, timeout: float = 300.0) -> dict:
    """Copy a local file or directory to <deploy_path>/<remote_subpath>."""
    remote = f"{target.remote()}:{target.deploy_path.rstrip('/')}/{remote_subpath.lstrip('/')}"
    args = ["scp"] + (["-r"] if recurse else []) + ["-P", str(target.port)]
    if target.key_path:
        args += ["-i", target.key_path]
    args += ["-o", "StrictHostKeyChecking=accept-new",
              "-o", "ConnectTimeout=10",
              str(local_path), remote]
    try:
        proc = subprocess.run(args, capture_output=True, text=True, timeout=timeout)
        return {"rc": proc.returncode, "stdout": proc.stdout[-1000:],
                  "stderr": proc.stderr[-1000:]}
    except subprocess.TimeoutExpired:
        return {"rc": -1, "stdout": "", "stderr": "TIMEOUT"}


def scp_pull(target: Target, remote_subpath: str, local_path: Path,
               recurse: bool = False, timeout: float = 120.0) -> dict:
    """Pull a remote file back."""
    remote = f"{target.remote()}:{target.deploy_path.rstrip('/')}/{remote_subpath.lstrip('/')}"
    args = ["scp"] + (["-r"] if recurse else []) + ["-P", str(target.port)]
    if target.key_path:
        args += ["-i", target.key_path]
    args += ["-o", "StrictHostKeyChecking=accept-new",
              "-o", "ConnectTimeout=10",
              remote, str(local_path)]
    try:
        proc = subprocess.run(args, capture_output=True, text=True, timeout=timeout)
        return {"rc": proc.returncode, "stdout": proc.stdout[-1000:],
                  "stderr": proc.stderr[-1000:]}
    except subprocess.TimeoutExpired:
        return {"rc": -1, "stdout": "", "stderr": "TIMEOUT"}


# ---------------------------------------------------------------------------
# Deploy + validate
# ---------------------------------------------------------------------------

def deploy(target: Target, project_dir: Path, slug: str) -> dict:
    """Ensure remote deploy_path exists, scp the project tree under it."""
    mk = ssh_run(target, f"mkdir -p {target.deploy_path}/{slug}", timeout=15)
    if mk["rc"] != 0:
        return {"ok": False, "stage": "mkdir", **mk}
    push = scp_push(target, project_dir, slug)
    if push["rc"] != 0:
        return {"ok": False, "stage": "scp", **push}
    return {"ok": True, "remote_path": f"{target.deploy_path}/{slug}"}


def remote_validate_static_web(target: Target, slug: str, port: int = 8765,
                                  duration: float = 5.0) -> dict:
    """Serve project_dir/index.html via python http.server on the target, then
    rely on the caller to CDP-screenshot http://<host>:<port>/index.html .
    Returns the URL to point CDP at.
    """
    remote_dir = f"{target.deploy_path}/{slug}/project"
    # kill any stale server first
    ssh_run(target, f"pkill -f 'http.server {port}' || true", timeout=10)
    # spawn detached background server
    spawn = ssh_run(
        target,
        f"cd {remote_dir} && nohup python3 -m http.server {port} >/tmp/aurora_{slug}_serve.log 2>&1 &",
        timeout=10,
    )
    base = target.preview_url_base or f"http://{target.host}:{port}"
    return {"ok": spawn["rc"] == 0, "url": f"{base}/index.html",
              "remote_dir": remote_dir, "port": port}


def remote_validate_python(target: Target, slug: str, entry: str = "main.py",
                              args: str = "--help") -> dict:
    """Run python3 <entry> <args> on the remote, return rc + output."""
    cmd = f"cd {target.deploy_path}/{slug}/project && python3 {entry} {args}"
    return ssh_run(target, cmd, timeout=30)


def remote_validate_node(target: Target, slug: str, entry: str = "index.js",
                            install: bool = True, probe_port: int = 3000,
                            timeout: float = 240.0) -> dict:
    """Optionally npm install on remote, then start the server in background
    and probe it with curl from the remote (avoids LAN firewall issues).
    """
    proj = f"{target.deploy_path}/{slug}/project"
    if install:
        ins = ssh_run(target,
                       f"cd {proj} && npm install --silent --no-audit --no-fund --loglevel=error",
                       timeout=timeout)
        if ins["rc"] != 0:
            return {"ok": False, "stage": "install", **ins}
    ssh_run(target, f"pkill -f 'node {entry}' || true", timeout=10)
    spawn = ssh_run(
        target,
        f"cd {proj} && PORT={probe_port} nohup node {entry} "
        f">/tmp/aurora_{slug}_node.log 2>&1 &",
        timeout=15,
    )
    if spawn["rc"] != 0:
        return {"ok": False, "stage": "spawn", **spawn}
    import time as _t
    _t.sleep(2.5)
    probe = ssh_run(
        target,
        f"curl -fsS -m 4 http://127.0.0.1:{probe_port}/ "
        f"|| curl -fsS -m 4 http://127.0.0.1:{probe_port}/api/health "
        f"|| curl -fsS -m 4 http://127.0.0.1:{probe_port}/api",
        timeout=12,
    )
    return {"ok": probe["rc"] == 0, "probe": probe}


# ---------------------------------------------------------------------------
# Connectivity smoke test
# ---------------------------------------------------------------------------

def connectivity(target: Target) -> dict:
    """Quick ssh + write probe; report platform info."""
    out = ssh_run(target, "uname -a && python3 --version 2>&1 || true; "
                            "node --version 2>&1 || true; "
                            "echo --DEPLOY_PATH-- && ls -ld " + target.deploy_path,
                    timeout=15)
    return {"ok": out["rc"] == 0, **out}


def enrich_for_target(target: Target | None) -> str:
    if target is None:
        return ""
    hints = target.platform_hints or ""
    return (
        f"\n\nDEPLOYMENT TARGET: {target.name} ({target.platform}). "
        f"Generated code WILL RUN ON THIS REMOTE. Constraints: {hints} "
        f"Deploy path on remote: {target.deploy_path}. "
        f"Use only libraries available on this platform. "
        f"If raspberry_pi: prefer RPi.GPIO/picamera2/lgpio for hardware; "
        f"if linux_x86 server: standard Python/Node stack; "
        f"if linux_wsl: same as linux_x86 but no real hardware GPIO."
    )


# ---------------------------------------------------------------------------
# CLI helper: list / add / test targets
# ---------------------------------------------------------------------------

def main(argv: list[str]) -> int:
    import argparse
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd")
    sub.add_parser("list")
    p_add = sub.add_parser("add")
    p_add.add_argument("name")
    p_add.add_argument("--host", required=True)
    p_add.add_argument("--user", required=True)
    p_add.add_argument("--deploy-path", required=True)
    p_add.add_argument("--port", type=int, default=22)
    p_add.add_argument("--key-path")
    p_add.add_argument("--platform", default="linux_x86")
    p_add.add_argument("--platform-hints", default="")
    p_add.add_argument("--preview-url-base")
    p_test = sub.add_parser("test")
    p_test.add_argument("name")
    args = ap.parse_args(argv[1:])

    targets = load_targets()
    if args.cmd == "list":
        if not targets:
            print(f"no targets in {DEFAULT_TARGETS_FILE}")
            return 0
        for name, t in targets.items():
            print(f"  {name:20s}  {t.user}@{t.host}:{t.port}  -> {t.deploy_path}  ({t.platform})")
        return 0
    if args.cmd == "add":
        t = Target(name=args.name, host=args.host, user=args.user,
                    deploy_path=args.deploy_path, port=args.port,
                    key_path=args.key_path, platform=args.platform,
                    platform_hints=args.platform_hints,
                    preview_url_base=args.preview_url_base)
        targets[args.name] = t
        save_targets(targets)
        print(f"added {args.name}")
        return 0
    if args.cmd == "test":
        t = targets.get(args.name)
        if not t:
            print(f"unknown target {args.name}")
            return 2
        print(f"testing {args.name} ({t.remote()})...")
        r = connectivity(t)
        print(json.dumps(r, indent=2))
        return 0 if r["ok"] else 1
    ap.print_help()
    return 2


if __name__ == "__main__":
    import sys
    sys.exit(main(sys.argv))
