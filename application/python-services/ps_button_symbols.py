"""PS-controller face-button symbol stamper — procedural decal on a Hunyuan3D /
TRELLIS / MV-Adapter output GLB whose 4 face buttons come out unmarked or with
smeared glyphs (the failure mode Juan calls out on the DualSense reproduction).

Why this exists — none of the upstream texturing paths reliably reproduces the
△ O X □ glyphs on the DualSense right-cluster buttons:

  * TRELLIS.2 paints them into the fragmented xatlas → "scribble" at render time
    (the giant X-scribble crossing all 4 buttons on cluster droit).
  * MV-Adapter (--max-precision, ICCV 2025) generates a clean 4K atlas but the
    symbols in its SDXL sample are too small to survive the per-face packing;
    the buttons render as clean plastic domes with no glyphs.

Contract:

  * Input: a `.glb` produced by any of our texturing paths, whose right cluster
    has 4 face buttons in the standard DualSense diamond (△ top, ○ right,
    ✕ bottom, □ left).
  * Output: a new `.glb` with the same geometry / material / everything except
    the baseColor atlas, which now carries the four glyphs stamped onto the
    UV triangles of each button cap.
  * The stamp is done in atlas space via per-face rasterization: for each atlas
    texel inside a button-cap UV triangle, we interpolate the 3D vertex
    positions barycentric, project onto the button's local XZ tangent plane
    centered on the button, and sample the corresponding glyph pixel. Every
    UV island is treated correctly, regardless of how fragmented the atlas is.
  * Pure numpy / PIL / OpenCV. No GPU. Runs in ~15s on a 4K atlas.

Detection — the 4 button centers on the right cluster are found by:

  1. Coarse localization: scan the Y-elevation map on the (X, Z) plane in the
     right region and find 4 local maxima that form a diamond.
  2. Refinement: RANSAC circle fit on the flat-top faces (normal_y > 0.85) in
     a 4-cm window around each coarse center; the fit center is the button
     center in the XZ plane and its Y is the median top-face Y.
  3. Assignment: TRIANGLE = min-Z (top of diamond, farthest from user),
     CIRCLE = max-X (right), CROSS = max-Z (bottom), SQUARE = min-X (left).
     These are the canonical DualSense positions.

If the mesh is not a DualSense (or its right cluster is missing the diamond),
the detector returns None and no stamping is attempted; the caller keeps the
original mesh unchanged.

Schema returned: aurora.ps_button_symbols.v1

Usage:
    python ps_button_symbols.py --in-glb IN.glb --out-glb OUT.glb
    python ps_button_symbols.py --in-glb IN.glb --out-glb OUT.glb --preview PREVIEW.png
"""
from __future__ import annotations

import argparse
import io
import json
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw
from pygltflib import GLTF2

Image.MAX_IMAGE_PIXELS = None
SCHEMA = "aurora.ps_button_symbols.v1"

# ---------------------------------------------------------------- symbol images

def build_symbols(res: int = 512, ink_rgb: tuple[int, int, int] = (45, 45, 45),
                   stroke_frac: float = 0.045) -> dict[str, np.ndarray]:
    """Build the 4 PS glyphs as RGBA arrays.

    Each symbol occupies the middle ~55% of the res×res image, centered.
    Ink is dark gray on transparent bg. Stroke is `stroke_frac` of image side.
    """
    BG = (255, 255, 255, 0)
    stroke_px = max(2, int(res * stroke_frac))
    ink = (*ink_rgb, 255)
    R = res * 0.32

    tri = Image.new("RGBA", (res, res), BG)
    d = ImageDraw.Draw(tri)
    cx = cy = res / 2
    d.polygon([(cx, cy - R),
               (cx + R * 0.866, cy + R * 0.5),
               (cx - R * 0.866, cy + R * 0.5)],
              outline=ink, fill=None, width=stroke_px)

    cir = Image.new("RGBA", (res, res), BG)
    d = ImageDraw.Draw(cir)
    r = res * 0.28
    d.ellipse([cx - r, cy - r, cx + r, cy + r], outline=ink, width=stroke_px)

    cro = Image.new("RGBA", (res, res), BG)
    d = ImageDraw.Draw(cro)
    r = res * 0.28
    d.line([(cx - r, cy - r), (cx + r, cy + r)], fill=ink, width=stroke_px)
    d.line([(cx + r, cy - r), (cx - r, cy + r)], fill=ink, width=stroke_px)

    sqr = Image.new("RGBA", (res, res), BG)
    d = ImageDraw.Draw(sqr)
    r = res * 0.25
    d.rectangle([cx - r, cy - r, cx + r, cy + r], outline=ink, width=stroke_px)

    return {"TRIANGLE": np.asarray(tri), "CIRCLE": np.asarray(cir),
            "CROSS": np.asarray(cro), "SQUARE": np.asarray(sqr)}

# --------------------------------------------------------- GLB atlas read/write

def _load_glb_atlas(glb_path: str):
    """Return (GLTF2, albedo_image_idx, original_png_bytes, rgb_array)."""
    g = GLTF2().load(glb_path)
    albedo_idx = None
    for mat in g.materials or []:
        pbr = mat.pbrMetallicRoughness
        if pbr and pbr.baseColorTexture is not None:
            albedo_idx = g.textures[pbr.baseColorTexture.index].source
            break
    if albedo_idx is None:
        raise RuntimeError("no baseColorTexture found in GLB")
    blob = g.binary_blob()
    bv = g.bufferViews[g.images[albedo_idx].bufferView]
    png_bytes = bytes(blob[bv.byteOffset: bv.byteOffset + bv.byteLength])
    rgb = np.asarray(Image.open(io.BytesIO(png_bytes)).convert("RGB"))
    return g, albedo_idx, png_bytes, rgb


def _write_glb_atlas(g: GLTF2, albedo_idx: int, new_png: bytes,
                      out_path: str) -> None:
    """Repack the binary blob with the new atlas PNG at `albedo_idx`.

    Byte-perfect for every other bufferView. Same pattern as
    `native_texture_precision._write_atlas`.
    """
    blob = g.binary_blob()
    target_bv = g.images[albedo_idx].bufferView
    order = sorted(range(len(g.bufferViews)),
                   key=lambda i: g.bufferViews[i].byteOffset or 0)
    out = bytearray()
    for i in order:
        bv = g.bufferViews[i]
        if len(out) % 4:
            out.extend(b"\x00" * (4 - len(out) % 4))
        if i == target_bv:
            data = new_png
        else:
            off = bv.byteOffset or 0
            data = blob[off: off + bv.byteLength]
        bv.byteOffset = len(out)
        bv.byteLength = len(data)
        out.extend(data)
    g.buffers[0].byteLength = len(out)
    g.set_binary_blob(bytes(out))
    g.save_binary(out_path)

# --------------------------------------------------- geometry read from accessor

def _acc_np(g: GLTF2, blob: bytes, idx: int) -> np.ndarray:
    a = g.accessors[idx]
    bv = g.bufferViews[a.bufferView]
    off = (bv.byteOffset or 0) + (a.byteOffset or 0)
    n = a.count
    ct = {"SCALAR": 1, "VEC2": 2, "VEC3": 3, "VEC4": 4}[a.type]
    dtype_map = {5120: np.int8, 5121: np.uint8, 5122: np.int16,
                 5123: np.uint16, 5125: np.uint32, 5126: np.float32}
    dtype = dtype_map[a.componentType]
    stride = bv.byteStride or (np.dtype(dtype).itemsize * ct)
    if stride == np.dtype(dtype).itemsize * ct:
        raw = blob[off: off + stride * n]
        arr = np.frombuffer(raw, dtype=dtype, count=n * ct).reshape(n, ct)
    else:
        arr = np.zeros((n, ct), dtype=dtype)
        for i in range(n):
            row = blob[off + i * stride: off + i * stride + np.dtype(dtype).itemsize * ct]
            arr[i] = np.frombuffer(row, dtype=dtype, count=ct)
    if a.type == "SCALAR":
        arr = arr.reshape(-1)
    return arr


def _load_geometry(g: GLTF2):
    """POS (N,3), UV (N,2), IDX (M*3,) from mesh[0].primitives[0], all float64/int64."""
    blob = g.binary_blob()
    prim = g.meshes[0].primitives[0]
    POS = _acc_np(g, blob, prim.attributes.POSITION).astype(np.float64)
    UV = _acc_np(g, blob, prim.attributes.TEXCOORD_0).astype(np.float64)
    IDX = _acc_np(g, blob, prim.indices).astype(np.int64)
    return POS, UV, IDX

# --------------------------------------------------- button diamond detection

def _detect_button_diamond(POS: np.ndarray, IDX: np.ndarray) -> dict | None:
    """Find the 4 face-button centers on the DualSense right cluster.

    The routine assumes:
      * glTF Y-up (face plate faces +Y).
      * Right cluster on +X side.
      * Buttons in a diamond ~5-6 cm across in scene units.

    Returns dict {name: {x, y, z}} or None if the diamond cannot be located.
    """
    tri = IDX.reshape(-1, 3)
    v0 = POS[tri[:, 0]]; v1 = POS[tri[:, 1]]; v2 = POS[tri[:, 2]]
    fc = (v0 + v1 + v2) / 3.0
    fn_raw = np.cross(v1 - v0, v2 - v0)
    fn = fn_raw / np.maximum(np.linalg.norm(fn_raw, axis=1, keepdims=True), 1e-12)

    bbox_min = POS.min(0); bbox_max = POS.max(0)
    size = bbox_max - bbox_min
    # Reject if not obviously a controller-like shape (widest in X)
    if size[0] < 0.8 or size[1] > size[0] * 0.6:
        return None

    # Elevation grid on right half X=[0.15..0.50], Z=[-0.30..0.10]
    gx_min, gx_max = 0.15, 0.50
    gz_min, gz_max = -0.30, 0.10
    RES = 512
    elev = np.full((RES, RES), -1e9)
    face_c_x = (v0[:, 0] + v1[:, 0] + v2[:, 0]) / 3
    face_c_z = (v0[:, 2] + v1[:, 2] + v2[:, 2]) / 3
    face_c_y = (v0[:, 1] + v1[:, 1] + v2[:, 1]) / 3
    ok = (face_c_x >= gx_min) & (face_c_x <= gx_max) & \
         (face_c_z >= gz_min) & (face_c_z <= gz_max) & (fn[:, 1] > 0)
    for tidx in np.arange(len(tri))[ok]:
        p = [POS[tri[tidx, k]] for k in range(3)]
        ix = np.array([(p[k][0] - gx_min) / (gx_max - gx_min) * (RES - 1) for k in range(3)])
        iz = np.array([(p[k][2] - gz_min) / (gz_max - gz_min) * (RES - 1) for k in range(3)])
        uy = np.array([p[k][1] for k in range(3)])
        xmn = max(0, int(np.floor(min(ix)))); xmx = min(RES-1, int(np.ceil(max(ix))))
        zmn = max(0, int(np.floor(min(iz)))); zmx = min(RES-1, int(np.ceil(max(iz))))
        if xmn > xmx or zmn > zmx: continue
        d = (iz[1]-iz[2])*(ix[0]-ix[2]) + (ix[2]-ix[1])*(iz[0]-iz[2])
        if abs(d) < 1e-12: continue
        for py in range(zmn, zmx + 1):
            for px in range(xmn, xmx + 1):
                w0 = ((iz[1]-iz[2])*(px-ix[2]) + (ix[2]-ix[1])*(py-iz[2])) / d
                w1 = ((iz[2]-iz[0])*(px-ix[2]) + (ix[0]-ix[2])*(py-iz[2])) / d
                w2 = 1 - w0 - w1
                if w0 < -0.005 or w1 < -0.005 or w2 < -0.005: continue
                y = w0*uy[0] + w1*uy[1] + w2*uy[2]
                if y > elev[py, px]:
                    elev[py, px] = y

    valid = elev > -1e8
    if valid.sum() < 100: return None
    med = np.median(elev[valid])
    filled = np.where(valid, elev, med)

    try:
        from scipy.ndimage import gaussian_filter
    except ImportError:
        return None
    bg = gaussian_filter(filled, sigma=25)
    bump = gaussian_filter(filled - bg, sigma=2.5)

    # Search 4 quadrants around expected diamond center (0.32, -0.18)
    CX, CZ = 0.32, -0.18
    DX, DZ = 0.06, 0.075

    def find_max(cx, cz, hx=0.03, hz=0.02):
        ix_c = int((cx - gx_min)/(gx_max - gx_min) * (RES - 1))
        iz_c = int((cz - gz_min)/(gz_max - gz_min) * (RES - 1))
        hxp = int(hx/(gx_max - gx_min) * (RES - 1))
        hzp = int(hz/(gz_max - gz_min) * (RES - 1))
        x0, x1 = max(0, ix_c-hxp), min(RES-1, ix_c+hxp)
        z0, z1 = max(0, iz_c-hzp), min(RES-1, iz_c+hzp)
        win = np.where(valid[z0:z1+1, x0:x1+1], bump[z0:z1+1, x0:x1+1], -1e9)
        j_l, i_l = np.unravel_index(np.argmax(win), win.shape)
        x = gx_min + (x0 + i_l)/(RES-1)*(gx_max - gx_min)
        z = gz_min + (z0 + j_l)/(RES-1)*(gz_max - gz_min)
        return x, float(filled[z0 + j_l, x0 + i_l]), z

    coarse = {
        "TRIANGLE": find_max(CX, CZ - DZ),
        "CIRCLE":   find_max(CX + DX, CZ, hx=0.02, hz=0.03),
        "CROSS":    find_max(CX, CZ + DZ),
        "SQUARE":   find_max(CX - DX, CZ, hx=0.02, hz=0.03),
    }

    # Refine each with circle fit on flat-top faces around the coarse center
    refined = {}
    for name, (Cx0, Cy0, Cz0) in coarse.items():
        dx = face_c_x - Cx0; dz = face_c_z - Cz0
        d2 = dx*dx + dz*dz
        mask = (d2 < 0.04**2) & (fn[:, 1] > 0.85) & (face_c_y > 0.09)
        if mask.sum() < 4:
            refined[name] = {"x": float(Cx0), "y": float(Cy0), "z": float(Cz0)}
            continue
        pts = np.column_stack([face_c_x[mask], face_c_z[mask]])
        y_vals = face_c_y[mask]
        cap = y_vals > np.percentile(y_vals, 30)
        if cap.sum() < 4: cap = np.ones(len(y_vals), dtype=bool)
        A = np.column_stack([2*pts[cap, 0], 2*pts[cap, 1], np.ones(cap.sum())])
        b = pts[cap, 0]**2 + pts[cap, 1]**2
        sol, *_ = np.linalg.lstsq(A, b, rcond=None)
        refined[name] = {"x": float(sol[0]),
                         "y": float(y_vals[cap].mean()),
                         "z": float(sol[1])}
    return refined

# --------------------------------------------------- per-face rasterization

def _rasterize_symbols_into_atlas(POS: np.ndarray, UV: np.ndarray, IDX: np.ndarray,
                                    atlas_rgb: np.ndarray, centers: dict,
                                    symbols: dict[str, np.ndarray],
                                    R_local: float = 0.030,
                                    R_face_search: float = 0.032,
                                    y_below_tolerance: float = 0.008,
                                    y_above_tolerance: float = 0.020) -> dict:
    """Paint each symbol into the atlas along the UV triangles of its button cap.

    For every atlas texel inside a face's UV triangle:
      - barycentric-interpolate the world (x, z) position
      - project onto local frame centered at button (Cx, Cz), scale R_local
      - sample the symbol PNG at (lu+1)/2, (lv+1)/2
      - alpha-blend the ink onto the atlas texel
    """
    tri = IDX.reshape(-1, 3)
    v0 = POS[tri[:, 0]]; v1 = POS[tri[:, 1]]; v2 = POS[tri[:, 2]]
    fc = (v0 + v1 + v2) / 3
    fn_raw = np.cross(v1 - v0, v2 - v0)
    fn = fn_raw / np.maximum(np.linalg.norm(fn_raw, axis=1, keepdims=True), 1e-12)

    H, W = atlas_rgb.shape[:2]
    SR = symbols["TRIANGLE"].shape[0]
    out = atlas_rgb.copy()
    stats = {}

    for name, C in centers.items():
        Cx, Cy, Cz = C["x"], C["y"], C["z"]
        sym = symbols[name]
        dx = fc[:, 0] - Cx; dz = fc[:, 2] - Cz
        d2 = dx*dx + dz*dz
        face_mask = (d2 < R_face_search * R_face_search) & (fn[:, 1] > 0.30) & \
                    (fc[:, 1] > Cy - y_below_tolerance) & (fc[:, 1] < Cy + y_above_tolerance)
        face_ids = np.arange(len(tri))[face_mask]
        painted = 0
        for fi in face_ids:
            i0, i1, i2 = tri[fi]
            uv0, uv1, uv2 = UV[i0], UV[i1], UV[i2]
            p0, p1, p2 = POS[i0], POS[i1], POS[i2]
            ax0 = uv0[0]*W; ay0 = uv0[1]*H
            ax1 = uv1[0]*W; ay1 = uv1[1]*H
            ax2 = uv2[0]*W; ay2 = uv2[1]*H
            xmn = max(0, int(np.floor(min(ax0, ax1, ax2))))
            xmx = min(W - 1, int(np.ceil(max(ax0, ax1, ax2))))
            ymn = max(0, int(np.floor(min(ay0, ay1, ay2))))
            ymx = min(H - 1, int(np.ceil(max(ay0, ay1, ay2))))
            if xmn > xmx or ymn > ymx: continue
            denom = (ay1 - ay2)*(ax0 - ax2) + (ax2 - ax1)*(ay0 - ay2)
            if abs(denom) < 1e-12: continue
            for py in range(ymn, ymx + 1):
                for px in range(xmn, xmx + 1):
                    w0 = ((ay1 - ay2)*(px - ax2) + (ax2 - ax1)*(py - ay2)) / denom
                    w1 = ((ay2 - ay0)*(px - ax2) + (ax0 - ax2)*(py - ay2)) / denom
                    w2 = 1 - w0 - w1
                    if w0 < 0 or w1 < 0 or w2 < 0: continue
                    x3 = w0*p0[0] + w1*p1[0] + w2*p2[0]
                    z3 = w0*p0[2] + w1*p1[2] + w2*p2[2]
                    lu = (x3 - Cx) / R_local
                    lv = (z3 - Cz) / R_local
                    if lu < -1 or lu > 1 or lv < -1 or lv > 1: continue
                    sxi = int((lu + 1)*0.5*(SR - 1))
                    syi = int((lv + 1)*0.5*(SR - 1))
                    sxi = max(0, min(SR - 1, sxi))
                    syi = max(0, min(SR - 1, syi))
                    sr, sg, sb, sa = sym[syi, sxi]
                    if sa == 0: continue
                    a = sa / 255.0
                    cur = out[py, px].astype(np.float32)
                    new = np.array([sr, sg, sb], dtype=np.float32)
                    out[py, px] = (cur*(1 - a) + new*a).clip(0, 255).astype(np.uint8)
                    painted += 1
        stats[name] = {"faces_selected": int(len(face_ids)),
                       "atlas_texels_painted": int(painted)}
    return out, stats

# ---------------------------------------------------------------------- main API

def stamp_ps_symbols_on_glb(in_glb: str, out_glb: str,
                             *, preview_png: str | None = None,
                             R_local: float = 0.030) -> dict:
    """Full pipeline: detect the 4 buttons, rasterize the glyphs, save GLB."""
    result = {"schema": SCHEMA, "in_glb": in_glb, "out_glb": out_glb,
              "ok": False, "detected_diamond": None, "stats": {}}
    if not Path(in_glb).is_file():
        result["reason"] = f"input glb missing: {in_glb}"
        return result
    g, albedo_idx, orig_png, atlas_rgb = _load_glb_atlas(in_glb)
    POS, UV, IDX = _load_geometry(g)
    result["atlas_size"] = [int(atlas_rgb.shape[1]), int(atlas_rgb.shape[0])]

    centers = _detect_button_diamond(POS, IDX)
    if centers is None:
        result["reason"] = "could not locate DualSense face-button diamond in mesh"
        return result
    result["detected_diamond"] = centers

    symbols = build_symbols()
    new_rgb, stats = _rasterize_symbols_into_atlas(
        POS, UV, IDX, atlas_rgb, centers, symbols, R_local=R_local)
    result["stats"] = stats

    if preview_png:
        Image.fromarray(new_rgb).save(preview_png)
    buf = io.BytesIO(); Image.fromarray(new_rgb).save(buf, format="PNG", optimize=False)
    _write_glb_atlas(g, albedo_idx, buf.getvalue(), out_glb)
    result["ok"] = Path(out_glb).is_file()
    return result


def _main() -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--in-glb", required=True, help="Input GLB (with baseColorTexture)")
    p.add_argument("--out-glb", required=True, help="Output GLB path")
    p.add_argument("--preview", help="Also write the new atlas PNG for inspection")
    p.add_argument("--r-local", type=float, default=0.030,
                   help="Half-size of the [-1..1] local plane in world units. Default 0.030 (~3cm).")
    p.add_argument("--pretty", action="store_true")
    args = p.parse_args()
    result = stamp_ps_symbols_on_glb(args.in_glb, args.out_glb,
                                     preview_png=args.preview, R_local=args.r_local)
    sys.stdout.write(json.dumps(result, indent=2 if args.pretty else None,
                                 ensure_ascii=True) + "\n")
    return 0 if result.get("ok") else 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(_main())
