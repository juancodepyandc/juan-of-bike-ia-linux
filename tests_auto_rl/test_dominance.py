#!/usr/bin/env python3
"""Non-régression de la sélection par dominance.

Le cas central est un candidat qui gagne sur le score composite mais perd sur la
pire vue CLIP: avant, il devenait le gagnant. Ici il ne doit jamais le devenir,
parce que le gradient doit dire « améliore tout », pas « échange CLIP contre
topologie ».
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from auto_rl.dominance import TRACKED_3D, comparable, dominates, pareto_front, select  # noqa: E402


def s(score, valid=True, **metrics):
    base = {"clip_mean": 0.70, "clip_worst_view": 0.60, "self_intersections_exactes": 1000,
            "taux_faces_auto_intersectees": 0.01, "nonmanifold_edge_fraction": 0.004,
            "boundary_edge_fraction": 0.03, "fragment_area_fraction": 0.01,
            "degenerate_face_fraction": 0.0, "self_intersections": 500}
    base.update(metrics)
    return {"judge": {"score": score, "valid": valid, "metrics": base}}


class TestDominance(unittest.TestCase):
    def test_domine_toutes_metriques(self):
        bon = s(0.80, clip_mean=0.75, clip_worst_view=0.65, self_intersections_exactes=500)
        mau = s(0.70)
        self.assertIs(dominates(bon["judge"]["metrics"], mau["judge"]["metrics"], TRACKED_3D), True)
        self.assertIs(dominates(mau["judge"]["metrics"], bon["judge"]["metrics"], TRACKED_3D), False)

    def test_egalite_pareille_ne_domine_pas(self):
        a = s(0.70)
        self.assertIs(dominates(a["judge"]["metrics"], a["judge"]["metrics"], TRACKED_3D), False,
                      "des métriques identiques ne doivent PAS compter comme domination")

    def test_absence_de_donnees_nest_pas_une_egalite(self):
        a = {"clip_mean": 0.7}
        b = {}
        self.assertIs(dominates(a, b, TRACKED_3D), None,
                      "sans métrique commune, la comparaison est impossible, pas une égalité")

    def test_front_exclut_le_dominne(self):
        faible = s(0.70)
        fort = s(0.80, clip_mean=0.80, clip_worst_view=0.70, self_intersections_exactes=100)
        front, used = pareto_front([faible, fort], TRACKED_3D)
        self.assertEqual(len(front), 1)
        self.assertIs(front[0], fort)
        self.assertIn("clip_worst_view", used)

    def test_winner_mieux_score_mais_pire_pire_vue_refuse(self):
        """Le cas central: meilleur score, mais régression de la pire vue CLIP.

        Avec un témoin neutre plus faible partout, le piège score-haut ne
        domine rien. Il peut gagner la paire par défaut, mais seulement parce
        qu'aucune dominance stricte n'existe, et la paire doit porter
        strict=False pour que l'audit compte cet arbitrage.
        """
        neutre = s(0.70)
        piege = s(0.95, clip_mean=0.99, clip_worst_view=0.10)
        w, l, diag = select([neutre, piege], TRACKED_3D)
        self.assertIsNotNone(w)
        self.assertFalse(diag["strict"], "le piege ne domine pas: la paire n'est pas non-regressive")

    def test_pire_vue_clip_bloque_la_dominance_stricte(self):
        """Si un témoin propre existe, le piège ne peut pas produire une paire stricte."""
        piege = s(0.95, clip_mean=0.99, clip_worst_view=0.10)
        propre = s(0.72, clip_mean=0.73, clip_worst_view=0.61, self_intersections_exactes=800)
        neutre = s(0.70)
        w, l, diag = select([neutre, propre, piege], TRACKED_3D)
        self.assertIsNot(w, piege, "le piege ne doit pas gagner quand une dominance stricte existe")
        self.assertTrue(diag["strict"], "avec un candidat propre dominant, la paire doit etre stricte")

    def test_plus_dintersections_bloque_la_dominance_stricte(self):
        """Même garantie via self_intersections_exactes: l'intersection prime."""
        neutre = s(0.70)
        propre = s(0.72, clip_mean=0.71, clip_worst_view=0.61, self_intersections_exactes=800)
        piege = s(0.95, clip_mean=0.95, clip_worst_view=0.90,
                  self_intersections_exactes=90000)
        w, l, diag = select([neutre, propre, piege], TRACKED_3D)
        self.assertIsNot(w, piege, "90k intersections ne doivent pas gagner face a un candidat propre")
        self.assertTrue(diag["strict"], "le candidat propre domine strictement le piege sur les intersections")

    def test_pire_vue_seule_tranche_sans_gain_clip_reel(self):
        """Un piège qui ne perd QUE la pire vue, sans gain CLIP réel, ne gagne pas."""
        neutre = s(0.70)
        piege = s(0.75, clip_mean=0.70, clip_worst_view=0.40)  # score +, pire vue -
        w, l, diag = select([neutre, piege], TRACKED_3D)
        self.assertIs(w, neutre, "sans gain CLIP reel, la pire vue tranche: neutre gagne")
        self.assertTrue(diag["strict"])

    def test_winner_valide_dominateur_accepte(self):
        neutre = s(0.70)
        bon = s(0.75, clip_mean=0.72, clip_worst_view=0.62, self_intersections_exactes=800)
        w, l, diag = select([neutre, bon], TRACKED_3D)
        self.assertIs(w, bon)
        self.assertIs(l, neutre)
        self.assertEqual(diag["raison"], "dominance")

    def test_invalide_jamais_gagnant(self):
        invalide = s(0.999, valid=False, clip_mean=0.99)
        neutre = s(0.70)
        bon = s(0.72, clip_mean=0.71, clip_worst_view=0.61)
        w, l, _ = select([invalide, neutre, bon], TRACKED_3D)
        self.assertIsNot(w, invalide, "un échantillon invalide ne peut pas être le gagnant")

    def test_conflit_de_metriques_choisit_le_moins_regressif(self):
        """Vrai arbitrage: X gagne en moyenne CLIP mais perd la pire vue.

        Aucune dominance stricte n'existe, donc la paire est conservee pour ne
        pas perdre la supervision, mais elle est marquee non stricte: l'audit
        doit pouvoir compter ces arbitrages.
        """
        x = s(0.90, clip_mean=0.95, clip_worst_view=0.10)
        y = s(0.70, clip_mean=0.60, clip_worst_view=0.80)
        w, l, diag = select([x, y], TRACKED_3D)
        self.assertIsNotNone(w, "un arbitrage ne doit pas priver la tache de preference")
        self.assertFalse(diag["strict"], "l'absence de dominance doit etre signalee")
        self.assertEqual(diag["raison"], "arbitrage_non_regressif_minimal")

    def test_dominance_stricte_prime_sur_le_score(self):
        """Un candidat strictement dominant est choisi meme avec un score plus bas."""
        dominant_moins_score = s(0.75, clip_mean=0.72, clip_worst_view=0.62,
                                 self_intersections_exactes=800)
        neutre = s(0.80)
        w, l, diag = select([dominant_moins_score, neutre], TRACKED_3D)
        self.assertIs(w, dominant_moins_score,
                      "le candidat qui ne regresse nulle part prime sur le score")
        self.assertTrue(diag["strict"])

    def test_score_marge_sappliquee_aux_arbitrages_seulement(self):
        """Le seuil de score ne vise que les paires non strictement dominantes.

        Deux candidats mutuellement incomparables et quasi a egalite de score
        feraient une preference trop bruyante: elle est refusee.
        """
        x = s(0.70, clip_mean=0.80, clip_worst_view=0.10)
        y = s(0.700001, clip_mean=0.60, clip_worst_view=0.80)
        w, l, diag = select([x, y], TRACKED_3D)
        self.assertIsNone(w, "un arbitrage a score quasi egal est trop bruyant")
        self.assertIn("écart de score", diag["raison"])

    def test_dominance_stricte_acceptee_meme_si_score_en_baisse(self):
        """Le cas recherché: toutes les métriques montent, le score composite baisse.

        Le composite ignore la métrique exacte, donc il peut baisser pendant
        qu'aucune métrique suivie ne régresse. Refuser ici réintroduirait
        exactement la régression qu'on cherche à empêcher.
        """
        propre = s(0.60, clip_mean=0.72, clip_worst_view=0.62,
                   self_intersections_exactes=100)
        ancien = s(0.90, clip_mean=0.70, clip_worst_view=0.60,
                   self_intersections_exactes=90000)
        w, l, diag = select([propre, ancien], TRACKED_3D)
        self.assertIs(w, propre, "la non-regression prime sur le score composite")
        self.assertIs(l, ancien)
        self.assertLess(diag["ecart_score"], 0.0,
                        "cet example DOIT avoir un ecart de score negatif, c'est le point")

    def test_metriques_manquantes_exclues_du_front(self):
        a = s(0.70)
        b = s(0.72, clip_worst_view=None)  # métrique absente: non comparable
        front, used = pareto_front([a, b], TRACKED_3D)
        self.assertNotIn("clip_worst_view", used,
                         "une métrique absente d'un échantillon ne doit pas servir")
        self.assertEqual(comparable(a["judge"]["metrics"], b["judge"]["metrics"], TRACKED_3D),
                         comparable(b["judge"]["metrics"], a["judge"]["metrics"], TRACKED_3D),
                         "la comparabilité doit être symétrique")

    def test_nan_ignoree(self):
        a = s(0.70)
        b = s(0.72, self_intersections_exactes=float("nan"))
        front, used = pareto_front([a, b], TRACKED_3D)
        self.assertNotIn("self_intersections_exactes", used)

    def test_direction_des_metriques(self):
        """Une métrique 'plus bas est mieux' doit aller dans le bon sens."""
        for key, signe in TRACKED_3D.items():
            haut = {key: 10}
            bas = {key: 1}
            attendu = signe < 0
            self.assertEqual(dominates(bas, haut, {key: signe}) is True, attendu,
                             f"direction incohérente pour {key}")


if __name__ == "__main__":
    unittest.main(verbosity=2)
