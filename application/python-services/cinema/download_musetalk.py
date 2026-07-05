"""
download_musetalk.py -- Telecharge UNIQUEMENT les poids MuseTalk V1.5 (4.4 GB).

V1.5 produit des dents et levres natives realistes via latent diffusion
audio-driven. Remplace le pipeline Wav2Lip+GFPGAN qui floutait la zone
bouche.

Modeles (~4.4 GB total) :
  - musetalkV15/musetalk.json + unet.pth          (3.4 GB)  TMElyralab/MuseTalk
  - sd-vae-ft-mse VAE encoder                     (335 MB)  stabilityai/sd-vae-ft-mse
  - whisper-tiny audio encoder                    (155 MB)  openai/whisper-tiny
  - DWPose dw-ll_ucoco_384.pth                    (407 MB)  yzd-v/DWPose
  - face-parse-bisent 79999_iter.pth + resnet18   (~100 MB) Google Drive + pytorch.org

Usage:
  python download_musetalk.py            # tout telecharger
  python download_musetalk.py --check    # juste lister ce qui manque
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from cache_paths import configure_ml_cache_environment  # type: ignore

CACHE_ENV = configure_ml_cache_environment()
MODELS_ROOT = Path(CACHE_ENV["AURORA_MODELS"])
HF_HUB_CACHE = Path(CACHE_ENV["HF_HUB_CACHE"])

# MuseTalk expects these weights at <MUSETALK_REPO>/models/...
MUSETALK_REPO = Path(__file__).resolve().parent.parent / "MuseTalk"
MODELS_DIR = MUSETALK_REPO / "models"


def emit(stage: str, detail: str):
    print(f"PROGRESS:{stage}:{detail}", flush=True)


def human(size_bytes: float) -> str:
    if size_bytes < 1024:
        return f"{int(size_bytes)} B"
    for unit in ("KB", "MB", "GB"):
        size_bytes /= 1024.0
        if size_bytes < 1024:
            return f"{size_bytes:.1f} {unit}"
    return f"{size_bytes:.1f} TB"


def check_size(path: Path, min_bytes: int, label: str) -> None:
    if not path.exists():
        raise FileNotFoundError(f"{label}: {path} introuvable apres download")
    size = path.stat().st_size
    if size < min_bytes:
        raise OSError(f"{label}: {path.name} ne fait que {human(size)} (attendu >= {human(min_bytes)})")
    emit("downloaded", f"{label}: {human(size)} -> {path.name}")


def fetch_url(url: str, dest: Path, min_bytes: int, label: str) -> Path:
    if dest.exists() and dest.stat().st_size >= min_bytes:
        emit("skip", f"{label} deja present ({human(dest.stat().st_size)})")
        return dest
    dest.parent.mkdir(parents=True, exist_ok=True)
    emit("fetch", f"{label} {url}")
    tmp = dest.with_suffix(dest.suffix + ".part")
    last_pct = -1
    with urllib.request.urlopen(url, timeout=60) as resp:
        total = int(resp.headers.get("Content-Length") or 0)
        downloaded = 0
        with tmp.open("wb") as f:
            while True:
                chunk = resp.read(1 << 20)
                if not chunk:
                    break
                f.write(chunk)
                downloaded += len(chunk)
                if total > 0:
                    pct = int(downloaded * 100 / total)
                    if pct != last_pct and pct % 20 == 0:
                        emit("progress", f"{label} {pct}%")
                        last_pct = pct
    tmp.replace(dest)
    check_size(dest, min_bytes, label)
    return dest


def fetch_hf_file(repo_id: str, filename: str, dest: Path, min_bytes: int, label: str) -> Path:
    from huggingface_hub import hf_hub_download

    if dest.exists() and dest.stat().st_size >= min_bytes:
        emit("skip", f"{label} deja present ({human(dest.stat().st_size)})")
        return dest

    dest.parent.mkdir(parents=True, exist_ok=True)
    emit("fetch", f"{label} {repo_id}/{filename}")
    cached = hf_hub_download(repo_id=repo_id, filename=filename, cache_dir=str(HF_HUB_CACHE))
    cached_path = Path(cached)
    if cached_path.resolve() != dest.resolve():
        shutil.copy2(cached_path, dest)
    check_size(dest, min_bytes, label)
    return dest


# --------------------------------------------------------------------------
# Downloads
# --------------------------------------------------------------------------

def download_musetalk_v15() -> dict:
    paths = {}
    paths["unet"] = str(fetch_hf_file(
        repo_id="TMElyralab/MuseTalk",
        filename="musetalkV15/unet.pth",
        dest=MODELS_DIR / "musetalkV15" / "unet.pth",
        min_bytes=3_300_000_000,
        label="MuseTalk V15 unet.pth",
    ))
    paths["config"] = str(fetch_hf_file(
        repo_id="TMElyralab/MuseTalk",
        filename="musetalkV15/musetalk.json",
        dest=MODELS_DIR / "musetalkV15" / "musetalk.json",
        min_bytes=100,
        label="MuseTalk V15 config",
    ))
    return paths


def download_sd_vae() -> dict:
    paths = {}
    paths["model"] = str(fetch_hf_file(
        repo_id="stabilityai/sd-vae-ft-mse",
        filename="diffusion_pytorch_model.bin",
        dest=MODELS_DIR / "sd-vae" / "diffusion_pytorch_model.bin",
        min_bytes=300_000_000,
        label="SD VAE ft-mse",
    ))
    paths["config"] = str(fetch_hf_file(
        repo_id="stabilityai/sd-vae-ft-mse",
        filename="config.json",
        dest=MODELS_DIR / "sd-vae" / "config.json",
        min_bytes=100,
        label="SD VAE config",
    ))
    return paths


def download_whisper_tiny() -> dict:
    paths = {}
    for fname, min_size in [
        ("config.json", 100),
        ("pytorch_model.bin", 100_000_000),
        ("preprocessor_config.json", 100),
    ]:
        paths[fname] = str(fetch_hf_file(
            repo_id="openai/whisper-tiny",
            filename=fname,
            dest=MODELS_DIR / "whisper" / fname,
            min_bytes=min_size,
            label=f"Whisper-tiny/{fname}",
        ))
    return paths


def download_dwpose() -> dict:
    return {"pose_pt": str(fetch_hf_file(
        repo_id="yzd-v/DWPose",
        filename="dw-ll_ucoco_384.pth",
        dest=MODELS_DIR / "dwpose" / "dw-ll_ucoco_384.pth",
        min_bytes=380_000_000,
        label="DWPose dw-ll_ucoco_384",
    ))}


# face-parse-bisent : Google Drive (gdown) + pytorch.org direct
def download_face_parse() -> dict:
    paths = {}
    # 79999_iter.pth — Google Drive ID 154JgKpzCPW82qINcVieuPH3fZ2e0P812
    bisent_path = MODELS_DIR / "face-parse-bisent" / "79999_iter.pth"
    if bisent_path.exists() and bisent_path.stat().st_size > 40_000_000:
        emit("skip", f"face-parse-bisent already present ({human(bisent_path.stat().st_size)})")
    else:
        bisent_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            import gdown
        except ImportError:
            emit("install", "pip install gdown for face-parse-bisent (Google Drive)")
            import subprocess
            subprocess.run([sys.executable, "-m", "pip", "install", "gdown"], check=False, timeout=120)
            import gdown
        emit("fetch", "face-parse-bisent 79999_iter.pth (Google Drive)")
        gdown.download(
            id="154JgKpzCPW82qINcVieuPH3fZ2e0P812",
            output=str(bisent_path),
            quiet=False,
        )
        check_size(bisent_path, 40_000_000, "face-parse-bisent 79999_iter.pth")
    paths["bisent"] = str(bisent_path)

    paths["resnet18"] = str(fetch_url(
        url="https://download.pytorch.org/models/resnet18-5c106cde.pth",
        dest=MODELS_DIR / "face-parse-bisent" / "resnet18-5c106cde.pth",
        min_bytes=40_000_000,
        label="resnet18-5c106cde.pth",
    ))
    return paths


# --------------------------------------------------------------------------
# Status
# --------------------------------------------------------------------------

def status() -> dict:
    targets = {
        "musetalk_v15_unet": MODELS_DIR / "musetalkV15" / "unet.pth",
        "musetalk_v15_config": MODELS_DIR / "musetalkV15" / "musetalk.json",
        "sd_vae": MODELS_DIR / "sd-vae" / "diffusion_pytorch_model.bin",
        "whisper_tiny": MODELS_DIR / "whisper" / "pytorch_model.bin",
        "dwpose": MODELS_DIR / "dwpose" / "dw-ll_ucoco_384.pth",
        "face_parse_bisent": MODELS_DIR / "face-parse-bisent" / "79999_iter.pth",
        "face_parse_resnet18": MODELS_DIR / "face-parse-bisent" / "resnet18-5c106cde.pth",
    }
    info = {}
    for name, path in targets.items():
        info[name] = {
            "path": str(path),
            "exists": path.exists(),
            "size": path.stat().st_size if path.exists() else 0,
        }
    info["ok"] = all(v["exists"] for v in info.values() if isinstance(v, dict))
    info["models_dir"] = str(MODELS_DIR)
    return info


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--only", default="all", help="musetalk,sd_vae,whisper,dwpose,face_parse")
    args = parser.parse_args()

    if args.check:
        print(json.dumps(status(), indent=2), flush=True)
        return 0

    only = {s.strip() for s in args.only.split(",") if s.strip()}
    if "all" in only:
        only = {"musetalk", "sd_vae", "whisper", "dwpose", "face_parse"}

    result: dict = {"models_dir": str(MODELS_DIR)}
    try:
        if "musetalk" in only:
            result["musetalk"] = download_musetalk_v15()
        if "sd_vae" in only:
            result["sd_vae"] = download_sd_vae()
        if "whisper" in only:
            result["whisper"] = download_whisper_tiny()
        if "dwpose" in only:
            result["dwpose"] = download_dwpose()
        if "face_parse" in only:
            result["face_parse"] = download_face_parse()
    except Exception as exc:
        result["ok"] = False
        result["error"] = f"{type(exc).__name__}: {exc}"
        print(json.dumps(result, indent=2), flush=True)
        return 1

    result["ok"] = True
    print(json.dumps(result, indent=2), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
