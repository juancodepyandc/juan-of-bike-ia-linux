"""
proc_medieval_king_coronation.py — 205e procédural AuroraIA (69e qualité)
Couronnement roi médiéval : trône + roi + reine + archevêque + 15 nobles + 8 dames + 6 gardes + vitraux + bannières + chandeliers
"""
import bpy, bmesh, math, random, os

random.seed(0xC0205A)

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
M_SKY = mat("sky", (0.12, 0.10, 0.18, 1.0), 0.0, 0.7, emission=(0.18,0.15,0.25), emission_strength=0.6)
M_STONE = mat("stone", (0.55, 0.50, 0.45, 1.0), 0.0, 0.75, emission=(0.45,0.40,0.35), emission_strength=0.5)
M_STONE_DARK = mat("stone_d", (0.35, 0.32, 0.28, 1.0), 0.0, 0.85)
M_FLOOR_TILE = mat("floor_t", (0.65, 0.58, 0.48, 1.0), 0.1, 0.45, emission=(0.50,0.45,0.38), emission_strength=0.6)
M_FLOOR_DARK = mat("floor_d", (0.30, 0.25, 0.20, 1.0), 0.0, 0.70)
M_CARPET_RED = mat("carpet", (0.65, 0.10, 0.10, 1.0), 0.0, 0.55, emission=(0.60,0.10,0.10), emission_strength=0.7)
M_CARPET_GOLD = mat("carpet_g", (0.85, 0.65, 0.25, 1.0), 0.4, 0.40, emission=(0.78,0.58,0.22), emission_strength=0.8)
M_WOOD = mat("wood", (0.40, 0.25, 0.12, 1.0), 0.0, 0.70)
M_WOOD_RICH = mat("wood_r", (0.55, 0.32, 0.15, 1.0), 0.0, 0.55, emission=(0.45,0.27,0.13), emission_strength=0.4)

# Gold
M_GOLD = mat("gold", (1.0, 0.78, 0.25, 1.0), 0.95, 0.18, emission=(0.95,0.72,0.22), emission_strength=1.2)
M_GOLD_BRIGHT = mat("gold_b", (1.0, 0.88, 0.40, 1.0), 0.95, 0.15, emission=(1.0,0.85,0.40), emission_strength=2.5)
M_SILVER = mat("silver", (0.85, 0.85, 0.88, 1.0), 0.92, 0.20, emission=(0.78,0.78,0.80), emission_strength=0.4)
M_BRONZE = mat("bronze", (0.65, 0.42, 0.20, 1.0), 0.85, 0.40, emission=(0.55,0.35,0.18), emission_strength=0.6)

# Gems
M_RUBY = mat("ruby", (0.85, 0.10, 0.20, 1.0), 0.3, 0.20, emission=(0.95,0.15,0.25), emission_strength=4.0)
M_SAPPHIRE = mat("sapphire", (0.15, 0.30, 0.85, 1.0), 0.3, 0.20, emission=(0.20,0.40,1.0), emission_strength=3.5)
M_EMERALD = mat("emerald", (0.10, 0.75, 0.30, 1.0), 0.3, 0.20, emission=(0.15,0.85,0.35), emission_strength=3.0)
M_PEARL = mat("pearl", (0.95, 0.95, 0.95, 1.0), 0.4, 0.25, emission=(0.85,0.85,0.85), emission_strength=1.5)

# Vitraux (stained glass)
M_VITRAIL_RED = mat("vit_r", (0.95, 0.10, 0.15, 1.0), 0.0, 0.10, emission=(1.0,0.15,0.20), emission_strength=8.0, alpha=0.65)
M_VITRAIL_BLUE = mat("vit_b", (0.10, 0.35, 0.95, 1.0), 0.0, 0.10, emission=(0.15,0.40,1.0), emission_strength=8.5, alpha=0.65)
M_VITRAIL_GREEN = mat("vit_g", (0.20, 0.75, 0.30, 1.0), 0.0, 0.10, emission=(0.25,0.85,0.35), emission_strength=8.0, alpha=0.65)
M_VITRAIL_YELLOW = mat("vit_y", (1.0, 0.85, 0.25, 1.0), 0.0, 0.10, emission=(1.0,0.85,0.30), emission_strength=9.0, alpha=0.65)
M_VITRAIL_PURPLE = mat("vit_p", (0.75, 0.30, 0.95, 1.0), 0.0, 0.10, emission=(0.80,0.35,1.0), emission_strength=8.5, alpha=0.65)
M_VITRAIL_LEAD = mat("vit_lead", (0.15, 0.12, 0.10, 1.0), 0.4, 0.45)

# Skin
M_SKIN = mat("skin", (0.92, 0.78, 0.65, 1.0), 0.0, 0.55, emission=(0.82,0.70,0.58), emission_strength=0.3)
M_SKIN_DARK = mat("skin_d", (0.55, 0.42, 0.30, 1.0), 0.0, 0.60, emission=(0.45,0.35,0.25), emission_strength=0.3)
M_HAIR_BLOND = mat("hair_b", (0.85, 0.65, 0.30, 1.0), 0.0, 0.70, emission=(0.80,0.60,0.28), emission_strength=0.4)
M_HAIR_BROWN = mat("hair_br", (0.30, 0.18, 0.10, 1.0), 0.0, 0.80)
M_HAIR_BLACK = mat("hair_bk", (0.06, 0.05, 0.04, 1.0), 0.0, 0.85)
M_HAIR_GREY = mat("hair_g", (0.65, 0.62, 0.60, 1.0), 0.0, 0.75)
M_HAIR_WHITE = mat("hair_w", (0.92, 0.92, 0.88, 1.0), 0.0, 0.75, emission=(0.85,0.85,0.82), emission_strength=0.5)
M_BEARD_GREY = mat("beard_g", (0.55, 0.52, 0.48, 1.0), 0.0, 0.85)
M_BEARD_BROWN = mat("beard_br", (0.30, 0.18, 0.10, 1.0), 0.0, 0.80)
M_BEARD_WHITE = mat("beard_w", (0.92, 0.92, 0.88, 1.0), 0.0, 0.80, emission=(0.85,0.85,0.82), emission_strength=0.4)

# Royal robes
M_ROYAL_RED = mat("royal_r", (0.55, 0.05, 0.10, 1.0), 0.0, 0.40, emission=(0.50,0.08,0.10), emission_strength=0.7)
M_ROYAL_PURPLE = mat("royal_p", (0.40, 0.10, 0.55, 1.0), 0.0, 0.45, emission=(0.38,0.10,0.50), emission_strength=0.7)
M_ROYAL_BLUE = mat("royal_b", (0.10, 0.20, 0.55, 1.0), 0.0, 0.45, emission=(0.10,0.20,0.50), emission_strength=0.6)
M_ROYAL_GREEN = mat("royal_g", (0.10, 0.45, 0.20, 1.0), 0.0, 0.45, emission=(0.10,0.40,0.18), emission_strength=0.6)
M_ERMINE = mat("ermine", (0.95, 0.93, 0.88, 1.0), 0.0, 0.80, emission=(0.88,0.85,0.80), emission_strength=0.5)
M_ERMINE_DOT = mat("ermine_d", (0.05, 0.05, 0.05, 1.0), 0.0, 0.85)
M_VELVET_RED = mat("velvet_r", (0.45, 0.08, 0.10, 1.0), 0.0, 0.65, emission=(0.40,0.10,0.10), emission_strength=0.5)
M_VELVET_BLUE = mat("velvet_b", (0.12, 0.20, 0.45, 1.0), 0.0, 0.65, emission=(0.12,0.20,0.42), emission_strength=0.5)
M_VELVET_GREEN = mat("velvet_g", (0.15, 0.40, 0.18, 1.0), 0.0, 0.65, emission=(0.15,0.38,0.18), emission_strength=0.4)
M_VELVET_PURPLE = mat("velvet_p", (0.35, 0.10, 0.45, 1.0), 0.0, 0.65, emission=(0.35,0.12,0.45), emission_strength=0.5)
M_TUNIC_BROWN = mat("tunic_br", (0.40, 0.25, 0.15, 1.0), 0.0, 0.70)

# Dress (ladies)
M_DRESS_PINK = mat("dress_p", (0.85, 0.55, 0.70, 1.0), 0.0, 0.50, emission=(0.78,0.50,0.65), emission_strength=0.6)
M_DRESS_GOLD = mat("dress_g", (0.85, 0.72, 0.30, 1.0), 0.3, 0.40, emission=(0.78,0.65,0.28), emission_strength=0.7)
M_DRESS_TEAL = mat("dress_t", (0.20, 0.55, 0.60, 1.0), 0.0, 0.45, emission=(0.18,0.50,0.55), emission_strength=0.6)
M_DRESS_LAVENDER = mat("dress_l", (0.70, 0.55, 0.85, 1.0), 0.0, 0.50, emission=(0.65,0.50,0.78), emission_strength=0.6)

# Armor
M_ARMOR_STEEL = mat("armor", (0.55, 0.55, 0.60, 1.0), 0.95, 0.20, emission=(0.50,0.50,0.55), emission_strength=0.5)
M_ARMOR_GOLD = mat("armor_g", (1.0, 0.78, 0.30, 1.0), 0.95, 0.18, emission=(0.95,0.72,0.25), emission_strength=0.9)

# Bishop / archbishop
M_BISHOP_WHITE = mat("bishop_w", (0.95, 0.92, 0.85, 1.0), 0.0, 0.55, emission=(0.88,0.85,0.78), emission_strength=0.7)
M_BISHOP_GOLD = mat("bishop_g", (0.95, 0.72, 0.25, 1.0), 0.5, 0.30, emission=(0.85,0.65,0.22), emission_strength=0.9)
M_MITRE = mat("mitre", (1.0, 0.95, 0.85, 1.0), 0.0, 0.45, emission=(0.95,0.90,0.80), emission_strength=0.8)
M_CROZIER = mat("crozier", (0.95, 0.78, 0.25, 1.0), 0.95, 0.18, emission=(0.90,0.72,0.25), emission_strength=1.2)

# Candle / chandelier
M_CANDLE = mat("candle", (0.95, 0.92, 0.80, 1.0), 0.0, 0.45, emission=(0.95,0.90,0.78), emission_strength=0.7)
M_FLAME = mat("flame", (1.0, 0.65, 0.20, 1.0), 0.0, 0.10, emission=(1.0,0.70,0.25), emission_strength=14.0)
M_FLAME_INNER = mat("flame_i", (1.0, 0.92, 0.50, 1.0), 0.0, 0.10, emission=(1.0,0.95,0.60), emission_strength=22.0)

# Banner / heraldry
BANNER_COLORS = [
    mat("ban_red", (0.65, 0.15, 0.15, 1.0), 0.0, 0.55, emission=(0.60,0.15,0.13), emission_strength=0.7),
    mat("ban_blue", (0.15, 0.30, 0.65, 1.0), 0.0, 0.55, emission=(0.15,0.28,0.60), emission_strength=0.7),
    mat("ban_gold", (0.85, 0.65, 0.25, 1.0), 0.3, 0.45, emission=(0.78,0.58,0.22), emission_strength=0.8),
    mat("ban_green", (0.20, 0.55, 0.30, 1.0), 0.0, 0.55, emission=(0.18,0.50,0.28), emission_strength=0.6),
    mat("ban_purple", (0.55, 0.20, 0.65, 1.0), 0.0, 0.55, emission=(0.50,0.20,0.60), emission_strength=0.7),
    mat("ban_white", (0.92, 0.90, 0.85, 1.0), 0.0, 0.50, emission=(0.85,0.82,0.78), emission_strength=0.6),
]
M_BANNER_TRIM = mat("ban_trim", (1.0, 0.78, 0.25, 1.0), 0.95, 0.18, emission=(0.95,0.72,0.22), emission_strength=0.9)

# Hound
M_HOUND = mat("hound", (0.55, 0.40, 0.25, 1.0), 0.0, 0.65, emission=(0.50,0.35,0.22), emission_strength=0.3)
M_HOUND_EYE = mat("hound_eye", (1.0, 0.65, 0.10, 1.0), 0.0, 0.15, emission=(1.0,0.65,0.10), emission_strength=3.5)

# Confetti
M_CONFETTI = mat("confetti", (1.0, 0.85, 0.40, 1.0), 0.0, 0.30, emission=(1.0,0.85,0.40), emission_strength=4.0)

# ============ HALL STRUCTURE ============
hall_e = empty("hall", loc=(0, 0, 0))

# Floor (tiled - 2 colors checker pattern subtle)
ground = beveled_cube("floor", (32, 28, 0.4), bevel_offset=0.05, loc=(0, 0, -0.2), parent=hall_e, mat_=M_FLOOR_TILE)
# Checker pattern dark tiles
for i in range(-7, 8, 2):
    for j in range(-6, 7, 2):
        if (i + j) % 4 == 0:
            beveled_cube(f"tile_d_{i}_{j}", (2, 2, 0.05), loc=(i*2, j*2, 0.02),
                         parent=hall_e, mat_=M_FLOOR_DARK)

# 4 walls (high)
beveled_cube("wall_back", (32, 0.5, 16), bevel_offset=0.05, loc=(0, 14, 8), parent=hall_e, mat_=M_STONE)
beveled_cube("wall_left", (0.5, 28, 16), bevel_offset=0.05, loc=(-16, 0, 8), parent=hall_e, mat_=M_STONE)
beveled_cube("wall_right", (0.5, 28, 16), bevel_offset=0.05, loc=(16, 0, 8), parent=hall_e, mat_=M_STONE)
# Vaulted ceiling (peaked)
for side in (-1, 1):
    beveled_cube(f"ceil_{side}", (32, 14.5, 0.4), bevel_offset=0.05,
                 loc=(0, side*7, 17), parent=hall_e, mat_=M_STONE_DARK).rotation_euler = (math.radians(side*-15), 0, 0)
# Ridge beam
beveled_cube("ridge", (32, 0.5, 0.5), loc=(0, 0, 18.5), parent=hall_e, mat_=M_WOOD_RICH)

# RED CARPET LONG (path from entrance to throne)
beveled_cube("carpet", (5, 20, 0.06), bevel_offset=0.02, loc=(0, -3, 0.03), parent=hall_e, mat_=M_CARPET_RED)
# Gold trim 2 strips
for side in (-1, 1):
    beveled_cube(f"carpet_trim_{side}", (0.20, 20, 0.04), loc=(side*2.5, -3, 0.06),
                 parent=hall_e, mat_=M_CARPET_GOLD)

# ============ 6 COLUMNS ROMANESQUES ============
columns_pos = [(-7, -2), (-7, 5), (-7, 12), (7, -2), (7, 5), (7, 12)]
for ci, (cx, cy) in enumerate(columns_pos):
    col_e = empty(f"col_e{ci}", (cx, cy, 0), parent=hall_e)
    # Base square
    beveled_cube(f"col_base{ci}", (1.1, 1.1, 0.4), bevel_offset=0.06,
                 loc=(0, 0, 0.20), parent=col_e, mat_=M_STONE)
    # Shaft cylinder
    cyl(f"col_shaft{ci}", r=0.45, depth=14, segs=20,
        loc=(0, 0, 7.4), parent=col_e, mat_=M_STONE)
    # Capital (cushion/cubic Romanesque signature)
    beveled_cube(f"col_cap{ci}", (1.0, 1.0, 0.5), bevel_offset=0.10,
                 loc=(0, 0, 14.65), parent=col_e, mat_=M_STONE)
    beveled_cube(f"col_abacus{ci}", (1.15, 1.15, 0.15), loc=(0, 0, 15.0),
                 parent=col_e, mat_=M_STONE_DARK)
    # Decorative ring
    cyl(f"col_ring{ci}", r=0.50, depth=0.10, segs=20,
        loc=(0, 0, 1.5), parent=col_e, mat_=M_GOLD)

# Arches between columns (3 arches each side)
for side_idx, side_x in enumerate((-7, 7)):
    for ai in range(2):
        ax_mid = (-2 + 5 + ai * 7) / 2
        # Approximate arch with 5 sphere chunks
        for j in range(5):
            t = j / 4.0
            angle = t * math.pi
            ay = -2 + ai*7 + 3.5 * (t - 0.5) * 2
            az = 15.0 + math.sin(angle) * 1.5
            smooth_sphere(f"arch_{side_idx}_{ai}_{j}", r=0.30,
                          loc=(side_x, ay, az), parent=hall_e, mat_=M_STONE)

# ============ VITRAUX (stained glass windows on walls) ============
# 4 windows back wall + 3 each side wall = 10 windows
def make_vitrail(name, loc, parent, scale=1.0, on_wall="back"):
    v_e = empty(name, loc, parent=parent)
    # Frame (pointed arch Gothic-Romanesque)
    if on_wall == "back":
        frame_rot = (math.radians(90), 0, 0)
    elif on_wall == "left":
        frame_rot = (math.radians(90), 0, math.radians(90))
    elif on_wall == "right":
        frame_rot = (math.radians(90), 0, math.radians(-90))
    # Window panes (8 colorful)
    pane_colors = [M_VITRAIL_RED, M_VITRAIL_BLUE, M_VITRAIL_GREEN,
                   M_VITRAIL_YELLOW, M_VITRAIL_PURPLE, M_VITRAIL_RED,
                   M_VITRAIL_BLUE, M_VITRAIL_GREEN]
    for r_idx in range(4):
        for c_idx in range(2):
            pane_idx = r_idx * 2 + c_idx
            pane_x = (c_idx - 0.5) * 0.45 * scale
            pane_z = (r_idx - 1.5) * 0.65 * scale
            pane = beveled_cube(f"{name}_pane{pane_idx}",
                                (0.40 * scale, 0.04, 0.55 * scale), bevel_offset=0.02,
                                loc=(pane_x if on_wall == "back" else 0,
                                     0 if on_wall == "back" else pane_x,
                                     pane_z),
                                parent=v_e, mat_=pane_colors[pane_idx])
    # Top arch panel
    for c_idx in range(2):
        pane_x = (c_idx - 0.5) * 0.45 * scale
        pane = beveled_cube(f"{name}_top{c_idx}",
                            (0.40 * scale, 0.04, 0.40 * scale), bevel_offset=0.02,
                            loc=(pane_x if on_wall == "back" else 0,
                                 0 if on_wall == "back" else pane_x,
                                 1.5 * scale),
                            parent=v_e, mat_=M_VITRAIL_PURPLE if c_idx == 0 else M_VITRAIL_YELLOW)
    # Lead frame outline
    frame_w = 1.0 * scale
    frame_h = 3.5 * scale
    beveled_cube(f"{name}_frame_t", (frame_w + 0.1, 0.06, 0.10),
                 loc=(0 if on_wall == "back" else 0, 0, frame_h/2 + 0.25),
                 parent=v_e, mat_=M_VITRAIL_LEAD)
    beveled_cube(f"{name}_frame_b", (frame_w + 0.1, 0.06, 0.10),
                 loc=(0, 0, -frame_h/2),
                 parent=v_e, mat_=M_VITRAIL_LEAD)
    for s in (-1, 1):
        beveled_cube(f"{name}_frame_{s}", (0.06, 0.06, frame_h),
                     loc=(s * frame_w/2 if on_wall == "back" else 0,
                          0 if on_wall == "back" else s * frame_w/2,
                          0),
                     parent=v_e, mat_=M_VITRAIL_LEAD)
    # Rose pattern center (small circle)
    cyl(f"{name}_rose", r=0.20*scale, depth=0.06, segs=20,
        loc=(0, 0, 0), parent=v_e, mat_=M_VITRAIL_YELLOW).rotation_euler = (math.radians(90), 0, 0)
    v_e["_phase"] = random.uniform(0, math.pi*2)
    return v_e

vitraux = []
# Back wall vitraux (4)
for i in range(4):
    v = make_vitrail(f"vit_back{i}", ((i - 1.5) * 7, 13.7, 9.5), hall_e, scale=1.5, on_wall="back")
    vitraux.append(v)
# Side wall vitraux (3 each side)
for side_idx, side_x in enumerate((-15.7, 15.7)):
    for i in range(3):
        v = make_vitrail(f"vit_side{side_idx}_{i}", (side_x, (i - 1) * 7, 9.5), hall_e,
                         scale=1.3, on_wall=("left" if side_idx == 0 else "right"))
        vitraux.append(v)

# ============ THRONE on raised dais ============
throne_e = empty("throne", loc=(0, 11, 0))

# Dais 3-step
for i in range(3):
    beveled_cube(f"dais{i}", (8 - i*0.8, 5 - i*0.6, 0.30), bevel_offset=0.05,
                 loc=(0, 0, 0.15 + i*0.30), parent=throne_e, mat_=M_STONE)
# Top dais platform
beveled_cube("dais_top", (6, 4, 0.20), loc=(0, 0, 1.20), parent=throne_e, mat_=M_CARPET_RED)

# Throne main body (large ornate chair)
throne_main_e = empty("throne_main_e", (0, 0.5, 1.30), parent=throne_e)
# Seat
beveled_cube("throne_seat", (1.8, 1.4, 0.35), bevel_offset=0.08,
             loc=(0, 0, 0.40), parent=throne_main_e, mat_=M_WOOD_RICH)
# Seat cushion velvet purple
beveled_cube("throne_cushion", (1.65, 1.25, 0.20), loc=(0, 0, 0.65),
             parent=throne_main_e, mat_=M_VELVET_PURPLE)
# Back tall (signature throne)
beveled_cube("throne_back", (1.8, 0.25, 3.5), bevel_offset=0.08,
             loc=(0, 0.65, 2.20), parent=throne_main_e, mat_=M_WOOD_RICH)
# Back cushion
beveled_cube("throne_back_cushion", (1.6, 0.15, 3.0), loc=(0, 0.55, 2.30),
             parent=throne_main_e, mat_=M_VELVET_PURPLE)
# 2 armrests (lion shaped)
for side in (-1, 1):
    arm_e = empty(f"arm_e_{side}", (side*0.85, -0.30, 1.0), parent=throne_main_e)
    # Body lion (signature throne)
    beveled_cube(f"throne_arm_{side}", (0.30, 1.5, 0.30), bevel_offset=0.05,
                 loc=(0, 0, 0), parent=arm_e, mat_=M_GOLD)
    # Lion head front
    smooth_sphere(f"throne_lion_h_{side}", r=0.25, loc=(0, -0.65, 0.10),
                  parent=arm_e, mat_=M_GOLD_BRIGHT)
    # Lion mane
    for i in range(8):
        a = (i / 8.0) * math.pi * 2
        smooth_sphere(f"throne_mane_{side}_{i}", r=0.10,
                      loc=(0.18*math.cos(a), -0.65, 0.10 + 0.18*math.sin(a)),
                      parent=arm_e, mat_=M_GOLD_BRIGHT)
    # 2 eyes ruby
    for ie in (-1, 1):
        smooth_sphere(f"throne_eye_{side}_{ie}", r=0.04,
                      loc=(ie*0.10, -0.80, 0.10), parent=arm_e, mat_=M_RUBY)

# Throne top finial - cross with gems (signature crown/coronation)
finial_e = empty("finial_e", (0, 0, 4.30), parent=throne_main_e)
# Cross
beveled_cube("finial_cross_v", (0.15, 0.05, 0.85), loc=(0, 0, 0.40),
             parent=finial_e, mat_=M_GOLD_BRIGHT)
beveled_cube("finial_cross_h", (0.55, 0.05, 0.15), loc=(0, 0, 0.55),
             parent=finial_e, mat_=M_GOLD_BRIGHT)
# Center gem
smooth_sphere("finial_gem", r=0.10, loc=(0, 0, 0.55),
              parent=finial_e, mat_=M_RUBY)
# 4 corner gems (sapphire/emerald/ruby/pearl)
gems_pos = [(0, 0, 0.0), (0, 0, 0.85), (-0.30, 0, 0.55), (0.30, 0, 0.55)]
gems_mat = [M_SAPPHIRE, M_EMERALD, M_PEARL, M_PEARL]
for gi, (gx, gy, gz) in enumerate(gems_pos):
    smooth_sphere(f"finial_g{gi}", r=0.05, loc=(gx, gy, gz),
                  parent=finial_e, mat_=gems_mat[gi])

# Throne decorative carvings (4 gold patterns on back)
for i in range(4):
    beveled_cube(f"throne_pat{i}", (1.3, 0.04, 0.15), loc=(0, 0.50, 1.4 + i*0.6),
                 parent=throne_main_e, mat_=M_GOLD)

# Throne legs (4 elaborate)
for x_idx, x in enumerate((-1, 1)):
    for y_idx, y in enumerate((-1, 1)):
        cyl(f"throne_leg_{x_idx}_{y_idx}", r=0.10, depth=0.40, segs=12,
            loc=(x*0.78, y*0.60, 0.0), parent=throne_main_e, mat_=M_GOLD)
        smooth_sphere(f"throne_leg_orb_{x_idx}_{y_idx}", r=0.12,
                      loc=(x*0.78, y*0.60, 0.30), parent=throne_main_e, mat_=M_GOLD)

# Secondary queen throne (smaller, beside)
queen_throne_e = empty("queen_throne", (2.5, 0.5, 1.30), parent=throne_e)
beveled_cube("qt_seat", (1.4, 1.1, 0.30), bevel_offset=0.06,
             loc=(0, 0, 0.35), parent=queen_throne_e, mat_=M_WOOD_RICH)
beveled_cube("qt_cushion", (1.3, 1.0, 0.15), loc=(0, 0, 0.55),
             parent=queen_throne_e, mat_=M_VELVET_PURPLE)
beveled_cube("qt_back", (1.4, 0.20, 2.5), bevel_offset=0.06,
             loc=(0, 0.55, 1.80), parent=queen_throne_e, mat_=M_WOOD_RICH)
beveled_cube("qt_back_cushion", (1.25, 0.12, 2.2), loc=(0, 0.45, 1.85),
             parent=queen_throne_e, mat_=M_VELVET_PURPLE)
# Finial small
smooth_sphere("qt_finial", r=0.15, loc=(0, 0, 3.20), parent=queen_throne_e, mat_=M_GOLD_BRIGHT)
# Cross small
beveled_cube("qt_cross_v", (0.06, 0.04, 0.30), loc=(0, 0, 3.55),
             parent=queen_throne_e, mat_=M_GOLD_BRIGHT)
beveled_cube("qt_cross_h", (0.20, 0.04, 0.06), loc=(0, 0, 3.55),
             parent=queen_throne_e, mat_=M_GOLD_BRIGHT)

# ============ KING (assis sur trône, couronné) ============
king_base = empty("king", loc=(0, 11.20, 1.30))
king_base.rotation_euler = (0, 0, 0)
# Lap (legs covered by robe long)
beveled_cube("king_lap", (0.70, 0.55, 0.40), bevel_offset=0.05,
             loc=(0, -0.35, 0.60), parent=king_base, mat_=M_ROYAL_RED)
# Cone robe down to feet (long royal robe)
smooth_cone("king_robe", r1=0.45, r2=0.30, depth=0.75, segs=18,
            loc=(0, 0, 0.30), parent=king_base, mat_=M_ROYAL_RED)
# Torso (sitting up)
beveled_cube("king_torso", (0.55, 0.32, 0.85), bevel_offset=0.05,
             loc=(0, 0, 1.20), parent=king_base, mat_=M_ROYAL_RED)
# Ermine collar (signature king)
cyl("king_collar", r=0.40, depth=0.18, segs=20,
    loc=(0, -0.10, 1.65), parent=king_base, mat_=M_ERMINE)
# Ermine spots (5 black)
for i in range(5):
    a = (i / 5.0) * math.pi - math.pi/2
    smooth_sphere(f"king_collar_spot{i}", r=0.025,
                  loc=(0.35*math.sin(a), -0.30, 1.65), parent=king_base, mat_=M_ERMINE_DOT)
# Royal chain pendant (signature)
cyl("king_chain", r=0.08, depth=0.04, segs=14,
    loc=(0, -0.20, 1.40), parent=king_base, mat_=M_GOLD_BRIGHT).rotation_euler = (math.radians(90), 0, 0)
# 3 chain links
for i in range(3):
    smooth_sphere(f"king_chain_l{i}", r=0.025,
                  loc=((i-1)*0.08, -0.22, 1.45), parent=king_base, mat_=M_GOLD_BRIGHT)

# Neck
cyl("king_neck", r=0.10, depth=0.18, segs=12,
    loc=(0, 0, 1.80), parent=king_base, mat_=M_SKIN)
# Head
king_head_e = empty("king_head_e", (0, 0, 2.00), parent=king_base)
smooth_sphere("king_head", r=0.22, segs=22, rings=14, loc=(0, 0, 0),
              parent=king_head_e, mat_=M_SKIN)
# Eyes
for side in (-1, 1):
    smooth_sphere(f"king_eye_{side}", r=0.03,
                  loc=(side*0.07, -0.18, 0.03), parent=king_head_e,
                  mat_=mat(f"kew{side}", (0.95,0.92,0.85,1), 0, 0.4))
    smooth_sphere(f"king_pup_{side}", r=0.018,
                  loc=(side*0.07, -0.20, 0.03), parent=king_head_e, mat_=M_SAPPHIRE)
# Nose
smooth_cone("king_nose", r1=0.04, r2=0.02, depth=0.10, segs=8,
            loc=(0, -0.20, -0.04), parent=king_head_e, mat_=M_SKIN).rotation_euler = (math.radians(60), 0, 0)
# Mouth (slight smile)
beveled_cube("king_mouth", (0.07, 0.02, 0.02), loc=(0, -0.20, -0.12),
             parent=king_head_e, mat_=mat("km", (0.55, 0.20, 0.20, 1), 0, 0.5))
# Beard (royal trimmed)
smooth_sphere("king_beard", r=0.14, loc=(0, -0.08, -0.15),
              parent=king_head_e, mat_=M_BEARD_BROWN, scale=(1.4, 0.7, 1.0))
# Hair brown
smooth_sphere("king_hair", r=0.24, loc=(0, 0.05, 0.05),
              parent=king_head_e, mat_=M_HAIR_BROWN, scale=(1.05, 1.0, 0.85))

# CROWN GOLD (signature royal crown!)
crown_e = empty("crown_e", (0, 0, 0.28), parent=king_head_e)
# Base ring
cyl("crown_base", r=0.24, depth=0.12, segs=24,
    loc=(0, 0, 0), parent=crown_e, mat_=M_GOLD_BRIGHT)
# 5 points (fleur-de-lis style)
for i in range(5):
    a = (i / 5.0) * math.pi * 2 + math.pi/2
    px = 0.20 * math.cos(a)
    py = 0.20 * math.sin(a)
    # Spike
    spike = smooth_cone(f"crown_spike{i}", r1=0.04, r2=0.005, depth=0.30, segs=8,
                       loc=(px, py, 0.20), parent=crown_e, mat_=M_GOLD_BRIGHT)
    # Tip ball gem
    gem_col = [M_RUBY, M_SAPPHIRE, M_EMERALD, M_PEARL, M_RUBY][i % 5]
    smooth_sphere(f"crown_gem{i}", r=0.05, loc=(px, py, 0.38),
                  parent=crown_e, mat_=gem_col)
# 4 gems on base ring
for i in range(4):
    a = (i / 4.0) * math.pi * 2
    gem_col = [M_RUBY, M_SAPPHIRE, M_EMERALD, M_RUBY][i]
    smooth_sphere(f"crown_base_gem{i}", r=0.04, loc=(0.25*math.cos(a), 0.25*math.sin(a), 0),
                  parent=crown_e, mat_=gem_col)
# Cross on top (signature)
beveled_cube("crown_cross_v", (0.04, 0.02, 0.15), loc=(0, 0, 0.45),
             parent=crown_e, mat_=M_GOLD_BRIGHT)
beveled_cube("crown_cross_h", (0.12, 0.02, 0.04), loc=(0, 0, 0.48),
             parent=crown_e, mat_=M_GOLD_BRIGHT)

# 2 arms (one holds sceptre, one holds orb)
# Right arm holds SCEPTRE
king_r_sh = empty("king_r_sh", (0.32, 0, 1.65), parent=king_base)
king_r_sh.rotation_euler = (math.radians(-50), 0, math.radians(-10))
cyl("king_r_up", r=0.08, depth=0.40, segs=10,
    loc=(0, 0, -0.20), parent=king_r_sh, mat_=M_ROYAL_RED)
king_r_el = empty("king_r_el", (0, 0, -0.42), parent=king_r_sh)
king_r_el.rotation_euler = (math.radians(40), 0, 0)
cyl("king_r_fa", r=0.07, depth=0.38, segs=10,
    loc=(0, 0, -0.20), parent=king_r_el, mat_=M_SKIN)
king_r_hand = empty("king_r_hand", (0, 0, -0.42), parent=king_r_el)
smooth_sphere("king_r_h_g", r=0.08, loc=(0,0,0), parent=king_r_hand, mat_=M_SKIN)

# SCEPTRE (in right hand)
sceptre_e = empty("sceptre_e", (0, 0, -0.10), parent=king_r_hand)
cyl("sceptre_shaft", r=0.04, depth=1.2, segs=12,
    loc=(0, 0, 0.60), parent=sceptre_e, mat_=M_GOLD_BRIGHT)
# Decorative bands
for i in range(3):
    cyl(f"sceptre_band{i}", r=0.05, depth=0.06, segs=14,
        loc=(0, 0, 0.30 + i*0.30), parent=sceptre_e, mat_=M_GOLD)
# Top fleur-de-lis (signature royal sceptre)
smooth_sphere("sceptre_orb_top", r=0.08, loc=(0, 0, 1.22),
              parent=sceptre_e, mat_=M_GOLD_BRIGHT)
# 3 petals fleur
for i in range(3):
    a = (i / 3.0) * math.pi * 2
    smooth_cone(f"sceptre_petal{i}", r1=0.04, r2=0.005, depth=0.15, segs=8,
                loc=(0.05*math.cos(a), 0.05*math.sin(a), 1.32), parent=sceptre_e,
                mat_=M_GOLD_BRIGHT).rotation_euler = (math.radians(-30*math.cos(a)),
                                                       math.radians(-30*math.sin(a)), 0)
# Gem at base of petals
smooth_sphere("sceptre_gem", r=0.04, loc=(0, 0, 1.45),
              parent=sceptre_e, mat_=M_RUBY)

# Left arm holds GLOBUS CRUCIGER (orb with cross)
king_l_sh = empty("king_l_sh", (-0.32, 0, 1.65), parent=king_base)
king_l_sh.rotation_euler = (math.radians(-60), 0, math.radians(15))
cyl("king_l_up", r=0.08, depth=0.40, segs=10,
    loc=(0, 0, -0.20), parent=king_l_sh, mat_=M_ROYAL_RED)
king_l_el = empty("king_l_el", (0, 0, -0.42), parent=king_l_sh)
king_l_el.rotation_euler = (math.radians(50), 0, 0)
cyl("king_l_fa", r=0.07, depth=0.38, segs=10,
    loc=(0, 0, -0.20), parent=king_l_el, mat_=M_SKIN)
king_l_hand = empty("king_l_hand", (0, 0, -0.42), parent=king_l_el)
smooth_sphere("king_l_h_g", r=0.08, loc=(0,0,0), parent=king_l_hand, mat_=M_SKIN)

# GLOBUS (orb)
globus_e = empty("globus_e", (0, 0, -0.20), parent=king_l_hand)
smooth_sphere("globus_orb", r=0.18, segs=22, rings=14, loc=(0, 0, 0),
              parent=globus_e, mat_=M_GOLD_BRIGHT)
# Cross on top
beveled_cube("globus_cross_v", (0.04, 0.02, 0.30), loc=(0, 0, 0.30),
             parent=globus_e, mat_=M_GOLD_BRIGHT)
beveled_cube("globus_cross_h", (0.20, 0.02, 0.04), loc=(0, 0, 0.35),
             parent=globus_e, mat_=M_GOLD_BRIGHT)
# Equator band
cyl("globus_eq", r=0.19, depth=0.04, segs=20,
    loc=(0, 0, 0), parent=globus_e, mat_=M_RUBY).rotation_euler = (math.radians(90), 0, 0)

# ============ QUEEN (assise sur trône reine) ============
queen_base = empty("queen", loc=(2.5, 11.20, 1.30))
# Dress long
smooth_cone("queen_dress", r1=0.45, r2=0.35, depth=0.85, segs=18,
            loc=(0, 0, 0.40), parent=queen_base, mat_=M_DRESS_GOLD)
# Torso
beveled_cube("queen_torso", (0.45, 0.28, 0.80), bevel_offset=0.05,
             loc=(0, 0, 1.20), parent=queen_base, mat_=M_DRESS_GOLD)
# Bodice details (gold)
beveled_cube("queen_bodice", (0.40, 0.10, 0.55), loc=(0, -0.18, 1.30),
             parent=queen_base, mat_=M_GOLD_BRIGHT)
# Neck
cyl("queen_neck", r=0.08, depth=0.15, segs=10,
    loc=(0, 0, 1.75), parent=queen_base, mat_=M_SKIN)
# Head
queen_head_e = empty("queen_head_e", (0, 0, 1.92), parent=queen_base)
smooth_sphere("queen_head", r=0.18, segs=20, rings=14, loc=(0, 0, 0),
              parent=queen_head_e, mat_=M_SKIN)
# Eyes
for side in (-1, 1):
    smooth_sphere(f"queen_eye_{side}", r=0.025,
                  loc=(side*0.06, -0.15, 0.03), parent=queen_head_e,
                  mat_=mat(f"qew{side}", (0.95,0.92,0.85,1), 0, 0.4))
# Long hair blonde flowing
smooth_sphere("queen_hair", r=0.21, loc=(0, 0.04, 0.05),
              parent=queen_head_e, mat_=M_HAIR_BLOND, scale=(1.05, 1.0, 0.95))
# Long hair back
for i in range(4):
    strand = beveled_cube(f"queen_hair_b{i}", (0.08, 0.10, 0.45),
                          loc=((i-1.5)*0.08, 0.20, -0.10 - i*0.05),
                          parent=queen_head_e, mat_=M_HAIR_BLOND)
    strand.rotation_euler = (math.radians(10), 0, 0)
# TIARA (signature queen)
tiara_e = empty("tiara_e", (0, 0, 0.22), parent=queen_head_e)
cyl("tiara_base", r=0.20, depth=0.06, segs=24,
    loc=(0, 0, 0), parent=tiara_e, mat_=M_SILVER)
# 7 points
for i in range(7):
    a = (i / 7.0) * math.pi - math.pi/2
    px = 0.18 * math.cos(a)
    py = 0.18 * math.sin(a)
    smooth_cone(f"tiara_p{i}", r1=0.03, r2=0.005, depth=0.18, segs=8,
                loc=(px, py - 0.05, 0.10), parent=tiara_e, mat_=M_SILVER)
    # Gem
    smooth_sphere(f"tiara_gem{i}", r=0.025, loc=(px, py - 0.05, 0.22),
                  parent=tiara_e, mat_=M_PEARL)
# Center large gem
smooth_sphere("tiara_center", r=0.05, loc=(0, -0.18, 0.06),
              parent=tiara_e, mat_=M_SAPPHIRE)

# 2 arms (folded modestly)
for side_idx, side in enumerate((-1, 1)):
    sh = empty(f"queen_sh{side_idx}", (side*0.25, 0, 1.60), parent=queen_base)
    sh.rotation_euler = (math.radians(-40), 0, math.radians(side*-10))
    cyl(f"queen_up{side_idx}", r=0.06, depth=0.35, segs=10,
        loc=(0, 0, -0.18), parent=sh, mat_=M_DRESS_GOLD)
    el = empty(f"queen_el{side_idx}", (0, 0, -0.37), parent=sh)
    el.rotation_euler = (math.radians(60), 0, 0)
    cyl(f"queen_fa{side_idx}", r=0.055, depth=0.35, segs=10,
        loc=(0, 0, -0.18), parent=el, mat_=M_SKIN)
    # Hand
    smooth_sphere(f"queen_hand{side_idx}", r=0.06, loc=(0, 0, -0.38),
                  parent=el, mat_=M_SKIN)

# ============ ARCHBISHOP (placing crown) ============
arch_base = empty("archbishop", loc=(0, 9.5, 1.5))
arch_base.rotation_euler = (0, 0, math.radians(180))  # facing king
# Legs
for side_idx, side in enumerate((-1, 1)):
    cyl(f"arch_leg{side_idx}", r=0.12, depth=0.85, segs=10,
        loc=(side*0.14, 0, 0.42), parent=arch_base, mat_=M_BISHOP_WHITE)
# Long robe (cope)
smooth_cone("arch_robe", r1=0.55, r2=0.40, depth=1.2, segs=18,
            loc=(0, 0, 1.0), parent=arch_base, mat_=M_BISHOP_WHITE)
# Gold trim on robe (2 vertical bands)
for side in (-1, 1):
    beveled_cube(f"arch_trim_{side}", (0.06, 0.06, 1.20),
                 loc=(side*0.15, -0.45, 1.0), parent=arch_base, mat_=M_BISHOP_GOLD)
# Torso
beveled_cube("arch_torso", (0.45, 0.30, 0.85), bevel_offset=0.05,
             loc=(0, 0, 1.70), parent=arch_base, mat_=M_BISHOP_WHITE)
# Gold cross pendant
beveled_cube("arch_cross_v", (0.06, 0.04, 0.30), loc=(0, -0.20, 1.80),
             parent=arch_base, mat_=M_GOLD_BRIGHT)
beveled_cube("arch_cross_h", (0.20, 0.04, 0.06), loc=(0, -0.20, 1.85),
             parent=arch_base, mat_=M_GOLD_BRIGHT)
# Stole (gold strip over shoulders)
for side in (-1, 1):
    beveled_cube(f"arch_stole_{side}", (0.18, 0.08, 1.2),
                 loc=(side*0.15, -0.20, 1.55), parent=arch_base, mat_=M_BISHOP_GOLD)
# Head
arch_head_e = empty("arch_head_e", (0, 0, 2.30), parent=arch_base)
smooth_sphere("arch_head", r=0.20, segs=20, rings=14, loc=(0,0,0),
              parent=arch_head_e, mat_=M_SKIN)
# Eyes
for side in (-1, 1):
    smooth_sphere(f"arch_eye_{side}", r=0.025,
                  loc=(side*0.07, -0.16, 0.03), parent=arch_head_e,
                  mat_=mat(f"aew{side}", (0.95,0.92,0.85,1), 0, 0.4))
# White beard (signature old archbishop)
smooth_sphere("arch_beard", r=0.16, loc=(0, -0.08, -0.20),
              parent=arch_head_e, mat_=M_BEARD_WHITE, scale=(1.4, 0.6, 1.4))
# White hair (visible at sides)
smooth_sphere("arch_hair", r=0.22, loc=(0, 0.03, 0.05),
              parent=arch_head_e, mat_=M_HAIR_WHITE, scale=(1.05, 1.0, 0.7))
# MITRE (signature archbishop hat)
mitre_e = empty("mitre_e", (0, 0, 0.20), parent=arch_head_e)
# Base ring
cyl("mitre_base", r=0.22, depth=0.10, segs=20,
    loc=(0, 0, 0), parent=mitre_e, mat_=M_MITRE)
# 2 peak panels (signature mitre)
for side in (-1, 1):
    panel = beveled_cube(f"mitre_p_{side}", (0.04, 0.40, 0.55), bevel_offset=0.04,
                        loc=(0, side*0.10, 0.30), parent=mitre_e, mat_=M_MITRE)
    panel.rotation_euler = (math.radians(side*15), 0, 0)
# Gold cross on front
beveled_cube("mitre_cross_v", (0.04, 0.04, 0.20), loc=(0, -0.10, 0.20),
             parent=mitre_e, mat_=M_BISHOP_GOLD)
beveled_cube("mitre_cross_h", (0.15, 0.04, 0.04), loc=(0, -0.10, 0.23),
             parent=mitre_e, mat_=M_BISHOP_GOLD)
# 2 lappets (hanging strips back of mitre)
for side in (-1, 1):
    beveled_cube(f"mitre_lap_{side}", (0.04, 0.05, 0.30),
                 loc=(side*0.08, 0.18, -0.10), parent=mitre_e, mat_=M_MITRE)

# 2 ARMS - holding ANOTHER CROWN (placing on king, ritual moment)
# Both arms raised forward
arch_l_sh = empty("arch_l_sh", (-0.25, 0, 2.05), parent=arch_base)
arch_l_sh.rotation_euler = (math.radians(-100), 0, math.radians(15))
cyl("arch_l_up", r=0.08, depth=0.40, segs=10,
    loc=(0, 0, -0.20), parent=arch_l_sh, mat_=M_BISHOP_WHITE)
arch_l_el = empty("arch_l_el", (0, 0, -0.42), parent=arch_l_sh)
arch_l_el.rotation_euler = (math.radians(40), 0, 0)
cyl("arch_l_fa", r=0.07, depth=0.38, segs=10,
    loc=(0, 0, -0.20), parent=arch_l_el, mat_=M_SKIN)
arch_l_hand = empty("arch_l_hand", (0, 0, -0.42), parent=arch_l_el)
smooth_sphere("arch_l_h_g", r=0.07, loc=(0,0,0), parent=arch_l_hand, mat_=M_SKIN)

arch_r_sh = empty("arch_r_sh", (0.25, 0, 2.05), parent=arch_base)
arch_r_sh.rotation_euler = (math.radians(-100), 0, math.radians(-15))
cyl("arch_r_up", r=0.08, depth=0.40, segs=10,
    loc=(0, 0, -0.20), parent=arch_r_sh, mat_=M_BISHOP_WHITE)
arch_r_el = empty("arch_r_el", (0, 0, -0.42), parent=arch_r_sh)
arch_r_el.rotation_euler = (math.radians(40), 0, 0)
cyl("arch_r_fa", r=0.07, depth=0.38, segs=10,
    loc=(0, 0, -0.20), parent=arch_r_el, mat_=M_SKIN)
arch_r_hand = empty("arch_r_hand", (0, 0, -0.42), parent=arch_r_el)
smooth_sphere("arch_r_h_g", r=0.07, loc=(0,0,0), parent=arch_r_hand, mat_=M_SKIN)

# Crown floating between his hands (about to place on king)
floating_crown_e = empty("float_crown", (0, -0.75, 2.0), parent=arch_base)
cyl("float_crown_base", r=0.18, depth=0.10, segs=24,
    loc=(0, 0, 0), parent=floating_crown_e, mat_=M_GOLD_BRIGHT)
for i in range(5):
    a = (i / 5.0) * math.pi * 2 + math.pi/2
    px = 0.15 * math.cos(a); py = 0.15 * math.sin(a)
    smooth_cone(f"fc_sp{i}", r1=0.03, r2=0.005, depth=0.22, segs=8,
                loc=(px, py, 0.16), parent=floating_crown_e, mat_=M_GOLD_BRIGHT)
    smooth_sphere(f"fc_g{i}", r=0.03, loc=(px, py, 0.30),
                  parent=floating_crown_e, mat_=[M_RUBY,M_SAPPHIRE,M_EMERALD,M_PEARL,M_RUBY][i])

# CROZIER (bishop's staff - leaning against him)
crozier_e = empty("crozier_e", (-0.5, -0.20, 0), parent=arch_base)
crozier_e.rotation_euler = (math.radians(-5), 0, 0)
cyl("croz_shaft", r=0.04, depth=2.8, segs=12,
    loc=(0, 0, 1.4), parent=crozier_e, mat_=M_CROZIER)
# Curled top (signature shepherd's crook)
crook_top_e = empty("crook_top_e", (0, 0, 2.85), parent=crozier_e)
for i in range(5):
    a = (i / 4.0) * math.pi
    cx = 0.15 * (1 - math.cos(a))
    cz = 0.15 * math.sin(a)
    smooth_sphere(f"croz_top{i}", r=0.05,
                  loc=(cx, 0, cz), parent=crook_top_e, mat_=M_CROZIER)
# Bands
for i in range(3):
    cyl(f"croz_band{i}", r=0.05, depth=0.05, segs=14,
        loc=(0, 0, 1.0 + i*0.5), parent=crozier_e, mat_=M_GOLD_BRIGHT)

# ============ 15 NOBLES (courtisans) on sides of carpet ============
def make_noble(name, loc, robe_mat, hair_mat, skin_mat=M_SKIN, has_beard=False,
               beard_mat=M_BEARD_BROWN, has_hat=False, hat_color=None,
               action="applaud", facing=0, scale=1.0):
    base = empty(name, loc)
    base.rotation_euler = (0, 0, facing)
    # Legs (under robe)
    for side_idx, side in enumerate((-1, 1)):
        cyl(f"{name}_leg{side_idx}", r=0.11*scale, depth=0.85*scale, segs=10,
            loc=(side*0.14*scale, 0, 0.42*scale), parent=base, mat_=M_TUNIC_BROWN)
        # Shoes
        beveled_cube(f"{name}_shoe{side_idx}", (0.18*scale, 0.26*scale, 0.06*scale),
                     loc=(side*0.14*scale, 0.05*scale, 0.04*scale), parent=base, mat_=M_TUNIC_BROWN)
    # Long robe / tunic
    smooth_cone(f"{name}_robe", r1=0.45*scale, r2=0.30*scale, depth=0.65*scale, segs=14,
                loc=(0, 0, 1.0*scale), parent=base, mat_=robe_mat)
    # Torso
    beveled_cube(f"{name}_torso", (0.50*scale, 0.32*scale, 0.85*scale), bevel_offset=0.05,
                 loc=(0, 0, 1.65*scale), parent=base, mat_=robe_mat)
    # Belt
    beveled_cube(f"{name}_belt", (0.55*scale, 0.36*scale, 0.06*scale),
                 loc=(0, 0, 1.30*scale), parent=base, mat_=M_BRONZE)
    # Optional gold chain pendant
    if random.random() < 0.5:
        beveled_cube(f"{name}_pendant", (0.06*scale, 0.04*scale, 0.20*scale),
                     loc=(0, -0.18*scale, 1.65*scale), parent=base, mat_=M_GOLD_BRIGHT)
    # Head
    head_e = empty(f"{name}_head_e", (0, 0, 2.10*scale), parent=base)
    smooth_sphere(f"{name}_head", r=0.18*scale, segs=20, rings=14, loc=(0,0,0),
                  parent=head_e, mat_=skin_mat)
    # Eyes
    for side in (-1, 1):
        smooth_sphere(f"{name}_eye_{side}", r=0.022*scale,
                      loc=(side*0.06*scale, -0.15*scale, 0.03*scale), parent=head_e,
                      mat_=mat(f"{name}_ew{side}", (0.95,0.92,0.85,1), 0, 0.4))
    # Hair
    smooth_sphere(f"{name}_hair", r=0.20*scale, loc=(0, 0.04*scale, 0.05*scale),
                  parent=head_e, mat_=hair_mat, scale=(1.05, 1.0, 0.75))
    # Beard
    if has_beard:
        smooth_sphere(f"{name}_beard", r=0.12*scale, loc=(0, -0.08*scale, -0.16*scale),
                      parent=head_e, mat_=beard_mat, scale=(1.3, 0.6, 1.2))
    # Optional hat
    if has_hat and hat_color:
        # Floppy beret-like
        smooth_sphere(f"{name}_hat", r=0.22*scale, loc=(0.05*scale, 0.03*scale, 0.15*scale),
                      parent=head_e, mat_=hat_color, scale=(1, 1, 0.5))
        # Feather
        if random.random() < 0.5:
            beveled_cube(f"{name}_feather", (0.04*scale, 0.06*scale, 0.35*scale),
                         loc=(-0.15*scale, 0.05*scale, 0.18*scale), parent=head_e, mat_=M_ERMINE)
    # 2 ARMS (action)
    arms_pose = {
        "applaud": [(math.radians(-130), -20), (math.radians(-130), 20)],
        "bow": [(math.radians(-50), -15), (math.radians(-50), 15)],
        "rest": [(math.radians(-15), 0), (math.radians(-15), 0)],
        "praying": [(math.radians(-100), -10), (math.radians(-100), 10)],
    }
    pose = arms_pose.get(action, arms_pose["applaud"])
    for side_idx, side in enumerate((-1, 1)):
        sh = empty(f"{name}_sh{side_idx}", (side*0.30*scale, 0, 2.0*scale), parent=base)
        rx, rz = pose[side_idx]
        sh.rotation_euler = (rx, 0, math.radians(side*-15 + rz))
        cyl(f"{name}_up{side_idx}", r=0.07*scale, depth=0.38*scale, segs=10,
            loc=(0, 0, -0.20*scale), parent=sh, mat_=robe_mat)
        el = empty(f"{name}_el{side_idx}", (0, 0, -0.40*scale), parent=sh)
        el.rotation_euler = (math.radians(30 if side==-1 else 40), 0, 0)
        cyl(f"{name}_fa{side_idx}", r=0.06*scale, depth=0.36*scale, segs=10,
            loc=(0, 0, -0.18*scale), parent=el, mat_=skin_mat)
        smooth_sphere(f"{name}_hand{side_idx}", r=0.06*scale,
                      loc=(0, 0, -0.40*scale), parent=el, mat_=skin_mat)
    return {"root": base, "head_e": head_e}

# 15 nobles placed on sides of carpet (lines)
nobles = []
noble_colors_robes = [M_VELVET_RED, M_VELVET_BLUE, M_VELVET_GREEN, M_VELVET_PURPLE, M_ROYAL_GREEN, M_ROYAL_BLUE]
noble_hairs = [M_HAIR_BROWN, M_HAIR_BLOND, M_HAIR_BLACK, M_HAIR_GREY]
for i in range(15):
    side = -1 if i < 8 else 1
    idx = i if i < 8 else i - 8
    nx = side * (3.5 + (idx % 2) * 0.8)
    ny = -7 + idx * 1.6
    facing = math.radians(side * -90)
    actions = ["applaud", "bow", "rest", "applaud", "applaud"]
    nob = make_noble(f"noble{i}", (nx, ny, 0),
                     random.choice(noble_colors_robes),
                     random.choice(noble_hairs),
                     M_SKIN if random.random() < 0.7 else M_SKIN_DARK,
                     has_beard=(random.random() < 0.5),
                     beard_mat=random.choice([M_BEARD_BROWN, M_BEARD_GREY]),
                     has_hat=(random.random() < 0.6),
                     hat_color=random.choice([M_VELVET_RED, M_VELVET_BLUE, M_VELVET_PURPLE]),
                     action=random.choice(actions),
                     facing=facing)
    nob["_action"] = nob.get("_action", random.choice(actions))
    nobles.append(nob)

# ============ 8 LADIES (elegant) ============
def make_lady(name, loc, dress_mat, hair_mat, skin_mat=M_SKIN,
              action="applaud", facing=0):
    base = empty(name, loc)
    base.rotation_euler = (0, 0, facing)
    # Long dress (flared cone full length)
    smooth_cone(f"{name}_dress", r1=0.50, r2=0.20, depth=1.45, segs=18,
                loc=(0, 0, 0.72), parent=base, mat_=dress_mat)
    # Bodice/torso narrow
    beveled_cube(f"{name}_bodice", (0.42, 0.25, 0.65), bevel_offset=0.05,
                 loc=(0, 0, 1.65), parent=base, mat_=dress_mat)
    # Decorative neckline gold
    cyl(f"{name}_neckline", r=0.22, depth=0.05, segs=18,
        loc=(0, -0.10, 1.90), parent=base, mat_=M_GOLD).rotation_euler = (math.radians(85), 0, 0)
    # Necklace
    for i in range(3):
        smooth_sphere(f"{name}_pearl{i}", r=0.03, loc=((i-1)*0.04, -0.15, 1.85),
                      parent=base, mat_=M_PEARL)
    # Head
    head_e = empty(f"{name}_head_e", (0, 0, 2.05), parent=base)
    smooth_sphere(f"{name}_head", r=0.17, segs=20, rings=14, loc=(0,0,0),
                  parent=head_e, mat_=skin_mat)
    # Eyes
    for side in (-1, 1):
        smooth_sphere(f"{name}_eye_{side}", r=0.022,
                      loc=(side*0.06, -0.14, 0.03), parent=head_e,
                      mat_=mat(f"{name}_ew{side}", (0.95,0.92,0.85,1), 0, 0.4))
    # Long elegant hair (braid or flowing)
    smooth_sphere(f"{name}_hair", r=0.19, loc=(0, 0.04, 0.05),
                  parent=head_e, mat_=hair_mat, scale=(1.05, 1.0, 0.85))
    # Long hair back (3 strands)
    for i in range(3):
        beveled_cube(f"{name}_hair_b{i}", (0.08, 0.10, 0.50),
                     loc=((i-1)*0.06, 0.18, -0.10), parent=head_e, mat_=hair_mat)
    # Decorative head piece (hennin/circlet)
    cyl(f"{name}_circlet", r=0.19, depth=0.04, segs=18,
        loc=(0, 0, 0.16), parent=head_e, mat_=M_GOLD)
    smooth_sphere(f"{name}_circ_gem", r=0.03, loc=(0, -0.17, 0.16),
                  parent=head_e, mat_=M_SAPPHIRE)
    # 2 ARMS folded
    arms_pose = {
        "applaud": [(math.radians(-130), -20), (math.radians(-130), 20)],
        "rest": [(math.radians(-30), 0), (math.radians(-30), 0)],
        "wave": [(math.radians(-150), -10), (math.radians(-30), 10)],
    }
    pose = arms_pose.get(action, arms_pose["applaud"])
    for side_idx, side in enumerate((-1, 1)):
        sh = empty(f"{name}_sh{side_idx}", (side*0.25, 0, 1.95), parent=base)
        rx, rz = pose[side_idx]
        sh.rotation_euler = (rx, 0, math.radians(side*-15 + rz))
        cyl(f"{name}_up{side_idx}", r=0.06, depth=0.36, segs=10,
            loc=(0, 0, -0.18), parent=sh, mat_=dress_mat)
        el = empty(f"{name}_el{side_idx}", (0, 0, -0.38), parent=sh)
        el.rotation_euler = (math.radians(40), 0, 0)
        cyl(f"{name}_fa{side_idx}", r=0.055, depth=0.34, segs=10,
            loc=(0, 0, -0.17), parent=el, mat_=skin_mat)
        smooth_sphere(f"{name}_hand{side_idx}", r=0.055,
                      loc=(0, 0, -0.38), parent=el, mat_=skin_mat)
    return {"root": base, "head_e": head_e}

ladies = []
lady_dresses = [M_DRESS_PINK, M_DRESS_GOLD, M_DRESS_TEAL, M_DRESS_LAVENDER]
for i in range(8):
    side = -1 if i < 4 else 1
    idx = i if i < 4 else i - 4
    lx = side * (5.0 + (idx % 2) * 0.6)
    ly = -3 + idx * 2.2
    facing = math.radians(side * -90)
    l = make_lady(f"lady{i}", (lx, ly, 0),
                  random.choice(lady_dresses),
                  random.choice([M_HAIR_BLOND, M_HAIR_BROWN, M_HAIR_BLACK]),
                  M_SKIN if random.random() < 0.7 else M_SKIN_DARK,
                  action=random.choice(["applaud", "wave", "rest"]),
                  facing=facing)
    ladies.append(l)

# ============ 6 GUARDS (plate armor) ============
def make_guard(name, loc, facing=0):
    base = empty(name, loc)
    base.rotation_euler = (0, 0, facing)
    # Legs (plate)
    for side_idx, side in enumerate((-1, 1)):
        cyl(f"{name}_leg{side_idx}", r=0.13, depth=0.85, segs=12,
            loc=(side*0.14, 0, 0.42), parent=base, mat_=M_ARMOR_STEEL)
        beveled_cube(f"{name}_boot{side_idx}", (0.20, 0.30, 0.15),
                     loc=(side*0.14, 0.05, 0.08), parent=base, mat_=M_ARMOR_STEEL)
        # Knee plate
        smooth_sphere(f"{name}_knee_{side_idx}", r=0.16,
                      loc=(side*0.14, 0, 0.85), parent=base, mat_=M_ARMOR_STEEL)
    # Torso cuirass
    beveled_cube(f"{name}_torso", (0.65, 0.40, 0.95), bevel_offset=0.08,
                 loc=(0, 0, 1.40), parent=base, mat_=M_ARMOR_STEEL)
    # Chest plate gold accent
    beveled_cube(f"{name}_chest", (0.50, 0.10, 0.50), bevel_offset=0.04,
                 loc=(0, -0.22, 1.55), parent=base, mat_=M_ARMOR_GOLD)
    # Tabard (over armor) - heraldic colors
    beveled_cube(f"{name}_tabard", (0.55, 0.06, 0.85),
                 loc=(0, -0.24, 1.40), parent=base, mat_=M_ROYAL_RED)
    # Royal insignia on tabard (gold cross or fleur)
    beveled_cube(f"{name}_insig_v", (0.06, 0.05, 0.25), loc=(0, -0.25, 1.45),
                 parent=base, mat_=M_GOLD_BRIGHT)
    beveled_cube(f"{name}_insig_h", (0.20, 0.05, 0.06), loc=(0, -0.25, 1.48),
                 parent=base, mat_=M_GOLD_BRIGHT)
    # 2 pauldrons (shoulder armor)
    for side in (-1, 1):
        paul = beveled_cube(f"{name}_paul_{side}", (0.30, 0.32, 0.30), bevel_offset=0.05,
                           loc=(side*0.42, 0, 1.85), parent=base, mat_=M_ARMOR_STEEL)
    # Head HELMET (great helm or bascinet)
    head_e = empty(f"{name}_head_e", (0, 0, 2.10), parent=base)
    # Helmet base
    smooth_sphere(f"{name}_helm", r=0.22, segs=20, rings=14, loc=(0, 0, 0),
                  parent=head_e, mat_=M_ARMOR_STEEL)
    # Visor slit
    beveled_cube(f"{name}_visor", (0.30, 0.05, 0.04), loc=(0, -0.18, 0.05),
                 parent=head_e, mat_=mat(f"{name}_vs", (0.05,0.05,0.05,1), 0, 0.5))
    # Nasal guard
    beveled_cube(f"{name}_nasal", (0.06, 0.04, 0.20), loc=(0, -0.20, -0.05),
                 parent=head_e, mat_=M_ARMOR_STEEL)
    # 2 ARMS (one holds polearm/halberd)
    # Left arm down with shield
    l_sh = empty(f"{name}_l_sh", (-0.32, 0, 1.95), parent=base)
    l_sh.rotation_euler = (math.radians(-15), 0, math.radians(15))
    cyl(f"{name}_l_up", r=0.10, depth=0.45, segs=12,
        loc=(0, 0, -0.22), parent=l_sh, mat_=M_ARMOR_STEEL)
    cyl(f"{name}_l_fa", r=0.09, depth=0.42, segs=12,
        loc=(0, 0, -0.65), parent=l_sh, mat_=M_ARMOR_STEEL)
    # SHIELD (heater shape)
    shield_e = empty(f"{name}_shield_e", (-0.30, -0.35, 1.20), parent=base)
    beveled_cube(f"{name}_shield_body", (0.50, 0.10, 0.65), bevel_offset=0.06,
                 loc=(0, 0, 0), parent=shield_e, mat_=M_ROYAL_RED)
    # Royal cross on shield
    beveled_cube(f"{name}_sh_cross_v", (0.05, 0.05, 0.45), loc=(0, -0.06, 0),
                 parent=shield_e, mat_=M_GOLD_BRIGHT)
    beveled_cube(f"{name}_sh_cross_h", (0.35, 0.05, 0.05), loc=(0, -0.06, 0.08),
                 parent=shield_e, mat_=M_GOLD_BRIGHT)
    # Right arm holds HALBERD/SPEAR
    r_sh = empty(f"{name}_r_sh", (0.32, 0, 1.95), parent=base)
    r_sh.rotation_euler = (math.radians(-20), 0, math.radians(-10))
    cyl(f"{name}_r_up", r=0.10, depth=0.45, segs=12,
        loc=(0, 0, -0.22), parent=r_sh, mat_=M_ARMOR_STEEL)
    cyl(f"{name}_r_fa", r=0.09, depth=0.42, segs=12,
        loc=(0, 0, -0.65), parent=r_sh, mat_=M_ARMOR_STEEL)
    # SPEAR/HALBERD
    spear_e = empty(f"{name}_spear_e", (0.45, -0.05, 1.40), parent=base)
    cyl(f"{name}_spear_pole", r=0.04, depth=3.5, segs=10,
        loc=(0, 0, 1.0), parent=spear_e, mat_=M_WOOD_RICH)
    # Spear tip (long blade)
    smooth_cone(f"{name}_spear_tip", r1=0.08, r2=0.005, depth=0.50, segs=10,
                loc=(0, 0, 3.0), parent=spear_e, mat_=M_ARMOR_GOLD)
    # Halberd axe blade
    beveled_cube(f"{name}_axe_blade", (0.04, 0.30, 0.25), bevel_offset=0.03,
                 loc=(0, 0.15, 2.75), parent=spear_e, mat_=M_ARMOR_GOLD)
    return {"root": base, "head_e": head_e}

guards = []
guard_positions = [(-7.5, 8, math.radians(0)),  # near throne left
                    (7.5, 8, math.radians(0)),
                    (-5, -10, math.radians(0)),  # entrance
                    (5, -10, math.radians(0)),
                    (-13, 0, math.radians(90)),  # walls
                    (13, 0, math.radians(-90))]
for i, (gx, gy, facing) in enumerate(guard_positions):
    g = make_guard(f"guard{i}", (gx, gy, 0), facing=facing)
    guards.append(g)

# ============ HOUND (royal hunting dog at king's feet) ============
hound_e = empty("hound", loc=(0, 10, 0))
hound_e.rotation_euler = (0, 0, math.radians(180))
# Body lying down
smooth_sphere("hound_body", r=0.35, segs=20, rings=14, loc=(0, 0, 0.40),
              parent=hound_e, mat_=M_HOUND, scale=(2.0, 0.85, 0.85))
# Head resting
head_e = empty("hound_head_e", (0.55, 0, 0.45), parent=hound_e)
smooth_sphere("hound_h", r=0.18, segs=20, rings=14, loc=(0, 0, 0),
              parent=head_e, mat_=M_HOUND, scale=(1.5, 0.95, 0.95))
# Long droopy ears
for side in (-1, 1):
    ear = beveled_cube(f"hound_ear_{side}", (0.06, 0.10, 0.25),
                       loc=(side*0.10, 0.06, 0.05), parent=head_e, mat_=M_HOUND)
    ear.rotation_euler = (math.radians(20), 0, math.radians(side*30))
# Snout long
smooth_sphere("hound_snout", r=0.12, loc=(0.18, 0, -0.05),
              parent=head_e, mat_=M_HAIR_BLACK)
# Eyes
for side in (-1, 1):
    smooth_sphere(f"hound_eye_{side}", r=0.04,
                  loc=(0.10, side*0.10, 0.05), parent=head_e, mat_=M_HOUND_EYE)
# 4 short legs folded
for x_idx, x in enumerate((-1, 1)):
    for y_idx, y in enumerate((-1, 1)):
        cyl(f"hound_leg{x_idx}{y_idx}", r=0.06, depth=0.25, segs=10,
            loc=(x*0.20, y*0.18, 0.15), parent=hound_e, mat_=M_HOUND)
# Tail
tail_e = empty("hound_tail_e", (-0.60, 0, 0.40), parent=hound_e)
cyl("hound_tail", r=0.05, depth=0.30, segs=10,
    loc=(0, 0, 0), parent=tail_e, mat_=M_HOUND).rotation_euler = (math.radians(-30), 0, 0)
# Royal collar (gold)
cyl("hound_collar", r=0.13, depth=0.05, segs=14,
    loc=(0.35, 0, 0.45), parent=hound_e, mat_=M_GOLD_BRIGHT).rotation_euler = (0, math.radians(90), 0)

# ============ 8 BANNERS HÉRALDIQUES (heraldic banners hanging from ceiling) ============
banner_positions = [(-12, -6), (-12, 0), (-12, 6), (12, -6), (12, 0), (12, 6), (-6, -11), (6, -11)]
banners_obj = []
for bi, (bx, by) in enumerate(banner_positions):
    b_e = empty(f"banner_e{bi}", (bx, by, 14))
    # Hanging rod
    cyl(f"banner_rod{bi}", r=0.04, depth=2.5, segs=10,
        loc=(0, 0, 0), parent=b_e, mat_=M_WOOD).rotation_euler = (0, math.radians(90), 0)
    # Banner cloth
    color = BANNER_COLORS[bi % 6]
    banner = beveled_cube(f"banner{bi}", (1.8, 0.05, 2.5), bevel_offset=0.04,
                         loc=(0, 0, -1.30), parent=b_e, mat_=color)
    # Heraldic symbol (cross / fleur / shield emblem)
    sym = random.choice(["cross", "fleur", "lion"])
    if sym == "cross":
        beveled_cube(f"banner_sym_v{bi}", (0.20, 0.04, 0.90), loc=(0.06, 0, -1.30),
                     parent=b_e, mat_=M_BANNER_TRIM)
        beveled_cube(f"banner_sym_h{bi}", (0.85, 0.04, 0.20), loc=(0.06, 0, -1.10),
                     parent=b_e, mat_=M_BANNER_TRIM)
    elif sym == "fleur":
        # Simplified fleur-de-lis (3 petals)
        for j in range(3):
            sa = (j - 1) * 0.6
            beveled_cube(f"banner_fl{bi}_{j}", (0.12, 0.04, 0.50),
                         loc=(0.06, 0, -1.30), parent=b_e, mat_=M_BANNER_TRIM).rotation_euler = (0, sa, 0)
    elif sym == "lion":
        # Lion shape (head + body simplified)
        smooth_sphere(f"banner_lion_h{bi}", r=0.20, loc=(0.06, 0, -0.80),
                      parent=b_e, mat_=M_BANNER_TRIM)
        beveled_cube(f"banner_lion_b{bi}", (0.50, 0.05, 0.50), loc=(0.06, 0, -1.30),
                     parent=b_e, mat_=M_BANNER_TRIM)
    # Trim at bottom
    beveled_cube(f"banner_trim_b{bi}", (1.85, 0.07, 0.15), loc=(0, 0, -2.55),
                 parent=b_e, mat_=M_BANNER_TRIM)
    # Fringe (small balls)
    for fi in range(7):
        smooth_sphere(f"banner_fringe{bi}_{fi}", r=0.04,
                      loc=((fi - 3) * 0.26, 0, -2.70), parent=b_e, mat_=M_BANNER_TRIM)
    b_e["_phase"] = bi * 0.4
    banners_obj.append(b_e)

# ============ CHANDELIERS (3 large hanging) ============
chandeliers = []
chandelier_positions = [(0, -2, 12), (-7, 5, 11), (7, 5, 11)]
for ci, (cx, cy, cz) in enumerate(chandelier_positions):
    c_e = empty(f"chand_e{ci}", (cx, cy, cz))
    # Chain (3 segs)
    for i in range(3):
        cyl(f"chand_chain{ci}_{i}", r=0.02, depth=0.7, segs=8,
            loc=(0, 0, 0.7 + i*0.7), parent=c_e, mat_=M_BRONZE)
    # Main ring (large)
    cyl(f"chand_ring{ci}", r=1.0, depth=0.08, segs=24,
        loc=(0, 0, 0), parent=c_e, mat_=M_BRONZE).rotation_euler = (math.radians(90), 0, 0)
    # Inner ring
    cyl(f"chand_ring2{ci}", r=0.55, depth=0.06, segs=20,
        loc=(0, 0, 0.10), parent=c_e, mat_=M_BRONZE).rotation_euler = (math.radians(90), 0, 0)
    # 12 candles on outer + 6 on inner
    candles_chand = []
    for j in range(12):
        a = (j / 12.0) * math.pi * 2
        cx2 = 0.95 * math.cos(a); cy2 = 0.95 * math.sin(a)
        # Candle holder
        cyl(f"chand_h{ci}_{j}", r=0.05, depth=0.05, segs=8,
            loc=(cx2, cy2, 0.10), parent=c_e, mat_=M_BRONZE)
        # Candle
        cyl(f"chand_c{ci}_{j}", r=0.04, depth=0.25, segs=8,
            loc=(cx2, cy2, 0.25), parent=c_e, mat_=M_CANDLE)
        # Flame
        flame_o = smooth_cone(f"chand_fl_o{ci}_{j}", r1=0.04, r2=0.005, depth=0.10, segs=8,
                              loc=(cx2, cy2, 0.42), parent=c_e, mat_=M_FLAME)
        flame_i = smooth_cone(f"chand_fl_i{ci}_{j}", r1=0.025, r2=0.005, depth=0.08, segs=6,
                              loc=(cx2, cy2, 0.44), parent=c_e, mat_=M_FLAME_INNER)
        flame_o["_phase"] = j * 0.3 + ci * 0.5
        flame_i["_phase"] = j * 0.3 + ci * 0.5 + 0.2
        candles_chand.append((flame_o, flame_i))
    # Inner 6 candles
    for j in range(6):
        a = (j / 6.0) * math.pi * 2
        cx2 = 0.50 * math.cos(a); cy2 = 0.50 * math.sin(a)
        cyl(f"chand_ic_h{ci}_{j}", r=0.04, depth=0.04, segs=8,
            loc=(cx2, cy2, 0.20), parent=c_e, mat_=M_BRONZE)
        cyl(f"chand_ic{ci}_{j}", r=0.035, depth=0.22, segs=8,
            loc=(cx2, cy2, 0.33), parent=c_e, mat_=M_CANDLE)
        flame_o = smooth_cone(f"chand_ifl_o{ci}_{j}", r1=0.035, r2=0.005, depth=0.10, segs=8,
                              loc=(cx2, cy2, 0.48), parent=c_e, mat_=M_FLAME)
        flame_i = smooth_cone(f"chand_ifl_i{ci}_{j}", r1=0.02, r2=0.005, depth=0.08, segs=6,
                              loc=(cx2, cy2, 0.50), parent=c_e, mat_=M_FLAME_INNER)
        flame_o["_phase"] = j * 0.3 + ci * 0.5 + 1.0
        flame_i["_phase"] = j * 0.3 + ci * 0.5 + 1.2
        candles_chand.append((flame_o, flame_i))
    # Center hanging gem
    smooth_sphere(f"chand_gem{ci}", r=0.12, loc=(0, 0, -0.30),
                  parent=c_e, mat_=M_RUBY)
    chandeliers.append({"e": c_e, "flames": candles_chand, "phase": ci * 0.5})

# ============ 200 CONFETTI / ROSE PETALS ============
confetti = []
for i in range(200):
    cx = random.uniform(-13, 13)
    cy = random.uniform(-10, 12)
    cz = random.uniform(2, 14)
    # Flatten cube (petal-like)
    color = random.choice([M_CONFETTI, M_VITRAIL_RED, M_VITRAIL_YELLOW, M_DRESS_PINK])
    pt = beveled_cube(f"conf{i}", (0.08, 0.10, 0.02), bevel_offset=0.01,
                     loc=(cx, cy, cz), mat_=color)
    pt.rotation_euler = (random.uniform(0, math.pi*2),
                         random.uniform(0, math.pi*2),
                         random.uniform(0, math.pi*2))
    pt["_phase"] = random.uniform(0, math.pi*2)
    pt["_base_x"] = cx; pt["_base_y"] = cy; pt["_base_z"] = cz
    pt["_speed"] = random.uniform(0.5, 1.2)
    confetti.append(pt)

# ============ ANIMATION ============
fps = 30; duration_s = 6; total_frames = fps * duration_s

# King subtle breath + head turn (looking at archbishop)
for f in range(1, total_frames + 1, 4):
    t = (f - 1) / fps
    king_base.location.z = 1.30 + math.sin(t * 0.8) * 0.02
    king_base.keyframe_insert("location", frame=f)
    king_head_e.rotation_euler = (math.sin(t * 0.5) * math.radians(2), 0,
                                   math.sin(t * 0.4) * math.radians(3))
    king_head_e.keyframe_insert("rotation_euler", frame=f)

# Queen subtle motion + tiara sparkle
for f in range(1, total_frames + 1, 5):
    t = (f - 1) / fps
    queen_base.location.z = 1.30 + math.sin(t * 0.9 + 0.5) * 0.02
    queen_base.keyframe_insert("location", frame=f)
    queen_head_e.rotation_euler = (0, 0, math.sin(t * 0.5) * math.radians(8))
    queen_head_e.keyframe_insert("rotation_euler", frame=f)

# Archbishop hands lowering crown onto king (slow descent + arms motion)
for f in range(1, total_frames + 1, 3):
    t = (f - 1) / fps
    # Floating crown lowers slightly (sacred ritual motion)
    floating_crown_e.location.z = 2.0 - math.sin(t * 0.8) * 0.15
    floating_crown_e.keyframe_insert("location", frame=f)
    # Slight rotate
    floating_crown_e.rotation_euler = (0, 0, t * 0.3)
    floating_crown_e.keyframe_insert("rotation_euler", frame=f)
    # Both arms pulse
    arch_l_sh.rotation_euler = (math.radians(-100) + math.sin(t * 0.6) * math.radians(5),
                                0,
                                math.radians(15))
    arch_l_sh.keyframe_insert("rotation_euler", frame=f)
    arch_r_sh.rotation_euler = (math.radians(-100) + math.sin(t * 0.6) * math.radians(5),
                                0,
                                math.radians(-15))
    arch_r_sh.keyframe_insert("rotation_euler", frame=f)

# 15 Nobles - applause + bowing + head turn
for ni, nob in enumerate(nobles):
    phase = ni * 0.3
    base_z = nob["root"].location.z
    for f in range(1, total_frames + 1, 4):
        t = (f - 1) / fps
        nob["root"].location.z = base_z + math.sin(t * 1.5 + phase) * 0.04
        nob["root"].keyframe_insert("location", frame=f)
        nob["head_e"].rotation_euler = (math.sin(t * 1.0 + phase) * math.radians(5), 0,
                                         math.sin(t * 0.7 + phase) * math.radians(15))
        nob["head_e"].keyframe_insert("rotation_euler", frame=f)

# 8 Ladies similar
for li, lady in enumerate(ladies):
    phase = li * 0.4
    base_z = lady["root"].location.z
    for f in range(1, total_frames + 1, 4):
        t = (f - 1) / fps
        lady["root"].location.z = base_z + math.sin(t * 1.3 + phase) * 0.03
        lady["root"].keyframe_insert("location", frame=f)
        lady["head_e"].rotation_euler = (0, 0, math.sin(t * 0.8 + phase) * math.radians(12))
        lady["head_e"].keyframe_insert("rotation_euler", frame=f)

# Guards stoic but subtle bob
for gi, gu in enumerate(guards):
    phase = gi * 0.3
    for f in range(1, total_frames + 1, 8):
        t = (f - 1) / fps
        gu["root"].location.z = math.sin(t * 0.5 + phase) * 0.02
        gu["root"].keyframe_insert("location", frame=f)

# Hound subtle (head turn + tail wave)
for f in range(1, total_frames + 1, 5):
    t = (f - 1) / fps
    tail_e.rotation_euler = (math.radians(-30), 0, math.sin(t * 1.8) * math.radians(20))
    tail_e.keyframe_insert("rotation_euler", frame=f)
    head_e.rotation_euler = (0, 0, math.sin(t * 0.9) * math.radians(15))
    head_e.keyframe_insert("rotation_euler", frame=f)

# Banners wave gently
for ban in banners_obj:
    phase = ban["_phase"]
    for f in range(1, total_frames + 1, 5):
        t = (f - 1) / fps
        ban.rotation_euler = (math.sin(t * 1.2 + phase) * math.radians(4),
                               math.sin(t * 1.0 + phase + 0.3) * math.radians(3),
                               0)
        ban.keyframe_insert("rotation_euler", frame=f)

# Chandeliers candles flicker
for chand in chandeliers:
    phase = chand["phase"]
    flames = chand["flames"]
    for flame_o, flame_i in flames:
        p_o = flame_o["_phase"]
        p_i = flame_i["_phase"]
        for f in range(1, total_frames + 1, 3):
            t = (f - 1) / fps
            s_o = 1 + math.sin(t * 6.0 + p_o) * 0.30
            flame_o.scale = (s_o, s_o, s_o)
            flame_o.keyframe_insert("scale", frame=f)
            s_i = 1 + math.sin(t * 8.0 + p_i) * 0.35
            flame_i.scale = (s_i, s_i, s_i)
            flame_i.keyframe_insert("scale", frame=f)
    # Chandelier subtle swing
    for f in range(1, total_frames + 1, 6):
        t = (f - 1) / fps
        chand["e"].rotation_euler = (math.sin(t * 0.4 + phase) * math.radians(2),
                                      math.cos(t * 0.4 + phase) * math.radians(2),
                                      t * 0.05)
        chand["e"].keyframe_insert("rotation_euler", frame=f)

# Vitraux glow différentielles
for v in vitraux:
    phase = v["_phase"]
    for f in range(1, total_frames + 1, 6):
        t = (f - 1) / fps
        s = 1 + math.sin(t * 1.5 + phase) * 0.05
        v.scale = (s, s, s)
        v.keyframe_insert("scale", frame=f)

# Confetti falling (continuous celebration)
for ct in confetti:
    phase = ct["_phase"]; speed = ct["_speed"]
    bx, by, bz = ct["_base_x"], ct["_base_y"], ct["_base_z"]
    for f in range(1, total_frames + 1, 4):
        t = (f - 1) / fps
        z = bz - (speed * t) % 15
        x = bx + math.sin(t * 1.2 + phase) * 0.5
        y = by + math.cos(t * 1.0 + phase) * 0.5
        ct.location = (x, y, max(-0.2, z))
        ct.rotation_euler = (phase + t * 1.5, phase + t * 1.2, phase + t * 1.8)
        ct.keyframe_insert("location", frame=f)
        ct.keyframe_insert("rotation_euler", frame=f)

# ============ EXPORT ============
out_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "public", "_pbr_test")
out_dir = os.path.normpath(out_dir)
os.makedirs(out_dir, exist_ok=True)
out_glb = os.path.join(out_dir, "pbr_coronation_proc.glb")

bpy.ops.object.select_all(action='SELECT')
bpy.ops.export_scene.gltf(
    filepath=out_glb, export_format='GLB',
    export_animations=True, export_apply=False, export_yup=True, use_selection=False,
)
size_mb = os.path.getsize(out_glb) / (1024 * 1024)
print(f"[proc_medieval_king_coronation] DONE → {out_glb} ({size_mb:.2f} MB)")
print("[proc_medieval_king_coronation] Hall + 6 columns + carpet + throne + king crown sceptre orb + queen tiara + archbishop crown + 15 nobles + 8 ladies + 6 guards + hound + 10 vitraux + 8 banners + 3 chandeliers + 200 confetti")
