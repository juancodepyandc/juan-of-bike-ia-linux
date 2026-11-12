"""Blender doit être trouvé là où l'utilisateur l'a posé, y compris sur son bureau."""
from __future__ import annotations

import os
import stat
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "application" / "python-services"))
import blender_locator  # noqa: E402


def _fake_exe(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("#!/bin/sh\necho Blender\n", encoding="utf-8")
    path.chmod(path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    return path


@unittest.skipIf(os.name == "nt", "chemins Linux simulés")
class BlenderLocatorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.home = Path(self.tmp.name) / "juan"
        self.home.mkdir()
        env = {k: v for k, v in os.environ.items() if k not in blender_locator.ENV_VARS and k not in ("OneDrive", "OneDriveConsumer", "XDG_CONFIG_HOME")}
        env["HOME"] = str(self.home)
        env["PATH"] = str(Path(self.tmp.name) / "empty-bin")
        patches = [
            patch.dict(os.environ, env, clear=True),
            patch.object(blender_locator, "APP_ROOT", Path(self.tmp.name) / "application"),
            patch.object(Path, "home", classmethod(lambda cls: self.home)),
            patch.object(blender_locator, "_standard_installs", lambda: []),
        ]
        for p in patches:
            p.start()
            self.addCleanup(p.stop)
        blender_locator._cached.cache_clear()
        self.addCleanup(blender_locator._cached.cache_clear)
        self.addCleanup(self.tmp.cleanup)

    def _xdg_desktop(self, name: str) -> Path:
        cfg = self.home / ".config" / "user-dirs.dirs"
        cfg.parent.mkdir(parents=True, exist_ok=True)
        cfg.write_text(f'XDG_DESKTOP_DIR="$HOME/{name}"\n', encoding="utf-8")
        desk = self.home / name
        desk.mkdir(exist_ok=True)
        return desk

    def test_portable_blender_extracted_on_the_french_desktop(self) -> None:
        desk = self._xdg_desktop("Bureau")
        _fake_exe(desk / "blender-4.2.12-linux-x64" / "blender")
        newest = _fake_exe(desk / "blender-4.5.3-linux-x64" / "blender")
        path, origin = blender_locator.locate()
        self.assertEqual(path, str(newest))
        self.assertIn("bureau", origin)

    def test_desktop_launcher_and_appimage(self) -> None:
        desk = self._xdg_desktop("Bureau")
        target = _fake_exe(self.home / "outils" / "blender-5.0" / "blender")
        (desk / "blender.desktop").write_text(f"[Desktop Entry]\nName=Blender\nExec={target} %f\n", encoding="utf-8")
        self.assertEqual(blender_locator.locate()[0], str(target))
        (desk / "blender.desktop").unlink()
        appimage = _fake_exe(desk / "Blender-4.4.0-x86_64.AppImage")
        self.assertEqual(blender_locator.locate()[0], str(appimage))

    def test_nested_folder_on_an_english_desktop(self) -> None:
        exe = _fake_exe(self.home / "Desktop" / "Blender" / "blender-4.3.2-linux-x64" / "blender")
        self.assertEqual(blender_locator.locate()[0], str(exe))

    def test_explicit_variable_wins_and_accepts_a_folder(self) -> None:
        desk = self._xdg_desktop("Bureau")
        _fake_exe(desk / "blender-4.5.3-linux-x64" / "blender")
        chosen = _fake_exe(self.home / "autre" / "blender")
        with patch.dict(os.environ, {"AURORA_BLENDER": str(chosen.parent)}):
            path, origin = blender_locator.locate()
            self.assertEqual((path, origin), (str(chosen), "AURORA_BLENDER"))

    def test_ensure_env_exports_the_found_blender_for_subprocesses(self) -> None:
        desk = self._xdg_desktop("Bureau")
        exe = _fake_exe(desk / "blender-4.5.3-linux-x64" / "blender")
        self.assertEqual(blender_locator.ensure_env(), str(exe))
        self.assertEqual(os.environ["AURORA_BLENDER"], str(exe))

    def test_nothing_found_is_reported_not_invented(self) -> None:
        self._xdg_desktop("Bureau")
        self.assertEqual(blender_locator.locate(), (None, "introuvable"))
        self.assertIsNone(blender_locator.ensure_env())
        self.assertNotIn("AURORA_BLENDER", os.environ)

    def test_windows_shortcut_target_is_read(self) -> None:
        raw = "C:\\Program Files\\Blender Foundation\\Blender 4.5\\blender-launcher.exe".encode("utf-16-le")
        data = b"L\x00\x00\x00" + b"\x00" * 60 + raw + b"\x00\x00"
        self.assertEqual(blender_locator.lnk_targets(data), ["C:\\Program Files\\Blender Foundation\\Blender 4.5\\blender-launcher.exe"])


if __name__ == "__main__":
    unittest.main()
