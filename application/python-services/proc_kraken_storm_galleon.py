"""
proc_kraken_storm_galleon.py — 199e procédural AuroraIA (63e qualité)
Combat kraken géant + galion tempête : 8 tentacules + tête + galion endommagé + foudre + vagues + pluie + 2 sirènes
"""
import bpy, bmesh, math, random, os

random.seed(0x6A4194199)

def reset():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    for c in (bpy.data.meshes, bpy.data.materials, bpy.data.objects,
              bpy.data.cameras, bpy.data.lights, bpy.data.collections):
        for x in list(c):
            try: c.remove(x)
            except: pass

def mat(name, base=(0.8,0.8,0.8,1.0), metallic=0.0, roughness=0.5,
        emission=None, emission_strength=0.0, alpha=1.0):
    m = bpy.data.materials.new(name); m.use_nodes = True
    bsdf = m.node_tree.nodes.get("Principled BSDF")
    if bsdf is None:
        m.node_tree.nodes.clear()
        bsdf = m.node_tree.nodes.new("ShaderNodeBsdfPrincipled")
        out = m.node_tree.nodes.new("ShaderNodeOutputMaterial")
        m.node_tree.links.new(bsdf.outputs[0], out.inputs[0])
    bsdf.inputs["Base Color"].default_value = base
    bsdf.inputs["Metallic"].default_value = metallic
    bsdf.inputs["Roughness"].default_value = roughness
    if emission is not None:
        if "Emission Color" in bsdf.inputs:
            bsdf.inputs["Emission Color"].default_value = (*emission, 1.0)
        elif "Emission" in bsdf.inputs:
            bsdf.inputs["Emission"].default_value = (*emission, 1.0)
        if "Emission Strength" in bsdf.inputs:
            bsdf.inputs["Emission Strength"].default_value = emission_strength
    if alpha < 1.0:
        bsdf.inputs["Alpha"].default_value = alpha
        m.blend_method = 'BLEND'
    return m

def smooth_shade(mesh):
    for poly in mesh.polygons:
        poly.use_smooth = True
    try:
        mesh.use_auto_smooth = True
        mesh.auto_smooth_angle = math.radians(40)
    except AttributeError:
        pass

def make_obj(name, bm, loc=(0,0,0), parent=None, mat_=None):
    me = bpy.data.meshes.new(name); bm.to_mesh(me); bm.free(); smooth_shade(me)
    obj = bpy.data.objects.new(name, me)
    bpy.context.collection.objects.link(obj)
    obj.location = loc
    if parent: obj.parent = parent
    if mat_: obj.data.materials.append(mat_)
    return obj

def beveled_cube(name, size_xyz, bevel_offset=0.04, bevel_segments=3, loc=(0,0,0), parent=None, mat_=None):
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    bmesh.ops.scale(bm, vec=size_xyz, verts=bm.verts)
    bmesh.ops.bevel(bm, geom=bm.edges[:] + bm.verts[:],
                    offset=bevel_offset, segments=bevel_segments,
                    profile=0.5, affect='EDGES')
    return make_obj(name, bm, loc, parent, mat_)

def smooth_sphere(name, r=1.0, segs=24, rings=16, loc=(0,0,0), parent=None, mat_=None, scale=(1,1,1)):
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=segs, v_segments=rings, radius=r)
    if scale != (1,1,1):
        bmesh.ops.scale(bm, vec=scale, verts=bm.verts)
    return make_obj(name, bm, loc, parent, mat_)

def smooth_cone(name, r1, r2, depth, segs=18, loc=(0,0,0), parent=None, mat_=None):
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, segments=segs, radius1=r1, radius2=r2, depth=depth, cap_ends=True)
    return make_obj(name, bm, loc, parent, mat_)

def cyl(name, r, depth, segs=16, loc=(0,0,0), parent=None, mat_=None):
    return smooth_cone(name, r, r, depth, segs, loc, parent, mat_)

def empty(name, loc=(0,0,0), parent=None):
    e = bpy.data.objects.new(name, None)
    bpy.context.collection.objects.link(e)
    e.location = loc
    if parent: e.parent = parent
    return e

reset()
scene = bpy.context.scene
scene.frame_start = 1; scene.frame_end = 180; scene.render.fps = 30

# Materials
M_SKY_STORM = mat("sky_storm", (0.10, 0.10, 0.18, 1.0), 0.0, 0.7, emission=(0.15,0.12,0.22), emission_strength=1.0)
M_STORM_CLOUD = mat("storm_cloud", (0.15, 0.13, 0.20, 1.0), 0.0, 0.85, emission=(0.18,0.15,0.22), emission_strength=0.6, alpha=0.85)
M_LIGHTNING = mat("lightning", (1.0, 0.95, 1.0, 1.0), 0.0, 0.05, emission=(1.0,0.95,1.0), emission_strength=30.0)
M_RAIN = mat("rain", (0.65, 0.78, 0.92, 1.0), 0.0, 0.10, emission=(0.70,0.82,0.95), emission_strength=2.0, alpha=0.6)
M_SPRAY = mat("spray", (0.92, 0.95, 1.0, 1.0), 0.0, 0.25, emission=(0.88,0.92,1.0), emission_strength=3.0, alpha=0.7)
M_FOAM = mat("foam", (1.0, 1.0, 1.0, 1.0), 0.0, 0.40, emission=(0.95,0.98,1.0), emission_strength=2.0)
M_WATER_DARK = mat("water_dark", (0.05, 0.12, 0.22, 1.0), 0.5, 0.20, emission=(0.08,0.18,0.30), emission_strength=0.8)
M_WATER_CREST = mat("water_crest", (0.30, 0.50, 0.65, 1.0), 0.3, 0.30, emission=(0.35,0.55,0.70), emission_strength=1.2)
M_MOON_GLOW = mat("moon", (0.85, 0.88, 0.95, 1.0), 0.0, 0.20, emission=(0.85,0.88,0.95), emission_strength=14.0)

# Kraken
M_KRAKEN_BODY = mat("kraken_body", (0.45, 0.12, 0.20, 1.0), 0.0, 0.55, emission=(0.40,0.10,0.18), emission_strength=0.6)
M_KRAKEN_DARK = mat("kraken_dark", (0.25, 0.08, 0.15, 1.0), 0.0, 0.60, emission=(0.22,0.06,0.12), emission_strength=0.5)
M_KRAKEN_BELLY = mat("kraken_belly", (0.85, 0.40, 0.50, 1.0), 0.0, 0.50, emission=(0.75,0.35,0.45), emission_strength=0.7)
M_KRAKEN_EYE = mat("kraken_eye", (1.0, 0.85, 0.20, 1.0), 0.0, 0.15, emission=(1.0,0.90,0.25), emission_strength=15.0)
M_KRAKEN_PUPIL = mat("kraken_pup", (0.05, 0.05, 0.08, 1.0), 0.0, 0.30, emission=(0.05,0.05,0.05), emission_strength=0.3)
M_SUCKER = mat("sucker", (0.95, 0.75, 0.65, 1.0), 0.0, 0.50, emission=(0.90,0.70,0.60), emission_strength=0.5)
M_BEAK = mat("beak", (0.15, 0.10, 0.08, 1.0), 0.4, 0.45)

# Galleon
M_WOOD_DARK = mat("wood_dark", (0.20, 0.12, 0.08, 1.0), 0.0, 0.78)
M_WOOD = mat("wood", (0.35, 0.20, 0.12, 1.0), 0.0, 0.70)
M_WOOD_DAMAGED = mat("wood_damaged", (0.45, 0.30, 0.18, 1.0), 0.0, 0.85, emission=(0.35,0.20,0.12), emission_strength=0.4)
M_SAIL = mat("sail", (0.85, 0.80, 0.70, 1.0), 0.0, 0.65, emission=(0.75,0.72,0.62), emission_strength=0.3)
M_SAIL_TORN = mat("sail_torn", (0.55, 0.50, 0.42, 1.0), 0.0, 0.75, emission=(0.45,0.42,0.35), emission_strength=0.25)
M_ROPE = mat("rope", (0.60, 0.45, 0.30, 1.0), 0.0, 0.80)
M_METAL = mat("metal", (0.30, 0.30, 0.32, 1.0), 0.85, 0.40, emission=(0.25,0.25,0.28), emission_strength=0.3)
M_CANNON = mat("cannon", (0.10, 0.10, 0.12, 1.0), 0.88, 0.40)
M_CANNON_FLASH = mat("cannon_flash", (1.0, 0.85, 0.40, 1.0), 0.0, 0.10, emission=(1.0,0.90,0.50), emission_strength=25.0)
M_GOLD = mat("gold", (1.0, 0.78, 0.25, 1.0), 0.95, 0.18, emission=(0.95,0.72,0.22), emission_strength=0.8)
M_JOLLY = mat("jolly", (0.05, 0.05, 0.05, 1.0), 0.0, 0.7)
M_JOLLY_WHITE = mat("jolly_white", (0.95, 0.95, 0.92, 1.0), 0.0, 0.6, emission=(0.85,0.85,0.82), emission_strength=0.4)
M_LANTERN_SHIP = mat("lantern_ship", (1.0, 0.65, 0.25, 1.0), 0.0, 0.20, emission=(1.0,0.70,0.30), emission_strength=12.0)

# Pirates
M_SKIN = mat("skin", (0.85, 0.70, 0.55, 1.0), 0.0, 0.55, emission=(0.75,0.62,0.48), emission_strength=0.25)
M_SKIN_DARK = mat("skin_dark", (0.55, 0.42, 0.30, 1.0), 0.0, 0.60, emission=(0.45,0.35,0.25), emission_strength=0.25)
M_COAT_CAPTAIN = mat("coat_cap", (0.45, 0.10, 0.10, 1.0), 0.0, 0.55, emission=(0.40,0.08,0.08), emission_strength=0.4)
M_COAT_PIRATE = mat("coat_p", (0.25, 0.18, 0.12, 1.0), 0.0, 0.65, emission=(0.20,0.15,0.10), emission_strength=0.3)
M_SHIRT_STRIPE = mat("shirt_s", (0.85, 0.30, 0.30, 1.0), 0.0, 0.65, emission=(0.75,0.25,0.25), emission_strength=0.3)
M_PANTS = mat("pants", (0.20, 0.18, 0.15, 1.0), 0.0, 0.75)
M_HAT_BICORNE = mat("hat_b", (0.08, 0.08, 0.08, 1.0), 0.0, 0.7)
M_BANDANA = mat("bandana", (0.75, 0.18, 0.15, 1.0), 0.0, 0.55, emission=(0.65,0.15,0.12), emission_strength=0.4)
M_HAIR = mat("hair", (0.20, 0.12, 0.08, 1.0), 0.0, 0.85)
M_BEARD = mat("beard", (0.15, 0.10, 0.05, 1.0), 0.0, 0.85)
M_SABER = mat("saber", (0.85, 0.90, 0.95, 1.0), 0.95, 0.10, emission=(0.80,0.85,0.92), emission_strength=0.8)

# Mermaid hostile
M_MERMAID_TAIL_DARK = mat("merm_tail", (0.40, 0.10, 0.55, 1.0), 0.4, 0.30, emission=(0.45,0.12,0.60), emission_strength=2.0)
M_MERMAID_SKIN = mat("merm_skin", (0.85, 0.78, 0.85, 1.0), 0.0, 0.50, emission=(0.75,0.70,0.78), emission_strength=0.5)
M_MERMAID_HAIR = mat("merm_hair", (0.20, 0.55, 0.65, 1.0), 0.0, 0.55, emission=(0.18,0.50,0.62), emission_strength=0.8)
M_MERMAID_EYE = mat("merm_eye", (0.50, 1.0, 0.80, 1.0), 0.0, 0.15, emission=(0.55,1.0,0.85), emission_strength=6.0)

# Debris
M_DEBRIS = mat("debris", (0.30, 0.20, 0.12, 1.0), 0.2, 0.75, emission=(0.25,0.17,0.10), emission_strength=0.4)

# ============ SKY DOME + STORM CLOUDS ============
sky = smooth_sphere("sky", r=90, segs=32, rings=20, loc=(0,0,0), mat_=M_SKY_STORM, scale=(1,1,0.6))
sky.scale = (1,1,0.6)

# 12 massive storm clouds
storm_clouds = []
for i in range(12):
    a = (i / 12.0) * math.pi * 2 + random.uniform(-0.1, 0.1)
    rad = random.uniform(20, 30)
    cx, cy = rad*math.cos(a), rad*math.sin(a)
    cz = random.uniform(15, 25)
    c_e = empty(f"cloud_e{i}", (cx, cy, cz))
    for j in range(6):
        smooth_sphere(f"cloud{i}_{j}", r=random.uniform(2.5, 4.5),
                      loc=(random.uniform(-3,3), random.uniform(-2,2), random.uniform(-0.5,0.5)),
                      parent=c_e, mat_=M_STORM_CLOUD)
    c_e["_phase"] = random.uniform(0, math.pi*2)
    storm_clouds.append(c_e)

# Moon hidden behind clouds (faint emissive)
moon = smooth_sphere("moon", r=2.5, loc=(10, 25, 22), mat_=M_MOON_GLOW)

# 3 lightning bolts (zigzag)
lightning_bolts = []
for li in range(3):
    base_x = -25 + li * 25
    base_y = 5 + li * 8
    bolt_e = empty(f"bolt_e{li}", (base_x, base_y, 24))
    # 6 zigzag segments
    for i in range(6):
        seg = beveled_cube(f"bolt{li}_{i}", (0.20, 0.10, 1.5), bevel_offset=0.02,
                          loc=(((i % 2) * 1.2) - 0.6, 0, -i * 1.2),
                          parent=bolt_e, mat_=M_LIGHTNING)
        seg.rotation_euler = (0, 0, math.radians(((i%2) * 35 - 17)))
    # Branches (2 per bolt)
    for bi in range(2):
        branch_e = empty(f"bolt_br{li}_{bi}", (random.uniform(-1, 1), 0, -random.uniform(2, 5)), parent=bolt_e)
        branch_e.rotation_euler = (0, math.radians(random.uniform(20, 60)), 0)
        for j in range(3):
            seg = beveled_cube(f"bolt_br{li}_{bi}_{j}", (0.15, 0.08, 1.0), bevel_offset=0.02,
                              loc=(((j%2)*0.8)-0.4, 0, -j*0.9), parent=branch_e, mat_=M_LIGHTNING)
            seg.rotation_euler = (0, 0, math.radians(((j%2)*30-15)))
    bolt_e["_phase"] = li * 2.0
    lightning_bolts.append(bolt_e)

# ============ STORMY OCEAN ============
ocean = beveled_cube("ocean", (80, 80, 0.5), bevel_offset=0.05, loc=(0, 0, -0.25), mat_=M_WATER_DARK)

# 12 BIG WAVES (massive crests)
big_waves = []
for i in range(12):
    a = (i / 12.0) * math.pi * 2 + random.uniform(-0.1, 0.1)
    rad = random.uniform(8, 25)
    wx, wy = rad*math.cos(a), rad*math.sin(a)
    # Wave body (elongated cylinder)
    w = smooth_sphere(f"wave{i}", r=random.uniform(2.5, 4.0), segs=22, rings=14,
                     loc=(wx, wy, 1.0 + random.uniform(0, 1.5)),
                     mat_=M_WATER_CREST,
                     scale=(random.uniform(2.5, 4.0), 1.2, 0.9))
    w["_phase"] = random.uniform(0, math.pi*2)
    w["_base_z"] = w.location.z
    # Foam crest on top
    smooth_sphere(f"wave_foam{i}", r=random.uniform(0.6, 1.2),
                  loc=(wx, wy, w.location.z + 1.5), mat_=M_FOAM,
                  scale=(2.5, 1.0, 0.3))
    big_waves.append(w)

# 30 small whitecaps scattered
whitecaps = []
for i in range(30):
    wx = random.uniform(-30, 30)
    wy = random.uniform(-30, 30)
    wz = 0.5 + random.uniform(0, 0.4)
    wc = smooth_sphere(f"whitecap{i}", r=random.uniform(0.3, 0.6),
                      loc=(wx, wy, wz), mat_=M_FOAM,
                      scale=(2.0, 0.7, 0.3))
    wc["_phase"] = random.uniform(0, math.pi*2)
    whitecaps.append(wc)

# ============ KRAKEN (8 tentacles + head) ============
kraken_base = empty("kraken", loc=(-8, -3, 0))

# HEAD (huge bulbous mass) - half submerged
head_e = empty("kraken_head_e", (0, 0, 2.5), parent=kraken_base)
# Main bulbous body
kraken_body = smooth_sphere("kraken_main", r=2.8, segs=32, rings=20,
                             loc=(0, 0, 0), parent=head_e, mat_=M_KRAKEN_BODY,
                             scale=(1.4, 1.2, 1.0))
# Belly lighter (front)
smooth_sphere("kraken_belly", r=2.4, loc=(0, -1.0, -0.5),
              parent=head_e, mat_=M_KRAKEN_BELLY, scale=(1.2, 0.6, 0.8))
# Top fins/protrusions (2)
for side in (-1, 1):
    smooth_cone(f"kraken_fin_{side}", r1=0.50, r2=0.10, depth=1.2, segs=12,
                loc=(side*1.5, 0.5, 1.5), parent=head_e, mat_=M_KRAKEN_DARK).rotation_euler = (0, math.radians(side*-20), 0)

# 2 HUGE EYES (yellow émissif glowing)
for side in (-1, 1):
    eye_e = empty(f"kraken_eye_e_{side}", (side*1.3, -1.8, 0.5), parent=head_e)
    # White (large sclera)
    smooth_sphere(f"kraken_eye_white_{side}", r=0.55, loc=(0, 0, 0),
                  parent=eye_e, mat_=M_KRAKEN_BELLY)
    # Iris
    smooth_sphere(f"kraken_iris_{side}", r=0.45, loc=(0, -0.20, 0),
                  parent=eye_e, mat_=M_KRAKEN_EYE)
    # Pupil (vertical slit like cephalopod)
    beveled_cube(f"kraken_pup_{side}", (0.10, 0.04, 0.40),
                 loc=(0, -0.40, 0), parent=eye_e, mat_=M_KRAKEN_PUPIL)
    # Eyelid (overhang above)
    smooth_sphere(f"kraken_lid_{side}", r=0.60, loc=(0, 0, 0.25),
                  parent=eye_e, mat_=M_KRAKEN_BODY, scale=(1, 1, 0.4))

# BEAK (parrot-like, between tentacles below head)
beak_e = empty("kraken_beak_e", (0, -1.5, -1.5), parent=head_e)
smooth_cone("beak_top", r1=0.30, r2=0.05, depth=0.45, segs=10,
            loc=(0, 0, 0.10), parent=beak_e, mat_=M_BEAK).rotation_euler = (math.radians(60), 0, 0)
smooth_cone("beak_bot", r1=0.30, r2=0.05, depth=0.45, segs=10,
            loc=(0, 0, -0.10), parent=beak_e, mat_=M_BEAK).rotation_euler = (math.radians(120), 0, 0)

# 8 TENTACLES (serpentine, made of 10 segments each with suckers)
tentacles = []
for ti in range(8):
    angle = (ti / 8.0) * math.pi * 2
    tentacle_e = empty(f"tentacle{ti}", (math.cos(angle)*1.5, math.sin(angle)*1.5, 1.5), parent=kraken_base)
    tentacle_e.rotation_euler = (0, 0, angle)
    # 10 segments tapered
    seg_empties = []
    parent_e = tentacle_e
    for s in range(10):
        # Segment empty (for animation)
        s_e = empty(f"tent{ti}_se{s}", (0, 1.0, 0), parent=parent_e)
        seg_empties.append(s_e)
        # Segment body
        r1 = 0.45 - s*0.035
        r2 = 0.40 - s*0.035
        seg = smooth_cone(f"tent{ti}_s{s}", r1=r1, r2=r2, depth=1.0, segs=12,
                          loc=(0, 0, 0), parent=s_e, mat_=M_KRAKEN_BODY)
        seg.rotation_euler = (math.radians(90), 0, 0)  # lie along Y
        # Belly (lighter underside)
        smooth_sphere(f"tent{ti}_belly{s}", r=r1*0.8, loc=(0, 0, -r1*0.4),
                      parent=s_e, mat_=M_KRAKEN_BELLY, scale=(1, 1.5, 0.5))
        # 3 suckers per segment (visible underside)
        for su in range(3):
            sucker_y = -0.3 + su * 0.30
            smooth_sphere(f"tent{ti}_suc{s}_{su}", r=r1*0.25,
                          loc=(0, sucker_y, -r1*0.55),
                          parent=s_e, mat_=M_SUCKER, scale=(1, 1, 0.3))
        parent_e = s_e

    # Tip (sharp end)
    smooth_cone(f"tent{ti}_tip", r1=0.05, r2=0.005, depth=0.30, segs=8,
                loc=(0, 0.5, 0), parent=parent_e, mat_=M_KRAKEN_DARK).rotation_euler = (math.radians(90), 0, 0)

    # Initial pose - splayed outward at various heights
    tentacle_e.rotation_euler = (math.radians(random.uniform(-30, 30)),
                                  math.radians(random.uniform(-60, -20)),
                                  angle)
    # Slight bends per segment
    for si, s_e in enumerate(seg_empties):
        s_e.rotation_euler = (math.radians(random.uniform(-8, 8)),
                               math.radians(random.uniform(15, 30)),
                               math.radians(random.uniform(-5, 5)))
    tentacles.append({"root": tentacle_e, "segments": seg_empties,
                      "phase": random.uniform(0, math.pi*2),
                      "angle": angle})

# ============ GALLEON (heavily damaged) ============
galleon_base = empty("galleon", loc=(8, 5, 0.5))
galleon_base.rotation_euler = (math.radians(-12), math.radians(8), math.radians(15))

# Hull (3 levels)
beveled_cube("hull_bot", (5.5, 1.6, 1.0), bevel_offset=0.10,
             loc=(0, 0, 0), parent=galleon_base, mat_=M_WOOD_DARK)
beveled_cube("hull_main", (5.2, 1.4, 0.8), bevel_offset=0.10,
             loc=(0, 0, 0.85), parent=galleon_base, mat_=M_WOOD)
# Bow tilted
bow = beveled_cube("bow", (1.5, 1.3, 1.2), bevel_offset=0.10,
                   loc=(3.0, 0, 0.6), parent=galleon_base, mat_=M_WOOD_DARK)
bow.rotation_euler = (0, math.radians(15), 0)
# Stern (raised aft castle)
beveled_cube("stern", (1.8, 1.5, 1.5), bevel_offset=0.10,
             loc=(-2.6, 0, 1.5), parent=galleon_base, mat_=M_WOOD)
# Bowsprit
bowsprit = cyl("bowsprit", r=0.10, depth=1.8, segs=10,
                loc=(3.9, 0, 1.2), parent=galleon_base, mat_=M_WOOD)
bowsprit.rotation_euler = (0, math.radians(-25), 0)

# Damage to hull (visible cracks, exposed wood)
for i in range(5):
    damage = beveled_cube(f"damage{i}", (random.uniform(0.4, 0.8),
                                          0.05,
                                          random.uniform(0.3, 0.6)),
                         loc=(random.uniform(-2, 2),
                              random.choice([-0.7, 0.7]),
                              random.uniform(0.4, 1.2)),
                         parent=galleon_base, mat_=M_WOOD_DAMAGED)
    damage.rotation_euler = (math.radians(random.uniform(-15, 15)),
                             math.radians(random.uniform(-15, 15)),
                             math.radians(random.uniform(0, 360)))

# Hull windows (6, some shattered)
for i in range(6):
    for side in (-1, 1):
        if random.random() < 0.5:
            smooth_sphere(f"win_{i}_{side}", r=0.10,
                          loc=(-2 + i*0.7, side*0.7, 0.45), parent=galleon_base,
                          mat_=M_LANTERN_SHIP, scale=(0.8, 0.3, 0.8))

# 3 MASTS (mainmast broken/snapped!)
mast_specs = [(2.0, "fore", False), (0.0, "main", True), (-1.8, "mizzen", False)]
for mx, name_m, broken in mast_specs:
    m_e = empty(f"mast_{name_m}", (mx, 0, 1.5), parent=galleon_base)
    if broken:
        # Snapped - shorter pole + tilted angle + jagged top
        cyl(f"mast_pole_{name_m}", r=0.13, depth=2.5, segs=12,
            loc=(0, 0, 1.25), parent=m_e, mat_=M_WOOD)
        # Jagged top
        smooth_cone(f"mast_jagged_{name_m}", r1=0.13, r2=0.04, depth=0.40, segs=8,
                    loc=(0, 0, 2.7), parent=m_e, mat_=M_WOOD_DAMAGED)
        # Tilted broken yard
        broken_yard = beveled_cube(f"broken_yard", (0.06, 1.8, 0.06),
                                   loc=(0.30, 0, 2.0), parent=m_e, mat_=M_WOOD_DAMAGED)
        broken_yard.rotation_euler = (math.radians(45), 0, math.radians(20))
        # Torn sail (small, hanging)
        torn = beveled_cube(f"torn_sail", (0.04, 1.5, 1.0), bevel_offset=0.03,
                           loc=(0.30, 0, 1.5), parent=m_e, mat_=M_SAIL_TORN)
        torn.rotation_euler = (math.radians(-25), 0, math.radians(10))
    else:
        # Standing mast (3.5m)
        cyl(f"mast_pole_{name_m}", r=0.12, depth=4.0, segs=12,
            loc=(0, 0, 2.0), parent=m_e, mat_=M_WOOD)
        # Top cap gold
        smooth_sphere(f"mast_top_{name_m}", r=0.16, loc=(0, 0, 4.0),
                      parent=m_e, mat_=M_GOLD)
        # 2 yards with damaged sails
        for j, yz in enumerate([1.0, 2.5]):
            yard = beveled_cube(f"yard_{name_m}_{j}", (0.06, 2.6, 0.06),
                               loc=(0, 0, yz), parent=m_e, mat_=M_WOOD_DARK)
            # Sail - 50% torn variant
            sail_mat = M_SAIL_TORN if random.random() < 0.6 else M_SAIL
            sail = beveled_cube(f"sail_{name_m}_{j}", (0.06, 2.4, 1.2), bevel_offset=0.03,
                               loc=(0, 0, yz - 0.6), parent=m_e, mat_=sail_mat)
            sail.scale = (1.3, 1, 1)
            sail["_phase"] = random.uniform(0, math.pi*2)
            # Tear pattern (rip strips)
            if random.random() < 0.5:
                # Make this sail visibly shorter / chunked
                sail.scale = (1.3, random.uniform(0.5, 0.9), 1)

# Jolly Roger on mizzen
flag_e = empty("flag", (0, 0, 4.0), parent=m_e)
flag = beveled_cube("flag_cloth", (0.04, 1.3, 0.75), bevel_offset=0.02,
                    loc=(0, 0.65, 0), parent=flag_e, mat_=M_JOLLY)
smooth_sphere("flag_skull", r=0.18, loc=(0.05, 0.65, 0.12),
              parent=flag_e, mat_=M_JOLLY_WHITE, scale=(1, 1.2, 1.2))

# 8 CANNONS (some firing flashes)
firing_cannons = []
for side_idx, side in enumerate((-1, 1)):
    for i in range(4):
        cx = -1.5 + i * 1.2
        c_e = empty(f"cannon_e{side_idx}_{i}", (cx, side*0.85, 1.0), parent=galleon_base)
        c_e.rotation_euler = (0, 0, math.radians(side*90))
        cyl(f"cannon_barrel{side_idx}_{i}", r=0.10, depth=0.7, segs=12,
            loc=(0, 0, -0.35), parent=c_e, mat_=M_CANNON)
        # Carriage
        beveled_cube(f"cannon_carr{side_idx}_{i}", (0.20, 0.20, 0.15),
                     loc=(0, 0, -0.15), parent=c_e, mat_=M_WOOD_DARK)
        # 2 wheels
        for w_idx, w_side in enumerate((-1, 1)):
            wheel = cyl(f"cannon_wheel{side_idx}_{i}_{w_idx}", r=0.07, depth=0.04, segs=12,
                       loc=(w_side*0.10, 0.10, -0.18), parent=c_e, mat_=M_WOOD)
            wheel.rotation_euler = (math.radians(90), 0, 0)
        # 25% chance firing (muzzle flash + smoke)
        if random.random() < 0.30:
            flash = smooth_sphere(f"cannon_flash{side_idx}_{i}", r=0.30,
                                  loc=(0, 0, -0.85), parent=c_e, mat_=M_CANNON_FLASH)
            flash["_phase"] = random.uniform(0, math.pi*2)
            firing_cannons.append(flash)
            # Smoke puff
            smooth_sphere(f"cannon_smoke{side_idx}_{i}", r=0.25,
                          loc=(0, 0, -1.20), parent=c_e, mat_=M_STORM_CLOUD)

# Lanterns (3 hanging ship lanterns)
ship_lanterns = []
for i, (lx, ly, lz) in enumerate([(3.0, 0, 2.5), (-2.0, 0, 2.0), (0, 0, 4.5)]):
    sl = smooth_sphere(f"ship_lantern{i}", r=0.15, loc=(lx, ly, lz),
                      parent=galleon_base, mat_=M_LANTERN_SHIP)
    sl["_phase"] = i * 0.5
    ship_lanterns.append(sl)

# ============ CAPTAIN on deck ============
captain_base = empty("captain", loc=(8 + 1.5, 5 + 0.0, 2.0))
captain_base.rotation_euler = (0, 0, math.radians(-30))
# Quick captain - similar simple anatomy
# Legs
for side_idx, side in enumerate((-1, 1)):
    cyl(f"cap_leg{side_idx}", r=0.13, depth=0.85, segs=10,
        loc=(side*0.15, 0, 0.42), parent=captain_base, mat_=M_PANTS)
    beveled_cube(f"cap_boot{side_idx}", (0.20, 0.30, 0.30),
                 loc=(side*0.15, 0.05, 0.08), parent=captain_base, mat_=M_HAT_BICORNE)
# Torso
beveled_cube("cap_torso", (0.55, 0.35, 0.90), bevel_offset=0.05,
             loc=(0, 0, 1.30), parent=captain_base, mat_=M_COAT_CAPTAIN)
# Belt
beveled_cube("cap_belt", (0.60, 0.40, 0.10), loc=(0, 0, 0.92),
             parent=captain_base, mat_=M_HAT_BICORNE)
# Buckle
beveled_cube("cap_buckle", (0.15, 0.10, 0.15), loc=(0, -0.22, 0.92),
             parent=captain_base, mat_=M_GOLD)
# Head
cap_head_e = empty("cap_head_e", (0, 0, 1.90), parent=captain_base)
smooth_sphere("cap_head", r=0.20, segs=20, rings=14, loc=(0, 0, 0),
              parent=cap_head_e, mat_=M_SKIN_DARK)
# Beard
smooth_sphere("cap_beard", r=0.15, loc=(0, -0.10, -0.13),
              parent=cap_head_e, mat_=M_BEARD, scale=(1.3, 0.7, 1.0))
# Eyes (anger)
for side in (-1, 1):
    smooth_sphere(f"cap_eye_{side}", r=0.025,
                  loc=(side*0.07, -0.17, 0.03), parent=cap_head_e, mat_=M_JOLLY_WHITE)
# BICORNE HAT
hat_e = empty("cap_hat_e", (0, 0, 0.25), parent=cap_head_e)
smooth_sphere("cap_hat_crown", r=0.22, loc=(0, 0, 0),
              parent=hat_e, mat_=M_HAT_BICORNE, scale=(1, 1, 0.5))
for side in (-1, 1):
    wing = beveled_cube(f"cap_hat_wing{side}", (0.55, 0.18, 0.12),
                       loc=(side*0.40, 0, 0.05), parent=hat_e, mat_=M_HAT_BICORNE)
    wing.rotation_euler = (0, math.radians(side*18), 0)
smooth_sphere("cap_hat_skull", r=0.09, loc=(0, -0.25, 0.05),
              parent=hat_e, mat_=M_JOLLY_WHITE, scale=(1, 0.3, 1))

# Right arm with saber raised high
cap_r_sh = empty("cap_r_sh", (0.25, 0, 1.65), parent=captain_base)
cap_r_sh.rotation_euler = (math.radians(-160), 0, math.radians(-15))
cyl("cap_r_up", r=0.09, depth=0.40, segs=10,
    loc=(0, 0, -0.20), parent=cap_r_sh, mat_=M_COAT_CAPTAIN)
cap_r_el = empty("cap_r_el", (0, 0, -0.42), parent=cap_r_sh)
cyl("cap_r_fa", r=0.08, depth=0.38, segs=10,
    loc=(0, 0, -0.20), parent=cap_r_el, mat_=M_SKIN_DARK)
# Hand
smooth_sphere("cap_r_hand", r=0.09, loc=(0, 0, -0.45), parent=cap_r_el, mat_=M_SKIN_DARK)
# SABER raised
saber_e = empty("cap_saber_e", (0, 0, -0.55), parent=cap_r_el)
cyl("cap_saber_handle", r=0.04, depth=0.20, segs=10,
    loc=(0, 0, -0.10), parent=saber_e, mat_=M_HAT_BICORNE)
cyl("cap_saber_guard", r=0.10, depth=0.04, segs=14,
    loc=(0, 0, 0), parent=saber_e, mat_=M_GOLD).rotation_euler = (math.radians(90), 0, 0)
# Blade long curved
cyl("cap_saber_blade", r=0.05, depth=1.5, segs=12,
    loc=(0, 0, 0.75), parent=saber_e, mat_=M_SABER)
smooth_cone("cap_saber_tip", r1=0.05, r2=0.005, depth=0.15, segs=10,
            loc=(0, 0, 1.55), parent=saber_e, mat_=M_SABER)

# Left arm extended (balance)
cap_l_sh = empty("cap_l_sh", (-0.25, 0, 1.65), parent=captain_base)
cap_l_sh.rotation_euler = (math.radians(-80), 0, math.radians(40))
cyl("cap_l_up", r=0.09, depth=0.40, segs=10,
    loc=(0, 0, -0.20), parent=cap_l_sh, mat_=M_COAT_CAPTAIN)
cap_l_el = empty("cap_l_el", (0, 0, -0.42), parent=cap_l_sh)
cyl("cap_l_fa", r=0.08, depth=0.38, segs=10,
    loc=(0, 0, -0.20), parent=cap_l_el, mat_=M_SKIN_DARK)

# ============ 6 PIRATE CREW on deck struggling ============
crew_members = []
def make_pirate(name, loc, coat_mat, skin_mat, hat_mat=M_BANDANA, hat_type="bandana", action="lean"):
    base = empty(name, loc)
    # Legs
    for side_idx, side in enumerate((-1, 1)):
        cyl(f"{name}_leg{side_idx}", r=0.11, depth=0.85, segs=8,
            loc=(side*0.13, 0, 0.42), parent=base, mat_=M_PANTS)
        beveled_cube(f"{name}_boot{side_idx}", (0.18, 0.28, 0.30),
                     loc=(side*0.13, 0.05, 0.08), parent=base, mat_=M_HAT_BICORNE)
    # Torso
    beveled_cube(f"{name}_torso", (0.48, 0.32, 0.85), bevel_offset=0.05,
                 loc=(0, 0, 1.28), parent=base, mat_=coat_mat)
    # Head
    head_e = empty(f"{name}_head_e", (0, 0, 1.85), parent=base)
    smooth_sphere(f"{name}_head", r=0.18, segs=18, rings=12, loc=(0,0,0),
                  parent=head_e, mat_=skin_mat)
    # Eyes
    for side in (-1, 1):
        smooth_sphere(f"{name}_eye_{side}", r=0.025,
                      loc=(side*0.06, -0.15, 0.03), parent=head_e, mat_=M_JOLLY_WHITE)
    # Hat
    if hat_type == "bandana":
        smooth_sphere(f"{name}_bandana", r=0.22, loc=(0, 0, 0.10),
                      parent=head_e, mat_=hat_mat, scale=(1, 1, 0.6))
        # Tail
        beveled_cube(f"{name}_b_tail", (0.05, 0.16, 0.04),
                     loc=(0.15, 0.05, 0.05), parent=head_e, mat_=hat_mat)
    else:
        smooth_sphere(f"{name}_hat_c", r=0.24, loc=(0, 0, 0.13),
                      parent=head_e, mat_=hat_mat, scale=(1, 1, 0.5))
    # Arms (action-dependent)
    poses = {
        "lean": [(math.radians(-160), math.radians(-10)), (math.radians(-100), math.radians(15))],
        "brace": [(math.radians(-130), math.radians(-15)), (math.radians(-130), math.radians(15))],
        "panic": [(math.radians(-170), 0), (math.radians(-170), 0)],
        "fall": [(math.radians(-90), math.radians(-30)), (math.radians(-30), math.radians(15))],
    }
    pose = poses.get(action, poses["lean"])
    for side_idx, side in enumerate((-1, 1)):
        sh = empty(f"{name}_sh{side_idx}", (side*0.25, 0, 1.65), parent=base)
        rx, rz = pose[side_idx]
        sh.rotation_euler = (rx, 0, math.radians(side*-15) + rz)
        cyl(f"{name}_up{side_idx}", r=0.08, depth=0.40, segs=8,
            loc=(0, 0, -0.20), parent=sh, mat_=coat_mat)
        cyl(f"{name}_fa{side_idx}", r=0.07, depth=0.38, segs=8,
            loc=(0, 0, -0.55), parent=sh, mat_=skin_mat)
    return {"root": base, "head_e": head_e}

crew_specs = [
    ("crew0", (8 - 1.5, 5 - 0.5, 1.5), M_COAT_PIRATE, M_SKIN, M_BANDANA, "bandana", "brace"),
    ("crew1", (8 - 0.3, 5 + 0.5, 1.5), M_SHIRT_STRIPE, M_SKIN_DARK, M_BANDANA, "bandana", "panic"),
    ("crew2", (8 + 2.5, 5 + 0.4, 1.5), M_COAT_PIRATE, M_SKIN, M_HAT_BICORNE, "tricorne", "lean"),
    ("crew3", (8 + 0.5, 5 - 0.8, 2.5), M_SHIRT_STRIPE, M_SKIN, M_BANDANA, "bandana", "fall"),
    ("crew4", (8 - 2.0, 5 + 0.3, 1.5), M_COAT_PIRATE, M_SKIN_DARK, M_BANDANA, "bandana", "lean"),
    ("crew5", (8 + 1.8, 5 - 0.4, 2.5), M_SHIRT_STRIPE, M_SKIN, M_HAT_BICORNE, "tricorne", "panic"),
]
for spec in crew_specs:
    c = make_pirate(*spec)
    c["root"].rotation_euler = (math.radians(random.uniform(-15, 15)),
                                math.radians(random.uniform(-15, 15)),
                                random.uniform(-math.pi, math.pi))
    crew_members.append(c)

# ============ 2 HOSTILE MERMAIDS ============
mermaids = []
def make_hostile_mermaid(name, loc):
    base = empty(name, loc)
    base.rotation_euler = (math.radians(15), 0, random.uniform(-math.pi, math.pi))
    # Tail (4-seg)
    tail_pivot = empty(f"{name}_tail_p", (0, 0, 0), parent=base)
    for i in range(4):
        r1 = 0.30 - i*0.04
        r2 = 0.26 - i*0.04
        seg = smooth_cone(f"{name}_t{i}", r1=r1, r2=r2, depth=0.55, segs=14,
                          loc=(0, 0, -(i+0.5)*0.55), parent=tail_pivot, mat_=M_MERMAID_TAIL_DARK)
    # 2 fins lobes
    fin_e = empty(f"{name}_fin_e", (0, 0, -2.40), parent=tail_pivot)
    for side in (-1, 1):
        fin = beveled_cube(f"{name}_fin_{side}", (0.50, 0.04, 0.40), bevel_offset=0.04,
                           loc=(side*0.35, 0, 0), parent=fin_e, mat_=M_MERMAID_TAIL_DARK)
        fin.rotation_euler = (0, math.radians(side*20), math.radians(side*15))
    # Torso
    beveled_cube(f"{name}_torso", (0.42, 0.28, 0.65), bevel_offset=0.05,
                 loc=(0, 0, 0.40), parent=base, mat_=M_MERMAID_SKIN)
    # Head
    head_e = empty(f"{name}_head_e", (0, 0, 0.95), parent=base)
    smooth_sphere(f"{name}_h", r=0.20, segs=20, rings=14, loc=(0,0,0),
                  parent=head_e, mat_=M_MERMAID_SKIN)
    # Eyes glowing green hostile
    for side in (-1, 1):
        smooth_sphere(f"{name}_eye_{side}", r=0.06,
                      loc=(side*0.09, -0.17, 0.02), parent=head_e, mat_=M_MERMAID_EYE)
    # Hair wild
    for i in range(8):
        a = (i / 8.0) * math.pi * 2
        rad = 0.20
        strand = beveled_cube(f"{name}_h{i}", (0.05, 0.05, 0.6),
                              loc=(rad*math.cos(a), rad*math.sin(a), -0.30),
                              parent=head_e, mat_=M_MERMAID_HAIR)
        strand.rotation_euler = (math.radians(10*math.cos(a)),
                                 math.radians(10*math.sin(a)),
                                 random.uniform(0, math.pi))
    # Open mouth (singing/screaming)
    beveled_cube(f"{name}_mouth", (0.08, 0.04, 0.10),
                 loc=(0, -0.18, -0.10), parent=head_e, mat_=M_KRAKEN_PUPIL)
    # Sharp teeth (4)
    for j in range(4):
        smooth_cone(f"{name}_tooth{j}", r1=0.015, r2=0.005, depth=0.06, segs=6,
                    loc=((j-1.5)*0.03, -0.20, -0.07), parent=head_e, mat_=M_JOLLY_WHITE)
    # Arms reaching
    for side_idx, side in enumerate((-1, 1)):
        sh = empty(f"{name}_sh{side_idx}", (side*0.22, 0, 0.85), parent=base)
        sh.rotation_euler = (math.radians(-120), 0, math.radians(side*-25))
        cyl(f"{name}_up{side_idx}", r=0.07, depth=0.38, segs=8,
            loc=(0, 0, -0.20), parent=sh, mat_=M_MERMAID_SKIN)
        # Claws hand
        for c in range(4):
            cl = smooth_cone(f"{name}_claw{side_idx}_{c}", r1=0.02, r2=0.005, depth=0.10, segs=6,
                            loc=((c-1.5)*0.04, 0, -0.50), parent=sh, mat_=M_JOLLY_WHITE)
    return {"root": base, "tail_p": tail_pivot, "head_e": head_e}

merm1 = make_hostile_mermaid("merm1", (12, -2, 3))
merm2 = make_hostile_mermaid("merm2", (4, 8, 4))
mermaids = [merm1, merm2]

# ============ DEBRIS (30 pieces flying/floating) ============
debris = []
for i in range(30):
    dx = random.uniform(-20, 20)
    dy = random.uniform(-20, 20)
    dz = random.uniform(1, 12)
    sz = random.uniform(0.15, 0.45)
    d = beveled_cube(f"debris{i}", (sz, sz*0.8, sz*0.6), bevel_offset=0.03,
                     loc=(dx, dy, dz), mat_=M_DEBRIS)
    d.rotation_euler = (random.uniform(0, math.pi*2),
                        random.uniform(0, math.pi*2),
                        random.uniform(0, math.pi*2))
    d["_phase"] = random.uniform(0, math.pi*2)
    d["_base_x"] = dx; d["_base_y"] = dy; d["_base_z"] = dz
    debris.append(d)

# ============ RAIN STREAKS (200 lines falling) ============
rain_streaks = []
for i in range(200):
    rx = random.uniform(-35, 35)
    ry = random.uniform(-35, 35)
    rz = random.uniform(5, 25)
    streak = cyl(f"rain{i}", r=0.02, depth=random.uniform(0.5, 1.2), segs=6,
                loc=(rx, ry, rz), mat_=M_RAIN)
    streak.rotation_euler = (math.radians(15), 0, 0)
    streak["_phase"] = random.uniform(0, math.pi*2)
    streak["_base_x"] = rx; streak["_base_y"] = ry; streak["_base_z"] = rz
    streak["_speed"] = random.uniform(8.0, 15.0)
    rain_streaks.append(streak)

# ============ SPRAY DROPLETS (60) ============
sprays = []
for i in range(60):
    sx = random.uniform(-12, 12)
    sy = random.uniform(-12, 12)
    sz = random.uniform(0.5, 4)
    sp = smooth_sphere(f"spray{i}", r=random.uniform(0.06, 0.12), segs=8, rings=6,
                      loc=(sx, sy, sz), mat_=M_SPRAY)
    sp["_phase"] = random.uniform(0, math.pi*2)
    sp["_base_x"] = sx; sp["_base_y"] = sy; sp["_base_z"] = sz
    sprays.append(sp)

# ============ ANIMATION ============
fps = 30; duration_s = 6; total_frames = fps * duration_s

# Kraken head bob + body roll
for f in range(1, total_frames + 1, 3):
    t = (f - 1) / fps
    head_e.location.z = 2.5 + math.sin(t * 1.0) * 0.4
    head_e.rotation_euler = (math.sin(t * 0.8) * math.radians(5),
                              math.cos(t * 0.7) * math.radians(5),
                              math.sin(t * 0.5) * math.radians(10))
    head_e.keyframe_insert("location", frame=f)
    head_e.keyframe_insert("rotation_euler", frame=f)

# Tentacles undulate (each segment wave with phase offset)
for tent in tentacles:
    phase = tent["phase"]
    segments = tent["segments"]
    root = tent["root"]
    base_root_x = root.rotation_euler.x
    base_root_y = root.rotation_euler.y
    base_root_z = root.rotation_euler.z
    for f in range(1, total_frames + 1, 3):
        t = (f - 1) / fps
        # Root swing
        root.rotation_euler = (base_root_x + math.sin(t * 1.5 + phase) * math.radians(15),
                                base_root_y + math.cos(t * 1.5 + phase) * math.radians(10),
                                base_root_z)
        root.keyframe_insert("rotation_euler", frame=f)
        # Each segment wave with phase offset (propagating wave)
        for si, s_e in enumerate(segments):
            wave_phase = phase + si * 0.5
            s_e.rotation_euler = (math.sin(t * 2.5 + wave_phase) * math.radians(8),
                                   math.radians(20) + math.sin(t * 2.0 + wave_phase) * math.radians(8),
                                   math.cos(t * 2.0 + wave_phase) * math.radians(5))
            s_e.keyframe_insert("rotation_euler", frame=f)

# Kraken main body subtle breath
for f in range(1, total_frames + 1, 5):
    t = (f - 1) / fps
    s = 1 + math.sin(t * 1.2) * 0.04
    kraken_body.scale = (1.4 * s, 1.2 * s, 1.0 * s)
    kraken_body.keyframe_insert("scale", frame=f)

# Galleon violent rolling
for f in range(1, total_frames + 1, 2):
    t = (f - 1) / fps
    galleon_base.location.z = 0.5 + math.sin(t * 1.8) * 0.5
    galleon_base.rotation_euler = (math.radians(-12) + math.sin(t * 1.5) * math.radians(12),
                                    math.radians(8) + math.sin(t * 1.8 + 0.5) * math.radians(8),
                                    math.radians(15) + math.sin(t * 1.0) * math.radians(6))
    galleon_base.keyframe_insert("location", frame=f)
    galleon_base.keyframe_insert("rotation_euler", frame=f)

# Captain matches galleon roll
for f in range(1, total_frames + 1, 3):
    t = (f - 1) / fps
    # Saber swing
    cap_r_sh.rotation_euler = (math.radians(-160) + math.sin(t * 3.0) * math.radians(25),
                                0,
                                math.radians(-15) + math.cos(t * 3.0) * math.radians(15))
    cap_r_sh.keyframe_insert("rotation_euler", frame=f)
    # Captain location follows galleon
    captain_base.location.z = 2.0 + math.sin(t * 1.8) * 0.5
    captain_base.keyframe_insert("location", frame=f)

# Crew Z bob with galleon roll
for c in crew_members:
    base_z = c["root"].location.z
    for f in range(1, total_frames + 1, 4):
        t = (f - 1) / fps
        c["root"].location.z = base_z + math.sin(t * 1.8) * 0.5
        c["root"].keyframe_insert("location", frame=f)
        # Head turn (panic)
        c["head_e"].rotation_euler = (math.sin(t * 2.0) * math.radians(10),
                                       0,
                                       math.sin(t * 1.5) * math.radians(25))
        c["head_e"].keyframe_insert("rotation_euler", frame=f)

# Big waves swell up/down
for w in big_waves:
    if "_phase" not in w.keys():
        continue
    phase = w["_phase"]
    base_z = w["_base_z"]
    for f in range(1, total_frames + 1, 4):
        t = (f - 1) / fps
        w.location.z = base_z + math.sin(t * 1.8 + phase) * 0.8
        s = 1 + math.sin(t * 2.0 + phase) * 0.15
        w.scale = (w.scale.x * s / w.scale.x, w.scale.y * s / w.scale.y, w.scale.z)
        w.keyframe_insert("location", frame=f)

# Whitecaps pulse
for wc in whitecaps:
    phase = wc["_phase"]
    for f in range(1, total_frames + 1, 5):
        t = (f - 1) / fps
        s = 1 + math.sin(t * 3.0 + phase) * 0.30
        wc.scale = (2.0 * s, 0.7 * s, 0.3)
        wc.keyframe_insert("scale", frame=f)

# Lightning flashes (rare bright bursts)
for bolt in lightning_bolts:
    phase = bolt["_phase"]
    for f in range(1, total_frames + 1, 2):
        t = (f - 1) / fps
        # Pulse on/off pattern
        flash_factor = max(0, math.sin(t * 1.0 + phase) - 0.85) * 6.7
        s = flash_factor + 0.001
        bolt.scale = (s, s, s)
        bolt.keyframe_insert("scale", frame=f)

# Cannons firing flashes
for flash in firing_cannons:
    phase = flash["_phase"]
    for f in range(1, total_frames + 1, 2):
        t = (f - 1) / fps
        # Periodic burst
        cycle = (t * 1.5 + phase) % 2.0
        if cycle < 0.3:
            s = (0.3 - cycle) * 3.5
        else:
            s = 0.1
        flash.scale = (s, s, s)
        flash.keyframe_insert("scale", frame=f)

# Mermaids tail swish + hair flow
for m in mermaids:
    for f in range(1, total_frames + 1, 3):
        t = (f - 1) / fps
        m["tail_p"].rotation_euler = (0, math.sin(t * 2.5) * math.radians(20),
                                       math.cos(t * 2.5) * math.radians(15))
        m["tail_p"].keyframe_insert("rotation_euler", frame=f)
        # Body bob
        m["root"].location.z = m["root"].location.z + math.sin(t * 1.5) * 0.02
        # actually use fixed base
        # (skip to keep simple)

# Rain falling fast
for r in rain_streaks:
    phase = r["_phase"]
    speed = r["_speed"]
    bx, by, bz = r["_base_x"], r["_base_y"], r["_base_z"]
    for f in range(1, total_frames + 1, 3):
        t = (f - 1) / fps
        z = bz - (speed * t) % 25
        r.location = (bx, by, max(-1, z))
        r.keyframe_insert("location", frame=f)

# Spray droplets pulse and drift
for sp in sprays:
    phase = sp["_phase"]
    bx, by, bz = sp["_base_x"], sp["_base_y"], sp["_base_z"]
    for f in range(1, total_frames + 1, 4):
        t = (f - 1) / fps
        x = bx + math.sin(t * 2.0 + phase) * 0.4
        y = by + math.cos(t * 1.8 + phase) * 0.4
        z = bz + math.sin(t * 2.5 + phase) * 0.5
        s = 1 + math.sin(t * 5.0 + phase) * 0.4
        sp.location = (x, y, z)
        sp.scale = (s, s, s)
        sp.keyframe_insert("location", frame=f)
        sp.keyframe_insert("scale", frame=f)

# Debris drift + spin
for d in debris:
    if "_phase" not in d.keys():
        continue
    phase = d["_phase"]
    bx, by, bz = d["_base_x"], d["_base_y"], d["_base_z"]
    for f in range(1, total_frames + 1, 5):
        t = (f - 1) / fps
        x = bx + math.sin(t * 1.0 + phase) * 0.6
        y = by + math.cos(t * 0.9 + phase) * 0.6
        z = bz + math.sin(t * 1.5 + phase) * 0.5
        d.location = (x, y, z)
        d.rotation_euler = (phase + t * 1.5, phase + t * 1.2, phase + t * 1.8)
        d.keyframe_insert("location", frame=f)
        d.keyframe_insert("rotation_euler", frame=f)

# Storm clouds drift
for c_e in storm_clouds:
    phase = c_e["_phase"]
    bx, by = c_e.location.x, c_e.location.y
    for f in range(1, total_frames + 1, 8):
        t = (f - 1) / fps
        c_e.location = (bx + math.sin(t * 0.3 + phase) * 1.0,
                        by + math.cos(t * 0.25 + phase) * 1.0,
                        c_e.location.z)
        c_e.keyframe_insert("location", frame=f)

# Ship lanterns sway + pulse
for sl in ship_lanterns:
    phase = sl["_phase"]
    base_x = sl.location.x; base_y = sl.location.y
    for f in range(1, total_frames + 1, 4):
        t = (f - 1) / fps
        s = 1 + math.sin(t * 2.5 + phase) * 0.10
        sl.scale = (s, s, s)
        sl.keyframe_insert("scale", frame=f)

# ============ EXPORT ============
# ARCHITECTURE DE SORTIE. Ce script ecrivait son GLB dans
# `application/public/_pbr_test/`, un dossier servi par Vite — et que le build
# EFFACAIT au build (vite.config.ts, closeBundle). Le
# livrable ne rejoignait donc jamais `application/output/3d/`, ou la
# bibliotheque 3D, l interface et le tunnel vont le chercher : le fichier
# existait sur le disque et restait invisible. 111 scripts partageaient ce
# defaut, alors que `aurora_output_paths` enonce le contraire en toutes
# lettres : « Every module MUST place its outputs under
# application/output/<module_name>/<project_name>/ ».
import sys as _sys_out
_sys_out.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from aurora_output_paths import get_3d_project_dir as _aurora_dir_3d
out_dir = str(_aurora_dir_3d(
    os.path.splitext(os.path.basename(os.path.abspath(__file__)))[0]))
out_dir = os.path.normpath(out_dir)
os.makedirs(out_dir, exist_ok=True)
out_glb = os.path.join(out_dir, "pbr_kraken_proc.glb")

bpy.ops.object.select_all(action='SELECT')
bpy.ops.export_scene.gltf(
    filepath=out_glb, export_format='GLB',
    export_animations=True, export_apply=False, export_yup=True, use_selection=False,
)
size_mb = os.path.getsize(out_glb) / (1024 * 1024)
print(f"[proc_kraken_storm_galleon] DONE → {out_glb} ({size_mb:.2f} MB)")
print("[proc_kraken_storm_galleon] Kraken 8 tentacles + head + 2 eyes émissifs + beak + galleon damaged 3 mâts (main broken) + 6 sails torn + 8 cannons firing + captain saber + 6 crew + 2 mermaids hostile + 12 storm clouds + 3 lightning bolts + 12 big waves + 200 rain streaks + 60 spray + 30 debris")
