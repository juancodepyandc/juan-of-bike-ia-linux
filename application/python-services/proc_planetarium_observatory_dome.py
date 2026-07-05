"""
proc_planetarium_observatory_dome.py — 196e procédural AuroraIA (60e qualité MILESTONE)
Grand planétarium dôme : coupole + télescope + 9 planètes + solar system + astronomes + sextants + 100 stars
"""
import bpy, bmesh, math, random, os

random.seed(0x507A2196)

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
M_DOME_OUTER = mat("dome_outer", (0.18, 0.20, 0.28, 1.0), 0.3, 0.45, emission=(0.15,0.18,0.25), emission_strength=0.5)
M_DOME_INNER = mat("dome_inner", (0.05, 0.05, 0.15, 1.0), 0.0, 0.85, emission=(0.10,0.08,0.20), emission_strength=1.0)
M_FLOOR = mat("floor", (0.20, 0.18, 0.20, 1.0), 0.3, 0.55, emission=(0.18,0.15,0.18), emission_strength=0.3)
M_FLOOR_PATTERN = mat("floor_p", (0.85, 0.78, 0.30, 1.0), 0.7, 0.30, emission=(0.75,0.68,0.28), emission_strength=0.6)
M_WALL = mat("wall", (0.45, 0.40, 0.35, 1.0), 0.2, 0.55, emission=(0.40,0.35,0.30), emission_strength=0.3)
M_BRASS = mat("brass", (0.85, 0.65, 0.25, 1.0), 0.92, 0.20, emission=(0.78,0.58,0.22), emission_strength=0.6)
M_GOLD = mat("gold", (1.0, 0.78, 0.25, 1.0), 0.95, 0.18, emission=(0.95,0.72,0.22), emission_strength=0.8)

# Telescope
M_TELE_TUBE = mat("tele_tube", (0.15, 0.15, 0.18, 1.0), 0.85, 0.30, emission=(0.10,0.10,0.13), emission_strength=0.3)
M_TELE_DETAIL = mat("tele_d", (0.55, 0.55, 0.58, 1.0), 0.85, 0.30, emission=(0.50,0.50,0.55), emission_strength=0.4)
M_TELE_LENS = mat("tele_lens", (0.40, 0.65, 0.85, 1.0), 0.0, 0.05, emission=(0.50,0.75,1.0), emission_strength=3.0, alpha=0.6)
M_TELE_TRIPOD = mat("tele_tri", (0.20, 0.20, 0.22, 1.0), 0.85, 0.45)

# Stars and celestials
M_STAR_BRIGHT = mat("star_bright", (1.0, 0.95, 0.80, 1.0), 0.0, 0.05, emission=(1.0,0.95,0.85), emission_strength=22.0)
M_STAR_WHITE = mat("star_white", (1.0, 1.0, 1.0, 1.0), 0.0, 0.05, emission=(1.0,1.0,1.0), emission_strength=18.0)
M_STAR_BLUE = mat("star_blue", (0.65, 0.80, 1.0, 1.0), 0.0, 0.05, emission=(0.70,0.85,1.0), emission_strength=20.0)
M_STAR_RED = mat("star_red", (1.0, 0.50, 0.40, 1.0), 0.0, 0.05, emission=(1.0,0.55,0.45), emission_strength=18.0)
M_CONSTELLATION = mat("const_line", (0.50, 0.80, 1.0, 1.0), 0.0, 0.10, emission=(0.55,0.85,1.0), emission_strength=8.0, alpha=0.5)
M_MILKY = mat("milky", (0.85, 0.80, 1.0, 1.0), 0.0, 0.20, emission=(0.85,0.80,1.0), emission_strength=4.5, alpha=0.4)

# Solar system planets
M_SUN = mat("sun_c", (1.0, 0.85, 0.30, 1.0), 0.0, 0.10, emission=(1.0,0.85,0.30), emission_strength=22.0)
M_MERCURY = mat("mercury", (0.55, 0.50, 0.45, 1.0), 0.0, 0.75, emission=(0.50,0.45,0.40), emission_strength=0.5)
M_VENUS = mat("venus", (0.95, 0.75, 0.45, 1.0), 0.0, 0.45, emission=(0.85,0.65,0.40), emission_strength=1.5)
M_EARTH = mat("earth", (0.30, 0.55, 0.85, 1.0), 0.0, 0.45, emission=(0.25,0.50,0.80), emission_strength=1.8)
M_EARTH_LAND = mat("earth_land", (0.30, 0.65, 0.25, 1.0), 0.0, 0.6, emission=(0.25,0.55,0.20), emission_strength=0.5)
M_MARS = mat("mars", (0.85, 0.40, 0.20, 1.0), 0.0, 0.55, emission=(0.75,0.35,0.18), emission_strength=1.2)
M_JUPITER = mat("jupiter", (0.85, 0.65, 0.40, 1.0), 0.0, 0.50, emission=(0.75,0.55,0.35), emission_strength=1.0)
M_JUPITER_BAND = mat("jup_band", (0.65, 0.40, 0.25, 1.0), 0.0, 0.55, emission=(0.55,0.35,0.20), emission_strength=0.8)
M_SATURN = mat("saturn", (0.90, 0.75, 0.50, 1.0), 0.0, 0.50, emission=(0.80,0.65,0.45), emission_strength=1.0)
M_SATURN_RING = mat("saturn_r", (0.85, 0.70, 0.45, 1.0), 0.3, 0.40, emission=(0.85,0.70,0.45), emission_strength=2.0, alpha=0.7)
M_URANUS = mat("uranus", (0.45, 0.75, 0.85, 1.0), 0.0, 0.45, emission=(0.40,0.70,0.80), emission_strength=1.2)
M_NEPTUNE = mat("neptune", (0.20, 0.35, 0.85, 1.0), 0.0, 0.45, emission=(0.18,0.30,0.80), emission_strength=1.5)
M_PLUTO = mat("pluto", (0.65, 0.55, 0.50, 1.0), 0.0, 0.70, emission=(0.55,0.45,0.42), emission_strength=0.4)
M_MOON_M = mat("moon_m", (0.85, 0.85, 0.78, 1.0), 0.0, 0.55, emission=(0.75,0.75,0.70), emission_strength=0.6)

# Orbital rings
M_ORBIT = mat("orbit", (0.45, 0.55, 0.70, 1.0), 0.0, 0.10, emission=(0.50,0.60,0.75), emission_strength=2.0, alpha=0.4)

# Satellites
M_SATELLITE = mat("sat", (0.85, 0.85, 0.88, 1.0), 0.92, 0.25, emission=(0.75,0.75,0.78), emission_strength=0.5)
M_SAT_PANEL = mat("sat_panel", (0.20, 0.30, 0.60, 1.0), 0.4, 0.30, emission=(0.25,0.35,0.65), emission_strength=2.5)
M_SAT_LIGHT = mat("sat_light", (1.0, 0.30, 0.30, 1.0), 0.0, 0.10, emission=(1.0,0.35,0.35), emission_strength=10.0)

# Astronomer
M_ASTRO_COAT = mat("astro_coat", (0.18, 0.15, 0.20, 1.0), 0.0, 0.60, emission=(0.15,0.12,0.18), emission_strength=0.3)
M_ASTRO_COAT_BLUE = mat("astro_coat_b", (0.15, 0.20, 0.35, 1.0), 0.0, 0.55, emission=(0.12,0.18,0.30), emission_strength=0.4)
M_ASTRO_PANTS = mat("astro_pants", (0.30, 0.25, 0.20, 1.0), 0.0, 0.70)
M_SKIN = mat("skin", (0.85, 0.75, 0.65, 1.0), 0.0, 0.55, emission=(0.75,0.65,0.55), emission_strength=0.25)
M_SKIN_DARK = mat("skin_d", (0.60, 0.45, 0.32, 1.0), 0.0, 0.6, emission=(0.50,0.38,0.28), emission_strength=0.25)
M_HAIR = mat("hair", (0.25, 0.15, 0.10, 1.0), 0.0, 0.75)
M_HAIR_GREY = mat("hair_grey", (0.55, 0.55, 0.55, 1.0), 0.0, 0.70)
M_GLASSES = mat("glasses", (0.10, 0.10, 0.12, 1.0), 0.4, 0.45, emission=(0.15,0.15,0.18), emission_strength=0.4)
M_LENS_G = mat("lens_g", (0.85, 0.95, 1.0, 0.5), 0.0, 0.05, emission=(0.80,0.90,1.0), emission_strength=1.0, alpha=0.5)

# Desk + maps + globe
M_DESK = mat("desk", (0.30, 0.18, 0.10, 1.0), 0.0, 0.70)
M_MAP_PAPER = mat("map", (0.92, 0.85, 0.65, 1.0), 0.0, 0.65, emission=(0.85,0.80,0.62), emission_strength=0.5)
M_MAP_INK = mat("map_ink", (0.20, 0.10, 0.05, 1.0), 0.0, 0.75)
M_MAP_LINES = mat("map_lines", (0.50, 0.70, 0.95, 1.0), 0.0, 0.40, emission=(0.45,0.65,0.95), emission_strength=2.0)
M_GLOBE_FRAME = mat("globe_frame", (0.85, 0.65, 0.25, 1.0), 0.95, 0.20, emission=(0.78,0.58,0.22), emission_strength=0.7)
M_GLOBE_SPHERE = mat("globe_s", (0.15, 0.20, 0.35, 1.0), 0.0, 0.30, emission=(0.20,0.30,0.50), emission_strength=2.0, alpha=0.65)

# Sextant
M_SEXTANT = mat("sextant", (0.85, 0.65, 0.25, 1.0), 0.92, 0.18, emission=(0.78,0.58,0.22), emission_strength=0.7)

# Smaller telescopes
M_SMALL_TELE = mat("small_tele", (0.25, 0.20, 0.18, 1.0), 0.85, 0.30, emission=(0.20,0.18,0.15), emission_strength=0.4)

# Particles
M_COSMIC = mat("cosmic", (0.85, 0.70, 1.0, 1.0), 0.0, 0.05, emission=(0.95,0.80,1.0), emission_strength=14.0)
M_NEBULA = mat("nebula", (0.85, 0.30, 0.85, 1.0), 0.0, 0.10, emission=(0.85,0.30,0.85), emission_strength=6.0, alpha=0.4)

# Lustre céleste
M_LUSTRE = mat("lustre", (1.0, 0.85, 0.40, 1.0), 0.95, 0.15, emission=(1.0,0.85,0.45), emission_strength=4.0)
M_LUSTRE_CRYSTAL = mat("lustre_c", (0.95, 0.95, 1.0, 0.7), 0.0, 0.05, emission=(0.90,0.92,1.0), emission_strength=5.0, alpha=0.7)

# ============ DOME STRUCTURE ============
# Outer dome (large hemisphere)
dome_outer = smooth_sphere("dome_out", r=25, segs=36, rings=20, loc=(0, 0, 0),
                            mat_=M_DOME_OUTER, scale=(1, 1, 0.65))
dome_outer.scale = (1, 1, 0.65)

# Inner dome (smaller, darker - for celestial projection)
dome_inner = smooth_sphere("dome_in", r=24, segs=36, rings=20, loc=(0, 0, 0),
                            mat_=M_DOME_INNER, scale=(1, 1, 0.65))
dome_inner.scale = (1, 1, 0.65)

# Floor (large disc)
floor = cyl("floor", r=24.5, depth=0.4, segs=48, loc=(0, 0, -0.2), mat_=M_FLOOR)
# Floor pattern (concentric rings + 8 radial lines)
for i in range(3):
    cyl(f"floor_ring{i}", r=5 + i*4, depth=0.05, segs=64,
        loc=(0, 0, 0.02), mat_=M_FLOOR_PATTERN)
for i in range(12):
    a = (i / 12.0) * math.pi * 2
    line = beveled_cube(f"floor_line{i}", (0.10, 18, 0.04),
                       loc=(0, 0, 0.03), mat_=M_FLOOR_PATTERN)
    line.rotation_euler = (0, 0, a)
# Zodiac symbols around outer ring (12)
for i in range(12):
    a = (i / 12.0) * math.pi * 2
    smooth_sphere(f"zodiac{i}", r=0.30, loc=(20*math.cos(a), 20*math.sin(a), 0.05),
                  mat_=M_GOLD, scale=(1, 1, 0.3))

# Wall ring (cylindrical base)
wall_ring = cyl("wall_ring", r=24.8, depth=4.5, segs=48,
                loc=(0, 0, 2.25), mat_=M_WALL)
# Replace top opening - use only outer cylinder + hide inner half later via segs
# Wall details: 8 columns inside ring
for i in range(8):
    a = (i / 8.0) * math.pi * 2
    cyl(f"wall_col{i}", r=0.35, depth=4.5, segs=18,
        loc=(22.5*math.cos(a), 22.5*math.sin(a), 2.25), mat_=M_WALL)
    smooth_sphere(f"wall_col_top{i}", r=0.40,
                  loc=(22.5*math.cos(a), 22.5*math.sin(a), 4.7), mat_=M_GOLD)

# DOME OPENING (slit at top - 2 sliding panels visible)
# Inner panel visible (representing partial opening)
for side in (-1, 1):
    panel = beveled_cube(f"dome_panel_{side}", (8, 1.0, 0.3), bevel_offset=0.05,
                        loc=(side*3, 0, 15), mat_=M_DOME_OUTER)
    panel.rotation_euler = (0, math.radians(side*30), 0)

# Sky visible through opening (large emissive plane)
sky_strip = beveled_cube("sky_strip", (5, 8, 0.1), bevel_offset=0.02,
                        loc=(0, 0, 16), mat_=M_DOME_INNER)

# ============ GREAT TELESCOPE (central, massive) ============
telescope_base = empty("telescope", loc=(0, 0, 0))

# Tripod (3 legs)
for i in range(3):
    a = (i / 3.0) * math.pi * 2
    leg_e = empty(f"tele_leg{i}", (1.4*math.cos(a), 1.4*math.sin(a), 0), parent=telescope_base)
    leg_e.rotation_euler = (math.radians(15*math.cos(a + math.pi/2)),
                            math.radians(-15*math.sin(a + math.pi/2)), 0)
    cyl(f"tele_leg_seg{i}", r=0.15, depth=4.5, segs=12,
        loc=(0, 0, 2.25), parent=leg_e, mat_=M_TELE_TRIPOD)
    # Foot pad
    cyl(f"tele_foot{i}", r=0.30, depth=0.10, segs=12,
        loc=(0, 0, 0), parent=leg_e, mat_=M_BRASS)
    # Brass ring middle
    cyl(f"tele_leg_ring{i}", r=0.20, depth=0.08, segs=14,
        loc=(0, 0, 2.0), parent=leg_e, mat_=M_BRASS)

# Mount platform (where tube pivots)
mount_e = empty("tele_mount", (0, 0, 4.0), parent=telescope_base)
# Equatorial mount (rotating)
mount_box = beveled_cube("mount_box", (0.7, 0.7, 0.7), bevel_offset=0.06,
                         loc=(0, 0, 0), parent=mount_e, mat_=M_TELE_DETAIL)
# Mount rings (gradés - graduated dial)
for r_size in (0.45, 0.50, 0.55):
    cyl(f"mount_ring_{r_size}", r=r_size, depth=0.05, segs=32,
        loc=(0, 0, 0.40), parent=mount_e, mat_=M_BRASS)
# Graduations (12 marks)
for i in range(12):
    a = (i / 12.0) * math.pi * 2
    beveled_cube(f"mount_grad{i}", (0.04, 0.04, 0.10),
                 loc=(0.55*math.cos(a), 0.55*math.sin(a), 0.45),
                 parent=mount_e, mat_=M_GOLD)

# TELESCOPE TUBE (large angled cylinder)
tube_pivot = empty("tube_pivot", (0, 0, 0.50), parent=mount_e)
tube_pivot.rotation_euler = (math.radians(45), 0, math.radians(20))  # angle skyward

# Main tube (long, 6m)
cyl("tube_main", r=0.55, depth=6.0, segs=24,
    loc=(0, 0, 1.5), parent=tube_pivot, mat_=M_TELE_TUBE)
# Brass bands (3 around tube)
for z in (0.5, 2.5, 4.5):
    cyl(f"tube_band_{z}", r=0.58, depth=0.10, segs=24,
        loc=(0, 0, z), parent=tube_pivot, mat_=M_BRASS)
# Front (objective lens end)
cyl("tube_obj", r=0.62, depth=0.25, segs=24,
    loc=(0, 0, 4.55), parent=tube_pivot, mat_=M_TELE_DETAIL)
# Objective lens (glowing blue)
cyl("tube_lens", r=0.50, depth=0.05, segs=24,
    loc=(0, 0, 4.70), parent=tube_pivot, mat_=M_TELE_LENS)
# Eyepiece end (smaller, opposite)
cyl("tube_eye", r=0.20, depth=0.30, segs=18,
    loc=(0, 0, -1.65), parent=tube_pivot, mat_=M_TELE_DETAIL)
# Eyepiece lens
cyl("tube_elens", r=0.15, depth=0.04, segs=18,
    loc=(0, 0, -1.82), parent=tube_pivot, mat_=M_TELE_LENS)
# Finder scope (small parallel scope)
finder_e = empty("finder", (0, -0.55, 2.0), parent=tube_pivot)
cyl("finder_tube", r=0.10, depth=1.0, segs=14,
    loc=(0, 0, 0), parent=finder_e, mat_=M_TELE_DETAIL)
cyl("finder_lens", r=0.10, depth=0.04, segs=14,
    loc=(0, 0, 0.55), parent=finder_e, mat_=M_TELE_LENS)
# Side handle for adjustment
cyl("adj_handle", r=0.04, depth=0.40, segs=10,
    loc=(0.65, 0, 1.5), parent=tube_pivot, mat_=M_BRASS).rotation_euler = (0, math.radians(90), 0)
smooth_sphere("adj_knob", r=0.08, loc=(0.85, 0, 1.5),
              parent=tube_pivot, mat_=M_GOLD)

# ============ SOLAR SYSTEM CENTERPIECE (orrery hanging from dome) ============
orrery_e = empty("orrery", loc=(8, 0, 11))
# Sun central (bright)
sun = smooth_sphere("orrery_sun", r=1.2, segs=28, rings=18, loc=(0, 0, 0),
                    parent=orrery_e, mat_=M_SUN)
# Sun halos
for i in range(3):
    halo = smooth_sphere(f"sun_halo{i}", r=1.4 + i*0.3, segs=20, rings=12,
                        loc=(0, 0, 0), parent=orrery_e, mat_=M_SUN, scale=(1, 1, 1))
    halo["_phase"] = i * 0.5

# Planets in orbit
planet_orbits = []
planet_specs = [
    ("mercury", 2.0, 0.18, M_MERCURY, 3.5),
    ("venus", 2.8, 0.30, M_VENUS, 2.5),
    ("earth", 3.6, 0.35, M_EARTH, 2.0),
    ("mars", 4.4, 0.25, M_MARS, 1.6),
    ("jupiter", 5.6, 0.65, M_JUPITER, 0.9),
    ("saturn", 7.0, 0.55, M_SATURN, 0.7),
    ("uranus", 8.2, 0.40, M_URANUS, 0.5),
    ("neptune", 9.2, 0.40, M_NEPTUNE, 0.4),
    ("pluto", 10.0, 0.18, M_PLUTO, 0.3),
]
for name, dist, size, m_, speed in planet_specs:
    p_e = empty(f"p_{name}_e", (0, 0, 0), parent=orrery_e)
    # Initial angle
    init_a = random.uniform(0, math.pi*2)
    p_e.rotation_euler = (0, 0, init_a)
    # Planet at distance
    planet = smooth_sphere(f"p_{name}", r=size, segs=22, rings=14,
                          loc=(dist, 0, 0), parent=p_e, mat_=m_)
    # Special: Earth gets land patches
    if name == "earth":
        for i in range(4):
            a = (i / 4.0) * math.pi * 2
            smooth_sphere(f"earth_land{i}", r=size*0.4,
                          loc=(dist + size*0.6*math.cos(a),
                               size*0.6*math.sin(a), 0),
                          parent=p_e, mat_=M_EARTH_LAND, scale=(0.6, 0.6, 0.5))
        # Moon
        moon_e = empty(f"earth_moon_e", (dist, 0, 0), parent=p_e)
        smooth_sphere("earth_moon", r=size*0.3, loc=(0.8, 0, 0),
                      parent=moon_e, mat_=M_MOON_M)
    # Jupiter gets bands
    if name == "jupiter":
        for i in range(3):
            cyl(f"jup_band{i}", r=size*1.02, depth=size*0.15, segs=24,
                loc=(dist, 0, (i-1)*size*0.3), parent=p_e, mat_=M_JUPITER_BAND)
    # Saturn gets RING
    if name == "saturn":
        ring1 = cyl("sat_ring1", r=size*1.8, depth=0.04, segs=40,
                   loc=(dist, 0, 0), parent=p_e, mat_=M_SATURN_RING)
        ring1.rotation_euler = (math.radians(20), 0, 0)
        ring2 = cyl("sat_ring2", r=size*2.2, depth=0.03, segs=40,
                   loc=(dist, 0, 0), parent=p_e, mat_=M_SATURN_RING)
        ring2.rotation_euler = (math.radians(20), 0, 0)
    # Orbital path ring
    cyl(f"orbit_ring_{name}", r=dist, depth=0.02, segs=80,
        loc=(0, 0, 0), parent=orrery_e, mat_=M_ORBIT)
    planet_orbits.append({"e": p_e, "speed": speed, "init_a": init_a, "dist": dist})

# 4 SATELLITES orbit smaller around sun
satellites = []
for i in range(4):
    a = (i / 4.0) * math.pi * 2
    sat_e = empty(f"sat_e{i}", (0, 0, 0), parent=orrery_e)
    sat_e.rotation_euler = (0, 0, a)
    # Body
    beveled_cube(f"sat_body{i}", (0.15, 0.15, 0.25), bevel_offset=0.02,
                 loc=(1.5, 0, 0), parent=sat_e, mat_=M_SATELLITE)
    # 2 solar panels
    for side in (-1, 1):
        beveled_cube(f"sat_panel{i}_{side}", (0.35, 0.04, 0.18),
                     loc=(1.5 + side*0.30, 0, 0), parent=sat_e, mat_=M_SAT_PANEL)
    # Antenna dish
    cyl(f"sat_dish{i}", r=0.08, depth=0.03, segs=12,
        loc=(1.5, 0, 0.18), parent=sat_e, mat_=M_SATELLITE)
    # Red light
    smooth_sphere(f"sat_light{i}", r=0.03, loc=(1.5, 0, -0.18),
                  parent=sat_e, mat_=M_SAT_LIGHT)
    satellites.append({"e": sat_e, "speed": random.uniform(1.5, 2.5)})

# ============ 100 STARS projected on dome ============
projected_stars = []
for i in range(100):
    a = random.uniform(0, math.pi*2)
    polar = random.uniform(0, math.pi/2.2)  # mostly upper dome
    r_dome = 23
    sx = r_dome * math.cos(a) * math.sin(polar)
    sy = r_dome * math.sin(a) * math.sin(polar)
    sz = r_dome * math.cos(polar)
    # Star color variation
    color_choice = random.random()
    if color_choice < 0.6:
        m_ = M_STAR_WHITE
    elif color_choice < 0.75:
        m_ = M_STAR_BLUE
    elif color_choice < 0.9:
        m_ = M_STAR_BRIGHT
    else:
        m_ = M_STAR_RED
    star = smooth_sphere(f"star{i}", r=random.uniform(0.08, 0.20), segs=10, rings=8,
                        loc=(sx, sy, sz), mat_=m_)
    star["_phase"] = random.uniform(0, math.pi*2)
    star["_speed"] = random.uniform(2.0, 4.5)
    projected_stars.append(star)

# ============ 8 CONSTELLATIONS (each = 5-8 connected stars + faint lines) ============
constellations = []
for ci in range(8):
    # Cluster center
    base_a = (ci / 8.0) * math.pi * 2
    base_polar = random.uniform(0.3, 1.1)
    r_dome = 22
    center_x = r_dome * math.cos(base_a) * math.sin(base_polar)
    center_y = r_dome * math.sin(base_a) * math.sin(base_polar)
    center_z = r_dome * math.cos(base_polar)
    c_e = empty(f"const_e{ci}", (0, 0, 0))
    # 5-7 stars in this constellation
    num_stars = random.randint(5, 7)
    star_positions = []
    for j in range(num_stars):
        spread = 2.5
        sx = center_x + random.uniform(-spread, spread)
        sy = center_y + random.uniform(-spread, spread)
        sz = center_z + random.uniform(-spread*0.5, spread*0.5)
        # Re-normalize roughly to dome surface
        d = math.sqrt(sx*sx + sy*sy + sz*sz)
        if d > 0:
            sx, sy, sz = sx/d * r_dome, sy/d * r_dome, sz/d * r_dome
        star = smooth_sphere(f"const{ci}_s{j}", r=0.22, segs=12, rings=8,
                            loc=(sx, sy, sz), parent=c_e, mat_=M_STAR_BRIGHT)
        star["_phase"] = random.uniform(0, math.pi*2)
        star_positions.append((sx, sy, sz))
    # Connect with thin lines (cylinders between consecutive)
    for j in range(len(star_positions) - 1):
        p1 = star_positions[j]; p2 = star_positions[j+1]
        # Midpoint
        mx = (p1[0]+p2[0])/2
        my = (p1[1]+p2[1])/2
        mz = (p1[2]+p2[2])/2
        # Length
        dx = p2[0]-p1[0]; dy = p2[1]-p1[1]; dz = p2[2]-p1[2]
        length = math.sqrt(dx*dx + dy*dy + dz*dz)
        line = cyl(f"const{ci}_l{j}", r=0.04, depth=length, segs=8,
                  loc=(mx, my, mz), parent=c_e, mat_=M_CONSTELLATION)
        # Orient
        yaw = math.atan2(dy, dx)
        pitch = math.atan2(math.sqrt(dx*dx + dy*dy), dz)
        line.rotation_euler = (0, pitch, yaw + math.pi/2)
    constellations.append(c_e)

# ============ MILKY WAY band (across upper dome) ============
milky_e = empty("milky_e", (0, 0, 0))
# 6 large emissive cloud blobs forming a band
for i in range(6):
    a = (i / 5.0) * math.pi - math.pi/2  # band across dome
    bx = 18 * math.cos(a + math.pi/3)
    by = 18 * math.sin(a + math.pi/3)
    bz = 12 + math.sin(a*2) * 3
    sm = smooth_sphere(f"milky{i}", r=random.uniform(3.0, 4.5),
                      loc=(bx, by, bz), parent=milky_e, mat_=M_MILKY,
                      scale=(2.0, 1.0, 0.8))
    sm["_phase"] = i * 0.4

# Nebulae (3 large colored emissive blobs)
nebulas = []
for i in range(3):
    a = random.uniform(0, math.pi*2)
    nx = 18 * math.cos(a)
    ny = 18 * math.sin(a)
    nz = random.uniform(8, 16)
    n = smooth_sphere(f"nebula{i}", r=random.uniform(2.0, 3.0),
                     loc=(nx, ny, nz), mat_=M_NEBULA,
                     scale=(1.5, 1.2, 1.0))
    n["_phase"] = random.uniform(0, math.pi*2)
    nebulas.append(n)

# ============ 6 ASTRONOMERS ============
def make_astronomer(name, loc, coat_mat, skin_mat, hair_mat, beard=False, glasses=True, pose="observe"):
    base = empty(name, loc)
    # Legs
    for side_idx, side in enumerate((-1, 1)):
        cyl(f"{name}_leg{side_idx}", r=0.12, depth=0.85, segs=10,
            loc=(side*0.15, 0, 0.42), parent=base, mat_=M_ASTRO_PANTS)
        # Shoe
        beveled_cube(f"{name}_shoe{side_idx}", (0.18, 0.30, 0.10),
                     loc=(side*0.15, 0.05, 0.05), parent=base, mat_=M_ASTRO_COAT)
    # Coat (long)
    beveled_cube(f"{name}_coat", (0.55, 0.35, 1.0), bevel_offset=0.05,
                 loc=(0, 0, 1.30), parent=base, mat_=coat_mat)
    # Coat tail (extending down)
    beveled_cube(f"{name}_coat_tail", (0.50, 0.30, 0.50),
                 loc=(0, 0, 0.65), parent=base, mat_=coat_mat)
    # Shirt collar (white)
    beveled_cube(f"{name}_collar", (0.30, 0.05, 0.20),
                 loc=(0, -0.18, 1.85), parent=base,
                 mat_=mat(f"{name}_shirt", (0.92,0.92,0.85,1), 0, 0.55))
    # Head
    head_e = empty(f"{name}_head_e", (0, 0, 2.05), parent=base)
    smooth_sphere(f"{name}_head", r=0.20, segs=20, rings=14,
                  loc=(0, 0, 0), parent=head_e, mat_=skin_mat)
    # Eyes
    for side in (-1, 1):
        smooth_sphere(f"{name}_eye_{side}", r=0.035,
                      loc=(side*0.07, -0.17, 0.03), parent=head_e,
                      mat_=mat(f"{name}_eye_w", (1,1,1,1), 0, 0.3))
        smooth_sphere(f"{name}_pup_{side}", r=0.018,
                      loc=(side*0.07, -0.19, 0.03), parent=head_e,
                      mat_=mat(f"{name}_pup", (0.05,0.05,0.10,1), 0, 0.4))
    # Nose
    smooth_cone(f"{name}_nose", r1=0.04, r2=0.015, depth=0.10, segs=8,
                loc=(0, -0.18, -0.03), parent=head_e, mat_=skin_mat).rotation_euler = (math.radians(60), 0, 0)
    # Glasses
    if glasses:
        for side in (-1, 1):
            cyl(f"{name}_glass_frame_{side}", r=0.05, depth=0.02, segs=14,
                loc=(side*0.07, -0.20, 0.03), parent=head_e, mat_=M_GLASSES).rotation_euler = (math.radians(90), 0, 0)
            cyl(f"{name}_lens_{side}", r=0.045, depth=0.01, segs=14,
                loc=(side*0.07, -0.21, 0.03), parent=head_e, mat_=M_LENS_G).rotation_euler = (math.radians(90), 0, 0)
        # Bridge
        beveled_cube(f"{name}_bridge", (0.04, 0.02, 0.02), loc=(0, -0.20, 0.03),
                     parent=head_e, mat_=M_GLASSES)
    # Hair
    smooth_sphere(f"{name}_hair", r=0.22, loc=(0, 0.03, 0.10),
                  parent=head_e, mat_=hair_mat, scale=(1.05, 0.95, 0.7))
    # Beard
    if beard:
        smooth_sphere(f"{name}_beard", r=0.13,
                      loc=(0, -0.15, -0.15), parent=head_e, mat_=hair_mat,
                      scale=(1.4, 0.5, 1.0))
    # Arms
    arms_pose = {
        "observe": [(0, -45, -45, 45), (0, -45, 45, 45)],  # both forward
        "point": [(0, -110, 0, 25), (0, -20, 0, 10)],
        "rest": [(0, -10, 0, 5), (0, -10, 0, 5)],
        "write": [(0, -50, -10, 50), (0, -50, 10, 50)],
    }
    pose_data = arms_pose.get(pose, arms_pose["observe"])
    for side_idx, side in enumerate((-1, 1)):
        sh = empty(f"{name}_sh{side_idx}", (side*0.30, 0, 1.75), parent=base)
        rx, ry, rz, el_rx = pose_data[side_idx]
        sh.rotation_euler = (math.radians(ry), 0, math.radians(side*-rz))
        cyl(f"{name}_up{side_idx}", r=0.08, depth=0.45, segs=10,
            loc=(0, 0, -0.22), parent=sh, mat_=coat_mat)
        el = empty(f"{name}_el{side_idx}", (0, 0, -0.46), parent=sh)
        el.rotation_euler = (math.radians(el_rx), 0, 0)
        cyl(f"{name}_fa{side_idx}", r=0.07, depth=0.42, segs=10,
            loc=(0, 0, -0.21), parent=el, mat_=coat_mat)
        # Hand
        smooth_sphere(f"{name}_hand{side_idx}", r=0.07,
                      loc=(0, 0, -0.45), parent=el, mat_=skin_mat)
    return {"root": base, "head_e": head_e}

# 6 astronomers in poses
astro_specs = [
    ("astro1", (1.5, -3, 0), M_ASTRO_COAT_BLUE, M_SKIN, M_HAIR_GREY, True, True, "observe"),
    ("astro2", (-3, 4, 0), M_ASTRO_COAT, M_SKIN_DARK, M_HAIR, False, True, "point"),
    ("astro3", (4, 3, 0), M_ASTRO_COAT_BLUE, M_SKIN, M_HAIR, False, False, "write"),
    ("astro4", (-5, -2, 0), M_ASTRO_COAT, M_SKIN_DARK, M_HAIR_GREY, True, True, "rest"),
    ("astro5", (6, -4, 0), M_ASTRO_COAT_BLUE, M_SKIN, M_HAIR, False, True, "observe"),
    ("astro6", (-2, -5, 0), M_ASTRO_COAT, M_SKIN, M_HAIR_GREY, True, False, "point"),
]
astros = []
for spec in astro_specs:
    a = make_astronomer(*spec)
    a["root"].rotation_euler = (0, 0, random.uniform(-math.pi, math.pi))
    astros.append(a)

# ============ DESK with maps and instruments ============
desk_base = empty("desk", loc=(-8, 8, 0))
# Desk top
beveled_cube("desk_top", (3.5, 1.5, 0.08), bevel_offset=0.04,
             loc=(0, 0, 1.0), parent=desk_base, mat_=M_DESK)
# 4 legs
for x_idx, x in enumerate((-1, 1)):
    for y_idx, y in enumerate((-1, 1)):
        cyl(f"desk_leg{x_idx}{y_idx}", r=0.08, depth=1.0, segs=10,
            loc=(x*1.55, y*0.65, 0.50), parent=desk_base, mat_=M_DESK)
# Stretchers
beveled_cube("desk_stretcher_f", (3.0, 0.04, 0.04), loc=(0, 0.65, 0.30),
             parent=desk_base, mat_=M_DESK)

# STAR MAP unrolled (3 maps)
for i in range(3):
    map_e = empty(f"map_e{i}", (-1 + i*1.0, 0.30, 1.08), parent=desk_base)
    map_e.rotation_euler = (0, 0, random.uniform(-0.3, 0.3))
    # Paper sheet
    beveled_cube(f"map_paper{i}", (0.85, 0.6, 0.01), bevel_offset=0.02,
                 loc=(0, 0, 0), parent=map_e, mat_=M_MAP_PAPER)
    # Constellation drawings (5 dots + 4 lines)
    for j in range(5):
        a = (j / 5.0) * math.pi * 2
        cyl(f"map_dot_{i}_{j}", r=0.025, depth=0.005, segs=10,
            loc=(0.20*math.cos(a), 0.15*math.sin(a), 0.008),
            parent=map_e, mat_=M_MAP_LINES)
    # Lines connecting (4)
    for j in range(4):
        a1 = (j / 5.0) * math.pi * 2
        a2 = ((j+1) / 5.0) * math.pi * 2
        x1, y1 = 0.20*math.cos(a1), 0.15*math.sin(a1)
        x2, y2 = 0.20*math.cos(a2), 0.15*math.sin(a2)
        mx, my = (x1+x2)/2, (y1+y2)/2
        l = math.sqrt((x2-x1)**2 + (y2-y1)**2)
        line = beveled_cube(f"map_line_{i}_{j}", (l*0.95, 0.01, 0.003),
                           loc=(mx, my, 0.008), parent=map_e, mat_=M_MAP_LINES)
        line.rotation_euler = (0, 0, math.atan2(y2-y1, x2-x1))
    # Map text scribbles (3 horizontal lines)
    for j in range(3):
        beveled_cube(f"map_text_{i}_{j}", (0.35, 0.02, 0.002),
                     loc=(-0.25, -0.18 + j*0.06, 0.008), parent=map_e, mat_=M_MAP_INK)

# 2 SEXTANTS brass (signature astronomical instrument)
for i in range(2):
    sext_e = empty(f"sext_e{i}", (-1.2 + i*2.4, -0.40, 1.05), parent=desk_base)
    sext_e.rotation_euler = (math.radians(10), 0, math.radians(15*((-1)**i)))
    # Frame (arc)
    for j in range(6):
        a = (j / 6.0) * math.pi/3 - math.pi/6  # 60° arc
        arc_seg = beveled_cube(f"sext_arc_{i}_{j}", (0.04, 0.04, 0.06),
                              loc=(0.20*math.sin(a), 0, 0.20*math.cos(a)),
                              parent=sext_e, mat_=M_SEXTANT)
    # Telescope on sextant
    cyl(f"sext_tube_{i}", r=0.03, depth=0.20, segs=10,
        loc=(0.10, 0, 0.05), parent=sext_e, mat_=M_TELE_TUBE)
    # Index arm
    beveled_cube(f"sext_arm_{i}", (0.04, 0.04, 0.25),
                 loc=(0, 0, 0.12), parent=sext_e, mat_=M_SEXTANT)
    # Pivot
    smooth_sphere(f"sext_pivot_{i}", r=0.03, loc=(0, 0, 0),
                  parent=sext_e, mat_=M_GOLD)
    # Sight
    cyl(f"sext_sight_{i}", r=0.025, depth=0.05, segs=8,
        loc=(0, 0, 0.25), parent=sext_e, mat_=M_BRASS)

# CELESTIAL GLOBE (signature instrument)
globe_e = empty("globe_e", (-0.5, -0.40, 1.20), parent=desk_base)
# Stand base
cyl("globe_base", r=0.25, depth=0.08, segs=18,
    loc=(0, 0, 0), parent=globe_e, mat_=M_DESK)
cyl("globe_post", r=0.04, depth=0.30, segs=10,
    loc=(0, 0, 0.15), parent=globe_e, mat_=M_GLOBE_FRAME)
# 2 rings (meridian + equatorial)
mer_ring = cyl("globe_meridian", r=0.35, depth=0.04, segs=32,
              loc=(0, 0, 0.50), parent=globe_e, mat_=M_GLOBE_FRAME)
mer_ring.rotation_euler = (0, math.radians(90), 0)
eq_ring = cyl("globe_equator", r=0.35, depth=0.04, segs=32,
             loc=(0, 0, 0.50), parent=globe_e, mat_=M_GLOBE_FRAME)
# Sphere globe
globe_sphere = smooth_sphere("globe_s", r=0.30, segs=24, rings=16,
                              loc=(0, 0, 0.50), parent=globe_e, mat_=M_GLOBE_SPHERE)

# 3 SMALLER TELESCOPES around dome
small_telescopes = []
for i in range(3):
    a = (i / 3.0) * math.pi * 2
    rad = 14
    st_e = empty(f"st_e{i}", (rad*math.cos(a), rad*math.sin(a), 0))
    st_e.rotation_euler = (0, 0, a + math.pi)  # facing center
    # Tripod legs (3)
    for j in range(3):
        leg_a = (j / 3.0) * math.pi * 2
        leg = cyl(f"st_leg{i}_{j}", r=0.06, depth=2.5, segs=10,
                 loc=(0.5*math.cos(leg_a), 0.5*math.sin(leg_a), 1.25),
                 parent=st_e, mat_=M_TELE_TRIPOD)
        leg.rotation_euler = (math.radians(10*math.cos(leg_a + math.pi/2)),
                              math.radians(-10*math.sin(leg_a + math.pi/2)), 0)
    # Mount
    smooth_sphere(f"st_mount{i}", r=0.20, loc=(0, 0, 2.5),
                  parent=st_e, mat_=M_TELE_DETAIL)
    # Tube
    tube_e = empty(f"st_tube_e{i}", (0, 0, 2.5), parent=st_e)
    tube_e.rotation_euler = (math.radians(35), 0, 0)
    cyl(f"st_tube{i}", r=0.18, depth=2.0, segs=14,
        loc=(0, 0, 0.7), parent=tube_e, mat_=M_SMALL_TELE)
    cyl(f"st_lens{i}", r=0.16, depth=0.04, segs=14,
        loc=(0, 0, 1.72), parent=tube_e, mat_=M_TELE_LENS)
    # Brass band
    cyl(f"st_band{i}", r=0.19, depth=0.06, segs=14,
        loc=(0, 0, 1.0), parent=tube_e, mat_=M_BRASS)
    small_telescopes.append(st_e)

# ============ LUSTRE CÉLESTE (chandelier hanging from dome) ============
lustre_e = empty("lustre", loc=(0, 0, 13))
# Central sphere
smooth_sphere("lustre_orb", r=0.40, segs=24, rings=16,
              loc=(0, 0, 0), parent=lustre_e, mat_=M_LUSTRE)
# 6 hanging crystals
for i in range(6):
    a = (i / 6.0) * math.pi * 2
    arm = cyl(f"lustre_arm{i}", r=0.04, depth=0.85, segs=10,
             loc=(0.45*math.cos(a), 0.45*math.sin(a), -0.20),
             parent=lustre_e, mat_=M_LUSTRE)
    arm.rotation_euler = (math.radians(-25*math.cos(a+math.pi/2)),
                          math.radians(25*math.sin(a+math.pi/2)), 0)
    # Crystal at end
    crystal_x = 0.9 * math.cos(a)
    crystal_y = 0.9 * math.sin(a)
    smooth_cone(f"lustre_crystal{i}", r1=0.10, r2=0.02, depth=0.35, segs=10,
                loc=(crystal_x, crystal_y, -0.65), parent=lustre_e, mat_=M_LUSTRE_CRYSTAL)
# Chain (3 segs)
for i in range(3):
    cyl(f"lustre_chain{i}", r=0.025, depth=0.6, segs=8,
        loc=(0, 0, 0.4 + i*0.6), parent=lustre_e, mat_=M_BRASS)
# Ceiling mount
cyl("lustre_mount", r=0.20, depth=0.15, segs=18,
    loc=(0, 0, 2.2), parent=lustre_e, mat_=M_BRASS)

# ============ 200 COSMIC PARTICLES ============
cosmics = []
for i in range(200):
    cx = random.uniform(-22, 22)
    cy = random.uniform(-22, 22)
    cz = random.uniform(1, 16)
    cp = smooth_sphere(f"cosmic{i}", r=random.uniform(0.06, 0.13), segs=8, rings=6,
                      loc=(cx, cy, cz), mat_=M_COSMIC)
    cp["_phase"] = random.uniform(0, math.pi*2)
    cp["_base_x"] = cx; cp["_base_y"] = cy; cp["_base_z"] = cz
    cp["_speed"] = random.uniform(0.4, 1.2)
    cosmics.append(cp)

# ============ ANIMATION ============
fps = 30; duration_s = 6; total_frames = fps * duration_s

# Telescope tube rotate + tilt
for f in range(1, total_frames + 1, 3):
    t = (f - 1) / fps
    # Mount rotates slowly (tracking sky)
    mount_e.rotation_euler = (0, 0, t * 0.3)
    mount_e.keyframe_insert("rotation_euler", frame=f)
    # Tube tilts slightly
    tube_pivot.rotation_euler = (math.radians(45) + math.sin(t * 0.5) * math.radians(5),
                                 0,
                                 math.radians(20) + math.sin(t * 0.4) * math.radians(8))
    tube_pivot.keyframe_insert("rotation_euler", frame=f)

# Solar system planets orbit
for p in planet_orbits:
    speed = p["speed"]
    init_a = p["init_a"]
    for f in range(1, total_frames + 1, 3):
        t = (f - 1) / fps
        p["e"].rotation_euler = (0, 0, init_a + t * speed)
        p["e"].keyframe_insert("rotation_euler", frame=f)

# Sun pulse intense
for f in range(1, total_frames + 1, 2):
    t = (f - 1) / fps
    s = 1 + math.sin(t * 2.0) * 0.10
    sun.scale = (s, s, s)
    sun.keyframe_insert("scale", frame=f)

# Sun halos breathe
for obj in bpy.data.objects:
    if obj.name.startswith("sun_halo"):
        if "_phase" in obj.keys():
            phase = obj["_phase"]
            for f in range(1, total_frames + 1, 4):
                t = (f - 1) / fps
                s = 1 + math.sin(t * 1.5 + phase) * 0.15
                obj.scale = (s, s, s)
                obj.keyframe_insert("scale", frame=f)

# Satellites orbit fast
for sat in satellites:
    speed = sat["speed"]
    for f in range(1, total_frames + 1, 3):
        t = (f - 1) / fps
        sat["e"].rotation_euler = (0, 0, t * speed)
        sat["e"].keyframe_insert("rotation_euler", frame=f)

# Orrery itself rotates slowly + bobs
for f in range(1, total_frames + 1, 4):
    t = (f - 1) / fps
    orrery_e.location.z = 11 + math.sin(t * 0.6) * 0.30
    orrery_e.rotation_euler = (0, 0, t * 0.10)
    orrery_e.keyframe_insert("location", frame=f)
    orrery_e.keyframe_insert("rotation_euler", frame=f)

# Stars twinkle
for star in projected_stars:
    phase = star["_phase"]; speed = star["_speed"]
    for f in range(1, total_frames + 1, 4):
        t = (f - 1) / fps
        s = 1 + math.sin(t * speed + phase) * 0.35
        star.scale = (s, s, s)
        star.keyframe_insert("scale", frame=f)

# Constellation stars twinkle (more dramatic)
for ci, c_e in enumerate(constellations):
    for f in range(1, total_frames + 1, 4):
        t = (f - 1) / fps
        s = 1 + math.sin(t * 2.0 + ci) * 0.25
        c_e.scale = (s, s, s)
        c_e.keyframe_insert("scale", frame=f)

# Milky way subtle drift
for obj in bpy.data.objects:
    if obj.name.startswith("milky"):
        if "_phase" in obj.keys():
            phase = obj["_phase"]
            bx = obj.location.x; by = obj.location.y
            for f in range(1, total_frames + 1, 8):
                t = (f - 1) / fps
                obj.location = (bx + math.sin(t * 0.4 + phase) * 0.5,
                                by + math.cos(t * 0.3 + phase) * 0.5,
                                obj.location.z)
                s = 1 + math.sin(t * 0.5 + phase) * 0.10
                obj.scale = (2.0*s, 1.0*s, 0.8*s)
                obj.keyframe_insert("location", frame=f)
                obj.keyframe_insert("scale", frame=f)

# Nebulas pulse
for n in nebulas:
    phase = n["_phase"]
    for f in range(1, total_frames + 1, 5):
        t = (f - 1) / fps
        s = 1 + math.sin(t * 1.2 + phase) * 0.15
        n.scale = (1.5*s, 1.2*s, 1.0*s)
        n.keyframe_insert("scale", frame=f)

# Astronomers subtle motion (sway + head turn)
for ai, a in enumerate(astros):
    base_z = a["root"].location.z
    phase = ai * 0.7
    for f in range(1, total_frames + 1, 5):
        t = (f - 1) / fps
        a["root"].location.z = base_z + math.sin(t * 0.8 + phase) * 0.04
        a["root"].keyframe_insert("location", frame=f)
        a["head_e"].rotation_euler = (math.sin(t * 0.6 + phase) * math.radians(5),
                                      math.cos(t * 0.5 + phase) * math.radians(3),
                                      math.sin(t * 0.7 + phase) * math.radians(15))
        a["head_e"].keyframe_insert("rotation_euler", frame=f)

# Globe rotate
for f in range(1, total_frames + 1, 4):
    t = (f - 1) / fps
    globe_sphere.rotation_euler = (0, 0, t * 0.5)
    globe_sphere.keyframe_insert("rotation_euler", frame=f)

# Small telescopes tilt slightly différentielles
for sti, st in enumerate(small_telescopes):
    for f in range(1, total_frames + 1, 6):
        t = (f - 1) / fps
        st.rotation_euler = (0, 0, sti * math.pi/3 + math.pi + math.sin(t * 0.5) * math.radians(10))
        st.keyframe_insert("rotation_euler", frame=f)

# Lustre rotate + bob
for f in range(1, total_frames + 1, 4):
    t = (f - 1) / fps
    lustre_e.location.z = 13 + math.sin(t * 1.0) * 0.10
    lustre_e.rotation_euler = (0, 0, t * 0.4)
    lustre_e.keyframe_insert("location", frame=f)
    lustre_e.keyframe_insert("rotation_euler", frame=f)

# Cosmic particles drift + twinkle
for cp in cosmics:
    phase = cp["_phase"]; speed = cp["_speed"]
    bx, by, bz = cp["_base_x"], cp["_base_y"], cp["_base_z"]
    for f in range(1, total_frames + 1, 6):
        t = (f - 1) / fps
        x = bx + math.sin(t * speed + phase) * 1.5
        y = by + math.cos(t * speed * 0.8 + phase) * 1.5
        z = bz + math.sin(t * speed * 0.6 + phase) * 1.2
        s = 1 + math.sin(t * 4.0 + phase) * 0.4
        cp.location = (x, y, z)
        cp.scale = (s, s, s)
        cp.keyframe_insert("location", frame=f)
        cp.keyframe_insert("scale", frame=f)

# ============ EXPORT ============
out_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "public", "_pbr_test")
out_dir = os.path.normpath(out_dir)
os.makedirs(out_dir, exist_ok=True)
out_glb = os.path.join(out_dir, "pbr_planetarium_proc.glb")

bpy.ops.object.select_all(action='SELECT')
bpy.ops.export_scene.gltf(
    filepath=out_glb, export_format='GLB',
    export_animations=True, export_apply=False, export_yup=True, use_selection=False,
)
size_mb = os.path.getsize(out_glb) / (1024 * 1024)
print(f"[proc_planetarium_observatory_dome] DONE → {out_glb} ({size_mb:.2f} MB)")
print("[proc_planetarium_observatory_dome] Dome + GREAT TELESCOPE + 9 planètes orrery + 4 satellites + 100 stars + 8 constellations + milky way + 3 nebulas + 6 astronomers + desk + 3 maps + 2 sextants + globe + 3 small telescopes + lustre + 200 cosmic particles")
