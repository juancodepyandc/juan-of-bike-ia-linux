#!/usr/bin/env python
"""Aurora 3D run index — scans `application/output/3d/` and groups files by
run id (naming convention `<id>_mesh.glb`, `<id>_reference.png`,
`<id>_front_synthetic.png`, etc.) plus standalone variants like
`cat1_baked.glb`, `cat1_reshaped.glb`. Returns a JSON list of runs with
their files + sizes + mtimes + (optionally) cached scores.

Designed for the dashboard's "Recent 3D runs" section so the user can see
what's been generated, what's been rescued, and at what quality.

Schema: aurora.run_index.v1.

Usage:
    python mesh_run_index.py
    python mesh_run_index.py --dir application/output/3d
    python mesh_run_index.py --pretty
    python mesh_run_index.py --kind pc_tower --score   # also score each mesh
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from collections import defaultdict
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DIR = REPO_ROOT / "application" / "output" / "3d"

# Match files like:
#   juan_bike_1777509822533_mesh.glb
#   juan_bike_1777509822533_reference.png
#   juan_bike_1777509822533_front_synthetic.png
#   juan_bike_1777509822533_front_synth_seed.png
#   guerrier_elfique_DEMO_v77zaj.glb (no obvious id, treat as standalone)
ID_PATTERN = re.compile(r"^(.+?)_(mesh|reference|front_synthetic|front_synth_seed)\.(?:glb|png)$")


def categorize(name: str) -> tuple[str | None, str]:
    """Return (run_id, role). role one of: mesh, reference, front_synthetic,
    front_synth_seed, baked, reshaped, viewer, preview, other."""
    lower = name.lower()
    m = ID_PATTERN.match(name)
    if m:
        return m.group(1), m.group(2)
    if "_baked" in lower:
        return None, "baked"
    if "_reshaped" in lower:
        return None, "reshaped"
    if "_rescue" in lower or "rescue_" in lower:
        return None, "rescue"
    if "viewer" in lower:
        return None, "viewer"
    if "preview" in lower:
        return None, "preview"
    if name.endswith(".glb"):
        return None, "standalone_glb"
    if name.endswith(".png"):
        return None, "standalone_png"
    if name.endswith(".html"):
        return None, "standalone_html"
    return None, "other"


def stat_file(path: Path) -> dict:
    try:
        st = path.stat()
        return {
            "name": path.name,
            "path": str(path.relative_to(REPO_ROOT) if path.is_relative_to(REPO_ROOT) else path),
            "size_bytes": int(st.st_size),
            "mtime_iso": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(st.st_mtime)),
            "mtime": int(st.st_mtime),
        }
    except OSError as exc:
        return {"name": path.name, "error": str(exc)}


def maybe_score(path: Path, kind: str | None) -> dict | None:
    if kind is None or not path.suffix.lower() == ".glb":
        return None
    try:
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        from mesh_quality_score import score_mesh  # noqa: WPS433 — local helper
    except ImportError:
        return None
    try:
        result = score_mesh(path, kind)
    except Exception as exc:  # noqa: BLE001
        return {"error": str(exc)[:120]}
    if not result.get("ok"):
        return {"error": result.get("error", "")[:120]}
    return {
        "overall_score": result["overall_score"],
        "retry_recommended": result["retry_recommended"],
        "failed_axes": result.get("failed_axes") or [],
    }


def index_runs(directory: Path, kind: str | None = None,
               score_meshes: bool = False) -> dict:
    if not directory.is_dir():
        return {"ok": False, "error": f"directory not found: {directory}"}

    runs: dict[str, dict] = defaultdict(lambda: {"files": []})
    standalones: list[dict] = []

    for item in sorted(directory.iterdir(), key=lambda p: p.stat().st_mtime if p.exists() else 0):
        if item.is_dir() or item.name.startswith("."):
            continue
        run_id, role = categorize(item.name)
        meta = stat_file(item)
        meta["role"] = role
        if score_meshes and role == "mesh":
            score = maybe_score(item, kind)
            if score:
                meta["score"] = score
        if run_id is None:
            standalones.append(meta)
        else:
            runs[run_id]["files"].append(meta)

    # Compute per-run latest mtime + total size
    runs_list: list[dict] = []
    for run_id, payload in runs.items():
        files = payload["files"]
        latest = max((f.get("mtime", 0) for f in files), default=0)
        total_size = sum(f.get("size_bytes", 0) for f in files)
        roles = {f["role"] for f in files}
        runs_list.append({
            "run_id": run_id,
            "files": files,
            "latest_mtime_iso": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(latest)) if latest else None,
            "total_size_bytes": total_size,
            "has_mesh": "mesh" in roles,
            "has_reference": "reference" in roles,
        })
    runs_list.sort(key=lambda r: (r.get("latest_mtime_iso") or ""), reverse=True)
    standalones.sort(key=lambda f: f.get("mtime", 0), reverse=True)

    return {
        "ok": True,
        "schema": "aurora.run_index.v1",
        "directory": str(directory),
        "scored": score_meshes,
        "kind_for_scoring": kind if score_meshes else None,
        "run_count": len(runs_list),
        "standalone_count": len(standalones),
        "runs": runs_list,
        "standalones": standalones,
    }


def render_pretty(result: dict) -> str:
    if not result.get("ok"):
        return f"FAIL: {result.get('error')}\n"
    lines = [
        f"3D run index — {result['directory']}",
        f"  {result['run_count']} runs, {result['standalone_count']} standalone files",
        "",
    ]
    for run in result["runs"]:
        lines.append(f"  [{run.get('latest_mtime_iso', '?')}] {run['run_id']}  "
                     f"({len(run['files'])} files, {run['total_size_bytes']:,} bytes)")
        for f in run["files"]:
            score = f.get("score")
            score_str = f"  score={score['overall_score']}" if score else ""
            lines.append(f"      - {f['role']:<18} {f['name']}{score_str}")
    if result["standalones"]:
        lines.append("")
        lines.append(f"  Standalone files ({result['standalone_count']}):")
        for f in result["standalones"][:20]:
            lines.append(f"      - {f['role']:<18} {f['name']}")
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Aurora 3D run index")
    parser.add_argument("--dir", default=str(DEFAULT_DIR))
    parser.add_argument("--score", action="store_true",
                        help="Also run mesh_quality_score on each .glb (slow)")
    parser.add_argument("--kind", default=None,
                        help="Subject kind for scoring (only with --score)")
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args()
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
    except (AttributeError, ValueError):
        pass
    result = index_runs(Path(args.dir), args.kind, args.score)
    if args.pretty:
        sys.stdout.write(render_pretty(result))
    else:
        sys.stdout.write(json.dumps(result, indent=2, ensure_ascii=True) + "\n")
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    sys.exit(main())
