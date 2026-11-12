#!/usr/bin/env python3
"""Localisation unique de l'exécutable Blender pour les services Python d'Aurora.

Ordre de recherche (le premier exécutable réel l'emporte) :
  1. variable AURORA_BLENDER (ou BLENDER_BIN / BLENDER_EXE) : fichier ou dossier ;
  2. Blender embarqué dans application/_blender (version la plus récente d'abord) ;
  3. ~/.local/bin/blender (convention du poste Linux), puis PATH ;
  4. installations standard : Program Files (toutes versions), Steam, Scoop, /opt,
     /snap, ~/Applications, /Applications (macOS) ;
  5. le bureau de l'utilisateur : dossier XDG du bureau (~/Bureau en français, lu dans
     ~/.config/user-dirs.dirs), ~/Desktop, bureaux OneDrive — dossier portable extrait
     (blender-*/blender), AppImage, lanceur .desktop (ligne Exec=) ou raccourci .lnk.

Le résultat est mis en cache pour le processus. ensure_env() l'exporte dans
AURORA_BLENDER pour que tous les sous-processus (qui lisent déjà cette variable)
utilisent le même Blender. `python blender_locator.py` affiche où Blender a été trouvé.
"""
from __future__ import annotations

import json
import os
import re
import shlex
import shutil
import sys
from functools import lru_cache
from pathlib import Path

APP_ROOT = Path(__file__).resolve().parents[1]
ENV_VARS = ("AURORA_BLENDER", "BLENDER_BIN", "BLENDER_EXE")
_VERSION = re.compile(r"(\d+)\.(\d+)(?:\.(\d+))?")
_LNK_PATH = re.compile(r"(?:[A-Za-z]:|%[A-Za-z_()]+%)\\[^\x00-\x1f\"<>|*?]{0,260}?blender(?:-launcher)?\.exe", re.I)


def _version_key(path: Path) -> tuple[int, int, int]:
    for part in reversed(Path(path).parts):
        m = _VERSION.search(part)
        if m:
            return tuple(int(x or 0) for x in m.groups())  # type: ignore[return-value]
    return (0, 0, 0)


def _is_exe(path: Path) -> bool:
    try:
        if not path.is_file():
            return False
        if os.name == "nt":
            return path.suffix.lower() == ".exe"
        return os.access(path, os.X_OK)
    except OSError:
        return False


def _normalize(path: Path) -> Path:
    # blender-launcher.exe ouvre une fenêtre ; les scripts sans interface ont besoin de blender.exe
    if path.name.lower() == "blender-launcher.exe":
        sibling = path.with_name("blender.exe")
        if _is_exe(sibling):
            return sibling
    return path


def _from_dir(folder: Path) -> Path | None:
    for rel in ("blender.exe", "blender", "Blender.app/Contents/MacOS/Blender", "Contents/MacOS/Blender"):
        candidate = folder / rel
        if _is_exe(candidate):
            return candidate
    return None


def _from_value(value: str | None) -> Path | None:
    if not value:
        return None
    path = Path(os.path.expandvars(os.path.expanduser(value.strip().strip('"'))))
    if path.is_dir():
        return _from_dir(path)
    return _normalize(path) if _is_exe(path) else None


def _bundled() -> list[Path]:
    root = APP_ROOT / "_blender"
    try:
        folders = sorted((p for p in root.glob("blender-*") if p.is_dir()), key=_version_key, reverse=True)
    except OSError:
        return []
    return [exe for exe in (_from_dir(f) for f in folders) if exe]


def _standard_installs() -> list[Path]:
    home = Path.home()
    found: list[Path] = []
    if os.name == "nt":
        bases = {os.environ.get(k) for k in ("ProgramFiles", "ProgramW6432", "ProgramFiles(x86)")}
        bases |= {r"C:\Program Files", r"C:\Program Files (x86)"}
        local = os.environ.get("LOCALAPPDATA")
        if local:
            bases.add(str(Path(local) / "Programs"))
        for base in filter(None, bases):
            root = Path(base)
            try:
                found += sorted(root.glob("Blender Foundation/Blender */blender.exe"), key=_version_key, reverse=True)
            except OSError:
                pass
            found.append(root / "Steam" / "steamapps" / "common" / "Blender" / "blender.exe")
        found.append(home / "scoop" / "apps" / "blender" / "current" / "blender.exe")
    else:
        found.append(home / ".local" / "bin" / "blender")
        found.append(Path("/snap/bin/blender"))
        for pattern_root, pattern in ((Path("/opt"), "blender*/blender"), (home, "blender*/blender"),
                                      (home / "Applications", "[Bb]lender*.AppImage"), (home / "Applications", "blender*/blender")):
            try:
                found += sorted(pattern_root.glob(pattern), key=_version_key, reverse=True)
            except OSError:
                pass
        found.append(Path("/Applications/Blender.app/Contents/MacOS/Blender"))
    return [_normalize(p) for p in found if _is_exe(p)]


def desktop_dirs() -> list[Path]:
    """Dossiers de bureau possibles (XDG, français, anglais, OneDrive), existants et sans doublon."""
    home = Path.home()
    dirs: list[Path] = []
    cfg = Path(os.environ.get("XDG_CONFIG_HOME") or home / ".config") / "user-dirs.dirs"
    try:
        m = re.search(r'^XDG_DESKTOP_DIR="?([^"\n]+)"?', cfg.read_text(encoding="utf-8", errors="replace"), re.M)
        if m:
            dirs.append(Path(m.group(1).replace("$HOME", str(home))))
    except OSError:
        pass
    for name in ("Bureau", "Desktop"):
        dirs.append(home / name)
    for onedrive in filter(None, (os.environ.get("OneDrive"), os.environ.get("OneDriveConsumer"), str(home / "OneDrive"))):
        for name in ("Bureau", "Desktop"):
            dirs.append(Path(onedrive) / name)
    seen: set[str] = set()
    out: list[Path] = []
    for d in dirs:
        key = os.path.normcase(str(d))
        if key not in seen and d.is_dir():
            seen.add(key)
            out.append(d)
    return out


def _exec_from_desktop_entry(entry: Path) -> Path | None:
    try:
        text = entry.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None
    m = re.search(r"^Exec=(.+)$", text, re.M)
    if not m:
        return None
    try:
        tokens = [t for t in shlex.split(m.group(1)) if not t.startswith("%")]
    except ValueError:
        tokens = m.group(1).split()
    if not tokens or tokens[0] in ("env", "flatpak"):
        return None
    first = tokens[0]
    if os.sep in first or "/" in first:
        path = Path(os.path.expanduser(first))
        return _normalize(path) if _is_exe(path) else None
    which = shutil.which(first)
    return Path(which) if which and "blender" in first.lower() else None


def lnk_targets(data: bytes) -> list[str]:
    """Chemins de blender.exe contenus dans un raccourci Windows (.lnk), ANSI ou UTF-16."""
    texts = [data.decode("latin-1", errors="ignore")]
    try:
        texts.append(data.decode("utf-16-le", errors="ignore"))
    except Exception:  # noqa: BLE001
        pass
    found: list[str] = []
    for text in texts:
        for m in _LNK_PATH.finditer(text):
            value = os.path.expandvars(m.group(0))
            if value not in found:
                found.append(value)
    return found


def _from_desktop(folder: Path) -> Path | None:
    try:
        entries = sorted(folder.iterdir(), key=lambda p: (_version_key(p), p.name), reverse=True)
    except OSError:
        return None
    for entry in entries:
        name = entry.name.lower()
        if "blender" not in name:
            continue
        try:
            if entry.is_dir():
                exe = _from_dir(entry)
                if exe is None:
                    # un niveau de plus : ~/Bureau/Blender/blender-4.2.12-linux-x64/blender
                    for sub in sorted((s for s in entry.iterdir() if s.is_dir()), key=_version_key, reverse=True):
                        exe = _from_dir(sub)
                        if exe:
                            break
                if exe:
                    return exe
            elif name.endswith(".desktop"):
                exe = _exec_from_desktop_entry(entry)
                if exe:
                    return exe
            elif name.endswith(".lnk"):
                for target in lnk_targets(entry.read_bytes()[:65536]):
                    exe = _from_value(target)
                    if exe:
                        return exe
            elif _is_exe(entry):  # AppImage, exécutable posé sur le bureau
                return _normalize(entry)
        except OSError:
            continue
    return None


def locate() -> tuple[str | None, str]:
    """(chemin, origine) du Blender retenu, sans cache."""
    for var in ENV_VARS:
        exe = _from_value(os.environ.get(var))
        if exe:
            return str(exe), var
    for exe in _bundled():
        return str(exe), "embarqué (application/_blender)"
    local_bin = Path.home() / ".local" / "bin" / "blender"
    if _is_exe(local_bin):
        return str(local_bin), "~/.local/bin"
    which = shutil.which("blender")
    if which:
        return which, "PATH"
    for exe in _standard_installs():
        return str(exe), "installation standard"
    for folder in desktop_dirs():
        exe = _from_desktop(folder)
        if exe:
            return str(exe), f"bureau ({folder})"
    return None, "introuvable"


@lru_cache(maxsize=1)
def _cached() -> tuple[str | None, str]:
    return locate()


def find_blender(refresh: bool = False) -> str | None:
    if refresh:
        _cached.cache_clear()
    return _cached()[0]


def ensure_env() -> str | None:
    """Exporte le Blender trouvé dans AURORA_BLENDER (fichier exécutable) pour les sous-processus."""
    current = os.environ.get("AURORA_BLENDER")
    exe = find_blender()
    if exe and (not current or not _is_exe(Path(current))):
        os.environ["AURORA_BLENDER"] = exe
    return exe


if __name__ == "__main__":
    path, origin = locate()
    sys.stdout.write(json.dumps({"blender": path, "origine": origin, "bureaux": [str(d) for d in desktop_dirs()]}, ensure_ascii=False) + "\n")
    raise SystemExit(0 if path else 1)
