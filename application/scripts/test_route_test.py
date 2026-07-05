"""Tests for application/scripts/route_test.py — guards the regex parity
with `routePipeline()` in `application/src/services/threeDIntent.ts`.

When you change a regex literal in either file, update both AND run this
test (or `python application/scripts/test_route_test.py`).
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parent))
from route_test import evaluate, route_pipeline  # noqa: E402


class Cat1LuxuryMaterialsTests(unittest.TestCase):
    """v78j fix: PC boitier with luxury material descriptors must prefer
    DreamGaussian over the Hunyuan3D default."""

    def test_quartz_fume_routes_dreamgaussian(self):
        out = evaluate(
            "boitier PC quartz fumé translucide, lotus or rose, obsidienne, acajou nordique"
        )
        self.assertTrue(out["flags"]["luxury_material"], "luxury material flag must trip")
        self.assertTrue(out["dreamgaussianPreferred"])

    def test_obsidienne_only(self):
        out = evaluate("statuette obsidienne lisse")
        self.assertTrue(out["flags"]["luxury_material"])
        self.assertTrue(out["dreamgaussianPreferred"])

    def test_or_rose_only(self):
        out = evaluate("bracelet or rose élégant")
        self.assertTrue(out["flags"]["luxury_material"])
        self.assertTrue(out["dreamgaussianPreferred"])

    def test_marbre_blanc(self):
        out = evaluate("vase en marbre blanc")
        self.assertTrue(out["flags"]["luxury_material"])
        self.assertTrue(out["dreamgaussianPreferred"])

    def test_chrome_brosse_diacritic(self):
        out = evaluate("Lampe en chrome brossé moderne")
        self.assertTrue(out["flags"]["luxury_material"])


class NoFalsePositiveTests(unittest.TestCase):
    """The luxury detector must not over-trigger on generic prompts —
    otherwise plain Hunyuan3D objects would be force-routed to DreamGaussian
    (slower, lower fidelity for non-stylized cases)."""

    def test_plain_sphere(self):
        out = evaluate("a red sphere")
        self.assertFalse(out["flags"]["luxury_material"])
        self.assertFalse(out["dreamgaussianPreferred"])

    def test_plain_pc_case(self):
        out = evaluate("boitier PC standard noir")
        self.assertFalse(out["flags"]["luxury_material"])
        self.assertFalse(out["dreamgaussianPreferred"])

    def test_generic_product(self):
        out = evaluate("a wooden chair")
        self.assertFalse(out["flags"]["luxury_material"])
        self.assertFalse(out["dreamgaussianPreferred"])


class StyizedKeepsRoutingTests(unittest.TestCase):
    """Pre-v78j stylized routing (anime/manga/cartoon) must still route
    to DreamGaussian — the new luxury bucket is purely additive."""

    def test_manga_character(self):
        out = evaluate("manga character running through forest")
        self.assertTrue(out["flags"]["stylized"])
        self.assertTrue(out["dreamgaussianPreferred"])

    def test_lowpoly_voxel(self):
        out = evaluate("lowpoly voxel village scene")
        self.assertTrue(out["flags"]["stylized"])


class MechanismKeepsRoutingTests(unittest.TestCase):

    def test_belt_pulley(self):
        out = evaluate("courroie de transmission avec poulie")
        self.assertTrue(out["flags"]["mechanism"])
        self.assertIn("procedural", out["probable_pipeline"])

    def test_hinge(self):
        out = evaluate("hinge joint with bracket")
        self.assertTrue(out["flags"]["mechanism"])


class StrimerRoutingTests(unittest.TestCase):

    def test_strimer_plus_v2_routes_to_dedicated_template(self):
        out = route_pipeline("Lian Li Strimer Plus V2 24-pin RGB cable chenillard")
        self.assertEqual(out["pipeline"], "procedural")
        self.assertEqual(out["procedural_template"], "strimer_plus_v2_cable")


class CharacterMotionRoutingTests(unittest.TestCase):

    def test_character_macarena_routes_to_ai_human_fidelity(self):
        out = route_pipeline(
            "personnage original colore qui danse la Macarena",
            purpose="character",
            subject_kind="character",
        )
        self.assertEqual(out["pipeline"], "ai_generation")
        self.assertIsNone(out["procedural_template"])
        self.assertTrue(out["flags"]["human_fidelity"])
        self.assertTrue(out["flags"]["hand_fidelity"])

    def test_explicit_procedural_character_keeps_humanoid_performer(self):
        out = route_pipeline(
            "mannequin procedural generique qui danse la Macarena pour test rig",
            purpose="character",
            subject_kind="character",
        )
        self.assertEqual(out["pipeline"], "procedural")
        self.assertEqual(out["procedural_template"], "humanoid_performer")
        self.assertFalse(out["flags"]["human_fidelity"])

    def test_named_real_person_dance_does_not_use_generic_performer(self):
        out = route_pipeline(
            "Emmanuel Macron realiste qui danse la Macarena",
            purpose="character",
            subject_kind="character",
        )
        self.assertEqual(out["pipeline"], "ai_generation")
        self.assertIsNone(out["procedural_template"])
        self.assertTrue(out["dreamgaussianPreferred"])

    def test_named_real_person_floss_routes_to_ai_human_hand_fidelity(self):
        out = route_pipeline(
            "Emmanuel Macron realiste qui fait le floss, mains et doigts visibles",
            purpose="character",
            subject_kind="character",
        )
        self.assertEqual(out["pipeline"], "ai_generation")
        self.assertIsNone(out["procedural_template"])
        self.assertTrue(out["flags"]["known_character"])
        self.assertTrue(out["flags"]["human_fidelity"])
        self.assertTrue(out["flags"]["hand_fidelity"])
        self.assertTrue(out["dreamgaussianPreferred"])

    def test_explicit_procedural_floss_can_keep_humanoid_performer(self):
        out = route_pipeline(
            "mannequin procedural generique qui fait le floss pour test rig",
            purpose="character",
            subject_kind="character",
        )
        self.assertEqual(out["pipeline"], "procedural")
        self.assertEqual(out["procedural_template"], "humanoid_performer")
        self.assertFalse(out["flags"]["human_fidelity"])

    def test_non_anime_does_not_trigger_stylized_flag(self):
        out = route_pipeline(
            "Emmanuel Macron realiste en rendu non-anime",
            purpose="character",
            subject_kind="character",
        )
        self.assertFalse(out["flags"]["stylized"])
        self.assertEqual(out["pipeline"], "ai_generation")
        self.assertIsNone(out["procedural_template"])

    def test_named_anime_character_dance_does_not_use_generic_performer(self):
        out = route_pipeline(
            "Lucy Heartfilia de Fairy Tail en anime qui danse la Macarena",
            purpose="character",
            subject_kind="character",
        )
        self.assertEqual(out["pipeline"], "ai_generation")
        self.assertIsNone(out["procedural_template"])
        self.assertTrue(out["dreamgaussianPreferred"])


class PhotogrammetryRoutingTests(unittest.TestCase):

    def test_scan_keyword(self):
        out = evaluate("8 photos d'un château pour scan 3D photogrammétrie")
        self.assertTrue(out["flags"]["photogrammetry"])
        self.assertIn("photogrammetry", out["probable_pipeline"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
