#!/usr/bin/env python
"""Aurora 3D color preservation diagnostic — pinpoints where in the pipeline
the colors collapse (reference synthesis was correct, generated mesh came
out monochrome).

Compares:
    1. Reference image (PNG): unique colors + variance + dominant palette
    2. Generated mesh (GLB): vertex color unique count + variance + palette
    3. (Optional) Post-processed mesh: same metrics

Outputs a JSON verdict identifying the lossy stage:
    "stage_lost": "generation" | "post_process" | "none"
    "ref_color_count": <int>
    "mesh_color_count": <int>
    "color_loss_ratio": <float>  # 0.0 = perfect, 1.0 = total loss

Schema: aurora.color_diagnostic.v1.

Usage:
    python mesh_color_diagnostic.py \\
        --reference path/to/ref.png --mesh path/to/mesh.glb
    python mesh_color_diagnostic.py \\
        --reference ref.png --mesh hunyuan.glb --post-mesh post.glb --pretty
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def quantize_colors(arr, buckets: int = 16):
    """Quantize an Nx3 RGB array into <buckets>^3 buckets and return the
    set of unique bucket triples + Counter."""
    import numpy as np
    a = np.asarray(arr).astype(int)
    if a.ndim != 2 or a.shape[1] < 3:
        return [], 0, 0.0
    rgb = a[:, :3]
    step = 256 // buckets
    quantized = (rgb // step).astype(int)
    unique = np.unique(quantized.view([("", quantized.dtype)] * 3))
    variance = float(rgb.astype(float).var(axis=0).sum())
    # Force int conversion of length to avoid numpy int64 leaking via .tolist().
    return unique.tolist(), int(len(unique)), round(variance, 4)


def palette_distribution(arr, top_n: int = 6):
    """Return the top_n most frequent quantized colors and their share."""
    try:
        import numpy as np
        from collections import Counter
    except ImportError:
        return []
    a = np.asarray(arr).astype(int)
    if a.ndim != 2 or a.shape[1] < 3:
        return []
    rgb = a[:, :3]
    step = 16
    quant = (rgb // step) * step  # snap to bucket center
    # Cast to native Python int so json.dumps does not choke on numpy.int64.
    keys = [tuple(int(c) for c in row) for row in quant]
    total = max(1, len(keys))
    counter = Counter(keys)
    return [
        {
            "rgb_quantized": [int(c) for c in k],
            "share": round(v / total, 4),
        }
        for k, v in counter.most_common(top_n)
    ]


def measure_image(path: Path) -> dict:
    out = {"path": str(path), "type": "image"}
    try:
        from PIL import Image
        import numpy as np
    except ImportError as exc:
        out["error"] = f"missing dep: {exc}"
        return out
    try:
        with Image.open(path) as im:
            im = im.convert("RGB")
            arr = np.asarray(im).reshape(-1, 3)
    except Exception as exc:  # noqa: BLE001 — PIL raises various
        out["error"] = f"image load failed: {exc}"
        return out
    _, count, variance = quantize_colors(arr, buckets=16)
    out["unique_colors"] = count
    out["variance"] = variance
    out["palette_top6"] = palette_distribution(arr)
    return out


def measure_mesh(path: Path) -> dict:
    out = {"path": str(path), "type": "mesh"}
    try:
        import trimesh
        import numpy as np
    except ImportError as exc:
        out["error"] = f"missing dep: {exc}"
        return out
    try:
        mesh = trimesh.load(str(path), force="mesh")
    except Exception as exc:  # noqa: BLE001
        out["error"] = f"mesh load failed: {exc}"
        return out
    visual = getattr(mesh, "visual", None)
    if visual is None:
        out["unique_colors"] = 0
        out["variance"] = 0.0
        out["palette_top6"] = []
        return out
    vc = getattr(visual, "vertex_colors", None)
    if vc is None or len(vc) == 0:
        out["unique_colors"] = 0
        out["variance"] = 0.0
        out["palette_top6"] = []
        return out
    arr = np.asarray(vc)[:, :3]
    _, count, variance = quantize_colors(arr, buckets=16)
    out["unique_colors"] = count
    out["variance"] = variance
    out["palette_top6"] = palette_distribution(arr)
    out["vertex_count"] = int(len(mesh.vertices))
    return out


def diagnose(reference: Path, mesh: Path, post_mesh: Path | None = None) -> dict:
    ref_metrics = measure_image(reference)
    mesh_metrics = measure_mesh(mesh)
    post_metrics = measure_mesh(post_mesh) if post_mesh else None

    if "error" in ref_metrics:
        return {"ok": False, "schema": "aurora.color_diagnostic.v1",
                "error": f"reference: {ref_metrics['error']}"}
    if "error" in mesh_metrics:
        return {"ok": False, "schema": "aurora.color_diagnostic.v1",
                "error": f"mesh: {mesh_metrics['error']}"}

    ref_count = ref_metrics.get("unique_colors", 0)
    mesh_count = mesh_metrics.get("unique_colors", 0)
    post_count = (post_metrics or {}).get("unique_colors", 0) if post_metrics else None

    color_loss_mesh = (
        round(1.0 - (mesh_count / max(1, ref_count)), 4)
        if ref_count > 0 else 0.0
    )

    stage_lost = "none"
    if color_loss_mesh > 0.7:
        stage_lost = "generation"
    elif post_metrics and post_count is not None:
        post_loss = (
            round(1.0 - (post_count / max(1, mesh_count)), 4)
            if mesh_count > 0 else 0.0
        )
        if post_loss > 0.5:
            stage_lost = "post_process"

    suggestions: list[str] = []
    if mesh_count <= 1 and ref_count > 50:
        suggestions.append(
            "Generation collapsed colors to monochrome — check the "
            "TRELLIS.2 texture SLat output, or pivot to DreamGaussian "
            "for stylized subjects (secondary pipeline)."
        )
    elif mesh_count < ref_count // 4 and ref_count > 50:
        suggestions.append(
            "Significant color loss in mesh — consider multi-view "
            "reference (front + back + side) before generation, or pivot "
            "to DreamGaussian for stylized subjects."
        )
    if post_metrics and post_count is not None and post_count < mesh_count // 2:
        suggestions.append(
            "Post-processing stripped colors — check meshPostprocess / "
            "blender_bridge cleanup steps; vertex colors must survive "
            "decimation and remeshing."
        )

    return {
        "ok": True,
        "schema": "aurora.color_diagnostic.v1",
        "reference": ref_metrics,
        "mesh": mesh_metrics,
        "post_mesh": post_metrics,
        "color_loss_ratio_ref_to_mesh": color_loss_mesh,
        "stage_lost": stage_lost,
        "suggestions": suggestions,
    }


def render_pretty(result: dict) -> str:
    if not result.get("ok"):
        return f"FAIL: {result.get('error')}\n"
    lines = [
        f"Color diagnostic — stage_lost: {result['stage_lost']}",
        f"Color loss ratio (ref->mesh): {result['color_loss_ratio_ref_to_mesh']}",
        "",
        f"Reference: {result['reference']['path']}",
        f"  unique_colors: {result['reference']['unique_colors']}",
        f"  variance:      {result['reference']['variance']}",
        "",
        f"Mesh: {result['mesh']['path']}",
        f"  unique_colors: {result['mesh']['unique_colors']}",
        f"  variance:      {result['mesh']['variance']}",
    ]
    if result.get("post_mesh"):
        lines.extend([
            "",
            f"Post-mesh: {result['post_mesh']['path']}",
            f"  unique_colors: {result['post_mesh']['unique_colors']}",
            f"  variance:      {result['post_mesh']['variance']}",
        ])
    if result["suggestions"]:
        lines.append("")
        lines.append("Suggestions:")
        for s in result["suggestions"]:
            lines.append(f"  - {s}")
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Aurora color preservation diagnostic")
    parser.add_argument("--reference", required=True, help="Path to reference PNG")
    parser.add_argument("--mesh", required=True, help="Path to generated GLB")
    parser.add_argument("--post-mesh", default=None,
                        help="Optional: path to post-processed GLB")
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args()
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
    except (AttributeError, ValueError):
        pass

    result = diagnose(
        Path(args.reference), Path(args.mesh),
        Path(args.post_mesh) if args.post_mesh else None,
    )
    if args.pretty:
        sys.stdout.write(render_pretty(result))
    else:
        sys.stdout.write(json.dumps(result, indent=2, ensure_ascii=True) + "\n")
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    sys.exit(main())
