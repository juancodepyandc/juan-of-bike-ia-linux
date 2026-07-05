#!/usr/bin/env python
"""Aurora 3D mesh comparator — score two GLBs side-by-side, output the
delta per axis. Useful for tracking improvement across rescue stages
(initial vs baked vs reshaped) or comparing two pipeline outputs
(Hunyuan3D vs DreamGaussian).

Usage:
    python mesh_compare.py --left orig.glb --right baked.glb --kind pc_tower
    python mesh_compare.py --left a.glb --right b.glb --kind humanoid --pretty

Schema: aurora.mesh_compare.v1
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parent))
from mesh_quality_score import score_mesh  # noqa: E402


def compare(left: Path, right: Path, kind: str = "generic") -> dict:
    left_score = score_mesh(left, kind)
    right_score = score_mesh(right, kind)
    if not left_score.get("ok"):
        return {"ok": False, "error": f"left: {left_score.get('error')}"}
    if not right_score.get("ok"):
        return {"ok": False, "error": f"right: {right_score.get('error')}"}

    axes = ("color_richness", "geometric_density", "silhouette_aspect",
            "manifold_health", "surface_quality")
    deltas: dict[str, dict] = {}
    for axis in axes:
        l_score = left_score["scores"][axis]["score"]
        r_score = right_score["scores"][axis]["score"]
        deltas[axis] = {
            "left": l_score,
            "right": r_score,
            "delta": r_score - l_score,
        }
    overall_delta = round(right_score["overall_score"] - left_score["overall_score"], 1)

    return {
        "ok": True,
        "schema": "aurora.mesh_compare.v1",
        "subject_kind": kind,
        "left": {
            "path": str(left),
            "overall_score": left_score["overall_score"],
            "failed_axes": left_score.get("failed_axes") or [],
        },
        "right": {
            "path": str(right),
            "overall_score": right_score["overall_score"],
            "failed_axes": right_score.get("failed_axes") or [],
        },
        "overall_delta": overall_delta,
        "axis_deltas": deltas,
        "winner": (
            "right" if overall_delta > 0
            else "left" if overall_delta < 0
            else "tie"
        ),
    }


def render_pretty(result: dict) -> str:
    if not result.get("ok"):
        return f"FAIL: {result.get('error')}\n"
    lines = [
        f"Mesh compare — kind: {result['subject_kind']}",
        f"  left:  {result['left']['path']}",
        f"  right: {result['right']['path']}",
        "",
        f"  overall:    {result['left']['overall_score']:>5}  ->  "
        f"{result['right']['overall_score']:>5}  ({result['overall_delta']:+})",
        "",
        f"  {'axis':<22} {'left':>5} {'right':>5} {'delta':>7}",
        "  " + "-" * 44,
    ]
    for axis, d in result["axis_deltas"].items():
        delta_sign = f"+{d['delta']}" if d["delta"] > 0 else str(d["delta"])
        lines.append(
            f"  {axis:<22} {d['left']:>5} {d['right']:>5} {delta_sign:>7}"
        )
    lines.append("")
    lines.append(f"  WINNER: {result['winner']}")
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Aurora 3D mesh comparator")
    parser.add_argument("--left", required=True)
    parser.add_argument("--right", required=True)
    parser.add_argument("--kind", default="generic")
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args()
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
    except (AttributeError, ValueError):
        pass

    result = compare(Path(args.left), Path(args.right), args.kind)
    if args.pretty:
        sys.stdout.write(render_pretty(result))
    else:
        sys.stdout.write(json.dumps(result, indent=2, ensure_ascii=True) + "\n")
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    sys.exit(main())
