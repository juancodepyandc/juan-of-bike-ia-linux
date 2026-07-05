"""
proc_aurora_borealis.py — 111e procédural AuroraIA, Phase F++++.

Aurores boréales : ciel nocturne étoilé + 3 bandes ondulantes lumineuses
(vert / vert-bleu / violet) en arcs traversant le ciel + 4 montagnes
neigeuses sombres en silhouette + lac réfléchissant + petite tente
d'observation au sol + 3 sapins.

Animation :
- bandes : déformation horizontale via scale + position waves
- bandes : émission pulse différentielle
- reflets sur le lac : strip mirrored (statique miroir, scale matched)
- 70 étoiles : scintillement (scale + emission pulse phases offset)
- lampe de la tente : pulse douce
- aurore secondaire faible en mouvement

Sortie : output/3d/pbr_aurora_proc.glb.
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
OUT = os.path.normpath(os.path.join(CWD, "..", "output", "3d", "pbr_aurora_proc.glb"))

random.seed(0xAAA404)

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


def aurora_strip(name, color, emi_strength, base_y, base_z, length=14.0, height=2.5, segments=32):
    """Build an aurora band as a series of stretched cubes side-by-side that
    can be independently positioned to draw a wavy curtain.  Returns parent
    + list of segment objects so the animation can wave them.
    """
    mat = make_mat(name + "_mat", color, roughness=0.0, alpha=0.55,
                    emi=color, emi_strength=emi_strength)
    parent = empty(name, (0, base_y, base_z))
    segs = []
    seg_w = length / segments
    for i in range(segments):
        x = -length / 2 + (i + 0.5) * seg_w
        c = cube(f"{name}_{i}", size=1.0, loc=(x, 0, 0), parent=parent, mat=mat)
        c.scale = (seg_w * 0.9, 0.04, height)
        segs.append(c)
    return parent, segs, mat


# --- materials --------------------------------------------------------------
MAT_NIGHT = make_mat("night_sky", (0.02, 0.025, 0.06), roughness=1.0,
                      emi=(0.04, 0.05, 0.12), emi_strength=0.4)
MAT_STAR_W = make_mat("star_w", (1.0, 1.0, 1.0), roughness=0.0,
                       emi=(1.0, 1.0, 1.0), emi_strength=4.5)
MAT_STAR_Y = make_mat("star_y", (1.0, 0.9, 0.65), roughness=0.0,
                       emi=(1.0, 0.9, 0.65), emi_strength=5.0)
MAT_STAR_B = make_mat("star_b", (0.7, 0.85, 1.0), roughness=0.0,
                       emi=(0.7, 0.85, 1.0), emi_strength=5.5)
MAT_MOON = make_mat("moon", (0.85, 0.88, 0.95), roughness=0.5,
                     emi=(0.85, 0.88, 0.95), emi_strength=2.0)
MAT_MOON_HALO = make_mat("moon_halo", (0.6, 0.7, 0.95), roughness=0.0, alpha=0.25,
                          emi=(0.6, 0.7, 1.0), emi_strength=1.5)
MAT_MOUNTAIN = make_mat("mountain", (0.05, 0.06, 0.10), roughness=0.95)
MAT_SNOW_CAP = make_mat("snow_cap", (0.85, 0.88, 0.95), roughness=0.6,
                          emi=(0.4, 0.45, 0.55), emi_strength=0.3)
MAT_LAKE = make_mat("lake", (0.04, 0.08, 0.12), metallic=0.85, roughness=0.05,
                     emi=(0.06, 0.10, 0.18), emi_strength=0.4)
MAT_SHORE = make_mat("shore", (0.06, 0.07, 0.09), roughness=0.9)
MAT_TENT = make_mat("tent", (0.55, 0.18, 0.12), roughness=0.7)
MAT_TENT_GLOW = make_mat("tent_glow", (1.0, 0.85, 0.5), roughness=0.0, alpha=0.8,
                          emi=(1.0, 0.8, 0.4), emi_strength=4.5)
MAT_TREE_FIR = make_mat("tree_fir", (0.04, 0.10, 0.05), roughness=0.85)
MAT_TRUNK = make_mat("trunk", (0.10, 0.07, 0.05), roughness=0.9)
MAT_SNOW_GROUND = make_mat("snow_ground", (0.20, 0.22, 0.25), roughness=0.7,
                             emi=(0.10, 0.12, 0.18), emi_strength=0.2)

# --- backdrop (deep sky) ----------------------------------------------------
sky = cube("sky_back", size=1.0, loc=(0, 16, 4), mat=MAT_NIGHT)
sky.scale = (24, 0.1, 14)

# --- 70 stars in the sky ----------------------------------------------------
for i in range(70):
    x = random.uniform(-20, 20)
    z = random.uniform(2.0, 11.0)
    y = random.uniform(13.5, 14.5)
    pick = random.random()
    if pick < 0.7:
        m = MAT_STAR_W
    elif pick < 0.88:
        m = MAT_STAR_Y
    else:
        m = MAT_STAR_B
    sr = random.uniform(0.05, 0.12)
    s = sphere(f"star_{i}", r=sr, segs=8, rings=6, loc=(x, y, z), mat=m)
    s["_phase"] = (i * 13) % 47  # for keyframe phase offset later

# --- moon -------------------------------------------------------------------
moon = sphere("moon", r=0.7, segs=24, rings=18, loc=(7.0, 13.0, 8.5), mat=MAT_MOON)
moon_halo = sphere("moon_halo", r=1.1, segs=20, rings=14, loc=(7.0, 13.2, 8.5), mat=MAT_MOON_HALO)

# --- 4 background mountains -------------------------------------------------
mountain_data = [
    (-8.0, 5.5, 6.0, 7.0),
    (-3.0, 4.8, 6.0, 5.5),
    ( 3.0, 5.2, 6.0, 6.2),
    ( 8.5, 5.0, 6.0, 6.0),
]
for i, (mx, mh, my, mw) in enumerate(mountain_data):
    mt = cone(f"mountain_{i}", r1=mw, r2=0.3, depth=mh, segs=8, loc=(mx, my, mh / 2 - 1.0), mat=MAT_MOUNTAIN)
    mt.rotation_euler = (math.radians(90), 0, random.uniform(0, math.pi))
    # snow cap : smaller cone on top
    cap = cone(f"snow_cap_{i}", r1=1.5, r2=0.1, depth=1.8, segs=8, loc=(mx, my, mh - 1.5), mat=MAT_SNOW_CAP)
    cap.rotation_euler = (math.radians(90), 0, 0)

# --- snow ground (foreground) -----------------------------------------------
ground = cube("snow_ground", size=1.0, loc=(0, 0, -0.5), mat=MAT_SNOW_GROUND)
ground.scale = (24, 0.05, 8)

# --- lake (mirrored area in front of mountains) -----------------------------
lake = cube("lake_surface", size=1.0, loc=(0, 3.5, -0.4), mat=MAT_LAKE)
lake.scale = (22, 0.05, 4)

# shore strip
shore = cube("shore_strip", size=1.0, loc=(0, 1.4, -0.45), mat=MAT_SHORE)
shore.scale = (24, 0.05, 0.4)

# --- aurora bands : 3 main + lake reflections -------------------------------
# main bands (high up in sky)
band_a_parent, band_a_segs, _ = aurora_strip("aurora_green", (0.2, 1.0, 0.45), 5.5, base_y=9.0, base_z=9.0, length=18.0, height=2.8, segments=36)
band_b_parent, band_b_segs, _ = aurora_strip("aurora_teal",  (0.2, 0.85, 0.95), 4.5, base_y=10.0, base_z=8.0, length=20.0, height=2.4, segments=36)
band_c_parent, band_c_segs, _ = aurora_strip("aurora_violet",(0.7, 0.3, 1.0), 4.0, base_y=11.0, base_z=10.0, length=22.0, height=2.0, segments=36)

# lake reflections (mirrored, dimmer)
refl_a_parent, refl_a_segs, _ = aurora_strip("aurora_refl_g", (0.2, 1.0, 0.45), 1.2, base_y=3.5, base_z=-0.35, length=18.0, height=0.7, segments=36)
refl_b_parent, refl_b_segs, _ = aurora_strip("aurora_refl_t", (0.2, 0.85, 0.95), 0.9, base_y=3.5, base_z=-0.30, length=20.0, height=0.6, segments=36)
refl_c_parent, refl_c_segs, _ = aurora_strip("aurora_refl_v", (0.7, 0.3, 1.0), 0.7, base_y=3.5, base_z=-0.25, length=22.0, height=0.55, segments=36)

# --- 3 fir trees on shore ---------------------------------------------------
def make_fir(name, x, z):
    p = empty(name, (x, 1.0, z))
    trunk = cone(f"{name}_trunk", r1=0.12, r2=0.10, depth=0.8, segs=8, loc=(0, 0.4, 0), parent=p, mat=MAT_TRUNK)
    trunk.rotation_euler = (math.radians(90), 0, 0)
    # 3 cone layers, stacked
    for j in range(3):
        h = 0.9 + j * 0.55
        r = 0.65 - j * 0.18
        layer = cone(f"{name}_layer_{j}", r1=r, r2=r * 0.4, depth=0.55, segs=10, loc=(0, h, 0), parent=p, mat=MAT_TREE_FIR)
        layer.rotation_euler = (math.radians(90), 0, 0)
    return p

for i, (x, z) in enumerate([(-5.0, 0.3), (-2.0, 0.0), (4.0, 0.2)]):
    make_fir(f"fir_{i}", x, z)

# --- tent d'observation with glowing lamp inside ---------------------------
tent_p = empty("tent", (1.5, 1.3, -0.1))
# tent shape : flattened pyramid (cone with 4 segments)
tent_body = cone("tent_body", r1=0.7, r2=0.05, depth=0.8, segs=4, loc=(0, 0.4, 0), parent=tent_p, mat=MAT_TENT)
tent_body.rotation_euler = (math.radians(90), 0, math.radians(45))
# glowing lantern inside (visible through fabric due to alpha+emission)
lantern = sphere("tent_lamp", r=0.20, segs=16, rings=12, loc=(0, 0.25, 0), parent=tent_p, mat=MAT_TENT_GLOW)

# --- animation --------------------------------------------------------------

def kf_loc(o, f, l):
    o.location = l
    o.keyframe_insert(data_path="location", frame=f)


def kf_scale(o, f, s):
    o.scale = s
    o.keyframe_insert(data_path="scale", frame=f)


FRAMES = 180

# aurora bands : wave each segment vertically + slight z drift
def animate_band(segs, freq, amp_z, amp_y, phase_off, base_height_scale):
    n = len(segs)
    seg_w = 18.0 / n  # approximate from default
    for f in range(1, FRAMES + 1, 3):
        tt = (f - 1) / (FRAMES - 1)
        for j, seg in enumerate(segs):
            u = j / (n - 1)
            wave = math.sin(u * math.pi * freq + tt * math.pi * 2.0 + phase_off)
            wave2 = math.sin(u * math.pi * (freq * 1.7) + tt * math.pi * 3.5 + phase_off + 1.2)
            dy = wave * amp_y
            dz = wave * amp_z + wave2 * amp_z * 0.35
            base_x = seg.location.x  # x stays
            kf_loc(seg, f, (base_x, dy, dz))
            # height pulse
            sz = base_height_scale * (1.0 + 0.18 * math.sin(u * math.pi * 5.0 + tt * math.pi * 4.0))
            kf_scale(seg, f, (seg.scale.x, seg.scale.y, sz))

animate_band(band_a_segs, freq=4.0, amp_z=0.45, amp_y=0.25, phase_off=0.0, base_height_scale=2.8)
animate_band(band_b_segs, freq=3.5, amp_z=0.55, amp_y=0.30, phase_off=1.0, base_height_scale=2.4)
animate_band(band_c_segs, freq=4.5, amp_z=0.40, amp_y=0.20, phase_off=2.1, base_height_scale=2.0)

# lake reflections : mirror motion (dimmer scale)
animate_band(refl_a_segs, freq=4.0, amp_z=0.10, amp_y=0.20, phase_off=0.0, base_height_scale=0.7)
animate_band(refl_b_segs, freq=3.5, amp_z=0.12, amp_y=0.25, phase_off=1.0, base_height_scale=0.6)
animate_band(refl_c_segs, freq=4.5, amp_z=0.08, amp_y=0.15, phase_off=2.1, base_height_scale=0.55)

# stars twinkle
for i in range(70):
    star = bpy.data.objects.get(f"star_{i}")
    if not star:
        continue
    phase = star["_phase"]
    for f in range(1, FRAMES + 1, 6):
        tt = (f - 1) / (FRAMES - 1)
        local = (math.sin(tt * math.pi * 6.0 + phase * 0.13) + 1) * 0.5
        s = 0.6 + 0.7 * local
        kf_scale(star, f, (s, s, s))

# moon slight halo breathing
for f in range(1, FRAMES + 1, 4):
    tt = (f - 1) / (FRAMES - 1)
    s = 1.0 + 0.1 * math.sin(tt * math.pi * 3.0)
    kf_scale(moon_halo, f, (s, s, s))

# tent lamp pulse
for f in range(1, FRAMES + 1, 4):
    tt = (f - 1) / (FRAMES - 1)
    s = 1.0 + 0.18 * math.sin(tt * math.pi * 4.5)
    kf_scale(lantern, f, (s, s, s))

# --- export -----------------------------------------------------------------
bpy.ops.object.select_all(action='SELECT')
bpy.ops.export_scene.gltf(
    filepath=OUT,
    export_format='GLB',
    export_animations=True,
    export_apply=False,
)
print(f"[proc_aurora] wrote {OUT}")
