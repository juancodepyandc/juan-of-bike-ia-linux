"""Compose une scene GLB multi-objets dans Blender headless."""
import bpy
import sys
import os
import json
import math
import traceback
from mathutils import Vector, Matrix
from mathutils.bvhtree import BVHTree


def parse_args():
    argv = sys.argv[sys.argv.index("--") + 1:]
    args = {"animate": False, "fps": 24}
    i = 0
    while i < len(argv):
        a = argv[i]
        if a == "--animate":
            args["animate"] = True
            i += 1
        elif a.startswith("--") and i + 1 < len(argv):
            args[a[2:]] = argv[i + 1]
            i += 2
        else:
            i += 1
    args["fps"] = int(args["fps"])
    return args


def import_glb(path):
    before = set(bpy.data.objects)
    bpy.ops.import_scene.gltf(filepath=path)
    return [o for o in bpy.data.objects if o not in before]


def mesh_objects(objs):
    return [o for o in objs if o.type == "MESH"]


def world_bounds(objs):
    bpy.context.view_layer.update()
    mn = Vector((1e18, 1e18, 1e18))
    mx = Vector((-1e18, -1e18, -1e18))
    for o in mesh_objects(objs):
        for c in o.bound_box:
            w = o.matrix_world @ Vector(c)
            for i in range(3):
                mn[i] = min(mn[i], w[i])
                mx[i] = max(mx[i], w[i])
    return mn, mx


def proxy_capture(objs, budget):
    meshes = mesh_objects(objs)
    total = sum(len(o.data.polygons) for o in meshes)
    ratio = min(1.0, float(budget) / max(total, 1))
    verts = []
    tris = []
    for o in meshes:
        if len(o.data.polygons) == 0:
            continue
        dup = o.copy()
        bpy.context.scene.collection.objects.link(dup)
        if ratio < 1.0 and len(o.data.polygons) > 1000:
            mod = dup.modifiers.new("aurora_dec", "DECIMATE")
            mod.ratio = ratio
        bpy.context.view_layer.update()
        deps = bpy.context.evaluated_depsgraph_get()
        ev = dup.evaluated_get(deps)
        me = ev.to_mesh()
        me.calc_loop_triangles()
        mw = ev.matrix_world.copy()
        base = len(verts)
        verts.extend([mw @ v.co for v in me.vertices])
        tris.extend([(t.vertices[0] + base, t.vertices[1] + base, t.vertices[2] + base) for t in me.loop_triangles])
        ev.to_mesh_clear()
        bpy.data.objects.remove(dup, do_unlink=True)
    bpy.context.view_layer.update()
    return verts, tris


def shifted_bvh(verts, tris, shift):
    return BVHTree.FromPolygons([v + shift for v in verts], tris, all_triangles=True)


def group_center(group):
    cx = sum(p.x for p in group) / len(group)
    cy = sum(p.y for p in group) / len(group)
    zs = sorted(p.z for p in group)
    return Vector((cx, cy, zs[min(int(len(zs) * 0.8), len(zs) - 1)]))


def detect_surface(bvh, tmin, tmax):
    n = 26
    h = max(tmax.z - tmin.z, 1e-6)
    fx = max(tmax.x - tmin.x, 1e-6)
    fy = max(tmax.y - tmin.y, 1e-6)
    cell = (fx / n) * (fy / n)
    hits = []
    for ix in range(n):
        for iy in range(n):
            x = tmin.x + fx * (ix + 0.5) / n
            y = tmin.y + fy * (iy + 0.5) / n
            origin = Vector((x, y, tmax.z + h * 0.25))
            loc, nor, idx, dist = bvh.ray_cast(origin, Vector((0.0, 0.0, -1.0)), h * 1.6)
            if loc is not None and nor is not None and abs(nor.z) > 0.8:
                hits.append(loc)
    if not hits:
        return None, []
    need = 0.15 * fx * fy
    binh = max(h * 0.04, 0.004)
    levels = sorted({round(p.z / binh) for p in hits}, reverse=True)
    for lv in levels:
        zc = lv * binh
        group = [p for p in hits if abs(p.z - zc) <= binh]
        if len(group) * cell >= need:
            return group_center(group), group
    top = max(p.z for p in hits)
    group = [p for p in hits if p.z >= top - binh * 2]
    return group_center(group), group


def find_back_dir(bvh, seat, tmin, tmax):
    if tmax.z - seat.z < 0.05 * max(tmax.z - tmin.z, 1e-6):
        return None
    zp = seat.z + (tmax.z - seat.z) * 0.5
    reach = max(tmax.x - tmin.x, tmax.y - tmin.y) * 1.2
    best = None
    bestd = 1e18
    for k in range(24):
        ang = 2.0 * math.pi * k / 24.0
        d = Vector((math.cos(ang), math.sin(ang), 0.0))
        loc, nor, idx, dist = bvh.ray_cast(Vector((seat.x, seat.y, zp)), d, reach)
        if loc is not None and dist is not None and dist < bestd:
            bestd = dist
            best = d.copy()
    return best


def make_root(name, objs):
    root = bpy.data.objects.new(name, None)
    bpy.context.scene.collection.objects.link(root)
    for o in objs:
        if o.parent is None:
            o.parent = root
            o.matrix_parent_inverse = Matrix.Identity(4)
    bpy.context.view_layer.update()
    return root


def find_armature(objs):
    for o in objs:
        if o.type == "ARMATURE":
            return o
    return None


def leg_bones(arm):
    thighs = []
    shins = []
    for pb in arm.pose.bones:
        low = pb.name.lower()
        if any(k in low for k in ("thigh", "upleg", "upper_leg", "upperleg")):
            thighs.append(pb)
        elif any(k in low for k in ("shin", "calf", "lowerleg", "lower_leg", "loleg")):
            shins.append(pb)
    return thighs, shins


def set_sit_pose(thighs, shins, factor):
    for pb in thighs:
        pb.rotation_mode = "XYZ"
        pb.rotation_euler = (-math.pi * 0.5 * factor, 0.0, 0.0)
    for pb in shins:
        pb.rotation_mode = "XYZ"
        pb.rotation_euler = (math.pi * 0.5 * factor, 0.0, 0.0)


def run(args, result):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    target_objs = import_glb(args["target"])
    actor_objs = import_glb(args["actor"])
    tmin, tmax = world_bounds(target_objs)
    amin, amax = world_bounds(actor_objs)
    target_h = tmax.z - tmin.z
    actor_h = amax.z - amin.z
    relation = args.get("relation", "next_to")
    actor_root = make_root("AuroraActorRoot", actor_objs)
    if relation == "sit_on" and target_h > 1e-6 and actor_h > 1e-6:
        ratio = actor_h / target_h
        if ratio > 2.2 or ratio < 0.5:
            s = 1.65 / actor_h
            actor_root.scale = (s, s, s)
    amin, amax = world_bounds(actor_objs)
    actor_h = amax.z - amin.z
    result["actor_height"] = round(actor_h, 4)
    result["target_height"] = round(target_h, 4)
    tverts, ttris = proxy_capture(target_objs, 60000)
    target_bvh = BVHTree.FromPolygons(tverts, ttris, all_triangles=True)
    seat = None
    group = []
    if relation in ("sit_on", "stand_on", "lie_on"):
        seat, group = detect_surface(target_bvh, tmin, tmax)
        if seat is None:
            raise RuntimeError("aucune surface horizontale detectee sur le target")
        result["seat_height"] = round(seat.z, 4)
    forward = Vector((1.0, 0.0, 0.0))
    if relation in ("sit_on", "stand_on", "lie_on"):
        back = find_back_dir(target_bvh, seat, tmin, tmax)
        if back is not None and back.length > 1e-6:
            forward = Vector((-back.x, -back.y, 0.0)).normalized()
    elif relation in ("next_to", "hold"):
        forward = Vector((-1.0, 0.0, 0.0))
    theta = math.atan2(forward.x, -forward.y)
    if relation == "lie_on":
        actor_root.rotation_euler = (-math.pi * 0.5, 0.0, theta)
    else:
        actor_root.rotation_euler = (0.0, 0.0, theta)
    arm = find_armature(actor_objs)
    thighs, shins = ([], [])
    if arm is not None:
        thighs, shins = leg_bones(arm)
    posed = False
    if relation == "sit_on" and arm is not None and thighs:
        try:
            set_sit_pose(thighs, shins, 1.0)
            posed = True
        except Exception:
            posed = False
    result["has_armature"] = bool(arm is not None)
    result["posed"] = bool(posed)
    amin, amax = world_bounds(actor_objs)
    acenter = (amin + amax) * 0.5
    actor_h = amax.z - amin.z
    step = 0.02 * max(actor_h, 1e-6)
    cverts, _ctris = proxy_capture(actor_objs, 40000)
    lo = amin.z + 0.35 * actor_h
    hi = amin.z + 0.55 * actor_h
    band = [v for v in cverts if lo <= v.z <= hi]
    if band:
        column = Vector((sum(v.x for v in band) / len(band), sum(v.y for v in band) / len(band), 0.0))
    else:
        column = Vector((acenter.x, acenter.y, 0.0))
    if relation == "sit_on":
        pelvis = amin.z + 0.45 * actor_h
        front = 0.0
        for p in group:
            front = max(front, (p - seat).dot(forward))
        if posed:
            g2 = seat + forward * (front * 0.35)
            push = forward.copy()
        else:
            projs = sorted((v - seat).dot(forward) for v in band) if band else []
            if len(projs) >= 10:
                bd = projs[int(0.9 * (len(projs) - 1))] - projs[int(0.1 * (len(projs) - 1))]
            else:
                bd = 0.3 * actor_h
            g2 = seat + forward * (front + 0.30 * bd)
            push = Vector((0.0, 0.0, 1.0))
        goal = Vector((g2.x, g2.y, 0.0))
        base = Vector((goal.x - column.x, goal.y - column.y, seat.z + 0.005 * actor_h - pelvis))
    elif relation in ("stand_on", "lie_on"):
        base = Vector((seat.x - acenter.x, seat.y - acenter.y, seat.z + 0.005 * actor_h - amin.z))
        push = Vector((0.0, 0.0, 1.0))
    else:
        width = tmax.x - tmin.x
        gap = 0.1 * width if relation == "next_to" else 0.02 * width
        cx = tmax.x + gap + (amax.x - amin.x) * 0.5
        cy = (tmin.y + tmax.y) * 0.5
        base = Vector((cx - acenter.x, cy - acenter.y, tmin.z - amin.z))
        push = Vector((1.0, 0.0, 0.0))
    actor_root.location = base
    bpy.context.view_layer.update()
    averts, atris = proxy_capture(actor_objs, 40000)
    shift = Vector((0.0, 0.0, 0.0))
    fixed = 0
    for i in range(40):
        abvh = shifted_bvh(averts, atris, shift)
        if not target_bvh.overlap(abvh):
            break
        shift = shift + push * step
        fixed += 1
    actor_root.location = base + shift
    bpy.context.view_layer.update()
    result["overlap_fixed"] = fixed
    if relation in ("sit_on", "stand_on", "lie_on"):
        down = Vector((0.0, 0.0, -1.0))
        settle = Vector((0.0, 0.0, 0.0))
        if not target_bvh.overlap(shifted_bvh(averts, atris, shift)):
            for _i in range(60):
                trial = settle + down * step
                if target_bvh.overlap(shifted_bvh(averts, atris, shift + trial)):
                    break
                settle = trial
                if abs(settle.z) > actor_h:
                    break
            actor_root.location = base + shift + settle
            bpy.context.view_layer.update()
    amin, amax = world_bounds(actor_objs)
    if relation == "sit_on":
        pelvis = amin.z + 0.45 * (amax.z - amin.z)
        result["contact_gap"] = round(abs(pelvis - seat.z), 4)
    elif relation in ("stand_on", "lie_on"):
        result["contact_gap"] = round(abs(amin.z - seat.z), 4)
    else:
        result["contact_gap"] = round(abs(amin.z - tmin.z), 4)
    if relation == "hold":
        troot = make_root("AuroraTargetRoot", target_objs)
        hand = Vector(((amin.x + amax.x) * 0.5, (amin.y + amax.y) * 0.5, amin.z + 0.72 * (amax.z - amin.z)))
        hand = hand + forward * (0.25 * max(amax.x - amin.x, amax.y - amin.y))
        tcen = (tmin + tmax) * 0.5
        troot.location = hand - tcen
        bpy.context.view_layer.update()
        result["contact_gap"] = 0.0
    if args["animate"]:
        scene = bpy.context.scene
        scene.render.fps = args["fps"]
        end = max(int(round(args["fps"] * 3)), 10)
        mid = max(int(round(end * 40.0 / 72.0)), 2)
        scene.frame_start = 1
        scene.frame_end = end
        try:
            bpy.context.preferences.edit.keyframe_new_interpolation_type = "BEZIER"
        except Exception:
            pass
        final = actor_root.location.copy()
        amin, amax = world_bounds(actor_objs)
        ground_dz = tmin.z - amin.z
        start = final + forward * (0.8 * max(actor_h, 0.5)) + Vector((0.0, 0.0, ground_dz))
        approach = Vector((final.x, final.y, final.z + ground_dz))
        actor_root.location = start
        actor_root.keyframe_insert("location", frame=1)
        actor_root.location = approach
        actor_root.keyframe_insert("location", frame=mid)
        actor_root.location = final
        actor_root.keyframe_insert("location", frame=end)
        if posed:
            set_sit_pose(thighs, shins, 0.0)
            for pb in thighs + shins:
                pb.keyframe_insert("rotation_euler", frame=1)
                pb.keyframe_insert("rotation_euler", frame=mid)
            set_sit_pose(thighs, shins, 1.0)
            for pb in thighs + shins:
                pb.keyframe_insert("rotation_euler", frame=end)
        scene.frame_set(end)
        result["animated"] = True
    out = args["output"]
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    bpy.ops.export_scene.gltf(filepath=out, export_format="GLB", export_animations=True, export_yup=True)


def main():
    args = parse_args()
    result = {"ok": False, "seat_height": None, "contact_gap": None,
              "overlap_fixed": 0, "has_armature": False, "animated": False}
    try:
        run(args, result)
        result["ok"] = True
    except Exception as exc:
        traceback.print_exc(file=sys.stderr)
        result["error"] = "%s: %s" % (type(exc).__name__, exc)
    print("SCENE_RESULT:" + json.dumps(result))
    sys.stdout.flush()


main()
