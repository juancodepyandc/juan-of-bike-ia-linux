"""Persist immutable mission files for authenticated, resumable delivery."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import time
from uuid import uuid4


ARTIFACT_TTL_SECONDS = 48 * 3600      # artifacts older than this are pruned
ARTIFACT_MAX_COUNT = 512             # hard cap on the number of descriptors kept


def artifact_root() -> Path:
    return Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local/share")) / "aurora/artifacts"


def _prune_artifacts(root: Path) -> None:
    """Bound artifact retention: drop stale tokens and cap directory growth."""
    now = time.time()
    try:
        candidates = sorted(
            (f for f in root.iterdir() if f.suffix == ".json"),
            key=lambda p: p.stat().st_mtime, reverse=True,
        )
    except OSError:
        return
    stale = [p for p in candidates if now - p.stat().st_mtime > ARTIFACT_TTL_SECONDS]
    # Keep the newest ARTIFACT_MAX_COUNT descriptors even if > TTL.
    excess = candidates[len(stale):][ARTIFACT_MAX_COUNT:]
    for meta in stale + excess:
        token = meta.stem
        meta.unlink(missing_ok=True)
        (root / f"{token}.bin").unlink(missing_ok=True)
        (root / f"{token}.part").unlink(missing_ok=True)


def publish_artifact(source: Path, filename: str, mission_id: str) -> dict:
    """Snapshot one file in bounded memory; return its transfer descriptor."""
    root = artifact_root()
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    token = uuid4().hex
    target = root / f"{token}.bin"
    partial = root / f"{token}.part"
    digest = hashlib.sha256()
    size = 0
    try:
        with source.open("rb") as reader, partial.open("xb") as writer:
            while chunk := reader.read(1024 * 1024):
                writer.write(chunk)
                digest.update(chunk)
                size += len(chunk)
        partial.replace(target)
        descriptor = {
            "filename": filename, "size": size, "sha256": digest.hexdigest(),
            "url": f"/api/cli/artifacts/{token}", "mission_id": mission_id,
        }
        (root / f"{token}.json").write_text(json.dumps(descriptor), encoding="utf-8")
        _prune_artifacts(root)
        return descriptor
    except Exception:
        partial.unlink(missing_ok=True)
        target.unlink(missing_ok=True)
        raise


def load_artifact(token: str) -> tuple[Path, dict]:
    if not re.fullmatch(r"[0-9a-f]{32}", token):
        raise FileNotFoundError("Unknown artifact")
    root = artifact_root()
    metadata = json.loads((root / f"{token}.json").read_text(encoding="utf-8"))
    path = root / f"{token}.bin"
    if not path.is_file() or path.stat().st_size != metadata["size"]:
        raise FileNotFoundError("Incomplete artifact")
    return path, metadata
