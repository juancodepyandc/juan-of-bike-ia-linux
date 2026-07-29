#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""poussiere_capillaire — retire les confettis flottants d'un maillage TRELLIS.

Mesure sur le guerrier: les meches de cheveux/barbe SOUS la resolution de la
grille (brins 0.5-2 mm, cellule 1.6 mm) sortent en ~8 400 ilots fermes de
quelques faces (mediane: 2) qui flottent autour de la tete — 0.6 % de l'aire,
100 % du bruit visuel. Ce ne sont PAS des trous (zero bord ouvert apres
soudure): remplir ne sert a rien, il faut BALAYER.

On supprime les composantes connexes de moins de N faces (defaut 100). L'ile
principale (94 % du maillage) et les structures legitimes (anneaux de cotte de
mailles: rattaches a l'ile) ne sont pas touchees.

Usage:
    python poussiere_capillaire.py --input mesh.glb --output mesh_propre.glb
                                   [--min-faces 100]
"""

from __future__ import annotations

import argparse
import json


def balayer(input_glb: str, output_glb: str, min_faces: int = 100) -> dict:
    import numpy as np
    import trimesh

    scene = trimesh.load(input_glb, process=False)
    if isinstance(scene, trimesh.Scene):
        geoms = list(scene.geometry.items())
    else:
        geoms = [("mesh", scene)]

    total_avant = 0
    total_apres = 0
    ilots_retires = 0
    for name, mesh in geoms:
        if not isinstance(mesh, trimesh.Trimesh) or len(mesh.faces) == 0:
            continue
        total_avant += len(mesh.faces)
        # composantes connexes PAR ARETES DE FACES sur le maillage tel quel
        # (les doublons de coutures UV separent des iles artificielles: on
        # soude d'abord une COPIE pour etablir la connexite reelle, puis on
        # reporte le verdict sur les faces d'origine — la geometrie livree
        # n'est jamais re-soudee, les UV restent intacts).
        ref = mesh.copy()
        ref.merge_vertices(merge_tex=True, merge_norm=True)
        comps = trimesh.graph.connected_components(
            ref.face_adjacency, min_len=0, nodes=np.arange(len(ref.faces)))
        garder = np.ones(len(mesh.faces), dtype=bool)
        for comp in comps:
            if len(comp) < min_faces:
                garder[comp] = False
                ilots_retires += 1
        if not garder.all():
            mesh.update_faces(garder)
            mesh.remove_unreferenced_vertices()
        total_apres += len(mesh.faces)

    if isinstance(scene, trimesh.Scene):
        scene.export(output_glb)
    else:
        geoms[0][1].export(output_glb)
    return {"ok": True, "faces_avant": total_avant, "faces_apres": total_apres,
            "ilots_retires": ilots_retires,
            "aire_retiree_pct": round(100.0 * (total_avant - total_apres)
                                      / max(total_avant, 1), 2),
            "fichier": output_glb}


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True)
    ap.add_argument("--output", required=True)
    ap.add_argument("--min-faces", type=int, default=100)
    a = ap.parse_args()
    print(json.dumps(balayer(a.input, a.output, a.min_faces), ensure_ascii=False))
