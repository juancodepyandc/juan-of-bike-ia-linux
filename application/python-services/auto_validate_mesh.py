#!/usr/bin/env python
"""Aurora 3D autonomous mesh validator — closes the autonomy loop.

Takes a generated GLB path + the original prompt, derives the subject kind
itself, scores the mesh, and outputs a retry decision plus a recommended
next pipeline. No human classification needed — designed to plug into the
post-Hunyuan3D / post-DreamGaussian step in ModelView.tsx (or any
orchestrator).

Pipeline rotation logic:
    Hunyuan3D fails on color/aspect → DreamGaussian (per v78j routing)
    DreamGaussian fails               → Procedural Blender (mechanism kinds)
                                          OR multi-view + Hunyuan3D retry
    Anything fails on manifold        → mesh_postprocess auto-fix first

Schema: aurora.auto_validate.v1.

Usage:
    python auto_validate_mesh.py --mesh path.glb --prompt "<prompt>"
    python auto_validate_mesh.py --mesh path.glb --prompt "<prompt>" --pretty
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parent))
from mesh_quality_score import score_mesh  # noqa: E402
from subject_kind_extractor import extract_kind  # noqa: E402


# Maps current pipeline + failure type -> recommended next pipeline.
# Keys: ("current_pipeline", "primary_failure"). The orchestrator reads the
# value to decide what to retry with. None = stop, accept the mesh.
RETRY_GRAPH: dict[tuple[str, str], str | None] = {
    # TRELLIS.2 est la seule voie de reconstruction: pas de second generateur
    # vers lequel basculer. Un echec de couleur/silhouette remonte tel quel
    # (le pipeline aurora_3d_pipeline.py gere deja sa propre boucle de
    # re-essai TRELLIS avec ancrage renforce); seul un defaut de manifold
    # beneficie encore d'un post-traitement local.
    ("trellis2", "color_richness"):    None,
    ("trellis2", "silhouette_aspect"): None,
    ("trellis2", "manifold_health"):   "mesh_postprocess",
    ("dreamgaussian", "color_richness"): "procedural_or_multiview",
    ("dreamgaussian", "silhouette_aspect"): "procedural_or_multiview",
    ("dreamgaussian", "manifold_health"): "mesh_postprocess",
    ("procedural", "color_richness"):   None,  # procedural rarely has color anyway
    ("procedural", "manifold_health"):  "mesh_postprocess",
    ("mesh_postprocess", "manifold_health"): None,  # last resort
}


def primary_failure(failed_axes: list[str]) -> str | None:
    """Pick the most actionable failed axis. Color is the most user-visible
    failure — prioritize it. Silhouette next, then manifold."""
    priority = ("color_richness", "silhouette_aspect", "manifold_health")
    for axis in priority:
        if axis in failed_axes:
            return axis
    return failed_axes[0] if failed_axes else None


def recommend_next_pipeline(current: str, failed_axes: list[str]) -> dict:
    """Return {next_pipeline, reason} for the orchestrator to act on."""
    failure = primary_failure(failed_axes)
    if failure is None:
        return {"next_pipeline": None, "reason": "no failed axes"}
    next_pipe = RETRY_GRAPH.get((current, failure))
    if next_pipe is None:
        return {
            "next_pipeline": None,
            "reason": f"no retry path for ({current}, {failure}); accept current mesh",
        }
    return {
        "next_pipeline": next_pipe,
        "reason": f"current={current}, primary_failure={failure} -> {next_pipe}",
    }


def auto_validate(mesh_path: str | Path, prompt: str, current_pipeline: str = "trellis2") -> dict:
    extraction = extract_kind(prompt)
    kind = extraction["kind"]
    score = score_mesh(mesh_path, kind)
    if not score.get("ok"):
        return {
            "ok": False,
            "schema": "aurora.auto_validate.v1",
            "error": score.get("error"),
            "extraction": extraction,
        }
    failed_axes = score.get("failed_axes") or []
    rec = recommend_next_pipeline(current_pipeline, failed_axes)
    return {
        "ok": True,
        "schema": "aurora.auto_validate.v1",
        "mesh_path": str(mesh_path),
        "prompt": prompt,
        "current_pipeline": current_pipeline,
        "extraction": extraction,
        "score": {
            "overall_score": score["overall_score"],
            "retry_recommended": score["retry_recommended"],
            "failed_axes": failed_axes,
            "retry_reasons": score.get("retry_reasons") or [],
            "axes": {k: v["score"] for k, v in score["scores"].items()},
        },
        "next_action": (
            {"action": "retry_pipeline", **rec}
            if score["retry_recommended"] and rec["next_pipeline"]
            else {"action": "accept", **rec}
        ),
    }


def render_pretty(result: dict) -> str:
    if not result.get("ok"):
        return f"FAIL: {result.get('error')}\n"
    lines = [
        f"Auto-validate — {result['mesh_path']}",
        f"Prompt: {result['prompt']}",
        f"Extracted kind: {result['extraction']['kind']} "
        f"(confidence {result['extraction']['confidence']}, "
        f"matched '{result['extraction']['matched_pattern']}')",
        f"Current pipeline: {result['current_pipeline']}",
        f"Overall score: {result['score']['overall_score']} / 100",
        "",
    ]
    for axis, sc in result["score"]["axes"].items():
        lines.append(f"  {axis:<20} {sc:>3} / 100")
    if result["score"]["failed_axes"]:
        lines.append(f"\nFailed axes: {result['score']['failed_axes']}")
    lines.append("")
    action = result["next_action"]
    if action["action"] == "retry_pipeline":
        lines.append(f"DECISION: retry with {action['next_pipeline']}")
        lines.append(f"Reason:   {action['reason']}")
    else:
        lines.append("DECISION: accept current mesh")
        lines.append(f"Reason:   {action.get('reason')}")
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Aurora autonomous mesh validator")
    parser.add_argument("--mesh", required=True, help="GLB path (relative or absolute)")
    parser.add_argument("--prompt", required=True, help="Original 3D prompt")
    parser.add_argument("--pipeline", default="trellis2",
                        choices=("trellis2", "dreamgaussian", "procedural", "mesh_postprocess"),
                        help="Which pipeline produced the mesh")
    parser.add_argument("--pretty", action="store_true",
                        help="Human-readable output instead of JSON")
    args = parser.parse_args()
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
    except (AttributeError, ValueError):
        pass

    result = auto_validate(args.mesh, args.prompt, args.pipeline)
    if args.pretty:
        sys.stdout.write(render_pretty(result))
    else:
        sys.stdout.write(json.dumps(result, indent=2, ensure_ascii=True) + "\n")
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    sys.exit(main())
