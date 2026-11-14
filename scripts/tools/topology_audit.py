#!/usr/bin/env python3
"""Audit de topologie d'un maillage, sans GPU ni rendu.

Reprend EXACTEMENT les metriques de `auto_rl/judges.py:MeshJudge.score`
(les lignes 80-100 et 126-128) et ajoute deux mesures de propreté que le
juge ne regarde pas mais qui expliquent les artefacts visibles :

  * `bords_ouverts_reels`  : aretes utilisees par un seul triangle, apres
    soudure par POSITION (et non par indice). Le juge compte les aretes
    apres `merge_vertices(merge_tex=True)`, ce qui laisse une couture UV
    par ile: un atlas de plusieurs ilots produit donc un faux "bord"
    meme quand la surface est fermee. Mesurer la position re donne le
    vrai etat du maillage.
  * `normales_absentes`    : un GLB sans attribut NORMAL s'eclaire mal
    dans n'importe quel viewer.

But: rendre mesurable l'ecart entre "le maillage est ouvert" et "le juge
le croit ouvert a cause des coutures UV", afin de ne pas repairing un
maillage deja ferme (cout Blender inutile) et de ne pas declarer sain un
maillage reellement troue.

Usage:
    python tools/topology_audit.py un.glb [autre.glb ...] [--json out.json]
"""
from __future__ import annotations

import argparse
import json
import struct
import sys
from pathlib import Path

import numpy as np


def _read_glb_json(path: Path) -> dict:
    raw = path.read_bytes()
    if raw[:4] != b"glTF":
        raise ValueError("%s n'est pas un GLB" % path)
    pos = 12
    doc = None
    while pos < len(raw):
        (clen, ctype) = struct.unpack("<II", raw[pos:pos + 8])
        chunk = raw[pos + 8:pos + 8 + clen]
        if ctype == 0x4E4F534A:  # JSON
            doc = json.loads(chunk.decode("utf-8"))
            break
        pos += 8 + clen
    if doc is None:
        raise ValueError("%s: chunk JSON absent" % path)
    return doc


def audit(path: Path) -> dict:
    """Metriques de topologie, calculees comme le juge 3D."""
    import trimesh
    from scipy.sparse import coo_matrix
    from scipy.sparse.csgraph import connected_components

    doc = _read_glb_json(path)
    attrs: set[str] = set()
    for mesh in doc.get("meshes", []):
        for prim in mesh.get("primitives", []):
            attrs |= set(prim.get("attributes", {}))

    mesh = trimesh.load(str(path), force="mesh", process=False)
    if not isinstance(mesh, trimesh.Trimesh) or len(mesh.faces) == 0:
        return {"fichier": str(path), "erreur": "maillage vide"}

    topo = mesh.copy()
    topo.merge_vertices(merge_tex=True, merge_norm=True)
    counts = np.bincount(topo.edges_unique_inverse)
    nonmanifold = float((counts > 2).mean())
    boundary = float((counts == 1).mean())

    adjacent = topo.face_adjacency
    graph = coo_matrix(
        (np.ones(len(adjacent), dtype=np.uint8), (adjacent[:, 0], adjacent[:, 1])),
        shape=(len(topo.faces), len(topo.faces)),
    ).tocsr()
    component_count, labels = connected_components(graph, directed=False)
    areas = np.bincount(labels, weights=topo.area_faces, minlength=component_count)
    fragment = float(1 - areas.max() / max(areas.sum(), 1e-12)) if len(areas) else 1.0
    degenerate = float((topo.area_faces < max(float(topo.area), 1e-12) * 1e-12).mean())

    # --- vrai etat de fermeture, mesure par POSITION et non par indice ---
    v = np.asarray(topo.vertices)
    f = np.asarray(topo.faces)
    extent = float(np.linalg.norm(v.max(0) - v.min(0))) or 1.0
    # meme grille que perfection_gate.audit_trous: 0.4 mm relatif au sujet
    cell = np.round(v / (extent * 4e-4)).astype(np.int64)
    _, inv = np.unique(cell, axis=0, return_inverse=True)
    fs = inv[f]
    keep = (fs[:, 0] != fs[:, 1]) & (fs[:, 1] != fs[:, 2]) & (fs[:, 0] != fs[:, 2])
    fs = fs[keep]
    if len(fs):
        e = np.sort(np.concatenate([fs[:, (0, 1)], fs[:, (1, 2)], fs[:, (0, 2)]]), axis=1)
        _, c = np.unique(e, axis=0, return_counts=True)
        bords_reels = int((c == 1).sum())
        aretes_reelles = int(len(c))
    else:
        bords_reels = 0
        aretes_reelles = 0

    # Le juge ne note PAS les auto-intersections ici (besoin de Blender);
    # on donne donc la part de topologie hors intersections, qui borne le
    # gain maximum d'un nettoyage geometrique.
    topo_sans_inter = max(0.0, 1 - 5 * nonmanifold - boundary - fragment - 5 * degenerate)

    return {
        "fichier": str(path),
        "faces": int(len(mesh.faces)),
        "sommets": int(len(mesh.vertices)),
        "nonmanifold_edge_fraction": nonmanifold,
        "boundary_edge_fraction": boundary,
        "fragment_area_fraction": fragment,
        "degenerate_face_fraction": degenerate,
        "components": int(component_count),
        "bords_ouverts_par_indice": int((counts == 1).sum()),
        "bords_ouverts_reels": bords_reels,
        "aretes_reelles": aretes_reelles,
        "etanche_par_position": bords_reels == 0,
        "normales_absentes": "NORMAL" not in attrs,
        "atlas_ilots": len(doc.get("images", [])),
        "topology_sans_intersections": topo_sans_inter,
    }


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("meshes", nargs="+")
    ap.add_argument("--json", help="ecrire aussi le resultat dans ce fichier")
    args = ap.parse_args(argv)

    rows = []
    for raw in args.meshes:
        p = Path(raw)
        if not p.is_file():
            print("absent: %s" % p, file=sys.stderr)
            continue
        try:
            row = audit(p)
        except Exception as exc:  # noqa: BLE001
            row = {"fichier": str(p), "erreur": repr(exc)}
        rows.append(row)

    hdr = ("fichier", "faces", "nonmanif", "bord_idx", "bord_reel", "fragment",
           "degen", "compos", "norm?", "topo_sans_int")
    print("%-46s %8s %8s %9s %10s %9s %6s %7s %6s %8s" % hdr)
    for r in rows:
        if "erreur" in r:
            print("%-46s ERREUR %s" % (Path(r["fichier"]).name, r["erreur"][:40]))
            continue
        print("%-46s %8d %8.4f %9d %10d %9.4f %6.4f %7d %6s %8.4f" % (
            Path(r["fichier"]).name, r["faces"], r["nonmanifold_edge_fraction"],
            r["bords_ouverts_par_indice"], r["bords_ouverts_reels"],
            r["fragment_area_fraction"], r["degenerate_face_fraction"],
            r["components"], "OUI" if r["normales_absentes"] else "non",
            r["topology_sans_intersections"]))

    if args.json:
        Path(args.json).parent.mkdir(parents=True, exist_ok=True)
        Path(args.json).write_text(json.dumps(rows, indent=1, ensure_ascii=False),
                                   encoding="utf-8")
        print("\nJSON -> %s" % args.json)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
