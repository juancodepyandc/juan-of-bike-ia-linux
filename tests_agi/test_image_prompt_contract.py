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

    def test_animal_full_body_does_not_imply_an_upright_portrait(self):
        result = self.director.direct_prompt("Pink axolotl, full body, long tail, plain white background")
        self.assertEqual(result["aspect_ratio"], "1:1")
        closeup = self.director.direct_prompt("Close-up portrait of a woman on a solid black background")
        self.assertIn("Close-up", closeup["human_prompt"])
        self.assertNotIn("fully visible", closeup["human_prompt"])

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

    def test_french_character_spelling_sangoku_and_transformation_adaptation(self):
        result = self.director.direct_prompt("Sangoku en Super Saiyan Blue")
        self.assertEqual(result["category"], "stylized_anime_ghibli")
        self.assertIn("Super Saiyan Blue", result["human_prompt"])
        self.assertIn("cyan-blue", result["human_prompt"])
        self.assertNotIn("jet-black hair", result["human_prompt"])
        self.assertIn("realistic skin pores", result["negative_prompt"])

    def test_explicit_real_textures_override_switches_anime_character_to_hybrid_photoreal(self):
        result = self.director.direct_prompt("Sangoku avec des textures de personne réelle")
        self.assertEqual(result["category"], "photo_realistic")
        self.assertEqual(result["subject_ontology"]["effective_render_mode"], "hybrid_anime_with_real_textures")
        self.assertIn("photorealistic human skin pores", result["human_prompt"])
        self.assertNotIn("cartoon,", result["negative_prompt"])

    def test_negative_exclusion_clause_strips_forbidden_item_and_locks_negative_prompt(self):
        result = self.director.direct_prompt("Luffy sans chapeau tenant un sabre dans la main droite")
        self.assertEqual(result["category"], "stylized_anime_ghibli")
        self.assertIn("bareheaded", result["human_prompt"])
        self.assertIn("specifically in the right hand", result["human_prompt"])
        self.assertIn("hat", result["negative_prompt"])
        self.assertIn("straw hat", result["negative_prompt"])

    def test_open_world_entity_grounding_resolves_unhardcoded_characters(self):
        """The medium is inferred from the encyclopedic text, not from a list of names.

        The lookup is answered by recorded MediaWiki payloads: the test checks the inference, it does
        not depend on reaching Wikipedia (the CI cannot) nor on a cache left on one machine.
        """
        import io
        import json
        import tempfile
        import urllib.parse
        from unittest import mock

        import agi_core.prompt_intelligence as intelligence
        from agi_core.prompt_intelligence import analyze_and_direct_prompt

        recorded = {
            "spike": ("Spike Spiegel", "personnage de Cowboy Bebop",
                      "Spike Spiegel est un personnage de fiction et le protagoniste de la série "
                      "télévisée d'animation japonaise Cowboy Bebop, créée par Sunrise."),
            "rudeus": ("Rudeus Greyrat", "personnage de Mushoku Tensei",
                       "Rudeus Greyrat est le personnage principal du light novel et de l'anime "
                       "Mushoku Tensei, une série de fantasy japonaise."),
        }

        def answer(request, timeout=None):
            query = urllib.parse.parse_qs(urllib.parse.urlparse(request.full_url).query).get("gsrsearch", [""])[0].lower()
            pages = {}
            for key, (title, description, extract) in recorded.items():
                if key in query:
                    pages = {"1": {"index": 1, "title": title, "description": description, "extract": extract}}
            return io.BytesIO(json.dumps({"query": {"pages": pages}}).encode("utf-8"))

        with tempfile.TemporaryDirectory() as directory, \
                mock.patch.object(intelligence, "_OPEN_WORLD_CACHE_FILE", Path(directory) / "entities.json"), \
                mock.patch.dict(intelligence._MEMORY_ENTITY_CACHE, clear=True), \
                mock.patch.dict("os.environ", {"AURORA_DISABLE_OPEN_WORLD_LOOKUP": "0"}), \
                mock.patch.object(intelligence.urllib.request, "urlopen", side_effect=answer):
            self._assert_open_world_grounding(analyze_and_direct_prompt)

    def _assert_open_world_grounding(self, analyze_and_direct_prompt):
        spike = analyze_and_direct_prompt("fais-moi Spike Spiegel", target_module="image", open_world_grounding=True)
        self.assertEqual(spike["subject_ontology"], "anime_manga_character")
        self.assertEqual(spike["effective_render_mode"], "native_anime_stylized")
        self.assertIsNotNone(spike.get("open_world_entity"))

        rudeus = analyze_and_direct_prompt(
            "Rudeus Greyrat avec des textures de personne réelle",
            target_module="image",
            open_world_grounding=True,
        )
        self.assertEqual(rudeus["subject_ontology"], "anime_manga_character")
        self.assertEqual(rudeus["effective_render_mode"], "hybrid_anime_with_real_textures")


if __name__ == "__main__":
    unittest.main()
