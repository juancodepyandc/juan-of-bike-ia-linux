"""
proc_egyptian_pharaoh_tomb_pyramid.py — 239e procédural AuroraIA (104e qualité)
Egyptian pharaoh tomb: ONE stone floor + sarcophagus + Tutankhamun mask + 4 Anubis + 2 Horus + canopic jars + 8 mummified servants + chariot + torches + 600 sand + 400 cursed scarabs
FIXES : 1 ground + 600 sand + 400 scarabs signature pharaoh tomb
"""
import bpy, bmesh, math, random, os

random.seed(0x70AB239)

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

# Tomb dark ambient palette
M_SKY = mat("sky", (0.05, 0.04, 0.06, 1.0), 0.0, 0.7, emission=(0.08,0.06,0.10), emission_strength=0.5)
M_AMBIENT = mat("amb", (0.55, 0.42, 0.28, 1.0), 0.0, 0.30, emission=(0.50,0.38,0.25), emission_strength=1.5)

# Stone floor
M_FLOOR_STONE = mat("floor", (0.55, 0.45, 0.32, 1.0), 0.0, 0.85, emission=(0.50,0.40,0.28), emission_strength=0.5)
M_FLOOR_DARK = mat("floor_d", (0.38, 0.30, 0.22, 1.0), 0.0, 0.85)
M_FLOOR_GOLD = mat("floor_g", (0.85, 0.65, 0.30, 1.0), 0.85, 0.30, emission=(0.78,0.60,0.28), emission_strength=0.7)

# Walls hieroglyphs
M_WALL_SAND = mat("wall_s", (0.78, 0.62, 0.42, 1.0), 0.0, 0.75, emission=(0.72,0.58,0.40), emission_strength=0.6)
M_WALL_DARK = mat("wall_d", (0.55, 0.42, 0.28, 1.0), 0.0, 0.85)
M_HIEROGLYPH = mat("hiero", (0.40, 0.25, 0.10, 1.0), 0.0, 0.70, emission=(0.55,0.35,0.15), emission_strength=0.8)
M_HIEROGLYPH_GOLD = mat("hiero_g", (0.95, 0.78, 0.30, 1.0), 0.95, 0.20, emission=(0.92,0.75,0.28), emission_strength=1.2)
M_LAPIS_BLUE = mat("lapis", (0.20, 0.40, 0.78, 1.0), 0.3, 0.30, emission=(0.18,0.38,0.72), emission_strength=1.5)

# Sarcophagus (signature gold)
M_GOLD_PHARAOH = mat("gold_p", (1.0, 0.82, 0.30, 1.0), 0.95, 0.18, emission=(0.95,0.78,0.28), emission_strength=1.5)
M_GOLD_DEEP = mat("gold_d", (0.85, 0.62, 0.20, 1.0), 0.95, 0.22, emission=(0.80,0.58,0.20), emission_strength=1.2)
M_TURQUOISE = mat("turq", (0.20, 0.78, 0.78, 1.0), 0.5, 0.25, emission=(0.20,0.75,0.75), emission_strength=2.0)
M_CARNELIAN_RED = mat("carnelian", (0.85, 0.20, 0.18, 1.0), 0.4, 0.30, emission=(0.78,0.20,0.18), emission_strength=1.5)
M_OBSIDIAN_BLACK = mat("obsidian", (0.05, 0.04, 0.05, 1.0), 0.8, 0.20, emission=(0.05,0.04,0.05), emission_strength=0.4)
M_MUMMY_BANDAGE = mat("mummy", (0.85, 0.72, 0.55, 1.0), 0.0, 0.85, emission=(0.78,0.65,0.50), emission_strength=0.6)
M_MUMMY_BANDAGE_OLD = mat("mummy_o", (0.65, 0.52, 0.35, 1.0), 0.0, 0.85)

# Anubis (signature jackal god black + gold)
M_ANUBIS_BODY = mat("anubis", (0.08, 0.06, 0.06, 1.0), 0.4, 0.25, emission=(0.08,0.06,0.06), emission_strength=0.4)
M_ANUBIS_GOLD = mat("anubis_g", (0.95, 0.78, 0.30, 1.0), 0.85, 0.25, emission=(0.92,0.75,0.28), emission_strength=1.2)
M_ANUBIS_EYE_RED = mat("anubis_e", (1.0, 0.20, 0.10, 1.0), 0.0, 0.10, emission=(1.0,0.20,0.10), emission_strength=14.0)

# Horus (signature falcon)
M_HORUS_BODY = mat("horus", (0.85, 0.78, 0.55, 1.0), 0.3, 0.45, emission=(0.78,0.72,0.50), emission_strength=0.6)
M_HORUS_BLUE = mat("horus_b", (0.20, 0.40, 0.78, 1.0), 0.0, 0.35, emission=(0.18,0.38,0.72), emission_strength=1.2)

# Canopic jars
M_CANOPIC = mat("canopic", (0.95, 0.78, 0.45, 1.0), 0.3, 0.45, emission=(0.88,0.72,0.42), emission_strength=0.7)
M_CANOPIC_BLUE = mat("canopic_b", (0.30, 0.55, 0.85, 1.0), 0.3, 0.40, emission=(0.28,0.50,0.78), emission_strength=0.8)

# Wood
M_WOOD_DARK_E = mat("wood_d", (0.32, 0.18, 0.08, 1.0), 0.0, 0.80, emission=(0.30,0.16,0.08), emission_strength=0.4)
M_WOOD_PAINTED = mat("wood_p", (0.55, 0.30, 0.15, 1.0), 0.0, 0.70, emission=(0.50,0.28,0.13), emission_strength=0.5)

# Skin
M_SKIN_EGY = mat("skin", (0.78, 0.55, 0.38, 1.0), 0.0, 0.55, emission=(0.72,0.52,0.36), emission_strength=0.5)

# Fire torches
M_FIRE_OUTER = mat("fire_o", (1.0, 0.55, 0.15, 1.0), 0.0, 0.20, emission=(1.0,0.55,0.15), emission_strength=18.0)
M_FIRE_CORE = mat("fire_c", (1.0, 0.92, 0.30, 1.0), 0.0, 0.20, emission=(1.0,0.92,0.30), emission_strength=22.0)
M_TORCH_WOOD = mat("torch_w", (0.30, 0.18, 0.10, 1.0), 0.0, 0.85)

# Scarab (signature blue/gold)
M_SCARAB_BLUE = mat("scarab_b", (0.20, 0.55, 0.85, 1.0), 0.6, 0.20, emission=(0.20,0.55,0.85), emission_strength=4.0)
M_SCARAB_GOLD = mat("scarab_g", (1.0, 0.85, 0.30, 1.0), 0.85, 0.18, emission=(0.95,0.80,0.28), emission_strength=3.5)
M_SCARAB_BODY = mat("scarab_bd", (0.18, 0.30, 0.18, 1.0), 0.5, 0.30, emission=(0.18,0.30,0.18), emission_strength=2.0)

# Sand
M_SAND_TOMB = mat("sand_t", (0.85, 0.72, 0.42, 1.0), 0.0, 0.55, emission=(0.78,0.68,0.38), emission_strength=2.0, alpha=0.65)

# Papyrus
M_PAPYRUS = mat("papyrus", (0.92, 0.82, 0.62, 1.0), 0.0, 0.65, emission=(0.85,0.78,0.58), emission_strength=0.6)
M_INK = mat("ink", (0.20, 0.10, 0.06, 1.0), 0.0, 0.75)

# Cat (Bastet)
M_BASTET = mat("bastet", (0.10, 0.08, 0.06, 1.0), 0.4, 0.30, emission=(0.10,0.08,0.06), emission_strength=0.5)
M_BASTET_GOLD = mat("bastet_g", (0.95, 0.78, 0.30, 1.0), 0.85, 0.20, emission=(0.92,0.75,0.28), emission_strength=1.0)

# ============ SKY (tomb interior - dark) ============
sky = smooth_sphere("sky", r=140, segs=32, rings=20, loc=(0,0,0), mat_=M_SKY)
sky.scale = (1,1,0.55)

# ============ TOMB WALLS (pyramid interior 4 sides + ceiling) ============
# Back wall
beveled_cube("wall_b", (40, 1, 14), bevel_offset=0.10, loc=(0, 20, 7), mat_=M_WALL_SAND)
# Front wall (with entrance)
beveled_cube("wall_f_l", (15, 1, 14), bevel_offset=0.10, loc=(-12.5, -20, 7), mat_=M_WALL_SAND)
beveled_cube("wall_f_r", (15, 1, 14), bevel_offset=0.10, loc=(12.5, -20, 7), mat_=M_WALL_SAND)
beveled_cube("wall_f_top", (10, 1, 4), bevel_offset=0.10, loc=(0, -20, 12), mat_=M_WALL_SAND)
# Side walls
for side, side_mul in zip(("L", "R"), (-1, 1)):
    beveled_cube(f"wall_{side}", (1, 40, 14), bevel_offset=0.10, loc=(side_mul*20, 0, 7), mat_=M_WALL_SAND)
# Ceiling (sloped pyramid signature)
for cy in range(8):
    cy_pos = (cy - 3.5) * 5
    width = 40 - abs(cy_pos) * 0.4
    beveled_cube(f"ceiling{cy}", (width, 5, 0.5), bevel_offset=0.06,
                 loc=(0, cy_pos, 14.5), mat_=M_WALL_DARK)

# HIEROGLYPHS columns on walls (signature)
for side_x, side_y in [(-1, 0), (1, 0), (0, 1)]:
    for ci in range(8):
        cz = 2 + ci * 1.4
        wall_x = side_x * 19.5 if side_x else 0
        wall_y = side_y * 19.5 if side_y else 0
        if side_x:
            offset_normal = -side_x * 0.3
            hx = wall_x + offset_normal
        else:
            offset_normal = -side_y * 0.3
            hx = wall_x
        # Hieroglyph column
        for hi in range(5):
            col = M_HIEROGLYPH if hi % 2 == 0 else M_HIEROGLYPH_GOLD
            if side_x:
                beveled_cube(f"hiero_{side_x}_{ci}_{hi}", (0.25, 0.45, 0.20), bevel_offset=0.02,
                             loc=(hx, ci*4 - 14 + hi*0.40, cz), mat_=col)
            else:
                beveled_cube(f"hiero_y_{ci}_{hi}", (0.45, 0.25, 0.20), bevel_offset=0.02,
                             loc=(ci*4 - 14 + hi*0.40, wall_y + offset_normal, cz), mat_=col)

# Decorative gold bands
for bz in (0.5, 13.5):
    beveled_cube(f"band_b_{bz}", (40, 1.05, 0.30), bevel_offset=0.04, loc=(0, 20, bz), mat_=M_HIEROGLYPH_GOLD)
    beveled_cube(f"band_f_l_{bz}", (15, 1.05, 0.30), bevel_offset=0.04, loc=(-12.5, -20, bz), mat_=M_HIEROGLYPH_GOLD)
    beveled_cube(f"band_f_r_{bz}", (15, 1.05, 0.30), bevel_offset=0.04, loc=(12.5, -20, bz), mat_=M_HIEROGLYPH_GOLD)
    for side, side_mul in zip(("L", "R"), (-1, 1)):
        beveled_cube(f"band_{side}_{bz}", (1.05, 40, 0.30), bevel_offset=0.04, loc=(side_mul*20, 0, bz), mat_=M_HIEROGLYPH_GOLD)

# ============ ONE clean stone floor ground ============
ground = beveled_cube("ground", (100, 100, 0.5), bevel_offset=0.08, loc=(0, 0, -0.25), mat_=M_AMBIENT)
# Polished floor (interior)
floor_main = beveled_cube("floor_main", (38, 38, 0.30), bevel_offset=0.06,
                          loc=(0, 0, 0.10), mat_=M_FLOOR_STONE)
# Stone tile pattern (organic 3D variations)
for i in range(60):
    a = random.uniform(0, math.pi*2)
    rad = random.uniform(2, 18)
    smooth_sphere(f"tile{i}", r=random.uniform(0.30, 0.50), segs=14, rings=10,
                  loc=(rad*math.cos(a), rad*math.sin(a), 0.10),
                  mat_=M_FLOOR_DARK if i % 2 == 0 else M_FLOOR_STONE,
                  scale=(1.3, 1.2, 0.20))
# Gold floor inlay (signature ankh pattern)
for ai in range(8):
    aa = (ai / 8.0) * math.pi * 2
    rad = 5
    # Vertical
    beveled_cube(f"ankh_v{ai}", (0.3, 0.3, 0.04), bevel_offset=0.01,
                 loc=(rad*math.cos(aa), rad*math.sin(aa) - 1, 0.28), mat_=M_FLOOR_GOLD)
    # Horizontal
    beveled_cube(f"ankh_h{ai}", (0.7, 0.3, 0.04), bevel_offset=0.01,
                 loc=(rad*math.cos(aa), rad*math.sin(aa), 0.28), mat_=M_FLOOR_GOLD)
    # Loop top
    smooth_sphere(f"ankh_l{ai}", r=0.20,
                  loc=(rad*math.cos(aa), rad*math.sin(aa) + 0.5, 0.28),
                  mat_=M_FLOOR_GOLD, scale=(1, 1, 0.3))

# ============ SARCOPHAGUS GOLD with Tutankhamun mask (signature) ============
sarco_e = empty("sarcophagus", loc=(0, 0, 0))
# Stone base
beveled_cube("s_base", (5, 2.5, 0.8), bevel_offset=0.10, loc=(0, 0, 0.40),
             parent=sarco_e, mat_=M_FLOOR_DARK)
# Body (anthropoid shape signature)
# Body lower
beveled_cube("s_body", (3.5, 1.5, 0.6), bevel_offset=0.20, loc=(0, 0, 1.10),
             parent=sarco_e, mat_=M_GOLD_PHARAOH)
# Curved shoulders
smooth_sphere("s_shoulders", r=1.2, segs=22, rings=16, loc=(0, -0.65, 1.40),
              parent=sarco_e, mat_=M_GOLD_PHARAOH, scale=(1.3, 0.9, 0.7))
# Head/mask part
smooth_sphere("s_head", r=0.85, segs=24, rings=18, loc=(0, -0.95, 1.55),
              parent=sarco_e, mat_=M_GOLD_PHARAOH, scale=(1, 0.85, 1.2))
# Face (Tutankhamun mask signature)
# Crown nemes (striped headdress signature)
nemes_e = empty("nemes_e", (0, -0.95, 1.85), parent=sarco_e)
# Yellow gold stripes alternating blue
for ny in range(7):
    ny_y = ny * 0.10 - 0.30
    nemes_y_offset = -0.3 + ny * 0.10
    # Stripes wrapping
    beveled_cube(f"nemes_g{ny}", (0.95, 0.04, 0.18), bevel_offset=0.02,
                 loc=(0, nemes_y_offset, ny*0.04 - 0.10), parent=nemes_e, mat_=M_GOLD_PHARAOH if ny % 2 == 0 else M_LAPIS_BLUE)
# Back of head wider
smooth_sphere("nemes_back", r=0.80, loc=(0, 0.10, -0.05),
              parent=nemes_e, mat_=M_GOLD_PHARAOH, scale=(1.2, 0.8, 1.0))
# Side flaps (signature nemes)
for side in (-1, 1):
    beveled_cube(f"nemes_flap{side}", (0.12, 0.55, 0.85), bevel_offset=0.05,
                 loc=(side*0.85, -0.10, -0.20), parent=nemes_e, mat_=M_GOLD_PHARAOH)
# Cobra uraeus on forehead (signature pharaoh)
uraeus_e = empty("uraeus_e", (0, -0.95, -0.20), parent=nemes_e)
smooth_sphere("uraeus_head", r=0.12, loc=(0, -0.20, 0),
              parent=uraeus_e, mat_=M_GOLD_PHARAOH)
# Cobra body curl
for ui in range(4):
    cyl(f"uraeus_b{ui}", r=0.05, depth=0.12, segs=10,
        loc=(math.sin(ui*0.5)*0.08, -0.08 - ui*0.05, -ui*0.05),
        parent=uraeus_e, mat_=M_GOLD_PHARAOH)
# Vulture (Nekhbet) beside cobra
smooth_sphere("vulture_head", r=0.10, loc=(0.10, -0.20, -0.10),
              parent=nemes_e, mat_=M_GOLD_PHARAOH)
# Face details
# Eyes inlaid (signature kohl outlined)
for side in (-1, 1):
    # Eye almond
    beveled_cube(f"sar_eye{side}", (0.15, 0.05, 0.06), bevel_offset=0.02,
                 loc=(side*0.20, -0.85, 1.65), parent=sarco_e, mat_=M_LAPIS_BLUE)
    # Pupil
    smooth_sphere(f"sar_pupil{side}", r=0.03, loc=(side*0.20, -0.93, 1.65),
                  parent=sarco_e, mat_=M_OBSIDIAN_BLACK)
    # Kohl line
    beveled_cube(f"sar_kohl{side}", (0.20, 0.05, 0.03), bevel_offset=0.01,
                 loc=(side*0.22, -0.90, 1.55), parent=sarco_e, mat_=M_OBSIDIAN_BLACK)
# Nose
smooth_cone("sar_nose", r1=0.06, r2=0.08, depth=0.20, segs=12,
            loc=(0, -1.00, 1.40), parent=sarco_e, mat_=M_GOLD_PHARAOH)
# Lips
beveled_cube("sar_lips", (0.20, 0.05, 0.06), bevel_offset=0.02, loc=(0, -1.0, 1.20),
             parent=sarco_e, mat_=M_CARNELIAN_RED)
# False beard (signature pharaoh)
beard_e = empty("beard_e", (0, -1.0, 1.0), parent=sarco_e)
for bi in range(3):
    cyl(f"beard{bi}", r=0.06 - bi*0.005, depth=0.15, segs=12,
        loc=(0, -bi*0.02, -bi*0.20), parent=beard_e, mat_=M_GOLD_PHARAOH)
# Crook + flail crossed on chest (signature)
crook_e = empty("crook_e", (-0.3, -0.4, 1.2), parent=sarco_e)
crook_e.rotation_euler = (math.radians(-60), 0, math.radians(-15))
cyl("crook", r=0.04, depth=0.50, segs=12, loc=(0, 0, 0), parent=crook_e, mat_=M_GOLD_PHARAOH)
# Crook curl top
smooth_sphere("crook_top", r=0.10, loc=(0, 0, 0.35), parent=crook_e, mat_=M_GOLD_PHARAOH)
# Flail
flail_e = empty("flail_e", (0.3, -0.4, 1.2), parent=sarco_e)
flail_e.rotation_euler = (math.radians(-60), 0, math.radians(15))
cyl("flail", r=0.04, depth=0.50, segs=12, loc=(0, 0, 0), parent=flail_e, mat_=M_GOLD_PHARAOH)
# 3 strands
for fi in range(3):
    fa = (fi - 1) * 0.10
    cyl(f"flail_str{fi}", r=0.02, depth=0.20, segs=8,
        loc=(math.sin(fa)*0.05, 0, 0.30), parent=flail_e, mat_=M_GOLD_PHARAOH)
# Necklace (signature wide pectoral collar)
collar_e = empty("collar_e", (0, -0.4, 1.65), parent=sarco_e)
for ci in range(20):
    ca = (ci / 20.0) * math.pi - math.pi/2
    cx_c = math.cos(ca) * 0.55
    cz_c = math.sin(ca) * 0.55 * 0.6
    col = M_LAPIS_BLUE if ci % 3 == 0 else (M_CARNELIAN_RED if ci % 3 == 1 else M_TURQUOISE)
    smooth_sphere(f"collar_b{ci}", r=0.05, loc=(cx_c, 0, cz_c),
                  parent=collar_e, mat_=col)
# Mummy inside (signature lid opened to reveal)
mummy_e = empty("mummy", (0, 0.1, 1.30), parent=sarco_e)
# Bandaged body
smooth_cone("mum_body", r1=0.55, r2=0.30, depth=2.5, segs=14,
            loc=(0, 0, 0), parent=mummy_e, mat_=M_MUMMY_BANDAGE)
# Bandage wraps
for wi in range(8):
    cyl(f"mum_wrap{wi}", r=0.50 - wi*0.025, depth=0.06, segs=18,
        loc=(0, 0, -1.0 + wi*0.30), parent=mummy_e, mat_=M_MUMMY_BANDAGE_OLD)
# Mummy head bandages
smooth_sphere("mum_head", r=0.30, loc=(0, 0, 1.30),
              parent=mummy_e, mat_=M_MUMMY_BANDAGE, scale=(1, 1, 1.1))
# Bandage strips on head
for wi in range(5):
    cyl(f"mum_h_wrap{wi}", r=0.32, depth=0.04, segs=18,
        loc=(0, 0, 1.10 + wi*0.10), parent=mummy_e, mat_=M_MUMMY_BANDAGE_OLD)
# Eyes (closed sealed bandage X)
for side in (-1, 1):
    beveled_cube(f"mum_eye_x{side}", (0.10, 0.03, 0.03), bevel_offset=0.01,
                 loc=(side*0.10, -0.25, 1.30), parent=mummy_e, mat_=M_MUMMY_BANDAGE_OLD)

# ============ 4 ANUBIS STATUES (jackal god signature) ============
def make_anubis(name, loc, scale=1.0, facing=0):
    base = empty(name, loc)
    base.rotation_euler = (0, 0, facing)
    # Stone pedestal
    beveled_cube(f"{name}_ped", (1.5*scale, 1.0*scale, 0.4*scale), bevel_offset=0.06,
                 loc=(0, 0, 0.2*scale), parent=base, mat_=M_FLOOR_DARK)
    # Body (sitting jackal posture)
    smooth_sphere(f"{name}_body", r=0.55*scale, segs=20, rings=14, loc=(0, 0, 0.8*scale),
                  parent=base, mat_=M_ANUBIS_BODY, scale=(0.9, 1.2, 1.5))
    # Gold collar
    cyl(f"{name}_collar", r=0.45*scale, depth=0.10*scale, segs=18,
        loc=(0, 0, 1.40*scale), parent=base, mat_=M_ANUBIS_GOLD)
    # JACKAL HEAD (signature elongated)
    head_e = empty(f"{name}_he", (0, -0.1, 1.65*scale), parent=base)
    # Head main
    smooth_sphere(f"{name}_head", r=0.35*scale, segs=22, rings=16, loc=(0, 0, 0),
                  parent=head_e, mat_=M_ANUBIS_BODY, scale=(1, 1.2, 1.1))
    # Long pointed snout (signature jackal)
    smooth_cone(f"{name}_snout", r1=0.18*scale, r2=0.08*scale, depth=0.55*scale, segs=14,
                loc=(0, -0.35*scale, -0.10*scale), parent=head_e,
                mat_=M_ANUBIS_BODY).rotation_euler = (math.radians(-90), 0, 0)
    # Snout tip
    smooth_sphere(f"{name}_snout_tip", r=0.06*scale, loc=(0, -0.65*scale, -0.10*scale),
                  parent=head_e, mat_=M_OBSIDIAN_BLACK)
    # TALL POINTED EARS (signature jackal)
    for side in (-1, 1):
        ear = smooth_cone(f"{name}_ear{side}", r1=0.10*scale, r2=0.01*scale, depth=0.45*scale, segs=12,
                          loc=(side*0.15*scale, 0.05*scale, 0.30*scale), parent=head_e, mat_=M_ANUBIS_BODY)
        ear.rotation_euler = (math.radians(-15), 0, math.radians(side*15))
        # Inner ear gold
        smooth_cone(f"{name}_ear_in{side}", r1=0.05*scale, r2=0.005*scale, depth=0.30*scale, segs=10,
                    loc=(side*0.15*scale, 0.02*scale, 0.35*scale), parent=head_e, mat_=M_ANUBIS_GOLD).rotation_euler = (math.radians(-15), 0, math.radians(side*15))
    # Glowing red eyes (signature)
    for side in (-1, 1):
        smooth_sphere(f"{name}_eye{side}", r=0.06*scale,
                      loc=(side*0.10*scale, -0.30*scale, 0.05*scale),
                      parent=head_e, mat_=M_ANUBIS_EYE_RED)
    # Gold ankh in hand
    # 2 arms holding ankh
    for side_idx, side in enumerate((-1, 1)):
        sh = empty(f"{name}_sh{side_idx}", (side*0.35*scale, 0, 1.40*scale), parent=base)
        sh.rotation_euler = (math.radians(-50), 0, math.radians(side*-25))
        cyl(f"{name}_uarm{side_idx}", r=0.08*scale, depth=0.40*scale, segs=12,
            loc=(0, 0, -0.20*scale), parent=sh, mat_=M_ANUBIS_BODY)
        cyl(f"{name}_fa{side_idx}", r=0.07*scale, depth=0.35*scale, segs=10,
            loc=(0, 0, -0.55*scale), parent=sh, mat_=M_ANUBIS_BODY)
    # Ankh between hands
    ankh_e = empty(f"{name}_ankh_e", (0, -0.5*scale, 1.0*scale), parent=base)
    cyl(f"{name}_ankh_v", r=0.04*scale, depth=0.5*scale, segs=10,
        loc=(0, 0, 0), parent=ankh_e, mat_=M_ANUBIS_GOLD)
    cyl(f"{name}_ankh_h", r=0.04*scale, depth=0.4*scale, segs=10,
        loc=(0, 0, 0.05*scale), parent=ankh_e, mat_=M_ANUBIS_GOLD).rotation_euler = (0, math.radians(90), 0)
    smooth_sphere(f"{name}_ankh_l", r=0.10*scale, loc=(0, 0, 0.30*scale),
                  parent=ankh_e, mat_=M_ANUBIS_GOLD, scale=(1, 1, 0.7))
    base["_phase"] = random.uniform(0, math.pi*2)
    return {"root": base, "he": head_e}

anubis_list = []
anubis_pos = [(-8, -7, 0, math.radians(45)),
              (8, -7, 0, math.radians(-45)),
              (-8, 7, 0, math.radians(135)),
              (8, 7, 0, math.radians(-135))]
for i, (ax, ay, az, fac) in enumerate(anubis_pos):
    a = make_anubis(f"anubis{i}", (ax, ay, az), scale=1.2, facing=fac)
    anubis_list.append(a)

# ============ 2 HORUS STATUES (falcon god signature) ============
def make_horus(name, loc, scale=1.0, facing=0):
    base = empty(name, loc)
    base.rotation_euler = (0, 0, facing)
    # Pedestal
    cyl(f"{name}_ped", r=0.7*scale, depth=0.4*scale, segs=16, loc=(0, 0, 0.2*scale),
        parent=base, mat_=M_FLOOR_DARK)
    # Body humanoid
    smooth_cone(f"{name}_body", r1=0.45*scale, r2=0.32*scale, depth=1.0*scale, segs=16,
                loc=(0, 0, 0.9*scale), parent=base, mat_=M_HORUS_BODY)
    # Belt
    cyl(f"{name}_belt", r=0.35*scale, depth=0.10*scale, segs=14,
        loc=(0, 0, 1.40*scale), parent=base, mat_=M_GOLD_PHARAOH)
    # FALCON HEAD (signature)
    head_e = empty(f"{name}_he", (0, 0, 1.85*scale), parent=base)
    smooth_sphere(f"{name}_head", r=0.30*scale, segs=22, rings=16, loc=(0, 0, 0),
                  parent=head_e, mat_=M_HORUS_BLUE)
    # White face cheek
    smooth_sphere(f"{name}_cheek", r=0.20*scale, loc=(0, -0.15*scale, 0),
                  parent=head_e, mat_=M_HORUS_BODY, scale=(1, 0.4, 1.1))
    # Black eye markings around eye (signature wedjat)
    for side in (-1, 1):
        # Eye
        smooth_sphere(f"{name}_eye{side}", r=0.06*scale,
                      loc=(side*0.13*scale, -0.22*scale, 0.05*scale),
                      parent=head_e, mat_=M_GOLD_PHARAOH)
        # Pupil
        smooth_sphere(f"{name}_pupil{side}", r=0.025*scale,
                      loc=(side*0.13*scale, -0.27*scale, 0.05*scale),
                      parent=head_e, mat_=M_OBSIDIAN_BLACK)
        # Kohl extension (signature eye of Horus)
        beveled_cube(f"{name}_kohl{side}", (0.15*scale, 0.05*scale, 0.04*scale), bevel_offset=0.01,
                     loc=(side*0.18*scale, -0.24*scale, 0), parent=head_e, mat_=M_OBSIDIAN_BLACK)
    # Hooked BEAK signature
    smooth_cone(f"{name}_beak", r1=0.10*scale, r2=0.02*scale, depth=0.30*scale, segs=12,
                loc=(0, -0.25*scale, -0.10*scale), parent=head_e,
                mat_=M_GOLD_PHARAOH).rotation_euler = (math.radians(-110), 0, 0)
    # Curved beak hook tip
    smooth_cone(f"{name}_beak_hook", r1=0.04*scale, r2=0.005*scale, depth=0.12*scale, segs=10,
                loc=(0, -0.36*scale, -0.15*scale), parent=head_e,
                mat_=M_GOLD_PHARAOH).rotation_euler = (math.radians(-160), 0, 0)
    # Pschent crown (signature pharaoh dual crown)
    # Red crown lower
    cyl(f"{name}_crown_r", r=0.32*scale, depth=0.30*scale, segs=16,
        loc=(0, 0, 0.30*scale), parent=head_e, mat_=M_CARNELIAN_RED)
    # White crown bulb
    smooth_sphere(f"{name}_crown_w", r=0.22*scale, loc=(0, 0, 0.50*scale),
                  parent=head_e, mat_=M_GOLD_PHARAOH, scale=(1, 1, 1.4))
    # Arms holding scepter
    for side_idx, side in enumerate((-1, 1)):
        sh = empty(f"{name}_sh{side_idx}", (side*0.32*scale, 0, 1.50*scale), parent=base)
        sh.rotation_euler = (math.radians(-40), 0, math.radians(side*-15))
        cyl(f"{name}_uarm{side_idx}", r=0.08*scale, depth=0.40*scale, segs=12,
            loc=(0, 0, -0.20*scale), parent=sh, mat_=M_HORUS_BODY)
        cyl(f"{name}_fa{side_idx}", r=0.07*scale, depth=0.35*scale, segs=10,
            loc=(0, 0, -0.55*scale), parent=sh, mat_=M_HORUS_BODY)
    base["_phase"] = random.uniform(0, math.pi*2)
    return {"root": base, "he": head_e}

horus_list = []
horus_pos = [(-14, 0, 0, math.radians(90)), (14, 0, 0, math.radians(-90))]
for i, (hx, hy, hz, fac) in enumerate(horus_pos):
    h = make_horus(f"horus{i}", (hx, hy, hz), scale=1.3, facing=fac)
    horus_list.append(h)

# ============ 4 CANOPIC JARS ============
canopic_heads = ["human", "baboon", "jackal", "falcon"]
for ci, head_type in enumerate(canopic_heads):
    cx_pos = -3 + ci * 2
    c_e = empty(f"canopic{ci}", (cx_pos, -3, 0))
    # Jar body
    smooth_sphere(f"can_body{ci}", r=0.30, segs=18, rings=14, loc=(0, 0, 0.40),
                  parent=c_e, mat_=M_CANOPIC, scale=(1, 1, 1.4))
    # Decorative band middle
    cyl(f"can_band{ci}", r=0.32, depth=0.10, segs=18, loc=(0, 0, 0.40),
        parent=c_e, mat_=M_HIEROGLYPH_GOLD)
    # Head lid (signature different per jar)
    head_lid_e = empty(f"can_head_e{ci}", (0, 0, 0.85), parent=c_e)
    if head_type == "human":
        # Human head (Imsety)
        smooth_sphere(f"can_h{ci}", r=0.18, segs=18, rings=12, loc=(0, 0, 0),
                      parent=head_lid_e, mat_=M_CANOPIC)
        # Nemes
        beveled_cube(f"can_nemes{ci}", (0.30, 0.10, 0.20), bevel_offset=0.03,
                     loc=(0, 0.05, 0.10), parent=head_lid_e, mat_=M_CANOPIC_BLUE)
    elif head_type == "baboon":
        # Baboon (Hapy)
        smooth_sphere(f"can_h{ci}", r=0.18, segs=18, rings=12, loc=(0, 0, 0),
                      parent=head_lid_e, mat_=M_CANOPIC, scale=(1, 1.2, 1))
        # Long snout
        smooth_cone(f"can_snout{ci}", r1=0.08, r2=0.05, depth=0.15, segs=10,
                    loc=(0, -0.15, -0.05), parent=head_lid_e,
                    mat_=M_CANOPIC).rotation_euler = (math.radians(-90), 0, 0)
    elif head_type == "jackal":
        # Jackal (Duamutef)
        smooth_sphere(f"can_h{ci}", r=0.18, segs=18, rings=12, loc=(0, 0, 0),
                      parent=head_lid_e, mat_=M_OBSIDIAN_BLACK)
        # Pointed snout
        smooth_cone(f"can_snout{ci}", r1=0.08, r2=0.03, depth=0.22, segs=10,
                    loc=(0, -0.20, -0.05), parent=head_lid_e,
                    mat_=M_OBSIDIAN_BLACK).rotation_euler = (math.radians(-90), 0, 0)
        # Tall ears
        for side in (-1, 1):
            smooth_cone(f"can_ear{ci}_{side}", r1=0.05, r2=0.005, depth=0.18, segs=10,
                        loc=(side*0.08, 0.04, 0.15), parent=head_lid_e, mat_=M_OBSIDIAN_BLACK)
    else:  # falcon
        # Falcon (Qebehsenuef)
        smooth_sphere(f"can_h{ci}", r=0.18, segs=18, rings=12, loc=(0, 0, 0),
                      parent=head_lid_e, mat_=M_HORUS_BLUE)
        # Beak
        smooth_cone(f"can_beak{ci}", r1=0.05, r2=0.005, depth=0.15, segs=10,
                    loc=(0, -0.15, -0.08), parent=head_lid_e,
                    mat_=M_GOLD_PHARAOH).rotation_euler = (math.radians(-100), 0, 0)

# ============ TORCHES on walls (signature) ============
torch_pos = [(-19, -10, 0), (19, -10, 0), (-19, 0, 0), (19, 0, 0),
             (-19, 10, 0), (19, 10, 0)]
torches = []
for ti, (tx, ty, tz) in enumerate(torch_pos):
    t_e = empty(f"torch{ti}", (tx, ty, tz))
    # Stone bracket
    beveled_cube(f"t_bracket{ti}", (0.6, 0.20, 0.6), bevel_offset=0.04, loc=(0, 0, 4),
                 parent=t_e, mat_=M_FLOOR_GOLD)
    # Torch pole
    cyl(f"t_pole{ti}", r=0.08, depth=1.2, segs=10, loc=(0, -0.5, 4.5),
        parent=t_e, mat_=M_TORCH_WOOD).rotation_euler = (math.radians(45), 0, 0)
    # Bowl
    smooth_sphere(f"t_bowl{ti}", r=0.20, loc=(0, -0.8, 5.2),
                  parent=t_e, mat_=M_FLOOR_GOLD, scale=(1, 1, 0.5))
    # Flame
    flame_e = empty(f"t_fl_e{ti}", (0, -0.85, 5.3), parent=t_e)
    smooth_cone(f"t_fl_o{ti}", r1=0.25, r2=0.05, depth=1.0, segs=14,
                loc=(0, 0, 0.50), parent=flame_e, mat_=M_FIRE_OUTER)
    smooth_cone(f"t_fl_c{ti}", r1=0.15, r2=0.02, depth=0.7, segs=14,
                loc=(0, 0, 0.35), parent=flame_e, mat_=M_FIRE_CORE)
    t_e["_phase"] = random.uniform(0, math.pi*2)
    torches.append({"e": t_e, "flame": flame_e})

# ============ 8 MUMMIFIED SERVANTS (Ushabti signature) ============
def make_ushabti(name, loc, scale=1.0, facing=0):
    base = empty(name, loc)
    base.rotation_euler = (0, 0, facing)
    # Bandaged body
    smooth_cone(f"{name}_body", r1=0.35*scale, r2=0.25*scale, depth=1.4*scale, segs=14,
                loc=(0, 0, 0.7*scale), parent=base, mat_=M_MUMMY_BANDAGE)
    # Bandage wraps
    for wi in range(6):
        cyl(f"{name}_wrap{wi}", r=0.30*scale - wi*0.020, depth=0.04*scale, segs=14,
            loc=(0, 0, 0.20*scale + wi*0.20*scale), parent=base, mat_=M_MUMMY_BANDAGE_OLD)
    # Head
    head_e = empty(f"{name}_he", (0, 0, 1.6*scale), parent=base)
    smooth_sphere(f"{name}_head", r=0.18*scale, segs=20, rings=14, loc=(0, 0, 0),
                  parent=head_e, mat_=M_MUMMY_BANDAGE)
    # Head bandages
    for wi in range(3):
        cyl(f"{name}_h_wrap{wi}", r=0.19*scale, depth=0.03*scale, segs=18,
            loc=(0, 0, -0.08*scale + wi*0.08*scale), parent=head_e, mat_=M_MUMMY_BANDAGE_OLD)
    # Closed eye slits
    for side in (-1, 1):
        beveled_cube(f"{name}_eye{side}", (0.07*scale, 0.03*scale, 0.02*scale), bevel_offset=0.005,
                     loc=(side*0.07*scale, -0.16*scale, 0.02*scale), parent=head_e, mat_=M_OBSIDIAN_BLACK)
    # Arms crossed (signature)
    for side in (-1, 1):
        beveled_cube(f"{name}_arm{side}", (0.25*scale, 0.10*scale, 0.08*scale), bevel_offset=0.02,
                     loc=(side*0.10*scale, -0.12*scale, 1.15*scale), parent=base, mat_=M_MUMMY_BANDAGE)
    # Tool in hand (hoe + flail)
    if random.random() > 0.5:
        # Hoe
        cyl(f"{name}_tool", r=0.025*scale, depth=0.40*scale, segs=8,
            loc=(0.25*scale, -0.15*scale, 1.20*scale), parent=base, mat_=M_GOLD_PHARAOH).rotation_euler = (math.radians(-90), 0, 0)
    base["_phase"] = random.uniform(0, math.pi*2)
    return {"root": base}

ushabti = []
ushabti_pos = []
for ui in range(8):
    side_x = 1 if ui % 2 == 0 else -1
    pos_y = -10 + (ui // 2) * 8
    ushabti_pos.append((side_x * 14, pos_y, 0))
for i, (ux, uy, uz) in enumerate(ushabti_pos):
    u = make_ushabti(f"ushabti{i}", (ux, uy, uz), scale=1.0, facing=math.radians(0 if i % 2 == 0 else 180))
    ushabti.append(u)

# ============ CHARIOT (signature pharaoh chariot) ============
chariot_e = empty("chariot", loc=(0, 14, 0))
# Body (semicircular)
beveled_cube("ch_body", (2.0, 1.0, 0.8), bevel_offset=0.10, loc=(0, 0, 0.8),
             parent=chariot_e, mat_=M_GOLD_PHARAOH)
# Decorative panels
for side in (-1, 1):
    beveled_cube(f"ch_panel{side}", (2.1, 0.10, 0.7), bevel_offset=0.04,
                 loc=(0, side*0.55, 0.8), parent=chariot_e, mat_=M_HIEROGLYPH_GOLD)
# 2 wheels (signature spoked)
for side in (-1, 1):
    w_e = empty(f"wheel_e{side}", (0.5, side*0.7, 0.5), parent=chariot_e)
    w_e.rotation_euler = (math.radians(90), 0, 0)
    cyl(f"wheel_rim{side}", r=0.7, depth=0.10, segs=20,
        loc=(0, 0, 0), parent=w_e, mat_=M_WOOD_PAINTED)
    # Hub
    cyl(f"wheel_hub{side}", r=0.12, depth=0.15, segs=14, loc=(0, 0, 0),
        parent=w_e, mat_=M_GOLD_PHARAOH)
    # 8 spokes
    for sp in range(8):
        sa = (sp / 8.0) * math.pi * 2
        spoke = beveled_cube(f"spoke{side}_{sp}", (0.04, 0.55, 0.04), bevel_offset=0.01,
                            loc=(0, 0, 0), parent=w_e, mat_=M_WOOD_PAINTED)
        spoke.rotation_euler = (0, 0, sa)
        spoke.location = (0.30*math.cos(sa), 0.30*math.sin(sa), 0)
# Pole to horse
beveled_cube("ch_pole", (3.0, 0.15, 0.15), bevel_offset=0.03, loc=(-1.5, 0, 0.50),
             parent=chariot_e, mat_=M_WOOD_PAINTED)
# Decorative front shield
beveled_cube("ch_front", (0.20, 1.2, 1.5), bevel_offset=0.06, loc=(1, 0, 1.3),
             parent=chariot_e, mat_=M_GOLD_PHARAOH)

# ============ BASTET CAT STATUE (signature) ============
bastet_e = empty("bastet", loc=(-5, -10, 0))
# Pedestal
beveled_cube("bast_ped", (1.0, 0.6, 0.6), bevel_offset=0.06, loc=(0, 0, 0.3),
             parent=bastet_e, mat_=M_FLOOR_GOLD)
# Cat body (signature sitting upright)
smooth_sphere("bast_body", r=0.30, segs=20, rings=14, loc=(0, 0, 0.85),
              parent=bastet_e, mat_=M_BASTET, scale=(0.8, 1, 1.5))
# Head
head_b_e = empty("bast_he", (0, 0, 1.50), parent=bastet_e)
smooth_sphere("bast_head", r=0.22, segs=20, rings=14, loc=(0, 0, 0),
              parent=head_b_e, mat_=M_BASTET, scale=(1, 1.1, 1))
# Cat ears
for side in (-1, 1):
    ear = smooth_cone(f"bast_ear{side}", r1=0.08, r2=0.01, depth=0.18, segs=10,
                      loc=(side*0.12, 0.05, 0.20), parent=head_b_e, mat_=M_BASTET)
    ear.rotation_euler = (math.radians(-10), 0, math.radians(side*15))
# Eyes
for side in (-1, 1):
    smooth_sphere(f"bast_eye{side}", r=0.04, loc=(side*0.10, -0.15, 0.05),
                  parent=head_b_e, mat_=M_BASTET_GOLD)
# Gold collar
cyl("bast_collar", r=0.20, depth=0.06, segs=16, loc=(0, 0, 1.25),
    parent=bastet_e, mat_=M_BASTET_GOLD)
# Front legs
for side in (-1, 1):
    cyl(f"bast_leg{side}", r=0.06, depth=0.50, segs=10, loc=(side*0.10, -0.20, 0.85),
        parent=bastet_e, mat_=M_BASTET)
# Tail wraps around
smooth_sphere("bast_tail", r=0.10, loc=(-0.30, 0.10, 0.80),
              parent=bastet_e, mat_=M_BASTET, scale=(0.5, 1, 0.5))

# ============ PHARAOH BED + PAPYRUS SCROLLS ============
bed_e = empty("bed", loc=(8, -12, 0))
# Bed frame
beveled_cube("b_frame", (3, 1.5, 0.3), bevel_offset=0.06, loc=(0, 0, 0.7),
             parent=bed_e, mat_=M_WOOD_PAINTED)
# Mattress
beveled_cube("b_mat", (2.8, 1.4, 0.20), bevel_offset=0.04, loc=(0, 0, 0.95),
             parent=bed_e, mat_=M_CARNELIAN_RED)
# 4 legs (animal shaped)
for x in (-1, 1):
    for y in (-1, 1):
        cyl(f"b_leg{x}{y}", r=0.08, depth=0.55, segs=10, loc=(x*1.3, y*0.6, 0.30),
            parent=bed_e, mat_=M_WOOD_PAINTED)
# Headrest
beveled_cube("b_head", (1.0, 0.20, 0.50), bevel_offset=0.04, loc=(-1.3, 0, 1.3),
             parent=bed_e, mat_=M_HIEROGLYPH_GOLD)

# Papyrus scrolls (signature)
for ps in range(5):
    psx_p = (ps - 2) * 0.40
    cyl(f"papyrus{ps}", r=0.05, depth=0.30, segs=10, loc=(psx_p, 0.5, 1.05),
        parent=bed_e, mat_=M_PAPYRUS).rotation_euler = (0, math.radians(90), 0)
    # Open scroll
    if ps == 2:
        beveled_cube(f"scroll_open", (0.30, 0.04, 0.20), bevel_offset=0.02,
                     loc=(0, 0.4, 1.10), parent=bed_e, mat_=M_PAPYRUS)
        # Hieroglyphs on it
        for hi in range(3):
            smooth_sphere(f"scroll_glyph{hi}", r=0.025,
                          loc=(-0.10 + hi*0.10, 0.40, 1.15), parent=bed_e, mat_=M_INK)

# ============================================================
# ⭐ 600 SAND + 400 CURSED SCARABS (PARTICULES THÉMATIQUES OBLIGATOIRES)
# ============================================================
sand_particles = []
for i in range(600):
    px = random.uniform(-18, 18)
    py = random.uniform(-18, 18)
    pz = random.uniform(0.3, 10)
    s_obj = smooth_sphere(f"sand{i}", r=random.uniform(0.06, 0.12), segs=8, rings=6,
                          loc=(px, py, pz), mat_=M_SAND_TOMB)
    s_obj["_phase"] = random.uniform(0, math.pi*2)
    s_obj["_base_x"] = px; s_obj["_base_y"] = py; s_obj["_base_z"] = pz
    s_obj["_amp_x"] = random.uniform(0.5, 1.4)
    s_obj["_amp_y"] = random.uniform(0.5, 1.4)
    s_obj["_amp_z"] = random.uniform(0.3, 1.0)
    s_obj["_speed"] = random.uniform(0.3, 0.7)
    sand_particles.append(s_obj)

# 400 cursed scarabs (signature flying)
scarabs = []
for i in range(400):
    px = random.uniform(-15, 15)
    py = random.uniform(-15, 15)
    pz = random.uniform(0.5, 10)
    s_e = empty(f"scarab{i}", (px, py, pz))
    # Body iridescent
    smooth_sphere(f"sc_body{i}", r=random.uniform(0.06, 0.10), segs=10, rings=6,
                  loc=(0, 0, 0), parent=s_e,
                  mat_=M_SCARAB_BLUE if i % 2 == 0 else M_SCARAB_GOLD,
                  scale=(1.4, 1, 1))
    # Wing covers (signature scarab)
    for side in (-1, 1):
        beveled_cube(f"sc_w{i}_{side}", (0.05, 0.03, 0.02), bevel_offset=0.005,
                     loc=(0, side*0.04, 0.04), parent=s_e, mat_=M_SCARAB_BODY)
    s_e["_phase"] = random.uniform(0, math.pi*2)
    s_e["_base_x"] = px; s_e["_base_y"] = py; s_e["_base_z"] = pz
    s_e["_amp_x"] = random.uniform(1.0, 2.5)
    s_e["_amp_y"] = random.uniform(1.0, 2.5)
    s_e["_amp_z"] = random.uniform(0.5, 1.5)
    s_e["_speed"] = random.uniform(1.0, 2.5)
    scarabs.append(s_e)

# ============ ANIMATION ============
fps = 30; duration_s = 6; total_frames = fps * duration_s

# Mummy slowly stirs (signature awakening)
for f in range(1, total_frames + 1, 5):
    t = (f - 1) / fps
    mummy_e.rotation_euler = (math.sin(t * 0.5) * math.radians(3),
                                math.cos(t * 0.4) * math.radians(2), 0)
    mummy_e.keyframe_insert("rotation_euler", frame=f)

# Anubis eyes pulse + body breath
for a in anubis_list:
    phase = a["root"]["_phase"]
    for f in range(1, total_frames + 1, 4):
        t = (f - 1) / fps
        # Body slow breathing
        a["root"].location.z = math.sin(t * 0.6 + phase) * 0.03
        a["root"].keyframe_insert("location", frame=f)
        # Eyes pulse
        for obj_name in [f"{a['root'].name}_eye-1", f"{a['root'].name}_eye1"]:
            eye = bpy.data.objects.get(obj_name)
            if eye:
                s = 1 + math.sin(t * 3.0 + phase) * 0.30
                eye.scale = (s, s, s)
                eye.keyframe_insert("scale", frame=f)

# Horus heads slight turn
for h in horus_list:
    phase = h["root"]["_phase"]
    for f in range(1, total_frames + 1, 5):
        t = (f - 1) / fps
        h["he"].rotation_euler = (0, 0, math.sin(t * 0.6 + phase) * math.radians(8))
        h["he"].keyframe_insert("rotation_euler", frame=f)

# Torches flicker
for tr in torches:
    phase = tr["e"]["_phase"]
    for f in range(1, total_frames + 1, 3):
        t = (f - 1) / fps
        s = 1 + math.sin(t * 5.0 + phase) * 0.15
        tr["flame"].scale = (1 + math.sin(t * 4.0 + phase) * 0.12,
                              1 + math.cos(t * 4.5 + phase) * 0.12, s)
        tr["flame"].rotation_euler = (0, 0, math.sin(t * 3.0 + phase) * 0.18)
        tr["flame"].keyframe_insert("scale", frame=f)
        tr["flame"].keyframe_insert("rotation_euler", frame=f)

# Ushabti sway slightly
for u in ushabti:
    phase = u["root"]["_phase"]
    base_z = u["root"].location.z
    for f in range(1, total_frames + 1, 5):
        t = (f - 1) / fps
        u["root"].location.z = base_z + math.sin(t * 0.4 + phase) * 0.03
        u["root"].rotation_euler = (math.sin(t * 0.5 + phase) * math.radians(2), 0,
                                     u["root"].rotation_euler.z)
        u["root"].keyframe_insert("location", frame=f)
        u["root"].keyframe_insert("rotation_euler", frame=f)

# ============================================================
# ⭐⭐⭐ 600 SAND drift + 400 CURSED SCARABS vortex (signature tomb)
# ============================================================
for s in sand_particles:
    phase = s["_phase"]; speed = s["_speed"]
    bx, by, bz = s["_base_x"], s["_base_y"], s["_base_z"]
    ax, ay, az = s["_amp_x"], s["_amp_y"], s["_amp_z"]
    for f in range(1, total_frames + 1, 4):
        t = (f - 1) / fps
        x = bx + ax * math.sin(t * speed + phase)
        y = by + ay * math.cos(t * speed * 0.9 + phase)
        z = bz + az * math.sin(t * speed * 1.3 + phase)
        s.location = (x, y, max(0.1, z))
        sc = 1 + math.sin(t * 2.0 + phase) * 0.20
        s.scale = (sc, sc, sc)
        s.keyframe_insert("location", frame=f)
        s.keyframe_insert("scale", frame=f)

# 400 cursed scarabs flying erratic
for sc in scarabs:
    phase = sc["_phase"]; speed = sc["_speed"]
    bx, by, bz = sc["_base_x"], sc["_base_y"], sc["_base_z"]
    ax, ay, az = sc["_amp_x"], sc["_amp_y"], sc["_amp_z"]
    for f in range(1, total_frames + 1, 3):
        t = (f - 1) / fps
        # Erratic flight (zigzag)
        x = bx + ax * math.sin(t * speed + phase) + 0.3*math.sin(t * speed * 4 + phase * 2)
        y = by + ay * math.cos(t * speed * 0.9 + phase) + 0.3*math.cos(t * speed * 4 + phase)
        z = bz + az * math.sin(t * speed * 1.4 + phase * 1.7) + 0.2*math.sin(t * 6.0 + phase)
        sc.location = (x, y, max(0.2, z))
        sc.rotation_euler = (0, 0, math.atan2(math.cos(t * speed * 0.9 + phase),
                                                math.sin(t * speed + phase)))
        sc.keyframe_insert("location", frame=f)
        sc.keyframe_insert("rotation_euler", frame=f)

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
out_glb = os.path.join(out_dir, "pbr_tomb_proc.glb")

bpy.ops.object.select_all(action='SELECT')
bpy.ops.export_scene.gltf(
    filepath=out_glb, export_format='GLB',
    export_animations=True, export_apply=False, export_yup=True, use_selection=False,
)
size_mb = os.path.getsize(out_glb) / (1024 * 1024)
print(f"[proc_egyptian_pharaoh_tomb_pyramid] DONE → {out_glb} ({size_mb:.2f} MB)")
print(f"[proc_egyptian_pharaoh_tomb_pyramid] ONE stone floor + hieroglyph walls + Tutankhamun sarcophagus + mummy + 4 Anubis + 2 Horus + 4 canopic jars + 6 torches + 8 ushabti + chariot + Bastet + bed + papyrus + 600 SAND + 400 CURSED SCARABS")
print("⭐ FIXES: 1 ground + 600 sand + 400 cursed scarabs (signature pharaoh tomb mandatory) ⭐")
