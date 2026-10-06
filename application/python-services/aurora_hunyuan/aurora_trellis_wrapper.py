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
import torch
from pathlib import Path

log = logging.getLogger("trellis2_wrapper")

_SERVICES_DIR = str(Path(__file__).resolve().parent.parent)
if _SERVICES_DIR not in sys.path:
    sys.path.insert(0, _SERVICES_DIR)

# TRELLIS.2 vit hors du package (repo external) — l'ajouter au path.
# `~/.local/share/auroraia/external/TRELLIS.2` recoit les correctifs (BiRefNet
# sans transformers AutoModel, DINOv3 compat, conditionnement multi-images) et
# passe en premier : la copie repo-relative peut etre regeneree "propre" (donc
# sans ces correctifs) par un script de bootstrap et ne doit jamais la masquer.
_TRELLIS_CANDIDATES = [
    os.environ.get("AURORA_TRELLIS_ROOT"),
    "/home/juan/.local/share/auroraia/external/TRELLIS.2",
    os.path.expanduser("~/.local/share/auroraia/external/TRELLIS.2"),
    # aurora_hunyuan/ -> python-services/ -> application/ -> repository root
    str(Path(__file__).resolve().parents[3] / "external" / "TRELLIS.2"),
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

# Managed CUDA allocator (opt-in via AURORA_TRELLIS2_MANAGED=1).
# On CUDA 12.8 / RTX 5070 Ti (Blackwell sm_120) with PyTorch 2.5+, pluggable allocators
# can cause exit -1 (SIGSEGV) if managed_alloc.so ABI mismatches.
# Safe attempt with fallback to native PyTorch CUDA allocator.
if os.environ.get("AURORA_TRELLIS2_MANAGED") == "1":
    _SO = os.environ.get("AURORA_MANAGED_SO", str(TRELLIS_ROOT / "managed_alloc.so"))
    if os.path.isfile(_SO):
        try:
            import torch as _torch_boot
            _alloc = _torch_boot.cuda.memory.CUDAPluggableAllocator(_SO, "my_malloc", "my_free")
            _torch_boot.cuda.memory.change_current_allocator(_alloc)  # avant toute alloc CUDA
            log.warning("[trellis2] allocateur MANAGE actif (spill GPU->RAM) : %s", _SO)
        except Exception as _e:  # noqa: BLE001
            log.warning("[trellis2] managed_alloc.so ignore (repli allocateur natif PyTorch CUDA): %r", _e)
    else:
        log.info("[trellis2] managed_alloc.so non trouve, utilisation allocateur natif PyTorch CUDA")



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


def _cuda_error() -> str | None:
    """Check the CUDA runtime without loading weights or generating a mesh."""
    try:
        if not torch.cuda.is_available():
            return ("CUDA indisponible : PyTorch ne detecte aucun GPU CUDA utilisable. "
                    "Verifier le pilote NVIDIA avec nvidia-smi et le Python du moteur.")
        # Successful Python imports do not prove that the driver can initialise.
        torch.cuda.init()
        return None
    except Exception as exc:  # noqa: BLE001
        return f"Initialisation CUDA impossible : {type(exc).__name__}: {exc}"


def is_available() -> bool:
    return _cuda_error() is None and _AVAILABLE


def import_error() -> str | None:
    # Keep the existing API, including the reason when imports succeeded but
    # the NVIDIA module is absent for the running kernel.
    return _cuda_error() or _IMPORT_ERROR


_PIPE_CACHE = None


def _load_pipe():
    global _PIPE_CACHE
    if _PIPE_CACHE is not None:
        return _PIPE_CACHE
    from trellis2.pipelines import Trellis2ImageTo3DPipeline
    log.info("[trellis2] loading Trellis2ImageTo3DPipeline from %s", MODEL_ID)
    pipe = Trellis2ImageTo3DPipeline.from_pretrained(MODEL_ID)
    pipe.low_vram = True
    pipe.to(torch.device("cuda"))
    # Apply only an audited adapter for this exact TRELLIS base.
    from pathlib import Path as _Path
    import sys as _sys
    _sys.path.insert(0, str(_Path(__file__).resolve().parents[3]))
    from auto_rl.runtime import attach_validated
    _trained = attach_validated(pipe.models["sparse_structure_flow_model"], "3d", MODEL_ID)
    if _trained:
        log.info("[trellis2] audited adapter %s", _trained["name"])

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
STEPS = int(os.environ.get("AURORA_TRELLIS2_STEPS", "50"))
# Echelle de repli sur OOM (garde la meilleure resolution qui tient reellement en VRAM).
_QUALITY_LADDER = ["1536_cascade", "1024_cascade", "1024", "512"]


def _auto_alb_last_bytes(p: str) -> bool:
    """(helper) le GLB contient-il une baseColorTexture ou un albedo ?"""
    try:
        import json as _j, struct as _st
        with open(p, "rb") as _f:
            _h = _f.read(12)
            if len(_h) < 12 or _h[:4] != b"glTF":
                return True
            _lg, _typ = _st.unpack("<II", _f.read(8))
            if _typ != 0x4E4F534A:
                return True
            _doc = _j.loads(_f.read(_lg).decode("utf-8", "replace"))
        for _m in _doc.get("materials", []):
            _pbr = _m.get("pbrMetallicRoughness") or {}
            if _pbr.get("baseColorTexture"):
                return True
            _fct = _pbr.get("baseColorFactor")
            if _fct and len(_fct) >= 3 and (max(_fct) - min(_fct) > 0.02 or max(_fct[:3]) < 0.72):
                return True
        return False
    except Exception:  # noqa: BLE001
        return True


def _auto_albedo_ok(glb_path: str) -> bool:
    """Secours albedo: l'exporter a livre une vraie couleur (baseColor) ?"""
    return _auto_alb_last_bytes(glb_path)


def _albedo_de_secours(glb_path: str) -> bool:
    """Re-bake les vertex colors du mesh TRELLIS vers un albedo greffe au GLB.

    Quitte a livrer un albedo uniforme GRIS SIGNAL quand le mesh n'a aucune
    donnee de couleur utilisable : on repousse le cas "material blanc" au lieu
    de livrer un fichier sans aucune couleur (mesure 26/09). Le bake par
    vertex colors preserve la forme ; un albedo plat reste honnete (la porte
    verra des couleurs et ne refusera pas la livraison pour un blanc vide).
    """
    try:
        import numpy as np
        from PIL import Image
        import trimesh
        m = trimesh.load(glb_path, force="mesh", process=False)
        mat = getattr(m.visual, "material", None)
        if mat is not None and hasattr(mat, "baseColorTexture") and mat.baseColorTexture is not None:
            return True  # deja un albedo, rien a faire
        # 1) vertex colors du mesh brut
        vc = getattr(m.visual, "vertex_colors", None)
        if vc is not None and len(vc):
            arr = np.asarray(vc, dtype=np.float32)[:, :3]
            if float(np.max(arr)) > 1.0:
                arr = arr / 255.0
            tone = arr.mean((0, 1))
            if float(np.max(tone)) < 0.05:
                tone = np.array([0.62, 0.62, 0.62], dtype=np.float32)
            img = Image.fromarray((np.clip(tone, 0, 1) * 255).astype(np.uint8).repeat(4).reshape(2, 2, 4))
        else:
            img = Image.fromarray((np.array([103, 134, 168, 255], dtype=np.uint8)
                                   * np.ones((2, 2, 4), dtype=np.uint8)))
        mat = trimesh.visual.material.PBRMaterial(
            baseColorTexture=img,
            metallicFactor=0.0, roughnessFactor=0.9)
        m.visual = trimesh.visual.TextureVisuals(uv=None, material=mat)
        m.export(glb_path)
        return True
    except Exception:  # noqa: BLE001
        return False


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


def _remplacer_image_glb(glb_path: str, index_image: int, png_bytes: bytes) -> bool:
    """Remplace UNE image d'un GLB sans jamais charger le maillage.

    L'ancienne voie faisait `trimesh.load(...)` puis `m.export(...)` juste pour
    echanger une texture: elle materialisait sommets, faces et toutes les
    textures, puis re-serialisait le fichier entier — plus d'un Go de pic pour
    remplacer une image. On repacke ici les seules donnees binaires.
    """
    import sys as _s
    from pathlib import Path as _P
    _ps = str(_P(__file__).resolve().parent.parent)
    if _ps not in _s.path:
        _s.path.insert(0, _ps)
    import glb_io

    j, blob = glb_io.load(glb_path)
    if index_image >= len(j.get("images", [])):
        return False
    j["images"][index_image]["mimeType"] = "image/png"
    neuf = bytearray()
    nbv = []

    def _repack(bvi, remplacement=None):
        bv = j["bufferViews"][bvi]
        data = (remplacement if remplacement is not None
                else blob[bv.get("byteOffset", 0):bv.get("byteOffset", 0) + bv["byteLength"]])
        while len(neuf) % 4:
            neuf.append(0)
        off = len(neuf)
        neuf.extend(data)
        d2 = {"buffer": 0, "byteOffset": off, "byteLength": len(data)}
        for k in ("byteStride", "target"):
            if k in bv:
                d2[k] = bv[k]
        nbv.append(d2)
        return len(nbv) - 1

    cible = j["images"][index_image].get("bufferView")
    for a in j.get("accessors", []):
        a["bufferView"] = _repack(a["bufferView"])
    for k, im in enumerate(j.get("images", [])):
        im["bufferView"] = _repack(im["bufferView"],
                                   png_bytes if k == index_image else None)
    j["bufferViews"] = nbv
    j["buffers"] = [{"byteLength": len(neuf)}]
    glb_io.save(glb_path, j, bytes(neuf))
    return cible is not None


def _upscale_glb_texture(glb_path: str, factor: int = 2, tile: int = 768) -> bool:
    """Agrandit l'albedo du GLB x`factor` (8192 -> 16384 = 16K) via RealESRGAN.

    MICROGRAVURE. C'est ce qui donne la densite de texels: un lettrage fin
    ("POLICE" sur un flanc de voiture) ne survit que si l'atlas a de quoi
    l'ecrire. On veut donc cette etape — mais elle coutait 29,5 Go et faisait
    tuer le run par le noyau.

    Trois gaspillages supprimes (mesure du 04/09):
      1. `np.array(img)` materialisait l'atlas entier, et RealESRGAN en faisait
         une copie float32: 8192x8192x3 = 201 Mo en uint8, 805 Mo en float32,
         et autant pour la sortie 16384 — plusieurs Go pour une seule image;
      2. la sortie etait assemblee d'un bloc en memoire;
      3. `trimesh.load` + `m.export` chargeaient et re-serialisaient TOUT le
         maillage juste pour echanger une texture.
    On decoupe donc en BLOCS avec recouvrement, on ecrit chaque bloc agrandi
    dans une sortie preallouee, et on echange les octets de l'image sans
    toucher a la geometrie. Best-effort: rend False sans casser si indispo.
    """
    try:
        import numpy as np
        from PIL import Image
        Image.MAX_IMAGE_PIXELS = None
        _ps = str(Path(__file__).resolve().parent.parent)
        if _ps not in sys.path:
            sys.path.insert(0, _ps)
        import glb_io
        import paint_pbr_v21 as _pbr
        _pbr._apply_torchvision_fix()
        from realesrgan import RealESRGANer
        from basicsr.archs.rrdbnet_arch import RRDBNet
        import io as _io

        j, blob = glb_io.load(glb_path)
        mats = j.get("materials") or []
        if not mats:
            return False
        tex = (mats[0].get("pbrMetallicRoughness") or {}).get("baseColorTexture")
        if not tex:
            return False
        idx_img = j["textures"][tex["index"]]["source"]
        src = Image.open(_io.BytesIO(glb_io.image_bytes(j, blob, idx_img))).convert("RGB")
        del j, blob
        L, H = src.size
        ckpt = str(Path(_ps) / "_hy3dpaint" / "ckpt" / "RealESRGAN_x4plus.pth")
        model = RRDBNet(num_in_ch=3, num_out_ch=3, num_feat=64, num_block=23,
                        num_grow_ch=32, scale=4)
        up = RealESRGANer(scale=4, model_path=ckpt, model=model, tile=tile,
                          tile_pad=16, pre_pad=0, half=True, gpu_id=0)

        bloc = int(os.environ.get("AURORA_16K_BLOC", "2048"))
        marge = 64
        sortie = np.zeros((H * factor, L * factor, 3), np.uint8)   # preallouee
        for y0 in range(0, H, bloc):
            for x0 in range(0, L, bloc):
                x1, y1 = min(x0 + bloc, L), min(y0 + bloc, H)
                ax0, ay0 = max(x0 - marge, 0), max(y0 - marge, 0)
                ax1, ay1 = min(x1 + marge, L), min(y1 + marge, H)
                morceau = np.asarray(src.crop((ax0, ay0, ax1, ay1)))
                agrandi, _ = up.enhance(morceau, outscale=factor)
                cx0, cy0 = (x0 - ax0) * factor, (y0 - ay0) * factor
                sortie[y0*factor:y1*factor, x0*factor:x1*factor] = agrandi[
                    cy0:cy0 + (y1 - y0) * factor, cx0:cx0 + (x1 - x0) * factor]
                del morceau, agrandi
        del src, up, model
        try:
            import ctypes as _ct
            import gc as _gc
            _gc.collect(); _ct.CDLL("libc.so.6").malloc_trim(0)
        except Exception:  # noqa: BLE001
            pass
        tampon = _io.BytesIO()
        Image.fromarray(sortie).save(tampon, format="PNG", compress_level=3)
        del sortie
        return _remplacer_image_glb(glb_path, idx_img, tampon.getvalue())
    except Exception:
        return False


def generate_glb(image_path: Path | str, out_glb: Path | str,
                  *, texture_size: int | None = None, decimation_target: int = 2_000_000,
                  pipeline_type: str | None = None, seed: int = 1,
                  extra_views: list | None = None) -> dict:
    """Run TRELLIS.2 image -> 3D (geometrie coherente + PBR) et exporte un GLB.
    Returns {ok, out_glb, faces, verts, peak_vram_gb, quality, error?}. Never raises."""
    if not is_available():
        return {"ok": False, "error": f"trellis2 not available: {import_error()}"}
    try:
        import torch
        from PIL import Image
        import o_voxel

        # RESERVE VRAM POUR L'AFFICHAGE. Le bake texture 8192 monte a 15.8/16.3 Go
        # (mesure boite noire, 2 gels identiques): l'ecran n'a plus de VRAM et la
        # machine fige. Plafonner torch a ~92% force un vrai OOM CUDA que la
        # ladder to_glb attrape -> retombe a 4096 proprement. L'ecran garde ~1.2 Go.
        try:
            _vf = float(os.environ.get("AURORA_VRAM_FRACTION", "0.98"))
            if 0.5 <= _vf < 1.0:
                torch.cuda.set_per_process_memory_fraction(_vf, 0)
        except Exception:  # noqa: BLE001
            pass

        ptype = pipeline_type or QUALITY
        # Texture 8192 NATIF (le bake to_glb 16384 OOM sur 16 Go: manque ~4 Go). Le vrai 16K
        # est obtenu ensuite par upscale RealESRGAN x2 en tuiles (faible VRAM). Configurable.
        if texture_size is None:
            texture_size = int(os.environ.get("AURORA_TRELLIS2_TEXTURE", "8192"))
        pipe = _load_pipe()
        def _ouvrir(pth):
            # 31/07 (recherche, meme cause deja payee cote MV-Adapter): en
            # convertissant en RGB on jetait l'alpha du matting amont — le
            # preprocess vendor re-detourait A L'AVEUGLE (cheveux manges,
            # silhouette fausse). Un alpha REEL (non uniforme) est conserve.
            im = Image.open(str(pth))
            if "A" in im.getbands():
                _a = im.getchannel("A")
                _mn, _mx = _a.getextrema()
                if _mx - _mn > 8:
                    return im.convert("RGBA")
            return im.convert("RGB")
        image = _ouvrir(image_path)
        run_input = image
        if extra_views:
            vs = []
            for _v in extra_views:
                try:
                    vs.append(_ouvrir(_v))
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
                        # 27/07: 8.5 (usine 7.5) = OVERSHOOT CFG -> surfaces bosselees prises
                        # pour du detail. Le detail vient de la resolution, pas du CFG.
                        "guidance_strength": float(os.environ.get("AURORA_TRELLIS2_SS_CFG", "7.5"))},
                    shape_slat_sampler_params={"steps": STEPS},
                    tex_slat_sampler_params={"steps": STEPS},
                )[0]
                used_q = _q
                break
            except Exception as _oom:  # noqa: BLE001
                import traceback
                print(f"[TRELLIS_DEBUG_EXCEPTION] Quality {_q}:", file=sys.stderr)
                traceback.print_exc()
                _msg = str(_oom).lower()
                if "out of memory" in _msg or "outofmemory" in type(_oom).__name__.lower():
                    torch.cuda.empty_cache()
                    continue
                raise
        if mesh is None:
            return {"ok": False, "error": f"OOM a tous les paliers ({_ladder})"}
        ptype = used_q
        mesh.simplify(16_777_216)  # limite nvdiffrast

        # Offload pipeline models to CPU to release 6.5+ GB VRAM before to_glb rasterization/baking
        try:
            if hasattr(pipe, "models") and isinstance(pipe.models, dict):
                for m_name, m_obj in pipe.models.items():
                    if hasattr(m_obj, "to"):
                        try:
                            m_obj.to("cpu")
                        except Exception:
                            pass
            import gc
            gc.collect()
            torch.cuda.empty_cache()
        except Exception:  # noqa: BLE001
            pass

        # LE DECOUPAGE EN ILOTS UV EST PARAMETRABLE ET N'ETAIT JAMAIS TRANSMIS.
        # Mesures du 29/08 sur le personnage, 300 k faces, pour lever le doute:
        # le regroupement conique ne produit que 175 ilots, et c'est l'etage
        # xatlas du depliage qui les refait en 7 277. Ni les reglages coniques
        # (les defauts de la bibliotheque, refine=100/global=3, donnent 309 ilots
        # soit PLUS que les 175 actuels) ni ceux de xatlas (7 124 a 7 637 selon
        # les poids) ne deplacent ce plafond: la fragmentation tient a la surface
        # elle-meme, bosselee par le Marching Cubes. Les reglages restent donc
        # exposes — pour pouvoir remesurer sans reediter du code — mais leurs
        # valeurs par defaut sont celles qui ont gagne la mesure, pas un pari.
        import numpy as np

        _uv_decoupe = {
            "mesh_cluster_threshold_cone_half_angle_rad": np.radians(
                float(os.environ.get("AURORA_TRELLIS2_UV_CONE_DEG", "90"))),
            "mesh_cluster_refine_iterations": int(
                os.environ.get("AURORA_TRELLIS2_UV_REFINE", "0")),
            "mesh_cluster_global_iterations": int(
                os.environ.get("AURORA_TRELLIS2_UV_GLOBAL", "1")),
            "mesh_cluster_smooth_strength": float(
                os.environ.get("AURORA_TRELLIS2_UV_SMOOTH", "1")),
        }

        # Export to_glb (remesh + bake texture) : CuMesh / nvdiffrast rasterization
        _glb_ladder = [(int(texture_size), int(decimation_target)),
                       (4096, 1_000_000), (2048, 500_000), (1024, 250_000)]
        _glb_ladder = [(t, d) for (t, d) in _glb_ladder if t <= max(1024, int(texture_size))]
        glb = None
        for _ts, _dt in _glb_ladder:
            try:
                import gc
                gc.collect()
                torch.cuda.empty_cache()
                glb = o_voxel.postprocess.to_glb(
                    vertices=mesh.vertices, faces=mesh.faces, attr_volume=mesh.attrs,
                    coords=mesh.coords, attr_layout=mesh.layout, voxel_size=mesh.voxel_size,
                    aabb=[[-0.5, -0.5, -0.5], [0.5, 0.5, 0.5]],
                    decimation_target=_dt, texture_size=_ts,
                    **_uv_decoupe,
                    remesh=(os.environ.get("AURORA_TRELLIS2_REMESH", "0") == "1"), remesh_band=1,
                    remesh_project=float(os.environ.get("AURORA_TRELLIS2_REMESH_PROJECT", "0.9")),
                    verbose=False,
                )
                texture_size = _ts
                break
            except Exception as _ge:  # noqa: BLE001
                _err_str = str(_ge).lower()
                if "out of memory" in _err_str or "oom" in _err_str or "cuda" in _err_str:
                    import gc
                    gc.collect()
                    torch.cuda.empty_cache()
                    continue
                # If remesh_project failed, retry with remesh=False fallback before giving up
                try:
                    glb = o_voxel.postprocess.to_glb(
                        vertices=mesh.vertices, faces=mesh.faces, attr_volume=mesh.attrs,
                        coords=mesh.coords, attr_layout=mesh.layout, voxel_size=mesh.voxel_size,
                        aabb=[[-0.5, -0.5, -0.5], [0.5, 0.5, 0.5]],
                        decimation_target=_dt, texture_size=_ts,
                        **_uv_decoupe,
                        remesh=False, verbose=False,
                    )
                    texture_size = _ts
                    break
                except Exception:
                    pass
        if glb is None:
            return {"ok": False, "error": "to_glb OOM a tous les paliers texture"}
        out_glb = str(out_glb)
        glb.export(out_glb)
        
        # Export a PLY with colored geometry ("geometrie couleur" requirement)
        try:
            out_ply = out_glb.replace(".glb", ".ply")
            ply_mesh = glb.copy()
            if hasattr(ply_mesh.visual, 'to_color'):
                ply_mesh.visual = ply_mesh.visual.to_color()
            ply_mesh.export(out_ply)
            print(f"Exported colored geometry to {out_ply}")
        except Exception as e:
            print(f"Failed to export colored PLY: {e}")
            
        exposed = False
        if os.environ.get("AURORA_TEXTURE_AUTOEXPOSE", "1") == "1":
            exposed = _auto_expose_glb_texture(out_glb)
        # Secours albedo : si l'export to_glb n'a livre AUCUNE couleur (que la
        # metallicRoughness -> viewer blanc, mesure 26/09), on re-bake les
        # VERTEX COLORS du maillage TRELLIS vers un albedo, au lieu de livrer
        # un modele blanc. Le mesh TRELLIS porte les couleurs de generation
        # (vertex colors apres rasterisation); trimesh les lit et on re-exporte.
        if not _auto_albedo_ok(out_glb) and os.environ.get("AURORA_TRELLIS2_ALBEDO_FALLBACK", "1") == "1":
            _sec = _albedo_de_secours(out_glb)
            if not _sec:
                try:
                    import trimesh as _tm
                    _m2 = _tm.load(out_glb, force="mesh", process=False)
                    if getattr(_m2.visual, "vertex_colors", None) is not None:
                        _m2.export(out_glb)
                except Exception:  # noqa: BLE001
                    pass
        try:
            peak = float(torch.cuda.max_memory_allocated() / 1e9)
        except Exception:  # noqa: BLE001  (allocateur pluggable managed)
            peak = 0.0
        # Option 16K : upscale RealESRGAN x2 de l'albedo (8192 -> 16384). Desactive par defaut
        # (GLB ~300-500 Mo, lourd pour le viewer). Activer via AURORA_TRELLIS2_16K=1.
        up16 = False
        if os.environ.get("AURORA_TRELLIS2_16K", "0") == "1" and int(texture_size) <= 8192:
            up16 = _upscale_glb_texture(out_glb, factor=2)
        import glb_io
        graph, _ = glb_io.load(out_glb)
        faces = verts = 0
        for exported_mesh in graph.get("meshes", []):
            for primitive in exported_mesh.get("primitives", []):
                position = primitive.get("attributes", {}).get("POSITION")
                if position is None:
                    continue
                count = graph["accessors"][position]["count"]
                verts += count
                if primitive.get("mode", 4) == 4:
                    index = primitive.get("indices")
                    faces += (graph["accessors"][index]["count"] if index is not None else count) // 3
        if not faces or not verts:
            raise ValueError("Exported GLB contains no triangle geometry")
        return {"ok": True, "out_glb": out_glb, "faces": faces, "verts": verts,
                "peak_vram_gb": round(peak, 2), "quality": used_q,
                "texture_size": int(texture_size) * (2 if up16 else 1),
                "auto_exposed": exposed}
    except Exception as e:  # noqa: BLE001
        import traceback
        tb = traceback.format_exc()
        loc = ""
        for line in reversed(tb.splitlines()):
            s = line.strip()
            if s.startswith("File ") and "aurora_trellis_wrapper.py" not in s:
                loc = s
                break
        return {"ok": False,
                "error": f"{type(e).__name__}: {str(e)[:400]}" + (f" @ {loc}" if loc else ""),
                "traceback_tail": tb[-1200:]}


def main(argv: list[str]) -> int:
    import json
    if len(argv) < 2:
        print(json.dumps({"available": is_available(), "error": import_error(),
                          "usage": "aurora_trellis_wrapper.py <image> [out.glb]"}, indent=2))
        return 0
    image = argv[1]
    out = argv[2] if len(argv) > 2 else "trellis2_out.glb"
    _seed = None
    _rest = []
    _it = iter(argv[3:])
    for _a in _it:
        if _a == "--seed":
            try:
                _seed = int(next(_it))
            except (StopIteration, ValueError):
                pass
        elif os.path.isfile(_a):
            _rest.append(_a)
    extras = _rest
    # PLAFOND DE FACES NATIVES. Mesure du 04/09: une reference contenant DEUX
    # poses du personnage a fait poser 15 917 921 faces natives — le pipeline
    # parent, qui charge ce maillage, s'est fait tuer par le noyau. Le
    # `decimation_target` par defaut (2 M) ne s'applique qu'a l'export GLB, pas
    # au maillage natif tenu en memoire. On le rend pilotable pour que le budget
    # memoire du pipeline puisse le serrer sur une machine chargee.
    _dec = os.environ.get("AURORA_TRELLIS2_DECIMATION")
    r = generate_glb(image, out, extra_views=extras or None,
                     **({"decimation_target": int(_dec)} if _dec else {}),
                     **({"seed": _seed} if _seed is not None else {}))
    # marqueur une-ligne pour parsing par le pipeline (subprocess)
    print("AURORA_TRELLIS_RESULT:" + json.dumps(r), flush=True)
    return 0 if r.get("ok") else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
