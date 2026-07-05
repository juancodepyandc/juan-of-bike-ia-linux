"""
proc_rainforest_thunderstorm.py — 209e procédural AuroraIA (73e qualité)
Forêt tropicale orage : ONE ground + 500 streaks pluie tombant + lightning + toucans + jaguar + perroquets + grenouilles
FIXES APPLIQUÉS : 1 SEUL ground + RAIN particules thématiques obligatoires
"""
import bpy, bmesh, math, random, os

random.seed(0x4A1A209)

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
M_SKY_STORM = mat("sky", (0.10, 0.12, 0.18, 1.0), 0.0, 0.85, emission=(0.15,0.18,0.25), emission_strength=0.6)
M_LIGHTNING = mat("lightning", (0.95, 0.95, 1.0, 1.0), 0.0, 0.05, emission=(1.0,0.98,1.0), emission_strength=30.0)
M_CLOUD_DARK = mat("cloud", (0.15, 0.15, 0.22, 1.0), 0.0, 0.85, emission=(0.20,0.20,0.28), emission_strength=0.5, alpha=0.85)
M_RAIN = mat("rain", (0.55, 0.75, 0.95, 1.0), 0.0, 0.10, emission=(0.65,0.85,1.0), emission_strength=3.0, alpha=0.7)
M_SPLASH = mat("splash", (0.85, 0.95, 1.0, 1.0), 0.0, 0.20, emission=(0.85,0.95,1.0), emission_strength=4.0)
M_SPARK_LIGHT = mat("spark", (1.0, 0.95, 0.65, 1.0), 0.0, 0.05, emission=(1.0,0.98,0.75), emission_strength=18.0)

# === ONE clean ground (jungle wet earth) ===
M_GROUND = mat("ground", (0.18, 0.15, 0.10, 1.0), 0.2, 0.85)
M_ROCK = mat("rock", (0.25, 0.22, 0.20, 1.0), 0.0, 0.85)
M_MUSHROOM_RED = mat("mush_r", (0.95, 0.18, 0.18, 1.0), 0.0, 0.50, emission=(0.95,0.20,0.20), emission_strength=2.0)
M_MUSHROOM_DOT = mat("mush_dot", (1.0, 0.95, 0.85, 1.0), 0.0, 0.45, emission=(0.95,0.92,0.85), emission_strength=0.5)
M_MUSHROOM_GLOW = mat("mush_g", (0.30, 1.0, 0.60, 1.0), 0.0, 0.30, emission=(0.40,1.0,0.65), emission_strength=4.0)

# Trees
M_TRUNK = mat("trunk", (0.25, 0.18, 0.12, 1.0), 0.0, 0.85, emission=(0.20,0.15,0.10), emission_strength=0.2)
M_LEAF_DARK = mat("leaf_d", (0.12, 0.30, 0.15, 1.0), 0.0, 0.65, emission=(0.10,0.25,0.12), emission_strength=0.3)
M_LEAF = mat("leaf", (0.18, 0.45, 0.20, 1.0), 0.0, 0.60, emission=(0.15,0.40,0.18), emission_strength=0.4)
M_LIANA = mat("liana", (0.30, 0.45, 0.18, 1.0), 0.0, 0.75, emission=(0.25,0.40,0.15), emission_strength=0.3)

# Animals
M_JAGUAR = mat("jaguar", (0.85, 0.65, 0.30, 1.0), 0.0, 0.65, emission=(0.78,0.58,0.28), emission_strength=0.4)
M_JAGUAR_SPOT = mat("jaguar_s", (0.15, 0.10, 0.06, 1.0), 0.0, 0.80)
M_JAGUAR_EYE = mat("jaguar_eye", (1.0, 0.85, 0.30, 1.0), 0.0, 0.15, emission=(1.0,0.85,0.30), emission_strength=8.0)

M_TOUCAN_BODY = mat("toucan_b", (0.08, 0.06, 0.06, 1.0), 0.0, 0.65, emission=(0.10,0.08,0.08), emission_strength=0.4)
M_TOUCAN_BELLY = mat("toucan_be", (1.0, 0.95, 0.92, 1.0), 0.0, 0.55, emission=(0.92,0.88,0.85), emission_strength=0.5)
M_TOUCAN_BEAK_TOP = mat("toucan_bk", (1.0, 0.65, 0.10, 1.0), 0.0, 0.40, emission=(1.0,0.65,0.10), emission_strength=1.2)
M_TOUCAN_BEAK_BOT = mat("toucan_bk2", (0.85, 0.20, 0.10, 1.0), 0.0, 0.45, emission=(0.85,0.20,0.10), emission_strength=1.0)

M_PARROT_RED = mat("par_r", (0.95, 0.15, 0.15, 1.0), 0.0, 0.50, emission=(0.95,0.18,0.18), emission_strength=1.5)
M_PARROT_BLUE = mat("par_b", (0.20, 0.45, 0.95, 1.0), 0.0, 0.50, emission=(0.20,0.45,0.95), emission_strength=1.5)
M_PARROT_YELLOW = mat("par_y", (1.0, 0.85, 0.20, 1.0), 0.0, 0.50, emission=(1.0,0.85,0.20), emission_strength=1.8)
M_PARROT_GREEN = mat("par_g", (0.20, 0.85, 0.30, 1.0), 0.0, 0.50, emission=(0.20,0.85,0.30), emission_strength=1.6)

M_FROG = mat("frog", (0.30, 0.95, 0.40, 1.0), 0.0, 0.35, emission=(0.35,1.0,0.45), emission_strength=2.0)
M_FROG_BELLY = mat("frog_b", (0.95, 0.95, 0.85, 1.0), 0.0, 0.40, emission=(0.85,0.85,0.78), emission_strength=0.5)
M_FROG_EYE = mat("frog_eye", (1.0, 0.85, 0.20, 1.0), 0.0, 0.15, emission=(1.0,0.85,0.20), emission_strength=6.0)
M_FROG_RED = mat("frog_r", (0.95, 0.20, 0.30, 1.0), 0.0, 0.40, emission=(0.95,0.25,0.35), emission_strength=2.5)
M_FROG_BLUE = mat("frog_blue", (0.25, 0.40, 0.85, 1.0), 0.0, 0.40, emission=(0.30,0.45,0.95), emission_strength=2.5)

# ============ SKY + STORM CLOUDS ============
sky = smooth_sphere("sky", r=95, segs=32, rings=20, loc=(0,0,0), mat_=M_SKY_STORM, scale=(1,1,0.60))
sky.scale = (1,1,0.60)

# 10 storm clouds dark drift
clouds = []
for i in range(10):
    a = (i / 10.0) * math.pi * 2
    rad = random.uniform(22, 34)
    cx, cy = rad*math.cos(a), rad*math.sin(a)
    cz = random.uniform(18, 28)
    c_e = empty(f"cloud_e{i}", (cx, cy, cz))
    for j in range(5):
        smooth_sphere(f"cloud{i}_{j}", r=random.uniform(2.5, 4.0),
                      loc=(random.uniform(-3,3), random.uniform(-2,2), random.uniform(-0.5,0.5)),
                      parent=c_e, mat_=M_CLOUD_DARK)
    c_e["_phase"] = random.uniform(0, math.pi*2)
    clouds.append(c_e)

# 8 LIGHTNING BOLTS zigzag (flash)
lightning_bolts = []
for li in range(8):
    base_x = -28 + li * 8
    base_y = random.uniform(-5, 15)
    bolt_e = empty(f"bolt_e{li}", (base_x, base_y, 30))
    for i in range(6):
        seg = beveled_cube(f"bolt{li}_{i}", (0.20, 0.10, 1.6), bevel_offset=0.02,
                          loc=((i % 2) * 1.0 - 0.5, 0, -i * 1.4),
                          parent=bolt_e, mat_=M_LIGHTNING)
        seg.rotation_euler = (0, 0, math.radians(((i % 2) * 35 - 17)))
    bolt_e["_phase"] = li * 1.0
    lightning_bolts.append(bolt_e)

# ============ ONE CLEAN JUNGLE GROUND (no stacked layers) ============
ground = beveled_cube("ground", (80, 80, 0.5), bevel_offset=0.08, loc=(0, 0, -0.25), mat_=M_GROUND)

# Organic ground bumps (3D scattered, NOT flat sheets)
for i in range(35):
    a = random.uniform(0, math.pi*2)
    rad = random.uniform(5, 32)
    smooth_sphere(f"bump{i}", r=random.uniform(0.5, 1.5),
                  loc=(rad*math.cos(a), rad*math.sin(a), 0.0),
                  mat_=M_GROUND, scale=(random.uniform(1, 1.4),
                                         random.uniform(1, 1.4),
                                         random.uniform(0.20, 0.45)))

# Rocks scattered (12)
for i in range(12):
    a = random.uniform(0, math.pi*2)
    rad = random.uniform(8, 28)
    smooth_sphere(f"rock{i}", r=random.uniform(0.5, 1.2),
                  loc=(rad*math.cos(a), rad*math.sin(a), 0.3),
                  mat_=M_ROCK,
                  scale=(random.uniform(0.8,1.3), random.uniform(0.8,1.3),
                         random.uniform(0.6,0.9))).rotation_euler = (random.uniform(-0.2, 0.2),
                                                                       random.uniform(-0.2, 0.2),
                                                                       random.uniform(0, math.pi*2))

# Glowing mushrooms (forest floor signature - 30)
mushrooms = []
for i in range(30):
    a = random.uniform(0, math.pi*2)
    rad = random.uniform(4, 25)
    mx = rad*math.cos(a); my = rad*math.sin(a)
    m_e = empty(f"mush{i}", (mx, my, 0))
    # Stem
    h = random.uniform(0.20, 0.45)
    cyl(f"mush_stem{i}", r=random.uniform(0.04, 0.08), depth=h, segs=10,
        loc=(0, 0, h/2), parent=m_e, mat_=M_MUSHROOM_DOT)
    # Cap (mix red+white agaric AND glow green)
    is_glow = random.random() < 0.4
    cap_mat = M_MUSHROOM_GLOW if is_glow else M_MUSHROOM_RED
    cap_r = random.uniform(0.12, 0.22)
    smooth_sphere(f"mush_cap{i}", r=cap_r, segs=14, rings=10,
                  loc=(0, 0, h+0.04), parent=m_e, mat_=cap_mat, scale=(1, 1, 0.5))
    # White dots on red
    if not is_glow:
        for j in range(4):
            da = (j / 4.0) * math.pi * 2
            smooth_sphere(f"mush_dot{i}_{j}", r=cap_r*0.18,
                          loc=(cap_r*0.5*math.cos(da), cap_r*0.5*math.sin(da), h+0.08),
                          parent=m_e, mat_=M_MUSHROOM_DOT)
    m_e["_phase"] = random.uniform(0, math.pi*2)
    mushrooms.append(m_e)

# ============ 12 TROPICAL TREES TALL ============
trees = []
def make_tree(name, loc, height=12, scale=1.0):
    base = empty(name, loc)
    # Trunk 6-segs tapered
    for i in range(6):
        r1 = (0.40 - i*0.04) * scale
        r2 = (0.36 - i*0.04) * scale
        h = height / 6
        seg = smooth_cone(f"{name}_t{i}", r1=r1, r2=r2, depth=h, segs=14,
                          loc=(0, 0, (i+0.5)*h), parent=base, mat_=M_TRUNK)
        seg.rotation_euler = (math.radians(random.uniform(-3,3)),
                              math.radians(random.uniform(-3,3)), 0)
    # Canopy puffs (10)
    top_z = height
    for j in range(10):
        a = (j / 10.0) * math.pi * 2
        rad = random.uniform(1.5, 2.8) * scale
        smooth_sphere(f"{name}_can{j}", r=random.uniform(1.0, 1.5) * scale,
                      loc=(rad*math.cos(a), rad*math.sin(a),
                           top_z + random.uniform(-0.4, 1.0)),
                      parent=base,
                      mat_=M_LEAF_DARK if random.random() < 0.4 else M_LEAF)
    # 4 large leaves visible
    for j in range(4):
        a = (j / 4.0) * math.pi * 2
        leaf = beveled_cube(f"{name}_leaf{j}", (0.10*scale, 1.5*scale, 0.05*scale),
                            bevel_offset=0.02,
                            loc=(1.8*scale*math.cos(a), 1.8*scale*math.sin(a),
                                 top_z + 0.5), parent=base, mat_=M_LEAF)
        leaf.rotation_euler = (math.radians(-30), 0, a)
    base["_phase"] = random.uniform(0, math.pi*2)
    return base

tree_positions = [(-12, 6, 0, 12, 1.0), (10, 8, 0, 14, 1.1),
                   (-15, -8, 0, 11, 0.95), (13, -10, 0, 13, 1.05),
                   (-20, 2, 0, 10, 0.9), (18, 4, 0, 12, 1.0),
                   (-8, 18, 0, 11, 0.95), (8, -18, 0, 12, 1.0),
                   (-18, 16, 0, 10, 0.9), (18, -16, 0, 11, 1.0),
                   (-5, -15, 0, 12, 1.0), (5, 15, 0, 11, 0.95)]
for i, (tx, ty, tz, h, sc) in enumerate(tree_positions):
    t = make_tree(f"tree{i}", (tx, ty, tz), height=h, scale=sc)
    trees.append(t)

# ============ LIANAS hanging from canopy (20) ============
lianas = []
for i in range(20):
    a = random.uniform(0, math.pi*2)
    rad = random.uniform(6, 22)
    lx = rad*math.cos(a); ly = rad*math.sin(a)
    l_e = empty(f"liana{i}", (lx, ly, 8))
    # 5 segments hanging down + curving
    for s in range(5):
        seg = cyl(f"liana_s{i}_{s}", r=0.04, depth=1.0, segs=10,
                 loc=(math.sin(s*0.3)*0.20, 0, -s*0.85), parent=l_e, mat_=M_LIANA)
        seg.rotation_euler = (0, math.sin(s*0.5)*0.3, 0)
    # Leaves at end
    smooth_sphere(f"liana_l{i}", r=0.25, loc=(0, 0, -4.3),
                  parent=l_e, mat_=M_LEAF)
    l_e["_phase"] = random.uniform(0, math.pi*2)
    lianas.append(l_e)

# ============ 4 JAGUARS prowl (signature jungle predator) ============
def make_jaguar(name, loc, facing=0):
    base = empty(name, loc)
    base.rotation_euler = (0, 0, facing)
    # Body
    smooth_sphere(f"{name}_body", r=0.40, segs=22, rings=14, loc=(0, 0, 0.85),
                  parent=base, mat_=M_JAGUAR, scale=(2.2, 1.0, 1.0))
    # Belly lighter
    smooth_sphere(f"{name}_belly", r=0.36, loc=(0, 0, 0.70),
                  parent=base, mat_=mat(f"{name}_b", (0.92,0.78,0.55,1), 0, 0.65), scale=(1.9, 0.9, 0.55))
    # 4 legs
    for x_idx, x in enumerate((-1, 1)):
        for y_idx, y in enumerate((-1, 1)):
            cyl(f"{name}_leg{x_idx}{y_idx}", r=0.08, depth=0.55, segs=10,
                loc=(x*0.40, y*0.25, 0.27), parent=base, mat_=M_JAGUAR)
            # Paw
            cyl(f"{name}_paw{x_idx}{y_idx}", r=0.10, depth=0.07, segs=10,
                loc=(x*0.40, y*0.25, 0.04), parent=base, mat_=M_JAGUAR)
            # 3 claws
            for c in range(3):
                smooth_cone(f"{name}_claw{x_idx}{y_idx}_{c}", r1=0.015, r2=0.005, depth=0.05, segs=6,
                            loc=(x*0.40 + (c-1)*0.03, y*0.25 + 0.10, 0.04),
                            parent=base, mat_=mat(f"jc{name[-1]}_{x_idx}_{y_idx}_{c}", (0.95,0.92,0.85,1), 0.2, 0.4)).rotation_euler = (math.radians(60), 0, 0)
    # Spots (10 rosettes)
    for si in range(10):
        sx = random.uniform(-0.85, 0.85)
        sy = random.uniform(-0.30, 0.30)
        sz = random.uniform(0.85, 1.05)
        smooth_sphere(f"{name}_spot{si}", r=random.uniform(0.05, 0.08),
                      loc=(sx, sy, sz), parent=base, mat_=M_JAGUAR_SPOT, scale=(1, 1, 0.5))
    # Tail (long)
    tail_e = empty(f"{name}_tail_e", (-0.95, 0, 0.85), parent=base)
    for ti in range(5):
        cyl(f"{name}_tail{ti}", r=0.05 - ti*0.005, depth=0.18, segs=10,
            loc=(-ti*0.12, math.sin(ti*0.6)*0.10, math.cos(ti*0.6)*0.05),
            parent=tail_e, mat_=M_JAGUAR)
    # Head
    head_e = empty(f"{name}_head_e", (1.0, 0, 0.95), parent=base)
    smooth_sphere(f"{name}_h", r=0.22, segs=20, rings=14, loc=(0, 0, 0),
                  parent=head_e, mat_=M_JAGUAR, scale=(1.2, 0.95, 0.95))
    # Snout
    smooth_sphere(f"{name}_snout", r=0.13, loc=(0.18, 0, -0.08),
                  parent=head_e, mat_=mat(f"{name}_s", (0.85,0.65,0.40,1), 0, 0.6))
    # Nose
    smooth_sphere(f"{name}_nose", r=0.04, loc=(0.28, 0, -0.05),
                  parent=head_e, mat_=mat(f"{name}_no", (0.15,0.10,0.08,1), 0, 0.5))
    # 2 EYES YELLOW émissifs (signature predator)
    for side in (-1, 1):
        smooth_sphere(f"{name}_eye{side}", r=0.05, loc=(side*0.10, 0.12, 0.05),
                      parent=head_e, mat_=M_JAGUAR_EYE)
        # Slit pupil
        beveled_cube(f"{name}_pup{side}", (0.012, 0.04, 0.03), loc=(side*0.10, 0.16, 0.05),
                     parent=head_e, mat_=mat(f"jp{name[-1]}_{side}", (0.05,0.05,0.05,1), 0, 0.5))
    # 2 round ears
    for side in (-1, 1):
        smooth_sphere(f"{name}_ear{side}", r=0.08, loc=(side*0.13, 0.02, 0.20),
                      parent=head_e, mat_=M_JAGUAR, scale=(0.9, 0.7, 1.0))
    # Whiskers
    for side in (-1, 1):
        for j in range(3):
            beveled_cube(f"{name}_wh{side}_{j}", (0.10, 0.005, 0.005),
                         loc=(side*0.15, 0.12, -0.05 + (j-1)*0.025),
                         parent=head_e, mat_=mat(f"jw{name[-1]}_{side}_{j}", (0.95,0.92,0.85,1), 0, 0.4))
    return {"root": base, "head_e": head_e, "tail": tail_e}

jaguars = []
jag_pos = [(-7, -10, 0, math.radians(60)),
           (5, -12, 0, math.radians(-30)),
           (-9, 12, 0, math.radians(-120)),
           (11, 14, 0, math.radians(180))]
for i, (jx, jy, jz, fac) in enumerate(jag_pos):
    j = make_jaguar(f"jag{i}", (jx, jy, jz), facing=fac)
    jaguars.append(j)

# ============ 3 TOUCANS (perched on branches) ============
toucans = []
for i in range(3):
    tx = (-10 + i*10)
    ty = (-3 + i*6)
    tz = 9 + i*1.5
    t_e = empty(f"toucan{i}", (tx, ty, tz))
    t_e.rotation_euler = (0, 0, random.uniform(-math.pi, math.pi))
    # Body (chubby black)
    smooth_sphere(f"toucan_body{i}", r=0.30, segs=20, rings=14, loc=(0, 0, 0),
                  parent=t_e, mat_=M_TOUCAN_BODY, scale=(1.2, 1.0, 1.4))
    # White belly/chest patch (signature)
    smooth_sphere(f"toucan_belly{i}", r=0.22, loc=(0, -0.15, -0.05),
                  parent=t_e, mat_=M_TOUCAN_BELLY, scale=(1, 0.5, 1.3))
    # Head
    head_e = empty(f"toucan_head_e{i}", (0, -0.10, 0.40), parent=t_e)
    smooth_sphere(f"toucan_h{i}", r=0.20, segs=18, rings=12, loc=(0, 0, 0),
                  parent=head_e, mat_=M_TOUCAN_BODY)
    # MASSIVE BEAK (signature toucan - huge orange + red tip)
    # Top mandible (curved, large)
    beak_top_e = empty(f"toucan_bk_top_e{i}", (0, -0.18, 0), parent=head_e)
    beak_top_e.rotation_euler = (math.radians(85), 0, 0)
    for j in range(3):
        seg = smooth_cone(f"toucan_bk_top{i}_{j}", r1=0.13 - j*0.03, r2=0.10 - j*0.03,
                         depth=0.30, segs=12,
                         loc=(0, 0, j*0.30 + 0.15), parent=beak_top_e, mat_=M_TOUCAN_BEAK_TOP)
        seg.rotation_euler = (math.radians(-j*6), 0, 0)
    # Beak tip darker (red)
    smooth_cone(f"toucan_bk_tip{i}", r1=0.08, r2=0.005, depth=0.15, segs=10,
                loc=(0, 0, 1.0), parent=beak_top_e, mat_=M_TOUCAN_BEAK_BOT)
    # Bottom mandible
    beak_bot_e = empty(f"toucan_bk_bot_e{i}", (0, -0.18, -0.10), parent=head_e)
    beak_bot_e.rotation_euler = (math.radians(95), 0, 0)
    for j in range(3):
        seg = smooth_cone(f"toucan_bk_bot{i}_{j}", r1=0.11 - j*0.025, r2=0.08 - j*0.025,
                         depth=0.28, segs=12,
                         loc=(0, 0, j*0.28 + 0.14), parent=beak_bot_e, mat_=M_TOUCAN_BEAK_TOP)
    # Eyes (small black)
    for side in (-1, 1):
        smooth_sphere(f"toucan_eye{i}_{side}", r=0.04, loc=(side*0.08, -0.13, 0.08),
                      parent=head_e, mat_=mat(f"te{i}_{side}", (0.05,0.05,0.05,1), 0, 0.4))
        # Eye ring (signature toucan colored)
        cyl(f"toucan_eye_ring{i}_{side}", r=0.06, depth=0.02, segs=14,
            loc=(side*0.08, -0.16, 0.08), parent=head_e, mat_=M_TOUCAN_BEAK_TOP).rotation_euler = (math.radians(90), 0, 0)
    # Wings folded
    for side in (-1, 1):
        beveled_cube(f"toucan_w{i}_{side}", (0.10, 0.18, 0.30), bevel_offset=0.03,
                     loc=(side*0.22, 0, -0.05), parent=t_e, mat_=M_TOUCAN_BODY)
    # Tail short
    beveled_cube(f"toucan_tail{i}", (0.10, 0.04, 0.20), loc=(0, 0.18, -0.10),
                 parent=t_e, mat_=M_TOUCAN_BODY)
    # 2 feet (yellow-orange perched on branch)
    for side in (-1, 1):
        cyl(f"toucan_foot{i}_{side}", r=0.03, depth=0.10, segs=8,
            loc=(side*0.06, 0, -0.32), parent=t_e, mat_=M_TOUCAN_BEAK_TOP)
    toucans.append({"e": t_e, "beak_top": beak_top_e, "beak_bot": beak_bot_e,
                    "head": head_e, "phase": random.uniform(0, math.pi*2)})

# ============ 5 PARROTS ARAS (colorful) ============
parrots = []
parrot_colors = [(M_PARROT_RED, M_PARROT_YELLOW),
                 (M_PARROT_BLUE, M_PARROT_YELLOW),
                 (M_PARROT_GREEN, M_PARROT_BLUE),
                 (M_PARROT_RED, M_PARROT_BLUE),
                 (M_PARROT_YELLOW, M_PARROT_GREEN)]
for i in range(5):
    a = (i / 5.0) * math.pi * 2
    rad = 14
    px = math.cos(a) * rad
    py = math.sin(a) * rad
    pz = 8 + random.uniform(0, 4)
    p_e = empty(f"parrot{i}", (px, py, pz))
    p_e.rotation_euler = (0, 0, a + math.pi/2)
    main_color, accent_color = parrot_colors[i]
    # Body
    smooth_sphere(f"parrot_body{i}", r=0.25, segs=18, rings=12, loc=(0, 0, 0),
                  parent=p_e, mat_=main_color, scale=(1.5, 1.0, 1.2))
    # Wings (open spread - flying)
    wings = []
    for side_idx, side in enumerate((-1, 1)):
        w_e = empty(f"parrot_w{i}_{side_idx}", (0, side*0.20, 0), parent=p_e)
        # Inner wing
        beveled_cube(f"parrot_w_in{i}_{side_idx}", (0.50, 0.55, 0.05), bevel_offset=0.02,
                     loc=(0, side*0.30, 0), parent=w_e, mat_=main_color)
        # Outer feathers (4 tips with accent color)
        for fi in range(4):
            beveled_cube(f"parrot_feat{i}_{side_idx}_{fi}", (0.10, 0.30, 0.03),
                         loc=(0.16 - fi*0.10, side*0.55, 0), parent=w_e, mat_=accent_color)
        wings.append((w_e, side))
    # Tail (long colored - signature ara)
    tail_e = empty(f"parrot_tail_e{i}", (-0.30, 0, 0), parent=p_e)
    for ti in range(3):
        beveled_cube(f"parrot_tail{i}_{ti}", (0.06, 0.40 - ti*0.05, 0.04),
                     loc=(-0.10 - ti*0.05, 0, 0),
                     parent=tail_e, mat_=accent_color if ti%2==0 else main_color)
    # Head
    head_e = empty(f"parrot_head_e{i}", (0.32, 0, 0.05), parent=p_e)
    smooth_sphere(f"parrot_h{i}", r=0.13, segs=18, rings=12, loc=(0, 0, 0),
                  parent=head_e, mat_=main_color)
    # Curved beak (hooked, signature parrot)
    smooth_cone(f"parrot_beak_top{i}", r1=0.05, r2=0.01, depth=0.13, segs=10,
                loc=(0.12, 0, -0.02), parent=head_e, mat_=mat(f"pb{i}", (0.20,0.15,0.10,1), 0.3, 0.45)).rotation_euler = (math.radians(70), 0, 0)
    # Eye
    smooth_sphere(f"parrot_eye{i}", r=0.025, loc=(0.08, -0.08, 0.03),
                  parent=head_e, mat_=mat(f"pe{i}", (0.95,0.92,0.85,1), 0, 0.3))
    smooth_sphere(f"parrot_pup{i}", r=0.012, loc=(0.10, -0.10, 0.03),
                  parent=head_e, mat_=mat(f"pp{i}", (0.05,0.05,0.05,1), 0, 0.5))
    parrots.append({"e": p_e, "wings": wings, "phase": random.uniform(0, math.pi*2),
                    "orbit_rad": rad, "orbit_speed": random.uniform(0.5, 0.8),
                    "orbit_phase": a, "base_z": pz})

# ============ 5 TREE FROGS (colorful, signature jungle) ============
frogs = []
frog_colors = [M_FROG, M_FROG_RED, M_FROG_BLUE, M_FROG, M_FROG_RED]
for i in range(5):
    a = (i / 5.0) * math.pi * 2 + 0.3
    rad = random.uniform(3, 10)
    fx = math.cos(a) * rad
    fy = math.sin(a) * rad
    fz = random.uniform(0.5, 4)  # different heights (on leaves/ground)
    f_e = empty(f"frog{i}", (fx, fy, fz))
    f_e.rotation_euler = (0, 0, random.uniform(-math.pi, math.pi))
    color = frog_colors[i]
    # Body (rounded)
    smooth_sphere(f"frog_body{i}", r=0.15, segs=18, rings=12, loc=(0, 0, 0.10),
                  parent=f_e, mat_=color, scale=(1.2, 1.0, 0.85))
    # White belly
    smooth_sphere(f"frog_belly{i}", r=0.13, loc=(0, 0, 0.05),
                  parent=f_e, mat_=M_FROG_BELLY, scale=(1.0, 0.9, 0.5))
    # 2 BULGING EYES (signature tree frog)
    for side in (-1, 1):
        # Eye stalk
        smooth_sphere(f"frog_es{i}_{side}", r=0.06, loc=(side*0.08, -0.06, 0.22),
                      parent=f_e, mat_=color)
        # Eye yellow
        smooth_sphere(f"frog_eye{i}_{side}", r=0.05, loc=(side*0.08, -0.10, 0.22),
                      parent=f_e, mat_=M_FROG_EYE)
        # Slit pupil vertical
        beveled_cube(f"frog_pup{i}_{side}", (0.012, 0.02, 0.04), loc=(side*0.08, -0.14, 0.22),
                     parent=f_e, mat_=mat(f"fp{i}_{side}", (0.05,0.05,0.05,1), 0, 0.5))
    # 4 legs (long for tree frog)
    for x_idx, x in enumerate((-1, 1)):
        for y_idx, y in enumerate((-1, 1)):
            # Thigh angled
            leg = cyl(f"frog_leg{i}_{x_idx}{y_idx}", r=0.025, depth=0.15, segs=8,
                     loc=(x*0.12, y*0.08, 0.05), parent=f_e, mat_=color)
            leg.rotation_euler = (0, math.radians(x*30), 0)
            # Toe pads (3 each)
            for c in range(3):
                smooth_sphere(f"frog_toe{i}_{x_idx}{y_idx}_{c}", r=0.025,
                              loc=(x*(0.20 + c*0.01), y*0.10, 0.0),
                              parent=f_e, mat_=color)
    frogs.append({"e": f_e, "phase": random.uniform(0, math.pi*2),
                  "base_z": fz})

# ============================================================
# ⭐ 500 RAIN STREAKS qui TOMBENT (PARTICULE THÉMATIQUE OBLIGATOIRE - storm scene)
# ============================================================
rain_streaks = []
for i in range(500):
    rx = random.uniform(-35, 35)
    ry = random.uniform(-35, 35)
    rz = random.uniform(2, 28)
    # Rain streak = vertical cylinder tilted slightly
    streak = cyl(f"rain{i}", r=0.018, depth=random.uniform(0.6, 1.3), segs=6,
                loc=(rx, ry, rz), mat_=M_RAIN)
    streak.rotation_euler = (math.radians(15), 0, 0)  # tilted angle (signature rain)
    streak["_phase"] = random.uniform(0, math.pi*2)
    streak["_base_x"] = rx; streak["_base_y"] = ry; streak["_base_z"] = rz
    streak["_speed"] = random.uniform(10.0, 18.0)  # fast falling
    rain_streaks.append(streak)

# ============ 50 SPLASH DROPLETS au sol ============
splashes = []
for i in range(50):
    a = random.uniform(0, math.pi*2)
    rad = random.uniform(2, 28)
    sx, sy = rad*math.cos(a), rad*math.sin(a)
    sp = smooth_sphere(f"splash{i}", r=random.uniform(0.06, 0.10), segs=8, rings=6,
                      loc=(sx, sy, 0.10), mat_=M_SPLASH, scale=(1.5, 1.5, 0.3))
    sp["_phase"] = random.uniform(0, math.pi*2)
    splashes.append(sp)

# ============ 100 LIGHTNING SPARKS (when lightning flashes) ============
spark_lights = []
for i in range(100):
    sx = random.uniform(-25, 25)
    sy = random.uniform(-25, 25)
    sz = random.uniform(5, 22)
    sp = smooth_sphere(f"spark_l{i}", r=random.uniform(0.04, 0.08), segs=6, rings=5,
                      loc=(sx, sy, sz), mat_=M_SPARK_LIGHT)
    sp["_phase"] = random.uniform(0, math.pi*2)
    sp["_base_x"] = sx; sp["_base_y"] = sy; sp["_base_z"] = sz
    spark_lights.append(sp)

# ============ ANIMATION ============
fps = 30; duration_s = 6; total_frames = fps * duration_s

# Trees sway in storm
for t in trees:
    phase = t["_phase"]
    for f in range(1, total_frames + 1, 5):
        t_v = (f - 1) / fps
        t.rotation_euler = (math.sin(t_v * 2.5 + phase) * math.radians(4),
                             math.cos(t_v * 2.3 + phase) * math.radians(3),
                             0)
        t.keyframe_insert("rotation_euler", frame=f)

# Lianas sway
for l in lianas:
    phase = l["_phase"]
    for f in range(1, total_frames + 1, 5):
        t = (f - 1) / fps
        l.rotation_euler = (math.sin(t * 2.0 + phase) * math.radians(8),
                             math.cos(t * 1.8 + phase) * math.radians(6),
                             0)
        l.keyframe_insert("rotation_euler", frame=f)

# Lightning flashes (rare bursts)
for bolt in lightning_bolts:
    phase = bolt["_phase"]
    for f in range(1, total_frames + 1, 2):
        t = (f - 1) / fps
        # Pulse on/off pattern (lightning flash)
        flash_factor = max(0, math.sin(t * 1.5 + phase) - 0.80) * 5.0
        s = flash_factor + 0.001
        bolt.scale = (s, s, s)
        bolt.keyframe_insert("scale", frame=f)

# Storm clouds drift
for c_e in clouds:
    phase = c_e["_phase"]
    bx, by = c_e.location.x, c_e.location.y
    for f in range(1, total_frames + 1, 8):
        t = (f - 1) / fps
        c_e.location = (bx + math.sin(t * 0.4 + phase) * 0.8,
                        by + math.cos(t * 0.3 + phase) * 0.8,
                        c_e.location.z)
        c_e.keyframe_insert("location", frame=f)

# Jaguars : stalk prowl + tail wave + head turn
for jag in jaguars:
    phase = hash(jag["root"].name) % 100 * 0.05
    base_z = jag["root"].location.z
    for f in range(1, total_frames + 1, 4):
        t = (f - 1) / fps
        jag["root"].location.z = base_z + math.sin(t * 1.5 + phase) * 0.03
        jag["root"].keyframe_insert("location", frame=f)
        jag["head_e"].rotation_euler = (math.sin(t * 0.8 + phase) * math.radians(5), 0,
                                          math.sin(t * 0.6 + phase) * math.radians(20))
        jag["head_e"].keyframe_insert("rotation_euler", frame=f)
        jag["tail"].rotation_euler = (0, math.sin(t * 2.0 + phase) * math.radians(20),
                                       math.sin(t * 1.5 + phase) * math.radians(25))
        jag["tail"].keyframe_insert("rotation_euler", frame=f)

# Toucans : beak open/close + head turn
for tc in toucans:
    phase = tc["phase"]
    for f in range(1, total_frames + 1, 4):
        t = (f - 1) / fps
        # Beak opens (signature toucan call)
        tc["beak_top"].rotation_euler = (math.radians(85) + math.sin(t * 3.0 + phase) * math.radians(8), 0, 0)
        tc["beak_bot"].rotation_euler = (math.radians(95) - math.sin(t * 3.0 + phase) * math.radians(8), 0, 0)
        tc["beak_top"].keyframe_insert("rotation_euler", frame=f)
        tc["beak_bot"].keyframe_insert("rotation_euler", frame=f)
        tc["head"].rotation_euler = (0, 0, math.sin(t * 1.0 + phase) * math.radians(20))
        tc["head"].keyframe_insert("rotation_euler", frame=f)

# Parrots flap wings + orbit
for p in parrots:
    phase = p["phase"]
    rad = p["orbit_rad"]
    speed = p["orbit_speed"]
    base_phase = p["orbit_phase"]
    base_z = p["base_z"]
    for f in range(1, total_frames + 1, 3):
        t = (f - 1) / fps
        flap = math.sin(t * 5.0 + phase) * math.radians(40)
        for w_e, side in p["wings"]:
            w_e.rotation_euler = (side * flap, 0, 0)
            w_e.keyframe_insert("rotation_euler", frame=f)
        a = base_phase + speed * t
        x = rad * math.cos(a)
        y = rad * math.sin(a)
        z = base_z + math.sin(t * 1.5 + phase) * 0.5
        p["e"].location = (x, y, z)
        p["e"].rotation_euler = (0, 0, a + math.pi/2)
        p["e"].keyframe_insert("location", frame=f)
        p["e"].keyframe_insert("rotation_euler", frame=f)

# Frogs : hop (signature)
for fr in frogs:
    phase = fr["phase"]
    base_z = fr["base_z"]
    for f in range(1, total_frames + 1, 4):
        t = (f - 1) / fps
        # Bouncing hop
        fr["e"].location.z = base_z + abs(math.sin(t * 2.5 + phase)) * 0.15
        fr["e"].keyframe_insert("location", frame=f)

# Mushrooms glow pulse
for m_obj in mushrooms:
    phase = m_obj["_phase"]
    for f in range(1, total_frames + 1, 5):
        t = (f - 1) / fps
        s = 1 + math.sin(t * 2.0 + phase) * 0.10
        m_obj.scale = (s, s, s)
        m_obj.keyframe_insert("scale", frame=f)

# ============================================================
# ⭐⭐⭐ 500 RAIN STREAKS qui TOMBENT (PARTICULE THÉMATIQUE OBLIGATOIRE)
# ============================================================
for r in rain_streaks:
    phase = r["_phase"]; speed = r["_speed"]
    bx, by, bz = r["_base_x"], r["_base_y"], r["_base_z"]
    for f in range(1, total_frames + 1, 3):
        t = (f - 1) / fps
        # Z descent fast (signature rain)
        z = bz - (speed * t) % 30
        # Slight X drift (wind tilt)
        x = bx - t * 0.5
        r.location = (x, by, max(-0.3, z))
        r.keyframe_insert("location", frame=f)

# Splashes pulse
for sp in splashes:
    phase = sp["_phase"]
    for f in range(1, total_frames + 1, 4):
        t = (f - 1) / fps
        cycle = (t * 2.0 + phase) % 1.5
        if cycle < 0.5:
            s = cycle * 4.0  # expand fast
        else:
            s = max(0.1, 1.0 - (cycle - 0.5) * 1.0)
        sp.scale = (1.5 * s, 1.5 * s, 0.3 * s)
        sp.keyframe_insert("scale", frame=f)

# Lightning sparks flash with bolts (cyclic)
for sl in spark_lights:
    phase = sl["_phase"]
    bx, by, bz = sl["_base_x"], sl["_base_y"], sl["_base_z"]
    for f in range(1, total_frames + 1, 3):
        t = (f - 1) / fps
        flash = max(0, math.sin(t * 1.5 + phase) - 0.85) * 6.7
        s = flash * 1.5 + 0.001
        sl.scale = (s, s, s)
        sl.keyframe_insert("scale", frame=f)

# ============ EXPORT ============
out_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "public", "_pbr_test")
out_dir = os.path.normpath(out_dir)
os.makedirs(out_dir, exist_ok=True)
out_glb = os.path.join(out_dir, "pbr_rainforest_proc.glb")

bpy.ops.object.select_all(action='SELECT')
bpy.ops.export_scene.gltf(
    filepath=out_glb, export_format='GLB',
    export_animations=True, export_apply=False, export_yup=True, use_selection=False,
)
size_mb = os.path.getsize(out_glb) / (1024 * 1024)
print(f"[proc_rainforest_thunderstorm] DONE → {out_glb} ({size_mb:.2f} MB)")
print("[proc_rainforest_thunderstorm] ONE ground + 12 tall trees + 20 lianas + 30 mushrooms + 4 jaguars + 3 toucans + 5 parrots + 5 tree frogs + 8 lightning bolts + 500 RAIN STREAKS + 50 splashes + 100 sparks + storm clouds")
print("⭐ FEEDBACK FIX: 1 single ground (no sandwich) + 500 rain falling Z descent 30m loop tilted 15° (thematic mandatory) ⭐")
