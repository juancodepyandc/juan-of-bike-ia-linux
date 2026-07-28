#!/usr/bin/env python3
"""Garde : extraction robuste du JSON renvoye par le modele de vision.

Cause reelle : "vision JSON parse failed" revenait en boucle sur des rendus,
laissant des scores None. Or une porte de qualite qui ne MESURE pas ne protege
rien : elle laisse passer des plans rates et en rejette de bons. L'ancienne
methode prenait `premier {` .. `dernier }`, ce qui casse des que le modele
ajoute de la prose, tronque sa sortie, ou ouvre un <think> sans le refermer.
"""

import importlib.util
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location(
    "cinema_pipeline_json_test", os.path.join(HERE, "cinema_pipeline.py"))
CP = importlib.util.module_from_spec(spec)
sys.modules["cinema_pipeline_json_test"] = CP
try:
    spec.loader.exec_module(CP)
except SystemExit:
    pass


class ExtractJsonTest(unittest.TestCase):

    def score(self, text):
        r = CP._extract_json_object(text)
        return (r or {}).get("score") if r else None

    def test_json_nu(self):
        self.assertEqual(self.score('{"score": 8}'), 8)

    def test_cloture_markdown(self):
        self.assertEqual(self.score('```json\n{"score": 7}\n```'), 7)

    def test_balise_think_fermee(self):
        self.assertEqual(self.score('<think>bla</think>{"score": 6}'), 6)

    def test_balise_think_non_fermee_ne_livre_pas_de_faux_score(self):
        """Le modele coupe en plein raisonnement : mieux vaut None qu'un score
        pioche dans sa reflexion."""
        self.assertIsNone(self.score('<think>je reflechis {"score": 99}'))

    def test_accolade_dans_une_chaine(self):
        self.assertEqual(self.score('Analyse. {"score": 5, "reason": "a}b"} Fin.'), 5)

    def test_json_tronque_refuse(self):
        self.assertIsNone(self.score('{"score": 4, "reason": "coupe"'))

    def test_premier_objet_invalide_puis_valide(self):
        self.assertEqual(self.score('bla {pas json} puis {"score": 3}'), 3)

    def test_objet_imbrique(self):
        self.assertEqual(self.score('{"a": {"b": 1}, "score": 9}'), 9)

    def test_texte_vide(self):
        self.assertIsNone(CP._extract_json_object(""))
        self.assertIsNone(CP._extract_json_object(None))


if __name__ == "__main__":
    unittest.main(verbosity=2)
