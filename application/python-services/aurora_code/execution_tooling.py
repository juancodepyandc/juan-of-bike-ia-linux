#!/usr/bin/env python3
"""Shared process and tool discovery helpers for the WS12 simulation lab."""

from __future__ import annotations

import os
import shutil
import signal
import subprocess
import time
from pathlib import Path
from typing import Any, Iterable


TOOL_ROOT = Path(
  os.environ.get("AURORA_CODE_TOOL_ROOT", "~/.local/share/auroraia/tools")
).expanduser()


def find_tool(env_name: str, names: Iterable[str], patterns: Iterable[str]) -> str | None:
  explicit = os.environ.get(env_name, "").strip()
  if explicit and Path(explicit).expanduser().is_file():
    return str(Path(explicit).expanduser().resolve())
  for name in names:
    found = shutil.which(name)
    if found:
      return found
  for pattern in patterns:
    for candidate in sorted(TOOL_ROOT.glob(pattern), reverse=True):
      if candidate.is_file() and os.access(candidate, os.X_OK):
        return str(candidate.resolve())
  return None


def android_sdk_root() -> Path | None:
  candidates = [
    os.environ.get("ANDROID_SDK_ROOT"),
    os.environ.get("ANDROID_HOME"),
    str(TOOL_ROOT / "android-sdk"),
  ]
  for raw in candidates:
    if not raw:
      continue
    path = Path(raw).expanduser()
    if (path / "platform-tools" / "adb").is_file() and (path / "emulator" / "emulator").is_file():
      return path.resolve()
  return None


def unavailable(stage_id: str, label: str, family: str, reason: str) -> dict[str, Any]:
  return {
    "id": stage_id,
    "label": label,
    "family": family,
    "status": "unavailable",
    "realExecution": False,
    "error": reason,
  }


def run_command(
  args: list[str],
  *,
  cwd: Path,
  timeout: int = 60,
  env: dict[str, str] | None = None,
  input_text: str | None = None,
) -> subprocess.CompletedProcess[str]:
  return subprocess.run(
    args,
    cwd=cwd,
    check=False,
    capture_output=True,
    text=True,
    timeout=timeout,
    env=env,
    input=input_text,
  )


def tail(value: str, limit: int = 2000) -> str:
  return (value or "")[-limit:]


def terminate_owned(proc: subprocess.Popen[Any], grace_seconds: float = 4.0) -> None:
  if proc.poll() is not None:
    return
  try:
    os.killpg(proc.pid, signal.SIGTERM)
    proc.wait(timeout=grace_seconds)
  except (ProcessLookupError, subprocess.TimeoutExpired):
    if proc.poll() is None:
      try:
        os.killpg(proc.pid, signal.SIGKILL)
      except ProcessLookupError:
        pass
      try:
        proc.wait(timeout=2)
      except subprocess.TimeoutExpired:
        pass


def run_until_marker(
  args: list[str],
  *,
  cwd: Path,
  log_path: Path,
  marker: str,
  timeout: int,
  env: dict[str, str] | None = None,
) -> tuple[bool, int | None, str, int]:
  started = time.monotonic()
  log_path.parent.mkdir(parents=True, exist_ok=True)
  with log_path.open("w", encoding="utf-8") as stream:
    proc = subprocess.Popen(
      args,
      cwd=cwd,
      stdout=stream,
      stderr=subprocess.STDOUT,
      text=True,
      env=env,
      start_new_session=True,
    )
    matched = False
    try:
      deadline = started + timeout
      while time.monotonic() < deadline:
        stream.flush()
        content = log_path.read_text(encoding="utf-8", errors="replace")
        if marker in content:
          matched = True
          break
        if proc.poll() is not None:
          break
        time.sleep(0.1)
    finally:
      terminate_owned(proc)
  content = log_path.read_text(encoding="utf-8", errors="replace")
  elapsed_ms = int((time.monotonic() - started) * 1000)
  return matched or marker in content, proc.returncode, content, elapsed_ms
