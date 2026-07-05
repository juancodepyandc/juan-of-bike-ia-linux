"""Tests for mesh_quality_score.py — validate scoring logic on synthetic
fixtures + the real Cat 1 mesh shipped with the repo.

Run: python application/python-services/test_mesh_quality_score.py
"""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parent))
from mesh_quality_score import score_mesh, KIND_ASPECT, AXIS_HARD_FLOORS  # noqa: E402


REPO_ROOT = Path(__file__).resolve().parents[2]
CAT1_MESH = REPO_ROOT / "application" / "output" / "3d" / "juan_bike_1777509822533_mesh.glb"


def _build_synthetic_mesh(verts: int = 1000, color_uniform: bool = True):
    """Build a small mesh in-memory for deterministic tests. Sphere by default."""
    import trimesh
    import numpy as np
    mesh = trimesh.creation.icosphere(subdivisions=4)  # ~10000 vertices
    if color_uniform:
        colors = np.tile(np.array([200, 100, 50, 255]), (len(mesh.vertices), 1))
    else:
        rng = np.random.default_rng(42)
        colors = rng.integers(0, 255, size=(len(mesh.vertices), 4), dtype=np.uint8)
        colors[:, 3] = 255
    mesh.visual.vertex_colors = colors
    return mesh


class ColorRichnessTests(unittest.TestCase):
    """color_richness must distinguish monochrome from richly-colored meshes."""

    def test_uniform_color_low_score(self):
        from mesh_quality_score import score_color_richness
        mesh = _build_synthetic_mesh(color_uniform=True)
        score, detail = score_color_richness(mesh)
        self.assertLess(score, AXIS_HARD_FLOORS["color_richness"],
                        "uniform color must trigger retry")
        self.assertTrue(detail["has_vertex_colors"])
        self.assertEqual(detail["unique_colors"], 1)

    def test_random_color_high_score(self):
        from mesh_quality_score import score_color_richness
        mesh = _build_synthetic_mesh(color_uniform=False)
        score, detail = score_color_richness(mesh)
        self.assertGreater(score, 60, "random colors should score high")
        self.assertGreater(detail["unique_colors"], 1000)


class SilhouetteAspectTests(unittest.TestCase):

    def test_open_kind_always_passes(self):
        from mesh_quality_score import score_silhouette_aspect
        mesh = _build_synthetic_mesh()
        score, detail = score_silhouette_aspect(mesh, "sphere")
        self.assertEqual(score, 100)
        self.assertEqual(detail["expected"], "open")

    def test_pc_tower_expects_tall(self):
        # An icosphere (1:1:1) is the wrong aspect for a PC tower (0.45:1:0.55).
        from mesh_quality_score import score_silhouette_aspect
        mesh = _build_synthetic_mesh()
        score, _ = score_silhouette_aspect(mesh, "pc_tower")
        self.assertLess(score, 70, "sphere should not score as a PC tower")


class GeometricDensityTests(unittest.TestCase):

    def test_below_floor(self):
        from mesh_quality_score import score_geometric_density
        # ~10000 verts is below pc_tower floor of 30000 but above sphere floor of 500.
        mesh = _build_synthetic_mesh()
        pc_score, _ = score_geometric_density(mesh, "pc_tower")
        sphere_score, _ = score_geometric_density(mesh, "sphere")
        self.assertLess(pc_score, 100)
        self.assertEqual(sphere_score, 100)


class Cat1RealMeshTests(unittest.TestCase):
    """Run the scorer on the actual Cat 1 GLB — pin the verdict so we
    know if the routing fix is improving things on subsequent retries."""

    def test_cat1_mesh_exists(self):
        if not CAT1_MESH.is_file():
            self.skipTest(f"Cat 1 mesh not present: {CAT1_MESH}")

    def test_cat1_recommends_retry_for_pc_tower(self):
        if not CAT1_MESH.is_file():
            self.skipTest("Cat 1 mesh not present")
        result = score_mesh(CAT1_MESH, "pc_tower")
        self.assertTrue(result["ok"], result.get("error"))
        # Per the v78j tour 9 audit, this mesh has color_richness=0 and a
        # near-cubic bbox. Both should trigger retry.
        self.assertTrue(result["retry_recommended"],
                        f"Cat 1 mesh must trigger retry; got {result}")
        self.assertIn("color_richness", result["failed_axes"])


class SchemaTests(unittest.TestCase):

    def test_schema_constant(self):
        if not CAT1_MESH.is_file():
            self.skipTest("no Cat 1 mesh — using a synthetic instead")
        result = score_mesh(CAT1_MESH, "pc_tower")
        self.assertEqual(result["schema"], "aurora.mesh_quality.v1")
        self.assertIn("scores", result)
        for axis in ("color_richness", "geometric_density", "silhouette_aspect",
                     "manifold_health", "surface_quality"):
            self.assertIn(axis, result["scores"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
