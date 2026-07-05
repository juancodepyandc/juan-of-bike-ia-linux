"""Tests for aurora_3d_mcp — engineer-grade 3D audit tools.

Tests the underlying t_inspect_* functions directly (no MCP transport
needed for the logic). Plus one smoke test that the server module
imports + the tool registry has the expected 7 tools wired."""

from __future__ import annotations

import json
import struct
import sys
import tempfile
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parent))
import aurora_3d_mcp as mcp  # noqa: E402


def _make_minimal_glb(target: Path, *,
                       n_materials: int = 0,
                       has_uv: bool = False,
                       n_animations: int = 0,
                       n_skins: int = 0) -> None:
    """Tiny cube GLB with optional flags so we can probe each audit branch."""
    import numpy as np
    v = np.array([
        [0,0,0],[1,0,0],[1,1,0],[0,1,0],
        [0,0,1],[1,0,1],[1,1,1],[0,1,1],
    ], dtype=np.float32)
    f = np.array([
        [0,1,2],[0,2,3], [4,6,5],[4,7,6],
        [0,4,5],[0,5,1], [2,6,7],[2,7,3],
        [1,5,6],[1,6,2], [0,3,7],[0,7,4],
    ], dtype=np.uint32)

    pos_b = v.tobytes()
    idx_b = f.tobytes()
    pieces = [pos_b, idx_b]
    bin_blob = b"".join(pieces)

    bvs = [
        {"buffer": 0, "byteOffset": 0, "byteLength": len(pos_b)},
        {"buffer": 0, "byteOffset": len(pos_b), "byteLength": len(idx_b)},
    ]
    accs = [
        {"bufferView": 0, "componentType": 5126, "count": 8, "type": "VEC3",
         "min": [0,0,0], "max": [1,1,1]},
        {"bufferView": 1, "componentType": 5125, "count": 36, "type": "SCALAR"},
    ]
    attrs = {"POSITION": 0}
    prim = {"attributes": attrs, "indices": 1, "mode": 4}
    if has_uv:
        uv = np.zeros((8, 2), dtype=np.float32)
        uv_b = uv.tobytes()
        offset = len(bin_blob)
        bvs.append({"buffer": 0, "byteOffset": offset, "byteLength": len(uv_b)})
        accs.append({"bufferView": len(bvs)-1, "componentType": 5126, "count": 8, "type": "VEC2"})
        attrs["TEXCOORD_0"] = len(accs) - 1
        bin_blob += uv_b

    gltf = {
        "asset": {"version": "2.0"},
        "scene": 0, "scenes": [{"nodes": [0]}],
        "nodes": [{"mesh": 0}],
        "meshes": [{"primitives": [prim]}],
        "buffers": [{"byteLength": len(bin_blob)}],
        "bufferViews": bvs,
        "accessors": accs,
    }
    if n_materials:
        gltf["materials"] = [{"name": f"mat_{i}"} for i in range(n_materials)]
        prim["material"] = 0
    if n_animations:
        gltf["animations"] = [{
            "name": f"anim_{i}",
            "samplers": [{"input": 0, "output": 0, "interpolation": "LINEAR"}],
            "channels": [{"sampler": 0, "target": {"node": 0, "path": "rotation"}}],
        } for i in range(n_animations)]
    if n_skins:
        gltf["skins"] = [{"joints": [0]} for _ in range(n_skins)]

    json_blob = json.dumps(gltf, separators=(",", ":")).encode("utf-8")
    json_pad = (4 - (len(json_blob) % 4)) % 4
    json_blob += b" " * json_pad
    bin_pad = (4 - (len(bin_blob) % 4)) % 4
    bin_blob += b"\x00" * bin_pad
    out = bytearray()
    out += b"glTF"
    out += struct.pack("<II", 2, 12 + 8 + len(json_blob) + 8 + len(bin_blob))
    out += struct.pack("<II", len(json_blob), 0x4E4F534A) + json_blob
    out += struct.pack("<II", len(bin_blob), 0x004E4942) + bin_blob
    target.write_bytes(bytes(out))


class GeometryAuditTests(unittest.TestCase):

    def test_cube_reports_single_blob_diagnostic(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "cube.glb"
            _make_minimal_glb(p)
            r = mcp.t_inspect_geometry(str(p))
            self.assertTrue(r["ok"])
            self.assertEqual(r["face_count"], 12)
            self.assertEqual(r["components_disjoint"], 1)
            self.assertEqual(r["parts_in_gltf_meshes_array"], 1)
            self.assertTrue(any("single fused blob" in d for d in r["diagnostics"]))

    def test_missing_file_returns_error(self):
        r = mcp.t_inspect_geometry("/tmp/totally_missing.glb")
        self.assertFalse(r["ok"])


class TextureAuditTests(unittest.TestCase):

    def test_no_material_no_uv_flagged(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "vc.glb"
            _make_minimal_glb(p)
            r = mcp.t_inspect_texture(str(p))
            self.assertTrue(r["ok"])
            self.assertEqual(r["n_materials"], 0)
            self.assertFalse(r["has_uv_map"])
            self.assertTrue(any("no materials defined" in d for d in r["diagnostics"]))
            self.assertTrue(any("no UV map" in d for d in r["diagnostics"]))

    def test_uv_present_no_diagnostic_for_missing_uv(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "uv.glb"
            _make_minimal_glb(p, has_uv=True, n_materials=1)
            r = mcp.t_inspect_texture(str(p))
            self.assertTrue(r["ok"])
            self.assertTrue(r["has_uv_map"])
            self.assertFalse(any("no UV map" in d for d in r["diagnostics"]))


class MotionAuditTests(unittest.TestCase):

    def test_no_animations_flagged(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "static.glb"
            _make_minimal_glb(p)
            r = mcp.t_inspect_motion(str(p))
            self.assertFalse(r["has_animations"])
            self.assertTrue(any("no glTF animations array" in d for d in r["diagnostics"]))

    def test_single_root_channel_flagged_as_rigid_block(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "rigid.glb"
            _make_minimal_glb(p, n_animations=1)
            r = mcp.t_inspect_motion(str(p))
            self.assertTrue(r["has_animations"])
            self.assertTrue(any("rigid block" in d for d in r["diagnostics"]))


class SquashAuditTests(unittest.TestCase):

    def test_humanoid_canonical_compares(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "cube.glb"
            _make_minimal_glb(p)
            # Cube has aspect [1,1,1], humanoid expects [1, 0.3, 0.2] → mismatch
            r = mcp.t_inspect_squash(str(p), expected_kind="humanoid")
            self.assertTrue(r["ok"])
            self.assertEqual(r["expected_kind"], "humanoid")
            self.assertGreater(r["aspect_l1_distance"], 0.6)
            self.assertTrue(any("silhouette mismatch" in d for d in r["diagnostics"]))


class SummarizeQualityTests(unittest.TestCase):

    def test_empty_minimal_cube_grades_low(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "minimal.glb"
            _make_minimal_glb(p)
            r = mcp.t_summarize_quality(str(p), expected_kind="humanoid")
            self.assertTrue(r["ok"])
            self.assertLess(r["engineer_grade"], 70)
            self.assertGreater(len(r["all_issues"]), 3)
            self.assertGreater(len(r["suggested_fixes"]), 0)

    def test_grade_caps_at_100_and_floor_0(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "c.glb"
            _make_minimal_glb(p)
            r = mcp.t_summarize_quality(str(p), expected_kind="generic")
            self.assertGreaterEqual(r["engineer_grade"], 0)
            self.assertLessEqual(r["engineer_grade"], 100)


class ServerWiringTests(unittest.TestCase):

    def test_seven_tools_registered(self):
        names = [t[0] for t in mcp._TOOLS]
        self.assertEqual(len(names), 7)
        self.assertIn("inspect_geometry", names)
        self.assertIn("inspect_texture", names)
        self.assertIn("inspect_anatomy", names)
        self.assertIn("inspect_motion", names)
        self.assertIn("inspect_components", names)
        self.assertIn("inspect_squash", names)
        self.assertIn("summarize_quality", names)

    def test_server_instance_exists(self):
        self.assertIsNotNone(mcp.server)


if __name__ == "__main__":
    unittest.main()
