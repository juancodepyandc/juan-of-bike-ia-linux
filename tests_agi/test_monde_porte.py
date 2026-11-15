"""Porte mesurée des scènes « monde » : un compte dur non nul, une mesure absente, un rendu f3d vide ou
surexposé refusent ; le cliquet ne fait que durcir. Aucun rendu réel : images synthétiques."""
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "application" / "python-services"))
from monde import porte  # noqa: E402

BONNES_MESURES = {"chevauchements": 0, "hors_piece": 0, "portes_bloquees": 0, "fenetres_bloquees": 0,
                  "inaccessibles": [], "pieces_isolees": [], "meubles_demandes": 40, "meubles_places": 40,
                  "pieces_manquantes": []}


class Atelier(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.dossier = Path(self._tmp.name)
        self.cliquet = self.dossier / "cliquet.json"

    def tearDown(self):
        self._tmp.cleanup()

    def image(self, nom, *, remplie=0.6, blanc=0.0):
        a = np.full((100, 100, 3), 50, dtype=np.uint8)
        cote = int(100 * remplie ** 0.5)
        a[10:10 + cote, 10:10 + cote] = (150, 110, 70)
        if blanc:
            a[:int(100 * blanc), :] = 255
        chemin = self.dossier / nom
        Image.fromarray(a).save(chemin)
        return chemin

    def rendus(self, **options):
        return {"rendus": [{"vue": "plan", "ok": True, "png": str(self.image("plan.png", **options)),
                            "part_blanc_pur": options.get("blanc", 0.0)},
                           {"vue": "aerienne_sud_est", "ok": True, "png": str(self.image("a.png")), "part_blanc_pur": 0.0}]}

    def juger(self, mesures=None, export=None, rendus=None, **options):
        return porte.juger("interieur", BONNES_MESURES if mesures is None else mesures,
                           {"octets": 1000, "triangles": 50_000} if export is None else export,
                           self.rendus() if rendus is None else rendus, chemin_cliquet=self.cliquet, **options)


class Verdicts(Atelier):
    def test_une_scene_mesuree_sans_defaut_est_acceptee(self):
        verdict = self.juger()
        self.assertEqual(verdict["verdict"], "accepte", verdict["raisons"])
        self.assertGreater(verdict["mesures"]["contenu_plan"], 0.3)

    def test_un_seul_compte_dur_refuse_avec_sa_raison(self):
        for cle in ("chevauchements", "portes_bloquees", "hors_piece"):
            with self.subTest(cle=cle):
                verdict = self.juger(dict(BONNES_MESURES, **{cle: 1}))
                self.assertEqual(verdict["verdict"], "refuse")
                self.assertTrue(any(porte.DURS[cle] in r for r in verdict["raisons"]))
        inaccessible = self.juger(dict(BONNES_MESURES, inaccessibles=["armoire (chambre)"]))
        self.assertEqual(inaccessible["verdict"], "refuse")

    def test_une_mesure_absente_n_est_jamais_un_succes(self):
        mesures = dict(BONNES_MESURES)
        del mesures["portes_bloquees"]
        verdict = self.juger(mesures)
        self.assertEqual(verdict["verdict"], "refuse")
        self.assertIn("portes_bloquees", " ".join(verdict["raisons"]))

    def test_sans_rendu_f3d_ou_avec_un_rendu_vide_ou_brule_la_scene_est_refusee(self):
        self.assertEqual(self.juger(rendus={})["verdict"], "refuse")
        vide = self.juger(rendus=self.rendus(remplie=0.01))
        self.assertTrue(any("presque vide" in r for r in vide["raisons"]))
        brule = self.juger(rendus=self.rendus(blanc=0.2))
        self.assertTrue(any("surexposition" in r for r in brule["raisons"]))

    def test_trop_peu_de_meubles_poses_ou_une_piece_manquante_refuse(self):
        self.assertEqual(self.juger(dict(BONNES_MESURES, meubles_places=20))["verdict"], "refuse")
        manque = self.juger(dict(BONNES_MESURES, pieces_manquantes=["cuisine"]))
        self.assertTrue(any("cuisine" in r for r in manque["raisons"]))


class Cliquet(Atelier):
    def test_le_plafond_est_plus_strict_que_la_base_dans_les_deux_sens(self):
        base, plafond = porte.seuils_au_pas(0), porte.seuils_au_pas(porte.PAS_SATURATION)
        self.assertGreater(plafond["part_places_min"], base["part_places_min"])
        self.assertLess(plafond["blanc_pur_max"], base["blanc_pur_max"])
        self.assertLess(plafond["triangles_max"], base["triangles_max"])

    def test_des_seuils_injectes_ne_sont_jamais_plus_laches_que_la_base(self):
        lache = self.juger(seuils={"part_places_min": 0.1, "blanc_pur_max": 0.9})
        self.assertEqual(lache["seuils"]["part_places_min"], porte.BORNES["part_places_min"][0])
        self.assertEqual(lache["seuils"]["blanc_pur_max"], porte.BORNES["blanc_pur_max"][0])

    def test_le_cliquet_n_avance_que_sur_une_livraison_acceptee(self):
        refus = self.juger(dict(BONNES_MESURES, chevauchements=2))
        avant = porte.cliquet(chemin=self.cliquet)["ratchet_level"]
        self.assertFalse(porte.avancer_cliquet(refus, chemin=self.cliquet)["avance"])
        self.assertEqual(porte.cliquet(chemin=self.cliquet)["ratchet_level"], avant)
        etat = porte.avancer_cliquet(self.juger(), chemin=self.cliquet)
        self.assertTrue(etat["avance"])
        self.assertEqual(etat["ratchet_level"], avant + 1)


if __name__ == "__main__":
    unittest.main()
