"""Wan2.2 TI2V-5B isolation harness — pipeline loaded once, N runs, one manifest.

Objectif : sortir la vraie qualité brute du modèle Wan2.2 TI2V-5B, sans le
juge VLM, sans la synthèse d'ancre, sans la file GPU du bridge, sans le
segmenteur cinema — pour pouvoir varier UN paramètre à la fois et voir
ce qui bouge.

Usage :
    /home/juan/AuroraIA/application/.venv/bin/python \\
        /home/juan/AuroraIA/application/python-services/wan22_isolation_app.py \\
        --campaign baseline
    ... --campaign steps      # varie num_inference_steps
    ... --campaign guidance   # varie guidance_scale
    ... --campaign seed       # varie seed (mesure la variance run-to-run)
    ... --campaign continuity # deux plans, plan 2 ancré sur dernière frame plan 1
    ... --campaign smoke      # rendu minuscule (vérifie le harnais)

Politique de sortie (durs) :
    application/output/video/wan22_isolation/
        manifest.json                              (seule source de vérité)
        <campaign>/<run_id>__<key>=<value>.mp4     (le clip)
        <campaign>/<run_id>__<key>=<value>.json    (le sidecar par run)
        _tmp/                                      (scratch, nettoyé)

Rien ailleurs. Aucun fichier orphelin.
"""

from __future__ import annotations

import argparse
import contextlib
import gc
import io
import json
import math
import os
import shutil
import subprocess
import sys
import time
import traceback
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Optional

# ---------- paths ----------

REPO_ROOT = Path("/home/juan/AuroraIA")
APP_ROOT = REPO_ROOT / "application"
OUT_ROOT = APP_ROOT / "output" / "video" / "wan22_isolation"
MANIFEST_PATH = OUT_ROOT / "manifest.json"
TMP_DIR = OUT_ROOT / "_tmp"

DEFAULT_REFERENCE = APP_ROOT / "output" / "RESULTATS" / "film_2026-07-29_natsu-et-le-velo-rouge" / "references" / "char_1_natsu.png"

WAN_TI2V_5B_MODEL = "Wan-AI/Wan2.2-TI2V-5B-Diffusers"

# ---------- baseline params (proven config from REFONTE_VIDEO_JOURNAL) ----------
#
# Le journal mesuré 60 étapes / 65 frames = 227,1 s en premium sur cette carte.
# Pour rester dans un budget de session raisonnable pendant les sweeps, on
# descend à 33 frames (~1,4 s à 24 fps, 8k+1) et 30 étapes en baseline.
# Le journal indique aussi guidance 4.5 pour Wan 5B, seed reproductible 1031.

BASELINE = dict(
    width=704,
    height=1280,           # 9:16 portrait (proven per WS-V-P/§3.1)
    num_frames=33,         # 8k+1 aligned, ~1.37 s at 24 fps
    fps=24,
    num_inference_steps=30,
    guidance_scale=4.5,
    seed=1031,
    motion_interp=0,       # RAW model output — no ffmpeg post
)

# Baseline prompt : action visible, sujet précis, cohérent avec la référence
# (le boy Natsu). Anglais (grammaire officielle Wan).
BASELINE_PROMPT = (
    "A young boy in a red jacket standing outdoors, "
    "gentle wind lifts strands of his black hair, "
    "he turns his head slowly to the left, natural daylight, "
    "cinematic wide shot, real physics, subtle body movement"
)

# Negative prompt : mirror la baseline durcie du prod (video_generate.py:1717-1748)
# MOINS "motion blur" (cf. journal cause #17 : interdire le flou casse la
# rotation à 24 fps). Cette version est représentative du prod, pas exhaustive.
BASELINE_NEG = (
    "worst quality, low quality, low resolution, pixelation, mosaic artifacts, "
    "compression noise, jpeg artifacts, aliasing, blurry, out of focus, "
    "soft focus, hazy, ghosting, frame ghosting, temporal incoherence, frame jump, "
    "frame jitter, frame freeze, stuttering, warped anatomy, melted face, "
    "morphing body, extra limbs, missing limbs, mutated hands, too many fingers, "
    "distorted proportions, duplicate subjects, cloned face, identity drift, "
    "face changing between frames, teleportation, pose discontinuity, "
    "over-saturated colors, posterization, banding, watermark, text, signature"
)

# ---------- shared state ----------

@dataclass
class RunResult:
    run_id: str
    campaign: str
    swept_key: Optional[str]
    swept_value: Any
    params: dict
    prompt: str
    reference_image: Optional[str]
    output_mp4: str
    output_json: str
    elapsed_seconds: float
    peak_vram_bytes: int
    ffprobe: dict
    metrics: dict
    warnings: list = field(default_factory=list)
    timestamp: float = field(default_factory=time.time)


# ---------- pipeline loading (mirrors video_generate.py:1533-1607) ----------

def warm_cusolver(torch) -> str:
    """Réserve 144 Mio pour cuSOLVER pendant que la VRAM est libre.

    Cause racine mesurée : sans ce warmup, un plan Wan a ~1 chance sur 8 de
    mourir après 350 s sur un solve 3x3 dans UniPC quand la VRAM sature.
    """
    if not torch.cuda.is_available():
        return "no-cuda"
    a = torch.eye(3, device="cuda", dtype=torch.float32)
    b = torch.ones(3, 1, device="cuda", dtype=torch.float32)
    torch.linalg.solve(a, b)
    torch.cuda.synchronize()
    del a, b
    return "warmed"


def load_wan_ti2v_5b_i2v(torch):
    """Charge la pipeline I2V TI2V-5B.

    On utilise ``enable_model_cpu_offload`` (uniforme sur tous les composants,
    VAE inclus) plutôt que ``apply_group_offloading`` sélectif : pour un
    banc d'isolation on veut la robustesse, pas l'optimisation. Le prod
    utilise group_block avec quelques précautions ; le résultat en sortie
    est le même à qualité identique, seule la vitesse/VRAM diffère
    marginalement.
    """
    from diffusers import (
        AutoencoderKLWan,
        WanImageToVideoPipeline,
        WanTransformer3DModel,
    )
    from transformers import UMT5EncoderModel

    dtype = torch.bfloat16 if torch.cuda.is_bf16_supported() else torch.float16
    model_id = WAN_TI2V_5B_MODEL

    # VAE en float32 (précision colorimétrique).
    vae = AutoencoderKLWan.from_pretrained(
        model_id, subfolder="vae", torch_dtype=torch.float32, low_cpu_mem_usage=True,
    )
    text_encoder = UMT5EncoderModel.from_pretrained(
        model_id, subfolder="text_encoder", torch_dtype=dtype, low_cpu_mem_usage=True,
    )
    transformer = WanTransformer3DModel.from_pretrained(
        model_id, subfolder="transformer", torch_dtype=dtype, low_cpu_mem_usage=True,
    )

    pipe = WanImageToVideoPipeline.from_pretrained(
        model_id,
        vae=vae,
        transformer=transformer,
        text_encoder=text_encoder,
        torch_dtype=dtype,
    )
    # model_cpu_offload hook: chaque composant est monté sur CUDA au moment
    # du forward, redescendu ensuite → pic VRAM ≈ le plus gros module + input.
    pipe.enable_model_cpu_offload()

    if hasattr(pipe, "vae") and hasattr(pipe.vae, "enable_tiling"):
        pipe.vae.enable_tiling()
    if hasattr(pipe, "vae") and hasattr(pipe.vae, "enable_slicing"):
        pipe.vae.enable_slicing()
    return pipe


# ---------- run a single generation ----------

def align_dim(v: int, mod: int = 32) -> int:
    return max(mod, round(v / mod) * mod)


def prepare_reference_image(ref_path: Path, width: int, height: int):
    from PIL import Image as PILImage
    img = PILImage.open(str(ref_path)).convert("RGB")
    # Wan I2V pipeline expects PIL Image sized exactly to (width, height)
    return img.resize((width, height))


def run_one_generation(pipe, torch, params: dict, prompt: str, neg: str,
                        reference_image_path: Path,
                        out_mp4: Path,
                        last_frame_dump: Optional[Path] = None) -> tuple[float, int, dict, list]:
    """Retourne (elapsed_seconds, peak_vram_bytes, ffprobe_dict, warnings)."""
    from diffusers.utils import export_to_video

    warnings: list = []

    w = align_dim(int(params["width"]))
    h = align_dim(int(params["height"]))
    n_frames = int(params["num_frames"])
    # Force 8k+1 aligned frame count (Wan segment constraint)
    n_frames = max(25, math.ceil((n_frames - 1) / 8) * 8 + 1)

    call_kwargs = dict(
        image=prepare_reference_image(reference_image_path, w, h),
        prompt=prompt,
        negative_prompt=neg,
        width=w,
        height=h,
        num_frames=n_frames,
        num_inference_steps=int(params["num_inference_steps"]),
        guidance_scale=float(params["guidance_scale"]),
    )

    seed_val = params.get("seed")
    if seed_val is not None:
        device = "cuda" if torch.cuda.is_available() else "cpu"
        gen = torch.Generator(device=device).manual_seed(int(seed_val))
        call_kwargs["generator"] = gen

    # guidance_rescale support (pipeline-version dependent)
    import inspect
    sig = inspect.signature(pipe.__call__)
    if "guidance_rescale" in sig.parameters:
        call_kwargs["guidance_rescale"] = 0.7

    if torch.cuda.is_available():
        torch.cuda.reset_peak_memory_stats()
        torch.cuda.empty_cache()

    t0 = time.time()
    output = pipe(**call_kwargs)
    if torch.cuda.is_available():
        torch.cuda.synchronize()
    elapsed = time.time() - t0

    peak_vram = int(torch.cuda.max_memory_allocated()) if torch.cuda.is_available() else 0

    video = output.frames[0]

    # Sauvegarde MP4 en 24 fps natif TI2V-5B (JAMAIS d'interp — brut modèle)
    out_mp4.parent.mkdir(parents=True, exist_ok=True)
    export_to_video(video, str(out_mp4), fps=int(params.get("fps", 24)))

    # Dump la dernière frame si demandé (pour ancrage du prochain plan)
    if last_frame_dump is not None:
        try:
            last = video[-1]
            _save_frame_pil(last, last_frame_dump)
        except Exception as e:
            warnings.append({"code": "last_frame_dump_failed", "detail": str(e)})

    ffprobe_result = ffprobe_facts(out_mp4)

    # Nettoyage post-génération : output/video (liste de PIL tensors) et
    # call_kwargs retiennent des tenseurs CUDA sans ça — cause mesurée
    # d'OOM sur le 8e run consécutif dans le même process.
    try:
        del output, video, call_kwargs
    except Exception:
        pass
    gc.collect()
    if torch.cuda.is_available():
        torch.cuda.empty_cache()
        try:
            torch.cuda.ipc_collect()
        except Exception:
            pass

    return elapsed, peak_vram, ffprobe_result, warnings


def _save_frame_pil(frame, out_path: Path):
    """Sauve une frame quelconque (PIL / numpy / tensor) en PNG."""
    from PIL import Image as PILImage
    import numpy as np
    try:
        if hasattr(frame, "save"):  # PIL Image
            frame.save(str(out_path))
            return
        arr = np.asarray(frame)
        if arr.dtype != np.uint8:
            if arr.max() <= 1.001:
                arr = (arr * 255.0).clip(0, 255).astype(np.uint8)
            else:
                arr = arr.clip(0, 255).astype(np.uint8)
        PILImage.fromarray(arr).save(str(out_path))
    except Exception as e:
        raise RuntimeError(f"cannot save frame: {e}")


# ---------- objective measurements ----------

def ffprobe_facts(mp4: Path) -> dict:
    """Vérité technique lue par ffprobe. Aucun bluff sur la résolution/fps."""
    if not mp4.exists():
        return {"error": "file_missing"}
    try:
        proc = subprocess.run(
            [
                "ffprobe", "-v", "error", "-select_streams", "v:0",
                "-show_entries", "stream=width,height,r_frame_rate,nb_frames,codec_name,duration,bit_rate",
                "-of", "json", str(mp4),
            ],
            capture_output=True, text=True, timeout=30,
        )
        if proc.returncode != 0:
            return {"error": proc.stderr[:200]}
        data = json.loads(proc.stdout)
        s = (data.get("streams") or [{}])[0]
        rfr = s.get("r_frame_rate", "24/1")
        try:
            num, den = rfr.split("/")
            fps = float(num) / max(1.0, float(den))
        except Exception:
            fps = None
        return dict(
            width=s.get("width"),
            height=s.get("height"),
            fps=fps,
            nb_frames=int(s.get("nb_frames")) if s.get("nb_frames") not in (None, "N/A") else None,
            codec=s.get("codec_name"),
            duration=float(s.get("duration")) if s.get("duration") else None,
            bit_rate=int(s.get("bit_rate")) if s.get("bit_rate") else None,
            file_size=mp4.stat().st_size,
        )
    except Exception as e:
        return {"error": str(e)[:200]}


def measure_middle_frame_sharpness(mp4: Path) -> Optional[float]:
    """Variance du Laplacien sur la frame centrale — plus haut = plus net."""
    try:
        import cv2  # opencv-python présent dans .venv
        import numpy as np
    except Exception:
        return None
    if not mp4.exists():
        return None
    cap = cv2.VideoCapture(str(mp4))
    try:
        n = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
        if n <= 0:
            return None
        cap.set(cv2.CAP_PROP_POS_FRAMES, n // 2)
        ok, frame = cap.read()
        if not ok:
            return None
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        return float(cv2.Laplacian(gray, cv2.CV_64F).var())
    finally:
        cap.release()


def measure_motion_amplitude(mp4: Path) -> Optional[float]:
    """Amplitude moyenne inter-frames — mesure grossière du mouvement.

    Retourne la moyenne de |frame[k] - frame[k-1]| en niveaux de gris [0..1],
    échantillonnée sur ~16 frames. Un plan figé = ~0.003 ; un plan avec
    mouvement clair = >0.02.
    """
    try:
        import cv2
        import numpy as np
    except Exception:
        return None
    if not mp4.exists():
        return None
    cap = cv2.VideoCapture(str(mp4))
    try:
        n = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
        if n < 2:
            return None
        indices = [int(round(i * (n - 1) / 15.0)) for i in range(16)]
        prev = None
        diffs = []
        for idx in indices:
            cap.set(cv2.CAP_PROP_POS_FRAMES, idx)
            ok, frame = cap.read()
            if not ok:
                continue
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY).astype("float32") / 255.0
            if prev is not None:
                diffs.append(float(abs(gray - prev).mean()))
            prev = gray
        if not diffs:
            return None
        return sum(diffs) / len(diffs)
    finally:
        cap.release()


def measure_shot_seam_delta(prev_mp4: Path, next_mp4: Path) -> Optional[float]:
    """Écart moyen |lastFrame(prev) - firstFrame(next)| ∈ [0..1].

    C'est la MESURE de continuité inter-plans : proche de 0 = raccord invisible,
    haut = saut brutal. Sert à quantifier le gain d'un ancrage I2V.
    """
    try:
        import cv2
        import numpy as np
    except Exception:
        return None
    if not prev_mp4.exists() or not next_mp4.exists():
        return None
    cap1 = cv2.VideoCapture(str(prev_mp4))
    cap2 = cv2.VideoCapture(str(next_mp4))
    try:
        n1 = int(cap1.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
        n2 = int(cap2.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
        if n1 == 0 or n2 == 0:
            return None
        cap1.set(cv2.CAP_PROP_POS_FRAMES, n1 - 1)
        ok1, f1 = cap1.read()
        cap2.set(cv2.CAP_PROP_POS_FRAMES, 0)
        ok2, f2 = cap2.read()
        if not ok1 or not ok2:
            return None
        if f1.shape != f2.shape:
            import cv2
            f2 = cv2.resize(f2, (f1.shape[1], f1.shape[0]))
        a = f1.astype("float32") / 255.0
        b = f2.astype("float32") / 255.0
        return float(abs(a - b).mean())
    finally:
        cap1.release()
        cap2.release()


# ---------- manifest management ----------

def load_manifest() -> list:
    if not MANIFEST_PATH.exists():
        return []
    try:
        return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    except Exception:
        return []


def append_manifest(entry: dict) -> None:
    OUT_ROOT.mkdir(parents=True, exist_ok=True)
    current = load_manifest()
    current.append(entry)
    MANIFEST_PATH.write_text(json.dumps(current, indent=2, default=str), encoding="utf-8")


# ---------- campaign execution ----------

def build_run_id(prefix: str) -> str:
    return f"{prefix}_{int(time.time())}_{os.getpid()%10000:04d}"


def relpath_str(p: Path) -> str:
    try:
        return str(p.relative_to(APP_ROOT))
    except Exception:
        return str(p)


def make_run(
    pipe, torch,
    campaign: str,
    swept_key: Optional[str],
    swept_value: Any,
    params: dict,
    prompt: str,
    reference_image: Path,
    prev_shot_mp4: Optional[Path] = None,
) -> RunResult:

    run_id = build_run_id(f"{campaign}_{swept_key}={swept_value}" if swept_key else campaign)
    campaign_dir = OUT_ROOT / campaign
    campaign_dir.mkdir(parents=True, exist_ok=True)

    safe_key = (swept_key or "run")
    safe_val = str(swept_value).replace("/", "-").replace(" ", "_")
    fname_core = f"{run_id}__{safe_key}={safe_val}"
    out_mp4 = campaign_dir / f"{fname_core}.mp4"
    out_json = campaign_dir / f"{fname_core}.json"
    last_frame_dump = TMP_DIR / f"{fname_core}__lastframe.png"
    TMP_DIR.mkdir(parents=True, exist_ok=True)

    print(f"[campaign={campaign} sweep {swept_key}={swept_value}] START", flush=True)
    print(f"  params: {json.dumps(params, sort_keys=True)}", flush=True)
    print(f"  ref: {reference_image}", flush=True)
    print(f"  out: {out_mp4}", flush=True)

    # Defense in depth : nettoyage AVANT et APRÈS chaque run.
    # Cause racine mesurée : sur 7 runs consécutifs dans le même process,
    # PyTorch accumule ~12,4 GiB alloués + fragmentation → 8e run OOM sur une
    # allocation de 1,96 GiB alors qu'il "reste" ~2 GiB (mais fragmentés).
    gc.collect()
    if torch.cuda.is_available():
        torch.cuda.empty_cache()
        try:
            torch.cuda.ipc_collect()
        except Exception:
            pass

    elapsed, peak_vram, ffp, warnings = run_one_generation(
        pipe, torch,
        params=params,
        prompt=prompt,
        neg=BASELINE_NEG,
        reference_image_path=reference_image,
        out_mp4=out_mp4,
        last_frame_dump=last_frame_dump,
    )

    metrics = dict(
        middle_frame_laplacian_var=measure_middle_frame_sharpness(out_mp4),
        motion_amplitude=measure_motion_amplitude(out_mp4),
    )
    if prev_shot_mp4 is not None:
        metrics["shot_seam_delta"] = measure_shot_seam_delta(prev_shot_mp4, out_mp4)
        metrics["chain_from_shot"] = relpath_str(prev_shot_mp4)

    result = RunResult(
        run_id=run_id,
        campaign=campaign,
        swept_key=swept_key,
        swept_value=swept_value,
        params=params,
        prompt=prompt,
        reference_image=relpath_str(reference_image),
        output_mp4=relpath_str(out_mp4),
        output_json=relpath_str(out_json),
        elapsed_seconds=round(elapsed, 2),
        peak_vram_bytes=peak_vram,
        ffprobe=ffp,
        metrics=metrics,
        warnings=warnings,
    )

    payload = asdict(result)
    payload["last_frame_dump"] = relpath_str(last_frame_dump) if last_frame_dump.exists() else None
    out_json.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    append_manifest(payload)

    def _fmt(x):
        return "N/A" if x is None else f"{x:.4f}" if isinstance(x, float) else str(x)
    print(f"[campaign={campaign} sweep {swept_key}={swept_value}] DONE"
          f" — {elapsed:.1f}s"
          f" peak_vram={peak_vram/1024**3:.2f}GB"
          f" laplacian={_fmt(metrics['middle_frame_laplacian_var'])}"
          f" amp={_fmt(metrics['motion_amplitude'])}",
          flush=True)
    return result


def campaign_smoke(pipe, torch, ref_image: Path):
    params = dict(BASELINE)
    params["width"] = 320
    params["height"] = 576
    params["num_frames"] = 25
    params["num_inference_steps"] = 8
    make_run(pipe, torch, "smoke", None, "smoke", params,
             BASELINE_PROMPT, ref_image)


def campaign_baseline(pipe, torch, ref_image: Path):
    make_run(pipe, torch, "baseline", None, "baseline",
             dict(BASELINE), BASELINE_PROMPT, ref_image)


def campaign_steps(pipe, torch, ref_image: Path):
    # 30 est le baseline (déjà couvert). Balayage : 20, 40, 60.
    for steps in (20, 40, 60):
        p = dict(BASELINE, num_inference_steps=steps)
        make_run(pipe, torch, "steps", "steps", steps, p, BASELINE_PROMPT, ref_image)


def campaign_guidance(pipe, torch, ref_image: Path):
    # 4.5 est le baseline. Balayage : 3.0, 6.0 (Wan A14B recommandé 3-4 I2V / 3.5-4 T2V ;
    # au-dessus de 5.5 dérive documentée).
    for g in (3.0, 6.0):
        p = dict(BASELINE, guidance_scale=g)
        make_run(pipe, torch, "guidance", "guidance", g, p, BASELINE_PROMPT, ref_image)


def campaign_seed(pipe, torch, ref_image: Path):
    # 1031 est le baseline. Balayage : 42, 7777 pour caractériser la variance.
    for s in (42, 7777):
        p = dict(BASELINE, seed=s)
        make_run(pipe, torch, "seed", "seed", s, p, BASELINE_PROMPT, ref_image)


def _find_reusable_baseline():
    """Cherche un run baseline déjà présent dans le manifest, avec sa lastframe.

    Évite de refaire le plan A quand un run baseline identique (même seed, même
    prompt, mêmes paramètres) existe déjà — la continuité repart sur exactement
    le même point de départ.
    """
    entries = load_manifest()
    for e in entries:
        if e.get("campaign") != "baseline":
            continue
        p = e.get("params") or {}
        if (p.get("width") != BASELINE["width"]
                or p.get("height") != BASELINE["height"]
                or p.get("num_frames") != BASELINE["num_frames"]
                or int(p.get("seed") or 0) != int(BASELINE["seed"])
                or float(p.get("guidance_scale") or 0) != float(BASELINE["guidance_scale"])
                or int(p.get("num_inference_steps") or 0) != int(BASELINE["num_inference_steps"])):
            continue
        mp4 = APP_ROOT / e["output_mp4"]
        lf = APP_ROOT / e["last_frame_dump"] if e.get("last_frame_dump") else None
        if mp4.exists() and lf and lf.exists():
            return e, mp4, lf
    return None, None, None


def campaign_continuity(pipe, torch, ref_image: Path):
    """Test central : plan 2 ancré sur last-frame plan 1 vs plan 2 non-ancré.

    Si un plan A baseline existe déjà (même seed/params), on le REUTILISE au lieu
    de le regénérer : le point de départ des deux comparaisons doit être
    strictement identique.
    """
    reused_entry, plan_a_mp4, plan_a_lastframe = _find_reusable_baseline()
    if reused_entry is not None:
        print(f"[continuity] plan A réutilisé du manifest : {reused_entry.get('run_id')}", flush=True)
    else:
        print("[continuity] pas de baseline réutilisable trouvée — génération d'un plan A dédié", flush=True)
        a = make_run(pipe, torch, "continuity", "chain", "A_seed=1031",
                     dict(BASELINE), BASELINE_PROMPT, ref_image)
        plan_a_mp4 = APP_ROOT / a.output_mp4
        candidate_lf = TMP_DIR / f"{a.run_id}__{a.swept_key}={a.swept_value}__lastframe.png"
        if candidate_lf.exists():
            plan_a_lastframe = candidate_lf
        else:
            plan_a_lastframe = TMP_DIR / f"{a.run_id}_fallback_lastframe.png"
            try:
                subprocess.run(
                    ["ffmpeg", "-y", "-v", "error", "-sseof", "-0.1",
                     "-i", str(plan_a_mp4),
                     "-vsync", "vfr", "-q:v", "2", "-frames:v", "1", str(plan_a_lastframe)],
                    check=True, timeout=30,
                )
            except Exception as e:
                print(f"  [continuity] extraction lastframe impossible: {e}", flush=True)
                return

    prompt_b = (
        "The same young boy in the red jacket continues moving, "
        "he takes one slow step forward, wind still ruffles his hair, "
        "same natural daylight, same cinematic wide shot, real physics"
    )
    b = make_run(pipe, torch, "continuity", "chain", "B_anchored_on_A_lastframe",
                 dict(BASELINE), prompt_b, plan_a_lastframe,
                 prev_shot_mp4=plan_a_mp4)

    b_prime = make_run(pipe, torch, "continuity", "chain", "B_prime_unanchored",
                       dict(BASELINE), prompt_b, ref_image,
                       prev_shot_mp4=plan_a_mp4)

    def _fmt(x):
        return "N/A" if x is None else f"{x:.4f}" if isinstance(x, float) else str(x)
    print("[continuity] verdict:", flush=True)
    print(f"  plan A source : {plan_a_mp4}", flush=True)
    print(f"  seam A→B  (anchored on A lastframe) : {_fmt(b.metrics.get('shot_seam_delta'))}", flush=True)
    print(f"  seam A→B' (unanchored, ref d'origine) : {_fmt(b_prime.metrics.get('shot_seam_delta'))}", flush=True)


def campaign_prod_continuity(pipe, torch, ref_image: Path):
    """Validation à l'échelle de PRODUCTION du correctif sharp_end.

    Le banc initial était à 33 frames (courtes, ~1,4 s). La demande utilisateur
    est haute qualité ET pleine durée. Ici on refait le protocole ancré vs
    non-ancré mais à la RESOLUTION NATIVE JOURNAL (832×480 landscape, 65 frames,
    24 fps, 60 étapes) — la config exacte qui a produit la baseline validée du
    2026-07-26. On mesure que le rapport 6× tient à cette échelle.
    """
    prod_params = dict(
        width=832,
        height=480,
        num_frames=65,
        fps=24,
        num_inference_steps=60,      # premium étapes journal
        guidance_scale=4.5,
        seed=1031,
        motion_interp=0,
    )
    # Plan A : rendu direct, ne réutilise PAS un baseline (résolution différente).
    a = make_run(pipe, torch, "prod_continuity", "chain", "A_prod_832x480_65f_60steps",
                 prod_params, BASELINE_PROMPT, ref_image)

    # Extraction de la SHARP TAIL frame de A via le mécanisme prod (celui qu'on
    # vient de patcher). Cela ferme la boucle : la validation utilise le
    # même chemin que le prod.
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "_cinema_pipeline",
        str(APP_ROOT / "python-services" / "cinema" / "cinema_pipeline.py"))
    _cp = importlib.util.module_from_spec(spec)
    try:
        sys.path.insert(0, str(APP_ROOT / "python-services" / "cinema"))
        spec.loader.exec_module(_cp)
    except Exception as e:
        print(f"[prod_continuity] impossible de charger cinema_pipeline: {e}", flush=True)
        return
    triplet_dir = TMP_DIR / f"{a.run_id}_triplet"
    triplet_dir.mkdir(parents=True, exist_ok=True)
    triplet = _cp.extract_keyframes_triplet(str(APP_ROOT / a.output_mp4), triplet_dir, 1)
    sharp_end = triplet.get("sharp_end")
    naive_end = triplet.get("end")
    if not sharp_end or not Path(sharp_end).exists():
        print(f"[prod_continuity] sharp_end absent, fallback échoué", flush=True)
        return
    lv_sharp = _cp._laplacian_variance(sharp_end)
    lv_naive = _cp._laplacian_variance(naive_end) if naive_end else None
    print(f"[prod_continuity] sharp_end laplacian={lv_sharp:.1f}, end laplacian={lv_naive}", flush=True)

    prompt_b = (
        "The same young boy in the red jacket continues moving, "
        "he takes one slow step forward, wind still ruffles his hair, "
        "same natural daylight, same cinematic wide shot, real physics"
    )
    # B ancré sur sharp_end (chemin prod post-patch)
    b_sharp = make_run(pipe, torch, "prod_continuity", "chain", "B_prod_anchored_sharp_end",
                       prod_params, prompt_b, Path(sharp_end),
                       prev_shot_mp4=APP_ROOT / a.output_mp4)
    # B_naive ancré sur end (chemin prod PRE-patch, comparaison directe)
    b_naive = make_run(pipe, torch, "prod_continuity", "chain", "B_prod_anchored_naive_end",
                       prod_params, prompt_b, Path(naive_end),
                       prev_shot_mp4=APP_ROOT / a.output_mp4)
    # B_ref ancré sur la ref FLUX d'origine (chemin "sans ancre inter-plans")
    b_ref = make_run(pipe, torch, "prod_continuity", "chain", "B_prod_unanchored_ref",
                     prod_params, prompt_b, ref_image,
                     prev_shot_mp4=APP_ROOT / a.output_mp4)

    def _fmt(x):
        return "N/A" if x is None else f"{x:.5f}" if isinstance(x, float) else str(x)
    print("\n[prod_continuity] VERDICT À L'ÉCHELLE PRODUCTION (832×480×65f×60steps):", flush=True)
    print(f"  seam A→B (ancré sharp_end)    : {_fmt(b_sharp.metrics.get('shot_seam_delta'))}", flush=True)
    print(f"  seam A→B (ancré end naïf)     : {_fmt(b_naive.metrics.get('shot_seam_delta'))}", flush=True)
    print(f"  seam A→B (ancré ref d'origine): {_fmt(b_ref.metrics.get('shot_seam_delta'))}", flush=True)


def _find_reusable_prod_A():
    """Cherche un plan A prod_continuity déjà rendu avec sa lastframe tenseur."""
    entries = load_manifest()
    for e in entries:
        if e.get("campaign") != "prod_continuity":
            continue
        if "A_prod" not in str(e.get("swept_value") or ""):
            continue
        mp4 = APP_ROOT / e["output_mp4"]
        lf = APP_ROOT / e["last_frame_dump"] if e.get("last_frame_dump") else None
        if mp4.exists() and lf and lf.exists():
            return e, mp4, lf
    return None, None, None


def campaign_prod_continuity_tensor(pipe, torch, ref_image: Path):
    """4ème arme : plan B ancré sur `video[-1]` du plan A (tenseur vrai).

    Complète le comparatif prod_continuity qui a mesuré sharp_end vs naive_end
    vs unanchored. Réutilise A existant si trouvé dans le manifest pour ne
    payer qu'UN seul rendu de B (le plan A est identique à celui déjà mesuré,
    donc le rejeu de A serait du gâchis GPU).
    """
    reused, plan_a_mp4, plan_a_tensor_lf = _find_reusable_prod_A()
    if reused is None:
        print("[prod_continuity_tensor] aucun plan A prod réutilisable — annulé", flush=True)
        print("  lance d'abord --campaign prod_continuity", flush=True)
        return
    print(f"[prod_continuity_tensor] plan A réutilisé : {reused.get('run_id')}", flush=True)
    print(f"  tensor lastframe : {plan_a_tensor_lf}", flush=True)

    prod_params = dict(
        width=832,
        height=480,
        num_frames=65,
        fps=24,
        num_inference_steps=60,
        guidance_scale=4.5,
        seed=1031,
        motion_interp=0,
    )
    prompt_b = (
        "The same young boy in the red jacket continues moving, "
        "he takes one slow step forward, wind still ruffles his hair, "
        "same natural daylight, same cinematic wide shot, real physics"
    )
    b = make_run(pipe, torch, "prod_continuity_tensor", "chain",
                 "B_prod_anchored_tensor_lastframe",
                 prod_params, prompt_b, plan_a_tensor_lf,
                 prev_shot_mp4=plan_a_mp4)

    def _fmt(x):
        return "N/A" if x is None else f"{x:.5f}" if isinstance(x, float) else str(x)
    print("\n[prod_continuity_tensor] MESURE 4ᵉ ARME (à comparer aux 3 précédentes) :", flush=True)
    print(f"  seam A→B (ancré tensor video[-1]) : {_fmt(b.metrics.get('shot_seam_delta'))}", flush=True)
    print("  Rappel prod_continuity (mêmes params, même plan A) :", flush=True)
    print("    sharp_end     = 0.02732", flush=True)
    print("    end naïf      = 0.01777  ← meilleur des 3 précédents", flush=True)
    print("    ref d'origine = 0.02781", flush=True)


CAMPAIGNS = {
    "smoke": campaign_smoke,
    "baseline": campaign_baseline,
    "steps": campaign_steps,
    "guidance": campaign_guidance,
    "seed": campaign_seed,
    "continuity": campaign_continuity,
    "prod_continuity": campaign_prod_continuity,
    "prod_continuity_tensor": campaign_prod_continuity_tensor,
}


def main():
    # Corrige la fragmentation VRAM mesurée sur 7 runs consécutifs (OOM sur le 8e).
    # expandable_segments coalesce les blocs libres au lieu de bloquer sur la
    # fragmentation.
    os.environ.setdefault("PYTORCH_CUDA_ALLOC_CONF", "expandable_segments:True")

    parser = argparse.ArgumentParser()
    parser.add_argument("--campaign", required=True, choices=sorted(CAMPAIGNS.keys()) + ["all"])
    parser.add_argument("--reference", default=str(DEFAULT_REFERENCE),
                        help="Chemin vers l'image de référence pour I2V")
    args = parser.parse_args()

    ref = Path(args.reference)
    if not ref.exists():
        print(f"FATAL: reference image not found: {ref}", flush=True)
        sys.exit(2)

    OUT_ROOT.mkdir(parents=True, exist_ok=True)

    print("=" * 70, flush=True)
    print(f"Wan2.2 TI2V-5B isolation harness — campaign={args.campaign}", flush=True)
    print(f"model: {WAN_TI2V_5B_MODEL}", flush=True)
    print(f"reference image: {ref}", flush=True)
    print(f"output root: {OUT_ROOT}", flush=True)
    print("=" * 70, flush=True)

    print("[boot] importing torch...", flush=True)
    import torch
    if not torch.cuda.is_available():
        print("FATAL: CUDA unavailable — Wan2.2 requires an NVIDIA GPU.", flush=True)
        sys.exit(3)

    print(f"[boot] CUDA {torch.version.cuda}, GPU: {torch.cuda.get_device_name(0)}", flush=True)

    t_boot = time.time()
    print("[boot] cusolver warm-up...", flush=True)
    warm_cusolver(torch)

    print("[boot] loading Wan pipeline (this takes ~30-60s)...", flush=True)
    pipe = load_wan_ti2v_5b_i2v(torch)
    t_load = time.time() - t_boot
    print(f"[boot] pipeline loaded in {t_load:.1f}s.", flush=True)

    if args.campaign == "all":
        # Ordre : baseline → sweeps rapides → continuité
        for name in ("baseline", "steps", "guidance", "seed", "continuity"):
            try:
                print("\n" + "-" * 70)
                print(f"CAMPAIGN {name}")
                print("-" * 70, flush=True)
                CAMPAIGNS[name](pipe, torch, ref)
            except Exception as e:
                print(f"  campaign {name} FAILED: {e}", flush=True)
                traceback.print_exc()
    else:
        CAMPAIGNS[args.campaign](pipe, torch, ref)

    print("\n" + "=" * 70)
    print(f"DONE. Manifest: {MANIFEST_PATH}")
    print("=" * 70, flush=True)


if __name__ == "__main__":
    main()
