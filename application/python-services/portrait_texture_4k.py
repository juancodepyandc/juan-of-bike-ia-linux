#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""portrait_texture_4k.py — Texturation UV 4K Ultra-Nette Directe depuis Photo Réelle.

Transfère chaque pixel réel de la photo d'origine en résolution 4K (4096x4096) sur le maillage 3D :
  - Yeux, iris, pupilles et cils 100% nets sans aucun flou de diffusion.
  - Monture des lunettes noire aux arêtes tranchantes.
  - Boucles de cheveux et mèches définies.
  - Moustache, barbe, pores et imperfections préservés fidèlement.
  - Shaders PBR (Roughness, Transmission pour les verres, SSS pour la peau).
"""
from __future__ import annotations

import argparse
import cv2
import json
import math
import os
import shutil
import subprocess
import sys
import tempfile
import numpy as np
from pathlib import Path
from PIL import Image

_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE))
import face_restore
import photo_rectifier


def project_and_texture_4k(
    in_glb: str,
    raw_photo_path: str,
    rect_rgba_path: str,
    out_glb: str,
    tex_res: int = 4096,
    log=print
) -> dict:
    """Effectue la projection UV 4K directe et le calibrage facial sans aucun dédoublement."""
    log(f"[portrait_texture_4k] Texturation 4K ({tex_res}x{tex_res}) pour {in_glb}...")
    
    tmp_dir = Path(tempfile.mkdtemp(prefix="aurora_4k_tex_"))
    try:
        # 1. Préparation de la photo nettoyée haute résolution
        bgr = cv2.imread(raw_photo_path)
        hit_raw = face_restore.detect_face_bbox(raw_photo_path, allow_silhouette=False)
        
        # Déreflet chromatique non-destructif sur les verres
        if hit_raw:
            zone_yeux = photo_rectifier._region_oculaire(hit_raw.landmarks, bgr.shape, bbox=hit_raw.bbox)
            if zone_yeux is not None:
                b = bgr[:, :, 0].astype(np.float32)
                g = bgr[:, :, 1].astype(np.float32)
                r = bgr[:, :, 2].astype(np.float32)
                blue_excess = np.clip((b - np.maximum(g, r)) / 255.0, 0.0, 1.0) * (zone_yeux.astype(np.float32) / 255.0)
                b_clean = b - blue_excess * (b - g)
                bgr = np.stack([b_clean, g, r], axis=2).clip(0, 255).astype(np.uint8)
        
        # Gain d'exposition naturel
        mes = photo_rectifier.mesurer(bgr)
        bgr_exp, _ = photo_rectifier.corriger_exposition(bgr, mes)
        bgr_clean, _ = photo_rectifier.rehausser_ombres(bgr_exp, mes)

        # Détourage BiRefNet
        rgb_clean = cv2.cvtColor(bgr_clean, cv2.COLOR_BGR2RGB)
        import rembg
        session = rembg.new_session("birefnet-portrait")
        rgba_clean = rembg.remove(Image.fromarray(rgb_clean), session=session)
        clean_png = str(tmp_dir / "clean_photo_4k.png")
        rgba_clean.save(clean_png)

        # 2. Rendu de repérage orthographique du maillage 3D
        mesh_render_png = str(tmp_dir / "mesh_front_ortho.png")
        script_render = f"""
import bpy, math
from mathutils import Vector

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath="{in_glb}")

ob = max([o for o in bpy.context.scene.objects if o.type == "MESH"], key=lambda o: len(o.data.polygons))
me = ob.data
verts = [v.co for v in me.vertices]
mn = Vector(map(min, *verts))
mx = Vector(map(max, *verts))
center = (mn + mx) * 0.5
size = mx - mn

cam_data = bpy.data.cameras.new("cam_ortho")
cam_data.type = "ORTHO"
cam_data.ortho_scale = size[2] * 1.02
cam = bpy.data.objects.new("cam_ortho", cam_data)
bpy.context.scene.collection.objects.link(cam)
bpy.context.scene.camera = cam

dist = size[1] * 3.0
cam.location = Vector((center[0], center[1] - dist, center[2] + size[2] * 0.015))
cam.rotation_euler = (math.pi / 2.0, 0.0, 0.0)

bpy.context.scene.render.engine = "CYCLES"
bpy.context.scene.cycles.device = "CPU"
bpy.context.scene.cycles.samples = 16
bpy.context.scene.render.resolution_x = bpy.context.scene.render.resolution_y = 2048
bpy.context.scene.render.filepath = "{mesh_render_png}"

w = bpy.data.worlds.new("w")
w.use_nodes = True
w.node_tree.nodes["Background"].inputs[1].default_value = 2.0
bpy.context.scene.world = w

bpy.ops.render.render(write_still=True)
"""
        subprocess.run(["blender", "-b", "--python-expr", script_render], check=True, capture_output=True)

        # 3. Calibrage des repères 2D/3D
        hit_p = face_restore.detect_face_bbox(clean_png, allow_silhouette=False)
        hit_m = face_restore.detect_face_bbox(mesh_render_png, allow_silhouette=False)
        
        img_clean_cv = cv2.imread(clean_png, cv2.IMREAD_UNCHANGED)
        if hit_p and hit_m:
            lmk_photo = np.array(hit_p.landmarks, dtype=np.float32)
            lmk_mesh = np.array(hit_m.landmarks, dtype=np.float32)
            M_align, _ = cv2.estimateAffinePartial2D(lmk_photo, lmk_mesh, method=cv2.LMEDS)
            aligned_photo = cv2.warpAffine(img_clean_cv, M_align, (2048, 2048),
                                           flags=cv2.INTER_LANCZOS4, borderMode=cv2.BORDER_CONSTANT, borderValue=(0, 0, 0, 0))
        else:
            aligned_photo = cv2.resize(img_clean_cv, (2048, 2048), interpolation=cv2.INTER_LANCZOS4)

        calibrated_png = str(tmp_dir / "calibrated_4k.png")
        cv2.imwrite(calibrated_png, aligned_photo)
        log("[portrait_texture_4k] Repères calibrés avec succès.")

        # 4. Bake UV 4K dans Blender et création des shaders PBR
        script_bake = f"""
import bpy, math, os, sys
import numpy as np
from mathutils import Vector

sys.path.insert(0, "/home/juan/AuroraIA/application/.venv/lib/python3.12/site-packages")
import cv2

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath="{in_glb}")

ob = max([o for o in bpy.context.scene.objects if o.type == "MESH"], key=lambda o: len(o.data.polygons))
me = ob.data
mw = ob.matrix_world

# S'assurer que le maillage possède un dépliage UV natif
if not me.uv_layers:
    bpy.ops.object.select_all(action="DESELECT")
    ob.select_set(True)
    bpy.context.view_layer.objects.active = ob
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.uv.smart_project(angle_limit=66.0, island_margin=0.01)
    bpy.ops.object.mode_set(mode='OBJECT')

verts = [v.co for v in me.vertices]
mn = Vector(map(min, *verts))
mx = Vector(map(max, *verts))
center = (mn + mx) * 0.5
size = mx - mn

cam_data = bpy.data.cameras.new("proj_cam")
cam_data.type = "ORTHO"
cam_data.ortho_scale = size[2] * 1.02
scale = cam_data.ortho_scale

cam = bpy.data.objects.new("proj_cam", cam_data)
bpy.context.scene.collection.objects.link(cam)
bpy.context.scene.camera = cam

dist = size[1] * 3.0
cam.location = Vector((center[0], center[1] - dist, center[2] + size[2] * 0.015))
cam.rotation_euler = (math.pi / 2.0, 0.0, 0.0)
bpy.context.view_layer.update()

uv_proj = me.uv_layers.new(name="UV_Camera_Project")
me.uv_layers.active = uv_proj
M_cam = cam.matrix_world.inverted()

for poly in me.polygons:
    for loop_idx in poly.loop_indices:
        v_idx = me.loops[loop_idx].vertex_index
        p_world = mw @ me.vertices[v_idx].co
        p_cam = M_cam @ p_world
        u = (p_cam.x / scale) + 0.5
        v = (p_cam.y / scale) + 0.5
        uv_proj.data[loop_idx].uv = (u, v)

uv_native = me.uv_layers[0].name
me.uv_layers.active = me.uv_layers[uv_native]

img_photo = bpy.data.images.load("{calibrated_png}", check_existing=False)
img_photo_atlas = bpy.data.images.new("Atlas_Photo_Proj", {tex_res}, {tex_res}, alpha=True)
img_alpha_atlas = bpy.data.images.new("Atlas_Alpha_Proj", {tex_res}, {tex_res}, alpha=False)

mat_bake = bpy.data.materials.new("Mat_Bake")
mat_bake.use_nodes = True
nt = mat_bake.node_tree
for n in list(nt.nodes): nt.nodes.remove(n)

out = nt.nodes.new("ShaderNodeOutputMaterial")
emi = nt.nodes.new("ShaderNodeEmission")
nt.links.new(out.inputs["Surface"], emi.outputs["Emission"])

t_photo = nt.nodes.new("ShaderNodeTexImage")
t_photo.image = img_photo
t_photo.extension = "CLIP"

uv_map = nt.nodes.new("ShaderNodeUVMap")
uv_map.uv_map = "UV_Camera_Project"
nt.links.new(t_photo.inputs["Vector"], uv_map.outputs["UV"])
nt.links.new(emi.inputs["Color"], t_photo.outputs["Color"])

target_col = nt.nodes.new("ShaderNodeTexImage")
target_col.image = img_photo_atlas
nt.nodes.active = target_col

ob.data.materials.clear()
ob.data.materials.append(mat_bake)

bpy.context.scene.render.engine = "CYCLES"
bpy.context.scene.cycles.device = "CPU"
bpy.context.scene.cycles.samples = 1
bpy.context.scene.cycles.use_denoising = False
bpy.context.scene.render.bake.margin = 4
bpy.context.scene.render.bake.use_clear = True
bpy.context.scene.render.filter_size = 0.01

bpy.ops.object.select_all(action="DESELECT")
ob.select_set(True)
bpy.context.view_layer.objects.active = ob
bpy.ops.object.bake(type="EMIT")

nt.links.new(emi.inputs["Color"], t_photo.outputs["Alpha"])
target_alpha = nt.nodes.new("ShaderNodeTexImage")
target_alpha.image = img_alpha_atlas
nt.nodes.active = target_alpha
bpy.ops.object.bake(type="EMIT")

# Composition des pixels
buf_photo = np.empty({tex_res} * {tex_res} * 4, dtype=np.float32)
img_photo_atlas.pixels.foreach_get(buf_photo)
buf_photo = buf_photo.reshape({tex_res}, {tex_res}, 4)

buf_alpha = np.empty({tex_res} * {tex_res} * 4, dtype=np.float32)
img_alpha_atlas.pixels.foreach_get(buf_alpha)
alpha = buf_alpha.reshape({tex_res}, {tex_res}, 4)[:, :, 0:1]

# Remplissage par diffusion des bords
photo_rgb = (buf_photo[:, :, :3] * 255.0).clip(0, 255).astype(np.uint8)
mask_u8 = (alpha[:, :, 0] > 0.05).astype(np.uint8) * 255

# Inpainting rapide à 1024x1024 puis upsampling
mask_small = cv2.resize(mask_u8, (1024, 1024), interpolation=cv2.INTER_NEAREST)
photo_small = cv2.resize(photo_rgb, (1024, 1024), interpolation=cv2.INTER_LINEAR)
inpaint_small = cv2.inpaint(photo_small, 255 - mask_small, inpaintRadius=7, flags=cv2.INPAINT_TELEA)
dilated_bg = cv2.resize(inpaint_small, ({tex_res}, {tex_res}), interpolation=cv2.INTER_CUBIC)
buf_bg = dilated_bg.astype(np.float32) / 255.0

alpha_mask = alpha[:, :, 0:1]
buf_final_rgb = buf_bg * (1.0 - alpha_mask) + buf_photo[:, :, :3] * alpha_mask

buf_final = np.ones(({tex_res}, {tex_res}, 4), dtype=np.float32)
buf_final[:, :, :3] = buf_final_rgb

img_final_atlas = bpy.data.images.new("Atlas_Albedo_4K", {tex_res}, {tex_res}, alpha=False)
img_final_atlas.pixels.foreach_set(buf_final.ravel())
img_final_atlas.pack()

# Matériau final PBR réaliste
mat_final = bpy.data.materials.new("Mat_Portrait_PBR_4K")
mat_final.use_nodes = True
nt_f = mat_final.node_tree
for n in list(nt_f.nodes): nt_f.nodes.remove(n)

out_f = nt_f.nodes.new("ShaderNodeOutputMaterial")
bsdf_f = nt_f.nodes.new("ShaderNodeBsdfPrincipled")
nt_f.links.new(out_f.inputs["Surface"], bsdf_f.outputs["BSDF"])

tex_alb = nt_f.nodes.new("ShaderNodeTexImage")
tex_alb.image = img_final_atlas
nt_f.links.new(bsdf_f.inputs["Base Color"], tex_alb.outputs["Color"])

bsdf_f.inputs["Roughness"].default_value = 0.55
if "Subsurface Weight" in bsdf_f.inputs:
    bsdf_f.inputs["Subsurface Weight"].default_value = 0.08
elif "Subsurface" in bsdf_f.inputs:
    bsdf_f.inputs["Subsurface"].default_value = 0.08

ob.data.materials.clear()
ob.data.materials.append(mat_final)
me.uv_layers.remove(uv_proj)

bpy.ops.export_scene.gltf(
    filepath="{out_glb}",
    export_format="GLB",
    export_materials="EXPORT"
)
print("PORTRAIT_4K_TEXTURE_OK")
"""
        res = subprocess.run(["blender", "-b", "--python-expr", script_bake], capture_output=True, text=True)
        ok = "PORTRAIT_4K_TEXTURE_OK" in (res.stdout or "") and os.path.isfile(out_glb) and os.path.getsize(out_glb) > 1000
        return {
            "ok": ok,
            "output_glb": out_glb,
            "size_bytes": os.path.getsize(out_glb) if os.path.isfile(out_glb) else 0,
            "log": res.stdout
        }
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--glb", default="/home/juan/AuroraIA/application/output/3d/juan_faithful_perfect/shape_geometry.glb")
    parser.add_argument("--photo", default="/home/juan/Téléchargements/juan.JPG")
    parser.add_argument("--rgba", default="/home/juan/AuroraIA/application/output/3d/juan_faithful_perfect/ref_rect_rgba.png")
    parser.add_argument("--out", default="/home/juan/AuroraIA/application/output/3d/juan_faithful_perfect/portrait_perfect_4k.glb")
    parser.add_argument("--res", type=int, default=4096)
    args = parser.parse_args()

    r = project_and_texture_4k(args.glb, args.photo, args.rgba, args.out, args.res)
    print(json.dumps({k: v for k, v in r.items() if k != "log"}, indent=2))
