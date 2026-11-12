import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest
import zipfile

from auto_rl.source_bundle import build_bundle, extract_bundle


class NativeSourceBundle(unittest.TestCase):
    def setUp(self):
        self.root = Path(__file__).resolve().parents[1]

    def test_deterministic_source_only_dependency_bundle_and_readback(self):
        raw, manifest = build_bundle(self.root, ["auto_rl.source_bundle"])
        again, _ = build_bundle(self.root, ["auto_rl.source_bundle"])
        self.assertEqual(raw, again)
        self.assertIn("auto_rl/source_bundle.py", manifest)
        self.assertTrue(all(name.endswith(".py") for name in manifest))
        with tempfile.TemporaryDirectory() as directory:
            extract_bundle(raw, directory, hashlib.sha256(raw).hexdigest())
            for name, expected in manifest.items():
                self.assertEqual(hashlib.sha256((Path(directory) / name).read_bytes()).hexdigest(), expected)

    def test_wrong_digest_never_extracts(self):
        raw, _ = build_bundle(self.root, ["auto_rl.source_bundle"])
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(ValueError):
                extract_bundle(raw, directory, "0" * 64)
            self.assertEqual(list(Path(directory).iterdir()), [])

    def test_traversal_or_alias_cannot_be_written_even_with_matching_archive_digest(self):
        for name in ("../escape.py", "nested/../escape.py", "nested//escape.py"):
            stream = io.BytesIO()
            content = b"pass\n"
            with zipfile.ZipFile(stream, "w") as archive:
                archive.writestr(name, content)
                archive.writestr("source_manifest.json", json.dumps({name: hashlib.sha256(content).hexdigest()}))
            raw = stream.getvalue()
            with tempfile.TemporaryDirectory() as directory:
                with self.assertRaises(ValueError):
                    extract_bundle(raw, directory, hashlib.sha256(raw).hexdigest())
                self.assertEqual(list(Path(directory).iterdir()), [])

    def test_existing_changed_source_is_preserved(self):
        raw, _ = build_bundle(self.root, ["auto_rl.source_bundle"])
        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory)
            target = destination / "auto_rl/source_bundle.py"
            target.parent.mkdir()
            target.write_text("existing user work")
            with self.assertRaises(ValueError):
                extract_bundle(raw, destination, hashlib.sha256(raw).hexdigest())
            self.assertEqual(target.read_text(), "existing user work")
