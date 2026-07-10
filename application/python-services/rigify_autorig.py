"""rigify_autorig — auto-rigs a humanoid GLB using Blender + Rigify addon.

Design:
  - Detects `blender` on PATH or common Windows install directories
  - If missing → returns actionable JSON telling the user to install Blender
  - Otherwise runs Blender in background with an embedded Python script that:
      1. imports the input GLB
      2. enables the "Rigify" addon (bundled with Blender)
      3. adds a human meta-rig, scales it to match the mesh bbox
      4. generates the rig
      5. parents the mesh to the rig with "Armature Deform With Automatic Weights"
      6. exports the result as GLB with animations-ready bones

Usage :
  python rigify_autorig.py --input model.glb --output rigged.glb
"""
import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parent.parent

BLENDER_CANDIDATES = [
    r"C:\Program Files\Blender Foundation\Blender 5.1\blender.exe",
    r"C:\Program Files\Blender Foundation\Blender 5.0\blender.exe",
    r"C:\Program Files\Blender Foundation\Blender 4.4\blender.exe",
    r"C:\Program Files\Blender Foundation\Blender 4.3\blender.exe",
    r"C:\Program Files\Blender Foundation\Blender 4.2\blender.exe",
    r"C:\Program Files\Blender Foundation\Blender 4.1\blender.exe",
    r"C:\Program Files\Blender Foundation\Blender 4.0\blender.exe",
    r"C:\Program Files\Blender Foundation\Blender 3.6\blender.exe",
    r"/Applications/Blender.app/Contents/MacOS/Blender",
    r"/usr/bin/blender",
    r"/usr/local/bin/blender",
]


def find_blender() -> str | None:
    # 0. portable Blender shipped under application/_blender/
    for portable in (WORKSPACE / "_blender").glob("blender-*-windows-x64"):
        exe = portable / "blender.exe"
        if exe.is_file():
            return str(exe)
    # 1. PATH
    found = shutil.which("blender")
    if found:
        return found
    # 2. Well-known Windows paths
    for cand in BLENDER_CANDIDATES:
        if os.path.isfile(cand):
            return cand
    return None


# -------------------- embedded Blender Python --------------------
# Saved to disk then passed via `blender --python <file>`
BLENDER_SCRIPT = r'''
import bpy, sys, os
argv = sys.argv
if "--" in argv:
    argv = argv[argv.index("--") + 1:]
else:
    argv = []
input_glb  = argv[0] if len(argv) > 0 else ""
output_glb = argv[1] if len(argv) > 1 else ""
if not input_glb or not os.path.isfile(input_glb):
    print("RIGIFY_ERROR: input GLB missing: %s" % input_glb)
    sys.exit(2)

# Clean default scene
bpy.ops.object.select_all(action="SELECT")
bpy.ops.object.delete(use_global=False, confirm=False)

# Import GLB
bpy.ops.import_scene.gltf(filepath=input_glb)
meshes = [o for o in bpy.context.scene.objects if o.type == "MESH"]
if not meshes:
    print("RIGIFY_ERROR: no MESH in the imported GLB")
    sys.exit(3)

# Apply smooth shading to all meshes to fix faceted appearance
for m in meshes:
    bpy.ops.object.select_all(action="DESELECT")
    m.select_set(True)
    bpy.context.view_layer.objects.active = m
    bpy.ops.object.shade_smooth()

# Enable Rigify (bundled addon)
try:
    bpy.ops.preferences.addon_enable(module="rigify")
except Exception as e:
    print("RIGIFY_ERROR: cannot enable Rigify addon: %s" % e)
    sys.exit(4)

metarig_kind = argv[3] if len(argv) > 3 else "human"
orig_mesh_names = set(o.name for o in meshes)
if metarig_kind == "quadruped":
    try:
        bpy.ops.object.armature_wolf_metarig_add()
    except Exception:
        bpy.ops.object.armature_basic_quadruped_metarig_add()
else:
    bpy.ops.object.armature_human_metarig_add()
metarig = bpy.context.object
metarig.name = "aurora_metarig"
print("RIGIFY_INFO: metarig %s" % metarig_kind)

# Compute mesh bounding box height, scale metarig to match
import mathutils, math
mesh = meshes[0]
mn = mathutils.Vector((1e18,) * 3)
mx = mathutils.Vector((-1e18,) * 3)
for mo in meshes:
    for corner in mo.bound_box:
        w = mo.matrix_world @ mathutils.Vector(corner)
        mn = mathutils.Vector(map(min, mn, w))
        mx = mathutils.Vector(map(max, mx, w))
height = mx.z - mn.z
mh = max((max(b.head_local.z, b.tail_local.z) for b in metarig.data.bones), default=0.0)
if height > 0.01 and mh > 0.01:
    f = height / mh
    metarig.scale = (f, f, f)
    if metarig_kind == "quadruped" and (mx.x - mn.x) > (mx.y - mn.y):
        metarig.rotation_euler = (0.0, 0.0, math.radians(90.0))
    bpy.ops.object.select_all(action="DESELECT")
    metarig.select_set(True)
    bpy.context.view_layer.objects.active = metarig
    bpy.ops.object.transform_apply(location=False, rotation=True, scale=True)
    import numpy as np
    _vs = mesh.data.vertices
    _co = np.empty(len(_vs) * 3, dtype=np.float64)
    _vs.foreach_get("co", _co)
    _co = _co.reshape(-1, 3)[::max(1, len(_vs) // 50000)]
    _mw = np.array(mesh.matrix_world)
    _w = _co @ _mw[:3, :3].T + _mw[:3, 3]
    flip = False
    if metarig_kind == "quadruped":
        _ymid = (_w[:, 1].min() + _w[:, 1].max()) / 2.0
        _front = _w[_w[:, 1] > _ymid]
        _back = _w[_w[:, 1] <= _ymid]
        if len(_front) > 50 and len(_back) > 50:
            mesh_head_dir = 1.0 if np.percentile(_front[:, 2], 95) >= np.percentile(_back[:, 2], 95) else -1.0
            hb = metarig.data.bones.get("head")
            if hb is not None:
                rig_head_dir = 1.0 if hb.head_local.y >= 0 else -1.0
                flip = mesh_head_dir != rig_head_dir
    else:
        _z5 = np.percentile(_w[:, 2], 5)
        _low = _w[_w[:, 2] <= _z5 + 0.03 * height]
        if len(_low) > 50:
            mesh_front_dir = 1.0 if (_low[:, 1].mean() - _w[:, 1].mean()) > 0 else -1.0
            tb = metarig.data.bones.get("toe.L") or metarig.data.bones.get("foot.L")
            if tb is not None:
                rig_front_dir = 1.0 if (tb.tail_local.y - tb.head_local.y) >= 0 else -1.0
                flip = mesh_front_dir != rig_front_dir
    if flip:
        metarig.rotation_euler = (0.0, 0.0, math.radians(180.0))
        bpy.ops.object.transform_apply(location=False, rotation=True, scale=False)
        print("RIGIFY_INFO: metarig retourne 180 (orientation avant/arriere detectee)")
    metarig.location = ((mn.x + mx.x) / 2.0, (mn.y + mx.y) / 2.0, mn.z)
    bpy.ops.object.select_all(action="DESELECT")
    metarig.select_set(True)
    bpy.context.view_layer.objects.active = metarig
    bpy.ops.object.transform_apply(location=True, rotation=False, scale=False)
    print("RIGIFY_INFO: metarig ajuste: hauteur mesh %.3f, facteur %.3f" % (height, f))

if metarig_kind != "quadruped":
    bpy.context.view_layer.objects.active = metarig
    bpy.ops.object.mode_set(mode="EDIT")
    eb = metarig.data.edit_bones
    arm_prefixes = ("upper_arm", "forearm", "hand", "palm", "thumb",
                    "f_index", "f_middle", "f_ring", "f_pinky")
    for side, sgn in (("L", 1.0), ("R", -1.0)):
        ua = eb.get("upper_arm.%s" % side)
        if ua is None:
            continue
        pivot = ua.head.copy()
        rot = mathutils.Matrix.Rotation(math.radians(55.0) * sgn, 4, "Y")
        for b in eb:
            if not b.name.endswith(side):
                continue
            if any(b.name.startswith(p) for p in arm_prefixes):
                b.head = rot @ (b.head - pivot) + pivot
                b.tail = rot @ (b.tail - pivot) + pivot
    bpy.ops.object.mode_set(mode="OBJECT")
    print("RIGIFY_INFO: bras metarig abaisses en A-pose")

# Generate the rig via Rigify
bpy.context.view_layer.objects.active = metarig
try:
    bpy.ops.pose.rigify_generate()
except Exception as e:
    print("RIGIFY_ERROR: rigify_generate failed: %s" % e)
    sys.exit(5)

# v77zal: Rigify naming changed in Blender 5.1 — the generated rig may be
# named "RIG-aurora_metarig", "rig_aurora", "rig", or just inherit a custom
# name. Find the rig as "any armature that is NOT our metarig", which is the
# robust convention across all Blender versions.
all_armatures = [o for o in bpy.context.scene.objects if o.type == "ARMATURE"]
rig_candidates = [o for o in all_armatures if o.name != "aurora_metarig" and "metarig" not in o.name.lower()]
if not rig_candidates:
    # Fallback: prefer one that starts with "rig" (legacy convention)
    rig_candidates = [o for o in all_armatures if o.name.lower().startswith("rig")]
if not rig_candidates:
    armature_names = [o.name for o in all_armatures]
    print("RIGIFY_ERROR: generated rig not found among armatures: %s" % armature_names)
    sys.exit(6)
rig = rig_candidates[0]
print("RIGIFY_INFO: generated rig found: %s" % rig.name)

# v77zal: Blender 5.1 — rigify_generate leaves us in POSE mode. Force OBJECT
# mode before select_all to avoid "context is incorrect" runtime error.
try:
    if bpy.context.mode != "OBJECT":
        bpy.ops.object.mode_set(mode="OBJECT")
except Exception:
    pass

# Parent mesh to rig with automatic weights
bpy.ops.object.select_all(action="DESELECT")
mesh.select_set(True)
rig.select_set(True)
bpy.context.view_layer.objects.active = rig
try:
    bpy.ops.object.parent_set(type="ARMATURE_AUTO")
except Exception as e:
    print("RIGIFY_ERROR: parenting failed: %s" % e)
    sys.exit(7)


def _skin_ok(m):
    if len(m.vertex_groups) < 4:
        return False
    vs = m.data.vertices
    step = max(1, len(vs) // 2000)
    idx = range(0, len(vs), step)
    counted = sum(1 for i in idx if len(vs[i].groups))
    return counted > len(idx) * 0.25


if not _skin_ok(mesh):
    print("RIGIFY_INFO: bone-heat vide (mesh dense) -> proxy decime + transfert de poids")
    dup = mesh.copy()
    dup.data = mesh.data.copy()
    bpy.context.scene.collection.objects.link(dup)
    for vg in list(dup.vertex_groups):
        dup.vertex_groups.remove(vg)
    for m2 in list(dup.modifiers):
        dup.modifiers.remove(m2)
    if len(dup.data.polygons) > 40000:
        dec = dup.modifiers.new("dec", "DECIMATE")
        dec.ratio = 40000.0 / len(dup.data.polygons)
        with bpy.context.temp_override(object=dup, active_object=dup, selected_editable_objects=[dup]):
            bpy.ops.object.modifier_apply(modifier=dec.name)
    rm = dup.modifiers.new("rm", "REMESH")
    rm.mode = "VOXEL"
    rm.voxel_size = max(max(dup.dimensions) / 60.0, 0.004)
    with bpy.context.temp_override(object=dup, active_object=dup, selected_editable_objects=[dup]):
        bpy.ops.object.modifier_apply(modifier=rm.name)
    if len(dup.data.polygons) > 60000:
        dec2 = dup.modifiers.new("dec2", "DECIMATE")
        dec2.ratio = 60000.0 / len(dup.data.polygons)
        with bpy.context.temp_override(object=dup, active_object=dup, selected_editable_objects=[dup]):
            bpy.ops.object.modifier_apply(modifier=dec2.name)
    try:
        _before_names = set(o.name for o in bpy.context.scene.objects)
        bpy.ops.object.select_all(action="DESELECT")
        dup.select_set(True)
        bpy.context.view_layer.objects.active = dup
        bpy.ops.object.mode_set(mode="EDIT")
        bpy.ops.mesh.select_all(action="SELECT")
        bpy.ops.mesh.separate(type="LOOSE")
        bpy.ops.object.mode_set(mode="OBJECT")
        _parts = [o for o in bpy.context.scene.objects
                  if o.type == "MESH" and (o == dup or o.name not in _before_names)]
        if len(_parts) > 1:
            _parts.sort(key=lambda o: len(o.data.polygons), reverse=True)
            dup = _parts[0]
            for o in _parts[1:]:
                bpy.data.objects.remove(o, do_unlink=True)
            print("RIGIFY_INFO: proxy: %d ilots supprimes, plus grande composante gardee (%d polys)"
                  % (len(_parts) - 1, len(dup.data.polygons)))
    except Exception as _ie:
        print("RIGIFY_INFO: separation ilots echec: %s" % _ie)
    print("RIGIFY_INFO: proxy remesh manifold: %d polys" % len(dup.data.polygons))
    ok_proxy = False
    try:
        with bpy.context.temp_override(active_object=rig, object=rig,
                                       selected_editable_objects=[dup, rig],
                                       selected_objects=[dup, rig]):
            bpy.ops.object.parent_set(type="ARMATURE_AUTO")
        ok_proxy = _skin_ok(dup)
    except Exception as e:
        print("RIGIFY_INFO: bone-heat proxy echec: %s" % e)
    if ok_proxy:
        import bmesh
        from mathutils.bvhtree import BVHTree
        for vg in list(mesh.vertex_groups):
            mesh.vertex_groups.remove(vg)
        gidx_map = {}
        for vg in dup.vertex_groups:
            gidx_map[vg.index] = mesh.vertex_groups.new(name=vg.name).index
        proxy_w = [{g.group: g.weight for g in v.groups if g.weight > 0.005}
                   for v in dup.data.vertices]
        dg = bpy.context.evaluated_depsgraph_get()
        bvh = BVHTree.FromObject(dup, dg)
        polys = dup.data.polygons
        pverts = dup.data.vertices
        xf = dup.matrix_world.inverted() @ mesh.matrix_world
        bm = bmesh.new()
        bm.from_mesh(mesh.data)
        dl = bm.verts.layers.deform.verify()
        assigned = 0
        for v in bm.verts:
            loc, _n, fi, _d = bvh.find_nearest(xf @ v.co)
            if fi is None:
                continue
            acc = {}
            tot = 0.0
            for pv in polys[fi].vertices:
                d = (pverts[pv].co - loc).length + 1e-8
                w = 1.0 / d
                tot += w
                for gi, gw in proxy_w[pv].items():
                    acc[gi] = acc.get(gi, 0.0) + w * gw
            if tot <= 0.0:
                continue
            inv = 1.0 / tot
            dv = v[dl]
            wrote = False
            for gi, gw in acc.items():
                val = gw * inv
                if val > 0.01 and gi in gidx_map:
                    dv[gidx_map[gi]] = val
                    wrote = True
            if wrote:
                assigned += 1
        bm.to_mesh(mesh.data)
        bm.free()
        has_arm = any(m2.type == "ARMATURE" for m2 in mesh.modifiers)
        if not has_arm:
            am = mesh.modifiers.new("aurora_arm", "ARMATURE")
            am.object = rig
        print("RIGIFY_INFO: transfert barycentrique BVH applique (%d/%d verts, %d groupes)"
              % (assigned, len(mesh.data.vertices), len(mesh.vertex_groups)))
    try:
        bpy.data.objects.remove(dup, do_unlink=True)
    except Exception:
        pass

    def _proximity_assign(idxs):
        import numpy as np
        inv = mesh.matrix_world.inverted()
        arm_mw = rig.matrix_world
        minor = ("toe", "ear", "jaw", "tongue", "teeth", "eye", "brow", "lip",
                 "cheek", "nose", "forehead", "temple", "chin", "thumb",
                 "f_index", "f_middle", "f_ring", "f_pinky", "palm", "r_", "f_",
                 "breast", "pelvis")
        bones = [b for b in rig.data.bones if b.use_deform
                 and not any(b.name.lower().replace("def-", "").startswith(p) for p in minor)]
        if len(bones) < 4:
            bones = [b for b in rig.data.bones if b.use_deform] or list(rig.data.bones)
        n_all = len(mesh.data.vertices)
        co = np.empty(n_all * 3, dtype=np.float64)
        mesh.data.vertices.foreach_get("co", co)
        co = co.reshape(n_all, 3)
        sel = np.asarray(idxs, dtype=np.int64)
        co = co[sel]
        n = len(sel)
        K = 4
        dk = np.full((n, K), 1e18)
        ik = np.zeros((n, K), dtype=np.int32)
        for bi, b in enumerate(bones):
            h = np.array(inv @ (arm_mw @ b.head_local))
            t = np.array(inv @ (arm_mw @ b.tail_local))
            ab = t - h
            denom = float(ab.dot(ab)) or 1e-12
            tt = np.clip(((co - h) @ ab) / denom, 0.0, 1.0)
            proj = h + tt[:, None] * ab
            d = np.linalg.norm(co - proj, axis=1)
            worst = dk[:, K - 1]
            better = d < worst
            dk[better, K - 1] = d[better]
            ik[better, K - 1] = bi
            order = np.argsort(dk, axis=1)
            dk = np.take_along_axis(dk, order, axis=1)
            ik = np.take_along_axis(ik, order, axis=1)
        eps = 1e-8
        w = 1.0 / (dk + eps) ** 2
        w = np.where(dk > 3.0 * (dk[:, :1] + eps), 0.0, w)
        w = w / w.sum(axis=1, keepdims=True)
        vg_by_name = {vg.name: vg for vg in mesh.vertex_groups}
        vgs = []
        for b in bones:
            vg = vg_by_name.get(b.name)
            if vg is None:
                vg = mesh.vertex_groups.new(name=b.name)
            vgs.append(vg)
        buckets = {}
        wq = np.round(w * 50) / 50.0
        for vi in range(n):
            for k in range(K):
                if wq[vi, k] > 0.015:
                    buckets.setdefault((int(ik[vi, k]), float(wq[vi, k])), []).append(int(sel[vi]))
        for (bi, wt), vids in buckets.items():
            vgs[bi].add(vids, wt, "ADD")
        print("RIGIFY_INFO: proximite-os: %d verts assignes sur %d os" % (n, len(bones)))

    empty_idx = [i for i, v in enumerate(mesh.data.vertices)
                 if sum(g.weight for g in v.groups) < 0.05]
    if empty_idx:
        print("RIGIFY_INFO: %d verts sans poids -> remplissage proximite" % len(empty_idx))
        _proximity_assign(empty_idx)
    if not any(m2.type == "ARMATURE" for m2 in mesh.modifiers):
        am = mesh.modifiers.new("aurora_arm", "ARMATURE")
        am.object = rig
    if not _skin_ok(mesh):
        print("RIGIFY_ERROR: skinning toujours vide apres proxy")
        sys.exit(8)

pose_mode = argv[4] if len(argv) > 4 else ""
if pose_mode == "sit":
    try:
        feet = [rig.pose.bones.get(n) for n in ("foot_ik.L", "foot_ik.R")]
        feet = [b for b in feet if b is not None]
        th_ref = (rig.pose.bones.get("thigh_fk.L") or rig.pose.bones.get("DEF-thigh.L")
                  or rig.pose.bones.get("thigh_fk.R"))
        if feet and th_ref is not None:
            lt = (th_ref.tail - th_ref.head).length
            delta = mathutils.Vector((0.0, -lt * 1.0, lt * 0.92))
            for pb in feet:
                M = pb.matrix.copy()
                M.translation = M.translation + delta
                pb.matrix = M
                bpy.context.view_layer.update()
            dth = rig.pose.bones.get("DEF-thigh.L") or rig.pose.bones.get("DEF-thigh.R")
            if dth is not None:
                dirv = (dth.tail - dth.head).normalized()
                print("RIGIFY_INFO: pose assise appliquee (cuisse dz=%.2f)" % dirv.z)
            for mo in [o for o in bpy.context.scene.objects if o.type == "MESH" and o.name in orig_mesh_names]:
                arm_mods = [m2 for m2 in mo.modifiers if m2.type == "ARMATURE"]
                for m2 in arm_mods:
                    with bpy.context.temp_override(object=mo, active_object=mo, selected_editable_objects=[mo]):
                        bpy.ops.object.modifier_apply(modifier=m2.name)
            bpy.ops.object.select_all(action="DESELECT")
            rig.select_set(True)
            bpy.context.view_layer.objects.active = rig
            bpy.ops.object.mode_set(mode="POSE")
            bpy.ops.pose.armature_apply(selected=False)
            bpy.ops.object.mode_set(mode="OBJECT")
            for mo in [o for o in bpy.context.scene.objects if o.type == "MESH" and o.name in orig_mesh_names]:
                if not any(m2.type == "ARMATURE" for m2 in mo.modifiers):
                    am2 = mo.modifiers.new("aurora_arm", "ARMATURE")
                    am2.object = rig
            print("RIGIFY_INFO: pose assise figee en rest (mesh bake + armature_apply)")
        else:
            print("RIGIFY_INFO: pose assise impossible (pas de foot_ik)")
    except Exception as _pe:
        print("RIGIFY_INFO: pose assise echec: %s" % _pe)

# v77zn: optional motion baking — bake an aurora.motion.v1 descriptor into
# an NLA action on the freshly generated rig before exporting.
motion_path = argv[2] if len(argv) > 2 else ""
motion_report = None
if motion_path and os.path.isfile(motion_path):
    try:
        import json as _json
        here = os.environ.get("AURORA_PYTHON_SERVICES")
        if here and here not in sys.path:
            sys.path.insert(0, here)
        import motion_baker as _mb  # noqa: E402
        with open(motion_path, "r", encoding="utf-8") as _fp:
            _motion = _json.load(_fp)
        _compiled = _mb.compile_motion_payload(_motion)
        # v77zq: forward primary mesh as fallback so mechanism primitives
        # (rotate/translate/extend on __object_root__) can mesh-direct
        # keyframe instead of being skipped.
        _mesh_fallback = next(
            (o for o in bpy.context.scene.objects if o.type == "MESH"), None,
        )
        # FORCE RIGIFY TO FK MODE!
        print("--- RIG PROPERTIES ---")
        for pb in rig.pose.bones:
            keys = list(pb.keys())
            if len(keys) > 0:
                print("BONE:", pb.name, "KEYS:", keys)
            for k in keys:
                if k == 'IK_FK' or k == 'ik_fk' or 'FK' in k.upper():
                    pb[k] = 1.0  # 1.0 is usually FK in Rigify
                    try:
                        pb.keyframe_insert(data_path=f'["{k}"]', frame=1)
                    except:
                        pass
        print("----------------------")
        
        motion_report = _mb.apply_compiled_motion(rig, _compiled, fallback_object=_mesh_fallback)
        print("MOTION_BAKED:", _compiled.get("id"),
              "applied=%d skipped=%d warnings=%d mech=%d" % (
                  motion_report.get("applied", 0),
                  motion_report.get("skipped", 0),
                  len(motion_report.get("warnings", [])),
                  len(motion_report.get("mechanism_actions", [])),
              ))
    except Exception as exc:
        print("MOTION_BAKE_WARN: %s" % exc)

# v77zal: Blender 5.1 — apply_compiled_motion leaves us in POSE mode if a
# motion was baked. Force OBJECT mode before select_all for export.
try:
    if bpy.context.mode != "OBJECT":
        bpy.ops.object.mode_set(mode="OBJECT")
except Exception:
    pass

# Export rigged GLB
bpy.ops.object.select_all(action="DESELECT")
rig.select_set(True)
for o in bpy.context.scene.objects:
    if o.type == "MESH" and o.name in orig_mesh_names:
        o.select_set(True)
try:
    # v80z: Blender 5.1 glTF I/O default animation mode dropped cross-object
    # actions when motion_baker assigned actions to multiple objects (rig +
    # mechanism mesh roots). Explicit ACTIVE_ACTIONS + NLA fallback so every
    # animated object's action survives export. Confirmed v5.1.19 generator.
    export_kwargs = dict(
        filepath=output_glb,
        export_format="GLB",
        export_skins=True,
        export_animations=True,
        use_selection=True,
    )
    try:
        # Blender 5.1+ accepts these knobs; older versions ignore unknown kw.
        export_kwargs["export_animation_mode"] = "ACTIVE_ACTIONS"
    except Exception:
        pass
    # Draco keeps files small, but the local acceptance/visual-audit path uses
    # trimesh and many UI viewers do not attach a DRACO loader by default. When
    # compressed, those readers see a zero-size mesh. Keep rigged exports plain
    # unless explicitly requested.
    if os.environ.get("AURORA_RIGIFY_DRACO", "").strip() == "1":
        export_kwargs["export_draco_mesh_compression_enable"] = True
        export_kwargs["export_draco_mesh_compression_level"] = 6
        export_kwargs["export_draco_position_quantization"] = 14
        export_kwargs["export_draco_normal_quantization"] = 10
        export_kwargs["export_draco_texcoord_quantization"] = 12
        export_kwargs["export_draco_color_quantization"] = 8
        export_kwargs["export_draco_generic_quantization"] = 12
    export_kwargs["export_optimize_animation_size"] = True
    try:
        bpy.ops.export_scene.gltf(**export_kwargs)
    except TypeError as draco_exc:
        # libdraco missing or older Blender: retry without Draco kwargs.
        for k in list(export_kwargs):
            if k.startswith("export_draco_") or k == "export_optimize_animation_size":
                del export_kwargs[k]
        bpy.ops.export_scene.gltf(**export_kwargs)
        print("RIGIFY_WARN: draco unavailable, exported uncompressed: %s" % draco_exc)
except Exception as e:
    print("RIGIFY_ERROR: export failed: %s" % e)
    sys.exit(8)

print("RIGIFY_OK: rigged GLB saved to %s" % output_glb)
'''


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input",  required=True, help="input GLB path")
    ap.add_argument("--output", required=True, help="output rigged GLB path")
    ap.add_argument("--motion", default="", help="optional aurora.motion.v1 JSON to bake as NLA action")
    ap.add_argument("--metarig", default="human", help="metarig family: human or quadruped")
    ap.add_argument("--pose", default="", help="static pose to apply via IK: sit")
    args = ap.parse_args()

    blender = find_blender()
    if not blender:
        print(json.dumps({
            "ok": False,
            "error": "Blender n'est pas installé. Télécharge-le sur blender.org (Rigify est inclus par défaut). Chemins détectés testés : " + ", ".join(BLENDER_CANDIDATES[:3]),
        }, ensure_ascii=False))
        return 10

    input_abs  = os.path.abspath(args.input)
    output_abs = os.path.abspath(args.output)
    if not os.path.isfile(input_abs):
        print(json.dumps({"ok": False, "error": f"input GLB missing: {input_abs}"}))
        return 11
    os.makedirs(os.path.dirname(output_abs), exist_ok=True)

    # Write script to temp .py
    with tempfile.NamedTemporaryFile(suffix=".py", delete=False, mode="w", encoding="utf-8") as fp:
        fp.write(BLENDER_SCRIPT)
        script_path = fp.name

    motion_abs = ""
    if args.motion:
        motion_abs = os.path.abspath(args.motion)
        if not os.path.isfile(motion_abs):
            print(json.dumps({"ok": False, "error": f"motion JSON missing: {motion_abs}"}))
            return 14

    # Forward the python-services directory to the embedded Blender script so
    # it can `import motion_baker` (Blender's bundled python has no notion of
    # our project layout).
    env = os.environ.copy()
    env["AURORA_PYTHON_SERVICES"] = os.path.dirname(os.path.abspath(__file__))

    cmd = [blender, "--background", "--python", script_path, "--", input_abs, output_abs, motion_abs, args.metarig, args.pose]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=600, env=env)
    except subprocess.TimeoutExpired:
        print(json.dumps({"ok": False, "error": "Blender timed out after 10 min"}))
        return 12
    finally:
        try: os.unlink(script_path)
        except Exception: pass

    out = (proc.stdout or "") + "\n" + (proc.stderr or "")
    print("--- BLENDER OUTPUT ---", file=sys.stderr)
    print(out, file=sys.stderr)
    print("----------------------", file=sys.stderr)
    if "RIGIFY_OK" in out and os.path.isfile(output_abs):
        url = "/" + os.path.relpath(output_abs, os.path.join(str(WORKSPACE), "public")).replace(os.sep, "/") \
            if output_abs.startswith(os.path.join(str(WORKSPACE), "public") + os.sep) else None
        print(json.dumps({
            "ok": True,
            "blender": blender,
            "path": output_abs,
            "url": url,
            "size_bytes": os.path.getsize(output_abs),
        }, ensure_ascii=False))
        return 0
    err_line = next((l for l in out.splitlines() if "RIGIFY_ERROR" in l), None)
    reason = err_line or (out.splitlines()[-5:] if out.splitlines() else ["unknown"])
    print(json.dumps({
        "ok": False,
        "error": f"Blender finished with exit={proc.returncode}: {reason}"[:600],
    }, ensure_ascii=False))
    return proc.returncode or 13


if __name__ == "__main__":
    sys.exit(main())
