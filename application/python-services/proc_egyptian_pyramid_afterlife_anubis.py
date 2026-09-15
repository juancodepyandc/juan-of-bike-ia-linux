"""
proc_egyptian_pyramid_afterlife_anubis.py — 204e procédural AuroraIA (68e qualité)
Pyramide Egypte afterlife : Anubis chacal + prêtres momification + sarcophage + balance Maât + canopes + Thoth ibis + scarabée + 8 chats
"""
import bpy, bmesh, math, random, os

random.seed(0xA8085204)

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

# Materials
M_SKY_TOMB = mat("sky_tomb", (0.10, 0.08, 0.12, 1.0), 0.0, 0.85, emission=(0.18,0.12,0.18), emission_strength=0.8)
M_WALL = mat("wall", (0.55, 0.42, 0.28, 1.0), 0.0, 0.75, emission=(0.45,0.35,0.22), emission_strength=0.4)
M_WALL_DARK = mat("wall_dark", (0.30, 0.22, 0.15, 1.0), 0.0, 0.85)
M_FLOOR = mat("floor", (0.40, 0.30, 0.18, 1.0), 0.0, 0.80, emission=(0.35,0.25,0.15), emission_strength=0.3)
M_STONE = mat("stone", (0.60, 0.55, 0.45, 1.0), 0.0, 0.80, emission=(0.50,0.45,0.38), emission_strength=0.4)

# Anubis
M_ANUBIS_BLACK = mat("anubis_b", (0.06, 0.06, 0.08, 1.0), 0.4, 0.40, emission=(0.10,0.10,0.12), emission_strength=0.5)
M_ANUBIS_GOLD = mat("anubis_g", (1.0, 0.78, 0.25, 1.0), 0.95, 0.18, emission=(0.95,0.72,0.22), emission_strength=1.5)
M_ANUBIS_BLUE = mat("anubis_blue", (0.10, 0.30, 0.65, 1.0), 0.3, 0.35, emission=(0.10,0.30,0.65), emission_strength=1.0)
M_ANUBIS_EYE = mat("anubis_eye", (1.0, 0.55, 0.10, 1.0), 0.0, 0.15, emission=(1.0,0.55,0.10), emission_strength=12.0)

# Gold + jewels
M_GOLD = mat("gold", (1.0, 0.78, 0.25, 1.0), 0.95, 0.18, emission=(0.95,0.72,0.22), emission_strength=1.5)
M_GOLD_BRIGHT = mat("gold_b", (1.0, 0.88, 0.40, 1.0), 0.95, 0.15, emission=(1.0,0.85,0.40), emission_strength=3.0)
M_LAPIS = mat("lapis", (0.10, 0.25, 0.75, 1.0), 0.3, 0.30, emission=(0.15,0.30,0.85), emission_strength=2.5)
M_RUBY = mat("ruby", (0.85, 0.10, 0.20, 1.0), 0.3, 0.20, emission=(0.95,0.15,0.25), emission_strength=3.0)
M_EMERALD = mat("emerald", (0.10, 0.75, 0.30, 1.0), 0.3, 0.20, emission=(0.15,0.85,0.35), emission_strength=2.5)
M_TURQUOISE = mat("turquoise", (0.15, 0.85, 0.85, 1.0), 0.0, 0.25, emission=(0.20,0.90,0.90), emission_strength=2.0)

# Hiéroglyphes émissifs
M_HIEROGLYPH = mat("hiero", (1.0, 0.65, 0.20, 1.0), 0.3, 0.25, emission=(1.0,0.65,0.20), emission_strength=10.0)
M_HIEROGLYPH_BLUE = mat("hiero_b", (0.30, 0.65, 1.0, 1.0), 0.3, 0.25, emission=(0.30,0.70,1.0), emission_strength=9.0)

# Mummification
M_BANDAGE = mat("bandage", (0.88, 0.78, 0.55, 1.0), 0.0, 0.78, emission=(0.78,0.72,0.55), emission_strength=0.5)
M_BANDAGE_DARK = mat("bandage_d", (0.55, 0.45, 0.30, 1.0), 0.0, 0.82)
M_SKIN_MUMMY = mat("skin_m", (0.55, 0.42, 0.30, 1.0), 0.0, 0.85, emission=(0.45,0.35,0.25), emission_strength=0.3)

# Priests
M_SKIN_EGYPT = mat("skin_e", (0.78, 0.55, 0.35, 1.0), 0.0, 0.60, emission=(0.70,0.50,0.30), emission_strength=0.3)
M_LINEN = mat("linen", (0.95, 0.90, 0.78, 1.0), 0.0, 0.65, emission=(0.85,0.82,0.70), emission_strength=0.5)
M_LINEN_WHITE = mat("linen_w", (1.0, 0.95, 0.85, 1.0), 0.0, 0.55, emission=(0.92,0.88,0.78), emission_strength=0.6)
M_HEADDRESS = mat("headdress", (0.20, 0.35, 0.85, 1.0), 0.2, 0.40, emission=(0.18,0.32,0.78), emission_strength=0.6)

# Sarcophagus
M_SARCO = mat("sarco", (0.92, 0.75, 0.30, 1.0), 0.90, 0.20, emission=(0.85,0.70,0.28), emission_strength=1.0)
M_SARCO_FACE = mat("sarco_face", (0.85, 0.68, 0.25, 1.0), 0.92, 0.18, emission=(0.80,0.65,0.25), emission_strength=1.2)
M_SARCO_PATTERN = mat("sarco_p", (0.15, 0.25, 0.65, 1.0), 0.3, 0.30, emission=(0.18,0.30,0.70), emission_strength=1.5)

# Balance Maât
M_BALANCE_FRAME = mat("balance_f", (0.85, 0.65, 0.25, 1.0), 0.92, 0.20, emission=(0.78,0.58,0.22), emission_strength=0.9)
M_FEATHER_MAAT = mat("feather_m", (0.95, 0.92, 0.85, 1.0), 0.0, 0.45, emission=(0.95,0.92,0.85), emission_strength=3.0)
M_HEART = mat("heart", (0.85, 0.18, 0.18, 1.0), 0.0, 0.50, emission=(0.85,0.20,0.20), emission_strength=2.5)

# Canopic jars
M_CANOPIC_BODY = mat("canopic", (0.92, 0.75, 0.30, 1.0), 0.85, 0.25, emission=(0.85,0.70,0.28), emission_strength=0.8)

# Scarab
M_SCARAB = mat("scarab", (0.15, 0.20, 0.30, 1.0), 0.85, 0.20, emission=(0.30,0.50,0.85), emission_strength=4.0)
M_SCARAB_ABDOMEN = mat("scarab_a", (0.10, 0.15, 0.25, 1.0), 0.5, 0.45, emission=(0.20,0.35,0.65), emission_strength=2.5)

# Ankh
M_ANKH = mat("ankh", (1.0, 0.78, 0.30, 1.0), 0.95, 0.15, emission=(1.0,0.78,0.30), emission_strength=5.0)

# Ra solaire
M_RA_SKIN = mat("ra_skin", (0.85, 0.65, 0.35, 1.0), 0.0, 0.55, emission=(0.78,0.58,0.30), emission_strength=0.5)
M_FALCON_HEAD = mat("falcon_h", (0.55, 0.35, 0.20, 1.0), 0.0, 0.50, emission=(0.50,0.32,0.18), emission_strength=0.5)
M_SUN_DISK = mat("sun_disk", (1.0, 0.80, 0.20, 1.0), 0.85, 0.15, emission=(1.0,0.80,0.20), emission_strength=12.0)
M_RA_EYE = mat("ra_eye", (1.0, 0.55, 0.10, 1.0), 0.0, 0.15, emission=(1.0,0.55,0.10), emission_strength=8.0)

# Thoth ibis
M_IBIS_BODY = mat("ibis_b", (0.92, 0.92, 0.88, 1.0), 0.0, 0.55, emission=(0.85,0.85,0.80), emission_strength=0.5)
M_IBIS_HEAD = mat("ibis_h", (0.10, 0.08, 0.06, 1.0), 0.0, 0.50, emission=(0.10,0.08,0.06), emission_strength=0.3)
M_IBIS_BEAK = mat("ibis_beak", (0.40, 0.30, 0.20, 1.0), 0.0, 0.55)

# Cats
M_CAT_BLACK = mat("cat_b", (0.06, 0.06, 0.07, 1.0), 0.0, 0.55, emission=(0.08,0.08,0.10), emission_strength=0.3)
M_CAT_BROWN = mat("cat_br", (0.55, 0.35, 0.20, 1.0), 0.0, 0.60, emission=(0.50,0.32,0.18), emission_strength=0.4)
M_CAT_EYE = mat("cat_eye", (1.0, 0.85, 0.20, 1.0), 0.0, 0.15, emission=(1.0,0.85,0.20), emission_strength=7.0)
M_CAT_COLLAR = mat("cat_c", (1.0, 0.78, 0.25, 1.0), 0.95, 0.18, emission=(0.95,0.72,0.22), emission_strength=1.2)

# Torches
M_FLAME = mat("flame", (1.0, 0.50, 0.10, 1.0), 0.0, 0.10, emission=(1.0,0.55,0.15), emission_strength=14.0)
M_FLAME_INNER = mat("flame_in", (1.0, 0.85, 0.30, 1.0), 0.0, 0.10, emission=(1.0,0.90,0.40), emission_strength=20.0)
M_TORCH_HOLDER = mat("torch_h", (0.55, 0.42, 0.20, 1.0), 0.85, 0.30, emission=(0.50,0.38,0.18), emission_strength=0.5)

# Papyrus
M_PAPYRUS = mat("papyrus", (0.92, 0.78, 0.45, 1.0), 0.0, 0.65, emission=(0.85,0.72,0.42), emission_strength=0.6)
M_INK = mat("ink", (0.20, 0.10, 0.05, 1.0), 0.0, 0.75)

# Sand
M_SAND = mat("sand", (0.95, 0.82, 0.45, 1.0), 0.0, 0.85, emission=(0.85,0.75,0.40), emission_strength=0.6)

# ============ TOMB CHAMBER SETTING ============
# Floor
ground = beveled_cube("ground", (45, 45, 0.5), bevel_offset=0.05, loc=(0, 0, -0.25), mat_=M_FLOOR)
# 4 walls
beveled_cube("wall_back", (45, 0.5, 12), bevel_offset=0.05, loc=(0, 18, 6), mat_=M_WALL)
beveled_cube("wall_left", (0.5, 36, 12), bevel_offset=0.05, loc=(-22, 0, 6), mat_=M_WALL)
beveled_cube("wall_right", (0.5, 36, 12), bevel_offset=0.05, loc=(22, 0, 6), mat_=M_WALL)
# Ceiling (dark blue with star pattern)
beveled_cube("ceiling", (45, 36, 0.5), bevel_offset=0.05, loc=(0, 0, 12), mat_=M_SKY_TOMB)

# 30 stars on ceiling (gold)
for i in range(30):
    sx = random.uniform(-20, 20)
    sy = random.uniform(-15, 15)
    smooth_sphere(f"star_ceil{i}", r=random.uniform(0.12, 0.20), segs=8, rings=6,
                  loc=(sx, sy, 11.7), mat_=M_GOLD_BRIGHT)

# 100 HIEROGLYPHES (sur murs) émissifs
glyphs = []
for wi, (wx_base, wy_base, wz_base, wall_dir) in enumerate([
    (0, 17.7, 0, "back"),
    (-21.7, 0, 0, "left"),
    (21.7, 0, 0, "right"),
]):
    for col in range(20):
        for row in range(2):
            if wall_dir == "back":
                gx = (col - 9.5) * 2.2
                gy = wy_base
                gz = 2 + row * 4
            elif wall_dir == "left":
                gx = wx_base
                gy = (col - 9.5) * 1.6
                gz = 2 + row * 4
            else:
                gx = wx_base
                gy = (col - 9.5) * 1.6
                gz = 2 + row * 4
            color = M_HIEROGLYPH if random.random() < 0.7 else M_HIEROGLYPH_BLUE
            glyph = beveled_cube(f"glyph_{wi}_{col}_{row}", (0.25, 0.10, 0.40), bevel_offset=0.03,
                                loc=(gx, gy, gz), mat_=color)
            glyph["_phase"] = random.uniform(0, math.pi*2)
            glyphs.append(glyph)

# ============ ANUBIS GIGANTESQUE central (tête de chacal) ============
anubis_e = empty("anubis", loc=(0, 5, 0))

# Pedestal
beveled_cube("anubis_ped", (3.5, 3.5, 0.5), bevel_offset=0.06,
             loc=(0, 0, 0.25), parent=anubis_e, mat_=M_STONE)
beveled_cube("anubis_ped_top", (3.7, 3.7, 0.15), loc=(0, 0, 0.58),
             parent=anubis_e, mat_=M_WALL)

# Anubis body sitting (sphinx-like pose - paws out)
# Lower body (haunches)
beveled_cube("anubis_haunch", (2.2, 2.5, 1.2), bevel_offset=0.10,
             loc=(0, 0.30, 1.30), parent=anubis_e, mat_=M_ANUBIS_BLACK)

# Front legs (forearms outstretched)
for side in (-1, 1):
    # Upper leg
    cyl(f"anubis_arm_{side}", r=0.35, depth=2.5, segs=16,
        loc=(side*0.65, -0.80, 1.40), parent=anubis_e, mat_=M_ANUBIS_BLACK).rotation_euler = (math.radians(75), 0, 0)
    # Paw
    beveled_cube(f"anubis_paw_{side}", (0.50, 0.55, 0.30), bevel_offset=0.06,
                 loc=(side*0.65, -1.70, 0.85), parent=anubis_e, mat_=M_ANUBIS_BLACK)
    # 3 claws
    for c in range(3):
        smooth_cone(f"anubis_claw_{side}_{c}", r1=0.05, r2=0.005, depth=0.12, segs=8,
                    loc=(side*0.65 + (c-1)*0.13, -1.95, 0.85),
                    parent=anubis_e, mat_=M_GOLD).rotation_euler = (math.radians(60), 0, 0)

# Torso (rising up)
beveled_cube("anubis_torso", (1.6, 1.0, 2.0), bevel_offset=0.08,
             loc=(0, 0, 3.5), parent=anubis_e, mat_=M_ANUBIS_BLACK)

# Gold chest plate (signature pectoral)
beveled_cube("anubis_pectoral", (1.5, 0.08, 1.0), bevel_offset=0.05,
             loc=(0, -0.55, 3.6), parent=anubis_e, mat_=M_ANUBIS_GOLD)
# Pectoral gem (lapis)
smooth_sphere("anubis_pec_gem", r=0.15, loc=(0, -0.60, 3.6),
              parent=anubis_e, mat_=M_LAPIS, scale=(1, 0.5, 1))
# 3 pectoral stripes blue
for i in range(3):
    beveled_cube(f"anubis_pec_str{i}", (1.6, 0.06, 0.08),
                 loc=(0, -0.58, 3.95 + i*0.15), parent=anubis_e, mat_=M_ANUBIS_BLUE)

# Skirt (gold pleated)
smooth_cone("anubis_skirt", r1=1.1, r2=0.65, depth=0.85, segs=18,
            loc=(0, 0, 2.7), parent=anubis_e, mat_=M_ANUBIS_GOLD)
# Skirt blue stripes (signature)
for i in range(8):
    a = (i / 8.0) * math.pi * 2
    beveled_cube(f"anubis_skirt_str{i}", (0.04, 0.04, 0.85),
                 loc=(0.95*math.cos(a), 0.95*math.sin(a), 2.7),
                 parent=anubis_e, mat_=M_ANUBIS_BLUE)

# Belt
cyl("anubis_belt", r=1.0, depth=0.18, segs=18,
    loc=(0, 0, 3.0), parent=anubis_e, mat_=M_ANUBIS_GOLD)

# Neck
cyl("anubis_neck", r=0.45, depth=0.50, segs=16,
    loc=(0, 0, 4.65), parent=anubis_e, mat_=M_ANUBIS_BLACK)

# HEAD JACKAL (signature Anubis!)
head_e = empty("anubis_head_e", (0, 0, 5.30), parent=anubis_e)
# Main skull (elongated)
smooth_sphere("anubis_skull", r=0.60, segs=24, rings=18, loc=(0, 0, 0),
              parent=head_e, mat_=M_ANUBIS_BLACK, scale=(1.0, 1.8, 1.0))
# Snout (long pointed forward)
smooth_cone("anubis_snout", r1=0.35, r2=0.12, depth=0.85, segs=16,
            loc=(0, -0.90, -0.08), parent=head_e, mat_=M_ANUBIS_BLACK).rotation_euler = (math.radians(75), 0, 0)
# Nose tip
smooth_sphere("anubis_nose", r=0.08, loc=(0, -1.30, -0.20),
              parent=head_e, mat_=M_ANUBIS_BLACK)
# Mouth slit
beveled_cube("anubis_mouth", (0.15, 0.10, 0.04), loc=(0, -1.25, -0.32),
             parent=head_e, mat_=mat("am", (0.10,0.05,0.05,1), 0, 0.5))

# 2 EARS POINTED (signature jackal)
for side in (-1, 1):
    ear_e = empty(f"anubis_ear_e_{side}", (side*0.25, 0.05, 0.55), parent=head_e)
    ear_e.rotation_euler = (math.radians(-15), math.radians(side*15), 0)
    # Outer ear (large pointed)
    smooth_cone(f"anubis_ear_{side}", r1=0.18, r2=0.02, depth=0.85, segs=10,
                loc=(0, 0, 0.40), parent=ear_e, mat_=M_ANUBIS_BLACK)
    # Inner ear (pink/red)
    smooth_cone(f"anubis_ear_in_{side}", r1=0.10, r2=0.01, depth=0.70, segs=10,
                loc=(0, -0.04, 0.40), parent=ear_e, mat_=M_RUBY)

# 2 yeux orange émissifs (signature dieu)
for side in (-1, 1):
    smooth_sphere(f"anubis_eye_{side}", r=0.10,
                  loc=(side*0.25, -0.50, 0.15), parent=head_e, mat_=M_ANUBIS_EYE)
    # Pupil dark
    smooth_sphere(f"anubis_pup_{side}", r=0.04,
                  loc=(side*0.25, -0.60, 0.15), parent=head_e, mat_=mat(f"ap_{side}", (0.05,0.05,0.05,1), 0, 0.5))

# Royal headdress nemes stripes (signature)
nemes_e = empty("anubis_nemes_e", (0, 0.20, 0.30), parent=head_e)
# Side flaps
for side in (-1, 1):
    flap = beveled_cube(f"anubis_flap_{side}", (0.10, 0.55, 0.85), bevel_offset=0.04,
                       loc=(side*0.55, 0.10, -0.20), parent=nemes_e, mat_=M_ANUBIS_GOLD)
    # Blue stripes
    for i in range(3):
        beveled_cube(f"anubis_flap_str_{side}_{i}", (0.12, 0.60, 0.10),
                     loc=(side*0.55, 0.10, -0.55 + i*0.30), parent=nemes_e, mat_=M_ANUBIS_BLUE)

# URAEUS (cobra forehead) signature
uraeus_e = empty("anubis_uraeus", (0, -0.30, 0.55), parent=head_e)
cyl("uraeus_body", r=0.08, depth=0.30, segs=10,
    loc=(0, 0, 0), parent=uraeus_e, mat_=M_GOLD_BRIGHT)
smooth_sphere("uraeus_head", r=0.10, loc=(0, -0.05, 0.18),
              parent=uraeus_e, mat_=M_GOLD_BRIGHT, scale=(1, 1.2, 0.8))
# Cobra eyes
for side in (-1, 1):
    smooth_sphere(f"uraeus_eye_{side}", r=0.02, loc=(side*0.04, -0.12, 0.20),
                  parent=uraeus_e, mat_=M_RUBY)

# Anubis holds ANKH and STAFF
# Right paw holds ankh
ankh_e = empty("ankh_e", (-1.05, -1.0, 1.0), parent=anubis_e)
ankh_e.rotation_euler = (0, 0, math.radians(20))
# Vertical stem
beveled_cube("ankh_stem", (0.08, 0.10, 0.85), bevel_offset=0.02,
             loc=(0, 0, 0.4), parent=ankh_e, mat_=M_ANKH)
# Horizontal arm
beveled_cube("ankh_arm", (0.50, 0.10, 0.10), loc=(0, 0, 0.55),
             parent=ankh_e, mat_=M_ANKH)
# Loop top (donut shape approximation)
ankh_loop_e = empty("ankh_loop_e", (0, 0, 1.0), parent=ankh_e)
for i in range(8):
    a = (i / 8.0) * math.pi * 2
    smooth_sphere(f"ankh_loop{i}", r=0.06,
                  loc=(0.20*math.cos(a), 0.05, 0.20*math.sin(a)),
                  parent=ankh_loop_e, mat_=M_ANKH)

# ============ SARCOPHAGUS DORÉ (in front of Anubis) ============
sarco_e = empty("sarco", loc=(0, -3, 0.5))
# Bottom (lying flat)
beveled_cube("sarco_body", (1.5, 4.0, 0.95), bevel_offset=0.10,
             loc=(0, 0, 0.475), parent=sarco_e, mat_=M_SARCO)

# Face/lid (top with face) - elevated head
beveled_cube("sarco_lid_body", (1.4, 3.8, 0.30), bevel_offset=0.08,
             loc=(0, 0, 1.10), parent=sarco_e, mat_=M_SARCO)

# Face panel raised (front - head end)
face_e = empty("sarco_face_e", (0, -1.5, 1.30), parent=sarco_e)
smooth_sphere("sarco_face_main", r=0.45, segs=24, rings=16, loc=(0, 0, 0),
              parent=face_e, mat_=M_SARCO_FACE, scale=(1.0, 1.2, 1.3))
# Eyes (kohl outlined - black lined)
for side in (-1, 1):
    # Eye sclera
    smooth_sphere(f"sarco_eye_w_{side}", r=0.08,
                  loc=(side*0.13, -0.30, 0.10), parent=face_e,
                  mat_=mat(f"sew{side}", (0.95,0.92,0.85,1), 0, 0.4))
    # Pupil (lapis)
    smooth_sphere(f"sarco_pup_{side}", r=0.05,
                  loc=(side*0.13, -0.38, 0.10), parent=face_e, mat_=M_LAPIS)
    # Kohl liner (black extending around)
    beveled_cube(f"sarco_kohl_{side}", (0.35, 0.02, 0.04),
                 loc=(side*0.13, -0.40, 0.10), parent=face_e, mat_=mat(f"kk{side}", (0.05,0.05,0.05,1), 0, 0.5))
# Mouth (slight smile)
beveled_cube("sarco_mouth", (0.18, 0.04, 0.04), loc=(0, -0.40, -0.15),
             parent=face_e, mat_=M_RUBY)
# Nose
smooth_cone("sarco_nose", r1=0.05, r2=0.02, depth=0.18, segs=10,
            loc=(0, -0.40, 0), parent=face_e, mat_=M_SARCO_FACE).rotation_euler = (math.radians(70), 0, 0)

# NEMES headdress (signature pharaoh)
nemes_sarco_e = empty("sarco_nemes_e", (0, 0.30, 0.35), parent=face_e)
# Side flaps
for side in (-1, 1):
    flap = beveled_cube(f"sarco_flap_{side}", (0.12, 0.65, 0.85), bevel_offset=0.04,
                       loc=(side*0.50, 0, -0.15), parent=nemes_sarco_e, mat_=M_SARCO_FACE)
    for i in range(3):
        beveled_cube(f"sarco_flap_str_{side}_{i}", (0.14, 0.70, 0.10),
                     loc=(side*0.50, 0, -0.50 + i*0.30), parent=nemes_sarco_e, mat_=M_LAPIS)

# False beard (signature pharaoh, attached to chin)
beveled_cube("sarco_beard", (0.15, 0.15, 0.35), bevel_offset=0.04,
             loc=(0, -0.45, -0.40), parent=face_e, mat_=M_GOLD_BRIGHT)

# Crook + flail crossed on chest (signature)
crook_e = empty("crook_e", (0, 0.10, 1.40), parent=sarco_e)
crook_e.rotation_euler = (0, 0, math.radians(15))
# Crook (curved staff)
cyl("crook", r=0.04, depth=0.50, segs=10,
    loc=(0, 0, 0.20), parent=crook_e, mat_=M_GOLD)
# Hook top
cyl("crook_hook", r=0.04, depth=0.20, segs=10,
    loc=(0.08, 0, 0.45), parent=crook_e, mat_=M_GOLD).rotation_euler = (math.radians(60), 0, 0)
# Flail (3 beaded strands)
flail_e = empty("flail_e", (0, 0.10, 1.40), parent=sarco_e)
flail_e.rotation_euler = (0, 0, math.radians(-15))
cyl("flail_h", r=0.04, depth=0.30, segs=10,
    loc=(0, 0, 0.10), parent=flail_e, mat_=M_GOLD)
# 3 strands
for i in range(3):
    for j in range(3):
        smooth_sphere(f"flail_bead_{i}_{j}", r=0.025,
                      loc=((i-1)*0.05, 0, 0.30 + j*0.06), parent=flail_e, mat_=M_GOLD)

# Sarcophagus body patterns (3 gold bands + hieroglyphs)
for i in range(3):
    beveled_cube(f"sarco_band{i}", (1.55, 0.04, 0.10), loc=(0, 0, 0.30 + i*0.30),
                 parent=sarco_e, mat_=M_GOLD)
# 8 hieroglyphs on side
for i in range(8):
    beveled_cube(f"sarco_hiero{i}", (0.20, 0.04, 0.25), loc=(0, -1.3 + i*0.35, 0.45),
                 parent=sarco_e, mat_=M_SARCO_PATTERN)

# Arms folded across chest (visible relief)
for side in (-1, 1):
    beveled_cube(f"sarco_arm_{side}", (0.20, 0.65, 0.10),
                 loc=(side*0.20, -0.20, 1.25), parent=sarco_e, mat_=M_SARCO_FACE).rotation_euler = (0, math.radians(side*10), 0)
    # Hand
    smooth_sphere(f"sarco_hand_{side}", r=0.10, loc=(side*0.10, -0.50, 1.30),
                  parent=sarco_e, mat_=M_SARCO_FACE)

# ============ 3 PRIESTS doing mummification ritual ============
def make_priest(name, loc, action="bandage", facing=0):
    base = empty(name, loc)
    base.rotation_euler = (0, 0, facing)
    # Legs
    for side_idx, side in enumerate((-1, 1)):
        cyl(f"{name}_leg{side_idx}", r=0.11, depth=0.85, segs=10,
            loc=(side*0.13, 0, 0.42), parent=base, mat_=M_SKIN_EGYPT)
        beveled_cube(f"{name}_sand{side_idx}", (0.18, 0.26, 0.06),
                     loc=(side*0.13, 0.04, 0.04), parent=base, mat_=M_BANDAGE_DARK)
    # Linen kilt (signature ancient Egypt)
    smooth_cone(f"{name}_kilt", r1=0.40, r2=0.30, depth=0.65, segs=14,
                loc=(0, 0, 1.0), parent=base, mat_=M_LINEN_WHITE)
    # Belt
    beveled_cube(f"{name}_belt", (0.65, 0.40, 0.06), loc=(0, 0, 1.30),
                 parent=base, mat_=M_GOLD)
    # Bare torso (Egyptian style)
    beveled_cube(f"{name}_torso", (0.42, 0.25, 0.65), bevel_offset=0.05,
                 loc=(0, 0, 1.65), parent=base, mat_=M_SKIN_EGYPT)
    # Wesekh collar (gold ornate disc, signature)
    cyl(f"{name}_wesekh", r=0.30, depth=0.06, segs=20,
        loc=(0, -0.10, 1.90), parent=base, mat_=M_GOLD).rotation_euler = (math.radians(85), 0, 0)
    # Wesekh stones (4 alternating)
    for i in range(4):
        a = (i / 4.0) * math.pi - math.pi/2
        col = [M_LAPIS, M_TURQUOISE, M_RUBY, M_EMERALD][i % 4]
        smooth_sphere(f"{name}_wes_g{i}", r=0.05,
                      loc=(0.22*math.sin(a), -0.10, 1.97), parent=base, mat_=col)
    # Neck
    cyl(f"{name}_neck", r=0.09, depth=0.15, segs=10,
        loc=(0, 0, 2.05), parent=base, mat_=M_SKIN_EGYPT)
    # Head
    head_e = empty(f"{name}_head_e", (0, 0, 2.25), parent=base)
    smooth_sphere(f"{name}_head", r=0.20, segs=20, rings=14, loc=(0,0,0),
                  parent=head_e, mat_=M_SKIN_EGYPT)
    # Eyes (kohl outlined)
    for side in (-1, 1):
        # Kohl liner
        beveled_cube(f"{name}_kohl_{side}", (0.10, 0.02, 0.025),
                     loc=(side*0.07, -0.18, 0.03), parent=head_e, mat_=mat(f"{name}_kk{side}", (0.05,0.05,0.05,1), 0, 0.5))
        smooth_sphere(f"{name}_eye_{side}", r=0.025,
                      loc=(side*0.07, -0.16, 0.03), parent=head_e,
                      mat_=mat(f"{name}_ew{side}", (0.95,0.92,0.85,1), 0, 0.4))
    # Bald head (priests shaven, signature) - no hair sphere
    # Nemes-like cloth (blue stripes) headcloth
    nemes_p_e = empty(f"{name}_nemes_e", (0, 0, 0.20), parent=head_e)
    # Top dome
    smooth_sphere(f"{name}_nemes_top", r=0.22, loc=(0, 0, -0.04), parent=nemes_p_e,
                  mat_=M_HEADDRESS, scale=(1.05, 1.05, 0.5))
    # Side flaps
    for side in (-1, 1):
        flap = beveled_cube(f"{name}_nemes_flap_{side}", (0.06, 0.30, 0.40), bevel_offset=0.02,
                           loc=(side*0.22, 0.05, -0.15), parent=nemes_p_e, mat_=M_HEADDRESS)
    # Stripes
    for i in range(3):
        cyl(f"{name}_nemes_str{i}", r=0.23, depth=0.04, segs=18,
            loc=(0, 0, -0.10 + i*0.07), parent=nemes_p_e, mat_=M_GOLD)
    # 2 arms (action-dependent)
    arm_poses = {
        "bandage": [(math.radians(-90), -10), (math.radians(-90), 10)],
        "praying": [(math.radians(-140), -10), (math.radians(-140), 10)],
        "carrying": [(math.radians(-70), -15), (math.radians(-70), 15)],
        "writing": [(math.radians(-80), -20), (math.radians(-90), 30)],
    }
    pose = arm_poses.get(action, arm_poses["bandage"])
    arms_e = {}
    for side_idx, side in enumerate((-1, 1)):
        sh = empty(f"{name}_sh{side_idx}", (side*0.22, 0, 2.05), parent=base)
        rx, rz = pose[side_idx]
        sh.rotation_euler = (rx, 0, math.radians(side*-15 + rz))
        cyl(f"{name}_up{side_idx}", r=0.06, depth=0.35, segs=10,
            loc=(0, 0, -0.18), parent=sh, mat_=M_SKIN_EGYPT)
        el = empty(f"{name}_el{side_idx}", (0, 0, -0.37), parent=sh)
        el.rotation_euler = (math.radians(30 if side == -1 else 40), 0, 0)
        cyl(f"{name}_fa{side_idx}", r=0.055, depth=0.33, segs=10,
            loc=(0, 0, -0.16), parent=el, mat_=M_SKIN_EGYPT)
        # Hand
        hand = empty(f"{name}_hand{side_idx}", (0, 0, -0.38), parent=el)
        smooth_sphere(f"{name}_h{side_idx}", r=0.06, loc=(0,0,0),
                      parent=hand, mat_=M_SKIN_EGYPT)
        arms_e[f"sh{side_idx}"] = sh
        arms_e[f"hand{side_idx}"] = hand
    # If bandaging, add bandage roll in hand
    if action == "bandage":
        cyl(f"{name}_bandage_roll", r=0.10, depth=0.15, segs=14,
            loc=(0, 0, -0.10), parent=arms_e["hand0"], mat_=M_BANDAGE)
        # Trailing bandage strip
        beveled_cube(f"{name}_bandage_strip", (0.20, 0.02, 0.50), bevel_offset=0.01,
                     loc=(0, 0, -0.30), parent=arms_e["hand0"], mat_=M_BANDAGE)
    return {"root": base, "head_e": head_e, "sh0": arms_e["sh0"], "sh1": arms_e["sh1"]}

priests = []
priest_specs = [
    ("priest1", (-2.5, -3, 0.5), "bandage", math.radians(90)),
    ("priest2", (2.5, -3, 0.5), "bandage", math.radians(-90)),
    ("priest3", (0, -5.5, 0.5), "praying", math.radians(0)),
]
for spec in priest_specs:
    p = make_priest(*spec)
    priests.append(p)

# ============ BALANCE OF MAÂT (judgment scales) ============
balance_e = empty("balance", loc=(-7, -3, 0))
# Base
beveled_cube("bal_base", (1.5, 1.5, 0.30), bevel_offset=0.05,
             loc=(0, 0, 0.15), parent=balance_e, mat_=M_STONE)
# Vertical pole
cyl("bal_pole", r=0.06, depth=3.0, segs=12,
    loc=(0, 0, 1.7), parent=balance_e, mat_=M_BALANCE_FRAME)
# Crossbeam horizontal
beveled_cube("bal_crossbeam", (3.5, 0.10, 0.10), loc=(0, 0, 3.10),
             parent=balance_e, mat_=M_BALANCE_FRAME)
# Center pivot ornament
smooth_sphere("bal_pivot", r=0.15, loc=(0, 0, 3.10),
              parent=balance_e, mat_=M_GOLD_BRIGHT)

# 2 pans hanging
# Pan with FEATHER OF MAÂT (left)
pan_left_e = empty("pan_l_e", (-1.7, 0, 3.10), parent=balance_e)
# Chain (3 strands)
for i in range(3):
    a = (i / 3.0) * math.pi * 2
    cyl(f"chain_l{i}", r=0.015, depth=0.6, segs=6,
        loc=(0.15*math.cos(a), 0.15*math.sin(a), -0.30), parent=pan_left_e, mat_=M_BALANCE_FRAME)
# Pan disc
cyl("pan_l_disc", r=0.40, depth=0.05, segs=18,
    loc=(0, 0, -0.65), parent=pan_left_e, mat_=M_BALANCE_FRAME)
# FEATHER MAÂT (white feather standing) signature
feather_e = empty("feather_maat_e", (0, 0, -0.62), parent=pan_left_e)
# Quill stem
cyl("feather_stem", r=0.015, depth=0.40, segs=8,
    loc=(0, 0, 0.20), parent=feather_e, mat_=M_FEATHER_MAAT)
# Vanes (4 layers expanding)
for i in range(5):
    w = 0.06 + i*0.02
    beveled_cube(f"feather_v{i}", (w, 0.01, 0.10), bevel_offset=0.01,
                 loc=(0, 0, 0.05 + i*0.07), parent=feather_e, mat_=M_FEATHER_MAAT)
# Pen tip
smooth_cone("feather_tip", r1=0.02, r2=0.005, depth=0.05, segs=6,
            loc=(0, 0, 0.42), parent=feather_e, mat_=M_FEATHER_MAAT)

# Pan with HEART (right)
pan_right_e = empty("pan_r_e", (1.7, 0, 3.10), parent=balance_e)
for i in range(3):
    a = (i / 3.0) * math.pi * 2
    cyl(f"chain_r{i}", r=0.015, depth=0.6, segs=6,
        loc=(0.15*math.cos(a), 0.15*math.sin(a), -0.30), parent=pan_right_e, mat_=M_BALANCE_FRAME)
cyl("pan_r_disc", r=0.40, depth=0.05, segs=18,
    loc=(0, 0, -0.65), parent=pan_right_e, mat_=M_BALANCE_FRAME)
# HEART (signature anatomical Egypt heart)
heart_e = empty("heart_e", (0, 0, -0.55), parent=pan_right_e)
smooth_sphere("heart_main", r=0.18, segs=22, rings=14, loc=(0, 0, 0),
              parent=heart_e, mat_=M_HEART, scale=(1, 1.2, 1.15))
smooth_sphere("heart_top1", r=0.10, loc=(-0.07, -0.05, 0.10),
              parent=heart_e, mat_=M_HEART)
smooth_sphere("heart_top2", r=0.10, loc=(0.07, -0.05, 0.10),
              parent=heart_e, mat_=M_HEART)
# Arteries
cyl("heart_artery", r=0.02, depth=0.10, segs=8,
    loc=(0, 0, 0.18), parent=heart_e, mat_=M_HEART)

# ============ 4 CANOPIC JARS (with animal heads) ============
canopic_specs = [
    ("imsety_human", "human"),      # liver - human head
    ("hapi_baboon", "baboon"),      # lungs - baboon head
    ("duamutef_jackal", "jackal"),  # stomach - jackal
    ("qebehsenuef_falcon", "falcon"), # intestines - falcon
]
for ci, (name_c, animal) in enumerate(canopic_specs):
    a = (ci / 4.0) * math.pi/2 + math.pi/4
    rad = 2.5
    cx = math.cos(a) * rad
    cy = -3 + math.sin(a) * rad - 1.0
    c_e = empty(f"canopic{ci}", (cx, cy, 0.5))
    # Body (jar)
    smooth_sphere(f"canopic_body{ci}", r=0.40, segs=20, rings=16, loc=(0, 0, 0.30),
                  parent=c_e, mat_=M_CANOPIC_BODY, scale=(1, 1, 1.4))
    # Neck
    cyl(f"canopic_neck{ci}", r=0.20, depth=0.25, segs=14,
        loc=(0, 0, 0.85), parent=c_e, mat_=M_CANOPIC_BODY)
    # Head (animal-shaped lid)
    head_e = empty(f"canopic_head{ci}", (0, 0, 1.05), parent=c_e)
    if animal == "human":
        smooth_sphere(f"can_h{ci}", r=0.20, loc=(0, 0, 0.10),
                      parent=head_e, mat_=M_SKIN_EGYPT)
        # Nemes-like flaps
        for side in (-1, 1):
            beveled_cube(f"can_flap{ci}_{side}", (0.04, 0.06, 0.20), bevel_offset=0.01,
                         loc=(side*0.18, 0.03, 0.10), parent=head_e, mat_=M_LAPIS)
    elif animal == "baboon":
        smooth_sphere(f"can_h{ci}", r=0.22, loc=(0, 0, 0.10),
                      parent=head_e, mat_=M_CAT_BROWN, scale=(1, 1.1, 1))
        # Long snout
        smooth_sphere(f"can_snout{ci}", r=0.10, loc=(0, -0.15, 0.05),
                      parent=head_e, mat_=M_CAT_BROWN, scale=(1, 1.5, 0.8))
        # 2 ears
        for side in (-1, 1):
            smooth_sphere(f"can_ear{ci}_{side}", r=0.06,
                          loc=(side*0.15, 0.05, 0.20), parent=head_e, mat_=M_CAT_BROWN)
    elif animal == "jackal":
        smooth_sphere(f"can_h{ci}", r=0.18, loc=(0, 0, 0.10),
                      parent=head_e, mat_=M_ANUBIS_BLACK, scale=(1, 1.5, 1))
        # Long snout
        smooth_cone(f"can_snout{ci}", r1=0.10, r2=0.04, depth=0.25, segs=10,
                    loc=(0, -0.15, 0.05), parent=head_e, mat_=M_ANUBIS_BLACK).rotation_euler = (math.radians(75), 0, 0)
        # Pointed ears
        for side in (-1, 1):
            smooth_cone(f"can_ear{ci}_{side}", r1=0.06, r2=0.005, depth=0.20, segs=8,
                        loc=(side*0.10, 0.06, 0.25), parent=head_e, mat_=M_ANUBIS_BLACK).rotation_euler = (0, math.radians(side*15), 0)
    elif animal == "falcon":
        smooth_sphere(f"can_h{ci}", r=0.18, loc=(0, 0, 0.10),
                      parent=head_e, mat_=M_FALCON_HEAD)
        # Hooked beak
        smooth_cone(f"can_beak{ci}", r1=0.06, r2=0.01, depth=0.15, segs=10,
                    loc=(0, -0.18, 0.06), parent=head_e, mat_=mat(f"cb{ci}", (0.85,0.55,0.20,1), 0, 0.4)).rotation_euler = (math.radians(70), 0, 0)
        # Markings around eyes
        for side in (-1, 1):
            beveled_cube(f"can_mark{ci}_{side}", (0.05, 0.03, 0.10),
                         loc=(side*0.10, -0.13, 0.10), parent=head_e, mat_=M_ANUBIS_BLACK)
    # Eyes (for all)
    for side in (-1, 1):
        smooth_sphere(f"can_eye{ci}_{side}", r=0.025, loc=(side*0.08, -0.16, 0.10),
                      parent=head_e, mat_=mat(f"cew{ci}_{side}", (0.05,0.05,0.05,1), 0, 0.4))
    # Decorative band on jar
    cyl(f"canopic_band{ci}", r=0.42, depth=0.06, segs=20,
        loc=(0, 0, 0.55), parent=c_e, mat_=M_LAPIS)

# ============ SCARABÉE GÉANT émissif (signature Khepri) ============
scarab_e = empty("scarab", loc=(0, -8, 0.5))
# Main body (oval beetle)
smooth_sphere("scarab_body", r=0.85, segs=24, rings=16, loc=(0, 0, 0.40),
              parent=scarab_e, mat_=M_SCARAB, scale=(1.3, 1.6, 0.55))
# Abdomen segments (3 lines visible)
for i in range(3):
    cyl(f"scarab_seg{i}", r=0.78, depth=0.06, segs=20,
        loc=(0, -0.3 + i*0.40, 0.50), parent=scarab_e, mat_=M_SCARAB_ABDOMEN).rotation_euler = (0, math.radians(90), 0)
# Head (smaller front)
smooth_sphere("scarab_head", r=0.30, loc=(0, 0.85, 0.40),
              parent=scarab_e, mat_=M_SCARAB, scale=(1.3, 0.8, 0.6))
# Mandibles (2)
for side in (-1, 1):
    mand = smooth_cone(f"scarab_mand_{side}", r1=0.08, r2=0.01, depth=0.20, segs=8,
                      loc=(side*0.15, 1.10, 0.40), parent=scarab_e, mat_=M_SCARAB).rotation_euler = (math.radians(70), 0, math.radians(side*20))
# 6 legs (3 each side)
for side_idx, side in enumerate((-1, 1)):
    for li in range(3):
        ly = -0.5 + li * 0.5
        leg = beveled_cube(f"scarab_leg_{side_idx}_{li}", (0.06, 0.05, 0.45),
                          loc=(side*0.85, ly, 0.30), parent=scarab_e, mat_=M_SCARAB_ABDOMEN)
        leg.rotation_euler = (0, math.radians(side*40), 0)
        # Joint segment
        beveled_cube(f"scarab_leg_j_{side_idx}_{li}", (0.04, 0.04, 0.20),
                     loc=(side*1.05, ly, 0.10), parent=scarab_e, mat_=M_SCARAB_ABDOMEN)
# Sun disc on back (signature Khepri)
cyl("scarab_disc", r=0.30, depth=0.05, segs=20,
    loc=(0, 0, 0.80), parent=scarab_e, mat_=M_SUN_DISK)
# 2 wings (folded above back)
for side in (-1, 1):
    wing = beveled_cube(f"scarab_wing_{side}", (0.04, 1.4, 0.85), bevel_offset=0.04,
                       loc=(side*0.30, 0, 0.65), parent=scarab_e, mat_=M_LAPIS)
    wing.rotation_euler = (0, math.radians(side*20), 0)
# 2 antennae
for side in (-1, 1):
    cyl(f"scarab_ant_{side}", r=0.02, depth=0.30, segs=8,
        loc=(side*0.10, 1.15, 0.55), parent=scarab_e, mat_=M_SCARAB).rotation_euler = (math.radians(-60), 0, math.radians(side*15))

# ============ RA SOLAR GOD (falcon-headed enthroned, signature) ============
ra_e = empty("ra", loc=(8, -3, 0))
# Throne
beveled_cube("ra_throne", (1.5, 1.5, 1.0), bevel_offset=0.10,
             loc=(0, 0, 0.5), parent=ra_e, mat_=M_GOLD)
# Throne back
beveled_cube("ra_throne_back", (1.5, 0.20, 2.5), bevel_offset=0.08,
             loc=(0, 0.65, 1.25), parent=ra_e, mat_=M_GOLD_BRIGHT)
# 2 lions (armrests)
for side in (-1, 1):
    smooth_sphere(f"ra_lion_{side}", r=0.30, loc=(side*0.75, -0.10, 1.20),
                  parent=ra_e, mat_=M_GOLD, scale=(1, 1.3, 1))
    # Lion head
    smooth_sphere(f"ra_lion_h_{side}", r=0.20, loc=(side*0.75, -0.55, 1.20),
                  parent=ra_e, mat_=M_GOLD_BRIGHT)
# Ra body (sitting)
# Legs/lap (cone going forward)
beveled_cube("ra_lap", (0.70, 0.85, 0.45), bevel_offset=0.06,
             loc=(0, -0.30, 1.20), parent=ra_e, mat_=M_LINEN_WHITE)
# Torso
beveled_cube("ra_torso", (0.65, 0.40, 1.0), bevel_offset=0.06,
             loc=(0, 0, 2.0), parent=ra_e, mat_=M_RA_SKIN)
# Wesekh collar gold
cyl("ra_collar", r=0.45, depth=0.08, segs=20,
    loc=(0, -0.20, 2.40), parent=ra_e, mat_=M_GOLD_BRIGHT).rotation_euler = (math.radians(85), 0, 0)
# Gem inlay on collar (rainbow)
for ji in range(6):
    a = (ji / 6.0) * math.pi - math.pi/2
    col = [M_LAPIS, M_TURQUOISE, M_RUBY, M_EMERALD, M_LAPIS, M_TURQUOISE][ji % 6]
    smooth_sphere(f"ra_col_gem{ji}", r=0.05, loc=(0.35*math.sin(a), -0.20, 2.42),
                  parent=ra_e, mat_=col)
# Falcon head (signature Ra)
ra_head_e = empty("ra_head_e", (0, 0, 2.85), parent=ra_e)
smooth_sphere("ra_falcon_head", r=0.30, segs=22, rings=14, loc=(0, 0, 0),
              parent=ra_head_e, mat_=M_FALCON_HEAD, scale=(1, 1.2, 1))
# Hooked beak (signature falcon)
smooth_cone("ra_beak", r1=0.10, r2=0.02, depth=0.25, segs=10,
            loc=(0, -0.30, -0.05), parent=ra_head_e, mat_=mat("rb", (0.85, 0.55, 0.20, 1), 0, 0.4)).rotation_euler = (math.radians(70), 0, 0)
# 2 falcon eyes émissifs
for side in (-1, 1):
    smooth_sphere(f"ra_eye_{side}", r=0.06, loc=(side*0.12, -0.22, 0.10),
                  parent=ra_head_e, mat_=M_RA_EYE)
# Eye markings (cobra-like around eye)
for side in (-1, 1):
    beveled_cube(f"ra_mark_{side}", (0.15, 0.04, 0.04), loc=(side*0.12, -0.27, 0.15),
                 parent=ra_head_e, mat_=M_ANUBIS_BLACK)
# SUN DISK on head (signature Ra-Horakhty)
smooth_sphere("ra_sun_disk", r=0.40, loc=(0, 0.10, 0.45),
              parent=ra_head_e, mat_=M_SUN_DISK)
# Cobra around sun disk
cyl("ra_cobra", r=0.05, depth=0.30, segs=10,
    loc=(0, -0.20, 0.45), parent=ra_head_e, mat_=M_GOLD_BRIGHT).rotation_euler = (math.radians(70), 0, 0)
smooth_sphere("ra_cobra_h", r=0.07, loc=(0, -0.35, 0.60),
              parent=ra_head_e, mat_=M_GOLD_BRIGHT)
# 2 arms
for side_idx, side in enumerate((-1, 1)):
    sh = empty(f"ra_sh{side_idx}", (side*0.32, 0, 2.45), parent=ra_e)
    sh.rotation_euler = (math.radians(-30), 0, math.radians(side*-15))
    cyl(f"ra_up{side_idx}", r=0.08, depth=0.40, segs=10,
        loc=(0, 0, -0.20), parent=sh, mat_=M_RA_SKIN)
    cyl(f"ra_fa{side_idx}", r=0.07, depth=0.38, segs=10,
        loc=(0, 0, -0.60), parent=sh, mat_=M_RA_SKIN)
    # Hand
    smooth_sphere(f"ra_hand{side_idx}", r=0.08, loc=(0, 0, -0.80),
                  parent=sh, mat_=M_RA_SKIN)
# Crook in right hand
crook_ra_e = empty("ra_crook", (0.42, -0.30, 1.60), parent=ra_e)
cyl("ra_crook_pole", r=0.04, depth=0.80, segs=10,
    loc=(0, 0, 0.40), parent=crook_ra_e, mat_=M_GOLD)
smooth_cone("ra_crook_hook", r1=0.06, r2=0.02, depth=0.18, segs=10,
            loc=(0.10, 0, 0.85), parent=crook_ra_e, mat_=M_GOLD).rotation_euler = (math.radians(50), 0, 0)

# ============ THOTH IBIS-HEADED GOD writing papyrus ============
thoth_e = empty("thoth", loc=(-8, -3, 0))
# Legs
for side_idx, side in enumerate((-1, 1)):
    cyl(f"thoth_leg{side_idx}", r=0.11, depth=0.85, segs=10,
        loc=(side*0.13, 0, 0.42), parent=thoth_e, mat_=M_SKIN_EGYPT)
# Kilt
smooth_cone("thoth_kilt", r1=0.40, r2=0.30, depth=0.65, segs=14,
            loc=(0, 0, 1.0), parent=thoth_e, mat_=M_LINEN_WHITE)
# Torso
beveled_cube("thoth_torso", (0.42, 0.25, 0.85), bevel_offset=0.05,
             loc=(0, 0, 1.75), parent=thoth_e, mat_=M_SKIN_EGYPT)
# Wesekh collar
cyl("thoth_collar", r=0.30, depth=0.06, segs=20,
    loc=(0, -0.10, 2.20), parent=thoth_e, mat_=M_GOLD).rotation_euler = (math.radians(85), 0, 0)
# Neck
cyl("thoth_neck", r=0.10, depth=0.15, segs=10,
    loc=(0, 0, 2.30), parent=thoth_e, mat_=M_SKIN_EGYPT)
# IBIS HEAD (signature Thoth)
thoth_head_e = empty("thoth_head_e", (0, 0, 2.55), parent=thoth_e)
# White ibis head body
smooth_sphere("thoth_h", r=0.22, segs=22, rings=14, loc=(0, 0, 0),
              parent=thoth_head_e, mat_=M_IBIS_HEAD)
# Long curved beak (signature ibis)
beak_e = empty("thoth_beak_e", (0, -0.20, -0.05), parent=thoth_head_e)
beak_e.rotation_euler = (math.radians(75), 0, 0)
for i in range(4):
    seg = cyl(f"thoth_beak{i}", r=0.04 - i*0.005, depth=0.18, segs=8,
             loc=(0, 0, i*0.18), parent=beak_e, mat_=M_IBIS_BEAK)
    seg.rotation_euler = (math.radians(-i*8), 0, 0)
# Eyes (small)
for side in (-1, 1):
    smooth_sphere(f"thoth_eye_{side}", r=0.04,
                  loc=(side*0.10, -0.15, 0.08), parent=thoth_head_e, mat_=M_GOLD_BRIGHT)
# Moon disc on top (signature Thoth)
moon_disc = cyl("thoth_moon", r=0.18, depth=0.04, segs=18,
                 loc=(0, 0.05, 0.30), parent=thoth_head_e, mat_=M_FEATHER_MAAT)
# Crescent
smooth_sphere("thoth_crescent", r=0.20, loc=(0, 0.05, 0.30),
              parent=thoth_head_e, mat_=M_FEATHER_MAAT, scale=(1, 0.2, 0.6))
# 2 arms holding papyrus + reed pen
# Left hand holds PAPYRUS
l_sh = empty("thoth_l_sh", (-0.22, 0, 2.10), parent=thoth_e)
l_sh.rotation_euler = (math.radians(-80), 0, math.radians(20))
cyl("thoth_l_up", r=0.06, depth=0.35, segs=10,
    loc=(0, 0, -0.18), parent=l_sh, mat_=M_SKIN_EGYPT)
cyl("thoth_l_fa", r=0.055, depth=0.35, segs=10,
    loc=(0, 0, -0.55), parent=l_sh, mat_=M_SKIN_EGYPT)
# PAPYRUS scroll unrolled in left hand
papyrus_e = empty("papyrus_e", (0, 0, -0.80), parent=l_sh)
papyrus_e.rotation_euler = (math.radians(40), 0, 0)
beveled_cube("papyrus_sheet", (0.50, 0.04, 0.40), bevel_offset=0.02,
             loc=(0, 0, 0), parent=papyrus_e, mat_=M_PAPYRUS)
# Hieroglyphs on papyrus (4 rows)
for i in range(4):
    for j in range(3):
        beveled_cube(f"pap_glyph_{i}_{j}", (0.08, 0.005, 0.06),
                     loc=((j-1)*0.13, -0.025, -0.12 + i*0.07), parent=papyrus_e, mat_=M_INK)
# Right hand holds REED PEN
r_sh = empty("thoth_r_sh", (0.22, 0, 2.10), parent=thoth_e)
r_sh.rotation_euler = (math.radians(-90), 0, math.radians(-30))
cyl("thoth_r_up", r=0.06, depth=0.35, segs=10,
    loc=(0, 0, -0.18), parent=r_sh, mat_=M_SKIN_EGYPT)
cyl("thoth_r_fa", r=0.055, depth=0.35, segs=10,
    loc=(0, 0, -0.55), parent=r_sh, mat_=M_SKIN_EGYPT)
# Reed pen
pen_e = empty("pen_e", (0, 0, -0.80), parent=r_sh)
cyl("pen_shaft", r=0.012, depth=0.20, segs=8,
    loc=(0, 0, 0), parent=pen_e, mat_=M_INK)
smooth_cone("pen_tip", r1=0.012, r2=0.002, depth=0.05, segs=6,
            loc=(0, 0, 0.12), parent=pen_e, mat_=M_INK)

# ============ 6 COLUMNS HIEROGLYPHES ============
columns_pos = [(-15, 8), (-5, 8), (5, 8), (15, 8), (-10, -10), (10, -10)]
for ci, (cx, cy) in enumerate(columns_pos):
    col_e = empty(f"col_e{ci}", (cx, cy, 0))
    # Base
    cyl(f"col_base{ci}", r=0.85, depth=0.40, segs=20,
        loc=(0, 0, 0.20), parent=col_e, mat_=M_STONE)
    # Shaft
    cyl(f"col_shaft{ci}", r=0.65, depth=8.5, segs=20,
        loc=(0, 0, 4.65), parent=col_e, mat_=M_WALL)
    # Hieroglyph carvings (6 per column)
    for hi in range(6):
        ha = (hi / 6.0) * math.pi * 2
        beveled_cube(f"col_hi_{ci}_{hi}", (0.20, 0.10, 0.40), bevel_offset=0.03,
                     loc=(0.66*math.cos(ha), 0.66*math.sin(ha), 2 + hi*0.9),
                     parent=col_e, mat_=M_HIEROGLYPH)
    # Lotus capital top (signature Egypt)
    smooth_cone(f"col_cap{ci}", r1=1.0, r2=0.65, depth=0.50, segs=20,
                loc=(0, 0, 9.15), parent=col_e, mat_=M_STONE)
    # Capital top disc
    cyl(f"col_top{ci}", r=1.1, depth=0.20, segs=20,
        loc=(0, 0, 9.50), parent=col_e, mat_=M_GOLD)
    # 6 lotus petals around top
    for li in range(6):
        a = (li / 6.0) * math.pi * 2
        petal = smooth_cone(f"col_petal_{ci}_{li}", r1=0.12, r2=0.02, depth=0.50, segs=8,
                            loc=(0.85*math.cos(a), 0.85*math.sin(a), 9.30),
                            parent=col_e, mat_=M_LAPIS)
        petal.rotation_euler = (math.radians(40*math.cos(a)),
                                math.radians(40*math.sin(a)), 0)

# ============ TORCHES ON WALLS (8) ============
torches = []
torch_positions = []
for i in range(4):
    torch_positions.append(((-15 + i*10), 17, 5))   # back wall
    torch_positions.append(((-15 + i*10), -15, 5))  # near priests area but valid
torch_positions = torch_positions[:8]
for ti, (tx, ty, tz) in enumerate(torch_positions):
    t_e = empty(f"torch_e{ti}", (tx, ty, tz))
    # Wall bracket
    beveled_cube(f"torch_bracket{ti}", (0.30, 0.10, 0.25), bevel_offset=0.03,
                 loc=(0, 0, 0), parent=t_e, mat_=M_TORCH_HOLDER)
    # Stick
    cyl(f"torch_stick{ti}", r=0.05, depth=0.45, segs=10,
        loc=(0, -0.10, 0.10), parent=t_e, mat_=M_WALL_DARK).rotation_euler = (math.radians(15), 0, 0)
    # Flames
    flame_o = smooth_cone(f"torch_fl_o{ti}", r1=0.20, r2=0.02, depth=0.65, segs=10,
                          loc=(0, -0.20, 0.45), parent=t_e, mat_=M_FLAME)
    flame_i = smooth_cone(f"torch_fl_i{ti}", r1=0.12, r2=0.01, depth=0.50, segs=10,
                          loc=(0, -0.20, 0.50), parent=t_e, mat_=M_FLAME_INNER)
    torches.append({"e": t_e, "outer": flame_o, "inner": flame_i,
                    "phase": ti * 0.5})

# ============ 8 EGYPTIAN CATS ============
cats = []
for ci in range(8):
    a = (ci / 8.0) * math.pi * 2 + 0.3
    rad = random.uniform(4, 10)
    cx = math.cos(a) * rad
    cy = math.sin(a) * rad - 2
    # Avoid sarcophagus area
    if abs(cy) < 4 and abs(cx) < 2:
        cy = -8
        cx = (ci - 4) * 1.5
    cat_e = empty(f"cat{ci}", (cx, cy, 0))
    cat_e.rotation_euler = (0, 0, random.uniform(-math.pi, math.pi))
    color = M_CAT_BLACK if random.random() < 0.6 else M_CAT_BROWN
    # Body sitting (Egyptian cat statue pose)
    smooth_sphere(f"cat_body{ci}", r=0.20, segs=20, rings=14, loc=(0, 0, 0.45),
                  parent=cat_e, mat_=color, scale=(1, 1.4, 1.0))
    # Sitting front legs (vertical)
    for side in (-1, 1):
        cyl(f"cat_fleg{ci}_{side}", r=0.05, depth=0.45, segs=10,
            loc=(side*0.10, -0.30, 0.22), parent=cat_e, mat_=color)
    # Head
    head_e = empty(f"cat_h_e{ci}", (0, -0.30, 0.80), parent=cat_e)
    smooth_sphere(f"cat_h{ci}", r=0.16, segs=20, rings=14, loc=(0, 0, 0),
                  parent=head_e, mat_=color, scale=(1, 0.9, 0.95))
    # Pointed ears
    for side in (-1, 1):
        ear = smooth_cone(f"cat_ear{ci}_{side}", r1=0.06, r2=0.005, depth=0.16, segs=8,
                         loc=(side*0.10, 0.05, 0.16), parent=head_e, mat_=color)
        ear.rotation_euler = (math.radians(-10), math.radians(side*15), 0)
    # Eyes yellow émissifs (signature Egyptian cat)
    for side in (-1, 1):
        smooth_sphere(f"cat_eye{ci}_{side}", r=0.05,
                      loc=(side*0.07, -0.13, 0.03), parent=head_e, mat_=M_CAT_EYE)
        # Slit pupil
        beveled_cube(f"cat_pup{ci}_{side}", (0.015, 0.005, 0.05),
                     loc=(side*0.07, -0.17, 0.03), parent=head_e, mat_=mat(f"cp{ci}_{side}", (0.05,0.05,0.05,1), 0, 0.5))
    # Nose pink
    smooth_sphere(f"cat_nose{ci}", r=0.02, loc=(0, -0.15, -0.04),
                  parent=head_e, mat_=mat(f"cn{ci}", (0.85, 0.40, 0.55, 1.0), 0, 0.55))
    # GOLD COLLAR (signature Egyptian cat - cats were sacred)
    cyl(f"cat_collar{ci}", r=0.13, depth=0.06, segs=14,
        loc=(0, 0, -0.10), parent=head_e, mat_=M_CAT_COLLAR)
    # Pendant
    smooth_sphere(f"cat_pendant{ci}", r=0.04, loc=(0, -0.15, -0.18),
                  parent=head_e, mat_=M_CAT_COLLAR, scale=(1, 1.3, 1))
    # Tail (curled around body)
    tail_e = empty(f"cat_tail_e{ci}", (0, 0.30, 0.45), parent=cat_e)
    for ti in range(5):
        a = ti * 0.5
        cyl(f"cat_tail{ci}_{ti}", r=0.04 - ti*0.005, depth=0.15, segs=10,
            loc=(0.15*math.sin(a), 0.15*math.cos(a), -ti*0.05), parent=tail_e, mat_=color)
    cats.append({"e": cat_e, "tail": tail_e, "head": head_e, "phase": random.uniform(0, math.pi*2)})

# ============ 200 SAND PARTICLES ============
sands = []
for i in range(200):
    sx = random.uniform(-21, 21)
    sy = random.uniform(-17, 17)
    sz = random.uniform(0.3, 10)
    sp = smooth_sphere(f"sand{i}", r=random.uniform(0.04, 0.08), segs=6, rings=4,
                      loc=(sx, sy, sz), mat_=M_SAND)
    sp["_phase"] = random.uniform(0, math.pi*2)
    sp["_base_x"] = sx; sp["_base_y"] = sy; sp["_base_z"] = sz
    sp["_speed"] = random.uniform(0.3, 0.8)
    sands.append(sp)

# ============ ANIMATION ============
fps = 30; duration_s = 6; total_frames = fps * duration_s

# Anubis subtle bob + head turn (slow imposing)
for f in range(1, total_frames + 1, 4):
    t = (f - 1) / fps
    anubis_e.location.z = math.sin(t * 0.6) * 0.06
    head_e.rotation_euler = (math.sin(t * 0.4) * math.radians(3), 0,
                              math.sin(t * 0.3) * math.radians(15))
    anubis_e.keyframe_insert("location", frame=f)
    head_e.keyframe_insert("rotation_euler", frame=f)

# Ankh glow pulse
for f in range(1, total_frames + 1, 4):
    t = (f - 1) / fps
    s = 1 + math.sin(t * 2.0) * 0.10
    ankh_e.scale = (s, s, s)
    ankh_e.keyframe_insert("scale", frame=f)

# Sarcophagus subtle glow + face pulse
for f in range(1, total_frames + 1, 5):
    t = (f - 1) / fps
    s = 1 + math.sin(t * 1.0) * 0.02
    sarco_e.scale = (s, s, s)
    sarco_e.keyframe_insert("scale", frame=f)

# 3 priests perform mummification (arms wrap motion + Z bob)
for pi, p in enumerate(priests):
    phase = pi * 0.7
    base_z = p["root"].location.z
    for f in range(1, total_frames + 1, 3):
        t = (f - 1) / fps
        p["root"].location.z = base_z + math.sin(t * 0.9 + phase) * 0.03
        p["root"].keyframe_insert("location", frame=f)
        # Arm wrap oscillation
        p["sh0"].rotation_euler = (math.radians(-90) + math.sin(t * 2.0 + phase) * math.radians(15),
                                    0,
                                    math.radians(-25) + math.cos(t * 2.0 + phase) * math.radians(10))
        p["sh0"].keyframe_insert("rotation_euler", frame=f)
        p["sh1"].rotation_euler = (math.radians(-90) + math.cos(t * 2.0 + phase) * math.radians(15),
                                    0,
                                    math.radians(25) + math.sin(t * 2.0 + phase) * math.radians(10))
        p["sh1"].keyframe_insert("rotation_euler", frame=f)

# Balance Maât (slight oscillation - pans bobbing)
for f in range(1, total_frames + 1, 3):
    t = (f - 1) / fps
    # Crossbeam slight tilt
    balance_e.rotation_euler = (0, math.sin(t * 0.8) * math.radians(4), 0)
    balance_e.keyframe_insert("rotation_euler", frame=f)
    # Pans bob (compensating)
    pan_left_e.location.z = 3.10 + math.sin(t * 0.8) * 0.05
    pan_right_e.location.z = 3.10 - math.sin(t * 0.8) * 0.05
    pan_left_e.keyframe_insert("location", frame=f)
    pan_right_e.keyframe_insert("location", frame=f)
    # Feather pulse (signature judgment)
    feather_e.rotation_euler = (0, math.sin(t * 1.5) * math.radians(8), t * 0.3)
    feather_e.keyframe_insert("rotation_euler", frame=f)
    # Heart beat pulse
    s_h = 1 + math.sin(t * 4.0) * 0.10
    heart_e.scale = (s_h, s_h, s_h)
    heart_e.keyframe_insert("scale", frame=f)

# Scarab roll + wings vibrate
for f in range(1, total_frames + 1, 3):
    t = (f - 1) / fps
    # Roll motion
    scarab_e.rotation_euler = (math.sin(t * 0.8) * math.radians(8),
                                math.sin(t * 0.6) * math.radians(5),
                                math.sin(t * 0.4) * math.radians(10))
    scarab_e.keyframe_insert("rotation_euler", frame=f)
    # Subtle Z bob
    scarab_e.location.z = 0.5 + math.sin(t * 1.5) * 0.05
    scarab_e.keyframe_insert("location", frame=f)

# Ra subtle + sun disk pulse
for f in range(1, total_frames + 1, 4):
    t = (f - 1) / fps
    ra_head_e.rotation_euler = (math.sin(t * 0.4) * math.radians(3), 0,
                                 math.sin(t * 0.3) * math.radians(10))
    ra_head_e.keyframe_insert("rotation_euler", frame=f)

# Thoth writing (right hand pen oscillation)
for f in range(1, total_frames + 1, 3):
    t = (f - 1) / fps
    r_sh.rotation_euler = (math.radians(-90) + math.sin(t * 3.0) * math.radians(10),
                            0,
                            math.radians(-30) + math.cos(t * 3.0) * math.radians(15))
    r_sh.keyframe_insert("rotation_euler", frame=f)
    thoth_head_e.rotation_euler = (math.sin(t * 1.0) * math.radians(5), 0, 0)
    thoth_head_e.keyframe_insert("rotation_euler", frame=f)

# Hieroglyphs pulse différentielles
for glyph in glyphs:
    phase = glyph["_phase"]
    for f in range(1, total_frames + 1, 6):
        t = (f - 1) / fps
        s = 1 + math.sin(t * 2.0 + phase) * 0.15
        glyph.scale = (s, s, s)
        glyph.keyframe_insert("scale", frame=f)

# Torches flames pulse
for t_obj in torches:
    p_o = t_obj["phase"]
    for f in range(1, total_frames + 1, 3):
        t = (f - 1) / fps
        s_o = 1 + math.sin(t * 6.0 + p_o) * 0.30
        t_obj["outer"].scale = (s_o, s_o, s_o)
        t_obj["outer"].keyframe_insert("scale", frame=f)
        s_i = 1 + math.sin(t * 8.0 + p_o + 0.3) * 0.35
        t_obj["inner"].scale = (s_i, s_i, s_i)
        t_obj["inner"].keyframe_insert("scale", frame=f)

# Cats subtle motion (sacred statues + tail wave)
for c in cats:
    phase = c["phase"]
    for f in range(1, total_frames + 1, 5):
        t = (f - 1) / fps
        c["head"].rotation_euler = (math.sin(t * 0.8 + phase) * math.radians(8), 0,
                                     math.sin(t * 0.6 + phase) * math.radians(15))
        c["head"].keyframe_insert("rotation_euler", frame=f)
        c["tail"].rotation_euler = (0, math.sin(t * 1.5 + phase) * math.radians(20),
                                     math.sin(t * 1.2 + phase) * math.radians(15))
        c["tail"].keyframe_insert("rotation_euler", frame=f)

# Sand particles drift
for sd in sands:
    phase = sd["_phase"]; speed = sd["_speed"]
    bx, by, bz = sd["_base_x"], sd["_base_y"], sd["_base_z"]
    for f in range(1, total_frames + 1, 6):
        t = (f - 1) / fps
        x = bx + math.sin(t * speed + phase) * 0.8
        y = by + math.cos(t * speed * 0.8 + phase) * 0.8
        z = bz + (t * 0.4) % 3.0
        s = 1 + math.sin(t * 3.0 + phase) * 0.3
        sd.location = (x, y, z)
        sd.scale = (s, s, s)
        sd.keyframe_insert("location", frame=f)
        sd.keyframe_insert("scale", frame=f)

# Canopic jars subtle glow pulse
for ci in range(4):
    for obj in bpy.data.objects:
        if obj.name == f"canopic{ci}":
            for f in range(1, total_frames + 1, 6):
                t = (f - 1) / fps
                s = 1 + math.sin(t * 1.2 + ci) * 0.04
                obj.scale = (s, s, s)
                obj.keyframe_insert("scale", frame=f)

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
out_glb = os.path.join(out_dir, "pbr_anubis_proc.glb")

bpy.ops.object.select_all(action='SELECT')
bpy.ops.export_scene.gltf(
    filepath=out_glb, export_format='GLB',
    export_animations=True, export_apply=False, export_yup=True, use_selection=False,
)
size_mb = os.path.getsize(out_glb) / (1024 * 1024)
print(f"[proc_egyptian_pyramid_afterlife_anubis] DONE → {out_glb} ({size_mb:.2f} MB)")
print("[proc_egyptian_pyramid_afterlife_anubis] Anubis sphinx + sarcophagus mummy + 3 priests bandage + Maât balance feather/heart + 4 canopic jars + giant scarab + Ra falcon + Thoth ibis writing + 6 lotus columns + 8 torches + 8 cats + 200 sand + ankh + ceiling stars")
