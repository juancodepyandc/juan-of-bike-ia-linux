import json
import math
import os
import sys
from pathlib import Path

import numpy as np
import trimesh
from PIL import Image, ImageDraw

VIEWS = {
    0: (35, 25),
    1: (90, 10),
    2: (215, 20),
    3: (-40, 20),
}
FOCAL_RATIO = 50.0 / 36.0


def _load_mesh(glb_path):
    scn = trimesh.load(str(glb_path))
    geoms = list(scn.geometry.values()) if hasattr(scn, "geometry") else [scn]
    m = max(geoms, key=lambda g: len(g.faces))
    return m


def _camera(center, radius, az_deg, el_deg):
    a = math.radians(az_deg)
    e = math.radians(el_deg)
    pos = center + np.array([math.cos(a) * math.cos(e),
                             math.sin(a) * math.cos(e),
                             math.sin(e)]) * (radius * 3.2)
    fwd = center - pos
    fwd = fwd / np.linalg.norm(fwd)
    up0 = np.array([0.0, 0.0, 1.0])
    right = np.cross(fwd, up0)
    if np.linalg.norm(right) < 1e-6:
        right = np.array([1.0, 0.0, 0.0])
    right = right / np.linalg.norm(right)
    up = np.cross(right, fwd)
    return pos, right, up, fwd


def _project(verts, pos, right, up, fwd):
    rel = verts - pos
    x = rel @ right
    y = rel @ up
    z = rel @ fwd
    z = np.maximum(z, 1e-6)
    u = 0.5 + (x / z) * FOCAL_RATIO
    v = 0.5 + (y / z) * FOCAL_RATIO
    return u, v


def bake_zone_masks(glb_path, manifest, out_dir, res=2048):
    m = _load_mesh(glb_path)
    verts = np.asarray(m.vertices, dtype=np.float64)
    faces = np.asarray(m.faces, dtype=np.int64)
    uv = getattr(m.visual, "uv", None)
    if uv is None:
        return {"ok": False, "error": "mesh sans UV"}
    uv = np.asarray(uv, dtype=np.float64)
    fnorm = np.asarray(m.face_normals, dtype=np.float64)
    fcent = verts[faces].mean(axis=1)
    mn = verts.min(axis=0)
    mx = verts.max(axis=0)
    center = (mn + mx) / 2.0
    radius = float(max(mx - mn) / 2.0) or 1.0

    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    written = 0
    for zone in manifest.get("zones", []):
        bboxes = zone.get("vision", {}).get("bboxes") or zone.get("bboxes") or []
        if not bboxes:
            continue
        img = Image.new("L", (res, res), 0)
        drw = ImageDraw.Draw(img)
        any_faces = False
        for entry in bboxes:
            vi = int(entry.get("view", 0))
            bb = entry.get("bbox_0_1000")
            if vi not in VIEWS or not bb:
                continue
            x1, y1, x2, y2 = [float(c) / 1000.0 for c in bb]
            az, el = VIEWS[vi]
            pos, right, upv, fwd = _camera(center, radius, az, el)
            u, v = _project(verts, pos, right, upv, fwd)
            pix_u = u
            pix_v = 1.0 - v
            inside_v = (pix_u >= x1) & (pix_u <= x2) & (pix_v >= y1) & (pix_v <= y2)
            facing = (fnorm @ (pos - fcent[0])) * 0
            view_dir = pos - fcent
            view_dir = view_dir / np.linalg.norm(view_dir, axis=1, keepdims=True)
            facing = (fnorm * view_dir).sum(axis=1) > 0.15
            f_inside = inside_v[faces].all(axis=1) & facing
            idx = np.where(f_inside)[0]
            if not len(idx):
                continue
            any_faces = True
            tri_uv = uv[faces[idx]]
            for tri in tri_uv:
                pts = [(float(p[0]) * (res - 1), float((1.0 - p[1])) * (res - 1)) for p in tri]
                drw.polygon(pts, fill=255)
        if not any_faces:
            continue
        mask_path = out_dir / f"mask_{zone.get('zone_id', 'zone')}.png"
        img.save(mask_path)
        zone.setdefault("target", {})["mask_png"] = str(mask_path)
        written += 1
    return {"ok": True, "masks": written}


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--mesh", required=True)
    ap.add_argument("--manifest", required=True)
    ap.add_argument("--outdir", required=True)
    ap.add_argument("--res", type=int, default=2048)
    a = ap.parse_args()
    manifest = json.loads(Path(a.manifest).read_text(encoding="utf-8"))
    r = bake_zone_masks(a.mesh, manifest, a.outdir, res=a.res)
    if r.get("ok"):
        Path(a.manifest).write_text(json.dumps(manifest, ensure_ascii=False, indent=1), encoding="utf-8")
    print("AURORA_MASKS_RESULT:" + json.dumps(r, ensure_ascii=False))
    return 0 if r.get("ok") else 1


if __name__ == "__main__":
    sys.exit(main())
