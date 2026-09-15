"""
proc_atlantis_submerged_temple.py — 195e procédural AuroraIA (59e qualité)
Atlantis sous-marine : temple grec + Poséidon + dauphins + raies + sirène + corail + algues
"""
import bpy, bmesh, math, random, os

random.seed(0xA710195)

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

# Materials - underwater palette (blue-green tones)
M_WATER = mat("water", (0.10, 0.35, 0.55, 1.0), 0.3, 0.20, emission=(0.15,0.40,0.60), emission_strength=2.5, alpha=0.85)
M_SURFACE = mat("surface", (0.65, 0.85, 1.0, 1.0), 0.0, 0.15, emission=(0.70,0.90,1.0), emission_strength=4.0, alpha=0.5)
M_SUNRAY = mat("sunray", (1.0, 0.95, 0.75, 1.0), 0.0, 0.05, emission=(1.0,0.95,0.75), emission_strength=8.0, alpha=0.4)
M_SAND = mat("sand", (0.85, 0.80, 0.65, 1.0), 0.0, 0.85, emission=(0.75,0.72,0.60), emission_strength=0.4)
M_ROCK = mat("rock", (0.30, 0.35, 0.30, 1.0), 0.0, 0.85)

# Temple
M_MARBLE = mat("marble", (0.85, 0.82, 0.75, 1.0), 0.1, 0.45, emission=(0.65,0.65,0.60), emission_strength=0.5)
M_MARBLE_WORN = mat("marble_worn", (0.55, 0.55, 0.52, 1.0), 0.0, 0.65, emission=(0.40,0.40,0.40), emission_strength=0.3)
M_ALGAE_GREEN = mat("algae_green", (0.20, 0.55, 0.30, 1.0), 0.0, 0.55, emission=(0.15,0.45,0.25), emission_strength=0.5)

# Poseidon
M_GOLD = mat("gold", (1.0, 0.78, 0.25, 1.0), 0.95, 0.20, emission=(0.95,0.72,0.22), emission_strength=1.2)
M_BRONZE = mat("bronze", (0.65, 0.42, 0.20, 1.0), 0.85, 0.40, emission=(0.55,0.35,0.18), emission_strength=0.6)
M_TRIDENT = mat("trident", (0.85, 0.65, 0.25, 1.0), 0.92, 0.15, emission=(0.90,0.70,0.30), emission_strength=2.5)

# Dolphins
M_DOLPHIN = mat("dolphin", (0.35, 0.45, 0.55, 1.0), 0.0, 0.30, emission=(0.30,0.40,0.50), emission_strength=0.5)
M_DOLPHIN_BELLY = mat("dolphin_b", (0.85, 0.90, 0.95, 1.0), 0.0, 0.35, emission=(0.75,0.82,0.90), emission_strength=0.6)
M_DOLPHIN_EYE = mat("d_eye", (0.10, 0.10, 0.12, 1.0), 0.0, 0.20, emission=(0.15,0.15,0.20), emission_strength=1.0)

# Manta rays
M_MANTA = mat("manta", (0.18, 0.20, 0.25, 1.0), 0.0, 0.40, emission=(0.15,0.18,0.22), emission_strength=0.4)
M_MANTA_BELLY = mat("manta_b", (0.55, 0.60, 0.65, 1.0), 0.0, 0.45, emission=(0.50,0.55,0.60), emission_strength=0.5)

# Fish (school)
M_FISH1 = mat("fish1", (1.0, 0.65, 0.25, 1.0), 0.0, 0.35, emission=(0.95,0.60,0.22), emission_strength=1.5)
M_FISH2 = mat("fish2", (0.95, 0.85, 0.30, 1.0), 0.0, 0.35, emission=(0.90,0.80,0.28), emission_strength=1.4)
M_FISH3 = mat("fish3", (0.40, 0.85, 0.95, 1.0), 0.0, 0.35, emission=(0.35,0.80,0.95), emission_strength=1.6)

# Coral
M_CORAL_PINK = mat("coral_pink", (1.0, 0.45, 0.60, 1.0), 0.0, 0.45, emission=(0.95,0.40,0.55), emission_strength=1.5)
M_CORAL_PURPLE = mat("coral_purple", (0.65, 0.30, 0.85, 1.0), 0.0, 0.50, emission=(0.60,0.28,0.80), emission_strength=1.4)
M_CORAL_YELLOW = mat("coral_yellow", (1.0, 0.85, 0.30, 1.0), 0.0, 0.45, emission=(0.95,0.80,0.28), emission_strength=1.5)

# Algae
M_KELP = mat("kelp", (0.18, 0.40, 0.20, 1.0), 0.0, 0.55, emission=(0.15,0.35,0.18), emission_strength=0.6)
M_KELP_LIGHT = mat("kelp_light", (0.30, 0.55, 0.25, 1.0), 0.0, 0.50, emission=(0.25,0.50,0.20), emission_strength=0.7)

# Mermaid
M_MERMAID_SKIN = mat("mermaid_skin", (0.95, 0.82, 0.70, 1.0), 0.0, 0.45, emission=(0.85,0.75,0.65), emission_strength=0.4)
M_MERMAID_TAIL = mat("mermaid_tail", (0.25, 0.55, 0.85, 1.0), 0.4, 0.25, emission=(0.30,0.60,0.90), emission_strength=1.8)
M_MERMAID_HAIR = mat("mermaid_hair", (0.85, 0.45, 0.15, 1.0), 0.0, 0.55, emission=(0.80,0.42,0.15), emission_strength=0.6)
M_MERMAID_BRA = mat("mermaid_bra", (0.85, 0.55, 0.85, 1.0), 0.3, 0.35, emission=(0.80,0.50,0.80), emission_strength=0.8)

# Amphora
M_AMPHORA = mat("amphora", (0.55, 0.35, 0.20, 1.0), 0.0, 0.55, emission=(0.45,0.28,0.15), emission_strength=0.3)
M_AMPHORA_DECO = mat("amphora_deco", (0.95, 0.85, 0.30, 1.0), 0.5, 0.30, emission=(0.85,0.75,0.28), emission_strength=0.5)

# Gold coins / bubbles / particles
M_GOLD_COIN = mat("gold_coin", (1.0, 0.85, 0.30, 1.0), 0.95, 0.18, emission=(1.0,0.80,0.30), emission_strength=2.5)
M_BUBBLE = mat("bubble", (0.75, 0.92, 1.0, 0.6), 0.0, 0.10, emission=(0.80,0.95,1.0), emission_strength=3.0, alpha=0.5)
M_SEDIMENT = mat("sediment", (0.65, 0.55, 0.40, 1.0), 0.0, 0.55, emission=(0.55,0.45,0.35), emission_strength=0.6, alpha=0.5)

# Hot vents
M_LAVA = mat("lava", (1.0, 0.45, 0.10, 1.0), 0.0, 0.10, emission=(1.0,0.50,0.12), emission_strength=12.0)
M_VENT_SMOKE = mat("vent_smoke", (0.35, 0.30, 0.30, 1.0), 0.0, 0.85, emission=(0.30,0.25,0.25), emission_strength=0.5, alpha=0.4)

# ============ WATER DOME (large sphere giving submerged feel) ============
water_dome = smooth_sphere("water_dome", r=85, segs=32, rings=20, loc=(0,0,0), mat_=M_WATER, scale=(1,1,0.65))
water_dome.scale = (1,1,0.65)

# Surface light (ceiling)
surface = beveled_cube("surface", (90, 90, 0.2), bevel_offset=0.05,
                       loc=(0, 0, 28), mat_=M_SURFACE)

# Sunrays (8 angled beams from surface)
sun_rays = []
for i in range(8):
    a = (i / 8.0) * math.pi * 2
    rx, ry = 5*math.cos(a), 5*math.sin(a)
    ray = smooth_cone(f"sunray{i}", r1=3.5, r2=0.5, depth=25, segs=12,
                     loc=(rx, ry, 13), mat_=M_SUNRAY)
    ray.rotation_euler = (math.radians(5*math.cos(a)),
                          math.radians(-5*math.sin(a)), 0)
    sun_rays.append(ray)

# ============ SEAFLOOR ============
seafloor = beveled_cube("seafloor", (90, 90, 0.5), bevel_offset=0.10,
                       loc=(0, 0, -0.25), mat_=M_SAND)
# Sand dunes (12 mounds)
for i in range(12):
    a = random.uniform(0, math.pi*2)
    rad = random.uniform(8, 30)
    smooth_sphere(f"dune{i}", r=random.uniform(1.5, 3.5),
                  loc=(rad*math.cos(a), rad*math.sin(a), 0.1),
                  mat_=M_SAND, scale=(1, 1, 0.25))

# Scattered rocks (20)
for i in range(20):
    a = random.uniform(0, math.pi*2)
    rad = random.uniform(5, 28)
    rx, ry = rad*math.cos(a), rad*math.sin(a)
    rock = smooth_sphere(f"rock{i}", r=random.uniform(0.5, 1.3),
                        loc=(rx, ry, 0.2), mat_=M_ROCK,
                        scale=(random.uniform(0.8,1.3), random.uniform(0.8,1.3),
                               random.uniform(0.7,1.0)))
    rock.rotation_euler = (0, 0, random.uniform(0, math.pi*2))

# ============ GREEK TEMPLE RUINED (center) ============
temple = empty("temple", loc=(0, 0, 0))

# Stylobate (platform with 3 steps)
for i in range(3):
    beveled_cube(f"steno{i}", (12 - i*0.6, 7 - i*0.5, 0.40),
                 loc=(0, 0, 0.20 + i*0.40), parent=temple, mat_=M_MARBLE)

# 8 COLUMNS (some broken, some standing) - 4 each long side
columns_pos = [(-4.5, -2.5), (-1.5, -2.5), (1.5, -2.5), (4.5, -2.5),
               (-4.5, 2.5), (-1.5, 2.5), (1.5, 2.5), (4.5, 2.5)]
broken_columns = [True, False, False, True, False, True, False, False]  # mix
for i, (cx, cy) in enumerate(columns_pos):
    col_e = empty(f"col_e{i}", (cx, cy, 1.4), parent=temple)
    height = 4.5 if not broken_columns[i] else random.uniform(1.5, 3.0)
    # Column base
    cyl(f"col_base{i}", r=0.45, depth=0.20, segs=20,
        loc=(0, 0, 0), parent=col_e, mat_=M_MARBLE)
    # Column shaft (tapered, ridged - 5 segments)
    for j in range(5):
        z = (j+0.5) * (height / 5)
        if z > height:
            break
        r1 = 0.38 - j * 0.015
        r2 = 0.36 - j * 0.015
        seg = smooth_cone(f"col_s{i}_{j}", r1=r1, r2=r2,
                          depth=height/5, segs=20,
                          loc=(0, 0, z), parent=col_e, mat_=M_MARBLE_WORN if broken_columns[i] else M_MARBLE)
    # Capital (top of column - if not broken)
    if not broken_columns[i]:
        # Doric capital style: simple flat block
        beveled_cube(f"col_cap{i}", (0.85, 0.85, 0.15), bevel_offset=0.04,
                     loc=(0, 0, height + 0.10), parent=col_e, mat_=M_MARBLE)
        beveled_cube(f"col_abacus{i}", (0.95, 0.95, 0.10),
                     loc=(0, 0, height + 0.25), parent=col_e, mat_=M_MARBLE)
    else:
        # Broken top - jagged angle
        cap_e = empty(f"col_cap_e{i}", (0, 0, height), parent=col_e)
        cap_e.rotation_euler = (math.radians(random.uniform(-15,15)),
                                math.radians(random.uniform(-15,15)), 0)
        cyl(f"col_cap{i}", r=0.32, depth=0.20, segs=16,
            loc=(0, 0, 0), parent=cap_e, mat_=M_MARBLE_WORN)
        # Algae on broken top
        smooth_sphere(f"col_algae{i}", r=0.25,
                      loc=(0.05, 0.05, 0.10), parent=cap_e, mat_=M_ALGAE_GREEN, scale=(1, 1, 0.4))

# Entablature (top beams across standing columns) - 2 lengthwise beams
for i, side in enumerate((-1, 1)):
    beveled_cube(f"architrave_{i}", (11, 0.40, 0.30), bevel_offset=0.05,
                 loc=(0, side*2.5, 6.10), parent=temple, mat_=M_MARBLE)
# Cross beams (3 of them, broken)
for i in range(3):
    bx = (i - 1) * 3.5
    cross = beveled_cube(f"cross_beam{i}", (0.4, 5.5, 0.3),
                        loc=(bx, 0, 6.10), parent=temple, mat_=M_MARBLE)
    if i == 1:  # middle broken
        cross.rotation_euler = (math.radians(10), 0, 0)

# Pediment fragments (broken triangular roof pieces)
for i in range(3):
    frag = beveled_cube(f"pediment{i}", (random.uniform(2.0, 3.5),
                                           random.uniform(1.8, 2.5),
                                           random.uniform(0.3, 0.5)),
                       bevel_offset=0.04,
                       loc=(random.uniform(-3,3), random.uniform(-1.5,1.5), 6.7),
                       parent=temple, mat_=M_MARBLE_WORN)
    frag.rotation_euler = (math.radians(random.uniform(-25,25)),
                           math.radians(random.uniform(-25,25)),
                           math.radians(random.uniform(0,90)))

# Fallen column lying on floor
fallen_col_e = empty("fallen_col", (-6, 4, 0.3), parent=temple)
fallen_col_e.rotation_euler = (0, math.radians(90), math.radians(20))
for j in range(5):
    cyl(f"fc_s{j}", r=0.35, depth=0.9, segs=18,
        loc=(0, 0, (j-2)*0.9), parent=fallen_col_e, mat_=M_MARBLE_WORN)
# Cap on fallen column
beveled_cube("fc_cap", (0.85, 0.85, 0.15), loc=(0, 0, -2.3),
             parent=fallen_col_e, mat_=M_MARBLE_WORN)

# ============ POSEIDON STATUE central altar ============
poseidon_base = empty("poseidon", loc=(0, 0, 1.8))
# Pedestal
beveled_cube("posp_ped", (2.0, 1.5, 0.45), bevel_offset=0.06,
             loc=(0, 0, 0), parent=poseidon_base, mat_=M_MARBLE)
beveled_cube("posp_ped_top", (1.8, 1.3, 0.10), loc=(0, 0, 0.28),
             parent=poseidon_base, mat_=M_MARBLE)

# Statue (anatomy with trident)
# Legs (standing pose)
for side_idx, side in enumerate((-1, 1)):
    leg_e = empty(f"pos_leg_e{side_idx}", (side*0.18, 0, 0.35), parent=poseidon_base)
    # Thigh
    cyl(f"pos_thigh{side_idx}", r=0.16, depth=0.85, segs=14,
        loc=(0, 0, 0.42), parent=leg_e, mat_=M_BRONZE)
    # Calf
    cyl(f"pos_calf{side_idx}", r=0.14, depth=0.85, segs=14,
        loc=(0, 0, 1.27), parent=leg_e, mat_=M_BRONZE)
    # Foot
    beveled_cube(f"pos_foot{side_idx}", (0.20, 0.32, 0.10),
                 loc=(0, 0.05, 1.75), parent=leg_e, mat_=M_BRONZE)
# Robe (lower body draped)
smooth_cone("pos_robe", r1=0.50, r2=0.30, depth=1.2, segs=16,
            loc=(0, 0, 1.4), parent=poseidon_base, mat_=M_BRONZE)
# Torso (muscular)
smooth_sphere("pos_torso", r=0.45, segs=22, rings=14,
              loc=(0, 0, 2.30), parent=poseidon_base, mat_=M_BRONZE,
              scale=(1, 0.6, 1.2))
# Chest muscles
smooth_sphere("pos_chest_l", r=0.18, loc=(-0.20, -0.20, 2.45),
              parent=poseidon_base, mat_=M_BRONZE)
smooth_sphere("pos_chest_r", r=0.18, loc=(0.20, -0.20, 2.45),
              parent=poseidon_base, mat_=M_BRONZE)
# Belt
beveled_cube("pos_belt", (0.55, 0.40, 0.10), loc=(0, 0, 2.0),
             parent=poseidon_base, mat_=M_GOLD)
# Neck
cyl("pos_neck", r=0.13, depth=0.20, segs=12, loc=(0, 0, 2.85),
    parent=poseidon_base, mat_=M_BRONZE)
# Head
pos_head = empty("pos_head_e", (0, 0, 3.15), parent=poseidon_base)
smooth_sphere("pos_head_s", r=0.32, segs=24, rings=16, loc=(0, 0, 0),
              parent=pos_head, mat_=M_BRONZE)
# Beard (long flowing)
for j in range(4):
    smooth_sphere(f"pos_beard{j}", r=0.10 - j*0.015,
                  loc=(0, -0.18, -0.20 - j*0.10),
                  parent=pos_head, mat_=M_BRONZE, scale=(1.5, 0.6, 1.2))
# Hair flowing wavy (5 strands)
for j in range(5):
    a = (j - 2) * 0.3
    hair_seg = beveled_cube(f"pos_hair{j}", (0.06, 0.10, 0.45),
                            loc=(0.20*math.sin(a), 0.20, 0.05 - j*0.15),
                            parent=pos_head, mat_=M_BRONZE)
    hair_seg.rotation_euler = (math.radians(20 + j*5), 0, math.radians(a*15))
# Crown (3 spikes)
for j in range(3):
    a = (j - 1) * 0.5
    smooth_cone(f"pos_crown{j}", r1=0.05, r2=0.01, depth=0.30, segs=10,
                loc=(0.15*math.sin(a), 0, 0.30), parent=pos_head, mat_=M_GOLD)
# Eyes
for side in (-1, 1):
    smooth_sphere(f"pos_eye_{side}", r=0.05, loc=(side*0.10, -0.27, 0.05),
                  parent=pos_head, mat_=M_GOLD)
    smooth_sphere(f"pos_pup_{side}", r=0.02, loc=(side*0.10, -0.31, 0.05),
                  parent=pos_head, mat_=M_DOLPHIN_EYE)

# ARMS - right arm raised holding TRIDENT
# Right shoulder
r_sh = empty("pos_r_sh", (0.45, 0, 2.65), parent=poseidon_base)
r_sh.rotation_euler = (math.radians(-100), 0, 0)
cyl("pos_r_upper", r=0.14, depth=0.55, segs=12, loc=(0, 0, -0.30),
    parent=r_sh, mat_=M_BRONZE)
r_el = empty("pos_r_el", (0, 0, -0.60), parent=r_sh)
r_el.rotation_euler = (math.radians(15), 0, 0)
cyl("pos_r_fa", r=0.12, depth=0.50, segs=12, loc=(0, 0, -0.27),
    parent=r_el, mat_=M_BRONZE)
r_hand = empty("pos_r_hand", (0, 0, -0.55), parent=r_el)
smooth_sphere("pos_r_hand_g", r=0.10, loc=(0, 0, 0),
              parent=r_hand, mat_=M_BRONZE)

# TRIDENT (gold) in right hand
trident_e = empty("trident", (0, 0, -0.08), parent=r_hand)
# Pole long
cyl("trident_pole", r=0.045, depth=3.0, segs=14,
    loc=(0, 0, 0.40), parent=trident_e, mat_=M_TRIDENT)
# 3 prongs at top
for side_idx, side in enumerate((-1, 0, 1)):
    prong = smooth_cone(f"trident_p{side_idx}", r1=0.05, r2=0.005, depth=0.55, segs=10,
                       loc=(side*0.15, 0, 2.10), parent=trident_e, mat_=M_TRIDENT)
    if side != 0:
        prong.rotation_euler = (0, math.radians(side*10), 0)
# Base ring decoration
cyl("trident_ring", r=0.07, depth=0.05, segs=14,
    loc=(0, 0, 1.85), parent=trident_e, mat_=M_GOLD)

# Left arm extended down (open palm)
l_sh = empty("pos_l_sh", (-0.45, 0, 2.65), parent=poseidon_base)
l_sh.rotation_euler = (math.radians(-15), 0, math.radians(10))
cyl("pos_l_upper", r=0.14, depth=0.55, segs=12, loc=(0, 0, -0.30),
    parent=l_sh, mat_=M_BRONZE)
l_el = empty("pos_l_el", (0, 0, -0.60), parent=l_sh)
cyl("pos_l_fa", r=0.12, depth=0.50, segs=12, loc=(0, 0, -0.27),
    parent=l_el, mat_=M_BRONZE)
# Left hand
smooth_sphere("pos_l_hand", r=0.10, loc=(0, 0, -0.55),
              parent=l_el, mat_=M_BRONZE)

# Eye gold disc (back, magical artifact)
oeil_e = empty("oeil", (0, 1.5, 2.5), parent=temple)
cyl("oeil_disc", r=0.85, depth=0.10, segs=32, loc=(0,0,0),
    parent=oeil_e, mat_=M_GOLD)
oeil_e.rotation_euler = (math.radians(90), 0, 0)
# Eye iris
cyl("oeil_iris", r=0.40, depth=0.05, segs=24, loc=(0, -0.06, 0),
    parent=oeil_e, mat_=M_TRIDENT)
# Pupil
cyl("oeil_pup", r=0.15, depth=0.05, segs=20, loc=(0, -0.10, 0),
    parent=oeil_e, mat_=M_DOLPHIN_EYE)

# ============ MERMAID ANATOMY ============
mermaid_base = empty("mermaid", loc=(8, -4, 4))
mermaid_base.rotation_euler = (0, 0, math.radians(-30))
# TAIL (lower body - 4 segs tapered with fin)
tail_pivot = empty("mer_tail_pivot", (0, 0, 0), parent=mermaid_base)
for i in range(4):
    r1 = 0.30 - i*0.04
    r2 = 0.26 - i*0.04
    seg = smooth_cone(f"mer_t{i}", r1=r1, r2=r2, depth=0.55, segs=16,
                      loc=(0, 0, -(i+0.5)*0.55), parent=tail_pivot, mat_=M_MERMAID_TAIL)
    seg["_phase"] = i * 0.5
# Tail fin (2 lobes at bottom)
fin_e = empty("mer_fin_e", (0, 0, -2.40), parent=tail_pivot)
for side in (-1, 1):
    fin = beveled_cube(f"mer_fin_{side}", (0.50, 0.04, 0.40), bevel_offset=0.04,
                       loc=(side*0.35, 0, 0), parent=fin_e, mat_=M_MERMAID_TAIL)
    fin.rotation_euler = (0, math.radians(side*20), math.radians(side*15))
# Scales pattern (5 ridges along tail)
for i in range(5):
    cyl(f"mer_scale{i}", r=0.30 - i*0.04, depth=0.04, segs=18,
        loc=(0, 0, -(i+0.5)*0.55), parent=tail_pivot, mat_=M_GOLD).rotation_euler = (math.radians(90), 0, 0)

# WAIST joint
waist_e = empty("mer_waist", (0, 0, 0.30), parent=mermaid_base)
# Torso (upper body)
torso = beveled_cube("mer_torso", (0.45, 0.30, 0.70), bevel_offset=0.06,
                     loc=(0, 0, 0.45), parent=waist_e, mat_=M_MERMAID_SKIN)
# BRA top (signature mermaid)
for side in (-1, 1):
    smooth_sphere(f"mer_bra_{side}", r=0.13,
                  loc=(side*0.15, -0.22, 0.60), parent=waist_e, mat_=M_MERMAID_BRA,
                  scale=(1, 0.8, 1))
# Neck
cyl("mer_neck", r=0.08, depth=0.15, segs=12, loc=(0, 0, 0.90),
    parent=waist_e, mat_=M_MERMAID_SKIN)
# Head
mer_head = empty("mer_head_e", (0, 0, 1.10), parent=waist_e)
smooth_sphere("mer_h", r=0.22, segs=22, rings=14, loc=(0, 0, 0),
              parent=mer_head, mat_=M_MERMAID_SKIN)
# Eyes (large anime-style)
for side in (-1, 1):
    smooth_sphere(f"mer_eye_{side}", r=0.06, loc=(side*0.09, -0.18, 0.02),
                  parent=mer_head, mat_=mat("mer_eye_white", (1,1,1,1), 0, 0.3))
    smooth_sphere(f"mer_iris_{side}", r=0.04, loc=(side*0.09, -0.21, 0.02),
                  parent=mer_head, mat_=M_MERMAID_TAIL)
    smooth_sphere(f"mer_pup_{side}", r=0.02, loc=(side*0.09, -0.23, 0.02),
                  parent=mer_head, mat_=M_DOLPHIN_EYE)
# Hair (long flowing red, multiple strands)
hair_e = empty("mer_hair_e", (0, 0.05, 0.10), parent=mer_head)
for i in range(8):
    a = (i / 8.0) * math.pi * 2
    rad = 0.20
    strand = beveled_cube(f"mer_hair{i}", (0.06, 0.06, 0.7),
                          loc=(rad*math.cos(a), rad*math.sin(a), -0.40),
                          parent=hair_e, mat_=M_MERMAID_HAIR)
    strand["_phase"] = i * 0.5
    strand.rotation_euler = (math.radians(8*math.cos(a)),
                             math.radians(8*math.sin(a)), 0)
# Lips (small smile)
beveled_cube("mer_lips", (0.07, 0.02, 0.02), loc=(0, -0.21, -0.10),
             parent=mer_head, mat_=mat("lips", (0.85, 0.30, 0.40, 1), 0, 0.5))

# Arms (flowing gracefully)
for side_idx, side in enumerate((-1, 1)):
    sh = empty(f"mer_sh{side_idx}", (side*0.28, 0, 0.85), parent=waist_e)
    sh.rotation_euler = (0, 0, math.radians(side*-30))
    cyl(f"mer_up{side_idx}", r=0.08, depth=0.40, segs=10,
        loc=(0, 0, -0.20), parent=sh, mat_=M_MERMAID_SKIN)
    el = empty(f"mer_el{side_idx}", (0, 0, -0.42), parent=sh)
    el.rotation_euler = (math.radians(30), 0, 0)
    cyl(f"mer_fa{side_idx}", r=0.07, depth=0.40, segs=10,
        loc=(0, 0, -0.20), parent=el, mat_=M_MERMAID_SKIN)
    # Hand
    smooth_sphere(f"mer_hand{side_idx}", r=0.07, loc=(0, 0, -0.45),
                  parent=el, mat_=M_MERMAID_SKIN)

# ============ DOLPHINS (8) ============
dolphins = []
for i in range(8):
    a = (i / 8.0) * math.pi * 2 + random.uniform(-0.2, 0.2)
    rad = random.uniform(12, 20)
    px, py = rad*math.cos(a), rad*math.sin(a)
    pz = random.uniform(6, 16)
    d_e = empty(f"dolphin_e{i}", (px, py, pz))
    d_e.rotation_euler = (0, 0, a + math.pi/2)
    # Body (streamlined)
    smooth_sphere(f"d_body{i}", r=0.5, segs=22, rings=14, loc=(0,0,0),
                  parent=d_e, mat_=M_DOLPHIN, scale=(2.3, 0.9, 1.0))
    # Belly lighter
    smooth_sphere(f"d_belly{i}", r=0.42, loc=(0, 0, -0.15),
                  parent=d_e, mat_=M_DOLPHIN_BELLY, scale=(2.0, 0.6, 0.5))
    # Head with rostrum (beak)
    smooth_cone(f"d_rostrum{i}", r1=0.20, r2=0.05, depth=0.45, segs=14,
                loc=(1.20, 0, -0.05), parent=d_e, mat_=M_DOLPHIN)
    # Eye
    for side in (-1, 1):
        smooth_sphere(f"d_eye{i}_{side}", r=0.05,
                      loc=(0.85, side*0.25, 0.10), parent=d_e, mat_=M_DOLPHIN_EYE)
    # Dorsal fin (top)
    fin = beveled_cube(f"d_dorsal{i}", (0.04, 0.45, 0.50), bevel_offset=0.04,
                       loc=(-0.10, 0, 0.45), parent=d_e, mat_=M_DOLPHIN)
    fin.rotation_euler = (math.radians(-15), 0, 0)
    # Pectoral fins (2 sides)
    for side in (-1, 1):
        pec = beveled_cube(f"d_pec{i}_{side}", (0.40, 0.04, 0.20), bevel_offset=0.03,
                           loc=(0.3, side*0.40, -0.10), parent=d_e, mat_=M_DOLPHIN)
        pec.rotation_euler = (0, math.radians(side*20), 0)
    # Tail fin (horizontal flukes)
    tail_e = empty(f"d_tail{i}", (-1.10, 0, 0), parent=d_e)
    fluke = beveled_cube(f"d_fluke{i}", (0.30, 0.80, 0.05), bevel_offset=0.04,
                         loc=(-0.10, 0, 0), parent=tail_e, mat_=M_DOLPHIN)
    fluke.rotation_euler = (math.radians(-15), 0, 0)
    dolphins.append({"e": d_e, "tail": tail_e, "phase": random.uniform(0, math.pi*2),
                     "orbit_rad": rad, "orbit_speed": random.uniform(0.3, 0.55),
                     "orbit_phase": a, "base_z": pz})

# ============ MANTA RAYS (4, planing) ============
mantas = []
for i in range(4):
    a = (i / 4.0) * math.pi * 2
    rad = random.uniform(15, 22)
    mx, my = rad*math.cos(a), rad*math.sin(a)
    mz = random.uniform(8, 14)
    m_e = empty(f"manta_e{i}", (mx, my, mz))
    m_e.rotation_euler = (0, 0, a + math.pi/2)
    # Body (diamond flat shape) - using flattened sphere
    smooth_sphere(f"m_body{i}", r=1.0, segs=24, rings=14, loc=(0,0,0),
                  parent=m_e, mat_=M_MANTA, scale=(2.5, 2.8, 0.20))
    # Belly
    smooth_sphere(f"m_belly{i}", r=0.85, loc=(0, 0, -0.08),
                  parent=m_e, mat_=M_MANTA_BELLY, scale=(2.0, 2.3, 0.15))
    # Head with cephalic horns (2 horns front)
    for side in (-1, 1):
        horn = smooth_cone(f"m_horn{i}_{side}", r1=0.10, r2=0.02, depth=0.40, segs=10,
                          loc=(2.0, side*0.20, 0.05), parent=m_e, mat_=M_MANTA)
        horn.rotation_euler = (0, math.radians(-30 + side*10), 0)
    # Wing edges (4 ripples per wing for animation)
    wings = []
    for side_idx, side in enumerate((-1, 1)):
        w_e = empty(f"m_w{i}_{side_idx}", (0, side*1.4, 0), parent=m_e)
        # Wing tip
        beveled_cube(f"m_w_tip{i}_{side_idx}", (1.5, 1.0, 0.04),
                     loc=(0, side*0.7, 0), parent=w_e, mat_=M_MANTA)
        wings.append((w_e, side))
    # Tail (thin whip-like)
    tail = cyl(f"m_tail{i}", r=0.06, depth=2.0, segs=10,
              loc=(-1.50, 0, -0.05), parent=m_e, mat_=M_MANTA)
    tail.rotation_euler = (0, math.radians(90), 0)
    mantas.append({"e": m_e, "wings": wings, "phase": random.uniform(0, math.pi*2),
                   "orbit_rad": rad, "orbit_speed": random.uniform(0.2, 0.4),
                   "orbit_phase": a, "base_z": mz})

# ============ FISH SCHOOL (100 small fish) ============
fish_school = []
for i in range(100):
    cluster = i // 25
    cluster_centers = [(15, 10, 10), (-12, 8, 8), (10, -14, 12), (-10, -12, 6)]
    cx, cy, cz = cluster_centers[cluster]
    fx = cx + random.uniform(-3, 3)
    fy = cy + random.uniform(-3, 3)
    fz = cz + random.uniform(-2, 2)
    mat_choice = [M_FISH1, M_FISH2, M_FISH3][cluster % 3]
    f_e = empty(f"fish_e{i}", (fx, fy, fz))
    f_e.rotation_euler = (0, 0, random.uniform(0, math.pi*2))
    # Body
    smooth_sphere(f"fish_b{i}", r=0.10, segs=12, rings=10, loc=(0,0,0),
                  parent=f_e, mat_=mat_choice, scale=(2.0, 0.7, 0.8))
    # Tail fin
    beveled_cube(f"fish_t{i}", (0.05, 0.04, 0.10), loc=(-0.18, 0, 0),
                 parent=f_e, mat_=mat_choice)
    fish_school.append({"e": f_e, "cluster": cluster, "phase": random.uniform(0, math.pi*2),
                        "base_x": fx, "base_y": fy, "base_z": fz})

# ============ CORAL (12 coral formations) ============
for i in range(12):
    a = random.uniform(0, math.pi*2)
    rad = random.uniform(5, 22)
    cx, cy = rad*math.cos(a), rad*math.sin(a)
    c_e = empty(f"coral_e{i}", (cx, cy, 0.3))
    color = [M_CORAL_PINK, M_CORAL_PURPLE, M_CORAL_YELLOW][i % 3]
    # 5 branches per coral
    for j in range(5):
        ang = (j / 5.0) * math.pi * 2
        # Stem
        seg = smooth_cone(f"coral{i}_b{j}", r1=0.12, r2=0.05,
                          depth=0.6 + random.uniform(0, 0.5), segs=10,
                          loc=(0.15*math.cos(ang), 0.15*math.sin(ang),
                               (0.6 + random.uniform(0, 0.5))/2),
                          parent=c_e, mat_=color)
        # Sub-branches
        for k in range(2):
            smooth_sphere(f"coral{i}_b{j}_s{k}", r=0.10,
                          loc=(0.15*math.cos(ang) + 0.10*math.cos(ang+k),
                               0.15*math.sin(ang) + 0.10*math.sin(ang+k),
                               (0.6 + random.uniform(0, 0.5)) + 0.05),
                          parent=c_e, mat_=color)

# ============ KELP (20 long algae strands) ============
kelps = []
for i in range(20):
    a = random.uniform(0, math.pi*2)
    rad = random.uniform(6, 28)
    kx, ky = rad*math.cos(a), rad*math.sin(a)
    k_e = empty(f"kelp_e{i}", (kx, ky, 0))
    height = random.uniform(6, 12)
    # 8 segments forming long strand
    for j in range(8):
        m_ = M_KELP_LIGHT if j % 2 == 0 else M_KELP
        seg = smooth_cone(f"kelp{i}_s{j}", r1=0.10-j*0.008, r2=0.08-j*0.008,
                          depth=height/8, segs=10,
                          loc=(0, 0, (j+0.5)*height/8),
                          parent=k_e, mat_=m_)
        # Leaf pairs (every 2 segs)
        if j % 2 == 0:
            for side in (-1, 1):
                leaf = beveled_cube(f"kelp{i}_l{j}_{side}", (0.10, 0.30, 0.03),
                                    loc=(side*0.20, 0, j*height/8),
                                    parent=k_e, mat_=M_KELP)
                leaf.rotation_euler = (math.radians(-10), 0, math.radians(side*30))
    k_e["_phase"] = random.uniform(0, math.pi*2)
    kelps.append(k_e)

# ============ AMPHORAS (8 broken pots) ============
for i in range(8):
    a = random.uniform(0, math.pi*2)
    rad = random.uniform(3, 12)
    ax, ay = rad*math.cos(a), rad*math.sin(a)
    am_e = empty(f"amph_e{i}", (ax, ay, 0.3))
    am_e.rotation_euler = (math.radians(random.uniform(-30, 30)),
                           math.radians(random.uniform(-30, 30)),
                           random.uniform(0, math.pi*2))
    # Body (ovoid)
    smooth_sphere(f"amph_body{i}", r=0.30, loc=(0, 0, 0.30),
                  parent=am_e, mat_=M_AMPHORA, scale=(1, 1, 1.5))
    # Neck
    cyl(f"amph_neck{i}", r=0.08, depth=0.15, segs=10,
        loc=(0, 0, 0.75), parent=am_e, mat_=M_AMPHORA)
    # Rim
    cyl(f"amph_rim{i}", r=0.12, depth=0.04, segs=14,
        loc=(0, 0, 0.85), parent=am_e, mat_=M_AMPHORA)
    # Decoration band gold
    cyl(f"amph_deco{i}", r=0.31, depth=0.05, segs=14,
        loc=(0, 0, 0.40), parent=am_e, mat_=M_AMPHORA_DECO)
    # 2 handles (curved)
    for side in (-1, 1):
        handle = beveled_cube(f"amph_h{i}_{side}", (0.04, 0.20, 0.10),
                             loc=(side*0.35, 0, 0.55), parent=am_e, mat_=M_AMPHORA)
        handle.rotation_euler = (0, math.radians(side*30), 0)
    # 40% broken (top removed visually with chip)
    if random.random() < 0.4:
        beveled_cube(f"amph_chip{i}", (0.30, 0.25, 0.15),
                     loc=(0, 0, 0.85), parent=am_e, mat_=M_AMPHORA_DECO)

# 50 GOLD COINS scattered
coins = []
for i in range(50):
    a = random.uniform(0, math.pi*2)
    rad = random.uniform(1, 8)
    cx, cy = rad*math.cos(a), rad*math.sin(a)
    cz = 0.15 + random.uniform(-0.05, 0.10)
    coin = cyl(f"coin{i}", r=0.10, depth=0.02, segs=14,
              loc=(cx, cy, cz), mat_=M_GOLD_COIN)
    coin.rotation_euler = (random.uniform(-0.3, 0.3),
                           random.uniform(-0.3, 0.3),
                           random.uniform(0, math.pi*2))
    coin["_phase"] = random.uniform(0, math.pi*2)
    coins.append(coin)

# ============ BUBBLES (50 rising) ============
bubbles = []
for i in range(50):
    a = random.uniform(0, math.pi*2)
    rad = random.uniform(2, 25)
    bx, by = rad*math.cos(a), rad*math.sin(a)
    bz = random.uniform(0.5, 5)
    b = smooth_sphere(f"bubble{i}", r=random.uniform(0.08, 0.20), segs=12, rings=8,
                     loc=(bx, by, bz), mat_=M_BUBBLE)
    b["_phase"] = random.uniform(0, math.pi*2)
    b["_speed"] = random.uniform(1.5, 3.5)
    b["_base_x"] = bx; b["_base_y"] = by; b["_base_z"] = bz
    bubbles.append(b)

# ============ HOT VENTS (3 thermal vents with bubbles + smoke) ============
vents = []
for i in range(3):
    vx = random.uniform(-15, 15)
    vy = random.uniform(-15, 15)
    v_e = empty(f"vent_e{i}", (vx, vy, 0))
    # Cone vent
    smooth_cone(f"vent_cone{i}", r1=0.7, r2=0.25, depth=1.2, segs=14,
                loc=(0, 0, 0.6), parent=v_e, mat_=M_ROCK)
    # Lava glow inside
    smooth_sphere(f"vent_lava{i}", r=0.25, loc=(0, 0, 1.1),
                  parent=v_e, mat_=M_LAVA)
    # 4 smoke puffs rising
    for j in range(4):
        sm = smooth_sphere(f"vent_smoke{i}_{j}", r=0.40,
                          loc=(random.uniform(-0.2,0.2), random.uniform(-0.2,0.2), 1.5 + j*0.7),
                          parent=v_e, mat_=M_VENT_SMOKE)
        sm["_phase"] = random.uniform(0, math.pi*2)
    vents.append(v_e)

# ============ 30 SEDIMENT particles ============
sediments = []
for i in range(30):
    sx = random.uniform(-25, 25)
    sy = random.uniform(-25, 25)
    sz = random.uniform(1, 15)
    sd = smooth_sphere(f"sed{i}", r=random.uniform(0.06, 0.12), segs=8, rings=6,
                      loc=(sx, sy, sz), mat_=M_SEDIMENT)
    sd["_phase"] = random.uniform(0, math.pi*2)
    sd["_base_x"] = sx; sd["_base_y"] = sy; sd["_base_z"] = sz
    sediments.append(sd)

# ============ ANIMATION ============
fps = 30; duration_s = 6; total_frames = fps * duration_s

# Bubbles rise
for b in bubbles:
    phase = b["_phase"]; speed = b["_speed"]
    bx, by, bz = b["_base_x"], b["_base_y"], b["_base_z"]
    for f in range(1, total_frames + 1, 3):
        t = (f - 1) / fps
        z = bz + (speed * t) % 22
        x = bx + math.sin(t * 2.0 + phase) * 0.25
        y = by + math.cos(t * 1.8 + phase) * 0.25
        s = 1 + math.sin(t * 4.0 + phase) * 0.1
        b.location = (x, y, z)
        b.scale = (s, s, s)
        b.keyframe_insert("location", frame=f)
        b.keyframe_insert("scale", frame=f)

# Dolphins orbit + body undulation
for d in dolphins:
    phase = d["phase"]
    rad = d["orbit_rad"]
    speed = d["orbit_speed"]
    base_phase = d["orbit_phase"]
    base_z = d["base_z"]
    tail = d["tail"]
    for f in range(1, total_frames + 1, 3):
        t = (f - 1) / fps
        a = base_phase + speed * t
        x = rad * math.cos(a)
        y = rad * math.sin(a)
        z = base_z + math.sin(t * 1.5 + phase) * 0.8
        d["e"].location = (x, y, z)
        d["e"].rotation_euler = (math.sin(t * 2.0 + phase) * math.radians(8), 0, a + math.pi/2)
        d["e"].keyframe_insert("location", frame=f)
        d["e"].keyframe_insert("rotation_euler", frame=f)
        # Tail oscillate
        tail.rotation_euler = (math.sin(t * 3.5 + phase) * math.radians(15), 0, 0)
        tail.keyframe_insert("rotation_euler", frame=f)

# Manta rays gentle wing flap + slow orbit
for m in mantas:
    phase = m["phase"]
    rad = m["orbit_rad"]
    speed = m["orbit_speed"]
    base_phase = m["orbit_phase"]
    base_z = m["base_z"]
    for f in range(1, total_frames + 1, 3):
        t = (f - 1) / fps
        a = base_phase + speed * t
        x = rad * math.cos(a)
        y = rad * math.sin(a)
        z = base_z + math.sin(t * 0.8 + phase) * 0.5
        m["e"].location = (x, y, z)
        m["e"].rotation_euler = (math.sin(t * 0.7 + phase) * math.radians(5), 0, a + math.pi/2)
        m["e"].keyframe_insert("location", frame=f)
        m["e"].keyframe_insert("rotation_euler", frame=f)
        # Wings flap slow
        flap = math.sin(t * 1.5 + phase) * math.radians(20)
        for w_e, side in m["wings"]:
            w_e.rotation_euler = (side * flap, 0, 0)
            w_e.keyframe_insert("rotation_euler", frame=f)

# Fish school swim (cluster movement)
for fish in fish_school:
    phase = fish["phase"]
    bx, by, bz = fish["base_x"], fish["base_y"], fish["base_z"]
    cluster = fish["cluster"]
    for f in range(1, total_frames + 1, 4):
        t = (f - 1) / fps
        # Cluster drift
        cluster_t = t * (0.5 + cluster*0.1)
        x = bx + math.sin(cluster_t + phase) * 1.5
        y = by + math.cos(cluster_t * 0.8 + phase) * 1.5
        z = bz + math.sin(cluster_t * 0.6 + phase) * 0.8
        fish["e"].location = (x, y, z)
        # Heading
        fish["e"].rotation_euler = (0, 0, math.atan2(y - by, x - bx) + math.pi/2)
        fish["e"].keyframe_insert("location", frame=f)
        fish["e"].keyframe_insert("rotation_euler", frame=f)

# Mermaid tail undulate + body sway + hair flow
for f in range(1, total_frames + 1, 3):
    t = (f - 1) / fps
    # Tail swish
    tail_pivot.rotation_euler = (0, math.sin(t * 2.0) * math.radians(15),
                                 math.sin(t * 1.5) * math.radians(10))
    tail_pivot.keyframe_insert("rotation_euler", frame=f)
    # Body sway
    mermaid_base.location.z = 4 + math.sin(t * 1.0) * 0.25
    mermaid_base.rotation_euler = (math.sin(t * 0.7) * math.radians(5), 0,
                                   math.radians(-30) + math.sin(t * 0.9) * math.radians(10))
    mermaid_base.keyframe_insert("location", frame=f)
    mermaid_base.keyframe_insert("rotation_euler", frame=f)
    # Hair flow
    hair_e.rotation_euler = (math.sin(t * 1.2) * math.radians(8),
                             math.cos(t * 1.0) * math.radians(8),
                             math.sin(t * 0.8) * math.radians(5))
    hair_e.keyframe_insert("rotation_euler", frame=f)

# Kelp wave
for k in kelps:
    phase = k["_phase"]
    for f in range(1, total_frames + 1, 4):
        t = (f - 1) / fps
        k.rotation_euler = (math.sin(t * 1.0 + phase) * math.radians(8),
                            math.cos(t * 0.9 + phase) * math.radians(6),
                            0)
        k.keyframe_insert("rotation_euler", frame=f)

# Gold coins shimmer + rotate
for coin in coins:
    if "_phase" not in coin.keys():
        continue
    phase = coin["_phase"]
    base_rot_z = coin.rotation_euler.z
    for f in range(1, total_frames + 1, 5):
        t = (f - 1) / fps
        s = 1 + math.sin(t * 2.5 + phase) * 0.10
        coin.scale = (s, s, s)
        coin.rotation_euler = (0, 0, base_rot_z + t * 0.3)
        coin.keyframe_insert("scale", frame=f)
        coin.keyframe_insert("rotation_euler", frame=f)

# Sunrays sway gently
for ri, ray in enumerate(sun_rays):
    base_rx = ray.rotation_euler.x
    base_ry = ray.rotation_euler.y
    phase = ri * 0.7
    for f in range(1, total_frames + 1, 6):
        t = (f - 1) / fps
        ray.rotation_euler = (base_rx + math.sin(t * 0.6 + phase) * math.radians(2),
                              base_ry + math.cos(t * 0.5 + phase) * math.radians(2),
                              0)
        s = 1 + math.sin(t * 1.5 + phase) * 0.12
        ray.scale = (s, s, 1)
        ray.keyframe_insert("rotation_euler", frame=f)
        ray.keyframe_insert("scale", frame=f)

# Hot vent lava pulse
for vi, v in enumerate(vents):
    for f in range(1, total_frames + 1, 4):
        t = (f - 1) / fps
        v.location.z = math.sin(t * 1.0 + vi) * 0.05
        v.keyframe_insert("location", frame=f)

# Sediments drift
for sd in sediments:
    phase = sd["_phase"]
    bx, by, bz = sd["_base_x"], sd["_base_y"], sd["_base_z"]
    for f in range(1, total_frames + 1, 5):
        t = (f - 1) / fps
        x = bx + math.sin(t * 0.6 + phase) * 1.5
        y = by + math.cos(t * 0.5 + phase) * 1.5
        z = bz + (t * 0.5) % 12.0
        sd.location = (x, y, z)
        s = 1 + math.sin(t * 2.0 + phase) * 0.3
        sd.scale = (s, s, s)
        sd.keyframe_insert("location", frame=f)
        sd.keyframe_insert("scale", frame=f)

# Poseidon subtle pulse breath
for f in range(1, total_frames + 1, 8):
    t = (f - 1) / fps
    s = 1 + math.sin(t * 0.5) * 0.015
    poseidon_base.scale = (s, s, s)
    poseidon_base.keyframe_insert("scale", frame=f)

# Trident pulse
for f in range(1, total_frames + 1, 4):
    t = (f - 1) / fps
    s = 1 + math.sin(t * 2.5) * 0.05
    trident_e.scale = (s, s, s)
    trident_e.keyframe_insert("scale", frame=f)

# Oeil dorée pulse rotate
for f in range(1, total_frames + 1, 4):
    t = (f - 1) / fps
    oeil_e.rotation_euler = (math.radians(90), 0, t * 0.3)
    s = 1 + math.sin(t * 2.0) * 0.05
    oeil_e.scale = (s, s, s)
    oeil_e.keyframe_insert("rotation_euler", frame=f)
    oeil_e.keyframe_insert("scale", frame=f)

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
out_glb = os.path.join(out_dir, "pbr_atlantis_submerged_proc.glb")

bpy.ops.object.select_all(action='SELECT')
bpy.ops.export_scene.gltf(
    filepath=out_glb, export_format='GLB',
    export_animations=True, export_apply=False, export_yup=True, use_selection=False,
)
size_mb = os.path.getsize(out_glb) / (1024 * 1024)
print(f"[proc_atlantis_submerged_temple] DONE → {out_glb} ({size_mb:.2f} MB)")
print("[proc_atlantis_submerged_temple] Greek temple ruins + 8 cols broken + Poseidon trident + Eye disc + Mermaid full + 8 dolphins + 4 manta rays + 100 fish school + 12 coral + 20 kelp + 8 amphoras + 50 coins + 50 bubbles + 3 hot vents + 30 sediments + 8 sunrays")
