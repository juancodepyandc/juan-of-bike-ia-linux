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
src, dst, mask_png = argv[0], argv[1], argv[2]
frames = int(argv[3]) if len(argv) > 3 else 60

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=src)
meshes = [o for o in bpy.context.scene.objects if o.type == "MESH"]
if not meshes:
    print("DRAPE_FAIL: pas de mesh")
    sys.exit(2)
obj = max(meshes, key=lambda o: len(o.data.polygons))
me = obj.data
if not me.uv_layers.active:
    print("DRAPE_FAIL: pas d'UV pour echantillonner le masque")
    sys.exit(3)

from PIL import Image
mimg = Image.open(mask_png).convert("L")
W, H = mimg.size
marr = np.asarray(mimg, dtype=np.float32) / 255.0

uvd = me.uv_layers.active.data
uvs = np.empty(len(uvd) * 2, dtype=np.float32)
uvd.foreach_get("uv", uvs)
uvs = uvs.reshape(-1, 2)
lv = np.empty(len(me.loops), dtype=np.int64)
me.loops.foreach_get("vertex_index", lv)
xi = np.clip((uvs[:, 0] % 1.0) * (W - 1), 0, W - 1).astype(np.int64)
yi = np.clip(((1.0 - uvs[:, 1]) % 1.0) * (H - 1), 0, H - 1).astype(np.int64)
lm = marr[yi, xi]
vw = np.zeros(len(me.vertices), dtype=np.float32)
cnt = np.zeros(len(me.vertices), dtype=np.int32)
np.add.at(vw, lv, lm)
np.add.at(cnt, lv, 1)
vw = vw / np.maximum(cnt, 1)
tissu = vw > 0.5
n_tissu = int(tissu.sum())
print("DRAPE_INFO: %d/%d verts tissu" % (n_tissu, len(vw)))
if n_tissu < 100:
    print("DRAPE_FAIL: zone tissu trop petite")
    sys.exit(4)

edges = np.empty(len(me.edges) * 2, dtype=np.int64)
me.edges.foreach_get("vertices", edges)
edges = edges.reshape(-1, 2)
boundary = np.zeros(len(vw), dtype=bool)
mixed = tissu[edges[:, 0]] != tissu[edges[:, 1]]
boundary[edges[mixed, 0]] = True
boundary[edges[mixed, 1]] = True
pin = boundary & tissu
for _ in range(2):
    grow = np.zeros(len(vw), dtype=bool)
    e_pin = pin[edges[:, 0]] | pin[edges[:, 1]]
    grow[edges[e_pin, 0]] = True
    grow[edges[e_pin, 1]] = True
    pin = (pin | grow) & tissu
print("DRAPE_INFO: %d verts epingles (bordure)" % int(pin.sum()))

vg_tissu = obj.vertex_groups.new(name="AuroraTissu")
vg_pin = obj.vertex_groups.new(name="AuroraPin")
vg_tissu.add(np.where(tissu)[0].tolist(), 1.0, "REPLACE")
vg_pin.add(np.where(pin)[0].tolist(), 1.0, "REPLACE")
vg_pin.add(np.where(~tissu)[0].tolist(), 1.0, "REPLACE")

body = obj.copy()
body.data = obj.data.copy()
bpy.context.scene.collection.objects.link(body)
col = body.modifiers.new("col", "COLLISION")
body.collision.thickness_outer = 0.003
body.hide_render = True

cloth = obj.modifiers.new("tissu", "CLOTH")
cs = cloth.settings
cs.vertex_group_mass = "AuroraPin"
cs.pin_stiffness = 1.0
cs.quality = 8
cs.mass = 0.25
cs.tension_stiffness = 12.0
cs.bending_stiffness = 0.4
cloth.collision_settings.collision_quality = 4
cloth.collision_settings.distance_min = 0.004
cloth.collision_settings.use_self_collision = False

sc = bpy.context.scene
sc.frame_start = 1
sc.frame_end = frames
cs.effector_weights.gravity = 1.0
for f in range(1, frames + 1):
    sc.frame_set(f)
dg = bpy.context.evaluated_depsgraph_get()
sc.frame_set(frames)
with bpy.context.temp_override(object=obj, active_object=obj, selected_editable_objects=[obj]):
    bpy.ops.object.modifier_apply(modifier=cloth.name)
bpy.data.objects.remove(body, do_unlink=True)
for vgn in ("AuroraTissu", "AuroraPin"):
    vg = obj.vertex_groups.get(vgn)
    if vg:
        obj.vertex_groups.remove(vg)

bpy.ops.object.select_all(action="SELECT")
bpy.ops.export_scene.gltf(filepath=dst, export_format="GLB", export_animations=True, export_yup=True)
print("DRAPE_OK: %s" % dst)
'''


def bake_drape(src, dst, mask_png, frames=60, timeout_s=3600):
    import shutil
    blender = os.environ.get("AURORA_BLENDER") or shutil.which("blender") or "blender"
    with tempfile.NamedTemporaryFile(suffix=".py", delete=False, mode="w", encoding="utf-8") as fp:
        fp.write(BLENDER_SCRIPT)
        script = fp.name
    try:
        p = subprocess.run([blender, "--background", "--python", script, "--",
                            str(src), str(dst), str(mask_png), str(frames)],
                           capture_output=True, text=True, timeout=timeout_s)
    finally:
        try:
            os.unlink(script)
        except OSError:
            pass
    out = p.stdout or ""
    infos = [l for l in out.splitlines() if l.startswith("DRAPE_INFO")]
    ok = "DRAPE_OK" in out and Path(dst).is_file() and Path(dst).stat().st_size > 1000
    err = next((l for l in out.splitlines() if l.startswith("DRAPE_FAIL")), "") or (p.stderr or "")[-250:]
    return {"ok": ok, "info": " | ".join(infos), "error": None if ok else err}


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True)
    ap.add_argument("--output", required=True)
    ap.add_argument("--mask", required=True)
    ap.add_argument("--frames", type=int, default=60)
    a = ap.parse_args()
    r = bake_drape(a.input, a.output, a.mask, frames=a.frames)
    print("AURORA_DRAPE_RESULT:" + json.dumps(r, ensure_ascii=False))
    return 0 if r["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
