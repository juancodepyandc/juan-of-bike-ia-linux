"""
proc_volcanic_eruption_lava.py — 211e procédural AuroraIA (75e qualité)
Éruption volcan : ONE ground + 600 embers/lava qui MONTENT + cone volcan + 4 coulées lave + cendres + helico + 2 explorateurs
FIXES : 1 ground propre + lava embers particles thématiques obligatoires
"""
import bpy, bmesh, math, random, os

random.seed(0x107C4211)

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
M_SKY = mat("sky", (0.30, 0.10, 0.08, 1.0), 0.0, 0.7, emission=(0.45,0.15,0.10), emission_strength=2.0)
M_ASH_CLOUD = mat("ash", (0.15, 0.12, 0.10, 1.0), 0.0, 0.85, emission=(0.25,0.18,0.15), emission_strength=0.8, alpha=0.85)
M_VOLCANIC_ROCK = mat("rock", (0.18, 0.15, 0.12, 1.0), 0.2, 0.85)
M_VOLCANIC_LIT = mat("rock_lit", (0.55, 0.20, 0.10, 1.0), 0.0, 0.55, emission=(0.65,0.25,0.10), emission_strength=2.0)
M_LAVA = mat("lava", (1.0, 0.45, 0.10, 1.0), 0.0, 0.10, emission=(1.0,0.50,0.12), emission_strength=15.0)
M_LAVA_BRIGHT = mat("lava_b", (1.0, 0.75, 0.20, 1.0), 0.0, 0.05, emission=(1.0,0.80,0.25), emission_strength=22.0)
M_LAVA_DARK = mat("lava_d", (0.85, 0.30, 0.05, 1.0), 0.0, 0.20, emission=(0.85,0.32,0.06), emission_strength=8.0)
M_EMBER = mat("ember", (1.0, 0.55, 0.15, 1.0), 0.0, 0.05, emission=(1.0,0.60,0.18), emission_strength=18.0)
M_SPARK = mat("spark", (1.0, 0.90, 0.50, 1.0), 0.0, 0.05, emission=(1.0,0.92,0.55), emission_strength=25.0)
M_SMOKE = mat("smoke", (0.20, 0.18, 0.18, 1.0), 0.0, 0.85, emission=(0.25,0.22,0.22), emission_strength=0.5, alpha=0.5)

# Burnt trees
M_BURNT_TREE = mat("burnt", (0.08, 0.06, 0.05, 1.0), 0.0, 0.90, emission=(0.20,0.10,0.05), emission_strength=0.4)

# Explorers
M_SUIT = mat("suit", (0.85, 0.45, 0.10, 1.0), 0.0, 0.55, emission=(0.85,0.45,0.10), emission_strength=0.7)
M_SUIT_REFLECT = mat("suit_r", (0.95, 0.85, 0.30, 1.0), 0.5, 0.30, emission=(0.95,0.85,0.30), emission_strength=1.5)
M_HELMET_VISOR = mat("visor", (0.10, 0.10, 0.15, 1.0), 0.3, 0.10, emission=(0.30,0.45,0.60), emission_strength=2.5, alpha=0.7)
M_HELMET_SHELL = mat("helmet", (0.95, 0.95, 0.90, 1.0), 0.0, 0.45, emission=(0.85,0.85,0.80), emission_strength=0.5)

# Helicopter
M_HELI_BODY = mat("heli", (0.85, 0.55, 0.20, 1.0), 0.85, 0.30, emission=(0.78,0.50,0.18), emission_strength=0.6)
M_HELI_WINDOW = mat("heli_w", (0.30, 0.60, 0.85, 1.0), 0.3, 0.10, emission=(0.40,0.70,0.95), emission_strength=2.0, alpha=0.6)
M_HELI_BLADE = mat("heli_b", (0.20, 0.20, 0.22, 1.0), 0.5, 0.45)
M_HELI_LIGHT = mat("heli_l", (1.0, 0.30, 0.30, 1.0), 0.0, 0.10, emission=(1.0,0.35,0.35), emission_strength=12.0)

# ============ SKY + ASH CLOUDS ============
sky = smooth_sphere("sky", r=95, segs=32, rings=20, loc=(0,0,0), mat_=M_SKY, scale=(1,1,0.60))
sky.scale = (1,1,0.60)

# 12 ash clouds dark drift
ash_clouds = []
for i in range(12):
    a = (i / 12.0) * math.pi * 2
    rad = random.uniform(20, 38)
    cx, cy = rad*math.cos(a), rad*math.sin(a)
    cz = random.uniform(18, 30)
    c_e = empty(f"ash_e{i}", (cx, cy, cz))
    for j in range(6):
        smooth_sphere(f"ash{i}_{j}", r=random.uniform(2.5, 4.5),
                      loc=(random.uniform(-3,3), random.uniform(-2,2), random.uniform(-0.5,0.5)),
                      parent=c_e, mat_=M_ASH_CLOUD)
    c_e["_phase"] = random.uniform(0, math.pi*2)
    ash_clouds.append(c_e)

# ============ ONE clean volcanic ground (single rock plane) ============
ground = beveled_cube("ground", (90, 90, 0.5), bevel_offset=0.08, loc=(0, 0, -0.25), mat_=M_VOLCANIC_ROCK)

# 30 organic ROCKS scattered (3D, not flat sheets)
for i in range(30):
    a = random.uniform(0, math.pi*2)
    rad = random.uniform(8, 38)
    smooth_sphere(f"rock{i}", r=random.uniform(0.5, 1.8),
                  loc=(rad*math.cos(a), rad*math.sin(a), 0.3),
                  mat_=M_VOLCANIC_ROCK if random.random() < 0.7 else M_VOLCANIC_LIT,
                  scale=(random.uniform(0.8,1.4), random.uniform(0.8,1.4),
                         random.uniform(0.5,0.9))).rotation_euler = (random.uniform(-0.2, 0.2),
                                                                       random.uniform(-0.2, 0.2),
                                                                       random.uniform(0, math.pi*2))

# 15 small lava pools scattered (where flows reached)
for i in range(15):
    a = random.uniform(0, math.pi*2)
    rad = random.uniform(10, 32)
    pool = cyl(f"lava_pool{i}", r=random.uniform(0.4, 1.2), depth=0.08, segs=20,
              loc=(rad*math.cos(a), rad*math.sin(a), 0.10), mat_=M_LAVA)

# ============ GIANT VOLCANO central ============
volcano_e = empty("volcano", loc=(0, 8, 0))
# Cone body (8 segments height)
for i in range(8):
    r1 = 8 - i*0.85
    r2 = 7 - i*0.85
    h = 1.5
    seg = smooth_cone(f"vol_seg{i}", r1=r1, r2=r2, depth=h, segs=32,
                      loc=(0, 0, h/2 + i*h), parent=volcano_e,
                      mat_=M_VOLCANIC_ROCK if i % 2 == 0 else M_VOLCANIC_LIT)
# Top crater (open)
crater_top_e = empty("crater_top", (0, 0, 12), parent=volcano_e)
# Crater rim (ring of rocks)
for i in range(16):
    a = (i / 16.0) * math.pi * 2
    smooth_sphere(f"crater_rock{i}", r=random.uniform(0.30, 0.55),
                  loc=(2.2*math.cos(a), 2.2*math.sin(a), 0),
                  parent=crater_top_e, mat_=M_VOLCANIC_LIT)
# Crater glow (lava inside)
cyl("crater_glow", r=1.8, depth=0.3, segs=24,
    loc=(0, 0, 0), parent=crater_top_e, mat_=M_LAVA_BRIGHT)

# ============ 4 LAVA FLOWS descending from crater ============
lava_flows = []
for fi in range(4):
    a = (fi / 4.0) * math.pi * 2
    flow_e = empty(f"flow{fi}", (0, 8, 0))
    flow_e.rotation_euler = (0, 0, a)
    # 6 segments flowing down volcano slope
    for s in range(6):
        # Goes from crater (z=12) down to ground (z=0)
        t = (s+1) / 6.0
        sx = 0
        sy = 2.2 + t * 5.5
        sz = 12.0 - t * 12.0
        # Slight zig-zag
        sy += math.sin(t * math.pi * 2) * 0.5
        flow_seg = beveled_cube(f"flow{fi}_s{s}", (0.7 + s*0.1, 1.0, 0.20), bevel_offset=0.05,
                                loc=(sx, sy, sz), parent=flow_e,
                                mat_=M_LAVA_BRIGHT if s % 2 == 0 else M_LAVA)
        # Tilt to follow slope
        flow_seg.rotation_euler = (math.radians(-40 + t*30), 0, 0)
        flow_seg["_phase"] = s * 0.5
    lava_flows.append(flow_e)

# ============ 4 BURNT TREES (silhouettes) ============
for ti in range(4):
    a = (ti / 4.0) * math.pi * 2 + 0.5
    rad = random.uniform(22, 30)
    tx, ty = rad*math.cos(a), rad*math.sin(a)
    t_e = empty(f"burnt_tree{ti}", (tx, ty, 0))
    # Twisted trunk 4 segs
    for s in range(4):
        seg = cyl(f"burnt_t{ti}_{s}", r=0.30 - s*0.04, depth=1.5, segs=10,
                 loc=(0, 0, (s+0.5)*1.5), parent=t_e, mat_=M_BURNT_TREE)
        seg.rotation_euler = (math.radians(random.uniform(-10, 10)),
                              math.radians(random.uniform(-10, 10)), 0)
    # 4 dead branches twisted
    for j in range(4):
        ba = (j / 4.0) * math.pi * 2
        branch = cyl(f"burnt_br{ti}_{j}", r=0.08, depth=1.5, segs=8,
                    loc=(math.cos(ba)*0.5, math.sin(ba)*0.5, 5.5),
                    parent=t_e, mat_=M_BURNT_TREE)
        branch.rotation_euler = (math.radians(60), 0, ba)

# ============ 2 EXPLORERS in protective suits ============
def make_explorer(name, loc, facing=0):
    base = empty(name, loc)
    base.rotation_euler = (0, 0, facing)
    # Legs (heat suit)
    for side_idx, side in enumerate((-1, 1)):
        cyl(f"{name}_leg{side_idx}", r=0.14, depth=0.85, segs=10,
            loc=(side*0.15, 0, 0.42), parent=base, mat_=M_SUIT)
        # Reflective stripes on legs
        cyl(f"{name}_leg_stripe{side_idx}", r=0.145, depth=0.06, segs=10,
            loc=(side*0.15, 0, 0.30), parent=base, mat_=M_SUIT_REFLECT)
        # Boots
        beveled_cube(f"{name}_boot{side_idx}", (0.20, 0.30, 0.18), bevel_offset=0.04,
                     loc=(side*0.15, 0.04, 0.10), parent=base, mat_=M_VOLCANIC_ROCK)
    # Torso suit
    beveled_cube(f"{name}_torso", (0.55, 0.35, 0.90), bevel_offset=0.06,
                 loc=(0, 0, 1.30), parent=base, mat_=M_SUIT)
    # 2 reflective chest stripes
    for j in range(2):
        beveled_cube(f"{name}_t_stripe{j}", (0.58, 0.36, 0.08),
                     loc=(0, 0, 1.10 + j*0.40), parent=base, mat_=M_SUIT_REFLECT)
    # Backpack/tank
    beveled_cube(f"{name}_pack", (0.30, 0.20, 0.50), bevel_offset=0.04,
                 loc=(0, 0.25, 1.30), parent=base, mat_=M_SUIT)
    # 2 tank cylinders
    for side in (-1, 1):
        cyl(f"{name}_tank_{side}", r=0.08, depth=0.55, segs=12,
            loc=(side*0.08, 0.30, 1.30), parent=base, mat_=M_HELI_BODY)
    # Neck
    cyl(f"{name}_neck", r=0.10, depth=0.20, segs=12,
        loc=(0, 0, 1.85), parent=base, mat_=M_SUIT)
    # HELMET (spherical heat-resistant)
    head_e = empty(f"{name}_head_e", (0, 0, 2.10), parent=base)
    smooth_sphere(f"{name}_helmet", r=0.25, segs=22, rings=14, loc=(0, 0, 0),
                  parent=head_e, mat_=M_HELMET_SHELL)
    # VISOR (large dark glass émissif - protective)
    smooth_sphere(f"{name}_visor", r=0.22, loc=(0, -0.10, 0),
                  parent=head_e, mat_=M_HELMET_VISOR, scale=(1, 0.5, 0.85))
    # Antenna
    cyl(f"{name}_antenna", r=0.02, depth=0.20, segs=6,
        loc=(0, 0, 0.30), parent=head_e, mat_=M_VOLCANIC_ROCK)
    smooth_sphere(f"{name}_antenna_tip", r=0.03, loc=(0, 0, 0.40),
                  parent=head_e, mat_=M_HELI_LIGHT)
    # Helmet light front
    smooth_sphere(f"{name}_light", r=0.05, loc=(0, -0.20, 0.10),
                  parent=head_e, mat_=M_SPARK)
    # 2 arms (one holding instrument)
    arm_data = [(math.radians(-30), -10), (math.radians(-80), 20)]
    for side_idx, side in enumerate((-1, 1)):
        sh = empty(f"{name}_sh{side_idx}", (side*0.30, 0, 1.80), parent=base)
        rx, rz = arm_data[side_idx]
        sh.rotation_euler = (rx, 0, math.radians(side*-10 + rz))
        cyl(f"{name}_up{side_idx}", r=0.09, depth=0.40, segs=10,
            loc=(0, 0, -0.20), parent=sh, mat_=M_SUIT)
        cyl(f"{name}_fa{side_idx}", r=0.08, depth=0.38, segs=10,
            loc=(0, 0, -0.60), parent=sh, mat_=M_SUIT)
        # Glove
        smooth_sphere(f"{name}_glove{side_idx}", r=0.10, loc=(0, 0, -0.82),
                      parent=sh, mat_=M_VOLCANIC_ROCK)
    # Instrument (sample container) in right hand
    cyl(f"{name}_instr", r=0.06, depth=0.30, segs=12,
        loc=(0.45, -0.25, 1.20), parent=base, mat_=M_HELMET_SHELL)
    smooth_sphere(f"{name}_instr_top", r=0.07, loc=(0.45, -0.25, 1.40),
                  parent=base, mat_=M_LAVA)
    return {"root": base, "head_e": head_e}

explorers = []
exp_pos = [(-12, -10, 0, math.radians(45)),
           (-9, -12, 0, math.radians(30))]
for i, (ex, ey, ez, fac) in enumerate(exp_pos):
    e = make_explorer(f"exp{i}", (ex, ey, ez), facing=fac)
    explorers.append(e)

# ============ HELICOPTER ============
heli_e = empty("helicopter", loc=(-12, 12, 14))
heli_e.rotation_euler = (0, 0, math.radians(-30))
# Body main
smooth_sphere("heli_body", r=1.2, segs=22, rings=14, loc=(0, 0, 0),
              parent=heli_e, mat_=M_HELI_BODY, scale=(2.5, 1.0, 1.0))
# Cockpit windows (front)
smooth_sphere("heli_cockpit", r=0.85, loc=(1.5, 0, 0.15),
              parent=heli_e, mat_=M_HELI_WINDOW, scale=(1.3, 1.0, 0.9))
# Tail boom
cyl("heli_tail", r=0.18, depth=2.5, segs=12,
    loc=(-2.0, 0, 0.1), parent=heli_e, mat_=M_HELI_BODY).rotation_euler = (0, math.radians(90), 0)
# Tail fin vertical
beveled_cube("heli_fin", (0.06, 0.40, 0.65), bevel_offset=0.04,
             loc=(-3.0, 0, 0.45), parent=heli_e, mat_=M_HELI_BODY)
# Tail rotor (small spinning)
tail_rotor_e = empty("tail_rotor", (-3.15, 0.20, 0.15), parent=heli_e)
for i in range(2):
    a = i * math.pi
    beveled_cube(f"tail_rot{i}", (0.04, 0.35, 0.02),
                 loc=(0, 0.30*math.cos(a), 0.30*math.sin(a)),
                 parent=tail_rotor_e, mat_=M_HELI_BLADE)
# Main rotor (top, large spinning)
main_rotor_e = empty("main_rotor", (0, 0, 1.0), parent=heli_e)
# Hub
smooth_sphere("rotor_hub", r=0.15, loc=(0, 0, 0),
              parent=main_rotor_e, mat_=M_HELI_BLADE)
# 4 blades
for i in range(4):
    a = i * math.pi / 2
    blade = beveled_cube(f"main_blade{i}", (3.5, 0.20, 0.04), bevel_offset=0.02,
                        loc=(0, 0, 0), parent=main_rotor_e, mat_=M_HELI_BLADE)
    blade.rotation_euler = (0, 0, a)
# Landing skids
for side in (-1, 1):
    cyl(f"skid_{side}", r=0.04, depth=2.5, segs=10,
        loc=(0, side*0.60, -0.85), parent=heli_e, mat_=M_HELI_BLADE).rotation_euler = (0, math.radians(90), 0)
    # Support struts
    for sj in (-1, 1):
        cyl(f"strut_{side}_{sj}", r=0.03, depth=0.5, segs=8,
            loc=(sj*0.50, side*0.60, -0.55), parent=heli_e, mat_=M_HELI_BLADE).rotation_euler = (0, 0, math.radians(side*30))
# Red blinking light
smooth_sphere("heli_light", r=0.08, loc=(0, 0, -0.50),
              parent=heli_e, mat_=M_HELI_LIGHT)
# Searchlight beam (cone forward)
beam = smooth_cone("heli_beam", r1=0.20, r2=1.5, depth=6, segs=14,
                   loc=(2.5, 0, -0.6), parent=heli_e,
                   mat_=mat("beam", (1.0, 0.95, 0.65, 0.3), 0, 0.05,
                            emission=(1.0,0.95,0.65), emission_strength=3.0, alpha=0.3))
beam.rotation_euler = (math.radians(-30), math.radians(90), 0)

# ============================================================
# ⭐ 600 LAVA EMBERS qui MONTENT du volcan (PARTICULE THÉMATIQUE OBLIGATOIRE)
# ============================================================
lava_embers = []
for i in range(600):
    # Start near crater + scattered
    a = random.uniform(0, math.pi*2)
    rad = random.uniform(0.5, 8)
    # Most embers start near crater top (high)
    if i < 400:
        # Cluster near crater
        ex = math.cos(a) * rad * 0.5
        ey = 8 + math.sin(a) * rad * 0.5
        ez = 8 + random.uniform(0, 10)
    else:
        # Spread wider
        ex = math.cos(a) * random.uniform(5, 20)
        ey = math.sin(a) * random.uniform(5, 20)
        ez = random.uniform(1, 14)
    em = smooth_sphere(f"ember{i}", r=random.uniform(0.06, 0.14), segs=6, rings=5,
                      loc=(ex, ey, ez), mat_=M_EMBER if random.random() < 0.7 else M_SPARK)
    em["_phase"] = random.uniform(0, math.pi*2)
    em["_base_x"] = ex; em["_base_y"] = ey; em["_base_z"] = ez
    em["_speed_z"] = random.uniform(2.0, 5.0)  # rising fast (signature volcanic)
    em["_drift_x"] = random.uniform(-0.8, 0.8)
    em["_drift_y"] = random.uniform(-0.8, 0.8)
    lava_embers.append(em)

# ============ 100 SMOKE/ASH RISING from crater ============
smoke_rises = []
for i in range(100):
    a = random.uniform(0, math.pi*2)
    rad = random.uniform(0.5, 4)
    sx = math.cos(a) * rad
    sy = 8 + math.sin(a) * rad
    sz = random.uniform(12, 25)
    sm = smooth_sphere(f"smoke{i}", r=random.uniform(0.6, 1.4), segs=14, rings=10,
                      loc=(sx, sy, sz), mat_=M_SMOKE)
    sm["_phase"] = random.uniform(0, math.pi*2)
    sm["_base_x"] = sx; sm["_base_y"] = sy; sm["_base_z"] = sz
    sm["_speed_z"] = random.uniform(1.0, 2.5)
    smoke_rises.append(sm)

# ============ ANIMATION ============
fps = 30; duration_s = 6; total_frames = fps * duration_s

# Volcano rumble (subtle Z shake)
for f in range(1, total_frames + 1, 3):
    t = (f - 1) / fps
    volcano_e.location.z = math.sin(t * 4.0) * 0.04
    volcano_e.keyframe_insert("location", frame=f)

# Crater glow pulse
for f in range(1, total_frames + 1, 3):
    t = (f - 1) / fps
    s = 1 + math.sin(t * 3.0) * 0.15
    crater_top_e.scale = (s, s, s)
    crater_top_e.keyframe_insert("scale", frame=f)

# Lava flows pulse (waves of intensity flowing down)
for flow in lava_flows:
    for child in flow.children:
        if "_phase" in child.keys():
            phase = child["_phase"]
            for f in range(1, total_frames + 1, 4):
                t = (f - 1) / fps
                s = 1 + math.sin(t * 4.0 + phase) * 0.20
                child.scale = (s, s, s)
                child.keyframe_insert("scale", frame=f)

# Helicopter circles (orbit around volcano) + main rotor spin + tail rotor spin
for f in range(1, total_frames + 1, 3):
    t = (f - 1) / fps
    a = t * 0.5
    r = 15
    heli_e.location = (r * math.cos(a), 8 + r * math.sin(a), 14 + math.sin(t * 1.0) * 0.5)
    heli_e.rotation_euler = (math.radians(5), 0, a + math.pi/2)
    heli_e.keyframe_insert("location", frame=f)
    heli_e.keyframe_insert("rotation_euler", frame=f)
    # Main rotor spin fast
    main_rotor_e.rotation_euler = (0, 0, t * 30.0)
    main_rotor_e.keyframe_insert("rotation_euler", frame=f)
    # Tail rotor
    tail_rotor_e.rotation_euler = (t * 50.0, 0, 0)
    tail_rotor_e.keyframe_insert("rotation_euler", frame=f)

# Explorers walk + head turn
for ex in explorers:
    base_z = ex["root"].location.z
    phase = hash(ex["root"].name) % 100 * 0.05
    for f in range(1, total_frames + 1, 4):
        t = (f - 1) / fps
        ex["root"].location.z = base_z + math.sin(t * 1.5 + phase) * 0.04
        ex["root"].keyframe_insert("location", frame=f)
        ex["head_e"].rotation_euler = (math.sin(t * 0.8 + phase) * math.radians(8), 0,
                                         math.sin(t * 0.6 + phase) * math.radians(15))
        ex["head_e"].keyframe_insert("rotation_euler", frame=f)

# Ash clouds drift
for c_e in ash_clouds:
    phase = c_e["_phase"]
    bx, by = c_e.location.x, c_e.location.y
    for f in range(1, total_frames + 1, 8):
        t = (f - 1) / fps
        c_e.location = (bx + math.sin(t * 0.4 + phase) * 0.8,
                        by + math.cos(t * 0.3 + phase) * 0.8,
                        c_e.location.z + math.sin(t * 0.5 + phase) * 0.3)
        c_e.keyframe_insert("location", frame=f)

# ============================================================
# ⭐⭐⭐ 600 LAVA EMBERS qui MONTENT (signature volcanic eruption)
# ============================================================
for em in lava_embers:
    phase = em["_phase"]
    speed_z = em["_speed_z"]
    drift_x = em["_drift_x"]
    drift_y = em["_drift_y"]
    bx, by, bz = em["_base_x"], em["_base_y"], em["_base_z"]
    for f in range(1, total_frames + 1, 3):
        t = (f - 1) / fps
        # Continuous rise + drift (signature ember rising from eruption)
        z = bz + (speed_z * t) % 20
        x = bx + drift_x * math.sin(t * 2.0 + phase)
        y = by + drift_y * math.cos(t * 1.8 + phase)
        # Flicker scale
        s = 1 + math.sin(t * 5.0 + phase) * 0.4
        em.location = (x, y, z)
        em.scale = (s, s, s)
        em.keyframe_insert("location", frame=f)
        em.keyframe_insert("scale", frame=f)

# 100 smoke columns rise
for sm in smoke_rises:
    phase = sm["_phase"]
    speed_z = sm["_speed_z"]
    bx, by, bz = sm["_base_x"], sm["_base_y"], sm["_base_z"]
    for f in range(1, total_frames + 1, 6):
        t = (f - 1) / fps
        z = bz + (speed_z * t) % 18
        x = bx + math.sin(t * 0.5 + phase) * 0.8
        y = by + math.cos(t * 0.4 + phase) * 0.8
        s = 1 + math.sin(t * 0.8 + phase) * 0.2
        sm.location = (x, y, z)
        sm.scale = (s, s, s)
        sm.keyframe_insert("location", frame=f)
        sm.keyframe_insert("scale", frame=f)

# ============ EXPORT ============
out_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "public", "_pbr_test")
out_dir = os.path.normpath(out_dir)
os.makedirs(out_dir, exist_ok=True)
out_glb = os.path.join(out_dir, "pbr_volcano_lava_proc.glb")

bpy.ops.object.select_all(action='SELECT')
bpy.ops.export_scene.gltf(
    filepath=out_glb, export_format='GLB',
    export_animations=True, export_apply=False, export_yup=True, use_selection=False,
)
size_mb = os.path.getsize(out_glb) / (1024 * 1024)
print(f"[proc_volcanic_eruption_lava] DONE → {out_glb} ({size_mb:.2f} MB)")
print("[proc_volcanic_eruption_lava] ONE ground + 30 rocks + 15 lava pools + volcano cone + 4 lava flows + 4 burnt trees + 2 explorers + helicopter + 600 EMBERS RISING + 100 smoke + 12 ash clouds")
print("⭐ FIXES: 1 ground + 600 lava embers Z rise fast 2-5 m/s + drift XY (signature eruption mandatory) ⭐")
