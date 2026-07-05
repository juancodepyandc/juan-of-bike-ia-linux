"""Tests for bake_vertex_colors.py — verify color restoration on Cat 1 GLB."""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parent))
from bake_vertex_colors import bake, KIND_PROJECTION  # noqa: E402
from mesh_quality_score import score_mesh  # noqa: E402


REPO_ROOT = Path(__file__).resolve().parents[2]
CAT1_REF  = REPO_ROOT / "application" / "output" / "3d" / "juan_bike_1777509822533_reference.png"
CAT1_MESH = REPO_ROOT / "application" / "output" / "3d" / "juan_bike_1777509822533_mesh.glb"


class BakeOutputTests(unittest.TestCase):

    def test_kind_projection_table_complete(self):
        # Every kind from mesh_quality_score must have a projection mapping.
        from mesh_quality_score import KIND_ASPECT
        missing = [k for k in KIND_ASPECT if k not in KIND_PROJECTION]
        self.assertFalse(missing, f"missing projection axes for: {missing}")

    def test_cat1_bake_produces_richer_palette(self):
        if not CAT1_REF.is_file() or not CAT1_MESH.is_file():
            self.skipTest("Cat 1 ref/mesh not present")
        with tempfile.TemporaryDirectory() as td:
            out = Path(td) / "baked.glb"
            result = bake(CAT1_MESH, CAT1_REF, out, "pc_tower")
            self.assertTrue(result["ok"], result.get("error"))
            self.assertEqual(result["schema"], "aurora.color_bake.v1")
            # Original mesh had 1 unique color. Baked should have hundreds at minimum.
            self.assertGreater(result["baked_unique_colors"], 1000,
                               "bake must restore palette richness")
            self.assertGreater(result["baked_variance"], 100)
            self.assertTrue(out.is_file())

    def test_cat1_baked_passes_color_axis(self):
        if not CAT1_REF.is_file() or not CAT1_MESH.is_file():
            self.skipTest("Cat 1 ref/mesh not present")
        with tempfile.TemporaryDirectory() as td:
            out = Path(td) / "baked.glb"
            bake_result = bake(CAT1_MESH, CAT1_REF, out, "pc_tower")
            self.assertTrue(bake_result["ok"])
            # Score the baked mesh: color_richness must rebound from 0 to 100.
            score = score_mesh(out, "pc_tower")
            self.assertTrue(score["ok"])
            self.assertEqual(score["scores"]["color_richness"]["score"], 100,
                             "baked mesh must hit max color_richness")
            # Overall must improve significantly (was 70.2, expect 88+).
            self.assertGreater(score["overall_score"], 85)


class MultiZoneBakeTests(unittest.TestCase):
    """Multi-zone uses vertex normals to classify front/side/back, resample
    back with mirrored U, and produce visually distinct zones."""

    def test_zone_breakdown_returned(self):
        if not CAT1_REF.is_file() or not CAT1_MESH.is_file():
            self.skipTest("Cat 1 ref/mesh not present")
        with tempfile.TemporaryDirectory() as td:
            out = Path(td) / "mz.glb"
            result = bake(CAT1_MESH, CAT1_REF, out, "pc_tower", multi_zone=True)
            self.assertTrue(result["ok"], result.get("error"))
            self.assertTrue(result["multi_zone"])
            zb = result["zone_breakdown"]
            self.assertIsNotNone(zb)
            self.assertGreater(zb["front"], 0)
            self.assertGreater(zb["side"], 0)
            self.assertGreater(zb["back"], 0)
            total = zb["front"] + zb["side"] + zb["back"]
            self.assertEqual(total, result["vertex_count"])

    def test_single_view_has_no_zone_breakdown(self):
        if not CAT1_REF.is_file() or not CAT1_MESH.is_file():
            self.skipTest("Cat 1 ref/mesh not present")
        with tempfile.TemporaryDirectory() as td:
            out = Path(td) / "single.glb"
            result = bake(CAT1_MESH, CAT1_REF, out, "pc_tower", multi_zone=False)
            self.assertTrue(result["ok"])
            self.assertFalse(result["multi_zone"])
            self.assertIsNone(result["zone_breakdown"])


class ProjectionAxesTests(unittest.TestCase):

    def test_pc_tower_uses_xy_front_view(self):
        # PC towers face the camera flat — X-right, Y-up, Z-depth.
        u, v, d = KIND_PROJECTION["pc_tower"]
        self.assertEqual((u, v, d), (0, 1, 2))

    def test_quadruped_uses_zy_side_view(self):
        # Quadrupeds are wider on Z (long body), so project ZY.
        u, v, d = KIND_PROJECTION["quadruped"]
        self.assertEqual((u, v, d), (2, 1, 0))


if __name__ == "__main__":
    unittest.main(verbosity=2)
