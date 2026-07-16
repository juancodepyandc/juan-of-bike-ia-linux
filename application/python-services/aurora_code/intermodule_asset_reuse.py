"""Reuse a validated Code asset family without crossing bundle boundaries."""
from __future__ import annotations

import copy
import json
import pathlib
import re
import shutil
from typing import Any


def _slug(value: str) -> str:
    return re.sub(r"[^a-z0-9_-]+", "-", value.lower()).strip("-")[:80]


def _inside(path: pathlib.Path, parent: pathlib.Path) -> bool:
    try:
        path.relative_to(parent)
        return True
    except ValueError:
        return False


def _copy_entry(
    entry: dict[str, Any],
    root: pathlib.Path,
    source_dir: pathlib.Path,
    target_dir: pathlib.Path,
) -> bool:
    storage_path = entry.get("storagePath")
    if not isinstance(storage_path, str):
        return False
    source = (root / storage_path).resolve()
    if not source.is_file() or not _inside(source, source_dir):
        return False
    relative = source.relative_to(source_dir)
    target = target_dir / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)
    entry["path"] = f"assets/generated/{target_dir.name}/{relative.as_posix()}"
    entry["storagePath"] = target.relative_to(root).as_posix()
    entry["previewUrl"] = f"/api/code/assets/file/{target_dir.name}/{relative.as_posix()}"
    entry["bytes"] = target.stat().st_size
    return True


def reuse_asset_from_bundle(
    root: pathlib.Path,
    target_dir: pathlib.Path,
    source_run_id: str,
    kind: str,
) -> tuple[dict[str, Any] | None, dict[str, Any]]:
    started_detail: dict[str, Any] = {
        "requestedEndpoint": "asset-bundle-cache",
        "actualEndpoint": "asset-bundle-cache",
        "sourceRunId": source_run_id,
    }
    source_name = _slug(source_run_id)
    source_dir = (root / "output" / "code_assets" / source_name).resolve()
    manifest = source_dir / "asset-bundle.json"
    try:
        if not source_name or not manifest.is_file():
            raise FileNotFoundError(f"bundle source introuvable: {source_run_id}")
        payload = json.loads(manifest.read_text(encoding="utf-8"))
        source_asset = next(
            asset for asset in payload.get("assets", [])
            if isinstance(asset, dict) and asset.get("kind") == kind
        )
        asset = copy.deepcopy(source_asset)
        if not _copy_entry(asset, root, source_dir, target_dir):
            raise ValueError("fichier principal absent ou hors bundle")
        variants = asset.get("variants")
        if isinstance(variants, list):
            for variant in variants:
                if not isinstance(variant, dict) or not _copy_entry(variant, root, source_dir, target_dir):
                    raise ValueError("variante absente ou hors bundle")
        for key in ("srcset", "projectSrcset"):
            if isinstance(asset.get(key), str):
                asset[key] = asset[key].replace(source_name, target_dir.name)
        metadata = asset.get("metadata") if isinstance(asset.get("metadata"), dict) else {}
        asset["metadata"] = {**metadata, "reusedFromRunId": source_name}
        started_detail["reusedExistingAsset"] = True
        return asset, started_detail
    except Exception as error:
        started_detail["reuseError"] = str(error)
        return None, started_detail


def reuse_or_generate(
    root: pathlib.Path,
    target_dir: pathlib.Path,
    source_run_id: str,
    kind: str,
    producer,
) -> tuple[dict[str, Any] | None, dict[str, Any]]:
    if not source_run_id:
        return producer()
    asset, reuse_detail = reuse_asset_from_bundle(root, target_dir, source_run_id, kind)
    if asset:
        return asset, reuse_detail
    asset, detail = producer()
    detail["reuseError"] = reuse_detail.get("reuseError")
    return asset, detail


def requested_asset_kinds(payload: dict[str, Any], supported: tuple[str, ...]) -> list[str]:
    requested = payload.get("requestedKinds")
    if not isinstance(requested, list):
        return list(supported)
    return list(dict.fromkeys(kind for kind in requested if kind in supported))
