"""
proc_indonesian_bali_temple_kecak.py — 283e procédural AuroraIA (148e qualité)
Indonesia Bali Uluwatu temple kecak: cliff temple + 8 Bali pagodas meru + 6 kecak dancers + 4 Bali dancers gold + rice paddies + Bali flag + 600 frangipani petals + 400 fireflies
FIXES : 1 ground rice paddies + signature petals + fireflies
"""
import bpy, bmesh, math, random, os

random.seed(0x70AB283)

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

# Sky tropical sunset Bali
M_SKY = mat("sky", (1.0, 0.55, 0.45, 1.0), 0.0, 0.7, emission=(1.0,0.55,0.45), emission_strength=2.5)
M_SKY_LOW = mat("sky_l", (0.92, 0.45, 0.62, 1.0), 0.0, 0.7, emission=(0.90,0.45,0.62), emission_strength=2.0)
M_SUN = mat("sun", (1.0, 0.80, 0.35, 1.0), 0.0, 0.1, emission=(1.0,0.80,0.35), emission_strength=22.0)

# Rice paddy ground
M_RICE_GREEN = mat("rg", (0.42, 0.68, 0.30, 1.0), 0.0, 0.65, emission=(0.40,0.65,0.30), emission_strength=0.4)
M_RICE_GOLD = mat("rgo", (0.82, 0.78, 0.30, 1.0), 0.0, 0.55, emission=(0.80,0.75,0.30), emission_strength=0.5)
M_WATER_PADDY = mat("wp", (0.45, 0.62, 0.55, 1.0), 0.2, 0.20, emission=(0.42,0.60,0.52), emission_strength=1.0, alpha=0.78)
M_DIRT = mat("d", (0.42, 0.30, 0.20, 1.0), 0.0, 0.92)
M_GRASS = mat("g", (0.32, 0.62, 0.30, 1.0), 0.0, 0.65)

# Stone temple
M_STONE_GRAY = mat("sg", (0.55, 0.50, 0.45, 1.0), 0.0, 0.85, emission=(0.52,0.50,0.45), emission_strength=0.3)
M_STONE_DARK = mat("sd", (0.32, 0.30, 0.28, 1.0), 0.0, 0.92)
M_STONE_LIGHT = mat("sl", (0.78, 0.72, 0.60, 1.0), 0.0, 0.75, emission=(0.75,0.70,0.60), emission_strength=0.4)
M_LAVA_STONE = mat("ls", (0.18, 0.15, 0.13, 1.0), 0.0, 0.92)

# Meru roof (signature black thatch)
M_THATCH_BLACK = mat("tb", (0.10, 0.08, 0.06, 1.0), 0.0, 0.95)
M_THATCH_DARK = mat("td", (0.22, 0.18, 0.14, 1.0), 0.0, 0.92)
M_GOLD = mat("go", (0.95, 0.78, 0.20, 1.0), 0.8, 0.20, emission=(0.92,0.75,0.20), emission_strength=1.2)

# Cliff
M_CLIFF = mat("cl", (0.65, 0.55, 0.45, 1.0), 0.0, 0.88, emission=(0.62,0.55,0.45), emission_strength=0.3)
M_OCEAN = mat("oc", (0.20, 0.55, 0.78, 1.0), 0.2, 0.20, emission=(0.20,0.52,0.75), emission_strength=1.5, alpha=0.75)
M_FOAM = mat("fm", (0.95, 0.95, 0.92, 1.0), 0.0, 0.30, emission=(0.92,0.92,0.90), emission_strength=1.5, alpha=0.65)

# Skin Bali
M_SKIN = mat("sk", (0.85, 0.65, 0.45, 1.0), 0.0, 0.55, emission=(0.82,0.62,0.45), emission_strength=0.3)
M_HAIR_BLACK = mat("hb", (0.10, 0.06, 0.05, 1.0), 0.0, 0.85)

# Sarong (signature Balinese ceremonial)
M_SARONG_RED = mat("sr", (0.78, 0.18, 0.20, 1.0), 0.0, 0.55, emission=(0.75,0.18,0.20), emission_strength=0.5)
M_SARONG_GOLD = mat("sgo", (0.92, 0.72, 0.20, 1.0), 0.4, 0.30, emission=(0.88,0.70,0.20), emission_strength=0.8)
M_SARONG_BLACK_WHITE = mat("sbw", (0.55, 0.55, 0.55, 1.0), 0.0, 0.65, emission=(0.52,0.52,0.52), emission_strength=0.4)  # Poleng signature

# Bali dancer dress (signature legong)
M_LEGONG_GOLD = mat("lg", (1.0, 0.78, 0.20, 1.0), 0.6, 0.25, emission=(0.95,0.75,0.20), emission_strength=1.0)
M_LEGONG_PURPLE = mat("lp", (0.55, 0.20, 0.85, 1.0), 0.0, 0.45, emission=(0.52,0.20,0.82), emission_strength=0.7)
M_LEGONG_RED = mat("lr", (0.92, 0.18, 0.22, 1.0), 0.0, 0.45, emission=(0.88,0.18,0.22), emission_strength=0.7)

# Crown gold (signature Balinese tiara)
M_CROWN_GOLD = mat("cg", (1.0, 0.85, 0.20, 1.0), 0.9, 0.10, emission=(0.95,0.82,0.20), emission_strength=2.0)

# Kecak men sarong (checkered black white poleng signature)
M_POLENG = mat("pl", (0.55, 0.55, 0.55, 1.0), 0.0, 0.65)

# Fire
M_FIRE = mat("f", (1.0, 0.55, 0.15, 1.0), 0.2, 0.10, emission=(1.0,0.55,0.15), emission_strength=18.0, alpha=0.85)
M_FIRE_HOT = mat("fh", (1.0, 0.92, 0.30, 1.0), 0.2, 0.10, emission=(1.0,0.92,0.30), emission_strength=25.0, alpha=0.90)
M_TORCH = mat("tc", (0.55, 0.32, 0.15, 1.0), 0.0, 0.85)

# Frangipani petals (signature Bali)
M_FRANG_WHITE = mat("fw", (0.98, 0.95, 0.92, 1.0), 0.0, 0.40, emission=(0.95,0.92,0.88), emission_strength=2.0)
M_FRANG_YELLOW = mat("fy", (1.0, 0.92, 0.45, 1.0), 0.0, 0.40, emission=(0.95,0.88,0.45), emission_strength=2.2)
M_FRANG_PINK = mat("fp", (1.0, 0.65, 0.75, 1.0), 0.0, 0.40, emission=(0.95,0.65,0.72), emission_strength=2.0)
FRANG_COLORS = [M_FRANG_WHITE, M_FRANG_YELLOW, M_FRANG_PINK]

# Firefly (signature)
M_FIREFLY = mat("ff", (1.0, 1.0, 0.55, 1.0), 0.0, 0.05, emission=(0.95,0.95,0.55), emission_strength=8.0)
M_FIREFLY_BODY = mat("ffb", (0.42, 0.32, 0.18, 1.0), 0.0, 0.55)

# Eyes
M_EYE = mat("ed", (0.05, 0.04, 0.04, 1.0), 0.0, 0.20)
M_LIPS_RED = mat("lr2", (0.85, 0.20, 0.20, 1.0), 0.0, 0.30, emission=(0.82,0.20,0.20), emission_strength=0.5)

# Bali flag (Indonesia)
M_FLAG_RED = mat("fr_b", (0.85, 0.18, 0.20, 1.0), 0.0, 0.45, emission=(0.82,0.18,0.20), emission_strength=1.0)
M_FLAG_WHITE = mat("fw_b", (0.95, 0.95, 0.92, 1.0), 0.0, 0.45, emission=(0.92,0.92,0.90), emission_strength=0.8)

# ============ SKY ============
sky = smooth_sphere("sky", r=320, segs=32, rings=20, loc=(0,0,0), mat_=M_SKY)
sky.scale = (1,1,0.6)
sky_l = smooth_sphere("sky_l", r=280, segs=28, rings=16, loc=(0,0,5), mat_=M_SKY_LOW)
sky_l.scale = (1,1,0.3)
sun = smooth_sphere("sun", r=12, segs=24, rings=18, loc=(0, 110, 18), mat_=M_SUN)
for sh in range(4):
    smooth_sphere(f"sun_h{sh}", r=12 + sh*1.3, segs=24, rings=18, loc=(0, 110, 18), mat_=M_SUN)

# ============ ONE clean rice paddy ground (signature terraces) ============
ground = beveled_cube("ground", (250, 250, 0.5), bevel_offset=0.10, loc=(0, 0, -0.25), mat_=M_RICE_GREEN)
# Rice paddy terraces (organic 3D bumps with water)
for hi in range(150):
    a = random.uniform(0, math.pi*2); rad = random.uniform(40, 110)
    smooth_sphere(f"hl{hi}", r=random.uniform(2, 4), segs=12, rings=8,
                  loc=(rad*math.cos(a), rad*math.sin(a), 0.15),
                  mat_=M_RICE_GOLD if hi % 3 == 0 else M_RICE_GREEN, scale=(1.5, 1.4, 0.2))
# Rice stalks (small)
for si in range(300):
    a = random.uniform(0, math.pi*2); rad = random.uniform(30, 115)
    cyl(f"rs{si}", r=0.03, depth=0.35, segs=4,
        loc=(rad*math.cos(a), rad*math.sin(a), 0.20),
        mat_=M_RICE_GOLD)
# Water in paddies
for wi in range(20):
    wa = random.uniform(0, math.pi*2); wr = random.uniform(40, 100)
    cyl(f"wp{wi}", r=random.uniform(3, 5), depth=0.04, segs=14,
        loc=(wa*math.cos(wa) if abs(wa*math.cos(wa)) < 100 else 80, math.sin(wa)*wr, 0.05),
        mat_=M_WATER_PADDY)

# ============ ULUWATU CLIFF + OCEAN (signature) ============
cliff_e = empty("cliff", (0, 55, 0))
# Cliff edge
beveled_cube("cl_b", (60, 20, 8), bevel_offset=0.30, loc=(0, 0, 4),
             parent=cliff_e, mat_=M_CLIFF)
# Cliff face drops to ocean
for ci in range(8):
    smooth_sphere(f"cl_s{ci}", r=4, segs=12, rings=10,
                  loc=(random.uniform(-25, 25), random.uniform(-12, 12), random.uniform(2, 7)),
                  parent=cliff_e, mat_=M_CLIFF, scale=(1.5, 1.4, 1.0))
# Ocean below cliff
ocean_e = empty("ocean", (0, 85, -2), parent=cliff_e)
beveled_cube("oc", (200, 80, 0.20), bevel_offset=0.08, loc=(0, 0, 0.20),
             parent=ocean_e, mat_=M_OCEAN)
# Wave foam at base of cliff
for fi in range(30):
    fx = random.uniform(-50, 50); fy = random.uniform(-15, 15)
    cyl(f"oc_f{fi}", r=random.uniform(0.5, 1.0), depth=0.05, segs=14,
        loc=(fx, fy, 0.30), parent=ocean_e, mat_=M_FOAM)

# ============ 8 BALI PAGODAS MERU (signature multi-tier black thatch) ============
def make_meru(name, loc, n_tiers, base_size, scale=1.0):
    base = empty(name, loc)
    # Stone base/plinth
    for pi in range(3):
        pz = pi * 0.4
        ps = base_size + 1.5 - pi * 0.5
        beveled_cube(f"{name}_pl{pi}", (ps, ps, 0.4), bevel_offset=0.08, loc=(0, 0, pz + 0.2),
                     parent=base, mat_=M_LAVA_STONE)
    base_z_start = 1.2
    # Sanctum walls (signature stone carved)
    beveled_cube(f"{name}_sn", (base_size, base_size, 2.5), bevel_offset=0.10,
                 loc=(0, 0, base_z_start + 1.25), parent=base, mat_=M_STONE_LIGHT)
    # Gold trim around sanctum
    for ti in range(4):
        beveled_cube(f"{name}_gt{ti}", (base_size + 0.05, base_size + 0.05, 0.10), bevel_offset=0.02,
                     loc=(0, 0, base_z_start + ti*0.6 + 0.20), parent=base, mat_=M_GOLD)
    # Doorway dark
    beveled_cube(f"{name}_d", (0.8, 0.10, 1.8), bevel_offset=0.04,
                 loc=(0, -base_size/2 - 0.05, base_z_start + 0.90), parent=base, mat_=M_LAVA_STONE)
    # MULTI-TIER MERU ROOFS (signature - always odd number 1/3/5/7/9/11)
    current_z = base_z_start + 2.5
    current_size = base_size + 0.5
    for ti in range(n_tiers):
        # Each roof tier
        roof_size = current_size + 0.6
        # Slanted roof slabs (4 sides)
        for side in range(4):
            sa = side * math.pi / 2
            slope_e = empty(f"{name}_rs{ti}_{side}_e", (0, 0, current_z + 0.35), parent=base)
            slope_e.rotation_euler = (math.radians(-40), 0, sa)
            beveled_cube(f"{name}_rs{ti}_{side}", (roof_size + 0.3, roof_size*0.7, 0.18), bevel_offset=0.04,
                         loc=(0, roof_size/2 + 0.4, 0), parent=slope_e, mat_=M_THATCH_BLACK)
        # Thatch texture lines
        for tri in range(int(roof_size)):
            beveled_cube(f"{name}_tt{ti}_{tri}", (roof_size + 0.4, 0.10, 0.04), bevel_offset=0.01,
                         loc=(0, -roof_size/2 - 0.1, current_z + 0.10), parent=base, mat_=M_THATCH_DARK)
        # Gold finials at corners
        for cri in range(4):
            cra = (cri / 4.0) * math.pi * 2 + math.pi/4
            smooth_cone(f"{name}_fi{ti}_{cri}", r1=0.08, r2=0.02, depth=0.25, segs=8,
                        loc=(math.cos(cra)*roof_size/2, math.sin(cra)*roof_size/2, current_z + 0.5),
                        parent=base, mat_=M_GOLD)
        # Middle wall section (small dark)
        wall_h = 0.5
        if ti < n_tiers - 1:
            current_size *= 0.85
            beveled_cube(f"{name}_w{ti}", (current_size, current_size, wall_h), bevel_offset=0.04,
                         loc=(0, 0, current_z + 0.7), parent=base, mat_=M_LAVA_STONE)
        current_z += 0.7 + wall_h
    # Final spire top (signature)
    smooth_cone(f"{name}_sp", r1=0.20, r2=0.04, depth=0.8, segs=12,
                loc=(0, 0, current_z + 0.4), parent=base, mat_=M_GOLD)
    smooth_sphere(f"{name}_spb", r=0.15, loc=(0, 0, current_z + 0.1),
                  parent=base, mat_=M_GOLD)
    return base

# 8 Meru pagodas with different tier counts (signature 3, 5, 7, 9, 11)
meru_pos = [(-25, -10, 5, 3), (25, -10, 7, 4), (-15, -25, 9, 5),
             (15, -25, 5, 3), (-30, 5, 7, 4), (30, 5, 5, 3),
             (-10, -5, 11, 6), (10, -5, 9, 5)]  # Tallest in middle
for i, (mx, my, nt, bs) in enumerate(meru_pos):
    make_meru(f"mer{i}", (mx, my, 0), nt, bs)

# ============ 6 KECAK DANCERS (signature monkey chant circle) ============
def make_kecak_dancer(name, loc, scale=1.0, facing=0):
    base = empty(name, loc)
    base.rotation_euler = (0, 0, facing)
    # Bare chest with checkered POLENG sarong waist (signature)
    smooth_cone(f"{name}_to", r1=0.32, r2=0.36, depth=0.75, segs=14, loc=(0, 0, 1.20),
                parent=base, mat_=M_SKIN)
    # Poleng sarong (signature black/white checkered cloth around waist)
    cyl(f"{name}_sa", r=0.40, depth=0.55, segs=14, loc=(0, 0, 0.62),
        parent=base, mat_=M_POLENG)
    # Checker pattern (signature)
    for ci in range(8):
        ca = (ci / 8.0) * math.pi * 2
        for cj in range(2):
            beveled_cube(f"{name}_chk{ci}_{cj}", (0.10, 0.08, 0.12), bevel_offset=0.01,
                         loc=(math.cos(ca)*0.40, math.sin(ca)*0.40, 0.50 + cj*0.20),
                         parent=base, mat_=M_THATCH_BLACK if (ci+cj) % 2 else M_FLAG_WHITE)
    # Legs bare
    for side in (-1, 1):
        cyl(f"{name}_l{side}", r=0.11, depth=0.55, segs=10,
            loc=(side*0.13, 0, 0.35), parent=base, mat_=M_SKIN)
    # Bare feet
    for side in (-1, 1):
        beveled_cube(f"{name}_f{side}", (0.10, 0.22, 0.05), bevel_offset=0.01,
                     loc=(side*0.13, 0.04, 0.03), parent=base, mat_=M_SKIN)
    # ARMS RAISED (signature chak chak gesture)
    for side_idx, side in enumerate((-1, 1)):
        sh = empty(f"{name}_a{side_idx}", (side*0.32, 0, 1.55), parent=base)
        sh.rotation_euler = (math.radians(-160), 0, math.radians(side*30))
        cyl(f"{name}_ua{side_idx}", r=0.08, depth=0.45, segs=10, loc=(0, 0, -0.22),
            parent=sh, mat_=M_SKIN)
        # Forearm raised straight up
        cyl(f"{name}_fa{side_idx}", r=0.07, depth=0.40, segs=10, loc=(0, 0, -0.62),
            parent=sh, mat_=M_SKIN)
        # Open palm with spread fingers (signature)
        for fi in range(5):
            cyl(f"{name}_fn{side_idx}_{fi}", r=0.018, depth=0.08, segs=6,
                loc=((fi - 2)*0.025, 0, -0.85), parent=sh, mat_=M_SKIN)
    # Head
    head_k_e = empty(f"{name}_he", (0, 0, 1.95), parent=base)
    smooth_sphere(f"{name}_h", r=0.18, segs=18, rings=14, loc=(0, 0, 0),
                  parent=head_k_e, mat_=M_SKIN)
    # Hair black
    for hi in range(15):
        ha = random.uniform(0, math.pi*2)
        cyl(f"{name}_hr{hi}", r=0.04, depth=0.10, segs=6,
            loc=(math.cos(ha)*0.12, math.sin(ha)*0.10, 0.13),
            parent=head_k_e, mat_=M_HAIR_BLACK)
    # Eyes wide
    for side in (-1, 1):
        smooth_sphere(f"{name}_ey{side}", r=0.03, loc=(side*0.06, -0.15, 0.03),
                      parent=head_k_e, mat_=M_FLAG_WHITE)
        smooth_sphere(f"{name}_ep{side}", r=0.020, loc=(side*0.06, -0.17, 0.03),
                      parent=head_k_e, mat_=M_EYE)
    # Open mouth (signature chanting)
    smooth_sphere(f"{name}_mo", r=0.05, loc=(0, -0.16, -0.10),
                  parent=head_k_e, mat_=M_LIPS_RED, scale=(1, 1, 1.3))
    base["_phase"] = random.uniform(0, math.pi*2)
    return {"root": base, "he": head_k_e}

kecaks = []
# Circle of kecak dancers (signature seated circle)
for i in range(6):
    ka_circle = (i / 6.0) * math.pi * 2
    kx = math.cos(ka_circle) * 12
    ky = math.sin(ka_circle) * 12 - 5
    # Face center
    facing = ka_circle + math.pi
    k = make_kecak_dancer(f"kc{i}", (kx, ky, 0), facing=facing)
    kecaks.append(k)

# ============ 4 BALI LEGONG DANCERS with GOLD CROWNS (signature) ============
def make_legong_dancer(name, loc, scale=1.0, facing=0):
    base = empty(name, loc)
    base.rotation_euler = (0, 0, facing)
    # Costume body
    dress_col = random.choice([M_LEGONG_PURPLE, M_LEGONG_RED])
    # Top
    smooth_cone(f"{name}_to", r1=0.28, r2=0.32, depth=0.70, segs=14, loc=(0, 0, 1.30),
                parent=base, mat_=dress_col)
    # Gold sash diagonal (signature)
    beveled_cube(f"{name}_gs", (0.65, 0.06, 0.30), bevel_offset=0.04,
                 loc=(0, -0.30, 1.35), parent=base, mat_=M_LEGONG_GOLD).rotation_euler = (0, math.radians(30), 0)
    # Long sarong skirt (signature gold/colored)
    skirt_e = empty(f"{name}_sk", (0, 0, 0.95), parent=base)
    for ri in range(2):
        rz = -ri * 0.20
        rr = 0.34 + ri * 0.05
        for rj in range(20):
            rja = (rj / 20.0) * math.pi * 2
            beveled_cube(f"{name}_r{ri}_{rj}", (0.06, 0.10, 0.55), bevel_offset=0.01,
                         loc=(math.cos(rja)*rr, math.sin(rja)*rr, rz - 0.27),
                         parent=skirt_e, mat_=dress_col if ri == 0 else M_LEGONG_GOLD).rotation_euler = (math.cos(rja)*0.10, math.sin(rja)*0.10, rja)
    # Legs
    for side in (-1, 1):
        cyl(f"{name}_l{side}", r=0.10, depth=0.80, segs=10,
            loc=(side*0.13, 0, 0.43), parent=base, mat_=M_SKIN)
    # Arms (graceful pose - hands turned up signature)
    for side_idx, side in enumerate((-1, 1)):
        sh = empty(f"{name}_a{side_idx}", (side*0.30, 0, 1.60), parent=base)
        sh.rotation_euler = (math.radians(-90), 0, math.radians(side*70))
        cyl(f"{name}_ua{side_idx}", r=0.07, depth=0.40, segs=10, loc=(0, 0, -0.20),
            parent=sh, mat_=M_SKIN)
        # Forearm bent up
        fa_e = empty(f"{name}_fae{side_idx}", (0, 0, -0.40), parent=sh)
        fa_e.rotation_euler = (math.radians(80), 0, 0)
        cyl(f"{name}_fa{side_idx}", r=0.06, depth=0.30, segs=10, loc=(0, 0, -0.15),
            parent=fa_e, mat_=M_SKIN)
        # Gold bangles
        for bi in range(3):
            cyl(f"{name}_bg{side_idx}_{bi}", r=0.063, depth=0.025, segs=10,
                loc=(0, 0, -0.50 + bi*0.04), parent=sh, mat_=M_LEGONG_GOLD)
    # Head
    head_l_e = empty(f"{name}_he", (0, 0, 1.95), parent=base)
    smooth_sphere(f"{name}_h", r=0.17, segs=18, rings=14, loc=(0, 0, 0),
                  parent=head_l_e, mat_=M_SKIN)
    # Long black hair
    for hi in range(20):
        ha = random.uniform(math.pi*0.5, math.pi*1.5)
        hair_len = random.uniform(0.4, 0.7)
        for hsi in range(int(hair_len * 6)):
            cyl(f"{name}_hr{hi}_{hsi}", r=0.025, depth=0.08, segs=6,
                loc=(math.cos(ha)*0.15, math.sin(ha)*0.12, -hsi*0.08 - 0.05),
                parent=head_l_e, mat_=M_HAIR_BLACK)
    # Eyes
    for side in (-1, 1):
        smooth_sphere(f"{name}_ey{side}", r=0.025, loc=(side*0.06, -0.15, 0.03),
                      parent=head_l_e, mat_=M_EYE)
    # Lips red
    beveled_cube(f"{name}_lp", (0.10, 0.04, 0.025), bevel_offset=0.005,
                 loc=(0, -0.16, -0.07), parent=head_l_e, mat_=M_LIPS_RED)
    # GOLD CROWN GELUNGAN (signature ornate Balinese tiara)
    crown_e = empty(f"{name}_cr", (0, 0, 0.18), parent=head_l_e)
    # Crown base ring
    cyl(f"{name}_cr_b", r=0.20, depth=0.10, segs=14, loc=(0, 0, 0),
        parent=crown_e, mat_=M_CROWN_GOLD)
    # Decorative ornate points (signature flames)
    for cri in range(6):
        cra = (cri / 6.0) * math.pi * 2
        # Curved flame-shape
        smooth_cone(f"{name}_cr_p{cri}", r1=0.06, r2=0.01, depth=0.35, segs=8,
                    loc=(math.cos(cra)*0.18, math.sin(cra)*0.18, 0.20),
                    parent=crown_e, mat_=M_CROWN_GOLD).rotation_euler = (random.uniform(-0.1, 0.1), random.uniform(-0.1, 0.1), 0)
    # Top center spike (signature tallest)
    smooth_cone(f"{name}_cr_c", r1=0.08, r2=0.01, depth=0.50, segs=10,
                loc=(0, 0, 0.30), parent=crown_e, mat_=M_CROWN_GOLD)
    # Frangipani flower in hair (signature)
    smooth_sphere(f"{name}_fl", r=0.08, loc=(0.15, -0.05, 0.08),
                  parent=head_l_e, mat_=M_FRANG_WHITE)
    for pp in range(5):
        ppa = (pp / 5.0) * math.pi * 2
        beveled_cube(f"{name}_flp{pp}", (0.04, 0.06, 0.025), bevel_offset=0.005,
                     loc=(0.15 + math.cos(ppa)*0.06, -0.05 + math.sin(ppa)*0.04, 0.08),
                     parent=head_l_e, mat_=M_FRANG_WHITE).rotation_euler = (0, 0, ppa)
    base["_phase"] = random.uniform(0, math.pi*2)
    return {"root": base, "he": head_l_e}

legongs = []
legong_pos = [(-8, 5, math.radians(180)), (-3, 8, math.radians(180)),
               (3, 8, math.radians(180)), (8, 5, math.radians(180))]
for i, (lx, ly, fac) in enumerate(legong_pos):
    lg = make_legong_dancer(f"lg{i}", (lx, ly, 0), facing=fac)
    legongs.append(lg)

# ============ CENTRAL FIRE PIT (signature kecak fire dance) ============
fire_e = empty("fire", (0, -5, 0))
# Stone ring
cyl("fr_b", r=1.5, depth=0.30, segs=18, loc=(0, 0, 0.15), parent=fire_e, mat_=M_LAVA_STONE)
# Inner glowing coals
cyl("fr_c", r=1.2, depth=0.15, segs=18, loc=(0, 0, 0.20), parent=fire_e, mat_=M_FIRE)
# Flames
for fi in range(8):
    fa = (fi / 8.0) * math.pi * 2
    fr_dist = random.uniform(0, 0.8)
    smooth_cone(f"fr_f{fi}", r1=0.25, r2=0.05, depth=0.8, segs=10,
                loc=(math.cos(fa)*fr_dist, math.sin(fa)*fr_dist, 0.70),
                parent=fire_e, mat_=M_FIRE_HOT)
# Wood logs
for li_w in range(4):
    la_l = (li_w / 4.0) * math.pi * 2
    cyl(f"fr_lg{li_w}", r=0.10, depth=1.6, segs=8,
        loc=(math.cos(la_l)*0.3, math.sin(la_l)*0.3, 0.30),
        parent=fire_e, mat_=M_TORCH).rotation_euler = (0, 0, la_l)
fire_e["_phase"] = 0

# ============ INDONESIA FLAG (signature 2-stripe) ============
flag_e = empty("flag", (-45, -30, 0))
cyl("fl_p", r=0.10, depth=12, segs=10, loc=(0, 0, 6), parent=flag_e, mat_=M_THATCH_BLACK)
# Red stripe top
beveled_cube("fl_r", (4, 0.05, 1.25), bevel_offset=0.06, loc=(2, 0, 11.4),
             parent=flag_e, mat_=M_FLAG_RED)
# White stripe bottom
beveled_cube("fl_w", (4, 0.05, 1.25), bevel_offset=0.06, loc=(2, 0, 10.15),
             parent=flag_e, mat_=M_FLAG_WHITE)
flag_e["_phase"] = 0

# ============================================================
# 600 FRANGIPANI PETALS + 400 FIREFLIES (PARTICULES SIGNATURES)
# ============================================================
petals = []
for i in range(600):
    px = random.uniform(-100, 100)
    py = random.uniform(-100, 100)
    pz = random.uniform(2, 25)
    p_col = random.choice(FRANG_COLORS)
    p_e = empty(f"pe{i}", (px, py, pz))
    # 5-petal frangipani (signature)
    for pp in range(5):
        ppa = (pp / 5.0) * math.pi * 2
        beveled_cube(f"pe{i}_p{pp}", (0.04, 0.08, 0.02), bevel_offset=0.005,
                     loc=(math.cos(ppa)*0.05, math.sin(ppa)*0.05, 0),
                     parent=p_e, mat_=p_col).rotation_euler = (0, 0, ppa)
    # Yellow center
    smooth_sphere(f"pe{i}_c", r=0.02, loc=(0, 0, 0.01), parent=p_e, mat_=M_FRANG_YELLOW)
    p_e["_phase"] = random.uniform(0, math.pi*2)
    p_e["_base_x"] = px; p_e["_base_z"] = pz
    p_e["_drift"] = random.uniform(0.2, 0.6)
    p_e["_fall"] = random.uniform(0.5, 1.3)
    p_e["_swing"] = random.uniform(1.0, 2.2)
    petals.append(p_e)

# 400 fireflies
fireflies = []
for i in range(400):
    px = random.uniform(-100, 100)
    py = random.uniform(-100, 100)
    pz = random.uniform(2, 20)
    ff_e = empty(f"ff{i}", (px, py, pz))
    # Body
    smooth_sphere(f"ff{i}_bo", r=0.06, segs=8, rings=6, loc=(0, 0, 0),
                  parent=ff_e, mat_=M_FIREFLY_BODY, scale=(1.4, 0.85, 0.85))
    # Glowing abdomen (signature)
    smooth_sphere(f"ff{i}_gl", r=0.10, segs=10, rings=8, loc=(-0.05, 0, 0),
                  parent=ff_e, mat_=M_FIREFLY)
    # Tiny wings
    for side in (-1, 1):
        beveled_cube(f"ff{i}_w{side}", (0.04, 0.10, 0.005), bevel_offset=0.005,
                     loc=(0, side*0.05, 0.03), parent=ff_e, mat_=M_FLAG_WHITE)
    ff_e["_phase"] = random.uniform(0, math.pi*2)
    ff_e["_base_x"] = px; ff_e["_base_y"] = py; ff_e["_base_z"] = pz
    ff_e["_amp"] = random.uniform(1, 3)
    ff_e["_speed"] = random.uniform(0.6, 1.4)
    ff_e["_blink"] = random.uniform(2, 5)
    fireflies.append(ff_e)

# ============ ANIMATION ============
fps = 30; duration_s = 6; total_frames = fps * duration_s

# Kecak dancers chant (synchronized rhythmic arm pump)
for k in kecaks:
    phase = k["root"]["_phase"]
    for f in range(1, total_frames + 1, 2):
        t = (f - 1) / fps
        # Synchronized "CHAK" rhythm (every beat)
        chak_intensity = abs(math.sin(t * 4.0))
        k["root"].rotation_euler = (chak_intensity * math.radians(5), 0,
                                     k["root"].rotation_euler.z + math.sin(t * 4.0) * math.radians(3))
        k["root"].location.z = chak_intensity * 0.10
        k["root"].keyframe_insert("rotation_euler", frame=f)
        k["root"].keyframe_insert("location", frame=f)
        # Head shake side to side
        k["he"].rotation_euler = (math.sin(t * 4.0 + phase) * math.radians(15), 0,
                                   math.cos(t * 4.0 + phase) * math.radians(20))
        k["he"].keyframe_insert("rotation_euler", frame=f)

# Legong dancers graceful sway with hand turns
for lg in legongs:
    phase = lg["root"]["_phase"]
    for f in range(1, total_frames + 1, 3):
        t = (f - 1) / fps
        lg["root"].rotation_euler = (math.sin(t * 1.5 + phase) * math.radians(3), 0,
                                       lg["root"].rotation_euler.z + math.sin(t * 1.0 + phase) * math.radians(8))
        lg["root"].keyframe_insert("rotation_euler", frame=f)
        lg["he"].rotation_euler = (math.sin(t * 1.5 + phase) * math.radians(10), 0,
                                    math.cos(t * 1.2 + phase) * math.radians(20))
        lg["he"].keyframe_insert("rotation_euler", frame=f)

# Fire pit flames flicker
for f in range(1, total_frames + 1, 2):
    t = (f - 1) / fps
    sc_f = 1 + math.sin(t * 12.0) * 0.30
    fire_e.scale = (sc_f, sc_f, sc_f * (1 + math.cos(t * 10.0) * 0.25))
    fire_e.keyframe_insert("scale", frame=f)

# Flag wave
for f in range(1, total_frames + 1, 5):
    t = (f - 1) / fps
    flag_e.rotation_euler = (0, 0, math.sin(t * 1.5) * math.radians(12))
    flag_e.keyframe_insert("rotation_euler", frame=f)

# 600 frangipani petals fall
for p in petals:
    phase = p["_phase"]; drift = p["_drift"]; fall = p["_fall"]; swing = p["_swing"]
    bx, bz = p["_base_x"], p["_base_z"]
    for f in range(1, total_frames + 1, 4):
        t = (f - 1) / fps
        x = bx + math.sin(t * swing + phase) * 0.8 + t * drift
        z = bz - (t * fall) % 20
        p.location = (x, p.location.y, z)
        p.rotation_euler = (t * 1.5 + phase, math.sin(t * 2.0 + phase) * math.radians(30), t * 1.0 + phase)
        p.keyframe_insert("location", frame=f)
        p.keyframe_insert("rotation_euler", frame=f)

# 400 fireflies float + blink
for ff in fireflies:
    phase = ff["_phase"]; speed = ff["_speed"]; amp = ff["_amp"]; blink = ff["_blink"]
    bx, by, bz = ff["_base_x"], ff["_base_y"], ff["_base_z"]
    for f in range(1, total_frames + 1, 3):
        t = (f - 1) / fps
        x = bx + math.sin(t * speed + phase) * amp
        y = by + math.cos(t * speed * 0.9 + phase) * amp
        z = bz + math.sin(t * speed * 1.3 + phase) * 1.5
        ff.location = (x, y, z)
        # Blink intensity
        blink_scale = 0.5 + abs(math.sin(t * blink + phase)) * 1.0
        ff.scale = (blink_scale, blink_scale, blink_scale)
        ff.keyframe_insert("location", frame=f)
        ff.keyframe_insert("scale", frame=f)

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
out_glb = os.path.join(out_dir, "pbr_bali_proc.glb")

bpy.ops.object.select_all(action='SELECT')
bpy.ops.export_scene.gltf(
    filepath=out_glb, export_format='GLB',
    export_animations=True, export_apply=False, export_yup=True, use_selection=False,
)
size_mb = os.path.getsize(out_glb) / (1024 * 1024)
print(f"[proc_indonesian_bali_temple_kecak] DONE → {out_glb} ({size_mb:.2f} MB)")
print("Bali Uluwatu temple kecak: Uluwatu cliff + Indian Ocean + 8 Bali meru pagodas with signature multi-tier black thatched roofs (3/5/7/9/11 odd tiers) + stone bases + gold trim + gold finials at corners + spires + 6 kecak chanters arranged in circle (bare chest + poleng black/white checkered sarong + arms raised signature CHAK-CHAK gesture + open mouths chanting) + 4 legong Balinese dancers (signature gold gelungan crowns with 6 flame points + central tallest spike + ornate gold dress + frangipani flower in hair + graceful arm turns) + central fire pit with flickering flames + 4 wood logs + Indonesia flag red/white + rice paddy terraces + 600 frangipani petals + 400 blinking fireflies")
print("🌺 FIXES: 1 rice paddy ground + 600 frangipani petals (white/yellow/pink) + 400 blinking fireflies signature 🌺")
