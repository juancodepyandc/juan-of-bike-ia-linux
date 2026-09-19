from flask import Blueprint, request, jsonify, Response, send_file, current_app, abort, g, stream_with_context
import os, subprocess, threading, time, datetime, json, sys, platform, pathlib, shutil, requests, uuid, re, psutil
import urllib.request as _urllib_req
from bridge_server import WORKSPACE, sortie_module, _proxy, _clean_headers, COMFYUI_PORT, OLLAMA_URL, COMFYUI_URL
import hashlib as _hashlib

connect_bp = Blueprint('connect_bp', __name__)

# =====================================================================
#  /api/connect/* — machine connectors (SSH, TCP) shared between
#  code & cowork modules. Targets are managed client-side and pushed
#  per-call; credentials never persisted server-side here, just used
#  in the request and discarded after the call returns.
# =====================================================================

_CONNECT_TARGETS_FILE = pathlib.Path.home() / ".aurora_code_targets.json"


def _load_connect_targets() -> dict:
    if not _CONNECT_TARGETS_FILE.exists():
        return {}
    try:
        return json.loads(_CONNECT_TARGETS_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _save_connect_targets(d: dict) -> None:
    _CONNECT_TARGETS_FILE.write_text(json.dumps(d, indent=2, ensure_ascii=False),
                                       encoding="utf-8")


def _try_paramiko():
    try:
        import paramiko  # type: ignore
        return paramiko
    except ImportError:
        return None


@connect_bp.route("/api/connect/targets/list", methods=["GET"])
def connect_targets_list():
    """List configured machine targets (no credentials returned)."""
    out = []
    for name, cfg in _load_connect_targets().items():
        safe = {k: v for k, v in cfg.items() if k not in ("password", "key_passphrase")}
        out.append({"name": name, **safe})
    return jsonify({"ok": True, "targets": out})


@connect_bp.route("/api/connect/targets/save", methods=["POST"])
def connect_targets_save():
    """Save / update a target. Body: {name, host, user, port?, deploy_path?,
       platform?, platform_hints?, preview_url_base?, key_path?, save_password?, password?}.
       If save_password is True the password is stored in the JSON; otherwise
       caller passes it per-request and we never persist it.
    """
    data = request.get_json(force=True, silent=True) or {}
    name = (data.get("name") or "").strip()
    if not name:
        return jsonify({"ok": False, "error": "name required"}), 400
    targets = _load_connect_targets()
    entry = targets.get(name, {})
    for k in ("host", "user", "port", "deploy_path", "platform", "platform_hints",
              "preview_url_base", "key_path"):
        if k in data and data[k] is not None:
            entry[k] = data[k]
    if data.get("save_password") and data.get("password"):
        entry["password"] = data["password"]
    targets[name] = entry
    _save_connect_targets(targets)
    safe = {k: v for k, v in entry.items() if k not in ("password",)}
    return jsonify({"ok": True, "name": name, **safe})


@connect_bp.route("/api/connect/targets/delete", methods=["POST"])
def connect_targets_delete():
    data = request.get_json(force=True, silent=True) or {}
    name = (data.get("name") or "").strip()
    targets = _load_connect_targets()
    if name in targets:
        del targets[name]
        _save_connect_targets(targets)
    return jsonify({"ok": True})


def _ssh_connect_params(data: dict) -> tuple[dict, dict | None]:
    """Resolve connection params from {target_name?} or full {host,user,port,...}.
    Returns (params_dict, error_dict_or_None).
    """
    targets = _load_connect_targets()
    if data.get("target_name"):
        t = targets.get(data["target_name"])
        if not t:
            return {}, {"ok": False, "error": f"unknown target {data['target_name']}"}
        params = dict(t)
    else:
        params = {}
    # caller-supplied overrides
    for k in ("host", "user", "port", "key_path", "password"):
        if data.get(k):
            params[k] = data[k]
    if not params.get("host") or not params.get("user"):
        return {}, {"ok": False, "error": "host + user required"}
    params.setdefault("port", 22)
    return params, None


@connect_bp.route("/api/connect/ssh/probe", methods=["POST"])
def connect_ssh_probe():
    """Smoke-test an SSH target. Body: {target_name?} OR {host,user,port?,password?,key_path?}.
    Tries paramiko first (handles password) then falls back to openssh client.
    Never persists the password.
    """
    data = request.get_json(force=True, silent=True) or {}
    params, err = _ssh_connect_params(data)
    if err:
        return jsonify(err), 400

    paramiko = _try_paramiko()
    if paramiko and params.get("password"):
        try:
            cli = paramiko.SSHClient()
            cli.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            cli.connect(hostname=params["host"], username=params["user"],
                        port=int(params["port"]), password=params["password"],
                        timeout=10, banner_timeout=10, auth_timeout=10)
            stdin, stdout, stderr = cli.exec_command("uname -a; python3 --version 2>&1; "
                                                        "node --version 2>&1 || true", timeout=10)
            out = stdout.read().decode("utf-8", errors="ignore")
            cli.close()
            return jsonify({"ok": True, "auth": "password", "out": out[:2000]})
        except Exception as e:
            return jsonify({"ok": False, "auth": "password", "error": str(e)[:300]}), 200

    # openssh path (key-based or agent)
    cmd = ["ssh", "-p", str(params["port"]),
           "-o", "StrictHostKeyChecking=accept-new",
           "-o", "ConnectTimeout=10",
           "-o", "BatchMode=yes"]
    if params.get("key_path"):
        cmd += ["-i", params["key_path"]]
    cmd += [f"{params['user']}@{params['host']}", "uname -a; python3 --version 2>&1; node --version 2>&1 || true"]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=20)
        return jsonify({"ok": proc.returncode == 0, "auth": "key",
                          "out": (proc.stdout or "")[:2000],
                          "err": (proc.stderr or "")[:500],
                          "rc": proc.returncode})
    except subprocess.TimeoutExpired:
        return jsonify({"ok": False, "error": "ssh timeout 20s"}), 200


@connect_bp.route("/api/connect/ssh/run", methods=["POST"])
def connect_ssh_run():
    """Run a command on the remote. Body: {target_name?, host?, user?, ..., command, timeout?}."""
    data = request.get_json(force=True, silent=True) or {}
    params, err = _ssh_connect_params(data)
    if err:
        return jsonify(err), 400
    command = data.get("command") or ""
    if not command:
        return jsonify({"ok": False, "error": "command required"}), 400
    timeout = float(data.get("timeout", 60))

    paramiko = _try_paramiko()
    if paramiko and params.get("password"):
        try:
            cli = paramiko.SSHClient()
            cli.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            cli.connect(hostname=params["host"], username=params["user"],
                        port=int(params["port"]), password=params["password"],
                        timeout=10, banner_timeout=10, auth_timeout=10)
            stdin, stdout, stderr = cli.exec_command(command, timeout=timeout)
            rc = stdout.channel.recv_exit_status()
            so = stdout.read().decode("utf-8", errors="ignore")
            se = stderr.read().decode("utf-8", errors="ignore")
            cli.close()
            return jsonify({"ok": rc == 0, "rc": rc, "stdout": so[:4000], "stderr": se[:2000]})
        except Exception as e:
            return jsonify({"ok": False, "error": str(e)[:300]}), 200

    cmd = ["ssh", "-p", str(params["port"]),
           "-o", "StrictHostKeyChecking=accept-new",
           "-o", "ConnectTimeout=10",
           "-o", "BatchMode=yes"]
    if params.get("key_path"):
        cmd += ["-i", params["key_path"]]
    cmd += [f"{params['user']}@{params['host']}", command]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout + 5)
        return jsonify({"ok": proc.returncode == 0, "rc": proc.returncode,
                          "stdout": (proc.stdout or "")[:4000],
                          "stderr": (proc.stderr or "")[:2000]})
    except subprocess.TimeoutExpired:
        return jsonify({"ok": False, "error": f"timeout {timeout}s"}), 200


@connect_bp.route("/api/connect/ssh/upload", methods=["POST"])
def connect_ssh_upload():
    """Upload one file's content to remote. Body: {target_name? or host+user+..., remote_path, content_b64}."""
    data = request.get_json(force=True, silent=True) or {}
    params, err = _ssh_connect_params(data)
    if err:
        return jsonify(err), 400
    remote_path = data.get("remote_path") or ""
    content_b64 = data.get("content_b64") or ""
    if not remote_path or not content_b64:
        return jsonify({"ok": False, "error": "remote_path + content_b64 required"}), 400
    try:
        raw = base64.b64decode(content_b64)
    except Exception:
        return jsonify({"ok": False, "error": "invalid base64"}), 400

    paramiko = _try_paramiko()
    if paramiko and params.get("password"):
        try:
            cli = paramiko.SSHClient()
            cli.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            cli.connect(hostname=params["host"], username=params["user"],
                        port=int(params["port"]), password=params["password"],
                        timeout=10, banner_timeout=10, auth_timeout=10)
            sftp = cli.open_sftp()
            # mkdir -p remote dir
            parts = remote_path.replace("\\", "/").split("/")
            d = ""
            for p in parts[:-1]:
                if not p:
                    d += "/"
                    continue
                d = (d + "/" + p) if d and not d.endswith("/") else (d + p)
                try:
                    sftp.stat(d)
                except FileNotFoundError:
                    sftp.mkdir(d)
            with sftp.open(remote_path, "wb") as f:
                f.write(raw)
            sftp.close()
            cli.close()
            return jsonify({"ok": True, "bytes": len(raw), "path": remote_path})
        except Exception as e:
            return jsonify({"ok": False, "error": str(e)[:300]}), 200

    # fallback: temp file + scp
    import tempfile
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".tmp")
    try:
        tmp.write(raw)
        tmp.close()
        cmd = ["scp", "-P", str(params["port"]),
               "-o", "StrictHostKeyChecking=accept-new",
               "-o", "ConnectTimeout=10"]
        if params.get("key_path"):
            cmd += ["-i", params["key_path"]]
        cmd += [tmp.name, f"{params['user']}@{params['host']}:{remote_path}"]
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        return jsonify({"ok": proc.returncode == 0,
                          "rc": proc.returncode,
                          "bytes": len(raw),
                          "err": (proc.stderr or "")[:500]})
    finally:
        try:
            os.unlink(tmp.name)
        except Exception:
            pass


@connect_bp.route("/api/connect/ssh/keygen", methods=["POST"])
def connect_ssh_keygen():
    """Generate an ed25519 SSH keypair locally. Body: {comment?, out_path?}.
    Returns the public key text and the local path of the private key.
    """
    data = request.get_json(force=True, silent=True) or {}
    comment = (data.get("comment") or "aurora").replace(" ", "_")[:64]
    home = pathlib.Path.home()
    default_dir = home / ".ssh"
    default_dir.mkdir(parents=True, exist_ok=True)
    out_path = data.get("out_path") or str(default_dir / f"id_ed25519_aurora_{comment}")
    if pathlib.Path(out_path).exists():
        return jsonify({"ok": False, "error": "key already exists, choose another out_path",
                          "path": out_path}), 400
    cmd = ["ssh-keygen", "-t", "ed25519", "-C", comment, "-N", "", "-f", out_path]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if proc.returncode != 0:
            return jsonify({"ok": False, "error": proc.stderr[-300:]}), 200
        pub = pathlib.Path(out_path + ".pub").read_text(encoding="utf-8").strip()
        return jsonify({"ok": True, "private_key_path": out_path, "public_key": pub,
                          "instructions": "Append `public_key` to /home/<user>/.ssh/authorized_keys on the target."})
    except subprocess.TimeoutExpired:
        return jsonify({"ok": False, "error": "keygen timeout"}), 200


@connect_bp.route("/api/connect/tcp/probe", methods=["POST"])
def connect_tcp_probe():
    """Quick TCP reachability probe. Body: {host, port, timeout?}."""
    import socket as _socket
    data = request.get_json(force=True, silent=True) or {}
    host = data.get("host")
    port = int(data.get("port") or 0)
    timeout = float(data.get("timeout") or 4.0)
    if not host or not port:
        return jsonify({"ok": False, "error": "host + port required"}), 400
    s = _socket.socket(_socket.AF_INET, _socket.SOCK_STREAM)
    s.settimeout(timeout)
    t0 = time.time()
    try:
        s.connect((host, port))
        s.close()
        return jsonify({"ok": True, "rtt_ms": int((time.time() - t0) * 1000)})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)[:200],
                          "rtt_ms": int((time.time() - t0) * 1000)}), 200



# --- Refactored to application/routes/cli_bp_routes.py ---
