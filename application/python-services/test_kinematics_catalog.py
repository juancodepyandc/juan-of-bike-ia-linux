"""Tests for the TS -> Python kinematics catalog contract.

WHY: motion_baker._compile_preset_ref() used to hard-code 3 presets
(walk_cycle, run_cycle, idle) and route the other 42 to _compile_custom_pose(),
which emits a single no-op marker keyframe. Every creature / mechanism / vehicle
preset therefore baked an "animated" GLB containing zero motion, and nothing in
the pipeline noticed: the rig existed, the action existed, the GLB exported, and
the perfection gate scored it 100/100.

These tests make that failure mode loud:
  - every preset the parser can emit must compile to at least one REAL
    (non-marker) bone instruction,
  - the catalog must stay in sync with kinematicsLibrary.ts,
  - a multi-segment prompt must be sequenced in time, not superimposed.

Run: python application/python-services/test_kinematics_catalog.py
"""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import motion_baker  # noqa: E402
import motion_parser  # noqa: E402

CATALOG = Path(__file__).resolve().parent / "kinematics_catalog.json"


def _compile_preset(preset_id: str, frame_count: int = 36):
    return motion_baker.compile_motion_payload({
        "schema": "aurora.motion.v1",
        "fps": 24,
        "frame_count": frame_count,
        "primitives": [{"kind": "preset_ref", "source_target": preset_id,
                        "modifiers": {}}],
    })


def _real_instructions(compiled):
    return [i for i in compiled["instructions"] if i.get("channel") != "marker"]


class TestCatalogPresent(unittest.TestCase):
    def test_catalog_file_exists(self):
        self.assertTrue(CATALOG.is_file(),
                        f"{CATALOG} missing — regenerate with "
                        "node --experimental-strip-types "
                        "application/scripts/export-kinematics-catalog.mts")

    def test_catalog_loads_and_is_non_trivial(self):
        presets = motion_baker.load_preset_catalog()
        self.assertGreaterEqual(len(presets), 40,
                                "catalog looks truncated — did the export fail?")

    def test_catalog_covers_every_parser_preset(self):
        """A verb the parser can match but the catalog lacks = silent no-op."""
        parser_ids = {pid for _rx, pid in motion_parser.VERB_TO_PRESET}
        catalog_ids = set(motion_baker.load_preset_catalog())
        missing = sorted(parser_ids - catalog_ids - {"custom.parsed"})
        self.assertEqual(missing, [],
                         f"parser can emit presets absent from the catalog: {missing}")


class TestEveryPresetBakesRealMotion(unittest.TestCase):
    """The regression that matters: no preset may compile to a no-op marker."""

    def test_no_preset_compiles_to_nothing(self):
        dead = []
        for preset_id in sorted({pid for _rx, pid in motion_parser.VERB_TO_PRESET}):
            if not _real_instructions(_compile_preset(preset_id)):
                dead.append(preset_id)
        self.assertEqual(dead, [],
                         f"{len(dead)} preset(s) bake NO real keyframes: {dead}")

    def test_creature_presets_drive_creature_targets(self):
        compiled = _compile_preset("creature.quadruped_walk")
        bones = {i["bone"] for i in _real_instructions(compiled)}
        self.assertTrue(any("front_" in b for b in bones),
                        f"quadruped gait never drives a FRONT limb: {sorted(bones)}")
        self.assertTrue(any(b.startswith(("thigh", "shin")) for b in bones),
                        f"quadruped gait never drives a hind limb: {sorted(bones)}")

    def test_roar_opens_the_jaw(self):
        compiled = _compile_preset("creature.roar")
        bones = {i["bone"] for i in _real_instructions(compiled)}
        self.assertTrue(any("jaw" in b or "teeth" in b for b in bones),
                        f"roar drives no jaw bone: {sorted(bones)}")

    def test_hinge_swing_drives_the_object_root(self):
        """Mechanism targets map to [] on purpose (object root, not a bone)."""
        compiled = _compile_preset("mechanism.hinge_swing")
        bones = {i["bone"] for i in _real_instructions(compiled)}
        self.assertIn("__object_root__", bones)


class TestSequencing(unittest.TestCase):
    def test_two_segments_do_not_overlap(self):
        motion = motion_parser.parse_custom_motion_prompt("il marche puis il rugit")
        self.assertIsNotNone(motion)
        compiled = motion_baker.compile_motion_payload(motion)
        spans = {}
        for ins in _real_instructions(compiled):
            frames = [f for f, _v in ins["samples"]]
            spans.setdefault(ins["source_target"], []).append((min(frames), max(frames)))

        walk = spans.get("legs")
        roar = spans.get("jaw")
        self.assertTrue(walk, "walk segment produced no leg instruction")
        self.assertTrue(roar, "roar segment produced no jaw instruction")
        walk_end = max(e for _s, e in walk)
        roar_start = min(s for s, _e in roar)
        self.assertLess(walk_end, roar_start,
                        f"segments overlap: walk ends {walk_end}, roar starts {roar_start}")

    def test_single_preset_layers_stay_simultaneous(self):
        """roar = chest + head + jaw are LAYERS of one motion, not a sequence."""
        compiled = _compile_preset("creature.roar", frame_count=48)
        starts = {min(f for f, _v in i["samples"]) for i in _real_instructions(compiled)}
        self.assertEqual(starts, {1},
                         f"preset layers were wrongly sequenced: starts={sorted(starts)}")

    def test_sequence_windows_are_weighted_by_duration(self):
        """walk (1.0 s) then roar (2.0 s) must not split the timeline 50/50."""
        motion = motion_parser.parse_custom_motion_prompt("il marche puis il rugit")
        compiled = motion_baker.compile_motion_payload(motion)
        total = compiled["frame_count"]
        legs = [i for i in _real_instructions(compiled) if i["source_target"] == "legs"]
        walk_len = max(max(f for f, _v in i["samples"]) for i in legs)
        self.assertLess(walk_len, total * 0.45,
                        f"walk took {walk_len}/{total} frames; expected ~1/3")


if __name__ == "__main__":
    unittest.main(verbosity=2)
