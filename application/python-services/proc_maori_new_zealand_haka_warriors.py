"""
proc_maori_new_zealand_haka_warriors.py — 274e procédural AuroraIA (139e qualité)
Maori NZ haka warriors: 6 haka warriors with moko tattoos + piu piu skirts + taiaha spears + 4 carved marae + Mt Cook + NZ flag + 600 koru ferns + 400 kiwi birds
FIXES : 1 ground prairie ferns + signature koru + kiwis
"""
import bpy, bmesh, math, random, os

random.seed(0x70AB274)

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

# Sky NZ dramatic
M_SKY = mat("sky", (0.45, 0.65, 0.85, 1.0), 0.0, 0.7, emission=(0.45,0.65,0.82), emission_strength=1.8)
M_SKY_LOW = mat("sky_l", (0.78, 0.85, 0.92, 1.0), 0.0, 0.7, emission=(0.78,0.85,0.92), emission_strength=1.5)
M_SUN = mat("sun", (1.0, 0.92, 0.65, 1.0), 0.0, 0.1, emission=(1.0,0.92,0.65), emission_strength=16.0)
M_CLOUD = mat("cl", (0.95, 0.95, 0.92, 1.0), 0.0, 0.85, emission=(0.95,0.95,0.92), emission_strength=1.0, alpha=0.85)

# Ground prairie green
M_PRAIRIE = mat("pr", (0.32, 0.62, 0.30, 1.0), 0.0, 0.65, emission=(0.30,0.60,0.30), emission_strength=0.4)
M_PRAIRIE_DARK = mat("prd", (0.22, 0.48, 0.22, 1.0), 0.0, 0.75)
M_DIRT = mat("d", (0.42, 0.30, 0.20, 1.0), 0.0, 0.92)
M_FERN_GREEN = mat("fg", (0.20, 0.55, 0.25, 1.0), 0.0, 0.55, emission=(0.20,0.52,0.25), emission_strength=0.5)
M_FERN_LIGHT = mat("fl", (0.45, 0.78, 0.35, 1.0), 0.0, 0.55, emission=(0.42,0.75,0.35), emission_strength=0.6)
M_FERN_DARK = mat("fd", (0.15, 0.38, 0.18, 1.0), 0.0, 0.75)

# Mountain Mt Cook
M_MOUNTAIN_GRAY = mat("mg", (0.32, 0.32, 0.32, 1.0), 0.0, 0.85)
M_MOUNTAIN_DARK = mat("md", (0.18, 0.18, 0.20, 1.0), 0.0, 0.92)
M_SNOW = mat("sn", (0.95, 0.95, 0.95, 1.0), 0.0, 0.55, emission=(0.92,0.92,0.92), emission_strength=0.5)

# Maori skin and tattoos
M_SKIN_BROWN = mat("sk", (0.55, 0.35, 0.22, 1.0), 0.0, 0.55, emission=(0.52,0.35,0.22), emission_strength=0.3)
M_TATTOO_BLACK = mat("tt", (0.08, 0.06, 0.05, 1.0), 0.0, 0.50, emission=(0.08,0.06,0.05), emission_strength=0.15)
M_HAIR_BLACK = mat("hb", (0.08, 0.06, 0.05, 1.0), 0.0, 0.85)

# Eyes (signature haka wide eyes)
M_EYE_WHITE = mat("ew", (0.95, 0.92, 0.85, 1.0), 0.0, 0.20, emission=(0.92,0.90,0.85), emission_strength=1.5)
M_EYE = mat("ed", (0.05, 0.04, 0.04, 1.0), 0.0, 0.20)
M_TONGUE_RED = mat("tr", (0.85, 0.20, 0.20, 1.0), 0.0, 0.45, emission=(0.82,0.20,0.20), emission_strength=0.8)

# Piu piu skirt (signature flax)
M_FLAX_BROWN = mat("flb", (0.42, 0.30, 0.18, 1.0), 0.0, 0.75)
M_FLAX_DARK = mat("fld", (0.25, 0.18, 0.10, 1.0), 0.0, 0.85)
M_FLAX_LIGHT = mat("fll", (0.65, 0.45, 0.22, 1.0), 0.0, 0.75)

# Taiaha (spear)
M_WOOD_DARK = mat("wd", (0.32, 0.20, 0.10, 1.0), 0.0, 0.75)
M_WOOD_LIGHT = mat("wl", (0.55, 0.38, 0.22, 1.0), 0.0, 0.65, emission=(0.52,0.38,0.22), emission_strength=0.3)

# Marae (meeting house) - signature carved red
M_MARAE_RED = mat("mr", (0.55, 0.22, 0.18, 1.0), 0.0, 0.65, emission=(0.52,0.20,0.18), emission_strength=0.5)
M_MARAE_DARK = mat("mrd", (0.32, 0.15, 0.10, 1.0), 0.0, 0.85)
M_MARAE_CARVE = mat("mrc", (0.85, 0.65, 0.35, 1.0), 0.0, 0.55, emission=(0.82,0.62,0.35), emission_strength=0.5)
M_PAUA = mat("pa", (0.30, 0.62, 0.85, 1.0), 0.8, 0.10, emission=(0.30,0.62,0.85), emission_strength=2.5)
M_PAUA_GREEN = mat("pg", (0.20, 0.85, 0.55, 1.0), 0.8, 0.10, emission=(0.20,0.85,0.55), emission_strength=2.0)
M_BONE = mat("bn", (0.92, 0.88, 0.78, 1.0), 0.0, 0.65, emission=(0.88,0.85,0.75), emission_strength=0.4)

# NZ flag (signature Union + Southern Cross)
M_FLAG_BLUE = mat("fb", (0.10, 0.20, 0.55, 1.0), 0.0, 0.45, emission=(0.10,0.20,0.52), emission_strength=1.0)
M_FLAG_RED = mat("fr2", (0.85, 0.18, 0.18, 1.0), 0.0, 0.45, emission=(0.82,0.18,0.18), emission_strength=1.0)
M_FLAG_WHITE = mat("fw", (0.95, 0.95, 0.92, 1.0), 0.0, 0.45, emission=(0.92,0.92,0.90), emission_strength=0.8)
M_STAR_RED = mat("sr", (0.92, 0.20, 0.22, 1.0), 0.0, 0.30, emission=(0.88,0.20,0.22), emission_strength=2.0)

# Kiwi bird (signature brown round)
M_KIWI_BROWN = mat("kb", (0.55, 0.32, 0.18, 1.0), 0.0, 0.85, emission=(0.52,0.30,0.18), emission_strength=0.3)
M_KIWI_BEAK = mat("kbk", (0.92, 0.78, 0.55, 1.0), 0.0, 0.55, emission=(0.88,0.75,0.55), emission_strength=0.4)

# Koru fern particles
M_KORU_BRIGHT = mat("kbr", (0.30, 0.85, 0.30, 1.0), 0.0, 0.40, emission=(0.30,0.82,0.30), emission_strength=2.0)
M_KORU_DEEP = mat("kdp", (0.15, 0.55, 0.20, 1.0), 0.0, 0.50, emission=(0.15,0.52,0.20), emission_strength=1.5)
M_KORU_LIME = mat("klm", (0.55, 0.95, 0.35, 1.0), 0.0, 0.40, emission=(0.52,0.92,0.35), emission_strength=2.0)
KORU_COLORS = [M_KORU_BRIGHT, M_KORU_DEEP, M_KORU_LIME]

# ============ SKY ============
sky = smooth_sphere("sky", r=320, segs=32, rings=20, loc=(0,0,0), mat_=M_SKY)
sky.scale = (1,1,0.6)
sky_l = smooth_sphere("sky_l", r=280, segs=28, rings=16, loc=(0,0,5), mat_=M_SKY_LOW)
sky_l.scale = (1,1,0.3)
# Sun
sun = smooth_sphere("sun", r=8, segs=24, rings=18, loc=(-40, 100, 30), mat_=M_SUN)
for sh in range(3):
    smooth_sphere(f"sun_h{sh}", r=8 + sh*1, segs=24, rings=18, loc=(-40, 100, 30), mat_=M_SUN)
# Clouds
for ci in range(20):
    cx = random.uniform(-150, 150); cy = random.uniform(-150, 150); cz = random.uniform(45, 70)
    cloud_e = empty(f"cl{ci}_e", (cx, cy, cz))
    for cp in range(5):
        cpa = random.uniform(0, math.pi*2); cpr = random.uniform(0, 4)
        smooth_sphere(f"cl{ci}_p{cp}", r=random.uniform(2, 4), segs=14, rings=10,
                      loc=(math.cos(cpa)*cpr, math.sin(cpa)*cpr, random.uniform(-1, 1)),
                      parent=cloud_e, mat_=M_CLOUD, scale=(1.5, 1.5, 0.5))

# ============ ONE clean prairie ground ============
ground = beveled_cube("ground", (300, 300, 0.5), bevel_offset=0.10, loc=(0, 0, -0.25), mat_=M_PRAIRIE)
# Hill bumps (organic 3D)
for hi in range(180):
    a = random.uniform(0, math.pi*2); rad = random.uniform(3, 130)
    smooth_sphere(f"hl{hi}", r=random.uniform(1.5, 3.0), segs=12, rings=8,
                  loc=(rad*math.cos(a), rad*math.sin(a), 0.15),
                  mat_=M_PRAIRIE_DARK if hi % 3 == 0 else M_PRAIRIE, scale=(1.5, 1.4, 0.22))
# Dirt patches
for di in range(30):
    smooth_sphere(f"di{di}", r=random.uniform(0.5, 1.0), segs=10, rings=6,
                  loc=(random.uniform(-100, 100), random.uniform(-100, 100), 0.10),
                  mat_=M_DIRT, scale=(1.4, 1.3, 0.18))
# Tussock grass clumps
for gi in range(100):
    a = random.uniform(0, math.pi*2); rad = random.uniform(8, 110)
    smooth_sphere(f"tg{gi}", r=random.uniform(0.3, 0.6), segs=10, rings=6,
                  loc=(rad*math.cos(a), rad*math.sin(a), 0.30),
                  mat_=M_FERN_GREEN if gi % 2 else M_FERN_DARK, scale=(1.2, 1.1, 0.85))

# ============ MT COOK snowy mountain backdrop (signature) ============
def make_mt_cook(name, loc, height, base_radius):
    base = empty(name, loc)
    n_layers = int(height / 4)
    for li in range(n_layers):
        lz = li * 4
        lr1 = base_radius * (1 - li / n_layers * 0.85)
        lr2 = base_radius * (1 - (li+1) / n_layers * 0.85)
        smooth_cone(f"{name}_l{li}", r1=lr1, r2=lr2, depth=4.5, segs=18,
                    loc=(0, 0, lz + 2.25), parent=base,
                    mat_=M_MOUNTAIN_DARK if li < n_layers//2 else M_MOUNTAIN_GRAY)
    # Snow cap on top half
    snow_e = empty(f"{name}_se", (0, 0, height * 0.55), parent=base)
    for si in range(5):
        sz = si * 3
        sr = base_radius * (0.5 - si / 5 * 0.4)
        smooth_cone(f"{name}_s{si}", r1=sr + 0.3, r2=sr - 0.1, depth=3, segs=16,
                    loc=(0, 0, sz), parent=snow_e, mat_=M_SNOW)
    smooth_cone(f"{name}_pk", r1=0.4, r2=0.04, depth=2, segs=12,
                loc=(0, 0, height - 0.5), parent=base, mat_=M_SNOW)
    return base

# Mt Cook + secondary peaks
make_mt_cook("mtcook", (0, 80, 0), 40, 12)
make_mt_cook("mt2", (-35, 75, 0), 32, 10)
make_mt_cook("mt3", (40, 70, 0), 28, 9)

# ============ 4 CARVED MARAE (signature meeting houses) ============
def make_marae(name, loc, scale=1.0, facing=0):
    base = empty(name, loc)
    base.rotation_euler = (0, 0, facing)
    # Main rectangular hall
    beveled_cube(f"{name}_h", (6, 10, 3), bevel_offset=0.10, loc=(0, 0, 1.7),
                 parent=base, mat_=M_MARAE_RED)
    # Steep angled roof (signature)
    roof_e = empty(f"{name}_re", (0, 0, 3.7), parent=base)
    # Triangular gable
    for gri in range(8):
        grx = -3 + gri*0.85
        gh = 2 - abs(gri - 3.5) * 0.4
        beveled_cube(f"{name}_gr{gri}", (0.85, 10.2, gh*0.05), bevel_offset=0.02,
                     loc=(grx, 0, gh/2), parent=roof_e, mat_=M_MARAE_DARK)
    # Two roof slopes
    for side_r in (-1, 1):
        slope_e = empty(f"{name}_sl{side_r}", (side_r*1.5, 0, 1.0), parent=roof_e)
        slope_e.rotation_euler = (0, side_r*math.radians(-30), 0)
        beveled_cube(f"{name}_sp{side_r}", (4, 10.5, 0.15), bevel_offset=0.04,
                     loc=(0, 0, 0), parent=slope_e, mat_=M_MARAE_DARK)
    # Bargeboards (signature carved gable boards)
    for side_b in (-1, 1):
        bb_e = empty(f"{name}_bb{side_b}", (side_b*3, -5, 2), parent=base)
        bb_e.rotation_euler = (math.radians(45), 0, side_b * math.radians(20))
        # Carved board
        beveled_cube(f"{name}_bbp{side_b}", (0.30, 0.20, 4), bevel_offset=0.05,
                     loc=(0, 0, 0), parent=bb_e, mat_=M_MARAE_CARVE)
        # Spiral koru carvings
        for ki in range(5):
            smooth_sphere(f"{name}_bbk{side_b}_{ki}", r=0.12,
                          loc=(0, 0, -1.8 + ki*0.9), parent=bb_e, mat_=M_MARAE_RED)
    # Front door
    beveled_cube(f"{name}_d", (1.5, 0.05, 2.5), bevel_offset=0.05,
                 loc=(0, -5.05, 1.25), parent=base, mat_=M_MARAE_DARK)
    # Carved tekoteko figure on top (signature ancestor)
    tek_e = empty(f"{name}_tk", (0, -5, 4.5), parent=base)
    # Body
    beveled_cube(f"{name}_tk_b", (0.40, 0.30, 1.0), bevel_offset=0.05,
                 loc=(0, 0, 0.5), parent=tek_e, mat_=M_MARAE_CARVE)
    # Head
    smooth_sphere(f"{name}_tk_h", r=0.30, segs=14, rings=10, loc=(0, 0, 1.2),
                  parent=tek_e, mat_=M_MARAE_CARVE, scale=(1, 1, 1.1))
    # Paua eyes signature (shimmering blue/green shell)
    for side_e in (-1, 1):
        smooth_sphere(f"{name}_tk_e{side_e}", r=0.07,
                      loc=(side_e*0.12, -0.22, 1.25), parent=tek_e, mat_=M_PAUA)
    # Tongue out (signature haka pose)
    beveled_cube(f"{name}_tk_to", (0.10, 0.04, 0.20), bevel_offset=0.02,
                 loc=(0, -0.25, 1.05), parent=tek_e, mat_=M_TONGUE_RED).rotation_euler = (math.radians(20), 0, 0)
    # Arms
    for side_a in (-1, 1):
        cyl(f"{name}_tk_a{side_a}", r=0.06, depth=0.40, segs=8,
            loc=(side_a*0.25, 0, 0.70), parent=tek_e, mat_=M_MARAE_CARVE).rotation_euler = (0, math.radians(60*side_a), 0)
    # Side wall carvings
    for side_w in (-1, 1):
        for ci_w in range(4):
            cyl(f"{name}_cw{side_w}_{ci_w}", r=0.15, depth=2.5, segs=10,
                loc=(side_w*3.1, -3 + ci_w*2, 1.5), parent=base, mat_=M_MARAE_CARVE)
            # Carved face
            smooth_sphere(f"{name}_cf{side_w}_{ci_w}", r=0.20, segs=12, rings=8,
                          loc=(side_w*3.15, -3 + ci_w*2, 1.8), parent=base, mat_=M_MARAE_RED)
            # Paua eye
            smooth_sphere(f"{name}_cpa{side_w}_{ci_w}", r=0.05,
                          loc=(side_w*3.30, -3 + ci_w*2, 1.85), parent=base, mat_=M_PAUA_GREEN)
    return base

for i, (mx, my, mf) in enumerate([(-25, -25, math.radians(0)), (25, -25, math.radians(0)),
                                    (-25, 25, math.radians(180)), (25, 25, math.radians(180))]):
    make_marae(f"mr{i}", (mx, my, 0), facing=mf)

# ============ 6 HAKA WARRIORS (signature) ============
def make_haka_warrior(name, loc, scale=1.0, facing=0):
    base = empty(name, loc)
    base.rotation_euler = (0, 0, facing)
    # Bare muscular torso
    smooth_cone(f"{name}_to", r1=0.36, r2=0.40, depth=0.85, segs=14, loc=(0, 0, 1.30),
                parent=base, mat_=M_SKIN_BROWN)
    # MOKO TATTOOS on chest/back (signature)
    for ti in range(8):
        ta = (ti / 8.0) * math.pi * 2
        smooth_sphere(f"{name}_tt{ti}", r=0.04,
                      loc=(math.cos(ta)*0.40, math.sin(ta)*0.05, 1.30),
                      parent=base, mat_=M_TATTOO_BLACK)
    # Spiral tattoos on shoulders
    for side_s in (-1, 1):
        for spi in range(6):
            spa = (spi / 6.0) * math.pi * 2
            smooth_sphere(f"{name}_sp{side_s}_{spi}", r=0.03,
                          loc=(side_s*0.36 + math.cos(spa)*0.05,
                               math.sin(spa)*0.05, 1.55),
                          parent=base, mat_=M_TATTOO_BLACK)
    # PIU PIU SKIRT (signature flax bundles)
    skirt_e = empty(f"{name}_sk", (0, 0, 0.95), parent=base)
    for gs_i in range(50):
        ga = (gs_i / 50.0) * math.pi * 2
        gx_s = math.cos(ga) * 0.36
        gy_s = math.sin(ga) * 0.36
        skirt_col = M_FLAX_BROWN if gs_i % 3 == 0 else (M_FLAX_DARK if gs_i % 3 == 1 else M_FLAX_LIGHT)
        beveled_cube(f"{name}_g{gs_i}", (0.03, 0.03, 0.55), bevel_offset=0.005,
                     loc=(gx_s, gy_s, -0.25), parent=skirt_e, mat_=skirt_col).rotation_euler = (math.cos(ga)*0.10, math.sin(ga)*0.10, ga)
    skirt_e["_phase"] = random.uniform(0, math.pi*2)
    # Muscular legs
    for side_l in (-1, 1):
        cyl(f"{name}_l{side_l}", r=0.13, depth=0.75, segs=10,
            loc=(side_l*0.15, 0, 0.38), parent=base, mat_=M_SKIN_BROWN)
        # Leg tattoos (signature)
        for li in range(3):
            cyl(f"{name}_lt{side_l}_{li}", r=0.135, depth=0.05, segs=10,
                loc=(side_l*0.15, 0, 0.20 + li*0.15), parent=base, mat_=M_TATTOO_BLACK)
        # Bare feet
        beveled_cube(f"{name}_f{side_l}", (0.13, 0.26, 0.06), bevel_offset=0.02,
                     loc=(side_l*0.15, 0.04, 0.03), parent=base, mat_=M_SKIN_BROWN)
    # Arms (haka pose - hands extended)
    for side_a in (-1, 1):
        sh = empty(f"{name}_a{side_a}", (side_a*0.40, 0, 1.65), parent=base)
        sh.rotation_euler = (math.radians(-90), 0, math.radians(side_a*60))
        cyl(f"{name}_ua{side_a}", r=0.10, depth=0.42, segs=10, loc=(0, 0, -0.21),
            parent=sh, mat_=M_SKIN_BROWN)
        # Arm tattoos
        cyl(f"{name}_uat{side_a}", r=0.105, depth=0.06, segs=10, loc=(0, 0, -0.30),
            parent=sh, mat_=M_TATTOO_BLACK)
        cyl(f"{name}_fa{side_a}", r=0.09, depth=0.40, segs=10, loc=(0, 0, -0.62),
            parent=sh, mat_=M_SKIN_BROWN)
        # Hand
        smooth_sphere(f"{name}_hd{side_a}", r=0.10, segs=12, rings=8, loc=(0, 0, -0.85),
                      parent=sh, mat_=M_SKIN_BROWN)
        sh["_phase"] = random.uniform(0, math.pi*2)
    # Head
    head_w_e = empty(f"{name}_he", (0, 0, 2.0), parent=base)
    smooth_sphere(f"{name}_h", r=0.20, segs=18, rings=14, loc=(0, 0, 0),
                  parent=head_w_e, mat_=M_SKIN_BROWN)
    # MOKO FACIAL TATTOOS (signature spiral patterns)
    # Forehead
    beveled_cube(f"{name}_mf", (0.30, 0.05, 0.04), bevel_offset=0.005,
                 loc=(0, -0.17, 0.10), parent=head_w_e, mat_=M_TATTOO_BLACK)
    # Cheek spirals (signature)
    for side_m in (-1, 1):
        for ci_m in range(5):
            cia = (ci_m / 5.0) * math.pi * 1.5
            smooth_sphere(f"{name}_mc{side_m}_{ci_m}", r=0.02,
                          loc=(side_m*(0.12 + math.cos(cia)*0.04),
                               -0.18,
                               math.sin(cia)*0.04 - 0.02),
                          parent=head_w_e, mat_=M_TATTOO_BLACK)
    # Chin tattoo
    beveled_cube(f"{name}_mn", (0.10, 0.04, 0.10), bevel_offset=0.005,
                 loc=(0, -0.17, -0.12), parent=head_w_e, mat_=M_TATTOO_BLACK)
    # WIDE EYES (signature haka pukana)
    for side_e in (-1, 1):
        smooth_sphere(f"{name}_ew{side_e}", r=0.045,
                      loc=(side_e*0.08, -0.17, 0.05),
                      parent=head_w_e, mat_=M_EYE_WHITE)
        smooth_sphere(f"{name}_ep{side_e}", r=0.020,
                      loc=(side_e*0.08, -0.20, 0.05),
                      parent=head_w_e, mat_=M_EYE)
    # TONGUE OUT signature (haka)
    tongue_e = empty(f"{name}_to_e", (0, -0.20, -0.06), parent=head_w_e)
    tongue_e.rotation_euler = (math.radians(30), 0, 0)
    beveled_cube(f"{name}_to_p", (0.08, 0.04, 0.15), bevel_offset=0.02,
                 loc=(0, 0, 0), parent=tongue_e, mat_=M_TONGUE_RED)
    tongue_e["_phase"] = random.uniform(0, math.pi*2)
    # Hair top knot (signature)
    smooth_sphere(f"{name}_ht", r=0.10, segs=14, rings=10, loc=(0, 0, 0.22),
                  parent=head_w_e, mat_=M_HAIR_BLACK)
    # Feathers in hair (signature)
    for fe in range(3):
        fa = (fe / 3.0 - 0.5) * math.radians(45)
        feather_e = empty(f"{name}_fe{fe}", (0, 0.05, 0.28), parent=head_w_e)
        feather_e.rotation_euler = (0, 0, fa)
        beveled_cube(f"{name}_fep{fe}", (0.04, 0.04, 0.25), bevel_offset=0.005,
                     loc=(0, 0, 0.15), parent=feather_e, mat_=M_BONE)
    # TAIAHA SPEAR (signature long carved war club)
    taiaha_e = empty(f"{name}_ti", (0.40, -0.40, 0.40), parent=base)
    taiaha_e.rotation_euler = (math.radians(-30), 0, math.radians(-20))
    # Main shaft
    cyl(f"{name}_ti_s", r=0.04, depth=2.0, segs=10, loc=(0, 0, 0),
        parent=taiaha_e, mat_=M_WOOD_DARK)
    # Carved head end (signature face)
    head_t_e = empty(f"{name}_ti_he", (0, 0, 1.10), parent=taiaha_e)
    smooth_sphere(f"{name}_ti_h", r=0.10, segs=12, rings=10, loc=(0, 0, 0),
                  parent=head_t_e, mat_=M_WOOD_LIGHT)
    # Tongue (signature)
    beveled_cube(f"{name}_ti_to", (0.06, 0.04, 0.15), bevel_offset=0.01,
                 loc=(0, -0.08, -0.05), parent=head_t_e, mat_=M_WOOD_LIGHT)
    # Paua eyes
    for side_t in (-1, 1):
        smooth_sphere(f"{name}_ti_e{side_t}", r=0.025,
                      loc=(side_t*0.05, -0.08, 0.03),
                      parent=head_t_e, mat_=M_PAUA)
    # Blade end (signature flat)
    beveled_cube(f"{name}_ti_bl", (0.16, 0.04, 0.40), bevel_offset=0.02,
                 loc=(0, 0, -1.20), parent=taiaha_e, mat_=M_WOOD_DARK)
    base["_phase"] = random.uniform(0, math.pi*2)
    return {"root": base, "skirt": skirt_e, "tongue": tongue_e, "he": head_w_e}

warriors = []
warrior_pos = [
    (-15, 0, math.radians(0)),
    (-9, 0, math.radians(0)),
    (-3, 0, math.radians(0)),
    (3, 0, math.radians(0)),
    (9, 0, math.radians(0)),
    (15, 0, math.radians(0)),
]
for i, (wx, wy, fac) in enumerate(warrior_pos):
    w = make_haka_warrior(f"hk{i}", (wx, wy, 0), facing=fac)
    warriors.append(w)

# ============ NZ FLAG (signature Union Jack + Southern Cross) ============
flag_e = empty("flag", (-55, -20, 0))
cyl("fl_p", r=0.10, depth=12, segs=10, loc=(0, 0, 6), parent=flag_e, mat_=M_MARAE_DARK)
# Blue field
beveled_cube("fl_b", (4, 0.05, 2.5), bevel_offset=0.06, loc=(2, 0, 10.5),
             parent=flag_e, mat_=M_FLAG_BLUE)
# UNION JACK in top-left quadrant (signature)
uj_e = empty("fl_uj", (1.0, -0.05, 11.10), parent=flag_e)
# White cross horizontal/vertical
beveled_cube("fl_uj_h", (2, 0.06, 0.20), bevel_offset=0.04, loc=(0, 0, 0),
             parent=uj_e, mat_=M_FLAG_WHITE)
beveled_cube("fl_uj_v", (0.20, 0.06, 0.80), bevel_offset=0.04, loc=(0, 0, 0),
             parent=uj_e, mat_=M_FLAG_WHITE)
# Red cross
beveled_cube("fl_uj_rh", (2.02, 0.07, 0.10), bevel_offset=0.02, loc=(0, -0.005, 0),
             parent=uj_e, mat_=M_FLAG_RED)
beveled_cube("fl_uj_rv", (0.10, 0.07, 0.82), bevel_offset=0.02, loc=(0, -0.005, 0),
             parent=uj_e, mat_=M_FLAG_RED)
# Diagonals X cross (signature)
for diag in (0, 1):
    diag_e = empty(f"fl_uj_d{diag}", (0, -0.04, 0), parent=uj_e)
    diag_e.rotation_euler = (0, math.radians(30 if diag == 0 else -30), 0)
    beveled_cube(f"fl_uj_dp{diag}", (2.2, 0.06, 0.08), bevel_offset=0.02,
                 loc=(0, 0, 0), parent=diag_e, mat_=M_FLAG_WHITE)
# SOUTHERN CROSS (signature - 4 red stars)
star_positions = [(2.6, 11.20, 0.15), (3.0, 10.50, 0.18), (3.3, 9.90, 0.13), (2.6, 9.85, 0.15)]
for si, (sx_st, sz_st, sr_st) in enumerate(star_positions):
    star_e = empty(f"fl_st{si}", (sx_st, -0.06, sz_st), parent=flag_e)
    for sp in range(5):
        spa = (sp / 5.0) * math.pi * 2 + math.pi/2
        beveled_cube(f"fl_st{si}_p{sp}", (0.03, 0.06, sr_st), bevel_offset=0.005,
                     loc=(math.cos(spa)*sr_st*0.4, 0, math.sin(spa)*sr_st*0.4),
                     parent=star_e, mat_=M_STAR_RED).rotation_euler = (spa - math.pi/2, 0, 0)
    smooth_sphere(f"fl_st{si}_c", r=sr_st*0.3, loc=(0, 0, 0),
                  parent=star_e, mat_=M_STAR_RED)
flag_e["_phase"] = 0

# ============================================================
# 600 KORU FERNS + 400 KIWI BIRDS (PARTICULES SIGNATURES)
# ============================================================
korus = []
for i in range(600):
    px = random.uniform(-100, 100)
    py = random.uniform(-100, 100)
    pz = random.uniform(2, 22)
    koru_e = empty(f"ko{i}", (px, py, pz))
    koru_col = random.choice(KORU_COLORS)
    # SPIRAL KORU (signature curling fern frond)
    n_spiral = 8
    for si in range(n_spiral):
        angle = (si / n_spiral) * math.pi * 1.5
        radius_s = 0.05 + si * 0.04
        sx_k = math.cos(angle) * radius_s
        sz_k = math.sin(angle) * radius_s
        smooth_sphere(f"ko{i}_s{si}", r=0.025 + si*0.005,
                      loc=(sx_k, 0, sz_k), parent=koru_e, mat_=koru_col)
    # Stem
    cyl(f"ko{i}_st", r=0.01, depth=0.25, segs=6, loc=(0, 0, -0.15),
        parent=koru_e, mat_=koru_col)
    koru_e["_phase"] = random.uniform(0, math.pi*2)
    koru_e["_base_x"] = px; koru_e["_base_z"] = pz
    koru_e["_drift"] = random.uniform(0.2, 0.5)
    koru_e["_swing"] = random.uniform(0.8, 2.0)
    koru_e["_spin"] = random.uniform(0.5, 1.5)
    korus.append(koru_e)

# 400 kiwi birds (mostly on ground, some hopping)
kiwis = []
for i in range(400):
    px = random.uniform(-110, 110)
    py = random.uniform(-110, 110)
    pz = 0.5
    k_e = empty(f"kw{i}", (px, py, pz))
    # Round body (signature kiwi shape)
    smooth_sphere(f"kw{i}_bo", r=0.25, segs=14, rings=10, loc=(0, 0, 0),
                  parent=k_e, mat_=M_KIWI_BROWN, scale=(1.2, 0.95, 0.85))
    # Small head
    smooth_sphere(f"kw{i}_h", r=0.12, segs=10, rings=8, loc=(0.25, 0, 0.10),
                  parent=k_e, mat_=M_KIWI_BROWN)
    # LONG BEAK (signature)
    cyl(f"kw{i}_bk", r=0.020, depth=0.25, segs=8, loc=(0.42, 0, 0.05),
        parent=k_e, mat_=M_KIWI_BEAK).rotation_euler = (0, math.radians(95), 0)
    # Tiny eyes
    for side in (-1, 1):
        smooth_sphere(f"kw{i}_ey{side}", r=0.015, loc=(0.28, side*0.06, 0.13),
                      parent=k_e, mat_=M_EYE)
    # Legs
    for side in (-1, 1):
        cyl(f"kw{i}_l{side}", r=0.025, depth=0.18, segs=6,
            loc=(0, side*0.06, -0.20), parent=k_e, mat_=M_KIWI_BEAK)
    # Feathers texture (bumps)
    for fi in range(6):
        fa = random.uniform(0, math.pi*2)
        smooth_sphere(f"kw{i}_fe{fi}", r=0.05, segs=8, rings=6,
                      loc=(math.cos(fa)*0.20, math.sin(fa)*0.20, random.uniform(-0.10, 0.10)),
                      parent=k_e, mat_=M_KIWI_BROWN)
    k_e["_phase"] = random.uniform(0, math.pi*2)
    k_e["_base_x"] = px; k_e["_base_y"] = py
    k_e["_speed"] = random.uniform(0.3, 0.7)
    kiwis.append(k_e)

# ============ ANIMATION ============
fps = 30; duration_s = 6; total_frames = fps * duration_s

# Haka warriors performing haka (synchronized aggressive stomp + arm slap)
for w in warriors:
    phase = w["root"]["_phase"]
    for f in range(1, total_frames + 1, 2):
        t = (f - 1) / fps
        # Powerful stomp (synchronized rhythm)
        stomp_z = abs(math.sin(t * 4.0)) * 0.20
        w["root"].location.z = stomp_z
        w["root"].rotation_euler = (math.sin(t * 4.0) * math.radians(8), 0,
                                     w["root"].rotation_euler.z + math.sin(t * 2.0 + phase) * math.radians(5))
        w["root"].keyframe_insert("location", frame=f)
        w["root"].keyframe_insert("rotation_euler", frame=f)
        # Skirt sway
        w["skirt"].rotation_euler = (math.sin(t * 4.0) * math.radians(12), 0,
                                      math.cos(t * 3.0) * math.radians(15))
        w["skirt"].keyframe_insert("rotation_euler", frame=f)
        # Tongue stick out (puke pose)
        tongue_scale = 1 + math.sin(t * 5.0 + phase) * 0.4
        w["tongue"].scale = (1, 1, tongue_scale)
        w["tongue"].keyframe_insert("scale", frame=f)
        # Head shake
        w["he"].rotation_euler = (math.sin(t * 4.0 + phase) * math.radians(15),
                                   math.cos(t * 4.0 + phase) * math.radians(8),
                                   math.sin(t * 3.0 + phase) * math.radians(10))
        w["he"].keyframe_insert("rotation_euler", frame=f)

# Flag wave
for f in range(1, total_frames + 1, 5):
    t = (f - 1) / fps
    flag_e.rotation_euler = (0, 0, math.sin(t * 1.5) * math.radians(10))
    flag_e.keyframe_insert("rotation_euler", frame=f)

# 600 koru spirals float + rotate
for k in korus:
    phase = k["_phase"]; drift = k["_drift"]; swing = k["_swing"]; spin = k["_spin"]
    bx, bz = k["_base_x"], k["_base_z"]
    for f in range(1, total_frames + 1, 4):
        t = (f - 1) / fps
        x = bx + math.sin(t * swing + phase) * 0.8
        z = bz + math.cos(t * swing * 0.8 + phase) * 0.5 - (t * drift) % 8
        k.location = (x, k.location.y, z)
        k.rotation_euler = (t * spin + phase, math.sin(t * 1.5 + phase) * math.radians(20), t * spin*0.6 + phase)
        k.keyframe_insert("location", frame=f)
        k.keyframe_insert("rotation_euler", frame=f)

# 400 kiwis hop and waddle
for kw in kiwis:
    phase = kw["_phase"]; speed = kw["_speed"]
    bx, by = kw["_base_x"], kw["_base_y"]
    for f in range(1, total_frames + 1, 4):
        t = (f - 1) / fps
        # Waddle motion
        x = bx + math.sin(t * speed + phase) * 2
        y = by + math.cos(t * speed * 0.7 + phase) * 2
        z = 0.5 + abs(math.sin(t * 3.0 + phase)) * 0.10
        kw.location = (x, y, z)
        kw.rotation_euler = (math.sin(t * 3.0 + phase) * math.radians(5), 0,
                              math.atan2(math.cos(t * speed + phase),
                                          -math.sin(t * speed + phase)))
        kw.keyframe_insert("location", frame=f)
        kw.keyframe_insert("rotation_euler", frame=f)

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
out_glb = os.path.join(out_dir, "pbr_maori_proc.glb")

bpy.ops.object.select_all(action='SELECT')
bpy.ops.export_scene.gltf(
    filepath=out_glb, export_format='GLB',
    export_animations=True, export_apply=False, export_yup=True, use_selection=False,
)
size_mb = os.path.getsize(out_glb) / (1024 * 1024)
print(f"[proc_maori_new_zealand_haka_warriors] DONE → {out_glb} ({size_mb:.2f} MB)")
print("Maori NZ haka: 6 warriors performing haka with moko facial tattoos (forehead/cheek spirals/chin) + wide pukana eyes + tongue out + chest/shoulder/arm/leg tattoos + 50-strand piu piu flax skirts + top knots with bone feathers + taiaha spears (carved head with paua eyes + flat blade) + 4 marae meeting houses with steep gable roofs + bargeboards + tekoteko ancestor figures with paua eyes + tongue + side wall carvings with paua + Mt Cook snowy + 2 secondary peaks + NZ flag with Union Jack + 4-star Southern Cross + 600 koru spirals + 400 kiwi birds")
print("🌿 FIXES: 1 prairie green ground + 600 koru spiral ferns + 400 kiwi birds waddling signature 🌿")
