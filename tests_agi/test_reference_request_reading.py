"""A reference image shows a subject at rest, once per requested object.

The run of 13 November 2026 asked for « coffre avec une animation d'ouverture ». The whole sentence
drove the reference search, so the retained "photo" was a sprite sheet of six chests at six
opening stages; the reconstruction copied the sheet and the final judge scored it 95.
Two general mechanisms now stand in the way and are tested here: the request is read into
subject / movement / number of instances, and the matte of any provided image is measured for
repeated shapes.
"""
from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SERVICES = ROOT / "application" / "python-services"
if str(SERVICES) not in sys.path:
    sys.path.insert(0, str(SERVICES))

from lecture_demande import SCHEMA, lire_demande  # noqa: E402


def answering(payload):
    return lambda _request: payload if isinstance(payload, str) else json.dumps(payload, ensure_ascii=False)


class RequestReading(unittest.TestCase):
    REQUEST = "coffre avec une animation d'ouverture"

    def test_subject_movement_and_count_are_separated(self):
        reading = lire_demande(self.REQUEST, interroger=answering(
            {"sujet": "un coffre fermé", "sujet_en": "closed chest", "mouvement": "animation d'ouverture",
             "exemplaires": 1}))
        self.assertEqual(reading["schema"], SCHEMA)
        self.assertEqual(reading["source"], "llm")
        self.assertEqual(reading["sujet"], "un coffre fermé")
        self.assertEqual(reading["mouvement"], "animation d'ouverture")
        self.assertEqual(reading["exemplaires"], 1)
        self.assertEqual(reading["demande"], self.REQUEST)

    def test_json_wrapped_in_prose_is_still_read(self):
        reading = lire_demande("une paire de bottes rouges", interroger=answering(
            'Voici : {"sujet": "une paire de bottes rouges", "sujet_en": "pair of red boots", '
            '"mouvement": "", "exemplaires": 2} — terminé.'))
        self.assertEqual((reading["source"], reading["exemplaires"], reading["mouvement"]), ("llm", 2, ""))

    def test_an_answer_outside_the_contract_is_never_passed_off_as_a_reading(self):
        broken_answers = [
            "je ne sais pas",                                             # no JSON
            {"sujet": "", "mouvement": "", "exemplaires": 1},              # empty subject
            {"sujet": "un coffre", "mouvement": "", "exemplaires": 0},     # impossible count
            {"sujet": "un coffre", "mouvement": "", "exemplaires": "un"},  # count is not a number
            {"sujet": "un coffre", "mouvement": "", "exemplaires": True},  # bool is not a count
            {"sujet": "un coffre", "mouvement": ["ouvre"], "exemplaires": 1},
            {"sujet": "un coffre " * 40, "mouvement": "", "exemplaires": 1},  # the model embroidered
            ["un coffre"],
        ]
        for answer in broken_answers:
            with self.subTest(answer=str(answer)[:40]):
                reading = lire_demande(self.REQUEST, interroger=answering(answer))
                self.assertEqual(reading["source"], "indisponible")
                self.assertEqual(reading["sujet"], self.REQUEST)   # the request, untouched
                self.assertIsNone(reading["exemplaires"])          # no count is invented
                self.assertEqual(reading["mouvement"], "")

    def test_an_unreachable_model_reports_itself(self):
        def offline(_request):
            raise ConnectionError("refused")
        reading = lire_demande(self.REQUEST, interroger=offline)
        self.assertEqual(reading["source"], "indisponible")
        self.assertIn("ConnectionError", reading["raison"])

    def test_an_empty_request_is_not_read(self):
        self.assertEqual(lire_demande("   ", interroger=answering({}))["source"], "indisponible")


class RepeatedShapes(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            import cv2  # noqa: F401
            import numpy  # noqa: F401
        except ImportError as exc:  # the lightweight contract CI has no OpenCV
            raise unittest.SkipTest(f"photo_rectifier needs OpenCV: {exc}")
        import photo_rectifier
        cls.module = photo_rectifier

    @staticmethod
    def canvas():
        import numpy as np
        return np.zeros((600, 900), dtype=np.uint8)

    def chest(self, mask, x, y, lid_lift):
        """A box whose lid sits `lid_lift` pixels above the body: one frame of an opening sequence."""
        mask[y + 60:y + 150, x:x + 180] = 255            # body
        mask[y + 20 - lid_lift:y + 62 - lid_lift, x - 6:x + 186] = 255  # lid, wider than the body
        if lid_lift > 4:                                 # the open lid stays attached by its hinge side
            mask[y + 20 - lid_lift:y + 62, x - 6:x + 4] = 255
        return mask

    def test_a_sheet_of_opening_stages_is_six_instances_of_one_shape(self):
        mask = self.canvas()
        for index in range(6):
            self.chest(mask, 60 + (index % 3) * 280, 60 + (index // 3) * 280, lid_lift=index * 6)
        mask[10:26, 380:520] = 255                       # a caption, far smaller than an object
        measure = self.module.mesurer_instances(mask)
        self.assertEqual(measure["composantes_majeures"], 6)
        self.assertEqual(measure["exemplaires"], 6)
        self.assertGreater(measure["part_repetee"], 0.9)
        self.assertTrue(self.module.reference_trop_d_exemplaires(measure, 1))
        self.assertTrue(self.module.reference_trop_d_exemplaires(measure, None))   # unread request: prudence
        self.assertFalse(self.module.reference_trop_d_exemplaires(measure, 6))

    def test_one_object_made_of_detached_pieces_is_one_instance(self):
        import cv2
        mask = self.canvas()
        mask[380:520, 250:650] = 255                                  # a wide base
        cv2.circle(mask, (450, 200), 120, 255, thickness=28)          # a ring floating above it
        measure = self.module.mesurer_instances(mask)
        self.assertEqual(measure["composantes_majeures"], 2)
        self.assertEqual(measure["exemplaires"], 1)
        self.assertLess(measure["iou_max"], self.module.IOU_MEME_FORME)
        self.assertFalse(self.module.reference_trop_d_exemplaires(measure, 1))

    def test_a_left_right_pair_counts_two_and_is_accepted_when_two_are_asked(self):
        import numpy as np
        mask = self.canvas()
        boot = np.zeros((300, 200), dtype=np.uint8)
        boot[0:220, 40:120] = 255                                     # shaft
        boot[200:300, 40:200] = 255                                   # foot pointing right
        mask[150:450, 150:350] = boot
        mask[150:450, 550:750] = boot[:, ::-1]                        # its mirror image
        measure = self.module.mesurer_instances(mask)
        self.assertEqual(measure["exemplaires"], 2)
        self.assertTrue(self.module.reference_trop_d_exemplaires(measure, 1))
        self.assertFalse(self.module.reference_trop_d_exemplaires(measure, 2))

    def test_a_single_subject_and_an_empty_matte(self):
        mask = self.canvas()
        mask[100:500, 300:600] = 255
        self.assertEqual(self.module.mesurer_instances(mask)["exemplaires"], 1)
        self.assertEqual(self.module.mesurer_instances(self.canvas())["exemplaires"], 0)


if __name__ == "__main__":
    unittest.main()
