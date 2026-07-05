"""
proc_mayan_temple_jungle.py — 215e procédural AuroraIA (79e qualité)
Temple maya nuit: ONE ground + 500 fireflies floating + Tikal pyramide étagée + Quetzalcoatl + jaguar guards + 8 prêtres + ceiba trees
FIXES : 1 ground propre + 500 fireflies (signature jungle nuit) thématique
"""
import bpy, bmesh, math, random, os

random.seed(0x0AAA215)

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

# Materials — Mayan jungle night
M_SKY = mat("sky", (0.04, 0.06, 0.18, 1.0), 0.0, 0.7, emission=(0.04,0.06,0.18), emission_strength=1.0)
M_MOON = mat("moon", (0.92, 0.92, 0.95, 1.0), 0.0, 0.20, emission=(0.92,0.92,0.95), emission_strength=10.0)
M_STAR = mat("star", (1.0, 1.0, 0.95, 1.0), 0.0, 0.20, emission=(1.0,1.0,0.95), emission_strength=8.0)
M_CLOUD_NIGHT = mat("cloud_n", (0.15, 0.18, 0.32, 1.0), 0.0, 0.65, emission=(0.18,0.20,0.35), emission_strength=0.5, alpha=0.65)

# Ground
M_GROUND = mat("ground", (0.18, 0.22, 0.10, 1.0), 0.0, 0.85, emission=(0.15,0.20,0.08), emission_strength=0.2)
M_GROUND_STONE = mat("ground_s", (0.35, 0.30, 0.22, 1.0), 0.0, 0.85, emission=(0.30,0.25,0.20), emission_strength=0.2)
M_MOSS = mat("moss", (0.25, 0.45, 0.20, 1.0), 0.0, 0.80, emission=(0.20,0.40,0.18), emission_strength=0.4)
M_ROCK = mat("rock", (0.30, 0.28, 0.25, 1.0), 0.0, 0.85, emission=(0.25,0.23,0.20), emission_strength=0.2)

# Pyramid Mayan limestone
M_STONE = mat("stone", (0.55, 0.48, 0.38, 1.0), 0.0, 0.75, emission=(0.50,0.42,0.32), emission_strength=0.3)
M_STONE_DARK = mat("stone_d", (0.40, 0.34, 0.26, 1.0), 0.0, 0.80, emission=(0.36,0.30,0.22), emission_strength=0.2)
M_STONE_AGED = mat("stone_a", (0.48, 0.42, 0.32, 1.0), 0.0, 0.80, emission=(0.42,0.36,0.28), emission_strength=0.25)
M_GLYPH = mat("glyph", (0.32, 0.28, 0.20, 1.0), 0.0, 0.65, emission=(0.30,0.25,0.18), emission_strength=0.3)

# Jade + gold
M_JADE = mat("jade", (0.18, 0.65, 0.45, 1.0), 0.7, 0.20, emission=(0.18,0.65,0.45), emission_strength=2.5)
M_GOLD = mat("gold", (0.95, 0.78, 0.30, 1.0), 0.95, 0.18, emission=(0.90,0.72,0.28), emission_strength=1.2)
M_OBSIDIAN = mat("obsidian", (0.08, 0.05, 0.10, 1.0), 0.8, 0.18, emission=(0.05,0.02,0.08), emission_strength=0.4)

# Quetzal feathers green/blue/red
M_QUETZAL_GREEN = mat("q_g", (0.15, 0.75, 0.35, 1.0), 0.0, 0.45, emission=(0.15,0.75,0.35), emission_strength=2.0)
M_QUETZAL_BLUE = mat("q_b", (0.20, 0.55, 0.85, 1.0), 0.0, 0.45, emission=(0.20,0.55,0.85), emission_strength=2.0)
M_QUETZAL_RED = mat("q_r", (0.90, 0.15, 0.20, 1.0), 0.0, 0.45, emission=(0.90,0.15,0.20), emission_strength=2.0)
M_SNAKE_SCALE = mat("snake", (0.20, 0.55, 0.30, 1.0), 0.4, 0.40, emission=(0.18,0.50,0.28), emission_strength=0.8)

# Jaguar
M_JAGUAR_GOLD = mat("jaguar", (0.85, 0.65, 0.30, 1.0), 0.0, 0.55, emission=(0.78,0.60,0.28), emission_strength=0.4)
M_JAGUAR_SPOT = mat("jaguar_s", (0.15, 0.10, 0.05, 1.0), 0.0, 0.75)
M_JAGUAR_EYE = mat("jaguar_e", (1.0, 0.85, 0.20, 1.0), 0.0, 0.20, emission=(1.0,0.85,0.20), emission_strength=8.0)
M_JAGUAR_STATUE = mat("jaguar_st", (0.45, 0.38, 0.30, 1.0), 0.0, 0.70, emission=(0.42,0.35,0.28), emission_strength=0.3)

# Priests
M_SKIN_MAYA = mat("skin", (0.70, 0.50, 0.35, 1.0), 0.0, 0.65, emission=(0.62,0.45,0.32), emission_strength=0.4)
M_ROBE_WHITE = mat("robe_w", (0.92, 0.88, 0.80, 1.0), 0.0, 0.65, emission=(0.85,0.82,0.75), emission_strength=0.5)
M_ROBE_RED = mat("robe_r", (0.78, 0.18, 0.20, 1.0), 0.0, 0.65, emission=(0.72,0.18,0.18), emission_strength=0.6)
M_ROBE_BLUE = mat("robe_b", (0.18, 0.38, 0.65, 1.0), 0.0, 0.65, emission=(0.18,0.38,0.65), emission_strength=0.5)
M_ROBE_SHAMAN = mat("robe_sh", (0.55, 0.25, 0.55, 1.0), 0.0, 0.65, emission=(0.50,0.22,0.50), emission_strength=0.7)
M_HAIR_BLACK = mat("hair", (0.05, 0.03, 0.02, 1.0), 0.0, 0.85)
M_HEADDRESS = mat("hd", (0.95, 0.78, 0.30, 1.0), 0.85, 0.25, emission=(0.90,0.72,0.28), emission_strength=0.8)

# Ceiba trees + jungle
M_CEIBA_TRUNK = mat("ceiba_t", (0.25, 0.18, 0.12, 1.0), 0.0, 0.80, emission=(0.20,0.15,0.10), emission_strength=0.2)
M_CEIBA_LEAF = mat("ceiba_l", (0.18, 0.45, 0.20, 1.0), 0.0, 0.55, emission=(0.15,0.40,0.18), emission_strength=0.4)
M_CEIBA_LEAF_BRIGHT = mat("ceiba_lb", (0.30, 0.65, 0.30, 1.0), 0.0, 0.50, emission=(0.28,0.60,0.28), emission_strength=0.7)
M_VINE = mat("vine", (0.18, 0.32, 0.15, 1.0), 0.0, 0.75, emission=(0.15,0.28,0.12), emission_strength=0.4)

# Fire braziers
M_BRAZIER = mat("brazier", (0.30, 0.20, 0.12, 1.0), 0.0, 0.80, emission=(0.25,0.18,0.10), emission_strength=0.2)
M_FIRE_CORE = mat("fire_c", (1.0, 0.85, 0.30, 1.0), 0.0, 0.20, emission=(1.0,0.85,0.30), emission_strength=15.0)
M_FIRE_OUTER = mat("fire_o", (1.0, 0.45, 0.15, 1.0), 0.0, 0.25, emission=(1.0,0.45,0.15), emission_strength=10.0)

# FIREFLIES (signature jungle night particle)
M_FIREFLY = mat("firefly", (1.0, 0.95, 0.50, 1.0), 0.0, 0.10, emission=(1.0,0.95,0.50), emission_strength=22.0)
M_FIREFLY_GREEN = mat("firefly_g", (0.55, 1.0, 0.55, 1.0), 0.0, 0.10, emission=(0.55,1.0,0.55), emission_strength=20.0)

# ============ SKY + MOON + STARS ============
sky = smooth_sphere("sky", r=130, segs=32, rings=20, loc=(0,0,0), mat_=M_SKY)
sky.scale = (1,1,0.55)
moon_e = empty("moon_e", (-25, 50, 30))
smooth_sphere("moon", r=4.5, loc=(0, 0, 0), parent=moon_e, mat_=M_MOON)
for i in range(3):
    smooth_sphere(f"moon_halo{i}", r=4.5 + (i+1)*1.2, loc=(0, 0, 0), parent=moon_e, mat_=M_MOON)

# 100 stars
for i in range(100):
    a = random.uniform(0, math.pi*2)
    phi = random.uniform(math.pi/6, math.pi/2.2)
    r_star = 95
    sx = r_star * math.cos(phi) * math.cos(a)
    sy = r_star * math.cos(phi) * math.sin(a)
    sz = r_star * math.sin(phi) * 0.4
    smooth_sphere(f"star{i}", r=random.uniform(0.18, 0.40), segs=10, rings=8,
                  loc=(sx, sy, sz), mat_=M_STAR)

# Dark clouds drift
clouds = []
for i in range(5):
    a = (i / 5.0) * math.pi * 2
    rad = random.uniform(30, 45)
    cx, cy = rad*math.cos(a), rad*math.sin(a)
    cz = random.uniform(22, 30)
    c_e = empty(f"cloud_e{i}", (cx, cy, cz))
    for j in range(5):
        smooth_sphere(f"cloud{i}_{j}", r=random.uniform(2.5, 4.0),
                      loc=(random.uniform(-3,3), random.uniform(-2,2), random.uniform(-0.5,0.5)),
                      parent=c_e, mat_=M_CLOUD_NIGHT)
    c_e["_phase"] = random.uniform(0, math.pi*2)
    clouds.append(c_e)

# ============ ONE clean jungle ground ============
ground = beveled_cube("ground", (100, 100, 0.5), bevel_offset=0.08, loc=(0, 0, -0.25), mat_=M_GROUND)

# Stone plaza in front (organic edge)
plaza = beveled_cube("plaza", (20, 18, 0.20), bevel_offset=0.06, loc=(0, 5, 0.05), mat_=M_GROUND_STONE)

# 25 moss patches scattered
for i in range(25):
    a = random.uniform(0, math.pi*2)
    rad = random.uniform(15, 38)
    smooth_sphere(f"moss{i}", r=random.uniform(0.35, 0.7),
                  loc=(rad*math.cos(a), rad*math.sin(a), 0.10),
                  mat_=M_MOSS, scale=(1.2, 1.1, 0.18))

# 20 jungle rocks
for i in range(20):
    a = random.uniform(0, math.pi*2)
    rad = random.uniform(18, 42)
    smooth_sphere(f"rock{i}", r=random.uniform(0.4, 0.95),
                  loc=(rad*math.cos(a), rad*math.sin(a), 0.30),
                  mat_=M_ROCK,
                  scale=(random.uniform(0.8,1.3), random.uniform(0.8,1.3),
                         random.uniform(0.5,0.8)))

# ============ TIKAL PYRAMIDE ÉTAGÉE (5 levels + temple top) ============
pyramid_e = empty("pyramid", loc=(0, -8, 0))
levels = 5
for lv in range(levels):
    width = 14 - lv * 2.0
    depth = 12 - lv * 1.8
    height = 1.5
    lz = lv * height + height/2
    # Level stone (aged)
    color = M_STONE if lv % 2 == 0 else M_STONE_AGED
    beveled_cube(f"pyr_lv{lv}", (width, depth, height), bevel_offset=0.05,
                 loc=(0, 0, lz), parent=pyramid_e, mat_=color)
    # Glyph band (inset)
    beveled_cube(f"pyr_glyph_f{lv}", (width*0.85, 0.15, 0.4), bevel_offset=0.03,
                 loc=(0, -depth/2 - 0.05, lz), parent=pyramid_e, mat_=M_GLYPH)
    beveled_cube(f"pyr_glyph_b{lv}", (width*0.85, 0.15, 0.4), bevel_offset=0.03,
                 loc=(0, depth/2 + 0.05, lz), parent=pyramid_e, mat_=M_GLYPH)

# Central stair (front)
stair_y = -6
stair_z_top = levels * 1.5
for s_idx in range(levels * 4):
    step_y = stair_y - s_idx * 0.45
    step_z = (s_idx + 0.5) * 1.5 / 4
    beveled_cube(f"pyr_stair{s_idx}", (2.5, 0.50, 0.35), bevel_offset=0.03,
                 loc=(0, step_y, step_z), parent=pyramid_e, mat_=M_STONE_DARK)

# Temple at summit
temple_e = empty("temple", (0, 0, levels * 1.5 + 0.5), parent=pyramid_e)
# Main chamber
beveled_cube("temple_main", (4, 3, 2.5), bevel_offset=0.05,
             loc=(0, 0, 1.25), parent=temple_e, mat_=M_STONE)
# Entrance (dark)
beveled_cube("temple_door", (1.0, 0.5, 1.8), bevel_offset=0.04,
             loc=(0, -1.5, 0.90), parent=temple_e, mat_=M_OBSIDIAN)
# Mayan crested roof (signature corbel)
beveled_cube("temple_roof1", (4.5, 3.5, 0.30), bevel_offset=0.04,
             loc=(0, 0, 2.65), parent=temple_e, mat_=M_STONE)
# Roof comb (vertical crest)
beveled_cube("temple_comb", (3, 0.40, 2.0), bevel_offset=0.05,
             loc=(0, 0, 3.80), parent=temple_e, mat_=M_STONE_AGED)
# Glyphs on comb
for gi in range(4):
    smooth_sphere(f"temple_glyph{gi}", r=0.20,
                  loc=(0, 0.22, 3.0 + gi*0.4), parent=temple_e,
                  mat_=M_JADE, scale=(1, 0.3, 1))
# Top finial
smooth_cone("temple_finial", r1=0.20, r2=0.04, depth=0.50, segs=14,
            loc=(0, 0, 4.95), parent=temple_e, mat_=M_GOLD)

# ============ 2 JAGUAR STATUES (guards at base of stairs) ============
def make_jaguar_statue(name, loc, facing=0):
    base = empty(name, loc)
    base.rotation_euler = (0, 0, facing)
    # Stone pedestal
    beveled_cube(f"{name}_ped", (1.5, 1.0, 0.50), bevel_offset=0.05,
                 loc=(0, 0, 0.25), parent=base, mat_=M_STONE_DARK)
    # Crouched body
    beveled_cube(f"{name}_body", (1.2, 0.7, 0.50), bevel_offset=0.05,
                 loc=(0, 0, 0.85), parent=base, mat_=M_JAGUAR_STATUE)
    # Head
    head_e = empty(f"{name}_he", (-0.55, 0, 1.20), parent=base)
    smooth_sphere(f"{name}_head", r=0.30, segs=20, rings=14, loc=(0, 0, 0),
                  parent=head_e, mat_=M_JAGUAR_STATUE)
    # Snout (open mouth)
    smooth_cone(f"{name}_snout", r1=0.20, r2=0.18, depth=0.30, segs=14,
                loc=(-0.20, 0, -0.05), parent=head_e, mat_=M_JAGUAR_STATUE).rotation_euler = (0, math.radians(-90), 0)
    # Fangs (white)
    for side in (-1, 1):
        f_t = smooth_cone(f"{name}_fang{side}", r1=0.04, r2=0.005, depth=0.15, segs=8,
                          loc=(-0.30, side*0.06, -0.10), parent=head_e,
                          mat_=mat(f"{name}_fang_m{side}", (0.95,0.92,0.85,1), 0, 0.3))
        f_t.rotation_euler = (0, math.radians(180), 0)
    # Glowing eyes (signature jaguar guard)
    for side in (-1, 1):
        smooth_sphere(f"{name}_eye{side}", r=0.08, loc=(-0.15, side*0.10, 0.10),
                      parent=head_e, mat_=M_JAGUAR_EYE)
    # Ears
    for side in (-1, 1):
        ear = smooth_cone(f"{name}_ear{side}", r1=0.10, r2=0.02, depth=0.18, segs=10,
                          loc=(0.10, side*0.15, 0.25), parent=head_e, mat_=M_JAGUAR_STATUE)
        ear.rotation_euler = (math.radians(-15), 0, math.radians(side*15))
    # 4 legs (crouched)
    for x_idx, x in enumerate((0.45, -0.45)):
        for y_idx, y in enumerate((-0.25, 0.25)):
            cyl(f"{name}_leg{x_idx}{y_idx}", r=0.12, depth=0.45, segs=10,
                loc=(x, y, 0.30), parent=base, mat_=M_JAGUAR_STATUE)
            cyl(f"{name}_paw{x_idx}{y_idx}", r=0.13, depth=0.10, segs=10,
                loc=(x, y, 0.08), parent=base, mat_=M_JAGUAR_STATUE)
    # Tail curled
    tail = beveled_cube(f"{name}_tail", (0.10, 0.10, 0.70),
                       loc=(0.60, 0, 0.90), parent=base, mat_=M_JAGUAR_STATUE)
    tail.rotation_euler = (0, math.radians(60), 0)
    return {"root": base, "head_e": head_e}

jag1 = make_jaguar_statue("jag1", (-3.5, -10, 0), math.radians(0))
jag2 = make_jaguar_statue("jag2", (3.5, -10, 0), math.radians(0))

# ============ QUETZALCOATL feathered serpent (curving above) ============
serpent_e = empty("serpent", loc=(0, -6, 10))
serpent_segments = []
seg_count = 18
for i in range(seg_count):
    # S-curve spiraling
    t_param = i / float(seg_count)
    sx = math.sin(t_param * math.pi * 3) * 4
    sy = -t_param * 8
    sz = math.sin(t_param * math.pi * 2.5) * 1.5
    seg = smooth_sphere(f"serp_seg{i}", r=0.45 - i*0.012, segs=18, rings=12,
                        loc=(sx, sy, sz), parent=serpent_e, mat_=M_SNAKE_SCALE,
                        scale=(1.1, 1.1, 1.0))
    # Feathers (signature quetzalcoatl plumes)
    for j in range(3):
        ja = (j / 3.0) * math.pi * 2
        feather_color = M_QUETZAL_GREEN if j == 0 else (M_QUETZAL_BLUE if j == 1 else M_QUETZAL_RED)
        f = beveled_cube(f"serp_f{i}_{j}", (0.08, 0.30, 0.04), bevel_offset=0.02,
                         loc=(sx + math.cos(ja)*0.4, sy + math.sin(ja)*0.2, sz + 0.20),
                         parent=serpent_e, mat_=feather_color)
        f.rotation_euler = (0, 0, ja)
    serpent_segments.append(seg)
# Serpent head (last segment + open mouth + tongue)
head_loc_x = math.sin(math.pi * 3) * 4
head_loc_y = -8
head_loc_z = math.sin(math.pi * 2.5) * 1.5
serpent_head = smooth_sphere("serp_head", r=0.55, segs=22, rings=16,
                              loc=(head_loc_x, head_loc_y, head_loc_z),
                              parent=serpent_e, mat_=M_SNAKE_SCALE, scale=(1.4, 1.0, 0.8))
# Fangs
for side in (-1, 1):
    smooth_cone(f"serp_fang{side}", r1=0.08, r2=0.01, depth=0.30, segs=10,
                loc=(head_loc_x + 0.35, head_loc_y + side*0.20, head_loc_z - 0.15),
                parent=serpent_e,
                mat_=mat(f"serp_fang_m{side}", (0.95,0.92,0.85,1), 0, 0.3)).rotation_euler = (0, math.radians(60), 0)
# Eyes (golden glow)
for side in (-1, 1):
    smooth_sphere(f"serp_eye{side}", r=0.10,
                  loc=(head_loc_x + 0.15, head_loc_y + side*0.25, head_loc_z + 0.20),
                  parent=serpent_e, mat_=M_JAGUAR_EYE)
# Plume crown around head
for fi in range(8):
    fa = (fi / 8.0) * math.pi * 2
    plume = beveled_cube(f"serp_plume{fi}", (0.10, 0.60, 0.05), bevel_offset=0.02,
                         loc=(head_loc_x - 0.2 + math.cos(fa)*0.4,
                              head_loc_y + math.sin(fa)*0.4,
                              head_loc_z + 0.40),
                         parent=serpent_e,
                         mat_=M_QUETZAL_GREEN if fi % 2 == 0 else M_QUETZAL_BLUE)
    plume.rotation_euler = (math.radians(20), 0, fa)

# ============ 8 PRIESTS + SHAMAN ============
def make_priest(name, loc, robe_mat, headdress=False, facing=0, action="stand", scale=1.0):
    base = empty(name, loc)
    base.rotation_euler = (0, 0, facing)
    # Long robe cone
    smooth_cone(f"{name}_robe", r1=0.48*scale, r2=0.32*scale, depth=1.6*scale, segs=18,
                loc=(0, 0, 0.80*scale), parent=base, mat_=robe_mat)
    # Belt
    cyl(f"{name}_belt", r=0.42*scale, depth=0.15*scale, segs=18,
        loc=(0, 0, 1.45*scale), parent=base, mat_=M_GOLD)
    # Torso
    beveled_cube(f"{name}_torso", (0.42*scale, 0.25*scale, 0.50*scale), bevel_offset=0.05,
                 loc=(0, 0, 1.90*scale), parent=base, mat_=robe_mat)
    # Necklace jade
    cyl(f"{name}_necklace", r=0.20*scale, depth=0.05*scale, segs=14,
        loc=(0, -0.15*scale, 2.05*scale), parent=base, mat_=M_JADE)
    # Neck
    cyl(f"{name}_neck", r=0.09*scale, depth=0.18*scale, segs=10,
        loc=(0, 0, 2.25*scale), parent=base, mat_=M_SKIN_MAYA)
    # Head
    head_e = empty(f"{name}_head_e", (0, 0, 2.42*scale), parent=base)
    smooth_sphere(f"{name}_head", r=0.18*scale, segs=20, rings=14, loc=(0, 0, 0),
                  parent=head_e, mat_=M_SKIN_MAYA)
    # Hair (black long)
    smooth_sphere(f"{name}_hair", r=0.20*scale, loc=(0, 0.04*scale, 0.05*scale),
                  parent=head_e, mat_=M_HAIR_BLACK, scale=(1, 1, 0.9))
    # Eyes
    for side in (-1, 1):
        smooth_sphere(f"{name}_eye{side}", r=0.022*scale,
                      loc=(side*0.06*scale, -0.14*scale, 0.02*scale), parent=head_e,
                      mat_=mat(f"{name}_ew{side}", (0.05,0.05,0.05,1), 0, 0.5))
    # Headdress (priest signature)
    if headdress:
        # Crown band
        cyl(f"{name}_hd_band", r=0.22*scale, depth=0.10*scale, segs=16,
            loc=(0, 0, 0.20*scale), parent=head_e, mat_=M_HEADDRESS)
        # Feathered crest (3 tall feathers)
        for fi in range(7):
            fa = (fi - 3) * 0.30
            feather_color = [M_QUETZAL_GREEN, M_QUETZAL_BLUE, M_QUETZAL_RED][fi % 3]
            f = beveled_cube(f"{name}_hd_f{fi}", (0.05*scale, 0.10*scale, 0.50*scale), bevel_offset=0.02,
                             loc=(math.sin(fa)*0.20*scale, math.cos(fa)*0.10*scale, 0.55*scale),
                             parent=head_e, mat_=feather_color)
            f.rotation_euler = (math.radians(-fa*30), 0, fa)
        # Jade ornament forehead
        smooth_sphere(f"{name}_hd_jade", r=0.06*scale,
                      loc=(0, -0.15*scale, 0.25*scale), parent=head_e, mat_=M_JADE)
    # Arms based on action
    arms_e = []
    arm_poses = {
        "stand": [(math.radians(-15), 0), (math.radians(-15), 0)],
        "chant": [(math.radians(-100), -20), (math.radians(-100), 20)],
        "offer": [(math.radians(-130), 0), (math.radians(-130), 0)],
    }
    pose = arm_poses.get(action, arm_poses["stand"])
    for side_idx, side in enumerate((-1, 1)):
        sh = empty(f"{name}_sh{side_idx}", (side*0.32*scale, 0, 2.18*scale), parent=base)
        rx, rz = pose[side_idx]
        sh.rotation_euler = (rx, 0, math.radians(side*-15 + rz))
        # Robe sleeve
        beveled_cube(f"{name}_sleeve{side_idx}", (0.18*scale, 0.20*scale, 0.45*scale), bevel_offset=0.03,
                     loc=(0, 0, -0.25*scale), parent=sh, mat_=robe_mat)
        cyl(f"{name}_fa{side_idx}", r=0.07*scale, depth=0.30*scale, segs=10,
            loc=(0, 0, -0.60*scale), parent=sh, mat_=M_SKIN_MAYA)
        smooth_sphere(f"{name}_hand{side_idx}", r=0.07*scale, loc=(0, 0, -0.80*scale),
                      parent=sh, mat_=M_SKIN_MAYA)
        arms_e.append(sh)
    base["_phase"] = random.uniform(0, math.pi*2)
    return {"root": base, "head_e": head_e, "arms": arms_e}

priests = []
# 8 priests in semi-circle around plaza + shaman center
priest_specs = [
    ("priest1", (-6, 2, 0), M_ROBE_WHITE, False, math.radians(20), "chant", 1.0),
    ("priest2", (-4, 4, 0), M_ROBE_WHITE, False, math.radians(0), "chant", 1.0),
    ("priest3", (-2, 5, 0), M_ROBE_WHITE, False, math.radians(-10), "chant", 1.0),
    ("priest4", (2, 5, 0), M_ROBE_WHITE, False, math.radians(10), "chant", 1.0),
    ("priest5", (4, 4, 0), M_ROBE_WHITE, False, math.radians(0), "chant", 1.0),
    ("priest6", (6, 2, 0), M_ROBE_WHITE, False, math.radians(-20), "chant", 1.0),
    ("priest7", (-5, 0, 0), M_ROBE_RED, False, math.radians(45), "offer", 1.0),
    ("priest8", (5, 0, 0), M_ROBE_BLUE, False, math.radians(-45), "offer", 1.0),
]
for spec in priest_specs:
    name, loc, robe, hd, fac, act, sc = spec
    p = make_priest(name, loc, robe, headdress=hd, facing=fac, action=act, scale=sc)
    priests.append(p)
# Shaman with headdress + jade mask center front
shaman = make_priest("shaman", (0, 3, 0), M_ROBE_SHAMAN, headdress=True,
                     facing=math.radians(180), action="offer", scale=1.15)
# Jade mask on shaman face (signature)
mask = beveled_cube("shaman_mask", (0.22, 0.06, 0.25), bevel_offset=0.03,
                    loc=(0, -0.17, 0), parent=shaman["head_e"], mat_=M_JADE)
priests.append(shaman)

# ============ 4 FIRE BRAZIERS ============
braziers = []
brazier_pos = [(-8, -2, 0), (8, -2, 0), (-8, 12, 0), (8, 12, 0)]
for i, (bx, by, bz) in enumerate(brazier_pos):
    b_e = empty(f"brazier{i}", (bx, by, bz))
    # 3 stone legs
    for leg_idx in range(3):
        a = (leg_idx / 3.0) * math.pi * 2
        leg = cyl(f"br_leg{i}_{leg_idx}", r=0.10, depth=1.0, segs=10,
                  loc=(0.30*math.cos(a), 0.30*math.sin(a), 0.50),
                  parent=b_e, mat_=M_BRAZIER)
        leg.rotation_euler = (math.radians(10*math.cos(a)),
                              math.radians(10*math.sin(a)), 0)
    # Stone bowl
    smooth_sphere(f"br_bowl{i}", r=0.50, segs=20, rings=14,
                  loc=(0, 0, 1.05), parent=b_e, mat_=M_BRAZIER, scale=(1, 1, 0.5))
    # Glyph band around bowl
    cyl(f"br_glyph{i}", r=0.52, depth=0.12, segs=20,
        loc=(0, 0, 1.05), parent=b_e, mat_=M_GLYPH)
    # Flame composite
    flame_e = empty(f"br_fl{i}", (0, 0, 1.30), parent=b_e)
    smooth_cone(f"br_fl_o{i}", r1=0.40, r2=0.05, depth=1.6, segs=14,
                loc=(0, 0, 0.8), parent=flame_e, mat_=M_FIRE_OUTER)
    smooth_cone(f"br_fl_c{i}", r1=0.22, r2=0.02, depth=1.1, segs=14,
                loc=(0, 0, 0.55), parent=flame_e, mat_=M_FIRE_CORE)
    b_e["_phase"] = random.uniform(0, math.pi*2)
    braziers.append({"e": b_e, "flame": flame_e})

# ============ 6 GLYPH STELES (stone tablets with carvings) ============
for i in range(6):
    a = (i / 6.0) * math.pi * 2
    rad = 12
    sx = rad * math.cos(a)
    sy = rad * math.sin(a) + 6
    s_e = empty(f"stele{i}", (sx, sy, 0))
    beveled_cube(f"stele_b{i}", (0.6, 0.30, 2.0), bevel_offset=0.04,
                 loc=(0, 0, 1.0), parent=s_e, mat_=M_STONE)
    # Glyphs
    for g in range(4):
        gz = 0.4 + g * 0.4
        smooth_sphere(f"stele_g{i}_{g}", r=0.10,
                      loc=(0, -0.17, gz), parent=s_e, mat_=M_GLYPH, scale=(1, 0.4, 1))

# ============ 10 CEIBA JUNGLE TREES (giant + vines) ============
ceibas = []
ceiba_pos = [(-25, 20, 0), (25, 22, 0), (-30, 5, 0), (30, 8, 0),
             (-22, 30, 0), (22, 30, 0), (-35, -10, 0), (35, -10, 0),
             (-15, 28, 0), (15, 28, 0)]
for i, (tx, ty, tz) in enumerate(ceiba_pos):
    base = empty(f"ceiba{i}", (tx, ty, tz))
    # Tall trunk (8 segments)
    for s in range(8):
        seg_r = 0.55 - s*0.03
        seg = smooth_cone(f"ceiba{i}_t{s}", r1=seg_r, r2=seg_r*0.95,
                          depth=1.2, segs=14,
                          loc=(0, 0, (s+0.5)*1.2),
                          parent=base, mat_=M_CEIBA_TRUNK)
    # Buttress roots (signature ceiba)
    for r in range(5):
        ra = (r / 5.0) * math.pi * 2
        root = beveled_cube(f"ceiba{i}_root{r}", (0.20, 0.50, 0.80), bevel_offset=0.03,
                            loc=(0.55*math.cos(ra), 0.55*math.sin(ra), 0.40),
                            parent=base, mat_=M_CEIBA_TRUNK)
        root.rotation_euler = (0, math.radians(35), ra)
    # Massive canopy
    for j in range(10):
        a = (j / 10.0) * math.pi * 2
        rad = random.uniform(2.5, 4.5)
        col = M_CEIBA_LEAF if j % 2 == 0 else M_CEIBA_LEAF_BRIGHT
        smooth_sphere(f"ceiba{i}_c{j}", r=random.uniform(1.6, 2.4),
                      loc=(rad*math.cos(a), rad*math.sin(a),
                           9.5 + random.uniform(-0.5, 1.5)),
                      parent=base, mat_=col, scale=(1, 1, 0.85))
    # Vines hanging
    for v in range(4):
        va = (v / 4.0) * math.pi * 2
        vine_e = empty(f"ceiba{i}_ve{v}", (3*math.cos(va), 3*math.sin(va), 8),
                       parent=base)
        for k in range(5):
            cyl(f"ceiba{i}_v{v}_{k}", r=0.04, depth=0.6, segs=8,
                loc=(0, 0, -k*0.6 - 0.30), parent=vine_e, mat_=M_VINE)
    base["_phase"] = random.uniform(0, math.pi*2)
    ceibas.append(base)

# ============ 4 PARROTS flying ============
def make_parrot(name, loc, body_color=M_QUETZAL_RED):
    base = empty(name, loc)
    smooth_sphere(f"{name}_body", r=0.22, segs=18, rings=12, loc=(0, 0, 0),
                  parent=base, mat_=body_color, scale=(1.7, 1, 1))
    # Head
    head = smooth_sphere(f"{name}_head", r=0.18, loc=(0.35, 0, 0.05),
                         parent=base, mat_=body_color)
    smooth_cone(f"{name}_beak", r1=0.08, r2=0.02, depth=0.18, segs=10,
                loc=(0.55, 0, -0.02), parent=base,
                mat_=mat(f"{name}_beak_m", (0.18, 0.10, 0.05, 1), 0, 0.7)).rotation_euler = (0, math.radians(90), 0)
    # Eye
    smooth_sphere(f"{name}_eye", r=0.025, loc=(0.45, 0.10, 0.10),
                  parent=base, mat_=mat(f"{name}_eye_m", (0.05,0.05,0.05,1), 0, 0.5))
    # Wings
    wings = []
    for side in (-1, 1):
        w_e = empty(f"{name}_we{side}", (0, side*0.20, 0), parent=base)
        beveled_cube(f"{name}_w{side}", (0.35, 0.45, 0.04), bevel_offset=0.02,
                     loc=(0, side*0.30, 0), parent=w_e,
                     mat_=M_QUETZAL_BLUE if side > 0 else M_QUETZAL_GREEN)
        wings.append((w_e, side))
    # Tail
    beveled_cube(f"{name}_tail", (0.30, 0.20, 0.08), loc=(-0.40, 0, 0),
                 parent=base, mat_=body_color)
    base["_phase"] = random.uniform(0, math.pi*2)
    return {"root": base, "wings": wings}

parrots = []
parrot_specs = [
    ("parrot1", (-10, 14, 12), M_QUETZAL_RED),
    ("parrot2", (10, 14, 12), M_QUETZAL_BLUE),
    ("parrot3", (-12, 18, 14), M_QUETZAL_GREEN),
    ("parrot4", (12, 16, 13), M_QUETZAL_RED),
]
for spec in parrot_specs:
    name, loc, col = spec
    p = make_parrot(name, loc, col)
    parrots.append(p)

# ============================================================
# ⭐ 500 FIREFLIES (PARTICULE THÉMATIQUE OBLIGATOIRE jungle nuit)
# ============================================================
fireflies = []
for i in range(500):
    px = random.uniform(-40, 40)
    py = random.uniform(-40, 40)
    pz = random.uniform(0.5, 18)
    color = M_FIREFLY if i % 3 != 0 else M_FIREFLY_GREEN
    f_obj = smooth_sphere(f"firefly{i}", r=random.uniform(0.06, 0.10), segs=10, rings=6,
                          loc=(px, py, pz), mat_=color)
    f_obj["_phase"] = random.uniform(0, math.pi*2)
    f_obj["_base_x"] = px; f_obj["_base_y"] = py; f_obj["_base_z"] = pz
    f_obj["_amp_x"] = random.uniform(0.8, 2.0)
    f_obj["_amp_y"] = random.uniform(0.8, 2.0)
    f_obj["_amp_z"] = random.uniform(0.4, 1.5)
    f_obj["_speed"] = random.uniform(0.4, 1.2)
    fireflies.append(f_obj)

# ============ ANIMATION ============
fps = 30; duration_s = 6; total_frames = fps * duration_s

# Ceiba sway
for t in ceibas:
    phase = t["_phase"]
    for f in range(1, total_frames + 1, 5):
        t_v = (f - 1) / fps
        t.rotation_euler = (math.sin(t_v * 0.7 + phase) * math.radians(2.5),
                             math.cos(t_v * 0.6 + phase) * math.radians(2.0),
                             0)
        t.keyframe_insert("rotation_euler", frame=f)

# Priests chant sway
for p in priests:
    phase = p["root"]["_phase"]
    base_z = p["root"].location.z
    for f in range(1, total_frames + 1, 4):
        t = (f - 1) / fps
        p["root"].location.z = base_z + math.sin(t * 1.5 + phase) * 0.04
        p["root"].rotation_euler = (math.sin(t * 1.2 + phase) * math.radians(4),
                                     math.cos(t * 1.0 + phase) * math.radians(3),
                                     p["root"].rotation_euler.z)
        p["root"].keyframe_insert("location", frame=f)
        p["root"].keyframe_insert("rotation_euler", frame=f)
        # Head bob
        p["head_e"].rotation_euler = (math.sin(t * 1.5 + phase) * math.radians(8), 0,
                                       math.sin(t * 1.2 + phase) * math.radians(10))
        p["head_e"].keyframe_insert("rotation_euler", frame=f)
        # Arms wave subtle
        for ai, arm in enumerate(p["arms"]):
            wave = math.sin(t * 2.5 + phase + ai * math.pi) * math.radians(8)
            base_rx = arm.rotation_euler.x
            arm.rotation_euler = (base_rx + wave, 0, arm.rotation_euler.z)
            arm.keyframe_insert("rotation_euler", frame=f)

# Quetzalcoatl serpent undulates (massive S-wave)
for f in range(1, total_frames + 1, 3):
    t = (f - 1) / fps
    # Whole serpent body weaves
    serpent_e.rotation_euler = (math.sin(t * 0.8) * math.radians(8),
                                 math.cos(t * 0.7) * math.radians(6),
                                 t * 0.3)
    serpent_e.keyframe_insert("rotation_euler", frame=f)
    serpent_e.location = (math.sin(t * 0.6) * 1.5, -6 + math.cos(t * 0.5) * 1.0,
                          10 + math.sin(t * 1.0) * 0.5)
    serpent_e.keyframe_insert("location", frame=f)

# Jaguar statues - glowing eyes pulse (emit material doesn't keyframe easy, so scale eyes)
for jag in (jag1, jag2):
    for obj in bpy.data.objects:
        if obj.name.startswith(f"{jag['root'].name}_eye"):
            phase = hash(obj.name) % 100 * 0.05
            for f in range(1, total_frames + 1, 4):
                t = (f - 1) / fps
                s = 1 + math.sin(t * 3.0 + phase) * 0.30
                obj.scale = (s, s, s)
                obj.keyframe_insert("scale", frame=f)

# Brazier flames flicker
for br in braziers:
    phase = br["e"]["_phase"]
    for f in range(1, total_frames + 1, 3):
        t = (f - 1) / fps
        s = 1 + math.sin(t * 5.0 + phase) * 0.15
        br["flame"].scale = (1 + math.sin(t * 4.0 + phase) * 0.10,
                              1 + math.cos(t * 4.5 + phase) * 0.10, s)
        br["flame"].rotation_euler = (0, 0, math.sin(t * 3.0 + phase) * 0.18)
        br["flame"].keyframe_insert("scale", frame=f)
        br["flame"].keyframe_insert("rotation_euler", frame=f)

# Parrots orbit + wings flap
for p in parrots:
    phase = p["root"]["_phase"]
    base_x, base_y, base_z = p["root"].location.x, p["root"].location.y, p["root"].location.z
    for f in range(1, total_frames + 1, 3):
        t = (f - 1) / fps
        # Orbit drift
        p["root"].location = (base_x + math.sin(t * 0.8 + phase) * 2.0,
                              base_y + math.cos(t * 0.7 + phase) * 1.5,
                              base_z + math.sin(t * 1.2 + phase) * 0.6)
        p["root"].rotation_euler = (0, 0, t * 0.8 + phase)
        p["root"].keyframe_insert("location", frame=f)
        p["root"].keyframe_insert("rotation_euler", frame=f)
        # Wing flap
        flap = math.sin(t * 5.0 + phase) * math.radians(35)
        for w_e, side in p["wings"]:
            w_e.rotation_euler = (side * flap, 0, 0)
            w_e.keyframe_insert("rotation_euler", frame=f)

# Clouds drift
for c_e in clouds:
    phase = c_e["_phase"]
    bx, by = c_e.location.x, c_e.location.y
    for f in range(1, total_frames + 1, 8):
        t = (f - 1) / fps
        c_e.location = (bx + math.sin(t * 0.3 + phase) * 0.7,
                        by + math.cos(t * 0.25 + phase) * 0.7,
                        c_e.location.z)
        c_e.keyframe_insert("location", frame=f)

# Moon halos pulse
for obj in bpy.data.objects:
    if obj.name.startswith("moon_halo"):
        for f in range(1, total_frames + 1, 6):
            t = (f - 1) / fps
            s = 1 + math.sin(t * 0.6) * 0.05
            obj.scale = (s, s, s)
            obj.keyframe_insert("scale", frame=f)

# ============================================================
# ⭐⭐⭐ 500 FIREFLIES FLOATING (signature jungle night)
# ============================================================
for ff in fireflies:
    phase = ff["_phase"]; speed = ff["_speed"]
    bx, by, bz = ff["_base_x"], ff["_base_y"], ff["_base_z"]
    ax, ay, az = ff["_amp_x"], ff["_amp_y"], ff["_amp_z"]
    for f in range(1, total_frames + 1, 4):
        t = (f - 1) / fps
        # Spiral drift floating slow
        x = bx + ax * math.sin(t * speed + phase)
        y = by + ay * math.cos(t * speed * 0.9 + phase)
        z = bz + az * math.sin(t * speed * 1.3 + phase * 1.5)
        ff.location = (x, y, max(0.2, z))
        ff.keyframe_insert("location", frame=f)
        # Pulse scale (firefly blink)
        sc = 1 + math.sin(t * 4.0 + phase) * 0.3
        ff.scale = (sc, sc, sc)
        ff.keyframe_insert("scale", frame=f)

# ============ EXPORT ============
out_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "public", "_pbr_test")
out_dir = os.path.normpath(out_dir)
os.makedirs(out_dir, exist_ok=True)
out_glb = os.path.join(out_dir, "pbr_mayan_proc.glb")

bpy.ops.object.select_all(action='SELECT')
bpy.ops.export_scene.gltf(
    filepath=out_glb, export_format='GLB',
    export_animations=True, export_apply=False, export_yup=True, use_selection=False,
)
size_mb = os.path.getsize(out_glb) / (1024 * 1024)
print(f"[proc_mayan_temple_jungle] DONE → {out_glb} ({size_mb:.2f} MB)")
print("[proc_mayan_temple_jungle] ONE ground + Tikal 5-tier + temple + 2 jaguar statues + Quetzalcoatl + 9 priests + 4 braziers + 10 ceibas + 4 parrots + 500 FIREFLIES")
print("⭐ FIXES: 1 ground + 500 fireflies floating spiral drift + pulse blink (signature jungle night mandatory) ⭐")
