"""
proc_ancient_greek_olympics.py — 214e procédural AuroraIA (78e qualité)
Olympiade antique: ONE ground + 600 olive leaves drift + Parthenon + Zeus statue + 8 athletes + chariot + spectators + Olympus mountains
FIXES : 1 ground propre + olive leaves thématique (laurier antique signature)
"""
import bpy, bmesh, math, random, os

random.seed(0x01ABC214)

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

# Materials — antique Greek golden hour
M_SKY = mat("sky", (1.0, 0.75, 0.45, 1.0), 0.0, 0.7, emission=(1.0,0.72,0.42), emission_strength=2.2)
M_SUN = mat("sun", (1.0, 0.92, 0.55, 1.0), 0.0, 0.10, emission=(1.0,0.92,0.55), emission_strength=18.0)
M_CLOUD = mat("cloud", (1.0, 0.85, 0.65, 1.0), 0.0, 0.55, emission=(1.0,0.85,0.65), emission_strength=1.8, alpha=0.80)

# Ground arena + variations
M_GROUND = mat("ground", (0.92, 0.85, 0.70, 1.0), 0.0, 0.85, emission=(0.85,0.78,0.65), emission_strength=0.3)
M_TRACK = mat("track", (0.85, 0.60, 0.30, 1.0), 0.0, 0.75, emission=(0.78,0.55,0.28), emission_strength=0.4)
M_DUST = mat("dust", (0.78, 0.65, 0.45, 1.0), 0.0, 0.85)
M_ROCK = mat("rock", (0.55, 0.50, 0.42, 1.0), 0.0, 0.85)

# Marble
M_MARBLE = mat("marble", (0.98, 0.95, 0.88, 1.0), 0.0, 0.30, emission=(0.95,0.92,0.85), emission_strength=0.5)
M_MARBLE_AGED = mat("marble_a", (0.85, 0.78, 0.70, 1.0), 0.0, 0.55, emission=(0.78,0.72,0.65), emission_strength=0.3)

# Olive leaves (signature)
M_OLIVE_DARK = mat("olive_d", (0.40, 0.55, 0.25, 1.0), 0.0, 0.55, emission=(0.35,0.50,0.22), emission_strength=0.5)
M_OLIVE_LIGHT = mat("olive_l", (0.65, 0.75, 0.35, 1.0), 0.0, 0.55, emission=(0.60,0.70,0.32), emission_strength=0.6)
M_OLIVE_GOLD = mat("olive_g", (0.95, 0.82, 0.30, 1.0), 0.7, 0.30, emission=(0.90,0.78,0.28), emission_strength=1.5)
M_OLIVE_TRUNK = mat("olive_t", (0.45, 0.35, 0.25, 1.0), 0.0, 0.85)
M_LAUREL = mat("laurel", (0.40, 0.55, 0.20, 1.0), 0.0, 0.55, emission=(0.38,0.52,0.18), emission_strength=0.6)

# Athletes skin + tunics
M_SKIN_GREEK = mat("skin_g", (0.95, 0.78, 0.62, 1.0), 0.0, 0.55, emission=(0.88,0.72,0.58), emission_strength=0.4)
M_TUNIC_WHITE = mat("tunic_w", (0.98, 0.95, 0.90, 1.0), 0.0, 0.55, emission=(0.92,0.88,0.82), emission_strength=0.4)
M_TUNIC_RED = mat("tunic_r", (0.85, 0.20, 0.18, 1.0), 0.0, 0.55, emission=(0.78,0.20,0.18), emission_strength=0.6)
M_TUNIC_BLUE = mat("tunic_b", (0.20, 0.45, 0.65, 1.0), 0.0, 0.55, emission=(0.18,0.40,0.60), emission_strength=0.6)
M_TUNIC_PURPLE = mat("tunic_p", (0.55, 0.20, 0.50, 1.0), 0.0, 0.55, emission=(0.50,0.18,0.45), emission_strength=0.6)
M_HAIR_DARK = mat("hair", (0.20, 0.12, 0.05, 1.0), 0.0, 0.85)
M_HAIR_BLOND = mat("hair_b", (0.85, 0.65, 0.30, 1.0), 0.0, 0.65)
M_BEARD = mat("beard", (0.15, 0.10, 0.05, 1.0), 0.0, 0.85)

# Discus + Javelin
M_DISCUS = mat("discus", (0.55, 0.45, 0.30, 1.0), 0.6, 0.40, emission=(0.50,0.42,0.28), emission_strength=0.5)
M_JAVELIN = mat("javelin", (0.55, 0.38, 0.22, 1.0), 0.0, 0.65)
M_JAVELIN_TIP = mat("jav_tip", (0.75, 0.70, 0.55, 1.0), 0.85, 0.20, emission=(0.70,0.65,0.50), emission_strength=0.6)

# Chariot
M_CHARIOT_WOOD = mat("chariot_w", (0.55, 0.35, 0.20, 1.0), 0.0, 0.65, emission=(0.50,0.32,0.18), emission_strength=0.4)
M_CHARIOT_GOLD = mat("chariot_g", (0.95, 0.78, 0.30, 1.0), 0.95, 0.18, emission=(0.90,0.72,0.28), emission_strength=0.9)
M_HORSE_BROWN = mat("horse_b", (0.45, 0.28, 0.15, 1.0), 0.0, 0.75, emission=(0.42,0.25,0.13), emission_strength=0.3)
M_HORSE_WHITE = mat("horse_w", (0.95, 0.92, 0.88, 1.0), 0.0, 0.65, emission=(0.88,0.85,0.82), emission_strength=0.4)
M_HORSE_BLACK = mat("horse_bk", (0.10, 0.08, 0.06, 1.0), 0.0, 0.80)
M_HORSE_MANE = mat("horse_m", (0.30, 0.18, 0.08, 1.0), 0.0, 0.85)

# Zeus statue
M_ZEUS_STONE = mat("zeus", (0.92, 0.88, 0.78, 1.0), 0.0, 0.50, emission=(0.88,0.82,0.72), emission_strength=0.5)
M_ZEUS_GOLD = mat("zeus_g", (1.0, 0.82, 0.30, 1.0), 0.95, 0.15, emission=(0.95,0.78,0.28), emission_strength=1.5)

# Tripod + flames
M_BRONZE = mat("bronze", (0.65, 0.45, 0.20, 1.0), 0.85, 0.25, emission=(0.60,0.42,0.18), emission_strength=0.4)
M_FLAME_CORE = mat("flame_c", (1.0, 0.85, 0.30, 1.0), 0.0, 0.20, emission=(1.0,0.85,0.30), emission_strength=10.0)
M_FLAME_OUTER = mat("flame_o", (1.0, 0.45, 0.15, 1.0), 0.0, 0.25, emission=(1.0,0.45,0.15), emission_strength=8.0)

# ============ SKY + SUN + CLOUDS ============
sky = smooth_sphere("sky", r=120, segs=32, rings=20, loc=(0,0,0), mat_=M_SKY)
sky.scale = (1,1,0.55)
sun = smooth_sphere("sun", r=5.0, loc=(15, 50, 18), mat_=M_SUN)
for i in range(3):
    smooth_sphere(f"sun_halo{i}", r=5.0 + (i+1)*1.8, loc=(15, 50, 18), mat_=M_SUN)

clouds = []
for i in range(6):
    a = (i / 6.0) * math.pi * 2
    rad = random.uniform(28, 38)
    cx, cy = rad*math.cos(a), rad*math.sin(a)
    cz = random.uniform(18, 26)
    c_e = empty(f"cloud_e{i}", (cx, cy, cz))
    for j in range(5):
        smooth_sphere(f"cloud{i}_{j}", r=random.uniform(2.2, 3.5),
                      loc=(random.uniform(-3,3), random.uniform(-2,2), random.uniform(-0.5,0.5)),
                      parent=c_e, mat_=M_CLOUD)
    c_e["_phase"] = random.uniform(0, math.pi*2)
    clouds.append(c_e)

# ============ Mt Olympus background ============
olympus_e = empty("olympus", loc=(0, 45, 4))
smooth_cone("oly_main", r1=16, r2=2.5, depth=12, segs=32,
            loc=(0, 0, 0), parent=olympus_e, mat_=M_ROCK)
smooth_cone("oly_cap", r1=3.5, r2=1.5, depth=2.2, segs=28,
            loc=(0, 0, 6.5), parent=olympus_e, mat_=M_MARBLE)
for side in (-1, 1):
    smooth_cone(f"oly_side{side}", r1=8, r2=1.5, depth=7, segs=24,
                loc=(side*18, -2, -2), parent=olympus_e, mat_=M_ROCK)
    smooth_cone(f"oly_cap_s{side}", r1=2.0, r2=1.0, depth=1.2, segs=20,
                loc=(side*18, -2, 2.5), parent=olympus_e, mat_=M_MARBLE_AGED)

# ============ ONE clean arena ground ============
ground = beveled_cube("ground", (90, 90, 0.5), bevel_offset=0.08, loc=(0, 0, -0.25), mat_=M_GROUND)

# Stadium oval track (organic - lines of dust)
track_e = empty("track", (0, 0, 0))
# Lane lines (5 concentric ovals)
for i in range(5):
    rad = 8 + i*1.8
    for j in range(40):
        ang = (j / 40.0) * math.pi * 2
        cx = rad * math.cos(ang)
        cy = rad * 0.55 * math.sin(ang)
        smooth_sphere(f"track_mark{i}_{j}", r=0.12,
                      loc=(cx, cy, 0.06), parent=track_e, mat_=M_TRACK, scale=(1, 1, 0.3))

# 20 rocks scattered (organic 3D)
for i in range(20):
    a = random.uniform(0, math.pi*2)
    rad = random.uniform(18, 32)
    smooth_sphere(f"rock{i}", r=random.uniform(0.35, 0.85),
                  loc=(rad*math.cos(a), rad*math.sin(a), 0.30),
                  mat_=M_ROCK,
                  scale=(random.uniform(0.8,1.3), random.uniform(0.8,1.3),
                         random.uniform(0.5,0.8)))

# Dust piles (organic 3D)
for i in range(15):
    a = random.uniform(0, math.pi*2)
    rad = random.uniform(10, 25)
    smooth_sphere(f"dust{i}", r=random.uniform(0.30, 0.55),
                  loc=(rad*math.cos(a), rad*math.sin(a), 0.10),
                  mat_=M_DUST, scale=(1.4, 1.2, 0.18))

# ============ PARTHENON TEMPLE (left side) ============
parthenon_e = empty("parthenon", loc=(-22, 12, 0))
# Stepped base
for i in range(3):
    width = 14 - i*0.5
    depth = 8 - i*0.3
    beveled_cube(f"par_step{i}", (width, depth, 0.40), bevel_offset=0.04,
                 loc=(0, 0, 0.20 + i*0.40), parent=parthenon_e, mat_=M_MARBLE)
# 8 columns front (ionic fluted)
for c_idx in range(8):
    cx = (c_idx - 3.5) * 1.6
    col_e = empty(f"par_col_e{c_idx}", (cx, -3.5, 1.30), parent=parthenon_e)
    # Column shaft
    cyl(f"par_col_shaft{c_idx}", r=0.40, depth=5.0, segs=20,
        loc=(0, 0, 2.5), parent=col_e, mat_=M_MARBLE)
    # Capital (ionic scroll)
    cyl(f"par_col_cap{c_idx}", r=0.55, depth=0.30, segs=16,
        loc=(0, 0, 5.15), parent=col_e, mat_=M_MARBLE)
    beveled_cube(f"par_col_volute{c_idx}", (0.50, 0.20, 0.20), bevel_offset=0.03,
                 loc=(0, 0, 5.30), parent=col_e, mat_=M_MARBLE)
    # Base
    cyl(f"par_col_base{c_idx}", r=0.50, depth=0.20, segs=16,
        loc=(0, 0, 0.10), parent=col_e, mat_=M_MARBLE)
# 8 columns back
for c_idx in range(8):
    cx = (c_idx - 3.5) * 1.6
    col_e = empty(f"par_col_e_b{c_idx}", (cx, 3.5, 1.30), parent=parthenon_e)
    cyl(f"par_col_shaft_b{c_idx}", r=0.40, depth=5.0, segs=20,
        loc=(0, 0, 2.5), parent=col_e, mat_=M_MARBLE)
    cyl(f"par_col_cap_b{c_idx}", r=0.55, depth=0.30, segs=16,
        loc=(0, 0, 5.15), parent=col_e, mat_=M_MARBLE)
    cyl(f"par_col_base_b{c_idx}", r=0.50, depth=0.20, segs=16,
        loc=(0, 0, 0.10), parent=col_e, mat_=M_MARBLE)
# Entablature (frieze + cornice)
beveled_cube("par_entab", (13, 7.5, 0.6), bevel_offset=0.05,
             loc=(0, 0, 6.8), parent=parthenon_e, mat_=M_MARBLE)
beveled_cube("par_frieze", (12.5, 7.2, 0.30), bevel_offset=0.04,
             loc=(0, 0, 7.30), parent=parthenon_e, mat_=M_MARBLE_AGED)
# Pediment (triangular front)
ped = beveled_cube("par_pediment_f", (13, 0.5, 1.5), bevel_offset=0.04,
                   loc=(0, -3.7, 8.1), parent=parthenon_e, mat_=M_MARBLE)
ped.rotation_euler = (math.radians(12), 0, 0)
ped2 = beveled_cube("par_pediment_b", (13, 0.5, 1.5), bevel_offset=0.04,
                    loc=(0, 3.7, 8.1), parent=parthenon_e, mat_=M_MARBLE)
ped2.rotation_euler = (math.radians(-12), 0, 0)
# Roof tiles
beveled_cube("par_roof", (12.5, 7, 0.30), bevel_offset=0.04,
             loc=(0, 0, 8.8), parent=parthenon_e, mat_=M_MARBLE_AGED)
# Acroterion (top decoration)
smooth_cone("par_acro_t", r1=0.40, r2=0.05, depth=1.0, segs=14,
            loc=(0, 0, 9.3), parent=parthenon_e, mat_=M_OLIVE_GOLD)

# ============ ZEUS STATUE (center back) ============
zeus_e = empty("zeus", loc=(0, 22, 0))
# Massive marble base
beveled_cube("zeus_base", (4, 3, 1.5), bevel_offset=0.08, loc=(0, 0, 0.75),
             parent=zeus_e, mat_=M_MARBLE)
beveled_cube("zeus_base2", (3.5, 2.5, 0.30), bevel_offset=0.04, loc=(0, 0, 1.65),
             parent=zeus_e, mat_=M_MARBLE_AGED)
# Throne
beveled_cube("zeus_throne_seat", (3, 2, 0.6), bevel_offset=0.05, loc=(0, 0, 2.10),
             parent=zeus_e, mat_=M_ZEUS_STONE)
beveled_cube("zeus_throne_back", (3, 0.5, 4), bevel_offset=0.06, loc=(0, 0.7, 4.40),
             parent=zeus_e, mat_=M_ZEUS_STONE)
for side in (-1, 1):
    beveled_cube(f"zeus_throne_arm{side}", (0.4, 1.5, 1.2), bevel_offset=0.04,
                 loc=(side*1.3, 0, 3.0), parent=zeus_e, mat_=M_ZEUS_STONE)
# Zeus body seated (massive)
beveled_cube("zeus_legs", (1.5, 1.5, 1.5), bevel_offset=0.07, loc=(0, 0, 3.15),
             parent=zeus_e, mat_=M_TUNIC_WHITE)
# Torso (bare chest, white toga over)
beveled_cube("zeus_torso", (1.6, 0.9, 1.8), bevel_offset=0.07, loc=(0, 0, 5.0),
             parent=zeus_e, mat_=M_ZEUS_STONE)
# Toga drape across chest
beveled_cube("zeus_toga", (1.65, 0.95, 1.5), bevel_offset=0.06, loc=(0, -0.05, 4.0),
             parent=zeus_e, mat_=M_TUNIC_WHITE)
# Head + beard
zeus_head_e = empty("zeus_head_e", (0, 0, 6.4), parent=zeus_e)
smooth_sphere("zeus_head", r=0.55, segs=22, rings=16, loc=(0, 0, 0),
              parent=zeus_head_e, mat_=M_ZEUS_STONE)
smooth_sphere("zeus_beard", r=0.50, loc=(0, -0.30, -0.30), parent=zeus_head_e,
              mat_=M_ZEUS_STONE, scale=(1.0, 1.0, 0.9))
# Hair (curls)
for i in range(8):
    a = (i / 8.0) * math.pi * 2
    smooth_sphere(f"zeus_curl{i}", r=0.18,
                  loc=(0.50*math.cos(a), 0.30*math.sin(a) + 0.30, 0.30),
                  parent=zeus_head_e, mat_=M_ZEUS_STONE)
# Crown laurel gold
for i in range(12):
    a = (i / 12.0) * math.pi * 2
    leaf = beveled_cube(f"zeus_laurel{i}", (0.10, 0.20, 0.04), bevel_offset=0.02,
                       loc=(0.60*math.cos(a), 0.60*math.sin(a), 0.55),
                       parent=zeus_head_e, mat_=M_OLIVE_GOLD)
    leaf.rotation_euler = (0, 0, a)
# Arms
for side in (-1, 1):
    sh = empty(f"zeus_sh{side}", (side*1.2, 0, 5.5), parent=zeus_e)
    sh.rotation_euler = (math.radians(-25), 0, math.radians(side*-30))
    beveled_cube(f"zeus_arm{side}", (0.40, 0.40, 1.4), bevel_offset=0.05,
                 loc=(0, 0, -0.7), parent=sh, mat_=M_ZEUS_STONE)
    smooth_sphere(f"zeus_hand{side}", r=0.25, loc=(0, 0, -1.55), parent=sh, mat_=M_ZEUS_STONE)
# Right hand holds thunderbolt (gold)
bolt = beveled_cube("zeus_bolt", (0.12, 0.12, 1.0), bevel_offset=0.03,
                    loc=(1.50, -0.40, 4.5), parent=zeus_e, mat_=M_ZEUS_GOLD)
bolt.rotation_euler = (math.radians(35), math.radians(20), 0)
# Bolt prongs at ends
for prong in range(3):
    pa = (prong / 3.0) * math.pi * 2
    p = beveled_cube(f"zeus_bolt_p{prong}", (0.08, 0.08, 0.4), bevel_offset=0.02,
                     loc=(1.50 + math.cos(pa)*0.15, -0.40 + math.sin(pa)*0.15, 5.0),
                     parent=zeus_e, mat_=M_ZEUS_GOLD)

# ============ 8 ATHLETES (varied poses) ============
def make_athlete(name, loc, tunic_mat, hair_mat, action="stand", facing=0, scale=1.0):
    base = empty(name, loc)
    base.rotation_euler = (0, 0, facing)
    # 2 legs muscular (with thigh + calf separated for definition)
    legs_e = []
    for side_idx, side in enumerate((-1, 1)):
        hip = empty(f"{name}_hip{side_idx}", (side*0.15*scale, 0, 0.85*scale), parent=base)
        # Knee bend depending on action
        leg_rx = 0
        if action == "run":
            leg_rx = math.radians(35 if side_idx==0 else -25)
        elif action == "throw":
            leg_rx = math.radians(-15 if side_idx==0 else 25)
        hip.rotation_euler = (leg_rx, 0, 0)
        # Thigh
        cyl(f"{name}_thigh{side_idx}", r=0.12*scale, depth=0.50*scale, segs=12,
            loc=(0, 0, -0.25*scale), parent=hip, mat_=M_SKIN_GREEK)
        # Knee bulge
        smooth_sphere(f"{name}_knee{side_idx}", r=0.10*scale, loc=(0, 0, -0.50*scale),
                      parent=hip, mat_=M_SKIN_GREEK)
        # Calf (slightly thinner)
        cyl(f"{name}_calf{side_idx}", r=0.10*scale, depth=0.45*scale, segs=12,
            loc=(0, 0, -0.75*scale), parent=hip, mat_=M_SKIN_GREEK)
        # Sandal
        beveled_cube(f"{name}_foot{side_idx}", (0.20*scale, 0.30*scale, 0.06*scale),
                     loc=(0, 0.05*scale, -1.00*scale), parent=hip,
                     mat_=mat(f"{name}_sandal{side_idx}", (0.55, 0.40, 0.20, 1.0), 0, 0.7))
        legs_e.append(hip)
    # Brief tunic / loincloth (athletes often nude in Olympics; minimal cloth)
    if action in ("run", "throw"):
        # Loincloth
        beveled_cube(f"{name}_loin", (0.32*scale, 0.20*scale, 0.25*scale), bevel_offset=0.03,
                     loc=(0, 0, 0.90*scale), parent=base, mat_=tunic_mat)
    else:
        # Tunic
        smooth_cone(f"{name}_tunic", r1=0.32*scale, r2=0.28*scale, depth=0.80*scale, segs=16,
                    loc=(0, 0, 0.85*scale), parent=base, mat_=tunic_mat)
    # Belt
    cyl(f"{name}_belt", r=0.30*scale, depth=0.08*scale, segs=16,
        loc=(0, 0, 1.05*scale), parent=base, mat_=M_OLIVE_GOLD)
    # Torso (muscular)
    beveled_cube(f"{name}_torso", (0.38*scale, 0.22*scale, 0.55*scale), bevel_offset=0.05,
                 loc=(0, 0, 1.40*scale), parent=base, mat_=M_SKIN_GREEK)
    # Pectorals (definition)
    for side in (-1, 1):
        smooth_sphere(f"{name}_pec{side}", r=0.10*scale,
                      loc=(side*0.10*scale, -0.12*scale, 1.55*scale), parent=base,
                      mat_=M_SKIN_GREEK, scale=(1, 0.6, 0.7))
    # Abs (visible 6-pack)
    for ab_row in range(3):
        for ab_col in (-1, 1):
            smooth_sphere(f"{name}_ab{ab_row}_{ab_col}", r=0.05*scale,
                          loc=(ab_col*0.06*scale, -0.12*scale, 1.40*scale - ab_row*0.10*scale),
                          parent=base, mat_=M_SKIN_GREEK, scale=(1, 0.4, 0.6))
    # Neck
    cyl(f"{name}_neck", r=0.09*scale, depth=0.18*scale, segs=10,
        loc=(0, 0, 1.78*scale), parent=base, mat_=M_SKIN_GREEK)
    # Head
    head_e = empty(f"{name}_head_e", (0, 0, 1.95*scale), parent=base)
    smooth_sphere(f"{name}_head", r=0.17*scale, segs=20, rings=14, loc=(0, 0, 0),
                  parent=head_e, mat_=M_SKIN_GREEK)
    # Eyes
    for side in (-1, 1):
        smooth_sphere(f"{name}_eye{side}", r=0.022*scale,
                      loc=(side*0.06*scale, -0.14*scale, 0.02*scale), parent=head_e,
                      mat_=mat(f"{name}_ew{side}", (0.05,0.05,0.05,1), 0, 0.5))
    # Hair (curly)
    smooth_sphere(f"{name}_hair", r=0.19*scale, loc=(0, 0.02*scale, 0.05*scale),
                  parent=head_e, mat_=hair_mat, scale=(1.05, 1.0, 0.85))
    # Hair curls (signature Greek)
    for i in range(6):
        a = (i / 6.0) * math.pi * 2
        smooth_sphere(f"{name}_curl{i}", r=0.06*scale,
                      loc=(0.15*scale*math.cos(a), 0.05*scale + 0.10*scale*math.sin(a), 0.18*scale),
                      parent=head_e, mat_=hair_mat)
    # Olive laurel crown
    for i in range(8):
        a = (i / 8.0) * math.pi * 2
        leaf = beveled_cube(f"{name}_laurel{i}", (0.05*scale, 0.10*scale, 0.02*scale), bevel_offset=0.01,
                            loc=(0.20*scale*math.cos(a), 0.20*scale*math.sin(a), 0.18*scale),
                            parent=head_e, mat_=M_OLIVE_LIGHT)
        leaf.rotation_euler = (0, 0, a)
    # Arms (action-dependent pose)
    arms_e = []
    arm_poses = {
        "stand": [(math.radians(-15), 0), (math.radians(-15), 0)],
        "run": [(math.radians(-65), 0), (math.radians(45), 0)],
        "throw": [(math.radians(-140), 30), (math.radians(45), -10)],
        "wrestle": [(math.radians(-90), -20), (math.radians(-90), 20)],
    }
    pose = arm_poses.get(action, arm_poses["stand"])
    for side_idx, side in enumerate((-1, 1)):
        sh = empty(f"{name}_sh{side_idx}", (side*0.30*scale, 0, 1.70*scale), parent=base)
        rx, rz = pose[side_idx]
        sh.rotation_euler = (rx, 0, math.radians(side*-15 + rz))
        # Upper arm (bicep visible)
        cyl(f"{name}_uarm{side_idx}", r=0.09*scale, depth=0.40*scale, segs=12,
            loc=(0, 0, -0.20*scale), parent=sh, mat_=M_SKIN_GREEK)
        smooth_sphere(f"{name}_bicep{side_idx}", r=0.085*scale,
                      loc=(0, -0.04*scale, -0.20*scale), parent=sh, mat_=M_SKIN_GREEK,
                      scale=(0.9, 0.7, 1.0))
        # Forearm
        cyl(f"{name}_fa{side_idx}", r=0.075*scale, depth=0.38*scale, segs=10,
            loc=(0, 0, -0.55*scale), parent=sh, mat_=M_SKIN_GREEK)
        # Hand
        smooth_sphere(f"{name}_hand{side_idx}", r=0.08*scale, loc=(0, 0, -0.78*scale),
                      parent=sh, mat_=M_SKIN_GREEK)
        arms_e.append(sh)
    return {"root": base, "head_e": head_e, "legs": legs_e, "arms": arms_e, "action": action}

athletes = []
ath_specs = [
    # Runners
    ("ath_run1", (3, -2, 0), M_TUNIC_WHITE, M_HAIR_DARK, "run", math.radians(0), 1.0),
    ("ath_run2", (1, -2, 0), M_TUNIC_RED, M_HAIR_BLOND, "run", math.radians(0), 1.0),
    ("ath_run3", (-1, -2, 0), M_TUNIC_BLUE, M_HAIR_DARK, "run", math.radians(0), 1.0),
    ("ath_run4", (-3, -2, 0), M_TUNIC_WHITE, M_HAIR_DARK, "run", math.radians(0), 1.0),
    # Discus thrower
    ("ath_disc", (6, 5, 0), M_TUNIC_WHITE, M_HAIR_DARK, "throw", math.radians(60), 1.0),
    # Javelin thrower
    ("ath_jav", (-6, 5, 0), M_TUNIC_WHITE, M_HAIR_BLOND, "throw", math.radians(-60), 1.0),
    # 2 wrestlers
    ("ath_wr1", (8, -6, 0), M_TUNIC_WHITE, M_HAIR_DARK, "wrestle", math.radians(45), 1.0),
    ("ath_wr2", (9, -7, 0), M_TUNIC_WHITE, M_HAIR_BLOND, "wrestle", math.radians(-135), 1.0),
]
for spec in ath_specs:
    name, loc, tunic, hair, action, fac, sc = spec
    a = make_athlete(name, loc, tunic, hair, action=action, facing=fac, scale=sc)
    athletes.append(a)

# Discus in disc thrower hand
discus_e = empty("discus_obj", (6 + 0.5, 5 + 0.6, 1.5))
cyl("discus_obj_main", r=0.25, depth=0.06, segs=20, loc=(0, 0, 0),
    parent=discus_e, mat_=M_DISCUS)

# Javelin in jav thrower hand
javelin_e = empty("javelin_obj", (-6 - 0.3, 5 - 0.5, 1.8))
javelin_e.rotation_euler = (math.radians(30), 0, math.radians(60))
cyl("jav_shaft", r=0.04, depth=2.5, segs=10, loc=(0, 0, 0),
    parent=javelin_e, mat_=M_JAVELIN)
smooth_cone("jav_tip", r1=0.05, r2=0.005, depth=0.3, segs=10,
            loc=(0, 0, 1.40), parent=javelin_e, mat_=M_JAVELIN_TIP)

# ============ CHARIOT BIGA (2 horses) ============
def make_horse(name, loc, body_mat=M_HORSE_BROWN, facing=0):
    base = empty(name, loc)
    base.rotation_euler = (0, 0, facing)
    # Body
    smooth_sphere(f"{name}_body", r=0.55, segs=20, rings=14, loc=(0, 0, 1.10),
                  parent=base, mat_=body_mat, scale=(1.7, 0.95, 0.95))
    # Neck (forward + up)
    neck = beveled_cube(f"{name}_neck", (0.40, 0.30, 0.70), bevel_offset=0.05,
                       loc=(0.85, 0, 1.30), parent=base, mat_=body_mat)
    neck.rotation_euler = (0, math.radians(-25), 0)
    # Head
    head_e = empty(f"{name}_head_e", (1.25, 0, 1.65), parent=base)
    beveled_cube(f"{name}_head", (0.50, 0.25, 0.30), bevel_offset=0.04,
                 loc=(0, 0, 0), parent=head_e, mat_=body_mat)
    # Muzzle
    smooth_cone(f"{name}_muzzle", r1=0.12, r2=0.10, depth=0.30, segs=14,
                loc=(0.30, 0, -0.05), parent=head_e, mat_=body_mat).rotation_euler = (0, math.radians(90), 0)
    # Eyes
    for side in (-1, 1):
        smooth_sphere(f"{name}_eye{side}", r=0.04,
                      loc=(0.05, side*0.12, 0.10), parent=head_e,
                      mat_=mat(f"{name}_ew{side}", (0.05,0.05,0.05,1), 0, 0.5))
    # Ears
    for side in (-1, 1):
        ear = smooth_cone(f"{name}_ear{side}", r1=0.06, r2=0.01, depth=0.15, segs=10,
                          loc=(-0.10, side*0.10, 0.20), parent=head_e, mat_=body_mat)
        ear.rotation_euler = (0, math.radians(-30), math.radians(side*15))
    # Mane (signature horse mane)
    for i in range(5):
        beveled_cube(f"{name}_mane{i}", (0.10, 0.05, 0.30),
                     loc=(0.5 - i*0.15, 0, 1.55 - i*0.05), parent=base, mat_=M_HORSE_MANE)
    # 4 legs
    for x_idx, x in enumerate((0.5, -0.5)):
        for y_idx, y in enumerate((-0.3, 0.3)):
            leg_e = empty(f"{name}_leg_e{x_idx}{y_idx}", (x, y, 0.55), parent=base)
            cyl(f"{name}_thigh_{x_idx}_{y_idx}", r=0.10, depth=0.55, segs=10,
                loc=(0, 0, -0.25), parent=leg_e, mat_=body_mat)
            cyl(f"{name}_calf_{x_idx}_{y_idx}", r=0.07, depth=0.40, segs=10,
                loc=(0, 0, -0.70), parent=leg_e, mat_=body_mat)
            cyl(f"{name}_hoof_{x_idx}_{y_idx}", r=0.10, depth=0.10, segs=10,
                loc=(0, 0, -0.95), parent=leg_e, mat_=M_HORSE_BLACK)
    # Tail
    tail = beveled_cube(f"{name}_tail", (0.10, 0.10, 0.80),
                       loc=(-0.85, 0, 1.30), parent=base, mat_=M_HORSE_MANE)
    tail.rotation_euler = (0, math.radians(35), 0)
    base["_phase"] = random.uniform(0, math.pi*2)
    return base

chariot_e = empty("chariot", (-10, -10, 0))
chariot_e.rotation_euler = (0, 0, math.radians(30))
# 2 horses pulling
horse1 = make_horse("horse_l", (-1.5, -0.6, 0), M_HORSE_WHITE, 0)
horse1.parent = chariot_e
horse2 = make_horse("horse_r", (-1.5, 0.6, 0), M_HORSE_BROWN, 0)
horse2.parent = chariot_e
# Chariot box (open back)
beveled_cube("chariot_box", (1.5, 1.4, 0.8), bevel_offset=0.05,
             loc=(0.5, 0, 0.95), parent=chariot_e, mat_=M_CHARIOT_WOOD)
# Front shield
beveled_cube("chariot_front", (0.20, 1.4, 1.0), bevel_offset=0.05,
             loc=(1.30, 0, 1.10), parent=chariot_e, mat_=M_CHARIOT_GOLD)
# 2 wheels
wheels = []
for side in (-1, 1):
    w_e = empty(f"wheel_e_{side}", (0.5, side*0.7, 0.55), parent=chariot_e)
    w_e.rotation_euler = (math.radians(90), 0, 0)
    cyl(f"wheel_rim_{side}", r=0.55, depth=0.10, segs=24, loc=(0, 0, 0),
        parent=w_e, mat_=M_CHARIOT_WOOD)
    cyl(f"wheel_hub_{side}", r=0.10, depth=0.12, segs=14, loc=(0, 0, 0),
        parent=w_e, mat_=M_CHARIOT_GOLD)
    # Spokes
    for sp in range(6):
        sa = (sp / 6.0) * math.pi * 2
        spoke = beveled_cube(f"spoke_{side}_{sp}", (0.04, 0.40, 0.04),
                            loc=(0, 0, 0), parent=w_e, mat_=M_CHARIOT_WOOD)
        spoke.rotation_euler = (0, 0, sa)
        spoke.location = (0.25*math.cos(sa), 0.25*math.sin(sa), 0)
    wheels.append(w_e)
# Pole connecting to horses
beveled_cube("chariot_pole", (3.0, 0.10, 0.10), bevel_offset=0.02,
             loc=(-1, 0, 0.50), parent=chariot_e, mat_=M_CHARIOT_WOOD)
# Charioteer (small visible figure in box)
char_e = empty("charioteer", (0.5, 0, 1.55), parent=chariot_e)
smooth_sphere("char_head", r=0.18, loc=(0, 0, 0.60), parent=char_e, mat_=M_SKIN_GREEK)
beveled_cube("char_body", (0.32, 0.22, 0.55), bevel_offset=0.04,
             loc=(0, 0, 0.20), parent=char_e, mat_=M_TUNIC_PURPLE)
beveled_cube("char_legs", (0.25, 0.22, 0.30), bevel_offset=0.03,
             loc=(0, 0, -0.20), parent=char_e, mat_=M_TUNIC_PURPLE)

# ============ 6 SPECTATORS in togas applauding ============
spectators = []
spec_specs = [
    ("spec1", (-18, -10, 0), M_TUNIC_RED, M_HAIR_DARK, 1.0),
    ("spec2", (-15, -12, 0), M_TUNIC_BLUE, M_HAIR_BLOND, 0.95),
    ("spec3", (-12, -10, 0), M_TUNIC_PURPLE, M_HAIR_DARK, 1.0),
    ("spec4", (15, -10, 0), M_TUNIC_WHITE, M_HAIR_DARK, 1.0),
    ("spec5", (18, -12, 0), M_TUNIC_RED, M_HAIR_BLOND, 0.95),
    ("spec6", (12, -10, 0), M_TUNIC_BLUE, M_HAIR_DARK, 1.0),
]
def make_spectator(name, loc, toga_mat, hair_mat, scale=1.0):
    base = empty(name, loc)
    base.rotation_euler = (0, 0, math.radians(180))
    # Standing legs (under toga)
    cyl(f"{name}_legs", r=0.30*scale, depth=1.1*scale, segs=14,
        loc=(0, 0, 0.55*scale), parent=base, mat_=toga_mat)
    # Long toga cone
    smooth_cone(f"{name}_toga", r1=0.40*scale, r2=0.32*scale, depth=1.0*scale, segs=16,
                loc=(0, 0, 0.95*scale), parent=base, mat_=toga_mat)
    # Belt
    cyl(f"{name}_belt", r=0.38*scale, depth=0.10*scale, segs=16,
        loc=(0, 0, 1.30*scale), parent=base, mat_=M_OLIVE_GOLD)
    # Torso
    beveled_cube(f"{name}_torso", (0.38*scale, 0.22*scale, 0.50*scale), bevel_offset=0.04,
                 loc=(0, 0, 1.65*scale), parent=base, mat_=toga_mat)
    # Head
    head_e = empty(f"{name}_head_e", (0, 0, 2.10*scale), parent=base)
    smooth_sphere(f"{name}_head", r=0.18*scale, segs=20, rings=14, loc=(0, 0, 0),
                  parent=head_e, mat_=M_SKIN_GREEK)
    smooth_sphere(f"{name}_hair", r=0.20*scale, loc=(0, 0.03*scale, 0.05*scale),
                  parent=head_e, mat_=hair_mat, scale=(1, 1, 0.85))
    # Laurel
    for i in range(8):
        a = (i / 8.0) * math.pi * 2
        leaf = beveled_cube(f"{name}_lau{i}", (0.05*scale, 0.10*scale, 0.02*scale), bevel_offset=0.01,
                            loc=(0.22*scale*math.cos(a), 0.22*scale*math.sin(a), 0.18*scale),
                            parent=head_e, mat_=M_OLIVE_DARK)
        leaf.rotation_euler = (0, 0, a)
    # Arms raised applauding
    arms_e = []
    for side_idx, side in enumerate((-1, 1)):
        sh = empty(f"{name}_sh{side_idx}", (side*0.30*scale, 0, 1.95*scale), parent=base)
        sh.rotation_euler = (math.radians(-130), 0, math.radians(side*-20))
        cyl(f"{name}_uarm{side_idx}", r=0.08*scale, depth=0.40*scale, segs=10,
            loc=(0, 0, -0.20*scale), parent=sh, mat_=M_SKIN_GREEK)
        cyl(f"{name}_fa{side_idx}", r=0.07*scale, depth=0.38*scale, segs=10,
            loc=(0, 0, -0.55*scale), parent=sh, mat_=M_SKIN_GREEK)
        smooth_sphere(f"{name}_hand{side_idx}", r=0.08*scale, loc=(0, 0, -0.78*scale),
                      parent=sh, mat_=M_SKIN_GREEK)
        arms_e.append(sh)
    base["_phase"] = random.uniform(0, math.pi*2)
    return {"root": base, "arms": arms_e, "head_e": head_e}

for spec in spec_specs:
    name, loc, toga, hair, sc = spec
    s = make_spectator(name, loc, toga, hair, scale=sc)
    spectators.append(s)

# ============ 4 BRONZE TRIPODS with flames ============
tripods = []
trip_pos = [(-7, -12, 0), (7, -12, 0), (-12, 6, 0), (12, 6, 0)]
for i, (tx, ty, tz) in enumerate(trip_pos):
    t_e = empty(f"tripod{i}", (tx, ty, tz))
    # 3 legs (signature tripod)
    for leg_idx in range(3):
        a = (leg_idx / 3.0) * math.pi * 2
        leg = beveled_cube(f"trip_leg{i}_{leg_idx}", (0.06, 0.06, 1.5), bevel_offset=0.02,
                          loc=(0.30*math.cos(a), 0.30*math.sin(a), 0.75),
                          parent=t_e, mat_=M_BRONZE)
        leg.rotation_euler = (0, 0, a)
    # Bowl
    smooth_sphere(f"trip_bowl{i}", r=0.45, segs=20, rings=14,
                  loc=(0, 0, 1.55), parent=t_e, mat_=M_BRONZE, scale=(1, 1, 0.5))
    # Flame (multi-cone composite)
    flame_e = empty(f"trip_flame{i}", (0, 0, 1.75), parent=t_e)
    smooth_cone(f"trip_fl_o{i}", r1=0.35, r2=0.05, depth=1.4, segs=14,
                loc=(0, 0, 0.7), parent=flame_e, mat_=M_FLAME_OUTER)
    smooth_cone(f"trip_fl_c{i}", r1=0.20, r2=0.02, depth=1.0, segs=14,
                loc=(0, 0, 0.5), parent=flame_e, mat_=M_FLAME_CORE)
    t_e["_phase"] = random.uniform(0, math.pi*2)
    tripods.append({"e": t_e, "flame": flame_e})

# ============ 6 ANCIENT OLIVE TREES (knotted trunks) ============
olive_trees = []
ot_pos = [(20, 18, 0), (-20, 18, 0), (24, -16, 0), (-24, -16, 0),
          (16, 22, 0), (-16, 22, 0)]
for i, (tx, ty, tz) in enumerate(ot_pos):
    base = empty(f"olive_t{i}", (tx, ty, tz))
    # Knotted trunk (5 twisted segments signature ancient olive)
    for s in range(5):
        seg = smooth_cone(f"olive_t{i}_seg{s}", r1=0.32 - s*0.02, r2=0.28 - s*0.02,
                          depth=0.7, segs=12,
                          loc=(random.uniform(-0.10, 0.10), random.uniform(-0.10, 0.10),
                               (s+0.5)*0.7),
                          parent=base, mat_=M_OLIVE_TRUNK)
        seg.rotation_euler = (math.radians(random.uniform(-8, 8)),
                              math.radians(random.uniform(-8, 8)), 0)
    # Branches with foliage
    for j in range(6):
        a = (j / 6.0) * math.pi * 2
        b_e = empty(f"olive_t{i}_be{j}", (0, 0, 3.0), parent=base)
        b_e.rotation_euler = (math.radians(60), 0, a)
        for k in range(2):
            cyl(f"olive_t{i}_b{j}_{k}", r=(0.10 - k*0.02), depth=0.6, segs=10,
                loc=(0, (k+0.5)*0.6, 0), parent=b_e,
                mat_=M_OLIVE_TRUNK).rotation_euler = (math.radians(90), 0, 0)
        # Foliage cluster
        for fl in range(4):
            smooth_sphere(f"olive_t{i}_f{j}_{fl}", r=random.uniform(0.45, 0.65),
                          loc=(random.uniform(-0.30, 0.30),
                               1.5 + random.uniform(-0.2, 0.2),
                               random.uniform(-0.20, 0.20)),
                          parent=b_e,
                          mat_=M_OLIVE_DARK if fl % 2 == 0 else M_OLIVE_LIGHT,
                          scale=(1, 1, 0.7))
    base["_phase"] = random.uniform(0, math.pi*2)
    olive_trees.append(base)

# ============================================================
# ⭐ 600 OLIVE LEAVES + LAUREL qui TOMBENT (PARTICULE THÉMATIQUE OBLIGATOIRE)
# ============================================================
olive_leaves = []
for i in range(600):
    px = random.uniform(-45, 45)
    py = random.uniform(-45, 45)
    pz = random.uniform(2, 28)
    color = M_OLIVE_DARK if i % 4 == 0 else (M_OLIVE_LIGHT if i % 4 == 1 else
            (M_OLIVE_GOLD if i % 4 == 2 else M_LAUREL))
    leaf = smooth_sphere(f"olive_leaf{i}", r=random.uniform(0.08, 0.14), segs=10, rings=6,
                         loc=(px, py, pz), mat_=color,
                         scale=(1.7, 0.5, 0.15))
    leaf.rotation_euler = (random.uniform(0, math.pi*2),
                           random.uniform(0, math.pi*2),
                           random.uniform(0, math.pi*2))
    leaf["_phase"] = random.uniform(0, math.pi*2)
    leaf["_base_x"] = px; leaf["_base_y"] = py; leaf["_base_z"] = pz
    leaf["_speed"] = random.uniform(0.4, 1.3)
    leaf["_drift_x"] = random.uniform(-2.0, 2.0)
    leaf["_drift_y"] = random.uniform(-2.0, 2.0)
    olive_leaves.append(leaf)

# ============ ANIMATION ============
fps = 30; duration_s = 6; total_frames = fps * duration_s

# Olive trees sway
for t in olive_trees:
    phase = t["_phase"]
    for f in range(1, total_frames + 1, 5):
        t_v = (f - 1) / fps
        t.rotation_euler = (math.sin(t_v * 0.9 + phase) * math.radians(2.5),
                             math.cos(t_v * 0.8 + phase) * math.radians(2.0),
                             0)
        t.keyframe_insert("rotation_euler", frame=f)

# Athletes animate per action
for a in athletes:
    phase = hash(a["root"].name) % 100 * 0.05
    action = a["action"]
    for f in range(1, total_frames + 1, 3):
        t = (f - 1) / fps
        if action == "run":
            # Legs alternate
            for li, leg in enumerate(a["legs"]):
                swing = math.sin(t * 6.0 + phase + li * math.pi) * math.radians(45)
                leg.rotation_euler = (swing, 0, 0)
                leg.keyframe_insert("rotation_euler", frame=f)
            # Arms alternate opposite
            for ai, arm in enumerate(a["arms"]):
                swing = math.sin(t * 6.0 + phase + ai * math.pi + math.pi) * math.radians(40)
                rx_base, rz_base = -0.65, 0
                if ai == 0:
                    arm.rotation_euler = (math.radians(-65) + swing, 0, math.radians(-15))
                else:
                    arm.rotation_euler = (math.radians(45) + swing, 0, math.radians(15))
                arm.keyframe_insert("rotation_euler", frame=f)
            # Body bob
            base_z = 0
            a["root"].location.z = base_z + abs(math.sin(t * 6.0 + phase)) * 0.10
            a["root"].keyframe_insert("location", frame=f)
        elif action == "throw":
            # Body twist + arm wind-up
            a["root"].rotation_euler = (0, 0, hash(a["root"].name) % 360 * math.pi / 180 +
                                          math.sin(t * 1.5 + phase) * math.radians(30))
            a["root"].keyframe_insert("rotation_euler", frame=f)
            # Throwing arm
            a["arms"][0].rotation_euler = (math.radians(-140) +
                                            math.sin(t * 1.5 + phase) * math.radians(40),
                                            0, math.radians(45))
            a["arms"][0].keyframe_insert("rotation_euler", frame=f)
        elif action == "wrestle":
            # Body lean forward + sway
            a["root"].rotation_euler = (math.sin(t * 1.2 + phase) * math.radians(10),
                                         math.cos(t * 1.0 + phase) * math.radians(8),
                                         hash(a["root"].name) % 360 * math.pi / 180)
            a["root"].keyframe_insert("rotation_euler", frame=f)

# Chariot rolls + wheels spin + horses gallop
chariot_phase = 0
for f in range(1, total_frames + 1, 3):
    t = (f - 1) / fps
    # Chariot circular motion (slow orbit)
    chariot_e.location = (-10 + math.sin(t * 0.5) * 3,
                          -10 + math.cos(t * 0.5) * 3, 0)
    chariot_e.rotation_euler = (0, 0, math.radians(30) + t * 0.5)
    chariot_e.keyframe_insert("location", frame=f)
    chariot_e.keyframe_insert("rotation_euler", frame=f)
    # Wheels spin
    for w in wheels:
        w.rotation_euler = (math.radians(90), 0, t * 10.0)
        w.keyframe_insert("rotation_euler", frame=f)

# Horses leg gallop animation
for hname in ("horse_l", "horse_r"):
    h = bpy.data.objects[hname]
    phase = h["_phase"]
    for f in range(1, total_frames + 1, 3):
        t = (f - 1) / fps
        # Body bob
        bob = abs(math.sin(t * 8.0 + phase)) * 0.10
        h.location.z = bob
        h.keyframe_insert("location", frame=f)

# Spectators applaud (arms wave)
for s in spectators:
    phase = s["root"]["_phase"]
    for f in range(1, total_frames + 1, 4):
        t = (f - 1) / fps
        for ai, arm in enumerate(s["arms"]):
            wave = math.sin(t * 4.0 + phase + ai * math.pi) * math.radians(15)
            arm.rotation_euler = (math.radians(-130) + wave, 0, math.radians((-1 if ai==0 else 1)*-20))
            arm.keyframe_insert("rotation_euler", frame=f)
        # Head bobs
        s["head_e"].rotation_euler = (math.sin(t * 1.5 + phase) * math.radians(8), 0,
                                       math.sin(t * 1.2 + phase) * math.radians(10))
        s["head_e"].keyframe_insert("rotation_euler", frame=f)

# Tripod flames flicker (scale + rotate)
for trip in tripods:
    phase = trip["e"]["_phase"]
    for f in range(1, total_frames + 1, 3):
        t = (f - 1) / fps
        s = 1 + math.sin(t * 5.0 + phase) * 0.12
        trip["flame"].scale = (1 + math.sin(t * 4.0 + phase) * 0.08,
                                1 + math.cos(t * 4.5 + phase) * 0.08, s)
        trip["flame"].rotation_euler = (0, 0, math.sin(t * 3.0 + phase) * 0.15)
        trip["flame"].keyframe_insert("scale", frame=f)
        trip["flame"].keyframe_insert("rotation_euler", frame=f)

# Clouds drift
for c_e in clouds:
    phase = c_e["_phase"]
    bx, by = c_e.location.x, c_e.location.y
    for f in range(1, total_frames + 1, 8):
        t = (f - 1) / fps
        c_e.location = (bx + math.sin(t * 0.3 + phase) * 0.7,
                        by + math.cos(t * 0.25 + phase) * 0.7,
                        c_e.location.z)
        c_e.keyframe_insert("location", frame=f)

# Sun halos
for obj in bpy.data.objects:
    if obj.name.startswith("sun_halo"):
        for f in range(1, total_frames + 1, 6):
            t = (f - 1) / fps
            s = 1 + math.sin(t * 0.8) * 0.06
            obj.scale = (s, s, s)
            obj.keyframe_insert("scale", frame=f)

# ============================================================
# ⭐⭐⭐ 600 OLIVE LEAVES TOMBANT (signature olympia antique)
# ============================================================
for lf in olive_leaves:
    phase = lf["_phase"]; speed = lf["_speed"]
    bx, by, bz = lf["_base_x"], lf["_base_y"], lf["_base_z"]
    drift_x = lf["_drift_x"]; drift_y = lf["_drift_y"]
    for f in range(1, total_frames + 1, 5):
        t = (f - 1) / fps
        # Slow descent (leaves)
        z = bz - (speed * t) % 28
        # Spiral drift (signature flutter)
        x = bx + drift_x * math.sin(t * 1.4 + phase) * 0.7
        y = by + drift_y * math.cos(t * 1.2 + phase) * 0.7
        # Tumble rotation
        rx = phase + t * 2.0
        ry = phase + t * 1.6
        rz = phase + t * 2.2
        lf.location = (x, y, max(0.05, z))
        lf.rotation_euler = (rx, ry, rz)
        lf.keyframe_insert("location", frame=f)
        lf.keyframe_insert("rotation_euler", frame=f)

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
out_glb = os.path.join(out_dir, "pbr_olympics_proc.glb")

bpy.ops.object.select_all(action='SELECT')
bpy.ops.export_scene.gltf(
    filepath=out_glb, export_format='GLB',
    export_animations=True, export_apply=False, export_yup=True, use_selection=False,
)
size_mb = os.path.getsize(out_glb) / (1024 * 1024)
print(f"[proc_ancient_greek_olympics] DONE → {out_glb} ({size_mb:.2f} MB)")
print("[proc_ancient_greek_olympics] ONE ground + Mt Olympus + Parthenon + Zeus statue + 8 athletes + biga chariot + 6 spectators + 4 tripods + 6 olive trees + 600 OLIVE LEAVES")
print("⭐ FIXES: 1 ground + 600 olive leaves Z descent + spiral drift + tumble (signature olympia mandatory) ⭐")
