"""
proc_caribbean_jamaica_reggae_beach.py — 265e procédural AuroraIA (130e qualité)
Jamaica Caribbean reggae beach: 8 palms + reggae stage + 4 rastas dreadlocks + 4 musicians + Jamaica flag + fishing boats + 600 starfish + 400 ocean bubbles
FIXES : 1 ground + 600 multicolor starfish + 400 bubbles (signature)
"""
import bpy, bmesh, math, random, os

random.seed(0x70AB265)

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

# Sunset sky tropical
M_SKY = mat("sky", (1.0, 0.55, 0.35, 1.0), 0.0, 0.7, emission=(1.0,0.55,0.35), emission_strength=2.2)
M_SKY_PURPLE = mat("sky_p", (0.55, 0.30, 0.65, 1.0), 0.0, 0.7, emission=(0.55,0.30,0.65), emission_strength=1.8)
M_SUN = mat("sun", (1.0, 0.75, 0.25, 1.0), 0.0, 0.1, emission=(1.0,0.75,0.25), emission_strength=20.0)

# Sand
M_SAND_GOLD = mat("sand", (0.95, 0.82, 0.55, 1.0), 0.0, 0.65, emission=(0.88,0.78,0.55), emission_strength=0.5)
M_SAND_DARK = mat("sand_d", (0.65, 0.55, 0.32, 1.0), 0.0, 0.75)

# Ocean turquoise
M_OCEAN = mat("ocean", (0.18, 0.78, 0.85, 1.0), 0.1, 0.20, emission=(0.18,0.75,0.82), emission_strength=1.8, alpha=0.78)
M_OCEAN_DEEP = mat("ocean_d", (0.10, 0.55, 0.72, 1.0), 0.1, 0.25, alpha=0.85)
M_FOAM = mat("foam", (0.95, 0.95, 0.92, 1.0), 0.0, 0.30, emission=(0.92,0.92,0.90), emission_strength=1.8, alpha=0.65)

# Palm
M_PALM_TRUNK = mat("pt", (0.55, 0.32, 0.15, 1.0), 0.0, 0.85, emission=(0.50,0.30,0.15), emission_strength=0.3)
M_PALM_LEAF = mat("pl", (0.30, 0.62, 0.25, 1.0), 0.0, 0.55, emission=(0.28,0.58,0.25), emission_strength=0.5)
M_COCONUT = mat("co", (0.32, 0.20, 0.10, 1.0), 0.0, 0.85)

# Jamaica colors signature
M_JAM_GREEN = mat("jg", (0.10, 0.55, 0.20, 1.0), 0.0, 0.55, emission=(0.10,0.52,0.20), emission_strength=1.0)
M_JAM_YELLOW = mat("jy", (1.0, 0.92, 0.20, 1.0), 0.0, 0.55, emission=(0.95,0.88,0.20), emission_strength=1.5)
M_JAM_BLACK = mat("jb", (0.05, 0.05, 0.05, 1.0), 0.0, 0.65)
M_JAM_RED = mat("jr", (0.85, 0.18, 0.18, 1.0), 0.0, 0.55, emission=(0.80,0.18,0.18), emission_strength=0.7)

# Skin
M_SKIN_DARK = mat("sd", (0.42, 0.25, 0.15, 1.0), 0.0, 0.55, emission=(0.40,0.25,0.15), emission_strength=0.4)

# Hair dreadlocks
M_DREAD_BLACK = mat("db", (0.18, 0.10, 0.06, 1.0), 0.0, 0.85)
M_DREAD_BROWN = mat("db_br", (0.32, 0.18, 0.08, 1.0), 0.0, 0.85)

# Stage
M_STAGE_WOOD = mat("sw", (0.55, 0.32, 0.15, 1.0), 0.0, 0.55, emission=(0.50,0.30,0.15), emission_strength=0.5)
M_STAGE_DARK = mat("sw_d", (0.28, 0.16, 0.08, 1.0), 0.0, 0.75)

# Instruments
M_GUITAR_WOOD = mat("gw", (0.55, 0.30, 0.15, 1.0), 0.0, 0.45, emission=(0.50,0.30,0.15), emission_strength=0.5)
M_DRUM_RED = mat("drr", (0.85, 0.18, 0.15, 1.0), 0.0, 0.55, emission=(0.80,0.18,0.15), emission_strength=0.5)
M_DRUM_SKIN = mat("drs", (0.92, 0.78, 0.55, 1.0), 0.0, 0.55, emission=(0.85,0.72,0.52), emission_strength=0.5)
M_STRING = mat("st", (0.85, 0.85, 0.85, 1.0), 0.5, 0.30)

# Boat
M_BOAT_RED = mat("br", (0.85, 0.20, 0.20, 1.0), 0.0, 0.65, emission=(0.80,0.20,0.20), emission_strength=0.7)
M_BOAT_BLUE = mat("bb", (0.18, 0.42, 0.78, 1.0), 0.0, 0.65, emission=(0.18,0.42,0.75), emission_strength=0.7)
M_BOAT_YELLOW = mat("by", (0.95, 0.78, 0.20, 1.0), 0.0, 0.55, emission=(0.90,0.75,0.20), emission_strength=0.9)
M_BOAT_GREEN = mat("bg", (0.20, 0.65, 0.30, 1.0), 0.0, 0.55, emission=(0.20,0.60,0.30), emission_strength=0.7)
M_BOAT_WHITE = mat("bw", (0.92, 0.88, 0.82, 1.0), 0.0, 0.70)
BOAT_COLORS = [M_BOAT_RED, M_BOAT_BLUE, M_BOAT_YELLOW, M_BOAT_GREEN]

# Starfish colors
M_STARFISH_RED = mat("sfr", (0.95, 0.30, 0.30, 1.0), 0.0, 0.45, emission=(0.92,0.30,0.30), emission_strength=1.5)
M_STARFISH_PINK = mat("sfp", (0.95, 0.55, 0.85, 1.0), 0.0, 0.45, emission=(0.92,0.55,0.82), emission_strength=1.5)
M_STARFISH_ORANGE = mat("sfo", (1.0, 0.65, 0.18, 1.0), 0.0, 0.45, emission=(0.95,0.65,0.18), emission_strength=1.5)
M_STARFISH_PURPLE = mat("sfpu", (0.65, 0.30, 0.85, 1.0), 0.0, 0.45, emission=(0.62,0.30,0.82), emission_strength=1.5)
M_STARFISH_YELLOW = mat("sfy", (1.0, 0.92, 0.30, 1.0), 0.0, 0.45, emission=(0.95,0.88,0.30), emission_strength=1.5)
STARFISH_COLORS = [M_STARFISH_RED, M_STARFISH_PINK, M_STARFISH_ORANGE, M_STARFISH_PURPLE, M_STARFISH_YELLOW]

# Bubble
M_BUBBLE = mat("bub", (0.85, 0.92, 0.95, 1.0), 0.0, 0.10, emission=(0.85,0.92,0.95), emission_strength=2.0, alpha=0.45)

# Eye
M_EYE_DARK = mat("ed", (0.05, 0.04, 0.04, 1.0), 0.0, 0.20)
M_LIPS = mat("lp", (0.55, 0.18, 0.20, 1.0), 0.0, 0.45)

# Hat tam (rasta knit hat signature)
M_TAM = mat("tam", (0.10, 0.55, 0.20, 1.0), 0.0, 0.75, emission=(0.10,0.52,0.20), emission_strength=0.7)

# ============ SKY ============
sky = smooth_sphere("sky", r=280, segs=32, rings=20, loc=(0,0,0), mat_=M_SKY)
sky.scale = (1,1,0.6)
sky_p = smooth_sphere("sky_p", r=240, segs=28, rings=16, loc=(0,0,10), mat_=M_SKY_PURPLE)
sky_p.scale = (1,1,0.3)
# Sun
sun = smooth_sphere("sun", r=8, segs=24, rings=18, loc=(0, 90, 10), mat_=M_SUN)
for sh in range(3):
    smooth_sphere(f"sun_h{sh}", r=8 + sh*1, segs=24, rings=18, loc=(0, 90, 10), mat_=M_SUN)

# ============ ONE clean golden sand ground ============
ground = beveled_cube("ground", (200, 200, 0.5), bevel_offset=0.10, loc=(0, 0, -0.25), mat_=M_SAND_GOLD)
# Sand dunes
for i in range(150):
    a = random.uniform(0, math.pi*2); rad = random.uniform(2, 80)
    smooth_sphere(f"dune{i}", r=random.uniform(0.4, 1.0), segs=10, rings=8,
                  loc=(rad*math.cos(a), rad*math.sin(a), 0.10),
                  mat_=M_SAND_DARK if i % 3 == 0 else M_SAND_GOLD, scale=(1.5, 1.4, 0.22))

# ============ OCEAN ============
ocean_e = empty("ocean", loc=(0, 60, 0))
beveled_cube("oc", (200, 80, 0.20), bevel_offset=0.08, loc=(0, 0, 0.20),
             parent=ocean_e, mat_=M_OCEAN)
beveled_cube("oc_d", (195, 75, 0.15), bevel_offset=0.06, loc=(0, 0, 0.25),
             parent=ocean_e, mat_=M_OCEAN_DEEP)
# Foam at shore
for fi in range(40):
    fx = random.uniform(-90, 90); fy = random.uniform(-35, -25)
    cyl(f"foam{fi}", r=random.uniform(0.5, 1.0), depth=0.06, segs=14,
        loc=(fx, fy, 0.30), parent=ocean_e, mat_=M_FOAM)

# ============ 8 PALM TREES (signature) ============
def make_palm(name, loc, scale=1.0, lean=0):
    base = empty(name, loc)
    base.rotation_euler = (0, math.radians(lean), 0)
    # Trunk curved
    for ti in range(12):
        tz = ti * 0.5
        tilt = math.sin(ti * 0.3) * 0.10
        cyl(f"{name}_t{ti}", r=0.18 - ti*0.005, depth=0.50, segs=10,
            loc=(tilt, 0, tz + 0.25), parent=base, mat_=M_PALM_TRUNK)
    # Crown
    crown_e = empty(f"{name}_cr", (0, 0, 6.5), parent=base)
    for li in range(10):
        la = (li / 10.0) * math.pi * 2
        leaf_e = empty(f"{name}_le{li}", (0, 0, 0), parent=crown_e)
        leaf_e.rotation_euler = (math.radians(70), 0, la)
        # Leaf rachis
        cyl(f"{name}_lr{li}", r=0.025, depth=2.5, segs=8, loc=(0, 0, 1.25),
            parent=leaf_e, mat_=M_PALM_TRUNK)
        # Pinnae
        for sl in range(8):
            sl_z = sl * 0.30 + 0.30
            for ps in (-1, 1):
                beveled_cube(f"{name}_pn{li}_{sl}_{ps}", (0.03, 0.5, 0.04), bevel_offset=0.01,
                             loc=(ps*0.25, 0, sl_z), parent=leaf_e, mat_=M_PALM_LEAF)
    # Coconuts
    for ci in range(6):
        ca = (ci / 6.0) * math.pi * 2
        smooth_sphere(f"{name}_co{ci}", r=0.20, loc=(math.cos(ca)*0.30, math.sin(ca)*0.30, 6.3),
                      parent=base, mat_=M_COCONUT)
    base["_phase"] = random.uniform(0, math.pi*2)
    return {"root": base, "crown": crown_e}

palms = []
palm_pos = [(-30, -15, 0, 5), (-20, -18, 0, -3), (-10, -12, 0, 8),
             (10, -12, 0, -8), (20, -18, 0, 3), (30, -15, 0, -5),
             (-15, -25, 0, 0), (15, -25, 0, 0)]
for i, (px, py, pz, lean) in enumerate(palm_pos):
    p = make_palm(f"palm{i}", (px, py, pz), scale=1.0, lean=lean)
    palms.append(p)

# ============ REGGAE STAGE (signature) ============
stage_e = empty("stage", loc=(0, 5, 0))
# Platform
beveled_cube("st_p", (12, 6, 0.6), bevel_offset=0.10, loc=(0, 0, 0.3),
             parent=stage_e, mat_=M_STAGE_WOOD)
# Plank lines
for pi in range(12):
    beveled_cube(f"st_pl{pi}", (12.1, 0.5, 0.05), bevel_offset=0.02,
                 loc=(0, -2.75 + pi*0.5, 0.62), parent=stage_e, mat_=M_STAGE_DARK)
# Back panel
beveled_cube("st_bp", (12, 0.30, 5), bevel_offset=0.10, loc=(0, 3, 3),
             parent=stage_e, mat_=M_JAM_BLACK)
# Jamaica flag pattern (signature green/yellow/black diagonal)
beveled_cube("st_fg", (5, 0.10, 3), bevel_offset=0.06, loc=(-3.5, 2.95, 3),
             parent=stage_e, mat_=M_JAM_GREEN)
beveled_cube("st_fy", (5, 0.10, 0.30), bevel_offset=0.04, loc=(0, 2.95, 3),
             parent=stage_e, mat_=M_JAM_YELLOW)
beveled_cube("st_fb", (5, 0.10, 3), bevel_offset=0.06, loc=(3.5, 2.95, 3),
             parent=stage_e, mat_=M_JAM_BLACK)
# Diagonal yellow X (signature Jamaica)
for diag in (0, 1):
    diag_e = empty(f"st_d{diag}_e", (0, 2.95, 3), parent=stage_e)
    diag_e.rotation_euler = (0, math.radians(30 if diag == 0 else -30), 0)
    beveled_cube(f"st_d{diag}", (14, 0.12, 0.30), bevel_offset=0.04,
                 loc=(0, 0, 0), parent=diag_e, mat_=M_JAM_YELLOW)
# Sound speakers (signature)
for side in (-1, 1):
    beveled_cube(f"st_sp{side}", (1, 1, 2), bevel_offset=0.10, loc=(side*5, -2, 1.6),
                 parent=stage_e, mat_=M_JAM_BLACK)
    # Speaker cones
    cyl(f"st_sc{side}", r=0.35, depth=0.10, segs=14, loc=(side*5, -2.55, 1.6),
        parent=stage_e, mat_=M_STAGE_DARK)
    smooth_sphere(f"st_sc_c{side}", r=0.20, loc=(side*5, -2.6, 1.6),
                  parent=stage_e, mat_=M_JAM_BLACK)
# Mic stands
for mi in range(3):
    mx = -2 + mi * 2
    cyl(f"st_ms{mi}", r=0.03, depth=2.5, segs=10, loc=(mx, 0, 1.85),
        parent=stage_e, mat_=M_JAM_BLACK)
    # Mic
    smooth_sphere(f"st_m{mi}", r=0.10, loc=(mx, 0, 3.10),
                  parent=stage_e, mat_=M_JAM_BLACK)

# ============ 4 RASTAS DREADLOCKS (signature) ============
def make_rasta(name, loc, scale=1.0, facing=0):
    base = empty(name, loc)
    base.rotation_euler = (0, 0, facing)
    # Body green/yellow/red shirt
    shirt_col = random.choice([M_JAM_GREEN, M_JAM_YELLOW, M_JAM_RED])
    smooth_cone(f"{name}_sh", r1=0.32, r2=0.34, depth=0.7, segs=14, loc=(0, 0, 1.30),
                parent=base, mat_=shirt_col)
    # Pants
    for side in (-1, 1):
        cyl(f"{name}_leg{side}", r=0.11, depth=0.95, segs=10,
            loc=(side*0.13, 0, 0.47), parent=base, mat_=M_STAGE_DARK)
    # Sandals
    for side in (-1, 1):
        beveled_cube(f"{name}_sd{side}", (0.10, 0.20, 0.04), bevel_offset=0.02,
                     loc=(side*0.13, 0, 0), parent=base, mat_=M_PALM_TRUNK)
    # Arms (one raised)
    for side_idx, side in enumerate((-1, 1)):
        sh = empty(f"{name}_a{side_idx}", (side*0.30, 0, 1.65), parent=base)
        if side_idx == 0:
            sh.rotation_euler = (math.radians(-140), 0, math.radians(20))
        else:
            sh.rotation_euler = (math.radians(-30), 0, math.radians(-15))
        cyl(f"{name}_ua{side_idx}", r=0.07, depth=0.40, segs=10, loc=(0, 0, -0.20),
            parent=sh, mat_=shirt_col)
        cyl(f"{name}_fa{side_idx}", r=0.06, depth=0.35, segs=10, loc=(0, 0, -0.55),
            parent=sh, mat_=M_SKIN_DARK)
    # Head
    head_r_e = empty(f"{name}_he", (0, 0, 1.95), parent=base)
    smooth_sphere(f"{name}_h", r=0.18, segs=18, rings=14, loc=(0, 0, 0),
                  parent=head_r_e, mat_=M_SKIN_DARK)
    # Eyes
    for side in (-1, 1):
        smooth_sphere(f"{name}_ey{side}", r=0.025, loc=(side*0.06, -0.15, 0.03),
                      parent=head_r_e, mat_=M_EYE_DARK)
    # Big smile
    beveled_cube(f"{name}_sm", (0.10, 0.04, 0.025), bevel_offset=0.005,
                 loc=(0, -0.17, -0.07), parent=head_r_e, mat_=M_LIPS)
    # DREADLOCKS signature (long thick locks)
    dread_col = random.choice([M_DREAD_BLACK, M_DREAD_BROWN])
    for di in range(20):
        da = random.uniform(0, math.pi*2)
        dr = random.uniform(0.10, 0.18)
        dx = math.cos(da) * dr
        dy = math.sin(da) * dr
        dread_len = random.uniform(0.50, 1.2)
        # Stack of segments
        for si in range(int(dread_len * 8)):
            sz_d = -si * 0.10 - 0.10
            cyl(f"{name}_dr{di}_{si}", r=0.045, depth=0.10, segs=8,
                loc=(dx + math.sin(si*0.3)*0.05, dy + math.cos(si*0.3)*0.05, sz_d),
                parent=head_r_e, mat_=dread_col)
        # Bead at tip (signature)
        if random.random() > 0.5:
            smooth_sphere(f"{name}_db{di}", r=0.04,
                          loc=(dx, dy, -dread_len*0.8 - 0.15),
                          parent=head_r_e, mat_=random.choice([M_JAM_RED, M_JAM_YELLOW, M_JAM_GREEN]))
    # TAM HAT (signature knit hat green/yellow/red)
    if random.random() > 0.5:
        tam_e = empty(f"{name}_tam", (0, 0, 0.30), parent=head_r_e)
        cyl(f"{name}_tam_b", r=0.30, depth=0.20, segs=18, loc=(0, 0, 0),
            parent=tam_e, mat_=M_TAM)
        smooth_sphere(f"{name}_tam_t", r=0.28, loc=(0, 0, 0.15),
                      parent=tam_e, mat_=M_TAM, scale=(1, 1, 0.7))
        # Stripes (signature)
        cyl(f"{name}_tam_y", r=0.31, depth=0.05, segs=18, loc=(0, 0, 0.05),
            parent=tam_e, mat_=M_JAM_YELLOW)
        cyl(f"{name}_tam_r", r=0.31, depth=0.05, segs=18, loc=(0, 0, -0.05),
            parent=tam_e, mat_=M_JAM_RED)
    base["_phase"] = random.uniform(0, math.pi*2)
    return {"root": base, "he": head_r_e}

rastas = []
rasta_pos = [(-15, -8, math.radians(20)), (-5, -10, math.radians(0)),
              (5, -10, math.radians(0)), (15, -8, math.radians(-20))]
for i, (rx, ry, fac) in enumerate(rasta_pos):
    r = make_rasta(f"rasta{i}", (rx, ry, 0), scale=1.0, facing=fac)
    rastas.append(r)

# ============ 4 MUSICIANS reggae on stage ============
def make_musician(name, loc, instrument, scale=1.0, facing=0):
    base = empty(name, loc)
    base.rotation_euler = (0, 0, facing)
    # Body
    shirt_col = random.choice([M_JAM_GREEN, M_JAM_YELLOW, M_JAM_RED, M_BOAT_BLUE])
    smooth_cone(f"{name}_sh", r1=0.32, r2=0.34, depth=0.7, segs=14, loc=(0, 0, 1.30),
                parent=base, mat_=shirt_col)
    # Pants
    for side in (-1, 1):
        cyl(f"{name}_leg{side}", r=0.11, depth=0.95, segs=10,
            loc=(side*0.13, 0, 0.47), parent=base, mat_=M_STAGE_DARK)
    # Head
    head_m_e = empty(f"{name}_he", (0, 0, 1.95), parent=base)
    smooth_sphere(f"{name}_h", r=0.18, segs=18, rings=14, loc=(0, 0, 0),
                  parent=head_m_e, mat_=M_SKIN_DARK)
    # Eyes
    for side in (-1, 1):
        smooth_sphere(f"{name}_ey{side}", r=0.025, loc=(side*0.06, -0.15, 0.03),
                      parent=head_m_e, mat_=M_EYE_DARK)
    # Dreadlocks
    for di in range(15):
        da = random.uniform(0, math.pi*2)
        dread_len = random.uniform(0.40, 0.9)
        for si in range(int(dread_len * 6)):
            cyl(f"{name}_d{di}_{si}", r=0.04, depth=0.10, segs=8,
                loc=(math.cos(da)*0.15, math.sin(da)*0.10, -si*0.10 - 0.10),
                parent=head_m_e, mat_=M_DREAD_BLACK)
    # INSTRUMENT
    inst_e = empty(f"{name}_inst", (0, -0.30, 1.30), parent=base)
    if instrument == "guitar":
        # Guitar body
        smooth_sphere(f"{name}_g_b", r=0.25, segs=18, rings=14, loc=(0, 0, 0),
                      parent=inst_e, mat_=M_GUITAR_WOOD, scale=(0.85, 0.30, 1.2))
        # Neck
        cyl(f"{name}_g_n", r=0.025, depth=0.55, segs=10, loc=(0, -0.10, 0.45),
            parent=inst_e, mat_=M_STAGE_DARK)
        # Strings
        for st in range(6):
            cyl(f"{name}_g_s{st}", r=0.003, depth=0.85, segs=6,
                loc=((st-2.5)*0.012, -0.13, 0.25), parent=inst_e, mat_=M_STRING)
    elif instrument == "drum":
        # Big djembe drum
        smooth_cone(f"{name}_d_t", r1=0.25, r2=0.18, depth=0.35, segs=14,
                    loc=(0, 0, 0.20), parent=inst_e, mat_=M_DRUM_RED)
        smooth_cone(f"{name}_d_b", r1=0.18, r2=0.20, depth=0.35, segs=14,
                    loc=(0, 0, -0.18), parent=inst_e, mat_=M_DRUM_RED)
        # Skin top
        cyl(f"{name}_d_s", r=0.25, depth=0.03, segs=14, loc=(0, 0, 0.38),
            parent=inst_e, mat_=M_DRUM_SKIN)
        # Rope tension
        for ri in range(8):
            ra = (ri / 8.0) * math.pi * 2
            cyl(f"{name}_d_r{ri}", r=0.003, depth=0.6, segs=6,
                loc=(math.cos(ra)*0.21, math.sin(ra)*0.21, 0), parent=inst_e, mat_=M_PALM_TRUNK)
    elif instrument == "bass":
        # Bass guitar (longer neck)
        smooth_sphere(f"{name}_b_b", r=0.28, segs=18, rings=14, loc=(0, 0, 0),
                      parent=inst_e, mat_=M_BOAT_BLUE, scale=(0.85, 0.30, 1.2))
        cyl(f"{name}_b_n", r=0.025, depth=0.85, segs=10, loc=(0, -0.10, 0.55),
            parent=inst_e, mat_=M_STAGE_DARK)
        for st in range(4):
            cyl(f"{name}_b_s{st}", r=0.005, depth=1.15, segs=6,
                loc=((st-1.5)*0.012, -0.13, 0.30), parent=inst_e, mat_=M_STRING)
    base["_phase"] = random.uniform(0, math.pi*2)
    return {"root": base, "inst": inst_e, "he": head_m_e}

musicians = []
mus_data = [("guitar", -3, 5), ("drum", 0, 5), ("bass", 3, 5), ("drum", -1, 7)]
for i, (inst, mx, my) in enumerate(mus_data):
    m = make_musician(f"mus{i}", (mx, my, 0.7), instrument=inst, scale=1.0,
                      facing=math.radians(180))
    musicians.append(m)

# ============ 4 FISHING BOATS (signature) ============
def make_fishing_boat(name, loc, scale=1.0, facing=0):
    base = empty(name, loc)
    base.rotation_euler = (0, 0, facing)
    boat_col = random.choice(BOAT_COLORS)
    # Long hull
    smooth_cone(f"{name}_h", r1=0.45, r2=0.10, depth=4, segs=14, loc=(0, 0, 0),
                parent=base, mat_=boat_col).rotation_euler = (0, math.radians(90), 0)
    # Plank lines
    beveled_cube(f"{name}_pl", (4.0, 0.85, 0.10), bevel_offset=0.04, loc=(0, 0, 0.10),
                 parent=base, mat_=M_BOAT_WHITE)
    # Inside boat
    beveled_cube(f"{name}_in", (3.5, 0.7, 0.20), bevel_offset=0.06, loc=(0, 0, 0.20),
                 parent=base, mat_=M_PALM_TRUNK)
    # Fishing nets piled
    for ni in range(5):
        nx = -1.5 + ni * 0.6
        smooth_sphere(f"{name}_n{ni}", r=0.15, loc=(nx, 0, 0.35), parent=base, mat_=M_BOAT_WHITE,
                      scale=(1, 1, 0.5))
    # Mast small
    cyl(f"{name}_m", r=0.04, depth=2, segs=8, loc=(0, 0, 1.20),
        parent=base, mat_=M_STAGE_DARK)
    # Small sail
    beveled_cube(f"{name}_s", (1.5, 0.05, 1.2), bevel_offset=0.06, loc=(0.6, 0, 1.50),
                 parent=base, mat_=M_BOAT_WHITE)
    base["_phase"] = random.uniform(0, math.pi*2)
    return base

boats = []
boat_pos = [(-25, 25, math.radians(-10)), (-10, 30, math.radians(0)),
             (10, 30, math.radians(10)), (25, 25, math.radians(-5))]
for i, (bx, by, fac) in enumerate(boat_pos):
    b = make_fishing_boat(f"boat{i}", (bx, by, 0.4), scale=1.0, facing=fac)
    boats.append(b)

# ============ JAMAICA FLAG huge (signature) ============
flag_big_e = empty("big_flag", (-30, 5, 0))
# Pole
cyl("bf_p", r=0.10, depth=10, segs=10, loc=(0, 0, 5), parent=flag_big_e, mat_=M_STAGE_DARK)
# Flag fabric with diagonals (signature)
beveled_cube("bf_g1", (4, 0.05, 2.5), bevel_offset=0.06, loc=(2, 0, 9),
             parent=flag_big_e, mat_=M_JAM_GREEN)
# Yellow X diagonals
for diag in (0, 1):
    diag_e = empty(f"bf_d{diag}_e", (2, -0.04, 9), parent=flag_big_e)
    diag_e.rotation_euler = (0, math.radians(30 if diag == 0 else -30), 0)
    beveled_cube(f"bf_d{diag}", (5, 0.05, 0.40), bevel_offset=0.04, loc=(0, 0, 0),
                 parent=diag_e, mat_=M_JAM_YELLOW)
# Black triangles top/bottom
for side in (-1, 1):
    diag_b_e = empty(f"bf_bk{side}_e", (2, -0.05, 9 + side*1.0), parent=flag_big_e)
    beveled_cube(f"bf_bk{side}", (1.5, 0.05, 1.0), bevel_offset=0.04, loc=(0, 0, 0),
                 parent=diag_b_e, mat_=M_JAM_BLACK)
flag_big_e["_phase"] = 0

# ============================================================
# ⭐ 600 STARFISH + 400 BUBBLES (PARTICULES THÉMATIQUES OBLIGATOIRES)
# ============================================================
starfish = []
for i in range(600):
    px = random.uniform(-70, 70)
    py = random.uniform(-30, 80)
    pz = random.uniform(0.3, 12)
    star_col = random.choice(STARFISH_COLORS)
    s_e = empty(f"sf{i}", (px, py, pz))
    # 5-arm star
    for arm in range(5):
        aa = (arm / 5.0) * math.pi * 2 + math.pi/2
        beveled_cube(f"sf{i}_a{arm}", (0.04, 0.10, 0.04), bevel_offset=0.01,
                     loc=(math.cos(aa)*0.06, math.sin(aa)*0.06, 0),
                     parent=s_e, mat_=star_col).rotation_euler = (0, 0, aa - math.pi/2)
    # Center
    smooth_sphere(f"sf{i}_c", r=0.04, loc=(0, 0, 0), parent=s_e, mat_=star_col)
    s_e["_phase"] = random.uniform(0, math.pi*2)
    s_e["_base_x"] = px; s_e["_base_y"] = py; s_e["_base_z"] = pz
    s_e["_amp_x"] = random.uniform(1.0, 2.5)
    s_e["_amp_y"] = random.uniform(1.0, 2.5)
    s_e["_amp_z"] = random.uniform(0.5, 1.5)
    s_e["_speed"] = random.uniform(0.3, 0.8)
    starfish.append(s_e)

# 400 bubbles
bubbles = []
for i in range(400):
    px = random.uniform(-70, 70)
    py = random.uniform(20, 80)
    pz = random.uniform(0.5, 12)
    b = smooth_sphere(f"bub{i}", r=random.uniform(0.10, 0.18), segs=10, rings=8,
                      loc=(px, py, pz), mat_=M_BUBBLE)
    b["_phase"] = random.uniform(0, math.pi*2)
    b["_base_x"] = px; b["_base_y"] = py; b["_base_z"] = pz
    b["_amp_x"] = random.uniform(0.5, 1.5)
    b["_amp_y"] = random.uniform(0.5, 1.5)
    b["_speed"] = random.uniform(0.5, 1.2)
    b["_rise"] = random.uniform(1.0, 2.5)
    bubbles.append(b)

# ============ ANIMATION ============
fps = 30; duration_s = 6; total_frames = fps * duration_s

# Palms sway
for p in palms:
    phase = p["root"]["_phase"]
    for f in range(1, total_frames + 1, 5):
        t = (f - 1) / fps
        p["crown"].rotation_euler = (math.sin(t * 0.8 + phase) * math.radians(5),
                                      math.cos(t * 0.8 + phase) * math.radians(5), 0)
        p["crown"].keyframe_insert("rotation_euler", frame=f)

# Rastas dance
for r in rastas:
    phase = r["root"]["_phase"]
    for f in range(1, total_frames + 1, 3):
        t = (f - 1) / fps
        r["root"].rotation_euler = (math.sin(t * 2.5 + phase) * math.radians(6),
                                     math.cos(t * 2.5 + phase) * math.radians(8),
                                     r["root"].rotation_euler.z)
        r["root"].location.z = abs(math.sin(t * 3.0 + phase)) * 0.20
        r["root"].keyframe_insert("rotation_euler", frame=f)
        r["root"].keyframe_insert("location", frame=f)
        r["he"].rotation_euler = (math.sin(t * 2.0 + phase) * math.radians(8), 0,
                                   math.cos(t * 1.5 + phase) * math.radians(15))
        r["he"].keyframe_insert("rotation_euler", frame=f)

# Musicians play
for m in musicians:
    phase = m["root"]["_phase"]
    for f in range(1, total_frames + 1, 3):
        t = (f - 1) / fps
        m["root"].rotation_euler = (math.sin(t * 3.0 + phase) * math.radians(5), 0,
                                     m["root"].rotation_euler.z)
        m["root"].keyframe_insert("rotation_euler", frame=f)
        sc_i = 1 + math.sin(t * 6.0 + phase) * 0.05
        m["inst"].scale = (sc_i, sc_i, sc_i)
        m["inst"].keyframe_insert("scale", frame=f)

# Boats bob
for b in boats:
    phase = b["_phase"]
    bz_b = b.location.z
    for f in range(1, total_frames + 1, 4):
        t = (f - 1) / fps
        b.location.z = bz_b + math.sin(t * 1.0 + phase) * 0.15
        b.rotation_euler = (math.sin(t * 1.0 + phase) * math.radians(3),
                             math.cos(t * 1.0 + phase) * math.radians(3),
                             b.rotation_euler.z)
        b.keyframe_insert("location", frame=f)
        b.keyframe_insert("rotation_euler", frame=f)

# Flag wave
for f in range(1, total_frames + 1, 5):
    t = (f - 1) / fps
    flag_big_e.rotation_euler = (0, 0, math.sin(t * 1.5) * math.radians(8))
    flag_big_e.keyframe_insert("rotation_euler", frame=f)

# 600 starfish float
for sf in starfish:
    phase = sf["_phase"]; speed = sf["_speed"]
    bx, by, bz = sf["_base_x"], sf["_base_y"], sf["_base_z"]
    ax, ay, az = sf["_amp_x"], sf["_amp_y"], sf["_amp_z"]
    for f in range(1, total_frames + 1, 4):
        t = (f - 1) / fps
        x = bx + ax * math.sin(t * speed + phase)
        y = by + ay * math.cos(t * speed * 0.9 + phase)
        z = bz + az * math.sin(t * speed * 1.3 + phase)
        sf.location = (x, y, z)
        sf.rotation_euler = (0, 0, t * 1.0 + phase)
        sf.keyframe_insert("location", frame=f)
        sf.keyframe_insert("rotation_euler", frame=f)

# 400 bubbles rise
for b in bubbles:
    phase = b["_phase"]; speed = b["_speed"]; rise = b["_rise"]
    bx, by, bz = b["_base_x"], b["_base_y"], b["_base_z"]
    ax, ay = b["_amp_x"], b["_amp_y"]
    for f in range(1, total_frames + 1, 4):
        t = (f - 1) / fps
        x = bx + ax * math.sin(t * speed + phase) * 0.3
        y = by + ay * math.cos(t * speed * 0.9 + phase) * 0.3
        z = bz + (t * rise) % 5
        b.location = (x, y, z)
        sc_b = 1 + math.sin(t * 2.0 + phase) * 0.10
        b.scale = (sc_b, sc_b, sc_b)
        b.keyframe_insert("location", frame=f)
        b.keyframe_insert("scale", frame=f)

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
out_glb = os.path.join(out_dir, "pbr_jamaica_proc.glb")

bpy.ops.object.select_all(action='SELECT')
bpy.ops.export_scene.gltf(
    filepath=out_glb, export_format='GLB',
    export_animations=True, export_apply=False, export_yup=True, use_selection=False,
)
size_mb = os.path.getsize(out_glb) / (1024 * 1024)
print(f"[proc_caribbean_jamaica_reggae_beach] DONE → {out_glb} ({size_mb:.2f} MB)")
print(f"[proc_caribbean_jamaica_reggae_beach] 8 palms + reggae stage Jamaica flag X diagonals + speakers + 3 mics + 4 rastas with dreadlocks signature + 4 musicians (guitar/djembe drum/bass) + 4 fishing boats + huge Jamaica flag + 600 starfish + 400 bubbles")
print("⭐ FIXES: 1 ground + 600 starfish + 400 bubbles (signature Jamaica mandatory) ⭐")
