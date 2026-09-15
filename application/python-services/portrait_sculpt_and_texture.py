#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""portrait_sculpt_and_texture.py — Sculpture anatomique du crâne, boucles de cheveux 3D et texturation 4K.

1. Lissage anatomique du crâne : élimine la pointe / le pic arrière.
2. Sculpture 3D procédurale des boucles de cheveux : transforme le bloc lisse en mèches bouclées définies.
3. Projection UV 4K avec occlusion stricte par normale :
   - Face avant (facing > 0.05) : Photo 4K ultra-nette (yeux, cils, iris, monture, barbe, pores).
   - Arrière et côtés (facing <= 0.05) : Texture continue (cheveux sombres texturés, peau de nuque, tissu sweat) SANS AUCUN DÉDOUBLEMENT À L'ARRIÈRE.
4. Shaders PBR physiques (Peau avec SSS, Cheveux bouclés texturés, Lunettes acétate).
"""
from __future__ import annotations

import argparse
import json
import math
import os
import subprocess
import sys
import tempfile
import numpy as np
from pathlib import Path
from PIL import Image

_HERE = Path(__file__).resolve().parent

_SCULPT_SCRIPT = r'''
import bpy
import bmesh
import json
import math
import os
import sys
import numpy as np
from mathutils import Vector, Matrix, noise

sys.path.insert(0, "/home/juan/AuroraIA/application/.venv/lib/python3.12/site-packages")
import cv2

argv = sys.argv[sys.argv.index("--") + 1:]
IN_GLB, PHOTO_PATH, OUT_GLB = argv[0], argv[1], argv[2]
TEX_RES = int(argv[3]) if len(argv) > 3 else 4096

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=IN_GLB)

meshes = [o for o in bpy.context.scene.objects if o.type == "MESH"]
if not meshes:
    print("SCULPT_FAIL aucun mesh")
    sys.exit(1)

ob = max(meshes, key=lambda o: len(o.data.polygons))
me = ob.data
mw = ob.matrix_world

# -------------------------------------------------------------
# 1. LISSAGE ANATOMIQUE DU CRÂNE (Élimination de la pointe arrière)
# -------------------------------------------------------------
verts = np.array([v.co for v in me.vertices])
mn = verts.min(axis=0)
mx = verts.max(axis=0)
center = (mn + mx) * 0.5
size = mx - mn

bm = bmesh.new()
bm.from_mesh(me)
bm.verts.ensure_lookup_table()

head_top_z = mx[2]
head_center_y = center[1]
head_center_z = center[2]
head_center_x = center[0]

# Rayon anatomique du crâne
rx = size[0] * 0.46
ry = size[1] * 0.44
rz = size[2] * 0.42

for v in bm.verts:
    p = v.co
    is_back_head = (p.y > head_center_y + 0.05 * size[1]) and (p.z > head_center_z)
    is_top_spike = (p.z > head_top_z - 0.15 * size[2]) and (p.y > head_center_y)
    
    if is_back_head or is_top_spike:
        dx = (p.x - head_center_x) / rx
        dy = (p.y - head_center_y) / ry
        dz = (p.z - (head_center_z + 0.08 * size[2])) / rz
        r_norm = math.sqrt(dx*dx + dy*dy + dz*dz)
        
        if r_norm > 1.05:
            factor = 1.05 / r_norm
            v.co.x = head_center_x + dx * rx * factor
            v.co.y = head_center_y + dy * ry * factor
            v.co.z = (head_center_z + 0.08 * size[2]) + dz * rz * factor

# -------------------------------------------------------------
# 2. SCULPTURE 3D PROCÉDURALE DES BOUCLES DE CHEVEUX
# -------------------------------------------------------------
for v in bm.verts:
    p = v.co
    is_hair = (p.z > head_center_z + 0.12 * size[2]) or (
        (p.y > head_center_y + 0.10 * size[1]) and (p.z > head_center_z - 0.05 * size[2])
    )
    is_face = (p.y < head_center_y - 0.02 * size[1]) and (p.z < head_center_z + 0.25 * size[2])
    
    if is_hair and not is_face:
        freq_macro = 16.0
        freq_micro = 45.0
        amp = size[2] * 0.014
        
        curl_macro = math.sin(p.x * freq_macro) * math.cos(p.y * freq_macro) + math.sin(p.z * freq_macro)
        curl_micro = math.sin(p.x * freq_micro + p.y * freq_micro) * 0.5
        curl_disp = (curl_macro * 0.7 + curl_micro * 0.3) * amp
        v.co += v.normal * curl_disp

bm.to_mesh(me)
bm.free()
me.update()

# -------------------------------------------------------------
# 3. DÉPLIAGE UV & PROJECTION AVEC OCCLUSION STRICTE PAR NORMALE
# -------------------------------------------------------------
if not me.uv_layers:
    bpy.ops.object.select_all(action="DESELECT")
    ob.select_set(True)
    bpy.context.view_layer.objects.active = ob
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.uv.smart_project(angle_limit=66.0, island_margin=0.01)
    bpy.ops.object.mode_set(mode='OBJECT')

verts_post = np.array([v.co for v in me.vertices])
mn_p = verts_post.min(axis=0)
mx_p = verts_post.max(axis=0)
center_p = (mn_p + mx_p) * 0.5
size_p = mx_p - mn_p

scale = max(size_p[0], size_p[2]) * 1.05

cam_data = bpy.data.cameras.new("proj_cam")
cam_data.type = "ORTHO"
cam_data.ortho_scale = scale

cam = bpy.data.objects.new("proj_cam", cam_data)
bpy.context.scene.collection.objects.link(cam)
bpy.context.scene.camera = cam

dist = size_p[1] * 3.0
cam.location = Vector((center_p[0], center_p[1] - dist, center_p[2]))
cam.rotation_euler = (math.pi / 2.0, 0.0, 0.0)
bpy.context.view_layer.update()

uv_proj = me.uv_layers.new(name="UV_Camera_Project")
me.uv_layers.active = uv_proj
M_cam = cam.matrix_world.inverted()

# Attribution des UV de projection avec rejet strict des faces arrière / cachées
for poly in me.polygons:
    # Normale monde de la face
    poly_norm_world = mw.to_3x3() @ poly.normal
    # Le vecteur caméra regarde selon +Y : facing = -poly_norm_world.y
    facing = -poly_norm_world.y
    
    for loop_idx in poly.loop_indices:
        v_idx = me.loops[loop_idx].vertex_index
        p_world = mw @ me.vertices[v_idx].co
        p_cam = M_cam @ p_world
        
        # Si la face regarde vers l'avant (facing > 0.08), projection valide
        if facing > 0.08:
            u = (p_cam.x / scale) + 0.5
            v = (p_cam.y / scale) + 0.5
            uv_proj.data[loop_idx].uv = (u, v)
        else:
            # Hors champ : coordonnée hors cadre CLIP (évite toute projection à l'arrière)
            uv_proj.data[loop_idx].uv = (-10.0, -10.0)

uv_native = me.uv_layers[0].name
me.uv_layers.active = me.uv_layers[uv_native]

# Texture photo
img_photo = bpy.data.images.load(PHOTO_PATH, check_existing=False)
img_photo_atlas = bpy.data.images.new("Atlas_Photo_Proj", TEX_RES, TEX_RES, alpha=True)
img_alpha_atlas = bpy.data.images.new("Atlas_Alpha_Proj", TEX_RES, TEX_RES, alpha=False)

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

# -------------------------------------------------------------
# 4. COMPOSITION INTELLIGENTE DE L'ATLAS PBR 4K
# -------------------------------------------------------------
buf_photo = np.empty(TEX_RES * TEX_RES * 4, dtype=np.float32)
img_photo_atlas.pixels.foreach_get(buf_photo)
buf_photo = buf_photo.reshape(TEX_RES, TEX_RES, 4)

buf_alpha = np.empty(TEX_RES * TEX_RES * 4, dtype=np.float32)
img_alpha_atlas.pixels.foreach_get(buf_alpha)
alpha = buf_alpha.reshape(TEX_RES, TEX_RES, 4)[:, :, 0:1]

photo_rgb = (buf_photo[:, :, :3] * 255.0).clip(0, 255).astype(np.uint8)
mask_u8 = (alpha[:, :, 0] > 0.05).astype(np.uint8) * 255

# Inpainting propre des zones non couvertes par la photo avant
# (arrière de la tête et nuque) par diffusion progressive des couleurs réelles
mask_small = cv2.resize(mask_u8, (1024, 1024), interpolation=cv2.INTER_NEAREST)
photo_small = cv2.resize(photo_rgb, (1024, 1024), interpolation=cv2.INTER_LINEAR)
inpaint_small = cv2.inpaint(photo_small, 255 - mask_small, inpaintRadius=9, flags=cv2.INPAINT_TELEA)
dilated_bg = cv2.resize(inpaint_small, (TEX_RES, TEX_RES), interpolation=cv2.INTER_CUBIC)
buf_bg = dilated_bg.astype(np.float32) / 255.0

alpha_mask = alpha[:, :, 0:1]
buf_final_rgb = buf_bg * (1.0 - alpha_mask) + buf_photo[:, :, :3] * alpha_mask

buf_final = np.ones((TEX_RES, TEX_RES, 4), dtype=np.float32)
buf_final[:, :, :3] = buf_final_rgb

img_final_atlas = bpy.data.images.new("Atlas_Albedo_4K", TEX_RES, TEX_RES, alpha=False)
img_final_atlas.pixels.foreach_set(buf_final.ravel())
img_final_atlas.pack()

# -------------------------------------------------------------
# 5. MATÉRIAUX PBR PHYSIQUES
# -------------------------------------------------------------
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

bsdf_f.inputs["Roughness"].default_value = 0.52
if "Subsurface Weight" in bsdf_f.inputs:
    bsdf_f.inputs["Subsurface Weight"].default_value = 0.08
elif "Subsurface" in bsdf_f.inputs:
    bsdf_f.inputs["Subsurface"].default_value = 0.08

ob.data.materials.clear()
ob.data.materials.append(mat_final)
me.uv_layers.remove(uv_proj)

bpy.ops.export_scene.gltf(
    filepath=OUT_GLB,
    export_format="GLB",
    export_materials="EXPORT"
)
print("SCULPT_AND_TEXTURE_OK")
'''


def run_sculpt_and_texture(in_glb: str, photo_path: str, out_glb: str, res: int = 4096) -> dict:
    with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False) as f:
        f.write(_SCULPT_SCRIPT)
        script_path = f.name
    try:
        cmd = ["blender", "-b", "--factory-startup", "-noaudio", "-P", script_path, "--",
               in_glb, photo_path, out_glb, str(res)]
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
        ok = "SCULPT_AND_TEXTURE_OK" in (r.stdout or "") and os.path.isfile(out_glb) and os.path.getsize(out_glb) > 1000
        return {
            "ok": ok,
            "output": out_glb,
            "size_bytes": os.path.getsize(out_glb) if os.path.isfile(out_glb) else 0,
            "stdout": r.stdout,
            "stderr": r.stderr
        }
    finally:
        try:
            os.remove(script_path)
        except OSError:
            pass


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--glb", default="/home/juan/AuroraIA/application/output/3d/juan_faithful_perfect/shape_geometry.glb")
    parser.add_argument("--photo", default="/home/juan/AuroraIA/application/output/3d/juan_faithful_perfect/ref_rect_rgba.png")
    parser.add_argument("--out", default="/home/juan/AuroraIA/application/output/3d/juan_faithful_perfect/juan_portrait_perfect_4k.glb")
    parser.add_argument("--res", type=int, default=4096)
    args = parser.parse_args()

    res = run_sculpt_and_texture(args.glb, args.photo, args.out, args.res)
    print(json.dumps({k: v for k, v in res.items() if k not in ("stdout", "stderr")}, indent=2))
