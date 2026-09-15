"""
proc_meteor_impact_crater_dinosaurs.py — 193e procédural AuroraIA (57e qualité)
Extinction K-Pg : météore en chute + crater + dinos fuyant + ptérodactyles + jungle brûlante + lave + cendres
"""
import bpy, bmesh, math, random, os

random.seed(0x6510193)

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
M_SKY = mat("sky", (0.30, 0.10, 0.08, 1.0), 0.0, 0.7, emission=(0.50,0.15,0.10), emission_strength=2.0)
M_ASH = mat("ash", (0.22, 0.20, 0.20, 1.0), 0.0, 0.85, emission=(0.30,0.25,0.22), emission_strength=0.5, alpha=0.5)
M_GROUND = mat("ground", (0.20, 0.15, 0.10, 1.0), 0.0, 0.85)
M_GROUND_BURN = mat("ground_burn", (0.40, 0.18, 0.08, 1.0), 0.0, 0.65, emission=(0.45,0.20,0.08), emission_strength=0.8)
M_CRATER = mat("crater", (0.55, 0.20, 0.10, 1.0), 0.0, 0.55, emission=(0.55,0.18,0.08), emission_strength=1.5)
M_LAVA = mat("lava", (1.0, 0.45, 0.10, 1.0), 0.0, 0.10, emission=(1.0,0.50,0.12), emission_strength=15.0)
M_LAVA_DARK = mat("lava_dark", (0.85, 0.30, 0.05, 1.0), 0.0, 0.15, emission=(0.85,0.30,0.05), emission_strength=8.0)

# Meteor
M_METEOR = mat("meteor", (0.20, 0.15, 0.12, 1.0), 0.4, 0.45, emission=(0.65,0.30,0.10), emission_strength=4.0)
M_METEOR_GLOW = mat("meteor_glow", (1.0, 0.55, 0.15, 1.0), 0.0, 0.10, emission=(1.0,0.60,0.20), emission_strength=25.0)
M_PLASMA_TRAIL = mat("plasma_trail", (1.0, 0.75, 0.30, 1.0), 0.0, 0.10, emission=(1.0,0.80,0.35), emission_strength=20.0)

# Shock wave ring
M_SHOCKWAVE = mat("shockwave", (1.0, 0.85, 0.55, 1.0), 0.0, 0.10, emission=(1.0,0.90,0.55), emission_strength=8.0, alpha=0.6)

# Trees + jungle
M_TRUNK = mat("trunk", (0.30, 0.20, 0.12, 1.0), 0.0, 0.85)
M_TRUNK_BURNT = mat("trunk_burnt", (0.10, 0.08, 0.06, 1.0), 0.0, 0.90, emission=(0.30,0.10,0.05), emission_strength=0.6)
M_LEAF = mat("leaf", (0.20, 0.45, 0.20, 1.0), 0.0, 0.65)
M_LEAF_BURN = mat("leaf_burn", (0.85, 0.45, 0.15, 1.0), 0.0, 0.50, emission=(0.95,0.50,0.15), emission_strength=2.5)
M_FERN = mat("fern", (0.18, 0.40, 0.15, 1.0), 0.0, 0.70, emission=(0.18,0.40,0.12), emission_strength=0.4)

# Fire
M_FLAME = mat("flame", (1.0, 0.50, 0.10, 1.0), 0.0, 0.10, emission=(1.0,0.55,0.15), emission_strength=12.0)
M_FLAME_INNER = mat("flame_in", (1.0, 0.85, 0.30, 1.0), 0.0, 0.10, emission=(1.0,0.90,0.40), emission_strength=18.0)

# Dinosaurs
M_TREX = mat("trex", (0.40, 0.30, 0.18, 1.0), 0.0, 0.70, emission=(0.35,0.25,0.15), emission_strength=0.2)
M_TREX_BELLY = mat("trex_belly", (0.65, 0.55, 0.35, 1.0), 0.0, 0.65)
M_TRICE = mat("trice", (0.45, 0.45, 0.30, 1.0), 0.0, 0.70, emission=(0.40,0.40,0.25), emission_strength=0.2)
M_TRICE_FRILL = mat("trice_frill", (0.65, 0.30, 0.20, 1.0), 0.0, 0.60, emission=(0.55,0.25,0.18), emission_strength=0.4)
M_RAPTOR = mat("raptor", (0.55, 0.35, 0.20, 1.0), 0.0, 0.65, emission=(0.45,0.30,0.18), emission_strength=0.3)
M_RAPTOR_STRIPE = mat("raptor_stripe", (0.85, 0.65, 0.40, 1.0), 0.0, 0.60, emission=(0.75,0.55,0.35), emission_strength=0.4)
M_TEETH = mat("teeth", (0.92, 0.88, 0.78, 1.0), 0.0, 0.50, emission=(0.85,0.80,0.70), emission_strength=0.4)
M_EYE = mat("eye", (1.0, 0.95, 0.30, 1.0), 0.0, 0.15, emission=(1.0,0.95,0.30), emission_strength=8.0)
M_CLAW = mat("claw", (0.15, 0.12, 0.08, 1.0), 0.3, 0.55, emission=(0.20,0.15,0.10), emission_strength=0.3)
M_BLOOD = mat("blood", (0.65, 0.10, 0.10, 1.0), 0.0, 0.45, emission=(0.55,0.10,0.08), emission_strength=0.5)

# Pterodactyl
M_PTERO = mat("ptero", (0.40, 0.30, 0.40, 1.0), 0.0, 0.65, emission=(0.35,0.25,0.35), emission_strength=0.3)
M_PTERO_MEMBRANE = mat("ptero_mem", (0.55, 0.35, 0.50, 1.0), 0.0, 0.55, emission=(0.50,0.30,0.45), emission_strength=0.4)
M_PTERO_CREST = mat("ptero_crest", (0.85, 0.50, 0.35, 1.0), 0.0, 0.55, emission=(0.80,0.45,0.30), emission_strength=0.6)

# Sparks / debris / smoke / feathers
M_SPARK = mat("spark", (1.0, 0.85, 0.30, 1.0), 0.0, 0.05, emission=(1.0,0.90,0.35), emission_strength=22.0)
M_DEBRIS = mat("debris", (0.35, 0.20, 0.10, 1.0), 0.2, 0.60, emission=(0.50,0.20,0.08), emission_strength=1.5)
M_SMOKE = mat("smoke", (0.18, 0.15, 0.15, 1.0), 0.0, 0.85, emission=(0.20,0.18,0.18), emission_strength=0.4, alpha=0.4)
M_FEATHER = mat("feather", (0.85, 0.65, 0.50, 1.0), 0.0, 0.55, emission=(0.55,0.20,0.15), emission_strength=0.6)

# ============ SKY DOME + ASH CLOUDS ============
sky = smooth_sphere("sky", r=85, segs=32, rings=20, loc=(0,0,0), mat_=M_SKY, scale=(1,1,0.65))
sky.scale = (1,1,0.65)

# 10 ash clouds drift
ash_clouds = []
for i in range(10):
    a = (i / 10.0) * math.pi * 2 + random.uniform(-0.1, 0.1)
    rad = random.uniform(25, 35)
    cx, cy = rad*math.cos(a), rad*math.sin(a)
    cz = random.uniform(20, 30)
    c_e = empty(f"ash_e{i}", (cx, cy, cz))
    for j in range(5):
        smooth_sphere(f"ash{i}_{j}", r=random.uniform(2.5, 4.5),
                      loc=(random.uniform(-3,3), random.uniform(-2,2), random.uniform(-0.5,0.5)),
                      parent=c_e, mat_=M_ASH)
    c_e["_phase"] = random.uniform(0, math.pi*2)
    ash_clouds.append(c_e)

# ============ GROUND + CRATER ============
ground = beveled_cube("ground", (70, 70, 0.4), bevel_offset=0.05, loc=(0,0,-0.2), mat_=M_GROUND)

# CRATER central (concave depression with rim)
crater_base = empty("crater_base", loc=(0, 0, 0))
# Crater bowl (inverted dome - using flattened large sphere)
smooth_sphere("crater_bowl", r=8.0, segs=32, rings=20, loc=(0, 0, -3),
              parent=crater_base, mat_=M_CRATER, scale=(1, 1, 0.5))
# Lava pool inside crater
smooth_sphere("crater_lava", r=5.5, segs=28, rings=18, loc=(0, 0, -1.8),
              parent=crater_base, mat_=M_LAVA, scale=(1, 1, 0.15))
# Lava dark spots floating
lava_spots = []
for i in range(8):
    a = (i / 8.0) * math.pi * 2
    rad = random.uniform(0.8, 4.0)
    sp = smooth_sphere(f"lava_spot{i}", r=random.uniform(0.4, 0.9),
                      loc=(rad*math.cos(a), rad*math.sin(a), -1.65),
                      parent=crater_base, mat_=M_LAVA_DARK,
                      scale=(1, 1, 0.2))
    sp["_phase"] = random.uniform(0, math.pi*2)
    lava_spots.append(sp)
# Crater rim (ring of debris uplifted)
for i in range(24):
    a = (i / 24.0) * math.pi * 2
    rim_r = 7.5
    bx, by = rim_r*math.cos(a), rim_r*math.sin(a)
    chunk = beveled_cube(f"rim_chunk{i}", (random.uniform(0.6, 1.2), random.uniform(0.6, 1.2), random.uniform(0.5, 1.0)),
                        loc=(bx, by, 0.5), parent=crater_base, mat_=M_GROUND_BURN)
    chunk.rotation_euler = (math.radians(random.uniform(-20,20)),
                            math.radians(random.uniform(-20,20)),
                            a)

# Burnt ring of ground (just outside rim)
for i in range(40):
    a = random.uniform(0, math.pi*2)
    rad = random.uniform(9, 14)
    bx, by = rad*math.cos(a), rad*math.sin(a)
    burn_patch = smooth_sphere(f"burn{i}", r=random.uniform(0.4, 1.0),
                              loc=(bx, by, 0.05), mat_=M_GROUND_BURN, scale=(1, 1, 0.15))

# Shock wave (expanding ring)
shockwave = cyl("shockwave", r=10.0, depth=0.3, segs=48, loc=(0, 0, 0.3), mat_=M_SHOCKWAVE)
shockwave["_base_r"] = 10.0

# ============ METEOR (falling, in mid-air) ============
meteor_e = empty("meteor", loc=(8, 8, 35))
# Main body irregular (sphere with random sub spheres for chunks)
smooth_sphere("meteor_core", r=2.0, segs=32, rings=20, loc=(0,0,0),
              parent=meteor_e, mat_=M_METEOR)
# Glow layer (outer, brighter)
smooth_sphere("meteor_outer_glow", r=2.2, segs=24, rings=16, loc=(0,0,0),
              parent=meteor_e, mat_=M_METEOR_GLOW, scale=(1.0, 1.0, 1.0))
# Chunks around meteor (5 broken bits)
for i in range(5):
    a = random.uniform(0, math.pi*2)
    smooth_sphere(f"meteor_chunk{i}", r=random.uniform(0.3, 0.6),
                  loc=(random.uniform(-1.5,1.5), random.uniform(-1.5,1.5), random.uniform(-0.5,1.0)),
                  parent=meteor_e, mat_=M_METEOR, scale=(random.uniform(0.8,1.2),
                                                          random.uniform(0.8,1.2),
                                                          random.uniform(0.8,1.2)))
# Plasma trail (long cone behind meteor pointing away from ground)
trail = smooth_cone("meteor_trail", r1=2.5, r2=0.5, depth=15, segs=20,
                    loc=(0, 0, 8.5), parent=meteor_e, mat_=M_PLASMA_TRAIL)
# Trail inner brighter
trail_inner = smooth_cone("meteor_trail_inner", r1=1.5, r2=0.2, depth=12, segs=16,
                          loc=(0, 0, 7.0), parent=meteor_e, mat_=M_METEOR_GLOW)
# Pre-explosion glow halo
smooth_sphere("meteor_halo", r=4.5, loc=(0,0,0), parent=meteor_e,
              mat_=M_PLASMA_TRAIL, scale=(1, 1, 1))

# ============ JUNGLE TREES (15 trees, some burning, some toppled) ============
trees = []
def make_jurassic_tree(name, loc, height=8, burning=False, fallen=False):
    base = empty(name, loc)
    # Trunk 5-seg tapered
    trunk_mat = M_TRUNK_BURNT if burning else M_TRUNK
    for i in range(5):
        r1 = 0.45 - i*0.05
        r2 = 0.40 - i*0.05
        h = height / 5
        if fallen:
            seg = smooth_cone(f"{name}_t{i}", r1=r1, r2=r2, depth=h, segs=14,
                              loc=((i+0.5)*h, 0, 0.4), parent=base, mat_=trunk_mat)
            seg.rotation_euler = (0, math.radians(90), 0)
        else:
            seg = smooth_cone(f"{name}_t{i}", r1=r1, r2=r2, depth=h, segs=14,
                              loc=(0, 0, (i+0.5)*h), parent=base, mat_=trunk_mat)
            seg.rotation_euler = (math.radians(random.uniform(-3,3)),
                                  math.radians(random.uniform(-3,3)), 0)
    # Canopy (top) - cycad/conifer style
    if not fallen:
        top_z = height
        for j in range(7):
            a = (j / 7.0) * math.pi * 2
            frond = empty(f"{name}_fr{j}", (0, 0, top_z), parent=base)
            frond.rotation_euler = (math.radians(-70 + random.uniform(-10,10)), 0, a)
            for k in range(3):
                m_ = M_LEAF_BURN if burning else M_LEAF
                seg = beveled_cube(f"{name}_fr{j}_{k}", (0.20, 0.8, 0.04),
                                   loc=(0, (k+0.5)*0.8, 0), parent=frond, mat_=m_)
                seg.scale = (1 - k*0.15, 1, 1)
                seg.rotation_euler = (math.radians(k*4), 0, 0)
        # Add burning flames on canopy if burning
        if burning:
            for j in range(4):
                a = (j / 4.0) * math.pi * 2
                smooth_cone(f"{name}_flame{j}", r1=0.30, r2=0.02, depth=0.8, segs=10,
                            loc=(0.8*math.cos(a), 0.8*math.sin(a), top_z+0.4),
                            parent=base, mat_=M_FLAME)
                smooth_cone(f"{name}_flame_i{j}", r1=0.18, r2=0.01, depth=0.6, segs=10,
                            loc=(0.8*math.cos(a), 0.8*math.sin(a), top_z+0.5),
                            parent=base, mat_=M_FLAME_INNER)
    return base

tree_positions = [
    (-18, -8, 0, 8, True, False), (18, 10, 0, 9, True, False),
    (-22, 5, 0, 7, False, False), (22, -5, 0, 8, False, False),
    (-15, 18, 0, 7, True, False), (15, -20, 0, 9, True, False),
    (-25, -15, 0, 6, False, True),  # fallen
    (25, 18, 0, 7, False, True),
    (-28, 2, 0, 8, True, False),
    (28, -2, 0, 7, False, False),
    (-12, -25, 0, 7, True, False), (12, 25, 0, 8, True, False),
    (-30, -22, 0, 8, False, True), (30, 22, 0, 7, False, False),
    (-10, 28, 0, 6, True, False),
]
for i, (x, y, z, h, b, fa) in enumerate(tree_positions):
    trees.append(make_jurassic_tree(f"tree{i}", (x, y, z), height=h, burning=b, fallen=fa))

# 30 ferns scattered (small)
ferns = []
for i in range(30):
    a = random.uniform(0, math.pi*2)
    rad = random.uniform(8, 25)
    fx, fy = rad*math.cos(a), rad*math.sin(a)
    fe = empty(f"fern_e{i}", (fx, fy, 0))
    # Stem
    cyl(f"fern_stem{i}", r=0.04, depth=0.4, segs=8, loc=(0,0,0.2),
        parent=fe, mat_=M_FERN)
    # 5 fronds
    for j in range(5):
        a2 = (j / 5.0) * math.pi * 2
        frond = beveled_cube(f"fern_f{i}_{j}", (0.08, 0.50, 0.03),
                            loc=(0.25*math.cos(a2), 0.25*math.sin(a2), 0.45),
                            parent=fe, mat_=M_FERN)
        frond.rotation_euler = (math.radians(-30 + random.uniform(-10,10)),
                                math.radians(20*math.cos(a2)), a2)
    ferns.append(fe)

# ============ T-REX (anatomie complète, running pose) ============
def make_trex(name, loc, facing=0):
    base = empty(name, loc)
    base.rotation_euler = (0, 0, facing)
    # Body (large barrel torso)
    body = smooth_sphere(f"{name}_body", r=0.85, segs=24, rings=16,
                         loc=(0, 0, 1.6), parent=base, mat_=M_TREX,
                         scale=(2.0, 1.2, 1.0))
    # Belly lighter
    smooth_sphere(f"{name}_belly", r=0.7, loc=(0, -0.3, 1.4),
                  parent=base, mat_=M_TREX_BELLY, scale=(1.8, 0.6, 0.8))
    # Neck (curving forward)
    neck_e = empty(f"{name}_neck_e", (1.4, 0, 1.95), parent=base)
    for i in range(3):
        cyl(f"{name}_neck{i}", r=0.35-i*0.05, depth=0.4, segs=12,
            loc=(i*0.30, 0, 0.10*i), parent=neck_e, mat_=M_TREX)
    # Head (large with snout)
    head_e = empty(f"{name}_head_e", (2.5, 0, 2.30), parent=base)
    smooth_sphere(f"{name}_head", r=0.55, segs=24, rings=16, loc=(0, 0, 0),
                  parent=head_e, mat_=M_TREX, scale=(1.6, 1.0, 0.9))
    # Lower jaw
    jaw_e = empty(f"{name}_jaw_e", (0.2, 0, -0.30), parent=head_e)
    beveled_cube(f"{name}_jaw", (0.95, 0.55, 0.22), bevel_offset=0.04,
                 loc=(0, 0, 0), parent=jaw_e, mat_=M_TREX)
    # Mouth open (jaw rotated down)
    jaw_e.rotation_euler = (math.radians(35), 0, 0)
    # Teeth (top + bottom rows, 6 each)
    for i in range(6):
        tx = (i - 2.5) * 0.16
        # Top
        smooth_cone(f"{name}_tooth_top{i}", r1=0.04, r2=0.005, depth=0.18, segs=8,
                    loc=(tx + 0.3, -0.20, -0.20), parent=head_e, mat_=M_TEETH)
        # Bottom
        smooth_cone(f"{name}_tooth_bot{i}", r1=0.04, r2=0.005, depth=0.18, segs=8,
                    loc=(tx + 0.3, -0.20, -0.55), parent=head_e, mat_=M_TEETH)
    # Eyes (red angry)
    for side in (-1, 1):
        smooth_sphere(f"{name}_eye_{side}", r=0.10,
                      loc=(0.30, side*0.30, 0.20), parent=head_e, mat_=M_EYE)
        smooth_sphere(f"{name}_pup_{side}", r=0.04,
                      loc=(0.38, side*0.30, 0.20), parent=head_e, mat_=M_BLOOD)
    # Brow ridges
    for side in (-1, 1):
        beveled_cube(f"{name}_brow_{side}", (0.20, 0.10, 0.08),
                     loc=(0.40, side*0.30, 0.35), parent=head_e, mat_=M_TREX)

    # Tail (5-seg curving back)
    tail_e = empty(f"{name}_tail_e", (-1.5, 0, 1.6), parent=base)
    for i in range(5):
        cyl(f"{name}_tail{i}", r=0.35-i*0.05, depth=0.55, segs=14,
            loc=(-i*0.55, 0, -i*0.05), parent=tail_e, mat_=M_TREX)

    # LEGS (powerful 2-legs running, alternating - one forward, one back)
    legs_e = []
    for side_idx, side in enumerate((-1, 1)):
        leg_e = empty(f"{name}_leg_e{side_idx}", (-0.1, side*0.45, 1.4), parent=base)
        legs_e.append(leg_e)
        # Thigh
        beveled_cube(f"{name}_thigh{side_idx}", (0.30, 0.30, 0.85),
                     loc=(0, 0, -0.45), parent=leg_e, mat_=M_TREX)
        # Knee
        knee_e = empty(f"{name}_knee{side_idx}", (0, 0, -0.92), parent=leg_e)
        # Shin
        beveled_cube(f"{name}_shin{side_idx}", (0.25, 0.25, 0.75),
                     loc=(0, 0, -0.4), parent=knee_e, mat_=M_TREX)
        # Foot
        foot = beveled_cube(f"{name}_foot{side_idx}", (0.30, 0.50, 0.15),
                            loc=(0, 0.10, -0.85), parent=knee_e, mat_=M_TREX_BELLY)
        # 3 toe claws
        for j in range(3):
            smooth_cone(f"{name}_claw{side_idx}_{j}", r1=0.04, r2=0.01, depth=0.12, segs=8,
                        loc=((j-1)*0.08, 0.30, -0.85), parent=knee_e, mat_=M_CLAW)
    # Tiny arms (signature T-Rex small forelimbs)
    for side_idx, side in enumerate((-1, 1)):
        arm_e = empty(f"{name}_arm{side_idx}", (0.6, side*0.50, 1.85), parent=base)
        cyl(f"{name}_arm_up{side_idx}", r=0.10, depth=0.30, segs=10,
            loc=(0, 0, -0.15), parent=arm_e, mat_=M_TREX)
        cyl(f"{name}_arm_low{side_idx}", r=0.08, depth=0.25, segs=10,
            loc=(0, 0, -0.45), parent=arm_e, mat_=M_TREX)
        # 2 claws
        for j in range(2):
            smooth_cone(f"{name}_clawA{side_idx}_{j}", r1=0.03, r2=0.005, depth=0.10, segs=8,
                        loc=(0, (j-0.5)*0.08, -0.62), parent=arm_e, mat_=M_CLAW)
    return {"root": base, "head_e": head_e, "tail_e": tail_e, "legs_e": legs_e,
            "jaw_e": jaw_e}

trex = make_trex("trex", (-8, 5, 0), facing=math.radians(45))

# ============ TRICERATOPS ============
def make_trice(name, loc, facing=0):
    base = empty(name, loc)
    base.rotation_euler = (0, 0, facing)
    # Body large
    smooth_sphere(f"{name}_body", r=0.95, segs=22, rings=16,
                  loc=(0, 0, 1.30), parent=base, mat_=M_TRICE,
                  scale=(2.2, 1.4, 1.1))
    # Head with FRILL
    head_e = empty(f"{name}_head_e", (1.8, 0, 1.30), parent=base)
    # Skull
    smooth_sphere(f"{name}_skull", r=0.50, segs=20, rings=14,
                  loc=(0, 0, 0), parent=head_e, mat_=M_TRICE,
                  scale=(1.4, 0.9, 0.9))
    # FRILL (large bony shield) - rounded back disc
    frill = smooth_sphere(f"{name}_frill", r=0.85, segs=24, rings=16,
                          loc=(-0.30, 0, 0.15), parent=head_e, mat_=M_TRICE_FRILL,
                          scale=(0.3, 1.2, 1.1))
    # Frill knobs (8 spikes around edge)
    for i in range(8):
        a = (i / 8.0) * math.pi
        smooth_cone(f"{name}_frill_spike{i}", r1=0.08, r2=0.01, depth=0.25, segs=8,
                    loc=(-0.45, 0.95*math.cos(a), 0.20 + 0.95*math.sin(a)),
                    parent=head_e, mat_=M_TRICE_FRILL)
    # Beak (parrot-like)
    smooth_cone(f"{name}_beak", r1=0.20, r2=0.05, depth=0.30, segs=10,
                loc=(0.55, 0, -0.10), parent=head_e, mat_=M_TRICE_FRILL)
    # 3 HORNS (signature triceratops!)
    # Nose horn (small)
    smooth_cone(f"{name}_nose_horn", r1=0.10, r2=0.02, depth=0.30, segs=10,
                loc=(0.40, 0, 0.20), parent=head_e, mat_=M_CLAW)
    # 2 brow horns (large)
    for side in (-1, 1):
        horn = smooth_cone(f"{name}_brow_horn_{side}", r1=0.12, r2=0.02, depth=0.70, segs=10,
                          loc=(0.20, side*0.30, 0.35), parent=head_e, mat_=M_CLAW)
        horn.rotation_euler = (math.radians(20), 0, math.radians(side*15))
    # Eyes
    for side in (-1, 1):
        smooth_sphere(f"{name}_eye_{side}", r=0.07,
                      loc=(0.25, side*0.30, 0.15), parent=head_e, mat_=M_EYE)

    # 4 LEGS (sturdy)
    legs_e = []
    for x_idx, x in enumerate((-1, 1)):
        for y_idx, y in enumerate((-1, 1)):
            leg_e = empty(f"{name}_leg_{x_idx}{y_idx}", (x*0.75, y*0.55, 1.1), parent=base)
            legs_e.append(leg_e)
            # Upper
            cyl(f"{name}_upleg_{x_idx}{y_idx}", r=0.18, depth=0.5, segs=12,
                loc=(0,0,-0.25), parent=leg_e, mat_=M_TRICE)
            # Lower
            cyl(f"{name}_lowleg_{x_idx}{y_idx}", r=0.16, depth=0.5, segs=12,
                loc=(0,0,-0.75), parent=leg_e, mat_=M_TRICE)
            # Foot
            beveled_cube(f"{name}_foot_{x_idx}{y_idx}", (0.30, 0.30, 0.12),
                         loc=(0,0,-1.06), parent=leg_e, mat_=M_TRICE)
    # Tail (3-seg)
    tail_e = empty(f"{name}_tail_e", (-1.4, 0, 1.3), parent=base)
    for i in range(3):
        cyl(f"{name}_tail{i}", r=0.20-i*0.04, depth=0.50, segs=10,
            loc=(-i*0.45, 0, -i*0.05), parent=tail_e, mat_=M_TRICE)
    return {"root": base, "head_e": head_e, "tail_e": tail_e, "legs_e": legs_e}

trice = make_trice("trice", (10, -8, 0), facing=math.radians(-120))

# ============ 2 RAPTORS (smaller, fast) ============
def make_raptor(name, loc, facing=0):
    base = empty(name, loc)
    base.rotation_euler = (0, 0, facing)
    # Body slim
    smooth_sphere(f"{name}_body", r=0.40, segs=20, rings=14,
                  loc=(0, 0, 0.95), parent=base, mat_=M_RAPTOR,
                  scale=(2.0, 1.0, 1.0))
    # Stripe pattern (3 stripes on back)
    for i in range(3):
        beveled_cube(f"{name}_stripe{i}", (0.20, 0.04, 0.10),
                     loc=((i-1)*0.3, 0, 1.15), parent=base, mat_=M_RAPTOR_STRIPE)
    # Neck
    neck_e = empty(f"{name}_neck_e", (0.85, 0, 1.10), parent=base)
    for i in range(3):
        cyl(f"{name}_neck{i}", r=0.18-i*0.02, depth=0.22, segs=10,
            loc=(i*0.20, 0, 0.05*i), parent=neck_e, mat_=M_RAPTOR)
    # Head (long snout)
    head_e = empty(f"{name}_head_e", (1.65, 0, 1.20), parent=base)
    smooth_sphere(f"{name}_head", r=0.25, segs=20, rings=14, loc=(0, 0, 0),
                  parent=head_e, mat_=M_RAPTOR, scale=(1.7, 0.9, 0.8))
    # Jaw open
    smooth_sphere(f"{name}_jaw", r=0.18, segs=18, rings=12,
                  loc=(0.10, 0, -0.18), parent=head_e, mat_=M_RAPTOR, scale=(1.6, 0.8, 0.5))
    # Teeth (4 each row)
    for i in range(4):
        smooth_cone(f"{name}_tooth_t{i}", r1=0.025, r2=0.005, depth=0.10, segs=6,
                    loc=(0.10 + (i-1.5)*0.10, -0.10, -0.05), parent=head_e, mat_=M_TEETH)
        smooth_cone(f"{name}_tooth_b{i}", r1=0.025, r2=0.005, depth=0.10, segs=6,
                    loc=(0.10 + (i-1.5)*0.10, -0.10, -0.25), parent=head_e, mat_=M_TEETH)
    # Eyes
    for side in (-1, 1):
        smooth_sphere(f"{name}_eye_{side}", r=0.05,
                      loc=(0.18, side*0.15, 0.10), parent=head_e, mat_=M_EYE)
    # Tail (long stiff - 5 segs)
    tail_e = empty(f"{name}_tail_e", (-0.85, 0, 0.95), parent=base)
    for i in range(5):
        cyl(f"{name}_tail{i}", r=0.15-i*0.025, depth=0.35, segs=10,
            loc=(-i*0.35, 0, 0), parent=tail_e, mat_=M_RAPTOR)
    # 2 hind legs (running)
    legs_e = []
    for side_idx, side in enumerate((-1, 1)):
        leg_e = empty(f"{name}_leg_e{side_idx}", (0, side*0.20, 0.85), parent=base)
        legs_e.append(leg_e)
        cyl(f"{name}_thigh{side_idx}", r=0.13, depth=0.45, segs=10,
            loc=(0,0,-0.22), parent=leg_e, mat_=M_RAPTOR)
        knee_e = empty(f"{name}_knee{side_idx}", (0,0,-0.45), parent=leg_e)
        cyl(f"{name}_shin{side_idx}", r=0.10, depth=0.40, segs=10,
            loc=(0,0,-0.20), parent=knee_e, mat_=M_RAPTOR)
        # Foot with signature sickle claw
        beveled_cube(f"{name}_foot{side_idx}", (0.15, 0.30, 0.08),
                     loc=(0, 0.10, -0.45), parent=knee_e, mat_=M_RAPTOR_STRIPE)
        # Sickle claw (signature!)
        sickle = smooth_cone(f"{name}_sickle{side_idx}", r1=0.05, r2=0.005, depth=0.20, segs=8,
                            loc=(0, 0.18, -0.50), parent=knee_e, mat_=M_CLAW)
        sickle.rotation_euler = (math.radians(70), 0, 0)
    # Tiny arms (2)
    for side_idx, side in enumerate((-1, 1)):
        arm_e = empty(f"{name}_arm{side_idx}", (0.4, side*0.30, 1.0), parent=base)
        cyl(f"{name}_arm{side_idx}", r=0.07, depth=0.25, segs=8,
            loc=(0,0,-0.12), parent=arm_e, mat_=M_RAPTOR)
        cyl(f"{name}_fore{side_idx}", r=0.06, depth=0.20, segs=8,
            loc=(0,0,-0.35), parent=arm_e, mat_=M_RAPTOR)
        # 3 claws
        for j in range(3):
            smooth_cone(f"{name}_handclaw{side_idx}_{j}", r1=0.03, r2=0.005, depth=0.08, segs=6,
                        loc=(0, (j-1)*0.05, -0.50), parent=arm_e, mat_=M_CLAW)
    return {"root": base, "head_e": head_e, "tail_e": tail_e, "legs_e": legs_e}

raptor1 = make_raptor("raptor1", (-3, -12, 0), facing=math.radians(60))
raptor2 = make_raptor("raptor2", (4, 12, 0), facing=math.radians(-130))

# ============ 8 PTERODACTYLS flying ============
pteros = []
for i in range(8):
    a = (i / 8.0) * math.pi * 2 + random.uniform(-0.2, 0.2)
    rad = random.uniform(12, 20)
    px, py = rad*math.cos(a), rad*math.sin(a)
    pz = random.uniform(10, 18)
    pte = empty(f"ptero_e{i}", (px, py, pz))
    pte.rotation_euler = (0, 0, a + math.pi/2)
    # Body slim
    smooth_sphere(f"ptero_b{i}", r=0.30, segs=18, rings=12,
                  loc=(0,0,0), parent=pte, mat_=M_PTERO, scale=(2.0, 0.9, 0.9))
    # Head with long beak
    smooth_sphere(f"ptero_h{i}", r=0.20, loc=(0.50, 0, 0.05),
                  parent=pte, mat_=M_PTERO, scale=(1.5, 0.9, 0.9))
    # Long pointed beak
    smooth_cone(f"ptero_beak{i}", r1=0.08, r2=0.005, depth=0.55, segs=10,
                loc=(0.95, 0, 0.05), parent=pte, mat_=M_PTERO)
    # CREST (signature pterodactyl)
    crest = beveled_cube(f"ptero_crest{i}", (0.04, 0.30, 0.40),
                        bevel_offset=0.02,
                        loc=(0.55, 0, 0.30), parent=pte, mat_=M_PTERO_CREST)
    crest.rotation_euler = (math.radians(-25), 0, 0)
    # Eyes
    for side in (-1, 1):
        smooth_sphere(f"ptero_eye{i}_{side}", r=0.04,
                      loc=(0.55, side*0.10, 0.10), parent=pte, mat_=M_EYE)
    # Wings (huge membrane wings)
    ptero_wings = []
    for side_idx, side in enumerate((-1, 1)):
        # Wing shoulder
        w_sh = empty(f"ptero_wsh{i}_{side_idx}", (0, side*0.20, 0.05), parent=pte)
        # Main wing arm
        cyl(f"ptero_warm{i}_{side_idx}", r=0.05, depth=0.85, segs=8,
            loc=(0, side*0.42, 0), parent=w_sh, mat_=M_PTERO)
        # Wing fingers (4 long bones)
        wf_e = empty(f"ptero_wf{i}_{side_idx}", (0, side*0.85, 0), parent=w_sh)
        for j in range(4):
            angle = (j / 4.0) * math.pi/2 - math.pi/8
            bone = cyl(f"ptero_wbone{i}_{side_idx}_{j}", r=0.04, depth=1.2-j*0.15, segs=6,
                      loc=(0, (1.2-j*0.15)/2 * math.cos(angle),
                           (1.2-j*0.15)/2 * math.sin(angle) * side),
                      parent=wf_e, mat_=M_PTERO)
            bone.rotation_euler = (math.radians(side*math.degrees(angle)), 0, 0)
        # Membrane (large flat triangle)
        mem = beveled_cube(f"ptero_mem{i}_{side_idx}", (0.06, 1.6, 0.04),
                          bevel_offset=0.02,
                          loc=(0, side*0.8, 0), parent=w_sh, mat_=M_PTERO_MEMBRANE)
        # Wider trailing edge
        mem2 = beveled_cube(f"ptero_mem2{i}_{side_idx}", (0.06, 1.2, 1.0),
                           bevel_offset=0.04,
                           loc=(-0.4, side*0.6, 0), parent=w_sh, mat_=M_PTERO_MEMBRANE)
        ptero_wings.append((w_sh, side))
    # Legs short tucked
    for side in (-1, 1):
        cyl(f"ptero_leg{i}_{side}", r=0.04, depth=0.3, segs=8,
            loc=(-0.3, side*0.12, -0.15), parent=pte, mat_=M_PTERO)
    # Tail short
    smooth_cone(f"ptero_tail{i}", r1=0.08, r2=0.01, depth=0.30, segs=8,
                loc=(-0.7, 0, 0), parent=pte, mat_=M_PTERO)
    pteros.append({"e": pte, "wings": ptero_wings, "phase": random.uniform(0, math.pi*2),
                   "orbit_radius": rad, "orbit_speed": random.uniform(0.4, 0.7),
                   "orbit_phase": a, "base_z": pz})

# ============ 50 DEBRIS (meteor fragments + rock) flying ============
debris = []
for i in range(50):
    dx = random.uniform(-30, 30)
    dy = random.uniform(-30, 30)
    dz = random.uniform(3, 22)
    sz = random.uniform(0.18, 0.45)
    m_ = M_DEBRIS if random.random() < 0.6 else M_METEOR
    d = beveled_cube(f"debris{i}", (sz, sz, sz),
                     loc=(dx, dy, dz), mat_=m_)
    d.rotation_euler = (random.uniform(0,math.pi*2),
                        random.uniform(0,math.pi*2),
                        random.uniform(0,math.pi*2))
    d["_phase"] = random.uniform(0, math.pi*2)
    d["_speed"] = random.uniform(0.5, 1.5)
    d["_base_x"] = dx; d["_base_y"] = dy; d["_base_z"] = dz
    debris.append(d)

# ============ 100 SPARKS (etincelles) ============
sparks = []
for i in range(100):
    # Mostly near crater + meteor path
    if i < 50:
        # Near crater
        a = random.uniform(0, math.pi*2)
        rad = random.uniform(0, 8)
        sx = rad*math.cos(a) + random.uniform(-1,1)
        sy = rad*math.sin(a) + random.uniform(-1,1)
        sz = random.uniform(0.5, 6)
    else:
        # Scattered
        sx = random.uniform(-25, 25)
        sy = random.uniform(-25, 25)
        sz = random.uniform(0.3, 12)
    sk = smooth_sphere(f"spark{i}", r=random.uniform(0.05, 0.12), segs=8, rings=6,
                      loc=(sx, sy, sz), mat_=M_SPARK)
    sk["_phase"] = random.uniform(0, math.pi*2)
    sk["_base_x"] = sx; sk["_base_y"] = sy; sk["_base_z"] = sz
    sk["_speed"] = random.uniform(0.8, 2.5)
    sparks.append(sk)

# ============ 20 SMOKE COLUMNS ============
smokes = []
for i in range(20):
    a = random.uniform(0, math.pi*2)
    rad = random.uniform(2, 22)
    sx, sy = rad*math.cos(a), rad*math.sin(a)
    sz = random.uniform(2, 14)
    sm = smooth_sphere(f"smoke{i}", r=random.uniform(1.0, 2.2),
                      loc=(sx, sy, sz), mat_=M_SMOKE, scale=(1, 1, 1.2))
    sm["_phase"] = random.uniform(0, math.pi*2)
    sm["_base_x"] = sx; sm["_base_y"] = sy; sm["_base_z"] = sz
    smokes.append(sm)

# ============ 15 FEATHERS/BLOOD particles ============
feathers = []
for i in range(15):
    fx = random.uniform(-15, 15)
    fy = random.uniform(-15, 15)
    fz = random.uniform(2, 8)
    f_obj = beveled_cube(f"feather{i}", (0.05, 0.18, 0.02),
                        loc=(fx, fy, fz), mat_=M_FEATHER)
    f_obj.rotation_euler = (random.uniform(0,math.pi*2),
                            random.uniform(0,math.pi*2),
                            random.uniform(0,math.pi*2))
    f_obj["_phase"] = random.uniform(0, math.pi*2)
    f_obj["_base_x"] = fx; f_obj["_base_y"] = fy; f_obj["_base_z"] = fz
    feathers.append(f_obj)

# ============ ANIMATION ============
fps = 30; duration_s = 6; total_frames = fps * duration_s

# Meteor falling (Z descent + spiral)
for f in range(1, total_frames + 1, 2):
    t = (f - 1) / fps
    # Start at (8,8,35), descend to ~(0,0,5) by end... but loop for continuous
    progress = (t * 0.3) % 1.0  # 1 cycle in ~3.3s
    z = 35 - progress * 30
    x = 8 - progress * 8 + math.sin(t * 4.0) * 1.5
    y = 8 - progress * 8 + math.cos(t * 4.0) * 1.5
    meteor_e.location = (x, y, max(5, z))
    meteor_e.rotation_euler = (t * 2.0, t * 1.5, t * 1.0)
    meteor_e.keyframe_insert("location", frame=f)
    meteor_e.keyframe_insert("rotation_euler", frame=f)
    # Meteor glow scale pulse
    s_glow = 1 + math.sin(t * 8.0) * 0.15
    trail.scale = (s_glow, s_glow, 1)
    trail.keyframe_insert("scale", frame=f)

# Shockwave expansion
for f in range(1, total_frames + 1, 2):
    t = (f - 1) / fps
    cycle = (t * 0.4) % 1.0
    s = 0.3 + cycle * 2.5
    shockwave.scale = (s, s, 0.3)
    shockwave.keyframe_insert("scale", frame=f)

# Lava spots pulse
for sp in lava_spots:
    phase = sp["_phase"]
    for f in range(1, total_frames + 1, 4):
        t = (f - 1) / fps
        s = 1 + math.sin(t * 2.0 + phase) * 0.20
        sp.scale = (s, s, 0.2)
        sp.keyframe_insert("scale", frame=f)

# T-Rex running (body bob + leg cycle + tail wave + jaw snap + head turn)
def animate_dino_run(dino, leg_speed=4.0, body_speed=4.0, tail_speed=2.5):
    legs = dino["legs_e"]
    tail_e = dino["tail_e"]
    head_e = dino.get("head_e")
    root = dino["root"]
    base_z = root.location.z
    for f in range(1, total_frames + 1, 3):
        t = (f - 1) / fps
        # Body bob
        root.location.z = base_z + abs(math.sin(t * body_speed)) * 0.15
        root.keyframe_insert("location", frame=f)
        # Legs alternate
        for li, leg in enumerate(legs):
            phase_offset = li * math.pi if len(legs) == 2 else (li * math.pi/2)
            leg.rotation_euler = (math.sin(t * leg_speed + phase_offset) * math.radians(40), 0, 0)
            leg.keyframe_insert("rotation_euler", frame=f)
        # Tail wave
        tail_e.rotation_euler = (0, math.sin(t * tail_speed) * math.radians(10),
                                 math.sin(t * tail_speed + 0.3) * math.radians(20))
        tail_e.keyframe_insert("rotation_euler", frame=f)
        # Head turn (looking back/around)
        if head_e:
            head_e.rotation_euler = (math.sin(t * 1.5) * math.radians(5),
                                     0,
                                     math.sin(t * 1.0) * math.radians(20))
            head_e.keyframe_insert("rotation_euler", frame=f)

animate_dino_run(trex, leg_speed=4.5, body_speed=4.5, tail_speed=2.5)
animate_dino_run(trice, leg_speed=3.0, body_speed=3.0, tail_speed=2.0)
animate_dino_run(raptor1, leg_speed=6.0, body_speed=6.0, tail_speed=3.5)
animate_dino_run(raptor2, leg_speed=6.0, body_speed=6.0, tail_speed=3.5)

# T-Rex jaw snap
for f in range(1, total_frames + 1, 4):
    t = (f - 1) / fps
    trex["jaw_e"].rotation_euler = (math.radians(35) + math.sin(t * 5.0) * math.radians(10), 0, 0)
    trex["jaw_e"].keyframe_insert("rotation_euler", frame=f)

# Pterodactyls flap + orbit + bob
for p in pteros:
    phase = p["phase"]
    rad = p["orbit_radius"]
    speed = p["orbit_speed"]
    base_phase = p["orbit_phase"]
    base_z = p["base_z"]
    for f in range(1, total_frames + 1, 3):
        t = (f - 1) / fps
        flap = math.sin(t * 4.5 + phase) * math.radians(50)
        for w_sh, side in p["wings"]:
            w_sh.rotation_euler = (side * flap, 0, 0)
            w_sh.keyframe_insert("rotation_euler", frame=f)
        a = base_phase + speed * t
        x = rad * math.cos(a)
        y = rad * math.sin(a)
        z = base_z + math.sin(t * 1.5 + phase) * 1.0
        p["e"].location = (x, y, z)
        p["e"].rotation_euler = (0, 0, a + math.pi/2)
        p["e"].keyframe_insert("location", frame=f)
        p["e"].keyframe_insert("rotation_euler", frame=f)

# Debris fall + spin
for d in debris:
    phase = d["_phase"]; speed = d["_speed"]
    bx, by, bz = d["_base_x"], d["_base_y"], d["_base_z"]
    for f in range(1, total_frames + 1, 4):
        t = (f - 1) / fps
        z = bz - (t * speed * 2.0) % 18.0
        x = bx + math.sin(t * 0.5 + phase) * 0.4
        y = by + math.cos(t * 0.5 + phase) * 0.4
        d.location = (x, y, max(0.1, z))
        d.rotation_euler = (phase + t * 2.5, phase + t * 1.8, phase + t * 2.0)
        d.keyframe_insert("location", frame=f)
        d.keyframe_insert("rotation_euler", frame=f)

# Sparks scatter + scale pulse
for sk in sparks:
    phase = sk["_phase"]; speed = sk["_speed"]
    bx, by, bz = sk["_base_x"], sk["_base_y"], sk["_base_z"]
    for f in range(1, total_frames + 1, 3):
        t = (f - 1) / fps
        cycle = (t * speed) % 1.2
        x = bx + math.cos(t * 6.0 + phase) * 0.7 * cycle
        y = by + math.sin(t * 6.0 + phase) * 0.7 * cycle
        z = bz + cycle * 1.0
        s = max(0.1, 1 - cycle * 0.6) * (1 + math.sin(t * 9.0 + phase) * 0.3)
        sk.location = (x, y, z)
        sk.scale = (s, s, s)
        sk.keyframe_insert("location", frame=f)
        sk.keyframe_insert("scale", frame=f)

# Smoke billow rise + drift
for sm in smokes:
    phase = sm["_phase"]
    bx, by, bz = sm["_base_x"], sm["_base_y"], sm["_base_z"]
    for f in range(1, total_frames + 1, 6):
        t = (f - 1) / fps
        x = bx + math.sin(t * 0.3 + phase) * 0.8
        y = by + math.cos(t * 0.25 + phase) * 0.8
        z = bz + (t * 0.5) % 5.0
        s = 1 + math.sin(t * 0.6 + phase) * 0.2
        sm.location = (x, y, z)
        sm.scale = (s, s, s*1.2)
        sm.keyframe_insert("location", frame=f)
        sm.keyframe_insert("scale", frame=f)

# Feathers tumble drift
for ft in feathers:
    phase = ft["_phase"]
    bx, by, bz = ft["_base_x"], ft["_base_y"], ft["_base_z"]
    for f in range(1, total_frames + 1, 4):
        t = (f - 1) / fps
        x = bx + math.sin(t * 0.8 + phase) * 1.2
        y = by + math.cos(t * 0.7 + phase) * 1.2
        z = bz - (t * 0.4) % 5.0
        ft.location = (x, y, max(0.2, z))
        ft.rotation_euler = (phase + t * 1.5, phase + t * 1.2, phase + t * 1.8)
        ft.keyframe_insert("location", frame=f)
        ft.keyframe_insert("rotation_euler", frame=f)

# Ash clouds drift + scale
for ac in ash_clouds:
    phase = ac["_phase"]
    bx, by = ac.location.x, ac.location.y
    for f in range(1, total_frames + 1, 8):
        t = (f - 1) / fps
        ac.location = (bx + math.sin(t * 0.3 + phase) * 0.7,
                       by + math.cos(t * 0.25 + phase) * 0.6,
                       ac.location.z)
        s = 1 + math.sin(t * 0.6 + phase) * 0.1
        ac.scale = (s, s, s)
        ac.keyframe_insert("location", frame=f)
        ac.keyframe_insert("scale", frame=f)

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
out_glb = os.path.join(out_dir, "pbr_meteor_proc.glb")

bpy.ops.object.select_all(action='SELECT')
bpy.ops.export_scene.gltf(
    filepath=out_glb, export_format='GLB',
    export_animations=True, export_apply=False, export_yup=True, use_selection=False,
)
size_mb = os.path.getsize(out_glb) / (1024 * 1024)
print(f"[proc_meteor_impact_crater_dinosaurs] DONE → {out_glb} ({size_mb:.2f} MB)")
print("[proc_meteor_impact_crater_dinosaurs] Meteor falling + crater + lava + shockwave + T-Rex + Triceratops + 2 Raptors + 8 Pterodactyls + 15 trees burning/fallen + 30 ferns + 50 debris + 100 sparks + 20 smoke + 15 feathers + ash clouds")
