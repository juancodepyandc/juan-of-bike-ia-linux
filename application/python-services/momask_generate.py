"""momask_generate — text-to-motion via MoMask (HumanML3D, VQ-VAE + masked transformer).

Wraps the external MoMask installation
(``~/.local/share/auroraia/external/momask-codes``) so the app can request N
BVH walk variants from a text prompt without cluttering the app venv with
torch 2.11+cu128 / CLIP / vector-quantize-pytorch. All heavy work runs inside
the ``momask`` conda env; this file only spawns the subprocess and returns
paths to the produced BVH + joints .npy artifacts.

Pipeline in memory/pipeline-deformation-3d.md.
Design:
  * ``generate_motions(prompt, ext, repeat_times, gpu_id)`` invokes
    ``conda run -n momask python run_gen.py --gpu_id X --ext EXT --repeat_times N --text_prompt "..."``.
  * Result: for each repeat i in [0..N-1], two BVH files
    ``sample0_repeat{i}_len{L}.bvh`` (raw) and ``sample0_repeat{i}_len{L}_ik.bvh``
    (with IK foot correction), plus the T x 22 x 3 joints in
    ``joints/0/sample0_repeat{i}_len{L}_ik.npy``. We always prefer the ``_ik``
    variant — it has the built-in foot-skate correction.
  * Env autodiscovery: honours ``AURORA_MOMASK_HOME``, ``AURORA_MOMASK_CONDA``,
    ``AURORA_MOMASK_ENV`` but falls back to the paths used in this repo.

Public API:
  * ``generate_motions(prompt, ext, repeat_times, gpu_id, timeout_s) -> dict``
  * ``locate_candidates(ext) -> list[dict]`` — enumerate all
    ``{bvh_ik, joints_ik, index, length}`` from a previous run without regen.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional


DEFAULT_MOMASK_HOME = Path.home() / ".local" / "share" / "auroraia" / "external" / "momask-codes"
DEFAULT_CONDA = Path.home() / ".local" / "opt" / "miniforge3" / "bin" / "conda"
DEFAULT_ENV = "momask"


def _momask_home() -> Path:
    return Path(os.environ.get("AURORA_MOMASK_HOME") or DEFAULT_MOMASK_HOME)


def _conda_bin() -> Path:
    return Path(os.environ.get("AURORA_MOMASK_CONDA") or DEFAULT_CONDA)


def _env_name() -> str:
    return os.environ.get("AURORA_MOMASK_ENV") or DEFAULT_ENV


def _sanitize_ext(ext: str) -> str:
    ext = re.sub(r"[^A-Za-z0-9_.-]", "_", ext.strip()) or "aurora_run"
    return ext[:80]


def locate_candidates(ext: str) -> List[Dict[str, Any]]:
    """Return one entry per repeat found under ``generation/<ext>``.

    Each entry has ``index``, ``length``, ``bvh_ik``, ``joints_ik`` and best-
    effort raw counterparts. Missing files are omitted from the list.
    """
    home = _momask_home()
    ext = _sanitize_ext(ext)
    anim_dir = home / "generation" / ext / "animations" / "0"
    joints_dir = home / "generation" / ext / "joints" / "0"
    out: List[Dict[str, Any]] = []
    if not anim_dir.is_dir():
        return out
    pattern = re.compile(r"^sample0_repeat(\d+)_len(\d+)_ik\.bvh$")
    for bvh in sorted(anim_dir.glob("sample0_repeat*_len*_ik.bvh")):
        m = pattern.match(bvh.name)
        if not m:
            continue
        idx = int(m.group(1))
        length = int(m.group(2))
        joints = joints_dir / f"sample0_repeat{idx}_len{length}_ik.npy"
        if not joints.is_file():
            # fallback to raw joints
            joints_raw = joints_dir / f"sample0_repeat{idx}_len{length}.npy"
            if joints_raw.is_file():
                joints = joints_raw
        out.append(
            {
                "index": idx,
                "length": length,
                "bvh_ik": str(bvh),
                "joints_ik": str(joints) if joints.is_file() else None,
            }
        )
    return out


def generate_motions(
    prompt: str,
    ext: str = "aurora_motion",
    repeat_times: int = 4,
    gpu_id: int = 0,
    timeout_s: int = 300,
    motion_length: int = 0,
    seed: Optional[int] = None,
) -> Dict[str, Any]:
    """Generate ``repeat_times`` motion variants for ``prompt`` and return metadata.

    Returns::

      {
        "ok": True,
        "prompt": ...,
        "ext": ...,
        "home": str(momask_home),
        "candidates": [ {index, length, bvh_ik, joints_ik}, ... ],
        "stdout_tail": "...",
      }

    Or on failure::

      { "ok": False, "error": "...", "stdout_tail": "...", "stderr_tail": "..." }
    """
    home = _momask_home()
    if not (home / "run_gen.py").is_file():
        return {
            "ok": False,
            "error": f"MoMask install missing: {home}/run_gen.py",
        }
    conda = _conda_bin()
    if not conda.is_file():
        return {"ok": False, "error": f"conda binary missing: {conda}"}
    env_name = _env_name()
    ext_clean = _sanitize_ext(ext)

    # Clean out any prior run under the same ext so we don't mix repeats.
    prior = home / "generation" / ext_clean
    if prior.is_dir():
        try:
            import shutil

            shutil.rmtree(prior)
        except Exception as exc:
            return {"ok": False, "error": f"cannot clean prior run {prior}: {exc}"}

    cmd: List[str] = [
        str(conda),
        "run",
        "-n",
        env_name,
        "--no-capture-output",
        "python",
        "run_gen.py",
        "--gpu_id",
        str(gpu_id),
        "--ext",
        ext_clean,
        "--repeat_times",
        str(max(1, repeat_times)),
        "--text_prompt",
        prompt,
    ]
    if motion_length and motion_length > 0:
        cmd += ["--motion_length", str(int(motion_length))]
    if seed is not None:
        cmd += ["--seed", str(int(seed))]

    try:
        proc = subprocess.run(
            cmd,
            cwd=str(home),
            capture_output=True,
            text=True,
            timeout=timeout_s,
        )
    except subprocess.TimeoutExpired as exc:
        return {
            "ok": False,
            "error": f"MoMask timed out after {timeout_s}s",
            "stdout_tail": (exc.stdout or "")[-2000:] if exc.stdout else "",
            "stderr_tail": (exc.stderr or "")[-2000:] if exc.stderr else "",
        }

    out_tail = (proc.stdout or "")[-2000:]
    err_tail = (proc.stderr or "")[-2000:]
    if proc.returncode != 0:
        return {
            "ok": False,
            "error": f"MoMask exit={proc.returncode}",
            "stdout_tail": out_tail,
            "stderr_tail": err_tail,
        }

    cands = locate_candidates(ext_clean)
    if not cands:
        return {
            "ok": False,
            "error": "MoMask produced no BVH output",
            "stdout_tail": out_tail,
            "stderr_tail": err_tail,
        }

    return {
        "ok": True,
        "prompt": prompt,
        "ext": ext_clean,
        "home": str(home),
        "candidates": cands,
        "stdout_tail": out_tail[-500:],
    }


def _cli() -> int:
    import argparse

    ap = argparse.ArgumentParser()
    ap.add_argument("--prompt", required=True)
    ap.add_argument("--ext", default="aurora_motion")
    ap.add_argument("--repeat", type=int, default=4)
    ap.add_argument("--gpu-id", type=int, default=0)
    ap.add_argument("--seed", type=int, default=None)
    ap.add_argument("--motion-length", type=int, default=0)
    args = ap.parse_args()
    res = generate_motions(
        args.prompt,
        ext=args.ext,
        repeat_times=args.repeat,
        gpu_id=args.gpu_id,
        motion_length=args.motion_length,
        seed=args.seed,
    )
    print(json.dumps(res, indent=2, ensure_ascii=False))
    return 0 if res.get("ok") else 1


if __name__ == "__main__":
    sys.exit(_cli())
