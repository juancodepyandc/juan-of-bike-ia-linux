"""Textures procédurales PBR du moteur « monde » : chaque matériau du vocabulaire reçoit des images
répétables, à l'échelle réelle, dont les moyennes respectent la spécification (couleur, rugosité, métal).

Ces tests mesurent les images elles-mêmes ; le jugement visuel passe par les rendus f3d de
`monde.materiaux.demo` (nuancier, salon, rue).
"""
from __future__ import annotations

import json
import struct
import sys
import tempfile
import time
import unittest
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "application" / "python-services"))
from monde import export_gltf, geometrie as g, materiaux, vocabulaire as voc  # noqa: E402
from monde.ir import Noeud, Partie, Scene  # noqa: E402

RES = 128
CLES = list(voc.MATERIAUX)


def _tableau(img) -> np.ndarray:
    return np.asarray(img, dtype=np.float64) / 255.0


class Textures(unittest.TestCase):
    def test_chaque_cle_rend_trois_images_repetables_a_la_resolution(self):
        for cle in CLES:
            with self.subTest(cle=cle):
                tex = materiaux.textures(cle, RES)
                self.assertEqual(set(tex), {"couleur", "orm", "normale"})
                for nom, img in tex.items():
                    self.assertEqual(img.size, (RES, RES), nom)
                    self.assertTrue(materiaux._verifier_repetable(img), nom)
                self.assertEqual(tex["orm"].mode, "RGB")
                self.assertEqual(tex["normale"].mode, "RGB")

    def test_la_couleur_moyenne_est_celle_de_la_spec(self):
        for cle in CLES:
            with self.subTest(cle=cle):
                spec = voc.materiau(cle)
                c = _tableau(materiaux.textures(cle, RES)["couleur"].convert("RGB"))
                zone = materiaux.zone_moyenne(cle, RES)
                # cible bornée à l'albédo physique maximal (un « #ffffff » n'existe pas en matière réelle)
                plafond = float(materiaux._vers_srgb(np.float32(materiaux.ALBEDO_MAX)))
                cible = np.minimum(np.asarray(materiaux.couleur_srgb(spec["couleur"])), plafond)
                self.assertLess(float(np.linalg.norm(c[zone].mean(axis=0) - cible)), 0.03)
                self.assertGreater(zone.mean(), 0.3)            # la zone de référence couvre l'essentiel du motif

    def test_aucune_texture_de_couleur_ne_contient_de_blanc_pur(self):
        for cle in CLES:
            with self.subTest(cle=cle):
                c = np.asarray(materiaux.textures(cle, RES)["couleur"].convert("RGB"))
                self.assertFalse(np.all(c == 255, axis=2).any())

    def test_rugosite_et_metal_respectent_la_spec(self):
        for cle in CLES:
            with self.subTest(cle=cle):
                spec = voc.materiau(cle)
                orm = _tableau(materiaux.textures(cle, RES)["orm"])
                zone = materiaux.zone_moyenne(cle, RES)
                self.assertAlmostEqual(float(orm[..., 1][zone].mean()), spec["rugosite"], delta=0.04)
                self.assertAlmostEqual(float(orm[..., 2].mean()), spec["metal"], delta=0.01)
                self.assertGreater(float(orm[..., 0].mean()), 0.6)   # occlusion : cavités seulement

    def test_la_carte_de_normales_est_unitaire_et_centree(self):
        for cle in CLES:
            with self.subTest(cle=cle):
                n = _tableau(materiaux.textures(cle, RES)["normale"]) * 2.0 - 1.0
                longueur = np.linalg.norm(n, axis=-1)
                self.assertLess(float(np.abs(longueur - 1.0).max()), 0.02)
                moyenne = (n.reshape(-1, 3).mean(axis=0) + 1.0) * 127.5
                self.assertLess(abs(moyenne[0] - 127.5), 4.0)
                self.assertLess(abs(moyenne[1] - 127.5), 4.0)
                self.assertGreater(moyenne[2], 220.0)
                self.assertTrue(np.all(n[..., 2] > 0.0))             # aucune normale tournée vers l'intérieur

    def test_une_variante_coloree_change_la_couleur_mais_pas_le_motif(self):
        coloriables = [c for c in CLES if voc.MATERIAUX[c]["coloriable"]]
        for cle in coloriables:
            with self.subTest(cle=cle):
                base = _tableau(materiaux.textures(cle, RES)["couleur"].convert("RGB"))
                teinte = _tableau(materiaux.textures(f"{cle}:bleu_canard", RES)["couleur"].convert("RGB"))
                cible = np.asarray(materiaux.couleur_srgb(voc.PALETTE["bleu_canard"]))
                zone = materiaux.zone_moyenne(f"{cle}:bleu_canard", RES)
                self.assertLess(float(np.linalg.norm(teinte[zone].mean(axis=0) - cible)), 0.03)
                self.assertGreater(float(np.abs(base - teinte).mean()), 0.05)
                n1 = np.asarray(materiaux.textures(cle, RES)["normale"])
                n2 = np.asarray(materiaux.textures(f"{cle}:bleu_canard", RES)["normale"])
                self.assertTrue(np.array_equal(n1, n2))              # même relief : seul le pigment change

    def test_deterministe_et_rapide(self):
        a = np.asarray(materiaux.textures("parquet_chene", RES)["couleur"])
        materiaux._calculer.cache_clear()
        b = np.asarray(materiaux.textures("parquet_chene", RES)["couleur"])
        self.assertTrue(np.array_equal(a, b))
        materiaux._calculer.cache_clear()
        lent = []
        for cle in CLES:
            debut = time.perf_counter()
            materiaux.textures(cle, 512)
            duree = time.perf_counter() - debut
            if duree > 0.6:
                lent.append((cle, round(duree, 2)))
        self.assertEqual(lent, [])

    def test_le_motif_est_a_l_echelle_reelle(self):
        # parquet : lames de ~15 cm dans un carreau de 1,2 m → ~8 rangées de joints horizontaux
        T = voc.MATERIAUX["parquet_chene"]["taille_m"]
        c = _tableau(materiaux.textures("parquet_chene", 512)["couleur"].convert("L"))
        profil = c.mean(axis=1)
        joints = profil < profil.mean() - 2.5 * profil.std() * 0.5
        transitions = int(np.sum(joints & ~np.roll(joints, 1)))
        self.assertAlmostEqual(transitions, round(T / 0.15), delta=1)
        # brique : ~14 assises par mètre (6,5 cm + 1 cm de joint, nombre pair pour le décalage)
        c = _tableau(materiaux.textures("brique", 512)["couleur"].convert("L"))
        profil = c.mean(axis=1)
        clair = profil > profil.mean() + 0.5 * profil.std()
        assises = int(np.sum(clair & ~np.roll(clair, 1)))
        self.assertEqual(assises, 14)


class Translucides(unittest.TestCase):
    def test_couleur_rgba_avec_le_bon_alpha(self):
        for cle, spec in voc.MATERIAUX.items():
            if spec.get("alpha", 1.0) >= 0.999:
                continue
            with self.subTest(cle=cle):
                img = materiaux.textures(cle, RES)["couleur"]
                self.assertEqual(img.mode, "RGBA")
                self.assertAlmostEqual(float(_tableau(img)[..., 3].mean()), spec["alpha"], delta=0.01)
                mat = materiaux.materiau_trimesh(cle, RES)
                self.assertEqual(mat.baseColorTexture.mode, "RGBA")
                self.assertEqual(mat.alphaMode, "BLEND")


class Export(unittest.TestCase):
    def test_une_scene_exportee_embarque_les_trois_textures(self):
        parties = [Partie(g.plaque(g.rectangle_xz(0, 0, 3, 3), 0.05), "parquet_chene", "sol"),
                   Partie(g.boite(3.0, 3.0, 0.2, x=1.5), "facade_pierre:creme", "facade"),
                   Partie(g.sphere(0.3, y=0.3, x=1.5, z=1.5), "verre", "boule")]
        with tempfile.TemporaryDirectory() as tmp:
            chemin = Path(tmp) / "scene.glb"
            export_gltf.exporter(Scene(Noeud("essai", parties=parties)), chemin, resolution=64)
            donnees = chemin.read_bytes()
        longueur = struct.unpack_from("<I", donnees, 12)[0]
        gltf = json.loads(donnees[20:20 + longueur])
        self.assertGreaterEqual(len(gltf["images"]), 9)
        for mat in gltf["materials"]:
            with self.subTest(materiau=mat["name"]):
                pbr = mat["pbrMetallicRoughness"]
                self.assertIn("baseColorTexture", pbr)
                self.assertIn("metallicRoughnessTexture", pbr)
                self.assertIn("normalTexture", mat)
                self.assertEqual(pbr.get("metallicFactor", 1.0), 1.0)   # la texture porte la valeur
        verre = next(m for m in gltf["materials"] if m["name"] == "verre")
        self.assertEqual(verre["alphaMode"], "BLEND")


class Planche(unittest.TestCase):
    def test_la_planche_montre_chaque_cle(self):
        img = materiaux.planche(CLES[:10], 64)
        self.assertEqual(img.width, 8 * 64)
        self.assertGreaterEqual(img.height, 2 * 64)


if __name__ == "__main__":
    unittest.main()
