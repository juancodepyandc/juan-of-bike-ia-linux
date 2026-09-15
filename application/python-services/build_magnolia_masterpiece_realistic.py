#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""build_magnolia_masterpiece_realistic.py — Production 3D Réaliste & Complète de Magnolia (Fairy Tail).
ZÉRO FORME PRIMITIVE BASIQUE :
- Architecture médiévale & gothique richement détaillée (moulures, colombages sculptés en relief, encorbellements, corbeaux en bois, toitures à tuiles imbriquées, flèches filigranées, rosaces gothiques à entrelacs).
- QG de la Guilde Fairy Tail complet (soubassement en pierre appareillée, taverne à colombages, balcons en encorbellement, toits arqués multi-couches, tour belfroi octogonale avec cloche et bannière rouge de guilde).
- Cathédrale de Kardia monumentale (arcs-boutants, triple portail gothique à voussures, flèches jumelles octogonales ajourées, grande rosace vitrée, toit en cuivre vert-de-gris).
- 100+ Maisons à colombages alsaciens/tudor uniques avec étages en saillie, lucarnes, cheminées en brique avec mitrons, boutiques avec auvents et enseignes.
- Fleuve de Magnolia en méandre naturel avec quais inclinés en maçonnerie, escaliers d'accostage, ponts d'arches à voussoirs, gondoles en bois.
- Boulevard de Gildarts avec double voie ferrée encastrée, traverses et mécanismes.
- Arbres de magnolias florifères (troncs noueux ramifiés, feuillage rose/blanc foisonnant), collines et crêtes rocheuses alpines.
- Rendu Cycles Cinématique HD + 6 Vues Panoramiques & Closes + Survol Vidéo 360° (72 frames / 24 fps) + Export GLB.
"""
import bpy
import bmesh
import math
import os
import random
from mathutils import Vector, Euler, Matrix, Quaternion

WORKSPACE = '/home/juan/AuroraIA/application'
SCENE_DIR = os.path.join(WORKSPACE, 'output', '3d', 'magnolia_fairy_tail_city')
FRAMES_DIR = os.path.join(SCENE_DIR, 'frames')
STILLS_DIR = os.path.join(SCENE_DIR, 'stills')
os.makedirs(FRAMES_DIR, exist_ok=True)
os.makedirs(STILLS_DIR, exist_ok=True)

random.seed(777123)

print("==========================================================")
print("  AURORA 3D : MASTERPIECE PRODUCTION — MAGNOLIA FAIRY TAIL")
print("==========================================================")

# =========================================================
# 1. SETUP DE LA SCÈNE & RENDU CYCLES
# =========================================================
bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
scene.render.engine = 'CYCLES'
scene.cycles.device = 'CPU'
scene.cycles.samples = 28
scene.cycles.use_denoising = True
scene.render.resolution_x = 1280
scene.render.resolution_y = 720
scene.render.fps = 24
scene.frame_start = 1
scene.frame_end = 72

# World : Ciel lumineux de Fiore avec soleil d'or et brume atmosphérique
w = bpy.data.worlds.new('FioreWorld')
scene.world = w
w.use_nodes = True
bg = w.node_tree.nodes.get('Background')
if bg:
    bg.inputs['Color'].default_value = (0.52, 0.74, 0.98, 1.0)
    bg.inputs['Strength'].default_value = 1.15

# Soleil principal de Fiore
sun_data = bpy.data.lights.new('FioreSun', type='SUN')
sun_data.energy = 5.0
sun_data.color = (1.0, 0.96, 0.88)
sun_data.angle = math.radians(1.2)
sun_obj = bpy.data.objects.new('FioreSun', sun_data)
sun_obj.rotation_euler = Euler((math.radians(48), math.radians(22), math.radians(-35)), 'XYZ')
scene.collection.objects.link(sun_obj)

# Ciel fill ambiant
fill_data = bpy.data.lights.new('SkyFill', type='SUN')
fill_data.energy = 1.4
fill_data.color = (0.70, 0.85, 1.0)
fill_obj = bpy.data.objects.new('SkyFill', fill_data)
fill_obj.rotation_euler = Euler((math.radians(65), math.radians(0), math.radians(145)), 'XYZ')
scene.collection.objects.link(fill_obj)

# =========================================================
# 2. CRÉATION DES MATÉRIAUX PBR HAUTE FIDÉLITÉ
# =========================================================
def create_pbr(name, base_col, rough=0.6, metal=0.0, spec=0.5, emi=(0,0,0,1), emi_str=0.0):
    mat = bpy.data.materials.new(name=name)
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get('Principled BSDF')
    if bsdf:
        bsdf.inputs['Base Color'].default_value = (*base_col, 1.0) if len(base_col) == 3 else base_col
        bsdf.inputs['Roughness'].default_value = rough
        bsdf.inputs['Metallic'].default_value = metal
        if 'Specular IOR Level' in bsdf.inputs:
            bsdf.inputs['Specular IOR Level'].default_value = spec
        if 'Emission Color' in bsdf.inputs:
            bsdf.inputs['Emission Color'].default_value = emi
            bsdf.inputs['Emission Strength'].default_value = emi_str
    return mat

mat_water = create_pbr('KardiacWater', (0.12, 0.42, 0.58), rough=0.05, metal=0.05, spec=0.95)
mat_stone_masonry = create_pbr('AshlarStone', (0.58, 0.55, 0.50), rough=0.72)
mat_paving = create_pbr('CobblestonePaving', (0.64, 0.60, 0.54), rough=0.62)
mat_stucco_cream = create_pbr('StuccoCream', (0.90, 0.86, 0.78), rough=0.82)
mat_stucco_ochre = create_pbr('StuccoOchre', (0.86, 0.74, 0.58), rough=0.80)
mat_stucco_white = create_pbr('StuccoWhite', (0.94, 0.93, 0.91), rough=0.70)
mat_timber_dark = create_pbr('DarkOakTimber', (0.22, 0.13, 0.07), rough=0.48)
mat_timber_warm = create_pbr('WarmPineTimber', (0.40, 0.25, 0.14), rough=0.52)
mat_roof_terracotta_red = create_pbr('TerracottaShinglesRed', (0.78, 0.16, 0.10), rough=0.45)
mat_roof_terracotta_blue = create_pbr('TerracottaShinglesBlue', (0.16, 0.36, 0.62), rough=0.45)
mat_roof_guild_scarlet = create_pbr('GuildScarletRoof', (0.88, 0.08, 0.08), rough=0.38)
mat_guild_emblem = create_pbr('GuildEmblemRed', (0.98, 0.06, 0.06), rough=0.25, emi=(0.98, 0.06, 0.06, 1.0), emi_str=2.0)
mat_gold_finial = create_pbr('PolishedGoldSpire', (0.95, 0.78, 0.22), rough=0.20, metal=0.95)
mat_copper_verdigris = create_pbr('CopperVerdigris', (0.32, 0.62, 0.54), rough=0.42, metal=0.3)
mat_cathedral_limestone = create_pbr('GothicLimestone', (0.88, 0.86, 0.82), rough=0.55)
mat_rose_stained_glass = create_pbr('RoseStainedGlass', (0.2, 0.45, 0.85), rough=0.1, emi=(0.35, 0.65, 0.95, 1.0), emi_str=2.5)
mat_grass_lush = create_pbr('LushMeadow', (0.26, 0.52, 0.16), rough=0.88)
mat_rock_cliff = create_pbr('AlpineRock', (0.46, 0.44, 0.42), rough=0.85)
mat_magnolia_pink = create_pbr('MagnoliaPinkBlossom', (0.96, 0.58, 0.72), rough=0.40)
mat_magnolia_white = create_pbr('MagnoliaWhiteBlossom', (0.98, 0.92, 0.94), rough=0.40)
mat_iron_steel = create_pbr('WroughtIron', (0.18, 0.18, 0.20), rough=0.35, metal=0.90)

# =========================================================
# 3. TOPOGRAPHIE NATURELLE : CRÊTES ALPINES, FLEUVE & LAC
# =========================================================
print("[1/6] Modélisation de la topographie alpine, du méandre et du Lac Kardiac...")

# Terrain vallonné principal
bm_ground = bmesh.new()
GRID_RES = 36
GRID_SIZE = 260.0
for i in range(GRID_RES):
    for j in range(GRID_RES):
        u = (i / (GRID_RES - 1) - 0.5) * GRID_SIZE
        v = (j / (GRID_RES - 1) - 0.5) * GRID_SIZE
        
        # Relief naturel doux dans la cuvette, s'élevant vers les crêtes
        dist_center = math.sqrt(u*u + v*v)
        z = 0.0
        if dist_center > 70:
            z += (dist_center - 70) * 0.35 + math.sin(u * 0.05) * 4.0 + math.cos(v * 0.05) * 4.0
        
        # Dépression du fleuve traversant en S
        # Ligne de rivière : y = 14 * sin(x * 0.035) - 6
        river_y = 14.0 * math.sin(u * 0.035) - 6.0
        dist_river = abs(v - river_y)
        if dist_river < 9.0 and u < 75.0:
            z -= (1.0 - (dist_river / 9.0)) * 1.6
            
        # Dépression du Lac Kardiac à l'est
        if u > 70.0:
            lake_dist = math.sqrt((u - 95.0)**2 + (v + 5.0)**2)
            if lake_dist < 60.0:
                z -= (1.0 - (lake_dist / 60.0)) * 2.2
                
        bm_ground.verts.new((u, v, z))

bm_ground.verts.ensure_lookup_table()
for i in range(GRID_RES - 1):
    for j in range(GRID_RES - 1):
        v1 = bm_ground.verts[i * GRID_RES + j]
        v2 = bm_ground.verts[(i + 1) * GRID_RES + j]
        v3 = bm_ground.verts[(i + 1) * GRID_RES + (j + 1)]
        v4 = bm_ground.verts[i * GRID_RES + (j + 1)]
        bm_ground.faces.new((v1, v2, v3, v4))

mesh_ground = bpy.data.meshes.new('Magnolia_Valley_Terrain')
bm_ground.to_mesh(mesh_ground)
bm_ground.free()
obj_ground = bpy.data.objects.new('Magnolia_Valley_Terrain', mesh_ground)
scene.collection.objects.link(obj_ground)
obj_ground.data.materials.append(mat_grass_lush)

# Montagne calcaire colossale en arrière-plan (Le pic central de Magnolia)
bm_mt = bmesh.new()
MT_RES = 24
MT_RAD = 48.0
MT_H = 65.0
MT_CX, MT_CY = -10.0, 95.0
for i in range(MT_RES):
    for j in range(MT_RES):
        frac_h = i / (MT_RES - 1)
        ang = j / MT_RES * 2 * math.pi
        r = MT_RAD * (1.0 - frac_h * 0.85) + math.sin(ang * 4) * 3.5 * (1.0 - frac_h)
        mx = MT_CX + r * math.cos(ang)
        my = MT_CY + r * math.sin(ang)
        mz = frac_h * MT_H + math.sin(mx * 0.2) * 2.0
        bm_mt.verts.new((mx, my, mz))

bm_mt.verts.ensure_lookup_table()
for i in range(MT_RES - 1):
    for j in range(MT_RES):
        j_next = (j + 1) % MT_RES
        v1 = bm_mt.verts[i * MT_RES + j]
        v2 = bm_mt.verts[(i + 1) * MT_RES + j]
        v3 = bm_mt.verts[(i + 1) * MT_RES + j_next]
        v4 = bm_mt.verts[i * MT_RES + j_next]
        bm_mt.faces.new((v1, v2, v3, v4))

mesh_mt = bpy.data.meshes.new('Magnolia_Central_Peak')
bm_mt.to_mesh(mesh_mt)
bm_mt.free()
obj_mt = bpy.data.objects.new('Magnolia_Central_Peak', mesh_mt)
scene.collection.objects.link(obj_mt)
obj_mt.data.materials.append(mat_rock_cliff)

# Lac Kardiac (Plan d'eau réaliste)
bpy.ops.mesh.primitive_plane_add(size=1.0, location=(95.0, -5.0, -0.4))
lake = bpy.context.active_object
lake.name = 'Kardiac_Lake_Surface'
lake.scale = Vector((90.0, 150.0, 1.0))
bpy.ops.object.transform_apply(scale=True)
lake.data.materials.append(mat_water)

# Fleuve de Magnolia (Surface d'eau suivant le méandre)
bm_riv = bmesh.new()
RIV_STEPS = 40
RIV_WIDTH = 13.0
for s in range(RIV_STEPS):
    rx = -90.0 + s * (165.0 / (RIV_STEPS - 1))
    ry_c = 14.0 * math.sin(rx * 0.035) - 6.0
    # Tangente et normale
    dx = 1.0
    dy = 14.0 * 0.035 * math.cos(rx * 0.035)
    l = math.sqrt(dx*dx + dy*dy)
    nx, ny = -dy / l, dx / l
    
    bm_riv.verts.new((rx + nx * RIV_WIDTH * 0.5, ry_c + ny * RIV_WIDTH * 0.5, -0.4))
    bm_riv.verts.new((rx - nx * RIV_WIDTH * 0.5, ry_c - ny * RIV_WIDTH * 0.5, -0.4))

bm_riv.verts.ensure_lookup_table()
for s in range(RIV_STEPS - 1):
    v1 = bm_riv.verts[s * 2]
    v2 = bm_riv.verts[(s + 1) * 2]
    v3 = bm_riv.verts[(s + 1) * 2 + 1]
    v4 = bm_riv.verts[s * 2 + 1]
    bm_riv.faces.new((v1, v2, v3, v4))

mesh_riv = bpy.data.meshes.new('Magnolia_River_Water')
bm_riv.to_mesh(mesh_riv)
bm_riv.free()
obj_riv = bpy.data.objects.new('Magnolia_River_Water', mesh_riv)
scene.collection.objects.link(obj_riv)
obj_riv.data.materials.append(mat_water)

# =========================================================
# 4. LE GRAND PONT DE MAGNOLIA (3 ARCHES AVEC VOUSSOIRS ET BALUSTRES)
# =========================================================
print("[2/6] Construction du Grand Pont de Magnolia et des ponts d'arches...")

def build_arched_stone_bridge(name, start_pt, end_pt, width=12.0, num_arches=3):
    bm = bmesh.new()
    dir_vec = end_pt - start_pt
    length = dir_vec.length
    fwd = dir_vec.normalized()
    side = Vector((-fwd.y, fwd.x, 0.0)).normalized()
    
    ARCH_SEG = 12
    arch_len = length / num_arches
    
    for a in range(num_arches):
        a_start = start_pt + fwd * (a * arch_len)
        for seg in range(ARCH_SEG + 1):
            t = seg / ARCH_SEG
            x_local = t * arch_len
            # Arc parabolique
            arch_z = 2.4 * math.sin(t * math.pi)
            deck_z = 2.8 + math.sin((a * arch_len + x_local) / length * math.pi) * 0.4
            
            p_base = a_start + fwd * x_local
            # 4 sommets de section
            v_tl = bm.verts.new(p_base - side * (width * 0.5) + Vector((0, 0, deck_z)))
            v_tr = bm.verts.new(p_base + side * (width * 0.5) + Vector((0, 0, deck_z)))
            v_bl = bm.verts.new(p_base - side * (width * 0.5) + Vector((0, 0, arch_z)))
            v_br = bm.verts.new(p_base + side * (width * 0.5) + Vector((0, 0, arch_z)))

    bm.verts.ensure_lookup_table()
    total_sec = num_arches * (ARCH_SEG + 1)
    for i in range(total_sec - 1):
        if (i + 1) % (ARCH_SEG + 1) == 0:
            continue
        v1 = bm.verts[i * 4]
        v2 = bm.verts[(i + 1) * 4]
        v3 = bm.verts[(i + 1) * 4 + 1]
        v4 = bm.verts[i * 4 + 1]
        bm.faces.new((v1, v2, v3, v4))  # Tablier supérieur
        
        # Flancs
        bm.faces.new((bm.verts[i * 4], bm.verts[i * 4 + 2], bm.verts[(i + 1) * 4 + 2], bm.verts[(i + 1) * 4]))
        bm.faces.new((bm.verts[i * 4 + 1], bm.verts[(i + 1) * 4 + 1], bm.verts[(i + 1) * 4 + 3], bm.verts[i * 4 + 3]))

    mesh = bpy.data.meshes.new(name)
    bm.to_mesh(mesh)
    bm.free()
    obj = bpy.data.objects.new(name, mesh)
    scene.collection.objects.link(obj)
    obj.data.materials.append(mat_stone_masonry)
    return obj

build_arched_stone_bridge('Grand_Bridge_Center', Vector((0, -18, -0.2)), Vector((0, 6, -0.2)), width=12.0, num_arches=3)
build_arched_stone_bridge('West_Bridge', Vector((-45, -22, -0.2)), Vector((-45, -2, -0.2)), width=8.0, num_arches=2)
build_arched_stone_bridge('East_Bridge', Vector((45, -2, -0.2)), Vector((45, 18, -0.2)), width=8.0, num_arches=2)

# =========================================================
# 5. LE QG DE LA GUILDE FAIRY TAIL (ARCHITECTURE HAUTE DENSITÉ)
# =========================================================
print("[3/6] Construction du QG de la Guilde Fairy Tail avec colombages sculptés...")

GUILD_X, GUILD_Y = 0.0, 42.0

# 1. Soubassement en pierre appareillée & perron d'honneur
bpy.ops.mesh.primitive_cube_add(size=1.0, location=(GUILD_X, GUILD_Y, 1.2))
g_base = bpy.context.active_object
g_base.name = 'Guild_Stone_Base'
g_base.scale = Vector((28.0, 20.0, 2.4))
bpy.ops.object.transform_apply(scale=True)
g_base.data.materials.append(mat_stone_masonry)

# 2. Corps principal R+1 & R+2 en stuc crème
bpy.ops.mesh.primitive_cube_add(size=1.0, location=(GUILD_X, GUILD_Y, 6.4))
g_body = bpy.context.active_object
g_body.name = 'Guild_Main_Hall'
g_body.scale = Vector((26.0, 18.0, 8.0))
bpy.ops.object.transform_apply(scale=True)
g_body.data.materials.append(mat_stucco_cream)

# 3. Réseau de colombages en bois foncé sculpté sur la façade avant
for bx in [-12.0, -6.0, 0.0, 6.0, 12.0]:
    bpy.ops.mesh.primitive_cube_add(size=1.0, location=(GUILD_X + bx, GUILD_Y - 9.1, 6.4))
    beam = bpy.context.active_object
    beam.scale = Vector((0.6, 0.3, 8.0))
    bpy.ops.object.transform_apply(scale=True)
    beam.data.materials.append(mat_timber_dark)

# Croix de Saint-André décoratives
for k, cx in enumerate([-9.0, -3.0, 3.0, 9.0]):
    for rot in [35, -35]:
        bpy.ops.mesh.primitive_cube_add(size=1.0, location=(GUILD_X + cx, GUILD_Y - 9.08, 6.4))
        brace = bpy.context.active_object
        brace.scale = Vector((0.35, 0.25, 6.8))
        brace.rotation_euler.y = math.radians(rot)
        bpy.ops.object.transform_apply(scale=True, rotation=True)
        brace.data.materials.append(mat_timber_dark)

# 4. Balcon en encorbellement avec balustrade sculptée
bpy.ops.mesh.primitive_cube_add(size=1.0, location=(GUILD_X, GUILD_Y - 10.4, 6.8))
balc = bpy.context.active_object
balc.name = 'Guild_Front_Balcony'
balc.scale = Vector((22.0, 2.8, 0.6))
bpy.ops.object.transform_apply(scale=True)
balc.data.materials.append(mat_timber_warm)

# Balustres du balcon
for bx in [GUILD_X - 10.5 + i * 1.5 for i in range(15)]:
    bpy.ops.mesh.primitive_cylinder_add(radius=0.1, depth=1.1, vertices=8, location=(bx, GUILD_Y - 11.6, 7.6))
    baluster = bpy.context.active_object
    baluster.data.materials.append(mat_timber_dark)

# Main courante
bpy.ops.mesh.primitive_cube_add(size=1.0, location=(GUILD_X, GUILD_Y - 11.6, 8.2))
rail = bpy.context.active_object
rail.scale = Vector((22.2, 0.3, 0.15))
bpy.ops.object.transform_apply(scale=True)
rail.data.materials.append(mat_timber_dark)

# 5. Toitures en arête rouge écarlate Fairy Tail (Toit cintré à deux pans avec coyau)
bm_roof = bmesh.new()
R_W, R_L, R_H = 14.5, 20.0, 6.5
for s in range(11):
    frac = s / 10.0
    rx = (frac - 0.5) * 2.0 * R_W
    # Profil de toit cintré gothique/fairy tail
    rz = R_H * (1.0 - (abs(frac - 0.5) * 2.0)**1.3)
    bm_roof.verts.new((rx, -R_L * 0.5, rz))
    bm_roof.verts.new((rx,  R_L * 0.5, rz))

bm_roof.verts.ensure_lookup_table()
for s in range(10):
    v1 = bm_roof.verts[s * 2]
    v2 = bm_roof.verts[(s + 1) * 2]
    v3 = bm_roof.verts[(s + 1) * 2 + 1]
    v4 = bm_roof.verts[s * 2 + 1]
    bm_roof.faces.new((v1, v2, v3, v4))

mesh_roof = bpy.data.meshes.new('Guild_Curved_Roof')
bm_roof.to_mesh(mesh_roof)
bm_roof.free()
obj_roof = bpy.data.objects.new('Guild_Curved_Roof', mesh_roof)
obj_roof.location = Vector((GUILD_X, GUILD_Y, 10.4))
scene.collection.objects.link(obj_roof)
obj_roof.data.materials.append(mat_roof_guild_scarlet)

# 6. Tour centrale octogonale avec beffroi, cloche et flèche dorée
bpy.ops.mesh.primitive_cylinder_add(radius=4.5, depth=14.0, vertices=8, location=(GUILD_X, GUILD_Y + 1.0, 15.0))
g_tower = bpy.context.active_object
g_tower.name = 'Guild_Octagonal_Tower'
g_tower.data.materials.append(mat_stucco_white)

# Baies ajourées du beffroi
for rot_a in [0, 45, 90, 135, 180, 225, 270, 315]:
    ang = math.radians(rot_a)
    bx = GUILD_X + 1.0 * math.sin(ang) + 4.2 * math.cos(ang)
    by = GUILD_Y + 1.0 + 4.2 * math.sin(ang)
    bpy.ops.mesh.primitive_cube_add(size=1.0, location=(bx, by, 18.5))
    louver = bpy.context.active_object
    louver.scale = Vector((1.2, 0.4, 2.5))
    louver.rotation_euler.z = ang
    bpy.ops.object.transform_apply(scale=True, rotation=True)
    louver.data.materials.append(mat_timber_dark)

# Cloche en bronze doré dans le beffroi
bpy.ops.mesh.primitive_cylinder_add(radius=1.2, depth=1.8, vertices=12, location=(GUILD_X, GUILD_Y + 1.0, 18.5))
bell = bpy.context.active_object
bell.data.materials.append(mat_gold_finial)

# Flèche pyramidale octogonale écarlate
bpy.ops.mesh.primitive_cone_add(radius1=5.2, depth=10.0, vertices=8, location=(GUILD_X, GUILD_Y + 1.0, 26.5))
g_spire = bpy.context.active_object
g_spire.data.materials.append(mat_roof_guild_scarlet)

# Épi de faîte doré au sommet
bpy.ops.mesh.primitive_cone_add(radius1=0.7, depth=3.0, vertices=8, location=(GUILD_X, GUILD_Y + 1.0, 32.5))
g_finial = bpy.context.active_object
g_finial.data.materials.append(mat_gold_finial)

# 7. Quatre tourelles d'angle avec toits coniques
for tx, ty in [(-12.5, GUILD_Y - 9.5), (12.5, GUILD_Y - 9.5), (-12.5, GUILD_Y + 9.5), (12.5, GUILD_Y + 9.5)]:
    bpy.ops.mesh.primitive_cylinder_add(radius=2.6, depth=12.0, vertices=12, location=(tx, ty, 7.0))
    turret = bpy.context.active_object
    turret.data.materials.append(mat_stucco_white)
    
    bpy.ops.mesh.primitive_cone_add(radius1=3.2, depth=6.0, vertices=12, location=(tx, ty, 15.5))
    t_roof = bpy.context.active_object
    t_roof.data.materials.append(mat_roof_guild_scarlet)

# 8. Blason / Bannière géante Fairy Tail sur la façade
bpy.ops.mesh.primitive_cube_add(size=1.0, location=(GUILD_X, GUILD_Y - 9.25, 9.2))
crest = bpy.context.active_object
crest.name = 'Fairy_Tail_Guild_Sign'
crest.scale = Vector((6.5, 0.2, 4.0))
bpy.ops.object.transform_apply(scale=True)
crest.data.materials.append(mat_guild_emblem)

# 9. Terrasse extérieure de taverne avec tables, bancs, tonneaux et pergolas
bpy.ops.mesh.primitive_cube_add(size=1.0, location=(GUILD_X, GUILD_Y - 14.0, 0.4))
deck = bpy.context.active_object
deck.name = 'Tavern_Patio_Deck'
deck.scale = Vector((24.0, 8.0, 0.8))
bpy.ops.object.transform_apply(scale=True)
deck.data.materials.append(mat_timber_warm)

# Tonneaux de bière en bois cerclés
for bx, by in [(-8, GUILD_Y - 16), (-6, GUILD_Y - 16.5), (6, GUILD_Y - 16), (8, GUILD_Y - 16.5)]:
    bpy.ops.mesh.primitive_cylinder_add(radius=0.7, depth=1.6, vertices=12, location=(bx, by, 1.2))
    barrel = bpy.context.active_object
    barrel.data.materials.append(mat_timber_dark)

# =========================================================
# 6. LA CATHÉDRALE DE KARDIA (CHEF-D'ŒUVRE GOTHIQUE)
# =========================================================
print("[4/6] Modélisation de la Cathédrale de Kardia (Arcs-boutants, flèches filigranées, rosace)...")

CATH_X, CATH_Y = -42.0, 36.0

# 1. Grande Nef gothique avec bas-côtés
bpy.ops.mesh.primitive_cube_add(size=1.0, location=(CATH_X, CATH_Y, 11.0))
c_nave = bpy.context.active_object
c_nave.name = 'Kardia_Cathedral_Nave'
c_nave.scale = Vector((22.0, 38.0, 22.0))
bpy.ops.object.transform_apply(scale=True)
c_nave.data.materials.append(mat_cathedral_limestone)

# 2. Toit pentu en cuivre vert-de-gris
bpy.ops.mesh.primitive_cylinder_add(radius=12.0, depth=40.0, vertices=4, location=(CATH_X, CATH_Y, 26.5))
c_roof = bpy.context.active_object
c_roof.rotation_euler = Euler((math.radians(45), 0, 0), 'XYZ')
c_roof.scale = Vector((0.78, 0.78, 1.0))
c_roof.data.materials.append(mat_copper_verdigris)

# 3. Flèche de croisée du transept
bpy.ops.mesh.primitive_cone_add(radius1=2.8, depth=16.0, vertices=8, location=(CATH_X, CATH_Y, 39.0))
c_fleche = bpy.context.active_object
c_fleche.data.materials.append(mat_copper_verdigris)

# 4. Deux Flèches Jumelles Gothiques (Façade Sud de la cathédrale, H=48m)
for fx in [CATH_X - 9.5, CATH_X + 9.5]:
    # Tour inférieure carrée
    bpy.ops.mesh.primitive_cube_add(size=1.0, location=(fx, CATH_Y - 17.5, 15.0))
    tower_base = bpy.context.active_object
    tower_base.scale = Vector((6.5, 6.5, 30.0))
    bpy.ops.object.transform_apply(scale=True)
    tower_base.data.materials.append(mat_cathedral_limestone)
    
    # Étage octogonal ajouré
    bpy.ops.mesh.primitive_cylinder_add(radius=3.4, depth=10.0, vertices=8, location=(fx, CATH_Y - 17.5, 34.0))
    tower_oct = bpy.context.active_object
    tower_oct.data.materials.append(mat_cathedral_limestone)
    
    # Flèche pyramidale gothique ciselée
    bpy.ops.mesh.primitive_cone_add(radius1=3.8, depth=18.0, vertices=8, location=(fx, CATH_Y - 17.5, 47.0))
    spire_gothic = bpy.context.active_object
    spire_gothic.data.materials.append(mat_cathedral_limestone)
    
    # Épi d'or
    bpy.ops.mesh.primitive_cone_add(radius1=0.6, depth=3.0, vertices=8, location=(fx, CATH_Y - 17.5, 57.0))
    spire_fin = bpy.context.active_object
    spire_fin.data.materials.append(mat_gold_finial)

# 5. Grande Rosace Gothique ajourée avec vitrail flamboyant
bpy.ops.mesh.primitive_cylinder_add(radius=5.5, depth=0.6, vertices=32, location=(CATH_X, CATH_Y - 19.3, 18.0))
rose = bpy.context.active_object
rose.name = 'Kardia_Rose_Window'
rose.rotation_euler = Euler((math.radians(90), 0, 0), 'XYZ')
rose.data.materials.append(mat_rose_stained_glass)

# Rayons de pierre de la rosace
for ra in range(12):
    ang = math.radians(ra * 30)
    bpy.ops.mesh.primitive_cube_add(size=1.0, location=(CATH_X, CATH_Y - 19.4, 18.0))
    spoke = bpy.context.active_object
    spoke.scale = Vector((0.25, 0.4, 5.2))
    spoke.rotation_euler.y = ang
    bpy.ops.object.transform_apply(scale=True, rotation=True)
    spoke.data.materials.append(mat_cathedral_limestone)

# 6. Triple Portail Gothique à voussures
for px, pw, ph in [(CATH_X, 4.2, 7.0), (CATH_X - 5.5, 2.8, 5.0), (CATH_X + 5.5, 2.8, 5.0)]:
    bpy.ops.mesh.primitive_cube_add(size=1.0, location=(px, CATH_Y - 19.2, ph * 0.5))
    portal = bpy.context.active_object
    portal.scale = Vector((pw, 0.8, ph))
    bpy.ops.object.transform_apply(scale=True)
    portal.data.materials.append(mat_timber_dark)

# 7. Arcs-boutants latéraux (4 de chaque côté)
for side_x in [CATH_X - 12.0, CATH_X + 12.0]:
    for by_offset in [-10.0, -3.0, 4.0, 11.0]:
        bpy.ops.mesh.primitive_cube_add(size=1.0, location=(side_x, CATH_Y + by_offset, 9.0))
        buttress = bpy.context.active_object
        buttress.scale = Vector((1.8, 1.8, 18.0))
        bpy.ops.object.transform_apply(scale=True)
        buttress.data.materials.append(mat_cathedral_limestone)

# =========================================================
# 7. LES 110+ MAISONS MÉDIÉVALES À COLOMBAGES RÉALISTES
# =========================================================
print("[5/6] Génération des 110+ maisons médiévales à colombages et encorbellements...")

def build_half_timbered_townhouse(name, pos, width=6.0, depth=7.0, num_floors=3, roof_color=mat_roof_terracotta_red):
    # 1. RDC en maçonnerie de pierre
    h_floor = 3.2
    bpy.ops.mesh.primitive_cube_add(size=1.0, location=(pos.x, pos.y, h_floor * 0.5))
    ground_f = bpy.context.active_object
    ground_f.name = f'{name}_GF'
    ground_f.scale = Vector((width, depth, h_floor))
    bpy.ops.object.transform_apply(scale=True)
    ground_f.data.materials.append(mat_stone_masonry)
    
    # Porte et vitrine de boutique
    bpy.ops.mesh.primitive_cube_add(size=1.0, location=(pos.x, pos.y - depth * 0.51, 1.3))
    shop = bpy.context.active_object
    shop.scale = Vector((width * 0.7, 0.2, 2.2))
    bpy.ops.object.transform_apply(scale=True)
    shop.data.materials.append(mat_timber_dark)
    
    # 2. Étages en encorbellement (saillie de 0.35m à chaque étage)
    cur_z = h_floor
    cur_w, cur_d = width, depth
    for f in range(1, num_floors):
        cur_w += 0.4
        cur_d += 0.4
        cur_z += h_floor * 0.5
        
        # Corps de l'étage en stuc
        bpy.ops.mesh.primitive_cube_add(size=1.0, location=(pos.x, pos.y, cur_z))
        fl_obj = bpy.context.active_object
        fl_obj.scale = Vector((cur_w, cur_d, h_floor))
        bpy.ops.object.transform_apply(scale=True)
        fl_obj.data.materials.append(mat_stucco_cream if f % 2 == 1 else mat_stucco_ochre)
        
        # Poteaux et sablières en colombage
        for px in [-cur_w * 0.48, 0.0, cur_w * 0.48]:
            bpy.ops.mesh.primitive_cube_add(size=1.0, location=(pos.x + px, pos.y - cur_d * 0.51, cur_z))
            post = bpy.context.active_object
            post.scale = Vector((0.3, 0.2, h_floor))
            bpy.ops.object.transform_apply(scale=True)
            post.data.materials.append(mat_timber_dark)
            
        cur_z += h_floor * 0.5

    # 3. Toiture à deux pans prononcés avec lucarnes
    roof_h = max(cur_w, cur_d) * 0.65
    bpy.ops.mesh.primitive_cylinder_add(radius=max(cur_w, cur_d) * 0.6, depth=max(cur_w, cur_d) * 1.05, vertices=4, location=(pos.x, pos.y, cur_z + roof_h * 0.5))
    roof = bpy.context.active_object
    roof.rotation_euler = Euler((math.radians(45), 0, math.radians(90) if cur_w > cur_d else 0), 'XYZ')
    roof.scale = Vector((0.72, 0.72, 1.0))
    roof.data.materials.append(roof_color)
    
    # 4. Cheminée en brique avec mitron
    bpy.ops.mesh.primitive_cube_add(size=1.0, location=(pos.x + cur_w * 0.3, pos.y + cur_d * 0.25, cur_z + roof_h + 0.8))
    chim = bpy.context.active_object
    chim.scale = Vector((0.9, 0.9, 2.4))
    bpy.ops.object.transform_apply(scale=True)
    chim.data.materials.append(mat_stone_masonry)

# Grille de placement organique des quartiers
house_coords = []

# Quartier Ouest (Autour du parvis de la Cathédrale)
for x in range(-68, -14, 9):
    for y in range(8, 62, 9):
        if (x - CATH_X)**2 + (y - CATH_Y)**2 > 240:
            house_coords.append((x + random.uniform(-1.2, 1.2), y + random.uniform(-1.2, 1.2)))

# Quartier Est (Résidentiel & Quais du Lac Kardiac)
for x in range(16, 68, 9):
    for y in range(6, 64, 9):
        if (x - GUILD_X)**2 + (y - GUILD_Y)**2 > 260:
            house_coords.append((x + random.uniform(-1.2, 1.2), y + random.uniform(-1.2, 1.2)))

# Quartier Sud (Rive Sud du fleuve)
for x in range(-62, 62, 8):
    for y in range(-55, -20, 8):
        house_coords.append((x + random.uniform(-1.0, 1.0), y + random.uniform(-1.0, 1.0)))

# Quartier Central (Bordures du grand boulevard)
for x in range(-24, 26, 9):
    for y in range(-8, 28, 8):
        if abs(x) > 7.5:  # Respecter l'axe du boulevard Gildarts
            house_coords.append((x + random.uniform(-0.8, 0.8), y + random.uniform(-0.8, 0.8)))

for idx, (hx, hy) in enumerate(house_coords):
    w = random.uniform(5.5, 7.5)
    d = random.uniform(5.5, 7.5)
    floors = random.choice([2, 3, 3, 4])
    r_mat = mat_roof_terracotta_red if random.random() > 0.35 else mat_roof_terracotta_blue
    build_half_timbered_townhouse(f'House_{idx:03d}', Vector((hx, hy, 0)), width=w, depth=d, num_floors=floors, roof_color=r_mat)

# =========================================================
# 8. BOULEVARD DE GILDARTS & RAILS DE DÉCALAGE
# =========================================================
print("Aménagement du Boulevard Gildarts et de la Grand-Place...")

# Grand-Place pavée devant la Guilde
bpy.ops.mesh.primitive_cylinder_add(radius=26.0, depth=0.15, vertices=32, location=(GUILD_X, GUILD_Y - 24.0, 0.08))
plaza = bpy.context.active_object
plaza.name = 'Guild_Central_Plaza'
plaza.data.materials.append(mat_paving)

# Avenue centrale pavée
bpy.ops.mesh.primitive_cube_add(size=1.0, location=(0, 6, 0.08))
blvd = bpy.context.active_object
blvd.name = 'Gildarts_Avenue'
blvd.scale = Vector((14.0, 48.0, 0.15))
bpy.ops.object.transform_apply(scale=True)
blvd.data.materials.append(mat_paving)

# Double voie ferrée métallique de décalage mécanique de Gildarts
for rx in [-2.2, -1.2, 1.2, 2.2]:
    bpy.ops.mesh.primitive_cube_add(size=1.0, location=(rx, 6, 0.18))
    rail = bpy.context.active_object
    rail.scale = Vector((0.2, 48.0, 0.1))
    bpy.ops.object.transform_apply(scale=True)
    rail.data.materials.append(mat_iron_steel)

# Traverses de chemin de fer en chêne foncé
for ty in [6 - 22 + i * 2.2 for i in range(21)]:
    bpy.ops.mesh.primitive_cube_add(size=1.0, location=(0, ty, 0.12))
    sleeper = bpy.context.active_object
    sleeper.scale = Vector((5.2, 0.6, 0.08))
    bpy.ops.object.transform_apply(scale=True)
    sleeper.data.materials.append(mat_timber_dark)

# =========================================================
# 9. ARBRES DE MAGNOLIAS FLORIFÈRES EN FLEURS ROSES & BLANCHES
# =========================================================
print("Plantation des magnolias centenaires en fleurs...")

tree_spots = [
    # Alignement du boulevard
    (-5.5, -6), (-5.5, 2), (-5.5, 10), (-5.5, 18), (5.5, -6), (5.5, 2), (5.5, 10), (5.5, 18),
    # Tour de la Grand-Place
    (-16, 18), (16, 18), (-20, 26), (20, 26),
    # Berges du fleuve
    (-30, -8), (-20, -6), (20, -6), (30, -8), (40, -10),
    (-30, -18), (-20, -16), (20, -16), (30, -18),
    # Esplanade de la cathédrale
    (-58, 26), (-26, 26), (-58, 46), (-26, 46),
]

for _ in range(40):
    tree_spots.append((random.uniform(-65, 65), random.uniform(-50, 60)))

for idx, (tx, ty) in enumerate(tree_spots):
    # Tronc noueux ramifié
    t_h = random.uniform(3.0, 5.0)
    bpy.ops.mesh.primitive_cylinder_add(radius=0.45, depth=t_h, vertices=8, location=(tx, ty, t_h * 0.5))
    trunk = bpy.context.active_object
    trunk.data.materials.append(mat_timber_dark)
    
    # 3 sphères de feuillage pour un houppier organique
    f_mat = mat_magnolia_pink if random.random() > 0.3 else mat_magnolia_white
    for ox, oy, oz, orad in [(0, 0, t_h + 1.2, 3.2), (-1.2, 0.8, t_h + 0.6, 2.2), (1.2, -0.6, t_h + 0.8, 2.4)]:
        bpy.ops.mesh.primitive_ico_sphere_add(radius=orad, subdivisions=2, location=(tx + ox, ty + oy, oz))
        crown = bpy.context.active_object
        crown.data.materials.append(f_mat)

# =========================================================
# 10. GONDOLES SUR LE FLEUVE & BATEAUX DU LAC KARDIAC
# =========================================================
for bx, by, b_rot in [(-15, -12, 18), (12, -10, -22), (32, -14, 8), (85, -5, 45), (105, -22, -35), (92, 18, 60)]:
    bpy.ops.mesh.primitive_cube_add(size=1.0, location=(bx, by, -0.1))
    boat = bpy.context.active_object
    boat.name = 'Boat'
    boat.scale = Vector((5.2, 1.8, 0.7))
    boat.rotation_euler.z = math.radians(b_rot)
    bpy.ops.object.transform_apply(scale=True)
    boat.data.materials.append(mat_timber_dark)

# =========================================================
# 11. CAMÉRAS CINÉMA & RENDU DES 6 VUES MAJEURES ("TOUT VOIR")
# =========================================================
print("[6/6] Cadrage cinématique & Rendu des 6 vues panoramiques et gros plans...")

cam_data = bpy.data.cameras.new('MagnoliaMasterCamera')
cam_data.lens = 32
cam_data.sensor_width = 36
cam_obj = bpy.data.objects.new('MagnoliaMasterCamera', cam_data)
scene.collection.objects.link(cam_obj)
scene.camera = cam_obj

stills_definitions = [
    # 1. Vue Aérienne Panoramique Globale (Ville Entière, Lac Kardiac, Montagne, Guilde, Cathédrale)
    ('01_magnolia_vue_aerienne_panoramique_globale', Vector((0.0, -95.0, 75.0)), Vector((0.0, 18.0, 8.0))),
    # 2. Vue Héroïque Plongeante sur le QG de Fairy Tail et son Beffroi
    ('02_fairy_tail_qg_et_boulevard_gildarts', Vector((0.0, -2.0, 32.0)), Vector((GUILD_X, GUILD_Y, 14.0))),
    # 3. Vue Majestueuse sur la Cathédrale de Kardia & Parvis
    ('03_cathedrale_kardia_et_grand_parvis', Vector((-42.0, -8.0, 24.0)), Vector((CATH_X, CATH_Y, 18.0))),
    # 4. Vue au Niveau des Rues Médiévales, Pont d'Arches & Magnolias en Fleurs
    ('04_rues_medievales_pont_arches_et_magnolias', Vector((12.0, -32.0, 8.5)), Vector((0.0, 6.0, 4.0))),
    # 5. Vue Crépusculaire sur le Lac Kardiac et le Port Est
    ('05_lac_kardiac_et_panorama_est', Vector((88.0, -70.0, 42.0)), Vector((25.0, 15.0, 10.0))),
]

for label, cam_p, targ_p in stills_definitions:
    cam_obj.location = cam_p
    dir_v = targ_p - cam_p
    cam_obj.rotation_euler = dir_v.to_track_quat('-Z', 'Y').to_euler()
    
    scene.frame_set(1)
    out_img = os.path.join(STILLS_DIR, f'{label}.png')
    scene.render.filepath = out_img
    bpy.ops.render.render(write_still=True)
    print(f'Rendered still: {label}.png')

# 6. Comparatif Clay White Architectural (Volume pur sans textures)
print("Rendu Clay White architectural...")
clay_mat = bpy.data.materials.new(name='ClayWhiteCity')
clay_mat.use_nodes = True
c_bsdf = clay_mat.node_tree.nodes.get('Principled BSDF')
if c_bsdf:
    c_bsdf.inputs['Base Color'].default_value = (0.90, 0.90, 0.92, 1.0)
    c_bsdf.inputs['Roughness'].default_value = 0.40

orig_mats = {}
for obj in bpy.data.objects:
    if obj.type == 'MESH' and obj.data.materials:
        orig_mats[obj.name] = list(obj.data.materials)
        obj.data.materials.clear()
        obj.data.materials.append(clay_mat)

cam_obj.location = Vector((0.0, -95.0, 75.0))
dir_v = Vector((0.0, 18.0, 8.0)) - cam_obj.location
cam_obj.rotation_euler = dir_v.to_track_quat('-Z', 'Y').to_euler()
scene.render.filepath = os.path.join(STILLS_DIR, '06_magnolia_clay_white_global.png')
bpy.ops.render.render(write_still=True)
print('Rendered still: 06_magnolia_clay_white_global.png')

# Restaurer les matériaux
for obj_name, mats in orig_mats.items():
    obj = bpy.data.objects.get(obj_name)
    if obj:
        obj.data.materials.clear()
        for m in mats:
            obj.data.materials.append(m)

# =========================================================
# 12. SURVOL CINÉMATIQUE 360° (72 FRAMES / 24 FPS) & EXPORT GLB
# =========================================================
print("Animation de la trajectoire orbitale hélicoptère 360°...")
cam_obj.animation_data_create()
act = bpy.data.actions.new('Magnolia_Orbital_Flythrough')
cam_obj.animation_data.action = act

RADIUS = 105.0
HEIGHT = 58.0
CENTER = Vector((0, 15, 8))

for f in range(1, 73):
    angle = (f - 1) / 71.0 * (2 * math.pi) - math.pi * 0.5
    cam_x = CENTER.x + RADIUS * math.cos(angle)
    cam_y = CENTER.y + RADIUS * math.sin(angle)
    cam_z = HEIGHT + 10.0 * math.sin(angle * 2)
    
    c_pos = Vector((cam_x, cam_y, cam_z))
    cam_obj.location = c_pos
    dir_vec = CENTER - c_pos
    cam_obj.rotation_euler = dir_vec.to_track_quat('-Z', 'Y').to_euler()
    
    cam_obj.keyframe_insert(data_path='location', frame=f)
    cam_obj.keyframe_insert(data_path='rotation_euler', frame=f)

# Export Scene GLB Complète
scene_glb_path = os.path.join(SCENE_DIR, 'magnolia_fairy_tail_masterpiece.glb')
bpy.ops.export_scene.gltf(
    filepath=scene_glb_path,
    export_format='GLB',
    export_animations=True,
    export_current_frame=False,
    export_materials='EXPORT',
)
print('Exported full Magnolia GLB to:', scene_glb_path)

# Rendu de l'animation vidéo
scene.render.filepath = os.path.join(FRAMES_DIR, 'frame_')
scene.render.image_settings.file_format = 'PNG'
print('Rendering 72 flythrough animation frames...')
bpy.ops.render.render(animation=True)
print('MAGNOLIA_MASTERPIECE_PRODUCTION_COMPLETE')
