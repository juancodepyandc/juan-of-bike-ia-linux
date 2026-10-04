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
