"""Composition « monde » de bout en bout, sans modèle de langue ni rendu f3d : programmes écrits à la main
(même forme que ceux du LLM), vraies briques (ville, paysage, meubles, matériaux, export, porte).

Ce que l'on vérifie : un fichier glTF par scène, les invariants mesurés transmis à la porte, une porte qui
refuse honnêtement une scène non rendue, et un programme inutilisable qui n'est jamais composé en silence.
"""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "application" / "python-services"))
from monde import composer  # noqa: E402

VILLE = {"schema": "aurora.programme-scene.v1", "source": "llm", "demande": "un petit bourg traditionnel",
         "type_scene": "ville", "titre": "bourg", "style": {"texte": None, "architecture": "traditionnel"},
         "interieur": None, "nature": None,
         "ville": {"taille_m": [180.0, 160.0], "trame": "organique", "zones": [{"type": "centre", "part": 0.5},
                                                                           {"type": "pavillonnaire", "part": 0.5}],
                   "etages": None, "largeur_rues_m": 9.0, "riviere": False, "arbres_alignement": True, "voitures": True,
                   "style": "traditionnel"}}
NATURE = {"schema": "aurora.programme-scene.v1", "source": "llm", "demande": "une colline boisée avec un lac",
          "type_scene": "nature", "titre": "colline", "style": {"texte": None, "architecture": None},
          "interieur": None, "ville": None,
          "nature": {"biome": "foret_temperee", "relief": "collines", "taille_m": 120.0, "eau": "lac"}}


INTERIEUR = {"schema": "aurora.programme-scene.v1", "source": "llm", "demande": "un studio avec une salle d'eau",
             "type_scene": "interieur", "titre": "studio", "style": {"texte": None, "architecture": None},
             "ville": None, "nature": None,
             "interieur": {"hauteur_plafond": 2.5, "complet": True, "pieces": [
                 {"nom": "séjour", "fonction": "salon", "surface_m2": 18.0, "adjacente_a": ["salle d'eau"], "sol": None,
                  "murs": None, "complete": True, "meubles": [
                      {"categorie": "canape", "nombre": 1, "relations": [["contre_mur", None]], "materiaux": {}},
                      {"categorie": "table_basse", "nombre": 1, "relations": [["devant", "canape"]], "materiaux": {}}]},
                 {"nom": "salle d'eau", "fonction": "salle_d_eau", "surface_m2": 4.5, "adjacente_a": ["séjour"], "sol": None,
                  "murs": None, "complete": True, "meubles": [
                      {"categorie": "lavabo", "nombre": 1, "relations": [["contre_mur", None]], "materiaux": {}}]}]}}


def interieur_plan(res):
    import json as _json
    from shapely.geometry import shape  # noqa: F401
    from monde import plan as plan_mod
    programme = res["programme"]["interieur"]
    pieces = [plan_mod.PieceDemandee(nom=p["nom"], fonction=p["fonction"], surface=p["surface_m2"],
                                     adjacente_a=p["adjacente_a"]) for p in programme["pieces"]]
    return plan_mod.concevoir_plan(pieces, hauteur_plafond=2.5, graine=res["graine"]).pieces


class Composition(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.dossier = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def test_une_ville_est_composee_mesuree_et_exportee(self):
        res = composer.composer(VILLE, self.dossier / "ville", graine=3, rendre=False)
        self.assertTrue(Path(res["glb"]).is_file())
        m = res["mesures"]
        for cle in ("batiments_sur_voirie", "batiments_chevauchants", "objets_sur_chaussee", "ecart_zones"):
            self.assertIn(cle, m)
        self.assertEqual((m["batiments_sur_voirie"], m["batiments_chevauchants"], m["objets_sur_chaussee"]), (0, 0, 0))
        self.assertGreater(m["batiments"], 5)
        journal = json.loads(Path(res["journal"]).read_text(encoding="utf-8"))
        self.assertEqual(journal["type_scene"], "ville")

    def test_sans_rendu_f3d_la_porte_refuse_et_le_dit(self):
        res = composer.composer(NATURE, self.dossier / "nature", graine=1, rendre=False)
        self.assertFalse(res["ok"])
        self.assertTrue(any("aucun rendu f3d" in r for r in res["porte"]["raisons"]))
        self.assertEqual(res["mesures"]["vegetation_dans_eau"], 0)
        self.assertGreater(res["mesures"]["vegetation"], 0)

    def test_un_programme_inutilisable_n_est_jamais_compose(self):
        for mauvais in ({**VILLE, "source": "indisponible", "raison": "modèle injoignable"},
                        {**VILLE, "type_scene": "interieur"}, {**VILLE, "ville": None}):
            with self.subTest(programme=mauvais.get("type_scene")):
                res = composer.composer(mauvais, self.dossier / "x", rendre=False)
                self.assertFalse(res["ok"])
                self.assertIn("inutilisable", res["error"])
        indispo = composer.composer_depuis_demande("une ville", self.dossier / "y",
                                                   programme={"source": "indisponible", "raison": "délai"}, rendre=False)
        self.assertFalse(indispo["ok"])
        self.assertIn("indisponible", indispo["error"])

    def test_chaque_scene_a_un_point_de_depart_pour_la_visite(self):
        ville = composer.composer(VILLE, self.dossier / "v", graine=3, rendre=False)
        nature = composer.composer(NATURE, self.dossier / "n", graine=1, rendre=False)
        for res in (ville, nature):
            depart = res["depart"]
            self.assertIsNotNone(depart)
            self.assertAlmostEqual(depart["direction"][0] ** 2 + depart["direction"][1] ** 2, 1.0, places=3)
        self.assertGreater(nature["depart"]["y"], (nature["mesures"]["niveau_eau_m"] or 0.0))   # pas dans l'eau
        interieur = composer.composer(INTERIEUR, self.dossier / "i", graine=2, rendre=False)
        depart = interieur["depart"]
        self.assertIsNotNone(depart)
        dedans = any(p.polygone.buffer(0.05).contains(__import__("shapely.geometry", fromlist=["Point"]).Point(depart["x"], depart["z"]))
                     for p in interieur_plan(interieur))
        self.assertTrue(dedans, depart)                      # derrière la porte d'entrée, dans le logement

    def test_la_graine_par_defaut_vient_de_la_demande(self):
        self.assertEqual(composer.graine_de("une ville"), composer.graine_de("une ville"))
        self.assertNotEqual(composer.graine_de("une ville"), composer.graine_de("un village"))


if __name__ == "__main__":
    unittest.main()
