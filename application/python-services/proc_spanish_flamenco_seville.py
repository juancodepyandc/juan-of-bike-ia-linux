"""
proc_spanish_flamenco_seville.py — 262e procédural AuroraIA (127e qualité)
Seville Spain flamenco: Giralda tower + Cathedral + 6 flamenco dancers + 4 guitarists + tablao stage + 4 toreadors traje de luces + bull + 8 spectators + 600 red roses + 400 castanets
FIXES : 1 ground + 600 roses + 400 castanets (signature)
"""
import bpy, bmesh, math, random, os

random.seed(0x70AB262)

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

# Sunset sky orange
M_SKY = mat("sky", (0.95, 0.55, 0.25, 1.0), 0.0, 0.7, emission=(0.95,0.55,0.25), emission_strength=2.2)
M_SKY_DEEP = mat("sky_d", (0.78, 0.32, 0.20, 1.0), 0.0, 0.7, emission=(0.78,0.32,0.20), emission_strength=2.0)
M_SUN = mat("sun", (1.0, 0.78, 0.30, 1.0), 0.0, 0.1, emission=(1.0,0.78,0.30), emission_strength=18.0)
M_CLOUD_RED = mat("cloud_r", (0.95, 0.62, 0.45, 1.0), 0.0, 0.7, emission=(0.92,0.60,0.45), emission_strength=1.6)

# Andalusian ground (signature ochre stone)
M_STONE_OCHRE = mat("stone_o", (0.85, 0.62, 0.32, 1.0), 0.0, 0.85, emission=(0.78,0.58,0.32), emission_strength=0.5)
M_STONE_DARK = mat("stone_d", (0.55, 0.40, 0.22, 1.0), 0.0, 0.85)
M_PAVE_RED = mat("pave_r", (0.65, 0.30, 0.20, 1.0), 0.0, 0.85)
M_PAVE_WHITE = mat("pave_w", (0.92, 0.85, 0.72, 1.0), 0.0, 0.75, emission=(0.85,0.80,0.72), emission_strength=0.5)

# GIRALDA TOWER (signature ochre Moorish + Renaissance)
M_GIRALDA = mat("g", (0.92, 0.65, 0.32, 1.0), 0.0, 0.75, emission=(0.85,0.62,0.32), emission_strength=0.6)
M_GIRALDA_DEEP = mat("g_d", (0.72, 0.45, 0.22, 1.0), 0.0, 0.85)
M_GIRALDA_PATTERN = mat("g_p", (0.62, 0.32, 0.18, 1.0), 0.0, 0.85, emission=(0.58,0.30,0.18), emission_strength=0.4)

# Cathedral
M_CATH_STONE = mat("cs", (0.78, 0.65, 0.45, 1.0), 0.0, 0.85, emission=(0.72,0.62,0.45), emission_strength=0.5)
M_CATH_GOLD = mat("cg", (1.0, 0.85, 0.30, 1.0), 0.95, 0.15, emission=(0.95,0.80,0.30), emission_strength=2.5)
M_CATH_DARK = mat("cd", (0.42, 0.35, 0.25, 1.0), 0.0, 0.85)

# Flamenco dress (signature red polka dots + ruffles)
M_DRESS_RED = mat("dr_r", (0.85, 0.15, 0.18, 1.0), 0.0, 0.55, emission=(0.80,0.15,0.18), emission_strength=0.7)
M_DRESS_DARK_RED = mat("dr_dr", (0.62, 0.10, 0.12, 1.0), 0.0, 0.65, emission=(0.58,0.10,0.12), emission_strength=0.5)
M_DRESS_BLACK = mat("dr_bk", (0.10, 0.08, 0.08, 1.0), 0.0, 0.65)
M_POLKA_WHITE = mat("pk_w", (0.95, 0.92, 0.85, 1.0), 0.0, 0.50, emission=(0.92,0.88,0.85), emission_strength=0.7)

# Skin
M_SKIN_TAN = mat("skin", (0.85, 0.62, 0.45, 1.0), 0.0, 0.55, emission=(0.80,0.60,0.45), emission_strength=0.4)
M_SKIN_DARKER = mat("skin_d", (0.65, 0.42, 0.25, 1.0), 0.0, 0.55, emission=(0.62,0.42,0.25), emission_strength=0.4)
SKIN_SP = [M_SKIN_TAN, M_SKIN_DARKER]

# Hair black
M_HAIR_BLACK_SP = mat("h_bk", (0.08, 0.05, 0.04, 1.0), 0.0, 0.55)
M_HAIR_BROWN_SP = mat("h_br", (0.32, 0.18, 0.10, 1.0), 0.0, 0.60)

# Toreador costume (signature traje de luces gold/silver)
M_TRAJE_GOLD = mat("tj_g", (1.0, 0.85, 0.25, 1.0), 0.95, 0.10, emission=(0.95,0.80,0.25), emission_strength=2.5)
M_TRAJE_RED = mat("tj_r", (0.85, 0.15, 0.20, 1.0), 0.0, 0.55, emission=(0.80,0.15,0.20), emission_strength=0.8)
M_TRAJE_PINK = mat("tj_p", (0.95, 0.45, 0.85, 1.0), 0.0, 0.55, emission=(0.92,0.45,0.82), emission_strength=0.8)
M_TRAJE_TIGHTS = mat("tj_t", (0.95, 0.92, 0.85, 1.0), 0.0, 0.65)
M_TRAJE_BLACK = mat("tj_bk", (0.08, 0.06, 0.06, 1.0), 0.4, 0.30)

# Bull
M_BULL_BLACK = mat("bl_b", (0.08, 0.05, 0.05, 1.0), 0.0, 0.85, emission=(0.10,0.08,0.08), emission_strength=0.5)
M_BULL_HORN = mat("bl_h", (0.85, 0.78, 0.65, 1.0), 0.0, 0.45)

# Guitar
M_GUITAR_WOOD = mat("gt_w", (0.55, 0.30, 0.15, 1.0), 0.0, 0.45, emission=(0.50,0.30,0.15), emission_strength=0.5)
M_GUITAR_DARK = mat("gt_d", (0.18, 0.10, 0.06, 1.0), 0.0, 0.55)
M_STRING = mat("string", (0.85, 0.85, 0.85, 1.0), 0.5, 0.30)

# Roses
M_ROSE_RED = mat("r_r", (0.95, 0.15, 0.18, 1.0), 0.0, 0.45, emission=(0.92,0.15,0.18), emission_strength=2.0)
M_ROSE_DEEP = mat("r_d", (0.65, 0.10, 0.15, 1.0), 0.0, 0.55, emission=(0.62,0.10,0.15), emission_strength=1.5)
M_ROSE_LEAF = mat("r_l", (0.20, 0.55, 0.25, 1.0), 0.0, 0.65)

# Eye
M_EYE_DARK_SP = mat("eye_d", (0.05, 0.04, 0.04, 1.0), 0.0, 0.20)
M_LIPS_RED_SP = mat("lp", (0.85, 0.18, 0.25, 1.0), 0.0, 0.40, emission=(0.80,0.18,0.25), emission_strength=0.6)

# Castanet
M_CASTANET = mat("cas", (0.55, 0.30, 0.15, 1.0), 0.5, 0.30, emission=(0.50,0.30,0.15), emission_strength=0.5)
M_CASTANET_GOLD = mat("cas_g", (1.0, 0.85, 0.30, 1.0), 0.95, 0.15, emission=(0.95,0.80,0.30), emission_strength=2.5)

# Tablao stage wood
M_STAGE_WOOD = mat("st_w", (0.55, 0.32, 0.15, 1.0), 0.0, 0.55, emission=(0.50,0.30,0.15), emission_strength=0.5)
M_STAGE_DARK = mat("st_d", (0.28, 0.16, 0.08, 1.0), 0.0, 0.75)

# ============ SKY ============
sky = smooth_sphere("sky", r=280, segs=32, rings=20, loc=(0,0,0), mat_=M_SKY)
sky.scale = (1,1,0.6)
sky_d = smooth_sphere("sky_d", r=230, segs=28, rings=16, loc=(0,0,5), mat_=M_SKY_DEEP)
sky_d.scale = (1,1,0.20)
# Sun
sun = smooth_sphere("sun", r=6, segs=24, rings=18, loc=(-30, 80, 30), mat_=M_SUN)
for sh in range(3):
    smooth_sphere(f"sun_h{sh}", r=6 + sh*0.8, segs=24, rings=18, loc=(-30, 80, 30), mat_=M_SUN)
# Clouds
for ci in range(15):
    cax = random.uniform(-100, 100); cay = random.uniform(-100, 100)
    caz = random.uniform(35, 60)
    cloud_e = empty(f"cloud{ci}", (cax, cay, caz))
    for cli in range(random.randint(3, 5)):
        smooth_sphere(f"c{ci}_{cli}", r=random.uniform(2.5, 4.5), segs=16, rings=10,
                      loc=(random.uniform(-3, 3), random.uniform(-3, 3), random.uniform(-0.5, 0.5)),
                      parent=cloud_e, mat_=M_CLOUD_RED, scale=(1.4, 1.2, 0.7))
    cloud_e["_phase"] = random.uniform(0, math.pi*2)

# ============ ONE clean Andalusian stone ground ============
ground = beveled_cube("ground", (200, 200, 0.5), bevel_offset=0.10, loc=(0, 0, -0.25), mat_=M_STONE_OCHRE)
# Tile pattern
for ti in range(30):
    for tj in range(30):
        tx_g = -45 + ti * 3; ty_g = -45 + tj * 3
        tcol = M_PAVE_RED if (ti + tj) % 3 == 0 else M_PAVE_WHITE if (ti + tj) % 3 == 1 else M_STONE_OCHRE
        beveled_cube(f"tile{ti}_{tj}", (2.8, 2.8, 0.06), bevel_offset=0.02,
                     loc=(tx_g, ty_g, 0.12), mat_=tcol)

# ============ GIRALDA TOWER (signature 96m bell tower) ============
giralda_e = empty("giralda", loc=(-30, 35, 0))
# Square Moorish base (12 levels)
for li in range(12):
    lz = li * 1.6
    lw = 5.0 - li * 0.02
    beveled_cube(f"g_l{li}", (lw, lw, 1.6), bevel_offset=0.06, loc=(0, 0, lz + 0.8),
                 parent=giralda_e, mat_=M_GIRALDA)
    # Decorative pattern bands (signature Moorish)
    if li % 2 == 0:
        for side_x, sx_m in zip(("F", "B"), (-1, 1)):
            for pi in range(4):
                px_p = -lw/2 + 0.5 + pi * (lw/4)
                beveled_cube(f"g_p{li}_{side_x}_{pi}", (0.4, 0.05, 0.30), bevel_offset=0.02,
                             loc=(px_p, sx_m*lw/2, lz + 0.8), parent=giralda_e, mat_=M_GIRALDA_PATTERN)
        for side_y, sy_m in zip(("L", "R"), (-1, 1)):
            for pi in range(4):
                py_p = -lw/2 + 0.5 + pi * (lw/4)
                beveled_cube(f"g_pY{li}_{side_y}_{pi}", (0.05, 0.4, 0.30), bevel_offset=0.02,
                             loc=(sy_m*lw/2, py_p, lz + 0.8), parent=giralda_e, mat_=M_GIRALDA_PATTERN)
    # Horseshoe arched windows
    for side_w in (-1, 1):
        beveled_cube(f"g_w{li}_{side_w}", (1.0, 0.1, 1.2), bevel_offset=0.25,
                     loc=(0, side_w*lw/2 - 0.02, lz + 0.8), parent=giralda_e, mat_=M_GIRALDA_DEEP)
# Renaissance belfry section (signature additions on top)
for li in range(4):
    lz = 12 * 1.6 + li * 2
    lw = 4.5 - li * 0.3
    beveled_cube(f"g_be{li}", (lw, lw, 2), bevel_offset=0.10, loc=(0, 0, lz + 1),
                 parent=giralda_e, mat_=M_GIRALDA)
    # Belfry arches
    for side_b in range(4):
        ba = (side_b / 4.0) * math.pi * 2
        beveled_cube(f"g_bea{li}_{side_b}", (1.5, 0.1, 1.5), bevel_offset=0.30,
                     loc=(math.cos(ba)*lw/2, math.sin(ba)*lw/2, lz + 1), parent=giralda_e,
                     mat_=M_GIRALDA_DEEP).rotation_euler = (0, 0, ba)
# Dome top section
cyl("g_dome_b", r=2, depth=1.5, segs=22, loc=(0, 0, 28.5), parent=giralda_e, mat_=M_GIRALDA)
smooth_sphere("g_dome", r=1.8, segs=22, rings=16, loc=(0, 0, 30), parent=giralda_e,
              mat_=M_GIRALDA, scale=(1, 1, 0.9))
# Spire
cyl("g_sp", r=0.20, depth=3, segs=12, loc=(0, 0, 32.5), parent=giralda_e, mat_=M_GIRALDA)
# EL GIRALDILLO weather vane signature (gold female figure)
g_fig_e = empty("g_fig", (0, 0, 35), parent=giralda_e)
# Body
smooth_cone("g_fig_b", r1=0.30, r2=0.25, depth=1.2, segs=12, loc=(0, 0, 0.6),
            parent=g_fig_e, mat_=M_CATH_GOLD)
# Head
smooth_sphere("g_fig_h", r=0.20, loc=(0, 0, 1.4), parent=g_fig_e, mat_=M_CATH_GOLD)
# Raised arm with banner
beveled_cube("g_fig_a", (0.4, 0.06, 0.06), bevel_offset=0.02, loc=(0.30, 0, 1.0),
             parent=g_fig_e, mat_=M_CATH_GOLD)
# Palm leaf
beveled_cube("g_fig_palm", (0.4, 0.04, 0.3), bevel_offset=0.04, loc=(0.55, 0, 1.0),
             parent=g_fig_e, mat_=M_CATH_GOLD)

# ============ SEVILLE CATHEDRAL (signature gothic) ============
cathedral_e = empty("cathedral", loc=(-5, 35, 0))
# Massive base
beveled_cube("cs_base", (25, 18, 12), bevel_offset=0.20, loc=(0, 0, 6),
             parent=cathedral_e, mat_=M_CATH_STONE)
# Flying buttresses (signature)
for bsi in range(6):
    bx = -10 + bsi * 4
    beveled_cube(f"cs_bt{bsi}", (1, 4, 8), bevel_offset=0.15, loc=(bx, -10, 5),
                 parent=cathedral_e, mat_=M_CATH_STONE)
    beveled_cube(f"cs_bt2{bsi}", (1, 4, 8), bevel_offset=0.15, loc=(bx, 10, 5),
                 parent=cathedral_e, mat_=M_CATH_STONE)
# Tall central nave + spires
for si in range(5):
    sx_p = -8 + si * 4
    cyl(f"cs_sp{si}", r=0.8, depth=15, segs=14, loc=(sx_p, 0, 19.5),
        parent=cathedral_e, mat_=M_CATH_STONE)
    smooth_cone(f"cs_sp_t{si}", r1=0.8, r2=0.05, depth=4, segs=14, loc=(sx_p, 0, 28),
                parent=cathedral_e, mat_=M_CATH_STONE)
    # Gold finial
    smooth_sphere(f"cs_sp_f{si}", r=0.20, loc=(sx_p, 0, 30.5),
                  parent=cathedral_e, mat_=M_CATH_GOLD)
# Rose window front signature
cyl("cs_rose", r=2.5, depth=0.30, segs=22, loc=(0, -9.2, 8), parent=cathedral_e, mat_=M_CATH_GOLD).rotation_euler = (math.radians(90), 0, 0)
# Rose details
for ri in range(12):
    ra = (ri / 12.0) * math.pi * 2
    cyl(f"cs_rp{ri}", r=0.15, depth=2.5, segs=8,
        loc=(math.cos(ra)*1.2, -9.3, 8 + math.sin(ra)*1.2),
        parent=cathedral_e, mat_=M_CATH_DARK).rotation_euler = (math.radians(90), 0, 0)
# Gothic arched doors
for di in range(3):
    dx = -4 + di * 4
    beveled_cube(f"cs_d{di}", (2, 0.30, 4), bevel_offset=0.30, loc=(dx, -9, 2),
                 parent=cathedral_e, mat_=M_CATH_DARK)

# ============ TABLAO STAGE (signature wood) ============
tablao_e = empty("tablao", loc=(0, -5, 0))
# Stage platform
beveled_cube("tb_pl", (16, 8, 0.5), bevel_offset=0.10, loc=(0, 0, 0.25),
             parent=tablao_e, mat_=M_STAGE_WOOD)
# Wood plank lines (signature for foot stomping)
for pi in range(16):
    beveled_cube(f"tb_p{pi}", (16.1, 0.5, 0.04), bevel_offset=0.01,
                 loc=(0, -3.75 + pi*0.5, 0.50), parent=tablao_e, mat_=M_STAGE_DARK)
# Back wall (signature dark red)
beveled_cube("tb_bw", (16, 0.30, 5), bevel_offset=0.10, loc=(0, 4, 2.75),
             parent=tablao_e, mat_=M_DRESS_DARK_RED)
# Spanish flag draped (signature yellow + red)
for fi in range(3):
    fy_p = -4 + fi * 4
    beveled_cube(f"tb_fl_y{fi}", (3, 0.10, 0.5), bevel_offset=0.04, loc=(fy_p, 4.05, 4.5),
                 parent=tablao_e, mat_=M_TRAJE_GOLD)
    beveled_cube(f"tb_fl_r{fi}", (3, 0.10, 0.5), bevel_offset=0.04, loc=(fy_p, 4.05, 4),
                 parent=tablao_e, mat_=M_DRESS_RED)
    beveled_cube(f"tb_fl_y2{fi}", (3, 0.10, 0.5), bevel_offset=0.04, loc=(fy_p, 4.05, 3.5),
                 parent=tablao_e, mat_=M_TRAJE_GOLD)

# ============ 6 FLAMENCO DANCERS (signature) ============
def make_flamenco_dancer(name, loc, scale=1.0, facing=0):
    base = empty(name, loc)
    base.rotation_euler = (0, 0, facing)
    # Long flowing dress (signature red with ruffles)
    smooth_cone(f"{name}_skirt", r1=0.70, r2=0.30, depth=1.7, segs=20, loc=(0, 0, 0.95),
                parent=base, mat_=M_DRESS_RED)
    # Signature multi-layered RUFFLES (volantes)
    for ri in range(5):
        ry = 0.20 + ri * 0.30
        rad = 0.75 - ri * 0.05
        # Outer ruffle (extra wave)
        for pi in range(16):
            pa = (pi / 16.0) * math.pi * 2
            smooth_sphere(f"{name}_rf{ri}_{pi}", r=0.10,
                          loc=(math.cos(pa)*rad, math.sin(pa)*rad, ry),
                          parent=base, mat_=M_DRESS_RED, scale=(1, 1, 0.3))
    # WHITE POLKA DOTS (signature)
    for di in range(60):
        da = random.uniform(0, math.pi*2)
        de = random.uniform(0, math.pi)
        dx = math.sin(de) * math.cos(da) * 0.65
        dy = math.sin(de) * math.sin(da) * 0.55
        dz = math.cos(de) * 0.6 + 0.95
        smooth_sphere(f"{name}_pk{di}", r=0.03,
                      loc=(dx, dy, dz), parent=base, mat_=M_POLKA_WHITE)
    # Corset top
    smooth_cone(f"{name}_corset", r1=0.32, r2=0.34, depth=0.50, segs=14, loc=(0, 0, 1.85),
                parent=base, mat_=M_DRESS_RED)
    # White polka on corset
    for di in range(15):
        da = (di / 15.0) * math.pi * 2
        smooth_sphere(f"{name}_pkc{di}", r=0.025,
                      loc=(math.cos(da)*0.34, math.sin(da)*0.34, 1.85 + (di%3)*0.10),
                      parent=base, mat_=M_POLKA_WHITE)
    # Arms raised dancing (signature flamenco pose)
    for side_idx, side in enumerate((-1, 1)):
        sh = empty(f"{name}_sh{side_idx}", (side*0.30, 0, 2.15), parent=base)
        if side == 1:
            sh.rotation_euler = (math.radians(-170), 0, math.radians(15))
        else:
            sh.rotation_euler = (math.radians(-120), 0, math.radians(-30))
        cyl(f"{name}_uarm{side_idx}", r=0.06, depth=0.40, segs=10,
            loc=(0, 0, -0.20), parent=sh, mat_=M_SKIN_TAN)
        # Lace ruffle on shoulder
        cyl(f"{name}_rfsl{side_idx}", r=0.18, depth=0.06, segs=14,
            loc=(0, 0, -0.05), parent=sh, mat_=M_DRESS_RED)
        cyl(f"{name}_fa{side_idx}", r=0.05, depth=0.35, segs=10,
            loc=(0, 0, -0.55), parent=sh, mat_=M_SKIN_TAN)
        # Hand with CASTANETS (signature)
        # Castanet
        smooth_sphere(f"{name}_cas{side_idx}", r=0.05, loc=(0, 0, -0.80),
                      parent=sh, mat_=M_CASTANET, scale=(1, 1, 0.5))
    # Head
    head_f_e = empty(f"{name}_he", (0, 0, 2.40), parent=base)
    smooth_sphere(f"{name}_head", r=0.18, segs=18, rings=14, loc=(0, 0, 0),
                  parent=head_f_e, mat_=M_SKIN_TAN)
    # Black hair tied tight + flower
    smooth_sphere(f"{name}_hair", r=0.22, loc=(0, 0.10, 0.05),
                  parent=head_f_e, mat_=M_HAIR_BLACK_SP, scale=(1, 1.1, 1.0))
    # ROSE FLOWER in hair (signature)
    rose_e = empty(f"{name}_rose", (0.18, 0.10, 0.15), parent=head_f_e)
    smooth_sphere(f"{name}_rs_c", r=0.06, loc=(0, 0, 0), parent=rose_e, mat_=M_ROSE_DEEP)
    for pi in range(8):
        pa = (pi / 8.0) * math.pi * 2
        smooth_sphere(f"{name}_rs_p{pi}", r=0.05,
                      loc=(math.cos(pa)*0.06, math.sin(pa)*0.06, 0),
                      parent=rose_e, mat_=M_ROSE_RED, scale=(1.3, 0.7, 0.5))
    # Eyes intense
    for side in (-1, 1):
        smooth_sphere(f"{name}_eye{side}", r=0.025,
                      loc=(side*0.06, -0.15, 0.03), parent=head_f_e, mat_=M_EYE_DARK_SP)
    # Red lips
    beveled_cube(f"{name}_lips", (0.08, 0.04, 0.025), bevel_offset=0.005,
                 loc=(0, -0.18, -0.07), parent=head_f_e, mat_=M_LIPS_RED_SP)
    # Earrings gold dangling
    for side in (-1, 1):
        smooth_sphere(f"{name}_er{side}", r=0.04, loc=(side*0.18, 0, -0.05),
                      parent=head_f_e, mat_=M_CATH_GOLD)
        cyl(f"{name}_er_d{side}", r=0.015, depth=0.10, segs=8, loc=(side*0.18, 0, -0.12),
            parent=head_f_e, mat_=M_CATH_GOLD)
    base["_phase"] = random.uniform(0, math.pi*2)
    return {"root": base, "he": head_f_e}

dancers = []
dancer_pos = [(-5, -3, math.radians(0)), (0, -3, math.radians(0)), (5, -3, math.radians(0)),
               (-5, -6, math.radians(0)), (0, -6, math.radians(0)), (5, -6, math.radians(0))]
for i, (dx, dy, fac) in enumerate(dancer_pos):
    d = make_flamenco_dancer(f"dancer{i}", (dx, dy, 0.55), scale=1.0, facing=fac)
    dancers.append(d)

# ============ 4 GUITARISTS (signature) ============
def make_guitarist(name, loc, scale=1.0, facing=0):
    base = empty(name, loc)
    base.rotation_euler = (0, 0, facing)
    # Black suit
    smooth_cone(f"{name}_jacket", r1=0.34, r2=0.32, depth=0.7, segs=14, loc=(0, 0, 0.55),
                parent=base, mat_=M_DRESS_BLACK)
    # White shirt collar
    cyl(f"{name}_col", r=0.30, depth=0.10, segs=14, loc=(0, 0, 0.95),
        parent=base, mat_=M_POLKA_WHITE)
    # Red sash signature
    cyl(f"{name}_sash", r=0.36, depth=0.10, segs=14, loc=(0, 0, 0.30),
        parent=base, mat_=M_DRESS_DARK_RED)
    # Head
    head_g_e = empty(f"{name}_he", (0, 0, 1.40), parent=base)
    smooth_sphere(f"{name}_head", r=0.18, segs=18, rings=14, loc=(0, 0, 0),
                  parent=head_g_e, mat_=random.choice(SKIN_SP))
    # Hair
    for hi in range(6):
        ha = (hi / 6.0) * math.pi * 2
        smooth_sphere(f"{name}_hr{hi}", r=0.05,
                      loc=(math.cos(ha)*0.15, math.sin(ha)*0.10, 0.10),
                      parent=head_g_e, mat_=random.choice([M_HAIR_BLACK_SP, M_HAIR_BROWN_SP]))
    # Beard
    for bi in range(8):
        ba = (bi / 8.0) * math.pi - math.pi/2
        smooth_sphere(f"{name}_bd{bi}", r=0.03,
                      loc=(math.sin(ba)*0.12, -0.15, -0.10),
                      parent=head_g_e, mat_=random.choice([M_HAIR_BLACK_SP, M_HAIR_BROWN_SP]))
    # Eyes
    for side in (-1, 1):
        smooth_sphere(f"{name}_eye{side}", r=0.025, loc=(side*0.06, -0.15, 0.03),
                      parent=head_g_e, mat_=M_EYE_DARK_SP)
    # GUITAR signature flamenco (golden wood)
    guitar_e = empty(f"{name}_gt", (0, -0.30, 0.75), parent=base)
    guitar_e.rotation_euler = (0, math.radians(-15), 0)
    # Body
    smooth_sphere(f"{name}_g_b", r=0.25, segs=18, rings=14, loc=(0, 0, 0),
                  parent=guitar_e, mat_=M_GUITAR_WOOD, scale=(0.85, 0.30, 1.2))
    # Soundhole
    cyl(f"{name}_g_h", r=0.06, depth=0.02, segs=14, loc=(0, -0.16, 0.05),
        parent=guitar_e, mat_=M_GUITAR_DARK)
    # Neck
    cyl(f"{name}_g_n", r=0.025, depth=0.55, segs=10, loc=(0, -0.10, 0.45),
        parent=guitar_e, mat_=M_GUITAR_DARK)
    # 6 strings
    for st in range(6):
        cyl(f"{name}_g_s{st}", r=0.003, depth=0.85, segs=6,
            loc=((st-2.5)*0.012, -0.13, 0.25), parent=guitar_e, mat_=M_STRING)
    # Headstock
    beveled_cube(f"{name}_g_hd", (0.10, 0.08, 0.10), bevel_offset=0.01,
                 loc=(0, -0.10, 0.75), parent=guitar_e, mat_=M_GUITAR_DARK)
    # Arm strumming
    arm_e = empty(f"{name}_arm", (0.20, -0.30, 0.85), parent=base)
    arm_e.rotation_euler = (math.radians(-70), 0, math.radians(-30))
    cyl(f"{name}_uarm", r=0.06, depth=0.40, segs=10, loc=(0, 0, -0.20),
        parent=arm_e, mat_=M_DRESS_BLACK)
    cyl(f"{name}_fa", r=0.05, depth=0.35, segs=10, loc=(0, 0, -0.55),
        parent=arm_e, mat_=M_SKIN_TAN)
    base["_phase"] = random.uniform(0, math.pi*2)
    return {"root": base, "inst": guitar_e, "he": head_g_e}

guitarists = []
guit_pos = [(-12, -10, math.radians(0)), (-8, -10, math.radians(0)),
             (8, -10, math.radians(0)), (12, -10, math.radians(0))]
for i, (gx, gy, fac) in enumerate(guit_pos):
    g = make_guitarist(f"guit{i}", (gx, gy, 0.55), scale=1.0, facing=fac)
    guitarists.append(g)

# ============ 4 TOREADORS (signature traje de luces) ============
def make_toreador(name, loc, scale=1.0, facing=0):
    base = empty(name, loc)
    base.rotation_euler = (0, 0, facing)
    traje_col = random.choice([M_TRAJE_GOLD, M_TRAJE_PINK, M_TRAJE_RED])
    # Tight pants white
    for side in (-1, 1):
        cyl(f"{name}_leg{side}", r=0.11, depth=1.0, segs=10,
            loc=(side*0.13, 0, 0.5), parent=base, mat_=M_TRAJE_TIGHTS)
    # Knee socks pink/red
    for side in (-1, 1):
        cyl(f"{name}_sk{side}", r=0.12, depth=0.55, segs=10,
            loc=(side*0.13, 0, 0.28), parent=base, mat_=M_TRAJE_RED)
        # Black shoes
        beveled_cube(f"{name}_sh{side}", (0.10, 0.20, 0.06), bevel_offset=0.02,
                     loc=(side*0.13, 0, 0), parent=base, mat_=M_TRAJE_BLACK)
    # JACKET (signature gold embroidered)
    smooth_cone(f"{name}_jacket", r1=0.30, r2=0.35, depth=0.70, segs=14, loc=(0, 0, 1.40),
                parent=base, mat_=traje_col)
    # GOLD EMBROIDERY signature ALL OVER jacket
    for ei in range(30):
        ea = random.uniform(0, math.pi*2)
        ee = random.uniform(0.1, 0.9)
        ex = math.sin(ee) * math.cos(ea) * 0.36
        ey = math.sin(ee) * math.sin(ea) * 0.36
        ez = math.cos(ee) * 0.4 + 1.40
        smooth_sphere(f"{name}_emb{ei}", r=0.025,
                      loc=(ex, ey, ez), parent=base, mat_=M_CATH_GOLD)
    # Shoulder epaulettes (signature)
    for side in (-1, 1):
        smooth_sphere(f"{name}_ep{side}", r=0.15, loc=(side*0.34, 0, 1.75),
                      parent=base, mat_=M_CATH_GOLD, scale=(1, 1.2, 0.7))
        # Gold tassels
        for ti in range(5):
            cyl(f"{name}_ts{side}_{ti}", r=0.012, depth=0.10, segs=6,
                loc=(side*0.34 + (ti-2)*0.04, 0, 1.65), parent=base, mat_=M_CATH_GOLD)
    # White frill at collar
    cyl(f"{name}_col", r=0.32, depth=0.10, segs=14, loc=(0, 0, 1.80),
        parent=base, mat_=M_POLKA_WHITE)
    # Belt sash red
    beveled_cube(f"{name}_sash", (0.7, 0.15, 0.20), bevel_offset=0.06, loc=(0, 0, 1.05),
                 parent=base, mat_=M_DRESS_DARK_RED)
    # Arms one raised (capote pose)
    sh_r = empty(f"{name}_sh_r", (0.32, 0, 1.65), parent=base)
    sh_r.rotation_euler = (math.radians(-150), 0, math.radians(-30))
    cyl(f"{name}_uarm_r", r=0.07, depth=0.40, segs=10, loc=(0, 0, -0.20),
        parent=sh_r, mat_=traje_col)
    cyl(f"{name}_fa_r", r=0.06, depth=0.35, segs=10, loc=(0, 0, -0.55),
        parent=sh_r, mat_=M_SKIN_TAN)
    # CAPOTE (red cape signature)
    cape_e = empty(f"{name}_cape", (0, 0, -0.85), parent=sh_r)
    for ci in range(8):
        ca = (ci / 8.0) * math.pi - math.pi/2
        beveled_cube(f"{name}_cp{ci}", (0.5, 0.06, 0.8), bevel_offset=0.06,
                     loc=(math.sin(ca)*0.40, 0, 0), parent=cape_e, mat_=M_DRESS_RED)
    sh_l = empty(f"{name}_sh_l", (-0.32, -0.15, 1.65), parent=base)
    sh_l.rotation_euler = (math.radians(-50), 0, math.radians(20))
    cyl(f"{name}_uarm_l", r=0.07, depth=0.40, segs=10, loc=(0, 0, -0.20),
        parent=sh_l, mat_=traje_col)
    cyl(f"{name}_fa_l", r=0.06, depth=0.35, segs=10, loc=(0, 0, -0.55),
        parent=sh_l, mat_=M_SKIN_TAN)
    # Head
    head_t_e = empty(f"{name}_he", (0, 0, 2.05), parent=base)
    smooth_sphere(f"{name}_head", r=0.18, segs=18, rings=14, loc=(0, 0, 0),
                  parent=head_t_e, mat_=random.choice(SKIN_SP))
    # Eyes
    for side in (-1, 1):
        smooth_sphere(f"{name}_eye{side}", r=0.025, loc=(side*0.06, -0.15, 0.03),
                      parent=head_t_e, mat_=M_EYE_DARK_SP)
    # Hair slicked black
    smooth_sphere(f"{name}_hair", r=0.16, loc=(0, 0.10, 0.08),
                  parent=head_t_e, mat_=M_HAIR_BLACK_SP, scale=(1, 1.1, 0.9))
    # MONTERA HAT (signature black bullfighter hat with 2 bumps)
    hat_t_e = empty(f"{name}_hat", (0, 0, 0.20), parent=head_t_e)
    cyl(f"{name}_h_brim", r=0.20, depth=0.04, segs=18, loc=(0, 0, 0),
        parent=hat_t_e, mat_=M_TRAJE_BLACK)
    # 2 bumps signature
    for side in (-1, 1):
        smooth_sphere(f"{name}_h_b{side}", r=0.13, loc=(side*0.10, 0, 0.10),
                      parent=hat_t_e, mat_=M_TRAJE_BLACK)
    # Coleta hairpiece (signature small braid at back)
    cyl(f"{name}_col_ta", r=0.025, depth=0.15, segs=8, loc=(0, 0.18, -0.05),
        parent=head_t_e, mat_=M_HAIR_BLACK_SP)
    base["_phase"] = random.uniform(0, math.pi*2)
    return {"root": base, "he": head_t_e, "cape": cape_e}

toreadors = []
tor_pos = [(-15, 5, math.radians(45)), (-10, 8, math.radians(0)),
            (10, 8, math.radians(-30)), (15, 5, math.radians(-45))]
for i, (tx, ty, fac) in enumerate(tor_pos):
    t = make_toreador(f"toreador{i}", (tx, ty, 0), scale=1.0, facing=fac)
    toreadors.append(t)

# ============ BULL (signature angry black) ============
bull_e = empty("bull", loc=(20, 5, 0))
bull_e.rotation_euler = (0, 0, math.radians(180))
# Body
smooth_sphere("bl_body", r=0.85, segs=22, rings=16, loc=(0, 0, 1.3),
              parent=bull_e, mat_=M_BULL_BLACK, scale=(1.8, 1.0, 1.0))
# Hump shoulders signature
smooth_sphere("bl_hump", r=0.55, loc=(0.7, 0, 1.8),
              parent=bull_e, mat_=M_BULL_BLACK)
# 4 thick legs
for x in (-1, 1):
    for y in (-1, 1):
        cyl(f"bl_l{x}{y}", r=0.18, depth=1.3, segs=12,
            loc=(x*0.55, y*0.35, 0.65), parent=bull_e, mat_=M_BULL_BLACK)
        # Hoof
        cyl(f"bl_h{x}{y}", r=0.20, depth=0.10, segs=12, loc=(x*0.55, y*0.35, 0.05),
            parent=bull_e, mat_=M_TRAJE_BLACK)
# Head
head_bl_e = empty("bl_he", (1.4, 0, 1.3), parent=bull_e)
smooth_sphere("bl_head", r=0.5, segs=20, rings=14, loc=(0, 0, 0),
              parent=head_bl_e, mat_=M_BULL_BLACK, scale=(1.4, 1.0, 1.0))
# Snout
smooth_sphere("bl_snout", r=0.35, loc=(0.30, 0, -0.10),
              parent=head_bl_e, mat_=M_BULL_BLACK, scale=(1.2, 0.9, 0.8))
# Nose
smooth_sphere("bl_nose", r=0.10, loc=(0.50, 0, -0.05), parent=head_bl_e, mat_=M_TRAJE_BLACK)
# HORNS (signature wide pointed)
for side in (-1, 1):
    h_e = empty(f"bl_h{side}_e", (-0.10, side*0.25, 0.30), parent=head_bl_e)
    h_e.rotation_euler = (math.radians(side*-20), 0, math.radians(side*40))
    for hi in range(5):
        cyl(f"bl_h{side}_{hi}", r=0.08 - hi*0.012, depth=0.15, segs=10,
            loc=(math.sin(hi*0.4)*0.05, 0, hi*0.15),
            parent=h_e, mat_=M_BULL_HORN)
    # Pointed tip
    smooth_cone(f"bl_h{side}_tip", r1=0.04, r2=0.005, depth=0.20, segs=8,
                loc=(0, 0, 0.85), parent=h_e, mat_=M_BULL_HORN)
# Ears
for side in (-1, 1):
    smooth_sphere(f"bl_ear{side}", r=0.15, loc=(-0.05, side*0.30, 0.20),
                  parent=head_bl_e, mat_=M_BULL_BLACK, scale=(0.5, 1.2, 1.2))
# Eyes glowing red
for side in (-1, 1):
    smooth_sphere(f"bl_eye{side}", r=0.06, loc=(0.20, side*0.20, 0.08),
                  parent=head_bl_e, mat_=M_DRESS_RED)
# Tail
cyl("bl_tail", r=0.05, depth=0.8, segs=8, loc=(-1.4, 0, 1.30),
    parent=bull_e, mat_=M_BULL_BLACK).rotation_euler = (math.radians(60), 0, 0)
# Tail tuft
smooth_sphere("bl_tt", r=0.10, loc=(-1.4, 0, 0.85),
              parent=bull_e, mat_=M_BULL_BLACK)
# Bandilleras (decorative darts in shoulder - signature)
for ki in range(3):
    ka = (ki / 3.0) * math.pi/2
    cyl(f"bl_b{ki}", r=0.015, depth=0.50, segs=8,
        loc=(0.6 + math.cos(ka)*0.10, math.sin(ka)*0.30, 2.10 + ki*0.05),
        parent=bull_e, mat_=M_TRAJE_RED).rotation_euler = (math.radians(70), 0, 0)
    # Ribbons
    beveled_cube(f"bl_br{ki}", (0.06, 0.04, 0.20), bevel_offset=0.02,
                 loc=(0.6 + math.cos(ka)*0.10, math.sin(ka)*0.30, 2.45 + ki*0.05),
                 parent=bull_e, mat_=random.choice([M_CATH_GOLD, M_DRESS_RED, M_TRAJE_PINK]))

# ============ 8 SPECTATORS sitting ============
def make_spectator(name, loc, scale=1.0, facing=0):
    base = empty(name, loc)
    base.rotation_euler = (0, 0, facing)
    shirt_col = random.choice([M_DRESS_RED, M_DRESS_BLACK, M_CATH_DARK, M_DRESS_DARK_RED, M_TRAJE_PINK])
    # Body
    smooth_cone(f"{name}_body", r1=0.30, r2=0.32, depth=0.55, segs=14, loc=(0, 0, 0.85),
                parent=base, mat_=shirt_col)
    # Legs forward (sitting)
    for side in (-1, 1):
        cyl(f"{name}_leg{side}", r=0.10, depth=0.60, segs=10,
            loc=(side*0.12, 0.20, 0.55), parent=base, mat_=M_DRESS_BLACK).rotation_euler = (math.radians(60), 0, 0)
    # Head
    head_s_e = empty(f"{name}_he", (0, 0, 1.30), parent=base)
    smooth_sphere(f"{name}_head", r=0.16, segs=16, rings=12, loc=(0, 0, 0),
                  parent=head_s_e, mat_=random.choice(SKIN_SP))
    # Hair
    smooth_sphere(f"{name}_hair", r=0.18, loc=(0, 0.05, 0.05),
                  parent=head_s_e, mat_=random.choice([M_HAIR_BLACK_SP, M_HAIR_BROWN_SP]),
                  scale=(1, 1.1, 0.95))
    # Eyes
    for side in (-1, 1):
        smooth_sphere(f"{name}_eye{side}", r=0.022, loc=(side*0.05, -0.13, 0.03),
                      parent=head_s_e, mat_=M_EYE_DARK_SP)
    # Hand fan signature (some spectators)
    if random.random() > 0.5:
        fan_e = empty(f"{name}_fan", (0.25, -0.10, 1.00), parent=base)
        fan_e.rotation_euler = (math.radians(-60), 0, math.radians(45))
        for fi in range(7):
            fa_fa = (fi / 6.0) * math.pi/2 - math.pi/4
            beveled_cube(f"{name}_fp{fi}", (0.04, 0.04, 0.20), bevel_offset=0.01,
                         loc=(math.cos(fa_fa)*0.15, 0, math.sin(fa_fa)*0.15),
                         parent=fan_e, mat_=random.choice([M_DRESS_RED, M_DRESS_BLACK, M_CATH_GOLD]))
    base["_phase"] = random.uniform(0, math.pi*2)
    return {"root": base, "he": head_s_e}

spectators = []
# Seats in arena around
spec_pos = [(-22, 12, math.radians(-15)), (-18, 14, math.radians(-30)),
             (-14, 16, math.radians(-45)), (-10, 17, math.radians(-60)),
             (10, 17, math.radians(60)), (14, 16, math.radians(45)),
             (18, 14, math.radians(30)), (22, 12, math.radians(15))]
for i, (sx, sy, fac) in enumerate(spec_pos):
    s = make_spectator(f"spec{i}", (sx, sy, 0.5), scale=1.0, facing=fac)
    spectators.append(s)

# Bench/seating for spectators
for bi in range(8):
    bx_p = -22 + bi * 6
    by_p = 12 + (bi % 2) * 2
    beveled_cube(f"bench{bi}", (3, 1, 0.4), bevel_offset=0.06, loc=(bx_p, by_p, 0.2),
                 mat_=M_STAGE_WOOD)

# ============================================================
# ⭐ 600 RED ROSES + 400 CASTANETS (PARTICULES THÉMATIQUES OBLIGATOIRES)
# ============================================================
roses = []
for i in range(600):
    px = random.uniform(-70, 70)
    py = random.uniform(-70, 70)
    pz = random.uniform(1, 18)
    r_e = empty(f"rs{i}", (px, py, pz))
    # Rose body (multi-petal)
    rcol = M_ROSE_RED if i % 2 == 0 else M_ROSE_DEEP
    # Center
    smooth_sphere(f"rs_c{i}", r=0.06, segs=10, rings=8, loc=(0, 0, 0),
                  parent=r_e, mat_=M_ROSE_DEEP)
    # 6 petals signature
    for pi in range(6):
        pa = (pi / 6.0) * math.pi * 2
        smooth_sphere(f"rs_p{i}_{pi}", r=0.06,
                      loc=(math.cos(pa)*0.05, math.sin(pa)*0.05, 0),
                      parent=r_e, mat_=rcol, scale=(1.4, 0.7, 0.4))
    r_e["_phase"] = random.uniform(0, math.pi*2)
    r_e["_base_x"] = px; r_e["_base_y"] = py; r_e["_base_z"] = pz
    r_e["_amp_x"] = random.uniform(1.0, 2.5)
    r_e["_amp_y"] = random.uniform(1.0, 2.5)
    r_e["_speed"] = random.uniform(0.5, 1.0)
    r_e["_fall"] = random.uniform(1.0, 2.5)
    roses.append(r_e)

# 400 castanets signature
castanets_part = []
for i in range(400):
    px = random.uniform(-50, 50)
    py = random.uniform(-50, 50)
    pz = random.uniform(2, 16)
    c_e = empty(f"cas{i}", (px, py, pz))
    # 2 shell halves
    smooth_sphere(f"cas_t{i}", r=0.08, segs=10, rings=8, loc=(0, 0, 0.03),
                  parent=c_e, mat_=M_CASTANET_GOLD, scale=(1, 1, 0.4))
    smooth_sphere(f"cas_b{i}", r=0.08, segs=10, rings=8, loc=(0, 0, -0.03),
                  parent=c_e, mat_=M_CASTANET_GOLD, scale=(1, 1, 0.4))
    # Cord
    cyl(f"cas_co{i}", r=0.005, depth=0.05, segs=6, loc=(0, 0, 0),
        parent=c_e, mat_=M_DRESS_RED)
    c_e["_phase"] = random.uniform(0, math.pi*2)
    c_e["_base_x"] = px; c_e["_base_y"] = py; c_e["_base_z"] = pz
    c_e["_amp_x"] = random.uniform(0.5, 1.5)
    c_e["_amp_y"] = random.uniform(0.5, 1.5)
    c_e["_speed"] = random.uniform(1.5, 3.5)
    castanets_part.append(c_e)

# ============ ANIMATION ============
fps = 30; duration_s = 6; total_frames = fps * duration_s

# Dancers flamenco
for d in dancers:
    phase = d["root"]["_phase"]
    for f in range(1, total_frames + 1, 2):
        t = (f - 1) / fps
        # Stomping + spinning signature
        d["root"].rotation_euler = (math.sin(t * 3.0 + phase) * math.radians(8),
                                     math.cos(t * 3.0 + phase) * math.radians(8),
                                     d["root"].rotation_euler.z + math.sin(t * 1.5 + phase) * math.radians(15))
        d["root"].location.z = 0.55 + abs(math.sin(t * 4.0 + phase)) * 0.15
        d["root"].keyframe_insert("rotation_euler", frame=f)
        d["root"].keyframe_insert("location", frame=f)
        d["he"].rotation_euler = (math.sin(t * 2.0 + phase) * math.radians(15), 0,
                                   math.cos(t * 2.0 + phase) * math.radians(25))
        d["he"].keyframe_insert("rotation_euler", frame=f)

# Guitarists strumming
for g in guitarists:
    phase = g["root"]["_phase"]
    for f in range(1, total_frames + 1, 3):
        t = (f - 1) / fps
        g["root"].rotation_euler = (math.sin(t * 3.0 + phase) * math.radians(4), 0,
                                     g["root"].rotation_euler.z)
        g["root"].keyframe_insert("rotation_euler", frame=f)
        sc_i = 1 + math.sin(t * 8.0 + phase) * 0.05
        g["inst"].scale = (sc_i, sc_i, sc_i)
        g["inst"].keyframe_insert("scale", frame=f)
        g["he"].rotation_euler = (math.sin(t * 2.0 + phase) * math.radians(8), 0, 0)
        g["he"].keyframe_insert("rotation_euler", frame=f)

# Toreadors with cape
for t_obj in toreadors:
    phase = t_obj["root"]["_phase"]
    for f in range(1, total_frames + 1, 3):
        t = (f - 1) / fps
        t_obj["cape"].rotation_euler = (math.sin(t * 2.5 + phase) * math.radians(20),
                                          math.cos(t * 2.5 + phase) * math.radians(15), 0)
        t_obj["cape"].keyframe_insert("rotation_euler", frame=f)
        t_obj["he"].rotation_euler = (0, 0, math.sin(t * 1.5 + phase) * math.radians(10))
        t_obj["he"].keyframe_insert("rotation_euler", frame=f)

# Bull paw + head
for f in range(1, total_frames + 1, 3):
    t = (f - 1) / fps
    bull_e.location.z = abs(math.sin(t * 2.5)) * 0.1
    bull_e.keyframe_insert("location", frame=f)
    head_bl_e.rotation_euler = (math.sin(t * 1.5) * math.radians(8), 0,
                                  math.cos(t * 1.0) * math.radians(15))
    head_bl_e.keyframe_insert("rotation_euler", frame=f)

# Spectators clap + sway
for s in spectators:
    phase = s["root"]["_phase"]
    for f in range(1, total_frames + 1, 3):
        t = (f - 1) / fps
        s["root"].rotation_euler = (math.sin(t * 2.0 + phase) * math.radians(3),
                                     math.cos(t * 2.0 + phase) * math.radians(3),
                                     s["root"].rotation_euler.z)
        s["root"].keyframe_insert("rotation_euler", frame=f)
        s["he"].rotation_euler = (0, 0, math.sin(t * 1.5 + phase) * math.radians(20))
        s["he"].keyframe_insert("rotation_euler", frame=f)

# 600 roses fall
for r in roses:
    phase = r["_phase"]; speed = r["_speed"]; fall = r["_fall"]
    bx, by, bz = r["_base_x"], r["_base_y"], r["_base_z"]
    ax, ay = r["_amp_x"], r["_amp_y"]
    for f in range(1, total_frames + 1, 4):
        t = (f - 1) / fps
        x = bx + ax * math.sin(t * speed + phase)
        y = by + ay * math.cos(t * speed * 0.9 + phase)
        z = bz - (t * fall) % (bz - 0.3)
        if z < 0.3: z = bz
        r.location = (x, y, max(0.2, z))
        r.rotation_euler = (t * 2.0 + phase, t * 1.5 + phase, t * 2.5 + phase)
        r.keyframe_insert("location", frame=f)
        r.keyframe_insert("rotation_euler", frame=f)

# 400 castanets spin
for c in castanets_part:
    phase = c["_phase"]; speed = c["_speed"]
    bx, by, bz = c["_base_x"], c["_base_y"], c["_base_z"]
    ax, ay = c["_amp_x"], c["_amp_y"]
    for f in range(1, total_frames + 1, 3):
        t = (f - 1) / fps
        x = bx + ax * math.sin(t * speed + phase) * 0.3
        y = by + ay * math.cos(t * speed * 0.9 + phase) * 0.3
        z = bz + math.sin(t * 2.0 + phase) * 0.5
        c.location = (x, y, z)
        # Rotation (signature spinning castanets)
        c.rotation_euler = (t * 5.0 + phase, t * 4.0 + phase, t * speed)
        c.keyframe_insert("location", frame=f)
        c.keyframe_insert("rotation_euler", frame=f)

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
out_glb = os.path.join(out_dir, "pbr_seville_proc.glb")

bpy.ops.object.select_all(action='SELECT')
bpy.ops.export_scene.gltf(
    filepath=out_glb, export_format='GLB',
    export_animations=True, export_apply=False, export_yup=True, use_selection=False,
)
size_mb = os.path.getsize(out_glb) / (1024 * 1024)
print(f"[proc_spanish_flamenco_seville] DONE → {out_glb} ({size_mb:.2f} MB)")
print(f"[proc_spanish_flamenco_seville] Giralda 96m with Moorish base + Renaissance belfry + El Giraldillo + Seville Cathedral gothic + 5 spires + rose window + tablao stage Spanish flag + 6 flamenco dancers red polka dots + 4 guitarists + 4 toreadors traje de luces gold + bull with bandilleras + 8 spectators with fans + 600 roses + 400 castanets")
print("⭐ FIXES: 1 ground + 600 roses + 400 castanets (signature Seville mandatory) ⭐")
