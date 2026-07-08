"""Battery of tests for anim_metrics.py — one PASS and one FAIL fixture per
metric, on synthetic deformed-scene takes (no Blender). Also checks the
type->family dispatch and that a failure surfaces the right correction knob.

Run: application/.venv/bin/python application/python-services/test_anim_metrics.py
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import anim_metrics as AM  # noqa: E402


def _rigid_line_take(scale=1.0):
    """3-vertex line, F frames, rigidly translated (no deformation)."""
    rest = np.array([[0, 0, 0], [1, 0, 0], [2, 0, 0]], float) * scale
    F = 4
    verts = np.stack([rest + np.array([i * 0.1, 0, 0]) for i in range(F)], axis=0)
    return {"fps": 24, "verts": verts, "rest": rest,
            "edges": np.array([[0, 1], [1, 2]])}


# ---------------------------------------------------------------------------
class EdgeStretchTests(unittest.TestCase):
    def test_clean_passes(self):
        r = AM.m_edge_stretch(_rigid_line_take())
        self.assertTrue(r["passed"], r)
        self.assertLess(r["value"], 1.5)

    def test_tear_fails_and_recommends_smoothing(self):
        t = _rigid_line_take()
        t["verts"][2, 2] = [4, 0, 0]  # edge 1-2 doubles -> strain 2
        r = AM.m_edge_stretch(t)
        self.assertFalse(r["passed"], r)
        self.assertEqual(r["knob"]["param"], "weight_smooth_iterations")


# ---------------------------------------------------------------------------
class FootGroundTests(unittest.TestCase):
    H = 1.8

    def _base(self, foot_z):
        rest = np.array([[0, 0, 0], [0, 0, self.H]], float)
        F = len(foot_z)
        joints = {
            "toe.L": np.stack([np.zeros(F), np.zeros(F), foot_z], axis=1),
            "heel.L": np.stack([np.zeros(F), np.zeros(F), foot_z + 0.02], axis=1),
            "ankle.L": np.stack([np.zeros(F), np.zeros(F), foot_z + 0.08], axis=1),
        }
        return {"fps": 24, "rest": rest, "ground": 0.0, "joints": joints, "up_axis": "Z"}

    def test_grounded_passes(self):
        r = AM.m_foot_ground(self._base(np.array([0.4, 0.2, 0.005, 0.2])))
        self.assertTrue(r["passed"], r)

    def test_floating_fails(self):
        r = AM.m_foot_ground(self._base(np.array([0.30, 0.32, 0.31, 0.30])))
        self.assertFalse(r["passed"], r)
        self.assertEqual(r["knob"]["param"], "foot_ik_lock")

    def test_penetration_fails(self):
        r = AM.m_foot_ground(self._base(np.array([0.2, -0.09, 0.2, 0.1])))
        self.assertFalse(r["passed"], r)
        self.assertLess(r["detail"]["max_penetration_norm"], 0)


# ---------------------------------------------------------------------------
class HeelToeRollTests(unittest.TestCase):
    def _take(self, heel_z, toe_z):
        F = len(heel_z)
        ankle_z = np.linspace(0.0, 0.3, F)  # median split -> lower half = stance
        j = {
            "heel.L": np.stack([np.zeros(F), np.zeros(F), heel_z], axis=1),
            "toe.L": np.stack([np.zeros(F), np.zeros(F), toe_z], axis=1),
            "ankle.L": np.stack([np.zeros(F), np.zeros(F), ankle_z], axis=1),
        }
        return {"fps": 24, "joints": j, "up_axis": "Z", "rest": np.zeros((2, 3))}

    def test_natural_roll_passes(self):
        # heel high early (heel-strike), toe high early then heel rises -> toe-heel
        # decreasing monotonically across stance
        heel = np.array([0.05, 0.02, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0])
        toe = np.array([0.10, 0.05, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0])
        r = AM.m_heel_toe_roll(self._take(heel, toe))
        self.assertTrue(r["passed"], r)

    def test_flat_foot_fails(self):
        z = np.zeros(8)
        r = AM.m_heel_toe_roll(self._take(z.copy(), z.copy()))
        self.assertFalse(r["passed"], r)
        self.assertEqual(r["knob"]["param"], "ankle_pitch_amplitude")


# ---------------------------------------------------------------------------
class ContralateralArmSwingTests(unittest.TestCase):
    def _take(self, arm_gain):
        t = np.linspace(0, 2 * np.pi, 24, endpoint=False)
        leg = 20 * np.sin(t)
        arm = arm_gain * np.sin(t)  # negative gain = anti-phase (natural)
        return {"fps": 24, "signals": {"thigh.R": leg, "arm.R": arm,
                                        "thigh.L": -leg, "arm.L": -arm}}

    def test_anti_phase_passes(self):
        r = AM.m_contralateral_arm_swing(self._take(-20))
        self.assertTrue(r["passed"], r)

    def test_in_phase_fails(self):
        r = AM.m_contralateral_arm_swing(self._take(+20))
        self.assertFalse(r["passed"], r)
        self.assertIn("phase", r["knob"]["param"])

    def test_flat_arm_fails_amplitude(self):
        r = AM.m_contralateral_arm_swing(self._take(-2))  # amp 4 deg < 8
        self.assertFalse(r["passed"], r)
        self.assertFalse(r["detail"]["amplitude_ok"])


# ---------------------------------------------------------------------------
class HeadCarriageTests(unittest.TestCase):
    def _take(self, tilt_deg, bob):
        F = 20
        neck = np.tile([0, 0, 1.5], (F, 1)).astype(float)
        a = np.radians(tilt_deg)
        head = neck + np.stack([np.full(F, 0.2 * np.sin(a)),
                                np.zeros(F),
                                0.2 * np.cos(a) + bob * np.sin(np.linspace(0, 6, F))], axis=1)
        return {"fps": 24, "joints": {"head": head, "neck": neck},
                "rest": np.array([[0, 0, 0], [0, 0, 1.8]], float),
                "shoulder_width": 0.4}

    def test_upright_passes(self):
        r = AM.m_head_carriage(self._take(2.0, 0.005))
        self.assertTrue(r["passed"], r)

    def test_tilted_bobbing_fails(self):
        r = AM.m_head_carriage(self._take(22.0, 0.12))
        self.assertFalse(r["passed"], r)
        self.assertEqual(r["knob"]["param"], "head_stabilization_gain")


# ---------------------------------------------------------------------------
def _two_capsule_take(gap):
    """Two vertical bar parts separated along x by `gap`, F frames static."""
    rng = np.random.default_rng(1)
    bar0 = rng.normal([0, 0, 0.5], [0.05, 0.05, 0.4], size=(40, 3))
    bar1 = rng.normal([gap, 0, 0.5], [0.05, 0.05, 0.4], size=(40, 3))
    rest = np.vstack([bar0, bar1])
    verts = np.stack([rest] * 3, axis=0)
    labels = np.array([0] * 40 + [1] * 40)
    return {"fps": 24, "verts": verts, "rest": rest, "part_labels": labels}


class SelfIntersectionTests(unittest.TestCase):
    def test_separated_passes(self):
        r = AM.m_self_intersection(_two_capsule_take(gap=1.0))
        self.assertTrue(r["passed"], r)

    def test_overlap_fails(self):
        r = AM.m_self_intersection(_two_capsule_take(gap=0.02))
        self.assertFalse(r["passed"], r)
        self.assertEqual(r["knob"]["param"], "self_collision_push")


# ---------------------------------------------------------------------------
class HandFlexionTests(unittest.TestCase):
    def _straight_finger(self, F=6):
        base = np.array([0, 0, 0.0])
        pts = [np.tile(base + np.array([0, 0, i * 0.03]), (F, 1)) for i in range(4)]
        return pts

    def _zigzag_finger(self, F=6):
        # segments bend +y then -y then +y -> cross products flip -> unnatural
        p0 = np.tile([0, 0, 0.0], (F, 1)).astype(float)
        p1 = np.tile([0, 0.03, 0.03], (F, 1)).astype(float)
        p2 = np.tile([0, 0.0, 0.06], (F, 1)).astype(float)
        p3 = np.tile([0, 0.03, 0.09], (F, 1)).astype(float)
        return [p0, p1, p2, p3]

    def test_natural_hand_passes(self):
        chains = {f"{n}.R": self._straight_finger() for n in ("index", "middle", "ring")}
        r = AM.m_hand_flexion({"finger_chains": chains})
        self.assertTrue(r["passed"], r)

    def test_broken_finger_fails(self):
        chains = {"index.R": self._zigzag_finger(), "middle.R": self._zigzag_finger()}
        r = AM.m_hand_flexion({"finger_chains": chains})
        self.assertFalse(r["passed"], r)
        self.assertEqual(r["knob"]["param"], "finger_curl_gradation")


# ---------------------------------------------------------------------------
class FingerSpreadTests(unittest.TestCase):
    def _finger(self, angle_deg, F=4):
        a = np.radians(angle_deg)
        d = np.array([np.cos(a), np.sin(a), 0.0]) * 0.04
        p0 = np.tile([0, 0, 0], (F, 1)).astype(float)
        p1 = np.tile(d, (F, 1))
        p2 = np.tile(2 * d, (F, 1))
        p3 = np.tile(3 * d, (F, 1))
        return [p0, p1, p2, p3]

    def test_narrow_passes(self):
        chains = {"index.R": self._finger(0), "middle.R": self._finger(8)}
        r = AM.m_finger_spread({"finger_chains": chains})
        self.assertTrue(r["passed"], r)

    def test_splayed_fails(self):
        chains = {"index.R": self._finger(0), "middle.R": self._finger(40)}
        r = AM.m_finger_spread({"finger_chains": chains})
        self.assertFalse(r["passed"], r)
        self.assertEqual(r["knob"]["param"], "finger_abduction_clamp")


# ---------------------------------------------------------------------------
def _rot_z(theta):
    c, s = np.cos(theta), np.sin(theta)
    return np.array([[c, -s, 0], [s, c, 0], [0, 0, 1.0]])


class PartRigidityTests(unittest.TestCase):
    def _cube(self):
        rng = np.random.default_rng(2)
        return rng.normal(0, 0.2, size=(30, 3)) + np.array([1.0, 0, 0.5])

    def test_rigid_rotation_passes(self):
        cube = self._cube()
        frames = [cube @ _rot_z(np.radians(a)).T for a in (0, 10, 20, 30)]
        rest = frames[0]
        verts = np.stack(frames, axis=0)
        take = {"fps": 24, "verts": verts, "rest": rest,
                "part_labels": np.zeros(len(cube), int)}
        r = AM.m_part_rigidity(take)
        self.assertTrue(r["passed"], r)

    def test_soft_scale_fails(self):
        cube = self._cube()
        frames = [cube * s for s in (1.0, 1.2, 1.5, 1.8)]  # non-rigid scaling
        take = {"fps": 24, "verts": np.stack(frames, axis=0), "rest": frames[0],
                "part_labels": np.zeros(len(cube), int)}
        r = AM.m_part_rigidity(take)
        self.assertFalse(r["passed"], r)
        self.assertEqual(r["knob"]["param"], "max_bone_influences")


# ---------------------------------------------------------------------------
class JointCoherenceTests(unittest.TestCase):
    def _two_parts(self, rotate_B):
        rng = np.random.default_rng(3)
        A = rng.normal([0, 0, 0], 0.2, size=(30, 3))
        B0 = rng.normal([1, 0, 0], 0.2, size=(30, 3))
        rest = np.vstack([A, B0])
        labels = np.array([0] * 30 + [1] * 30)
        frames = []
        for f, R in enumerate(rotate_B):
            Bf = (B0 - B0.mean(0)) @ R.T + B0.mean(0)
            frames.append(np.vstack([A, Bf]))
        return {"fps": 24, "verts": np.stack(frames, 0), "rest": rest,
                "part_labels": labels, "joint_parts": [(0, 1)]}

    def test_fixed_axis_passes(self):
        rots = [_rot_z(np.radians(a)) for a in (0, 8, 16, 24, 32)]
        r = AM.m_joint_coherence(self._two_parts(rots))
        self.assertTrue(r["passed"], r)

    def test_wandering_axis_fails(self):
        rx = lambda a: np.array([[1, 0, 0], [0, np.cos(a), -np.sin(a)],
                                 [0, np.sin(a), np.cos(a)]])
        rots = [np.eye(3), _rot_z(np.radians(20)), rx(np.radians(25)),
                _rot_z(np.radians(-15)), rx(np.radians(30))]
        r = AM.m_joint_coherence(self._two_parts(rots))
        self.assertFalse(r["passed"], r)
        self.assertIn("pivot_lock", r["knob"]["param"])


# ---------------------------------------------------------------------------
class FloatingPartTests(unittest.TestCase):
    def _take(self, centroid_path):
        F = len(centroid_path)
        glove = np.random.default_rng(4).normal(0, 0.05, size=(20, 3))
        verts = np.stack([glove + centroid_path[f] for f in range(F)], axis=0)
        rest = np.vstack([verts[0], verts[0] + np.array([2, 2, 2])])  # give a scale
        return {"fps": 24, "verts": verts, "rest": rest,
                "floating_parts": {"glove.L": {"verts_idx": list(range(20))}}}

    def test_smooth_follow_passes(self):
        t = np.linspace(0, 2 * np.pi, 24)
        path = np.stack([0.1 * np.sin(t), np.zeros(24), 0.1 * np.cos(t)], axis=1)
        r = AM.m_floating_part_stability(self._take(path))
        self.assertTrue(r["passed"], r)

    def test_jitter_fails(self):
        rng = np.random.default_rng(5)
        path = rng.normal(0, 1.0, size=(24, 3))  # violent random jumps
        r = AM.m_floating_part_stability(self._take(path))
        self.assertFalse(r["passed"], r)
        self.assertEqual(r["knob"]["param"], "float_follow_damping")


# ---------------------------------------------------------------------------
class ScreenFaceTests(unittest.TestCase):
    def _feat(self, uv, present=None):
        return {"uv": np.asarray(uv, float),
                "present": np.asarray(present, bool) if present is not None else None}

    def test_coherent_face_passes(self):
        F = 20
        eyeL = self._feat(np.tile([0.3, 0.6], (F, 1)))
        eyeR = self._feat(np.tile([0.7, 0.6], (F, 1)))
        mouth = self._feat(np.tile([0.5, 0.3], (F, 1)))
        r = AM.m_screen_face_coherence({"screen_features":
                                        {"eye.L": eyeL, "eye.R": eyeR, "mouth": mouth}})
        self.assertTrue(r["passed"], r)

    def test_feature_leaves_screen_fails(self):
        F = 20
        uv = np.tile([0.3, 0.6], (F, 1))
        uv[5:15, 0] = 1.6  # eye slides off the right edge for 10 frames
        eyeL = self._feat(uv)
        r = AM.m_screen_face_coherence({"screen_features": {"eye.L": eyeL}})
        self.assertFalse(r["passed"], r)
        self.assertIn("screen", r["knob"]["param"])

    def test_feature_vanishes_fails(self):
        F = 20
        present = np.ones(F, bool)
        present[6:12] = False  # mouth gone for 6 frames = permanent dropout
        mouth = self._feat(np.tile([0.5, 0.3], (F, 1)), present)
        r = AM.m_screen_face_coherence({"screen_features": {"mouth": mouth}})
        self.assertFalse(r["passed"], r)


# ---------------------------------------------------------------------------
class LuminousTests(unittest.TestCase):
    F = 48

    def test_temporal_smoothness_passes(self):
        t = np.linspace(0, 4 * np.pi, self.F)
        em = 0.5 + 0.4 * np.sin(t)[:, None] * np.ones((1, 8))
        r = AM.m_temporal_smoothness({"fps": 24, "emission": em})
        self.assertTrue(r["passed"], r)

    def test_temporal_smoothness_jerky_fails(self):
        em = np.tile(np.array([0.0, 1.0])[np.newaxis].repeat(1, 0).ravel(), self.F // 2)
        em = np.resize(np.array([0.0, 1.0]), self.F)[:, None] * np.ones((1, 8))
        r = AM.m_temporal_smoothness({"fps": 24, "emission": em})
        self.assertFalse(r["passed"], r)
        self.assertEqual(r["knob"]["param"], "emission_smoothing_frames")

    def test_pulsation_periodic_passes(self):
        t = np.arange(self.F)
        em = (0.5 + 0.4 * np.sin(2 * np.pi * t / 8.0))[:, None] * np.ones((1, 6))
        r = AM.m_pulsation_coherence({"fps": 24, "emission": em, "pattern": "breathing"})
        self.assertTrue(r["passed"], r)

    def test_pulsation_random_fails(self):
        em = np.random.default_rng(6).random((self.F, 6))
        r = AM.m_pulsation_coherence({"fps": 24, "emission": em, "pattern": "breathing"})
        self.assertFalse(r["passed"], r)
        self.assertEqual(r["knob"]["param"], "pulse_period_lock")

    def test_flicker_smooth_passes(self):
        t = np.linspace(0, 4 * np.pi, self.F)
        em = (0.5 + 0.4 * np.sin(t))[:, None] * np.ones((1, 6))
        r = AM.m_flicker({"fps": 24, "emission": em})
        self.assertTrue(r["passed"], r)

    def test_flicker_dropouts_fail(self):
        t = np.linspace(0, 4 * np.pi, self.F)
        em = (0.5 + 0.4 * np.sin(t))[:, None] * np.ones((1, 6))
        em[10, :] = 0.0  # single-frame blackout on every LED
        em[20, 2] = 0.0
        r = AM.m_flicker({"fps": 24, "emission": em})
        self.assertFalse(r["passed"], r)
        self.assertGreater(r["detail"]["single_frame_dropouts"], 0)

    def test_dynamic_range_static_fails(self):
        em = np.full((self.F, 6), 0.5)
        r = AM.m_emission_dynamic_range({"fps": 24, "emission": em, "pattern": "breathing"})
        self.assertFalse(r["passed"], r)
        self.assertEqual(r["knob"]["param"], "pattern_amplitude")

    def test_dynamic_range_static_color_ok(self):
        em = np.full((self.F, 6), 0.5)
        r = AM.m_emission_dynamic_range({"fps": 24, "emission": em, "pattern": "static_color"})
        self.assertTrue(r["passed"], r)


# ---------------------------------------------------------------------------
class DispatchTests(unittest.TestCase):
    def test_family_for_intent(self):
        cases = {
            "led_emission": "luminous",
            "oled_screen": "screen",
            "mechanical_simple": "mecha_rigid",
            "rigid_static": "mecha_rigid",
            "fan_pwm": "mecha_rigid",
        }
        for cat, fam in cases.items():
            self.assertEqual(AM.family_for_intent({"category": cat}), fam, cat)
        self.assertEqual(AM.family_for_intent(
            {"category": "creature_organic", "creature_anim": {"locomotion": "humanoid"}}),
            "humanoid")
        self.assertEqual(AM.family_for_intent(
            {"category": "creature_organic", "creature_anim": {"locomotion": "serpent"}}),
            "creature")

    def test_evaluate_humanoid_tear_surfaces_knob(self):
        t = _rigid_line_take()
        t["verts"][2, 2] = [4, 0, 0]
        rep = AM.evaluate(t, "humanoid")
        self.assertIn("edge_stretch", rep["failed_metrics"])
        self.assertTrue(any(k["metric"] == "edge_stretch" for k in rep["knobs"]))
        self.assertFalse(rep["passed"])

    def test_evaluate_caine_hybrid_runs_screen(self):
        # a creature take with a screen face -> add_screen pulls in the screen metric
        t = _two_capsule_take(gap=1.0)
        F = 20
        t["floating_parts"] = {"glove.L": {"verts_idx": list(range(5))}}
        t["screen_features"] = {"eye.L": {"uv": np.tile([0.3, 0.6], (F, 1)), "present": None}}
        rep = AM.evaluate(t, "creature", add_screen=True)
        self.assertIn("screen_face_coherence", [r["metric"] for r in rep["results"]])

    def test_thresholds_and_knobs_aligned(self):
        self.assertEqual(AM._self_test(), 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
