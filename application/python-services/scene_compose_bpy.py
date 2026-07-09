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


def _opt_float(args, key):
    v = args.get(key)
    if v is None:
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


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


def verts_sum(verts, tri):
    return Vector(verts[tri[0]]) + Vector(verts[tri[1]]) + Vector(verts[tri[2]])


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


def ensure_skinning(arm, objs):
    need = [o for o in mesh_objects(objs) if len(o.vertex_groups) == 0]
    if arm is None or not need:
        return False
    dups = []
    for o in need:
        d = o.copy()
        d.data = o.data.copy()
        bpy.context.scene.collection.objects.link(d)
        if len(d.data.polygons) > 40000:
            m = d.modifiers.new("dec", "DECIMATE")
            m.ratio = 40000.0 / len(d.data.polygons)
            with bpy.context.temp_override(object=d, active_object=d, selected_editable_objects=[d]):
                bpy.ops.object.modifier_apply(modifier=m.name)
        dups.append(d)
    proxy = dups[0]
    if len(dups) > 1:
        with bpy.context.temp_override(active_object=proxy, selected_editable_objects=dups, selected_objects=dups):
            bpy.ops.object.join()
    ok = False
    try:
        with bpy.context.temp_override(active_object=arm, object=arm,
                                       selected_editable_objects=[proxy, arm],
                                       selected_objects=[proxy, arm]):
            bpy.ops.object.parent_set(type="ARMATURE_AUTO")
        ok = len(proxy.vertex_groups) > 3
    except Exception:
        ok = False
    if ok:
        for o in need:
            for vg in proxy.vertex_groups:
                if vg.name not in o.vertex_groups:
                    o.vertex_groups.new(name=vg.name)
            dt = o.modifiers.new("dt", "DATA_TRANSFER")
            dt.object = proxy
            dt.use_vert_data = True
            dt.data_types_verts = {"VGROUP_WEIGHTS"}
            dt.vert_mapping = "NEAREST"
            dt.layers_vgroup_select_src = "ALL"
            dt.layers_vgroup_select_dst = "NAME"
            with bpy.context.temp_override(object=o, active_object=o, selected_editable_objects=[o]):
                bpy.ops.object.modifier_apply(modifier=dt.name)
            am = o.modifiers.new("aurora_arm", "ARMATURE")
            am.object = arm
    try:
        bpy.data.objects.remove(proxy, do_unlink=True)
    except Exception:
        pass
    return ok


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
    def pick(bones):
        defs = [b for b in bones if b.name.lower().startswith("def-")]
        if defs:
            return defs
        clean = [b for b in bones if not any(k in b.name.lower() for k in ("org-", "mch-", "tweak", "_ik", "ik_", "_fk"))]
        return clean or bones
    return pick(thighs), pick(shins)


def force_fk(arm):
    n = 0
    for pb in arm.pose.bones:
        try:
            if "IK_FK" in pb.keys():
                pb["IK_FK"] = 1.0
                n += 1
        except Exception:
            pass
    return n


def aim_bone(pb, target_dir):
    cur = pb.tail - pb.head
    if cur.length < 1e-9 or target_dir.length < 1e-9:
        return
    q = cur.normalized().rotation_difference(target_dir.normalized())
    M = Matrix.Translation(pb.head) @ q.to_matrix().to_4x4() @ Matrix.Translation(-pb.head)
    pb.matrix = M @ pb.matrix


def set_sit_pose(arm, thighs, shins, forward):
    inv = arm.matrix_world.to_3x3().inverted()
    fa = (inv @ forward).normalized()
    da = (inv @ Vector((0.0, 0.0, -1.0))).normalized()
    for pb in thighs:
        aim_bone(pb, fa)
    bpy.context.view_layer.update()
    for pb in shins:
        aim_bone(pb, da)
    bpy.context.view_layer.update()


def clear_pose(bones):
    for pb in bones:
        pb.matrix_basis.identity()
    bpy.context.view_layer.update()


def run(args, result):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    target_objs = import_glb(args["target"])
    actor_objs = import_glb(args["actor"])
    tmin, tmax = world_bounds(target_objs)
    amin, amax = world_bounds(actor_objs)
    target_h = tmax.z - tmin.z
    actor_h = amax.z - amin.z
    relation = args.get("relation", "next_to")
    strategy = args.get("strategy")
    strategy_relations = {"legs_bent": "sit_on", "edge": "sit_on", "stand": "stand_on", "lie": "lie_on"}
    if strategy in strategy_relations:
        relation = strategy_relations[strategy]
    if strategy:
        result["strategy"] = strategy
    seat_h_frac = _opt_float(args, "seat-height-frac")
    seat_d_frac = _opt_float(args, "seat-depth-frac")
    scale_mul = _opt_float(args, "scale-mul")
    actor_root = make_root("AuroraActorRoot", actor_objs)
    if scale_mul is not None and scale_mul > 0:
        actor_root.scale = (scale_mul, scale_mul, scale_mul)
        result["scale_mul"] = scale_mul
    elif relation == "sit_on" and target_h > 1e-6 and actor_h > 1e-6:
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
        try:
            seat, group = detect_surface(target_bvh, tmin, tmax)
        except Exception:
            seat, group = None, []
        if seat_h_frac is not None:
            z = tmin.z + max(0.0, min(1.0, seat_h_frac)) * target_h
            if seat is None:
                seat = Vector(((tmin.x + tmax.x) * 0.5, (tmin.y + tmax.y) * 0.5, z))
                group = []
            else:
                seat = Vector((seat.x, seat.y, z))
            result["seat_override"] = seat_h_frac
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
    if seat_d_frac is not None and relation in ("sit_on", "stand_on", "lie_on"):
        corners = [Vector((x, y, 0.0)) for x in (tmin.x, tmax.x) for y in (tmin.y, tmax.y)]
        base2 = Vector((seat.x, seat.y, 0.0))
        projs = [(c - base2).dot(forward) for c in corners]
        pmax_p, pmin_p = max(projs), min(projs)
        off = pmax_p - max(0.0, min(1.0, seat_d_frac)) * (pmax_p - pmin_p)
        seat = seat + forward * off
        result["seat_depth_override"] = seat_d_frac
    theta = math.atan2(forward.x, -forward.y)
    if relation == "lie_on":
        actor_root.rotation_euler = (-math.pi * 0.5, 0.0, theta)
    else:
        actor_root.rotation_euler = (0.0, 0.0, theta)
    arm = find_armature(actor_objs)
    skinned = False
    if arm is not None:
        try:
            skinned = ensure_skinning(arm, actor_objs)
            bpy.context.view_layer.update()
        except Exception:
            skinned = False
    result["skin_built"] = bool(skinned)
    thighs, shins = ([], [])
    if arm is not None:
        thighs, shins = leg_bones(arm)
    posed = False
    if relation == "sit_on" and arm is not None and thighs and strategy in (None, "legs_bent"):
        try:
            force_fk(arm)
            set_sit_pose(arm, thighs, shins, forward)
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
        if posed and thighs:
            pelvis = max((arm.matrix_world @ pb.head).z for pb in thighs)
        front = 0.0
        for p in group:
            front = max(front, (p - seat).dot(forward))
        if seat_d_frac is not None:
            g2 = Vector(seat)
            push = Vector((0.0, 0.0, 1.0))
        elif posed:
            tl = 0.0
            for pb in thighs:
                tl = max(tl, ((arm.matrix_world @ pb.tail) - (arm.matrix_world @ pb.head)).length)
            pd = front - tl
            if pd < -0.4 * front:
                pd = -0.4 * front
            if pd > 0.6 * front:
                pd = 0.6 * front
            g2 = seat + forward * pd
            push = Vector((0.0, 0.0, 1.0))
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
    tol = max(60, int(0.004 * len(atris)))
    best_shift = Vector(shift)
    best_pairs = None
    pairs0 = target_bvh.overlap(shifted_bvh(averts, atris, shift))
    if pairs0:
        cs = []
        for _pa, pb2 in pairs0[:300]:
            tri = atris[pb2] if pb2 < len(atris) else atris[0]
            cs.append(verts_sum(averts, tri) / 3.0 + shift)
        result["overlap_zone0"] = {"n": len(pairs0),
                                   "x": [round(min(c.x for c in cs), 2), round(max(c.x for c in cs), 2)],
                                   "y": [round(min(c.y for c in cs), 2), round(max(c.y for c in cs), 2)],
                                   "z": [round(min(c.z for c in cs), 2), round(max(c.z for c in cs), 2)]}
    for i in range(40):
        p = len(target_bvh.overlap(shifted_bvh(averts, atris, shift)))
        if best_pairs is None or p < best_pairs:
            best_pairs = p
            best_shift = Vector(shift)
        if p <= tol:
            break
        shift = shift + push * step
        fixed += 1
    if best_pairs is not None and best_pairs > tol:
        shift = best_shift
        result["fit"] = "partial"
    else:
        result["fit"] = "ok"
    actor_root.location = base + shift
    bpy.context.view_layer.update()
    result["overlap_fixed"] = fixed
    pairs = target_bvh.overlap(shifted_bvh(averts, atris, shift))
    if pairs:
        cs = []
        for _pa, pb2 in pairs[:300]:
            tri = atris[pb2] if pb2 < len(atris) else atris[0]
            c = (verts_sum(averts, tri)) / 3.0 + shift
            cs.append(c)
        xs = [round(c.x, 2) for c in cs]
        ys = [round(c.y, 2) for c in cs]
        zz = [round(c.z, 2) for c in cs]
        result["overlap_zone"] = {"n": len(pairs),
                                  "x": [min(xs), max(xs)], "y": [min(ys), max(ys)],
                                  "z": [min(zz), max(zz)]}
    if relation == "sit_on" and posed and len(pairs) > tol and strategy != "legs_bent":
        clear_pose(thighs + shins)
        posed = False
        result["posed"] = False
        result["sit_fallback"] = "edge"
        amin, amax = world_bounds(actor_objs)
        acenter = (amin + amax) * 0.5
        actor_h = amax.z - amin.z
        pelvis = amin.z + 0.45 * actor_h
        cv2, _c2 = proxy_capture(actor_objs, 40000)
        lo = amin.z + 0.35 * actor_h
        hi = amin.z + 0.55 * actor_h
        band = [v for v in cv2 if lo <= v.z <= hi]
        if band:
            column = Vector((sum(v.x for v in band) / len(band), sum(v.y for v in band) / len(band), 0.0))
        else:
            column = Vector((acenter.x, acenter.y, 0.0))
        projs = sorted((v - seat).dot(forward) for v in band) if band else []
        if len(projs) >= 10:
            bd = projs[int(0.9 * (len(projs) - 1))] - projs[int(0.1 * (len(projs) - 1))]
        else:
            bd = 0.3 * actor_h
        g2 = seat + forward * (front + 0.30 * bd)
        base = Vector((g2.x - column.x, g2.y - column.y, seat.z + 0.005 * actor_h - pelvis))
        actor_root.location = base
        bpy.context.view_layer.update()
        averts, atris = proxy_capture(actor_objs, 40000)
        shift = Vector((0.0, 0.0, 0.0))
        push = Vector((0.0, 0.0, 1.0))
        best_shift = Vector(shift)
        best_pairs = None
        for i in range(40):
            p = len(target_bvh.overlap(shifted_bvh(averts, atris, shift)))
            if best_pairs is None or p < best_pairs:
                best_pairs = p
                best_shift = Vector(shift)
            if p <= tol:
                break
            shift = shift + push * step
            fixed += 1
        if best_pairs is not None and best_pairs > tol:
            shift = best_shift
            result["fit"] = "partial"
        else:
            result["fit"] = "ok"
        actor_root.location = base + shift
        bpy.context.view_layer.update()
        result["overlap_fixed"] = fixed
    if relation in ("sit_on", "stand_on", "lie_on"):
        down = Vector((0.0, 0.0, -1.0))
        settle = Vector((0.0, 0.0, 0.0))
        if len(target_bvh.overlap(shifted_bvh(averts, atris, shift))) <= tol:
            for _i in range(60):
                trial = settle + down * step
                if len(target_bvh.overlap(shifted_bvh(averts, atris, shift + trial))) > tol:
                    break
                settle = trial
                if abs(settle.z) > actor_h:
                    break
            actor_root.location = base + shift + settle
            bpy.context.view_layer.update()
    dz_frac = _opt_float(args, "dz-frac")
    dfwd_frac = _opt_float(args, "dfwd-frac")
    extra = Vector((0.0, 0.0, 0.0))
    if dz_frac:
        extra = extra + Vector((0.0, 0.0, max(-1.0, min(1.0, dz_frac)) * target_h))
    if dfwd_frac:
        span = max(tmax.x - tmin.x, tmax.y - tmin.y, 1e-6)
        extra = extra + forward * (max(-1.0, min(1.0, dfwd_frac)) * span)
    if extra.length > 1e-9:
        actor_root.location = actor_root.location + extra
        bpy.context.view_layer.update()
        result["offset_applied"] = [round(extra.x, 4), round(extra.y, 4), round(extra.z, 4)]
    amin, amax = world_bounds(actor_objs)
    if relation == "sit_on":
        pelvis = amin.z + 0.45 * (amax.z - amin.z)
        if posed and thighs:
            pelvis = max((arm.matrix_world @ pb.head).z for pb in thighs)
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
            clear_pose(thighs + shins)
            for pb in thighs + shins:
                pb.keyframe_insert("rotation_quaternion", frame=1)
                pb.keyframe_insert("rotation_quaternion", frame=mid)
            set_sit_pose(arm, thighs, shins, forward)
            for pb in thighs + shins:
                pb.keyframe_insert("rotation_quaternion", frame=end)
        scene.frame_set(end)
        result["animated"] = True
    if posed and not args["animate"]:
        dg = bpy.context.evaluated_depsgraph_get()
        for o in mesh_objects(actor_objs):
            try:
                ev = o.evaluated_get(dg)
                me = bpy.data.meshes.new_from_object(ev)
                o.modifiers.clear()
                o.data = me
            except Exception:
                pass
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
