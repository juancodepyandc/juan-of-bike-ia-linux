"""Disposition des meubles du moteur « monde » : contraintes MESURÉES sur les instances livrées.

Logement de 6 et de 4 pièces meublé avec les meubles typiques de chaque fonction (objets provisoires aux
dimensions moyennes du vocabulaire) : 0 chevauchement, 0 objet hors pièce, 0 porte bloquée, 0 fenêtre
masquée, chaque objet posé atteignable depuis une porte ; tout objet demandé est soit posé, soit rendu en
échec avec une raison. Une demande impossible (3 lits doubles dans un wc) est refusée explicitement.
"""
from __future__ import annotations

import math
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "application" / "python-services"))
from monde import vocabulaire as voc  # noqa: E402
from monde.disposition import (Demande, demandes_typiques, disposer, mesurer_instances, meubler,  # noqa: E402
                               objet_provisoire, scene_meublee)
from monde.plan import PieceDemandee as P, concevoir_plan  # noqa: E402

SIX = [P("entree", "entree", 5.0), P("salon", "salon", 24.0, ["cuisine"]), P("cuisine", "cuisine", 10.0),
       P("chambre", "chambre", 12.0), P("bain", "salle_de_bain", 6.0), P("wc", "wc", 1.6)]
QUATRE = [P("entree", "entree", 4.0), P("salon", "salon", 20.0), P("chambre", "chambre", 11.0),
          P("bain", "salle_de_bain", 5.0)]


def _verifier(test: unittest.TestCase, plan, dispositions) -> None:
    for nom, d in dispositions.items():
        piece = plan.piece(nom)
        with test.subTest(piece=nom):
            for cle in ("chevauchements", "hors_piece", "portes_bloquees", "fenetres_bloquees", "degagements_occupes"):
                test.assertEqual(d.mesures[cle], 0, (cle, d.mesures))
            test.assertEqual(d.mesures["inaccessibles"], [])
            # recalcul indépendant depuis les seules instances livrées
            m = mesurer_instances(piece, d.instances, plan.hauteur_plafond)
            for cle in ("chevauchements", "hors_piece", "portes_bloquees", "fenetres_bloquees", "degagements_occupes"):
                test.assertEqual(m[cle], 0, (cle, m))
            test.assertEqual(m["inaccessibles"], [])
            # rien n'est perdu en silence
            test.assertEqual(len(d.instances) + len(d.echecs), d.mesures["demandes"])
            for e in d.echecs:
                test.assertTrue(e["raison"] and len(e["raison"]) > 10, e)
            # chaque objet au sol est dans la pièce ; chaque objet suspendu touche le plafond
            for inst in d.instances:
                o = inst.objet
                test.assertTrue(o.emprise(inst.pose).within(piece.polygone.buffer(0.011)), inst.nom)
                test.assertLessEqual(inst.pose.y + o.hauteur, plan.hauteur_plafond + 1e-6, inst.nom)
                if o.plafond:
                    test.assertAlmostEqual(inst.pose.y + o.hauteur, plan.hauteur_plafond, places=6)


class LogementMeuble(unittest.TestCase):
    def test_six_pieces_deux_graines(self):
        for graine in (0, 1):
            plan = concevoir_plan(SIX, graine=graine)
            demandes = {p.nom: demandes_typiques(p.fonction) for p in plan.pieces}
            dispositions = meubler(plan, demandes, graine=graine)
            _verifier(self, plan, dispositions)
            places = sum(len(d.instances) for d in dispositions.values())
            voulus = sum(d.mesures["demandes"] for d in dispositions.values())
            self.assertGreaterEqual(places / voulus, 0.8, (places, voulus))      # mesuré : 0,90 à 0,95
            # les meubles structurants sont là
            for nom, categorie in (("salon", "canape"), ("chambre", "lit_double"), ("cuisine", "plan_de_travail"),
                                   ("bain", "baignoire"), ("wc", "wc")):
                with self.subTest(graine=graine, piece=nom):
                    self.assertIn(categorie, [i.objet.categorie for i in dispositions[nom].instances])

    def test_quatre_pieces(self):
        plan = concevoir_plan(QUATRE, graine=2)
        dispositions = meubler(plan, {p.nom: demandes_typiques(p.fonction) for p in plan.pieces}, graine=2)
        _verifier(self, plan, dispositions)

    def test_scene_exportable_avec_instances_dans_leur_piece(self):
        plan = concevoir_plan(QUATRE, graine=0)
        dispositions = meubler(plan, {p.nom: demandes_typiques(p.fonction) for p in plan.pieces}, graine=0)
        scene = scene_meublee(plan, dispositions, plafond=False)
        noeuds = {n.nom: n for n in scene.racine.enfants}
        for nom, d in dispositions.items():
            noms = {i.nom for i in noeuds[nom].instances}
            self.assertTrue({i.nom for i in d.instances} <= noms)


class Relations(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        plan = concevoir_plan([P("chambre", "chambre", 14.0)], graine=0)
        cls.piece = plan.pieces[0]
        cls.d = disposer(cls.piece, demandes_typiques("chambre"), graine=0)
        cls.par_nom = {i.nom: i for i in cls.d.instances}

    def test_tout_est_place_dans_une_chambre_de_14_m2(self):
        self.assertEqual(self.d.echecs, [])

    def test_tables_de_chevet_de_part_et_d_autre_du_lit(self):
        lit = self.par_nom["lit_double_1"]
        cotes = []
        for nom in ("table_de_chevet_1", "table_de_chevet_2"):
            t = self.par_nom[nom]
            c, s = math.cos(lit.pose.lacet), math.sin(lit.pose.lacet)
            dx, dz = t.pose.x - lit.pose.x, t.pose.z - lit.pose.z
            cotes.append(math.copysign(1.0, c * dx - s * dz))
            self.assertLess(t.objet.emprise(t.pose).distance(lit.objet.emprise(lit.pose)), 0.36)
        self.assertEqual(sorted(cotes), [-1.0, 1.0])

    def test_lampe_sur_la_table_de_chevet(self):
        for lampe in ("lampe_de_table_1", "lampe_de_table_2"):
            inst = self.par_nom[lampe]
            support = self.par_nom[inst.meta["support"]]
            self.assertAlmostEqual(inst.pose.y, support.objet.surfaces[0].hauteur)
            self.assertTrue(support.objet.emprise(support.pose).contains(
                inst.objet.emprise(inst.pose).centroid))

    def test_tableau_au_mur_au_dessus_du_lit(self):
        tableau, lit = self.par_nom["tableau_1"], self.par_nom["lit_double_1"]
        self.assertGreaterEqual(tableau.pose.y, lit.objet.hauteur + 0.1 - 1e-9)
        self.assertLess(self.piece.polygone.exterior.distance(
            tableau.objet.emprise(tableau.pose).centroid), tableau.objet.profondeur)

    def test_dos_au_mur(self):
        for nom in ("lit_double_1", "armoire_1", "commode_1"):
            inst = self.par_nom[nom]
            dos = inst.pose.vers_monde(0.0, -inst.objet.profondeur / 2)
            from shapely.geometry import Point
            self.assertLess(self.piece.polygone.exterior.distance(Point(dos)), 0.02, nom)

    def test_chaises_autour_de_la_table_tournees_vers_elle(self):
        plan = concevoir_plan([P("repas", "salle_a_manger", 18.0)], graine=0)
        d = disposer(plan.pieces[0], demandes_typiques("salle_a_manger"), graine=0)
        table = next(i for i in d.instances if i.objet.categorie == "table_a_manger")
        chaises = [i for i in d.instances if i.objet.categorie == "chaise"]
        self.assertGreaterEqual(len(chaises), 4)
        for ch in chaises:
            fx, fz = ch.pose.face()
            vx, vz = table.pose.x - ch.pose.x, table.pose.z - ch.pose.z
            self.assertGreater((fx * vx + fz * vz) / math.hypot(vx, vz), 0.5, ch.nom)


class Echecs(unittest.TestCase):
    def test_trois_lits_dans_un_wc_sont_refuses_avec_raison(self):
        plan = concevoir_plan([P("wc", "wc", 4.0)], graine=0)
        d = disposer(plan.pieces[0], [Demande("lit_double", 3, [("contre_mur", None)])], graine=0)
        self.assertEqual(d.instances, [])
        self.assertEqual(len(d.echecs), 3)
        for e in d.echecs:
            self.assertEqual(e["categorie"], "lit_double")
            self.assertIn("aucune pose", e["raison"])
        self.assertEqual(d.mesures["places"], 0)
        self.assertEqual(d.mesures["demandes"], 3)

    def test_objet_sans_sa_cible_est_explique(self):
        plan = concevoir_plan([P("salon", "salon", 20.0)], graine=0)
        d = disposer(plan.pieces[0], [Demande("lampe_de_table", 1, [("sur", "commode")])], graine=0)
        self.assertEqual(len(d.echecs), 1)
        self.assertIn("commode", d.echecs[0]["raison"])

    def test_cle_hors_vocabulaire(self):
        plan = concevoir_plan([P("salon", "salon", 20.0)], graine=0)
        with self.assertRaises(KeyError):
            disposer(plan.pieces[0], [Demande("licorne")])
        with self.assertRaises(KeyError):
            disposer(plan.pieces[0], [Demande("canape", 1, [("en_lévitation", None)])])


class ObjetProvisoire(unittest.TestCase):
    def test_dimensions_moyennes_et_drapeaux_du_vocabulaire(self):
        for cle, spec in voc.CATEGORIES.items():
            o = objet_provisoire(cle, 0, {})
            with self.subTest(categorie=cle):
                self.assertAlmostEqual(o.largeur, sum(spec["largeur"]) / 2)
                self.assertAlmostEqual(o.profondeur, sum(spec["profondeur"]) / 2)
                self.assertEqual(o.mural, spec["mural"])
                self.assertEqual(o.sol_partage, spec["sol_partage"])
                self.assertEqual(bool(o.surfaces), spec["support"])
                for p in o.parties:
                    voc.materiau(p.materiau)
                    (x0, y0, z0), (x1, y1, z1) = p.maillage.bounds
                    self.assertGreaterEqual(y0, -1e-9)
                    self.assertLessEqual(y1, o.hauteur + 1e-6)
                    self.assertLessEqual(max(abs(x0), abs(x1)), o.largeur / 2 + 1e-6)
                    self.assertLessEqual(max(abs(z0), abs(z1)), o.profondeur / 2 + 0.013)

    def test_repli_compact_aux_dimensions_minimales(self):
        # cuisine étroite : le linéaire moyen (2,4 m) n'entre pas, le linéaire minimal (1,2 m) oui
        plan = concevoir_plan([P("cuisine", "cuisine", 4.2)], rapport=1.2, graine=0)
        d = disposer(plan.pieces[0], [Demande("plan_de_travail", 1, [("contre_mur", None)])], graine=0)
        self.assertEqual(len(d.instances), 1, d.echecs)
        o = d.instances[0].objet
        if o.meta.get("compact"):
            self.assertAlmostEqual(o.largeur, voc.CATEGORIES["plan_de_travail"]["largeur"][0])


if __name__ == "__main__":
    unittest.main()
