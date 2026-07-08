"""
AuroraIA - Hunyuan3D mesh generation
Usage: python hunyuan3d_run.py --image <path> --output-dir <dir> --run-id <id> --format glb|obj
"""

import argparse
import gc
import importlib.util
import json
import os
import re
import subprocess
import sys
import threading
from typing import Any

# v83-3dloop : sur Windows, stdout est en cp1252 -> les PROGRESS contenant des
# caracteres non-latin1 (fleche U+2192, etc.) faisaient crasher le thread
# read_worker_stream (UnicodeEncodeError dans print(line, flush=True)), ce qui
# faisait croire que le worker etait mort -> retry en boucle -> jamais de texture.
# On force stdout/stderr en utf-8 errors=replace.
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]
    except Exception:
        pass

from cache_paths import configure_ml_cache_environment


SHAPE_MODEL_ID = "tencent/Hunyuan3D-2.1"
SHAPE_SUBFOLDER = "hunyuan3d-dit-v2-1"
SHAPE_MULTIVIEW_MODEL_ID = "tencent/Hunyuan3D-2mv"
SHAPE_MULTIVIEW_SUBFOLDER = "hunyuan3d-dit-v2-mv"
SHAPE_FALLBACK_MODEL_ID = "tencent/Hunyuan3D-2"
SHAPE_FALLBACK_SUBFOLDER = "hunyuan3d-dit-v2-0"
TEXTURE_MODEL_ID = "tencent/Hunyuan3D-2"
HY3DGEN_INTERNAL_SUBFOLDER = "hunyuan3d-dit-v2-0"

REQUIRED_PACKAGES = {
    "torch": "torch",
    "PIL": "Pillow",
    "numpy": "numpy",
    "trimesh": "trimesh",
    "yaml": "PyYAML",
    "pymeshlab": "pymeshlab",
    "pygltflib": "pygltflib",
    "einops": "einops",
    "omegaconf": "omegaconf",
    "hy3dgen": "hy3dgen",
    "rembg": "rembg",
    "diffusers": "diffusers",
    "transformers": "transformers",
    "accelerate": "accelerate",
    "safetensors": "safetensors",
    "huggingface_hub": "huggingface_hub",
}

TRANSIENT_SHAPE_ERROR_PATTERNS = [
    re.compile(pattern, re.IGNORECASE)
    for pattern in [
        r"out of memory",
        r"cuda",
        r"cudnn",
        r"allocate",
        r"allow_in_graph",
        r"torch\._dynamo",
        r"components",
    ]
]

WORKER_NATIVE_CRASH_EXIT_CODES = {-1073741819, 3221225477}
WORKER_JSON_LINE_RE = re.compile(r"^\s*\{[\s\S]*\}\s*$")
WORKER_RETRYABLE_ERROR_PATTERNS = [
    re.compile(pattern, re.IGNORECASE)
    for pattern in [
        r"allow_in_graph",
        r"torch\._dynamo",
        r"access violation",
        r"c0000005",
        r"segmentation",
        r"out of memory",
        r"cuda",
        r"cudnn",
        r"components",
    ]
]


def emit(stage: str, detail: str):
    print(f"PROGRESS:{stage}:{detail}", flush=True)


def configure_runtime_environment() -> None:
    configure_ml_cache_environment()
    os.environ.setdefault("PYTHONUTF8", "1")
    os.environ.setdefault("HF_HUB_DISABLE_PROGRESS_BARS", "1")
    os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")
    os.environ.setdefault("TORCHDYNAMO_DISABLE", "1")


def ensure_dependencies():
    missing = []
    for import_name, pip_name in REQUIRED_PACKAGES.items():
        try:
            __import__(import_name)
        except Exception:
            missing.append(pip_name)

    if missing:
        emit("install", f"Installation automatique de {', '.join(missing)}...")
        subprocess.check_call(
            [sys.executable, "-m", "pip", "install", "--quiet"] + missing,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
        )
        emit("install", "Dependances 3D installees.")


def empty_cuda_cache():
    try:
        import torch

        if torch.cuda.is_available():
            torch.cuda.empty_cache()
    except Exception:
        pass
    gc.collect()


def ensure_hf_snapshot(repo_id: str, allow_patterns: list[str] | None = None) -> str:
    from huggingface_hub import snapshot_download

    cache_dir = os.environ.get("HF_HUB_CACHE")
    emit("asset_scan", f"Verification locale de {repo_id}...")
    try:
        return snapshot_download(
            repo_id=repo_id,
            allow_patterns=allow_patterns or None,
            local_files_only=True,
            cache_dir=cache_dir,
        )
    except Exception:
        emit("asset_download", f"Telechargement de {repo_id}...")
        return snapshot_download(
            repo_id=repo_id,
            allow_patterns=allow_patterns or None,
            cache_dir=cache_dir,
        )


def find_weight_file(model_dir: str) -> dict[str, Any] | None:
    import glob

    if not os.path.isdir(model_dir):
        return None

    if glob.glob(os.path.join(model_dir, "*.safetensors.index.json")):
        return {"use_safetensors": True, "variant": None, "weight_format": "safetensors"}
    if glob.glob(os.path.join(model_dir, "model-*-of-*.safetensors")):
        return {"use_safetensors": True, "variant": None, "weight_format": "safetensors"}
    if os.path.exists(os.path.join(model_dir, "model.fp16.safetensors")):
        return {"use_safetensors": True, "variant": "fp16", "weight_format": "safetensors"}
    if os.path.exists(os.path.join(model_dir, "model.safetensors")):
        return {"use_safetensors": True, "variant": None, "weight_format": "safetensors"}
    if os.path.exists(os.path.join(model_dir, "model.fp16.ckpt")):
        return {"use_safetensors": False, "variant": "fp16", "weight_format": "ckpt"}
    if os.path.exists(os.path.join(model_dir, "model.ckpt")):
        return {"use_safetensors": False, "variant": None, "weight_format": "ckpt"}

    any_safetensors = glob.glob(os.path.join(model_dir, "*.safetensors"))
    if any_safetensors:
        return {"use_safetensors": True, "variant": None, "weight_format": "safetensors"}

    return None


def read_config_text(snapshot_path: str, subfolder: str) -> str:
    for filename in ("config.yaml", "config.yml"):
        config_path = os.path.join(snapshot_path, subfolder, filename)
        if os.path.exists(config_path):
            with open(config_path, "r", encoding="utf-8", errors="ignore") as handle:
                return handle.read()
    return ""


def detect_config_namespace(snapshot_path: str, subfolder: str) -> str:
    config_text = read_config_text(snapshot_path, subfolder)
    if "hy3dshape." in config_text:
        return "hy3dshape"
    if "hy3dgen.shapegen" in config_text:
        return "hy3dgen"
    return "unknown"


def evaluate_shape_runtime(snapshot_path: str, subfolder: str) -> dict[str, Any]:
    namespace = detect_config_namespace(snapshot_path, subfolder)

    if namespace == "hy3dshape":
        return {
            "supported": False,
            "runtime": namespace,
            "reason": (
                "snapshot 2.1 detecte (namespace hy3dshape) mais le runner actif utilise la pile hy3dgen 2.0; "
                "fallback automatique vers le snapshot shape compatible."
            ),
        }

    if importlib.util.find_spec("hy3dgen") is None:
        return {
            "supported": False,
            "runtime": "missing",
            "reason": "package hy3dgen absent dans ce runtime Python.",
        }

    return {
        "supported": True,
        "runtime": "hy3dgen",
        "reason": "",
    }


def ensure_shape_compat(snapshot_path: str, actual_subfolder: str) -> None:
    src_dir = os.path.join(snapshot_path, actual_subfolder)
    dst_dir = os.path.join(snapshot_path, HY3DGEN_INTERNAL_SUBFOLDER)

    if actual_subfolder == HY3DGEN_INTERNAL_SUBFOLDER:
        _ensure_fp16_weight(src_dir)
        return

    if os.path.isdir(dst_dir) and any(
        filename.endswith(".safetensors") or filename.endswith(".ckpt")
        for filename in os.listdir(dst_dir)
    ):
        _ensure_fp16_weight(dst_dir)
        return

    os.makedirs(dst_dir, exist_ok=True)
    if not os.path.isdir(src_dir):
        return

    for filename in os.listdir(src_dir):
        src_file = os.path.join(src_dir, filename)
        dst_file = os.path.join(dst_dir, filename)
        if os.path.isfile(src_file) and not os.path.exists(dst_file):
            try:
                os.link(src_file, dst_file)
            except Exception:
                import shutil

                shutil.copy2(src_file, dst_file)

    _ensure_fp16_weight(dst_dir)


def _ensure_fp16_weight(model_dir: str) -> None:
    fp16 = os.path.join(model_dir, "model.fp16.safetensors")
    generic = os.path.join(model_dir, "model.safetensors")
    if not os.path.exists(fp16) and os.path.exists(generic):
        try:
            os.link(generic, fp16)
        except Exception:
            import shutil

            shutil.copy2(generic, fp16)


def resolve_shape_candidate(request_multiview: bool) -> dict[str, Any]:
    candidates = []
    if request_multiview:
        candidates.append(
            {
                "repo_id": SHAPE_MULTIVIEW_MODEL_ID,
                "subfolder": SHAPE_MULTIVIEW_SUBFOLDER,
                "load_subfolder": SHAPE_MULTIVIEW_SUBFOLDER,
                "input_mode": "multiview",
                "bridge_compat": False,
            }
        )

    candidates.extend(
        [
            {
                "repo_id": SHAPE_MODEL_ID,
                "subfolder": SHAPE_SUBFOLDER,
                "load_subfolder": HY3DGEN_INTERNAL_SUBFOLDER,
                "input_mode": "single_view",
                "bridge_compat": True,
            },
            {
                "repo_id": SHAPE_FALLBACK_MODEL_ID,
                "subfolder": SHAPE_FALLBACK_SUBFOLDER,
                "load_subfolder": HY3DGEN_INTERNAL_SUBFOLDER,
                "input_mode": "single_view",
                "bridge_compat": True,
            },
        ]
    )

    failures: list[str] = []

    for candidate in candidates:
        snapshot_path = ensure_hf_snapshot(
            candidate["repo_id"],
            allow_patterns=[f"{candidate['subfolder']}/*"],
        )
        model_dir = os.path.join(snapshot_path, candidate["subfolder"])
        weight_info = find_weight_file(model_dir)

        if weight_info is None:
            failures.append(
                f"{candidate['repo_id']}/{candidate['subfolder']} "
                f"(repertoire: {model_dir!r} - aucun poids exploitable detecte)"
            )
            continue

        runtime_check = evaluate_shape_runtime(snapshot_path, candidate["subfolder"])
        if not runtime_check["supported"]:
            emit(
                "shape_fallback",
                f"{candidate['repo_id']}/{candidate['subfolder']} ignore: {runtime_check['reason']}",
            )
            failures.append(
                f"{candidate['repo_id']}/{candidate['subfolder']} "
                f"(poids detectes mais runtime incompatible: {runtime_check['reason']})"
            )
            continue

        if candidate["bridge_compat"]:
            ensure_shape_compat(snapshot_path, candidate["subfolder"])
        return {
            **candidate,
            "model_path": snapshot_path,
            "shape_runtime": runtime_check["runtime"],
            "compatibility_reason": runtime_check["reason"],
            **weight_info,
        }

    raise FileNotFoundError("Aucun poids shape Hunyuan exploitable n a ete trouve. " + " | ".join(failures))


def ensure_texture_assets() -> str:
    return ensure_hf_snapshot(
        TEXTURE_MODEL_ID,
        allow_patterns=[
            "hunyuan3d-delight-v2-0/*",
            "hunyuan3d-paint-v2-0/*",
            "hunyuan3d-dit-v2-0/*",
        ],
    )


def safe_enable_model_cpu_offload(pipeline, label: str, device: str, allow_offload: bool = True) -> bool:
    if not allow_offload:
        emit("offload_skip", f"{label}: offload desactive par la strategie de recuperation.")
        return False
    if device != "cuda":
        return False
    if not hasattr(pipeline, "enable_model_cpu_offload"):
        emit("offload_skip", f"{label}: offload indisponible sur ce pipeline.")
        return False
    if not hasattr(pipeline, "components"):
        emit("offload_skip", f"{label}: offload ignore car le pipeline n expose pas components.")
        return False

    try:
        pipeline.enable_model_cpu_offload()
        emit("offload", f"{label}: offload CPU actif.")
        return True
    except Exception as offload_error:
        emit("offload_skip", f"{label}: offload ignore ({offload_error})")
        return False


def should_retry_shape(error: Exception) -> bool:
    message = str(error)
    return any(pattern.search(message) for pattern in TRANSIENT_SHAPE_ERROR_PATTERNS)


def build_shape_strategies(
    intent_purpose: str,
    motion_readiness: str,
    dimensional_precision: bool,
    multiview: bool,
    preferred_label: str = "maximum_quality",
):
    # Maximized quality parameters — precision and fidelity over speed
    base_octree = 512 if dimensional_precision else 448 if motion_readiness in {"rig_candidate", "articulated"} else 384
    base_chunks = 12000 if dimensional_precision else 10000
    base_steps = 64 if dimensional_precision else 56

    if intent_purpose == "character":
        # Characters need maximum resolution to avoid blobby/cartoony output
        base_octree = max(base_octree, 512)
        base_steps = max(base_steps, 70)
        base_chunks = max(base_chunks, 12000)
    if intent_purpose == "game_asset":
        base_steps = max(48, base_steps)
    if multiview:
        base_octree = max(base_octree, 448)
        base_steps += 6
        base_chunks = max(base_chunks, 11000)

    strategies = [
        {
            "label": "maximum_quality",
            "kwargs": {
                "num_inference_steps": base_steps,
                "octree_resolution": base_octree,
                "num_chunks": base_chunks,
                "enable_pbar": False,
            },
        },
        {
            "label": "balanced",
            "kwargs": {
                "num_inference_steps": max(42, base_steps - 10),
                "octree_resolution": max(384, base_octree - 64),
                "num_chunks": max(8000, base_chunks - 2000),
                "enable_pbar": False,
            },
        },
        {
            "label": "memory_safe",
            "kwargs": {
                "num_inference_steps": max(34, base_steps - 18),
                "octree_resolution": max(320, base_octree - 128),
                "num_chunks": max(6000, base_chunks - 4000),
                "enable_pbar": False,
            },
        },
        {
            "label": "stability_fallback",
            "kwargs": {
                "num_inference_steps": 30,
                "octree_resolution": 256,
                "num_chunks": 4000,
                "enable_pbar": False,
            },
        },
    ]

    strategy_orders = {
        "maximum_quality": ["maximum_quality", "balanced", "memory_safe", "stability_fallback"],
        "balanced": ["balanced", "memory_safe", "stability_fallback"],
        "memory_safe": ["memory_safe", "stability_fallback"],
        "stability_fallback": ["stability_fallback"],
    }
    label_to_strategy = {strategy["label"]: strategy for strategy in strategies}
    ordered_labels = strategy_orders.get(preferred_label, strategy_orders["maximum_quality"])
    return [label_to_strategy[label] for label in ordered_labels if label in label_to_strategy]


def run_shape_generation(shape_pipeline, image, strategies: list[dict[str, Any]]):
    last_error: Exception | None = None

    for index, strategy in enumerate(strategies, start=1):
        emit("shape_strategy", f"Strategie shape {strategy['label']} ({index}/{len(strategies)})...")
        try:
            mesh = shape_pipeline(image=image, **strategy["kwargs"])[0]
            return mesh, strategy["label"]
        except Exception as shape_error:
            last_error = shape_error
            emit("shape_retry", f"Strategie {strategy['label']} echouee ({shape_error})")
            if not should_retry_shape(shape_error) or index == len(strategies):
                break
            empty_cuda_cache()

    if last_error is not None:
        raise last_error
    raise RuntimeError("Aucune strategie shape n a pu etre executee.")


def detect_paint_high_res_kwargs(paint_pipeline, target_size: int) -> dict:
    """v77zh: probe Hunyuan3DPaintPipeline.__call__ for any kwarg that lets us
    push the bake resolution above the 1024 default. The Meshy-grade texture
    pop comes from 2K+ albedo with sharp detail; Hunyuan3D-2's default 1024
    bake is the bottleneck. We pass the target size only via kwargs that the
    actual pipeline signature accepts so older/newer hy3dgen forks don't
    blow up on TypeError.

    Returns an empty dict when the pipeline accepts none of the candidate
    kwargs — the caller falls back to default resolution silently.
    """
    import inspect

    candidate_keys = (
        "texture_size",
        "texture_resolution",
        "tex_resolution",
        "image_size",
        "render_size",
        "render_resolution",
        "size",
    )
    try:
        signature = inspect.signature(paint_pipeline.__call__)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        try:
            signature = inspect.signature(paint_pipeline)
        except (TypeError, ValueError):
            return {}
    accepted = set(signature.parameters.keys())
    for key in candidate_keys:
        if key in accepted:
            return {key: target_size}
    # Some hy3dgen forks expose **kwargs only — try the safest known one.
    for parameter in signature.parameters.values():
        if parameter.kind == inspect.Parameter.VAR_KEYWORD:
            return {"texture_size": target_size}
    return {}


def run_texture_generation(
    mesh,
    image,
    texture_model_path: str,
    device: str,
    paint_pipeline_factory,
    intent_purpose: str = "default",
):
    last_error: Exception | None = None
    max_texture_attempts = 3
    last_strategy = "none"
    textured = False
    mesh_to_export = mesh
    paint_offload = False

    # v77zh: characters and products win the most from a 2K bake (skin pores,
    # logo legibility, fabric weave) — keep mechanical / generic at 1536 to
    # avoid OOM on smaller GPUs while still beating the 1024 default.
    target_resolutions = (
        (2048, 1536, 1024)
        if intent_purpose in {"character", "product"}
        else (1536, 1280, 1024)
    )

    for attempt in range(1, max_texture_attempts + 1):
        try:
            emit("texture_load", f"Chargement du pipeline texture paint (tentative {attempt}/{max_texture_attempts})...")
            paint_pipeline = paint_pipeline_factory(texture_model_path)
            paint_offload = safe_enable_model_cpu_offload(paint_pipeline, "paint_pipeline", device)
            target_size = target_resolutions[min(attempt - 1, len(target_resolutions) - 1)]
            high_res_kwargs = detect_paint_high_res_kwargs(paint_pipeline, target_size)
            if high_res_kwargs:
                kw_label = ",".join(f"{k}={v}" for k, v in high_res_kwargs.items())
                emit("texture_run", f"Application de la texture paint ({kw_label})...")
            else:
                emit("texture_run", "Application de la texture paint (resolution defaut, signature non extensible)...")
            try:
                mesh_to_export = paint_pipeline(mesh, image, **high_res_kwargs)
            except TypeError as type_error:
                # Pipeline rejected the kwargs even though signature said it
                # accepted them (some forks declare **kwargs but only forward
                # a subset). Retry plain.
                emit("texture_retry", f"High-res kwargs refuses ({type_error}); fallback resolution defaut.")
                mesh_to_export = paint_pipeline(mesh, image)
                high_res_kwargs = {}
            textured = True
            last_strategy = (
                f"paint_attempt_{attempt}_size{list(high_res_kwargs.values())[0]}"
                if high_res_kwargs
                else f"paint_attempt_{attempt}_default"
            )
            return mesh_to_export, textured, last_strategy, paint_offload
        except Exception as texture_error:
            last_error = texture_error
            emit("texture_retry", f"Tentative {attempt} echouee ({texture_error})")
            if attempt < max_texture_attempts:
                empty_cuda_cache()

    emit("texture_warn", f"Texture paint echouee apres retries, export shape brute. Derniere erreur: {last_error}")
    return mesh_to_export, textured, "shape_only", paint_offload


def run_texture_with_pbr_or_fallback(
    mesh,
    image,
    texture_model_path: str,
    device: str,
    paint_pipeline_factory,
    intent_purpose: str = "default",
    run_id: str = "run",
    output_dir: str = ".",
    disable_pbr: bool = False,
):
    """Prefer the Hunyuan3D-2.1 PBR paint (hy3dpaint: albedo + metallic-roughness),
    fall back to the v2.0 albedo-only paint on any failure / OOM / unavailability."""
    if not disable_pbr:
        try:
            import paint_pbr_v21 as _pbr

            if _pbr.is_available():
                emit("texture_run", "Texture PBR 2.1 (hy3dpaint) — albedo + metallic-roughness...")
                work_dir = os.path.join(output_dir, f"{run_id}_pbr_work")
                os.makedirs(work_dir, exist_ok=True)
                white_path = os.path.join(work_dir, "white_mesh.obj")
                try:
                    mesh.export(white_path)
                except Exception:
                    white_path = os.path.join(work_dir, "white_mesh.glb")
                    mesh.export(white_path)
                # v90: more views + higher texture resolution for organic/product
                # so the face/skin/labels are sharp. The internal ladder
                # (1024→768→512→384→256) absorbs OOM on the 16GB card.
                mnv = 8 if intent_purpose in {"character", "product"} else 4
                tex_res = 1024 if intent_purpose in {"character", "product"} else 512
                out_glb = os.path.join(work_dir, f"{run_id}_pbr.glb")
                pbr_res = _pbr.paint_pbr_v21(
                    white_path, image, out_glb, work_dir, max_num_view=mnv, resolution=tex_res
                )
                if pbr_res.get("ok") and os.path.isfile(pbr_res.get("glb", "")):
                    import trimesh

                    painted = trimesh.load(pbr_res["glb"], force="mesh", process=False)
                    emit(
                        "texture_ok",
                        f"PBR 2.1 OK (res={pbr_res.get('resolution')}, MR={pbr_res.get('has_mr')}, "
                        f"normal={pbr_res.get('has_normal')}, albedo={pbr_res.get('has_albedo')}, faces={pbr_res.get('faces')})",
                    )
                    return painted, True, f"paint_pbr_v21_res{pbr_res.get('resolution')}", False
                emit("texture_warn", f"PBR 2.1 echoue -> fallback paint 2.0. ({pbr_res.get('error')})")
            else:
                emit("texture_info", "hy3dpaint PBR 2.1 indisponible (extensions/vendor manquants) -> paint 2.0")
        except Exception as exc:  # noqa: BLE001
            emit("texture_warn", f"PBR 2.1 exception ({exc!r}) -> fallback paint 2.0")
    return run_texture_generation(
        mesh, image, texture_model_path, device, paint_pipeline_factory, intent_purpose=intent_purpose
    )


def export_mesh_with_fallback(mesh, output_path: str, requested_format: str) -> tuple[str, str]:
    try:
        mesh.export(output_path)
        return output_path, requested_format
    except Exception as export_error:
        if requested_format != "glb":
            raise export_error

        fallback_path = os.path.splitext(output_path)[0] + ".obj"
        emit("export_fallback", f"Export GLB echoue ({export_error}). Repli automatique en OBJ pour ne pas perdre le mesh.")
        mesh.export(fallback_path)
        return fallback_path, "obj"


def post_process_mesh_in_place(
    mesh_path: str,
    intent_purpose: str,
    motion_readiness: str,
    target_dimension_meters: float | None = None,
    target_dimension_axis: str = "max",
    enforce_symmetry: bool = False,
    symmetry_blend: float = 0.55,
) -> dict[str, Any]:
    """Run the Aurora mesh post-processing pipeline in-place: smoothing,
    floater removal, hole filling, decimation and normal repair.

    Hunyuan3D outputs typically arrive over-tessellated, with a handful of
    isolated micro-shells and noisy normals — exactly what makes the Three.js
    viewer show "artefacts" (dark patches, spiky silhouettes, floating
    triangles). Running mesh_postprocess after every successful generation
    removes those before the user ever sees the mesh.

    v82: when the caller passes a target_dimension_meters, the pipeline also
    rescales the mesh on its largest (or chosen) axis. The user typing
    'pendule de 30cm' now ships a 0.3m mesh from the FIRST generation, no
    Sauvetage click needed.

    Returns a dict the worker can attach to the JSON payload so the UI can
    display "smoothed by pymeshlab/trimesh" diagnostics.
    """
    try:
        # v83-3dloop : si le mesh est DEJA texture (sortie du module Hunyuan paint),
        # NE PAS le post-processer — la decimation/lissage trimesh detruit les UV et
        # le baseColorTexture (trimesh quadric_decimation ne porte pas mesh.visual).
        # Le mesh peint est deja decime en amont (mesh_render.set_mesh, mode CPU). On le garde tel quel.
        try:
            import trimesh as _tm
            _m = _tm.load(mesh_path, process=False, force="mesh")
            _vis = getattr(_m, "visual", None)
            _mat = getattr(_vis, "material", None)
            _has_tex = (
                getattr(_vis, "uv", None) is not None
                or (_mat is not None and getattr(_mat, "baseColorTexture", None) is not None)
                or (_vis is not None and _vis.__class__.__name__ == "TextureVisuals")
            )
            if _has_tex:
                emit("post_skip", "Mesh deja texture -> post-process Taubin/decimation IGNORE (preserve UV/texture)")
                return {"applied": False, "skipped_reason": "textured_mesh",
                        "faces": int(len(_m.faces)), "verts": int(len(_m.vertices))}
        except Exception:
            pass

        # Lazy import: only load when Hunyuan succeeded.
        import importlib.util

        if importlib.util.find_spec("mesh_postprocess") is None:
            # Add the script's directory so the worker subprocess finds it.
            sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

        import mesh_postprocess

        smoothed_path = os.path.splitext(mesh_path)[0] + "_smoothed" + os.path.splitext(mesh_path)[1]
        emit("post_start", "Lissage anti-artefacts (Taubin + decimation)...")
        overrides: dict[str, Any] = {}
        if target_dimension_meters is not None and target_dimension_meters > 0:
            overrides["target_dimension_meters"] = float(target_dimension_meters)
            overrides["target_dimension_axis"] = target_dimension_axis
            emit("post_dimension", f"target {target_dimension_meters:.3f}m sur axe {target_dimension_axis}")
        if enforce_symmetry:
            overrides["enforce_symmetry"] = True
            overrides["symmetry_blend"] = float(symmetry_blend)
            emit("post_symmetry", f"YZ-mirror enforcement enabled, blend={symmetry_blend}")
        result = mesh_postprocess.post_process(
            mesh_path,
            smoothed_path,
            intent_purpose=intent_purpose,
            motion_readiness=motion_readiness,
            overrides=overrides if overrides else None,
        )
        if not result.get("ok") or not os.path.exists(smoothed_path):
            return {"applied": False, "reason": "post-process did not produce a file"}
        # Replace the original mesh atomically so the rest of the pipeline
        # (validation, export reporting) sees the cleaned version under the
        # same path.
        try:
            os.replace(smoothed_path, mesh_path)
        except Exception as replace_error:
            return {"applied": False, "reason": f"replace failed: {replace_error}"}
        return {
            "applied": True,
            "engine": result.get("engine"),
            "before_faces": result.get("before_faces"),
            "after_faces": result.get("after_faces"),
            "before_verts": result.get("before_verts"),
            "after_verts": result.get("after_verts"),
            "dropped_floaters": result.get("dropped_floaters", 0),
        }
    except Exception as exc:
        emit("post_warn", f"post-process skipped: {exc}")
        return {"applied": False, "reason": str(exc)[-200:]}


def validate_humanoid_proportions(mesh, validation: dict[str, Any], intent_purpose: str) -> None:
    """v77zj: anatomical proportion checks for character / body_part subjects.

    Hunyuan3D-2 occasionally ships geometrically-valid meshes that fail
    obvious humanoid sanity checks: head taking 40% of the silhouette
    (chibi when the user asked for a realistic adult), torso wider than
    tall (blob), or head wider than the shoulders (inverted proportions).
    Validation grade A-F was clean for these because their faces and
    triangles were fine — the proportions were the failure.

    Reports three new metrics:
      * humanoid_aspect_ratio  — vertical_extent / max(other extents).
        Adults ~ 3.0-4.0, chibi ~ 2.0, blob ~ 1.0
      * head_vertex_fraction   — share of vertices in the top 12.5% of the
        vertical axis. Adults ~ 0.10-0.20, chibi ~ 0.30+, dominant-head
        artefact ~ 0.45+
      * head_body_width_ratio  — width of the head zone divided by width
        of the bottom 25% (legs+feet). Adults ~ 0.35-0.6, inverted ~ >1.0

    Each metric only flags warnings (not hard fails) so realistic chibi
    or stylised characters keep passing. Together they let the auto-
    correction layer see "this looks like a blob, retry" instead of
    accepting a bad mesh because its triangles were fine.
    """
    if intent_purpose not in ("character", "body_part"):
        return
    try:
        import numpy as np
    except ImportError:
        return
    if not hasattr(mesh, "vertices") or len(mesh.vertices) < 100:
        return

    verts = np.asarray(mesh.vertices)
    extents = mesh.extents
    if extents is None or len(extents) < 3:
        return

    vertical_axis = int(np.argmax(extents))
    height = float(extents[vertical_axis])
    if height <= 1e-6:
        return

    other_axes = [i for i in range(3) if i != vertical_axis]
    horizontal_max = max(float(extents[i]) for i in other_axes)
    aspect = height / max(horizontal_max, 1e-6)
    validation["humanoid_aspect_ratio"] = float(aspect)

    if aspect < 1.4:
        validation["warnings"].append(
            f"Silhouette trapue (height/width = {aspect:.2f}): personnage proche d une silhouette blob, "
            "un humanoide debout cible 2.0+ et un adulte realiste 3.0+"
        )
    elif aspect < 1.8:
        validation["warnings"].append(
            f"Silhouette legerement trapue (height/width = {aspect:.2f}): style chibi probable"
        )

    z = verts[:, vertical_axis]
    z_max = float(z.max())
    head_threshold = z_max - height * 0.125
    head_indices = z >= head_threshold
    head_count = int(head_indices.sum())
    total_count = int(len(z))
    head_fraction = head_count / max(total_count, 1)
    validation["head_vertex_fraction"] = float(head_fraction)

    if head_fraction > 0.45:
        validation["warnings"].append(
            f"Tete dominante ({head_fraction:.0%} des vertices dans le top 1/8 de la hauteur): "
            "la silhouette ne ressemble pas a un humanoide debout"
        )
    elif head_fraction > 0.30:
        validation["warnings"].append(
            f"Style chibi detecte ({head_fraction:.0%} des vertices dans la tete vs ~15% pour un adulte realiste)"
        )
    elif head_fraction < 0.04:
        validation["warnings"].append(
            f"Tete tres reduite ({head_fraction:.0%}): possible mesh tronque ou stylisation extreme"
        )

    z_min = float(z.min())
    bottom_threshold = z_min + height * 0.25
    bottom_indices = z <= bottom_threshold
    if head_count >= 10 and bottom_indices.sum() >= 10:
        primary_horizontal = other_axes[0]
        head_width = float(np.ptp(verts[head_indices][:, primary_horizontal]))
        bottom_width = float(np.ptp(verts[bottom_indices][:, primary_horizontal]))
        if bottom_width > 1e-6:
            head_body_width_ratio = head_width / bottom_width
            validation["head_body_width_ratio"] = float(head_body_width_ratio)
            if head_body_width_ratio > 1.5:
                validation["warnings"].append(
                    f"Tete plus large que les jambes ({head_body_width_ratio:.2f}x): "
                    "proportions inversees, probable echec de la silhouette humanoide"
                )
            elif head_body_width_ratio > 1.05:
                validation["warnings"].append(
                    f"Tete a peu pres aussi large que les jambes ({head_body_width_ratio:.2f}x): "
                    "verifie que ce n est pas un personnage avec un casque/coiffure tres volumineuse"
                )


def validate_output_mesh(output_path: str, intent_purpose: str = "default") -> dict[str, Any]:
    """Validate the exported mesh with deep geometry analysis:
    file size, face/vertex counts, flatness, disconnected components,
    aspect ratio, surface area density, degenerate faces, and bounding-box sanity.

    v77zj: when intent_purpose is character / body_part, also runs
    validate_humanoid_proportions to flag chibi / blob / inverted-
    proportion meshes that pass triangle sanity checks but fail the
    obvious "looks like a person standing up" sanity check.
    """
    if not os.path.exists(output_path):
        raise FileNotFoundError(f"Mesh exporte introuvable: {output_path}")

    size = os.path.getsize(output_path)
    if size < 4096:
        raise RuntimeError(f"Mesh exporte trop petit pour etre exploitable ({size} octets).")

    validation: dict[str, Any] = {
        "file_size": size,
        "quality_ok": True,
        "issues": [],
        "warnings": [],
        "geometry_grade": "unknown",
    }

    try:
        import trimesh
        import numpy as np

        scene_or_mesh = trimesh.load(output_path)
        if scene_or_mesh is None:
            validation["quality_ok"] = False
            validation["issues"].append("Impossible de charger le mesh pour validation")
            return validation

        # Handle scenes (multi-object GLB) vs single meshes
        if isinstance(scene_or_mesh, trimesh.Scene):
            meshes = [g for g in scene_or_mesh.geometry.values() if isinstance(g, trimesh.Trimesh)]
            if not meshes:
                validation["quality_ok"] = False
                validation["issues"].append("Scene GLB vide: aucun mesh exploitable")
                return validation
            mesh = trimesh.util.concatenate(meshes) if len(meshes) > 1 else meshes[0]
            validation["component_count"] = len(meshes)
        else:
            mesh = scene_or_mesh if isinstance(scene_or_mesh, trimesh.Trimesh) else trimesh.Trimesh()
            validation["component_count"] = 1

        bounds = mesh.bounds
        extents = mesh.extents
        face_count = len(mesh.faces) if hasattr(mesh, "faces") else 0
        vertex_count = len(mesh.vertices) if hasattr(mesh, "vertices") else 0

        validation["vertex_count"] = vertex_count
        validation["face_count"] = face_count
        validation["extents"] = extents.tolist() if hasattr(extents, "tolist") else list(extents)
        validation["bounds"] = bounds.tolist() if hasattr(bounds, "tolist") else [list(b) for b in bounds]

        # ── Check 1: degenerate mesh (too few faces) ──
        if face_count < 100:
            validation["quality_ok"] = False
            validation["issues"].append(f"Mesh degenere: seulement {face_count} faces (minimum 100)")
        elif face_count < 500:
            validation["warnings"].append(f"Mesh tres low-poly: {face_count} faces (risque de perte de detail)")

        # ── Check 2: flat mesh (one dimension much smaller than others) ──
        sorted_extents = sorted(extents)
        if sorted_extents[2] > 0.001:
            flatness_ratio = sorted_extents[0] / sorted_extents[2]
            validation["flatness_ratio"] = float(flatness_ratio)
            if flatness_ratio < 0.05:
                validation["quality_ok"] = False
                validation["issues"].append(
                    f"Mesh trop plat (ratio {flatness_ratio:.3f}): "
                    f"dimensions {sorted_extents[0]:.4f} x {sorted_extents[1]:.4f} x {sorted_extents[2]:.4f}. "
                    "Le mesh ressemble a un bas-relief 2D plutot qu un objet 3D."
                )
            elif flatness_ratio < 0.12:
                validation["warnings"].append(
                    f"Mesh relativement plat (ratio {flatness_ratio:.3f}): verifier que ce n est pas un artefact"
                )
        else:
            validation["flatness_ratio"] = 0.0

        # ── Check 3: microscopic mesh ──
        max_extent = float(max(extents)) if len(extents) > 0 else 0
        if max_extent < 0.001:
            validation["quality_ok"] = False
            validation["issues"].append(f"Mesh microscopique (max dimension {max_extent:.6f})")

        # ── Check 4: NaN vertices ──
        if np.any(np.isnan(mesh.vertices)):
            validation["quality_ok"] = False
            validation["issues"].append("Mesh contient des vertices NaN (geometrie corrompue)")

        # ── Check 5: aspect ratio sanity ──
        if sorted_extents[2] > 0.001 and sorted_extents[1] > 0.001:
            aspect_xy = sorted_extents[1] / sorted_extents[2]
            validation["aspect_ratio"] = float(aspect_xy)
            if aspect_xy < 0.08:
                validation["warnings"].append(
                    f"Ratio d aspect extreme ({aspect_xy:.3f}): le mesh est tres allonge dans une seule direction"
                )

        # ── Check 6: disconnected components ──
        try:
            body_count = mesh.body_count if hasattr(mesh, "body_count") else 1
            validation["disconnected_bodies"] = int(body_count)
            if body_count > 20:
                validation["warnings"].append(
                    f"Mesh tres fragmente: {body_count} corps disconnectes (risque de geometrie flottante)"
                )
        except Exception:
            validation["disconnected_bodies"] = -1

        # ── Check 7: surface area density (faces per unit volume) ──
        try:
            volume = float(mesh.volume) if mesh.is_volume else 0
            surface_area = float(mesh.area) if hasattr(mesh, "area") else 0
            validation["surface_area"] = surface_area
            validation["volume"] = volume
            if surface_area > 0 and face_count > 0:
                area_per_face = surface_area / face_count
                validation["area_per_face"] = float(area_per_face)
                # Very small area per face = mesh is over-tessellated in a tiny region (potential artifact)
                if area_per_face < 1e-8 and face_count > 1000:
                    validation["warnings"].append(
                        "Certaines faces sont microscopiques: possible artefact de tessellation"
                    )
        except Exception:
            pass

        # ── Check 8: degenerate faces (zero-area triangles) ──
        try:
            face_areas = mesh.area_faces if hasattr(mesh, "area_faces") else np.array([])
            if len(face_areas) > 0:
                zero_area_count = int(np.sum(face_areas < 1e-10))
                validation["degenerate_face_count"] = zero_area_count
                degen_ratio = zero_area_count / max(face_count, 1)
                if degen_ratio > 0.15:
                    validation["quality_ok"] = False
                    validation["issues"].append(
                        f"{zero_area_count} faces degenerees ({degen_ratio:.1%} du total): "
                        "geometrie corrompue ou artefacts de reconstruction"
                    )
                elif degen_ratio > 0.05:
                    validation["warnings"].append(
                        f"{zero_area_count} faces degenerees ({degen_ratio:.1%}): qualite mesh reduite"
                    )
        except Exception:
            pass

        # ── Check 9: watertight / manifold ──
        try:
            validation["is_watertight"] = bool(mesh.is_watertight)
            if not mesh.is_watertight:
                validation["warnings"].append("Mesh non etanche (non-manifold ou trous): normal pour AI generation")
        except Exception:
            validation["is_watertight"] = False

        # ── Geometry grade ──
        issue_count = len(validation["issues"])
        warning_count = len(validation["warnings"])
        if issue_count == 0 and warning_count == 0:
            validation["geometry_grade"] = "A"
        elif issue_count == 0 and warning_count <= 2:
            validation["geometry_grade"] = "B"
        elif issue_count == 0:
            validation["geometry_grade"] = "C"
        elif issue_count <= 1:
            validation["geometry_grade"] = "D"
        else:
            validation["geometry_grade"] = "F"

        # v77zj: humanoid proportion sanity. Runs only for character /
        # body_part purposes — appends warnings to validation in place.
        validate_humanoid_proportions(mesh, validation, intent_purpose)

        # Re-derive grade after humanoid checks so chibi / blob / inverted
        # warnings actually drop the grade and the auto-correction layer
        # picks them up.
        issue_count = len(validation["issues"])
        warning_count = len(validation["warnings"])
        if issue_count == 0 and warning_count == 0:
            validation["geometry_grade"] = "A"
        elif issue_count == 0 and warning_count <= 2:
            validation["geometry_grade"] = "B"
        elif issue_count == 0:
            validation["geometry_grade"] = "C"
        elif issue_count <= 1:
            validation["geometry_grade"] = "D"
        else:
            validation["geometry_grade"] = "F"

        if validation["issues"]:
            emit("validate", f"Problemes mesh detectes: {'; '.join(validation['issues'])}")
        elif validation["warnings"]:
            emit("validate", f"Mesh valide avec avertissements: {'; '.join(validation['warnings'][:3])}")
        else:
            emit("validate", f"Mesh valide (grade {validation['geometry_grade']}): "
                 f"{vertex_count} vertices, {face_count} faces, "
                 f"dimensions {extents[0]:.3f} x {extents[1]:.3f} x {extents[2]:.3f}")

    except ImportError:
        emit("validate", "trimesh indisponible, validation geometrique ignoree")
    except Exception as e:
        emit("validate", f"Validation geometrique echouee: {e}")

    return validation


def humanize_error(exc: Exception) -> str:
    message = str(exc)

    if re.search(r"No module named 'hy3dshape'", message, flags=re.IGNORECASE):
        return (
            "Le snapshot shape 2.1 requiert le runtime officiel hy3dshape, absent ici. "
            "Le module doit utiliser le fallback shape Hunyuan3D-2 compatible hy3dgen."
        )
    if "object has no attribute 'components'" in message:
        return (
            "Le pipeline hy3dgen actif ne supporte pas l offload CPU de type diffusers. "
            "Aurora doit ignorer cet offload et continuer avec une strategie shape plus stable."
        )
    if re.search(r"allow_in_graph|torch\._dynamo", message, flags=re.IGNORECASE):
        return (
            "Le runtime PyTorch a rencontre une incompatibilite Dynamo ou compilation. "
            "Le module doit retomber sur une strategie d inference plus conservative."
        )

    return message


def collect_multiview_paths(args) -> dict[str, str]:
    if getattr(args, "disable_multiview", False):
        return {}
    views = {
        "front": args.mv_front,
        "back": args.mv_back,
        "left": args.mv_left,
        "right": args.mv_right,
    }
    return {view: path for view, path in views.items() if path}


def load_source_image(path: str, rembg_available: bool, background_remover):
    from PIL import Image

    image = Image.open(path).convert("RGBA")
    if rembg_available and background_remover is not None:
        return background_remover(image)
    return image.convert("RGB")


def prepare_source_images(
    primary_path: str,
    multiview_paths: dict[str, str],
    rembg_available: bool,
    background_remover,
):
    prepared_multiview = {}

    for view, path in multiview_paths.items():
        if not os.path.exists(path):
            raise FileNotFoundError(f"Vue {view} introuvable: {path}")
        prepared_multiview[view] = load_source_image(path, rembg_available, background_remover)

    if len(prepared_multiview) >= 2:
        texture_reference = prepared_multiview.get("front") or next(iter(prepared_multiview.values()))
        return prepared_multiview, texture_reference, len(prepared_multiview), True

    if not os.path.exists(primary_path):
        raise FileNotFoundError(f"Image introuvable: {primary_path}")

    primary_image = load_source_image(primary_path, rembg_available, background_remover)
    return primary_image, primary_image, 1, False


def resolve_device(torch_module, force_device: str) -> str:
    if force_device == "cpu":
        emit("device", "Mode secours force sur CPU.")
        return "cpu"
    if force_device == "cuda":
        if torch_module.cuda.is_available():
            return "cuda"
        emit("device", "CUDA indisponible, fallback automatique sur CPU.")
        return "cpu"
    return "cuda" if torch_module.cuda.is_available() else "cpu"


def iter_json_lines(lines: list[str]):
    for raw_line in reversed(lines):
        line = raw_line.strip()
        if not line or not WORKER_JSON_LINE_RE.match(line):
            continue
        try:
            parsed = json.loads(line)
        except Exception:
            continue
        if isinstance(parsed, dict):
            yield parsed


def extract_worker_payload(stdout_lines: list[str]) -> dict[str, Any] | None:
    return next(iter_json_lines(stdout_lines), None)


def compact_worker_output(stdout_lines: list[str], stderr_lines: list[str], limit: int = 8) -> str:
    combined: list[str] = []
    for line in stderr_lines + stdout_lines:
        cleaned = line.strip()
        if not cleaned or cleaned.startswith("PROGRESS:") or cleaned.startswith("SAVED:"):
            continue
        combined.append(cleaned)
    if not combined:
        return "sortie worker indisponible"
    return " | ".join(combined[-limit:])


def should_retry_worker(return_code: int, stdout_lines: list[str], stderr_lines: list[str]) -> bool:
    if return_code in WORKER_NATIVE_CRASH_EXIT_CODES:
        return True

    combined = "\n".join(stderr_lines + stdout_lines)
    return any(pattern.search(combined) for pattern in WORKER_RETRYABLE_ERROR_PATTERNS)


def humanize_worker_failure(return_code: int, stdout_lines: list[str], stderr_lines: list[str]) -> str:
    payload = extract_worker_payload(stdout_lines)
    if payload and payload.get("error"):
        base_message = str(payload["error"])
    else:
        base_message = compact_worker_output(stdout_lines, stderr_lines)

    if return_code in WORKER_NATIVE_CRASH_EXIT_CODES:
        return (
            "Le runtime Hunyuan3D a subi un crash natif Windows pendant la phase shape "
            "(PyTorch/CUDA). Aurora a relance plusieurs strategies plus prudentes, mais le "
            f"worker a quand meme termine sur un crash. Detail: {base_message}"
        )

    if re.search(r"allow_in_graph|torch\._dynamo", base_message, flags=re.IGNORECASE):
        return (
            "Le runtime Hunyuan3D reste bloque par une incompatibilite TorchDynamo/compilation "
            f"malgre les retries defensifs. Detail: {base_message}"
        )

    return humanize_error(RuntimeError(base_message))


def read_worker_stream(stream, bucket: list[str], echo_progress: bool) -> None:
    try:
        for raw_line in iter(stream.readline, ""):
            line = raw_line.rstrip("\r\n")
            if not line:
                continue
            bucket.append(line)
            if echo_progress and line.startswith("PROGRESS:"):
                print(line, flush=True)
    finally:
        try:
            stream.close()
        except Exception:
            pass


def build_worker_cli_args(args, attempt: dict[str, Any]) -> list[str]:
    worker_args = [
        os.path.abspath(__file__),
        "--worker-mode",
        "--skip-dependency-check",
        "--image",
        args.image,
        "--output-dir",
        args.output_dir,
        "--run-id",
        args.run_id,
        "--format",
        args.format,
        "--intent-purpose",
        args.intent_purpose,
        "--motion-readiness",
        args.motion_readiness,
        "--force-device",
        attempt["force_device"],
        "--preferred-shape-strategy",
        attempt["preferred_shape_strategy"],
        "--attempt-label",
        attempt["label"],
    ]

    if args.dimensional_precision:
        worker_args.append("--dimensional-precision")
    if getattr(args, "target_dimension_meters", None) is not None and args.target_dimension_meters > 0:
        worker_args.extend(["--target-dimension-meters", str(args.target_dimension_meters)])
        worker_args.extend(["--target-dimension-axis", args.target_dimension_axis])
    if args.mv_front:
        worker_args.extend(["--mv-front", args.mv_front])
    if args.mv_back:
        worker_args.extend(["--mv-back", args.mv_back])
    if args.mv_left:
        worker_args.extend(["--mv-left", args.mv_left])
    if args.mv_right:
        worker_args.extend(["--mv-right", args.mv_right])
    if attempt.get("disable_offload"):
        worker_args.append("--disable-offload")
    if attempt.get("disable_texture"):
        worker_args.append("--disable-texture")
    if attempt.get("disable_multiview"):
        worker_args.append("--disable-multiview")

    return worker_args


def build_worker_attempts(multiview_requested: bool) -> list[dict[str, Any]]:
    attempts = [
        {
            "label": "gpu_quality_guarded",
            "summary": "qualite maximale avec garde-fous TorchDynamo",
            "preferred_shape_strategy": "maximum_quality",
            "force_device": "auto",
            "disable_offload": False,
            "disable_texture": False,
            "disable_multiview": False,
            "env": {
                "TORCHDYNAMO_DISABLE": "1",
            },
        },
        {
            "label": "gpu_stable_no_offload",
            "summary": "GPU stable sans offload CPU diffusers",
            "preferred_shape_strategy": "balanced",
            "force_device": "auto",
            "disable_offload": True,
            "disable_texture": False,
            "disable_multiview": False,
            "env": {
                "TORCHDYNAMO_DISABLE": "1",
            },
        },
    ]

    if multiview_requested:
        attempts.append(
            {
                "label": "single_view_recovery",
                "summary": "fallback single-view si la multivue declenche l instabilite",
                "preferred_shape_strategy": "memory_safe",
                "force_device": "auto",
                "disable_offload": True,
                "disable_texture": False,
                "disable_multiview": True,
                "env": {
                    "TORCHDYNAMO_DISABLE": "1",
                },
            }
        )
    else:
        attempts.append(
            {
                "label": "gpu_memory_safe",
                "summary": "GPU memory-safe",
                "preferred_shape_strategy": "memory_safe",
                "force_device": "auto",
                "disable_offload": True,
                "disable_texture": False,
                "disable_multiview": False,
                "env": {
                    "TORCHDYNAMO_DISABLE": "1",
                },
            }
        )

    attempts.append(
        {
            "label": "cpu_shape_rescue",
            "summary": "secours CPU shape-only pour sauver un mesh exploitable",
            "preferred_shape_strategy": "stability_fallback",
            "force_device": "cpu",
            "disable_offload": True,
            "disable_texture": True,
            "disable_multiview": multiview_requested,
            "env": {
                "TORCHDYNAMO_DISABLE": "1",
                "CUDA_VISIBLE_DEVICES": "",
            },
        }
    )

    return attempts


def run_worker_subprocess(args, attempt: dict[str, Any]) -> tuple[int, list[str], list[str]]:
    env = os.environ.copy()
    env.update(attempt.get("env", {}))
    command = [sys.executable] + build_worker_cli_args(args, attempt)
    process = subprocess.Popen(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=env,
    )

    stdout_lines: list[str] = []
    stderr_lines: list[str] = []
    stdout_thread = threading.Thread(
        target=read_worker_stream,
        args=(process.stdout, stdout_lines, True),
        daemon=True,
    )
    stderr_thread = threading.Thread(
        target=read_worker_stream,
        args=(process.stderr, stderr_lines, False),
        daemon=True,
    )
    stdout_thread.start()
    stderr_thread.start()
    return_code = process.wait()
    stdout_thread.join()
    stderr_thread.join()
    return return_code, stdout_lines, stderr_lines


def run_worker(args) -> int:
    configure_runtime_environment()
    if not args.skip_dependency_check:
        ensure_dependencies()

    input_image = args.image
    output_dir = args.output_dir
    run_id = args.run_id
    requested_format = args.format
    output_path = os.path.join(output_dir, f"{run_id}_mesh.{requested_format}")
    os.makedirs(output_dir, exist_ok=True)
    multiview_paths = collect_multiview_paths(args)

    import torch
    from hy3dgen.shapegen import Hunyuan3DDiTFlowMatchingPipeline
    from hy3dgen.texgen import Hunyuan3DPaintPipeline

    try:
        from hy3dgen.rembg import BackgroundRemover

        rembg_available = True
    except Exception:
        BackgroundRemover = None
        rembg_available = False
        emit("bg", "rembg indisponible - image brute utilisee sans detourage")

    device = resolve_device(torch, args.force_device)
    dtype = torch.float16 if device == "cuda" else torch.float32
    emit("device", f"Backend Hunyuan3D sur {device.upper()}")

    try:
        emit("bg", "Preparation de l image source...")
        background_remover = BackgroundRemover() if rembg_available and BackgroundRemover is not None else None
        shape_inputs, texture_image, view_count, multiview_requested = prepare_source_images(
            input_image,
            multiview_paths,
            rembg_available,
            background_remover,
        )
        if getattr(args, "disable_multiview", False) and view_count > 1:
            emit("shape_fallback", "Multivue desactivee par la strategie de recuperation, la vue principale sera privilegiee.")
        if multiview_requested:
            emit("shape_mode", f"Mode multivue demande avec {view_count} vues.")

        shape_candidate = resolve_shape_candidate(multiview_requested)
        texture_model_path = ensure_texture_assets() if not args.disable_texture else ""
        shape_label = shape_candidate["repo_id"]

        fallback_used = shape_candidate["repo_id"] != SHAPE_MODEL_ID and shape_candidate.get("input_mode") != "multiview"

        if fallback_used:
            emit("shape_fallback", f"Fallback shape actif vers {shape_label}/{shape_candidate['subfolder']}.")
        if multiview_requested and shape_candidate.get("input_mode") != "multiview":
            emit("shape_fallback", "Mode multivue indisponible sur le snapshot courant, fallback single-view sur la vue principale.")

        emit("shape_load", f"Chargement du modele shape {shape_label}/{shape_candidate['subfolder']} ({shape_candidate['weight_format']})...")
        snapshot_path = shape_candidate["model_path"]
        os.environ["HY3DGEN_MODELS"] = os.path.dirname(snapshot_path)
        snapshot_dirname = os.path.basename(snapshot_path)

        shape_pipeline = Hunyuan3DDiTFlowMatchingPipeline.from_pretrained(
            snapshot_dirname,
            subfolder=shape_candidate["load_subfolder"],
            variant=shape_candidate.get("variant"),
            use_safetensors=shape_candidate["use_safetensors"],
            device=device,
            dtype=dtype,
        )
        shape_offload = safe_enable_model_cpu_offload(shape_pipeline, "shape_pipeline", device, allow_offload=not args.disable_offload)

        emit("shape_run", "Generation du mesh shape...")
        effective_shape_inputs = shape_inputs if shape_candidate.get("input_mode") == "multiview" else texture_image
        mesh, shape_strategy = run_shape_generation(
            shape_pipeline,
            effective_shape_inputs,
            build_shape_strategies(
                args.intent_purpose,
                args.motion_readiness,
                args.dimensional_precision,
                shape_candidate.get("input_mode") == "multiview",
                preferred_label=args.preferred_shape_strategy,
            ),
        )

        # Libere la VRAM du pipeline shape AVANT de peindre. Le paint PBR (diffusion 8 vues
        # + RealESRGAN) reclame ~14 Go sur 16 ; comme l'offload CPU est ignore par la pile
        # hy3dgen, garder le DiT shape resident faisait OOM la texture a TOUTES les
        # resolutions (jusqu'a 256) -> mesh gris sans couleur. Le mesh est deja extrait.
        try:
            shape_pipeline = None  # noqa: F841  (libere la reference GPU)
        except Exception:
            pass
        gc.collect()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
            try:
                torch.cuda.ipc_collect()
            except Exception:
                pass
        emit("vram_free", "VRAM du shape liberee avant la texture.")

        if args.disable_texture:
            emit("texture_skip", "Texture desactivee par la strategie de recuperation; export de la shape brute.")
            mesh_to_export = mesh
            textured = False
            texture_strategy = "shape_only_forced"
            paint_offload = False
        else:
            mesh_to_export, textured, texture_strategy, paint_offload = run_texture_with_pbr_or_fallback(
                mesh,
                texture_image,
                texture_model_path,
                device,
                Hunyuan3DPaintPipeline.from_pretrained,
                intent_purpose=args.intent_purpose,
                run_id=run_id,
                output_dir=output_dir,
                disable_pbr=bool(getattr(args, "disable_pbr_paint", False)),
            )

        emit("export", f"Export {requested_format.upper()} en cours...")
        output_path, exported_format = export_mesh_with_fallback(mesh_to_export, output_path, requested_format)
        # Smooth + decimate + repair the mesh in-place to clean Hunyuan3D
        # artefacts (spikes, floaters, noisy normals) before the viewer sees it.
        post_process_report = post_process_mesh_in_place(
            output_path,
            args.intent_purpose,
            args.motion_readiness,
            target_dimension_meters=getattr(args, "target_dimension_meters", None),
            target_dimension_axis=getattr(args, "target_dimension_axis", "max"),
            enforce_symmetry=bool(getattr(args, "enforce_symmetry", False)),
            symmetry_blend=float(getattr(args, "symmetry_blend", 0.55)),
        )
        mesh_validation = validate_output_mesh(output_path, intent_purpose=args.intent_purpose)

        # If mesh fails geometry quality checks, report but don't crash
        # (the TypeScript layer will decide whether to retry)
        mesh_quality_ok = mesh_validation.get("quality_ok", True)
        mesh_quality_issues = mesh_validation.get("issues", [])

        print(f"SAVED:{output_path}", flush=True)
        print(
            json.dumps(
                {
                    "ok": True,
                    "path": output_path,
                    "format": exported_format,
                    "shape_model": shape_candidate["repo_id"],
                    "shape_subfolder": shape_candidate["subfolder"],
                    "shape_weight_format": shape_candidate["weight_format"],
                    "shape_runtime": shape_candidate.get("shape_runtime", "hy3dgen"),
                    "shape_strategy": shape_strategy,
                    "shape_offload": shape_offload,
                    "texture_model": TEXTURE_MODEL_ID if not args.disable_texture else None,
                    "texture_strategy": texture_strategy,
                    "paint_offload": paint_offload,
                    "textured": textured,
                    "fallback_used": fallback_used,
                    "compatibility_reason": shape_candidate.get("compatibility_reason") or None,
                    "shape_input_mode": shape_candidate.get("input_mode", "single_view"),
                    "multiview_used": bool(shape_candidate.get("input_mode") == "multiview"),
                    "view_count": view_count,
                    "device": device,
                    "attempt_label": args.attempt_label,
                    "texture_disabled": bool(args.disable_texture),
                    "offload_disabled": bool(args.disable_offload),
                    "mesh_quality_ok": mesh_quality_ok,
                    "mesh_quality_issues": mesh_quality_issues,
                    "mesh_quality_warnings": mesh_validation.get("warnings", []),
                    "mesh_geometry_grade": mesh_validation.get("geometry_grade", "unknown"),
                    "mesh_vertex_count": mesh_validation.get("vertex_count"),
                    "mesh_face_count": mesh_validation.get("face_count"),
                    "mesh_extents": mesh_validation.get("extents"),
                    "mesh_flatness_ratio": mesh_validation.get("flatness_ratio"),
                    "mesh_aspect_ratio": mesh_validation.get("aspect_ratio"),
                    "mesh_humanoid_aspect_ratio": mesh_validation.get("humanoid_aspect_ratio"),
                    "mesh_head_vertex_fraction": mesh_validation.get("head_vertex_fraction"),
                    "mesh_head_body_width_ratio": mesh_validation.get("head_body_width_ratio"),
                    "mesh_disconnected_bodies": mesh_validation.get("disconnected_bodies"),
                    "mesh_degenerate_face_count": mesh_validation.get("degenerate_face_count"),
                    "mesh_is_watertight": mesh_validation.get("is_watertight"),
                    "mesh_surface_area": mesh_validation.get("surface_area"),
                    "mesh_volume": mesh_validation.get("volume"),
                    "post_processing": post_process_report,
                }
            )
        )

        del mesh_to_export
        del mesh
        empty_cuda_cache()
        return 0
    except Exception as exc:
        try:
            empty_cuda_cache()
        except Exception:
            pass
        gc.collect()
        print(json.dumps({"ok": False, "error": humanize_error(exc)[-700:], "attempt_label": args.attempt_label}))
        return 1


def run_orchestrator(args) -> int:
    configure_runtime_environment()
    ensure_dependencies()

    multiview_requested = bool(collect_multiview_paths(args))
    attempts = build_worker_attempts(multiview_requested)
    last_failure: dict[str, Any] | None = None

    for index, attempt in enumerate(attempts, start=1):
        emit("shape_worker", f"Tentative protegee {index}/{len(attempts)}: {attempt['summary']}...")
        return_code, stdout_lines, stderr_lines = run_worker_subprocess(args, attempt)
        payload = extract_worker_payload(stdout_lines)

        if return_code == 0 and payload and payload.get("ok"):
            for line in stdout_lines:
                if line.startswith("PROGRESS:") or WORKER_JSON_LINE_RE.match(line.strip()):
                    continue
                print(line, flush=True)

            payload["orchestrated"] = True
            payload["worker_attempt_index"] = index
            payload["worker_attempt_count"] = len(attempts)
            payload["recovery_attempt"] = attempt["label"] if index > 1 else None
            payload["recovery_applied"] = index > 1
            print(json.dumps(payload))
            return 0

        last_failure = {
            "attempt": attempt,
            "index": index,
            "return_code": return_code,
            "stdout_lines": stdout_lines,
            "stderr_lines": stderr_lines,
        }
        if index < len(attempts) and should_retry_worker(return_code, stdout_lines, stderr_lines):
            emit("shape_retry", f"Tentative {attempt['label']} echouee; passage a une strategie encore plus defensive.")
            continue
        break

    if last_failure is None:
        print(json.dumps({"ok": False, "error": "Aucune tentative Hunyuan3D n a pu etre executee."}))
        return 0

    error_message = humanize_worker_failure(
        last_failure["return_code"],
        last_failure["stdout_lines"],
        last_failure["stderr_lines"],
    )
    print(
        json.dumps(
            {
                "ok": False,
                "error": error_message,
                "worker_attempt_index": last_failure["index"],
                "worker_attempt_count": len(attempts),
                "last_attempt": last_failure["attempt"]["label"],
            }
        )
    )
    return 0


def main():
    parser = argparse.ArgumentParser(description="Hunyuan3D mesh generation")
    parser.add_argument("--image", required=True, help="Input reference image path")
    parser.add_argument("--mv-front", help="Optional front view path")
    parser.add_argument("--mv-back", help="Optional back view path")
    parser.add_argument("--mv-left", help="Optional left view path")
    parser.add_argument("--mv-right", help="Optional right view path")
    parser.add_argument("--output-dir", required=True, help="Output directory for mesh")
    parser.add_argument("--run-id", required=True, help="Unique run ID for filenames")
    parser.add_argument("--format", default="glb", choices=["glb", "obj"], help="Output mesh format")
    parser.add_argument("--intent-purpose", default="visual_preview")
    parser.add_argument("--motion-readiness", default="static_only")
    parser.add_argument("--dimensional-precision", action="store_true")
    parser.add_argument(
        "--target-dimension-meters",
        type=float,
        default=None,
        help="v82: scale exported mesh so its largest extent matches this size (in meters)",
    )
    parser.add_argument(
        "--target-dimension-axis",
        choices=["max", "x", "y", "z"],
        default="max",
    )
    parser.add_argument(
        "--enforce-symmetry",
        action="store_true",
        help="v77zi: bilateral symmetry enforcement on YZ plane (recommended for character/body_part/creature)",
    )
    parser.add_argument(
        "--symmetry-blend",
        type=float,
        default=0.55,
        help="Symmetry blend (0.5 perfect mean, 0.55 default, 0.7 light)",
    )
    parser.add_argument("--worker-mode", action="store_true")
    parser.add_argument("--skip-dependency-check", action="store_true")
    parser.add_argument("--disable-offload", action="store_true")
    parser.add_argument("--disable-texture", action="store_true")
    parser.add_argument("--disable-pbr-paint", action="store_true",
                        help="Skip the Hunyuan3D-2.1 PBR paint (hy3dpaint) and use the v2.0 albedo-only paint.")
    parser.add_argument("--disable-multiview", action="store_true")
    parser.add_argument("--force-device", default="auto", choices=["auto", "cuda", "cpu"])
    parser.add_argument(
        "--preferred-shape-strategy",
        default="maximum_quality",
        choices=["maximum_quality", "balanced", "memory_safe", "stability_fallback"],
    )
    parser.add_argument("--attempt-label", default="direct")
    args = parser.parse_args()
    if args.worker_mode:
        return run_worker(args)
    return run_orchestrator(args)


if __name__ == "__main__":
    sys.exit(main())
