"""Le style DEMANDÉ fixe le médium, à son meilleur (15/11/2026) : réaliste → photographie haut de gamme ;
animé → animation haut de gamme ; un personnage de dessin animé « en version réaliste » → réaliste.
Avant : « Zig et Sharko en version réaliste » prenait le style « Cartoon 2D Xilam » de son sujet, et le moteur
de scènes rendait tout en textures photographiques, même pour une demande animée."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "application" / "python-services"))
from monde import materiaux  # noqa: E402
from universal_style_engine import aligner_sur_cible, classify_style  # noqa: E402


class StyleDemande(unittest.TestCase):
    def test_la_demande_explicite_l_emporte_sur_le_sujet(self):
        realiste = aligner_sur_cible(classify_style("Zig et Sharko en version réaliste"), "photo")
        self.assertEqual(realiste["style_id"], "realistic_pbr")
        self.assertEqual(realiste["impose_par_la_demande"]["cible"], "photo")
        anime_3d = aligner_sur_cible(classify_style("Zig et Sharko en animation 3D"), "cgi_3d")
        self.assertNotIn(anime_3d["style_id"], ("cartoon_2d_flat", "realistic_pbr"))

    def test_sans_style_demande_le_profil_du_sujet_reste(self):
        profil = classify_style("Zig et Sharko")
        self.assertIs(aligner_sur_cible(profil, None), profil)
        conforme = classify_style("un chat réaliste")
        self.assertIs(aligner_sur_cible(conforme, "photo"), conforme)       # déjà conforme : rien ne change

    def test_le_rendu_des_scenes_suit_le_medium(self):
        self.assertEqual(materiaux.rendu_depuis_cible("photo"), "realiste")
        self.assertEqual(materiaux.rendu_depuis_cible("cgi_3d"), "anime")
        self.assertEqual(materiaux.rendu_depuis_cible("cel_2d"), "toon")
        self.assertEqual(materiaux.rendu_depuis_cible(None), "realiste")


class MateriauxStylises(unittest.TestCase):
    def grain(self, image):
        a = np.asarray(image.convert("L"), dtype=np.float32)
        return float(np.abs(np.diff(a, axis=0)).mean() + np.abs(np.diff(a, axis=1)).mean())

    def saturation(self, image):
        a = np.asarray(image.convert("RGB"), dtype=np.float32)
        return float((a.max(axis=2) - a.min(axis=2)).mean())

    def test_anime_sans_grain_et_plus_sature_toon_en_aplats_realiste_intact(self):
        brut = materiaux.textures("parquet_chene", 256)
        anime = materiaux.styliser(brut, "anime")
        toon = materiaux.styliser(brut, "toon")
        self.assertIs(materiaux.styliser(brut, "realiste"), brut)
        self.assertLess(self.grain(anime["couleur"]), 0.7 * self.grain(brut["couleur"]))
        self.assertGreater(self.saturation(anime["couleur"]), self.saturation(brut["couleur"]))
        couleurs = np.unique(np.asarray(toon["couleur"].convert("RGB")).reshape(-1, 3), axis=0)
        self.assertLessEqual(len(couleurs), 6)                                   # aplats
        n = np.asarray(anime["normale"], dtype=np.float32) / 127.5 - 1.0
        n0 = np.asarray(brut["normale"], dtype=np.float32) / 127.5 - 1.0
        self.assertLess(np.abs(n[..., :2]).mean(), np.abs(n0[..., :2]).mean())  # relief adouci

    def test_un_rendu_inconnu_est_une_erreur_et_le_cache_distingue_les_rendus(self):
        with self.assertRaises(KeyError):
            materiaux.materiau_trimesh("parquet_chene", 64, "aquarelle")
        self.assertIsNot(materiaux.materiau_trimesh("parquet_chene", 64, "anime"),
                         materiaux.materiau_trimesh("parquet_chene", 64, "realiste"))


if __name__ == "__main__":
    unittest.main()
