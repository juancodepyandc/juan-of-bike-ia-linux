#!/usr/bin/env python3
"""
bump-extension-version.py — auto-bump manifest.json version quand
les fichiers de l'extension changent.

Le bridge sert /api/cowork/extension/version qui retourne la version
du manifest. L'extension Aurora-Connect polle ça et déclenche un
chrome.runtime.reload() automatique quand la version change → l'user
n'a JAMAIS besoin de cliquer Recharger sur chrome://extensions.

Usage : appelé automatiquement par update-aurora-prod.bat. Compute
SHA256 de tous les fichiers de application/extension/, compare au
hash stocké dans .extension-hash.txt à la racine. Si différent →
bump la patch version dans manifest.json + écris le nouveau hash.

v82jo Pass A (pré-Phase 3).
"""
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
EXT_DIR = ROOT / "application" / "extension"
MANIFEST = EXT_DIR / "manifest.json"
HASH_FILE = ROOT / ".extension-hash.txt"


def compute_dir_hash(d: Path) -> str:
    """SHA256 de la concat triée des contenus de chaque fichier."""
    h = hashlib.sha256()
    files = sorted(p for p in d.rglob("*") if p.is_file() and not p.name.startswith("."))
    for f in files:
        h.update(str(f.relative_to(d)).encode("utf-8"))
        h.update(b"\0")
        try:
            h.update(f.read_bytes())
        except OSError:
            pass
    return h.hexdigest()


def bump_patch(version: str) -> str:
    """Bump 1.2.3 → 1.2.4. Si format inattendu, append .1."""
    parts = version.split(".")
    if len(parts) >= 3 and all(p.isdigit() for p in parts):
        parts[-1] = str(int(parts[-1]) + 1)
        return ".".join(parts)
    return version + ".1"


def main() -> int:
    if not EXT_DIR.is_dir():
        print(f"[bump-ext] Extension dir absent : {EXT_DIR}", file=sys.stderr)
        return 1
    if not MANIFEST.is_file():
        print(f"[bump-ext] manifest.json absent : {MANIFEST}", file=sys.stderr)
        return 1
    cur_hash = compute_dir_hash(EXT_DIR)
    prev_hash = HASH_FILE.read_text(encoding="utf-8").strip() if HASH_FILE.is_file() else ""
    if cur_hash == prev_hash:
        print(f"[bump-ext] Aucun changement extension. Hash {cur_hash[:8]}.")
        return 0
    # Hash différent → bump
    with open(MANIFEST, "r", encoding="utf-8") as f:
        manifest = json.load(f)
    old_version = manifest.get("version", "1.0.0")
    new_version = bump_patch(old_version)
    manifest["version"] = new_version
    with open(MANIFEST, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)
    HASH_FILE.write_text(cur_hash + "\n", encoding="utf-8")
    print(f"[bump-ext] Version {old_version} -> {new_version} (hash {cur_hash[:8]}).")
    print(f"[bump-ext] L'extension Aurora-Connect se rechargera au prochain poll (~30s).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
