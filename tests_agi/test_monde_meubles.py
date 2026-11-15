"""Meubles, objets et végétation paramétriques du moteur « monde » (monde.meubles).

Contrat vérifié pour CHAQUE catégorie du vocabulaire et trois graines : dimensions déclarées = étendue
réelle de la géométrie (1 cm), dans la fourchette bornée ; emprise centrée ; point bas à y = 0 ; matériaux
du vocabulaire ; dessus utilisable des supports ; face vers +Z (dossiers derrière, poignées devant, écran
tourné vers l'avant, phares à l'avant) ; dimensions données respectées ; budgets de triangles ; même
graine = même géométrie. Aucun rendu ici (les planches f3d sont produites par `meubles.inspecter`).
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

import numpy as np
import trimesh

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "application" / "python-services"))
from monde import meubles as mb  # noqa: E402
from monde import vocabulaire as voc  # noqa: E402

GRAINES = (0, 1, 2)
TOL = 0.01


def _sommets(objet, emplacement: str | None = None) -> np.ndarray:
    parties = [p for p in objet.parties if emplacement is None or p.nom == emplacement]
    return np.vstack([np.asarray(p.maillage.vertices) for p in parties])


def _triangles(objet) -> int:
    return sum(len(p.maillage.faces) for p in objet.parties)


class Catalogue(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.objets = {(c, gr): mb._construire(c, None, None, None, None, None, gr)
                      for c in mb.categories_disponibles() for gr in GRAINES}

    def test_les_categories_sont_celles_du_vocabulaire(self):
        self.assertEqual(mb.categories_disponibles(), sorted(voc.CATEGORIES))
        self.assertEqual(set(mb.CONSTRUCTEURS), set(voc.CATEGORIES))

    def test_dimensions_declarees_egales_a_la_geometrie_et_dans_la_fourchette(self):
        for (c, gr), (o, _) in self.objets.items():
            with self.subTest(categorie=c, graine=gr):
                v = _sommets(o)
                lo, hi = v.min(axis=0), v.max(axis=0)
                self.assertAlmostEqual(o.largeur, hi[0] - lo[0], delta=TOL)
                self.assertAlmostEqual(o.hauteur, hi[1] - lo[1], delta=TOL)
                self.assertAlmostEqual(o.profondeur, hi[2] - lo[2], delta=TOL)
                cat = voc.CATEGORIES[c]
                for axe, valeur in (("largeur", o.largeur), ("profondeur", o.profondeur), ("hauteur", o.hauteur)):
                    a, b = cat[axe]
                    self.assertGreaterEqual(valeur, 0.7 * a - TOL, axe)
                    self.assertLessEqual(valeur, 1.4 * b + TOL, axe)

    def test_emprise_centree_et_point_bas_au_sol(self):
        for (c, gr), (o, _) in self.objets.items():
            with self.subTest(categorie=c, graine=gr):
                v = _sommets(o)
                self.assertAlmostEqual(float(v[:, 1].min()), 0.0, places=4)
                self.assertAlmostEqual(float((v[:, 0].min() + v[:, 0].max()) / 2), 0.0, places=3)
                self.assertAlmostEqual(float((v[:, 2].min() + v[:, 2].max()) / 2), 0.0, places=3)

    def test_materiaux_du_vocabulaire_et_emplacements_nommes(self):
        for (c, gr), (o, _) in self.objets.items():
            with self.subTest(categorie=c, graine=gr):
                mats = o.meta["materiaux"]
                self.assertEqual(set(o.meta), {"style", "graine", "materiaux"})
                self.assertTrue(set(voc.CATEGORIES[c]["materiaux"]) <= set(mats))
                for p in o.parties:
                    voc.materiau(p.materiau)
                    self.assertIn(p.nom, mats, "chaque partie porte le nom d'un emplacement")
                    # le matériau est celui de l'emplacement (ou sa base re-teintée : reliures, peinture)
                    self.assertEqual(p.materiau.partition(":")[0], mats[p.nom].partition(":")[0])
                    self.assertTrue(len(p.maillage.faces) > 0)
                    self.assertIsNotNone(getattr(p.maillage.visual, "uv", None))

    def test_drapeaux_copies_du_vocabulaire(self):
        for (c, gr), (o, _) in self.objets.items():
            cat = voc.CATEGORIES[c]
            with self.subTest(categorie=c):
                self.assertEqual(o.mural, cat["mural"])
                self.assertEqual(o.plafond, cat["plafond"])
                self.assertEqual(o.sol_partage, cat["sol_partage"])
                self.assertAlmostEqual(o.degagement, cat["degagement"])
                self.assertAlmostEqual(o.degagement_cotes, cat["degagement_cotes"])

    def test_les_supports_ont_un_dessus_a_leur_hauteur(self):
        for (c, gr), (o, _) in self.objets.items():
            if not voc.CATEGORIES[c]["support"]:
                self.assertEqual(o.surfaces, [], c)
                continue
            with self.subTest(categorie=c, graine=gr):
                self.assertEqual(len(o.surfaces), 1)
                s = o.surfaces[0]
                if c == "plan_de_travail":            # le robinet dépasse du plan
                    self.assertLess(s.hauteur, o.hauteur)
                    self.assertTrue(0.6 <= s.hauteur <= 1.3)
                else:
                    self.assertAlmostEqual(s.hauteur, o.hauteur, delta=TOL)
                xs = [p[0] for p in s.polygone]
                zs = [p[1] for p in s.polygone]
                self.assertAlmostEqual(max(xs) - min(xs), o.largeur, delta=TOL)
                self.assertAlmostEqual(max(zs) - min(zs), o.profondeur, delta=TOL)
                # il y a bien de la matière à la hauteur du dessus (pas un dessus fantôme)
                v = _sommets(o)
                self.assertTrue(np.any(np.abs(v[:, 1] - s.hauteur) < 0.005))

    def test_budgets_de_triangles(self):
        for (c, gr), (o, _) in self.objets.items():
            with self.subTest(categorie=c, graine=gr):
                self.assertLessEqual(_triangles(o), mb.budget_triangles(c))
        self.assertEqual(mb.budget_triangles("voiture"), 9000)
        self.assertEqual(mb.budget_triangles("arbre"), 15000)
        self.assertEqual(mb.budget_triangles("canape"), 6000)

    def test_fidelite_des_constructeurs_avant_ajustement(self):
        """L'ajustement final ne fait que recaler : chaque constructeur vise déjà les bonnes dimensions."""
        for (c, gr), (_, brouillon) in self.objets.items():
            with self.subTest(categorie=c, graine=gr, facteurs=np.round(brouillon.facteurs, 3).tolist()):
                self.assertTrue(np.all(brouillon.facteurs > 0.8) and np.all(brouillon.facteurs < 1.25))


class FaceVersPlusZ(unittest.TestCase):
    def _haut(self, o, part: float = 0.12) -> np.ndarray:
        v = _sommets(o)
        return v[v[:, 1] > o.hauteur * (1.0 - part)]

    def test_dossiers_et_tetes_de_lit_derriere(self):
        for c in ("canape", "fauteuil", "chaise", "lit_simple", "lit_double", "banc_public", "transat"):
            for gr in GRAINES:
                for style in (None, *mb.STYLES_MEUBLES):
                    with self.subTest(categorie=c, graine=gr, style=style):
                        o = mb.generer(c, graine=gr, style=style)
                        self.assertLess(float(self._haut(o)[:, 2].mean()), 0.0)

    def test_poignees_devant(self):
        for c in ("armoire", "commode", "buffet", "table_de_chevet", "meuble_tv", "placard_haut", "refrigerateur",
                  "plan_de_travail", "ilot_cuisine", "console", "lave_vaisselle"):
            for gr in GRAINES:
                with self.subTest(categorie=c, graine=gr):
                    o = mb.generer(c, graine=gr)
                    v = _sommets(o, "poignees")
                    self.assertGreater(float(v[:, 2].mean()), 0.0)
                    self.assertAlmostEqual(float(v[:, 2].max()), o.profondeur / 2, delta=0.03)

    def test_ecran_de_television_tourne_vers_l_avant(self):
        for gr in GRAINES:
            o = mb.generer("television", graine=gr)
            ecran = next(p.maillage for p in o.parties if p.nom == "ecran")
            # un rayon venant de l'avant (+Z) frappe l'écran avant tout le reste
            origine = np.array([[0.0, o.hauteur * 0.6, 5.0]])
            direction = np.array([[0.0, 0.0, -1.0]])
            touches = []
            for p in o.parties:
                pts, _, _ = trimesh.ray.ray_triangle.RayMeshIntersector(p.maillage).intersects_location(
                    origine, direction)
                if len(pts):
                    touches.append((float(pts[:, 2].max()), p.nom))
            self.assertEqual(max(touches)[1], "ecran", touches)
            # et la face avant de l'écran regarde +Z
            aires = ecran.area_faces
            avant = aires[ecran.face_normals[:, 2] > 0.95].sum()
            self.assertGreater(avant, 0.3 * aires.sum())

    def test_voiture_roues_symetriques_phares_devant(self):
        for gr in GRAINES:
            with self.subTest(graine=gr):
                o = mb.generer("voiture", graine=gr)
                pneus = _sommets(o, "pneus")
                self.assertAlmostEqual(float(pneus[:, 0].mean()), 0.0, delta=0.02)
                self.assertAlmostEqual(float(pneus[:, 2].mean()), 0.0, delta=0.06)
                self.assertAlmostEqual(float(pneus[:, 1].min()), 0.0, delta=0.005)   # les roues portent
                self.assertGreater(float(_sommets(o, "feux_avant")[:, 2].min()), o.profondeur / 4)
                self.assertLess(float(_sommets(o, "feux_arriere")[:, 2].max()), -o.profondeur / 4)
                # quatre roues : un pneu dans chaque quadrant
                for sx in (-1, 1):
                    for sz in (-1, 1):
                        self.assertTrue(np.any((np.sign(pneus[:, 0]) == sx) & (np.sign(pneus[:, 2]) == sz)))

    def test_cuisine_robinet_au_fond_plaque_sur_le_plan(self):
        o = mb.generer("plan_de_travail", graine=3)
        h_plan = o.surfaces[0].hauteur
        self.assertLess(float(_sommets(o, "robinet")[:, 2].min()), 0.0)
        plaque = _sommets(o, "plaque")
        self.assertAlmostEqual(float(plaque[:, 1].min()), h_plan, delta=0.002)
        evier = _sommets(o, "evier")
        self.assertLess(float(evier[:, 1].min()), h_plan - 0.1)      # une vraie cuve, sous le plan


class Parametres(unittest.TestCase):
    def test_dimensions_donnees_respectees_et_bornees(self):
        for c, cat in voc.CATEGORIES.items():
            L = float(np.mean(cat["largeur"]))
            P = float(np.mean(cat["profondeur"]))
            H = float(np.mean(cat["hauteur"]))
            with self.subTest(categorie=c):
                o = mb.generer(c, largeur=L, profondeur=P, hauteur=H, graine=5)
                self.assertAlmostEqual(o.largeur, L, delta=TOL)
                self.assertAlmostEqual(o.profondeur, P, delta=TOL)
                if c == "plan_de_travail":
                    self.assertAlmostEqual(o.surfaces[0].hauteur, H, delta=TOL)
                else:
                    self.assertAlmostEqual(o.hauteur, H, delta=TOL)
                trop = mb.generer(c, largeur=100.0, graine=5)
                self.assertAlmostEqual(trop.largeur, 1.4 * cat["largeur"][1], delta=TOL)

    def test_une_dimension_donnee_ne_change_pas_les_autres_tirages(self):
        a = mb.generer("commode", graine=11)
        b = mb.generer("commode", largeur=1.0, graine=11)
        self.assertAlmostEqual(a.hauteur, b.hauteur, delta=1e-9)
        self.assertAlmostEqual(a.profondeur, b.profondeur, delta=1e-9)

    def test_allometrie_des_arbres(self):
        for gr in range(6):
            for style, (r0, r1) in mb.RAPPORT_COURONNE.items():
                o = mb.generer("arbre", style=style, graine=gr)
                lo, hi = voc.CATEGORIES["arbre"]["largeur"]
                attendu = np.clip(o.hauteur * np.array([r0, r1]), lo, hi)
                self.assertTrue(attendu[0] - TOL <= o.largeur <= attendu[1] + TOL, (style, gr))

    def test_determinisme(self):
        for c in mb.categories_disponibles():
            with self.subTest(categorie=c):
                a, b = mb.generer(c, graine=42), mb.generer(c, graine=42)
                self.assertEqual([p.nom for p in a.parties], [p.nom for p in b.parties])
                for pa, pb in zip(a.parties, b.parties):
                    self.assertTrue(np.array_equal(pa.maillage.vertices, pb.maillage.vertices))
                autre = mb.generer(c, graine=43)
                self.assertFalse(np.allclose([a.largeur, a.profondeur, a.hauteur],
                                             [autre.largeur, autre.profondeur, autre.hauteur]))

    def test_style_et_materiaux(self):
        o = mb.generer("canape", style="industriel", graine=1)
        self.assertEqual(o.meta["style"], "industriel")
        self.assertEqual(o.meta["materiaux"]["pieds"], "metal_noir")
        self.assertEqual(o.meta["materiaux"]["structure"], "cuir")         # loi de style : cuir
        o = mb.generer("canape", style="industriel", materiaux={"structure": "velours:bleu_nuit"}, graine=1)
        self.assertEqual(o.meta["materiaux"]["structure"], "velours:bleu_nuit")   # le programme prime
        self.assertIn("velours:bleu_nuit", {p.materiau for p in o.parties})
        o = mb.generer("table_a_manger", style="scandinave", graine=2)
        self.assertEqual(o.meta["materiaux"]["plateau"], "bois_clair")
        o = mb.generer("arbre", style="bouleau", graine=2)
        self.assertEqual(o.meta["materiaux"]["tronc"], "bois_peint:blanc_casse")
        for mauvais in ({"structure": "bois_magique"}, {"structure": "inox:rouge"}, {"accoudoir_volant": "tissu"}):
            with self.assertRaises(KeyError):
                mb.generer("canape", materiaux=mauvais)
        with self.assertRaises(KeyError):
            mb.generer("canape", style="baroque_spatial")
        with self.assertRaises(KeyError):
            mb.generer("arbre", style="moderne")
        with self.assertRaises(KeyError):
            mb.generer("licorne")

    def test_les_styles_changent_la_forme(self):
        for c in ("canape", "chaise", "table_a_manger", "commode", "armoire", "lit_double"):
            with self.subTest(categorie=c):
                signatures = set()
                for style in mb.STYLES_MEUBLES:
                    o = mb.generer(c, style=style, largeur=float(np.mean(voc.CATEGORIES[c]["largeur"])),
                                   profondeur=float(np.mean(voc.CATEGORIES[c]["profondeur"])),
                                   hauteur=float(np.mean(voc.CATEGORIES[c]["hauteur"])), graine=0)
                    signatures.add((_triangles(o), tuple(sorted({p.materiau for p in o.parties}))))
                self.assertEqual(len(signatures), len(mb.STYLES_MEUBLES))

    def test_reliures_variees(self):
        o = mb.generer("bibliotheque", graine=4)
        teintes = {p.materiau for p in o.parties if p.nom == "livres"}
        self.assertGreaterEqual(len(teintes), 5)
        o = mb.generer("bibliotheque", graine=4, materiaux={"livres": "papier:bordeaux"})
        self.assertEqual({p.materiau for p in o.parties if p.nom == "livres"}, {"papier:bordeaux"})


if __name__ == "__main__":
    unittest.main()
