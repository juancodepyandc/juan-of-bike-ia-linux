"""
proc_arctic_inuit_village.py — 208e procédural AuroraIA (72e qualité)
Village inuit arctique : igloos + chasseurs + huskies + ours polaire + phoques + caribou
APPLIQUE FEEDBACK CRITIQUE :
  1. UN SEUL ground propre (pas de sandwich de couches plates)
  2. NEIGE QUI TOMBE animée (particules thématiques obligatoires)
"""
import bpy, bmesh, math, random, os

random.seed(0xA2C71C208)

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
M_SKY_NIGHT = mat("sky", (0.06, 0.10, 0.22, 1.0), 0.0, 0.85, emission=(0.10,0.15,0.30), emission_strength=1.0)
M_MOON = mat("moon", (0.95, 0.95, 0.92, 1.0), 0.0, 0.25, emission=(0.95,0.95,0.92), emission_strength=18.0)
M_STAR = mat("star", (1.0, 1.0, 1.0, 1.0), 0.0, 0.05, emission=(1.0,1.0,1.0), emission_strength=16.0)
M_AURORA_GREEN = mat("aur_g", (0.20, 1.0, 0.55, 1.0), 0.0, 0.10, emission=(0.25,1.0,0.60), emission_strength=7.0, alpha=0.55)
M_AURORA_PURPLE = mat("aur_p", (0.70, 0.30, 1.0, 1.0), 0.0, 0.10, emission=(0.75,0.35,1.0), emission_strength=6.5, alpha=0.55)
M_AURORA_PINK = mat("aur_pk", (1.0, 0.45, 0.75, 1.0), 0.0, 0.10, emission=(1.0,0.50,0.78), emission_strength=6.0, alpha=0.55)

# ============ ONE clean snow ground - PAS DE COUCHES STACKED ============
M_SNOW = mat("snow", (0.92, 0.95, 0.98, 1.0), 0.0, 0.45, emission=(0.85,0.90,0.98), emission_strength=0.7)
M_SNOWFLAKE = mat("snowflake", (1.0, 1.0, 1.0, 1.0), 0.0, 0.10, emission=(1.0,1.0,1.0), emission_strength=10.0)

M_ICE = mat("ice", (0.65, 0.85, 0.95, 0.85), 0.4, 0.15, emission=(0.55,0.78,0.92), emission_strength=1.5, alpha=0.85)
M_ICE_DARK = mat("ice_d", (0.30, 0.50, 0.65, 1.0), 0.3, 0.30, emission=(0.25,0.45,0.60), emission_strength=0.5)
M_SEA = mat("sea", (0.10, 0.20, 0.35, 0.75), 0.5, 0.10, emission=(0.12,0.25,0.40), emission_strength=0.6, alpha=0.75)

# Inuit clothing - parkas fur
M_PARKA_BROWN = mat("parka_br", (0.45, 0.30, 0.18, 1.0), 0.0, 0.80, emission=(0.40,0.27,0.16), emission_strength=0.3)
M_PARKA_GREY = mat("parka_g", (0.55, 0.50, 0.45, 1.0), 0.0, 0.80, emission=(0.48,0.43,0.40), emission_strength=0.3)
M_PARKA_BLUE = mat("parka_b", (0.20, 0.30, 0.45, 1.0), 0.0, 0.75, emission=(0.18,0.27,0.40), emission_strength=0.3)
M_FUR_TRIM = mat("fur_trim", (0.85, 0.78, 0.65, 1.0), 0.0, 0.85, emission=(0.78,0.72,0.60), emission_strength=0.4)
M_SKIN_INUIT = mat("skin_i", (0.85, 0.65, 0.45, 1.0), 0.0, 0.60, emission=(0.75,0.58,0.40), emission_strength=0.3)
M_HAIR_BLACK = mat("hair", (0.06, 0.05, 0.04, 1.0), 0.0, 0.85)
M_BOOTS = mat("boots", (0.30, 0.18, 0.10, 1.0), 0.0, 0.78)

# Igloos
M_IGLOO_BLOCK = mat("igloo", (0.85, 0.90, 0.95, 1.0), 0.0, 0.55, emission=(0.78,0.85,0.92), emission_strength=0.6)
M_IGLOO_DARK = mat("igloo_d", (0.65, 0.72, 0.80, 1.0), 0.0, 0.65, emission=(0.55,0.62,0.72), emission_strength=0.4)
M_IGLOO_GLOW = mat("igloo_glow", (1.0, 0.75, 0.30, 1.0), 0.0, 0.15, emission=(1.0,0.80,0.35), emission_strength=12.0, alpha=0.7)

# Animals
M_HUSKY_WHITE = mat("husky_w", (0.95, 0.95, 0.92, 1.0), 0.0, 0.65, emission=(0.88,0.88,0.85), emission_strength=0.4)
M_HUSKY_GREY = mat("husky_g", (0.45, 0.45, 0.48, 1.0), 0.0, 0.70)
M_HUSKY_EYE = mat("husky_eye", (0.20, 0.60, 1.0, 1.0), 0.0, 0.15, emission=(0.25,0.70,1.0), emission_strength=5.0)

M_BEAR_WHITE = mat("bear", (0.95, 0.92, 0.85, 1.0), 0.0, 0.70, emission=(0.85,0.82,0.75), emission_strength=0.4)
M_BEAR_NOSE = mat("bear_n", (0.08, 0.06, 0.05, 1.0), 0.0, 0.40)
M_BEAR_EYE = mat("bear_eye", (0.10, 0.08, 0.05, 1.0), 0.0, 0.20, emission=(0.15,0.10,0.08), emission_strength=0.6)

M_SEAL = mat("seal", (0.35, 0.30, 0.28, 1.0), 0.0, 0.65, emission=(0.30,0.25,0.23), emission_strength=0.3)
M_SEAL_BELLY = mat("seal_b", (0.65, 0.60, 0.55, 1.0), 0.0, 0.65)

M_CARIBOU = mat("caribou", (0.55, 0.40, 0.28, 1.0), 0.0, 0.70, emission=(0.45,0.32,0.22), emission_strength=0.3)
M_CARIBOU_HORN = mat("caribou_h", (0.55, 0.45, 0.30, 1.0), 0.2, 0.50)

# Sled + harpoon
M_WOOD = mat("wood", (0.30, 0.18, 0.10, 1.0), 0.0, 0.75)
M_BONE = mat("bone", (0.92, 0.88, 0.78, 1.0), 0.0, 0.55, emission=(0.85,0.80,0.72), emission_strength=0.4)
M_ROPE = mat("rope", (0.55, 0.40, 0.25, 1.0), 0.0, 0.80)

# Fire (small)
M_FLAME = mat("flame", (1.0, 0.50, 0.10, 1.0), 0.0, 0.10, emission=(1.0,0.55,0.15), emission_strength=14.0)
M_FLAME_INNER = mat("flame_i", (1.0, 0.85, 0.30, 1.0), 0.0, 0.10, emission=(1.0,0.90,0.40), emission_strength=20.0)

# Rocks / snow drifts (organic geometry not flat layers)
M_ROCK = mat("rock", (0.35, 0.32, 0.30, 1.0), 0.0, 0.85)

# ============ SKY ============
sky = smooth_sphere("sky", r=95, segs=32, rings=20, loc=(0,0,0), mat_=M_SKY_NIGHT, scale=(1,1,0.65))
sky.scale = (1,1,0.65)

# MOON
moon = smooth_sphere("moon", r=3.0, loc=(-20, 35, 28), mat_=M_MOON)
# Moon halo
moon_halo = smooth_sphere("moon_halo", r=4.0, loc=(-20, 35, 28), mat_=M_MOON, scale=(1, 1, 1))

# 100 STARS twinkle
stars = []
for i in range(100):
    sx = random.uniform(-50, 50)
    sy = random.uniform(15, 45)
    sz = random.uniform(15, 38)
    star = smooth_sphere(f"star{i}", r=random.uniform(0.06, 0.14), segs=8, rings=6,
                        loc=(sx, sy, sz), mat_=M_STAR)
    star["_phase"] = random.uniform(0, math.pi*2)
    stars.append(star)

# AURORA BORÉALE (4 ribbons - signature)
aurora_ribbons = []
aurora_mats = [M_AURORA_GREEN, M_AURORA_PURPLE, M_AURORA_GREEN, M_AURORA_PINK]
for ri in range(4):
    rib_e = empty(f"aurora_e{ri}", (0, 30, 22 + ri * 3))
    for j in range(10):
        a = (j / 9.0) * math.pi - math.pi/2
        rib_y = 30 + math.sin(a * 3 + ri * 0.5) * 4
        rib_z = math.cos(a * 2 + ri * 0.4) * 3
        rib = beveled_cube(f"aurora{ri}_{j}", (7, 0.4, 5), bevel_offset=0.1,
                          loc=(a * 9, rib_y - 30, rib_z),
                          parent=rib_e, mat_=aurora_mats[ri])
        rib["_phase"] = j * 0.3 + ri * 0.4
    rib_e["_base_phase"] = ri * 0.5
    aurora_ribbons.append(rib_e)

# ============ ONE CLEAN SNOW GROUND (single plane, no layered sandwich) ============
# Single ground - bumpy via subdivided plane simulated by adding organic geometry on top
ground = beveled_cube("ground", (80, 80, 0.5), bevel_offset=0.08, loc=(0, 0, -0.25), mat_=M_SNOW)

# Organic snow drifts (3D bumps - NOT layered flat discs)
snow_drifts = []
for i in range(30):
    a = random.uniform(0, math.pi*2)
    rad = random.uniform(8, 30)
    sx = rad * math.cos(a)
    sy = rad * math.sin(a)
    drift = smooth_sphere(f"drift{i}", r=random.uniform(0.8, 2.0), segs=18, rings=12,
                          loc=(sx, sy, 0.0), mat_=M_SNOW,
                          scale=(random.uniform(1.2, 2.0),
                                 random.uniform(1.0, 1.8),
                                 random.uniform(0.20, 0.40)))
    drift.rotation_euler = (0, 0, random.uniform(0, math.pi*2))
    snow_drifts.append(drift)

# Scattered rocks (10) - organic 3D not flat
for i in range(10):
    a = random.uniform(0, math.pi*2)
    rad = random.uniform(15, 32)
    smooth_sphere(f"rock{i}", r=random.uniform(0.6, 1.4),
                  loc=(rad*math.cos(a), rad*math.sin(a), 0.2),
                  mat_=M_ROCK,
                  scale=(random.uniform(0.8,1.2), random.uniform(0.8,1.2),
                         random.uniform(0.5,0.8))).rotation_euler = (random.uniform(-0.2, 0.2),
                                                                       random.uniform(-0.2, 0.2),
                                                                       random.uniform(0, math.pi*2))

# Frozen sea hole (one carved depression, not a stack) - simple cavity
sea_hole_e = empty("sea_hole", loc=(15, -10, 0))
# Sea water visible (single disc, slight depression)
cyl("sea_water", r=4.0, depth=0.30, segs=32,
    loc=(0, 0, -0.20), parent=sea_hole_e, mat_=M_SEA)
# Ice edge fragments (broken rim, organic)
for i in range(12):
    a = (i / 12.0) * math.pi * 2
    smooth_sphere(f"ice_frag{i}", r=random.uniform(0.30, 0.55),
                  loc=(4.0*math.cos(a), 4.0*math.sin(a), 0.15),
                  parent=sea_hole_e, mat_=M_ICE,
                  scale=(random.uniform(1.2, 1.8),
                         random.uniform(0.8, 1.4),
                         random.uniform(0.4, 0.8))).rotation_euler = (random.uniform(-0.4, 0.4),
                                                                        random.uniform(-0.4, 0.4),
                                                                        random.uniform(0, math.pi*2))

# ============ 4 IGLOOS authentique anatomy ============
def make_igloo(name, loc, scale=1.0, facing=0):
    base = empty(name, loc)
    base.rotation_euler = (0, 0, facing)
    # Dome (half sphere)
    dome = smooth_sphere(f"{name}_dome", r=2.0*scale, segs=24, rings=14,
                         loc=(0, 0, 0), parent=base, mat_=M_IGLOO_BLOCK,
                         scale=(1.0, 1.0, 0.65))
    # Carved snow blocks effect (8 visible rings stacked)
    for ri in range(6):
        z_off = ri * 0.30 * scale
        r_size = 2.0 * scale * math.cos(ri * 0.25)
        # 12 blocks per ring (visible block lines)
        for bi in range(12):
            ba = (bi / 12.0) * math.pi * 2
            bx = r_size * math.cos(ba) * 1.02
            by = r_size * math.sin(ba) * 1.02
            block = beveled_cube(f"{name}_block{ri}_{bi}",
                                 (0.55*scale, 0.05*scale, 0.20*scale),
                                 bevel_offset=0.02,
                                 loc=(bx, by, z_off + 0.10), parent=base, mat_=M_IGLOO_DARK)
            block.rotation_euler = (0, 0, ba)
    # Entrance tunnel (cylinder forward)
    tunnel_e = empty(f"{name}_tunnel_e", (0, -2.0*scale, 0.05), parent=base)
    cyl(f"{name}_tunnel", r=0.55*scale, depth=1.2*scale, segs=16,
        loc=(0, -0.6*scale, 0.55*scale), parent=tunnel_e, mat_=M_IGLOO_BLOCK).rotation_euler = (math.radians(90), 0, 0)
    # Inner glow visible (warm interior light)
    smooth_sphere(f"{name}_glow", r=0.40*scale, loc=(0, -2.4*scale, 0.55*scale),
                  parent=base, mat_=M_IGLOO_GLOW)
    return base

igloos = []
igloo_positions = [(-8, 5, 1.0, 0),
                   (-3, 8, 0.95, math.radians(30)),
                   (3, 7, 1.05, math.radians(-15)),
                   (8, 10, 0.9, math.radians(45))]
for i, (ix, iy, sc, fac) in enumerate(igloo_positions):
    igl = make_igloo(f"igloo{i}", (ix, iy, 0), scale=sc, facing=fac)
    igloos.append(igl)

# ============ 4 INUIT HUNTERS anatomy authentique ============
def make_inuit(name, loc, parka_mat, action="stand", facing=0, has_harpoon=False, scale=1.0):
    base = empty(name, loc)
    base.rotation_euler = (0, 0, facing)
    # Legs (covered in fur pants)
    for side_idx, side in enumerate((-1, 1)):
        cyl(f"{name}_leg{side_idx}", r=0.13*scale, depth=0.85*scale, segs=10,
            loc=(side*0.14*scale, 0, 0.42*scale), parent=base, mat_=parka_mat)
        # Big snow boots (mukluks)
        beveled_cube(f"{name}_mukluk{side_idx}", (0.22*scale, 0.32*scale, 0.20*scale), bevel_offset=0.04,
                     loc=(side*0.14*scale, 0.04*scale, 0.10*scale), parent=base, mat_=M_BOOTS)
        # Fur cuffs on boots
        cyl(f"{name}_boot_cuff{side_idx}", r=0.15*scale, depth=0.08*scale, segs=12,
            loc=(side*0.14*scale, 0, 0.21*scale), parent=base, mat_=M_FUR_TRIM)
    # Body parka (rounded chunky fur coat)
    smooth_sphere(f"{name}_torso", r=0.45*scale, segs=22, rings=14,
                  loc=(0, 0, 1.30*scale), parent=base, mat_=parka_mat,
                  scale=(1.2, 0.85, 1.5))
    # Fur trim bottom of parka
    cyl(f"{name}_parka_bottom", r=0.50*scale, depth=0.12*scale, segs=18,
        loc=(0, 0, 0.92*scale), parent=base, mat_=M_FUR_TRIM)
    # Hood (large fur-trimmed) - signature Inuit parka
    hood_e = empty(f"{name}_hood_e", (0, 0.10*scale, 1.95*scale), parent=base)
    # Hood opening rim (large fur ruff)
    cyl(f"{name}_hood_ruff", r=0.32*scale, depth=0.18*scale, segs=20,
        loc=(0, 0, 0), parent=hood_e, mat_=M_FUR_TRIM)
    # Hood back dome
    smooth_sphere(f"{name}_hood_back", r=0.28*scale, loc=(0, 0.10*scale, 0.10*scale),
                  parent=hood_e, mat_=parka_mat, scale=(1, 1, 1.1))
    # Face inside hood
    head_e = empty(f"{name}_head_e", (0, -0.10*scale, 0), parent=hood_e)
    smooth_sphere(f"{name}_head", r=0.16*scale, segs=18, rings=12, loc=(0, 0, 0),
                  parent=head_e, mat_=M_SKIN_INUIT)
    # Eyes (almond)
    for side in (-1, 1):
        smooth_sphere(f"{name}_eye{side}", r=0.025*scale,
                      loc=(side*0.06*scale, -0.13*scale, 0.02*scale), parent=head_e,
                      mat_=mat(f"{name}_ew{side}", (0.05,0.05,0.05,1), 0, 0.5))
    # Cheeks rosy
    for side in (-1, 1):
        smooth_sphere(f"{name}_cheek{side}", r=0.03*scale,
                      loc=(side*0.10*scale, -0.10*scale, -0.05*scale), parent=head_e,
                      mat_=mat(f"{name}_ch{side}", (0.85,0.50,0.50,1), 0, 0.6,
                                emission=(0.85,0.50,0.50), emission_strength=0.3))
    # Nose
    smooth_sphere(f"{name}_nose", r=0.025*scale, loc=(0, -0.15*scale, -0.03*scale),
                  parent=head_e, mat_=M_SKIN_INUIT)
    # 2 arms
    arm_poses = {
        "stand": [(math.radians(-15), 0), (math.radians(-15), 0)],
        "harpoon": [(math.radians(-90), -30), (math.radians(-90), 20)],
        "wave": [(math.radians(-160), -10), (math.radians(-15), 0)],
        "hold": [(math.radians(-60), -10), (math.radians(-60), 10)],
    }
    pose = arm_poses.get(action, arm_poses["stand"])
    arms_e = {}
    for side_idx, side in enumerate((-1, 1)):
        sh = empty(f"{name}_sh{side_idx}", (side*0.32*scale, 0, 1.65*scale), parent=base)
        rx, rz = pose[side_idx]
        sh.rotation_euler = (rx, 0, math.radians(side*-15 + rz))
        cyl(f"{name}_up{side_idx}", r=0.10*scale, depth=0.40*scale, segs=10,
            loc=(0, 0, -0.20*scale), parent=sh, mat_=parka_mat)
        el = empty(f"{name}_el{side_idx}", (0, 0, -0.42*scale), parent=sh)
        el.rotation_euler = (math.radians(30 if side==-1 else 40), 0, 0)
        cyl(f"{name}_fa{side_idx}", r=0.09*scale, depth=0.38*scale, segs=10,
            loc=(0, 0, -0.18*scale), parent=el, mat_=parka_mat)
        # Mitten (fur)
        smooth_sphere(f"{name}_mitten{side_idx}", r=0.10*scale,
                      loc=(0, 0, -0.42*scale), parent=el, mat_=M_FUR_TRIM)
        arms_e[f"sh{side_idx}"] = sh
        arms_e[f"el{side_idx}"] = el
    # Harpoon if hunter
    if has_harpoon:
        harpoon_e = empty(f"{name}_harpoon_e", (0, 0, -0.15*scale), parent=arms_e["el1"])
        # Long wooden shaft
        cyl(f"{name}_harpoon_shaft", r=0.04*scale, depth=2.2*scale, segs=10,
            loc=(0, 0, 1.0*scale), parent=harpoon_e, mat_=M_WOOD)
        # Bone tip
        smooth_cone(f"{name}_harpoon_tip", r1=0.08*scale, r2=0.005, depth=0.30*scale, segs=10,
                    loc=(0, 0, 2.20*scale), parent=harpoon_e, mat_=M_BONE)
        # 2 barbs (signature harpoon)
        for side in (-1, 1):
            barb = beveled_cube(f"{name}_barb{side}", (0.04*scale, 0.08*scale, 0.12*scale),
                               loc=(side*0.06*scale, 0, 2.05*scale), parent=harpoon_e, mat_=M_BONE)
            barb.rotation_euler = (0, math.radians(side*30), 0)
        # Rope wrapped
        for i in range(3):
            cyl(f"{name}_rope_wrap{i}", r=0.05*scale, depth=0.04*scale, segs=12,
                loc=(0, 0, 0.5 + i*0.6), parent=harpoon_e, mat_=M_ROPE)
    return {"root": base, "head_e": head_e, "hood_e": hood_e,
            "sh0": arms_e["sh0"], "sh1": arms_e["sh1"]}

inuits = []
inuit_specs = [
    ("inuit1", (-5, -3, 0), M_PARKA_BROWN, "harpoon", math.radians(-60), True),
    ("inuit2", (0, -5, 0), M_PARKA_GREY, "wave", math.radians(0), False),
    ("inuit3", (5, -2, 0), M_PARKA_BLUE, "hold", math.radians(45), False),
    ("inuit4", (10, -8, 0), M_PARKA_BROWN, "harpoon", math.radians(-90), True),
]
for spec in inuit_specs:
    name, loc, parka, action, fac, harpoon = spec
    i = make_inuit(name, loc, parka, action=action, facing=fac, has_harpoon=harpoon)
    inuits.append(i)

# ============ 6 HUSKIES (sled dogs) ============
def make_husky(name, loc, white_color=True, facing=0):
    base = empty(name, loc)
    base.rotation_euler = (0, 0, facing)
    body_color = M_HUSKY_WHITE if white_color else M_HUSKY_GREY
    # Body
    smooth_sphere(f"{name}_body", r=0.35, segs=20, rings=14, loc=(0, 0, 0.55),
                  parent=base, mat_=body_color, scale=(2.0, 1.0, 1.0))
    # White belly under
    smooth_sphere(f"{name}_belly", r=0.32, loc=(0, 0, 0.40),
                  parent=base, mat_=M_HUSKY_WHITE, scale=(1.7, 0.9, 0.55))
    # 4 legs
    for x_idx, x in enumerate((-1, 1)):
        for y_idx, y in enumerate((-1, 1)):
            cyl(f"{name}_leg{x_idx}{y_idx}", r=0.08, depth=0.55, segs=10,
                loc=(x*0.35, y*0.22, 0.27), parent=base, mat_=body_color)
            # Paw (white)
            smooth_sphere(f"{name}_paw{x_idx}{y_idx}", r=0.09, loc=(x*0.35, y*0.22, 0),
                          parent=base, mat_=M_HUSKY_WHITE, scale=(1, 1.2, 0.7))
    # Neck
    cyl(f"{name}_neck", r=0.13, depth=0.20, segs=12,
        loc=(0.70, 0, 0.65), parent=base, mat_=body_color).rotation_euler = (0, math.radians(70), 0)
    # Head
    head_e = empty(f"{name}_head_e", (0.85, 0, 0.85), parent=base)
    smooth_sphere(f"{name}_h", r=0.16, segs=18, rings=12, loc=(0, 0, 0),
                  parent=head_e, mat_=body_color, scale=(1.5, 0.9, 0.95))
    # Snout
    smooth_sphere(f"{name}_snout", r=0.10, loc=(0.18, 0, -0.04),
                  parent=head_e, mat_=M_HUSKY_WHITE, scale=(1.2, 0.85, 0.85))
    # Nose
    smooth_sphere(f"{name}_nose", r=0.03, loc=(0.27, 0, -0.02),
                  parent=head_e, mat_=mat(f"{name}_n", (0.10,0.08,0.06,1), 0, 0.5))
    # 2 pointed ears
    for side in (-1, 1):
        ear = smooth_cone(f"{name}_ear{side}", r1=0.06, r2=0.005, depth=0.15, segs=8,
                         loc=(side*0.08, 0.04, 0.18), parent=head_e, mat_=body_color)
        ear.rotation_euler = (math.radians(-5), math.radians(side*15), 0)
    # 2 ICE BLUE EYES (signature husky)
    for side in (-1, 1):
        smooth_sphere(f"{name}_eye{side}", r=0.04, loc=(side*0.07, -0.12, 0.05),
                      parent=head_e, mat_=M_HUSKY_EYE)
    # Tail (curled up)
    tail_e = empty(f"{name}_tail_e", (-0.70, 0, 0.60), parent=base)
    for i in range(3):
        a = i * 0.6
        cyl(f"{name}_tail{i}", r=0.06 - i*0.01, depth=0.18, segs=10,
            loc=(0.10*math.sin(a), 0, 0.10*math.cos(a) + i*0.10),
            parent=tail_e, mat_=body_color)
    return {"root": base, "head_e": head_e, "tail": tail_e}

huskies = []
husky_pos = [(-7, 0, 0, True, math.radians(0)),
             (-6, 1.5, 0, False, math.radians(15)),
             (-4, -1, 0, True, math.radians(-10)),
             (-3, 1, 0, False, math.radians(20)),
             (-1, 0, 0, True, math.radians(0)),
             (0, 2, 0, False, math.radians(-15))]
for i, (hx, hy, hz, w, fac) in enumerate(husky_pos):
    h = make_husky(f"husky{i}", (hx, hy, hz), white_color=w, facing=fac)
    huskies.append(h)

# ============ SLED (sled with reins to huskies) ============
sled_e = empty("sled", loc=(2, 0, 0))
# 2 runners
for side in (-1, 1):
    cyl(f"sled_runner_{side}", r=0.04, depth=2.5, segs=10,
        loc=(0, side*0.40, 0.10), parent=sled_e, mat_=M_WOOD).rotation_euler = (0, math.radians(90), 0)
# Runner tip curved
for side in (-1, 1):
    cyl(f"sled_runner_tip_{side}", r=0.04, depth=0.35, segs=10,
        loc=(-1.40, side*0.40, 0.25), parent=sled_e, mat_=M_WOOD).rotation_euler = (0, math.radians(60), 0)
# Floor
beveled_cube("sled_floor", (1.8, 0.85, 0.05), loc=(0, 0, 0.20), parent=sled_e, mat_=M_WOOD)
# Crossbars (5)
for i in range(5):
    beveled_cube(f"sled_cross{i}", (0.04, 0.9, 0.04), loc=(-0.7 + i*0.35, 0, 0.18),
                 parent=sled_e, mat_=M_WOOD)
# Cargo (bundled fur pack)
smooth_sphere("sled_cargo", r=0.35, loc=(0.30, 0, 0.45),
              parent=sled_e, mat_=M_PARKA_BROWN, scale=(1.5, 1.0, 0.8))
# Rope to huskies
cyl("sled_rope", r=0.02, depth=8, segs=8,
    loc=(-3.5, 0, 0.30), parent=sled_e, mat_=M_ROPE).rotation_euler = (0, math.radians(90), 0)

# ============ POLAR BEAR (massive, signature arctic) ============
bear_e = empty("bear", loc=(-15, 12, 0))
bear_e.rotation_euler = (0, 0, math.radians(-30))
# Body massive
smooth_sphere("bear_body", r=0.90, segs=24, rings=16, loc=(0, 0, 1.10),
              parent=bear_e, mat_=M_BEAR_WHITE, scale=(2.2, 1.1, 1.0))
# 4 legs heavy
for x_idx, x in enumerate((-1, 1)):
    for y_idx, y in enumerate((-1, 1)):
        cyl(f"bear_leg{x_idx}{y_idx}", r=0.25, depth=1.0, segs=14,
            loc=(x*0.75, y*0.50, 0.50), parent=bear_e, mat_=M_BEAR_WHITE)
        # Paw
        smooth_sphere(f"bear_paw{x_idx}{y_idx}", r=0.30, loc=(x*0.75, y*0.50 + 0.05, 0.05),
                      parent=bear_e, mat_=M_BEAR_WHITE, scale=(1.0, 1.3, 0.6))
        # Black claws
        for c in range(3):
            smooth_cone(f"bear_claw{x_idx}{y_idx}_{c}", r1=0.04, r2=0.005, depth=0.08, segs=6,
                        loc=(x*0.75 + (c-1)*0.10, y*0.50 + 0.30, 0.05),
                        parent=bear_e, mat_=M_BEAR_NOSE).rotation_euler = (math.radians(60), 0, 0)
# Head
head_b_e = empty("bear_head_e", (1.80, 0, 1.30), parent=bear_e)
smooth_sphere("bear_h", r=0.40, segs=22, rings=14, loc=(0, 0, 0),
              parent=head_b_e, mat_=M_BEAR_WHITE, scale=(1.2, 1.1, 1.0))
# Snout
smooth_sphere("bear_snout", r=0.30, loc=(0.25, 0, -0.10),
              parent=head_b_e, mat_=M_BEAR_WHITE, scale=(1.1, 1.0, 0.85))
# Nose black
smooth_sphere("bear_nose", r=0.08, loc=(0.50, 0, -0.10),
              parent=head_b_e, mat_=M_BEAR_NOSE)
# Mouth
beveled_cube("bear_mouth", (0.15, 0.05, 0.04), loc=(0.40, 0, -0.25),
             parent=head_b_e, mat_=M_BEAR_NOSE)
# 2 small eyes
for side in (-1, 1):
    smooth_sphere(f"bear_eye{side}", r=0.04, loc=(0.15, side*0.18, 0.10),
                  parent=head_b_e, mat_=M_BEAR_EYE)
# 2 round ears
for side in (-1, 1):
    smooth_sphere(f"bear_ear{side}", r=0.12, loc=(-0.10, side*0.25, 0.30),
                  parent=head_b_e, mat_=M_BEAR_WHITE)
    # Inner ear
    smooth_sphere(f"bear_ear_in{side}", r=0.08, loc=(-0.05, side*0.27, 0.30),
                  parent=head_b_e, mat_=mat(f"bei{side}", (0.85,0.65,0.55,1), 0, 0.7))

# ============ 3 SEALS (sea hole + on ice) ============
seals = []
seal_positions = [(15, -10, -0.05, math.radians(0)),    # near sea hole
                   (16, -8, 0.0, math.radians(60)),
                   (18, -11, 0.0, math.radians(-45))]
for i, (sx, sy, sz, fac) in enumerate(seal_positions):
    s_e = empty(f"seal{i}", (sx, sy, sz))
    s_e.rotation_euler = (0, 0, fac)
    # Body torpedo
    smooth_sphere(f"seal_body{i}", r=0.40, segs=20, rings=14, loc=(0, 0, 0.30),
                  parent=s_e, mat_=M_SEAL, scale=(2.5, 0.9, 0.85))
    # Belly lighter
    smooth_sphere(f"seal_belly{i}", r=0.34, loc=(0, 0, 0.18),
                  parent=s_e, mat_=M_SEAL_BELLY, scale=(2.3, 0.85, 0.50))
    # Head
    smooth_sphere(f"seal_h{i}", r=0.20, loc=(0.85, 0, 0.40),
                  parent=s_e, mat_=M_SEAL, scale=(1.0, 0.95, 0.95))
    # Snout
    smooth_sphere(f"seal_snout{i}", r=0.12, loc=(1.05, 0, 0.35),
                  parent=s_e, mat_=M_SEAL_BELLY)
    # Eyes large dark
    for side in (-1, 1):
        smooth_sphere(f"seal_eye{i}_{side}", r=0.05, loc=(0.85, side*0.13, 0.45),
                      parent=s_e, mat_=M_BEAR_EYE)
    # Nose
    smooth_sphere(f"seal_nose{i}", r=0.025, loc=(1.15, 0, 0.32),
                  parent=s_e, mat_=M_BEAR_NOSE)
    # Whiskers (3 each side)
    for side in (-1, 1):
        for j in range(3):
            beveled_cube(f"seal_wh{i}_{side}_{j}", (0.15, 0.005, 0.005),
                         loc=(0.95, side*0.12, 0.35 + (j-1)*0.03),
                         parent=s_e, mat_=M_FUR_TRIM)
    # 2 flippers front
    for side in (-1, 1):
        flipper = beveled_cube(f"seal_flipper_{i}_{side}", (0.30, 0.06, 0.10), bevel_offset=0.02,
                              loc=(0.30, side*0.35, 0.15), parent=s_e, mat_=M_SEAL)
        flipper.rotation_euler = (0, 0, math.radians(side*30))
    # Tail flippers (2 horizontal)
    for side in (-1, 1):
        tail_fl = beveled_cube(f"seal_tail{i}_{side}", (0.20, 0.30, 0.05), bevel_offset=0.02,
                              loc=(-0.95, side*0.10, 0.20), parent=s_e, mat_=M_SEAL)
        tail_fl.rotation_euler = (0, 0, math.radians(side*15))
    seals.append({"e": s_e, "phase": random.uniform(0, math.pi*2)})

# ============ 2 CARIBOUS (with antlers) ============
caribous = []
for ci in range(2):
    cx = -18 + ci * 3
    cy = -8 + ci * 2
    c_e = empty(f"caribou{ci}", (cx, cy, 0))
    c_e.rotation_euler = (0, 0, math.radians(-90 + ci*30))
    # Body
    smooth_sphere(f"caribou_body{ci}", r=0.55, segs=22, rings=14, loc=(0, 0, 1.30),
                  parent=c_e, mat_=M_CARIBOU, scale=(2.0, 1.0, 1.0))
    # 4 legs long thin
    for x_idx, x in enumerate((-1, 1)):
        for y_idx, y in enumerate((-1, 1)):
            cyl(f"caribou_leg{ci}_{x_idx}{y_idx}", r=0.08, depth=1.20, segs=12,
                loc=(x*0.55, y*0.30, 0.60), parent=c_e, mat_=M_CARIBOU)
            # Hooves
            cyl(f"caribou_hoof{ci}_{x_idx}{y_idx}", r=0.10, depth=0.08, segs=10,
                loc=(x*0.55, y*0.30, 0.04), parent=c_e, mat_=mat(f"hf{ci}_{x_idx}{y_idx}", (0.20,0.15,0.10,1), 0.3, 0.55))
    # Neck
    neck_e = empty(f"caribou_neck_e{ci}", (0.85, 0, 1.45), parent=c_e)
    cyl(f"caribou_neck{ci}", r=0.18, depth=0.50, segs=12,
        loc=(0.20, 0, 0.30), parent=neck_e, mat_=M_CARIBOU).rotation_euler = (0, math.radians(60), 0)
    # Head
    head_c_e = empty(f"caribou_head_e{ci}", (1.30, 0, 1.85), parent=c_e)
    smooth_sphere(f"caribou_h{ci}", r=0.22, segs=20, rings=14, loc=(0, 0, 0),
                  parent=head_c_e, mat_=M_CARIBOU, scale=(1.6, 0.95, 0.90))
    # Snout
    smooth_sphere(f"caribou_snout{ci}", r=0.15, loc=(0.20, 0, -0.05),
                  parent=head_c_e, mat_=M_SEAL_BELLY)
    # Ears
    for side in (-1, 1):
        smooth_cone(f"caribou_ear{ci}_{side}", r1=0.06, r2=0.005, depth=0.18, segs=8,
                    loc=(side*0.10, 0.05, 0.20), parent=head_c_e, mat_=M_CARIBOU).rotation_euler = (math.radians(-15), 0, 0)
    # Eyes
    for side in (-1, 1):
        smooth_sphere(f"caribou_eye{ci}_{side}", r=0.04, loc=(side*0.10, 0.10, 0.05),
                      parent=head_c_e, mat_=M_BEAR_EYE)
    # MASSIVE ANTLERS (signature caribou)
    for side in (-1, 1):
        antler_e = empty(f"caribou_antler{ci}_{side}", (side*0.08, 0.02, 0.30), parent=head_c_e)
        antler_e.rotation_euler = (math.radians(-15), math.radians(side*30), 0)
        # Main shaft
        for s in range(3):
            cyl(f"caribou_ant_s{ci}_{side}_{s}", r=0.05 - s*0.008, depth=0.40, segs=10,
                loc=(0, 0, s*0.40 + 0.20), parent=antler_e, mat_=M_CARIBOU_HORN).rotation_euler = (math.radians(-15*s), 0, 0)
        # 3 branches
        for b in range(3):
            ba = b * math.radians(40)
            branch_e = empty(f"caribou_br{ci}_{side}_{b}", (0, 0, 0.50 + b*0.30), parent=antler_e)
            branch_e.rotation_euler = (math.radians(-30), math.radians(side*45), ba)
            cyl(f"caribou_br_seg{ci}_{side}_{b}", r=0.025, depth=0.25, segs=8,
                loc=(0, 0, 0.13), parent=branch_e, mat_=M_CARIBOU_HORN)
            # Tip
            smooth_cone(f"caribou_br_tip{ci}_{side}_{b}", r1=0.025, r2=0.005, depth=0.10, segs=6,
                        loc=(0, 0, 0.30), parent=branch_e, mat_=M_CARIBOU_HORN)
    # Tail short
    cyl(f"caribou_tail{ci}", r=0.05, depth=0.20, segs=8,
        loc=(-0.95, 0, 1.40), parent=c_e, mat_=M_CARIBOU).rotation_euler = (math.radians(-30), 0, 0)
    caribous.append({"e": c_e, "head": head_c_e, "phase": random.uniform(0, math.pi*2)})

# ============ SMALL CAMPFIRE (between igloos) ============
fire_e = empty("campfire", loc=(0, 3, 0))
# Stone ring (6 stones)
for i in range(6):
    a = (i / 6.0) * math.pi * 2
    smooth_sphere(f"fire_stone{i}", r=0.20,
                  loc=(0.60*math.cos(a), 0.60*math.sin(a), 0.10),
                  parent=fire_e, mat_=M_ROCK)
# 3 logs
for i in range(3):
    a = (i / 3.0) * math.pi * 2
    log = cyl(f"fire_log{i}", r=0.10, depth=0.85, segs=10,
             loc=(0.05*math.cos(a), 0.05*math.sin(a), 0.15),
             parent=fire_e, mat_=M_WOOD)
    log.rotation_euler = (math.radians(90), 0, a)
# 4 flames
flames_fire = []
for i in range(4):
    a = (i / 4.0) * math.pi * 2
    rad = 0.15
    fx = rad * math.cos(a)
    fy = rad * math.sin(a)
    outer = smooth_cone(f"fire_fl_o{i}", r1=0.18, r2=0.02, depth=0.55, segs=10,
                       loc=(fx, fy, 0.45), parent=fire_e, mat_=M_FLAME)
    inner = smooth_cone(f"fire_fl_i{i}", r1=0.10, r2=0.01, depth=0.40, segs=10,
                       loc=(fx, fy, 0.50), parent=fire_e, mat_=M_FLAME_INNER)
    outer["_phase"] = i * 0.5
    inner["_phase"] = i * 0.5 + 0.3
    flames_fire.append((outer, inner))

# ============================================================
# ⭐ NEIGE QUI TOMBE ANIMÉE - 400 SNOWFLAKES (PARTICULE THÉMATIQUE OBLIGATOIRE)
# ============================================================
snowflakes = []
for i in range(400):
    sx = random.uniform(-40, 40)
    sy = random.uniform(-40, 40)
    sz = random.uniform(2, 25)
    sf = smooth_sphere(f"snowflake{i}", r=random.uniform(0.05, 0.12), segs=8, rings=6,
                      loc=(sx, sy, sz), mat_=M_SNOWFLAKE)
    sf["_phase"] = random.uniform(0, math.pi*2)
    sf["_speed"] = random.uniform(1.0, 2.5)
    sf["_base_x"] = sx; sf["_base_y"] = sy; sf["_base_z"] = sz
    sf["_drift_x"] = random.uniform(-0.6, 0.6)
    sf["_drift_y"] = random.uniform(-0.6, 0.6)
    snowflakes.append(sf)

# ============ ANIMATION ============
fps = 30; duration_s = 6; total_frames = fps * duration_s

# Stars twinkle
for star in stars:
    phase = star["_phase"]
    for f in range(1, total_frames + 1, 6):
        t = (f - 1) / fps
        s = 1 + math.sin(t * 3.0 + phase) * 0.35
        star.scale = (s, s, s)
        star.keyframe_insert("scale", frame=f)

# Aurora breathe + drift
for ar in aurora_ribbons:
    base_phase = ar["_base_phase"]
    base_z = ar.location.z
    for f in range(1, total_frames + 1, 4):
        t = (f - 1) / fps
        ar.location.z = base_z + math.sin(t * 0.6 + base_phase) * 1.0
        ar.rotation_euler = (math.sin(t * 0.4 + base_phase) * math.radians(4),
                              math.cos(t * 0.5 + base_phase) * math.radians(4),
                              0)
        s = 1 + math.sin(t * 0.8 + base_phase) * 0.1
        ar.scale = (s, s, s)
        ar.keyframe_insert("location", frame=f)
        ar.keyframe_insert("rotation_euler", frame=f)
        ar.keyframe_insert("scale", frame=f)

# Moon breathe
for f in range(1, total_frames + 1, 6):
    t = (f - 1) / fps
    s = 1 + math.sin(t * 0.6) * 0.04
    moon.scale = (s, s, s)
    moon.keyframe_insert("scale", frame=f)

# Inuits Z bob + head turn + arms motion
for inu in inuits:
    phase = hash(inu["root"].name) % 100 * 0.05
    base_z = inu["root"].location.z
    for f in range(1, total_frames + 1, 4):
        t = (f - 1) / fps
        inu["root"].location.z = base_z + math.sin(t * 1.0 + phase) * 0.03
        inu["root"].keyframe_insert("location", frame=f)
        inu["head_e"].rotation_euler = (math.sin(t * 0.7 + phase) * math.radians(5), 0,
                                          math.sin(t * 0.5 + phase) * math.radians(15))
        inu["head_e"].keyframe_insert("rotation_euler", frame=f)

# Huskies tail wave + head turn
for hk in huskies:
    base_z = hk["root"].location.z
    phase = hash(hk["root"].name) % 100 * 0.04
    for f in range(1, total_frames + 1, 4):
        t = (f - 1) / fps
        hk["root"].location.z = base_z + math.sin(t * 1.3 + phase) * 0.02
        hk["root"].keyframe_insert("location", frame=f)
        hk["tail"].rotation_euler = (math.sin(t * 3.5 + phase) * math.radians(15),
                                       0, math.sin(t * 2.5 + phase) * math.radians(25))
        hk["tail"].keyframe_insert("rotation_euler", frame=f)
        hk["head_e"].rotation_euler = (0, 0, math.sin(t * 1.0 + phase) * math.radians(20))
        hk["head_e"].keyframe_insert("rotation_euler", frame=f)

# Polar bear walk + head turn
for f in range(1, total_frames + 1, 4):
    t = (f - 1) / fps
    bear_e.location.z = math.sin(t * 1.0) * 0.04
    bear_e.keyframe_insert("location", frame=f)
    head_b_e.rotation_euler = (math.sin(t * 0.8) * math.radians(5), 0,
                                math.sin(t * 0.6) * math.radians(15))
    head_b_e.keyframe_insert("rotation_euler", frame=f)

# Seals subtle bob + head turn
for sl in seals:
    phase = sl["phase"]
    base_z = sl["e"].location.z
    for f in range(1, total_frames + 1, 5):
        t = (f - 1) / fps
        sl["e"].location.z = base_z + math.sin(t * 1.5 + phase) * 0.04
        sl["e"].keyframe_insert("location", frame=f)

# Caribous head bob + slight antler tilt
for cb in caribous:
    phase = cb["phase"]
    base_z = cb["e"].location.z
    for f in range(1, total_frames + 1, 5):
        t = (f - 1) / fps
        cb["e"].location.z = base_z + math.sin(t * 1.2 + phase) * 0.03
        cb["e"].keyframe_insert("location", frame=f)
        cb["head"].rotation_euler = (math.sin(t * 0.8 + phase) * math.radians(8), 0,
                                       math.sin(t * 0.6 + phase) * math.radians(12))
        cb["head"].keyframe_insert("rotation_euler", frame=f)

# Campfire flames
for outer, inner in flames_fire:
    p_o = outer["_phase"]; p_i = inner["_phase"]
    for f in range(1, total_frames + 1, 3):
        t = (f - 1) / fps
        s_o = 1 + math.sin(t * 6.0 + p_o) * 0.30
        outer.scale = (s_o, s_o, s_o)
        outer.keyframe_insert("scale", frame=f)
        s_i = 1 + math.sin(t * 8.0 + p_i) * 0.35
        inner.scale = (s_i, s_i, s_i)
        inner.keyframe_insert("scale", frame=f)

# ============================================================
# ⭐⭐⭐ NEIGE TOMBANTE (400 flocons) — PARTICULE THÉMATIQUE OBLIGATOIRE
# ============================================================
for sf in snowflakes:
    phase = sf["_phase"]; speed = sf["_speed"]
    bx, by, bz = sf["_base_x"], sf["_base_y"], sf["_base_z"]
    dx_v = sf["_drift_x"]; dy_v = sf["_drift_y"]
    for f in range(1, total_frames + 1, 4):
        t = (f - 1) / fps
        # Continuous falling Z descent + horizontal drift (signature snow fall)
        z = bz - (speed * t) % 28
        x = bx + dx_v * math.sin(t * 1.5 + phase)
        y = by + dy_v * math.cos(t * 1.3 + phase)
        # Tumble rotation
        sf.location = (x, y, max(-0.2, z))
        sf.rotation_euler = (phase + t * 1.5, phase + t * 1.2, phase + t * 1.8)
        sf.keyframe_insert("location", frame=f)
        sf.keyframe_insert("rotation_euler", frame=f)

# ============ EXPORT ============
out_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "public", "_pbr_test")
out_dir = os.path.normpath(out_dir)
os.makedirs(out_dir, exist_ok=True)
out_glb = os.path.join(out_dir, "pbr_arctic_proc.glb")

bpy.ops.object.select_all(action='SELECT')
bpy.ops.export_scene.gltf(
    filepath=out_glb, export_format='GLB',
    export_animations=True, export_apply=False, export_yup=True, use_selection=False,
)
size_mb = os.path.getsize(out_glb) / (1024 * 1024)
print(f"[proc_arctic_inuit_village] DONE → {out_glb} ({size_mb:.2f} MB)")
print("[proc_arctic_inuit_village] ONE GROUND + 30 organic drifts + 4 igloos + sea hole + 4 inuits + 6 huskies + sled + polar bear + 3 seals + 2 caribous + campfire + 400 FALLING SNOWFLAKES + 4 aurora + 100 stars + moon")
print("⭐ FEEDBACK FIX APPLIED: 1 single ground (organic drifts, NOT stacked layers) + thematic snow particles MANDATORY ⭐")
