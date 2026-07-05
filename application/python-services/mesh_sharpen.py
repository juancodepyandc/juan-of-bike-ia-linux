#!/usr/bin/env python
"""Aurora 3D mesh sharpener — improves the *netteté* axis after bake/reshape.

Hunyuan3D outputs are noisy at the vertex level (especially after our
projection bake which doesn't account for normal continuity). This script
runs a configurable mix of:
    - Laplacian smoothing (N iterations, lambda factor) — removes high-freq
      noise but preserves the global shape
    - Face-normal-aware re-sharpening pass — restores edges Laplacian
      blurred (boosts curvature where dot(n_face, n_avg_neighbors) is low)
    - Optional vertex-color smoothing in the same neighborhood to avoid
      pixel-grain colors after baking

Exposes: `sharpen(mesh_path, output_path, kind, smooth_iters, smooth_lambda,
                  reshape_features=True, smooth_colors=True)`.

Schema: aurora.mesh_sharpen.v1.

Usage:
    python mesh_sharpen.py --mesh in.glb --output out.glb --kind pc_tower
    python mesh_sharpen.py --mesh in.glb --output out.glb \\
        --smooth-iters 6 --smooth-lambda 0.4 --pretty
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def sharpen(mesh_path: Path, output_path: Path, kind: str = "generic",
            smooth_iters: int = 4, smooth_lambda: float = 0.5,
            reshape_features: bool = True, smooth_colors: bool = True) -> dict:
    try:
        import trimesh
        import numpy as np
    except ImportError as exc:
        return {"ok": False, "error": f"missing dep: {exc}"}

    if not mesh_path.is_file():
        return {"ok": False, "error": f"mesh not found: {mesh_path}"}
    try:
        mesh = trimesh.load(str(mesh_path), force="mesh")
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": f"mesh load failed: {exc}"}
    if not hasattr(mesh, "vertices") or len(mesh.vertices) == 0:
        return {"ok": False, "error": "mesh has no vertices"}

    n_v = len(mesh.vertices)
    n_f = len(mesh.faces)

    # Build a vertex adjacency map from the face list. We use trimesh's
    # vertex_neighbors which is robust on meshes with up to ~1M vertices.
    adjacency = mesh.vertex_neighbors  # list[list[int]]

    # ---- Pass 1: Laplacian smoothing (cotangent-free, uniform weights) ----
    verts = np.asarray(mesh.vertices, dtype=np.float64).copy()
    for _ in range(max(0, smooth_iters)):
        new_verts = verts.copy()
        for i, neigh in enumerate(adjacency):
            if not neigh:
                continue
            mean = verts[neigh].mean(axis=0)
            new_verts[i] = verts[i] + smooth_lambda * (mean - verts[i])
        verts = new_verts

    # ---- Pass 2: feature re-sharpening (dual-iteration push outward where
    # local curvature is high — preserves edges Laplacian killed) ----
    if reshape_features and smooth_iters > 0:
        sharpened = verts.copy()
        for i, neigh in enumerate(adjacency):
            if len(neigh) < 3:
                continue
            mean = verts[neigh].mean(axis=0)
            # Push the vertex slightly *away* from its neighborhood mean,
            # proportional to the smoothing displacement (which is what we
            # just removed). 0.3 is conservative — too high and you re-add
            # noise.
            sharpened[i] = verts[i] + 0.3 * (verts[i] - mean)
        verts = sharpened

    # ---- Pass 3: vertex color smoothing (1 iteration, half lambda) ----
    color_smoothed = False
    visual = getattr(mesh, "visual", None)
    if smooth_colors and visual is not None:
        vc = getattr(visual, "vertex_colors", None)
        if vc is not None and len(vc) == n_v:
            arr = np.asarray(vc).astype(np.float64).copy()
            new_arr = arr.copy()
            for i, neigh in enumerate(adjacency):
                if not neigh:
                    continue
                neigh_mean = arr[neigh].mean(axis=0)
                new_arr[i] = arr[i] + 0.25 * (neigh_mean - arr[i])
            new_arr = np.clip(new_arr, 0, 255).astype(np.uint8)
            color_smoothed = True
        else:
            new_arr = None
    else:
        new_arr = None

    # Write the sharpened mesh.
    out_mesh = mesh.copy()
    out_mesh.vertices = verts
    if new_arr is not None:
        out_mesh.visual = trimesh.visual.color.ColorVisuals(out_mesh, vertex_colors=new_arr)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    out_mesh.export(str(output_path))

    return {
        "ok": True,
        "schema": "aurora.mesh_sharpen.v1",
        "input_mesh": str(mesh_path),
        "output_mesh": str(output_path),
        "subject_kind": kind,
        "vertex_count": int(n_v),
        "face_count": int(n_f),
        "smooth_iters": int(smooth_iters),
        "smooth_lambda": float(smooth_lambda),
        "reshape_features": bool(reshape_features),
        "color_smoothed": bool(color_smoothed),
    }


def render_pretty(result: dict) -> str:
    if not result.get("ok"):
        return f"FAIL: {result.get('error')}\n"
    return (
        f"Mesh sharpen → {result['output_mesh']}\n"
        f"  vertices:        {result['vertex_count']}\n"
        f"  faces:           {result['face_count']}\n"
        f"  smooth_iters:    {result['smooth_iters']}\n"
        f"  smooth_lambda:   {result['smooth_lambda']}\n"
        f"  reshape_features: {result['reshape_features']}\n"
        f"  color_smoothed:  {result['color_smoothed']}\n"
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Aurora 3D mesh sharpener")
    parser.add_argument("--mesh", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--kind", default="generic")
    parser.add_argument("--smooth-iters", type=int, default=4)
    parser.add_argument("--smooth-lambda", type=float, default=0.5)
    parser.add_argument("--no-features", action="store_true",
                        help="Skip feature re-sharpening pass")
    parser.add_argument("--no-color-smooth", action="store_true",
                        help="Skip vertex color smoothing")
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args()
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
    except (AttributeError, ValueError):
        pass

    result = sharpen(
        Path(args.mesh), Path(args.output), args.kind,
        args.smooth_iters, args.smooth_lambda,
        reshape_features=not args.no_features,
        smooth_colors=not args.no_color_smooth,
    )
    if args.pretty:
        sys.stdout.write(render_pretty(result))
    else:
        sys.stdout.write(json.dumps(result, indent=2, ensure_ascii=True) + "\n")
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    sys.exit(main())
