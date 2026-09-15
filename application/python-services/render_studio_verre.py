import bpy, sys, math, os
from mathutils import Vector
argv=sys.argv[sys.argv.index("--")+1:]
GLB, OUT = argv[0], argv[1]
AZ = float(argv[2]) if len(argv)>2 else 0.0
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=GLB)

objs=[o for o in bpy.context.scene.objects if o.type=='MESH']
mn=Vector((1e9,)*3); mx=Vector((-1e9,)*3)
for o in objs:
    for c in o.bound_box:
        w=o.matrix_world @ Vector(c)
        mn=Vector((min(mn[i],w[i]) for i in range(3))); mx=Vector((max(mx[i],w[i]) for i in range(3)))
ctr=(mn+mx)/2; size=max((mx-mn))

# monde: gris clair uniforme (le verre a besoin d'un environnement a traverser)
w=bpy.data.worlds.new("W"); bpy.context.scene.world=w; w.use_nodes=True
bg=w.node_tree.nodes["Background"]; bg.inputs[0].default_value=(0.62,0.63,0.66,1); bg.inputs[1].default_value=1.0

def aire(loc,rot,taille,energie):
    d=bpy.data.lights.new("L",type='AREA'); d.size=taille; d.energy=energie
    o=bpy.data.objects.new("L",d); o.location=loc; o.rotation_euler=rot
    bpy.context.collection.objects.link(o)
aire((size*1.6,size*1.1,size*1.5),(math.radians(52),0,math.radians(52)),size*2.2,size*size*900)
aire((-size*1.7,size*0.5,size*1.0),(math.radians(64),0,math.radians(-58)),size*2.0,size*size*450)
aire((0,size*0.2,-size*2.0),(math.radians(-90),0,0),size*2.5,size*size*300)

cam=bpy.data.cameras.new("C"); cam.lens=85
co=bpy.data.objects.new("C",cam); bpy.context.collection.objects.link(co)
bpy.context.scene.camera=co
dist=size*3.1
import math as _m
_a=_m.radians(AZ)
co.location=(ctr.x+dist*_m.sin(_a), ctr.y-dist*_m.cos(_a), ctr.z+size*0.06)
co.rotation_euler=(_m.radians(90),0,_a)

sc=bpy.context.scene
sc.render.engine='CYCLES'
try:
    prefs=bpy.context.preferences.addons['cycles'].preferences
    prefs.compute_device_type='CUDA'; prefs.get_devices()
    for d in prefs.devices: d.use=True
    sc.cycles.device='GPU'
except Exception as e: print("GPU indispo:",e)
sc.cycles.samples=64
sc.cycles.use_denoising=True
sc.cycles.transmission_bounces=24
sc.cycles.max_bounces=24
sc.cycles.blur_glossy=0.5
sc.render.resolution_x=900; sc.render.resolution_y=900
sc.render.film_transparent=False
sc.view_settings.view_transform='Filmic' if 'Filmic' in [v.name for v in sc.view_settings.bl_rna.properties['view_transform'].enum_items] else 'Standard'
sc.render.filepath=OUT
bpy.ops.render.render(write_still=True)
print("RENDU:",OUT)
