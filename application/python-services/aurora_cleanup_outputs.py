#!/usr/bin/env python
"""Aurora 3D output cleanup — prune stale test artifacts from
`application/output/3d/`.

The output directory accumulates `_endpoint.glb`, `_selftest.glb`,
`_test.glb` variants from selftest gates and ad-hoc smoke tests. Over
time this becomes hard to navigate (47+ standalones in v79). This script
identifies and (with --apply) removes stale artifacts while preserving
the canonical:
   - {run_id}_mesh.glb (Hunyuan3D raw)
   - {run_id}_reference.png (FLUX ref)
   - {run_id}_front_synth_seed.png + _front_synthetic.png (FLUX intermediate)
   - rescue_{run_id}/*.glb (final rescued meshes)
   - cat{N}_*.glb (Cat 1-N final variants)

Defaults to --dry-run; pass --apply to actually delete.

Usage:
   python aurora_cleanup_outputs.py            # show what would go
   python aurora_cleanup_outputs.py --apply    # actually delete
   python aurora_cleanup_outputs.py --pretty   # human-readable output
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DIR = REPO_ROOT / "application" / "output" / "3d"

# Filename patterns that mark a file as expendable test artifact:
PRUNE_PATTERNS = [
    re.compile(r"_endpoint(?:_baked)?\.glb$"),
    re.compile(r"_selftest(?:_baked)?\.glb$"),
    re.compile(r"_test\.glb$"),
    re.compile(r"^aurora_cleaned\.glb$"),  # leftover from blender_bridge cleanup
]

# Filename patterns that we ALWAYS preserve, even if the prune patterns match:
PRESERVE_PATTERNS = [
    re.compile(r"^cat[0-9]+_[^/]*_(reference|reference_back|reference_left|reference_right)\.png$"),
]


def is_prunable(name: str) -> bool:
    if any(p.search(name) for p in PRESERVE_PATTERNS):
        return False
    return any(p.search(name) for p in PRUNE_PATTERNS)


def scan(directory: Path) -> dict:
    if not directory.is_dir():
        return {"ok": False, "error": f"directory not found: {directory}"}
    candidates: list[dict] = []
    keepers: list[dict] = []
    for f in sorted(directory.iterdir(), key=lambda p: p.stat().st_mtime if p.exists() else 0):
        if f.is_dir() or f.name.startswith("."):
            continue
        info = {
            "name": f.name,
            "size_bytes": int(f.stat().st_size),
            "size_mb": round(f.stat().st_size / (1024 * 1024), 2),
        }
        if is_prunable(f.name):
            candidates.append(info)
        else:
            keepers.append(info)
    total_prune_mb = round(sum(c["size_bytes"] for c in candidates) / (1024 * 1024), 2)
    return {
        "ok": True,
        "schema": "aurora.cleanup.v1",
        "directory": str(directory),
        "prune_candidates": candidates,
        "preserve_count": len(keepers),
        "prune_count": len(candidates),
        "would_free_mb": total_prune_mb,
    }


def apply_prune(report: dict, directory: Path) -> dict:
    deleted: list[str] = []
    failed: list[dict] = []
    for c in report.get("prune_candidates") or []:
        path = directory / c["name"]
        try:
            path.unlink()
            deleted.append(c["name"])
        except OSError as exc:
            failed.append({"name": c["name"], "error": str(exc)})
    return {
        "deleted_count": len(deleted),
        "freed_mb": round(sum(c["size_bytes"] for c in (report.get("prune_candidates") or [])
                              if c["name"] in deleted) / (1024 * 1024), 2),
        "deleted": deleted,
        "failed": failed,
    }


def render_pretty(report: dict, applied: dict | None = None) -> str:
    if not report.get("ok"):
        return f"FAIL: {report.get('error')}\n"
    lines = [
        f"Cleanup scan — {report['directory']}",
        f"  preserve: {report['preserve_count']} files",
        f"  prune:    {report['prune_count']} files ({report['would_free_mb']} MB)",
        "",
    ]
    for c in report["prune_candidates"]:
        lines.append(f"  - {c['name']:<55} {c['size_mb']:>8.2f} MB")
    if applied is not None:
        lines.append("")
        lines.append(f"Applied: {applied['deleted_count']} deleted, "
                     f"{applied['freed_mb']} MB freed")
        if applied.get("failed"):
            lines.append(f"Failed: {len(applied['failed'])}")
            for f in applied["failed"][:5]:
                lines.append(f"  - {f['name']}: {f['error']}")
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Aurora 3D output cleanup")
    parser.add_argument("--dir", default=str(DEFAULT_DIR))
    parser.add_argument("--apply", action="store_true",
                        help="Actually delete (default is dry-run)")
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args()
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
    except (AttributeError, ValueError):
        pass

    report = scan(Path(args.dir))
    applied = None
    if args.apply and report.get("ok"):
        applied = apply_prune(report, Path(args.dir))

    if args.pretty:
        sys.stdout.write(render_pretty(report, applied))
    else:
        out = {"scan": report}
        if applied is not None:
            out["applied"] = applied
        sys.stdout.write(json.dumps(out, indent=2, ensure_ascii=True) + "\n")
    return 0 if report.get("ok") else 1


if __name__ == "__main__":
    sys.exit(main())
