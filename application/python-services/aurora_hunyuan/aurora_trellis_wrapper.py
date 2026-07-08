"""Aurora wrapper for microsoft/TRELLIS.2 image-to-3D (module `trellis2`).

TRELLIS.2-4B reconstruit une geometrie 3D COHERENTE + PBR depuis UNE seule image,
en interne, sans jamais fusionner des vues qui se contredisent. C'est ce qui elimine
le "double-visage / cornes doublees / poitrine fragmentee" du chemin Hunyuan-2mv
(4 vues FLUX independantes). Valide sur RTX 5070 Ti / Blackwell sm_120 :
peak VRAM ~3.6 Go (tres en dessous des 16 Go), ~4 min/objet.

Kernels compiles pour cette machine (voir SETUP_TRELLIS2_LINUX.md) :
flex_gemm, cumesh, o_voxel, nvdiffrast. Modele : microsoft/TRELLIS.2-4B (deja en cache HF).

Usage:
    from aurora_trellis_wrapper import is_available, generate_glb
    if is_available():
        r = generate_glb(image_path, out_glb)  # {ok, out_glb, faces, verts} / {ok:False, error}
"""
from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

log = logging.getLogger("trellis2_wrapper")

# TRELLIS.2 vit hors du package (repo external) — l'ajouter au path.
_TRELLIS_CANDIDATES = [
    os.environ.get("AURORA_TRELLIS_ROOT"),
    "/home/juan/.local/share/auroraia/external/TRELLIS.2",
    os.path.expanduser("~/.local/share/auroraia/external/TRELLIS.2"),
]
TRELLIS_ROOT = next((Path(p) for p in _TRELLIS_CANDIDATES if p and Path(p).exists()), Path("/nonexistent"))
if TRELLIS_ROOT.exists() and str(TRELLIS_ROOT) not in sys.path:
    sys.path.insert(0, str(TRELLIS_ROOT))

# Backends: flex_gemm (conv sparse) + xformers (attention) — flash_attn PAS requis.
os.environ.setdefault("ATTN_BACKEND", "xformers")
os.environ.setdefault("SPCONV_ALGO", "native")
os.environ.setdefault("PYTORCH_CUDA_ALLOC_CONF", "expandable_segments:True")
# nvdiffrast JIT-compile son plugin CUDA au 1er usage -> besoin de nvcc dans le PATH.
if "CUDA_HOME" not in os.environ and Path("/usr/local/cuda-12.8").exists():
    os.environ["CUDA_HOME"] = "/usr/local/cuda-12.8"
_cuda_bin = os.path.join(os.environ.get("CUDA_HOME", ""), "bin")
if _cuda_bin and _cuda_bin not in os.environ.get("PATH", ""):
    os.environ["PATH"] = _cuda_bin + os.pathsep + os.environ.get("PATH", "")

MODEL_ID = os.environ.get("AURORA_TRELLIS2_MODEL", "microsoft/TRELLIS.2-4B")


def _try_import():
    """Return (ok, error_str). True = TRELLIS.2 + tous les kernels importent."""
    try:
        import torch  # noqa: F401
        import flex_gemm  # noqa: F401
        import cumesh  # noqa: F401
        import o_voxel  # noqa: F401
        import nvdiffrast.torch  # noqa: F401
        from trellis2.pipelines import Trellis2ImageTo3DPipeline  # noqa: F401
        return True, None
    except ImportError as e:
        return False, f"ImportError: {e}"
    except Exception as e:  # noqa: BLE001
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
    from trellis2.pipelines import Trellis2ImageTo3DPipeline
    log.info("[trellis2] loading Trellis2ImageTo3DPipeline from %s", MODEL_ID)
    pipe = Trellis2ImageTo3DPipeline.from_pretrained(MODEL_ID)
    pipe.cuda()
    _PIPE_CACHE = pipe
    return pipe


# Qualite par defaut : 1024_cascade = le defaut TRELLIS.2, excellent detail ET fiable sur 16 Go
# (peak ~4-6 Go). 1536_cascade est plus fin mais monte a ~15 Go et OOM a l'extraction CuMesh
# dans le contexte du pipeline -> on l'essaie seulement si demande, avec repli automatique.
# Options: 512, 1024, 1024_cascade, 1536_cascade.
QUALITY = os.environ.get("AURORA_TRELLIS2_QUALITY", "1024_cascade")
# Echelle de repli sur OOM (garde la meilleure resolution qui tient reellement en VRAM).
_QUALITY_LADDER = ["1536_cascade", "1024_cascade", "1024", "512"]


def _upscale_glb_texture(glb_path: str, factor: int = 2, tile: int = 768) -> bool:
    """Upscale l'albedo du GLB x`factor` (8192 -> 16384 = 16K) via RealESRGAN en tuiles
    (faible VRAM), en place. Best-effort : renvoie False sans casser si indispo."""
    try:
        import numpy as np
        from PIL import Image
        Image.MAX_IMAGE_PIXELS = None
        import trimesh
        _ps = str(Path(__file__).resolve().parent.parent)  # python-services
        if _ps not in sys.path:
            sys.path.insert(0, _ps)
        import paint_pbr_v21 as _pbr  # reutilise le fix torchvision + RealESRGAN de la texture
        _pbr._apply_torchvision_fix()
        from realesrgan import RealESRGANer
        from basicsr.archs.rrdbnet_arch import RRDBNet
        ckpt = str(Path(_ps) / "_hy3dpaint" / "ckpt" / "RealESRGAN_x4plus.pth")
        model = RRDBNet(num_in_ch=3, num_out_ch=3, num_feat=64, num_block=23, num_grow_ch=32, scale=4)
        up = RealESRGANer(scale=4, model_path=ckpt, model=model, tile=tile, tile_pad=16,
                          pre_pad=0, half=True, gpu_id=0)
        m = trimesh.load(glb_path, force="mesh", process=False)
        mat = getattr(m.visual, "material", None)
        img = getattr(mat, "baseColorTexture", None) if mat is not None else None
        if img is None:
            return False
        out, _ = up.enhance(np.array(img.convert("RGB")), outscale=factor)
        mat.baseColorTexture = Image.fromarray(out)
        m.export(glb_path)
        return True
    except Exception:
        return False


def generate_glb(image_path: Path | str, out_glb: Path | str,
                  *, texture_size: int | None = None, decimation_target: int = 2_000_000,
                  pipeline_type: str | None = None, seed: int = 1) -> dict:
    """Run TRELLIS.2 image -> 3D (geometrie coherente + PBR) et exporte un GLB.
    Returns {ok, out_glb, faces, verts, peak_vram_gb, quality, error?}. Never raises."""
    if not _AVAILABLE:
        return {"ok": False, "error": f"trellis2 not available: {_IMPORT_ERROR}"}
    try:
        import torch
        from PIL import Image
        import o_voxel

        ptype = pipeline_type or QUALITY
        # Texture 8192 NATIF (le bake to_glb 16384 OOM sur 16 Go: manque ~4 Go). Le vrai 16K
        # est obtenu ensuite par upscale RealESRGAN x2 en tuiles (faible VRAM). Configurable.
        if texture_size is None:
            texture_size = int(os.environ.get("AURORA_TRELLIS2_TEXTURE", "8192"))
        pipe = _load_pipe()
        image = Image.open(str(image_path)).convert("RGB")
        # Repli automatique sur OOM : essaie ptype puis les paliers plus bas (CuMesh/CUDA OOM).
        if ptype in _QUALITY_LADDER:
            _ladder = _QUALITY_LADDER[_QUALITY_LADDER.index(ptype):]
        else:
            _ladder = [ptype]
        mesh = None
        used_q = ptype
        for _q in _ladder:
            try:
                torch.cuda.reset_peak_memory_stats()
                torch.cuda.empty_cache()
                mesh = pipe.run(image, seed=seed, pipeline_type=_q)[0]
                used_q = _q
                break
            except Exception as _oom:  # noqa: BLE001
                _msg = str(_oom).lower()
                if "out of memory" in _msg or "outofmemory" in type(_oom).__name__.lower():
                    torch.cuda.empty_cache()
                    continue
                raise
        if mesh is None:
            return {"ok": False, "error": f"OOM a tous les paliers ({_ladder})"}
        ptype = used_q
        mesh.simplify(16_777_216)  # limite nvdiffrast

        # Export to_glb (remesh + bake texture) : peut OOM (CuMesh) sur un mesh complexe
        # (ex. carte mere reelle detaillee). On descend texture/decimation plutot que de
        # laisser tomber vers le Hunyuan mou. Garde TRELLIS meme en cas de VRAM serree.
        _glb_ladder = [(int(texture_size), int(decimation_target)),
                       (4096, 1_000_000), (2048, 500_000)]
        _glb_ladder = [(t, d) for (t, d) in _glb_ladder if t <= int(texture_size)]
        glb = None
        for _ts, _dt in _glb_ladder:
            try:
                torch.cuda.empty_cache()
                glb = o_voxel.postprocess.to_glb(
                    vertices=mesh.vertices, faces=mesh.faces, attr_volume=mesh.attrs,
                    coords=mesh.coords, attr_layout=mesh.layout, voxel_size=mesh.voxel_size,
                    aabb=[[-0.5, -0.5, -0.5], [0.5, 0.5, 0.5]],
                    decimation_target=_dt, texture_size=_ts,
                    remesh=True, remesh_band=1, remesh_project=0, verbose=False,
                )
                texture_size = _ts
                break
            except Exception as _ge:  # noqa: BLE001
                if "out of memory" in str(_ge).lower():
                    torch.cuda.empty_cache()
                    continue
                raise
        if glb is None:
            return {"ok": False, "error": "to_glb OOM a tous les paliers texture"}
        out_glb = str(out_glb)
        glb.export(out_glb)
        peak = float(torch.cuda.max_memory_allocated() / 1e9)
        # Option 16K : upscale RealESRGAN x2 de l'albedo (8192 -> 16384). Desactive par defaut
        # (GLB ~300-500 Mo, lourd pour le viewer). Activer via AURORA_TRELLIS2_16K=1.
        up16 = False
        if os.environ.get("AURORA_TRELLIS2_16K", "0") == "1" and int(texture_size) <= 8192:
            up16 = _upscale_glb_texture(out_glb, factor=2)
        try:
            faces = int(len(mesh.faces))
            verts = int(len(mesh.vertices))
        except Exception:
            faces = verts = 0
        return {"ok": True, "out_glb": out_glb, "faces": faces, "verts": verts,
                "peak_vram_gb": round(peak, 2), "quality": ptype,
                "texture_size": (16384 if up16 else int(texture_size))}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "error": f"{type(e).__name__}: {str(e)[:400]}"}


def main(argv: list[str]) -> int:
    import json
    if len(argv) < 2:
        print(json.dumps({"available": is_available(), "error": import_error(),
                          "usage": "aurora_trellis_wrapper.py <image> [out.glb]"}, indent=2))
        return 0
    image = argv[1]
    out = argv[2] if len(argv) > 2 else "trellis2_out.glb"
    r = generate_glb(image, out)
    # marqueur une-ligne pour parsing par le pipeline (subprocess)
    print("AURORA_TRELLIS_RESULT:" + json.dumps(r), flush=True)
    return 0 if r.get("ok") else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
