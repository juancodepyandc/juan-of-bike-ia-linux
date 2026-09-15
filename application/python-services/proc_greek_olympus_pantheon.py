"""
proc_greek_olympus_pantheon.py — 202e procédural AuroraIA (66e qualité)
Mont Olympus : Parthénon + 12 Olympiens + Pégase + Cyclope + Centaure + Hydre 9 têtes + nuages
"""
import bpy, bmesh, math, random, os

random.seed(0xA10E202)

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
M_SKY = mat("sky", (0.55, 0.75, 0.95, 1.0), 0.0, 0.7, emission=(0.65,0.82,1.0), emission_strength=2.5)
M_SUN = mat("sun", (1.0, 0.95, 0.65, 1.0), 0.0, 0.10, emission=(1.0,0.95,0.65), emission_strength=22.0)
M_CLOUD = mat("cloud", (0.98, 0.95, 1.0, 1.0), 0.0, 0.55, emission=(0.95,0.92,0.98), emission_strength=3.0, alpha=0.85)
M_STAR = mat("star", (1.0, 1.0, 1.0, 1.0), 0.0, 0.05, emission=(1.0,1.0,1.0), emission_strength=15.0)

# Marble + temple
M_MARBLE = mat("marble", (0.92, 0.90, 0.85, 1.0), 0.1, 0.40, emission=(0.78,0.75,0.70), emission_strength=0.8)
M_MARBLE_GOLD = mat("marble_g", (0.95, 0.85, 0.55, 1.0), 0.4, 0.30, emission=(0.85,0.75,0.45), emission_strength=1.0)
M_GOLD = mat("gold", (1.0, 0.78, 0.25, 1.0), 0.95, 0.18, emission=(0.95,0.72,0.22), emission_strength=1.5)
M_GOLD_BRIGHT = mat("gold_b", (1.0, 0.88, 0.35, 1.0), 0.95, 0.15, emission=(1.0,0.85,0.40), emission_strength=2.8)
M_BRONZE = mat("bronze", (0.65, 0.42, 0.20, 1.0), 0.85, 0.40, emission=(0.55,0.35,0.18), emission_strength=0.7)
M_STONE = mat("stone", (0.65, 0.62, 0.58, 1.0), 0.0, 0.75, emission=(0.55,0.52,0.48), emission_strength=0.5)

# 12 Olympians skin (différents tons for gods)
M_SKIN_ZEUS = mat("skin_zeus", (0.92, 0.85, 0.75, 1.0), 0.0, 0.55, emission=(0.85,0.78,0.68), emission_strength=0.6)
M_SKIN_GOD = mat("skin_god", (0.95, 0.88, 0.78, 1.0), 0.0, 0.50, emission=(0.88,0.82,0.72), emission_strength=0.5)
M_SKIN_GODDESS = mat("skin_goddess", (1.0, 0.92, 0.85, 1.0), 0.0, 0.45, emission=(0.92,0.85,0.78), emission_strength=0.6)
M_HAIR_GOLDEN = mat("hair_g", (0.95, 0.78, 0.30, 1.0), 0.3, 0.45, emission=(0.85,0.70,0.28), emission_strength=0.8)
M_HAIR_BLACK = mat("hair_b", (0.10, 0.08, 0.05, 1.0), 0.0, 0.85)
M_HAIR_BROWN = mat("hair_br", (0.30, 0.18, 0.10, 1.0), 0.0, 0.80)
M_BEARD_WHITE = mat("beard_w", (0.85, 0.82, 0.78, 1.0), 0.0, 0.75, emission=(0.78,0.75,0.72), emission_strength=0.5)
M_BEARD_BROWN = mat("beard_br", (0.40, 0.25, 0.15, 1.0), 0.0, 0.80)

# Robes various Olympian colors
M_ROBE_PURPLE = mat("robe_p", (0.50, 0.20, 0.65, 1.0), 0.0, 0.45, emission=(0.45,0.18,0.60), emission_strength=0.7)
M_ROBE_WHITE = mat("robe_w", (0.95, 0.92, 0.88, 1.0), 0.0, 0.45, emission=(0.85,0.82,0.78), emission_strength=0.7)
M_ROBE_BLUE = mat("robe_b", (0.20, 0.40, 0.85, 1.0), 0.0, 0.45, emission=(0.18,0.35,0.78), emission_strength=0.8)
M_ROBE_GREEN = mat("robe_g", (0.20, 0.55, 0.30, 1.0), 0.0, 0.45, emission=(0.18,0.50,0.28), emission_strength=0.7)
M_ROBE_RED = mat("robe_r", (0.65, 0.15, 0.15, 1.0), 0.0, 0.45, emission=(0.55,0.15,0.13), emission_strength=0.8)
M_ROBE_ROSE = mat("robe_rose", (0.95, 0.55, 0.75, 1.0), 0.0, 0.45, emission=(0.85,0.50,0.68), emission_strength=0.8)
M_ROBE_GREY = mat("robe_grey", (0.40, 0.40, 0.45, 1.0), 0.0, 0.55, emission=(0.35,0.35,0.40), emission_strength=0.5)

# Weapons / attributes
M_LIGHTNING = mat("lightning", (0.85, 0.95, 1.0, 1.0), 0.0, 0.05, emission=(0.90,0.98,1.0), emission_strength=25.0)
M_SPEAR = mat("spear", (0.85, 0.85, 0.90, 1.0), 0.95, 0.10, emission=(0.78,0.78,0.85), emission_strength=0.8)
M_BOW = mat("bow", (0.55, 0.30, 0.15, 1.0), 0.3, 0.55, emission=(0.50,0.28,0.13), emission_strength=0.5)
M_LYRE = mat("lyre", (1.0, 0.78, 0.30, 1.0), 0.85, 0.20, emission=(0.95,0.72,0.28), emission_strength=1.0)
M_TRIDENT = mat("trident", (0.85, 0.65, 0.25, 1.0), 0.92, 0.15, emission=(0.90,0.70,0.30), emission_strength=2.5)
M_HAMMER = mat("hammer", (0.45, 0.45, 0.48, 1.0), 0.92, 0.30, emission=(0.40,0.40,0.45), emission_strength=0.6)
M_WINE_CUP = mat("wine_cup", (0.65, 0.45, 0.20, 1.0), 0.85, 0.30, emission=(0.55,0.40,0.18), emission_strength=0.6)
M_WINE = mat("wine", (0.45, 0.05, 0.10, 1.0), 0.0, 0.20, emission=(0.50,0.10,0.12), emission_strength=2.5)

# Pegasus
M_PEGASUS = mat("pegasus", (1.0, 0.98, 0.95, 1.0), 0.0, 0.40, emission=(0.92,0.90,0.88), emission_strength=0.8)
M_PEGASUS_MANE = mat("peg_mane", (0.95, 0.88, 0.55, 1.0), 0.0, 0.55, emission=(0.85,0.78,0.50), emission_strength=0.9)
M_PEGASUS_HOOF = mat("peg_hoof", (0.85, 0.65, 0.30, 1.0), 0.85, 0.20, emission=(0.75,0.58,0.25), emission_strength=0.5)

# Cyclops
M_CYCLOPS_SKIN = mat("cyc_skin", (0.55, 0.45, 0.35, 1.0), 0.0, 0.65, emission=(0.45,0.38,0.28), emission_strength=0.4)
M_CYCLOPS_EYE = mat("cyc_eye", (1.0, 0.30, 0.10, 1.0), 0.0, 0.15, emission=(1.0,0.35,0.15), emission_strength=8.0)
M_CYCLOPS_HAIR = mat("cyc_hair", (0.18, 0.12, 0.08, 1.0), 0.0, 0.80)

# Centaur
M_CENT_HORSE = mat("cent_horse", (0.45, 0.25, 0.15, 1.0), 0.0, 0.55, emission=(0.40,0.22,0.13), emission_strength=0.4)
M_CENT_HUMAN = mat("cent_human", (0.85, 0.70, 0.55, 1.0), 0.0, 0.55, emission=(0.75,0.62,0.48), emission_strength=0.4)

# Hydra
M_HYDRA_BODY = mat("hydra", (0.20, 0.50, 0.30, 1.0), 0.0, 0.50, emission=(0.18,0.45,0.28), emission_strength=0.7)
M_HYDRA_BELLY = mat("hydra_belly", (0.55, 0.85, 0.55, 1.0), 0.0, 0.55, emission=(0.50,0.78,0.50), emission_strength=0.6)
M_HYDRA_EYE = mat("hydra_eye", (1.0, 0.90, 0.20, 1.0), 0.0, 0.15, emission=(1.0,0.90,0.20), emission_strength=9.0)
M_HYDRA_TONGUE = mat("hydra_tongue", (0.85, 0.20, 0.30, 1.0), 0.0, 0.45, emission=(0.80,0.18,0.28), emission_strength=2.0)
M_HYDRA_VENOM = mat("hydra_venom", (0.55, 1.0, 0.30, 1.0), 0.0, 0.10, emission=(0.55,1.0,0.30), emission_strength=5.0)

# Olive
M_OLIVE_TRUNK = mat("olive_t", (0.45, 0.40, 0.30, 1.0), 0.0, 0.85)
M_OLIVE_LEAF = mat("olive_l", (0.55, 0.70, 0.45, 1.0), 0.0, 0.60, emission=(0.45,0.62,0.38), emission_strength=0.5)
M_OLIVE = mat("olive", (0.20, 0.25, 0.10, 1.0), 0.3, 0.50, emission=(0.18,0.22,0.10), emission_strength=0.6)

# Aura (god effects)
M_AURA = mat("aura", (1.0, 0.95, 0.50, 1.0), 0.0, 0.10, emission=(1.0,0.92,0.55), emission_strength=4.0, alpha=0.4)

# ============ SKY + SUN + CLOUDS ============
sky = smooth_sphere("sky", r=100, segs=32, rings=20, loc=(0,0,0), mat_=M_SKY, scale=(1,1,0.65))
sky.scale = (1,1,0.65)
sun = smooth_sphere("sun", r=4.5, loc=(0, 40, 30), mat_=M_SUN)

# 50 stars (visible despite day - mountain top)
for i in range(50):
    sx = random.uniform(-50, 50)
    sy = random.uniform(20, 45)
    sz = random.uniform(20, 38)
    star = smooth_sphere(f"star{i}", r=random.uniform(0.06, 0.12), segs=8, rings=6,
                        loc=(sx, sy, sz), mat_=M_STAR)
    star["_phase"] = random.uniform(0, math.pi*2)

# 8 clouds (low - around mount top)
clouds = []
for i in range(8):
    a = (i / 8.0) * math.pi * 2
    rad = random.uniform(18, 28)
    cx, cy = rad*math.cos(a), rad*math.sin(a)
    cz = random.uniform(6, 14)
    c_e = empty(f"cloud_e{i}", (cx, cy, cz))
    for j in range(5):
        smooth_sphere(f"cloud{i}_{j}", r=random.uniform(2.5, 4.0),
                      loc=(random.uniform(-3,3), random.uniform(-2,2), random.uniform(-0.5,0.5)),
                      parent=c_e, mat_=M_CLOUD)
    c_e["_phase"] = random.uniform(0, math.pi*2)
    clouds.append(c_e)

# ============ MOUNT TOP (rocky plateau) ============
ground = beveled_cube("ground", (60, 60, 0.6), bevel_offset=0.10, loc=(0, 0, -0.3), mat_=M_STONE)
# Cloud line at edge of platform (8 puffs around base)
for i in range(8):
    a = (i / 8.0) * math.pi * 2
    smooth_sphere(f"base_cloud{i}", r=2.5,
                  loc=(28*math.cos(a), 28*math.sin(a), -0.5),
                  mat_=M_CLOUD, scale=(1.5, 1.2, 0.4))

# ============ PARTHENON TEMPLE central ============
parthenon_e = empty("parthenon", loc=(0, 0, 0))

# Stylobate (platform with 3 steps)
for i in range(3):
    beveled_cube(f"st{i}", (20 - i*0.6, 12 - i*0.5, 0.40),
                 loc=(0, 0, 0.20 + i*0.40), parent=parthenon_e, mat_=M_MARBLE)

# 16 IONIC COLUMNS (8 front + 8 back, plus sides)
column_positions = []
# Front row 8
for i in range(8):
    column_positions.append(((i-3.5)*2.4, -5.0))
# Back row 8
for i in range(8):
    column_positions.append(((i-3.5)*2.4, 5.0))
# Left + right rows 6 each
for i in range(6):
    column_positions.append((-9, (i-2.5)*2.0))
    column_positions.append((9, (i-2.5)*2.0))

columns = []
for ci, (cx, cy) in enumerate(column_positions):
    col_e = empty(f"col_e{ci}", (cx, cy, 1.4), parent=parthenon_e)
    # Base
    cyl(f"col_base{ci}", r=0.45, depth=0.25, segs=20,
        loc=(0, 0, 0), parent=col_e, mat_=M_MARBLE)
    # Shaft (5 segs - fluted columns)
    for s in range(5):
        z = (s+0.5) * 0.95
        r = 0.38 - s*0.012
        seg = smooth_cone(f"col_s{ci}_{s}", r1=r, r2=r-0.012, depth=0.95, segs=24,
                          loc=(0, 0, z), parent=col_e, mat_=M_MARBLE)
        # 4 small flute lines around each
        for fl in range(4):
            a = (fl / 4.0) * math.pi * 2
            beveled_cube(f"col_fl{ci}_{s}_{fl}", (0.03, 0.03, 0.85), bevel_offset=0.005,
                         loc=(r*0.95*math.cos(a), r*0.95*math.sin(a), z),
                         parent=col_e, mat_=M_MARBLE)
    # IONIC CAPITAL (2 volutes scroll)
    cap_z = 4.85
    # Abacus base
    beveled_cube(f"col_cap_a{ci}", (0.85, 0.85, 0.10), bevel_offset=0.03,
                 loc=(0, 0, cap_z), parent=col_e, mat_=M_MARBLE)
    # 2 volutes (scrolls signature ionic)
    for side in (-1, 1):
        # Volute as flatten sphere
        smooth_sphere(f"col_vol{ci}_{side}", r=0.22,
                      loc=(side*0.50, 0, cap_z - 0.05), parent=col_e, mat_=M_MARBLE,
                      scale=(1, 0.4, 1))
    # Top abacus
    beveled_cube(f"col_top{ci}", (0.95, 0.95, 0.10), bevel_offset=0.03,
                 loc=(0, 0, cap_z + 0.20), parent=col_e, mat_=M_MARBLE)
    columns.append(col_e)

# Entablature (top across columns)
beveled_cube("entablature_n", (20, 12.5, 0.40), bevel_offset=0.06,
             loc=(0, 0, 6.95), parent=parthenon_e, mat_=M_MARBLE)
# Frieze (carved band)
beveled_cube("frieze", (20.5, 12.6, 0.30), loc=(0, 0, 7.30),
             parent=parthenon_e, mat_=M_MARBLE_GOLD)

# Pediment (triangular roof)
# Use 2 angled slabs forming peak
for side in (-1, 1):
    ped = beveled_cube(f"pediment_{side}", (20, 8, 0.30), bevel_offset=0.05,
                      loc=(0, side*3, 8.4), parent=parthenon_e, mat_=M_MARBLE)
    ped.rotation_euler = (math.radians(side*-20), 0, 0)
# Top apex (ornament golden)
smooth_cone("apex", r1=0.40, r2=0.05, depth=0.85, segs=12,
            loc=(0, 0, 9.8), parent=parthenon_e, mat_=M_GOLD_BRIGHT)

# Pediment sculpture (5 figures relief)
for i in range(5):
    x = (i - 2) * 2.5
    smooth_sphere(f"ped_fig{i}", r=0.45,
                  loc=(x, 0, 8.4), parent=parthenon_e, mat_=M_MARBLE_GOLD,
                  scale=(1, 1, 1.3))

# ============ 12 OLYMPIENS DIEUX STATUES MONUMENTALES (autour de Zeus central) ============
def make_god_statue(name, loc, robe_mat, hair_mat, skin_mat,
                    has_beard=False, beard_mat=M_BEARD_BROWN, attribute="none", facing=0):
    base = empty(name, loc)
    base.rotation_euler = (0, 0, facing)
    # Pedestal
    cyl(f"{name}_ped", r=0.65, depth=0.30, segs=20,
        loc=(0, 0, 0.15), parent=base, mat_=M_STONE)
    cyl(f"{name}_ped2", r=0.55, depth=0.10, segs=20,
        loc=(0, 0, 0.35), parent=base, mat_=M_MARBLE)
    # Legs
    for side_idx, side in enumerate((-1, 1)):
        cyl(f"{name}_leg{side_idx}", r=0.13, depth=0.85, segs=12,
            loc=(side*0.13, 0, 0.85), parent=base, mat_=skin_mat)
        # Foot (sandal)
        beveled_cube(f"{name}_foot{side_idx}", (0.18, 0.30, 0.06),
                     loc=(side*0.13, 0.06, 0.43), parent=base, mat_=M_BRONZE)
    # Robe drapée (long cone descending)
    smooth_cone(f"{name}_robe", r1=0.55, r2=0.30, depth=1.4, segs=18,
                loc=(0, 0, 1.20), parent=base, mat_=robe_mat)
    # Belt sash
    cyl(f"{name}_sash", r=0.42, depth=0.10, segs=18,
        loc=(0, 0, 1.85), parent=base, mat_=M_GOLD_BRIGHT)
    # Torso (musculaire)
    smooth_sphere(f"{name}_torso", r=0.42, loc=(0, 0, 2.20),
                  parent=base, mat_=skin_mat, scale=(1, 0.65, 1.1))
    # 2 chest muscles (if male)
    if has_beard or attribute in ("lightning", "hammer", "spear", "trident", "bow"):
        for side in (-1, 1):
            smooth_sphere(f"{name}_chest_{side}", r=0.18, loc=(side*0.20, -0.18, 2.30),
                          parent=base, mat_=skin_mat)
    # Neck
    cyl(f"{name}_neck", r=0.11, depth=0.18, segs=12,
        loc=(0, 0, 2.65), parent=base, mat_=skin_mat)
    # Head
    head_e = empty(f"{name}_head_e", (0, 0, 2.85), parent=base)
    smooth_sphere(f"{name}_head", r=0.22, segs=22, rings=14, loc=(0,0,0),
                  parent=head_e, mat_=skin_mat)
    # Eyes
    for side in (-1, 1):
        smooth_sphere(f"{name}_eye_{side}", r=0.03,
                      loc=(side*0.07, -0.18, 0.03), parent=head_e,
                      mat_=mat(f"{name}_ew", (1,1,1,1), 0, 0.3))
    # Nose
    smooth_cone(f"{name}_nose", r1=0.04, r2=0.02, depth=0.12, segs=8,
                loc=(0, -0.20, -0.03), parent=head_e, mat_=skin_mat).rotation_euler = (math.radians(60), 0, 0)
    # Hair flowing
    smooth_sphere(f"{name}_hair", r=0.25, loc=(0, 0.05, 0.10),
                  parent=head_e, mat_=hair_mat, scale=(1.05, 0.95, 0.85))
    # Long hair back (3 strands)
    for j in range(3):
        strand = beveled_cube(f"{name}_hair_b{j}", (0.06, 0.10, 0.4),
                              loc=((j-1)*0.10, 0.20, -0.05 - j*0.05),
                              parent=head_e, mat_=hair_mat)
        strand.rotation_euler = (math.radians(15), 0, math.radians((j-1)*5))
    # Beard
    if has_beard:
        smooth_sphere(f"{name}_beard1", r=0.15, loc=(0, -0.10, -0.15),
                      parent=head_e, mat_=beard_mat, scale=(1.3, 0.6, 1.5))
        for j in range(3):
            smooth_sphere(f"{name}_beard_b{j}", r=0.07 - j*0.015,
                          loc=(0, -0.12, -0.30 - j*0.10),
                          parent=head_e, mat_=beard_mat, scale=(1, 1, 1.2))
    # Laurel crown (gold leaves)
    for j in range(8):
        a = (j / 8.0) * math.pi * 2
        leaf = beveled_cube(f"{name}_laurel{j}", (0.04, 0.05, 0.12),
                            loc=(0.22*math.cos(a), 0.22*math.sin(a), 0.18),
                            parent=head_e, mat_=M_GOLD)
        leaf.rotation_euler = (math.radians(-30), 0, a)

    # ATTRIBUTE in right hand
    r_sh = empty(f"{name}_r_sh", (0.32, 0, 2.40), parent=base)
    cyl(f"{name}_r_up", r=0.10, depth=0.45, segs=10,
        loc=(0, 0, -0.22), parent=r_sh, mat_=skin_mat)
    r_el = empty(f"{name}_r_el", (0, 0, -0.46), parent=r_sh)
    cyl(f"{name}_r_fa", r=0.09, depth=0.40, segs=10,
        loc=(0, 0, -0.20), parent=r_el, mat_=skin_mat)
    r_hand = empty(f"{name}_r_hand", (0, 0, -0.42), parent=r_el)
    smooth_sphere(f"{name}_r_hand_g", r=0.09, loc=(0, 0, 0),
                  parent=r_hand, mat_=skin_mat)

    # Pose right arm based on attribute
    if attribute == "lightning":
        r_sh.rotation_euler = (math.radians(-160), 0, math.radians(-20))
        # Lightning bolt jagged zigzag
        bolt_e = empty(f"{name}_bolt_e", (0, 0, -0.10), parent=r_hand)
        for i in range(4):
            seg = beveled_cube(f"{name}_bolt{i}", (0.15, 0.06, 0.30), bevel_offset=0.02,
                              loc=((i%2)*0.15 - 0.075, 0, -0.20 - i*0.30),
                              parent=bolt_e, mat_=M_LIGHTNING)
            seg.rotation_euler = (0, 0, math.radians(((i%2)*30 - 15)))
    elif attribute == "spear":
        r_sh.rotation_euler = (math.radians(-90), 0, math.radians(-15))
        # Spear long
        spear_e = empty(f"{name}_spear_e", (0, 0, -0.05), parent=r_hand)
        cyl(f"{name}_spear_shaft", r=0.04, depth=2.5, segs=10,
            loc=(0, 0, 0), parent=spear_e, mat_=M_BRONZE)
        smooth_cone(f"{name}_spear_tip", r1=0.06, r2=0.005, depth=0.35, segs=10,
                    loc=(0, 0, 1.40), parent=spear_e, mat_=M_SPEAR)
    elif attribute == "lyre":
        r_sh.rotation_euler = (math.radians(-70), 0, math.radians(20))
        # Hold lyre
        lyre_e = empty(f"{name}_lyre_e", (0, 0, -0.20), parent=r_hand)
        beveled_cube(f"{name}_lyre_body", (0.28, 0.08, 0.35), bevel_offset=0.04,
                     loc=(0, 0, 0), parent=lyre_e, mat_=M_LYRE)
        for s in (-1, 1):
            beveled_cube(f"{name}_lyre_h_{s}", (0.04, 0.06, 0.25),
                         loc=(s*0.14, 0, 0.25), parent=lyre_e, mat_=M_LYRE)
        beveled_cube(f"{name}_lyre_x", (0.35, 0.04, 0.04), loc=(0, 0, 0.35),
                     parent=lyre_e, mat_=M_LYRE)
        # 4 strings
        for i in range(4):
            cyl(f"{name}_lyre_str{i}", r=0.005, depth=0.30, segs=4,
                loc=((i-1.5)*0.06, 0, 0.15), parent=lyre_e, mat_=M_GOLD)
    elif attribute == "bow":
        r_sh.rotation_euler = (math.radians(-90), 0, math.radians(-15))
        # Bow curved (2 cones forming arc)
        bow_e = empty(f"{name}_bow_e", (0, 0, -0.20), parent=r_hand)
        for side in (-1, 1):
            seg = smooth_cone(f"{name}_bow_s_{side}", r1=0.04, r2=0.02, depth=0.55, segs=10,
                             loc=(0, side*0.20, 0), parent=bow_e, mat_=M_BOW)
            seg.rotation_euler = (math.radians(side*30), 0, 0)
        # String
        cyl(f"{name}_bow_str", r=0.005, depth=1.0, segs=4,
            loc=(0.05, 0, 0), parent=bow_e, mat_=M_GOLD)
    elif attribute == "trident":
        r_sh.rotation_euler = (math.radians(-150), 0, math.radians(-20))
        trident_e = empty(f"{name}_trident_e", (0, 0, -0.05), parent=r_hand)
        cyl(f"{name}_trident_pole", r=0.05, depth=2.2, segs=12,
            loc=(0, 0, 0.6), parent=trident_e, mat_=M_TRIDENT)
        for side_idx, side in enumerate((-1, 0, 1)):
            prong = smooth_cone(f"{name}_pr_{side_idx}", r1=0.05, r2=0.005, depth=0.45, segs=10,
                               loc=(side*0.15, 0, 1.85), parent=trident_e, mat_=M_TRIDENT)
            if side != 0:
                prong.rotation_euler = (0, math.radians(side*8), 0)
    elif attribute == "hammer":
        r_sh.rotation_euler = (math.radians(-130), 0, math.radians(-20))
        ham_e = empty(f"{name}_ham_e", (0, 0, -0.10), parent=r_hand)
        # Handle
        cyl(f"{name}_ham_handle", r=0.05, depth=0.70, segs=10,
            loc=(0, 0, 0.30), parent=ham_e, mat_=M_BOW)
        # Head
        beveled_cube(f"{name}_ham_head", (0.35, 0.15, 0.18), bevel_offset=0.03,
                     loc=(0, 0, 0.70), parent=ham_e, mat_=M_HAMMER)
    elif attribute == "wine":
        r_sh.rotation_euler = (math.radians(-90), 0, math.radians(-15))
        cup_e = empty(f"{name}_cup_e", (0, 0, -0.15), parent=r_hand)
        cyl(f"{name}_cup", r=0.10, depth=0.15, segs=14,
            loc=(0, 0, 0), parent=cup_e, mat_=M_WINE_CUP)
        smooth_sphere(f"{name}_wine_l", r=0.09, loc=(0, 0, 0.04),
                      parent=cup_e, mat_=M_WINE, scale=(1, 1, 0.5))
    else:
        # default offering
        r_sh.rotation_euler = (math.radians(-50), 0, math.radians(-10))

    # Left arm down
    l_sh = empty(f"{name}_l_sh", (-0.32, 0, 2.40), parent=base)
    l_sh.rotation_euler = (math.radians(-15), 0, math.radians(15))
    cyl(f"{name}_l_up", r=0.10, depth=0.45, segs=10,
        loc=(0, 0, -0.22), parent=l_sh, mat_=skin_mat)
    cyl(f"{name}_l_fa", r=0.09, depth=0.40, segs=10,
        loc=(0, 0, -0.62), parent=l_sh, mat_=skin_mat)
    smooth_sphere(f"{name}_l_hand", r=0.09, loc=(0, 0, -0.82),
                  parent=l_sh, mat_=skin_mat)

    # Glow aura around god (subtle sphere)
    aura = smooth_sphere(f"{name}_aura", r=1.4, segs=20, rings=14,
                        loc=(0, 0, 1.8), parent=base, mat_=M_AURA,
                        scale=(1, 0.6, 1.2))
    aura["_phase"] = random.uniform(0, math.pi*2)
    return {"root": base, "head_e": head_e, "r_sh": r_sh, "aura": aura}

# 12 Olympians positions (circle radius 7)
god_specs = [
    ("zeus",     M_ROBE_PURPLE, M_HAIR_GOLDEN, M_SKIN_ZEUS, True, M_BEARD_WHITE, "lightning"),
    ("athena",   M_ROBE_WHITE,  M_HAIR_BLACK,  M_SKIN_GODDESS, False, M_BEARD_BROWN, "spear"),
    ("apollo",   M_ROBE_BLUE,   M_HAIR_GOLDEN, M_SKIN_GOD, False, M_BEARD_BROWN, "lyre"),
    ("artemis",  M_ROBE_GREEN,  M_HAIR_GOLDEN, M_SKIN_GODDESS, False, M_BEARD_BROWN, "bow"),
    ("ares",     M_ROBE_RED,    M_HAIR_BLACK,  M_SKIN_GOD, True,  M_BEARD_BROWN, "spear"),
    ("aphrodite", M_ROBE_ROSE,  M_HAIR_GOLDEN, M_SKIN_GODDESS, False, M_BEARD_BROWN, "none"),
    ("hermes",   M_ROBE_WHITE,  M_HAIR_BROWN,  M_SKIN_GOD, False, M_BEARD_BROWN, "none"),
    ("hephaestus", M_ROBE_GREY, M_HAIR_BROWN,  M_SKIN_GOD, True, M_BEARD_BROWN, "hammer"),
    ("dionysus", M_ROBE_PURPLE, M_HAIR_BLACK,  M_SKIN_GOD, True, M_BEARD_BROWN, "wine"),
    ("poseidon", M_ROBE_BLUE,   M_HAIR_GOLDEN, M_SKIN_ZEUS, True, M_BEARD_WHITE, "trident"),
    ("demeter",  M_ROBE_GREEN,  M_HAIR_GOLDEN, M_SKIN_GODDESS, False, M_BEARD_BROWN, "none"),
    ("hera",     M_ROBE_PURPLE, M_HAIR_BLACK,  M_SKIN_GODDESS, False, M_BEARD_BROWN, "none"),
]
gods = []
for gi, spec in enumerate(god_specs):
    name, robe, hair, skin, beard, beard_m, attr = spec
    angle = (gi / 12.0) * math.pi * 2
    rad = 7
    gx = rad * math.cos(angle)
    gy = rad * math.sin(angle)
    facing = angle + math.pi  # face center
    g = make_god_statue(name, (gx, gy, 0.5), robe, hair, skin,
                        has_beard=beard, beard_mat=beard_m,
                        attribute=attr, facing=facing)
    # Zeus center bigger
    if name == "zeus":
        # Move to center, scale larger
        g["root"].location = (0, 0, 0.5)
        g["root"].scale = (1.4, 1.4, 1.4)
    gods.append((name, g, attr))

# ============ PEGASUS (white winged horse flying) ============
pegasus_e = empty("pegasus", loc=(-14, 8, 16))
pegasus_e.rotation_euler = (0, 0, math.radians(-45))
# Body
smooth_sphere("peg_body", r=0.85, segs=22, rings=14, loc=(0,0,0),
              parent=pegasus_e, mat_=M_PEGASUS, scale=(2.0, 0.9, 1.0))
# Neck (curving forward+up)
neck_e = empty("peg_neck_e", (1.0, 0, 0.40), parent=pegasus_e)
for i in range(3):
    cyl(f"peg_neck{i}", r=0.25 - i*0.02, depth=0.40, segs=14,
        loc=(i*0.15, 0, 0.10*i + 0.20), parent=neck_e, mat_=M_PEGASUS)
# Head
smooth_sphere("peg_head", r=0.30, loc=(1.55, 0, 0.95),
              parent=pegasus_e, mat_=M_PEGASUS, scale=(1.6, 0.9, 0.9))
# Snout
smooth_sphere("peg_snout", r=0.15, loc=(1.85, 0, 0.85),
              parent=pegasus_e, mat_=M_PEGASUS)
# Ears
for side in (-1, 1):
    smooth_cone(f"peg_ear_{side}", r1=0.06, r2=0.005, depth=0.18, segs=8,
                loc=(1.40, side*0.12, 1.20), parent=pegasus_e, mat_=M_PEGASUS).rotation_euler = (math.radians(-20), math.radians(side*15), 0)
# Eyes
for side in (-1, 1):
    smooth_sphere(f"peg_eye_{side}", r=0.06,
                  loc=(1.55, side*0.18, 1.00), parent=pegasus_e, mat_=M_HYDRA_EYE)
# Mane (5 chunks flowing)
for i in range(5):
    smooth_sphere(f"peg_mane{i}", r=0.15 - i*0.015,
                  loc=(1.20 - i*0.20, 0, 0.95), parent=pegasus_e,
                  mat_=M_PEGASUS_MANE, scale=(1, 1.3, 1.0))
# 4 LEGS (galloping pose)
for x_idx, x in enumerate((-0.5, 0.5)):
    for y_idx, y in enumerate((-1, 1)):
        leg_e = empty(f"peg_leg_e{x_idx}_{y_idx}", (x, y*0.40, -0.20), parent=pegasus_e)
        leg_e.rotation_euler = (math.radians(15 if x_idx == 0 else -15), 0, 0)
        cyl(f"peg_leg{x_idx}_{y_idx}", r=0.10, depth=0.7, segs=10,
            loc=(0, 0, -0.35), parent=leg_e, mat_=M_PEGASUS)
        # Hoof
        cyl(f"peg_hoof{x_idx}_{y_idx}", r=0.12, depth=0.10, segs=12,
            loc=(0, 0, -0.75), parent=leg_e, mat_=M_PEGASUS_HOOF)
# Tail (5 long flowing)
for i in range(5):
    tail = smooth_sphere(f"peg_tail{i}", r=0.12 - i*0.01,
                        loc=(-1.20 - i*0.15, 0, 0 - i*0.05),
                        parent=pegasus_e, mat_=M_PEGASUS_MANE, scale=(1, 1.3, 1))
# WINGS HUGE (signature pegasus)
peg_wings = []
for side_idx, side in enumerate((-1, 1)):
    w_e = empty(f"peg_w_e{side_idx}", (0, side*0.45, 0.40), parent=pegasus_e)
    # Inner wing
    beveled_cube(f"peg_w_in{side_idx}", (1.2, 1.4, 0.06), bevel_offset=0.04,
                 loc=(0, side*0.7, 0.10), parent=w_e, mat_=M_PEGASUS)
    # Outer wing
    w_outer = empty(f"peg_w_out{side_idx}", (0, side*1.4, 0.20), parent=w_e)
    beveled_cube(f"peg_w_o{side_idx}", (1.0, 1.2, 0.05),
                 loc=(0, side*0.6, 0), parent=w_outer, mat_=M_PEGASUS)
    # Primary feathers
    for fi in range(4):
        beveled_cube(f"peg_prim{side_idx}_{fi}", (0.20, 0.60, 0.03),
                     loc=(0.4 - fi*0.30, side*1.2, 0), parent=w_outer, mat_=M_PEGASUS)
    peg_wings.append((w_e, w_outer, side))

# ============ CYCLOPE GÉANT (off to side) ============
cyclops_e = empty("cyclops", loc=(16, -10, 0))
cyclops_e.rotation_euler = (0, 0, math.radians(-110))
# Body massive
beveled_cube("cyc_torso", (1.4, 0.85, 2.2), bevel_offset=0.10,
             loc=(0, 0, 2.5), parent=cyclops_e, mat_=M_CYCLOPS_SKIN)
# 2 legs huge
for side_idx, side in enumerate((-1, 1)):
    cyl(f"cyc_leg{side_idx}", r=0.32, depth=1.6, segs=14,
        loc=(side*0.35, 0, 0.8), parent=cyclops_e, mat_=M_CYCLOPS_SKIN)
    cyl(f"cyc_calf{side_idx}", r=0.30, depth=0.40, segs=12,
        loc=(side*0.35, 0, 0.20), parent=cyclops_e, mat_=M_CYCLOPS_SKIN)
# Head with 1 EYE (signature cyclops)
cyc_head_e = empty("cyc_head_e", (0, 0, 4.0), parent=cyclops_e)
smooth_sphere("cyc_head", r=0.65, segs=24, rings=16, loc=(0,0,0),
              parent=cyc_head_e, mat_=M_CYCLOPS_SKIN)
# 1 GIANT EYE (signature)
smooth_sphere("cyc_eye_main", r=0.30, loc=(0, -0.55, 0.10),
              parent=cyc_head_e, mat_=mat("cyc_eye_w", (1,1,1,1), 0, 0.3))
smooth_sphere("cyc_iris", r=0.25, loc=(0, -0.70, 0.10),
              parent=cyc_head_e, mat_=M_CYCLOPS_EYE)
smooth_sphere("cyc_pupil", r=0.10, loc=(0, -0.78, 0.10),
              parent=cyc_head_e, mat_=mat("cyc_p", (0.05,0.05,0.05,1), 0, 0.5))
# Wild hair
for i in range(10):
    a = random.uniform(0, math.pi*2)
    smooth_sphere(f"cyc_hair{i}", r=0.20,
                  loc=(0.45*math.cos(a), 0.45*math.sin(a) + 0.2, 0.20),
                  parent=cyc_head_e, mat_=M_CYCLOPS_HAIR)
# 2 ARMS muscular
for side_idx, side in enumerate((-1, 1)):
    sh = empty(f"cyc_sh{side_idx}", (side*0.75, 0, 3.4), parent=cyclops_e)
    sh.rotation_euler = (math.radians(-20), 0, math.radians(side*-15))
    cyl(f"cyc_up{side_idx}", r=0.22, depth=0.85, segs=12,
        loc=(0, 0, -0.45), parent=sh, mat_=M_CYCLOPS_SKIN)
    cyl(f"cyc_fa{side_idx}", r=0.20, depth=0.80, segs=12,
        loc=(0, 0, -1.30), parent=sh, mat_=M_CYCLOPS_SKIN)
    # Fist
    beveled_cube(f"cyc_fist{side_idx}", (0.35, 0.30, 0.30),
                 loc=(0, 0, -1.85), parent=sh, mat_=M_CYCLOPS_SKIN)
# Beard wild
smooth_sphere("cyc_beard", r=0.35, loc=(0, -0.40, -0.40),
              parent=cyc_head_e, mat_=M_CYCLOPS_HAIR, scale=(1.3, 0.6, 1.5))

# ============ CENTAURE ============
centaur_e = empty("centaur", loc=(-12, -10, 0))
centaur_e.rotation_euler = (0, 0, math.radians(45))
# HORSE BODY (lower) :
# Torso horse
smooth_sphere("cent_horsebody", r=0.65, segs=22, rings=14, loc=(0, 0, 1.0),
              parent=centaur_e, mat_=M_CENT_HORSE, scale=(2.0, 1.0, 1.0))
# 4 horse legs
for x_idx, x in enumerate((-1, 1)):
    for y_idx, y in enumerate((-1, 1)):
        cyl(f"cent_leg{x_idx}_{y_idx}", r=0.12, depth=1.0, segs=10,
            loc=(x*0.5, y*0.35, 0.50), parent=centaur_e, mat_=M_CENT_HORSE)
        # Hoof
        cyl(f"cent_hoof{x_idx}_{y_idx}", r=0.13, depth=0.10, segs=12,
            loc=(x*0.5, y*0.35, -0.05), parent=centaur_e, mat_=M_PEGASUS_HOOF)
# Tail horse (long)
for i in range(5):
    cyl(f"cent_tail{i}", r=0.08 - i*0.01, depth=0.25, segs=10,
        loc=(-1.4 - i*0.10, 0, 0.95 - i*0.08), parent=centaur_e, mat_=M_CENT_HORSE)

# HUMAN UPPER BODY (front, rises from horse front)
human_e = empty("cent_human_e", (1.10, 0, 1.0), parent=centaur_e)
# Torso human
beveled_cube("cent_torso", (0.50, 0.32, 0.90), bevel_offset=0.06,
             loc=(0, 0, 0.65), parent=human_e, mat_=M_CENT_HUMAN)
# Head
cent_head_e = empty("cent_head", (0, 0, 1.20), parent=human_e)
smooth_sphere("cent_h", r=0.22, segs=20, rings=14, loc=(0,0,0),
              parent=cent_head_e, mat_=M_CENT_HUMAN)
# Beard
smooth_sphere("cent_beard", r=0.15, loc=(0, -0.10, -0.15),
              parent=cent_head_e, mat_=M_BEARD_BROWN, scale=(1.3, 0.6, 1.5))
# Hair
smooth_sphere("cent_hair", r=0.24, loc=(0, 0.05, 0.10),
              parent=cent_head_e, mat_=M_HAIR_BROWN, scale=(1.05, 0.95, 0.7))
# 2 arms with bow (centaur archer)
cent_l_sh = empty("cent_l_sh", (-0.25, 0, 0.95), parent=human_e)
cent_l_sh.rotation_euler = (math.radians(-100), 0, math.radians(20))
cyl("cent_l_up", r=0.08, depth=0.40, segs=10,
    loc=(0, 0, -0.20), parent=cent_l_sh, mat_=M_CENT_HUMAN)
cent_r_sh = empty("cent_r_sh", (0.25, 0, 0.95), parent=human_e)
cent_r_sh.rotation_euler = (math.radians(-90), 0, math.radians(-15))
cyl("cent_r_up", r=0.08, depth=0.40, segs=10,
    loc=(0, 0, -0.20), parent=cent_r_sh, mat_=M_CENT_HUMAN)
# Bow drawn
bow_e = empty("cent_bow_e", (0.40, -0.30, 0.65), parent=human_e)
for side in (-1, 1):
    seg = smooth_cone(f"cent_bow_s_{side}", r1=0.04, r2=0.02, depth=0.6, segs=10,
                     loc=(0, side*0.22, 0), parent=bow_e, mat_=M_BOW)
    seg.rotation_euler = (math.radians(side*30), 0, 0)
# Arrow
cyl("cent_arrow", r=0.02, depth=0.55, segs=8,
    loc=(0.10, 0, 0), parent=bow_e, mat_=M_BOW).rotation_euler = (0, math.radians(90), 0)
smooth_cone("cent_arrow_tip", r1=0.03, r2=0.005, depth=0.10, segs=8,
            loc=(0.40, 0, 0), parent=bow_e, mat_=M_SPEAR).rotation_euler = (0, math.radians(90), 0)

# ============ HYDRE 9 TÊTES (Lernaean Hydra) ============
hydra_e = empty("hydra", loc=(12, 10, 0))
hydra_e.rotation_euler = (0, 0, math.radians(-135))
# Body (massive serpentine)
smooth_sphere("hyd_body", r=1.5, segs=28, rings=18, loc=(0, 0, 1.5),
              parent=hydra_e, mat_=M_HYDRA_BODY, scale=(1.8, 1.5, 1.0))
# Belly lighter
smooth_sphere("hyd_belly", r=1.3, loc=(0, 0, 1.0),
              parent=hydra_e, mat_=M_HYDRA_BELLY, scale=(1.6, 1.2, 0.6))
# 4 legs/lizard legs
for x_idx, x in enumerate((-1, 1)):
    for y_idx, y in enumerate((-1, 1)):
        cyl(f"hyd_leg{x_idx}_{y_idx}", r=0.25, depth=1.0, segs=12,
            loc=(x*0.85, y*0.65, 0.55), parent=hydra_e, mat_=M_HYDRA_BODY)
        # 3 claws each
        for c in range(3):
            smooth_cone(f"hyd_claw{x_idx}_{y_idx}_{c}", r1=0.06, r2=0.005, depth=0.15, segs=8,
                        loc=(x*0.85 + (c-1)*0.06, y*0.85, 0.05),
                        parent=hydra_e, mat_=M_SPEAR).rotation_euler = (math.radians(60), 0, 0)
# Tail thick + long
for i in range(5):
    t = i / 4.0
    tail_seg = smooth_sphere(f"hyd_tail{i}", r=0.50 - i*0.07,
                            loc=(-1.5 - i*0.7, math.sin(t*math.pi)*0.5, 1.0 - i*0.10),
                            parent=hydra_e, mat_=M_HYDRA_BODY, scale=(1, 1.5, 0.9))
# 9 HEADS necks (each 6-seg serpentine)
heads = []
for hi in range(9):
    angle = (hi / 9.0) * math.pi - math.pi/2  # -90 to +90 front spread
    head_x = 0.5 + 3.0  # forward of body
    head_y = math.sin(angle) * 3.0
    head_z = 2.5 + math.cos(angle) * 1.5
    # Neck (parent chain)
    neck_root = empty(f"hyd_neck_root{hi}", (1.5, 0, 2.0), parent=hydra_e)
    neck_root.rotation_euler = (math.sin(angle) * 0.5, 0, angle)
    # 6 neck segments
    neck_segs = []
    parent_e = neck_root
    for s in range(6):
        s_e = empty(f"hyd_neck{hi}_se{s}", (0, 0.6, 0), parent=parent_e)
        neck_segs.append(s_e)
        # Segment
        r = 0.35 - s*0.035
        seg = smooth_cone(f"hyd_neck{hi}_s{s}", r1=r, r2=r-0.025, depth=0.6, segs=14,
                          loc=(0, 0, 0), parent=s_e, mat_=M_HYDRA_BODY)
        seg.rotation_euler = (math.radians(90), 0, 0)
        parent_e = s_e
    # Head end
    head_e_h = empty(f"hyd_head_e{hi}", (0, 0.4, 0), parent=parent_e)
    smooth_sphere(f"hyd_head{hi}", r=0.30, segs=20, rings=14, loc=(0, 0, 0),
                  parent=head_e_h, mat_=M_HYDRA_BODY, scale=(1.3, 1.5, 0.85))
    # Open mouth
    smooth_sphere(f"hyd_mouth{hi}", r=0.20, loc=(0, 0.30, -0.15),
                  parent=head_e_h, mat_=mat(f"hm_in{hi}", (0.30,0.10,0.10,1), 0, 0.5,
                                              emission=(0.30,0.10,0.10), emission_strength=2.0))
    # 4 fangs
    for f_idx in range(4):
        smooth_cone(f"hyd_fang{hi}_{f_idx}", r1=0.04, r2=0.005, depth=0.18, segs=8,
                    loc=((f_idx-1.5)*0.07, 0.35, -0.18),
                    parent=head_e_h, mat_=mat(f"hf{hi}_{f_idx}", (1,0.95,0.85,1), 0, 0.3)).rotation_euler = (math.radians(150), 0, 0)
    # Eyes glow yellow
    for side in (-1, 1):
        smooth_sphere(f"hyd_eye{hi}_{side}", r=0.06,
                      loc=(side*0.12, 0.20, 0.10), parent=head_e_h, mat_=M_HYDRA_EYE)
    # Forked tongue
    tongue_e = empty(f"hyd_tongue{hi}_e", (0, 0.50, -0.10), parent=head_e_h)
    for side in (-1, 1):
        fork = beveled_cube(f"hyd_tongue{hi}_{side}", (0.03, 0.20, 0.03),
                            loc=(side*0.04, 0.10, 0), parent=tongue_e, mat_=M_HYDRA_TONGUE)
    # Venom drip from mouth
    smooth_sphere(f"hyd_venom{hi}", r=0.05, loc=(0, 0.40, -0.25),
                  parent=head_e_h, mat_=M_HYDRA_VENOM)
    heads.append({"neck_root": neck_root, "segs": neck_segs, "head_e": head_e_h,
                  "tongue_e": tongue_e, "phase": hi * 0.4, "angle": angle})

# ============ 6 OLIVE TREES (signature Greece) ============
olive_trees = []
for i in range(6):
    a = (i / 6.0) * math.pi * 2 + 0.3
    rad = random.uniform(16, 22)
    tx = rad*math.cos(a)
    ty = rad*math.sin(a)
    tree_e = empty(f"olive{i}", (tx, ty, 0))
    # Trunk twisted
    for s in range(4):
        r1 = 0.30 - s*0.03
        seg = smooth_cone(f"ol_t{i}_{s}", r1=r1, r2=r1-0.02, depth=0.85, segs=14,
                          loc=(random.uniform(-0.1,0.1), random.uniform(-0.1,0.1),
                               (s+0.5)*0.85), parent=tree_e, mat_=M_OLIVE_TRUNK)
        seg.rotation_euler = (math.radians(random.uniform(-5,5)),
                              math.radians(random.uniform(-5,5)), 0)
    # Canopy (8 leaf clusters)
    for j in range(8):
        a2 = (j / 8.0) * math.pi * 2
        rad2 = random.uniform(1.2, 2.0)
        smooth_sphere(f"ol_can{i}_{j}", r=random.uniform(0.8, 1.2),
                      loc=(rad2*math.cos(a2), rad2*math.sin(a2),
                           3.6 + random.uniform(-0.4, 0.4)),
                      parent=tree_e, mat_=M_OLIVE_LEAF, scale=(1, 1, 0.7))
    # Olives (8 olive fruits émissifs)
    for j in range(8):
        a3 = random.uniform(0, math.pi*2)
        smooth_sphere(f"ol_fruit{i}_{j}", r=0.08,
                      loc=(1.2*math.cos(a3), 1.2*math.sin(a3),
                           3.5 + random.uniform(-0.3, 0.3)),
                      parent=tree_e, mat_=M_OLIVE, scale=(1, 1, 1.2))
    olive_trees.append(tree_e)

# ============ 200 OLIVE LEAVES floating ============
leaves = []
for i in range(200):
    lx = random.uniform(-28, 28)
    ly = random.uniform(-28, 28)
    lz = random.uniform(2, 15)
    leaf = beveled_cube(f"leaf{i}", (0.08, 0.16, 0.02), bevel_offset=0.01,
                       loc=(lx, ly, lz), mat_=M_OLIVE_LEAF)
    leaf.rotation_euler = (random.uniform(0, math.pi*2),
                           random.uniform(0, math.pi*2),
                           random.uniform(0, math.pi*2))
    leaf["_phase"] = random.uniform(0, math.pi*2)
    leaf["_base_x"] = lx; leaf["_base_y"] = ly; leaf["_base_z"] = lz
    leaf["_speed"] = random.uniform(0.4, 1.0)
    leaves.append(leaf)

# ============ ANIMATION ============
fps = 30; duration_s = 6; total_frames = fps * duration_s

# Zeus lightning crackle + Olympians subtle pulse
for name, g, attr in gods:
    phase = hash(name) % 100 * 0.05
    aura = g["aura"]
    for f in range(1, total_frames + 1, 4):
        t = (f - 1) / fps
        # Aura pulse
        s = 1 + math.sin(t * 1.5 + phase) * 0.10
        aura.scale = (s, 0.6 * s, 1.2 * s)
        aura.keyframe_insert("scale", frame=f)
        # Head subtle turn
        g["head_e"].rotation_euler = (math.sin(t * 0.6 + phase) * math.radians(3),
                                       0,
                                       math.sin(t * 0.4 + phase) * math.radians(8))
        g["head_e"].keyframe_insert("rotation_euler", frame=f)
    # Zeus right arm with lightning - extra crackle
    if attr == "lightning":
        for f in range(1, total_frames + 1, 2):
            t = (f - 1) / fps
            g["r_sh"].rotation_euler = (math.radians(-160) + math.sin(t * 3.0) * math.radians(10),
                                         0,
                                         math.radians(-20))
            g["r_sh"].keyframe_insert("rotation_euler", frame=f)
    # Athena spear oscillate
    if attr == "spear" and name == "athena":
        for f in range(1, total_frames + 1, 5):
            t = (f - 1) / fps
            g["r_sh"].rotation_euler = (math.radians(-90) + math.sin(t * 1.2) * math.radians(5),
                                         0,
                                         math.radians(-15))
            g["r_sh"].keyframe_insert("rotation_euler", frame=f)
    # Apollo lyre strum
    if attr == "lyre":
        for f in range(1, total_frames + 1, 3):
            t = (f - 1) / fps
            g["r_sh"].rotation_euler = (math.radians(-70) + math.sin(t * 4.0) * math.radians(10),
                                         0,
                                         math.radians(20))
            g["r_sh"].keyframe_insert("rotation_euler", frame=f)

# Pegasus flap + orbit
for f in range(1, total_frames + 1, 3):
    t = (f - 1) / fps
    flap = math.sin(t * 2.5) * math.radians(30)
    for w_e, w_out, side in peg_wings:
        w_e.rotation_euler = (side * flap, 0, 0)
        w_e.keyframe_insert("rotation_euler", frame=f)
        w_out.rotation_euler = (side * flap * 0.5, 0, 0)
        w_out.keyframe_insert("rotation_euler", frame=f)
    # Orbit
    angle = t * 0.4
    r = 14
    pegasus_e.location = (r * math.cos(angle), r * math.sin(angle) + 8,
                          16 + math.sin(t * 1.0) * 0.8)
    pegasus_e.rotation_euler = (0, 0, angle + math.pi/2)
    pegasus_e.keyframe_insert("location", frame=f)
    pegasus_e.keyframe_insert("rotation_euler", frame=f)

# Cyclops subtle bob + eye focus
for f in range(1, total_frames + 1, 5):
    t = (f - 1) / fps
    cyclops_e.location.z = math.sin(t * 1.0) * 0.05
    cyc_head_e.rotation_euler = (math.sin(t * 0.7) * math.radians(5), 0,
                                  math.sin(t * 0.5) * math.radians(15))
    cyclops_e.keyframe_insert("location", frame=f)
    cyc_head_e.keyframe_insert("rotation_euler", frame=f)

# Centaur subtle bob + bow draw
for f in range(1, total_frames + 1, 5):
    t = (f - 1) / fps
    centaur_e.location.z = math.sin(t * 1.5) * 0.05
    centaur_e.keyframe_insert("location", frame=f)
    cent_head_e.rotation_euler = (0, 0, math.sin(t * 0.6) * math.radians(10))
    cent_head_e.keyframe_insert("rotation_euler", frame=f)

# Hydra 9 heads turn différentielles
for hi, h in enumerate(heads):
    phase = h["phase"]
    base_angle = h["angle"]
    for f in range(1, total_frames + 1, 3):
        t = (f - 1) / fps
        # Root rotates side-to-side
        h["neck_root"].rotation_euler = (math.sin(base_angle) * 0.5 + math.sin(t * 1.5 + phase) * math.radians(15),
                                          math.cos(t * 1.0 + phase) * math.radians(5),
                                          base_angle + math.sin(t * 0.8 + phase) * math.radians(10))
        h["neck_root"].keyframe_insert("rotation_euler", frame=f)
        # Each segment wave
        for si, s_e in enumerate(h["segs"]):
            s_e.rotation_euler = (math.sin(t * 2.0 + phase + si*0.4) * math.radians(8),
                                   0,
                                   math.cos(t * 1.5 + phase + si*0.4) * math.radians(5))
            s_e.keyframe_insert("rotation_euler", frame=f)
        # Tongue flick
        h["tongue_e"].rotation_euler = (math.sin(t * 8.0 + phase) * math.radians(20), 0, 0)
        h["tongue_e"].keyframe_insert("rotation_euler", frame=f)

# Sun pulse
for f in range(1, total_frames + 1, 4):
    t = (f - 1) / fps
    s = 1 + math.sin(t * 1.0) * 0.06
    sun.scale = (s, s, s)
    sun.keyframe_insert("scale", frame=f)

# Clouds drift
for c_e in clouds:
    phase = c_e["_phase"]
    bx, by = c_e.location.x, c_e.location.y
    for f in range(1, total_frames + 1, 8):
        t = (f - 1) / fps
        c_e.location = (bx + math.sin(t * 0.3 + phase) * 0.8,
                        by + math.cos(t * 0.25 + phase) * 0.8,
                        c_e.location.z + math.sin(t * 0.4 + phase) * 0.3)
        c_e.keyframe_insert("location", frame=f)

# 200 leaves drift
for l in leaves:
    phase = l["_phase"]; speed = l["_speed"]
    bx, by, bz = l["_base_x"], l["_base_y"], l["_base_z"]
    for f in range(1, total_frames + 1, 6):
        t = (f - 1) / fps
        x = bx + math.sin(t * speed + phase) * 1.5
        y = by + math.cos(t * speed * 0.8 + phase) * 1.5
        z = bz + math.sin(t * speed * 0.6 + phase) * 1.0 - (t * 0.5) % 4.0
        l.location = (x, y, max(0.5, z))
        l.rotation_euler = (phase + t * 1.5, phase + t * 1.2, phase + t * 1.8)
        l.keyframe_insert("location", frame=f)
        l.keyframe_insert("rotation_euler", frame=f)

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
out_glb = os.path.join(out_dir, "pbr_olympus_proc.glb")

bpy.ops.object.select_all(action='SELECT')
bpy.ops.export_scene.gltf(
    filepath=out_glb, export_format='GLB',
    export_animations=True, export_apply=False, export_yup=True, use_selection=False,
)
size_mb = os.path.getsize(out_glb) / (1024 * 1024)
print(f"[proc_greek_olympus_pantheon] DONE → {out_glb} ({size_mb:.2f} MB)")
print("[proc_greek_olympus_pantheon] Parthenon + 26 ionic columns + 12 Olympians (Zeus+Athena+Apollo+Artemis+Ares+Aphrodite+Hermes+Hephaestus+Dionysus+Poseidon+Demeter+Hera) + Pegasus + Cyclops + Centaur + Hydre 9 têtes + 6 olive trees + 200 leaves + 8 clouds + 50 stars")
