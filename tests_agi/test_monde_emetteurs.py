"""Émissions animées (gaz, liquides) : lois physiques mesurées, et animation glTF réellement écrite.

« Un coup de parfum » (15/11/2026) : la brume part du bec, file ~0,4 m freinée par l'air puis s'étale ; une
fumée monte ; un jet d'eau suit une parabole ; des gouttes tombent ; une flamme monte en rétrécissant."""
from __future__ import annotations

import json
import struct
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "application" / "python-services"))
from monde import animation_gltf, emetteurs, export_gltf, geometrie as g  # noqa: E402
from monde.ir import Noeud, Partie, Scene  # noqa: E402


def lire(chemin: Path) -> dict:
    d = chemin.read_bytes()
    n = struct.unpack_from("<I", d, 12)[0]
    return json.loads(d[20:20 + n])


class Lois(unittest.TestCase):
    def mesures(self, type_, **options):
        return emetteurs.construire(emetteurs.Emission(type_, origine=(0.0, 1.0, 0.0), graine=1, **options))

    def test_les_ordres_de_grandeur_physiques(self):
        _, _, brume = self.mesures("brume", direction=(0.0, 0.0, 1.0))
        self.assertTrue(0.25 < brume["portee_max_m"] < 0.7, brume)          # un vaporisateur porte ~0,4 m
        _, _, jet = self.mesures("jet_liquide")
        self.assertTrue(0.75 < jet["hauteur_max_m"] < 1.3, jet)             # v²/2g ≈ 1 m pour 4,4 m/s
        _, _, fumee = self.mesures("fumee")
        self.assertGreater(fumee["hauteur_max_m"], 2.0)                     # la fumée monte
        _, pistes, _ = self.mesures("gouttes", direction=(0.0, -1.0, 0.0))
        ys = [p[1] for piste in pistes.values() for p in piste["translation"]]
        self.assertLess(min(ys), 0.0)                                       # les gouttes tombent sous la source

    def test_une_flamme_retrecit_et_une_brume_s_etale(self):
        _, pistes, _ = self.mesures("flamme")
        piste = next(iter(pistes.values()))
        echelles = np.array(piste["scale"])[:, 0]
        vivantes = echelles[echelles > 1e-3]
        self.assertGreater(vivantes[0], vivantes[-1])
        _, pistes, _ = self.mesures("brume", direction=(0.0, 0.0, 1.0))
        piste = next(iter(pistes.values()))
        e = np.array(piste["scale"])[:, 0]
        vivantes = e[e > 1e-3]
        self.assertLess(vivantes[0], vivantes[-1])

    def test_un_type_inconnu_est_une_erreur(self):
        with self.assertRaises(KeyError):
            emetteurs.construire(emetteurs.Emission("arc_en_ciel", origine=(0, 0, 0)))


class Injection(unittest.TestCase):
    def test_l_animation_est_ecrite_dans_le_glb_et_rejouable(self):
        noeud, pistes, _ = emetteurs.construire(emetteurs.Emission("vapeur", origine=(0.0, 0.1, 0.0), nom="tasse"))
        scene = Scene(Noeud("table", parties=[Partie(g.cylindre(0.04, 0.09), "ceramique", "tasse")], enfants=[noeud]))
        with tempfile.TemporaryDirectory() as tmp:
            glb = Path(tmp) / "t.glb"
            export_gltf.exporter(scene, glb, resolution=32)
            res = animation_gltf.injecter(glb, {**pistes, "absent": next(iter(pistes.values()))})
            gltf = lire(glb)
        self.assertEqual(res["absents"], ["absent"])                        # signalé, jamais ignoré
        self.assertEqual(len(gltf["animations"]), 1)
        anim = gltf["animations"][0]
        self.assertEqual(len(anim["channels"]), 2 * len(pistes))
        temps = gltf["accessors"][anim["samplers"][0]["input"]]
        self.assertAlmostEqual(temps["max"][0], emetteurs.LOIS["vapeur"].duree_boucle, places=4)
        self.assertEqual({c["target"]["path"] for c in anim["channels"]}, {"translation", "scale"})
        self.assertEqual(gltf["buffers"][0]["byteLength"] % 4, 0)


if __name__ == "__main__":
    unittest.main()


class Similitude(unittest.TestCase):
    def test_un_jet_deux_fois_plus_grand_monte_deux_fois_plus_haut(self):
        # Froude : vitesses en racine de la taille, hauteur atteinte proportionnelle à la taille
        _, _, petit = emetteurs.construire(emetteurs.Emission("jet_liquide", origine=(0, 0, 0), echelle=1.0, graine=2))
        _, _, grand = emetteurs.construire(emetteurs.Emission("jet_liquide", origine=(0, 0, 0), echelle=2.0, graine=2))
        self.assertAlmostEqual(grand["hauteur_max_m"] / petit["hauteur_max_m"], 2.0, delta=0.15)
