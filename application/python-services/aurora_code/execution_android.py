#!/usr/bin/env python3
"""Build and execute a real Android APK/PWA probe for Aurora Code WS12."""

from __future__ import annotations

import os
import re
import shutil
import socket
import subprocess
import time
import zipfile
import xml.etree.ElementTree as ElementTree
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit, urlunsplit

from execution_android_app import ACTIVITY_SOURCE, MANIFEST
from execution_android_profiles import ANDROID_PROFILES
from execution_tooling import TOOL_ROOT, android_sdk_root, run_command, tail, terminate_owned, unavailable


ANDROID_MARKER = "AURORA_WS12_PWA_EXECUTED"
ANDROID_INTERACTION_MARKER = "AURORA_WS12_INTERACTION_VERIFIED"
PACKAGE = "ia.aurora.codeprobe"
ACTIVITY = f"{PACKAGE}/.MainActivity"
SYSTEM_IMAGE = "system-images;android-36;default;x86_64"


def android_guest_url(url: str) -> str:
  parsed = urlsplit(url)
  if parsed.hostname not in {"127.0.0.1", "localhost", "::1"}:
    return url
  host = "10.0.2.2"
  if parsed.port:
    host += f":{parsed.port}"
  return urlunsplit((parsed.scheme, host, parsed.path, parsed.query, parsed.fragment))


def _version_key(path: Path) -> tuple[int, ...]:
  values = []
  for part in path.name.split("."):
    values.append(int(part) if part.isdigit() else 0)
  return tuple(values)


def _android_env(sdk: Path, avd_home: Path) -> dict[str, str]:
  env = os.environ.copy()
  java_home = Path(env.get("JAVA_HOME", "")) if env.get("JAVA_HOME") else None
  if not java_home or not (java_home / "bin" / "javac").is_file():
    jdks = sorted(TOOL_ROOT.glob("jdk-*/bin/javac"), reverse=True)
    java_home = jdks[0].parents[1] if jdks else None
  path_parts = [str(sdk / "platform-tools"), str(sdk / "emulator")]
  if java_home:
    path_parts.append(str(java_home / "bin"))
    env["JAVA_HOME"] = str(java_home)
  env.update({
    "ANDROID_HOME": str(sdk),
    "ANDROID_SDK_ROOT": str(sdk),
    "ANDROID_AVD_HOME": str(avd_home),
    "PATH": os.pathsep.join([*path_parts, env.get("PATH", "")]),
  })
  return env


def _find_avdmanager(sdk: Path) -> Path | None:
  candidates = sorted(sdk.glob("cmdline-tools/*/bin/avdmanager"), reverse=True)
  return candidates[0] if candidates else None


def _ensure_avd(
  sdk: Path,
  avd_home: Path,
  env: dict[str, str],
  avd_name: str,
  device: str,
) -> tuple[bool, str]:
  avd_home.mkdir(parents=True, exist_ok=True)
  if (avd_home / f"{avd_name}.avd" / "config.ini").is_file():
    return True, "AVD deja present"
  manager = _find_avdmanager(sdk)
  if not manager:
    return False, "avdmanager introuvable"
  proc = run_command(
    [str(manager), "create", "avd", "--force", "--name", avd_name, "--package", SYSTEM_IMAGE, "--device", device],
    cwd=avd_home,
    timeout=90,
    env=env,
    input_text="no\n",
  )
  log = (proc.stdout or "") + (proc.stderr or "")
  return proc.returncode == 0 and (avd_home / f"{avd_name}.avd").is_dir(), log


def _build_apk(sdk: Path, target: Path, env: dict[str, str]) -> tuple[Path | None, str]:
  target.mkdir(parents=True, exist_ok=True)
  source = target / "src" / "ia" / "aurora" / "codeprobe" / "MainActivity.java"
  source.parent.mkdir(parents=True, exist_ok=True)
  source.write_text(ACTIVITY_SOURCE, encoding="utf-8")
  (target / "AndroidManifest.xml").write_text(MANIFEST, encoding="utf-8")
  platforms = sorted(sdk.glob("platforms/android-*/android.jar"), key=lambda item: int(item.parent.name.split("-")[-1]))
  builds = sorted((item for item in (sdk / "build-tools").glob("*") if item.is_dir()), key=_version_key)
  javac = shutil.which("javac", path=env.get("PATH"))
  keytool = shutil.which("keytool", path=env.get("PATH"))
  if not platforms or not builds or not javac or not keytool:
    return None, "plateforme Android, build-tools ou JDK incomplet"
  android_jar, build = platforms[-1], builds[-1]
  aapt2, d8 = build / "aapt2", build / "d8"
  zipalign, signer = build / "zipalign", build / "apksigner"
  unsigned, aligned, apk = target / "unsigned.apk", target / "aligned.apk", target / "aurora-ws12-code-probe.apk"
  classes, dex = target / "classes", target / "dex"
  classes.mkdir(exist_ok=True)
  dex.mkdir(exist_ok=True)
  commands = [
    [str(aapt2), "link", "-o", str(unsigned), "--manifest", str(target / "AndroidManifest.xml"), "-I", str(android_jar),
     "--min-sdk-version", "28", "--target-sdk-version", "36"],
    [javac, "-source", "8", "-target", "8", "-classpath", str(android_jar), "-d", str(classes), str(source)],
  ]
  logs = []
  for args in commands:
    proc = run_command(args, cwd=target, timeout=90, env=env)
    logs.append((proc.stdout or "") + (proc.stderr or ""))
    if proc.returncode:
      return None, "\n".join(logs)
  class_files = [str(item) for item in classes.rglob("*.class")]
  proc = run_command([str(d8), "--release", "--lib", str(android_jar), "--output", str(dex), *class_files], cwd=target, timeout=90, env=env)
  logs.append((proc.stdout or "") + (proc.stderr or ""))
  if proc.returncode or not (dex / "classes.dex").is_file():
    return None, "\n".join(logs)
  with zipfile.ZipFile(unsigned, "a", compression=zipfile.ZIP_DEFLATED) as archive:
    archive.write(dex / "classes.dex", "classes.dex")
  keystore = target / "probe.keystore"
  if keystore.is_file():
    key = subprocess.CompletedProcess([keytool], 0, "keystore existant reutilise\n", "")
  else:
    key = run_command(
      [keytool, "-genkeypair", "-keystore", str(keystore), "-storepass", "android", "-keypass", "android",
       "-alias", "aurora", "-keyalg", "RSA", "-validity", "3650", "-dname", "CN=Aurora WS12,O=AuroraIA,C=FR"],
      cwd=target,
      timeout=60,
      env=env,
    )
  align = run_command([str(zipalign), "-f", "4", str(unsigned), str(aligned)], cwd=target, timeout=30, env=env)
  sign = run_command(
    [str(signer), "sign", "--ks", str(keystore), "--ks-pass", "pass:android", "--key-pass", "pass:android",
     "--out", str(apk), str(aligned)],
    cwd=target,
    timeout=60,
    env=env,
  )
  logs.extend([(key.stdout or "") + (key.stderr or ""), (align.stdout or "") + (align.stderr or ""),
               (sign.stdout or "") + (sign.stderr or "")])
  ok = key.returncode == align.returncode == sign.returncode == 0 and apk.is_file()
  return (apk if ok else None), "\n".join(logs)


def _free_emulator_port() -> int | None:
  for port in [*range(5554, 5588, 2), *range(5588, 5680, 2)]:
    with socket.socket() as probe:
      probe.settimeout(0.05)
      if probe.connect_ex(("127.0.0.1", port)) != 0:
        return port
  return None


def _adb(adb: Path, serial: str, target: Path, env: dict[str, str], *args: str, timeout: int = 30):
  return run_command([str(adb), "-s", serial, *args], cwd=target, timeout=timeout, env=env)


def _tap_target(xml: str, label: str) -> tuple[int, int] | None:
  try:
    root = ElementTree.fromstring(xml)
  except ElementTree.ParseError:
    return None
  for node in root.iter("node"):
    if label.casefold() not in node.attrib.get("text", "").casefold():
      continue
    bounds = re.fullmatch(r"\[(\d+),(\d+)]\[(\d+),(\d+)]", node.attrib.get("bounds", ""))
    if bounds:
      left, top, right, bottom = (int(value) for value in bounds.groups())
      return (left + right) // 2, (top + bottom) // 2
  return None


def _package_resumed(raw: str) -> bool:
  return any(
    PACKAGE in line and ("topResumedActivity" in line or "mResumedActivity" in line)
    for line in raw.splitlines()
  )


def run_android_stage(url: str, out_dir: Path, profile_name: str = "phone") -> dict[str, Any]:
  profile = ANDROID_PROFILES.get(profile_name)
  if not profile:
    raise ValueError(f"profil Android inconnu: {profile_name}")
  label = profile["label"]
  sdk = android_sdk_root()
  if not sdk:
    return unavailable(profile["stageId"], label, "mobile_real", "Android SDK emulator/adb introuvable")
  target = (out_dir / profile["target"]).resolve()
  avd_home = TOOL_ROOT / "android-avd"
  env = _android_env(sdk, avd_home)
  ready, avd_log = _ensure_avd(sdk, avd_home, env, profile["avdName"], profile["device"])
  if not ready:
    return unavailable(profile["stageId"], label, "mobile_real", tail(avd_log))
  apk, build_log = _build_apk(sdk, target, env)
  (target / "build.log").write_text(build_log, encoding="utf-8")
  if not apk:
    return unavailable(profile["stageId"], label, "mobile_real", tail(build_log))
  port = _free_emulator_port()
  if not port:
    return unavailable(profile["stageId"], label, "mobile_real", "aucun port emulator libre")
  emulator, adb = sdk / "emulator" / "emulator", sdk / "platform-tools" / "adb"
  serial, emulator_log = f"emulator-{port}", target / "emulator.log"
  stream = emulator_log.open("w", encoding="utf-8")
  proc = subprocess.Popen(
    [str(emulator), "-avd", profile["avdName"], "-port", str(port), "-no-window", "-no-audio", "-no-boot-anim",
     "-no-snapshot", "-gpu", "swiftshader_indirect", "-accel", "auto"],
    cwd=target,
    stdout=stream,
    stderr=subprocess.STDOUT,
    text=True,
    env=env,
    start_new_session=True,
  )
  marker_xml, marker_log, before_xml, booted = "", "", "", False
  interaction_ok, interaction_verified, error = False, False, ""
  started = time.monotonic()
  try:
    deadline = time.monotonic() + 180
    while time.monotonic() < deadline and proc.poll() is None:
      state = _adb(adb, serial, target, env, "get-state", timeout=10)
      boot = _adb(adb, serial, target, env, "shell", "getprop", "sys.boot_completed", timeout=10)
      if state.returncode == 0 and boot.stdout.strip() == "1":
        booted = True
        break
      time.sleep(2)
    if not booted:
      error = "AVD non boote avant timeout"
    else:
      _adb(adb, serial, target, env, "shell", "settings", "put", "global", "window_animation_scale", "0")
      _adb(adb, serial, target, env, "uninstall", PACKAGE, timeout=45)
      install = _adb(adb, serial, target, env, "install", "--no-incremental", "-r", str(apk), timeout=90)
      guest_url = android_guest_url(url)
      _adb(adb, serial, target, env, "logcat", "-c", timeout=20)
      launch = _adb(adb, serial, target, env, "shell", "am", "start", "-W", "-n", ACTIVITY,
                    "--es", "target_url", guest_url, "--es", "device_profile", profile_name, timeout=60)
      (target / "install.log").write_text((install.stdout or "") + (install.stderr or ""), encoding="utf-8")
      (target / "launch.log").write_text((launch.stdout or "") + (launch.stderr or ""), encoding="utf-8")
      if install.returncode or launch.returncode:
        error = tail((install.stderr or install.stdout) + (launch.stderr or launch.stdout))
      else:
        for _attempt in range(45):
          marker_probe = _adb(adb, serial, target, env, "logcat", "-d", "-s", "AuroraWS12:I", "*:S", timeout=20)
          marker_log = marker_probe.stdout or ""
          if ANDROID_MARKER in marker_log:
            break
          time.sleep(1)
        if ANDROID_MARKER in marker_log:
          before_xml, tap = "", None
          for _ui_attempt in range(3):
            _adb(adb, serial, target, env, "shell", "uiautomator", "dump", "/sdcard/aurora_before.xml", timeout=20)
            before = _adb(adb, serial, target, env, "exec-out", "cat", "/sdcard/aurora_before.xml", timeout=20)
            before_xml = before.stdout or ""
            tap = _tap_target(before_xml, "Continuer sans admin")
            if tap:
              break
            time.sleep(2)
          (target / "window_before.xml").write_text(before_xml, encoding="utf-8")
          if tap:
            action = _adb(adb, serial, target, env, "shell", "input", "tap", str(tap[0]), str(tap[1]), timeout=20)
            interaction_ok = action.returncode == 0
            (target / "interaction.log").write_text(
              f"tap Continuer sans admin at {tap[0]},{tap[1]} rc={action.returncode}\n", encoding="utf-8"
            )
            for _interaction_attempt in range(30):
              marker_probe = _adb(adb, serial, target, env, "logcat", "-d", "-s", "AuroraWS12:I", "*:S", timeout=20)
              marker_log = marker_probe.stdout or ""
              if ANDROID_INTERACTION_MARKER in marker_log:
                break
              time.sleep(0.5)
        marker_xml = before_xml
        activity = _adb(adb, serial, target, env, "shell", "dumpsys", "activity", "activities", timeout=30)
        activity_log = activity.stdout or ""
        interaction_verified = (
          interaction_ok
          and ANDROID_INTERACTION_MARKER in marker_log
          and _package_resumed(activity_log)
        )
        (target / "window.xml").write_text(marker_xml, encoding="utf-8")
        (target / "marker.log").write_text(marker_log, encoding="utf-8")
        (target / "activity.log").write_text(activity_log, encoding="utf-8")
        with (target / "android.png").open("wb") as screenshot:
          subprocess.run([str(adb), "-s", serial, "exec-out", "screencap", "-p"], cwd=target, env=env,
                         stdout=screenshot, stderr=subprocess.PIPE, timeout=30, check=False)
        props = _adb(adb, serial, target, env, "shell", "getprop", timeout=30)
        logs = _adb(adb, serial, target, env, "logcat", "-d", "-v", "threadtime", "-t", "400", timeout=30)
        (target / "getprop.log").write_text(props.stdout or "", encoding="utf-8")
        (target / "logcat.log").write_text(logs.stdout or "", encoding="utf-8")
  except (OSError, subprocess.TimeoutExpired) as exc:
    error = str(exc)
  finally:
    if booted:
      try:
        _adb(adb, serial, target, env, "emu", "kill", timeout=15)
      except subprocess.TimeoutExpired:
        pass
    terminate_owned(proc)
    stream.close()
  screenshot = target / "android.png"
  ok = (
    ANDROID_MARKER in marker_log
    and ANDROID_MARKER in marker_xml
    and PACKAGE in marker_xml
    and interaction_ok
    and interaction_verified
    and screenshot.is_file()
    and screenshot.stat().st_size > 1000
  )
  return {
    "id": profile["stageId"],
    "label": label,
    "family": "mobile_real",
    "status": "executed" if ok else "unavailable",
    "realExecution": ok,
    "toolPath": str(emulator),
    "artifactPath": str(apk),
    "screenshotPath": str(screenshot) if screenshot.is_file() else None,
    "deviceSerial": serial,
    "deviceProfile": profile_name,
    "interactionExecuted": interaction_ok,
    "interactionVerified": interaction_verified,
    "durationMs": int((time.monotonic() - started) * 1000),
    "detail": "APK compile/signe/installe; WebView execute; sequence utilisateur adb validee" if ok else None,
    **({} if ok else {"error": error or tail(emulator_log.read_text(encoding="utf-8", errors="replace"))}),
  }


def run_android_stages(url: str, out_dir: Path) -> list[dict[str, Any]]:
  return [run_android_stage(url, out_dir, profile) for profile in ANDROID_PROFILES]
