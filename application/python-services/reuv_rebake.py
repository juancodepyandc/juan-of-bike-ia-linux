import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

BLENDER_SCRIPT = r'''
import bpy, sys
import numpy as np

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
src, dst = argv[0], argv[1]
res = int(argv[2]) if len(argv) > 2 else 8192

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=src)
obj = max([o for o in bpy.context.scene.objects if o.type == "MESH"],
          key=lambda o: len(o.data.polygons))
me = obj.data
if not me.uv_layers or not me.materials:
    print("REUV_SKIP: pas d'UV ou de materiau")
    sys.exit(0)

uv = me.uv_layers.active.data
uvs = np.empty(len(uv) * 2, dtype=np.float32)
uv.foreach_get("uv", uvs)
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
print("REUV_INFO: conflit UV avant/arriere = %.1f%%" % (100 * ratio))
if ratio < 0.05:
    print("REUV_SKIP: atlas deja propre")
    sys.exit(0)

src_img = None
for mat in me.materials:
    if not mat or not mat.use_nodes:
        continue
    for n in mat.node_tree.nodes:
        if n.type == "BSDF_PRINCIPLED":
            base = n.inputs.get("Base Color")
            if base is not None and base.links:
                nn = base.links[0].from_node
                if nn.type == "TEX_IMAGE" and nn.image is not None:
                    src_img = nn.image
if src_img is None:
    print("REUV_SKIP: pas de texture base color")
    sys.exit(0)

old_uv_name = me.uv_layers.active.name
bpy.ops.object.select_all(action="DESELECT")
obj.select_set(True)
bpy.context.view_layer.objects.active = obj

import tempfile, subprocess as sp, os as _os
venv_py = _os.environ.get("AURORA_VENV_PY", sys.executable)
n_polys = len(me.polygons)
tri_ok = all(p.loop_total == 3 for p in me.polygons[:200])
if not tri_ok:
    print("REUV_SKIP: mesh non triangulaire")
    sys.exit(0)
faces = np.empty(n_polys * 3, dtype=np.int64)
me.polygons.foreach_get("vertices", faces)
faces = faces.reshape(-1, 3)
verts = np.empty(len(me.vertices) * 3, dtype=np.float64)
me.vertices.foreach_get("co", verts)
verts = verts.reshape(-1, 3)
tmp_in = tempfile.mktemp(suffix=".npz")
tmp_out = tempfile.mktemp(suffix=".npz")
np.savez(tmp_in, v=verts, f=faces)
code = ("import numpy as np, xatlas; d = np.load(%r); "
        "vm, idx, uv = xatlas.parametrize(d['v'], d['f'].astype(np.uint32)); "
        "np.savez(%r, idx=idx, uv=uv)") % (tmp_in, tmp_out)
r = sp.run([venv_py, "-c", code], capture_output=True, text=True, timeout=1800)
if r.returncode != 0 or not _os.path.isfile(tmp_out):
    print("REUV_FAIL: xatlas: %s" % (r.stderr or "")[-200:])
    sys.exit(5)
d = np.load(tmp_out)
idx = d["idx"].astype(np.int64)
uv_new = d["uv"].astype(np.float32)
if uv_new.max() > 1.001 or uv_new.min() < -0.001:
    rng = uv_new.max(axis=0) - uv_new.min(axis=0)
    uv_new = (uv_new - uv_new.min(axis=0)) / np.maximum(rng, 1e-8)
loop_uvs = uv_new[idx.reshape(-1)]
new_uv = me.uv_layers.new(name="AuroraUV")
new_uv.data.foreach_set("uv", loop_uvs.reshape(-1).astype(np.float32))
me.uv_layers.active = me.uv_layers["AuroraUV"]
me.uv_layers["AuroraUV"].active_render = True
print("REUV_INFO: xatlas ok (%d ilots impossibles a compter, uv loops=%d)" % (0, len(loop_uvs)))

sc = bpy.context.scene
sc.render.engine = "CYCLES"
try:
    sc.cycles.device = "CPU"
except Exception:
    pass
sc.cycles.samples = 1

new_img = bpy.data.images.new("AuroraBase", width=res, height=res, alpha=False)
mat = me.materials[0]
nt = mat.node_tree
bsdf = next(n for n in nt.nodes if n.type == "BSDF_PRINCIPLED")
out_node = next(n for n in nt.nodes if n.type == "OUTPUT_MATERIAL")
emit = nt.nodes.new("ShaderNodeEmission")
src_tex = nt.nodes.new("ShaderNodeTexImage")
src_tex.image = src_img
old_uv_node = nt.nodes.new("ShaderNodeUVMap")
old_uv_node.uv_map = old_uv_name
nt.links.new(old_uv_node.outputs["UV"], src_tex.inputs["Vector"])
nt.links.new(src_tex.outputs["Color"], emit.inputs["Color"])
for lk in list(out_node.inputs["Surface"].links):
    nt.links.remove(lk)
nt.links.new(emit.outputs["Emission"], out_node.inputs["Surface"])

tgt_tex = nt.nodes.new("ShaderNodeTexImage")
tgt_tex.image = new_img
for n in nt.nodes:
    n.select = False
tgt_tex.select = True
nt.nodes.active = tgt_tex

bpy.ops.object.bake(type="EMIT", use_selected_to_active=False, margin=12)

for lk in list(out_node.inputs["Surface"].links):
    nt.links.remove(lk)
nt.links.new(bsdf.outputs["BSDF"], out_node.inputs["Surface"])
for lk in list(bsdf.inputs["Base Color"].links):
    nt.links.remove(lk)
new_uv_node = nt.nodes.new("ShaderNodeUVMap")
new_uv_node.uv_map = "AuroraUV"
nt.links.new(new_uv_node.outputs["UV"], tgt_tex.inputs["Vector"])
nt.links.new(tgt_tex.outputs["Color"], bsdf.inputs["Base Color"])

layer = me.uv_layers.get(old_uv_name)
if layer is not None:
    me.uv_layers.remove(layer)
bpy.ops.object.select_all(action="SELECT")
bpy.ops.export_scene.gltf(filepath=dst, export_format="GLB", export_yup=True)
print("REUV_OK: %s" % dst)
'''


def reuv_rebake(src, dst, res=8192, timeout_s=3600):
    import shutil
    blender = os.environ.get("AURORA_BLENDER") or shutil.which("blender") or "blender"
    with tempfile.NamedTemporaryFile(suffix=".py", delete=False, mode="w", encoding="utf-8") as fp:
        fp.write(BLENDER_SCRIPT)
        script = fp.name
    try:
        env = {**os.environ, "AURORA_VENV_PY": sys.executable}
        p = subprocess.run([blender, "--background", "--python", script, "--",
                            str(src), str(dst), str(res)],
                           capture_output=True, text=True, timeout=timeout_s, env=env)
    finally:
        try:
            os.unlink(script)
        except OSError:
            pass
    out = p.stdout or ""
    info = next((l for l in out.splitlines() if l.startswith("REUV_INFO")), "")
    if "REUV_SKIP" in out:
        return {"ok": True, "skipped": True, "info": info,
                "reason": next((l for l in out.splitlines() if l.startswith("REUV_SKIP")), "")}
    ok = "REUV_OK" in out and Path(dst).is_file() and Path(dst).stat().st_size > 1000
    return {"ok": ok, "skipped": False, "info": info,
            "error": None if ok else (p.stderr or out)[-300:]}


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True)
    ap.add_argument("--output", required=True)
    ap.add_argument("--res", type=int, default=8192)
    a = ap.parse_args()
    r = reuv_rebake(a.input, a.output, res=a.res)
    print("AURORA_REUV_RESULT:" + json.dumps(r, ensure_ascii=False))
    return 0 if r["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
