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
n0 = len(clean.data.polygons)
if n0 > target_tris:
    dec = clean.modifiers.new("dec", "DECIMATE")
    dec.ratio = target_tris / float(n0)
    with bpy.context.temp_override(object=clean, active_object=clean, selected_editable_objects=[clean]):
        bpy.ops.object.modifier_apply(modifier=dec.name)
print("SANITIZE_INFO: remesh %d -> %d tris (voxel %.4f)" % (n0, len(clean.data.polygons), rm.voxel_size if hasattr(rm, "voxel_size") else 0))

me = clean.data
venv_py = os.environ.get("AURORA_VENV_PY", sys.executable)
import tempfile as tf, subprocess as sp
faces = np.empty(len(me.polygons) * 3, dtype=np.int64)
me.polygons.foreach_get("vertices", faces)
faces = faces.reshape(-1, 3)
verts = np.empty(len(me.vertices) * 3, dtype=np.float64)
me.vertices.foreach_get("co", verts)
verts = verts.reshape(-1, 3)
tmp_in = tf.mktemp(suffix=".npz")
tmp_out = tf.mktemp(suffix=".npz")
np.savez(tmp_in, v=verts, f=faces)
code = ("import numpy as np, xatlas; d = np.load(%r); "
        "vm, idx, uv = xatlas.parametrize(d['v'], d['f'].astype(np.uint32)); "
        "np.savez(%r, idx=idx, uv=uv)") % (tmp_in, tmp_out)
r = sp.run([venv_py, "-c", code], capture_output=True, text=True, timeout=2400)
if r.returncode != 0 or not os.path.isfile(tmp_out):
    print("SANITIZE_FAIL: xatlas: %s" % (r.stderr or "")[-200:])
    sys.exit(5)
d = np.load(tmp_out)
idx = d["idx"].astype(np.int64)
uv_new = d["uv"].astype(np.float32)
if uv_new.max() > 1.001 or uv_new.min() < -0.001:
    rng = uv_new.max(axis=0) - uv_new.min(axis=0)
    uv_new = (uv_new - uv_new.min(axis=0)) / np.maximum(rng, 1e-8)
while me.uv_layers:
    me.uv_layers.remove(me.uv_layers[0])
new_uv = me.uv_layers.new(name="AuroraUV")
new_uv.data.foreach_set("uv", uv_new[idx.reshape(-1)].reshape(-1).astype(np.float32))
me.uv_layers.active = me.uv_layers["AuroraUV"]
me.uv_layers["AuroraUV"].active_render = True
print("SANITIZE_INFO: xatlas ok (%d uvs)" % len(uv_new))

sc = bpy.context.scene
sc.render.engine = "CYCLES"
try:
    sc.cycles.device = "CPU"
except Exception:
    pass
sc.cycles.samples = 4

new_img = bpy.data.images.new("AuroraBase", width=res, height=res, alpha=False)
mat = bpy.data.materials.new("AuroraMat")
mat.use_nodes = True
nt = mat.node_tree
bsdf = next(n for n in nt.nodes if n.type == "BSDF_PRINCIPLED")
tex = nt.nodes.new("ShaderNodeTexImage")
tex.image = new_img
for n in nt.nodes:
    n.select = False
tex.select = True
nt.nodes.active = tex
me.materials.clear()
me.materials.append(mat)

bpy.ops.object.select_all(action="DESELECT")
src_obj.select_set(True)
clean.select_set(True)
bpy.context.view_layer.objects.active = clean
bpy.ops.object.bake(
    type="DIFFUSE",
    pass_filter={"COLOR"},
    use_selected_to_active=True,
    cage_extrusion=size * 0.004,
    max_ray_distance=size * 0.015,
    margin=12,
)

nt.links.new(tex.outputs["Color"], bsdf.inputs["Base Color"])
uvn = nt.nodes.new("ShaderNodeUVMap")
uvn.uv_map = "AuroraUV"
nt.links.new(uvn.outputs["UV"], tex.inputs["Vector"])

for o in sources:
    bpy.data.objects.remove(o, do_unlink=True)
bpy.ops.object.select_all(action="SELECT")
bpy.ops.export_scene.gltf(filepath=dst, export_format="GLB", export_yup=True)
print("SANITIZE_OK: %s (%d tris)" % (dst, len(me.polygons)))
'''


def sanitize_mesh(src, dst, res=8192, target_tris=900000, timeout_s=7200):
    import shutil
    blender = os.environ.get("AURORA_BLENDER") or shutil.which("blender") or "blender"
    with tempfile.NamedTemporaryFile(suffix=".py", delete=False, mode="w", encoding="utf-8") as fp:
        fp.write(BLENDER_SCRIPT)
        script = fp.name
    try:
        env = {**os.environ, "AURORA_VENV_PY": sys.executable}
        p = subprocess.run([blender, "--background", "--python", script, "--",
                            str(src), str(dst), str(res), str(target_tris)],
                           capture_output=True, text=True, timeout=timeout_s, env=env)
    finally:
        try:
            os.unlink(script)
        except OSError:
            pass
    out = p.stdout or ""
    infos = [l for l in out.splitlines() if l.startswith("SANITIZE_INFO")]
    ok = "SANITIZE_OK" in out and Path(dst).is_file() and Path(dst).stat().st_size > 1000
    err = next((l for l in out.splitlines() if l.startswith("SANITIZE_FAIL")), "") or (p.stderr or "")[-250:]
    return {"ok": ok, "info": " | ".join(infos), "error": None if ok else err, "output": str(dst)}


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
