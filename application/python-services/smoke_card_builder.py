import bpy
import bmesh
import json
import math
import os
import sys
import tempfile

import mathutils

TEX_SIZE = 256
CARD_SEGMENTS = 10
CARD_COUNT = 3
BILLOW_KEY_COUNT = 10
GAS_KINDS = ("smoke", "steam", "fog")

GAS_TINT = {
    "smoke": (0.58, 0.58, 0.62),
    "steam": (0.92, 0.94, 0.96),
    "fog": (0.78, 0.80, 0.82),
}
GAS_ALPHA_GAIN = {"smoke": 1.0, "steam": 0.85, "fog": 0.6}
GAS_EMISSION = {"smoke": 0.25, "steam": 0.5, "fog": 0.35}


def _parse_zone(bbox_zone):
    z = bbox_zone or {}
    c = z.get("center") or (0.0, 0.0, 0.0)
    s = z.get("size") or (1.0, 1.0, 1.5)
    center = (float(c[0]), float(c[1]), float(c[2]))
    size = (max(abs(float(s[0])), 1e-3),
            max(abs(float(s[1])), 1e-3),
            max(abs(float(s[2])), 1e-3))
    return center, size


def _fractal_noise(np, size, octaves=5, seed=7):
    rng = np.random.default_rng(seed)
    out = np.zeros((size, size), dtype=np.float64)
    amp = 1.0
    total = 0.0
    for octave in range(octaves):
        cells = 2 ** (octave + 2)
        grid = rng.random((cells + 1, cells + 1))
        xs = np.linspace(0.0, cells, size, endpoint=False)
        x0 = xs.astype(int)
        fx = xs - x0
        x1 = np.minimum(x0 + 1, cells)
        a = grid[np.ix_(x0, x0)]
        b = grid[np.ix_(x0, x1)]
        c = grid[np.ix_(x1, x0)]
        d = grid[np.ix_(x1, x1)]
        wx = fx[np.newaxis, :]
        wy = fx[:, np.newaxis]
        layer = (a * (1 - wx) * (1 - wy) + b * wx * (1 - wy)
                 + c * (1 - wx) * wy + d * wx * wy)
        out += amp * layer
        total += amp
        amp *= 0.5
    return out / max(total, 1e-9)


def make_gas_texture(kind="smoke", name="AuroraGasTex", seed=7):
    import numpy as np
    noise = _fractal_noise(np, TEX_SIZE, seed=seed)
    ys, xs = np.mgrid[0:TEX_SIZE, 0:TEX_SIZE].astype(np.float64)
    cx = (xs / (TEX_SIZE - 1)) * 2.0 - 1.0
    cy = (ys / (TEX_SIZE - 1)) * 2.0 - 1.0
    radial = np.clip(1.0 - np.sqrt(cx * cx + cy * cy), 0.0, 1.0)
    alpha = np.clip((noise - 0.32) * 2.2, 0.0, 1.0) * (radial ** 1.2)
    alpha = np.clip(alpha * GAS_ALPHA_GAIN.get(kind, 1.0), 0.0, 1.0)
    tint = GAS_TINT.get(kind, GAS_TINT["smoke"])
    shade = 0.75 + 0.25 * noise
    rgba = np.empty((TEX_SIZE, TEX_SIZE, 4), dtype=np.float32)
    rgba[:, :, 0] = tint[0] * shade
    rgba[:, :, 1] = tint[1] * shade
    rgba[:, :, 2] = tint[2] * shade
    rgba[:, :, 3] = alpha
    img = bpy.data.images.new(name, width=TEX_SIZE, height=TEX_SIZE, alpha=True)
    img.pixels.foreach_set(rgba.ravel())
    try:
        img.filepath_raw = os.path.join(tempfile.gettempdir(), name + ".png")
        img.file_format = "PNG"
        img.save()
    except Exception:
        try:
            img.pack()
        except Exception:
            pass
    return img


def make_gas_material(kind="smoke", name="AuroraGasMat", seed=7):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    nt = mat.node_tree
    bsdf = None
    for node in nt.nodes:
        if node.type == "BSDF_PRINCIPLED":
            bsdf = node
            break
    img = make_gas_texture(kind, name + "Tex", seed=seed)
    tex = nt.nodes.new(type="ShaderNodeTexImage")
    tex.image = img
    if bsdf is not None:
        tex.location = (bsdf.location.x - 400, bsdf.location.y)
        for sock_name in ("Base Color", "Emission Color", "Emission"):
            sock = bsdf.inputs.get(sock_name)
            if sock is not None:
                try:
                    nt.links.new(tex.outputs["Color"], sock)
                except Exception:
                    pass
        alpha_sock = bsdf.inputs.get("Alpha")
        if alpha_sock is not None:
            try:
                nt.links.new(tex.outputs["Alpha"], alpha_sock)
            except Exception:
                pass
        strength = bsdf.inputs.get("Emission Strength")
        if strength is not None:
            try:
                strength.default_value = GAS_EMISSION.get(kind, 0.3)
            except Exception:
                pass
        rough = bsdf.inputs.get("Roughness")
        if rough is not None:
            try:
                rough.default_value = 1.0
            except Exception:
                pass
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


def _build_cards_object(name, center, size, material):
    w = max(size[0], size[1])
    h = size[2]
    bm = bmesh.new()
    tmp = bpy.data.meshes.new(name + "_card_tmp")
    for k in range(CARD_COUNT):
        card = bmesh.new()
        bmesh.ops.create_grid(card, x_segments=CARD_SEGMENTS,
                              y_segments=CARD_SEGMENTS, size=0.5, calc_uvs=True)
        rot = (mathutils.Matrix.Rotation(math.radians(180.0 * k / CARD_COUNT), 4, "Z")
               @ mathutils.Matrix.Rotation(math.radians(90.0), 4, "X"))
        for v in card.verts:
            v.co.x *= w
            v.co.y *= h
            v.co = rot @ v.co
        card.to_mesh(tmp)
        bm.from_mesh(tmp)
        card.free()
    mesh = bpy.data.meshes.new(name)
    bm.to_mesh(mesh)
    bm.free()
    bpy.data.meshes.remove(tmp)
    mesh.materials.append(material)
    for poly in mesh.polygons:
        poly.use_smooth = True
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.scene.collection.objects.link(obj)
    obj.location = (center[0], center[1], center[2])
    return obj


def _add_billow_shape_keys(obj, size, billow_amplitude):
    mesh = obj.data
    obj.shape_key_add(name="Basis", from_mix=False)
    w = max(max(size[0], size[1]), 1e-3)
    h = max(size[2], 1e-3)
    amp = max(billow_amplitude, 0.0) * 0.18 * w
    base = [v.co.copy() for v in mesh.vertices]
    for i in range(BILLOW_KEY_COUNT):
        phase = 2.0 * math.pi * i / BILLOW_KEY_COUNT
        key = obj.shape_key_add(name="Billow_%02d" % i, from_mix=False)
        for vi, co in enumerate(base):
            u = (co.z + h * 0.5) / h
            r = math.hypot(co.x, co.y)
            if r > 1e-9:
                nx, ny = co.x / r, co.y / r
            else:
                nx, ny = 0.0, 0.0
            swell = amp * (0.25 + 0.75 * u) * math.sin(2.0 * math.pi * 1.5 * u - phase)
            lift = amp * 0.3 * math.sin(2.0 * math.pi * 2.0 * u - phase + 1.3)
            key.data[vi].co = (co.x + nx * swell, co.y + ny * swell, co.z + lift)
    return BILLOW_KEY_COUNT


def animate_billow_cycle(obj, fps, loop_s):
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


def _animate_rise(root, rise_height, billow_amplitude, total_frames):
    base_loc = tuple(root.location)
    base_scale = tuple(root.scale)
    swell = 1.0 + 0.35 * max(billow_amplitude, 0.0)
    step = max(total_frames // 24, 1)
    frames = list(range(1, total_frames + 1, step))
    if frames[-1] != total_frames:
        frames.append(total_frames)
    for f in frames:
        t = (f - 1) / float(max(total_frames - 1, 1))
        root.location = (base_loc[0], base_loc[1], base_loc[2] + rise_height * t)
        s = 1.0 + (swell - 1.0) * t
        root.scale = (base_scale[0] * s, base_scale[1] * s, base_scale[2])
        root.rotation_euler = (0.0, 0.0, math.radians(30.0) * t)
        root.keyframe_insert("location", frame=f)
        root.keyframe_insert("scale", frame=f)
        root.keyframe_insert("rotation_euler", frame=f)
    return len(frames)


def create_smoke_cards(bbox_zone, kind="smoke", rise_speed=0.3,
                       billow_amplitude=0.5, loop_s=4.0, fps=24,
                       name="AuroraSmoke", seed=7):
    center, size = _parse_zone(bbox_zone)
    kind = kind if kind in GAS_KINDS else "smoke"
    material = make_gas_material(kind, name + "Mat", seed=seed)
    root = bpy.data.objects.new(name + "Root", None)
    bpy.context.scene.collection.objects.link(root)
    root.location = (center[0], center[1], center[2])
    cards = _build_cards_object(name + "Cards", (0.0, 0.0, 0.0), size, material)
    cards.parent = root
    key_count = _add_billow_shape_keys(cards, size, billow_amplitude)
    total_frames = animate_billow_cycle(cards, fps, loop_s)
    rise_height = max(rise_speed, 0.0) * max(loop_s, 0.25)
    keyed = _animate_rise(root, rise_height, billow_amplitude, total_frames)
    return {
        "object": cards.name,
        "root": root.name,
        "kind": kind,
        "material": material.name,
        "vertex_count": len(cards.data.vertices),
        "card_count": CARD_COUNT,
        "shape_key_count": key_count,
        "frame_count": total_frames,
        "rise_height": rise_height,
        "trs_keyframes": keyed,
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


def _self_test(output_path="/tmp/smoke_test.glb", fps=24):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    result = {"self_test": True}
    build = create_smoke_cards(
        {"center": [0.0, 0.0, 0.75], "size": [1.0, 1.0, 1.5]},
        kind="smoke", rise_speed=0.3, billow_amplitude=0.6,
        loop_s=3.0, fps=fps,
    )
    result["build"] = build
    result.update(_export_glb(output_path, fps, build.get("frame_count", 1)))
    return result


def main():
    args = _argv_after_dashes()
    if "--self-test" in args:
        out = "/tmp/smoke_test.glb"
        if "--output" in args:
            out = args[args.index("--output") + 1]
        result = _self_test(out)
    else:
        bbox = [0.0, 0.0, 0.75, 1.0, 1.0, 1.5]
        if "--bbox" in args:
            bbox = [float(x) for x in args[args.index("--bbox") + 1].split(",")]
        kind = args[args.index("--kind") + 1] if "--kind" in args else "smoke"
        fps = int(args[args.index("--fps") + 1]) if "--fps" in args else 24
        loop_s = float(args[args.index("--loop-s") + 1]) if "--loop-s" in args else 4.0
        rise = float(args[args.index("--rise-speed") + 1]) if "--rise-speed" in args else 0.3
        billow = float(args[args.index("--billow") + 1]) if "--billow" in args else 0.5
        out = args[args.index("--output") + 1] if "--output" in args else "/tmp/smoke_manual.glb"
        bpy.ops.wm.read_factory_settings(use_empty=True)
        result = create_smoke_cards(
            {"center": bbox[0:3], "size": bbox[3:6]}, kind=kind,
            rise_speed=rise, billow_amplitude=billow, loop_s=loop_s, fps=fps,
        )
        result.update(_export_glb(out, fps, result.get("frame_count", 1)))
    print("AURORA_GAS_RESULT_BEGIN")
    print(json.dumps(result))
    print("AURORA_GAS_RESULT_END")


if __name__ == "__main__":
    main()
