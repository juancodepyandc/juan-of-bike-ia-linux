"""
proc_cuban_havana_salsa_classic_cars.py — 268e procédural AuroraIA (133e qualité)
Cuba Havana salsa classic cars: pastel colonial facades + 4 vintage American cars 50s + 6 salsa dancers + 4 musicians (congas trumpet maracas guitar) + Cuban flag + Capitolio dome + 600 cigar smoke wisps + 400 salsa music notes
FIXES : 1 ground cobblestone + signature smoke + notes
"""
import bpy, bmesh, math, random, os

random.seed(0x70AB268)

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

# Sky tropical sunset Havana
M_SKY = mat("sky", (1.0, 0.60, 0.35, 1.0), 0.0, 0.7, emission=(1.0,0.60,0.35), emission_strength=2.0)
M_SKY_LOW = mat("sky_l", (0.85, 0.45, 0.55, 1.0), 0.0, 0.7, emission=(0.85,0.45,0.55), emission_strength=1.5)
M_SUN = mat("sun", (1.0, 0.80, 0.30, 1.0), 0.0, 0.1, emission=(1.0,0.80,0.30), emission_strength=20.0)

# Cobblestone ground
M_COBBLE = mat("co", (0.55, 0.50, 0.42, 1.0), 0.0, 0.85, emission=(0.55,0.50,0.42), emission_strength=0.3)
M_COBBLE_DARK = mat("cod", (0.32, 0.28, 0.22, 1.0), 0.0, 0.92)
M_STREET = mat("str", (0.42, 0.38, 0.32, 1.0), 0.0, 0.80)

# Pastel facade colors (Havana signature)
M_HAV_BLUE = mat("hb", (0.55, 0.80, 0.95, 1.0), 0.0, 0.65, emission=(0.55,0.78,0.92), emission_strength=0.6)
M_HAV_YELLOW = mat("hy", (1.0, 0.92, 0.65, 1.0), 0.0, 0.65, emission=(0.95,0.88,0.62), emission_strength=0.7)
M_HAV_PINK = mat("hp", (1.0, 0.75, 0.80, 1.0), 0.0, 0.65, emission=(0.95,0.72,0.78), emission_strength=0.6)
M_HAV_GREEN = mat("hg", (0.55, 0.85, 0.70, 1.0), 0.0, 0.65, emission=(0.55,0.82,0.68), emission_strength=0.6)
M_HAV_ORANGE = mat("ho", (1.0, 0.78, 0.55, 1.0), 0.0, 0.65, emission=(0.95,0.75,0.55), emission_strength=0.7)
M_HAV_CORAL = mat("hc", (0.95, 0.65, 0.55, 1.0), 0.0, 0.65, emission=(0.92,0.62,0.55), emission_strength=0.6)
M_HAV_PEACH = mat("hpe", (1.0, 0.82, 0.65, 1.0), 0.0, 0.65, emission=(0.95,0.78,0.62), emission_strength=0.7)
HAV_COLORS = [M_HAV_BLUE, M_HAV_YELLOW, M_HAV_PINK, M_HAV_GREEN, M_HAV_ORANGE, M_HAV_CORAL, M_HAV_PEACH]

# Window/door
M_WINDOW = mat("wd", (0.85, 0.75, 0.55, 1.0), 0.0, 0.35, emission=(0.85,0.75,0.55), emission_strength=3.0)
M_FRAME = mat("fr", (0.22, 0.15, 0.10, 1.0), 0.0, 0.75)
M_SHUTTER = mat("sh", (0.18, 0.40, 0.55, 1.0), 0.0, 0.65, emission=(0.18,0.40,0.55), emission_strength=0.4)
M_DOOR_WOOD = mat("dw", (0.35, 0.20, 0.12, 1.0), 0.0, 0.65)

# Iron balcony
M_IRON = mat("ir", (0.15, 0.12, 0.10, 1.0), 0.6, 0.40)

# Skin colors
M_SKIN_MED = mat("sm", (0.78, 0.55, 0.42, 1.0), 0.0, 0.55, emission=(0.75,0.55,0.42), emission_strength=0.3)
M_SKIN_DARK = mat("sd", (0.55, 0.35, 0.22, 1.0), 0.0, 0.55, emission=(0.52,0.35,0.22), emission_strength=0.3)
SKINS = [M_SKIN_MED, M_SKIN_DARK]

# Hair
M_HAIR_BLACK = mat("hbl", (0.08, 0.06, 0.05, 1.0), 0.0, 0.85)
M_HAIR_BROWN = mat("hbr", (0.32, 0.18, 0.08, 1.0), 0.0, 0.85)

# Salsa woman dress colorful
M_SALSA_RED = mat("sr", (0.92, 0.20, 0.30, 1.0), 0.0, 0.45, emission=(0.90,0.20,0.30), emission_strength=0.8)
M_SALSA_PINK = mat("sp", (1.0, 0.35, 0.55, 1.0), 0.0, 0.45, emission=(0.95,0.35,0.55), emission_strength=0.8)
M_SALSA_YELLOW = mat("sy", (1.0, 0.85, 0.20, 1.0), 0.0, 0.45, emission=(0.95,0.85,0.20), emission_strength=1.0)
M_SALSA_TURQ = mat("st", (0.20, 0.78, 0.78, 1.0), 0.0, 0.45, emission=(0.20,0.75,0.75), emission_strength=0.8)
SALSA_COLORS = [M_SALSA_RED, M_SALSA_PINK, M_SALSA_YELLOW, M_SALSA_TURQ]

# Man clothing
M_SHIRT_WHITE = mat("sw", (0.92, 0.90, 0.85, 1.0), 0.0, 0.35, emission=(0.88,0.86,0.82), emission_strength=0.4)
M_SHIRT_GUAYABERA = mat("sg", (0.92, 0.92, 0.88, 1.0), 0.0, 0.45, emission=(0.88,0.88,0.85), emission_strength=0.5)
M_PANTS_CREAM = mat("pc", (0.85, 0.75, 0.55, 1.0), 0.0, 0.55, emission=(0.82,0.72,0.55), emission_strength=0.3)
M_PANTS_BLACK = mat("pb", (0.08, 0.07, 0.07, 1.0), 0.1, 0.45)

# Hat
M_HAT_STRAW = mat("hs", (0.85, 0.72, 0.50, 1.0), 0.0, 0.65, emission=(0.82,0.70,0.50), emission_strength=0.4)
M_HAT_BLACK = mat("hbk", (0.08, 0.07, 0.07, 1.0), 0.0, 0.55)

# Shoes
M_SHOE = mat("sho", (0.18, 0.10, 0.08, 1.0), 0.3, 0.25)

# Eye/lips
M_EYE = mat("ed", (0.05, 0.04, 0.04, 1.0), 0.0, 0.20)
M_LIPS_RED = mat("lr", (0.85, 0.18, 0.20, 1.0), 0.0, 0.30, emission=(0.80,0.18,0.20), emission_strength=0.5)

# Classic American cars 1950s (signature)
M_CAR_PINK = mat("cp", (1.0, 0.55, 0.75, 1.0), 0.6, 0.20, emission=(0.95,0.55,0.72), emission_strength=0.6)
M_CAR_TURQ = mat("ct", (0.20, 0.78, 0.78, 1.0), 0.6, 0.20, emission=(0.20,0.75,0.75), emission_strength=0.5)
M_CAR_RED = mat("cr", (0.92, 0.20, 0.20, 1.0), 0.6, 0.20, emission=(0.90,0.20,0.20), emission_strength=0.5)
M_CAR_YELLOW = mat("cy", (1.0, 0.85, 0.20, 1.0), 0.6, 0.20, emission=(0.95,0.82,0.20), emission_strength=0.6)
CAR_COLORS = [M_CAR_PINK, M_CAR_TURQ, M_CAR_RED, M_CAR_YELLOW]
M_CHROME = mat("ch", (0.92, 0.92, 0.92, 1.0), 1.0, 0.05)
M_TIRE = mat("ti", (0.08, 0.07, 0.07, 1.0), 0.0, 0.85)
M_RIM = mat("rm", (0.92, 0.92, 0.92, 1.0), 1.0, 0.10)
M_GLASS_CAR = mat("gc", (0.30, 0.50, 0.65, 1.0), 0.0, 0.10, emission=(0.30,0.50,0.65), emission_strength=0.8, alpha=0.65)
M_HEADLIGHT = mat("hl", (1.0, 1.0, 0.85, 1.0), 0.5, 0.05, emission=(1.0,1.0,0.85), emission_strength=15.0)
M_BUMPER = mat("bp", (0.92, 0.92, 0.92, 1.0), 1.0, 0.10)

# Cuban flag
M_FLAG_BLUE = mat("fb", (0.18, 0.32, 0.65, 1.0), 0.0, 0.45, emission=(0.18,0.30,0.62), emission_strength=1.0)
M_FLAG_WHITE = mat("fw", (0.95, 0.95, 0.92, 1.0), 0.0, 0.45, emission=(0.92,0.92,0.90), emission_strength=0.8)
M_FLAG_RED = mat("fr2", (0.85, 0.15, 0.18, 1.0), 0.0, 0.45, emission=(0.82,0.15,0.18), emission_strength=1.0)
M_FLAG_STAR = mat("fs", (0.95, 0.95, 0.92, 1.0), 0.0, 0.20, emission=(0.92,0.92,0.88), emission_strength=4.0)

# Instruments
M_CONGA_WOOD = mat("cw", (0.55, 0.32, 0.15, 1.0), 0.0, 0.55, emission=(0.50,0.30,0.15), emission_strength=0.4)
M_CONGA_RED = mat("cr2", (0.92, 0.30, 0.25, 1.0), 0.0, 0.55, emission=(0.88,0.30,0.25), emission_strength=0.6)
M_CONGA_SKIN = mat("cs", (0.95, 0.85, 0.65, 1.0), 0.0, 0.55, emission=(0.92,0.82,0.65), emission_strength=0.4)
M_TRUMPET = mat("tr", (0.95, 0.78, 0.20, 1.0), 1.0, 0.15, emission=(0.92,0.75,0.20), emission_strength=0.5)
M_MARACA = mat("mc", (0.55, 0.32, 0.18, 1.0), 0.0, 0.55)
M_GUITAR_WOOD = mat("gw", (0.78, 0.55, 0.30, 1.0), 0.0, 0.35, emission=(0.75,0.55,0.30), emission_strength=0.5)
M_GUITAR_DARK = mat("gd", (0.32, 0.18, 0.08, 1.0), 0.0, 0.45)
M_STRING = mat("str", (0.85, 0.85, 0.85, 1.0), 0.5, 0.30)

# Cigar
M_CIGAR_BROWN = mat("cib", (0.32, 0.18, 0.10, 1.0), 0.0, 0.75)
M_CIGAR_TIP = mat("cit", (1.0, 0.55, 0.15, 1.0), 0.0, 0.20, emission=(1.0,0.55,0.15), emission_strength=6.0)

# Smoke wisp
M_SMOKE = mat("sm", (0.92, 0.90, 0.88, 1.0), 0.0, 0.95, emission=(0.92,0.90,0.88), emission_strength=1.0, alpha=0.45)
M_SMOKE_GRAY = mat("sg", (0.65, 0.62, 0.60, 1.0), 0.0, 0.95, emission=(0.65,0.62,0.60), emission_strength=0.5, alpha=0.40)

# Music note
M_NOTE = mat("n", (1.0, 0.45, 0.20, 1.0), 0.3, 0.20, emission=(0.95,0.45,0.20), emission_strength=2.5)
M_NOTE_HOT = mat("nh", (1.0, 0.85, 0.30, 1.0), 0.3, 0.20, emission=(0.95,0.82,0.30), emission_strength=3.0)

# Capitolio dome
M_CAPITOL = mat("ca", (0.85, 0.82, 0.78, 1.0), 0.0, 0.55, emission=(0.82,0.80,0.75), emission_strength=0.5)
M_CAPITOL_DOME = mat("cad", (0.55, 0.55, 0.55, 1.0), 0.5, 0.30, emission=(0.55,0.55,0.55), emission_strength=0.5)

# Palm
M_PALM_TRUNK = mat("pt", (0.55, 0.32, 0.15, 1.0), 0.0, 0.85, emission=(0.50,0.30,0.15), emission_strength=0.3)
M_PALM_LEAF = mat("pl", (0.30, 0.62, 0.25, 1.0), 0.0, 0.55, emission=(0.28,0.58,0.25), emission_strength=0.5)

# ============ SKY ============
sky = smooth_sphere("sky", r=280, segs=32, rings=20, loc=(0,0,0), mat_=M_SKY)
sky.scale = (1,1,0.6)
sky_l = smooth_sphere("sky_l", r=240, segs=28, rings=16, loc=(0,0,5), mat_=M_SKY_LOW)
sky_l.scale = (1,1,0.3)
# Sun
sun = smooth_sphere("sun", r=8, segs=24, rings=18, loc=(40, 90, 12), mat_=M_SUN)
for sh in range(3):
    smooth_sphere(f"sun_h{sh}", r=8 + sh*1, segs=24, rings=18, loc=(40, 90, 12), mat_=M_SUN)

# ============ ONE clean cobblestone ground ============
ground = beveled_cube("ground", (200, 200, 0.5), bevel_offset=0.10, loc=(0, 0, -0.25), mat_=M_STREET)
# Cobblestones
for cbi in range(60):
    for cbj in range(60):
        bx = -45 + cbi * 1.5
        by = -45 + cbj * 1.5
        if -42 < bx < 42 and -42 < by < 42 and random.random() > 0.25:
            smooth_sphere(f"cb{cbi}_{cbj}", r=0.45, segs=10, rings=6,
                          loc=(bx + random.uniform(-0.1, 0.1), by + random.uniform(-0.1, 0.1), 0.10),
                          mat_=M_COBBLE if (cbi + cbj) % 2 else M_COBBLE_DARK, scale=(1.4, 1.3, 0.18))

# ============ HAVANA COLONIAL FACADES (signature pastel) ============
def make_facade(name, loc, width, height, depth, mat_):
    base = empty(name, loc)
    # Main wall
    beveled_cube(f"{name}_w", (width, depth, height), bevel_offset=0.10,
                 loc=(0, 0, height/2), parent=base, mat_=mat_)
    # Windows with shutters
    win_rows = 2; win_cols = max(2, int(width / 3))
    for r in range(win_rows):
        for c in range(win_cols):
            wx = -width/2 + (c + 0.5) * (width / win_cols)
            wz = (r + 1) * (height / (win_rows + 1))
            # Frame
            beveled_cube(f"{name}_wf{r}_{c}", (1.0, 0.05, 1.4), bevel_offset=0.03,
                         loc=(wx, -depth/2 - 0.05, wz), parent=base, mat_=M_FRAME)
            # Glass
            beveled_cube(f"{name}_wg{r}_{c}", (0.85, 0.02, 1.25), bevel_offset=0.02,
                         loc=(wx, -depth/2 - 0.08, wz), parent=base, mat_=M_WINDOW)
            # Shutters (signature)
            for sd in (-1, 1):
                shutter = beveled_cube(f"{name}_sh{r}_{c}_{sd}", (0.42, 0.04, 1.35), bevel_offset=0.02,
                                         loc=(wx + sd*0.50, -depth/2 - 0.12, wz), parent=base, mat_=M_SHUTTER)
            # Balcony rail (signature)
            if r == 1:
                beveled_cube(f"{name}_bw{c}", (1.20, 0.5, 0.04), bevel_offset=0.02,
                             loc=(wx, -depth/2 - 0.30, wz - 0.75), parent=base, mat_=M_IRON)
                for bi in range(8):
                    bx_b = -0.55 + bi * 0.16
                    cyl(f"{name}_bb{c}_{bi}", r=0.018, depth=0.50, segs=6,
                        loc=(wx + bx_b, -depth/2 - 0.30, wz - 0.50), parent=base, mat_=M_IRON)
                for sd in (-1, 1):
                    cyl(f"{name}_brs{c}_{sd}", r=0.025, depth=0.55, segs=6,
                        loc=(wx + sd*0.60, -depth/2 - 0.30, wz - 0.48), parent=base, mat_=M_IRON)
    # Door
    beveled_cube(f"{name}_d", (1.2, 0.06, 2.4), bevel_offset=0.05,
                 loc=(0, -depth/2 - 0.05, 1.2), parent=base, mat_=M_DOOR_WOOD)
    # Cornice top
    beveled_cube(f"{name}_co", (width + 0.4, depth + 0.4, 0.30), bevel_offset=0.06,
                 loc=(0, 0, height + 0.15), parent=base, mat_=M_COBBLE)
    return base

# Left row facades
for i, (fx, fy, fw, fh) in enumerate([(-32, -25, 7, 8), (-32, -15, 7, 7), (-32, -5, 7, 9), (-32, 5, 7, 8), (-32, 15, 7, 7)]):
    make_facade(f"facL{i}", (fx, fy, 0), fw, fh, 3, random.choice(HAV_COLORS))
# Right row facades
for i, (fx, fy, fw, fh) in enumerate([(32, -25, 7, 7), (32, -15, 7, 8), (32, -5, 7, 9), (32, 5, 7, 7), (32, 15, 7, 8)]):
    fac = make_facade(f"facR{i}", (fx, fy, 0), fw, fh, 3, random.choice(HAV_COLORS))
    fac.rotation_euler = (0, 0, math.radians(180))

# ============ CAPITOLIO dome (signature distant landmark) ============
capitol_e = empty("capitol", (0, 60, 0))
# Main rectangular base
beveled_cube("cap_b", (20, 10, 8), bevel_offset=0.15, loc=(0, 0, 4), parent=capitol_e, mat_=M_CAPITOL)
# Columns front
for ci in range(8):
    cyl(f"cap_co{ci}", r=0.30, depth=6, segs=14, loc=(-7 + ci*2, -5.2, 3),
        parent=capitol_e, mat_=M_CAPITOL)
# Pediment
smooth_cone("cap_pe", r1=10, r2=8, depth=2, segs=14, loc=(0, -5.5, 9),
            parent=capitol_e, mat_=M_CAPITOL).rotation_euler = (math.radians(90), 0, 0)
# Drum (cylinder under dome)
cyl("cap_dr", r=4, depth=2, segs=22, loc=(0, 0, 9), parent=capitol_e, mat_=M_CAPITOL)
# Columned drum
for di in range(16):
    da = (di / 16.0) * math.pi * 2
    cyl(f"cap_dc{di}", r=0.20, depth=2.2, segs=10,
        loc=(math.cos(da)*4.2, math.sin(da)*4.2, 9), parent=capitol_e, mat_=M_CAPITOL)
# DOME (signature)
smooth_sphere("cap_d", r=4, segs=24, rings=18, loc=(0, 0, 11),
              parent=capitol_e, mat_=M_CAPITOL_DOME, scale=(1, 1, 0.8))
# Lantern
cyl("cap_l", r=0.8, depth=1.5, segs=14, loc=(0, 0, 14.5), parent=capitol_e, mat_=M_CAPITOL)
# Spire
smooth_cone("cap_sp", r1=0.8, r2=0.05, depth=2.5, segs=10, loc=(0, 0, 16.5),
            parent=capitol_e, mat_=M_CAPITOL_DOME)

# ============ 4 CLASSIC AMERICAN CARS 50s (signature) ============
def make_classic_car(name, loc, facing=0):
    base = empty(name, loc)
    base.rotation_euler = (0, 0, facing)
    car_col = random.choice(CAR_COLORS)
    # Main body (lower)
    beveled_cube(f"{name}_bo", (4.5, 1.7, 0.6), bevel_offset=0.15, loc=(0, 0, 0.55),
                 parent=base, mat_=car_col)
    # Hood front (rounded)
    beveled_cube(f"{name}_hd", (1.8, 1.6, 0.45), bevel_offset=0.20, loc=(1.5, 0, 0.95),
                 parent=base, mat_=car_col)
    # Trunk back (rounded)
    beveled_cube(f"{name}_tk", (1.4, 1.6, 0.45), bevel_offset=0.20, loc=(-1.6, 0, 0.95),
                 parent=base, mat_=car_col)
    # Cabin/roof
    beveled_cube(f"{name}_ca", (2.0, 1.5, 0.55), bevel_offset=0.15, loc=(0, 0, 1.35),
                 parent=base, mat_=car_col)
    # Roof glass (front windshield - tilted)
    front_w_e = empty(f"{name}_fwe", (0.8, 0, 1.35), parent=base)
    front_w_e.rotation_euler = (0, math.radians(-25), 0)
    beveled_cube(f"{name}_fw", (0.05, 1.45, 0.50), bevel_offset=0.04, loc=(0, 0, 0),
                 parent=front_w_e, mat_=M_GLASS_CAR)
    # Side glass
    for side in (-1, 1):
        beveled_cube(f"{name}_sw{side}", (1.7, 0.05, 0.45), bevel_offset=0.04,
                     loc=(0, side*0.76, 1.35), parent=base, mat_=M_GLASS_CAR)
    # Tail fins (signature 50s)
    for side in (-1, 1):
        fin_e = empty(f"{name}_fie{side}", (-1.8, side*0.70, 1.30), parent=base)
        beveled_cube(f"{name}_fi{side}", (0.40, 0.10, 0.45), bevel_offset=0.04, loc=(0, 0, 0),
                     parent=fin_e, mat_=car_col)
    # Chrome bumpers
    beveled_cube(f"{name}_b_f", (0.30, 1.7, 0.18), bevel_offset=0.05, loc=(2.40, 0, 0.50),
                 parent=base, mat_=M_BUMPER)
    beveled_cube(f"{name}_b_r", (0.30, 1.7, 0.18), bevel_offset=0.05, loc=(-2.20, 0, 0.50),
                 parent=base, mat_=M_BUMPER)
    # Headlights (round, signature)
    for side in (-1, 1):
        smooth_sphere(f"{name}_hl{side}", r=0.18, segs=14, rings=10,
                      loc=(2.40, side*0.55, 0.85), parent=base, mat_=M_HEADLIGHT)
    # Wheels with chrome rims
    wheel_pos = [(1.5, 0.85), (1.5, -0.85), (-1.5, 0.85), (-1.5, -0.85)]
    for wi, (wx, wy) in enumerate(wheel_pos):
        wh_e = empty(f"{name}_wh{wi}", (wx, wy, 0.40), parent=base)
        cyl(f"{name}_w{wi}", r=0.40, depth=0.30, segs=20, loc=(0, 0, 0), parent=wh_e,
            mat_=M_TIRE).rotation_euler = (math.radians(90), 0, 0)
        cyl(f"{name}_r{wi}", r=0.20, depth=0.32, segs=16, loc=(0, 0, 0), parent=wh_e,
            mat_=M_RIM).rotation_euler = (math.radians(90), 0, 0)
        # Hubcap
        smooth_sphere(f"{name}_hc{wi}", r=0.20, segs=14, rings=10, loc=(0, 0, 0),
                      parent=wh_e, mat_=M_CHROME, scale=(1, 1, 0.4))
        wh_e["_wheel"] = True
    # Grille
    for gri in range(8):
        cyl(f"{name}_g{gri}", r=0.02, depth=0.5, segs=6,
            loc=(2.40, -0.4 + gri*0.11, 0.65), parent=base, mat_=M_CHROME).rotation_euler = (math.radians(90), 0, 0)
    # Side trim (chrome strip)
    beveled_cube(f"{name}_tr_l", (4.2, 0.04, 0.05), bevel_offset=0.005, loc=(0, 0.85, 0.85),
                 parent=base, mat_=M_CHROME)
    beveled_cube(f"{name}_tr_r", (4.2, 0.04, 0.05), bevel_offset=0.005, loc=(0, -0.85, 0.85),
                 parent=base, mat_=M_CHROME)
    base["_phase"] = random.uniform(0, math.pi*2)
    return {"root": base, "color": car_col}

cars = []
car_pos = [(-15, -8, math.radians(0)), (15, -8, math.radians(180)),
            (-15, 20, math.radians(0)), (15, 20, math.radians(180))]
for i, (cx, cy, fac) in enumerate(car_pos):
    c = make_classic_car(f"car{i}", (cx, cy, 0), facing=fac)
    cars.append(c)

# ============ 6 SALSA DANCERS (signature) ============
def make_salsa_woman(name, loc, scale=1.0, facing=0):
    base = empty(name, loc)
    base.rotation_euler = (0, 0, facing)
    sk = random.choice(SKINS)
    # Salsa dress (short, colorful, ruffled)
    dress_col = random.choice(SALSA_COLORS)
    # Top
    smooth_cone(f"{name}_to", r1=0.28, r2=0.30, depth=0.5, segs=14, loc=(0, 0, 1.40),
                parent=base, mat_=dress_col)
    # Bare shoulders
    cyl(f"{name}_ch", r=0.28, depth=0.10, segs=14, loc=(0, 0, 1.70),
        parent=base, mat_=sk)
    # Skirt (signature ruffles)
    skirt_e = empty(f"{name}_sk", (0, 0, 1.15), parent=base)
    for ri in range(3):
        rz = -ri * 0.18
        rr = 0.32 + ri * 0.05
        for rj in range(20):
            rja = (rj / 20.0) * math.pi * 2
            beveled_cube(f"{name}_r{ri}_{rj}", (0.07, 0.10, 0.18), bevel_offset=0.01,
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
    # Arms (raised salsa)
    for side_idx, side in enumerate((-1, 1)):
        sh = empty(f"{name}_a{side_idx}", (side*0.30, 0, 1.65), parent=base)
        sh.rotation_euler = (math.radians(-130 if side_idx == 0 else -80), 0, math.radians(side*30))
        cyl(f"{name}_ua{side_idx}", r=0.06, depth=0.40, segs=10, loc=(0, 0, -0.20),
            parent=sh, mat_=sk)
        cyl(f"{name}_fa{side_idx}", r=0.05, depth=0.35, segs=10, loc=(0, 0, -0.55),
            parent=sh, mat_=sk)
    # Head
    head_w_e = empty(f"{name}_he", (0, 0, 1.95), parent=base)
    smooth_sphere(f"{name}_h", r=0.17, segs=18, rings=14, loc=(0, 0, 0),
                  parent=head_w_e, mat_=sk)
    # Hair (long curly)
    hair_col = random.choice([M_HAIR_BLACK, M_HAIR_BROWN])
    for hi in range(25):
        ha = random.uniform(0, math.pi*2)
        hair_len = random.uniform(0.5, 0.9)
        for hsi in range(int(hair_len * 6)):
            cyl(f"{name}_hr{hi}_{hsi}", r=0.025, depth=0.10, segs=6,
                loc=(math.cos(ha)*0.15 + math.sin(hsi*0.5)*0.03,
                     math.sin(ha)*0.15 + math.cos(hsi*0.5)*0.03,
                     -hsi*0.10 - 0.05),
                parent=head_w_e, mat_=hair_col)
    # Eyes
    for side in (-1, 1):
        smooth_sphere(f"{name}_ey{side}", r=0.025, loc=(side*0.06, -0.14, 0.03),
                      parent=head_w_e, mat_=M_EYE)
    # Lips
    beveled_cube(f"{name}_lp", (0.10, 0.04, 0.025), bevel_offset=0.005,
                 loc=(0, -0.16, -0.07), parent=head_w_e, mat_=M_LIPS_RED)
    # Flower in hair
    smooth_sphere(f"{name}_fl", r=0.07, loc=(0.13, 0.05, 0.10),
                  parent=head_w_e, mat_=random.choice(SALSA_COLORS))
    base["_phase"] = random.uniform(0, math.pi*2)
    return {"root": base, "he": head_w_e, "skirt": skirt_e}

def make_salsa_man(name, loc, scale=1.0, facing=0):
    base = empty(name, loc)
    base.rotation_euler = (0, 0, facing)
    sk = random.choice(SKINS)
    # Guayabera shirt (signature white)
    smooth_cone(f"{name}_sh", r1=0.32, r2=0.34, depth=0.85, segs=14, loc=(0, 0, 1.30),
                parent=base, mat_=M_SHIRT_GUAYABERA)
    # Vertical pleats (signature)
    for pli in range(4):
        plx = -0.18 + pli*0.12
        beveled_cube(f"{name}_pl{pli}", (0.04, 0.04, 0.80), bevel_offset=0.005,
                     loc=(plx, -0.34, 1.30), parent=base, mat_=M_SHIRT_WHITE)
    # Pants
    for side in (-1, 1):
        cyl(f"{name}_p{side}", r=0.11, depth=0.95, segs=10,
            loc=(side*0.13, 0, 0.45), parent=base, mat_=M_PANTS_CREAM)
    # Shoes
    for side in (-1, 1):
        beveled_cube(f"{name}_sh{side}", (0.13, 0.28, 0.06), bevel_offset=0.02,
                     loc=(side*0.13, 0, 0.03), parent=base, mat_=M_SHOE)
    # Arms (one extended, one on hip)
    sh_l = empty(f"{name}_a0", (-0.32, 0, 1.65), parent=base)
    sh_l.rotation_euler = (math.radians(-60), 0, math.radians(50))
    cyl(f"{name}_ua0", r=0.07, depth=0.40, segs=10, loc=(0, 0, -0.20),
        parent=sh_l, mat_=M_SHIRT_GUAYABERA)
    cyl(f"{name}_fa0", r=0.06, depth=0.35, segs=10, loc=(0, 0, -0.55),
        parent=sh_l, mat_=sk)
    sh_r = empty(f"{name}_a1", (0.32, 0, 1.65), parent=base)
    sh_r.rotation_euler = (math.radians(-90), 0, math.radians(-50))
    cyl(f"{name}_ua1", r=0.07, depth=0.40, segs=10, loc=(0, 0, -0.20),
        parent=sh_r, mat_=M_SHIRT_GUAYABERA)
    # Head
    head_m_e = empty(f"{name}_he", (0, 0, 1.95), parent=base)
    smooth_sphere(f"{name}_h", r=0.18, segs=18, rings=14, loc=(0, 0, 0),
                  parent=head_m_e, mat_=sk)
    # Hair
    for hi in range(15):
        ha = random.uniform(0, math.pi*2)
        cyl(f"{name}_hr{hi}", r=0.04, depth=0.10, segs=6,
            loc=(math.cos(ha)*0.12, math.sin(ha)*0.10, 0.15),
            parent=head_m_e, mat_=M_HAIR_BLACK)
    # STRAW HAT signature (Panama)
    if random.random() > 0.5:
        hat_e = empty(f"{name}_ha", (0, 0, 0.20), parent=head_m_e)
        cyl(f"{name}_ha_c", r=0.20, depth=0.16, segs=18, loc=(0, 0, 0),
            parent=hat_e, mat_=M_HAT_STRAW)
        cyl(f"{name}_ha_b", r=0.32, depth=0.04, segs=18, loc=(0, 0, -0.10),
            parent=hat_e, mat_=M_HAT_STRAW)
        # Black band
        cyl(f"{name}_ha_bd", r=0.21, depth=0.04, segs=18, loc=(0, 0, -0.05),
            parent=hat_e, mat_=M_HAT_BLACK)
    # Eyes
    for side in (-1, 1):
        smooth_sphere(f"{name}_ey{side}", r=0.025, loc=(side*0.06, -0.15, 0.03),
                      parent=head_m_e, mat_=M_EYE)
    # CIGAR signature
    cigar_e = empty(f"{name}_ci", (0.10, -0.20, -0.04), parent=head_m_e)
    cyl(f"{name}_ci_b", r=0.025, depth=0.18, segs=8, loc=(0, 0, 0),
        parent=cigar_e, mat_=M_CIGAR_BROWN).rotation_euler = (math.radians(90), 0, math.radians(20))
    smooth_sphere(f"{name}_ci_t", r=0.025, loc=(0.10, 0, 0),
                  parent=cigar_e, mat_=M_CIGAR_TIP)
    cigar_e["is_cigar"] = True
    base["_phase"] = random.uniform(0, math.pi*2)
    return {"root": base, "he": head_m_e, "cigar": cigar_e}

dancers = []
dancer_pairs = [
    ((-8, 0, math.radians(30)), (-6.5, 0, math.radians(210))),
    ((0, 5, math.radians(0)), (0, 6.5, math.radians(180))),
    ((8, 0, math.radians(-30)), (6.5, 0, math.radians(150)))
]
for pi, (wpos, mpos) in enumerate(dancer_pairs):
    w = make_salsa_woman(f"sw{pi}", (wpos[0], wpos[1], 0), facing=wpos[2])
    m = make_salsa_man(f"sm{pi}", (mpos[0], mpos[1], 0), facing=mpos[2])
    dancers.append({"w": w, "m": m})

# ============ 4 MUSICIANS (congas/trumpet/maracas/guitar) ============
def make_musician(name, loc, instrument, facing=0):
    base = empty(name, loc)
    base.rotation_euler = (0, 0, facing)
    sk = random.choice(SKINS)
    shirt_col = random.choice([M_SHIRT_GUAYABERA, M_SALSA_RED, M_SALSA_YELLOW])
    # Body
    smooth_cone(f"{name}_bo", r1=0.32, r2=0.34, depth=0.7, segs=14, loc=(0, 0, 1.20),
                parent=base, mat_=shirt_col)
    # Pants
    for side in (-1, 1):
        cyl(f"{name}_p{side}", r=0.11, depth=0.50, segs=10,
            loc=(side*0.28, 0.18, 0.70), parent=base, mat_=M_PANTS_BLACK).rotation_euler = (math.radians(80), 0, 0)
    # Head
    head_mu_e = empty(f"{name}_he", (0, 0, 1.85), parent=base)
    smooth_sphere(f"{name}_h", r=0.18, segs=18, rings=14, loc=(0, 0, 0),
                  parent=head_mu_e, mat_=sk)
    # Hair
    for hi in range(15):
        ha = random.uniform(0, math.pi*2)
        cyl(f"{name}_hr{hi}", r=0.04, depth=0.10, segs=6,
            loc=(math.cos(ha)*0.12, math.sin(ha)*0.10, 0.15),
            parent=head_mu_e, mat_=M_HAIR_BLACK)
    # Eyes
    for side in (-1, 1):
        smooth_sphere(f"{name}_ey{side}", r=0.025, loc=(side*0.06, -0.15, 0.03),
                      parent=head_mu_e, mat_=M_EYE)
    # Straw hat
    if random.random() > 0.3:
        hat_e = empty(f"{name}_ha", (0, 0, 0.20), parent=head_mu_e)
        cyl(f"{name}_ha_c", r=0.20, depth=0.16, segs=18, loc=(0, 0, 0),
            parent=hat_e, mat_=M_HAT_STRAW)
        cyl(f"{name}_ha_b", r=0.32, depth=0.04, segs=18, loc=(0, 0, -0.10),
            parent=hat_e, mat_=M_HAT_STRAW)
    # INSTRUMENT
    inst_e = empty(f"{name}_inst", (0, -0.40, 1.10), parent=base)
    if instrument == "congas":
        # 2 congas side by side
        for cgi, ox in enumerate((-0.28, 0.28)):
            cg = empty(f"{name}_cg{cgi}", (ox, 0, 0), parent=inst_e)
            smooth_cone(f"{name}_cg{cgi}_b", r1=0.18, r2=0.22, depth=0.85, segs=16,
                        loc=(0, 0, 0), parent=cg, mat_=M_CONGA_WOOD if cgi == 0 else M_CONGA_RED)
            cyl(f"{name}_cg{cgi}_s", r=0.20, depth=0.04, segs=16, loc=(0, 0, 0.45),
                parent=cg, mat_=M_CONGA_SKIN)
            # Tension lugs
            for li in range(6):
                la = (li / 6.0) * math.pi * 2
                cyl(f"{name}_cg{cgi}_l{li}", r=0.015, depth=0.10, segs=6,
                    loc=(math.cos(la)*0.20, math.sin(la)*0.20, 0.40),
                    parent=cg, mat_=M_CHROME)
    elif instrument == "trumpet":
        # Trumpet body (signature gold)
        cyl(f"{name}_t_b", r=0.04, depth=0.6, segs=10, loc=(0, 0, 0),
            parent=inst_e, mat_=M_TRUMPET).rotation_euler = (math.radians(90), 0, 0)
        # Bell flare
        smooth_cone(f"{name}_t_bl", r1=0.05, r2=0.18, depth=0.30, segs=16, loc=(0, 0.40, 0),
                    parent=inst_e, mat_=M_TRUMPET).rotation_euler = (math.radians(90), 0, 0)
        # Valves
        for vi in range(3):
            cyl(f"{name}_t_v{vi}", r=0.04, depth=0.15, segs=8,
                loc=(0, -0.10 + vi*0.10, 0.06), parent=inst_e, mat_=M_TRUMPET)
        # Mouthpiece
        cyl(f"{name}_t_m", r=0.03, depth=0.05, segs=8, loc=(0, -0.32, 0),
            parent=inst_e, mat_=M_CHROME).rotation_euler = (math.radians(90), 0, 0)
    elif instrument == "maracas":
        # 2 maracas
        for mki, ox in enumerate((-0.10, 0.10)):
            smooth_sphere(f"{name}_mk{mki}", r=0.10, segs=14, rings=10,
                          loc=(ox, 0, 0.15), parent=inst_e, mat_=M_MARACA)
            cyl(f"{name}_mkh{mki}", r=0.02, depth=0.20, segs=8,
                loc=(ox, 0, 0), parent=inst_e, mat_=M_MARACA)
    elif instrument == "guitar":
        # Guitar body
        smooth_sphere(f"{name}_g_b", r=0.22, segs=18, rings=14, loc=(0, 0, 0),
                      parent=inst_e, mat_=M_GUITAR_WOOD, scale=(0.85, 0.30, 1.2))
        # Hole
        cyl(f"{name}_g_h", r=0.07, depth=0.02, segs=12, loc=(0, -0.10, 0),
            parent=inst_e, mat_=M_GUITAR_DARK)
        # Neck
        cyl(f"{name}_g_n", r=0.025, depth=0.55, segs=10, loc=(0, -0.10, 0.45),
            parent=inst_e, mat_=M_GUITAR_DARK)
        # Strings
        for st in range(6):
            cyl(f"{name}_g_s{st}", r=0.003, depth=0.85, segs=6,
                loc=((st-2.5)*0.012, -0.13, 0.25), parent=inst_e, mat_=M_STRING)
    # Arms
    for side_idx, side in enumerate((-1, 1)):
        sh = empty(f"{name}_a{side_idx}", (side*0.30, 0, 1.55), parent=base)
        sh.rotation_euler = (math.radians(-90 if side_idx == 0 else -70), 0, 0)
        cyl(f"{name}_ua{side_idx}", r=0.06, depth=0.30, segs=10, loc=(0, 0, -0.15),
            parent=sh, mat_=shirt_col)
    base["_phase"] = random.uniform(0, math.pi*2)
    return {"root": base, "inst": inst_e}

musicians = []
mus_data = [("congas", -20, 10), ("trumpet", -8, 18), ("maracas", 8, 18), ("guitar", 20, 10)]
for i, (inst, mx, my) in enumerate(mus_data):
    m = make_musician(f"mus{i}", (mx, my, 0.6), instrument=inst, facing=math.radians(180))
    musicians.append(m)

# ============ CUBAN FLAG (signature) ============
flag_e = empty("flag", (-40, 0, 0))
cyl("fl_p", r=0.10, depth=10, segs=10, loc=(0, 0, 5), parent=flag_e, mat_=M_IRON)
# Flag with 5 stripes (3 blue + 2 white)
for si in range(5):
    sz = 8.0 + si * 0.50
    color = M_FLAG_BLUE if si % 2 == 0 else M_FLAG_WHITE
    beveled_cube(f"fl_s{si}", (3, 0.05, 0.50), bevel_offset=0.04, loc=(1.5, 0, sz),
                 parent=flag_e, mat_=color)
# Red triangle (signature)
for ti in range(8):
    tw = 1.5 - ti * 0.15
    beveled_cube(f"fl_t{ti}", (tw, 0.06, 0.30), bevel_offset=0.02,
                 loc=(tw/2 + 0.05, 0, 8.0 + ti*0.30), parent=flag_e, mat_=M_FLAG_RED)
# White star
star_e = empty("fl_st", (0.4, -0.08, 9.3), parent=flag_e)
for sp in range(5):
    spa = (sp / 5.0) * math.pi * 2 + math.pi/2
    beveled_cube(f"fl_sp{sp}", (0.04, 0.18, 0.04), bevel_offset=0.005,
                 loc=(math.cos(spa)*0.10, 0, math.sin(spa)*0.10),
                 parent=star_e, mat_=M_FLAG_STAR).rotation_euler = (spa - math.pi/2, 0, 0)
smooth_sphere("fl_stc", r=0.07, loc=(0, 0, 0), parent=star_e, mat_=M_FLAG_STAR)
flag_e["_phase"] = 0

# Palms
def make_palm(name, loc, lean=0):
    base = empty(name, loc)
    base.rotation_euler = (0, math.radians(lean), 0)
    for ti in range(10):
        tz = ti * 0.5
        cyl(f"{name}_t{ti}", r=0.16 - ti*0.005, depth=0.50, segs=10,
            loc=(math.sin(ti*0.3)*0.10, 0, tz + 0.25), parent=base, mat_=M_PALM_TRUNK)
    crown_e = empty(f"{name}_cr", (0, 0, 5.5), parent=base)
    for li in range(8):
        la = (li / 8.0) * math.pi * 2
        leaf_e = empty(f"{name}_le{li}", (0, 0, 0), parent=crown_e)
        leaf_e.rotation_euler = (math.radians(70), 0, la)
        cyl(f"{name}_lr{li}", r=0.02, depth=2.0, segs=8, loc=(0, 0, 1.0),
            parent=leaf_e, mat_=M_PALM_TRUNK)
        for sl in range(6):
            for ps in (-1, 1):
                beveled_cube(f"{name}_pn{li}_{sl}_{ps}", (0.03, 0.45, 0.04), bevel_offset=0.01,
                             loc=(ps*0.22, 0, sl*0.30 + 0.30), parent=leaf_e, mat_=M_PALM_LEAF)
    base["_phase"] = random.uniform(0, math.pi*2)
    return {"root": base, "crown": crown_e}

palms = []
for i, (px, py) in enumerate([(-35, -20), (35, -20), (-35, 20), (35, 20)]):
    palms.append(make_palm(f"palm{i}", (px, py, 0)))

# ============================================================
# 600 CIGAR SMOKE WISPS + 400 MUSIC NOTES (PARTICULES SIGNATURES)
# ============================================================
smoke_wisps = []
for i in range(600):
    # Concentrate around dancers/musicians (cigars)
    if i < 400:
        # Random near dancers
        px = random.uniform(-25, 25)
        py = random.uniform(-15, 25)
        pz = random.uniform(2, 18)
    else:
        # Scattered city
        px = random.uniform(-60, 60)
        py = random.uniform(-50, 50)
        pz = random.uniform(3, 22)
    s_col = M_SMOKE if i % 3 == 0 else M_SMOKE_GRAY
    s = smooth_sphere(f"sw{i}", r=random.uniform(0.10, 0.22), segs=10, rings=8,
                      loc=(px, py, pz), mat_=s_col, scale=(1.4, 1.4, 0.6))
    s["_phase"] = random.uniform(0, math.pi*2)
    s["_base_x"] = px; s["_base_y"] = py; s["_base_z"] = pz
    s["_drift_x"] = random.uniform(-0.5, 0.5)
    s["_drift_y"] = random.uniform(-0.5, 0.5)
    s["_rise"] = random.uniform(1.0, 2.5)
    s["_speed"] = random.uniform(0.5, 1.2)
    smoke_wisps.append(s)

# 400 music notes
notes = []
for i in range(400):
    px = random.uniform(-50, 50)
    py = random.uniform(-30, 30)
    pz = random.uniform(2, 20)
    n_e = empty(f"no{i}", (px, py, pz))
    note_col = M_NOTE if i % 2 == 0 else M_NOTE_HOT
    # Note head
    smooth_sphere(f"no{i}_h", r=0.10, segs=12, rings=8, loc=(0, 0, 0),
                  parent=n_e, mat_=note_col, scale=(1, 0.6, 0.8))
    # Stem
    cyl(f"no{i}_s", r=0.012, depth=0.50, segs=6, loc=(0.08, 0, 0.25),
        parent=n_e, mat_=note_col)
    # Flag
    if i % 3 == 0:
        beveled_cube(f"no{i}_f", (0.04, 0.03, 0.18), bevel_offset=0.005,
                     loc=(0.12, 0, 0.42), parent=n_e, mat_=note_col).rotation_euler = (0, math.radians(20), 0)
    n_e["_phase"] = random.uniform(0, math.pi*2)
    n_e["_base_x"] = px; n_e["_base_y"] = py; n_e["_base_z"] = pz
    n_e["_amp_x"] = random.uniform(0.6, 1.5)
    n_e["_amp_y"] = random.uniform(0.6, 1.5)
    n_e["_amp_z"] = random.uniform(0.4, 1.2)
    n_e["_speed"] = random.uniform(0.4, 1.0)
    notes.append(n_e)

# ============ ANIMATION ============
fps = 30; duration_s = 6; total_frames = fps * duration_s

# Cars bob
for c in cars:
    phase = c["root"]["_phase"]
    for f in range(1, total_frames + 1, 5):
        t = (f - 1) / fps
        c["root"].location.z = math.sin(t * 1.5 + phase) * 0.04
        c["root"].rotation_euler = (math.sin(t * 1.5 + phase) * math.radians(1.5), 0,
                                     c["root"].rotation_euler.z)
        c["root"].keyframe_insert("location", frame=f)
        c["root"].keyframe_insert("rotation_euler", frame=f)

# Salsa dancers spin/dip
for d in dancers:
    w = d["w"]; m = d["m"]
    phase_w = w["root"]["_phase"]; phase_m = m["root"]["_phase"]
    fac_w = w["root"].rotation_euler.z
    fac_m = m["root"].rotation_euler.z
    for f in range(1, total_frames + 1, 3):
        t = (f - 1) / fps
        # Woman spins hips
        w["root"].rotation_euler = (math.sin(t * 2.0 + phase_w) * math.radians(5), 0,
                                     fac_w + math.sin(t * 1.5 + phase_w) * math.radians(25))
        w["root"].keyframe_insert("rotation_euler", frame=f)
        # Skirt swirl
        w["skirt"].rotation_euler = (0, 0, math.sin(t * 2.5 + phase_w) * math.radians(30))
        w["skirt"].keyframe_insert("rotation_euler", frame=f)
        # Head sway
        w["he"].rotation_euler = (math.sin(t * 2.0 + phase_w) * math.radians(8), 0,
                                   math.cos(t * 1.5 + phase_w) * math.radians(20))
        w["he"].keyframe_insert("rotation_euler", frame=f)
        # Man
        m["root"].rotation_euler = (math.sin(t * 2.0 + phase_m) * math.radians(4), 0,
                                     fac_m + math.sin(t * 1.5 + phase_m) * math.radians(15))
        m["root"].keyframe_insert("rotation_euler", frame=f)
        m["he"].rotation_euler = (math.sin(t * 2.0 + phase_m) * math.radians(5), 0,
                                   math.cos(t * 1.5 + phase_m) * math.radians(10))
        m["he"].keyframe_insert("rotation_euler", frame=f)

# Musicians play
for m in musicians:
    phase = m["root"]["_phase"]
    for f in range(1, total_frames + 1, 3):
        t = (f - 1) / fps
        m["root"].rotation_euler = (math.sin(t * 3.5 + phase) * math.radians(5), 0,
                                     m["root"].rotation_euler.z)
        m["root"].keyframe_insert("rotation_euler", frame=f)
        sc_m = 1 + math.sin(t * 7.0 + phase) * 0.08
        m["inst"].scale = (sc_m, sc_m, sc_m)
        m["inst"].keyframe_insert("scale", frame=f)

# Palms sway
for p in palms:
    phase = p["root"]["_phase"]
    for f in range(1, total_frames + 1, 5):
        t = (f - 1) / fps
        p["crown"].rotation_euler = (math.sin(t * 0.8 + phase) * math.radians(6),
                                      math.cos(t * 0.8 + phase) * math.radians(6), 0)
        p["crown"].keyframe_insert("rotation_euler", frame=f)

# Flag wave
for f in range(1, total_frames + 1, 5):
    t = (f - 1) / fps
    flag_e.rotation_euler = (0, 0, math.sin(t * 1.5) * math.radians(10))
    flag_e.keyframe_insert("rotation_euler", frame=f)

# 600 smoke wisps rise + drift
for s in smoke_wisps:
    phase = s["_phase"]; speed = s["_speed"]; rise = s["_rise"]
    bx, by, bz = s["_base_x"], s["_base_y"], s["_base_z"]
    dx, dy = s["_drift_x"], s["_drift_y"]
    for f in range(1, total_frames + 1, 4):
        t = (f - 1) / fps
        x = bx + dx * t + math.sin(t * speed + phase) * 0.4
        y = by + dy * t + math.cos(t * speed * 0.9 + phase) * 0.4
        z = bz + (t * rise) % 14
        s.location = (x, y, z)
        sc_s = 1 + math.sin(t * 1.5 + phase) * 0.30 + t * 0.05
        s.scale = (sc_s * 1.4, sc_s * 1.4, sc_s * 0.6)
        s.keyframe_insert("location", frame=f)
        s.keyframe_insert("scale", frame=f)

# 400 notes float multi-axis
for n in notes:
    phase = n["_phase"]; speed = n["_speed"]
    bx, by, bz = n["_base_x"], n["_base_y"], n["_base_z"]
    ax, ay, az = n["_amp_x"], n["_amp_y"], n["_amp_z"]
    for f in range(1, total_frames + 1, 4):
        t = (f - 1) / fps
        x = bx + ax * math.sin(t * speed + phase)
        y = by + ay * math.cos(t * speed * 0.9 + phase)
        z = bz + az * math.sin(t * speed * 1.2 + phase) + t * 0.5
        n.location = (x, y, z)
        n.rotation_euler = (math.sin(t * 2.5 + phase) * math.radians(20), 0,
                             t * 0.8 + phase)
        n.keyframe_insert("location", frame=f)
        n.keyframe_insert("rotation_euler", frame=f)

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
out_glb = os.path.join(out_dir, "pbr_cuba_proc.glb")

bpy.ops.object.select_all(action='SELECT')
bpy.ops.export_scene.gltf(
    filepath=out_glb, export_format='GLB',
    export_animations=True, export_apply=False, export_yup=True, use_selection=False,
)
size_mb = os.path.getsize(out_glb) / (1024 * 1024)
print(f"[proc_cuban_havana_salsa_classic_cars] DONE → {out_glb} ({size_mb:.2f} MB)")
print("Cuba Havana: 10 pastel facades with shutters + iron balconies + Capitolio dome + 4 classic 1950s American cars (tail fins/chrome/headlights/hubcaps) + 6 salsa dancers (3 women ruffled dresses + 3 men guayabera straw hats cigars) + 4 musicians (congas/trumpet/maracas/guitar) + Cuban flag with star + palms + 600 cigar smoke + 400 salsa notes")
print("🚗 FIXES: 1 cobblestone ground + 600 cigar smoke + 400 music notes (signature Cuba mandatory) 🚗")
