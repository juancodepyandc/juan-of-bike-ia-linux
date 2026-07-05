import bpy
import copy
import json
import math
import os
import struct
import sys
from mathutils import Matrix, Vector

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
params = json.loads(argv[0]) if argv else {}
output_dir = argv[1] if len(argv) > 1 else "/tmp"
run_id = argv[2] if len(argv) > 2 else "historical_person"
fmt = argv[3] if len(argv) > 3 else "glb"

bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
scene.render.fps = 24
scene.frame_start = 1
scene.frame_end = 73


def hex_to_rgb(value, fallback):
    if not isinstance(value, str):
        return fallback
    value = value.strip().lstrip("#")
    if len(value) != 6:
        return fallback
    try:
        return (
            int(value[0:2], 16) / 255.0,
            int(value[2:4], 16) / 255.0,
            int(value[4:6], 16) / 255.0,
        )
    except Exception:
        return fallback


def make_texture(name, base, accent, weave=True, intensity=1.0):
    img = bpy.data.images.new(name, width=256, height=256, alpha=False)
    pixels = []
    for y in range(256):
        for x in range(256):
            grain = intensity * (0.018 * math.sin(x * 0.43) + 0.012 * math.sin(y * 0.29))
            stripe = 1.0 if weave and ((x // 13 + y // 29) % 2 == 0) else 0.0
            mix = 0.88 + intensity * 0.035 * stripe
            r = max(0.0, min(1.0, base[0] * mix + accent[0] * (1.0 - mix) + grain))
            g = max(0.0, min(1.0, base[1] * mix + accent[1] * (1.0 - mix) + grain))
            b = max(0.0, min(1.0, base[2] * mix + accent[2] * (1.0 - mix) + grain))
            pixels.extend([r, g, b, 1.0])
    img.pixels.foreach_set(pixels)
    img.pack()
    return img


skin_rgb = hex_to_rgb(params.get("skin"), (0.64, 0.46, 0.34))
hair_rgb = hex_to_rgb(params.get("hair"), (0.04, 0.035, 0.03))
suit_rgb = hex_to_rgb(params.get("jacket"), (0.015, 0.015, 0.018))
waistcoat_rgb = hex_to_rgb(params.get("waistcoat"), (0.045, 0.044, 0.042))
shirt_rgb = hex_to_rgb(params.get("shirt"), (0.92, 0.90, 0.84))
shoe_rgb = hex_to_rgb(params.get("shoes"), (0.01, 0.01, 0.012))

skin_tex = make_texture("Lincoln_skin_subtle_pores_texture", skin_rgb, (0.50, 0.31, 0.23), False, 0.45)
suit_tex = make_texture("Lincoln_black_wool_frock_coat_texture", suit_rgb, (0.08, 0.08, 0.085), True, 0.55)
shirt_tex = make_texture("Lincoln_white_cotton_shirt_texture", shirt_rgb, (0.76, 0.74, 0.70), True, 0.35)
hair_tex = make_texture("Lincoln_dark_hair_beard_strand_texture", hair_rgb, (0.12, 0.09, 0.065), False, 0.50)


def mat(name, color, texture=None, roughness=0.65):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nodes = m.node_tree.nodes
    links = m.node_tree.links
    nodes.clear()
    bsdf = nodes.new("ShaderNodeBsdfPrincipled")
    out = nodes.new("ShaderNodeOutputMaterial")
    if texture is not None:
        tex = nodes.new("ShaderNodeTexImage")
        tex.image = texture
        tex.extension = "REPEAT"
        links.new(tex.outputs["Color"], bsdf.inputs["Base Color"])
    else:
        bsdf.inputs["Base Color"].default_value = (*color, 1.0)
    if "Roughness" in bsdf.inputs:
        bsdf.inputs["Roughness"].default_value = roughness
    if "Metallic" in bsdf.inputs:
        bsdf.inputs["Metallic"].default_value = 0.0
    links.new(bsdf.outputs["BSDF"], out.inputs["Surface"])
    return m


skin_mat = mat("Mat_skin_face_hands_warm_textured", skin_rgb, skin_tex, 0.58)
hair_mat = mat("Mat_dark_hair_chin_curtain_beard_no_moustache", hair_rgb, hair_tex, 0.86)
suit_mat = mat("Mat_black_frock_coat_wool_textured", suit_rgb, suit_tex, 0.72)
waistcoat_mat = mat("Mat_black_waistcoat_buttons", waistcoat_rgb, suit_tex, 0.68)
shirt_mat = mat("Mat_white_shirt_cotton_texture", shirt_rgb, shirt_tex, 0.62)
shoe_mat = mat("Mat_polished_black_shoes", shoe_rgb, None, 0.38)
eye_mat = mat("Mat_deep_set_dark_eyes", (0.005, 0.004, 0.003), None, 0.18)


def shade(obj):
    try:
        bpy.context.view_layer.objects.active = obj
        obj.select_set(True)
        bpy.ops.object.shade_smooth()
        obj.select_set(False)
    except Exception:
        pass
    return obj


def sphere(name, loc, scale, material, segments=64, rings=32):
    bpy.ops.mesh.primitive_uv_sphere_add(segments=segments, ring_count=rings, radius=1.0, location=loc)
    obj = bpy.context.active_object
    obj.name = name
    obj.scale = scale
    obj.data.materials.append(material)
    return shade(obj)


def rounded_box(name, loc, scale, material, bevel=0.025, segments=6):
    bpy.ops.mesh.primitive_cube_add(size=1.0, location=loc)
    obj = bpy.context.active_object
    obj.name = name
    obj.scale = scale
    obj.data.materials.append(material)
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    if bevel > 0:
        b = obj.modifiers.new(f"{name}_soft_bevel", "BEVEL")
        b.width = bevel
        b.segments = segments
        n = obj.modifiers.new(f"{name}_weighted_normals", "WEIGHTED_NORMAL")
        try:
            bpy.context.view_layer.objects.active = obj
            bpy.ops.object.modifier_apply(modifier=b.name)
            bpy.ops.object.modifier_apply(modifier=n.name)
        except Exception:
            pass
    return shade(obj)


def cyl(name, loc, radius, depth, material, vertices=48):
    bpy.ops.mesh.primitive_cylinder_add(vertices=vertices, radius=radius, depth=depth, location=loc)
    obj = bpy.context.active_object
    obj.name = name
    obj.data.materials.append(material)
    return shade(obj)


def cone(name, loc, radius1, radius2, depth, material, vertices=48):
    bpy.ops.mesh.primitive_cone_add(vertices=vertices, radius1=radius1, radius2=radius2, depth=depth, location=loc)
    obj = bpy.context.active_object
    obj.name = name
    obj.data.materials.append(material)
    return shade(obj)


def loft_ellipse_mesh(name, rings, material, segments=40, cap_top=True, cap_bottom=True):
    """Create a smooth tailored body/clothing volume from elliptical rings.

    Rings are tuples: (z, x_radius, y_radius, y_offset). This makes a single
    coherent silhouette instead of stacked primitives.
    """
    verts = []
    for z, rx, ry, yoff in rings:
        for i in range(segments):
            a = 2.0 * math.pi * i / segments
            verts.append((rx * math.cos(a), yoff + ry * math.sin(a), z))
    faces = []
    for r in range(len(rings) - 1):
        base = r * segments
        next_base = (r + 1) * segments
        for i in range(segments):
            faces.append((base + i, base + (i + 1) % segments, next_base + (i + 1) % segments, next_base + i))
    if cap_bottom:
        faces.append(tuple(reversed(range(segments))))
    if cap_top:
        start = (len(rings) - 1) * segments
        faces.append(tuple(start + i for i in range(segments)))
    mesh = bpy.data.meshes.new(f"{name}_mesh")
    mesh.from_pydata(verts, [], faces)
    mesh.update()
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(obj)
    obj.data.materials.append(material)
    bevel = obj.modifiers.new(f"{name}_cloth_soft_bevel", "BEVEL")
    bevel.width = 0.006
    bevel.segments = 2
    normal = obj.modifiers.new(f"{name}_weighted_normals", "WEIGHTED_NORMAL")
    try:
        bpy.context.view_layer.objects.active = obj
        obj.select_set(True)
        bpy.ops.object.modifier_apply(modifier=bevel.name)
        bpy.ops.object.modifier_apply(modifier=normal.name)
        obj.select_set(False)
    except Exception:
        pass
    return shade(obj)


def make_segment(name, radius, material, vertices=48):
    return cyl(name, (0, 0, 0), radius, 1.0, material, vertices)


def set_between(obj, frame, a, b):
    scene.frame_set(frame)
    va = Vector(a)
    vb = Vector(b)
    d = vb - va
    obj.location = (va + vb) * 0.5
    obj.rotation_euler = d.to_track_quat("Z", "Y").to_euler()
    obj.scale = (1.0, 1.0, max(d.length, 0.001))
    obj.keyframe_insert("location", frame=frame)
    obj.keyframe_insert("rotation_euler", frame=frame)
    obj.keyframe_insert("scale", frame=frame)


def set_loc(obj, frame, loc):
    scene.frame_set(frame)
    obj.location = loc
    obj.keyframe_insert("location", frame=frame)


def set_rot(obj, frame, rot_deg):
    scene.frame_set(frame)
    obj.rotation_euler = tuple(math.radians(v) for v in rot_deg)
    obj.keyframe_insert("rotation_euler", frame=frame)


def parent_keep_world(child, parent):
    child.parent = parent
    try:
        child.matrix_parent_inverse = parent.matrix_world.inverted()
    except Exception:
        pass


def empty(name, loc):
    obj = bpy.data.objects.new(name, None)
    obj.empty_display_type = "PLAIN_AXES"
    obj.empty_display_size = 0.05
    obj.location = loc
    bpy.context.collection.objects.link(obj)
    return obj


root = bpy.data.objects.new("root_pelvis_walk_controller", None)
root.empty_display_type = "PLAIN_AXES"
bpy.context.collection.objects.link(root)

pelvis = loft_ellipse_mesh(
    "pelvis_hips_black_trousers_tailored_not_blob",
    [
        (0.86, 0.135, 0.075, 0.002),
        (0.96, 0.160, 0.083, 0.000),
        (1.08, 0.150, 0.080, -0.002),
    ],
    waistcoat_mat,
    44,
)
torso = loft_ellipse_mesh(
    "torso_spine_tailored_long_black_frock_coat_continuous",
    [
        (0.92, 0.178, 0.058, 0.020),
        (1.08, 0.170, 0.070, 0.006),
        (1.30, 0.158, 0.082, -0.002),
        (1.52, 0.185, 0.088, -0.002),
        (1.66, 0.215, 0.092, 0.000),
        (1.74, 0.120, 0.068, 0.004),
    ],
    suit_mat,
    56,
)
waistcoat = rounded_box("front_black_waistcoat_separate_panel", (0, -0.100, 1.38), (0.125, 0.014, 0.340), waistcoat_mat, 0.008, 3)
shirt = rounded_box("front_white_shirt_visible_collar_panel", (0, -0.116, 1.505), (0.082, 0.012, 0.260), shirt_mat, 0.008, 3)
lapel_l = rounded_box("left_black_frock_coat_lapel", (-0.075, -0.128, 1.53), (0.052, 0.015, 0.27), suit_mat, 0.010, 4)
lapel_r = rounded_box("right_black_frock_coat_lapel", (0.075, -0.128, 1.53), (0.052, 0.015, 0.27), suit_mat, 0.010, 4)
lapel_l.rotation_euler[2] = math.radians(-11)
lapel_r.rotation_euler[2] = math.radians(11)
tail_l = rounded_box("left_long_black_frock_coat_tail_flat_cloth", (-0.075, 0.054, 0.79), (0.074, 0.016, 0.330), suit_mat, 0.008, 3)
tail_r = rounded_box("right_long_black_frock_coat_tail_flat_cloth", (0.075, 0.054, 0.79), (0.074, 0.016, 0.330), suit_mat, 0.008, 3)

for side, sx in [("left", -1), ("right", 1)]:
    front_panel = rounded_box(f"{side}_flat_tailored_frock_coat_front_panel", (sx * 0.082, -0.124, 1.34), (0.050, 0.007, 0.400), suit_mat, 0.006, 2)
    front_panel.rotation_euler[2] = math.radians(-3 * sx)
    shoulder_pad = rounded_box(f"{side}_squared_19th_century_shoulder_pad", (sx * 0.132, -0.014, 1.685), (0.040, 0.022, 0.018), suit_mat, 0.007, 2)
    shoulder_pad.rotation_euler[2] = math.radians(4 * sx)
    coat_hem = rounded_box(f"{side}_front_frock_coat_lower_hem_edge", (sx * 0.080, -0.130, 0.935), (0.058, 0.004, 0.008), suit_mat, 0.001, 1)
    rear_pleat = rounded_box(f"{side}_rear_frock_coat_center_pleat_detail", (sx * 0.034, 0.084, 0.88), (0.006, 0.006, 0.300), suit_mat, 0.001, 1)
    collar = rounded_box(f"{side}_white_standing_shirt_collar_wing", (sx * 0.038, -0.142, 1.680), (0.032, 0.006, 0.036), shirt_mat, 0.002, 1)
    collar.rotation_euler[2] = math.radians(-14 * sx)
    for j, z in enumerate([1.62, 1.53, 1.44, 1.35, 1.26, 1.17]):
        fold = rounded_box(
            f"{side}_subtle_vertical_wool_fold_{j}",
            (sx * (0.154 + 0.006 * (j % 2)), -0.149, z),
            (0.003, 0.003, 0.050),
            suit_mat,
            0.0008,
            1,
        )

for i, z in enumerate([1.55, 1.43, 1.31, 1.19]):
    btn = sphere(f"waistcoat_black_button_{i}", (0, -0.146, z), (0.011, 0.004, 0.011), shoe_mat, 24, 10)
    rim = sphere(f"waistcoat_button_highlight_rim_{i}", (0.003, -0.149, z + 0.002), (0.004, 0.0015, 0.004), shirt_mat, 12, 6)
for name, x in [("bow_tie_left_black_triangle", -0.035), ("bow_tie_right_black_triangle", 0.035)]:
    bow = cone(name, (x, -0.145, 1.705), 0.035, 0.008, 0.035, shoe_mat, 4)
    bow.rotation_euler[1] = math.radians(90)

for side, sx in [("left", -1), ("right", 1)]:
    seam = rounded_box(f"{side}_frock_coat_front_vertical_seam_detail", (sx * 0.145, -0.146, 1.34), (0.006, 0.006, 0.43), suit_mat, 0.001, 1)
    pocket = rounded_box(f"{side}_black_frock_coat_pocket_flap_detail", (sx * 0.135, -0.150, 1.15), (0.070, 0.007, 0.016), suit_mat, 0.002, 1)
    pocket.rotation_euler[2] = math.radians(3 * sx)
    tail_edge = rounded_box(f"{side}_rear_coat_tail_outer_edge_detail", (sx * 0.132, 0.062, 0.82), (0.004, 0.004, 0.30), suit_mat, 0.001, 1)
    cuff = rounded_box(f"{side}_white_shirt_cuff_visible_at_wrist_detail", (sx * 0.245, -0.095, 1.02), (0.035, 0.012, 0.014), shirt_mat, 0.003, 2)

for i, z in enumerate([1.63, 1.58, 1.53, 1.48, 1.43, 1.38, 1.33, 1.28]):
    stitch_l = rounded_box(f"left_lapel_wool_stitch_line_{i}", (-0.055, -0.148, z), (0.004, 0.003, 0.010), suit_mat, 0.0008, 1)
    stitch_r = rounded_box(f"right_lapel_wool_stitch_line_{i}", (0.055, -0.148, z), (0.004, 0.003, 0.010), suit_mat, 0.0008, 1)

neck = cyl("neck_skin_visible_above_collar", (0, 0, 1.72), 0.043, 0.12, skin_mat, 40)
head = sphere("head_long_narrow_face_prominent_cheekbones_high_detail", (0, -0.006, 1.93), (0.110, 0.074, 0.174), skin_mat, 128, 64)
chin = sphere("prominent_chin_under_chin_curtain_beard", (0, -0.100, 1.805), (0.066, 0.020, 0.040), hair_mat, 56, 20)
for i, (x, z, sx) in enumerate([(-0.076, 1.890, 0.022), (-0.064, 1.850, 0.026), (0.064, 1.850, 0.026), (0.076, 1.890, 0.022)]):
    sphere(f"side_chin_curtain_beard_no_moustache_{i}", (x, -0.104, z), (sx, 0.013, 0.050), hair_mat, 48, 18)
for i, x in enumerate([-0.046, -0.023, 0.0, 0.023, 0.046]):
    sphere(f"lower_jaw_beard_lock_{i}", (x, -0.108, 1.785 - 0.008 * abs(i - 2)), (0.020, 0.012, 0.038), hair_mat, 36, 14)

for side, x in [("left", -0.118), ("right", 0.118)]:
    ear = sphere(f"{side}_ear_skin_visible_profile_detail", (x, -0.018, 1.925), (0.025, 0.015, 0.046), skin_mat, 40, 18)
    inner = sphere(f"{side}_inner_ear_ridge_skin_detail", (x * 1.004, -0.030, 1.925), (0.015, 0.006, 0.030), skin_mat, 28, 12)

hair_cap = sphere("dark_slightly_messy_hair_cap_high_detail", (0, -0.004, 2.048), (0.112, 0.094, 0.050), hair_mat, 128, 32)
for i, x in enumerate([-0.080, -0.045, -0.010, 0.025, 0.065]):
    lock = cone(f"messy_dark_front_hair_lock_{i}", (x, -0.078, 2.037 + 0.006 * (i % 2)), 0.014, 0.004, 0.050, hair_mat, 20)
    lock.rotation_euler[0] = math.radians(-10)
for i, x in enumerate([-0.082, -0.052, -0.022, 0.012, 0.046, 0.078]):
    strand = cyl(f"short_hair_strand_texture_geometry_{i}", (x, -0.088, 2.010 - 0.004 * abs(i - 2)), 0.0030, 0.045, hair_mat, 12)
    strand.rotation_euler[0] = math.radians(-7)
    strand.rotation_euler[1] = math.radians(6 * math.sin(i))

hat_brim = cyl("lincoln_stovepipe_hat_wide_flat_brim_identity_cue", (0, -0.002, 2.110), 0.142, 0.020, shoe_mat, 96)
hat_crown = cyl("lincoln_tall_stovepipe_hat_crown_identity_cue", (0, -0.002, 2.202), 0.092, 0.185, shoe_mat, 96)
hat_band = cyl("lincoln_stovepipe_hat_satin_band_detail", (0, -0.002, 2.147), 0.096, 0.020, hair_mat, 96)

for name, x in [("deep_set_eye_left_dark_small", -0.044), ("deep_set_eye_right_dark_small", 0.044)]:
    sphere(name, (x, -0.152, 1.958), (0.012, 0.006, 0.008), eye_mat, 32, 12)
for name, x, tilt in [("dark_brow_left", -0.047, -6), ("dark_brow_right", 0.047, 6)]:
    brow = rounded_box(name, (x, -0.157, 1.992), (0.042, 0.006, 0.007), hair_mat, 0.002, 1)
    brow.rotation_euler[2] = math.radians(tilt)
nose = cone("long_narrow_nose_profile", (0, -0.162, 1.920), 0.017, 0.006, 0.060, skin_mat, 40)
nose.rotation_euler[0] = math.radians(90)
mouth = rounded_box("small_mouth_visible_no_moustache", (0, -0.164, 1.862), (0.038, 0.0035, 0.006), skin_mat, 0.0015, 1)
for i, z in enumerate([2.005, 1.990, 1.975]):
    wrinkle = rounded_box(f"forehead_horizontal_wrinkle_skin_detail_{i}", (0, -0.154, z), (0.082 - 0.010 * i, 0.004, 0.003), skin_mat, 0.001, 1)
for side, sx in [("left", -1), ("right", 1)]:
    cheek = rounded_box(f"{side}_prominent_cheekbone_skin_plane_detail", (sx * 0.060, -0.153, 1.925), (0.046, 0.004, 0.006), skin_mat, 0.0015, 1)
    cheek.rotation_euler[2] = math.radians(-7 * sx)
    fold = rounded_box(f"{side}_nasolabial_face_fold_no_moustache_detail", (sx * 0.038, -0.156, 1.885), (0.006, 0.004, 0.047), skin_mat, 0.001, 1)
    fold.rotation_euler[2] = math.radians(7 * sx)
    eyelid = rounded_box(f"{side}_lower_eyelid_face_detail", (sx * 0.046, -0.154, 1.947), (0.030, 0.003, 0.004), skin_mat, 0.001, 1)

def remove_primitive_face_overlays():
    if params.get("preserve_face_detail_overlays", True):
        return
    # The scan carries the nose, lips, cheeks and forehead relief. Remove
    # primitive overlays that would otherwise read as duplicate artifacts.
    primitive_face_tokens = (
        "long_narrow_nose_profile",
        "small_mouth_visible_no_moustache",
        "forehead_horizontal_wrinkle",
        "prominent_cheekbone_skin_plane_detail",
        "nasolabial_face_fold_no_moustache_detail",
        "lower_eyelid_face_detail",
    )
    for obj in list(bpy.context.scene.objects):
        if obj.type == "MESH" and any(token in obj.name for token in primitive_face_tokens):
            bpy.data.objects.remove(obj, do_unlink=True)


def import_face_scan_patch(scan_path, source_label, source_url):
    before = set(bpy.context.scene.objects)
    ext = os.path.splitext(scan_path)[1].lower()
    try:
        if ext in (".glb", ".gltf"):
            bpy.ops.import_scene.gltf(filepath=scan_path)
        elif ext == ".stl":
            if hasattr(bpy.ops.wm, "stl_import"):
                bpy.ops.wm.stl_import(filepath=scan_path)
            else:
                bpy.ops.import_mesh.stl(filepath=scan_path)
        else:
            return []
        imported = [obj for obj in bpy.context.scene.objects if obj not in before and obj.type == "MESH"]
    except Exception:
        return []
    if not imported:
        return []

    for obj in imported:
        obj.name = f"smithsonian_cc0_lincoln_face_scan_patch_{obj.name}"
        obj.data.name = f"{obj.name}_mesh"
        obj.data.transform(obj.matrix_world)
        obj.matrix_world = Matrix.Identity(4)

    all_coords = [obj.matrix_world @ Vector(corner) for obj in imported for corner in obj.bound_box]
    min_v = Vector((min(v[i] for v in all_coords) for i in range(3)))
    max_v = Vector((max(v[i] for v in all_coords) for i in range(3)))
    depth_y = max(0.001, max_v.y - min_v.y)
    height_z = max(0.001, max_v.z - min_v.z)
    # Keep only the face-bearing side of the Smithsonian cast. The raw model is
    # a hollow plaster head; this turns it into a front facial relief patch.
    width_x = max(0.001, max_v.x - min_v.x)
    keep_y = min_v.y + depth_y * 0.55
    keep_top_z = min_v.z + height_z * 0.76
    keep_min_x = min_v.x + width_x * 0.18
    keep_max_x = max_v.x - width_x * 0.18
    try:
        import bmesh
        for obj in imported:
            bm = bmesh.new()
            bm.from_mesh(obj.data)
            remove = [
                v for v in bm.verts
                if v.co.y < keep_y or v.co.z > keep_top_z or v.co.x < keep_min_x or v.co.x > keep_max_x
            ]
            if remove:
                bmesh.ops.delete(bm, geom=remove, context="VERTS")
            bm.to_mesh(obj.data)
            bm.free()
            obj.data.update()
    except Exception:
        pass

    patch_coords = []
    for obj in imported:
        if len(obj.data.vertices) == 0:
            bpy.data.objects.remove(obj, do_unlink=True)
            continue
        for v in obj.data.vertices:
            patch_coords.append(obj.matrix_world @ v.co)
    if not patch_coords:
        return []

    min_p = Vector((min(v[i] for v in patch_coords) for i in range(3)))
    max_p = Vector((max(v[i] for v in patch_coords) for i in range(3)))
    center = (min_p + max_p) * 0.5
    patch_height = max(0.001, max_p.z - min_p.z)
    base_scale = 0.268 / patch_height
    transform = (
        Matrix.Translation(Vector((0.0, -0.116, 1.916)))
        @ Matrix.Rotation(math.radians(180.0), 4, "Z")
        @ Matrix.Diagonal((base_scale * 0.78, base_scale * 0.38, base_scale * 1.00, 1.0))
        @ Matrix.Translation(-center)
    )
    for obj in imported:
        obj.data.transform(transform)
        obj.data.update()
        obj.data.materials.clear()
        obj.data.materials.append(skin_mat)
        shade(obj)
        parent_keep_world(obj, head)
        obj["aurora_reference_source"] = source_label
        obj["aurora_reference_url"] = source_url
    remove_primitive_face_overlays()
    return imported


face_scan_imported = []
face_scan_path = params.get("face_scan_glb_path")
if params.get("use_face_scan_patch", False) and isinstance(face_scan_path, str) and os.path.isfile(face_scan_path):
    face_scan_imported = import_face_scan_patch(
        face_scan_path,
        params.get("face_scan_source", "Smithsonian CC0 Lincoln life mask GLB"),
        params.get("face_scan_url", "https://3d.si.edu/object/3d/abraham-lincoln:c02c239d-5ebf-4a7a-a368-e2288bbf4b31"),
    )
elif isinstance(face_scan_path, str) and os.path.isfile(face_scan_path):
    head["aurora_reference_source"] = params.get("face_scan_source", "Smithsonian CC0 Lincoln life mask GLB")
    head["aurora_reference_url"] = params.get(
        "face_scan_url",
        "https://3d.si.edu/object/3d/abraham-lincoln:c02c239d-5ebf-4a7a-a368-e2288bbf4b31",
    )

life_mask_path = params.get("life_mask_stl_path")
if not face_scan_imported and isinstance(life_mask_path, str) and os.path.isfile(life_mask_path):
    before = set(bpy.context.scene.objects)
    try:
        if hasattr(bpy.ops.wm, "stl_import"):
            bpy.ops.wm.stl_import(filepath=life_mask_path)
        else:
            bpy.ops.import_mesh.stl(filepath=life_mask_path)
        imported = [obj for obj in bpy.context.scene.objects if obj not in before and obj.type == "MESH"]
    except Exception:
        imported = []
    if imported:
        mask = imported[0]
        mask.name = "smithsonian_cc0_lincoln_life_mask_face_scan"
        mask.data.name = "smithsonian_cc0_lincoln_life_mask_face_scan_mesh"
        mask.data.materials.clear()
        mask.data.materials.append(skin_mat)
        mask.scale = (0.00108, 0.00108, 0.00108)
        mask.location = (0.0, -0.092, 1.930)
        mask.rotation_euler = (0.0, 0.0, math.radians(90))
        shade(mask)
        remove_primitive_face_overlays()
        mask["aurora_reference_source"] = "Smithsonian/Wikimedia CC0 Lincoln life mask"
        mask["aurora_reference_url"] = "https://commons.wikimedia.org/wiki/File:Abraham_Lincoln_Life_Volks_Mask_-_3D_model_by_The_Smithsonian_Institution_-_Sketchfab.stl"


def import_scan_group(scan_path, group_name, material, target_largest_extent, source_label, source_url):
    before = set(bpy.context.scene.objects)
    ext = os.path.splitext(scan_path)[1].lower()
    try:
        if ext in (".glb", ".gltf"):
            bpy.ops.import_scene.gltf(filepath=scan_path)
        elif ext == ".stl":
            if hasattr(bpy.ops.wm, "stl_import"):
                bpy.ops.wm.stl_import(filepath=scan_path)
            else:
                bpy.ops.import_mesh.stl(filepath=scan_path)
        else:
            return None
    except Exception:
        return None

    imported = [obj for obj in bpy.context.scene.objects if obj not in before and obj.type == "MESH"]
    if not imported:
        return None

    for obj in imported:
        obj.data.transform(obj.matrix_world)
        obj.matrix_world = Matrix.Identity(4)

    coords = [obj.matrix_world @ Vector(corner) for obj in imported for corner in obj.bound_box]
    if not coords:
        for obj in imported:
            bpy.data.objects.remove(obj, do_unlink=True)
        return None

    min_v = Vector((min(v[i] for v in coords) for i in range(3)))
    max_v = Vector((max(v[i] for v in coords) for i in range(3)))
    center = (min_v + max_v) * 0.5
    extents = max_v - min_v
    source_size = max(extents[:]) or 1.0
    scale = target_largest_extent / source_size
    transform = Matrix.Diagonal((scale, scale, scale, 1.0)) @ Matrix.Translation(-center)

    group = empty(group_name, (0, 0, 0))
    group["aurora_reference_source"] = source_label
    group["aurora_reference_url"] = source_url
    for obj in imported:
        obj.name = f"{group_name}_{obj.name}"
        obj.data.name = f"{obj.name}_mesh"
        obj.data.transform(transform)
        obj.data.update()
        obj.data.materials.clear()
        obj.data.materials.append(material)
        shade(obj)
        parent_keep_world(obj, group)
        obj["aurora_reference_source"] = source_label
        obj["aurora_reference_url"] = source_url
    return group


def make_hand(side, sx):
    scan_key = "left_hand_scan_glb_path" if side == "L" else "right_hand_scan_glb_path"
    scan_path = params.get(scan_key)
    if isinstance(scan_path, str) and os.path.isfile(scan_path):
        source_label = params.get("hand_scan_source", "Smithsonian CC0 Lincoln Volk hand cast GLB")
        source_url = params.get(
            "hand_scan_url",
            "https://3d.si.edu/object/3d/abraham-lincoln:d8c642d6-4ebc-11ea-b77f-2e728ce88125",
        )
        scanned = import_scan_group(
            scan_path,
            f"hand_{side}_smithsonian_cc0_volk_cast_high_detail",
            skin_mat,
            0.105,
            source_label,
            source_url,
        )
        if scanned is not None:
            scanned.rotation_euler = (math.radians(0.0), math.radians(0.0), math.radians(4.0 * -sx))
            return scanned

    hand = sphere(f"hand_{side}_palm_visible_with_separate_fingers", (sx * 0.25, -0.10, 1.02), (0.032, 0.020, 0.030), skin_mat, 40, 16)
    finger_specs = [
        ("thumb", sx * 0.034, -0.015, -0.005, 0.014, 0.0048),
        ("index_finger", sx * 0.021, -0.025, 0.012, 0.018, 0.0042),
        ("middle_finger", sx * 0.007, -0.027, 0.014, 0.020, 0.0045),
        ("ring_finger", sx * -0.007, -0.025, 0.011, 0.018, 0.0041),
        ("pinky_finger", sx * -0.019, -0.022, 0.008, 0.015, 0.0038),
    ]
    for name, dx, dy, dz, length, radius in finger_specs:
        for phalanx in range(3):
            y = hand.location.y + dy - phalanx * length * 0.72
            z = hand.location.z + dz - phalanx * 0.002
            f = cyl(
                f"{name}_{side}_separate_digit_phalanx_{phalanx}",
                (hand.location.x + dx, y, z),
                radius * (1.0 - 0.08 * phalanx),
                length,
                skin_mat,
                20,
            )
            f.rotation_euler[0] = math.radians(82)
            parent_keep_world(f, hand)
            joint = sphere(
                f"{name}_{side}_knuckle_joint_{phalanx}",
                (hand.location.x + dx, y + 0.003, z + 0.001),
                (radius * 1.25, radius * 0.85, radius * 1.05),
                skin_mat,
                18,
                8,
            )
            parent_keep_world(joint, hand)
        nail = rounded_box(
            f"{name}_{side}_tiny_fingernail_detail",
            (hand.location.x + dx, hand.location.y + dy - length * 2.15, hand.location.z + dz + 0.002),
            (radius * 0.85, 0.0018, radius * 0.42),
            shirt_mat,
            0.0007,
            1,
        )
        parent_keep_world(nail, hand)
    return hand


parts_static = [
    pelvis, torso, waistcoat, shirt, lapel_l, lapel_r, tail_l, tail_r, neck, head, chin,
    hair_cap, nose, mouth,
]
for obj in list(bpy.context.scene.objects):
    if obj.type == "MESH" and obj.name not in {"hand_L_palm_visible_with_separate_fingers", "hand_R_palm_visible_with_separate_fingers"}:
        parent_keep_world(obj, root)

head_controller = head

arm_parts = {}
leg_parts = {}
for side, sx in [("L", -1), ("R", 1)]:
    arm_parts[side] = {
        "shoulder": sphere(f"shoulder_{side}_black_sleeve_joint", (sx * 0.188, -0.005, 1.58), (0.047, 0.039, 0.047), suit_mat, 36, 14),
        "elbow": sphere(f"elbow_{side}_sleeve_joint", (sx * 0.240, -0.035, 1.30), (0.037, 0.030, 0.037), suit_mat, 32, 12),
        "upper": make_segment(f"upper_arm_{side}_black_frock_sleeve", 0.044, suit_mat, 56),
        "fore": make_segment(f"forearm_{side}_black_frock_sleeve", 0.037, suit_mat, 56),
        "hand": make_hand(side, sx),
    }
    leg_parts[side] = {
        "knee": sphere(f"knee_{side}_black_trouser_joint", (sx * 0.078, -0.010, 0.53), (0.047, 0.038, 0.047), waistcoat_mat, 32, 12),
        "thigh": make_segment(f"thigh_{side}_black_trouser_segment", 0.064, waistcoat_mat, 56),
        "shin": make_segment(f"shin_{side}_black_trouser_segment", 0.052, waistcoat_mat, 56),
        "foot": sphere(f"foot_{side}_polished_black_shoe", (sx * 0.078, -0.090, 0.088), (0.068, 0.132, 0.047), shoe_mat, 48, 16),
        "front_crease": make_segment(f"front_trouser_crease_{side}_animated_detail", 0.0028, waistcoat_mat, 12),
        "shoe_toe_cap": sphere(f"shoe_toe_cap_{side}_polished_detail", (sx * 0.078, -0.165, 0.099), (0.056, 0.052, 0.020), shoe_mat, 32, 10),
    }


frames = list(range(1, 74, 6))
for f in frames:
    t = 2.0 * math.pi * (f - 1) / 72.0
    root_z = 0.018 * math.sin(2 * t)
    root_y = 0.016 * math.sin(t + math.pi / 2)
    set_loc(root, f, (0.0, root_y, root_z))
    set_rot(torso, f, (0.0, 0.0, 3.6 * math.sin(t)))
    set_rot(head_controller, f, (1.6 * math.sin(t + 0.3), 0.0, -2.6 * math.sin(t)))
    for side, sx in [("L", -1), ("R", 1)]:
        phase = math.sin(t if side == "L" else t + math.pi)
        arm_phase = -phase
        shoulder = (sx * 0.190, -0.002 + root_y, 1.58 + root_z)
        elbow = (sx * (0.240 + 0.012 * abs(arm_phase)), -0.044 + 0.076 * arm_phase + root_y, 1.31 + root_z)
        wrist = (sx * (0.228 + 0.010 * abs(arm_phase)), -0.080 + 0.128 * arm_phase + root_y, 1.030 + root_z)
        set_loc(arm_parts[side]["shoulder"], f, shoulder)
        set_loc(arm_parts[side]["elbow"], f, elbow)
        set_loc(arm_parts[side]["hand"], f, wrist)
        set_between(arm_parts[side]["upper"], f, shoulder, elbow)
        set_between(arm_parts[side]["fore"], f, elbow, wrist)

        swing = max(0.0, phase)
        planted = max(0.0, -phase)
        hip = (sx * 0.078, -0.006 + root_y, 0.92 + root_z)
        knee = (sx * (0.083 - 0.010 * swing + 0.004 * planted), 0.035 * phase + root_y, 0.52 + 0.070 * swing + 0.014 * planted + root_z)
        ankle = (sx * (0.078 + 0.008 * phase), -0.125 * phase + root_y, 0.124 + 0.036 * swing + root_z * 0.35)
        foot = (sx * (0.084 + 0.012 * phase), -0.148 * phase - 0.050 + root_y, 0.087 + 0.032 * swing)
        set_loc(leg_parts[side]["knee"], f, knee)
        set_loc(leg_parts[side]["foot"], f, foot)
        set_between(leg_parts[side]["thigh"], f, hip, knee)
        set_between(leg_parts[side]["shin"], f, knee, ankle)
        crease_top = (sx * 0.080, -0.038 * phase + root_y - 0.010, 0.83 + root_z)
        crease_bottom = (sx * 0.081, -0.120 * phase + root_y - 0.015, 0.22 + 0.040 * swing + root_z * 0.25)
        set_between(leg_parts[side]["front_crease"], f, crease_top, crease_bottom)
        set_loc(leg_parts[side]["shoe_toe_cap"], f, (sx * (0.085 + 0.012 * phase), -0.148 * phase - 0.134 + root_y, 0.103 + 0.026 * swing))

for obj in bpy.context.scene.objects:
    if obj.animation_data and obj.animation_data.action:
        for fc in obj.animation_data.action.fcurves:
            for kp in fc.keyframe_points:
                kp.interpolation = "BEZIER"
            try:
                fc.modifiers.new(type="CYCLES")
            except Exception:
                pass

scene.frame_set(1)
bpy.context.view_layer.update()
for obj in bpy.context.scene.objects:
    if obj.animation_data and obj.animation_data.action:
        obj.location = obj.location.copy()
        obj.rotation_euler = obj.rotation_euler.copy()
        obj.scale = obj.scale.copy()
bpy.context.view_layer.update()


def collapse_glb_animations(glb_path, clip_name):
    try:
        with open(glb_path, "rb") as fh:
            raw = fh.read()
        if raw[:4] != b"glTF":
            return {"collapsed": False, "reason": "not_glb"}
        version, _ = struct.unpack_from("<II", raw, 4)
        if version != 2:
            return {"collapsed": False, "reason": "unsupported_glb_version"}
        offset = 12
        chunks = []
        while offset + 8 <= len(raw):
            chunk_len, chunk_type = struct.unpack_from("<II", raw, offset)
            offset += 8
            chunks.append((chunk_type, raw[offset:offset + chunk_len]))
            offset += chunk_len
        gltf = json.loads(chunks[0][1].rstrip(bytes([0]) + b" ").decode("utf-8"))
        animations = gltf.get("animations") or []
        if len(animations) <= 1:
            if animations:
                animations[0]["name"] = clip_name
            return {"collapsed": False, "reason": "already_single", "animation_count": len(animations)}
        samplers = []
        channels = []
        for anim in animations:
            sampler_offset = len(samplers)
            for sampler in anim.get("samplers") or []:
                samplers.append(copy.deepcopy(sampler))
            for channel in anim.get("channels") or []:
                ch = copy.deepcopy(channel)
                ch["sampler"] = int(ch.get("sampler", 0)) + sampler_offset
                channels.append(ch)
        gltf["animations"] = [{"name": clip_name, "samplers": samplers, "channels": channels}]
        json_bytes = json.dumps(gltf, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
        json_bytes += b" " * ((4 - len(json_bytes) % 4) % 4)
        chunks[0] = (0x4E4F534A, json_bytes)
        out = bytearray(b"glTF")
        out.extend(struct.pack("<II", 2, 12 + sum(8 + len(data) for _, data in chunks)))
        for chunk_type, data in chunks:
            out.extend(struct.pack("<II", len(data), chunk_type))
            out.extend(data)
        with open(glb_path, "wb") as fh:
            fh.write(out)
        return {"collapsed": True, "animation_count_before": len(animations), "animation_count_after": 1, "channels": len(channels)}
    except Exception as exc:
        return {"collapsed": False, "reason": f"{type(exc).__name__}: {exc}"}


out_path = os.path.join(output_dir, f"{run_id}_procedural.{fmt}")
if fmt == "glb":
    bpy.ops.export_scene.gltf(
        filepath=out_path,
        export_format="GLB",
        export_animations=True,
        export_extras=True,
        export_current_frame=True,
        export_frame_range=True,
        export_bake_animation=True,
    )
    collapse = collapse_glb_animations(out_path, "Dignified_Walk_Cycle")
elif fmt == "fbx":
    bpy.ops.export_scene.fbx(filepath=out_path, use_selection=False)
    collapse = None
else:
    bpy.ops.wm.obj_export(filepath=out_path)
    collapse = None

print(json.dumps({
    "ok": True,
    "path": out_path,
    "format": fmt,
    "template": "historical_person_performer",
    "person": params.get("person_name", "Abraham Lincoln"),
    "animationFrames": 73,
    "animationCollapse": collapse,
    "identityCues": [
        "black frock coat",
        "black waistcoat",
        "white shirt",
        "black bow tie",
        "chin curtain beard without moustache",
        "long narrow face",
        "dark messy hair",
        "separate fingers",
    ],
}))
