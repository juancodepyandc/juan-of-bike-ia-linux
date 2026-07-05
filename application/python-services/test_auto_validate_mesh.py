"""Tests for auto_validate_mesh.py — verify the autonomous loop produces
correct retry decisions. Run alongside test_mesh_quality_score.py.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parent))
from auto_validate_mesh import (  # noqa: E402
    auto_validate, primary_failure, recommend_next_pipeline, RETRY_GRAPH,
)
from subject_kind_extractor import extract_kind  # noqa: E402


REPO_ROOT = Path(__file__).resolve().parents[2]
CAT1_MESH = REPO_ROOT / "application" / "output" / "3d" / "juan_bike_1777509822533_mesh.glb"


class SubjectKindExtractionTests(unittest.TestCase):

    def test_pc_tower_match(self):
        out = extract_kind("boitier PC quartz fume translucide")
        self.assertEqual(out["kind"], "pc_tower")
        self.assertEqual(out["confidence"], 1.0)

    def test_humanoid_with_quadruped_alt(self):
        out = extract_kind("guerrier elfique sur cheval")
        self.assertEqual(out["kind"], "humanoid")
        self.assertIn("quadruped", out["alternatives"])

    def test_creature_dragon(self):
        out = extract_kind("dragon noir avec ailes dorees")
        self.assertEqual(out["kind"], "creature")

    def test_vehicle_brand(self):
        out = extract_kind("tesla model S noire")
        self.assertEqual(out["kind"], "vehicle")

    def test_gadget_iphone(self):
        out = extract_kind("iphone 15 pro")
        self.assertEqual(out["kind"], "gadget")

    def test_no_match_returns_generic(self):
        out = extract_kind("la chose bidule abstraction")
        self.assertEqual(out["kind"], "generic")
        self.assertEqual(out["confidence"], 0.0)

    def test_empty_prompt(self):
        out = extract_kind("")
        self.assertEqual(out["kind"], "generic")


class PrimaryFailureTests(unittest.TestCase):

    def test_color_wins_priority(self):
        self.assertEqual(
            primary_failure(["silhouette_aspect", "color_richness", "manifold_health"]),
            "color_richness",
        )

    def test_silhouette_when_no_color(self):
        self.assertEqual(
            primary_failure(["silhouette_aspect", "manifold_health"]),
            "silhouette_aspect",
        )

    def test_no_failures(self):
        self.assertIsNone(primary_failure([]))


class RetryGraphTests(unittest.TestCase):

    def test_hunyuan_color_failure_to_dreamgaussian(self):
        rec = recommend_next_pipeline("hunyuan3d", ["color_richness"])
        self.assertEqual(rec["next_pipeline"], "dreamgaussian")

    def test_hunyuan_aspect_failure_to_dreamgaussian(self):
        rec = recommend_next_pipeline("hunyuan3d", ["silhouette_aspect"])
        self.assertEqual(rec["next_pipeline"], "dreamgaussian")

    def test_hunyuan_manifold_to_postprocess(self):
        rec = recommend_next_pipeline("hunyuan3d", ["manifold_health"])
        self.assertEqual(rec["next_pipeline"], "mesh_postprocess")

    def test_dreamgaussian_to_procedural(self):
        rec = recommend_next_pipeline("dreamgaussian", ["color_richness"])
        self.assertEqual(rec["next_pipeline"], "procedural_or_multiview")

    def test_no_failures_returns_none(self):
        rec = recommend_next_pipeline("hunyuan3d", [])
        self.assertIsNone(rec["next_pipeline"])


class Cat1AutoValidateTests(unittest.TestCase):
    """End-to-end: feed Cat 1 prompt + mesh, verify retry decision."""

    def test_cat1_recommends_dreamgaussian(self):
        if not CAT1_MESH.is_file():
            self.skipTest("Cat 1 mesh not present")
        result = auto_validate(
            CAT1_MESH,
            "boitier PC quartz fume translucide, lotus or rose, obsidienne, acajou nordique",
            "hunyuan3d",
        )
        self.assertTrue(result["ok"], result.get("error"))
        self.assertEqual(result["extraction"]["kind"], "pc_tower")
        self.assertTrue(result["score"]["retry_recommended"])
        self.assertEqual(result["next_action"]["action"], "retry_pipeline")
        self.assertEqual(result["next_action"]["next_pipeline"], "dreamgaussian")

    def test_cat1_schema(self):
        if not CAT1_MESH.is_file():
            self.skipTest("Cat 1 mesh not present")
        result = auto_validate(CAT1_MESH, "boitier PC", "hunyuan3d")
        self.assertEqual(result["schema"], "aurora.auto_validate.v1")


if __name__ == "__main__":
    unittest.main(verbosity=2)
