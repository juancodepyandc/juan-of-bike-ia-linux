"""Tests for mesh_batch_rescue.py — exercise the full chain on a synthetic
two-run directory and on the live Cat 1 setup.
"""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parent))
from mesh_batch_rescue import (  # noqa: E402
    batch_rescue, read_sidecar_prompt,
)


REPO_ROOT = Path(__file__).resolve().parents[2]
CAT1_REF  = REPO_ROOT / "application" / "output" / "3d" / "juan_bike_1777509822533_reference.png"
CAT1_MESH = REPO_ROOT / "application" / "output" / "3d" / "juan_bike_1777509822533_mesh.glb"


class SidecarPromptTests(unittest.TestCase):

    def test_reads_sidecar_when_present(self):
        with tempfile.TemporaryDirectory() as td:
            d = Path(td)
            (d / "x_prompt.txt").write_text("hello world", encoding="utf-8")
            self.assertEqual(read_sidecar_prompt("x", d), "hello world")

    def test_returns_none_when_missing(self):
        with tempfile.TemporaryDirectory() as td:
            self.assertIsNone(read_sidecar_prompt("nope", Path(td)))


class BatchRescueLiveTests(unittest.TestCase):
    """Run on the actual repo's output/3d. Should rescue Cat 1 successfully
    and skip the run that has only synthetic seeds (no mesh)."""

    def test_cat1_rescued_others_skipped(self):
        if not CAT1_MESH.is_file() or not CAT1_REF.is_file():
            self.skipTest("Cat 1 ref/mesh not present")
        source = REPO_ROOT / "application" / "output" / "3d"
        with tempfile.TemporaryDirectory() as td:
            result = batch_rescue(source, Path(td), "boitier PC quartz fume")
            self.assertTrue(result["ok"])
            self.assertEqual(result["schema"], "aurora.batch_rescue.v1")
            self.assertGreaterEqual(result["rescued_count"], 1)
            cat1 = next((r for r in result["rescued"]
                         if "1777509822533" in r["run_id"]), None)
            self.assertIsNotNone(cat1, "Cat 1 must be in rescued list")
            self.assertTrue(cat1["ok"])
            self.assertGreaterEqual(cat1["score_delta"], 15.0)


class BatchRescueErrorTests(unittest.TestCase):

    def test_missing_source_dir(self):
        with tempfile.TemporaryDirectory() as td:
            result = batch_rescue(Path("/nonexistent/aurora"), Path(td))
            self.assertFalse(result["ok"])
            self.assertIn("not found", result["error"])

    def test_empty_source_dir(self):
        with tempfile.TemporaryDirectory() as src:
            with tempfile.TemporaryDirectory() as out:
                result = batch_rescue(Path(src), Path(out))
                self.assertTrue(result["ok"])
                self.assertEqual(result["rescued_count"], 0)
                self.assertEqual(result["skipped_count"], 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
