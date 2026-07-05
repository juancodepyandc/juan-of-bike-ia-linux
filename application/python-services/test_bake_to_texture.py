"""Tests for bake_to_texture — UV-mapped texture baking from vertex colors."""

from __future__ import annotations

import json
import struct
import sys
import tempfile
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parent))
from bake_to_texture import bake  # noqa: E402


def _make_vertex_color_glb(target: Path) -> None:
    """Write a tiny valid GLB: cube with per-vertex RGBA color, no UV / no
    materials. Mirrors what bake_vertex_colors output looks like."""
    import numpy as np
    # 8 vertices of a unit cube, 12 triangles
    v = np.array([
        [0,0,0],[1,0,0],[1,1,0],[0,1,0],
        [0,0,1],[1,0,1],[1,1,1],[0,1,1],
    ], dtype=np.float32)
    f = np.array([
        [0,1,2],[0,2,3], [4,6,5],[4,7,6],
        [0,4,5],[0,5,1], [2,6,7],[2,7,3],
        [1,5,6],[1,6,2], [0,3,7],[0,7,4],
    ], dtype=np.uint32)
    c = np.array([
        [255,0,0,255], [0,255,0,255], [0,0,255,255], [255,255,0,255],
        [255,0,255,255], [0,255,255,255], [255,255,255,255], [128,128,128,255],
    ], dtype=np.uint8)

    # Layout the binary chunk
    pos_bytes = v.tobytes()
    color_bytes = c.tobytes()
    idx_bytes = f.tobytes()
    bin_blob = pos_bytes + color_bytes + idx_bytes

    gltf = {
        "asset": {"version": "2.0"},
        "scene": 0, "scenes": [{"nodes": [0]}],
        "nodes": [{"mesh": 0}],
        "meshes": [{
            "primitives": [{
                "attributes": {"POSITION": 0, "COLOR_0": 1},
                "indices": 2, "mode": 4,
            }],
        }],
        "buffers": [{"byteLength": len(bin_blob)}],
        "bufferViews": [
            {"buffer": 0, "byteOffset": 0, "byteLength": len(pos_bytes)},
            {"buffer": 0, "byteOffset": len(pos_bytes), "byteLength": len(color_bytes)},
            {"buffer": 0, "byteOffset": len(pos_bytes) + len(color_bytes),
             "byteLength": len(idx_bytes)},
        ],
        "accessors": [
            {"bufferView": 0, "componentType": 5126, "count": 8, "type": "VEC3",
             "min": [0.0,0.0,0.0], "max": [1.0,1.0,1.0]},
            {"bufferView": 1, "componentType": 5121, "count": 8, "type": "VEC4",
             "normalized": True},
            {"bufferView": 2, "componentType": 5125, "count": 36, "type": "SCALAR"},
        ],
    }
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


def _read_gltf(glb_path: Path) -> dict:
    with open(glb_path, "rb") as f:
        f.seek(12)
        json_len, _ = struct.unpack("<II", f.read(8))
        return json.loads(f.read(json_len).rstrip(b"\x00"))


class BakeToTextureTests(unittest.TestCase):

    def test_cube_produces_uv_textured_glb(self):
        with tempfile.TemporaryDirectory() as td:
            src = Path(td) / "src.glb"
            dst = Path(td) / "dst.glb"
            _make_vertex_color_glb(src)
            res = bake(src, dst, atlas_size=256)
            self.assertTrue(res["ok"], f"bake failed: {res}")
            self.assertEqual(res["n_faces"], 12)
            self.assertGreater(res["atlas_coverage_pct"], 0.0)
            # Verify the output GLB structure
            gltf = _read_gltf(dst)
            self.assertEqual(len(gltf["materials"]), 1)
            self.assertEqual(len(gltf["textures"]), 1)
            self.assertEqual(len(gltf["images"]), 1)
            prim = gltf["meshes"][0]["primitives"][0]
            self.assertIn("TEXCOORD_0", prim["attributes"])
            self.assertNotIn("COLOR_0", prim["attributes"])
            self.assertIn("baseColorTexture",
                          gltf["materials"][0]["pbrMetallicRoughness"])

    def test_missing_input_returns_ok_false(self):
        with tempfile.TemporaryDirectory() as td:
            res = bake(Path(td) / "nope.glb", Path(td) / "out.glb")
            self.assertFalse(res["ok"])
            self.assertIn("not found", res["error"])

    def test_atlas_size_respected(self):
        with tempfile.TemporaryDirectory() as td:
            src = Path(td) / "src.glb"
            dst = Path(td) / "dst.glb"
            _make_vertex_color_glb(src)
            res = bake(src, dst, atlas_size=512)
            self.assertEqual(res["atlas_size"], 512)


if __name__ == "__main__":
    unittest.main()
