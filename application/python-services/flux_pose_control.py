#!/usr/bin/env python
"""FLUX + Shakker Union ControlNet (OpenPose) reference synth.

Forces a hard A-pose on the generated human so the multi-view turnaround audit
(which otherwise rejects every realistic full-body human — arms fused to torso,
not a true profile) actually passes, giving Hunyuan3D a clean riggable subject.

Reuses the polling/fetch helpers from flux_reference_synth; only the workflow
graph differs (adds ControlNetLoader → SetUnionControlNetType(openpose) →
ControlNetApplyAdvanced driven by a drawn OpenPose skeleton).

Schema: aurora.flux_posed.v1
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path
from random import randint

sys.path.insert(0, str(Path(__file__).resolve().parent))
from flux_reference_synth import (  # noqa: E402
    COMFY_BASE, DEFAULT_CLIP_L, DEFAULT_CLIP_T5, DEFAULT_UNET, DEFAULT_VAE,
    DEFAULT_OUTPUT_DIR, fetch_to, output_path_from_history, poll_history, post_prompt,
)
from openpose_skeleton import write_pose  # noqa: E402

CONTROLNET_NAME = "Shakker_FLUX_Union_Pro_2.safetensors"
# ComfyUI input dir (LoadImage reads from here).
COMFY_INPUT_DIR = Path(__file__).resolve().parents[2] / "modele" / "comfyui" / "comfyui" / "input"

# Per-view orientation text. The OpenPose skeleton fixes the LIMB pose but does
# not encode facing direction (a front and back A-pose skeleton look alike), so
# the text must drive orientation. Without this the back/profile views render
# as another front view.
VIEW_ORIENT = {
    "front": "front view, facing the camera directly, full face visible",
    "back": "back view seen directly from behind, back of the head and the back "
            "of the jacket visible, the face is NOT visible, no facial features",
    "left": "exact left side profile, true 90 degree side view, the subject faces "
            "to the left, only one eye and one ear visible, not a front view",
    "right": "exact right side profile, true 90 degree side view, the subject faces "
             "to the right, only one eye and one ear visible, not a front view",
}


def build_posed_workflow(prompt: str, pose_filename: str, *, width: int = 1024,
                         height: int = 1024, steps: int = 25, seed: int | None = None,
                         guidance: float = 3.5, cn_strength: float = 0.65,
                         cn_end: float = 0.80, filename_prefix: str = "aurora_posed") -> dict:
    if seed is None:
        seed = randint(1, 2**32 - 1)
    return {
        "11": {"class_type": "DualCLIPLoader", "inputs": {
            "clip_name1": DEFAULT_CLIP_T5, "clip_name2": DEFAULT_CLIP_L, "type": "flux"}},
        "12": {"class_type": "UNETLoader", "inputs": {
            "unet_name": DEFAULT_UNET, "weight_dtype": "fp8_e4m3fn"}},
        "10": {"class_type": "VAELoader", "inputs": {"vae_name": DEFAULT_VAE}},
        "6": {"class_type": "CLIPTextEncode", "inputs": {"clip": ["11", 0], "text": prompt}},
        "33": {"class_type": "CLIPTextEncode", "inputs": {"clip": ["11", 0], "text": ""}},
        "26": {"class_type": "FluxGuidance", "inputs": {"conditioning": ["6", 0], "guidance": guidance}},
        "27": {"class_type": "EmptySD3LatentImage", "inputs": {"width": width, "height": height, "batch_size": 1}},
        # ── ControlNet pose branch ──
        "40": {"class_type": "LoadImage", "inputs": {"image": pose_filename}},
        "41": {"class_type": "ControlNetLoader", "inputs": {"control_net_name": CONTROLNET_NAME}},
        "42": {"class_type": "SetUnionControlNetType", "inputs": {"control_net": ["41", 0], "type": "openpose"}},
        "43": {"class_type": "ControlNetApplyAdvanced", "inputs": {
            "positive": ["26", 0], "negative": ["33", 0], "control_net": ["42", 0],
            "image": ["40", 0], "strength": cn_strength,
            "start_percent": 0.0, "end_percent": cn_end, "vae": ["10", 0]}},
        "31": {"class_type": "KSampler", "inputs": {
            "model": ["12", 0], "positive": ["43", 0], "negative": ["43", 1],
            "latent_image": ["27", 0], "seed": seed, "steps": steps, "cfg": 1.0,
            "sampler_name": "euler", "scheduler": "simple", "denoise": 1.0}},
        "8": {"class_type": "VAEDecode", "inputs": {"samples": ["31", 0], "vae": ["10", 0]}},
        "9": {"class_type": "SaveImage", "inputs": {"images": ["8", 0], "filename_prefix": filename_prefix}},
    }


def synth_posed(prompt: str, run_id: str, view: str, *,
                output_dir: Path = DEFAULT_OUTPUT_DIR, width: int = 1024,
                height: int = 1024, steps: int = 25, seed: int | None = None,
                cn_strength: float = 0.65, cn_end: float = 0.80,
                comfy_base: str = COMFY_BASE) -> dict:
    started = time.time()
    # 1. draw + stage the OpenPose skeleton into ComfyUI/input
    pose_name = f"aurora_pose_{run_id}_{view}.png"
    write_pose(view, COMFY_INPUT_DIR / pose_name, size=max(width, height))
    # 1b. append per-view orientation so back/profile don't render as a front view
    orient = VIEW_ORIENT.get(view, "")
    view_prompt = f"{prompt.rstrip(' ,.')}, {orient}" if orient else prompt
    # 2. build + submit
    wf = build_posed_workflow(view_prompt, pose_name, width=width, height=height,
                              steps=steps, seed=seed, cn_strength=cn_strength,
                              cn_end=cn_end, filename_prefix=f"aurora_{run_id}_{view}")
    seed_used = wf["31"]["inputs"]["seed"]
    try:
        pid = post_prompt(wf, comfy_base)
        entry = poll_history(pid, comfy_base=comfy_base)
        url = output_path_from_history(entry, comfy_base)
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": f"{type(exc).__name__}: {exc}", "view": view}
    out_name = f"{run_id}_reference.png" if view == "front" else f"{run_id}_{view}_reference.png"
    out_path = output_dir / out_name
    size = fetch_to(url, out_path)
    return {"ok": True, "view": view, "reference_path": str(out_path),
            "pose_image": str(COMFY_INPUT_DIR / pose_name), "seed": int(seed_used),
            "size_bytes": size, "elapsed_s": round(time.time() - started, 1)}


def main() -> int:
    ap = argparse.ArgumentParser(description="FLUX posed reference synth (ControlNet OpenPose)")
    ap.add_argument("--prompt", required=True)
    ap.add_argument("--run-id", required=True, dest="run_id")
    ap.add_argument("--view", default="front", choices=["front", "back", "left", "right"])
    ap.add_argument("--strength", type=float, default=0.65)
    ap.add_argument("--cn-end", type=float, default=0.80, dest="cn_end")
    ap.add_argument("--seed", type=int, default=None)
    args = ap.parse_args()
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
    except (AttributeError, ValueError):
        pass
    r = synth_posed(args.prompt, args.run_id, args.view, seed=args.seed,
                    cn_strength=args.strength, cn_end=args.cn_end)
    import json
    sys.stdout.write(json.dumps(r, ensure_ascii=True) + "\n")
    return 0 if r.get("ok") else 1


if __name__ == "__main__":
    sys.exit(main())
