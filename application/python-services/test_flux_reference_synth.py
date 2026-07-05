import tempfile
import unittest
from pathlib import Path
import sys

from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).resolve().parent))

from flux_reference_synth import (
    MULTIVIEW_SUFFIXES,
    _cleanup_character_reference,
    _human_fidelity_contract,
    _motion_reference_contract,
    _single_view_base_prompt,
    audit_multiview_consistency,
)


class FluxReferenceSynthTests(unittest.TestCase):
    def _character_ref(self, path: Path, *, width: int, color=(32, 16, 16)) -> None:
        img = Image.new("RGB", (256, 256), "white")
        draw = ImageDraw.Draw(img)
        x0 = (256 - width) // 2
        x1 = x0 + width
        draw.rectangle((x0, 18, x1, 244), fill=(232, 226, 214), outline=(16, 16, 16))
        draw.rectangle((x0 + 8, 50, x1 - 8, 130), fill=color)
        draw.ellipse((112, 6, 144, 42), fill=(220, 132, 142), outline=(16, 16, 16))
        draw.line((x0 + 14, 70, x0 - 16, 150), fill=(16, 16, 16), width=6)
        draw.line((x1 - 14, 70, x1 + 16, 150), fill=(16, 16, 16), width=6)
        draw.line((x0 + 20, 130, x0 + 12, 244), fill=(16, 16, 16), width=7)
        draw.line((x1 - 20, 130, x1 - 12, 244), fill=(16, 16, 16), width=7)
        img.save(path)

    def _multi_character_ref(self, path: Path) -> None:
        img = Image.new("RGB", (256, 256), "white")
        draw = ImageDraw.Draw(img)
        for x0 in (24, 102, 180):
            x1 = x0 + 48
            draw.rectangle((x0, 42, x1, 220), fill=(28, 42, 70), outline=(16, 16, 16))
            draw.ellipse((x0 + 12, 12, x0 + 36, 44), fill=(220, 160, 132), outline=(16, 16, 16))
            draw.line((x0 + 12, 82, x0 - 4, 150), fill=(16, 16, 16), width=5)
            draw.line((x1 - 12, 82, x1 + 4, 150), fill=(16, 16, 16), width=5)
            draw.line((x0 + 15, 220, x0 + 10, 248), fill=(16, 16, 16), width=6)
            draw.line((x1 - 15, 220, x1 - 10, 248), fill=(16, 16, 16), width=6)
        img.save(path)

    def test_turnaround_prompt_requires_same_subject_and_pose(self):
        suffix = " ".join(MULTIVIEW_SUFFIXES.values()).lower()
        self.assertIn("same exact requested identity", suffix)
        self.assertIn("hands never in pockets", suffix)
        self.assertIn("no gender swap", suffix)
        self.assertIn("90 degree side view", suffix)
        self.assertIn("one full-body subject only", suffix)
        self.assertIn("no contact sheet", suffix)
        self.assertIn("hands never in pockets", suffix)
        self.assertIn("feet and shoes fully visible", suffix)

    def test_motion_reference_contract_requires_rig_readable_pose(self):
        contract = _motion_reference_contract("danse la Macarena").lower()

        self.assertIn("motion-rig ready source", contract)
        self.assertIn("do not show the requested dance/action", contract)
        self.assertIn("arms", contract)
        self.assertIn("hands", contract)
        self.assertIn("no hands in pockets", contract)

    def test_floss_motion_reference_contract_requires_arm_hand_clearance(self):
        contract = _motion_reference_contract("floss dance complet bras et hanches").lower()

        self.assertIn("motion-rig ready source", contract)
        self.assertIn("expressive arm motion", contract)
        self.assertIn("visible hands", contract)

    def test_human_fidelity_contract_rejects_mannequin_hands(self):
        contract = _human_fidelity_contract(
            "personnage realiste qui danse",
            "character",
            "danse la Macarena avec mains retournees",
        ).lower()

        self.assertIn("high-fidelity human/character contract", contract)
        self.assertIn("stylized mannequin", contract)
        self.assertIn("separate fingers", contract)
        self.assertIn("palm direction", contract)

    def test_floss_human_fidelity_contract_requires_palm_direction(self):
        contract = _human_fidelity_contract(
            "Emmanuel Macron realiste",
            "character",
            "floss dance complet avec poings mains poignets visibles",
        ).lower()

        self.assertIn("photorealistic adult human proportions", contract)
        self.assertIn("palm direction", contract)

    def test_multiview_prompt_sanitizes_sheet_language(self):
        cleaned = _single_view_base_prompt(
            "personnage realiste avec face, profil, dos coherents, costume bleu"
        ).lower()

        self.assertIn("single clean reconstruction view", cleaned)
        self.assertNotIn("face, profil, dos", cleaned)

    def test_character_audit_rejects_three_quarter_side_views(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._character_ref(root / "front.png", width=72)
            self._character_ref(root / "back.png", width=72)
            self._character_ref(root / "left.png", width=92)
            self._character_ref(root / "right.png", width=94)

            report = audit_multiview_consistency(
                {
                    "front": root / "front.png",
                    "back": root / "back.png",
                    "left": root / "left.png",
                    "right": root / "right.png",
                },
                subject_kind="character",
            )

        self.assertFalse(report["ok"])
        self.assertTrue(any("side profile wider" in item for item in report["failures"]))

    def test_character_audit_rejects_near_front_side_views(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._character_ref(root / "front.png", width=80)
            self._character_ref(root / "back.png", width=72)
            self._character_ref(root / "left.png", width=68)
            self._character_ref(root / "right.png", width=66)

            report = audit_multiview_consistency(
                {
                    "front": root / "front.png",
                    "back": root / "back.png",
                    "left": root / "left.png",
                    "right": root / "right.png",
                },
                subject_kind="character",
            )

        self.assertFalse(report["ok"])
        self.assertTrue(any("side profile wider" in item for item in report["failures"]))

    def test_character_motion_audit_rejects_pose_too_closed_for_dance(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for view in ("front", "back", "left", "right"):
                img = Image.new("RGB", (256, 256), "white")
                draw = ImageDraw.Draw(img)
                draw.rectangle((96, 28, 160, 234), fill=(28, 42, 70), outline=(16, 16, 16))
                draw.ellipse((112, 8, 144, 42), fill=(220, 160, 132), outline=(16, 16, 16))
                draw.line((112, 234, 108, 246), fill=(16, 16, 16), width=5)
                draw.line((144, 234, 148, 246), fill=(16, 16, 16), width=5)
                img.save(root / f"{view}.png")

            report = audit_multiview_consistency(
                {view: root / f"{view}.png" for view in ("front", "back", "left", "right")},
                subject_kind="character",
                motion_prompt="danse la Macarena",
            )

        self.assertFalse(report["ok"])
        self.assertTrue(any("motion-ready pose too narrow" in item for item in report["failures"]))
        self.assertTrue(report["motion_requirements"]["requires_arm_clearance"])

    def test_character_audit_rejects_multi_subject_reference_sheets(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._multi_character_ref(root / "front.png")
            self._multi_character_ref(root / "back.png")
            self._multi_character_ref(root / "left.png")
            self._multi_character_ref(root / "right.png")

            report = audit_multiview_consistency(
                {
                    "front": root / "front.png",
                    "back": root / "back.png",
                    "left": root / "left.png",
                    "right": root / "right.png",
                },
                subject_kind="character",
            )

        self.assertFalse(report["ok"])
        self.assertTrue(any("multiple separated subjects" in item for item in report["failures"]))
        self.assertTrue(any("largest subject does not dominate" in item for item in report["failures"]))

    def test_character_audit_rejects_bottom_cropped_subject(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for view in ("front", "back", "left", "right"):
                img = Image.new("RGB", (256, 256), "white")
                draw = ImageDraw.Draw(img)
                draw.rectangle((92, 8, 164, 255), fill=(28, 42, 70), outline=(16, 16, 16))
                draw.ellipse((108, 0, 148, 44), fill=(220, 160, 132), outline=(16, 16, 16))
                img.save(root / f"{view}.png")

            report = audit_multiview_consistency(
                {view: root / f"{view}.png" for view in ("front", "back", "left", "right")},
                subject_kind="character",
            )

        self.assertFalse(report["ok"])
        self.assertTrue(any("touches bottom frame" in item for item in report["failures"]))

    def test_cleanup_removes_pale_reference_sheet_ghosts(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            img = Image.new("RGB", (256, 256), "white")
            draw = ImageDraw.Draw(img)
            draw.rectangle((22, 40, 74, 230), fill=(190, 194, 198))
            draw.rectangle((106, 28, 154, 232), fill=(20, 30, 58))
            draw.ellipse((116, 8, 144, 34), fill=(218, 158, 130))
            draw.rectangle((186, 40, 238, 230), fill=(190, 194, 198))
            path = root / "ghosts.png"
            img.save(path)

            cleanup = _cleanup_character_reference(path)
            metric_report = audit_multiview_consistency(
                {view: path for view in ("front", "back", "left", "right")},
                subject_kind="character",
            )

        self.assertTrue(cleanup["ok"])
        self.assertGreater(cleanup["ghost_pixels_whitened"], 0)
        self.assertLess(metric_report["views"]["front"]["bbox"]["w"], 0.72)


if __name__ == "__main__":
    unittest.main()
