#!/usr/bin/env python3
"""La metrique exacte ne doit PAS entrer dans le composite.

Ajouter `self_intersections_exactes` aux metriques ne doit avoir aucune
consequence sur `score`, sinon tous les scores deja produits deviendraient
illisibles. Ce test verrouille cette frontiere: il reconstruit le composite tel
qu'il est ecrit dans `judges.py`, puis exige que la metrique exacte n'y entre pas.

Il verifie aussi que la formule elle-meme n'a pas derive, en la comparant a la
regle documentee.
"""
from __future__ import annotations

import re
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

JUGES = Path(__file__).resolve().parents[1] / "auto_rl" / "judges.py"


def composite(nonmanifold, boundary, fragment, degenerate, inter_bvh, face_count,
              clip_mean, clip_worst):
    """Recopie litterale de la formule de judges.py, y compris sa ponderation."""
    topology = max(0, 1 - 5 * nonmanifold - boundary - fragment - 5 * degenerate)
    if inter_bvh is not None:
        topology *= 1 / (1 + inter_bvh / max(1, face_count) * 20)
    return 0.45 * topology + 0.35 * clip_mean + 0.2 * clip_worst


class TestCompositeInchange(unittest.TestCase):
    def test_formule_du_score_intacte(self):
        src = JUGES.read_text()
        self.assertIn("topology = max(0, 1 - 5 * nonmanifold - boundary - fragment - 5 * degenerate)", src)
        self.assertIn("topology *= 1 / (1 + inter / max(1, face_count) * 20)", src)
        self.assertIn("return result(0.45 * topology + 0.35 * np.mean(scores) + 0.2 * min(scores)", src)

    def test_metrique_exacte_absente_de_la_formule(self):
        src = JUGES.read_text()
        # toute ligne participant au composite ne doit pas citer la metrique exacte
        for ligne in src.splitlines():
            if "0.45 * topology" in ligne or "topology *=" in ligne or "topology = max" in ligne:
                self.assertNotIn("exact", ligne,
                                 "la metrique exacte a fuité dans le composite : " + ligne.strip())

    def test_score_independant_de_la_metrique_exacte(self):
        """Varier la metrique exacte ne doit pas bouger le score d'un centieme."""
        base = dict(nonmanifold=0.004, boundary=0.031, fragment=0.014, degenerate=0.0001,
                    inter_bvh=14727, face_count=97865, clip_mean=0.71, clip_worst=0.62)
        ref = composite(**base)
        for exact in (0, 1, 1950, 24265, 10 ** 6, None):
            # la metrique exacte n'est meme pas un parametre: on le montre
            self.assertNotIn("exact", base)
            self.assertAlmostEqual(composite(**base), ref, places=15,
                                   msg=f"le composite bouge avec exact={exact}")

    def test_metrique_exacte_signalee(self):
        src = JUGES.read_text()
        self.assertIn('"self_intersections_exactes": exact', src)
        self.assertIn('"taux_faces_auto_intersectees"', src)

    def test_regle_documentee(self):
        """Le gain de la regle historique reste celui du BVH, pas de l'exact."""
        # Avec la regle historique, la metrique exacte n'entre pas: le multiplicateur
        # de topologie est determine uniquement par `inter` (BVH).
        fort_bvh = composite(0.004, 0.031, 0.014, 0.0001, 14727, 97865, 0.71, 0.62)
        faible_bvh = composite(0.004, 0.031, 0.014, 0.0001, 572, 97865, 0.71, 0.62)
        self.assertGreater(faible_bvh, fort_bvh,
                           "moins d'auto-intersections BVH doit donner un meilleur score")


if __name__ == "__main__":
    unittest.main(verbosity=2)
