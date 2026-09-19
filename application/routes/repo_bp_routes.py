from flask import Blueprint, request, jsonify, Response, send_file, current_app, abort, g, stream_with_context
import os, subprocess, threading, time, datetime, json, sys, platform, pathlib, shutil, requests, uuid, re, psutil
import urllib.request as _urllib_req
from bridge_server import WORKSPACE, sortie_module, _proxy, _clean_headers, COMFYUI_PORT, OLLAMA_URL, COMFYUI_URL

repo_bp = Blueprint('repo_bp', __name__)

# =====================================================================
#  /api/code/repo/* — work directly on a local repository (v85)
#  pick (native folder dialog) · scan (read project as context) ·
#  write (apply changes back) · git (status / branch). Lets the Code
#  module iterate on ANY existing project on disk, not just greenfield
#  in-app generation.
# =====================================================================

_REPO_LANG_BY_EXT = {
    "ts": "typescript", "tsx": "typescript", "js": "javascript", "jsx": "javascript",
    "mjs": "javascript", "cjs": "javascript", "py": "python", "rs": "rust", "go": "go",
    "java": "java", "kt": "kotlin", "swift": "swift", "c": "c", "h": "c", "cpp": "cpp",
    "cc": "cpp", "hpp": "cpp", "cs": "csharp", "rb": "ruby", "php": "php", "lua": "lua",
    "sh": "bash", "bash": "bash", "ps1": "powershell", "sql": "sql", "html": "html",
    "htm": "html", "css": "css", "scss": "scss", "sass": "scss", "less": "less",
    "vue": "vue", "svelte": "svelte", "json": "json", "yaml": "yaml", "yml": "yaml",
    "toml": "toml", "xml": "xml", "md": "markdown", "txt": "text", "ini": "ini",
    "cfg": "ini", "env": "text", "dockerfile": "dockerfile", "r": "r", "dart": "dart",
}

_REPO_SKIP_DIRS = {
    ".git", "node_modules", "dist", "build", "out", ".next", ".nuxt", ".svelte-kit",
    "__pycache__", ".venv", "venv", "env", ".env", "target", "vendor", ".idea",
    ".vscode", "coverage", ".cache", ".turbo", ".parcel-cache", "bin", "obj",
    ".gradle", "Pods", ".expo", ".aurora_backup", "site-packages",
}

_REPO_SKIP_EXT = {
    "png", "jpg", "jpeg", "gif", "webp", "ico", "bmp", "tiff", "svg", "pdf",
    "mp4", "mov", "avi", "mkv", "webm", "mp3", "wav", "ogg", "flac", "zip",
    "tar", "gz", "rar", "7z", "exe", "dll", "so", "dylib", "bin", "wasm",
    "ttf", "otf", "woff", "woff2", "eot", "glb", "gltf", "fbx", "obj", "blend",
    "psd", "ai", "sketch", "db", "sqlite", "lock", "pyc", "pack", "idx",
}


def _repo_lang(rel: str) -> str:
    low = rel.lower()
    if low.endswith("dockerfile") or low == "dockerfile":
        return "dockerfile"
    ext = low.rsplit(".", 1)[-1] if "." in low else ""
    return _REPO_LANG_BY_EXT.get(ext, "text")


def _repo_git(path, args, timeout=8):
    try:
        proc = subprocess.run(
            ["git", "-C", str(path), *args],
            capture_output=True, text=True, timeout=timeout,
        )
        if proc.returncode == 0:
            return proc.stdout.strip()
    except Exception:
        pass
    return None


@repo_bp.route("/api/code/repo/pick", methods=["POST"])
def code_repo_pick():
    """Open a native folder picker and return the chosen path.

    Runs the dialog in a FRESH python process (sys.executable) so Tk never
    touches the Flask worker thread (which would crash on Windows).
    """
    try:
        snippet = (
            "import tkinter, tkinter.filedialog as fd;"
            "r=tkinter.Tk();r.withdraw();r.attributes('-topmost',True);"
            "p=fd.askdirectory(title='Choisis le dossier du repo');"
            "print(p or '')"
        )
        proc = subprocess.run(
            [sys.executable, "-c", snippet],
            capture_output=True, text=True, timeout=120,
        )
        path = (proc.stdout or "").strip().splitlines()[-1].strip() if proc.stdout.strip() else ""
        if not path or not os.path.isdir(path):
            return jsonify({"ok": False, "error": "Aucun dossier sélectionné."})
        return jsonify({"ok": True, "path": os.path.abspath(path)})
    except Exception as e:
        return jsonify({"ok": False, "error": f"Sélecteur indisponible: {e}"}), 500


@repo_bp.route("/api/code/repo/scan", methods=["POST"])
def code_repo_scan():
    """Read a repository into a capped, text-only snapshot for LLM context.

    Body: {path, max_files?, max_bytes?, max_file_bytes?}
    Uses `git ls-files` when the dir is a git repo (respects .gitignore),
    otherwise walks with a skip-list. Returns {files:[{path,content,language}]}.
    """
    try:
        data = request.get_json(force=True, silent=True) or {}
        root = os.path.abspath((data.get("path") or "").strip())
        if not root or not os.path.isdir(root):
            return jsonify({"ok": False, "error": "Chemin invalide ou introuvable."}), 400
        max_files = int(data.get("max_files") or 120)
        max_bytes = int(data.get("max_bytes") or 1_400_000)
        max_file_bytes = int(data.get("max_file_bytes") or 60_000)

        is_git = os.path.isdir(os.path.join(root, ".git"))
        branch = _repo_git(root, ["rev-parse", "--abbrev-ref", "HEAD"]) if is_git else None

        # Build the candidate relative-path list.
        rels = []
        tracked = _repo_git(root, ["ls-files"]) if is_git else None
        if tracked:
            for line in tracked.splitlines():
                rel = line.strip()
                if rel:
                    rels.append(rel)
        else:
            for dirpath, dirnames, filenames in os.walk(root):
                dirnames[:] = [d for d in dirnames if d not in _REPO_SKIP_DIRS and not d.startswith(".")]
                for fn in filenames:
                    full = os.path.join(dirpath, fn)
                    rel = os.path.relpath(full, root).replace("\\", "/")
                    rels.append(rel)

        files = []
        total_bytes = 0
        total_candidates = len(rels)
        truncated = False
        # Prefer salient files first (entrypoints, manifests, src).
        def _rank(rel):
            low = rel.lower()
            score = 0
            if any(low.endswith(m) for m in ("package.json", "cargo.toml", "pyproject.toml", "go.mod", "requirements.txt", "readme.md")):
                score -= 100
            if low.startswith("src/") or "/src/" in low:
                score -= 20
            score += low.count("/")
            return score
        rels.sort(key=_rank)

        for rel in rels:
            if len(files) >= max_files or total_bytes >= max_bytes:
                truncated = True
                break
            parts = rel.split("/")
            if any(p in _REPO_SKIP_DIRS for p in parts):
                continue
            ext = rel.rsplit(".", 1)[-1].lower() if "." in rel else ""
            if ext in _REPO_SKIP_EXT:
                continue
            full = os.path.join(root, rel)
            try:
                if not os.path.isfile(full):
                    continue
                if os.path.getsize(full) > max_file_bytes * 4:
                    continue
                with open(full, "r", encoding="utf-8") as fh:
                    content = fh.read(max_file_bytes + 1)
            except (UnicodeDecodeError, OSError):
                continue
            if len(content) > max_file_bytes:
                content = content[:max_file_bytes] + "\n/* … fichier tronqué pour le contexte … */"
            total_bytes += len(content)
            files.append({"path": rel, "content": content, "language": _repo_lang(rel)})

        return jsonify({
            "ok": True,
            "path": root,
            "label": os.path.basename(root.rstrip("/\\")) or root,
            "branch": branch,
            "is_git": is_git,
            "truncated": truncated,
            "total_files": total_candidates,
            "total_bytes": total_bytes,
            "files": files,
        })
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@repo_bp.route("/api/code/repo/write", methods=["POST"])
def code_repo_write():
    """Write generated/modified files back into a repository.

    Body: {path, files:[{path, content}], backup?}
    Sanitizes each relative path (no absolute, no ..). When backup=true,
    overwritten files are copied to <repo>/.aurora_backup/<ts>/ first.
    """
    import shutil  # module-level import is function-local elsewhere — ensure it's bound here
    try:
        data = request.get_json(force=True, silent=True) or {}
        root = os.path.abspath((data.get("path") or "").strip())
        files = data.get("files") or []
        if not root or not os.path.isdir(root):
            return jsonify({"ok": False, "error": "Chemin du repo invalide."}), 400
        if not isinstance(files, list) or not files:
            return jsonify({"ok": False, "error": "Aucun fichier à écrire."}), 400

        backup = bool(data.get("backup", True))
        backup_dir = os.path.join(root, ".aurora_backup", str(int(time.time())))
        written, skipped, backed_up = [], [], []
        for f in files:
            if not isinstance(f, dict):
                continue
            rel = str(f.get("path") or "").strip().replace("\\", "/").lstrip("/")
            if not rel or ".." in rel.split("/"):
                skipped.append(rel or "(vide)")
                continue
            content = f.get("content")
            if not isinstance(content, str):
                content = str(content or "")
            full = os.path.join(root, rel)
            # Stay inside the repo root.
            if os.path.commonpath([os.path.abspath(full), root]) != root:
                skipped.append(rel)
                continue
            try:
                if backup and os.path.isfile(full):
                    bdest = os.path.join(backup_dir, rel)
                    os.makedirs(os.path.dirname(bdest) or backup_dir, exist_ok=True)
                    shutil.copy2(full, bdest)
                    backed_up.append(rel)
                os.makedirs(os.path.dirname(full) or root, exist_ok=True)
                with open(full, "w", encoding="utf-8", newline="\n") as fh:
                    fh.write(content)
                written.append(rel)
            except Exception:
                skipped.append(rel)

        return jsonify({
            "ok": True, "path": root, "written": written,
            "skipped": skipped, "backed_up": backed_up,
            "backup_dir": backup_dir if backed_up else None,
        })
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@repo_bp.route("/api/code/repo/git", methods=["POST"])
def code_repo_git_info():
    """Lightweight git info: {path, action: 'status'|'branch'}."""
    try:
        data = request.get_json(force=True, silent=True) or {}
        root = os.path.abspath((data.get("path") or "").strip())
        action = (data.get("action") or "status").strip()
        if not root or not os.path.isdir(root):
            return jsonify({"ok": False, "error": "Chemin invalide."}), 400
        if not os.path.isdir(os.path.join(root, ".git")):
            return jsonify({"ok": True, "is_git": False})
        branch = _repo_git(root, ["rev-parse", "--abbrev-ref", "HEAD"])
        if action == "branch":
            return jsonify({"ok": True, "is_git": True, "branch": branch})
        status = _repo_git(root, ["status", "--porcelain"]) or ""
        changed = [ln.strip() for ln in status.splitlines() if ln.strip()]
        return jsonify({"ok": True, "is_git": True, "branch": branch,
                        "dirty": len(changed) > 0, "changed": changed[:60]})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@repo_bp.route("/api/code/repo/install", methods=["POST"])
def code_repo_install():
    """Autonomy (v85f): detect the project's dependency manifest and run its
    install command in a DETACHED console so the generated/repo project actually
    runs on the PC. Body: {path}. Returns immediately; install runs in the
    spawned console (npm/pnpm/yarn install, pip install, cargo build, go mod).
    """
    try:
        data = request.get_json(force=True, silent=True) or {}
        root = os.path.abspath((data.get("path") or "").strip())
        if not root or not os.path.isdir(root):
            return jsonify({"ok": False, "error": "Chemin invalide."}), 400

        def _has(name):
            return os.path.isfile(os.path.join(root, name))

        cmd = None
        manifest = None
        if _has("package.json"):
            manifest = "package.json"
            cmd = ("pnpm install" if _has("pnpm-lock.yaml")
                   else "yarn install" if _has("yarn.lock")
                   else "npm install")
        elif _has("requirements.txt"):
            manifest = "requirements.txt"
            cmd = f'"{sys.executable}" -m pip install -r requirements.txt'
        elif _has("pyproject.toml"):
            manifest = "pyproject.toml"
            cmd = f'"{sys.executable}" -m pip install -e .'
        elif _has("Cargo.toml"):
            manifest = "Cargo.toml"
            cmd = "cargo build"
        elif _has("go.mod"):
            manifest = "go.mod"
            cmd = "go mod download"

        if not cmd:
            return jsonify({"ok": False, "error": "Aucun manifeste détecté (package.json, requirements.txt, pyproject.toml, Cargo.toml, go.mod)."})

        try:
            if platform.system() == "Windows":
                subprocess.Popen(cmd, cwd=root, shell=True,
                                 creationflags=subprocess.CREATE_NEW_CONSOLE | subprocess.CREATE_BREAKAWAY_FROM_JOB)
            else:
                subprocess.Popen(cmd, cwd=root, shell=True, start_new_session=True)
        except Exception as ex:
            return jsonify({"ok": False, "error": f"Lancement échoué: {ex}", "command": cmd}), 500
        return jsonify({"ok": True, "command": cmd, "cwd": root, "manifest": manifest})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@repo_bp.route("/proxy/ollama/<path:path>", methods=["GET", "POST", "PUT", "DELETE"])
def ollama_proxy(path):
    try:
        return _proxy(f"{OLLAMA_URL}/{path}")
    except Exception as e:
        return jsonify({"error": f"Ollama non joignable: {e}"}), 504


@repo_bp.route("/api/ollama/chat", methods=["POST"])
def ollama_chat():
    """Route directe pour le chat stream — headers propres."""
    try:
        resp = requests.post(
            f"{OLLAMA_URL}/api/chat",
            json=request.json,
            headers={"Content-Type": "application/json"},
            stream=True,
            timeout=180,
        )
        return Response(
            resp.iter_content(chunk_size=4096),
            content_type="application/json",
        )
    except Exception as e:
        return jsonify({"error": str(e)}), 500


