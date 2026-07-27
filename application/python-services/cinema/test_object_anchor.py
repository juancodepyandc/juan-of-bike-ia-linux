#!/usr/bin/env python3
"""Garde de non-regression : ancrage d'objet explicite (`anchor_as_object`).

Contexte : un velo note 10/10/10/10 au plan 1 d'un film reel est revenu
meconnaissable au plan 5 (cadre deforme, roue elliptique, artefacts) parce que
sa reference canonique, meme lorsqu'elle existe, n'etait JAMAIS utilisee comme
ancre i2v — les entites "object-like" etaient ecartees a trois endroits, et la
porte `portrait_anchor_allowed` (concue pour les visages) bloquait le reste.

Ces tests figent les deux garanties du correctif :
  1. une entite `anchor_as_object` ancre bien les plans qui la montrent ;
  2. le comportement des entites SANS ce champ est strictement inchange.
"""

import importlib.util
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))


def _load():
    spec = importlib.util.spec_from_file_location(
        "cinema_pipeline_under_test", os.path.join(HERE, "cinema_pipeline.py"))
    mod = importlib.util.module_from_spec(spec)
    sys.modules["cinema_pipeline_under_test"] = mod
    try:
        spec.loader.exec_module(mod)
    except SystemExit:
        pass
    return mod


CP = _load()

CHARS = {
    "Velo": {"description": "a bright red carbon racing bicycle",
             "anchor_as_object": True},
    "Milo": {"description": "an adult male mechanic with curly dark hair"},
}
KEYFRAMES = {"Velo": "/tmp/velo.png", "Milo": "/tmp/milo.png"}


class ObjectAnchorTest(unittest.TestCase):

    def anchor(self, shot, speaker=""):
        return CP.select_anchor_character(shot, speaker, CHARS, KEYFRAMES)[0]

    # --- 1. l'objet declare ancre bien -------------------------------------
    def test_objet_plan_large_est_ancre(self):
        """Un plan large sur l'objet doit l'ancrer : c'est precisement le cas
        ou la porte portrait bloquait tout, alors qu'elle vise les visages."""
        self.assertEqual(
            self.anchor({"scene": "Wide shot of the red racing Velo on a ledge",
                         "camera": "wide"}), "Velo")

    def test_objet_plan_moyen_est_ancre(self):
        self.assertEqual(
            self.anchor({"scene": "Medium shot of the Velo at sunset",
                         "camera": "medium"}), "Velo")

    def test_objet_non_mentionne_pas_ancre(self):
        """L'ancre ne s'applique que si l'objet est reellement dans le plan."""
        self.assertEqual(
            self.anchor({"scene": "Wide shot of an empty valley",
                         "camera": "wide"}), "")

    # --- 2. un objet ne prend jamais la main sur un dialogue ---------------
    def test_plan_dialogue_ne_prend_pas_l_ancre_objet(self):
        """Un objet ne parle pas : sur un plan dialogue, l'ancre objet doit
        s'effacer, sinon on remplacerait le locuteur par un produit."""
        self.assertEqual(
            self.anchor({"scene": "Medium shot of Velo while Milo speaks",
                         "camera": "medium", "dialogue": "Bonjour"},
                        speaker="Milo"), "")

    def test_plan_lipsync_ne_prend_pas_l_ancre_objet(self):
        self.assertEqual(
            self.anchor({"scene": "Close-up of the Velo and Milo",
                         "camera": "close-up", "needs_lipsync": True},
                        speaker="Milo"), "Milo")

    # --- 3. non-regression : sans le champ, rien ne change -----------------
    def test_personnage_gros_plan_studio_inchange(self):
        self.assertEqual(
            self.anchor({"scene": "Close-up of Milo in a film studio",
                         "camera": "close-up", "dialogue": "Salut"},
                        speaker="Milo"), "Milo")

    def test_personnage_plan_large_toujours_refuse(self):
        """Comportement d'origine : un portrait n'ancre pas un plan large,
        sinon le fond du portrait remplace le decor demande."""
        self.assertEqual(
            self.anchor({"scene": "Wide shot of Milo walking",
                         "camera": "wide"}), "")

    def test_entite_sans_champ_reste_hors_ancrage_objet(self):
        chars = {"Chaise": {"description": "a wooden chair, an object"}}
        kf = {"Chaise": "/tmp/chaise.png"}
        name, _ = CP.select_anchor_character(
            {"scene": "Wide shot of the Chaise", "camera": "wide"}, "", chars, kf)
        self.assertEqual(name, "")

    def test_validate_character_false_desactive_tout(self):
        self.assertEqual(
            self.anchor({"scene": "Wide shot of the Velo", "camera": "wide",
                         "validate_character": False}), "")


if __name__ == "__main__":
    unittest.main(verbosity=2)
