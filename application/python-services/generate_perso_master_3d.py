#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""generate_perso_master_3d.py — Génération 3D Master Haute Fidélité pour la Caricature Juan.

Combine :
1. TRELLIS.2 (1536_cascade) pour la géométrie et les mèches de boucles.
2. Blender Orthographic Texture Projection pour la netteté vectorielle 4K de la face et du dos.
3. Rendu de vérification Cycles 4 vues.
"""
from __future__ import annotations

import os
import sys
import time
import logging
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("perso_master_3d")

REPO_ROOT = Path(__file__).resolve().parents[2]
SERVICES_DIR = REPO_ROOT / "application" / "python-services"
HUNYUAN_DIR = SERVICES_DIR / "aurora_hunyuan"

sys.path.insert(0, str(HUNYUAN_DIR))
sys.path.insert(0, str(SERVICES_DIR))

import aurora_trellis_wrapper as atw


def main():
    front_img = REPO_ROOT / "application" / "output" / "3d" / "perso_vizion_4k" / "perso_master_front.png"
    back_img = REPO_ROOT / "application" / "output" / "3d" / "perso_vizion_4k" / "perso_master_back.png"
    out_dir = REPO_ROOT / "application" / "output" / "3d" / "perso_vizion_4k"
    out_dir.mkdir(parents=True, exist_ok=True)
    
    raw_glb = out_dir / "perso_trellis_raw.glb"
    final_glb = out_dir / "perso_vizion_master.glb"
    
    log.info("=== STEP 1/3: TRELLIS.2 1536_cascade 3D Mesh Generation ===")
    t0 = time.time()
    
    # Run Trellis with high quality
    res = atw.generate_glb(
        image_path=front_img,
        out_glb=raw_glb,
        pipeline_type="1536_cascade",
        texture_size=4096,
        decimation_target=800_000,
        extra_views=[back_img],
        seed=42,
    )
    log.info(f"TRELLIS.2 Result: {res}")
    
    if not res.get("ok") or not raw_glb.is_file():
        log.warning(f"TRELLIS.2 1536 fallback: {res.get('error')}")
        res = atw.generate_glb(
            image_path=front_img,
            out_glb=raw_glb,
            pipeline_type="1024_cascade",
            texture_size=4096,
            decimation_target=500_000,
            seed=42,
        )
        log.info(f"TRELLIS.2 1024_cascade Result: {res}")

    if not raw_glb.is_file():
        log.error("TRELLIS.2 did not produce a GLB.")
        sys.exit(1)

    log.info(f"TRELLIS.2 completed in {time.time() - t0:.1f}s — Mesh: {raw_glb.stat().st_size / 1024 / 1024:.2f} MB")
    
    log.info("=== STEP 2/3: Direct High-Fidelity 4K Texture Projection (Front & Back) ===")
    try:
        import subprocess
        fidelity_script = SERVICES_DIR / "texture_fidelity.py"
        if fidelity_script.is_file():
            cmd = [
                sys.executable, str(fidelity_script),
                "--mesh", str(raw_glb),
                "--photo", str(front_img),
                "--output", str(final_glb),
                "--size", "4096",
            ]
            log.info(f"Running texture fidelity: {' '.join(cmd)}")
            p = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
            log.info(f"Fidelity stdout: {p.stdout}")
            if p.returncode != 0:
                log.warning(f"Fidelity stderr: {p.stderr}")
                import shutil
                shutil.copy(raw_glb, final_glb)
        else:
            import shutil
            shutil.copy(raw_glb, final_glb)
    except Exception as exc:
        log.warning(f"Texture fidelity step error: {exc}")
        import shutil
        shutil.copy(raw_glb, final_glb)

    log.info("=== STEP 3/3: Renders de vérification 4 vues (Cycles) ===")
    views_dir = out_dir / "verifications"
    views_dir.mkdir(exist_ok=True)
    
    render_script = f"""
import bpy, math
from mathutils import Vector

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath="{final_glb}")

meshes = [o for o in bpy.context.scene.objects if o.type == "MESH"]
if not meshes:
    raise RuntimeError("No mesh in imported scene")
ob = max(meshes, key=lambda o: len(o.data.polygons))

verts = [ob.matrix_world @ v.co for v in ob.data.vertices]
mn = Vector(map(min, *verts))
mx = Vector(map(max, *verts))
center = (mn + mx) * 0.5
size = mx - mn
max_dim = max(size.x, size.y, size.z)

cam_data = bpy.data.cameras.new("Cam")
cam = bpy.data.objects.new("Cam", cam_data)
bpy.context.scene.collection.objects.link(cam)
bpy.context.scene.camera = cam

world = bpy.data.worlds.new("StudioWorld")
world.use_nodes = True
world.node_tree.nodes["Background"].inputs[0].default_value = (0.08, 0.08, 0.09, 1.0)
world.node_tree.nodes["Background"].inputs[1].default_value = 1.0
bpy.context.scene.world = world

key_light = bpy.data.lights.new("KeyLight", type="AREA")
key_light.energy = 180.0
key_light.size = 2.0
key_ob = bpy.data.objects.new("KeyLight", key_light)
key_ob.location = (center.x + max_dim * 1.5, center.y - max_dim * 2.0, center.z + max_dim * 1.5)
bpy.context.scene.collection.objects.link(key_ob)

fill_light = bpy.data.lights.new("FillLight", type="AREA")
fill_light.energy = 80.0
fill_light.size = 2.5
fill_ob = bpy.data.objects.new("FillLight", fill_light)
fill_ob.location = (center.x - max_dim * 1.5, center.y - max_dim * 1.5, center.z + max_dim * 0.5)
bpy.context.scene.collection.objects.link(fill_ob)

rim_light = bpy.data.lights.new("RimLight", type="AREA")
rim_light.energy = 220.0
rim_light.size = 1.8
rim_ob = bpy.data.objects.new("RimLight", rim_light)
rim_ob.location = (center.x, center.y + max_dim * 2.0, center.z + max_dim * 1.2)
bpy.context.scene.collection.objects.link(rim_ob)

bpy.context.scene.render.engine = "CYCLES"
bpy.context.scene.cycles.device = "GPU"
bpy.context.scene.cycles.samples = 64
bpy.context.scene.render.resolution_x = 1024
bpy.context.scene.render.resolution_y = 1024

dist = max_dim * 2.2
angles = [("vue_front", 0), ("vue_right", 90), ("vue_back", 180), ("vue_left", 270)]

for name, deg in angles:
    rad = math.radians(deg)
    cx = center.x + dist * math.sin(rad)
    cy = center.y - dist * math.cos(rad)
    cz = center.z + size.z * 0.05
    cam.location = Vector((cx, cy, cz))
    
    direction = center - cam.location
    rot_quat = direction.to_track_quat('-Z', 'Y')
    cam.rotation_euler = rot_quat.to_euler()
    
    out_path = "{views_dir}/" + name + ".png"
    bpy.context.scene.render.filepath = out_path
    bpy.ops.render.render(write_still=True)
    print(f"Rendered: {out_path}")
"""
    try:
        import subprocess
        p = subprocess.run(["blender", "-b", "--python-expr", render_script], capture_output=True, text=True, timeout=120)
        log.info(f"Blender render stdout: {p.stdout[-500:] if p.stdout else ''}")
    except Exception as exc:
        log.warning(f"Blender render error: {exc}")

    log.info(f"=== ALL DONE! Final GLB available at: {final_glb} ===")


if __name__ == "__main__":
    main()
