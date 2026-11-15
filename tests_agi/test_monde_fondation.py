"""Fondation du moteur de scènes « monde » : vocabulaires cohérents, primitives, conventions, export glTF.

Le moteur remplace la composition d'objets isolés posés en ligne (cartographie du 15/11/2026 : un
« intérieur de maison complet » donnait trois pièces-objets sans mur commun ni meuble). Ici on vérifie
le socle commun à toutes ses briques ; aucun modèle, aucun rendu.
"""
from __future__ import annotations

import json
import math
import struct
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "application" / "python-services"))
from monde import export_gltf, geometrie as g, materiaux, vocabulaire as voc  # noqa: E402
from monde.ir import Instance, Noeud, Objet, Partie, Pose, Scene  # noqa: E402


def lire_glb(chemin: Path) -> tuple[dict, bytes]:
    donnees = chemin.read_bytes()
    longueur_json = struct.unpack_from("<I", donnees, 12)[0]
    gltf = json.loads(donnees[20:20 + longueur_json])
    binaire = donnees[20 + longueur_json + 8:]
    return gltf, binaire


class Vocabulaires(unittest.TestCase):
    def test_chaque_materiau_par_defaut_des_objets_existe(self):
        for cle, cat in voc.CATEGORIES.items():
            for emplacement, mat in cat["materiaux"].items():
                with self.subTest(objet=cle, emplacement=emplacement):
                    voc.materiau(mat)
            for axe in ("largeur", "profondeur", "hauteur"):
                lo, hi = cat[axe]
                self.assertTrue(0 < lo <= hi, (cle, axe))

    def test_les_pieces_ne_citent_que_des_objets_et_relations_connus(self):
        for cle, piece in voc.FONCTIONS_PIECES.items():
            voc.materiau(piece["sol"])
            voc.materiau(piece["murs"])
            for categorie, nombre, relations in piece["meubles_typiques"]:
                self.assertIn(categorie, voc.CATEGORIES, cle)
                self.assertGreaterEqual(nombre, 1)
                for relation, cible in relations:
                    self.assertIn(relation, voc.RELATIONS, (cle, categorie))
                    self.assertEqual(cible is not None, voc.RELATIONS[relation]["cible"], (cle, categorie, relation))
                    if cible is not None:
                        self.assertIn(cible, voc.CATEGORIES)

    def test_styles_et_biomes_ne_citent_que_des_cles_connues(self):
        for style in voc.STYLES_ARCHI.values():
            for facade in style["facades"]:
                voc.materiau(facade)
            voc.materiau(style["toiture"])
            self.assertTrue(set(style["toits"]) <= set(voc.TOITS))
            voc.materiau(style["interieur"]["sol"])
            voc.materiau(style["interieur"]["murs"])
        for biome in voc.BIOMES.values():
            voc.materiau(biome["sol"])
            for categorie, style, densite in biome["vegetation"]:
                self.assertIn(categorie, voc.CATEGORIES)
                self.assertTrue(style is None or style in voc.CATEGORIES[categorie]["styles"])

    def test_une_cle_inconnue_ou_une_couleur_hors_palette_est_une_erreur(self):
        with self.assertRaises(KeyError):
            voc.materiau("bois_magique")
        with self.assertRaises(KeyError):
            voc.materiau("tissu:fuchsia_galactique")
        with self.assertRaises(KeyError):
            voc.materiau("inox:rouge")              # l'inox n'est pas coloriable
        self.assertEqual(voc.materiau("tissu:#A1B2C3")["couleur"], "#a1b2c3")


class Primitives(unittest.TestCase):
    def test_une_boite_a_des_uv_en_metres_et_repose_sur_le_sol(self):
        m = g.boite(2.0, 1.0, 0.5)
        self.assertAlmostEqual(float(m.bounds[0][1]), 0.0)
        self.assertAlmostEqual(float(m.bounds[1][1]), 1.0)
        uv = np.asarray(m.visual.uv)
        self.assertAlmostEqual(float(np.ptp(uv[:, 0])), 2.0, places=5)   # la face de 2 m couvre 2 unités
        self.assertTrue(np.allclose(np.linalg.norm(m.vertex_normals, axis=1), 1.0))

    def test_le_cylindre_est_vertical_et_lisse_sur_les_cotes(self):
        m = g.cylindre(0.1, 0.8, x=1.0, y=0.2)
        self.assertAlmostEqual(float(m.bounds[0][1]), 0.2)
        self.assertAlmostEqual(float(m.bounds[1][1]), 1.0)
        cote = np.abs(m.vertex_normals[:, 1]) < 0.1
        self.assertTrue(cote.any())
        # normales lissées : sur le flanc, elles sont radiales (pas une seule normale par facette)
        radiales = m.vertex_normals[cote][:, [0, 2]]
        self.assertGreater(len(np.unique(np.round(radiales, 3), axis=0)), 12)

    def test_une_extrusion_suit_le_plan_x_z(self):
        m = g.extrusion([(0, 0), (3, 0), (3, 2), (0, 2)], 2.5)
        (x0, y0, z0), (x1, y1, z1) = m.bounds
        self.assertEqual([round(v, 6) for v in (x0, y0, z0, x1, y1, z1)], [0, 0, 0, 3, 2.5, 2])
        # orientation correcte après la réflexion (x, y_plan, h) → (x, h, z) : normales vers l'extérieur
        centres = m.triangles_center
        self.assertTrue(np.all(m.face_normals[centres[:, 1] > 2.499][:, 1] > 0.99))
        self.assertTrue(np.all(m.face_normals[centres[:, 1] < 0.001][:, 1] < -0.99))
        cote_x = m.face_normals[centres[:, 0] > 2.999]
        self.assertTrue(len(cote_x) and np.all(cote_x[:, 0] > 0.99))

    def test_la_boite_arrondie_et_la_revolution_ont_les_bonnes_dimensions(self):
        m = g.boite_arrondie(1.0, 0.4, 0.6, 0.08)
        self.assertTrue(np.allclose(m.extents, [1.0, 0.4, 0.6], atol=1e-3))
        r = g.revolution([(0.0, 0.0), (0.2, 0.0), (0.1, 0.5), (0.0, 0.5)])
        self.assertAlmostEqual(float(r.bounds[1][1]), 0.5, places=5)
        self.assertAlmostEqual(float(r.extents[0]), 0.4, places=2)


class Conventions(unittest.TestCase):
    def test_la_face_suit_le_lacet(self):
        self.assertTrue(np.allclose(Pose(lacet=0.0).face(), (0.0, 1.0)))
        self.assertTrue(np.allclose(Pose(lacet=math.pi / 2).face(), (1.0, 0.0), atol=1e-12))
        p = Pose(x=1.0, z=2.0, lacet=math.pi / 2)
        self.assertTrue(np.allclose(p.vers_monde(0.0, 1.0), (2.0, 2.0)))
        point = p.matrice() @ np.array([0.0, 0.0, 1.0, 1.0])
        self.assertTrue(np.allclose(point[[0, 2]], (2.0, 2.0)))

    def test_l_emprise_et_le_degagement_tournent_avec_l_objet(self):
        o = Objet("lit", "lit_double", [], largeur=1.6, profondeur=2.0, hauteur=1.0, degagement=0.6)
        emprise = o.emprise(Pose(lacet=math.pi / 2))
        minx, minz, maxx, maxz = emprise.bounds
        self.assertAlmostEqual(maxx - minx, 2.0)                  # la longueur est maintenant en x
        devant = o.zone_degagement(Pose(lacet=math.pi / 2))
        self.assertGreater(devant.bounds[0], 0.99)                # devant la face, donc côté +x


class Export(unittest.TestCase):
    def test_hierarchie_materiaux_uv_et_translucidite(self):
        sol = Partie(g.plaque(g.rectangle_xz(0, 0, 4, 3), 0.05), "parquet_chene", "sol")
        mur = Partie(g.boite(4.0, 2.5, 0.1, x=2.0, z=0.0), "platre_peint:vert_sauge", "mur")
        vitre = Partie(g.boite(1.0, 1.2, 0.01, x=2.0, y=0.9, z=0.0), "verre", "vitre")
        canape = Objet("canape", "canape", [Partie(g.boite_arrondie(2.0, 0.45, 0.9, 0.06), "tissu:gris", "assise")],
                       largeur=2.0, profondeur=0.9, hauteur=0.8)
        piece = Noeud("salon", parties=[sol, mur, vitre], instances=[Instance(canape, Pose(2.0, 1.5, math.pi), "canape")])
        scene = Scene(Noeud("maison", enfants=[piece]), extras={"programme": {"type_scene": "interieur"}})
        with tempfile.TemporaryDirectory() as tmp:
            rapport = export_gltf.exporter(scene, Path(tmp) / "scene.glb", resolution=64)
            gltf, _ = lire_glb(Path(tmp) / "scene.glb")
        noms = {n.get("name") for n in gltf["nodes"]}
        self.assertTrue({"maison", "salon", "canape"} <= noms, noms)
        self.assertEqual(sorted(rapport["materiaux"]), sorted(["parquet_chene", "platre_peint:vert_sauge", "verre", "tissu:gris"]))
        self.assertEqual(len(gltf["materials"]), 4)
        for maillage in gltf["meshes"]:
            for primitive in maillage["primitives"]:
                self.assertIn("NORMAL", primitive["attributes"])
                self.assertIn("TEXCOORD_0", primitive["attributes"])
        verre = next(m for m in gltf["materials"] if m["name"] == "verre")
        self.assertEqual(verre["alphaMode"], "BLEND")
        self.assertIn("baseColorTexture", verre["pbrMetallicRoughness"])   # l'alpha lu par f3d
        canape_noeud = next(n for n in gltf["nodes"] if n.get("name") == "canape")
        self.assertIn("rotation", canape_noeud)                     # la pose est portée par le nœud
        self.assertIn("translation", canape_noeud)
        # les extras d'un objet (catégorie, pivot d'une porte…) arrivent dans le glTF (three.js : userData)
        self.assertEqual(canape_noeud.get("extras", {}).get("categorie"), "canape")

    def test_une_cle_que_three_js_interprete_n_est_jamais_ecrite_telle_quelle(self):
        # three.js r183 lit `userData.pivot` comme un tableau : « charniere » y donnait une position NaN
        porte = Objet("porte", "porte", [Partie(g.boite(0.9, 2.0, 0.04), "bois_peint", "vantail")], 0.9, 0.04, 2.0)
        scene = Scene(Noeud("logement", instances=[Instance(porte, Pose(1.0, 0.0, 0.0), "porte_a_b",
                                                            meta={"pivot": "charniere", "angle_ouverture_rad": 1.57})]))
        with tempfile.TemporaryDirectory() as tmp:
            export_gltf.exporter(scene, Path(tmp) / "p.glb", resolution=32)
            gltf, _ = lire_glb(Path(tmp) / "p.glb")
        extras = next(n for n in gltf["nodes"] if n.get("name") == "porte_a_b")["extras"]
        self.assertNotIn("pivot", extras)
        self.assertEqual(extras["aurora_pivot"], "charniere")
        self.assertAlmostEqual(extras["angle_ouverture_rad"], 1.57)


if __name__ == "__main__":
    unittest.main()
