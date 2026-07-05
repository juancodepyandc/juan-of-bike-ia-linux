"""
juan of bike IA - Python runtime bootstrap per module

Usage:
  python runtime_prepare.py --module video
  python runtime_prepare.py --module 3d
"""

import argparse
import json
import os
import subprocess
import sys

from cache_paths import configure_ml_cache_environment


PYTORCH_CUDA_INDEX_URL = "https://download.pytorch.org/whl/cu128"

MODULE_REQUIREMENTS = {
    "video": {
        "diffusers": "diffusers>=0.33.0",
        "PIL": "Pillow",
        "numpy": "numpy",
        "accelerate": "accelerate",
        "transformers": "transformers>=4.45.0",
        "sentencepiece": "sentencepiece",
        "imageio": "imageio[ffmpeg]",
        "safetensors": "safetensors",
    },
    "3d": {
        "PIL": "Pillow",
        "numpy": "numpy",
        "trimesh": "trimesh",
        "yaml": "PyYAML",
        "pymeshlab": "pymeshlab",
        "pygltflib": "pygltflib",
        "einops": "einops",
        "omegaconf": "omegaconf",
        "hy3dgen": "hy3dgen",
        "rembg": "rembg",
        "diffusers": "diffusers>=0.33.0",
        "transformers": "transformers>=4.45.0",
        "accelerate": "accelerate",
        "sentencepiece": "sentencepiece",
        "safetensors": "safetensors",
        "huggingface_hub": "huggingface_hub",
    },
    "voice": {
        "faster_whisper": "faster-whisper",
        "soundfile": "soundfile",
        "scipy": "scipy",
        "huggingface_hub": "huggingface_hub",
        "transformers": "transformers>=4.45.0",
        "accelerate": "accelerate",
    },
}


def emit(stage: str, detail: str):
    print(f"PROGRESS:{stage}:{detail}", flush=True)


def parse_args():
    parser = argparse.ArgumentParser(description="Prepare local Python runtime")
    parser.add_argument("--module", required=True, choices=sorted(MODULE_REQUIREMENTS))
    parser.add_argument("--skip-torch", action="store_true", help="Ne pas verifier/installer PyTorch (pour le module voice si deja pret)")
    return parser.parse_args()


def pip_install(args):
    command = [
        sys.executable,
        "-m",
        "pip",
        "install",
        "--disable-pip-version-check",
        "--quiet",
    ] + args
    subprocess.check_call(command, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)


def detect_nvidia():
    try:
        completed = subprocess.run(
            ["nvidia-smi", "--query-gpu=name,memory.total", "--format=csv,noheader,nounits"],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
        if completed.returncode != 0:
            return None

        first_line = completed.stdout.strip().splitlines()[0]
        name, total_mb = [part.strip() for part in first_line.split(",", 1)]
        return {
            "name": name,
            "vram_gb": round(float(total_mb) / 1024.0, 1),
        }
    except Exception:
        return None


def torch_info():
    try:
        import torch  # type: ignore

        info = {
            "version": getattr(torch, "__version__", "inconnue"),
            "cuda_available": bool(torch.cuda.is_available()),
            "device_count": int(torch.cuda.device_count()) if torch.cuda.is_available() else 0,
            "device_name": torch.cuda.get_device_name(0) if torch.cuda.is_available() else None,
        }
        return info
    except Exception:
        return None


def ensure_torch_runtime():
    gpu_info = detect_nvidia()
    current_torch = torch_info()

    if gpu_info and current_torch and current_torch["cuda_available"]:
        emit("ready", f"PyTorch CUDA deja pret sur {current_torch['device_name']}.")
        return current_torch

    if gpu_info:
        emit("install", f"PyTorch CUDA requis pour la RTX locale ({gpu_info['name']}). Installation officielle en cours...")
        pip_install([
            "--upgrade",
            "--index-url",
            PYTORCH_CUDA_INDEX_URL,
            "torch",
            "torchvision",
            "torchaudio",
        ])
        current_torch = torch_info()
        if not current_torch or not current_torch["cuda_available"]:
            raise RuntimeError(
                "PyTorch CUDA n a pas pu etre active apres installation. Verifie le runtime Python utilise par l application."
            )

        emit("ready", f"PyTorch CUDA actif sur {current_torch['device_name']}.")
        return current_torch

    if not current_torch:
        emit("install", "PyTorch absent, installation CPU minimale en cours...")
        pip_install(["torch", "torchvision", "torchaudio"])
        current_torch = torch_info()

    emit("ready", "PyTorch disponible sans CUDA detecte.")
    return current_torch


def ensure_packages(module_name: str):
    required = MODULE_REQUIREMENTS[module_name]
    missing = []

    for import_name, pip_name in required.items():
        try:
            __import__(import_name)
        except Exception:
            missing.append(pip_name)

    if missing:
        emit("install", f"Installation automatique de {', '.join(missing)}...")
        pip_install(missing)
        emit("warming", f"Dependances {module_name} installees.")


def main():
    args = parse_args()
    configure_ml_cache_environment()
    os.environ.setdefault("HF_HUB_DISABLE_PROGRESS_BARS", "1")
    os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")

    try:
        emit("scan", f"Analyse du runtime Python pour le module {args.module}...")
        current_torch = None if args.skip_torch else ensure_torch_runtime()
        if current_torch is None and not args.skip_torch:
            current_torch = torch_info()
        ensure_packages(args.module)

        result = {
            "ok": True,
            "path": sys.executable,
            "module": args.module,
            "python": sys.executable,
            "torch": current_torch or {},
        }
        emit("ready", f"Runtime Python {args.module} pret.")
        print(json.dumps(result))
    except Exception as exc:
        print(json.dumps({"ok": False, "error": str(exc)}))
        sys.exit(1)


if __name__ == "__main__":
    main()
