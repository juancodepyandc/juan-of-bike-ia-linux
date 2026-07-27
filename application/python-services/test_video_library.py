#!/usr/bin/env python3
"""Garde de non-regression : publication automatique dans la bibliotheque.

Contexte : le pipeline n'ecrivait que dans `temp/cinema/job_<id>/`, un
repertoire TEMPORAIRE. Rien n'apparaissait dans `output/videos`, le resultat
n'etait ni citable ni retrouvable, et il fallait lancer un rangement a la main.
`publish_job` est appelee a la fin de chaque rendu : ces tests figent son
contrat, notamment le fait qu'elle COPIE (jamais ne deplace) — un film coute
des heures de calcul, la publication ne doit pas pouvoir le detruire.
"""

import importlib.util
import json
import os
import shutil
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

spec = importlib.util.spec_from_file_location(
    "video_library_under_test", os.path.join(HERE, "video_library.py"))
VL = importlib.util.module_from_spec(spec)
sys.modules["video_library_under_test"] = VL
spec.loader.exec_module(VL)


class PublishJobTest(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.job = os.path.join(self.tmp, "job_abc")
        self.work = os.path.join(self.tmp, "work")
        os.makedirs(self.job)
        os.makedirs(self.work)
        self.final = os.path.join(self.job, "final.mp4")
        with open(self.final, "wb") as f:
            f.write(b"\0" * 20000)
        with open(os.path.join(self.job, "storyboard.json"), "w") as f:
            json.dump({"title": "Un film"}, f)
        for name in ("char_1_natsu.png", "shot_01_muxed.mp4", "music.wav",
                     "shot_01_silent.render_log.txt"):
            with open(os.path.join(self.work, name), "wb") as f:
                f.write(b"\0" * 128)
        self.published = []
        # publie dans un FILMS temporaire pour ne pas polluer la vraie
        # bibliotheque pendant les tests
        self._films = VL.FILMS
        VL.FILMS = os.path.join(self.tmp, "films")

    def tearDown(self):
        VL.FILMS = self._films
        shutil.rmtree(self.tmp, ignore_errors=True)

    def publish(self, **kw):
        d = VL.publish_job(job_dir=self.job, work_dir=self.work,
                           title="Un film", final_mp4=self.final, **kw)
        self.published.append(d)
        return d

    def test_cree_l_arborescence_complete(self):
        d = self.publish()
        for sub in ("plans", "references", "audio"):
            self.assertTrue(os.path.isdir(os.path.join(d, sub)), sub)
        for f in ("film.mp4", "rapport.json", "storyboard.json"):
            self.assertTrue(os.path.isfile(os.path.join(d, f)), f)

    def test_trie_les_artefacts_par_type(self):
        d = self.publish()
        self.assertIn("char_1_natsu.png", os.listdir(os.path.join(d, "references")))
        self.assertIn("shot_01_muxed.mp4", os.listdir(os.path.join(d, "plans")))
        self.assertIn("music.wav", os.listdir(os.path.join(d, "audio")))
        # un log de rendu n'est pas un livrable : il ne doit pas etre publie
        for sub in ("plans", "references", "audio"):
            self.assertNotIn("shot_01_silent.render_log.txt",
                             os.listdir(os.path.join(d, sub)))

    def test_copie_et_ne_detruit_jamais_la_source(self):
        """Un film coute des heures : la publication ne doit pas le deplacer."""
        self.publish()
        self.assertTrue(os.path.exists(self.final))

    def test_nom_lisible_et_date(self):
        d = self.publish()
        self.assertRegex(os.path.basename(d), r"^\d{4}-\d{2}-\d{2}_un-film")

    def test_pas_de_collision_entre_deux_films_homonymes(self):
        a = self.publish()
        b = self.publish()
        self.assertNotEqual(a, b)
        self.assertTrue(os.path.isfile(os.path.join(b, "film.mp4")))

    def test_refuse_un_livrable_absent(self):
        with self.assertRaises(RuntimeError):
            VL.publish_job(self.job, self.work, "x",
                           os.path.join(self.job, "inexistant.mp4"))

    def test_refuse_un_livrable_tronque(self):
        petit = os.path.join(self.job, "petit.mp4")
        with open(petit, "wb") as f:
            f.write(b"\0" * 10)
        with self.assertRaises(RuntimeError):
            VL.publish_job(self.job, self.work, "x", petit)

    def test_rapport_porte_l_empreinte(self):
        d = self.publish()
        with open(os.path.join(d, "rapport.json")) as f:
            rapport = json.load(f)
        self.assertEqual(len(rapport["sha256"]), 64)
        self.assertEqual(rapport["titre"], "Un film")

    def test_tolere_un_dossier_de_travail_absent(self):
        d = VL.publish_job(self.job, os.path.join(self.tmp, "nexistepas"),
                           "Un film", self.final)
        self.assertTrue(os.path.isfile(os.path.join(d, "film.mp4")))


if __name__ == "__main__":
    unittest.main(verbosity=2)
