"""
proc_bioluminescent_abyss.py — 219e procédural AuroraIA (83e qualité)
Bioluminescent abyss: ONE seabed + 800 plankton + 12 jellyfish + 6 anglerfish + 3 giant squids + 4 tube worms + 2 beaked whales + shipwreck + bubbles
FIXES : 1 ground propre + 800 plankton bioluminescent thématique (signature abysses)
"""
import bpy, bmesh, math, random, os

random.seed(0xABA55219)

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

# Abyss materials — deep ocean dark + glowing biolume
M_WATER_DARK = mat("water_d", (0.02, 0.04, 0.10, 1.0), 0.0, 0.7, emission=(0.02,0.04,0.12), emission_strength=0.5)
M_LIGHT_RAY = mat("ray", (0.65, 0.85, 1.0, 0.50), 0.0, 0.20, emission=(0.65,0.85,1.0), emission_strength=4.5, alpha=0.50)

# Seabed sand
M_SAND_DEEP = mat("sand", (0.30, 0.30, 0.32, 1.0), 0.0, 0.80, emission=(0.25,0.25,0.28), emission_strength=0.3)
M_SAND_DARK = mat("sand_d", (0.18, 0.18, 0.22, 1.0), 0.0, 0.85)
M_ROCK_ABYSS = mat("rock", (0.20, 0.18, 0.22, 1.0), 0.0, 0.85)
M_ROCK_GLOW = mat("rock_g", (0.20, 0.22, 0.30, 1.0), 0.0, 0.75, emission=(0.20,0.30,0.42), emission_strength=0.7)

# Biolume colors (signature)
M_BIO_CYAN = mat("bio_c", (0.18, 0.90, 0.92, 1.0), 0.0, 0.10, emission=(0.18,0.90,0.92), emission_strength=14.0)
M_BIO_VIOLET = mat("bio_v", (0.65, 0.20, 0.95, 1.0), 0.0, 0.10, emission=(0.65,0.20,0.95), emission_strength=12.0)
M_BIO_PINK = mat("bio_p", (1.0, 0.35, 0.75, 1.0), 0.0, 0.10, emission=(1.0,0.35,0.75), emission_strength=13.0)
M_BIO_GREEN = mat("bio_g", (0.20, 0.95, 0.45, 1.0), 0.0, 0.10, emission=(0.20,0.95,0.45), emission_strength=12.0)
M_BIO_BLUE = mat("bio_b", (0.20, 0.45, 1.0, 1.0), 0.0, 0.10, emission=(0.20,0.45,1.0), emission_strength=13.0)
M_BIO_YELLOW = mat("bio_y", (1.0, 0.92, 0.30, 1.0), 0.0, 0.10, emission=(1.0,0.92,0.30), emission_strength=15.0)

# Jellyfish translucent bodies
M_JELLY_CYAN = mat("jc", (0.40, 0.92, 0.95, 0.65), 0.0, 0.15, emission=(0.40,0.92,0.95), emission_strength=5.0, alpha=0.65)
M_JELLY_VIOLET = mat("jv", (0.80, 0.40, 1.0, 0.65), 0.0, 0.15, emission=(0.80,0.40,1.0), emission_strength=4.5, alpha=0.65)
M_JELLY_PINK = mat("jp", (1.0, 0.55, 0.85, 0.65), 0.0, 0.15, emission=(1.0,0.55,0.85), emission_strength=5.0, alpha=0.65)
M_TENTACLE = mat("tent", (0.55, 0.80, 0.95, 0.55), 0.0, 0.20, emission=(0.55,0.80,0.95), emission_strength=3.0, alpha=0.55)

# Anglerfish dark + lure
M_ANGLER = mat("angler", (0.10, 0.08, 0.12, 1.0), 0.3, 0.55, emission=(0.10,0.08,0.12), emission_strength=0.4)
M_FANG_ANG = mat("fang", (0.95, 0.92, 0.85, 1.0), 0.0, 0.40, emission=(0.85,0.82,0.75), emission_strength=0.6)
M_FISH_EYE = mat("f_eye", (1.0, 0.85, 0.30, 1.0), 0.0, 0.10, emission=(1.0,0.85,0.30), emission_strength=8.0)

# Giant squid
M_SQUID = mat("squid", (0.55, 0.20, 0.35, 1.0), 0.0, 0.60, emission=(0.50,0.18,0.30), emission_strength=0.7)
M_SQUID_BELLY = mat("squid_b", (0.85, 0.45, 0.55, 1.0), 0.0, 0.55, emission=(0.78,0.42,0.50), emission_strength=0.8)
M_SQUID_EYE = mat("se", (1.0, 0.95, 0.30, 1.0), 0.0, 0.10, emission=(1.0,0.95,0.30), emission_strength=10.0)
M_SUCKER = mat("sucker", (0.95, 0.80, 0.70, 1.0), 0.0, 0.55, emission=(0.85,0.72,0.65), emission_strength=0.4)

# Anemones + worms + algae
M_ANEMONE_BASE = mat("anem_b", (0.55, 0.30, 0.30, 1.0), 0.0, 0.65, emission=(0.50,0.28,0.28), emission_strength=0.4)
M_TUBE = mat("tube", (0.40, 0.35, 0.45, 1.0), 0.0, 0.65, emission=(0.35,0.32,0.40), emission_strength=0.4)
M_ALGAE_GLOW = mat("algae_g", (0.30, 0.85, 0.65, 1.0), 0.0, 0.55, emission=(0.30,0.85,0.65), emission_strength=2.5)

# Whales (deep dark)
M_WHALE = mat("whale", (0.18, 0.20, 0.25, 1.0), 0.0, 0.70, emission=(0.15,0.18,0.22), emission_strength=0.5)
M_WHALE_BELLY = mat("whale_b", (0.45, 0.48, 0.55, 1.0), 0.0, 0.65, emission=(0.40,0.42,0.50), emission_strength=0.4)

# Shipwreck
M_WOOD_ROT = mat("wood_r", (0.25, 0.18, 0.12, 1.0), 0.0, 0.85, emission=(0.22,0.16,0.10), emission_strength=0.3)
M_MOSS_WET = mat("moss_w", (0.20, 0.45, 0.25, 1.0), 0.0, 0.75, emission=(0.18,0.40,0.22), emission_strength=0.7)
M_RUST = mat("rust", (0.55, 0.32, 0.18, 1.0), 0.0, 0.85, emission=(0.50,0.30,0.16), emission_strength=0.4)

# Bubbles
M_BUBBLE = mat("bubble", (0.95, 0.95, 1.0, 0.65), 0.0, 0.10, emission=(0.85,0.92,1.0), emission_strength=1.8, alpha=0.65)

# Coral / fluorescent
M_CORAL_PINK = mat("cor_p", (1.0, 0.40, 0.70, 1.0), 0.0, 0.45, emission=(1.0,0.40,0.70), emission_strength=3.0)
M_CORAL_BLUE = mat("cor_b", (0.30, 0.55, 1.0, 1.0), 0.0, 0.45, emission=(0.30,0.55,1.0), emission_strength=3.0)
M_CORAL_PURPLE = mat("cor_pu", (0.65, 0.30, 1.0, 1.0), 0.0, 0.45, emission=(0.65,0.30,1.0), emission_strength=3.0)
M_CORAL_GREEN = mat("cor_g", (0.30, 1.0, 0.55, 1.0), 0.0, 0.45, emission=(0.30,1.0,0.55), emission_strength=3.0)

# ============ SKY (dark water above) ============
sky = smooth_sphere("sky", r=140, segs=32, rings=20, loc=(0,0,0), mat_=M_WATER_DARK)
sky.scale = (1,1,0.55)

# 5 LIGHT RAYS from surface (signature god rays descending)
for i in range(5):
    a = (i / 5.0) * math.pi * 2
    rx = math.cos(a) * 15
    ry = math.sin(a) * 15
    ray_e = empty(f"ray_e{i}", (rx, ry, 25))
    ray = smooth_cone(f"ray{i}", r1=3, r2=8, depth=25, segs=16,
                      loc=(0, 0, 0), parent=ray_e, mat_=M_LIGHT_RAY)
    ray_e["_phase"] = random.uniform(0, math.pi*2)

# ============ ONE clean abyssal seabed ============
ground = beveled_cube("ground", (100, 100, 0.5), bevel_offset=0.08, loc=(0, 0, -0.25), mat_=M_SAND_DEEP)

# Sand mounds (organic 3D variations)
for i in range(50):
    a = random.uniform(0, math.pi*2)
    rad = random.uniform(8, 42)
    smooth_sphere(f"sand_m{i}", r=random.uniform(0.6, 1.4),
                  loc=(rad*math.cos(a), rad*math.sin(a), 0.30),
                  mat_=M_SAND_DARK if i % 3 == 0 else M_SAND_DEEP,
                  scale=(1.8, 1.5, 0.30))

# 40 rocks (organic 3D)
for i in range(40):
    a = random.uniform(0, math.pi*2)
    rad = random.uniform(10, 40)
    smooth_sphere(f"rock{i}", r=random.uniform(0.5, 1.3),
                  loc=(rad*math.cos(a), rad*math.sin(a), 0.40),
                  mat_=M_ROCK_ABYSS if i % 4 != 0 else M_ROCK_GLOW,
                  scale=(random.uniform(0.8,1.3), random.uniform(0.8,1.3),
                         random.uniform(0.5,0.85)))

# Bioluminescent algae sway (signature undersea glow)
algae_objs = []
for i in range(30):
    a = random.uniform(0, math.pi*2)
    rad = random.uniform(12, 35)
    ax = rad * math.cos(a)
    ay = rad * math.sin(a)
    al_e = empty(f"algae{i}", (ax, ay, 0))
    # 5 swaying segments
    for s in range(5):
        smooth_cone(f"algae{i}_s{s}", r1=0.12 - s*0.012, r2=0.10 - s*0.012,
                    depth=0.5, segs=10,
                    loc=(random.uniform(-0.05,0.05), random.uniform(-0.05,0.05),
                         (s+0.5)*0.45),
                    parent=al_e, mat_=M_ALGAE_GLOW)
    al_e["_phase"] = random.uniform(0, math.pi*2)
    algae_objs.append(al_e)

# Coral cluster fluorescent (signature reef glow)
coral_colors = [M_CORAL_PINK, M_CORAL_BLUE, M_CORAL_PURPLE, M_CORAL_GREEN]
for i in range(20):
    a = random.uniform(0, math.pi*2)
    rad = random.uniform(8, 30)
    cx = rad * math.cos(a)
    cy = rad * math.sin(a)
    coral_e = empty(f"coral{i}", (cx, cy, 0))
    # Branching coral
    for br in range(5):
        bra = (br / 5.0) * math.pi * 2
        col = coral_colors[i % 4]
        for k in range(3):
            t_p = k / 3.0
            seg_x = math.cos(bra) * t_p * 0.6
            seg_y = math.sin(bra) * t_p * 0.6
            seg_z = 0.4 + t_p * 0.8
            cyl(f"coral{i}_{br}_{k}", r=0.10 - k*0.02, depth=0.30, segs=8,
                loc=(seg_x, seg_y, seg_z), parent=coral_e, mat_=col)
        # Tip glow
        smooth_sphere(f"coral{i}_{br}_tip", r=0.12,
                      loc=(math.cos(bra)*0.6, math.sin(bra)*0.6, 1.2),
                      parent=coral_e, mat_=col)

# 8 ANEMONES on seabed
anemones = []
for i in range(8):
    a = (i / 8.0) * math.pi * 2 + random.uniform(-0.2, 0.2)
    rad = random.uniform(6, 22)
    ax = rad * math.cos(a)
    ay = rad * math.sin(a)
    an_e = empty(f"anem{i}", (ax, ay, 0))
    # Body base
    smooth_sphere(f"anem_body{i}", r=0.40, segs=18, rings=12,
                  loc=(0, 0, 0.40), parent=an_e, mat_=M_ANEMONE_BASE,
                  scale=(1, 1, 0.8))
    # Tentacles radiating up (signature)
    bio_col = [M_BIO_CYAN, M_BIO_VIOLET, M_BIO_PINK, M_BIO_GREEN][i % 4]
    for ti in range(16):
        ta = (ti / 16.0) * math.pi * 2
        for sk in range(4):
            cyl(f"anem{i}_t{ti}_{sk}", r=0.025, depth=0.18, segs=8,
                loc=(0.20*math.cos(ta), 0.20*math.sin(ta), 0.60 + sk*0.15),
                parent=an_e, mat_=bio_col)
        # Tip light
        smooth_sphere(f"anem{i}_tip{ti}", r=0.06,
                      loc=(0.20*math.cos(ta), 0.20*math.sin(ta), 1.30),
                      parent=an_e, mat_=bio_col)
    an_e["_phase"] = random.uniform(0, math.pi*2)
    anemones.append(an_e)

# 4 TUBE WORMS (giant fluorescent)
tube_worms = []
for i in range(4):
    a = (i / 4.0) * math.pi * 2
    rad = 18
    tx = rad * math.cos(a)
    ty = rad * math.sin(a)
    tw_e = empty(f"tw{i}", (tx, ty, 0))
    # Tube body
    cyl(f"tw_tube{i}", r=0.30, depth=2.5, segs=14,
        loc=(0, 0, 1.25), parent=tw_e, mat_=M_TUBE)
    # Plume at top (signature)
    plume_color = [M_BIO_PINK, M_BIO_CYAN, M_BIO_VIOLET, M_BIO_GREEN][i]
    for pi in range(20):
        pa = (pi / 20.0) * math.pi * 2
        rad_p = random.uniform(0.15, 0.30)
        ph_z = random.uniform(2.7, 3.3)
        smooth_sphere(f"tw_plu{i}_{pi}", r=random.uniform(0.08, 0.14),
                      loc=(rad_p*math.cos(pa), rad_p*math.sin(pa), ph_z),
                      parent=tw_e, mat_=plume_color)
    tw_e["_phase"] = random.uniform(0, math.pi*2)
    tube_worms.append(tw_e)

# ============ 12 BIOLUMINESCENT JELLYFISH ============
def make_jellyfish(name, loc, body_mat, scale=1.0):
    base = empty(name, loc)
    # Bell (dome) - signature jellyfish shape
    smooth_sphere(f"{name}_bell", r=0.55*scale, segs=22, rings=14, loc=(0, 0, 0),
                  parent=base, mat_=body_mat, scale=(1, 1, 0.65))
    # Inner glow core
    smooth_sphere(f"{name}_core", r=0.35*scale, loc=(0, 0, 0),
                  parent=base, mat_=body_mat, scale=(1, 1, 0.5))
    # Decorative bell rings
    for ri in range(3):
        cyl(f"{name}_ring{ri}", r=0.55*scale - ri*0.10*scale, depth=0.03*scale, segs=18,
            loc=(0, 0, -0.10*scale - ri*0.05*scale), parent=base, mat_=body_mat)
    # 8 long trailing tentacles
    tentacles = []
    for ti in range(8):
        ta = (ti / 8.0) * math.pi * 2
        t_e = empty(f"{name}_t_e{ti}", (0.35*scale*math.cos(ta), 0.35*scale*math.sin(ta), -0.2*scale),
                    parent=base)
        for sk in range(8):
            t_z = -0.2*scale - sk*0.30*scale
            wave_x = math.sin(sk * 0.5) * 0.10*scale
            wave_y = math.cos(sk * 0.5) * 0.10*scale
            cyl(f"{name}_t{ti}_{sk}", r=0.02*scale, depth=0.30*scale, segs=8,
                loc=(wave_x, wave_y, t_z), parent=t_e, mat_=M_TENTACLE)
        tentacles.append(t_e)
    # 4 short oral arms (more prominent)
    oral_arms = []
    for oi in range(4):
        oa = (oi / 4.0) * math.pi * 2
        o_e = empty(f"{name}_oa_e{oi}", (0, 0, -0.25*scale), parent=base)
        o_e.rotation_euler = (0, 0, oa)
        for sk in range(5):
            o_z = -sk*0.18*scale
            o_x = math.sin(sk * 0.8) * 0.10*scale
            beveled_cube(f"{name}_oa{oi}_{sk}", (0.06*scale, 0.04*scale, 0.18*scale), bevel_offset=0.01,
                         loc=(0.10*scale + o_x, 0, o_z), parent=o_e, mat_=body_mat)
        oral_arms.append(o_e)
    base["_phase"] = random.uniform(0, math.pi*2)
    return {"root": base, "tentacles": tentacles, "oral_arms": oral_arms}

jellyfish_list = []
jelly_colors = [M_JELLY_CYAN, M_JELLY_VIOLET, M_JELLY_PINK]
for i in range(12):
    a = (i / 12.0) * math.pi * 2 + random.uniform(-0.3, 0.3)
    rad = random.uniform(5, 22)
    jx = rad * math.cos(a)
    jy = rad * math.sin(a)
    jz = random.uniform(4, 18)
    j = make_jellyfish(f"jelly{i}", (jx, jy, jz), jelly_colors[i % 3], scale=random.uniform(0.7, 1.3))
    jellyfish_list.append(j)

# ============ 6 ANGLERFISH (deep abyss fishes with lure) ============
def make_anglerfish(name, loc, facing=0):
    base = empty(name, loc)
    base.rotation_euler = (0, 0, facing)
    # Massive bulbous body
    smooth_sphere(f"{name}_body", r=0.60, segs=22, rings=16, loc=(0, 0, 0),
                  parent=base, mat_=M_ANGLER, scale=(1.4, 1, 1))
    # Mouth (cavernous - signature)
    smooth_sphere(f"{name}_mouth", r=0.40, loc=(0.55, 0, 0),
                  parent=base, mat_=M_ANGLER, scale=(0.9, 1, 0.85))
    # Lower jaw open
    beveled_cube(f"{name}_jaw_l", (0.40, 0.50, 0.20), bevel_offset=0.04,
                 loc=(0.55, 0, -0.20), parent=base, mat_=M_ANGLER)
    # Multiple sharp fangs (signature)
    for fi in range(7):
        fa = (fi - 3) * 0.10
        # Upper
        smooth_cone(f"{name}_fang_u{fi}", r1=0.05, r2=0.005, depth=0.20, segs=8,
                    loc=(0.85, fa, 0.05), parent=base, mat_=M_FANG_ANG).rotation_euler = (0, math.radians(180), 0)
        # Lower
        smooth_cone(f"{name}_fang_l{fi}", r1=0.05, r2=0.005, depth=0.20, segs=8,
                    loc=(0.85, fa, -0.15), parent=base, mat_=M_FANG_ANG)
    # Glowing eyes
    for side in (-1, 1):
        smooth_sphere(f"{name}_eye{side}", r=0.10,
                      loc=(0.30, side*0.30, 0.20), parent=base, mat_=M_FISH_EYE)
    # LURE (signature anglerfish bioluminescent dorsal lure)
    lure_e = empty(f"{name}_lure_e", (0.15, 0, 0.50), parent=base)
    # Long curved stem
    for sk in range(5):
        sk_x = math.sin(sk * 0.3) * 0.10
        cyl(f"{name}_lure_st{sk}", r=0.020, depth=0.18, segs=8,
            loc=(sk_x, 0, sk * 0.15), parent=lure_e, mat_=M_ANGLER)
    # Glowing bulb at end
    smooth_sphere(f"{name}_lure_b", r=0.14, loc=(0.30, 0, 0.80),
                  parent=lure_e, mat_=M_BIO_YELLOW)
    # Halo around lure
    for h in range(3):
        smooth_sphere(f"{name}_lure_h{h}", r=0.14 + (h+1)*0.05,
                      loc=(0.30, 0, 0.80), parent=lure_e, mat_=M_BIO_YELLOW)
    # Tail (forked + small)
    beveled_cube(f"{name}_tail", (0.20, 0.30, 0.15), bevel_offset=0.03,
                 loc=(-0.75, 0, 0), parent=base, mat_=M_ANGLER)
    # Side fins
    for side in (-1, 1):
        beveled_cube(f"{name}_fin{side}", (0.30, 0.10, 0.15), bevel_offset=0.03,
                     loc=(0.10, side*0.50, 0), parent=base, mat_=M_ANGLER)
    base["_phase"] = random.uniform(0, math.pi*2)
    return {"root": base, "lure_e": lure_e}

anglerfish_list = []
for i in range(6):
    a = (i / 6.0) * math.pi * 2
    rad = random.uniform(8, 24)
    ax = rad * math.cos(a)
    ay = rad * math.sin(a)
    az = random.uniform(1.5, 12)
    af = make_anglerfish(f"angler{i}", (ax, ay, az), facing=a + math.pi/2)
    anglerfish_list.append(af)

# ============ 3 GIANT SQUIDS ============
def make_squid(name, loc, facing=0, scale=1.0):
    base = empty(name, loc)
    base.rotation_euler = (0, 0, facing)
    # Mantle (signature long conical)
    smooth_cone(f"{name}_mantle", r1=0.65*scale, r2=0.10*scale, depth=2.5*scale, segs=18,
                loc=(0, 0, 1.50*scale), parent=base, mat_=M_SQUID)
    # Mantle belly (lighter)
    smooth_cone(f"{name}_belly", r1=0.45*scale, r2=0.10*scale, depth=2.3*scale, segs=16,
                loc=(0, -0.18*scale, 1.55*scale), parent=base, mat_=M_SQUID_BELLY)
    # Mantle fins (signature)
    for side in (-1, 1):
        fin = beveled_cube(f"{name}_fin{side}", (0.10*scale, 0.40*scale, 0.50*scale), bevel_offset=0.03,
                          loc=(0, side*0.40*scale, 2.50*scale), parent=base, mat_=M_SQUID)
        fin.rotation_euler = (0, 0, math.radians(side*15))
    # Head bulge
    smooth_sphere(f"{name}_head", r=0.55*scale, loc=(0, 0, 0.30*scale),
                  parent=base, mat_=M_SQUID, scale=(1, 1, 0.85))
    # MASSIVE glowing eyes (signature squid)
    head_e = empty(f"{name}_he", (0, 0, 0.30*scale), parent=base)
    for side in (-1, 1):
        smooth_sphere(f"{name}_eye{side}", r=0.18*scale,
                      loc=(0.30*scale, side*0.45*scale, 0.05*scale), parent=head_e, mat_=M_SQUID_EYE)
        # Eye glow rings
        for hi in range(2):
            smooth_sphere(f"{name}_eyeh{side}_{hi}", r=0.18*scale + (hi+1)*0.05*scale,
                          loc=(0.30*scale, side*0.45*scale, 0.05*scale), parent=head_e, mat_=M_SQUID_EYE)
    # 10 tentacles (8 arms + 2 long feeding tentacles) signature
    tentacles = []
    for ti in range(10):
        ta = (ti / 10.0) * math.pi * 2
        t_e = empty(f"{name}_t_e{ti}", (0.25*scale*math.cos(ta), 0.25*scale*math.sin(ta), -0.10*scale),
                    parent=base)
        is_long = ti < 2  # First 2 are long feeding tentacles
        seg_count = 12 if is_long else 8
        seg_len = 0.40*scale if is_long else 0.35*scale
        seg_r_base = 0.06*scale if is_long else 0.07*scale
        for sk in range(seg_count):
            t_z = -0.10*scale - sk*seg_len
            wave_x = math.sin(sk * 0.6 + ti) * 0.10*scale
            wave_y = math.cos(sk * 0.6 + ti) * 0.10*scale
            cyl(f"{name}_t{ti}_{sk}", r=seg_r_base - sk*0.005*scale, depth=seg_len, segs=8,
                loc=(wave_x, wave_y, t_z), parent=t_e, mat_=M_SQUID_BELLY if sk % 2 == 0 else M_SQUID)
            # Suckers (signature)
            if sk % 2 == 1 and not is_long:
                for su in (-1, 1):
                    smooth_sphere(f"{name}_t{ti}_{sk}_su{su}", r=0.025*scale,
                                  loc=(wave_x + su*0.04*scale, wave_y, t_z),
                                  parent=t_e, mat_=M_SUCKER)
        # End club (for long tentacles only - feeding)
        if is_long:
            smooth_sphere(f"{name}_t{ti}_club", r=0.10*scale,
                          loc=(0, 0, -0.10*scale - seg_count*seg_len),
                          parent=t_e, mat_=M_SUCKER, scale=(1, 1, 1.3))
        tentacles.append(t_e)
    base["_phase"] = random.uniform(0, math.pi*2)
    return {"root": base, "he": head_e, "tentacles": tentacles}

squids = []
squid_specs = [
    ("squid1", (-15, 8, 12), math.radians(45), 1.3),
    ("squid2", (15, -8, 10), math.radians(-90), 1.1),
    ("squid3", (0, -18, 14), math.radians(180), 1.5),
]
for spec in squid_specs:
    name, loc, fac, sc = spec
    s = make_squid(name, loc, facing=fac, scale=sc)
    squids.append(s)

# ============ SHIPWRECK (sunken galleon) ============
wreck_e = empty("wreck", loc=(-22, -8, 0))
wreck_e.rotation_euler = (math.radians(10), math.radians(15), math.radians(-20))
# Hull (broken)
beveled_cube("w_hull", (6, 2.5, 1.5), bevel_offset=0.08, loc=(0, 0, 0.75),
             parent=wreck_e, mat_=M_WOOD_ROT)
# Hull split (top half open)
beveled_cube("w_hull_top", (4, 2.0, 0.8), bevel_offset=0.06, loc=(-1, 0, 1.90),
             parent=wreck_e, mat_=M_WOOD_ROT)
# Mast broken
mast = cyl("w_mast", r=0.18, depth=4.0, segs=14,
           loc=(0, 0, 2.5), parent=wreck_e, mat_=M_WOOD_ROT)
mast.rotation_euler = (math.radians(30), 0, 0)
# Yardarm
beveled_cube("w_yard", (2.5, 0.15, 0.15), bevel_offset=0.03,
             loc=(0, 0, 4.5), parent=wreck_e, mat_=M_WOOD_ROT)
# Tattered sail remnants
beveled_cube("w_sail", (2.0, 0.05, 1.0), bevel_offset=0.03,
             loc=(0, 0.10, 4.0), parent=wreck_e,
             mat_=mat("sail_m", (0.65, 0.55, 0.45, 1), 0, 0.85, alpha=0.85))
# Rusty cannon
cannon_e = empty("w_cannon", (1.5, 1.0, 1.5), parent=wreck_e)
cyl("w_cn_barrel", r=0.20, depth=1.5, segs=14, loc=(0, 0, 0), parent=cannon_e, mat_=M_RUST)
beveled_cube("w_cn_carr", (0.5, 0.6, 0.30), bevel_offset=0.04,
             loc=(-0.5, 0, -0.20), parent=cannon_e, mat_=M_WOOD_ROT)
# Moss/algae covering hull
for i in range(15):
    mx = random.uniform(-3, 3)
    my = random.uniform(-1.2, 1.2)
    mz = random.uniform(0.5, 1.8)
    smooth_sphere(f"w_moss{i}", r=random.uniform(0.20, 0.40),
                  loc=(mx, my, mz), parent=wreck_e, mat_=M_MOSS_WET,
                  scale=(1.2, 1.0, 0.25))

# ============ 2 BEAKED WHALES (deep diving cetaceans) ============
def make_whale(name, loc, facing=0):
    base = empty(name, loc)
    base.rotation_euler = (0, 0, facing)
    # Massive elongated body
    smooth_sphere(f"{name}_body", r=0.95, segs=22, rings=16, loc=(0, 0, 0),
                  parent=base, mat_=M_WHALE, scale=(3.0, 1.0, 1.0))
    # Belly lighter
    smooth_sphere(f"{name}_belly", r=0.85, loc=(0, 0, -0.20),
                  parent=base, mat_=M_WHALE_BELLY, scale=(2.5, 0.95, 0.65))
    # Head (signature beaked)
    smooth_cone(f"{name}_head", r1=0.70, r2=0.20, depth=1.2, segs=18,
                loc=(2.5, 0, 0), parent=base, mat_=M_WHALE).rotation_euler = (0, math.radians(90), 0)
    # Beak tip
    smooth_cone(f"{name}_beak", r1=0.15, r2=0.05, depth=0.40, segs=12,
                loc=(3.0, 0, -0.05), parent=base, mat_=M_WHALE).rotation_euler = (0, math.radians(90), 0)
    # Eyes
    for side in (-1, 1):
        smooth_sphere(f"{name}_eye{side}", r=0.06,
                      loc=(2.0, side*0.65, 0.20), parent=base,
                      mat_=mat(f"{name}_ew{side}", (0.05,0.05,0.05,1), 0, 0.4))
    # Dorsal fin (small)
    dorsal = beveled_cube(f"{name}_dorsal", (0.20, 0.30, 0.40), bevel_offset=0.04,
                          loc=(0, 0, 0.85), parent=base, mat_=M_WHALE)
    dorsal.rotation_euler = (0, math.radians(-25), 0)
    # Pectoral fins
    for side in (-1, 1):
        fin = beveled_cube(f"{name}_pec{side}", (0.50, 0.20, 0.10), bevel_offset=0.03,
                          loc=(1.0, side*0.80, -0.20), parent=base, mat_=M_WHALE)
        fin.rotation_euler = (0, math.radians(15), math.radians(side*20))
    # Tail fluke
    tail_e = empty(f"{name}_te", (-2.5, 0, 0), parent=base)
    beveled_cube(f"{name}_fluke", (0.30, 1.50, 0.10), bevel_offset=0.04,
                 loc=(0, 0, 0), parent=tail_e, mat_=M_WHALE)
    base["_phase"] = random.uniform(0, math.pi*2)
    return {"root": base, "tail": tail_e}

whales = [
    make_whale("whale1", (28, 18, 14), math.radians(180)),
    make_whale("whale2", (-25, 25, 18), math.radians(-60)),
]

# ============================================================
# ⭐ 800 BIOLUMINESCENT PLANCTON + 100 BUBBLES (PARTICULES THÉMATIQUES OBLIGATOIRES)
# ============================================================
# 800 plancton - tiny glowing particles
plankton = []
for i in range(800):
    px = random.uniform(-42, 42)
    py = random.uniform(-42, 42)
    pz = random.uniform(0.5, 22)
    bio_col = [M_BIO_CYAN, M_BIO_VIOLET, M_BIO_PINK, M_BIO_GREEN, M_BIO_BLUE][i % 5]
    p_obj = smooth_sphere(f"plk{i}", r=random.uniform(0.04, 0.08), segs=8, rings=6,
                          loc=(px, py, pz), mat_=bio_col)
    p_obj["_phase"] = random.uniform(0, math.pi*2)
    p_obj["_base_x"] = px; p_obj["_base_y"] = py; p_obj["_base_z"] = pz
    p_obj["_amp_x"] = random.uniform(0.6, 1.8)
    p_obj["_amp_y"] = random.uniform(0.6, 1.8)
    p_obj["_amp_z"] = random.uniform(0.4, 1.2)
    p_obj["_speed"] = random.uniform(0.3, 1.0)
    plankton.append(p_obj)

# 100 bubbles rising
bubbles = []
for i in range(100):
    px = random.uniform(-40, 40)
    py = random.uniform(-40, 40)
    pz = random.uniform(0.5, 18)
    b_obj = smooth_sphere(f"bub{i}", r=random.uniform(0.08, 0.18), segs=12, rings=8,
                          loc=(px, py, pz), mat_=M_BUBBLE)
    b_obj["_phase"] = random.uniform(0, math.pi*2)
    b_obj["_base_x"] = px; b_obj["_base_y"] = py; b_obj["_base_z"] = pz
    b_obj["_speed"] = random.uniform(1.5, 3.5)
    b_obj["_drift_x"] = random.uniform(-0.8, 0.8)
    b_obj["_drift_y"] = random.uniform(-0.8, 0.8)
    bubbles.append(b_obj)

# ============ ANIMATION ============
fps = 30; duration_s = 6; total_frames = fps * duration_s

# Light rays slow rotation
for ray_idx in range(5):
    ray_obj = bpy.data.objects[f"ray_e{ray_idx}"]
    phase = ray_obj["_phase"]
    for f in range(1, total_frames + 1, 6):
        t = (f - 1) / fps
        ray_obj.rotation_euler = (math.sin(t * 0.3 + phase) * math.radians(5),
                                    math.cos(t * 0.2 + phase) * math.radians(4), 0)
        ray_obj.keyframe_insert("rotation_euler", frame=f)

# Algae sway
for al in algae_objs:
    phase = al["_phase"]
    for f in range(1, total_frames + 1, 5):
        t = (f - 1) / fps
        al.rotation_euler = (math.sin(t * 1.2 + phase) * math.radians(8),
                              math.cos(t * 1.0 + phase) * math.radians(6),
                              0)
        al.keyframe_insert("rotation_euler", frame=f)

# Anemones contract+expand
for an in anemones:
    phase = an["_phase"]
    for f in range(1, total_frames + 1, 4):
        t = (f - 1) / fps
        s = 1 + math.sin(t * 1.5 + phase) * 0.12
        an.scale = (s, s, 1 + math.sin(t * 1.2 + phase) * 0.08)
        an.keyframe_insert("scale", frame=f)

# Tube worms wave plume
for tw in tube_worms:
    phase = tw["_phase"]
    for f in range(1, total_frames + 1, 4):
        t = (f - 1) / fps
        tw.rotation_euler = (math.sin(t * 1.3 + phase) * math.radians(6),
                              math.cos(t * 1.1 + phase) * math.radians(5), 0)
        tw.keyframe_insert("rotation_euler", frame=f)

# Jellyfish - pulse bell + rise + tentacles wave
for j in jellyfish_list:
    phase = j["root"]["_phase"]
    base_z = j["root"].location.z
    for f in range(1, total_frames + 1, 3):
        t = (f - 1) / fps
        # Bell pulse - signature
        s = 1 + math.sin(t * 2.5 + phase) * 0.12
        j["root"].scale = (s, s, 1 + math.cos(t * 2.5 + phase) * 0.08)
        # Rise slow
        j["root"].location.z = base_z + math.sin(t * 0.6 + phase) * 2.0
        j["root"].location.x = j["root"].location.x + math.sin(t * 0.3 + phase) * 0.05  # subtle drift
        j["root"].keyframe_insert("scale", frame=f)
        j["root"].keyframe_insert("location", frame=f)
        # Tentacle wave
        for ti, t_e in enumerate(j["tentacles"]):
            t_e.rotation_euler = (math.sin(t * 1.5 + phase + ti * 0.5) * math.radians(8),
                                   math.cos(t * 1.3 + phase + ti * 0.5) * math.radians(8), 0)
            t_e.keyframe_insert("rotation_euler", frame=f)
        # Oral arms
        for oi, o_e in enumerate(j["oral_arms"]):
            o_e.rotation_euler = (math.sin(t * 1.2 + phase + oi * 0.7) * math.radians(10), 0,
                                    o_e.rotation_euler.z)
            o_e.keyframe_insert("rotation_euler", frame=f)

# Anglerfish - subtle bob + lure oscillates (signature)
for af in anglerfish_list:
    phase = af["root"]["_phase"]
    base_x = af["root"].location.x
    base_y = af["root"].location.y
    base_z = af["root"].location.z
    for f in range(1, total_frames + 1, 4):
        t = (f - 1) / fps
        af["root"].location = (base_x + math.sin(t * 0.5 + phase) * 1.5,
                                base_y + math.cos(t * 0.4 + phase) * 1.0,
                                base_z + math.sin(t * 0.8 + phase) * 0.8)
        af["root"].keyframe_insert("location", frame=f)
        # Lure oscillates (signature anglerfish lure twitch)
        af["lure_e"].rotation_euler = (math.sin(t * 2.5 + phase) * math.radians(15),
                                         math.cos(t * 2.0 + phase) * math.radians(12), 0)
        af["lure_e"].keyframe_insert("rotation_euler", frame=f)

# Squid - mantle wave + tentacles propulsion
for sq in squids:
    phase = sq["root"]["_phase"]
    base_x = sq["root"].location.x
    base_y = sq["root"].location.y
    base_z = sq["root"].location.z
    for f in range(1, total_frames + 1, 3):
        t = (f - 1) / fps
        # Jet propulsion drift
        sq["root"].location = (base_x + math.sin(t * 0.5 + phase) * 2.0,
                                base_y + math.cos(t * 0.4 + phase) * 1.5,
                                base_z + math.sin(t * 0.7 + phase) * 1.2)
        sq["root"].rotation_euler = (math.sin(t * 0.5 + phase) * math.radians(6),
                                       math.cos(t * 0.4 + phase) * math.radians(5),
                                       sq["root"].rotation_euler.z + t * 0.2)
        sq["root"].keyframe_insert("location", frame=f)
        sq["root"].keyframe_insert("rotation_euler", frame=f)
        # Tentacles propagated wave (signature octopus/squid movement)
        for ti, t_e in enumerate(sq["tentacles"]):
            t_phase = phase + ti * 0.3
            t_e.rotation_euler = (math.sin(t * 1.8 + t_phase) * math.radians(12),
                                   math.cos(t * 1.5 + t_phase) * math.radians(10), 0)
            t_e.keyframe_insert("rotation_euler", frame=f)
        # Eye glow pulse
        sq["he"].scale = (1 + math.sin(t * 3.0 + phase) * 0.08,
                          1 + math.sin(t * 3.0 + phase) * 0.08, 1)
        sq["he"].keyframe_insert("scale", frame=f)

# Whales - slow majestic dive
for w in whales:
    phase = w["root"]["_phase"]
    base_x = w["root"].location.x
    base_y = w["root"].location.y
    base_z = w["root"].location.z
    for f in range(1, total_frames + 1, 4):
        t = (f - 1) / fps
        w["root"].location = (base_x + math.sin(t * 0.3 + phase) * 3.0,
                               base_y + math.cos(t * 0.25 + phase) * 2.5,
                               base_z + math.sin(t * 0.4 + phase) * 2.0)
        w["root"].rotation_euler = (math.sin(t * 0.4 + phase) * math.radians(8),
                                      math.cos(t * 0.3 + phase) * math.radians(6),
                                      w["root"].rotation_euler.z)
        w["root"].keyframe_insert("location", frame=f)
        w["root"].keyframe_insert("rotation_euler", frame=f)
        # Tail wave (signature whale swim)
        w["tail"].rotation_euler = (math.sin(t * 1.5 + phase) * math.radians(20), 0, 0)
        w["tail"].keyframe_insert("rotation_euler", frame=f)

# ============================================================
# ⭐⭐⭐ 800 PLANKTON drift Brownian + pulse (signature bioluminescent abyss)
# ============================================================
for p in plankton:
    phase = p["_phase"]; speed = p["_speed"]
    bx, by, bz = p["_base_x"], p["_base_y"], p["_base_z"]
    ax, ay, az = p["_amp_x"], p["_amp_y"], p["_amp_z"]
    for f in range(1, total_frames + 1, 4):
        t = (f - 1) / fps
        # Brownian drift
        x = bx + ax * math.sin(t * speed + phase)
        y = by + ay * math.cos(t * speed * 0.85 + phase)
        z = bz + az * math.sin(t * speed * 1.3 + phase * 1.5)
        p.location = (x, y, max(0.2, z))
        # Pulse scale (signature blink)
        sc = 1 + math.sin(t * 3.0 + phase) * 0.4
        p.scale = (sc, sc, sc)
        p.keyframe_insert("location", frame=f)
        p.keyframe_insert("scale", frame=f)

# 100 BUBBLES rise
for b in bubbles:
    phase = b["_phase"]; speed = b["_speed"]
    bx, by, bz = b["_base_x"], b["_base_y"], b["_base_z"]
    drift_x = b["_drift_x"]; drift_y = b["_drift_y"]
    for f in range(1, total_frames + 1, 4):
        t = (f - 1) / fps
        # Rise (faster than plankton)
        z = bz + (speed * t) % 22
        x = bx + drift_x * math.sin(t * 1.5 + phase)
        y = by + drift_y * math.cos(t * 1.3 + phase)
        b.location = (x, y, min(22, z))
        # Wobble shape
        sc = 1 + math.sin(t * 4.0 + phase) * 0.10
        b.scale = (sc, sc, sc)
        b.keyframe_insert("location", frame=f)
        b.keyframe_insert("scale", frame=f)

# ============ EXPORT ============
out_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "public", "_pbr_test")
out_dir = os.path.normpath(out_dir)
os.makedirs(out_dir, exist_ok=True)
out_glb = os.path.join(out_dir, "pbr_abyss_proc.glb")

bpy.ops.object.select_all(action='SELECT')
bpy.ops.export_scene.gltf(
    filepath=out_glb, export_format='GLB',
    export_animations=True, export_apply=False, export_yup=True, use_selection=False,
)
size_mb = os.path.getsize(out_glb) / (1024 * 1024)
print(f"[proc_bioluminescent_abyss] DONE → {out_glb} ({size_mb:.2f} MB)")
print("[proc_bioluminescent_abyss] ONE seabed + 5 god rays + 30 glowing algae + 20 fluorescent corals + 8 anemones + 4 tube worms + 12 jellyfish + 6 anglerfish + 3 giant squids + shipwreck + 2 whales + 800 PLANKTON + 100 BUBBLES")
print("⭐ FIXES: 1 ground + 800 plankton Brownian + pulse + 100 bubbles (signature bioluminescent abyss mandatory) ⭐")
