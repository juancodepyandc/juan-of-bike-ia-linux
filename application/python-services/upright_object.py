"""upright_object.py — redresse un objet genere dont l'orientation est arbitraire.

Le generateur ne garantit aucune convention d'axe: une chaise sort couchee, une
tasse sur le flanc. Composer une scene par-dessus n'a alors aucun sens (on assied
un personnage sur une chaise renversee).

On ne peut PAS coder la regle en dur ("une chaise a ses pieds en bas"): elle ne
generaliserait a rien d'autre. On ne peut pas non plus la deduire de la geometrie
seule - "poser l'objet sur sa plus grande face" couche justement une chaise sur son
dossier, et l'axe principal d'une ACP ne dit rien du haut et du bas.

C'est un probleme de SENS COMMUN, pas de geometrie: on le pose donc au modele de
vision, qui sait a quoi ressemble une chaise debout. On rend l'objet sous les 6
orientations canoniques (chaque axe +/- porte le "haut") et on lui demande laquelle
montre l'objet dans sa position de repos naturelle. La rotation retenue est ensuite
appliquee au GLB.

Usage:
    python upright_object.py <in.glb> <out.glb> [--desc "une chaise"]
"""

from __future__ import annotations

import base64
import re
import json
import os
import shutil
import subprocess
import sys
import tempfile

_HERE = os.path.dirname(os.path.abspath(__file__))
OLLAMA = os.environ.get("AURORA_OLLAMA_URL", "http://127.0.0.1:11434")
VLM = os.environ.get("AURORA_VLM_MODEL", "qwen3-vl:30b")

# Les 6 orientations canoniques: quelle rotation amene chaque axe du modele sur le
# +Z du monde. (rx, ry, rz) en degres, appliquees dans cet ordre.
_CANDIDATES = [
    ("tel quel",              (0, 0, 0)),
    ("retourne",              (180, 0, 0)),
    ("bascule vers l'avant",  (90, 0, 0)),
    ("bascule vers l'arriere", (-90, 0, 0)),
    ("couche a droite",       (0, 90, 0)),
    ("couche a gauche",       (0, -90, 0)),
]


_BPY_RENDER = r'''
import bpy, json, math, os, sys
from mathutils import Vector

argv = sys.argv[sys.argv.index("--") + 1:]
GLB, OUTDIR, CANDS = argv[0], argv[1], json.loads(argv[2])

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=GLB)
objs = [o for o in bpy.context.scene.objects if o.type in ("MESH", "ARMATURE")]
if not objs:
    print("UPRIGHT_FAIL aucun objet"); sys.exit(3)

# Les RACINES ne sont pas forcement des meshes: l'import glTF interpose une EMPTY
# ("world"). Ne parenter que les MESH/ARMATURE laisserait la hierarchie intacte et
# la rotation sans effet - on rendrait 6 fois la MEME image.
root = bpy.data.objects.new("AuroraUprightRoot", None)
bpy.context.scene.collection.objects.link(root)
for o in list(bpy.context.scene.objects):
    if o.parent is None and o is not root:
        o.parent = root

scn = bpy.context.scene
scn.render.engine = "BLENDER_EEVEE_NEXT" if "BLENDER_EEVEE_NEXT" in [
    i.identifier for i in bpy.types.RenderSettings.bl_rna.properties["engine"].enum_items
] else "BLENDER_EEVEE"
scn.render.resolution_x = scn.render.resolution_y = 512
scn.render.image_settings.file_format = "PNG"
scn.render.film_transparent = False
scn.world = bpy.data.worlds.new("w")
scn.world.use_nodes = True
scn.world.node_tree.nodes["Background"].inputs[0].default_value = (0.9, 0.9, 0.9, 1)
light = bpy.data.objects.new("k", bpy.data.lights.new("k", type="SUN"))
light.data.energy = 3.0
light.rotation_euler = (math.radians(50), 0, math.radians(35))
scn.collection.objects.link(light)

cam_d = bpy.data.cameras.new("cam"); cam_d.type = "ORTHO"
cam = bpy.data.objects.new("cam", cam_d); scn.collection.objects.link(cam)
scn.camera = cam

out = []
for i, (name, rot) in enumerate(CANDS):
    root.rotation_euler = tuple(math.radians(a) for a in rot)
    bpy.context.view_layer.update()
    lo = Vector((1e9, 1e9, 1e9)); hi = Vector((-1e9, -1e9, -1e9))
    for o in objs:
        if o.type != "MESH":
            continue
        for c in o.bound_box:
            w = o.matrix_world @ Vector(c)
            for k in range(3):
                lo[k] = min(lo[k], w[k]); hi[k] = max(hi[k], w[k])
    ctr = (lo + hi) * 0.5
    span = max((hi - lo).x, (hi - lo).y, (hi - lo).z) or 1.0
    # vue de 3/4 legerement en contre-plongee: c'est celle ou un humain juge le
    # mieux si un objet "tient debout" (une vue de face pure est ambigue).
    d = Vector((0.72, -0.62, 0.31)).normalized()
    cam_d.ortho_scale = span * 1.25
    cam.location = ctr + d * (span * 3.0)
    cam.rotation_euler = d.to_track_quat("Z", "Y").to_euler()
    bpy.context.view_layer.update()
    png = os.path.join(OUTDIR, "cand_%d.png" % i)
    scn.render.filepath = png
    bpy.ops.render.render(write_still=True)
    out.append({"i": i, "name": name, "rot": rot, "png": png})

open(os.path.join(OUTDIR, "cands.json"), "w").write(json.dumps(out))
print("UPRIGHT_RENDER_OK")
'''


_BPY_APPLY = r'''
import bpy, json, math, sys
from mathutils import Euler

argv = sys.argv[sys.argv.index("--") + 1:]
GLB, OUT_GLB, ROT = argv[0], argv[1], json.loads(argv[2])

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=GLB)

# PIEGE glTF: la conversion Z-up <-> Y-up de l'exportateur EST une rotation de 90
# deg autour de X. Poser la rotation sur la transformation d'un noeud la lui fait
# absorber (verifie: un modele bascule de 90 deg ressortait DEBOUT). On CUIT donc
# la rotation dans les sommets - aucune convention d'axe ne peut plus l'annuler.
R = Euler([math.radians(a) for a in ROT], "XYZ").to_matrix().to_4x4()
done = set()
for o in bpy.context.scene.objects:
    if o.type != "MESH" or o.data.name in done:
        continue
    M = o.matrix_world
    o.data.transform(M.inverted() @ R @ M)
    done.add(o.data.name)
bpy.context.view_layer.update()
bpy.ops.export_scene.gltf(filepath=OUT_GLB, export_format="GLB")
print("UPRIGHT_APPLY_OK")
'''


def _find_blender() -> str | None:
    env = os.environ.get("AURORA_BLENDER")
    if env and os.path.exists(env):
        return env
    for c in ("/home/juan/.local/bin/blender", "/usr/bin/blender", "blender"):
        p = shutil.which(c) if not os.path.isabs(c) else (c if os.path.exists(c) else None)
        if p:
            return p
    return None


def _blender(script: str, args: list, tag: str) -> str:
    b = _find_blender()
    if not b:
        raise RuntimeError("blender introuvable")
    with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False) as f:
        f.write(script)
        sp = f.name
    r = subprocess.run([b, "-b", "--factory-startup", "-noaudio", "-P", sp, "--"] + args,
                       capture_output=True, text=True, timeout=1800)
    os.unlink(sp)
    log = (r.stdout or "") + (r.stderr or "")
    if tag not in log:
        raise RuntimeError("%s echoue: %s" % (tag, log[-300:]))
    return log


def _contact_sheet(cands: list, path: str) -> None:
    """Assemble les candidats en UNE planche-contact numerotee.

    Envoyer 6 images separees ne marche pas: le modele ne les met pas en regard et
    repond au hasard (verifie: il choisissait l'index 0 avec une raison vide, alors
    que l'objet y etait manifestement couche). Une planche unique lui permet de
    COMPARER, ce qui est precisement la tache demandee.
    """
    import cv2
    import numpy as np

    tiles = []
    for i, c in enumerate(cands):
        im = cv2.resize(cv2.imread(c["png"]), (320, 320))
        cv2.rectangle(im, (0, 0), (319, 319), (60, 60, 60), 2)
        cv2.rectangle(im, (4, 4), (58, 44), (255, 255, 255), -1)
        cv2.putText(im, str(i), (14, 36), cv2.FONT_HERSHEY_SIMPLEX, 1.2,
                    (0, 0, 200), 3)
        tiles.append(im)
    rows = [np.hstack(tiles[0:3]), np.hstack(tiles[3:6])]
    cv2.imwrite(path, np.vstack(rows))


def _ask_vlm(cands: list, desc: str, sheet: str) -> tuple[int, str]:
    """Demande au modele de vision laquelle des vues montre l'objet DEBOUT."""
    import urllib.request

    _contact_sheet(cands, sheet)
    with open(sheet, "rb") as fh:
        img = base64.b64encode(fh.read()).decode()
    what = desc.strip() or "cet objet"
    prompt = (
        "Cette image est une planche de %d vignettes numerotees (0 a %d, de gauche a "
        "droite puis ligne suivante). Ce sont des rendus du MEME objet (%s), chacun "
        "dans une ORIENTATION differente.\n"
        "Le sol est horizontal, en bas de chaque vignette.\n"
        "Question: dans QUELLE vignette l'objet est-il dans sa position NATURELLE de "
        "repos, telle qu'il se tiendrait vraiment sur un sol ? (une chaise sur ses "
        "pieds et non sur son dossier, une tasse sur son fond, une personne debout "
        "sur ses pieds et non couchee ni la tete en bas). Ignore la couleur et la "
        "qualite: SEULE l'orientation compte.\n"
        "Reponds par le SEUL numero de la vignette, rien d'autre."
        % (len(cands), len(cands) - 1, what)
    )
    # PAS de `format: json` ici: ce modele renvoie alors une reponse VIDE (verifie).
    # En texte libre il repond juste. On lit donc le premier entier de sa reponse.
    body = json.dumps({
        "model": VLM, "prompt": prompt, "images": [img], "stream": False,
        "keep_alive": 0, "options": {"temperature": 0.0},
    }).encode()
    req = urllib.request.Request(OLLAMA + "/api/generate", data=body,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=600) as r:
        data = json.loads(r.read().decode())
    raw = (data.get("response") or "").strip()
    m = re.search(r"\d+", raw)
    if not m:
        return -1, "reponse sans numero: %r" % raw[:60]
    idx = int(m.group())
    if not 0 <= idx < len(cands):
        return -1, "numero hors bornes (%d)" % idx
    return idx, raw[:40]


def _etendues(glb: str):
    """Etendues X/Y/Z du maillage, lues dans les accesseurs glTF (Y = hauteur)."""
    try:
        from pygltflib import GLTF2
        g = GLTF2().load(glb)
        lo = [1e30] * 3
        hi = [-1e30] * 3
        for m in (g.meshes or []):
            for p in m.primitives:
                a = g.accessors[p.attributes.POSITION]
                if not a.min or not a.max:
                    continue
                for i in range(3):
                    lo[i] = min(lo[i], float(a.min[i]))
                    hi[i] = max(hi[i], float(a.max[i]))
        if lo[0] > 1e29:
            return None
        return [hi[i] - lo[i] for i in range(3)]
    except Exception:  # noqa: BLE001
        return None


def _est_couche(ext) -> bool:
    """Un objet est COUCHE quand sa hauteur est sa plus petite dimension.

    Un moniteur pose a plat: hauteur 0.11 contre 1.90 et 1.16 -> couche.
    Le meme moniteur debout: hauteur 1.16, la plus petite etant l'epaisseur
    0.11 -> deja droit. C'est le seul cas ou un redressement a un sens.
    """
    if not ext:
        return True                      # dans le doute on laisse juger le VLM
    return ext[1] <= min(ext[0], ext[2]) + 1e-9


def upright(glb: str, out_glb: str, desc: str = "", workdir: str | None = None) -> dict:
    wd = workdir or tempfile.mkdtemp(prefix="upright_")
    os.makedirs(wd, exist_ok=True)
    _blender(_BPY_RENDER, [glb, wd, json.dumps(_CANDIDATES)], "UPRIGHT_RENDER_OK")
    cands = json.loads(open(os.path.join(wd, "cands.json")).read())

    try:
        idx, why = _ask_vlm(cands, desc, os.path.join(wd, "planche.png"))
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": "VLM indisponible: %r" % exc}
    if idx < 0:
        # NE PAS retomber silencieusement sur l'index 0: c'est precisement ce qui
        # avait masque le bug (le module repondait "deja droit" sur un objet couche).
        # Mieux vaut ne rien faire et le DIRE que de tourner l'objet au hasard.
        return {"ok": False, "error": "le modele de vision n'a pas tranche (%s)" % why}

    rot = cands[idx]["rot"]
    # GARDE: ne redresser QUE ce qui est couche. Un objet deja debout n'a rien
    # a gagner d'une bascule, et il a tout a perdre — mesure du 27/08 sur le
    # studio VIZION: l'ecran sortait juste (1.90 large x 1.16 haut), le VLM a
    # choisi une bascule de 90 deg et l'a livre en PORTRAIT (1.16 x 1.90),
    # seul objet de la scene, tourne. Une bascule qui change l'axe VERTICAL
    # d'un objet deja debout est donc refusee; on prefere ne rien faire et le
    # dire, comme pour le VLM muet juste au-dessus.
    _ext = _etendues(glb)
    _bascule_verticale = any(abs(float(r)) > 1e-6 for r in (rot[0], rot[2]))
    if _bascule_verticale and not _est_couche(_ext):
        return {"ok": True, "already_upright": True, "choice": cands[idx]["name"],
                "reason": ("bascule %s REFUSEE: l'objet est deja debout "
                           "(etendues %s, hauteur non minimale) — %s"
                           % (rot, [round(x, 2) for x in (_ext or [])], why)),
                "output": glb}
    if rot == [0, 0, 0] or tuple(rot) == (0, 0, 0):
        # deja droit: on ne reexporte pas (un aller-retour GLB coute et peut degrader)
        return {"ok": True, "already_upright": True, "choice": cands[idx]["name"],
                "reason": why, "output": glb}
    _blender(_BPY_APPLY, [glb, out_glb, json.dumps(rot)], "UPRIGHT_APPLY_OK")
    return {"ok": True, "already_upright": False, "choice": cands[idx]["name"],
            "rotation_deg": rot, "reason": why, "output": out_glb}


def main() -> int:
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("glb")
    ap.add_argument("output")
    ap.add_argument("--desc", default="")
    ap.add_argument("--workdir", default=None)
    a = ap.parse_args()
    try:
        r = upright(a.glb, a.output, a.desc, a.workdir)
    except Exception as exc:  # noqa: BLE001
        r = {"ok": False, "error": str(exc)}
    print("AURORA_UPRIGHT_RESULT " + json.dumps(r, ensure_ascii=False))
    return 0 if r.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
