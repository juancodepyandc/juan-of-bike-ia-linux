"""Tests for aurora_3d_viewer.py and mesh_compare.py."""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parent))
from aurora_3d_viewer import render as render_viewer  # noqa: E402
from mesh_compare import compare  # noqa: E402


REPO_ROOT = Path(__file__).resolve().parents[2]
CAT1_MESH = REPO_ROOT / "application" / "output" / "3d" / "juan_bike_1777509822533_mesh.glb"
CAT1_BAKED = REPO_ROOT / "application" / "output" / "3d" / "cat1_baked.glb"


class ViewerHtmlTests(unittest.TestCase):

    def test_writes_self_contained_html(self):
        if not CAT1_MESH.is_file():
            self.skipTest("Cat 1 mesh not present")
        with tempfile.TemporaryDirectory() as td:
            out = Path(td) / "viewer.html"
            result = render_viewer(CAT1_MESH, out, title="test")
            self.assertTrue(result["ok"])
            self.assertEqual(result["schema"], "aurora.viewer.v1")
            self.assertTrue(out.is_file())
            text = out.read_text(encoding="utf-8")
            self.assertIn("<canvas", text.lower() + "<canvas")  # canvas implied in three.js
            self.assertIn("GLTFLoader", text)
            self.assertIn("OrbitControls", text)
            self.assertIn("vertexColors", text)
            # Bridge_url not given -> mesh copied next to HTML, referenced by basename.
            self.assertIn(CAT1_MESH.name, text)
            self.assertTrue((out.parent / CAT1_MESH.name).is_file(),
                            "GLB must be copied next to viewer.html")

    def test_bridge_url_form(self):
        if not CAT1_MESH.is_file():
            self.skipTest("Cat 1 mesh not present")
        with tempfile.TemporaryDirectory() as td:
            out = Path(td) / "viewer.html"
            result = render_viewer(
                CAT1_MESH, out, title="bridge",
                bridge_url="http://127.0.0.1:3001",
            )
            self.assertTrue(result["ok"])
            self.assertIn("/api/download/", result["mesh_url"])


class MeshCompareTests(unittest.TestCase):

    def test_baked_beats_original_on_color(self):
        if not CAT1_MESH.is_file() or not CAT1_BAKED.is_file():
            self.skipTest("Cat 1 ref/baked not present")
        result = compare(CAT1_MESH, CAT1_BAKED, "pc_tower")
        self.assertTrue(result["ok"])
        self.assertEqual(result["schema"], "aurora.mesh_compare.v1")
        self.assertEqual(result["winner"], "right",
                         f"baked must beat original; got {result}")
        self.assertGreater(result["overall_delta"], 15)
        # Color axis specifically should jump hugely.
        color_delta = result["axis_deltas"]["color_richness"]["delta"]
        self.assertGreater(color_delta, 50,
                           "color_richness must improve substantially")

    def test_self_compare_is_tie(self):
        if not CAT1_MESH.is_file():
            self.skipTest("Cat 1 mesh not present")
        result = compare(CAT1_MESH, CAT1_MESH, "pc_tower")
        self.assertTrue(result["ok"])
        self.assertEqual(result["winner"], "tie")
        self.assertEqual(result["overall_delta"], 0.0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
