# Blender headless: 4 vues azimut (0/90/180/270) du GLB, geometrie de camera
# identique a motion_clay_render (la planche que l'on juge). Usage:
#   blender -b -P orient_rendu_bpy.py -- <glb> <dossier_sortie>
import math
import os
import sys

import bpy
from mathutils import Vector

argv = sys.argv[sys.argv.index("--") + 1:]
GLB, OUT = argv[0], argv[1]
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=GLB)
sc = bpy.context.scene
# GARDE ALPHA (deja payee ailleurs dans le projet): l'alpha de l'atlas relie
# au Principled rend la MAJORITE des faces transparentes sous Cycles — le
# Pikachu entier apparaissait comme des fragments epars. Le juge force
# l'opacite: il evalue la matiere, pas les trous d'alpha.
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
    except Exception:  # noqa: BLE001
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
radius = max((mx - mn).length / 2, 0.1)
cam = bpy.data.objects.new("cam", bpy.data.cameras.new("cam"))
sc.collection.objects.link(cam)
sc.camera = cam
# CYCLES CPU: EEVEE headless rend NOIR depuis le driver 595.84 (lampe
# ignoree, luminance ~5/255 — verifie sur bon modele) et Workbench segfault.
# Cycles CPU ne depend pas du GPU: lent mais toujours juste — et le juge
# doit etre incassable.
sc.render.engine = "CYCLES"
sc.cycles.device = "CPU"
sc.cycles.samples = 24
sc.cycles.use_denoising = False
w = bpy.data.worlds.new("w")
w.use_nodes = True
# EXPOSITION (27/07): a 0.8 d'eclairage d'ambiance ET avec la transformee
# filmique par defaut, le rendu de controle sortait a ~50/255 de luminance
# alors que l'atlas mesure un jaune parfait ([218 185 35]). Un juge
# sous-expose REFUSE tout a tort — deja paye en verdicts "trop sombre".
# Ambiance forte + transformee STANDARD = on juge la matiere, pas le film.
w.node_tree.nodes["Background"].inputs[1].default_value = 3.0
sc.world = w
try:
    sc.view_settings.view_transform = "Standard"
    sc.view_settings.look = "None"
except Exception:  # noqa: BLE001
    pass
sc.render.resolution_x = sc.render.resolution_y = 640
lum = bpy.data.objects.new("sun", bpy.data.lights.new("sun", "SUN"))
lum.data.energy = 4.0
sc.collection.objects.link(lum)
dist = radius * 3.0
for i, az in enumerate((270, 0, 90, 180)):
    a = math.radians(az)
    cam.location = center + Vector((math.cos(a), math.sin(a), 0.35)) * dist
    d = center - cam.location
    cam.rotation_euler = d.to_track_quat("-Z", "Y").to_euler()
    # la lampe SUIT la camera: un soleil fixe laissait 2 vues dans le noir et
    # le VLM choisissait la vue bien eclairee (le dos) comme "face"
    lum.rotation_euler = cam.rotation_euler
    sc.render.filepath = os.path.join(OUT, "az%03d.png" % az)
    bpy.ops.render.render(write_still=True)
print("VUES4_OK")
