#!/usr/bin/env python3

import struct
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import simulation_lab
from simulation_android import ANDROID_PROFILES, _package_resumed, _tap_target, android_guest_url
from simulation_embedded import _elf32_to_raw
from simulation_tooling import unavailable


def fake_elf32(payload: bytes, address: int = 0x8000) -> bytes:
  header = bytearray(52)
  header[:6] = b"\x7fELF\x01\x01"
  struct.pack_into("<I", header, 28, 52)
  struct.pack_into("<HH", header, 42, 32, 1)
  segment = struct.pack("<IIIIIIII", 1, 84, address, address, len(payload), len(payload) + 4, 5, 4)
  return bytes(header) + segment + payload


class SimulationEnvironmentTests(unittest.TestCase):
  def test_android_loopback_is_mapped_to_emulator_host(self):
    self.assertEqual(
      android_guest_url("http://127.0.0.1:1420/code?q=1"),
      "http://10.0.2.2:1420/code?q=1",
    )
    self.assertEqual(android_guest_url("https://example.test/app"), "https://example.test/app")

  def test_android_matrix_contains_real_phone_and_tablet_profiles(self):
    self.assertEqual(set(ANDROID_PROFILES), {"phone", "tablet"})
    self.assertNotEqual(ANDROID_PROFILES["phone"]["device"], ANDROID_PROFILES["tablet"]["device"])

  def test_android_user_action_uses_accessibility_bounds(self):
    xml = '<hierarchy><node text="Continuer sans admin" bounds="[100,200][300,260]" /></hierarchy>'
    self.assertEqual(_tap_target(xml, "continuer sans admin"), (200, 230))
    self.assertIsNone(_tap_target("<invalid", "Continuer"))

  def test_android_foreground_activity_must_be_the_probe_package(self):
    resumed = "topResumedActivity=ActivityRecord{1 u0 ia.aurora.codeprobe/.MainActivity t8}"
    launcher = "topResumedActivity=ActivityRecord{1 u0 com.google.android.apps.nexuslauncher/.NexusLauncherActivity}"
    self.assertTrue(_package_resumed(resumed))
    self.assertFalse(_package_resumed(launcher))

  def test_elf_load_segment_is_converted_to_raw_firmware(self):
    with tempfile.TemporaryDirectory() as raw:
      root = Path(raw)
      elf, image = root / "firmware.elf", root / "kernel.img"
      elf.write_bytes(fake_elf32(b"AURORA"))
      _elf32_to_raw(elf, image)
      self.assertEqual(image.read_bytes(), b"AURORA\x00\x00\x00\x00")

  def test_unavailable_stage_never_claims_real_execution(self):
    stage = unavailable("tool", "Tool", "embedded", "missing")
    self.assertEqual(stage["status"], "unavailable")
    self.assertFalse(stage["realExecution"])

  def test_environment_matrix_executes_each_external_runner(self):
    executed = lambda stage_id: {
      "id": stage_id,
      "label": stage_id,
      "family": "os_boot",
      "status": "executed",
      "realExecution": True,
    }
    webkit = [{"browser": "webkit", "status": "executed"}]
    with patch.object(simulation_lab, "run_android_stages", return_value=[executed("android")]), \
         patch.object(simulation_lab, "run_renode_stage", return_value=executed("renode")), \
         patch.object(simulation_lab, "run_qemu_raspberry_stage", return_value=executed("raspberry")), \
         patch.object(simulation_lab, "run_qemu_os_stage", return_value=executed("os")):
      stages = simulation_lab._environment_stages("http://127.0.0.1:1420", Path("out"), webkit)
    self.assertEqual([stage["id"] for stage in stages[:4]], ["android", "renode", "raspberry", "os"])
    self.assertNotIn("webkit_real_browser", [stage["id"] for stage in stages])
    self.assertEqual(stages[-1]["status"], "deferred")


if __name__ == "__main__":
  unittest.main()
