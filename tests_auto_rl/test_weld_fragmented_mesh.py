#!/usr/bin/env python3
"""Non-regression de la reparation de fragmentation (auto_rl/weld_fragmented_mesh).

Reproduit le defaut TRELLIS: la surface est continue mais les sommets sont
dupliques sur les coutures, ce qui casse le maillage en milliers d'iles. Aux
yeux du juge c'est une qualite catastrophique (fragment -> 1.0) et la decimation
UV-preserving est bloquee par preserveboundary=True.

Ces tests utilisent un maillage synthetique construit sur place: aucun artefact
lourd, aucun GPU, aucun rendu.
"""
from __future__ import annotations

import hashlib
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from auto_rl.weld_fragmented_mesh import _fragments, weld_mesh  # noqa: E402


def _make_fragmented_grid(n: int = 6):
    """Grille plane dont chaque bande de faces possede sa propre copie des sommets.

    Les positions sont strictement identiques entre les copies: c'est exactement
    l'artefact de duplication de TRELLIS, et non un vrai decalage geometrique.
    """
    import trimesh

    xs, ys = np.meshgrid(np.linspace(0, 1, n + 1), np.linspace(0, 1, n + 1))
    pos = np.column_stack([xs.ravel(), ys.ravel(), np.zeros((n + 1) ** 2)])
    uv = pos[:, :2].copy()

    verts, uvs, faces = [], [], []
    for j in range(n):
        for i in range(n):
            quad = (j * (n + 1) + i, j * (n + 1) + i + 1,
                    (j + 1) * (n + 1) + i + 1, (j + 1) * (n + 1) + i)
            base = len(verts)
            verts.extend(pos[list(quad)])
            uvs.extend(uv[list(quad)])
            faces.append([base, base + 1, base + 2])
            faces.append([base, base + 2, base + 3])

    m = trimesh.Trimesh(vertices=np.array(verts), faces=np.array(faces), process=False)
    m.visual = trimesh.visual.TextureVisuals(uv=np.array(uvs, dtype=np.float64))
    return m


class TestWeldFragmentedMesh(unittest.TestCase):
    def _roundtrip(self, mesh):
        tmp = Path(tempfile.mkdtemp())
        src = tmp / "fragmente.glb"
        dst = tmp / "soude.glb"
        mesh.export(str(src))
        before = hashlib.sha256(src.read_bytes()).hexdigest()
        report = weld_mesh(str(src), str(dst))
        return src, dst, report, before

    def test_weld_reduit_la_fragmentation(self):
        mesh = _make_fragmented_grid()
        comps_before, frag_before, faces_before = _fragments(mesh)
        self.assertGreater(comps_before, 10, "le maillage de test doit etre fragmente")
        self.assertGreater(frag_before, 0.9)

        _, dst, report, _ = self._roundtrip(mesh)
        self.assertTrue(report["ok"], report.get("reason"))
        self.assertEqual(report["components_after"], 1, "la grille doit redevenir connexe")
        self.assertLess(report["fragment_after"], 0.05)
        self.assertEqual(report["faces_before"], faces_before)

    def test_uv_preservees_et_alignees(self):
        mesh = _make_fragmented_grid()
        _, dst, report, _ = self._roundtrip(mesh)
        self.assertTrue(report["ok"], report.get("reason"))

        import trimesh

        out = trimesh.load(str(dst), process=False, force="mesh")
        uv = getattr(out.visual, "uv", None)
        self.assertIsNotNone(uv, "les UV ne doivent pas disparaitre")
        self.assertEqual(len(uv), len(out.vertices), "UV desynchronisees des sommets")
        self.assertTrue(report["uv_preserved"])

    def test_entree_intacte_et_fichier_ecrit(self):
        mesh = _make_fragmented_grid()
        src, dst, report, digest_before = self._roundtrip(mesh)
        self.assertTrue(report["ok"], report.get("reason"))
        self.assertEqual(hashlib.sha256(src.read_bytes()).hexdigest(), digest_before,
                         "l'original doit rester intact (operation non destructive)")
        self.assertTrue(dst.exists() and dst.stat().st_size > 0)

    def test_refus_ecrasement_entree(self):
        mesh = _make_fragmented_grid()
        tmp = Path(tempfile.mkdtemp())
        src = tmp / "fragmente.glb"
        mesh.export(str(src))
        with self.assertRaises(ValueError):
            weld_mesh(str(src), str(src))

    def test_pertes_de_faces_bornees(self):
        mesh = _make_fragmented_grid()
        _, _, report, _ = self._roundtrip(mesh)
        lost = report["faces_before"] - report["faces_after"]
        self.assertGreaterEqual(lost, 0)
        self.assertLessEqual(lost, int(report["faces_before"] * 0.005),
                             "trop de faces perdues pour etre une simple reindexation")


class TestWeldGate(unittest.TestCase):
    """Un maillage deja connexe ne doit PAS etre reecrit par le pipeline."""

    def test_maillage_deja_connexe_laisse_intact(self):
        import trimesh

        sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "application/python-services"))
        from optimize_textured_mesh import _weld_fragmented

        tmp = Path(tempfile.mkdtemp())
        src, dst = tmp / "sain.glb", tmp / "sain_soude.glb"
        m = trimesh.creation.icosphere(subdivisions=2)
        m.export(str(src))

        log: list = []
        applied = _weld_fragmented(str(src), str(dst), log)
        self.assertFalse(applied, "un maillage deja connexe ne doit pas etre reecrit")
        self.assertFalse(dst.exists())
        self.assertTrue(any(s.get("stage") == "weld" and s.get("skipped") for s in log), log)


if __name__ == "__main__":
    unittest.main(verbosity=2)
