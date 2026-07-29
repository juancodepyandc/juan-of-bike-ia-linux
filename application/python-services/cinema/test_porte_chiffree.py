#!/usr/bin/env python3
"""Gardes : la porte chiffree doit MESURER, pas deviner.

Contexte : le juge VLM a note le meme plan 7, puis 6, puis 10, puis 5 — images
identiques. On ne corrige pas un juge bruite en le relancant : on le remplace,
pour tout ce qui est mesurable, par des chiffres.

Piege corrige avant mise en service, et fige ici : comparer un plan a un
PORTRAIT studio ne mesure pas l'identite mais le CADRAGE. Mesure sur quatre
plans reels, un personnage parfaitement reconnaissable obtenait 0,17 a 0,35,
parce que l'embedding DINOv2 encode toute l'image et que le decor y pese plus
que le sujet. Le seuil aurait refuse des plans corrects et laisse passer un
mauvais plan bien cadre.
"""

import importlib.util
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))


def _load():
    spec = importlib.util.spec_from_file_location(
        "porte_sous_test", os.path.join(HERE, "porte_chiffree.py"))
    m = importlib.util.module_from_spec(spec)
    sys.modules["porte_sous_test"] = m
    try:
        spec.loader.exec_module(m)
    except SystemExit:
        pass
    return m


P = _load()


class TestDeltaE(unittest.TestCase):
    """Mesure sur le film reel : plans 3 et 4 a 25 et 33 de delta-E, ce sont
    exactement les deux dont la couleur avait derive a l'oeil."""

    def test_deux_couleurs_identiques_sont_a_zero(self):
        import numpy as np
        lab = np.array([150.0, 120.0, 160.0])
        self.assertAlmostEqual(P.delta_e(lab, lab), 0.0, places=5)

    def test_l_ecart_mesure_du_film_depasse_le_seuil(self):
        import numpy as np
        a = np.array([157.7, 121.1, 160.6])   # lumiere mediane du film
        b = np.array([157.7, 121.1, 193.9])   # plan 4, derive jaune
        self.assertGreater(P.delta_e(a, b), P.SEUIL_DELTA_E)

    def test_une_mesure_absente_ne_fabrique_pas_un_verdict(self):
        self.assertEqual(P.delta_e(None, None), -1.0)


class TestSimilarite(unittest.TestCase):

    def test_un_vecteur_est_identique_a_lui_meme(self):
        import numpy as np
        v = np.array([0.6, 0.8])
        self.assertAlmostEqual(P.similarite(v, v), 1.0, places=5)

    def test_deux_vecteurs_orthogonaux(self):
        import numpy as np
        self.assertAlmostEqual(
            P.similarite(np.array([1.0, 0.0]), np.array([0.0, 1.0])), 0.0)

    def test_une_empreinte_absente_rend_moins_un(self):
        self.assertEqual(P.similarite(None, None), -1.0)


class TestSeuils(unittest.TestCase):
    """Les seuils viennent de mesures reelles, pas d'intuitions."""

    def test_le_seuil_de_mouvement_separe_les_valeurs_mesurees(self):
        self.assertLess(0.58, P.SEUIL_MOUVEMENT)    # plan reste fige
        self.assertGreater(2.5, P.SEUIL_MOUVEMENT)   # sortie S2V animee
        self.assertGreater(9.26, P.SEUIL_MOUVEMENT)  # plan dialogue du film

    def test_le_seuil_de_constance_laisse_passer_les_plans_reels(self):
        for mesure in (0.62, 0.711, 0.778, 0.837):
            self.assertGreater(mesure, P.SEUIL_CONSTANCE)

    def test_le_seuil_de_constance_aurait_refuse_la_comparaison_au_portrait(self):
        """Regression du piege : ces valeurs sont celles obtenues contre un
        portrait studio, sur des plans pourtant corrects."""
        for mesure in (0.17, 0.20, 0.35):
            self.assertLess(mesure, P.SEUIL_CONSTANCE)

    def test_le_seuil_de_derive_interne_laisse_passer_les_plans_reels(self):
        for mesure in (0.836, 0.897, 0.92, 0.978):
            self.assertGreater(mesure, P.SEUIL_DERIVE_INTERNE)


class TestRobustesse(unittest.TestCase):
    """Une porte qui ne peut pas mesurer ne doit JAMAIS fabriquer un verdict,
    ni dans un sens ni dans l'autre."""

    def test_un_plan_illisible_est_non_note(self):
        r = P.mesurer_plan("/tmp/inexistant_aurora_xyz.mp4")
        self.assertFalse(r["graded"])
        self.assertFalse(r["ok"])

    def test_amplitude_d_un_fichier_absent(self):
        self.assertIsNone(P.amplitude_mouvement("/tmp/inexistant_aurora_xyz.mp4"))

    def test_aucune_image_ne_donne_aucune_signature(self):
        self.assertIsNone(P.signature_du_film([]))


if __name__ == "__main__":
    unittest.main(verbosity=2)
