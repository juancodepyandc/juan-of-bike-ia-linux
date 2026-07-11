import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

BLENDER_SCRIPT = r'''
import bpy, sys, math
from mathutils import Vector

argv = sys.argv[sys.argv.index("--") + 1:]
src, dst = argv[0], argv[1]
frames = int(argv[2]) if len(argv) > 2 else 36
resolution = int(argv[3]) if len(argv) > 3 else 64
viscosite = argv[4] if len(argv) > 4 else "fluide"
fps = 24

bpy.ops.wm.read_factory_settings(use_empty=True)
try:
    bpy.context.preferences.edit.keyframe_new_interpolation_type = 'CONSTANT'
except Exception:
    pass
bpy.ops.import_scene.gltf(filepath=src)
sc = bpy.context.scene
sc.frame_start = 1
sc.frame_end = frames
sc.render.fps = fps

meshes = [o for o in sc.objects if o.type == "MESH"]
if not meshes:
    print("SIM_FAIL: pas de mesh")
    sys.exit(2)
socle = max(meshes, key=lambda o: len(o.data.polygons))

mn = Vector((1e9,) * 3)
mx = Vector((-1e9,) * 3)
for c in socle.bound_box:
    w = socle.matrix_world @ Vector(c)
    mn = Vector((min(mn[i], w[i]) for i in range(3)))
    mx = Vector((max(mx[i], w[i]) for i in range(3)))
centre = (mn + mx) / 2
taille = mx - mn
rayon = max(taille) / 2

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

bpy.ops.mesh.primitive_cube_add(location=(centre.x, centre.y, centre.z + taille.z * 0.08))
domaine = bpy.context.active_object
domaine.scale = (taille.x * 0.62, taille.y * 0.62, taille.z * 0.72)
bpy.ops.object.transform_apply(scale=True)
fd = domaine.modifiers.new("fluide", "FLUID")
fd.fluid_type = "DOMAIN"
ds = fd.domain_settings
ds.domain_type = "LIQUID"
ds.resolution_max = resolution
ds.use_mesh = True
ds.mesh_scale = 1
ds.cache_frame_start = 1
ds.cache_frame_end = frames
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
bpy.ops.mesh.primitive_uv_sphere_add(radius=rayon * 0.04, location=(haut.x, haut.y, haut.z - rayon * 0.025))
jet = bpy.context.active_object
fj = jet.modifiers.new("fluide", "FLUID")
fj.fluid_type = "FLOW"
js = fj.flow_settings
js.flow_type = "LIQUID"
js.flow_behavior = "INFLOW"
js.use_initial_velocity = True
js.velocity_coord = (0.0, 0.0, rayon * 0.9)
jet.hide_render = True
jet.display_type = "WIRE"

fe = proxy.modifiers.new("fluide", "FLUID")
fe.fluid_type = "EFFECTOR"
fe.effector_settings.effector_type = "COLLISION"
fe.effector_settings.surface_distance = rayon * 0.004

bpy.context.view_layer.objects.active = domaine
with bpy.context.temp_override(object=domaine, active_object=domaine, selected_objects=[domaine]):
    bpy.ops.fluid.bake_all()
print("SIM_INFO: bake termine", flush=True)

mat_eau = bpy.data.materials.new("AuroraEauSim")
mat_eau.use_nodes = True
bsdf = next(n for n in mat_eau.node_tree.nodes if n.type == "BSDF_PRINCIPLED")
bsdf.inputs["Base Color"].default_value = (0.55, 0.78, 0.86, 1.0)
bsdf.inputs["Roughness"].default_value = 0.03
try:
    bsdf.inputs["Transmission Weight"].default_value = 0.9
except KeyError:
    try:
        bsdf.inputs["Transmission"].default_value = 0.9
    except KeyError:
        pass
try:
    bsdf.inputs["IOR"].default_value = 1.33
except KeyError:
    pass
mat_eau.surface_render_method = "BLENDED" if hasattr(mat_eau, "surface_render_method") else None

dg_frames = []
for f in range(1, frames + 1):
    sc.frame_set(f)
    dg = bpy.context.evaluated_depsgraph_get()
    dom_eval = domaine.evaluated_get(dg)
    me = bpy.data.meshes.new_from_object(dom_eval)
    if len(me.polygons) == 0:
        bpy.data.meshes.remove(me)
        continue
    ob = bpy.data.objects.new("EauSim_%03d" % f, me)
    ob.data.materials.append(mat_eau)
    sc.collection.objects.link(ob)
    dg_frames.append((f, ob))
print("SIM_INFO: %d frames de fluide extraites" % len(dg_frames), flush=True)
if len(dg_frames) < 4:
    print("SIM_FAIL: trop peu de frames fluides")
    sys.exit(3)

for f, ob in dg_frames:
    for probe in (sc.frame_start, f - 1, f, f + 1, sc.frame_end + 1):
        if probe < sc.frame_start:
            continue
        visible = (probe == f)
        ob.scale = (1.0, 1.0, 1.0) if visible else (0.0, 0.0, 0.0)
        ob.keyframe_insert("scale", frame=probe)

for objet in (domaine, jet, proxy):
    bpy.data.objects.remove(objet, do_unlink=True)

bpy.ops.object.select_all(action="SELECT")
bpy.ops.export_scene.gltf(filepath=dst, export_format="GLB",
                          export_animations=True, export_yup=True,
                          export_morph=True, export_force_sampling=False)
print("SIM_OK: %s (%d frames eau)" % (dst, len(dg_frames)))
'''


def bake_fluid_sim(src, dst, frames=36, resolution=64, viscosite="fluide", timeout_s=7200):
    import shutil
    blender = os.environ.get("AURORA_BLENDER") or shutil.which("blender") or "blender"
    with tempfile.NamedTemporaryFile(suffix=".py", delete=False, mode="w", encoding="utf-8") as fp:
        fp.write(BLENDER_SCRIPT)
        script = fp.name
    try:
        p = subprocess.run([blender, "--background", "--python", script, "--",
                            str(src), str(dst), str(frames), str(resolution), viscosite],
                           capture_output=True, text=True, timeout=timeout_s)
    finally:
        try:
            os.unlink(script)
        except OSError:
            pass
    out = p.stdout or ""
    infos = [l for l in out.splitlines() if l.startswith("SIM_INFO")]
    ok = "SIM_OK" in out and Path(dst).is_file() and Path(dst).stat().st_size > 10000
    err = next((l for l in out.splitlines() if l.startswith("SIM_FAIL")), "") or (p.stderr or "")[-300:]
    return {"ok": ok, "info": " | ".join(infos), "error": None if ok else err, "output": str(dst)}


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True)
    ap.add_argument("--output", required=True)
    ap.add_argument("--frames", type=int, default=36)
    ap.add_argument("--resolution", type=int, default=64)
    ap.add_argument("--viscosite", default="fluide")
    a = ap.parse_args()
    r = bake_fluid_sim(a.input, a.output, frames=a.frames, resolution=a.resolution, viscosite=a.viscosite)
    print("AURORA_FLUIDSIM_RESULT:" + json.dumps(r, ensure_ascii=False))
    return 0 if r["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
