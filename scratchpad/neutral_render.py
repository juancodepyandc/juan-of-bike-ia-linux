"""Neutral PBR studio render in Blender Cycles.

Renders a GLB under a soft studio lighting rig (3 area lights + neutral world),
Filmic-off (Standard view transform) so we judge the *material* not a tonemap.
This is renderer-agnostic ground truth to compare against the three.js viewer.

Usage: blender -b -P neutral_render.py -- IN.glb OUTDIR LABEL [az]
"""
import sys, os, math
import bpy
from mathutils import Vector

argv = sys.argv[sys.argv.index("--")+1:] if "--" in sys.argv else []
IN, OUTDIR, LABEL = argv[0], argv[1], argv[2]
os.makedirs(OUTDIR, exist_ok=True)

bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene
sc.render.engine = "CYCLES"
try: sc.cycles.device = "CPU"
except Exception: pass
sc.cycles.samples = 96
sc.render.resolution_x = 1000
sc.render.resolution_y = 1000
sc.render.film_transparent = False
# Standard view transform => no ACES/Filmic; judge raw material response.
sc.view_settings.view_transform = "Standard"
sc.view_settings.look = "None"
sc.view_settings.exposure = 0.0
sc.view_settings.gamma = 1.0

# neutral grey world, mild ambient so it is not a black void
world = bpy.data.worlds.new("W"); sc.world = world
world.use_nodes = True
bg = world.node_tree.nodes["Background"]
bg.inputs[0].default_value = (0.18, 0.18, 0.18, 1.0)
bg.inputs[1].default_value = 0.6

bpy.ops.import_scene.gltf(filepath=IN)

# gather imported meshes, compute bounds
meshes = [o for o in bpy.data.objects if o.type == "MESH"]
mins = Vector((1e9,1e9,1e9)); maxs = Vector((-1e9,-1e9,-1e9))
for o in meshes:
    for c in o.bound_box:
        w = o.matrix_world @ Vector(c)
        for i in range(3):
            mins[i]=min(mins[i],w[i]); maxs[i]=max(maxs[i],w[i])
ctr = (mins+maxs)/2.0
size = maxs-mins
rad = max(size.x,size.y,size.z)*0.5 or 1.0

# soft studio: 3 area lights (key/fill/rim), broad -> soft shadows
def area(name, loc, energy, sizeL):
    ld = bpy.data.lights.new(name, "AREA"); ld.energy=energy; ld.size=sizeL
    ob = bpy.data.objects.new(name, ld); bpy.context.collection.objects.link(ob)
    ob.location = loc
    d = (ctr-Vector(loc)); ob.rotation_euler = d.to_track_quat('-Z','Y').to_euler()
    return ob
D = rad*4.0
area("key",  (ctr.x+D*0.7, ctr.y-D*0.5, ctr.z+D*0.8), 1200*rad*rad, rad*3)
area("fill", (ctr.x-D*0.9, ctr.y-D*0.3, ctr.z+D*0.2), 500*rad*rad,  rad*4)
area("rim",  (ctr.x, ctr.y+D*1.0, ctr.z+D*0.9),        800*rad*rad, rad*2.5)

# camera az=35 el=12 like the viewer default
az=math.radians(35); el=math.radians(12); dist=rad*4.6
cam_d = bpy.data.cameras.new("cam"); cam_d.lens=45
cam = bpy.data.objects.new("cam", cam_d); bpy.context.collection.objects.link(cam)
cam.location = (ctr.x+math.sin(az)*math.cos(el)*dist, ctr.y-math.cos(az)*math.cos(el)*dist, ctr.z+math.sin(el)*dist+size.z*0.05)
cam.rotation_euler = (ctr-cam.location).to_track_quat('-Z','Y').to_euler()
sc.camera = cam

sc.render.image_settings.file_format="PNG"
out = os.path.join(OUTDIR, LABEL+"_neutral.png")
sc.render.filepath = out
bpy.ops.render.render(write_still=True)
print("NEUTRAL_RENDER_OK", out, flush=True)
