import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

BLENDER_SCRIPT = r'''
import bpy, sys, os, math, colorsys
import numpy as np

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
src, dst = argv[0], argv[1]
fps = int(argv[2]) if len(argv) > 2 else 24
loop_s = float(argv[3]) if len(argv) > 3 else 3.0
amp_scale = float(argv[4]) if len(argv) > 4 else 1.0
couleur_cible = argv[5] if len(argv) > 5 else "bleu"
vitesse = float(argv[6]) if len(argv) > 6 else 1.0

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=src)
meshes = [o for o in bpy.context.scene.objects if o.type == "MESH"]
if not meshes:
    print("EAU_FAIL: pas de mesh")
    sys.exit(2)
obj = max(meshes, key=lambda o: len(o.data.polygons))
me = obj.data

img = None
for mat in me.materials:
    if not mat or not mat.use_nodes:
        continue
    for n in mat.node_tree.nodes:
        if n.type == "BSDF_PRINCIPLED":
            base = n.inputs.get("Base Color")
            if base is not None:
                for lk in base.links:
                    src_node = lk.from_node
                    if src_node.type == "TEX_IMAGE" and src_node.image is not None:
                        img = src_node.image
                    elif src_node.type == "MIX" or src_node.type == "MIX_RGB":
                        for inp in src_node.inputs:
                            for lk2 in inp.links:
                                if lk2.from_node.type == "TEX_IMAGE" and lk2.from_node.image is not None:
                                    img = lk2.from_node.image
    if img:
        break
if img is None:
    for mat in me.materials:
        if not mat or not mat.use_nodes:
            continue
        for n in mat.node_tree.nodes:
            if n.type == "TEX_IMAGE" and n.image is not None and "normal" not in (n.image.name or "").lower():
                img = n.image
                break
        if img:
            break
if img is None or not me.uv_layers.active:
    print("EAU_FAIL: pas de texture ou d'UV")
    sys.exit(3)

w, h = img.size
px = np.empty(w * h * 4, dtype=np.float32)
img.pixels.foreach_get(px)
px = px.reshape(h, w, 4)

n_verts = len(me.vertices)
uv_layer = me.uv_layers.active.data
loops = me.loops
sum_rgb = np.zeros((n_verts, 3), dtype=np.float64)
cnt = np.zeros(n_verts, dtype=np.int32)
uvs = np.empty(len(uv_layer) * 2, dtype=np.float32)
uv_layer.foreach_get("uv", uvs)
uvs = uvs.reshape(-1, 2)
lv = np.empty(len(loops), dtype=np.int32)
loops.foreach_get("vertex_index", lv)
xi = np.clip((uvs[:, 0] % 1.0) * (w - 1), 0, w - 1).astype(np.int32)
yi = np.clip((uvs[:, 1] % 1.0) * (h - 1), 0, h - 1).astype(np.int32)
cols = px[yi, xi, :3]
np.add.at(sum_rgb, lv, cols)
np.add.at(cnt, lv, 1)
cnt = np.maximum(cnt, 1)
rgb = sum_rgb / cnt[:, None]

mx = rgb.max(axis=1)
mn = rgb.min(axis=1)
val = mx
sat = np.where(mx > 1e-5, (mx - mn) / np.maximum(mx, 1e-5), 0.0)
r, g, b = rgb[:, 0], rgb[:, 1], rgb[:, 2]
if couleur_cible == "chaud":
    cible_dom = (r > b * 1.25) & (r > g * 1.05) & (val > 0.35)
elif couleur_cible == "blanc":
    cible_dom = (val > 0.80) & (sat < 0.12)
elif couleur_cible == "sombre":
    cible_dom = (val < 0.25)
else:
    cible_dom = (b > r * 1.22) & (b > g * 1.10) & (val > 0.30) & (sat > 0.14)
water = cible_dom.copy()

co = np.empty(n_verts * 3, dtype=np.float64)
me.vertices.foreach_get("co", co)
co = co.reshape(-1, 3)
nrm = np.empty(n_verts * 3, dtype=np.float64)
me.vertices.foreach_get("normal", nrm)
nrm = nrm.reshape(-1, 3)

edges = np.empty(len(me.edges) * 2, dtype=np.int32)
me.edges.foreach_get("vertices", edges)
edges = edges.reshape(-1, 2)
foam = (val > 0.85) & (sat < 0.08) & (b >= r)
for _ in range(3):
    votes = np.zeros(n_verts, dtype=np.int32)
    deg = np.zeros(n_verts, dtype=np.int32)
    wa = water[edges[:, 0]].astype(np.int32)
    wb = water[edges[:, 1]].astype(np.int32)
    np.add.at(votes, edges[:, 0], wb)
    np.add.at(votes, edges[:, 1], wa)
    np.add.at(deg, edges[:, 0], 1)
    np.add.at(deg, edges[:, 1], 1)
    frac = votes / np.maximum(deg, 1)
    water = (water & (frac >= 0.25)) | (frac >= 0.6) | (foam & (frac >= 0.4))

n_water = int(water.sum())
frac_water = n_water / max(n_verts, 1)
print("EAU_INFO: %d/%d verts eau (%.1f%%)" % (n_water, n_verts, 100 * frac_water))
if frac_water < 0.02:
    print("EAU_FAIL: trop peu d'eau detectee")
    sys.exit(4)

size = float(max(obj.dimensions))
lam = max(size * 0.16, 1e-4)
lam_z = max(size * 0.10, 1e-4)
flat = nrm[:, 2] > 0.75
steep = nrm[:, 2] < 0.35
amp_flat = size * 0.005 * amp_scale
amp_mid = size * 0.002 * amp_scale
amp_steep = size * 0.004 * amp_scale

cx = float(co[water, 0].mean()) if water.any() else float(co[:, 0].mean())
cy = float(co[water, 1].mean()) if water.any() else float(co[:, 1].mean())
rad = np.sqrt((co[:, 0] - cx) ** 2 + (co[:, 1] - cy) ** 2)

if me.shape_keys is None:
    obj.shape_key_add(name="Basis", from_mix=False)
K = 8
keys = []
idx_water = np.where(water)[0]
for k in range(K):
    ph = 2.0 * math.pi * k / K
    sk = obj.shape_key_add(name="Eau_%02d" % k, from_mix=False)
    disp = np.zeros((n_verts, 3), dtype=np.float64)
    idx_flat = idx_water[flat[idx_water]]
    idx_steep = idx_water[steep[idx_water]]
    idx_mid = idx_water[~flat[idx_water] & ~steep[idx_water]]
    if len(idx_flat):
        ripple = amp_flat * np.sin(rad[idx_flat] / lam * 2.0 * math.pi - ph)
        ripple += 0.4 * amp_flat * np.sin(rad[idx_flat] / (lam * 0.43) * 2.0 * math.pi - ph * 2.0)
        disp[idx_flat, 2] = ripple
    if len(idx_mid):
        stream = amp_mid * np.sin(co[idx_mid, 2] / lam_z * 2.0 * math.pi + ph)
        disp[idx_mid] = nrm[idx_mid] * stream[:, None]
        disp[idx_mid, 2] -= amp_mid * 0.7 * (0.5 + 0.5 * np.sin(co[idx_mid, 2] / lam_z * 2.0 * math.pi + ph))
    if len(idx_steep):
        stream = np.sin(co[idx_steep, 2] / lam_z * 2.0 * math.pi + ph)
        disp[idx_steep] = nrm[idx_steep] * (amp_steep * 0.5 * stream)[:, None]
        disp[idx_steep, 2] -= amp_steep * (0.5 + 0.5 * stream)
    new_co = (co + disp).reshape(-1)
    sk.data.foreach_set("co", new_co.astype(np.float32))
    keys.append(sk)

frame_count = max(int(round(fps * loop_s / max(vitesse, 0.2))), K * 2)
sc = bpy.context.scene
sc.frame_start = 1
sc.frame_end = frame_count
for k, sk in enumerate(keys):
    for f in range(1, frame_count + 1):
        t = (f - 1) / float(frame_count)
        pos = (t * K) % K
        d = min(abs(pos - k), K - abs(pos - k))
        sk.value = max(0.0, 1.0 - d)
        sk.keyframe_insert("value", frame=f)

bpy.ops.object.select_all(action="SELECT")
bpy.ops.export_scene.gltf(filepath=dst, export_format="GLB",
                          export_animations=True, export_yup=True,
                          export_morph=True)
print("EAU_OK: %s (K=%d, frames=%d)" % (dst, K, frame_count))
'''


def animate_sculpted_water(src, dst, fps=24, loop_s=3.0, timeout_s=1800, amp_scale=1.0,
                           couleur_cible="bleu", vitesse=1.0):
    import shutil
    blender = os.environ.get("AURORA_BLENDER") or shutil.which("blender") or "blender"
    with tempfile.NamedTemporaryFile(suffix=".py", delete=False, mode="w", encoding="utf-8") as fp:
        fp.write(BLENDER_SCRIPT)
        script = fp.name
    try:
        p = subprocess.run([blender, "--background", "--python", script, "--",
                            str(src), str(dst), str(fps), str(loop_s), str(amp_scale),
                            str(couleur_cible), str(vitesse)],
                           capture_output=True, text=True, timeout=timeout_s)
    finally:
        try:
            os.unlink(script)
        except OSError:
            pass
    out = (p.stdout or "")
    info = next((l for l in out.splitlines() if l.startswith("EAU_INFO")), "")
    ok = "EAU_OK" in out and Path(dst).is_file() and Path(dst).stat().st_size > 1000
    err = next((l for l in out.splitlines() if l.startswith("EAU_FAIL")), "") or (p.stderr or "")[-200:]
    return {"ok": ok, "info": info, "error": None if ok else err, "output": str(dst)}


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True)
    ap.add_argument("--output", required=True)
    ap.add_argument("--fps", type=int, default=24)
    ap.add_argument("--loop", type=float, default=3.0)
    a = ap.parse_args()
    r = animate_sculpted_water(a.input, a.output, fps=a.fps, loop_s=a.loop)
    print("AURORA_EAU_RESULT:" + json.dumps(r, ensure_ascii=False))
    return 0 if r["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
