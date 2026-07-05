"""
proc_antarctic_penguins_emperor_colony.py — 284e procédural AuroraIA (149e qualité)
Antarctic emperor penguin colony: 4 emperor adults + 6 baby chicks + 4 leopard seals + iceberg + polar research station + Antarctic flag + 600 polar snowflakes + 400 jumping baby penguins
FIXES : 1 ground snow ice + signature snowflakes + jumping penguins
"""
import bpy, bmesh, math, random, os

random.seed(0x70AB284)

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

# Polar sky
M_SKY = mat("sky", (0.55, 0.72, 0.85, 1.0), 0.0, 0.7, emission=(0.55,0.70,0.82), emission_strength=1.5)
M_SKY_LOW = mat("sky_l", (0.85, 0.92, 0.95, 1.0), 0.0, 0.7, emission=(0.85,0.90,0.95), emission_strength=1.3)
M_SUN_POLAR = mat("sun", (0.95, 0.92, 0.85, 1.0), 0.0, 0.1, emission=(0.92,0.90,0.82), emission_strength=12.0)
M_AURORA_GREEN = mat("ag", (0.18, 0.95, 0.45, 1.0), 0.0, 0.05, emission=(0.18,0.92,0.45), emission_strength=6.0, alpha=0.55)
M_AURORA_PURPLE = mat("ap", (0.55, 0.25, 0.85, 1.0), 0.0, 0.05, emission=(0.55,0.25,0.82), emission_strength=5.0, alpha=0.55)

# Snow/ice ground
M_SNOW = mat("sn", (0.95, 0.95, 0.95, 1.0), 0.0, 0.45, emission=(0.92,0.92,0.92), emission_strength=0.6)
M_SNOW_BLUE = mat("snb", (0.85, 0.92, 0.98, 1.0), 0.0, 0.35, emission=(0.82,0.92,0.95), emission_strength=0.8)
M_ICE = mat("ic", (0.78, 0.92, 0.98, 1.0), 0.0, 0.10, emission=(0.75,0.90,0.95), emission_strength=1.0)
M_ICE_BLUE = mat("ib", (0.45, 0.85, 0.95, 1.0), 0.0, 0.10, emission=(0.42,0.82,0.92), emission_strength=1.5)
M_ICE_DEEP = mat("idp", (0.30, 0.65, 0.85, 1.0), 0.0, 0.15, emission=(0.30,0.62,0.82), emission_strength=1.3)

# Penguin (signature emperor)
M_PENGUIN_BLACK = mat("pb", (0.10, 0.10, 0.12, 1.0), 0.0, 0.45, emission=(0.10,0.10,0.12), emission_strength=0.3)
M_PENGUIN_WHITE = mat("pw", (0.95, 0.95, 0.92, 1.0), 0.0, 0.45, emission=(0.92,0.92,0.90), emission_strength=0.5)
M_PENGUIN_YELLOW = mat("py", (1.0, 0.85, 0.20, 1.0), 0.0, 0.30, emission=(0.95,0.82,0.20), emission_strength=1.5)
M_PENGUIN_ORANGE = mat("po", (1.0, 0.55, 0.18, 1.0), 0.0, 0.40, emission=(0.95,0.55,0.18), emission_strength=1.2)
M_BEAK = mat("bk", (0.95, 0.78, 0.20, 1.0), 0.3, 0.30, emission=(0.92,0.75,0.20), emission_strength=0.7)
M_BEAK_DARK = mat("bkd", (0.45, 0.32, 0.15, 1.0), 0.2, 0.45)

# Baby chick (signature gray fluffy)
M_CHICK_GRAY = mat("cg", (0.65, 0.65, 0.65, 1.0), 0.0, 0.85, emission=(0.62,0.62,0.62), emission_strength=0.4)
M_CHICK_DARK = mat("cd", (0.32, 0.32, 0.32, 1.0), 0.0, 0.85)
M_CHICK_WHITE_FACE = mat("cwf", (0.92, 0.90, 0.88, 1.0), 0.0, 0.55, emission=(0.88,0.85,0.82), emission_strength=0.4)

# Leopard seal
M_SEAL_GRAY = mat("sg", (0.55, 0.62, 0.68, 1.0), 0.1, 0.55, emission=(0.55,0.62,0.68), emission_strength=0.3)
M_SEAL_DARK = mat("sd", (0.32, 0.38, 0.42, 1.0), 0.1, 0.65)
M_SEAL_SPOT = mat("ss", (0.15, 0.18, 0.20, 1.0), 0.0, 0.55)
M_SEAL_BELLY = mat("sbe", (0.85, 0.88, 0.92, 1.0), 0.0, 0.55, emission=(0.82,0.85,0.90), emission_strength=0.4)

# Iceberg
M_ICEBERG = mat("igb", (0.92, 0.95, 0.98, 1.0), 0.0, 0.15, emission=(0.88,0.92,0.95), emission_strength=1.0)
M_ICEBERG_BLUE = mat("igbb", (0.55, 0.85, 0.92, 1.0), 0.0, 0.10, emission=(0.52,0.82,0.90), emission_strength=1.4)
M_ICEBERG_DEEP = mat("igbd", (0.20, 0.55, 0.78, 1.0), 0.0, 0.15, emission=(0.18,0.52,0.75), emission_strength=1.0)
M_WATER_POLAR = mat("wp", (0.18, 0.42, 0.62, 1.0), 0.3, 0.10, emission=(0.18,0.42,0.62), emission_strength=1.5, alpha=0.78)

# Research station
M_STATION_RED = mat("str", (0.85, 0.25, 0.20, 1.0), 0.0, 0.55, emission=(0.82,0.25,0.20), emission_strength=0.7)
M_STATION_WHITE = mat("stw", (0.92, 0.92, 0.88, 1.0), 0.0, 0.55, emission=(0.88,0.88,0.85), emission_strength=0.5)
M_METAL = mat("me", (0.55, 0.55, 0.55, 1.0), 0.7, 0.30)
M_GLASS = mat("gl", (0.30, 0.55, 0.78, 1.0), 0.0, 0.10, emission=(0.30,0.55,0.78), emission_strength=2.5, alpha=0.55)
M_ANTENNA = mat("an", (0.42, 0.42, 0.45, 1.0), 0.8, 0.30)

# Eye
M_EYE = mat("ed", (0.05, 0.04, 0.04, 1.0), 0.0, 0.20)

# Antarctic flag
M_FLAG_BLUE = mat("fb", (0.10, 0.32, 0.65, 1.0), 0.0, 0.45, emission=(0.10,0.30,0.62), emission_strength=1.0)
M_FLAG_WHITE = mat("fw", (0.95, 0.95, 0.92, 1.0), 0.0, 0.45, emission=(0.92,0.92,0.90), emission_strength=0.8)

# Snowflakes (signature 6-point)
M_FLAKE_WHITE = mat("flw", (0.98, 0.98, 0.95, 1.0), 0.0, 0.20, emission=(0.95,0.95,0.92), emission_strength=2.5)
M_FLAKE_BLUE = mat("flb", (0.78, 0.92, 0.98, 1.0), 0.0, 0.20, emission=(0.75,0.90,0.95), emission_strength=2.3)

# ============ SKY ============
sky = smooth_sphere("sky", r=320, segs=32, rings=20, loc=(0,0,0), mat_=M_SKY)
sky.scale = (1,1,0.6)
sky_l = smooth_sphere("sky_l", r=280, segs=28, rings=16, loc=(0,0,5), mat_=M_SKY_LOW)
sky_l.scale = (1,1,0.3)
# Low sun (polar)
sun = smooth_sphere("sun", r=8, segs=24, rings=18, loc=(60, 100, 15), mat_=M_SUN_POLAR)
for sh in range(3):
    smooth_sphere(f"sun_h{sh}", r=8 + sh*1, segs=24, rings=18, loc=(60, 100, 15), mat_=M_SUN_POLAR)
# Aurora australis (signature)
for ai in range(10):
    ai_x = -120 + ai * 25
    aurora_e = empty(f"au{ai}_e", (ai_x, 100, 50))
    aurora_col = M_AURORA_GREEN if ai % 2 == 0 else M_AURORA_PURPLE
    for asi in range(6):
        beveled_cube(f"au{ai}_s{asi}", (2, 0.10, 0.30), bevel_offset=0.04,
                     loc=(0, 0, -asi*0.5 + math.sin(asi*0.5)*0.5),
                     parent=aurora_e, mat_=aurora_col)

# ============ ONE clean snow/ice ground ============
ground = beveled_cube("ground", (300, 300, 0.5), bevel_offset=0.10, loc=(0, 0, -0.25), mat_=M_SNOW)
# Snow drifts (organic 3D)
for hi in range(200):
    a = random.uniform(0, math.pi*2); rad = random.uniform(3, 140)
    smooth_sphere(f"hl{hi}", r=random.uniform(1.5, 3.5), segs=12, rings=8,
                  loc=(rad*math.cos(a), rad*math.sin(a), 0.15),
                  mat_=M_SNOW_BLUE if hi % 3 == 0 else M_SNOW, scale=(1.5, 1.4, 0.20))
# Ice patches (transparent)
for ii in range(50):
    a = random.uniform(0, math.pi*2); rad = random.uniform(30, 120)
    smooth_sphere(f"ic{ii}", r=random.uniform(1.0, 2.0), segs=10, rings=8,
                  loc=(rad*math.cos(a), rad*math.sin(a), 0.12),
                  mat_=M_ICE, scale=(1.4, 1.3, 0.18))
# Ice cracks (signature deep blue)
for ci in range(15):
    cx_c = random.uniform(-100, 100); cy_c = random.uniform(-100, 100)
    beveled_cube(f"ick{ci}", (random.uniform(2, 5), 0.20, 0.10), bevel_offset=0.04,
                 loc=(cx_c, cy_c, 0.15), mat_=M_ICE_DEEP).rotation_euler = (0, 0, random.uniform(0, math.pi))

# ============ MASSIVE ICEBERG (signature blue) ============
iceberg_e = empty("iceberg", (-60, 60, 0))
# Main berg above water
for bi in range(15):
    smooth_sphere(f"ig{bi}", r=random.uniform(4, 8), segs=14, rings=12,
                  loc=(random.uniform(-12, 12), random.uniform(-8, 8), random.uniform(5, 25)),
                  parent=iceberg_e, mat_=M_ICEBERG if bi % 2 else M_ICEBERG_BLUE,
                  scale=(1.3, 1.2, 0.85))
# Underwater portion (signature - blue submerged)
for bui in range(8):
    smooth_sphere(f"igu{bui}", r=random.uniform(5, 9), segs=14, rings=12,
                  loc=(random.uniform(-15, 15), random.uniform(-10, 10), random.uniform(-12, -2)),
                  parent=iceberg_e, mat_=M_ICEBERG_DEEP,
                  scale=(1.4, 1.3, 0.85))
# Ice cliff edge (signature jagged)
for ci_e in range(10):
    ca_e = (ci_e / 10.0) * math.pi * 2
    beveled_cube(f"ig_cl{ci_e}", (random.uniform(2, 4), 0.40, random.uniform(8, 15)), bevel_offset=0.12,
                 loc=(math.cos(ca_e)*13, math.sin(ca_e)*10, random.uniform(8, 14)),
                 parent=iceberg_e, mat_=M_ICEBERG_BLUE).rotation_euler = (0, 0, ca_e)

# ============ POLAR OCEAN beyond iceberg ============
ocean_e = empty("ocean", (60, 70, 0))
beveled_cube("oc", (100, 50, 0.20), bevel_offset=0.08, loc=(0, 0, 0.20),
             parent=ocean_e, mat_=M_WATER_POLAR)
# Floating ice chunks
for fci in range(15):
    fcx = random.uniform(-45, 45); fcy = random.uniform(-22, 22)
    smooth_sphere(f"oc_ic{fci}", r=random.uniform(0.6, 1.2), segs=10, rings=8,
                  loc=(fcx, fcy, 0.35), parent=ocean_e, mat_=M_ICEBERG, scale=(1.4, 1.3, 0.5))

# ============ 4 EMPEROR PENGUINS ADULTS (signature) ============
def make_emperor_penguin(name, loc, scale=1.0, facing=0):
    base = empty(name, loc)
    base.rotation_euler = (0, 0, facing)
    # Body (signature elongated vertical)
    smooth_sphere(f"{name}_bo", r=0.55, segs=14, rings=12, loc=(0, 0, 1.10),
                  parent=base, mat_=M_PENGUIN_BLACK, scale=(0.85, 0.85, 1.6))
    # WHITE BELLY (signature)
    smooth_sphere(f"{name}_be", r=0.50, segs=14, rings=12, loc=(0, -0.10, 1.05),
                  parent=base, mat_=M_PENGUIN_WHITE, scale=(0.85, 0.65, 1.5))
    # Head
    head_p_e = empty(f"{name}_he", (0, 0, 2.05), parent=base)
    smooth_sphere(f"{name}_h", r=0.30, segs=14, rings=12, loc=(0, 0, 0),
                  parent=head_p_e, mat_=M_PENGUIN_BLACK, scale=(0.85, 0.85, 1.0))
    # YELLOW NECK PATCH (signature emperor)
    smooth_sphere(f"{name}_ny", r=0.25, segs=12, rings=10, loc=(0, -0.15, -0.20),
                  parent=head_p_e, mat_=M_PENGUIN_YELLOW, scale=(0.85, 0.85, 1.2))
    # ORANGE EAR PATCH (signature emperor)
    for side in (-1, 1):
        smooth_sphere(f"{name}_eo{side}", r=0.08, segs=10, rings=8,
                      loc=(side*0.20, 0, 0.05), parent=head_p_e, mat_=M_PENGUIN_ORANGE)
    # Eyes (small black)
    for side in (-1, 1):
        smooth_sphere(f"{name}_ey{side}", r=0.025, loc=(side*0.10, -0.22, 0.05),
                      parent=head_p_e, mat_=M_EYE)
    # LONG CURVED BEAK (signature)
    beak_e = empty(f"{name}_be", (0.20, -0.20, -0.05), parent=head_p_e)
    cyl(f"{name}_be_t", r=0.04, depth=0.18, segs=10, loc=(0, 0, 0),
        parent=beak_e, mat_=M_BEAK_DARK).rotation_euler = (0, math.radians(95), 0)
    # Wing flippers (signature short)
    for side in (-1, 1):
        wing_e = empty(f"{name}_w{side}_e", (side*0.50, 0, 1.30), parent=base)
        wing_e.rotation_euler = (0, math.radians(side*5), math.radians(side*15))
        beveled_cube(f"{name}_w{side}", (0.10, 0.20, 0.95), bevel_offset=0.05,
                     loc=(side*0.05, 0, -0.10), parent=wing_e, mat_=M_PENGUIN_BLACK)
    # Feet (signature pink/orange)
    for side in (-1, 1):
        beveled_cube(f"{name}_f{side}", (0.10, 0.25, 0.06), bevel_offset=0.02,
                     loc=(side*0.10, 0.10, 0.03), parent=base, mat_=M_PENGUIN_ORANGE)
        # Toes
        for tt in range(3):
            beveled_cube(f"{name}_t{side}_{tt}", (0.04, 0.08, 0.03), bevel_offset=0.005,
                         loc=(side*0.10 + (tt-1)*0.05, 0.20, 0.02),
                         parent=base, mat_=M_PENGUIN_ORANGE)
    # Tail (short stubby)
    beveled_cube(f"{name}_tl", (0.20, 0.10, 0.10), bevel_offset=0.04,
                 loc=(0, 0.30, 0.45), parent=base, mat_=M_PENGUIN_BLACK)
    base["_phase"] = random.uniform(0, math.pi*2)
    return {"root": base, "he": head_p_e}

emperors = []
emperor_pos = [(-12, 0, math.radians(20)), (-4, 5, math.radians(0)),
                (4, 5, math.radians(0)), (12, 0, math.radians(-20))]
for i, (px, py, fac) in enumerate(emperor_pos):
    p = make_emperor_penguin(f"em{i}", (px, py, 0), facing=fac)
    emperors.append(p)

# ============ 6 BABY PENGUIN CHICKS (signature gray fluffy) ============
def make_chick(name, loc, scale=1.0, facing=0):
    base = empty(name, loc)
    base.rotation_euler = (0, 0, facing)
    # Round fluffy gray body (signature)
    smooth_sphere(f"{name}_bo", r=0.30, segs=14, rings=12, loc=(0, 0, 0.45),
                  parent=base, mat_=M_CHICK_GRAY, scale=(0.85, 0.85, 1.3))
    # Lighter belly
    smooth_sphere(f"{name}_be", r=0.25, segs=12, rings=10, loc=(0, -0.05, 0.40),
                  parent=base, mat_=M_CHICK_GRAY, scale=(0.85, 0.65, 1.2))
    # Head
    head_ch_e = empty(f"{name}_he", (0, 0, 0.85), parent=base)
    smooth_sphere(f"{name}_h", r=0.20, segs=14, rings=12, loc=(0, 0, 0),
                  parent=head_ch_e, mat_=M_CHICK_DARK)
    # WHITE FACE PATCH (signature emperor chick)
    smooth_sphere(f"{name}_fa", r=0.18, segs=12, rings=10, loc=(0, -0.06, 0),
                  parent=head_ch_e, mat_=M_CHICK_WHITE_FACE, scale=(0.85, 0.70, 0.85))
    # Beak (small dark)
    cyl(f"{name}_bk", r=0.025, depth=0.10, segs=8, loc=(0.15, -0.10, 0),
        parent=head_ch_e, mat_=M_BEAK_DARK).rotation_euler = (0, math.radians(95), 0)
    # Eyes
    for side in (-1, 1):
        smooth_sphere(f"{name}_ey{side}", r=0.020, loc=(side*0.06, -0.16, 0.03),
                      parent=head_ch_e, mat_=M_EYE)
    # Small wings (still fluffy)
    for side in (-1, 1):
        beveled_cube(f"{name}_w{side}", (0.08, 0.14, 0.40), bevel_offset=0.04,
                     loc=(side*0.28, 0, 0.50), parent=base, mat_=M_CHICK_GRAY)
    # Tiny feet
    for side in (-1, 1):
        beveled_cube(f"{name}_f{side}", (0.06, 0.15, 0.04), bevel_offset=0.01,
                     loc=(side*0.08, 0.08, 0.02), parent=base, mat_=M_PENGUIN_ORANGE)
    base["_phase"] = random.uniform(0, math.pi*2)
    return {"root": base, "he": head_ch_e}

chicks = []
chick_pos = [(-15, 12, math.radians(20)), (-7, 15, math.radians(0)),
              (0, 18, math.radians(0)), (7, 15, math.radians(0)),
              (15, 12, math.radians(-20)), (-3, 10, math.radians(30))]
for i, (cx_c, cy_c, fac) in enumerate(chick_pos):
    c = make_chick(f"ch{i}", (cx_c, cy_c, 0), facing=fac)
    chicks.append(c)

# ============ 4 LEOPARD SEALS (signature spotted) ============
def make_leopard_seal(name, loc, scale=1.0, facing=0):
    base = empty(name, loc)
    base.rotation_euler = (0, 0, facing)
    # Long elongated body (signature)
    smooth_sphere(f"{name}_bo", r=0.55, segs=14, rings=12, loc=(0, 0, 0.55),
                  parent=base, mat_=M_SEAL_GRAY, scale=(2.5, 0.85, 0.85))
    # Belly lighter
    smooth_sphere(f"{name}_be", r=0.50, segs=12, rings=10, loc=(0, 0, 0.35),
                  parent=base, mat_=M_SEAL_BELLY, scale=(2.3, 0.85, 0.45))
    # SPOTS (signature leopard)
    for spi in range(25):
        sa = random.uniform(0, math.pi*2)
        sc_x = random.uniform(-1.0, 1.0)
        sc_y = math.cos(sa) * 0.50
        sc_z = math.sin(sa) * 0.50 + 0.55
        smooth_sphere(f"{name}_sp{spi}", r=0.05, segs=8, rings=6,
                      loc=(sc_x, sc_y, sc_z), parent=base, mat_=M_SEAL_SPOT)
    # Head (signature wide reptilian)
    head_s_e = empty(f"{name}_he", (1.20, 0, 0.55), parent=base)
    smooth_sphere(f"{name}_h", r=0.32, segs=14, rings=12, loc=(0, 0, 0),
                  parent=head_s_e, mat_=M_SEAL_GRAY, scale=(1.5, 0.85, 0.75))
    # Snout
    smooth_sphere(f"{name}_sn", r=0.20, segs=12, rings=10, loc=(0.30, 0, -0.05),
                  parent=head_s_e, mat_=M_SEAL_DARK, scale=(1.3, 0.85, 0.65))
    # Big jaw (signature predator)
    beveled_cube(f"{name}_jw", (0.40, 0.30, 0.06), bevel_offset=0.02,
                 loc=(0.30, 0, -0.18), parent=head_s_e, mat_=M_SEAL_DARK)
    # Eyes (signature small dark)
    for side in (-1, 1):
        smooth_sphere(f"{name}_ey{side}", r=0.035, loc=(0.05, side*0.18, 0.10),
                      parent=head_s_e, mat_=M_EYE)
    # Whiskers
    for side in (-1, 1):
        for wi in range(4):
            cyl(f"{name}_w{side}_{wi}", r=0.005, depth=0.20, segs=4,
                loc=(0.40, side*0.10 + wi*0.02, -0.05 + wi*0.01),
                parent=head_s_e, mat_=M_FLAG_WHITE).rotation_euler = (0, math.radians(75), 0)
    # 2 front flippers (signature large)
    for side in (-1, 1):
        flipper_e = empty(f"{name}_fl{side}", (0.50, side*0.55, 0.30), parent=base)
        flipper_e.rotation_euler = (0, math.radians(20), math.radians(side*30))
        beveled_cube(f"{name}_flp{side}", (0.70, 0.30, 0.10), bevel_offset=0.05,
                     loc=(0.30, 0, 0), parent=flipper_e, mat_=M_SEAL_DARK)
    # Tail flippers
    for side in (-1, 1):
        beveled_cube(f"{name}_tfl{side}", (0.50, 0.25, 0.10), bevel_offset=0.05,
                     loc=(-1.30, side*0.20, 0.30), parent=base, mat_=M_SEAL_DARK)
    base["_phase"] = random.uniform(0, math.pi*2)
    return {"root": base, "he": head_s_e}

seals = []
seal_pos = [(-30, 25, math.radians(30)), (35, 30, math.radians(-30)),
             (-35, -20, math.radians(60)), (30, -25, math.radians(-60))]
for i, (sx_s, sy_s, fac) in enumerate(seal_pos):
    s = make_leopard_seal(f"sl{i}", (sx_s, sy_s, 0), facing=fac)
    seals.append(s)

# ============ POLAR RESEARCH STATION (signature) ============
station_e = empty("station", (45, -30, 0))
# Main station building (signature red elevated on stilts)
beveled_cube("st_b", (10, 6, 2.5), bevel_offset=0.10, loc=(0, 0, 4),
             parent=station_e, mat_=M_STATION_RED)
# Stilts (signature for snowdrifts)
for ssi in range(4):
    ssa = (ssi / 4.0) * math.pi * 2 + math.pi/4
    cyl(f"st_s{ssi}", r=0.20, depth=3, segs=10,
        loc=(math.cos(ssa)*4, math.sin(ssa)*2.5, 1.5), parent=station_e, mat_=M_METAL)
# Windows
for wi in range(6):
    wx = -4 + wi * 1.6
    beveled_cube(f"st_w{wi}", (0.8, 0.10, 0.8), bevel_offset=0.04,
                 loc=(wx, -3.05, 4.5), parent=station_e, mat_=M_GLASS)
# Roof
beveled_cube("st_r", (10.5, 6.5, 0.40), bevel_offset=0.08, loc=(0, 0, 5.4),
             parent=station_e, mat_=M_STATION_WHITE)
# Antenna mast
cyl("st_an", r=0.10, depth=4, segs=10, loc=(0, 0, 7.5), parent=station_e, mat_=M_ANTENNA)
# Antenna dishes
smooth_sphere("st_ad", r=0.40, segs=14, rings=10, loc=(0, 0, 9.0),
              parent=station_e, mat_=M_METAL, scale=(1, 1, 0.4))
# Solar panels on roof
for pi in range(3):
    beveled_cube(f"st_p{pi}", (2, 1.5, 0.10), bevel_offset=0.02,
                 loc=(-3 + pi*3, 1.5, 5.65), parent=station_e, mat_=M_GLASS).rotation_euler = (math.radians(-30), 0, 0)
# Steps
beveled_cube("st_st", (2, 1, 0.20), bevel_offset=0.04, loc=(0, -3.5, 2.5), parent=station_e, mat_=M_METAL)
beveled_cube("st_st2", (2, 1, 0.20), bevel_offset=0.04, loc=(0, -3.5, 2.0), parent=station_e, mat_=M_METAL)
beveled_cube("st_st3", (2, 1, 0.20), bevel_offset=0.04, loc=(0, -3.5, 1.5), parent=station_e, mat_=M_METAL)
# Door
beveled_cube("st_d", (1, 0.10, 1.5), bevel_offset=0.04, loc=(0, -3.05, 4.0),
             parent=station_e, mat_=M_STATION_WHITE)
# Station name plaque
beveled_cube("st_pl", (3, 0.06, 0.4), bevel_offset=0.02, loc=(0, -3.10, 5.0),
             parent=station_e, mat_=M_STATION_WHITE)

# ============ ANTARCTIC FLAG (signature blue with white continent) ============
flag_e = empty("flag", (-55, 30, 0))
cyl("fl_p", r=0.10, depth=12, segs=10, loc=(0, 0, 6), parent=flag_e, mat_=M_METAL)
# Blue field
beveled_cube("fl_b", (4, 0.05, 2.5), bevel_offset=0.06, loc=(2, 0, 10.5),
             parent=flag_e, mat_=M_FLAG_BLUE)
# WHITE ANTARCTIC CONTINENT SHAPE (signature simplified)
# Central blob
smooth_sphere("fl_co", r=0.60, segs=18, rings=14, loc=(2, -0.06, 10.5),
              parent=flag_e, mat_=M_FLAG_WHITE, scale=(1.5, 0.10, 1.2))
# Continent extensions
for ci in range(6):
    ca = (ci / 6.0) * math.pi * 2
    smooth_sphere(f"fl_co{ci}", r=random.uniform(0.20, 0.35), segs=14, rings=10,
                  loc=(2 + math.cos(ca)*0.6, -0.06, 10.5 + math.sin(ca)*0.4),
                  parent=flag_e, mat_=M_FLAG_WHITE, scale=(1.2, 0.10, 1.0))
flag_e["_phase"] = 0

# ============================================================
# 600 POLAR SNOWFLAKES + 400 JUMPING BABY PENGUINS (PARTICULES SIGNATURES)
# ============================================================
flakes = []
for i in range(600):
    px = random.uniform(-130, 130)
    py = random.uniform(-130, 130)
    pz = random.uniform(3, 35)
    flake_col = M_FLAKE_WHITE if i % 2 == 0 else M_FLAKE_BLUE
    flake_e = empty(f"sf{i}", (px, py, pz))
    # 6-point snowflake (signature)
    for sp in range(6):
        spa = (sp / 6.0) * math.pi * 2
        beveled_cube(f"sf{i}_p{sp}", (0.03, 0.10, 0.01), bevel_offset=0.005,
                     loc=(math.cos(spa)*0.06, math.sin(spa)*0.06, 0),
                     parent=flake_e, mat_=flake_col).rotation_euler = (0, 0, spa)
    # Center
    smooth_sphere(f"sf{i}_c", r=0.025, loc=(0, 0, 0), parent=flake_e, mat_=flake_col)
    # Side spurs (signature)
    for spu in range(6):
        spa = (spu / 6.0) * math.pi * 2
        for ss in (-1, 1):
            beveled_cube(f"sf{i}_sp{spu}_{ss}", (0.015, 0.04, 0.01), bevel_offset=0.005,
                         loc=(math.cos(spa)*0.10, math.sin(spa)*0.10 + ss*0.015, 0),
                         parent=flake_e, mat_=flake_col)
    flake_e["_phase"] = random.uniform(0, math.pi*2)
    flake_e["_base_x"] = px; flake_e["_base_z"] = pz
    flake_e["_drift"] = random.uniform(0.2, 0.5)
    flake_e["_fall"] = random.uniform(0.6, 1.4)
    flake_e["_swing"] = random.uniform(1.0, 2.0)
    flakes.append(flake_e)

# 400 jumping mini chicks
mini_chicks = []
for i in range(400):
    px = random.uniform(-110, 110)
    py = random.uniform(-110, 110)
    pz = 0.3
    mc_e = empty(f"mc{i}", (px, py, pz))
    # Tiny chick body
    smooth_sphere(f"mc{i}_bo", r=0.15, segs=10, rings=8, loc=(0, 0, 0),
                  parent=mc_e, mat_=M_CHICK_GRAY, scale=(0.85, 0.85, 1.2))
    # Head
    smooth_sphere(f"mc{i}_h", r=0.10, segs=8, rings=6, loc=(0, 0, 0.18),
                  parent=mc_e, mat_=M_CHICK_DARK)
    # White face
    smooth_sphere(f"mc{i}_fa", r=0.08, segs=8, rings=6, loc=(0, -0.04, 0.18),
                  parent=mc_e, mat_=M_CHICK_WHITE_FACE)
    # Beak
    cyl(f"mc{i}_bk", r=0.012, depth=0.05, segs=6, loc=(0.07, -0.04, 0.18),
        parent=mc_e, mat_=M_BEAK_DARK).rotation_euler = (0, math.radians(95), 0)
    # Tiny feet
    for side in (-1, 1):
        beveled_cube(f"mc{i}_f{side}", (0.03, 0.06, 0.02), bevel_offset=0.005,
                     loc=(side*0.04, 0.04, -0.10), parent=mc_e, mat_=M_PENGUIN_ORANGE)
    mc_e["_phase"] = random.uniform(0, math.pi*2)
    mc_e["_base_x"] = px; mc_e["_base_y"] = py
    mc_e["_speed"] = random.uniform(0.5, 1.0)
    mc_e["_jump_h"] = random.uniform(0.6, 1.5)
    mc_e["_direction"] = random.uniform(0, math.pi*2)
    mini_chicks.append(mc_e)

# ============ ANIMATION ============
fps = 30; duration_s = 6; total_frames = fps * duration_s

# Emperors sway (huddling)
for p in emperors:
    phase = p["root"]["_phase"]
    for f in range(1, total_frames + 1, 5):
        t = (f - 1) / fps
        p["root"].rotation_euler = (math.sin(t * 0.8 + phase) * math.radians(2), 0,
                                     p["root"].rotation_euler.z)
        p["root"].keyframe_insert("rotation_euler", frame=f)
        p["he"].rotation_euler = (math.sin(t * 0.8 + phase) * math.radians(3), 0,
                                   math.cos(t * 0.6 + phase) * math.radians(8))
        p["he"].keyframe_insert("rotation_euler", frame=f)

# Chicks wobble
for c in chicks:
    phase = c["root"]["_phase"]
    for f in range(1, total_frames + 1, 4):
        t = (f - 1) / fps
        c["root"].rotation_euler = (math.sin(t * 1.5 + phase) * math.radians(5), 0,
                                     c["root"].rotation_euler.z)
        c["root"].location.z = abs(math.sin(t * 2.0 + phase)) * 0.05
        c["root"].keyframe_insert("rotation_euler", frame=f)
        c["root"].keyframe_insert("location", frame=f)
        c["he"].rotation_euler = (math.sin(t * 1.5 + phase) * math.radians(10), 0,
                                   math.cos(t * 1.0 + phase) * math.radians(20))
        c["he"].keyframe_insert("rotation_euler", frame=f)

# Seals undulate
for s in seals:
    phase = s["root"]["_phase"]
    for f in range(1, total_frames + 1, 4):
        t = (f - 1) / fps
        s["root"].rotation_euler = (math.sin(t * 1.2 + phase) * math.radians(3), 0,
                                     s["root"].rotation_euler.z)
        s["root"].location.z = math.sin(t * 1.0 + phase) * 0.08
        s["root"].keyframe_insert("rotation_euler", frame=f)
        s["root"].keyframe_insert("location", frame=f)
        s["he"].rotation_euler = (0, math.sin(t * 1.2 + phase) * math.radians(8),
                                   math.cos(t * 1.0 + phase) * math.radians(15))
        s["he"].keyframe_insert("rotation_euler", frame=f)

# Flag wave
for f in range(1, total_frames + 1, 5):
    t = (f - 1) / fps
    flag_e.rotation_euler = (0, 0, math.sin(t * 1.5) * math.radians(10))
    flag_e.keyframe_insert("rotation_euler", frame=f)

# 600 snowflakes fall + sway
for sf in flakes:
    phase = sf["_phase"]; drift = sf["_drift"]; fall = sf["_fall"]; swing = sf["_swing"]
    bx, bz = sf["_base_x"], sf["_base_z"]
    for f in range(1, total_frames + 1, 4):
        t = (f - 1) / fps
        x = bx + math.sin(t * swing + phase) * 0.7 + t * drift
        z = bz - (t * fall) % 30
        sf.location = (x, sf.location.y, z)
        sf.rotation_euler = (t * 2.0 + phase, math.sin(t * 2.5 + phase) * math.radians(25), t * 1.5 + phase)
        sf.keyframe_insert("location", frame=f)
        sf.keyframe_insert("rotation_euler", frame=f)

# 400 mini chicks jump
for mc in mini_chicks:
    phase = mc["_phase"]; speed = mc["_speed"]; jh = mc["_jump_h"]; direction = mc["_direction"]
    bx, by = mc["_base_x"], mc["_base_y"]
    for f in range(1, total_frames + 1, 3):
        t = (f - 1) / fps
        x = bx + math.cos(direction) * t * speed
        y = by + math.sin(direction) * t * speed
        z = 0.3 + abs(math.sin(t * 4.0 + phase)) * jh
        mc.location = (x, y, z)
        mc.rotation_euler = (math.sin(t * 4.0 + phase) * math.radians(8), 0, direction)
        mc.keyframe_insert("location", frame=f)
        mc.keyframe_insert("rotation_euler", frame=f)

# ============ EXPORT ============
out_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "public", "_pbr_test")
out_dir = os.path.normpath(out_dir)
os.makedirs(out_dir, exist_ok=True)
out_glb = os.path.join(out_dir, "pbr_antarctic_proc.glb")

bpy.ops.object.select_all(action='SELECT')
bpy.ops.export_scene.gltf(
    filepath=out_glb, export_format='GLB',
    export_animations=True, export_apply=False, export_yup=True, use_selection=False,
)
size_mb = os.path.getsize(out_glb) / (1024 * 1024)
print(f"[proc_antarctic_penguins_emperor_colony] DONE → {out_glb} ({size_mb:.2f} MB)")
print("Antarctica: 4 Emperor penguins (signature black body + white belly + yellow neck patch + orange ear patches + long curved beak + wing flippers + pink/orange feet with toes) + 6 baby chicks (signature fluffy gray body + white face patch + small wings + tiny beak + tiny orange feet) + 4 leopard seals (signature long body + 25 spots + wide reptilian head + jaws + whiskers + 2 large flippers + tail flippers) + massive blue iceberg (above water + submerged blue portion + 10 jagged ice cliffs) + polar ocean with 15 floating ice chunks + research station with red building + 4 stilts + windows + antenna + solar panels + entrance steps + Antarctic flag (blue + white continent shape) + aurora australis arches green/purple + 600 polar snowflakes (signature 6-point + side spurs) + 400 jumping mini chicks")
print("🐧 FIXES: 1 snow ice ground + 600 6-point snowflakes + 400 jumping baby chicks signature 🐧")
