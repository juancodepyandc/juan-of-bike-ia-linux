#!/usr/bin/env python
"""MV-Adapter re-texturing wrapper for Aurora hard-surface reproductions.

Re-textures a mesh (typically the Hunyuan3D / TRELLIS output for a product,
vehicle or other hard-surface subject) by running MV-Adapter's
`texture_i2tex.py` script. MV-Adapter uses UV-aware multi-view diffusion:
it generates 6 consistent views of the mesh from a reference photo, then
un-projects them onto a clean 4K UV atlas via CV-CUDA + nvdiffrast.

Why this exists — TRELLIS.2 paints textures directly into the fragmented
atlas that Marching Cubes produces (hundreds of tiny UV islands).
Reproducing a symbol like the PlayStation button glyphs in that space is a
crapshoot: the ink lands on random UV islands and the mesh reads as
scribbled. MV-Adapter side-steps the problem entirely by regenerating a
clean atlas + baking view-consistent RGB on top.

## Contract

* Input: a `.glb` (Aurora rescue output) and a reference photo (Aurora
  FLUX reference).
* Output: a new `<save_name>_shaded.glb` next to `save_dir`, ~2-5 MB with
  a 4K baseColor texture. Original mesh is untouched.
* Runs the vendored MV-Adapter tree (external, cloned to
  `~/.local/share/auroraia/external/MV-Adapter`) inside the `mvadapter`
  conda env (Python 3.10, torch 2.11 cu128 Blackwell).
* Peak VRAM ~15 GB (SDXL 768^2 + 4K UV bake) on a shared 16 GB card.
* Failure modes: env missing (returns ok=False + reason), OOM (returns
  ok=False + captured stderr), input mesh unreadable, non-manifold that
  survives MV-Adapter's own cleanup step. On any failure the caller
  keeps the original mesh unchanged.

## Schema

Returns `aurora.mvadapter_retexture.v1`::

    {
        "ok": bool,
        "schema": "aurora.mvadapter_retexture.v1",
        "in_mesh": "...",
        "reference": "...",
        "out_mesh": "..." | None,
        "elapsed_s": float,
        "peak_vram_mb": int | None,
        "reason": str | None,   # populated when ok=False
        "log_tail": str,        # last 4 KB of stderr for diagnostics
    }

## Prerequisites (installed once by the operator, not by this script)

* Conda env `mvadapter` with torch cu128, MV-Adapter's `requirements.txt`
  (+ `jaxtyping`, `typeguard`, `gltflib`).
* MV-Adapter tree cloned + local patches applied (ref hidden-states offload
  to CPU, pymeshlab `PercentageValue` shim, `del pipe` before texture
  bake). Those patches keep peak VRAM under 16 GB on Blackwell 5070 Ti.
* Weights `RealESRGAN_x2plus.pth`, `big-lama.pt` in `MV-Adapter/checkpoints`.
* HF cache pre-populated with SDXL base + BiRefNet + MV-Adapter (auto on
  first run).

The env/paths can be overridden via environment variables:

* `AURORA_MVADAPTER_CONDA` — conda env name (default `mvadapter`).
* `AURORA_MVADAPTER_ROOT` — path to the MV-Adapter checkout (default
  `~/.local/share/auroraia/external/MV-Adapter`).
* `AURORA_MVADAPTER_HF_HOME` — HF cache (default `~/.cache/huggingface`).
* `AURORA_MVADAPTER_VARIANT` — `sdxl` (default) or `sd21` (fallback for
  <10 GB VRAM, requires HF access to SD2.1 base).
* `AURORA_MVADAPTER_TIMEOUT_S` — hard cap on the subprocess (default 900).
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path


SCHEMA = "aurora.mvadapter_retexture.v1"

DEFAULT_CONDA_ENV = os.environ.get("AURORA_MVADAPTER_CONDA", "mvadapter")
DEFAULT_MVADAPTER_ROOT = Path(
    os.environ.get(
        "AURORA_MVADAPTER_ROOT",
        str(Path.home() / ".local" / "share" / "auroraia" / "external" / "MV-Adapter"),
    )
)
DEFAULT_HF_HOME = os.environ.get(
    "AURORA_MVADAPTER_HF_HOME", str(Path.home() / ".cache" / "huggingface")
)
DEFAULT_VARIANT = os.environ.get("AURORA_MVADAPTER_VARIANT", "sdxl")
DEFAULT_TIMEOUT_S = int(os.environ.get("AURORA_MVADAPTER_TIMEOUT_S", "900"))
DEFAULT_MINICONDA = Path(
    os.environ.get(
        "AURORA_MINICONDA_ROOT",
        str(Path.home() / ".local" / "opt" / "miniforge3"),
    )
)


def _conda_python(env_name: str) -> Path | None:
    """Return the Python binary for a named conda env, or None if absent."""
    candidate = DEFAULT_MINICONDA / "envs" / env_name / "bin" / "python"
    return candidate if candidate.is_file() else None


def preflight() -> dict:
    """Report whether all pieces are in place — non-destructive."""
    py = _conda_python(DEFAULT_CONDA_ENV)
    root = DEFAULT_MVADAPTER_ROOT
    weights = [
        root / "checkpoints" / "RealESRGAN_x2plus.pth",
        root / "checkpoints" / "big-lama.pt",
    ]
    missing_weights = [str(p) for p in weights if not p.is_file()]
    return {
        "conda_env": DEFAULT_CONDA_ENV,
        "conda_python": str(py) if py else None,
        "mvadapter_root": str(root),
        "mvadapter_root_exists": root.is_dir(),
        "script_exists": (root / "scripts" / "texture_i2tex.py").is_file(),
        "missing_weights": missing_weights,
        "ready": (
            py is not None
            and root.is_dir()
            and (root / "scripts" / "texture_i2tex.py").is_file()
            and not missing_weights
        ),
    }


def retexture(
    in_mesh: str | Path,
    reference: str | Path,
    save_dir: str | Path,
    save_name: str,
    *,
    variant: str = DEFAULT_VARIANT,
    remove_bg: bool = True,
    preprocess_mesh: bool = True,
    conda_env: str = DEFAULT_CONDA_ENV,
    mvadapter_root: Path = DEFAULT_MVADAPTER_ROOT,
    hf_home: str = DEFAULT_HF_HOME,
    timeout_s: int = DEFAULT_TIMEOUT_S,
) -> dict:
    """Run MV-Adapter re-texturing. See module docstring for the schema."""
    started = time.time()
    result: dict = {
        "ok": False,
        "schema": SCHEMA,
        "in_mesh": str(in_mesh),
        "reference": str(reference),
        "out_mesh": None,
        "elapsed_s": 0.0,
        "peak_vram_mb": None,
        "reason": None,
        "log_tail": "",
    }
    in_mesh = Path(in_mesh)
    reference = Path(reference)
    save_dir = Path(save_dir)
    save_dir.mkdir(parents=True, exist_ok=True)

    if not in_mesh.is_file():
        result["reason"] = f"input mesh missing: {in_mesh}"
        return result
    if not reference.is_file():
        result["reason"] = f"reference image missing: {reference}"
        return result

    prechecks = preflight()
    if not prechecks["ready"]:
        result["reason"] = (
            "mvadapter env not ready: " + json.dumps(prechecks, ensure_ascii=True)
        )
        return result

    python_bin = prechecks["conda_python"]
    assert python_bin is not None  # narrowed by ready check

    env = dict(os.environ)
    env["HF_HOME"] = hf_home
    # expandable_segments reclaims fragmented VRAM slices — necessary on 5070 Ti.
    env.setdefault("PYTORCH_CUDA_ALLOC_CONF", "expandable_segments:True")

    cmd = [
        python_bin,
        "-m", "scripts.texture_i2tex",
        "--variant", variant,
        "--image", str(reference),
        "--mesh", str(in_mesh),
        "--save_dir", str(save_dir),
        "--save_name", save_name,
    ]
    if preprocess_mesh:
        cmd.append("--preprocess_mesh")
    if remove_bg:
        cmd.append("--remove_bg")

    try:
        # SORTIE SUR DISQUE, PAS EN MEMOIRE. `capture_output=True` accumule
        # TOUT ce que l'enfant ecrit dans la RAM du parent, sans borne. MV-Adapter
        # est un modele de diffusion: il ecrit des barres de progression en
        # continu pendant des minutes. Mesure du 05/09 a la sonde 2 secondes:
        # le pipeline passe de 1 Go a 28 Go en HUIT secondes a cette etape,
        # sans aucun processus enfant visible, puis se fait tuer par le noyau.
        # Sept lancements perdus. On ne garde que la fin du flux: le resultat
        # et les messages d'erreur y sont.
        import tempfile as _tf

        class _Proc:
            pass

        with _tf.TemporaryFile("w+", encoding="utf-8", errors="replace") as _fo, \
             _tf.TemporaryFile("w+", encoding="utf-8", errors="replace") as _fe:
            _rc = subprocess.run(
                cmd,
                cwd=str(mvadapter_root),
                env=env,
                stdout=_fo,
                stderr=_fe,
                text=True,
                timeout=timeout_s,
            )
            _fo.seek(0); _fe.seek(0)
            proc = _Proc()
            proc.returncode = _rc.returncode
            proc.stdout = _fo.read()[-200000:]
            proc.stderr = _fe.read()[-200000:]
    except subprocess.TimeoutExpired as exc:
        result["reason"] = f"timeout after {timeout_s}s"
        result["log_tail"] = (exc.stderr or "")[-4096:] if hasattr(exc, "stderr") else ""
        result["elapsed_s"] = round(time.time() - started, 2)
        return result
    except Exception as exc:  # noqa: BLE001
        result["reason"] = f"subprocess failed to launch: {exc!r}"
        result["elapsed_s"] = round(time.time() - started, 2)
        return result

    result["elapsed_s"] = round(time.time() - started, 2)
    log_tail = ((proc.stderr or "") + "\n" + (proc.stdout or ""))[-4096:]
    result["log_tail"] = log_tail
    if proc.returncode != 0:
        result["reason"] = f"exit {proc.returncode}"
        return result

    out_path = save_dir / f"{save_name}_shaded.glb"
    if not out_path.is_file():
        result["reason"] = f"missing output {out_path}"
        return result
    result["ok"] = True
    result["out_mesh"] = str(out_path)
    return result


def _main() -> int:
    p = argparse.ArgumentParser(description="MV-Adapter re-texturing wrapper")
    p.add_argument("--mesh", help="Input GLB to re-texture (required unless --preflight)")
    p.add_argument("--reference",
                   help="Reference photo — FLUX synth or user-supplied (required unless --preflight)")
    p.add_argument("--save-dir", dest="save_dir",
                   help="Output directory (required unless --preflight)")
    p.add_argument("--save-name", dest="save_name",
                   help="Output basename — writes <save_dir>/<save_name>_shaded.glb (required unless --preflight)")
    p.add_argument("--variant", default=DEFAULT_VARIANT, choices=["sdxl", "sd21"])
    p.add_argument("--no-remove-bg", action="store_true")
    p.add_argument("--no-preprocess", action="store_true")
    p.add_argument("--preflight", action="store_true",
                   help="Report env readiness and exit without running")
    p.add_argument("--pretty", action="store_true")
    args = p.parse_args()
    if args.preflight:
        out = preflight()
    else:
        missing = [name for name in ("mesh", "reference", "save_dir", "save_name")
                   if not getattr(args, name)]
        if missing:
            p.error("required unless --preflight: --" + ", --".join(missing))
        out = retexture(
            in_mesh=args.mesh,
            reference=args.reference,
            save_dir=args.save_dir,
            save_name=args.save_name,
            variant=args.variant,
            remove_bg=not args.no_remove_bg,
            preprocess_mesh=not args.no_preprocess,
        )
    sys.stdout.write(json.dumps(out, indent=2 if args.pretty else None, ensure_ascii=True) + "\n")
    return 0 if out.get("ok", out.get("ready", False)) else 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(_main())
