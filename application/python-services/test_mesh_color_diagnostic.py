"""Tests for mesh_color_diagnostic.py — verify the lossy-stage detection
on the real Cat 1 reference + mesh.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parent))
from mesh_color_diagnostic import diagnose, measure_image, measure_mesh  # noqa: E402


REPO_ROOT = Path(__file__).resolve().parents[2]
CAT1_REF  = REPO_ROOT / "application" / "output" / "3d" / "juan_bike_1777509822533_reference.png"
CAT1_MESH = REPO_ROOT / "application" / "output" / "3d" / "juan_bike_1777509822533_mesh.glb"


class MeasureImageTests(unittest.TestCase):

    def test_cat1_reference_has_many_colors(self):
        if not CAT1_REF.is_file():
            self.skipTest("Cat 1 reference not present")
        m = measure_image(CAT1_REF)
        self.assertNotIn("error", m)
        self.assertGreater(m["unique_colors"], 100,
                           "PC reference should have rich color palette")
        self.assertGreater(m["variance"], 1000)


class MeasureMeshTests(unittest.TestCase):

    def test_cat1_mesh_color_count(self):
        if not CAT1_MESH.is_file():
            self.skipTest("Cat 1 mesh not present")
        m = measure_mesh(CAT1_MESH)
        self.assertNotIn("error", m)
        # Per the v78u verdict, this mesh has exactly 1 unique color.
        self.assertEqual(m["unique_colors"], 1)
        self.assertEqual(m["variance"], 0.0)


class Cat1DiagnosticEndToEndTests(unittest.TestCase):

    def test_pinpoints_hunyuan3d(self):
        if not CAT1_REF.is_file() or not CAT1_MESH.is_file():
            self.skipTest("Cat 1 ref/mesh not present")
        result = diagnose(CAT1_REF, CAT1_MESH)
        self.assertTrue(result["ok"], result.get("error"))
        self.assertEqual(result["stage_lost"], "hunyuan3d",
                         f"v78u proved Hunyuan3D collapsed colors; got {result}")
        self.assertGreater(result["color_loss_ratio_ref_to_mesh"], 0.9)
        self.assertTrue(result["suggestions"],
                        "must produce actionable suggestions")

    def test_schema_constant(self):
        if not CAT1_REF.is_file() or not CAT1_MESH.is_file():
            self.skipTest("Cat 1 ref/mesh not present")
        result = diagnose(CAT1_REF, CAT1_MESH)
        self.assertEqual(result["schema"], "aurora.color_diagnostic.v1")


if __name__ == "__main__":
    unittest.main(verbosity=2)
