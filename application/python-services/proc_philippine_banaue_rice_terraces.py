"""
proc_philippine_banaue_rice_terraces.py — 292e procédural AuroraIA (157e qualité)
Philippines Banaue rice terraces: signature Ifugao stepped terraces + 6 farmers salakot hats + 4 carabao water buffaloes + nipa huts + Philippines flag + 600 golden rice grains + 400 walking carabaos
FIXES : 1 ground green terraces + signature rice + carabaos
"""
import bpy, bmesh, math, random, os

random.seed(0x70AB292)

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

# Sky tropical dawn
M_SKY = mat("sky", (0.55, 0.72, 0.85, 1.0), 0.0, 0.7, emission=(0.55,0.70,0.82), emission_strength=1.8)
M_SKY_LOW = mat("sky_l", (0.95, 0.85, 0.65, 1.0), 0.0, 0.7, emission=(0.92,0.82,0.65), emission_strength=1.5)
M_SUN = mat("sun", (1.0, 0.92, 0.55, 1.0), 0.0, 0.1, emission=(1.0,0.92,0.55), emission_strength=15.0)
M_MIST = mat("mi", (0.92, 0.95, 0.92, 1.0), 0.0, 0.95, emission=(0.92,0.95,0.92), emission_strength=1.0, alpha=0.45)

# Rice terrace greens (signature multi-stage)
M_RICE_BRIGHT = mat("rb", (0.35, 0.78, 0.32, 1.0), 0.0, 0.55, emission=(0.32,0.75,0.30), emission_strength=0.5)
M_RICE_DARK = mat("rd", (0.20, 0.55, 0.25, 1.0), 0.0, 0.65)
M_RICE_GOLD = mat("rg", (0.85, 0.78, 0.30, 1.0), 0.0, 0.55, emission=(0.82,0.75,0.30), emission_strength=0.7)
M_RICE_YELLOW = mat("ry", (0.92, 0.85, 0.42, 1.0), 0.0, 0.55, emission=(0.88,0.82,0.42), emission_strength=0.6)
RICE_COLORS = [M_RICE_BRIGHT, M_RICE_DARK, M_RICE_GOLD, M_RICE_YELLOW]
M_PADDY_WATER = mat("pw", (0.55, 0.78, 0.65, 1.0), 0.3, 0.10, emission=(0.55,0.75,0.62), emission_strength=1.5, alpha=0.78)
M_PADDY_MUD = mat("pm", (0.45, 0.32, 0.20, 1.0), 0.0, 0.85)
M_WALL_STONE = mat("ws", (0.55, 0.50, 0.42, 1.0), 0.0, 0.92)

# Carabao water buffalo (signature)
M_CARABAO_GRAY = mat("cg", (0.42, 0.40, 0.38, 1.0), 0.0, 0.85, emission=(0.40,0.40,0.38), emission_strength=0.3)
M_CARABAO_DARK = mat("cgd", (0.22, 0.22, 0.20, 1.0), 0.0, 0.92)
M_CARABAO_BELLY = mat("cgb", (0.55, 0.50, 0.45, 1.0), 0.0, 0.85)
M_HORN_CURVED = mat("hc", (0.32, 0.28, 0.22, 1.0), 0.2, 0.55)

# Farmer
M_SKIN_TAN = mat("sk", (0.78, 0.55, 0.35, 1.0), 0.0, 0.55, emission=(0.75,0.55,0.35), emission_strength=0.3)
M_HAIR_BLACK = mat("hb", (0.10, 0.06, 0.05, 1.0), 0.0, 0.85)
M_SHIRT_WHITE = mat("sw", (0.92, 0.90, 0.82, 1.0), 0.0, 0.55, emission=(0.88,0.85,0.80), emission_strength=0.4)
M_PANTS_BROWN = mat("pb", (0.42, 0.28, 0.18, 1.0), 0.0, 0.75)
M_PANTS_BLACK = mat("pbk", (0.10, 0.10, 0.12, 1.0), 0.0, 0.75)

# Salakot (signature woven palm hat)
M_SALAKOT = mat("sl", (0.85, 0.72, 0.42, 1.0), 0.0, 0.75, emission=(0.82,0.70,0.42), emission_strength=0.4)
M_SALAKOT_DARK = mat("sld", (0.55, 0.42, 0.20, 1.0), 0.0, 0.85)

# Nipa hut (signature thatched bamboo)
M_BAMBOO = mat("bm", (0.65, 0.55, 0.32, 1.0), 0.0, 0.75, emission=(0.62,0.55,0.32), emission_strength=0.3)
M_BAMBOO_DARK = mat("bmd", (0.42, 0.32, 0.18, 1.0), 0.0, 0.85)
M_NIPA_THATCH = mat("nt", (0.78, 0.55, 0.20, 1.0), 0.0, 0.85)
M_NIPA_DARK = mat("ntd", (0.55, 0.38, 0.15, 1.0), 0.0, 0.92)

# Philippines flag colors (signature)
M_FLAG_BLUE = mat("fb", (0.10, 0.32, 0.62, 1.0), 0.0, 0.45, emission=(0.10,0.30,0.60), emission_strength=1.0)
M_FLAG_RED = mat("fr", (0.78, 0.18, 0.20, 1.0), 0.0, 0.45, emission=(0.75,0.18,0.20), emission_strength=1.0)
M_FLAG_WHITE = mat("fw", (0.95, 0.95, 0.92, 1.0), 0.0, 0.45, emission=(0.92,0.92,0.90), emission_strength=0.8)
M_FLAG_YELLOW = mat("fy", (1.0, 0.85, 0.20, 1.0), 0.0, 0.30, emission=(0.95,0.82,0.20), emission_strength=2.0)

# Eye
M_EYE = mat("ed", (0.05, 0.04, 0.04, 1.0), 0.0, 0.20)

# Rice grain particles
M_GRAIN_GOLD = mat("gg", (1.0, 0.85, 0.30, 1.0), 0.3, 0.30, emission=(0.95,0.82,0.30), emission_strength=2.5)
M_GRAIN_LIGHT = mat("gl", (1.0, 0.92, 0.55, 1.0), 0.2, 0.25, emission=(0.95,0.88,0.55), emission_strength=2.8)
M_GRAIN_DARK = mat("gd", (0.78, 0.65, 0.20, 1.0), 0.3, 0.40, emission=(0.75,0.62,0.20), emission_strength=2.0)
GRAIN_COLORS = [M_GRAIN_GOLD, M_GRAIN_LIGHT, M_GRAIN_DARK]

# Mountain
M_MOUNTAIN = mat("mt", (0.42, 0.55, 0.32, 1.0), 0.0, 0.85)
M_MOUNTAIN_DARK = mat("mtd", (0.28, 0.42, 0.22, 1.0), 0.0, 0.92)

# Tool
M_TOOL_WOOD = mat("tw", (0.55, 0.32, 0.15, 1.0), 0.0, 0.85)
M_TOOL_METAL = mat("tm", (0.55, 0.55, 0.58, 1.0), 0.7, 0.30)

# ============ SKY ============
sky = smooth_sphere("sky", r=320, segs=32, rings=20, loc=(0,0,0), mat_=M_SKY)
sky.scale = (1,1,0.6)
sky_l = smooth_sphere("sky_l", r=280, segs=28, rings=16, loc=(0,0,5), mat_=M_SKY_LOW)
sky_l.scale = (1,1,0.3)
sun = smooth_sphere("sun", r=10, segs=24, rings=18, loc=(-50, 110, 35), mat_=M_SUN)
for sh in range(3):
    smooth_sphere(f"sun_h{sh}", r=10 + sh*1.2, segs=24, rings=18, loc=(-50, 110, 35), mat_=M_SUN)
# Morning mist
for mi in range(15):
    mx = random.uniform(-120, 120); my = random.uniform(-100, 100); mz = random.uniform(10, 30)
    smooth_sphere(f"mst{mi}", r=random.uniform(2, 5), segs=12, rings=8,
                  loc=(mx, my, mz), mat_=M_MIST, scale=(2, 2, 0.5))

# ============ ONE clean stepped rice terraces ground (signature Ifugao) ============
ground = beveled_cube("ground", (260, 260, 0.5), bevel_offset=0.10, loc=(0, 0, -0.25), mat_=M_RICE_DARK)
# RICE TERRACES (signature stepped multiple levels going up mountain)
terrace_e = empty("terraces", (0, 30, 0))
n_terraces = 12
for ti in range(n_terraces):
    tz = ti * 1.2
    tw = 100 - ti * 5  # Wide at bottom narrow at top
    td = 80 - ti * 4
    tr_col = random.choice(RICE_COLORS)
    # Terrace level (flat top)
    beveled_cube(f"tr{ti}", (tw, td, 0.30), bevel_offset=0.06,
                 loc=(0, 0, tz + 0.15), parent=terrace_e, mat_=tr_col)
    # Water in paddy (signature reflective)
    if ti % 2 == 0:
        beveled_cube(f"tr{ti}_w", (tw - 1, td - 1, 0.10), bevel_offset=0.04,
                     loc=(0, 0, tz + 0.32), parent=terrace_e, mat_=M_PADDY_WATER)
    # Stone retaining wall (signature)
    cyl(f"tr{ti}_w1", r=0.30, depth=1.2, segs=10,
        loc=(-tw/2 + 0.30, 0, tz + 0.60), parent=terrace_e, mat_=M_WALL_STONE)
    cyl(f"tr{ti}_w2", r=0.30, depth=1.2, segs=10,
        loc=(tw/2 - 0.30, 0, tz + 0.60), parent=terrace_e, mat_=M_WALL_STONE)
    # Front stone wall
    beveled_cube(f"tr{ti}_fw", (tw, 0.30, 1.0), bevel_offset=0.06,
                 loc=(0, td/2 - 0.15, tz + 0.50), parent=terrace_e, mat_=M_WALL_STONE)
    # Rice stalks on terrace
    if ti < 8:
        for rsi in range(int(tw / 4)):
            for rsj in range(int(td / 5)):
                rsx = -tw/2 + 2 + rsi * 4
                rsy = -td/2 + 2 + rsj * 5
                cyl(f"tr{ti}_rs{rsi}_{rsj}", r=0.025, depth=0.45, segs=4,
                    loc=(rsx, rsy, tz + 0.55),
                    parent=terrace_e, mat_=M_RICE_GOLD if ti % 3 == 2 else M_RICE_BRIGHT)
# Mountain backdrop
def make_mountain(name, loc, height, base_radius):
    base = empty(name, loc)
    n_layers = int(height / 4)
    for li in range(n_layers):
        lz = li * 4
        lr1 = base_radius * (1 - li / n_layers * 0.85)
        lr2 = base_radius * (1 - (li+1) / n_layers * 0.85)
        smooth_cone(f"{name}_l{li}", r1=lr1, r2=lr2, depth=4.5, segs=18,
                    loc=(0, 0, lz + 2.25), parent=base,
                    mat_=M_MOUNTAIN_DARK if li < n_layers//2 else M_MOUNTAIN)
    return base

make_mountain("mt1", (0, 90, 0), 35, 12)
make_mountain("mt2", (-50, 80, 0), 30, 10)
make_mountain("mt3", (50, 85, 0), 32, 11)

# ============ 4 NIPA HUTS (signature bamboo + thatch) ============
def make_nipa_hut(name, loc, scale=1.0):
    base = empty(name, loc)
    # ELEVATED ON STILTS (signature)
    for si in range(4):
        sa = (si / 4.0) * math.pi * 2 + math.pi/4
        cyl(f"{name}_st{si}", r=0.12, depth=1.5, segs=10,
            loc=(math.cos(sa)*1.5, math.sin(sa)*1.5, 0.75), parent=base, mat_=M_BAMBOO)
    # Floor platform
    beveled_cube(f"{name}_pl", (3.5, 3.5, 0.20), bevel_offset=0.06, loc=(0, 0, 1.55),
                 parent=base, mat_=M_BAMBOO)
    # Bamboo wall (signature woven bamboo)
    beveled_cube(f"{name}_w", (3, 3, 1.8), bevel_offset=0.10, loc=(0, 0, 2.55),
                 parent=base, mat_=M_BAMBOO)
    # Bamboo wall lines (decorative)
    for wbi in range(10):
        wby = -1.45 + wbi * 0.3
        beveled_cube(f"{name}_wb{wbi}", (3.05, 0.04, 0.04), bevel_offset=0.005,
                     loc=(0, -1.55, 1.8 + wbi*0.20), parent=base, mat_=M_BAMBOO_DARK)
    # NIPA THATCHED PYRAMID ROOF (signature steep)
    roof_e = empty(f"{name}_re", (0, 0, 3.5), parent=base)
    smooth_cone(f"{name}_r", r1=2.5, r2=0.05, depth=2.2, segs=4, loc=(0, 0, 1.0),
                parent=roof_e, mat_=M_NIPA_THATCH).rotation_euler = (0, 0, math.radians(45))
    # Thatch tufts
    for ti_t in range(30):
        ta = random.uniform(0, math.pi*2); tr = random.uniform(0.3, 2.3)
        smooth_sphere(f"{name}_t{ti_t}", r=random.uniform(0.10, 0.18), segs=10, rings=6,
                      loc=(math.cos(ta)*tr, math.sin(ta)*tr, random.uniform(0.5, 1.8)),
                      parent=roof_e, mat_=M_NIPA_DARK if ti_t % 2 else M_NIPA_THATCH, scale=(1.2, 1.2, 0.7))
    # Door + ladder (signature)
    beveled_cube(f"{name}_d", (0.7, 0.05, 1.3), bevel_offset=0.04,
                 loc=(0, -1.55, 2.20), parent=base, mat_=M_BAMBOO_DARK)
    # Ladder
    cyl(f"{name}_ld_p1", r=0.04, depth=1.6, segs=6,
        loc=(-0.25, -1.65, 0.80), parent=base, mat_=M_BAMBOO)
    cyl(f"{name}_ld_p2", r=0.04, depth=1.6, segs=6,
        loc=(0.25, -1.65, 0.80), parent=base, mat_=M_BAMBOO)
    for ri_l in range(5):
        cyl(f"{name}_ld_r{ri_l}", r=0.03, depth=0.50, segs=6,
            loc=(0, -1.65, 0.3 + ri_l*0.25), parent=base, mat_=M_BAMBOO).rotation_euler = (0, math.radians(90), 0)
    # Window
    for side in (-1, 1):
        beveled_cube(f"{name}_wi{side}", (0.8, 0.05, 0.7), bevel_offset=0.04,
                     loc=(side*1.55, 0, 2.6), parent=base, mat_=M_BAMBOO_DARK)
    return base

for i, (hx, hy) in enumerate([(-40, -45), (-15, -50), (15, -50), (40, -45)]):
    make_nipa_hut(f"nh{i}", (hx, hy, 0))

# ============ 4 CARABAO WATER BUFFALOES (signature) ============
def make_carabao(name, loc, scale=1.0, facing=0):
    base = empty(name, loc)
    base.rotation_euler = (0, 0, facing)
    # Body massive
    smooth_sphere(f"{name}_bo", r=0.85, segs=14, rings=12, loc=(0, 0, 1.25),
                  parent=base, mat_=M_CARABAO_GRAY, scale=(1.7, 0.95, 0.85))
    # Belly lighter
    smooth_sphere(f"{name}_be", r=0.80, segs=12, rings=10, loc=(0, 0, 0.95),
                  parent=base, mat_=M_CARABAO_BELLY, scale=(1.6, 0.95, 0.55))
    # Head wide
    head_c_e = empty(f"{name}_he", (1.20, 0, 1.45), parent=base)
    head_c_e.rotation_euler = (0, math.radians(-15), 0)
    smooth_sphere(f"{name}_h", r=0.42, segs=14, rings=12, loc=(0, 0, 0),
                  parent=head_c_e, mat_=M_CARABAO_DARK, scale=(1.4, 1.0, 0.95))
    # Snout
    smooth_sphere(f"{name}_sn", r=0.25, segs=12, rings=10, loc=(0.30, 0, -0.15),
                  parent=head_c_e, mat_=M_CARABAO_BELLY)
    # MASSIVE CURVED HORNS (signature)
    for side in (-1, 1):
        horn_e = empty(f"{name}_hn{side}_e", (-0.10, side*0.28, 0.25), parent=head_c_e)
        horn_e.rotation_euler = (math.radians(-side*15), math.radians(side*70), 0)
        # Long curved horn (8 segments)
        for hi in range(8):
            ha = (hi / 8.0) * math.pi * 0.6
            r_b = 0.08 - hi * 0.008
            cyl(f"{name}_hn{side}_{hi}", r=r_b, depth=0.20, segs=10,
                loc=(math.sin(ha)*0.10, 0, math.cos(ha)*0.10 + hi*0.18),
                parent=horn_e, mat_=M_HORN_CURVED)
        # Horn tip
        smooth_cone(f"{name}_hnt{side}", r1=0.04, r2=0.01, depth=0.15, segs=8,
                    loc=(0.5, 0, 1.4), parent=horn_e, mat_=M_HORN_CURVED)
    # Ears
    for side in (-1, 1):
        smooth_sphere(f"{name}_er{side}", r=0.10, segs=10, rings=8,
                      loc=(-0.10, side*0.30, 0.15), parent=head_c_e,
                      mat_=M_CARABAO_GRAY, scale=(0.4, 1.0, 1.3))
    # Eyes
    for side in (-1, 1):
        smooth_sphere(f"{name}_ey{side}", r=0.05, loc=(0.08, side*0.18, 0.08),
                      parent=head_c_e, mat_=M_EYE)
    # 4 stocky legs
    for li, (lx_c, ly_c) in enumerate([(0.75, 0.40), (0.75, -0.40), (-0.75, 0.40), (-0.75, -0.40)]):
        leg_e = empty(f"{name}_le{li}", (lx_c, ly_c, 0.85), parent=base)
        cyl(f"{name}_ul{li}", r=0.18, depth=0.50, segs=10, loc=(0, 0, -0.25),
            parent=leg_e, mat_=M_CARABAO_GRAY)
        cyl(f"{name}_ll{li}", r=0.16, depth=0.40, segs=10, loc=(0, 0, -0.70),
            parent=leg_e, mat_=M_CARABAO_GRAY)
        # Hoof
        cyl(f"{name}_hf{li}", r=0.18, depth=0.10, segs=10, loc=(0, 0, -0.95),
            parent=leg_e, mat_=M_HORN_CURVED)
    # Tail with tuft
    tail_e = empty(f"{name}_te", (-1.40, 0, 1.30), parent=base)
    tail_e.rotation_euler = (0, math.radians(100), 0)
    for ti in range(5):
        cyl(f"{name}_t{ti}", r=0.06 - ti*0.005, depth=0.15, segs=8,
            loc=(0, 0, ti*0.15), parent=tail_e, mat_=M_CARABAO_GRAY)
    smooth_sphere(f"{name}_tt", r=0.12, loc=(0, 0, 0.85),
                  parent=tail_e, mat_=M_CARABAO_DARK)
    base["_phase"] = random.uniform(0, math.pi*2)
    return {"root": base, "he": head_c_e}

carabaos = []
carabao_pos = [(-25, -25, math.radians(30)), (-5, -28, math.radians(-15)),
                (15, -25, math.radians(20)), (30, -28, math.radians(-30))]
for i, (cx, cy, fac) in enumerate(carabao_pos):
    c = make_carabao(f"cb{i}", (cx, cy, 0), facing=fac)
    carabaos.append(c)

# ============ 6 FARMERS (signature salakot hat) ============
def make_farmer(name, loc, scale=1.0, facing=0):
    base = empty(name, loc)
    base.rotation_euler = (0, 0, facing)
    # White shirt
    smooth_cone(f"{name}_sh", r1=0.30, r2=0.32, depth=0.7, segs=14, loc=(0, 0, 1.30),
                parent=base, mat_=M_SHIRT_WHITE)
    # Rolled up sleeves (signature)
    for side in (-1, 1):
        cyl(f"{name}_rs{side}", r=0.10, depth=0.15, segs=10,
            loc=(side*0.30, 0, 1.55), parent=base, mat_=M_SHIRT_WHITE)
    # Pants
    pants_col = random.choice([M_PANTS_BROWN, M_PANTS_BLACK])
    for side in (-1, 1):
        cyl(f"{name}_p{side}", r=0.11, depth=0.85, segs=10,
            loc=(side*0.13, 0, 0.45), parent=base, mat_=pants_col)
    # Bare feet (signature working in paddies)
    for side in (-1, 1):
        beveled_cube(f"{name}_f{side}", (0.10, 0.20, 0.05), bevel_offset=0.01,
                     loc=(side*0.13, 0.04, 0.03), parent=base, mat_=M_SKIN_TAN)
    # Arms
    for side_idx, side in enumerate((-1, 1)):
        sh_a = empty(f"{name}_a{side_idx}", (side*0.30, 0, 1.55), parent=base)
        sh_a.rotation_euler = (math.radians(-70), 0, math.radians(side*20))
        cyl(f"{name}_ua{side_idx}", r=0.07, depth=0.35, segs=10, loc=(0, 0, -0.18),
            parent=sh_a, mat_=M_SHIRT_WHITE)
        cyl(f"{name}_fa{side_idx}", r=0.06, depth=0.30, segs=10, loc=(0, 0, -0.48),
            parent=sh_a, mat_=M_SKIN_TAN)
    # TOOL (sickle or stick - signature)
    tool_e = empty(f"{name}_tl", (0.30, -0.10, 0.50), parent=base)
    tool_e.rotation_euler = (math.radians(-30), 0, math.radians(-15))
    cyl(f"{name}_tl_p", r=0.025, depth=1.5, segs=8, loc=(0, 0, 0),
        parent=tool_e, mat_=M_TOOL_WOOD)
    # Curved blade
    cyl(f"{name}_tl_b", r=0.02, depth=0.25, segs=8, loc=(0.10, 0, 0.75),
        parent=tool_e, mat_=M_TOOL_METAL).rotation_euler = (0, math.radians(70), 0)
    # Head
    head_f_e = empty(f"{name}_he", (0, 0, 1.95), parent=base)
    smooth_sphere(f"{name}_h", r=0.17, segs=18, rings=14, loc=(0, 0, 0),
                  parent=head_f_e, mat_=M_SKIN_TAN)
    # Hair
    for hi in range(10):
        ha = random.uniform(0, math.pi*2)
        cyl(f"{name}_hr{hi}", r=0.04, depth=0.06, segs=6,
            loc=(math.cos(ha)*0.12, math.sin(ha)*0.10, 0.10),
            parent=head_f_e, mat_=M_HAIR_BLACK)
    # Eyes
    for side in (-1, 1):
        smooth_sphere(f"{name}_ey{side}", r=0.025, loc=(side*0.06, -0.15, 0.03),
                      parent=head_f_e, mat_=M_EYE)
    # SALAKOT HAT (signature wide woven cone)
    hat_e = empty(f"{name}_ha", (0, 0, 0.18), parent=head_f_e)
    # Cone shape
    smooth_cone(f"{name}_ha_c", r1=0.40, r2=0.05, depth=0.30, segs=14, loc=(0, 0, 0.15),
                parent=hat_e, mat_=M_SALAKOT)
    # Brim
    cyl(f"{name}_ha_b", r=0.42, depth=0.03, segs=18, loc=(0, 0, 0),
        parent=hat_e, mat_=M_SALAKOT_DARK)
    # Strap
    cyl(f"{name}_ha_st", r=0.02, depth=0.20, segs=6, loc=(0, 0.10, 0),
        parent=hat_e, mat_=M_TOOL_WOOD)
    # Decorative point on top (signature)
    cyl(f"{name}_ha_p", r=0.04, depth=0.10, segs=8, loc=(0, 0, 0.35),
        parent=hat_e, mat_=M_SALAKOT_DARK)
    base["_phase"] = random.uniform(0, math.pi*2)
    return {"root": base, "he": head_f_e}

farmers = []
farmer_pos = [(-30, 5, math.radians(45)), (-15, 8, math.radians(0)),
               (0, 10, math.radians(-15)), (15, 8, math.radians(20)),
               (30, 5, math.radians(-30)), (-10, -5, math.radians(60))]
for i, (fx, fy, fac) in enumerate(farmer_pos):
    f = make_farmer(f"fm{i}", (fx, fy, 0), facing=fac)
    farmers.append(f)

# ============ PHILIPPINES FLAG (signature) ============
flag_e = empty("flag", (-55, -45, 0))
cyl("fl_p", r=0.10, depth=12, segs=10, loc=(0, 0, 6), parent=flag_e, mat_=M_BAMBOO_DARK)
# White triangle (left signature)
triangle_e = empty("fl_tr", (0.50, -0.06, 10.5), parent=flag_e)
for ti_f in range(8):
    ti_t = ti_f / 8.0
    tw_f = 1.3 * (1 - ti_t)
    beveled_cube(f"fl_tr_t{ti_f}", (tw_f, 0.05, 0.30), bevel_offset=0.04,
                 loc=(0, 0, (ti_f - 4) * 0.30), parent=triangle_e, mat_=M_FLAG_WHITE)
# Blue stripe top
beveled_cube("fl_b", (2.7, 0.05, 1.25), bevel_offset=0.06, loc=(2.85, 0, 11.10),
             parent=flag_e, mat_=M_FLAG_BLUE)
# Red stripe bottom
beveled_cube("fl_r", (2.7, 0.05, 1.25), bevel_offset=0.06, loc=(2.85, 0, 9.85),
             parent=flag_e, mat_=M_FLAG_RED)
# 8 rays sun in triangle (signature)
sun_e = empty("fl_sun", (0.50, -0.07, 10.5), parent=flag_e)
smooth_sphere("fl_sun_c", r=0.15, loc=(0, 0, 0), parent=sun_e, mat_=M_FLAG_YELLOW)
# 8 rays
for ri in range(8):
    rang = (ri / 8.0) * math.pi * 2
    beveled_cube(f"fl_sun_r{ri}", (0.05, 0.04, 0.25), bevel_offset=0.005,
                 loc=(math.cos(rang)*0.25, 0, math.sin(rang)*0.25),
                 parent=sun_e, mat_=M_FLAG_YELLOW).rotation_euler = (0, rang, 0)
# 3 stars at corners of triangle
for si_st, (sx_st, sz_st) in enumerate([(0.30, 0.95), (0.30, -0.95), (-0.50, 0)]):
    star_se = empty(f"fl_st{si_st}", (0.50 + sx_st, -0.07, 10.5 + sz_st), parent=flag_e)
    for sp in range(5):
        spa = (sp / 5.0) * math.pi * 2 + math.pi/2
        beveled_cube(f"fl_st{si_st}_p{sp}", (0.025, 0.04, 0.10), bevel_offset=0.005,
                     loc=(math.cos(spa)*0.06, 0, math.sin(spa)*0.06),
                     parent=star_se, mat_=M_FLAG_YELLOW).rotation_euler = (spa - math.pi/2, 0, 0)
    smooth_sphere(f"fl_st{si_st}_c", r=0.035, loc=(0, 0, 0), parent=star_se, mat_=M_FLAG_YELLOW)
flag_e["_phase"] = 0

# ============================================================
# 600 RICE GRAINS + 400 WALKING CARABAOS (PARTICULES SIGNATURES)
# ============================================================
grains = []
for i in range(600):
    px = random.uniform(-100, 100)
    py = random.uniform(-100, 100)
    pz = random.uniform(2, 25)
    g_col = random.choice(GRAIN_COLORS)
    # Grain shape (elongated oval)
    g = smooth_sphere(f"gr{i}", r=0.08, segs=8, rings=6, loc=(px, py, pz),
                     mat_=g_col, scale=(1, 0.4, 0.4))
    g["_phase"] = random.uniform(0, math.pi*2)
    g["_base_x"] = px; g["_base_y"] = py; g["_base_z"] = pz
    g["_amp_x"] = random.uniform(0.5, 1.5)
    g["_amp_y"] = random.uniform(0.5, 1.5)
    g["_amp_z"] = random.uniform(0.4, 1.0)
    g["_speed"] = random.uniform(0.5, 1.2)
    grains.append(g)

# 400 mini carabaos
mini_carabaos = []
for i in range(400):
    px = random.uniform(-100, 100)
    py = random.uniform(-100, 100)
    pz = 0.6
    mc_e = empty(f"mc{i}", (px, py, pz))
    # Body
    smooth_sphere(f"mc{i}_bo", r=0.25, segs=10, rings=8, loc=(0, 0, 0),
                  parent=mc_e, mat_=M_CARABAO_GRAY, scale=(1.6, 0.85, 0.85))
    # Head
    smooth_sphere(f"mc{i}_h", r=0.13, segs=10, rings=8, loc=(0.30, 0, 0.10),
                  parent=mc_e, mat_=M_CARABAO_DARK, scale=(1.3, 0.95, 0.85))
    # Horns (simplified)
    for side in (-1, 1):
        cyl(f"mc{i}_hn{side}", r=0.025, depth=0.20, segs=6,
            loc=(0.20, side*0.10, 0.20), parent=mc_e, mat_=M_HORN_CURVED).rotation_euler = (0, 0, math.radians(side*45))
    # Legs
    for side in (-1, 1):
        for fr in (-1, 1):
            cyl(f"mc{i}_l{side}_{fr}", r=0.05, depth=0.30, segs=6,
                loc=(fr*0.18, side*0.12, -0.15), parent=mc_e, mat_=M_CARABAO_GRAY)
    mc_e["_phase"] = random.uniform(0, math.pi*2)
    mc_e["_base_x"] = px; mc_e["_base_y"] = py
    mc_e["_speed"] = random.uniform(0.3, 0.6)
    mc_e["_direction"] = random.uniform(0, math.pi*2)
    mini_carabaos.append(mc_e)

# ============ ANIMATION ============
fps = 30; duration_s = 6; total_frames = fps * duration_s

# Carabaos sway/walk
for c in carabaos:
    phase = c["root"]["_phase"]
    for f in range(1, total_frames + 1, 4):
        t = (f - 1) / fps
        c["root"].rotation_euler = (math.sin(t * 1.0 + phase) * math.radians(2), 0,
                                     c["root"].rotation_euler.z)
        c["root"].location.z = abs(math.sin(t * 1.5 + phase)) * 0.05
        c["root"].keyframe_insert("rotation_euler", frame=f)
        c["root"].keyframe_insert("location", frame=f)
        c["he"].rotation_euler = (0, math.radians(-15) + math.sin(t * 1.0 + phase) * math.radians(5),
                                   math.cos(t * 0.8 + phase) * math.radians(10))
        c["he"].keyframe_insert("rotation_euler", frame=f)

# Farmers work
for fm in farmers:
    phase = fm["root"]["_phase"]
    for f in range(1, total_frames + 1, 3):
        t = (f - 1) / fps
        fm["root"].rotation_euler = (math.sin(t * 2.0 + phase) * math.radians(8), 0,
                                       fm["root"].rotation_euler.z + math.sin(t * 1.5 + phase) * math.radians(5))
        fm["root"].keyframe_insert("rotation_euler", frame=f)
        fm["he"].rotation_euler = (math.sin(t * 2.0 + phase) * math.radians(10), 0, 0)
        fm["he"].keyframe_insert("rotation_euler", frame=f)

# Flag wave
for f in range(1, total_frames + 1, 5):
    t = (f - 1) / fps
    flag_e.rotation_euler = (0, 0, math.sin(t * 1.5) * math.radians(12))
    flag_e.keyframe_insert("rotation_euler", frame=f)

# 600 rice grains float multi-axis
for g in grains:
    phase = g["_phase"]; speed = g["_speed"]
    bx, by, bz = g["_base_x"], g["_base_y"], g["_base_z"]
    ax, ay, az = g["_amp_x"], g["_amp_y"], g["_amp_z"]
    for f in range(1, total_frames + 1, 4):
        t = (f - 1) / fps
        x = bx + ax * math.sin(t * speed + phase)
        y = by + ay * math.cos(t * speed * 0.9 + phase)
        z = bz + az * math.sin(t * speed * 1.2 + phase) + t * 0.4
        g.location = (x, y, z)
        g.rotation_euler = (math.sin(t * 2.0 + phase) * math.radians(20), 0,
                             t * 1.0 + phase)
        g.keyframe_insert("location", frame=f)
        g.keyframe_insert("rotation_euler", frame=f)

# 400 mini carabaos walk
for mc in mini_carabaos:
    phase = mc["_phase"]; speed = mc["_speed"]; direction = mc["_direction"]
    bx, by = mc["_base_x"], mc["_base_y"]
    for f in range(1, total_frames + 1, 4):
        t = (f - 1) / fps
        x = bx + math.cos(direction) * t * speed
        y = by + math.sin(direction) * t * speed
        z = 0.6 + abs(math.sin(t * 3.0 + phase)) * 0.05
        mc.location = (x, y, z)
        mc.rotation_euler = (math.sin(t * 3.0 + phase) * math.radians(2), 0, direction)
        mc.keyframe_insert("location", frame=f)
        mc.keyframe_insert("rotation_euler", frame=f)

# ============ EXPORT ============
out_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "public", "_pbr_test")
out_dir = os.path.normpath(out_dir)
os.makedirs(out_dir, exist_ok=True)
out_glb = os.path.join(out_dir, "pbr_philippines_proc.glb")

bpy.ops.object.select_all(action='SELECT')
bpy.ops.export_scene.gltf(
    filepath=out_glb, export_format='GLB',
    export_animations=True, export_apply=False, export_yup=True, use_selection=False,
)
size_mb = os.path.getsize(out_glb) / (1024 * 1024)
print(f"[proc_philippine_banaue_rice_terraces] DONE → {out_glb} ({size_mb:.2f} MB)")
print("Philippines Banaue: signature Ifugao rice terraces (12 stepped levels going up mountain with paddy water reflections + stone retaining walls + rice stalks) + 3 mountain peaks + morning mist + 4 nipa huts elevated on bamboo stilts with thatched pyramidal roofs + ladders + woven bamboo walls + 4 carabao water buffaloes (signature gray + curved horns + droopy ears + 4 stocky legs + tail tuft) + 6 farmers (signature salakot conical woven hats + white shirts + sickles + bare feet + rolled sleeves) + Philippines flag (white triangle + 8-ray sun + 3 stars + blue/red stripes) + 600 rice grains floating + 400 mini carabaos walking signature")
print("🌾 FIXES: 1 green terraces ground + 600 rice grains + 400 walking carabaos signature 🌾")
