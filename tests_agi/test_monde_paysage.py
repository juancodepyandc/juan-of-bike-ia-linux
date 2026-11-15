"""Paysages procéduraux du moteur « monde » : invariants MESURÉS (pas de rendu ici ; les rendus f3d de contrôle
sont produits par `python -m monde.paysage`).

Hauteurs dans l'amplitude du relief, eau là où elle est demandée (et seulement là), aucune végétation dans
l'eau ni sur une pente de plus de 35°, objets posés sur le relief (jamais en l'air), sol par pente et
altitude, Poisson-disque, budget de triangles tenu même avec une fabrique lourde.
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "application" / "python-services"))
from scipy.spatial import cKDTree  # noqa: E402

from monde import geometrie as g  # noqa: E402
from monde import paysage  # noqa: E402
from monde import vocabulaire as voc  # noqa: E402
from monde.ir import Partie  # noqa: E402

CACHE: dict = {}


def scene(taille, relief, biome, eau, graine=0, **kw):
    cle = (taille, relief, biome, eau, graine, tuple(sorted(kw)))
    if cle not in CACHE:
        CACHE[cle] = paysage.terrain(taille, relief, biome, eau=eau, graine=graine, **kw)
    return CACHE[cle]


def instances(racine, nom="vegetation"):
    for n in racine.parcourir():
        if n.nom == nom:
            return n.instances
    return []


class Relief(unittest.TestCase):
    def test_hauteurs_dans_l_amplitude_pour_tous_les_reliefs_et_toutes_les_eaux(self):
        for relief, spec in voc.RELIEFS.items():
            for eau in ("aucune", "lac", "riviere", "mer"):
                with self.subTest(relief=relief, eau=eau):
                    rel, info = paysage.relief_carre(200.0, relief, eau=eau, graine=7)
                    self.assertGreaterEqual(float(rel.h.min()), -1e-9)
                    self.assertLessEqual(float(rel.h.max()), spec["amplitude"] + 1e-9)
                    self.assertAlmostEqual(float(np.ptp(rel.h)), spec["amplitude"], places=6)
                    if eau == "aucune":
                        self.assertIsNone(rel.niveau_eau)
                    else:
                        self.assertTrue(0.0 < rel.niveau_eau < spec["amplitude"])

    def test_part_d_eau_proche_de_la_visee(self):
        for eau, visee in paysage.PARTS_EAU.items():
            parts = []
            for graine in range(3):
                rel, _ = paysage.relief_carre(300.0, "collines", eau=eau, graine=graine)
                parts.append(float((rel.h < rel.niveau_eau).mean()))
            with self.subTest(eau=eau):
                self.assertGreater(min(parts), 0.4 * visee, parts)
                self.assertLess(max(parts), 2.0 * visee, parts)

    def test_le_relief_est_continu_et_la_pente_moyenne_raisonnable(self):
        rel, _ = paysage.relief_carre(300.0, "montagneux", graine=1)
        pente = rel._pente
        self.assertLess(float(np.median(pente)), 35.0)       # une montagne, pas un champ d'aiguilles
        rel, _ = paysage.relief_carre(300.0, "plat", graine=1)
        self.assertLess(float(rel._pente.max()), 5.0)

    def test_une_cle_inconnue_est_une_erreur(self):
        with self.assertRaises(KeyError):
            paysage.relief_carre(100.0, "abyssal")
        with self.assertRaises(KeyError):
            paysage.relief_carre(100.0, "plat", eau="ocean_de_lave")
        with self.assertRaises(KeyError):
            paysage.terrain(100.0, "plat", "jungle_lunaire")


class Sol(unittest.TestCase):
    def test_neige_en_altitude_seulement_sur_un_relief_eleve_et_roche_sur_les_pentes(self):
        racine, rel = scene(300.0, "montagneux", "foret_de_coniferes", "lac", 1)
        sol = next(n for n in racine.parcourir() if n.nom == "sol")
        mats = {p.materiau: p.maillage for p in sol.parties if p.nom != "jupe"}
        self.assertIn("neige", mats)
        self.assertIn("roche", mats)
        self.assertIn("gravier", mats)                    # rivage du lac
        hmin = float(rel.h.min())
        neige_y = mats["neige"].triangles_center[:, 1]
        self.assertGreater(float(np.median(neige_y)) - hmin, 0.6 * rel.amplitude)
        pente_roche = np.degrees(np.arccos(np.clip(mats["roche"].face_normals[:, 1], -1, 1)))
        pente_terre = np.degrees(np.arccos(np.clip(mats["terre"].face_normals[:, 1], -1, 1)))
        self.assertGreater(float(np.median(pente_roche)), float(np.median(pente_terre)) + 10.0)
        racine2, _ = scene(250.0, "cotier", "plage", "mer", 2)
        sol2 = next(n for n in racine2.parcourir() if n.nom == "sol")
        self.assertNotIn("neige", {p.materiau for p in sol2.parties})

    def test_normales_du_terrain_vers_le_haut_et_eau_plane(self):
        racine, rel = scene(250.0, "cotier", "plage", "mer", 2)
        sol = next(n for n in racine.parcourir() if n.nom == "sol")
        for p in sol.parties:
            if p.nom == "jupe":
                continue
            self.assertTrue(np.all(p.maillage.face_normals[:, 1] > 0.0), p.nom)
        eau = next(n for n in racine.parcourir() if n.nom == "eau").parties[0].maillage
        dessus = eau.face_normals[:, 1] > 0.5
        self.assertTrue(np.allclose(eau.vertices[eau.faces[dessus]][..., 1], rel.niveau_eau))


class Vegetation(unittest.TestCase):
    CAS = [(300.0, "montagneux", "foret_de_coniferes", "lac", 1), (250.0, "cotier", "plage", "mer", 2),
           (200.0, "collines", "foret_temperee", "riviere", 3)]

    def test_aucune_vegetation_dans_l_eau_ni_sur_une_pente_forte(self):
        for cas in self.CAS:
            racine, rel = scene(*cas)
            inst = instances(racine)
            with self.subTest(cas=cas):
                self.assertGreater(len(inst), 30)
                x = np.array([i.pose.x for i in inst])
                z = np.array([i.pose.z for i in inst])
                self.assertFalse(np.any(rel(x, z) < rel.niveau_eau))
                self.assertTrue(np.all(rel.pente_deg(x, z) <= paysage.PENTE_MAX_VEGETATION_DEG))

    def test_objets_poses_sur_le_relief_jamais_en_l_air(self):
        racine, rel = scene(*self.CAS[0])
        for i in instances(racine):
            h = float(rel(i.pose.x, i.pose.z))
            self.assertLessEqual(i.pose.y, h + 1e-9)                       # jamais au-dessus du sol
            self.assertGreater(i.pose.y, h - 0.3 * i.objet.hauteur - 2.0)  # ni enterré

    def test_densite_du_biome_respectee_sur_la_surface_utilisable(self):
        racine, rel = scene(200.0, "plat", "foret_temperee", "aucune", 4)
        inst = instances(racine)
        par_cat = {}
        for i in inst:
            par_cat[(i.meta["categorie"], i.meta["style"])] = par_cat.get((i.meta["categorie"], i.meta["style"]), 0) + 1
        for cat, style, densite in voc.BIOMES["foret_temperee"]["vegetation"]:
            attendu = densite * 4.0                                         # 4 ha
            with self.subTest(cat=cat, style=style):
                self.assertGreater(par_cat.get((cat, style), 0), 0.6 * attendu)
                self.assertLessEqual(par_cat.get((cat, style), 0), 1.05 * attendu)

    def test_poisson_disque_respecte_la_distance_minimale(self):
        pts = paysage.poisson_disque(0.0, 0.0, 80.0, 60.0, 3.0, graine=1)
        self.assertGreater(len(pts), 200)
        d, _ = cKDTree(pts).query(pts, k=2)
        self.assertGreaterEqual(float(d[:, 1].min()), 3.0 - 1e-9)

    def test_budget_tenu_avec_une_fabrique_lourde(self):
        def lourde(categorie, graine, options):
            o = paysage.objet_provisoire(categorie, graine, options)
            o.parties.append(Partie(g.sphere(1.0, subdivisions=4, y=2.0), "feuillage", "masse"))   # ~5 000 tri
            return o

        racine, _ = paysage.terrain(300.0, "collines", "foret_de_coniferes", eau="lac", graine=1, fabrique=lourde)
        self.assertLess(paysage.triangles_noeud(racine), paysage.BUDGET_PAYSAGE)
        veg = next(n for n in racine.parcourir() if n.nom == "vegetation")
        self.assertLess(veg.extras["rapport"]["eclaircissement"], 1.0)

    def test_budget_par_defaut_300_m(self):
        racine, _ = scene(*self.CAS[0])
        self.assertLess(paysage.triangles_noeud(racine), paysage.BUDGET_PAYSAGE)
        self.assertTrue(all(n.fusion for n in racine.enfants))


class Provisoire(unittest.TestCase):
    def test_chaque_categorie_exterieure_a_une_silhouette_aux_bons_materiaux(self):
        for cle, spec in voc.CATEGORIES.items():
            if not spec["exterieur"]:
                continue
            with self.subTest(categorie=cle):
                o = paysage.objet_provisoire(cle, 0, {})
                self.assertTrue(o.parties)
                for p in o.parties:
                    voc.materiau(p.materiau)
                    self.assertIn(p.materiau, spec["materiaux"].values())
                lo = np.min([p.maillage.bounds[0] for p in o.parties], axis=0)
                self.assertGreaterEqual(lo[1], -1e-6)                      # posé au sol
                self.assertLess(paysage.triangles_objet(o), 1500)


if __name__ == "__main__":
    unittest.main()
