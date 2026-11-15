"""Animation ON shows the subject at rest; the generator's colours are never repainted.

Run of 15/11/2026, « natsu Dragneel qui cours », animation enabled: the request reader came back
with an invented red outfit and the running posture, was rejected without a second chance, and the
whole sentence — movement included — went to the reference. The character was rebuilt mid-stride,
the texture retouch then painted the black waistcoat yellow and the white trousers skin-coloured,
and the refused mesh never reached the animation step (no mouvement/ folder).
"""
from __future__ import annotations

import json
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
SERVICES = ROOT / "application" / "python-services"
sys.path.insert(0, str(SERVICES))

from lecture_demande import lire_demande  # noqa: E402

GOOD = {"sujet": "Natsu Dragneel", "sujet_en": "Natsu Dragneel", "mouvement": "qui cours", "exemplaires": 1,
        "corps_articule": True, "conception": False,
        "sujets": [{"nom": "natsu Dragneel", "nomme": True, "nature": "personnage", "nature_en": "character",
                    "clause": "natsu Dragneel qui cours", "mouvement": "qui cours", "mouvement_en": "a person runs forward",
                    "milieu": {"matiere": None, "relation": None, "justification": ""}}],
        "style": {"texte": "", "cible": None, "justification": ""}}
EMBROIDERED = dict(GOOD, sujet="Natsu Dragneel, personnage aux cheveux roses portant une tenue rouge sans manches, "
                               "des gants rouges et un pantalon noir, dans une posture dynamique de course")


class RequestReading(unittest.TestCase):
    def test_an_embroidered_answer_gets_one_correction_naming_the_broken_rule(self):
        asked: list[str] = []

        def model(text: str) -> str:
            asked.append(text)
            return json.dumps(EMBROIDERED if len(asked) == 1 else GOOD)

        reading = lire_demande("natsu Dragneel qui cours", interroger=model)
        self.assertEqual(reading["source"], "llm")
        self.assertEqual((reading["sujet"], reading["mouvement"]), ("Natsu Dragneel", "qui cours"))
        self.assertTrue(reading["corps_articule"])
        self.assertEqual(len(asked), 2)
        self.assertIn("ne respecte pas le contrat", asked[1])
        self.assertIn("plus long que la demande", asked[1])

    def test_a_second_bad_answer_is_reported_with_its_reason_never_invented(self):
        reading = lire_demande("natsu Dragneel qui cours", interroger=lambda text: json.dumps(EMBROIDERED))
        self.assertEqual(reading["source"], "indisponible")
        self.assertIn("plus long que la demande", reading["raison"])
        self.assertIsNone(reading["corps_articule"])


def pipeline():
    import aurora_3d_pipeline
    return aurora_3d_pipeline


READING = {"source": "llm", "demande": "natsu Dragneel qui cours", "sujet": "Natsu Dragneel",
           "mouvement": "qui cours", "corps_articule": True}


class ReferenceDependsOnTheAnimationButton(unittest.TestCase):
    def test_animation_on_shows_the_subject_at_rest_and_keeps_the_movement_for_the_rig(self):
        choice = pipeline().reference_selon_animation(READING, "natsu Dragneel qui cours", "on")
        self.assertEqual(choice["prompt"], "Natsu Dragneel")
        self.assertEqual(choice["mouvement_reference"], "qui cours")
        self.assertTrue(choice["corps_articule"])

    def test_animation_off_keeps_the_requested_action_as_the_static_subject(self):
        choice = pipeline().reference_selon_animation(READING, "natsu Dragneel qui cours", "off")
        self.assertEqual(choice["prompt"], "natsu Dragneel qui cours")
        self.assertIsNone(choice["mouvement_reference"])
        self.assertIn("pose demandee", choice["message"])

    def test_animation_on_without_a_reading_still_rests_a_body_named_by_the_interface(self):
        unread = {"source": "indisponible", "sujet": "natsu Dragneel qui cours", "mouvement": ""}
        choice = pipeline().reference_selon_animation(unread, "natsu Dragneel qui cours", "on",
                                                      subject_kind_hint="character")
        self.assertEqual(choice["prompt"], "natsu Dragneel qui cours")
        self.assertTrue(choice["mouvement_reference"])
        self.assertTrue(choice["corps_articule"])

    def test_an_object_that_moves_starts_in_its_initial_state_without_a_rest_pose(self):
        chest = {"source": "llm", "sujet": "un coffre fermé", "mouvement": "s'ouvre", "corps_articule": False}
        choice = pipeline().reference_selon_animation(chest, "un coffre qui s'ouvre", "on")
        self.assertEqual(choice["prompt"], "un coffre fermé")
        self.assertFalse(choice["corps_articule"])

    def test_the_reference_prompt_carries_the_rest_pose_only_for_an_animated_body(self):
        mod = pipeline()
        import agi_core.prompt_intelligence as intelligence
        import universal_style_engine as styles
        # no live language model in a unit test: the ontology and style readers answer « nothing »
        with patch.object(intelligence, "analyze_and_direct_prompt", return_value=None), \
                patch.object(styles, "classify_style", return_value={}):
            body = mod.enhance_flux_prompt("Natsu Dragneel", motion_prompt="qui cours", subject_kind="character",
                                           objet_isole=True, corps_articule=True)
            static = mod.enhance_flux_prompt("Natsu Dragneel qui court", motion_prompt=None, subject_kind="character",
                                             objet_isole=True, corps_articule=True)
            chest = mod.enhance_flux_prompt("un coffre fermé", motion_prompt="s'ouvre", subject_kind="object",
                                            objet_isole=True, corps_articule=False)
        self.assertIn("neutral rigging pose", body)
        self.assertNotIn("neutral rigging pose", static)
        self.assertNotIn("neutral rigging pose", chest)


class GeneratorColoursAreKept(unittest.TestCase):
    def mesh(self):
        import trimesh
        from PIL import Image
        albedo = np.zeros((8, 8, 3), np.uint8)
        albedo[:, 4:] = 245                      # left half black cloth, right half white
        orm = np.zeros((8, 8, 3), np.uint8)
        orm[..., 0], orm[..., 1], orm[..., 2] = 255, 210, 230   # the generator says « metal 0.9 » everywhere
        box = trimesh.creation.box()
        uv = np.random.default_rng(0).random((len(box.vertices), 2))
        material = trimesh.visual.material.PBRMaterial(baseColorTexture=Image.fromarray(albedo),
                                                       metallicRoughnessTexture=Image.fromarray(orm))
        box.visual = trimesh.visual.TextureVisuals(uv=uv, material=material)
        return box, albedo

    def test_the_albedo_and_geometry_leave_untouched_and_dark_texels_cannot_be_metal(self):
        from pbr_cartography import enhance_mesh_and_pbr_cartography
        box, albedo = self.mesh()
        faces_before = len(box.faces)
        with patch.dict(os.environ, {"AURORA_PBR_CARTOGRAPHIE": "fidele"}):
            meta = enhance_mesh_and_pbr_cartography(box, None, prompt_context="un samourai kintsugi")
        material = box.visual.material
        self.assertTrue(np.array_equal(np.asarray(material.baseColorTexture.convert("RGB")), albedo))
        self.assertEqual(len(box.faces), faces_before)
        metal = np.asarray(material.metallicRoughnessTexture.convert("RGB"))[..., 2]
        self.assertEqual(int(metal[:, :4].max()), 0)            # black cloth: F0 far below any metal
        self.assertEqual(int(metal[:, 4:].min()), 120)          # bright: kept, scaled 230 × 0.52
        self.assertEqual(meta["cartographie"], "fidele")


if __name__ == "__main__":
    unittest.main()
