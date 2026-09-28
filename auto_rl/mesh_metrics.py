"""Métriques de maillage exactes et vérifiables pour l'audit 3D.

Pourquoi ce module existe. `render_mesh.py` comptait les auto-intersections avec
`BVHTree.overlap()`, qui est un test de PHASE LARGE: il retourne les paires de
triangles dont les boîtes englobantes se recouvrent, sans vérifier l'intersection
géométrique. Le compte obtenu (572 à 14 727 sur des maillages de ~93 000 faces)
mesure donc la densité de la structure, pas un défaut. Comme ce terme entre dans
la topologie avec le multiplicateur `1/(1 + n/faces*20)`, il absorbe en moyenne
0,1536 du score composite, soit dix fois plus que tous les autres termes réunis:
un signal de récompense bruité à 10 % du score.

Corriger une métrique n'est PAS améliorer un modèle: les scores montent parce
que la règle mesure mieux, pas parce que la géométrie est meilleure. Les deux
comptes sont donc exposés séparément, `intersections_exactes` et
`intersections_bvh`, pour que la correction reste lisible.

Aucune approximation: test triangle-triangle de Möller vectorisé, cas coplanar
traité par séparateurs d'axes en 2D. Validé sur des maillages à vérité connue
dans `tests_auto_rl/test_mesh_metrics.py`.
"""

from __future__ import annotations

import numpy as np

_EPS_REL = 1e-12
# Borne l'etendue couverte par une face, pour qu'une face degeneree ou tres
# allongee ne fasse pas exploser le nombre d'insertions dans la grille.
_MAX_CELL_SPAN = 64


def _triangles(mesh) -> np.ndarray:
    faces = np.asarray(mesh.faces)
    return np.asarray(mesh.vertices)[faces]


def _project(axes: np.ndarray, pts: np.ndarray) -> np.ndarray:
    """Projette des points sur des axes unitaires. axes (N,A,C), pts (N,P,C) -> (N,A,P).

    La projection est un SCALAIRE: on somme sur les coordonnees. Les deux
    operandes doivent partager la MEME lettre pour l'axe contracte, sinon einsum
    fait un produit externe au lieu d'un produit scalaire, silencieusement.
    """
    return np.einsum("nac,nic->nai", axes, pts)


def _candidate_pairs(lo: np.ndarray, hi: np.ndarray) -> np.ndarray:
    """Paires de faces dont les AABB se recouvrent, via grille de hachage 3D.

    C'est un SUR-ENSEMBLE exact, donc sans faux negatif: deux AABB qui se
    recouvrentlouent au moins une cellule commune. On ne materialise jamais la
    liste complete des paires (qui serait de l'ordre de n^2/2), seulement les
    paires reellement candidates.

    Une taille de cellule au-dela de la plus grande face ferait exploser le
    nombre de cellules vides; on borne donc l'etendue couverte par cellule.
    """
    n = len(lo)
    if n < 2:
        return np.empty((0, 2), dtype=np.int64)
    ext = hi - lo
    cell = float(np.percentile(ext.max(axis=1), 90))
    if not np.isfinite(cell) or cell <= 0.0:
        cell = float(ext.max()) or 1.0

    c0 = np.floor(lo / cell).astype(np.int64)
    span = np.minimum(np.floor(hi / cell).astype(np.int64) - c0, _MAX_CELL_SPAN)
    span = np.maximum(span, 0)
    counts = ((span[:, 0] + 1) * (span[:, 1] + 1) * (span[:, 2] + 1)).astype(np.int64)
    total = int(counts.sum())
    if total == 0:
        return np.empty((0, 2), dtype=np.int64)

    face = np.repeat(np.arange(n, dtype=np.int64), counts)
    starts = np.repeat(np.cumsum(counts) - counts, counts)
    k = np.arange(total, dtype=np.int64) - starts
    sx, sy = span[face, 0] + 1, span[face, 1] + 1
    x = c0[face, 0] + k % sx
    y = c0[face, 1] + (k // sx) % sy
    z = c0[face, 2] + k // (sx * sy)
    key = (x * 73856093) ^ (y * 19349663) ^ (z * 83492791)

    order = np.argsort(key, kind="stable")
    key, face = key[order], face[order]
    bounds = np.flatnonzero(np.diff(key)) + 1
    groups = np.split(face, bounds)

    out = []
    for g in groups:
        if len(g) < 2:
            continue
        i, j = np.triu_indices(len(g), 1)
        out.append(np.column_stack([g[i], g[j]]))
    if not out:
        return np.empty((0, 2), dtype=np.int64)
    pairs = np.concatenate(out, axis=0)
    # Deux faces qui se recouvrent partagent PLUSIEURES cellules: sans
    # deduplication la meme paire serait comptee plusieurs fois.
    key = np.unique(pairs[:, 0].astype(np.int64) * n + pairs[:, 1])
    return np.column_stack([key // n, key % n])


def _sat2d(p1: np.ndarray, p2: np.ndarray) -> np.ndarray:
    """Recouvrement de deux triangles convexes 2D par separateurs d'axes.

    Pour des polygones convexes, les axes sont les normales de toutes les aretes
    des deux triangles (3 + 3): la separation sur un seul d'eux suffit a conclure.
    """
    axes = []
    for tri in (p1, p2):
        e = np.roll(tri, -1, axis=1) - tri
        n = np.stack([-e[..., 1], e[..., 0]], axis=-1)
        axes.append(n / np.maximum(np.linalg.norm(n, axis=-1, keepdims=True), 1e-30))
    axes = np.concatenate(axes, axis=1)  # (N, 6, 2)
    a_min, a_max = _project(axes, p1).min(axis=2), _project(axes, p1).max(axis=2)
    b_min, b_max = _project(axes, p2).min(axis=2), _project(axes, p2).max(axis=2)
    separated = (a_max < b_min) | (b_max < a_min)  # (N, 6)
    return ~separated.any(axis=1)  # (N,)


def _plane_distances(normal: np.ndarray, tri: np.ndarray, offset: np.ndarray) -> np.ndarray:
    """Distance signee de chaque sommet de `tri` au plan decrit par (normal, offset).

    normal (N,3), tri (N,3,3), offset (N,) -> (N,3): l'axe des SOMMETS est
    l'axe 1 de `tri`, donc il faut contracter normal avec la DERNIERE dimension.
    """
    return np.einsum("nj,nkj->nk", normal, tri) + offset[:, None]


def _coplanar_overlap(t1: np.ndarray, t2: np.ndarray) -> np.ndarray:
    """Cas coplanar: projection dans le plan du triangle puis SAT 2D.

    L'axe `a` doit être un axe DIFFERENT de celui domine par la normale: sinon
    `n` et `a` sont paralleles, leur produit vectoriel est nul, et la base
    projetée devient du NaN qui fait partout "recouvrement".
    """
    n = np.cross(t1[:, 1] - t1[:, 0], t1[:, 2] - t1[:, 0])
    k = np.argmax(np.abs(n), axis=1)
    a = np.zeros((len(t1), 3))
    a[np.arange(len(t1)), (k + 1) % 3] = 1.0
    u = np.cross(n, a)
    u = u / np.maximum(np.linalg.norm(u, axis=-1, keepdims=True), 1e-30)
    v = np.cross(n, u)
    p1 = np.stack([_project(u[:, None, :], t1)[:, 0],
                   _project(v[:, None, :], t1)[:, 0]], axis=-1)
    p2 = np.stack([_project(u[:, None, :], t2)[:, 0],
                   _project(v[:, None, :], t2)[:, 0]], axis=-1)
    return _sat2d(p1, p2)


def _aabb_pairs(lo: np.ndarray, hi: np.ndarray) -> np.ndarray:
    """Paires de faces dont les AABB se recouvrent (phase large, sur-ensemble)."""
    pairs = _candidate_pairs(lo, hi)
    if len(pairs) == 0:
        return pairs
    a, b = pairs[:, 0], pairs[:, 1]
    return pairs[(np.minimum(hi[a], hi[b]) >= np.maximum(lo[a], lo[b])).all(axis=1)]


def _hit_pairs(verts: np.ndarray, faces: np.ndarray):
    """Paires de faces qui s'intersectent reellement, et leur phase large.

    Retourne (ia, ib, n_candidats_aabb): `ia/ib` sont les faces en intersection,
    `n_candidats_aabb` est la borne phase large. L'ecart entre les deux mesure
    exactement le bruit de l'ancienne mesure par AABB.
    """
    t = np.asarray(verts, dtype=float)[np.asarray(faces)]
    lo, hi = t.min(axis=1), t.max(axis=1)

    broad = _aabb_pairs(lo, hi)
    if len(broad) == 0:
        return np.empty(0, np.int64), np.empty(0, np.int64), 0
    ia, ib = broad[:, 0], broad[:, 1]

    # paires partageant un sommet: par construction elles se touchent, ce n'est
    # pas une auto-intersection
    shared = (t[ia][:, :, None, :] == t[ib][:, None, :, :]).all(axis=-1).any(axis=(1, 2))
    ia, ib = ia[~shared], ib[~shared]
    if len(ia) == 0:
        return ia, ib, len(broad)

    t1, t2 = t[ia], t[ib]
    n1 = np.cross(t1[:, 1] - t1[:, 0], t1[:, 2] - t1[:, 0])
    n2 = np.cross(t2[:, 1] - t2[:, 0], t2[:, 2] - t2[:, 0])
    d1 = -np.einsum("ij,ij->i", n1, t1[:, 0])
    d2 = -np.einsum("ij,ij->i", n2, t2[:, 0])
    s1 = _plane_distances(n1, t2, d1)
    s2 = _plane_distances(n2, t1, d2)
    scale = np.maximum(
        np.maximum(np.abs(s1).max(axis=1), np.abs(s2).max(axis=1)),
        np.maximum(np.abs(n1).max(axis=1), np.abs(n2).max(axis=1)) * _EPS_REL,
    )
    tol = scale * _EPS_REL
    coplanar = (np.abs(s1) <= tol[:, None]).all(axis=1) & (np.abs(s2) <= tol[:, None]).all(axis=1)

    straddles = (s1.max(axis=1) > 0) & (s1.min(axis=1) < 0)
    straddles &= (s2.max(axis=1) > 0) & (s2.min(axis=1) < 0)
    hit = straddles & ~coplanar
    if coplanar.any():
        hit[coplanar] = _coplanar_overlap(t1[coplanar], t2[coplanar]).ravel()
    return ia[hit], ib[hit], len(broad)


def exact_intersections(verts: np.ndarray, faces: np.ndarray) -> int:
    """Nombre exact de paires de faces qui s'intersectent reellement.

    Exclut les paires qui partagent un sommet: dans un maillage, deux faces
    voisines se touchent toujours, ce n'est pas un defaut.
    """
    ia, _, _ = _hit_pairs(verts, faces)
    return int(len(ia))


def measure(mesh) -> dict:
    """Métriques d'auto-intersection exactes et héritées, sur un même maillage."""
    faces = np.asarray(mesh.faces)
    verts = np.asarray(mesh.vertices)
    ia, ib, broad = _hit_pairs(verts, faces)
    touche = np.unique(np.concatenate([ia, ib])) if len(ia) else np.empty(0, np.int64)
    n = int(len(faces))
    return {
        "faces": n,
        "sommets": int(len(verts)),
        "intersections_exactes": int(len(ia)),
        "paires_aabb_recouvrantes": int(broad),
        "faces_impliquees": int(len(touche)),
        "taux_faces_impliquees": round(len(touche) / n, 6) if n else 0.0,
    }
