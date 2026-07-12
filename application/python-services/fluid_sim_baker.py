import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

BLENDER_SCRIPT = r'''
import bpy, sys, math, os
from mathutils import Vector

argv = sys.argv[sys.argv.index("--") + 1:]
src, dst = argv[0], argv[1]
frames = int(argv[2]) if len(argv) > 2 else 36
resolution = int(argv[3]) if len(argv) > 3 else 64
viscosite = argv[4] if len(argv) > 4 else "fluide"
debit = float(argv[5]) if len(argv) > 5 else 1.6
cache_dir = argv[6] if len(argv) > 6 else ""
fps = 24
prelude = max(24, int(frames * 1.5))

bpy.ops.wm.read_factory_settings(use_empty=True)
try:
    bpy.context.preferences.edit.keyframe_new_interpolation_type = 'CONSTANT'
except Exception:
    pass
bpy.ops.import_scene.gltf(filepath=src)
sc = bpy.context.scene
sc.frame_start = 1
sc.frame_end = frames + prelude
sc.render.fps = fps

meshes = [o for o in sc.objects if o.type == "MESH"]
if not meshes:
    print("SIM_FAIL: pas de mesh")
    sys.exit(2)
socle = max(meshes, key=lambda o: len(o.data.polygons))

if socle.data.shape_keys:
    bpy.context.view_layer.objects.active = socle
    socle.shape_key_clear()
if socle.animation_data:
    socle.animation_data_clear()
print("SIM_INFO: socle fige (morphs sculptes retires — tout le mouvement vient de la sim)", flush=True)

mn = Vector((1e9,) * 3)
mx = Vector((-1e9,) * 3)
for c in socle.bound_box:
    w = socle.matrix_world @ Vector(c)
    mn = Vector((min(mn[i], w[i]) for i in range(3)))
    mx = Vector((max(mx[i], w[i]) for i in range(3)))
centre = (mn + mx) / 2
taille = mx - mn
rayon = max(taille) / 2


img_socle = None
for mat in socle.data.materials:
    if not mat or not mat.use_nodes:
        continue
    for n in mat.node_tree.nodes:
        if n.type == "TEX_IMAGE" and n.image is not None and "normal" not in (n.image.name or "").lower():
            img_socle = n.image
            break
    if img_socle:
        break
if img_socle is not None and socle.data.uv_layers.active:
    import numpy as np
    me_s = socle.data
    w0, h0 = img_socle.size
    px0 = np.empty(w0 * h0 * 4, dtype=np.float32)
    img_socle.pixels.foreach_get(px0)
    px0 = px0.reshape(h0, w0, 4)
    nv = len(me_s.vertices)
    uvd = me_s.uv_layers.active.data
    uvs0 = np.empty(len(uvd) * 2, dtype=np.float32)
    uvd.foreach_get("uv", uvs0)
    uvs0 = uvs0.reshape(-1, 2)
    lv0 = np.empty(len(me_s.loops), dtype=np.int32)
    me_s.loops.foreach_get("vertex_index", lv0)
    xi0 = np.clip((uvs0[:, 0] % 1.0) * (w0 - 1), 0, w0 - 1).astype(np.int32)
    yi0 = np.clip((uvs0[:, 1] % 1.0) * (h0 - 1), 0, h0 - 1).astype(np.int32)
    cols0 = px0[yi0, xi0, :3]
    srgb = np.zeros((nv, 3), dtype=np.float64)
    cnt0 = np.zeros(nv, dtype=np.int32)
    np.add.at(srgb, lv0, cols0)
    np.add.at(cnt0, lv0, 1)
    rgb0 = srgb / np.maximum(cnt0, 1)[:, None]
    b0 = rgb0[:, 2]
    eau_v = (b0 > rgb0[:, 0] * 1.12) & (b0 > rgb0[:, 1] * 1.02)
    nr0 = np.empty(nv * 3, dtype=np.float64)
    me_s.vertices.foreach_get("normal", nr0)
    nr0 = nr0.reshape(-1, 3)
    raide = np.abs(nr0[:, 2]) < 0.55

    a_virer = eau_v & raide
    if a_virer.sum() > 100:
        import bmesh
        bm = bmesh.new()
        bm.from_mesh(me_s)
        bm.verts.ensure_lookup_table()
        cible = [f for f in bm.faces if all(a_virer[v.index] for v in f.verts)]
        bmesh.ops.delete(bm, geom=cible, context="FACES")
        bm.to_mesh(me_s)
        bm.free()
        print("SIM_INFO: %d faces d'eau figee purgees" % len(cible), flush=True)

proxy = socle.copy()
proxy.data = socle.data.copy()
sc.collection.objects.link(proxy)
if proxy.data.shape_keys:
    bpy.context.view_layer.objects.active = proxy
    proxy.shape_key_clear()
if proxy.animation_data:
    proxy.animation_data_clear()
dec = proxy.modifiers.new("dec", "DECIMATE")
dec.ratio = min(1.0, 120000.0 / max(len(proxy.data.polygons), 1))
bpy.context.view_layer.objects.active = proxy
bpy.ops.object.modifier_apply(modifier=dec.name)
proxy.hide_render = True

# Domaine SNUG (le cube Blender fait +-1 => scale S donne 2S de large). 0.58 => 116%
# d'emprise: enveloppe la fontaine avec une petite marge, l'eau est retenue par la
# PIERRE reelle. Plancher POSE au niveau de la base (mn.z) pour que l'eau debordante
# soit retiree des qu'elle atteint le bassin bas, sans longue chute sous la base
# (l'ancien domaine descendait 0.3 SOUS la fontaine -> gouttes visibles sous le socle).
# Hauteur = 1.16*taille.z: reste de la marge en haut pour le panache du jet.
_dom_loc_z = centre.z + taille.z * 0.18
bpy.ops.mesh.primitive_cube_add(location=(centre.x, centre.y, _dom_loc_z))
domaine = bpy.context.active_object
domaine.scale = (taille.x * 0.58, taille.y * 0.58, taille.z * 0.72)
bpy.ops.object.transform_apply(scale=True)
fd = domaine.modifiers.new("fluide", "FLUID")
fd.fluid_type = "DOMAIN"
ds = fd.domain_settings
ds.domain_type = "LIQUID"
ds.resolution_max = resolution
ds.use_mesh = True
ds.mesh_scale = 1
try:
    ds.mesh_particle_radius = 1.05
except AttributeError:
    pass
ds.cache_frame_start = 1
ds.cache_frame_end = frames + prelude
ds.cache_type = "ALL"
if cache_dir:
    ds.cache_directory = cache_dir
ds.use_adaptive_timesteps = True
if viscosite == "epais":
    ds.use_viscosity = True
    ds.viscosity_value = 0.05

haut = None
zmax = -1e9
for v in socle.data.vertices:
    w = socle.matrix_world @ v.co
    if w.z > zmax and (Vector((w.x, w.y)) - Vector((centre.x, centre.y))).length < rayon * 0.25:
        zmax = w.z
        haut = w
if haut is None:
    haut = Vector((centre.x, centre.y, mx.z))
cellule = max(domaine.dimensions) / resolution
ray_jet = max(rayon * 0.030, cellule * 2.3)
g = abs(sc.gravity[2]) or 9.81
apex = taille.z * 0.20 * debit
v_jet = math.sqrt(2.0 * g * apex)
print("SIM_INFO: taille=(%.2f,%.2f,%.2f) cellule=%.4f ray_jet=%.4f v_jet=%.2f apex=%.2f"
      % (taille.x, taille.y, taille.z, cellule, ray_jet, v_jet, apex), flush=True)
bpy.ops.mesh.primitive_uv_sphere_add(radius=ray_jet, location=(haut.x, haut.y, haut.z - ray_jet * 0.55))
jet = bpy.context.active_object
fj = jet.modifiers.new("fluide", "FLUID")
fj.fluid_type = "FLOW"
js = fj.flow_settings
js.flow_type = "LIQUID"
js.flow_behavior = "INFLOW"
js.use_initial_velocity = True
js.velocity_coord = (0.0, 0.0, v_jet)
js.subframes = 2
jet.hide_render = True
jet.display_type = "WIRE"

fe = proxy.modifiers.new("fluide", "FLUID")
fe.fluid_type = "EFFECTOR"
fe.effector_settings.effector_type = "COLLISION"
fe.effector_settings.surface_distance = rayon * 0.004

# Exutoire = drainage type "pompe de recirculation". Placé au niveau de la surface
# du BASSIN LE PLUS BAS : toute eau qui redescend jusque-là est retirée, donc le
# bassin bas ne déborde jamais et rien ne cascade sur la pierre extérieure ni ne
# goutte sous la base. Niveau détecté depuis les faces d'eau plates du mesh sculpté.
niveau_drain = mn.z + taille.z * 0.16
try:
    import numpy as _np2
    _me = socle.data
    _nrz = _np2.empty(len(_me.vertices) * 3, dtype=_np2.float64)
    _me.vertices.foreach_get("normal", _nrz)
    _nrz = _nrz.reshape(-1, 3)
    _co = _np2.empty(len(_me.vertices) * 3, dtype=_np2.float64)
    _me.vertices.foreach_get("co", _co)
    _co = _co.reshape(-1, 3)[:, 2] + socle.matrix_world.translation.z
    _plats = _co[_nrz[:, 2] > 0.80]
    if _plats.size > 200:
        niveau_drain = float(_np2.percentile(_plats, 12)) + taille.z * 0.02
except Exception as _e_drain:
    print("SIM_INFO: niveau drain par defaut (%r)" % _e_drain, flush=True)
bas_dom = domaine.location.z - domaine.dimensions.z / 2.0
ep_sortie = max(niveau_drain - bas_dom, max(taille) * 6.0 / resolution)
bpy.ops.mesh.primitive_cube_add(location=(centre.x, centre.y, bas_dom + ep_sortie / 2.0))
sortie = bpy.context.active_object
sortie.scale = (taille.x * 0.60, taille.y * 0.60, ep_sortie / 2.0)
bpy.ops.object.transform_apply(scale=True)
fo = sortie.modifiers.new("fluide", "FLUID")
fo.fluid_type = "FLOW"
ofs = fo.flow_settings
ofs.flow_type = "LIQUID"
ofs.flow_behavior = "OUTFLOW"
sortie.hide_render = True
sortie.display_type = "WIRE"
print("SIM_INFO: exutoire jusqu'a z=%.4f (bassin bas)" % (bas_dom + ep_sortie), flush=True)

bpy.context.view_layer.objects.active = domaine
with bpy.context.temp_override(object=domaine, active_object=domaine, selected_objects=[domaine]):
    _ret = bpy.ops.fluid.bake_all()
print("SIM_INFO: bake_all -> %s" % _ret, flush=True)
import time as _t
import glob as _g
_attendu = int((frames + prelude) * 0.8)
_deadline = _t.time() + 2400
_n_mesh = 0
_stalle = 0
while _t.time() < _deadline:
    _avant = _n_mesh
    _n_mesh = len(_g.glob(os.path.join(bpy.path.abspath(ds.cache_directory), "mesh", "*.bobj.gz")))
    if _n_mesh >= _attendu:
        break
    _stalle = _stalle + 1 if _n_mesh == _avant else 0
    if _stalle >= 9:
        break
    _t.sleep(10)
print("SIM_INFO: bake termine (%d fichiers mesh en cache)" % _n_mesh, flush=True)
if _n_mesh < 4:
    print("SIM_FAIL: cache fluide vide apres attente")
    sys.exit(4)

mat_eau = bpy.data.materials.new("AuroraEauSim")
mat_eau.use_nodes = True
bsdf = next(n for n in mat_eau.node_tree.nodes if n.type == "BSDF_PRINCIPLED")
bsdf.inputs["Base Color"].default_value = (0.42, 0.68, 0.78, 1.0)
bsdf.inputs["Roughness"].default_value = 0.02
try:
    bsdf.inputs["Transmission Weight"].default_value = 0.95
except KeyError:
    try:
        bsdf.inputs["Transmission"].default_value = 0.95
    except KeyError:
        pass
try:
    bsdf.inputs["IOR"].default_value = 1.33
except KeyError:
    pass
mat_eau.surface_render_method = "BLENDED" if hasattr(mat_eau, "surface_render_method") else None

dg_frames = []
for f in range(prelude + 1, prelude + frames + 1):
    sc.frame_set(f)
    dg = bpy.context.evaluated_depsgraph_get()
    dom_eval = domaine.evaluated_get(dg)
    me = bpy.data.meshes.new_from_object(dom_eval)
    if len(me.polygons) < 50:
        bpy.data.meshes.remove(me)
        continue
    me.polygons.foreach_set("use_smooth", [True] * len(me.polygons))
    ob = bpy.data.objects.new("EauSim_%03d" % f, me)
    ob.data.materials.append(mat_eau)
    sc.collection.objects.link(ob)
    if len(me.polygons) > 40000:
        dm = ob.modifiers.new("dec", "DECIMATE")
        dm.ratio = 0.55
        bpy.context.view_layer.objects.active = ob
        bpy.ops.object.modifier_apply(modifier=dm.name)
    dg_frames.append((f - prelude, ob))
print("SIM_INFO: %d frames de fluide extraites (prechauffe de %d frames jetee)" % (len(dg_frames), prelude), flush=True)
if len(dg_frames) < 4:
    print("SIM_FAIL: trop peu de frames fluides")
    sys.exit(3)
sc.frame_end = frames

for f, ob in dg_frames:
    for probe in (sc.frame_start, f - 1, f, f + 1, sc.frame_end + 1):
        if probe < sc.frame_start:
            continue
        visible = (probe == f)
        ob.scale = (1.0, 1.0, 1.0) if visible else (0.0, 0.0, 0.0)
        ob.keyframe_insert("scale", frame=probe)

for objet in (domaine, jet, proxy, sortie):
    bpy.data.objects.remove(objet, do_unlink=True)

bpy.ops.object.select_all(action="SELECT")
bpy.ops.export_scene.gltf(filepath=dst, export_format="GLB",
                          export_animations=True, export_yup=True,
                          export_morph=True, export_force_sampling=True)
print("SIM_OK: %s (%d frames eau)" % (dst, len(dg_frames)))
'''


def bake_fluid_sim(src, dst, frames=48, resolution=128, viscosite="fluide", debit=1.6, timeout_s=7200):
    import shutil
    blender = os.environ.get("AURORA_BLENDER") or shutil.which("blender") or "blender"
    with tempfile.NamedTemporaryFile(suffix=".py", delete=False, mode="w", encoding="utf-8") as fp:
        fp.write(BLENDER_SCRIPT)
        script = fp.name
    cache_dir = tempfile.mkdtemp(prefix="aurora_flip_")
    try:
        p = subprocess.run([blender, "--background", "--python", script, "--",
                            str(src), str(dst), str(frames), str(resolution), viscosite,
                            str(debit), cache_dir],
                           capture_output=True, text=True, timeout=timeout_s)
    finally:
        try:
            os.unlink(script)
        except OSError:
            pass
        import shutil as _sh2
        _sh2.rmtree(cache_dir, ignore_errors=True)
    out = p.stdout or ""
    infos = [l for l in out.splitlines() if l.startswith("SIM_INFO")]
    ok = "SIM_OK" in out and Path(dst).is_file() and Path(dst).stat().st_size > 10000
    if not ok:
        infos.append("TAIL_STDOUT: " + out[-1200:].replace("\n", " | "))
        infos.append("TAIL_STDERR: " + (p.stderr or "")[-600:].replace("\n", " | "))
    err = next((l for l in out.splitlines() if l.startswith("SIM_FAIL")), "") or (p.stderr or "")[-300:]
    return {"ok": ok, "info": " | ".join(infos), "error": None if ok else err, "output": str(dst)}


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True)
    ap.add_argument("--output", required=True)
    ap.add_argument("--frames", type=int, default=48)
    ap.add_argument("--resolution", type=int, default=128)
    ap.add_argument("--viscosite", default="fluide")
    ap.add_argument("--debit", type=float, default=1.6)
    a = ap.parse_args()
    r = bake_fluid_sim(a.input, a.output, frames=a.frames, resolution=a.resolution,
                       viscosite=a.viscosite, debit=a.debit)
    print("AURORA_FLUIDSIM_RESULT:" + json.dumps(r, ensure_ascii=False))
    return 0 if r["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
