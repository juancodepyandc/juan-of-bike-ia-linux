"""hy3dpaint — Hunyuan3D-2.1 PBR texturing (albedo + metallic-roughness).

Wraps the vendored `_hy3dpaint/` pipeline. Given a "white" shape mesh + a reference
image, runs the PBR multiview-diffusion paint and writes a GLB whose material is a
glTF PBRMaterial carrying:
  - baseColorTexture        (the albedo, ~2k+)
  - metallicRoughnessTexture (glTF packing: G = roughness, B = metallic, R = 255)
  - normalTexture            (only if the renderer produced one — currently it doesn't,
                              the high->low normal bake is a separate stage)

This is the v2.1 replacement for the v2.0 albedo-only paint in `hy3dgen.texgen`.
On any failure (OOM at all resolutions, import error, ...) it returns {"ok": False}
and the caller falls back to the v2.0 path.

CLI (smoke test):
  python paint_pbr_v21.py --mesh white.glb --image ref.png --output out_pbr.glb [--views 4] [--res 512]
"""
from __future__ import annotations

import glob
import json
import os
import sys
import traceback
import cv2
import numpy as np
from pathlib import Path
from typing import Any

_HERE = Path(__file__).resolve().parent
_HY3DPAINT = _HERE / "_hy3dpaint"
_REPO_ROOT = _HERE.parents[1]  # .../AuroraIA-v2

# Make sure the HF cache points at the repo-local model store (the bridge sets
# HF_HUB_CACHE, but a standalone run might not).
_HF_LOCAL = _REPO_ROOT / "modele" / "huggingface"
if _HF_LOCAL.is_dir():
    os.environ.setdefault("HF_HOME", str(_HF_LOCAL))
    os.environ.setdefault("HF_HUB_CACHE", str(_HF_LOCAL / "hub"))

_pipeline_cache: dict[int, Any] = {}  # res -> Hunyuan3DPaintPipeline (per-process reuse)


def _ensure_path() -> None:
    p = str(_HY3DPAINT)
    if p not in sys.path:
        sys.path.insert(0, p)


def is_available() -> bool:
    """Cheap check: vendored dir + the built extensions importable."""
    if not (_HY3DPAINT / "textureGenPipeline.py").is_file():
        return False
    try:
        import torch  # noqa: F401  (custom_rasterizer_kernel needs torch's DLL dir first)
        import custom_rasterizer  # noqa: F401
        import mesh_inpaint_processor  # noqa: F401
        return True
    except Exception:
        return False


def _apply_torchvision_fix(log=print) -> None:
    """basicsr/realesrgan import torchvision.transforms.functional_tensor (removed in tv>=0.17)."""
    _ensure_path()
    try:
        from utils.torchvision_fix import apply_fix  # type: ignore
        apply_fix()
        return
    except Exception:
        pass
    try:  # minimal hand-rolled shim
        import types
        import torchvision.transforms.functional as _F
        if "torchvision.transforms.functional_tensor" not in sys.modules:
            m = types.ModuleType("torchvision.transforms.functional_tensor")
            m.rgb_to_grayscale = _F.rgb_to_grayscale  # type: ignore[attr-defined]
            sys.modules["torchvision.transforms.functional_tensor"] = m
    except Exception as exc:  # noqa: BLE001
        log(f"PROGRESS:texture_warn:torchvision_fix indisponible ({exc!r})")


def _build_pipeline(max_num_view: int, resolution: int, log=print):
    _ensure_path()
    _apply_torchvision_fix(log)
    import torch  # noqa: F401
    import custom_rasterizer  # noqa: F401  (load torch DLLs first via the import above)
    from textureGenPipeline import Hunyuan3DPaintConfig, Hunyuan3DPaintPipeline  # type: ignore

    cfg = Hunyuan3DPaintConfig(max_num_view, resolution)
    cfg.multiview_cfg_path = str(_HY3DPAINT / "cfgs" / "hunyuan-paint-pbr.yaml")
    cfg.realesrgan_ckpt_path = str(_HY3DPAINT / "ckpt" / "RealESRGAN_x4plus.pth")
    # `custom_pipeline` is built inside utils/multiview_utils as
    # os.path.join(dirname(__file__), "..", "hunyuanpaintpbr") which resolves under _hy3dpaint — ok.
    log(f"PROGRESS:texture_load:hy3dpaint PBR 2.1 — chargement modeles (vues={max_num_view}, res={resolution})...")
    return Hunyuan3DPaintPipeline(cfg)


def _open_rgb(path):
    from PIL import Image
    if path and os.path.isfile(path):
        return Image.open(path).convert("RGB")
    return None


def _compose_metallic_roughness(metallic_png, roughness_png, roughness_floor: float = 0.88):
    """glTF metallicRoughnessTexture: R=occlusion(unused→255), G=roughness, B=metallic."""
    from PIL import Image
    import numpy as np
    m = _open_rgb(metallic_png)
    r = _open_rgb(roughness_png)
    if m is None and r is None:
        return None
    ref = m if m is not None else r
    size = ref.size
    m_l = (m.convert("L") if m is not None else Image.new("L", size, 0))
    min_byte = int(roughness_floor * 255)
    if r is not None:
        r_arr = np.asarray(r.convert("L"), dtype=np.uint8)
        r_clamped = np.clip(r_arr, min_byte, 255)
        r_l = Image.fromarray(r_clamped)
    else:
        r_l = Image.new("L", size, min_byte)
    if m_l.size != size:
        m_l = m_l.resize(size)
    if r_l.size != size:
        r_l = r_l.resize(size)
    full = Image.new("L", size, 255)
    return Image.merge("RGB", (full, r_l, m_l))


def _find_map(directory: str, *needles: str):
    for needle in needles:
        for ext in ("png", "jpg", "jpeg"):
            hits = sorted(glob.glob(os.path.join(directory, f"*{needle}*.{ext}")))
            if hits:
                return hits[0]
    return None


def paint_pbr_v21(
    white_mesh_path: str,
    ref_image,
    out_glb_path: str,
    work_dir: str,
    max_num_view: int = 4,
    resolution: int = 512,
    log=print,
    prompt: str | None = None,
) -> dict[str, Any]:
    """Run the hy3dpaint PBR pipeline. Returns {ok, glb, has_mr, has_normal, has_albedo, faces} or {ok:False, error}."""
    try:
        import trimesh
        from PIL import Image
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": f"missing dep: {exc!r}"}

    os.makedirs(work_dir, exist_ok=True)

    # Normalise the reference -> PIL RGB with anti-halo edge dilation.
    if isinstance(ref_image, str):
        raw_img = Image.open(ref_image)
    elif isinstance(ref_image, Image.Image):
        raw_img = ref_image
    else:
        raw_img = None

    if raw_img is not None:
        if raw_img.mode == "RGBA":
            arr = np.array(raw_img)
            alpha = arr[..., 3]
            if (alpha == 0).any() and (alpha > 0).any():
                rgb = arr[..., :3].copy()
                mask = (alpha == 0).astype(np.uint8) * 255
                # Dilate edge colors into transparent region to eliminate white halo/speckles on seams
                dilated_rgb = cv2.inpaint(rgb, mask, 7, cv2.INPAINT_TELEA)
                img = Image.fromarray(dilated_rgb)
            else:
                img = raw_img.convert("RGB")
        else:
            img = raw_img.convert("RGB")
    else:
        img = ref_image

    # The pipeline wants a file path it can `trimesh.load` + remesh; if we were handed a
    # GLB (or an in-memory mesh saved by the caller), give it an OBJ.
    src = white_mesh_path
    if not str(src).lower().endswith((".obj", ".ply", ".glb")):
        m0 = trimesh.load(src, force="mesh", process=False)
        src = os.path.join(work_dir, "white_mesh.obj")
        m0.export(src)

    out_obj = os.path.join(work_dir, "textured_pbr.obj")
    errors: list[str] = []
    used_res = None

    # v90: graceful OOM ladder. Old [resolution,384,256] meant a 1024 OOM crashed
    # straight to 384 (worse than the old 512 default). Step down gently so a high
    # target degrades to the next-best resolution, not the floor.
    _ladder = list(dict.fromkeys([resolution, 768, 512, 384, 256]))
    _ladder = [r for r in _ladder if r <= resolution] or [resolution]
    for res in _ladder:
        try:
            if res not in _pipeline_cache:
                # free any previously-built pipeline at another res before building a new one
                if _pipeline_cache:
                    try:
                        import gc
                        import torch
                        _pipeline_cache.clear()
                        gc.collect()
                        torch.cuda.empty_cache()
                    except Exception:
                        _pipeline_cache.clear()
                _pipeline_cache[res] = _build_pipeline(max_num_view, res, log)
            pipe = _pipeline_cache[res]
            try:
                pipe.config.resolution = res
            except Exception:
                pass
            log(f"PROGRESS:texture_run:hy3dpaint PBR 2.1 — diffusion multivue (res={res}, vues={max_num_view})...")
            pipe(mesh_path=src, image_path=img, output_mesh_path=out_obj, use_remesh=True, save_glb=False, prompt=prompt)
            used_res = res
            break
        except RuntimeError as exc:
            msg = str(exc)
            errors.append(f"res={res}: {msg}")
            low = msg.lower()
            if ("out of memory" in low) or ("cuda error" in low) or ("cublas" in low) or ("alloc" in low):
                log(f"PROGRESS:texture_warn:hy3dpaint OOM/CUDA @res={res} — retry resolution plus basse...")
                try:
                    import gc
                    import torch
                    _pipeline_cache.clear()
                    gc.collect()
                    torch.cuda.empty_cache()
                except Exception:
                    _pipeline_cache.clear()
                continue
            return {"ok": False, "error": f"hy3dpaint runtime error: {msg}", "errors": errors}
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "error": f"hy3dpaint error: {exc!r}", "trace": traceback.format_exc(), "errors": errors}
    else:
        return {"ok": False, "error": f"hy3dpaint OOM at all resolutions", "errors": errors}

    if not os.path.isfile(out_obj):
        return {"ok": False, "error": "hy3dpaint produced no textured OBJ", "errors": errors}

    # Collect the textured OBJ + sibling PBR maps.
    out_dir = os.path.dirname(out_obj)
    metallic_png = _find_map(out_dir, "metallic")
    roughness_png = _find_map(out_dir, "roughness")
    normal_png = _find_map(out_dir, "normal")

    tm = trimesh.load(out_obj, force="mesh", process=False)
    uv = getattr(getattr(tm, "visual", None), "uv", None)
    mat0 = getattr(getattr(tm, "visual", None), "material", None)
    albedo = None
    if mat0 is not None:
        albedo = getattr(mat0, "baseColorTexture", None) or getattr(mat0, "image", None)
    if albedo is None:
        albedo = getattr(getattr(tm, "visual", None), "image", None)
    if albedo is None:
        ap = _find_map(out_dir, "albedo", "diffuse", "basecolor")
        albedo = _open_rgb(ap)

    mr_img = _compose_metallic_roughness(metallic_png, roughness_png)
    normal_img = _open_rgb(normal_png)

    pbr_kwargs: dict[str, Any] = {"metallicFactor": 1.0, "roughnessFactor": 1.0}
    if albedo is not None:
        pbr_kwargs["baseColorTexture"] = albedo
    if mr_img is not None:
        pbr_kwargs["metallicRoughnessTexture"] = mr_img
    if normal_img is not None:
        pbr_kwargs["normalTexture"] = normal_img
    material = trimesh.visual.material.PBRMaterial(**pbr_kwargs)
    if uv is not None:
        tm.visual = trimesh.visual.TextureVisuals(uv=uv, material=material, image=albedo)
    elif getattr(tm, "visual", None) is not None:
        tm.visual.material = material

    os.makedirs(os.path.dirname(out_glb_path) or ".", exist_ok=True)
    tm.export(out_glb_path)
    return {
        "ok": True,
        "glb": out_glb_path,
        "obj": out_obj,
        "resolution": used_res,
        "has_albedo": albedo is not None,
        "has_mr": mr_img is not None,
        "has_normal": normal_img is not None,
        "faces": int(len(tm.faces)),
        "vertices": int(len(tm.vertices)),
    }


def main() -> None:
    import argparse
    ap = argparse.ArgumentParser(description="hy3dpaint PBR 2.1 texturing (smoke test).")
    ap.add_argument("--mesh", required=True)
    ap.add_argument("--image", required=True)
    ap.add_argument("--output", required=True)
    ap.add_argument("--work-dir", default=None)
    ap.add_argument("--views", type=int, default=4)
    ap.add_argument("--res", type=int, default=512)
    args = ap.parse_args()
    wd = args.work_dir or os.path.join(os.path.dirname(os.path.abspath(args.output)), "_pbr_work")
    res = paint_pbr_v21(args.mesh, args.image, args.output, wd, max_num_view=args.views, resolution=args.res)
    print(json.dumps(res, default=str))
    sys.exit(0 if res.get("ok") else 1)


if __name__ == "__main__":
    main()
