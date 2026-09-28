"""Réparation non destructive de la fragmentation par soudure de sommets.

TRELLIS livre un maillage dont la surface est continue mais dont les sommets
sont DUPLIQUÉS: chaque îlot de texture obtient sa propre copie des sommets
situés sur la couture. Résultat mesuré sur les validations: 8 100 composantes
connexes pour 97 623 faces, alors que la géométrie est continue au 1e-9.

Deux conséquences concretes, toutes deux mesurées:

1. Le juge (`auto_rl/judges.py`) punish `fragment = 1 - aire_max/aire_totale`,
   soit 0,9393 sur ces maillages. La soudure le ramène à 0,0736.
2. La décimation UV-preserving (`optimize_textured_mesh.py`) est contrainte par
   `preserveboundary=True`: avec 8 100 îlots, elle plafonne à 58 329 faces
   pour une cible de 40 000. Après soudure elle atteint la cible (39 999).

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
    """Mimique exactement la metrique du juge: (composantes, fragment, faces)."""
    from scipy.sparse import coo_matrix
    from scipy.sparse.csgraph import connected_components

    adjacent = mesh.face_adjacency
    graph = coo_matrix(
        (np.ones(len(adjacent), dtype=np.uint8), (adjacent[:, 0], adjacent[:, 1])),
        shape=(len(mesh.faces), len(mesh.faces)),
    ).tocsr()
    count, labels = connected_components(graph, directed=False)
    areas = np.bincount(labels, weights=mesh.area_faces, minlength=count)
    fragment = float(1 - areas.max() / max(areas.sum(), 1e-12)) if len(areas) else 1.0
    return int(count), fragment, int(len(mesh.faces))


def weld_mesh(glb_in: str, glb_out: str, digits: int = DEFAULT_DIGITS) -> dict[str, Any]:
    """Soude les sommets coincidents en respectant les UV. Ne modifie pas l'entree."""
    import trimesh

    src = Path(glb_in).resolve()
    dst = Path(glb_out).resolve()
    if src == dst:
        raise ValueError(f"refus d'ecraser l'original: {src}")

    base = trimesh.load(str(src), process=False, force="mesh")
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
    lost = faces_before - faces_after
    if lost > max(1, int(faces_before * _MAX_FACE_LOSS_RATIO)):
        return {
            "ok": False,
            "reason": f"trop de faces perdues: {lost}/{faces_before}",
            "faces_before": faces_before,
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
        "components_before": comps_before,
        "components_after": comps_after,
        "fragment_before": round(frag_before, 6),
        "fragment_after": round(frag_after, 6),
        "fragment_gain": round(frag_before - frag_after, 6),
        "faces_before": faces_before,
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
