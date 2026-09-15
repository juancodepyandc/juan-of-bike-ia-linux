#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""porte_anti_masque — verdict CHIFFRE « masque creux » sur un GLB.

Doctrine (31/07, demande verbatim: « jamais avoir un masque a part quand
c'est demande ») + recherche du jour: un reconstructeur image->3D produit
parfois un RELIEF (coquille plate) au lieu d'un volume ferme. Le juge VLM le
rate souvent (vu de face, un masque ressemble au sujet). Trois mesures
geometriques tranchent, verdict masque si AU MOINS DEUX sur trois:

  M1 aplatissement PCA des sommets  : e3/e2 < 0.18  (attrape le masque
     incline, contrairement a la bbox axiale)
  M2 epaisseur caracteristique      : watertight -> 2*volume/aire normalise
     par la diagonale < 0.02 ; sinon bords ouverts / aretes totales > 2 %
  M3 dos plat                       : > 30 % de l'aire des faces orientees
     vers l'arriere couchees sur un meme plan (RMS < 1.5 % de la diagonale)

Sortie: {"masque": bool, "mesures": {...}} — journalisable telle quelle.
"""
from __future__ import annotations

import json
import sys


def mesurer(glb: str) -> dict:
    import numpy as np
    import trimesh

    m = trimesh.load(glb, force="mesh", process=False)
    v = np.asarray(m.vertices, dtype=np.float64)
    f = np.asarray(m.faces)
    if len(v) < 100 or len(f) < 100:
        return {"masque": False, "mesures": {"note": "maillage trop petit pour juger"}}
    diag = float(np.linalg.norm(v.max(0) - v.min(0))) or 1.0

    # M1 — aplatissement PCA
    c = v - v.mean(0)
    # sous-echantillonnage pour la covariance (rapide, stable)
    idx = np.random.default_rng(7).choice(len(c), min(120000, len(c)), replace=False)
    val = np.linalg.eigvalsh(np.cov(c[idx].T))
    val = np.sort(np.abs(val))[::-1]
    m1_ratio = float(np.sqrt(val[2] / (val[1] + 1e-12)))
    m1 = m1_ratio < 0.18

    # M2 — epaisseur caracteristique
    if m.is_watertight and m.volume > 0:
        m2_val = float(2.0 * m.volume / (m.area + 1e-12) / diag)
        m2 = m2_val < 0.02
        m2_mode = "volume"
    else:
        # SOUDURE VIRTUELLE d'abord (astuce eprouvee de perfection_gate):
        # un maillage TRELLIS a des millions de coutures UV qui comptent
        # comme bords ouverts — sans soudure, M2 votait « masque » sur tout
        # volume sain (mesure: fontaine a 0.425 de faux bords).
        grille = np.round(v / (diag * 4e-4)).astype(np.int64)
        _, inv = np.unique(grille, axis=0, return_inverse=True)
        fs = inv[f]
        fs = fs[(fs[:, 0] != fs[:, 1]) & (fs[:, 1] != fs[:, 2]) & (fs[:, 0] != fs[:, 2])]
        e = np.sort(np.concatenate([fs[:, (0, 1)], fs[:, (1, 2)], fs[:, (0, 2)]]), axis=1)
        uniq, cnt = np.unique(e, axis=0, return_counts=True)
        m2_val = float((cnt == 1).sum() / (len(uniq) + 1e-12))
        m2 = m2_val > 0.02
        m2_mode = "bords_soudes"

    # M3 — dos plat (faces regardant l'arriere, co-planaires)
    tri = v[f]
    n = np.cross(tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0])
    aires = 0.5 * np.linalg.norm(n, axis=1)
    nz = n[:, 2] / (np.linalg.norm(n, axis=1) + 1e-12)
    arr = nz < -0.5
    m3 = False
    m3_val = 0.0
    if arr.sum() > 50:
        z_arr = tri[arr].mean(axis=1)[:, 2]
        a_arr = aires[arr]
        part = float(a_arr.sum() / (aires.sum() + 1e-12))
        rms = float(np.sqrt(np.average((z_arr - np.average(z_arr, weights=a_arr)) ** 2,
                                       weights=a_arr))) / diag
        m3_val = part
        m3 = part > 0.30 and rms < 0.015

    # Un vrai masque / bas-relief / silhouette plate presente AU MOINS DEUX indicateurs concordants
    # (ou un aplatissement extreme < 0.05, pour ne pas confondre un objet volumetrique a large envergure avec un masque).
    est_masque = (m1_ratio < 0.05) or (int(m1) + int(m2) + int(m3) >= 2)
    votes = int(m1) + int(m2) + int(m3)
    return {
        "masque": bool(est_masque),
        "mesures": {
            "aplatissement_e3_e2": round(m1_ratio, 4), "m1_plat": m1,
            "epaisseur_" + m2_mode: round(m2_val, 4), "m2_fin": m2,
            "part_dos_plat": round(m3_val, 3), "m3_dos_plat": m3,
            "votes": votes,
        },
    }


if __name__ == "__main__":
    print(json.dumps(mesurer(sys.argv[1]), ensure_ascii=False))
