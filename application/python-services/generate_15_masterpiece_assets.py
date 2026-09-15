#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""generate_15_masterpiece_assets.py — Génération haute qualité des 15 chefs-d'œuvre
(Monuments, Personnages, Véhicules, Environnements, Objets Magiques complexes).
"""
import os
import torch
from pathlib import Path
from diffusers import StableDiffusionXLPipeline

OUT_DIR = Path('/home/juan/AuroraIA/application/output/3d/magnolia_fairy_tail_city/15_masterpieces')
OUT_DIR.mkdir(parents=True, exist_ok=True)

device = 'cuda' if torch.cuda.is_available() else 'cpu'
print(f"Loading SDXL on {device}...")

pipe = StableDiffusionXLPipeline.from_pretrained(
    'stabilityai/stable-diffusion-xl-base-1.0',
    torch_dtype=torch.float16,
    variant='fp16',
    use_safetensors=True
).to(device)

negative_prompt = "blurry, low quality, deformed, malformed, extra limbs, bad anatomy, simple shapes, cartoonish low poly, flat textures, watermark, signature"

ASSETS = [
    (
        "01_fairy_tail_guild_hall",
        "masterpiece, 8k, architectural master shot of the iconic Fairy Tail Guild Hall in Magnolia town, fantasy tavern castle with red lacquered arched tiered roofs, octagonal bell tower with glowing gold spire, red guild crest banner, timber framed half-timbering with carved brackets, warm outdoor tavern patio with oak kegs and benches, paved stone plaza, bright sunny day, octane render 8k",
        101, 1024, 768
    ),
    (
        "02_kardia_cathedral",
        "masterpiece, 8k, monumental Gothic Kardia Cathedral in Magnolia town from Fairy Tail, colossal white limestone twin belfry spires reaching into the sky, intricate stone lace tracery, massive illuminated blue and violet rose stained glass window, green copper verdigris nave roof, flying buttresses, grand ceremonial marble stairs, high fantasy architectural octane render",
        102, 1024, 768
    ),
    (
        "03_mercurius_palace_crocus",
        "masterpiece, 8k, colossal Mercurius Royal Palace in Crocus Fiore, grand white marble and gold fantasy castle, gigantic golden domes, celestial astrological towers, massive Eclipse Gate pedestal with glowing celestial runes, monumental water fountains and tiered royal gardens, majestic daytime lighting, cinematic octane render",
        103, 1024, 768
    ),
    (
        "04_floating_city_extalia",
        "masterpiece, 8k, magnificent floating island city of Extalia in Edolas sky, soaring gravity-defying white islands with cascading reverse waterfalls flowing into the clouds, luminous crystal arch bridges connecting palace citadels, angelic white spires, glowing blue magical lacrima crystals, ethereal volumetric clouds, anime high fantasy masterpiece",
        104, 1024, 768
    ),
    (
        "05_cliffside_himalayan_monastery",
        "masterpiece, 8k, majestic ancient Tibetan Himalayan monastery perched precariously on a vertical snowy mountain precipice, multi-tiered red and golden pagoda roofs, stone stairways carved into the rock face, colorful wind-blown prayer flags, dramatic sunset golden hour lighting, hyper-detailed photorealistic architectural photography",
        105, 1024, 768
    ),
    (
        "06_natsu_dragon_force",
        "masterpiece, 8k, dynamic full body heroic character concept of Natsu Dragneel in Dragon Force, athletic muscled warrior with crimson and gold dragon scales on cheek and arms, spiky salmon pink hair, white dragon scale scarf, blazing swirling dragon fire surrounding his fists, glowing golden eyes, dynamic combat stance, high quality anime figure octane render",
        106, 768, 1024
    ),
    (
        "07_erza_flame_empress_armor",
        "masterpiece, 8k, majestic full body heroic character concept of Erza Scarlet in Flame Empress Armor, scarlet red and gold ornate knight armor with dragon wing pauldrons, flowing long scarlet crimson hair, wielding a massive blazing broadsword with ruby core, fiery aura, confident royal warrior stance, hyper-detailed anime figure 8k",
        107, 768, 1024
    ),
    (
        "08_acnologia_dragon_apocalypse",
        "masterpiece, 8k, colossal dragon of the apocalypse Acnologia, massive terrifying black obsidian dragon with glowing neon cyan tribal markings across body and wings, four large serrated horns, immense razor wingspan, roaring with blue vortex energy beam from maw, hovering above dark stormy clouds, cinematic epic monster octane render",
        108, 1024, 768
    ),
    (
        "09_chimera_beast_guardian",
        "masterpiece, 8k, noble chimera beast warrior in full body A-pose, athletic feline and wolf anatomy, thick charcoal and silver fur coat, glowing amber eyes, wearing ornate bronze and leather battle harness with shoulder armor, razor sharp talons, muscular coiled tail, hyper-detailed anatomical creature sculpt, octane render",
        109, 768, 1024
    ),
    (
        "10_christina_flying_ship",
        "masterpiece, 8k, the magical flying airship Christina of Blue Pegasus, colossal aerodynamic silver and gold sky vessel shaped like a soaring winged pegasus with spread golden feather wings, glowing blue lacrima crystal propulsion engines, glass canopy bridge, flying through sunlit fluffy clouds, high fantasy airship masterpiece",
        110, 1024, 768
    ),
    (
        "11_magnolia_magical_steam_train",
        "masterpiece, 8k, heavy fantasy steampunk magical locomotive train, dark cast iron and polished brass boiler, glowing turquoise lacrima reactor core visible through glass hatches, complex interlocking valve gears and pistons, glowing furnace firebox, emitting white steam clouds on ornate iron tracks, high detailed engineering render",
        111, 1024, 768
    ),
    (
        "12_domus_flau_grand_magic_games_arena",
        "masterpiece, 8k, the colossal Domus Flau colosseum stadium of the Grand Magic Games in Crocus, immense circular open-air stone arena with towering stone warrior statues holding eternal torches, tiered spectator balconies under colorful guild banners, glowing central combat battlefield with arcane magic circles, epic cinematic crowd atmosphere",
        112, 1024, 768
    ),
    (
        "13_phantom_lord_walking_fortress",
        "masterpiece, 8k, menacing dark gothic walking fortress of Phantom Lord guild, massive black iron castle perched atop four colossal mechanical hydraulic spider-like legs, gigantic Jupiter magic cannon emerging from the main tower, dark storm clouds and purple lightning strikes, monumental scale, cinematic dark fantasy",
        113, 1024, 768
    ),
    (
        "14_celestial_time_astrolabe",
        "masterpiece, 8k, highly complex celestial astrological clockwork sphere, multiple concentric floating orichalcum rings engraved with golden zodiac symbols, central glowing quartz chronos crystal, interlocking micro-gears, floating celestial star map holograms, isolated on dark velvet studio backdrop, hyper-detailed hard surface render",
        114, 1024, 1024
    ),
    (
        "15_black_dragon_bone_throne",
        "masterpiece, 8k, monumental throne of the Dragon King, colossal throne constructed from interlocking black dragon skull horns, polished volcanic obsidian seat with crimson velvet cushion, glowing embers and blue necrotic flame torches flanking the stone dais, dark fantasy king throne room, photorealistic 8k octane render",
        115, 1024, 1024
    )
]

for name, prompt, seed, w, h in ASSETS:
    target_file = OUT_DIR / f"{name}.png"
    if target_file.is_file():
        print(f"[SKIP] Already exists: {target_file.name}")
        continue
    print(f"[GEN] Generating {name} (seed={seed}, {w}x{h})...")
    gen = torch.Generator(device=device).manual_seed(seed)
    img = pipe(
        prompt=prompt,
        negative_prompt=negative_prompt,
        num_inference_steps=24,
        guidance_scale=7.5,
        generator=gen,
        width=w,
        height=h
    ).images[0]
    img.save(target_file)
    print(f"[OK] Saved {target_file.name}")

print("ALL 15 MASTERPIECE ASSETS GENERATED SUCCESSFULLY!")
