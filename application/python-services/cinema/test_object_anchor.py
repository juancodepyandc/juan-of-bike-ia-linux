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


class ObjectKeyframePromptTest(unittest.TestCase):
    """La reference canonique d'un objet ne doit contenir QUE l'objet.

    Mesure a l'origine : la description "a bright red carbon road racing
    bicycle with drop handlebars..." ne matche AUCUN mot-cle de
    is_object_like_character. Elle recevait donc le prompt PORTRAIT, FLUX a
    place un garcon generique derriere le velo, et cette reference servant
    d'ancre i2v, le garcon a remplace Natsu dans 2 plans sur 5.
    """

    VELO = ("a bright red carbon road racing bicycle with drop handlebars, "
            "deep-section black rims and a chrome chainring")

    def test_heuristique_seule_rate_un_velo(self):
        """Constat qui justifie le champ explicite : le mot-cle ne suffit pas."""
        self.assertFalse(CP.is_object_like_character(self.VELO))

    def test_anchor_as_object_force_le_prompt_objet(self):
        p = CP.build_character_keyframe_prompt(self.VELO, "", is_object=True)
        self.assertNotIn("portrait of", p)
        self.assertIn("concept art", p)

    def test_prompt_objet_exclut_explicitement_toute_personne(self):
        p = CP.build_character_keyframe_prompt(self.VELO, "", is_object=True)
        for interdit in ("no person", "no human", "nobody holding it",
                         "nobody behind it", "unoccupied"):
            self.assertIn(interdit, p, interdit)

    def test_personnage_garde_le_prompt_portrait(self):
        p = CP.build_character_keyframe_prompt(
            "a young man with spiky pink hair", "", is_object=False)
        self.assertIn("portrait of", p)

    def test_heuristique_toujours_active_sans_le_champ(self):
        """Non-regression : un descriptif contenant un mot-cle reste un objet."""
        p = CP.build_character_keyframe_prompt("a small metallic drone", "")
        self.assertIn("concept art", p)



class ObjectCompletenessTest(unittest.TestCase):
    """Une reference d'objet doit etre COMPLETE, pas seulement ressemblante.

    Cas reel a l'origine : le velo canonique du film Natsu passait la porte de
    ressemblance alors qu'il lui manquait les PEDALES et qu'un garcon
    generique figurait derriere lui. L'objet incomplet s'est ensuite propage a
    tous les plans qu'il ancrait, et le garcon a remplace le personnage.
    Verifie en direct sur l'artefact fautif : le juge renvoie
    missing=['pedals','brake calipers'], person_present=True.
    """

    def _with_payload(self, payload):
        original = CP._ollama_vision_json
        CP._ollama_vision_json = lambda *a, **k: payload
        try:
            import tempfile, os
            fd, p = tempfile.mkstemp(suffix=".png")
            os.write(fd, b"\0" * 64)
            os.close(fd)
            try:
                return CP.validate_object_completeness(p, "un velo de course")
            finally:
                os.unlink(p)
        finally:
            CP._ollama_vision_json = original

    def test_objet_complet_passe(self):
        r = self._with_payload({"missing": [], "malformed": [],
                                "person_present": False})
        self.assertTrue(r["ok"])
        self.assertTrue(r["graded"])

    def test_piece_manquante_refuse(self):
        r = self._with_payload({"missing": ["pedals"], "malformed": [],
                                "person_present": False})
        self.assertFalse(r["ok"])
        self.assertIn("pedals", r["reason"])

    def test_piece_deformee_refuse(self):
        r = self._with_payload({"missing": [], "malformed": ["front wheel"],
                                "person_present": False})
        self.assertFalse(r["ok"])
        self.assertIn("deformees", r["reason"])

    def test_personne_presente_refuse(self):
        """Une reference d'objet doit contenir l'objet SEUL."""
        r = self._with_payload({"missing": [], "malformed": [],
                                "person_present": True})
        self.assertFalse(r["ok"])
        self.assertIn("personne", r["reason"])

    def test_panne_vision_ne_fabrique_jamais_un_succes(self):
        r = self._with_payload(None)
        self.assertFalse(r["ok"])
        self.assertFalse(r["graded"])


class LocomotionNoAnchorTest(unittest.TestCase):
    """Un plan de LOCOMOTION ne doit pas etre ancre sur une image fixe.

    Cas reel : le plan "Natsu roule dans la ruelle" etait ancre en i2v sur une
    image de velo A L'ARRET tenu a la main. Le conditionnement i2v verrouille la
    geometrie de depart, donc le modele a conserve la pose : personnage debout
    derriere son velo, pieds au sol, fond immobile. Notes phys=3/10 act=2/10,
    avec l'issue "Feet are not positioned on the pedals (he's standing)".
    """

    def anchor(self, shot, speaker=""):
        return CP.select_anchor_character(shot, speaker, CHARS, KEYFRAMES)[0]

    def test_plan_de_roulage_non_ancre(self):
        self.assertEqual(
            self.anchor({"scene": "Tracking shot of Milo riding the Velo down an alley",
                         "camera": "medium"}), "")

    def test_course_non_ancree(self):
        self.assertEqual(
            self.anchor({"scene": "Wide shot of Milo running through the street",
                         "camera": "wide"}), "")

    def test_locomotion_detectee_dans_le_contrat_d_action(self):
        self.assertEqual(
            self.anchor({"scene": "Medium shot of Milo and the Velo",
                         "camera": "medium",
                         "action_contract": "He is pedalling continuously"}), "")

    def test_force_t2v_explicite(self):
        self.assertEqual(
            self.anchor({"scene": "Medium shot of the Velo", "camera": "medium",
                         "force_t2v": True}), "")

    def test_plan_statique_reste_ancre(self):
        """Non-regression : un plan sans locomotion garde son ancre."""
        self.assertEqual(
            self.anchor({"scene": "Medium shot of the Velo leaning on a wall",
                         "camera": "medium"}), "Velo")

    def test_dialogue_statique_reste_ancre(self):
        self.assertEqual(
            self.anchor({"scene": "Close-up of Milo in a film studio",
                         "camera": "close-up", "dialogue": "Salut"},
                        speaker="Milo"), "Milo")

if __name__ == "__main__":
    unittest.main(verbosity=2)
