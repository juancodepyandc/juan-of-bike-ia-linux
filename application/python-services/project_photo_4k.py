#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""project_photo_4k.py — Projection UV 4K ultra-nette directe depuis la photo d'origine.

Bake chaque pixel réel de la photo (2.4K/4K) directement sur l'atlas UV du modèle 3D :
  - Yeux, pupilles, cils et paupières 100% nets sans aucun flou.
  - Monture des lunettes aux arêtes tranchantes.
  - Boucles de cheveux et mèches ultra-définies.
  - Moustache, barbe naissante, pores et imperfections préservés pixel par pixel.
  - Motifs du t-shirt et col nets en haute résolution.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import subprocess
import sys
import tempfile
from pathlib import Path

_HERE = Path(__file__).resolve().parent

_BPY_SCRIPT = r'''
import bpy
import bmesh
import json
import math
import os
import sys
import numpy as np
from mathutils import Vector, Matrix
from mathutils.bvhtree import BVHTree

argv = sys.argv[sys.argv.index("--") + 1:]
IN_GLB, PHOTO_PATH, OUT_GLB = argv[0], argv[1], argv[2]
TEX_RES = int(argv[3]) if len(argv) > 3 else 4096

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=IN_GLB)

meshes = [o for o in bpy.context.scene.objects if o.type == "MESH"]
if not meshes:
    print("PROJ_FAIL aucun mesh")
    sys.exit(1)

ob = max(meshes, key=lambda o: len(o.data.polygons))
me = ob.data
mw = ob.matrix_world

# 1. Calcul de la boîte englobante et cadrage de la tête
verts = np.empty(len(me.vertices) * 3, dtype=np.float32)
me.vertices.foreach_get("co", verts)
verts = verts.reshape(-1, 3)
mw_np = np.array(mw.to_4x4())
vw = verts @ mw_np[:3, :3].T + mw_np[:3, 3]

mn = vw.min(axis=0)
mx = vw.max(axis=0)
center = (mn + mx) * 0.5
size = mx - mn

# Repérer la face avant (azimut 270 dans la convention Hunyuan, regardant selon -X)
# En coordonnées monde Blender, la face avant pointe vers -X
# On place la caméra face au sujet
cam_data = bpy.data.cameras.new("proj_cam")
cam_data.type = "ORTHO"
# L'échelle ortho encadre exactement la tête et le buste
cam_data.ortho_scale = max(size[1], size[2]) * 1.05
cam = bpy.data.objects.new("proj_cam", cam_data)
bpy.context.scene.collection.objects.link(cam)
bpy.context.scene.camera = cam

# Positionnement caméra face à la tête : regard vers +X (azimut 270)
dist = size[0] * 3.0
cam.location = Vector((center[0] - dist, center[1], center[2] + size[2] * 0.02))
cam.rotation_euler = (math.pi / 2.0, 0.0, -math.pi / 2.0)

bpy.context.view_layer.update()

# 2. Création de la couche UV de projection caméra
uv_proj = me.uv_layers.new(name="UV_Camera_Project")
me.uv_layers.active = uv_proj

# Projection des sommets dans le plan caméra
M_cam = cam.matrix_world.inverted()
scale = cam_data.ortho_scale

# Calcul des coordonnées UV caméra pour chaque coin de polygone (loop)
for poly in me.polygons:
    for loop_idx in poly.loop_indices:
        v_idx = me.loops[loop_idx].vertex_index
        p_world = mw @ me.vertices[v_idx].co
        p_cam = M_cam @ p_world
        # Coordonnées caméra [-scale/2, scale/2] -> UV [0, 1]
        u = (p_cam.x / scale) + 0.5
        v = (p_cam.y / scale) + 0.5
        uv_proj.data[loop_idx].uv = (u, v)

# Rétablir la couche UV d'origine active pour le bake
uv_native = me.uv_layers[0].name
me.uv_layers.active = me.uv_layers[uv_native]

# 3. Chargement de la photo 4K et création de l'image atlas 4K
img_photo = bpy.data.images.load(PHOTO_PATH, check_existing=False)
img_photo.colorspace_settings.name = "sRGB"

img_atlas_4k = bpy.data.images.new("Atlas_Albedo_4K", TEX_RES, TEX_RES, alpha=False)

# Création du matériau de bake
mat_bake = bpy.data.materials.new("Mat_Bake_4K")
mat_bake.use_nodes = True
nt = mat_bake.node_tree
for n in list(nt.nodes):
    nt.nodes.remove(n)

node_out = nt.nodes.new("ShaderNodeOutputMaterial")
node_emi = nt.nodes.new("ShaderNodeEmission")
nt.links.new(node_out.inputs["Surface"], node_emi.outputs["Emission"])

# Texture photo projetée via UV_Camera_Project
node_tex = nt.nodes.new("ShaderNodeTexImage")
node_tex.image = img_photo
node_tex.extension = "CLIP"

node_uv = nt.nodes.new("ShaderNodeUVMap")
node_uv.uv_map = "UV_Camera_Project"
nt.links.new(node_tex.inputs["Vector"], node_uv.outputs["UV"])
nt.links.new(node_emi.inputs["Color"], node_tex.outputs["Color"])

# Cible du bake dans l'atlas 4K
node_target = nt.nodes.new("ShaderNodeTexImage")
node_target.image = img_atlas_4k
nt.nodes.active = node_target

ob.data.materials.clear()
ob.data.materials.append(mat_bake)

# 4. Exécution du Bake Cycles
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

print(f"BAKE_START 4K ({TEX_RES}x{TEX_RES})...")
bpy.ops.object.bake(type="EMIT")
print("BAKE_DONE")

# 5. Création du matériau PBR final haute définition
mat_final = bpy.data.materials.new("Mat_Portrait_PBR_4K")
mat_final.use_nodes = True
nt_f = mat_final.node_tree
for n in list(nt_f.nodes):
    nt_f.nodes.remove(n)

out_f = nt_f.nodes.new("ShaderNodeOutputMaterial")
bsdf_f = nt_f.nodes.new("ShaderNodeBsdfPrincipled")
nt_f.links.new(out_f.inputs["Surface"], bsdf_f.outputs["BSDF"])

tex_albedo = nt_f.nodes.new("ShaderNodeTexImage")
tex_albedo.image = img_atlas_4k
nt_f.links.new(bsdf_f.inputs["Base Color"], tex_albedo.outputs["Color"])

bsdf_f.inputs["Roughness"].default_value = 0.55
if "Subsurface Weight" in bsdf_f.inputs:
    bsdf_f.inputs["Subsurface Weight"].default_value = 0.10
elif "Subsurface" in bsdf_f.inputs:
    bsdf_f.inputs["Subsurface"].default_value = 0.10

ob.data.materials.clear()
ob.data.materials.append(mat_final)

# Nettoyer la couche UV temporaire de projection pour un export GLB propre
me.uv_layers.remove(uv_proj)

bpy.ops.export_scene.gltf(
    filepath=OUT_GLB,
    export_format="GLB",
    export_materials="EXPORT",
    export_apply=True
)
print("PROJECT_4K_OK")
'''


def run_project_4k(in_glb: str, photo_path: str, out_glb: str, res: int = 4096) -> dict:
    with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False) as f:
        f.write(_BPY_SCRIPT)
        script_path = f.name
    try:
        cmd = ["blender", "-b", "--factory-startup", "-noaudio", "-P", script_path, "--",
               in_glb, photo_path, out_glb, str(res)]
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
        log = (r.stdout or "") + (r.stderr or "")
        ok = "PROJECT_4K_OK" in log and os.path.isfile(out_glb) and os.path.getsize(out_glb) > 1000
        # NE FILTRER LE JOURNAL QUE QUAND TOUT VA BIEN. Le filtre ne gardait que
        # les lignes BAKE_/PROJECT_, si bien qu'un echec ressemblait a un succes:
        # "BAKE_DONE" s'affichait, aucun fichier n'existait, et la vraie cause
        # (un nom de noeud invalide sous Blender 5) etait jetee avec le reste.
        journal = [line for line in log.splitlines()
                   if "BAKE_" in line or "PROJECT_" in line]
        if not ok:
            journal = log.splitlines()[-40:]
        return {
            "ok": ok,
            "output": out_glb,
            "size_bytes": os.path.getsize(out_glb) if os.path.isfile(out_glb) else 0,
            "log": journal,
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
    parser.add_argument("--out", default="/home/juan/AuroraIA/application/output/3d/juan_faithful_perfect/portrait_sharp_4k.glb")
    parser.add_argument("--res", type=int, default=4096)
    args = parser.parse_args()

    res = run_project_4k(args.glb, args.photo, args.out, args.res)
    print(json.dumps(res, ensure_ascii=False, indent=2))
