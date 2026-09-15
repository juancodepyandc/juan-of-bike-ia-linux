#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""run_true_360_masterpiece_pipeline.py — Pipeline Officiel de Production 3D Réelle 360° :
ZÉRO DÉTOURAGE DESTRUCTIF + VÉRITABLE GÉOMÉTRIE 360° ENTIÈREMENT CONSTRUITE (Face + Profil + Dos).
Chaque projet sous output/3d/<nom_du_projet>/ contient :
  - <nom_du_projet>_360.glb (modèle 3D volumique 360° complet)
  - render_front.png (rendu cinématique face 3/4)
  - render_back.png (rendu cinématique dos 3/4)
  - references/
    - view_front.png
    - view_side.png
    - view_back.png
"""
import os
import sys
import torch
import subprocess
from pathlib import Path
from diffusers import StableDiffusionXLPipeline

OUTPUT_3D_ROOT = Path('/home/juan/AuroraIA/application/output/3d')
PYTHON_ENV = Path('/home/juan/AuroraIA/application/.venv/bin/python')
TRELLIS_SCRIPT = Path('/home/juan/AuroraIA/application/python-services/aurora_hunyuan/aurora_trellis_wrapper.py')
BLENDER_BIN = Path('/home/juan/.local/bin/blender')

device = 'cuda' if torch.cuda.is_available() else 'cpu'

# 15 Projets Officiels avec prompts spécialisés (Front, Side, Back)
PROJECT_SPECS = [
    (
        "01_fairy_tail_guild_hall",
        "masterpiece, 8k, architectural front view of the iconic Fairy Tail Guild Hall in Magnolia town, fantasy tavern castle with red lacquered arched tiered roofs, octagonal bell tower with glowing gold spire, red guild crest banner, timber framed half-timbering with carved brackets, outdoor tavern patio, solid neutral studio background, centered, full building visible",
        "masterpiece, 8k, architectural side profile 3/4 view of the iconic Fairy Tail Guild Hall in Magnolia town, side facade with timber framed balconies, tiered red roof overhang, side turrets, tavern patio extension, solid neutral studio background, centered, full building visible",
        "masterpiece, 8k, architectural back rear view of the iconic Fairy Tail Guild Hall in Magnolia town, rear facade with stone masonry foundation, arched timber framed back windows, rear conical red roof spires, octagonal bell tower from behind, stone chimneys, solid neutral studio background, centered, full building visible",
        301
    ),
    (
        "02_kardia_cathedral",
        "masterpiece, 8k, monumental Gothic Kardia Cathedral front facade in Magnolia, colossal white limestone twin belfry spires reaching into sky, massive blue and violet rose stained glass window, ceremonial marble stairs, solid neutral studio background, centered, full cathedral",
        "masterpiece, 8k, monumental Gothic Kardia Cathedral side flank profile, massive green copper verdigris nave roof, flying buttresses, tall arched mullioned stained glass windows, solid neutral studio background, centered, full cathedral",
        "masterpiece, 8k, monumental Gothic Kardia Cathedral rear apse view, semicircular stone apse with radial flying buttresses, rear gargoyles, crossing fleche spire, solid neutral studio background, centered, full cathedral",
        302
    ),
    (
        "03_mercurius_palace_crocus",
        "masterpiece, 8k, colossal Mercurius Royal Palace front entrance in Crocus Fiore, white marble and gold castle, gigantic golden domes, celestial astrological towers, Eclipse Gate pedestal with glowing runes, solid neutral studio background, centered",
        "masterpiece, 8k, colossal Mercurius Royal Palace side profile, tiered palace wings, golden dome rotundas, arched colonnades, royal terrace, solid neutral studio background, centered",
        "masterpiece, 8k, colossal Mercurius Royal Palace rear facade, royal gardens gate, towering celestial spires, rear marble courtyards, solid neutral studio background, centered",
        303
    ),
    (
        "04_floating_city_extalia",
        "masterpiece, 8k, magnificent floating island city of Extalia in Edolas sky, soaring gravity-defying white islands with cascading reverse waterfalls flowing into clouds, luminous crystal arch bridges, angelic white spires, glowing blue lacrima crystals, solid neutral studio background",
        "masterpiece, 8k, floating island city of Extalia side view, floating crystal platforms, airborne aqueducts, side towers, solid neutral studio background",
        "masterpiece, 8k, floating island city of Extalia rear perspective, underside exposed floating earth roots, glowing celestial energy core, rear spires, solid neutral studio background",
        304
    ),
    (
        "05_cliffside_himalayan_monastery",
        "masterpiece, 8k, majestic ancient Tibetan Himalayan monastery front view, multi-tiered red and golden pagoda roofs, stone stairways carved in rock, colorful prayer flags, solid neutral studio background",
        "masterpiece, 8k, ancient Tibetan Himalayan monastery side profile, tiered vertical cantilevered balconies over cliff face, solid neutral studio background",
        "masterpiece, 8k, ancient Tibetan Himalayan monastery rear perspective, mountain rock anchorage, rear temple sanctum, solid neutral studio background",
        305
    ),
    (
        "06_natsu_dragon_force",
        "masterpiece, 8k, dynamic full body front view of Natsu Dragneel in Dragon Force, athletic muscled warrior with crimson and gold dragon scales on cheek and arms, spiky salmon pink hair, white dragon scale scarf, swirling dragon fire on fists, solid neutral studio background, full figure A-pose",
        "masterpiece, 8k, dynamic full body side profile of Natsu Dragneel in Dragon Force, muscular arms, dragon scale pauldrons, flame aura, solid neutral studio background, full figure",
        "masterpiece, 8k, dynamic full body back rear view of Natsu Dragneel in Dragon Force, muscular back, flowing scarf ends, fiery aura around shoulder blades, solid neutral studio background, full figure",
        306
    ),
    (
        "07_erza_flame_empress_armor",
        "masterpiece, 8k, majestic full body front view of Erza Scarlet in Flame Empress Armor, scarlet red and gold ornate knight armor with dragon wing pauldrons, long scarlet hair, wielding blazing broadsword with ruby core, solid neutral studio background, full figure",
        "masterpiece, 8k, majestic full body side profile of Erza Scarlet in Flame Empress Armor, dragon wing pauldrons, flowing hair, broadsword profile, solid neutral studio background, full figure",
        "masterpiece, 8k, majestic full body back rear view of Erza Scarlet in Flame Empress Armor, articulated spine armor plates, long flowing scarlet hair, solid neutral studio background, full figure",
        307
    ),
    (
        "08_acnologia_dragon_apocalypse",
        "masterpiece, 8k, colossal dragon Acnologia front view, massive black obsidian dragon with glowing neon cyan tribal markings, four serrated horns, razor wingspan, roaring with blue vortex maw, solid neutral studio background, full body",
        "masterpiece, 8k, colossal dragon Acnologia side profile, immense wingspan profile, muscular legs, spiked tail, cyan glowing markings, solid neutral studio background, full body",
        "masterpiece, 8k, colossal dragon Acnologia back rear view, massive obsidian back dorsal spines, huge wings outstretched from behind, long tail, solid neutral studio background, full body",
        308
    ),
    (
        "09_chimera_beast_guardian",
        "masterpiece, 8k, noble chimera beast warrior front view, athletic feline and wolf anatomy, charcoal and silver fur coat, glowing amber eyes, ornate bronze and leather battle harness, solid neutral studio background, full body A-pose",
        "masterpiece, 8k, noble chimera beast warrior side profile, muscular feline legs, arched spine, bronze shoulder armor, long coiled tail, solid neutral studio background, full body",
        "masterpiece, 8k, noble chimera beast warrior back rear view, muscular back, thick fur mane from behind, rear harness straps, tail base, solid neutral studio background, full body",
        309
    ),
    (
        "10_christina_flying_ship",
        "masterpiece, 8k, the magical flying airship Christina front view, aerodynamic silver and gold sky vessel shaped like soaring winged pegasus, golden feather wings, glowing blue lacrima engines, solid neutral studio background",
        "masterpiece, 8k, magical flying airship Christina side profile, elongated fuselage, golden wing side span, glass canopy bridge, solid neutral studio background",
        "masterpiece, 8k, magical flying airship Christina rear view, glowing blue lacrima propulsion thrusters, golden pegasus tail rudder, solid neutral studio background",
        310
    ),
    (
        "11_magnolia_magical_steam_train",
        "masterpiece, 8k, heavy fantasy steampunk magical locomotive train front view, dark cast iron and brass boiler, glowing turquoise lacrima reactor core, cowcatcher grill, solid neutral studio background",
        "masterpiece, 8k, magical locomotive train side profile, long boiler, interlocking drive wheels, pistons and valve gears, cabin, solid neutral studio background",
        "masterpiece, 8k, magical locomotive train rear view, engineer cabin rear, coal and lacrima tender car, solid neutral studio background",
        311
    ),
    (
        "12_domus_flau_grand_magic_games_arena",
        "masterpiece, 8k, Domus Flau colosseum stadium front entrance, colossal circular stone arena, towering stone warrior statues with torches, tiered balconies, solid neutral studio background",
        "masterpiece, 8k, Domus Flau colosseum side profile, curved exterior arched arcade walls, massive statues, solid neutral studio background",
        "masterpiece, 8k, Domus Flau colosseum rear perspective, royal pavilion box, rear arches and banners, solid neutral studio background",
        312
    ),
    (
        "13_phantom_lord_walking_fortress",
        "masterpiece, 8k, dark gothic walking fortress of Phantom Lord front view, black iron castle atop colossal hydraulic spider legs, Jupiter magic cannon, solid neutral studio background",
        "masterpiece, 8k, dark gothic walking fortress side profile, four massive articulated steel legs, castle towers, cannon barrel, solid neutral studio background",
        "masterpiece, 8k, dark gothic walking fortress rear view, mechanical rear leg joints, rear castle bastions, solid neutral studio background",
        313
    ),
    (
        "14_celestial_time_astrolabe",
        "masterpiece, 8k, celestial astrological clockwork sphere front view, concentric floating orichalcum rings with golden zodiac symbols, central glowing quartz chronos crystal, solid neutral studio background",
        "masterpiece, 8k, celestial astrological clockwork sphere side profile, interlocking micro-gears, ring pivot bearings, solid neutral studio background",
        "masterpiece, 8k, celestial astrological clockwork sphere rear view, astrological calendar dials, rear crystal mounts, solid neutral studio background",
        314
    ),
    (
        "15_black_dragon_bone_throne",
        "masterpiece, 8k, monumental throne of the Dragon King front view, constructed from interlocking black dragon skull horns, obsidian seat with crimson velvet cushion, glowing embers, solid neutral studio background",
        "masterpiece, 8k, throne of the Dragon King side profile, curved dragon horn armrests, obsidian dais steps, solid neutral studio background",
        "masterpiece, 8k, throne of the Dragon King rear view, massive interlocking dragon spine backrest, rear horn crown, solid neutral studio background",
        315
    ),
]

# Script Blender pour rendu Double Angle (Face + Dos)
BLENDER_SCRIPT = Path('/home/juan/AuroraIA/application/python-services/render_double_turntable.py')
with open(BLENDER_SCRIPT, "w") as f:
    f.write("""
import bpy, sys
from mathutils import Vector

argv = sys.argv[sys.argv.index("--") + 1:]
glb_in, png_front, png_back = argv[0], argv[1], argv[2]

bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
scene.render.engine = 'CYCLES'
scene.cycles.device = 'CPU'
scene.cycles.samples = 28
scene.cycles.use_denoising = True
scene.render.resolution_x = 1024
scene.render.resolution_y = 768

w = bpy.data.worlds.new('Studio')
scene.world = w
w.use_nodes = True
w.node_tree.nodes.get('Background').inputs['Color'].default_value = (0.06, 0.07, 0.09, 1.0)

sun = bpy.data.objects.new('Sun', bpy.data.lights.new('Sun', type='SUN'))
sun.data.energy = 4.0
sun.rotation_euler = (0.85, 0.3, -0.6)
scene.collection.objects.link(sun)

fill = bpy.data.objects.new('Fill', bpy.data.lights.new('Fill', type='SUN'))
fill.data.energy = 2.0
fill.rotation_euler = (0.85, 0.3, 2.5)
scene.collection.objects.link(fill)

bpy.ops.import_scene.gltf(filepath=glb_in)

cam_obj = bpy.data.objects.new('Camera', bpy.data.cameras.new('Camera'))
cam_obj.data.lens = 42
scene.collection.objects.link(cam_obj)
scene.camera = cam_obj

# Rendu 1 : Face 3/4
cam_p1 = Vector((1.5, -2.8, 1.4))
cam_obj.location = cam_p1
cam_obj.rotation_euler = (Vector((0,0,0.4)) - cam_p1).to_track_quat('-Z', 'Y').to_euler()
scene.render.filepath = png_front
bpy.ops.render.render(write_still=True)

# Rendu 2 : Dos 3/4
cam_p2 = Vector((-1.5, 2.8, 1.4))
cam_obj.location = cam_p2
cam_obj.rotation_euler = (Vector((0,0,0.4)) - cam_p2).to_track_quat('-Z', 'Y').to_euler()
scene.render.filepath = png_back
bpy.ops.render.render(write_still=True)
""")

print("==========================================================")
print("  EXÉCUTION DU PIPELINE 3D MULTI-VUES 360° SUR LES 15 PROJETS")
print("==========================================================")

# Étape 1 : Génération de toutes les références 360° avec SDXL
print("\n[PHASE 1/2] Synthèse des références 360° cohérentes (Face, Profil, Dos)...")
pipe = StableDiffusionXLPipeline.from_pretrained(
    'stabilityai/stable-diffusion-xl-base-1.0',
    torch_dtype=torch.float16,
    variant='fp16',
    use_safetensors=True
).to(device)

negative = "blurry, low quality, deformed, cropped, modern buildings, multiple objects, dark background"

for idx, (p_name, p_front, p_side, p_back, base_seed) in enumerate(PROJECT_SPECS, 1):
    p_dir = OUTPUT_3D_ROOT / p_name
    ref_dir = p_dir / "references"
    ref_dir.mkdir(parents=True, exist_ok=True)
    
    vf = ref_dir / "view_front.png"
    vs = ref_dir / "view_side.png"
    vb = ref_dir / "view_back.png"
    
    if not vf.is_file():
        print(f"[{idx}/15] {p_name} -> view_front.png")
        img = pipe(prompt=p_front, negative_prompt=negative, num_inference_steps=24, guidance_scale=7.5, generator=torch.Generator(device=device).manual_seed(base_seed), width=1024, height=1024).images[0]
        img.save(vf)
    if not vs.is_file():
        print(f"[{idx}/15] {p_name} -> view_side.png")
        img = pipe(prompt=p_side, negative_prompt=negative, num_inference_steps=24, guidance_scale=7.5, generator=torch.Generator(device=device).manual_seed(base_seed + 1), width=1024, height=1024).images[0]
        img.save(vs)
    if not vb.is_file():
        print(f"[{idx}/15] {p_name} -> view_back.png")
        img = pipe(prompt=p_back, negative_prompt=negative, num_inference_steps=24, guidance_scale=7.5, generator=torch.Generator(device=device).manual_seed(base_seed + 2), width=1024, height=1024).images[0]
        img.save(vb)

del pipe
torch.cuda.empty_cache()
print("\nToutes les références 360° sont prêtes dans chaque projet !")

# Étape 2 : Reconstruction 3D volumique Multi-Vues 360° avec TRELLIS.2
print("\n[PHASE 2/2] Reconstruction 3D Volumique 360° (TRELLIS.2 Multi-Vues)...")

for idx, (p_name, _, _, _, base_seed) in enumerate(PROJECT_SPECS, 1):
    p_dir = OUTPUT_3D_ROOT / p_name
    ref_dir = p_dir / "references"
    
    vf = ref_dir / "view_front.png"
    vs = ref_dir / "view_side.png"
    vb = ref_dir / "view_back.png"
    out_glb = p_dir / f"{p_name}_360.glb"
    png_front = p_dir / "render_front.png"
    png_back = p_dir / "render_back.png"
    
    print(f"\n=======================================================")
    print(f"[{idx}/15] Reconstruction 3D : {p_name}")
    print(f"=======================================================")
    
    if not out_glb.is_file() or out_glb.stat().st_size < 10000:
        cmd_trellis = [
            str(PYTHON_ENV),
            str(TRELLIS_SCRIPT),
            str(vf),
            str(out_glb),
            str(vs),
            str(vb),
            "--seed", str(base_seed)
        ]
        p = subprocess.run(cmd_trellis, capture_output=True, text=True)
        for line in p.stdout.splitlines():
            if "AURORA_TRELLIS_RESULT" in line:
                print(f"  {line}")
    else:
        print(f"  [OK] Fichier 3D GLB 360° déjà généré ({out_glb.stat().st_size // 1024 // 1024} Mo)")

    # Rendu Double Angle
    if out_glb.is_file() and (not png_front.is_file() or not png_back.is_file()):
        cmd_render = [
            str(BLENDER_BIN),
            "--background",
            "--python", str(BLENDER_SCRIPT),
            "--", str(out_glb), str(png_front), str(png_back)
        ]
        subprocess.run(cmd_render, capture_output=True, text=True)
        print(f"  [OK] Rendus Face et Dos sauvegardés dans {p_dir.name}")

print("\n==========================================================")
print("  PRODUCTION 3D RÉELLE 360° TERMINÉE SUR LES 15 PROJETS !")
print("==========================================================")
