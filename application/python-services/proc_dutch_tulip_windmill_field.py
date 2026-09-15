"""
proc_dutch_tulip_windmill_field.py — 233e procédural AuroraIA (97e qualité)
Dutch tulip windmill: ONE earth ground + 800 tulip rows colorful + 4 windmills rotating + farmhouse + canals + boats + 4 farmers + 6 Friesian cows + horses + storks nest + 600 tulip petals + 400 wind particles
FIXES : 1 ground + 600 tulip petals + 400 wind particles signature Netherlands
"""
import bpy, bmesh, math, random, os

random.seed(0x21077233)

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

# Dutch palette - bright sunny
M_SKY = mat("sky", (0.50, 0.72, 0.95, 1.0), 0.0, 0.7, emission=(0.45,0.68,0.92), emission_strength=2.5)
M_SUN = mat("sun", (1.0, 0.95, 0.65, 1.0), 0.0, 0.10, emission=(1.0,0.95,0.65), emission_strength=20.0)
M_CLOUD = mat("cloud", (1.0, 1.0, 0.95, 1.0), 0.0, 0.55, emission=(0.92,0.92,0.88), emission_strength=2.0, alpha=0.85)
M_CLOUD_DARK = mat("cloud_d", (0.65, 0.70, 0.78, 1.0), 0.0, 0.65, emission=(0.60,0.65,0.72), emission_strength=1.5, alpha=0.85)

# Ground
M_EARTH = mat("earth", (0.42, 0.30, 0.18, 1.0), 0.0, 0.85, emission=(0.38,0.28,0.16), emission_strength=0.4)
M_GRASS = mat("grass", (0.30, 0.62, 0.30, 1.0), 0.0, 0.75, emission=(0.28,0.58,0.28), emission_strength=0.5)
M_GRASS_BRIGHT = mat("grass_b", (0.45, 0.78, 0.35, 1.0), 0.0, 0.70, emission=(0.42,0.72,0.32), emission_strength=0.6)
M_PATH_DUTCH = mat("path", (0.65, 0.50, 0.32, 1.0), 0.0, 0.80, emission=(0.60,0.48,0.30), emission_strength=0.4)

# Canal water
M_CANAL = mat("canal", (0.32, 0.55, 0.65, 0.85), 0.4, 0.10, emission=(0.30,0.50,0.62), emission_strength=1.2, alpha=0.85)
M_CANAL_RIPPLE = mat("c_ripple", (0.65, 0.85, 0.92, 0.75), 0.0, 0.20, emission=(0.60,0.80,0.88), emission_strength=2.0, alpha=0.75)

# Tulip colors (signature multicolor)
M_TULIP_RED = mat("t_r", (0.95, 0.18, 0.20, 1.0), 0.0, 0.45, emission=(0.90,0.18,0.20), emission_strength=2.0)
M_TULIP_YELLOW = mat("t_y", (1.0, 0.92, 0.20, 1.0), 0.0, 0.40, emission=(1.0,0.92,0.20), emission_strength=2.5)
M_TULIP_PINK = mat("t_pk", (1.0, 0.55, 0.75, 1.0), 0.0, 0.45, emission=(1.0,0.55,0.75), emission_strength=2.2)
M_TULIP_PURPLE = mat("t_pu", (0.55, 0.20, 0.78, 1.0), 0.0, 0.45, emission=(0.50,0.18,0.72), emission_strength=2.0)
M_TULIP_WHITE = mat("t_w", (1.0, 0.95, 0.92, 1.0), 0.0, 0.45, emission=(1.0,0.92,0.88), emission_strength=1.8)
M_TULIP_ORANGE = mat("t_o", (1.0, 0.55, 0.10, 1.0), 0.0, 0.40, emission=(1.0,0.55,0.10), emission_strength=2.4)
M_TULIP_STEM = mat("t_s", (0.30, 0.55, 0.25, 1.0), 0.0, 0.65)
M_TULIP_LEAF = mat("t_l", (0.35, 0.60, 0.28, 1.0), 0.0, 0.65, emission=(0.32,0.55,0.25), emission_strength=0.4)

# Windmill (signature)
M_MILL_WOOD_DARK = mat("mill_d", (0.35, 0.22, 0.12, 1.0), 0.0, 0.85, emission=(0.32,0.20,0.10), emission_strength=0.3)
M_MILL_WOOD = mat("mill_w", (0.55, 0.35, 0.20, 1.0), 0.0, 0.75, emission=(0.50,0.32,0.18), emission_strength=0.4)
M_MILL_WHITE = mat("mill_white", (0.92, 0.88, 0.82, 1.0), 0.0, 0.70, emission=(0.85,0.82,0.78), emission_strength=0.6)
M_MILL_CAP = mat("mill_cap", (0.30, 0.45, 0.28, 1.0), 0.0, 0.65, emission=(0.28,0.42,0.25), emission_strength=0.5)
M_SAIL_CANVAS = mat("sail_c", (0.92, 0.88, 0.80, 1.0), 0.0, 0.60, emission=(0.85,0.82,0.75), emission_strength=0.7)

# Farmhouse
M_BRICK_RED = mat("brick", (0.65, 0.30, 0.20, 1.0), 0.0, 0.80, emission=(0.60,0.28,0.18), emission_strength=0.4)
M_BRICK_DARK = mat("brick_d", (0.45, 0.22, 0.15, 1.0), 0.0, 0.85)
M_ROOF_DUTCH = mat("roof_d", (0.35, 0.22, 0.15, 1.0), 0.0, 0.75, emission=(0.32,0.20,0.13), emission_strength=0.3)
M_TILE_ROOF = mat("tile_r", (0.55, 0.25, 0.15, 1.0), 0.0, 0.55, emission=(0.50,0.22,0.13), emission_strength=0.4)
M_WINDOW_DUTCH = mat("win_d", (0.85, 0.92, 0.95, 1.0), 0.0, 0.10, emission=(0.78,0.85,0.92), emission_strength=1.5, alpha=0.85)
M_WINDOW_GLOW_D = mat("win_gd", (1.0, 0.82, 0.45, 1.0), 0.0, 0.10, emission=(1.0,0.82,0.45), emission_strength=5.0)
M_SHUTTER_GREEN = mat("shutter_g", (0.20, 0.45, 0.30, 1.0), 0.0, 0.65, emission=(0.18,0.42,0.28), emission_strength=0.5)
M_DOOR_DUTCH = mat("door_d", (0.35, 0.20, 0.10, 1.0), 0.0, 0.80)

# Boats
M_BOAT_HULL = mat("boat_h", (0.45, 0.28, 0.15, 1.0), 0.0, 0.75)
M_BOAT_INSIDE = mat("boat_i", (0.65, 0.50, 0.32, 1.0), 0.0, 0.70)

# Farmer clothing
M_SKIN_DUTCH = mat("skin", (0.95, 0.78, 0.65, 1.0), 0.0, 0.55, emission=(0.88,0.72,0.62), emission_strength=0.4)
M_HAIR_BLOND_D = mat("hair_d", (0.85, 0.65, 0.30, 1.0), 0.0, 0.65)
M_HAIR_BROWN_D = mat("hair_br", (0.42, 0.25, 0.12, 1.0), 0.0, 0.85)
M_SHIRT_WHITE_D = mat("shirt", (0.92, 0.88, 0.82, 1.0), 0.0, 0.70, emission=(0.85,0.82,0.78), emission_strength=0.5)
M_OVERALLS = mat("overalls", (0.20, 0.40, 0.65, 1.0), 0.0, 0.75, emission=(0.18,0.38,0.60), emission_strength=0.4)
M_SKIRT_DRESS = mat("skirt_d", (0.78, 0.18, 0.18, 1.0), 0.0, 0.65, emission=(0.72,0.18,0.18), emission_strength=0.6)
M_APRON_D = mat("apron_d", (0.92, 0.88, 0.82, 1.0), 0.0, 0.70, emission=(0.85,0.82,0.78), emission_strength=0.5)
M_HAT_STRAW = mat("hat_st", (0.92, 0.78, 0.42, 1.0), 0.0, 0.75, emission=(0.85,0.72,0.40), emission_strength=0.5)
M_BONNET_LACE = mat("bonnet", (0.95, 0.92, 0.85, 1.0), 0.0, 0.65, emission=(0.88,0.85,0.78), emission_strength=0.5)
# CLOGS signature wooden shoes
M_CLOG = mat("clog", (0.92, 0.78, 0.42, 1.0), 0.0, 0.75, emission=(0.85,0.72,0.40), emission_strength=0.6)

# Friesian cows (black and white)
M_COW_BLACK = mat("cow_b", (0.10, 0.08, 0.08, 1.0), 0.0, 0.80)
M_COW_WHITE = mat("cow_w", (0.95, 0.92, 0.88, 1.0), 0.0, 0.65, emission=(0.88,0.85,0.82), emission_strength=0.4)
M_COW_PINK_D = mat("cow_pk", (0.95, 0.62, 0.62, 1.0), 0.0, 0.50, emission=(0.88,0.58,0.58), emission_strength=0.4)
M_HORN_D = mat("horn_d", (0.55, 0.45, 0.30, 1.0), 0.2, 0.55)

# Horses (draft)
M_HORSE_CHESTNUT = mat("horse_c", (0.45, 0.25, 0.12, 1.0), 0.0, 0.75, emission=(0.42,0.22,0.10), emission_strength=0.3)
M_HORSE_WHITE_D = mat("horse_wd", (0.92, 0.88, 0.82, 1.0), 0.0, 0.65)
M_HORSE_MANE = mat("horse_m", (0.30, 0.18, 0.10, 1.0), 0.0, 0.85)

# Stork
M_STORK_WHITE = mat("stork", (0.98, 0.95, 0.92, 1.0), 0.0, 0.55, emission=(0.92,0.90,0.88), emission_strength=0.6)
M_STORK_BLACK = mat("stork_bk", (0.08, 0.06, 0.06, 1.0), 0.0, 0.70)
M_STORK_BEAK = mat("stork_b", (0.95, 0.18, 0.20, 1.0), 0.0, 0.45, emission=(0.90,0.18,0.20), emission_strength=0.8)
M_STORK_LEG = mat("stork_l", (0.95, 0.18, 0.20, 1.0), 0.0, 0.55)

# Nest
M_NEST = mat("nest", (0.45, 0.32, 0.20, 1.0), 0.0, 0.85)

# Wind particle
M_WIND = mat("wind", (0.85, 0.92, 0.95, 0.55), 0.0, 0.30, emission=(0.78,0.85,0.92), emission_strength=2.0, alpha=0.55)

# ============ SKY + SUN + CLOUDS (signature dutch sky big clouds) ============
sky = smooth_sphere("sky", r=140, segs=32, rings=20, loc=(0,0,0), mat_=M_SKY)
sky.scale = (1,1,0.55)
sun_e = empty("sun_e", (20, 50, 30))
smooth_sphere("sun", r=5.5, loc=(0, 0, 0), parent=sun_e, mat_=M_SUN)
for i in range(3):
    smooth_sphere(f"sun_halo{i}", r=5.5 + (i+1)*1.8, loc=(0, 0, 0), parent=sun_e, mat_=M_SUN)

# Massive cumulus clouds (signature Dutch sky)
clouds = []
for i in range(12):
    a = (i / 12.0) * math.pi * 2
    rad = random.uniform(30, 45)
    cx, cy = rad*math.cos(a), rad*math.sin(a)
    cz = random.uniform(22, 32)
    c_e = empty(f"cloud_e{i}", (cx, cy, cz))
    col = M_CLOUD if i % 3 != 0 else M_CLOUD_DARK
    for j in range(7):
        smooth_sphere(f"cloud{i}_{j}", r=random.uniform(3.0, 4.5),
                      loc=(random.uniform(-3,3), random.uniform(-2,2), random.uniform(-0.5,0.5)),
                      parent=c_e, mat_=col)
    c_e["_phase"] = random.uniform(0, math.pi*2)
    clouds.append(c_e)

# ============ ONE clean earth ground ============
ground = beveled_cube("ground", (100, 100, 0.5), bevel_offset=0.08, loc=(0, 0, -0.25), mat_=M_EARTH)
# Grass patches (organic 3D)
for i in range(60):
    a = random.uniform(0, math.pi*2)
    rad = random.uniform(10, 42)
    smooth_sphere(f"grass{i}", r=random.uniform(0.30, 0.55),
                  loc=(rad*math.cos(a), rad*math.sin(a), 0.15),
                  mat_=M_GRASS if i % 2 == 0 else M_GRASS_BRIGHT,
                  scale=(1.4, 1.3, 0.18))
# Stone path
for i in range(30):
    px = (i - 15) * 1.4
    py = math.sin(i * 0.3) * 1.5 - 6
    smooth_sphere(f"path{i}", r=random.uniform(0.30, 0.50), segs=14, rings=10,
                  loc=(px, py, 0.08), mat_=M_PATH_DUTCH,
                  scale=(1.4, 1.0, 0.20))

# ============ CANAL (signature Dutch waterway) ============
canal_e = empty("canal", loc=(0, -15, 0))
beveled_cube("canal_main", (50, 5, 0.20), bevel_offset=0.05, loc=(0, 0, -0.05),
             parent=canal_e, mat_=M_CANAL)
# Canal embankments (stone)
for side in (-1, 1):
    beveled_cube(f"canal_emb_{side}", (50, 0.5, 0.40), bevel_offset=0.04,
                 loc=(0, side*2.7, 0.10), parent=canal_e, mat_=M_BRICK_DARK)
# Ripples
for i in range(20):
    rx_r = random.uniform(-22, 22)
    ry_r = random.uniform(-2, 2)
    smooth_sphere(f"canal_ripple{i}", r=random.uniform(0.25, 0.50), segs=14, rings=10,
                  loc=(rx_r, ry_r, 0.05), parent=canal_e, mat_=M_CANAL_RIPPLE,
                  scale=(1.5, 1.3, 0.10))

# ============ 4 WINDMILLS (signature Dutch) ============
def make_windmill(name, loc, scale=1.0):
    base = empty(name, loc)
    # Round base (signature wide bottom tapered)
    for tier in range(5):
        t_r = (3.0 - tier * 0.35) * scale
        t_h = 1.4 * scale
        t_z = tier * t_h + t_h / 2
        cyl(f"{name}_tier{tier}", r=t_r, depth=t_h, segs=24,
            loc=(0, 0, t_z), parent=base, mat_=M_MILL_WHITE if tier % 2 == 0 else M_MILL_WOOD)
    # Top brick band
    cyl(f"{name}_top_band", r=1.5*scale, depth=0.30*scale, segs=24,
        loc=(0, 0, 7.0*scale), parent=base, mat_=M_BRICK_RED)
    # CAP (signature green rotating top)
    cap_e = empty(f"{name}_cap_e", (0, 0, 7.5*scale), parent=base)
    smooth_sphere(f"{name}_cap", r=1.6*scale, segs=22, rings=14,
                  loc=(0, 0, 0.3*scale), parent=cap_e, mat_=M_MILL_CAP,
                  scale=(1, 1.4, 0.8))
    # Cap front (signature pointed)
    smooth_cone(f"{name}_cap_pt", r1=0.5*scale, r2=0.1*scale, depth=1.0*scale, segs=14,
                loc=(0, -1.8*scale, 0.5*scale), parent=cap_e, mat_=M_MILL_CAP).rotation_euler = (math.radians(90), 0, 0)
    # Windows on body (signature)
    for wi in range(4):
        wa = (wi / 4.0) * math.pi * 2
        wx = 1.55*scale*math.cos(wa)
        wy = 1.55*scale*math.sin(wa)
        wz = 4*scale + (wi*0.5)*scale
        beveled_cube(f"{name}_win{wi}", (0.4*scale, 0.10*scale, 0.6*scale), bevel_offset=0.03,
                     loc=(wx, wy, wz), parent=base, mat_=M_WINDOW_GLOW_D)
    # Door
    beveled_cube(f"{name}_door", (0.6*scale, 0.15*scale, 1.5*scale), bevel_offset=0.04,
                 loc=(0, -2.4*scale, 0.75*scale), parent=base, mat_=M_DOOR_DUTCH)
    # SAILS (4 blades cross signature)
    sails_e = empty(f"{name}_sails_e", (0, -1.8*scale, 7.8*scale), parent=base)
    sails_e.rotation_euler = (math.radians(90), 0, 0)
    # 4 cross beam blades
    for blade in range(4):
        ba = (blade / 4.0) * math.pi * 2
        b_e = empty(f"{name}_b_e{blade}", (0, 0, 0), parent=sails_e)
        b_e.rotation_euler = (0, 0, ba)
        # Main beam (signature)
        beveled_cube(f"{name}_beam{blade}", (0.15*scale, 0.20*scale, 4.5*scale), bevel_offset=0.02,
                     loc=(0, 0, 2.25*scale), parent=b_e, mat_=M_MILL_WOOD_DARK)
        # 4 lattice cross supports (signature wooden lattice)
        for lat in range(5):
            lat_z = (lat + 1) * 0.85*scale
            beveled_cube(f"{name}_lat{blade}_{lat}", (1.0*scale, 0.05*scale, 0.06*scale), bevel_offset=0.01,
                         loc=(0, 0, lat_z), parent=b_e, mat_=M_MILL_WOOD_DARK)
        # CANVAS SAIL (signature white fabric one side)
        beveled_cube(f"{name}_canvas{blade}", (0.40*scale, 0.05*scale, 4.0*scale), bevel_offset=0.01,
                     loc=(0.30*scale, 0, 2.0*scale), parent=b_e, mat_=M_SAIL_CANVAS)
    # Front platform
    beveled_cube(f"{name}_platform", (3.5*scale, 1.5*scale, 0.20*scale), bevel_offset=0.04,
                 loc=(0, -3.0*scale, 0.20*scale), parent=base, mat_=M_MILL_WOOD)
    # Stairs to platform
    for st in range(3):
        beveled_cube(f"{name}_stair{st}", (1.5*scale, 0.30*scale, 0.20*scale), bevel_offset=0.02,
                     loc=(0, -3.8*scale - st*0.4*scale, 0.05*scale + st*0.07*scale), parent=base, mat_=M_MILL_WOOD)
    return {"root": base, "sails": sails_e}

windmills = []
mill_pos = [(-22, 8, 0, 1.0), (22, 8, 0, 1.05), (-22, -25, 0, 0.95), (22, -25, 0, 1.0)]
for i, (mx, my, mz, sc) in enumerate(mill_pos):
    m = make_windmill(f"mill{i}", (mx, my, mz), scale=sc)
    windmills.append(m)

# ============ FARMHOUSE (signature Dutch brick) ============
farm_e = empty("farm", loc=(0, 10, 0))
# Brick walls
beveled_cube("f_walls", (8, 5, 4), bevel_offset=0.06, loc=(0, 0, 2.0),
             parent=farm_e, mat_=M_BRICK_RED)
# Brick detail (organic 3D)
for bi in range(30):
    bx_b = random.uniform(-3.8, 3.8)
    by_b = -2.55
    bz_b = random.uniform(0.1, 3.8)
    smooth_sphere(f"f_brick{bi}", r=0.10, loc=(bx_b, by_b, bz_b),
                  parent=farm_e, mat_=M_BRICK_DARK, scale=(1.5, 0.5, 0.6))
# Stepped gable (signature Dutch architecture)
for step in range(4):
    s_w = 7 - step * 0.8
    beveled_cube(f"f_gable_{step}", (s_w, 0.3, 0.40), bevel_offset=0.03,
                 loc=(0, -2.55, 4.0 + step*0.40), parent=farm_e, mat_=M_BRICK_RED)
    beveled_cube(f"f_gable_b_{step}", (s_w, 0.3, 0.40), bevel_offset=0.03,
                 loc=(0, 2.55, 4.0 + step*0.40), parent=farm_e, mat_=M_BRICK_RED)
# Cap top
beveled_cube("f_gable_top", (1.5, 0.3, 0.40), bevel_offset=0.03,
             loc=(0, -2.55, 5.6), parent=farm_e, mat_=M_BRICK_RED)
beveled_cube("f_gable_top_b", (1.5, 0.3, 0.40), bevel_offset=0.03,
             loc=(0, 2.55, 5.6), parent=farm_e, mat_=M_BRICK_RED)
# Tile roof
for side, side_mul in zip(("L", "R"), (-1, 1)):
    roof = beveled_cube(f"f_roof_{side}", (8.5, 3.0, 0.25), bevel_offset=0.04,
                       loc=(0, side_mul*1.2, 5.0), parent=farm_e, mat_=M_TILE_ROOF)
    roof.rotation_euler = (math.radians(side_mul*-30), 0, 0)
# Roof ridge
beveled_cube("f_ridge", (8.5, 0.3, 0.25), bevel_offset=0.03, loc=(0, 0, 6.3),
             parent=farm_e, mat_=M_ROOF_DUTCH)
# Chimney
beveled_cube("f_chimney", (0.45, 0.45, 1.8), bevel_offset=0.04,
             loc=(-2.5, 0, 7.0), parent=farm_e, mat_=M_BRICK_RED)
# Smoke
for si in range(3):
    smooth_sphere(f"f_smoke{si}", r=0.30 + si*0.08,
                  loc=(-2.5, 0, 8.0 + si*0.6),
                  parent=farm_e, mat_=mat(f"smoke_m{si}", (0.85, 0.85, 0.82, 1.0), 0, 0.65,
                                            emission=(0.80,0.80,0.78), emission_strength=0.7, alpha=0.65))
# Door (Dutch door signature split)
beveled_cube("f_door", (1.0, 0.20, 2.2), bevel_offset=0.04,
             loc=(0, -2.65, 1.1), parent=farm_e, mat_=M_DOOR_DUTCH)
# Door split line (signature Dutch door)
beveled_cube("f_door_split", (1.0, 0.04, 0.05), bevel_offset=0.01,
             loc=(0, -2.70, 1.5), parent=farm_e, mat_=M_BRICK_DARK)
# Door handle
smooth_sphere("f_door_h", r=0.06, loc=(0.30, -2.78, 1.1),
              parent=farm_e, mat_=M_TILE_ROOF)
# 4 windows with green shutters (signature)
for wi in range(4):
    wx = (wi % 2 * 2 - 1) * 2.5
    wy_idx = wi // 2
    wy = -2.55 if wy_idx == 0 else 2.55
    wz = 2.5
    # Window glass
    beveled_cube(f"f_win{wi}", (1.0, 0.10, 1.0), bevel_offset=0.03,
                 loc=(wx, wy, wz), parent=farm_e, mat_=M_WINDOW_DUTCH)
    # Glow
    beveled_cube(f"f_win_glow{wi}", (0.85, 0.05, 0.85), bevel_offset=0.02,
                 loc=(wx, wy + (-0.04 if wy_idx == 0 else 0.04), wz),
                 parent=farm_e, mat_=M_WINDOW_GLOW_D)
    # Cross frame
    beveled_cube(f"f_win_v{wi}", (0.05, 0.05, 1.0), loc=(wx, wy, wz),
                 parent=farm_e, mat_=M_DOOR_DUTCH)
    beveled_cube(f"f_win_h{wi}", (1.0, 0.05, 0.05), loc=(wx, wy, wz),
                 parent=farm_e, mat_=M_DOOR_DUTCH)
    # Green shutters (signature)
    for side in (-1, 1):
        beveled_cube(f"f_shut{wi}_{side}", (0.5, 0.04, 1.0), bevel_offset=0.02,
                     loc=(wx + side*0.7, wy - 0.05 * (1 if wy_idx == 0 else -1), wz),
                     parent=farm_e, mat_=M_SHUTTER_GREEN)
# STORK NEST on chimney top (signature Dutch)
nest_e = empty("nest", (-2.5, 0, 8.0), parent=farm_e)
for nsi in range(8):
    nsa = (nsi / 8.0) * math.pi * 2
    cyl(f"nest_s{nsi}", r=0.04, depth=0.40, segs=6,
        loc=(0.20*math.cos(nsa), 0.20*math.sin(nsa), 0.05), parent=nest_e,
        mat_=M_NEST).rotation_euler = (math.radians(80), 0, nsa)
# Nest disc
cyl("nest_d", r=0.30, depth=0.10, segs=14, loc=(0, 0, 0),
    parent=nest_e, mat_=M_NEST)

# ============ STORKS in nest (signature) ============
def make_stork(name, loc, parent_obj=None):
    base = empty(name, loc, parent=parent_obj)
    # Body white
    smooth_sphere(f"{name}_body", r=0.25, segs=18, rings=12, loc=(0, 0, 0.15),
                  parent=base, mat_=M_STORK_WHITE, scale=(1.6, 1, 1))
    # Wing black tips
    for side in (-1, 1):
        beveled_cube(f"{name}_wing{side}", (0.20, 0.12, 0.30), bevel_offset=0.03,
                     loc=(0, side*0.20, 0.20), parent=base, mat_=M_STORK_BLACK)
    # Long neck
    neck_e = empty(f"{name}_neck_e", (0.35, 0, 0.40), parent=base)
    for ni in range(5):
        cyl(f"{name}_neck{ni}", r=0.05, depth=0.18, segs=10,
            loc=(0, 0, ni*0.16), parent=neck_e, mat_=M_STORK_WHITE)
    # Head
    head_e = empty(f"{name}_he", (0, 0, 0.80), parent=neck_e)
    smooth_sphere(f"{name}_head", r=0.12, loc=(0, 0, 0),
                  parent=head_e, mat_=M_STORK_WHITE)
    # Long red beak (signature)
    smooth_cone(f"{name}_beak", r1=0.04, r2=0.01, depth=0.35, segs=10,
                loc=(0.20, 0, -0.02), parent=head_e,
                mat_=M_STORK_BEAK).rotation_euler = (0, math.radians(90), 0)
    # Eyes
    smooth_sphere(f"{name}_eye", r=0.025, loc=(0.06, 0.08, 0.04),
                  parent=head_e, mat_=M_STORK_BLACK)
    # Long red legs (signature stork)
    for side in (-1, 1):
        cyl(f"{name}_leg{side}", r=0.025, depth=0.50, segs=10,
            loc=(0, side*0.08, -0.10), parent=base, mat_=M_STORK_LEG)
    base["_phase"] = random.uniform(0, math.pi*2)
    return {"root": base, "he": head_e}

storks = [
    make_stork("stork1", (0.1, 0, 0.20), parent_obj=nest_e),
    make_stork("stork2", (-0.1, 0.1, 0.18), parent_obj=nest_e),
]

# ============ BOATS in canal (2 wooden) ============
def make_boat(name, loc, facing=0):
    base = empty(name, loc)
    base.rotation_euler = (0, 0, facing)
    # Long hull
    beveled_cube(f"{name}_hull", (3.5, 1.0, 0.40), bevel_offset=0.08,
                 loc=(0, 0, 0.10), parent=base, mat_=M_BOAT_HULL)
    # Inside
    beveled_cube(f"{name}_inside", (3.2, 0.85, 0.25), bevel_offset=0.05,
                 loc=(0, 0, 0.25), parent=base, mat_=M_BOAT_INSIDE)
    # Bow
    smooth_cone(f"{name}_bow", r1=0.30, r2=0.10, depth=0.50, segs=10,
                loc=(1.85, 0, 0.20), parent=base, mat_=M_BOAT_HULL).rotation_euler = (0, math.radians(90), 0)
    # Stern
    smooth_cone(f"{name}_stern", r1=0.30, r2=0.10, depth=0.30, segs=10,
                loc=(-1.75, 0, 0.20), parent=base, mat_=M_BOAT_HULL).rotation_euler = (0, math.radians(-90), 0)
    # 2 benches
    for bi in range(2):
        beveled_cube(f"{name}_bench{bi}", (0.5, 0.85, 0.10),
                     loc=((bi*2-1)*0.6, 0, 0.40), parent=base, mat_=M_MILL_WOOD)
    return base

boats = []
boat_pos = [(-10, -15, 0, math.radians(15)),
            (8, -14, 0, math.radians(-15))]
for i, (bx, by, bz, fac) in enumerate(boat_pos):
    b = make_boat(f"boat{i}", (bx, by, bz), facing=fac)
    boats.append(b)

# ============ 800 TULIPS in rows (signature multicolor field) ============
tulip_colors = [M_TULIP_RED, M_TULIP_YELLOW, M_TULIP_PINK, M_TULIP_PURPLE, M_TULIP_WHITE, M_TULIP_ORANGE]
tulips = []
# 20 rows x 40 plants each
for row in range(20):
    row_y = -10 + row * 0.7
    # Each row is 1 color (signature - blocks)
    row_col = tulip_colors[row % 6]
    for col in range(40):
        col_x = (col - 19.5) * 0.6
        # Skip areas where structures/canals are
        if abs(col_x) < 4 and abs(row_y - 10) < 5:  # farmhouse area
            continue
        if abs(row_y + 15) < 3:  # canal area
            continue
        if (col_x - (-22))**2 + (row_y - 8)**2 < 25:  # windmill 1
            continue
        if (col_x - 22)**2 + (row_y - 8)**2 < 25:  # windmill 2
            continue
        tx_t = col_x + random.uniform(-0.05, 0.05)
        ty_t = row_y + random.uniform(-0.05, 0.05)
        t_e = empty(f"tul_{row}_{col}", (tx_t, ty_t, 0))
        # Stem
        cyl(f"tul_st_{row}_{col}", r=0.02, depth=0.40, segs=6,
            loc=(0, 0, 0.20), parent=t_e, mat_=M_TULIP_STEM)
        # 2 leaves
        for li in range(2):
            beveled_cube(f"tul_l_{row}_{col}_{li}", (0.04, 0.20, 0.015), bevel_offset=0.005,
                         loc=((li*2-1)*0.03, 0, 0.15), parent=t_e, mat_=M_TULIP_LEAF)
        # FLOWER HEAD (signature cup shape 6 petals)
        for pi in range(6):
            pa = (pi / 6.0) * math.pi * 2
            petal = beveled_cube(f"tul_p_{row}_{col}_{pi}", (0.05, 0.07, 0.10), bevel_offset=0.01,
                                 loc=(0.04*math.cos(pa), 0.04*math.sin(pa), 0.45),
                                 parent=t_e, mat_=row_col)
            petal.rotation_euler = (math.radians(10), 0, pa)
        # Inner base
        cyl(f"tul_b_{row}_{col}", r=0.04, depth=0.05, segs=10,
            loc=(0, 0, 0.42), parent=t_e, mat_=row_col)
        t_e["_phase"] = random.uniform(0, math.pi*2)
        tulips.append(t_e)

# ============ 4 FARMERS + 1 WOMAN ============
def make_farmer(name, loc, is_woman=False, facing=0, scale=1.0):
    base = empty(name, loc)
    base.rotation_euler = (0, 0, facing)
    # Legs
    for side_idx, side in enumerate((-1, 1)):
        hip = empty(f"{name}_hip{side_idx}", (side*0.13*scale, 0, 0.85*scale), parent=base)
        if is_woman:
            # Hidden under long skirt
            cyl(f"{name}_legs", r=0.30*scale, depth=0.90*scale, segs=14,
                loc=(0, 0, 0.45*scale), parent=base, mat_=M_SKIRT_DRESS)
            break  # Single leg cone for woman
        else:
            cyl(f"{name}_thigh{side_idx}", r=0.10*scale, depth=0.45*scale, segs=12,
                loc=(0, 0, -0.22*scale), parent=hip, mat_=M_OVERALLS)
            cyl(f"{name}_calf{side_idx}", r=0.085*scale, depth=0.40*scale, segs=12,
                loc=(0, 0, -0.65*scale), parent=hip, mat_=M_OVERALLS)
            # CLOGS signature wooden shoes
            beveled_cube(f"{name}_clog{side_idx}", (0.16*scale, 0.32*scale, 0.12*scale), bevel_offset=0.03,
                         loc=(0, 0.04*scale, -0.85*scale), parent=hip, mat_=M_CLOG)
            # Curl up clog tip (signature)
            smooth_sphere(f"{name}_clog_tip{side_idx}", r=0.06*scale,
                          loc=(0, 0.18*scale, -0.78*scale), parent=hip, mat_=M_CLOG)
    # Apron / overalls
    if is_woman:
        beveled_cube(f"{name}_apron", (0.40*scale, 0.10*scale, 1.2*scale), bevel_offset=0.04,
                     loc=(0, -0.18*scale, 1.05*scale), parent=base, mat_=M_APRON_D)
    else:
        # Suspender straps
        for side in (-1, 1):
            beveled_cube(f"{name}_susp{side}", (0.05*scale, 0.05*scale, 0.80*scale), bevel_offset=0.01,
                         loc=(side*0.10*scale, -0.13*scale, 1.45*scale), parent=base, mat_=M_OVERALLS)
    # Shirt
    beveled_cube(f"{name}_shirt", (0.42*scale, 0.24*scale, 0.55*scale), bevel_offset=0.05,
                 loc=(0, 0, 1.55*scale), parent=base, mat_=M_SHIRT_WHITE_D)
    # Neck
    cyl(f"{name}_neck", r=0.09*scale, depth=0.16*scale, segs=10,
        loc=(0, 0, 1.92*scale), parent=base, mat_=M_SKIN_DUTCH)
    # Head
    head_e = empty(f"{name}_he", (0, 0, 2.10*scale), parent=base)
    smooth_sphere(f"{name}_head", r=0.18*scale, segs=20, rings=14, loc=(0, 0, 0),
                  parent=head_e, mat_=M_SKIN_DUTCH)
    # Hair (blond signature)
    smooth_sphere(f"{name}_hair", r=0.20*scale, loc=(0, 0.04*scale, 0.05*scale),
                  parent=head_e, mat_=M_HAIR_BLOND_D, scale=(1, 1, 0.85))
    # Hat
    if is_woman:
        # LACE BONNET (signature Dutch)
        cyl(f"{name}_bonnet_b", r=0.22*scale, depth=0.05*scale, segs=18,
            loc=(0, 0, 0.18*scale), parent=head_e, mat_=M_BONNET_LACE)
        # Bonnet crown
        smooth_sphere(f"{name}_bonnet_c", r=0.20*scale, loc=(0, 0.03*scale, 0.18*scale),
                      parent=head_e, mat_=M_BONNET_LACE, scale=(1.1, 1.0, 0.5))
        # Side flaps (signature)
        for side in (-1, 1):
            flap = beveled_cube(f"{name}_flap{side}", (0.04*scale, 0.12*scale, 0.25*scale), bevel_offset=0.01,
                               loc=(side*0.22*scale, -0.05*scale, 0.08*scale),
                               parent=head_e, mat_=M_BONNET_LACE)
            flap.rotation_euler = (0, 0, math.radians(side*-25))
    else:
        # Straw hat
        cyl(f"{name}_hat_brim", r=0.32*scale, depth=0.04*scale, segs=18,
            loc=(0, 0, 0.20*scale), parent=head_e, mat_=M_HAT_STRAW)
        cyl(f"{name}_hat_crown", r=0.18*scale, depth=0.18*scale, segs=16,
            loc=(0, 0, 0.32*scale), parent=head_e, mat_=M_HAT_STRAW)
    # Eyes
    for side in (-1, 1):
        smooth_sphere(f"{name}_eye{side}", r=0.022*scale,
                      loc=(side*0.06*scale, -0.14*scale, 0.02*scale), parent=head_e,
                      mat_=mat(f"{name}_ew{side}", (0.18, 0.45, 0.65, 1), 0, 0.4,
                                emission=(0.18,0.42,0.62), emission_strength=0.4))
    # Arms
    arms_e = []
    for side_idx, side in enumerate((-1, 1)):
        sh = empty(f"{name}_sh{side_idx}", (side*0.30*scale, 0, 1.85*scale), parent=base)
        sh.rotation_euler = (math.radians(-30), 0, math.radians(side*-15))
        cyl(f"{name}_uarm{side_idx}", r=0.08*scale, depth=0.32*scale, segs=12,
            loc=(0, 0, -0.16*scale), parent=sh, mat_=M_SHIRT_WHITE_D)
        cyl(f"{name}_fa{side_idx}", r=0.07*scale, depth=0.30*scale, segs=10,
            loc=(0, 0, -0.45*scale), parent=sh, mat_=M_SKIN_DUTCH)
        smooth_sphere(f"{name}_hand{side_idx}", r=0.08*scale, loc=(0, 0, -0.62*scale),
                      parent=sh, mat_=M_SKIN_DUTCH)
        arms_e.append(sh)
    base["_phase"] = random.uniform(0, math.pi*2)
    return {"root": base, "he": head_e, "arms": arms_e}

farmers = []
farmer_specs = [
    ("f1", (-10, 5, 0), False, math.radians(45)),
    ("f2", (10, 5, 0), False, math.radians(-45)),
    ("f3", (-7, -3, 0), False, math.radians(90)),
    ("f4", (7, -3, 0), False, math.radians(-90)),
]
for spec in farmer_specs:
    name, loc, is_w, fac = spec
    f = make_farmer(name, loc, is_woman=is_w, facing=fac)
    farmers.append(f)
# Woman
woman_d = make_farmer("woman", (0, 6, 0), is_woman=True, facing=math.radians(180))
farmers.append(woman_d)

# ============ 6 FRIESIAN COWS (signature black & white) ============
def make_friesian_cow(name, loc, facing=0):
    base = empty(name, loc)
    base.rotation_euler = (0, 0, facing)
    # Body (mostly white)
    smooth_sphere(f"{name}_body", r=0.55, segs=20, rings=14, loc=(0, 0, 1.05),
                  parent=base, mat_=M_COW_WHITE, scale=(1.7, 1, 1))
    # Black patches (signature Friesian)
    for sp in range(5):
        smooth_sphere(f"{name}_spot{sp}", r=0.22,
                      loc=(random.uniform(-0.7, 0.7), random.uniform(-0.5, 0.5),
                           1.05 + random.uniform(-0.2, 0.4)),
                      parent=base, mat_=M_COW_BLACK,
                      scale=(1.3, 1, 0.4))
    # Belly
    smooth_sphere(f"{name}_belly", r=0.45, loc=(0, 0, 0.90),
                  parent=base, mat_=M_COW_WHITE, scale=(1.5, 0.95, 0.6))
    # Neck
    neck = beveled_cube(f"{name}_neck", (0.35, 0.30, 0.50), bevel_offset=0.05,
                       loc=(0.80, 0, 1.20), parent=base, mat_=M_COW_WHITE)
    neck.rotation_euler = (0, math.radians(-15), 0)
    # Head
    head_e = empty(f"{name}_he", (1.20, 0, 1.40), parent=base)
    beveled_cube(f"{name}_head", (0.45, 0.25, 0.30), bevel_offset=0.05,
                 loc=(0, 0, 0), parent=head_e, mat_=M_COW_WHITE)
    # Black markings on face
    beveled_cube(f"{name}_face_mark", (0.20, 0.05, 0.30), loc=(0, -0.12, 0),
                 parent=head_e, mat_=M_COW_BLACK)
    # Muzzle (pink signature)
    smooth_sphere(f"{name}_muzzle", r=0.13,
                  loc=(0.22, 0, -0.05), parent=head_e, mat_=M_COW_PINK_D,
                  scale=(1, 0.9, 0.8))
    # Eyes
    for side in (-1, 1):
        smooth_sphere(f"{name}_eye{side}", r=0.04,
                      loc=(0.06, side*0.12, 0.08), parent=head_e, mat_=M_COW_BLACK)
    # Horns (small)
    for side in (-1, 1):
        horn = smooth_cone(f"{name}_horn{side}", r1=0.04, r2=0.01, depth=0.18, segs=10,
                           loc=(-0.10, side*0.13, 0.20), parent=head_e, mat_=M_HORN_D)
        horn.rotation_euler = (math.radians(-30), 0, math.radians(side*30))
    # Ears
    for side in (-1, 1):
        ear = beveled_cube(f"{name}_ear{side}", (0.06, 0.16, 0.04),
                          loc=(-0.05, side*0.22, 0.18), parent=head_e, mat_=M_COW_WHITE)
        ear.rotation_euler = (0, 0, math.radians(side*40))
    # 4 legs
    for x_idx, x in enumerate((0.50, -0.50)):
        for y_idx, y in enumerate((-0.35, 0.35)):
            cyl(f"{name}_leg{x_idx}{y_idx}", r=0.10, depth=0.80, segs=10,
                loc=(x, y, 0.40), parent=base, mat_=M_COW_WHITE)
            cyl(f"{name}_hoof{x_idx}{y_idx}", r=0.11, depth=0.10, segs=10,
                loc=(x, y, 0.05), parent=base, mat_=M_COW_BLACK)
    # Udder pink
    smooth_sphere(f"{name}_udder", r=0.18, loc=(-0.40, 0, 0.70),
                  parent=base, mat_=M_COW_PINK_D, scale=(1, 0.9, 0.8))
    # Tail
    cyl(f"{name}_tail", r=0.04, depth=0.60, segs=10,
        loc=(-0.85, 0, 1.10), parent=base, mat_=M_COW_WHITE)
    smooth_sphere(f"{name}_tail_t", r=0.08, loc=(-0.95, 0, 0.75),
                  parent=base, mat_=M_COW_BLACK)
    base["_phase"] = random.uniform(0, math.pi*2)
    return {"root": base, "he": head_e}

cows = []
cow_pos = [(-15, 3, 0, math.radians(20)), (-12, -2, 0, math.radians(45)),
           (15, 3, 0, math.radians(-20)), (12, -2, 0, math.radians(-45)),
           (-15, -8, 0, math.radians(90)), (15, -8, 0, math.radians(-90))]
for i, (cx, cy, cz, fac) in enumerate(cow_pos):
    c = make_friesian_cow(f"cow{i}", (cx, cy, cz), facing=fac)
    cows.append(c)

# ============ 2 DRAFT HORSES ============
def make_draft_horse(name, loc, body_color=M_HORSE_CHESTNUT, facing=0):
    base = empty(name, loc)
    base.rotation_euler = (0, 0, facing)
    # Massive body (draft horse)
    smooth_sphere(f"{name}_body", r=0.65, segs=20, rings=14, loc=(0, 0, 1.40),
                  parent=base, mat_=body_color, scale=(1.8, 1.1, 1.1))
    # Neck (powerful)
    neck = beveled_cube(f"{name}_neck", (0.45, 0.35, 0.70), bevel_offset=0.05,
                       loc=(0.95, 0, 1.55), parent=base, mat_=body_color)
    neck.rotation_euler = (0, math.radians(-25), 0)
    # Head
    head_e = empty(f"{name}_he", (1.45, 0, 1.90), parent=base)
    beveled_cube(f"{name}_head", (0.55, 0.28, 0.30), bevel_offset=0.05,
                 loc=(0, 0, 0), parent=head_e, mat_=body_color)
    smooth_cone(f"{name}_muzzle", r1=0.13, r2=0.10, depth=0.30, segs=14,
                loc=(0.30, 0, -0.06), parent=head_e,
                mat_=body_color).rotation_euler = (0, math.radians(90), 0)
    # Eyes
    for side in (-1, 1):
        smooth_sphere(f"{name}_eye{side}", r=0.05,
                      loc=(0.10, side*0.14, 0.08), parent=head_e, mat_=M_COW_BLACK)
    # Ears
    for side in (-1, 1):
        ear = smooth_cone(f"{name}_ear{side}", r1=0.06, r2=0.01, depth=0.18, segs=10,
                          loc=(-0.10, side*0.12, 0.20), parent=head_e, mat_=body_color)
        ear.rotation_euler = (math.radians(-15), 0, math.radians(side*15))
    # MASSIVE MANE (signature draft horse)
    for mi in range(8):
        beveled_cube(f"{name}_mane{mi}", (0.06, 0.10, 0.35),
                     loc=(0.6 - mi*0.15, 0, 1.85 - mi*0.05), parent=base, mat_=M_HORSE_MANE)
    # 4 powerful legs
    for x_idx, x in enumerate((0.55, -0.55)):
        for y_idx, y in enumerate((-0.40, 0.40)):
            cyl(f"{name}_leg{x_idx}{y_idx}", r=0.13, depth=1.0, segs=10,
                loc=(x, y, 0.50), parent=base, mat_=body_color)
            # Feathered fetlock (signature draft signature)
            smooth_sphere(f"{name}_feath{x_idx}{y_idx}", r=0.15,
                          loc=(x, y, 0.20), parent=base, mat_=M_HORSE_WHITE_D,
                          scale=(1, 1, 0.5))
            # Hoof
            cyl(f"{name}_hoof{x_idx}{y_idx}", r=0.14, depth=0.12, segs=10,
                loc=(x, y, 0.05), parent=base, mat_=M_COW_BLACK)
    # Tail (long)
    tail_e = empty(f"{name}_te", (-0.95, 0, 1.40), parent=base)
    for ti in range(5):
        cyl(f"{name}_tail{ti}", r=0.06 - ti*0.005, depth=0.30, segs=10,
            loc=(0, 0, -ti*0.20), parent=tail_e, mat_=M_HORSE_MANE)
    base["_phase"] = random.uniform(0, math.pi*2)
    return {"root": base, "he": head_e}

horses = [
    make_draft_horse("horse1", (-18, -4, 0), facing=math.radians(60)),
    make_draft_horse("horse2", (18, -4, 0), facing=math.radians(-60)),
]

# Tulip bouquet near farmhouse (signature)
for bi in range(3):
    bx_b = -3 + bi*3
    bouq_e = empty(f"bouquet{bi}", (bx_b, 7, 0))
    cyl(f"bouq_vase{bi}", r=0.20, depth=0.40, segs=14, loc=(0, 0, 0.20),
        parent=bouq_e, mat_=M_BRICK_RED)
    for fi in range(7):
        fa = (fi / 7.0) * math.pi * 2
        col = tulip_colors[fi % 6]
        smooth_sphere(f"bouq_f{bi}_{fi}", r=0.10,
                      loc=(0.10*math.cos(fa), 0.10*math.sin(fa), 0.50 + fi*0.04),
                      parent=bouq_e, mat_=col, scale=(1, 1, 1.5))

# ============================================================
# ⭐ 600 TULIP PETALS + 400 WIND PARTICLES (PARTICULES THÉMATIQUES OBLIGATOIRES)
# ============================================================
tulip_petals = []
for i in range(600):
    px = random.uniform(-30, 30)
    py = random.uniform(-30, 30)
    pz = random.uniform(0.5, 10)
    col = tulip_colors[i % 6]
    p_obj = smooth_sphere(f"tp{i}", r=random.uniform(0.08, 0.14), segs=10, rings=6,
                          loc=(px, py, pz), mat_=col,
                          scale=(1.4, 0.6, 0.15))
    p_obj.rotation_euler = (random.uniform(0, math.pi*2),
                            random.uniform(0, math.pi*2),
                            random.uniform(0, math.pi*2))
    p_obj["_phase"] = random.uniform(0, math.pi*2)
    p_obj["_base_x"] = px; p_obj["_base_y"] = py; p_obj["_base_z"] = pz
    p_obj["_speed"] = random.uniform(0.4, 1.2)
    p_obj["_drift_x"] = random.uniform(-2.0, 2.0)
    p_obj["_drift_y"] = random.uniform(-1.0, 1.0)
    tulip_petals.append(p_obj)

# 400 wind particles (signature)
wind_particles = []
for i in range(400):
    px = random.uniform(-40, 40)
    py = random.uniform(-40, 40)
    pz = random.uniform(0.5, 12)
    w_obj = smooth_sphere(f"wp{i}", r=random.uniform(0.10, 0.18), segs=10, rings=6,
                          loc=(px, py, pz), mat_=M_WIND,
                          scale=(1.5, 0.3, 0.3))
    w_obj["_phase"] = random.uniform(0, math.pi*2)
    w_obj["_base_x"] = px; w_obj["_base_y"] = py; w_obj["_base_z"] = pz
    w_obj["_amp_x"] = random.uniform(2.0, 4.5)
    w_obj["_amp_y"] = random.uniform(0.5, 1.5)
    w_obj["_amp_z"] = random.uniform(0.4, 1.0)
    w_obj["_speed"] = random.uniform(0.8, 1.6)
    wind_particles.append(w_obj)

# ============ ANIMATION ============
fps = 30; duration_s = 6; total_frames = fps * duration_s

# Windmill sails rotate (signature)
for m in windmills:
    for f in range(1, total_frames + 1, 3):
        t = (f - 1) / fps
        m["sails"].rotation_euler = (math.radians(90), 0, t * 1.5)
        m["sails"].keyframe_insert("rotation_euler", frame=f)

# Tulips sway
for tul in tulips[::5]:  # animate 1/5 to keep file size
    phase = tul["_phase"]
    for f in range(1, total_frames + 1, 6):
        t_v = (f - 1) / fps
        tul.rotation_euler = (math.sin(t_v * 1.5 + phase) * math.radians(6),
                                math.cos(t_v * 1.2 + phase) * math.radians(4),
                                0)
        tul.keyframe_insert("rotation_euler", frame=f)

# Farmers work
for fa in farmers:
    phase = fa["root"]["_phase"]
    base_z = fa["root"].location.z
    for f in range(1, total_frames + 1, 4):
        t = (f - 1) / fps
        fa["root"].location.z = base_z + math.sin(t * 1.2 + phase) * 0.04
        fa["root"].keyframe_insert("location", frame=f)
        for ai, arm in enumerate(fa["arms"]):
            base_rx = arm.rotation_euler.x
            wave = math.sin(t * 2.0 + phase + ai * math.pi) * math.radians(15)
            arm.rotation_euler = (base_rx + wave, 0, arm.rotation_euler.z)
            arm.keyframe_insert("rotation_euler", frame=f)
        fa["he"].rotation_euler = (math.sin(t * 1.0 + phase) * math.radians(6), 0,
                                    math.sin(t * 0.8 + phase) * math.radians(15))
        fa["he"].keyframe_insert("rotation_euler", frame=f)

# Cows graze
for c in cows:
    phase = c["root"]["_phase"]
    base_z = c["root"].location.z
    for f in range(1, total_frames + 1, 5):
        t = (f - 1) / fps
        c["root"].location.z = base_z + math.sin(t * 1.0 + phase) * 0.04
        c["root"].keyframe_insert("location", frame=f)
        c["he"].rotation_euler = (math.sin(t * 0.8 + phase) * math.radians(12), 0,
                                    math.sin(t * 0.5 + phase) * math.radians(15))
        c["he"].keyframe_insert("rotation_euler", frame=f)

# Horses
for h in horses:
    phase = h["root"]["_phase"]
    base_z = h["root"].location.z
    for f in range(1, total_frames + 1, 4):
        t = (f - 1) / fps
        h["root"].location.z = base_z + abs(math.sin(t * 1.5 + phase)) * 0.06
        h["root"].keyframe_insert("location", frame=f)
        h["he"].rotation_euler = (math.sin(t * 1.0 + phase) * math.radians(8), 0,
                                    math.sin(t * 0.7 + phase) * math.radians(10))
        h["he"].keyframe_insert("rotation_euler", frame=f)

# Storks bob heads
for s in storks:
    phase = s["root"]["_phase"]
    for f in range(1, total_frames + 1, 4):
        t = (f - 1) / fps
        s["he"].rotation_euler = (math.sin(t * 1.5 + phase) * math.radians(10), 0,
                                    math.sin(t * 1.0 + phase) * math.radians(15))
        s["he"].keyframe_insert("rotation_euler", frame=f)

# Boats rock
for b in boats:
    for f in range(1, total_frames + 1, 4):
        t = (f - 1) / fps
        b.rotation_euler = (math.sin(t * 1.5) * math.radians(3),
                             math.cos(t * 1.2) * math.radians(2),
                             b.rotation_euler.z)
        b.location.z = math.sin(t * 1.5) * 0.05
        b.keyframe_insert("rotation_euler", frame=f)
        b.keyframe_insert("location", frame=f)

# Clouds drift
for c_e in clouds:
    phase = c_e["_phase"]
    bx, by = c_e.location.x, c_e.location.y
    for f in range(1, total_frames + 1, 8):
        t = (f - 1) / fps
        c_e.location = (bx + math.sin(t * 0.3 + phase) * 0.8,
                        by + math.cos(t * 0.25 + phase) * 0.8,
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
# ⭐⭐⭐ 600 TULIP PETALS + 400 WIND PARTICLES
# ============================================================
for p in tulip_petals:
    phase = p["_phase"]; speed = p["_speed"]
    bx, by, bz = p["_base_x"], p["_base_y"], p["_base_z"]
    drift_x = p["_drift_x"]; drift_y = p["_drift_y"]
    for f in range(1, total_frames + 1, 5):
        t = (f - 1) / fps
        # Wind blown
        z = bz + math.sin(t * 1.2 + phase) * 1.0
        x = bx + drift_x * (math.sin(t * 1.0 + phase) + t * 0.3) * 0.5
        y = by + drift_y * math.cos(t * 0.8 + phase) * 0.6
        p.location = (x, y, max(0.3, z))
        p.rotation_euler = (phase + t * 1.7, phase + t * 1.5, phase + t * 2.0)
        p.keyframe_insert("location", frame=f)
        p.keyframe_insert("rotation_euler", frame=f)

# 400 WIND particles fast drift
for w in wind_particles:
    phase = w["_phase"]; speed = w["_speed"]
    bx, by, bz = w["_base_x"], w["_base_y"], w["_base_z"]
    ax, ay, az = w["_amp_x"], w["_amp_y"], w["_amp_z"]
    for f in range(1, total_frames + 1, 3):
        t = (f - 1) / fps
        # Wind blows mostly in X direction (signature wind from sea)
        x = bx + ax * (math.sin(t * speed + phase) + t * 0.6)
        y = by + ay * math.cos(t * speed * 0.9 + phase)
        z = bz + az * math.sin(t * speed * 1.2 + phase)
        # Wrap around
        if x > 50: x = -50
        w.location = (x, y, max(0.3, z))
        sc = 1 + math.sin(t * 4.0 + phase) * 0.2
        w.scale = (sc * 1.5, sc * 0.3, sc * 0.3)
        w.keyframe_insert("location", frame=f)
        w.keyframe_insert("scale", frame=f)

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
out_glb = os.path.join(out_dir, "pbr_netherlands_proc.glb")

bpy.ops.object.select_all(action='SELECT')
bpy.ops.export_scene.gltf(
    filepath=out_glb, export_format='GLB',
    export_animations=True, export_apply=False, export_yup=True, use_selection=False,
)
size_mb = os.path.getsize(out_glb) / (1024 * 1024)
print(f"[proc_dutch_tulip_windmill_field] DONE → {out_glb} ({size_mb:.2f} MB)")
print(f"[proc_dutch_tulip_windmill_field] ONE earth ground + 800 tulips multicolor rows + 4 windmills rotating sails + farmhouse stepped gable + canals + 2 boats + 5 farmers clogs + 6 Friesian cows + 2 draft horses + storks nest + 600 TULIP PETALS + 400 WIND PARTICLES")
print("⭐ FIXES: 1 ground + 600 tulip petals + 400 wind particles (signature Netherlands mandatory) ⭐")
