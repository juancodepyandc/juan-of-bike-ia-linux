"""face_refine.py — raffine la TEXTURE DU VISAGE d'un mesh par re-rendu / restauration / reprojection.

Le probleme: sur un mesh TRELLIS, le visage occupe un petit chart de l'atlas et
sort flou (yeux sans detail, barbe en bouillie). Toute tentative de plaquer une
photo de reference bute sur l'ALIGNEMENT: la photo est cadree autrement que le
mesh, et rien ne garantit la correspondance pixel <-> surface.

La methode retenue supprime le probleme d'alignement par construction:

  1. on REND la tete depuis le mesh lui-meme (camera orthographique, albedo a
     plat sans eclairage) -> l'image EST la surface, vue par une camera connue ;
  2. on RESTAURE ce rendu (`face_restore.restore_in_frame`: prior facial GFPGAN
     recale sur la geometrie reelle + Real-ESRGAN), en gardant le CADRAGE ;
  3. on REPROJETTE l'image restauree avec EXACTEMENT la meme camera -> la
     correspondance est exacte, il n'y a plus aucune boite a deviner.

Plusieurs vues (face + 3/4 gauche + 3/4 droite) sont fusionnees par poids
(orientation x visibilite x marge de cadre), ce qui couvre les joues et les
tempes sans couture.

Usage:
    python face_refine.py <in.glb> <out.glb> [--views 3] [--res 1024] [--strength 0.9]
"""

from __future__ import annotations

import json
import math
import os
import shutil
import subprocess
import sys
import tempfile

_HERE = os.path.dirname(os.path.abspath(__file__))


def _find_blender() -> str | None:
    env = os.environ.get("AURORA_BLENDER")
    if env and os.path.exists(env):
        return env
    for c in ("/home/juan/.local/bin/blender", "/usr/bin/blender", "blender"):
        p = shutil.which(c) if not os.path.isabs(c) else (c if os.path.exists(c) else None)
        if p:
            return p
    return None


# --------------------------------------------------------------------------
# PASSE A (Blender): rendus orthographiques albedo-a-plat, 4 azimuts, plein cadre.
# Sert uniquement a TROUVER la face avant (yunet cote python) et la boite tete.
# --------------------------------------------------------------------------
_BPY_SURVEY = r'''
import bpy, json, math, os, sys
from mathutils import Vector

argv = sys.argv[sys.argv.index("--") + 1:]
GLB, OUTDIR, RES, NAZ = argv[0], argv[1], int(argv[2]), int(argv[3])

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=GLB)
meshes = [o for o in bpy.context.scene.objects if o.type == "MESH"]
if not meshes:
    print("SURVEY_FAIL aucun mesh"); sys.exit(3)

# bbox monde
lo = Vector((1e9, 1e9, 1e9)); hi = Vector((-1e9, -1e9, -1e9))
for ob in meshes:
    for c in ob.bound_box:
        w = ob.matrix_world @ Vector(c)
        for i in range(3):
            lo[i] = min(lo[i], w[i]); hi[i] = max(hi[i], w[i])
ctr = (lo + hi) * 0.5
size = hi - lo
span = max(size.x, size.y, size.z)

# --- albedo A PLAT: chaque materiau devient une emission de sa Base Color ---
# (on veut que le rendu SOIT la texture, pas la texture eclairee)
for ob in meshes:
    for slot in ob.material_slots:
        mat = slot.material
        if not mat or not mat.use_nodes:
            continue
        nt = mat.node_tree
        out = next((n for n in nt.nodes if n.type == "OUTPUT_MATERIAL"), None)
        bsdf = next((n for n in nt.nodes if n.type == "BSDF_PRINCIPLED"), None)
        if not out or not bsdf:
            continue
        emi = nt.nodes.new("ShaderNodeEmission")
        emi.location = (bsdf.location.x, bsdf.location.y - 400)
        bc = bsdf.inputs["Base Color"]
        if bc.is_linked:
            nt.links.new(emi.inputs["Color"], bc.links[0].from_socket)
        else:
            emi.inputs["Color"].default_value = bc.default_value
        nt.links.new(out.inputs["Surface"], emi.outputs["Emission"])
        mat.blend_method = "OPAQUE"

scn = bpy.context.scene
scn.render.engine = "BLENDER_EEVEE_NEXT" if "BLENDER_EEVEE_NEXT" in [
    i.identifier for i in bpy.types.RenderSettings.bl_rna.properties["engine"].enum_items
] else "BLENDER_EEVEE"
scn.render.resolution_x = RES; scn.render.resolution_y = RES
scn.render.resolution_percentage = 100
scn.render.image_settings.file_format = "PNG"
scn.render.image_settings.color_mode = "RGBA"
scn.render.film_transparent = True
scn.view_settings.view_transform = "Standard"   # pas d'ACES: on veut l'albedo brut

cam_d = bpy.data.cameras.new("cam"); cam_d.type = "ORTHO"
cam = bpy.data.objects.new("cam", cam_d); scn.collection.objects.link(cam)
scn.camera = cam

views = []
step = 360.0 / NAZ
for k in range(NAZ):
    az = step * k
    a = math.radians(az)
    d = Vector((math.sin(a), -math.cos(a), 0.0))   # azimut autour de +Z (up)
    cam_d.ortho_scale = span * 1.06
    cam.location = ctr + d * (span * 3.0)
    cam.rotation_euler = d.to_track_quat("Z", "Y").to_euler()
    bpy.context.view_layer.update()
    png = os.path.join(OUTDIR, "survey_%02d.png" % k)
    scn.render.filepath = png
    bpy.ops.render.render(write_still=True)
    views.append({
        "k": k, "azimuth": az, "png": png,
        "dir": [d.x, d.y, d.z],
        "ortho_scale": cam_d.ortho_scale,
        "loc": [cam.location.x, cam.location.y, cam.location.z],
        "matrix": [list(r) for r in cam.matrix_world],
    })

meta = {
    "res": RES, "span": span,
    "center": [ctr.x, ctr.y, ctr.z],
    "bbox": [[lo.x, lo.y, lo.z], [hi.x, hi.y, hi.z]],
    "views": views,
}
open(os.path.join(OUTDIR, "survey.json"), "w").write(json.dumps(meta))
print("SURVEY_OK")
'''


# --------------------------------------------------------------------------
# PASSE B (Blender): rendus orthographiques CADRES SUR LA TETE, N azimuts.
# --------------------------------------------------------------------------
_BPY_HEADSHOT = r'''
import bpy, json, math, os, sys
from mathutils import Vector

argv = sys.argv[sys.argv.index("--") + 1:]
GLB, OUTDIR, CFG = argv[0], argv[1], argv[2]
cfg = json.loads(open(CFG).read())
RES = int(cfg["res"])
CENTER = Vector(cfg["head_center"])
SCALE = float(cfg["head_scale"])       # taille monde du cadre
BASE_AZ = float(cfg["base_azimuth"])   # azimut de la vue de face (deg)
YAWS = cfg["yaws"]                     # ecarts en deg autour de la face
SPAN = float(cfg["span"])

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=GLB)
meshes = [o for o in bpy.context.scene.objects if o.type == "MESH"]

# --- profondeur reelle de la tete -------------------------------------------
# La detection ne donne que la position LATERALE et VERTICALE (elle lit une
# image). La profondeur vient de la geometrie: sans elle, tourner la camera de
# +/-32 deg autour d'un centre mal place fait sortir la tete du cadre.
UP = int(cfg["up_axis"]); LAT = int(cfg["lateral_axis"])
HMIN = cfg["head_min"]; HMAX = cfg["head_max"]
a0 = math.radians(BASE_AZ)
d0 = Vector((math.sin(a0), -math.cos(a0), 0.0))
acc = Vector((0, 0, 0)); n = 0
for ob in meshes:
    mw = ob.matrix_world
    for v in ob.data.vertices:
        w = mw @ v.co
        if HMIN[UP] <= w[UP] <= HMAX[UP] and HMIN[LAT] <= w[LAT] <= HMAX[LAT]:
            acc += w; n += 1
if n:
    centroid = acc / n
    CENTER = CENTER + d0 * (centroid - CENTER).dot(d0)
    print("HEAD_INFO %d sommets tete, centre corrige (%.3f %.3f %.3f)"
          % (n, CENTER.x, CENTER.y, CENTER.z))

for ob in meshes:
    for slot in ob.material_slots:
        mat = slot.material
        if not mat or not mat.use_nodes:
            continue
        nt = mat.node_tree
        out = next((n for n in nt.nodes if n.type == "OUTPUT_MATERIAL"), None)
        bsdf = next((n for n in nt.nodes if n.type == "BSDF_PRINCIPLED"), None)
        if not out or not bsdf:
            continue
        emi = nt.nodes.new("ShaderNodeEmission")
        bc = bsdf.inputs["Base Color"]
        if bc.is_linked:
            nt.links.new(emi.inputs["Color"], bc.links[0].from_socket)
        else:
            emi.inputs["Color"].default_value = bc.default_value
        nt.links.new(out.inputs["Surface"], emi.outputs["Emission"])

scn = bpy.context.scene
scn.render.engine = "BLENDER_EEVEE_NEXT" if "BLENDER_EEVEE_NEXT" in [
    i.identifier for i in bpy.types.RenderSettings.bl_rna.properties["engine"].enum_items
] else "BLENDER_EEVEE"
scn.render.resolution_x = RES; scn.render.resolution_y = RES
scn.render.resolution_percentage = 100
scn.render.image_settings.file_format = "PNG"
scn.render.image_settings.color_mode = "RGB"
scn.render.film_transparent = False
scn.world = bpy.data.worlds.new("w")
scn.world.use_nodes = True
scn.world.node_tree.nodes["Background"].inputs[0].default_value = (0.5, 0.5, 0.5, 1)
scn.view_settings.view_transform = "Standard"

cam_d = bpy.data.cameras.new("cam"); cam_d.type = "ORTHO"
cam_d.ortho_scale = SCALE
cam = bpy.data.objects.new("cam", cam_d); scn.collection.objects.link(cam)
scn.camera = cam

shots = []
for i, dy in enumerate(YAWS):
    a = math.radians(BASE_AZ + float(dy))
    d = Vector((math.sin(a), -math.cos(a), 0.0))
    cam.location = CENTER + d * (SPAN * 3.0)
    cam.rotation_euler = d.to_track_quat("Z", "Y").to_euler()
    bpy.context.view_layer.update()
    png = os.path.join(OUTDIR, "head_%d.png" % i)
    scn.render.filepath = png
    bpy.ops.render.render(write_still=True)
    shots.append({
        "i": i, "yaw": float(dy), "png": png,
        "matrix": [list(r) for r in cam.matrix_world],
        "ortho_scale": float(cam_d.ortho_scale),
        "res": RES,
    })

open(os.path.join(OUTDIR, "shots.json"), "w").write(json.dumps({"shots": shots}))
print("HEADSHOT_OK")
'''


# --------------------------------------------------------------------------
# PASSE C (Blender): reprojection des vues restaurees dans l'atlas.
# --------------------------------------------------------------------------
_BPY_PROJECT = r'''
import bpy, bmesh, json, math, os, sys
import numpy as np
from mathutils import Vector, Matrix
from mathutils.bvhtree import BVHTree

argv = sys.argv[sys.argv.index("--") + 1:]
GLB, OUT_GLB, CFG = argv[0], argv[1], argv[2]
cfg = json.loads(open(CFG).read())
SHOTS = cfg["shots"]                       # [{png_restored, matrix, ortho_scale, res}]
HEAD_MIN = Vector(cfg["head_min"])         # boite tete monde (x,z serres; y libre)
HEAD_MAX = Vector(cfg["head_max"])
STRENGTH = float(cfg.get("strength", 0.9))
UPAX = int(cfg.get("up_axis", 2))

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=GLB)
meshes = [o for o in bpy.context.scene.objects if o.type == "MESH"]
if not meshes:
    print("PROJ_FAIL aucun mesh"); sys.exit(3)
ob = max(meshes, key=lambda o: len(o.data.polygons))
me = ob.data
mw = ob.matrix_world

# --- image albedo cible -----------------------------------------------------
alb = None
for slot in ob.material_slots:
    mat = slot.material
    if not mat or not mat.use_nodes:
        continue
    bsdf = next((n for n in mat.node_tree.nodes if n.type == "BSDF_PRINCIPLED"), None)
    if not bsdf:
        continue
    bc = bsdf.inputs["Base Color"]
    if bc.is_linked and bc.links[0].from_node.type == "TEX_IMAGE":
        alb = bc.links[0].from_node.image
        break
if alb is None:
    print("PROJ_FAIL pas d'image albedo"); sys.exit(4)
AW, AH = alb.size
print("PROJ_INFO albedo %dx%d" % (AW, AH))

uv_atlas = me.uv_layers.active.name if me.uv_layers.active else me.uv_layers[0].name

# --- selection des faces TETE ----------------------------------------------
# boite serree sur x/z (mesurée dans le rendu de face), libre sur la profondeur:
# les faces arriere du crane sont incluses mais recevront un poids nul.
verts = np.empty(len(me.vertices) * 3, dtype=np.float32)
me.vertices.foreach_get("co", verts)
verts = verts.reshape(-1, 3)
mw_np = np.array(mw.to_4x4())
vw = verts @ mw_np[:3, :3].T + mw_np[:3, 3]

AXES = [0, 1, 2]
side_axes = [a for a in AXES if a != UPAX]
inb = np.ones(len(vw), dtype=bool)
inb &= (vw[:, UPAX] >= HEAD_MIN[UPAX]) & (vw[:, UPAX] <= HEAD_MAX[UPAX])
# axe lateral (largeur mesuree dans le rendu): on le connait, il est fourni
LAT = int(cfg["lateral_axis"])
inb &= (vw[:, LAT] >= HEAD_MIN[LAT]) & (vw[:, LAT] <= HEAD_MAX[LAT])

head_faces = [p.index for p in me.polygons if all(inb[v] for v in p.vertices)]
print("PROJ_INFO %d/%d faces tete" % (len(head_faces), len(me.polygons)))
if not head_faces:
    print("PROJ_FAIL aucune face tete"); sys.exit(5)

# --- objet temporaire = uniquement la tete (le bake ne touche que ses texels) --
bpy.ops.object.select_all(action="DESELECT")
ob.select_set(True)
bpy.context.view_layer.objects.active = ob
bpy.ops.object.duplicate()
head = bpy.context.view_layer.objects.active
hme = head.data
bm = bmesh.new(); bm.from_mesh(hme)
bm.faces.ensure_lookup_table()
keep = set(head_faces)
drop = [f for f in bm.faces if f.index not in keep]
bmesh.ops.delete(bm, geom=drop, context="FACES")
bm.to_mesh(hme); bm.free()
print("PROJ_INFO objet tete: %d faces" % len(hme.polygons))

# BVH du mesh COMPLET (occlusion par le corps / les cheveux)
bm_full = bmesh.new(); bm_full.from_mesh(me)
bm_full.transform(mw)
bvh = BVHTree.FromBMesh(bm_full)
bm_full.free()

# normales monde de l'objet tete
hv = np.empty(len(hme.vertices) * 3, dtype=np.float32)
hme.vertices.foreach_get("co", hv); hv = hv.reshape(-1, 3)
hn = np.empty(len(hme.vertices) * 3, dtype=np.float32)
hme.vertices.foreach_get("normal", hn); hn = hn.reshape(-1, 3)
hmw = np.array(head.matrix_world.to_4x4())
hvw = hv @ hmw[:3, :3].T + hmw[:3, 3]
nrm = hn @ np.linalg.inv(hmw[:3, :3]).T
nrm /= np.maximum(np.linalg.norm(nrm, axis=1, keepdims=True), 1e-9)

acc_c = np.zeros((AH, AW, 3), dtype=np.float32)
acc_w = np.zeros((AH, AW, 1), dtype=np.float32)
acc_max = np.zeros((AH, AW, 1), dtype=np.float32)
# Fusion des vues: la MEILLEURE domine (poids^SHARP), on ne les moyenne PAS. Chaque
# vue restauree invente son propre micro-detail; ces details sont decorreles d'une
# vue a l'autre, donc une moyenne les annule (mesure: seulement 34% de l'amplitude
# du differentiel restituee). L'exposant concentre le melange sur la vue la plus
# frontale pour ce texel, tout en gardant un fondu continu (pas de couture).
SHARP = 4.0

for shot in SHOTS:
    M = Matrix([list(r) for r in shot["matrix"]])
    S = float(shot["ortho_scale"])
    cam_loc = M.translation
    R = np.array(M.to_3x3())
    right, up, back = R[:, 0], R[:, 1], R[:, 2]   # camera regarde -Z (donc -back)
    view = -back                                   # direction de vue (monde)

    # 1) UV de projection: monde -> plan camera -> [0,1]
    rel = hvw - np.array(cam_loc)
    px = (rel @ right) / (S * 0.5)                # [-1,1] dans le cadre
    py = (rel @ up) / (S * 0.5)
    u = px * 0.5 + 0.5
    v = py * 0.5 + 0.5

    # 2) poids = orientation x marge de cadre x ellipse du VISAGE x visibilite
    facing = -(nrm @ view)                        # normale face a la camera
    w = np.clip((facing - 0.15) / 0.45, 0.0, 1.0)
    # marge de cadre: fondu 6% au bord, zero hors cadre
    fu = np.clip((np.minimum(u, 1.0 - u)) / 0.06, 0.0, 1.0)
    fv = np.clip((np.minimum(v, 1.0 - v)) / 0.06, 0.0, 1.0)
    w *= fu * fv
    # ellipse du visage: seul le VISAGE est reellement restaure par le prior.
    # Ailleurs (cheveux, nuque, col) l'image restauree n'est qu'un reechantillonnage
    # de l'albedo -> la reprojeter n'apporterait rien et ajouterait du flou.
    uc, vc, ru, rv = shot["face_uv"]
    rr = np.sqrt(((u - uc) / ru) ** 2 + ((v - vc) / rv) ** 2)
    w *= np.clip((1.15 - rr) / 0.30, 0.0, 1.0)
    # 3) visibilite: rayon vers la camera
    cand = np.where(w > 0.01)[0]
    vis = np.zeros(len(hvw), dtype=np.float32)
    eps = float(np.linalg.norm(np.array(HEAD_MAX) - np.array(HEAD_MIN))) * 0.004
    for i in cand:
        o = Vector(hvw[i] + nrm[i] * eps)
        hit = bvh.ray_cast(o, Vector(-view), S * 6.0)
        vis[i] = 0.0 if (hit and hit[0] is not None) else 1.0
    w *= vis
    print("PROJ_INFO vue yaw=%+.0f: %d sommets pondérés (max w=%.2f)"
          % (shot["yaw"], int((w > 0.05).sum()), float(w.max())))
    if float(w.max()) <= 0.05:
        continue

    # --- couche UV de projection
    uvname = "proj_%d" % shot["i"]
    if uvname in hme.uv_layers:
        hme.uv_layers.remove(hme.uv_layers[uvname])
    hme.uv_layers.new(name=uvname)
    lay = hme.uv_layers[uvname]
    loops_v = np.empty(len(hme.loops), dtype=np.int32)
    hme.loops.foreach_get("vertex_index", loops_v)
    uvs = np.empty((len(hme.loops), 2), dtype=np.float32)
    uvs[:, 0] = u[loops_v]; uvs[:, 1] = v[loops_v]
    lay.data.foreach_set("uv", uvs.ravel())

    # --- couleur de poids par sommet
    cname = "wgt_%d" % shot["i"]
    if cname in hme.color_attributes:
        hme.color_attributes.remove(hme.color_attributes[cname])
    ca = hme.color_attributes.new(name=cname, type="FLOAT_COLOR", domain="POINT")
    col = np.ones((len(hme.vertices), 4), dtype=np.float32)
    col[:, 0] = col[:, 1] = col[:, 2] = w
    ca.data.foreach_set("color", col.ravel())

    # LA CIBLE du bake est l'UV ACTIVE -> ce doit etre l'atlas d'origine.
    hme.uv_layers.active = hme.uv_layers[uv_atlas]
    hme.uv_layers[uv_atlas].active_render = True

    # On ne reprojette PAS l'image restauree (cela imposerait a l'atlas la resolution
    # du rendu: mesure -11% de nettete). On reprojette le DIFFERENTIEL de detail
    # (restaure - rendu), encode signe, et on l'AJOUTE a l'atlas: celui-ci garde sa
    # resolution native et ne gagne que ce que le prior a apporte.
    img_r = bpy.data.images.load(shot["png_delta"], check_existing=False)
    img_r.colorspace_settings.name = "Non-Color"   # valeurs BRUTES: c'est un ecart, pas une couleur

    def bake_into(node_builder, name, is_data):
        tgt = bpy.data.images.new(name, AW, AH, alpha=False, float_buffer=True,
                                  is_data=is_data)
        mat = bpy.data.materials.new("bk_" + name)
        mat.use_nodes = True
        nt = mat.node_tree
        for n in list(nt.nodes):
            nt.nodes.remove(n)
        out = nt.nodes.new("ShaderNodeOutputMaterial")
        emi = nt.nodes.new("ShaderNodeEmission")
        nt.links.new(out.inputs["Surface"], emi.outputs["Emission"])
        node_builder(nt, emi)
        tex = nt.nodes.new("ShaderNodeTexImage")   # cible du bake
        tex.image = tgt
        nt.nodes.active = tex
        head.data.materials.clear()
        head.data.materials.append(mat)
        bpy.context.scene.render.engine = "CYCLES"
        bpy.context.scene.cycles.samples = 1
        bpy.context.scene.cycles.use_denoising = False
        bpy.context.scene.render.bake.margin = 4
        bpy.context.scene.render.bake.use_clear = True
        # Le bake applique le FILTRE DE RECONSTRUCTION de pixel (1.5 px par defaut):
        # c'est un flou d'une texel et demie, applique precisement sur les hautes
        # frequences qu'on essaie de transporter. On le neutralise.
        bpy.context.scene.render.filter_size = 0.01
        bpy.ops.object.select_all(action="DESELECT")
        head.select_set(True)
        bpy.context.view_layer.objects.active = head
        bpy.ops.object.bake(type="EMIT")
        buf = np.empty(AW * AH * 4, dtype=np.float32)
        tgt.pixels.foreach_get(buf)
        return buf.reshape(AH, AW, 4)

    def build_color(nt, emi):
        t = nt.nodes.new("ShaderNodeTexImage")
        t.image = img_r
        t.extension = "EXTEND"
        uvn = nt.nodes.new("ShaderNodeUVMap")
        uvn.uv_map = uvname
        nt.links.new(t.inputs["Vector"], uvn.outputs["UV"])
        nt.links.new(emi.inputs["Color"], t.outputs["Color"])

    def build_weight(nt, emi):
        c = nt.nodes.new("ShaderNodeVertexColor")
        c.layer_name = cname
        nt.links.new(emi.inputs["Color"], c.outputs["Color"])

    # is_data=True sur LES DEUX cibles: le bake ecrit du lineaire, et une image
    # declaree sRGB se ferait re-convertir a la lecture de .pixels -> une
    # linearisation de trop, soit un visage nettement assombri (verifie: la peau
    # passait de 158/119/110 a 106/62/54).
    C = bake_into(build_color, "C_%d" % shot["i"], True)
    W = bake_into(build_weight, "W_%d" % shot["i"], True)
    Wv = W[:, :, :1]
    Ws = np.power(np.clip(Wv, 0.0, 1.0), SHARP)
    acc_c += C[:, :, :3] * Ws
    acc_w += Ws
    acc_max = np.maximum(acc_max, Wv)
    print("PROJ_INFO vue %d bakee (texels w>0.05: %d)"
          % (shot["i"], int((W[:, :, 0] > 0.05).sum())))
    del C, W, Wv, Ws

# --- composition dans l'atlas ----------------------------------------------
base = np.empty(AW * AH * 4, dtype=np.float32)
alb.pixels.foreach_get(base)
base = base.reshape(AH, AW, 4)

# couverture = MEILLEURE vue du texel (et non la somme des poids: un texel bien vu
# par une seule vue est aussi bien servi qu'un texel vu par trois).
den = acc_max[:, :, 0]
mask = den > 0.02
if not mask.any():
    print("PROJ_FAIL aucun texel pondéré"); sys.exit(6)
# Decodage du signe: l'encodage est enc = d*0.5 + 0.5 (pour tenir dans [0,1] avec
# le signe), donc d = (enc - 0.5) * 2. Sans le facteur 2 on ne reinjecte que la
# moitie du differentiel.
delta = (acc_c / np.maximum(acc_w, 1e-6) - 0.5) * 2.0

# `Image.pixels` rend le buffer BRUT: pour un atlas 8 bits c'est du sRGB ENCODE, et
# le differentiel a ete calcule dans CE MEME espace (les rendus sont des PNG sRGB) ->
# l'addition est directement homogene. Pour un atlas FLOTTANT le buffer est lineaire:
# on passe alors la base en sRGB, on y ajoute le differentiel, et on revient.
_l2s = lambda x: np.where(x <= 0.0031308, x * 12.92,
                          1.055 * np.power(np.clip(x, 0.0, None), 1 / 2.4) - 0.055)
_s2l = lambda x: np.where(x <= 0.04045, x / 12.92,
                          ((np.clip(x, 0.0, 1.0) + 0.055) / 1.055) ** 2.4)

a = (STRENGTH * np.clip(den, 0.0, 1.0))[:, :, None]
out = base.copy()
if alb.is_float:
    print("PROJ_INFO atlas flottant -> ajout du differentiel dans l'espace sRGB")
    srgb = _l2s(base[:, :, :3])
    out[:, :, :3] = _s2l(np.clip(srgb + a * delta, 0.0, 1.0))
else:
    out[:, :, :3] = np.clip(base[:, :, :3] + a * delta, 0.0, 1.0)
alb.pixels.foreach_set(out.ravel())
alb.update()
if alb.packed_file or not alb.filepath:
    alb.pack()

amp = float(np.abs(delta[mask]).mean())
print("PROJ_INFO %d texels enrichis (%.2f%% de l'atlas), detail moyen ajoute %.1f/255"
      % (int(mask.sum()), 100.0 * mask.sum() / (AW * AH), amp * 255.0))

# --- RELIEF: carte de normales du visage ------------------------------------
# Le mesh n'en a AUCUNE (verifie sur le GLB): son visage est un bloc lisse. On
# projette la hauteur extraite de la reference, puis on laisse BLENDER en deduire
# la normale tangente. C'est volontaire: son noeud Bump derive la hauteur SUR LA
# SURFACE, la ou un gradient calcule dans l'atlas serait faux a chaque frontiere
# d'ilot (l'atlas natif est tres fragmente).
HEIGHT = cfg.get("height")
if HEIGHT and os.path.isfile(HEIGHT.get("png", "")):
    NRES = int(cfg.get("normal_res", 4096))
    himg = bpy.data.images.load(HEIGHT["png"], check_existing=False)
    himg.colorspace_settings.name = "Non-Color"

    # hauteur -> atlas, par la meme projection que l'albedo
    hbake = bpy.data.images.new("H_atlas", NRES, NRES, alpha=False,
                                float_buffer=True, is_data=True)

    front = SHOTS[0]
    mat = bpy.data.materials.new("bk_h")
    mat.use_nodes = True
    nt = mat.node_tree
    for n0 in list(nt.nodes):
        nt.nodes.remove(n0)
    out_n = nt.nodes.new("ShaderNodeOutputMaterial")
    emi = nt.nodes.new("ShaderNodeEmission")
    nt.links.new(out_n.inputs["Surface"], emi.outputs["Emission"])
    t = nt.nodes.new("ShaderNodeTexImage")
    t.image = himg
    t.extension = "EXTEND"
    uvn = nt.nodes.new("ShaderNodeUVMap")
    uvn.uv_map = "proj_%d" % front["i"]
    nt.links.new(t.inputs["Vector"], uvn.outputs["UV"])
    nt.links.new(emi.inputs["Color"], t.outputs["Color"])
    tgt = nt.nodes.new("ShaderNodeTexImage")
    tgt.image = hbake
    nt.nodes.active = tgt
    head.data.materials.clear()
    head.data.materials.append(mat)
    hme.uv_layers.active = hme.uv_layers[uv_atlas]
    bpy.context.scene.render.bake.use_clear = True
    bpy.ops.object.select_all(action="DESELECT")
    head.select_set(True)
    bpy.context.view_layer.objects.active = head
    bpy.ops.object.bake(type="EMIT")

    # hors du visage, la hauteur doit etre NEUTRE (0.5), pas 0: sinon le Bump
    # verrait une falaise au bord du masque.
    hbuf = np.empty(NRES * NRES * 4, dtype=np.float32)
    hbake.pixels.foreach_get(hbuf)
    hbuf = hbuf.reshape(NRES, NRES, 4)
    _ix = (np.arange(NRES) * (AH / float(NRES))).astype(np.int64)
    flat = acc_max[:, :, 0][np.ix_(_ix, _ix)] <= 0.02
    hbuf[flat, 0] = hbuf[flat, 1] = hbuf[flat, 2] = 0.5
    hbake.pixels.foreach_set(hbuf.ravel())
    hbake.update()

    # Bump -> bake de la normale TANGENTE
    nimg = bpy.data.images.new("N_atlas", NRES, NRES, alpha=False,
                               float_buffer=False, is_data=True)
    npx = np.tile(np.array([0.5, 0.5, 1.0, 1.0], dtype=np.float32), NRES * NRES)
    nimg.pixels.foreach_set(npx)

    mat2 = bpy.data.materials.new("bk_n")
    mat2.use_nodes = True
    nt2 = mat2.node_tree
    for n0 in list(nt2.nodes):
        nt2.nodes.remove(n0)
    out2 = nt2.nodes.new("ShaderNodeOutputMaterial")
    bsdf2 = nt2.nodes.new("ShaderNodeBsdfPrincipled")
    nt2.links.new(out2.inputs["Surface"], bsdf2.outputs["BSDF"])
    ht = nt2.nodes.new("ShaderNodeTexImage")
    ht.image = hbake
    ht.interpolation = "Cubic"
    bump = nt2.nodes.new("ShaderNodeBump")
    bump.inputs["Strength"].default_value = 1.0
    bump.inputs["Distance"].default_value = float(HEIGHT["h_scale"]) * float(
        cfg.get("normal_strength", 1.0))
    nt2.links.new(bump.inputs["Height"], ht.outputs["Color"])
    nt2.links.new(bsdf2.inputs["Normal"], bump.outputs["Normal"])
    tgt2 = nt2.nodes.new("ShaderNodeTexImage")
    tgt2.image = nimg
    nt2.nodes.active = tgt2
    head.data.materials.clear()
    head.data.materials.append(mat2)
    bpy.context.scene.render.bake.use_clear = False   # garder la normale plate ailleurs
    bpy.context.scene.render.bake.normal_space = "TANGENT"
    bpy.ops.object.select_all(action="DESELECT")
    head.select_set(True)
    bpy.context.view_layer.objects.active = head
    bpy.ops.object.bake(type="NORMAL")

    nbuf = np.empty(NRES * NRES * 4, dtype=np.float32)
    nimg.pixels.foreach_get(nbuf)
    nbuf = nbuf.reshape(NRES, NRES, 4)
    dev = float(np.abs(nbuf[:, :, :2] - 0.5).max())
    nimg.pack()

    # brancher la normale sur le materiau D'ORIGINE
    for slot in ob.material_slots:
        m = slot.material
        if not m or not m.use_nodes:
            continue
        b = next((n0 for n0 in m.node_tree.nodes if n0.type == "BSDF_PRINCIPLED"), None)
        if not b:
            continue
        nm = m.node_tree.nodes.new("ShaderNodeNormalMap")
        tn = m.node_tree.nodes.new("ShaderNodeTexImage")
        tn.image = nimg
        tn.interpolation = "Linear"
        m.node_tree.links.new(nm.inputs["Color"], tn.outputs["Color"])
        m.node_tree.links.new(b.inputs["Normal"], nm.outputs["Normal"])
    print("PROJ_INFO carte de normales %dx%d creee (relief +/-%.1f mm, ecart max %.3f)"
          % (NRES, NRES, HEIGHT["h_scale"] * 500.0, dev))

bpy.data.objects.remove(head, do_unlink=True)
bpy.ops.export_scene.gltf(filepath=OUT_GLB, export_format="GLB",
                          export_materials="EXPORT")
print("PROJ_OK glb=%s texels=%d" % (OUT_GLB, int(mask.sum())))
'''


def _delta_from_reference(render_png: str, reference_png: str, delta_png: str,
                          crop_png: str):
    """Differentiel de structure pris sur la VRAIE reference, recalee par ses reperes.

    C'est la source d'information la plus riche dont on dispose: la reference FLUX
    a un visage NET, aux yeux OUVERTS (mesure: 148 px, score 0.93). Le generateur,
    lui, ne la voit qu'a 518 px - la tete n'y fait plus que ~55 px - d'ou des yeux
    en pastilles qu'aucun prior ne reconstruit (GFPGAN, partant de la bouillie,
    ne produit qu'un visage lisse generique).

    L'ALIGNEMENT, qui avait fait echouer la premiere tentative, est ici exact: le
    detecteur rend 5 reperes (yeux, nez, coins de bouche) sur la reference ET sur
    le rendu du mesh. Deux jeux de reperes donnent la similitude qui les superpose.

    On n'emprunte a la reference que sa STRUCTURE (moyennes + hautes frequences):
    les basses frequences - donc la carnation et l'eclairage - restent celles du
    mesh, sinon la greffe se verrait comme une couture.
    """
    import cv2
    import numpy as np
    import face_restore as fr

    hit_ren = fr.detect_face_bbox(render_png, allow_silhouette=False)
    if hit_ren is None:
        return None, "aucun visage sur le rendu"

    # la tete de la reference, restauree et upscalee (Real-ESRGAN x4 + prior)
    info = fr.restore_face(reference_png, crop_png, target=1024, margin=1.9,
                           fidelity=0.9, detail=0.9, suppress=0.0, min_identity=0.30)
    if not info.get("ok"):
        return None, "reference non restauree: %s" % info.get("error")

    crop = cv2.imread(crop_png, cv2.IMREAD_COLOR)
    ren = cv2.imread(render_png, cv2.IMREAD_COLOR)
    R = ren.shape[0]

    hx, hy, hs, _ = info["head_box"]
    sc = float(info["target"]) / float(hs)
    lmk_ref = np.array(info["landmarks"], dtype=np.float32)
    lmk_crop = (lmk_ref - np.array([hx, hy], np.float32)) * sc      # reperes dans le crop
    lmk_ren = np.array(hit_ren.landmarks, dtype=np.float32)         # reperes dans le rendu

    M, _inl = cv2.estimateAffinePartial2D(lmk_crop, lmk_ren, method=cv2.LMEDS)
    if M is None:
        return None, "recalage des reperes impossible"
    warped = cv2.warpAffine(crop, M, (R, R), flags=cv2.INTER_LANCZOS4,
                            borderMode=cv2.BORDER_REPLICATE).astype(np.float32)

    # residu de recalage (en px) = qualite de la superposition des traits
    proj = cv2.transform(lmk_crop.reshape(-1, 1, 2), M).reshape(-1, 2)
    err = float(np.linalg.norm(proj - lmk_ren, axis=1).mean())

    # NB: on s'en tient a la SIMILITUDE. Un recalage dense (flot optique) a ete
    # essaye pour rattraper les ~11 px de residu: il DEGRADE nettement le resultat.
    # Le flot est estime entre la reference et un visage en bouillie - il n'y trouve
    # pas de correspondances fiables, produit un champ aberrant, et fait litteralement
    # fondre la bouche et la barbe. Sur une geometrie aussi abimee, la contrainte
    # rigide des 5 reperes est plus robuste que la liberte du flot.
    fw = max(hit_ren.bbox[2], hit_ren.bbox[3])
    ren_f = ren.astype(np.float32)

    # on ne garde que la structure: basses frequences reprises au mesh
    sig = max(2.0, 0.10 * fw)
    matched = warped - cv2.GaussianBlur(warped, (0, 0), sig) \
        + cv2.GaussianBlur(ren_f, (0, 0), sig)

    d = (matched - ren_f) / 255.0
    enc = np.clip(d * 0.5 + 0.5, 0.0, 1.0)
    cv2.imwrite(delta_png, (enc * 65535.0).astype(np.uint16))

    # la reference RECALEE dans le cadre du rendu: c'est elle qui porte le relief
    warped_png = os.path.splitext(delta_png)[0] + "_warped.png"
    cv2.imwrite(warped_png, np.clip(warped, 0, 255).astype(np.uint8))

    return {
        "residu_reperes_px": round(err, 2),
        "visage_reference_px": info.get("face_px_in"),
        "visage_restaure_px": info.get("face_px_out"),
        "identity_cosine": info.get("identity_cosine"),
        "detail": round(float(np.abs(d).mean() * 255.0), 2),
        "warped_png": warped_png,
        "landmarks": [[float(a), float(b)] for a, b in lmk_ren],
        "face_px": float(fw),
    }, None


def _integrate_slopes(p, q):
    """Reconstruit une hauteur a partir de ses pentes (Frankot-Chellappa, par FFT).

    Un champ de normales n'est pas integrable exactement (bruit, occlusions): on
    cherche la hauteur dont le gradient est le plus proche, au sens des moindres
    carres. La solution est directe en Fourier.
    """
    import numpy as np
    H, W = p.shape
    wx = np.fft.fftfreq(W).reshape(1, W) * 2.0 * np.pi
    wy = np.fft.fftfreq(H).reshape(H, 1) * 2.0 * np.pi
    P, Q = np.fft.fft2(p), np.fft.fft2(q)
    den = wx ** 2 + wy ** 2
    den[0, 0] = 1.0
    Z = (-1j * wx * P - 1j * wy * Q) / den
    Z[0, 0] = 0.0
    return np.real(np.fft.ifft2(Z))


def _relief_from_reference(warped_png: str, height_png: str, landmarks,
                           face_px: float, world_per_px: float):
    """Extrait le RELIEF du visage de la reference et l'exprime en hauteur (monde).

    Le mesh n'a AUCUNE carte de normales (verifie sur le GLB): son visage est un
    bloc lisse, ce qu'aucune texture ne compense - c'est un defaut de GEOMETRIE.
    L'etat de l'art (Make-A-Character 2, Photo-Realistic Facial Details Synthesis)
    represente ce detail comme un displacement en espace UV, infere de l'image.

    On estime donc les normales de surface de la reference recalee (Marigold, par
    diffusion), on les integre en hauteur, et on n'en garde que les HAUTES
    FREQUENCES: rides, orbites, ailes du nez, sillon des levres. La forme globale
    du visage, elle, appartient au mesh - la reprendre creerait un conflit avec sa
    silhouette reelle.
    """
    import cv2
    import numpy as np
    import torch
    from diffusers import MarigoldNormalsPipeline

    img = cv2.imread(warped_png, cv2.IMREAD_COLOR)
    R = img.shape[0]
    dev = "cuda" if torch.cuda.is_available() else "cpu"
    pipe = MarigoldNormalsPipeline.from_pretrained(
        "prs-eth/marigold-normals-v1-1",
        torch_dtype=torch.float16 if dev == "cuda" else torch.float32).to(dev)
    small = cv2.resize(img, (768, 768), interpolation=cv2.INTER_AREA)
    out = pipe(cv2.cvtColor(small, cv2.COLOR_BGR2RGB), num_inference_steps=4,
               processing_resolution=768, ensemble_size=1)
    n = np.asarray(out.prediction[0], dtype=np.float32)
    del pipe
    if dev == "cuda":
        torch.cuda.empty_cache()
    n = cv2.resize(n, (R, R), interpolation=cv2.INTER_LINEAR)
    nz = np.where(np.abs(n[:, :, 2]) < 0.15, 0.15 * np.sign(n[:, :, 2] + 1e-6),
                  n[:, :, 2])

    # Les conventions d'axe d'un estimateur de normales ne sont pas garanties (y
    # vers le haut ou vers le bas, z vers ou depuis la camera). Plutot que de les
    # supposer, on TESTE les 4 combinaisons de signes et on garde celle qui est
    # physiquement juste: le nez RESSORT et les yeux sont EN CREUX. Les reperes du
    # detecteur donnent ces trois points, donc le critere est objectif.
    (rex, rey), (lex, ley), (nx_, ny_) = landmarks[0], landmarks[1], landmarks[2]
    rad = max(3, int(0.10 * face_px))

    def _disk(h, cx, cy):
        y0, y1 = max(0, int(cy) - rad), min(R, int(cy) + rad)
        x0, x1 = max(0, int(cx) - rad), min(R, int(cx) + rad)
        return float(h[y0:y1, x0:x1].mean()) if y1 > y0 and x1 > x0 else 0.0

    best, best_score = None, -1e30
    for sx in (1.0, -1.0):
        for sy in (1.0, -1.0):
            h = _integrate_slopes(sx * (-n[:, :, 0] / nz), sy * (-n[:, :, 1] / nz))
            score = _disk(h, nx_, ny_) - 0.5 * (_disk(h, rex, rey) + _disk(h, lex, ley))
            if score > best_score:
                best, best_score = h, score
    h = best

    # relief = hautes frequences seules; la forme globale reste celle du mesh
    sig = max(2.0, 0.11 * face_px)
    h = (h - cv2.GaussianBlur(h, (0, 0), sig)) * world_per_px

    amp = float(np.percentile(np.abs(h), 99.5)) or 1e-6
    enc = np.clip(h / (2.0 * amp) + 0.5, 0.0, 1.0)
    cv2.imwrite(height_png, (enc * 65535.0).astype(np.uint16))
    return {"h_scale": 2.0 * amp, "relief_mm": round(amp * 1000.0, 3),
            "nez_saillant": bool(best_score > 0)}


def _run_blender(script: str, args: list[str], tag: str) -> str:
    blender = _find_blender()
    if not blender:
        raise RuntimeError("blender introuvable")
    with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False) as f:
        f.write(script)
        sp = f.name
    cmd = [blender, "-b", "--factory-startup", "-noaudio", "-P", sp, "--"] + args
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=3600)
    os.unlink(sp)
    log = (r.stdout or "") + (r.stderr or "")
    keep = [l for l in log.splitlines() if any(
        k in l for k in ("_INFO", "_OK", "_FAIL", "Error", "Traceback"))]
    for l in keep:
        sys.stderr.write("[face_refine/%s] %s\n" % (tag, l))
    if "%s_OK" % tag.upper() not in log:
        raise RuntimeError("passe %s echouee" % tag)
    return log


def refine_face(glb: str, out_glb: str, views: int = 3, res: int = 1024,
                strength: float = 0.9, workdir: str | None = None,
                upscale: int = 2, suppress: float = 0.0,
                fidelity: float = 0.35, chroma: float = 0.8,
                reference: str | None = None, relief: bool = True,
                normal_strength: float = 1.0) -> dict:
    """`res` cadre la tete pour que le visage y fasse ~500px: la RESOLUTION NATIVE
    du prior GFPGAN (512). Inutile de monter plus haut: on ne reprojette pas l'image
    restauree mais le DIFFERENTIEL de detail, qu'on ADDITIONNE a l'atlas - celui-ci
    garde donc sa propre resolution (remplacer ses texels par le rendu lui coutait
    -11% de nettete, mesure).

    `suppress` DOIT rester nul ici: ce terme rabote les hautes frequences de la base
    pour brider celles qu'invente Real-ESRGAN, mais dans un differentiel il se
    traduirait par un detail NEGATIF, donc par un flou soustrait a l'atlas.
    """
    sys.path.insert(0, _HERE)
    import cv2
    import numpy as np
    import face_restore

    wd = workdir or tempfile.mkdtemp(prefix="facerefine_")
    os.makedirs(wd, exist_ok=True)

    # --- A: reperage (balayage d'azimuts, plein cadre) ----------------------
    naz = 24
    _run_blender(_BPY_SURVEY, [glb, wd, "640", str(naz)], "survey")
    survey = json.loads(open(os.path.join(wd, "survey.json")).read())

    # On ne cherche pas le meilleur SCORE de detection mais la vue la plus
    # FRONTALE: un profil se detecte tres bien et donnerait un cadrage de biais.
    # Frontalite = symetrie du nez entre les deux yeux (reperes yunet).
    best = None
    for v in survey["views"]:
        try:
            hit = face_restore.detect_face_bbox(v["png"], allow_silhouette=False)
        except Exception:
            hit = None
        if not hit or len(hit.landmarks) < 3:
            continue
        (rex, rey), (lex, ley), (nx, ny) = hit.landmarks[0], hit.landmarks[1], hit.landmarks[2]
        eye_d = math.hypot(lex - rex, ley - rey)
        if eye_d < 1e-3:
            continue
        skew = abs(nx - (lex + rex) * 0.5) / eye_d      # 0 = nez centre = de face
        front = max(0.0, 1.0 - 2.0 * skew)
        rank = hit.score * front
        sys.stderr.write(
            "[face_refine] azimut %3.0f: score=%.3f frontalite=%.2f -> %.3f\n"
            % (v["azimuth"], hit.score, front, rank))
        if best is None or rank > best[2]:
            best = (v, hit, rank)
    if best is None:
        return {"ok": False, "error": "aucun visage detecte sur %d azimuts" % naz}

    view, hit, _rank = best
    R = int(survey["res"])
    S = float(view["ortho_scale"])
    # boite tete (carre) dans le rendu -> monde, via le mapping ortho exact
    hx, hy, hs = face_restore.head_box(hit, R, R, margin=1.55)
    cx_px, cy_px = hx + hs * 0.5, hy + hs * 0.5
    ndc_x = (cx_px / R) * 2.0 - 1.0
    ndc_y = 1.0 - (cy_px / R) * 2.0          # image top-down -> ndc bottom-up
    M = view["matrix"]
    right = np.array([M[0][0], M[1][0], M[2][0]])
    up = np.array([M[0][1], M[1][1], M[2][1]])
    # Le centre du modele se projette au centre du cadre: on part de LUI (et non
    # de la camera, qui est a 3 spans devant -> centre de rotation aberrant).
    mctr = np.array(survey["center"], dtype=float)
    ctr_w = mctr + right * (ndc_x * S * 0.5) + up * (ndc_y * S * 0.5)
    head_w = (hs / R) * S                    # taille monde du cadre tete

    up_axis = int(np.argmax(np.abs(up)))
    lat_axis = int(np.argmax(np.abs(right)))
    lo = np.array(survey["bbox"][0], dtype=float)
    hi = np.array(survey["bbox"][1], dtype=float)
    hmin, hmax = lo.copy(), hi.copy()
    for ax, half in ((up_axis, head_w * 0.5), (lat_axis, head_w * 0.5)):
        hmin[ax] = ctr_w[ax] - half
        hmax[ax] = ctr_w[ax] + half
    sys.stderr.write(
        "[face_refine] face avant: azimut %.0f (score %.3f) | tete: centre "
        "(%.3f %.3f %.3f) taille %.3f | up=%d lat=%d\n"
        % (view["azimuth"], hit.score, ctr_w[0], ctr_w[1], ctr_w[2], head_w,
           up_axis, lat_axis))

    # --- B: rendus tete (N azimuts autour de la face) -----------------------
    yaws = {1: [0.0], 3: [-30.0, 0.0, 30.0],
            5: [-50.0, -26.0, 0.0, 26.0, 50.0]}.get(views, [-30.0, 0.0, 30.0])
    cfg_b = {
        "res": res, "head_center": [float(x) for x in ctr_w],
        "head_scale": head_w * 1.25, "base_azimuth": float(view["azimuth"]),
        "yaws": yaws, "span": float(survey["span"]),
        "head_min": [float(x) for x in hmin], "head_max": [float(x) for x in hmax],
        "up_axis": up_axis, "lateral_axis": lat_axis,
    }
    p_b = os.path.join(wd, "cfg_b.json")
    open(p_b, "w").write(json.dumps(cfg_b))
    _run_blender(_BPY_HEADSHOT, [glb, wd, p_b], "headshot")
    shots = json.loads(open(os.path.join(wd, "shots.json")).read())["shots"]

    # --- VOIE REFERENCE: la vraie face, recalee par ses reperes --------------
    # Elle prime sur le prior: la reference contient l'information REELLE (yeux
    # ouverts, traits nets) que le generateur a perdue en ré-échantillonnant son
    # entree. Le prior, lui, ne peut qu'inventer a partir de la bouillie.
    kept = []
    height_cfg = None
    if reference and os.path.isfile(reference):
        front = next((s for s in shots if abs(s["yaw"]) < 1e-6), None)
        if front is not None:
            info, err = _delta_from_reference(
                front["png"], reference,
                os.path.join(wd, "ref_delta.png"), os.path.join(wd, "ref_crop.png"))
            if info is None:
                sys.stderr.write("[face_refine] voie reference indisponible (%s)\n" % err)
            else:
                hit = face_restore.detect_face_bbox(front["png"], allow_silhouette=False)
                Rv = int(front["res"])
                bx, by, bw, bh = hit.bbox
                # ellipse calee sur le visage DETECTE: hors de cette zone la machoire
                # et la chevelure de la reference ne coincident pas avec celles du
                # mesh, et y projeter laisserait un fantome.
                front["face_uv"] = [(bx + bw * 0.5) / Rv, 1.0 - (by + bh * 0.5) / Rv,
                                    (bw * 0.5) / Rv * 1.25, (bh * 0.5) / Rv * 1.15]
                front["png_delta"] = os.path.join(wd, "ref_delta.png")
                front["png_restored"] = os.path.join(wd, "ref_crop.png")
                kept.append(front)
                sys.stderr.write(
                    "[face_refine] REFERENCE recalee: visage %s->%s px, residu "
                    "reperes %.1f px, identite=%s, detail %.1f/255\n"
                    % (info["visage_reference_px"], info["visage_restaure_px"],
                       info["residu_reperes_px"], info["identity_cosine"],
                       info["detail"]))

                # RELIEF: le mesh n'a aucune carte de normales -> visage plat.
                if relief:
                    try:
                        height_png = os.path.join(wd, "ref_height.png")
                        hinfo = _relief_from_reference(
                            info["warped_png"], height_png, info["landmarks"],
                            info["face_px"], head_w * 1.25 / float(res))
                        hinfo["png"] = height_png
                        height_cfg = hinfo
                        sys.stderr.write(
                            "[face_refine] RELIEF extrait: +/-%.2f mm, nez saillant=%s\n"
                            % (hinfo["relief_mm"], hinfo["nez_saillant"]))
                    except Exception as exc:  # noqa: BLE001
                        sys.stderr.write("[face_refine] relief indisponible: %r\n" % exc)
        if kept:
            shots = []          # la reference suffit: pas de prior a superposer

    # --- sinon: restauration de chaque vue par le prior (cadrage conserve) ---
    for s in shots:
        # une vue sans visage detecte n'apporte rien et projetterait du vide:
        # on la rejette AVANT de payer la restauration.
        try:
            vh = face_restore.detect_face_bbox(s["png"], allow_silhouette=False)
        except Exception:
            vh = None
        if vh is None:
            sys.stderr.write("[face_refine] vue yaw=%+.0f: aucun visage -> ignoree\n"
                             % s["yaw"])
            continue
        out_png = os.path.join(wd, "head_%d_restored.png" % s["i"])
        try:
            info = face_restore.restore_in_frame(
                s["png"], out_png, upscale=upscale, fidelity=fidelity, detail=1.0,
                suppress=suppress, chroma=chroma, min_identity=0.35,
            )
        except Exception as exc:
            sys.stderr.write("[face_refine] restore vue %d echec: %s\n" % (s["i"], exc))
            continue
        if not info.get("ok") or not info.get("restorer"):
            sys.stderr.write(
                "[face_refine] vue yaw=%+.0f: prior NON applique (%s) -> ignoree\n"
                % (s["yaw"], info.get("prior_rejected") or info.get("error")))
            continue

        # DIFFERENTIEL DE DETAIL: ce que la restauration a AJOUTE, et rien d'autre.
        # On le reprojettera pour l'ADDITIONNER a l'atlas, au lieu de remplacer ses
        # texels par le rendu (ce qui lui imposerait la resolution du rendu: -11%
        # de nettete mesures). L'encodage est signe (+0.5) sur 16 bits.
        # Le differentiel est calcule A LA RESOLUTION DU RENDU, pas a celle de
        # l'image restauree: l'atlas ne dispose que d'environ autant de texels que
        # le rendu a de pixels pour le visage. Un differentiel a 2x cette bande se
        # fait echantillonner sans pre-filtrage par le bake -> il crenele, et le
        # rendu moyenne ensuite ce bruit (mesure: seuls 34% de l'amplitude
        # survivaient). INTER_AREA borne proprement la bande.
        ren = cv2.imread(s["png"], cv2.IMREAD_COLOR).astype(np.float32)
        res_img = cv2.imread(out_png, cv2.IMREAD_COLOR).astype(np.float32)
        if res_img.shape[:2] != ren.shape[:2]:
            res_img = cv2.resize(res_img, (ren.shape[1], ren.shape[0]),
                                 interpolation=cv2.INTER_AREA)
        d = (res_img - ren) / 255.0
        enc = np.clip(d * 0.5 + 0.5, 0.0, 1.0)
        delta_png = os.path.join(wd, "head_%d_delta.png" % s["i"])
        cv2.imwrite(delta_png, (enc * 65535.0).astype(np.uint16))

        # Ellipse du visage: DEDUITE DU CADRAGE, pas d'une detection (celle-ci varie
        # d'une vue a l'autre - mesure: 186px puis 582px sur le meme sujet - et une
        # boite trop petite annulerait la vue). La camera vise le centre de la tete
        # et le cadre vaut head_w*1.25, donc le visage est centre, de rayon connu.
        s["face_uv"] = [0.5, 0.5, 0.34, 0.40]
        s["png_delta"] = delta_png
        s["png_restored"] = out_png
        kept.append(s)
        sys.stderr.write(
            "[face_refine] vue yaw=%+.0f restauree: identite=%s, prior=%s, "
            "detail ajoute %.1f/255\n"
            % (s["yaw"], info.get("identity_cosine"), info.get("restorer"),
               float(np.abs(d).mean() * 255.0)))
    if not kept:
        return {"ok": False, "error": "aucune vue tete restauree"}

    # --- C: reprojection ----------------------------------------------------
    cfg_c = {
        "shots": kept, "strength": strength,
        "head_min": [float(x) for x in hmin], "head_max": [float(x) for x in hmax],
        "up_axis": up_axis, "lateral_axis": lat_axis,
        "height": height_cfg, "normal_res": 4096,
        "normal_strength": normal_strength,
    }
    p_c = os.path.join(wd, "cfg_c.json")
    open(p_c, "w").write(json.dumps(cfg_c))
    log = _run_blender(_BPY_PROJECT, [glb, out_glb, p_c], "proj")
    texels = 0
    for l in log.splitlines():
        if l.startswith("PROJ_OK"):
            for tok in l.split():
                if tok.startswith("texels="):
                    texels = int(tok.split("=")[1])

    return {
        "ok": True, "output": out_glb, "workdir": wd,
        "front_azimuth": view["azimuth"], "detect_score": round(hit.score, 3),
        "head_center": [round(float(x), 4) for x in ctr_w],
        "head_scale": round(head_w, 4),
        "views": [{"yaw": s["yaw"], "png": s["png_restored"]} for s in kept],
        "texels": texels, "strength": strength,
        "relief_mm": (height_cfg or {}).get("relief_mm"),
        "normal_map": bool(height_cfg),
    }


def main() -> int:
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("glb")
    ap.add_argument("output")
    ap.add_argument("--views", type=int, default=3)
    ap.add_argument("--res", type=int, default=1024)
    ap.add_argument("--strength", type=float, default=0.85)
    ap.add_argument("--workdir", default=None)
    ap.add_argument("--upscale", type=int, default=2)
    ap.add_argument("--suppress", type=float, default=0.0)
    ap.add_argument("--fidelity", type=float, default=0.35)
    ap.add_argument("--chroma", type=float, default=0.8)
    ap.add_argument("--reference", default=None,
                    help="image de reference du run: sa face, recalee par ses "
                         "reperes, prime sur le prior (information REELLE)")
    ap.add_argument("--no-relief", action="store_true",
                    help="ne pas construire la carte de normales du visage")
    ap.add_argument("--normal-strength", type=float, default=1.0)
    a = ap.parse_args()
    try:
        r = refine_face(a.glb, a.output, a.views, a.res, a.strength, a.workdir,
                        a.upscale, a.suppress, a.fidelity, a.chroma, a.reference,
                        not a.no_relief, a.normal_strength)
    except Exception as exc:
        r = {"ok": False, "error": str(exc)}
    print("AURORA_FACE_REFINE_RESULT " + json.dumps(r))
    return 0 if r.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
