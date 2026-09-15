"""
proc_argentina_tango_buenos_aires.py — 267e procédural AuroraIA (132e qualité)
Argentina tango Buenos Aires Caminito: 4 tango couples + 4 musicians (bandoneon piano violin contrabass) + colorful Caminito facades + lampposts + Argentina flag + Obelisco + 600 red roses + 400 music notes
FIXES : 1 ground brick paves + signature roses + notes
"""
import bpy, bmesh, math, random, os

random.seed(0x70AB267)

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

# Sky Buenos Aires night warm
M_SKY = mat("sky", (0.18, 0.12, 0.30, 1.0), 0.0, 0.7, emission=(0.18,0.12,0.30), emission_strength=1.5)
M_SKY_LOW = mat("sky_l", (0.55, 0.30, 0.40, 1.0), 0.0, 0.7, emission=(0.55,0.30,0.40), emission_strength=1.3)
M_STAR = mat("st", (1.0, 0.95, 0.85, 1.0), 0.0, 0.1, emission=(1.0,0.95,0.85), emission_strength=8.0)

# Brick pave ground (Caminito)
M_PAVE_RED = mat("pr", (0.65, 0.30, 0.20, 1.0), 0.0, 0.65, emission=(0.62,0.28,0.18), emission_strength=0.25)
M_PAVE_DARK = mat("pd", (0.45, 0.22, 0.15, 1.0), 0.0, 0.75)
M_GROUT = mat("gr", (0.22, 0.18, 0.15, 1.0), 0.0, 0.92)

# Caminito facade colors (signature)
M_FAC_YELLOW = mat("fy", (1.0, 0.85, 0.20, 1.0), 0.0, 0.55, emission=(0.95,0.82,0.20), emission_strength=1.0)
M_FAC_BLUE = mat("fb", (0.20, 0.55, 0.85, 1.0), 0.0, 0.55, emission=(0.20,0.52,0.82), emission_strength=0.9)
M_FAC_RED = mat("fr", (0.85, 0.25, 0.25, 1.0), 0.0, 0.55, emission=(0.82,0.25,0.25), emission_strength=0.9)
M_FAC_GREEN = mat("fg", (0.35, 0.75, 0.40, 1.0), 0.0, 0.55, emission=(0.32,0.72,0.40), emission_strength=0.8)
M_FAC_ORANGE = mat("fo", (1.0, 0.55, 0.20, 1.0), 0.0, 0.55, emission=(0.95,0.55,0.20), emission_strength=1.0)
M_FAC_PINK = mat("fp", (0.95, 0.45, 0.65, 1.0), 0.0, 0.55, emission=(0.92,0.45,0.62), emission_strength=0.9)
M_FAC_TURQ = mat("ft", (0.30, 0.78, 0.78, 1.0), 0.0, 0.55, emission=(0.30,0.75,0.75), emission_strength=0.9)
FACADE_COLORS = [M_FAC_YELLOW, M_FAC_BLUE, M_FAC_RED, M_FAC_GREEN, M_FAC_ORANGE, M_FAC_PINK, M_FAC_TURQ]

# Window
M_WINDOW = mat("wd", (0.85, 0.78, 0.55, 1.0), 0.0, 0.35, emission=(0.85,0.78,0.55), emission_strength=4.0)
M_WINDOW_FRAME = mat("wf", (0.22, 0.15, 0.10, 1.0), 0.0, 0.75)
M_DOOR = mat("dr", (0.32, 0.18, 0.10, 1.0), 0.0, 0.75)
M_BALCONY = mat("bal", (0.18, 0.15, 0.13, 1.0), 0.5, 0.45)

# Tango clothing
M_SKIN = mat("sk", (0.85, 0.65, 0.50, 1.0), 0.0, 0.55, emission=(0.80,0.62,0.50), emission_strength=0.3)
M_HAIR_BLACK = mat("hb", (0.10, 0.06, 0.05, 1.0), 0.0, 0.85)
M_HAIR_DARK = mat("hd", (0.20, 0.12, 0.08, 1.0), 0.0, 0.85)

# Woman tango dress red signature
M_DRESS_RED = mat("dr", (0.85, 0.10, 0.18, 1.0), 0.0, 0.45, emission=(0.82,0.10,0.18), emission_strength=0.7)
M_DRESS_RED_DARK = mat("drd", (0.55, 0.08, 0.12, 1.0), 0.0, 0.55)
M_FISHNET = mat("fn", (0.10, 0.08, 0.10, 1.0), 0.2, 0.35)

# Man tango suit
M_SUIT_BLACK = mat("sb", (0.08, 0.07, 0.07, 1.0), 0.1, 0.45)
M_SUIT_DARK_GRAY = mat("sg", (0.18, 0.17, 0.18, 1.0), 0.1, 0.50)
M_SHIRT_WHITE = mat("sw", (0.92, 0.90, 0.85, 1.0), 0.0, 0.35, emission=(0.88,0.86,0.82), emission_strength=0.5)
M_TIE_RED = mat("tr", (0.65, 0.10, 0.15, 1.0), 0.0, 0.45)
M_SHOE_BLACK = mat("shb", (0.06, 0.06, 0.06, 1.0), 0.3, 0.20)
M_HAT_FEDORA = mat("hf", (0.08, 0.07, 0.07, 1.0), 0.0, 0.55)

# Heels red
M_HEEL_RED = mat("hr", (0.85, 0.10, 0.18, 1.0), 0.2, 0.20, emission=(0.80,0.10,0.18), emission_strength=0.5)

# Lipstick
M_LIPS_RED = mat("lr", (0.85, 0.10, 0.18, 1.0), 0.0, 0.30, emission=(0.80,0.10,0.18), emission_strength=0.5)
M_EYE_DARK = mat("ed", (0.05, 0.04, 0.04, 1.0), 0.0, 0.20)

# Lamppost
M_LAMP_METAL = mat("lm", (0.18, 0.15, 0.13, 1.0), 0.7, 0.30)
M_LAMP_GLOW = mat("lg", (1.0, 0.85, 0.45, 1.0), 0.0, 0.10, emission=(1.0,0.85,0.45), emission_strength=15.0)

# Argentina flag
M_FLAG_BLUE = mat("flb", (0.45, 0.72, 0.92, 1.0), 0.0, 0.45, emission=(0.45,0.70,0.90), emission_strength=1.2)
M_FLAG_WHITE = mat("flw", (0.95, 0.95, 0.92, 1.0), 0.0, 0.45, emission=(0.92,0.92,0.90), emission_strength=1.0)
M_FLAG_SUN = mat("fls", (1.0, 0.85, 0.20, 1.0), 0.0, 0.30, emission=(1.0,0.85,0.20), emission_strength=4.0)

# Bandoneon (square accordion signature)
M_BANDON_BLACK = mat("bb", (0.10, 0.08, 0.08, 1.0), 0.2, 0.45)
M_BANDON_WHITE = mat("bw", (0.92, 0.88, 0.82, 1.0), 0.0, 0.45)
M_BANDON_MOTHER = mat("bm", (0.85, 0.78, 0.55, 1.0), 0.5, 0.20, emission=(0.85,0.78,0.55), emission_strength=0.5)

# Piano
M_PIANO_BLACK = mat("pb", (0.05, 0.05, 0.05, 1.0), 0.6, 0.10)
M_PIANO_KEY_W = mat("pkw", (0.98, 0.96, 0.92, 1.0), 0.0, 0.20)
M_PIANO_KEY_B = mat("pkb", (0.03, 0.03, 0.03, 1.0), 0.2, 0.20)

# Violin
M_VIOLIN_WOOD = mat("vw", (0.55, 0.25, 0.10, 1.0), 0.0, 0.30, emission=(0.55,0.25,0.10), emission_strength=0.4)
M_VIOLIN_DARK = mat("vwd", (0.32, 0.15, 0.05, 1.0), 0.0, 0.45)
M_STRING = mat("st", (0.85, 0.85, 0.85, 1.0), 0.5, 0.30)

# Contrabass
M_BASS_WOOD = mat("bsw", (0.55, 0.32, 0.15, 1.0), 0.0, 0.30, emission=(0.55,0.32,0.15), emission_strength=0.4)

# Obelisco
M_OBELISC = mat("ob", (0.85, 0.82, 0.78, 1.0), 0.0, 0.55, emission=(0.82,0.80,0.75), emission_strength=0.5)

# Rose
M_ROSE_RED = mat("rr", (0.85, 0.08, 0.15, 1.0), 0.0, 0.40, emission=(0.82,0.08,0.15), emission_strength=2.0)
M_ROSE_DARK = mat("rd", (0.55, 0.05, 0.10, 1.0), 0.0, 0.45, emission=(0.52,0.05,0.10), emission_strength=1.5)
M_LEAF_GREEN = mat("lg2", (0.30, 0.65, 0.25, 1.0), 0.0, 0.50, emission=(0.28,0.62,0.25), emission_strength=0.5)

# Music note
M_NOTE = mat("n", (1.0, 0.92, 0.30, 1.0), 0.2, 0.20, emission=(0.95,0.88,0.30), emission_strength=2.5)
M_NOTE_DARK = mat("nd", (0.08, 0.06, 0.06, 1.0), 0.2, 0.20, emission=(0.08,0.06,0.06), emission_strength=0.5)

# String for hat
M_FEATHER = mat("fe", (0.85, 0.85, 0.85, 1.0), 0.0, 0.55)

# ============ SKY ============
sky = smooth_sphere("sky", r=280, segs=32, rings=20, loc=(0,0,0), mat_=M_SKY)
sky.scale = (1,1,0.6)
sky_l = smooth_sphere("sky_l", r=240, segs=28, rings=16, loc=(0,0,5), mat_=M_SKY_LOW)
sky_l.scale = (1,1,0.3)
# Stars
for si in range(80):
    sa = random.uniform(0, math.pi*2); se = random.uniform(0.4, 0.9)
    sx = math.cos(sa) * 200 * math.cos(se)
    sy = math.sin(sa) * 200 * math.cos(se)
    sz = math.sin(se) * 150 + 40
    smooth_sphere(f"star{si}", r=random.uniform(0.4, 0.9), segs=8, rings=6,
                  loc=(sx, sy, sz), mat_=M_STAR)

# ============ ONE clean brick pave ground (Caminito) ============
ground = beveled_cube("ground", (200, 200, 0.5), bevel_offset=0.10, loc=(0, 0, -0.25), mat_=M_PAVE_DARK)
# Brick pavement pattern (signature Caminito)
for bi in range(70):
    for bj in range(70):
        bx = -55 + bi * 1.6
        by = -55 + bj * 1.6
        if -50 < bx < 50 and -50 < by < 50 and random.random() > 0.3:
            beveled_cube(f"br{bi}_{bj}", (0.7, 0.4, 0.08), bevel_offset=0.02,
                         loc=(bx, by, 0.05), mat_=M_PAVE_RED if (bi + bj) % 2 else M_PAVE_DARK)

# ============ CAMINITO FACADES (signature multi-colored) ============
def make_facade(name, loc, width, height, depth, mat_, has_balcony=True):
    base = empty(name, loc)
    # Main wall
    beveled_cube(f"{name}_w", (width, depth, height), bevel_offset=0.10,
                 loc=(0, 0, height/2), parent=base, mat_=mat_)
    # Windows
    win_rows = 2; win_cols = max(2, int(width / 3))
    for r in range(win_rows):
        for c in range(win_cols):
            wx = -width/2 + (c + 0.5) * (width / win_cols)
            wz = (r + 1) * (height / (win_rows + 1))
            # Frame
            beveled_cube(f"{name}_wf{r}_{c}", (0.9, 0.05, 0.9), bevel_offset=0.03,
                         loc=(wx, -depth/2 - 0.05, wz), parent=base, mat_=M_WINDOW_FRAME)
            # Glass
            beveled_cube(f"{name}_wg{r}_{c}", (0.8, 0.02, 0.8), bevel_offset=0.02,
                         loc=(wx, -depth/2 - 0.08, wz), parent=base, mat_=M_WINDOW)
            # Cross bars
            beveled_cube(f"{name}_wc{r}_{c}_v", (0.04, 0.04, 0.8), bevel_offset=0.01,
                         loc=(wx, -depth/2 - 0.09, wz), parent=base, mat_=M_WINDOW_FRAME)
            beveled_cube(f"{name}_wc{r}_{c}_h", (0.8, 0.04, 0.04), bevel_offset=0.01,
                         loc=(wx, -depth/2 - 0.09, wz), parent=base, mat_=M_WINDOW_FRAME)
            # Balcony (signature wrought iron)
            if has_balcony and r == 1:
                beveled_cube(f"{name}_bw{c}", (1.1, 0.5, 0.05), bevel_offset=0.02,
                             loc=(wx, -depth/2 - 0.30, wz - 0.55), parent=base, mat_=M_BALCONY)
                # Iron bars
                for bi in range(8):
                    bx_b = -0.5 + bi * 0.14
                    cyl(f"{name}_bb{c}_{bi}", r=0.02, depth=0.45, segs=6,
                        loc=(wx + bx_b, -depth/2 - 0.30, wz - 0.32), parent=base, mat_=M_BALCONY)
                # Top rail
                beveled_cube(f"{name}_br{c}", (1.1, 0.55, 0.04), bevel_offset=0.01,
                             loc=(wx, -depth/2 - 0.30, wz - 0.10), parent=base, mat_=M_BALCONY)
                # Side rails
                for sd in (-1, 1):
                    cyl(f"{name}_brs{c}_{sd}", r=0.025, depth=0.50, segs=6,
                        loc=(wx + sd*0.55, -depth/2 - 0.30, wz - 0.30), parent=base, mat_=M_BALCONY)
    # Door at ground center
    beveled_cube(f"{name}_d", (1.0, 0.06, 2.0), bevel_offset=0.05,
                 loc=(0, -depth/2 - 0.05, 1.0), parent=base, mat_=M_DOOR)
    # Roof line
    beveled_cube(f"{name}_rl", (width + 0.4, depth + 0.4, 0.20), bevel_offset=0.05,
                 loc=(0, 0, height + 0.10), parent=base, mat_=M_PAVE_DARK)
    return base

# Left row facades
fac_pos_left = [(-32, -25, 6, 7, 3), (-32, -16, 6, 6, 3), (-32, -7, 6, 8, 3),
                 (-32, 2, 6, 6, 3), (-32, 11, 6, 7, 3)]
for i, (fx, fy, fw, fh, fd) in enumerate(fac_pos_left):
    make_facade(f"facL{i}", (fx, fy, 0), fw, fh, fd, random.choice(FACADE_COLORS))

# Right row facades
fac_pos_right = [(32, -25, 6, 6, 3), (32, -16, 6, 7, 3), (32, -7, 6, 8, 3),
                  (32, 2, 6, 7, 3), (32, 11, 6, 6, 3)]
for i, (fx, fy, fw, fh, fd) in enumerate(fac_pos_right):
    fac = make_facade(f"facR{i}", (fx, fy, 0), fw, fh, fd, random.choice(FACADE_COLORS))
    fac.rotation_euler = (0, 0, math.radians(180))

# ============ OBELISCO silhouette signature ============
obelisc_e = empty("obelisc", (0, 50, 0))
# Base square
beveled_cube("ob_b", (4, 4, 1.5), bevel_offset=0.10, loc=(0, 0, 0.75),
             parent=obelisc_e, mat_=M_OBELISC)
# Main tapered shaft
for layer in range(15):
    lz = 1.5 + layer * 1.8
    lw = 3 - layer * 0.16
    beveled_cube(f"ob_s{layer}", (lw, lw, 1.8), bevel_offset=0.05,
                 loc=(0, 0, lz + 0.9), parent=obelisc_e, mat_=M_OBELISC)
# Pyramidal top
smooth_cone("ob_t", r1=0.35, r2=0.05, depth=2.5, segs=4,
            loc=(0, 0, 1.5 + 15*1.8 + 1.25), parent=obelisc_e, mat_=M_OBELISC)

# ============ 4 TANGO COUPLES (signature) ============
def make_tango_woman(name, loc, parent_base):
    # Body (red dress)
    smooth_cone(f"{name}_to", r1=0.30, r2=0.32, depth=0.7, segs=14, loc=(0, 0, 1.30),
                parent=parent_base, mat_=M_DRESS_RED)
    # Bare shoulders / cleavage line
    cyl(f"{name}_chest", r=0.30, depth=0.15, segs=14, loc=(0, 0, 1.65),
        parent=parent_base, mat_=M_SKIN)
    # Long dress (red flowing)
    skirt_e = empty(f"{name}_sk", (0, 0, 0.95), parent=parent_base)
    # Asymmetric long skirt (signature tango high slit)
    for sgi in range(30):
        sga = (sgi / 30.0) * math.pi * 2
        gx = math.cos(sga) * 0.32
        gy = math.sin(sga) * 0.32
        skirt_h = random.uniform(0.6, 1.1)
        beveled_cube(f"{name}_g{sgi}", (0.06, 0.06, skirt_h), bevel_offset=0.01,
                     loc=(gx, gy, -skirt_h/2), parent=skirt_e, mat_=M_DRESS_RED).rotation_euler = (math.cos(sga)*0.10, math.sin(sga)*0.10, sga)
    # Legs (fishnet)
    for side in (-1, 1):
        cyl(f"{name}_leg{side}", r=0.085, depth=0.95, segs=10,
            loc=(side*0.13, 0, 0.50), parent=parent_base, mat_=M_FISHNET)
    # Heels
    for side in (-1, 1):
        beveled_cube(f"{name}_h{side}", (0.10, 0.22, 0.04), bevel_offset=0.02,
                     loc=(side*0.13, 0, 0), parent=parent_base, mat_=M_HEEL_RED)
        # Heel spike
        cyl(f"{name}_hs{side}", r=0.015, depth=0.10, segs=6,
            loc=(side*0.13, 0.06, 0.05), parent=parent_base, mat_=M_HEEL_RED)
    # Arms (one extended toward partner)
    sh_l = empty(f"{name}_a0", (-0.30, 0, 1.65), parent=parent_base)
    sh_l.rotation_euler = (math.radians(-60), 0, math.radians(50))
    cyl(f"{name}_ua0", r=0.06, depth=0.40, segs=10, loc=(0, 0, -0.20),
        parent=sh_l, mat_=M_SKIN)
    cyl(f"{name}_fa0", r=0.05, depth=0.35, segs=10, loc=(0, 0, -0.55),
        parent=sh_l, mat_=M_SKIN)
    sh_r = empty(f"{name}_a1", (0.30, 0, 1.65), parent=parent_base)
    sh_r.rotation_euler = (math.radians(-30), 0, math.radians(-40))
    cyl(f"{name}_ua1", r=0.06, depth=0.40, segs=10, loc=(0, 0, -0.20),
        parent=sh_r, mat_=M_SKIN)
    cyl(f"{name}_fa1", r=0.05, depth=0.35, segs=10, loc=(0, 0, -0.55),
        parent=sh_r, mat_=M_SKIN)
    # Head
    head_w_e = empty(f"{name}_he", (0, 0, 1.95), parent=parent_base)
    smooth_sphere(f"{name}_h", r=0.17, segs=18, rings=14, loc=(0, 0, 0),
                  parent=head_w_e, mat_=M_SKIN)
    # Hair (slicked back bun)
    for hi in range(20):
        ha = random.uniform(0, math.pi*1.2) + math.pi*0.4
        cyl(f"{name}_hr{hi}", r=0.04, depth=0.20, segs=6,
            loc=(math.cos(ha)*0.12, math.sin(ha)*0.10 + 0.05, 0.05),
            parent=head_w_e, mat_=M_HAIR_BLACK)
    # Bun
    smooth_sphere(f"{name}_bun", r=0.12, segs=14, rings=10, loc=(0, 0.18, 0.05),
                  parent=head_w_e, mat_=M_HAIR_BLACK)
    # Eyes
    for side in (-1, 1):
        smooth_sphere(f"{name}_ey{side}", r=0.025, loc=(side*0.06, -0.14, 0.03),
                      parent=head_w_e, mat_=M_EYE_DARK)
    # Red lips (signature)
    beveled_cube(f"{name}_lp", (0.10, 0.04, 0.025), bevel_offset=0.005,
                 loc=(0, -0.16, -0.07), parent=head_w_e, mat_=M_LIPS_RED)
    # Rose in hair (signature)
    smooth_sphere(f"{name}_rh", r=0.10, segs=14, rings=10, loc=(0.15, 0.05, 0.10),
                  parent=head_w_e, mat_=M_ROSE_RED)
    for pp in range(5):
        ppa = (pp / 5.0) * math.pi * 2
        beveled_cube(f"{name}_rhp{pp}", (0.05, 0.08, 0.03), bevel_offset=0.005,
                     loc=(0.15 + math.cos(ppa)*0.08, 0.05 + math.sin(ppa)*0.08, 0.10),
                     parent=head_w_e, mat_=M_ROSE_RED)
    return {"he": head_w_e}

def make_tango_man(name, loc, parent_base):
    # Black suit jacket
    smooth_cone(f"{name}_j", r1=0.34, r2=0.36, depth=0.85, segs=14, loc=(0, 0, 1.25),
                parent=parent_base, mat_=M_SUIT_BLACK)
    # White shirt collar (V)
    beveled_cube(f"{name}_sh_c", (0.18, 0.06, 0.50), bevel_offset=0.02,
                 loc=(0, -0.30, 1.45), parent=parent_base, mat_=M_SHIRT_WHITE)
    # Tie red
    beveled_cube(f"{name}_ti", (0.06, 0.03, 0.35), bevel_offset=0.005,
                 loc=(0, -0.32, 1.40), parent=parent_base, mat_=M_TIE_RED)
    # Tie knot
    beveled_cube(f"{name}_tk", (0.08, 0.04, 0.06), bevel_offset=0.01,
                 loc=(0, -0.32, 1.60), parent=parent_base, mat_=M_TIE_RED)
    # Pants
    for side in (-1, 1):
        cyl(f"{name}_pl{side}", r=0.11, depth=0.95, segs=10,
            loc=(side*0.13, 0, 0.50), parent=parent_base, mat_=M_SUIT_DARK_GRAY)
    # Shoes
    for side in (-1, 1):
        beveled_cube(f"{name}_sh{side}", (0.13, 0.28, 0.06), bevel_offset=0.02,
                     loc=(side*0.13, 0, 0.03), parent=parent_base, mat_=M_SHOE_BLACK)
    # Arms (one around woman's waist, one extended)
    sh_lm = empty(f"{name}_a0", (-0.32, 0, 1.65), parent=parent_base)
    sh_lm.rotation_euler = (math.radians(-50), 0, math.radians(40))
    cyl(f"{name}_ua0", r=0.075, depth=0.40, segs=10, loc=(0, 0, -0.20),
        parent=sh_lm, mat_=M_SUIT_BLACK)
    cyl(f"{name}_fa0", r=0.065, depth=0.35, segs=10, loc=(0, 0, -0.55),
        parent=sh_lm, mat_=M_SHIRT_WHITE)
    sh_rm = empty(f"{name}_a1", (0.32, 0, 1.65), parent=parent_base)
    sh_rm.rotation_euler = (math.radians(-80), 0, math.radians(-60))
    cyl(f"{name}_ua1", r=0.075, depth=0.40, segs=10, loc=(0, 0, -0.20),
        parent=sh_rm, mat_=M_SUIT_BLACK)
    cyl(f"{name}_fa1", r=0.065, depth=0.35, segs=10, loc=(0, 0, -0.55),
        parent=sh_rm, mat_=M_SHIRT_WHITE)
    # Head
    head_m_e = empty(f"{name}_he", (0, 0, 1.95), parent=parent_base)
    smooth_sphere(f"{name}_h", r=0.18, segs=18, rings=14, loc=(0, 0, 0),
                  parent=head_m_e, mat_=M_SKIN)
    # Slicked black hair
    for hi in range(15):
        ha = random.uniform(0, math.pi*2)
        cyl(f"{name}_hr{hi}", r=0.04, depth=0.10, segs=6,
            loc=(math.cos(ha)*0.12, math.sin(ha)*0.10, 0.15),
            parent=head_m_e, mat_=M_HAIR_BLACK)
    # FEDORA hat (signature tango)
    if random.random() > 0.4:
        hat_e = empty(f"{name}_hat", (0, 0, 0.20), parent=head_m_e)
        cyl(f"{name}_hat_c", r=0.20, depth=0.18, segs=18, loc=(0, 0, 0),
            parent=hat_e, mat_=M_HAT_FEDORA)
        cyl(f"{name}_hat_b", r=0.30, depth=0.04, segs=18, loc=(0, 0, -0.10),
            parent=hat_e, mat_=M_HAT_FEDORA)
        # Band
        cyl(f"{name}_hat_bd", r=0.21, depth=0.05, segs=18, loc=(0, 0, -0.06),
            parent=hat_e, mat_=M_TIE_RED)
    # Eyes
    for side in (-1, 1):
        smooth_sphere(f"{name}_ey{side}", r=0.025, loc=(side*0.06, -0.15, 0.03),
                      parent=head_m_e, mat_=M_EYE_DARK)
    # Mustache
    beveled_cube(f"{name}_m", (0.10, 0.04, 0.025), bevel_offset=0.005,
                 loc=(0, -0.17, -0.04), parent=head_m_e, mat_=M_HAIR_BLACK)
    return {"he": head_m_e}

def make_tango_couple(name, loc, facing=0):
    base = empty(name, loc)
    base.rotation_euler = (0, 0, facing)
    # Woman slightly behind/left
    woman_base = empty(f"{name}_W", (-0.20, 0.15, 0), parent=base)
    woman_base.rotation_euler = (0, 0, math.radians(-15))
    w = make_tango_woman(f"{name}_w", (0, 0, 0), woman_base)
    # Man slightly in front/right
    man_base = empty(f"{name}_M", (0.20, -0.15, 0), parent=base)
    man_base.rotation_euler = (0, 0, math.radians(15))
    m = make_tango_man(f"{name}_m", (0, 0, 0), man_base)
    base["_phase"] = random.uniform(0, math.pi*2)
    return {"root": base, "woman": woman_base, "man": man_base, "he_w": w["he"], "he_m": m["he"]}

couples = []
couple_pos = [(-15, -10, math.radians(20)), (-5, -15, math.radians(0)),
               (5, -15, math.radians(0)), (15, -10, math.radians(-20))]
for i, (cx, cy, fac) in enumerate(couple_pos):
    c = make_tango_couple(f"cp{i}", (cx, cy, 0), facing=fac)
    couples.append(c)

# ============ 4 MUSICIANS ============
def make_musician(name, loc, instrument, facing=0):
    base = empty(name, loc)
    base.rotation_euler = (0, 0, facing)
    # Sitting (suit)
    smooth_cone(f"{name}_j", r1=0.32, r2=0.34, depth=0.7, segs=14, loc=(0, 0, 1.20),
                parent=base, mat_=M_SUIT_BLACK)
    # Pants crossed
    for side in (-1, 1):
        cyl(f"{name}_pl{side}", r=0.10, depth=0.50, segs=10,
            loc=(side*0.28, 0.18, 0.70), parent=base, mat_=M_SUIT_DARK_GRAY).rotation_euler = (math.radians(80), 0, 0)
    # White shirt collar
    beveled_cube(f"{name}_sh_c", (0.15, 0.04, 0.35), bevel_offset=0.02,
                 loc=(0, -0.30, 1.40), parent=base, mat_=M_SHIRT_WHITE)
    # Tie
    beveled_cube(f"{name}_ti", (0.05, 0.02, 0.25), bevel_offset=0.005,
                 loc=(0, -0.31, 1.35), parent=base, mat_=M_TIE_RED)
    # Head
    head_mu_e = empty(f"{name}_he", (0, 0, 1.80), parent=base)
    smooth_sphere(f"{name}_h", r=0.18, segs=18, rings=14, loc=(0, 0, 0),
                  parent=head_mu_e, mat_=M_SKIN)
    # Hair
    for hi in range(12):
        ha = random.uniform(0, math.pi*2)
        cyl(f"{name}_hr{hi}", r=0.04, depth=0.10, segs=6,
            loc=(math.cos(ha)*0.12, math.sin(ha)*0.10, 0.15),
            parent=head_mu_e, mat_=M_HAIR_DARK)
    # Eyes
    for side in (-1, 1):
        smooth_sphere(f"{name}_ey{side}", r=0.025, loc=(side*0.06, -0.15, 0.03),
                      parent=head_mu_e, mat_=M_EYE_DARK)
    # INSTRUMENT
    inst_e = empty(f"{name}_inst", (0, -0.40, 1.20), parent=base)
    if instrument == "bandoneon":
        # Bandoneon (square accordion signature)
        # Two side blocks (bellows compress between)
        for side in (-1, 1):
            beveled_cube(f"{name}_bd{side}", (0.30, 0.20, 0.30), bevel_offset=0.04,
                         loc=(side*0.20, 0, 0), parent=inst_e, mat_=M_BANDON_BLACK)
            # Mother of pearl buttons
            for bri in range(3):
                for bci in range(3):
                    smooth_sphere(f"{name}_bd{side}_b{bri}_{bci}", r=0.025,
                                  loc=(side*0.20 - 0.10 + bci*0.10, -0.10, -0.10 + bri*0.10),
                                  parent=inst_e, mat_=M_BANDON_MOTHER)
        # Bellows (pleated middle)
        for pl in range(8):
            beveled_cube(f"{name}_bd_p{pl}", (0.05, 0.18, 0.28), bevel_offset=0.01,
                         loc=(-0.10 + pl*0.025, 0, 0), parent=inst_e, mat_=M_BANDON_WHITE if pl%2==0 else M_BANDON_BLACK)
    elif instrument == "violin":
        # Violin body
        smooth_sphere(f"{name}_v_b", r=0.20, segs=16, rings=12, loc=(0, 0, 0),
                      parent=inst_e, mat_=M_VIOLIN_WOOD, scale=(0.85, 0.20, 1.2))
        # Neck
        cyl(f"{name}_v_n", r=0.025, depth=0.5, segs=10, loc=(0, -0.05, 0.32),
            parent=inst_e, mat_=M_VIOLIN_DARK)
        # F-holes (signature dark)
        for fh in (-1, 1):
            beveled_cube(f"{name}_v_fh{fh}", (0.02, 0.05, 0.08), bevel_offset=0.005,
                         loc=(fh*0.06, -0.08, 0), parent=inst_e, mat_=M_VIOLIN_DARK)
        # Strings
        for st in range(4):
            cyl(f"{name}_v_s{st}", r=0.003, depth=0.85, segs=6,
                loc=((st-1.5)*0.012, -0.08, 0.15), parent=inst_e, mat_=M_STRING)
        # Bow
        cyl(f"{name}_v_bo", r=0.015, depth=0.70, segs=8, loc=(0.30, -0.20, 0),
            parent=inst_e, mat_=M_VIOLIN_DARK).rotation_euler = (0, 0, math.radians(45))
    elif instrument == "piano":
        # Mini piano (silhouette)
        beveled_cube(f"{name}_p_b", (1.2, 0.5, 0.6), bevel_offset=0.06, loc=(0, 0, 0),
                     parent=inst_e, mat_=M_PIANO_BLACK)
        # White keys
        for kw in range(14):
            kx_w = -0.55 + kw * 0.085
            beveled_cube(f"{name}_p_kw{kw}", (0.08, 0.15, 0.04), bevel_offset=0.005,
                         loc=(kx_w, -0.20, 0.32), parent=inst_e, mat_=M_PIANO_KEY_W)
        # Black keys
        for kb in range(10):
            kx_b = -0.50 + kb * 0.115
            if kb % 7 not in (2, 6):  # skip B-C and E-F gaps roughly
                beveled_cube(f"{name}_p_kb{kb}", (0.05, 0.08, 0.05), bevel_offset=0.005,
                             loc=(kx_b, -0.25, 0.34), parent=inst_e, mat_=M_PIANO_KEY_B)
    elif instrument == "contrabass":
        # Big contrabass body
        smooth_sphere(f"{name}_b_b", r=0.45, segs=18, rings=14, loc=(0, 0, 0.5),
                      parent=inst_e, mat_=M_BASS_WOOD, scale=(0.85, 0.30, 1.4))
        # Neck (long)
        cyl(f"{name}_b_n", r=0.04, depth=1.5, segs=10, loc=(0, -0.10, 1.50),
            parent=inst_e, mat_=M_VIOLIN_DARK)
        # Strings
        for st in range(4):
            cyl(f"{name}_b_s{st}", r=0.005, depth=2.2, segs=6,
                loc=((st-1.5)*0.014, -0.13, 0.80), parent=inst_e, mat_=M_STRING)
        # Endpin
        cyl(f"{name}_b_ep", r=0.02, depth=0.5, segs=6, loc=(0, 0, -0.25),
            parent=inst_e, mat_=M_LAMP_METAL)
    # Arms
    for side_idx, side in enumerate((-1, 1)):
        sh = empty(f"{name}_a{side_idx}", (side*0.30, 0, 1.55), parent=base)
        sh.rotation_euler = (math.radians(-90 if side_idx == 0 else -70), 0, 0)
        cyl(f"{name}_ua{side_idx}", r=0.06, depth=0.30, segs=10, loc=(0, 0, -0.15),
            parent=sh, mat_=M_SUIT_BLACK)
    base["_phase"] = random.uniform(0, math.pi*2)
    return {"root": base, "inst": inst_e}

musicians = []
mus_data = [("bandoneon", -22, 20), ("piano", -8, 22), ("violin", 8, 22), ("contrabass", 22, 20)]
for i, (inst, mx, my) in enumerate(mus_data):
    m = make_musician(f"mus{i}", (mx, my, 0.6), instrument=inst,
                      facing=math.radians(180))
    musicians.append(m)

# ============ LAMPPOSTS (signature warm light) ============
def make_lamp(name, loc):
    base = empty(name, loc)
    # Base
    cyl(f"{name}_b", r=0.25, depth=0.40, segs=12, loc=(0, 0, 0.20), parent=base, mat_=M_LAMP_METAL)
    # Pole
    cyl(f"{name}_p", r=0.10, depth=5, segs=10, loc=(0, 0, 2.70), parent=base, mat_=M_LAMP_METAL)
    # Arm
    cyl(f"{name}_arm", r=0.06, depth=0.50, segs=8, loc=(0.25, 0, 5.10),
        parent=base, mat_=M_LAMP_METAL).rotation_euler = (0, math.radians(90), 0)
    # Lantern
    lantern_e = empty(f"{name}_le", (0.50, 0, 5.10), parent=base)
    cyl(f"{name}_lc", r=0.18, depth=0.40, segs=12, loc=(0, 0, 0), parent=lantern_e, mat_=M_LAMP_METAL)
    # Glow inside
    smooth_sphere(f"{name}_lg", r=0.15, segs=14, rings=10, loc=(0, 0, 0),
                  parent=lantern_e, mat_=M_LAMP_GLOW)
    return base

for i, (lx, ly) in enumerate([(-25, -25), (-25, 0), (-25, 25), (25, -25), (25, 0), (25, 25), (0, -30), (0, 30)]):
    make_lamp(f"lamp{i}", (lx, ly, 0))

# ============ ARGENTINA FLAG (signature pole + sun) ============
flag_e = empty("flag", (-40, 0, 0))
cyl("fl_p", r=0.10, depth=10, segs=10, loc=(0, 0, 5), parent=flag_e, mat_=M_LAMP_METAL)
# Blue stripe top
beveled_cube("fl_bt", (4, 0.05, 0.85), bevel_offset=0.06, loc=(2, 0, 9.4),
             parent=flag_e, mat_=M_FLAG_BLUE)
# White stripe middle
beveled_cube("fl_w", (4, 0.05, 0.85), bevel_offset=0.06, loc=(2, 0, 8.55),
             parent=flag_e, mat_=M_FLAG_WHITE)
# Blue stripe bottom
beveled_cube("fl_bb", (4, 0.05, 0.85), bevel_offset=0.06, loc=(2, 0, 7.70),
             parent=flag_e, mat_=M_FLAG_BLUE)
# Sun of May (signature)
smooth_sphere("fl_s", r=0.30, segs=18, rings=14, loc=(2, -0.06, 8.55),
              parent=flag_e, mat_=M_FLAG_SUN)
# Sun rays
for ri in range(16):
    rang = (ri / 16.0) * math.pi * 2
    beveled_cube(f"fl_sr{ri}", (0.05, 0.04, 0.20), bevel_offset=0.005,
                 loc=(2 + math.cos(rang)*0.40, -0.06, 8.55 + math.sin(rang)*0.40),
                 parent=flag_e, mat_=M_FLAG_SUN).rotation_euler = (0, rang, 0)
flag_e["_phase"] = 0

# ============================================================
# 600 RED ROSES FALLING + 400 MUSIC NOTES FLOATING (PARTICULES SIGNATURES)
# ============================================================
roses = []
for i in range(600):
    px = random.uniform(-60, 60)
    py = random.uniform(-50, 50)
    pz = random.uniform(2, 18)
    r_e = empty(f"ro{i}", (px, py, pz))
    # Rose head (multilayer petals)
    smooth_sphere(f"ro{i}_c", r=0.08, segs=10, rings=8, loc=(0, 0, 0),
                  parent=r_e, mat_=M_ROSE_DARK)
    for pp in range(5):
        ppa = (pp / 5.0) * math.pi * 2
        beveled_cube(f"ro{i}_p{pp}", (0.04, 0.10, 0.03), bevel_offset=0.005,
                     loc=(math.cos(ppa)*0.08, math.sin(ppa)*0.08, 0.02),
                     parent=r_e, mat_=M_ROSE_RED).rotation_euler = (0, 0, ppa)
    # Stem (short)
    cyl(f"ro{i}_s", r=0.012, depth=0.25, segs=6, loc=(0, 0, -0.18),
        parent=r_e, mat_=M_LEAF_GREEN)
    # Leaf
    beveled_cube(f"ro{i}_lf", (0.05, 0.10, 0.015), bevel_offset=0.005,
                 loc=(0.05, 0, -0.20), parent=r_e, mat_=M_LEAF_GREEN)
    r_e["_phase"] = random.uniform(0, math.pi*2)
    r_e["_base_x"] = px; r_e["_base_z"] = pz
    r_e["_drift"] = random.uniform(0.2, 0.6)
    r_e["_fall"] = random.uniform(0.7, 1.4)
    r_e["_swing"] = random.uniform(0.8, 1.8)
    roses.append(r_e)

# 400 music notes
notes = []
for i in range(400):
    px = random.uniform(-65, 65)
    py = random.uniform(-50, 50)
    pz = random.uniform(2, 20)
    n_e = empty(f"no{i}", (px, py, pz))
    # Note head
    smooth_sphere(f"no{i}_h", r=0.10, segs=12, rings=8, loc=(0, 0, 0),
                  parent=n_e, mat_=M_NOTE, scale=(1, 0.6, 0.8))
    # Stem
    cyl(f"no{i}_s", r=0.012, depth=0.50, segs=6, loc=(0.08, 0, 0.25),
        parent=n_e, mat_=M_NOTE)
    # Flag (eighth note) - random for variety
    if i % 2 == 0:
        beveled_cube(f"no{i}_f", (0.04, 0.03, 0.20), bevel_offset=0.005,
                     loc=(0.13, 0, 0.45), parent=n_e, mat_=M_NOTE).rotation_euler = (0, math.radians(20), 0)
    n_e["_phase"] = random.uniform(0, math.pi*2)
    n_e["_base_x"] = px; n_e["_base_y"] = py; n_e["_base_z"] = pz
    n_e["_amp_x"] = random.uniform(0.5, 1.5)
    n_e["_amp_y"] = random.uniform(0.5, 1.5)
    n_e["_amp_z"] = random.uniform(0.4, 1.0)
    n_e["_speed"] = random.uniform(0.4, 1.0)
    notes.append(n_e)

# ============ ANIMATION ============
fps = 30; duration_s = 6; total_frames = fps * duration_s

# Tango couples sway hips and turn
for c in couples:
    phase = c["root"]["_phase"]
    fac = c["root"].rotation_euler.z
    for f in range(1, total_frames + 1, 3):
        t = (f - 1) / fps
        c["root"].rotation_euler = (math.sin(t * 2.0 + phase) * math.radians(4), 0,
                                     fac + math.sin(t * 0.8 + phase) * math.radians(20))
        c["root"].keyframe_insert("rotation_euler", frame=f)
        # Woman head dramatic tilt back
        c["he_w"].rotation_euler = (math.sin(t * 2.0 + phase) * math.radians(15) + math.radians(-10), 0,
                                     math.cos(t * 1.5 + phase) * math.radians(15))
        c["he_w"].keyframe_insert("rotation_euler", frame=f)
        c["he_m"].rotation_euler = (math.sin(t * 2.0 + phase) * math.radians(5), 0,
                                     math.cos(t * 1.5 + phase) * math.radians(10))
        c["he_m"].keyframe_insert("rotation_euler", frame=f)

# Musicians play
for m in musicians:
    phase = m["root"]["_phase"]
    for f in range(1, total_frames + 1, 3):
        t = (f - 1) / fps
        m["root"].rotation_euler = (math.sin(t * 3.0 + phase) * math.radians(4), 0,
                                     m["root"].rotation_euler.z)
        m["root"].keyframe_insert("rotation_euler", frame=f)
        sc_m = 1 + math.sin(t * 5.0 + phase) * 0.05
        m["inst"].scale = (sc_m, sc_m, sc_m)
        m["inst"].keyframe_insert("scale", frame=f)

# Flag wave
for f in range(1, total_frames + 1, 5):
    t = (f - 1) / fps
    flag_e.rotation_euler = (0, 0, math.sin(t * 1.5) * math.radians(10))
    flag_e.keyframe_insert("rotation_euler", frame=f)

# 600 roses fall
for r in roses:
    phase = r["_phase"]; drift = r["_drift"]; fall = r["_fall"]; swing = r["_swing"]
    bx, bz = r["_base_x"], r["_base_z"]
    for f in range(1, total_frames + 1, 4):
        t = (f - 1) / fps
        x = bx + math.sin(t * swing + phase) * 0.6 + t * drift
        z = bz - (t * fall) % 16
        r.location = (x, r.location.y, z)
        r.rotation_euler = (t * 1.5 + phase, math.sin(t * 2.0 + phase) * math.radians(25), t * 0.8 + phase)
        r.keyframe_insert("location", frame=f)
        r.keyframe_insert("rotation_euler", frame=f)

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
        n.rotation_euler = (math.sin(t * 2.0 + phase) * math.radians(15), 0,
                             t * 0.5 + phase)
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
out_glb = os.path.join(out_dir, "pbr_argentina_proc.glb")

bpy.ops.object.select_all(action='SELECT')
bpy.ops.export_scene.gltf(
    filepath=out_glb, export_format='GLB',
    export_animations=True, export_apply=False, export_yup=True, use_selection=False,
)
size_mb = os.path.getsize(out_glb) / (1024 * 1024)
print(f"[proc_argentina_tango_buenos_aires] DONE → {out_glb} ({size_mb:.2f} MB)")
print("Argentina tango Buenos Aires: 4 tango couples (red dress + black suit) + 4 musicians (bandoneon/piano/violin/contrabass) + 10 Caminito facades multi-colored + windows + balconies + Obelisco + 8 lampposts + Argentina flag with sun + 600 roses + 400 notes")
print("🌹 FIXES: 1 brick pave ground + 600 red roses + 400 music notes (signature Argentina mandatory) 🌹")
