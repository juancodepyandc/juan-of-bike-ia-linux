"""
proc_samurai_duel_sakura.py — 189e procédural AuroraIA (53e qualité)
Duel samouraïs sous cerisiers sakura + temple shinto + Mt Fuji + grue
Construction smooth (bevels + smooth shading + multi-axis animations + anatomie articulée hiérarchique)
"""
import bpy, bmesh, math, random, os, sys

random.seed(0x5A11189)

# ============ HELPERS ============
def reset():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    for c in (bpy.data.meshes, bpy.data.materials, bpy.data.objects,
              bpy.data.cameras, bpy.data.lights, bpy.data.collections):
        for x in list(c):
            try: c.remove(x)
            except: pass

def mat(name, base=(0.8,0.8,0.8,1.0), metallic=0.0, roughness=0.5, emission=None, emission_strength=0.0, alpha=1.0):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
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
    bm.to_mesh(me); bm.free()
    smooth_shade(me)
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

def smooth_sphere(name, r=1.0, segs=32, rings=20, loc=(0,0,0), parent=None, mat_=None, scale=(1,1,1)):
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=segs, v_segments=rings, radius=r)
    if scale != (1,1,1):
        bmesh.ops.scale(bm, vec=scale, verts=bm.verts)
    return make_obj(name, bm, loc, parent, mat_)

def smooth_cone(name, r1, r2, depth, segs=24, loc=(0,0,0), parent=None, mat_=None):
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, segments=segs, radius1=r1, radius2=r2, depth=depth, cap_ends=True)
    return make_obj(name, bm, loc, parent, mat_)

def cyl(name, r, depth, segs=20, loc=(0,0,0), parent=None, mat_=None):
    return smooth_cone(name, r, r, depth, segs, loc, parent, mat_)

def kf(obj, frame, attr, val):
    if attr == "loc":
        obj.location = val; obj.keyframe_insert("location", frame=frame)
    elif attr == "rot":
        obj.rotation_euler = val; obj.keyframe_insert("rotation_euler", frame=frame)
    elif attr == "scale":
        obj.scale = val; obj.keyframe_insert("scale", frame=frame)

def empty(name, loc=(0,0,0), parent=None):
    e = bpy.data.objects.new(name, None)
    bpy.context.collection.objects.link(e)
    e.location = loc
    if parent: e.parent = parent
    return e

# ============ SCENE ============
reset()
scene = bpy.context.scene
scene.frame_start = 1
scene.frame_end = 180  # 6s @ 30fps
scene.render.fps = 30

# Materials
M_SKY = mat("sky", (0.95, 0.85, 0.70, 1.0), 0.0, 0.7, emission=(0.95, 0.85, 0.70), emission_strength=1.4)
M_SUN = mat("sun", (1.0, 0.95, 0.75, 1.0), 0.0, 0.3, emission=(1.0, 0.92, 0.65), emission_strength=18.0)
M_MOUNTAIN = mat("fuji", (0.55, 0.55, 0.65, 1.0), 0.0, 0.8)
M_SNOW = mat("snow", (1.0, 1.0, 1.0, 1.0), 0.0, 0.4, emission=(0.95,0.95,1.0), emission_strength=0.6)
M_GROUND = mat("ground", (0.42, 0.55, 0.32, 1.0), 0.0, 0.85)
M_STONE = mat("stone", (0.55, 0.52, 0.48, 1.0), 0.0, 0.85)
M_TEMPLE_RED = mat("temple_red", (0.75, 0.18, 0.15, 1.0), 0.0, 0.6, emission=(0.65,0.15,0.12), emission_strength=0.3)
M_TEMPLE_WOOD = mat("temple_wood", (0.45, 0.28, 0.18, 1.0), 0.0, 0.7)
M_ROOF = mat("roof", (0.25, 0.20, 0.18, 1.0), 0.2, 0.55)
M_GOLD = mat("gold", (1.0, 0.82, 0.35, 1.0), 0.95, 0.25, emission=(0.95,0.78,0.30), emission_strength=0.6)

M_TRUNK = mat("trunk", (0.30, 0.20, 0.15, 1.0), 0.0, 0.85)
M_SAKURA_PINK = mat("sakura_pink", (1.0, 0.65, 0.78, 1.0), 0.0, 0.6, emission=(1.0,0.60,0.75), emission_strength=0.7)
M_SAKURA_DEEP = mat("sakura_deep", (1.0, 0.50, 0.65, 1.0), 0.0, 0.55, emission=(1.0,0.45,0.60), emission_strength=0.9)
M_PETAL = mat("petal", (1.0, 0.70, 0.82, 1.0), 0.0, 0.5, emission=(1.0,0.65,0.78), emission_strength=1.2)

M_ARMOR_BLACK = mat("armor_black", (0.10, 0.10, 0.13, 1.0), 0.65, 0.35, emission=(0.05,0.05,0.08), emission_strength=0.2)
M_ARMOR_RED = mat("armor_red", (0.55, 0.10, 0.10, 1.0), 0.6, 0.35, emission=(0.45,0.08,0.08), emission_strength=0.35)
M_ARMOR_BLUE = mat("armor_blue", (0.10, 0.20, 0.55, 1.0), 0.6, 0.35, emission=(0.08,0.18,0.50), emission_strength=0.35)
M_ARMOR_GOLD = mat("armor_gold", (0.95, 0.75, 0.32, 1.0), 0.92, 0.30, emission=(0.85,0.65,0.25), emission_strength=0.5)
M_SKIN = mat("skin", (0.95, 0.80, 0.68, 1.0), 0.0, 0.55, emission=(0.85,0.70,0.58), emission_strength=0.15)
M_KATANA = mat("katana", (0.92, 0.95, 0.98, 1.0), 0.98, 0.05, emission=(0.95,0.95,1.0), emission_strength=0.8)
M_KATANA_HILT = mat("hilt", (0.05, 0.05, 0.08, 1.0), 0.0, 0.7)

M_BRIDGE = mat("bridge", (0.85, 0.15, 0.12, 1.0), 0.0, 0.55, emission=(0.75,0.12,0.10), emission_strength=0.4)
M_LANTERN = mat("lantern", (1.0, 0.45, 0.20, 1.0), 0.0, 0.5, emission=(1.0,0.55,0.25), emission_strength=8.0)
M_LANTERN_FRAME = mat("lantern_frame", (0.05, 0.05, 0.05, 1.0), 0.3, 0.6)

M_CRANE_WHITE = mat("crane", (0.98, 0.98, 1.0, 1.0), 0.0, 0.45, emission=(0.95,0.95,1.0), emission_strength=0.4)
M_CRANE_RED = mat("crane_red", (0.85, 0.15, 0.10, 1.0), 0.0, 0.45, emission=(0.75,0.12,0.08), emission_strength=0.6)
M_CRANE_BLACK = mat("crane_black", (0.10, 0.10, 0.10, 1.0), 0.0, 0.7)

M_BUDDHA = mat("buddha", (0.92, 0.75, 0.35, 1.0), 0.85, 0.30, emission=(0.85,0.68,0.30), emission_strength=1.4)
M_WATER = mat("water", (0.30, 0.55, 0.65, 0.7), 0.4, 0.10, emission=(0.40,0.65,0.75), emission_strength=0.6, alpha=0.65)
M_LOTUS = mat("lotus", (1.0, 0.85, 0.92, 1.0), 0.0, 0.5, emission=(1.0,0.80,0.90), emission_strength=0.8)
M_LOTUS_GREEN = mat("lotus_leaf", (0.25, 0.55, 0.30, 1.0), 0.0, 0.55, emission=(0.20,0.50,0.25), emission_strength=0.25)

# ============ SKY DOME ============
sky = smooth_sphere("sky_dome", r=80.0, segs=32, rings=20, loc=(0,0,0), mat_=M_SKY, scale=(1,1,0.55))
sky.scale = (1,1,0.55)

# Sun
sun = smooth_sphere("sun_disc", r=4.5, loc=(-22, 35, 22), mat_=M_SUN)

# ============ MT FUJI (background) ============
fuji = smooth_cone("fuji", r1=18.0, r2=2.5, depth=14.0, segs=32, loc=(0, 38, 7.0), mat_=M_MOUNTAIN)
# Snow cap on fuji
fuji_snow = smooth_cone("fuji_snow", r1=4.5, r2=2.5, depth=2.6, segs=32, loc=(0, 38, 13.5), mat_=M_SNOW)

# Side mountain (left)
fuji_l = smooth_cone("fuji_l", r1=11.0, r2=1.5, depth=8.0, segs=24, loc=(-25, 35, 4.0), mat_=M_MOUNTAIN)
fuji_l_snow = smooth_cone("fuji_l_snow", r1=2.6, r2=1.5, depth=1.5, segs=24, loc=(-25, 35, 7.7), mat_=M_SNOW)
fuji_r = smooth_cone("fuji_r", r1=10.0, r2=1.2, depth=7.0, segs=24, loc=(22, 35, 3.5), mat_=M_MOUNTAIN)
fuji_r_snow = smooth_cone("fuji_r_snow", r1=2.3, r2=1.2, depth=1.3, segs=24, loc=(22, 35, 6.9), mat_=M_SNOW)

# ============ GROUND ============
ground = beveled_cube("ground", (40, 40, 0.4), bevel_offset=0.1, loc=(0, 0, -0.2), mat_=M_GROUND)

# ============ SAKURA TREES (6 trees) ============
def make_sakura(name, loc, scale=1.0):
    base = empty(name, loc)
    # Trunk (5-segment curved tapered)
    segments = 5
    parent = base
    for i in range(segments):
        h = 0.7 * scale
        r1 = (0.35 - i*0.04) * scale
        r2 = (0.32 - i*0.04) * scale
        zoff = (i + 0.5) * h
        seg = smooth_cone(f"{name}_t{i}", r1=r1, r2=r2, depth=h, segs=16, loc=(0,0,zoff), parent=base, mat_=M_TRUNK)
        # slight bend
        seg.rotation_euler = (math.radians(random.uniform(-3,3)),
                              math.radians(random.uniform(-3,3)), 0)
    # Canopy: 5 main puffs + 12 sub puffs
    canopy_z = segments * 0.7 * scale + 0.3
    main_puffs = [
        ("center", (0, 0, canopy_z + 0.5*scale), 1.6*scale),
        ("L", (-1.1*scale, 0, canopy_z + 0.2*scale), 1.2*scale),
        ("R", (1.1*scale, 0, canopy_z + 0.2*scale), 1.2*scale),
        ("F", (0, -1.0*scale, canopy_z + 0.3*scale), 1.1*scale),
        ("B", (0, 1.0*scale, canopy_z + 0.3*scale), 1.1*scale),
    ]
    for tag, p, r in main_puffs:
        m_ = M_SAKURA_DEEP if random.random() < 0.4 else M_SAKURA_PINK
        smooth_sphere(f"{name}_c_{tag}", r=r, segs=24, rings=14, loc=p, parent=base, mat_=m_)
    # 12 sub puffs scattered
    for i in range(12):
        angle = (i / 12.0) * math.pi * 2 + random.uniform(-0.2, 0.2)
        rad = random.uniform(1.0, 1.7) * scale
        h = canopy_z + random.uniform(-0.3, 0.8) * scale
        x, y = rad*math.cos(angle), rad*math.sin(angle)
        r = random.uniform(0.55, 0.85) * scale
        m_ = M_SAKURA_DEEP if random.random() < 0.3 else M_SAKURA_PINK
        smooth_sphere(f"{name}_s{i}", r=r, segs=18, rings=10, loc=(x,y,h), parent=base, mat_=m_)
    return base

trees = []
tree_positions = [
    (-12, 8, 0, 1.2), (12, 7, 0, 1.1),
    (-8, -10, 0, 1.0), (10, -9, 0, 1.05),
    (-15, -3, 0, 0.95), (16, 2, 0, 1.15),
]
for i, (x, y, z, s) in enumerate(tree_positions):
    t = make_sakura(f"tree{i}", (x, y, z), scale=s)
    trees.append(t)

# ============ TEMPLE SHINTO (background, behind duelists) ============
temple_base = empty("temple", loc=(0, 24, 0))
# Platform
temple_platform = beveled_cube("temple_platform", (10, 6, 1.2), loc=(0, 0, 0.6), parent=temple_base, mat_=M_STONE)
# Stairs (3 steps)
for i in range(3):
    beveled_cube(f"step{i}", (8, 0.8, 0.3), loc=(0, -3.2 - i*0.7, 0.15 + i*0.3), parent=temple_base, mat_=M_STONE)
# Main building body (raised platform + columns + body)
temple_body = beveled_cube("temple_body", (8.5, 4.5, 3.5), loc=(0, 0, 2.95), parent=temple_base, mat_=M_TEMPLE_RED)
# 4 corner columns
col_positions = [(-3.8, -1.8), (3.8, -1.8), (-3.8, 1.8), (3.8, 1.8)]
for i, (cx, cy) in enumerate(col_positions):
    cyl(f"col{i}", r=0.25, depth=3.5, segs=20, loc=(cx, cy, 2.95), parent=temple_base, mat_=M_TEMPLE_WOOD)
# Roof - pagoda style (3-tier upward sloping)
# Tier 1: wide curved roof
roof1 = beveled_cube("roof1", (10.5, 6.0, 0.4), loc=(0, 0, 5.0), parent=temple_base, mat_=M_ROOF)
# Tier 2 body (smaller)
beveled_cube("tier2_body", (6.5, 3.5, 1.5), loc=(0, 0, 5.95), parent=temple_base, mat_=M_TEMPLE_RED)
# Tier 2 roof
roof2 = beveled_cube("roof2", (8.0, 4.5, 0.35), loc=(0, 0, 6.9), parent=temple_base, mat_=M_ROOF)
# Tier 3 body (smallest)
beveled_cube("tier3_body", (4.5, 2.5, 1.2), loc=(0, 0, 7.65), parent=temple_base, mat_=M_TEMPLE_RED)
# Tier 3 roof
roof3 = beveled_cube("roof3", (6.0, 3.5, 0.32), loc=(0, 0, 8.45), parent=temple_base, mat_=M_ROOF)
# Top finial - gold sphere + spike
smooth_sphere("finial_orb", r=0.35, loc=(0, 0, 8.85), parent=temple_base, mat_=M_GOLD)
smooth_cone("finial_spike", r1=0.10, r2=0.02, depth=1.2, segs=12, loc=(0, 0, 9.55), parent=temple_base, mat_=M_GOLD)

# ============ RED BRIDGE (foreground left) ============
bridge_base = empty("bridge", loc=(-9, -4, 0.3))
# Curved arc bridge - 7 segments
for i in range(7):
    t = (i / 6.0) * 2 - 1  # -1 to 1
    arc_z = 1.2 * (1 - t*t)
    seg_x = i * 0.65 - 1.95
    beveled_cube(f"bridge_s{i}", (0.65, 1.8, 0.25), loc=(seg_x, 0, arc_z),
                 parent=bridge_base, mat_=M_BRIDGE)
# Bridge railings (left/right)
for side in (-1, 1):
    for i in range(7):
        t = (i / 6.0) * 2 - 1
        arc_z = 1.2 * (1 - t*t) + 0.5
        seg_x = i * 0.65 - 1.95
        cyl(f"rail_s{side}_{i}", r=0.04, depth=0.5, segs=8,
            loc=(seg_x, side*0.85, arc_z), parent=bridge_base, mat_=M_BRIDGE)
# Bridge posts (each end)
for side in (-1, 1):
    for end in (-1, 1):
        post = beveled_cube(f"post_{side}_{end}", (0.16, 0.16, 1.0),
                            loc=(end*2.0, side*0.85, 0.6),
                            parent=bridge_base, mat_=M_BRIDGE)
        smooth_sphere(f"post_top_{side}_{end}", r=0.13,
                      loc=(end*2.0, side*0.85, 1.18),
                      parent=bridge_base, mat_=M_GOLD)

# ============ LOTUS POND (under bridge area) ============
pond = empty("pond", loc=(-9, -4, 0))
# Pond water
smooth_sphere("pond_water", r=2.8, loc=(0, 0, 0.05), parent=pond, mat_=M_WATER, scale=(1.2, 1.0, 0.05))
# 5 lotus flowers floating
lotus_lst = []
for i in range(5):
    angle = (i / 5.0) * math.pi * 2
    rad = random.uniform(1.0, 1.7)
    x, y = rad*math.cos(angle), rad*math.sin(angle)
    leaf = smooth_sphere(f"lotus_leaf{i}", r=0.35, loc=(x, y, 0.08),
                        parent=pond, mat_=M_LOTUS_GREEN, scale=(1, 1, 0.15))
    flower = smooth_sphere(f"lotus_f{i}", r=0.16, loc=(x, y, 0.20),
                          parent=pond, mat_=M_LOTUS)
    lotus_lst.append((leaf, flower))
# 4 ripples concentric
ripples = []
for i in range(4):
    rip = smooth_sphere(f"ripple{i}", r=0.3+i*0.3, loc=(0, 0, 0.1),
                       parent=pond, mat_=M_WATER, scale=(1,1,0.02))
    rip["_base_scale"] = 1.0 + i*0.5
    ripples.append(rip)

# ============ SAMURAI ANATOMY ============
def make_samurai(name, loc, facing_dir=1, armor_main=M_ARMOR_BLACK, armor_accent=M_ARMOR_RED):
    """facing_dir: 1=facing +Y, -1=facing -Y. Samurai in duel ready stance, katana raised diagonal."""
    body_empty = empty(name, loc)
    body_empty.rotation_euler = (0, 0, math.radians(0 if facing_dir==1 else 180))

    # Legs (separated) - in slight crouch stance
    leg_stance = 0.35
    for side_idx, side in enumerate((-1, 1)):
        leg_empty = empty(f"{name}_leg_e_{side_idx}", (side*leg_stance, 0, 1.05), parent=body_empty)
        # Upper leg
        beveled_cube(f"{name}_thigh_{side_idx}", (0.30, 0.30, 0.95),
                     loc=(0, 0, -0.45), parent=leg_empty, mat_=armor_main)
        # Lower leg
        beveled_cube(f"{name}_shin_{side_idx}", (0.26, 0.26, 0.9),
                     loc=(0, 0, -1.35), parent=leg_empty, mat_=armor_main)
        # Foot
        beveled_cube(f"{name}_foot_{side_idx}", (0.30, 0.55, 0.18),
                     loc=(0, 0.05, -1.85), parent=leg_empty, mat_=M_KATANA_HILT)

    # Torso (do/cuirasse) - wider chest, narrower waist (do-maru style)
    torso = beveled_cube(f"{name}_torso", (0.85, 0.55, 1.0),
                         bevel_offset=0.08, loc=(0, 0, 1.85), parent=body_empty, mat_=armor_main)
    # Chest plate accent
    beveled_cube(f"{name}_chest_plate", (0.62, 0.10, 0.55),
                 loc=(0, -0.32, 2.10), parent=body_empty, mat_=armor_accent)
    # Belt obi
    beveled_cube(f"{name}_belt", (0.92, 0.60, 0.18),
                 loc=(0, 0, 1.35), parent=body_empty, mat_=M_ARMOR_GOLD)
    # Skirt (kusazuri - 5 hanging plates)
    for i in range(5):
        angle = (i - 2) * 0.35
        px = math.sin(angle) * 0.50
        py = -math.cos(angle) * 0.10
        beveled_cube(f"{name}_skirt{i}", (0.30, 0.10, 0.55),
                     loc=(px, py - 0.30, 1.05), parent=body_empty, mat_=armor_main)
    # Shoulder pauldrons (sode)
    for side_idx, side in enumerate((-1, 1)):
        sode = beveled_cube(f"{name}_sode_{side_idx}", (0.32, 0.45, 0.55),
                            bevel_offset=0.06,
                            loc=(side*0.55, -0.05, 2.10), parent=body_empty, mat_=armor_accent)
        sode.rotation_euler = (0, math.radians(side*8), 0)

    # Neck
    cyl(f"{name}_neck", r=0.18, depth=0.30, segs=16,
        loc=(0, 0, 2.55), parent=body_empty, mat_=M_SKIN)

    # Head
    head_empty = empty(f"{name}_head_e", (0, 0, 2.85), parent=body_empty)
    smooth_sphere(f"{name}_head", r=0.30, segs=24, rings=18,
                  loc=(0, 0, 0), parent=head_empty, mat_=M_SKIN)
    # KABUTO helmet (rounded dome)
    smooth_sphere(f"{name}_kabuto_dome", r=0.36, segs=24, rings=14,
                  loc=(0, 0.04, 0.10), parent=head_empty, mat_=armor_main, scale=(1.0, 1.0, 0.9))
    # Kabuto crest (maedate) - decorative front piece (curved horns)
    for side_idx, side in enumerate((-1, 1)):
        horn = smooth_cone(f"{name}_horn_{side_idx}", r1=0.06, r2=0.01, depth=0.55, segs=12,
                           loc=(side*0.12, -0.20, 0.35), parent=head_empty, mat_=M_ARMOR_GOLD)
        horn.rotation_euler = (math.radians(-30), 0, math.radians(side*15))
    # Crest center disc
    smooth_sphere(f"{name}_crest", r=0.10, loc=(0, -0.30, 0.20),
                  parent=head_empty, mat_=M_ARMOR_GOLD, scale=(1.5, 0.3, 1.5))
    # Kabuto neck guard (shikoro - 3 lames)
    for i in range(3):
        lame = beveled_cube(f"{name}_shikoro{i}", (0.55, 0.10, 0.18),
                            loc=(0, 0.18, -0.05 - i*0.16), parent=head_empty, mat_=armor_accent)
        lame.rotation_euler = (math.radians(10 + i*8), 0, 0)
    # Mempo mask (jaw guard)
    mempo = beveled_cube(f"{name}_mempo", (0.40, 0.20, 0.30),
                         loc=(0, -0.18, -0.10), parent=head_empty, mat_=armor_main)
    # Mempo nose
    smooth_sphere(f"{name}_mempo_nose", r=0.10, loc=(0, -0.30, -0.05),
                  parent=head_empty, mat_=armor_main, scale=(1, 1.4, 1))
    # Eyes (slits, faint glow under helmet)
    for side_idx, side in enumerate((-1, 1)):
        smooth_sphere(f"{name}_eye_{side_idx}", r=0.04,
                      loc=(side*0.10, -0.22, 0.08), parent=head_empty,
                      mat_=M_LANTERN, scale=(1.2, 0.3, 0.6))

    # ARMS - Right arm raised holding katana, Left arm forward gripping katana too (2-handed grip)
    # Right shoulder
    r_shoulder = empty(f"{name}_r_shoulder", (0.55, 0, 2.30), parent=body_empty)
    # Right upper arm
    beveled_cube(f"{name}_r_upper", (0.22, 0.22, 0.60),
                 loc=(0, 0, -0.30), parent=r_shoulder, mat_=armor_main)
    # Right elbow + forearm
    r_elbow = empty(f"{name}_r_elbow", (0, 0, -0.62), parent=r_shoulder)
    beveled_cube(f"{name}_r_forearm", (0.20, 0.20, 0.60),
                 loc=(0, 0, -0.30), parent=r_elbow, mat_=armor_main)
    # Right hand
    r_hand = empty(f"{name}_r_hand", (0, 0, -0.65), parent=r_elbow)
    smooth_sphere(f"{name}_r_hand_g", r=0.13, loc=(0, 0, 0), parent=r_hand, mat_=M_KATANA_HILT)

    # Left shoulder
    l_shoulder = empty(f"{name}_l_shoulder", (-0.55, 0, 2.30), parent=body_empty)
    beveled_cube(f"{name}_l_upper", (0.22, 0.22, 0.60),
                 loc=(0, 0, -0.30), parent=l_shoulder, mat_=armor_main)
    l_elbow = empty(f"{name}_l_elbow", (0, 0, -0.62), parent=l_shoulder)
    beveled_cube(f"{name}_l_forearm", (0.20, 0.20, 0.60),
                 loc=(0, 0, -0.30), parent=l_elbow, mat_=armor_main)
    l_hand = empty(f"{name}_l_hand", (0, 0, -0.65), parent=l_elbow)
    smooth_sphere(f"{name}_l_hand_g", r=0.13, loc=(0, 0, 0), parent=l_hand, mat_=M_KATANA_HILT)

    # Pose arms in duel stance (katana raised diagonal, 2-handed grip)
    # Right arm raised back over shoulder
    r_shoulder.rotation_euler = (math.radians(-55), 0, math.radians(-15))
    r_elbow.rotation_euler = (math.radians(20), 0, 0)
    # Left arm forward, slightly bent
    l_shoulder.rotation_euler = (math.radians(-35), 0, math.radians(15))
    l_elbow.rotation_euler = (math.radians(40), 0, 0)

    # KATANA (attached to right hand, but visually rests on both)
    katana_empty = empty(f"{name}_katana", (0, 0, -0.10), parent=r_hand)
    # Tsuka (handle/hilt)
    cyl(f"{name}_tsuka", r=0.05, depth=0.50, segs=12, loc=(0, 0, -0.25),
        parent=katana_empty, mat_=M_KATANA_HILT)
    # Tsuba (handguard)
    cyl(f"{name}_tsuba", r=0.12, depth=0.04, segs=20, loc=(0, 0, -0.05),
        parent=katana_empty, mat_=M_ARMOR_GOLD)
    # Blade (long, slightly curved - approximated by tilted segments)
    blade_empty = empty(f"{name}_blade_e", (0, 0, 0.05), parent=katana_empty)
    # 4 segments simulating gentle curve
    for i in range(4):
        seg = beveled_cube(f"{name}_blade_s{i}", (0.04, 0.015, 0.35),
                           bevel_offset=0.005,
                           loc=(0, -i*0.02, 0.2 + i*0.32), parent=blade_empty, mat_=M_KATANA)
        seg.rotation_euler = (math.radians(i*3), 0, 0)
    # Kissaki (tip)
    smooth_cone(f"{name}_kissaki", r1=0.04, r2=0.005, depth=0.20, segs=12,
                loc=(0, -0.08, 1.55), parent=blade_empty, mat_=M_KATANA)

    return {
        "root": body_empty,
        "head_e": head_empty,
        "r_shoulder": r_shoulder,
        "l_shoulder": l_shoulder,
        "katana": katana_empty,
        "blade": blade_empty,
    }

# Two samurai facing each other
sam1 = make_samurai("sam1", (-3.5, 0, 0), facing_dir=1,
                    armor_main=M_ARMOR_BLACK, armor_accent=M_ARMOR_RED)
sam1["root"].rotation_euler = (0, 0, math.radians(15))  # slight angle facing center

sam2 = make_samurai("sam2", (3.5, 0, 0), facing_dir=-1,
                    armor_main=M_ARMOR_BLUE, armor_accent=M_ARMOR_GOLD)
sam2["root"].rotation_euler = (0, 0, math.radians(180-15))

# ============ LANTERNS (8 paper lanterns) ============
lanterns = []
lantern_positions = [
    (-7, 12, 1.8), (7, 12, 1.8),
    (-10, 4, 1.7), (10, 4, 1.7),
    (-5, -8, 1.5), (5, -8, 1.5),
    (-12, 22, 2.5), (12, 22, 2.5),
]
for i, (lx, ly, lz) in enumerate(lantern_positions):
    le = empty(f"lant_e{i}", (lx, ly, lz))
    # Pole
    cyl(f"lant_pole{i}", r=0.05, depth=lz, segs=10,
        loc=(0, 0, -lz/2), parent=le, mat_=M_LANTERN_FRAME)
    # Lantern body (cylinder + spheres at top/bottom)
    cyl(f"lant_body{i}", r=0.30, depth=0.55, segs=20,
        loc=(0, 0, 0.05), parent=le, mat_=M_LANTERN)
    smooth_sphere(f"lant_top{i}", r=0.30, segs=18, rings=10,
                  loc=(0, 0, 0.30), parent=le, mat_=M_LANTERN, scale=(1,1,0.3))
    smooth_sphere(f"lant_bot{i}", r=0.30, segs=18, rings=10,
                  loc=(0, 0, -0.20), parent=le, mat_=M_LANTERN, scale=(1,1,0.3))
    # Frame band
    cyl(f"lant_frame_t{i}", r=0.32, depth=0.04, segs=20,
        loc=(0, 0, 0.30), parent=le, mat_=M_LANTERN_FRAME)
    cyl(f"lant_frame_b{i}", r=0.32, depth=0.04, segs=20,
        loc=(0, 0, -0.20), parent=le, mat_=M_LANTERN_FRAME)
    lanterns.append(le)

# ============ BUDDHA STATUE (right side garden) ============
buddha_base = empty("buddha", loc=(13, -10, 0))
# Lotus pedestal
smooth_sphere("buddha_pedestal", r=1.2, loc=(0, 0, 0.5), parent=buddha_base,
              mat_=M_LOTUS, scale=(1, 1, 0.4))
# Petal ring around pedestal
for i in range(8):
    a = (i / 8.0) * math.pi * 2
    p = smooth_sphere(f"buddha_petal{i}", r=0.45,
                     loc=(1.0*math.cos(a), 1.0*math.sin(a), 0.6),
                     parent=buddha_base, mat_=M_LOTUS, scale=(0.5, 1, 0.3))
    p.rotation_euler = (0, 0, a + math.pi/2)
# Body sitting cross-legged
beveled_cube("buddha_legs", (1.6, 1.6, 0.6), loc=(0, 0, 1.15),
             parent=buddha_base, mat_=M_BUDDHA)
beveled_cube("buddha_torso", (1.1, 0.7, 1.4), loc=(0, 0, 2.15),
             parent=buddha_base, mat_=M_BUDDHA)
# Head (smooth)
smooth_sphere("buddha_head", r=0.55, segs=28, rings=18,
              loc=(0, 0, 3.25), parent=buddha_base, mat_=M_BUDDHA)
# Topknot ushnisha
smooth_sphere("buddha_topknot", r=0.20, loc=(0, 0, 3.85),
              parent=buddha_base, mat_=M_BUDDHA)
# Hands meditating (palms up)
for side in (-1, 1):
    smooth_sphere(f"buddha_hand_{side}", r=0.25,
                  loc=(side*0.55, -0.35, 1.50),
                  parent=buddha_base, mat_=M_BUDDHA, scale=(1, 1.5, 0.5))
# Halo (gold disc behind head)
halo = cyl("buddha_halo", r=0.85, depth=0.05, segs=32,
            loc=(0, 0.15, 3.3), parent=buddha_base, mat_=M_GOLD)
halo.rotation_euler = (math.radians(90), 0, 0)

# ============ CRANE (white, flying) ============
crane_empty = empty("crane", loc=(8, 18, 11))
# Body
crane_body = smooth_sphere("crane_body", r=0.50, segs=20, rings=14,
                            loc=(0,0,0), parent=crane_empty, mat_=M_CRANE_WHITE,
                            scale=(2.5, 1.0, 1.0))
# Neck (long, curved S-shape - 4 segments)
neck_e = empty("crane_neck_e", (0.9, 0, 0.3), parent=crane_empty)
for i in range(4):
    seg = cyl(f"crane_neck{i}", r=0.10, depth=0.35, segs=12,
              loc=(i*0.18, 0, 0.18 + i*0.10), parent=neck_e, mat_=M_CRANE_WHITE)
    seg.rotation_euler = (0, math.radians(-25 + i*15), 0)
# Head
crane_head = smooth_sphere("crane_head", r=0.16, loc=(0.85, 0, 0.85),
                            parent=neck_e, mat_=M_CRANE_WHITE)
# Red crown patch
smooth_sphere("crane_crown", r=0.10, loc=(0.78, 0, 1.0),
              parent=neck_e, mat_=M_CRANE_RED, scale=(1, 1, 0.5))
# Beak
smooth_cone("crane_beak", r1=0.06, r2=0.005, depth=0.30, segs=12,
            loc=(1.10, 0, 0.85), parent=neck_e, mat_=M_CRANE_BLACK)
# Tail feathers (black tips)
beveled_cube("crane_tail", (0.40, 0.20, 0.10),
             loc=(-1.20, 0, -0.05), parent=crane_empty, mat_=M_CRANE_BLACK)
# Wings (large outstretched - 2 segments each)
wings = []
for side_idx, side in enumerate((-1, 1)):
    w_shoulder = empty(f"wing_sh{side_idx}", (0, side*0.35, 0.10), parent=crane_empty)
    # Inner wing
    beveled_cube(f"wing_inner_{side_idx}", (1.0, 1.4, 0.06),
                 loc=(0, side*0.7, 0), parent=w_shoulder, mat_=M_CRANE_WHITE)
    # Outer wing (tip with black feathers)
    w_outer = empty(f"wing_outer_e{side_idx}", (0, side*1.4, 0), parent=w_shoulder)
    beveled_cube(f"wing_outer_{side_idx}", (0.9, 1.0, 0.05),
                 loc=(0, side*0.5, 0), parent=w_outer, mat_=M_CRANE_WHITE)
    # Black wingtips
    beveled_cube(f"wing_tip_{side_idx}", (0.55, 0.40, 0.04),
                 loc=(0, side*0.95, 0), parent=w_outer, mat_=M_CRANE_BLACK)
    wings.append((w_shoulder, w_outer, side))
# Legs (tucked back in flight)
for side_idx, side in enumerate((-1, 1)):
    leg = cyl(f"crane_leg{side_idx}", r=0.04, depth=0.7, segs=10,
              loc=(-0.7, side*0.15, -0.35), parent=crane_empty, mat_=M_CRANE_BLACK)
    leg.rotation_euler = (math.radians(20), 0, 0)

# ============ 300 SAKURA PETALS (floating) ============
petals = []
for i in range(300):
    # Spread across scene with random positions
    x = random.uniform(-22, 22)
    y = random.uniform(-18, 28)
    z = random.uniform(0.5, 18)
    # Small flattened sphere = petal
    pt = smooth_sphere(f"petal{i}", r=0.10, segs=10, rings=6,
                       loc=(x, y, z), mat_=M_PETAL,
                       scale=(1.5, 0.7, 0.2))
    pt.rotation_euler = (random.uniform(0, math.pi*2),
                         random.uniform(0, math.pi*2),
                         random.uniform(0, math.pi*2))
    pt["_phase"] = random.uniform(0, math.pi*2)
    pt["_fall_speed"] = random.uniform(1.5, 3.5)
    pt["_drift_x"] = random.uniform(-0.8, 0.8)
    pt["_drift_y"] = random.uniform(-0.6, 0.6)
    pt["_base_z"] = z
    petals.append(pt)

# ============ STONE LANTERNS (2 ground stone lanterns) ============
for i, (sx, sy) in enumerate([(-13, -6), (13, 6)]):
    sle = empty(f"sl{i}", (sx, sy, 0))
    # Base
    beveled_cube(f"sl_base{i}", (0.6, 0.6, 0.2), loc=(0, 0, 0.1), parent=sle, mat_=M_STONE)
    # Pillar
    cyl(f"sl_pillar{i}", r=0.15, depth=0.8, segs=12, loc=(0, 0, 0.6), parent=sle, mat_=M_STONE)
    # Top platform
    beveled_cube(f"sl_plat{i}", (0.5, 0.5, 0.1), loc=(0, 0, 1.05), parent=sle, mat_=M_STONE)
    # Light chamber (hollow look)
    beveled_cube(f"sl_chamber{i}", (0.35, 0.35, 0.35), loc=(0, 0, 1.30), parent=sle, mat_=M_STONE)
    smooth_sphere(f"sl_light{i}", r=0.10, loc=(0, 0, 1.30), parent=sle, mat_=M_LANTERN)
    # Roof
    smooth_cone(f"sl_roof{i}", r1=0.40, r2=0.15, depth=0.20, segs=12,
                loc=(0, 0, 1.60), parent=sle, mat_=M_STONE)
    smooth_sphere(f"sl_finial{i}", r=0.08, loc=(0, 0, 1.78), parent=sle, mat_=M_GOLD)

# ============ ANIMATION ============
fps = 30
duration_s = 6
total_frames = fps * duration_s

# Samurai - subtle tense breath + katana micro-rotation (rotate Z slight)
# Both samurai have very slight forward-back bob (tense duel pose)
for f in range(1, total_frames + 1, 4):
    t = (f - 1) / fps
    # sam1 micro bob X (tense) + katana slight twist
    sam1["root"].location.z = 0 + math.sin(t * 1.5) * 0.015
    sam1["root"].keyframe_insert("location", frame=f)
    sam1["katana"].rotation_euler = (
        math.sin(t * 1.2) * 0.05,
        math.sin(t * 1.0 + 0.3) * 0.04,
        math.sin(t * 0.8) * 0.06,
    )
    sam1["katana"].keyframe_insert("rotation_euler", frame=f)
    # sam2 mirror
    sam2["root"].location.z = 0 + math.sin(t * 1.5 + math.pi*0.5) * 0.015
    sam2["root"].keyframe_insert("location", frame=f)
    sam2["katana"].rotation_euler = (
        math.sin(t * 1.2 + 0.5) * 0.05,
        math.sin(t * 1.0 + 0.8) * 0.04,
        math.sin(t * 0.8 + 0.7) * 0.06,
    )
    sam2["katana"].keyframe_insert("rotation_euler", frame=f)

# Petals - fall + drift in 3D
for pt in petals:
    base_z = pt["_base_z"]
    fall = pt["_fall_speed"]
    dx = pt["_drift_x"]
    dy = pt["_drift_y"]
    phase = pt["_phase"]
    base_x = pt.location.x
    base_y = pt.location.y
    for f in range(1, total_frames + 1, 6):
        t = (f - 1) / fps
        # Continuous fall (loops back to top)
        z = base_z - (fall * t) % 18
        # Drift sway
        x = base_x + dx * math.sin(t * 2.0 + phase)
        y = base_y + dy * math.cos(t * 1.5 + phase)
        # Tumble rotation
        rx = phase + t * 1.2
        ry = phase + t * 0.8
        rz = phase + t * 1.5
        pt.location = (x, y, z)
        pt.rotation_euler = (rx, ry, rz)
        pt.keyframe_insert("location", frame=f)
        pt.keyframe_insert("rotation_euler", frame=f)

# Trees - sway gently
for ti, tree in enumerate(trees):
    for f in range(1, total_frames + 1, 6):
        t = (f - 1) / fps
        tree.rotation_euler = (
            math.sin(t * 0.8 + ti) * math.radians(2.5),
            math.cos(t * 0.7 + ti*0.5) * math.radians(2.0),
            0,
        )
        tree.keyframe_insert("rotation_euler", frame=f)

# Crane - flap wings + orbit slowly
crane_orbit_radius = 10
crane_base_z = 11
for f in range(1, total_frames + 1, 3):
    t = (f - 1) / fps
    # Wing flap
    flap = math.sin(t * 3.5) * math.radians(35)
    for w_shoulder, w_outer, side in wings:
        w_shoulder.rotation_euler = (side * flap, 0, 0)
        w_shoulder.keyframe_insert("rotation_euler", frame=f)
        w_outer.rotation_euler = (side * flap * 0.5, 0, 0)
        w_outer.keyframe_insert("rotation_euler", frame=f)
    # Orbit
    angle = t * 0.6
    crane_empty.location = (
        8 + crane_orbit_radius * math.cos(angle) * 0.6,
        18 + crane_orbit_radius * math.sin(angle) * 0.5,
        crane_base_z + math.sin(t * 1.5) * 0.6,
    )
    crane_empty.rotation_euler = (0, 0, angle + math.pi/2)
    crane_empty.keyframe_insert("location", frame=f)
    crane_empty.keyframe_insert("rotation_euler", frame=f)

# Lanterns - pulse + slight bob
for i, le in enumerate(lanterns):
    base_z = le.location.z
    phase = i * 0.7
    for f in range(1, total_frames + 1, 5):
        t = (f - 1) / fps
        le.location.z = base_z + math.sin(t * 1.8 + phase) * 0.06
        le.scale = (
            1 + math.sin(t * 2.5 + phase) * 0.03,
            1 + math.sin(t * 2.5 + phase) * 0.03,
            1 + math.cos(t * 2.5 + phase) * 0.03,
        )
        le.keyframe_insert("location", frame=f)
        le.keyframe_insert("scale", frame=f)

# Buddha - subtle breath
for f in range(1, total_frames + 1, 6):
    t = (f - 1) / fps
    s = 1 + math.sin(t * 0.6) * 0.015
    buddha_base.scale = (s, s, s)
    buddha_base.keyframe_insert("scale", frame=f)

# Pond ripples expansion
for ri, rip in enumerate(ripples):
    base_s = rip["_base_scale"]
    for f in range(1, total_frames + 1, 4):
        t = (f - 1) / fps
        s_factor = 1 + (math.sin(t * 0.8 - ri * 0.5) + 1) * 0.4
        rip.scale = (s_factor * base_s, s_factor * base_s, 0.02)
        rip.keyframe_insert("scale", frame=f)

# Lotus flowers - subtle bob
for i, (leaf, flower) in enumerate(lotus_lst):
    base_z_leaf = leaf.location.z
    base_z_flower = flower.location.z
    phase = i * 0.8
    for f in range(1, total_frames + 1, 6):
        t = (f - 1) / fps
        leaf.location.z = base_z_leaf + math.sin(t * 1.2 + phase) * 0.03
        flower.location.z = base_z_flower + math.sin(t * 1.2 + phase) * 0.03
        leaf.keyframe_insert("location", frame=f)
        flower.keyframe_insert("location", frame=f)

# Temple finial pulse
# Already done above implicitly via no-op; small twist anim:
for f in range(1, total_frames + 1, 8):
    t = (f - 1) / fps
    temple_base.rotation_euler = (0, 0, math.sin(t * 0.4) * math.radians(0.5))
    temple_base.keyframe_insert("rotation_euler", frame=f)

# Sun gentle breathe (scale)
for f in range(1, total_frames + 1, 6):
    t = (f - 1) / fps
    s = 1 + math.sin(t * 0.5) * 0.05
    sun.scale = (s, s, s)
    sun.keyframe_insert("scale", frame=f)

# ============ EXPORT ============
out_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                       "..", "public", "_pbr_test")
out_dir = os.path.normpath(out_dir)
os.makedirs(out_dir, exist_ok=True)
out_glb = os.path.join(out_dir, "pbr_samurai_proc.glb")

bpy.ops.object.select_all(action='SELECT')
bpy.ops.export_scene.gltf(
    filepath=out_glb,
    export_format='GLB',
    export_animations=True,
    export_apply=False,
    export_yup=True,
    use_selection=False,
)

# Size report
size_mb = os.path.getsize(out_glb) / (1024 * 1024)
print(f"[proc_samurai_duel_sakura] DONE → {out_glb} ({size_mb:.2f} MB)")
print(f"[proc_samurai_duel_sakura] 6 cherry trees + 2 samurai armures + temple shinto 3-tier + Mt Fuji + red bridge + lotus pond + buddha + crane + 300 sakura petals + 8 lanterns + 2 stone lanterns")
