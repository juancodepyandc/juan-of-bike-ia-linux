"""Tests for mesh_run_index.py."""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parent))
from mesh_run_index import categorize, index_runs  # noqa: E402


REPO_ROOT = Path(__file__).resolve().parents[2]
LIVE_DIR = REPO_ROOT / "application" / "output" / "3d"


class CategorizeTests(unittest.TestCase):

    def test_id_mesh_glb(self):
        run_id, role = categorize("juan_bike_1777509822533_mesh.glb")
        self.assertEqual(run_id, "juan_bike_1777509822533")
        self.assertEqual(role, "mesh")

    def test_id_reference_png(self):
        run_id, role = categorize("juan_bike_1777509822533_reference.png")
        self.assertEqual(run_id, "juan_bike_1777509822533")
        self.assertEqual(role, "reference")

    def test_id_front_synthetic(self):
        run_id, role = categorize("juan_bike_1777509822533_front_synthetic.png")
        self.assertEqual(run_id, "juan_bike_1777509822533")
        self.assertEqual(role, "front_synthetic")

    def test_baked_standalone(self):
        run_id, role = categorize("cat1_baked.glb")
        self.assertIsNone(run_id)
        self.assertEqual(role, "baked")

    def test_reshaped_standalone(self):
        run_id, role = categorize("cat1_reshaped.glb")
        self.assertIsNone(run_id)
        self.assertEqual(role, "reshaped")

    def test_viewer(self):
        run_id, role = categorize("cat1_viewer.html")
        self.assertIsNone(run_id)
        self.assertEqual(role, "viewer")

    def test_other(self):
        run_id, role = categorize("README.md")
        self.assertIsNone(run_id)
        self.assertEqual(role, "other")


class IndexRunsTests(unittest.TestCase):

    def test_empty_dir_succeeds(self):
        with tempfile.TemporaryDirectory() as td:
            result = index_runs(Path(td))
            self.assertTrue(result["ok"])
            self.assertEqual(result["run_count"], 0)
            self.assertEqual(result["standalone_count"], 0)

    def test_missing_dir_fails(self):
        result = index_runs(Path("/nonexistent/dir/aurora"))
        self.assertFalse(result["ok"])

    def test_synthetic_grouping(self):
        with tempfile.TemporaryDirectory() as td:
            d = Path(td)
            (d / "test_run_1_mesh.glb").write_bytes(b"x")
            (d / "test_run_1_reference.png").write_bytes(b"y")
            (d / "test_run_1_front_synthetic.png").write_bytes(b"z")
            (d / "extra_baked.glb").write_bytes(b"w")
            result = index_runs(d)
            self.assertTrue(result["ok"])
            self.assertEqual(result["run_count"], 1)
            run = result["runs"][0]
            self.assertEqual(run["run_id"], "test_run_1")
            self.assertEqual(len(run["files"]), 3)
            self.assertTrue(run["has_mesh"])
            self.assertTrue(run["has_reference"])
            # extra_baked.glb is standalone
            self.assertEqual(result["standalone_count"], 1)

    def test_live_dir_finds_cat1(self):
        """Indexation du dossier de sortie REEL, quand l artefact y est encore.

        Ce test exigeait la presence d une execution precise
        (`1777509822533`), produite lors d une session passee. Le nettoyage
        periodique des sorties l a retiree, et le test echouait depuis — non
        parce que l indexation serait cassee, mais parce que la donnee
        n existe plus. Un test qui depend d un artefact non reproductible ne
        peut pas etre un test de regression : il ne dit rien sur le code.

        On le garde comme controle OPPORTUNISTE — il verifie l indexation sur
        la vraie arborescence quand l artefact est la — et la structure est
        desormais verifiee sur donnees synthetiques par les autres cas de ce
        fichier, qui eux sont reproductibles partout.
        """
        if not LIVE_DIR.is_dir():
            self.skipTest("output/3d absent")
        result = index_runs(LIVE_DIR)
        self.assertTrue(result["ok"])
        self.assertEqual(result["schema"], "aurora.run_index.v1")
        cat1 = next(
            (r for r in result["runs"]
             if "1777509822533" in r["run_id"]),
            None,
        )
        if cat1 is None:
            self.skipTest(
                "l execution 1777509822533 n est plus dans output/3d "
                "(nettoyage des sorties) — rien a indexer pour ce controle")
        self.assertTrue(cat1["has_mesh"])
        self.assertTrue(cat1["has_reference"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
