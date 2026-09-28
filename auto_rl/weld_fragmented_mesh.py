"""Réparation non destructive de la fragmentation par soudure de sommets.

TRELLIS livre un maillage dont la surface est continue mais dont les sommets
sont DUPLIQUÉS: chaque îlot de texture obtient sa propre copie des sommets
situés sur la couture. Mesuré: 8 103 composantes connexes pour 97 623 faces,
et 951 618 pour la scène Natsu, alors que la géométrie est continue au 1e-9.
La distance médiane d'un sommet à son plus proche voisin situé dans une AUTRE
composante vaut exactement 0,000000.

Pourquoi cette soudure existe, et ce qu'elle ne fait PAS:

1. Ce que le juge VOIT. `auto_rl/judges.py` (MeshJudge.score) soude déjà une
   copie avant de mesurer `fragment`. Le juge n'est donc PAS pénalisé par cet
   artefact: sans soudure 0,93-0,95, avec 0,07-0,32, et l'écart est déjà capté
   aujourd'hui. Cette soudure n'améliore donc PAS le score du juge. Une mesure
   de fragmentation prise SANS la soudure du juge surestimerait le gain.
2. Ce que la décimation subit. `optimize_textured_mesh.py` est réellement
   bloqué: `preserveboundary=True` verrouille chaque îlot. Mesuré, cible
   40 000 faces: 97 623 -> 58 329 sans soudure, -> 39 999 avec. Sur Natsu:
   967 762 faces obtenues, 45 000 atteints, 200,7 Mo -> 90,4 Mo.
3. Ce que le consommateur voit. Les .glb livrés contiennent des milliers
   d'îlots non raccordés, ce qui coûte au rendu temps réel, au culling et à
   tout outillage qui ne soude pas.

La soudure respecte la texture (`merge_tex=True`): seuls des sommets de même
position ET même UV sont fusionnés, donc l'atlas n'est jamais écrasé.

Non destructif: l'entrée n'est jamais modifiée, l'original est conservé.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

import numpy as np

# Arrondi des coordonnées servant de cle de fusion. 1e-6 est tres inferieur au
# detail utile d'un maillage de diagonale ~1.65, et suffit: 6 et 4 donnent le
# meme resultat (8 100 -> 849 composantes). 3 n'apporte plus rien.
DEFAULT_DIGITS = 6

# La soudure transforme en degeneres les triangles dont deux sommets
# coincident. On les retire explicitement AVANT l'export pour que le compte
# rapporte soit exactement celui du fichier produit.
_MAX_FACE_LOSS_RATIO = 0.005


def _fragments(mesh) -> tuple[int, float, int]:
    """Reproduit EXACTEMENT la metrique du juge (judges.py, MeshJudge.score).

    Point non evident et decisif: le juge soude DEJA une copie
    (`topo.merge_vertices(merge_tex=True, merge_norm=True)`) avant de compter
    les composantes. Un maillage livre par TRELLIS est donc deja immunise contre
    l'artefact de duplication: mesure SANS soudure `fragment` vaut 0,93-0,95,
    mesure AVEC elle 0,07-0,32. Comparer les deux sans cette etape surestimerait
    massivement l'ecart reellement vu par le juge.
    """
    from scipy.sparse import coo_matrix
    from scipy.sparse.csgraph import connected_components

    topo = mesh.copy()
    topo.merge_vertices(merge_tex=True, merge_norm=True)
    adjacent = topo.face_adjacency
    graph = coo_matrix(
        (np.ones(len(adjacent), dtype=np.uint8), (adjacent[:, 0], adjacent[:, 1])),
        shape=(len(topo.faces), len(topo.faces)),
    ).tocsr()
    count, labels = connected_components(graph, directed=False)
    areas = np.bincount(labels, weights=topo.area_faces, minlength=count)
    fragment = float(1 - areas.max() / max(areas.sum(), 1e-12)) if len(areas) else 1.0
    return int(count), fragment, int(len(topo.faces))


def _components_raw(mesh) -> int:
    """Composantes connexes SANS soudure: mesure l'indexation, pas la forme."""
    from scipy.sparse import coo_matrix
    from scipy.sparse.csgraph import connected_components

    adjacent = mesh.face_adjacency
    graph = coo_matrix(
        (np.ones(len(adjacent), dtype=np.uint8), (adjacent[:, 0], adjacent[:, 1])),
        shape=(len(mesh.faces), len(mesh.faces)),
    ).tocsr()
    return int(connected_components(graph, directed=False)[0])


def weld_mesh(glb_in: str, glb_out: str, digits: int = DEFAULT_DIGITS) -> dict[str, Any]:
    """Soude les sommets coincidents en respectant les UV. Ne modifie pas l'entree."""
    import trimesh

    src = Path(glb_in).resolve()
    dst = Path(glb_out).resolve()
    if src == dst:
        raise ValueError(f"refus d'ecraser l'original: {src}")

    base = trimesh.load(str(src), process=False, force="mesh")
    # faces_before sur le fichier REEL, avant toute transformation.
    raw_comps_before = _components_raw(base)
    faces_file = int(len(base.faces))
    comps_before, frag_before, faces_before = _fragments(base)
    uv_before = getattr(base.visual, "uv", None)
    if uv_before is None:
        return {"ok": False, "reason": "mesh has no UVs"}

    welded = base.copy()
    welded.merge_vertices(merge_tex=True, merge_norm=True, digits_vertex=digits)
    # Retire explicitement les triangles devenus degeneres pour que faces_after
    # decrive exactement le fichier ecrit. merge_vertices en retire deja certains
    # de son cote: faces_lost_total rend la difference totale imputable.
    keep = welded.nondegenerate_faces(height=0.0)
    dropped_degenerate = int(len(welded.faces) - len(keep))
    welded.update_faces(keep)
    welded.remove_unreferenced_vertices()

    verts_after = int(len(welded.vertices))
    uv_after = getattr(welded.visual, "uv", None)
    if uv_after is None or len(uv_after) != verts_after:
        return {"ok": False, "reason": "soudure incoherente: UVLost"}

    comps_after, frag_after, faces_after = _fragments(welded)
    raw_comps_after = _components_raw(welded)
    lost = faces_file - faces_after
    if lost > max(1, int(faces_file * _MAX_FACE_LOSS_RATIO)):
        return {
            "ok": False,
            "reason": f"trop de faces perdues: {lost}/{faces_file}",
            "faces_before": faces_file,
            "faces_after": faces_after,
        }

    dst.parent.mkdir(parents=True, exist_ok=True)
    # Le nom temporaire DOIT garder l'extension, sinon trimesh ne reconnait pas
    # le format. Ecriture atomique: jamais de .glb partiel visible par l'API.
    tmp = dst.with_name(f"{dst.name}.tmp.glb")
    welded.export(str(tmp))
    os.replace(tmp, dst)

    return {
        "ok": True,
        "input": str(src),
        "output": str(dst),
        "digits": digits,
        # Indexation: ce que voit un consommateur qui ne soude pas (culling,
        # rendu temps reel, connectivity). C'est la vraie fragmentation du fichier.
        "components_raw_before": raw_comps_before,
        "components_raw_after": raw_comps_after,
        # Metrique du juge, APRES sa propre soudure: deja immunise, donc
        # fragment_gain reste faible et attendu. Ne pas y lire un gain de score.
        "components_judge_before": comps_before,
        "components_judge_after": comps_after,
        "fragment_before": round(frag_before, 6),
        "fragment_after": round(frag_after, 6),
        "fragment_gain": round(frag_before - frag_after, 6),
        "judge_already_welds": True,
        "faces_before": faces_file,
        "faces_after": faces_after,
        "faces_lost_total": lost,
        "degenerate_faces_removed_explicit": dropped_degenerate,
        "vertices_before": int(len(base.vertices)),
        "vertices_after": verts_after,
        "uv_preserved": True,
        "input_untouched": True,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("input")
    ap.add_argument("output")
    ap.add_argument("--digits", type=int, default=DEFAULT_DIGITS)
    ap.add_argument("--report", help="chemin du rapport JSON")
    args = ap.parse_args()

    report = weld_mesh(args.input, args.output, args.digits)
    if args.report:
        Path(args.report).parent.mkdir(parents=True, exist_ok=True)
        Path(args.report).write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0 if report.get("ok") else 1


if __name__ == "__main__":
    sys.exit(main())
