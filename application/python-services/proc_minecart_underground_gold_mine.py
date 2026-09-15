"""
proc_minecart_underground_gold_mine.py — 198e procédural AuroraIA (62e qualité)
Mine d'or souterraine : galerie + rails sinueux + 3 minecarts + 5 mineurs + treuil + monte-charge + cristaux + bats
"""
import bpy, bmesh, math, random, os

random.seed(0x6017198)

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
M_DARK = mat("dark", (0.04, 0.04, 0.06, 1.0), 0.0, 0.85)
M_ROCK = mat("rock", (0.20, 0.18, 0.16, 1.0), 0.0, 0.85)
M_ROCK_LIT = mat("rock_lit", (0.32, 0.28, 0.22, 1.0), 0.0, 0.75, emission=(0.30,0.25,0.20), emission_strength=0.6)
M_DIRT = mat("dirt", (0.18, 0.13, 0.09, 1.0), 0.0, 0.85)
M_FLOOR = mat("floor", (0.22, 0.18, 0.14, 1.0), 0.0, 0.80)
M_WOOD = mat("wood", (0.30, 0.18, 0.10, 1.0), 0.0, 0.78)
M_WOOD_OLD = mat("wood_old", (0.45, 0.30, 0.15, 1.0), 0.0, 0.72, emission=(0.40,0.25,0.12), emission_strength=0.3)

# Rails
M_RAIL = mat("rail", (0.45, 0.45, 0.48, 1.0), 0.90, 0.30, emission=(0.40,0.40,0.42), emission_strength=0.5)
M_SLEEPER = mat("sleeper", (0.30, 0.20, 0.10, 1.0), 0.0, 0.85)

# Minecart
M_CART = mat("cart", (0.30, 0.22, 0.15, 1.0), 0.3, 0.55, emission=(0.25,0.20,0.13), emission_strength=0.3)
M_CART_METAL = mat("cart_metal", (0.55, 0.50, 0.48, 1.0), 0.85, 0.40, emission=(0.50,0.45,0.42), emission_strength=0.4)
M_WHEEL = mat("wheel_m", (0.12, 0.10, 0.08, 1.0), 0.85, 0.45, emission=(0.15,0.12,0.10), emission_strength=0.3)
M_WHEEL_RIM = mat("wheel_rim_m", (0.45, 0.45, 0.48, 1.0), 0.90, 0.30, emission=(0.40,0.40,0.42), emission_strength=0.4)

# Gold
M_GOLD = mat("gold", (1.0, 0.78, 0.25, 1.0), 0.95, 0.18, emission=(0.95,0.72,0.22), emission_strength=2.5)
M_GOLD_BRIGHT = mat("gold_bright", (1.0, 0.85, 0.35, 1.0), 0.95, 0.15, emission=(1.0,0.85,0.40), emission_strength=4.5)
M_GOLD_RICH = mat("gold_rich", (0.95, 0.78, 0.30, 1.0), 0.95, 0.22, emission=(0.90,0.72,0.25), emission_strength=1.8)

# Crystals
M_CRYSTAL_BLUE = mat("c_blue", (0.40, 0.75, 1.0, 1.0), 0.0, 0.10, emission=(0.50,0.85,1.0), emission_strength=8.0, alpha=0.75)
M_CRYSTAL_PURPLE = mat("c_purple", (0.75, 0.40, 1.0, 1.0), 0.0, 0.10, emission=(0.80,0.45,1.0), emission_strength=7.0, alpha=0.75)
M_CRYSTAL_GREEN = mat("c_green", (0.40, 1.0, 0.55, 1.0), 0.0, 0.10, emission=(0.45,1.0,0.60), emission_strength=8.5, alpha=0.75)
M_CRYSTAL_WHITE = mat("c_white", (0.92, 0.95, 1.0, 1.0), 0.0, 0.10, emission=(0.95,0.95,1.0), emission_strength=10.0, alpha=0.75)

# Miners
M_MINER_OVERALL = mat("miner_overall", (0.30, 0.20, 0.10, 1.0), 0.0, 0.70, emission=(0.25,0.18,0.10), emission_strength=0.4)
M_MINER_OVERALL_RED = mat("miner_overall_r", (0.45, 0.20, 0.15, 1.0), 0.0, 0.60, emission=(0.40,0.18,0.13), emission_strength=0.5)
M_MINER_OVERALL_BLUE = mat("miner_overall_b", (0.20, 0.30, 0.45, 1.0), 0.0, 0.60, emission=(0.18,0.28,0.40), emission_strength=0.5)
M_SKIN = mat("skin", (0.85, 0.70, 0.55, 1.0), 0.0, 0.55, emission=(0.75,0.62,0.48), emission_strength=0.3)
M_SKIN_DIRTY = mat("skin_dirty", (0.55, 0.42, 0.30, 1.0), 0.0, 0.7, emission=(0.45,0.35,0.25), emission_strength=0.3)
M_BEARD = mat("beard", (0.45, 0.30, 0.20, 1.0), 0.0, 0.80)
M_HAIR = mat("hair", (0.30, 0.18, 0.10, 1.0), 0.0, 0.80)
M_HELMET = mat("helmet", (0.85, 0.55, 0.20, 1.0), 0.3, 0.45, emission=(0.78,0.50,0.18), emission_strength=0.5)
M_HELMET_LAMP = mat("helmet_lamp", (1.0, 0.92, 0.65, 1.0), 0.0, 0.10, emission=(1.0,0.95,0.70), emission_strength=22.0)
M_HELMET_LAMP_BEAM = mat("h_lamp_beam", (1.0, 0.92, 0.65, 0.4), 0.0, 0.05, emission=(1.0,0.92,0.70), emission_strength=4.0, alpha=0.4)

# Pickaxe
M_PICKAXE_HANDLE = mat("pick_h", (0.30, 0.18, 0.10, 1.0), 0.0, 0.75)
M_PICKAXE_HEAD = mat("pick_head", (0.35, 0.30, 0.28, 1.0), 0.85, 0.40, emission=(0.30,0.28,0.26), emission_strength=0.4)

# Bats
M_BAT = mat("bat", (0.10, 0.08, 0.06, 1.0), 0.0, 0.55, emission=(0.12,0.10,0.08), emission_strength=0.3)
M_BAT_EYE = mat("bat_eye", (1.0, 0.30, 0.15, 1.0), 0.0, 0.15, emission=(1.0,0.35,0.18), emission_strength=4.0)

# Lanterns
M_LANTERN = mat("lantern", (1.0, 0.60, 0.20, 1.0), 0.0, 0.30, emission=(1.0,0.65,0.25), emission_strength=14.0)
M_LANTERN_FRAME = mat("lantern_frame", (0.30, 0.20, 0.10, 1.0), 0.3, 0.55)

# Particles
M_DUST = mat("dust", (0.55, 0.45, 0.35, 1.0), 0.0, 0.55, emission=(0.55,0.45,0.35), emission_strength=2.0, alpha=0.5)
M_SPORE = mat("spore", (0.90, 0.85, 0.65, 1.0), 0.0, 0.45, emission=(0.92,0.85,0.65), emission_strength=4.5)

# ============ MINE TUNNEL STRUCTURE ============
mine_e = empty("mine", loc=(0, 0, 0))

# Floor (uneven rock surface)
floor = beveled_cube("floor", (45, 30, 0.4), bevel_offset=0.05, loc=(0, 0, -0.2),
                    parent=mine_e, mat_=M_FLOOR)

# Walls (massive rock around)
# Left wall
beveled_cube("wall_left", (45, 0.6, 8.0), bevel_offset=0.10,
             loc=(0, -14, 4.0), parent=mine_e, mat_=M_ROCK)
# Right wall
beveled_cube("wall_right", (45, 0.6, 8.0), bevel_offset=0.10,
             loc=(0, 14, 4.0), parent=mine_e, mat_=M_ROCK)
# Back wall
beveled_cube("wall_back", (0.6, 28, 8.0), bevel_offset=0.10,
             loc=(22.5, 0, 4.0), parent=mine_e, mat_=M_ROCK)
# Front (smaller, opening)
for side in (-1, 1):
    beveled_cube(f"wall_front_{side}", (0.6, 8, 8.0), bevel_offset=0.10,
                 loc=(-22.5, side*9, 4.0), parent=mine_e, mat_=M_ROCK)
# Front top (lintel)
beveled_cube("wall_front_top", (0.6, 28, 2.0), bevel_offset=0.10,
             loc=(-22.5, 0, 7.0), parent=mine_e, mat_=M_ROCK)

# CEILING with stalactites
ceiling = beveled_cube("ceiling", (45, 30, 0.4), bevel_offset=0.05,
                       loc=(0, 0, 8.0), parent=mine_e, mat_=M_ROCK)
# 15 stalactites hanging
for i in range(15):
    sx = random.uniform(-20, 20)
    sy = random.uniform(-12, 12)
    sl = random.uniform(0.6, 1.8)
    smooth_cone(f"stal{i}", r1=random.uniform(0.20, 0.40), r2=0.02, depth=sl, segs=10,
                loc=(sx, sy, 8.0 - sl/2), parent=mine_e, mat_=M_ROCK)

# Rock outcroppings (for atmosphere - 12)
for i in range(12):
    a = random.uniform(0, math.pi*2)
    rad = random.uniform(10, 13)
    rx, ry = rad*math.cos(a), rad*math.sin(a)
    smooth_sphere(f"rock_out{i}", r=random.uniform(0.8, 1.8),
                  loc=(rx, ry, random.uniform(0.5, 3)), parent=mine_e, mat_=M_ROCK,
                  scale=(random.uniform(0.8,1.3), random.uniform(0.8,1.3),
                         random.uniform(0.6,1.0)))

# Floor rocks (rubble - 25 small)
for i in range(25):
    rx = random.uniform(-21, 21)
    ry = random.uniform(-13, 13)
    smooth_sphere(f"rubble{i}", r=random.uniform(0.20, 0.45),
                  loc=(rx, ry, 0.15), parent=mine_e, mat_=M_ROCK,
                  scale=(1, 1, 0.5))

# ============ RAILS (sinuous, S-curve track) ============
# Create a curving path made of straight + curved segments
# Main long rail going through center, with slight curves
rail_segs = 30
rail_points = []
for i in range(rail_segs + 1):
    t = i / rail_segs
    x = -20 + t * 40
    y = math.sin(t * math.pi * 2) * 2.5  # S-curve
    z = 0.05
    rail_points.append((x, y, z))

# Build 2 rails (left + right of track) using cylinders connecting consecutive points
rails_obj = []
for side in (-0.65, 0.65):
    for i in range(len(rail_points) - 1):
        p1 = rail_points[i]; p2 = rail_points[i+1]
        # Adjust Y for side
        y1 = p1[1] + side; y2 = p2[1] + side
        dx = p2[0] - p1[0]; dy = y2 - y1; dz = p2[2] - p1[2]
        length = math.sqrt(dx*dx + dy*dy + dz*dz)
        mx = (p1[0] + p2[0]) / 2
        my = (y1 + y2) / 2
        mz = (p1[2] + p2[2]) / 2
        seg = cyl(f"rail_{side}_{i}", r=0.05, depth=length, segs=8,
                 loc=(mx, my, mz), parent=mine_e, mat_=M_RAIL)
        # Orient along direction
        yaw = math.atan2(dy, dx)
        pitch = math.atan2(math.sqrt(dx*dx + dy*dy), dz) - math.pi/2
        seg.rotation_euler = (0, 0, 0)  # we'll set after via matrix
        seg.rotation_euler = (math.atan2(dz, math.sqrt(dx*dx + dy*dy)),
                              math.radians(90),
                              math.atan2(dy, dx))
        # Simpler approach: rotate Y by 90 (to make cylinder lie along X), then yaw around Z
        seg.rotation_euler = (0, math.radians(90), yaw)
        rails_obj.append(seg)

# Sleepers (15)
for i in range(0, rail_segs + 1, 2):
    px, py, pz = rail_points[i]
    beveled_cube(f"sleeper{i}", (0.30, 1.8, 0.10), bevel_offset=0.02,
                 loc=(px, py, -0.05), parent=mine_e, mat_=M_SLEEPER)

# Side branching track (small dead-end)
branch_e = empty("branch", (10, 0, 0), parent=mine_e)
for i in range(10):
    px = i * 1.0
    py = 8 + i * 0.5  # angled
    pz = 0.05
    if i < 9:
        # Two rails
        for s in (-0.65, 0.65):
            seg = cyl(f"branch_rail_{i}_{s}", r=0.04, depth=1.0, segs=8,
                     loc=(px+0.5, py+0.25 + s*math.cos(0.5), pz), parent=branch_e, mat_=M_RAIL)
            seg.rotation_euler = (0, math.radians(90), math.atan2(0.5, 1.0))
    # Sleeper
    beveled_cube(f"branch_sleeper{i}", (0.20, 1.6, 0.08),
                 loc=(px, py, -0.05), parent=branch_e, mat_=M_SLEEPER)

# ============ 3 MINECARTS (wagonnets) ============
def make_minecart(name, loc, gold_fill="full", color=M_CART):
    base = empty(name, loc)
    # Body (open top box)
    # Walls (4 sides)
    beveled_cube(f"{name}_w_left", (1.6, 0.10, 0.85), bevel_offset=0.04,
                 loc=(0, -0.45, 0.5), parent=base, mat_=color)
    beveled_cube(f"{name}_w_right", (1.6, 0.10, 0.85), bevel_offset=0.04,
                 loc=(0, 0.45, 0.5), parent=base, mat_=color)
    beveled_cube(f"{name}_w_back", (0.10, 1.0, 0.85),
                 loc=(-0.80, 0, 0.5), parent=base, mat_=color)
    beveled_cube(f"{name}_w_front", (0.10, 1.0, 0.85),
                 loc=(0.80, 0, 0.5), parent=base, mat_=color)
    # Bottom
    beveled_cube(f"{name}_bottom", (1.7, 1.1, 0.10), bevel_offset=0.04,
                 loc=(0, 0, 0.15), parent=base, mat_=color)
    # Metal reinforcement bands (4)
    for x_pos in (-0.7, 0.7):
        for side in (-1, 1):
            beveled_cube(f"{name}_metal_h_{x_pos}_{side}", (0.05, 0.05, 0.95),
                         loc=(x_pos, side*0.45, 0.55), parent=base, mat_=M_CART_METAL)
    # Horizontal top rim
    cyl(f"{name}_rim_top", r=0.05, depth=1.7, segs=8,
        loc=(0, 0.45, 0.95), parent=base, mat_=M_CART_METAL).rotation_euler = (0, math.radians(90), 0)
    cyl(f"{name}_rim_top_b", r=0.05, depth=1.7, segs=8,
        loc=(0, -0.45, 0.95), parent=base, mat_=M_CART_METAL).rotation_euler = (0, math.radians(90), 0)

    # GOLD/ORE FILL inside
    if gold_fill == "full":
        # Heaping mound of gold nuggets
        for i in range(15):
            nx = random.uniform(-0.7, 0.7)
            ny = random.uniform(-0.35, 0.35)
            nz = 0.55 + random.uniform(0, 0.30)
            smooth_sphere(f"{name}_nug{i}", r=random.uniform(0.10, 0.18), segs=14, rings=10,
                          loc=(nx, ny, nz), parent=base, mat_=M_GOLD_BRIGHT,
                          scale=(1, 1, 0.7))
    elif gold_fill == "partial":
        # Some gold + dirt
        for i in range(8):
            nx = random.uniform(-0.7, 0.7)
            ny = random.uniform(-0.35, 0.35)
            nz = 0.42 + random.uniform(0, 0.15)
            m_ = M_GOLD_BRIGHT if random.random() < 0.5 else M_ROCK
            smooth_sphere(f"{name}_pg{i}", r=random.uniform(0.10, 0.16), segs=14, rings=10,
                          loc=(nx, ny, nz), parent=base, mat_=m_,
                          scale=(1, 1, 0.7))

    # 4 WHEELS (2 axes)
    wheels = []
    for ax_idx, ax_x in enumerate((-0.55, 0.55)):
        for side_idx, side in enumerate((-1, 1)):
            w_e = empty(f"{name}_wheel_e{ax_idx}_{side_idx}", (ax_x, side*0.55, 0), parent=base)
            cyl(f"{name}_wheel{ax_idx}_{side_idx}", r=0.18, depth=0.05, segs=20,
                loc=(0,0,0), parent=w_e, mat_=M_WHEEL).rotation_euler = (math.radians(90), 0, 0)
            cyl(f"{name}_wrim{ax_idx}_{side_idx}", r=0.20, depth=0.04, segs=20,
                loc=(0,0,0), parent=w_e, mat_=M_WHEEL_RIM).rotation_euler = (math.radians(90), 0, 0)
            # Spokes (6)
            for s in range(6):
                a = (s / 6.0) * math.pi * 2
                beveled_cube(f"{name}_spoke{ax_idx}_{side_idx}_{s}",
                             (0.03, 0.02, 0.16),
                             loc=(0, 0, 0), parent=w_e, mat_=M_WHEEL_RIM).rotation_euler = (math.radians(90), a, 0)
            wheels.append(w_e)
    # Axle bars
    for ax_x in (-0.55, 0.55):
        cyl(f"{name}_axle_{ax_x}", r=0.04, depth=1.2, segs=10,
            loc=(ax_x, 0, 0), parent=base, mat_=M_CART_METAL).rotation_euler = (math.radians(90), 0, 0)

    # Coupling hook (front)
    cyl(f"{name}_coupling", r=0.04, depth=0.25, segs=10,
        loc=(0.95, 0, 0.4), parent=base, mat_=M_CART_METAL).rotation_euler = (0, math.radians(90), 0)

    return {"root": base, "wheels": wheels}

# 3 minecarts spaced along track
cart1 = make_minecart("cart1", (-12, math.sin(-12/40 * math.pi * 2 + math.pi) * 2.5 + 0, 0.35),
                      gold_fill="full", color=M_CART)
cart2 = make_minecart("cart2", (-3, math.sin(-3/40 * math.pi * 2 + math.pi) * 2.5 + 0, 0.35),
                      gold_fill="partial", color=M_CART)
cart3 = make_minecart("cart3", (8, math.sin(8/40 * math.pi * 2 + math.pi) * 2.5 + 0, 0.35),
                      gold_fill="full", color=M_CART)
carts = [cart1, cart2, cart3]

# ============ 5 MINEURS ============
def make_miner(name, loc, overall_mat, action="pickaxe", facing=0):
    base = empty(name, loc)
    base.rotation_euler = (0, 0, facing)
    # 2 legs (overall trouser)
    for side_idx, side in enumerate((-1, 1)):
        cyl(f"{name}_leg{side_idx}", r=0.12, depth=0.85, segs=10,
            loc=(side*0.15, 0, 0.42), parent=base, mat_=overall_mat)
        # Boot
        beveled_cube(f"{name}_boot{side_idx}", (0.20, 0.30, 0.15),
                     loc=(side*0.15, 0.05, 0.08), parent=base, mat_=M_DARK)
    # Torso (overall full)
    beveled_cube(f"{name}_torso", (0.50, 0.35, 0.85), bevel_offset=0.05,
                 loc=(0, 0, 1.30), parent=base, mat_=overall_mat)
    # Suspenders/straps (2)
    for side in (-1, 1):
        beveled_cube(f"{name}_strap_{side}", (0.06, 0.04, 0.70),
                     loc=(side*0.15, -0.18, 1.30), parent=base, mat_=overall_mat)
    # Belt
    beveled_cube(f"{name}_belt", (0.55, 0.40, 0.10), loc=(0, 0, 0.90),
                 parent=base, mat_=M_DARK)
    # Head
    head_e = empty(f"{name}_head_e", (0, 0, 1.90), parent=base)
    smooth_sphere(f"{name}_head", r=0.18, segs=20, rings=14, loc=(0, 0, 0),
                  parent=head_e, mat_=M_SKIN_DIRTY)
    # Eyes (squinting from dust)
    for side in (-1, 1):
        smooth_sphere(f"{name}_eye_{side}", r=0.025,
                      loc=(side*0.06, -0.15, 0.03), parent=head_e,
                      mat_=mat(f"{name}_ew", (1,1,1,1), 0, 0.3))
    # Nose
    smooth_sphere(f"{name}_nose", r=0.04, loc=(0, -0.17, -0.04),
                  parent=head_e, mat_=M_SKIN_DIRTY)
    # Mouth
    beveled_cube(f"{name}_mouth", (0.06, 0.02, 0.02), loc=(0, -0.17, -0.10),
                 parent=head_e, mat_=M_DARK)
    # BEARD (typical miner)
    smooth_sphere(f"{name}_beard", r=0.13,
                  loc=(0, -0.10, -0.15), parent=head_e, mat_=M_BEARD,
                  scale=(1.3, 0.6, 1.0))
    # HELMET (yellow/orange hardhat)
    helmet_e = empty(f"{name}_helmet_e", (0, 0, 0.20), parent=head_e)
    # Brim
    cyl(f"{name}_helmet_brim", r=0.24, depth=0.04, segs=18,
        loc=(0, 0, -0.02), parent=helmet_e, mat_=M_HELMET)
    # Dome
    smooth_sphere(f"{name}_helmet_dome", r=0.20, segs=18, rings=12,
                  loc=(0, 0, 0.05), parent=helmet_e, mat_=M_HELMET,
                  scale=(1, 1, 0.85))
    # HEADLAMP (front, glowing bright)
    cyl(f"{name}_lamp_housing", r=0.07, depth=0.06, segs=12,
        loc=(0, -0.18, 0.02), parent=helmet_e, mat_=M_CART_METAL).rotation_euler = (math.radians(90), 0, 0)
    cyl(f"{name}_lamp_lens", r=0.06, depth=0.03, segs=12,
        loc=(0, -0.22, 0.02), parent=helmet_e, mat_=M_HELMET_LAMP).rotation_euler = (math.radians(90), 0, 0)
    # Lamp beam (small cone forward)
    beam = smooth_cone(f"{name}_lamp_beam", r1=0.06, r2=0.50, depth=2.5, segs=10,
                       loc=(0, -1.5, 0.02), parent=helmet_e, mat_=M_HELMET_LAMP_BEAM)
    beam.rotation_euler = (math.radians(-90), 0, 0)

    # ARMS - 2 arms with pickaxe (swing motion)
    # Right arm raised back (mid swing)
    r_sh = empty(f"{name}_r_sh", (0.28, 0, 1.65), parent=base)
    if action == "pickaxe":
        r_sh.rotation_euler = (math.radians(-120), 0, math.radians(-15))
    else:
        r_sh.rotation_euler = (math.radians(-10), 0, 0)
    cyl(f"{name}_r_up", r=0.08, depth=0.40, segs=10,
        loc=(0, 0, -0.20), parent=r_sh, mat_=overall_mat)
    r_el = empty(f"{name}_r_el", (0, 0, -0.42), parent=r_sh)
    cyl(f"{name}_r_fa", r=0.07, depth=0.38, segs=10,
        loc=(0, 0, -0.20), parent=r_el, mat_=M_SKIN_DIRTY)
    r_hand = empty(f"{name}_r_hand", (0, 0, -0.42), parent=r_el)
    smooth_sphere(f"{name}_r_hand_g", r=0.08, loc=(0, 0, 0),
                  parent=r_hand, mat_=M_SKIN_DIRTY)

    # Left arm forward (gripping pickaxe handle)
    l_sh = empty(f"{name}_l_sh", (-0.28, 0, 1.65), parent=base)
    if action == "pickaxe":
        l_sh.rotation_euler = (math.radians(-65), 0, math.radians(15))
    else:
        l_sh.rotation_euler = (math.radians(-10), 0, 0)
    cyl(f"{name}_l_up", r=0.08, depth=0.40, segs=10,
        loc=(0, 0, -0.20), parent=l_sh, mat_=overall_mat)
    l_el = empty(f"{name}_l_el", (0, 0, -0.42), parent=l_sh)
    l_el.rotation_euler = (math.radians(40), 0, 0)
    cyl(f"{name}_l_fa", r=0.07, depth=0.38, segs=10,
        loc=(0, 0, -0.20), parent=l_el, mat_=M_SKIN_DIRTY)
    l_hand = empty(f"{name}_l_hand", (0, 0, -0.42), parent=l_el)
    smooth_sphere(f"{name}_l_hand_g", r=0.08, loc=(0, 0, 0),
                  parent=l_hand, mat_=M_SKIN_DIRTY)

    # PICKAXE (held with both hands)
    if action == "pickaxe":
        pick_e = empty(f"{name}_pick_e", (0, 0, -0.05), parent=r_hand)
        # Handle long
        cyl(f"{name}_pick_handle", r=0.04, depth=1.0, segs=10,
            loc=(0, 0, -0.50), parent=pick_e, mat_=M_PICKAXE_HANDLE)
        # Head (perpendicular)
        head_pick_e = empty(f"{name}_pick_he", (0, 0, -1.0), parent=pick_e)
        beveled_cube(f"{name}_pick_head", (0.04, 0.40, 0.08),
                     loc=(0, 0, 0), parent=head_pick_e, mat_=M_PICKAXE_HEAD)
        # Pointed tip
        smooth_cone(f"{name}_pick_tip", r1=0.04, r2=0.005, depth=0.20, segs=8,
                    loc=(0, 0.30, 0), parent=head_pick_e, mat_=M_PICKAXE_HEAD)
        # Flat end (back)
        beveled_cube(f"{name}_pick_flat", (0.10, 0.08, 0.04),
                     loc=(0, -0.20, 0), parent=head_pick_e, mat_=M_PICKAXE_HEAD)
        return {"root": base, "head_e": head_e, "r_sh": r_sh, "l_sh": l_sh,
                "helmet_lamp": beam}
    return {"root": base, "head_e": head_e, "r_sh": r_sh, "l_sh": l_sh,
            "helmet_lamp": beam}

miner_specs = [
    ("miner1", (-15, -8, 0.5), M_MINER_OVERALL, "pickaxe", math.radians(-30)),
    ("miner2", (5, -7, 0.5), M_MINER_OVERALL_RED, "pickaxe", math.radians(120)),
    ("miner3", (-8, 8, 0.5), M_MINER_OVERALL_BLUE, "pickaxe", math.radians(-90)),
    ("miner4", (12, 9, 0.5), M_MINER_OVERALL, "pickaxe", math.radians(60)),
    ("miner5", (-18, 4, 0.5), M_MINER_OVERALL_RED, "pickaxe", math.radians(40)),
]
miners = []
for spec in miner_specs:
    m = make_miner(*spec)
    miners.append(m)

# ============ TREUIL (winch) + MONTE-CHARGE (elevator) ============
treuil_e = empty("treuil", loc=(-18, 12, 0))
# 4 wood posts (frame)
for x_idx, x in enumerate((-1, 1)):
    for y_idx, y in enumerate((-1, 1)):
        cyl(f"treuil_post{x_idx}{y_idx}", r=0.10, depth=6.0, segs=10,
            loc=(x*1.5, y*1.0, 3.0), parent=treuil_e, mat_=M_WOOD_OLD)
# Top cross beams
beveled_cube("treuil_beam_x", (3.4, 0.20, 0.20), loc=(0, 0, 6.0),
             parent=treuil_e, mat_=M_WOOD_OLD)
beveled_cube("treuil_beam_y", (0.20, 2.2, 0.20), loc=(0, 0, 6.0),
             parent=treuil_e, mat_=M_WOOD_OLD)
# Pulley wheel at top (rotates)
pulley_e = empty("pulley_e", (0, 0, 5.7), parent=treuil_e)
cyl("pulley_disc", r=0.45, depth=0.10, segs=24,
    loc=(0, 0, 0), parent=pulley_e, mat_=M_CART_METAL).rotation_euler = (math.radians(90), 0, 0)
cyl("pulley_rim", r=0.50, depth=0.08, segs=24,
    loc=(0, 0, 0), parent=pulley_e, mat_=M_WOOD_OLD).rotation_euler = (math.radians(90), 0, 0)
# 6 spokes
for i in range(6):
    a = i * math.pi / 3
    beveled_cube(f"pulley_spoke{i}", (0.04, 0.04, 0.38),
                 loc=(0, 0, 0), parent=pulley_e, mat_=M_WOOD_OLD).rotation_euler = (math.radians(90), a, 0)

# Cable (hanging down from pulley to platform)
cyl("treuil_cable", r=0.02, depth=4.5, segs=8,
    loc=(0, 0, 3.35), parent=treuil_e, mat_=M_CART_METAL)

# Monte-charge platform (square wood with chains at corners)
platform_e = empty("platform_e", (0, 0, 1.1), parent=treuil_e)
beveled_cube("plat_floor", (2.0, 1.5, 0.15), bevel_offset=0.04,
             loc=(0, 0, 0), parent=platform_e, mat_=M_WOOD_OLD)
# Cargo on platform (gold sacks)
for i in range(3):
    smooth_sphere(f"sack{i}", r=0.30, loc=((i-1)*0.6, 0, 0.30),
                  parent=platform_e, mat_=M_GOLD_RICH, scale=(1, 1, 1.2))
# Side ropes (4)
for x_idx, x in enumerate((-1, 1)):
    for y_idx, y in enumerate((-1, 1)):
        cyl(f"plat_rope{x_idx}{y_idx}", r=0.015, depth=4.0, segs=6,
            loc=(x*0.9, y*0.7, 2.0), parent=treuil_e, mat_=M_PICKAXE_HANDLE)
# Crank handle (operator side)
handle_e = empty("handle_e", (1.8, 0, 4.0), parent=treuil_e)
cyl("handle_shaft", r=0.05, depth=0.30, segs=10,
    loc=(0, 0, 0), parent=handle_e, mat_=M_CART_METAL).rotation_euler = (math.radians(90), 0, 0)
beveled_cube("handle_grip", (0.04, 0.04, 0.25), loc=(0.15, 0, 0),
             parent=handle_e, mat_=M_PICKAXE_HANDLE)

# ============ CRYSTALS (signature mine treasures) ============
# 25 crystals scattered on walls and floor
crystals = []
crystal_mats = [M_CRYSTAL_BLUE, M_CRYSTAL_PURPLE, M_CRYSTAL_GREEN, M_CRYSTAL_WHITE]
for i in range(25):
    a = random.uniform(0, math.pi*2)
    rad = random.uniform(8, 13)
    cx = rad * math.cos(a)
    cy = rad * math.sin(a)
    cz = random.uniform(0.3, 5)
    cluster_e = empty(f"crystal_e{i}", (cx, cy, cz))
    cluster_e.rotation_euler = (random.uniform(-0.3, 0.3),
                                random.uniform(-0.3, 0.3),
                                random.uniform(0, math.pi*2))
    m_ = random.choice(crystal_mats)
    # 4-6 crystal shards per cluster
    num_shards = random.randint(4, 6)
    for j in range(num_shards):
        a2 = (j / num_shards) * math.pi * 2
        shard_h = random.uniform(0.3, 0.7)
        shard = smooth_cone(f"crystal{i}_{j}", r1=0.10, r2=0.02, depth=shard_h, segs=6,
                           loc=(0.10*math.cos(a2), 0.10*math.sin(a2), shard_h/2),
                           parent=cluster_e, mat_=m_)
        shard.rotation_euler = (math.radians(random.uniform(-15, 15)),
                                math.radians(random.uniform(-15, 15)), 0)
    cluster_e["_phase"] = random.uniform(0, math.pi*2)
    crystals.append(cluster_e)

# ============ 40 GOLD NUGGETS scattered on floor ============
nuggets = []
for i in range(40):
    a = random.uniform(0, math.pi*2)
    rad = random.uniform(3, 18)
    nx, ny = rad*math.cos(a), rad*math.sin(a)
    nug = smooth_sphere(f"nugget{i}", r=random.uniform(0.08, 0.18), segs=12, rings=8,
                       loc=(nx, ny, 0.18), mat_=M_GOLD_BRIGHT,
                       scale=(1, 1, 0.6))
    nug.rotation_euler = (random.uniform(-0.3, 0.3),
                          random.uniform(-0.3, 0.3),
                          random.uniform(0, math.pi*2))
    nug["_phase"] = random.uniform(0, math.pi*2)
    nuggets.append(nug)

# ============ 6 LANTERNS hanging from ceiling beams ============
lanterns = []
lantern_positions = [(-12, -8, 6), (8, -10, 6), (-5, 5, 6), (10, 8, 6),
                     (-18, 0, 6), (15, 0, 6)]
for i, (lx, ly, lz) in enumerate(lantern_positions):
    l_e = empty(f"lantern_e{i}", (lx, ly, lz))
    # Hanging chain
    cyl(f"lant_chain{i}", r=0.015, depth=1.5, segs=6,
        loc=(0, 0, 0.75), parent=l_e, mat_=M_LANTERN_FRAME)
    # Lantern frame top
    cyl(f"lant_top{i}", r=0.10, depth=0.05, segs=12,
        loc=(0, 0, 0), parent=l_e, mat_=M_LANTERN_FRAME)
    # Glass body (4 panels in box)
    beveled_cube(f"lant_body{i}", (0.18, 0.18, 0.25), bevel_offset=0.02,
                 loc=(0, 0, -0.15), parent=l_e, mat_=M_LANTERN)
    # Bottom cap
    cyl(f"lant_bot{i}", r=0.10, depth=0.05, segs=12,
        loc=(0, 0, -0.30), parent=l_e, mat_=M_LANTERN_FRAME)
    lanterns.append(l_e)

# ============ 8 BATS flying ============
bats = []
for i in range(8):
    a = (i / 8.0) * math.pi * 2 + random.uniform(-0.2, 0.2)
    rad = random.uniform(8, 13)
    bx, by = rad*math.cos(a), rad*math.sin(a)
    bz = random.uniform(4, 7)
    b_e = empty(f"bat_e{i}", (bx, by, bz))
    b_e.rotation_euler = (0, 0, a + math.pi/2)
    # Body (small)
    smooth_sphere(f"bat_body{i}", r=0.15, segs=14, rings=10, loc=(0,0,0),
                  parent=b_e, mat_=M_BAT, scale=(1, 1.5, 1))
    # Head
    smooth_sphere(f"bat_head{i}", r=0.10, loc=(0, -0.20, 0.05),
                  parent=b_e, mat_=M_BAT)
    # Eyes
    for side in (-1, 1):
        smooth_sphere(f"bat_eye{i}_{side}", r=0.025,
                      loc=(side*0.05, -0.27, 0.05), parent=b_e, mat_=M_BAT_EYE)
    # Ears (2 pointed)
    for side in (-1, 1):
        smooth_cone(f"bat_ear{i}_{side}", r1=0.04, r2=0.005, depth=0.10, segs=8,
                    loc=(side*0.07, -0.17, 0.15), parent=b_e, mat_=M_BAT)
    # Wings (2 large, articulated)
    bat_wings = []
    for side_idx, side in enumerate((-1, 1)):
        w_e = empty(f"bat_w_e{i}_{side_idx}", (0, 0, 0), parent=b_e)
        # Wing membrane (irregular shape, approximated by beveled cube)
        beveled_cube(f"bat_w{i}_{side_idx}", (0.50, 0.04, 0.40), bevel_offset=0.02,
                     loc=(side*0.40, 0, 0), parent=w_e, mat_=M_BAT)
        # Wing finger bones (3)
        for j in range(3):
            bone = beveled_cube(f"bat_bone{i}_{side_idx}_{j}", (0.42, 0.02, 0.02),
                               loc=(side*0.40, 0, -0.10 + j*0.10), parent=w_e, mat_=M_BAT)
        bat_wings.append((w_e, side))
    bats.append({"e": b_e, "wings": bat_wings, "phase": random.uniform(0, math.pi*2),
                 "orbit_rad": rad, "orbit_speed": random.uniform(0.5, 0.9),
                 "orbit_phase": a, "base_z": bz})

# ============ WOOD SCAFFOLDING (supports beams) ============
# 6 wooden support beams across the tunnel (vertical) + horizontal beam
support_beams = []
for i in range(6):
    sx = -18 + i * 7
    # Vertical post
    cyl(f"support_v{i}", r=0.20, depth=8.0, segs=12,
        loc=(sx, 0, 4.0), parent=mine_e, mat_=M_WOOD)
    # Top horizontal beam (across width)
    beveled_cube(f"support_h{i}", (0.40, 4.5, 0.30), bevel_offset=0.04,
                 loc=(sx, 0, 7.7), parent=mine_e, mat_=M_WOOD)
    # Diagonal braces
    for side in (-1, 1):
        diag = beveled_cube(f"support_d{i}_{side}", (0.20, 0.20, 2.5),
                            loc=(sx, side*1.5, 6.5), parent=mine_e, mat_=M_WOOD)
        diag.rotation_euler = (math.radians(side*-30), 0, 0)
    # Plank along top
    beveled_cube(f"support_plank{i}", (0.6, 4.5, 0.05),
                 loc=(sx, 0, 7.85), parent=mine_e, mat_=M_WOOD)
# Longitudinal beam at top connecting (1)
beveled_cube("support_long", (42, 0.30, 0.30), loc=(-1.5, 2.0, 7.7),
             parent=mine_e, mat_=M_WOOD)
beveled_cube("support_long2", (42, 0.30, 0.30), loc=(-1.5, -2.0, 7.7),
             parent=mine_e, mat_=M_WOOD)

# ============ 60 DUST + SPORES particles ============
particles = []
for i in range(60):
    px = random.uniform(-20, 20)
    py = random.uniform(-13, 13)
    pz = random.uniform(1, 7)
    m_ = M_DUST if i < 40 else M_SPORE
    p = smooth_sphere(f"part{i}", r=random.uniform(0.05, 0.10), segs=8, rings=6,
                     loc=(px, py, pz), mat_=m_)
    p["_phase"] = random.uniform(0, math.pi*2)
    p["_base_x"] = px; p["_base_y"] = py; p["_base_z"] = pz
    p["_speed"] = random.uniform(0.3, 0.8)
    particles.append(p)

# ============ ANIMATION ============
fps = 30; duration_s = 6; total_frames = fps * duration_s

# Minecart roll along rails + wheels spin
for ci, cart in enumerate(carts):
    base_x = cart["root"].location.x
    for f in range(1, total_frames + 1, 3):
        t = (f - 1) / fps
        # Forward motion (slow, ~2m/6s)
        offset = (t * 1.0) % 6.0 - 3.0
        new_x = base_x + offset * 0.3
        # Y position follows rail S-curve
        rail_t = (new_x + 20) / 40
        new_y = math.sin(rail_t * math.pi * 2 + math.pi) * 2.5
        cart["root"].location = (new_x, new_y, 0.35 + math.sin(t * 4.0) * 0.02)
        cart["root"].rotation_euler = (0, 0,
                                        # Heading
                                        math.atan2(math.cos(rail_t * math.pi * 2 + math.pi) * 2.5 * (2*math.pi/40), 1) * 0.5)
        cart["root"].keyframe_insert("location", frame=f)
        cart["root"].keyframe_insert("rotation_euler", frame=f)
        # Wheels spin
        for w in cart["wheels"]:
            w.rotation_euler = (t * 4.0, 0, 0)
            w.keyframe_insert("rotation_euler", frame=f)

# Miners swing pickaxe (alternating + Z bob)
for mi, miner in enumerate(miners):
    phase = mi * 0.6
    base_z = miner["root"].location.z
    for f in range(1, total_frames + 1, 3):
        t = (f - 1) / fps
        # Subtle Z bob
        miner["root"].location.z = base_z + math.sin(t * 3.0 + phase) * 0.03
        miner["root"].keyframe_insert("location", frame=f)
        # Right shoulder pickaxe swing
        miner["r_sh"].rotation_euler = (math.radians(-120) + math.sin(t * 3.5 + phase) * math.radians(50),
                                        0,
                                        math.radians(-15) + math.sin(t * 3.5 + phase + 0.3) * math.radians(10))
        miner["r_sh"].keyframe_insert("rotation_euler", frame=f)
        # Left shoulder follows
        miner["l_sh"].rotation_euler = (math.radians(-65) + math.sin(t * 3.5 + phase) * math.radians(20),
                                        0,
                                        math.radians(15))
        miner["l_sh"].keyframe_insert("rotation_euler", frame=f)
        # Head turn
        miner["head_e"].rotation_euler = (0, 0, math.sin(t * 1.5 + phase) * math.radians(10))
        miner["head_e"].keyframe_insert("rotation_euler", frame=f)
        # Helmet lamp tracking
        miner["helmet_lamp"].rotation_euler = (math.radians(-90) + math.sin(t * 1.0 + phase) * math.radians(5),
                                                0, 0)
        miner["helmet_lamp"].keyframe_insert("rotation_euler", frame=f)

# Treuil pulley rotates
for f in range(1, total_frames + 1, 3):
    t = (f - 1) / fps
    pulley_e.rotation_euler = (0, t * 1.0, 0)
    pulley_e.keyframe_insert("rotation_euler", frame=f)
    # Crank handle rotates
    handle_e.rotation_euler = (t * 1.0, 0, 0)
    handle_e.keyframe_insert("rotation_euler", frame=f)

# Monte-charge platform moves up/down slowly
for f in range(1, total_frames + 1, 4):
    t = (f - 1) / fps
    cycle = (t * 0.3) % 1.0
    z = 1.1 + cycle * 3.5  # 1.1 to 4.6 then loop
    platform_e.location.z = z
    platform_e.keyframe_insert("location", frame=f)

# Crystals pulse différentielles
for c in crystals:
    phase = c["_phase"]
    for f in range(1, total_frames + 1, 4):
        t = (f - 1) / fps
        s = 1 + math.sin(t * 2.0 + phase) * 0.10
        c.scale = (s, s, s)
        c.keyframe_insert("scale", frame=f)

# Bats flap + orbit
for b in bats:
    phase = b["phase"]
    rad = b["orbit_rad"]
    speed = b["orbit_speed"]
    base_phase = b["orbit_phase"]
    base_z = b["base_z"]
    for f in range(1, total_frames + 1, 3):
        t = (f - 1) / fps
        # Flap (fast)
        flap = math.sin(t * 8.0 + phase) * math.radians(40)
        for w_e, side in b["wings"]:
            w_e.rotation_euler = (side * flap, 0, 0)
            w_e.keyframe_insert("rotation_euler", frame=f)
        # Orbit (erratic)
        a = base_phase + speed * t
        x = rad * math.cos(a)
        y = rad * math.sin(a)
        z = base_z + math.sin(t * 2.5 + phase) * 1.0
        b["e"].location = (x, y, z)
        b["e"].rotation_euler = (math.sin(t * 1.5) * math.radians(10),
                                 0, a + math.pi/2)
        b["e"].keyframe_insert("location", frame=f)
        b["e"].keyframe_insert("rotation_euler", frame=f)

# Lanterns pulse + slight sway
for li, l in enumerate(lanterns):
    phase = li * 0.5
    for f in range(1, total_frames + 1, 4):
        t = (f - 1) / fps
        s = 1 + math.sin(t * 2.5 + phase) * 0.08
        l.scale = (s, s, s)
        l.rotation_euler = (math.sin(t * 1.2 + phase) * math.radians(3),
                            math.cos(t * 1.0 + phase) * math.radians(3),
                            0)
        l.keyframe_insert("scale", frame=f)
        l.keyframe_insert("rotation_euler", frame=f)

# Gold nuggets shimmer
for n in nuggets:
    if "_phase" not in n.keys():
        continue
    phase = n["_phase"]
    base_rot_z = n.rotation_euler.z
    for f in range(1, total_frames + 1, 5):
        t = (f - 1) / fps
        s = 1 + math.sin(t * 2.5 + phase) * 0.12
        n.scale = (s, s, 0.6 * s)
        n.rotation_euler = (n.rotation_euler.x, n.rotation_euler.y, base_rot_z + t * 0.3)
        n.keyframe_insert("scale", frame=f)
        n.keyframe_insert("rotation_euler", frame=f)

# Particles drift + twinkle
for p in particles:
    phase = p["_phase"]; speed = p["_speed"]
    bx, by, bz = p["_base_x"], p["_base_y"], p["_base_z"]
    for f in range(1, total_frames + 1, 5):
        t = (f - 1) / fps
        x = bx + math.sin(t * speed + phase) * 1.5
        y = by + math.cos(t * speed * 0.8 + phase) * 1.5
        z = bz + math.sin(t * speed * 0.6 + phase) * 1.0 + (t * 0.2) % 4.0
        s = 1 + math.sin(t * 3.5 + phase) * 0.4
        p.location = (x, y, z)
        p.scale = (s, s, s)
        p.keyframe_insert("location", frame=f)
        p.keyframe_insert("scale", frame=f)

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
out_glb = os.path.join(out_dir, "pbr_mine_proc.glb")

bpy.ops.object.select_all(action='SELECT')
bpy.ops.export_scene.gltf(
    filepath=out_glb, export_format='GLB',
    export_animations=True, export_apply=False, export_yup=True, use_selection=False,
)
size_mb = os.path.getsize(out_glb) / (1024 * 1024)
print(f"[proc_minecart_underground_gold_mine] DONE → {out_glb} ({size_mb:.2f} MB)")
print("[proc_minecart_underground_gold_mine] Tunnel rock + sinuous rails 30-seg + 3 minecarts loaded gold + 5 miners pickaxe swing + treuil pulley + monte-charge + 25 crystals + 40 gold nuggets + 6 lanterns + 8 bats flying + 6 wood supports + 60 dust/spores")
