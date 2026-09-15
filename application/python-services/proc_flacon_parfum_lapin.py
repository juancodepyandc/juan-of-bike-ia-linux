#!/usr/bin/env python3
"""Flacon de parfum en forme de lapin, en CRISTAL — genere, pas reconstruit.

Pourquoi procedural et pas image->3D: un objet TRANSPARENT ne peut pas etre
reconstruit depuis une photo. TRELLIS et les autres modeles image->3D produisent
un SOLIDE la ou il faudrait du verre, parce que la refraction invalide
l'hypothese de vue unique sur laquelle ils reposent — un objet transparent n'a
pas de surface visible, il emprunte l'image de ce qu'il y a derriere. Resultat:
une silhouette molle, arrondie, sans arete, et aucune cavite.

Un flacon est un objet PARAMETRIQUE. Le modeler donne ce que la reconstruction
ne donnera jamais: aretes nettes, paroi d'epaisseur reelle, vraie cavite, vrai
volume de liquide avec sa surface, tube plongeur.

Proportions relevees sur la reference (hauteur totale = 1.0, y de -0.5 a +0.5).

CLI:
  python proc_flacon_parfum_lapin.py <sortie.glb> [--niveau -0.06]
"""
from __future__ import annotations
import argparse, json, os, shutil, subprocess, sys, tempfile, time
from pathlib import Path

_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE))


def _find_blender() -> str | None:
    for sub in (_HERE.parent / "_blender").glob("blender-*"):
        for nom in ("blender", "blender.exe"):
            exe = sub / nom
            if exe.is_file():
                return str(exe)
    return shutil.which("blender") or str(Path.home() / ".local/bin/blender")


_SCRIPT = r'''
import bpy, bmesh, math, sys
from mathutils import Matrix, Vector

def _argv():
    a = sys.argv
    return a[a.index("--")+1:] if "--" in a else []
args = _argv()
OUT = args[0]
NIVEAU = float(args[1]) if len(args) > 1 else -0.06   # surface du liquide
PAROI  = float(args[2]) if len(args) > 2 else 0.045   # CRISTAL MASSIF, pas une bouteille fine

bpy.ops.wm.read_factory_settings(use_empty=True)
SC = bpy.context.scene

def mat(nom, couleur, metal, rough, transmission=0.0, ior=1.45):
    m = bpy.data.materials.new(nom); m.use_nodes = True
    b = m.node_tree.nodes.get("Principled BSDF")
    if b:
        b.inputs["Base Color"].default_value = (*couleur, 1.0)
        b.inputs["Metallic"].default_value = metal
        b.inputs["Roughness"].default_value = rough
        for cle in ("Transmission Weight", "Transmission"):
            if cle in b.inputs:
                b.inputs[cle].default_value = transmission; break
        if "IOR" in b.inputs:
            b.inputs["IOR"].default_value = ior
    return m

M_VERRE   = mat("verre",   (1.0, 1.0, 1.0),      0.0, 0.03, 1.0, 1.55)
M_OR      = mat("or",      (1.0, 0.78, 0.34),    1.0, 0.16)
M_LIQUIDE = mat("liquide", (0.86, 0.52, 0.13),   0.0, 0.10)

def objet(nom, bm, materiau):
    me = bpy.data.meshes.new(nom)
    bm.to_mesh(me); bm.free()
    ob = bpy.data.objects.new(nom, me)
    bpy.context.collection.objects.link(ob)
    ob.data.materials.append(materiau)
    return ob

def revolution(nom, profil, materiau, segments=128, fermer_haut=False):
    """Tourne un profil (rayon, hauteur) autour de l'axe Z.

    ATTENTION AXES: Blender est Z-UP, glTF est Y-UP, et l'exportateur applique
    la conversion. Il faut donc construire en Z vertical: batir en Y vertical
    sort un sujet COUCHE apres export. Convention ici: Z = hauteur, -Y = avant.
    """
    bm = bmesh.new()
    verts = [bm.verts.new((r, 0.0, z)) for r, z in profil]
    aretes = [bm.edges.new((verts[i], verts[i+1])) for i in range(len(verts)-1)]
    bmesh.ops.spin(bm, geom=verts + aretes, cent=(0, 0, 0), axis=(0, 0, 1),
                   dvec=(0, 0, 0), angle=2*math.pi, steps=segments, use_merge=True)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-5)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    return objet(nom, bm, materiau)

def ellipsoide(nom, centre, rayons, materiau, subd=4, rot=None):
    """centre = (x, avant, hauteur), rayons = (rx, r_avant, r_hauteur)."""
    centre = (centre[0], -centre[1], centre[2])
    rayons = (rayons[0], rayons[1], rayons[2])
    bm = bmesh.new()
    bmesh.ops.create_icosphere(bm, subdivisions=subd, radius=1.0)
    bmesh.ops.scale(bm, vec=Vector(rayons), verts=bm.verts)
    if rot:
        bmesh.ops.rotate(bm, cent=(0, 0, 0), matrix=rot, verts=bm.verts)
    bmesh.ops.translate(bm, vec=Vector(centre), verts=bm.verts)
    return objet(nom, bm, materiau)

def lisser(ob, angle=math.radians(32)):
    bpy.context.view_layer.objects.active = ob
    for p in ob.data.polygons:
        p.use_smooth = True
    try:
        bpy.ops.object.shade_auto_smooth(angle=angle)
    except Exception:
        pass

# ---------------------------------------------------------------- corps
# Profil du flacon: socle plat, panse renflee, epaulement, col.
# Profil du flacon: socle, panse ronde (max vers z=-0.34), epaule, col.
# Releve sur la reference: rayon exterieur max 0.205, col a 0.12.
PROFIL_CORPS = [
    (0.0000, -0.5000), (0.0700, -0.5000), (0.1150, -0.4990), (0.1450, -0.4950),
    (0.1700, -0.4870), (0.1880, -0.4740), (0.1990, -0.4560), (0.2055, -0.4300),
    (0.2090, -0.3900), (0.2100, -0.3400), (0.2085, -0.2900), (0.2040, -0.2400),
    (0.1975, -0.1950), (0.1880, -0.1550), (0.1760, -0.1200), (0.1610, -0.0900),
    (0.1450, -0.0650), (0.1320, -0.0450), (0.1240, -0.0280), (0.1205, -0.0100),
]
corps = revolution("verre_corps", PROFIL_CORPS, M_VERRE)
# Paroi d'epaisseur REELLE -> cavite interieure + rebord au col.
bpy.context.view_layer.objects.active = corps
md = corps.modifiers.new("paroi", 'SOLIDIFY')
md.thickness = PAROI; md.offset = 1.0; md.use_rim = True; md.use_even_offset = True
bpy.ops.object.modifier_apply(modifier=md.name)
# Chanfrein: c'est lui qui accroche la lumiere et donne l'arete de cristal.
mb = corps.modifiers.new("chanfrein", 'BEVEL')
mb.width = 0.0045; mb.segments = 2; mb.limit_method = 'ANGLE'; mb.angle_limit = math.radians(28)
bpy.ops.object.modifier_apply(modifier=mb.name)
lisser(corps)

# ------------------------------------------------------- pattes avant
pattes = []
for sx in (-1, 1):
    p = ellipsoide("verre_patte_%d" % (sx+1), (sx*0.104, 0.142, -0.4680),
                   (0.050, 0.100, 0.042), M_VERRE)
    lisser(p); pattes.append(p)
    h = ellipsoide("verre_hanche_%d" % (sx+1), (sx*0.178, -0.010, -0.3300),
                   (0.060, 0.088, 0.108), M_VERRE)
    lisser(h); pattes.append(h)

# ------------------------------------------------------------ tete
tete = ellipsoide("verre_tete", (0.0, 0.0, 0.1080), (0.140, 0.126, 0.132), M_VERRE, subd=5)
lisser(tete)
joues = []
for sx in (-1, 1):
    j = ellipsoide("verre_joue_%d" % (sx+1), (sx*0.084, 0.030, 0.0700),
                   (0.064, 0.064, 0.055), M_VERRE)
    lisser(j); joues.append(j)
museau = ellipsoide("verre_museau", (0.0, 0.100, 0.0680), (0.054, 0.046, 0.042), M_VERRE)
lisser(museau)

# ------------------------------------------------------------ oreilles
oreilles = []
for sx in (-1, 1):
    # inclinaison: vers l'exterieur (autour de Y), puis leger recul (autour de X)
    rot = Matrix.Rotation(math.radians(sx*9.0), 4, 'Y') @ Matrix.Rotation(math.radians(6.0), 4, 'X')
    o = ellipsoide("verre_oreille_%d" % (sx+1), (sx*0.068, -0.034, 0.3520),
                   (0.049, 0.023, 0.188), M_VERRE, subd=4, rot=rot)
    lisser(o); oreilles.append(o)

# --------------------------------------------------------- collerette or
PROFIL_COL = [
    (0.1195, -0.0060), (0.1330, -0.0050), (0.1345, 0.0010), (0.1300, 0.0060),
    (0.1330, 0.0120), (0.1345, 0.0180), (0.1300, 0.0235), (0.1210, 0.0270),
    (0.1100, 0.0280),
]
collerette = revolution("or_collerette", PROFIL_COL, M_OR, segments=128)
lisser(collerette, math.radians(22))

# ------------------------------------------------------------ gicleur or
gicleur = revolution("or_gicleur", [
    (0.000, 0.0280), (0.034, 0.0280), (0.036, 0.0330), (0.036, 0.0560),
    (0.030, 0.0590), (0.030, 0.0700), (0.000, 0.0700),
], M_OR, segments=64)
lisser(gicleur, math.radians(20))

# tube plongeur: il descend dans le liquide, on le voit a travers le verre
tube = revolution("or_tube", [
    (0.0000, -0.4150), (0.0075, -0.4150), (0.0075, 0.0280), (0.0000, 0.0280),
], M_OR, segments=32)

# ------------------------------------------------------------ yeux or
yeux = []
for sx in (-1, 1):
    y = ellipsoide("or_oeil_%d" % (sx+1), (sx*0.070, 0.086, 0.1180),
                   (0.019, 0.016, 0.021), M_OR, subd=4)
    lisser(y); yeux.append(y)

# ---------------------------------------------------------- LIQUIDE
# Meme profil que la cavite (corps moins la paroi), coupe au niveau demande,
# ferme par une surface PLANE: c'est elle qui se lit comme la surface du parfum.
def rayon_interieur(y):
    pts = PROFIL_CORPS
    for i in range(len(pts)-1):
        (r0, y0), (r1, y1) = pts[i], pts[i+1]
        if y0 <= y <= y1:
            t = 0.0 if y1 == y0 else (y - y0) / (y1 - y0)
            return max(r0 + t*(r1-r0) - PAROI*1.06, 0.001)
    return max(pts[-1][0] - PAROI*1.06, 0.001)

ys = [PROFIL_CORPS[0][1] + PAROI*1.06]
while ys[-1] < NIVEAU - 0.004:
    ys.append(ys[-1] + 0.006)
profil_liq = [(0.0, ys[0])] + [(rayon_interieur(y), y) for y in ys[1:]]
profil_liq.append((rayon_interieur(NIVEAU), NIVEAU))
profil_liq.append((0.0, NIVEAU))          # surface plane du liquide
liquide = revolution("liquide", profil_liq, M_LIQUIDE, segments=96)
lisser(liquide, math.radians(50))

bpy.ops.object.select_all(action='DESELECT')
bpy.ops.export_scene.gltf(filepath=OUT, export_format="GLB",
                          export_apply=True, export_animations=False)
print("FLACON_OK: %s" % OUT, flush=True)
'''


def fabrique(sortie: str, niveau: float = -0.06, paroi: float = 0.013) -> dict:
    t0 = time.time()
    blender = _find_blender()
    if not blender or not Path(blender).is_file():
        return {"ok": False, "error": "Blender introuvable"}
    work = Path(tempfile.mkdtemp(prefix="proc_flacon_"))
    try:
        sc = work / "build.py"
        sc.write_text(_SCRIPT, encoding="utf-8")
        brut = str(work / "brut.glb")
        cmd = [blender, "--background", "--factory-startup", "--python", str(sc),
               "--", brut, str(niveau), str(paroi)]
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=900)
        if "FLACON_OK" not in (proc.stdout or "") or not os.path.isfile(brut):
            tail = "\n".join((proc.stdout or "").splitlines()[-25:]
                             + (proc.stderr or "").splitlines()[-25:])
            return {"ok": False, "error": f"Blender exit {proc.returncode}", "log": tail}
        infos = _materiaux_valides(brut, sortie)
        return {"ok": True, "glb": os.path.abspath(sortie),
                "elapsed_s": round(time.time()-t0, 1),
                "size_bytes": os.path.getsize(sortie), **infos}
    finally:
        shutil.rmtree(work, ignore_errors=True)


def _materiaux_valides(brut: str, sortie: str) -> dict:
    """Applique les reglages verre/or/liquide valides dans les DEUX familles de
    moteurs (three.js et f3d/VTK). Voir LISEZ_MOI du dossier de sortie:
    un verre BLANC melange en alpha donne du lait, il faut une teinte legere."""
    import glb_io
    j, blob = glb_io.load(brut)
    compte = {"verre": 0, "or": 0, "liquide": 0}
    for m in j.get("materials", []):
        nom = (m.get("name") or "").lower()
        pbr = m.setdefault("pbrMetallicRoughness", {})
        ext = m.setdefault("extensions", {})
        if nom.startswith("verre"):
            compte["verre"] += 1
            m["alphaMode"] = "BLEND"; m["doubleSided"] = True
            pbr["baseColorFactor"] = [0.55, 0.62, 0.70, 0.38]
            pbr["metallicFactor"] = 0.0; pbr["roughnessFactor"] = 0.045
            ext["KHR_materials_transmission"] = {"transmissionFactor": 1.0}
            ext["KHR_materials_ior"] = {"ior": 1.58}
            ext["KHR_materials_specular"] = {"specularFactor": 1.0}
            ext["KHR_materials_volume"] = {"thicknessFactor": 0.12,
                                           "attenuationDistance": 2.5,
                                           "attenuationColor": [0.93, 0.97, 1.0]}
        elif nom.startswith("or"):
            compte["or"] += 1
            m["alphaMode"] = "OPAQUE"; m["doubleSided"] = False
            pbr["baseColorFactor"] = [1.0, 0.78, 0.34, 1.0]
            pbr["metallicFactor"] = 1.0; pbr["roughnessFactor"] = 0.16
        elif nom.startswith("liquide"):
            # OPAQUE, et c'est voulu: three.js ne peint que les objets opaques
            # dans sa cible de transmission. Un liquide transmissif serait
            # invisible a travers le verre.
            compte["liquide"] += 1
            m["alphaMode"] = "OPAQUE"; m["doubleSided"] = False
            pbr["baseColorFactor"] = [0.55, 0.20, 0.015, 1.0]
            pbr["metallicFactor"] = 0.0; pbr["roughnessFactor"] = 0.12
            ext["KHR_materials_specular"] = {"specularFactor": 1.0}
            ext["KHR_materials_ior"] = {"ior": 1.42}
            ext["KHR_materials_clearcoat"] = {"clearcoatFactor": 0.25,
                                              "clearcoatRoughnessFactor": 0.05}
    j["extensionsUsed"] = sorted(set(j.get("extensionsUsed", [])) | {
        "KHR_materials_transmission", "KHR_materials_ior",
        "KHR_materials_volume", "KHR_materials_specular", "KHR_materials_clearcoat"})
    os.makedirs(os.path.dirname(os.path.abspath(sortie)) or ".", exist_ok=True)
    glb_io.save(sortie, j, blob)
    tris = sum(j["accessors"][p["indices"]]["count"] // 3
               for me in j.get("meshes", []) for p in me.get("primitives", [])
               if p.get("indices") is not None)
    return {"materiaux": compte, "triangles": tris}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("sortie")
    ap.add_argument("--niveau", type=float, default=-0.06,
                    help="hauteur de la surface du liquide")
    ap.add_argument("--paroi", type=float, default=0.045,
                    help="epaisseur de la paroi. Le cristal de la reference est MASSIF: une paroi fine donne un pot de confiture ou l'ambre remplit toute la silhouette, sans lisere de verre clair.")
    a = ap.parse_args()
    r = fabrique(a.sortie, a.niveau, a.paroi)
    print(json.dumps(r, indent=2))
    sys.exit(0 if r.get("ok") else 1)


if __name__ == "__main__":
    main()
