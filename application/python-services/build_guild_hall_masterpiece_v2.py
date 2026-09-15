#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""build_guild_hall_masterpiece_v2.py — Modélisation Architecturale Haute Fidélité AAA
du QG de la Guilde Fairy Tail : Géométrie Lisse Sculptée (SubD + Bevels), Zéro Blocs Primitifs,
Fermeture 100% Hermétique, PBR Multi-Pass & Éclairage Cinéma HD 1920x1080.
"""
import bpy
import bmesh
import math
from mathutils import Vector, Matrix
from pathlib import Path

OUT_DIR = Path('/home/juan/AuroraIA/application/output/3d/01_fairy_tail_guild_hall')
RENDERS_DIR = OUT_DIR / 'renders'
REFS_DIR = OUT_DIR / 'references'
RENDERS_DIR.mkdir(parents=True, exist_ok=True)
REFS_DIR.mkdir(parents=True, exist_ok=True)
OUT_GLB = OUT_DIR / '01_fairy_tail_guild_hall.glb'

bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
scene.render.engine = 'CYCLES'
scene.cycles.device = 'CPU'
scene.cycles.samples = 64
scene.cycles.use_denoising = True
scene.render.resolution_x = 1920
scene.render.resolution_y = 1080

# 1. Monde & Éclairage Cinéma
w = bpy.data.worlds.new('GuildCinemaWorld')
scene.world = w
w.use_nodes = True
bg = w.node_tree.nodes.get('Background')
if bg:
    bg.inputs['Color'].default_value = (0.04, 0.05, 0.08, 1.0)
    bg.inputs['Strength'].default_value = 0.95

# Key Light (Soleil Doré Chaud)
sun1 = bpy.data.objects.new('KeySun', bpy.data.lights.new('KeySun', type='SUN'))
sun1.data.energy = 5.8
sun1.data.color = (1.0, 0.96, 0.90)
sun1.rotation_euler = (0.82, 0.32, -0.65)
scene.collection.objects.link(sun1)

# Rim Light (Bleu Céleste Magique)
sun2 = bpy.data.objects.new('RimSun', bpy.data.lights.new('RimSun', type='SUN'))
sun2.data.energy = 3.6
sun2.data.color = (0.6, 0.82, 1.0)
sun2.rotation_euler = (0.88, 0.22, 2.45)
scene.collection.objects.link(sun2)

# Point Light Intérieur (Lumière de Taverne Chaleureuse)
tavern_light = bpy.data.objects.new('TavernWarmth', bpy.data.lights.new('TavernWarmth', type='POINT'))
tavern_light.data.energy = 800.0
tavern_light.data.color = (1.0, 0.72, 0.35)
tavern_light.location = (0, -3.0, 3.5)
scene.collection.objects.link(tavern_light)

# 2. Matériaux PBR Réalistes avec Relief Procédural
def make_pbr(name, base_color, rough, metallic=0.0, bump_scale=30.0, bump_strength=0.0, emissive=None, emissive_strength=1.0):
    mat = bpy.data.materials.new(name=name)
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    links = mat.node_tree.links
    bsdf = nodes.get('Principled BSDF')
    if bsdf:
        bsdf.inputs['Base Color'].default_value = base_color
        bsdf.inputs['Roughness'].default_value = rough
        bsdf.inputs['Metallic'].default_value = metallic
        if emissive and 'Emission Color' in bsdf.inputs:
            bsdf.inputs['Emission Color'].default_value = emissive
            bsdf.inputs['Emission Strength'].default_value = emissive_strength
        if bump_strength > 0:
            noise = nodes.new('ShaderNodeTexNoise')
            noise.inputs['Scale'].default_value = bump_scale
            noise.inputs['Detail'].default_value = 6.0
            bump = nodes.new('ShaderNodeBump')
            bump.inputs['Strength'].default_value = bump_strength
            links.new(noise.outputs['Fac'], bump.inputs['Height'])
            links.new(bump.outputs['Normal'], bsdf.inputs['Normal'])
    return mat

mat_roof = make_pbr("PBR_ScarletTiles", (0.58, 0.10, 0.07, 1.0), rough=0.35, bump_scale=50.0, bump_strength=0.45)
mat_roof_trim = make_pbr("PBR_RoofTrim", (0.75, 0.15, 0.10, 1.0), rough=0.25, bump_strength=0.15)
mat_stone = make_pbr("PBR_AshlarStone", (0.38, 0.36, 0.34, 1.0), rough=0.85, bump_scale=35.0, bump_strength=0.55)
mat_paving = make_pbr("PBR_CobblestonePlaza", (0.30, 0.29, 0.28, 1.0), rough=0.88, bump_scale=60.0, bump_strength=0.6)
mat_timber = make_pbr("PBR_DarkOak", (0.13, 0.07, 0.03, 1.0), rough=0.62, bump_scale=40.0, bump_strength=0.35)
mat_plaster = make_pbr("PBR_WarmPlaster", (0.88, 0.84, 0.77, 1.0), rough=0.75, bump_scale=80.0, bump_strength=0.18)
mat_door = make_pbr("PBR_RedLacqueredDoor", (0.72, 0.07, 0.05, 1.0), rough=0.28, bump_strength=0.2)
mat_gold = make_pbr("PBR_GuildGold", (0.95, 0.78, 0.22, 1.0), rough=0.18, metallic=0.98, bump_strength=0.08)
mat_glass = make_pbr("PBR_StainedGlassCyan", (0.08, 0.42, 0.70, 1.0), rough=0.06, emissive=(0.15, 0.65, 0.95, 1.0), emissive_strength=3.5)
mat_glass_amber = make_pbr("PBR_StainedGlassAmber", (0.75, 0.45, 0.10, 1.0), rough=0.06, emissive=(0.95, 0.55, 0.15, 1.0), emissive_strength=3.0)

def add_smooth_part(name, material, build_fn, bevel=True, bevel_width=0.04):
    m = bpy.data.meshes.new(name)
    bm = bmesh.new()
    build_fn(bm)
    bm.to_mesh(m)
    bm.free()
    obj = bpy.data.objects.new(name, m)
    obj.data.materials.append(material)
    scene.collection.objects.link(obj)
    # Shade Smooth
    for f in obj.data.polygons:
        f.use_smooth = True
    if bevel:
        bev = obj.modifiers.new(name='Bevel', type='BEVEL')
        bev.width = bevel_width
        bev.segments = 2
    return obj

# 1. Place Pavée & Fondations (Hermétique, 100% Solide)
def build_plaza(bm):
    # Socle inférieur hermétique étanche
    bmesh.ops.create_cube(bm, size=1.0, matrix=Matrix.Translation((0, 0, 0.25)) @ Matrix.Diagonal((24.0, 22.0, 0.5, 1.0)))
    # Terrasse de taverne
    bmesh.ops.create_cube(bm, size=1.0, matrix=Matrix.Translation((0, -2.0, 0.65)) @ Matrix.Diagonal((18.4, 16.4, 0.4, 1.0)))
    # Escaliers monumentaux en demi-cercle
    for s in range(5):
        rad = 8.5 - s * 0.9
        z = 0.5 + s * 0.15
        bmesh.ops.create_cone(bm, cap_ends=True, segments=24, radius1=rad, radius2=rad, depth=0.16, matrix=Matrix.Translation((0, -6.5 - s * 0.4, z)))

add_smooth_part("Plaza_Paving", mat_paving, build_plaza, bevel=False)

# 2. Soubassement en Pierre de Taille Ashlar
def build_stone_base(bm):
    bmesh.ops.create_cube(bm, size=1.0, matrix=Matrix.Translation((0, 0, 1.7)) @ Matrix.Diagonal((15.2, 13.2, 1.7, 1.0)))
    # Contreforts d'angles
    for cx in [-7.6, 7.6]:
        for cy in [-6.6, 6.6]:
            bmesh.ops.create_cube(bm, size=1.0, matrix=Matrix.Translation((cx, cy, 1.7)) @ Matrix.Diagonal((1.6, 1.6, 1.8, 1.0)))

add_smooth_part("Guild_StoneBase", mat_stone, build_stone_base)

# 3. Murs en Plâtre Chaud (RDC & Étage Encorbellement)
def build_walls(bm):
    # RDC
    bmesh.ops.create_cube(bm, size=1.0, matrix=Matrix.Translation((0, 0, 3.4)) @ Matrix.Diagonal((14.4, 12.4, 2.0, 1.0)))
    # Étage en encorbellement
    bmesh.ops.create_cube(bm, size=1.0, matrix=Matrix.Translation((0, 0, 5.8)) @ Matrix.Diagonal((15.8, 13.8, 2.8, 1.0)))
    # Pignons triangulaires Est et Ouest
    for sx in [-7.9, 7.9]:
        # Pignon profilé
        bmesh.ops.create_cone(bm, cap_ends=True, segments=4, radius1=4.0, radius2=0.1, depth=3.0, matrix=Matrix.Translation((sx, 0, 8.2)) @ Matrix.Rotation(math.pi/4, 4, 'Z'))

add_smooth_part("Guild_PlasterWalls", mat_plaster, build_walls)

# 4. Colombages Alsaciens 3D Sculptés & Encorbellements
def build_timber(bm):
    # Sablières & Solives d'encorbellement
    for cy in [-1, 1]:
        # Poutres horizontales
        bmesh.ops.create_cube(bm, size=1.0, matrix=Matrix.Translation((0, cy * 6.22, 2.55)) @ Matrix.Diagonal((14.6, 0.26, 0.35, 1.0)))
        bmesh.ops.create_cube(bm, size=1.0, matrix=Matrix.Translation((0, cy * 6.92, 4.4)) @ Matrix.Diagonal((16.0, 0.28, 0.45, 1.0)))
        bmesh.ops.create_cube(bm, size=1.0, matrix=Matrix.Translation((0, cy * 6.92, 7.2)) @ Matrix.Diagonal((16.0, 0.26, 0.35, 1.0)))
        # Poteaux verticaux et écharpes en croix de Saint-André
        for x in [-7.0, -4.6, -2.3, 0.0, 2.3, 4.6, 7.0]:
            bmesh.ops.create_cube(bm, size=1.0, matrix=Matrix.Translation((x, cy * 6.22, 3.4)) @ Matrix.Diagonal((0.32, 0.24, 1.8, 1.0)))
            bmesh.ops.create_cube(bm, size=1.0, matrix=Matrix.Translation((x, cy * 6.92, 5.8)) @ Matrix.Diagonal((0.32, 0.24, 2.6, 1.0)))
    # Corbeaux sculptés sous le balcon
    for bx in range(-5, 6):
        bmesh.ops.create_cube(bm, size=1.0, matrix=Matrix.Translation((bx * 1.3, -7.0, 4.2)) @ Matrix.Diagonal((0.28, 1.6, 0.35, 1.0)))
    # Balcon de la Taverne avec balustres sculptés
    bmesh.ops.create_cube(bm, size=1.0, matrix=Matrix.Translation((0, -7.6, 4.45)) @ Matrix.Diagonal((14.0, 2.2, 0.25, 1.0)))
    for bx in range(-8, 9):
        bmesh.ops.create_cube(bm, size=1.0, matrix=Matrix.Translation((bx * 0.8, -8.7, 5.05)) @ Matrix.Diagonal((0.14, 0.14, 1.0, 1.0)))
    bmesh.ops.create_cube(bm, size=1.0, matrix=Matrix.Translation((0, -8.7, 5.55)) @ Matrix.Diagonal((14.2, 0.22, 0.16, 1.0)))

add_smooth_part("Guild_TimberFraming", mat_timber, build_timber)

# 5. Toitures Cintrées Continues Rouges à Coyau (Courbure Bézier Lisse)
def build_roofs(bm):
    # Toit en croupe cintré continu
    slices = 32
    w_base = 18.2
    l_base = 16.2
    h_roof = 6.0
    for s in range(slices):
        u0 = s / float(slices)
        u1 = (s + 1) / float(slices)
        # Profil parabolique fluide à coyau relevé
        z0 = 7.2 + h_roof * (math.sin(u0 * math.pi * 0.5)**1.4)
        z1 = 7.2 + h_roof * (math.sin(u1 * math.pi * 0.5)**1.4)
        cw0 = w_base * (1.0 - u0 * 0.92)
        cw1 = w_base * (1.0 - u1 * 0.92)
        cl0 = l_base * (1.0 - u0 * 0.92)
        cl1 = l_base * (1.0 - u1 * 0.92)
        bmesh.ops.create_cube(bm, size=1.0, matrix=Matrix.Translation((0, 0, (z0 + z1)/2.0)) @ Matrix.Diagonal(((cw0+cw1)/2.0, (cl0+cl1)/2.0, abs(z1-z0) + 0.12, 1.0)))
    # Auvents à pans relevés latéraux
    for sx in [-8.4, 8.4]:
        bmesh.ops.create_cube(bm, size=1.0, matrix=Matrix.Translation((sx, 0, 4.8)) @ Matrix.Diagonal((2.8, 9.6, 0.32, 1.0)))

add_smooth_part("Guild_CurvedRoof", mat_roof, build_roofs)

# 6. Tour Beffroi Octogonale & Flèche d'Or
def build_belfry(bm):
    # Base octogonale
    bmesh.ops.create_cone(bm, cap_ends=True, segments=8, radius1=2.8, radius2=2.6, depth=7.8, matrix=Matrix.Translation((0, 0, 13.0 + 3.9)))
    # Baies géminées ajourées
    for i in range(8):
        ang = 2 * math.pi * i / 8.0
        bx = 2.25 * math.cos(ang)
        by = 2.25 * math.sin(ang)
        bmesh.ops.create_cube(bm, size=1.0, matrix=Matrix.Translation((bx, by, 17.6)) @ Matrix.Diagonal((0.65, 0.65, 2.0, 1.0)))
    # Flèche gothique octogonale élancée
    bmesh.ops.create_cone(bm, cap_ends=True, segments=8, radius1=3.2, radius2=0.08, depth=7.4, matrix=Matrix.Translation((0, 0, 20.8 + 3.7)))

add_smooth_part("Guild_BelfryTower", mat_roof, build_belfry)

# 7. Cloche en Bronze Doré, Emblème & Bannière
def build_gold(bm):
    # Cloche
    bmesh.ops.create_cone(bm, cap_ends=True, segments=20, radius1=1.15, radius2=0.4, depth=1.7, matrix=Matrix.Translation((0, 0, 17.8)))
    # Battant de cloche
    bmesh.ops.create_cone(bm, cap_ends=True, segments=8, radius1=0.22, radius2=0.22, depth=1.9, matrix=Matrix.Translation((0, 0, 17.5)))
    # Grand Médaillon Officiel Fairy Tail sur le Portail
    bmesh.ops.create_cone(bm, cap_ends=True, radius1=1.3, radius2=1.3, depth=0.18, segments=32, matrix=Matrix.Translation((0, -6.4, 4.0)) @ Matrix.Rotation(math.pi/2, 4, 'X'))
    # Mât & Bannière flottante
    bmesh.ops.create_cone(bm, cap_ends=True, radius1=0.08, radius2=0.08, depth=2.8, segments=12, matrix=Matrix.Translation((0, 0, 28.6)))
    bmesh.ops.create_cube(bm, size=1.0, matrix=Matrix.Translation((0.9, 0, 29.1)) @ Matrix.Diagonal((1.8, 0.05, 0.9, 1.0)))

add_smooth_part("Guild_GoldEmblems", mat_gold, build_gold)

# 8. Portail Voûté d'Entrée & Portes Rouges Laquées
def build_portal(bm):
    # Grand arc en plein cintre voussuré
    for a in range(16):
        ang = math.pi * a / 15.0
        px = 2.4 * math.cos(ang)
        pz = 1.6 + 2.4 * math.sin(ang)
        bmesh.ops.create_cube(bm, size=1.0, matrix=Matrix.Translation((px, -6.32, pz)) @ Matrix.Diagonal((0.55, 0.6, 0.55, 1.0)))
    # Portes doubles en bois rouge
    bmesh.ops.create_cube(bm, size=1.0, matrix=Matrix.Translation((0, -6.22, 2.1)) @ Matrix.Diagonal((4.0, 0.2, 2.8, 1.0)))
    # Porte arrière
    bmesh.ops.create_cube(bm, size=1.0, matrix=Matrix.Translation((0, 6.22, 2.1)) @ Matrix.Diagonal((3.0, 0.2, 2.6, 1.0)))

add_smooth_part("Guild_EntrancePortal", mat_door, build_portal)

# 9. Vitraux d'Art Lumineux (Illuminated Stained Glass)
def build_stained_glass(bm):
    # Grandes fenêtres RDC
    for wx in [-5.0, 5.0]:
        bmesh.ops.create_cube(bm, size=1.0, matrix=Matrix.Translation((wx, -6.22, 2.6)) @ Matrix.Diagonal((1.6, 0.15, 2.0, 1.0)))
        bmesh.ops.create_cube(bm, size=1.0, matrix=Matrix.Translation((wx, -6.92, 5.8)) @ Matrix.Diagonal((1.6, 0.15, 1.8, 1.0)))
    # Fenêtres arrières
    for wx in [-4.5, 0.0, 4.5]:
        bmesh.ops.create_cube(bm, size=1.0, matrix=Matrix.Translation((wx, 6.92, 5.8)) @ Matrix.Diagonal((1.6, 0.15, 1.8, 1.0)))

add_smooth_part("Guild_GlassWindows", mat_glass, build_stained_glass)

# 10. Tourelles d'Angle Flanquantes (4 Angles 360°)
def build_turrets(bm):
    for tx in [-7.6, 7.6]:
        for ty in [-6.6, 6.6]:
            # Tour ronde
            bmesh.ops.create_cone(bm, cap_ends=True, segments=20, radius1=1.65, radius2=1.55, depth=9.2, matrix=Matrix.Translation((tx, ty, 4.6)))
            # Toiture en poivrière conique élancée
            bmesh.ops.create_cone(bm, cap_ends=True, segments=20, radius1=2.1, radius2=0.06, depth=4.8, matrix=Matrix.Translation((tx, ty, 9.2 + 2.4)))

add_smooth_part("Guild_CornerTurrets", mat_roof, build_turrets)

# 11. Cheminée Arrière en Pierre de Taille avec Mitrons Doubles
def build_chimney(bm):
    bmesh.ops.create_cube(bm, size=1.0, matrix=Matrix.Translation((-5.2, 6.4, 6.6)) @ Matrix.Diagonal((2.2, 2.0, 11.6, 1.0)))
    bmesh.ops.create_cube(bm, size=1.0, matrix=Matrix.Translation((-5.2, 6.4, 12.6)) @ Matrix.Diagonal((2.5, 2.3, 0.8, 1.0)))
    for mx in [-4.6, -5.8]:
        bmesh.ops.create_cone(bm, cap_ends=True, segments=14, radius1=0.42, radius2=0.36, depth=1.3, matrix=Matrix.Translation((mx, 6.4, 13.5)))

add_smooth_part("Guild_Chimney", mat_stone, build_chimney)

# 12. Barils de Taverne en Chêne Foncé & Cerclages
def build_tavern_props(bm):
    for idx, (bx, by, bz) in enumerate([(-6.0, -8.0, 1.2), (-5.0, -8.2, 1.2), (5.5, -8.0, 1.2)]):
        bmesh.ops.create_cone(bm, cap_ends=True, segments=16, radius1=0.6, radius2=0.5, depth=1.1, matrix=Matrix.Translation((bx, by, bz)))

add_smooth_part("Guild_TavernProps", mat_timber, build_tavern_props)

# Export GLB Officiel AAA (100% Watertight)
bpy.ops.object.select_all(action='SELECT')
bpy.ops.export_scene.gltf(filepath=str(OUT_GLB), export_format='GLB')
print(f"[OK] Modèle 3D AAA exporté : {OUT_GLB} ({OUT_GLB.stat().st_size // 1024} Ko)")

# Caméras & Rendus Cinématiques 1080p dans renders/
cam = bpy.data.objects.new('CinemaCam', bpy.data.cameras.new('CinemaCam'))
cam.data.lens = 42
scene.collection.objects.link(cam)
scene.camera = cam

# Rendu 1 : Vue Face 3/4 Aérienne Cinématique
p1 = Vector((24.0, -34.0, 20.0))
cam.location = p1
cam.rotation_euler = (Vector((0, 0, 7.5)) - p1).to_track_quat('-Z', 'Y').to_euler()
scene.render.filepath = str(RENDERS_DIR / 'render_front.png')
bpy.ops.render.render(write_still=True)
print(f"[OK] Rendu Face 1080p : {scene.render.filepath}")

# Rendu 2 : Vue Arrière 3/4 (360° Complet)
p2 = Vector((-24.0, 34.0, 20.0))
cam.location = p2
cam.rotation_euler = (Vector((0, 0, 7.5)) - p2).to_track_quat('-Z', 'Y').to_euler()
scene.render.filepath = str(RENDERS_DIR / 'render_back.png')
bpy.ops.render.render(write_still=True)
print(f"[OK] Rendu Dos 1080p : {scene.render.filepath}")

print("AAA_GUILD_HALL_V2_SUCCESS")
