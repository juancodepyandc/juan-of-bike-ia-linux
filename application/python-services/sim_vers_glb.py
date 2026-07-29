#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""sim_vers_glb — une simulation devient une ANIMATION dans le GLB livré.

Maillon manquant (27/07): Houdini produisait de vraies séquences
(`.bgeo.sc` par image) que RIEN ne convertissait — l'eau et le sable étaient
simulés puis perdus. Ici on transforme une séquence de nuages de points en
animation glTF standard, lisible par three.js sans extension exotique.

Deux représentations, choisies automatiquement:
  * MORPH TARGETS quand le nombre de particules est constant (granulaire):
    un seul maillage, une forme par image, animation de poids. C'est le
    format le plus compact et le mieux supporté.
  * SÉQUENCE DE VISIBILITÉ quand le compte varie (liquide à émission
    continue): un maillage par image, rendu visible tour à tour par une
    animation d'échelle (0 -> 1). Aucune extension requise.

Chaque particule devient un petit tétraèdre (4 sommets): assez pour être vue
et ombrée, 3x moins lourd qu'un cube.

Usage:
    python sim_vers_glb.py --sequence <dossier_bgeo> --output eau.glb
                           [--rayon 0.012] [--fps 24] [--max-particules 6000]
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

HFS = Path(os.environ.get(
    "AURORA_HFS",
    Path.home() / ".local/share/auroraia/external/hfs22.0.368"))

_LECTEUR = r"""
import hou, sys, os, json
dossier, sortie, maxp = sys.argv[1], sys.argv[2], int(sys.argv[3])
fichiers = sorted(f for f in os.listdir(dossier) if f.endswith(".bgeo.sc"))
frames = []
for nom in fichiers:
    g = hou.Geometry()
    g.loadFromFile(os.path.join(dossier, nom))
    pts = [list(p.position()) for p in g.points()]
    if maxp and len(pts) > maxp:
        pas = max(1, len(pts) // maxp)
        pts = pts[::pas][:maxp]
    frames.append(pts)
with open(sortie, "w") as fh:
    json.dump(frames, fh)
print("LECTURE_OK frames=%d" % len(frames))
"""

_BLENDER = r"""
import bpy, json, sys, math
positions_json, out_glb, rayon, fps = sys.argv[-4], sys.argv[-3], float(sys.argv[-2]), int(sys.argv[-1])
frames = json.load(open(positions_json))
bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene
sc.render.fps = fps
sc.frame_start = 1
sc.frame_end = max(2, len(frames))
comptes = {len(f) for f in frames}
constant = len(comptes) == 1 and frames and len(frames[0]) > 0

def tetra(cx, cy, cz, r):
    return [(cx + r, cy - r, cz - r), (cx - r, cy + r, cz - r),
            (cx - r, cy - r, cz + r), (cx + r, cy + r, cz + r)]
FACES = [(0, 1, 2), (0, 1, 3), (0, 2, 3), (1, 2, 3)]

def maillage_de(pts, nom):
    verts, faces = [], []
    for i, (x, y, z) in enumerate(pts):
        base = len(verts)
        verts.extend(tetra(x, y, z, rayon))
        faces.extend([(base + a, base + b, base + c) for a, b, c in FACES])
    me = bpy.data.meshes.new(nom)
    me.from_pydata(verts, [], faces)
    me.update()
    ob = bpy.data.objects.new(nom, me)
    sc.collection.objects.link(ob)
    return ob

if constant:
    # MORPH TARGETS: un maillage, une forme par image
    ob = maillage_de(frames[0], "simulation")
    ob.shape_key_add(name="base", from_mix=False)
    for i, pts in enumerate(frames):
        sk = ob.shape_key_add(name="f%04d" % i, from_mix=False)
        for j, (x, y, z) in enumerate(pts):
            for k, co in enumerate(tetra(x, y, z, rayon)):
                sk.data[j * 4 + k].co = co
    for i in range(len(frames)):
        sk = ob.data.shape_keys.key_blocks["f%04d" % i]
        for f_ in range(1, len(frames) + 1):
            sk.value = 1.0 if f_ == i + 1 else 0.0
            sk.keyframe_insert("value", frame=f_)
    mode = "morph"
else:
    # SEQUENCE: un maillage par image, echelle 0/1 pour n'en montrer qu'un
    for i, pts in enumerate(frames):
        ob = maillage_de(pts, "sim_%04d" % i)
        for f_ in range(1, len(frames) + 1):
            s = 1.0 if f_ == i + 1 else 0.0
            ob.scale = (s, s, s)
            ob.keyframe_insert("scale", frame=f_)
    mode = "sequence"

for ob in sc.objects:
    if ob.type == "MESH" and not ob.data.materials:
        m = bpy.data.materials.new("sim")
        m.use_nodes = True
        ob.data.materials.append(m)

bpy.ops.object.select_all(action="SELECT")
bpy.ops.export_scene.gltf(filepath=out_glb, export_format="GLB",
                          export_animations=True, export_morph=True,
                          export_animation_mode="ACTIONS",
                          export_frame_range=True)
print("SIM_GLB_OK mode=%s frames=%d" % (mode, len(frames)))
"""


def _blender() -> str:
    import shutil
    return shutil.which("blender") or "blender"


def convertir(dossier_sequence: str, sortie_glb: str, rayon: float = 0.012,
              fps: int = 24, max_particules: int = 6000,
              timeout_s: int = 2400) -> dict:
    src = Path(dossier_sequence)
    fichiers = sorted(src.glob("*.bgeo.sc"))
    if not fichiers:
        return {"ok": False, "error": "aucune image dans %s" % src}
    hy = HFS / "bin" / "hython"
    if not hy.is_file():
        return {"ok": False, "error": "hython absent (%s)" % hy}
    with tempfile.TemporaryDirectory() as td:
        pos = os.path.join(td, "positions.json")
        s1 = os.path.join(td, "lect.py")
        Path(s1).write_text(_LECTEUR, encoding="utf-8")
        r1 = subprocess.run([str(hy), s1, str(src), pos, str(max_particules)],
                            capture_output=True, text=True, timeout=timeout_s)
        if "LECTURE_OK" not in (r1.stdout or ""):
            return {"ok": False, "error": "lecture bgeo: %s"
                    % (r1.stderr or r1.stdout or "")[-250:]}
        s2 = os.path.join(td, "bld.py")
        Path(s2).write_text(_BLENDER, encoding="utf-8")
        r2 = subprocess.run([_blender(), "-b", "-P", s2, "--",
                             pos, str(sortie_glb), str(rayon), str(fps)],
                            capture_output=True, text=True, timeout=timeout_s)
        out = (r2.stdout or "") + (r2.stderr or "")
        if "SIM_GLB_OK" not in out or not Path(sortie_glb).is_file():
            return {"ok": False, "error": "conversion glTF: %s" % out[-250:]}
        import re
        m = re.search(r"SIM_GLB_OK mode=(\w+) frames=(\d+)", out)
        return {"ok": True, "sortie": str(sortie_glb),
                "mode": m.group(1) if m else "?",
                "frames": int(m.group(2)) if m else len(fichiers),
                "images_source": len(fichiers),
                "octets": Path(sortie_glb).stat().st_size}


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--sequence", required=True)
    ap.add_argument("--output", required=True)
    ap.add_argument("--rayon", type=float, default=0.012)
    ap.add_argument("--fps", type=int, default=24)
    ap.add_argument("--max-particules", type=int, default=6000)
    a = ap.parse_args()
    print(json.dumps(convertir(a.sequence, a.output, a.rayon, a.fps,
                               a.max_particules), ensure_ascii=False))
