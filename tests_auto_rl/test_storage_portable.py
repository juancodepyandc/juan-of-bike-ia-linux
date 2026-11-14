"""Real file locking and UTF-8 persistence on every supported CI platform."""
from pathlib import Path
import tempfile
import unittest

from auto_rl.storage import atomic_json, exclusive_lock, read_json


class PortableStorageTests(unittest.TestCase):
    def test_lock_excludes_a_second_holder_and_releases_after_exception(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/'cycle.lock'
            with self.assertRaisesRegex(ValueError,'operation interrupted'):
                with exclusive_lock(path):
                    with self.assertRaisesRegex(RuntimeError,'déjà actif'):
                        with exclusive_lock(path):
                            self.fail('Second holder must never enter')
                    raise ValueError('operation interrupted')
            with exclusive_lock(path):
                self.assertTrue(path.is_file())

    def test_json_round_trip_keeps_international_text_without_locale_assumptions(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/'observations.json'
            value = {'goal':'Réfléchir à 東京, vérifier λ et réparer 🛠'}
            atomic_json(path,value)
            self.assertEqual(read_json(path),value)
            self.assertIn('東京',path.read_text(encoding='utf-8'))

    def test_control_process_identity_works_without_procfs(self):
        import os
        from unittest.mock import patch
        from auto_rl import control
        with patch.object(Path, "read_text", side_effect=OSError("no /proc on macOS/Windows/BSD")):
            ident = control.process_identity(os.getpid())
            self.assertIsNotNone(ident)
            self.assertIn(str(os.getpid()), str(ident))
            self.assertIsNone(control.process_identity(-999999))

    def test_reclaim_comfy_ram_survives_missing_systemctl(self):
        from unittest.mock import patch
        from auto_rl import resources
        with patch("subprocess.run", side_effect=FileNotFoundError("no systemctl on Alpine/Void/macOS/Windows")):
            resources.reclaim_comfy_ram()

    def test_before_after_report_desktop_and_font_fallback(self):
        from auto_rl import before_after_report
        self.assertIsInstance(before_after_report.BUREAU_STUDIO_DIR, Path)
        font = before_after_report._load_font(14, bold=True)
        self.assertIsNotNone(font)

    def test_a_module_is_served_reinforced_only_after_official_promotion(self):
        """All 12 modules are listed; none may be reported or served as reinforced without a promotion."""
        from auto_rl.reinforced_registry import PROMOTED_STATUS, get_reinforced_overview
        status = get_reinforced_overview()
        modules = status.get("modules", {})
        self.assertGreaterEqual(len(modules), 12)
        for mod_id, info in modules.items():
            promoted = info.get("promoted_officially") is True and info.get("status") == PROMOTED_STATUS
            self.assertEqual(bool(info.get("reinforced_available")), promoted,
                             f"Module {mod_id}: reinforced_available must mean officially promoted")
            self.assertEqual(info.get("effective_variant"), "renforce" if promoted else "base",
                             f"Module {mod_id}: an unpromoted candidate must leave the base model in service")
            self.assertIn(info.get("selected_variant"), ("base", "renforce"))

