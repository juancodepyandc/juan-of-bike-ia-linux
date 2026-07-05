"""
proc_iceberg.py — 114e procédural AuroraIA, Phase F++++.

Iceberg massif dans océan polaire : masse de glace au-dessus (1/3 visible)
+ masse immergée (2/3 visible à travers l'eau) + 6 pingouins sur plateaux
+ 1 ours polaire sur sommet + 3 morceaux de glace flottants détachés
+ 8 oiseaux dans le ciel + océan bleu profond + reflets soleil
+ ciel polaire avec nuages.

Animation :
- iceberg sway lente sur Z (±2°)
- 6 pingouins frémissent (tilt sin)
- ours polaire respire (scale Y subtle)
- 8 oiseaux volent en cercle
- 3 glaces flottantes : bob + slow drift
- soleil reflets ondulent

Sortie : output/3d/pbr_iceberg_proc.glb.
"""
import bmesh
import bpy
import math
import os
import random

bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
scene.frame_start = 1
scene.frame_end = 180
scene.render.fps = 30

CWD = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.normpath(os.path.join(CWD, "..", "output", "3d", "pbr_iceberg_proc.glb"))

random.seed(0xCEBEE5)

# --- helpers ----------------------------------------------------------------

def make_mat(name, base, metallic=0.0, roughness=0.6, alpha=1.0, emi=(0, 0, 0), emi_strength=0.0):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes["Principled BSDF"]
    bsdf.inputs["Base Color"].default_value = (*base, 1.0)
    bsdf.inputs["Metallic"].default_value = metallic
    bsdf.inputs["Roughness"].default_value = roughness
    bsdf.inputs["Alpha"].default_value = alpha
    if "Emission Color" in bsdf.inputs:
        bsdf.inputs["Emission Color"].default_value = (*emi, 1.0)
    if "Emission Strength" in bsdf.inputs:
        bsdf.inputs["Emission Strength"].default_value = emi_strength
    if alpha < 1.0:
        mat.blend_method = 'BLEND'
    return mat


def add_obj(name, mesh, parent=None):
    o = bpy.data.objects.new(name, mesh)
    scene.collection.objects.link(o)
    if parent:
        o.parent = parent
    return o


def empty(name, location=(0, 0, 0), parent=None):
    e = bpy.data.objects.new(name, None)
    e.location = location
    scene.collection.objects.link(e)
    if parent:
        e.parent = parent
    return e


def cube(name, size=1.0, loc=(0, 0, 0), parent=None, mat=None):
    me = bpy.data.meshes.new(name)
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=size)
    bm.to_mesh(me)
    bm.free()
    o = add_obj(name, me, parent)
    o.location = loc
    if mat:
        me.materials.append(mat)
    return o


def sphere(name, r=1.0, segs=24, rings=12, loc=(0, 0, 0), parent=None, mat=None):
    me = bpy.data.meshes.new(name)
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=segs, v_segments=rings, radius=r)
    bm.to_mesh(me)
    bm.free()
    o = add_obj(name, me, parent)
    o.location = loc
    if mat:
        me.materials.append(mat)
    return o


def cone(name, r1=1.0, r2=0.0, depth=1.0, segs=24, loc=(0, 0, 0), parent=None, mat=None):
    me = bpy.data.meshes.new(name)
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, segments=segs, radius1=r1, radius2=r2, depth=depth, cap_ends=True)
    bm.to_mesh(me)
    bm.free()
    o = add_obj(name, me, parent)
    o.location = loc
    if mat:
        me.materials.append(mat)
    return o


# --- materials --------------------------------------------------------------
MAT_SKY_POLAR = make_mat("sky_polar", (0.78, 0.85, 0.95), roughness=1.0,
                          emi=(0.50, 0.65, 0.85), emi_strength=0.6)
MAT_CLOUD = make_mat("cloud", (0.95, 0.97, 1.0), roughness=1.0, alpha=0.9,
                      emi=(0.85, 0.92, 1.0), emi_strength=0.4)
MAT_SUN = make_mat("sun", (1.0, 0.95, 0.75), roughness=0.0,
                    emi=(1.0, 0.95, 0.7), emi_strength=6.0)
MAT_SUN_HALO = make_mat("sun_halo", (1.0, 0.95, 0.8), roughness=0.0, alpha=0.2,
                          emi=(1.0, 0.9, 0.7), emi_strength=2.0)
MAT_OCEAN = make_mat(
    "ocean", (0.05, 0.15, 0.30), metallic=0.85, roughness=0.08, alpha=0.95,
    emi=(0.10, 0.20, 0.35), emi_strength=0.4,
)
MAT_OCEAN_REFL = make_mat(
    "ocean_refl", (1.0, 0.85, 0.6), roughness=0.0, alpha=0.5,
    emi=(1.0, 0.85, 0.5), emi_strength=2.5,
)
MAT_ICE_TOP = make_mat(
    "ice_top", (0.92, 0.95, 1.0), metallic=0.05, roughness=0.4,
    emi=(0.7, 0.85, 1.0), emi_strength=0.5,
)
MAT_ICE_BLUE = make_mat(
    "ice_blue", (0.55, 0.78, 0.95), metallic=0.1, roughness=0.3, alpha=0.85,
    emi=(0.45, 0.70, 0.95), emi_strength=0.6,
)
MAT_ICE_UNDER = make_mat(
    "ice_under", (0.30, 0.55, 0.75), roughness=0.4, alpha=0.55,
    emi=(0.25, 0.50, 0.75), emi_strength=0.5,
)
MAT_PENGUIN_BODY = make_mat("penguin_body", (0.05, 0.05, 0.06), roughness=0.7)
MAT_PENGUIN_BELLY = make_mat("penguin_belly", (0.95, 0.95, 0.95), roughness=0.7)
MAT_PENGUIN_BEAK = make_mat("penguin_beak", (0.90, 0.55, 0.10), roughness=0.6)
MAT_PENGUIN_EYE = make_mat("penguin_eye", (0.05, 0.05, 0.05), roughness=0.2,
                             emi=(0.05, 0.05, 0.05), emi_strength=0.0)
MAT_BEAR_BODY = make_mat("bear_body", (0.95, 0.96, 0.98), roughness=0.85)
MAT_BEAR_NOSE = make_mat("bear_nose", (0.08, 0.07, 0.07), roughness=0.6)
MAT_BIRD = make_mat("bird", (0.20, 0.20, 0.22), roughness=0.7)

# --- backdrop ---------------------------------------------------------------
sky = cube("sky_back", size=1.0, loc=(0, 16, 6), mat=MAT_SKY_POLAR)
sky.scale = (28, 0.1, 14)

# 5 clouds
for i in range(5):
    cx = -10 + i * 5 + random.uniform(-1, 1)
    cz = 9.5 + random.uniform(-1, 1)
    cy = 14.5 + random.uniform(-0.5, 0.5)
    c = sphere(f"cloud_{i}", r=random.uniform(1.0, 1.6), segs=16, rings=10, loc=(cx, cy, cz), mat=MAT_CLOUD)
    c.scale = (1.5, 0.5, 1.0)

# sun + halo
sun_p = empty("sun_p", (5.5, 13.5, 9.0))
sun = sphere("sun", r=0.7, segs=20, rings=14, loc=(0, 0, 0), parent=sun_p, mat=MAT_SUN)
sun_halo = sphere("sun_halo", r=1.3, segs=18, rings=12, loc=(0, 0, 0), parent=sun_p, mat=MAT_SUN_HALO)

# --- ocean surface ----------------------------------------------------------
ocean = cube("ocean_surface", size=1.0, loc=(0, 0, 0), mat=MAT_OCEAN)
ocean.scale = (30, 0.05, 22)

# sun reflection (5 horizontal strips on water under sun)
refl_strips = []
for i in range(7):
    r_y = 0.05
    r_z = 5.0 + i * 1.2
    r_x = 5.5  # under sun
    w = 1.5 - i * 0.15
    rs = cube(f"sun_refl_{i}", size=1.0, loc=(r_x, r_y, r_z), mat=MAT_OCEAN_REFL)
    rs.scale = (w, 0.05, 0.25)
    refl_strips.append((rs, i))

# --- main iceberg : irregular icy mass --------------------------------------
iceberg_pivot = empty("iceberg", (0, 0, 0))

# top portion (above waterline) — stacked cones + cubes for irregularity
# main peak
peak = cone("ice_peak", r1=2.5, r2=0.8, depth=4.5, segs=8, loc=(0, 2.3, 0), parent=iceberg_pivot, mat=MAT_ICE_TOP)
peak.rotation_euler = (math.radians(90), 0, math.radians(15))

# secondary peak (left)
peak2 = cone("ice_peak2", r1=1.5, r2=0.4, depth=3.0, segs=8, loc=(-1.8, 1.6, 0.4), parent=iceberg_pivot, mat=MAT_ICE_TOP)
peak2.rotation_euler = (math.radians(90), 0, math.radians(-25))

# plateau (lower right)
plat = cube("ice_plateau", size=1.0, loc=(2.0, 0.9, 0.5), parent=iceberg_pivot, mat=MAT_ICE_TOP)
plat.scale = (1.6, 0.5, 1.2)
plat.rotation_euler = (0, 0, math.radians(-8))

# secondary plateau for penguins (middle level)
plat2 = cube("ice_plateau2", size=1.0, loc=(-1.0, 1.3, 0.8), parent=iceberg_pivot, mat=MAT_ICE_TOP)
plat2.scale = (1.0, 0.3, 0.8)
plat2.rotation_euler = (0, 0, math.radians(6))

# ice waterline ring (lighter blue at waterline)
for i in range(5):
    a = i * (math.pi * 2 / 5)
    wx = math.cos(a) * 2.8
    wz = math.sin(a) * 2.2
    wr = sphere(f"waterline_{i}", r=0.6, segs=14, rings=10, loc=(wx, 0.15, wz), parent=iceberg_pivot, mat=MAT_ICE_BLUE)
    wr.scale = (1.4, 0.3, 1.0)

# submerged portion (visible through alpha water) — under y=0
under1 = sphere("ice_under1", r=3.5, segs=20, rings=14, loc=(0, -2.2, 0), parent=iceberg_pivot, mat=MAT_ICE_UNDER)
under1.scale = (1.4, 1.5, 1.2)

under2 = sphere("ice_under2", r=2.0, segs=18, rings=12, loc=(-1.5, -4.0, 0.5), parent=iceberg_pivot, mat=MAT_ICE_UNDER)
under2.scale = (1.2, 1.6, 1.0)

under3 = cone("ice_under_keel", r1=1.0, r2=2.0, depth=3.5, segs=12, loc=(0.8, -5.5, -0.3), parent=iceberg_pivot, mat=MAT_ICE_UNDER)
under3.rotation_euler = (math.radians(90), 0, math.radians(10))

# --- 6 penguins on plateaus -------------------------------------------------
def make_penguin(name, x, y, z, scale=1.0, parent=None, rot_y=0.0):
    pp = empty(name, (x, y, z), parent=parent)
    pp.rotation_euler = (0, rot_y, 0)
    body = sphere(f"{name}_body", r=0.18 * scale, segs=14, rings=10, loc=(0, 0.18 * scale, 0), parent=pp, mat=MAT_PENGUIN_BODY)
    body.scale = (1.0, 1.4, 0.9)
    belly = sphere(f"{name}_belly", r=0.13 * scale, segs=12, rings=10, loc=(0, 0.15 * scale, 0.06 * scale), parent=pp, mat=MAT_PENGUIN_BELLY)
    belly.scale = (1.0, 1.3, 0.5)
    head = sphere(f"{name}_head", r=0.10 * scale, segs=12, rings=10, loc=(0, 0.40 * scale, 0), parent=pp, mat=MAT_PENGUIN_BODY)
    beak = cone(f"{name}_beak", r1=0.04 * scale, r2=0.01 * scale, depth=0.10 * scale, segs=8, loc=(0, 0.40 * scale, 0.10 * scale), parent=pp, mat=MAT_PENGUIN_BEAK)
    beak.rotation_euler = (math.radians(90), 0, 0)
    # 2 small eyes
    for dx in (-0.04, 0.04):
        e = sphere(f"{name}_eye_{dx}", r=0.012 * scale, segs=6, rings=4, loc=(dx * scale, 0.42 * scale, 0.08 * scale), parent=pp, mat=MAT_PENGUIN_EYE)
    # 2 wings (small flat ovals on sides)
    for side, x_off in (("L", -0.13), ("R", 0.13)):
        w = sphere(f"{name}_wing_{side}", r=0.06 * scale, segs=10, rings=8, loc=(x_off * scale, 0.18 * scale, 0), parent=pp, mat=MAT_PENGUIN_BODY)
        w.scale = (0.4, 1.3, 0.8)
    # 2 small feet (orange flat cubes)
    for fx in (-0.05, 0.05):
        ft = cube(f"{name}_foot_{fx}", size=1.0, loc=(fx * scale, 0.02 * scale, 0.10 * scale), parent=pp, mat=MAT_PENGUIN_BEAK)
        ft.scale = (0.04, 0.02, 0.06)
    return pp

# 6 penguins on different surfaces
penguins = []
penguin_locs = [
    ( 1.6, 1.40, 0.6, 0.0),   # on plat
    ( 2.4, 1.40, 0.3, 0.3),
    ( 1.9, 1.40,-0.1, 1.2),
    (-1.0, 1.60, 0.8, 2.5),   # on plat2
    (-0.5, 1.60, 0.5, 1.8),
    ( 0.5, 5.8, 0.0, 0.5),    # on peak top
]
for i, (px, py, pz, ry) in enumerate(penguin_locs):
    p = make_penguin(f"penguin_{i}", px, py, pz, scale=0.9 if i == 5 else 1.0, parent=iceberg_pivot, rot_y=ry)
    penguins.append(p)

# --- polar bear on the secondary plateau -----------------------------------
bear_p = empty("bear", (-1.0, 1.45, 0.8), parent=iceberg_pivot)
bear_body = sphere("bear_body", r=0.35, segs=14, rings=10, loc=(0, 0.18, 0), parent=bear_p, mat=MAT_BEAR_BODY)
bear_body.scale = (1.4, 0.8, 1.0)
bear_head = sphere("bear_head", r=0.18, segs=14, rings=10, loc=(0.45, 0.22, 0), parent=bear_p, mat=MAT_BEAR_BODY)
bear_head.scale = (1.0, 0.9, 1.0)
bear_nose = sphere("bear_nose", r=0.04, segs=8, rings=6, loc=(0.62, 0.20, 0), parent=bear_p, mat=MAT_BEAR_NOSE)
# 2 ears
for dy, dz in [(0.32, 0.10), (0.32, -0.10)]:
    e = sphere(f"bear_ear_{dz}", r=0.05, segs=8, rings=6, loc=(0.45, dy, dz), parent=bear_p, mat=MAT_BEAR_BODY)
# 4 legs
for x_off, z_off in [(0.20, 0.18), (0.20, -0.18), (-0.20, 0.18), (-0.20, -0.18)]:
    leg = cube(f"bear_leg_{x_off}_{z_off}", size=1.0, loc=(x_off, 0.0, z_off), parent=bear_p, mat=MAT_BEAR_BODY)
    leg.scale = (0.08, 0.15, 0.08)

# --- 3 ice floes around (detached pieces) ----------------------------------
floes = []
for i, (fx, fz) in enumerate([(5.5, 4.0), (-7.0, 3.5), (8.0, -3.5)]):
    fp = empty(f"floe_{i}", (fx, 0, fz))
    base = cube(f"floe_{i}_base", size=1.0, loc=(0, 0.2, 0), parent=fp, mat=MAT_ICE_TOP)
    base.scale = (1.2 + random.uniform(-0.2, 0.4), 0.25, 0.8 + random.uniform(-0.1, 0.3))
    # bump on top
    bump = sphere(f"floe_{i}_bump", r=0.4, segs=14, rings=10, loc=(0, 0.45, 0), parent=fp, mat=MAT_ICE_TOP)
    bump.scale = (0.8, 0.5, 0.6)
    # underwater piece (visible through water)
    underp = sphere(f"floe_{i}_under", r=0.7, segs=14, rings=10, loc=(0, -0.5, 0), parent=fp, mat=MAT_ICE_UNDER)
    underp.scale = (1.3, 1.4, 1.0)
    floes.append(fp)

# --- 8 birds flying in the sky --------------------------------------------
birds = []
for i in range(8):
    a = i * (math.pi * 2 / 8) + 0.4
    r = 5.5 + random.uniform(-0.5, 0.5)
    bx = math.cos(a) * r
    bz = math.sin(a) * r
    by = 8.0 + random.uniform(-1.0, 1.0)
    bp = empty(f"bird_{i}", (bx, by, bz))
    # simple bird : tiny body + 2 wings (slim cubes)
    body = sphere(f"bird_{i}_body", r=0.10, segs=8, rings=6, loc=(0, 0, 0), parent=bp, mat=MAT_BIRD)
    body.scale = (1.0, 0.6, 1.4)
    for side, x_off in (("L", -0.25), ("R", 0.25)):
        w = cube(f"bird_{i}_wing_{side}", size=1.0, loc=(x_off, 0, 0), parent=bp, mat=MAT_BIRD)
        w.scale = (0.20, 0.02, 0.10)
    birds.append((bp, a, r, by))

# --- animation --------------------------------------------------------------

def kf_loc(o, f, l):
    o.location = l
    o.keyframe_insert(data_path="location", frame=f)


def kf_scale(o, f, s):
    o.scale = s
    o.keyframe_insert(data_path="scale", frame=f)


def kf_rot(o, f, r):
    o.rotation_euler = r
    o.keyframe_insert(data_path="rotation_euler", frame=f)


FRAMES = 180

# iceberg slow sway and gentle bob
for f in range(1, FRAMES + 1, 3):
    tt = (f - 1) / (FRAMES - 1)
    rot = math.radians(2.0) * math.sin(tt * math.pi * 2.0)
    by = 0.08 * math.sin(tt * math.pi * 3.0)
    kf_loc(iceberg_pivot, f, (0, by, 0))
    kf_rot(iceberg_pivot, f, (0, 0, rot))

# penguins frémissent (tilt subtle)
for i, p in enumerate(penguins):
    phase = i * 0.4
    for f in range(1, FRAMES + 1, 4):
        tt = (f - 1) / (FRAMES - 1)
        tilt = math.radians(3.0) * math.sin(tt * math.pi * 6.0 + phase)
        kf_rot(p, f, (tilt, p.rotation_euler.y, 0))

# bear breathes
for f in range(1, FRAMES + 1, 4):
    tt = (f - 1) / (FRAMES - 1)
    s = 1.0 + 0.05 * math.sin(tt * math.pi * 4.0)
    kf_scale(bear_body, f, (1.4 * s, 0.8, 1.0))

# 3 floes drift + bob
for i, fp in enumerate(floes):
    phase = i * 1.3
    bx0 = fp.location.x
    bz0 = fp.location.z
    for f in range(1, FRAMES + 1, 4):
        tt = (f - 1) / (FRAMES - 1)
        dx = bx0 + 0.3 * math.sin(tt * math.pi * 1.5 + phase)
        dz = bz0 + 0.2 * math.cos(tt * math.pi * 1.2 + phase * 0.7)
        dy = 0.10 * math.sin(tt * math.pi * 4.0 + phase)
        kf_loc(fp, f, (dx, dy, dz))
        kf_rot(fp, f, (0, math.radians(8) * math.sin(tt * math.pi * 2.0 + phase), 0))

# birds fly in circles
for bp, a0, r, by in birds:
    for f in range(1, FRAMES + 1, 3):
        tt = (f - 1) / (FRAMES - 1)
        angle = a0 + tt * math.pi * 2.0
        bx = math.cos(angle) * r
        bz = math.sin(angle) * r
        by_a = by + 0.2 * math.sin(tt * math.pi * 4.0 + a0 * 2)
        kf_loc(bp, f, (bx, by_a, bz))
        kf_rot(bp, f, (0, -angle + math.pi / 2, math.radians(15) * math.sin(tt * math.pi * 8.0)))

# sun reflection strips wobble (scale x wave)
for rs, idx in refl_strips:
    base_x = rs.scale.x
    for f in range(1, FRAMES + 1, 3):
        tt = (f - 1) / (FRAMES - 1)
        s = base_x * (1.0 + 0.15 * math.sin(tt * math.pi * 6.0 + idx * 0.7))
        kf_scale(rs, f, (s, rs.scale.y, rs.scale.z))

# sun halo breathe
for f in range(1, FRAMES + 1, 4):
    tt = (f - 1) / (FRAMES - 1)
    s = 1.0 + 0.1 * math.sin(tt * math.pi * 3.0)
    kf_scale(sun_halo, f, (s, s, s))

# --- export -----------------------------------------------------------------
bpy.ops.object.select_all(action='SELECT')
bpy.ops.export_scene.gltf(
    filepath=OUT,
    export_format='GLB',
    export_animations=True,
    export_apply=False,
)
print(f"[proc_iceberg] wrote {OUT}")
