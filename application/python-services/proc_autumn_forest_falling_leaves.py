"""
proc_autumn_forest_falling_leaves.py — 212e procédural AuroraIA (76e qualité)
Forêt automne : ONE ground + 500 feuilles tombant + 15 arbres orange/rouge + 6 cerfs + 4 écureuils + 3 ours + ruisseau + cabane
FIXES : 1 ground + autumn leaves falling thématique obligatoire
"""
import bpy, bmesh, math, random, os

random.seed(0xA107511)

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

# Materials - warm autumn palette
M_SKY = mat("sky", (0.95, 0.55, 0.30, 1.0), 0.0, 0.7, emission=(0.95,0.60,0.32), emission_strength=2.0)
M_SUN = mat("sun", (1.0, 0.70, 0.25, 1.0), 0.0, 0.10, emission=(1.0,0.75,0.28), emission_strength=16.0)
M_CLOUD = mat("cloud", (0.95, 0.75, 0.55, 1.0), 0.0, 0.55, emission=(0.92,0.72,0.55), emission_strength=2.0, alpha=0.85)

# === ONE ground - leaves carpet ===
M_GROUND = mat("ground", (0.45, 0.30, 0.18, 1.0), 0.0, 0.85, emission=(0.40,0.25,0.15), emission_strength=0.3)
M_LEAF_CARPET = mat("leaf_carpet", (0.65, 0.30, 0.12, 1.0), 0.0, 0.80, emission=(0.55,0.25,0.10), emission_strength=0.4)
M_ROCK = mat("rock", (0.40, 0.32, 0.25, 1.0), 0.0, 0.85)

# Autumn leaves colors
M_LEAF_RED = mat("leaf_r", (0.95, 0.25, 0.15, 1.0), 0.0, 0.50, emission=(0.95,0.30,0.15), emission_strength=1.5)
M_LEAF_ORANGE = mat("leaf_o", (1.0, 0.55, 0.10, 1.0), 0.0, 0.55, emission=(1.0,0.55,0.12), emission_strength=1.8)
M_LEAF_YELLOW = mat("leaf_y", (1.0, 0.80, 0.20, 1.0), 0.0, 0.55, emission=(1.0,0.85,0.25), emission_strength=2.0)
M_LEAF_BROWN = mat("leaf_br", (0.65, 0.35, 0.15, 1.0), 0.0, 0.65, emission=(0.55,0.30,0.13), emission_strength=0.8)

# Trees
M_TRUNK = mat("trunk", (0.30, 0.20, 0.12, 1.0), 0.0, 0.85)
M_TRUNK_LIGHT = mat("trunk_l", (0.55, 0.40, 0.25, 1.0), 0.0, 0.80, emission=(0.45,0.32,0.20), emission_strength=0.3)

# Animals
M_DEER_BROWN = mat("deer", (0.55, 0.35, 0.20, 1.0), 0.0, 0.70, emission=(0.48,0.30,0.18), emission_strength=0.3)
M_DEER_BELLY = mat("deer_b", (0.92, 0.85, 0.65, 1.0), 0.0, 0.65, emission=(0.85,0.78,0.58), emission_strength=0.4)
M_DEER_TAIL = mat("deer_t", (0.95, 0.92, 0.88, 1.0), 0.0, 0.55, emission=(0.92,0.88,0.85), emission_strength=0.5)
M_ANTLER = mat("antler", (0.55, 0.42, 0.28, 1.0), 0.2, 0.50, emission=(0.45,0.35,0.22), emission_strength=0.3)
M_DEER_EYE = mat("deer_eye", (0.10, 0.06, 0.04, 1.0), 0.0, 0.20)

M_SQUIRREL_RED = mat("squirrel", (0.85, 0.40, 0.15, 1.0), 0.0, 0.65, emission=(0.78,0.38,0.15), emission_strength=0.5)
M_SQUIRREL_BELLY = mat("squirrel_b", (0.95, 0.85, 0.65, 1.0), 0.0, 0.65, emission=(0.85,0.78,0.58), emission_strength=0.4)

M_BEAR_BROWN = mat("bear", (0.30, 0.20, 0.12, 1.0), 0.0, 0.85, emission=(0.30,0.20,0.12), emission_strength=0.3)
M_BEAR_NOSE = mat("bear_n", (0.08, 0.06, 0.05, 1.0), 0.0, 0.40)

# Mushrooms (red+white agaric)
M_MUSH_RED = mat("mush_r", (0.95, 0.18, 0.18, 1.0), 0.0, 0.50, emission=(0.95,0.20,0.20), emission_strength=1.5)
M_MUSH_DOT = mat("mush_d", (1.0, 0.95, 0.85, 1.0), 0.0, 0.45, emission=(0.95,0.92,0.85), emission_strength=0.5)
M_MUSH_STEM = mat("mush_s", (0.92, 0.88, 0.78, 1.0), 0.0, 0.65, emission=(0.85,0.80,0.72), emission_strength=0.3)
M_MUSH_BROWN = mat("mush_br", (0.55, 0.35, 0.20, 1.0), 0.0, 0.70, emission=(0.50,0.32,0.18), emission_strength=0.4)

# Stream water
M_WATER = mat("water", (0.30, 0.55, 0.65, 0.75), 0.4, 0.10, emission=(0.40,0.65,0.75), emission_strength=0.8, alpha=0.75)
M_FOAM = mat("foam", (0.95, 0.95, 0.92, 1.0), 0.0, 0.50, emission=(0.90,0.90,0.88), emission_strength=1.0)

# Cabin
M_CABIN_WOOD = mat("cabin", (0.35, 0.22, 0.12, 1.0), 0.0, 0.80, emission=(0.30,0.18,0.10), emission_strength=0.3)
M_CABIN_ROOF = mat("cabin_r", (0.45, 0.20, 0.08, 1.0), 0.0, 0.75, emission=(0.40,0.18,0.08), emission_strength=0.3)
M_WINDOW = mat("window", (1.0, 0.85, 0.40, 1.0), 0.0, 0.20, emission=(1.0,0.85,0.40), emission_strength=10.0)
M_DOOR = mat("door", (0.25, 0.15, 0.08, 1.0), 0.0, 0.78)
M_CHIMNEY_SMOKE = mat("smoke", (0.85, 0.82, 0.78, 1.0), 0.0, 0.85, emission=(0.80,0.78,0.75), emission_strength=0.5, alpha=0.5)

# Pine cones
M_PINECONE = mat("pinecone", (0.45, 0.28, 0.15, 1.0), 0.0, 0.75)

# ============ SKY + SUN + CLOUDS ============
sky = smooth_sphere("sky", r=95, segs=32, rings=20, loc=(0,0,0), mat_=M_SKY, scale=(1,1,0.60))
sky.scale = (1,1,0.60)
# Setting sun (warm)
sun = smooth_sphere("sun", r=5.5, loc=(15, 35, 18), mat_=M_SUN)
# Sun halos
for i in range(3):
    halo = smooth_sphere(f"sun_halo{i}", r=5.5 + (i+1)*1.5, loc=(15, 35, 18),
                        mat_=M_SUN)
    halo["_phase"] = i * 0.5

# 8 clouds warm color drift
clouds = []
for i in range(8):
    a = (i / 8.0) * math.pi * 2
    rad = random.uniform(22, 32)
    cx, cy = rad*math.cos(a), rad*math.sin(a)
    cz = random.uniform(14, 22)
    c_e = empty(f"cloud_e{i}", (cx, cy, cz))
    for j in range(5):
        smooth_sphere(f"cloud{i}_{j}", r=random.uniform(2.0, 3.0),
                      loc=(random.uniform(-3,3), random.uniform(-2,2), random.uniform(-0.5,0.5)),
                      parent=c_e, mat_=M_CLOUD)
    c_e["_phase"] = random.uniform(0, math.pi*2)
    clouds.append(c_e)

# ============ ONE clean autumn ground (leaves carpet, single plane) ============
ground = beveled_cube("ground", (90, 90, 0.5), bevel_offset=0.08, loc=(0, 0, -0.25), mat_=M_GROUND)

# Organic ground variations via scattered leaf patches (3D scattered)
for i in range(80):
    a = random.uniform(0, math.pi*2)
    rad = random.uniform(3, 38)
    sx = rad * math.cos(a)
    sy = rad * math.sin(a)
    # Small leaf cluster (3D scattered, not flat sheet)
    smooth_sphere(f"leaf_p{i}", r=random.uniform(0.5, 1.2), segs=14, rings=10,
                  loc=(sx, sy, 0.10), mat_=M_LEAF_CARPET,
                  scale=(random.uniform(1.0, 1.4),
                         random.uniform(1.0, 1.4),
                         random.uniform(0.10, 0.25))).rotation_euler = (0, 0, random.uniform(0, math.pi*2))

# 20 rocks scattered
for i in range(20):
    a = random.uniform(0, math.pi*2)
    rad = random.uniform(5, 35)
    smooth_sphere(f"rock{i}", r=random.uniform(0.4, 1.2),
                  loc=(rad*math.cos(a), rad*math.sin(a), 0.25),
                  mat_=M_ROCK,
                  scale=(random.uniform(0.8,1.4), random.uniform(0.8,1.4),
                         random.uniform(0.5,0.8))).rotation_euler = (random.uniform(-0.2, 0.2),
                                                                       random.uniform(-0.2, 0.2),
                                                                       random.uniform(0, math.pi*2))

# ============ 15 AUTUMN TREES ============
trees = []
def make_autumn_tree(name, loc, height=8, scale=1.0, leaf_color=M_LEAF_RED):
    base = empty(name, loc)
    # Trunk 5-seg with bark texture (slight rotation per seg)
    for i in range(5):
        r1 = (0.35 - i*0.04) * scale
        r2 = (0.30 - i*0.04) * scale
        h = height / 5
        seg = smooth_cone(f"{name}_t{i}", r1=r1, r2=r2, depth=h, segs=14,
                          loc=(0, 0, (i+0.5)*h), parent=base, mat_=M_TRUNK)
        seg.rotation_euler = (math.radians(random.uniform(-3,3)),
                              math.radians(random.uniform(-3,3)), 0)
    # 6 main branches radiating from top
    branches_e = []
    top_z = height
    for j in range(6):
        a = (j / 6.0) * math.pi * 2 + random.uniform(-0.2, 0.2)
        b_e = empty(f"{name}_b_e{j}", (0, 0, top_z * 0.7), parent=base)
        b_e.rotation_euler = (math.radians(50), 0, a)
        # 2 segments
        for k in range(2):
            cyl(f"{name}_b{j}_{k}", r=(0.12 - k*0.03)*scale,
                depth=1.0*scale, segs=10,
                loc=(0, (k+0.5)*1.0*scale, 0), parent=b_e, mat_=M_TRUNK_LIGHT).rotation_euler = (math.radians(90), 0, 0)
        branches_e.append(b_e)

    # Canopy (15 dense leaf clusters in autumn colors)
    autumn_colors = [M_LEAF_RED, M_LEAF_ORANGE, M_LEAF_YELLOW]
    for j in range(15):
        a = random.uniform(0, math.pi*2)
        rad = random.uniform(1.5, 3.0) * scale
        cluster_color = random.choice(autumn_colors)
        smooth_sphere(f"{name}_can{j}", r=random.uniform(0.8, 1.4)*scale,
                      loc=(rad*math.cos(a), rad*math.sin(a),
                           top_z + random.uniform(-0.5, 1.5)),
                      parent=base, mat_=cluster_color,
                      scale=(1, 1, 0.85))
    base["_phase"] = random.uniform(0, math.pi*2)
    return base

tree_positions = [(-10, 5, 0, 8, 1.0), (12, 8, 0, 9, 1.1),
                  (-15, -5, 0, 7, 0.95), (8, -10, 0, 8, 1.0),
                  (-20, 2, 0, 9, 1.0), (18, 4, 0, 7, 0.9),
                  (-8, 18, 0, 8, 1.0), (10, -20, 0, 9, 1.05),
                  (-18, 18, 0, 7, 0.95), (20, -15, 0, 8, 1.0),
                  (-5, -18, 0, 8, 0.95), (5, 18, 0, 7, 0.9),
                  (-25, -2, 0, 9, 1.0), (25, 2, 0, 8, 1.0),
                  (0, 22, 0, 10, 1.1)]
for i, (tx, ty, tz, h, sc) in enumerate(tree_positions):
    colors = [M_LEAF_RED, M_LEAF_ORANGE, M_LEAF_YELLOW]
    t = make_autumn_tree(f"tree{i}", (tx, ty, tz), height=h, scale=sc,
                         leaf_color=colors[i % 3])
    trees.append(t)

# ============ STREAM (small flowing creek) ============
stream_e = empty("stream", loc=(0, 0, 0))
# 8 connected water segments forming serpentine creek
for i in range(8):
    sx = -15 + i * 4
    sy = math.sin(i * 0.5) * 2.5
    seg = beveled_cube(f"stream{i}", (4.5, 1.2, 0.10), bevel_offset=0.04,
                       loc=(sx, sy, 0.05), parent=stream_e, mat_=M_WATER)
    seg["_phase"] = i * 0.4
# Foam at rocks (4 small)
for i in range(4):
    sx = -10 + i * 8
    sy = math.sin(i * 0.5 + 1) * 2.5
    smooth_sphere(f"foam{i}", r=0.20, loc=(sx, sy, 0.12), parent=stream_e,
                  mat_=M_FOAM, scale=(1.5, 1, 0.3))
    foam = bpy.data.objects[f"foam{i}"]
    foam["_phase"] = i * 0.5

# Stream bank rocks (8)
for i in range(8):
    side = -1 if i < 4 else 1
    idx = i % 4
    sx = -10 + idx * 6
    sy = math.sin(idx * 0.5) * 2.5 + side * 0.8
    smooth_sphere(f"stream_rock{i}", r=random.uniform(0.30, 0.55),
                  loc=(sx, sy, 0.15), parent=stream_e, mat_=M_ROCK,
                  scale=(1, 1, 0.6))

# ============ CABIN (wooden rustique) ============
cabin_e = empty("cabin", loc=(-8, 14, 0))
cabin_e.rotation_euler = (0, 0, math.radians(-20))
# Main body (log cabin)
beveled_cube("cabin_body", (3.5, 3.0, 2.5), bevel_offset=0.06,
             loc=(0, 0, 1.25), parent=cabin_e, mat_=M_CABIN_WOOD)
# Log details (visible 5 horizontal logs)
for i in range(5):
    cyl(f"cabin_log{i}", r=0.13, depth=3.5, segs=14,
        loc=(0, -1.55, 0.30 + i*0.50), parent=cabin_e, mat_=M_CABIN_WOOD).rotation_euler = (0, math.radians(90), 0)
# Roof (peaked triangular)
for side in (-1, 1):
    roof = beveled_cube(f"cabin_roof_{side}", (3.8, 2.0, 0.20), bevel_offset=0.05,
                       loc=(0, side*1.0, 3.0), parent=cabin_e, mat_=M_CABIN_ROOF)
    roof.rotation_euler = (math.radians(side*-25), 0, 0)
# Door (front)
beveled_cube("cabin_door", (0.80, 0.06, 1.6), loc=(0, -1.55, 0.80),
             parent=cabin_e, mat_=M_DOOR)
# Door handle
smooth_sphere("door_handle", r=0.05, loc=(0.30, -1.60, 0.80),
              parent=cabin_e, mat_=M_ANTLER)
# 2 windows glowing (warm interior light)
for side in (-1, 1):
    beveled_cube(f"cabin_win{side}", (0.55, 0.06, 0.55), bevel_offset=0.02,
                 loc=(side*1.20, -1.55, 1.50), parent=cabin_e, mat_=M_WINDOW)
    # Window frame
    for fi in range(4):
        beveled_cube(f"cabin_win_frame{side}_{fi}",
                     (0.60, 0.04, 0.06) if fi < 2 else (0.06, 0.04, 0.55),
                     loc=(side*1.20, -1.55, 1.20 + fi*0.30) if fi < 2 else (side*1.20 + (fi-2.5)*0.30, -1.55, 1.50),
                     parent=cabin_e, mat_=M_DOOR)
# Chimney
cyl("cabin_chimney", r=0.30, depth=2.0, segs=14,
    loc=(1.0, 0.5, 3.5), parent=cabin_e, mat_=M_ROCK)
# Chimney brick lines
for i in range(4):
    cyl(f"chim_band{i}", r=0.32, depth=0.06, segs=14,
        loc=(1.0, 0.5, 2.8 + i*0.4), parent=cabin_e, mat_=M_BEAR_BROWN)
# Smoke rising from chimney
smoke_chim_e = empty("smoke_chim", (1.0, 0.5, 4.5), parent=cabin_e)
for i in range(4):
    smooth_sphere(f"chim_smoke{i}", r=0.20 + i*0.05,
                  loc=(random.uniform(-0.10, 0.10), random.uniform(-0.10, 0.10), i*0.4),
                  parent=smoke_chim_e, mat_=M_CHIMNEY_SMOKE)

# Stack of firewood beside cabin (12 logs)
for i in range(12):
    cyl(f"firewood{i}", r=0.13, depth=1.0, segs=10,
        loc=(2.4, -1.3 + (i % 3)*0.30, 0.20 + (i // 3) * 0.28),
        parent=cabin_e, mat_=M_CABIN_WOOD).rotation_euler = (0, math.radians(90), 0)

# ============ DEER constructor (with antlers + white tail signature) ============
def make_deer(name, loc, has_antlers=True, facing=0):
    base = empty(name, loc)
    base.rotation_euler = (0, 0, facing)
    # Body
    smooth_sphere(f"{name}_body", r=0.42, segs=22, rings=14, loc=(0, 0, 1.10),
                  parent=base, mat_=M_DEER_BROWN, scale=(2.0, 0.95, 1.0))
    # Belly white
    smooth_sphere(f"{name}_belly", r=0.36, loc=(0, 0, 0.92),
                  parent=base, mat_=M_DEER_BELLY, scale=(1.7, 0.85, 0.55))
    # 4 long thin legs
    for x_idx, x in enumerate((-1, 1)):
        for y_idx, y in enumerate((-1, 1)):
            cyl(f"{name}_leg{x_idx}{y_idx}", r=0.07, depth=1.0, segs=10,
                loc=(x*0.40, y*0.22, 0.50), parent=base, mat_=M_DEER_BROWN)
            # Hoof
            cyl(f"{name}_hoof{x_idx}{y_idx}", r=0.08, depth=0.06, segs=10,
                loc=(x*0.40, y*0.22, 0.03), parent=base, mat_=mat(f"hf{name[-1]}_{x_idx}{y_idx}", (0.15,0.10,0.05,1), 0.3, 0.55))
    # NECK long
    neck_e = empty(f"{name}_neck_e", (0.65, 0, 1.20), parent=base)
    cyl(f"{name}_neck", r=0.14, depth=0.55, segs=12,
        loc=(0.10, 0, 0.30), parent=neck_e, mat_=M_DEER_BROWN).rotation_euler = (0, math.radians(60), 0)
    # HEAD
    head_e = empty(f"{name}_head_e", (1.10, 0, 1.65), parent=base)
    smooth_sphere(f"{name}_h", r=0.18, segs=20, rings=14, loc=(0, 0, 0),
                  parent=head_e, mat_=M_DEER_BROWN, scale=(1.7, 0.9, 0.9))
    # Snout
    smooth_sphere(f"{name}_snout", r=0.12, loc=(0.18, 0, -0.06),
                  parent=head_e, mat_=M_DEER_BELLY)
    # Nose
    smooth_sphere(f"{name}_nose", r=0.04, loc=(0.30, 0, -0.05),
                  parent=head_e, mat_=M_BEAR_NOSE)
    # Eyes large dark
    for side in (-1, 1):
        smooth_sphere(f"{name}_eye{side}", r=0.04, loc=(side*0.10, 0.06, 0.03),
                      parent=head_e, mat_=M_DEER_EYE)
    # 2 ears large
    for side in (-1, 1):
        ear = smooth_cone(f"{name}_ear{side}", r1=0.08, r2=0.005, depth=0.20, segs=8,
                         loc=(side*0.13, 0.02, 0.18), parent=head_e, mat_=M_DEER_BROWN)
        ear.rotation_euler = (math.radians(-15), math.radians(side*15), 0)
    # ANTLERS branched (signature stag)
    if has_antlers:
        for side in (-1, 1):
            antler_e = empty(f"{name}_ant{side}", (side*0.10, -0.05, 0.25), parent=head_e)
            antler_e.rotation_euler = (math.radians(-15), math.radians(side*25), 0)
            # Main shaft
            for s in range(3):
                cyl(f"{name}_ant_s{side}_{s}", r=0.04 - s*0.005, depth=0.30, segs=10,
                    loc=(0, 0, s*0.30 + 0.15), parent=antler_e, mat_=M_ANTLER).rotation_euler = (math.radians(-15*s), 0, 0)
            # 2 branches
            for b in range(2):
                br_e = empty(f"{name}_ant_br{side}_{b}", (0, 0, 0.40 + b*0.40), parent=antler_e)
                br_e.rotation_euler = (math.radians(-30), math.radians(side*45), 0)
                cyl(f"{name}_ant_br_s{side}_{b}", r=0.025, depth=0.20, segs=8,
                    loc=(0, 0, 0.10), parent=br_e, mat_=M_ANTLER)
                smooth_cone(f"{name}_ant_br_t{side}_{b}", r1=0.025, r2=0.005, depth=0.08, segs=6,
                            loc=(0, 0, 0.24), parent=br_e, mat_=M_ANTLER)
    # WHITE TAIL up (signature deer)
    tail_e = empty(f"{name}_tail_e", (-0.90, 0, 1.30), parent=base)
    tail_e.rotation_euler = (math.radians(-30), 0, 0)
    smooth_sphere(f"{name}_tail", r=0.10, loc=(0, 0, 0.15),
                  parent=tail_e, mat_=M_DEER_TAIL, scale=(1, 1.5, 1))
    return {"root": base, "head_e": head_e, "tail_e": tail_e}

# 6 deer (2 stags with antlers + 4 does)
deer = []
deer_pos = [(-3, -5, 0, True, math.radians(45)),    # stag
            (3, -8, 0, True, math.radians(-30)),    # stag
            (-5, -3, 0, False, math.radians(60)),   # doe
            (5, -5, 0, False, math.radians(-45)),   # doe
            (-7, -7, 0, False, math.radians(30)),   # doe
            (7, -3, 0, False, math.radians(-60))]   # doe
for i, (dx, dy, dz, antlers, fac) in enumerate(deer_pos):
    d = make_deer(f"deer{i}", (dx, dy, dz), has_antlers=antlers, facing=fac)
    deer.append(d)

# ============ 4 SQUIRRELS on tree branches ============
squirrels = []
for i in range(4):
    # Place on tree branches
    tree_idx = i * 3 % len(tree_positions)
    tx, ty, tz, h, sc = tree_positions[tree_idx]
    sx = tx + random.uniform(-1.5, 1.5)
    sy = ty + random.uniform(-1.5, 1.5)
    sz_pos = h * 0.7 + random.uniform(-0.5, 0.5)
    sq_e = empty(f"squirrel{i}", (sx, sy, sz_pos))
    sq_e.rotation_euler = (0, 0, random.uniform(-math.pi, math.pi))
    # Body small
    smooth_sphere(f"sq_body{i}", r=0.12, segs=18, rings=12, loc=(0, 0, 0.10),
                  parent=sq_e, mat_=M_SQUIRREL_RED, scale=(1.5, 1.0, 1.0))
    # Belly
    smooth_sphere(f"sq_belly{i}", r=0.10, loc=(0, 0, 0.05),
                  parent=sq_e, mat_=M_SQUIRREL_BELLY, scale=(1.3, 0.85, 0.55))
    # Head
    head_e = empty(f"sq_head_e{i}", (0.18, 0, 0.20), parent=sq_e)
    smooth_sphere(f"sq_h{i}", r=0.08, segs=16, rings=10, loc=(0, 0, 0),
                  parent=head_e, mat_=M_SQUIRREL_RED, scale=(1.2, 0.95, 0.95))
    # Snout
    smooth_sphere(f"sq_snout{i}", r=0.05, loc=(0.07, 0, -0.02),
                  parent=head_e, mat_=M_SQUIRREL_BELLY)
    # Nose
    smooth_sphere(f"sq_nose{i}", r=0.012, loc=(0.10, 0, -0.02),
                  parent=head_e, mat_=M_BEAR_NOSE)
    # Eyes
    for side in (-1, 1):
        smooth_sphere(f"sq_eye{i}_{side}", r=0.018, loc=(side*0.04, 0.04, 0.02),
                      parent=head_e, mat_=M_DEER_EYE)
    # 2 pointed ears (signature squirrel)
    for side in (-1, 1):
        ear = smooth_cone(f"sq_ear{i}_{side}", r1=0.025, r2=0.005, depth=0.06, segs=6,
                         loc=(side*0.05, 0, 0.10), parent=head_e, mat_=M_SQUIRREL_RED)
    # 4 small legs
    for x_idx, x in enumerate((-1, 1)):
        for y_idx, y in enumerate((-1, 1)):
            cyl(f"sq_leg{i}_{x_idx}{y_idx}", r=0.02, depth=0.10, segs=8,
                loc=(x*0.08, y*0.08, 0.05), parent=sq_e, mat_=M_SQUIRREL_RED)
    # LARGE BUSHY TAIL up (signature squirrel)
    tail_e = empty(f"sq_tail_e{i}", (-0.10, 0, 0.10), parent=sq_e)
    tail_e.rotation_euler = (math.radians(-90), 0, 0)
    # 4 fluffy chunks
    for j in range(4):
        smooth_sphere(f"sq_tail{i}_{j}", r=0.10 - j*0.01,
                      loc=(0, 0.15 + j*0.10, 0),
                      parent=tail_e, mat_=M_SQUIRREL_RED, scale=(1, 1.3, 1.5))
    # Acorn in front paws (signature)
    smooth_sphere(f"sq_acorn{i}", r=0.04, loc=(0.20, 0, 0.10),
                  parent=sq_e, mat_=M_MUSH_BROWN)
    smooth_sphere(f"sq_acorn_cap{i}", r=0.045, loc=(0.20, 0, 0.13),
                  parent=sq_e, mat_=M_PINECONE, scale=(1, 1, 0.5))
    squirrels.append({"e": sq_e, "head": head_e, "tail": tail_e,
                       "phase": random.uniform(0, math.pi*2)})

# ============ 3 BROWN BEARS foraging ============
bears = []
def make_bear(name, loc, scale=1.0, facing=0):
    base = empty(name, loc)
    base.rotation_euler = (0, 0, facing)
    # Body massive
    smooth_sphere(f"{name}_body", r=0.65*scale, segs=22, rings=14, loc=(0, 0, 0.85*scale),
                  parent=base, mat_=M_BEAR_BROWN, scale=(2.0, 1.1, 1.0))
    # 4 legs
    for x_idx, x in enumerate((-1, 1)):
        for y_idx, y in enumerate((-1, 1)):
            cyl(f"{name}_leg{x_idx}{y_idx}", r=0.18*scale, depth=0.70*scale, segs=12,
                loc=(x*0.50*scale, y*0.35*scale, 0.35*scale), parent=base, mat_=M_BEAR_BROWN)
            # Paw
            smooth_sphere(f"{name}_paw{x_idx}{y_idx}", r=0.22*scale, loc=(x*0.50*scale, y*0.35*scale + 0.05*scale, 0.05*scale),
                          parent=base, mat_=M_BEAR_BROWN, scale=(1, 1.3, 0.6))
            # Claws (3)
            for c in range(3):
                smooth_cone(f"{name}_claw{x_idx}{y_idx}_{c}", r1=0.03*scale, r2=0.005, depth=0.08*scale, segs=6,
                            loc=(x*0.50*scale + (c-1)*0.08*scale, y*0.35*scale + 0.25*scale, 0.04*scale),
                            parent=base, mat_=mat(f"bc{name[-1]}_{x_idx}{y_idx}_{c}", (0.10,0.08,0.05,1), 0.2, 0.5)).rotation_euler = (math.radians(60), 0, 0)
    # Head
    head_e = empty(f"{name}_head_e", (1.20*scale, 0, 1.0*scale), parent=base)
    smooth_sphere(f"{name}_h", r=0.30*scale, segs=22, rings=14, loc=(0, 0, 0),
                  parent=head_e, mat_=M_BEAR_BROWN, scale=(1.2, 1.0, 1.0))
    # Snout
    smooth_sphere(f"{name}_snout", r=0.22*scale, loc=(0.22*scale, 0, -0.08*scale),
                  parent=head_e, mat_=M_BEAR_BROWN, scale=(1.1, 1.0, 0.85))
    # Nose black
    smooth_sphere(f"{name}_nose", r=0.06*scale, loc=(0.40*scale, 0, -0.08*scale),
                  parent=head_e, mat_=M_BEAR_NOSE)
    # Mouth
    beveled_cube(f"{name}_mouth", (0.12*scale, 0.04*scale, 0.04*scale), loc=(0.32*scale, 0, -0.20*scale),
                 parent=head_e, mat_=M_BEAR_NOSE)
    # Eyes
    for side in (-1, 1):
        smooth_sphere(f"{name}_eye{side}", r=0.035*scale, loc=(0.13*scale, side*0.13*scale, 0.06*scale),
                      parent=head_e, mat_=M_DEER_EYE)
    # 2 round ears
    for side in (-1, 1):
        smooth_sphere(f"{name}_ear{side}", r=0.09*scale, loc=(-0.10*scale, side*0.20*scale, 0.25*scale),
                      parent=head_e, mat_=M_BEAR_BROWN)
    return {"root": base, "head_e": head_e}

bear_pos = [(-15, -12, 0, 1.0, math.radians(60)),
            (12, -18, 0, 1.1, math.radians(-30)),
            (-18, 8, 0, 0.95, math.radians(45))]
for i, (bx, by, bz, sc, fac) in enumerate(bear_pos):
    b = make_bear(f"bear{i}", (bx, by, bz), scale=sc, facing=fac)
    bears.append(b)

# ============ 8 MUSHROOMS (red agaric + brown mix) ============
mushrooms = []
for i in range(8):
    a = random.uniform(0, math.pi*2)
    rad = random.uniform(3, 18)
    mx = rad*math.cos(a); my = rad*math.sin(a)
    m_e = empty(f"mush{i}", (mx, my, 0))
    h = random.uniform(0.30, 0.55)
    cyl(f"mush_stem{i}", r=random.uniform(0.06, 0.10), depth=h, segs=10,
        loc=(0, 0, h/2), parent=m_e, mat_=M_MUSH_STEM)
    is_red = random.random() < 0.5
    cap_mat = M_MUSH_RED if is_red else M_MUSH_BROWN
    cap_r = random.uniform(0.18, 0.30)
    smooth_sphere(f"mush_cap{i}", r=cap_r, segs=18, rings=12,
                  loc=(0, 0, h+0.05), parent=m_e, mat_=cap_mat, scale=(1, 1, 0.55))
    if is_red:
        # White dots
        for j in range(5):
            da = (j / 5.0) * math.pi * 2
            smooth_sphere(f"mush_dot{i}_{j}", r=cap_r*0.18,
                          loc=(cap_r*0.5*math.cos(da), cap_r*0.5*math.sin(da), h+0.12),
                          parent=m_e, mat_=M_MUSH_DOT)
    m_e["_phase"] = random.uniform(0, math.pi*2)
    mushrooms.append(m_e)

# ============ 50 PINE CONES on ground ============
for i in range(50):
    a = random.uniform(0, math.pi*2)
    rad = random.uniform(3, 32)
    px = rad*math.cos(a)
    py = rad*math.sin(a)
    pc = smooth_cone(f"pinecone{i}", r1=0.07, r2=0.04, depth=0.18, segs=10,
                     loc=(px, py, 0.10), mat_=M_PINECONE)
    pc.rotation_euler = (math.radians(random.uniform(-30, 30)),
                         math.radians(random.uniform(-30, 30)),
                         random.uniform(0, math.pi*2))

# ============ 200 LEAVES already on ground (organic 3D bumps) ============
for i in range(200):
    a = random.uniform(0, math.pi*2)
    rad = random.uniform(2, 35)
    lx = rad*math.cos(a)
    ly = rad*math.sin(a)
    color = random.choice([M_LEAF_RED, M_LEAF_ORANGE, M_LEAF_YELLOW, M_LEAF_BROWN])
    leaf = beveled_cube(f"ground_leaf{i}", (0.20, 0.18, 0.025), bevel_offset=0.02,
                        loc=(lx, ly, 0.08), mat_=color)
    leaf.rotation_euler = (math.radians(random.uniform(-20, 20)),
                           math.radians(random.uniform(-20, 20)),
                           random.uniform(0, math.pi*2))

# ============================================================
# ⭐ 500 FEUILLES qui TOMBENT (PARTICULE THÉMATIQUE OBLIGATOIRE autumn)
# ============================================================
falling_leaves = []
for i in range(500):
    lx = random.uniform(-40, 40)
    ly = random.uniform(-40, 40)
    lz = random.uniform(2, 22)
    color = random.choice([M_LEAF_RED, M_LEAF_ORANGE, M_LEAF_YELLOW, M_LEAF_BROWN])
    leaf = beveled_cube(f"fall_leaf{i}", (0.18, 0.16, 0.02), bevel_offset=0.01,
                       loc=(lx, ly, lz), mat_=color)
    leaf.rotation_euler = (random.uniform(0, math.pi*2),
                           random.uniform(0, math.pi*2),
                           random.uniform(0, math.pi*2))
    leaf["_phase"] = random.uniform(0, math.pi*2)
    leaf["_base_x"] = lx; leaf["_base_y"] = ly; leaf["_base_z"] = lz
    leaf["_speed"] = random.uniform(0.8, 2.0)  # slow falling (leaves are light)
    leaf["_drift_x"] = random.uniform(-1.2, 1.2)
    leaf["_drift_y"] = random.uniform(-1.2, 1.2)
    falling_leaves.append(leaf)

# ============ ANIMATION ============
fps = 30; duration_s = 6; total_frames = fps * duration_s

# Trees sway gentle autumn breeze
for t in trees:
    phase = t["_phase"]
    for f in range(1, total_frames + 1, 5):
        t_v = (f - 1) / fps
        t.rotation_euler = (math.sin(t_v * 1.0 + phase) * math.radians(2.5),
                             math.cos(t_v * 0.9 + phase) * math.radians(2.0),
                             0)
        t.keyframe_insert("rotation_euler", frame=f)

# 6 DEER : Z bob + head turn + tail flick
for d in deer:
    phase = hash(d["root"].name) % 100 * 0.05
    base_z = d["root"].location.z
    for f in range(1, total_frames + 1, 4):
        t = (f - 1) / fps
        d["root"].location.z = base_z + math.sin(t * 1.2 + phase) * 0.03
        d["root"].keyframe_insert("location", frame=f)
        d["head_e"].rotation_euler = (math.sin(t * 0.8 + phase) * math.radians(8), 0,
                                        math.sin(t * 0.6 + phase) * math.radians(20))
        d["head_e"].keyframe_insert("rotation_euler", frame=f)
        # Tail flick
        d["tail_e"].rotation_euler = (math.radians(-30) + math.sin(t * 3.0 + phase) * math.radians(10),
                                       0,
                                       math.sin(t * 2.5 + phase) * math.radians(15))
        d["tail_e"].keyframe_insert("rotation_euler", frame=f)

# 4 SQUIRRELS : bounce + tail wave + head turn
for sq in squirrels:
    phase = sq["phase"]
    base_z = sq["e"].location.z
    for f in range(1, total_frames + 1, 3):
        t = (f - 1) / fps
        # Quick bouncing
        sq["e"].location.z = base_z + abs(math.sin(t * 3.5 + phase)) * 0.08
        sq["e"].keyframe_insert("location", frame=f)
        sq["head"].rotation_euler = (0, 0, math.sin(t * 1.5 + phase) * math.radians(30))
        sq["head"].keyframe_insert("rotation_euler", frame=f)
        # Tail wave (signature)
        sq["tail"].rotation_euler = (math.radians(-90) + math.sin(t * 2.5 + phase) * math.radians(15),
                                      math.sin(t * 2.0 + phase) * math.radians(10),
                                      0)
        sq["tail"].keyframe_insert("rotation_euler", frame=f)

# 3 BEARS : Z bob + head turn
for b in bears:
    phase = hash(b["root"].name) % 100 * 0.05
    base_z = b["root"].location.z
    for f in range(1, total_frames + 1, 5):
        t = (f - 1) / fps
        b["root"].location.z = base_z + math.sin(t * 1.0 + phase) * 0.04
        b["root"].keyframe_insert("location", frame=f)
        b["head_e"].rotation_euler = (math.sin(t * 0.8 + phase) * math.radians(8), 0,
                                        math.sin(t * 0.6 + phase) * math.radians(20))
        b["head_e"].keyframe_insert("rotation_euler", frame=f)

# Mushrooms subtle pulse
for m_obj in mushrooms:
    phase = m_obj["_phase"]
    for f in range(1, total_frames + 1, 6):
        t = (f - 1) / fps
        s = 1 + math.sin(t * 1.5 + phase) * 0.05
        m_obj.scale = (s, s, s)
        m_obj.keyframe_insert("scale", frame=f)

# Stream water flow pulse
for obj in stream_e.children:
    if obj.name.startswith("stream") and "_phase" in obj.keys():
        phase = obj["_phase"]
        for f in range(1, total_frames + 1, 4):
            t = (f - 1) / fps
            s = 1 + math.sin(t * 2.5 + phase) * 0.03
            obj.scale = (s, s, s)
            obj.keyframe_insert("scale", frame=f)

# Cabin smoke rise
for child in smoke_chim_e.children:
    base_z = child.location.z
    for f in range(1, total_frames + 1, 6):
        t = (f - 1) / fps
        child.location.z = base_z + (t * 0.5) % 3.0
        s = 1 + math.sin(t * 0.8) * 0.15
        child.scale = (s, s, s)
        child.keyframe_insert("location", frame=f)
        child.keyframe_insert("scale", frame=f)

# Clouds drift + sun halos breathe
for c_e in clouds:
    phase = c_e["_phase"]
    bx, by = c_e.location.x, c_e.location.y
    for f in range(1, total_frames + 1, 8):
        t = (f - 1) / fps
        c_e.location = (bx + math.sin(t * 0.3 + phase) * 0.6,
                        by + math.cos(t * 0.25 + phase) * 0.6,
                        c_e.location.z)
        c_e.keyframe_insert("location", frame=f)

for obj in bpy.data.objects:
    if obj.name.startswith("sun_halo"):
        if "_phase" in obj.keys():
            phase = obj["_phase"]
            for f in range(1, total_frames + 1, 6):
                t = (f - 1) / fps
                s = 1 + math.sin(t * 0.8 + phase) * 0.05
                obj.scale = (s, s, s)
                obj.keyframe_insert("scale", frame=f)

# ============================================================
# ⭐⭐⭐ 500 FEUILLES qui TOMBENT (signature autumn)
# ============================================================
for lf in falling_leaves:
    phase = lf["_phase"]; speed = lf["_speed"]
    bx, by, bz = lf["_base_x"], lf["_base_y"], lf["_base_z"]
    drift_x = lf["_drift_x"]; drift_y = lf["_drift_y"]
    for f in range(1, total_frames + 1, 4):
        t = (f - 1) / fps
        # Slow descent
        z = bz - (speed * t) % 22
        # Spiral drift (leaves flutter signature)
        x = bx + drift_x * math.sin(t * 1.2 + phase) * 0.6
        y = by + drift_y * math.cos(t * 1.0 + phase) * 0.6
        # Tumble rotation (signature falling leaf)
        rx = phase + t * 1.5
        ry = phase + t * 1.2
        rz = phase + t * 1.8
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
out_glb = os.path.join(out_dir, "pbr_autumn_proc.glb")

bpy.ops.object.select_all(action='SELECT')
bpy.ops.export_scene.gltf(
    filepath=out_glb, export_format='GLB',
    export_animations=True, export_apply=False, export_yup=True, use_selection=False,
)
size_mb = os.path.getsize(out_glb) / (1024 * 1024)
print(f"[proc_autumn_forest_falling_leaves] DONE → {out_glb} ({size_mb:.2f} MB)")
print("[proc_autumn_forest_falling_leaves] ONE ground + 15 autumn trees + 6 deer + 4 squirrels + 3 bears + cabin + stream + 8 mushrooms + 50 pinecones + 200 ground leaves + 500 FALLING LEAVES")
print("⭐ FIXES: 1 ground + 500 leaves falling Z slow + spiral drift + tumble rotation (autumn signature mandatory) ⭐")
