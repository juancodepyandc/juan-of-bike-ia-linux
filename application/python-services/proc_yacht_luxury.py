"""
proc_yacht_luxury.py — 141e procédural AuroraIA, Phase F++++.
QUALITÉ ULTRA — feedback utilisateur appliqué.

Yacht de luxe sur mer turquoise :
- coque profilée bevelée smooth
- 3 ponts (main + lower + upper)
- hélipad sur le toit avec hélicoptère
- piscine deck arrière + jacuzzi
- bar
- 4 chaises longues
- 2 parasols
- mât radio + 2 antennes
- drapeau pavillon
- 12 hublots émissifs + 12 fenêtres latérales
- cockpit bridge
- ancre
- 4 bouées
- lumières navigation
- 8 vagues océan + 6 foam

Animations multi-axes simultanées :
- yacht : pitch + roll + bob
- helicopter rotor + tail rotor spins
- antennes pivot
- drapeau wave
- 12 hublots pulse cycle
- jacuzzi water ripple
- 8 vagues ondulent

Sortie : output/3d/pbr_yacht_proc.glb.
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
OUT = os.path.normpath(os.path.join(CWD, "..", "output", "3d", "pbr_yacht_proc.glb"))

random.seed(0xCAFE61)

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


def smooth_shade(mesh):
    for poly in mesh.polygons:
        poly.use_smooth = True
    try:
        mesh.use_auto_smooth = True
        mesh.auto_smooth_angle = math.radians(40)
    except AttributeError:
        pass


def beveled_cube(name, size_xyz, bevel_offset=0.05, bevel_segments=3, loc=(0, 0, 0), parent=None, mat=None, smooth=True):
    me = bpy.data.meshes.new(name)
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    bmesh.ops.scale(bm, vec=(size_xyz[0], size_xyz[1], size_xyz[2]), verts=bm.verts)
    bmesh.ops.bevel(
        bm,
        geom=bm.edges[:] + bm.verts[:],
        offset=bevel_offset,
        segments=bevel_segments,
        profile=0.5,
        affect='EDGES',
    )
    bm.to_mesh(me)
    bm.free()
    o = add_obj(name, me, parent)
    o.location = loc
    if mat:
        me.materials.append(mat)
    if smooth:
        smooth_shade(me)
    return o


def smooth_sphere(name, r=1.0, segs=32, rings=20, loc=(0, 0, 0), parent=None, mat=None, scale=(1, 1, 1)):
    me = bpy.data.meshes.new(name)
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=segs, v_segments=rings, radius=r)
    if scale != (1, 1, 1):
        bmesh.ops.scale(bm, vec=scale, verts=bm.verts)
    bm.to_mesh(me)
    bm.free()
    o = add_obj(name, me, parent)
    o.location = loc
    if mat:
        me.materials.append(mat)
    smooth_shade(me)
    return o


def smooth_cone(name, r1=1.0, r2=0.0, depth=1.0, segs=24, loc=(0, 0, 0), parent=None, mat=None):
    me = bpy.data.meshes.new(name)
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, segments=segs, radius1=r1, radius2=r2, depth=depth, cap_ends=True)
    bm.to_mesh(me)
    bm.free()
    o = add_obj(name, me, parent)
    o.location = loc
    if mat:
        me.materials.append(mat)
    smooth_shade(me)
    return o


# --- materials --------------------------------------------------------------
MAT_SKY = make_mat("sky", (0.55, 0.78, 0.95), roughness=1.0,
                    emi=(0.45, 0.65, 0.85), emi_strength=0.5)
MAT_OCEAN = make_mat("ocean", (0.10, 0.55, 0.65), metallic=0.85, roughness=0.10, alpha=0.92,
                       emi=(0.15, 0.60, 0.70), emi_strength=0.6)
MAT_WAVE = make_mat("wave", (0.30, 0.70, 0.80), metallic=0.7, roughness=0.15, alpha=0.85,
                      emi=(0.20, 0.65, 0.75), emi_strength=0.5)
MAT_FOAM = make_mat("foam", (0.98, 0.98, 1.0), roughness=0.4, alpha=0.85,
                      emi=(0.85, 0.90, 1.0), emi_strength=1.2)
MAT_HULL_WHITE = make_mat("hull_white", (0.95, 0.95, 0.96), metallic=0.40, roughness=0.30,
                            emi=(0.20, 0.20, 0.22), emi_strength=0.20)
MAT_HULL_BLUE = make_mat("hull_blue", (0.10, 0.25, 0.55), metallic=0.55, roughness=0.30,
                           emi=(0.05, 0.10, 0.25), emi_strength=0.30)
MAT_DECK_WOOD = make_mat("deck_wood", (0.65, 0.45, 0.25), roughness=0.55,
                           emi=(0.25, 0.18, 0.08), emi_strength=0.25)
MAT_WINDOW = make_mat("window", (1.0, 0.92, 0.55), roughness=0.0, alpha=0.85,
                        emi=(1.0, 0.92, 0.55), emi_strength=5.5)
MAT_WINDOW_DARK = make_mat("window_dark", (0.10, 0.18, 0.30), roughness=0.0, alpha=0.55, metallic=0.55,
                             emi=(0.05, 0.12, 0.25), emi_strength=0.40)
MAT_CHROME = make_mat("chrome", (0.95, 0.95, 0.98), metallic=0.99, roughness=0.05)
MAT_HELICOPTER_BODY = make_mat("heli_body", (0.95, 0.95, 0.95), metallic=0.50, roughness=0.30,
                                 emi=(0.20, 0.20, 0.22), emi_strength=0.20)
MAT_HELICOPTER_DARK = make_mat("heli_dark", (0.20, 0.20, 0.22), metallic=0.70, roughness=0.35)
MAT_HELI_ROTOR = make_mat("heli_rotor", (0.15, 0.15, 0.18), metallic=0.80, roughness=0.30)
MAT_HELI_GLASS = make_mat("heli_glass", (0.10, 0.20, 0.30), roughness=0.0, alpha=0.45, metallic=0.55,
                            emi=(0.10, 0.15, 0.25), emi_strength=0.40)
MAT_POOL_WATER = make_mat("pool", (0.15, 0.55, 0.85), metallic=0.65, roughness=0.10, alpha=0.92,
                            emi=(0.20, 0.60, 0.85), emi_strength=0.7)
MAT_JACUZZI = make_mat("jacuzzi", (0.95, 0.40, 0.30), metallic=0.30, roughness=0.20, alpha=0.85,
                         emi=(0.45, 0.15, 0.10), emi_strength=0.6)
MAT_CHAIR = make_mat("chair", (0.95, 0.92, 0.85), roughness=0.6)
MAT_PARASOL = make_mat("parasol", (0.95, 0.10, 0.20), roughness=0.7,
                         emi=(0.35, 0.05, 0.08), emi_strength=0.4)
MAT_PARASOL_POLE = make_mat("parasol_pole", (0.95, 0.95, 0.98), metallic=0.85, roughness=0.20)
MAT_ANCHOR = make_mat("anchor", (0.30, 0.30, 0.35), metallic=0.80, roughness=0.35)
MAT_BUOY = make_mat("buoy", (1.0, 0.50, 0.10), roughness=0.5,
                      emi=(0.45, 0.20, 0.05), emi_strength=0.5)
MAT_NAV_RED = make_mat("nav_red", (1.0, 0.10, 0.10), roughness=0.0,
                         emi=(1.0, 0.10, 0.10), emi_strength=10.0)
MAT_NAV_GREEN = make_mat("nav_green", (0.10, 1.0, 0.30), roughness=0.0,
                           emi=(0.10, 1.0, 0.30), emi_strength=10.0)
MAT_FLAG_R = make_mat("flag_r", (0.85, 0.10, 0.10), roughness=0.6,
                        emi=(0.30, 0.05, 0.05), emi_strength=0.3)
MAT_FLAG_B = make_mat("flag_b", (0.15, 0.25, 0.65), roughness=0.6,
                        emi=(0.05, 0.10, 0.30), emi_strength=0.3)
MAT_ANTENNA = make_mat("antenna", (0.85, 0.85, 0.92), metallic=0.85, roughness=0.20)

# --- backdrop : sky --------------------------------------------------------
sky = beveled_cube("sky_back", (40, 0.2, 16), bevel_offset=0.05, bevel_segments=2, loc=(0, 9, 6), mat=MAT_SKY)

# 5 small clouds
for i, (cx, cy, cz) in enumerate([(-12, 14, 7), (-4, 13, 8), (4, 14, 9), (10, 13.5, 6), (-8, 13, 10)]):
    cl = smooth_sphere(f"cloud_{i}", r=random.uniform(1.0, 1.5), segs=18, rings=12, loc=(cx, cy, cz), mat=make_mat(f"cloud_mat_{i}", (0.98, 0.98, 1.0), roughness=1.0, alpha=0.9, emi=(0.85, 0.90, 0.95), emi_strength=0.3), scale=(1.5, 0.5, 1.0))

# --- ocean surface ----------------------------------------------------------
ocean = beveled_cube("ocean", (40, 0.1, 28), bevel_offset=0.05, bevel_segments=2, loc=(0, 0, 0), mat=MAT_OCEAN)

# 8 wave crests
waves = []
for i in range(8):
    wx = random.uniform(-15, 15)
    wz = random.uniform(-10, 10)
    if abs(wx) < 4 and abs(wz) < 6:
        continue  # leave yacht area clear
    w = smooth_sphere(f"wave_{i}", r=random.uniform(0.7, 1.1), segs=20, rings=14, loc=(wx, 0.3, wz), mat=MAT_WAVE, scale=(2.2, 0.4, 1.4))
    waves.append((w, wx, wz, random.uniform(0, math.pi * 2)))

# 6 foam crests
foams = []
for i in range(6):
    wx = random.uniform(-12, 12)
    wz = random.uniform(-8, 8)
    fo = smooth_sphere(f"foam_{i}", r=0.5, segs=14, rings=10, loc=(wx, 0.55, wz), mat=MAT_FOAM, scale=(1.4, 0.15, 0.8))
    foams.append((fo, wx, wz, random.uniform(0, 1)))

# --- yacht ---------------------------------------------------------------
yacht = empty("yacht", (0, 0.7, 0))

# hull (long bevelled cube + tapered front)
# main hull body
hull = beveled_cube("hull", (5.0, 0.8, 1.5), bevel_offset=0.20, bevel_segments=5, loc=(0, 0, 0), parent=yacht, mat=MAT_HULL_WHITE)

# tapered bow (front pointed)
bow = smooth_cone("bow", r1=0.75, r2=0.10, depth=1.0, segs=20, loc=(2.95, 0, 0), parent=yacht, mat=MAT_HULL_WHITE)
bow.rotation_euler = (0, math.radians(90), 0)
bow.scale = (1.0, 1.0, 1.8)

# stern (back, slightly rounded)
stern = smooth_sphere("stern", r=0.5, segs=24, rings=16, loc=(-2.6, 0, 0), parent=yacht, mat=MAT_HULL_WHITE, scale=(0.6, 1.6, 3.0))

# hull blue stripe (waterline accent)
stripe = beveled_cube("hull_stripe", (6.2, 0.10, 1.55), bevel_offset=0.04, bevel_segments=2, loc=(0, -0.35, 0), parent=yacht, mat=MAT_HULL_BLUE)

# --- lower deck (main deck wood) ----------------------------------------
lower_deck = beveled_cube("lower_deck", (4.6, 0.06, 1.4), bevel_offset=0.04, bevel_segments=2, loc=(0, 0.45, 0), parent=yacht, mat=MAT_DECK_WOOD)

# 12 hull windows (port + starboard)
hull_windows = []
for side, dz in [("L", 0.78), ("R", -0.78)]:
    for i in range(6):
        wx = -1.5 + i * 0.55
        w = beveled_cube(f"hull_win_{side}_{i}", (0.32, 0.18, 0.04), bevel_offset=0.03, bevel_segments=2, loc=(wx, 0.10, dz), parent=yacht, mat=MAT_WINDOW)
        hull_windows.append(w)

# --- middle deck (cabin level) ----------------------------------------
cabin_body = beveled_cube("cabin_body", (3.6, 0.75, 1.25), bevel_offset=0.10, bevel_segments=4, loc=(-0.2, 0.90, 0), parent=yacht, mat=MAT_HULL_WHITE)

# 12 cabin windows
cabin_windows = []
for side, dz in [("L", 0.65), ("R", -0.65)]:
    for i in range(6):
        wx = -1.4 + i * 0.50
        w = beveled_cube(f"cabin_win_{side}_{i}", (0.32, 0.30, 0.04), bevel_offset=0.03, bevel_segments=2, loc=(wx, 0.95, dz), parent=yacht, mat=MAT_WINDOW_DARK)
        cabin_windows.append(w)

# --- bridge (cockpit, front of cabin) -------------------------------
bridge_p = empty("bridge_p", (1.0, 1.45, 0), parent=yacht)
# cockpit shell
bridge_shell = beveled_cube("bridge_shell", (1.0, 0.55, 1.20), bevel_offset=0.12, bevel_segments=4, loc=(0, 0, 0), parent=bridge_p, mat=MAT_HULL_WHITE)
# windshield (slanted forward)
windshield = beveled_cube("bridge_windshield", (0.10, 0.45, 1.10), bevel_offset=0.05, bevel_segments=3, loc=(0.50, 0.05, 0), parent=bridge_p, mat=MAT_WINDOW_DARK)
windshield.rotation_euler = (0, 0, math.radians(-25))
# side windows
for side, dz in [("L", 0.62), ("R", -0.62)]:
    sw = beveled_cube(f"bridge_side_{side}", (0.95, 0.35, 0.04), bevel_offset=0.03, bevel_segments=2, loc=(0, 0.05, dz), parent=bridge_p, mat=MAT_WINDOW_DARK)
# roof
bridge_roof = beveled_cube("bridge_roof", (1.05, 0.06, 1.25), bevel_offset=0.05, bevel_segments=3, loc=(0, 0.32, 0), parent=bridge_p, mat=MAT_HULL_WHITE)

# --- upper deck (helipad level) -------------------------------------
upper_deck = beveled_cube("upper_deck", (3.0, 0.06, 1.15), bevel_offset=0.05, bevel_segments=3, loc=(-0.5, 1.75, 0), parent=yacht, mat=MAT_DECK_WOOD)

# --- helipad and helicopter -----------------------------------------
helipad = smooth_cone("helipad", r1=0.85, r2=0.85, depth=0.05, segs=24, loc=(-0.5, 1.83, 0), parent=yacht, mat=MAT_DECK_WOOD)
helipad.rotation_euler = (math.radians(90), 0, 0)
# H circle stripe
h_stripe = smooth_cone("helipad_stripe", r1=0.40, r2=0.40, depth=0.03, segs=20, loc=(-0.5, 1.86, 0), parent=yacht, mat=MAT_HULL_WHITE)
h_stripe.rotation_euler = (math.radians(90), 0, 0)
# H letter (3 stripes forming H)
for k, (kx, sx) in enumerate([(-0.10, 0.04), (0.10, 0.04), (0, 0.20)]):
    if k < 2:
        line = beveled_cube(f"h_line_{k}", (sx, 0.02, 0.30), bevel_offset=0.005, bevel_segments=2, loc=(-0.5 + kx, 1.88, 0), parent=yacht, mat=MAT_HULL_WHITE)
    else:
        line = beveled_cube(f"h_line_{k}", (sx, 0.02, 0.04), bevel_offset=0.005, bevel_segments=2, loc=(-0.5 + kx, 1.88, 0), parent=yacht, mat=MAT_HULL_WHITE)

# helicopter sitting on pad
heli_p = empty("helicopter", (-0.5, 1.90, 0), parent=yacht)
# main body
heli_body = smooth_sphere("heli_body", r=0.32, segs=22, rings=16, loc=(0, 0, 0), parent=heli_p, mat=MAT_HELICOPTER_BODY, scale=(1.8, 0.9, 1.0))
# cockpit glass bubble
heli_glass = smooth_sphere("heli_glass", r=0.22, segs=18, rings=14, loc=(0.30, 0.05, 0), parent=heli_p, mat=MAT_HELI_GLASS, scale=(1.2, 0.9, 1.0))
# tail boom (cone)
heli_tail = smooth_cone("heli_tail", r1=0.10, r2=0.05, depth=0.70, segs=14, loc=(-0.55, 0.10, 0), parent=heli_p, mat=MAT_HELICOPTER_BODY)
heli_tail.rotation_euler = (0, math.radians(-90), 0)
# tail fin
heli_fin = beveled_cube("heli_fin", (0.18, 0.15, 0.03), bevel_offset=0.02, bevel_segments=2, loc=(-0.95, 0.20, 0), parent=heli_p, mat=MAT_HELICOPTER_BODY)
# main rotor mount
rotor_mast = smooth_cone("rotor_mast", r1=0.04, r2=0.04, depth=0.15, segs=10, loc=(0, 0.32, 0), parent=heli_p, mat=MAT_HELI_ROTOR)
rotor_mast.rotation_euler = (math.radians(90), 0, 0)
# main rotor (4 blades)
rotor_p = empty("rotor_p", (0, 0.42, 0), parent=heli_p)
for k in range(4):
    ka = k * (math.pi / 2)
    blade = beveled_cube(f"rotor_blade_{k}", (1.2, 0.02, 0.08), bevel_offset=0.02, bevel_segments=2, loc=(0, 0, 0), parent=rotor_p, mat=MAT_HELI_ROTOR)
    blade.rotation_euler = (0, ka, 0)
# tail rotor (3 blades)
tail_rotor_p = empty("tail_rotor_p", (-1.20, 0.25, 0.10), parent=heli_p)
for k in range(3):
    ka = k * (math.pi * 2 / 3)
    blade = beveled_cube(f"tail_blade_{k}", (0.04, 0.02, 0.18), bevel_offset=0.01, bevel_segments=2, loc=(0, 0, 0), parent=tail_rotor_p, mat=MAT_HELI_ROTOR)
    blade.rotation_euler = (0, 0, ka)
# 2 landing skids
for side, dz in [("L", 0.18), ("R", -0.18)]:
    skid = smooth_cone(f"heli_skid_{side}", r1=0.025, r2=0.025, depth=0.55, segs=8, loc=(0, -0.25, dz), parent=heli_p, mat=MAT_HELI_ROTOR)
    skid.rotation_euler = (0, math.radians(90), 0)

# --- piscine arrière (rectangle pool sur lower deck arrière) ----------
pool = beveled_cube("pool", (1.1, 0.10, 0.7), bevel_offset=0.04, bevel_segments=3, loc=(-1.8, 0.52, 0.3), parent=yacht, mat=MAT_POOL_WATER)
# pool rim (slight gold trim)
pool_rim_data = [
    ("F", 0, 0.40, 1.20, 0.04),
    ("B", 0, -0.40, 1.20, 0.04),
    ("L", 0.60, 0, 0.04, 0.80),
    ("R", -0.60, 0, 0.04, 0.80),
]
for side, dx_in, dz_in, sx, sz in pool_rim_data:
    rim = beveled_cube(f"pool_rim_{side}", (sx, 0.04, sz), bevel_offset=0.01, bevel_segments=2, loc=(-1.8 + dx_in, 0.55, 0.3 + dz_in), parent=yacht, mat=MAT_CHROME)

# --- jacuzzi (smaller round, hot tub) ----------------------------
jacuzzi_p = empty("jacuzzi", (-1.5, 0.55, -0.6), parent=yacht)
jacuzzi_water = smooth_cone("jacuzzi_water", r1=0.35, r2=0.35, depth=0.08, segs=20, loc=(0, 0, 0), parent=jacuzzi_p, mat=MAT_JACUZZI)
jacuzzi_water.rotation_euler = (math.radians(90), 0, 0)
# rim
jacuzzi_rim = smooth_cone("jacuzzi_rim", r1=0.40, r2=0.40, depth=0.12, segs=20, loc=(0, -0.04, 0), parent=jacuzzi_p, mat=MAT_HULL_WHITE)
jacuzzi_rim.rotation_euler = (math.radians(90), 0, 0)

# --- 4 chaises longues (deck loungers) ---------------------------------
for i, (cx, cz) in enumerate([(1.5, 0.55), (1.5, -0.55), (-2.5, 0.50), (-2.5, -0.50)]):
    chair_p = empty(f"chair_{i}", (cx, 0.50, cz), parent=yacht)
    # base
    base = beveled_cube(f"chair_{i}_base", (0.50, 0.04, 0.18), bevel_offset=0.02, bevel_segments=2, loc=(0, 0, 0), parent=chair_p, mat=MAT_CHAIR)
    # backrest
    back = beveled_cube(f"chair_{i}_back", (0.06, 0.30, 0.18), bevel_offset=0.02, bevel_segments=2, loc=(-0.20, 0.13, 0), parent=chair_p, mat=MAT_CHAIR)
    back.rotation_euler = (0, 0, math.radians(-30))
    # legs (2)
    for k, lx in enumerate([0.15, -0.15]):
        leg = beveled_cube(f"chair_{i}_l_{k}", (0.03, 0.10, 0.03), bevel_offset=0.005, bevel_segments=2, loc=(lx, -0.05, 0), parent=chair_p, mat=MAT_CHROME)

# --- 2 parasols ---------------------------------------------------
for i, (px, pz) in enumerate([(1.0, 0), (-2.2, -0.6)]):
    parasol_p = empty(f"parasol_{i}", (px, 0.55, pz), parent=yacht)
    # pole
    pole = smooth_cone(f"parasol_{i}_pole", r1=0.03, r2=0.03, depth=0.8, segs=10, loc=(0, 0.4, 0), parent=parasol_p, mat=MAT_PARASOL_POLE)
    pole.rotation_euler = (math.radians(90), 0, 0)
    # canopy
    canopy = smooth_cone(f"parasol_{i}_canopy", r1=0.55, r2=0.05, depth=0.20, segs=18, loc=(0, 0.95, 0), parent=parasol_p, mat=MAT_PARASOL)
    canopy.rotation_euler = (math.radians(90), 0, 0)
    # top sphere
    top = smooth_sphere(f"parasol_{i}_top", r=0.04, segs=14, rings=10, loc=(0, 1.10, 0), parent=parasol_p, mat=MAT_PARASOL_POLE)

# --- mât radio + 2 antennes ----------------------------------------
mast_p = empty("mast_p", (0.5, 2.0, 0), parent=yacht)
mast_pole = smooth_cone("mast_pole", r1=0.04, r2=0.03, depth=1.2, segs=10, loc=(0, 0.60, 0), parent=mast_p, mat=MAT_ANTENNA)
mast_pole.rotation_euler = (math.radians(90), 0, 0)
# 2 antennas
antennas = []
for side, rot in [("L", math.radians(20)), ("R", math.radians(-20))]:
    ant_p = empty(f"antenna_p_{side}", (0, 1.2, 0), parent=mast_p)
    ant_p.rotation_euler = (0, 0, rot)
    ant = smooth_cone(f"antenna_{side}", r1=0.015, r2=0.005, depth=0.7, segs=8, loc=(0, 0.35, 0), parent=ant_p, mat=MAT_ANTENNA)
    ant.rotation_euler = (math.radians(90), 0, 0)
    # tip (small sphere)
    tip = smooth_sphere(f"antenna_{side}_tip", r=0.03, segs=10, rings=8, loc=(0, 0.72, 0), parent=ant_p, mat=MAT_NAV_RED if side == "L" else MAT_NAV_GREEN)
    antennas.append(ant_p)
# radar dish on top
radar_p = empty("radar_p", (0, 1.5, 0), parent=mast_p)
radar = smooth_sphere("radar", r=0.18, segs=20, rings=14, loc=(0, 0, 0), parent=radar_p, mat=MAT_CHROME, scale=(1.0, 0.4, 1.0))

# --- drapeau pavillon ----------------------------------------------
flag_p = empty("flag_p", (-2.8, 1.85, 0), parent=yacht)
flag_pole = smooth_cone("flag_pole", r1=0.025, r2=0.020, depth=0.8, segs=10, loc=(0, 0.4, 0), parent=flag_p, mat=MAT_ANTENNA)
flag_pole.rotation_euler = (math.radians(90), 0, 0)
# 5 segments waving
flag_segs = []
for k in range(5):
    mat = MAT_FLAG_R if k % 2 == 0 else MAT_FLAG_B
    seg = beveled_cube(f"flag_seg_{k}", (0.06, 0.20, 0.04), bevel_offset=0.01, bevel_segments=2, loc=(0.04 + k * 0.06, 0.65, 0), parent=flag_p, mat=mat)
    flag_segs.append(seg)

# --- ancre (sur bow latéral) ---------------------------------
anchor_p = empty("anchor", (2.4, -0.20, 0.85), parent=yacht)
# rope to anchor
arope = smooth_cone("arope", r1=0.015, r2=0.015, depth=0.50, segs=6, loc=(0, 0.20, 0), parent=anchor_p, mat=MAT_DECK_WOOD)
arope.rotation_euler = (math.radians(90), 0, 0)
# anchor body
ab = beveled_cube("anchor_body", (0.06, 0.30, 0.06), bevel_offset=0.02, bevel_segments=2, loc=(0, 0, 0), parent=anchor_p, mat=MAT_ANCHOR)
# 2 arms
for side, dx in [("L", -0.20), ("R", 0.20)]:
    arm = smooth_cone(f"anchor_arm_{side}", r1=0.04, r2=0.02, depth=0.30, segs=8, loc=(dx, -0.06, 0), parent=anchor_p, mat=MAT_ANCHOR)
    arm.rotation_euler = (0, 0, math.radians(60 if side == "L" else -60))

# --- 4 bouées orange sur côtés ---------------------------------
for i, (bx, bz) in enumerate([(1.5, 0.92), (1.5, -0.92), (-1.5, 0.92), (-1.5, -0.92)]):
    bp = empty(f"buoy_{i}", (bx, 0.30, bz), parent=yacht)
    # outer ring (annular smooth)
    ring = smooth_cone(f"buoy_{i}_ring", r1=0.18, r2=0.18, depth=0.10, segs=20, loc=(0, 0, 0), parent=bp, mat=MAT_BUOY)
    ring.rotation_euler = (math.radians(90), 0, 0)
    # inner hole (subtract via inner ring darker)
    inner = smooth_cone(f"buoy_{i}_in", r1=0.10, r2=0.10, depth=0.12, segs=18, loc=(0, 0, 0), parent=bp, mat=MAT_HULL_WHITE)
    inner.rotation_euler = (math.radians(90), 0, 0)

# --- nav lights port (red) + starboard (green) -----------------
# Front nav lights
nav_lights = []
for side, dz, mat in [("L", 0.78, MAT_NAV_RED), ("R", -0.78, MAT_NAV_GREEN)]:
    n = smooth_sphere(f"nav_{side}", r=0.06, segs=14, rings=10, loc=(2.7, 0.55, dz), parent=yacht, mat=mat)
    nav_lights.append(n)
# Top mast light (white)
nav_top = smooth_sphere("nav_top", r=0.06, segs=14, rings=10, loc=(0.5, 3.65, 0), parent=yacht, mat=make_mat("nav_white_top", (1, 1, 0.95), roughness=0, emi=(1, 1, 0.95), emi_strength=12.0))

# --- bar (small structure on lower deck) ----------------------
bar_p = empty("bar", (-1.0, 0.55, 0.3), parent=yacht)
bar_body = beveled_cube("bar_body", (0.50, 0.45, 0.25), bevel_offset=0.05, bevel_segments=3, loc=(0, 0.20, 0), parent=bar_p, mat=MAT_DECK_WOOD)
# 3 bottles on top (sphères stretched)
for k in range(3):
    kx = -0.15 + k * 0.15
    bot = smooth_sphere(f"bar_bot_{k}", r=0.05, segs=14, rings=10, loc=(kx, 0.50, 0), parent=bar_p, mat=MAT_WINDOW_DARK, scale=(1.0, 1.8, 1.0))

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

# yacht pitch + roll + bob (multi-axis)
for f in range(1, FRAMES + 1, 2):
    tt = (f - 1) / (FRAMES - 1)
    pitch = math.radians(3) * math.sin(tt * math.pi * 2.0)
    roll = math.radians(2.5) * math.cos(tt * math.pi * 1.8)
    by = 0.7 + 0.10 * math.sin(tt * math.pi * 2.5)
    kf_loc(yacht, f, (0, by, 0))
    kf_rot(yacht, f, (pitch, 0, roll))

# helicopter main rotor spins fast
for f in range(1, FRAMES + 1, 2):
    tt = (f - 1) / (FRAMES - 1)
    kf_rot(rotor_p, f, (0, tt * math.pi * 40, 0))  # very fast

# helicopter tail rotor spins
for f in range(1, FRAMES + 1, 2):
    tt = (f - 1) / (FRAMES - 1)
    kf_rot(tail_rotor_p, f, (tt * math.pi * 50, 0, 0))

# antennas pivot
for i, ant_p in enumerate(antennas):
    base_rot = ant_p.rotation_euler.copy()
    for f in range(1, FRAMES + 1, 4):
        tt = (f - 1) / (FRAMES - 1)
        delta = math.radians(10) * math.sin(tt * math.pi * 3.0 + i * 0.5)
        kf_rot(ant_p, f, (delta, 0, base_rot[2]))

# radar rotates Y
for f in range(1, FRAMES + 1, 3):
    tt = (f - 1) / (FRAMES - 1)
    kf_rot(radar_p, f, (0, tt * math.pi * 4.0, 0))

# flag waves (5 segments)
for i, seg in enumerate(flag_segs):
    base_x = seg.location.x
    base_y = seg.location.y
    base_z = seg.location.z
    for f in range(1, FRAMES + 1, 2):
        tt = (f - 1) / (FRAMES - 1)
        wave = math.sin(i * 0.4 + tt * math.pi * 7.0)
        kz = wave * 0.10
        ky = base_y + math.cos(i * 0.4 + tt * math.pi * 7.0) * 0.04
        kf_loc(seg, f, (base_x, ky, kz))
        kf_rot(seg, f, (0, 0, wave * 0.15))

# 12 hull + 12 cabin windows pulse cycle (24 total)
for i, w in enumerate(hull_windows + cabin_windows):
    phase = i * 0.25
    for f in range(1, FRAMES + 1, 4):
        tt = (f - 1) / (FRAMES - 1)
        s = 1.0 + 0.08 * math.sin(tt * math.pi * 4.0 + phase)
        kf_scale(w, f, (s, s, 1.0))

# jacuzzi water ripple (scale wobble)
for f in range(1, FRAMES + 1, 3):
    tt = (f - 1) / (FRAMES - 1)
    s = 1.0 + 0.05 * math.sin(tt * math.pi * 6.0)
    kf_scale(jacuzzi_water, f, (s, 1.0, s))

# pool water ripple
for f in range(1, FRAMES + 1, 3):
    tt = (f - 1) / (FRAMES - 1)
    s = 1.0 + 0.03 * math.sin(tt * math.pi * 5.0)
    kf_scale(pool, f, (s, 1.0, s))

# 8 waves ondulate
for w, wx, wz, ph in waves:
    for f in range(1, FRAMES + 1, 3):
        tt = (f - 1) / (FRAMES - 1)
        dy = 0.3 + 0.30 * math.sin(tt * math.pi * 4.0 + ph)
        kf_loc(w, f, (wx, dy, wz))
        s = 1.0 + 0.12 * math.cos(tt * math.pi * 3.0 + ph)
        kf_scale(w, f, (2.2 * s, 0.4, 1.4 * s))

# 6 foam dance
for fo, fx, fz, ph in foams:
    for f in range(1, FRAMES + 1, 3):
        tt = (f - 1) / (FRAMES - 1)
        dy = 0.55 + 0.15 * math.sin(tt * math.pi * 5.0 + ph)
        s = 1.0 + 0.20 * math.sin(tt * math.pi * 6.0 + ph)
        kf_loc(fo, f, (fx, dy, fz))
        kf_scale(fo, f, (1.4 * s, 0.15, 0.8 * s))

# nav lights blink (fast)
for nl in nav_lights:
    for f in range(1, FRAMES + 1, 2):
        tt = (f - 1) / (FRAMES - 1)
        s = 1.0 + 0.25 * math.sin(tt * math.pi * 12.0)
        kf_scale(nl, f, (s, s, s))

# top nav light pulse fast
for f in range(1, FRAMES + 1, 2):
    tt = (f - 1) / (FRAMES - 1)
    s = 1.0 + 0.30 * math.sin(tt * math.pi * 15.0)
    kf_scale(nav_top, f, (s, s, s))

# --- export -----------------------------------------------------------------
bpy.ops.object.select_all(action='SELECT')
bpy.ops.export_scene.gltf(
    filepath=OUT,
    export_format='GLB',
    export_animations=True,
    export_apply=False,
)
print(f"[proc_yacht] wrote {OUT}")
