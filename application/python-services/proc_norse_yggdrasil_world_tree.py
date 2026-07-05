"""
proc_norse_yggdrasil_world_tree.py — 217e procédural AuroraIA (81e qualité)
Yggdrasil norse: ONE ground + 800 cosmic leaves + massive world tree + 9 branches + Odin + 4 norns + Nidhogg + Ratatoskr + corbeaux + cosmic sky
FIXES : 1 ground propre + 800 cosmic leaves thématique (signature Yggdrasil)
"""
import bpy, bmesh, math, random, os

random.seed(0x46217)

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

# Cosmic Yggdrasil materials
M_SKY = mat("sky", (0.05, 0.04, 0.15, 1.0), 0.0, 0.7, emission=(0.05,0.04,0.15), emission_strength=1.0)
M_AURORA_PURPLE = mat("aurora_p", (0.45, 0.20, 0.85, 1.0), 0.0, 0.20, emission=(0.45,0.20,0.85), emission_strength=8.0, alpha=0.7)
M_AURORA_BLUE = mat("aurora_b", (0.20, 0.45, 0.95, 1.0), 0.0, 0.20, emission=(0.20,0.45,0.95), emission_strength=7.0, alpha=0.7)
M_AURORA_GREEN = mat("aurora_g", (0.15, 0.85, 0.55, 1.0), 0.0, 0.20, emission=(0.15,0.85,0.55), emission_strength=7.5, alpha=0.7)
M_STAR = mat("star", (1.0, 1.0, 0.95, 1.0), 0.0, 0.20, emission=(1.0,1.0,0.95), emission_strength=12.0)
M_NEBULA = mat("nebula", (0.55, 0.20, 0.75, 1.0), 0.0, 0.70, emission=(0.50,0.20,0.70), emission_strength=2.0, alpha=0.55)

# Yggdrasil bark + leaves
M_BARK = mat("bark", (0.20, 0.12, 0.06, 1.0), 0.0, 0.85, emission=(0.18,0.10,0.05), emission_strength=0.2)
M_BARK_GLOW = mat("bark_g", (0.45, 0.30, 0.15, 1.0), 0.0, 0.75, emission=(0.55,0.40,0.20), emission_strength=0.9)
M_LEAF_GOLD = mat("leaf_g", (1.0, 0.85, 0.30, 1.0), 0.7, 0.30, emission=(0.95,0.78,0.28), emission_strength=2.5)
M_LEAF_BRONZE = mat("leaf_b", (0.85, 0.55, 0.20, 1.0), 0.5, 0.40, emission=(0.78,0.50,0.18), emission_strength=2.0)
M_LEAF_GREEN_DEEP = mat("leaf_gd", (0.25, 0.55, 0.30, 1.0), 0.0, 0.55, emission=(0.22,0.50,0.28), emission_strength=1.2)
M_LEAF_AUTUMN = mat("leaf_a", (0.85, 0.40, 0.15, 1.0), 0.0, 0.45, emission=(0.78,0.38,0.15), emission_strength=1.5)

# Runes blue glowing on bark
M_RUNE_BLUE = mat("rune_b", (0.20, 0.65, 0.95, 1.0), 0.0, 0.20, emission=(0.20,0.65,0.95), emission_strength=15.0)
M_RUNE_GOLD = mat("rune_g", (1.0, 0.78, 0.20, 1.0), 0.0, 0.20, emission=(1.0,0.78,0.20), emission_strength=12.0)

# Ground roots
M_GROUND = mat("ground", (0.18, 0.15, 0.10, 1.0), 0.0, 0.85, emission=(0.15,0.12,0.08), emission_strength=0.2)
M_GROUND_GLOW = mat("ground_g", (0.30, 0.22, 0.15, 1.0), 0.0, 0.75, emission=(0.28,0.20,0.13), emission_strength=0.5)
M_ROCK = mat("rock", (0.30, 0.28, 0.25, 1.0), 0.0, 0.85)
M_MOSS_NORSE = mat("moss", (0.20, 0.45, 0.25, 1.0), 0.0, 0.75, emission=(0.18,0.40,0.22), emission_strength=0.6)

# Norns - cloaked figures
M_CLOAK_DARK = mat("cloak_d", (0.10, 0.08, 0.15, 1.0), 0.0, 0.85, emission=(0.10,0.08,0.15), emission_strength=0.3)
M_CLOAK_GRAY = mat("cloak_g", (0.30, 0.32, 0.40, 1.0), 0.0, 0.75, emission=(0.28,0.30,0.38), emission_strength=0.4)
M_CLOAK_WHITE = mat("cloak_w", (0.85, 0.85, 0.92, 1.0), 0.0, 0.65, emission=(0.78,0.78,0.85), emission_strength=0.6)
M_CLOAK_BLOOD = mat("cloak_b", (0.55, 0.10, 0.15, 1.0), 0.0, 0.65, emission=(0.50,0.10,0.15), emission_strength=0.7)
M_SKIN_NORN = mat("skin_n", (0.92, 0.85, 0.78, 1.0), 0.0, 0.55, emission=(0.85,0.78,0.72), emission_strength=0.5)
M_HAIR_SILVER = mat("hair_s", (0.85, 0.85, 0.92, 1.0), 0.1, 0.55, emission=(0.78,0.78,0.85), emission_strength=0.4)

# Odin (one-eyed bearded sage)
M_ODIN_CLOAK = mat("odin_c", (0.18, 0.15, 0.35, 1.0), 0.0, 0.75, emission=(0.18,0.15,0.32), emission_strength=0.5)
M_ODIN_CAPE = mat("odin_cape", (0.20, 0.18, 0.40, 1.0), 0.0, 0.70, emission=(0.20,0.18,0.40), emission_strength=0.6)
M_ODIN_HAT = mat("odin_h", (0.28, 0.22, 0.18, 1.0), 0.0, 0.75, emission=(0.25,0.20,0.15), emission_strength=0.4)
M_BEARD_WHITE = mat("beard", (0.92, 0.92, 0.95, 1.0), 0.0, 0.65, emission=(0.85,0.85,0.90), emission_strength=0.4)
M_ODIN_GOLD = mat("odin_g", (0.95, 0.78, 0.30, 1.0), 0.95, 0.18, emission=(0.90,0.72,0.28), emission_strength=1.5)
M_EYE_PATCH = mat("eyepatch", (0.10, 0.05, 0.03, 1.0), 0.0, 0.80)
M_EYE_SOCKET = mat("eye_socket", (0.05, 0.05, 0.05, 1.0), 0.0, 0.50)
M_ODIN_EYE = mat("odin_eye", (0.65, 0.85, 1.0, 1.0), 0.0, 0.10, emission=(0.65,0.85,1.0), emission_strength=8.0)

# Nidhogg dragon
M_NIDHOGG = mat("nidhogg", (0.35, 0.20, 0.18, 1.0), 0.3, 0.55, emission=(0.30,0.18,0.15), emission_strength=0.5)
M_NIDHOGG_BACK = mat("nidhogg_b", (0.55, 0.22, 0.15, 1.0), 0.0, 0.65, emission=(0.50,0.20,0.13), emission_strength=0.7)
M_DRAGON_EYE = mat("d_eye", (1.0, 0.20, 0.10, 1.0), 0.0, 0.10, emission=(1.0,0.20,0.10), emission_strength=12.0)
M_FANG = mat("fang", (0.92, 0.88, 0.80, 1.0), 0.0, 0.40, emission=(0.85,0.82,0.75), emission_strength=0.4)

# Ratatoskr squirrel
M_SQUIRREL = mat("squirrel", (0.75, 0.40, 0.15, 1.0), 0.0, 0.55, emission=(0.70,0.38,0.15), emission_strength=0.5)
M_SQUIRREL_BELLY = mat("sq_belly", (0.95, 0.88, 0.75, 1.0), 0.0, 0.55, emission=(0.88,0.82,0.70), emission_strength=0.4)

# Ravens Huginn/Muninn
M_RAVEN = mat("raven", (0.05, 0.04, 0.06, 1.0), 0.3, 0.45, emission=(0.05,0.04,0.06), emission_strength=0.3)
M_RAVEN_SHINE = mat("raven_s", (0.18, 0.16, 0.22, 1.0), 0.5, 0.30, emission=(0.18,0.16,0.22), emission_strength=0.6)
M_RAVEN_EYE = mat("raven_eye", (1.0, 0.85, 0.20, 1.0), 0.0, 0.20, emission=(1.0,0.85,0.20), emission_strength=10.0)

# ============ SKY + COSMIC ============
sky = smooth_sphere("sky", r=140, segs=32, rings=20, loc=(0,0,0), mat_=M_SKY)
sky.scale = (1,1,0.5)

# Aurora ribbons (3 large planes)
for i, col in enumerate((M_AURORA_PURPLE, M_AURORA_BLUE, M_AURORA_GREEN)):
    a_e = empty(f"aurora_e{i}", (0, 25, 35 + i*4))
    for s in range(8):
        seg_x = (s - 3.5) * 6
        seg_z = math.sin(s * 0.8) * 2
        beveled_cube(f"aurora_{i}_{s}", (6, 0.3, 4 + i), bevel_offset=0.1,
                     loc=(seg_x, 0, seg_z), parent=a_e, mat_=col)
    a_e["_phase"] = i * 0.5
    a_e.rotation_euler = (math.radians(10*i), 0, 0)

# 200 stars
for i in range(200):
    a = random.uniform(0, math.pi*2)
    phi = random.uniform(math.pi/8, math.pi/2.2)
    r_star = 110
    sx = r_star * math.cos(phi) * math.cos(a)
    sy = r_star * math.cos(phi) * math.sin(a)
    sz = r_star * math.sin(phi) * 0.4
    smooth_sphere(f"star{i}", r=random.uniform(0.20, 0.50), segs=10, rings=8,
                  loc=(sx, sy, sz), mat_=M_STAR)

# Nebulas drift
for i in range(5):
    a = (i / 5.0) * math.pi * 2
    rad = random.uniform(60, 80)
    cx = rad * math.cos(a)
    cy = rad * math.sin(a)
    cz = random.uniform(25, 45)
    n_e = empty(f"nebula_e{i}", (cx, cy, cz))
    for j in range(4):
        smooth_sphere(f"nebula{i}_{j}", r=random.uniform(4.0, 6.5),
                      loc=(random.uniform(-4,4), random.uniform(-3,3), random.uniform(-1,1)),
                      parent=n_e, mat_=M_NEBULA)
    n_e["_phase"] = random.uniform(0, math.pi*2)

# ============ ONE clean cosmic ground ============
ground = beveled_cube("ground", (90, 90, 0.5), bevel_offset=0.08, loc=(0, 0, -0.25), mat_=M_GROUND)

# Glowing root patterns radiating from tree base (organic 3D)
for i in range(40):
    a = (i / 40.0) * math.pi * 2
    # 5-segment radial root
    rad_start = 1.5
    rad_end = random.uniform(15, 30)
    for s in range(8):
        t_param = s / 8.0
        rad = rad_start + (rad_end - rad_start) * t_param
        x = rad * math.cos(a) + math.sin(t_param * math.pi * 3) * 0.5
        y = rad * math.sin(a) + math.cos(t_param * math.pi * 3) * 0.5
        r_size = (0.40 - t_param * 0.30) * random.uniform(0.7, 1.2)
        smooth_sphere(f"root_glow{i}_{s}", r=r_size, segs=10, rings=8,
                      loc=(x, y, 0.20),
                      mat_=M_GROUND_GLOW if s % 2 == 0 else M_GROUND,
                      scale=(1.5, 0.6, 0.30))

# 25 rocks (mystical norse)
for i in range(25):
    a = random.uniform(0, math.pi*2)
    rad = random.uniform(15, 35)
    smooth_sphere(f"rock{i}", r=random.uniform(0.5, 1.1),
                  loc=(rad*math.cos(a), rad*math.sin(a), 0.30),
                  mat_=M_ROCK,
                  scale=(random.uniform(0.8,1.3), random.uniform(0.8,1.3),
                         random.uniform(0.5,0.8)))

# Moss patches (norse moss)
for i in range(20):
    a = random.uniform(0, math.pi*2)
    rad = random.uniform(8, 35)
    smooth_sphere(f"moss{i}", r=random.uniform(0.30, 0.6),
                  loc=(rad*math.cos(a), rad*math.sin(a), 0.10),
                  mat_=M_MOSS_NORSE, scale=(1.4, 1.2, 0.20))

# 6 stone runestones (engraved)
runestone_pos = [(8, 8, 0), (-8, 8, 0), (10, -5, 0), (-10, -5, 0),
                 (5, 12, 0), (-5, 12, 0)]
for i, (rsx, rsy, rsz) in enumerate(runestone_pos):
    r_e = empty(f"rs{i}", (rsx, rsy, rsz))
    # Tall stone slab
    beveled_cube(f"rs_body{i}", (0.8, 0.35, 2.2), bevel_offset=0.05,
                 loc=(0, 0, 1.1), parent=r_e, mat_=M_ROCK)
    # Glowing rune symbols
    for ri in range(5):
        smooth_sphere(f"rs_rune{i}_{ri}", r=0.10,
                      loc=(0, -0.20, 0.5 + ri*0.35), parent=r_e,
                      mat_=M_RUNE_BLUE, scale=(1, 0.3, 1))

# ============ YGGDRASIL MASSIVE WORLD TREE ============
yggdrasil_e = empty("yggdrasil", loc=(0, 0, 0))
# MASSIVE trunk - 12 segments vertical (12m tall + tapered)
trunk_segs = 14
for s in range(trunk_segs):
    r1 = 2.8 - s*0.10
    r2 = 2.7 - s*0.10
    seg_z = (s+0.5) * 0.9
    # Twisted trunk (slight rotation per segment)
    seg = smooth_cone(f"yg_trunk{s}", r1=r1, r2=r2, depth=0.95, segs=20,
                      loc=(math.sin(s*0.2)*0.1, math.cos(s*0.2)*0.1, seg_z),
                      parent=yggdrasil_e, mat_=M_BARK if s % 2 == 0 else M_BARK_GLOW)
    seg.rotation_euler = (math.radians(random.uniform(-3,3)),
                          math.radians(random.uniform(-3,3)), 0)

# Bark knots (random bumps)
for i in range(20):
    h = random.uniform(1, 11)
    a = random.uniform(0, math.pi*2)
    smooth_sphere(f"yg_knot{i}", r=random.uniform(0.20, 0.40),
                  loc=(2.3*math.cos(a), 2.3*math.sin(a), h),
                  parent=yggdrasil_e, mat_=M_BARK, scale=(1, 0.7, 1.2))

# RUNES carved on trunk (signature Yggdrasil)
for ring in range(5):
    rh = 2.0 + ring * 2.0
    for ri in range(8):
        ra = (ri / 8.0) * math.pi * 2
        rune = beveled_cube(f"yg_rune_r{ring}_{ri}", (0.12, 0.05, 0.35), bevel_offset=0.02,
                            loc=(2.55*math.cos(ra), 2.55*math.sin(ra), rh),
                            parent=yggdrasil_e,
                            mat_=M_RUNE_BLUE if (ring + ri) % 3 != 0 else M_RUNE_GOLD)
        rune.rotation_euler = (0, 0, ra + math.pi/2)

# 9 MASSIVE BRANCHES (9 nordic worlds)
branches = []
top_z = 12.5
for j in range(9):
    a = (j / 9.0) * math.pi * 2
    b_e = empty(f"yg_b_e{j}", (0, 0, top_z - 1.0), parent=yggdrasil_e)
    b_e.rotation_euler = (math.radians(45 + random.uniform(-10, 10)), 0, a)
    # Branch 4 segments tapered
    for k in range(5):
        cyl(f"yg_b{j}_{k}", r=(0.55 - k*0.08), depth=1.4, segs=14,
            loc=(0, (k+0.5)*1.4, 0), parent=b_e,
            mat_=M_BARK).rotation_euler = (math.radians(90), 0, 0)
    # Sub-branches per main branch (each = a world)
    for sb in range(3):
        sb_e = empty(f"yg_sb_e{j}_{sb}", (0, 6, 0), parent=b_e)
        sb_e.rotation_euler = (0, math.radians(30*(sb-1)), 0)
        for k in range(3):
            cyl(f"yg_sb{j}_{sb}_{k}", r=(0.20 - k*0.04), depth=0.9, segs=10,
                loc=(0, (k+0.5)*0.9, 0), parent=sb_e,
                mat_=M_BARK).rotation_euler = (math.radians(90), 0, 0)
        # MASSIVE foliage cluster (cosmic canopy)
        for fc in range(8):
            fa = (fc / 8.0) * math.pi * 2
            rad = random.uniform(1.5, 3.0)
            col = [M_LEAF_GOLD, M_LEAF_BRONZE, M_LEAF_GREEN_DEEP, M_LEAF_AUTUMN][fc % 4]
            smooth_sphere(f"yg_fol{j}_{sb}_{fc}", r=random.uniform(1.2, 1.8),
                          loc=(rad*math.cos(fa), 3 + rad*math.sin(fa),
                               random.uniform(-0.5, 0.5)),
                          parent=sb_e, mat_=col,
                          scale=(1, 1, 0.85))
    branches.append(b_e)

# Top center foliage cluster (signature world tree crown)
for fc in range(20):
    a = (fc / 20.0) * math.pi * 2
    rad = random.uniform(2.5, 5.0)
    col = [M_LEAF_GOLD, M_LEAF_BRONZE, M_LEAF_GREEN_DEEP][fc % 3]
    smooth_sphere(f"yg_crown{fc}", r=random.uniform(1.5, 2.2),
                  loc=(rad*math.cos(a), rad*math.sin(a), top_z + 3 + random.uniform(-1, 2)),
                  parent=yggdrasil_e, mat_=col,
                  scale=(1, 1, 0.85))

# MASSIVE GIANT ROOTS (3 main roots = 3 wells in mythology)
root_dirs = [math.radians(0), math.radians(120), math.radians(240)]
for ri, ra in enumerate(root_dirs):
    r_e = empty(f"yg_root_e{ri}", (0, 0, 0.5), parent=yggdrasil_e)
    r_e.rotation_euler = (0, 0, ra)
    # 6-segment root descending + radiating
    for k in range(7):
        seg_r = 1.2 - k*0.12
        seg_x = (k+0.5) * 1.8
        seg_z = -math.sin(k * 0.4) * 0.6 - 0.3
        seg = cyl(f"yg_root{ri}_{k}", r=seg_r, depth=1.6, segs=14,
                  loc=(seg_x, 0, seg_z), parent=r_e, mat_=M_BARK)
        seg.rotation_euler = (0, math.radians(90), 0)
    # Sub-roots branching
    for sr in range(3):
        sr_a = (sr - 1) * 0.5
        for k in range(3):
            cyl(f"yg_subroot{ri}_{sr}_{k}", r=0.30 - k*0.06, depth=1.0, segs=10,
                loc=(8 + k*1.0, sr_a * (k+1), 0),
                parent=r_e, mat_=M_BARK).rotation_euler = (0, math.radians(75 + sr*15), 0)

# ============ ODIN (one-eyed sage, gray cape, wide-brim hat) ============
odin_e = empty("odin", loc=(7, 6, 0))
odin_e.rotation_euler = (0, 0, math.radians(-130))
# Cape (massive cone draped)
smooth_cone("odin_cape", r1=0.85, r2=0.45, depth=2.8, segs=20,
            loc=(0, 0, 1.40), parent=odin_e, mat_=M_ODIN_CAPE)
# Hood overflowing
smooth_sphere("odin_hood", r=0.45, loc=(0, 0.10, 2.30),
              parent=odin_e, mat_=M_ODIN_CAPE, scale=(1.1, 1.0, 0.9))
# Inner robe
smooth_cone("odin_robe", r1=0.55, r2=0.30, depth=2.0, segs=18,
            loc=(0, 0, 1.0), parent=odin_e, mat_=M_ODIN_CLOAK)
# Belt
cyl("odin_belt", r=0.45, depth=0.18, segs=18,
    loc=(0, 0, 1.85), parent=odin_e, mat_=M_BARK)
# Buckle
beveled_cube("odin_buckle", (0.20, 0.05, 0.20), bevel_offset=0.03,
             loc=(0, -0.45, 1.85), parent=odin_e, mat_=M_ODIN_GOLD)
# Torso
beveled_cube("odin_torso", (0.45, 0.30, 0.55), bevel_offset=0.05,
             loc=(0, 0, 2.20), parent=odin_e, mat_=M_ODIN_CLOAK)
# Wide-brim hat (signature)
cyl("odin_brim", r=0.55, depth=0.06, segs=20,
    loc=(0, 0, 3.10), parent=odin_e, mat_=M_ODIN_HAT)
cyl("odin_crown", r=0.32, depth=0.40, segs=16,
    loc=(0, 0, 3.32), parent=odin_e, mat_=M_ODIN_HAT)
# Hat top
smooth_sphere("odin_hat_top", r=0.30, loc=(0, 0, 3.55), parent=odin_e,
              mat_=M_ODIN_HAT, scale=(1, 1, 0.8))
# Neck
cyl("odin_neck", r=0.08, depth=0.16, segs=10, loc=(0, 0, 2.60), parent=odin_e,
    mat_=M_SKIN_NORN)
# Head
odin_head_e = empty("odin_head_e", (0, 0, 2.85), parent=odin_e)
smooth_sphere("odin_head", r=0.20, segs=20, rings=14, loc=(0, 0, 0),
              parent=odin_head_e, mat_=M_SKIN_NORN)
# Long white beard (signature)
smooth_sphere("odin_beard", r=0.30,
              loc=(0, -0.18, -0.30), parent=odin_head_e,
              mat_=M_BEARD_WHITE, scale=(1.1, 1.0, 1.5))
# Beard strands
for i in range(5):
    strand = beveled_cube(f"odin_b_str{i}", (0.10, 0.08, 0.50),
                          loc=((i-2)*0.07, -0.18, -0.70),
                          parent=odin_head_e, mat_=M_BEARD_WHITE)
    strand.rotation_euler = (math.radians(random.uniform(-10, 10)), 0, 0)
# Mustache
smooth_sphere("odin_mustache", r=0.10,
              loc=(0, -0.18, -0.05), parent=odin_head_e,
              mat_=M_BEARD_WHITE, scale=(1.5, 0.8, 0.6))
# Right eye open glowing
smooth_sphere("odin_eye_r", r=0.035,
              loc=(0.07, -0.17, 0.04), parent=odin_head_e, mat_=M_ODIN_EYE)
# Left eye patch (signature one-eye Odin)
beveled_cube("odin_eyepatch", (0.09, 0.04, 0.07), bevel_offset=0.02,
             loc=(-0.07, -0.17, 0.04), parent=odin_head_e, mat_=M_EYE_PATCH)
# Eyepatch strap across head
strap = beveled_cube("odin_strap", (0.42, 0.04, 0.025), bevel_offset=0.01,
                     loc=(0, -0.05, 0.10), parent=odin_head_e, mat_=M_EYE_PATCH)
strap.rotation_euler = (0, 0, math.radians(-25))
# Long hair (white, behind)
smooth_sphere("odin_hair", r=0.25, loc=(0, 0.10, 0.05),
              parent=odin_head_e, mat_=M_BEARD_WHITE, scale=(1, 1, 0.9))
# 2 arms (staff hold)
for side_idx, side in enumerate((-1, 1)):
    sh = empty(f"odin_sh{side_idx}", (side*0.32, 0, 2.40), parent=odin_e)
    if side_idx == 0:
        sh.rotation_euler = (math.radians(-30), 0, math.radians(15))
    else:
        sh.rotation_euler = (math.radians(-90), 0, math.radians(-25))
    # Cape sleeve
    smooth_cone(f"odin_sleeve{side_idx}", r1=0.18, r2=0.12, depth=0.50, segs=14,
                loc=(0, 0, -0.25), parent=sh, mat_=M_ODIN_CAPE)
    cyl(f"odin_fa{side_idx}", r=0.07, depth=0.35, segs=10,
        loc=(0, 0, -0.60), parent=sh, mat_=M_SKIN_NORN)
    smooth_sphere(f"odin_hand{side_idx}", r=0.08, loc=(0, 0, -0.80),
                  parent=sh, mat_=M_SKIN_NORN)
# Staff (Gungnir spear)
staff_e = empty("odin_staff", (0.50, 0, 2.0), parent=odin_e)
staff_e.rotation_euler = (math.radians(-10), 0, 0)
cyl("staff_shaft", r=0.04, depth=3.0, segs=10, loc=(0, 0, 0),
    parent=staff_e, mat_=M_BARK)
# Spear tip gold (Gungnir signature)
smooth_cone("staff_tip", r1=0.08, r2=0.008, depth=0.45, segs=12,
            loc=(0, 0, 1.65), parent=staff_e, mat_=M_ODIN_GOLD)
# Runes on shaft
for ri in range(4):
    smooth_sphere(f"staff_rune{ri}", r=0.03, loc=(0, 0, -0.5 + ri*0.35),
                  parent=staff_e, mat_=M_RUNE_GOLD)

# ============ 4 NORNS (Urd, Verdandi, Skuld + extra) cloaked prophetesses ============
def make_norn(name, loc, cloak_mat, action="stand", facing=0, scale=1.0):
    base = empty(name, loc)
    base.rotation_euler = (0, 0, facing)
    # Long cloak cone
    smooth_cone(f"{name}_cloak", r1=0.55*scale, r2=0.35*scale, depth=2.0*scale, segs=18,
                loc=(0, 0, 1.0*scale), parent=base, mat_=cloak_mat)
    # Hood
    smooth_sphere(f"{name}_hood", r=0.32*scale, loc=(0, 0.05*scale, 2.10*scale),
                  parent=base, mat_=cloak_mat, scale=(1.05, 1.0, 0.95))
    # Inner robe
    smooth_cone(f"{name}_robe", r1=0.32*scale, r2=0.25*scale, depth=1.5*scale, segs=14,
                loc=(0, 0, 0.75*scale), parent=base, mat_=M_CLOAK_DARK)
    # Belt cord
    cyl(f"{name}_belt", r=0.30*scale, depth=0.08*scale, segs=16,
        loc=(0, 0, 1.30*scale), parent=base, mat_=M_BARK)
    # Hands holding rune stone or thread of fate
    head_e = empty(f"{name}_he", (0, 0, 2.10*scale), parent=base)
    # Visible face within hood (signature mysterious)
    smooth_sphere(f"{name}_face", r=0.16*scale, segs=18, rings=12,
                  loc=(0, -0.18*scale, 0), parent=head_e, mat_=M_SKIN_NORN)
    # Long silver hair
    smooth_sphere(f"{name}_hair", r=0.20*scale, loc=(0, 0.04*scale, 0.05*scale),
                  parent=head_e, mat_=M_HAIR_SILVER, scale=(1, 1, 0.85))
    # Eyes (glowing pale blue)
    for side in (-1, 1):
        smooth_sphere(f"{name}_eye{side}", r=0.022*scale,
                      loc=(side*0.05*scale, -0.30*scale, 0.02*scale), parent=head_e,
                      mat_=M_ODIN_EYE)
    # Arms (each norn carries something)
    arms_e = []
    for side_idx, side in enumerate((-1, 1)):
        sh = empty(f"{name}_sh{side_idx}", (side*0.30*scale, 0, 2.10*scale), parent=base)
        if action == "weave":
            sh.rotation_euler = (math.radians(-100), 0, math.radians(side*-30))
        elif action == "chant":
            sh.rotation_euler = (math.radians(-130), 0, math.radians(side*-20))
        else:
            sh.rotation_euler = (math.radians(-25), 0, math.radians(side*-15))
        smooth_cone(f"{name}_sleeve{side_idx}", r1=0.15*scale, r2=0.10*scale, depth=0.50*scale, segs=12,
                    loc=(0, 0, -0.25*scale), parent=sh, mat_=cloak_mat)
        cyl(f"{name}_fa{side_idx}", r=0.06*scale, depth=0.35*scale, segs=10,
            loc=(0, 0, -0.60*scale), parent=sh, mat_=M_SKIN_NORN)
        smooth_sphere(f"{name}_hand{side_idx}", r=0.07*scale, loc=(0, 0, -0.80*scale),
                      parent=sh, mat_=M_SKIN_NORN)
        arms_e.append(sh)
    # Glowing rune stone in front
    smooth_sphere(f"{name}_runestone", r=0.10*scale, loc=(0, -0.40*scale, 1.50*scale),
                  parent=base, mat_=M_RUNE_BLUE)
    base["_phase"] = random.uniform(0, math.pi*2)
    return {"root": base, "he": head_e, "arms": arms_e}

norns = []
norn_specs = [
    ("norn_urd", (-3, 8, 0), M_CLOAK_GRAY, "chant", math.radians(0)),     # past
    ("norn_verd", (3, 8, 0), M_CLOAK_WHITE, "weave", math.radians(0)),    # present
    ("norn_skuld", (0, 11, 0), M_CLOAK_DARK, "chant", math.radians(180)), # future
    ("norn_extra", (-6, 5, 0), M_CLOAK_BLOOD, "chant", math.radians(30)), # blood norn
]
for spec in norn_specs:
    name, loc, cloak, act, fac = spec
    n = make_norn(name, loc, cloak, action=act, facing=fac, scale=1.0)
    norns.append(n)

# ============ NIDHOGG DRAGON gnawing root ============
nid_e = empty("nidhogg", loc=(-8, -10, 0.5))
nid_e.rotation_euler = (0, 0, math.radians(35))
# Long sinuous body 12 segments
nid_segs = 12
nid_seg_objs = []
for s in range(nid_segs):
    t_param = s / float(nid_segs - 1)
    seg_x = -t_param * 6.0
    seg_y = math.sin(t_param * math.pi * 1.5) * 1.5
    seg_z = 0.7 - math.sin(t_param * math.pi) * 0.5
    seg_r = 0.50 - t_param * 0.30
    seg = smooth_sphere(f"nid_seg{s}", r=seg_r, segs=18, rings=12,
                        loc=(seg_x, seg_y, seg_z), parent=nid_e, mat_=M_NIDHOGG,
                        scale=(1.4, 1, 1))
    # Spikes on back
    if s % 2 == 0:
        smooth_cone(f"nid_spike{s}", r1=0.10, r2=0.01, depth=0.25, segs=8,
                    loc=(seg_x, seg_y, seg_z + seg_r + 0.12),
                    parent=nid_e, mat_=M_NIDHOGG_BACK)
    nid_seg_objs.append(seg)
# Head (front of body)
head_x, head_y, head_z = 0, 0, 0.7
nid_head_e = empty("nid_head_e", (head_x, head_y, head_z), parent=nid_e)
smooth_sphere("nid_head", r=0.60, segs=22, rings=16, loc=(0, 0, 0),
              parent=nid_head_e, mat_=M_NIDHOGG, scale=(1.6, 1, 0.9))
# Snout
smooth_cone("nid_snout", r1=0.35, r2=0.20, depth=0.50, segs=14,
            loc=(0.80, 0, -0.05), parent=nid_head_e, mat_=M_NIDHOGG).rotation_euler = (0, math.radians(90), 0)
# Fangs (open mouth gnawing root)
for fang_idx in range(3):
    fa = (fang_idx - 1) * 0.30
    smooth_cone(f"nid_fang_u{fang_idx}", r1=0.08, r2=0.01, depth=0.30, segs=10,
                loc=(0.95, fa*0.12, 0.10),
                parent=nid_head_e, mat_=M_FANG).rotation_euler = (0, math.radians(180), 0)
    smooth_cone(f"nid_fang_l{fang_idx}", r1=0.08, r2=0.01, depth=0.30, segs=10,
                loc=(0.95, fa*0.12, -0.15),
                parent=nid_head_e, mat_=M_FANG)
# Glowing red eyes
for side in (-1, 1):
    smooth_sphere(f"nid_eye{side}", r=0.10,
                  loc=(0.30, side*0.20, 0.18), parent=nid_head_e, mat_=M_DRAGON_EYE)
# Horns
for side in (-1, 1):
    horn = smooth_cone(f"nid_horn{side}", r1=0.08, r2=0.02, depth=0.50, segs=10,
                      loc=(-0.15, side*0.25, 0.35), parent=nid_head_e, mat_=M_NIDHOGG_BACK)
    horn.rotation_euler = (math.radians(-25), 0, math.radians(side*25))
# 4 short legs (claws)
for x_idx, x in enumerate((-1.5, -4.5)):
    for y_idx, y_off in enumerate((-0.4, 0.4)):
        leg_e = empty(f"nid_leg_e{x_idx}{y_idx}", (x, y_off, 0.35), parent=nid_e)
        cyl(f"nid_thigh{x_idx}{y_idx}", r=0.13, depth=0.40, segs=10,
            loc=(0, 0, -0.20), parent=leg_e, mat_=M_NIDHOGG)
        # Claws
        for c_idx in range(3):
            smooth_cone(f"nid_claw{x_idx}{y_idx}_{c_idx}", r1=0.05, r2=0.005, depth=0.15, segs=8,
                        loc=((c_idx-1)*0.05, 0, -0.50), parent=leg_e, mat_=M_FANG)
# 2 wings (membranous, folded close to body)
for side in (-1, 1):
    w = beveled_cube(f"nid_wing{side}", (0.90, 0.50, 0.04), bevel_offset=0.02,
                     loc=(-2, side*0.40, 1.0), parent=nid_e, mat_=M_NIDHOGG_BACK)
    w.rotation_euler = (math.radians(side*30), math.radians(10), 0)

# ============ RATATOSKR squirrel messenger ============
rat_e = empty("ratatoskr", loc=(2.5, 0, 6.5))
# Body
smooth_sphere("rat_body", r=0.22, segs=20, rings=14, loc=(0, 0, 0),
              parent=rat_e, mat_=M_SQUIRREL, scale=(1.5, 1, 1))
# Belly
smooth_sphere("rat_belly", r=0.18, loc=(0, -0.10, -0.05),
              parent=rat_e, mat_=M_SQUIRREL_BELLY, scale=(1.2, 1, 0.7))
# Head
rat_head_e = empty("rat_he", (0.30, 0, 0.10), parent=rat_e)
smooth_sphere("rat_head", r=0.18, segs=18, rings=12,
              loc=(0, 0, 0), parent=rat_head_e, mat_=M_SQUIRREL)
# Snout
smooth_cone("rat_snout", r1=0.10, r2=0.06, depth=0.18, segs=12,
            loc=(0.18, 0, -0.04), parent=rat_head_e,
            mat_=M_SQUIRREL).rotation_euler = (0, math.radians(90), 0)
# Eyes (large beady)
for side in (-1, 1):
    smooth_sphere(f"rat_eye{side}", r=0.04,
                  loc=(0.08, side*0.10, 0.06), parent=rat_head_e,
                  mat_=mat(f"rat_ew{side}", (0.05,0.05,0.05,1), 0, 0.4))
# Ears (large tufted)
for side in (-1, 1):
    ear = smooth_cone(f"rat_ear{side}", r1=0.08, r2=0.01, depth=0.18, segs=10,
                      loc=(0, side*0.12, 0.20), parent=rat_head_e, mat_=M_SQUIRREL)
    ear.rotation_euler = (0, math.radians(-15), math.radians(side*10))
# 4 legs
for x_idx, x in enumerate((0.18, -0.18)):
    for y_idx, y_off in enumerate((-0.15, 0.15)):
        cyl(f"rat_leg{x_idx}{y_idx}", r=0.05, depth=0.25, segs=10,
            loc=(x, y_off, -0.20), parent=rat_e, mat_=M_SQUIRREL)
# MASSIVE BUSHY TAIL (signature squirrel)
tail_e = empty("rat_tail_e", (-0.30, 0, 0.10), parent=rat_e)
for ti in range(5):
    smooth_sphere(f"rat_tail{ti}", r=0.18 - ti*0.015,
                  loc=(-ti*0.18, 0, ti*0.15),
                  parent=tail_e, mat_=M_SQUIRREL,
                  scale=(1, 0.85, 1.2))
# Tail tip
smooth_sphere("rat_tail_tip", r=0.20, loc=(-1.0, 0, 0.75),
              parent=tail_e, mat_=M_SQUIRREL_BELLY)
rat_e["_phase"] = 0

# ============ 2 RAVENS Huginn (Thought) + Muninn (Memory) ============
def make_raven(name, loc):
    base = empty(name, loc)
    smooth_sphere(f"{name}_body", r=0.30, segs=20, rings=14, loc=(0, 0, 0),
                  parent=base, mat_=M_RAVEN, scale=(1.7, 1, 1))
    # Iridescent neck shimmer
    smooth_sphere(f"{name}_neck", r=0.18, loc=(0.30, 0, 0.10),
                  parent=base, mat_=M_RAVEN_SHINE)
    # Head
    head_e = empty(f"{name}_he", (0.45, 0, 0.15), parent=base)
    smooth_sphere(f"{name}_head", r=0.18, segs=18, rings=12, loc=(0, 0, 0),
                  parent=head_e, mat_=M_RAVEN)
    # Beak (long, pointed)
    smooth_cone(f"{name}_beak", r1=0.08, r2=0.01, depth=0.30, segs=10,
                loc=(0.25, 0, -0.02), parent=head_e,
                mat_=M_RAVEN_SHINE).rotation_euler = (0, math.radians(90), 0)
    # Eyes (yellow glowing)
    for side in (-1, 1):
        smooth_sphere(f"{name}_eye{side}", r=0.05,
                      loc=(0.10, side*0.10, 0.05), parent=head_e, mat_=M_RAVEN_EYE)
    # Wings (spread for flying)
    wings = []
    for side in (-1, 1):
        w_e = empty(f"{name}_we{side}", (0, side*0.20, 0.05), parent=base)
        beveled_cube(f"{name}_w_m{side}", (0.50, 0.90, 0.05), bevel_offset=0.02,
                     loc=(0, side*0.50, 0), parent=w_e, mat_=M_RAVEN)
        # Wing tip
        beveled_cube(f"{name}_w_t{side}", (0.40, 0.40, 0.04), bevel_offset=0.02,
                     loc=(0, side*1.00, 0), parent=w_e, mat_=M_RAVEN_SHINE)
        wings.append((w_e, side))
    # Tail
    beveled_cube(f"{name}_tail", (0.35, 0.25, 0.05), loc=(-0.45, 0, 0),
                 parent=base, mat_=M_RAVEN)
    base["_phase"] = random.uniform(0, math.pi*2)
    return {"root": base, "he": head_e, "wings": wings}

ravens = [
    make_raven("huginn", (4, -3, 8.5)),
    make_raven("muninn", (-4, -3, 9.0)),
]

# ============================================================
# ⭐ 800 COSMIC LEAVES tombant + flotter (PARTICULE THÉMATIQUE OBLIGATOIRE)
# ============================================================
cosmic_leaves = []
for i in range(800):
    px = random.uniform(-40, 40)
    py = random.uniform(-40, 40)
    pz = random.uniform(2, 30)
    col_idx = i % 4
    if col_idx == 0: color = M_LEAF_GOLD
    elif col_idx == 1: color = M_LEAF_BRONZE
    elif col_idx == 2: color = M_LEAF_GREEN_DEEP
    else: color = M_LEAF_AUTUMN
    leaf = smooth_sphere(f"cleaf{i}", r=random.uniform(0.10, 0.16), segs=10, rings=6,
                         loc=(px, py, pz), mat_=color,
                         scale=(1.7, 0.6, 0.15))
    leaf.rotation_euler = (random.uniform(0, math.pi*2),
                           random.uniform(0, math.pi*2),
                           random.uniform(0, math.pi*2))
    leaf["_phase"] = random.uniform(0, math.pi*2)
    leaf["_base_x"] = px; leaf["_base_y"] = py; leaf["_base_z"] = pz
    leaf["_speed"] = random.uniform(0.3, 1.2)
    leaf["_drift_x"] = random.uniform(-2.0, 2.0)
    leaf["_drift_y"] = random.uniform(-2.0, 2.0)
    cosmic_leaves.append(leaf)

# ============ ANIMATION ============
fps = 30; duration_s = 6; total_frames = fps * duration_s

# Yggdrasil sway majestic
for f in range(1, total_frames + 1, 5):
    t = (f - 1) / fps
    yggdrasil_e.rotation_euler = (math.sin(t * 0.4) * math.radians(1.5),
                                    math.cos(t * 0.3) * math.radians(1.2),
                                    0)
    yggdrasil_e.keyframe_insert("rotation_euler", frame=f)

# Branches sway propagated
for b_e in branches:
    phase = hash(b_e.name) % 100 * 0.05
    base_rx = b_e.rotation_euler.x
    base_ry = b_e.rotation_euler.y
    base_rz = b_e.rotation_euler.z
    for f in range(1, total_frames + 1, 5):
        t = (f - 1) / fps
        b_e.rotation_euler = (base_rx + math.sin(t * 0.8 + phase) * math.radians(2),
                               base_ry + math.cos(t * 0.7 + phase) * math.radians(2),
                               base_rz)
        b_e.keyframe_insert("rotation_euler", frame=f)

# Aurora ribbons wave
for i in range(3):
    a_obj = bpy.data.objects[f"aurora_e{i}"]
    phase = a_obj["_phase"]
    base_x = a_obj.location.x
    base_z = a_obj.location.z
    for f in range(1, total_frames + 1, 4):
        t = (f - 1) / fps
        a_obj.location.x = base_x + math.sin(t * 0.6 + phase) * 4
        a_obj.location.z = base_z + math.cos(t * 0.5 + phase) * 1.5
        a_obj.keyframe_insert("location", frame=f)

# Odin animations - cape sway + head turn slow
odin_head_e_o = bpy.data.objects.get("odin_head_e")
for f in range(1, total_frames + 1, 5):
    t = (f - 1) / fps
    odin_e.rotation_euler = (math.sin(t * 0.5) * math.radians(2),
                              math.cos(t * 0.4) * math.radians(1.5),
                              math.radians(-130))
    odin_e.keyframe_insert("rotation_euler", frame=f)
    if odin_head_e_o:
        odin_head_e_o.rotation_euler = (0, 0, math.sin(t * 0.7) * math.radians(15))
        odin_head_e_o.keyframe_insert("rotation_euler", frame=f)

# Norns animations
for n in norns:
    phase = n["root"]["_phase"]
    base_z = n["root"].location.z
    for f in range(1, total_frames + 1, 4):
        t = (f - 1) / fps
        # Body sway
        n["root"].location.z = base_z + math.sin(t * 1.0 + phase) * 0.04
        n["root"].rotation_euler = (math.sin(t * 0.8 + phase) * math.radians(3),
                                     math.cos(t * 0.6 + phase) * math.radians(2),
                                     n["root"].rotation_euler.z)
        n["root"].keyframe_insert("location", frame=f)
        n["root"].keyframe_insert("rotation_euler", frame=f)
        # Head turn
        n["he"].rotation_euler = (math.sin(t * 0.8 + phase) * math.radians(8), 0,
                                    math.sin(t * 0.6 + phase) * math.radians(15))
        n["he"].keyframe_insert("rotation_euler", frame=f)
        # Arms gesture
        for ai, arm in enumerate(n["arms"]):
            base_rx = arm.rotation_euler.x
            base_rz = arm.rotation_euler.z
            wave = math.sin(t * 2.0 + phase + ai * math.pi) * math.radians(10)
            arm.rotation_euler = (base_rx + wave, 0, base_rz)
            arm.keyframe_insert("rotation_euler", frame=f)

# Nidhogg dragon - body ondule (snake-like)
for f in range(1, total_frames + 1, 3):
    t = (f - 1) / fps
    nid_e.rotation_euler = (math.sin(t * 1.2) * math.radians(3),
                             0,
                             math.radians(35) + math.cos(t * 0.8) * math.radians(5))
    nid_e.keyframe_insert("rotation_euler", frame=f)
    # Body segments ondule wave
    for s_idx, seg in enumerate(nid_seg_objs):
        # Slight wave
        base_x = -((s_idx / float(nid_segs - 1)) * 6.0)
        wave_offset = math.sin(t * 2.0 + s_idx * 0.4) * 0.2
        seg.location.y = math.sin((s_idx / float(nid_segs - 1)) * math.pi * 1.5) * 1.5 + wave_offset
        seg.keyframe_insert("location", frame=f)
# Head bites (rumbles)
for f in range(1, total_frames + 1, 4):
    t = (f - 1) / fps
    nid_head_e.rotation_euler = (math.sin(t * 3.0) * math.radians(8), 0,
                                  math.cos(t * 2.5) * math.radians(15))
    nid_head_e.keyframe_insert("rotation_euler", frame=f)

# Eye pulse (red glow)
for side in (-1, 1):
    eye_obj = bpy.data.objects.get(f"nid_eye{side}")
    if eye_obj:
        for f in range(1, total_frames + 1, 4):
            t = (f - 1) / fps
            s = 1 + math.sin(t * 4.0) * 0.30
            eye_obj.scale = (s, s, s)
            eye_obj.keyframe_insert("scale", frame=f)

# Ratatoskr runs branches
for f in range(1, total_frames + 1, 3):
    t = (f - 1) / fps
    # Orbit around trunk + climb up/down
    a = t * 1.5
    rad = 2.8 + math.sin(t * 0.5) * 0.3
    rat_e.location = (rad * math.cos(a), rad * math.sin(a),
                       6.5 + math.sin(t * 1.2) * 2.0)
    rat_e.rotation_euler = (0, 0, a + math.pi/2)
    rat_e.keyframe_insert("location", frame=f)
    rat_e.keyframe_insert("rotation_euler", frame=f)

# Ravens orbit + wing flap
for r in ravens:
    phase = r["root"]["_phase"]
    base_x = r["root"].location.x
    base_y = r["root"].location.y
    base_z = r["root"].location.z
    for f in range(1, total_frames + 1, 3):
        t = (f - 1) / fps
        # Orbit around tree
        a = t * 0.8 + phase
        rad = 6 + math.sin(t * 0.5) * 1.5
        r["root"].location = (rad * math.cos(a), rad * math.sin(a),
                               base_z + math.sin(t * 1.2 + phase) * 1.0)
        r["root"].rotation_euler = (0, 0, a + math.pi/2)
        r["root"].keyframe_insert("location", frame=f)
        r["root"].keyframe_insert("rotation_euler", frame=f)
        # Wing flap
        flap = math.sin(t * 5.0 + phase) * math.radians(35)
        for w_e, side in r["wings"]:
            w_e.rotation_euler = (side * flap, 0, 0)
            w_e.keyframe_insert("rotation_euler", frame=f)
        # Head
        r["he"].rotation_euler = (math.sin(t * 2.0 + phase) * math.radians(10), 0,
                                    math.sin(t * 1.5 + phase) * math.radians(15))
        r["he"].keyframe_insert("rotation_euler", frame=f)

# Nebulas drift
for obj in bpy.data.objects:
    if obj.name.startswith("nebula_e"):
        phase = obj["_phase"]
        bx, by = obj.location.x, obj.location.y
        for f in range(1, total_frames + 1, 8):
            t = (f - 1) / fps
            obj.location = (bx + math.sin(t * 0.3 + phase) * 1.5,
                            by + math.cos(t * 0.25 + phase) * 1.5,
                            obj.location.z)
            obj.keyframe_insert("location", frame=f)

# ============================================================
# ⭐⭐⭐ 800 COSMIC LEAVES tombant (signature Yggdrasil)
# ============================================================
for lf in cosmic_leaves:
    phase = lf["_phase"]; speed = lf["_speed"]
    bx, by, bz = lf["_base_x"], lf["_base_y"], lf["_base_z"]
    drift_x = lf["_drift_x"]; drift_y = lf["_drift_y"]
    for f in range(1, total_frames + 1, 5):
        t = (f - 1) / fps
        z = bz - (speed * t) % 30
        x = bx + drift_x * math.sin(t * 1.3 + phase) * 0.7
        y = by + drift_y * math.cos(t * 1.1 + phase) * 0.7
        rx = phase + t * 2.0
        ry = phase + t * 1.6
        rz = phase + t * 2.2
        lf.location = (x, y, max(0.05, z))
        lf.rotation_euler = (rx, ry, rz)
        lf.keyframe_insert("location", frame=f)
        lf.keyframe_insert("rotation_euler", frame=f)

# ============ EXPORT ============
out_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "public", "_pbr_test")
out_dir = os.path.normpath(out_dir)
os.makedirs(out_dir, exist_ok=True)
out_glb = os.path.join(out_dir, "pbr_yggdrasil_proc.glb")

bpy.ops.object.select_all(action='SELECT')
bpy.ops.export_scene.gltf(
    filepath=out_glb, export_format='GLB',
    export_animations=True, export_apply=False, export_yup=True, use_selection=False,
)
size_mb = os.path.getsize(out_glb) / (1024 * 1024)
print(f"[proc_norse_yggdrasil_world_tree] DONE → {out_glb} ({size_mb:.2f} MB)")
print("[proc_norse_yggdrasil_world_tree] ONE ground + Yggdrasil 14-seg trunk + 9 branches + 3 mega roots + Odin + 4 Norns + Nidhogg dragon + Ratatoskr + Huginn/Muninn + aurora + 800 COSMIC LEAVES")
print("⭐ FIXES: 1 ground + 800 cosmic leaves Z descent + spiral drift + tumble (signature Yggdrasil mandatory) ⭐")
