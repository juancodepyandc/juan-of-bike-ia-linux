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


if __name__ == "__main__":
    unittest.main()
