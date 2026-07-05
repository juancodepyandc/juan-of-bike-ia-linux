"""
proc_new_orleans_jazz_mardi_gras.py — 271e procédural AuroraIA (136e qualité)
New Orleans jazz Mardi Gras: 8 French Quarter facades + 4 jazz musicians + 4 masked dancers + Mardi Gras float + Louisiana flag pelican + gas lamps + 600 Mardi Gras beads + 400 jazz notes
FIXES : 1 ground Bourbon pavé + signature beads + notes
"""
import bpy, bmesh, math, random, os

random.seed(0x70AB271)

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

# Night sky Bourbon Street
M_SKY = mat("sky", (0.10, 0.08, 0.22, 1.0), 0.0, 0.7, emission=(0.10,0.08,0.22), emission_strength=1.5)
M_SKY_LOW = mat("sky_l", (0.42, 0.20, 0.45, 1.0), 0.0, 0.7, emission=(0.42,0.20,0.45), emission_strength=1.3)
M_STAR = mat("st", (1.0, 0.95, 0.85, 1.0), 0.0, 0.1, emission=(1.0,0.95,0.85), emission_strength=8.0)
M_MOON = mat("mn", (0.95, 0.92, 0.85, 1.0), 0.0, 0.1, emission=(0.95,0.92,0.85), emission_strength=15.0)

# Cobblestone street
M_STREET = mat("strt", (0.32, 0.28, 0.22, 1.0), 0.0, 0.85)
M_PAVE = mat("pv", (0.45, 0.38, 0.30, 1.0), 0.0, 0.85, emission=(0.42,0.38,0.30), emission_strength=0.2)
M_PAVE_WET = mat("pw", (0.55, 0.50, 0.45, 1.0), 0.3, 0.30, emission=(0.55,0.50,0.45), emission_strength=0.5)

# French Quarter facades (pastel signature)
M_NO_PINK = mat("nop", (1.0, 0.62, 0.65, 1.0), 0.0, 0.65, emission=(0.95,0.62,0.62), emission_strength=0.7)
M_NO_YELLOW = mat("noy", (1.0, 0.85, 0.45, 1.0), 0.0, 0.65, emission=(0.95,0.82,0.45), emission_strength=0.8)
M_NO_GREEN = mat("nog", (0.55, 0.75, 0.55, 1.0), 0.0, 0.65, emission=(0.55,0.72,0.55), emission_strength=0.6)
M_NO_BLUE = mat("nob", (0.55, 0.72, 0.85, 1.0), 0.0, 0.65, emission=(0.55,0.70,0.82), emission_strength=0.6)
M_NO_LAVENDER = mat("nol", (0.75, 0.65, 0.85, 1.0), 0.0, 0.65, emission=(0.72,0.62,0.82), emission_strength=0.6)
M_NO_RED = mat("nor", (0.85, 0.30, 0.32, 1.0), 0.0, 0.65, emission=(0.82,0.30,0.32), emission_strength=0.7)
FACADE_COLORS = [M_NO_PINK, M_NO_YELLOW, M_NO_GREEN, M_NO_BLUE, M_NO_LAVENDER, M_NO_RED]

# Window
M_WINDOW = mat("wd", (0.85, 0.78, 0.50, 1.0), 0.0, 0.35, emission=(0.85,0.78,0.50), emission_strength=5.0)
M_WINDOW_FRAME = mat("wf", (0.18, 0.13, 0.10, 1.0), 0.0, 0.75)
M_DOOR_WOOD = mat("dw", (0.32, 0.18, 0.10, 1.0), 0.0, 0.75)

# Wrought iron balcony (signature)
M_IRON = mat("ir", (0.12, 0.10, 0.10, 1.0), 0.6, 0.45)

# Brick
M_BRICK = mat("br", (0.65, 0.32, 0.22, 1.0), 0.0, 0.85, emission=(0.62,0.30,0.20), emission_strength=0.3)

# Skin
M_SKIN_MED = mat("sm", (0.78, 0.58, 0.45, 1.0), 0.0, 0.55, emission=(0.75,0.55,0.45), emission_strength=0.3)
M_SKIN_DARK = mat("sd", (0.45, 0.30, 0.20, 1.0), 0.0, 0.55, emission=(0.42,0.28,0.18), emission_strength=0.3)
SKINS = [M_SKIN_MED, M_SKIN_DARK]

# Hair
M_HAIR_BLACK = mat("hb", (0.10, 0.06, 0.05, 1.0), 0.0, 0.85)
M_HAIR_BROWN = mat("hbr", (0.32, 0.18, 0.08, 1.0), 0.0, 0.85)

# Musician outfit (jazz suit + bowtie)
M_SUIT_BLACK = mat("sb", (0.08, 0.07, 0.07, 1.0), 0.2, 0.45)
M_SUIT_WHITE = mat("sw", (0.92, 0.90, 0.85, 1.0), 0.0, 0.35, emission=(0.88,0.86,0.82), emission_strength=0.4)
M_SUIT_PINSTRIPE = mat("sp", (0.18, 0.16, 0.18, 1.0), 0.2, 0.50)
M_BOWTIE_PURPLE = mat("bp", (0.55, 0.20, 0.85, 1.0), 0.0, 0.45, emission=(0.52,0.20,0.82), emission_strength=0.7)
M_BOWTIE_GREEN = mat("bg", (0.30, 0.85, 0.30, 1.0), 0.0, 0.45, emission=(0.30,0.82,0.30), emission_strength=0.6)
M_BOWTIE_GOLD = mat("bgo", (1.0, 0.85, 0.20, 1.0), 0.3, 0.30, emission=(0.95,0.82,0.20), emission_strength=1.0)
BOWTIE_COLORS = [M_BOWTIE_PURPLE, M_BOWTIE_GREEN, M_BOWTIE_GOLD]

# Mardi Gras colors signature (purple gold green)
M_MG_PURPLE = mat("mgp", (0.55, 0.18, 0.85, 1.0), 0.0, 0.40, emission=(0.55,0.18,0.82), emission_strength=2.0)
M_MG_GOLD = mat("mgg", (1.0, 0.82, 0.18, 1.0), 0.4, 0.20, emission=(0.95,0.80,0.18), emission_strength=2.2)
M_MG_GREEN = mat("mgn", (0.20, 0.85, 0.30, 1.0), 0.0, 0.40, emission=(0.20,0.82,0.30), emission_strength=2.0)
MG_COLORS = [M_MG_PURPLE, M_MG_GOLD, M_MG_GREEN]

# Bourbon Street neon signs
M_NEON_RED = mat("nr", (1.0, 0.20, 0.20, 1.0), 0.0, 0.10, emission=(1.0,0.20,0.20), emission_strength=15.0)
M_NEON_BLUE = mat("nbl", (0.20, 0.55, 1.0, 1.0), 0.0, 0.10, emission=(0.20,0.55,1.0), emission_strength=15.0)
M_NEON_PINK = mat("npk", (1.0, 0.30, 0.85, 1.0), 0.0, 0.10, emission=(1.0,0.30,0.82), emission_strength=15.0)
M_NEON_GREEN = mat("ngn", (0.30, 1.0, 0.30, 1.0), 0.0, 0.10, emission=(0.30,0.95,0.30), emission_strength=15.0)
NEON_COLORS = [M_NEON_RED, M_NEON_BLUE, M_NEON_PINK, M_NEON_GREEN]

# Gas lamp (signature)
M_GAS_METAL = mat("gm", (0.18, 0.15, 0.13, 1.0), 0.6, 0.40)
M_GAS_GLOW = mat("gg", (1.0, 0.78, 0.30, 1.0), 0.0, 0.10, emission=(1.0,0.78,0.30), emission_strength=18.0)
M_GAS_GLASS = mat("ggl", (0.85, 0.78, 0.55, 1.0), 0.0, 0.10, emission=(0.85,0.78,0.55), emission_strength=2.0, alpha=0.70)

# Instruments (jazz brass signature)
M_BRASS_GOLD = mat("brg", (0.95, 0.78, 0.20, 1.0), 1.0, 0.10, emission=(0.92,0.75,0.20), emission_strength=0.7)
M_BRASS_DARK = mat("brd", (0.55, 0.42, 0.10, 1.0), 0.8, 0.30)
M_TROMBONE_SLIDE = mat("trs", (0.95, 0.95, 0.92, 1.0), 1.0, 0.05)

# Mardi Gras float
M_FLOAT_PURPLE = mat("fpp", (0.65, 0.30, 0.85, 1.0), 0.0, 0.45, emission=(0.62,0.30,0.82), emission_strength=1.0)
M_FLOAT_GOLD = mat("fpg", (1.0, 0.85, 0.25, 1.0), 0.4, 0.30, emission=(0.95,0.82,0.25), emission_strength=1.5)
M_FLOAT_GREEN = mat("fpgn", (0.35, 0.85, 0.40, 1.0), 0.0, 0.45, emission=(0.32,0.82,0.40), emission_strength=1.0)

# Masks (signature Venetian Mardi Gras)
M_MASK_GOLD = mat("msg", (1.0, 0.82, 0.30, 1.0), 0.6, 0.20, emission=(0.95,0.80,0.30), emission_strength=1.5)
M_MASK_PURPLE = mat("msp", (0.55, 0.20, 0.85, 1.0), 0.3, 0.30, emission=(0.52,0.20,0.82), emission_strength=1.2)
M_FEATHER_PURPLE = mat("ftp", (0.55, 0.18, 0.85, 1.0), 0.0, 0.55, emission=(0.55,0.18,0.82), emission_strength=1.0)
M_FEATHER_GOLD = mat("ftg", (0.95, 0.82, 0.25, 1.0), 0.0, 0.55, emission=(0.92,0.80,0.25), emission_strength=1.2)
M_FEATHER_GREEN = mat("ftgn", (0.32, 0.85, 0.40, 1.0), 0.0, 0.55, emission=(0.32,0.82,0.40), emission_strength=1.0)

# Eyes/lips
M_EYE = mat("ed", (0.05, 0.04, 0.04, 1.0), 0.0, 0.20)
M_LIPS_RED = mat("lr", (0.85, 0.18, 0.20, 1.0), 0.0, 0.30, emission=(0.80,0.18,0.20), emission_strength=0.5)

# Louisiana flag pelican
M_FLAG_BLUE = mat("fbl", (0.18, 0.32, 0.65, 1.0), 0.0, 0.45, emission=(0.18,0.30,0.62), emission_strength=1.0)
M_FLAG_WHITE = mat("fw", (0.95, 0.95, 0.92, 1.0), 0.0, 0.45, emission=(0.92,0.92,0.90), emission_strength=0.8)
M_PELICAN_WHITE = mat("pcw", (0.92, 0.88, 0.82, 1.0), 0.0, 0.55, emission=(0.88,0.86,0.80), emission_strength=0.5)
M_PELICAN_GOLD = mat("pcg", (0.92, 0.72, 0.20, 1.0), 0.3, 0.30, emission=(0.88,0.70,0.20), emission_strength=0.7)

# Beads
M_BEAD_PURPLE = mat("bdp", (0.55, 0.18, 0.85, 1.0), 0.7, 0.10, emission=(0.55,0.18,0.82), emission_strength=2.5)
M_BEAD_GOLD = mat("bdg", (1.0, 0.85, 0.20, 1.0), 0.9, 0.05, emission=(0.95,0.82,0.20), emission_strength=3.0)
M_BEAD_GREEN = mat("bdgn", (0.20, 0.92, 0.35, 1.0), 0.7, 0.10, emission=(0.20,0.88,0.35), emission_strength=2.5)
BEAD_COLORS = [M_BEAD_PURPLE, M_BEAD_GOLD, M_BEAD_GREEN]

# Music note
M_NOTE = mat("n", (1.0, 0.85, 0.30, 1.0), 0.4, 0.20, emission=(0.95,0.82,0.30), emission_strength=2.8)
M_NOTE_PURPLE = mat("np", (0.55, 0.18, 0.85, 1.0), 0.4, 0.20, emission=(0.52,0.18,0.82), emission_strength=2.5)

# ============ SKY ============
sky = smooth_sphere("sky", r=280, segs=32, rings=20, loc=(0,0,0), mat_=M_SKY)
sky.scale = (1,1,0.6)
sky_l = smooth_sphere("sky_l", r=240, segs=28, rings=16, loc=(0,0,5), mat_=M_SKY_LOW)
sky_l.scale = (1,1,0.3)
# Moon
smooth_sphere("moon", r=6, segs=24, rings=18, loc=(40, 90, 25), mat_=M_MOON)
# Stars
for si in range(60):
    sa = random.uniform(0, math.pi*2); se = random.uniform(0.4, 0.9)
    sx_st = math.cos(sa) * 200 * math.cos(se)
    sy_st = math.sin(sa) * 200 * math.cos(se)
    sz_st = math.sin(se) * 150 + 40
    smooth_sphere(f"star{si}", r=random.uniform(0.4, 0.9), segs=8, rings=6,
                  loc=(sx_st, sy_st, sz_st), mat_=M_STAR)

# ============ ONE clean Bourbon Street pavement ground ============
ground = beveled_cube("ground", (200, 200, 0.5), bevel_offset=0.10, loc=(0, 0, -0.25), mat_=M_STREET)
# Cobblestones along street
for cbi in range(50):
    for cbj in range(50):
        bx = -38 + cbi * 1.5
        by = -38 + cbj * 1.5
        if -35 < bx < 35 and -35 < by < 35 and random.random() > 0.25:
            cyl(f"cb{cbi}_{cbj}", r=0.42, depth=0.06, segs=10,
                loc=(bx, by, 0.10),
                mat_=M_PAVE if (cbi + cbj) % 2 else M_PAVE_WET)

# ============ 8 FRENCH QUARTER FACADES (signature wrought iron balconies) ============
def make_facade(name, loc, width, height, depth, mat_):
    base = empty(name, loc)
    # Main wall
    beveled_cube(f"{name}_w", (width, depth, height), bevel_offset=0.10,
                 loc=(0, 0, height/2), parent=base, mat_=mat_)
    # Windows on 2 floors
    win_rows = 3; win_cols = max(2, int(width / 3))
    for r in range(win_rows):
        for c in range(win_cols):
            wx = -width/2 + (c + 0.5) * (width / win_cols)
            wz = (r + 0.5) * (height / win_rows)
            # Frame
            beveled_cube(f"{name}_wf{r}_{c}", (0.95, 0.05, 1.4), bevel_offset=0.03,
                         loc=(wx, -depth/2 - 0.05, wz), parent=base, mat_=M_WINDOW_FRAME)
            # Glass
            beveled_cube(f"{name}_wg{r}_{c}", (0.85, 0.02, 1.25), bevel_offset=0.02,
                         loc=(wx, -depth/2 - 0.08, wz), parent=base, mat_=M_WINDOW)
            # Cross bars
            beveled_cube(f"{name}_wxv{r}_{c}", (0.04, 0.04, 1.25), bevel_offset=0.01,
                         loc=(wx, -depth/2 - 0.09, wz), parent=base, mat_=M_WINDOW_FRAME)
            beveled_cube(f"{name}_wxh{r}_{c}", (0.85, 0.04, 0.04), bevel_offset=0.01,
                         loc=(wx, -depth/2 - 0.09, wz), parent=base, mat_=M_WINDOW_FRAME)
    # WROUGHT IRON BALCONY (signature continuous on upper floor)
    for r in (1, 2):
        bz_ba = (r + 0.5) * (height / win_rows) - 0.75
        # Floor plate
        beveled_cube(f"{name}_bf{r}", (width + 0.3, 1.2, 0.10), bevel_offset=0.03,
                     loc=(0, -depth/2 - 0.60, bz_ba - 0.10), parent=base, mat_=M_IRON)
        # Top rail
        beveled_cube(f"{name}_br{r}", (width + 0.3, 1.2, 0.06), bevel_offset=0.02,
                     loc=(0, -depth/2 - 0.60, bz_ba + 0.50), parent=base, mat_=M_IRON)
        # Vertical bars
        n_bars = int(width / 0.15)
        for bi in range(n_bars):
            bx_b = -width/2 + bi * 0.15
            cyl(f"{name}_bv{r}_{bi}", r=0.015, depth=0.55, segs=6,
                loc=(bx_b, -depth/2 - 0.95, bz_ba + 0.20), parent=base, mat_=M_IRON)
        # Front rail (signature ornate pattern)
        n_orn = int(width / 0.5)
        for oi in range(n_orn):
            ox = -width/2 + (oi + 0.5) * (width / n_orn)
            # Ornament curl
            smooth_sphere(f"{name}_bo{r}_{oi}", r=0.10, segs=10, rings=8,
                          loc=(ox, -depth/2 - 1.20, bz_ba + 0.50),
                          parent=base, mat_=M_IRON)
        # Support brackets
        for sb_i in (-1, 1):
            sb_x_p = sb_i * (width/2 - 0.5)
            cyl(f"{name}_bk{r}_{sb_i}", r=0.04, depth=1.4, segs=6,
                loc=(sb_x_p, -depth/2 - 0.30, bz_ba - 0.30),
                parent=base, mat_=M_IRON).rotation_euler = (math.radians(90), 0, math.radians(45))
    # Door
    beveled_cube(f"{name}_d", (1.2, 0.06, 2.0), bevel_offset=0.05,
                 loc=(0, -depth/2 - 0.05, 1.0), parent=base, mat_=M_DOOR_WOOD)
    # Cornice
    beveled_cube(f"{name}_co", (width + 0.4, depth + 0.4, 0.30), bevel_offset=0.06,
                 loc=(0, 0, height + 0.15), parent=base, mat_=M_BRICK)
    # Neon sign (signature Bourbon Street)
    neon_e = empty(f"{name}_ne", (-width/3, -depth/2 - 0.40, height * 0.3), parent=base)
    cyl(f"{name}_ne_b", r=0.12, depth=0.10, segs=10, loc=(0, 0, 0),
        parent=neon_e, mat_=M_IRON).rotation_euler = (math.radians(90), 0, 0)
    # Neon tube (curled)
    neon_col = random.choice(NEON_COLORS)
    for ni in range(8):
        na = (ni / 8.0) * math.pi * 2
        cyl(f"{name}_ne_t{ni}", r=0.04, depth=0.20, segs=6,
            loc=(math.cos(na)*0.25, -0.08, math.sin(na)*0.25),
            parent=neon_e, mat_=neon_col)
    return base

# Left row facades
for i, (fx, fy, fw, fh) in enumerate([(-22, -28, 8, 9), (-22, -18, 8, 8), (-22, -8, 8, 10), (-22, 2, 8, 9)]):
    make_facade(f"facL{i}", (fx, fy, 0), fw, fh, 3, random.choice(FACADE_COLORS))
# Right row facades
for i, (fx, fy, fw, fh) in enumerate([(22, -28, 8, 9), (22, -18, 8, 10), (22, -8, 8, 8), (22, 2, 8, 9)]):
    fac = make_facade(f"facR{i}", (fx, fy, 0), fw, fh, 3, random.choice(FACADE_COLORS))
    fac.rotation_euler = (0, 0, math.radians(180))

# ============ 8 GAS LAMPS (signature warm glow) ============
def make_gas_lamp(name, loc):
    base = empty(name, loc)
    # Base
    cyl(f"{name}_b", r=0.25, depth=0.35, segs=12, loc=(0, 0, 0.18), parent=base, mat_=M_GAS_METAL)
    # Pole
    cyl(f"{name}_p", r=0.08, depth=4, segs=10, loc=(0, 0, 2.20), parent=base, mat_=M_GAS_METAL)
    # Lantern housing (signature 4-sided glass)
    for si in range(4):
        sa = (si / 4.0) * math.pi * 2
        beveled_cube(f"{name}_gh{si}", (0.04, 0.30, 0.50), bevel_offset=0.01,
                     loc=(math.cos(sa)*0.22, math.sin(sa)*0.22, 4.30),
                     parent=base, mat_=M_GAS_METAL).rotation_euler = (0, 0, sa)
    # Glass panels
    for si in range(4):
        sa = (si / 4.0 + 0.125) * math.pi * 2
        beveled_cube(f"{name}_gp{si}", (0.32, 0.04, 0.45), bevel_offset=0.01,
                     loc=(math.cos(sa)*0.20, math.sin(sa)*0.20, 4.30),
                     parent=base, mat_=M_GAS_GLASS).rotation_euler = (0, 0, sa)
    # Flame inside
    smooth_sphere(f"{name}_fl", r=0.12, segs=12, rings=8, loc=(0, 0, 4.25),
                  parent=base, mat_=M_GAS_GLOW)
    # Top cap
    smooth_cone(f"{name}_tc", r1=0.30, r2=0.05, depth=0.30, segs=14, loc=(0, 0, 4.70),
                parent=base, mat_=M_GAS_METAL)
    # Cross arms
    for si in (-1, 1):
        cyl(f"{name}_ca{si}", r=0.05, depth=0.40, segs=8,
            loc=(si*0.20, 0, 3.95), parent=base, mat_=M_GAS_METAL).rotation_euler = (0, math.radians(90), 0)
    return base

for i, (lx, ly) in enumerate([(-17, -22), (-17, -12), (-17, -2), (-17, 5),
                                (17, -22), (17, -12), (17, -2), (17, 5)]):
    make_gas_lamp(f"lp{i}", (lx, ly, 0))

# ============ 4 JAZZ MUSICIANS (signature) ============
def make_jazz_musician(name, loc, instrument, facing=0):
    base = empty(name, loc)
    base.rotation_euler = (0, 0, facing)
    sk = random.choice(SKINS)
    suit_mat = random.choice([M_SUIT_BLACK, M_SUIT_PINSTRIPE])
    # Jacket
    smooth_cone(f"{name}_j", r1=0.32, r2=0.34, depth=0.85, segs=14, loc=(0, 0, 1.25),
                parent=base, mat_=suit_mat)
    # White shirt collar
    beveled_cube(f"{name}_sh_c", (0.20, 0.06, 0.55), bevel_offset=0.02,
                 loc=(0, -0.30, 1.50), parent=base, mat_=M_SUIT_WHITE)
    # Bowtie (signature)
    btie_e = empty(f"{name}_bt", (0, -0.32, 1.65), parent=base)
    bt_col = random.choice(BOWTIE_COLORS)
    beveled_cube(f"{name}_bt_l", (0.10, 0.04, 0.08), bevel_offset=0.01, loc=(-0.05, 0, 0),
                 parent=btie_e, mat_=bt_col)
    beveled_cube(f"{name}_bt_r", (0.10, 0.04, 0.08), bevel_offset=0.01, loc=(0.05, 0, 0),
                 parent=btie_e, mat_=bt_col)
    beveled_cube(f"{name}_bt_c", (0.04, 0.05, 0.06), bevel_offset=0.005, loc=(0, 0, 0),
                 parent=btie_e, mat_=bt_col)
    # Pants
    for side in (-1, 1):
        cyl(f"{name}_p{side}", r=0.11, depth=0.95, segs=10,
            loc=(side*0.13, 0, 0.50), parent=base, mat_=suit_mat)
    # Dress shoes
    for side in (-1, 1):
        beveled_cube(f"{name}_sh{side}", (0.13, 0.28, 0.06), bevel_offset=0.02,
                     loc=(side*0.13, 0, 0.03), parent=base, mat_=M_SUIT_BLACK)
    # Head
    head_mu_e = empty(f"{name}_he", (0, 0, 1.95), parent=base)
    smooth_sphere(f"{name}_h", r=0.18, segs=18, rings=14, loc=(0, 0, 0),
                  parent=head_mu_e, mat_=sk)
    # Hair
    hair_col = random.choice([M_HAIR_BLACK, M_HAIR_BROWN])
    for hi in range(12):
        ha = random.uniform(0, math.pi*2)
        cyl(f"{name}_hr{hi}", r=0.04, depth=0.10, segs=6,
            loc=(math.cos(ha)*0.12, math.sin(ha)*0.10, 0.15),
            parent=head_mu_e, mat_=hair_col)
    # Eyes
    for side in (-1, 1):
        smooth_sphere(f"{name}_ey{side}", r=0.025, loc=(side*0.06, -0.15, 0.03),
                      parent=head_mu_e, mat_=M_EYE)
    # FEDORA hat (signature jazz)
    hat_e = empty(f"{name}_ha", (0, 0, 0.20), parent=head_mu_e)
    cyl(f"{name}_ha_c", r=0.20, depth=0.18, segs=18, loc=(0, 0, 0),
        parent=hat_e, mat_=M_SUIT_BLACK)
    cyl(f"{name}_ha_b", r=0.30, depth=0.04, segs=18, loc=(0, 0, -0.10),
        parent=hat_e, mat_=M_SUIT_BLACK)
    # Band
    cyl(f"{name}_ha_bd", r=0.21, depth=0.04, segs=18, loc=(0, 0, -0.06),
        parent=hat_e, mat_=bt_col)
    # INSTRUMENT
    inst_e = empty(f"{name}_inst", (0, -0.40, 1.30), parent=base)
    if instrument == "trumpet":
        # Bell
        smooth_cone(f"{name}_t_bl", r1=0.04, r2=0.20, depth=0.35, segs=16, loc=(0, 0.40, 0),
                    parent=inst_e, mat_=M_BRASS_GOLD).rotation_euler = (math.radians(90), 0, 0)
        # Body tube
        cyl(f"{name}_t_b", r=0.04, depth=0.60, segs=10, loc=(0, 0, 0),
            parent=inst_e, mat_=M_BRASS_GOLD).rotation_euler = (math.radians(90), 0, 0)
        # Valves (3 piston)
        for vi in range(3):
            cyl(f"{name}_t_v{vi}", r=0.04, depth=0.18, segs=10,
                loc=(0, -0.10 + vi*0.10, 0.08), parent=inst_e, mat_=M_BRASS_DARK)
            cyl(f"{name}_t_vt{vi}", r=0.03, depth=0.05, segs=8,
                loc=(0, -0.10 + vi*0.10, 0.20), parent=inst_e, mat_=M_BRASS_GOLD)
        # Mouthpiece
        cyl(f"{name}_t_m", r=0.03, depth=0.06, segs=8, loc=(0, -0.34, 0),
            parent=inst_e, mat_=M_BRASS_GOLD).rotation_euler = (math.radians(90), 0, 0)
    elif instrument == "saxophone":
        # Body curved (signature S-shape)
        for sci in range(12):
            sca = (sci / 12.0) * math.radians(180)
            cyl(f"{name}_s_c{sci}", r=0.04 + sci*0.005, depth=0.15, segs=10,
                loc=(math.sin(sca)*0.15, 0, -math.cos(sca)*0.35 + 0.05),
                parent=inst_e, mat_=M_BRASS_GOLD).rotation_euler = (sca, 0, 0)
        # Bell (signature flare)
        smooth_cone(f"{name}_s_bl", r1=0.10, r2=0.22, depth=0.30, segs=16, loc=(0.20, 0, -0.30),
                    parent=inst_e, mat_=M_BRASS_GOLD).rotation_euler = (math.radians(45), 0, 0)
        # Keys (signature pearl buttons)
        for ki in range(8):
            kz_p = -0.30 + ki * 0.08
            smooth_sphere(f"{name}_s_k{ki}", r=0.025, loc=(0.10, -0.06, kz_p),
                          parent=inst_e, mat_=M_SUIT_WHITE)
        # Mouthpiece
        cyl(f"{name}_s_m", r=0.025, depth=0.10, segs=8, loc=(0, 0, 0.50),
            parent=inst_e, mat_=M_SUIT_BLACK)
        cyl(f"{name}_s_mr", r=0.035, depth=0.05, segs=8, loc=(0, 0, 0.40),
            parent=inst_e, mat_=M_BRASS_GOLD)
    elif instrument == "trombone":
        # Bell
        smooth_cone(f"{name}_tb_bl", r1=0.04, r2=0.22, depth=0.40, segs=16, loc=(0.30, 0, 0),
                    parent=inst_e, mat_=M_BRASS_GOLD).rotation_euler = (math.radians(90), math.radians(-90), 0)
        # U-bend at back
        for ubi in range(8):
            uba = (ubi / 8.0) * math.pi
            cyl(f"{name}_tb_u{ubi}", r=0.03, depth=0.10, segs=8,
                loc=(-0.40 - math.sin(uba)*0.15, 0, -math.cos(uba)*0.15),
                parent=inst_e, mat_=M_BRASS_GOLD)
        # Slide tubes (chrome signature)
        cyl(f"{name}_tb_s1", r=0.025, depth=0.80, segs=8, loc=(-0.20, -0.07, 0.05),
            parent=inst_e, mat_=M_TROMBONE_SLIDE).rotation_euler = (0, math.radians(90), 0)
        cyl(f"{name}_tb_s2", r=0.025, depth=0.80, segs=8, loc=(-0.20, 0.07, 0.05),
            parent=inst_e, mat_=M_TROMBONE_SLIDE).rotation_euler = (0, math.radians(90), 0)
        # Mouthpiece
        cyl(f"{name}_tb_m", r=0.03, depth=0.08, segs=8, loc=(0.45, 0, 0),
            parent=inst_e, mat_=M_BRASS_GOLD).rotation_euler = (math.radians(90), math.radians(-90), 0)
    elif instrument == "tuba":
        # Massive coiled body (signature)
        for ci in range(20):
            ca = (ci / 20.0) * math.pi * 2
            cyl(f"{name}_tu_c{ci}", r=0.06, depth=0.20, segs=8,
                loc=(math.cos(ca)*0.30, 0, math.sin(ca)*0.30 + 0.10),
                parent=inst_e, mat_=M_BRASS_GOLD).rotation_euler = (ca, math.radians(90), 0)
        # Huge bell flare (signature upward facing)
        smooth_cone(f"{name}_tu_bl", r1=0.10, r2=0.45, depth=0.60, segs=18, loc=(0, 0, 0.60),
                    parent=inst_e, mat_=M_BRASS_GOLD)
        # Valves
        for vi in range(4):
            cyl(f"{name}_tu_v{vi}", r=0.05, depth=0.20, segs=10,
                loc=(0.40, -0.10 + vi*0.07, 0.15), parent=inst_e, mat_=M_BRASS_DARK)
    # Arms holding instrument
    for side_idx, side in enumerate((-1, 1)):
        sh = empty(f"{name}_a{side_idx}", (side*0.32, 0, 1.65), parent=base)
        sh.rotation_euler = (math.radians(-90 if side_idx == 0 else -70), 0, 0)
        cyl(f"{name}_ua{side_idx}", r=0.07, depth=0.40, segs=10, loc=(0, 0, -0.20),
            parent=sh, mat_=suit_mat)
        cyl(f"{name}_fa{side_idx}", r=0.06, depth=0.35, segs=10, loc=(0, 0, -0.55),
            parent=sh, mat_=M_SUIT_WHITE)
    base["_phase"] = random.uniform(0, math.pi*2)
    return {"root": base, "inst": inst_e, "he": head_mu_e}

musicians = []
mus_data = [("trumpet", -12, -22), ("saxophone", -4, -22), ("trombone", 4, -22), ("tuba", 12, -22)]
for i, (inst, mx, my) in enumerate(mus_data):
    m = make_jazz_musician(f"mus{i}", (mx, my, 0), instrument=inst,
                            facing=math.radians(0))
    musicians.append(m)

# ============ 4 MASKED DANCERS (signature Mardi Gras) ============
def make_masked_dancer(name, loc, facing=0):
    base = empty(name, loc)
    base.rotation_euler = (0, 0, facing)
    sk = random.choice(SKINS)
    # Costume colorful (Mardi Gras colors)
    dress_col = random.choice(MG_COLORS)
    # Body
    smooth_cone(f"{name}_to", r1=0.30, r2=0.32, depth=0.85, segs=14, loc=(0, 0, 1.30),
                parent=base, mat_=dress_col)
    # Skirt flowing
    skirt_e = empty(f"{name}_sk", (0, 0, 0.95), parent=base)
    for ri in range(2):
        rz = -ri * 0.20
        rr = 0.34 + ri * 0.08
        for rj in range(20):
            rja = (rj / 20.0) * math.pi * 2
            beveled_cube(f"{name}_r{ri}_{rj}", (0.08, 0.10, 0.20), bevel_offset=0.01,
                         loc=(math.cos(rja)*rr, math.sin(rja)*rr, rz),
                         parent=skirt_e, mat_=dress_col).rotation_euler = (0, math.cos(rja)*0.10, rja)
    # Legs
    for side in (-1, 1):
        cyl(f"{name}_l{side}", r=0.09, depth=0.85, segs=10,
            loc=(side*0.13, 0, 0.45), parent=base, mat_=sk)
    # Heels
    for side in (-1, 1):
        beveled_cube(f"{name}_h{side}", (0.10, 0.22, 0.04), bevel_offset=0.02,
                     loc=(side*0.13, 0, 0), parent=base, mat_=dress_col)
    # Arms raised
    for side_idx, side in enumerate((-1, 1)):
        sh = empty(f"{name}_a{side_idx}", (side*0.30, 0, 1.65), parent=base)
        sh.rotation_euler = (math.radians(-130 if side_idx == 0 else -100), 0, math.radians(side*40))
        cyl(f"{name}_ua{side_idx}", r=0.06, depth=0.40, segs=10, loc=(0, 0, -0.20),
            parent=sh, mat_=sk)
        # Long gloves
        cyl(f"{name}_gl{side_idx}", r=0.06, depth=0.40, segs=10, loc=(0, 0, -0.55),
            parent=sh, mat_=dress_col)
        cyl(f"{name}_fa{side_idx}", r=0.05, depth=0.20, segs=10, loc=(0, 0, -0.85),
            parent=sh, mat_=sk)
    # Head
    head_d_e = empty(f"{name}_he", (0, 0, 1.95), parent=base)
    smooth_sphere(f"{name}_h", r=0.17, segs=18, rings=14, loc=(0, 0, 0),
                  parent=head_d_e, mat_=sk)
    # MASK (signature half-face Mardi Gras)
    mask_e = empty(f"{name}_msk", (0, -0.16, 0.02), parent=head_d_e)
    mask_col = random.choice([M_MASK_GOLD, M_MASK_PURPLE])
    # Mask base (covers upper face)
    beveled_cube(f"{name}_msk_b", (0.32, 0.04, 0.18), bevel_offset=0.04,
                 loc=(0, 0, 0.04), parent=mask_e, mat_=mask_col)
    # Eye holes
    for side in (-1, 1):
        cyl(f"{name}_msk_e{side}", r=0.04, depth=0.10, segs=10,
            loc=(side*0.08, -0.02, 0.04), parent=mask_e, mat_=M_EYE).rotation_euler = (math.radians(90), 0, 0)
    # FEATHERS (signature top of mask)
    for fi in range(6):
        fa = (fi / 6.0 - 0.5) * math.radians(80)
        feather_col = random.choice([M_FEATHER_PURPLE, M_FEATHER_GOLD, M_FEATHER_GREEN])
        feather_e = empty(f"{name}_fe{fi}_e", (math.sin(fa)*0.10, 0, 0.20), parent=mask_e)
        feather_e.rotation_euler = (0, 0, fa)
        # Feather plume
        for fsi in range(6):
            beveled_cube(f"{name}_fe{fi}_p{fsi}", (0.04, 0.04, 0.12), bevel_offset=0.005,
                         loc=(0, 0, 0.10 + fsi*0.12), parent=feather_e, mat_=feather_col)
        # Feather barbs
        for fbi in range(8):
            for fbs in (-1, 1):
                beveled_cube(f"{name}_fe{fi}_b{fbi}_{fbs}", (0.06, 0.02, 0.04), bevel_offset=0.005,
                             loc=(fbs*0.06, 0, 0.15 + fbi*0.08), parent=feather_e, mat_=feather_col)
    # Side ribbons
    for side_r in (-1, 1):
        ribbon_e = empty(f"{name}_rb{side_r}", (side_r*0.20, 0, 0), parent=mask_e)
        for ri_b in range(6):
            beveled_cube(f"{name}_rb{side_r}_{ri_b}", (0.05, 0.03, 0.10), bevel_offset=0.005,
                         loc=(side_r*0.05 + math.sin(ri_b*0.3)*0.02, 0, -ri_b*0.12),
                         parent=ribbon_e, mat_=random.choice(MG_COLORS))
    # Hair (long curly)
    hair_col = random.choice([M_HAIR_BLACK, M_HAIR_BROWN])
    for hi in range(20):
        ha = random.uniform(math.pi*0.5, math.pi*1.5)
        hair_len = random.uniform(0.4, 0.7)
        for hsi in range(int(hair_len * 6)):
            cyl(f"{name}_hr{hi}_{hsi}", r=0.025, depth=0.10, segs=6,
                loc=(math.cos(ha)*0.15, math.sin(ha)*0.12, -hsi*0.10 - 0.05),
                parent=head_d_e, mat_=hair_col)
    # Lips
    beveled_cube(f"{name}_lp", (0.10, 0.04, 0.025), bevel_offset=0.005,
                 loc=(0, -0.16, -0.08), parent=head_d_e, mat_=M_LIPS_RED)
    base["_phase"] = random.uniform(0, math.pi*2)
    return {"root": base, "he": head_d_e, "skirt": skirt_e}

dancers = []
dancer_pos = [(-10, 5, math.radians(15)), (-3, 8, math.radians(0)),
               (3, 8, math.radians(0)), (10, 5, math.radians(-15))]
for i, (dx, dy, fac) in enumerate(dancer_pos):
    d = make_masked_dancer(f"mdc{i}", (dx, dy, 0), facing=fac)
    dancers.append(d)

# ============ MARDI GRAS FLOAT (signature parade) ============
float_e = empty("float", (0, 18, 0))
# Base platform
beveled_cube("ft_p", (8, 4, 0.8), bevel_offset=0.10, loc=(0, 0, 0.40),
             parent=float_e, mat_=M_FLOAT_PURPLE)
# Wheels
for side in (-1, 1):
    for fr in (-1, 1):
        wh_e = empty(f"ft_w{side}_{fr}", (fr*3, side*2, 0.40), parent=float_e)
        cyl(f"ft_wh{side}_{fr}", r=0.40, depth=0.30, segs=18, loc=(0, 0, 0), parent=wh_e,
            mat_=M_SUIT_BLACK).rotation_euler = (math.radians(90), 0, 0)
        cyl(f"ft_wr{side}_{fr}", r=0.20, depth=0.32, segs=14, loc=(0, 0, 0), parent=wh_e,
            mat_=M_FLOAT_GOLD).rotation_euler = (math.radians(90), 0, 0)
# Decorations (signature crown shape on top)
# Tower base
beveled_cube("ft_tb", (3, 2, 1.8), bevel_offset=0.10, loc=(0, 0, 1.70),
             parent=float_e, mat_=M_FLOAT_GOLD)
# Decorative stripes
for di in range(4):
    dz_f = 0.95 + di * 0.20
    color = MG_COLORS[di % 3]
    beveled_cube(f"ft_ds{di}", (8.1, 4.1, 0.10), bevel_offset=0.04,
                 loc=(0, 0, dz_f), parent=float_e, mat_=color)
# CROWN on top (signature)
crown_e = empty("ft_cr", (0, 0, 2.9), parent=float_e)
cyl("ft_cr_b", r=1.0, depth=0.40, segs=14, loc=(0, 0, 0), parent=crown_e, mat_=M_FLOAT_GOLD)
# Crown points
for cpi in range(8):
    cpa = (cpi / 8.0) * math.pi * 2
    smooth_cone(f"ft_cr_p{cpi}", r1=0.10, r2=0.04, depth=0.50, segs=8,
                loc=(math.cos(cpa)*0.85, math.sin(cpa)*0.85, 0.40),
                parent=crown_e, mat_=M_FLOAT_GOLD)
    # Jewel
    smooth_sphere(f"ft_cr_j{cpi}", r=0.10,
                  loc=(math.cos(cpa)*0.85, math.sin(cpa)*0.85, 0.65),
                  parent=crown_e, mat_=random.choice(MG_COLORS))
# Banner front
beveled_cube("ft_ba", (3.5, 0.10, 1.5), bevel_offset=0.06, loc=(0, -2.10, 1.50),
             parent=float_e, mat_=M_FLOAT_GREEN)
# Fleur de lys decoration (signature New Orleans)
fdl_e = empty("ft_fdl", (0, -2.20, 1.50), parent=float_e)
# Center petal
beveled_cube("ft_fdl_c", (0.10, 0.04, 0.50), bevel_offset=0.02, loc=(0, 0, 0.05),
             parent=fdl_e, mat_=M_FLOAT_GOLD)
# Side curls
for side_f in (-1, 1):
    fdl_p = empty(f"ft_fdl_s{side_f}", (side_f*0.10, 0, 0), parent=fdl_e)
    fdl_p.rotation_euler = (0, side_f*math.radians(30), 0)
    beveled_cube(f"ft_fdl_sp{side_f}", (0.08, 0.04, 0.40), bevel_offset=0.02,
                 loc=(0, 0, 0), parent=fdl_p, mat_=M_FLOAT_GOLD)
# Cross band
beveled_cube("ft_fdl_b", (0.40, 0.04, 0.08), bevel_offset=0.01, loc=(0, 0, -0.10),
             parent=fdl_e, mat_=M_FLOAT_GOLD)
float_e["_phase"] = 0

# ============ LOUISIANA FLAG with pelican (signature) ============
flag_e = empty("flag", (-32, 12, 0))
cyl("fl_p", r=0.10, depth=10, segs=10, loc=(0, 0, 5), parent=flag_e, mat_=M_GAS_METAL)
beveled_cube("fl_w", (3, 0.05, 2), bevel_offset=0.06, loc=(1.5, 0, 9),
             parent=flag_e, mat_=M_FLAG_BLUE)
# PELICAN signature
pel_e = empty("fl_pel", (1.5, -0.05, 9), parent=flag_e)
# Body
smooth_sphere("fl_pel_b", r=0.30, segs=14, rings=10, loc=(0, 0, 0),
              parent=pel_e, mat_=M_PELICAN_WHITE, scale=(1.4, 0.4, 1.0))
# Head
smooth_sphere("fl_pel_h", r=0.15, segs=12, rings=8, loc=(0.30, 0, 0.15),
              parent=pel_e, mat_=M_PELICAN_WHITE)
# Long beak (signature)
cyl("fl_pel_be", r=0.05, depth=0.40, segs=8, loc=(0.55, 0, 0.05),
    parent=pel_e, mat_=M_PELICAN_GOLD).rotation_euler = (0, math.radians(90), math.radians(-10))
# Pouch
smooth_sphere("fl_pel_po", r=0.10, segs=12, rings=8, loc=(0.45, 0, -0.05),
              parent=pel_e, mat_=M_PELICAN_GOLD)
# Wings
for side_p in (-1, 1):
    beveled_cube(f"fl_pel_w{side_p}", (0.04, 0.40, 0.20), bevel_offset=0.02,
                 loc=(0, 0.05, side_p*0.15), parent=pel_e, mat_=M_PELICAN_WHITE)
# 3 babies (signature in nest)
for bb in range(3):
    bba = (bb / 3.0 - 0.5) * math.radians(50)
    smooth_sphere(f"fl_pel_bb{bb}", r=0.08, segs=10, rings=8,
                  loc=(0 + math.sin(bba)*0.10, 0, -0.20 + math.cos(bba)*0.05),
                  parent=pel_e, mat_=M_PELICAN_WHITE)
flag_e["_phase"] = 0

# ============================================================
# 600 MARDI GRAS BEADS + 400 JAZZ NOTES (PARTICULES SIGNATURES)
# ============================================================
beads = []
for i in range(600):
    px = random.uniform(-50, 50)
    py = random.uniform(-40, 40)
    pz = random.uniform(2, 22)
    bead_e = empty(f"bd{i}", (px, py, pz))
    bead_col = random.choice(BEAD_COLORS)
    # Bead string with multiple beads (signature)
    for bi in range(12):
        bia = (bi / 12.0) * math.pi * 2
        smooth_sphere(f"bd{i}_b{bi}", r=0.05,
                      loc=(math.cos(bia)*0.20, math.sin(bia)*0.20, 0),
                      parent=bead_e, mat_=bead_col)
    bead_e["_phase"] = random.uniform(0, math.pi*2)
    bead_e["_base_x"] = px; bead_e["_base_z"] = pz
    bead_e["_drift"] = random.uniform(0.2, 0.6)
    bead_e["_fall"] = random.uniform(0.5, 1.3)
    bead_e["_swing"] = random.uniform(0.8, 1.8)
    beads.append(bead_e)

# 400 jazz notes
notes = []
for i in range(400):
    px = random.uniform(-55, 55)
    py = random.uniform(-40, 40)
    pz = random.uniform(2, 22)
    n_e = empty(f"no{i}", (px, py, pz))
    note_col = M_NOTE if i % 2 == 0 else M_NOTE_PURPLE
    # Note head
    smooth_sphere(f"no{i}_h", r=0.10, segs=12, rings=8, loc=(0, 0, 0),
                  parent=n_e, mat_=note_col, scale=(1, 0.6, 0.8))
    # Stem
    cyl(f"no{i}_s", r=0.012, depth=0.50, segs=6, loc=(0.08, 0, 0.25),
        parent=n_e, mat_=note_col)
    # Flag/swing
    if i % 3 == 0:
        beveled_cube(f"no{i}_f", (0.05, 0.03, 0.20), bevel_offset=0.005,
                     loc=(0.13, 0, 0.44), parent=n_e, mat_=note_col).rotation_euler = (0, math.radians(20), 0)
    n_e["_phase"] = random.uniform(0, math.pi*2)
    n_e["_base_x"] = px; n_e["_base_y"] = py; n_e["_base_z"] = pz
    n_e["_amp_x"] = random.uniform(0.8, 1.8)
    n_e["_amp_y"] = random.uniform(0.8, 1.8)
    n_e["_amp_z"] = random.uniform(0.5, 1.2)
    n_e["_speed"] = random.uniform(0.5, 1.3)
    notes.append(n_e)

# ============ ANIMATION ============
fps = 30; duration_s = 6; total_frames = fps * duration_s

# Jazz musicians play
for m in musicians:
    phase = m["root"]["_phase"]
    for f in range(1, total_frames + 1, 3):
        t = (f - 1) / fps
        m["root"].rotation_euler = (math.sin(t * 3.5 + phase) * math.radians(5), 0,
                                     m["root"].rotation_euler.z + math.sin(t * 1.5 + phase) * math.radians(5))
        m["root"].location.z = abs(math.sin(t * 3.0 + phase)) * 0.10
        m["root"].keyframe_insert("rotation_euler", frame=f)
        m["root"].keyframe_insert("location", frame=f)
        sc_m = 1 + math.sin(t * 7.0 + phase) * 0.08
        m["inst"].scale = (sc_m, sc_m, sc_m)
        m["inst"].keyframe_insert("scale", frame=f)
        m["he"].rotation_euler = (math.sin(t * 3.5 + phase) * math.radians(8), 0, 0)
        m["he"].keyframe_insert("rotation_euler", frame=f)

# Masked dancers spin
for d in dancers:
    phase = d["root"]["_phase"]
    fac = d["root"].rotation_euler.z
    for f in range(1, total_frames + 1, 3):
        t = (f - 1) / fps
        d["root"].rotation_euler = (math.sin(t * 2.5 + phase) * math.radians(6), 0,
                                     fac + math.sin(t * 1.5 + phase) * math.radians(30))
        d["root"].location.z = abs(math.sin(t * 3.0 + phase)) * 0.15
        d["root"].keyframe_insert("rotation_euler", frame=f)
        d["root"].keyframe_insert("location", frame=f)
        d["skirt"].rotation_euler = (0, 0, math.sin(t * 3.0 + phase) * math.radians(35))
        d["skirt"].keyframe_insert("rotation_euler", frame=f)
        d["he"].rotation_euler = (math.sin(t * 2.5 + phase) * math.radians(10), 0,
                                   math.cos(t * 2.0 + phase) * math.radians(20))
        d["he"].keyframe_insert("rotation_euler", frame=f)

# Float bob
for f in range(1, total_frames + 1, 4):
    t = (f - 1) / fps
    float_e.location.z = math.sin(t * 0.8) * 0.10
    float_e.rotation_euler = (math.sin(t * 0.8) * math.radians(2), 0, math.sin(t * 0.5) * math.radians(3))
    float_e.keyframe_insert("location", frame=f)
    float_e.keyframe_insert("rotation_euler", frame=f)

# Flag wave
for f in range(1, total_frames + 1, 5):
    t = (f - 1) / fps
    flag_e.rotation_euler = (0, 0, math.sin(t * 1.5) * math.radians(10))
    flag_e.keyframe_insert("rotation_euler", frame=f)

# 600 beads fall + sway
for b in beads:
    phase = b["_phase"]; drift = b["_drift"]; fall = b["_fall"]; swing = b["_swing"]
    bx, bz = b["_base_x"], b["_base_z"]
    for f in range(1, total_frames + 1, 4):
        t = (f - 1) / fps
        x = bx + math.sin(t * swing + phase) * 0.8 + t * drift
        z = bz - (t * fall) % 20
        b.location = (x, b.location.y, z)
        b.rotation_euler = (t * 2.0 + phase, math.sin(t * 2.5 + phase) * math.radians(30), t * 1.5 + phase)
        b.keyframe_insert("location", frame=f)
        b.keyframe_insert("rotation_euler", frame=f)

# 400 jazz notes float
for n in notes:
    phase = n["_phase"]; speed = n["_speed"]
    bx, by, bz = n["_base_x"], n["_base_y"], n["_base_z"]
    ax, ay, az = n["_amp_x"], n["_amp_y"], n["_amp_z"]
    for f in range(1, total_frames + 1, 4):
        t = (f - 1) / fps
        x = bx + ax * math.sin(t * speed + phase)
        y = by + ay * math.cos(t * speed * 0.9 + phase)
        z = bz + az * math.sin(t * speed * 1.2 + phase) + t * 0.6
        n.location = (x, y, z)
        n.rotation_euler = (math.sin(t * 2.5 + phase) * math.radians(20), 0,
                             t * 0.7 + phase)
        n.keyframe_insert("location", frame=f)
        n.keyframe_insert("rotation_euler", frame=f)

# ============ EXPORT ============
out_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "public", "_pbr_test")
out_dir = os.path.normpath(out_dir)
os.makedirs(out_dir, exist_ok=True)
out_glb = os.path.join(out_dir, "pbr_neworleans_proc.glb")

bpy.ops.object.select_all(action='SELECT')
bpy.ops.export_scene.gltf(
    filepath=out_glb, export_format='GLB',
    export_animations=True, export_apply=False, export_yup=True, use_selection=False,
)
size_mb = os.path.getsize(out_glb) / (1024 * 1024)
print(f"[proc_new_orleans_jazz_mardi_gras] DONE → {out_glb} ({size_mb:.2f} MB)")
print("New Orleans Bourbon Street: 8 French Quarter facades pastel + wrought iron continuous balconies + neon signs + 8 gas lamps with flame + 4 jazz musicians (trumpet/saxophone/trombone/tuba complete brass instruments) + 4 masked Mardi Gras dancers (gold/purple masks + feather plumes + colorful gowns + long gloves) + Mardi Gras float with crown + fleur de lys + Louisiana flag pelican with 3 babies signature + 600 beads + 400 jazz notes + 60 stars + moon")
print("🎷 FIXES: 1 cobblestone ground + 600 Mardi Gras beads (purple/gold/green strings) + 400 jazz notes (signature mandatory) 🎷")
