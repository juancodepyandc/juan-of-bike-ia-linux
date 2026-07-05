#!/usr/bin/env python
"""Unit tests for faithful_scene_prompt — the compound-scene fidelity composer.

Run: python -m unittest test_faithful_scene_prompt -v
Pure stdlib (unittest), no network, no GPU.
"""

from __future__ import annotations

import unittest

from faithful_scene_prompt import (
    compose_faithful_prompt,
    detect_facets,
    refine_subject_kind,
)


COMPLEX_PROMPT = (
    "Keanu Reeves en tenue de motard cyberpunk, debout près d'une moto futuriste "
    "à réacteur, dans une ruelle néo-tokyo sous la pluie battante ; des néons "
    "roses et bleus se reflètent dans les flaques, de la vapeur s'échappe des "
    "bouches d'égout, des étincelles jaillissent d'un bras mécanique articulé qui "
    "répare la moto, de l'eau ruisselle le long de sa veste, une hélice de turbine "
    "tourne sur le flanc du véhicule, son blouson de cuir noir reflète les néons."
)


class TestFacetDetection(unittest.TestCase):
    def test_complex_scene_detects_all_families(self):
        a = detect_facets(COMPLEX_PROMPT, "il lève le poing puis salue")
        self.assertTrue(a["compound"])
        for family in ("decor", "mechanical", "fluids", "luminous", "motion"):
            self.assertIn(family, a["families"], f"missing facet: {family}")

    def test_identity_is_extracted(self):
        a = detect_facets(COMPLEX_PROMPT)
        self.assertIsNotNone(a["identity"])
        self.assertEqual(a["identity"]["name"], "Keanu Reeves")

    def test_luminous_handles_french_plurals(self):
        # Regression: trailing \b previously dropped "néons"/"étincelles" plurals,
        # silently losing the whole luminous facet.
        a = detect_facets("des néons roses et des étincelles dorées")
        self.assertIn("luminous", a["families"])

    def test_fluids_handles_plurals(self):
        a = detect_facets("des flaques d'eau et des gouttes de pluie")
        self.assertIn("fluids", a["families"])

    def test_french_verb_conjugations_are_caught(self):
        # Regression: "tournent" (3rd-person plural), "oscille", "bioluminescents",
        # "éclairent" previously slipped past the trailing \b and dropped the
        # motion / luminous facets entirely.
        a = detect_facets(
            "des engrenages tournent, le balancier oscille, des cristaux "
            "bioluminescents éclairent la caverne, de l'eau ruisselle"
        )
        self.assertIn("motion", a["families"])
        self.assertIn("luminous", a["families"])

    def test_no_overmatch_on_innocuous_words(self):
        # Stems must not fire on unrelated words: a plain still-life prompt has
        # no motion/luminous facet.
        a = detect_facets("a wooden bowl of oranges on a marble table")
        self.assertNotIn("motion", a["families"])
        self.assertNotIn("luminous", a["families"])

    def test_english_compound_scene(self):
        a = detect_facets(
            "Albert Einstein standing in a neon-lit workshop, steam rising, "
            "a spinning brass gear turbine, sparks flying, water dripping"
        )
        self.assertTrue(a["compound"])
        for family in ("decor", "mechanical", "fluids", "luminous", "motion"):
            self.assertIn(family, a["families"])


class TestComposer(unittest.TestCase):
    def test_compound_prompt_gets_contract(self):
        out = compose_faithful_prompt(COMPLEX_PROMPT,
                                      subject_kind="character",
                                      motion_prompt="il lève le poing")
        self.assertTrue(out["applied"])
        self.assertIn("MULTI-ELEMENT FIDELITY CONTRACT", out["prompt"])
        self.assertIn("Keanu Reeves", out["prompt"])
        # The verbatim user prompt must remain at the front untouched.
        self.assertTrue(out["prompt"].startswith("Keanu Reeves en tenue de motard"))

    def test_contract_names_every_requested_element(self):
        out = compose_faithful_prompt(COMPLEX_PROMPT)
        contract = " ".join(out["contract_lines"]).lower()
        for needle in ("identity", "decor", "mechanical", "fluid", "luminous", "motion"):
            self.assertIn(needle, contract, f"contract missing: {needle}")

    def test_simple_prompt_is_noop(self):
        out = compose_faithful_prompt("a red ceramic coffee mug")
        self.assertFalse(out["applied"])
        self.assertEqual(out["prompt"], "a red ceramic coffee mug")
        self.assertNotIn("MULTI-ELEMENT", out["prompt"])

    def test_single_subject_character_is_noop(self):
        out = compose_faithful_prompt("a fantasy elf warrior with a sword")
        self.assertFalse(out["applied"])


class TestKindRescue(unittest.TestCase):
    def test_named_human_on_vehicle_becomes_character(self):
        r = refine_subject_kind(COMPLEX_PROMPT, "vehicle",
                                "il lève le poing")
        self.assertTrue(r["changed"])
        self.assertEqual(r["kind"], "character")

    def test_branded_product_is_not_humanized(self):
        # "Lian Li" is a two-token proper name but there's no human signal:
        # a cable must never be rescued into a character.
        r = refine_subject_kind(
            "Lian Li Strimer Plus V2 24-pin RGB extension cable", "generic")
        self.assertFalse(r["changed"])
        self.assertEqual(r["kind"], "generic")

    def test_existing_organic_kind_is_preserved(self):
        r = refine_subject_kind(COMPLEX_PROMPT, "humanoid")
        self.assertFalse(r["changed"])
        self.assertEqual(r["kind"], "humanoid")

    def test_no_identity_no_rescue(self):
        r = refine_subject_kind("a sports car on a track", "vehicle")
        self.assertFalse(r["changed"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
