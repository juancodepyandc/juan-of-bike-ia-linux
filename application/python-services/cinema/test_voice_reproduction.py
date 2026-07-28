#!/usr/bin/env python3
"""Garde de non-regression : reproduction de voix plutot que synthese.

Contexte mesure : la bibliotheque de voix etait VIDE (`count: 0`) alors que
CosyVoice3 — moteur de clonage zero-shot — etait installe et pret. Tous les
personnages tombaient donc sur un preset generique, et le film sonnait
synthetique. Pire, le routage envoyait vers ce preset MEME quand une reference
existait, des lors que le personnage portait `voice_policy: "style"`.

Ces tests figent trois garanties :
  1. un echantillon depose est retrouve malgre les decorations de nom
     (`style_natsu_fr` <-> `natsu_dragneel_VF.mp4`) ;
  2. une voix amorcee par TTS ne compte JAMAIS comme une reference — la cloner
     reproduirait fidelement un robot ;
  3. l'absence d'echantillon est dite explicitement, jamais masquee.
"""

import importlib.util
import os
import sys
import tempfile
import unittest
from pathlib import Path

HERE = os.path.dirname(os.path.abspath(__file__))


def _load():
    spec = importlib.util.spec_from_file_location(
        "voice_clone_under_test", os.path.join(HERE, "voice_clone.py"))
    mod = importlib.util.module_from_spec(spec)
    sys.modules["voice_clone_under_test"] = mod
    spec.loader.exec_module(mod)
    return mod


VC = _load()


class TestCorrespondanceEchantillon(unittest.TestCase):
    """Le nom du fichier depose ne doit pas avoir a etre exact."""

    def _match(self, character: str, filename: str) -> bool:
        a = VC._core_tokens(character)
        b = VC._core_tokens(Path(filename).stem)
        if not a or not b:
            return False
        n = min(len(a), len(b))
        return a[:n] == b[:n]

    def test_decorations_ignorees(self):
        for char, fn in [
            ("style_natsu_fr", "natsu.mp4"),
            ("Natsu", "natsu_dragneel_VF.mp3"),
            ("Natsu", "natsu_dragneel_scene_complete.mkv"),
            ("Mecano", "mecano_french_older.m4a"),
            ("voix_lucy_fr", "lucy.wav"),
        ]:
            with self.subTest(char=char, fichier=fn):
                self.assertTrue(self._match(char, fn))

    def test_personnage_different_jamais_confondu(self):
        for char, fn in [("Natsu", "luffy_vf.wav"),
                         ("Lucy", "natsu.mp3"),
                         ("Gray", "grayson_smith.wav")]:
            with self.subTest(char=char, fichier=fn):
                self.assertFalse(self._match(char, fn))

    def test_nom_vide_ne_matche_rien(self):
        self.assertEqual(VC._core_tokens("style_fr"), [])
        self.assertIsNone(VC.find_sample_file("style_fr"))


class TestVraieVoix(unittest.TestCase):
    """Une voix amorcee par Kokoro n'est pas une reference de reproduction."""

    def test_amorcage_tts_refuse(self):
        self.assertFalse(VC.is_real_voice({"source": "bootstrap_kokoro_1785"}))

    def test_echantillon_depose_accepte(self):
        self.assertTrue(VC.is_real_voice({"source": "echantillon:natsu.mp4"}))

    def test_source_absente_refusee(self):
        self.assertFalse(VC.is_real_voice({}))
        self.assertFalse(VC.is_real_voice({"source": ""}))


class TestResolution(unittest.TestCase):
    """L'absence de reference doit etre dite, pas masquee."""

    def test_sans_echantillon_dit_clairement_non_clone(self):
        res = VC.resolve_voice("PersonnageQuiNExistePas", "fr")
        self.assertFalse(res["ok"])
        self.assertFalse(res["cloned"])
        self.assertIn("echantillons", res["dropbox"])
        self.assertTrue(res["hint"])

    def test_personnage_sans_nom(self):
        res = VC.resolve_voice("", "fr")
        self.assertFalse(res["cloned"])

    def test_le_depot_ignore_les_fichiers_non_media(self):
        with tempfile.TemporaryDirectory() as tmp:
            original = VC.DROPBOX_DIR
            try:
                VC.DROPBOX_DIR = Path(tmp)
                (Path(tmp) / "natsu.md").write_text("pas un son")
                (Path(tmp) / "natsu.txt").write_text("pas un son")
                self.assertIsNone(VC.find_sample_file("natsu"))
                (Path(tmp) / "natsu.wav").write_bytes(b"RIFF")
                self.assertIsNotNone(VC.find_sample_file("natsu"))
            finally:
                VC.DROPBOX_DIR = original

    def test_le_plus_long_echantillon_gagne(self):
        with tempfile.TemporaryDirectory() as tmp:
            original = VC.DROPBOX_DIR
            try:
                VC.DROPBOX_DIR = Path(tmp)
                (Path(tmp) / "natsu.wav").write_bytes(b"x" * 100)
                (Path(tmp) / "natsu_scene_longue.wav").write_bytes(b"x" * 5000)
                best = VC.find_sample_file("natsu")
                self.assertEqual(best.name, "natsu_scene_longue.wav")
            finally:
                VC.DROPBOX_DIR = original


if __name__ == "__main__":
    unittest.main(verbosity=2)
