"""Check the geometry audit contract with actual, tiny Blender exports."""

import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


@unittest.skipUnless(shutil.which("blender"), "Blender is required for the geometry integration test")
class BlenderGeometryTests(unittest.TestCase):
    def test_solid_and_open_mesh_have_distinct_audits(self):
        blender = shutil.which("blender")
        auditor = Path(__file__).resolve().parents[1] / "application/python-services/aurora_hunyuan/blender_mesh_auditor.py"
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fixture = root / "fixtures.py"
            fixture.write_text(
                "import bpy, pathlib, sys\n"
                "root = pathlib.Path(sys.argv[-1])\n"
                "bpy.ops.wm.read_factory_settings(use_empty=True)\n"
                "bpy.ops.mesh.primitive_cube_add()\n"
                "bpy.ops.export_scene.gltf(filepath=str(root / 'solid.glb'), export_format='GLB')\n"
                "bpy.ops.object.delete()\n"
                "bpy.ops.mesh.primitive_plane_add()\n"
                "bpy.ops.export_scene.gltf(filepath=str(root / 'open.glb'), export_format='GLB')\n"
            )
            generated = subprocess.run([blender, "--background", "--python", str(fixture), "--", str(root)],
                                       capture_output=True, text=True, timeout=60)
            self.assertEqual(generated.returncode, 0, generated.stdout + generated.stderr)
            reports = {}
            for name in ("solid", "open"):
                report = root / f"{name}.json"
                result = subprocess.run([blender, "--background", "--python", str(auditor), "--",
                                         str(root / f"{name}.glb"), str(report)],
                                        capture_output=True, text=True, timeout=60)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                reports[name] = json.loads(report.read_text())
            print("Measured Blender geometry:", json.dumps(reports, sort_keys=True))
            self.assertEqual(reports["solid"]["non_manifold_edges"], 0)
            self.assertEqual(reports["solid"]["parts_count"], 1)
            self.assertGreater(reports["solid"]["total_faces"], 0)
            self.assertGreater(reports["open"]["non_manifold_edges"], 0)


if __name__ == "__main__":
    unittest.main()
