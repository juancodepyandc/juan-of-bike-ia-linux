import bpy, sys, os, math
argv = sys.argv[sys.argv.index("--")+1:]
char_glb = argv[0]; out_dir = argv[1]; effect = argv[2] if len(argv)>2 else "fire"
bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene
# 1) le personnage anime
bpy.ops.import_scene.gltf(filepath=char_glb)

# GARDE ALPHA: TRELLIS encode les cheveux en semi-transparent (alpha ~69 sur
# la tete du guerrier, mesure) mais exporte OPAQUE. Cycles honore l'entree
# Alpha du Principled -> la chevelure entiere disparaitrait au rendu. On force
# l'opacite sur tous les materiaux importes.
for _m in bpy.data.materials:
    if not _m.use_nodes:
        continue
    for _n in _m.node_tree.nodes:
        if _n.type == "BSDF_PRINCIPLED" and "Alpha" in _n.inputs:
            for _lk in list(_n.inputs["Alpha"].links):
                _m.node_tree.links.remove(_lk)
            _n.inputs["Alpha"].default_value = 1.0
    try:
        _m.blend_method = "OPAQUE"
    except Exception:
        pass

meshes=[o for o in bpy.data.objects if o.type=="MESH"]
if not meshes:
    print("COMPOSE_FAIL pas de mesh"); sys.exit(2)
subj=max(meshes,key=lambda o:len(o.data.polygons))
# etendue temporelle depuis les actions importees
fend=2
for a in bpy.data.actions:
    if a.frame_range: fend=max(fend,int(a.frame_range[1]))
fend=min(fend,24)
sc.frame_start,sc.frame_end=1,fend
cx,cy,cz=subj.location; size=max(subj.dimensions.x,subj.dimensions.y,subj.dimensions.z,0.3)
# 2) le volume de feu, colle au sujet
# "avec une flamme": foyer localise a cote du sujet (pas englobant), decale
# pour que le personnage reste visible. "en feu" (engulf) serait size*1.6.
engulf = effect.endswith("_engulf")
if engulf:
    bpy.ops.mesh.primitive_cube_add(size=size*1.7, location=(cx,cy,cz+size*0.5))
    dom=bpy.context.object; dom.scale=(0.7,0.7,1.25)
else:
    bpy.ops.mesh.primitive_cube_add(size=size*0.9, location=(cx+size*0.8,cy,cz+size*0.6))
    dom=bpy.context.object; dom.scale=(0.6,0.6,1.1)
dom.name="Feu"
vm=bpy.data.materials.new("F"); vm.use_nodes=True; nt=vm.node_tree
for n in list(nt.nodes):
    if n.type!="OUTPUT_MATERIAL": nt.nodes.remove(n)
o=next(n for n in nt.nodes if n.type=="OUTPUT_MATERIAL")
co=nt.nodes.new("ShaderNodeTexCoord"); mp=nt.nodes.new("ShaderNodeMapping")
no=nt.nodes.new("ShaderNodeTexNoise"); no.inputs["Scale"].default_value=4.0; no.inputs["Detail"].default_value=6.0
m1=nt.nodes.new("ShaderNodeMath"); m1.operation="MULTIPLY"; m1.inputs[1].default_value=25
m2=nt.nodes.new("ShaderNodeMath"); m2.operation="SUBTRACT"; m2.inputs[1].default_value=7
m3=nt.nodes.new("ShaderNodeMath"); m3.operation="MAXIMUM"; m3.inputs[1].default_value=0
pv=nt.nodes.new("ShaderNodeVolumePrincipled"); pv.inputs["Color"].default_value=(0.05,0.05,0.05,1)
pv.inputs["Temperature"].default_value=1600; pv.inputs["Blackbody Intensity"].default_value=4
nt.links.new(co.outputs["Generated"],mp.inputs["Vector"]); nt.links.new(mp.outputs["Vector"],no.inputs["Vector"])
nt.links.new(no.outputs["Fac"],m1.inputs[0]); nt.links.new(m1.outputs[0],m2.inputs[0])
nt.links.new(m2.outputs[0],m3.inputs[0]); nt.links.new(m3.outputs[0],pv.inputs["Density"])
nt.links.new(pv.outputs["Volume"],o.inputs["Volume"]); dom.data.materials.append(vm)
for fr in range(1,fend+1):
    t=(fr-1)/max(fend-1,1); mp.inputs["Location"].default_value=(0,0,-t*3)
    mp.inputs["Location"].keyframe_insert("default_value",frame=fr)
# 3) camera + lumiere + rendu
sc.render.engine="CYCLES"
try:
    pr=bpy.context.preferences.addons["cycles"].preferences; pr.compute_device_type="CUDA"; pr.get_devices()
    for d in pr.devices: d.use=(d.type!="CPU")
    sc.cycles.device="GPU"
except Exception: sc.cycles.device="CPU"
sc.cycles.samples=24; sc.render.resolution_x=sc.render.resolution_y=420
if sc.world is None: sc.world=bpy.data.worlds.new("W")
sc.world.use_nodes=True
bg=next(n for n in sc.world.node_tree.nodes if n.type=="BACKGROUND")
bg.inputs[0].default_value=(0.03,0.03,0.04,1); bg.inputs[1].default_value=0.4
d=size*4
bpy.ops.object.camera_add(location=(cx+d,cy-d,cz+d*0.5)); cam=bpy.context.object
dir=math.atan2(d,d); cam.rotation_euler=(1.15,0,0.785); sc.camera=cam
bpy.ops.object.light_add(type="AREA",location=(cx+2,cy-2,cz+3)); bpy.context.object.data.energy=600
os.makedirs(out_dir,exist_ok=True)
for fr in range(1,fend+1):
    sc.frame_set(fr); sc.render.filepath=os.path.join(out_dir,"c%03d.png"%fr)
    bpy.ops.render.render(write_still=True)
print("COMPOSE_OK %d images"%fend)
