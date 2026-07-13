"""mocap_pipeline — end-to-end MoMask text-to-motion + retarget_bvh + polish.

The chain:
  1. Text prompt -> MoMask generates N BVH candidates (see momask_generate).
  2. Score each candidate on gait geometry (see motion_score); pick the best.
  3. Blender: import the target mesh GLB, generate a Rigify rig OR use the
     rig already present, then run the mocap bake (BVH retarget + neck limit +
     foot ground clamp + per-frame foot lock + finger curl + arm-swing boost).
  4. Export animated GLB.

Two entry points:
  * ``run_end_to_end(input_glb, output_glb, prompt, ...)`` — full pipeline,
    delegates to ``rigify_autorig --mocap-bvh`` so the same Rigify rigging
    code applies (weld, auto-weights, proxy transfer, etc.), then the BVH is
    baked instead of the procedural motion_baker.
  * ``run_bake_only(input_rigged_glb, output_glb, bvh, ...)`` — assumes the
    input already has a Rigify armature. Faster: it re-imports the GLB into
    Blender, finds the armature, and runs mocap_bake_bpy.run_mocap_bake.

Public constants:
  * ``DEFAULT_PROMPTS`` — a set of well-tested prompts curating known-good
    MoMask outputs (a person walks forward, confidently, with arms swinging).
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
from typing import Any, Dict, List, Optional

HERE = Path(__file__).resolve().parent

sys.path.insert(0, str(HERE))
import motion_score  # noqa: E402
import momask_generate  # noqa: E402


# Prompts biased for the SOTA pro-walk look Juan asked for: erect posture,
# forward stride, ARMS SWINGING WIDE. All feed HumanML3D vocabulary — MoMask
# was trained on natural English descriptions of everyday motions.
DEFAULT_PROMPTS: List[str] = [
    "a person walks forward naturally with a confident stride and arms swinging",
    "a person walks forward briskly, arms swinging in a wide natural arc",
    "a person strides forward at a steady pace, shoulders relaxed, arms swinging",
    "a person walks forward with a purposeful gait and pronounced arm swing",
]


def _write_json(path: Path, data: Dict[str, Any]) -> None:
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def curate_best_bvh(
    prompts: List[str],
    repeats_per_prompt: int = 4,
    ext_prefix: str = "aurora_mocap",
    gpu_id: int = 0,
) -> Dict[str, Any]:
    """Generate motion for each prompt, score, return the best BVH.

    Result::

      {
        "ok": True,
        "best": {"bvh_ik": "...", "composite": 0.93, "metrics": {...},
                 "prompt": "..."},
        "all": [ ... all scored candidates ...],
      }
    """
    all_scored: List[Dict[str, Any]] = []
    for i, prompt in enumerate(prompts):
        ext = f"{ext_prefix}_p{i}"
        r = momask_generate.generate_motions(
            prompt,
            ext=ext,
            repeat_times=repeats_per_prompt,
            gpu_id=gpu_id,
            timeout_s=300,
        )
        if not r.get("ok"):
            print(
                f"[mocap_pipeline] MoMask failed for prompt '{prompt}': "
                f"{r.get('error')}",
                file=sys.stderr,
            )
            continue
        scored = motion_score.score_candidates(r["candidates"])
        for s in scored:
            s["prompt"] = prompt
            all_scored.append(s)
    if not all_scored:
        return {"ok": False, "error": "no valid candidates from any prompt"}
    all_scored.sort(key=lambda r: r.get("composite", -1.0), reverse=True)
    return {"ok": True, "best": all_scored[0], "all": all_scored[:12]}


def run_end_to_end(
    input_glb: str,
    output_glb: str,
    prompt: str = "",
    prompts: Optional[List[str]] = None,
    repeats_per_prompt: int = 4,
    gpu_id: int = 0,
    metarig_kind: str = "human",
    bvh_dst_dir: Optional[str] = None,
) -> Dict[str, Any]:
    """Full chain: mesh GLB in -> animated rigged GLB out.

    * generates + curates BVH
    * copies the winning BVH to ``bvh_dst_dir`` so we keep a stable
      reference alongside the output
    * calls ``rigify_autorig.py --mocap-bvh <bvh>`` to rig + bake in Blender
    """
    if prompts is None:
        prompts = [prompt] if prompt else DEFAULT_PROMPTS[:]

    input_glb = os.path.abspath(input_glb)
    output_glb = os.path.abspath(output_glb)
    if not os.path.isfile(input_glb):
        return {"ok": False, "error": f"input GLB missing: {input_glb}"}
    os.makedirs(os.path.dirname(output_glb), exist_ok=True)

    print("[mocap_pipeline] curating MoMask candidates...", flush=True)
    curated = curate_best_bvh(prompts, repeats_per_prompt=repeats_per_prompt, gpu_id=gpu_id)
    if not curated.get("ok"):
        return {"ok": False, "step": "curate", **curated}
    best = curated["best"]
    best_bvh = best["bvh_ik"]
    print(
        f"[mocap_pipeline] best BVH: {best_bvh}\n"
        f"  composite={best['composite']:.3f} metrics={best['metrics']}\n"
        f"  prompt='{best['prompt']}'",
        flush=True,
    )

    # persist the winner
    if bvh_dst_dir:
        os.makedirs(bvh_dst_dir, exist_ok=True)
        dst_bvh = os.path.join(bvh_dst_dir, "mocap_winner.bvh")
        shutil.copy2(best_bvh, dst_bvh)
        _write_json(Path(bvh_dst_dir) / "mocap_score.json", curated)
        best_bvh = dst_bvh

    rigify = HERE / "rigify_autorig.py"
    cmd = [
        sys.executable,
        str(rigify),
        "--input",
        input_glb,
        "--output",
        output_glb,
        "--metarig",
        metarig_kind,
        "--mocap-bvh",
        best_bvh,
    ]
    print("[mocap_pipeline] running:", " ".join(cmd), flush=True)
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=900)
    if proc.returncode != 0:
        return {
            "ok": False,
            "step": "rigify_bake",
            "error": f"rigify_autorig exit={proc.returncode}",
            "stdout": (proc.stdout or "")[-3000:],
            "stderr": (proc.stderr or "")[-3000:],
        }
    return {
        "ok": True,
        "path": output_glb,
        "size_bytes": os.path.getsize(output_glb) if os.path.isfile(output_glb) else 0,
        "bvh": best_bvh,
        "score": {"composite": best["composite"], "metrics": best["metrics"], "prompt": best["prompt"]},
        "candidates_count": len(curated["all"]),
    }


def _cli() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True, help="input mesh GLB (unrigged)")
    ap.add_argument("--output", required=True, help="output rigged+animated GLB")
    ap.add_argument("--prompt", default="", help="single text prompt for MoMask")
    ap.add_argument(
        "--use-prompt-set",
        action="store_true",
        help="use the DEFAULT_PROMPTS curated set instead of --prompt",
    )
    ap.add_argument("--repeats", type=int, default=4)
    ap.add_argument("--gpu-id", type=int, default=0)
    ap.add_argument("--metarig", default="human")
    ap.add_argument("--bvh-dst-dir", default="", help="where to persist the winning BVH + score.json")
    args = ap.parse_args()

    prompts = DEFAULT_PROMPTS if args.use_prompt_set else ([args.prompt] if args.prompt else DEFAULT_PROMPTS)
    r = run_end_to_end(
        args.input,
        args.output,
        prompt=args.prompt,
        prompts=prompts,
        repeats_per_prompt=args.repeats,
        gpu_id=args.gpu_id,
        metarig_kind=args.metarig,
        bvh_dst_dir=args.bvh_dst_dir or None,
    )
    print(json.dumps(r, indent=2, ensure_ascii=False))
    return 0 if r.get("ok") else 1


if __name__ == "__main__":
    sys.exit(_cli())
