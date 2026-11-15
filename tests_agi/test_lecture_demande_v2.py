"""Request contract v2: one entry per subject, the style apart, the medium each movement implies.

Run of 15/11/2026: « Zig et Sharko en version réaliste : Zig la hyène qui court et Sharko le requin
qui nage » — identity, style and medium were mixed in one label ("Zig la hyène et Sharko le requin,
en version réaliste"), so the image search, the identity and the water were all lost downstream.
Names here are invented: the rules are about the sentence, never about a subject.
"""
from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "application" / "python-services"))
from lecture_demande import SCHEMA, lire_demande  # noqa: E402

REQUEST = "Plim et Glouk en version réaliste : Plim le renard qui court et Glouk la baleine qui nage"


def subject(nom, nature, nature_en, clause, mouvement, mouvement_en, matiere, relation, justification):
    return {"nom": nom, "nomme": True, "nature": nature, "nature_en": nature_en, "clause": clause,
            "mouvement": mouvement, "mouvement_en": mouvement_en,
            "milieu": {"matiere": matiere, "relation": relation, "justification": justification}}


GOOD = {
    "sujet": "Plim le renard et Glouk la baleine", "sujet_en": "Plim the fox and Glouk the whale",
    "mouvement": "Plim court et Glouk nage", "exemplaires": 2, "corps_articule": True, "conception": False,
    "sujets": [
        subject("Plim", "un renard", "fox", "Plim le renard qui court", "qui court", "a person runs forward",
                "solide", "sur", "court"),
        subject("Glouk", "une baleine", "whale", "Glouk la baleine qui nage", "qui nage", "a person swims",
                "liquide", "immerge", "nage"),
    ],
    "style": {"texte": "en version réaliste", "cible": "photo", "justification": "en version réaliste"},
}


def answering(*answers):
    replies = list(answers)
    return lambda _text: json.dumps(replies.pop(0) if len(replies) > 1 else replies[0], ensure_ascii=False)


class ContractV2(unittest.TestCase):
    def test_each_subject_keeps_its_clause_movement_and_medium_and_the_style_stays_apart(self):
        reading = lire_demande(REQUEST, interroger=answering(GOOD))
        self.assertEqual((reading["schema"], reading["source"]), (SCHEMA, "llm"))
        self.assertEqual([s["nom"] for s in reading["sujets"]], ["Plim", "Glouk"])
        self.assertEqual(reading["sujets"][1]["milieu"]["matiere"], "liquide")
        self.assertEqual(reading["sujets"][1]["mouvement_en"], "a person swims")
        self.assertEqual(reading["style"], {"texte": "en version réaliste", "cible": "photo",
                                            "justification": "en version réaliste"})

    def test_accents_and_case_do_not_break_the_exact_copy_rule(self):
        loose = json.loads(json.dumps(GOOD))
        loose["sujets"][0]["clause"] = "plim le renard QUI COURT"
        loose["style"]["texte"] = "En Version Realiste"
        self.assertEqual(lire_demande(REQUEST, interroger=answering(loose))["source"], "llm")

    def test_an_invented_clause_gets_one_correction_then_is_never_passed_off(self):
        invented = json.loads(json.dumps(GOOD))
        invented["sujets"][0]["clause"] = "Plim le renard roux aux yeux verts"
        asked = []

        def model(text):
            asked.append(text)
            return json.dumps(invented if len(asked) == 1 else GOOD, ensure_ascii=False)
        self.assertEqual(lire_demande(REQUEST, interroger=model)["source"], "llm")
        self.assertIn("clause doit être un morceau exact", asked[1])
        self.assertEqual(lire_demande(REQUEST, interroger=answering(invented))["source"], "indisponible")

    def test_an_incoherent_medium_is_refused(self):
        wrong = json.loads(json.dumps(GOOD))
        wrong["sujets"][1]["milieu"] = {"matiere": "gaz", "relation": "immerge", "justification": "nage"}
        reading = lire_demande(REQUEST, interroger=answering(wrong))
        self.assertEqual(reading["source"], "indisponible")
        self.assertIn("immerge implique la matière liquide", reading["raison"])

    def test_the_style_never_leaks_into_a_subject(self):
        leaking = json.loads(json.dumps(GOOD))
        leaking["sujets"][0]["nature"] = "un renard en version réaliste"
        self.assertEqual(lire_demande(REQUEST, interroger=answering(leaking))["source"], "indisponible")


class PlaceToBuild(unittest.TestCase):
    """A whole place (interior, town, landscape) goes to the scene engine instead of being cut into objects
    (15/11/2026: « un intérieur de maison complet » became three room-objects set in a row)."""

    PLACE = "un intérieur de maison complet, salon cuisine chambre, réaliste"

    def reading(self, lieu, demande=None):
        place = {"nom": None, "nomme": False, "nature": "intérieur de maison", "nature_en": "house interior",
                 "clause": "un intérieur de maison complet", "mouvement": "", "mouvement_en": "",
                 "milieu": {"matiere": None, "relation": None, "justification": ""}}
        answer = {"sujet": "un intérieur de maison complet", "sujet_en": "a complete house interior", "mouvement": "",
                  "exemplaires": 1, "corps_articule": False, "conception": False, "sujets": [place],
                  "style": {"texte": "réaliste", "cible": "photo", "justification": "réaliste"}, "lieu": lieu}
        return answer

    def test_a_place_is_typed_and_justified_by_the_request_words(self):
        reading = lire_demande(self.PLACE, interroger=answering(self.reading(
            {"type": "interieur", "justification": "intérieur de maison complet"})))
        self.assertEqual(reading["lieu"], {"type": "interieur", "justification": "intérieur de maison complet"})

    def test_subjects_in_a_setting_are_not_a_place_and_old_readings_have_none(self):
        self.assertEqual(lire_demande(REQUEST, interroger=answering(GOOD))["lieu"], {"type": None, "justification": ""})
        null_place = dict(GOOD, lieu={"type": None, "justification": ""})
        self.assertIsNone(lire_demande(REQUEST, interroger=answering(null_place))["lieu"]["type"])

    def test_an_invented_justification_gets_one_correction(self):
        invented = self.reading({"type": "interieur", "justification": "une villa de luxe"})
        asked = []

        def model(text):
            asked.append(text)
            good = {"type": "interieur", "justification": "intérieur de maison"}
            return json.dumps(self.reading(good if len(asked) > 1 else invented["lieu"]), ensure_ascii=False)
        self.assertEqual(lire_demande(self.PLACE + " ", interroger=model)["lieu"]["type"], "interieur")
        self.assertIn("lieu.justification", asked[1])
        refused = lire_demande(self.PLACE + "  .", interroger=answering(self.reading({"type": "chateau", "justification": "maison"})))
        self.assertEqual(refused["source"], "indisponible")


if __name__ == "__main__":
    unittest.main()


class EmissionOfASubject(unittest.TestCase):
    """« Un coup de parfum » (15/11/2026): the matter a subject emits is read from the request's words."""

    SPRAY = "un flacon de parfum qui fait un coup de parfum"

    def reading(self, emission):
        subject = {"nom": None, "nomme": False, "nature": "flacon de parfum", "nature_en": "perfume bottle",
                   "clause": "un flacon de parfum qui fait un coup de parfum", "mouvement": "fait un coup de parfum",
                   "mouvement_en": "", "milieu": {"matiere": "gaz", "relation": "dans_l_air",
                                                  "justification": "coup de parfum"}}
        if emission is not None:
            subject["emission"] = emission
        return {"sujet": "un flacon de parfum", "sujet_en": "a perfume bottle", "mouvement": "fait un coup de parfum",
                "exemplaires": 1, "corps_articule": False, "conception": False, "sujets": [subject],
                "style": {"texte": "", "cible": None, "justification": ""}}

    def test_a_spray_is_typed_placed_and_justified(self):
        reading = lire_demande(self.SPRAY, interroger=answering(self.reading(
            {"type": "brume", "point": "avant", "justification": "coup de parfum"})))
        self.assertEqual(reading["sujets"][0]["emission"],
                         {"type": "brume", "point": "avant", "justification": "coup de parfum"})

    def test_no_emission_or_an_older_reading_gives_none(self):
        reading = lire_demande(self.SPRAY + " ", interroger=answering(self.reading(None)))
        self.assertEqual(reading["sujets"][0]["emission"], {"type": None, "point": None, "justification": ""})

    def test_an_unknown_type_or_an_invented_justification_is_refused(self):
        for bad in ({"type": "arc_en_ciel", "point": "haut", "justification": "coup de parfum"},
                    {"type": "brume", "point": "avant", "justification": "nuage parfumé enchanté"}):
            with self.subTest(bad=bad):
                reading = lire_demande(self.SPRAY + "  .", interroger=answering(self.reading(bad)))
                self.assertEqual(reading["source"], "indisponible")
