"""Aurora multi-scene loop with robust topology repair.

For each scene:
1. Run image generation + shape generation
2. Audit shape geometry via Blender (blender_mesh_auditor.py)
3. If topology fails (non-manifold, floaters), run blender_mesh_repair.py
4. Run texture generation
5. Final critic score (texture, silhouette)
6. Commit
"""
from __future__ import annotations

import argparse
import json
import logging
import shutil
import subprocess
import sys
import time
from dataclasses import asdict
from pathlib import Path

from aurora_classify import classify
from aurora_critic import evaluate
import pipeline_hunyuan_robust as pipeline

REPO = Path(__file__).resolve().parent
AURORA = Path(r"C:\Users\Juan\Desktop\ia\AuroraIA-v2")
BLENDER = AURORA / "application" / "_blender" / "blender-4.2.12-windows-x64" / "blender.exe"
STATE = REPO / "aurora_state_robust.json"

log = logging.getLogger("loop_robust")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

DEFAULT_QUEUE: list[dict[str, str]] = [
    {"prompt": "a steampunk brass mechanical clockwork dragon with spinning gears", "name": "steampunk_clockwork_dragon"},
    {"prompt": "a glowing crystal lantern floating in fog at night, mystic", "name": "crystal_lantern_fog"},
]

def load_state() -> dict:
    if STATE.exists():
        return json.loads(STATE.read_text(encoding="utf-8"))
    return {"completed": [], "failed": []}

def save_state(state: dict) -> None:
    STATE.write_text(json.dumps(state, indent=2, ensure_ascii=False), encoding="utf-8")

def audit_shape(glb_path: Path) -> dict:
    audit_json = glb_path.with_name("audit.json")
    cmd = [str(BLENDER), "--background", "--python", str(REPO / "blender_mesh_auditor.py"), "--", str(glb_path), str(audit_json)]
    subprocess.run(cmd, capture_output=True, text=True)
    if audit_json.exists():
        return json.loads(audit_json.read_text())
    return {"error": "Audit JSON not produced"}

def repair_shape(glb_path: Path) -> Path:
    out_glb = glb_path.with_name(glb_path.stem + "_repaired.glb")
    cmd = [str(BLENDER), "--background", "--python", str(REPO / "blender_mesh_repair.py"), "--", str(glb_path), str(out_glb)]
    res = subprocess.run(cmd, capture_output=True, text=True)
    if out_glb.exists():
        return out_glb
    log.error(f"Repair failed: {res.stderr}")
    return glb_path

def process_scene(prompt: str, name: str, device: str = "cuda") -> bool:
    log.info(f"=== Starting {name} on {device} ===")
    profile = classify(prompt, name)
    pack_dir = pipeline.OUTPUT_ROOT / f"pbr_{profile.name}_pack"
    pack_dir.mkdir(parents=True, exist_ok=True)
    
    profile_path = pack_dir / "profile.json"
    profile_path.write_text(json.dumps(asdict(profile), indent=2, ensure_ascii=False))
    
    img_clean_path = pack_dir / "input_nobg.png"
    shape_glb = pack_dir / f"shape_{profile.name}.glb"
    final_glb = pack_dir / f"pbr_{profile.name}_proc.glb"
    
    # 1. Image
    raw_img = pack_dir / "input.png"
    if not img_clean_path.exists():
        pipeline.run_image_gen(profile.prompt_image, raw_img, device=device)
        pipeline.boost_and_rembg(raw_img, img_clean_path)
        
    # 2. Shape
    if not shape_glb.exists():
        pipeline.run_shape_gen(img_clean_path, shape_glb, device=device)
        
    # 3. Audit & Repair
    audit = audit_shape(shape_glb)
    log.info(f"Shape Audit: {audit}")
    needs_repair = False
    if audit.get("non_manifold_edges", 0) > 0: needs_repair = True
    if audit.get("degenerated_faces", 0) > 0: needs_repair = True
    if audit.get("parts_count", 1) > 1: needs_repair = True
    
    if needs_repair:
        log.warning("Shape geometry is flawed. Triggering Blender repair...")
        repaired_glb = repair_shape(shape_glb)
        if repaired_glb != shape_glb:
            # Swap
            shape_glb.unlink()
            repaired_glb.rename(shape_glb)
            audit2 = audit_shape(shape_glb)
            log.info(f"Shape Audit After Repair: {audit2}")
            
    # 4. Texture
    if not final_glb.exists():
        pipeline.run_tex_gen(shape_glb, img_clean_path, final_glb, device=device)
        
    # 5. Animate
    pipeline.run_blender_animate(final_glb, profile_path, pack_dir)
    
    # Final Critic (Texture, exposure, etc)
    crit = evaluate(pack_dir, min_score=0.60)
    log.info(f"Final Critic Score: {crit['score']}")
    
    # Git Commit
    subprocess.run(["git", "-C", str(AURORA), "add", "-f", str(pack_dir)], check=False, capture_output=True)
    msg = f"feat: {name} Robust PBR pack (score {crit['score']:.2f})"
    subprocess.run(["git", "-C", str(AURORA), "commit", "-m", msg], check=False, capture_output=True)
    return True

def run_queue(queue: list[dict[str, str]], device: str = "cuda") -> None:
    state = load_state()
    for entry in queue:
        name = entry["name"]
        if name in state["completed"]:
            continue
        ok = process_scene(entry["prompt"], name, device=device)
        if ok:
            state["completed"].append(name)
        else:
            state["failed"].append(name)
        save_state(state)

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--default-queue", action="store_true")
    ap.add_argument("--prompt", help="Texte pour générer une scène spécifique")
    ap.add_argument("--name", help="Nom de la scène spécifique")
    ap.add_argument("--safe-mode", action="store_true", help="Run entirely on CPU with 0%% crash risk")
    ap.add_argument("--device", default=None, help="Force execution device (cpu or cuda)")
    args = ap.parse_args()
    
    import os
    # Environment variable check as a global fallback
    env_safe = os.environ.get("AURORA_SAFE_MODE", "0") == "1" or os.environ.get("AURORA_USE_CPU", "0") == "1"
    
    device = "cpu" if (args.safe_mode or args.device == "cpu" or env_safe) else "cuda"
    if args.device == "cuda":
        device = "cuda"
    
    if args.default_queue:
        run_queue(DEFAULT_QUEUE, device=device)
    elif args.prompt and args.name:
        process_scene(args.prompt, args.name, device=device)
    else:
        print("Usage: python aurora_loop_robust.py --default-queue OR --prompt \"...\" --name \"...\" [--safe-mode]")
