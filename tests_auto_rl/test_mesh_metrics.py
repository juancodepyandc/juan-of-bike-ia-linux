#!/usr/bin/env python3
"""Verite connue pour auto_rl/mesh_metrics.py.

Un juge ne peut garantir la non-regression que si sa mesure est, elle-meme,
verifiee. Ces cas ont une reponse calculable a la main: deux triangles qui se
croisent, deux qui ne se croisent pas, deux spheres disjointes, deux spheres
imbriquees.
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from auto_rl.mesh_metrics import exact_intersections  # noqa: E402


def _t(a, b, c):
    return np.array(a, dtype=float), np.array(b, dtype=float), np.array(c, dtype=float)


def _tri_tri_reference(t1: np.ndarray, t2: np.ndarray, tol: float = 1e-12) -> bool:
    """Reference independante, ecrite en scalaire et sans broadcasting.

    Algorithme deliberement different de celui du module: on teste les 6 aretes
    l'une contre l'autre avec Moeller-Trumbore, plus un test 2D si coplanaires.
    Deux implementations qui structurellement differentes qui convergent sur des
    milliers de paires aleatoires cela vaut bien plus qu'un cas main.
    """
    def segment_tri(p, q, a, b, c):
        d = q - p
        e1, e2 = b - a, c - a
        h = np.cross(d, e2)
        det = np.dot(e1, h)
        if abs(det) < tol:
            return False
        inv = 1.0 / det
        s = p - a
        u = np.dot(s, h) * inv
        if u < -tol or u > 1.0 + tol:
            return False
        qv = np.cross(s, e1)
        v = np.dot(d, qv) * inv
        if v < -tol or u + v > 1.0 + tol:
            return False
        t = np.dot(e2, qv) * inv
        # t DOIT etre dans [0,1]: sans ce test on compte une arete qui perce le
        # plan du triangle AU-DELA de son extremite, ce qui n'est pas une intersection.
        return -tol <= t <= 1.0 + tol

    for i in range(3):
        for j in range(3):
            if segment_tri(t1[i], t1[(i + 1) % 3], t2[0], t2[1], t2[2]):
                return True
            if segment_tri(t2[i], t2[(i + 1) % 3], t1[0], t1[1], t1[2]):
                return True

    n1 = np.cross(t1[1] - t1[0], t1[2] - t1[0])
    if np.dot(n1, n1) < tol:
        return False
    if min(np.dot(n1, t2[k] - t1[0]) for k in range(3)) > tol:
        return False
    if max(np.dot(n1, t2[k] - t1[0]) for k in range(3)) < -tol:
        return False
    n2 = np.cross(t2[1] - t2[0], t2[2] - t2[0])
    if min(np.dot(n2, t1[k] - t2[0]) for k in range(3)) > tol:
        return False
    if max(np.dot(n2, t1[k] - t2[0]) for k in range(3)) < -tol:
        return False

    if min(abs(np.dot(n1, t2[k] - t1[0])) for k in range(3)) < tol:
        ref = n1 / np.linalg.norm(n1)
        u = np.array([1.0, 0.0, 0.0])
        if abs(np.dot(ref, u)) > 0.9:
            u = np.array([0.0, 1.0, 0.0])
        u = np.cross(ref, u) / np.linalg.norm(np.cross(ref, u))
        w = np.cross(ref, u)

        def flat(t):
            return np.stack([t @ u, t @ w], axis=-1)

        return _reference_sat2d(flat(t1), flat(t2))
    return True


def _reference_sat2d(p1, p2, tol=1e-12) -> bool:
    axes = []
    for tri in (p1, p2):
        for i in range(3):
            e = tri[(i + 1) % 3] - tri[i]
            n = np.array([-e[1], e[0]])
            axes.append(n / np.linalg.norm(n))
    for ax in axes:
        a = p1 @ ax
        b = p2 @ ax
        if a.max() < b.min() - tol or b.max() < a.min() - tol:
            return False
    return True


def _reference_count(v: np.ndarray, faces: np.ndarray) -> int:
    t = v[faces]
    lo, hi = t.min(axis=1), t.max(axis=1)
    n = 0
    for i in range(len(t)):
        for j in range(i + 1, len(t)):
            # Paires de faces voisines: elles se touchent par construction, ce
            # n'est PAS une auto-intersection. Sans ce filtre la reference
            # compterait chaque arete d'un maillage ferme comme une intersection.
            if (t[i][:, None, :] == t[j][None, :, :]).all(axis=-1).any():
                continue
            # AABB disjoints => triangles disjoints. Filtre valide, et il
            # supprime les faux positifs du test par aretes.
            if not (np.minimum(hi[i], hi[j]) >= np.maximum(lo[i], lo[j])).all():
                continue
            if _tri_tri_reference(t[i], t[j]):
                n += 1
    return n


class TestExactIntersections(unittest.TestCase):
    def test_deux_triangles_se_croisant(self):
        a, b, c = _t([0, 0, 0], [1, 0, 0], [0, 1, 0])
        d, e, f = _t([0.25, 0.25, -1], [0.25, 0.25, 1], [0.9, 0.25, 0])
        v = np.vstack([a, b, c, d, e, f])
        faces = np.array([[0, 1, 2], [3, 4, 5]])
        self.assertEqual(exact_intersections(v, faces), 1)

    def test_deux_triangles_disjoints(self):
        a, b, c = _t([0, 0, 0], [1, 0, 0], [0, 1, 0])
        d, e, f = _t([0, 0, 5], [1, 0, 5], [0, 1, 5])
        v = np.vstack([a, b, c, d, e, f])
        faces = np.array([[0, 1, 2], [3, 4, 5]])
        self.assertEqual(exact_intersections(v, faces), 0)

    def test_coplanaraires_croises(self):
        a, b, c = _t([0, 0, 0], [2, 0, 0], [0, 2, 0])
        d, e, f = _t([1, 1, 0], [3, 1, 0], [1, 3, 0])
        v = np.vstack([a, b, c, d, e, f])
        faces = np.array([[0, 1, 2], [3, 4, 5]])
        self.assertEqual(exact_intersections(v, faces), 1)

    def test_coplanaraires_disjoints(self):
        a, b, c = _t([0, 0, 0], [1, 0, 0], [0, 1, 0])
        d, e, f = _t([5, 5, 0], [6, 5, 0], [5, 6, 0])
        v = np.vstack([a, b, c, d, e, f])
        faces = np.array([[0, 1, 2], [3, 4, 5]])
        self.assertEqual(exact_intersections(v, faces), 0)

    def test_triangles_partageant_un_sommet(self):
        a, b, c = _t([0, 0, 0], [1, 0, 0], [0, 1, 0])
        d, e, f = _t([0, 0, 0], [0, 1, 0], [-1, 0, 0])
        v = np.vstack([a, b, c, d, e, f])
        faces = np.array([[0, 1, 2], [3, 4, 0]])
        self.assertEqual(exact_intersections(v, faces), 0,
                         "deux triangles voisins ne sont pas une auto-intersection")

    def test_deux_sphères_disjointes(self):
        import trimesh

        a = trimesh.creation.icosphere(subdivisions=2, radius=1.0)
        b = trimesh.creation.icosphere(subdivisions=2, radius=1.0)
        b.apply_translation([10, 0, 0])
        m = trimesh.util.concatenate([a, b])
        self.assertEqual(exact_intersections(np.asarray(m.vertices), np.asarray(m.faces)), 0)

    def test_deux_sphères_imbriquées_sans_contact(self):
        """Cas piege: concentriques, les surfaces ne se touchent pas -> 0."""
        import trimesh

        a = trimesh.creation.icosphere(subdivisions=2, radius=1.0)
        b = trimesh.creation.icosphere(subdivisions=2, radius=0.4)
        m = trimesh.util.concatenate([a, b])
        self.assertEqual(exact_intersections(np.asarray(m.vertices), np.asarray(m.faces)), 0,
                         "concentriques: imbriquees sans se toucher, AUCUNE intersection")

    def test_deux_sphères_secantes(self):
        """Cas dur: spheres se traversant, AABB qui se recouvrent partiellement."""
        import trimesh

        a = trimesh.creation.icosphere(subdivisions=3, radius=1.0)
        b = trimesh.creation.icosphere(subdivisions=3, radius=1.0)
        b.apply_translation([1.2, 0, 0])
        m = trimesh.util.concatenate([a, b])
        n = exact_intersections(np.asarray(m.vertices), np.asarray(m.faces))
        self.assertGreater(n, 0, "des spheres secantes DOIVENT etre detectees")

    def test_sphere_unique_sans_auto_intersection(self):
        import trimesh

        a = trimesh.creation.icosphere(subdivisions=2, radius=1.0)
        self.assertEqual(exact_intersections(np.asarray(a.vertices), np.asarray(a.faces)), 0)

    def test_differentiel_triangles_aleatoires(self):
        """Fuzz: comparaison avec la reference sur paires aleatoires."""
        rng = np.random.default_rng(20260928)
        for essai in range(12):
            v = rng.normal(scale=0.5, size=(24, 3))
            faces = np.array([[3 * k, 3 * k + 1, 3 * k + 2] for k in range(8)])
            self.assertEqual(exact_intersections(v, faces), _reference_count(v, faces),
                             f"divergence sur l'essai {essai}")

    def test_differentiel_aplati_coplanaire(self):
        """Fuzz dans un seul plan exact: exerce la branche coplanaire/SAT.

        Le bruit est nul et non 1e-9: avec du bruit, deux triangles qui se
        touchent au pixel pres tombaient sur la frontiere de tolerance et le
        test devenait ambigü, ce qui ne prouve rien.
        """
        rng = np.random.default_rng(4242)
        for essai in range(10):
            v = np.column_stack([rng.uniform(-1, 1, 24), rng.uniform(-1, 1, 24),
                                 np.zeros(24)])
            faces = np.array([[3 * k, 3 * k + 1, 3 * k + 2] for k in range(8)])
            self.assertEqual(exact_intersections(v, faces), _reference_count(v, faces),
                             f"divergence coplanaire sur l'essai {essai}")

    def test_differentiel_spheres_multiples(self):
        """Fuzz sur des spheres: beaucoup de voisinages legitimes, few intersections."""
        import trimesh

        rng = np.random.default_rng(7)
        for essai in range(6):
            a = trimesh.creation.icosphere(subdivisions=1, radius=1.0)
            b = trimesh.creation.icosphere(subdivisions=1, radius=1.0)
            b.apply_translation(rng.uniform(-1.5, 1.5, 3))
            m = trimesh.util.concatenate([a, b])
            v, f = np.asarray(m.vertices), np.asarray(m.faces)
            self.assertEqual(exact_intersections(v, f), _reference_count(v, f),
                             f"divergence spheres sur l'essai {essai}")


if __name__ == "__main__":
    unittest.main(verbosity=2)
