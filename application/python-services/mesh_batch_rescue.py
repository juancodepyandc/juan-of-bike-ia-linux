#!/usr/bin/env python
"""Aurora 3D batch rescue — runs auto_rescue_mesh on every grouped run found
by mesh_run_index. Useful when Cat 2-4 of the 3D /loop generate a series of
meshes and you want to rescue them all in one shot.

For each run with both mesh.glb and reference.png present:
    auto_rescue(mesh, reference, prompt, output_dir/<run_id>/)

The prompt for each run is read from a sidecar `<run_id>_prompt.txt` if
present, else falls back to a generic one (limits color preservation
quality but doesn't crash).

Usage:
    python mesh_batch_rescue.py --output-dir application/output/3d/rescue_batch
    python mesh_batch_rescue.py --output-dir out/ --pretty
    python mesh_batch_rescue.py --dir application/output/3d --output-dir out/

Schema: aurora.batch_rescue.v1.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DIR = REPO_ROOT / "application" / "output" / "3d"

sys.path.insert(0, str(Path(__file__).resolve().parent))
from auto_rescue_mesh import auto_rescue  # noqa: E402
from mesh_run_index import index_runs  # noqa: E402


def find_files(run: dict, role: str) -> Path | None:
    for f in run.get("files") or []:
        if f.get("role") == role:
            path = Path(f.get("path") or "")
            if not path.is_absolute():
                path = REPO_ROOT / path
            return path if path.is_file() else None
    return None


def read_sidecar_prompt(run_id: str, source_dir: Path) -> str | None:
    sidecar = source_dir / f"{run_id}_prompt.txt"
    if sidecar.is_file():
        try:
            return sidecar.read_text(encoding="utf-8").strip()
        except OSError:
            return None
    return None


def batch_rescue(source_dir: Path, output_dir: Path,
                 fallback_prompt: str = "generic 3D object") -> dict:
    if not source_dir.is_dir():
        return {"ok": False, "error": f"source dir not found: {source_dir}"}
    output_dir.mkdir(parents=True, exist_ok=True)

    idx = index_runs(source_dir)
    if not idx.get("ok"):
        return {"ok": False, "error": idx.get("error")}

    rescued = []
    skipped = []
    for run in idx.get("runs") or []:
        run_id = run["run_id"]
        if not run.get("has_mesh") or not run.get("has_reference"):
            skipped.append({
                "run_id": run_id,
                "reason": "missing mesh or reference",
            })
            continue
        mesh = find_files(run, "mesh")
        ref = find_files(run, "reference")
        if mesh is None or ref is None:
            skipped.append({
                "run_id": run_id,
                "reason": "mesh / reference path resolution failed",
            })
            continue
        prompt = read_sidecar_prompt(run_id, source_dir) or fallback_prompt
        run_out_dir = output_dir / run_id
        result = auto_rescue(mesh, ref, prompt, run_out_dir)
        rescued.append({
            "run_id": run_id,
            "ok": result.get("ok", False),
            "initial_score": result.get("initial_score"),
            "final_score": result.get("final_score"),
            "score_delta": result.get("score_delta"),
            "kind": (result.get("extraction") or {}).get("kind"),
            "final_mesh": result.get("final_mesh"),
            "error": result.get("error") if not result.get("ok") else None,
        })

    deltas = [r["score_delta"] for r in rescued
              if r.get("ok") and r.get("score_delta") is not None]
    avg_delta = round(sum(deltas) / len(deltas), 2) if deltas else 0.0

    return {
        "ok": True,
        "schema": "aurora.batch_rescue.v1",
        "source_dir": str(source_dir),
        "output_dir": str(output_dir),
        "fallback_prompt": fallback_prompt,
        "rescued_count": sum(1 for r in rescued if r.get("ok")),
        "failed_count": sum(1 for r in rescued if not r.get("ok")),
        "skipped_count": len(skipped),
        "avg_score_delta": avg_delta,
        "rescued": rescued,
        "skipped": skipped,
    }


def render_pretty(result: dict) -> str:
    if not result.get("ok"):
        return f"FAIL: {result.get('error')}\n"
    lines = [
        f"Batch rescue — {result['source_dir']} -> {result['output_dir']}",
        f"  rescued: {result['rescued_count']}, "
        f"failed: {result['failed_count']}, "
        f"skipped: {result['skipped_count']}",
        f"  avg score delta: {result['avg_score_delta']:+}",
        "",
    ]
    for r in result["rescued"]:
        if r.get("ok"):
            lines.append(
                f"  [OK] {r['run_id']:<32} kind={r.get('kind', '?')}  "
                f"score {r.get('initial_score')} -> {r.get('final_score')}  "
                f"(delta {r.get('score_delta'):+})"
            )
        else:
            lines.append(f"  [FAIL] {r['run_id']:<32} {r.get('error', '?')}")
    for s in result["skipped"]:
        lines.append(f"  [SKIP] {s['run_id']:<32} {s['reason']}")
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Aurora 3D batch rescue")
    parser.add_argument("--dir", default=str(DEFAULT_DIR),
                        help="Source directory to scan")
    parser.add_argument("--output-dir", required=True, dest="output_dir")
    parser.add_argument("--fallback-prompt", default="generic 3D object",
                        help="Used when no <run_id>_prompt.txt sidecar exists")
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args()
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
    except (AttributeError, ValueError):
        pass

    result = batch_rescue(Path(args.dir), Path(args.output_dir), args.fallback_prompt)
    if args.pretty:
        sys.stdout.write(render_pretty(result))
    else:
        sys.stdout.write(json.dumps(result, indent=2, ensure_ascii=True) + "\n")
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    sys.exit(main())
