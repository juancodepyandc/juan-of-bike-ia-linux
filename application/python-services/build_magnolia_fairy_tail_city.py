#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""build_magnolia_fairy_tail_city.py — Générateur 3D Haute Fidélité de la Ville Entière de Magnolia (Fairy Tail).
Comprend :
- Le QG de la Guilde Fairy Tail (Multi-étages, tourelles coniques rouges, clocher central, terrasse de taverne, bannière Fairy Tail).
- La Cathédrale de Kardia (Grandioses tours jumelles gothiques, rosace, parvis de pierre).
- Le Lac Kardiac et le Réseau de Canaux navigables (Quais en pierre, ponts d'arches, gondoles).
- Les Rues Médiévales et 120+ Bâtiments à colombages (Toits de tuiles rouges et bleues, cheminées, auvents de marché).
- Le Boulevard de Gildarts (Rails et séparateurs de décalage de la ville).
- La Gare de Magnolia et la voie ferrée.
- Les Arbres de Magnolias en fleurs roses, parcs, collines et remparts d'enceinte.
- 5 Vues Caméras Clés + Survol Cinématique 360° (72 Frames / 24 fps) + Export GLB.
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

random.seed(42)

print("==========================================================")
print("  AURORA 3D : PRODUCTION DE LA VILLE ENTIÈRE DE MAGNOLIA")
print("==========================================================")

# =========================================================
# 1. SETUP CYCLES & LIGHTING FIORE SOLEIL ÉCLATANT
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

# World Anime Sky (Ciel bleu azur de Fiore)
w = bpy.data.worlds.new('FioreSky')
scene.world = w
w.use_nodes = True
bg = w.node_tree.nodes.get('Background')
if bg:
    bg.inputs['Color'].default_value = (0.45, 0.70, 0.95, 1.0)
    bg.inputs['Strength'].default_value = 1.0

# Soleil radieux de Fiore (Sun Light)
sun_data = bpy.data.lights.new('FioreSun', type='SUN')
sun_data.energy = 4.5
sun_data.color = (1.0, 0.96, 0.88)
sun_data.angle = math.radians(1.5)
sun_obj = bpy.data.objects.new('FioreSun', sun_data)
sun_obj.rotation_euler = Euler((math.radians(52), math.radians(18), math.radians(-40)), 'XYZ')
scene.collection.objects.link(sun_obj)

# Sky Fill Light
fill_data = bpy.data.lights.new('SkyFill', type='SUN')
fill_data.energy = 1.2
fill_data.color = (0.65, 0.80, 1.0)
fill_obj = bpy.data.objects.new('SkyFill', fill_data)
fill_obj.rotation_euler = Euler((math.radians(70), math.radians(0), math.radians(140)), 'XYZ')
scene.collection.objects.link(fill_obj)

# =========================================================
# 2. CRÉATION DES SHADERS PBR DE MAGNOLIA
# =========================================================
def create_pbr_mat(name, base_color, metallic=0.0, roughness=0.5, specular=0.5, emission=(0,0,0,1), emission_strength=0.0):
    mat = bpy.data.materials.new(name=name)
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get('Principled BSDF')
    if bsdf:
        bsdf.inputs['Base Color'].default_value = (*base_color, 1.0) if len(base_color) == 3 else base_color
        bsdf.inputs['Metallic'].default_value = metallic
        bsdf.inputs['Roughness'].default_value = roughness
        if 'Specular IOR Level' in bsdf.inputs:
            bsdf.inputs['Specular IOR Level'].default_value = specular
        if 'Emission Color' in bsdf.inputs:
            bsdf.inputs['Emission Color'].default_value = emission
            bsdf.inputs['Emission Strength'].default_value = emission_strength
    return mat

mat_water = create_pbr_mat('KardiacWater', (0.15, 0.48, 0.65), metallic=0.1, roughness=0.08, specular=0.9)
mat_stone_wall = create_pbr_mat('CityStone', (0.55, 0.52, 0.48), metallic=0.0, roughness=0.75)
mat_piazza_paving = create_pbr_mat('PiazzaStone', (0.72, 0.68, 0.60), metallic=0.0, roughness=0.60)
mat_stucco_cream = create_pbr_mat('StuccoCream', (0.88, 0.84, 0.76), metallic=0.0, roughness=0.80)
mat_stucco_white = create_pbr_mat('StuccoWhite', (0.92, 0.92, 0.90), metallic=0.0, roughness=0.65)
mat_timber = create_pbr_mat('DarkTimber', (0.24, 0.14, 0.08), metallic=0.0, roughness=0.45)
mat_roof_red = create_pbr_mat('RoofTerracottaRed', (0.75, 0.18, 0.12), metallic=0.0, roughness=0.50)
mat_roof_blue = create_pbr_mat('RoofTerracottaBlue', (0.18, 0.38, 0.65), metallic=0.0, roughness=0.50)
mat_roof_guild = create_pbr_mat('RoofGuildRed', (0.85, 0.12, 0.12), metallic=0.0, roughness=0.40)
mat_guild_crest = create_pbr_mat('GuildCrestRed', (0.95, 0.05, 0.08), metallic=0.2, roughness=0.30, emission=(0.95, 0.05, 0.08, 1.0), emission_strength=1.5)
mat_gold = create_pbr_mat('GuildGoldSpire', (0.95, 0.80, 0.25), metallic=0.92, roughness=0.22)
mat_cathedral_marble = create_pbr_mat('CathedralMarble', (0.90, 0.88, 0.85), metallic=0.05, roughness=0.35)
mat_rose_window = create_pbr_mat('RoseWindow', (0.2, 0.4, 0.8), metallic=0.1, roughness=0.1, emission=(0.3, 0.6, 0.9, 1.0), emission_strength=2.0)
mat_grass = create_pbr_mat('LushGrass', (0.28, 0.55, 0.18), metallic=0.0, roughness=0.85)
mat_magnolia_pink = create_pbr_mat('MagnoliaBlossom', (0.95, 0.60, 0.75), metallic=0.0, roughness=0.45)
mat_wood_deck = create_pbr_mat('WoodDecking', (0.42, 0.28, 0.16), metallic=0.0, roughness=0.60)
mat_iron_rails = create_pbr_mat('GildartsIronRails', (0.20, 0.20, 0.22), metallic=0.85, roughness=0.35)

# =========================================================
# 3. TOPOGRAPHIE : TERRAIN, LAC KARDIAC & CANAUX
# =========================================================
print("[1/5] Modélisation de la topographie, du Lac Kardiac et des canaux...")

# Terrain principal (Herbe vallonnée)
bpy.ops.mesh.primitive_plane_add(size=1.0, location=(0, 0, -0.2))
ground = bpy.context.active_object
ground.name = 'Magnolia_Terrain'
ground.scale = Vector((220, 220, 1))
bpy.ops.object.transform_apply(scale=True)
ground.data.materials.append(mat_grass)

# Collines environnantes au nord et à l'ouest
for cx, cy, cz, csx, csy in [(-60, 60, 8, 50, 45), (60, 70, 12, 55, 40), (-70, -30, 7, 45, 50)]:
    bpy.ops.mesh.primitive_cylinder_add(radius=1.0, depth=1.0, vertices=16, location=(cx, cy, cz * 0.5 - 0.2))
    hill = bpy.context.active_object
    hill.scale = Vector((csx, csy, cz))
    bpy.ops.object.transform_apply(scale=True)
    hill.data.materials.append(mat_grass)

# Lac Kardiac (Grand plan d'eau à l'est)
bpy.ops.mesh.primitive_plane_add(size=1.0, location=(65, -10, 0.0))
lake = bpy.context.active_object
lake.name = 'Kardiac_Lake'
lake.scale = Vector((70, 140, 1))
bpy.ops.object.transform_apply(scale=True)
lake.data.materials.append(mat_water)

# Grand Canal Central (Traversant Magnolia d'Ouest en Est vers le Lac)
bpy.ops.mesh.primitive_plane_add(size=1.0, location=(0, -8, 0.0))
canal = bpy.context.active_object
canal.name = 'Magnolia_Canal_Water'
canal.scale = Vector((130, 12, 1))
bpy.ops.object.transform_apply(scale=True)
canal.data.materials.append(mat_water)

# Quais en pierre du canal (Nord & Sud)
for qy in [-2.0, -14.0]:
    bpy.ops.mesh.primitive_cube_add(size=1.0, location=(0, qy, 0.4))
    quay = bpy.context.active_object
    quay.scale = Vector((130, 1.2, 0.8))
    bpy.ops.object.transform_apply(scale=True)
    quay.data.materials.append(mat_stone_wall)

# Grand Pont de Magnolia (Pont principal en arc enjambant le canal)
bpy.ops.mesh.primitive_cube_add(size=1.0, location=(0, -8, 1.2))
main_bridge = bpy.context.active_object
main_bridge.name = 'Grand_Magnolia_Bridge'
main_bridge.scale = Vector((10.0, 14.0, 0.8))
bpy.ops.object.transform_apply(scale=True)
main_bridge.data.materials.append(mat_piazza_paving)

# Parapets du pont
for px in [-4.6, 4.6]:
    bpy.ops.mesh.primitive_cube_add(size=1.0, location=(px, -8, 2.0))
    parapet = bpy.context.active_object
    parapet.scale = Vector((0.6, 14.0, 0.8))
    bpy.ops.object.transform_apply(scale=True)
    parapet.data.materials.append(mat_stone_wall)

# Second pont d'arches
bpy.ops.mesh.primitive_cube_add(size=1.0, location=(-35, -8, 1.0))
sec_bridge = bpy.context.active_object
sec_bridge.scale = Vector((6.0, 14.0, 0.7))
bpy.ops.object.transform_apply(scale=True)
sec_bridge.data.materials.append(mat_piazza_paving)

# =========================================================
# 4. LE BOULEVARD CENTRAL DE GILDARTS & PLACE PRINCIPALE
# =========================================================
print("[2/5] Construction du Boulevard de Gildarts et de la Grand-Place...")

# Grand-Place devant la guilde
bpy.ops.mesh.primitive_cylinder_add(radius=22.0, depth=0.1, vertices=32, location=(0, 24, 0.05))
plaza = bpy.context.active_object
plaza.name = 'Guild_Plaza'
plaza.data.materials.append(mat_piazza_paving)

# Boulevard central menant du pont sud à la guilde
bpy.ops.mesh.primitive_cube_add(size=1.0, location=(0, 8, 0.05))
blvd = bpy.context.active_object
blvd.name = 'Gildarts_Boulevard'
blvd.scale = Vector((12.0, 32.0, 0.1))
bpy.ops.object.transform_apply(scale=True)
blvd.data.materials.append(mat_piazza_paving)

# Rails de décalage de Gildarts (Double voie de fer au centre de l'avenue)
for rx in [-1.5, 1.5]:
    bpy.ops.mesh.primitive_cube_add(size=1.0, location=(rx, 8, 0.12))
    rail = bpy.context.active_object
    rail.scale = Vector((0.25, 32.0, 0.08))
    bpy.ops.object.transform_apply(scale=True)
    rail.data.materials.append(mat_iron_rails)

# =========================================================
# 5. LE QG DE LA GUILDE FAIRY TAIL (SYMBOLE MAJEUR)
# =========================================================
print("[3/5] Modélisation du QG de la Guilde Fairy Tail...")

# Corps principal de la guilde (Bâtiment imposant à étages)
bpy.ops.mesh.primitive_cube_add(size=1.0, location=(0, 36, 4.0))
guild_main = bpy.context.active_object
guild_main.name = 'Fairy_Tail_Guild_Hall'
guild_main.scale = Vector((22.0, 16.0, 8.0))
bpy.ops.object.transform_apply(scale=True)
guild_main.data.materials.append(mat_stucco_cream)

# Colombages décoratifs de la guilde
for bx in [-10.8, -5.4, 0.0, 5.4, 10.8]:
    bpy.ops.mesh.primitive_cube_add(size=1.0, location=(bx, 27.9, 4.0))
    beam = bpy.context.active_object
    beam.scale = Vector((0.5, 0.3, 8.0))
    bpy.ops.object.transform_apply(scale=True)
    beam.data.materials.append(mat_timber)

# Toit principal en arête rouge Fairy Tail
bpy.ops.mesh.primitive_cylinder_add(radius=12.0, depth=23.0, vertices=4, location=(0, 36, 9.8))
guild_roof = bpy.context.active_object
guild_roof.rotation_euler = Euler((math.radians(45), 0, math.radians(90)), 'XYZ')
guild_roof.scale = Vector((0.7, 0.7, 1.0))
guild_roof.data.materials.append(mat_roof_guild)

# Tour centrale avec Clocher et Flèche Dorée
bpy.ops.mesh.primitive_cylinder_add(radius=3.5, depth=14.0, vertices=16, location=(0, 36, 12.0))
guild_tower = bpy.context.active_object
guild_tower.name = 'Guild_Central_Tower'
guild_tower.data.materials.append(mat_stucco_white)

# Flèche conique rouge de la tour
bpy.ops.mesh.primitive_cone_add(radius1=4.2, depth=7.0, vertices=16, location=(0, 36, 21.5))
guild_spire = bpy.context.active_object
guild_spire.data.materials.append(mat_roof_guild)

# Épi de faîte doré au sommet de la tour
bpy.ops.mesh.primitive_cone_add(radius1=0.6, depth=2.5, vertices=8, location=(0, 36, 25.5))
spire_gold = bpy.context.active_object
spire_gold.data.materials.append(mat_gold)

# Tourelles d'angle rouges (4 tours)
for tx, ty in [(-10.5, 28.5), (10.5, 28.5), (-10.5, 43.5), (10.5, 43.5)]:
    bpy.ops.mesh.primitive_cylinder_add(radius=2.2, depth=10.0, vertices=12, location=(tx, ty, 5.0))
    turret = bpy.context.active_object
    turret.data.materials.append(mat_stucco_white)
    
    bpy.ops.mesh.primitive_cone_add(radius1=2.6, depth=4.5, vertices=12, location=(tx, ty, 11.5))
    turret_roof = bpy.context.active_object
    turret_roof.data.materials.append(mat_roof_guild)

# Bannière / Blason Fairy Tail au fronton
bpy.ops.mesh.primitive_cube_add(size=1.0, location=(0, 27.8, 7.2))
crest = bpy.context.active_object
crest.name = 'Fairy_Tail_Emblem_Banner'
crest.scale = Vector((5.5, 0.2, 3.2))
bpy.ops.object.transform_apply(scale=True)
crest.data.materials.append(mat_guild_crest)

# Terrasse extérieure de la taverne avec tonnelles et tables
bpy.ops.mesh.primitive_cube_add(size=1.0, location=(0, 25.0, 0.4))
deck = bpy.context.active_object
deck.name = 'Tavern_Terrace_Deck'
deck.scale = Vector((18.0, 6.0, 0.8))
bpy.ops.object.transform_apply(scale=True)
deck.data.materials.append(mat_wood_deck)

# Tables et bancs de taverne
for tbx in [-6, -2, 2, 6]:
    bpy.ops.mesh.primitive_cube_add(size=1.0, location=(tbx, 25.0, 1.1))
    tbl = bpy.context.active_object
    tbl.scale = Vector((1.8, 1.2, 0.6))
    bpy.ops.object.transform_apply(scale=True)
    tbl.data.materials.append(mat_timber)

# =========================================================
# 6. LA CATHÉDRALE DE KARDIA (BÂTIMENT MONUMENTAL)
# =========================================================
print("[4/5] Modélisation de la Cathédrale de Kardia...")

CATH_X, CATH_Y = -35.0, 30.0

# Corps principal de la nef cathédrale
bpy.ops.mesh.primitive_cube_add(size=1.0, location=(CATH_X, CATH_Y, 7.5))
cath_main = bpy.context.active_object
cath_main.name = 'Kardia_Cathedral'
cath_main.scale = Vector((18.0, 28.0, 15.0))
bpy.ops.object.transform_apply(scale=True)
cath_main.data.materials.append(mat_cathedral_marble)

# Toit pentu en cuivre/pierre de la nef
bpy.ops.mesh.primitive_cylinder_add(radius=10.0, depth=29.0, vertices=4, location=(CATH_X, CATH_Y, 18.0))
cath_roof = bpy.context.active_object
cath_roof.rotation_euler = Euler((math.radians(45), 0, 0), 'XYZ')
cath_roof.scale = Vector((0.75, 0.75, 1.0))
cath_roof.data.materials.append(mat_roof_blue)

# Deux Flèches Jumelles Gothiques (Façade Sud de la cathédrale)
for fx in [CATH_X - 7.5, CATH_X + 7.5]:
    bpy.ops.mesh.primitive_cube_add(size=1.0, location=(fx, CATH_Y - 12.5, 12.0))
    spire_base = bpy.context.active_object
    spire_base.scale = Vector((5.0, 5.0, 24.0))
    bpy.ops.object.transform_apply(scale=True)
    spire_base.data.materials.append(mat_cathedral_marble)
    
    # Flèche gothique pyramidale
    bpy.ops.mesh.primitive_cone_add(radius1=3.4, depth=14.0, vertices=8, location=(fx, CATH_Y - 12.5, 30.0))
    spire_top = bpy.context.active_object
    spire_top.data.materials.append(mat_gold)

# Rosace centrale lumineuse
bpy.ops.mesh.primitive_cylinder_add(radius=4.5, depth=0.4, vertices=24, location=(CATH_X, CATH_Y - 14.1, 14.0))
rose = bpy.context.active_object
rose.name = 'Cathedral_Rose_Window'
rose.rotation_euler = Euler((math.radians(90), 0, 0), 'XYZ')
rose.data.materials.append(mat_rose_window)

# Parvis pavé de la cathédrale
bpy.ops.mesh.primitive_cube_add(size=1.0, location=(CATH_X, CATH_Y - 20.0, 0.1))
cath_piazza = bpy.context.active_object
cath_piazza.scale = Vector((28.0, 16.0, 0.2))
bpy.ops.object.transform_apply(scale=True)
cath_piazza.data.materials.append(mat_piazza_paving)

# =========================================================
# 7. LES QUARTIERS DE LA VILLE : 120+ MAISONS MÉDIÉVALES
# =========================================================
print("[5/5] Génération des 120+ maisons médiévales et quartiers de Magnolia...")

# Grille de quartiers réalistes (Nord, Ouest, Est, Sud de la rivière)
house_locations = []

# Quartier Ouest (autour de la cathédrale)
for x in range(-55, -12, 9):
    for y in range(4, 48, 9):
        if (x - CATH_X)**2 + (y - CATH_Y)**2 > 120:  # Éviter la cathédrale
            house_locations.append((x + random.uniform(-1.5, 1.5), y + random.uniform(-1.5, 1.5)))

# Quartier Est (Résidentiel & Portuaire près du lac)
for x in range(14, 52, 9):
    for y in range(4, 50, 9):
        house_locations.append((x + random.uniform(-1.5, 1.5), y + random.uniform(-1.5, 1.5)))

# Quartier Sud (de l'autre côté du canal)
for x in range(-50, 50, 8):
    for y in range(-45, -16, 8):
        house_locations.append((x + random.uniform(-1.2, 1.2), y + random.uniform(-1.2, 1.2)))

# Quartier Central (autour de la grand-place)
for x in range(-20, 22, 10):
    for y in range(-6, 18, 8):
        if abs(x) > 6:  # Laisser libre le boulevard de Gildarts
            house_locations.append((x + random.uniform(-1.0, 1.0), y + random.uniform(-1.0, 1.0)))

# Construire chaque maison avec variété
for i, (hx, hy) in enumerate(house_locations):
    # Dimensions variées
    w = random.uniform(4.5, 6.5)
    d = random.uniform(4.5, 6.5)
    h = random.uniform(4.0, 7.5)
    
    # Corps de maison
    bpy.ops.mesh.primitive_cube_add(size=1.0, location=(hx, hy, h * 0.5))
    house = bpy.context.active_object
    house.scale = Vector((w, d, h))
    bpy.ops.object.transform_apply(scale=True)
    house.data.materials.append(mat_stucco_cream if i % 2 == 0 else mat_stucco_white)
    
    # Toit pointu (rouge ou bleu selon style Fairy Tail)
    roof_mat = mat_roof_red if random.random() > 0.4 else mat_roof_blue
    bpy.ops.mesh.primitive_cylinder_add(radius=max(w, d) * 0.6, depth=max(w, d) * 1.05, vertices=4, location=(hx, hy, h + 1.2))
    roof = bpy.context.active_object
    roof.rotation_euler = Euler((math.radians(45), 0, math.radians(90) if w > d else 0), 'XYZ')
    roof.scale = Vector((0.7, 0.7, 1.0))
    roof.data.materials.append(roof_mat)
    
    # Cheminée en pierre
    bpy.ops.mesh.primitive_cube_add(size=1.0, location=(hx + w * 0.3, hy + d * 0.3, h + 2.0))
    chimney = bpy.context.active_object
    chimney.scale = Vector((0.8, 0.8, 2.2))
    bpy.ops.object.transform_apply(scale=True)
    chimney.data.materials.append(mat_stone_wall)

# =========================================================
# 8. ARBRES DE MAGNOLIAS EN FLEURS ROSES (SYMBOLE DE LA VILLE)
# =========================================================
print("Plantation de 60 magnolias en fleurs roses et végétation...")

magnolia_locs = [
    # Le long du boulevard de Gildarts
    (-4.0, 2), (-4.0, 10), (-4.0, 18), (4.0, 2), (4.0, 10), (4.0, 18),
    # Autour de la place de la guilde
    (-14, 28), (14, 28), (-16, 20), (16, 20),
    # Berges du canal
    (-25, -3.5), (-15, -3.5), (15, -3.5), (25, -3.5), (35, -3.5),
    (-25, -12.5), (-15, -12.5), (15, -12.5), (25, -12.5),
    # Autour de la cathédrale
    (-48, 22), (-22, 22), (-48, 38), (-22, 38),
]

# Ajouter des arbres aléatoires supplémentaires dans les parcs
for _ in range(35):
    magnolia_locs.append((random.uniform(-55, 55), random.uniform(-40, 50)))

for tx, ty in magnolia_locs:
    # Tronc
    th = random.uniform(2.5, 4.0)
    bpy.ops.mesh.primitive_cylinder_add(radius=0.35, depth=th, vertices=8, location=(tx, ty, th * 0.5))
    trunk = bpy.context.active_object
    trunk.data.materials.append(mat_timber)
    
    # Couronne de fleurs de magnolia roses
    bpy.ops.mesh.primitive_ico_sphere_add(radius=random.uniform(2.0, 3.2), subdivisions=2, location=(tx, ty, th + 1.6))
    foliage = bpy.context.active_object
    foliage.data.materials.append(mat_magnolia_pink)

# =========================================================
# 9. GONDOLES / BATEAUX SUR LE CANAL ET LE LAC KARDIAC
# =========================================================
for bx, by, rot in [(-12, -8, 20), (8, -8, -15), (28, -8, 5), (60, -2, 45), (70, -18, -30)]:
    bpy.ops.mesh.primitive_cube_add(size=1.0, location=(bx, by, 0.3))
    boat = bpy.context.active_object
    boat.scale = Vector((4.2, 1.4, 0.6))
    boat.rotation_euler.z = math.radians(rot)
    bpy.ops.object.transform_apply(scale=True)
    boat.data.materials.append(mat_timber)

# =========================================================
# 10. REMPARTS D'ENCEINTE & PORTES DE LA VILLE
# =========================================================
# Mur d'enceinte Sud
bpy.ops.mesh.primitive_cube_add(size=1.0, location=(0, -50, 2.5))
wall_s = bpy.context.active_object
wall_s.scale = Vector((110.0, 2.0, 5.0))
bpy.ops.object.transform_apply(scale=True)
wall_s.data.materials.append(mat_stone_wall)

# Tours de garde rondes aux angles des remparts
for wx, wy in [(-55, -50), (55, -50), (-55, 50), (55, 50)]:
    bpy.ops.mesh.primitive_cylinder_add(radius=3.5, depth=8.0, vertices=16, location=(wx, wy, 4.0))
    guard_tower = bpy.context.active_object
    guard_tower.data.materials.append(mat_stone_wall)
    
    bpy.ops.mesh.primitive_cone_add(radius1=4.0, depth=4.0, vertices=16, location=(wx, wy, 10.0))
    gt_roof = bpy.context.active_object
    gt_roof.data.materials.append(mat_roof_blue)

# =========================================================
# 11. CAMÉRAS & RENDU DE TOUTES LES VUES CLÉS ("QUE L'ON PUISSE TOUT VOIR")
# =========================================================
print("Configuration des caméras et rendu des 5 vues complètes...")

cam_data = bpy.data.cameras.new('MagnoliaCamera')
cam_data.lens = 32
cam_data.sensor_width = 36
cam_obj = bpy.data.objects.new('MagnoliaCamera', cam_data)
scene.collection.objects.link(cam_obj)
scene.camera = cam_obj

# 5 Vues Clés pour TOUT voir de Magnolia :
stills_config = [
    # 1. Vue Aérienne Panoramique Globale (Ville Entière, Lac Kardiac, Guilde, Cathédrale)
    ('01_magnolia_vue_aerienne_panoramique_globale', Vector((0, -85, 62)), Vector((0, 8, 4))),
    # 2. Vue Plongeante sur le QG de Fairy Tail et le Boulevard Gildarts
    ('02_fairy_tail_qg_et_boulevard_gildarts', Vector((0, -12, 28)), Vector((0, 36, 10))),
    # 3. Vue Majestueuse sur la Cathédrale de Kardia & Parvis
    ('03_cathedrale_kardia_et_grand_parvis', Vector((-35, -5, 20)), Vector((-35, 30, 14))),
    # 4. Vue au Niveau des Rues, Canaux & Fleurs de Magnolia
    ('04_rues_medievales_canaux_et_fleurs_magnolia', Vector((8, -26, 6)), Vector((0, 8, 4))),
    # 5. Vue Crépusculaire sur le Lac Kardiac et le Port Est
    ('05_lac_kardiac_et_panorama_est', Vector((75, -60, 35)), Vector((20, 10, 8))),
]

for label, cam_pos, target_pos in stills_config:
    cam_obj.location = cam_pos
    dir_vec = target_pos - cam_pos
    cam_obj.rotation_euler = dir_vec.to_track_quat('-Z', 'Y').to_euler()
    
    scene.frame_set(1)
    out_path = os.path.join(STILLS_DIR, f'{label}.png')
    scene.render.filepath = out_path
    bpy.ops.render.render(write_still=True)
    print(f'Rendered still: {label}.png')

# Vue Clay White de la Ville Entière (Volumes purs)
print("Rendu Clay White architectural...")
clay_mat = bpy.data.materials.new(name='ClayWhiteCity')
clay_mat.use_nodes = True
c_bsdf = clay_mat.node_tree.nodes.get('Principled BSDF')
if c_bsdf:
    c_bsdf.inputs['Base Color'].default_value = (0.90, 0.90, 0.92, 1.0)
    c_bsdf.inputs['Roughness'].default_value = 0.40

# Remplacer temporairement tous les matériaux par clay
orig_materials = {}
for obj in bpy.data.objects:
    if obj.type == 'MESH' and obj.data.materials:
        orig_materials[obj.name] = list(obj.data.materials)
        obj.data.materials.clear()
        obj.data.materials.append(clay_mat)

cam_obj.location = Vector((0, -85, 62))
dir_vec = Vector((0, 8, 4)) - cam_obj.location
cam_obj.rotation_euler = dir_vec.to_track_quat('-Z', 'Y').to_euler()
scene.render.filepath = os.path.join(STILLS_DIR, '06_magnolia_clay_white_global.png')
bpy.ops.render.render(write_still=True)
print('Rendered still: 06_magnolia_clay_white_global.png')

# Restaurer les matériaux
for obj_name, mats in orig_materials.items():
    obj = bpy.data.objects.get(obj_name)
    if obj:
        obj.data.materials.clear()
        for m in mats:
            obj.data.materials.append(m)

# =========================================================
# 12. SURVOL CINÉMATIQUE 360° DE MAGNOLIA (72 Frames / 24 fps)
# =========================================================
print("Animation de la trajectoire hélicoptère / survol 360° de Magnolia...")
cam_obj.animation_data_create()
act = bpy.data.actions.new('Magnolia_Flythrough')
cam_obj.animation_data.action = act

RADIUS = 95.0
HEIGHT = 52.0
CENTER = Vector((0, 10, 5))

for f in range(1, 73):
    angle = (f - 1) / 71.0 * (2 * math.pi) - math.pi * 0.5
    cam_x = CENTER.x + RADIUS * math.cos(angle)
    cam_y = CENTER.y + RADIUS * math.sin(angle)
    cam_z = HEIGHT + 8.0 * math.sin(angle * 2)
    
    c_pos = Vector((cam_x, cam_y, cam_z))
    cam_obj.location = c_pos
    dir_vec = CENTER - c_pos
    cam_obj.rotation_euler = dir_vec.to_track_quat('-Z', 'Y').to_euler()
    
    cam_obj.keyframe_insert(data_path='location', frame=f)
    cam_obj.keyframe_insert(data_path='rotation_euler', frame=f)

# Export Scene GLB Complète
scene_glb_path = os.path.join(SCENE_DIR, 'magnolia_fairy_tail_city.glb')
bpy.ops.export_scene.gltf(
    filepath=scene_glb_path,
    export_format='GLB',
    export_animations=True,
    export_current_frame=False,
    export_materials='EXPORT',
)
print('Exported full Magnolia GLB to:', scene_glb_path)

# Rendu de l'animation
scene.render.filepath = os.path.join(FRAMES_DIR, 'frame_')
scene.render.image_settings.file_format = 'PNG'
print('Rendering 72 flythrough animation frames...')
bpy.ops.render.render(animation=True)
print('MAGNOLIA_CITY_PRODUCTION_COMPLETE')
