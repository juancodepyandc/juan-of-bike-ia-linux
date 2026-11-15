"""Plans de logement du moteur « monde » : invariants MESURÉS sur la géométrie livrée (pas sur le rapport du
planificateur), pour des programmes de 2, 4, 6 et 8 pièces et plusieurs graines.

Mesuré : surface totale à 10 % près, largeurs minimales, toutes les pièces atteintes depuis l'entrée par des
portes réellement posées sur un mur commun, pièces à jour en façade avec fenêtre, fenêtres seulement sur les
murs extérieurs, vrais vides dans les murs (rayon à travers une porte ou une fenêtre), pivot des vantaux sur
la charnière, maquette coupée à 1,20 m.
"""
from __future__ import annotations

import sys
import tempfile
import unittest
from collections import deque
from pathlib import Path

import numpy as np
import trimesh
from shapely.geometry import Point

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "application" / "python-services"))
from monde import export_gltf, vocabulaire as voc  # noqa: E402
from monde.ir import Scene  # noqa: E402
from monde.plan import (EP_EXT, EP_INT, MARGE_PORTE, PieceDemandee as P, concevoir_plan,  # noqa: E402
                        construire_geometrie, verifier_plan)

PROGRAMMES = {
    2: [P("sejour", "salon", 22.0), P("douche", "salle_d_eau", 4.0)],
    4: [P("entree", "entree", 4.0), P("salon", "salon", 20.0), P("chambre", "chambre", 11.0),
        P("bain", "salle_de_bain", 5.0)],
    6: [P("entree", "entree", 5.0), P("salon", "salon", 24.0, ["cuisine"]), P("cuisine", "cuisine", 10.0),
        P("chambre", "chambre", 12.0), P("bain", "salle_de_bain", 6.0), P("wc", "wc", 1.6)],
    8: [P("entree", "entree", 6.0), P("salon", "salon", 28.0), P("cuisine", "cuisine", 11.0, ["salon"]),
        P("ch1", "chambre", 13.0), P("ch2", "chambre", 11.0), P("ch3", "chambre_enfant", 10.0),
        P("bain", "salle_de_bain", 6.0), P("wc", "wc", 1.5)],
}
GRAINES = (0, 1, 2, 3)
LARGEUR_SPEC = {"wc": 0.9, "couloir": 0.9, "salle_d_eau": 0.9}


def _plans():
    for n, programme in PROGRAMMES.items():
        for graine in GRAINES:
            yield n, graine, programme, concevoir_plan(programme, graine=graine)


class InvariantsDuPlan(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.plans = list(_plans())

    def test_surface_totale_a_dix_pour_cent(self):
        for n, graine, programme, plan in self.plans:
            with self.subTest(pieces=n, graine=graine):
                voulu = sum(p.surface for p in programme)
                noms = {p.nom for p in programme}
                obtenu = sum(p.polygone.area for p in plan.pieces if p.nom in noms)
                self.assertLess(abs(obtenu - voulu) / voulu, 0.10, (obtenu, voulu))
                # emprise ≥ pièces, pièces disjointes et dans l'emprise
                for i, a in enumerate(plan.pieces):
                    self.assertTrue(a.polygone.buffer(-1e-6).within(plan.emprise))
                    for b in plan.pieces[i + 1:]:
                        self.assertLess(a.polygone.intersection(b.polygone).area, 1e-6, (a.nom, b.nom))

    def test_largeurs_minimales(self):
        for n, graine, _, plan in self.plans:
            for p in plan.pieces:
                with self.subTest(pieces=n, graine=graine, piece=p.nom):
                    x0, z0, x1, z1 = p.polygone.bounds
                    self.assertGreaterEqual(min(x1 - x0, z1 - z0), LARGEUR_SPEC.get(p.fonction, 1.8) - 1e-6)

    def test_toutes_les_pieces_atteintes_par_de_vraies_portes(self):
        for n, graine, _, plan in self.plans:
            with self.subTest(pieces=n, graine=graine):
                pieces = {p.nom: p for p in plan.pieces}
                graphe = {nom: set() for nom in pieces}
                for o in plan.ouvertures:
                    if o.type != "porte":
                        continue
                    a, b = o.pieces
                    # la porte est sur le mur commun : à une demi-cloison de chaque sol libre
                    for nom in (a, b):
                        self.assertAlmostEqual(pieces[nom].polygone.distance(Point(o.centre)), EP_INT / 2, places=6)
                    # ses deux bords restent à ≥ 0,15 m des extrémités du mur, des deux côtés
                    dx, dz = o.direction
                    for s in (-1, 1):
                        bord = (o.centre[0] + s * dx * (o.largeur / 2 + MARGE_PORTE - 1e-6),
                                o.centre[1] + s * dz * (o.largeur / 2 + MARGE_PORTE - 1e-6))
                        for nom in (a, b):
                            self.assertLess(pieces[nom].polygone.distance(Point(bord)), EP_INT / 2 + 1e-6)
                    self.assertTrue(0.83 - 1e-9 <= o.largeur <= 0.9 + 1e-9)
                    self.assertAlmostEqual(o.hauteur, 2.04)
                    graphe[a].add(b)
                    graphe[b].add(a)
                vus, file = {plan.entree}, deque([plan.entree])
                while file:
                    for m in graphe[file.popleft()]:
                        if m not in vus:
                            vus.add(m)
                            file.append(m)
                self.assertEqual(vus, set(pieces), "pièces inaccessibles depuis l'entrée")
                entrees = [o for o in plan.ouvertures if o.type == "porte_entree"]
                self.assertEqual(len(entrees), 1)
                self.assertIn(pieces[entrees[0].pieces[0]].fonction, ("entree", "salon"))

    def test_jour_en_facade_et_fenetres_seulement_sur_murs_exterieurs(self):
        for n, graine, _, plan in self.plans:
            contour = plan.emprise.exterior
            with self.subTest(pieces=n, graine=graine):
                for p in plan.pieces:
                    if voc.FONCTIONS_PIECES[p.fonction]["fenetre"]:
                        self.assertGreater(p.polygone.intersection(contour).length, 1.0, p.nom)
                        self.assertTrue(any(o.type == "fenetre" for o in p.ouvertures), p.nom)
                for o in plan.ouvertures:
                    if o.type != "fenetre":
                        continue
                    self.assertIsNone(o.pieces[1])
                    c = Point(o.centre)
                    self.assertFalse(plan.emprise.contains(c))                 # dehors : dans le mur extérieur
                    self.assertAlmostEqual(c.distance(contour), EP_EXT / 2, places=6)
                    # la baie entière est en façade de SA pièce, loin des angles
                    p = plan.piece(o.pieces[0])
                    dx, dz = o.direction
                    for s in (-1, 1):
                        bord = Point(o.centre[0] + s * dx * (o.largeur / 2 + 0.4 - 1e-6),
                                     o.centre[1] + s * dz * (o.largeur / 2 + 0.4 - 1e-6))
                        self.assertLess(p.polygone.distance(bord), EP_EXT / 2 + 1e-6)
                    # jamais devant une porte
                    for porte in plan.ouvertures:
                        if porte.type == "porte_entree":
                            self.assertGreater(o.rectangle().distance(porte.rectangle()), 0.3)

    def test_verification_independante_et_diversite(self):
        emprises = {}
        for n, graine, _, plan in self.plans:
            v = verifier_plan(plan)
            with self.subTest(pieces=n, graine=graine):
                for cle in ("inaccessibles", "etroites", "sans_jour", "sans_fenetre", "fenetres_interieures"):
                    self.assertEqual(v[cle], [], cle)
                self.assertTrue(plan.mesures["valide"], plan.mesures["violations"])
            emprises.setdefault(n, set()).add(tuple(round(c, 2) for c in plan.emprise.bounds))
        for n, formes in emprises.items():
            self.assertGreater(len(formes), 1, f"{n} pièces : la graine ne change rien")

    def test_couloir_ajoute_au_dela_de_cinq_pieces(self):
        for n, graine, _, plan in self.plans:
            fonctions = [p.fonction for p in plan.pieces]
            with self.subTest(pieces=n, graine=graine):
                if n > 5:
                    self.assertIn("couloir", fonctions)
                    couloir = next(p for p in plan.pieces if p.fonction == "couloir")
                    self.assertIsNone(couloir.demandee)

    def test_entree_invalide(self):
        with self.assertRaises(KeyError):
            concevoir_plan([P("x", "piscine_olympique", 10.0)])
        with self.assertRaises(ValueError):
            concevoir_plan([P("a", "salon", 10.0), P("a", "chambre", 10.0)])
        with self.assertRaises(KeyError):
            concevoir_plan([P("a", "salon", 10.0, ["fantome"])])


def _murs(noeud) -> trimesh.Trimesh:
    return trimesh.util.concatenate([p.maillage for p in noeud.parties if p.nom in ("murs", "facade")])


def _traverse(maillage: trimesh.Trimesh, a, b) -> bool:
    origine = np.array([[a[0], a[1], a[2]]], dtype=float)
    direction = np.array([[b[0] - a[0], b[1] - a[1], b[2] - a[2]]], dtype=float)
    longueur = float(np.linalg.norm(direction))
    points, rayons, _ = maillage.ray.intersects_location(origine, direction / longueur)
    return bool(len(points)) and bool(np.any(np.linalg.norm(points - origine[0], axis=1) <= longueur))


class Geometrie(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.plan = concevoir_plan(PROGRAMMES[6], graine=1)
        cls.noeud = construire_geometrie(cls.plan)
        cls.murs = trimesh.util.concatenate([_murs(n) for n in cls.noeud.enfants if n.nom != "plafonds"])

    def test_un_noeud_par_piece_facades_et_plafonds(self):
        noms = [n.nom for n in self.noeud.enfants]
        self.assertEqual(set(noms) - {"facades", "plafonds"}, {p.nom for p in self.plan.pieces})
        self.assertIn("plafonds", noms)
        self.assertNotIn("plafonds", [n.nom for n in construire_geometrie(self.plan, plafond=False).enfants])

    def test_portes_et_fenetres_sont_de_vrais_vides(self):
        for o in self.plan.ouvertures:
            nx, nz = o.normale
            y = o.allege + o.hauteur / 2
            a = (o.centre[0] - nx * 0.4, y, o.centre[1] - nz * 0.4)
            b = (o.centre[0] + nx * 0.4, y, o.centre[1] + nz * 0.4)
            with self.subTest(ouverture=o.nom):
                self.assertFalse(_traverse(self.murs, a, b), "le mur n'est pas percé")
                # témoin : 30 cm au-dessus du linteau, le mur est plein
                ay = (a[0], o.allege + o.hauteur + 0.15, a[2])
                by = (b[0], o.allege + o.hauteur + 0.15, b[2])
                if o.allege + o.hauteur + 0.2 < self.plan.hauteur_plafond:
                    self.assertTrue(_traverse(self.murs, ay, by), "le linteau manque")

    def test_vantaux_pivotent_sur_la_charniere(self):
        vantaux = {i.nom: i for n in self.noeud.enfants for i in n.instances}
        portes = [o for o in self.plan.ouvertures if o.type in ("porte", "porte_entree")]
        self.assertEqual(set(vantaux), {o.nom for o in portes})
        for o in portes:
            inst = vantaux[o.nom]
            with self.subTest(porte=o.nom):
                self.assertTrue(o.nom.startswith("porte_"))
                # l'origine du nœud est sur un montant de la baie (à une demi-largeur du centre, le long du mur)
                dx, dz = inst.pose.x - o.centre[0], inst.pose.z - o.centre[1]
                le_long = dx * o.direction[0] + dz * o.direction[1]
                self.assertAlmostEqual(abs(le_long), o.largeur / 2, delta=0.02)
                # le vantail fermé couvre la baie : son autre extrémité est sur l'autre montant
                bout = inst.pose.vers_monde(inst.objet.largeur, 0.0)
                le_long_bout = (bout[0] - o.centre[0]) * o.direction[0] + (bout[1] - o.centre[1]) * o.direction[1]
                self.assertAlmostEqual(le_long_bout, -le_long, delta=0.03)
                # l'angle d'ouverture amène le vantail du côté de la pièce où il débat
                ouvert = inst.pose.__class__(inst.pose.x, inst.pose.z,
                                             inst.pose.lacet + inst.meta["angle_ouverture_rad"], 0.0)
                milieu = ouvert.vers_monde(inst.objet.largeur / 2, 0.0)
                piece = self.plan.piece(o.ouvre_vers)
                self.assertTrue(piece.polygone.buffer(0.02).contains(Point(milieu)), "s'ouvre du mauvais côté")

    def test_maquette_coupe_les_murs_a_1m20(self):
        maquette = construire_geometrie(self.plan, maquette=True)
        haut = max(float(p.maillage.bounds[1][1]) for n in maquette.enfants for p in n.parties
                   if p.nom in ("murs", "facade"))
        self.assertLessEqual(haut, 1.2 + 1e-6)
        self.assertNotIn("plafonds", [n.nom for n in maquette.enfants])

    def test_cloison_mitoyenne_dans_le_materiau_de_chaque_piece(self):
        for o in self.plan.ouvertures:
            if o.type != "porte":
                continue
            a, b = (self.plan.piece(n) for n in o.pieces)
            noeuds = {n.nom: n for n in self.noeud.enfants}
            for piece in (a, b):
                murs = [p for p in noeuds[piece.nom].parties if p.nom == "murs"]
                self.assertEqual(len(murs), 1)
                self.assertEqual(murs[0].materiau, piece.murs)
                # le demi-mur de la pièce ne dépasse pas l'axe de la cloison
                cx0, cz0, cx1, cz1 = piece.cellule.bounds
                (mx0, _, mz0), (mx1, _, mz1) = murs[0].maillage.bounds
                self.assertGreaterEqual(mx0, cx0 - EP_EXT / 2 - 1e-6)
                self.assertLessEqual(mx1, cx1 + EP_EXT / 2 + 1e-6)

    def test_export_glb(self):
        with tempfile.TemporaryDirectory() as tmp:
            rapport = export_gltf.exporter(Scene(self.noeud), Path(tmp) / "plan.glb", resolution=32)
        self.assertIn("verre", rapport["materiaux"])
        self.assertLess(rapport["triangles"], 20000)
        self.assertGreater(rapport["objets"], 0)


if __name__ == "__main__":
    unittest.main()
