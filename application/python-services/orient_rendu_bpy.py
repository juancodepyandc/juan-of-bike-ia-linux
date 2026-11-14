# Blender headless: 4 vues azimut (0/90/180/270) du GLB avec éclairage Studio 3-points
# et environnement dual (fond neutre caméra + dôme studio HDR procédural pour reflets
# spéculaires des gouttes d'eau, réfraction cristal, vernis clearcoat et métaux PBR).
# Usage:
#   blender -b -P orient_rendu_bpy.py -- <glb> <dossier_sortie> [fond]
import math
import os
import sys

import bpy
from mathutils import Vector

argv = sys.argv[sys.argv.index("--") + 1:]
GLB, OUT = argv[0], argv[1]
FOND = float(argv[2]) if len(argv) > 2 else 3.0
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=GLB)
sc = bpy.context.scene

# GARDE ALPHA + PRÉSERVATION OPTIQUE PBR (Transmission, Clearcoat, IOR, Normal, Emission):
# On force Alpha = 1.0 (opacité de surface pour éviter tout trou d'alpha d'atlas),
# tout en préservant intégralement Transmission Weight, Coat Weight, IOR, Normal et Emission.
has_transmissive = False
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
                    _tr = _n.inputs.get("Transmission Weight") or _n.inputs.get("Transmission")
                    if _tr is not None and float(_tr.default_value) > 0.01:
                        if float(_tr.default_value) >= 0.45 or "crystal" in (_m.name or "").lower() or "glass" in (_m.name or "").lower():
                            has_transmissive = True
                        else:
                            _tr.default_value = 0.0
                    _nrm = _n.inputs.get("Normal")
                    _cnrm = _n.inputs.get("Coat Normal")
                    if _nrm is not None and _nrm.is_linked and _cnrm is not None and not _cnrm.is_linked:
                        _m.node_tree.links.new(_nrm.links[0].from_socket, _cnrm)
    except Exception:  # noqa: BLE001
        pass

mn = Vector((1e9,) * 3)
mx = Vector((-1e9,) * 3)
for o in sc.objects:
    if o.type != "MESH":
        continue
    for c in o.bound_box:
        w_pt = o.matrix_world @ Vector(c)
        mn = Vector(map(min, mn, w_pt))
        mx = Vector(map(max, mx, w_pt))
center = (mn + mx) / 2
radius = max((mx - mn).length / 2, 0.1)

cam = bpy.data.objects.new("cam", bpy.data.cameras.new("cam"))
sc.collection.objects.link(cam)
sc.camera = cam

# CYCLES CPU + OpenImageDenoise : rendu physique exact des normales, gouttes d'eau,
# réfraction cristal (KHR_materials_transmission/volume) et vernis clearcoat.
sc.render.engine = "CYCLES"
sc.cycles.device = "CPU"
sc.cycles.samples = 48 if has_transmissive else 36
try:
    sc.cycles.use_denoising = True
except Exception:  # noqa: BLE001
    pass
sc.cycles.max_bounces = 8
sc.cycles.transmission_bounces = 8
sc.cycles.glossy_bounces = 4

# ENVIRONNEMENT DUAL SANS NaN (Caméra = fond studio neutre ; Reflets/Transmission = éclairage studio doux):
w = bpy.data.worlds.new("w")
w.use_nodes = True
nt = w.node_tree
nt.nodes.clear()

n_out = nt.nodes.new("ShaderNodeOutputWorld")
n_mix = nt.nodes.new("ShaderNodeMixShader")
n_lp = nt.nodes.new("ShaderNodeLightPath")
n_bg_cam = nt.nodes.new("ShaderNodeBackground")
n_bg_env = nt.nodes.new("ShaderNodeBackground")

# Fond caméra uniforme neutre
bg_val = max(0.18, min(FOND * 0.22, 0.78))
n_bg_cam.inputs["Color"].default_value = (bg_val, bg_val, bg_val * 1.02, 1.0)
n_bg_cam.inputs["Strength"].default_value = 1.0

# Éclairage ambiant studio doux pour la diffusion/transmission (les reflets spéculaires francs viennent des 3 lampes studio)
n_bg_env.inputs["Color"].default_value = (0.88, 0.90, 0.95, 1.0)
n_bg_env.inputs["Strength"].default_value = 0.72

nt.links.new(n_lp.outputs["Is Camera Ray"], n_mix.inputs["Fac"])
nt.links.new(n_bg_env.outputs["Background"], n_mix.inputs[1])
nt.links.new(n_bg_cam.outputs["Background"], n_mix.inputs[2])
nt.links.new(n_mix.outputs["Shader"], n_out.inputs["Surface"])
sc.world = w

try:
    sc.view_settings.view_transform = "Standard"
    sc.view_settings.look = "None"
except Exception:  # noqa: BLE001
    pass
_render_res = max(640, int(os.environ.get("AURORA_VERIFY_RENDER_RES", "1200")))
sc.render.resolution_x = sc.render.resolution_y = _render_res

# ÉCLAIRAGE STUDIO 3-POINTS (Key + Fill + Rim) solidaire de l'azimut caméra (softbox équilibrée sans brûlure spéculaire)
key_light = bpy.data.objects.new("key_sun", bpy.data.lights.new("key_sun", "SUN"))
key_light.data.energy = 2.15
key_light.data.angle = math.radians(22.0)  # softbox studio douce sans tache de brûlure spéculaire
sc.collection.objects.link(key_light)

fill_light = bpy.data.objects.new("fill_sun", bpy.data.lights.new("fill_sun", "SUN"))
fill_light.data.energy = 1.55
fill_light.data.angle = math.radians(45.0)  # débouchage doux des ombres sous casque/visière sans disque spéculaire parasite
try:
    fill_light.data.specular_factor = 0.0
except Exception:
    pass
fill_light.data.color = (0.95, 0.97, 1.0)
sc.collection.objects.link(fill_light)
try:
    fill_light.visible_glossy = False
except Exception:
    pass

rim_light = bpy.data.objects.new("rim_sun", bpy.data.lights.new("rim_sun", "SUN"))
rim_light.data.energy = 1.35
rim_light.data.angle = math.radians(18.0)  # contre-jour Fresnel doux sur silhouettes et reliefs
rim_light.data.color = (1.0, 0.97, 0.92)
sc.collection.objects.link(rim_light)

dist = radius * 3.0
for i, az in enumerate((270, 0, 90, 180)):
    a = math.radians(az)
    cam.location = center + Vector((math.cos(a), math.sin(a), 0.35)) * dist
    d = center - cam.location
    cam.rotation_euler = d.to_track_quat("-Z", "Y").to_euler()

    # Key light: décalée de +28° en azimut et plus haute (+0.65) pour sculpter le relief et les gouttes
    a_key = math.radians(az + 28.0)
    key_pos = center + Vector((math.cos(a_key), math.sin(a_key), 0.68)) * dist
    key_light.rotation_euler = (center - key_pos).to_track_quat("-Z", "Y").to_euler()

    # Fill light: décalée de -42° en azimut
    a_fill = math.radians(az - 42.0)
    fill_pos = center + Vector((math.cos(a_fill), math.sin(a_fill), 0.22)) * dist
    fill_light.rotation_euler = (center - fill_pos).to_track_quat("-Z", "Y").to_euler()

    # Rim light: contre-jour (+145° en azimut, +0.75 en hauteur)
    a_rim = math.radians(az + 145.0)
    rim_pos = center + Vector((math.cos(a_rim), math.sin(a_rim), 0.75)) * dist
    rim_light.rotation_euler = (center - rim_pos).to_track_quat("-Z", "Y").to_euler()

    sc.render.filepath = os.path.join(OUT, "az%03d.png" % az)
    bpy.ops.render.render(write_still=True)
print("VUES4_OK")
