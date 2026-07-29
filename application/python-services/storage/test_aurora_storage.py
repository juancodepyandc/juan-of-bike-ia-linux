"""Filesystem-only tests for Aurora's two-tier storage manager."""

from __future__ import annotations

import json
import tempfile
import unittest
from collections import namedtuple
from pathlib import Path
from unittest.mock import patch

import aurora_storage
from aurora_storage import AuroraStorageManager, GIB


Usage = namedtuple("Usage", "total used free")


class AuroraStorageTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.workspace = root / "application"
        self.internal = root / "internal"
        self.cold = root / "cold"
        self.workspace.mkdir()
        self.internal.mkdir()
        self.cold.mkdir()
        self.hot_model = self.internal / "models" / "candidate"
        self.cold_model = self.cold / "hf" / "candidate"
        self.hot_model.mkdir(parents=True)
        (self.hot_model / "weights.bin").write_bytes(b"aurora-weights")
        self.manifest = self.workspace / "config" / "storage_manifest.json"
        self.manifest.parent.mkdir()
        self.manifest.write_text(json.dumps({
            "version": 1,
            "entries": [{
                "id": "candidate",
                "kind": "video",
                "hot_path": str(self.hot_model),
                "cold_path": str(self.cold_model),
                "size_gb": 0.001,
                "tier": "hot",
                "pin": False,
                "last_access": 1,
            }],
        }), encoding="utf-8")
        self.free = {"hot": 100.0, "cold": 100.0}

        def disk_usage(path: str):
            tier = "cold" if str(path).startswith(str(self.cold)) else "hot"
            free = self.free[tier] * GIB
            return Usage(200 * GIB, 200 * GIB - free, free)

        self.manager = AuroraStorageManager(
            manifest_path=self.manifest,
            cold_root=self.cold,
            internal_root=self.internal,
            workspace=self.workspace,
            disk_usage_fn=disk_usage,
            ismount_fn=lambda path: path == str(self.cold),
        )

    def tearDown(self):
        self.tmp.cleanup()

    def test_offline_support_is_never_treated_as_a_directory_fallback(self):
        manager = AuroraStorageManager(
            manifest_path=self.manifest,
            cold_root=self.cold,
            internal_root=self.internal,
            workspace=self.workspace,
            disk_usage_fn=self.manager._disk_usage,
            ismount_fn=lambda _path: False,
        )
        status = manager.status()
        self.assertFalse(status["key_mounted"])
        self.assertEqual(status["outputs_tier"], "hot")
        self.assertEqual(manager.tier_model("candidate", "cold")["reason"], "cold_storage_offline")

    def test_hard_floor_refuses_saturation(self):
        self.free["cold"] = 21.0
        result = self.manager.ensure_space("cold", 2.0)
        self.assertFalse(result["ok"])
        self.assertEqual(result["reason"], "disk_full")
        self.assertEqual(result["floor_gb"], 20.0)

    def test_cold_tiering_stage_and_unstage_are_reversible(self):
        migrated = self.manager.tier_model("candidate", "cold")
        self.assertTrue(migrated["ok"])
        self.assertTrue(self.hot_model.is_symlink())
        self.assertTrue((self.cold_model / "weights.bin").exists())

        staged = self.manager.stage("candidate")
        self.assertTrue(staged["ok"])
        self.assertFalse(self.hot_model.is_symlink())
        self.assertTrue((self.hot_model / "weights.bin").exists())
        self.assertTrue((self.cold_model / "weights.bin").exists())

        unstaged = self.manager.unstage("candidate")
        self.assertTrue(unstaged["ok"])
        self.assertTrue(self.hot_model.is_symlink())
        self.assertEqual(self.manager.entries()[0]["tier"], "cold")

    def test_symlink_failure_rolls_hot_source_back(self):
        with patch.object(aurora_storage.os, "symlink", side_effect=OSError("simulated")):
            result = self.manager.tier_model("candidate", "cold")
        self.assertFalse(result["ok"])
        self.assertTrue(self.hot_model.is_dir())
        self.assertFalse(self.hot_model.is_symlink())
        self.assertEqual((self.hot_model / "weights.bin").read_bytes(), b"aurora-weights")
        self.assertEqual(self.manager.entries()[0]["tier"], "hot")

    def test_missing_cold_output_uses_internal_with_warning(self):
        manager = AuroraStorageManager(
            manifest_path=self.manifest,
            cold_root=self.cold,
            internal_root=self.internal,
            workspace=self.workspace,
            disk_usage_fn=self.manager._disk_usage,
            ismount_fn=lambda _path: False,
        )
        result = manager.ensure_output_target(1)
        self.assertTrue(result["ok"])
        self.assertEqual(result["tier"], "hot")
        self.assertEqual(result["warnings"][0]["code"], "cold_storage_offline")

    def test_gc_defaults_to_dry_run_and_only_targets_terminal_jobs(self):
        old_job = self.workspace / "temp" / "cinema" / "job_old"
        active_job = self.workspace / "temp" / "cinema" / "job_active"
        old_job.mkdir(parents=True)
        active_job.mkdir(parents=True)
        (old_job / "status.json").write_text('{"status":"done"}', encoding="utf-8")
        (active_job / "status.json").write_text('{"status":"running"}', encoding="utf-8")
        result = self.manager.gc(dry_run=True, max_age_minutes=1)
        # New status files are not old enough yet.
        self.assertEqual(result["candidates"], [])
        self.assertTrue(old_job.exists())
        self.assertTrue(active_job.exists())


if __name__ == "__main__":
    unittest.main()
