#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Mesures comportementales des services Python 3D.

Meme contrat que `conformanceMesures.mjs` cote TypeScript : chaque mesure rend
un entier « nombre de defauts », 0 = conforme, et n appelle que des fonctions
deja exportees AVANT correction — c est ce qui permet de faire tourner le meme
banc sur les deux etats du code et de comparer des NOMBRES.

Sortie : une ligne JSON sur stdout.
    .venv/bin/python scripts/conformance_mesures.py
"""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

RACINE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RACINE / "python-services"))

import numpy as np  # noqa: E402


def _humanoide():
    """Trois cylindres bien separes — pas d auto-intersection parasite."""
    def cyl(cx, cy, z0, z1, r=0.06, n=16, k=6):
        pts = []
        for z in np.linspace(z0, z1, k):
            for a in np.linspace(0.0, 2.0 * np.pi, n, endpoint=False):
                pts.append([cx + r * np.cos(a), cy + r * np.sin(a), z])
        return np.array(pts, dtype=float)
    jl, jr, to = cyl(-0.15, 0, 0, 0.9), cyl(0.15, 0, 0, 0.9), cyl(0, 0, 0.9, 1.7, r=0.18)
    rest = np.vstack([jl, jr, to])
    parts = np.array([0] * len(jl) + [1] * len(jr) + [2] * len(to))
    aretes, base = [], 0
    for bloc in (jl, jr, to):
        for i in range(len(bloc) - 1):
            aretes.append([base + i, base + i + 1])
        base += len(bloc)
    return rest, np.array(aretes), parts


def mesures() -> list[dict]:
    out: list[dict] = []

    def ajoute(module, quoi, defauts, detail):
        out.append({"module": module, "quoi": quoi, "defauts": int(defauts), "detail": detail})

    # --- 1. Metriques d animation : le fige est-il distingue du mouvant ? ---
    try:
        import anim_metrics as AM
        rest, aretes, parts = _humanoide()
        F = 48

        def prise(verts):
            return {"fps": 24, "verts": verts, "rest": rest, "edges": aretes,
                    "part_labels": parts, "up_axis": "Z", "ground": 0.0,
                    "adjacent_parts": [(0, 2), (1, 2)]}

        fige = np.tile(rest, (F, 1, 1))
        t = np.arange(F) / 24.0
        mouvant = np.tile(rest, (F, 1, 1)).copy()
        mouvant[:, :, 0] += (0.12 * np.sin(2 * np.pi * t))[:, None]

        a = AM.evaluate(prise(fige), "humanoid")
        b = AM.evaluate(prise(mouvant), "humanoid")
        defauts = 0
        details = []
        if a["passed"]:
            defauts += 1
            details.append("un personnage FIGE est accepte")
        if not b["passed"]:
            defauts += 1
            details.append(f"un personnage qui bouge est refuse ({b['failed_metrics']})")
        if a["passed"] == b["passed"]:
            defauts += 1
            details.append("fige et mouvant rendent le meme verdict")
        ajoute("3D/anim", "porte de mouvement", defauts,
               " ; ".join(details) or "fige refuse, mouvant accepte, les deux distingues")
    except Exception as exc:  # noqa: BLE001
        ajoute("3D/anim", "porte de mouvement", 1, f"sonde en echec : {exc}")

    # --- 2. Compilateur de mouvement : chaque preset bouge-t-il ? ----------
    try:
        import motion_baker as MB
        catalogue = MB.load_preset_catalog()

        def amplitude_max(payload):
            best = 0.0
            for i in payload["instructions"]:
                vals = [v for (_f, v) in i["samples"]]
                if vals:
                    best = max(best, max(vals) - min(vals))
            return best

        morts = []
        for pid in sorted(catalogue):
            r = MB.compile_motion_payload({
                "schema": "aurora.motion.v1", "id": "m", "fps": 24, "frame_count": 48,
                "primitives": [{"kind": "preset_ref", "source_target": pid, "modifiers": {}}]})
            if r["instruction_count"] == 0 or amplitude_max(r) <= 1e-9:
                morts.append(pid)
        ajoute("3D/mouvement", "presets qui bougent", len(morts),
               f"{len(catalogue) - len(morts)}/{len(catalogue)} presets produisent un mouvement reel"
               + (f" ; morts : {morts[:5]}" if morts else ""))
    except Exception as exc:  # noqa: BLE001
        ajoute("3D/mouvement", "presets qui bougent", 1, f"sonde en echec : {exc}")

    # --- 3. Portail de qualite : un maillage quasi vide passe-t-il ? -------
    try:
        import trimesh
        from mesh_quality_score import score_mesh
        with tempfile.TemporaryDirectory() as td:
            defauts, details = 0, []
            for sub, attendu_refuse in ((0, True), (4, False)):
                m = trimesh.creation.icosphere(subdivisions=sub, radius=0.5)
                v = np.asarray(m.vertices)
                c = np.zeros((len(v), 4), np.uint8)
                c[:, 3] = 255
                c[:, :3] = ((v - v.min(0)) / (np.ptp(v, axis=0) + 1e-9) * 255).astype(np.uint8)
                m.visual.vertex_colors = c
                p = str(Path(td) / f"i{sub}.glb")
                m.export(p)
                r = score_mesh(p, "generic")
                refuse = bool(r["retry_recommended"])
                if refuse != attendu_refuse:
                    defauts += 1
                    details.append(
                        f"{len(v)} sommets : {'refuse' if refuse else 'LIVRE'} "
                        f"(note {r['overall_score']})")
            ajoute("3D/qualite", "plancher de densite", defauts,
                   " ; ".join(details) or "12 sommets refuses, 2562 acceptes")
    except Exception as exc:  # noqa: BLE001
        ajoute("3D/qualite", "plancher de densite", 1, f"sonde en echec : {exc}")

    # --- 4. Table de projection du bake de couleurs ------------------------
    try:
        from bake_vertex_colors import KIND_PROJECTION
        from mesh_quality_score import KIND_ASPECT
        manquants = [k for k in KIND_ASPECT if k not in KIND_PROJECTION]
        ajoute("3D/couleur", "table de projection", len(manquants),
               f"{len(manquants)} famille(s) sans axe de projection explicite"
               + (f" : {manquants}" if manquants else ""))
    except Exception as exc:  # noqa: BLE001
        ajoute("3D/couleur", "table de projection", 1, f"sonde en echec : {exc}")

    # --- 5. Graphe de reprise : chaque couple est-il DECIDE ? --------------
    try:
        from auto_validate_mesh import RETRY_GRAPH
        generateurs = sorted({g for (g, _a) in RETRY_GRAPH})
        axes = ("color_richness", "silhouette_aspect", "manifold_health")
        manquants = [(g, a) for g in generateurs for a in axes if (g, a) not in RETRY_GRAPH]
        ajoute("3D/reprise", "graphe de reprise", len(manquants),
               f"{len(manquants)} couple(s) (generateur, axe) sans decision explicite"
               + (f" : {manquants}" if manquants else ""))
    except Exception as exc:  # noqa: BLE001
        ajoute("3D/reprise", "graphe de reprise", 1, f"sonde en echec : {exc}")

    return out


if __name__ == "__main__":
    sys.stdout.write(json.dumps(mesures(), ensure_ascii=False) + "\n")
