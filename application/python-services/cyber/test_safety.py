from __future__ import annotations

# --- Resolution des modules voisins ----------------------------------------
# Ces tests importent leurs modules VOISINS a plat (`import _safety`). Cela
# fonctionne quand on les lance depuis ce dossier, mais pas sous
# `unittest discover` lance depuis python-services/, ou le fichier est charge
# comme `<paquet>.test_x` et ou le dossier du paquet n est PAS dans sys.path.
# L import echouait alors, et unittest comptait une ERREUR de test — un
# defaut d environnement maquille en regression. On ajoute le dossier du
# fichier, comme le font deja les tests de la racine.
import sys as _sys_boot
from pathlib import Path as _Path_boot
_sys_boot.path.insert(0, str(_Path_boot(__file__).resolve().parent))
# ---------------------------------------------------------------------------

import tempfile
import unittest
from pathlib import Path

import _safety


class CyberSafetyTests(unittest.TestCase):
    def test_private_network_allowed_public_network_blocked(self) -> None:
        self.assertEqual(_safety.assert_private("127.0.0.1"), "127.0.0.1")
        with self.assertRaises(PermissionError):
            _safety.assert_private("8.8.8.8")

    def test_read_path_stays_inside_application_workspace(self) -> None:
        outside = _safety.APP_ROOT.parent / "README.md"
        self.assertTrue(outside.exists(), outside)
        with self.assertRaises(PermissionError):
            _safety.validate_read_file(outside)

    def test_safe_read_bytes_enforces_size_cap(self) -> None:
        temp_root = _safety.APP_ROOT / "temp"
        temp_root.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=temp_root) as tmp:
            sample = Path(tmp) / "sample.bin"
            sample.write_bytes(b"aurora")
            self.assertEqual(_safety.safe_read_bytes(sample), b"aurora")
            with self.assertRaises(ValueError):
                _safety.safe_read_bytes(sample, max_bytes=3)

    def test_output_path_rejects_traversal(self) -> None:
        with self.assertRaises(PermissionError):
            _safety.validate_output_path("../escape.txt", create_parent=False)

    def test_sanitize_ports_deduplicates_and_rejects_bad_values(self) -> None:
        self.assertEqual(_safety.sanitize_ports([80, 443, 80]), [80, 443])
        with self.assertRaises(ValueError):
            _safety.sanitize_ports([0])
        with self.assertRaises(ValueError):
            _safety.sanitize_ports([65536])

    def test_text_payload_has_byte_cap(self) -> None:
        self.assertEqual(_safety.validate_text_payload("secret", "ok", max_bytes=2), "ok")
        with self.assertRaises(ValueError):
            _safety.validate_text_payload("secret", "éé", max_bytes=2)


if __name__ == "__main__":
    unittest.main(verbosity=2)
