import bpy
import bmesh
import json
import math
import sys

WATER_BASE_COLOR = (0.30, 0.62, 0.68, 1.0)
WATER_ALPHA_FALLBACK = 0.45
WATER_IOR = 1.33
WATER_ROUGHNESS = 0.05
GRID_SEGMENTS = 48
TUBE_SEGMENTS = 24
TUBE_RINGS = 16
WAVE_KEY_COUNT = 10
DROPLET_COUNT = 8

JET_KINDS = ("fountain", "pour", "waterfall")
SURFACE_KINDS = ("ripple", "still")


def _parse_zone(bbox_zone):
    z = bbox_zone or {}
    c = z.get("center") or (0.0, 0.0, 0.0)
    s = z.get("size") or (1.0, 1.0, 1.0)
    center = (float(c[0]), float(c[1]), float(c[2]))
    size = (max(abs(float(s[0])), 1e-3),
            max(abs(float(s[1])), 1e-3),
            max(abs(float(s[2])), 1e-3))
    return center, size


def _set_input(bsdf, names, value):
    for name in names:
        sock = bsdf.inputs.get(name)
        if sock is None:
            continue
        try:
            sock.default_value = value
            return True
        except Exception:
            pass
    return False


def make_water_material(name="AuroraWaterMat"):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    bsdf = None
    for node in mat.node_tree.nodes:
        if node.type == "BSDF_PRINCIPLED":
            bsdf = node
            break
    if bsdf is not None:
        _set_input(bsdf, ("Base Color",), WATER_BASE_COLOR)
        _set_input(bsdf, ("Transmission Weight", "Transmission"), 1.0)
        _set_input(bsdf, ("IOR",), WATER_IOR)
        _set_input(bsdf, ("Roughness",), WATER_ROUGHNESS)
        _set_input(bsdf, ("Alpha",), WATER_ALPHA_FALLBACK)
    for attr, value in (("surface_render_method", "BLENDED"),
                        ("blend_method", "BLEND")):
        try:
            setattr(mat, attr, value)
        except Exception:
            pass
    try:
        mat.use_backface_culling = False
    except Exception:
        pass
    return mat


def _new_object_from_bmesh(name, bm, material):
    mesh = bpy.data.meshes.new(name)
    bm.to_mesh(mesh)
    bm.free()
    mesh.materials.append(material)
    for poly in mesh.polygons:
        poly.use_smooth = True
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.scene.collection.objects.link(obj)
    return obj


def _build_surface_object(name, center, size, material):
    bm = bmesh.new()
    bmesh.ops.create_grid(bm, x_segments=GRID_SEGMENTS, y_segments=GRID_SEGMENTS, size=0.5)
    for v in bm.verts:
        v.co.x *= size[0]
        v.co.y *= size[1]
        v.co.z = 0.0
    obj = _new_object_from_bmesh(name, bm, material)
    obj.location = (center[0], center[1], center[2])
    return obj


def _build_tube_object(name, center, size, material):
    rx = max(size[0] * 0.5, 1e-3)
    ry = max(size[1] * 0.5, 1e-3)
    height = size[2]
    bm = bmesh.new()
    rings = []
    for ring in range(TUBE_RINGS + 1):
        z = height * (ring / float(TUBE_RINGS)) - height * 0.5
        row = []
        for seg in range(TUBE_SEGMENTS):
            a = 2.0 * math.pi * seg / TUBE_SEGMENTS
            row.append(bm.verts.new((rx * math.cos(a), ry * math.sin(a), z)))
        rings.append(row)
    for ring in range(TUBE_RINGS):
        for seg in range(TUBE_SEGMENTS):
            v0 = rings[ring][seg]
            v1 = rings[ring][(seg + 1) % TUBE_SEGMENTS]
            v2 = rings[ring + 1][(seg + 1) % TUBE_SEGMENTS]
            v3 = rings[ring + 1][seg]
            bm.faces.new((v0, v1, v2, v3))
    obj = _new_object_from_bmesh(name, bm, material)
    obj.location = (center[0], center[1], center[2])
    _apply_thin_wall(obj, min(rx, ry))
    return obj


def _apply_thin_wall(obj, radius):
    try:
        mod = obj.modifiers.new("AuroraThinWall", "SOLIDIFY")
        mod.thickness = max(radius * 0.06, 0.002)
        mod.offset = 0.0
        bpy.context.view_layer.objects.active = obj
        obj.select_set(True)
        bpy.ops.object.modifier_apply(modifier=mod.name)
        return True
    except Exception:
        try:
            obj.modifiers.clear()
        except Exception:
            pass
        return False


def _add_wave_shape_keys_surface(obj, size, wave_amplitude):
    mesh = obj.data
    obj.shape_key_add(name="Basis", from_mix=False)
    r_max = max(min(size[0], size[1]) * 0.5, 1e-3)
    amp = max(wave_amplitude, 0.0) * 0.08 * min(size[0], size[1])
    base = [v.co.copy() for v in mesh.vertices]
    for i in range(WAVE_KEY_COUNT):
        phase = 2.0 * math.pi * i / WAVE_KEY_COUNT
        key = obj.shape_key_add(name="Wave_%02d" % i, from_mix=False)
        for vi, co in enumerate(base):
            r = math.hypot(co.x, co.y)
            falloff = max(0.0, math.cos(0.5 * math.pi * min(r / r_max, 1.0)))
            dz = amp * math.sin(2.0 * math.pi * 2.5 * (r / r_max) - phase) * falloff
            key.data[vi].co = (co.x, co.y, co.z + dz)
    return WAVE_KEY_COUNT


def _add_wave_shape_keys_tube(obj, size, wave_amplitude):
    mesh = obj.data
    obj.shape_key_add(name="Basis", from_mix=False)
    height = max(size[2], 1e-3)
    r_ref = max(min(size[0], size[1]) * 0.5, 1e-3)
    amp = max(wave_amplitude, 0.0) * 0.25 * r_ref
    base = [v.co.copy() for v in mesh.vertices]
    for i in range(WAVE_KEY_COUNT):
        phase = 2.0 * math.pi * i / WAVE_KEY_COUNT
        key = obj.shape_key_add(name="Wave_%02d" % i, from_mix=False)
        for vi, co in enumerate(base):
            u = (co.z + height * 0.5) / height
            bulge = amp * math.sin(2.0 * math.pi * 2.0 * u - phase)
            r = math.hypot(co.x, co.y)
            if r > 1e-9:
                nx, ny = co.x / r, co.y / r
            else:
                nx, ny = 0.0, 0.0
            sway = amp * 0.5 * math.sin(2.0 * math.pi * u * 1.5 - phase)
            key.data[vi].co = (co.x + nx * bulge + sway,
                               co.y + ny * bulge,
                               co.z)
    return WAVE_KEY_COUNT


def animate_wave_cycle(obj, fps, loop_s):
    shape_keys = obj.data.shape_keys
    if shape_keys is None:
        return 0
    key_blocks = [kb for kb in shape_keys.key_blocks if kb.name != "Basis"]
    n = len(key_blocks)
    if n == 0:
        return 0
    total = max(int(round(fps * max(loop_s, 0.25))), 4)
    for f in range(1, total + 1):
        t = (f - 1) / float(total)
        for i, kb in enumerate(key_blocks):
            d = abs((t * n) - i) % n
            d = min(d, n - d)
            kb.value = max(0.0, 1.0 - d)
            kb.keyframe_insert("value", frame=f)
    return total


def _add_droplets(center, size, material, fps, total_frames):
    made = []
    top_z = center[2] + size[2] * 0.5
    r_ref = max(min(size[0], size[1]) * 0.5, 1e-3)
    for j in range(DROPLET_COUNT):
        bm = bmesh.new()
        bmesh.ops.create_icosphere(bm, subdivisions=1, radius=max(r_ref * 0.12, 0.004))
        obj = _new_object_from_bmesh("AuroraDroplet_%02d" % j, bm, material)
        angle = 2.0 * math.pi * j / DROPLET_COUNT
        phase = j / float(DROPLET_COUNT)
        step = max(total_frames // 24, 1)
        for f in range(1, total_frames + 1, step):
            t = (((f - 1) / float(total_frames)) + phase) % 1.0
            reach = r_ref * (0.4 + 1.6 * t)
            obj.location = (center[0] + math.cos(angle) * reach,
                            center[1] + math.sin(angle) * reach,
                            top_z + size[2] * 0.35 * 4.0 * t * (1.0 - t))
            obj.keyframe_insert("location", frame=f)
        made.append(obj.name)
    return made


def create_water_surface(bbox_zone, kind, wave_amplitude=0.35, loop_s=3.0,
                         fps=24, droplets=False, name="AuroraWater"):
    center, size = _parse_zone(bbox_zone)
    kind = kind if kind in JET_KINDS + SURFACE_KINDS else "ripple"
    material = make_water_material(name + "Mat")
    if kind in JET_KINDS:
        obj = _build_tube_object(name + "Jet", center, size, material)
        key_count = _add_wave_shape_keys_tube(obj, size, wave_amplitude)
    else:
        obj = _build_surface_object(name + "Surface", center, size, material)
        key_count = _add_wave_shape_keys_surface(obj, size, wave_amplitude)
    total_frames = animate_wave_cycle(obj, fps, loop_s)
    droplet_names = []
    if droplets and kind in ("fountain", "waterfall"):
        try:
            droplet_names = _add_droplets(center, size, material, fps, total_frames)
        except Exception:
            droplet_names = []
    return {
        "object": obj.name,
        "kind": kind,
        "material": material.name,
        "vertex_count": len(obj.data.vertices),
        "shape_key_count": key_count,
        "frame_count": total_frames,
        "droplets": droplet_names,
        "center": list(center),
        "size": list(size),
    }


def _export_glb(path, fps, frame_end):
    scene = bpy.context.scene
    scene.render.fps = int(fps)
    scene.frame_start = 1
    scene.frame_end = max(int(frame_end), 1)
    kwargs = dict(
        filepath=path,
        export_format="GLB",
        export_animations=True,
        export_force_sampling=True,
        export_nla_strips=False,
        export_extras=True,
        export_morph=True,
        export_morph_normal=False,
        export_morph_animation=True,
    )
    try:
        bpy.ops.export_scene.gltf(**kwargs)
        return {"exported": path}
    except TypeError as exc:
        for k in ("export_morph_normal", "export_morph_animation"):
            kwargs.pop(k, None)
        try:
            bpy.ops.export_scene.gltf(**kwargs)
            return {"exported": path, "export_warn": str(exc)}
        except Exception as exc2:
            return {"export_error": str(exc2)}
    except Exception as exc:
        return {"export_error": str(exc)}


def _argv_after_dashes():
    argv = sys.argv
    if "--" in argv:
        return argv[argv.index("--") + 1:]
    return []


def _self_test(output_path="/tmp/water_test.glb", fps=24):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    result = {"self_test": True, "builds": []}
    surface = create_water_surface(
        {"center": [0.0, 0.0, 0.0], "size": [2.0, 2.0, 0.2]},
        "ripple", wave_amplitude=0.5, loop_s=2.0, fps=fps,
    )
    result["builds"].append(surface)
    jet = create_water_surface(
        {"center": [3.0, 0.0, 0.6], "size": [0.4, 0.4, 1.2]},
        "fountain", wave_amplitude=0.6, loop_s=2.0, fps=fps,
        droplets=True, name="AuroraFountain",
    )
    result["builds"].append(jet)
    frame_end = max(b.get("frame_count", 1) for b in result["builds"])
    result.update(_export_glb(output_path, fps, frame_end))
    return result


def main():
    args = _argv_after_dashes()
    if "--self-test" in args:
        out = "/tmp/water_test.glb"
        if "--output" in args:
            out = args[args.index("--output") + 1]
        result = _self_test(out)
    else:
        bbox = [0.0, 0.0, 0.0, 2.0, 2.0, 0.3]
        if "--bbox" in args:
            bbox = [float(x) for x in args[args.index("--bbox") + 1].split(",")]
        kind = args[args.index("--kind") + 1] if "--kind" in args else "ripple"
        fps = int(args[args.index("--fps") + 1]) if "--fps" in args else 24
        loop_s = float(args[args.index("--loop-s") + 1]) if "--loop-s" in args else 3.0
        amp = float(args[args.index("--amplitude") + 1]) if "--amplitude" in args else 0.35
        out = args[args.index("--output") + 1] if "--output" in args else "/tmp/water_manual.glb"
        bpy.ops.wm.read_factory_settings(use_empty=True)
        result = create_water_surface(
            {"center": bbox[0:3], "size": bbox[3:6]}, kind,
            wave_amplitude=amp, loop_s=loop_s, fps=fps,
            droplets="--droplets" in args,
        )
        result.update(_export_glb(out, fps, result.get("frame_count", 1)))
    print("AURORA_FLUID_RESULT_BEGIN")
    print(json.dumps(result))
    print("AURORA_FLUID_RESULT_END")


if __name__ == "__main__":
    main()
