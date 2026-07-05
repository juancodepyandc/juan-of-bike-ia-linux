"""
juan of bike IA - local model asset preflight

Modes:
  python model_prepare.py --mode hf-file --repo-id city96/FLUX.1-dev-gguf --filename flux1-dev-Q8_0.gguf --destination C:/.../flux1-dev-Q8_0.gguf
  python model_prepare.py --mode hf-snapshot --repo-id Wan-AI/Wan2.2-T2V-A14B-Diffusers
"""

import argparse
import json
import os
import pathlib
import shutil
import subprocess
import sys

from cache_paths import configure_ml_cache_environment

REQUIRED_PACKAGES = {
    "huggingface_hub": "huggingface_hub",
    "tqdm": "tqdm",
}


def ensure_dependencies():
    """Installe automatiquement les packages pip manquants."""
    missing = []
    for import_name, pip_name in REQUIRED_PACKAGES.items():
        try:
            __import__(import_name)
        except ImportError:
            missing.append(pip_name)
    if missing:
        print(f"PROGRESS:install:Installation automatique de {', '.join(missing)}...", flush=True)
        subprocess.check_call(
            [sys.executable, "-m", "pip", "install", "--quiet"] + missing,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
        )
        print("PROGRESS:install:Dependances model_prepare installees.", flush=True)


ensure_dependencies()
configure_ml_cache_environment()

from huggingface_hub import hf_hub_download, snapshot_download
from tqdm.auto import tqdm


class ProgressPrinter(tqdm):
    def __init__(self, *args, **kwargs):
        self._last_report = -1
        super().__init__(*args, **kwargs)

    def update(self, n=1):
        value = super().update(n)
        total = self.total or 0
        if total:
            percent = int((self.n / total) * 100)
            if percent != self._last_report and (percent == 100 or percent - self._last_report >= 2):
                desc = (self.desc or "telechargement").strip() or "telechargement"
                print(f"PROGRESS:download:{desc} {percent}%", flush=True)
                self._last_report = percent
        return value


def parse_args():
    parser = argparse.ArgumentParser(description="Prepare local model assets")
    parser.add_argument("--mode", required=True, choices=["hf-file", "hf-snapshot"])
    parser.add_argument("--repo-id", required=True)
    parser.add_argument("--filename")
    parser.add_argument("--destination")
    parser.add_argument("--allow-pattern", action="append", dest="allow_patterns")
    return parser.parse_args()


def _resolve_destination(destination: str) -> str:
    """Resolve a (possibly relative) model destination to an absolute path.

    Resolution order:
    1. Already absolute → normalise and return.
    2. COMFYUI_DIR env var (injected by bridge_server.py at runtime).
    3. AURORA_MODELS env var (set by configure_ml_cache_environment) +
       comfyui/comfyui subdirectory — the AuroraIA-v2 project layout.
    4. Auto-detect from this script's location:
       python-services/ → application/ → AuroraIA-v2/ → modele/comfyui/comfyui
    """
    if os.path.isabs(destination):
        return os.path.normpath(destination)

    # 1. Explicit COMFYUI_DIR (bridge injected)
    comfyui_dir = os.environ.get("COMFYUI_DIR", "").strip()
    if comfyui_dir and os.path.isdir(comfyui_dir):
        return os.path.normpath(os.path.join(comfyui_dir, destination))

    # 2. Derive ComfyUI dir from AURORA_MODELS (set by configure_ml_cache_environment)
    aurora_models = os.environ.get("AURORA_MODELS", "").strip()
    if aurora_models:
        for sub in ("comfyui/comfyui", "comfyui"):
            candidate = os.path.join(aurora_models, sub)
            if os.path.isdir(candidate):
                return os.path.normpath(os.path.join(candidate, destination))

    # 3. Auto-detect: python-services/ → AuroraIA-v2/modele/comfyui/comfyui
    here = pathlib.Path(__file__).resolve().parent   # …/application/python-services
    modele = here.parent.parent / "modele"           # …/AuroraIA-v2/modele
    if modele.is_dir():
        for sub in ("comfyui/comfyui", "comfyui"):
            candidate = modele / sub
            if candidate.is_dir():
                return str((candidate / destination).resolve())

    # 4. Scan project roots for any directory containing models/
    project_root = here.parent.parent                # …/AuroraIA-v2/
    for search_root in [project_root / "modele", project_root / "models"]:
        if search_root.is_dir():
            for sub in ("comfyui/comfyui", "comfyui", "."):
                base = search_root / sub
                full = base / destination
                if full.parent.is_dir() or base.is_dir():
                    os.makedirs(str(full.parent), exist_ok=True)
                    return str(full.resolve())

    aurora_models_diag = aurora_models or "non defini"
    comfyui_dir_diag = comfyui_dir or "non defini"
    print(json.dumps({
        "ok": False,
        "error": (
            f"ComfyUI introuvable — chemin relatif '{destination}' non resoluble. "
            f"AURORA_MODELS={aurora_models_diag}, COMFYUI_DIR={comfyui_dir_diag}. "
            f"Verifiez que modele/comfyui/comfyui existe dans le dossier AuroraIA-v2."
        ),
    }), flush=True)
    sys.exit(1)


def ensure_hf_file(repo_id: str, filename: str, destination: str) -> dict:
    """Download a single model file from HuggingFace Hub to a local destination.

    Uses hf_hub_download (single-file, cached) then copies to the target path.
    This correctly handles filenames with subdirectory prefixes (e.g. split_files/vae/ae.safetensors).
    """
    if not filename or not destination:
        raise ValueError("hf-file exige --filename et --destination")

    dest = _resolve_destination(destination)
    os.makedirs(os.path.dirname(dest), exist_ok=True)

    print(f"PROGRESS:scan:Verification locale de {os.path.basename(filename)}...", flush=True)
    if os.path.isfile(dest) and os.path.getsize(dest) > 0:
        return {"ok": True, "path": dest, "cached": True, "repo_id": repo_id, "filename": filename}

    cache_dir = os.environ.get("HF_HUB_CACHE")
    print(f"PROGRESS:download:Telechargement de {os.path.basename(filename)}...", flush=True)

    # Download to HF cache (handles resume, token, etc.) then copy to dest.
    # Copying from the cache avoids path-structure issues with nested filenames
    # like "split_files/vae/ae.safetensors" whose local_dir download lands in a subdir.
    cached_path = hf_hub_download(
        repo_id=repo_id,
        filename=filename,
        cache_dir=cache_dir,
    )
    shutil.copyfile(cached_path, dest)

    if not os.path.isfile(dest) or os.path.getsize(dest) == 0:
        raise FileNotFoundError(f"Fichier attendu introuvable apres download: {dest}")

    return {"ok": True, "path": dest, "cached": False, "repo_id": repo_id, "filename": filename}


def ensure_hf_snapshot(repo_id, allow_patterns=None):
    allow_patterns = allow_patterns or None
    cache_dir = os.environ.get("HF_HUB_CACHE")
    print(f"PROGRESS:scan:Verification du cache local pour {repo_id}...", flush=True)

    try:
        cached_path = snapshot_download(
            repo_id=repo_id,
            allow_patterns=allow_patterns,
            local_files_only=True,
            cache_dir=cache_dir,
        )
        return {
            "ok": True,
            "path": cached_path,
            "cached": True,
            "repo_id": repo_id,
        }
    except Exception:
        pass

    print(f"PROGRESS:download:Telechargement du depot {repo_id}...", flush=True)
    snapshot_path = snapshot_download(
        repo_id=repo_id,
        allow_patterns=allow_patterns,
        tqdm_class=ProgressPrinter,
        cache_dir=cache_dir,
    )
    return {
        "ok": True,
        "path": snapshot_path,
        "cached": False,
        "repo_id": repo_id,
    }


def main():
    args = parse_args()

    try:
        if args.mode == "hf-file":
            result = ensure_hf_file(args.repo_id, args.filename, args.destination)
        else:
            result = ensure_hf_snapshot(args.repo_id, args.allow_patterns)

        print("PROGRESS:ready:Asset pret pour le module.", flush=True)
        print(json.dumps(result))
    except Exception as exc:
        print(json.dumps({"ok": False, "error": str(exc)}))
        sys.exit(1)


if __name__ == "__main__":
    main()
