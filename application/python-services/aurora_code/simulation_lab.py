#!/usr/bin/env python3
"""Aurora Code WS12 simulation lab.

Runs real browser/device simulations when the local toolchain exists and
returns explicit degraded/unavailable statuses otherwise. No system install is
performed here.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
CDP_HELPER = ROOT / "python-services" / "aurora_code" / "cdp_drive.mjs"
PLAYWRIGHT_HELPER = ROOT / "python-services" / "aurora_code" / "playwright_simulate.mjs"
SCHEMA = "aurora.code.simulation-lab/1"


def _which(*names: str) -> str | None:
  for name in names:
    found = shutil.which(name)
    if found:
      return found
  return None


def _parse_json(raw: str) -> dict[str, Any]:
  try:
    parsed = json.loads(raw or "{}")
    return parsed if isinstance(parsed, dict) else {}
  except Exception:
    return {}


def _run_chromium_profiles(url: str, out_dir: Path, wait_ms: int) -> list[dict[str, Any]]:
  target = out_dir / "chromium"
  target.mkdir(parents=True, exist_ok=True)
  proc = subprocess.run(
    ["node", str(CDP_HELPER), "simulate", url, str(target), str(wait_ms)],
    cwd=ROOT,
    check=False,
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
    text=True,
    timeout=max(45, wait_ms / 1000 * 12 + 75),
  )
  payload = _parse_json(proc.stdout)
  stages = payload.get("stages") if isinstance(payload.get("stages"), list) else []
  if proc.returncode == 0 and stages:
    return stages
  return [{
    "id": "chromium_profiles",
    "label": "Chromium CDP device profiles",
    "family": "web",
    "browser": "chromium",
    "status": "unavailable",
    "realExecution": False,
    "error": (proc.stderr or proc.stdout or f"cdp rc={proc.returncode}")[-1500:],
  }]


def _run_firefox_smoke(url: str, out_dir: Path, wait_ms: int) -> dict[str, Any]:
  firefox = _which("firefox")
  if not firefox:
    return {
      "id": "firefox_headless",
      "label": "Firefox headless screenshot",
      "family": "web",
      "browser": "firefox",
      "status": "unavailable",
      "realExecution": False,
      "error": "firefox introuvable dans PATH",
    }
  screenshot = out_dir / "firefox_1440x900.png"
  profile_dir = Path(tempfile.mkdtemp(prefix="aurora_firefox_"))
  try:
    proc = subprocess.run(
      [
        firefox,
        "--headless",
        "--new-instance",
        "--profile",
        str(profile_dir),
        "--screenshot",
        str(screenshot),
        "--window-size",
        "1440,900",
        url,
      ],
      cwd=ROOT,
      check=False,
      stdout=subprocess.PIPE,
      stderr=subprocess.PIPE,
      text=True,
      timeout=max(45, wait_ms / 1000 + 45),
    )
  except subprocess.TimeoutExpired:
    shutil.rmtree(profile_dir, ignore_errors=True)
    return {
      "id": "firefox_headless",
      "label": "Firefox headless screenshot",
      "family": "web",
      "browser": "firefox",
      "status": "unavailable",
      "realExecution": False,
      "error": "timeout firefox headless",
    }
  finally:
    shutil.rmtree(profile_dir, ignore_errors=True)
  ok = proc.returncode == 0 and screenshot.is_file() and screenshot.stat().st_size > 0
  return {
    "id": "firefox_headless",
    "label": "Firefox headless screenshot",
    "family": "web",
    "browser": "firefox",
    "status": "executed" if ok else "unavailable",
    "realExecution": bool(ok),
    "viewport": "1440x900",
    "width": 1440,
    "height": 900,
    "dpr": 1,
    "touch": False,
    "screenshotPath": str(screenshot),
    **({} if ok else {"error": (proc.stderr or proc.stdout or "firefox screenshot failed")[-1500:]}),
  }


def _run_playwright_matrix(url: str, out_dir: Path, wait_ms: int) -> list[dict[str, Any]]:
  if not PLAYWRIGHT_HELPER.is_file():
    return [{
      "id": "playwright_browser_matrix",
      "label": "Playwright Chromium/Firefox/WebKit",
      "family": "web",
      "status": "unavailable",
      "realExecution": False,
      "error": "playwright_simulate.mjs introuvable",
    }]
  target = out_dir / "playwright"
  target.mkdir(parents=True, exist_ok=True)
  proc = subprocess.run(
    ["node", str(PLAYWRIGHT_HELPER), url, str(target), str(wait_ms)],
    cwd=ROOT,
    check=False,
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
    text=True,
    timeout=max(60, wait_ms / 1000 * 8 + 90),
  )
  payload = _parse_json(proc.stdout)
  stages = payload.get("stages") if isinstance(payload.get("stages"), list) else []
  if stages:
    return stages
  return [{
    "id": "playwright_browser_matrix",
    "label": "Playwright Chromium/Firefox/WebKit",
    "family": "web",
    "status": "unavailable",
    "realExecution": False,
    "error": (proc.stderr or proc.stdout or f"playwright rc={proc.returncode}")[-1500:],
  }]


def _availability_stage(
  stage_id: str,
  label: str,
  family: str,
  tool: str | None,
  unavailable_reason: str,
  *,
  degraded_detail: str | None = None,
) -> dict[str, Any]:
  if tool:
    return {
      "id": stage_id,
      "label": label,
      "family": family,
      "status": "degraded" if degraded_detail else "detected",
      "realExecution": False,
      "toolPath": tool,
      "detail": degraded_detail or "outil detecte; scenario specifique requis pour execution",
    }
  return {
    "id": stage_id,
    "label": label,
    "family": family,
    "status": "unavailable",
    "realExecution": False,
    "error": unavailable_reason,
  }


def _environment_stages() -> list[dict[str, Any]]:
  return [
    _availability_stage(
      "webkit_real_browser",
      "WebKit real browser",
      "web",
      _which("MiniBrowser", "webkit2gtk-driver", "webkit2png"),
      "WebKit headless CLI introuvable; ne pas remplacer par largeur CSS.",
    ),
    _availability_stage(
      "android_real_mobile",
      "Android emulator / device",
      "mobile_real",
      _which("emulator", "adb", "waydroid"),
      "Android emulator, adb ou Waydroid introuvable; execution mobile reelle differree.",
    ),
    _availability_stage(
      "renode_microcontrollers",
      "Renode ESP32/Arduino/Raspberry",
      "embedded",
      _which("renode"),
      "Renode introuvable; firmware non simule et non remplace par mock largeur.",
    ),
    _availability_stage(
      "qemu_bootable_os",
      "QEMU OS/Raspberry boot",
      "os_boot",
      _which("qemu-system-x86_64", "qemu-system-aarch64", "qemu-system-arm"),
      "QEMU introuvable; image OS/Raspberry non lancee.",
    ),
    {
      "id": "console_emulation_feasibility",
      "label": "Consoles anciennes/recentes",
      "family": "console",
      "status": "deferred",
      "realExecution": False,
      "detail": "Necessite emulateurs open-source dedies par console et ROM/SDK legalement fournis; hors execution automatique generique.",
    },
  ]


def run_lab(url: str, out_dir: Path, wait_ms: int = 2500) -> dict[str, Any]:
  out_dir.mkdir(parents=True, exist_ok=True)
  stages = []
  stages.extend(_run_chromium_profiles(url, out_dir, wait_ms))
  playwright_stages = _run_playwright_matrix(url, out_dir, wait_ms)
  stages.extend(playwright_stages)
  if not any(stage.get("browser") == "firefox" and stage.get("status") == "executed" for stage in playwright_stages):
    stages.append(_run_firefox_smoke(url, out_dir, wait_ms))
  stages.extend(_environment_stages())
  return {
    "schemaVersion": SCHEMA,
    "url": url,
    "createdAt": int(time.time() * 1000),
    "outDir": str(out_dir),
    "stages": stages,
  }


def main(argv: list[str]) -> int:
  if len(argv) < 3:
    print("usage: simulation_lab.py <url> <out_dir> [wait_ms]", file=sys.stderr)
    return 2
  wait_ms = int(argv[3]) if len(argv) > 3 else 2500
  print(json.dumps(run_lab(argv[1], Path(argv[2]), wait_ms), ensure_ascii=False))
  return 0


if __name__ == "__main__":
  raise SystemExit(main(sys.argv))
