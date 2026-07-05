"""
proc_nepalese_kathmandu_durbar_square.py — 279e procédural AuroraIA (144e qualité)
Nepal Kathmandu Durbar Square: 5 Newar pagodas multi-tier + 4 sadhus + 4 women in sari + Hanuman statues + Mt Everest + Nepal flag double triangle + 600 prayer flags + 400 meditating sadhus
FIXES : 1 ground stone temple + signature prayer flags + sadhus
"""
import bpy, bmesh, math, random, os

random.seed(0x70AB279)

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

# Sky Himalaya
M_SKY = mat("sky", (0.55, 0.72, 0.92, 1.0), 0.0, 0.7, emission=(0.55,0.70,0.90), emission_strength=1.8)
M_SKY_LOW = mat("sky_l", (0.95, 0.78, 0.65, 1.0), 0.0, 0.7, emission=(0.95,0.78,0.65), emission_strength=1.5)
M_SUN = mat("sun", (1.0, 0.92, 0.65, 1.0), 0.0, 0.1, emission=(1.0,0.92,0.65), emission_strength=18.0)

# Stone ground
M_STONE_PAVE = mat("st", (0.65, 0.55, 0.45, 1.0), 0.0, 0.85, emission=(0.62,0.55,0.45), emission_strength=0.3)
M_STONE_DARK = mat("std", (0.42, 0.38, 0.32, 1.0), 0.0, 0.92)
M_STONE_LIGHT = mat("stl", (0.85, 0.78, 0.62, 1.0), 0.0, 0.75, emission=(0.82,0.75,0.62), emission_strength=0.4)

# Mountain (Everest)
M_MOUNTAIN_DARK = mat("md", (0.32, 0.32, 0.35, 1.0), 0.0, 0.92)
M_MOUNTAIN_GRAY = mat("mg", (0.55, 0.55, 0.55, 1.0), 0.0, 0.85)
M_SNOW = mat("sn", (0.95, 0.95, 0.95, 1.0), 0.0, 0.55, emission=(0.92,0.92,0.92), emission_strength=0.5)

# Newar pagoda (signature red brick + dark wood)
M_BRICK_RED = mat("br", (0.65, 0.32, 0.22, 1.0), 0.0, 0.75, emission=(0.62,0.30,0.22), emission_strength=0.5)
M_BRICK_DARK = mat("bdr", (0.42, 0.20, 0.15, 1.0), 0.0, 0.85)
M_WOOD_CARVED = mat("wc", (0.32, 0.18, 0.10, 1.0), 0.0, 0.75)
M_WOOD_LIGHT = mat("wl", (0.55, 0.32, 0.15, 1.0), 0.0, 0.65, emission=(0.52,0.30,0.15), emission_strength=0.4)
M_ROOF_TILE = mat("rt", (0.45, 0.22, 0.15, 1.0), 0.0, 0.75)
M_GOLD = mat("g", (0.95, 0.78, 0.20, 1.0), 0.8, 0.20, emission=(0.92,0.75,0.20), emission_strength=1.2)
M_BRASS = mat("b", (0.85, 0.65, 0.20, 1.0), 0.7, 0.30, emission=(0.82,0.62,0.20), emission_strength=0.7)
M_RED_PAINT = mat("rp", (0.85, 0.20, 0.20, 1.0), 0.0, 0.55, emission=(0.82,0.20,0.20), emission_strength=0.6)

# Sadhu skin/body paint (signature)
M_SKIN_BROWN = mat("sb", (0.75, 0.55, 0.40, 1.0), 0.0, 0.55, emission=(0.72,0.55,0.40), emission_strength=0.3)
M_BODY_ASH = mat("ba", (0.85, 0.82, 0.78, 1.0), 0.0, 0.85, emission=(0.82,0.80,0.78), emission_strength=0.4)
M_PAINT_ORANGE = mat("po", (1.0, 0.55, 0.18, 1.0), 0.0, 0.45, emission=(0.95,0.55,0.18), emission_strength=1.0)
M_PAINT_RED = mat("pr2", (0.85, 0.18, 0.20, 1.0), 0.0, 0.45, emission=(0.82,0.18,0.20), emission_strength=0.8)
M_PAINT_YELLOW = mat("py", (1.0, 0.85, 0.30, 1.0), 0.0, 0.45, emission=(0.95,0.82,0.30), emission_strength=1.0)
M_HAIR_GRAY = mat("hg", (0.55, 0.50, 0.48, 1.0), 0.0, 0.85)
M_HAIR_DREAD = mat("hd", (0.32, 0.18, 0.10, 1.0), 0.0, 0.85)
M_LOINCLOTH = mat("lc", (0.92, 0.55, 0.20, 1.0), 0.0, 0.65, emission=(0.88,0.55,0.20), emission_strength=0.6)

# Sari (signature)
M_SARI_RED = mat("sar_r", (0.85, 0.18, 0.30, 1.0), 0.0, 0.45, emission=(0.82,0.18,0.30), emission_strength=0.7)
M_SARI_PINK = mat("sar_p", (1.0, 0.45, 0.70, 1.0), 0.0, 0.45, emission=(0.95,0.45,0.65), emission_strength=0.8)
M_SARI_GREEN = mat("sar_g", (0.32, 0.65, 0.40, 1.0), 0.0, 0.45, emission=(0.30,0.62,0.40), emission_strength=0.6)
M_SARI_BLUE = mat("sar_b", (0.20, 0.42, 0.78, 1.0), 0.0, 0.45, emission=(0.20,0.42,0.75), emission_strength=0.6)
SARI_COLORS = [M_SARI_RED, M_SARI_PINK, M_SARI_GREEN, M_SARI_BLUE]

# Hanuman statue (signature monkey god)
M_HANUMAN_STONE = mat("hs", (0.55, 0.42, 0.30, 1.0), 0.0, 0.75, emission=(0.52,0.42,0.30), emission_strength=0.3)
M_HANUMAN_RED = mat("hr2", (0.78, 0.30, 0.22, 1.0), 0.0, 0.55, emission=(0.75,0.30,0.22), emission_strength=0.4)

# Bell
M_BELL_BRASS = mat("be", (0.92, 0.65, 0.18, 1.0), 0.9, 0.20, emission=(0.88,0.62,0.18), emission_strength=0.7)

# Prayer flag colors (5 signature)
M_PRAYER_BLUE = mat("pb", (0.20, 0.45, 0.85, 1.0), 0.0, 0.45, emission=(0.20,0.42,0.82), emission_strength=2.0)
M_PRAYER_WHITE = mat("pw", (0.95, 0.95, 0.92, 1.0), 0.0, 0.45, emission=(0.92,0.92,0.90), emission_strength=1.5)
M_PRAYER_RED = mat("prd", (0.85, 0.18, 0.20, 1.0), 0.0, 0.45, emission=(0.82,0.18,0.20), emission_strength=2.0)
M_PRAYER_GREEN = mat("pg", (0.30, 0.78, 0.32, 1.0), 0.0, 0.45, emission=(0.30,0.75,0.30), emission_strength=2.0)
M_PRAYER_YELLOW = mat("py2", (1.0, 0.85, 0.20, 1.0), 0.0, 0.45, emission=(0.95,0.82,0.20), emission_strength=2.2)
PRAYER_COLORS = [M_PRAYER_BLUE, M_PRAYER_WHITE, M_PRAYER_RED, M_PRAYER_GREEN, M_PRAYER_YELLOW]

# Nepal flag (signature double triangle)
M_FLAG_RED = mat("fr_n", (0.85, 0.18, 0.20, 1.0), 0.0, 0.45, emission=(0.82,0.18,0.20), emission_strength=1.2)
M_FLAG_BLUE = mat("fb_n", (0.10, 0.32, 0.65, 1.0), 0.0, 0.45, emission=(0.10,0.30,0.62), emission_strength=1.0)
M_FLAG_WHITE = mat("fw_n", (0.95, 0.95, 0.92, 1.0), 0.0, 0.30, emission=(0.92,0.92,0.88), emission_strength=2.5)

# Eyes
M_EYE = mat("ed", (0.05, 0.04, 0.04, 1.0), 0.0, 0.20)
M_EYE_INTENSE = mat("ei", (0.95, 0.95, 0.45, 1.0), 0.0, 0.20, emission=(0.92,0.92,0.45), emission_strength=2.5)

# Incense smoke (small sadhu fire)
M_SMOKE = mat("sm", (0.85, 0.82, 0.78, 1.0), 0.0, 0.95, emission=(0.85,0.82,0.78), emission_strength=1.0, alpha=0.50)

# ============ SKY ============
sky = smooth_sphere("sky", r=320, segs=32, rings=20, loc=(0,0,0), mat_=M_SKY)
sky.scale = (1,1,0.6)
sky_l = smooth_sphere("sky_l", r=280, segs=28, rings=16, loc=(0,0,5), mat_=M_SKY_LOW)
sky_l.scale = (1,1,0.3)
# Sun
sun = smooth_sphere("sun", r=8, segs=24, rings=18, loc=(-50, 110, 35), mat_=M_SUN)
for sh in range(3):
    smooth_sphere(f"sun_h{sh}", r=8 + sh*1, segs=24, rings=18, loc=(-50, 110, 35), mat_=M_SUN)

# ============ MT EVEREST (signature backdrop) ============
def make_everest(name, loc, height, base_radius):
    base = empty(name, loc)
    n_layers = int(height / 4)
    for li in range(n_layers):
        lz = li * 4
        lr1 = base_radius * (1 - li / n_layers * 0.85)
        lr2 = base_radius * (1 - (li+1) / n_layers * 0.85)
        smooth_cone(f"{name}_l{li}", r1=lr1, r2=lr2, depth=4.5, segs=20,
                    loc=(0, 0, lz + 2.25), parent=base,
                    mat_=M_MOUNTAIN_DARK if li < n_layers//2 else M_MOUNTAIN_GRAY)
    # Snow cap (signature ice cap)
    snow_e = empty(f"{name}_se", (0, 0, height * 0.50), parent=base)
    for si in range(6):
        sz_s = si * 4
        sr = base_radius * (0.55 - si / 6 * 0.45)
        smooth_cone(f"{name}_s{si}", r1=sr + 0.5, r2=sr - 0.2, depth=4, segs=18,
                    loc=(0, 0, sz_s), parent=snow_e, mat_=M_SNOW)
    smooth_cone(f"{name}_pk", r1=0.5, r2=0.05, depth=3, segs=14,
                loc=(0, 0, height - 1), parent=base, mat_=M_SNOW)
    return base

make_everest("everest", (0, 90, 0), 55, 16)
# Secondary Himalayan peaks
make_everest("peak2", (-45, 80, 0), 35, 11)
make_everest("peak3", (50, 85, 0), 40, 12)
make_everest("peak4", (-80, 90, 0), 30, 9)

# ============ ONE clean stone pave ground ============
ground = beveled_cube("ground", (200, 200, 0.5), bevel_offset=0.10, loc=(0, 0, -0.25), mat_=M_STONE_PAVE)
# Stone pavers (signature temple square)
for cbi in range(40):
    for cbj in range(40):
        bx = -30 + cbi * 1.5
        by = -30 + cbj * 1.5
        if -28 < bx < 28 and -28 < by < 28 and random.random() > 0.25:
            beveled_cube(f"pv{cbi}_{cbj}", (1.3, 1.3, 0.10), bevel_offset=0.02,
                         loc=(bx, by, 0.10),
                         mat_=M_STONE_LIGHT if (cbi + cbj) % 2 else M_STONE_DARK)

# ============ 5 NEWAR PAGODAS (signature multi-tier roofs) ============
def make_newar_pagoda(name, loc, n_tiers, base_size, scale=1.0):
    base = empty(name, loc)
    # Plinth (multi-step pyramid base signature)
    for pi in range(4):
        pz = pi * 0.40
        ps = base_size + 2 - pi * 0.5
        beveled_cube(f"{name}_pl{pi}", (ps, ps, 0.40), bevel_offset=0.08, loc=(0, 0, pz + 0.20),
                     parent=base, mat_=M_STONE_DARK)
    base_z_start = 1.6
    # Main sanctum brick walls
    sanctum_h = 3.5
    beveled_cube(f"{name}_sn", (base_size, base_size, sanctum_h), bevel_offset=0.10,
                 loc=(0, 0, base_z_start + sanctum_h/2), parent=base, mat_=M_BRICK_RED)
    # Brick lines
    for bli in range(8):
        bly = -base_size/2 + bli * (base_size/8) + base_size/16
        beveled_cube(f"{name}_bl{bli}", (base_size + 0.02, 0.04, 0.06), bevel_offset=0.005,
                     loc=(0, bly - base_size/2 - 0.02, base_z_start + sanctum_h/2),
                     parent=base, mat_=M_BRICK_DARK)
    # Carved wooden door (signature)
    beveled_cube(f"{name}_d", (1.4, 0.10, 2.5), bevel_offset=0.05,
                 loc=(0, -base_size/2 - 0.05, base_z_start + 1.25),
                 parent=base, mat_=M_WOOD_CARVED)
    # Door frame ornate
    for fi in range(3):
        beveled_cube(f"{name}_df{fi}", (1.6 + fi*0.10, 0.04, 0.10), bevel_offset=0.01,
                     loc=(0, -base_size/2 - 0.10, base_z_start + 2.55 + fi*0.10),
                     parent=base, mat_=M_GOLD)
    # Carved wooden window struts (signature)
    for wi, (wx, wy) in enumerate([(-base_size/2, 0), (base_size/2, 0), (0, base_size/2)]):
        for wci in range(4):
            beveled_cube(f"{name}_w{wi}_{wci}", (0.10, 0.10, 0.80), bevel_offset=0.01,
                         loc=(wx, wy, base_z_start + 1.5 + wci*0.10), parent=base, mat_=M_WOOD_CARVED)
    # 4 stone lions at corners (signature guardians)
    for li_g, (lx_g, ly_g) in enumerate([(-base_size/2-0.5, -base_size/2-0.5), (base_size/2+0.5, -base_size/2-0.5),
                                            (-base_size/2-0.5, base_size/2+0.5), (base_size/2+0.5, base_size/2+0.5)]):
        smooth_sphere(f"{name}_li{li_g}", r=0.35, segs=14, rings=10,
                      loc=(lx_g, ly_g, base_z_start - 0.10),
                      parent=base, mat_=M_STONE_DARK, scale=(1.3, 1.2, 1.0))
    # MULTIPLE TIERED ROOFS (signature Newar)
    current_z = base_z_start + sanctum_h
    current_size = base_size
    for ti in range(n_tiers):
        # Roof
        roof_size = current_size + 1.8 - ti * 0.4
        # Slanted roof slabs (4 sides)
        for side in range(4):
            sa = side * math.pi / 2
            slope_e = empty(f"{name}_rs{ti}_{side}_e", (0, 0, current_z + 0.4), parent=base)
            slope_e.rotation_euler = (math.radians(-35), 0, sa)
            beveled_cube(f"{name}_rs{ti}_{side}", (roof_size + 0.5, roof_size*0.8, 0.20), bevel_offset=0.06,
                         loc=(0, roof_size/2 + 0.5, 0), parent=slope_e, mat_=M_ROOF_TILE)
        # Roof tiles (decorative)
        for tr in range(int(roof_size)):
            beveled_cube(f"{name}_tr{ti}_{tr}", (roof_size + 0.6, 0.10, 0.04), bevel_offset=0.01,
                         loc=(0, -roof_size/2 - 0.1, current_z + 0.10), parent=base, mat_=M_WOOD_LIGHT)
        # Wooden struts (signature carved tundals)
        for str_si in range(4):
            sa = str_si * math.pi / 2
            strut_e = empty(f"{name}_str{ti}_{str_si}_e", (0, 0, current_z - 0.30), parent=base)
            strut_e.rotation_euler = (math.radians(-30), 0, sa)
            for sli in range(2):
                beveled_cube(f"{name}_str{ti}_{str_si}_{sli}", (0.15, 0.60, 0.10), bevel_offset=0.02,
                             loc=(sli*0.5 - 0.25, current_size/2 + 0.4, 0.20),
                             parent=strut_e, mat_=M_WOOD_CARVED)
        # Roof corner ornaments (signature gold)
        for cri in range(4):
            cra = (cri / 4.0) * math.pi * 2 + math.pi/4
            cyl(f"{name}_co{ti}_{cri}", r=0.10, depth=0.40, segs=8,
                loc=(math.cos(cra)*roof_size/2, math.sin(cra)*roof_size/2, current_z + 0.4),
                parent=base, mat_=M_GOLD)
        # Middle wall
        wall_h = 1.2 - ti * 0.15
        if ti < n_tiers - 1:
            current_size = current_size * 0.85
            beveled_cube(f"{name}_w{ti}", (current_size, current_size, wall_h), bevel_offset=0.06,
                         loc=(0, 0, current_z + 0.6 + wall_h/2), parent=base, mat_=M_BRICK_RED)
            # Small windows
            for wi in range(4):
                wa_w = (wi / 4.0) * math.pi * 2
                cyl(f"{name}_ww{ti}_{wi}", r=0.20, depth=0.10, segs=10,
                    loc=(math.cos(wa_w)*current_size/2, math.sin(wa_w)*current_size/2, current_z + 0.6 + wall_h/2),
                    parent=base, mat_=M_WOOD_CARVED).rotation_euler = (math.radians(90), 0, wa_w)
        current_z += 0.6 + wall_h
    # Final golden pinnacle (signature)
    smooth_cone(f"{name}_pn", r1=0.6, r2=0.05, depth=2, segs=14,
                loc=(0, 0, current_z + 1.0), parent=base, mat_=M_GOLD)
    smooth_sphere(f"{name}_pn_b", r=0.30, loc=(0, 0, current_z + 0.5),
                  parent=base, mat_=M_GOLD)
    return base

pagoda_pos = [(-18, -18, 3, 4), (18, -18, 4, 5), (-18, 18, 3, 4),
               (18, 18, 3, 4), (0, 0, 5, 6)]  # Central tallest
for i, (px, py, nt, bs) in enumerate(pagoda_pos):
    make_newar_pagoda(f"pg{i}", (px, py, 0), nt, bs)

# ============ 4 SADHUS (signature holy men) ============
def make_sadhu(name, loc, scale=1.0, facing=0, pose="standing"):
    base = empty(name, loc)
    base.rotation_euler = (0, 0, facing)
    # Body ash-covered (signature)
    smooth_cone(f"{name}_to", r1=0.30, r2=0.32, depth=0.85, segs=14, loc=(0, 0, 1.25),
                parent=base, mat_=M_BODY_ASH)
    # ORANGE LOINCLOTH (signature)
    cyl(f"{name}_lc", r=0.35, depth=0.45, segs=14, loc=(0, 0, 0.80),
        parent=base, mat_=M_LOINCLOTH)
    # Painted body stripes (signature horizontal)
    for sti in range(3):
        cyl(f"{name}_st{sti}", r=0.36, depth=0.05, segs=14, loc=(0, 0, 1.10 + sti*0.20),
            parent=base, mat_=random.choice([M_PAINT_ORANGE, M_PAINT_RED, M_PAINT_YELLOW]))
    # Legs (lotus pose if sitting)
    if pose == "sitting":
        for side in (-1, 1):
            cyl(f"{name}_l{side}", r=0.13, depth=0.55, segs=10,
                loc=(side*0.30, 0.20, 0.30), parent=base, mat_=M_BODY_ASH).rotation_euler = (math.radians(80), 0, 0)
    else:
        for side in (-1, 1):
            cyl(f"{name}_l{side}", r=0.11, depth=0.85, segs=10,
                loc=(side*0.13, 0, 0.45), parent=base, mat_=M_BODY_ASH)
        # Bare feet
        for side in (-1, 1):
            beveled_cube(f"{name}_f{side}", (0.10, 0.22, 0.05), bevel_offset=0.01,
                         loc=(side*0.13, 0.04, 0.03), parent=base, mat_=M_BODY_ASH)
    # Arms (one raised mudra signature)
    sh_l = empty(f"{name}_a0", (-0.30, 0, 1.65), parent=base)
    sh_l.rotation_euler = (math.radians(-150), 0, 0)
    cyl(f"{name}_ua0", r=0.07, depth=0.40, segs=10, loc=(0, 0, -0.20),
        parent=sh_l, mat_=M_BODY_ASH)
    cyl(f"{name}_fa0", r=0.06, depth=0.35, segs=10, loc=(0, 0, -0.55),
        parent=sh_l, mat_=M_BODY_ASH)
    # Right arm holding staff or rosary
    sh_r = empty(f"{name}_a1", (0.30, 0, 1.65), parent=base)
    sh_r.rotation_euler = (math.radians(-30), 0, math.radians(-15))
    cyl(f"{name}_ua1", r=0.07, depth=0.40, segs=10, loc=(0, 0, -0.20),
        parent=sh_r, mat_=M_BODY_ASH)
    cyl(f"{name}_fa1", r=0.06, depth=0.35, segs=10, loc=(0, 0, -0.55),
        parent=sh_r, mat_=M_BODY_ASH)
    # STAFF (trident signature)
    staff_e = empty(f"{name}_sf", (0.55, 0.30, 0.20), parent=base)
    cyl(f"{name}_sf_p", r=0.025, depth=2.5, segs=8, loc=(0, 0, 0),
        parent=staff_e, mat_=M_WOOD_CARVED)
    # Trident on top (signature)
    for ti in (-1, 0, 1):
        cyl(f"{name}_sf_t{ti}", r=0.020, depth=0.30, segs=6,
            loc=(ti*0.06, 0, 1.40), parent=staff_e, mat_=M_BRASS)
        smooth_cone(f"{name}_sf_tt{ti}", r1=0.05, r2=0.005, depth=0.10, segs=6,
                    loc=(ti*0.06, 0, 1.55), parent=staff_e, mat_=M_BRASS)
    # Head
    head_s_e = empty(f"{name}_he", (0, 0, 2.0), parent=base)
    smooth_sphere(f"{name}_h", r=0.18, segs=18, rings=14, loc=(0, 0, 0),
                  parent=head_s_e, mat_=M_BODY_ASH)
    # LONG DREADLOCKS (signature)
    for di in range(25):
        da = random.uniform(0, math.pi*2)
        dread_len = random.uniform(0.50, 1.20)
        for dsi in range(int(dread_len * 6)):
            cyl(f"{name}_dr{di}_{dsi}", r=0.025, depth=0.10, segs=6,
                loc=(math.cos(da)*0.18 + math.sin(dsi*0.3)*0.04,
                     math.sin(da)*0.15 + math.cos(dsi*0.3)*0.04,
                     -dsi*0.10 - 0.10),
                parent=head_s_e, mat_=M_HAIR_DREAD)
    # FOREHEAD TILAK (signature)
    beveled_cube(f"{name}_tk", (0.05, 0.04, 0.15), bevel_offset=0.005,
                 loc=(0, -0.17, 0.05), parent=head_s_e, mat_=M_PAINT_RED)
    # Ash painted face stripes (signature)
    for fi in range(3):
        beveled_cube(f"{name}_fs{fi}", (0.25, 0.04, 0.02), bevel_offset=0.005,
                     loc=(0, -0.17, -0.04 + fi*0.04), parent=head_s_e, mat_=M_BODY_ASH)
    # INTENSE EYES (signature)
    for side in (-1, 1):
        smooth_sphere(f"{name}_ey{side}", r=0.035, loc=(side*0.07, -0.17, 0.01),
                      parent=head_s_e, mat_=M_EYE_INTENSE)
        smooth_sphere(f"{name}_ep{side}", r=0.018, loc=(side*0.07, -0.20, 0.01),
                      parent=head_s_e, mat_=M_EYE)
    # Long white beard
    for bi in range(20):
        ba = random.uniform(-math.pi*0.4, math.pi*0.4)
        beard_len = random.uniform(0.30, 0.70)
        for bsi in range(int(beard_len * 6)):
            cyl(f"{name}_bd{bi}_{bsi}", r=0.020, depth=0.08, segs=6,
                loc=(math.sin(ba)*0.12, -0.12, -0.10 - bsi*0.08),
                parent=head_s_e, mat_=M_HAIR_GRAY)
    base["_phase"] = random.uniform(0, math.pi*2)
    return {"root": base, "he": head_s_e}

sadhus = []
sadhu_pos = [(-12, -8, math.radians(20), "standing"), (-4, -8, math.radians(0), "standing"),
              (4, -8, math.radians(0), "standing"), (12, -8, math.radians(-20), "standing")]
for i, (sx_s, sy_s, fac, pose) in enumerate(sadhu_pos):
    s = make_sadhu(f"sd{i}", (sx_s, sy_s, 0), facing=fac, pose=pose)
    sadhus.append(s)

# ============ 4 NEPALESE WOMEN in SARI (signature) ============
def make_nepali_woman(name, loc, scale=1.0, facing=0):
    base = empty(name, loc)
    base.rotation_euler = (0, 0, facing)
    sari_col = random.choice(SARI_COLORS)
    # Sari body wrap
    smooth_cone(f"{name}_to", r1=0.30, r2=0.34, depth=0.95, segs=14, loc=(0, 0, 1.25),
                parent=base, mat_=sari_col)
    # Sari skirt long
    skirt_e = empty(f"{name}_sk", (0, 0, 0.95), parent=base)
    for ri in range(2):
        rz = -ri * 0.20
        rr = 0.36 + ri * 0.05
        for rj in range(20):
            rja = (rj / 20.0) * math.pi * 2
            beveled_cube(f"{name}_r{ri}_{rj}", (0.06, 0.10, 0.55), bevel_offset=0.01,
                         loc=(math.cos(rja)*rr, math.sin(rja)*rr, rz - 0.27),
                         parent=skirt_e, mat_=sari_col).rotation_euler = (math.cos(rja)*0.05, math.sin(rja)*0.05, rja)
    # Sari pallu (signature drape over shoulder)
    pallu_e = empty(f"{name}_pa", (0, -0.30, 1.60), parent=base)
    pallu_e.rotation_euler = (math.radians(45), 0, 0)
    beveled_cube(f"{name}_pa_p", (0.45, 0.06, 0.70), bevel_offset=0.04, loc=(0, 0, 0),
                 parent=pallu_e, mat_=sari_col)
    # Legs
    for side in (-1, 1):
        cyl(f"{name}_l{side}", r=0.10, depth=0.80, segs=10,
            loc=(side*0.13, 0, 0.43), parent=base, mat_=M_SKIN_BROWN)
    # Arms
    for side_idx, side in enumerate((-1, 1)):
        sh = empty(f"{name}_a{side_idx}", (side*0.30, 0, 1.60), parent=base)
        sh.rotation_euler = (math.radians(-70), 0, math.radians(side*30))
        cyl(f"{name}_ua{side_idx}", r=0.07, depth=0.35, segs=10, loc=(0, 0, -0.18),
            parent=sh, mat_=M_SKIN_BROWN)
        cyl(f"{name}_fa{side_idx}", r=0.06, depth=0.30, segs=10, loc=(0, 0, -0.50),
            parent=sh, mat_=M_SKIN_BROWN)
        # Bangles (signature)
        for bi in range(4):
            cyl(f"{name}_bg{side_idx}_{bi}", r=0.063, depth=0.025, segs=10,
                loc=(0, 0, -0.60 + bi*0.025), parent=sh, mat_=M_GOLD)
    # Head
    head_w_e = empty(f"{name}_he", (0, 0, 1.95), parent=base)
    smooth_sphere(f"{name}_h", r=0.17, segs=18, rings=14, loc=(0, 0, 0),
                  parent=head_w_e, mat_=M_SKIN_BROWN)
    # Long black hair
    for hi in range(20):
        ha = random.uniform(math.pi*0.5, math.pi*1.5)
        hair_len = random.uniform(0.5, 0.8)
        for hsi in range(int(hair_len * 6)):
            cyl(f"{name}_hr{hi}_{hsi}", r=0.025, depth=0.10, segs=6,
                loc=(math.cos(ha)*0.15, math.sin(ha)*0.13, -hsi*0.10 - 0.05),
                parent=head_w_e, mat_=M_HAIR_DREAD)
    # Bindi (signature red dot)
    smooth_sphere(f"{name}_bn", r=0.025, loc=(0, -0.16, 0.08),
                  parent=head_w_e, mat_=M_PAINT_RED)
    # Eyes
    for side in (-1, 1):
        smooth_sphere(f"{name}_ey{side}", r=0.025, loc=(side*0.06, -0.15, 0.02),
                      parent=head_w_e, mat_=M_EYE)
    # Earrings (signature gold)
    for side in (-1, 1):
        cyl(f"{name}_er{side}", r=0.025, depth=0.10, segs=8,
            loc=(side*0.18, 0, -0.05), parent=head_w_e, mat_=M_GOLD)
    # Nose ring
    cyl(f"{name}_nr", r=0.015, depth=0.04, segs=8, loc=(-0.04, -0.16, -0.02),
        parent=head_w_e, mat_=M_GOLD).rotation_euler = (0, math.radians(90), 0)
    base["_phase"] = random.uniform(0, math.pi*2)
    return {"root": base, "he": head_w_e}

women = []
woman_pos = [(-15, 8, math.radians(180)), (-5, 12, math.radians(180)),
              (5, 12, math.radians(180)), (15, 8, math.radians(180))]
for i, (wx, wy, fac) in enumerate(woman_pos):
    w = make_nepali_woman(f"nw{i}", (wx, wy, 0), facing=fac)
    women.append(w)

# ============ HANUMAN STATUE (signature monkey god) ============
def make_hanuman(name, loc):
    base = empty(name, loc)
    # Pedestal
    cyl(f"{name}_pd", r=1, depth=0.6, segs=18, loc=(0, 0, 0.3), parent=base, mat_=M_STONE_DARK)
    # Red-painted body (signature)
    smooth_sphere(f"{name}_bo", r=0.60, segs=14, rings=12, loc=(0, 0, 1.2),
                  parent=base, mat_=M_HANUMAN_RED, scale=(1, 0.85, 1.4))
    # Head
    head_h_e = empty(f"{name}_he", (0, 0, 2.45), parent=base)
    smooth_sphere(f"{name}_h", r=0.30, segs=14, rings=12, loc=(0, 0, 0),
                  parent=head_h_e, mat_=M_HANUMAN_RED)
    # Monkey snout
    smooth_sphere(f"{name}_sn", r=0.15, segs=12, rings=10, loc=(0, -0.20, -0.05),
                  parent=head_h_e, mat_=M_HANUMAN_RED, scale=(0.85, 1.3, 0.85))
    # Crown
    cyl(f"{name}_cr", r=0.32, depth=0.20, segs=14, loc=(0, 0, 0.20),
        parent=head_h_e, mat_=M_GOLD)
    # Crown points
    for cp in range(5):
        cpa = (cp / 5.0) * math.pi * 2
        smooth_cone(f"{name}_cp{cp}", r1=0.08, r2=0.02, depth=0.25, segs=8,
                    loc=(math.cos(cpa)*0.28, math.sin(cpa)*0.28, 0.40),
                    parent=head_h_e, mat_=M_GOLD)
    # Eyes
    for side in (-1, 1):
        smooth_sphere(f"{name}_ey{side}", r=0.05, loc=(side*0.10, -0.22, 0.05),
                      parent=head_h_e, mat_=M_GOLD)
    # Arms (raised holding mace)
    for side_idx, side in enumerate((-1, 1)):
        sh = empty(f"{name}_a{side_idx}", (side*0.50, 0, 1.85), parent=base)
        sh.rotation_euler = (math.radians(-120 if side_idx == 0 else -60), 0, math.radians(side*30))
        cyl(f"{name}_ua{side_idx}", r=0.12, depth=0.55, segs=10, loc=(0, 0, -0.28),
            parent=sh, mat_=M_HANUMAN_RED)
    # Mace (signature gada)
    cyl(f"{name}_md", r=0.06, depth=0.80, segs=10, loc=(-0.45, 0, 2.35),
        parent=base, mat_=M_GOLD).rotation_euler = (math.radians(180), 0, 0)
    smooth_sphere(f"{name}_md_h", r=0.20, segs=12, rings=10, loc=(-0.45, 0, 2.85),
                  parent=base, mat_=M_GOLD)
    # Tail (signature monkey)
    tail_e = empty(f"{name}_t", (-0.40, 0, 1.30), parent=base)
    for ti in range(8):
        ta_t = (ti / 8.0) * math.pi
        tx_t = -math.cos(ta_t) * 0.5 - 0.3
        tz_t = math.sin(ta_t) * 0.5 - 0.1
        cyl(f"{name}_tl{ti}", r=0.08 - ti*0.005, depth=0.15, segs=10,
            loc=(tx_t, 0, tz_t), parent=tail_e, mat_=M_HANUMAN_RED)
    return base

make_hanuman("hanuman", (0, -20, 0))

# ============ TEMPLE BELLS (signature) ============
for bi in range(8):
    ba = (bi / 8.0) * math.pi * 2
    bell_x = math.cos(ba) * 25
    bell_y = math.sin(ba) * 25
    bell_e = empty(f"bell{bi}", (bell_x, bell_y, 4))
    # Bell shape
    smooth_cone(f"bell{bi}_b", r1=0.30, r2=0.35, depth=0.50, segs=18, loc=(0, 0, 0),
                parent=bell_e, mat_=M_BELL_BRASS)
    # Top knob
    smooth_sphere(f"bell{bi}_k", r=0.12, segs=12, rings=10, loc=(0, 0, 0.35),
                  parent=bell_e, mat_=M_BELL_BRASS)
    # Clapper
    cyl(f"bell{bi}_cl", r=0.04, depth=0.20, segs=8, loc=(0, 0, -0.25),
        parent=bell_e, mat_=M_BELL_BRASS)
    # Hanging post
    cyl(f"bell{bi}_p", r=0.06, depth=4, segs=10, loc=(0, 0, 2),
        parent=bell_e, mat_=M_WOOD_CARVED)

# ============ NEPAL FLAG (signature double triangle) ============
flag_e = empty("flag", (-40, 25, 0))
cyl("fl_p", r=0.10, depth=10, segs=10, loc=(0, 0, 5), parent=flag_e, mat_=M_WOOD_CARVED)
# Double triangle shape (signature - only non-rectangular national flag)
# Lower triangle (larger)
for ti_lt in range(8):
    tw = 2.5 - ti_lt * 0.25
    beveled_cube(f"fl_lt{ti_lt}", (tw, 0.05, 0.25), bevel_offset=0.02,
                 loc=(tw/2 + 0.05, 0, 7 + ti_lt*0.25), parent=flag_e, mat_=M_FLAG_RED)
# Upper triangle (smaller)
for ti_ut in range(7):
    tw_u = 2.2 - ti_ut * 0.25
    beveled_cube(f"fl_ut{ti_ut}", (tw_u, 0.05, 0.25), bevel_offset=0.02,
                 loc=(tw_u/2 + 0.05, 0, 9 + ti_ut*0.25), parent=flag_e, mat_=M_FLAG_RED)
# Blue border (signature)
for bi in range(20):
    bz = 7 + bi * 0.18
    bw_b = 2.5 - (bi if bi < 8 else (16 - bi)) * 0.20 if bi < 16 else 0
    if bi >= 8 and bi <= 15:
        bw_b = 2.2 - (bi - 8) * 0.25
    if bw_b > 0:
        beveled_cube(f"fl_bb{bi}", (0.10, 0.06, 0.20), bevel_offset=0.01,
                     loc=(bw_b + 0.10, 0, bz), parent=flag_e, mat_=M_FLAG_BLUE)
# Sun (upper triangle - signature)
smooth_sphere("fl_sun", r=0.25, segs=14, rings=10, loc=(0.8, -0.06, 10.3),
              parent=flag_e, mat_=M_FLAG_WHITE)
# Sun rays
for ri in range(8):
    rang = (ri / 8.0) * math.pi * 2
    beveled_cube(f"fl_sr{ri}", (0.04, 0.05, 0.15), bevel_offset=0.005,
                 loc=(0.8 + math.cos(rang)*0.35, -0.06, 10.3 + math.sin(rang)*0.35),
                 parent=flag_e, mat_=M_FLAG_WHITE).rotation_euler = (0, rang, 0)
# Moon (lower triangle - signature)
smooth_sphere("fl_moon", r=0.20, segs=14, rings=10, loc=(0.7, -0.06, 8.5),
              parent=flag_e, mat_=M_FLAG_WHITE, scale=(1, 0.3, 1))
flag_e["_phase"] = 0

# ============================================================
# 600 PRAYER FLAGS + 400 MEDITATING SADHUS (PARTICULES SIGNATURES)
# ============================================================
prayer_flags = []
# Strings of prayer flags across the square (signature 5 colors)
n_strings = 25
for str_i in range(n_strings):
    str_angle = (str_i / n_strings) * math.pi * 2
    str_x_s = math.cos(str_angle) * 30
    str_y_s = math.sin(str_angle) * 30
    str_x_e = math.cos(str_angle + 0.4) * 30
    str_y_e = math.sin(str_angle + 0.4) * 30
    # 24 flags per string
    for fi in range(24):
        t = fi / 24.0
        fx = str_x_s + (str_x_e - str_x_s) * t
        fy = str_y_s + (str_y_e - str_y_s) * t
        fz = random.uniform(8, 16)
        flag_col = PRAYER_COLORS[fi % 5]
        pf = empty(f"pf{str_i}_{fi}", (fx, fy, fz))
        beveled_cube(f"pf{str_i}_{fi}_b", (0.30, 0.05, 0.40), bevel_offset=0.02,
                     loc=(0, 0, 0), parent=pf, mat_=flag_col)
        pf["_phase"] = random.uniform(0, math.pi*2)
        pf["_speed"] = random.uniform(1.0, 2.5)
        prayer_flags.append(pf)

# Total exactly 600 — currently 25 strings * 24 = 600 ✓

# 400 meditating sadhus floating particles (signature)
mini_sadhus = []
for i in range(400):
    px = random.uniform(-90, 90)
    py = random.uniform(-90, 90)
    pz = random.uniform(3, 30)
    ms_e = empty(f"ms{i}", (px, py, pz))
    # Tiny sadhu silhouette (sitting cross-legged signature)
    # Body
    smooth_cone(f"ms{i}_to", r1=0.08, r2=0.09, depth=0.20, segs=10, loc=(0, 0, 0.10),
                parent=ms_e, mat_=M_LOINCLOTH)
    # Head
    smooth_sphere(f"ms{i}_h", r=0.05, segs=8, rings=6, loc=(0, 0, 0.25),
                  parent=ms_e, mat_=M_BODY_ASH)
    # Crossed legs
    cyl(f"ms{i}_l", r=0.08, depth=0.05, segs=8, loc=(0, 0, 0),
        parent=ms_e, mat_=M_BODY_ASH)
    # Hands in meditation pose
    for side in (-1, 1):
        smooth_sphere(f"ms{i}_hd{side}", r=0.025, loc=(side*0.06, 0, 0.05),
                      parent=ms_e, mat_=M_BODY_ASH)
    # Aura glow
    smooth_sphere(f"ms{i}_au", r=0.15, segs=10, rings=8, loc=(0, 0, 0.15),
                  parent=ms_e, mat_=M_PAINT_YELLOW)
    ms_e["_phase"] = random.uniform(0, math.pi*2)
    ms_e["_base_x"] = px; ms_e["_base_y"] = py; ms_e["_base_z"] = pz
    ms_e["_amp"] = random.uniform(0.5, 1.5)
    ms_e["_speed"] = random.uniform(0.3, 0.8)
    mini_sadhus.append(ms_e)

# ============ ANIMATION ============
fps = 30; duration_s = 6; total_frames = fps * duration_s

# Sadhus meditate sway
for s in sadhus:
    phase = s["root"]["_phase"]
    for f in range(1, total_frames + 1, 5):
        t = (f - 1) / fps
        s["root"].rotation_euler = (math.sin(t * 0.8 + phase) * math.radians(2), 0,
                                     s["root"].rotation_euler.z)
        s["root"].keyframe_insert("rotation_euler", frame=f)
        s["he"].rotation_euler = (math.sin(t * 0.8 + phase) * math.radians(3), 0, 0)
        s["he"].keyframe_insert("rotation_euler", frame=f)

# Women sway gracefully
for w in women:
    phase = w["root"]["_phase"]
    for f in range(1, total_frames + 1, 5):
        t = (f - 1) / fps
        w["root"].rotation_euler = (math.sin(t * 1.0 + phase) * math.radians(2), 0,
                                     w["root"].rotation_euler.z)
        w["root"].keyframe_insert("rotation_euler", frame=f)
        w["he"].rotation_euler = (math.sin(t * 1.0 + phase) * math.radians(4), 0,
                                   math.cos(t * 0.8 + phase) * math.radians(15))
        w["he"].keyframe_insert("rotation_euler", frame=f)

# Flag wave
for f in range(1, total_frames + 1, 5):
    t = (f - 1) / fps
    flag_e.rotation_euler = (0, 0, math.sin(t * 1.5) * math.radians(15))
    flag_e.keyframe_insert("rotation_euler", frame=f)

# 600 prayer flags flutter
for pf in prayer_flags:
    phase = pf["_phase"]; speed = pf["_speed"]
    for f in range(1, total_frames + 1, 4):
        t = (f - 1) / fps
        pf.rotation_euler = (math.sin(t * speed + phase) * math.radians(25),
                              math.cos(t * speed * 0.8 + phase) * math.radians(20),
                              math.sin(t * speed * 1.2 + phase) * math.radians(15))
        pf.keyframe_insert("rotation_euler", frame=f)

# 400 mini sadhus float meditating
for ms in mini_sadhus:
    phase = ms["_phase"]; speed = ms["_speed"]; amp = ms["_amp"]
    bx, by, bz_m = ms["_base_x"], ms["_base_y"], ms["_base_z"]
    for f in range(1, total_frames + 1, 4):
        t = (f - 1) / fps
        x = bx + math.sin(t * speed + phase) * amp
        y = by + math.cos(t * speed * 0.7 + phase) * amp
        z = bz_m + math.sin(t * speed * 1.3 + phase) * 0.8
        ms.location = (x, y, z)
        ms.rotation_euler = (0, 0, t * 0.3 + phase)
        ms.keyframe_insert("location", frame=f)
        ms.keyframe_insert("rotation_euler", frame=f)

# ============ EXPORT ============
out_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "public", "_pbr_test")
out_dir = os.path.normpath(out_dir)
os.makedirs(out_dir, exist_ok=True)
out_glb = os.path.join(out_dir, "pbr_nepal_proc.glb")

bpy.ops.object.select_all(action='SELECT')
bpy.ops.export_scene.gltf(
    filepath=out_glb, export_format='GLB',
    export_animations=True, export_apply=False, export_yup=True, use_selection=False,
)
size_mb = os.path.getsize(out_glb) / (1024 * 1024)
print(f"[proc_nepalese_kathmandu_durbar_square] DONE → {out_glb} ({size_mb:.2f} MB)")
print("Nepal Kathmandu Durbar Square: 5 Newar pagodas (multi-step plinth + brick walls + 4 corner lions + tiered roofs 3-5 tiers + carved tundal struts + corner gold ornaments + golden pinnacles + sanctum doors) + Mt Everest 55m + 3 secondary Himalayan peaks + 4 sadhus (ash-painted bodies + orange loincloths + dreadlocks + tilak forehead + intense glowing eyes + tridents) + 4 Nepali women in colorful saris (pallu drape + bangles + bindi + nose rings + earrings) + Hanuman statue (red painted monkey god + crown + mace + tail) + 8 temple bells with hanging posts + Nepal flag (signature unique double triangle + sun + moon) + 600 prayer flags (5 colors signature 25 strings of 24 flags) + 400 mini meditating sadhus with golden aura")
print("🕉️ FIXES: 1 stone pave ground + 600 prayer flags (blue/white/red/green/yellow) + 400 meditating sadhus floating signature 🕉️")
