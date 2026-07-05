"""
proc_japanese_hanami_sakura.py — 213e procédural AuroraIA (77e qualité)
Hanami Japon : ONE ground + 800 pétales sakura tombant + 12 cerisiers + torii + temple + 8 visiteurs kimono + koi + grues + Mt Fuji
FIXES : 1 ground propre + sakura petals falling thématique
"""
import bpy, bmesh, math, random, os

random.seed(0x5A4A213)

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

# Materials - soft pastel Japan
M_SKY = mat("sky", (0.95, 0.75, 0.85, 1.0), 0.0, 0.7, emission=(0.92,0.72,0.85), emission_strength=1.8)
M_SUN = mat("sun", (1.0, 0.85, 0.55, 1.0), 0.0, 0.10, emission=(1.0,0.85,0.55), emission_strength=14.0)
M_CLOUD = mat("cloud", (1.0, 0.90, 0.85, 1.0), 0.0, 0.55, emission=(0.95,0.88,0.85), emission_strength=2.0, alpha=0.85)

# === ONE ground - grass tatami ===
M_GROUND = mat("ground", (0.55, 0.65, 0.35, 1.0), 0.0, 0.85, emission=(0.45,0.55,0.30), emission_strength=0.3)
M_PATH = mat("path", (0.65, 0.55, 0.40, 1.0), 0.0, 0.75, emission=(0.55,0.48,0.35), emission_strength=0.3)
M_ROCK = mat("rock", (0.45, 0.42, 0.40, 1.0), 0.0, 0.85)
M_MOSS = mat("moss", (0.30, 0.55, 0.25, 1.0), 0.0, 0.75, emission=(0.25,0.50,0.22), emission_strength=0.4)

# Sakura colors
M_SAKURA_PINK = mat("sakura_p", (1.0, 0.75, 0.85, 1.0), 0.0, 0.50, emission=(1.0,0.75,0.85), emission_strength=1.8)
M_SAKURA_DEEP = mat("sakura_d", (1.0, 0.55, 0.75, 1.0), 0.0, 0.50, emission=(1.0,0.55,0.75), emission_strength=2.2)
M_SAKURA_WHITE = mat("sakura_w", (1.0, 0.95, 0.92, 1.0), 0.0, 0.50, emission=(1.0,0.95,0.92), emission_strength=1.5)
M_PETAL = mat("petal", (1.0, 0.65, 0.80, 1.0), 0.0, 0.45, emission=(1.0,0.65,0.80), emission_strength=2.0)
M_TRUNK = mat("trunk", (0.30, 0.20, 0.15, 1.0), 0.0, 0.85)
M_TRUNK_GRAY = mat("trunk_g", (0.40, 0.32, 0.30, 1.0), 0.0, 0.85)

# Torii red
M_TORII_RED = mat("torii", (0.85, 0.18, 0.18, 1.0), 0.0, 0.55, emission=(0.78,0.18,0.15), emission_strength=0.8)
M_TORII_BLACK = mat("torii_bk", (0.08, 0.06, 0.06, 1.0), 0.0, 0.85)

# Temple
M_TEMPLE_WOOD = mat("temple_w", (0.55, 0.30, 0.15, 1.0), 0.0, 0.70, emission=(0.50,0.28,0.13), emission_strength=0.4)
M_TEMPLE_ROOF = mat("temple_r", (0.40, 0.10, 0.10, 1.0), 0.0, 0.55, emission=(0.35,0.10,0.10), emission_strength=0.5)
M_TEMPLE_GOLD = mat("temple_g", (1.0, 0.78, 0.30, 1.0), 0.95, 0.18, emission=(0.95,0.72,0.28), emission_strength=0.8)
M_TEMPLE_WHITE = mat("temple_white", (0.95, 0.92, 0.85, 1.0), 0.0, 0.55, emission=(0.85,0.82,0.78), emission_strength=0.5)

# Lanterns
M_LANTERN = mat("lantern", (1.0, 0.55, 0.20, 1.0), 0.0, 0.30, emission=(1.0,0.60,0.25), emission_strength=8.0)
M_LANTERN_FRAME = mat("lantern_f", (0.15, 0.10, 0.08, 1.0), 0.3, 0.55)

# Kimono colors
M_KIMONO_PINK = mat("k_pink", (0.95, 0.55, 0.70, 1.0), 0.0, 0.55, emission=(0.90,0.50,0.65), emission_strength=0.6)
M_KIMONO_RED = mat("k_red", (0.85, 0.20, 0.25, 1.0), 0.0, 0.55, emission=(0.78,0.20,0.22), emission_strength=0.7)
M_KIMONO_BLUE = mat("k_blue", (0.20, 0.40, 0.65, 1.0), 0.0, 0.55, emission=(0.18,0.35,0.60), emission_strength=0.6)
M_KIMONO_PURPLE = mat("k_p", (0.55, 0.30, 0.65, 1.0), 0.0, 0.55, emission=(0.50,0.28,0.60), emission_strength=0.6)
M_KIMONO_GREEN = mat("k_g", (0.30, 0.55, 0.35, 1.0), 0.0, 0.55, emission=(0.28,0.50,0.32), emission_strength=0.5)
M_OBI_GOLD = mat("obi_g", (0.95, 0.78, 0.30, 1.0), 0.5, 0.40, emission=(0.85,0.70,0.28), emission_strength=0.7)
M_OBI_BLACK = mat("obi_bk", (0.05, 0.05, 0.05, 1.0), 0.0, 0.65)
M_SKIN_JAPAN = mat("skin_j", (0.95, 0.85, 0.78, 1.0), 0.0, 0.55, emission=(0.85,0.78,0.72), emission_strength=0.35)
M_HAIR_BLACK = mat("hair", (0.05, 0.04, 0.04, 1.0), 0.0, 0.85)

# Pond
M_WATER = mat("water", (0.30, 0.55, 0.65, 0.75), 0.4, 0.10, emission=(0.40,0.65,0.75), emission_strength=0.8, alpha=0.75)
M_KOI_ORANGE = mat("koi_o", (1.0, 0.55, 0.10, 1.0), 0.0, 0.45, emission=(1.0,0.55,0.10), emission_strength=2.5)
M_KOI_WHITE = mat("koi_w", (1.0, 0.95, 0.92, 1.0), 0.0, 0.45, emission=(0.95,0.90,0.85), emission_strength=1.0)
M_KOI_BLACK = mat("koi_b", (0.10, 0.08, 0.06, 1.0), 0.0, 0.60)
M_LOTUS = mat("lotus", (1.0, 0.85, 0.92, 1.0), 0.0, 0.55, emission=(1.0,0.85,0.92), emission_strength=1.2)
M_LOTUS_LEAF = mat("lotus_l", (0.25, 0.55, 0.30, 1.0), 0.0, 0.65, emission=(0.20,0.50,0.25), emission_strength=0.4)

# Crane
M_CRANE = mat("crane", (0.95, 0.93, 0.90, 1.0), 0.0, 0.55, emission=(0.88,0.86,0.85), emission_strength=0.6)
M_CRANE_RED = mat("crane_r", (0.85, 0.15, 0.12, 1.0), 0.0, 0.55, emission=(0.78,0.15,0.12), emission_strength=0.8)
M_CRANE_BLACK = mat("crane_bk", (0.05, 0.04, 0.04, 1.0), 0.0, 0.70)

# Tea pavilion + picnic
M_TATAMI = mat("tatami", (0.85, 0.70, 0.45, 1.0), 0.0, 0.70, emission=(0.75,0.62,0.40), emission_strength=0.4)
M_BENTO_WOOD = mat("bento_w", (0.40, 0.25, 0.15, 1.0), 0.0, 0.65, emission=(0.35,0.22,0.13), emission_strength=0.3)
M_RICE = mat("rice", (0.95, 0.92, 0.85, 1.0), 0.0, 0.55, emission=(0.90,0.88,0.82), emission_strength=0.5)
M_TEA_BOWL = mat("bowl", (0.85, 0.65, 0.35, 1.0), 0.6, 0.35, emission=(0.78,0.58,0.30), emission_strength=0.5)

# Mountain Fuji
M_FUJI = mat("fuji", (0.55, 0.55, 0.65, 1.0), 0.0, 0.80)
M_FUJI_SNOW = mat("fuji_s", (0.98, 0.98, 1.0, 1.0), 0.0, 0.45, emission=(0.92,0.92,0.98), emission_strength=0.8)

# ============ SKY + SUN + CLOUDS ============
sky = smooth_sphere("sky", r=100, segs=32, rings=20, loc=(0,0,0), mat_=M_SKY, scale=(1,1,0.6))
sky.scale = (1,1,0.6)
sun = smooth_sphere("sun", r=4.0, loc=(0, 40, 20), mat_=M_SUN)
for i in range(3):
    smooth_sphere(f"sun_halo{i}", r=4.0 + (i+1)*1.5, loc=(0, 40, 20), mat_=M_SUN)

# 8 clouds drift
clouds = []
for i in range(8):
    a = (i / 8.0) * math.pi * 2
    rad = random.uniform(22, 32)
    cx, cy = rad*math.cos(a), rad*math.sin(a)
    cz = random.uniform(14, 22)
    c_e = empty(f"cloud_e{i}", (cx, cy, cz))
    for j in range(5):
        smooth_sphere(f"cloud{i}_{j}", r=random.uniform(2.0, 3.2),
                      loc=(random.uniform(-3,3), random.uniform(-2,2), random.uniform(-0.5,0.5)),
                      parent=c_e, mat_=M_CLOUD)
    c_e["_phase"] = random.uniform(0, math.pi*2)
    clouds.append(c_e)

# ============ Mt Fuji background (single huge cone with snow cap) ============
fuji_e = empty("fuji", loc=(0, 38, 4))
fuji_main = smooth_cone("fuji_main", r1=14, r2=2.5, depth=10, segs=32,
                         loc=(0, 0, 0), parent=fuji_e, mat_=M_FUJI)
# Snow cap top
smooth_cone("fuji_snow", r1=3.5, r2=2.0, depth=2.0, segs=32,
            loc=(0, 0, 5.5), parent=fuji_e, mat_=M_FUJI_SNOW)
# 2 small side mountains
for side in (-1, 1):
    smooth_cone(f"fuji_side{side}", r1=7, r2=1.5, depth=6, segs=24,
                loc=(side*16, -2, -2), parent=fuji_e, mat_=M_FUJI)
    smooth_cone(f"fuji_side_snow{side}", r1=2.0, r2=1.0, depth=1.2, segs=20,
                loc=(side*16, -2, 2.5), parent=fuji_e, mat_=M_FUJI_SNOW)

# ============ ONE clean park ground (single plane) ============
ground = beveled_cube("ground", (80, 80, 0.5), bevel_offset=0.08, loc=(0, 0, -0.25), mat_=M_GROUND)

# Path of stones (organic 3D, scattered)
for i in range(30):
    px = (i - 15) * 1.2
    py = math.sin(i * 0.3) * 1.5
    smooth_sphere(f"path_stone{i}", r=random.uniform(0.30, 0.55), segs=14, rings=10,
                  loc=(px, py, 0.08), mat_=M_PATH,
                  scale=(1.2, 1.0, 0.30))

# 15 rocks scattered (organic 3D)
for i in range(15):
    a = random.uniform(0, math.pi*2)
    rad = random.uniform(6, 25)
    smooth_sphere(f"rock{i}", r=random.uniform(0.4, 0.9),
                  loc=(rad*math.cos(a), rad*math.sin(a), 0.30),
                  mat_=M_ROCK,
                  scale=(random.uniform(0.8,1.3), random.uniform(0.8,1.3),
                         random.uniform(0.5,0.8)))

# 20 moss patches (small organic)
for i in range(20):
    a = random.uniform(0, math.pi*2)
    rad = random.uniform(4, 28)
    smooth_sphere(f"moss{i}", r=random.uniform(0.35, 0.7),
                  loc=(rad*math.cos(a), rad*math.sin(a), 0.10),
                  mat_=M_MOSS, scale=(1, 1, 0.15))

# ============ 12 CHERRY TREES SAKURA in full bloom ============
def make_sakura(name, loc, scale=1.0):
    base = empty(name, loc)
    # Trunk 5-seg twisted (signature curved trunks)
    for i in range(5):
        r1 = (0.38 - i*0.04) * scale
        r2 = (0.34 - i*0.04) * scale
        seg = smooth_cone(f"{name}_t{i}", r1=r1, r2=r2, depth=0.9, segs=14,
                          loc=(random.uniform(-0.05,0.05), random.uniform(-0.05,0.05),
                               (i+0.5)*0.9),
                          parent=base, mat_=M_TRUNK_GRAY)
        seg.rotation_euler = (math.radians(random.uniform(-5,5)),
                              math.radians(random.uniform(-5,5)), 0)
    # 5 main branches radiating
    top_z = 4.5
    branches_e = []
    for j in range(5):
        a = (j / 5.0) * math.pi * 2
        b_e = empty(f"{name}_b_e{j}", (0, 0, top_z - 0.5), parent=base)
        b_e.rotation_euler = (math.radians(55), 0, a)
        # 3 segments tapered branches
        for k in range(3):
            cyl(f"{name}_b{j}_{k}", r=(0.13 - k*0.025)*scale, depth=0.7*scale, segs=10,
                loc=(0, (k+0.5)*0.7*scale, 0), parent=b_e, mat_=M_TRUNK).rotation_euler = (math.radians(90), 0, 0)
        branches_e.append(b_e)
    # Canopy MASSIVE pink puffs (signature full bloom)
    sakura_colors = [M_SAKURA_PINK, M_SAKURA_DEEP, M_SAKURA_WHITE]
    # Main puffs
    for j in range(8):
        a = (j / 8.0) * math.pi * 2
        rad = random.uniform(1.5, 2.5) * scale
        col = sakura_colors[j % 3]
        smooth_sphere(f"{name}_can{j}", r=random.uniform(1.1, 1.6) * scale,
                      loc=(rad*math.cos(a), rad*math.sin(a),
                           top_z + random.uniform(0, 1.0)),
                      parent=base, mat_=col, scale=(1, 1, 0.85))
    # Smaller fluffy puffs
    for j in range(12):
        a = random.uniform(0, math.pi*2)
        rad = random.uniform(1.0, 2.8) * scale
        col = random.choice(sakura_colors)
        smooth_sphere(f"{name}_subcan{j}", r=random.uniform(0.5, 0.85) * scale,
                      loc=(rad*math.cos(a), rad*math.sin(a),
                           top_z + random.uniform(-0.3, 0.8)),
                      parent=base, mat_=col, scale=(1, 1, 0.7))
    base["_phase"] = random.uniform(0, math.pi*2)
    return base

trees = []
tree_pos = [(-12, 5, 0, 1.0), (12, 8, 0, 1.1),
            (-15, -5, 0, 0.95), (8, -10, 0, 1.0),
            (-20, 2, 0, 1.0), (18, 4, 0, 0.9),
            (-8, 18, 0, 1.05), (10, -20, 0, 0.95),
            (-18, 18, 0, 0.9), (20, -15, 0, 1.0),
            (-5, -18, 0, 0.95), (5, 18, 0, 1.05)]
for i, (tx, ty, tz, sc) in enumerate(tree_pos):
    t = make_sakura(f"tree{i}", (tx, ty, tz), scale=sc)
    trees.append(t)

# ============ TORII GATE (red) ============
torii_e = empty("torii", loc=(0, -8, 0))
# 2 vertical pillars
for side in (-1, 1):
    cyl(f"torii_pillar{side}", r=0.30, depth=4.5, segs=16,
        loc=(side*2.0, 0, 2.25), parent=torii_e, mat_=M_TORII_RED)
# Top horizontal beam (kasagi - curved up at ends)
beveled_cube("torii_top", (5.5, 0.4, 0.35), bevel_offset=0.06,
             loc=(0, 0, 4.65), parent=torii_e, mat_=M_TORII_RED)
# Upper rail black band (nuki)
beveled_cube("torii_top_band", (4.0, 0.5, 0.15), loc=(0, 0, 4.30),
             parent=torii_e, mat_=M_TORII_BLACK)
# 2 curved end pieces
for side in (-1, 1):
    end = beveled_cube(f"torii_end{side}", (0.5, 0.4, 0.55), bevel_offset=0.05,
                      loc=(side*2.5, 0, 4.85), parent=torii_e, mat_=M_TORII_RED)
    end.rotation_euler = (0, math.radians(side*-15), 0)
# Lower nuki rail
beveled_cube("torii_lower_rail", (3.6, 0.30, 0.20), loc=(0, 0, 3.40),
             parent=torii_e, mat_=M_TORII_RED)

# ============ TEMPLE SHINTO ============
temple_e = empty("temple", loc=(0, -18, 0))
# Platform
beveled_cube("temple_platform", (8, 5, 0.5), bevel_offset=0.06,
             loc=(0, 0, 0.25), parent=temple_e, mat_=M_TEMPLE_WOOD)
# 4 columns
for x_idx, x in enumerate((-1, 1)):
    for y_idx, y in enumerate((-1, 1)):
        cyl(f"temple_col{x_idx}{y_idx}", r=0.20, depth=3.0, segs=14,
            loc=(x*3.0, y*1.8, 2.0), parent=temple_e, mat_=M_TEMPLE_WOOD)
# Main body
beveled_cube("temple_body", (6.5, 3.5, 2.5), bevel_offset=0.05,
             loc=(0, 0, 2.25), parent=temple_e, mat_=M_TEMPLE_WHITE)
# Pagoda roof tier 1
for side in (-1, 1):
    roof = beveled_cube(f"temple_roof1_{side}", (7.5, 2.5, 0.25), bevel_offset=0.04,
                       loc=(0, side*1.5, 4.0), parent=temple_e, mat_=M_TEMPLE_ROOF)
    roof.rotation_euler = (math.radians(side*-20), 0, 0)
# Tier 2 smaller
beveled_cube("temple_tier2", (5.0, 2.5, 1.5), bevel_offset=0.05,
             loc=(0, 0, 4.85), parent=temple_e, mat_=M_TEMPLE_WHITE)
for side in (-1, 1):
    roof = beveled_cube(f"temple_roof2_{side}", (5.5, 2.0, 0.25), bevel_offset=0.04,
                       loc=(0, side*1.0, 5.85), parent=temple_e, mat_=M_TEMPLE_ROOF)
    roof.rotation_euler = (math.radians(side*-22), 0, 0)
# Gold finial top
smooth_cone("temple_finial", r1=0.30, r2=0.05, depth=1.5, segs=14,
            loc=(0, 0, 7.0), parent=temple_e, mat_=M_TEMPLE_GOLD)
smooth_sphere("temple_orb", r=0.20, loc=(0, 0, 7.85), parent=temple_e, mat_=M_TEMPLE_GOLD)

# ============ 6 LANTERNS japonaises ============
lanterns = []
lantern_pos = [(-5, -3, 0), (5, -3, 0), (-10, 0, 0), (10, 0, 0),
               (-3, -12, 0), (3, -12, 0)]
for i, (lx, ly, lz) in enumerate(lantern_pos):
    l_e = empty(f"lantern{i}", (lx, ly, lz))
    # Stone base
    cyl(f"lant_base{i}", r=0.25, depth=0.20, segs=14,
        loc=(0, 0, 0.10), parent=l_e, mat_=M_ROCK)
    # Pole
    cyl(f"lant_pole{i}", r=0.10, depth=1.5, segs=12,
        loc=(0, 0, 0.95), parent=l_e, mat_=M_LANTERN_FRAME)
    # Body
    cyl(f"lant_body{i}", r=0.35, depth=0.6, segs=16,
        loc=(0, 0, 2.0), parent=l_e, mat_=M_LANTERN)
    # Frame bands
    for fi in range(3):
        cyl(f"lant_fr{i}_{fi}", r=0.37, depth=0.04, segs=16,
            loc=(0, 0, 1.75 + fi*0.25), parent=l_e, mat_=M_LANTERN_FRAME)
    # Roof
    smooth_cone(f"lant_roof{i}", r1=0.45, r2=0.10, depth=0.30, segs=14,
                loc=(0, 0, 2.45), parent=l_e, mat_=M_LANTERN_FRAME)
    l_e["_phase"] = random.uniform(0, math.pi*2)
    lanterns.append(l_e)

# ============ KOI POND ============
pond_e = empty("pond", loc=(8, 10, 0))
# Water surface single disc
cyl("pond_water", r=4.0, depth=0.15, segs=32,
    loc=(0, 0, 0.05), parent=pond_e, mat_=M_WATER)
# 12 organic rim rocks
for i in range(12):
    a = (i / 12.0) * math.pi * 2
    smooth_sphere(f"pond_rim{i}", r=random.uniform(0.30, 0.50),
                  loc=(4.3*math.cos(a), 4.3*math.sin(a), 0.20),
                  parent=pond_e, mat_=M_ROCK)
# 5 koi fish swimming
kois = []
for i in range(5):
    a = (i / 5.0) * math.pi * 2
    rad = random.uniform(1.5, 3.0)
    kx = rad*math.cos(a)
    ky = rad*math.sin(a)
    k_e = empty(f"koi{i}", (kx, ky, -0.05), parent=pond_e)
    k_e.rotation_euler = (0, 0, a + math.pi/2)
    # Body
    color = M_KOI_ORANGE if i % 2 == 0 else M_KOI_WHITE
    smooth_sphere(f"koi_b{i}", r=0.20, segs=16, rings=12, loc=(0, 0, 0),
                  parent=k_e, mat_=color, scale=(2.5, 0.95, 0.7))
    # Spots (3 dark)
    for s in range(3):
        smooth_sphere(f"koi_s{i}_{s}", r=0.06,
                      loc=(-0.10 + s*0.10, 0, 0.10), parent=k_e,
                      mat_=M_KOI_BLACK if random.random() < 0.5 else M_KOI_ORANGE,
                      scale=(1, 1, 0.4))
    # Tail fin
    beveled_cube(f"koi_tail{i}", (0.15, 0.04, 0.10), loc=(-0.40, 0, 0),
                 parent=k_e, mat_=color)
    # 2 side fins
    for side in (-1, 1):
        fin = beveled_cube(f"koi_fin{i}_{side}", (0.10, 0.04, 0.08),
                          loc=(0.10, side*0.18, 0), parent=k_e, mat_=color)
    kois.append({"e": k_e, "phase": random.uniform(0, math.pi*2),
                 "orbit_rad": rad, "orbit_phase": a})
# 6 lotus flowers floating
for i in range(6):
    a = (i / 6.0) * math.pi * 2
    rad = 2.5
    lx_p = rad*math.cos(a)
    ly_p = rad*math.sin(a)
    # Leaf flat
    smooth_sphere(f"lotus_leaf{i}", r=0.35, loc=(lx_p, ly_p, 0.10),
                  parent=pond_e, mat_=M_LOTUS_LEAF, scale=(1, 1, 0.15))
    # Flower petals (6 petals around center)
    for j in range(6):
        pa = (j / 6.0) * math.pi * 2
        petal_x = lx_p + 0.10*math.cos(pa)
        petal_y = ly_p + 0.10*math.sin(pa)
        smooth_sphere(f"lotus_petal{i}_{j}", r=0.06,
                      loc=(petal_x, petal_y, 0.18),
                      parent=pond_e, mat_=M_LOTUS, scale=(1, 1, 0.7))

# ============ 8 VISITORS in kimonos ============
def make_visitor(name, loc, kimono_mat, hair_mat=M_HAIR_BLACK, action="stand", facing=0, scale=1.0):
    base = empty(name, loc)
    base.rotation_euler = (0, 0, facing)
    # Long kimono robe (signature cone form)
    smooth_cone(f"{name}_kimono", r1=0.45*scale, r2=0.30*scale, depth=1.4*scale, segs=18,
                loc=(0, 0, 0.7*scale), parent=base, mat_=kimono_mat)
    # OBI belt (signature wide sash)
    cyl(f"{name}_obi", r=0.42*scale, depth=0.25*scale, segs=18,
        loc=(0, 0, 1.40*scale), parent=base, mat_=M_OBI_GOLD)
    # Obi knot back (signature)
    beveled_cube(f"{name}_obi_knot", (0.30*scale, 0.20*scale, 0.20*scale), bevel_offset=0.03,
                 loc=(0, 0.35*scale, 1.45*scale), parent=base, mat_=M_OBI_GOLD)
    # Torso visible
    beveled_cube(f"{name}_torso", (0.42*scale, 0.28*scale, 0.50*scale), bevel_offset=0.05,
                 loc=(0, 0, 1.78*scale), parent=base, mat_=kimono_mat)
    # Neck
    cyl(f"{name}_neck", r=0.10*scale, depth=0.18*scale, segs=12,
        loc=(0, 0, 2.10*scale), parent=base, mat_=M_SKIN_JAPAN)
    # Head
    head_e = empty(f"{name}_head_e", (0, 0, 2.25*scale), parent=base)
    smooth_sphere(f"{name}_head", r=0.18*scale, segs=20, rings=14, loc=(0, 0, 0),
                  parent=head_e, mat_=M_SKIN_JAPAN)
    # Eyes (almond)
    for side in (-1, 1):
        smooth_sphere(f"{name}_eye{side}", r=0.022*scale,
                      loc=(side*0.06*scale, -0.15*scale, 0.02*scale), parent=head_e,
                      mat_=mat(f"{name}_ew{side}", (0.05,0.05,0.05,1), 0, 0.5))
    # Hair (black, traditional)
    smooth_sphere(f"{name}_hair", r=0.22*scale, loc=(0, 0.05*scale, 0.04*scale),
                  parent=head_e, mat_=hair_mat, scale=(1.05, 1.0, 0.85))
    # Long hair back (5 strands tied)
    for i in range(3):
        strand = beveled_cube(f"{name}_hair_b{i}", (0.06*scale, 0.10*scale, 0.45*scale),
                              loc=((i-1)*0.05*scale, 0.22*scale, -0.18*scale - i*0.05*scale),
                              parent=head_e, mat_=hair_mat)
        strand.rotation_euler = (math.radians(15), 0, 0)
    # Hair pin (kanzashi gold)
    cyl(f"{name}_kanzashi", r=0.015*scale, depth=0.20*scale, segs=8,
        loc=(0.10*scale, 0.10*scale, 0.18*scale), parent=head_e, mat_=M_OBI_GOLD)
    smooth_sphere(f"{name}_kanzashi_top", r=0.025*scale, loc=(0.10*scale, 0.10*scale, 0.30*scale),
                  parent=head_e, mat_=M_SAKURA_PINK)
    # 2 arms (action-dependent)
    arm_poses = {
        "stand": [(math.radians(-15), 0), (math.radians(-15), 0)],
        "sit": [(math.radians(-45), -15), (math.radians(-45), 15)],  # arms forward (sitting)
        "tea": [(math.radians(-90), -10), (math.radians(-60), 25)],  # holding cup
        "wave": [(math.radians(-160), -10), (math.radians(-15), 0)],
    }
    pose = arm_poses.get(action, arm_poses["stand"])
    for side_idx, side in enumerate((-1, 1)):
        sh = empty(f"{name}_sh{side_idx}", (side*0.30*scale, 0, 2.05*scale), parent=base)
        rx, rz = pose[side_idx]
        sh.rotation_euler = (rx, 0, math.radians(side*-15 + rz))
        # Sleeve (wide kimono sleeve signature)
        beveled_cube(f"{name}_sleeve{side_idx}", (0.20*scale, 0.30*scale, 0.50*scale), bevel_offset=0.04,
                     loc=(0, 0, -0.30*scale), parent=sh, mat_=kimono_mat)
        cyl(f"{name}_fa{side_idx}", r=0.07*scale, depth=0.30*scale, segs=10,
            loc=(0, 0, -0.55*scale), parent=sh, mat_=M_SKIN_JAPAN)
        # Hand
        smooth_sphere(f"{name}_hand{side_idx}", r=0.07*scale, loc=(0, 0, -0.72*scale),
                      parent=sh, mat_=M_SKIN_JAPAN)
    return {"root": base, "head_e": head_e}

# 8 visitors mixed
visitor_specs = [
    ("vis1", (1, 0, 0), M_KIMONO_PINK, "stand", math.radians(180), 1.0),
    ("vis2", (-2, 1, 0), M_KIMONO_BLUE, "wave", math.radians(120), 0.95),
    ("vis3", (3, -2, 0), M_KIMONO_RED, "stand", math.radians(-90), 1.0),
    ("vis4", (-4, 4, 0), M_KIMONO_PURPLE, "sit", math.radians(45), 0.85),  # picnic
    ("vis5", (-3, 5, 0), M_KIMONO_GREEN, "sit", math.radians(-45), 0.85),  # picnic
    ("vis6", (-5, 3, 0), M_KIMONO_PINK, "tea", math.radians(90), 0.85),  # tea
    ("vis7", (6, 5, 0), M_KIMONO_BLUE, "stand", math.radians(0), 0.75),   # child
    ("vis8", (7, 4, 0), M_KIMONO_RED, "wave", math.radians(45), 0.75),    # child
]
visitors = []
for spec in visitor_specs:
    name, loc, kimono, action, fac, sc = spec
    v = make_visitor(name, loc, kimono, action=action, facing=fac, scale=sc)
    visitors.append(v)

# ============ PICNIC SETUP (tatami mat + bento boxes + tea) ============
picnic_e = empty("picnic", loc=(-4, 4, 0))
# Tatami mat (rectangular)
beveled_cube("tatami", (2.5, 1.8, 0.05), bevel_offset=0.04,
             loc=(0, 0, 0.05), parent=picnic_e, mat_=M_TATAMI)
# 3 bento boxes
for i in range(3):
    bx = (i - 1) * 0.6
    beveled_cube(f"bento{i}", (0.45, 0.30, 0.12), bevel_offset=0.04,
                 loc=(bx, 0, 0.16), parent=picnic_e, mat_=M_BENTO_WOOD)
    # Rice
    smooth_sphere(f"rice{i}", r=0.12, loc=(bx, 0, 0.24),
                  parent=picnic_e, mat_=M_RICE, scale=(1.3, 1.0, 0.4))
# 2 tea bowls
for side in (-1, 1):
    cyl(f"tea_bowl_{side}", r=0.10, depth=0.10, segs=14,
        loc=(side*0.5, -0.55, 0.15), parent=picnic_e, mat_=M_TEA_BOWL)
    # Tea liquid
    smooth_sphere(f"tea_liquid_{side}", r=0.09, loc=(side*0.5, -0.55, 0.18),
                  parent=picnic_e, mat_=mat(f"tea{side}", (0.30, 0.55, 0.30, 1.0), 0, 0.3,
                                              emission=(0.30,0.55,0.30), emission_strength=0.5),
                  scale=(1, 1, 0.3))

# ============ TEA PAVILION (small) ============
pavilion_e = empty("pavilion", loc=(15, 12, 0))
# Wood platform
beveled_cube("pav_floor", (3.5, 3.0, 0.20), bevel_offset=0.04,
             loc=(0, 0, 0.10), parent=pavilion_e, mat_=M_TEMPLE_WOOD)
# 4 columns
for x_idx, x in enumerate((-1, 1)):
    for y_idx, y in enumerate((-1, 1)):
        cyl(f"pav_col{x_idx}{y_idx}", r=0.10, depth=2.5, segs=12,
            loc=(x*1.5, y*1.3, 1.45), parent=pavilion_e, mat_=M_TEMPLE_WOOD)
# Pagoda roof
for side in (-1, 1):
    roof = beveled_cube(f"pav_roof_{side}", (4, 2.0, 0.20), bevel_offset=0.04,
                       loc=(0, side*1.2, 3.0), parent=pavilion_e, mat_=M_TEMPLE_ROOF)
    roof.rotation_euler = (math.radians(side*-25), 0, 0)
# Top finial
smooth_cone("pav_finial", r1=0.15, r2=0.02, depth=0.50, segs=12,
            loc=(0, 0, 3.40), parent=pavilion_e, mat_=M_TEMPLE_GOLD)
# Hanging lantern inside
cyl("pav_lantern", r=0.20, depth=0.40, segs=16,
    loc=(0, 0, 2.30), parent=pavilion_e, mat_=M_LANTERN)

# ============ 4 CRANES (white) standing + flying ============
def make_crane(name, loc, flying=False, facing=0):
    base = empty(name, loc)
    base.rotation_euler = (0, 0, facing)
    z_off = 5 if flying else 0
    # Body
    smooth_sphere(f"{name}_body", r=0.35, segs=20, rings=14, loc=(0, 0, 1.0 + z_off),
                  parent=base, mat_=M_CRANE, scale=(2.0, 0.9, 1.0))
    # Long S-curved neck (signature crane)
    neck_e = empty(f"{name}_neck_e", (0.50, 0, 1.30 + z_off), parent=base)
    for i in range(5):
        a = i * 0.5
        nx = 0.15 * math.sin(a)
        nz = 0.15 * math.cos(a) + i * 0.18
        cyl(f"{name}_neck{i}", r=0.06, depth=0.20, segs=10,
            loc=(nx, 0, nz), parent=neck_e, mat_=M_CRANE)
    # Head
    head_e = empty(f"{name}_head_e", (0.15, 0, 1.10), parent=neck_e)
    smooth_sphere(f"{name}_h", r=0.10, segs=16, rings=12, loc=(0, 0, 0),
                  parent=head_e, mat_=M_CRANE)
    # Red crown (signature crane red patch)
    smooth_sphere(f"{name}_crown", r=0.06, loc=(0, 0.04, 0.06),
                  parent=head_e, mat_=M_CRANE_RED, scale=(1, 1, 0.6))
    # Beak (pointed)
    smooth_cone(f"{name}_beak", r1=0.04, r2=0.005, depth=0.25, segs=10,
                loc=(0.15, 0, -0.05), parent=head_e, mat_=M_CRANE_BLACK).rotation_euler = (math.radians(75), 0, 0)
    # Eye
    smooth_sphere(f"{name}_eye", r=0.02, loc=(0.05, 0, 0.05),
                  parent=head_e, mat_=M_CRANE_BLACK)
    # 2 wings
    wings = []
    if flying:
        # Spread wings
        for side_idx, side in enumerate((-1, 1)):
            w_e = empty(f"{name}_w{side_idx}", (0, side*0.30, 1.0 + z_off), parent=base)
            beveled_cube(f"{name}_w_main{side_idx}", (0.50, 0.85, 0.05), bevel_offset=0.03,
                         loc=(0, side*0.45, 0), parent=w_e, mat_=M_CRANE)
            # Black tip
            beveled_cube(f"{name}_w_tip{side_idx}", (0.40, 0.30, 0.04),
                         loc=(0, side*0.85, 0), parent=w_e, mat_=M_CRANE_BLACK)
            wings.append((w_e, side))
    else:
        # Folded wings
        for side in (-1, 1):
            beveled_cube(f"{name}_w_fold{side}", (0.10, 0.40, 0.30), bevel_offset=0.03,
                         loc=(0, side*0.25, 1.0 + z_off), parent=base, mat_=M_CRANE)
    # Tail feathers (black tips)
    beveled_cube(f"{name}_tail", (0.30, 0.20, 0.10), loc=(-0.55, 0, 1.0 + z_off),
                 parent=base, mat_=M_CRANE_BLACK)
    # Legs (only if standing)
    if not flying:
        for side_idx, side in enumerate((-1, 1)):
            cyl(f"{name}_leg{side_idx}", r=0.03, depth=0.90, segs=10,
                loc=(side*0.05, 0, 0.45), parent=base, mat_=M_CRANE_BLACK)
            # Foot
            for tj in range(3):
                ta = (tj / 3.0) * math.pi - math.pi/2
                beveled_cube(f"{name}_toe{side_idx}_{tj}", (0.04, 0.08, 0.02),
                             loc=(side*0.05 + math.cos(ta)*0.04,
                                  math.sin(ta)*0.04, 0.02), parent=base, mat_=M_CRANE_BLACK)
    return {"root": base, "head_e": head_e, "wings": wings, "flying": flying}

cranes = []
crane_specs = [
    ("crane1", (-7, 10, 0), False, math.radians(45)),
    ("crane2", (-9, 12, 0), False, math.radians(-30)),
    ("crane3", (12, -8, 12), True, math.radians(60)),
    ("crane4", (-15, -5, 14), True, math.radians(-45)),
]
for spec in crane_specs:
    name, loc, flying, fac = spec
    c = make_crane(name, loc, flying=flying, facing=fac)
    cranes.append(c)

# ============================================================
# ⭐ 800 PÉTALES SAKURA qui TOMBENT (PARTICULE THÉMATIQUE OBLIGATOIRE)
# ============================================================
sakura_petals = []
for i in range(800):
    px = random.uniform(-40, 40)
    py = random.uniform(-40, 40)
    pz = random.uniform(2, 25)
    color = M_SAKURA_PINK if i % 3 == 0 else (M_SAKURA_DEEP if i % 3 == 1 else M_SAKURA_WHITE)
    # Petal shape (flat oval)
    petal = smooth_sphere(f"petal{i}", r=random.uniform(0.08, 0.13), segs=10, rings=6,
                          loc=(px, py, pz), mat_=M_PETAL if random.random() < 0.5 else color,
                          scale=(1.5, 0.6, 0.15))
    petal.rotation_euler = (random.uniform(0, math.pi*2),
                            random.uniform(0, math.pi*2),
                            random.uniform(0, math.pi*2))
    petal["_phase"] = random.uniform(0, math.pi*2)
    petal["_base_x"] = px; petal["_base_y"] = py; petal["_base_z"] = pz
    petal["_speed"] = random.uniform(0.5, 1.5)  # slow falling petals (light)
    petal["_drift_x"] = random.uniform(-1.5, 1.5)
    petal["_drift_y"] = random.uniform(-1.5, 1.5)
    sakura_petals.append(petal)

# ============ ANIMATION ============
fps = 30; duration_s = 6; total_frames = fps * duration_s

# Trees sway gently
for t in trees:
    phase = t["_phase"]
    for f in range(1, total_frames + 1, 5):
        t_v = (f - 1) / fps
        t.rotation_euler = (math.sin(t_v * 0.8 + phase) * math.radians(2.5),
                             math.cos(t_v * 0.7 + phase) * math.radians(2.0),
                             0)
        t.keyframe_insert("rotation_euler", frame=f)

# 8 visitors subtle bob + head turn
for v in visitors:
    phase = hash(v["root"].name) % 100 * 0.05
    base_z = v["root"].location.z
    for f in range(1, total_frames + 1, 5):
        t = (f - 1) / fps
        v["root"].location.z = base_z + math.sin(t * 1.0 + phase) * 0.02
        v["root"].keyframe_insert("location", frame=f)
        v["head_e"].rotation_euler = (math.sin(t * 0.6 + phase) * math.radians(3), 0,
                                        math.sin(t * 0.5 + phase) * math.radians(15))
        v["head_e"].keyframe_insert("rotation_euler", frame=f)

# Koi fish swim orbit pond
for k in kois:
    phase = k["phase"]
    rad = k["orbit_rad"]
    base_phase = k["orbit_phase"]
    for f in range(1, total_frames + 1, 4):
        t = (f - 1) / fps
        a = base_phase + t * 0.5
        x = rad * math.cos(a)
        y = rad * math.sin(a)
        k["e"].location = (x, y, -0.05 + math.sin(t * 1.5 + phase) * 0.04)
        k["e"].rotation_euler = (0, 0, a + math.pi/2)
        k["e"].keyframe_insert("location", frame=f)
        k["e"].keyframe_insert("rotation_euler", frame=f)

# Cranes flying flap + orbit, standing subtle
for c in cranes:
    phase = hash(c["root"].name) % 100 * 0.05
    if c["flying"]:
        base_z = c["root"].location.z
        base_x = c["root"].location.x
        base_y = c["root"].location.y
        for f in range(1, total_frames + 1, 3):
            t = (f - 1) / fps
            flap = math.sin(t * 2.0 + phase) * math.radians(30)
            for w_e, side in c["wings"]:
                w_e.rotation_euler = (side * flap, 0, 0)
                w_e.keyframe_insert("rotation_euler", frame=f)
            # Slight bob + drift
            c["root"].location.z = base_z + math.sin(t * 1.5 + phase) * 0.5
            c["root"].location.x = base_x + math.sin(t * 0.4 + phase) * 1.0
            c["root"].keyframe_insert("location", frame=f)
    else:
        for f in range(1, total_frames + 1, 5):
            t = (f - 1) / fps
            c["head_e"].rotation_euler = (math.sin(t * 0.8 + phase) * math.radians(8), 0,
                                            math.sin(t * 0.6 + phase) * math.radians(20))
            c["head_e"].keyframe_insert("rotation_euler", frame=f)

# Lanterns pulse
for l in lanterns:
    phase = l["_phase"]
    for f in range(1, total_frames + 1, 4):
        t = (f - 1) / fps
        s = 1 + math.sin(t * 2.0 + phase) * 0.06
        l.scale = (s, s, s)
        l.keyframe_insert("scale", frame=f)

# Clouds drift
for c_e in clouds:
    phase = c_e["_phase"]
    bx, by = c_e.location.x, c_e.location.y
    for f in range(1, total_frames + 1, 8):
        t = (f - 1) / fps
        c_e.location = (bx + math.sin(t * 0.3 + phase) * 0.6,
                        by + math.cos(t * 0.25 + phase) * 0.6,
                        c_e.location.z)
        c_e.keyframe_insert("location", frame=f)

# Sun halos
for obj in bpy.data.objects:
    if obj.name.startswith("sun_halo"):
        for f in range(1, total_frames + 1, 6):
            t = (f - 1) / fps
            s = 1 + math.sin(t * 0.8) * 0.05
            obj.scale = (s, s, s)
            obj.keyframe_insert("scale", frame=f)

# ============================================================
# ⭐⭐⭐ 800 PÉTALES SAKURA TOMBANT (signature hanami)
# ============================================================
for pt in sakura_petals:
    phase = pt["_phase"]; speed = pt["_speed"]
    bx, by, bz = pt["_base_x"], pt["_base_y"], pt["_base_z"]
    drift_x = pt["_drift_x"]; drift_y = pt["_drift_y"]
    for f in range(1, total_frames + 1, 5):
        t = (f - 1) / fps
        # Slow descent (petals are light)
        z = bz - (speed * t) % 25
        # Spiral drift (signature flutter)
        x = bx + drift_x * math.sin(t * 1.5 + phase) * 0.6
        y = by + drift_y * math.cos(t * 1.3 + phase) * 0.6
        # Tumble rotation
        rx = phase + t * 1.8
        ry = phase + t * 1.5
        rz = phase + t * 2.0
        pt.location = (x, y, max(0.05, z))
        pt.rotation_euler = (rx, ry, rz)
        pt.keyframe_insert("location", frame=f)
        pt.keyframe_insert("rotation_euler", frame=f)

# ============ EXPORT ============
out_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "public", "_pbr_test")
out_dir = os.path.normpath(out_dir)
os.makedirs(out_dir, exist_ok=True)
out_glb = os.path.join(out_dir, "pbr_hanami_proc.glb")

bpy.ops.object.select_all(action='SELECT')
bpy.ops.export_scene.gltf(
    filepath=out_glb, export_format='GLB',
    export_animations=True, export_apply=False, export_yup=True, use_selection=False,
)
size_mb = os.path.getsize(out_glb) / (1024 * 1024)
print(f"[proc_japanese_hanami_sakura] DONE → {out_glb} ({size_mb:.2f} MB)")
print("[proc_japanese_hanami_sakura] ONE ground + Mt Fuji + 12 sakura trees + torii + temple + 6 lanterns + koi pond + 5 koi + 6 lotus + 8 visitors kimono + picnic + tea pavilion + 4 cranes + 800 SAKURA PETALS")
print("⭐ FIXES: 1 ground + 800 sakura petals Z slow descent + spiral drift + tumble (signature hanami mandatory) ⭐")
