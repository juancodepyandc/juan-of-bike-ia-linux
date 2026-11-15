"""Mondes à visiter : une ville dans sa campagne, des maisons où l'on entre par une porte qui donne sur la rue.

Village du 15/11/2026 : départ dehors face à une maison, on entre par sa porte (test Node de la marche) ;
ici, on vérifie les lois du monde sur un petit bourg, avec les vraies briques, sans rendu.
"""
from __future__ import annotations

import math
import sys
import unittest
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "application" / "python-services"))
from monde import geometrie as g, univers, vocabulaire as voc  # noqa: E402
from monde.composer import fabrique_meubles  # noqa: E402
from monde.ir import Instance, Noeud, Objet, Partie, Pose  # noqa: E402

BOURG = {"source": "llm", "demande": "un petit bourg", "type_scene": "ville",
         "style": {"texte": None, "architecture": "traditionnel"},
         "ville": {"taille_m": [170.0, 150.0], "trame": "grille", "zones": [{"type": "pavillonnaire", "part": 1.0}],
                   "etages": None, "largeur_rues_m": 9.0, "riviere": False, "arbres_alignement": True,
                   "voitures": False, "style": "traditionnel"}}


class Lois(unittest.TestCase):
    def test_le_programme_d_une_maison_suit_sa_surface(self):
        for surface in (30.0, 60.0, 95.0, 150.0):
            with self.subTest(surface=surface):
                pieces = univers.programme_maison(surface)
                fonctions = [f for _, f, _, _ in pieces]
                self.assertIn("entree", fonctions)
                self.assertIn("salon", fonctions)
                self.assertTrue(any(f.startswith("salle_d") for f in fonctions))
                for _, f, s, _ in pieces:
                    lo, hi = voc.FONCTIONS_PIECES[f]["surface"]
                    self.assertTrue(lo <= s <= hi, (f, s))
        self.assertGreater(len(univers.programme_maison(150.0)), len(univers.programme_maison(30.0)))

    def test_deplacer_tourne_et_pose_parties_et_objets_ensemble(self):
        objet = Objet("cube", "cube", [Partie(g.boite(1.0, 1.0, 1.0), "bois_chene")], 1.0, 1.0, 1.0)
        noeud = Noeud("maison", parties=[Partie(g.boite(2.0, 0.1, 2.0, x=1.0, z=0.0), "parquet_chene")],
                      instances=[Instance(objet, Pose(1.0, 0.0, 0.0), "cube")])
        univers.deplacer(noeud, math.pi / 2, (1.0, 0.0), (10.0, 0.15, 20.0))
        centre = noeud.parties[0].maillage.bounds.mean(axis=0)
        self.assertTrue(np.allclose(centre[[0, 2]], (10.0, 20.0), atol=1e-6))       # le centre suit
        self.assertAlmostEqual(float(noeud.parties[0].maillage.bounds[1][1]), 0.25, places=6)
        pose = noeud.instances[0].pose
        self.assertTrue(np.allclose((pose.x, pose.y, pose.z, pose.lacet), (10.0, 0.15, 20.0, math.pi / 2)))


class Bourg(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.res = univers.construire_monde(BOURG, 11, fabrique_meubles())

    def test_des_maisons_visitables_dans_leur_parcelle_porte_sur_rue(self):
        plan = self.res["plan"]
        visitables = [(ilot, lot, b) for ilot, lot, b in plan.batiments() if b.visitable]
        self.assertGreaterEqual(len(visitables), 1)
        self.assertEqual(self.res["mesures"]["maisons_visitables"], len(visitables))
        for _, lot, b in visitables:
            self.assertTrue(b.emprise.within(lot.polygone.buffer(0.06)))
            self.assertEqual(b.etages, 1)
        m = self.res["mesures"]
        self.assertEqual((m["chevauchements"], m["portes_bloquees"], m["batiments_sur_voirie"]), (0, 0, 0))
        self.assertEqual(m["inaccessibles"], [])
        self.assertGreater(m["meubles_places"], 10)

    def test_le_depart_est_dehors_face_a_une_porte_qui_regarde_la_rue(self):
        depart = self.res["depart"]
        self.assertIn("maison visitable", depart["lieu"])
        from shapely.geometry import Point
        plan = self.res["plan"]
        dehors = Point(depart["x"], depart["z"])
        self.assertFalse(any(b.emprise.contains(dehors) for _, _, b in plan.batiments()))
        # la porte (4 m devant) est plus près de la chaussée que le centre de sa maison
        porte = (depart["x"] + 4 * depart["direction"][0], depart["z"] + 4 * depart["direction"][1])
        maison = min((b for _, _, b in plan.batiments() if b.visitable), key=lambda b: b.emprise.distance(Point(*porte)))
        c = maison.emprise.centroid
        self.assertLess(plan.chaussee.distance(Point(*porte)), plan.chaussee.distance(c))

    def test_la_campagne_entoure_la_ville_sans_passer_dessous(self):
        racine = self.res["scene"].racine
        campagne = next(n for n in racine.parcourir() if n.nom == "campagne")
        sol = next(n for n in campagne.parcourir() if n.nom == "sol")
        plan = self.res["plan"]
        dedans = plan.rectangle.buffer(-2.0)
        from shapely import contains_xy
        for p in sol.parties:
            c = p.maillage.triangles_center
            self.assertFalse(contains_xy(dedans, c[:, 0], c[:, 2]).any(), p.materiau)
        W, D = plan.taille
        etendue = max(float(np.ptp(np.vstack([p.maillage.vertices for p in sol.parties]), axis=0)[k]) for k in (0, 2))
        self.assertGreater(etendue, max(W, D) * 1.4)


if __name__ == "__main__":
    unittest.main()
