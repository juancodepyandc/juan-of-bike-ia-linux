"""Tests for mesh_part_split — k-means clustering split with material preservation."""

from __future__ import annotations

import json
import struct
import sys
import tempfile
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parent))
from mesh_part_split import _kmeans_lloyd, split  # noqa: E402


def _make_textured_glb(target: Path) -> None:
    """Cube with UV coords and a 1×1 PNG embedded as the baseColorTexture.
    Mimics what bake_to_texture produces."""
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
    uv = np.array([
        [0,0],[1,0],[1,1],[0,1], [0,0],[1,0],[1,1],[0,1],
    ], dtype=np.float32)

    pos_b = v.tobytes()
    uv_b  = uv.tobytes()
    idx_b = f.tobytes()
    # Tiny 1x1 PNG (red, opaque). Hand-crafted minimal valid PNG.
    png_bytes = bytes.fromhex(
        "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c489"
        "0000000d49444154789c63f8cf80010000600d2c1d4b9b0000000049454e44ae426082"
    )
    bin_blob = pos_b + uv_b + idx_b + png_bytes

    pos_off = 0
    uv_off  = len(pos_b)
    idx_off = uv_off + len(uv_b)
    img_off = idx_off + len(idx_b)

    gltf = {
        "asset": {"version": "2.0"},
        "scene": 0, "scenes": [{"nodes": [0]}],
        "nodes": [{"mesh": 0}],
        "meshes": [{
            "primitives": [{
                "attributes": {"POSITION": 0, "TEXCOORD_0": 1},
                "indices": 2, "material": 0, "mode": 4,
            }],
        }],
        "materials": [{
            "name": "src_mat",
            "pbrMetallicRoughness": {
                "baseColorTexture": {"index": 0, "texCoord": 0},
                "metallicFactor": 0.0, "roughnessFactor": 0.85,
            },
        }],
        "textures": [{"sampler": 0, "source": 0}],
        "samplers": [{"magFilter": 9729, "minFilter": 9987,
                      "wrapS": 10497, "wrapT": 10497}],
        "images": [{"bufferView": 3, "mimeType": "image/png"}],
        "accessors": [
            {"bufferView": 0, "componentType": 5126, "count": 8, "type": "VEC3",
             "min": [0,0,0], "max": [1,1,1]},
            {"bufferView": 1, "componentType": 5126, "count": 8, "type": "VEC2"},
            {"bufferView": 2, "componentType": 5125, "count": 36, "type": "SCALAR"},
        ],
        "bufferViews": [
            {"buffer": 0, "byteOffset": pos_off, "byteLength": len(pos_b)},
            {"buffer": 0, "byteOffset": uv_off,  "byteLength": len(uv_b)},
            {"buffer": 0, "byteOffset": idx_off, "byteLength": len(idx_b)},
            {"buffer": 0, "byteOffset": img_off, "byteLength": len(png_bytes)},
        ],
        "buffers": [{"byteLength": len(bin_blob)}],
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


class KMeansTests(unittest.TestCase):

    def test_lloyd_on_two_clear_clusters_finds_them(self):
        import numpy as np
        rng = np.random.default_rng(0)
        a = rng.normal(loc=[0, 0, 0], scale=0.05, size=(50, 3))
        b = rng.normal(loc=[5, 5, 5], scale=0.05, size=(50, 3))
        pts = np.vstack([a, b]).astype(np.float32)
        labels, centroids = _kmeans_lloyd(pts, k=2, n_iter=10, seed=42)
        # Both centroids should be near [0,0,0] and [5,5,5] in some order
        d = sorted(np.linalg.norm(centroids - np.array([[0,0,0],[5,5,5]]), axis=1))
        self.assertLess(d[0], 0.5)
        # First-half labels should agree among themselves, same for second-half
        self.assertEqual(len(set(labels[:50])), 1)
        self.assertEqual(len(set(labels[50:])), 1)


class SplitTests(unittest.TestCase):

    def test_textured_cube_splits_into_k_parts_preserving_texture(self):
        with tempfile.TemporaryDirectory() as td:
            src = Path(td) / "src.glb"
            dst = Path(td) / "dst.glb"
            _make_textured_glb(src)
            res = split(src, dst, k=2)
            self.assertTrue(res["ok"], f"split failed: {res}")
            self.assertEqual(res["parts_produced"], 2)
            self.assertTrue(res["uv_preserved"])
            gltf = _read_gltf(dst)
            self.assertEqual(len(gltf["meshes"]), 2)
            self.assertEqual(len(gltf["nodes"]), 2)
            # Each node has its own translation (cluster centroid)
            for node in gltf["nodes"]:
                self.assertIn("translation", node)
            # Material/texture/image carried across
            self.assertEqual(len(gltf["materials"]), 1)
            self.assertEqual(len(gltf["textures"]), 1)
            self.assertEqual(len(gltf["images"]), 1)
            for mesh in gltf["meshes"]:
                self.assertIn("material", mesh["primitives"][0])

    def test_missing_input(self):
        with tempfile.TemporaryDirectory() as td:
            res = split(Path(td) / "nope.glb", Path(td) / "out.glb", k=4)
            self.assertFalse(res["ok"])
            self.assertIn("not found", res["error"])

    def test_too_few_vertices(self):
        with tempfile.TemporaryDirectory() as td:
            src = Path(td) / "src.glb"
            dst = Path(td) / "dst.glb"
            _make_textured_glb(src)
            # Cube has 8 vertices; k=20 should fail clean
            res = split(src, dst, k=20)
            self.assertFalse(res["ok"])
            self.assertIn("too few vertices", res["error"])


if __name__ == "__main__":
    unittest.main()
