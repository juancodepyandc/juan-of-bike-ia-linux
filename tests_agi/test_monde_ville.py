"""Villes procédurales du moteur « monde » : invariants MESURÉS sur des plans générés (pas de rendu ici ;
les rendus f3d de contrôle sont produits par `python -m monde.ville <demo>`).

Chaque test vérifie une loi générale sur plusieurs trames et styles : aucun bâtiment sur la voirie, des
bâtiments dans leur parcelle et disjoints, les parts de zones à ± 15 %, chaque îlot desservi, les étages
dans la fourchette, rien de planté sur la chaussée, des ponts là où une rue franchit l'eau, des UV de façade
alignées sur les étages, un budget de triangles tenu.
"""
from __future__ import annotations

import math
import sys
import unittest
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "application" / "python-services"))
from shapely.geometry import Point  # noqa: E402
from shapely.ops import unary_union  # noqa: E402
from shapely.strtree import STRtree  # noqa: E402

from monde import vocabulaire as voc  # noqa: E402
from monde import ville  # noqa: E402
from monde.ville import ZoneDemandee  # noqa: E402

PLANS: dict[str, ville.PlanVille] = {}

CAS = {
    "grille_moderne": dict(taille=(300.0, 300.0), trame="grille", style="moderne", graine=3,
                           zones=[ZoneDemandee("centre", 0.25), ZoneDemandee("residentiel", 0.35),
                                  ZoneDemandee("parc", 0.15), ZoneDemandee("affaires", 0.25)]),
    "radiale_riviere": dict(taille=(300.0, 300.0), trame="radiale", style="haussmannien", riviere=True, graine=1,
                            zones=[ZoneDemandee("residentiel", 0.6), ZoneDemandee("centre", 0.3),
                                   ZoneDemandee("place", 0.1)]),
    "organique_pavillons": dict(taille=(300.0, 260.0), trame="organique", style="traditionnel", graine=5,
                                zones=[ZoneDemandee("pavillonnaire", 0.85), ZoneDemandee("place", 0.15)]),
    "irreguliere_eau": dict(taille=(320.0, 280.0), trame="grille_irreguliere", style="industriel", graine=2,
                            zones=[ZoneDemandee("industriel", 0.4), ZoneDemandee("residentiel", 0.4),
                                   ZoneDemandee("eau", 0.2)]),
}


def plan(nom: str) -> ville.PlanVille:
    if nom not in PLANS:
        PLANS[nom] = ville.concevoir_ville(**CAS[nom])
    return PLANS[nom]


class Vocabulaire(unittest.TestCase):
    def test_les_gabarits_couvrent_toutes_les_zones_et_citent_des_materiaux_connus(self):
        self.assertEqual(set(ville.GABARITS_ZONE), set(voc.ZONES_VILLE))
        for z, gab in ville.GABARITS_ZONE.items():
            voc.materiau(gab["sol"])
        for base, uni in ville.MATERIAU_UNI.items():
            voc.materiau(base)
            voc.materiau(uni)
        for couleur in ville.TEINTES_AUTOMOBILES:
            voc.materiau(f"carrosserie:{couleur}")

    def test_une_cle_inconnue_est_une_erreur(self):
        with self.assertRaises(KeyError):
            ZoneDemandee("quartier_magique", 0.5)
        with self.assertRaises(KeyError):
            ville.concevoir_ville(trame="fractale")
        with self.assertRaises(KeyError):
            ville.concevoir_ville(style="baroque_spatial")

    def test_profil_de_rue(self):
        for largeur in (8.0, 12.0, 16.8, 24.0):
            p = ville.profil_rue(largeur)
            self.assertTrue(2.0 <= p["trottoir"] <= 4.0)
            self.assertAlmostEqual(2 * p["trottoir"] + p["chaussee"], max(largeur, 2 * p["trottoir"] + 3.0), places=6)
            self.assertGreaterEqual(p["voies"], 1)
            self.assertGreater(p["largeur_voie"], 2.5)


class Plans(unittest.TestCase):
    def test_aucun_batiment_ne_touche_chaussee_ni_trottoir(self):
        for nom in CAS:
            p = plan(nom)
            voirie = unary_union([p.chaussee, p.trottoirs])
            with self.subTest(cas=nom):
                self.assertGreater(len(p.batiments()), 20)
                for _, _, b in p.batiments():
                    self.assertLess(b.emprise.intersection(voirie).area, 0.01)

    def test_batiments_dans_leur_parcelle_et_disjoints(self):
        for nom in CAS:
            p = plan(nom)
            emprises = [b.emprise for _, _, b in p.batiments()]
            with self.subTest(cas=nom):
                for _, lot, b in p.batiments():
                    self.assertTrue(b.emprise.within(lot.polygone.buffer(0.01)))
                arbre = STRtree(emprises)
                for i, e in enumerate(emprises):
                    for j in arbre.query(e):
                        if int(j) != i:
                            self.assertLess(e.intersection(emprises[int(j)]).area, 0.01)

    def test_parts_de_zones_a_15_pour_cent(self):
        for nom in CAS:
            p = plan(nom)
            with self.subTest(cas=nom):
                for zone, part in p.parts_demandees.items():
                    mesure = p.parts_mesurees.get(zone, 0.0)
                    self.assertLessEqual(abs(mesure - part) / part, 0.15, (zone, part, mesure))

    def test_chaque_ilot_touche_une_rue(self):
        for nom in CAS:
            p = plan(nom)
            trottoirs = p.trottoirs.buffer(0.5)
            with self.subTest(cas=nom):
                for i in p.ilots:
                    self.assertGreater(i.polygone.intersection(trottoirs).area, 1.0)

    def test_etages_dans_la_fourchette_de_la_zone_ou_imposee(self):
        for nom in CAS:
            p = plan(nom)
            with self.subTest(cas=nom):
                for ilot, _, b in p.batiments():
                    lo, hi = voc.ZONES_VILLE[ilot.zone]["etages"]
                    self.assertTrue(lo <= b.etages <= hi, (ilot.zone, b.etages))
                    attendu = b.base + b.hauteur_rdc + (b.etages - 1) * b.hauteur_etage
                    self.assertAlmostEqual(max(v.y1 for v in b.volumes), attendu, places=6)
        impose = ville.concevoir_ville(taille=(200.0, 200.0), zones=[ZoneDemandee("residentiel", 1.0)], etages=(2, 3),
                                       graine=4)
        self.assertTrue(all(2 <= b.etages <= 3 for _, _, b in impose.batiments()))

    def test_des_tours_au_centre_des_affaires(self):
        p = plan("grille_moderne")
        tours = [b for i, _, b in p.batiments() if i.zone == "affaires"]
        self.assertTrue(tours)
        self.assertTrue(all(b.toit in ("plat", "terrasse") for b in tours))
        d_aff = np.mean([i.distance for i in p.ilots if i.zone == "affaires"])
        d_res = np.mean([i.distance for i in p.ilots if i.zone == "residentiel"])
        self.assertLess(d_aff, d_res)                 # le plus intense au centre

    def test_arbres_et_lampadaires_jamais_sur_la_chaussee(self):
        for nom in CAS:
            p = plan(nom)
            with self.subTest(cas=nom):
                n = 0
                for pl in p.mobilier:
                    if pl.categorie in ("arbre", "lampadaire_rue", "banc_public", "poubelle_rue", "buisson"):
                        self.assertFalse(p.chaussee.contains(Point(pl.x, pl.z)), pl)
                        n += 1
                self.assertGreater(n, 50)

    def test_lampadaires_tournes_vers_la_chaussee_et_voitures_dans_le_sens_de_la_rue(self):
        p = plan("grille_moderne")
        lampes = [pl for pl in p.mobilier if pl.categorie == "lampadaire_rue"]
        bords = p.chaussee.boundary
        tournees = 0
        for pl in lampes:
            q = bords.interpolate(bords.project(Point(pl.x, pl.z)))
            vers = np.array([q.x - pl.x, q.y - pl.z])
            if np.hypot(*vers) > 3.0:          # lampadaires des allées de parc : pas de chaussée voisine
                continue
            face = np.array([math.sin(pl.lacet), math.cos(pl.lacet)])
            self.assertGreater(face @ (vers / np.hypot(*vers)), 0.9)
            tournees += 1
        self.assertGreater(tournees, 20)
        voitures = [pl for pl in p.mobilier if pl.categorie == "voiture"]
        self.assertGreater(len(voitures), 20)
        arbre = STRtree([s["ligne"] for s in p.segments])
        for pl in voitures:
            seg = p.segments[int(arbre.nearest(Point(pl.x, pl.z)))]["ligne"]
            s = seg.project(Point(pl.x, pl.z))
            a, b = np.asarray(seg.interpolate(max(0, s - 1)).coords[0]), np.asarray(seg.interpolate(s + 1).coords[0])
            d = (b - a) / np.hypot(*(b - a))
            face = np.array([math.sin(pl.lacet), math.cos(pl.lacet)])
            self.assertGreater(abs(face @ d), 0.98)
            self.assertTrue(p.chaussee.contains(Point(pl.x, pl.z)))

    def test_un_pont_partout_ou_une_rue_franchit_l_eau(self):
        for nom in ("radiale_riviere", "irreguliere_eau"):
            p = plan(nom)
            with self.subTest(cas=nom):
                self.assertIsNotNone(p.eau)
                self.assertGreaterEqual(len(p.ponts), 1)
                tabliers = unary_union([pt["polygone"] for pt in p.ponts])
                for r in p.rues:
                    dans_eau = r.ligne.intersection(p.eau)
                    if dans_eau.length > 1.0:
                        self.assertTrue(r.pont, r.rang)
                        self.assertLess(dans_eau.difference(tabliers).length, 0.05)
                # aucun bloc ni bâtiment dans l'eau
                for i in p.ilots:
                    self.assertLess(i.polygone.intersection(p.eau).area, 0.01)

    def test_balayage_toutes_trames_et_tous_styles(self):
        """32 villes (4 trames × 8 styles, 3 programmes de zones, rivière une fois sur quatre) : aucune
        exception, aucun bâtiment sur la voirie ni hors parcelle, parts à ± 15 %."""
        import itertools
        programmes = [[ZoneDemandee("centre", .3), ZoneDemandee("residentiel", .5), ZoneDemandee("parc", .2)],
                      [ZoneDemandee("pavillonnaire", .7), ZoneDemandee("industriel", .3)],
                      [ZoneDemandee("affaires", .4), ZoneDemandee("centre", .3), ZoneDemandee("place", .1),
                       ZoneDemandee("eau", .2)]]
        for k, (trame, style) in enumerate(itertools.product(voc.TRAMES, voc.STYLES_ARCHI)):
            with self.subTest(trame=trame, style=style):
                p = ville.concevoir_ville(taille=(260.0, 240.0), trame=trame, style=style, zones=programmes[k % 3],
                                          graine=k, riviere=(k % 4 == 0))
                voirie = unary_union([p.chaussee, p.trottoirs])
                self.assertGreater(len(p.batiments()), 5)
                for _, lot, b in p.batiments():
                    self.assertLess(b.emprise.intersection(voirie).area, 0.01)
                    self.assertTrue(b.emprise.within(lot.polygone.buffer(0.01)))
                for zone, part in p.parts_demandees.items():
                    self.assertLessEqual(abs(p.parts_mesurees.get(zone, 0.0) - part) / part, 0.15, zone)

    def test_marquages_et_passages_sur_la_chaussee(self):
        p = plan("grille_moderne")
        self.assertGreater(len(p.marquages), 50)
        self.assertGreater(len(p.passages), 20)
        chaussee = p.chaussee.buffer(0.05)
        for m in p.marquages[:200] + p.passages[:200]:
            self.assertGreater(m.intersection(chaussee).area / m.area, 0.9)


class Geometrie(unittest.TestCase):
    def test_uv_de_facade_une_rangee_par_etage_et_travees_entieres(self):
        p = plan("grille_moderne")
        vus = 0
        for _, _, b in p.batiments()[:40]:
            taille = voc.materiau(b.facade)["taille_m"]
            y_ref = b.base + (b.hauteur_rdc if b.commerce else 0.0)
            for v in b.volumes:
                for mat, maillages in ville._murs_volume(v, b, b.facade).items():
                    for m in maillages:
                        uv = np.asarray(m.visual.uv)
                        y = np.asarray(m.vertices)[:, 1]
                        if mat == b.facade:
                            np.testing.assert_allclose(uv[:, 1] * b.hauteur_etage / taille, y - y_ref, atol=1e-6)
                            vus += 1
                        else:
                            t_v = voc.materiau("vitrine")["taille_m"]
                            np.testing.assert_allclose(uv[:, 1] * b.hauteur_rdc / t_v, y - b.base, atol=1e-6)
        self.assertGreater(vus, 100)
        # Travées entières : le u maximal de chaque façade continue est un multiple de taille_m.
        b = next(b for _, _, b in p.batiments() if b.volumes[0].libre is None)
        taille = voc.materiau(b.facade)["taille_m"]
        v = b.volumes[0]
        for m in ville._murs_volume(v, b, b.facade)[b.facade]:
            fin = float(np.asarray(m.visual.uv)[:, 0].max())
            self.assertAlmostEqual(fin / taille, round(fin / taille), places=6)

    def test_normales_des_murs_vers_l_exterieur(self):
        p = plan("radiale_riviere")
        for _, _, b in p.batiments()[:20]:
            for v in b.volumes:
                poly = v.polygone
                for maillages in ville._murs_volume(v, b, b.facade).values():
                    for m in maillages:
                        c = m.triangles_center.mean(axis=0)
                        n = m.face_normals[0]
                        dehors = Point(c[0] + 0.05 * n[0], c[2] + 0.05 * n[2])
                        self.assertFalse(poly.buffer(-1e-3).contains(dehors))
                        self.assertTrue(np.allclose(m.face_normals, m.vertex_normals[m.faces].mean(axis=1), atol=1e-6))

    def test_construction_tient_le_budget_et_garde_peu_de_noeuds(self):
        p = ville.concevoir_ville(taille=(400.0, 400.0), trame="grille", style="moderne", graine=0,
                                  zones=[ZoneDemandee("centre", 0.25), ZoneDemandee("residentiel", 0.35),
                                         ZoneDemandee("parc", 0.15), ZoneDemandee("affaires", 0.25)])
        racine = ville.construire_ville(p)
        tri = ville.triangles_noeud(racine)
        self.assertLess(tri, ville.BUDGET_VILLE)
        noeuds = list(racine.parcourir())
        self.assertLessEqual(len(noeuds), 15)
        self.assertTrue(all(n.fusion for n in noeuds[1:]))
        noms = {n.nom for n in noeuds}
        self.assertTrue({"sol", "voirie", "vegetation", "mobilier", "vehicules"} <= noms, noms)

    def test_une_fabrique_lourde_est_eclaircie_pour_tenir_le_budget(self):
        from monde import geometrie as g
        from monde.ir import Objet, Partie

        def lourde(categorie, graine, options):
            o = ville.objet_provisoire(categorie, graine, options)
            if categorie == "arbre":
                o.parties.append(Partie(g.sphere(1.0, subdivisions=5, y=3.0), "feuillage", "masse"))  # ~20 000 tri
            return o

        p = plan("organique_pavillons")
        racine = ville.construire_ville(p, fabrique=lourde, budget_triangles=600_000)
        self.assertLess(ville.triangles_noeud(racine), 600_000)
        self.assertLess(racine.extras["eclaircissement_vegetation"], 1.0)


if __name__ == "__main__":
    unittest.main()
