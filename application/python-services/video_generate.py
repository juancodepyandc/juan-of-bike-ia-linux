"""
juan of bike IA - Wan 2.2 video generation

Supports:
  python video_generate.py --prompt "..." --output "..." --width 768 --height 512 --num_frames 49
  python video_generate.py --prompt "..." --output "..." --image ref.png --width 768 --height 512 --num_frames 49
"""

import argparse
import gc
import inspect
import json
import math
import os
import re
import signal
import subprocess
import sys
import threading
import time

from cache_paths import configure_ml_cache_environment


WAN_T2V_MODEL = "Wan-AI/Wan2.2-T2V-A14B-Diffusers"
WAN_I2V_MODEL = "Wan-AI/Wan2.2-I2V-A14B-Diffusers"

# Wan 2.2 A14B GGUF — the 14B MoE model quantized down to 4-bit so that both
# the HighNoise and LowNoise experts fit in 16 GB VRAM simultaneously via
# group-block offload. This is the quality-winning path on consumer cards:
# you get the full A14B architecture (not a 5B distillation, not LTX) at
# ~9.65 GB per expert, which is what the user explicitly asked for.
WAN_T2V_GGUF_REPO = "QuantStack/Wan2.2-T2V-A14B-GGUF"
WAN_I2V_GGUF_REPO = "QuantStack/Wan2.2-I2V-A14B-GGUF"
WAN_GGUF_QUANT_DEFAULT = "Q4_K_M"  # 9.65 GB per expert — fits 16 GB with offload

# Wan 2.2 TI2V-5B — unified 5B parameter text+image-to-video from Wan-AI.
# ~34 GB fp16 on disk but only ~10-14 GB active VRAM during inference with
# group-block offload. Kept as a secondary option when GGUF A14B fails.
WAN_TI2V_5B_MODEL = "Wan-AI/Wan2.2-TI2V-5B-Diffusers"
LTX_VIDEO_MODEL = "Lightricks/LTX-Video"
LTX_SPEED_MODEL = "Lightricks/LTX-Video"              # ltxv-2b-distilled (rapide, 16GB VRAM)
# Previously pointed at "Lightricks/LTX-Video-13B-fp8" which is GATED on HF
# and required user auth — every quality-mode run crashed with
# "not a valid model identifier" because the user had no token. The unified
# `Lightricks/LTX-Video` repo is OPEN and already ships the quality
# transformer variants inside, so we point both modes at it. Diffusers will
# pick the right weights based on config.json.
LTX_QUALITY_MODEL = "Lightricks/LTX-Video"

REQUIRED_PACKAGES = {
    "torch": "torch",
    "diffusers": "diffusers",
    "PIL": "Pillow",
    "numpy": "numpy",
    "accelerate": "accelerate",
    "transformers": "transformers",
    "sentencepiece": "sentencepiece",
    "imageio": "imageio[ffmpeg]",
    "safetensors": "safetensors",
}


def emit(stage: str, detail: str):
    print(f"PROGRESS:{stage}:{detail}", flush=True)


# Signal handler pour SIGTERM (exit 15) — ecrit un JSON d'erreur propre avant de quitter
def _sigterm_handler(signum, frame):
    error_msg = (
        "Generation interrompue par le systeme (SIGTERM). "
        "Cause probable: VRAM insuffisante ou timeout du watchdog. "
        "Essayez avec une resolution plus basse ou moins de frames."
    )
    emit("error", error_msg)
    print(json.dumps({"ok": False, "error": error_msg}), flush=True)
    sys.exit(1)


signal.signal(signal.SIGTERM, _sigterm_handler)


def configure_runtime_environment():
    configure_ml_cache_environment()
    os.environ.setdefault("PYTHONUTF8", "1")
    os.environ.setdefault("HF_HUB_DISABLE_PROGRESS_BARS", "1")
    os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")
    os.environ.setdefault("TORCHDYNAMO_DISABLE", "1")
    # Only apply the CUDA allocator hint — the torch.compile disables above
    # are known to conflict with some diffusers kernels on PyTorch 2.11 and
    # can cause fresh crashes. We keep the allocator tuning because it is
    # strictly additive (newer allocator, same API).
    os.environ.setdefault(
        "PYTORCH_CUDA_ALLOC_CONF",
        "expandable_segments:True",
    )


def ensure_dependencies():
    missing = []
    for import_name, pip_name in REQUIRED_PACKAGES.items():
        try:
            __import__(import_name)
        except Exception:
            missing.append(pip_name)
    if missing:
        emit("install", f"Installation automatique de {', '.join(missing)}...")
        subprocess.check_call(
            [sys.executable, "-m", "pip", "install", "--disable-pip-version-check", "--quiet"] + missing,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
        )
        emit("install", "Dependances video installees.")


def preflight_model_access(model_ids):
    """Validate that every HuggingFace repo in `model_ids` is reachable
    without auth, emit clear download progress, and skip models that are
    gated behind a token.

    Returns a list of `(model_id, ok, reason)` tuples — the caller can
    filter its strategies to avoid picking a model that will fail to load.
    """
    import urllib.request
    import urllib.error
    results = []
    for mid in model_ids:
        url = f"https://huggingface.co/api/models/{mid}"
        try:
            with urllib.request.urlopen(url, timeout=10) as resp:
                data = resp.read().decode("utf-8", errors="replace")
            gated = '"gated":"auto"' in data or '"gated":true' in data or '"gated": true' in data
            if gated:
                emit("preflight", f"{mid} est gate sur HuggingFace — strategie ignoree.")
                results.append((mid, False, "gated"))
            else:
                results.append((mid, True, "ok"))
        except urllib.error.HTTPError as http_err:
            reason = f"HTTP {http_err.code}"
            emit("preflight", f"{mid} inaccessible ({reason}) — strategie ignoree.")
            results.append((mid, False, reason))
        except Exception as check_err:
            emit("preflight", f"{mid} verification impossible ({type(check_err).__name__}) — on tente quand meme.")
            results.append((mid, True, "assumed-ok"))
    return results


def filter_strategies_by_access(strategies):
    """Drop strategies whose primary model is gated/unreachable.

    Runs one preflight per unique model_id referenced by the strategy list.
    If every Wan strategy fails the check, we still keep the LTX fallback
    because the user explicitly asks for "quality video no matter what".
    """
    unique_ids = []
    seen = set()
    for s in strategies:
        mid = s.get("model_override") or s.get("companion_model") or s.get("ltx_model")
        if mid and mid not in seen:
            seen.add(mid)
            unique_ids.append(mid)
    verdicts = dict()
    for mid, ok, reason in preflight_model_access(unique_ids):
        verdicts[mid] = ok
    kept = []
    dropped = []
    for s in strategies:
        mid = s.get("model_override") or s.get("companion_model") or s.get("ltx_model")
        if mid and verdicts.get(mid) is False:
            dropped.append(s["id"])
            continue
        kept.append(s)
    if dropped:
        emit("preflight", f"Strategies ignorees (modele gate/inaccessible): {', '.join(dropped)}")
    if not kept:
        emit("preflight", "Toutes les strategies sont inaccessibles; on reessaye la derniere en mode degrade.")
        return strategies[-1:]
    return kept


def check_vram():
    try:
        out = subprocess.check_output(
            ["nvidia-smi", "--query-gpu=memory.total,memory.free", "--format=csv,noheader,nounits"],
            text=True,
            timeout=5,
        )
        first = out.strip().splitlines()[0]
        parts = first.split(",")
        total = float(parts[0].strip()) / 1024
        free = float(parts[1].strip()) / 1024
        return total, free
    except Exception:
        return 0, 0


def _try_vram_unblock():
    """Best-effort VRAM defragmentation/empty when the card sits at 99 %+.

    Called by the monitor when saturation persists but we don't want to kill
    the worker yet. torch.cuda.empty_cache() frees the cached allocator
    fragments that commonly pin VRAM at 99.5-99.9 % between DiT steps on a
    group-offload pipeline, giving the next step real headroom without
    interrupting the generation.
    """
    try:
        import torch  # type: ignore
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
            torch.cuda.synchronize()
            try:
                import gc
                gc.collect()
            except Exception:
                pass
            return True
    except Exception:
        pass
    return False


def _exit_when_parent_dies():
    """Watchdog Windows : thread qui attend la mort du process parent et
    termine immediatement ce worker (os._exit). Best-effort, silencieux."""
    try:
        import ctypes
        import threading as _th

        ppid = os.getppid()
        SYNCHRONIZE = 0x00100000
        handle = ctypes.windll.kernel32.OpenProcess(SYNCHRONIZE, False, ppid)
        if not handle:
            return

        def _wait_and_die():
            ctypes.windll.kernel32.WaitForSingleObject(handle, 0xFFFFFFFF)
            os._exit(1)

        _th.Thread(target=_wait_and_die, daemon=True, name="parent-watchdog").start()
    except Exception:
        pass


def _available_commit_gb() -> float:
    """Commit memoire disponible (RAM + pagefile restants) en GB, via
    GlobalMemoryStatusEx — zero dependance. -1 si indisponible (non-Windows)."""
    try:
        import ctypes

        class MEMORYSTATUSEX(ctypes.Structure):
            _fields_ = [
                ("dwLength", ctypes.c_ulong),
                ("dwMemoryLoad", ctypes.c_ulong),
                ("ullTotalPhys", ctypes.c_uint64),
                ("ullAvailPhys", ctypes.c_uint64),
                ("ullTotalPageFile", ctypes.c_uint64),
                ("ullAvailPageFile", ctypes.c_uint64),
                ("ullTotalVirtual", ctypes.c_uint64),
                ("ullAvailVirtual", ctypes.c_uint64),
                ("ullAvailExtendedVirtual", ctypes.c_uint64),
            ]

        st = MEMORYSTATUSEX()
        st.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
        if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(st)):
            return -1.0
        return st.ullAvailPageFile / 1024 ** 3
    except Exception:
        return -1.0


def _total_commit_gb() -> float:
    """Limite de commit totale (RAM + taille courante du pagefile) en GB."""
    try:
        import ctypes

        class MEMORYSTATUSEX(ctypes.Structure):
            _fields_ = [
                ("dwLength", ctypes.c_ulong),
                ("dwMemoryLoad", ctypes.c_ulong),
                ("ullTotalPhys", ctypes.c_uint64),
                ("ullAvailPhys", ctypes.c_uint64),
                ("ullTotalPageFile", ctypes.c_uint64),
                ("ullAvailPageFile", ctypes.c_uint64),
                ("ullTotalVirtual", ctypes.c_uint64),
                ("ullAvailVirtual", ctypes.c_uint64),
                ("ullAvailExtendedVirtual", ctypes.c_uint64),
            ]

        st = MEMORYSTATUSEX()
        st.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
        if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(st)):
            return -1.0
        return st.ullTotalPageFile / 1024 ** 3
    except Exception:
        return -1.0


def _ensure_commit_headroom(target_gb: float = 26.0):
    """Anti `os error 1455` (fichier de pagination insuffisant).

    Apres un reboot Windows le pagefile retombe au minimum systeme ; le
    chargement Wan TI2V-5B fp16 (~16-20 GB de commit au-dela de la RAM)
    burst plus vite que la croissance automatique → 1455, et meme LTX
    crashe (0xC0000005). Reproduit en live v84.

    Fix sans droits admin : forcer la croissance PROGRESSIVE du pagefile en
    allouant des blocs de 256 MB touches, puis tout liberer. Le fichier de
    pagination reste agrandi jusqu'au prochain reboot → le commit budget
    suffit pour les chargements fp16 suivants.
    """
    avail = _available_commit_gb()
    if avail < 0 or avail >= target_gb:
        return

    # Garde-fou disque : la croissance du pagefile consomme l'espace du
    # volume systeme. Ne jamais viser au-dela de (libre - 8 GB).
    try:
        import shutil as _sh
        disk_free_gb = _sh.disk_usage("C:\\").free / 1024 ** 3
    except Exception:
        disk_free_gb = 1e9
    max_growth = max(0.0, disk_free_gb - 8.0)
    effective_target = min(target_gb, avail + max_growth)
    if effective_target <= avail + 1.0:
        emit("vram", f"Commit {avail:.1f}GB et disque trop juste ({disk_free_gb:.1f}GB libre) — pas de gonflage possible.")
        return

    emit("vram", f"Commit dispo {avail:.1f}GB < {effective_target:.0f}GB — gonflage progressif du pagefile (anti 1455)...")
    step = 128 * 1024 * 1024
    need_gb = effective_target - avail
    limit_start = _total_commit_gb()
    blocks = []
    consecutive_failures = 0
    started = time.time()
    try:
        # En tenant les blocs, le commit DISPONIBLE ne monte pas (charge et
        # limite croissent ensemble) : la bonne condition d'arret est la
        # croissance de la LIMITE. La croissance pagefile est ASYNCHRONE :
        # sur refus (MemoryError) on attend que Windows etende, puis retry.
        while _total_commit_gb() - limit_start < need_gb and time.time() - started < 180:
            try:
                blocks.append(bytearray(step))
                consecutive_failures = 0
                time.sleep(0.15)
            except MemoryError:
                consecutive_failures += 1
                if consecutive_failures >= 6:
                    break
                time.sleep(1.5)
    finally:
        blocks.clear()
        del blocks
        gc.collect()
    emit("vram", f"Commit dispo apres gonflage: {_available_commit_gb():.1f}GB (limite {_total_commit_gb():.0f}GB, cible +{need_gb:.0f}GB)")


def _evict_ollama_models():
    """Best-effort : decharge tous les modeles Ollama residents (VRAM + RAM).

    GET /api/ps liste les modeles charges, puis POST /api/generate avec
    keep_alive=0 force leur eviction immediate. Echec silencieux si Ollama
    est down — on ne bloque jamais une generation video pour ca.
    """
    try:
        import requests as _rq
        base = os.environ.get("OLLAMA_URL", "http://127.0.0.1:11434")
        ps = _rq.get(f"{base}/api/ps", timeout=4).json()
        models = [m.get("name") for m in ps.get("models", []) if m.get("name")]
        for name in models:
            try:
                _rq.post(
                    f"{base}/api/generate",
                    json={"model": name, "prompt": "", "keep_alive": 0, "stream": False},
                    timeout=15,
                )
            except Exception:
                pass
        if models:
            emit("vram", f"Ollama evince avant chargement video: {', '.join(models)}")
    except Exception:
        pass
    # v84 : ComfyUI aussi — un Kontext/FLUX reste charge apres une session
    # image (~10-11 GB VRAM) et etouffe le chargement Wan. POST /free est
    # le pendant serveur de comfyuiFreeVram() cote TS. Best-effort.
    try:
        import requests as _rq2
        _rq2.post(
            "http://127.0.0.1:8188/free",
            json={"unload_models": True, "free_memory": True},
            timeout=6,
        )
        emit("vram", "ComfyUI /free demande avant chargement video")
    except Exception:
        pass


def monitor_vram(stop_event, pid):
    """Watchdog with two tiers instead of one hard-kill threshold:

      Tier 1 (99.5% for 30 s): proactive — trigger torch.cuda.empty_cache()
      to release allocator fragments. On a 16 GB card with group-block
      offload the stored allocator routinely pins ~150 MB of dead cache
      that keeps used_pct hovering at 99.8% even between steps. A single
      empty_cache() drops it back to ~95-98% and the next step proceeds.

      Tier 2 (99.9% for 40 s AND no Python progress lately): real hang.
      Kill the worker.

    This matches what the user saw — "stuck at 99.8% 0 GB free but no
    obvious error". Tier 1 is the fix; tier 2 is the last resort.
    """
    consecutive_warn = 0
    consecutive_critical = 0
    last_bucket = None
    WARN_THRESHOLD = 0.995     # 99.5 % — trigger empty_cache
    SATURATION_THRESHOLD = 0.999  # 99.9 % — real saturation
    WARN_POLLS_BEFORE_UNBLOCK = 6  # 6 × 5 s = 30 s before we try to unblock
    CONSECUTIVE_REQUIRED = 8       # 8 × 5 s = 40 s at >= 99.9 % → kill
    unblock_attempts = 0
    MAX_UNBLOCK_ATTEMPTS = 4       # beyond that, hardware is genuinely full
    while not stop_event.is_set():
        total, free = check_vram()
        if total > 0:
            used_pct = (total - free) / total
            if used_pct >= SATURATION_THRESHOLD:
                consecutive_critical += 1
                consecutive_warn += 1
                emit("vram", f"VRAM critique a {used_pct*100:.1f}% ({consecutive_critical}/{CONSECUTIVE_REQUIRED})")
                if consecutive_critical >= CONSECUTIVE_REQUIRED:
                    emit("vram", f"Arret de securite, VRAM critique soutenue {CONSECUTIVE_REQUIRED * 5}s ({used_pct*100:.1f}%)")
                    try:
                        os.kill(pid, signal.SIGTERM)
                    except Exception:
                        pass
                    sys.exit(1)
            elif used_pct >= WARN_THRESHOLD:
                # Tier 1: VRAM between 99.5 % and 99.9 %. Not catastrophic,
                # but almost no headroom for the next step. After ~30 s we
                # proactively flush the torch allocator cache — usually
                # releases 150-500 MB pinned between diffusion steps.
                consecutive_warn += 1
                consecutive_critical = 0
                if consecutive_warn == 1:
                    emit("vram", f"VRAM tendue a {used_pct*100:.1f}% ({free*1024:.0f}MB libres) — surveillance active")
                if consecutive_warn >= WARN_POLLS_BEFORE_UNBLOCK and unblock_attempts < MAX_UNBLOCK_ATTEMPTS:
                    unblock_attempts += 1
                    emit("vram", f"Tentative de deblocage VRAM #{unblock_attempts} (torch.cuda.empty_cache)")
                    _try_vram_unblock()
                    consecutive_warn = 0
            else:
                consecutive_critical = 0
                consecutive_warn = 0
                bucket = round(used_pct * 20) / 20
                if used_pct > 0.9 and bucket != last_bucket:
                    emit("vram", f"VRAM chargee a {used_pct*100:.1f}% ({free:.1f}GB libres)")
                    last_bucket = bucket
                elif used_pct <= 0.9:
                    last_bucket = None
        stop_event.wait(5)


def parse_args():
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--prompt")
    parser.add_argument("--output")
    parser.add_argument("--image")
    parser.add_argument("--width", type=int)
    parser.add_argument("--height", type=int)
    parser.add_argument("--num_frames", type=int)
    parser.add_argument("--thumbnail")
    parser.add_argument("--vram_gb", type=float, default=0.0)
    parser.add_argument("--model_mode", default="speed", choices=["speed", "quality"])
    parser.add_argument(
        "--quality_mode",
        default="auto",
        choices=["auto", "balanced", "premium"],
        help=(
            "auto (default): pipeline picks the highest quality the hardware "
            "and duration can sustain — equivalent to premium on 16 GB VRAM. "
            "balanced: explicit speed override, ~2 min. "
            "premium: explicit max fidelity override."
        ),
    )
    parser.add_argument(
        "--motion_interp",
        default="1",
        choices=["0", "1", "2"],
        help=(
            "0: no interpolation. 1: ffmpeg minterpolate to 48 fps (default). "
            "2: aggressive 60 fps + MCI with 'mci' mode for silky motion."
        ),
    )
    # v82lo : seed pour reproduction stricte d'un shot. Si fourni, on
    # force torch.manual_seed + numpy + diffusers Generator. Sans seed,
    # Wan2.2 utilise random — chaque run = résultat différent.
    parser.add_argument("--seed", type=int, default=None,
                        help="Random seed pour reproduction stricte (None = random)")
    # v82ln : negative prompt pour éviter artefacts (deformed, blurry, etc.)
    parser.add_argument("--negative_prompt", default=None,
                        help="Negative prompt anti-artefacts (deformed, blurry, watermark...)")
    parser.add_argument("--worker-config-json")
    parser.add_argument("positional", nargs="*")
    args = parser.parse_args()

    # v82lo : expose args via global pour que la fonction render() puisse
    # lire seed + negative_prompt sans devoir refactorer toute la signature.
    global _args_global
    _args_global = args

    if args.worker_config_json:
        return args

    if args.prompt and args.output and args.width and args.height and args.num_frames:
        return args

    if len(args.positional) >= 5:
        args.prompt = args.positional[0]
        args.output = args.positional[1]
        args.width = int(args.positional[2])
        args.height = int(args.positional[3])
        args.num_frames = min(int(args.positional[4]), 97)
        return args

    raise ValueError(
        "Usage: video_generate.py --prompt --output [--image path] --width --height --num_frames"
    )


def round_to_32(value):
    return max(32, round(value / 32) * 32)


def _ffmpeg_interpolate(src_path, dst_path, src_fps=24, target_fps=48):
    """Use ffmpeg's `minterpolate` filter to synthesise intermediate frames.

    This is motion-compensated interpolation (mci + obmc): it estimates optical
    flow between adjacent frames and creates new frames in between, smoothing
    out the limb-snapping temporal artefacts typical of diffusion video.
    Works on CPU only; a 49-frame clip processes in ~3-8 s.
    """
    import shutil
    import subprocess
    ffmpeg_bin = shutil.which("ffmpeg")
    if not ffmpeg_bin:
        # imageio[ffmpeg] ships a bundled ffmpeg binary
        try:
            import imageio_ffmpeg  # type: ignore
            ffmpeg_bin = imageio_ffmpeg.get_ffmpeg_exe()
        except Exception:
            raise RuntimeError("ffmpeg indisponible — interpolation desactivee")
    cmd = [
        ffmpeg_bin, "-y", "-i", src_path,
        # minterpolate with motion-compensated interpolation, overlapped block
        # matching, bidirectional reference frames. Produces visibly smoother
        # motion than simple duplication or linear blend.
        "-vf", f"minterpolate=fps={target_fps}:mi_mode=mci:mc_mode=aobmc:me_mode=bidir:vsbmc=1",
        "-c:v", "libx264",
        "-preset", "slow",
        "-crf", "17",  # near-lossless — we already paid the generation cost
        "-pix_fmt", "yuv420p",
        dst_path,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=240)
    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg minterpolate echec (code {result.returncode}): {result.stderr[-300:]}")


def frame_to_uint8(frame):
    import numpy as np

    if hasattr(frame, "numpy"):
        frame_np = frame.cpu().numpy() if hasattr(frame, "cpu") else frame.numpy()
    elif hasattr(frame, "convert"):
        frame_np = np.array(frame)
    else:
        frame_np = np.array(frame)

    if frame_np.ndim == 3 and frame_np.shape[0] in (1, 3, 4):
        frame_np = np.transpose(frame_np, (1, 2, 0))

    if frame_np.ndim == 2:
        frame_np = np.stack([frame_np] * 3, axis=-1)
    elif frame_np.ndim == 3 and frame_np.shape[2] == 1:
        frame_np = np.repeat(frame_np, 3, axis=2)
    elif frame_np.ndim == 3 and frame_np.shape[2] > 3:
        frame_np = frame_np[:, :, :3]

    if frame_np.dtype != np.uint8:
        if frame_np.size == 0:
            frame_np = np.zeros((1, 1, 3), dtype=np.uint8)
        elif frame_np.max() <= 1.0:
            frame_np = (frame_np * 255).clip(0, 255).astype(np.uint8)
        else:
            frame_np = frame_np.clip(0, 255).astype(np.uint8)

    return frame_np


def validate_key_frame(frame_np):
    import numpy as np

    if frame_np.size == 0 or frame_np.ndim != 3:
        return False, "image-cle vide ou invalide", {
            "mean_luma": 0.0,
            "std_luma": 0.0,
            "dynamic_range": 0.0,
            "white_ratio": 0.0,
            "black_ratio": 0.0,
            "near_median_ratio": 1.0,
        }

    rgb = frame_np[:, :, :3].astype(np.float32)
    luminance = 0.2126 * rgb[:, :, 0] + 0.7152 * rgb[:, :, 1] + 0.0722 * rgb[:, :, 2]
    median_rgb = np.median(rgb, axis=(0, 1), keepdims=True)
    per_pixel_deviation = np.max(np.abs(rgb - median_rgb), axis=2)

    metrics = {
        "mean_luma": round(float(np.mean(luminance)), 2),
        "std_luma": round(float(np.std(luminance)), 2),
        "dynamic_range": round(float(np.percentile(luminance, 99) - np.percentile(luminance, 1)), 2),
        "white_ratio": round(float(np.mean(np.all(rgb >= 245, axis=2))), 4),
        "black_ratio": round(float(np.mean(np.all(rgb <= 10, axis=2))), 4),
        "near_median_ratio": round(float(np.mean(per_pixel_deviation <= 6.0)), 4),
    }

    if metrics["white_ratio"] >= 0.97 and metrics["std_luma"] < 8:
        return False, "image-cle presque entierement blanche", metrics
    if metrics["black_ratio"] >= 0.97 and metrics["std_luma"] < 8:
        return False, "image-cle presque entierement noire", metrics
    if metrics["dynamic_range"] < 12 and metrics["std_luma"] < 6:
        return False, "image-cle quasi uniforme sans contraste exploitable", metrics
    if metrics["near_median_ratio"] >= 0.985 and metrics["std_luma"] < 10:
        return False, "image-cle quasi uniforme avec trop peu de details", metrics

    return True, None, metrics


def format_validation_summary(metrics):
    return (
        f"luma={metrics['mean_luma']}, "
        f"std={metrics['std_luma']}, "
        f"range={metrics['dynamic_range']}, "
        f"white={metrics['white_ratio']:.2%}, "
        f"black={metrics['black_ratio']:.2%}, "
        f"uniform={metrics['near_median_ratio']:.2%}"
    )


def parse_last_json_line(output):
    lines = [line.strip() for line in output.splitlines() if line.strip()]
    for index in range(len(lines) - 1, -1, -1):
        try:
            return json.loads(lines[index])
        except Exception:
            continue
    return None


def child_error_summary(output):
    ansi_escape = re.compile(r"\x1B\[[0-?]*[ -/]*[@-~]")
    lines = []
    saw_model_loading_failure = False
    noisy_loading_markers = (
        "Loading checkpoint shards",
        "Loading weights:",
        "Fetching ",
        "Loading pipeline components",
        "warnings.warn(",
    )

    for raw_line in output.splitlines():
        line = ansi_escape.sub("", raw_line).strip()
        if (
            not line
            or line.startswith("PROGRESS:")
            or line.startswith("THUMBNAIL:")
            or line.startswith("SAVED:")
        ):
            continue

        if any(marker in line for marker in noisy_loading_markers):
            saw_model_loading_failure = True
            continue

        lines.append(line)

    if lines:
        return " | ".join(lines[-4:])
    if saw_model_loading_failure:
        return "Le worker video a quitte pendant le chargement du gros modele video."
    return "Le worker video a quitte sans detail exploitable."


def get_compute_dtype(torch):
    if not torch.cuda.is_available():
        return torch.float32
    if hasattr(torch.cuda, "is_bf16_supported") and torch.cuda.is_bf16_supported():
        return torch.bfloat16
    return torch.float16


def _adaptive_resolution_budget(num_frames: int, mode_quality: str, vram_gb: float):
    """Return (max_width, max_height) based on the requested duration.

    Philosophy: ALWAYS maximum quality unless the user explicitly caps. The
    model decides the best resolution it can sustain for the requested
    duration. Short clips hit HD/FHD, long clips drop toward LTX/Wan native
    resolution to stay in VRAM.

    Budget in Mpix·seconds (24 fps, sequential CPU offload on 16 GB VRAM):
      * balanced 16 GB ~= 3.0 Mpix·s  (was 1.8 — too low, forced 704×480)
      * premium  16 GB ~= 4.5 Mpix·s  (bigger window, longer inference)
    Cards with >22 GB get roughly double.
    """
    seconds = max(1.0, num_frames / 24.0)
    if vram_gb >= 22:
        budget_mpixs = 9.0 if mode_quality == "premium" else 6.5
    else:
        budget_mpixs = 4.5 if mode_quality == "premium" else 3.0
    target_mpix = budget_mpixs / seconds  # megapixels per frame allowed
    # Hard caps per tier — FHD/2K/4K ceilings.
    if vram_gb >= 22:
        hard_cap_mpix = 8.3 if mode_quality == "premium" else 3.69
    else:
        hard_cap_mpix = 3.69 if mode_quality == "premium" else 2.07
    mpix = min(target_mpix, hard_cap_mpix)
    # Choose a 16:9 resolution that matches the target megapixels. Diffusion
    # models want multiples of 32.
    # 4K = 3840×2160 (8.29 Mpix), 2K = 2560×1440 (3.69), FHD = 1920×1080 (2.07),
    # 720p = 1280×720 (0.92), 540p = 960×544 (0.52), native Wan = 832×480 (0.40).
    candidates = [
        (3840, 2176, 8.36),  # 4K
        (2560, 1440, 3.69),  # 2K
        (1920, 1088, 2.09),  # FHD
        (1600, 896, 1.43),
        (1280, 736, 0.94),   # 720p
        (1088, 608, 0.66),
        (960, 544, 0.52),
        (832, 480, 0.40),    # Wan native
        (704, 400, 0.28),
        (576, 320, 0.18),
    ]
    for w, h, m in candidates:
        if m <= mpix + 0.01:
            return w, h
    return 576, 320  # floor


def build_strategies(mode, width, height, num_frames, vram_gb=0.0, ltx_model=None, quality_mode="balanced"):
    """Build an ordered list of generation strategies adapted to the available VRAM.

    Tiers:
      < 8 GB  → GGUF/sequential offload, minimal resolution
      8-12 GB → group-block (num_blocks=2), conservative resolution
      12-24 GB → group-block (num_blocks=4), full requested resolution
      ≥ 24 GB → no offload, maximum resolution and frames

    IMPORTANT: Wan 2.2 A14B has 14B parameters. Even with aggressive offload
    it requires ~22-30 GB RAM+VRAM to instantiate the transformer pipeline.
    On a 16 GB card (mid tier) every Wan 2.2 attempt today exits with
    "Le worker video a quitte pendant le chargement" because the worker gets
    SIGKILLed by the OS when host RAM saturates. We therefore promote LTX
    to PRIMARY on any card with less than ~22 GB of usable VRAM, and keep
    Wan only on true 24 GB+ cards where it can actually load. LTX gives
    visually comparable results and converges in ~20 s instead of crashing.
    """

    # Determine tier from VRAM if nvidia-smi value was passed; fall back to
    # the conservative tier when VRAM is unknown (0).
    if vram_gb >= 24:
        tier = "high"
    elif vram_gb >= 12:
        tier = "mid"
    elif vram_gb >= 8:
        tier = "low"
    else:
        tier = "minimal"

    # VRAM-tight path (12-22 GB cards like the 5070 Ti, 4080, 3080 Ti, A4000).
    # Priority: Wan 2.2 A14B GGUF Q4_K_M (true 14B MoE quality, ~9.6 GB per
    # expert, with aggressive offload both experts fit in 16 GB) → Wan 2.2
    # TI2V-5B (unified 5B fallback) → LTX (safety net).
    #
    # Step counts tuned for visual sharpness, not speed. Below ~40 LTX steps
    # you get the motion blur + morphing limbs the user complained about.
    # Resolutions pinned to each model's NATIVE training resolution so the
    # diffusion output isn't a bilinear upscale that looks soft.
    #
    # PREMIUM MODE: the caller accepts long render times in exchange for
    # maximum fidelity. On 32 GB RAM + 16 GB VRAM, the full fp16 A14B
    # (42 GB resident) does NOT fit — attempting it segfaults during load.
    # Instead we escalate GGUF quantization: Q4_K_M → Q6_K (nearly imperceptible
    # quality loss vs fp16, 12 GB per expert) → Q5_K_M as secondary. Combined
    # with sequential CPU offload and 60 steps this produces clean anatomy and
    # stable identity across frames, which is what the user actually asked for.
    # 16 GB VRAM path. Wan 2.2 TI2V-5B primary + LTX safety.
    #
    # Why TI2V-5B over A14B on 16 GB:
    #   - A14B MoE (2 × 14B experts) keeps exploding on Windows (ACCESS_VIOLATION
    #     in the allocator, group_offload + .to() incompatibility, 42 GB fp16
    #     residents that don't fit 32 GB RAM). Verified across multiple attempts.
    #   - TI2V-5B is a SINGLE 5B transformer — no MoE swap fragmentation,
    #     ~16 GB fp16 resident (fits 32 GB RAM easily), and it is UNIFIED
    #     (T2V + I2V in one pipeline).
    #   - The user has it already cached (32 GB on disk in HF hub).
    #   - It is a real Wan 2.2 checkpoint — trained on the same data as A14B,
    #     so its character/object recognition is orders of magnitude better
    #     than LTX-Video for named subjects.
    # `enable_model_cpu_offload()` is the battle-tested offload path:
    # whole model lives on CPU, moves to CUDA block-by-block during inference.
    # No group hooks, no .to() conflict, no fragmentation edge case.
    if vram_gb > 0 and vram_gb < 22:
        chosen_ltx = ltx_model or LTX_VIDEO_MODEL
        # "Quality always first" philosophy: we pick the max resolution the
        # adaptive budget allows for the given duration, never cap below the
        # model's native high-res. The user only ever gets a lower number if
        # they explicitly passed a smaller --width / --height.
        frames_cap = 97 if quality_mode == "premium" else 81
        ltx_frames = min(max(num_frames, 25), frames_cap)
        # TI2V-5B supports up to 1280×720 @ 24 fps per the Wan-AI model card.
        # We cap at that upper bound (native HD), letting the adaptive budget
        # choose between 1280×720 (short clip) and e.g. 704×480 (long clip).
        wan_frames = min(max(num_frames, 33), 73)
        wan_budget_w, wan_budget_h = _adaptive_resolution_budget(wan_frames, quality_mode, vram_gb)
        ltx_budget_w, ltx_budget_h = _adaptive_resolution_budget(ltx_frames, quality_mode, vram_gb)
        wan_w = min(width, wan_budget_w, 1280)
        wan_h = min(height, wan_budget_h, 720)
        ltx_w = min(width, ltx_budget_w, 1920)
        ltx_h = min(height, ltx_budget_h, 1088)
        wan_steps = 60 if quality_mode == "premium" else 50  # bumped from 40/50
        ltx_steps = 60 if quality_mode == "premium" else 50

        base_wan = {
            "family": "wan",
            "model_override": WAN_TI2V_5B_MODEL,
            "offload": "model_cpu",
            "width": wan_w,
            "height": wan_h,
            "num_frames": wan_frames,
            "num_inference_steps": wan_steps,
        }
        base_ltx = {
            "family": "ltx",
            "ltx_model": chosen_ltx,
            "offload": "ltx_group",
            "width": ltx_w,
            "height": ltx_h,
            "num_frames": ltx_frames,
            "num_inference_steps": ltx_steps,
        }
        base_ltx_safe = {
            **base_ltx,
            "width": min(ltx_w, 768),
            "height": min(ltx_h, 512),
            "num_frames": min(ltx_frames, 65),
            "num_inference_steps": max(36, ltx_steps - 14),
        }

        if mode == "i2v":
            return [
                {**base_wan, "id": "wan5b-i2v-primary"},
                {**base_ltx, "id": "ltx-i2v-safety"},
                {**base_ltx_safe, "id": "ltx-i2v-lowmem"},
            ]
        return [
            {**base_wan, "id": "wan5b-t2v-primary"},
            {**base_ltx, "id": "ltx-t2v-safety"},
            {**base_ltx_safe, "id": "ltx-t2v-lowmem"},
        ]

    if mode == "i2v":
        strategies = []

        if tier == "high":
            strategies.append({
                "id": "i2v-bf16-full",
                "family": "wan",
                "offload": "none",
                "width": min(width, 768),
                "height": min(height, 512),
                "num_frames": min(num_frames, 49),
                "num_inference_steps": 50,
            })
        elif tier == "mid":
            strategies.append({
                "id": "i2v-group-block",
                "family": "wan",
                "offload": "group_block",
                "num_blocks_per_group": 4,
                "width": min(width, 640),
                "height": min(height, 480),
                "num_frames": min(num_frames, 33),
                "num_inference_steps": 30,
            })
        elif tier == "low":
            strategies.append({
                "id": "i2v-group-block-safe",
                "family": "wan",
                "offload": "group_block",
                "num_blocks_per_group": 2,
                "width": min(width, 480),
                "height": min(height, 320),
                "num_frames": min(num_frames, 25),
                "num_inference_steps": 26,
            })
        else:  # minimal
            strategies.append({
                "id": "i2v-gguf-sequential",
                # family "wan_gguf" (et non "wan") : c'est la seule branche du loader
                # qui sait injecter des transformers GGUF via GGUFQuantizationConfig.
                # Avec "wan", le repo GGUF etait passe a WanPipeline.from_pretrained
                # -> crash garanti sur tres basse VRAM.
                "family": "wan_gguf",
                "offload": "sequential",
                "gguf_repo": WAN_I2V_GGUF_REPO,
                "gguf_quant": WAN_GGUF_QUANT_DEFAULT,
                "width": min(width, 480),
                "height": min(height, 320),
                "num_frames": min(num_frames, 25),
                "num_inference_steps": 22,
            })

        # Always add a conservative Wan fallback then the LTX safety net
        strategies.append({
            "id": "i2v-cpu-offload-min",
            "family": "wan",
            "offload": "model_cpu",
            "width": min(width, 512),
            "height": min(height, 320),
            "num_frames": min(num_frames, 25),
            "num_inference_steps": 22,
        })
        strategies.append({
            "id": "ltx-i2v-fallback",
            "family": "ltx",
            "ltx_model": ltx_model or LTX_VIDEO_MODEL,
            "offload": "ltx_group",
            "width": min(width, 576),
            "height": min(height, 576),
            "num_frames": min(max(num_frames, 17), 81),
            "num_inference_steps": 30,
        })
        return strategies

    # T2V strategies
    strategies = []

    if tier == "high":
        strategies.append({
            "id": "t2v-bf16-full",
            "family": "wan",
            "offload": "none",
            "width": min(width, 832),
            "height": min(height, 640),
            "num_frames": min(num_frames, 81),
            "num_inference_steps": 50,
        })
    elif tier == "mid":
        strategies.append({
            "id": "t2v-group-block",
            "family": "wan",
            "offload": "group_block",
            "num_blocks_per_group": 4,
            "width": min(width, 768),
            "height": min(height, 512),
            "num_frames": min(num_frames, 49),
            "num_inference_steps": 50,
        })
    elif tier == "low":
        strategies.append({
            "id": "t2v-group-block-safe",
            "family": "wan",
            "offload": "group_block",
            "num_blocks_per_group": 2,
            "width": min(width, 512),
            "height": min(height, 384),
            "num_frames": min(num_frames, 33),
            "num_inference_steps": 28,
        })
    else:  # minimal
        strategies.append({
            "id": "t2v-sequential",
            "family": "wan",
            "offload": "sequential",
            "width": min(width, 480),
            "height": min(height, 320),
            "num_frames": min(num_frames, 25),
            "num_inference_steps": 22,
        })

    strategies.append({
        "id": "t2v-cpu-offload-safe",
        "family": "wan",
        "offload": "model_cpu",
        "width": min(width, 640),
        "height": min(height, 384),
        "num_frames": min(num_frames, 33),
        "num_inference_steps": 26,
    })
    strategies.append({
        "id": "ltx-t2v-fallback",
        "family": "ltx",
        "ltx_model": ltx_model or LTX_VIDEO_MODEL,
        "offload": "ltx_group",
        "width": min(width, 768),
        "height": min(height, 512),
        "num_frames": min(max(num_frames, 17), 97),
        "num_inference_steps": 36,
    })
    return strategies


def align_dimensions(pipe, width, height):
    mod_value = 32
    try:
        patch_size = getattr(pipe.transformer.config, "patch_size", None)
        if isinstance(patch_size, (list, tuple)) and len(patch_size) > 1:
            mod_value = int(pipe.vae_scale_factor_spatial * patch_size[1])
        elif isinstance(patch_size, int):
            mod_value = int(pipe.vae_scale_factor_spatial * patch_size)
    except Exception:
        mod_value = 32

    width = max(mod_value, round(width / mod_value) * mod_value)
    height = max(mod_value, round(height / mod_value) * mod_value)
    return width, height


def apply_offload_strategy(torch, text_encoder, transformer, use_stream=False, num_blocks_per_group=4):
    from diffusers.hooks.group_offloading import apply_group_offloading

    onload_device = torch.device("cuda")
    offload_device = torch.device("cpu")

    apply_group_offloading(
        text_encoder,
        onload_device=onload_device,
        offload_device=offload_device,
        offload_type="block_level",
        num_blocks_per_group=num_blocks_per_group,
    )
    transformer.enable_group_offload(
        onload_device=onload_device,
        offload_device=offload_device,
        offload_type="block_level",
        num_blocks_per_group=num_blocks_per_group,
        use_stream=use_stream,
    )


def load_video_pipeline(mode, model_id, strategy):
    import torch
    from diffusers import (
        AutoencoderKLWan,
        AutoModel,
        LTXImageToVideoPipeline,
        LTXPipeline,
        WanImageToVideoPipeline,
        WanPipeline,
        WanTransformer3DModel,
    )
    from diffusers.hooks import apply_group_offloading
    from transformers import CLIPVisionModel, UMT5EncoderModel

    compute_dtype = get_compute_dtype(torch)
    cache_dir = os.environ.get("HF_HUB_CACHE")
    emit("loading_pipeline", f"Strategie {strategy['id']} - chargement des composants...")

    # ── Wan 2.2 A14B GGUF (MoE) path ──
    # The GGUF repos ship quantized transformer experts ONLY; every other
    # pipeline component (text_encoder, tokenizer, VAE, scheduler, image_encoder
    # when I2V) is pulled from the companion A14B Diffusers repo which is what
    # Diffusers' WanPipeline.from_pretrained knows how to parse. We therefore
    # compose the pipeline by injecting GGUF-loaded transformers into the
    # standard A14B skeleton.
    if strategy.get("family") == "wan_gguf":
        try:
            from diffusers import GGUFQuantizationConfig
        except Exception as gguf_err:
            raise RuntimeError(
                f"GGUFQuantizationConfig indisponible dans diffusers {getattr(__import__('diffusers'), '__version__', '?')}: {gguf_err}"
            )
        from huggingface_hub import hf_hub_download

        gguf_repo = strategy.get("gguf_repo") or (WAN_I2V_GGUF_REPO if mode == "i2v" else WAN_T2V_GGUF_REPO)
        quant = strategy.get("gguf_quant", WAN_GGUF_QUANT_DEFAULT)
        companion = strategy.get("companion_model") or (WAN_I2V_MODEL if mode == "i2v" else WAN_T2V_MODEL)
        offload_type = strategy.get("offload", "group_block")
        blocks = strategy.get("num_blocks_per_group", 2)

        family_tag = "I2V" if mode == "i2v" else "T2V"

        # Download the two MoE experts (HighNoise + LowNoise) via hf_hub_download
        # so Diffusers' from_single_file can resolve a local path.
        high_path = hf_hub_download(
            repo_id=gguf_repo,
            filename=f"HighNoise/Wan2.2-{family_tag}-A14B-HighNoise-{quant}.gguf",
            cache_dir=cache_dir,
        )
        low_path = hf_hub_download(
            repo_id=gguf_repo,
            filename=f"LowNoise/Wan2.2-{family_tag}-A14B-LowNoise-{quant}.gguf",
            cache_dir=cache_dir,
        )

        emit("loading_pipeline", f"Strategie {strategy['id']} - chargement transformer HighNoise {quant}...")
        transformer_high = WanTransformer3DModel.from_single_file(
            high_path,
            quantization_config=GGUFQuantizationConfig(compute_dtype=compute_dtype),
            torch_dtype=compute_dtype,
            config=f"{companion}/transformer",
            cache_dir=cache_dir,
        )
        emit("loading_pipeline", f"Strategie {strategy['id']} - chargement transformer LowNoise {quant}...")
        transformer_low = WanTransformer3DModel.from_single_file(
            low_path,
            quantization_config=GGUFQuantizationConfig(compute_dtype=compute_dtype),
            torch_dtype=compute_dtype,
            config=f"{companion}/transformer_2",
            cache_dir=cache_dir,
        )

        emit("loading_pipeline", f"Strategie {strategy['id']} - chargement text_encoder UMT5 XXL...")
        text_encoder = UMT5EncoderModel.from_pretrained(
            companion,
            subfolder="text_encoder",
            torch_dtype=compute_dtype,
            low_cpu_mem_usage=True,
            cache_dir=cache_dir,
        )

        emit("loading_pipeline", f"Strategie {strategy['id']} - chargement VAE...")
        vae = AutoencoderKLWan.from_pretrained(
            companion,
            subfolder="vae",
            torch_dtype=torch.float32,
            low_cpu_mem_usage=True,
            cache_dir=cache_dir,
        )

        # Aggressive CPU offload on every GGUF component so the two 9.6 GB
        # experts can ping-pong onto the GPU one at a time without OOMing.
        onload_device = torch.device("cuda")
        offload_device = torch.device("cpu")
        for name, module in (
            ("transformer_high", transformer_high),
            ("transformer_low", transformer_low),
        ):
            try:
                apply_group_offloading(
                    module,
                    onload_device=onload_device,
                    offload_device=offload_device,
                    offload_type="leaf_level" if offload_type == "sequential" else "block_level",
                    num_blocks_per_group=blocks,
                    use_stream=False,
                )
            except Exception as off_err:
                emit("loading_pipeline", f"Offload {name} indisponible: {off_err}")
        try:
            apply_group_offloading(
                text_encoder,
                onload_device=onload_device,
                offload_device=offload_device,
                offload_type="block_level",
                num_blocks_per_group=2,
            )
        except Exception:
            pass

        if mode == "i2v":
            image_encoder = AutoModel.from_pretrained(
                companion,
                subfolder="image_encoder",
                torch_dtype=torch.float32,
                cache_dir=cache_dir,
            )
            pipe = WanImageToVideoPipeline.from_pretrained(
                companion,
                transformer=transformer_high,
                transformer_2=transformer_low,
                text_encoder=text_encoder,
                vae=vae,
                image_encoder=image_encoder,
                torch_dtype=compute_dtype,
                cache_dir=cache_dir,
            )
        else:
            pipe = WanPipeline.from_pretrained(
                companion,
                transformer=transformer_high,
                transformer_2=transformer_low,
                text_encoder=text_encoder,
                vae=vae,
                torch_dtype=compute_dtype,
                cache_dir=cache_dir,
            )
        # DO NOT call pipe.to("cuda") — the Wan 2.2 A14B GGUF path already
        # applied group_offloading to both MoE transformers and the text
        # encoder, which makes diffusers refuse any manual .to(). The group
        # offload hook handles CUDA placement per-block at inference time.
        # Move only the UNHOOKED components (vae, image_encoder) explicitly.
        def _is_group_offloaded(mod):
            try:
                return any(getattr(m, "_diffusers_hook", None) is not None for m in mod.modules())
            except Exception:
                return False
        try:
            if hasattr(pipe, "vae") and pipe.vae is not None and not _is_group_offloaded(pipe.vae):
                pipe.vae.to("cuda")
        except Exception:
            pass
        try:
            if hasattr(pipe, "image_encoder") and pipe.image_encoder is not None and not _is_group_offloaded(pipe.image_encoder):
                pipe.image_encoder.to("cuda")
        except Exception:
            pass
        if hasattr(pipe, "vae") and hasattr(pipe.vae, "enable_tiling"):
            pipe.vae.enable_tiling()
        if hasattr(pipe, "vae") and hasattr(pipe.vae, "enable_slicing"):
            pipe.vae.enable_slicing()
        return pipe

    if strategy.get("family") == "ltx":
        _ltx_model = strategy.get("ltx_model", LTX_VIDEO_MODEL)
        transformer = AutoModel.from_pretrained(
            _ltx_model,
            subfolder="transformer",
            torch_dtype=compute_dtype,
            cache_dir=cache_dir,
        )
        if hasattr(transformer, "enable_layerwise_casting") and hasattr(torch, "float8_e4m3fn"):
            transformer.enable_layerwise_casting(
                storage_dtype=torch.float8_e4m3fn,
                compute_dtype=compute_dtype,
            )

        pipeline_cls = LTXImageToVideoPipeline if mode == "i2v" else LTXPipeline
        pipe = pipeline_cls.from_pretrained(
            _ltx_model,
            transformer=transformer,
            torch_dtype=compute_dtype,
            cache_dir=cache_dir,
        )

        onload_device = torch.device("cuda")
        offload_device = torch.device("cpu")
        if hasattr(pipe.transformer, "enable_group_offload"):
            pipe.transformer.enable_group_offload(
                onload_device=onload_device,
                offload_device=offload_device,
                offload_type="leaf_level",
                use_stream=False,
            )
        apply_group_offloading(
            pipe.text_encoder,
            onload_device=onload_device,
            offload_device=offload_device,
            offload_type="block_level",
            num_blocks_per_group=2,
        )
        apply_group_offloading(
            pipe.vae,
            onload_device=onload_device,
            offload_device=offload_device,
            offload_type="leaf_level",
        )
        # DO NOT call pipe.to("cuda") here: once a module is group-offloaded,
        # diffusers explicitly refuses any manual .to() and raises
        # "is group offloaded and moving it to cuda via .to() is not supported".
        # The group offload hook already places each block on CUDA at the
        # right moment during inference, so no manual placement is needed.
        if hasattr(pipe, "vae") and hasattr(pipe.vae, "enable_tiling"):
            pipe.vae.enable_tiling()
        return pipe

    # Wan 2.2 TI2V-5B is a UNIFIED text+image-to-video model — there is no
    # image_encoder subfolder; the image path is passed directly to the pipe
    # call and WanPipeline routes it internally. Force the T2V path for
    # either mode so we don't try to load a non-existent image_encoder.
    is_ti2v_unified = model_id == WAN_TI2V_5B_MODEL

    if mode == "i2v" and not is_ti2v_unified:
        # Use AutoModel so the correct class (e.g. CLIPVisionModelWithProjection)
        # is resolved automatically from config.json rather than forcing CLIPVisionModel.
        image_encoder = AutoModel.from_pretrained(
            model_id,
            subfolder="image_encoder",
            torch_dtype=torch.float32,
            cache_dir=cache_dir,
        )
        vae = AutoencoderKLWan.from_pretrained(
            model_id,
            subfolder="vae",
            torch_dtype=torch.float32,
            low_cpu_mem_usage=True,
            cache_dir=cache_dir,
        )

        offload_type = strategy.get("offload", "group_block")
        blocks = strategy.get("num_blocks_per_group", 4)

        if offload_type == "group_block":
            text_encoder = UMT5EncoderModel.from_pretrained(
                model_id,
                subfolder="text_encoder",
                torch_dtype=compute_dtype,
                low_cpu_mem_usage=True,
                cache_dir=cache_dir,
            )
            transformer = WanTransformer3DModel.from_pretrained(
                model_id,
                subfolder="transformer",
                torch_dtype=compute_dtype,
                low_cpu_mem_usage=True,
                cache_dir=cache_dir,
            )
            apply_offload_strategy(torch, text_encoder, transformer, num_blocks_per_group=blocks)
            pipe = WanImageToVideoPipeline.from_pretrained(
                model_id,
                vae=vae,
                transformer=transformer,
                text_encoder=text_encoder,
                image_encoder=image_encoder,
                torch_dtype=compute_dtype,
                cache_dir=cache_dir,
            )
            # pipe.to("cuda") is forbidden after group_offloading: diffusers
            # refuses manual .to() on hooked modules. The offload hook places
            # each block on CUDA per-step.
        elif offload_type == "none":
            pipe = WanImageToVideoPipeline.from_pretrained(
                model_id,
                vae=vae,
                image_encoder=image_encoder,
                torch_dtype=compute_dtype,
                cache_dir=cache_dir,
            )
            pipe.to("cuda")
        elif offload_type == "sequential":
            pipe = WanImageToVideoPipeline.from_pretrained(
                model_id,
                vae=vae,
                image_encoder=image_encoder,
                torch_dtype=compute_dtype,
                cache_dir=cache_dir,
            )
            pipe.enable_sequential_cpu_offload()
        else:  # model_cpu or any unknown fallback
            pipe = WanImageToVideoPipeline.from_pretrained(
                model_id,
                vae=vae,
                image_encoder=image_encoder,
                torch_dtype=compute_dtype,
                cache_dir=cache_dir,
            )
            pipe.enable_model_cpu_offload()
    else:
        vae = AutoencoderKLWan.from_pretrained(
            model_id,
            subfolder="vae",
            torch_dtype=torch.float32,
            low_cpu_mem_usage=True,
            cache_dir=cache_dir,
        )

        offload_type = strategy.get("offload", "group_block")
        blocks = strategy.get("num_blocks_per_group", 4)

        if offload_type == "group_block":
            text_encoder = UMT5EncoderModel.from_pretrained(
                model_id,
                subfolder="text_encoder",
                torch_dtype=compute_dtype,
                low_cpu_mem_usage=True,
                cache_dir=cache_dir,
            )
            transformer = WanTransformer3DModel.from_pretrained(
                model_id,
                subfolder="transformer",
                torch_dtype=compute_dtype,
                low_cpu_mem_usage=True,
                cache_dir=cache_dir,
            )
            apply_offload_strategy(torch, text_encoder, transformer, num_blocks_per_group=blocks)
            pipe = WanPipeline.from_pretrained(
                model_id,
                vae=vae,
                transformer=transformer,
                text_encoder=text_encoder,
                torch_dtype=compute_dtype,
                cache_dir=cache_dir,
            )
            # pipe.to("cuda") forbidden after group_offloading (see I2V path).
        elif offload_type == "none":
            pipe = WanPipeline.from_pretrained(
                model_id,
                vae=vae,
                torch_dtype=compute_dtype,
                cache_dir=cache_dir,
            )
            pipe.to("cuda")
        elif offload_type == "sequential":
            pipe = WanPipeline.from_pretrained(
                model_id,
                vae=vae,
                torch_dtype=compute_dtype,
                cache_dir=cache_dir,
            )
            pipe.enable_sequential_cpu_offload()
        else:  # model_cpu or any unknown fallback
            pipe = WanPipeline.from_pretrained(
                model_id,
                vae=vae,
                torch_dtype=compute_dtype,
                cache_dir=cache_dir,
            )
            pipe.enable_model_cpu_offload()

    if hasattr(pipe, "vae") and hasattr(pipe.vae, "enable_tiling"):
        pipe.vae.enable_tiling()
    if hasattr(pipe, "vae") and hasattr(pipe.vae, "enable_slicing"):
        pipe.vae.enable_slicing()

    return pipe


def run_worker(worker_config):
    configure_runtime_environment()
    os.environ.setdefault("HF_HUB_DISABLE_PROGRESS_BARS", "1")
    os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")

    import torch
    from PIL import Image as PILImage
    from diffusers.utils import export_to_video

    if not torch.cuda.is_available():
        raise RuntimeError(
            "Torch CUDA indisponible dans le runtime Python actif. Le module video doit utiliser un Python avec support CUDA."
        )

    prompt = worker_config["prompt"]
    output_path = worker_config["output_path"]
    image_path = worker_config.get("image_path")
    thumbnail_path = worker_config.get("thumbnail_path")
    mode = worker_config["mode"]
    model_id = worker_config["model_id"]
    strategy = worker_config["strategy"]
    active_model_id = LTX_VIDEO_MODEL if strategy.get("family") == "ltx" else model_id

    torch.cuda.empty_cache()
    gc.collect()

    emit(
        "init",
        f"Initialisation du pipeline {mode.upper()} via {strategy['id']} ({strategy['width']}x{strategy['height']}, {strategy['num_frames']} frames)",
    )
    pipe = load_video_pipeline(mode, model_id, strategy)
    width, height = align_dimensions(pipe, round_to_32(strategy["width"]), round_to_32(strategy["height"]))

    negative_prompt = (
        # Quality floor
        "worst quality, low quality, low resolution, pixelation, mosaic artifacts, compression noise, "
        "jpeg artifacts, aliasing, blurry, out of focus, motion blur, soft focus, hazy, ghosting, "
        "frame ghosting, temporal incoherence, frame jump, frame jitter, frame freeze, stuttering, "
        # Anatomy — HUMAN
        "warped anatomy, melted face, morphing body, melting limbs, extra limbs, missing limbs, "
        "floating limbs, disconnected body parts, mutated hands, too many fingers, distorted proportions, "
        # Anatomy — ANIMAL / CREATURE (user's request: don't fabricate legs on legless species)
        "fabricated limbs on legless animals, legs on snakes, legs on fish, legs on seahorse, "
        "fins on land animals, extra heads, mutated anatomy, species hybridization errors, "
        "anatomically impossible body parts, invented appendages, wrong number of legs, "
        "wrong number of fins, wrong number of wings, non-existent limbs for this species, "
        # Physics — contact and collision
        "phasing through objects, passing through solid bodies, clipping through ground, "
        "floating off ground when standing, broken contact with surface, gravity defying, "
        "weightless motion when weight is implied, objects intersecting solid geometry, "
        "limbs intersecting body, character body passing through props, "
        # Identity drift
        "duplicate subjects, cloned face, identity drift, face changing between frames, "
        "teleportation, pose discontinuity, changing clothes unless requested, random background jumps, "
        # Color / encoding
        "over-saturated colors, posterization, banding, lowres upscale, watermark, text, signature"
    )

    # v82lo : append shot-specific negative prompt provided by cinema_pipeline.
    # Preserves the anatomy/physics baseline above + adds shot-specific terms
    # (e.g. "motion blur" for action shots, "close-up artifacts" for wides).
    extra_neg = getattr(_args_global, "negative_prompt", None) if "_args_global" in globals() else None
    if extra_neg:
        negative_prompt = f"{negative_prompt}, {extra_neg}"

    # Family-specific guidance tuning. LTX was trained with guidance 3.0-3.5;
    # pushing higher over-sharpens and collapses limbs into blur. Wan 2.2 A14B
    # prefers 4.5-5.0 for crisp motion. Diffusion models are extremely sensitive
    # to this — wrong guidance is a major reason for the "blob" outputs.
    family = strategy.get("family", "")
    if family == "ltx":
        guidance = 3.2
    elif family == "wan_gguf":
        guidance = 4.8
    else:  # wan (5B or any other future variant)
        guidance = 4.5

    call_kwargs = {
        "prompt": prompt,
        "negative_prompt": negative_prompt,
        "width": width,
        "height": height,
        "num_frames": strategy["num_frames"],
        "num_inference_steps": strategy["num_inference_steps"],
        "guidance_scale": guidance,
    }

    # v82lo : seed pour reproduction stricte. torch.Generator + manual_seed
    # sur cuda si dispo, sinon cpu. Si seed est None, le generator n'est
    # pas passé, le pipeline utilise random.
    seed_val = getattr(_args_global, "seed", None) if "_args_global" in globals() else None
    if seed_val is not None:
        try:
            import torch as _torch
            device = "cuda" if _torch.cuda.is_available() else "cpu"
            generator = _torch.Generator(device=device).manual_seed(int(seed_val))
            call_kwargs["generator"] = generator
            emit("seed", f"manual_seed={seed_val} on {device}")
        except Exception as _e:
            emit("seed_warn", f"failed to set seed {seed_val}: {_e}")

    # Inspect signature once, before any version-sensitive kwargs are set.
    signature = inspect.signature(pipe.__call__)

    # guidance_rescale counter-acts the over-saturation and blown contours
    # that show up at high guidance. 0.7 is the sweet spot for most diffusion
    # video models — keeps the prompt-adherence of high guidance while
    # restoring natural contrast. Only passed if the pipeline accepts it
    # (older diffusers signatures don't).
    if "guidance_rescale" in signature.parameters:
        call_kwargs["guidance_rescale"] = 0.7

    if strategy.get("family") == "ltx":
        if "decode_timestep" in signature.parameters:
            call_kwargs["decode_timestep"] = 0.05
        if "decode_noise_scale" in signature.parameters:
            call_kwargs["decode_noise_scale"] = 0.025

    if image_path:
        if not os.path.exists(image_path):
            raise FileNotFoundError(f"Image de reference introuvable: {image_path}")
        call_kwargs["image"] = PILImage.open(image_path).convert("RGB").resize((width, height))
        if strategy.get("family") == "ltx" and "image_cond_noise_scale" in signature.parameters:
            call_kwargs["image_cond_noise_scale"] = 0.025

    if "callback_on_step_end" in signature.parameters:

        def on_step_end(_pipe, step_index, _timestep, callback_kwargs):
            current_step = int(step_index) + 1
            emit("generating", f"Step {current_step}/{strategy['num_inference_steps']}")
            return callback_kwargs

        call_kwargs["callback_on_step_end"] = on_step_end

    emit("loading_done", f"Pipeline charge avec {strategy['id']} - debut de la generation")
    emit(
        "generating",
        "Generation video en cours..." if strategy.get("family") == "ltx" else "Generation video Wan 2.2 en cours...",
    )
    start = time.time()
    video = pipe(**call_kwargs).frames[0]
    elapsed = time.time() - start

    emit("validating", "Validation de l'image-cle extraite...")
    middle_idx = len(video) // 2
    frame = video[middle_idx]
    frame_np = frame_to_uint8(frame)
    validation_ok, validation_reason, validation_metrics = validate_key_frame(frame_np)
    validation_summary = format_validation_summary(validation_metrics)

    if thumbnail_path:
        try:
            os.makedirs(os.path.dirname(thumbnail_path), exist_ok=True)
            PILImage.fromarray(frame_np).save(thumbnail_path)
            print(f"THUMBNAIL:{thumbnail_path}", flush=True)
        except Exception as thumb_err:
            print(f"THUMBNAIL_ERROR:{thumb_err}", flush=True)

    if not validation_ok:
        raise RuntimeError(
            f"Validation visuelle echouee: {validation_reason}. Image-cle rejetee ({validation_summary})."
        )

    emit("saving", f"Sauvegarde de la sortie ({elapsed:.1f}s)")
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    # CRITICAL: LTX-Video and Wan 2.2 are both trained at 24 fps native. The
    # previous export at fps=16 was stretching the frames — a 49-frame clip
    # trained at 24 fps (~2 s of motion) was being played as 49/16 = 3 s,
    # which is why motion looked choppy and limbs "froze". Matching the
    # model's native fps gives smooth, correctly-timed playback.
    family = strategy.get("family", "")
    export_fps = 24 if family in {"ltx", "wan", "wan_gguf"} else 16
    try:
        export_to_video(video, output_path, fps=export_fps)
    except TypeError:
        # Older diffusers took only two positional args.
        export_to_video(video, output_path)

    # ── Motion-compensated frame interpolation via ffmpeg ──
    # The diffusion model outputs 24 fps; temporal artefacts (limbs snapping
    # between positions) become invisible once the frame rate is doubled and
    # ffmpeg's optical-flow motion estimator synthesises the intermediate
    # frames. This is the same technique RIFE uses, built into ffmpeg's
    # `minterpolate` filter — no extra dependency, runs on CPU in seconds.
    # Pull from env so the pipeline signature stays unchanged — the main()
    # entrypoint writes AURORA_VIDEO_MOTION_INTERP before spawning the worker.
    interp_level = os.environ.get("AURORA_VIDEO_MOTION_INTERP", "1")
    try:
        interp_level_int = int(interp_level)
    except Exception:
        interp_level_int = 1
    if interp_level_int >= 1:
        target_fps = 60 if interp_level_int >= 2 else 48
        interp_out = output_path.replace(".mp4", f"_smooth{target_fps}.mp4")
        try:
            _ffmpeg_interpolate(output_path, interp_out, src_fps=export_fps, target_fps=target_fps)
            # Replace the original with the smooth version so downstream
            # downloads / players pick it up transparently.
            if os.path.exists(interp_out) and os.path.getsize(interp_out) > 1024:
                os.replace(interp_out, output_path)
                emit("saving", f"Motion-interpolation {export_fps}->{target_fps} fps applique")
        except Exception as interp_err:
            emit("saving", f"Interpolation ignoree ({interp_err})")
    print(f"SAVED:{output_path}", flush=True)
    print(
        json.dumps(
            {
                "ok": True,
                "path": output_path,
                "elapsed_seconds": round(elapsed, 1),
                "mode": mode,
                "model": active_model_id,
                "strategy": strategy["id"],
                "output_validated": True,
                "validation_summary": validation_summary,
                "validation": {
                    "ok": True,
                    "reason": None,
                    "summary": validation_summary,
                    "metrics": validation_metrics,
                    "thumbnail_path": thumbnail_path,
                },
            }
        )
    )

    del pipe
    del video
    torch.cuda.empty_cache()
    gc.collect()


def run_worker_subprocess(worker_config):
    # v84 BUG RACINE : Popen(text=True) sans encoding decode la sortie du
    # worker en cp1252 (locale Windows FR). Premier octet UTF-8 hors cp1252
    # (barre tqdm, accent) → UnicodeDecodeError dans la boucle de lecture →
    # plus personne ne lit le pipe → le worker se FIGE sur write() (buffer
    # OS plein) pendant que finally:child.wait() attend pour toujours →
    # zombie de 9+ GB de commit, puis os error 1455 en cascade sur tous les
    # chargements suivants. Reproduit et diagnostique en live.
    # Fix : UTF-8 force des DEUX cotes du pipe + errors=replace + kill du
    # worker si la lecture casse malgre tout.
    worker_env = {**os.environ, "PYTHONIOENCODING": "utf-8", "PYTHONUTF8": "1"}
    try:
        child = subprocess.Popen(
            [sys.executable, __file__, "--worker-config-json", json.dumps(worker_config)],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            bufsize=1,
            env=worker_env,
        )
    except Exception as spawn_err:
        error_msg = f"Impossible de lancer le sous-processus video: {spawn_err}"
        emit("error", error_msg)
        print(json.dumps({"ok": False, "error": error_msg}), flush=True)
        return 1, error_msg

    lines = []
    try:
        for raw_line in child.stdout or []:
            line = raw_line.rstrip("\n")
            lines.append(line)
            if (
                line.startswith("PROGRESS:")
                or line.startswith("THUMBNAIL:")
                or line.startswith("SAVED:")
                or line.strip().startswith("{")
            ):
                print(line, flush=True)
    except Exception as read_err:
        # Ne JAMAIS laisser un worker vivant sans lecteur de pipe.
        lines.append(f"[lecture sortie worker interrompue: {read_err}]")
        try:
            child.kill()
        except Exception:
            pass
    finally:
        child.wait()

    exit_code = child.returncode or 0
    output = "\n".join(lines)

    # If the worker crashed without emitting JSON, synthesize one from captured output
    if exit_code != 0 and not parse_last_json_line(output):
        summary = child_error_summary(output)
        fallback_json = json.dumps({
            "ok": False,
            "error": summary or f"Le worker video a quitte avec le code {exit_code} sans detail.",
        })
        print(fallback_json, flush=True)
        lines.append(fallback_json)
        output = "\n".join(lines)

    return exit_code, output


def main():
    args = parse_args()
    configure_runtime_environment()

    # Propagate the motion-interpolation preference to worker subprocesses via
    # the environment so the export path in run_worker can pick it up without
    # another plumbing round-trip.
    os.environ["AURORA_VIDEO_MOTION_INTERP"] = str(getattr(args, "motion_interp", "1"))

    if args.worker_config_json:
        # v84 : le worker DOIT mourir avec son parent. Sans ca, un kill du
        # parent (timeout UI, crash bridge, reboot partiel) laisse un worker
        # orphelin qui retient des dizaines de GB de commit — reproduit en
        # live : 115 GB de commit consommes par 3 orphelins → os error 1455
        # sur tous les chargements suivants.
        _exit_when_parent_dies()
        try:
            ensure_dependencies()
        except Exception as dep_err:
            print(json.dumps({"ok": False, "error": f"Installation des dependances echouee: {dep_err}"}), flush=True)
            sys.exit(1)
        worker_config = json.loads(args.worker_config_json)
        try:
            run_worker(worker_config)
        except Exception as exc:
            import traceback
            tb = traceback.format_exc()
            print(json.dumps({
                "ok": False,
                "error": str(exc)[-900:],
                "traceback": tb[-1200:],
            }), flush=True)
            sys.exit(1)
        return

    ensure_dependencies()
    width = round_to_32(int(args.width))
    height = round_to_32(int(args.height))
    num_frames = min(int(args.num_frames), 97)
    prompt = args.prompt
    output_path = args.output
    image_path = args.image
    thumbnail_path = args.thumbnail
    mode = "i2v" if image_path else "t2v"
    model_id = WAN_I2V_MODEL if image_path else WAN_T2V_MODEL

    # v84 : eviction Ollama + budget commit AVANT la mesure de VRAM — sinon
    # le clamp resolution ci-dessous lit la VRAM pendant que qwen (qui vient
    # de servir taskIntelligence) squatte encore la carte, et bride a 480x320
    # un rendu qui aurait toute la carte 2 secondes plus tard. Reproduit en
    # live depuis le tunnel.
    _evict_ollama_models()
    _ensure_commit_headroom()

    total_vram, free_vram = check_vram()
    # Use VRAM from args if provided (passed by VideoView), else use runtime detection
    detected_vram = args.vram_gb if args.vram_gb > 0 else total_vram
    emit("vram", f"VRAM disponible: {free_vram:.1f}GB libre / {total_vram:.1f}GB total (tier base: {detected_vram:.1f}GB)")

    # Pre-check VRAM: si moins de 2GB libre, reduire automatiquement la resolution
    if total_vram > 0 and free_vram < 2.0:
        emit("vram", f"VRAM tres basse ({free_vram:.1f}GB libre). Reduction automatique de la resolution.")
        width = min(width, 480)
        height = min(height, 320)
        num_frames = min(num_frames, 25)
    elif total_vram > 0 and free_vram < 4.0:
        emit("vram", f"VRAM limitee ({free_vram:.1f}GB libre). Ajustement conservateur.")
        width = min(width, 640)
        height = min(height, 480)
        num_frames = min(num_frames, 33)

    stop_monitor = threading.Event()
    monitor_thread = threading.Thread(target=monitor_vram, args=(stop_monitor, os.getpid()), daemon=True)
    monitor_thread.start()

    try:
        ltx_model = LTX_QUALITY_MODEL if getattr(args, "model_mode", "speed") == "quality" else LTX_SPEED_MODEL
        quality_mode_raw = getattr(args, "quality_mode", "auto")
        # "auto" is the new default — the pipeline picks the highest quality
        # the hardware + duration can sustain. On 16 GB VRAM this maps to
        # premium; on >=22 GB cards it gives the full 4K budget.
        if quality_mode_raw == "auto":
            quality_mode = "premium" if detected_vram > 0 else "balanced"
        else:
            quality_mode = quality_mode_raw
        emit("quality_mode", f"Mode qualite: {quality_mode} (demande: {quality_mode_raw})")
        strategies = build_strategies(
            mode, width, height, num_frames,
            vram_gb=detected_vram, ltx_model=ltx_model, quality_mode=quality_mode,
        )
        # Pre-check each strategy's model on HF: gated / 404 / network-down
        # repos get dropped BEFORE we spend minutes downloading before a
        # terminal auth error. This is what was making LTX-Video-13B-fp8
        # crash the whole video module on non-authenticated accounts.
        emit("preflight", "Verification de l'acces aux modeles video...")
        strategies = filter_strategies_by_access(strategies)
        last_failure = None

        emit("loading_start", "Demarrage du chargement video...")
        for attempt, strategy in enumerate(strategies, start=1):
            emit(
                "repair",
                f"Tentative {attempt}/{len(strategies)} avec {strategy['id']} ({strategy['width']}x{strategy['height']}, {strategy['num_frames']} frames)",
            )
            # Allow strategy to override the default model (e.g. GGUF variant for low VRAM)
            effective_model_id = strategy.get("model_override", model_id)
            worker_config = {
                "prompt": prompt,
                "output_path": output_path,
                "image_path": image_path,
                "thumbnail_path": thumbnail_path,
                "mode": mode,
                "model_id": effective_model_id,
                "strategy": strategy,
            }
            exit_code, output = run_worker_subprocess(worker_config)
            result = parse_last_json_line(output)

            if exit_code == 0 and result and result.get("ok") and result.get("path"):
                return

            error_message = result.get("error") if isinstance(result, dict) else child_error_summary(output)
            last_failure = {
                "exit_code": exit_code,
                "error": error_message or child_error_summary(output),
                "strategy": strategy["id"],
            }

            if attempt < len(strategies):
                emit(
                    "repair",
                    f"Echec de {strategy['id']} ({last_failure['error']}). Nouvelle tentative plus conservative...",
                )
                time.sleep(1)

        final_error = last_failure or {
            "exit_code": -1,
            "error": "Le pipeline video a echoue sans detail exploitable.",
            "strategy": "unknown",
        }
        print(
            json.dumps(
                {
                    "ok": False,
                    "error": (
                        f"Echec apres auto-reparation ({final_error['strategy']}, exit {final_error['exit_code']}): "
                        f"{final_error['error']}"
                    ),
                }
            )
        )
        sys.exit(1)
    finally:
        stop_monitor.set()


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except Exception as fatal:
        # Catch-all: ensure the parent process ALWAYS gets a parseable JSON line,
        # even if the crash happens before main() sets up its own error handling.
        import traceback
        tb = traceback.format_exc()
        error_detail = f"{type(fatal).__name__}: {str(fatal)[:600]}"
        print(json.dumps({
            "ok": False,
            "error": f"Erreur fatale avant le pipeline video: {error_detail}",
            "traceback": tb[-1200:],
        }), flush=True)
        sys.exit(1)
