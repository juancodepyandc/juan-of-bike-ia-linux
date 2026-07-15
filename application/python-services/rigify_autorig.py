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
# extra slot for a MoMask-produced BVH to retarget onto the freshly generated
# rig via retarget_bvh (MakeWalk). When set, we SKIP the procedural
# motion_baker path entirely and use the BVH as the sole source of motion.
mocap_bvh = argv[5] if len(argv) > 5 else ""
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

# v113: PRE-EXISTING RIG CLEANUP. When the pipeline re-runs on an already-
# rigged GLB (humain_final_materials.glb has a full Rigify aurora_rig + 706
# vertex groups baked in), a naive re-rig produces a DOUBLE-RIG state:
# the mesh keeps the OLD ARMATURE modifier + OLD vertex groups AND gets a
# NEW ARMATURE modifier + NEW vertex groups from parent_set. Weights get
# split across two rigs and the mesh explodes during animation (torso
# shatters, feet float, arms unresponsive — the v18 catastrophe).
# Fix: strip existing armature(s), armature modifiers, and vertex groups
# from all imported meshes BEFORE the metarig generation begins. The static
# base geometry is preserved (positions untouched).
_pre_arms = [o for o in bpy.context.scene.objects if o.type == "ARMATURE"]
_purge_stats = []
for m in meshes:
    _n_groups = len(m.vertex_groups)
    _n_arm_mods = sum(1 for mod in m.modifiers if mod.type == "ARMATURE")
    if _n_groups or _n_arm_mods:
        # Detach parent first so removing the armature doesn't wreck the
        # mesh's world transform.
        if m.parent is not None and m.parent.type == "ARMATURE":
            _mw = m.matrix_world.copy()
            m.parent = None
            m.matrix_world = _mw
        for mod in list(m.modifiers):
            if mod.type == "ARMATURE":
                m.modifiers.remove(mod)
        for vg in list(m.vertex_groups):
            m.vertex_groups.remove(vg)
        _purge_stats.append((m.name, _n_groups, _n_arm_mods))
for _arm in _pre_arms:
    try:
        bpy.data.objects.remove(_arm, do_unlink=True)
    except Exception:
        pass
if _purge_stats or _pre_arms:
    print("RIGIFY_INFO: pre-existing rig purged (%d armatures, %s meshes cleaned: %s)"
          % (len(_pre_arms), len(_purge_stats), _purge_stats))

# v113: STRAY MESH PURGE. TRELLIS.2 exports sometimes carry an environment
# proxy (Icosphere used for material sampling, a 2m-wide light dome). If
# left in the scene, its bbox INFLATES the height passed to the metarig
# scale factor — a 1m humain gets a 2m rig, bones end up outside the body,
# bone-heat produces empty groups, the proxy fallback kicks in with a
# coarse voxel remesh, and the mesh explodes at animation time.
# Rule: keep only the LARGEST connected mesh (by vertex count). Stray
# icospheres, environment domes, decorative widgets are dropped.
if len(meshes) > 1:
    meshes_sorted = sorted(meshes, key=lambda o: len(o.data.vertices), reverse=True)
    _keep = meshes_sorted[0]
    _drop = meshes_sorted[1:]
    # only drop meshes that are clearly minority (< 5% of the keeper's
    # vertex count). If the mesh has a genuine secondary body (e.g. a
    # weapon a character carries), we would keep it. TRELLIS typical:
    # keeper=952k, icosphere=42 → 0.004% → drop.
    _kv = max(1, len(_keep.data.vertices))
    for o in _drop:
        if len(o.data.vertices) < 0.05 * _kv:
            print("RIGIFY_INFO: stray mesh purged: %s (%d verts vs keeper %d)"
                  % (o.name, len(o.data.vertices), _kv))
            try:
                bpy.data.objects.remove(o, do_unlink=True)
            except Exception:
                pass
    meshes = [o for o in bpy.context.scene.objects if o.type == "MESH"]

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

# v112: WELD FRAGMENTED MESH before Rigify parenting. TRELLIS.2 exports
# with dedoubled vertices at every UV seam, giving a mesh made of thousands
# of disconnected islands. On any rotating bone, adjacent islands fly
# apart ("shards"). Weld with a tiny distance restores connectivity while
# preserving fine detail. Threshold scales with mesh dimension so it works
# on any character size. See memory/pipeline-deformation-3d.md.
if bpy.ops.object.mode_set.poll() is not False:
    for _mo in [o for o in bpy.context.scene.objects
                if o.type == "MESH" and o.name in orig_mesh_names]:
        bpy.ops.object.select_all(action="DESELECT")
        _mo.select_set(True)
        bpy.context.view_layer.objects.active = _mo
        try:
            _n_before = len(_mo.data.vertices)
            # 0.0008 (et non 0.00025): a 0.25mm la soudure ne reconnectait PAS la
            # soupe TRELLIS (~78k ilots persistaient -> le mesh se dechirait a
            # l'animation). A 0.0008 elle fusionne les doublons -> 12 ilots, TEXTURE
            # INTACTE (les doublons partagent l'UV), mouvement propre. Verifie.
            _weld_dist = max(max(_mo.dimensions) * 0.0008, 0.0006)
            import bmesh as _bm
            _bmm = _bm.new()
            _bmm.from_mesh(_mo.data)
            _bm.ops.remove_doubles(_bmm, verts=_bmm.verts, dist=_weld_dist)
            _bmm.to_mesh(_mo.data)
            _bmm.free()
            _mo.data.update()
            _n_after = len(_mo.data.vertices)
            print("RIGIFY_INFO: mesh weld %s: %d -> %d verts (dist=%.5f)"
                  % (_mo.name, _n_before, _n_after, _weld_dist))
        except Exception as _we:
            print("RIGIFY_INFO: weld skipped for %s: %s" % (_mo.name, _we))
    try:
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
    # v113: proxy resolution UP. Prior tuning (40k decimate + voxel dim/60 +
    # decimate 60k) collapsed a 1m humanoid to ~3400 polys, an arm cross-
    # section had 2-3 voxels, so bone-heat merged forearm and hip weights.
    # Result: mesh forearm/hand verts got hip weights and moved with the
    # pelvis during walk (the v19 "cape at belt" effect). Denser proxy:
    #   * initial decimate up to 200k (preserves geometry for remesh)
    #   * voxel_size = dim / 220 → ~5mm on a 1m body → ~40-80k shell polys,
    #     arm cross-section has ~10 voxels wide, forearm+hand resolvable
    #   * second decimate ceiling raised to 120k so the resolution survives.
    if len(dup.data.polygons) > 200000:
        dec = dup.modifiers.new("dec", "DECIMATE")
        dec.ratio = 200000.0 / len(dup.data.polygons)
        with bpy.context.temp_override(object=dup, active_object=dup, selected_editable_objects=[dup]):
            bpy.ops.object.modifier_apply(modifier=dec.name)
    rm = dup.modifiers.new("rm", "REMESH")
    rm.mode = "VOXEL"
    rm.voxel_size = max(max(dup.dimensions) / 220.0, 0.003)
    with bpy.context.temp_override(object=dup, active_object=dup, selected_editable_objects=[dup]):
        bpy.ops.object.modifier_apply(modifier=rm.name)
    if len(dup.data.polygons) > 120000:
        dec2 = dup.modifiers.new("dec2", "DECIMATE")
        dec2.ratio = 120000.0 / len(dup.data.polygons)
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

# v113: ANATOMICAL WEIGHT CAP. After Rigify auto-weights + proxy transfer,
# the arm DEF- bones (upper_arm, forearm, hand) often bleed weight into
# distant shirt/torso verts — the proxy remesh at ~49k polys represents
# each arm with only ~200 verts, so bone-heat merges arm/shirt boundaries.
# Result at animation: shirt mesh drags with the arm swing (the "cape/
# stretched arms" pattern seen in v22/v23/v24 renders). Real fix = compute
# per-vertex distance to each arm bone's line segment in rest pose; if
# distance exceeds ~2x the arm cross-section, ZERO the arm-bone weight.
# Anatomical fact: shirt verts on the chest are >12cm from any arm bone
# center, real skin/muscle within the arm is <5cm from the bone. Threshold
# scales with mesh body height. Purely geometric, no fudge factors.
if metarig_kind == "human":
    try:
        import numpy as _npc
        import mathutils as _mu

        _bh = mx.z - mn.z  # body height
        # radius of influence for arm bones (vertices within this from the
        # bone segment KEEP their weight; farther verts get capped)
        _arm_radius = max(_bh * 0.055, 0.045)  # 5.5% body height, min 45mm
        _leg_radius = max(_bh * 0.08, 0.060)   # legs are bigger (thighs)

        _cap_bones = {
            # arm bones — should NEVER weight shirt/torso/legs
            "DEF-upper_arm.L":    ("arm", _arm_radius * 1.2),  # shoulder region wider
            "DEF-upper_arm.L.001": ("arm", _arm_radius * 1.1),
            "DEF-upper_arm.R":    ("arm", _arm_radius * 1.2),
            "DEF-upper_arm.R.001": ("arm", _arm_radius * 1.1),
            "DEF-forearm.L":      ("arm", _arm_radius),
            "DEF-forearm.L.001":  ("arm", _arm_radius),
            "DEF-forearm.R":      ("arm", _arm_radius),
            "DEF-forearm.R.001":  ("arm", _arm_radius),
            "DEF-hand.L":         ("arm", _arm_radius * 0.9),
            "DEF-hand.R":         ("arm", _arm_radius * 0.9),
            # leg bones — should NEVER weight arms/torso
            "DEF-thigh.L":        ("leg", _leg_radius),
            "DEF-thigh.L.001":    ("leg", _leg_radius),
            "DEF-thigh.R":        ("leg", _leg_radius),
            "DEF-thigh.R.001":    ("leg", _leg_radius),
            "DEF-shin.L":         ("leg", _leg_radius * 0.85),
            "DEF-shin.L.001":     ("leg", _leg_radius * 0.85),
            "DEF-shin.R":         ("leg", _leg_radius * 0.85),
            "DEF-shin.R.001":     ("leg", _leg_radius * 0.85),
            "DEF-foot.L":         ("leg", _leg_radius * 0.75),
            "DEF-foot.R":         ("leg", _leg_radius * 0.75),
        }

        _cap_stats = {"capped_bones": 0, "capped_verts_total": 0}
        for _mo in [o for o in bpy.context.scene.objects
                    if o.type == "MESH" and o.name in orig_mesh_names]:
            _nvt = len(_mo.data.vertices)
            if _nvt < 100:
                continue
            _co = _npc.empty(_nvt * 3, dtype=_npc.float32)
            _mo.data.vertices.foreach_get("co", _co)
            _co = _co.reshape(_nvt, 3)
            _mw = _npc.array(_mo.matrix_world, dtype=_npc.float32)
            _wco = _co @ _mw[:3, :3].T + _mw[:3, 3]  # world vertex coords

            _arm_mw = _npc.array(rig.matrix_world, dtype=_npc.float32)
            _vg_by_name = {vg.name: vg for vg in _mo.vertex_groups}
            for _bname, (_kind, _radius) in _cap_bones.items():
                _b = rig.data.bones.get(_bname)
                _vg = _vg_by_name.get(_bname)
                if _b is None or _vg is None:
                    continue
                # bone endpoints in world coords
                _h = _npc.array(_arm_mw @ _npc.array(_b.head_local.to_4d()))[:3]
                _t = _npc.array(_arm_mw @ _npc.array(_b.tail_local.to_4d()))[:3]
                _ab = _t - _h
                _l2 = float(_ab @ _ab) or 1e-9
                _tt = _npc.clip(((_wco - _h) @ _ab) / _l2, 0.0, 1.0)
                _proj = _h + _tt[:, None] * _ab
                _dist = _npc.linalg.norm(_wco - _proj, axis=1)
                _cap_mask = _dist > _radius
                # capped verts: remove from this vertex group
                _cap_idx = _npc.where(_cap_mask)[0]
                if len(_cap_idx) == 0:
                    continue
                # sample: only cap verts that actually had weight in this group
                _cap_list = [int(i) for i in _cap_idx]
                try:
                    _vg.remove(_cap_list)
                    _cap_stats["capped_bones"] += 1
                    _cap_stats["capped_verts_total"] += len(_cap_list)
                except Exception:
                    pass

            # After capping, renormalize each vertex's remaining weights so
            # they sum to 1 (Blender then respects the new distribution).
            import bmesh as _bmr
            _bm3 = _bmr.new()
            _bm3.from_mesh(_mo.data)
            _dl = _bm3.verts.layers.deform.verify()
            _renorm = 0
            for _v in _bm3.verts:
                _dv = _v[_dl]
                _s = sum(_dv.values())
                if _s <= 1e-6 or abs(_s - 1.0) < 1e-4:
                    continue
                _inv = 1.0 / _s
                for _gi in list(_dv.keys()):
                    _dv[_gi] = _dv[_gi] * _inv
                _renorm += 1
            _bm3.to_mesh(_mo.data)
            _bm3.free()
            _mo.data.update()
            print("RIGIFY_INFO: anatomical cap on %s: %d bone-vert prunes, %d verts renormalized"
                  % (_mo.name, _cap_stats["capped_verts_total"], _renorm))
    except Exception as _cap_e:
        print("RIGIFY_INFO: anatomical cap failed: %s" % _cap_e)
        import traceback as _tbc
        _tbc.print_exc()

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
# When --mocap-bvh is set, we take the MoMask/retarget_bvh path and SKIP the
# procedural motion_baker (see application/python-services/mocap_pipeline.py).
motion_path = argv[2] if len(argv) > 2 else ""
motion_report = None

# ---- MoMask + retarget_bvh (MakeWalk) mocap chain ------------------------
if mocap_bvh and os.path.isfile(mocap_bvh) and metarig_kind == "human":
    print("MOCAP_INFO: retargeting BVH", mocap_bvh)
    # Pre-mocap mesh hardening: mocap-scale rotations expose the classic
    # TRELLIS.2 shirt-shard problem (thin double-shell garments tear at the
    # shoulder). Two mitigations before the bake:
    #   (a) SECOND WELD PASS at ~1mm on the upper-body verts only. Increases
    #       island connectivity on the T-shirt / neckline without touching
    #       fine facial detail (memory: >2mm destroys detail).
    #   (b) CORRECTIVE_SMOOTH modifier (delta-mush) on each mesh. Relaxes
    #       any deltas the Armature modifier introduces, mapping to the
    #       skinned rest surface. Placed AFTER the Armature modifier so it
    #       smooths the deformed state. Confirmed on the humain: without
    #       it frame ~75 of the MoMask walk shatters the shirt into shards.
    try:
        import bmesh as _bm2
        for _mo in [o for o in bpy.context.scene.objects
                    if o.type == "MESH" and o.name in orig_mesh_names]:
            n_before = len(_mo.data.vertices)
            _dim = max(_mo.dimensions) if _mo.dimensions else 1.0
            _upper_z = mn.z + 0.55 * (mx.z - mn.z)  # roughly waist-up
            _weld = max(_dim * 0.00075, 0.0007)
            _bmm = _bm2.new()
            _bmm.from_mesh(_mo.data)
            # collect verts above the upper_z threshold in world space
            _mw = _mo.matrix_world
            sel_verts = []
            for v in _bmm.verts:
                wz = (_mw @ v.co).z
                if wz >= _upper_z:
                    sel_verts.append(v)
            if sel_verts:
                _bm2.ops.remove_doubles(_bmm, verts=sel_verts, dist=_weld)
                _bmm.to_mesh(_mo.data)
                _mo.data.update()
            _bmm.free()
            n_after = len(_mo.data.vertices)
            print("RIGIFY_INFO: upper-body weld %s: %d -> %d verts (dist=%.4f)"
                  % (_mo.name, n_before, n_after, _weld))

            # (c) LAPLACIAN WEIGHT SMOOTHING on the upper body — this is what
            # actually EXPORTS via glTF (unlike Corrective Smooth, which is a
            # Blender-only modifier the exporter strips). We build a numpy
            # adjacency from mesh edges, then for each upper-body vertex
            # replace its weight in each group with the mean of its 1-ring
            # neighbours' weights. 22 iterations, factor 0.55.
            # Docs: memory/pipeline-deformation-3d.md ("smooth_upper_weights").
            import numpy as _np2

            if len(_mo.vertex_groups) >= 3:
                nvt = len(_mo.data.vertices)
                # gather world-Z for the upper mask
                co = _np2.empty(nvt * 3, dtype=_np2.float32)
                _mo.data.vertices.foreach_get("co", co)
                co = co.reshape(nvt, 3)
                mw = _np2.array(_mo.matrix_world)
                wco = co @ mw[:3, :3].T + mw[:3, 3]
                upper_mask = wco[:, 2] >= _upper_z
                # protect fingers/hands so the finger curl stays crisp
                hand_names = {vg.name for vg in _mo.vertex_groups
                              if any(k in vg.name.lower() for k in
                              ("hand", "f_index", "f_middle", "f_ring",
                               "f_pinky", "thumb", "palm"))}
                # per-vertex weight matrix (sparse in principle; here dense
                # over the vertex groups we actually smooth)
                grp_ids = {vg.index: vg.name for vg in _mo.vertex_groups}
                nvg = len(grp_ids)
                W = _np2.zeros((nvt, nvg), dtype=_np2.float32)
                # sort weights into W
                sorted_gidx = sorted(grp_ids.keys())
                gidx_to_col = {gi: i for i, gi in enumerate(sorted_gidx)}
                for vi, v in enumerate(_mo.data.vertices):
                    for g in v.groups:
                        if g.group in gidx_to_col:
                            W[vi, gidx_to_col[g.group]] = g.weight
                # build 1-ring neighbours from edges
                nedges = len(_mo.data.edges)
                _e = _np2.empty(nedges * 2, dtype=_np2.int32)
                _mo.data.edges.foreach_get("vertices", _e)
                _e = _e.reshape(nedges, 2)
                # accumulate neighbour weights
                iters = 22
                factor = 0.55
                # For efficiency, only smooth verts in the upper mask
                for _it in range(iters):
                    # for each edge, accumulate contribution to each endpoint
                    Wneigh = _np2.zeros_like(W)
                    cnt = _np2.zeros(nvt, dtype=_np2.float32)
                    _np2.add.at(Wneigh, _e[:, 0], W[_e[:, 1]])
                    _np2.add.at(cnt, _e[:, 0], 1.0)
                    _np2.add.at(Wneigh, _e[:, 1], W[_e[:, 0]])
                    _np2.add.at(cnt, _e[:, 1], 1.0)
                    Wneigh /= (cnt[:, None] + 1e-6)
                    # blend
                    new_W = W * (1.0 - factor) + Wneigh * factor
                    # protect hands: keep original weights on hand verts
                    for gname in hand_names:
                        vg = _mo.vertex_groups.get(gname)
                        if vg and vg.index in gidx_to_col:
                            col = gidx_to_col[vg.index]
                            new_W[:, col] = W[:, col]
                    # only apply in upper mask
                    W[upper_mask] = new_W[upper_mask]
                # renormalize per-vertex so weights sum to 1
                s = W.sum(axis=1, keepdims=True) + 1e-6
                W = W / s
                # write back into vertex_groups
                nz_thresh = 0.008
                # rebuild each group's entries in bulk
                for gi in sorted_gidx:
                    col = gidx_to_col[gi]
                    vg = None
                    for _vg in _mo.vertex_groups:
                        if _vg.index == gi:
                            vg = _vg
                            break
                    if vg is None:
                        continue
                    # clear existing entries in the upper mask; keep hands
                    if grp_ids[gi] in hand_names:
                        continue
                    upper_idx = _np2.where(upper_mask)[0]
                    # remove and re-add in bulk
                    for vi in upper_idx:
                        try:
                            vg.remove([int(vi)])
                        except Exception:
                            pass
                    # add non-negligible weights
                    keep = upper_idx[W[upper_idx, col] > nz_thresh]
                    if len(keep):
                        # can only add float weight, one at a time using .add
                        # bucket by rounded weight for a speedup
                        buckets = {}
                        wq = _np2.round(W[keep, col] * 100.0) / 100.0
                        for i_local, vi in enumerate(keep):
                            buckets.setdefault(float(wq[i_local]), []).append(int(vi))
                        for wt, vids in buckets.items():
                            if wt > 0.0:
                                vg.add(vids, float(wt), "REPLACE")
                print("RIGIFY_INFO: Laplacian weight smooth on %s (upper-body verts=%d, iters=%d)"
                      % (_mo.name, int(upper_mask.sum()), iters))

            # (d) CORRECTIVE_SMOOTH modifier — Blender-side polish only.
            # We keep it because when the pipeline is used in Blender (viewer
            # embed, render_anim_frames.py loads the animated GLB and the
            # modifier is dropped anyway) it hurts nothing. On export the
            # exporter strips it.
            has_cs = any(m.type == "CORRECTIVE_SMOOTH" for m in _mo.modifiers)
            if not has_cs:
                cs = _mo.modifiers.new("aurora_cs", "CORRECTIVE_SMOOTH")
                cs.factor = 0.55
                cs.iterations = 8
                try:
                    cs.smooth_type = "LENGTH_WEIGHTED"
                except Exception:
                    pass
                try:
                    cs.use_only_smooth = False
                except Exception:
                    pass
                print("RIGIFY_INFO: corrective smooth added on %s (factor=0.55, iter=8)" % _mo.name)
    except Exception as _prep_err:
        print("MOCAP_INFO: pre-bake hardening skipped: %s" % _prep_err)
        import traceback as _tbp
        _tbp.print_exc()
    here = os.environ.get("AURORA_PYTHON_SERVICES")
    if here and here not in sys.path:
        sys.path.insert(0, here)
    try:
        os.environ["AURORA_INSIDE_BLENDER"] = "1"
        import mocap_bake_bpy as _mb  # noqa: E402
        _mesh_fallback = next(
            (o for o in bpy.context.scene.objects if o.type == "MESH"), None,
        )
        _mocap_report = _mb.run_mocap_bake(
            rig,
            mocap_bvh,
            orig_mesh_names,
            ground_z=float(mn.z) if 'mn' in dir() else 0.0,
            mesh_fallback=_mesh_fallback,
            arm_swing_boost=float(os.environ.get("AURORA_MOCAP_ARM_BOOST", "1.35")),
            per_frame_foot_lock=os.environ.get("AURORA_MOCAP_FOOT_LOCK", "1") != "0",
        )
        # Sync scene frame range to the retargeted action so the glTF exporter
        # writes every frame of the walk cycle.
        _fr = _mocap_report.get("frame_range") or [1, 1]
        bpy.context.scene.frame_start = int(_fr[0])
        bpy.context.scene.frame_end = int(_fr[1])
        print("MOCAP_BAKED: frames=%s steps=%s" % (_fr, _mocap_report.get("steps")))
    except Exception as _me:
        print("MOCAP_ERROR: %s" % _me)
        import traceback as _tb
        _tb.print_exc()
        # Fall through to procedural motion if the BVH path failed.
        pass
elif motion_path and os.path.isfile(motion_path):
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
        # v113: IK vs FK mode PER LIMB, driven by which bones the compiled
        # motion actually keyframes. Previous version blanket-forced FK=1.0
        # on every bone that had an IK_FK property. That KILLS arm swing:
        # motion_baker writes location keyframes on hand_ik.L/R (IK targets)
        # and the arm mesh is expected to follow via IK — but with FK=1.0,
        # the IK constraints are muted, hand_ik.L sweeps 60cm and the arm
        # doesn't move at all (verified by tracking DEF-hand.L world position
        # in v21_proc_boost: hand_ik yP2P=0.616m, DEF-hand yP2P=0.000m). Fix:
        # inspect the compiled instructions, and for each Rigify limb pair
        # ("upper_arm"/"hand" for arms, "thigh"/"foot" for legs) decide the
        # IK/FK setting from which bone family the motion drives.
        _limb_targets = {
            "IK-arm.L":  ("hand_ik.L", ("upper_arm_parent.L",), "IK_FK"),
            "IK-arm.R":  ("hand_ik.R", ("upper_arm_parent.R",), "IK_FK"),
            "IK-leg.L":  ("foot_ik.L", ("thigh_parent.L",), "IK_FK"),
            "IK-leg.R":  ("foot_ik.R", ("thigh_parent.R",), "IK_FK"),
        }
        # Which limbs did compile touch as IK targets?
        _instr_bones = set()
        for _ins in _compiled.get("instructions") or []:
            _instr_bones.add(str(_ins.get("bone") or ""))
        _uses_ik = {
            "IK-arm.L": "hand_ik.L" in _instr_bones,
            "IK-arm.R": "hand_ik.R" in _instr_bones,
            "IK-leg.L": "foot_ik.L" in _instr_bones,
            "IK-leg.R": "foot_ik.R" in _instr_bones,
        }
        for _lname, (_tbone, _prop_owners, _prop_name) in _limb_targets.items():
            _ik_wanted = 1 if _uses_ik.get(_lname) else 0
            # 0 = full IK, 1 = full FK in Rigify convention
            _fk_value = 0.0 if _ik_wanted else 1.0
            for _po_name in _prop_owners:
                _po = rig.pose.bones.get(_po_name)
                if _po is None:
                    continue
                for _k in list(_po.keys()):
                    if _k == _prop_name or "IK_FK" in _k.upper():
                        try:
                            _po[_k] = _fk_value
                            _po.keyframe_insert(data_path='["%s"]' % _k, frame=1)
                            print("RIGIFY_INFO: %s.%s = %.2f (%s mode)"
                                  % (_po_name, _k, _fk_value,
                                     "IK" if _ik_wanted else "FK"))
                        except Exception:
                            pass
        
        motion_report = _mb.apply_compiled_motion(rig, _compiled, fallback_object=_mesh_fallback)
        print("MOTION_BAKED:", _compiled.get("id"),
              "applied=%d skipped=%d warnings=%d mech=%d" % (
                  motion_report.get("applied", 0),
                  motion_report.get("skipped", 0),
                  len(motion_report.get("warnings", [])),
                  len(motion_report.get("mechanism_actions", [])),
              ))

        # v112: post-bake polish for humanoid rigs — addresses the four
        # plafond defects documented in memory/pipeline-deformation-3d.md
        # (starfish hands, head dive from missing neck constraint, feet
        # sinking through ground, feet floating). These are constant static
        # corrections baked as single frame-1 keyframes so gltf export
        # carries them across every frame of the walk cycle. Skipped when
        # metarig != human.
        _motion_id = str(_compiled.get("id") or "").lower()
        _is_locomotion = any(t in _motion_id for t in ("walk", "run", "crawl", "march"))
        if metarig_kind == "human" and (_motion_id or _is_locomotion):
            try:
                if bpy.context.mode != "OBJECT":
                    bpy.ops.object.mode_set(mode="OBJECT")
                bpy.ops.object.select_all(action="DESELECT")
                rig.select_set(True)
                bpy.context.view_layer.objects.active = rig
                bpy.ops.object.mode_set(mode="POSE")

                # 1) FINGER CURL — avoid the "starfish" hand. Rigify names
                # finger DEF-bones "DEF-f_index.01.L" / "DEF-f_middle.02.R"
                # etc. Segment index encoded via .01/.02/.03 (dot-separated,
                # NOT _01_fk_). We keyframe the DEF- bones because that's
                # what the mesh is skinned to (matches the DEF- retarget for
                # limbs).
                _finger_stems = ("def-f_index", "def-f_middle", "def-f_ring",
                                 "def-f_pinky", "def-thumb")
                _finger_curl_by_seg = {"01": 0.22, "02": 0.55, "03": 0.60}  # radians
                _thumb_curl = {"01": 0.08, "02": 0.30, "03": 0.35}
                _curled = 0
                for pb in rig.pose.bones:
                    n = pb.name.lower()
                    if not any(n.startswith(s) for s in _finger_stems):
                        continue
                    seg = None
                    for s in (".01.", ".02.", ".03."):
                        if s in n:
                            seg = s[1:3]
                            break
                    if seg is None:
                        continue
                    curl = (_thumb_curl if "thumb" in n else _finger_curl_by_seg).get(seg, 0.0)
                    if curl == 0.0:
                        continue
                    # Mute Rigify constraints on this DEF- bone so our
                    # keyframe isn't overridden by the driver chain.
                    for _c in pb.constraints:
                        _c.mute = True
                    pb.rotation_mode = "XYZ"
                    pb.rotation_euler.x = curl
                    try:
                        pb.keyframe_insert(data_path="rotation_euler", index=0, frame=1)
                        _curled += 1
                    except Exception:
                        pass
                print("RIGIFY_INFO: finger curl applied on %d bones (no starfish)" % _curled)

                # 2) NECK LIMIT ROTATION — text-to-motion / procedural gait
                # often produces a head dive (nod ~-50deg) because the neck
                # inherits torso pitch. Clamp neck rotation so the head stays
                # level regardless of what the motion primitives command.
                _neck = (rig.pose.bones.get("neck") or rig.pose.bones.get("neck_fk")
                         or rig.pose.bones.get("neck.001"))
                if _neck is not None:
                    _existing = [c for c in _neck.constraints if c.type == "LIMIT_ROTATION"]
                    if not _existing:
                        _lr = _neck.constraints.new(type="LIMIT_ROTATION")
                        _lr.owner_space = "LOCAL"
                        _lr.use_limit_x = True
                        _lr.min_x = -0.244  # -14 deg
                        _lr.max_x = 0.384   # +22 deg
                        _lr.use_limit_z = True
                        _lr.min_z = -0.349  # -20 deg
                        _lr.max_z = 0.349   # +20 deg
                        print("RIGIFY_INFO: neck LIMIT_ROTATION added (head stays level)")

                # 3) FOOT GROUND PLANE — during walk the passing foot must not
                # dip below the floor. Add a LIMIT_LOCATION on foot_ik.L/R min_z
                # so the IK target can't sink; the mesh floor is z=min of the
                # imported mesh in world (mn.z passed in from earlier).
                for _side in ("L", "R"):
                    _foot = (rig.pose.bones.get("foot_ik.%s" % _side)
                             or rig.pose.bones.get("foot.%s" % _side))
                    if _foot is None:
                        continue
                    if any(c.type == "LIMIT_LOCATION" for c in _foot.constraints):
                        continue
                    _ll = _foot.constraints.new(type="LIMIT_LOCATION")
                    _ll.owner_space = "LOCAL"
                    _ll.use_min_y = True
                    _ll.min_y = 0.0  # foot IK local Y is height above rest
                    print("RIGIFY_INFO: foot_ik.%s ground clamp added" % _side)

                # 4) ROOT VERTICAL BOUNCE — biological walk has a subtle
                # sinusoidal head bob (~2 cm) synchronized to the stride.
                # If the motion payload didn't already keyframe the torso,
                # add a soft bounce so the character isn't dragged along a
                # perfectly flat line.
                _torso = rig.pose.bones.get("torso") or rig.pose.bones.get("spine_fk")
                _has_torso_z = False
                if rig.animation_data and rig.animation_data.action:
                    _cur_action = rig.animation_data.action
                    try:
                        # Peek at fcurves via the layered API to see if torso.z
                        # is already animated.
                        import motion_baker as _mb2  # noqa: F401
                        _slot = None
                        if hasattr(_cur_action, "slots") and len(_cur_action.slots) > 0:
                            _slot = _cur_action.slots[0]
                        _fcv = _mb.__dict__.get("_get_action_fcurves", lambda a, s: [])(_cur_action, _slot)
                        for _fc in _fcv:
                            if _torso and _torso.name in _fc.data_path and "location" in _fc.data_path and _fc.array_index == 2:
                                _has_torso_z = True
                                break
                    except Exception:
                        pass
                if _torso is not None and not _has_torso_z and _is_locomotion:
                    import math as _m
                    _fps = int(_compiled.get("fps") or 24)
                    _fc_end = int(_compiled.get("frame_count") or 24)
                    _torso.rotation_mode = "XYZ"
                    for _f in range(1, _fc_end + 1):
                        _t = (_f - 1) / _fps
                        _torso.location.z = 0.015 * _m.sin(2 * _m.pi * 2.0 * _t)
                        _torso.keyframe_insert(data_path="location", index=2, frame=_f)
                    print("RIGIFY_INFO: torso vertical bounce baked (%d frames)" % _fc_end)

                bpy.ops.object.mode_set(mode="OBJECT")
            except Exception as _polish_e:
                print("RIGIFY_INFO: post-motion polish partial: %s" % _polish_e)
    except Exception as exc:
        print("MOTION_BAKE_WARN: %s" % exc)

# v77zal: Blender 5.1 — apply_compiled_motion leaves us in POSE mode if a
# motion was baked. Force OBJECT mode before select_all for export.
try:
    if bpy.context.mode != "OBJECT":
        bpy.ops.object.mode_set(mode="OBJECT")
except Exception:
    pass

# PURGE AVANT EXPORT. La purge d'import (v113) ne voit que les meshes presents a
# l'arrivee; or le rig en CREE (widgets). Une Icosphere de 2 m se retrouvait ainsi
# dans le GLB rigge, et le compositeur, mesurant l'englobant de l'acteur, lui
# attribuait 2 m au lieu de 1 -> echelle divisee par deux, et un homme exactement
# de la taille de sa chaise. On repurge donc juste avant l'export.
_ms = [o for o in bpy.context.scene.objects if o.type == "MESH"]
if len(_ms) > 1:
    _ms.sort(key=lambda o: len(o.data.vertices), reverse=True)
    _kv = max(1, len(_ms[0].data.vertices))
    for _o in _ms[1:]:
        if len(_o.data.vertices) < 0.05 * _kv:
            print("RIGIFY_INFO: parasite purge avant export: %s (%d verts vs %d)"
                  % (_o.name, len(_o.data.vertices), _kv))
            try:
                orig_mesh_names.discard(_o.name)
            except Exception:
                pass
            try:
                bpy.data.objects.remove(_o, do_unlink=True)
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


MIA_ROOT_DEFAULT = os.path.expanduser("~/.local/share/auroraia/external/Make-It-Animatable")
MIA_ENV_DEFAULT = os.path.expanduser("~/.local/opt/miniforge3/envs/mia/bin/python")


def _mia_available(mia_root: str, mia_python: str) -> bool:
    """MIA can serve a human only if we have both the checkout AND a python
    interpreter with the mia conda env (torch 2.11+cu128, pytorch3d, gradio,
    trimesh) — no runtime dep-install here."""
    return (
        os.path.isdir(mia_root)
        and os.path.isfile(os.path.join(mia_root, "app.py"))
        and os.path.isfile(os.path.join(mia_root, "data", "Mixamo", "bones.fbx"))
        and os.path.isfile(mia_python)
    )


def _run_mia(
    input_glb: str,
    output_dir: str,
    mia_root: str,
    mia_python: str,
    rest_pose_type: str = "A-pose",
    reset_to_rest: bool = False,
    no_fingers: bool = True,
    timeout_s: int = 900,
) -> tuple[str, str] | tuple[None, str]:
    """Drive `scratchpad/mia_rig.py` under the mia conda env. Returns
    (output_glb_path, log) on success or (None, reason) on failure. The
    output GLB has been converted from FBX with FBX2glTF native (embedded in
    MIA's `vis_blender`), preserving fine geometry and orientation."""
    runner = os.path.join(str(WORKSPACE.parent), "scratchpad", "mia_rig.py")
    if not os.path.isfile(runner):
        return None, f"MIA runner missing: {runner}"
    # Stage the input inside output_dir so MIA writes side-outputs there,
    # not next to the caller's input.
    os.makedirs(output_dir, exist_ok=True)
    staged_in = os.path.join(output_dir, "mia_input.glb")
    try:
        shutil.copyfile(input_glb, staged_in)
    except Exception as e:
        return None, f"MIA stage copy failed: {e}"
    env = os.environ.copy()
    env["MIA_ROOT"] = mia_root
    cmd = [
        mia_python,
        runner,
        staged_in,
        rest_pose_type,
        "1" if reset_to_rest else "0",
        "1" if no_fingers else "0",
    ]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout_s, env=env)
    except subprocess.TimeoutExpired:
        return None, f"MIA timed out after {timeout_s}s"
    log = (proc.stdout or "") + "\n" + (proc.stderr or "")
    if "MIA_OK" not in log:
        return None, f"MIA did not report MIA_OK (exit={proc.returncode}); tail={log.splitlines()[-6:]}"
    # MIA writes to <staged_in_stem>/<staged_in_stem>.glb
    stem = os.path.splitext(os.path.basename(staged_in))[0]
    produced = os.path.join(os.path.dirname(staged_in), stem, f"{stem}.glb")
    if not os.path.isfile(produced):
        return None, f"MIA output missing: {produced}"
    return produced, log


def _motion_is_locomotion(motion_json_path: str):
    """If the parsed motion is a locomotion (walk/run/march), return dict of
    procedural-walk params {frames, swing_deg, speed}; else None. MIA rigs a
    Mixamo FK skeleton that Aurora's Rigify/IK motion presets cannot drive, so a
    locomotion is baked procedurally on the Mixamo bones (see mia_walk_apply)."""
    try:
        if not motion_json_path or not os.path.isfile(motion_json_path):
            return None
        with open(motion_json_path, encoding="utf-8") as f:
            m = json.load(f)
    except Exception:
        return None
    label = str(m.get("label", "")).lower()
    if not any(k in label for k in ("walk", "run", "march", "locomot", "jog", "stroll", "sprint")):
        return None
    frames = int(m.get("frame_count") or 36)
    speed = 1.0
    swing = 40.0
    for p in (m.get("primitives") or []):
        mods = p.get("modifiers") or {}
        speed = float(mods.get("speedMul", speed) or speed)
        swing *= float(mods.get("amplitudeMul", 1.0) or 1.0)
    if "run" in label or "sprint" in label or "jog" in label:
        swing = max(swing, 55.0)
    return {"frames": max(8, frames), "swing_deg": max(15.0, min(70.0, swing)), "speed": speed}


def _apply_mia_walk(in_glb: str, out_glb: str, loco: dict):
    """Bake a procedural Mixamo walk onto a MIA-rigged GLB via Blender +
    mia_walk_apply.py. Returns (ok, log_tail)."""
    blender = find_blender()
    if not blender:
        return False, "Blender introuvable pour appliquer la marche MIA"
    script = os.path.join(os.path.dirname(os.path.abspath(__file__)), "mia_walk_apply.py")
    if not os.path.isfile(script):
        return False, f"mia_walk_apply.py manquant: {script}"
    os.makedirs(os.path.dirname(os.path.abspath(out_glb)), exist_ok=True)
    cmd = [blender, "-b", "-P", script, "--", in_glb, out_glb,
           str(loco["frames"]), str(loco["swing_deg"]), str(loco["speed"])]
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=600, check=False)
    except Exception as e:  # noqa: BLE001
        return False, f"exception: {e}"
    log = (p.stdout or "") + (p.stderr or "")
    return ("MIA_WALK_OK" in log and os.path.isfile(out_glb)), log[-500:]


def _motion_to_english(text: str) -> str:
    """Translate a natural (any-language) motion description to a concise English
    phrase for MoMask (HumanML3D). Uses the local Ollama LLM so it's the AI that
    understands the movement — no hardcoded verb table. Falls back to the raw text."""
    text = (text or "").strip()
    if not text:
        return "a person walks forward"
    try:
        import urllib.request
        model = os.environ.get("AURORA_MOTION_LLM", "qwen3:30b-a3b-instruct-2507-q4_K_M")
        body = json.dumps({
            "model": model,
            "prompt": ("You convert a motion description to a concise English phrase for a "
                       "text-to-motion model (HumanML3D style). Output ONLY the phrase, no "
                       "quotes, no explanation. Input: " + text),
            "stream": False, "options": {"temperature": 0.1},
            # Unload the LLM from the GPU immediately after translating: the very
            # next step (MoMask) needs the whole 15GB GPU, and a 14GB resident LLM
            # would OOM it. keep_alive:0 frees the VRAM before MoMask runs.
            "keep_alive": 0,
        }).encode()
        req = urllib.request.Request("http://127.0.0.1:11434/api/generate", data=body,
                                     headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=90) as r:
            out = json.loads(r.read().decode()).get("response", "").strip()
        out = out.splitlines()[0].strip().strip('"').strip() if out else ""
        return out or text
    except Exception:
        return text


def _apply_mia_motion(mia_glb: str, out_glb: str, motion_text: str):
    """GENUINE motion for a MIA/Mixamo rig (replaces the hand-authored walk):
    MoMask text-to-motion -> BVH -> retarget onto the Mixamo skeleton (+ spine
    clamp against waist shatter). Handles ANY described motion. Returns (ok, log)."""
    try:
        import momask_generate as mg
    except Exception as e:  # noqa: BLE001
        return False, f"momask_generate import failed: {e}"
    motion_en = _motion_to_english(motion_text)
    try:
        ext = "aurora_mia_" + str(abs(hash(out_glb)) % 100000)
        gen = mg.generate_motions(motion_en, ext=ext, repeat_times=1, gpu_id=0, timeout_s=480)
    except Exception as e:  # noqa: BLE001
        return False, f"MoMask exception: {e}"
    if not gen.get("ok") or not gen.get("candidates"):
        return False, f"MoMask no candidates ({str(gen.get('error',''))[:120]})"
    cand = gen["candidates"][0]
    bvh = cand.get("bvh_ik") or cand.get("bvh")
    if not bvh or not os.path.isfile(bvh):
        return False, "MoMask BVH missing"
    blender = find_blender()
    if not blender:
        return False, "Blender introuvable pour le retarget"
    script = os.path.join(os.path.dirname(os.path.abspath(__file__)), "mia_mocap_retarget.py")
    os.makedirs(os.path.dirname(os.path.abspath(out_glb)), exist_ok=True)
    cmd = [blender, "-b", "-P", script, "--", mia_glb, bvh, out_glb]
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=700, check=False)
    except Exception as e:  # noqa: BLE001
        return False, f"retarget subprocess exception: {e}"
    log = (p.stdout or "") + (p.stderr or "")
    ok = "MIA_MOCAP_OK" in log and os.path.isfile(out_glb)
    return ok, f"motion_en='{motion_en}' | " + log[-400:]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input",  required=True, help="input GLB path")
    ap.add_argument("--output", required=True, help="output rigged GLB path")
    ap.add_argument("--motion", default="", help="optional aurora.motion.v1 JSON to bake as NLA action")
    ap.add_argument("--motion-text", default="", dest="motion_text", help="natural-language motion description (any language) -> MoMask text-to-motion for MIA/Mixamo rigs")
    ap.add_argument("--metarig", default="human", help="metarig family: human or quadruped")
    ap.add_argument("--pose", default="", help="static pose to apply via IK: sit")
    ap.add_argument("--mocap-bvh", default="", help="optional BVH (MoMask/HumanML3D) to retarget onto the rig via retarget_bvh")
    ap.add_argument("--use-mia", action="store_true", help="Use Make-It-Animatable (MIA) for human rigging instead of Rigify — produces a Mixamo 52-bone skeleton with anatomical skinning weights that don't bleed the T-shirt onto the arm bones. Falls back to Rigify if MIA env is unavailable.")
    ap.add_argument("--mia-root", default=MIA_ROOT_DEFAULT, help="MIA checkout dir")
    ap.add_argument("--mia-python", default=MIA_ENV_DEFAULT, help="Python interpreter for the mia conda env")
    ap.add_argument("--mia-rest-pose", default="A-pose", choices=("T-pose", "A-pose", "No"), help="rest pose hint for MIA")
    args = ap.parse_args()

    # SOUDER L'ENTREE AVANT TOUTE VOIE DE RIG. TRELLIS sort la surface en ~78k ilots
    # disjoints; sous une deformation ils glissent -> jambe/vetement dechires. La
    # soudure interne du script Rigify ne couvrait PAS la voie MIA (celle qui applique
    # le mouvement MoMask), donc une vraie marche dechirait quand meme. On soude donc
    # ICI, en amont: MIA comme Rigify recoivent un maillage CONNEXE. Les doublons
    # partagent l'UV -> texture intacte (verifie: 78169->12 ilots, rendu identique).
    if os.environ.get("AURORA_RIG_WELD", "1") == "1" and os.path.isfile(args.input):
        try:
            import mesh_weld
            _welded = os.path.splitext(os.path.abspath(args.output))[0] + "_pre_weld.glb"
            os.makedirs(os.path.dirname(_welded), exist_ok=True)
            _wr = mesh_weld.weld(os.path.abspath(args.input), _welded, dist=0.0008)
            if _wr.get("ok") and os.path.isfile(_welded):
                print("RIGIFY_INFO: entree soudee %d->%d sommets, %d->%d ilots"
                      % (_wr.get("verts_before", 0), _wr.get("verts_after", 0),
                         _wr.get("islands_before", 0), _wr.get("islands_after", 0)),
                      file=sys.stderr)
                args.input = _welded
            else:
                print("RIGIFY_INFO: soudure amont indispo (%s) -> entree brute"
                      % _wr.get("error"), file=sys.stderr)
        except Exception as _we:  # noqa: BLE001
            print("RIGIFY_INFO: soudure amont echec (%r) -> entree brute" % _we,
                  file=sys.stderr)

    # --------- MIA path (opt-in via --use-mia) ---------
    # MIA replaces Rigify for humans when the caller explicitly asks and the
    # env is available. Skinning weights are anatomically clean (mesh/shirt
    # separated from arm bones), so a 45° arm swing during walk doesn't
    # explode the sleeves — the defect that plagues the Rigify path on TRELLIS
    # meshes with proxy 50k. Falls back to Rigify silently on any error.
    if args.use_mia and args.metarig == "human":
        input_abs = os.path.abspath(args.input)
        output_abs = os.path.abspath(args.output)
        if not os.path.isfile(input_abs):
            print(json.dumps({"ok": False, "error": f"input GLB missing: {input_abs}"}))
            return 11
        if _mia_available(args.mia_root, args.mia_python):
            os.makedirs(os.path.dirname(output_abs), exist_ok=True)
            mia_out_dir = os.path.join(os.path.dirname(output_abs), "mia_work")
            produced, mia_log = _run_mia(
                input_abs, mia_out_dir, args.mia_root, args.mia_python,
                rest_pose_type=args.mia_rest_pose,
                reset_to_rest=False,   # KEEP A-pose weights — natural walk swing
                no_fingers=True,       # humain has hands closed/at sides
            )
            print("--- MIA OUTPUT ---", file=sys.stderr)
            print(mia_log if mia_log else "(no log)", file=sys.stderr)
            print("------------------", file=sys.stderr)
            if produced and os.path.isfile(produced):
                # MIA rigs a Mixamo FK skeleton with anatomical skinning but bakes
                # NO animation. Aurora's motion_baker presets target Rigify+IK bones
                # that don't exist here -> apply_compiled_motion would skip every bone
                # ("exported no glTF animations"). If a locomotion was requested, bake
                # a procedural walk DIRECTLY on the Mixamo bones so the subject moves.
                final_src = produced
                walk_note = ""
                # GENUINE motion first: MoMask text-to-motion retargeted onto the
                # Mixamo rig (handles walk/run/dance/wave/... from the natural
                # description). Procedural walk is only a LAST-RESORT fallback for
                # locomotion if MoMask/retarget is unavailable — never the default.
                motion_text = (getattr(args, "motion_text", "") or "").strip()
                if motion_text:
                    animated = os.path.join(os.path.dirname(output_abs), "mia_work", "mia_motion.glb")
                    ok_m, mlog = _apply_mia_motion(produced, animated, motion_text)
                    if ok_m:
                        final_src = animated
                        walk_note = " + mouvement MoMask (texte->mouvement) retargete sur Mixamo"
                    else:
                        print("MIA_MOTION_INFO: MoMask/retarget indispo -> fallback marche proc. " + mlog, file=sys.stderr)
                if not walk_note:
                    _loco = _motion_is_locomotion(args.motion)
                    if _loco:
                        animated = os.path.join(os.path.dirname(output_abs), "mia_work", "mia_walk.glb")
                        ok_walk, wlog = _apply_mia_walk(produced, animated, _loco)
                        if ok_walk:
                            final_src = animated
                            walk_note = f" + marche procedurale Mixamo (fallback, {_loco['frames']}f)"
                        else:
                            print("MIA_WALK_INFO: fallback marche echoue -> rig sans animation. " + wlog, file=sys.stderr)
                try:
                    shutil.copyfile(final_src, output_abs)
                except Exception as e:
                    print(json.dumps({"ok": False, "error": f"MIA output copy failed: {e}"}))
                    return 16
                print(json.dumps({
                    "ok": True,
                    "rigger": "make-it-animatable",
                    "path": output_abs,
                    "size_bytes": os.path.getsize(output_abs),
                    "animated": bool(walk_note),
                    "notes": "MIA anatomical skinning — no sleeve bleed on arm swing. skin='keep' recommended downstream (no re-bind, no Corrective Smooth)." + walk_note,
                }, ensure_ascii=False))
                return 0
            # else: fall through to Rigify
            print("MIA_INFO: MIA path failed, falling back to Rigify", file=sys.stderr)
        else:
            print("MIA_INFO: MIA env unavailable, using Rigify", file=sys.stderr)

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

    mocap_abs = ""
    if args.mocap_bvh:
        mocap_abs = os.path.abspath(args.mocap_bvh)
        if not os.path.isfile(mocap_abs):
            print(json.dumps({"ok": False, "error": f"mocap BVH missing: {mocap_abs}"}))
            return 15

    cmd = [blender, "--background", "--python", script_path, "--", input_abs, output_abs, motion_abs, args.metarig, args.pose, mocap_abs]
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
