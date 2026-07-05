"""
musetalk_runner.py -- Phase 3, MuseTalk V1.5 audio-driven lipsync wrapper.

MuseTalk (TMElyralab, 2024) est un latent-diffusion lipsync qui produit des
levres et dents NATIVEMENT realistes, contrairement a Wav2Lip qui floute la
zone bouche en latent 96x96. Ce runner expose une API CLI uniforme pour
cinema_pipeline.py :

  python musetalk_runner.py --check
  python musetalk_runner.py --drive --source img.png --audio voice.wav --output out.mp4

Performance mesuree (RTX 5070 Ti 16 GB, 3.77 s audio, face statique 768x1024) :
  - Landmarks face_alignment 2D-FAN  : ~35 s (premier appel, charge le FAN)
  - Whisper-tiny audio embedding     : ~2 s
  - UNet V15 latent diffusion        : ~30 s pour 24 batch passes
  - VAE decode + paste-back          : ~14 s pour 94 frames
  - ffmpeg encode + audio mux        : ~1 s
  Total                              : ~80 s pour 3.77 s de clip.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from cache_paths import configure_ml_cache_environment  # type: ignore

CACHE_ENV = configure_ml_cache_environment()

MUSETALK_REPO = Path(__file__).resolve().parent.parent / "MuseTalk"
MUSETALK_INFER = MUSETALK_REPO / "scripts" / "inference.py"
MUSETALK_MODELS = MUSETALK_REPO / "models"
MUSETALK_UNET = MUSETALK_MODELS / "musetalkV15" / "unet.pth"
MUSETALK_CONFIG = MUSETALK_MODELS / "musetalkV15" / "musetalk.json"


def emit(stage: str, detail: str):
    print(f"PROGRESS:{stage}:{detail}", flush=True)


def _run(cmd: list, timeout: int, cwd: str | None = None, env: dict | None = None) -> tuple:
    creationflags = 0
    if sys.platform == "win32":
        creationflags = 0x08000000
    full_env = os.environ.copy()
    if env:
        full_env.update(env)
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True,
                              timeout=timeout, creationflags=creationflags,
                              cwd=cwd, env=full_env, encoding="utf-8", errors="replace")
        return proc.returncode, proc.stdout, proc.stderr
    except subprocess.TimeoutExpired:
        return 124, "", f"timeout after {timeout}s"
    except Exception as exc:
        return 1, "", str(exc)


def cmd_check() -> dict:
    info = {
        "musetalk_repo": str(MUSETALK_REPO),
        "inference_py": MUSETALK_INFER.exists(),
        "unet_v15": MUSETALK_UNET.exists(),
        "config_v15": MUSETALK_CONFIG.exists(),
        "sd_vae": (MUSETALK_MODELS / "sd-vae" / "diffusion_pytorch_model.bin").exists(),
        "whisper_tiny": (MUSETALK_MODELS / "whisper" / "pytorch_model.bin").exists(),
        "dwpose": (MUSETALK_MODELS / "dwpose" / "dw-ll_ucoco_384.pth").exists(),
        "face_parse_bisent": (MUSETALK_MODELS / "face-parse-bisent" / "79999_iter.pth").exists(),
        "face_parse_resnet": (MUSETALK_MODELS / "face-parse-bisent" / "resnet18-5c106cde.pth").exists(),
    }
    info["ok"] = all(v for k, v in info.items() if k != "musetalk_repo" and isinstance(v, bool))
    return info


def cmd_drive(source: Path, audio: Path, output: Path,
              version: str = "v15", batch_size: int = 4) -> dict:
    """Drive a MuseTalk lipsync from ``source`` (image or video) + ``audio``,
    writing the result mp4 to ``output``."""
    if not MUSETALK_INFER.exists() or not MUSETALK_UNET.exists():
        return {"ok": False, "error": "musetalk_not_installed"}
    if not source.exists():
        return {"ok": False, "error": f"source not found: {source}"}
    if not audio.exists():
        return {"ok": False, "error": f"audio not found: {audio}"}

    # MuseTalk ingests a YAML "inference_config" listing tasks. We synthesize
    # a one-task YAML in a tempdir.
    with tempfile.TemporaryDirectory(prefix="musetalk_", dir=str(MUSETALK_REPO)) as tmp:
        tmp_path = Path(tmp)
        cfg = tmp_path / "task.yaml"
        cfg.write_text(
            f"task_0:\n video_path: \"{source.resolve().as_posix()}\"\n"
            f" audio_path: \"{audio.resolve().as_posix()}\"\n",
            encoding="utf-8",
        )

        result_dir = tmp_path / "results"
        out_name = output.stem + ".mp4"
        cmd = [
            sys.executable, "-m", "scripts.inference",
            "--inference_config", str(cfg.resolve()),
            "--result_dir", str(result_dir.resolve()),
            "--version", version,
            "--use_float16",
            "--batch_size", str(batch_size),
            "--output_vid_name", out_name,
            "--unet_config", "models/musetalkV15/musetalk.json",
            "--unet_model_path", "models/musetalkV15/unet.pth",
        ]
        emit("musetalk", f"V{version} latent-diffusion inference")
        rc, stdout, stderr = _run(
            cmd, timeout=1800, cwd=str(MUSETALK_REPO),
            env={"PYTHONIOENCODING": "utf-8", "PYTHONUTF8": "1"},
        )

        # MuseTalk drops final mp4 at <result_dir>/<version>/<out_name>.
        # Even when its post-cleanup raises 'save_dir_full' on image input,
        # the mp4 has already been written.
        produced = result_dir / version / out_name
        if not produced.exists():
            return {
                "ok": False,
                "error": f"MuseTalk produced no mp4 (rc={rc}): "
                         f"{(stderr or stdout)[-300:]}",
            }

        output.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(produced, output)
        return {"ok": True, "mp4": str(output), "engine": "musetalk-v15"}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--drive", action="store_true")
    parser.add_argument("--source", type=str)
    parser.add_argument("--audio", type=str)
    parser.add_argument("--output", type=str)
    parser.add_argument("--version", default="v15", choices=["v1", "v15"])
    parser.add_argument("--batch_size", type=int, default=4)
    args = parser.parse_args()

    if args.check:
        info = cmd_check()
        print(json.dumps(info), flush=True)
        sys.exit(0 if info["ok"] else 1)

    if not args.drive or not args.source or not args.audio or not args.output:
        print(json.dumps({"ok": False, "error": "--drive --source X --audio Y --output Z required"}), flush=True)
        sys.exit(1)

    result = cmd_drive(
        Path(args.source).resolve(), Path(args.audio).resolve(),
        Path(args.output).resolve(), version=args.version,
        batch_size=args.batch_size,
    )
    print(json.dumps(result), flush=True)
    sys.exit(0 if result.get("ok") else 1)


if __name__ == "__main__":
    main()
