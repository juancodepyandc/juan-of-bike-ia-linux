"""
proc_roman_colosseum_gladiators.py — 223e procédural AuroraIA (87e qualité)
Roman colosseum: ONE arena ground + 600 dust + 400 sparks + Colosseum 4 tiers 80 arches + 4 gladiators combat + Caesar + senators + lions cage + 8 spectators + SPQR flags + torches
FIXES : 1 ground + 600 dust + 400 sparks thématiques signature combat antique
"""
import bpy, bmesh, math, random, os

random.seed(0xC012223)

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

# Rome dusk palette
M_SKY = mat("sky", (0.95, 0.55, 0.30, 1.0), 0.0, 0.7, emission=(0.90,0.50,0.28), emission_strength=2.5)
M_SUN = mat("sun", (1.0, 0.78, 0.30, 1.0), 0.0, 0.10, emission=(1.0,0.78,0.30), emission_strength=22.0)
M_CLOUD = mat("cloud", (1.0, 0.78, 0.55, 1.0), 0.0, 0.55, emission=(0.95,0.72,0.50), emission_strength=2.0, alpha=0.85)

# Arena sand
M_SAND_ARENA = mat("sand", (0.78, 0.62, 0.38, 1.0), 0.0, 0.85, emission=(0.72,0.58,0.35), emission_strength=0.5)
M_SAND_DARK = mat("sand_d", (0.65, 0.48, 0.28, 1.0), 0.0, 0.85)
M_BLOOD_STAIN = mat("blood", (0.55, 0.15, 0.10, 1.0), 0.0, 0.70, emission=(0.50,0.15,0.10), emission_strength=0.4)

# Marble + travertine
M_MARBLE_WHITE = mat("marble_w", (0.92, 0.88, 0.78, 1.0), 0.0, 0.45, emission=(0.85,0.82,0.75), emission_strength=0.7)
M_TRAVERTINE = mat("trav", (0.85, 0.75, 0.55, 1.0), 0.0, 0.70, emission=(0.78,0.70,0.50), emission_strength=0.6)
M_TRAVERTINE_AGED = mat("trav_a", (0.72, 0.62, 0.45, 1.0), 0.0, 0.75, emission=(0.65,0.58,0.42), emission_strength=0.5)
M_STONE = mat("stone", (0.55, 0.50, 0.42, 1.0), 0.0, 0.85)

# Gladiator armor + cloth
M_SKIN_GLAD = mat("skin", (0.92, 0.72, 0.55, 1.0), 0.0, 0.55, emission=(0.85,0.68,0.52), emission_strength=0.4)
M_BRONZE = mat("bronze", (0.75, 0.50, 0.25, 1.0), 0.85, 0.25, emission=(0.70,0.48,0.22), emission_strength=0.7)
M_BRONZE_DARK = mat("bronze_d", (0.55, 0.35, 0.18, 1.0), 0.85, 0.40, emission=(0.50,0.32,0.15), emission_strength=0.5)
M_IRON = mat("iron", (0.55, 0.55, 0.60, 1.0), 0.85, 0.30, emission=(0.50,0.50,0.55), emission_strength=0.5)
M_STEEL = mat("steel", (0.75, 0.75, 0.80, 1.0), 0.95, 0.18, emission=(0.70,0.70,0.75), emission_strength=0.6)
M_LEATHER = mat("leather", (0.45, 0.25, 0.15, 1.0), 0.0, 0.75, emission=(0.40,0.22,0.13), emission_strength=0.3)
M_TUNIC_RED = mat("tunic_r", (0.78, 0.18, 0.18, 1.0), 0.0, 0.55, emission=(0.72,0.18,0.18), emission_strength=0.6)
M_TUNIC_BLUE = mat("tunic_b", (0.20, 0.40, 0.65, 1.0), 0.0, 0.55, emission=(0.18,0.38,0.60), emission_strength=0.6)
M_TUNIC_BROWN = mat("tunic_br", (0.45, 0.30, 0.18, 1.0), 0.0, 0.55, emission=(0.42,0.28,0.16), emission_strength=0.5)
M_HAIR_GLAD = mat("hair", (0.18, 0.12, 0.05, 1.0), 0.0, 0.85)
M_FANG = mat("fang", (0.95, 0.92, 0.85, 1.0), 0.0, 0.40, emission=(0.85,0.82,0.75), emission_strength=0.5)
M_NET = mat("net", (0.55, 0.50, 0.30, 1.0), 0.0, 0.75)

# Caesar + senators
M_TOGA_WHITE = mat("toga_w", (0.95, 0.92, 0.85, 1.0), 0.0, 0.65, emission=(0.88,0.85,0.78), emission_strength=0.5)
M_TOGA_PURPLE = mat("toga_p", (0.55, 0.20, 0.50, 1.0), 0.0, 0.55, emission=(0.50,0.18,0.45), emission_strength=0.7)
M_TOGA_RED = mat("toga_r", (0.85, 0.18, 0.18, 1.0), 0.0, 0.60, emission=(0.78,0.18,0.18), emission_strength=0.7)
M_LAUREL_GOLD = mat("laurel", (1.0, 0.78, 0.20, 1.0), 0.85, 0.25, emission=(0.95,0.72,0.20), emission_strength=1.5)
M_TROPHY_GOLD = mat("trophy", (1.0, 0.82, 0.30, 1.0), 0.95, 0.18, emission=(0.95,0.78,0.28), emission_strength=1.5)

# Lions
M_LION_GOLD = mat("lion", (0.85, 0.62, 0.30, 1.0), 0.0, 0.65, emission=(0.78,0.58,0.28), emission_strength=0.4)
M_LION_MANE = mat("mane", (0.55, 0.32, 0.12, 1.0), 0.0, 0.85, emission=(0.50,0.30,0.10), emission_strength=0.3)
M_LION_EYE = mat("l_eye", (1.0, 0.85, 0.20, 1.0), 0.0, 0.10, emission=(1.0,0.85,0.20), emission_strength=10.0)
M_CAGE = mat("cage", (0.30, 0.30, 0.35, 1.0), 0.70, 0.55, emission=(0.25,0.25,0.30), emission_strength=0.3)

# Flags + drapeaux SPQR
M_FLAG_SPQR = mat("flag_s", (0.85, 0.18, 0.18, 1.0), 0.0, 0.55, emission=(0.78,0.18,0.18), emission_strength=0.7)
M_FLAG_GOLD = mat("flag_g", (1.0, 0.82, 0.30, 1.0), 0.7, 0.30, emission=(0.95,0.78,0.28), emission_strength=1.0)
M_POLE = mat("pole", (0.45, 0.30, 0.18, 1.0), 0.0, 0.75)

# Torches
M_TORCH_WOOD = mat("torch_w", (0.40, 0.25, 0.15, 1.0), 0.0, 0.80)
M_FIRE_OUTER = mat("fire_o", (1.0, 0.55, 0.15, 1.0), 0.0, 0.20, emission=(1.0,0.55,0.15), emission_strength=12.0)
M_FIRE_CORE = mat("fire_c", (1.0, 0.92, 0.30, 1.0), 0.0, 0.20, emission=(1.0,0.92,0.30), emission_strength=18.0)
M_SMOKE = mat("smoke", (0.30, 0.28, 0.25, 1.0), 0.0, 0.85, emission=(0.25,0.23,0.20), emission_strength=0.5, alpha=0.65)

# Dust + sparks signature
M_DUST = mat("dust", (0.85, 0.65, 0.40, 1.0), 0.0, 0.55, emission=(0.78,0.60,0.38), emission_strength=2.5, alpha=0.65)
M_DUST_DARK = mat("dust_d", (0.65, 0.45, 0.25, 1.0), 0.0, 0.65, emission=(0.60,0.42,0.22), emission_strength=2.0, alpha=0.65)
M_SPARK = mat("spark", (1.0, 0.92, 0.30, 1.0), 0.0, 0.10, emission=(1.0,0.92,0.30), emission_strength=20.0)
M_SPARK_ORANGE = mat("spark_o", (1.0, 0.65, 0.15, 1.0), 0.0, 0.10, emission=(1.0,0.65,0.15), emission_strength=18.0)

# ============ SKY + SUN + CLOUDS ============
sky = smooth_sphere("sky", r=140, segs=32, rings=20, loc=(0,0,0), mat_=M_SKY)
sky.scale = (1,1,0.55)
sun_e = empty("sun_e", (35, 0, 28))
smooth_sphere("sun", r=6.0, loc=(0, 0, 0), parent=sun_e, mat_=M_SUN)
for i in range(3):
    smooth_sphere(f"sun_halo{i}", r=6.0 + (i+1)*1.8, loc=(0, 0, 0), parent=sun_e, mat_=M_SUN)

# Clouds drift
clouds = []
for i in range(8):
    a = (i / 8.0) * math.pi * 2
    rad = random.uniform(35, 50)
    cx, cy = rad*math.cos(a), rad*math.sin(a)
    cz = random.uniform(25, 36)
    c_e = empty(f"cloud_e{i}", (cx, cy, cz))
    for j in range(5):
        smooth_sphere(f"cloud{i}_{j}", r=random.uniform(2.8, 4.2),
                      loc=(random.uniform(-3,3), random.uniform(-2,2), random.uniform(-0.5,0.5)),
                      parent=c_e, mat_=M_CLOUD)
    c_e["_phase"] = random.uniform(0, math.pi*2)
    clouds.append(c_e)

# ============ ONE arena sand ground (oval) ============
ground = beveled_cube("ground", (38, 28, 0.5), bevel_offset=0.08, loc=(0, 0, -0.25), mat_=M_SAND_ARENA)
# Around arena lower border (terrace)
border = beveled_cube("ground_outer", (100, 100, 0.5), bevel_offset=0.08, loc=(0, 0, -0.50), mat_=M_STONE)

# Sand variations (organic 3D)
for i in range(40):
    a = random.uniform(0, math.pi*2)
    rad = random.uniform(2, 15)
    rad_y = rad * 0.7
    smooth_sphere(f"sand_m{i}", r=random.uniform(0.30, 0.55), segs=14, rings=10,
                  loc=(rad*math.cos(a), rad_y*math.sin(a), 0.10),
                  mat_=M_SAND_DARK if i % 3 == 0 else M_SAND_ARENA,
                  scale=(1.5, 1.3, 0.25))

# Blood stains (signature combat aftermath)
for i in range(6):
    a = random.uniform(0, math.pi*2)
    rad = random.uniform(2, 10)
    smooth_sphere(f"blood{i}", r=random.uniform(0.30, 0.55), segs=14, rings=10,
                  loc=(rad*math.cos(a), rad*0.7*math.sin(a), 0.08),
                  mat_=M_BLOOD_STAIN, scale=(1.8, 1.5, 0.12))

# ============ COLOSSEUM 4-tier oval (signature) ============
colosseum_e = empty("colo", loc=(0, 0, 0))
# Outer oval radius
outer_r_x = 30
outer_r_y = 24
# 4 tiers: base, arches level 1, arches level 2, attic
tier_heights = [4, 4, 4, 3.5]
tier_count = 4

# Tier base platform
tier_y_offset = 0
for tier in range(tier_count):
    tier_z = tier_y_offset
    tier_h = tier_heights[tier]
    # Solid ring base for each tier (signature exterior)
    # Build with 80 arch segments per tier (top 3 tiers) or solid (bottom)
    if tier == tier_count - 1:
        # Attic (top) - solid wall + small windows
        for seg in range(40):
            sa = (seg / 40.0) * math.pi * 2
            wx = outer_r_x * math.cos(sa)
            wy = outer_r_y * math.sin(sa)
            beveled_cube(f"colo_attic{seg}", (1.5, 1.5, tier_h), bevel_offset=0.05,
                         loc=(wx, wy, tier_z + tier_h/2), parent=colosseum_e,
                         mat_=M_TRAVERTINE if seg % 2 == 0 else M_TRAVERTINE_AGED)
        # Small rectangular windows
        for seg in range(20):
            sa = (seg / 20.0) * math.pi * 2
            wx_w = (outer_r_x - 0.5) * math.cos(sa)
            wy_w = (outer_r_y - 0.5) * math.sin(sa)
            beveled_cube(f"colo_aw{seg}", (1.0, 1.0, 1.5), bevel_offset=0.03,
                         loc=(wx_w, wy_w, tier_z + tier_h/2),
                         parent=colosseum_e,
                         mat_=mat(f"aw_m{seg}", (0.1, 0.08, 0.06, 1), 0, 0.7))
    else:
        # Arched tiers (20 arches per tier - 80 total)
        for seg in range(20):
            sa = (seg / 20.0) * math.pi * 2
            sa_next = ((seg + 1) / 20.0) * math.pi * 2
            sa_mid = (sa + sa_next) / 2
            # Column between arches
            col_x = outer_r_x * math.cos(sa)
            col_y = outer_r_y * math.sin(sa)
            cyl(f"colo_col_{tier}_{seg}", r=0.6, depth=tier_h, segs=14,
                loc=(col_x, col_y, tier_z + tier_h/2), parent=colosseum_e,
                mat_=M_TRAVERTINE if (tier + seg) % 2 == 0 else M_TRAVERTINE_AGED)
            # Capital top
            cyl(f"colo_cap_{tier}_{seg}", r=0.75, depth=0.20, segs=14,
                loc=(col_x, col_y, tier_z + tier_h - 0.10), parent=colosseum_e,
                mat_=M_TRAVERTINE)
            # Arch top (curved beam between columns)
            arch_x = outer_r_x * math.cos(sa_mid)
            arch_y = outer_r_y * math.sin(sa_mid)
            # Lintel
            lintel = beveled_cube(f"colo_lintel_{tier}_{seg}", (3.5, 1.0, 0.8), bevel_offset=0.05,
                                  loc=(arch_x, arch_y, tier_z + tier_h - 0.4), parent=colosseum_e,
                                  mat_=M_TRAVERTINE)
            lintel.rotation_euler = (0, 0, sa_mid + math.pi/2)
            # Arch curve approximation (5 segments per arch)
            for arch_seg in range(5):
                arch_t = arch_seg / 4.0  # 0..1
                arch_h_local = math.sin(arch_t * math.pi) * 0.4
                # Position relative to arch_mid
                offset_along = (arch_t - 0.5) * 2.5
                arch_pos_x = arch_x + math.cos(sa_mid + math.pi/2) * offset_along
                arch_pos_y = arch_y + math.sin(sa_mid + math.pi/2) * offset_along
                arch_pos_z = tier_z + tier_h - 1.2 + arch_h_local
                arch_block = beveled_cube(f"colo_arch_{tier}_{seg}_{arch_seg}", (0.6, 0.6, 0.3),
                                           bevel_offset=0.04,
                                           loc=(arch_pos_x, arch_pos_y, arch_pos_z),
                                           parent=colosseum_e, mat_=M_TRAVERTINE_AGED)
                arch_block.rotation_euler = (0, 0, sa_mid + math.pi/2)
    # Horizontal cornice band between tiers
    for seg in range(40):
        sa = (seg / 40.0) * math.pi * 2
        wx = outer_r_x * math.cos(sa)
        wy = outer_r_y * math.sin(sa)
        beveled_cube(f"colo_cornice_{tier}_{seg}", (1.5, 1.5, 0.4), bevel_offset=0.04,
                     loc=(wx, wy, tier_z + tier_h), parent=colosseum_e,
                     mat_=M_TRAVERTINE)
    tier_y_offset += tier_h

# Inner wall (around arena edge - lower)
inner_r_x = 18
inner_r_y = 12
for seg in range(30):
    sa = (seg / 30.0) * math.pi * 2
    wx = inner_r_x * math.cos(sa)
    wy = inner_r_y * math.sin(sa)
    beveled_cube(f"colo_inner{seg}", (1.2, 1.2, 4.0), bevel_offset=0.04,
                 loc=(wx, wy, 2.0), parent=colosseum_e,
                 mat_=M_TRAVERTINE_AGED)

# Spectator tiers (rising rings inside)
for tier_step in range(4):
    inner_step_x = 18 + tier_step * 2
    inner_step_y = 12 + tier_step * 1.5
    inner_step_z = 4 + tier_step * 1.5
    for seg in range(36):
        sa = (seg / 36.0) * math.pi * 2
        wx = inner_step_x * math.cos(sa)
        wy = inner_step_y * math.sin(sa)
        beveled_cube(f"colo_step{tier_step}_{seg}", (1.5, 1.5, 0.5), bevel_offset=0.03,
                     loc=(wx, wy, inner_step_z), parent=colosseum_e,
                     mat_=M_TRAVERTINE if seg % 2 == 0 else M_TRAVERTINE_AGED)

# ============ 100 SMALL SPECTATORS in tiers (far) ============
for spec_idx in range(100):
    sa = (spec_idx / 100.0) * math.pi * 2 + random.uniform(-0.1, 0.1)
    rad_x = random.uniform(20, 25)
    rad_y = random.uniform(14, 18)
    spec_z = random.uniform(5, 9)
    sx = rad_x * math.cos(sa)
    sy = rad_y * math.sin(sa)
    # Body
    smooth_cone(f"sp_body{spec_idx}", r1=0.30, r2=0.20, depth=0.80, segs=12,
                loc=(sx, sy, spec_z + 0.40),
                mat_=M_TOGA_WHITE if spec_idx % 3 == 0 else (M_TOGA_RED if spec_idx % 3 == 1 else M_TOGA_BROWN if False else M_TUNIC_BROWN))
    # Head
    smooth_sphere(f"sp_h{spec_idx}", r=0.12, segs=12, rings=8,
                  loc=(sx, sy, spec_z + 0.95),
                  mat_=M_SKIN_GLAD)

# ============ EMPEROR CAESAR'S BOX ============
caesar_box_e = empty("caesar_box", loc=(0, -16, 0))
# Marble platform
beveled_cube("cb_plat", (6, 3, 1.0), bevel_offset=0.06, loc=(0, 0, 4),
             parent=caesar_box_e, mat_=M_MARBLE_WHITE)
# 4 columns
for x in (-1, 1):
    for y in (-1, 1):
        cyl(f"cb_col_{x}{y}", r=0.20, depth=3.0, segs=14,
            loc=(x*2.5, y*1.3, 6.0), parent=caesar_box_e, mat_=M_MARBLE_WHITE)
# Top entablature
beveled_cube("cb_top", (6.5, 3.5, 0.5), bevel_offset=0.04,
             loc=(0, 0, 7.75), parent=caesar_box_e, mat_=M_MARBLE_WHITE)
# Decorative pediment
ped = beveled_cube("cb_ped", (6.5, 0.4, 1.5), bevel_offset=0.04,
                   loc=(0, 0, 8.5), parent=caesar_box_e, mat_=M_MARBLE_WHITE)
# Caesar's throne
beveled_cube("c_throne_seat", (1.6, 1.0, 0.4), bevel_offset=0.04,
             loc=(0, 0, 4.7), parent=caesar_box_e, mat_=M_TROPHY_GOLD)
beveled_cube("c_throne_back", (1.6, 0.20, 2.5), bevel_offset=0.05,
             loc=(0, 0.4, 6.0), parent=caesar_box_e, mat_=M_TROPHY_GOLD)
for arm_side in (-1, 1):
    beveled_cube(f"c_throne_arm_{arm_side}", (0.20, 0.80, 0.60),
                 loc=(arm_side*0.8, 0, 5.20), parent=caesar_box_e, mat_=M_TROPHY_GOLD)
# CAESAR (sitting)
caesar_e = empty("caesar", (0, 0, 5.3), parent=caesar_box_e)
# Toga purple (signature)
smooth_cone("c_toga", r1=0.50, r2=0.35, depth=1.5, segs=18,
            loc=(0, 0, 0), parent=caesar_e, mat_=M_TOGA_PURPLE)
# Hip
smooth_sphere("c_hip", r=0.30, loc=(0, 0, -0.50),
              parent=caesar_e, mat_=M_TOGA_PURPLE, scale=(1.4, 1.4, 0.5))
# Torso
beveled_cube("c_torso", (0.42, 0.25, 0.55), bevel_offset=0.05,
             loc=(0, 0, 0.95), parent=caesar_e, mat_=M_TOGA_PURPLE)
# Gold band edge (signature)
beveled_cube("c_band", (0.43, 0.05, 0.55), bevel_offset=0.03,
             loc=(0, -0.15, 0.95), parent=caesar_e, mat_=M_LAUREL_GOLD)
# Neck
cyl("c_neck", r=0.09, depth=0.16, segs=10, loc=(0, 0, 1.30),
    parent=caesar_e, mat_=M_SKIN_GLAD)
# Head
c_head_e = empty("c_he", (0, 0, 1.48), parent=caesar_e)
smooth_sphere("c_head", r=0.18, segs=20, rings=14, loc=(0, 0, 0),
              parent=c_head_e, mat_=M_SKIN_GLAD)
# Eyes
for side in (-1, 1):
    smooth_sphere(f"c_eye{side}", r=0.022,
                  loc=(side*0.06, -0.14, 0.02), parent=c_head_e,
                  mat_=mat(f"c_ew{side}", (0.05,0.05,0.05,1), 0, 0.5))
# Hair (short Roman curly)
smooth_sphere("c_hair", r=0.20, loc=(0, 0.03, 0.05),
              parent=c_head_e, mat_=M_HAIR_GLAD, scale=(1, 1, 0.85))
# LAUREL CROWN (signature Caesar)
for ci in range(14):
    ca = (ci / 14.0) * math.pi * 2
    leaf = beveled_cube(f"c_laurel{ci}", (0.05, 0.10, 0.02), bevel_offset=0.01,
                        loc=(0.22*math.cos(ca), 0.22*math.sin(ca), 0.18),
                        parent=c_head_e, mat_=M_LAUREL_GOLD)
    leaf.rotation_euler = (0, 0, ca)
# Arms raised (judging - thumbs up/down sign signature)
for side_idx, side in enumerate((-1, 1)):
    sh = empty(f"c_sh{side_idx}", (side*0.30, 0, 1.20), parent=caesar_e)
    sh.rotation_euler = (math.radians(-95), 0, math.radians(side*-25))
    smooth_cone(f"c_sleeve{side_idx}", r1=0.15, r2=0.10, depth=0.40, segs=12,
                loc=(0, 0, -0.20), parent=sh, mat_=M_TOGA_PURPLE)
    cyl(f"c_fa{side_idx}", r=0.07, depth=0.30, segs=10,
        loc=(0, 0, -0.55), parent=sh, mat_=M_SKIN_GLAD)
    smooth_sphere(f"c_hand{side_idx}", r=0.08, loc=(0, 0, -0.72),
                  parent=sh, mat_=M_SKIN_GLAD)
    # Thumb (Caesar's verdict signature)
    cyl(f"c_thumb{side_idx}", r=0.025, depth=0.10, segs=8,
        loc=(0, 0, -0.82), parent=sh, mat_=M_SKIN_GLAD)
# Trophy / scepter
smooth_cone("c_scepter", r1=0.05, r2=0.02, depth=1.0, segs=10,
            loc=(-0.5, 0, 0.5), parent=caesar_e, mat_=M_TROPHY_GOLD)
smooth_sphere("c_scepter_orb", r=0.10, loc=(-0.5, 0, 1.10),
              parent=caesar_e, mat_=M_TROPHY_GOLD)

# 4 SENATORS standing around Caesar
def make_senator(name, loc, toga_mat, facing=0):
    base = empty(name, loc)
    base.rotation_euler = (0, 0, facing)
    smooth_cone(f"{name}_toga", r1=0.50, r2=0.32, depth=2.0, segs=18,
                loc=(0, 0, 1.0), parent=base, mat_=toga_mat)
    cyl(f"{name}_belt", r=0.40, depth=0.08, segs=14,
        loc=(0, 0, 1.55), parent=base, mat_=M_LAUREL_GOLD)
    beveled_cube(f"{name}_torso", (0.42, 0.25, 0.55), bevel_offset=0.05,
                 loc=(0, 0, 1.95), parent=base, mat_=toga_mat)
    cyl(f"{name}_neck", r=0.09, depth=0.16, segs=10,
        loc=(0, 0, 2.30), parent=base, mat_=M_SKIN_GLAD)
    head_e = empty(f"{name}_he", (0, 0, 2.48), parent=base)
    smooth_sphere(f"{name}_head", r=0.18, segs=20, rings=14, loc=(0, 0, 0),
                  parent=head_e, mat_=M_SKIN_GLAD)
    smooth_sphere(f"{name}_hair", r=0.20, loc=(0, 0.03, 0.05),
                  parent=head_e, mat_=M_HAIR_GLAD, scale=(1, 1, 0.85))
    for side in (-1, 1):
        smooth_sphere(f"{name}_eye{side}", r=0.022,
                      loc=(side*0.06, -0.14, 0.02), parent=head_e,
                      mat_=mat(f"{name}_ew{side}", (0.05,0.05,0.05,1), 0, 0.5))
    # Arms raised applauding
    arms_e = []
    for side_idx, side in enumerate((-1, 1)):
        sh = empty(f"{name}_sh{side_idx}", (side*0.30, 0, 2.20), parent=base)
        sh.rotation_euler = (math.radians(-130), 0, math.radians(side*-20))
        smooth_cone(f"{name}_sleeve{side_idx}", r1=0.14, r2=0.09, depth=0.45, segs=12,
                    loc=(0, 0, -0.22), parent=sh, mat_=toga_mat)
        cyl(f"{name}_fa{side_idx}", r=0.07, depth=0.30, segs=10,
            loc=(0, 0, -0.60), parent=sh, mat_=M_SKIN_GLAD)
        smooth_sphere(f"{name}_hand{side_idx}", r=0.08, loc=(0, 0, -0.78),
                      parent=sh, mat_=M_SKIN_GLAD)
        arms_e.append(sh)
    base["_phase"] = random.uniform(0, math.pi*2)
    return {"root": base, "he": head_e, "arms": arms_e}

senators = [
    make_senator("sen1", (-3, -16, 4.5), M_TOGA_WHITE, math.radians(0)),
    make_senator("sen2", (3, -16, 4.5), M_TOGA_WHITE, math.radians(0)),
    make_senator("sen3", (-3, -18, 4.5), M_TOGA_RED, math.radians(20)),
    make_senator("sen4", (3, -18, 4.5), M_TOGA_RED, math.radians(-20)),
]

# ============ 8 SPECTATORS in lower tiers (visible) ============
spectators = []
spec_loc = [(-12, -8, 4.5), (12, -8, 4.5), (-15, 4, 4.5), (15, 4, 4.5),
            (-10, 10, 5.0), (10, 10, 5.0), (-5, 13, 5.0), (5, 13, 5.0)]
for i, (sx, sy, sz) in enumerate(spec_loc):
    sp = make_senator(f"spec{i}", (sx, sy, sz),
                       M_TUNIC_BROWN if i % 2 == 0 else M_TUNIC_BLUE,
                       facing=math.radians(180 if sy > 0 else 0))
    spectators.append(sp)

# ============ 4 GLADIATORS combat in arena ============
def make_gladiator(name, loc, type_g, facing=0):
    """type_g: 'retiarius' (net+trident), 'secutor' (helmet+gladius), 'mirmillo' (shield+gladius), 'hoplomachus' (spear+shield)"""
    base = empty(name, loc)
    base.rotation_euler = (0, 0, facing)
    # Legs (combat stance - separated)
    legs_e = []
    for side_idx, side in enumerate((-1, 1)):
        hip = empty(f"{name}_hip{side_idx}", (side*0.18, 0, 0.85), parent=base)
        # Lunge stance
        leg_rx = math.radians(20 if side_idx==0 else -10)
        hip.rotation_euler = (leg_rx, 0, 0)
        # Thigh
        cyl(f"{name}_thigh{side_idx}", r=0.12, depth=0.50, segs=12,
            loc=(0, 0, -0.25), parent=hip, mat_=M_SKIN_GLAD)
        smooth_sphere(f"{name}_knee{side_idx}", r=0.10, loc=(0, 0, -0.50),
                      parent=hip, mat_=M_SKIN_GLAD)
        # Calf
        cyl(f"{name}_calf{side_idx}", r=0.10, depth=0.45, segs=12,
            loc=(0, 0, -0.75), parent=hip, mat_=M_SKIN_GLAD)
        # Greaves (signature bronze leg armor for some)
        if type_g in ("secutor", "hoplomachus"):
            beveled_cube(f"{name}_greave{side_idx}", (0.13, 0.16, 0.40), bevel_offset=0.03,
                         loc=(0, -0.04, -0.75), parent=hip, mat_=M_BRONZE)
        # Sandals
        beveled_cube(f"{name}_sandal{side_idx}", (0.20, 0.30, 0.06),
                     loc=(0, 0.05, -1.0), parent=hip, mat_=M_LEATHER)
        legs_e.append(hip)
    # Loincloth/subligaculum (signature gladiator)
    smooth_cone(f"{name}_loin", r1=0.32, r2=0.25, depth=0.40, segs=14,
                loc=(0, 0, 0.95), parent=base, mat_=M_TUNIC_RED if type_g != "retiarius" else M_TUNIC_BROWN)
    # Belt + buckle
    cyl(f"{name}_belt", r=0.30, depth=0.10, segs=14,
        loc=(0, 0, 1.05), parent=base, mat_=M_BRONZE_DARK)
    beveled_cube(f"{name}_buckle", (0.10, 0.05, 0.10), loc=(0, -0.30, 1.05),
                 parent=base, mat_=M_BRONZE)
    # Torso muscular bare
    beveled_cube(f"{name}_torso", (0.40, 0.22, 0.55), bevel_offset=0.05,
                 loc=(0, 0, 1.42), parent=base, mat_=M_SKIN_GLAD)
    # Pectorals
    for side in (-1, 1):
        smooth_sphere(f"{name}_pec{side}", r=0.11,
                      loc=(side*0.10, -0.12, 1.55), parent=base,
                      mat_=M_SKIN_GLAD, scale=(1, 0.6, 0.7))
    # Abs
    for ab_row in range(3):
        for ab_col in (-1, 1):
            smooth_sphere(f"{name}_ab{ab_row}_{ab_col}", r=0.05,
                          loc=(ab_col*0.07, -0.12, 1.40 - ab_row*0.10),
                          parent=base, mat_=M_SKIN_GLAD, scale=(1, 0.4, 0.6))
    # Manica (arm guard - signature gladiator)
    arm_guard_side = -1 if type_g != "retiarius" else 1
    for sk in range(4):
        cyl(f"{name}_manica{sk}", r=0.10, depth=0.10, segs=14,
            loc=(arm_guard_side*0.30, 0, 1.45 + sk*0.10), parent=base, mat_=M_BRONZE)
    # Neck
    cyl(f"{name}_neck", r=0.09, depth=0.18, segs=10,
        loc=(0, 0, 1.78), parent=base, mat_=M_SKIN_GLAD)
    # Head + helmet
    head_e = empty(f"{name}_he", (0, 0, 1.95), parent=base)
    smooth_sphere(f"{name}_head", r=0.18, segs=20, rings=14, loc=(0, 0, 0),
                  parent=head_e, mat_=M_SKIN_GLAD)
    # Helmet type signature
    if type_g == "secutor":
        # Smooth round helmet (signature secutor - looks like fish to drown retiarius)
        smooth_sphere(f"{name}_helm", r=0.22, loc=(0, 0, 0.05),
                      parent=head_e, mat_=M_BRONZE, scale=(1, 1.2, 1))
        # Small eye holes
        for side in (-1, 1):
            smooth_sphere(f"{name}_he_hole{side}", r=0.025,
                          loc=(side*0.07, -0.18, 0.02), parent=head_e,
                          mat_=mat(f"{name}_hh{side}", (0.05,0.05,0.05,1), 0, 0.5))
        # Top crest
        beveled_cube(f"{name}_crest", (0.04, 0.30, 0.15), bevel_offset=0.01,
                     loc=(0, 0, 0.25), parent=head_e, mat_=M_TUNIC_RED)
    elif type_g == "mirmillo":
        # Helmet with crest (signature mirmillo)
        cyl(f"{name}_helm_b", r=0.22, depth=0.20, segs=18,
            loc=(0, 0, 0.05), parent=head_e, mat_=M_BRONZE)
        cyl(f"{name}_helm_top", r=0.20, depth=0.15, segs=18,
            loc=(0, 0, 0.20), parent=head_e, mat_=M_BRONZE)
        # Crest (high fan)
        for cr in range(5):
            crp = (cr - 2) * 0.10
            beveled_cube(f"{name}_cr{cr}", (0.03, 0.04, 0.30), bevel_offset=0.01,
                         loc=(crp, 0, 0.45), parent=head_e, mat_=M_TUNIC_RED)
        # Face visor
        beveled_cube(f"{name}_visor", (0.22, 0.10, 0.12), bevel_offset=0.02,
                     loc=(0, -0.13, 0.05), parent=head_e, mat_=M_BRONZE)
    elif type_g == "hoplomachus":
        # Brimmed helmet with feathers
        cyl(f"{name}_helm", r=0.22, depth=0.25, segs=18,
            loc=(0, 0, 0.05), parent=head_e, mat_=M_BRONZE)
        # Brim
        cyl(f"{name}_brim", r=0.28, depth=0.04, segs=18,
            loc=(0, 0, -0.08), parent=head_e, mat_=M_BRONZE)
        # Feather crest
        for fi in range(3):
            f_obj = beveled_cube(f"{name}_feat{fi}", (0.03, 0.04, 0.45), bevel_offset=0.01,
                                 loc=(0, 0, 0.40 + fi*0.05), parent=head_e, mat_=M_TUNIC_BLUE)
            f_obj.rotation_euler = (math.radians(fi*-5), 0, 0)
    else:  # retiarius - no helmet (signature retiarius unarmored head)
        # Hair
        smooth_sphere(f"{name}_hair", r=0.20, loc=(0, 0.03, 0.05),
                      parent=head_e, mat_=M_HAIR_GLAD, scale=(1, 1, 0.85))
        # Beard
        smooth_sphere(f"{name}_beard", r=0.10, loc=(0, -0.15, -0.10),
                      parent=head_e, mat_=M_HAIR_GLAD, scale=(1, 0.7, 0.9))
    # Arms (combat pose)
    arms_e = []
    arm_poses = {
        "retiarius": [(math.radians(-110), -30), (math.radians(-30), 20)],
        "secutor": [(math.radians(-90), -45), (math.radians(-90), 35)],
        "mirmillo": [(math.radians(-100), -20), (math.radians(-80), 30)],
        "hoplomachus": [(math.radians(-100), -30), (math.radians(-110), 20)],
    }
    pose = arm_poses.get(type_g, arm_poses["secutor"])
    for side_idx, side in enumerate((-1, 1)):
        sh = empty(f"{name}_sh{side_idx}", (side*0.30, 0, 1.70), parent=base)
        rx, rz = pose[side_idx]
        sh.rotation_euler = (rx, 0, math.radians(side*-15 + rz))
        # Bicep
        cyl(f"{name}_uarm{side_idx}", r=0.09, depth=0.40, segs=12,
            loc=(0, 0, -0.20), parent=sh, mat_=M_SKIN_GLAD)
        smooth_sphere(f"{name}_bicep{side_idx}", r=0.085,
                      loc=(0, -0.04, -0.20), parent=sh, mat_=M_SKIN_GLAD,
                      scale=(0.9, 0.7, 1.0))
        # Forearm
        cyl(f"{name}_fa{side_idx}", r=0.075, depth=0.38, segs=10,
            loc=(0, 0, -0.55), parent=sh, mat_=M_SKIN_GLAD)
        smooth_sphere(f"{name}_hand{side_idx}", r=0.08, loc=(0, 0, -0.78),
                      parent=sh, mat_=M_SKIN_GLAD)
        arms_e.append(sh)
    # Weapons + shield (signature per type)
    if type_g == "retiarius":
        # Trident in right hand (signature)
        trident_e = empty(f"{name}_trident_e", (0.10, -0.3, 0.5), parent=base)
        trident_e.rotation_euler = (math.radians(30), math.radians(45), 0)
        cyl(f"{name}_trident_shaft", r=0.04, depth=2.5, segs=10, loc=(0, 0, 0),
            parent=trident_e, mat_=M_TORCH_WOOD)
        # 3 prongs at top
        for pr in range(3):
            pa = (pr - 1) * 0.15
            prong = beveled_cube(f"{name}_prong{pr}", (0.04, 0.04, 0.40), bevel_offset=0.02,
                                 loc=(math.sin(pa)*0.10, 0, 1.50), parent=trident_e, mat_=M_IRON)
            prong.rotation_euler = (pa, 0, 0)
            smooth_cone(f"{name}_prong_tip{pr}", r1=0.04, r2=0.005, depth=0.15, segs=8,
                        loc=(math.sin(pa)*0.10, 0, 1.78), parent=trident_e, mat_=M_STEEL)
        # NET in left hand (signature retiarius)
        net_e = empty(f"{name}_net_e", (-0.25, -0.4, 1.0), parent=base)
        # Net flat patches
        for ni in range(8):
            na = (ni / 8.0) * math.pi * 2
            for sk in range(3):
                cyl(f"{name}_net{ni}_{sk}", r=0.012, depth=0.15, segs=4,
                    loc=(0.30*math.cos(na), 0.30*math.sin(na), -sk*0.20),
                    parent=net_e, mat_=M_NET)
    elif type_g == "secutor":
        # Gladius (short sword) in right hand
        sword_e = empty(f"{name}_sword_e", (-0.25, -0.5, 1.0), parent=base)
        sword_e.rotation_euler = (math.radians(70), math.radians(20), 0)
        # Blade
        beveled_cube(f"{name}_blade", (0.10, 0.04, 0.70), bevel_offset=0.02,
                     loc=(0, 0, 0.50), parent=sword_e, mat_=M_STEEL)
        # Hilt
        cyl(f"{name}_hilt", r=0.04, depth=0.20, segs=10, loc=(0, 0, 0.10),
            parent=sword_e, mat_=M_LEATHER)
        # Crossguard
        beveled_cube(f"{name}_crossguard", (0.15, 0.05, 0.04), bevel_offset=0.01,
                     loc=(0, 0, 0.20), parent=sword_e, mat_=M_BRONZE)
        # Pommel
        smooth_sphere(f"{name}_pommel", r=0.05, loc=(0, 0, 0), parent=sword_e, mat_=M_BRONZE)
        # Small scutum shield in left hand
        shield_e = empty(f"{name}_shield_e", (0.30, -0.5, 1.0), parent=base)
        shield_e.rotation_euler = (0, math.radians(-30), 0)
        beveled_cube(f"{name}_shield", (0.6, 0.04, 0.8), bevel_offset=0.04,
                     loc=(0, 0, 0), parent=shield_e, mat_=M_TUNIC_RED)
        # Center boss
        smooth_sphere(f"{name}_boss", r=0.10, loc=(0, -0.04, 0),
                      parent=shield_e, mat_=M_BRONZE)
    elif type_g == "mirmillo":
        # Gladius right
        sword_e = empty(f"{name}_sword_e", (-0.25, -0.5, 1.0), parent=base)
        sword_e.rotation_euler = (math.radians(60), math.radians(40), 0)
        beveled_cube(f"{name}_blade", (0.10, 0.04, 0.70), bevel_offset=0.02,
                     loc=(0, 0, 0.50), parent=sword_e, mat_=M_STEEL)
        cyl(f"{name}_hilt", r=0.04, depth=0.20, segs=10, loc=(0, 0, 0.10),
            parent=sword_e, mat_=M_LEATHER)
        beveled_cube(f"{name}_crossguard", (0.15, 0.05, 0.04), bevel_offset=0.01,
                     loc=(0, 0, 0.20), parent=sword_e, mat_=M_BRONZE)
        # LARGE scutum shield (signature mirmillo)
        shield_e = empty(f"{name}_shield_e", (0.30, -0.5, 1.0), parent=base)
        shield_e.rotation_euler = (0, math.radians(-30), 0)
        beveled_cube(f"{name}_shield", (1.0, 0.05, 1.2), bevel_offset=0.05,
                     loc=(0, 0, 0), parent=shield_e, mat_=M_TUNIC_BLUE)
        # Boss center
        smooth_sphere(f"{name}_boss", r=0.15, loc=(0, -0.05, 0),
                      parent=shield_e, mat_=M_LAUREL_GOLD)
        # Decorative ring
        cyl(f"{name}_shield_ring", r=0.55, depth=0.02, segs=24,
            loc=(0, -0.04, 0), parent=shield_e, mat_=M_LAUREL_GOLD).rotation_euler = (math.radians(90), 0, 0)
    elif type_g == "hoplomachus":
        # Long spear (signature hoplomachus)
        spear_e = empty(f"{name}_spear_e", (-0.25, -0.4, 1.0), parent=base)
        spear_e.rotation_euler = (math.radians(30), math.radians(60), 0)
        cyl(f"{name}_spear_shaft", r=0.04, depth=3.0, segs=10, loc=(0, 0, 0),
            parent=spear_e, mat_=M_TORCH_WOOD)
        smooth_cone(f"{name}_spear_tip", r1=0.06, r2=0.005, depth=0.30, segs=10,
                    loc=(0, 0, 1.65), parent=spear_e, mat_=M_STEEL)
        # Round shield (parmula - small signature)
        shield_e = empty(f"{name}_shield_e", (0.30, -0.5, 1.0), parent=base)
        shield_e.rotation_euler = (0, math.radians(-30), 0)
        cyl(f"{name}_shield_disc", r=0.45, depth=0.05, segs=24,
            loc=(0, 0, 0), parent=shield_e, mat_=M_BRONZE).rotation_euler = (math.radians(90), 0, 0)
        # Boss
        smooth_sphere(f"{name}_boss", r=0.10, loc=(0, -0.04, 0),
                      parent=shield_e, mat_=M_LAUREL_GOLD)
    base["_phase"] = random.uniform(0, math.pi*2)
    return {"root": base, "he": head_e, "arms": arms_e, "legs": legs_e, "type": type_g}

# 4 gladiators in combat pairs
gladiators = [
    make_gladiator("glad1", (-3, 2, 0), "retiarius", math.radians(-45)),
    make_gladiator("glad2", (3, 2, 0), "secutor", math.radians(135)),
    make_gladiator("glad3", (-3, -4, 0), "mirmillo", math.radians(45)),
    make_gladiator("glad4", (3, -4, 0), "hoplomachus", math.radians(-135)),
]

# ============ LIONS CAGE ============
cage_e = empty("cage", loc=(15, 8, 0))
cage_e.rotation_euler = (0, 0, math.radians(-30))
# Cage floor
beveled_cube("cage_floor", (3, 2, 0.20), bevel_offset=0.04,
             loc=(0, 0, 0.10), parent=cage_e, mat_=M_TRAVERTINE)
# 4 corner posts
for x in (-1, 1):
    for y in (-1, 1):
        cyl(f"cage_p_{x}{y}", r=0.10, depth=2.5, segs=10,
            loc=(x*1.4, y*0.9, 1.35), parent=cage_e, mat_=M_CAGE)
# Vertical bars
for i in range(14):
    ba = (i / 14.0) * math.pi * 2
    bx = 1.4 * math.cos(ba)
    by = 0.9 * math.sin(ba)
    cyl(f"cage_b{i}", r=0.04, depth=2.4, segs=6,
        loc=(bx, by, 1.30), parent=cage_e, mat_=M_CAGE)
# Top horizontal frame
for tx in (-1, 1):
    for ty in (-1, 1):
        beveled_cube(f"cage_top_{tx}{ty}", (2.8, 0.10, 0.10),
                     loc=(0, ty*0.9, 2.55), parent=cage_e, mat_=M_CAGE)
        beveled_cube(f"cage_top_y_{tx}{ty}", (0.10, 1.8, 0.10),
                     loc=(tx*1.4, 0, 2.55), parent=cage_e, mat_=M_CAGE)
# Top roof
beveled_cube("cage_roof", (3, 2, 0.15), bevel_offset=0.04,
             loc=(0, 0, 2.65), parent=cage_e, mat_=M_CAGE)

# Lion inside cage
lion_e = empty("lion", (0, 0, 0.5), parent=cage_e)
# Body
smooth_sphere("lion_body", r=0.40, segs=20, rings=14, loc=(0, 0, 0.40),
              parent=lion_e, mat_=M_LION_GOLD, scale=(1.7, 1, 1))
# Head
lion_head_e = empty("lion_he", (0.65, 0, 0.50), parent=lion_e)
smooth_sphere("lion_head", r=0.30, segs=20, rings=14, loc=(0, 0, 0),
              parent=lion_head_e, mat_=M_LION_GOLD)
# MANE (signature - 16 mane segments around head)
for mi in range(16):
    ma = (mi / 16.0) * math.pi * 2
    smooth_sphere(f"lion_mane{mi}", r=0.18,
                  loc=(-0.05 + math.cos(ma)*0.25, math.sin(ma)*0.25, 0.0),
                  parent=lion_head_e, mat_=M_LION_MANE)
# Muzzle
smooth_cone("lion_muzzle", r1=0.18, r2=0.14, depth=0.20, segs=12,
            loc=(0.30, 0, -0.05), parent=lion_head_e,
            mat_=M_LION_GOLD).rotation_euler = (0, math.radians(90), 0)
# Glowing eyes
for side in (-1, 1):
    smooth_sphere(f"lion_eye{side}", r=0.05,
                  loc=(0.18, side*0.12, 0.10), parent=lion_head_e, mat_=M_LION_EYE)
# Fangs (open roar mouth signature)
for side in (-1, 1):
    smooth_cone(f"lion_fang{side}", r1=0.04, r2=0.005, depth=0.10, segs=8,
                loc=(0.42, side*0.06, -0.05), parent=lion_head_e,
                mat_=M_FANG).rotation_euler = (0, math.radians(180), 0)
# 4 legs
for x_idx, x in enumerate((0.40, -0.40)):
    for y_idx, y in enumerate((-0.30, 0.30)):
        cyl(f"lion_leg{x_idx}{y_idx}", r=0.10, depth=0.50, segs=10,
            loc=(x, y, 0.20), parent=lion_e, mat_=M_LION_GOLD)
        cyl(f"lion_paw{x_idx}{y_idx}", r=0.12, depth=0.10, segs=10,
            loc=(x, y, 0.0), parent=lion_e, mat_=M_LION_GOLD)
# Tail with tuft
cyl("lion_tail", r=0.05, depth=0.80, segs=10,
    loc=(-0.65, 0, 0.55), parent=lion_e, mat_=M_LION_GOLD)
smooth_sphere("lion_tail_tuft", r=0.10, loc=(-1.05, 0, 0.40),
              parent=lion_e, mat_=M_LION_MANE)
# 2nd lion (smaller, in same cage)
lion2_e = empty("lion2", (-1.0, 0.5, 0.5), parent=cage_e)
smooth_sphere("lion2_body", r=0.32, segs=20, rings=14, loc=(0, 0, 0.35),
              parent=lion2_e, mat_=M_LION_GOLD, scale=(1.6, 1, 1))
lion2_head_e = empty("lion2_he", (0.50, 0, 0.45), parent=lion2_e)
smooth_sphere("lion2_head", r=0.25, segs=20, rings=14, loc=(0, 0, 0),
              parent=lion2_head_e, mat_=M_LION_GOLD)
for mi in range(14):
    ma = (mi / 14.0) * math.pi * 2
    smooth_sphere(f"lion2_mane{mi}", r=0.15,
                  loc=(-0.05 + math.cos(ma)*0.20, math.sin(ma)*0.20, 0.0),
                  parent=lion2_head_e, mat_=M_LION_MANE)

# ============ 8 SPQR FLAGS on poles ============
spqr_flags = []
for fi in range(8):
    fa = (fi / 8.0) * math.pi * 2
    fr_x = 27 * math.cos(fa)
    fr_y = 21 * math.sin(fa)
    f_e = empty(f"flag{fi}", (fr_x, fr_y, 0))
    # Pole
    cyl(f"flag_pole{fi}", r=0.10, depth=12.0, segs=10,
        loc=(0, 0, 6.0), parent=f_e, mat_=M_POLE)
    # Gold eagle (signature SPQR top)
    smooth_sphere(f"flag_eagle_b{fi}", r=0.15, loc=(0, 0, 12.0),
                  parent=f_e, mat_=M_FLAG_GOLD, scale=(1, 1.2, 1))
    # Eagle wings spread
    for w_side in (-1, 1):
        beveled_cube(f"flag_eagle_w{fi}_{w_side}", (0.30, 0.05, 0.20), bevel_offset=0.02,
                     loc=(0, w_side*0.20, 12.0), parent=f_e, mat_=M_FLAG_GOLD)
    # Flag cloth (rectangular red)
    flag_cloth_e = empty(f"flag_cloth_e{fi}", (0, 0, 9.0), parent=f_e)
    beveled_cube(f"flag_cloth{fi}", (0.6, 0.05, 2.0), bevel_offset=0.03,
                 loc=(0.40, 0, 0), parent=flag_cloth_e, mat_=M_FLAG_SPQR)
    # SPQR gold letters (4 small)
    for li_idx in range(4):
        beveled_cube(f"flag_letter{fi}_{li_idx}", (0.10, 0.06, 0.15), bevel_offset=0.01,
                     loc=(0.40, -0.04, 0.40 - li_idx*0.30), parent=flag_cloth_e,
                     mat_=M_FLAG_GOLD)
    f_e["_phase"] = random.uniform(0, math.pi*2)
    spqr_flags.append({"e": f_e, "cloth": flag_cloth_e})

# ============ 4 TORCHES on pylons ============
torches = []
torch_pos = [(-14, -10, 0), (14, -10, 0), (-14, 10, 0), (14, 10, 0)]
for ti, (tx, ty, tz) in enumerate(torch_pos):
    t_e = empty(f"torch{ti}", (tx, ty, tz))
    # Stone pylon
    beveled_cube(f"t_pylon{ti}", (1.0, 1.0, 5), bevel_offset=0.06,
                 loc=(0, 0, 2.5), parent=t_e, mat_=M_TRAVERTINE)
    # Bowl top
    smooth_sphere(f"t_bowl{ti}", r=0.50, segs=18, rings=12,
                  loc=(0, 0, 5.3), parent=t_e, mat_=M_BRONZE_DARK, scale=(1, 1, 0.6))
    # Flame composite
    flame_e = empty(f"t_fl{ti}", (0, 0, 5.7), parent=t_e)
    smooth_cone(f"t_fl_o{ti}", r1=0.45, r2=0.05, depth=1.8, segs=14,
                loc=(0, 0, 0.9), parent=flame_e, mat_=M_FIRE_OUTER)
    smooth_cone(f"t_fl_c{ti}", r1=0.25, r2=0.02, depth=1.2, segs=14,
                loc=(0, 0, 0.6), parent=flame_e, mat_=M_FIRE_CORE)
    # Smoke column
    for si in range(4):
        smooth_sphere(f"t_smoke{ti}_{si}", r=0.30 + si*0.10,
                      loc=(math.sin(si*0.6)*0.20, math.cos(si*0.6)*0.20, 7.0 + si*0.7),
                      parent=t_e, mat_=M_SMOKE)
    t_e["_phase"] = random.uniform(0, math.pi*2)
    torches.append({"e": t_e, "flame": flame_e})

# ============================================================
# ⭐ 600 DUST + 400 SPARKS (PARTICULES THÉMATIQUES OBLIGATOIRES)
# ============================================================
# 600 dust drift (signature arena combat)
dust_particles = []
for i in range(600):
    px = random.uniform(-18, 18)
    py = random.uniform(-12, 12)
    pz = random.uniform(0.5, 4)
    col = M_DUST if i % 2 == 0 else M_DUST_DARK
    d_obj = smooth_sphere(f"dust{i}", r=random.uniform(0.08, 0.16), segs=8, rings=6,
                          loc=(px, py, pz), mat_=col)
    d_obj["_phase"] = random.uniform(0, math.pi*2)
    d_obj["_base_x"] = px; d_obj["_base_y"] = py; d_obj["_base_z"] = pz
    d_obj["_amp_x"] = random.uniform(0.6, 1.6)
    d_obj["_amp_y"] = random.uniform(0.6, 1.6)
    d_obj["_amp_z"] = random.uniform(0.3, 0.8)
    d_obj["_speed"] = random.uniform(0.3, 0.8)
    dust_particles.append(d_obj)

# 400 sparks (signature weapons clash)
sparks = []
# Sparks concentrated near gladiators
spark_centers = [(0, 2, 1.5), (0, -4, 1.5)]
for i in range(400):
    cx, cy, cz = spark_centers[i % 2]
    px = cx + random.uniform(-2, 2)
    py = cy + random.uniform(-2, 2)
    pz = cz + random.uniform(-0.5, 1.5)
    col = M_SPARK if i % 2 == 0 else M_SPARK_ORANGE
    s_obj = smooth_sphere(f"spark{i}", r=random.uniform(0.04, 0.08), segs=8, rings=6,
                          loc=(px, py, pz), mat_=col)
    s_obj["_phase"] = random.uniform(0, math.pi*2)
    s_obj["_base_x"] = px; s_obj["_base_y"] = py; s_obj["_base_z"] = pz
    s_obj["_amp"] = random.uniform(0.3, 1.0)
    s_obj["_speed"] = random.uniform(2.0, 4.0)
    sparks.append(s_obj)

# ============ ANIMATION ============
fps = 30; duration_s = 6; total_frames = fps * duration_s

# Gladiators combat (body sway + arms swing + leg shift)
for g in gladiators:
    phase = g["root"]["_phase"]
    base_z = g["root"].location.z
    for f in range(1, total_frames + 1, 3):
        t = (f - 1) / fps
        # Body sway (combat intensity)
        g["root"].location.z = base_z + abs(math.sin(t * 3.0 + phase)) * 0.10
        g["root"].rotation_euler = (math.sin(t * 1.5 + phase) * math.radians(8),
                                     math.cos(t * 1.2 + phase) * math.radians(6),
                                     g["root"].rotation_euler.z + math.sin(t * 0.6 + phase) * math.radians(10))
        g["root"].keyframe_insert("location", frame=f)
        g["root"].keyframe_insert("rotation_euler", frame=f)
        # Arms swing (combat strikes)
        for ai, arm in enumerate(g["arms"]):
            base_rx = arm.rotation_euler.x
            base_rz = arm.rotation_euler.z
            swing = math.sin(t * 4.5 + phase + ai * math.pi) * math.radians(30)
            arm.rotation_euler = (base_rx + swing, 0, base_rz)
            arm.keyframe_insert("rotation_euler", frame=f)
        # Head turn (look at opponent)
        g["he"].rotation_euler = (math.sin(t * 2.0 + phase) * math.radians(8), 0,
                                    math.sin(t * 1.5 + phase) * math.radians(12))
        g["he"].keyframe_insert("rotation_euler", frame=f)

# Caesar slight head turn + arm gestures
c_he = bpy.data.objects.get("c_he")
if c_he:
    for f in range(1, total_frames + 1, 5):
        t = (f - 1) / fps
        c_he.rotation_euler = (math.sin(t * 0.8) * math.radians(5), 0,
                                math.sin(t * 0.5) * math.radians(15))
        c_he.keyframe_insert("rotation_euler", frame=f)

# Senators applaud
for sen in senators:
    phase = sen["root"]["_phase"]
    for f in range(1, total_frames + 1, 4):
        t = (f - 1) / fps
        for ai, arm in enumerate(sen["arms"]):
            wave = math.sin(t * 4.0 + phase + ai * math.pi) * math.radians(15)
            arm.rotation_euler = (math.radians(-130) + wave, 0, math.radians((-1 if ai==0 else 1)*-20))
            arm.keyframe_insert("rotation_euler", frame=f)
        sen["he"].rotation_euler = (math.sin(t * 1.5 + phase) * math.radians(6), 0,
                                       math.sin(t * 1.2 + phase) * math.radians(10))
        sen["he"].keyframe_insert("rotation_euler", frame=f)

# Spectators bob applaud
for sp in spectators:
    phase = sp["root"]["_phase"]
    base_z = sp["root"].location.z
    for f in range(1, total_frames + 1, 4):
        t = (f - 1) / fps
        sp["root"].location.z = base_z + abs(math.sin(t * 2.5 + phase)) * 0.05
        sp["root"].keyframe_insert("location", frame=f)
        for ai, arm in enumerate(sp["arms"]):
            wave = math.sin(t * 4.5 + phase + ai * math.pi) * math.radians(20)
            arm.rotation_euler = (math.radians(-130) + wave, 0, math.radians((-1 if ai==0 else 1)*-20))
            arm.keyframe_insert("rotation_euler", frame=f)

# Lions roar (head movement, body shake)
lion_he_obj = bpy.data.objects.get("lion_he")
if lion_he_obj:
    for f in range(1, total_frames + 1, 3):
        t = (f - 1) / fps
        lion_he_obj.rotation_euler = (math.sin(t * 2.0) * math.radians(15), 0,
                                        math.sin(t * 1.5) * math.radians(10))
        lion_he_obj.keyframe_insert("rotation_euler", frame=f)

# SPQR flags flap
for fl in spqr_flags:
    phase = fl["e"]["_phase"]
    for f in range(1, total_frames + 1, 3):
        t = (f - 1) / fps
        fl["cloth"].rotation_euler = (math.sin(t * 3.5 + phase) * math.radians(20),
                                        math.cos(t * 3.0 + phase) * math.radians(15),
                                        math.sin(t * 2.5 + phase) * math.radians(10))
        fl["cloth"].keyframe_insert("rotation_euler", frame=f)

# Torch flames flicker
for tr in torches:
    phase = tr["e"]["_phase"]
    for f in range(1, total_frames + 1, 3):
        t = (f - 1) / fps
        s = 1 + math.sin(t * 5.0 + phase) * 0.15
        tr["flame"].scale = (1 + math.sin(t * 4.0 + phase) * 0.12,
                              1 + math.cos(t * 4.5 + phase) * 0.12, s)
        tr["flame"].rotation_euler = (0, 0, math.sin(t * 3.0 + phase) * 0.18)
        tr["flame"].keyframe_insert("scale", frame=f)
        tr["flame"].keyframe_insert("rotation_euler", frame=f)

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
            s = 1 + math.sin(t * 0.7) * 0.05
            obj.scale = (s, s, s)
            obj.keyframe_insert("scale", frame=f)

# ============================================================
# ⭐⭐⭐ 600 DUST drift (signature arena combat)
# ============================================================
for d in dust_particles:
    phase = d["_phase"]; speed = d["_speed"]
    bx, by, bz = d["_base_x"], d["_base_y"], d["_base_z"]
    ax, ay, az = d["_amp_x"], d["_amp_y"], d["_amp_z"]
    for f in range(1, total_frames + 1, 4):
        t = (f - 1) / fps
        x = bx + ax * math.sin(t * speed + phase)
        y = by + ay * math.cos(t * speed * 0.9 + phase)
        z = bz + az * math.sin(t * speed * 1.3 + phase * 1.5)
        d.location = (x, y, max(0.2, z))
        sc = 1 + math.sin(t * 2.5 + phase) * 0.25
        d.scale = (sc, sc, sc)
        d.keyframe_insert("location", frame=f)
        d.keyframe_insert("scale", frame=f)

# 400 SPARKS jaillissent (rise quickly + fade)
for s in sparks:
    phase = s["_phase"]; speed = s["_speed"]
    bx, by, bz = s["_base_x"], s["_base_y"], s["_base_z"]
    amp = s["_amp"]
    for f in range(1, total_frames + 1, 3):
        t = (f - 1) / fps
        # Rise rapid + spiral
        z = bz + (speed * t) % 4
        x = bx + amp * math.sin(t * 3.0 + phase) * 0.5
        y = by + amp * math.cos(t * 2.5 + phase) * 0.5
        s.location = (x, y, min(6, z))
        # Pulse
        sc = 1 + math.sin(t * 6.0 + phase) * 0.4
        s.scale = (sc, sc, sc)
        s.keyframe_insert("location", frame=f)
        s.keyframe_insert("scale", frame=f)

# ============ EXPORT ============
out_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "public", "_pbr_test")
out_dir = os.path.normpath(out_dir)
os.makedirs(out_dir, exist_ok=True)
out_glb = os.path.join(out_dir, "pbr_colosseum_proc.glb")

bpy.ops.object.select_all(action='SELECT')
bpy.ops.export_scene.gltf(
    filepath=out_glb, export_format='GLB',
    export_animations=True, export_apply=False, export_yup=True, use_selection=False,
)
size_mb = os.path.getsize(out_glb) / (1024 * 1024)
print(f"[proc_roman_colosseum_gladiators] DONE → {out_glb} ({size_mb:.2f} MB)")
print(f"[proc_roman_colosseum_gladiators] ONE arena + Colosseum 4-tier 80 arches + Caesar throne+laurel + 4 senators + 8 spectators + 100 small spectators + 4 gladiators (retiarius+secutor+mirmillo+hoplomachus) + 2 lions cage + 8 SPQR flags + 4 torches + 600 DUST + 400 SPARKS")
print("⭐ FIXES: 1 arena + 600 dust drift + 400 sparks rise (signature combat antique mandatory) ⭐")
