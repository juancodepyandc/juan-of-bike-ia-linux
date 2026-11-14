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


# Share of vertices the fold repair may pin back to their source position before the smoothing
# is declared failed. Above it the result would mostly be the unsmoothed source reported as smoothed.
MAX_CLAMPED_VERTEX_FRACTION = 0.05

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
        import trimesh as _tm
        # WELD-AWARE Taubin. The xatlas re-unwrap upstream SPLITS vertices along
        # every UV seam: two vertices sit at the SAME 3D position but are separate
        # in topology (so each UV island gets its own texels). trimesh's Laplacian
        # treats those twins as independent vertices with different neighbourhoods,
        # so plain filter_taubin drifts them apart and OPENS a visible crack along
        # every seam (clean apple -> cracked plates). Fix: run the smooth on the
        # WELDED topology (coincident twins merged into one), then copy each
        # welded group's smoothed position back onto its split vertices. Seam twins
        # move together -> no cracks, and UVs/faces/visual stay 1:1 (we only write
        # new positions into the original vertex array).
        faces = np.asarray(mesh.faces)
        tol = max(ext0 * 1e-6, 1e-9)
        keys = np.round(v0 / tol).astype(np.int64)
        _, inverse = np.unique(keys, axis=0, return_inverse=True)
        inverse = np.asarray(inverse).ravel()
        n_groups = int(inverse.max()) + 1 if len(inverse) else 0
        if n_groups and n_groups < len(v0):
            # there ARE coincident twins to weld -> use the weld-aware path
            vw = np.zeros((n_groups, 3), dtype=float)
            counts = np.zeros(n_groups, dtype=float)
            np.add.at(vw, inverse, v0)
            np.add.at(counts, inverse, 1.0)
            vw /= np.maximum(counts, 1.0)[:, None]
            fw = inverse[faces]
            deg = (fw[:, 0] == fw[:, 1]) | (fw[:, 1] == fw[:, 2]) | (fw[:, 0] == fw[:, 2])
            welded = _tm.Trimesh(vertices=vw, faces=fw[~deg], process=False)
            filter_taubin(welded, lamb=lamb, nu=nu, iterations=max(1, int(iterations)))
            vw_s = np.asarray(welded.vertices, dtype=float)
            mesh.vertices = vw_s[inverse]
            # UV islands retain separate vertices, but a smooth surface must
            # share shading normals across those islands as well as positions.
            # Computing on the split mesh creates specular seams and facets.
            smooth_normals = np.asarray(welded.vertex_normals)[inverse].copy()
        else:
            # already welded (no twins) -> smooth in place
            filter_taubin(mesh, lamb=lamb, nu=nu, iterations=max(1, int(iterations)))
            smooth_normals = np.asarray(mesh.vertex_normals).copy()
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": f"taubin failed: {exc}"}

    v1 = np.asarray(mesh.vertices, dtype=float)
    if not np.all(np.isfinite(v1)):
        return {"ok": False, "error": "NaN/Inf after smoothing (reverted)"}
    ext1 = float(np.linalg.norm(v1.max(axis=0) - v1.min(axis=0)))
    if ext0 > 0 and (ext1 > ext0 * 1.5 or ext1 < ext0 * 0.5):
        return {"ok": False, "error": f"bbox blew up {ext0:.3f}->{ext1:.3f} (reverted)"}

    # Detect triangle foldovers before exporting: preserving UVs alone cannot
    # prevent a smoothed surface from crossing itself locally. Locally clamp
    # any folded triangle vertex groups back to v0 so 99%+ of the mesh benefits
    # from Taubin smoothing with zero folded triangles.
    before_tri = v0[faces]
    before_cross = np.cross(before_tri[:, 1] - before_tri[:, 0], before_tri[:, 2] - before_tri[:, 0])
    valid = np.linalg.norm(before_cross, axis=1) > max(ext0 ** 2 * 1e-14, 1e-20)
    clamped_groups = 0
    reverted = np.zeros(len(v0), dtype=bool)
    folded_before_clamp = 0
    for _pass in range(10):
        after_tri = v1[faces]
        after_cross = np.cross(after_tri[:, 1] - after_tri[:, 0], after_tri[:, 2] - after_tri[:, 0])
        flip_mask = valid & (np.einsum('ij,ij->i', before_cross, after_cross) <= 0)
        if _pass == 0:
            folded_before_clamp = int(np.count_nonzero(flip_mask))
        if not np.any(flip_mask):
            break
        bad_verts = np.unique(faces[flip_mask].ravel())
        if len(inverse) == len(v0):
            bad_groups = np.unique(inverse[bad_verts])
            revert_mask = np.isin(inverse, bad_groups)
            clamped_groups += int(len(bad_groups))
        else:
            revert_mask = np.zeros(len(v0), dtype=bool)
            revert_mask[bad_verts] = True
        reverted |= revert_mask
        v1[revert_mask] = v0[revert_mask]
        # Clamping is a local repair. Once it has to undo a large share of the surface the smoothing
        # itself is wrong (global flip, collapse): refuse instead of exporting a silent no-op as a success.
        if float(reverted.mean()) > MAX_CLAMPED_VERTEX_FRACTION:
            return {"ok": False,
                    "error": "Smoothing folds or collapses original triangles; source retained",
                    "folded_triangles": folded_before_clamp,
                    "clamped_vertex_fraction": round(float(reverted.mean()), 6)}
    mesh.vertices = v1
    after_tri = v1[faces]
    after_cross = np.cross(after_tri[:, 1] - after_tri[:, 0], after_tri[:, 2] - after_tri[:, 0])
    flipped = int(np.count_nonzero(valid & (np.einsum('ij,ij->i', before_cross, after_cross) <= 0)))
    if flipped:
        return {"ok": False, "error": "Smoothing folds or collapses original triangles; source retained", "folded_triangles": flipped}

    # Re-attach the original visual (filter_taubin keeps vertex order/count, so the
    # per-vertex UVs still map 1:1; trimesh keeps mesh.visual but we re-assert it).
    if visual is not None:
        mesh.visual = visual
    if not np.all(np.isfinite(smooth_normals)):
        return {"ok": False, "error": "Invalid shading normals after smoothing"}
    mesh.vertex_normals = smooth_normals
    out_path.parent.mkdir(parents=True, exist_ok=True)
    src_j = None
    if in_path.suffix.lower() == ".glb" and out_path.suffix.lower() == ".glb":
        try:
            import glb_io
            src_j, _ = glb_io.load(in_path)
        except Exception:  # noqa: BLE001
            src_j = None
    try:
        mesh.export(out_path, **({"include_normals": True}
                                if out_path.suffix.lower() in {".glb", ".gltf"} else {}))
        if src_j is not None:
            try:
                import glb_io
                dst_j, dst_blob = glb_io.load(out_path)
                src_mats = src_j.get("materials") or []
                dst_mats = dst_j.get("materials") or []
                if src_mats and dst_mats:
                    exts_used = set(dst_j.get("extensionsUsed") or [])
                    for s_ext in (src_j.get("extensionsUsed") or []):
                        if str(s_ext).startswith("KHR_materials_"):
                            exts_used.add(str(s_ext))
                    for idx, d_mat in enumerate(dst_mats):
                        s_mat = src_mats[idx] if idx < len(src_mats) else src_mats[0]
                        if isinstance(s_mat.get("extensions"), dict):
                            d_exts = d_mat.setdefault("extensions", {})
                            for k, v in s_mat["extensions"].items():
                                d_exts[k] = v
                                exts_used.add(k)
                        d_pbr = d_mat.get("pbrMetallicRoughness") or {}
                        mrt_info = d_pbr.get("metallicRoughnessTexture")
                        if isinstance(mrt_info, dict) and "index" in mrt_info and "occlusionTexture" not in d_mat:
                            occ_s = 0.75
                            if isinstance(s_mat.get("occlusionTexture"), dict):
                                occ_s = float(s_mat["occlusionTexture"].get("strength", 0.75))
                            d_mat["occlusionTexture"] = {"index": mrt_info["index"], "strength": occ_s}
                    if exts_used:
                        dst_j["extensionsUsed"] = sorted(exts_used)
                    glb_io.save(out_path, dst_j, dst_blob)
            except Exception:  # noqa: BLE001
                pass
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": f"export failed: {exc}"}

    moved = float(np.linalg.norm(v1 - v0, axis=1).mean())
    return {
        "ok": True,
        "output": str(out_path),
        "iterations": int(iterations),
        "vertices": int(len(v1)),
        "mean_vertex_move": round(moved, 6),
        "folded_triangles": 0,
        "folded_triangles_before_clamp": folded_before_clamp,
        "clamped_vertex_fraction": round(float(reverted.mean()), 6),
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
