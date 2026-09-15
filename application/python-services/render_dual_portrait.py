#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""render_dual_portrait.py — Rendus Studio HD Multi-Angles (Texturé Couleur + Clay Tout Blanc).
"""
import bpy
import math
import os
import sys
from mathutils import Vector

argv = sys.argv[sys.argv.index("--") + 1:]
COLOR_GLB, CLAY_GLB, OUT_DIR = argv[0], argv[1], argv[2]
os.makedirs(OUT_DIR, exist_ok=True)

def setup_studio_scene():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    scene.render.engine = 'CYCLES'
    scene.cycles.device = 'CPU'
    scene.cycles.samples = 24
    scene.cycles.use_denoising = True
    scene.render.resolution_x = 1200
    scene.render.resolution_y = 1200
    scene.render.film_transparent = False

    w = scene.world or bpy.data.worlds.new("World")
    scene.world = w
    w.use_nodes = True
    bg = w.node_tree.nodes.get("Background")
    if bg:
        bg.inputs["Color"].default_value = (0.04, 0.04, 0.04, 1.0)
        bg.inputs["Strength"].default_value = 0.5
    return scene

def render_mesh(glb_path, prefix):
    setup_studio_scene()
    bpy.ops.import_scene.gltf(filepath=glb_path)
    
    meshes = [o for o in bpy.context.scene.objects if o.type == 'MESH']
    if not meshes:
        return
    ob = max(meshes, key=lambda o: len(o.data.polygons))
    
    verts = [v.co for v in ob.data.vertices]
    mn = Vector(map(min, *verts))
    mx = Vector(map(max, *verts))
    center = (mn + mx) * 0.5
    size = mx - mn
    radius = max(size) * 0.5
    
    # Caméra Portrait Focale 85mm
    cam_data = bpy.data.cameras.new("Camera")
    cam_data.lens = 85
    cam_data.sensor_width = 36
    cam_data.sensor_height = 36
    cam = bpy.data.objects.new("Camera", cam_data)
    bpy.context.scene.collection.objects.link(cam)
    bpy.context.scene.camera = cam
    
    # 3-Point Lighting
    dist = radius * 3.8
    key_data = bpy.data.lights.new("KeyLight", type='AREA')
    key_data.energy = 450.0
    key_data.size = radius * 1.5
    key_data.color = (1.0, 0.98, 0.95)
    key_obj = bpy.data.objects.new("KeyLight", key_data)
    key_obj.location = Vector((center.x - radius * 1.8, center.y - dist * 0.7, center.z + radius * 1.2))
    bpy.context.scene.collection.objects.link(key_obj)

    fill_data = bpy.data.lights.new("FillLight", type='AREA')
    fill_data.energy = 180.0
    fill_data.size = radius * 2.0
    fill_data.color = (0.92, 0.95, 1.0)
    fill_obj = bpy.data.objects.new("FillLight", fill_data)
    fill_obj.location = Vector((center.x + radius * 1.8, center.y - dist * 0.7, center.z + radius * 0.6))
    bpy.context.scene.collection.objects.link(fill_obj)

    rim_data = bpy.data.lights.new("RimLight", type='AREA')
    rim_data.energy = 380.0
    rim_data.size = radius * 1.2
    rim_data.color = (1.0, 1.0, 1.0)
    rim_obj = bpy.data.objects.new("RimLight", rim_data)
    rim_obj.location = Vector((center.x, center.y + dist * 0.8, center.z + radius * 1.5))
    bpy.context.scene.collection.objects.link(rim_obj)

    angles = [
        (270, "face"),
        (315, "trois_quarts_droit"),
        (000, "profil_droit"),
        (225, "trois_quarts_gauche"),
        (180, "profil_gauche"),
        (90,  "arriere")
    ]
    
    for az_deg, label in angles:
        az_rad = math.radians(az_deg)
        cam_x = center.x + dist * math.cos(az_rad)
        cam_y = center.y + dist * math.sin(az_rad)
        cam_z = center.z + radius * 0.05
        
        cam.location = Vector((cam_x, cam_y, cam_z))
        
        # Pointer vers le centre de la tête
        direction = center - cam.location
        rot_quat = direction.to_track_quat('-Z', 'Y')
        cam.rotation_euler = rot_quat.to_euler()
        
        bpy.context.scene.render.filepath = os.path.join(OUT_DIR, f"{prefix}_{label}.png")
        bpy.ops.render.render(write_still=True)
        print(f"Rendered {bpy.context.scene.render.filepath}")

render_mesh(COLOR_GLB, "texture_4k")
render_mesh(CLAY_GLB, "clay_white")
print("DUAL_RENDER_OK")
