"""Prompt contracts, with no GPU or generated-image quality claims."""
from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path

SERVICES = Path(__file__).resolve().parents[1] / "application" / "python-services"


def load_director():
    spec = importlib.util.spec_from_file_location("human_prompt_director", SERVICES / "human_prompt_director.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class PromptContractTests(unittest.TestCase):
    def setUp(self):
        self.director = load_director()

    def test_isolated_anime_preserves_subject_and_does_not_invent_sky(self):
        brief = "Anime illustration of Natsu Dragneel, pink hair, white scarf, holding a rifle, full-body character on a plain white background"
        result = self.director.direct_prompt(brief)
        self.assertIn(brief, result["human_prompt"])
        self.assertEqual(result["requested_background"], "white")
        self.assertLess(result["width"], result["height"])
        for invented in ("Ghibli", "Shinkai", "clouds", "atmospheric sky"):
            self.assertNotIn(invented, result["human_prompt"])

    def test_uniform_background_overrides_conflicting_style_decor(self):
        for brief, color in [("Icône de potion sur fond blanc uni", "white"),
                             ("personnage cyberpunk sur fond bleu uniforme", "blue"),
                             ("portrait Pixar on a solid black background", "black")]:
            with self.subTest(brief=brief):
                result = self.director.direct_prompt(brief)
                self.assertEqual(result["requested_background"], color)
                self.assertIn(brief, result["human_prompt"])
                for invented in ("dark slate", "rain-slicked asphalt", "out-of-focus background"):
                    self.assertNotIn(invented, result["human_prompt"])

    def test_requested_setting_is_retained(self):
        brief = "Anime character in a forest with blue sky and clouds"
        result = self.director.direct_prompt(brief)
        self.assertIn(brief, result["human_prompt"])
        self.assertNotIn("requested_background", result)
        self.assertNotIn("Ghibli", result["human_prompt"])

    def test_negative_background_clause_is_not_a_positive_request(self):
        for brief in ("Anime character, avoid a white background", "portrait sans fond blanc"):
            self.assertNotIn("requested_background", self.director.direct_prompt(brief))

    def test_explicit_ratio_takes_priority_over_full_body_default(self):
        result = self.director.direct_prompt("Anime full-body character, image 16:9")
        self.assertEqual(result["aspect_ratio"], "16:9")
        self.assertGreater(result["width"], result["height"])

    def test_forced_category_controls_prompt_and_invalid_category_is_rejected(self):
        result = self.director.direct_prompt("A red fox", force_category="stylized_watercolor")
        self.assertEqual(result["category"], "stylized_watercolor")
        self.assertIn("watercolor", result["human_prompt"])
        self.assertIn("red fox", result["human_prompt"])
        with self.assertRaises(ValueError):
            self.director.direct_prompt("A red fox", force_category="unsupported")

    def test_game_prop_does_not_lose_original_subject(self):
        result = self.director.direct_prompt("A low poly prop of a wooden bench, front view")
        self.assertEqual(result["category"], "game_asset_3d_prop")
        self.assertIn("wooden bench, front view", result["human_prompt"])
        self.assertNotIn("isometric", result["human_prompt"])

    def test_subject_folder_does_not_classify_character_by_carried_weapon(self):
        # Load just this pure routing function: CI deliberately needs no Pillow/NumPy.
        import ast
        source = ast.parse((SERVICES / "image_module_engine.py").read_text(encoding="utf-8"))
        function = next(node for node in source.body if isinstance(node, ast.FunctionDef) and node.name == "resolve_main_folder")
        import re
        namespace = {"re": re, "strip_accents": self.director.strip_accents}
        exec(compile(ast.Module(body=[function], type_ignores=[]), "image-routing", "exec"), namespace)
        route = namespace["resolve_main_folder"]
        self.assertEqual(route("stylized_anime_ghibli", "Natsu, a character carrying a weapon"), "perso")
        self.assertEqual(route("stylized_pixar_3d", "Personnage avec une arme"), "perso")
        self.assertEqual(route("game_asset_icon_ui", "icon of a character"), "assets")
        self.assertEqual(route("stylized_anime_ghibli", "city landscape"), "decor")


if __name__ == "__main__":
    unittest.main()
