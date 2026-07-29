#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""fusion_acteurs — un seul GLB livre, tous les acteurs dedans.

Sans cette etape, chaque simulation produisait son propre fichier a cote:
l'utilisateur recevait un moulin sans son eau. Ici on importe le modele
principal et tous les GLB d'acteurs animes dans une meme scene, on conserve
LEURS animations, et on exporte un fichier unique.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import tempfile
from pathlib import Path

_SCRIPT = r"""
import bpy, sys, json
args = json.loads(sys.argv[-1])
bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene
fin = 1
for i, chemin in enumerate([args["principal"]] + args["acteurs"]):
    avant = set(bpy.data.objects)
    try:
        bpy.ops.import_scene.gltf(filepath=chemin)
    except Exception as e:
        sys.stderr.write("import %s: %r\n" % (chemin, e))
        continue
    nouveaux = [o for o in bpy.data.objects if o not in avant]
    for o in nouveaux:
        o.name = "acteur%d_%s" % (i, o.name)
    for a in bpy.data.actions:
        try:
            fin = max(fin, int(a.frame_range[1]))
        except Exception:
            pass
sc.frame_start = 1
sc.frame_end = max(2, fin)
bpy.ops.object.select_all(action="SELECT")
bpy.ops.export_scene.gltf(filepath=args["sortie"], export_format="GLB",
                          export_animations=True, export_morph=True,
                          export_animation_mode="ACTIONS",
                          export_frame_range=True, export_extras=True)
print("FUSION_OK objets=%d fin=%d" % (len(bpy.data.objects), sc.frame_end))
"""


def fusionner(principal: str, acteurs: list, sortie: str,
              timeout_s: int = 2400) -> dict:
    acteurs = [a for a in (acteurs or []) if a and Path(a).is_file()]
    if not acteurs:
        return {"ok": False, "error": "aucun acteur anime a fusionner"}
    import shutil
    blender = shutil.which("blender") or "blender"
    with tempfile.TemporaryDirectory() as td:
        s = os.path.join(td, "f.py")
        Path(s).write_text(_SCRIPT, encoding="utf-8")
        payload = json.dumps({"principal": principal, "acteurs": acteurs,
                              "sortie": sortie})
        r = subprocess.run([blender, "-b", "-P", s, "--", payload],
                           capture_output=True, text=True, timeout=timeout_s)
        out = (r.stdout or "") + (r.stderr or "")
        if "FUSION_OK" not in out or not Path(sortie).is_file():
            return {"ok": False, "error": out[-250:]}
        return {"ok": True, "sortie": sortie, "acteurs": len(acteurs),
                "octets": Path(sortie).stat().st_size}


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--principal", required=True)
    ap.add_argument("--acteur", action="append", default=[])
    ap.add_argument("--sortie", required=True)
    a = ap.parse_args()
    print(json.dumps(fusionner(a.principal, a.acteur, a.sortie),
                     ensure_ascii=False))
