"""No production module may reference a global name that nothing defines.

When the bridge was split into route modules, names that used to be module globals of
`bridge_server.py` (`_python_jobs`, `_run_python_job`, `_uuid`, `quote`, ...) stayed in the moved
code without an import. Python only notices at call time: every video or voice job answered
HTTP 500 with a NameError while the server looked healthy. This test reads the source of each
production module with the standard library only, so it runs on every CI platform without the
application's heavy dependencies.
"""
from __future__ import annotations

import ast
import builtins
import symtable
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

MODULE_ATTRIBUTES = {
    "__file__", "__name__", "__doc__", "__builtins__", "__spec__", "__package__", "__loader__",
    "__path__", "__debug__", "__annotations__", "__dict__", "__class__", "__qualname__", "__module__",
    "__cached__", "__all__",
}

# Every Python file under these locations is production code reached by the bridge, the missions
# or the MCP hub. Vendored trees and generated copies are not part of the contract.
SCOPES = (
    ("application", ("*.py",)),
    ("application/routes", ("*.py",)),
    ("agi_core", ("*.py",)),
    ("mcp", ("hub.py",)),
)

# Engines the product calls directly. Listed by name because python-services also holds vendored
# code and one-off scripts that this test does not vouch for.
ENGINE_MODULES = (
    "application/python-services/aurora_3d_pipeline.py",
    "application/python-services/motion_intent_bpy_runner.py",
    "application/python-services/motion_intent_classifier.py",
    "application/python-services/mia_mocap_retarget.py",
    "application/python-services/universal_anatomical_rig_engine.py",
    "application/python-services/voice_service.py",
    "application/python-services/character_research.py",
    "application/python-services/perfection_gate.py",
    "application/python-services/livraison_organisee.py",
    "application/python-services/pipeline_delivery.py",
    "application/python-services/mesh_taubin.py",
    "application/python-services/photo_rectifier.py",
    "application/python-services/reference_visual_search.py",
    "application/python-services/lecture_demande.py",
    "application/python-services/articulated_motion.py",
    "application/python-services/motion_intent_baker.py",
)


def undefined_global_names(source: str, filename: str = "<source>") -> set[str]:
    """Names read as globals that no module-level binding, `global` assignment or builtin provides."""
    tree = ast.parse(source, filename)
    if any(isinstance(node, ast.ImportFrom) and any(alias.name == "*" for alias in node.names)
           for node in ast.walk(tree)):
        raise ValueError(f"{filename}: a star import hides which names exist; import them explicitly")
    top = symtable.symtable(source, filename, "exec")
    bound = set(dir(builtins)) | MODULE_ATTRIBUTES

    def tables(table):
        yield table
        for child in table.get_children():
            yield from tables(child)

    for symbol in top.get_symbols():
        if symbol.is_assigned() or symbol.is_imported() or symbol.is_namespace():
            bound.add(symbol.get_name())
    for table in tables(top):
        if table is top:
            continue
        for symbol in table.get_symbols():
            if symbol.is_declared_global() and (symbol.is_assigned() or symbol.is_imported()
                                                or symbol.is_namespace()):
                bound.add(symbol.get_name())

    missing: set[str] = set()
    for symbol in top.get_symbols():
        if symbol.is_referenced() and symbol.get_name() not in bound:
            missing.add(symbol.get_name())
    for table in tables(top):
        if table is top:
            continue
        for symbol in table.get_symbols():
            if symbol.is_referenced() and symbol.is_global() and symbol.get_name() not in bound:
                missing.add(symbol.get_name())
    return missing


def production_files() -> list[Path]:
    files: set[Path] = set()
    for folder, patterns in SCOPES:
        for pattern in patterns:
            files.update(path for path in (ROOT / folder).glob(pattern) if path.is_file() and not path.is_symlink())
    files.update(ROOT / name for name in ENGINE_MODULES)
    return sorted(files)


class NoUndefinedNames(unittest.TestCase):
    def test_the_checker_sees_a_missing_global_and_accepts_a_defined_one(self):
        # A checker that could never fail would prove nothing: it must flag the exact defect it guards.
        broken = (
            "import threading\n"
            "def create_job(payload):\n"
            "    job_id = _uuid.uuid4().hex\n"
            "    with _python_jobs_lock:\n"
            "        _python_jobs[job_id] = payload\n"
            "    return job_id\n"
        )
        self.assertEqual(undefined_global_names(broken), {"_uuid", "_python_jobs_lock", "_python_jobs"})
        fixed = (
            "import threading\nimport uuid as _uuid\n"
            "_python_jobs = {}\n_python_jobs_lock = threading.Lock()\n" + broken.split("\n", 1)[1]
        )
        self.assertEqual(undefined_global_names(fixed), set())
        late_global = "def boot():\n    global _state\n    _state = 1\ndef read():\n    return _state\n"
        self.assertEqual(undefined_global_names(late_global), set())
        with self.assertRaises(ValueError):
            undefined_global_names("from os import *\nprint(getcwd())\n")

    def test_every_listed_engine_module_exists(self):
        for name in ENGINE_MODULES:
            self.assertTrue((ROOT / name).is_file(), f"{name} is listed as a production engine but is missing")

    def test_production_modules_reference_only_defined_globals(self):
        files = production_files()
        self.assertGreater(len(files), 60, "the production scope collapsed: paths moved?")
        self.assertIn(ROOT / "application/routes/cinema_bp_routes.py", files)
        self.assertIn(ROOT / "application/bridge_server.py", files)
        for path in files:
            with self.subTest(module=path.relative_to(ROOT).as_posix()):
                source = path.read_text(encoding="utf-8")
                self.assertEqual(undefined_global_names(source, str(path)), set())


if __name__ == "__main__":
    unittest.main()
