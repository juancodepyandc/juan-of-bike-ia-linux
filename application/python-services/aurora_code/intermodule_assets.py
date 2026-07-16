#!/usr/bin/env python3
"""Materialise les assets inter-modules demandes par le Module Code (WS15)."""
from __future__ import annotations
import base64
import io
import json
import os
import pathlib
import re
import shutil
import sys
import time
import urllib.parse
import urllib.request
from random import randint
from typing import Any

from PIL import Image, features

try:
    from .intermodule_rag import build_rag_trace
    from .intermodule_asset_reuse import requested_asset_kinds, reuse_or_generate
except ImportError:
    from intermodule_rag import build_rag_trace
    from intermodule_asset_reuse import requested_asset_kinds, reuse_or_generate


SCHEMA = "aurora.code.asset-bundle/1"
SUPPORTED_KINDS = ("image", "model3d", "voice")
def workspace_root() -> pathlib.Path:
    return pathlib.Path(__file__).resolve().parents[2]


def slug(value: str) -> str:
    out = re.sub(r"[^a-z0-9_-]+", "-", value.lower()).strip("-")
    return out[:80] or "asset"


def post_json(base_url: str, path: str, payload: dict[str, Any], timeout: int = 30) -> dict[str, Any]:
    request = urllib.request.Request(
        urllib.parse.urljoin(f"{base_url.rstrip('/')}/", path.lstrip("/")),
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8", errors="replace") or "{}")


def get_json(base_url: str, path: str, timeout: int = 30) -> dict[str, Any]:
    url = urllib.parse.urljoin(f"{base_url.rstrip('/')}/", path.lstrip("/"))
    with urllib.request.urlopen(url, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8", errors="replace") or "{}")


def get_bytes(base_url: str, path: str, timeout: int = 30) -> tuple[bytes, str]:
    url = urllib.parse.urljoin(f"{base_url.rstrip('/')}/", path.lstrip("/"))
    with urllib.request.urlopen(url, timeout=timeout) as response:
        content_type = response.headers.get("Content-Type", "application/octet-stream").split(";")[0]
        return response.read(), content_type


def data_url_to_bytes(data_url: str) -> tuple[bytes, str]:
    match = re.match(r"^data:([^;]+);base64,(.+)$", data_url, re.S)
    if not match:
        raise ValueError("data URL image invalide")
    return base64.b64decode(match.group(2)), match.group(1)


def write_json(path: pathlib.Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def _project_path(out_dir: pathlib.Path, path: pathlib.Path) -> str:
    return f"assets/generated/{out_dir.name}/{path.relative_to(out_dir).as_posix()}"


def _storage_path(root: pathlib.Path, path: pathlib.Path) -> str:
    return path.relative_to(root).as_posix()


def _preview_url(out_dir: pathlib.Path, path: pathlib.Path) -> str:
    rel = urllib.parse.quote(path.relative_to(out_dir).as_posix(), safe="/")
    return f"/api/code/assets/file/{urllib.parse.quote(out_dir.name)}/{rel}"


def optimize_image(data: bytes, root: pathlib.Path, out_dir: pathlib.Path, name: str) -> dict[str, Any]:
    image = Image.open(io.BytesIO(data)).convert("RGB")
    widths = sorted({min(width, image.width) for width in (1400, 800, 480)}, reverse=True)
    formats = [("WEBP", "webp", "image/webp", {"quality": 86, "method": 6})]
    if features.check("avif"):
        formats.insert(0, ("AVIF", "avif", "image/avif", {"quality": 72}))

    variants: list[dict[str, Any]] = []
    for image_format, suffix, mime_type, options in formats:
        for width in widths:
            ratio = width / image.width
            height = max(1, round(image.height * ratio))
            resized = image.resize((width, height), Image.Resampling.LANCZOS)
            path = out_dir / "images" / f"{name}-{width}.{suffix}"
            path.parent.mkdir(parents=True, exist_ok=True)
            resized.save(path, image_format, **options)
            variants.append({
                "path": _project_path(out_dir, path),
                "storagePath": _storage_path(root, path),
                "previewUrl": _preview_url(out_dir, path),
                "width": width,
                "height": height,
                "mimeType": mime_type,
                "bytes": path.stat().st_size,
            })

    preferred = [variant for variant in variants if variant["mimeType"] == "image/avif"] or variants
    primary = max(preferred, key=lambda variant: int(variant["width"]))
    srcset = ", ".join(f"{variant['previewUrl']} {variant['width']}w" for variant in preferred)
    project_srcset = ", ".join(f"{variant['path']} {variant['width']}w" for variant in preferred)
    return {"primary": primary, "variants": variants, "srcset": srcset, "projectSrcset": project_srcset}


def build_flux_workflow(prompt: str, seed: int, width: int = 1280, height: int = 768) -> dict[str, Any]:
    """Workflow FLUX.2 valide par l'installation ComfyUI Aurora."""
    return {
        "11": {"class_type": "CLIPLoader", "inputs": {"clip_name": "mistral_3_small_flux2_fp8.safetensors", "type": "flux2"}},
        "12": {"class_type": "UNETLoader", "inputs": {"unet_name": "flux2_dev_fp8mixed.safetensors", "weight_dtype": "default"}},
        "10": {"class_type": "VAELoader", "inputs": {"vae_name": "flux2-vae.safetensors"}},
        "6": {"class_type": "CLIPTextEncode", "inputs": {"clip": ["11", 0], "text": prompt}},
        "33": {"class_type": "CLIPTextEncode", "inputs": {"clip": ["11", 0],
            "text": "watermark, random text, low detail, blurry, duplicated subject, split view, collage"}},
        "27": {"class_type": "EmptyFlux2LatentImage", "inputs": {"width": width, "height": height, "batch_size": 1}},
        "40": {"class_type": "Flux2Scheduler", "inputs": {"steps": 24, "width": width, "height": height}},
        "41": {"class_type": "KSamplerSelect", "inputs": {"sampler_name": "euler"}},
        "26": {"class_type": "CFGGuider", "inputs": {"model": ["12", 0], "positive": ["6", 0], "negative": ["33", 0], "cfg": 4.5}},
        "42": {"class_type": "RandomNoise", "inputs": {"noise_seed": seed}},
        "31": {"class_type": "SamplerCustomAdvanced", "inputs": {"noise": ["42", 0],
            "guider": ["26", 0], "sampler": ["41", 0], "sigmas": ["40", 0], "latent_image": ["27", 0]}},
        "8": {"class_type": "VAEDecode", "inputs": {"samples": ["31", 0], "vae": ["10", 0]}},
        "9": {"class_type": "SaveImage", "inputs": {"images": ["8", 0], "filename_prefix": "aurora_code_ws15"}},
    }


def generate_comfy_image(base_url: str, prompt: str, seed: int, timeout: int = 240) -> tuple[bytes, str, dict[str, Any]]:
    status = get_json(base_url, "/api/comfyui/status", timeout=8)
    if not status.get("running"):
        raise RuntimeError("ComfyUI indisponible")
    workflow = build_flux_workflow(prompt, seed)
    queued = post_json(base_url, "/proxy/comfy/prompt", {"prompt": workflow}, timeout=30)
    prompt_id = str(queued.get("prompt_id") or "")
    if not prompt_id:
        raise RuntimeError(f"ComfyUI n'a pas retourne de prompt_id: {queued}")

    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        history = get_json(base_url, f"/proxy/comfy/history/{prompt_id}", timeout=15)
        entry = history.get(prompt_id) or {}
        for output in (entry.get("outputs") or {}).values():
            images = output.get("images") or []
            if images:
                image = images[0]
                query = urllib.parse.urlencode({
                    "filename": image.get("filename", ""),
                    "subfolder": image.get("subfolder", ""),
                    "type": image.get("type", "output"),
                })
                data, mime_type = get_bytes(base_url, f"/api/comfyui/image?{query}", timeout=45)
                if len(data) < 2_000:
                    raise RuntimeError("image ComfyUI vide ou invalide")
                return data, mime_type, {"promptId": prompt_id, "output": image}
        time.sleep(2)
    raise TimeoutError(f"generation ComfyUI depassee ({timeout}s)")


def generate_image_asset(base_url: str, root: pathlib.Path, out_dir: pathlib.Path, prompt: str, seed: int) -> tuple[dict[str, Any] | None, dict[str, Any]]:
    started = time.monotonic()
    detail: dict[str, Any] = {"requestedEndpoint": "/api/comfyui/image", "queueEndpoint": "/proxy/comfy/prompt"}
    try:
        visual_prompt = (
            "Image-only editorial product photograph. Translate the brief into one concrete visual subject; "
            "never render the brief itself, a poster, a screen, or interface copy. "
            f"Subject brief: {prompt[:700]}. Premium coherent art direction, studio lighting, clean composition, "
            "blank unmarked surfaces, no typography, no title, no caption, no logo, no letters, no numbers."
        )
        raw, input_mime, provenance = generate_comfy_image(base_url, visual_prompt, seed)
        detail.update({"actualEndpoint": "/api/comfyui/image", "source": "comfyui-flux2", **provenance})
    except Exception as comfy_error:
        detail["comfyError"] = str(comfy_error)
        fallback = post_json(base_url, "/api/web/image", {
            "query": f"{prompt[:120]} premium product visual", "width": 1400, "height": 900,
        }, timeout=40)
        if not fallback.get("ok") or not fallback.get("dataUrl"):
            detail["error"] = fallback.get("error") or "image bridge failed"
            return None, detail
        raw, input_mime = data_url_to_bytes(str(fallback["dataUrl"]))
        detail.update({"actualEndpoint": "/api/web/image", "source": fallback.get("via") or "web"})

    optimized = optimize_image(raw, root, out_dir, "hero")
    primary = optimized["primary"]
    detail["durationMs"] = round((time.monotonic() - started) * 1000)
    return {
        "id": "image-hero",
        "kind": "image",
        "role": "hero",
        **primary,
        "sourceModule": "image",
        "bridgeEndpoint": str(detail["actualEndpoint"]),
        "requestedEndpoint": "/api/comfyui/image",
        "optimized": True,
        "srcset": optimized["srcset"],
        "projectSrcset": optimized["projectSrcset"],
        "variants": optimized["variants"],
        "metadata": {"seed": seed, "inputMimeType": input_mime, "source": detail.get("source")},
    }, detail


def latest_existing_glb(root: pathlib.Path, source_run_id: str = "") -> pathlib.Path | None:
    base = root / "output" / "3d" / "generations"
    search_root = base / slug(source_run_id) if source_run_id else base
    candidates = list(search_root.glob("**/*final_materials.glb")) or list(search_root.glob("**/*.glb"))
    valid = [path for path in candidates if path.is_file() and path.stat().st_size > 1024]
    return max(valid, key=lambda path: path.stat().st_mtime) if valid else None


def generate_3d_asset(
    base_url: str,
    root: pathlib.Path,
    out_dir: pathlib.Path,
    prompt: str,
    run_id: str,
    fresh: bool,
    allow_existing: bool,
    source_run_id: str,
    timeout: int,
) -> tuple[dict[str, Any] | None, dict[str, Any]]:
    """Delegue au client 3D qualite max (multi-vues TRELLIS + score/rescue/retry
    + nettoyage des intermediaires). Voir intermodule_3d_quality."""
    from intermodule_3d_quality import generate_quality_3d_asset

    return generate_quality_3d_asset(
        base_url=base_url, root=root, out_dir=out_dir, prompt=prompt, run_id=run_id,
        fresh=fresh, allow_existing=allow_existing, source_run_id=source_run_id,
        timeout=timeout, post=post_json, find_existing=latest_existing_glb,
        slugify=slug, project_path=_project_path, storage_path=_storage_path,
        preview_url=_preview_url,
    )


def generate_voice_asset(base_url: str, root: pathlib.Path, out_dir: pathlib.Path, prompt: str) -> tuple[dict[str, Any] | None, dict[str, Any]]:
    started = time.monotonic()
    detail: dict[str, Any] = {"requestedEndpoint": "/api/voice/tts", "fallbackEndpoint": "/api/voice/synthesize"}
    try:
        text = f"Presentation audio du projet : {prompt[:130]}."
        payload = post_json(base_url, "/api/voice/tts", {
            "text": text, "lang": "fr", "voice": "lyra-soft",
        }, timeout=180)
        if not payload.get("ok"):
            raise RuntimeError(str(payload.get("error") or "TTS echoue"))
        data, content_type = get_bytes(base_url, str(payload.get("audio_url") or "/api/voice/tts-audio"), timeout=45)
        if len(data) < 512:
            raise RuntimeError("audio TTS vide")
        target = out_dir / "voice" / "narration.wav"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        detail.update({"actualEndpoint": "/api/voice/tts", "durationMs": round((time.monotonic() - started) * 1000)})
        return {
            "id": "voice-narration",
            "kind": "voice",
            "role": "narration",
            "path": _project_path(out_dir, target),
            "storagePath": _storage_path(root, target),
            "previewUrl": _preview_url(out_dir, target),
            "mimeType": content_type or "audio/wav",
            "bytes": target.stat().st_size,
            "sourceModule": "voice",
            "bridgeEndpoint": "/api/voice/tts",
            "optimized": True,
            "metadata": {"engine": payload.get("engine"), "voice": payload.get("voice")},
        }, detail
    except Exception as error:
        detail["error"] = str(error)
        return None, detail


def build_bundle(payload: dict[str, Any]) -> dict[str, Any]:
    root = workspace_root()
    prompt = str(payload.get("prompt") or "Aurora premium product").strip()
    base_url = str(payload.get("baseUrl") or os.environ.get("AURORA_BRIDGE_URL") or "http://127.0.0.1:3001").rstrip("/")
    run_id = slug(str(payload.get("runId") or f"ws15_{int(time.time())}"))
    out_dir = root / "output" / "code_assets" / run_id
    out_dir.mkdir(parents=True, exist_ok=True)
    requested = requested_asset_kinds(payload, SUPPORTED_KINDS)
    seed = int(payload.get("seed") or randint(1, 2**32 - 1))
    assets: list[dict[str, Any]] = []
    routes: list[dict[str, Any]] = []

    producers: dict[str, Any] = {
        "image": lambda: reuse_or_generate(root, out_dir, str(payload.get("sourceImageRunId") or ""), "image", lambda: generate_image_asset(base_url, root, out_dir, prompt, seed)),
        "model3d": lambda: generate_3d_asset(
            base_url, root, out_dir, prompt, run_id,
            bool(payload.get("fresh3d", False)), bool(payload.get("allowExisting3d", True)),
            str(payload.get("source3dRunId") or ""), int(payload.get("threeDTimeoutSec") or 14_400),
        ),
        "voice": lambda: reuse_or_generate(root, out_dir, str(payload.get("sourceVoiceRunId") or ""), "voice", lambda: generate_voice_asset(base_url, root, out_dir, prompt)),
    }
    for kind in requested:
        asset, route = producers[kind]()
        route["kind"] = kind
        route["ok"] = asset is not None
        routes.append(route)
        if asset:
            assets.append(asset)

    rag = build_rag_trace(base_url, out_dir, prompt)
    routes.extend([
        {"kind": "vision", "requestedEndpoint": "/api/code/visual-audit", "ok": True, "status": "WS9 render judge available"},
        {"kind": "rag_reference", "requestedEndpoint": "/api/web/search", "fallbackEndpoint": "/api/web/extract", "ok": not bool(rag.get("error"))},
    ])
    produced = {asset["kind"] for asset in assets}
    missing = [kind for kind in requested if kind not in produced]
    bundle = {
        "schemaVersion": SCHEMA,
        "createdAt": int(time.time() * 1000),
        "runId": run_id,
        "prompt": prompt,
        "archetype": str(payload.get("archetype") or "default"),
        "outDir": _storage_path(root, out_dir),
        "requiredKinds": requested,
        "missingRequired": missing,
        "assets": assets,
        "routes": routes,
        "rag": rag,
        "deferred": [{
            "kind": "music_sfx",
            "reason": "Le bridge Aurora expose la voix/TTS, mais aucun service musique/SFX dedie pendant WS15.",
        }],
    }
    write_json(out_dir / "asset-bundle.json", bundle)
    return bundle


def main() -> int:
    payload = json.loads(sys.stdin.read() or "{}")
    bundle = build_bundle(payload)
    print(json.dumps(bundle, ensure_ascii=False))
    return 0 if not bundle["missingRequired"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
