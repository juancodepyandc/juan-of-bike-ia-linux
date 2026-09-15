import bpy
import math
import os
import sys
from mathutils import Vector

argv = sys.argv[sys.argv.index("--") + 1:]
GLB, OUT = argv[0], argv[1]
os.makedirs(OUT, exist_ok=True)

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=GLB)
sc = bpy.context.scene

# Force opaque
for _m in bpy.data.materials:
    try:
        _m.blend_method = "OPAQUE"
        if _m.use_nodes:
            for _n in _m.node_tree.nodes:
                if _n.type == "BSDF_PRINCIPLED":
                    _inp = _n.inputs.get("Alpha")
                    if _inp is not None:
                        for _l in list(_inp.links):
                            _m.node_tree.links.remove(_l)
                        _inp.default_value = 1.0
    except Exception:
        pass

mn = Vector((1e9,) * 3)
mx = Vector((-1e9,) * 3)
for o in sc.objects:
    if o.type != "MESH":
        continue
    for c in o.bound_box:
        w = o.matrix_world @ Vector(c)
        mn = Vector(map(min, mn, w))
        mx = Vector(map(max, mx, w))

center = (mn + mx) / 2
# Focus on head area
head_center = center.copy()
head_center.z += (mx.z - mn.z) * 0.12
size_z = mx.z - mn.z

cam_data = bpy.data.cameras.new("cam_hd")
cam_data.lens = 85.0  # 85mm portrait focal length (natural perspective, zero fisheye distortion)
cam = bpy.data.objects.new("cam_hd", cam_data)
sc.collection.objects.link(cam)
sc.camera = cam

sc.render.engine = "CYCLES"
sc.cycles.device = "CPU"
sc.cycles.samples = 64
sc.cycles.use_denoising = True
sc.render.resolution_x = sc.render.resolution_y = 1200

w = bpy.data.worlds.new("w_hd")
w.use_nodes = True
w.node_tree.nodes["Background"].inputs[1].default_value = 1.5
sc.world = w
try:
    sc.view_settings.view_transform = "Standard"
    sc.view_settings.look = "None"
except Exception:
    pass

# Studio lighting setup (Key light, Fill light, Rim light)
key_light = bpy.data.objects.new("key_sun", bpy.data.lights.new("key_sun", "SUN"))
key_light.data.energy = 3.0
sc.collection.objects.link(key_light)

# Portrait distance for 85mm lens to frame head nicely
dist = size_z * 2.6

# 4 portrait angles
for az in (270, 315, 0, 90, 180, 225):
    a = math.radians(az)
    # Slight eye-level angle
    cam.location = head_center + Vector((math.cos(a), math.sin(a), 0.05)) * dist
    d = head_center - cam.location
    cam.rotation_euler = d.to_track_quat("-Z", "Y").to_euler()
    key_light.rotation_euler = cam.rotation_euler
    
    out_path = os.path.join(OUT, f"portrait_az{az:03d}.png")
    sc.render.filepath = out_path
    bpy.ops.render.render(write_still=True)
    print(f"Rendered {out_path}")

print("PORTRAIT_HD_OK")
