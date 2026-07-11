import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

BLENDER_SCRIPT = r'''
import bpy, math, sys, os
from mathutils import Vector
argv = sys.argv[sys.argv.index("--")+1:]
glb, outdir = argv[0], argv[1]
frames = [int(x) for x in (argv[2].split(",") if len(argv) > 2 else ["1", "12", "24"])]
os.makedirs(outdir, exist_ok=True)
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=glb)
sc = bpy.context.scene
meshes = [o for o in bpy.data.objects if o.type == 'MESH']
mn = Vector((1e9,)*3); mx = Vector((-1e9,)*3)
for o in meshes:
    for c in o.bound_box:
        w = o.matrix_world @ Vector(c)
        mn = Vector((min(mn[i], w[i]) for i in range(3)))
        mx = Vector((max(mx[i], w[i]) for i in range(3)))
center = (mn+mx)/2; radius = max(mx-mn)/2 or 1.0
world = bpy.data.worlds.new("W"); sc.world = world
world.use_nodes = True
world.node_tree.nodes["Background"].inputs[0].default_value = (0.82, 0.82, 0.82, 1)
sun_d = bpy.data.lights.new("Sun", 'SUN'); sun_d.energy = 3.0
sun = bpy.data.objects.new("Sun", sun_d); sc.collection.objects.link(sun)
sun.rotation_euler = (math.radians(55), 0, math.radians(35))
cam_d = bpy.data.cameras.new("Cam"); cam = bpy.data.objects.new("Cam", cam_d)
sc.collection.objects.link(cam); sc.camera = cam
a = math.radians(35); e = math.radians(22)
cam.location = center + Vector((math.cos(a)*math.cos(e), math.sin(a)*math.cos(e), math.sin(e))) * radius * 3.1
d = cam.location - center
cam.rotation_euler = d.to_track_quat('Z', 'Y').to_euler()
try: sc.render.engine = 'BLENDER_EEVEE_NEXT'
except Exception: sc.render.engine = 'BLENDER_EEVEE'
sc.render.resolution_x = 720; sc.render.resolution_y = 720
for f in frames:
    sc.frame_set(f)
    sc.render.filepath = os.path.join(outdir, "sonde_%03d.png" % f)
    bpy.ops.render.render(write_still=True)
    print("SONDE_FRAME", f, flush=True)
print("SONDE_OK")
'''


def probe_frames(glb, outdir, frames=(1, 9, 17), timeout_s=900):
    import shutil
    blender = os.environ.get("AURORA_BLENDER") or shutil.which("blender") or "blender"
    with tempfile.NamedTemporaryFile(suffix=".py", delete=False, mode="w", encoding="utf-8") as fp:
        fp.write(BLENDER_SCRIPT)
        script = fp.name
    try:
        p = subprocess.run([blender, "--background", "--python", script, "--",
                            str(glb), str(outdir), ",".join(str(f) for f in frames)],
                           capture_output=True, text=True, timeout=timeout_s)
    finally:
        try:
            os.unlink(script)
        except OSError:
            pass
    ok = "SONDE_OK" in (p.stdout or "")
    imgs = sorted(str(f) for f in Path(outdir).glob("sonde_*.png"))
    return {"ok": ok and len(imgs) >= 2, "frames": imgs}


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--glb", required=True)
    ap.add_argument("--outdir", required=True)
    ap.add_argument("--frames", default="1,9,17")
    a = ap.parse_args()
    r = probe_frames(a.glb, a.outdir, [int(x) for x in a.frames.split(",")])
    print("AURORA_SONDE_RESULT:" + json.dumps(r, ensure_ascii=False))
    return 0 if r["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
