from __future__ import annotations

import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory


sys.path.insert(0, str(Path(__file__).resolve().parent))

from three_d_regression_suite import parse_mesh_map, run_suite  # noqa: E402


class ThreeDRegressionSuiteTests(unittest.TestCase):
    def test_public_domain_lincoln_contract_is_deterministic(self):
        with TemporaryDirectory() as tmp:
            report = run_suite(
                case_ids=["public_domain_known_person_abraham_lincoln"],
                output_dir=tmp,
                run_id="unit_lincoln",
            )

        self.assertTrue(report["ok"])
        case = report["cases"][0]
        self.assertEqual(case["routing"]["pipeline"], "procedural")
        self.assertEqual(case["routing"]["procedural_template"], "historical_person_performer")
        self.assertFalse(case["routing"]["dreamgaussianPreferred"])
        self.assertTrue(case["routing"]["flags"]["known_character"])
        self.assertTrue(case["routing"]["flags"]["human_fidelity"])
        self.assertTrue(case["routing"]["flags"]["hand_fidelity"])
        self.assertIn("front", case["contract"]["required_views"])
        self.assertIn("back", case["contract"]["required_views"])
        self.assertIn("left", case["contract"]["required_views"])
        self.assertIn("right", case["contract"]["required_views"])
        self.assertIn(
            "https://commons.wikimedia.org/wiki/File:Abraham_Lincoln_November_1863.jpg",
            case["reference_policy"]["source_urls"],
        )
        self.assertEqual(case["mesh_audit"]["status"], "skipped")

    def test_mechanical_and_strimer_routes_stay_procedural(self):
        with TemporaryDirectory() as tmp:
            report = run_suite(
                case_ids=["mechanical_belt_drive_motion", "exact_strimer_product"],
                output_dir=tmp,
                run_id="unit_procedural",
            )

        self.assertTrue(report["ok"])
        by_id = {case["id"]: case for case in report["cases"]}
        belt = by_id["mechanical_belt_drive_motion"]["routing"]
        self.assertEqual(belt["pipeline"], "procedural")
        self.assertEqual(belt["procedural_template"], "pulley_belt_system")
        self.assertEqual(belt["system_class"], "belt_drive")
        self.assertTrue(belt["flags"]["kinematic"])
        self.assertTrue(belt["flags"]["cinematic_signal"])

        strimer = by_id["exact_strimer_product"]["routing"]
        self.assertEqual(strimer["pipeline"], "procedural")
        self.assertEqual(strimer["procedural_template"], "strimer_plus_v2_cable")
        self.assertEqual(strimer["system_class"], "pc_cabling")
        self.assertTrue(strimer["flags"]["procedural_cable"])

    def test_humanoid_motion_keeps_human_and_hand_fidelity(self):
        with TemporaryDirectory() as tmp:
            report = run_suite(
                case_ids=["humanoid_motion_hand_fidelity"],
                output_dir=tmp,
                run_id="unit_humanoid",
            )

        self.assertTrue(report["ok"])
        routing = report["cases"][0]["routing"]
        self.assertEqual(routing["pipeline"], "ai_generation")
        self.assertIsNone(routing["procedural_template"])
        self.assertTrue(routing["dreamgaussianPreferred"])
        self.assertTrue(routing["flags"]["human_fidelity"])
        self.assertTrue(routing["flags"]["hand_fidelity"])

    def test_parse_mesh_map_validates_shape(self):
        self.assertEqual(parse_mesh_map(["a=b.glb", "c=C:/tmp/model.glb"]), {
            "a": "b.glb",
            "c": "C:/tmp/model.glb",
        })
        with self.assertRaises(ValueError):
            parse_mesh_map(["missing_separator"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
