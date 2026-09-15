# -*- coding: utf-8 -*-
"""Metriques d animation — un personnage FIGE ne doit pas passer la porte.

POURQUOI CE FICHIER EXISTE
--------------------------
`anim_metrics.evaluate` conclut par
`passed = len(failed) == 0 and len(graded) > 0`. Ce garde-fou exige qu au
moins une metrique ait pu NOTER. Il n exige d aucune metrique qu elle ait
observe du MOUVEMENT.

Or une prise reduite au minimum — `verts` + `edges` + `part_labels`, ce que
rend un bake depourvu de pistes de joints — ne laisse noter que
`edge_stretch` et `self_intersection`. Un personnage entierement fige passe
trivialement les deux: un maillage immobile ne se dechire pas et ne
s auto-traverse pas davantage qu au repos.

Mesure avant correction, sur l humanoide de synthese construit ici: le
personnage FIGE et le personnage qui BOUGE rendaient tous deux
`passed=True`, avec exactement les memes metriques notees. La porte ne les
distinguait pas — c est la panne qui a deja coute au projet une validation
a 100/100 sur un sujet immobile.

METHODE
-------
Geometrie de synthese entierement deterministe (aucun tirage aleatoire, aucun
fichier externe): trois cylindres bien separes, donc pas d auto-intersection
parasite qui masquerait la comparaison. La verite terrain est construite, pas
estimee.

Reproduction en ligne de commande :
    .venv/bin/python -m unittest discover -s python-services -p 'test_anim_metrics_motion.py' -t python-services
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import anim_metrics as AM  # noqa: E402


FPS = 24
FRAMES = 48


def _cylindre(cx: float, cy: float, z0: float, z1: float,
              r: float = 0.06, n: int = 16, k: int = 6) -> np.ndarray:
    """Anneaux empiles — geometrie fermee, pas de sommets errants."""
    pts = []
    for z in np.linspace(z0, z1, k):
        for a in np.linspace(0.0, 2.0 * np.pi, n, endpoint=False):
            pts.append([cx + r * np.cos(a), cy + r * np.sin(a), z])
    return np.array(pts, dtype=float)


JAMBE_L = _cylindre(-0.15, 0.0, 0.0, 0.9)
JAMBE_R = _cylindre(+0.15, 0.0, 0.0, 0.9)
TORSE = _cylindre(0.0, 0.0, 0.9, 1.7, r=0.18)
REST = np.vstack([JAMBE_L, JAMBE_R, TORSE])
PARTS = np.array([0] * len(JAMBE_L) + [1] * len(JAMBE_R) + [2] * len(TORSE))

_EDGES = []
_base = 0
for _bloc in (JAMBE_L, JAMBE_R, TORSE):
    for _i in range(len(_bloc) - 1):
        _EDGES.append([_base + _i, _base + _i + 1])
    _base += len(_bloc)
EDGES = np.array(_EDGES)


def prise(verts: np.ndarray, **extra) -> dict:
    take = {
        "fps": FPS, "verts": verts, "rest": REST, "edges": EDGES,
        "part_labels": PARTS, "up_axis": "Z", "ground": 0.0,
        "adjacent_parts": [(0, 2), (1, 2)],
    }
    take.update(extra)
    return take


def fige() -> np.ndarray:
    return np.tile(REST, (FRAMES, 1, 1))


def marche(amplitude: float = 0.12) -> np.ndarray:
    t = np.arange(FRAMES) / float(FPS)
    v = np.tile(REST, (FRAMES, 1, 1)).copy()
    v[:, :, 0] += (amplitude * np.sin(2 * np.pi * 1.0 * t))[:, None]
    return v


class PorteFigeTests(unittest.TestCase):
    """Le coeur du sujet : fige et mouvant doivent etre DISTINGUES."""

    def test_le_personnage_fige_est_refuse(self):
        rapport = AM.evaluate(prise(fige()), "humanoid")
        self.assertFalse(
            rapport["passed"],
            "un personnage entierement immobile a ete accepte : "
            f"metriques notees = {[r['metric'] for r in rapport['results'] if r['passed'] is not None]}")

    def test_le_personnage_qui_bouge_est_accepte(self):
        rapport = AM.evaluate(prise(marche()), "humanoid")
        self.assertTrue(
            rapport["passed"],
            f"faux positif : {rapport['failed_metrics']}")

    def test_les_deux_sont_distingues(self):
        a = AM.evaluate(prise(fige()), "humanoid")
        b = AM.evaluate(prise(marche()), "humanoid")
        self.assertNotEqual(
            a["passed"], b["passed"],
            "fige et mouvant rendent le meme verdict : la porte ne mesure pas le mouvement")

    def test_la_metrique_fautive_est_nommee(self):
        rapport = AM.evaluate(prise(fige()), "humanoid")
        self.assertIn("motion_amplitude", rapport["failed_metrics"])

    def test_un_bouton_est_propose_pour_la_reparation(self):
        rapport = AM.evaluate(prise(fige()), "humanoid")
        boutons = [k["metric"] for k in rapport["knobs"]]
        self.assertIn("motion_amplitude", boutons,
                      "un echec sans bouton ne dit pas quoi corriger")


class AmplitudeTests(unittest.TestCase):

    def test_amplitude_nulle_sur_une_prise_figee(self):
        r = AM.m_motion_amplitude(prise(fige()), "humanoid")
        self.assertEqual(r["value"], 0.0)
        self.assertTrue(r["detail"]["frozen"])
        self.assertFalse(r["passed"])

    def test_amplitude_croissante_avec_le_mouvement(self):
        valeurs = [AM.m_motion_amplitude(prise(marche(a)), "humanoid")["value"]
                   for a in (0.0, 0.05, 0.10, 0.20, 0.40)]
        for i in range(1, len(valeurs)):
            self.assertGreater(
                valeurs[i], valeurs[i - 1],
                f"amplitude non monotone : {valeurs}")

    def test_amplitude_normalisee_par_la_taille_du_sujet(self):
        """Un sujet deux fois plus grand qui bouge deux fois plus doit rendre
        la MEME amplitude relative — sinon la metrique mesure des metres, pas
        du mouvement."""
        petit = AM.m_motion_amplitude(prise(marche(0.10)), "humanoid")["value"]
        grand_rest = REST * 2.0
        t = np.arange(FRAMES) / float(FPS)
        v = np.tile(grand_rest, (FRAMES, 1, 1)).copy()
        v[:, :, 0] += (0.20 * np.sin(2 * np.pi * t))[:, None]
        take = prise(v)
        take["rest"] = grand_rest
        grand = AM.m_motion_amplitude(take, "humanoid")["value"]
        self.assertAlmostEqual(petit, grand, places=4,
                               msg=f"petit={petit} grand={grand}")

    def test_une_seule_image_est_ignoree_pas_refusee(self):
        """Une pose statique exportee sur une image n est pas une animation
        ratee : c est autre chose. La metrique doit se taire."""
        r = AM.m_motion_amplitude(prise(np.tile(REST, (1, 1, 1))), "humanoid")
        self.assertIsNone(r["passed"])
        self.assertTrue(r["skipped"])

    def test_prise_sans_verts_est_ignoree(self):
        r = AM.m_motion_amplitude({"fps": FPS}, "humanoid")
        self.assertIsNone(r["passed"])

    def test_sujet_degenere_reste_un_echec_sans_lever(self):
        """Tous les sommets au meme point, sur toutes les images.

        `_bbox_diag` rend 1.0 pour une boite degeneree, donc aucune division
        par zero: la valeur reste finie, vaut 0.0, et l echec est le bon
        verdict — un sujet reduit a un point immobile n est pas une animation.
        Ce qu on verifie ici, c est qu il ne LEVE pas et ne rend pas l infini.
        """
        v = np.zeros((FRAMES, 10, 3))
        r = AM.m_motion_amplitude({"fps": FPS, "verts": v}, "humanoid")
        self.assertEqual(r["value"], 0.0)
        self.assertFalse(r["passed"])
        self.assertTrue(np.isfinite(r["value"]))

    def test_valeur_toujours_finie(self):
        for amplitude in (0.0, 1e-9, 0.01, 10.0, 1e6):
            r = AM.m_motion_amplitude(prise(marche(amplitude)), "humanoid")
            self.assertTrue(np.isfinite(r["value"]), f"amplitude={amplitude}")


class FamillesTests(unittest.TestCase):

    def test_les_familles_deformantes_mesurent_le_mouvement(self):
        for famille in ("humanoid", "creature", "mecha_rigid"):
            notees = [r["metric"] for r in AM.evaluate(prise(marche()), famille)["results"]]
            self.assertIn("motion_amplitude", notees, famille)

    def test_aucune_famille_ne_passe_sans_rien_noter(self):
        """Une prise vide ne doit jamais rendre `passed=True` : c est la forme
        la plus pure du faux positif — tout ignorer, donc tout accepter."""
        for famille in sorted(AM.FAMILY_METRICS):
            rapport = AM.evaluate({"fps": FPS}, famille)
            self.assertFalse(rapport["passed"], famille)
            self.assertEqual(rapport["n_graded"], 0, famille)

    def test_le_fige_est_refuse_dans_chaque_famille_deformante(self):
        for famille in ("humanoid", "creature", "mecha_rigid"):
            rapport = AM.evaluate(prise(fige()), famille)
            self.assertFalse(rapport["passed"], f"{famille} accepte un sujet immobile")

    def test_chaque_seuil_a_un_bouton_et_reciproquement(self):
        sans_bouton = [m for m in AM.THRESHOLDS
                       if m != "edge_stretch" and m not in AM.KNOBS]
        sans_seuil = [m for m in AM.KNOBS if m not in AM.THRESHOLDS]
        self.assertEqual(sans_bouton, [], "seuils sans bouton de reparation")
        self.assertEqual(sans_seuil, [], "boutons sans seuil")


class DeterminismeTests(unittest.TestCase):

    def test_deux_evaluations_identiques(self):
        a = AM.evaluate(prise(marche()), "humanoid")
        b = AM.evaluate(prise(marche()), "humanoid")
        self.assertEqual(a["failed_metrics"], b["failed_metrics"])
        self.assertEqual([r["value"] for r in a["results"]],
                         [r["value"] for r in b["results"]])

    def test_l_evaluation_ne_modifie_pas_la_prise(self):
        take = prise(marche())
        avant = {k: (v.copy() if isinstance(v, np.ndarray) else v) for k, v in take.items()}
        AM.evaluate(take, "humanoid")
        for k, v in avant.items():
            if isinstance(v, np.ndarray):
                self.assertTrue(np.array_equal(v, take[k]), f"{k} modifie")


if __name__ == "__main__":
    unittest.main()
