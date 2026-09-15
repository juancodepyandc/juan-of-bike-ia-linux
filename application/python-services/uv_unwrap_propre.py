#!/usr/bin/env python
"""Deplie un maillage en ilots UV larges avant de le repeindre.

Marching Cubes (TRELLIS.2, Hunyuan3D) ne produit pas d'UV: l'atlas livre est
decoupe en centaines d'eclats minuscules — mesure du 29/08 sur le personnage:
749 ilots dont 727 sous 1 % de la surface, le plus gros n'en portant que 19,6 %.
Un logo ou un texte qui traverse le torse tombe alors sur des dizaines d'eclats
disjoints et se lit comme un gribouillis, quelle que soit la resolution.

Aucun repeintre ne repare ca: MV-Adapter, comme le paint natif, ecrit dans les UV
qu'on lui donne. Il faut donc redeplier en amont. On accepte volontairement plus
de distorsion (max_cost eleve) parce que l'objectif n'est pas la fidelite metrique
de la parametrisation mais la CONTINUITE: un torse d'une seule piece porte un
flocage lisible, un torse en quarante morceaux non.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import trimesh


def _plus_gros(scene) -> trimesh.Trimesh:
    if isinstance(scene, trimesh.Trimesh):
        return scene
    geoms = list(scene.geometry.values())
    if not geoms:
        raise ValueError("aucune geometrie dans le fichier")
    return max(geoms, key=lambda g: len(g.faces))


def mesurer_ilots(maillage: trimesh.Trimesh) -> dict:
    """Compte les ilots UV et la part portee par le plus gros."""
    uv = getattr(maillage.visual, "uv", None)
    if uv is None:
        return {"ilots": None, "raison": "pas d'UV"}
    _, inverse = np.unique(np.round(np.asarray(uv), 5), axis=0, return_inverse=True)
    faces = inverse[maillage.faces]
    parent = np.arange(int(faces.max()) + 1)

    def racine(noeud: int) -> int:
        while parent[noeud] != noeud:
            parent[noeud] = parent[parent[noeud]]
            noeud = parent[noeud]
        return noeud

    for a, b, c in faces:
        for x, y in ((a, b), (b, c)):
            rx, ry = racine(int(x)), racine(int(y))
            if rx != ry:
                parent[rx] = ry
    etiquettes = np.array([racine(int(i)) for i in faces[:, 0]])
    _, tailles = np.unique(etiquettes, return_counts=True)
    return {
        "ilots": int(len(tailles)),
        "plus_gros_pct": round(100.0 * float(tailles.max()) / len(faces), 2),
        "ilots_sous_1pct": int((tailles < 0.01 * len(faces)).sum()),
    }


def deplier(entree: str | Path, sortie: str | Path,
            resolution: int = 4096, marge: int = 4,
            cout_max: float = 8.0) -> dict:
    """Redeplie le maillage et ecrit un GLB sans texture, pret a etre repeint."""
    import xatlas

    entree, sortie = Path(entree), Path(sortie)
    maillage = _plus_gros(trimesh.load(entree, process=False))
    avant = mesurer_ilots(maillage)

    atlas = xatlas.Atlas()
    atlas.add_mesh(np.asarray(maillage.vertices, dtype=np.float32),
                   np.asarray(maillage.faces, dtype=np.uint32))
    options_ilots = xatlas.ChartOptions()
    # Plus le cout tolere est haut, moins xatlas coupe: on echange de la
    # distorsion contre de la continuite, ce qui est exactement le compromis
    # utile quand la texture porte du texte.
    options_ilots.max_cost = float(cout_max)
    options_ilots.max_iterations = 4
    options_pack = xatlas.PackOptions()
    options_pack.resolution = int(resolution)
    options_pack.padding = int(marge)
    # LE PACKING EXHAUSTIF NE TIENT PAS L'ECHELLE: mesure du 29/08, plus de dix
    # minutes sans rendre la main sur 568 k faces. Ce qu'on cherche ici est la
    # CONTINUITE des ilots, pas leur placement optimal dans le carre — on ne
    # paie donc l'exhaustivite que sur les maillages ou elle reste gratuite.
    options_pack.bruteForce = len(maillage.faces) <= 150_000
    atlas.generate(chart_options=options_ilots, pack_options=options_pack)
    correspondance, indices, uvs = atlas[0]

    redeplie = trimesh.Trimesh(
        vertices=np.asarray(maillage.vertices)[correspondance],
        faces=np.asarray(indices),
        process=False)
    redeplie.visual = trimesh.visual.TextureVisuals(uv=np.asarray(uvs))
    sortie.parent.mkdir(parents=True, exist_ok=True)
    redeplie.export(sortie)

    apres = mesurer_ilots(redeplie)
    return {
        "schema": "aurora.uv_unwrap.v1",
        "ok": sortie.is_file(),
        "entree": str(entree),
        "sortie": str(sortie),
        "faces": int(len(redeplie.faces)),
        "avant": avant,
        "apres": apres,
        "utilisation_atlas_pct": round(100.0 * float(getattr(atlas, "utilization", 0.0) if not isinstance(getattr(atlas, "utilization", 0.0), (list, tuple)) else atlas.utilization[0]), 1),
    }


if __name__ == "__main__":
    import json

    if len(sys.argv) < 3:
        print("usage: uv_unwrap_propre.py <entree.glb> <sortie.glb> [resolution]")
        raise SystemExit(2)
    res = int(sys.argv[3]) if len(sys.argv) > 3 else 4096
    print(json.dumps(deplier(sys.argv[1], sys.argv[2], resolution=res),
                     ensure_ascii=False, indent=2))
