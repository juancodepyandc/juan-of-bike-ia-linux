# -*- coding: utf-8 -*-
"""Portail de qualite 3D — ce qu il laisse passer, et ce qu il arrete.

POURQUOI CE FICHIER EXISTE
--------------------------
`score_mesh` est la derniere porte avant livraison d un modele. Sa note
globale est une moyenne ponderee, doublee de PLANCHERS DURS par axe: un axe
sous son plancher force la reprise, quelle que soit la moyenne.

L axe `geometric_density` n avait PAS de plancher. Il ne pesait que 20 % de
la moyenne et ne pouvait donc jamais bloquer seul. Mesure du defaut: une
icosphere de 12 SOMMETS (20 faces), correctement coloriee, sortait a 67,8/100
avec `retry_recommended = False` et aucun axe en echec — livree comme modele
fini. Le detail de l axe disait pourtant `passes_floor: False`:
l information existait et etait jetee.

Calibrage: les 26 GLB reels presents dans `output/3d` comptent de 65 858 a
5 610 029 sommets et notent TOUS la densite a 100. Un plancher a 20 n en
rejette aucun.

METHODE
-------
Les maillages sont FABRIQUES ici avec trimesh, donc reproductibles partout et
sans dependre d une sortie de session passee. Les controles sur les GLB reels
sont marques opportunistes : ils se sautent proprement si le dossier est vide.

Reproduction en ligne de commande :
    .venv/bin/python -m unittest discover -s python-services -p 'test_mesh_quality_gate.py' -t python-services
"""

from __future__ import annotations

import glob
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from mesh_quality_score import (  # noqa: E402
    AXIS_HARD_FLOORS, KIND_VERTEX_FLOOR, RETRY_THRESHOLD, score_mesh,
)

try:
    import trimesh
    _TRIMESH = True
except Exception:  # pragma: no cover
    _TRIMESH = False

SORTIE_3D = Path(__file__).resolve().parents[1] / "output" / "3d"


@unittest.skipUnless(_TRIMESH, "trimesh requis")
class PortailDensiteTests(unittest.TestCase):
    """Le coeur du sujet : un maillage quasi vide ne part pas en livraison."""

    @classmethod
    def setUpClass(cls):
        cls.dossier = tempfile.mkdtemp()

    def _glb(self, mesh, nom: str) -> str:
        chemin = str(Path(self.dossier) / f"{nom}.glb")
        mesh.export(chemin)
        return chemin

    def _colore(self, mesh):
        """Couleurs riches : on isole ainsi l axe densite. Sans cela, un echec
        de couleur masquerait ce qu on veut mesurer."""
        v = np.asarray(mesh.vertices)
        c = np.zeros((len(v), 4), np.uint8)
        c[:, 3] = 255
        c[:, :3] = ((v - v.min(0)) / (np.ptp(v, axis=0) + 1e-9) * 255).astype(np.uint8)
        mesh.visual.vertex_colors = c
        return mesh

    def _ico(self, subdivisions: int):
        return self._colore(trimesh.creation.icosphere(subdivisions=subdivisions, radius=0.5))

    def test_la_densite_a_un_plancher_dur(self):
        self.assertIn(
            "geometric_density", AXIS_HARD_FLOORS,
            "sans plancher, la densite ne pese que 20 % de la moyenne et ne peut "
            "jamais bloquer seule une livraison")

    def test_un_maillage_de_12_sommets_est_refuse(self):
        r = score_mesh(self._glb(self._ico(0), "ico0"), "generic")
        self.assertTrue(r["ok"])
        self.assertTrue(
            r["retry_recommended"],
            f"12 sommets livres comme modele fini (note {r['overall_score']})")
        self.assertIn("geometric_density", r["failed_axes"])

    def test_la_raison_du_refus_est_explicite(self):
        r = score_mesh(self._glb(self._ico(0), "ico0b"), "generic")
        self.assertTrue(any("geometric_density" in raison for raison in r["retry_reasons"]),
                        r["retry_reasons"])

    def test_escalier_de_densite(self):
        """La note doit croitre avec le nombre de sommets, et le verdict
        basculer une seule fois."""
        notes = []
        for sub in range(0, 5):
            r = score_mesh(self._glb(self._ico(sub), f"esc{sub}"), "generic")
            notes.append((sub, r["scores"]["geometric_density"]["score"],
                          r["retry_recommended"]))
        densites = [n[1] for n in notes]
        for i in range(1, len(densites)):
            self.assertGreaterEqual(densites[i], densites[i - 1], notes)
        self.assertTrue(notes[0][2], "12 sommets accepte")
        self.assertFalse(notes[-1][2], f"2562 sommets refuse : {notes}")

    def test_un_seul_triangle_est_refuse(self):
        v = np.array([[0, 0, 0], [1, 0, 0], [0, 1, 0]], float)
        m = trimesh.Trimesh(vertices=v, faces=np.array([[0, 1, 2]]), process=False)
        m.visual.vertex_colors = np.array(
            [[255, 0, 0, 255], [0, 255, 0, 255], [0, 0, 255, 255]], np.uint8)
        r = score_mesh(self._glb(m, "triangle"), "generic")
        self.assertTrue(r["retry_recommended"])

    def test_chaque_famille_declare_un_plancher_de_sommets(self):
        for famille, plancher in KIND_VERTEX_FLOOR.items():
            self.assertGreater(plancher, 0, famille)


@unittest.skipUnless(_TRIMESH, "trimesh requis")
class PortailCouleurTests(unittest.TestCase):
    """Le maillage NOIR — la panne la plus couteuse de l historique du projet."""

    @classmethod
    def setUpClass(cls):
        cls.dossier = tempfile.mkdtemp()

    def _glb(self, mesh, nom: str) -> str:
        chemin = str(Path(self.dossier) / f"{nom}.glb")
        mesh.export(chemin)
        return chemin

    def _sphere_teintee(self, rgb):
        m = trimesh.creation.icosphere(subdivisions=3, radius=0.5)
        m.visual.vertex_colors = np.tile(list(rgb) + [255], (len(m.vertices), 1)).astype(np.uint8)
        return m

    def test_un_maillage_noir_est_refuse(self):
        r = score_mesh(self._glb(self._sphere_teintee((0, 0, 0)), "noir"), "generic")
        self.assertIn("color_richness", r["failed_axes"])
        self.assertTrue(r["retry_recommended"])

    def test_un_maillage_monochrome_est_refuse(self):
        for teinte, nom in [((128, 128, 128), "gris"), ((200, 30, 30), "rouge")]:
            with self.subTest(teinte=nom):
                r = score_mesh(self._glb(self._sphere_teintee(teinte), nom), "generic")
                self.assertIn("color_richness", r["failed_axes"])

    def test_un_maillage_sans_couleur_est_refuse(self):
        m = trimesh.creation.icosphere(subdivisions=3, radius=0.5)
        r = score_mesh(self._glb(m, "nu"), "generic")
        self.assertIn("color_richness", r["failed_axes"])

    def test_un_degrade_riche_est_accepte(self):
        m = trimesh.creation.icosphere(subdivisions=4, radius=0.5)
        v = np.asarray(m.vertices)
        c = np.zeros((len(v), 4), np.uint8)
        c[:, 3] = 255
        c[:, :3] = ((v - v.min(0)) / (np.ptp(v, axis=0) + 1e-9) * 255).astype(np.uint8)
        m.visual.vertex_colors = c
        r = score_mesh(self._glb(m, "degrade"), "generic")
        self.assertNotIn("color_richness", r["failed_axes"],
                         f"faux positif sur un maillage colorie : {r['scores']['color_richness']}")


@unittest.skipUnless(_TRIMESH, "trimesh requis")
class ContratDeSortieTests(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.dossier = tempfile.mkdtemp()
        m = trimesh.creation.icosphere(subdivisions=3, radius=0.5)
        cls.chemin = str(Path(cls.dossier) / "base.glb")
        m.export(cls.chemin)

    def test_forme_du_rapport(self):
        r = score_mesh(self.chemin, "generic")
        for cle in ("ok", "schema", "overall_score", "retry_recommended",
                    "retry_threshold", "retry_reasons", "failed_axes", "scores"):
            self.assertIn(cle, r, cle)
        self.assertEqual(r["schema"], "aurora.mesh_quality.v1")

    def test_les_cinq_axes_sont_toujours_notes(self):
        r = score_mesh(self.chemin, "generic")
        for axe in ("color_richness", "geometric_density", "silhouette_aspect",
                    "manifold_health", "surface_quality"):
            self.assertIn(axe, r["scores"], axe)
            self.assertIsInstance(r["scores"][axe]["score"], int)

    def test_les_notes_restent_dans_zero_cent(self):
        r = score_mesh(self.chemin, "generic")
        for axe, detail in r["scores"].items():
            self.assertGreaterEqual(detail["score"], 0, axe)
            self.assertLessEqual(detail["score"], 100, axe)
        self.assertGreaterEqual(r["overall_score"], 0)
        self.assertLessEqual(r["overall_score"], 100)

    def test_tout_axe_sous_son_plancher_force_la_reprise(self):
        """Propriete du portail, independante des valeurs : si un axe est
        signale en echec, la reprise DOIT etre recommandee."""
        for sub in range(0, 5):
            m = trimesh.creation.icosphere(subdivisions=sub, radius=0.5)
            chemin = str(Path(self.dossier) / f"p{sub}.glb")
            m.export(chemin)
            r = score_mesh(chemin, "generic")
            if r["failed_axes"]:
                self.assertTrue(r["retry_recommended"],
                                f"axes en echec {r['failed_axes']} sans reprise")

    def test_une_famille_inconnue_retombe_sur_generic_sans_lever(self):
        r = score_mesh(self.chemin, "famille_inexistante")
        self.assertTrue(r["ok"])
        self.assertEqual(r["subject_kind"], "generic")

    def test_fichier_absent(self):
        r = score_mesh("/tmp/ce_fichier_n_existe_pas.glb", "generic")
        self.assertFalse(r["ok"])
        self.assertIn("not found", r["error"])

    def test_fichier_illisible(self):
        chemin = str(Path(self.dossier) / "corrompu.glb")
        Path(chemin).write_bytes(b"ceci n est pas un glb")
        r = score_mesh(chemin, "generic")
        self.assertFalse(r["ok"])
        self.assertIsInstance(r["error"], str)

    def test_notation_deterministe(self):
        a = score_mesh(self.chemin, "generic")
        b = score_mesh(self.chemin, "generic")
        self.assertEqual(a["overall_score"], b["overall_score"])
        self.assertEqual(a["failed_axes"], b["failed_axes"])


class CalibrageSurLivraisonsReellesTests(unittest.TestCase):
    """Controle OPPORTUNISTE : le plancher ne doit pas rejeter du vrai travail.

    Se saute proprement quand `output/3d` est vide — un test de regression ne
    peut pas dependre d artefacts de session.
    """

    def test_aucun_glb_reel_n_est_rejete_par_le_plancher_de_densite(self):
        if not SORTIE_3D.is_dir():
            self.skipTest("output/3d absent")
        fichiers = sorted(glob.glob(str(SORTIE_3D / "**" / "*.glb"), recursive=True))[:12]
        if not fichiers:
            self.skipTest("aucun GLB dans output/3d")
        rejetes = []
        examines = 0
        for chemin in fichiers:
            r = score_mesh(chemin, "generic")
            if not r.get("ok"):
                continue
            examines += 1
            if "geometric_density" in r["failed_axes"]:
                rejetes.append((Path(chemin).name,
                                r["scores"]["geometric_density"]["vertex_count"]))
        if examines == 0:
            self.skipTest("aucun GLB lisible")
        self.assertEqual(
            rejetes, [],
            f"{len(rejetes)}/{examines} livraisons reelles rejetees par le plancher "
            f"de densite ({AXIS_HARD_FLOORS['geometric_density']}) : {rejetes}")


if __name__ == "__main__":
    unittest.main()
