#!/usr/bin/env python3
"""Gardes : etalonnage commun du film, sans destruction d'image.

Contexte mesure sur un film reel (5 plans, meme ruelle, meme heure) :
  plan 1  moyenne 0,794 0,831 0,879   <- quasi crame
  plan 3  moyenne 0,276 0,292 0,371   <- sombre
  ecart maximal 0,52 sur une echelle de 0 a 1
Isolement chaque plan est correct ; c'est a la COUPE que l'oeil lit la rupture.
Aucun reglage de generation ne corrige cela : le defaut n'existe que dans la
relation entre les plans.

Ces tests figent les trois proprietes qui empechent le remede d'etre pire que
le mal :
  1. la reference est la MEDIANE (un plan aberrant ne contamine pas les autres) ;
  2. la correction est BORNEE (combler 0,52 d'un coup ecraserait les hautes
     lumieres du plan sombre) ;
  3. un plan deja dans la lumiere du film n'est pas reencode pour rien.
"""

import importlib.util
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))


def _load():
    spec = importlib.util.spec_from_file_location(
        "film_grade_under_test", os.path.join(HERE, "film_grade.py"))
    mod = importlib.util.module_from_spec(spec)
    sys.modules["film_grade_under_test"] = mod
    spec.loader.exec_module(mod)
    return mod


FG = _load()


def _m(mean, std=(0.25, 0.25, 0.25)):
    return {"ok": True, "mean": list(mean), "std": list(std)}


class TestReference(unittest.TestCase):

    def test_la_mediane_ignore_le_plan_aberrant(self):
        """Trois plans coherents et un crame : la reference doit rester sur les
        trois, sinon le plan rate tire tout le film vers lui."""
        mesures = [_m((0.5, 0.5, 0.5)), _m((0.52, 0.52, 0.52)),
                   _m((0.48, 0.48, 0.48)), _m((0.95, 0.95, 0.95))]
        ref = FG.film_reference(mesures)
        self.assertTrue(ref["ok"])
        for c in range(3):
            self.assertLess(ref["mean"][c], 0.6)

    def test_les_mesures_ratees_sont_ecartees(self):
        ref = FG.film_reference([_m((0.5, 0.5, 0.5)),
                                 {"ok": False, "error": "illisible"}])
        self.assertTrue(ref["ok"])
        self.assertEqual(ref["shots"], 1)

    def test_aucune_mesure_exploitable(self):
        ref = FG.film_reference([{"ok": False}, {"ok": False}])
        self.assertFalse(ref["ok"])


class TestCorrectionBornee(unittest.TestCase):

    def test_le_decalage_est_plafonne(self):
        """Un plan tres sombre ramene vers un film clair : le decalage ne doit
        jamais depasser le plafond, sinon tout ce qui depasse devient blanc."""
        corr = FG.correction_for(_m((0.27, 0.29, 0.37)),
                                 {"mean": [0.61, 0.71, 0.77],
                                  "std": [0.3, 0.27, 0.31]})
        for off in corr["offset"]:
            self.assertLessEqual(abs(off), FG.MAX_OFFSET + 1e-6)

    def test_le_gain_est_borne_des_deux_cotes(self):
        for std_plan in (0.02, 0.9):
            corr = FG.correction_for(_m((0.5, 0.5, 0.5), (std_plan,) * 3),
                                     {"mean": [0.5, 0.5, 0.5],
                                      "std": [0.3, 0.3, 0.3]})
            for g in corr["gain"]:
                self.assertGreaterEqual(g, FG.MIN_GAIN - 1e-6)
                self.assertLessEqual(g, FG.MAX_GAIN + 1e-6)

    def test_un_plan_deja_conforme_ne_bouge_pas(self):
        ref = {"mean": [0.5, 0.5, 0.5], "std": [0.25, 0.25, 0.25]}
        corr = FG.correction_for(_m((0.5, 0.5, 0.5)), ref)
        self.assertTrue(FG.is_noop(corr))

    def test_un_plan_decale_doit_bouger(self):
        ref = {"mean": [0.5, 0.5, 0.5], "std": [0.25, 0.25, 0.25]}
        corr = FG.correction_for(_m((0.8, 0.8, 0.8)), ref)
        self.assertFalse(FG.is_noop(corr))

    def test_force_nulle_ne_change_rien(self):
        ref = {"mean": [0.2, 0.2, 0.2], "std": [0.4, 0.4, 0.4]}
        corr = FG.correction_for(_m((0.8, 0.8, 0.8)), ref, strength=0.0)
        self.assertTrue(FG.is_noop(corr))

    def test_la_correction_va_dans_le_bon_sens(self):
        """Un plan trop clair doit etre assombri, pas eclairci davantage."""
        ref = {"mean": [0.5, 0.5, 0.5], "std": [0.25, 0.25, 0.25]}
        corr = FG.correction_for(_m((0.8, 0.8, 0.8)), ref)
        sortie = corr["gain"][0] * 0.8 + corr["offset"][0]
        self.assertLess(sortie, 0.8)
        self.assertGreater(sortie, 0.5)


class TestFiltreFfmpeg(unittest.TestCase):

    def test_les_canaux_sont_remis_dans_l_ordre_ffmpeg(self):
        """OpenCV mesure en BGR, ffmpeg nomme r/g/b : une inversion
        transformerait une correction de bleu en correction de rouge."""
        corr = {"gain": [1.0, 1.0, 1.2], "offset": [0.0, 0.0, 0.05]}
        f = FG._filter_string(corr)
        self.assertTrue(f.startswith("colorlevels="))
        for canal in ("rimin", "rimax", "gimin", "gimax", "bimin", "bimax"):
            self.assertIn(canal, f)
        # gain 1.2 + offset 0.05 est sur le canal ROUGE (3e position BGR)
        rimax = float(f.split("rimax=")[1].split(":")[0])
        self.assertAlmostEqual(rimax, (1.0 - 0.05) / 1.2, places=4)

    def test_les_bornes_restent_dans_la_plage_acceptee(self):
        corr = FG.correction_for(_m((0.05, 0.05, 0.05), (0.02,) * 3),
                                 {"mean": [0.9, 0.9, 0.9], "std": [0.5] * 3})
        f = FG._filter_string(corr)
        for part in f.replace("colorlevels=", "").split(":"):
            valeur = float(part.split("=")[1])
            self.assertGreaterEqual(valeur, -1.0)
            self.assertLessEqual(valeur, 1.0)

    def test_bornes_jamais_confondues(self):
        """imin == imax donnerait une division par zero dans ffmpeg."""
        corr = {"gain": [FG.MAX_GAIN] * 3, "offset": [0.0] * 3}
        f = FG._filter_string(corr)
        for canal in ("r", "g", "b"):
            imin = float(f.split(f"{canal}imin=")[1].split(":")[0])
            imax = float(f.split(f"{canal}imax=")[1].split(":")[0])
            self.assertGreater(imax - imin, 0)


class TestRobustesse(unittest.TestCase):
    """Un etalonnage rate ne doit JAMAIS coûter un plan."""

    def test_un_plan_illisible_est_conserve_tel_quel(self):
        vrai = FG.measure_shot
        FG.measure_shot = lambda p, samples=12: (
            {"ok": False, "error": "illisible"} if "casse" in p
            else _m((0.5, 0.5, 0.5)))
        try:
            res = FG.harmonise(["/tmp/bon_a.mp4", "/tmp/casse.mp4"],
                               "/tmp/aurora_grade_test_out")
        finally:
            FG.measure_shot = vrai
        self.assertTrue(res["ok"])
        self.assertIn("/tmp/casse.mp4", res["files"])
        self.assertEqual(len(res["files"]), 2)

    def test_un_reencodage_rate_conserve_l_original(self):
        vrai_m, vrai_a = FG.measure_shot, FG.apply_correction
        FG.measure_shot = lambda p, samples=12: (
            _m((0.9, 0.9, 0.9)) if "clair" in p else _m((0.2, 0.2, 0.2)))
        FG.apply_correction = lambda *a, **k: {"ok": False, "error": "ffmpeg ko"}
        try:
            res = FG.harmonise(["/tmp/clair.mp4", "/tmp/sombre.mp4"],
                               "/tmp/aurora_grade_test_out")
        finally:
            FG.measure_shot, FG.apply_correction = vrai_m, vrai_a
        self.assertTrue(res["ok"])
        self.assertEqual(res["files"], ["/tmp/clair.mp4", "/tmp/sombre.mp4"])
        self.assertEqual(res["applied"], 0)

    def test_aucune_mesure_exploitable_rend_les_fichiers_d_origine(self):
        vrai = FG.measure_shot
        FG.measure_shot = lambda p, samples=12: {"ok": False, "error": "x"}
        try:
            res = FG.harmonise(["/tmp/a.mp4", "/tmp/b.mp4"], "/tmp/aurora_g2")
        finally:
            FG.measure_shot = vrai
        self.assertFalse(res["ok"])
        self.assertEqual(res["files"], ["/tmp/a.mp4", "/tmp/b.mp4"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
