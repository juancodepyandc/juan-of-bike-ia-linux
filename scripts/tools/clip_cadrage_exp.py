"""Expérience: le cadrage du juge 3D écrase-t-il le score CLIP ?

Constat mesuré le 27/09 sur `train_mechanism_000` (oiseau d'horlogerie en
laiton), run 3d-20260927-033735-60b069 :

    clip_mean = 0.2833   clip_worst = 0.2271   score total = 0.2623

Les 4 vues ne montrent que 8.5 % a 14.1 % de pixels d'avant-plan, dans une
boîte qui ne couvre que 15.7 % a 27.8 % du cadre, en 256x256, sur un fond gris
monde (0.18 lineaire -> 118 en sRGB). L'objet fait donc environ 60x70 pixels :
« fine engraved metal », « rivets », « overlapping gears » sont invisibles a
cette echelle, et CLIP ne peut pas les reconnaitre.

`auto_rl/render_mesh.py:52` explique le phenomene sans le vouloir :
`radius` est la MOITIE DE LA DIAGONALE de l'AABB de TOUS les sommets. Or ce
maillage a 833 composantes connexes: quelques eclats flottants etranges
dilatent l'AABB, donc `ortho_scale = radius * 2.5` recadre sur les debris et
reduit l'objet reel. Le juge ne mesure donc pas la qualite du modele mais
en partie la taille du sujet dans le cadre.

Hypothese a tester: cadrer l'objet utile plutot que ses debris, et serrer le
cadrage, doit remonter clip_mean de maniere importante SANS toucher au modele,
au maillage, ni aux textures.

Ce script ne modifie aucun fichier de production. Il rend une copie avec un
cadrage robuste, puis note les deux jeux de vues avec le meme `ClipJudge`
que `auto_rl/judges.py`, donc comparaison a protocole egal.

Lancement: application/.venv/bin/python tools/clip_cadrage_exp.py <mesh.glb> <prompt>
"""
from __future__ import annotations

import json
import math
import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

RENDREUR = r"""
import bpy, sys, json, math
from mathutils import Vector
mesh_path, out_dir, views, size, mode = sys.argv[sys.argv.index("--")+1:]
root = bpy.path.abspath(out_dir)
import os; os.makedirs(root, exist_ok=True)
bpy.ops.object.select_all(action="SELECT"); bpy.ops.object.delete(use_global=False)
bpy.ops.import_scene.gltf(filepath=bpy.path.abspath(mesh_path))
objs = [o for o in bpy.context.scene.objects if o.type == "MESH"]
scene = bpy.context.scene
scene.render.engine = "BLENDER_WORKBENCH"
scene.display.shading.light = "STUDIO"
scene.display.shading.color_type = "TEXTURE"
scene.display.shading.show_shadows = True
scene.display.shading.show_cavity = True
scene.display.shading.background_type = "WORLD"
scene.world.color = (0.18, 0.18, 0.18)
scene.render.resolution_x = scene.render.resolution_y = int(size)
scene.render.resolution_percentage = 100
scene.render.image_settings.file_format = "PNG"

# --- deplacement de l'origine sur le centre utile -----------------------------
co = []
for o in objs:
    co.extend([o.matrix_world @ v.co for v in o.data.vertices])
pts = [v[:] for v in co]
if mode == "robuste":
    # percentiles: ignore les 2 % extremes de chaque axe, qui sont des debris
    a = np.array([[p[i] for i in range(3)] for p in pts], dtype=np.float64)
    lo = np.percentile(a, 2.0, axis=0); hi = np.percentile(a, 98.0, axis=0)
else:
    a = np.array([[p[i] for i in range(3)] for p in pts], dtype=np.float64)
    lo = a.min(axis=0); hi = a.max(axis=0)
centre_retenu = (lo + hi) / 2.0
# on rend le repere recentre: chaque objet est translate de -centre_retenu
for o in objs:
    o.matrix_world.translation = o.matrix_world.translation - Vector(centre_retenu.tolist())

bpy.ops.object.camera_add(); camera = bpy.context.object; scene.camera = camera
camera.data.type = "ORTHO"
if mode == "robuste":
    # cadre serre sur l'objet utile: 1.35x la plus grande etendue utile
    etendue = float((hi - lo).max())
    camera.data.ortho_scale = etendue * 1.35
else:
    mini = Vector(lo.tolist()); maxi = Vector(hi.tolist())
    radius = (maxi - mini).length / 2
    camera.data.ortho_scale = radius * 2.5
for i in range(int(views)):
    ang = i * 2 * math.pi / int(views)
    # on vise le point (0,0,0) du repere recentre
    camera.location = Vector((math.cos(ang), math.sin(ang), 0.55)) * radius_view(camera)
    camera.rotation_euler = (Vector((0,0,0)) - camera.location).to_track_quat("-Z","Y").to_euler()
    scene.render.filepath = bpy.path.abspath(os.path.join(root, "view_%02d.png" % i))
    bpy.ops.render.render(write_still=True)
print("RENDU_OK")
"""

# `radius_view` est injecte: on lit l'ortho_scale pour placer la camera a une
# distance fixe, ce qui evite de dependre de la variable Python du driver.
RENDREUR = RENDREUR.replace(
    "camera.location = Vector((math.cos(ang), math.sin(ang), 0.55)) * radius_view(camera)",
    "camera.location = Vector((math.cos(ang), math.sin(ang), 0.55)) * (camera.data.ortho_scale * 3.0)",
)
RENDREUR = "import numpy as np\n" + RENDREUR


def _blender() -> str:
    sys.path.insert(0, str(ROOT / "application/python-services"))
    from perfection_gate import _blender as b
    return b()


def rendre(mesh: str, out: Path, mode: str, vues: int = 4, taille: int = 256) -> list:
    out.mkdir(parents=True, exist_ok=True)
    script = Path(tempfile.mkstemp(suffix=".py")[1])
    script.write_text(RENDREUR, encoding="utf-8")
    r = subprocess.run(
        [_blender(), "-b", "--python", str(script), "--", str(mesh), str(out),
         str(vues), str(taille), mode],
        capture_output=True, text=True, timeout=1800)
    script.unlink(missing_ok=True)
    files = sorted(out.glob("view_*.png"))
    if len(files) != vues:
        raise RuntimeError("rendu incomplet: %s" % (r.stdout or "")[-200:])
    return files


def couverture(fichiers: list) -> dict:
    parts, boites = [], []
    for f in fichiers:
        g = np.array(Image.open(f).convert("RGB"), dtype=np.float32).mean(axis=2)
        coin = np.concatenate([g[:12, :12].ravel(), g[:12, -12:].ravel(),
                               g[-12:, :12].ravel(), g[-12:, -12:].ravel()])
        fond, sd = np.median(coin), np.std(coin)
        fg = np.abs(g - fond) > max(8.0, 3 * sd)
        ys, xs = np.nonzero(fg)
        parts.append(fg.mean() * 100)
        if len(xs):
            boites.append((xs.max() - xs.min() + 1) * (ys.max() - ys.min() + 1)
                          / fg.size * 100)
    return {"avant_plan_pct": round(float(np.mean(parts)), 2),
            "bbox_pct": round(float(np.mean(boites)), 2) if boites else 0.0}


def main() -> int:
    mesh, prompt = sys.argv[1], sys.argv[2]
    out = Path(tempfile.mkdtemp(prefix="cadrage_", dir="/home/juan/AuroraIA/Outputs/auto_rl/diagnostics"))
    from auto_rl.backends import local_snapshot
    from auto_rl.config import defaults
    from auto_rl.judges import ClipJudge
    clip = ClipJudge(local_snapshot(defaults("3d")["models"]["clip"]), None)
    resultat = {"mesh": mesh, "prompt": prompt, "vues": 4, "taille": 256}
    for mode in ("actuel", "robuste"):
        d = out / mode
        f = rendre(mesh, d, mode)
        with Image.open(f[0]) as im0:
            resultat.setdefault("dimensions", im0.size)
        sc = clip.scores([Image.open(p).convert("RGB") for p in f], prompt)
        cov = couverture(f)
        resultat[mode] = {
            "clip_par_vue": [round(v, 4) for v in sc],
            "clip_mean": round(float(np.mean(sc)), 4),
            "clip_worst": round(round(min(sc), 4), 4),
            **cov,
        }
    a, b = resultat["actuel"], resultat["robuste"]
    resultat["delta"] = {
        "clip_mean": round(b["clip_mean"] - a["clip_mean"], 4),
        "clip_worst": round(b["clip_worst"] - a["clip_worst"], 4),
        "avant_plan_pct": round(b["avant_plan_pct"] - a["avant_plan_pct"], 2),
        "score_total_estime": round(
            0.45 * 0.2617 + 0.35 * b["clip_mean"] + 0.2 * b["clip_worst"], 4),
        "score_total_actuel": round(
            0.45 * 0.2617 + 0.35 * a["clip_mean"] + 0.2 * a["clip_worst"], 4),
    }
    (ROOT / "Outputs/auto_rl/diagnostics/clip_cadrage_exp.json").write_text(
        json.dumps(resultat, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(resultat, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
