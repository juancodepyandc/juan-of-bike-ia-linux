#!/usr/bin/env python3
"""Check/materialize Markdown compatibility files from ARCHITECTURE_MAITRE.md.

Default operation is read-only. --write updates only explicitly declared exports.
--check-code compares audited source hashes; it never blesses stale prose.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
MASTER = ROOT / "ARCHITECTURE_MAITRE.md"
INVENTORY = ROOT / "scripts/documentation/source_inventory.json"
ROOTS = {"AuroraIA": ROOT, "aurora-remote-cli": ROOT.parent / "aurora-remote-cli",
         "aurora-live": ROOT.parent / "aurora-live"}
EXPORT = re.compile(
    r'^<!-- AURORA_EXPORT (\{[^\n]+\}) -->\n'
    r'`{10}markdown\n(.*?)\n`{10}\n<!-- /AURORA_EXPORT -->$', re.M | re.S)


def digest(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def exports(text: str) -> list[tuple[dict, Path, bytes]]:
    result = []
    seen = set()
    for match in EXPORT.finditer(text):
        meta = json.loads(match.group(1))
        repo, rel = meta["repo"], Path(meta["path"])
        if repo not in ROOTS or rel.is_absolute() or ".." in rel.parts or rel.suffix != ".md":
            raise ValueError(f"Invalid export target: {meta!r}")
        target = ROOTS[repo] / rel
        if target == MASTER or target in seen:
            raise ValueError(f"Duplicate or recursive export: {target}")
        if target.is_symlink() or target.resolve() != target:
            raise ValueError(f"Symlink export refused: {target}")
        seen.add(target)
        body = match.group(2)
        if meta.get("final_newline", True):
            body += "\n"
        result.append((meta, target, body.encode("utf-8")))
    if not result or len(result) != text.count("<!-- AURORA_EXPORT "):
        raise ValueError("Missing or malformed export block")
    return result


def preserve_live_status(expected: bytes, current: bytes) -> bytes:
    """The publisher owns dynamic STATUS content, not the documentation source."""
    pattern = rb"<!--STATUS-->.*?<!--/STATUS-->"
    found = re.search(pattern, current, re.S)
    if found is None or re.search(pattern, expected, re.S) is None:
        raise ValueError("Missing live STATUS block")
    return re.sub(pattern, lambda _: found.group(0), expected, count=1, flags=re.S)


def atomic_write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    mode = path.stat().st_mode & 0o777 if path.exists() else 0o644
    fd, temp = tempfile.mkstemp(prefix=".doc-master-", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(data)
        os.chmod(temp, mode)
        os.replace(temp, path)
    finally:
        if os.path.exists(temp):
            os.unlink(temp)


def check_code() -> int:
    snapshot = json.loads(INVENTORY.read_text(encoding="utf-8"))
    changed = []
    for item in snapshot["files"]:
        path = ROOTS[item["repo"]] / item["path"]
        if not path.is_file() or digest(path.read_bytes()) != item["sha256"]:
            changed.append(f'{item["repo"]}/{item["path"]}')
    if changed:
        print("Source drift: review affected master sections before updating the snapshot.")
        for name in changed:
            print(name)
        return 1
    print(f'OK: {len(snapshot["files"])} audited source hashes match.')
    print("This check covers the indexed files, not unindexed additions or runtime behavior.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true", help="materialize the declared exports")
    parser.add_argument("--check-code", action="store_true", help="check indexed source hashes")
    args = parser.parse_args()
    if args.check_code:
        return check_code()
    # Validate ALL targets before writing anything.
    planned = []
    for meta, path, body in exports(MASTER.read_text(encoding="utf-8")):
        current = path.read_bytes() if path.exists() else None
        if meta.get("preserve_live_status") and current is not None:
            body = preserve_live_status(body, current)
        if current != body:
            planned.append((path, body))
    if args.write:
        for path, body in planned:
            atomic_write(path, body)
            print(f"Updated: {path}")
        print(f"OK: {len(planned)} export(s) updated. No source code or models modified.")
        return 0
    for path, _ in planned:
        print(f"Export differs: {path}")
    if planned:
        print("Review the master, then run with --write to synchronize these files.")
        return 1
    print("OK: all Markdown compatibility exports match the master.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ValueError, OSError, KeyError, json.JSONDecodeError) as exc:
        print(f"Documentation error: {exc}", file=sys.stderr)
        raise SystemExit(2)
