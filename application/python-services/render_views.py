import bpy, math, sys, os
from mathutils import Vector

argv = sys.argv[sys.argv.index("--")+1:]
glb, outdir = argv[0], argv[1]
os.makedirs(outdir, exist_ok=True)

# scene propre
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=glb)

# bounding box global des meshes
meshes = [o for o in bpy.data.objects if o.type == 'MESH']
mn = Vector(( 1e9, 1e9, 1e9)); mx = Vector((-1e9,-1e9,-1e9))
for o in meshes:
    for c in o.bound_box:
        w = o.matrix_world @ Vector(c)
        mn = Vector((min(mn[i],w[i]) for i in range(3)))
        mx = Vector((max(mx[i],w[i]) for i in range(3)))
center = (mn+mx)/2
size = (mx-mn); radius = max(size)/2 or 1.0

# monde gris clair (pour voir les couleurs sans fond noir)
world = bpy.data.worlds.new("W"); bpy.context.scene.world = world
world.use_nodes = True
world.node_tree.nodes["Background"].inputs[0].default_value = (0.85,0.85,0.85,1)
world.node_tree.nodes["Background"].inputs[1].default_value = 1.0

# soleil
sun_d = bpy.data.lights.new("Sun", 'SUN'); sun_d.energy = 3.0
sun = bpy.data.objects.new("Sun", sun_d); bpy.context.collection.objects.link(sun)
sun.rotation_euler = (math.radians(55), 0, math.radians(35))

# camera
cam_d = bpy.data.cameras.new("Cam"); cam = bpy.data.objects.new("Cam", cam_d)
bpy.context.collection.objects.link(cam); bpy.context.scene.camera = cam

def look_at(obj, target):
    d = (obj.location - target)
    obj.rotation_euler = d.to_track_quat('Z','Y').to_euler()

# moteur
scene = bpy.context.scene
try: scene.render.engine = 'BLENDER_EEVEE_NEXT'
except Exception: scene.render.engine = 'BLENDER_EEVEE'
scene.render.resolution_x = 1100; scene.render.resolution_y = 1100
scene.render.film_transparent = False
try: scene.eevee.taa_render_samples = 32
except Exception: pass

dist = radius * 3.2
# angles : 3/4 avant, profil, arriere (test doublon), dessus
views = {
  "01_face34": (35, 25),
  "02_profil": (90, 10),
  "03_arriere": (215, 20),
  "04_autre34": (-40, 20),
}
for name,(az,el) in views.items():
    a = math.radians(az); e = math.radians(el)
    cam.location = center + Vector((math.cos(a)*math.cos(e), math.sin(a)*math.cos(e), math.sin(e)))*dist
    look_at(cam, center)
    scene.render.filepath = os.path.join(outdir, f"macaw_{name}.png")
    bpy.ops.render.render(write_still=True)
    print("rendered", name, flush=True)
print("DONE")
