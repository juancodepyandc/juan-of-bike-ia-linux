"""Provisionnement sûr de CosyVoice3 dans un environnement isolé.

Dry-run par défaut. Le mode --apply ne formate rien, ne touche jamais à
application/.venv et refuse de franchir le plancher de stockage Aurora.
Le venv CosyVoice réutilise en lecture seule le torch 2.11/CUDA 12.8 déjà
validé sur Blackwell, car le requirements officiel épingle torch 2.3/CUDA
12.1, trop ancien pour cette RTX 5070 Ti.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path


WORKSPACE = Path(__file__).resolve().parents[2]
REPO_ROOT = WORKSPACE.parent
STORAGE_DIR = WORKSPACE / "python-services" / "storage"
sys.path.insert(0, str(STORAGE_DIR))
from aurora_storage import AuroraStorageManager


OFFICIAL_REPO = "https://github.com/QwenAudio/CosyVoice.git"
OFFICIAL_MODEL = "FunAudioLLM/Fun-CosyVoice3-0.5B-2512"
APP_DATA = Path.home() / ".local/share/auroraia"
VENV_DIR = APP_DATA / "venvs" / "cosyvoice3"
ENGINE_DIR = APP_DATA / "engines" / "CosyVoice"
INTERNAL_MODEL_DIR = APP_DATA / "models" / "Fun-CosyVoice3-0.5B-2512"

# Basic local inference only: no Gradio/FastAPI/DeepSpeed/TensorRT server stack.
# Torch, torchaudio and faster-whisper come read-only from application/.venv.
INFERENCE_PACKAGES = [
    "conformer==0.3.2",
    "diffusers==0.29.0",
    "gdown==5.1.0",
    "hydra-core==1.3.2",
    "HyperPyYAML==1.2.3",
    "inflect==7.3.1",
    "librosa==0.10.2",
    "modelscope>=1.20.0",
    "numpy==1.26.4",
    "omegaconf==2.3.0",
    # 1.27+ PyPI cible CUDA 13. Cette machine et torch 2.11 sont CUDA 12.8 ;
    # ORT 1.26 est la dernière roue officielle CUDA 12.8/cuDNN 9.
    "onnxruntime-gpu==1.26.0",
    "protobuf>=4.25,<6",
    "pyarrow==18.1.0",
    "pyworld>=0.3.4",
    "soundfile>=0.12.1",
    "transformers==4.51.3",
    "x-transformers==2.11.24",
    "wetext==0.0.4",
    "wget>=3.2",
]

# Le dépôt officiel importe l'API Python d'openai-whisper, mais sa contrainte
# historique ``triton<3`` tenterait de remplacer torch 2.11/cu128 par torch
# 2.3/cu121. Toutes ses dépendances d'exécution sont déjà présentes via le
# pont Blackwell ; seul le paquet Python est installé localement.
NO_DEPS_PACKAGES = [
    "openai-whisper==20231117",
    # Les dépendances Lightning/TorchMetrics existent déjà dans le runtime
    # Blackwell ; installer avec dépendances risquerait aussi de résoudre un
    # second torch incompatible.
    "lightning==2.2.4",
    # 0.11.1 est la roue CPU officielle compatible torch 2.11. Elle suffit
    # pour décoder les références WAV et n'introduit aucune bibliothèque CUDA 13.
    "torchcodec==0.11.1",
]


def application_site_packages() -> Path:
    candidates = sorted((WORKSPACE / ".venv" / "lib").glob("python*/site-packages"))
    if not candidates:
        raise RuntimeError("site-packages application/.venv introuvable")
    site = candidates[-1]
    probe = site / "torch"
    if not probe.exists():
        raise RuntimeError("torch Blackwell absent du venv application existant")
    return site


def runtime_paths(manager: AuroraStorageManager) -> dict:
    if manager.cold_mounted():
        model_dir = manager.cold_root / "models" / "Fun-CosyVoice3-0.5B-2512"
        tier = "cold"
    else:
        model_dir = INTERNAL_MODEL_DIR
        tier = "hot"
    return {
        "venv": VENV_DIR,
        "python": VENV_DIR / "bin" / "python",
        "repo": ENGINE_DIR,
        "model": model_dir,
        "model_tier": tier,
        "shared_torch_site": application_site_packages(),
    }


def run_checked(command: list[str], *, timeout: int = 3600) -> dict:
    proc = subprocess.run(command, capture_output=True, text=True, timeout=timeout)
    if proc.returncode != 0:
        raise RuntimeError(
            f"commande echouee ({proc.returncode}): {' '.join(command[:4])}\n"
            f"{(proc.stderr or proc.stdout)[-1200:]}"
        )
    return {"stdout": proc.stdout[-1200:], "stderr": proc.stderr[-1200:]}


def download_worker(model_dir: Path) -> int:
    from huggingface_hub import snapshot_download

    model_dir.mkdir(parents=True, exist_ok=True)
    snapshot_download(
        repo_id=OFFICIAL_MODEL,
        local_dir=str(model_dir),
    )
    return 0


def plan(manager: AuroraStorageManager) -> dict:
    paths = runtime_paths(manager)
    capacity = manager.ensure_space(
        paths["model_tier"],
        16.0,
        allow_eviction=False,
        dry_run=True,
    )
    return {
        "ok": bool(capacity.get("ok")),
        "dry_run": True,
        "component": "cosyvoice3",
        "official_repo": OFFICIAL_REPO,
        "official_model": OFFICIAL_MODEL,
        "paths": {key: str(value) for key, value in paths.items()},
        "capacity": capacity,
        "actions": [
            "creer un venv CosyVoice3 distinct",
            "lier en lecture seule torch/torchaudio CUDA 12.8 depuis application/.venv",
            "cloner le depot officiel avec ses sous-modules",
            "installer uniquement les dependances d'inference dans le venv isole",
            "telecharger le snapshot officiel complet dans l'etage choisi",
            "executer cosyvoice3_adapter.py --check",
        ],
        "excluded_official_requirements": [
            "torch==2.3.1/cu121 (incompatible Blackwell)",
            "deepspeed, TensorRT, Gradio, FastAPI (inutiles pour l'inference locale directe)",
        ],
    }


def apply(manager: AuroraStorageManager) -> dict:
    result = plan(manager)
    paths = runtime_paths(manager)
    # Le dry-run informe l'interface, mais le mode apply doit revérifier la
    # capacité au dernier moment avec la sémantique réelle du gestionnaire.
    capacity = manager.ensure_space(
        paths["model_tier"],
        16.0,
        allow_eviction=False,
        dry_run=False,
    )
    result.update({
        "ok": bool(capacity.get("ok")),
        "dry_run": False,
        "capacity": capacity,
    })
    if not result["ok"]:
        return result
    venv_python = Path(paths["python"])
    if not venv_python.exists():
        VENV_DIR.parent.mkdir(parents=True, exist_ok=True)
        run_checked([sys.executable, "-m", "venv", str(VENV_DIR)], timeout=600)

    venv_site_candidates = sorted((VENV_DIR / "lib").glob("python*/site-packages"))
    if not venv_site_candidates:
        raise RuntimeError("site-packages du venv CosyVoice3 introuvable")
    torch_bridge = venv_site_candidates[-1] / "aurora_blackwell_torch.pth"
    torch_bridge.write_text(str(paths["shared_torch_site"]) + "\n", encoding="utf-8")

    if not ENGINE_DIR.exists():
        ENGINE_DIR.parent.mkdir(parents=True, exist_ok=True)
        run_checked([
            "git", "clone", "--depth", "1", "--recurse-submodules",
            "--shallow-submodules", OFFICIAL_REPO, str(ENGINE_DIR),
        ], timeout=1800)
    elif not (ENGINE_DIR / ".git").is_dir():
        raise RuntimeError(f"chemin moteur existant non gere: {ENGINE_DIR}")
    else:
        dirty = subprocess.run(
            ["git", "-C", str(ENGINE_DIR), "status", "--porcelain"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if dirty.returncode != 0 or dirty.stdout.strip():
            raise RuntimeError("depot CosyVoice existant modifie; mise a jour automatique refusee")
        run_checked([
            "git", "-C", str(ENGINE_DIR), "submodule", "update",
            "--init", "--recursive", "--depth", "1",
        ], timeout=1200)

    run_checked([
        str(venv_python), "-m", "pip", "install", "--upgrade",
        "pip", "wheel", "setuptools<81",
    ], timeout=900)
    run_checked([
        str(venv_python), "-m", "pip", "install", "--no-build-isolation",
        *INFERENCE_PACKAGES,
    ], timeout=5400)
    run_checked([
        str(venv_python), "-m", "pip", "install", "--no-build-isolation",
        "--no-deps", *NO_DEPS_PACKAGES,
    ], timeout=1800)

    model_dir = Path(paths["model"])
    run_checked([
        str(venv_python), str(Path(__file__).resolve()),
        "--download-worker", "--model-dir", str(model_dir),
    ], timeout=7200)

    cinema_dir = Path(__file__).resolve().parent
    adapter = cinema_dir / "cosyvoice3_adapter.py"
    env = {
        **os.environ,
        "AURORA_COSYVOICE3_PYTHON": str(venv_python),
        "AURORA_COSYVOICE3_REPO": str(ENGINE_DIR),
        "AURORA_COSYVOICE3_MODEL": str(model_dir),
    }
    check = subprocess.run(
        [str(venv_python), str(adapter), "--check"],
        capture_output=True,
        text=True,
        timeout=180,
        env=env,
    )
    payload = None
    for line in reversed(check.stdout.splitlines()):
        try:
            payload = json.loads(line)
            break
        except Exception:
            continue
    return {
        **result,
        "ok": check.returncode == 0 and bool((payload or {}).get("ok")),
        "dry_run": False,
        "check": payload or {
            "ok": False,
            "error": (check.stderr or check.stdout)[-800:],
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--download-worker", action="store_true")
    parser.add_argument("--model-dir", default="")
    args = parser.parse_args()
    if args.download_worker:
        if not args.model_dir:
            print(json.dumps({"ok": False, "error": "--model-dir requis"}))
            return 2
        return download_worker(Path(args.model_dir))

    manager = AuroraStorageManager()
    try:
        result = apply(manager) if args.apply else plan(manager)
    except Exception as exc:
        result = {"ok": False, "error": f"{type(exc).__name__}: {str(exc)[:1200]}"}
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result.get("ok") else 2


if __name__ == "__main__":
    raise SystemExit(main())
