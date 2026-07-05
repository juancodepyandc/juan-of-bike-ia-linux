"""Tests for glb_animation_injector — injects glTF animations into GLBs."""

from __future__ import annotations

import json
import struct
import sys
import tempfile
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parent))
from glb_animation_injector import _build_keyframe_floats, inject  # noqa: E402


def _minimal_glb(target_path: Path) -> None:
    """Write a minimal valid GLB with a single empty scene + one node, no
    animations, so we can test injection round-trip."""
    gltf = {
        "asset": {"version": "2.0"},
        "scene": 0,
        "scenes": [{"nodes": [0]}],
        "nodes": [{"name": "root"}],
        "buffers": [{"byteLength": 0}],
    }
    json_blob = json.dumps(gltf, separators=(",", ":")).encode("utf-8")
    json_pad = (4 - (len(json_blob) % 4)) % 4
    json_blob_padded = json_blob + (b" " * json_pad)
    bin_blob = b""
    bin_pad = 0
    bin_blob_padded = bin_blob + (b"\x00" * bin_pad)
    total = 12 + 8 + len(json_blob_padded) + 8 + len(bin_blob_padded)
    out = bytearray()
    out += b"glTF"
    out += struct.pack("<II", 2, total)
    out += struct.pack("<II", len(json_blob_padded), 0x4E4F534A)
    out += json_blob_padded
    out += struct.pack("<II", len(bin_blob_padded), 0x004E4942)
    out += bin_blob_padded
    target_path.write_bytes(bytes(out))


def _read_animations(glb_path: Path) -> list:
    raw = glb_path.read_bytes()
    json_len, json_type = struct.unpack_from("<II", raw, 12)
    body = raw[20:20 + json_len].rstrip(b"\x00")
    return json.loads(body).get("animations") or []


class KeyframeBuildersTests(unittest.TestCase):

    def test_rotate_y_quaternion_count(self):
        times, vals, comp, path, n = _build_keyframe_floats("rotate_y", 4.0, fps=30)
        self.assertEqual(comp, 4)
        self.assertEqual(path, "rotation")
        self.assertEqual(n, 120)
        self.assertEqual(len(times), 120 * 4)         # 120 floats × 4 bytes
        self.assertEqual(len(vals), 120 * 4 * 4)      # 120 quats × 4 floats × 4 bytes

    def test_bob_translation_count(self):
        _, vals, comp, path, n = _build_keyframe_floats("bob", 1.0, fps=30)
        self.assertEqual(comp, 3)
        self.assertEqual(path, "translation")
        self.assertEqual(len(vals), n * 3 * 4)

    def test_breathe_scale_starts_at_one(self):
        _, vals, _, path, _ = _build_keyframe_floats("breathe", 2.0)
        self.assertEqual(path, "scale")
        # First triple unpack — should be very close to 1.0
        first_x = struct.unpack_from("<f", vals, 0)[0]
        self.assertAlmostEqual(first_x, 1.0, places=4)

    def test_unknown_motion_raises(self):
        with self.assertRaises(ValueError):
            _build_keyframe_floats("warp_drive", 1.0)


class InjectionTests(unittest.TestCase):

    def test_injects_one_animation_into_minimal_glb(self):
        with tempfile.TemporaryDirectory() as td:
            src = Path(td) / "src.glb"
            dst = Path(td) / "dst.glb"
            _minimal_glb(src)
            self.assertEqual(_read_animations(src), [])
            res = inject(src, dst, motion_kind="rotate_y", duration=4.0)
            self.assertTrue(res["ok"])
            self.assertEqual(res["animations_now"], 1)
            anims = _read_animations(dst)
            self.assertEqual(len(anims), 1)
            self.assertEqual(anims[0]["name"], "aurora_inject_rotate_y")
            self.assertEqual(anims[0]["channels"][0]["target"]["path"], "rotation")
            self.assertEqual(anims[0]["channels"][0]["target"]["node"], 0)

    def test_each_motion_kind_produces_correct_path(self):
        with tempfile.TemporaryDirectory() as td:
            src = Path(td) / "src.glb"
            _minimal_glb(src)
            for kind, expected_path in (
                ("rotate_y", "rotation"),
                ("bob", "translation"),
                ("breathe", "scale"),
            ):
                dst = Path(td) / f"dst_{kind}.glb"
                res = inject(src, dst, motion_kind=kind, duration=1.0)
                self.assertTrue(res["ok"])
                anims = _read_animations(dst)
                self.assertEqual(anims[0]["channels"][0]["target"]["path"],
                                 expected_path)

    def test_walk_humanoid_falls_back_when_no_bones(self):
        """A minimal GLB has no humanoid bones — walk_humanoid must
        gracefully fall back to single-channel root rotation."""
        with tempfile.TemporaryDirectory() as td:
            src = Path(td) / "src.glb"
            dst = Path(td) / "dst.glb"
            _minimal_glb(src)
            res = inject(src, dst, motion_kind="walk_humanoid", duration=1.0)
            self.assertTrue(res["ok"])
            anims = _read_animations(dst)
            self.assertEqual(len(anims), 1)
            # Fallback uses the rotate_y single-channel path, animation_path stored
            self.assertEqual(anims[0]["channels"][0]["target"]["path"], "rotation")
            # Name reflects the fallback
            self.assertIn("fallback", anims[0]["name"])

    def test_walk_humanoid_drives_8_bones_when_present(self):
        """Synthesize a glTF with full Rigify bone set and verify 8 channels
        target the right nodes (thigh.L/R, shin.L/R, upper_arm.L/R, forearm.L/R)."""
        with tempfile.TemporaryDirectory() as td:
            src = Path(td) / "src.glb"
            dst = Path(td) / "dst.glb"
            gltf = {
                "asset": {"version": "2.0"},
                "scene": 0,
                "scenes": [{"nodes": [0]}],
                "nodes": [
                    {"name": "root"},
                    {"name": "thigh.L"},
                    {"name": "thigh.R"},
                    {"name": "shin.L"},
                    {"name": "shin.R"},
                    {"name": "upper_arm.L"},
                    {"name": "upper_arm.R"},
                    {"name": "forearm.L"},
                    {"name": "forearm.R"},
                    {"name": "MCH-thigh_tweak.L"},   # filtered out
                    {"name": "VIS_shin_ik_pole.L"},  # filtered out
                ],
                "buffers": [{"byteLength": 0}],
            }
            jb = json.dumps(gltf, separators=(",", ":")).encode("utf-8")
            jp = (4 - (len(jb) % 4)) % 4
            jb += b" " * jp
            payload = b"glTF" + struct.pack("<II", 2, 12 + 8 + len(jb) + 8)
            payload += struct.pack("<II", len(jb), 0x4E4F534A) + jb
            payload += struct.pack("<II", 0, 0x004E4942)
            src.write_bytes(payload)

            res = inject(src, dst, motion_kind="walk_humanoid", duration=1.0)
            self.assertTrue(res["ok"])
            self.assertEqual(res["n_channels"], 8)
            self.assertCountEqual(
                res["bones_animated"],
                ["thigh.L", "thigh.R", "shin.L", "shin.R",
                 "upper_arm.L", "upper_arm.R", "forearm.L", "forearm.R"],
            )
            anims = _read_animations(dst)
            self.assertEqual(len(anims[0]["channels"]), 8)
            target_nodes = {ch["target"]["node"] for ch in anims[0]["channels"]}
            # Should hit nodes 1-8, NOT 9 (MCH-tweak) or 10 (VIS_)
            self.assertEqual(target_nodes, {1, 2, 3, 4, 5, 6, 7, 8})

    def test_gear_train_split_rotate_drives_each_root_node(self):
        """v80ak — for a glTF with N top-level scene nodes (mesh_part_split
        output), inject one rotation channel per root node so parts rotate
        independently. Result: motion audit reports zero rigid-block diags."""
        with tempfile.TemporaryDirectory() as td:
            src = Path(td) / "src.glb"
            dst = Path(td) / "dst.glb"
            # Build a glTF with 4 top-level nodes (no meshes, but injection
            # only needs the node graph for rotation channels)
            gltf = {
                "asset": {"version": "2.0"},
                "scene": 0,
                "scenes": [{"nodes": [0, 1, 2, 3]}],
                "nodes": [
                    {"name": "part_0", "translation": [0.5, 0.0, 0.0]},
                    {"name": "part_1", "translation": [-0.5, 0.0, 0.0]},
                    {"name": "part_2", "translation": [0.0, 0.5, 0.0]},
                    {"name": "part_3", "translation": [0.0, -0.5, 0.0]},
                ],
                "buffers": [{"byteLength": 0}],
            }
            jb = json.dumps(gltf, separators=(",", ":")).encode("utf-8")
            jp = (4 - (len(jb) % 4)) % 4
            jb += b" " * jp
            payload = b"glTF" + struct.pack("<II", 2, 12 + 8 + len(jb) + 8)
            payload += struct.pack("<II", len(jb), 0x4E4F534A) + jb
            payload += struct.pack("<II", 0, 0x004E4942)
            src.write_bytes(payload)

            res = inject(src, dst, motion_kind="gear_train_split_rotate", duration=2.0)
            self.assertTrue(res["ok"], f"injection failed: {res}")
            self.assertEqual(res["motion_kind"], "gear_train_split_rotate")
            self.assertEqual(res["n_channels"], 4)
            self.assertEqual(len(res["parts_animated"]), 4)
            anims = _read_animations(dst)
            self.assertEqual(len(anims[0]["channels"]), 4)
            target_nodes = {ch["target"]["node"] for ch in anims[0]["channels"]}
            self.assertEqual(target_nodes, {0, 1, 2, 3})

    def test_invalid_input_returns_ok_false(self):
        with tempfile.TemporaryDirectory() as td:
            src = Path(td) / "junk.glb"
            src.write_bytes(b"not a glb")
            dst = Path(td) / "dst.glb"
            res = inject(src, dst)
            self.assertFalse(res["ok"])
            self.assertIn("not a glb", res["error"])


if __name__ == "__main__":
    unittest.main()
