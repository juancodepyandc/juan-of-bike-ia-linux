#!/usr/bin/env python3
"""AuroraIA High-Precision Image & Asset Generation Engine

Generates structured 2-level subject packages:
application/output/image/<category>/<subject_slug>/
  ├── image.png                 # Master high-resolution render
  ├── prompt.txt                # Raw and human art-directed prompts
  ├── metadata.json             # Complete technical specs & QA scores
  ├── palette.json              # Extracted color palette
  ├── README.md                 # Project documentation & integration guide
  ├── asset_isolated_alpha.png  # (For assets/icons/props) Alpha cutout
  ├── icon_512x512.png          # (For assets/icons) UI Mipmaps
  ├── icon_256x256.png
  ├── icon_128x128.png
  ├── icon_64x64.png
  ├── avatar_crop_512x512.png   # (For perso) Focused face avatar
  ├── detail_macro_crop.png     # (For perso) High-frequency zoom
  ├── seamless_2x2_tiling.png   # (For textures) Continuous 2x2 pattern test
  └── normal_map_simulated.png  # (For textures) PBR normal map
"""

from __future__ import annotations
import argparse
import json
import os
import re
import sys
import time
import urllib.request
import urllib.parse
import urllib.error
import shutil
from pathlib import Path
from typing import Dict, Any, Optional, Tuple, List
from PIL import Image, ImageOps, ImageFilter
import numpy as np

from human_prompt_director import direct_prompt, detect_category

REPO_ROOT = Path(__file__).resolve().parents[2]
BASE_OUTPUT_DIR = REPO_ROOT / "application" / "output" / "image"
COMFY_BASE = "http://127.0.0.1:8188"

DEFAULT_CLIP = "mistral_3_small_flux2_fp8.safetensors"
DEFAULT_UNET = "flux2-dev-Q4_K_M.gguf"
DEFAULT_VAE = "flux2-vae.safetensors"
CLIP_DEVICE = "cpu"

def slugify(text: str) -> str:
    s = re.sub(r"[^\w\s-]", "", text.lower())
    return re.sub(r"[-\s]+", "_", s).strip("_")[:40]

def resolve_main_folder(category: str, raw_text: str = "") -> str:
    c = category.lower()
    t = raw_text.lower()
    if "edit" in c or "retouche" in t or "inpaint" in t:
        return "edits"
    if any(k in c or k in t for k in ["asset", "coffre", "chest", "tresor", "trésor", "potion", "prop", "sprite", "pixel", "isometric", "icon", "texture", "sol_pave", "weapon", "arme", "bouclier", "shield"]):
        return "assets"
    if any(k in c or k in t for k in ["perso", "portrait", "visage", "guerrier", "guerriere", "samourai", "samouraï", "femme", "homme", "personne", "ingenieur", "ingénieure", "artisan", "horloger", "dragon", "duel", "avatar", "manga", "pixar"]):
        return "perso"
    if any(k in c or k in t for k in ["decor", "décors", "paysage", "cite", "cité", "solarpunk", "ruelle", "ville", "temple", "prairie", "train", "ghibli", "concept"]):
        return "decor"
    return "perso" if "photo" in c else "decor"

def unload_ollama_memory() -> None:
    """Evicts any resident Ollama models from RAM/VRAM before loading FLUX."""
    base = os.environ.get("OLLAMA_URL", "http://127.0.0.1:11434")
    try:
        req = urllib.request.Request(f"{base}/api/ps")
        with urllib.request.urlopen(req, timeout=5) as r:
            loaded = json.loads(r.read().decode("utf-8")).get("models", [])
        for m in loaded:
            evict_req = urllib.request.Request(
                f"{base}/api/generate",
                data=json.dumps({"model": m.get("name"), "keep_alive": 0}).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST"
            )
            with urllib.request.urlopen(evict_req, timeout=10) as rr:
                rr.read()
        if loaded:
            print(f"[Memory] Unloaded {len(loaded)} Ollama model(s) to optimize GPU headroom.", flush=True)
    except Exception:
        pass

# --- QUALITY ASSURANCE & AFFINITY METRICS ---

def calculate_sharpness(im: Image.Image) -> float:
    gray = np.array(im.convert("L"), dtype=np.float32)
    h, w = gray.shape
    pad = np.pad(gray, 1, mode="edge")
    lap = (
        pad[0:h, 1:w+1] + pad[2:h+2, 1:w+1] +
        pad[1:h+1, 0:w] + pad[1:h+1, 2:w+2] -
        4 * pad[1:h+1, 1:w+1]
    )
    return float(np.var(lap))

def calculate_contrast(im: Image.Image) -> float:
    gray = np.array(im.convert("L"), dtype=np.float32)
    return float(np.std(gray))

def calculate_tileability_error(im: Image.Image) -> float:
    arr = np.array(im.convert("RGB"), dtype=np.float32)
    h_diff = np.mean((arr[:, 0, :] - arr[:, -1, :]) ** 2)
    v_diff = np.mean((arr[0, :, :] - arr[-1, :, :]) ** 2)
    return float((h_diff + v_diff) / 2.0)

def calculate_dominant_palette(im: Image.Image, count: int = 6) -> List[str]:
    small = im.convert("RGB").resize((64, 64))
    colors = small.getcolors(maxcolors=4096)
    if colors:
        colors.sort(key=lambda c: c[0], reverse=True)
        return [f"#{c[1][0]:02x}{c[1][1]:02x}{c[1][2]:02x}" for c in colors[:count]]
    return ["#12141a", "#1a1e28", "#242a38"]

def compute_normal_map(gray_arr: np.ndarray) -> Image.Image:
    h, w = gray_arr.shape
    pad = np.pad(gray_arr, 1, mode="edge")
    dx = (pad[0:h, 2:w+2] + 2 * pad[1:h+1, 2:w+2] + pad[2:h+2, 2:w+2]) - \
         (pad[0:h, 0:w] + 2 * pad[1:h+1, 0:w] + pad[2:h+2, 0:w])
    dy = (pad[2:h+2, 0:w] + 2 * pad[2:h+2, 1:w+1] + pad[2:h+2, 2:w+2]) - \
         (pad[0:h, 0:w] + 2 * pad[0:h, 1:w+1] + pad[0:h, 2:w+2])
    dx = dx / 8.0
    dy = dy / 8.0
    dz = np.ones_like(dx) * 32.0
    norm = np.sqrt(dx**2 + dy**2 + dz**2)
    nx = (dx / norm * 0.5 + 0.5) * 255.0
    ny = (-dy / norm * 0.5 + 0.5) * 255.0
    nz = (dz / norm * 0.5 + 0.5) * 255.0
    rgb = np.stack([nx, ny, nz], axis=2).astype(np.uint8)
    return Image.fromarray(rgb)

# --- COMFYUI FLUX WORKFLOW BUILDER ---

def build_comfy_flux_workflow(
    prompt: str,
    negative_prompt: str,
    width: int,
    height: int,
    steps: int,
    guidance: float,
    seed: int,
    prefix: str
) -> Dict[str, Any]:
    workflow = {
        "11": {
            "class_type": "CLIPLoader",
            "inputs": {
                "clip_name": DEFAULT_CLIP,
                "type": "flux2",
                "device": CLIP_DEVICE
            }
        },
        "12": {
            "class_type": "UnetLoaderGGUF",
            "inputs": {
                "unet_name": DEFAULT_UNET
            }
        },
        "10": {
            "class_type": "VAELoader",
            "inputs": {
                "vae_name": DEFAULT_VAE
            }
        },
        "6": {
            "class_type": "CLIPTextEncode",
            "inputs": {
                "clip": ["11", 0],
                "text": prompt
            }
        },
        "33": {
            "class_type": "CLIPTextEncode",
            "inputs": {
                "clip": ["11", 0],
                "text": negative_prompt
            }
        },
        "27": {
            "class_type": "EmptyFlux2LatentImage",
            "inputs": {
                "width": width,
                "height": height,
                "batch_size": 1
            }
        },
        "40": {
            "class_type": "Flux2Scheduler",
            "inputs": {
                "steps": steps,
                "width": width,
                "height": height
            }
        },
        "41": {
            "class_type": "KSamplerSelect",
            "inputs": {
                "sampler_name": "euler"
            }
        },
        "26": {
            "class_type": "CFGGuider",
            "inputs": {
                "model": ["12", 0],
                "positive": ["6", 0],
                "negative": ["33", 0],
                "cfg": guidance
            }
        },
        "42": {
            "class_type": "RandomNoise",
            "inputs": {
                "noise_seed": seed
            }
        },
        "31": {
            "class_type": "SamplerCustomAdvanced",
            "inputs": {
                "noise": ["42", 0],
                "guider": ["26", 0],
                "sampler": ["41", 0],
                "sigmas": ["40", 0],
                "latent_image": ["27", 0]
            }
        },
        "8": {
            "class_type": "VAEDecode",
            "inputs": {
                "samples": ["31", 0],
                "vae": ["10", 0]
            }
        },
        "9": {
            "class_type": "SaveImage",
            "inputs": {
                "images": ["8", 0],
                "filename_prefix": prefix
            }
        }
    }
    sys.path.insert(0, str(REPO_ROOT))
    from auto_rl.image_runtime import apply_validated_workflow
    return apply_validated_workflow(workflow)


def submit_comfy_prompt(workflow: Dict[str, Any]) -> Optional[str]:
    unload_ollama_memory()
    try:
        data = json.dumps({"prompt": workflow}).encode("utf-8")
        req = urllib.request.Request(
            f"{COMFY_BASE}/prompt",
            data=data,
            headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(req, timeout=20) as resp:
            res = json.loads(resp.read().decode("utf-8"))
            return res.get("prompt_id")
    except Exception as exc:
        print(f"[ComfyUI] Queue error: {exc}")
        return None

def wait_for_comfy_image(prompt_id: str, timeout_s: int = 1200) -> Optional[bytes]:
    start = time.time()
    while time.time() - start < timeout_s:
        try:
            req = urllib.request.Request(f"{COMFY_BASE}/history/{prompt_id}")
            with urllib.request.urlopen(req, timeout=5) as resp:
                hist = json.loads(resp.read().decode("utf-8"))
                if prompt_id in hist:
                    outputs = hist[prompt_id].get("outputs", {})
                    for node_id, node_out in outputs.items():
                        images = node_out.get("images", [])
                        if images:
                            fn = images[0].get("filename")
                            sub = images[0].get("subfolder", "")
                            t = images[0].get("type", "output")
                            qs = urllib.parse.urlencode({"filename": fn, "subfolder": sub, "type": t})
                            img_req = urllib.request.Request(f"{COMFY_BASE}/view?{qs}")
                            with urllib.request.urlopen(img_req, timeout=15) as img_resp:
                                return img_resp.read()
        except Exception:
            pass
        time.sleep(2.0)
    return None

# --- MAIN GENERATION PIPELINE ---

def generate_image_manifest(
    raw_prompt: str,
    output_dir: Optional[Path] = None,
    seed: Optional[int] = None,
    force_category: Optional[str] = None,
    use_comfy: bool = True
) -> Dict[str, Any]:
    start_time = time.time()
    
    spec = direct_prompt(raw_prompt)
    if force_category:
        spec["category"] = force_category
        
    category = spec["category"]
    main_cat = resolve_main_folder(category, raw_prompt)
    slug = slugify(raw_prompt)
    
    subject_dir = (output_dir or (BASE_OUTPUT_DIR / main_cat / slug))
    
    ts = int(time.time())
    run_seed = seed if seed is not None else (ts % 1000000000)
    
    master_png = subject_dir / "image.png"
    prompt_txt = subject_dir / "prompt.txt"
    metadata_json = subject_dir / "metadata.json"
    palette_json = subject_dir / "palette.json"
    readme_md = subject_dir / "README.md"
    
    w, h = spec["width"], spec["height"]
    img_data: Optional[bytes] = None
    engine_name = "simulation"
    
    if use_comfy:
        try:
            req = urllib.request.Request(f"{COMFY_BASE}/system_stats")
            with urllib.request.urlopen(req, timeout=3) as resp:
                if resp.status == 200:
                    wf = build_comfy_flux_workflow(
                        prompt=spec["human_prompt"],
                        negative_prompt=spec["negative_prompt"],
                        width=w,
                        height=h,
                        steps=spec["steps"],
                        guidance=spec["guidance"],
                        seed=run_seed,
                        prefix=f"aurora_{slug[:18]}"
                    )
                    p_id = submit_comfy_prompt(wf)
                    if p_id:
                        print(f"[ComfyUI] Job {p_id} queued on CUDA ({w}x{h}, {spec['steps']} steps)...")
                        img_data = wait_for_comfy_image(p_id, timeout_s=360)
                        if img_data:
                            engine_name = "flux2_dev_comfyui_cuda"
        except Exception as exc:
            raise RuntimeError(f"ComfyUI generation failed: {exc}") from exc
        if not img_data:
            raise RuntimeError("ComfyUI produced no image; the package was not published")
            
    if img_data:
        import io
        img = Image.open(io.BytesIO(img_data)).convert("RGB")
    else:
        # Explicit offline simulation for tests and package previews.
        arr = np.zeros((h, w, 3), dtype=np.float32)
        if category == "photo_realistic":
            for y in range(h):
                t = y / h
                arr[y, :, 0] = 36 * (1 - t) + 20 * t
                arr[y, :, 1] = 42 * (1 - t) + 25 * t
                arr[y, :, 2] = 52 * (1 - t) + 32 * t
        elif "game_asset" in category:
            arr[:, :] = [16, 18, 24]
        elif "cyberpunk" in category:
            arr[:, :] = [10, 12, 24]
        else:
            arr[:, :] = [28, 26, 32]
        img = Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8))
        
    subject_dir.mkdir(parents=True, exist_ok=True)
    img.save(master_png)
    
    # 1. Save prompt.txt
    prompt_txt.write_text(
        f"=== TITRE DU PROJET : {spec['title']} ===\n"
        f"Catégorie Principale : {main_cat}\n"
        f"Sous-Catégorie : {category}\n\n"
        f"[DEMANDE UTILISATEUR]\n{raw_prompt}\n\n"
        f"[PROMPT DIRECTION ARTISTIQUE HUMAINE]\n{spec['human_prompt']}\n\n"
        f"[PROMPT NÉGATIF]\n{spec['negative_prompt']}\n",
        encoding="utf-8"
    )
    
    # 2. Extract Palette
    palette = calculate_dominant_palette(img, count=8)
    with open(palette_json, "w", encoding="utf-8") as f:
        json.dump({"dominant_palette_hex": palette, "primary_color": palette[0] if palette else "#000000"}, f, indent=2)
        
    # 3. Generate subject-specific derived assets
    derived_files = []
    
    if main_cat == "assets" or "icon" in category or "asset" in category or "sprite" in category or "isometric" in category:
        arr = np.array(img.convert("RGBA"))
        r, g, b = arr[:, :, 0], arr[:, :, 1], arr[:, :, 2]
        is_bg = ((r > 240) & (g > 240) & (b > 240)) | ((r < 30) & (g < 35) & (b < 40))
        arr[is_bg, 3] = 0
        alpha_im = Image.fromarray(arr)
        alpha_path = subject_dir / "asset_isolated_alpha.png"
        alpha_im.save(alpha_path)
        derived_files.append("asset_isolated_alpha.png")
        
        for sz in [512, 256, 128, 64]:
            ico = alpha_im.resize((sz, sz), Image.Resampling.LANCZOS)
            ico_path = subject_dir / f"icon_{sz}x{sz}.png"
            ico.save(ico_path)
            derived_files.append(f"icon_{sz}x{sz}.png")
            
    if "texture" in category:
        tile_2x2 = Image.new("RGB", (w * 2, h * 2))
        tile_2x2.paste(img, (0, 0))
        tile_2x2.paste(img, (w, 0))
        tile_2x2.paste(img, (0, h))
        tile_2x2.paste(img, (w, h))
        tile_path = subject_dir / "seamless_2x2_tiling.png"
        tile_2x2.save(tile_path)
        derived_files.append("seamless_2x2_tiling.png")
        
        gray = np.array(img.convert("L"), dtype=np.float32)
        normal_im = compute_normal_map(gray)
        normal_path = subject_dir / "normal_map_simulated.png"
        normal_im.save(normal_path)
        derived_files.append("normal_map_simulated.png")
        
        height_im = img.convert("L")
        height_path = subject_dir / "height_map.png"
        height_im.save(height_path)
        derived_files.append("height_map.png")
        
    if main_cat == "perso" or "photo" in category or "portrait" in category:
        crop_sz = min(w, h)
        left = (w - crop_sz) // 2
        top = 0
        avatar = img.crop((left, top, left + crop_sz, top + crop_sz)).resize((512, 512), Image.Resampling.LANCZOS)
        avatar_path = subject_dir / "avatar_crop_512x512.png"
        avatar.save(avatar_path)
        derived_files.append("avatar_crop_512x512.png")
        
        cx, cy = w // 2, h // 3
        d_crop = img.crop((max(0, cx - 200), max(0, cy - 200), min(w, cx + 200), min(h, cy + 200)))
        d_path = subject_dir / "detail_macro_crop.png"
        d_crop.save(d_path)
        derived_files.append("detail_macro_crop.png")
        
    if main_cat == "decor" or "cyberpunk" in category or "stylized" in category:
        card = img.resize((600, 400), Image.Resampling.LANCZOS)
        card_path = subject_dir / "card_preview_600x400.png"
        card.save(card_path)
        derived_files.append("card_preview_600x400.png")
        
    sharpness = calculate_sharpness(img)
    contrast = calculate_contrast(img)
    tile_error = calculate_tileability_error(img) if category == "game_asset_texture" else None
    elapsed_ms = int((time.time() - start_time) * 1000)
    quality_status = "MEASURED_NOT_EVALUATED" if use_comfy else "SIMULATED_NOT_EVALUATED"
    
    # 4. Save metadata.json
    manifest = {
        "id": f"pkg_{ts}_{slug}",
        "subject_slug": slug,
        "main_category": main_cat,
        "title": spec["title"],
        "category": category,
        "raw_user_prompt": raw_prompt,
        "human_art_directed_prompt": spec["human_prompt"],
        "negative_prompt": spec["negative_prompt"],
        "dimensions": {
            "width": w,
            "height": h,
            "aspect_ratio": spec["aspect_ratio"]
        },
        "generation_params": {
            "steps": spec["steps"],
            "guidance": spec["guidance"],
            "seed": run_seed,
            "engine": engine_name
        },
        "game_asset_metadata": spec.get("game_asset_meta"),
        "quality_assurance_metrics": {
            "sharpness_laplacian_variance": round(sharpness, 2),
            "contrast_std": round(contrast, 2),
            "dominant_palette_hex": palette,
            "seamless_tileability_mse": round(tile_error, 2) if tile_error is not None else None,
            "status": quality_status
        },
        "quality_checklist": spec["quality_checklist"],
        "package_files": {
            "directory": str(subject_dir),
            "relative_dir": f"image/{main_cat}/{slug}",
            "master_image": str(master_png),
            "prompt_file": str(prompt_txt),
            "metadata_file": str(metadata_json),
            "palette_file": str(palette_json),
            "readme_file": str(readme_md),
            "derived_files": derived_files
        },
        "metrics": {
            "generation_time_ms": elapsed_ms,
            "timestamp": ts
        }
    }
    with open(metadata_json, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)
        
    # 5. Save README.md
    readme_content = f"""# 📦 Package Sujet : {spec['title']}

**Dossier** : `output/image/{main_cat}/{slug}/`  
**Catégorie** : `{main_cat}` / `{category}`  
**Résolution Master** : `{w}x{h}` ({spec['aspect_ratio']})  
**Moteur d'Inférence** : `{engine_name}`  

---

## 🎯 Prompts & Direction Artistique

### Demande Originale :
> {raw_prompt}

### Synthèse Art Director :
```text
{spec['human_prompt']}
```

---

## 📁 Contenu du Pack

| Fichier | Rôle / Description |
| :--- | :--- |
| [`image.png`](./image.png) | **Master Render** haute résolution |
| [`prompt.txt`](./prompt.txt) | Traçabilité des prompts d'entrée |
| [`metadata.json`](./metadata.json) | Paramètres de génération complets (graine, moteur, étapes) |
| [`palette.json`](./palette.json) | Nuancier des teintes dominantes ({', '.join(palette[:4])}) |
"""
    for df in derived_files:
        readme_content += f"| [`{df}`](./{df}) | Fichier dérivé optimisé ({df.split('.')[0]}) |\n"

    readme_content += f"""
---

## 📊 Métriques d'Assurance Qualité
- **Variance du Laplacien (Netteté)** : `{sharpness:.2f}`
- **Écart-Type de Luminance (Contraste)** : `{contrast:.2f}`
- **Statut** : `{quality_status}`
"""
    readme_md.write_text(readme_content, encoding="utf-8")
    
    print(f"SUCCESS: Created Category/Subject Package -> {subject_dir} ({len(derived_files) + 5} files)")
    return manifest

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Aurora Image Module Engine")
    parser.add_argument("prompt", type=str, help="User prompt description")
    parser.add_argument("--category", type=str, default=None, help="Force category")
    parser.add_argument("--seed", type=int, default=None, help="Random seed")
    parser.add_argument("--no-comfy", action="store_true", help="Disable ComfyUI live queue")
    args = parser.parse_args()
    
    manifest = generate_image_manifest(
        args.prompt,
        force_category=args.category,
        seed=args.seed,
        use_comfy=not args.no_comfy
    )
    print(json.dumps(manifest, indent=2, ensure_ascii=False))
