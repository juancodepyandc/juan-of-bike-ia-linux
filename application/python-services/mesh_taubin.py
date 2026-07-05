#!/usr/bin/env python
"""UV-safe Taubin smoothing for TEXTURED Hunyuan3D meshes (v90).

Why: the production character/product path is always textured (Hunyuan paint), so
the existing manifold/smoothing rescue is skipped (it would destroy painted UVs).
That leaves the raw Marching-Cubes faceting in place — the "cubique/robotique"
look the user flagged. Taubin smoothing (λ|μ) moves VERTEX POSITIONS only and
does NOT touch the per-vertex UVs or the topology, so it removes MC faceting
while keeping the texture mapping intact. Unlike Laplacian it does not shrink the
volume (the μ backward pass cancels the λ forward shrink).

Run: python mesh_taubin.py --input mesh.glb --output smooth.glb [--iterations 8]
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


def taubin_smooth(in_path: str | Path, out_path: str | Path, *,
                  iterations: int = 8, lamb: float = 0.5, nu: float = 0.53) -> dict:
    """Apply UV-preserving Taubin smoothing. Returns {ok, ...}. Reverts on any
    geometry blow-up (NaN / bbox explosion) so a bad smooth never ships."""
    try:
        import numpy as np
        import trimesh
        from trimesh.smoothing import filter_taubin
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": f"deps unavailable: {type(exc).__name__}: {exc}"}

    in_path, out_path = Path(in_path), Path(out_path)
    try:
        mesh = trimesh.load(in_path, force="mesh", process=False)
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": f"load failed: {exc}"}
    if not hasattr(mesh, "vertices") or len(mesh.vertices) == 0:
        return {"ok": False, "error": "no vertices"}

    v0 = np.asarray(mesh.vertices, dtype=float).copy()
    ext0 = float(np.linalg.norm(v0.max(axis=0) - v0.min(axis=0)))
    # Snapshot visuals so we can guarantee they survive the export.
    visual = getattr(mesh, "visual", None)
    try:
        filter_taubin(mesh, lamb=lamb, nu=nu, iterations=max(1, int(iterations)))
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": f"taubin failed: {exc}"}

    v1 = np.asarray(mesh.vertices, dtype=float)
    if not np.all(np.isfinite(v1)):
        return {"ok": False, "error": "NaN/Inf after smoothing (reverted)"}
    ext1 = float(np.linalg.norm(v1.max(axis=0) - v1.min(axis=0)))
    if ext0 > 0 and (ext1 > ext0 * 1.5 or ext1 < ext0 * 0.5):
        return {"ok": False, "error": f"bbox blew up {ext0:.3f}->{ext1:.3f} (reverted)"}

    # Re-attach the original visual (filter_taubin keeps vertex order/count, so the
    # per-vertex UVs still map 1:1; trimesh keeps mesh.visual but we re-assert it).
    if visual is not None:
        mesh.visual = visual
    out_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        mesh.export(out_path)
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": f"export failed: {exc}"}

    moved = float(np.linalg.norm(v1 - v0, axis=1).mean())
    return {
        "ok": True,
        "output": str(out_path),
        "iterations": int(iterations),
        "vertices": int(len(v1)),
        "mean_vertex_move": round(moved, 6),
        "bbox_extent": round(ext1, 4),
        "textured": visual is not None and type(visual).__name__ == "TextureVisuals",
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="UV-safe Taubin smoothing for textured meshes")
    ap.add_argument("--input", required=True)
    ap.add_argument("--output", required=True)
    ap.add_argument("--iterations", type=int, default=8)
    ap.add_argument("--lamb", type=float, default=0.5)
    ap.add_argument("--nu", type=float, default=0.53)
    args = ap.parse_args()
    import json
    r = taubin_smooth(args.input, args.output, iterations=args.iterations,
                      lamb=args.lamb, nu=args.nu)
    sys.stdout.write(json.dumps(r, ensure_ascii=True) + "\n")
    return 0 if r.get("ok") else 1


if __name__ == "__main__":
    sys.exit(main())
