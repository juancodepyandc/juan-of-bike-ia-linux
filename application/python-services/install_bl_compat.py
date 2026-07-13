"""Installe le shim de compat Blender 5.x (`_bl_compat_startup.py`) dans le dossier
`scripts/startup/` de CHAQUE version de Blender présente dans la config utilisateur.

Pourquoi : Blender 5.0+ a supprimé `Action.fcurves`. 100+ générateurs `proc_*.py`
animés d'AuroraIA (grande roue, moulin, carrousel, horloge à pendule, etc.) bouclent
sur `action.fcurves` pour poser l'interpolation LINEAR — sur Blender 5.1 ça lève
AttributeError, le script build.py CRASHE avant l'export, et la génération échoue
(AUCUN GLB). Le shim, chargé au démarrage de toute invocation Blender, restaure l'API.

Idempotent. À lancer une fois après install/màj de Blender :
    python install_bl_compat.py
Retourne le nombre de dossiers startup où le shim a été (re)copié.
"""
from __future__ import annotations
import shutil
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
SHIM_SRC = _HERE / "_bl_compat_startup.py"
DST_NAME = "aurora_fcurves_compat.py"


def _blender_config_roots() -> list[Path]:
    roots: list[Path] = []
    home = Path.home()
    # Linux / macOS
    roots += [home / ".config" / "blender"]
    roots += [home / "Library" / "Application Support" / "Blender"]
    # Windows
    import os
    appdata = os.environ.get("APPDATA")
    if appdata:
        roots.append(Path(appdata) / "Blender Foundation" / "Blender")
    return [r for r in roots if r.is_dir()]


def install() -> int:
    if not SHIM_SRC.is_file():
        print(f"BL_COMPAT_FAIL: source manquante {SHIM_SRC}", file=sys.stderr)
        return 0
    n = 0
    for root in _blender_config_roots():
        for ver_dir in root.iterdir():
            if not ver_dir.is_dir():
                continue
            startup = ver_dir / "scripts" / "startup"
            startup.mkdir(parents=True, exist_ok=True)
            shutil.copy2(SHIM_SRC, startup / DST_NAME)
            print(f"BL_COMPAT_OK: {startup / DST_NAME}")
            n += 1
    if n == 0:
        print("BL_COMPAT_WARN: aucune config Blender trouvée")
    return n


if __name__ == "__main__":
    sys.exit(0 if install() >= 0 else 1)
