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

# Spill GPU->RAM (memoire managee cudaMallocManaged) : permet a l'extraction du mesh 1536
# de DEBORDER sur la RAM (30 Go) quand elle depasse les 16 Go de VRAM -> tient le VRAI 1536
# (petits reliefs: fentes, resistances, cheveux au mm). Lent (page-faults PCIe) mais complet.
# DOIT s'executer AVANT toute allocation CUDA du process. Opt-in via AURORA_TRELLIS2_MANAGED=1.
if os.environ.get("AURORA_TRELLIS2_MANAGED") == "1":
    try:
        import torch as _torch_boot
        _SO = os.environ.get("AURORA_MANAGED_SO", str(TRELLIS_ROOT / "managed_alloc.so"))
        _alloc = _torch_boot.cuda.memory.CUDAPluggableAllocator(_SO, "my_malloc", "my_free")
        _torch_boot.cuda.memory.change_current_allocator(_alloc)  # avant toute alloc CUDA
        log.warning("[trellis2] allocateur MANAGE actif (spill GPU->RAM, lent) : %s", _SO)
    except Exception as _e:  # noqa: BLE001
        log.error("[trellis2] echec allocateur manage: %r", _e)


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
    # Etape A (gratuit) : liberer les latents (shape_slat/tex_slat) AVANT fill_holes/CuMesh
    # (le pic OOM du 1536) -> rend ~1-3 Go juste avant l'extraction. Sur des monkeypatch de
    # decode_latent car le wrapper ne peut pas s'inserer dans run(). Sur (return_latent=False).
    try:
        import types as _types, torch as _t
        from trellis2.representations import MeshWithVoxel as _MWV

        def _decode_latent_lowmem(self, shape_slat, tex_slat, resolution):
            meshes, subs = self.decode_shape_slat(shape_slat, resolution)
            tex_voxels = self.decode_tex_slat(tex_slat, subs)
            del subs
            for _lat in (shape_slat, tex_slat):
                try:
                    _lat.feats = _t.empty(0, device=_lat.feats.device, dtype=_lat.feats.dtype)
                except Exception:  # noqa: BLE001
                    pass
            _t.cuda.empty_cache()
            out = []
            for m, v in zip(meshes, tex_voxels):
                m.fill_holes()
                out.append(_MWV(m.vertices, m.faces, origin=[-0.5, -0.5, -0.5],
                                voxel_size=1 / resolution, coords=v.coords[:, 1:], attrs=v.feats,
                                voxel_shape=_t.Size([*v.shape, *v.spatial_shape]),
                                layout=self.pbr_attr_layout))
            return out

        pipe.decode_latent = _types.MethodType(_decode_latent_lowmem, pipe)
        log.info("[trellis2] decode_latent low-mem patch actif")
    except Exception as _e:  # noqa: BLE001
        log.warning("[trellis2] patch decode_latent ignore: %r", _e)
    _PIPE_CACHE = pipe
    return pipe


# Qualite MAX par defaut : 1536_cascade = geometrie la plus fine (rayons/cables/cheveux fins
# mieux resolus, moins d'emmelement). Repli auto vers 1024_cascade/512 si OOM (l'utilisateur
# veut la precision max meme si plus lent). Options: 512, 1024, 1024_cascade, 1536_cascade.
QUALITY = os.environ.get("AURORA_TRELLIS2_QUALITY", "1536_cascade")
# Pas de diffusion (raffinement). Plus haut = plus precis, plus lent. Defaut TRELLIS ~12-25.
STEPS = int(os.environ.get("AURORA_TRELLIS2_STEPS", "30"))
# Echelle de repli sur OOM (garde la meilleure resolution qui tient reellement en VRAM).
_QUALITY_LADDER = ["1536_cascade", "1024_cascade", "1024", "512"]


def _auto_expose_glb_texture(glb_path: str, target_p50: float = 0.30, floor_p50: float = 0.16) -> bool:
    try:
        import numpy as np
        from PIL import Image
        Image.MAX_IMAGE_PIXELS = None
        import trimesh
        m = trimesh.load(glb_path, force="mesh", process=False)
        mat = getattr(m.visual, "material", None)
        img = getattr(mat, "baseColorTexture", None) if mat is not None else None
        if img is None:
            return False
        arr = np.asarray(img.convert("RGB"), dtype=np.float32) / 255.0
        lum = 0.2126 * arr[..., 0] + 0.7152 * arr[..., 1] + 0.0722 * arr[..., 2]
        p50 = float(np.percentile(lum, 50))
        if p50 >= floor_p50:
            return False
        gamma = np.log(max(target_p50, 1e-3)) / np.log(max(p50, 1e-3))
        gamma = float(np.clip(gamma, 0.45, 1.0))
        arr = np.power(arr, gamma)
        mat.baseColorTexture = Image.fromarray((np.clip(arr, 0, 1) * 255).astype(np.uint8))
        m.export(glb_path)
        return True
    except Exception:
        return False


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
                  pipeline_type: str | None = None, seed: int = 1,
                  extra_views: list | None = None) -> dict:
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
        run_input = image
        if extra_views:
            vs = []
            for _v in extra_views:
                try:
                    vs.append(Image.open(str(_v)).convert("RGB"))
                except Exception:
                    pass
            if vs:
                run_input = [image] + vs
        # Repli automatique sur OOM : essaie ptype puis les paliers plus bas (CuMesh/CUDA OOM).
        if ptype in _QUALITY_LADDER:
            _ladder = _QUALITY_LADDER[_QUALITY_LADDER.index(ptype):]
        else:
            _ladder = [ptype]
        mesh = None
        used_q = ptype
        for _q in _ladder:
            try:
                try:  # non supporte par l'allocateur pluggable (managed)
                    torch.cuda.reset_peak_memory_stats()
                except Exception:  # noqa: BLE001
                    pass
                torch.cuda.empty_cache()
                mesh = pipe.run(
                    run_input, seed=seed, pipeline_type=_q,
                    max_num_tokens=int(os.environ.get("AURORA_TRELLIS2_MAXTOK", "49152")),
                    sparse_structure_sampler_params={"steps": STEPS,
                        "guidance_strength": float(os.environ.get("AURORA_TRELLIS2_SS_CFG", "8.5"))},
                    shape_slat_sampler_params={"steps": STEPS},
                    tex_slat_sampler_params={"steps": STEPS},
                )[0]
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
        exposed = False
        if os.environ.get("AURORA_TEXTURE_AUTOEXPOSE", "1") == "1":
            exposed = _auto_expose_glb_texture(out_glb)
        try:
            peak = float(torch.cuda.max_memory_allocated() / 1e9)
        except Exception:  # noqa: BLE001  (allocateur pluggable managed)
            peak = 0.0
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
                "texture_size": (16384 if up16 else int(texture_size)),
                "auto_exposed": exposed}
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
    extras = [a for a in argv[3:] if os.path.isfile(a)]
    r = generate_glb(image, out, extra_views=extras or None)
    # marqueur une-ligne pour parsing par le pipeline (subprocess)
    print("AURORA_TRELLIS_RESULT:" + json.dumps(r), flush=True)
    return 0 if r.get("ok") else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
