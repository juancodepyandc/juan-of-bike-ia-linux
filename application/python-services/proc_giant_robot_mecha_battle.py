"""
proc_giant_robot_mecha_battle.py — 192e procédural AuroraIA (56e qualité)
2 mécas géants en combat + ville détruite + missiles + sparks + drones + smoke + débris
"""
import bpy, bmesh, math, random, os

random.seed(0xBEEF192)

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
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me); bm.free(); smooth_shade(me)
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
M_SKY = mat("sky", (0.30, 0.08, 0.06, 1.0), 0.0, 0.7, emission=(0.45,0.10,0.08), emission_strength=1.2)
M_GROUND = mat("ground", (0.18, 0.15, 0.12, 1.0), 0.2, 0.75)
M_RUBBLE = mat("rubble", (0.30, 0.27, 0.22, 1.0), 0.0, 0.85)
M_BUILDING_DARK = mat("bld_dark", (0.22, 0.20, 0.20, 1.0), 0.3, 0.6)
M_BUILDING = mat("bld", (0.45, 0.40, 0.38, 1.0), 0.2, 0.65)
M_WINDOW = mat("window", (1.0, 0.65, 0.20, 1.0), 0.0, 0.20, emission=(1.0,0.60,0.18), emission_strength=4.0)

# Mecha 1 (blue) materials
M_MECHA1_PRIM = mat("m1_prim", (0.15, 0.30, 0.65, 1.0), 0.85, 0.32, emission=(0.10,0.25,0.55), emission_strength=0.5)
M_MECHA1_SEC = mat("m1_sec", (0.85, 0.20, 0.15, 1.0), 0.7, 0.38, emission=(0.75,0.18,0.12), emission_strength=0.5)
M_MECHA1_DARK = mat("m1_dark", (0.10, 0.10, 0.13, 1.0), 0.85, 0.40)

# Mecha 2 (red)
M_MECHA2_PRIM = mat("m2_prim", (0.55, 0.10, 0.12, 1.0), 0.85, 0.32, emission=(0.50,0.10,0.10), emission_strength=0.5)
M_MECHA2_SEC = mat("m2_sec", (0.90, 0.80, 0.20, 1.0), 0.7, 0.35, emission=(0.85,0.72,0.20), emission_strength=0.6)
M_MECHA2_DARK = mat("m2_dark", (0.12, 0.08, 0.10, 1.0), 0.85, 0.40)

M_METAL = mat("metal", (0.45, 0.45, 0.48, 1.0), 0.92, 0.20, emission=(0.35,0.35,0.38), emission_strength=0.3)
M_GLASS_COCKPIT = mat("cockpit_glass", (0.50, 0.85, 1.0, 0.6), 0.0, 0.10, emission=(0.40,0.70,0.95), emission_strength=2.0, alpha=0.6)

M_PLASMA_BLUE = mat("plasma_blue", (0.40, 0.80, 1.0, 1.0), 0.0, 0.05, emission=(0.50,0.90,1.0), emission_strength=18.0)
M_PLASMA_RED = mat("plasma_red", (1.0, 0.30, 0.20, 1.0), 0.0, 0.05, emission=(1.0,0.40,0.25), emission_strength=18.0)
M_LASER_BLUE = mat("laser_blue", (0.30, 0.70, 1.0, 1.0), 0.0, 0.05, emission=(0.40,0.80,1.0), emission_strength=25.0)
M_LASER_RED = mat("laser_red", (1.0, 0.20, 0.10, 1.0), 0.0, 0.05, emission=(1.0,0.30,0.15), emission_strength=25.0)

M_FLAME = mat("flame", (1.0, 0.50, 0.10, 1.0), 0.0, 0.10, emission=(1.0,0.55,0.15), emission_strength=12.0)
M_FLAME_INNER = mat("flame_in", (1.0, 0.85, 0.30, 1.0), 0.0, 0.10, emission=(1.0,0.90,0.40), emission_strength=18.0)
M_SPARK = mat("spark", (1.0, 0.95, 0.40, 1.0), 0.0, 0.05, emission=(1.0,0.95,0.50), emission_strength=20.0)
M_SMOKE = mat("smoke", (0.20, 0.18, 0.18, 1.0), 0.0, 0.85, emission=(0.30,0.25,0.22), emission_strength=0.5, alpha=0.4)
M_MISSILE = mat("missile", (0.55, 0.50, 0.45, 1.0), 0.7, 0.35, emission=(0.50,0.45,0.40), emission_strength=0.3)
M_MISSILE_TRAIL = mat("missile_trail", (1.0, 0.65, 0.30, 1.0), 0.0, 0.10, emission=(1.0,0.70,0.35), emission_strength=15.0)

M_DRONE = mat("drone", (0.30, 0.30, 0.35, 1.0), 0.85, 0.35, emission=(0.25,0.25,0.28), emission_strength=0.3)
M_DRONE_LIGHT = mat("drone_light", (1.0, 0.30, 0.30, 1.0), 0.0, 0.10, emission=(1.0,0.35,0.35), emission_strength=12.0)
M_DRONE_PROP = mat("drone_prop", (0.20, 0.20, 0.22, 1.0), 0.5, 0.45)

# ============ SKY ============
sky = smooth_sphere("sky", r=85, segs=32, rings=20, loc=(0,0,0), mat_=M_SKY, scale=(1,1,0.6))
sky.scale = (1,1,0.6)
# Storm clouds (8)
clouds = []
for i in range(8):
    a = (i / 8.0) * math.pi * 2
    cx, cy = 30*math.cos(a), 30*math.sin(a)
    cz = 22 + random.uniform(-3, 4)
    c_e = empty(f"cloud_e{i}", (cx, cy, cz))
    for j in range(4):
        smooth_sphere(f"cloud{i}_{j}", r=random.uniform(2.5, 4.0),
                      loc=(random.uniform(-2.5,2.5), random.uniform(-1.5,1.5), random.uniform(-0.5,0.5)),
                      parent=c_e, mat_=M_SMOKE)
    clouds.append(c_e)

# ============ GROUND ============
ground = beveled_cube("ground", (60, 60, 0.4), bevel_offset=0.05, loc=(0,0,-0.2), mat_=M_GROUND)
# Rubble piles (20)
for i in range(20):
    a = random.uniform(0, math.pi*2)
    rad = random.uniform(4, 22)
    rx, ry = rad*math.cos(a), rad*math.sin(a)
    rs = random.uniform(0.4, 1.0)
    rock = smooth_sphere(f"rubble{i}", r=rs,
                        loc=(rx, ry, rs*0.4), mat_=M_RUBBLE,
                        scale=(random.uniform(0.8,1.2), random.uniform(0.8,1.2), random.uniform(0.5,0.9)))
    rock.rotation_euler = (0, 0, random.uniform(0, math.pi*2))

# Ground crackle (12 small flame patches)
ground_flames = []
for i in range(12):
    a = random.uniform(0, math.pi*2)
    rad = random.uniform(3, 18)
    fx, fy = rad*math.cos(a), rad*math.sin(a)
    f_e = empty(f"gflame_e{i}", (fx, fy, 0))
    outer = smooth_cone(f"gflame_o{i}", r1=0.30, r2=0.02, depth=0.7, segs=10,
                       loc=(0,0,0.35), parent=f_e, mat_=M_FLAME)
    inner = smooth_cone(f"gflame_i{i}", r1=0.18, r2=0.01, depth=0.5, segs=10,
                       loc=(0,0,0.40), parent=f_e, mat_=M_FLAME_INNER)
    outer["_phase"] = i * 0.5
    inner["_phase"] = i * 0.5 + 0.3
    ground_flames.append((outer, inner))

# ============ DESTROYED BUILDINGS (8) ============
for i in range(8):
    a = (i / 8.0) * math.pi * 2 + random.uniform(-0.1, 0.1)
    rad = random.uniform(18, 26)
    bx, by = rad*math.cos(a), rad*math.sin(a)
    b_e = empty(f"bld_e{i}", (bx, by, 0))
    b_e.rotation_euler = (0, 0, a + math.pi/2)
    # Building heights random
    height = random.uniform(6, 14)
    # Main body (slightly tilted - destroyed)
    body = beveled_cube(f"bld_body{i}", (3.0, 3.0, height), bevel_offset=0.10,
                       loc=(0, 0, height/2), parent=b_e, mat_=M_BUILDING)
    body.rotation_euler = (math.radians(random.uniform(-8,8)),
                           math.radians(random.uniform(-8,8)), 0)
    # Broken top (jagged)
    for j in range(3):
        chunk = beveled_cube(f"bld_chunk{i}_{j}", (random.uniform(0.8,1.5), random.uniform(0.8,1.5), random.uniform(0.6,1.2)),
                            loc=(random.uniform(-1,1), random.uniform(-1,1), height + random.uniform(0.3,1.0)),
                            parent=b_e, mat_=M_BUILDING_DARK)
        chunk.rotation_euler = (math.radians(random.uniform(-30,30)),
                                math.radians(random.uniform(-30,30)),
                                math.radians(random.uniform(0,90)))
    # Windows (some illuminated, some dark)
    for w in range(int(height)):
        for side_idx, side in enumerate((-1, 1)):
            if random.random() < 0.5:
                m_ = M_WINDOW if random.random() < 0.4 else M_BUILDING_DARK
                beveled_cube(f"bld_win_{i}_{w}_{side_idx}", (3.2, 0.10, 0.30),
                             loc=(0, side*1.55, w*0.9 + 0.5), parent=b_e, mat_=m_)

# ============ MECHA (parameterized constructor) ============
def make_mecha(name, loc, primary, secondary, dark, plasma_color, laser_color):
    """Giant 6m mecha with cockpit head + arms with cannon/sword + hydraulic legs + jetpack"""
    base = empty(name, loc)
    # ===== LEGS (hydraulic, 4-seg per leg) =====
    legs_e = []
    for side_idx, side in enumerate((-1, 1)):
        leg_e = empty(f"{name}_leg_e{side_idx}", (side*0.55, 0, 2.0), parent=base)
        legs_e.append(leg_e)
        # Hip joint sphere
        smooth_sphere(f"{name}_hip{side_idx}", r=0.35, loc=(0,0,0),
                      parent=leg_e, mat_=primary)
        # Thigh (with hydraulic piston visible)
        beveled_cube(f"{name}_thigh{side_idx}", (0.45, 0.45, 1.2),
                     loc=(0, 0, -0.8), parent=leg_e, mat_=primary)
        # Piston cylinder
        cyl(f"{name}_piston{side_idx}", r=0.10, depth=0.9, segs=12,
            loc=(0.30, 0, -0.7), parent=leg_e, mat_=M_METAL)
        # Knee joint
        knee_e = empty(f"{name}_knee{side_idx}", (0, 0, -1.45), parent=leg_e)
        smooth_sphere(f"{name}_kneecap{side_idx}", r=0.30, loc=(0,0,0),
                      parent=knee_e, mat_=secondary)
        # Shin
        beveled_cube(f"{name}_shin{side_idx}", (0.40, 0.40, 1.15),
                     loc=(0, 0, -0.75), parent=knee_e, mat_=primary)
        # Calf piston
        cyl(f"{name}_calf_piston{side_idx}", r=0.08, depth=0.9, segs=10,
            loc=(0.25, 0, -0.7), parent=knee_e, mat_=M_METAL)
        # Foot (large stomping pad)
        foot = beveled_cube(f"{name}_foot{side_idx}", (0.85, 1.1, 0.35),
                            bevel_offset=0.08,
                            loc=(0, 0.10, -1.50), parent=knee_e, mat_=dark)
        # Toe armor (3 plates)
        for i in range(3):
            beveled_cube(f"{name}_toe{side_idx}_{i}", (0.22, 0.30, 0.18),
                         loc=((i-1)*0.25, 0.55, -1.45), parent=knee_e, mat_=secondary)

    # ===== HIPS / WAIST =====
    hip_box = beveled_cube(f"{name}_hipbox", (1.4, 0.85, 0.65),
                            bevel_offset=0.08, loc=(0, 0, 2.45), parent=base, mat_=dark)
    # ===== TORSO =====
    torso_e = empty(f"{name}_torso_e", (0, 0, 3.2), parent=base)
    # Main torso (wider chest)
    beveled_cube(f"{name}_torso", (1.65, 1.0, 1.2), bevel_offset=0.10,
                 loc=(0, 0, 0), parent=torso_e, mat_=primary)
    # Chest core glow (centerpiece)
    smooth_sphere(f"{name}_core", r=0.30, loc=(0, -0.55, 0.25),
                  parent=torso_e, mat_=plasma_color, scale=(1, 0.4, 1))
    # Shoulder pauldrons (large)
    for side_idx, side in enumerate((-1, 1)):
        paul = beveled_cube(f"{name}_paul{side_idx}", (0.65, 0.85, 0.85),
                            bevel_offset=0.08,
                            loc=(side*1.05, 0, 0.30), parent=torso_e, mat_=secondary)
        paul.rotation_euler = (0, math.radians(side*8), 0)
        # Pauldron details (3 ridges)
        for i in range(3):
            cyl(f"{name}_paul_ridge{side_idx}_{i}", r=0.04, depth=0.80, segs=8,
                loc=(side*1.05, (i-1)*0.25, 0.65), parent=torso_e, mat_=M_METAL)

    # Back jetpack
    jet_e = empty(f"{name}_jet_e", (0, 0.6, 0.20), parent=torso_e)
    for side in (-1, 1):
        cyl(f"{name}_jet_thr{side}", r=0.28, depth=0.85, segs=14,
            loc=(side*0.45, 0, 0), parent=jet_e, mat_=dark)
        # Jet flame inner
        smooth_cone(f"{name}_jet_fl{side}", r1=0.22, r2=0.05, depth=0.7, segs=12,
                   loc=(side*0.45, 0, -0.65), parent=jet_e, mat_=plasma_color)
        smooth_cone(f"{name}_jet_fli{side}", r1=0.14, r2=0.02, depth=0.5, segs=10,
                   loc=(side*0.45, 0, -0.70), parent=jet_e, mat_=M_FLAME_INNER)

    # ===== HEAD / COCKPIT =====
    head_e = empty(f"{name}_head_e", (0, 0, 0.95), parent=torso_e)
    # Cockpit dome
    smooth_sphere(f"{name}_cockpit_dome", r=0.55, segs=24, rings=16,
                  loc=(0, 0, 0), parent=head_e, mat_=primary, scale=(1, 0.9, 1))
    # Visor (cockpit glass)
    beveled_cube(f"{name}_visor", (0.85, 0.10, 0.35), bevel_offset=0.04,
                 loc=(0, -0.45, 0.05), parent=head_e, mat_=M_GLASS_COCKPIT)
    # Head crest (V-shape)
    crest = beveled_cube(f"{name}_crest", (0.20, 0.25, 0.45),
                         loc=(0, -0.25, 0.45), parent=head_e, mat_=secondary)
    crest.rotation_euler = (math.radians(-25), 0, 0)
    # Head antennae (2 angled)
    for side in (-1, 1):
        ant = cyl(f"{name}_ant{side}", r=0.04, depth=0.55, segs=8,
                 loc=(side*0.30, 0.10, 0.40), parent=head_e, mat_=M_METAL)
        ant.rotation_euler = (math.radians(-25), 0, math.radians(side*20))
        # Tip light
        smooth_sphere(f"{name}_ant_tip{side}", r=0.04,
                      loc=(side*0.43, 0.30, 0.65), parent=head_e, mat_=plasma_color)
    # Side ear units
    for side in (-1, 1):
        beveled_cube(f"{name}_ear{side}", (0.15, 0.35, 0.30),
                     loc=(side*0.55, 0, 0), parent=head_e, mat_=dark)

    # ===== ARMS =====
    # Right arm with CANNON
    r_sh = empty(f"{name}_r_sh", (1.05, 0, 0.35), parent=torso_e)
    r_sh.rotation_euler = (math.radians(-20), 0, math.radians(-15))
    # Upper arm
    beveled_cube(f"{name}_r_upper", (0.50, 0.50, 1.0),
                 loc=(0, 0, -0.5), parent=r_sh, mat_=primary)
    # Elbow joint
    r_el = empty(f"{name}_r_el", (0, 0, -1.05), parent=r_sh)
    r_el.rotation_euler = (math.radians(45), 0, 0)
    smooth_sphere(f"{name}_r_elcap", r=0.30, loc=(0,0,0), parent=r_el, mat_=secondary)
    # Forearm (chunky)
    beveled_cube(f"{name}_r_fa", (0.55, 0.55, 1.0),
                 loc=(0, 0, -0.55), parent=r_el, mat_=primary)
    # CANNON (mounted on forearm, pointing forward)
    cannon_e = empty(f"{name}_cannon_e", (0, -0.30, -0.65), parent=r_el)
    cannon_e.rotation_euler = (math.radians(75), 0, 0)
    # Cannon barrel (large)
    cyl(f"{name}_cannon_brl", r=0.20, depth=1.6, segs=18,
        loc=(0, 0, 0.6), parent=cannon_e, mat_=dark)
    # Cannon outer housing
    cyl(f"{name}_cannon_h", r=0.30, depth=0.65, segs=18,
        loc=(0, 0, 0.20), parent=cannon_e, mat_=secondary)
    # Cannon muzzle ring
    cyl(f"{name}_cannon_mz", r=0.25, depth=0.08, segs=16,
        loc=(0, 0, 1.4), parent=cannon_e, mat_=M_METAL)
    # Cannon glow charge inside
    smooth_sphere(f"{name}_cannon_glow", r=0.15, loc=(0, 0, 1.35),
                  parent=cannon_e, mat_=plasma_color)

    # Left arm with PLASMA SWORD
    l_sh = empty(f"{name}_l_sh", (-1.05, 0, 0.35), parent=torso_e)
    l_sh.rotation_euler = (math.radians(-100), 0, math.radians(15))
    beveled_cube(f"{name}_l_upper", (0.50, 0.50, 1.0),
                 loc=(0, 0, -0.5), parent=l_sh, mat_=primary)
    l_el = empty(f"{name}_l_el", (0, 0, -1.05), parent=l_sh)
    l_el.rotation_euler = (math.radians(50), 0, 0)
    smooth_sphere(f"{name}_l_elcap", r=0.30, loc=(0,0,0), parent=l_el, mat_=secondary)
    beveled_cube(f"{name}_l_fa", (0.55, 0.55, 1.0),
                 loc=(0, 0, -0.55), parent=l_el, mat_=primary)
    # Hand (fist closed)
    l_hand = empty(f"{name}_l_hand", (0, 0, -1.20), parent=l_el)
    beveled_cube(f"{name}_l_hand_g", (0.50, 0.55, 0.50), bevel_offset=0.08,
                 loc=(0, 0, 0), parent=l_hand, mat_=dark)
    # PLASMA SWORD (long beam emanating from hand)
    sword_e = empty(f"{name}_sword_e", (0, 0, -0.35), parent=l_hand)
    # Hilt
    cyl(f"{name}_sword_hilt", r=0.10, depth=0.50, segs=12,
        loc=(0, 0, 0), parent=sword_e, mat_=dark)
    # Guard
    beveled_cube(f"{name}_sword_guard", (0.30, 0.30, 0.08),
                 loc=(0, 0, -0.25), parent=sword_e, mat_=M_METAL)
    # Plasma blade (long emissive)
    blade = cyl(f"{name}_sword_blade", r=0.10, depth=3.0, segs=14,
               loc=(0, 0, -1.85), parent=sword_e, mat_=plasma_color)
    # Blade glow tip
    smooth_cone(f"{name}_sword_tip", r1=0.10, r2=0.005, depth=0.30, segs=12,
                loc=(0, 0, -3.50), parent=sword_e, mat_=plasma_color)

    return {"root": base, "torso_e": torso_e, "legs_e": legs_e,
            "head_e": head_e, "l_sh": l_sh, "r_sh": r_sh,
            "sword_e": sword_e, "cannon_e": cannon_e,
            "laser_color": laser_color, "plasma_color": plasma_color}

mecha1 = make_mecha("m1", (-5, -2, 0), M_MECHA1_PRIM, M_MECHA1_SEC, M_MECHA1_DARK, M_PLASMA_BLUE, M_LASER_BLUE)
mecha1["root"].rotation_euler = (0, 0, math.radians(30))
mecha2 = make_mecha("m2", (5, 2, 0), M_MECHA2_PRIM, M_MECHA2_SEC, M_MECHA2_DARK, M_PLASMA_RED, M_LASER_RED)
mecha2["root"].rotation_euler = (0, 0, math.radians(180 - 30))

# ============ LASER BEAMS crossing (between mechas) ============
# 2 laser cylinders animated
laser1 = cyl("laser1", r=0.18, depth=12.0, segs=10, loc=(0, 0, 5), mat_=M_LASER_BLUE)
laser1.rotation_euler = (math.radians(90), 0, math.radians(-25))
laser1.location = (0, 0, 5.5)
laser2 = cyl("laser2", r=0.18, depth=12.0, segs=10, loc=(0, 0, 4.5), mat_=M_LASER_RED)
laser2.rotation_euler = (math.radians(90), 0, math.radians(25))

# ============ 30 MISSILES with TRAILS ============
missiles = []
for i in range(30):
    # Trajectory between mechas (curved spirals)
    src = (-5 if i % 2 == 0 else 5, -2 if i % 2 == 0 else 2, random.uniform(5, 8))
    tgt = (5 if i % 2 == 0 else -5, 2 if i % 2 == 0 else -2, random.uniform(3, 8))
    # Initial position somewhere along path
    t0 = i / 30.0
    mx = src[0] + (tgt[0]-src[0]) * t0
    my = src[1] + (tgt[1]-src[1]) * t0
    mz = src[2] + (tgt[2]-src[2]) * t0 + math.sin(t0 * math.pi) * 3
    m_e = empty(f"missile_e{i}", (mx, my, mz))
    # Direction
    dx = tgt[0] - src[0]; dy = tgt[1] - src[1]
    yaw = math.atan2(dy, dx)
    m_e.rotation_euler = (0, math.radians(90), yaw)
    # Body
    cyl(f"missile_body{i}", r=0.08, depth=0.60, segs=10, loc=(0,0,0),
        parent=m_e, mat_=M_MISSILE)
    # Nose cone
    smooth_cone(f"missile_nose{i}", r1=0.08, r2=0.01, depth=0.20, segs=10,
                loc=(0, 0, 0.40), parent=m_e, mat_=M_MISSILE)
    # 4 fins
    for j in range(4):
        a = (j / 4.0) * math.pi * 2
        beveled_cube(f"missile_fin{i}_{j}", (0.10, 0.02, 0.15),
                     loc=(0.10*math.cos(a), 0.10*math.sin(a), -0.25),
                     parent=m_e, mat_=M_MISSILE)
    # Trail (emissive)
    smooth_cone(f"missile_trail{i}", r1=0.10, r2=0.02, depth=0.80, segs=10,
                loc=(0, 0, -0.70), parent=m_e, mat_=M_MISSILE_TRAIL)
    missiles.append({"e": m_e, "src": src, "tgt": tgt,
                     "phase": random.uniform(0, math.pi*2),
                     "speed": random.uniform(0.8, 1.5)})

# ============ 50 SPARKS (explosions/crackling) ============
sparks = []
for i in range(50):
    # Cluster near mechas (collision points)
    if i < 20:
        # Cluster 1 between mechas at top
        cx = random.uniform(-3, 3)
        cy = random.uniform(-1, 1)
        cz = random.uniform(4, 8)
    elif i < 35:
        # At mecha 1 feet
        cx = -5 + random.uniform(-2, 2)
        cy = -2 + random.uniform(-2, 2)
        cz = random.uniform(0.5, 2)
    else:
        # At mecha 2 feet
        cx = 5 + random.uniform(-2, 2)
        cy = 2 + random.uniform(-2, 2)
        cz = random.uniform(0.5, 2)
    sk = smooth_sphere(f"spark{i}", r=random.uniform(0.06, 0.14), segs=10, rings=8,
                      loc=(cx, cy, cz), mat_=M_SPARK)
    sk["_phase"] = random.uniform(0, math.pi*2)
    sk["_speed"] = random.uniform(1.0, 3.0)
    sk["_base_x"] = cx; sk["_base_y"] = cy; sk["_base_z"] = cz
    sparks.append(sk)

# ============ 20 SMOKE BILLOWS ============
smokes = []
for i in range(20):
    a = random.uniform(0, math.pi*2)
    rad = random.uniform(3, 15)
    sx, sy = rad*math.cos(a), rad*math.sin(a)
    sz = random.uniform(2, 12)
    sm = smooth_sphere(f"smoke{i}", r=random.uniform(1.2, 2.5), segs=18, rings=12,
                      loc=(sx, sy, sz), mat_=M_SMOKE)
    sm["_phase"] = random.uniform(0, math.pi*2)
    sm["_base_x"] = sx; sm["_base_y"] = sy; sm["_base_z"] = sz
    smokes.append(sm)

# ============ 8 DRONES SUPPORT (orbit) ============
drones = []
for i in range(8):
    a = (i / 8.0) * math.pi * 2
    rad = 15
    dx, dy = rad*math.cos(a), rad*math.sin(a)
    dz = random.uniform(8, 14)
    d_e = empty(f"drone_e{i}", (dx, dy, dz))
    # Body
    smooth_sphere(f"drone_body{i}", r=0.45, segs=18, rings=12,
                  loc=(0,0,0), parent=d_e, mat_=M_DRONE, scale=(1.2, 1.2, 0.6))
    # 4 propellers
    drone_props = []
    for j, (px, py) in enumerate([(0.5,0.5), (-0.5,0.5), (-0.5,-0.5), (0.5,-0.5)]):
        # Arm
        arm = cyl(f"drone_arm{i}_{j}", r=0.04, depth=0.45, segs=8,
                 loc=(px*0.5, py*0.5, 0), parent=d_e, mat_=M_DRONE)
        arm.rotation_euler = (0, math.radians(90), math.atan2(py, px))
        # Prop housing
        cyl(f"drone_house{i}_{j}", r=0.10, depth=0.10, segs=10,
            loc=(px, py, 0.05), parent=d_e, mat_=M_DRONE)
        # Spinning prop (flat disc)
        prop_e = empty(f"drone_prop_e{i}_{j}", (px, py, 0.10), parent=d_e)
        for k in range(3):
            ang = k * math.pi * 2 / 3
            blade = beveled_cube(f"drone_pb{i}_{j}_{k}", (0.32, 0.04, 0.01),
                                 loc=(0.16*math.cos(ang), 0.16*math.sin(ang), 0),
                                 parent=prop_e, mat_=M_DRONE_PROP)
            blade.rotation_euler = (0, 0, ang)
        drone_props.append(prop_e)
    # Bottom light (red)
    smooth_sphere(f"drone_light{i}", r=0.10, loc=(0, 0, -0.20),
                  parent=d_e, mat_=M_DRONE_LIGHT)
    # Front camera lens
    smooth_sphere(f"drone_cam{i}", r=0.08, loc=(0, -0.30, 0),
                  parent=d_e, mat_=M_DRONE_LIGHT)
    drones.append({"e": d_e, "props": drone_props, "phase": a,
                   "orbit_speed": random.uniform(0.4, 0.7),
                   "base_z": dz})

# ============ 30 DEBRIS flying ============
debris = []
for i in range(30):
    dx = random.uniform(-25, 25)
    dy = random.uniform(-25, 25)
    dz = random.uniform(2, 14)
    d = beveled_cube(f"debris{i}", (random.uniform(0.15,0.4), random.uniform(0.15,0.4), random.uniform(0.15,0.4)),
                     loc=(dx, dy, dz), mat_=M_RUBBLE if random.random() < 0.6 else M_MECHA1_DARK)
    d.rotation_euler = (random.uniform(0,math.pi*2),
                        random.uniform(0,math.pi*2),
                        random.uniform(0,math.pi*2))
    d["_phase"] = random.uniform(0, math.pi*2)
    d["_base_x"] = dx; d["_base_y"] = dy; d["_base_z"] = dz
    debris.append(d)

# ============ ANIMATION ============
fps = 30; duration_s = 6; total_frames = fps * duration_s

# Mecha 1 stomp (Z bob + torso rotate + sword swing + cannon rotate)
for f in range(1, total_frames + 1, 3):
    t = (f - 1) / fps
    # Stomp pattern: alternating leg lift
    stomp1_z = abs(math.sin(t * 2.0)) * 0.4
    stomp2_z = abs(math.sin(t * 2.0 + math.pi)) * 0.4
    # Mecha 1 root z
    mecha1["root"].location.z = stomp1_z * 0.3
    mecha1["root"].keyframe_insert("location", frame=f)
    # Mecha 1 torso turn slightly
    mecha1["torso_e"].rotation_euler = (
        math.sin(t * 1.5) * math.radians(3),
        0,
        math.sin(t * 1.0) * math.radians(8),
    )
    mecha1["torso_e"].keyframe_insert("rotation_euler", frame=f)
    # Mecha 1 sword swing (large arc)
    mecha1["l_sh"].rotation_euler = (
        math.radians(-100) + math.sin(t * 2.5) * math.radians(30),
        0,
        math.radians(15) + math.sin(t * 2.5 + 0.5) * math.radians(15),
    )
    mecha1["l_sh"].keyframe_insert("rotation_euler", frame=f)
    # Mecha 1 cannon track
    mecha1["r_sh"].rotation_euler = (
        math.radians(-20) + math.sin(t * 1.8) * math.radians(10),
        0,
        math.radians(-15) + math.sin(t * 1.4) * math.radians(15),
    )
    mecha1["r_sh"].keyframe_insert("rotation_euler", frame=f)
    # Head track
    mecha1["head_e"].rotation_euler = (0, 0, math.sin(t * 1.5) * math.radians(15))
    mecha1["head_e"].keyframe_insert("rotation_euler", frame=f)

    # Mecha 2 mirror
    mecha2["root"].location.z = stomp2_z * 0.3
    mecha2["root"].keyframe_insert("location", frame=f)
    mecha2["torso_e"].rotation_euler = (
        math.sin(t * 1.5 + 0.7) * math.radians(3),
        0,
        math.sin(t * 1.0 + 0.5) * math.radians(8),
    )
    mecha2["torso_e"].keyframe_insert("rotation_euler", frame=f)
    mecha2["l_sh"].rotation_euler = (
        math.radians(-100) + math.sin(t * 2.5 + 0.8) * math.radians(30),
        0,
        math.radians(15) + math.sin(t * 2.5 + 1.0) * math.radians(15),
    )
    mecha2["l_sh"].keyframe_insert("rotation_euler", frame=f)
    mecha2["r_sh"].rotation_euler = (
        math.radians(-20) + math.sin(t * 1.8 + 0.5) * math.radians(10),
        0,
        math.radians(-15) + math.sin(t * 1.4 + 0.7) * math.radians(15),
    )
    mecha2["r_sh"].keyframe_insert("rotation_euler", frame=f)
    mecha2["head_e"].rotation_euler = (0, 0, math.sin(t * 1.5 + 1.0) * math.radians(15))
    mecha2["head_e"].keyframe_insert("rotation_euler", frame=f)

# Laser beams flicker
for f in range(1, total_frames + 1, 2):
    t = (f - 1) / fps
    s1 = 1 + math.sin(t * 8.0) * 0.30
    laser1.scale = (s1, 1, s1)
    laser1.keyframe_insert("scale", frame=f)
    s2 = 1 + math.sin(t * 9.0 + 0.3) * 0.30
    laser2.scale = (s2, 1, s2)
    laser2.keyframe_insert("scale", frame=f)

# Missiles spiral trajectory
for m in missiles:
    src = m["src"]; tgt = m["tgt"]; phase = m["phase"]; speed = m["speed"]
    for f in range(1, total_frames + 1, 3):
        t = (f - 1) / fps
        loop_t = ((t * speed) % 2.0) / 2.0
        x = src[0] + (tgt[0]-src[0]) * loop_t
        y = src[1] + (tgt[1]-src[1]) * loop_t
        z = src[2] + (tgt[2]-src[2]) * loop_t + math.sin(loop_t * math.pi) * 3
        # Spiral perpendicular
        x += math.cos(t * 3.0 + phase) * 0.5
        y += math.sin(t * 3.0 + phase) * 0.5
        m["e"].location = (x, y, z)
        m["e"].keyframe_insert("location", frame=f)

# Sparks crackle (Z explosion + scale pulse + scatter)
for sk in sparks:
    if "_phase" not in sk.keys():
        continue
    phase = sk["_phase"]
    speed = sk["_speed"]
    bx, by, bz = sk["_base_x"], sk["_base_y"], sk["_base_z"]
    for f in range(1, total_frames + 1, 3):
        t = (f - 1) / fps
        cycle = (t * speed) % 1.5
        x = bx + math.cos(t * 5.0 + phase) * 0.8 * cycle
        y = by + math.sin(t * 5.0 + phase) * 0.8 * cycle
        z = bz + cycle * 1.0
        s = max(0.1, 1 - cycle * 0.7) * (1 + math.sin(t * 8.0 + phase) * 0.3)
        sk.location = (x, y, z)
        sk.scale = (s, s, s)
        sk.keyframe_insert("location", frame=f)
        sk.keyframe_insert("scale", frame=f)

# Smoke billow (drift + scale grow)
for sm in smokes:
    if "_phase" not in sm.keys():
        continue
    phase = sm["_phase"]
    bx, by, bz = sm["_base_x"], sm["_base_y"], sm["_base_z"]
    for f in range(1, total_frames + 1, 6):
        t = (f - 1) / fps
        x = bx + math.sin(t * 0.4 + phase) * 0.6
        y = by + math.cos(t * 0.35 + phase) * 0.6
        z = bz + (t * 0.3) % 4.0
        s = 1 + math.sin(t * 0.8 + phase) * 0.20
        sm.location = (x, y, z)
        sm.scale = (s, s, s)
        sm.keyframe_insert("location", frame=f)
        sm.keyframe_insert("scale", frame=f)

# Drones orbit + propellers spin
for d in drones:
    phase = d["phase"]
    speed = d["orbit_speed"]
    base_z = d["base_z"]
    for f in range(1, total_frames + 1, 3):
        t = (f - 1) / fps
        a = phase + speed * t
        x = 15 * math.cos(a); y = 15 * math.sin(a)
        z = base_z + math.sin(t * 1.5 + phase) * 0.5
        d["e"].location = (x, y, z)
        d["e"].rotation_euler = (0, 0, a + math.pi/2)
        d["e"].keyframe_insert("location", frame=f)
        d["e"].keyframe_insert("rotation_euler", frame=f)
        # Spin props
        for p in d["props"]:
            p.rotation_euler = (0, 0, t * 30)
            p.keyframe_insert("rotation_euler", frame=f)

# Ground flames pulse
for outer, inner in ground_flames:
    p_o = outer["_phase"]; p_i = inner["_phase"]
    for f in range(1, total_frames + 1, 3):
        t = (f - 1) / fps
        s_o = 1 + math.sin(t * 6.0 + p_o) * 0.25
        outer.scale = (s_o, s_o, s_o); outer.keyframe_insert("scale", frame=f)
        s_i = 1 + math.sin(t * 8.0 + p_i) * 0.30
        inner.scale = (s_i, s_i, s_i); inner.keyframe_insert("scale", frame=f)

# Debris fall + spin
for d in debris:
    phase = d["_phase"]
    bx, by, bz = d["_base_x"], d["_base_y"], d["_base_z"]
    for f in range(1, total_frames + 1, 4):
        t = (f - 1) / fps
        z = bz - (t * 1.0) % 8.0
        x = bx + math.sin(t * 0.5 + phase) * 0.3
        y = by + math.cos(t * 0.5 + phase) * 0.3
        d.location = (x, y, max(0.1, z))
        d.rotation_euler = (phase + t * 2.0, phase + t * 1.5, phase + t * 2.5)
        d.keyframe_insert("location", frame=f)
        d.keyframe_insert("rotation_euler", frame=f)

# Clouds drift
for ci, cl in enumerate(clouds):
    bx, by = cl.location.x, cl.location.y
    phase = ci * 0.7
    for f in range(1, total_frames + 1, 10):
        t = (f - 1) / fps
        cl.location = (bx + math.sin(t * 0.3 + phase) * 0.6,
                       by + math.cos(t * 0.25 + phase) * 0.5,
                       cl.location.z)
        cl.keyframe_insert("location", frame=f)

# ============ EXPORT ============
out_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "public", "_pbr_test")
out_dir = os.path.normpath(out_dir)
os.makedirs(out_dir, exist_ok=True)
out_glb = os.path.join(out_dir, "pbr_mecha_battle_proc.glb")

bpy.ops.object.select_all(action='SELECT')
bpy.ops.export_scene.gltf(
    filepath=out_glb, export_format='GLB',
    export_animations=True, export_apply=False, export_yup=True, use_selection=False,
)
size_mb = os.path.getsize(out_glb) / (1024 * 1024)
print(f"[proc_giant_robot_mecha_battle] DONE → {out_glb} ({size_mb:.2f} MB)")
print("[proc_giant_robot_mecha_battle] 2 mechas full anatomy + cockpit + cannon + plasma sword + jetpack + 8 buildings broken + 30 missiles spiral + 50 sparks + 20 smoke + 8 drones orbit + 30 debris + ground flames + lasers")
