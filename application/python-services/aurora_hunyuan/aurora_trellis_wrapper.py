"""Aurora wrapper for microsoft/TRELLIS image-to-3D.

Trellis is a state-of-the-art structured-3D-latents model that can produce
cleaner geometry than Hunyuan3D-2 on vehicles, architecture, and multi-element
scenes. We call it ONLY as an optional second-pass when the Hunyuan3D output
fails certain critic gates (e.g. floaters/disconnected/box-aspect).

Hard runtime constraints we hit on this machine (RTX 5070 Ti / Blackwell SM 12.0
+ PyTorch nightly cu128):
  - Trellis upstream supports PyTorch 2.4.0 + cu118/cu121/cu124 only. Custom CUDA
    kernels (diffoctreerast, vox2seq, spconv, mip-splatting, kaolin) need to be
    compiled against the exact torch+cuda combination and require Linux toolchain.
  - On Blackwell SM 12.0 with cu128 nightly, prebuilt wheels do not exist.
    Compiling from source on Windows fails for several of these modules.

So this wrapper is intentionally *optional*: if Trellis is importable and
TRELLIS_READY is True, we use it; otherwise we just signal "not available"
and the caller falls back to Hunyuan3D-2 (which we already have working).

Usage:
    from aurora_trellis_wrapper import is_available, generate_glb
    if is_available():
        glb_bytes = generate_glb(image_path, out_glb)

Setup (when ready):
    pip install pillow imageio imageio-ffmpeg easydict opencv-python-headless
                 open3d xatlas pyvista pymeshfix igraph
    pip install git+https://github.com/EasternJournalist/utils3d.git
    # Then attempt the custom CUDA kernels in the TRELLIS repo:
    cd TRELLIS && bash setup.sh --kaolin --nvdiffrast --diffoctreerast --vox2seq --spconv
    # Most likely fails on Windows + Blackwell; report error and stick to Hunyuan3D.
"""
from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

log = logging.getLogger("trellis_wrapper")

# Make Trellis importable when the repo is sibling to this file's parent.
TRELLIS_ROOT = Path(r"C:\Users\Juan\Desktop\ia\TRELLIS")
if TRELLIS_ROOT.exists() and str(TRELLIS_ROOT) not in sys.path:
    sys.path.insert(0, str(TRELLIS_ROOT))


def _try_import():
    """Return (ok, error_str). True = Trellis pipelines import cleanly."""
    try:
        os.environ.setdefault("ATTN_BACKEND", "xformers")
        os.environ.setdefault("SPCONV_ALGO", "native")
        from trellis.pipelines import TrellisImageTo3DPipeline  # noqa: F401
        return True, None
    except ImportError as e:
        return False, f"ImportError: {e}"
    except Exception as e:
        return False, f"{type(e).__name__}: {e}"


_AVAILABLE, _IMPORT_ERROR = _try_import()


def is_available() -> bool:
    return _AVAILABLE


def import_error() -> str | None:
    return _IMPORT_ERROR


_PIPE_CACHE = None


def _load_pipe():
    global _PIPE_CACHE
    if _PIPE_CACHE is not None:
        return _PIPE_CACHE
    from trellis.pipelines import TrellisImageTo3DPipeline
    log.info("[trellis] loading TrellisImageTo3DPipeline from microsoft/TRELLIS-image-large")
    pipe = TrellisImageTo3DPipeline.from_pretrained("microsoft/TRELLIS-image-large")
    pipe.cuda()
    _PIPE_CACHE = pipe
    return pipe


def generate_glb(image_path: Path | str, out_glb: Path | str,
                  seed: int = 1, num_samples_first_stage: int = 12,
                  num_samples_second_stage: int = 12) -> dict:
    """Run Trellis image -> 3D and export a GLB with textured mesh.
    Returns {ok, out_glb, faces, verts, error?}. Never raises."""
    if not _AVAILABLE:
        return {"ok": False, "error": f"trellis not available: {_IMPORT_ERROR}"}
    try:
        from PIL import Image
        import torch  # noqa: F401
        pipe = _load_pipe()
        img = Image.open(str(image_path)).convert("RGBA")
        out = pipe.run(
            img,
            seed=seed,
            sparse_structure_sampler_params={"steps": num_samples_first_stage},
            slat_sampler_params={"steps": num_samples_second_stage},
            formats=["mesh"],
        )
        mesh = out["mesh"][0]
        # export glb via utils3d / trellis renderer
        try:
            from trellis.utils import postprocessing_utils
            glb = postprocessing_utils.to_glb(out["gaussian"][0] if "gaussian" in out else None,
                                                 mesh, simplify=0.95, texture_size=1024)
            glb.export(str(out_glb))
        except Exception:
            # fall back to raw mesh export
            import trimesh
            tm = trimesh.Trimesh(vertices=mesh.vertices.cpu().numpy(),
                                   faces=mesh.faces.cpu().numpy(), process=False)
            tm.export(str(out_glb))
        return {
            "ok": True,
            "out_glb": str(out_glb),
            "verts": int(len(mesh.vertices)),
            "faces": int(len(mesh.faces)),
        }
    except Exception as e:
        return {"ok": False, "error": f"{type(e).__name__}: {str(e)[:300]}"}


def main(argv: list[str]) -> int:
    import json
    if len(argv) < 2:
        print(json.dumps({"available": is_available(),
                            "error": import_error(),
                            "usage": "aurora_trellis_wrapper.py <image> [out.glb]"}, indent=2))
        return 0
    image = argv[1]
    out = argv[2] if len(argv) > 2 else "trellis_out.glb"
    r = generate_glb(image, out)
    print(json.dumps(r, indent=2))
    return 0 if r["ok"] else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
