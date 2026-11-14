"""The 3D library groups files by generation, titles them with the user's request, opens the deliverable.

`/api/3d/list` showed every GLB flat: each generation appeared as four files whose names are the
same from one project to the next, with no title or preview, and the 3D view only had a raw file
picker to reopen a model.
"""
from __future__ import annotations

import json
import struct
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "application"))
from three_d_library import projets_3d  # noqa: E402


def glb(path: Path, animated: bool = False) -> None:
    """Smallest valid GLB header with a JSON chunk; animation declared or not."""
    doc = {"asset": {"version": "2.0"}, "animations": [{"channels": [], "samplers": []}] if animated else []}
    data = json.dumps(doc).encode()
    data += b" " * ((4 - len(data) % 4) % 4)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"glTF" + struct.pack("<II", 2, 12 + 8 + len(data)) + struct.pack("<II", len(data), 0x4E4F534A) + data)


class Library(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name) / "3d"
        run = self.root / "conversations" / "coffre_avec_une_animation_d_ouverture_run42" / "run42"
        glb(run / "modele" / "modele_couleurs.glb")
        glb(run / "modele" / "modele_geometrie.glb")
        glb(run / "mouvement" / "mouvement_couleurs.glb", animated=True)
        glb(run / "mouvement" / "mouvement_geometrie.glb", animated=True)
        glb(run / "work" / "run42_mesh.glb")                      # intermediate: hidden once delivered
        (run / "apercus").mkdir()
        (run / "apercus" / "f3d_ouverture_t0.png").write_bytes(b"\x89PNG")
        (run / "journal").mkdir()
        (run / "journal" / "audit.json").write_text(json.dumps(
            {"audit": [{"stage": "lecture_demande", "demande": "coffre avec une animation d'ouverture"}]}), encoding="utf-8")
        (run / "prompt").mkdir()
        (run / "prompt" / "prompt.txt").write_text("un coffre fermé, A closed wooden chest, studio lighting", encoding="utf-8")

        ui_run = self.root / "conversations" / "vase_4d04e8a2-4fca-4ef8" / "juan_bike_1"
        glb(ui_run / "modele" / "modele_couleurs.glb")
        glb(ui_run / "modele" / "modele_couleurs_anim.glb", animated=True)   # animation written next to the model
        (ui_run / "prompt").mkdir(parents=True)
        (ui_run / "prompt" / "prompt.txt").write_text("session_id=s1\nrun_id=juan_bike_1\n\nvase en forme de cœur", encoding="utf-8")

        loose = self.root / "_validation" / "articulation"
        glb(loose / "sortie_coffre.glb", animated=True)

    def tearDown(self):
        self.tmp.cleanup()

    def project(self, needle: str):
        projects = projets_3d([str(self.root)])
        return next(p for p in projects if needle in p["id"]), projects

    def test_one_card_per_generation_with_the_user_request_as_title(self):
        chest, projects = self.project("run42")
        self.assertEqual(len(projects), 3)
        # the technical generator prompt is never the title; the request read by the pipeline is
        self.assertEqual(chest["titre"], "coffre avec une animation d'ouverture")
        vase, _ = self.project("juan_bike_1")
        self.assertEqual(vase["titre"], "vase en forme de cœur")

    def test_the_default_deliverable_is_the_animated_model_and_variants_are_named(self):
        chest, _ = self.project("run42")
        self.assertTrue(chest["anime"])
        self.assertEqual(chest["livrable"]["nom"], "mouvement_couleurs.glb")
        self.assertEqual([v["role"] for v in chest["variantes"]],
                         ["Animé — couleurs", "Couleurs", "Animé — géométrie", "Géométrie seule"])
        self.assertTrue(all(v["url"].startswith("/api/3d/file/conversations/") for v in chest["variantes"]))
        self.assertNotIn("run42_mesh.glb", [v["nom"] for v in chest["variantes"]])

    def test_an_animation_is_recognised_from_the_file_not_from_its_folder(self):
        vase, _ = self.project("juan_bike_1")
        self.assertTrue(vase["anime"])
        self.assertEqual(vase["livrable"]["nom"], "modele_couleurs_anim.glb")
        self.assertEqual(vase["livrable"]["role"], "Animé — couleurs")

    def test_the_thumbnail_comes_from_the_rendered_previews(self):
        chest, _ = self.project("run42")
        self.assertTrue(chest["vignette"].endswith("/apercus/f3d_ouverture_t0.png"))
        loose, _ = self.project("_validation")
        self.assertIsNone(loose["vignette"])


if __name__ == "__main__":
    unittest.main()
