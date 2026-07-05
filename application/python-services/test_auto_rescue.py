"""Tests for auto_rescue_mesh.py and mesh_reshape.py — full rescue chain
end-to-end on Cat 1.
"""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parent))
from auto_rescue_mesh import auto_rescue  # noqa: E402
from mesh_reshape import reshape, find_best_axis_mapping  # noqa: E402
from mesh_quality_score import score_mesh, KIND_ASPECT  # noqa: E402


REPO_ROOT = Path(__file__).resolve().parents[2]
CAT1_REF  = REPO_ROOT / "application" / "output" / "3d" / "juan_bike_1777509822533_reference.png"
CAT1_MESH = REPO_ROOT / "application" / "output" / "3d" / "juan_bike_1777509822533_mesh.glb"


class FindBestAxisMappingTests(unittest.TestCase):

    def test_identity_perm_when_already_sorted(self):
        perm, dist = find_best_axis_mapping([0.45, 1.0, 0.55], [0.45, 1.0, 0.55])
        self.assertEqual(perm, (0, 1, 2))
        self.assertEqual(dist, 0.0)

    def test_picks_swap_when_axes_differ(self):
        # Input axes are [width=Z, height=Y, depth=X], canonical is [X, Y, Z].
        perm, dist = find_best_axis_mapping([0.97, 1.0, 0.49], [0.45, 1.0, 0.55])
        self.assertLess(dist, 0.6)


class MeshReshapeTests(unittest.TestCase):

    def test_open_kind_skips(self):
        if not CAT1_MESH.is_file():
            self.skipTest("Cat 1 mesh not present")
        with tempfile.TemporaryDirectory() as td:
            out = Path(td) / "out.glb"
            result = reshape(CAT1_MESH, out, "sphere")
            self.assertTrue(result.get("skipped"))

    def test_pc_tower_brings_aspect_closer(self):
        if not CAT1_MESH.is_file():
            self.skipTest("Cat 1 mesh not present")
        with tempfile.TemporaryDirectory() as td:
            out = Path(td) / "out.glb"
            result = reshape(CAT1_MESH, out, "pc_tower", max_distortion=0.30)
            self.assertTrue(result["ok"])
            self.assertEqual(result["schema"], "aurora.mesh_reshape.v1")
            self.assertLess(result["aspect_l1_after"], 0.30,
                            "reshape must reduce aspect L1 distance")


class AutoRescueChainTests(unittest.TestCase):

    def test_cat1_full_chain_lifts_score(self):
        if not CAT1_REF.is_file() or not CAT1_MESH.is_file():
            self.skipTest("Cat 1 ref/mesh not present")
        with tempfile.TemporaryDirectory() as td:
            result = auto_rescue(
                CAT1_MESH, CAT1_REF,
                "boitier PC quartz fume translucide obsidienne acajou",
                Path(td),
            )
            self.assertTrue(result["ok"], result.get("error"))
            self.assertEqual(result["schema"], "aurora.auto_rescue.v1")
            self.assertEqual(result["extraction"]["kind"], "pc_tower")
            # Initial 70.2; final must lift by at least 15 points (color rescue).
            self.assertGreaterEqual(result["score_delta"], 15.0,
                                    f"rescue should lift score; got {result}")
            # color_richness must no longer fail after bake stage.
            self.assertNotIn("color_richness", result["final_failed_axes"])
            # Audit trail must record initial + bake + score_after_bake at minimum.
            stages = [a.get("stage") for a in result["audit_trail"]]
            self.assertIn("initial", stages)
            self.assertIn("bake_colors", stages)


if __name__ == "__main__":
    unittest.main(verbosity=2)
