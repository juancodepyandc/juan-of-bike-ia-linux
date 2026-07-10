import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

BLENDER_SCRIPT = r'''
import bpy, sys, os
import numpy as np

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
src, dst = argv[0], argv[1]
res = int(argv[2]) if len(argv) > 2 else 8192
target_tris = int(argv[3]) if len(argv) > 3 else 900000

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=src)
sources = [o for o in bpy.context.scene.objects if o.type == "MESH"]
if not sources:
    print("SANITIZE_FAIL: pas de mesh")
    sys.exit(2)
src_obj = max(sources, key=lambda o: len(o.data.polygons))

clean_ply = argv[4] if len(argv) > 4 else ""

if clean_ply and os.path.isfile(clean_ply):
    bpy.ops.wm.ply_import(filepath=clean_ply)
    clean = bpy.context.active_object
    clean.matrix_world = src_obj.matrix_world.copy()
    bpy.ops.object.select_all(action="DESELECT")
    clean.select_set(True)
    bpy.context.view_layer.objects.active = clean
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.mesh.normals_make_consistent(inside=False)
    bpy.ops.object.mode_set(mode="OBJECT")
    try:
        bpy.ops.mesh.customdata_custom_splitnormals_clear()
    except Exception:
        pass
    _smf = np.ones(len(clean.data.polygons), dtype=bool)
    clean.data.polygons.foreach_set("use_smooth", _smf)
    clean.data.update()
    size = max(clean.dimensions)
    print("SANITIZE_INFO: mesh nettoye charge (%d tris)" % len(clean.data.polygons))
else:
    clean = src_obj.copy()
    clean.data = src_obj.data.copy()
    bpy.context.scene.collection.objects.link(clean)
    for m in list(clean.modifiers):
        clean.modifiers.remove(m)
    size = max(clean.dimensions)
    rm = clean.modifiers.new("rm", "REMESH")
    rm.mode = "VOXEL"
    rm.voxel_size = max(size / 420.0, 0.0006)
    with bpy.context.temp_override(object=clean, active_object=clean, selected_editable_objects=[clean]):
        bpy.ops.object.modifier_apply(modifier=rm.name)
    try:
        _before = set(o.name for o in bpy.context.scene.objects)
        bpy.ops.object.select_all(action="DESELECT")
        clean.select_set(True)
        bpy.context.view_layer.objects.active = clean
        bpy.ops.object.mode_set(mode="EDIT")
        bpy.ops.mesh.select_all(action="SELECT")
        bpy.ops.mesh.separate(type="LOOSE")
        bpy.ops.object.mode_set(mode="OBJECT")
        _parts = [o for o in bpy.context.scene.objects
                  if o.type == "MESH" and (o == clean or o.name not in _before)]
        if len(_parts) > 1:
            _parts.sort(key=lambda o: len(o.data.polygons), reverse=True)
            clean = _parts[0]
            for o in _parts[1:]:
                bpy.data.objects.remove(o, do_unlink=True)
            print("SANITIZE_INFO: %d coques internes supprimees" % (len(_parts) - 1))
    except Exception as _ie:
        print("SANITIZE_INFO: separation coques echec: %s" % _ie)
    sm = clean.modifiers.new("sm", "SMOOTH")
    sm.factor = 1.0
    sm.iterations = 20
    with bpy.context.temp_override(object=clean, active_object=clean, selected_editable_objects=[clean]):
        bpy.ops.object.modifier_apply(modifier=sm.name)
    tri = clean.modifiers.new("tri", "TRIANGULATE")
    with bpy.context.temp_override(object=clean, active_object=clean, selected_editable_objects=[clean]):
        bpy.ops.object.modifier_apply(modifier=tri.name)
    n0 = len(clean.data.polygons)
    if n0 > target_tris:
        dec = clean.modifiers.new("dec", "DECIMATE")
        dec.ratio = target_tris / float(n0)
        with bpy.context.temp_override(object=clean, active_object=clean, selected_editable_objects=[clean]):
            bpy.ops.object.modifier_apply(modifier=dec.name)
        tri2 = clean.modifiers.new("tri2", "TRIANGULATE")
        with bpy.context.temp_override(object=clean, active_object=clean, selected_editable_objects=[clean]):
            bpy.ops.object.modifier_apply(modifier=tri2.name)
    bpy.ops.object.select_all(action="DESELECT")
    clean.select_set(True)
    bpy.context.view_layer.objects.active = clean
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.mesh.normals_make_consistent(inside=False)
    bpy.ops.object.mode_set(mode="OBJECT")
    try:
        bpy.ops.mesh.customdata_custom_splitnormals_clear()
    except Exception:
        pass
    _sm = np.ones(len(clean.data.polygons), dtype=bool)
    clean.data.polygons.foreach_set("use_smooth", _sm)
    clean.data.update()
    print("SANITIZE_INFO: normales exterieures + shading lisse uniforme")
    print("SANITIZE_INFO: remesh %d -> %d tris (voxel %.4f)" % (n0, len(clean.data.polygons), rm.voxel_size if hasattr(rm, "voxel_size") else 0))

me = clean.data
while me.uv_layers:
    me.uv_layers.remove(me.uv_layers[0])
me.uv_layers.new(name="AuroraUV")
me.uv_layers.active = me.uv_layers["AuroraUV"]
me.uv_layers["AuroraUV"].active_render = True
bpy.ops.object.select_all(action="DESELECT")
clean.select_set(True)
bpy.context.view_layer.objects.active = clean
import tempfile as _tf, subprocess as _sp
_venv_py = os.environ.get("AURORA_VENV_PY", sys.executable)
_faces = np.empty(len(me.polygons) * 3, dtype=np.int64)
me.polygons.foreach_get("vertices", _faces)
_faces = _faces.reshape(-1, 3)
_verts = np.empty(len(me.vertices) * 3, dtype=np.float64)
me.vertices.foreach_get("co", _verts)
_verts = _verts.reshape(-1, 3)
_tin = _tf.mktemp(suffix=".npz")
_tout = _tf.mktemp(suffix=".npz")
np.savez(_tin, v=_verts, f=_faces)
_code = ("import numpy as np, xatlas; d = np.load(%r); "
         "vm, idx, uv = xatlas.parametrize(d['v'], d['f'].astype(np.uint32)); "
         "np.savez(%r, idx=idx, uv=uv)") % (_tin, _tout)
_r = _sp.run([_venv_py, "-c", _code], capture_output=True, text=True, timeout=1200)
if _r.returncode != 0 or not os.path.isfile(_tout):
    print("SANITIZE_FAIL: xatlas: %s" % (_r.stderr or "")[-200:])
    sys.exit(5)
_d = np.load(_tout)
_idx = _d["idx"].astype(np.int64)
_uvn = _d["uv"].astype(np.float32)
if _uvn.max() > 1.001 or _uvn.min() < -0.001:
    _rng = _uvn.max(axis=0) - _uvn.min(axis=0)
    _uvn = (_uvn - _uvn.min(axis=0)) / np.maximum(_rng, 1e-8)
me.uv_layers["AuroraUV"].data.foreach_set("uv", _uvn[_idx.reshape(-1)].reshape(-1))

uvd = me.uv_layers.active.data
uvs = np.empty(len(uvd) * 2, dtype=np.float32)
uvd.foreach_get("uv", uvs)
uvs = uvs.reshape(-1, 2)
lv = np.empty(len(me.loops), dtype=np.int32)
me.loops.foreach_get("vertex_index", lv)
co = np.empty(len(me.vertices) * 3, dtype=np.float32)
me.vertices.foreach_get("co", co)
co = co.reshape(-1, 3)
grid = 512
xi = np.clip((uvs[:, 0] % 1.0) * (grid - 1), 0, grid - 1).astype(np.int64)
yi = np.clip((uvs[:, 1] % 1.0) * (grid - 1), 0, grid - 1).astype(np.int64)
cell = yi * grid + xi
depth = co[lv] @ np.array([0.57, 0.57, 0.57], dtype=np.float32)
order = np.argsort(cell)
cs = cell[order]; ds = depth[order]
uniq, start = np.unique(cs, return_index=True)
spans = np.split(ds, start[1:])
diag = float(np.linalg.norm(co.max(axis=0) - co.min(axis=0)))
conflict = sum(1 for s in spans if len(s) > 2 and (s.max() - s.min()) > diag * 0.05)
ratio = conflict / max(len(uniq), 1)
print("SANITIZE_INFO: xatlas sur manifold, conflit residuel = %.1f%%" % (100 * ratio))
if ratio > 0.10:
    print("SANITIZE_FAIL: UV encore en conflit apres remesh")
    sys.exit(5)
areas_px = []
for pi in range(0, len(me.polygons), max(1, len(me.polygons) // 4000)):
    pp = me.polygons[pi]
    a = uvs[pp.loop_start]; b = uvs[pp.loop_start + 1]; c = uvs[pp.loop_start + 2]
    areas_px.append(abs((b[0]-a[0])*(c[1]-a[1]) - (c[0]-a[0])*(b[1]-a[1])) * 0.5 * res * res)
med_px = float(np.median(np.array(areas_px)))
print("SANITIZE_INFO: aire UV mediane par tri = %.2f px" % med_px)
if med_px < 4.0:
    print("SANITIZE_FAIL: ilots UV trop fragmentes (mediane %.2f px)" % med_px)
    sys.exit(7)

import mathutils, math

def _uv_std(tag):
    _l = me.uv_layers.get("AuroraUV")
    if _l is None:
        print("UVPROBE %s: AuroraUV ABSENT" % tag)
        return
    _a = np.empty(len(_l.data) * 2, dtype=np.float64)
    _l.data.foreach_get("uv", _a)
    print("UVPROBE %s: std=%.4f min=%.3f max=%.3f" % (tag, _a.std(), _a.min(), _a.max()))

_uv_std("apres_smart")
sc = bpy.context.scene
sc.render.engine = "CYCLES"
try:
    sc.cycles.device = "CPU"
except Exception:
    pass
sc.cycles.samples = 1
sc.render.film_transparent = True
sc.render.resolution_x = 2048
sc.render.resolution_y = 2048

for smat in src_obj.data.materials:
    if not smat or not smat.use_nodes:
        continue
    snt = smat.node_tree
    sout = next(n for n in snt.nodes if n.type == "OUTPUT_MATERIAL")
    sbsdf = next((n for n in snt.nodes if n.type == "BSDF_PRINCIPLED"), None)
    if sbsdf is None:
        continue
    semit = snt.nodes.new("ShaderNodeEmission")
    base_links = sbsdf.inputs["Base Color"].links
    if base_links:
        snt.links.new(base_links[0].from_socket, semit.inputs["Color"])
    else:
        semit.inputs["Color"].default_value = sbsdf.inputs["Base Color"].default_value
    for lk in list(sout.inputs["Surface"].links):
        snt.links.remove(lk)
    snt.links.new(semit.outputs["Emission"], sout.inputs["Surface"])

bb = [src_obj.matrix_world @ mathutils.Vector(c) for c in src_obj.bound_box]
center = sum(bb, mathutils.Vector()) / 8.0
radius = max((p - center).length for p in bb)
dirs = [mathutils.Vector(v) for v in
        ((0, 0, 1), (1, 0, 0), (-1, 0, 0), (0, 1, 0), (0, -1, 0), (0, 0, -1))]
dirs = dirs[:int(os.environ.get("AURORA_SANITIZE_VIEWS", "6"))]

clean.hide_render = True
views = []
for i, d in enumerate(dirs):
    cam = bpy.data.cameras.new("vc%d" % i)
    cam.type = "ORTHO"
    cam.ortho_scale = radius * 2.3
    co = bpy.data.objects.new("vc%d" % i, cam)
    sc.collection.objects.link(co)
    co.location = center + d * radius * 3.0
    co.rotation_euler = (co.location - center).to_track_quat("Z", "Y").to_euler()
    sc.camera = co
    img_path = "/tmp/aurora_mv_%d.png" % i
    sc.render.filepath = img_path
    bpy.ops.render.render(write_still=True)
    views.append((co, d, img_path))
clean.hide_render = False

mat = bpy.data.materials.new("AuroraMat")
mat.use_nodes = True
nt = mat.node_tree
bsdf = next(n for n in nt.nodes if n.type == "BSDF_PRINCIPLED")
out_node = next(n for n in nt.nodes if n.type == "OUTPUT_MATERIAL")
me.materials.clear()
me.materials.append(mat)

_wv = np.empty(len(me.vertices) * 3, dtype=np.float64)
me.vertices.foreach_get("co", _wv)
_wv = _wv.reshape(-1, 3)
_mw = np.array(clean.matrix_world)
_wworld = _wv @ _mw[:3, :3].T + _mw[:3, 3]
_lv2 = np.empty(len(me.loops), dtype=np.int64)
me.loops.foreach_get("vertex_index", _lv2)
for i, (co, d, img_path) in enumerate(views):
    lname = "PV%d" % i
    _lay = me.uv_layers.new(name=lname)
    if _lay is None:
        print("SANITIZE_FAIL: limite de layers UV atteinte a %s" % lname)
        sys.exit(6)
    _cm = np.array(co.matrix_world.inverted())
    _cam_space = _wworld @ _cm[:3, :3].T + _cm[:3, 3]
    _scale = co.data.ortho_scale
    _u = _cam_space[:, 0] / _scale + 0.5
    _vv = _cam_space[:, 1] / _scale + 0.5
    _uvproj = np.stack([_u[_lv2], _vv[_lv2]], axis=1).astype(np.float32)
    _lay.data.foreach_set("uv", _uvproj.reshape(-1))
me.uv_layers.active = me.uv_layers["AuroraUV"]
me.uv_layers["AuroraUV"].active_render = True
_uv_std("apres_modificateurs")

geom = nt.nodes.new("ShaderNodeNewGeometry")
accum_color = None
accum_w = None
for i, (co, d, img_path) in enumerate(views):
    img_i = bpy.data.images.load(img_path)
    ti = nt.nodes.new("ShaderNodeTexImage")
    ti.image = img_i
    ti.extension = "CLIP"
    uvn = nt.nodes.new("ShaderNodeUVMap")
    uvn.uv_map = "PV%d" % i
    nt.links.new(uvn.outputs["UV"], ti.inputs["Vector"])
    dotn = nt.nodes.new("ShaderNodeVectorMath")
    dotn.operation = "DOT_PRODUCT"
    dotn.inputs[1].default_value = tuple(d)
    nt.links.new(geom.outputs["Normal"], dotn.inputs[0])
    mx = nt.nodes.new("ShaderNodeMath")
    mx.operation = "MAXIMUM"
    mx.inputs[1].default_value = 0.0
    nt.links.new(dotn.outputs["Value"], mx.inputs[0])
    pw = nt.nodes.new("ShaderNodeMath")
    pw.operation = "POWER"
    pw.inputs[1].default_value = 6.0
    nt.links.new(mx.outputs["Value"], pw.inputs[0])
    wa = nt.nodes.new("ShaderNodeMath")
    wa.operation = "MULTIPLY"
    nt.links.new(pw.outputs["Value"], wa.inputs[0])
    nt.links.new(ti.outputs["Alpha"], wa.inputs[1])
    wc = nt.nodes.new("ShaderNodeVectorMath")
    wc.operation = "SCALE"
    nt.links.new(ti.outputs["Color"], wc.inputs[0])
    nt.links.new(wa.outputs["Value"], wc.inputs["Scale"])
    if accum_color is None:
        accum_color = wc.outputs["Vector"]
        accum_w = wa.outputs["Value"]
    else:
        addc = nt.nodes.new("ShaderNodeVectorMath")
        addc.operation = "ADD"
        nt.links.new(accum_color, addc.inputs[0])
        nt.links.new(wc.outputs["Vector"], addc.inputs[1])
        accum_color = addc.outputs["Vector"]
        addw = nt.nodes.new("ShaderNodeMath")
        addw.operation = "ADD"
        nt.links.new(accum_w, addw.inputs[0])
        nt.links.new(wa.outputs["Value"], addw.inputs[1])
        accum_w = addw.outputs["Value"]
weps = nt.nodes.new("ShaderNodeMath")
weps.operation = "MAXIMUM"
weps.inputs[1].default_value = 1e-5
nt.links.new(accum_w, weps.inputs[0])
divn = nt.nodes.new("ShaderNodeVectorMath")
divn.operation = "SCALE"
nt.links.new(accum_color, divn.inputs[0])
inv = nt.nodes.new("ShaderNodeMath")
inv.operation = "DIVIDE"
inv.inputs[0].default_value = 1.0
nt.links.new(weps.outputs["Value"], inv.inputs[1])
nt.links.new(inv.outputs["Value"], divn.inputs["Scale"])
emitc = nt.nodes.new("ShaderNodeEmission")
nt.links.new(divn.outputs["Vector"], emitc.inputs["Color"])
for lk in list(out_node.inputs["Surface"].links):
    nt.links.remove(lk)
nt.links.new(emitc.outputs["Emission"], out_node.inputs["Surface"])

new_img = bpy.data.images.new("AuroraBase", width=res, height=res, alpha=False)
tgt = nt.nodes.new("ShaderNodeTexImage")
tgt.image = new_img
for n in nt.nodes:
    n.select = False
tgt.select = True
nt.nodes.active = tgt

src_obj.hide_render = True
bpy.ops.object.select_all(action="DESELECT")
clean.select_set(True)
bpy.context.view_layer.objects.active = clean
bpy.ops.object.bake(type="EMIT", use_selected_to_active=False, margin=12)

for lk in list(out_node.inputs["Surface"].links):
    nt.links.remove(lk)
nt.links.new(bsdf.outputs["BSDF"], out_node.inputs["Surface"])
for lk in list(bsdf.inputs["Base Color"].links):
    nt.links.remove(lk)
uvfin = nt.nodes.new("ShaderNodeUVMap")
uvfin.uv_map = "AuroraUV"
nt.links.new(uvfin.outputs["UV"], tgt.inputs["Vector"])
nt.links.new(tgt.outputs["Color"], bsdf.inputs["Base Color"])
for i in range(len(views)):
    lay = me.uv_layers.get("PV%d" % i)
    if lay is not None:
        me.uv_layers.remove(lay)
_uv_std("apres_suppression_PV")

for o in sources:
    bpy.data.objects.remove(o, do_unlink=True)
bpy.ops.object.select_all(action="SELECT")
bpy.ops.export_scene.gltf(filepath=dst, export_format="GLB", export_yup=True)
print("SANITIZE_OK: %s (%d tris)" % (dst, len(me.polygons)))
'''


def mesh_health(src):
    import numpy as np
    import trimesh
    scn = trimesh.load(str(src), process=False)
    geoms = list(scn.geometry.values()) if hasattr(scn, "geometry") else [scn]
    m = max(geoms, key=lambda g: len(g.faces))
    uv = getattr(m.visual, "uv", None)
    if uv is None or not len(uv):
        return {"sain": False, "raison": "pas d'UV d'origine"}
    v = np.asarray(m.vertices, dtype=np.float64)
    f = np.asarray(m.faces, dtype=np.int64)
    uv = np.asarray(uv, dtype=np.float64)
    diag = float(np.linalg.norm(v.max(axis=0) - v.min(axis=0))) or 1.0
    res = 4096
    try:
        img = m.visual.material.baseColorTexture
        if img is not None:
            res = max(img.size)
    except Exception:
        pass
    grid = 512
    corners = f.reshape(-1)
    fuv = uv[corners]
    xi = np.clip((fuv[:, 0] % 1.0) * (grid - 1), 0, grid - 1).astype(np.int64)
    yi = np.clip((fuv[:, 1] % 1.0) * (grid - 1), 0, grid - 1).astype(np.int64)
    cell = yi * grid + xi
    depth = v[corners] @ np.array([0.57, 0.57, 0.57])
    order = np.argsort(cell)
    cs = cell[order]
    ds = depth[order]
    uniq, start = np.unique(cs, return_index=True)
    spans = np.split(ds, start[1:])
    conflict = sum(1 for s in spans if len(s) > 2 and (s.max() - s.min()) > diag * 0.05)
    ratio = conflict / max(len(uniq), 1)
    a = uv[f[:, 0]]
    b = uv[f[:, 1]]
    c = uv[f[:, 2]]
    areas = np.abs((b[:, 0] - a[:, 0]) * (c[:, 1] - a[:, 1])
                   - (c[:, 0] - a[:, 0]) * (b[:, 1] - a[:, 1])) * 0.5
    med_px = float(np.median(areas)) * res * res
    sain = ratio <= 0.10 and med_px >= 4.0
    if sain:
        raison = None
    elif ratio > 0.10:
        raison = "conflit profondeur %.1f%% (doubles surfaces)" % (100 * ratio)
    else:
        raison = "ilots UV fragmentes (mediane %.2f px)" % med_px
    return {"sain": sain, "conflit": round(ratio, 4),
            "aire_px_mediane": round(med_px, 2), "res_atlas": res,
            "tris": int(len(f)), "raison": raison}


def _soft_clean(src, target_tris):
    import trimesh
    import pymeshlab
    scn = trimesh.load(str(src), process=False)
    geoms = list(scn.geometry.values()) if hasattr(scn, "geometry") else [scn]
    fused = trimesh.util.concatenate(geoms) if len(geoms) > 1 else geoms[0]
    tmp = tempfile.mktemp(suffix=".ply")
    fused.export(tmp)
    ms = pymeshlab.MeshSet()
    ms.load_new_mesh(tmp)
    os.unlink(tmp)
    ms.meshing_merge_close_vertices(threshold=pymeshlab.PercentageValue(0.2))
    ms.meshing_remove_duplicate_faces()
    try:
        ms.meshing_remove_connected_component_by_diameter(
            mincomponentdiag=pymeshlab.PercentageValue(1.0))
    except Exception:
        pass
    if ms.current_mesh().face_number() > int(target_tris):
        ms.meshing_decimation_quadric_edge_collapse(
            targetfacenum=int(target_tris), preservenormal=True, planarquadric=True,
            preserveboundary=True, boundaryweight=2.0, qualitythr=0.3)
    out = tempfile.mktemp(suffix=".ply")
    ms.save_current_mesh(out)
    return out


def _poisson_clean(src, target_tris):
    import numpy as np
    import trimesh
    import pymeshlab
    scn = trimesh.load(str(src))
    geoms = list(scn.geometry.values()) if hasattr(scn, "geometry") else [scn]
    v = np.vstack([np.asarray(g.vertices) for g in geoms])
    ms = pymeshlab.MeshSet()
    ms.add_mesh(pymeshlab.Mesh(vertex_matrix=v))
    ms.compute_normal_for_point_clouds(k=24, smoothiter=2)
    ms.generate_surface_reconstruction_screened_poisson(depth=10, samplespernode=1.5)
    try:
        ms.meshing_remove_connected_component_by_diameter()
    except Exception:
        pass
    try:
        ms.apply_coord_taubin_smoothing(stepsmoothnum=5)
    except Exception:
        pass
    ms.meshing_decimation_quadric_edge_collapse(targetfacenum=int(target_tris))
    out = tempfile.mktemp(suffix=".ply")
    ms.save_current_mesh(out)
    return out


def sanitize_mesh(src, dst, res=8192, target_tris=900000, timeout_s=7200):
    import shutil
    blender = os.environ.get("AURORA_BLENDER") or shutil.which("blender") or "blender"
    env = {**os.environ, "AURORA_VENV_PY": sys.executable}
    result = None
    for mode, cleaner in (("doux", _soft_clean), ("poisson", _poisson_clean)):
        try:
            ply = cleaner(src, target_tris)
        except Exception:
            ply = ""
        with tempfile.NamedTemporaryFile(suffix=".py", delete=False, mode="w", encoding="utf-8") as fp:
            fp.write(BLENDER_SCRIPT)
            script = fp.name
        try:
            p = subprocess.run([blender, "--background", "--python", script, "--",
                                str(src), str(dst), str(res), str(target_tris), ply],
                               capture_output=True, text=True, timeout=timeout_s, env=env)
        finally:
            try:
                os.unlink(script)
            except OSError:
                pass
        out = p.stdout or ""
        for _l in out.splitlines():
            if "UVPROBE" in _l:
                print(_l, flush=True)
        infos = [l for l in out.splitlines() if l.startswith("SANITIZE_INFO")]
        ok = "SANITIZE_OK" in out and Path(dst).is_file() and Path(dst).stat().st_size > 1000
        err = next((l for l in out.splitlines() if l.startswith("SANITIZE_FAIL")), "") or (p.stderr or "")[-250:]
        result = {"ok": ok, "info": ("mode %s | " % mode) + " | ".join(infos),
                  "error": None if ok else err, "output": str(dst), "mode": mode}
        if ok:
            break
        if mode == "doux":
            print("SANITIZE_RETRY: mode doux echoue (%s), tentative poisson" % err[:120], flush=True)
    return result


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True)
    ap.add_argument("--output", required=True)
    ap.add_argument("--res", type=int, default=8192)
    ap.add_argument("--tris", type=int, default=900000)
    a = ap.parse_args()
    r = sanitize_mesh(a.input, a.output, res=a.res, target_tris=a.tris)
    print("AURORA_SANITIZE_RESULT:" + json.dumps(r, ensure_ascii=False))
    return 0 if r["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
