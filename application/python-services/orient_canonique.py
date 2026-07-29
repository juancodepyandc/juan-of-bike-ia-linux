#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""orient_canonique — met le sujet FACE à la convention, cuit dans les sommets.

Le defaut paye deux fois: le sujet reconstruit regarde une direction
arbitraire; un pivot glTF ajoute apres coup est aplati par l'aller-retour FBX
de MIA -> planches et viewer montrent le DOS, la danse est illisible
(constate par l'utilisateur). La bonne strategie: canoniser UNE FOIS, a la
source, dans les SOMMETS — plus rien en aval ne peut le perdre.

Methode (generale, aucun a priori de sujet):
  1. Blender rend 4 vues yaw (0/90/180/270) du GLB texture;
  2. le VLM designe la vue qui montre la FACE (visage/avant du sujet);
  3. Blender tourne les racines du yaw correspondant et APPLIQUE la
     transformation (sommets + armatures), puis re-exporte SUR PLACE.

Usage: python orient_canonique.py --glb modele.glb
Sortie JSON: {ok, vue_face, yaw_applique_deg}
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

PS = Path(__file__).resolve().parent


def _blender() -> str:
    import shutil
    return shutil.which("blender") or "blender"


_BAKE = r"""
import bpy, math, sys
import mathutils
glb, yaw_deg = sys.argv[-2], float(sys.argv[-1])
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=glb)
sc = bpy.context.scene
racines = [o for o in sc.objects if o.parent is None]
rot = mathutils.Matrix.Rotation(math.radians(yaw_deg), 4, "Z")
for o in racines:
    o.matrix_world = rot @ o.matrix_world
bpy.ops.object.select_all(action="SELECT")
bpy.context.view_layer.objects.active = racines[0]
bpy.ops.object.transform_apply(location=False, rotation=True, scale=False)
bpy.ops.object.select_all(action="SELECT")
bpy.ops.export_scene.gltf(filepath=glb, export_animations=True,
                          export_animation_mode="ACTIONS")
print("BAKE_OK")
"""


def orienter(glb: str) -> dict:
    glb = str(Path(glb).resolve())
    with tempfile.TemporaryDirectory(prefix="orient_") as td:
        r = subprocess.run([_blender(), "-b", "-P",
                            str(PS / "orient_rendu_bpy.py"), "--", glb, td],
                           capture_output=True, text=True, timeout=900)
        if "VUES4_OK" not in (r.stdout or ""):
            return {"ok": False, "error": "rendu 4 vues echoue: %s"
                    % (r.stdout or r.stderr or "")[-300:]}
        azs = (270, 0, 90, 180)
        vues = [os.path.join(td, "az%03d.png" % a) for a in azs]
        sys.path.insert(0, str(PS))
        try:
            from vlm_judge import ask_vlm
            verdict = ask_vlm(
                vues,
                "Voici le MEME sujet 3D vu sous 4 angles (images 1 a 4, "
                "tournees de 90 degres). Quelle image montre sa FACE — "
                "visage, yeux, avant du sujet — le plus directement ? "
                "Reponds STRICTEMENT l'index 1, 2, 3 ou 4.",
                schema_hint='{"vue_face": 1|2|3|4, "raison": "..."}',
                timeout=120)
            iv = int(verdict.get("vue_face"))
            if iv not in (1, 2, 3, 4):
                raise ValueError(iv)
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "error": "VLM indisponible/indecis: %r" % (exc,)}
        # la vue retenue est prise depuis l'azimut azs[iv-1]; la camera des
        # planches est a 270 deg: on tourne le sujet pour que sa face pointe
        # vers elle.
        yaw = (270.0 - azs[iv - 1]) % 360.0
        if yaw == 0.0:
            return {"ok": True, "vue_face": iv, "yaw_applique_deg": 0.0}
        b = subprocess.run([_blender(), "-b", "--python-expr", _BAKE,
                            "--", glb, str(yaw)],
                           capture_output=True, text=True, timeout=1800)
        if "BAKE_OK" not in (b.stdout or ""):
            return {"ok": False, "error": "bake yaw echoue: %s"
                    % (b.stdout or b.stderr or "")[-200:]}
        return {"ok": True, "vue_face": iv, "yaw_applique_deg": yaw}


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--glb", required=True)
    a = ap.parse_args()
    print(json.dumps(orienter(a.glb), ensure_ascii=False))
