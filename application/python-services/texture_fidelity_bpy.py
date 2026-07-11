import bpy
import sys
import os
import json
import traceback
import numpy as np
from mathutils import Vector


def _args():
    a = sys.argv
    if "--" not in a:
        return {}
    rest = a[a.index("--") + 1:]
    out = {}
    for i in range(0, len(rest) - 1, 2):
        out[rest[i].lstrip("-")] = rest[i + 1]
    return out


def _mesh_objects():
    return [o for o in bpy.data.objects if o.type == "MESH" and o.data and len(o.data.polygons)]


def _world_bbox(objs):
    mn = Vector((1e18, 1e18, 1e18))
    mx = Vector((-1e18, -1e18, -1e18))
    for o in objs:
        for c in o.bound_box:
            w = o.matrix_world @ Vector(c)
            mn = Vector((min(mn[i], w[i]) for i in range(3)))
            mx = Vector((max(mx[i], w[i]) for i in range(3)))
    return mn, mx


def _setup_cycles(scene):
    import os as _os
    scene.render.engine = "CYCLES"
    scene.cycles.samples = 1
    scene.cycles.use_denoising = False
    scene.render.use_persistent_data = True
    if _os.environ.get("AURORA_FIDELITY_CPU") == "1":
        scene.cycles.device = "CPU"
        print("FIDELITY_LOG:cycles device CPU (force)", flush=True)
        return
    prefs = bpy.context.preferences.addons["cycles"].preferences
    for ct in ("OPTIX", "CUDA"):
        try:
            prefs.compute_device_type = ct
            prefs.get_devices()
            gpus = [d for d in prefs.devices if d.type == ct]
            if gpus:
                for d in prefs.devices:
                    d.use = d.type == ct
                scene.cycles.device = "GPU"
                print(f"FIDELITY_LOG:cycles device {ct}", flush=True)
                return
        except Exception:
            continue
    scene.cycles.device = "CPU"
    print("FIDELITY_LOG:cycles device CPU", flush=True)


def _load_mask_image(path):
    img = bpy.data.images.load(path)
    w, h = img.size
    px = np.empty(w * h * 4, dtype=np.float32)
    img.pixels.foreach_get(px)
    bpy.data.images.remove(img)
    return px.reshape(h, w, 4)[..., 0] > 0.5


def _norm_canvas(mask, cell=120, canvas=136):
    ys, xs = np.nonzero(mask)
    out = np.zeros((canvas, canvas), dtype=bool)
    if xs.size == 0:
        return out
    sub = mask[ys.min():ys.max() + 1, xs.min():xs.max() + 1]
    h, w = sub.shape
    s = cell / max(h, w)
    nh = max(1, int(round(h * s)))
    nw = max(1, int(round(w * s)))
    yi = np.clip((np.arange(nh) / s).astype(int), 0, h - 1)
    xi = np.clip((np.arange(nw) / s).astype(int), 0, w - 1)
    r = sub[yi][:, xi]
    oy = (canvas - nh) // 2
    ox = (canvas - nw) // 2
    out[oy:oy + nh, ox:ox + nw] = r
    return out


def _iou(a, b):
    union = np.logical_or(a, b).sum()
    if not union:
        return 0.0
    return float(np.logical_and(a, b).sum()) / float(union)


_AXES = {
    "+X": Vector((1, 0, 0)),
    "-X": Vector((-1, 0, 0)),
    "+Y": Vector((0, 1, 0)),
    "-Y": Vector((0, -1, 0)),
    "+Z": Vector((0, 0, 1)),
    "-Z": Vector((0, 0, -1)),
}


def _frame_for_axis(axis, mn, mx):
    quat = axis.to_track_quat("Z", "Y")
    right = quat @ Vector((1, 0, 0))
    up = quat @ Vector((0, 1, 0))
    ext = mx - mn
    w = sum(abs(right[i]) * ext[i] for i in range(3))
    h = sum(abs(up[i]) * ext[i] for i in range(3))
    d = sum(abs(axis[i]) * ext[i] for i in range(3))
    return quat, right, up, max(w, 1e-6), max(h, 1e-6), max(d, 1e-6)


def _render_silhouette(scene, cam_obj, axis, mn, mx, path, res=320):
    center = (mn + mx) / 2
    quat, right, up, w, h, d = _frame_for_axis(axis, mn, mx)
    dist = d / 2 + max((mx - mn)) + 0.1
    cam_obj.location = center + axis * dist
    cam_obj.rotation_euler = quat.to_euler()
    cam_obj.data.type = "ORTHO"
    cam_obj.data.ortho_scale = max(w, h) * 1.02
    cam_obj.data.clip_start = 0.001
    cam_obj.data.clip_end = dist * 10
    scene.render.resolution_x = res
    scene.render.resolution_y = res
    scene.render.film_transparent = True
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGBA"
    scene.render.filepath = path
    bpy.ops.render.render(write_still=True)
    img = bpy.data.images.load(path)
    px = np.empty(res * res * 4, dtype=np.float32)
    img.pixels.foreach_get(px)
    bpy.data.images.remove(img)
    return px.reshape(res, res, 4)[..., 3] > 0.1


def _detect_axis(scene, cam_obj, mn, mx, photo_mask, workdir):
    ref = _norm_canvas(photo_mask)
    scores = {}
    for name, axis in _AXES.items():
        p = os.path.join(workdir, f"sil_{name.replace('+', 'p').replace('-', 'm')}.png")
        sil = _render_silhouette(scene, cam_obj, axis, mn, mx, p)
        scores[name] = round(_iou(_norm_canvas(sil), ref), 4)
        print(f"FIDELITY_LOG:axis {name} iou={scores[name]}", flush=True)
    best = max(scores, key=scores.get)
    return best, scores


def _write_projection_uvs(objs, axis, mn, mx):
    quat, right, up, w, h, d = _frame_for_axis(axis, mn, mx)
    r = np.array(right, dtype=np.float64)
    u = np.array(up, dtype=np.float64)
    worlds = []
    for o in objs:
        me = o.data
        n = len(me.vertices)
        co = np.empty(n * 3, dtype=np.float32)
        me.vertices.foreach_get("co", co)
        co = co.reshape(n, 3).astype(np.float64)
        M = np.array(o.matrix_world, dtype=np.float64)
        worlds.append(co @ M[:3, :3].T + M[:3, 3])
    s_all = [wp @ r for wp in worlds]
    t_all = [wp @ u for wp in worlds]
    smin = min(float(s.min()) for s in s_all)
    smax = max(float(s.max()) for s in s_all)
    tmin = min(float(t.min()) for t in t_all)
    tmax = max(float(t.max()) for t in t_all)
    ds = max(smax - smin, 1e-9)
    dt = max(tmax - tmin, 1e-9)
    for o, s, t in zip(objs, s_all, t_all):
        me = o.data
        uu = (s - smin) / ds
        vv = (t - tmin) / dt
        nl = len(me.loops)
        vi = np.empty(nl, dtype=np.int32)
        me.loops.foreach_get("vertex_index", vi)
        uv = np.empty((nl, 2), dtype=np.float32)
        uv[:, 0] = uu[vi]
        uv[:, 1] = vv[vi]
        layer = me.uv_layers.get("FidelityProj") or me.uv_layers.new(name="FidelityProj")
        layer.data.foreach_set("uv", uv.ravel())
        me.uv_layers.active_index = 0
        me.uv_layers[0].active_render = True


def _write_visibility(objs, axis, mn, mx):
    from mathutils.bvhtree import BVHTree
    verts_all = []
    tris_all = []
    base = 0
    for o in objs:
        me = o.data
        n = len(me.vertices)
        co = np.empty(n * 3, dtype=np.float32)
        me.vertices.foreach_get("co", co)
        co = co.reshape(n, 3).astype(np.float64)
        M = np.array(o.matrix_world, dtype=np.float64)
        w = co @ M[:3, :3].T + M[:3, 3]
        verts_all.append(w)
        me.calc_loop_triangles()
        nt_ = len(me.loop_triangles)
        tv = np.empty(nt_ * 3, dtype=np.int32)
        me.loop_triangles.foreach_get("vertices", tv)
        tv = tv.reshape(-1, 3)
        for a, b, c in tv:
            tris_all.append((int(a) + base, int(b) + base, int(c) + base))
        base += n
    allv = np.concatenate(verts_all, axis=0)
    bvh = BVHTree.FromPolygons([Vector((float(p[0]), float(p[1]), float(p[2]))) for p in allv],
                               tris_all, all_triangles=True)
    ax = Vector(axis).normalized()
    diag = (mx - mn).length
    eps = 0.004 * diag
    off = ax * (diag * 2.0)
    for o, w in zip(objs, verts_all):
        me = o.data
        attr = me.color_attributes.get("FidVis")
        if attr is None:
            attr = me.color_attributes.new(name="FidVis", type="FLOAT_COLOR", domain="POINT")
        n = len(me.vertices)
        vals = np.zeros(n * 4, dtype=np.float32)
        vals[3::4] = 1.0
        for i in range(n):
            p = Vector((float(w[i][0]), float(w[i][1]), float(w[i][2])))
            loc, _nor, _idx, _dist = bvh.ray_cast(p + off, -ax, diag * 4.0)
            if loc is not None and (loc - p).length <= eps:
                vals[i * 4] = 1.0
                vals[i * 4 + 1] = 1.0
                vals[i * 4 + 2] = 1.0
        attr.data.foreach_set("color", vals)


def _build_bake_material(photo_path, axis, size, center=None, depth=1.0):
    photo = bpy.data.images.load(photo_path)
    photo.colorspace_settings.name = "sRGB"
    img_c = bpy.data.images.new("fid_bake_color", size, size, alpha=True)
    img_c.generated_color = (0, 0, 0, 0)
    img_m = bpy.data.images.new("fid_bake_mask", size, size, alpha=False)
    img_m.colorspace_settings.name = "Non-Color"
    img_m.generated_color = (0, 0, 0, 1)
    mat = bpy.data.materials.new("FidelityBake")
    mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    emit = nt.nodes.new("ShaderNodeEmission")
    uvn = nt.nodes.new("ShaderNodeUVMap")
    uvn.uv_map = "FidelityProj"
    tex = nt.nodes.new("ShaderNodeTexImage")
    tex.image = photo
    tex.extension = "CLIP"
    tex.interpolation = "Cubic"
    geo = nt.nodes.new("ShaderNodeNewGeometry")
    dot = nt.nodes.new("ShaderNodeVectorMath")
    dot.operation = "DOT_PRODUCT"
    dot.inputs[1].default_value = tuple(axis)
    mx0 = nt.nodes.new("ShaderNodeMath")
    mx0.operation = "MAXIMUM"
    mx0.inputs[1].default_value = 0.0
    mul = nt.nodes.new("ShaderNodeMath")
    mul.operation = "MULTIPLY"
    nc = nt.nodes.new("ShaderNodeTexImage")
    nc.image = img_c
    nm = nt.nodes.new("ShaderNodeTexImage")
    nm.image = img_m
    nt.links.new(uvn.outputs["UV"], tex.inputs["Vector"])
    nt.links.new(geo.outputs["Normal"], dot.inputs[0])
    nt.links.new(dot.outputs["Value"], mx0.inputs[0])
    nt.links.new(mx0.outputs["Value"], mul.inputs[0])
    nt.links.new(tex.outputs["Alpha"], mul.inputs[1])
    if center is not None:
        sub = nt.nodes.new("ShaderNodeVectorMath")
        sub.operation = "SUBTRACT"
        sub.inputs[1].default_value = tuple(center)
        pdot = nt.nodes.new("ShaderNodeVectorMath")
        pdot.operation = "DOT_PRODUCT"
        pdot.inputs[1].default_value = tuple(axis)
        gate = nt.nodes.new("ShaderNodeMath")
        gate.operation = "GREATER_THAN"
        gate.inputs[1].default_value = -0.05 * float(depth)
        mul2 = nt.nodes.new("ShaderNodeMath")
        mul2.operation = "MULTIPLY"
        nt.links.new(geo.outputs["Position"], sub.inputs[0])
        nt.links.new(sub.outputs["Vector"], pdot.inputs[0])
        nt.links.new(pdot.outputs["Value"], gate.inputs[0])
        nt.links.new(mul.outputs["Value"], mul2.inputs[0])
        nt.links.new(gate.outputs["Value"], mul2.inputs[1])
        mul = mul2
    vat = nt.nodes.new("ShaderNodeAttribute")
    vat.attribute_name = "FidVis"
    mulv = nt.nodes.new("ShaderNodeMath")
    mulv.operation = "MULTIPLY"
    nt.links.new(mul.outputs["Value"], mulv.inputs[0])
    nt.links.new(vat.outputs["Fac"], mulv.inputs[1])
    mul = mulv
    nt.links.new(emit.outputs["Emission"], out.inputs["Surface"])
    return mat, nt, emit, tex, mul, nc, nm, img_c, img_m


def _bake_pass(scene, objs, nt, target_node):
    for node in nt.nodes:
        node.select = False
    target_node.select = True
    nt.nodes.active = target_node
    scene.render.bake.margin = 16
    try:
        scene.render.bake.margin_type = "EXTEND"
    except Exception:
        pass
    for o in objs:
        bpy.ops.object.select_all(action="DESELECT")
        o.select_set(True)
        bpy.context.view_layer.objects.active = o
        bpy.ops.object.bake(type="EMIT", margin=16, use_clear=False)


def _save_image(img, path):
    img.filepath_raw = path
    img.file_format = "PNG"
    img.save()


def main():
    a = _args()
    mesh = a["mesh"]
    photo = a["photo"]
    mask_path = a["mask"]
    workdir = a["workdir"]
    size = int(a.get("size", "4096"))
    os.makedirs(workdir, exist_ok=True)

    bpy.ops.wm.read_factory_settings(use_empty=True)
    print("FIDELITY_LOG:import glb...", flush=True)
    bpy.ops.import_scene.gltf(filepath=mesh)
    objs = _mesh_objects()
    if not objs:
        raise RuntimeError("no mesh objects in glb")
    faces = sum(len(o.data.polygons) for o in objs)
    for o in objs:
        if not o.data.uv_layers:
            raise RuntimeError("mesh has no uv layer")
        o.data.materials.clear()
    for img in list(bpy.data.images):
        if img.users == 0:
            bpy.data.images.remove(img)

    scene = bpy.context.scene
    _setup_cycles(scene)
    world = bpy.data.worlds.new("W")
    scene.world = world
    cam_d = bpy.data.cameras.new("Cam")
    cam = bpy.data.objects.new("Cam", cam_d)
    bpy.context.collection.objects.link(cam)
    scene.camera = cam

    mn, mx = _world_bbox(objs)
    photo_mask = _load_mask_image(mask_path)
    axis_name, scores = _detect_axis(scene, cam, mn, mx, photo_mask, workdir)
    axis = _AXES[axis_name]
    print(f"FIDELITY_LOG:axis choisi {axis_name}", flush=True)

    scene.render.use_persistent_data = False
    _write_projection_uvs(objs, axis, mn, mx)
    _write_visibility(objs, axis, mn, mx)
    _c = (mn + mx) / 2
    _d = abs((mx - mn).x * axis[0]) + abs((mx - mn).y * axis[1]) + abs((mx - mn).z * axis[2])
    mat, nt, emit, tex, mul, nc, nm, img_c, img_m = _build_bake_material(photo, axis, size, center=_c, depth=max(_d, 1e-6))
    for o in objs:
        o.data.materials.clear()
        o.data.materials.append(mat)

    print("FIDELITY_LOG:bake couleur...", flush=True)
    nt.links.new(tex.outputs["Color"], emit.inputs["Color"])
    _bake_pass(scene, objs, nt, nc)
    print("FIDELITY_LOG:bake masque...", flush=True)
    for l in list(emit.inputs["Color"].links):
        nt.links.remove(l)
    nt.links.new(mul.outputs["Value"], emit.inputs["Color"])
    _bake_pass(scene, objs, nt, nm)

    bake_color = os.path.join(workdir, "bake_color.png")
    bake_mask = os.path.join(workdir, "bake_mask.png")
    _save_image(img_c, bake_color)
    _save_image(img_m, bake_mask)

    print("FIDELITY_RESULT:" + json.dumps({
        "ok": True,
        "axis": axis_name,
        "scores": scores,
        "bake_color": bake_color,
        "bake_mask": bake_mask,
        "faces": faces,
        "size": size,
    }), flush=True)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        traceback.print_exc()
        print("FIDELITY_RESULT:" + json.dumps({"ok": False, "error": repr(exc)}), flush=True)
        sys.exit(1)
