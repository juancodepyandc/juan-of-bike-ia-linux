"""Atlas-aware despeckle — kills the TRELLIS micro-island "mouchetis" (RC1/RC6).

MEASURED ROOT CAUSE (Goldorak run, 1.88 M tris, 8192^2 atlas)
------------------------------------------------------------
The native atlas (TRELLIS / Marching-Cubes + xatlas) holds 87 222 UV islands.
18 320 of them are *degenerate*: their UV area is below one texel, and xatlas has
collapsed **all of them onto the very same texel — the atlas corner (0,0)**.
That corner happens to hold RGB(16,44,77): dark blue. So 18 320 real 3D patches,
scattered all over the body, all sample one dark-blue texel. On a robot you get
blue/beige specks on the panels; on a human you get the blue/beige speckle on the
SKIN and on the CLOTHES. That is the "mouchetis" — measured, not inferred:
painting that single texel magenta lights up ~180 dots per view in the real
three.js viewer.

Consequence: a *texture-only* fix CANNOT work. All the parasite charts share one
texel, so one texel = one colour for 18 320 different neighbourhoods. They must be
given their own texels.

WHY NOT A SPATIAL FILTER
-----------------------
Any image-space operation (blur / median / inpaint over the atlas) crosses UV
island frontiers and reveals the atlas structure on the model (the leopard
pattern; lesson learned in native_texture_precision.py). And texture_despeckle.py
is a *colour* detector (blue fluid / hot lava): useless on skin, cloth, metal.

APPROACH — no colour prior, no hardcode, no image-space leakage
---------------------------------------------------------------
1. Segment the UV islands = connected components of the vertex graph induced by
   the faces (a UV seam duplicates the vertex, so "shares a vertex index" is
   exactly "same UV island"). Measure each island's area **in texels**.
2. PARASITE = island whose texel area < `min_island_px`. It cannot carry any
   detail, and its texel is unreliable (collapsed / padding / bleed).
3. Its true colour is the MEDIAN of its neighbours **in 3D** — the faces sharing a
   welded vertex on the mesh. Never a spatial neighbourhood in the atlas. So no
   atlas-space reference is ever introduced and no frontier can be revealed.
   Gate: repair only fires when the current colour deviates from that median by
   more than `--tol` (Lab dE76). A clean atlas is a strict no-op.
4. REPAIR, two modes (auto):
   - `relocate` (default when the UVs are plain float32): the chart is re-homed to
     a private flat patch allocated in the FREE atlas space (48 % of this atlas is
     unused), painted with the 3D-neighbour median in **every** texture bound to
     the same texcoord set (baseColor, metallicRoughness, occlusion, normal,
     emissive). The atlas edit is purely ADDITIVE — it only writes into empty
     space, so no existing chart can ever be corrupted. The island's UVs are moved
     onto that patch (non-degenerate placement on a small circle inside the patch
     core, so no zero-area UV triangle is introduced).
   - `inplace`: when the chart owns exclusive texels (no collapse), its texels are
     simply repainted with the same 3D-neighbour median. Used as a fallback when
     the UVs are not writable (quantized meshes) or the free space is exhausted.
5. INTRA-ISLAND pass (complement): switching median inside the *big* islands to kill
   salt & pepper without ever crossing a frontier — the median is applied only on
   texels whose whole k x k footprint is inside the island (mask erosion by the
   kernel), and only where the pixel is an impulse outlier
   (|orig - median| > `--impulse-tol`). Real detail (edges, pores, garment seams)
   is preserved; frontiers are structurally unreachable.

Generic: no assumption on the subject (skin, cloth, metal, robot). Geometry,
normals and topology are never touched — only the baseColor/MR/AO/normal PNG bytes
(in free space) and, in relocate mode, the TEXCOORD of the parasite charts.

Schema: aurora.despeckle_atlas.v1

CLI:
    python texture_despeckle_atlas.py --glb in.glb --output out.glb
    python texture_despeckle_atlas.py --glb in.glb --output out.glb \
        --min-island-px 6 --strength 1.0 --tol 8 --mode auto --no-intra-median
    python texture_despeckle_atlas.py --glb in.glb --analyze-only
"""
from __future__ import annotations

import argparse
import io
import json
import struct
import sys
import time
from pathlib import Path

import cv2
import numpy as np
from PIL import Image
from pygltflib import GLTF2

Image.MAX_IMAGE_PIXELS = None

_CTYPE = {5120: "i1", 5121: "u1", 5122: "i2", 5123: "u2", 5125: "u4", 5126: "f4"}
_NCOMP = {"SCALAR": 1, "VEC2": 2, "VEC3": 3, "VEC4": 4}

SCHEMA = "aurora.despeckle_atlas.v1"


class _Unreadable(RuntimeError):
    """Geometry cannot be read (Draco/quantized/sparse): the caller must skip, not crash."""


# ------------------------------------------------------------------------- glTF
def _read_accessor(g: GLTF2, blob: bytes, idx: int) -> np.ndarray:
    a = g.accessors[idx]
    if a.bufferView is None:
        raise _Unreadable(f"accessor {idx} has no bufferView "
                          "(compressed or sparse geometry: decompress the GLB first)")
    bv = g.bufferViews[a.bufferView]
    off = (bv.byteOffset or 0) + (a.byteOffset or 0)
    n = _NCOMP[a.type]
    dt = np.dtype(_CTYPE[a.componentType]).newbyteorder("<")
    stride = bv.byteStride or n * dt.itemsize
    raw = np.frombuffer(blob, dtype=np.uint8, count=a.count * stride, offset=off)
    raw = raw.reshape(a.count, stride)[:, : n * dt.itemsize]
    return np.ascontiguousarray(raw).view(dt).reshape(a.count, n)


def _decode_image(g: GLTF2, blob: bytes, img_idx: int) -> np.ndarray:
    im = g.images[img_idx]
    if im.bufferView is None:
        raise RuntimeError(f"image {img_idx} is not embedded (uri-based GLB unsupported)")
    bv = g.bufferViews[im.bufferView]
    off = bv.byteOffset or 0
    png = bytes(blob[off: off + bv.byteLength])
    return np.asarray(Image.open(io.BytesIO(png)).convert("RGB"))


def _encode_png(rgb: np.ndarray) -> bytes:
    ok, buf = cv2.imencode(".png", cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR),
                           [int(cv2.IMWRITE_PNG_COMPRESSION), 6])
    if not ok:
        raise RuntimeError("PNG encode failed")
    return buf.tobytes()


def _write_glb(g: GLTF2, blob: bytes, bv_payload: dict, out_glb: str) -> None:
    """Repack the binary chunk, substituting the given bufferView payloads."""
    order = sorted(range(len(g.bufferViews)), key=lambda i: g.bufferViews[i].byteOffset or 0)
    out = bytearray()
    for i in order:
        bv = g.bufferViews[i]
        if len(out) % 4:
            out.extend(b"\x00" * (4 - len(out) % 4))
        if i in bv_payload:
            data = bv_payload[i]
        else:
            off = bv.byteOffset or 0
            data = blob[off: off + bv.byteLength]
        bv.byteOffset = len(out)
        bv.byteLength = len(data)
        out.extend(data)
    g.buffers[0].byteLength = len(out)
    g.set_binary_blob(bytes(out))
    g.save_binary(out_glb)


# --------------------------------------------------------------------- topology
def _connected_components(edges: np.ndarray, nv: int) -> np.ndarray:
    """Vertex -> UV island label. scipy when available, union-find fallback."""
    try:
        from scipy.sparse import coo_matrix
        from scipy.sparse.csgraph import connected_components
        m = coo_matrix((np.ones(len(edges), np.uint8), (edges[:, 0], edges[:, 1])),
                       shape=(nv, nv))
        _, lab = connected_components(m, directed=False)
        return lab.astype(np.int64)
    except ImportError:
        parent = np.arange(nv, dtype=np.int64)

        def find(x: int) -> int:
            root = x
            while parent[root] != root:
                root = parent[root]
            while parent[x] != root:
                parent[x], x = root, parent[x]
            return root

        for a, b in edges:
            ra, rb = find(int(a)), find(int(b))
            if ra != rb:
                parent[ra] = rb
        roots = np.array([find(i) for i in range(nv)], dtype=np.int64)
        _, lab = np.unique(roots, return_inverse=True)
        return lab.astype(np.int64)


def _weld(pos: np.ndarray) -> np.ndarray:
    """Vertex -> welded id (UV seams duplicate vertices at the same 3D position)."""
    lo, hi = pos.min(axis=0), pos.max(axis=0)
    diag = float(np.linalg.norm(hi - lo)) or 1.0
    q = np.round(pos.astype(np.float64) / (diag * 1e-6)).astype(np.int64)
    _, inv = np.unique(q, axis=0, return_inverse=True)
    return inv.reshape(-1).astype(np.int64)


def _lab_delta(c0, c1) -> float:
    a = cv2.cvtColor(np.asarray(c0, np.uint8).reshape(1, 1, 3), cv2.COLOR_RGB2LAB).astype(np.float32)
    b = cv2.cvtColor(np.asarray(c1, np.uint8).reshape(1, 1, 3), cv2.COLOR_RGB2LAB).astype(np.float32)
    return float(np.linalg.norm(a - b))


def _rasterize(tris_px: np.ndarray, W: int, H: int) -> np.ndarray:
    """Coverage mask of the given triangles (chunked: millions of tiny polygons)."""
    cov = np.zeros((H, W), np.uint8)
    for i in range(0, len(tris_px), 200000):
        chunk = np.round(tris_px[i: i + 200000]).astype(np.int32)
        cv2.fillPoly(cov, list(chunk), 1)
    return cov


class _PatchAllocator:
    """Hands out private, chart-free PxP blocks in the unused space of the atlas.

    The free space of a TRELLIS atlas is *fragmented* (it is the gutter between
    ~90 k charts), so a fixed patch size is not viable: on the reference run there
    are 119 free 16x16 blocks but 39 183 free 8x8 ones. The patch size is therefore
    chosen as the LARGEST one whose supply covers the demand, floored by the
    resolution ratio so that the patch still spans >= 2 texels in the *smallest*
    texture bound to the same UVs.
    """

    CANDIDATES = (32, 24, 16, 12, 8, 6, 4)

    def __init__(self, coverage: np.ndarray, needed: int, min_patch: int = 4):
        H, W = coverage.shape
        self.blocks = np.zeros((0, 2), np.int64)
        self.patch = 0
        self.n = 0
        for p in self.CANDIDATES:
            if p < min_patch:
                continue
            m = max(1, p // 4)
            se = np.ones((2 * m + 1, 2 * m + 1), np.uint8)
            busy = cv2.dilate(coverage, se)
            gh, gw = H // p, W // p
            free = busy[: gh * p, : gw * p].reshape(gh, p, gw, p).max(axis=(1, 3)) == 0
            cnt = int(free.sum())
            ys, xs = np.nonzero(free)
            self.blocks = np.stack([xs * p, ys * p], axis=1)
            self.patch = p
            self.margin = m
            if cnt >= needed:
                return                              # largest patch that fits the demand

    def take(self):
        if self.n >= len(self.blocks):
            return None
        b = self.blocks[self.n]
        self.n += 1
        return int(b[0]), int(b[1])


# -------------------------------------------------------------------- main pass
def _process_group(images: dict, base_img: int, uv: np.ndarray, pos: np.ndarray,
                   faces: np.ndarray, nrm: np.ndarray | None, *, min_island_px: float,
                   strength: float, tol: float, pad: int, mode: str, intra_median: int,
                   impulse_tol: int, intra_min_area: float, blend_sliver_normals: bool,
                   verbose: bool):
    """Returns (stats, new_uv|None, new_nrm|None). `images` {idx: HxWx3} is mutated."""
    rgb = images[base_img]
    H, W = rgb.shape[:2]
    t0 = time.time()

    # --- UV islands
    nv = len(uv)
    edges = np.concatenate([faces[:, [0, 1]], faces[:, [1, 2]], faces[:, [2, 0]]])
    vlab = _connected_components(edges, nv)
    del edges
    flab = vlab[faces[:, 0]]                       # a face lives in exactly one island
    ids, inv = np.unique(flab, return_inverse=True)
    n_isl = len(ids)

    uv_px = uv.astype(np.float64) * [W, H]         # glTF UV origin = top-left, no flip
    tri = uv_px[faces]
    ar = 0.5 * np.abs((tri[:, 1, 0] - tri[:, 0, 0]) * (tri[:, 2, 1] - tri[:, 0, 1])
                      - (tri[:, 2, 0] - tri[:, 0, 0]) * (tri[:, 1, 1] - tri[:, 0, 1]))
    isl_area = np.bincount(inv, ar, n_isl)         # island area in TEXELS
    parasite = isl_area < float(min_island_px)
    n_par = int(parasite.sum())

    st = {
        "islands_total": n_isl,
        "islands_parasite": n_par,
        "island_area_hist": {f"<{t}texels": int((isl_area < t).sum()) for t in (1, 6, 16, 64, 256)},
        "atlas": [W, H],
        "faces": int(len(faces)),
        "islands_purged": 0, "islands_relocated": 0, "islands_inplace": 0,
        "islands_skipped_clean": 0, "islands_unplaced": 0, "islands_no_neighbour": 0,
        "islands_intra_filtered": 0, "normals_blended": 0,
        "px_changed": 0, "px_changed_purge": 0, "px_changed_intra": 0,
    }

    order = np.argsort(inv, kind="stable")
    starts = np.searchsorted(inv[order], np.arange(n_isl))
    ends = np.searchsorted(inv[order], np.arange(n_isl), side="right")

    new_uv = None
    new_nrm = None
    px_purge = 0

    if n_par:
        face_par = parasite[inv]
        kept_tris = tri[~face_par]
        coverage = _rasterize(kept_tris, W, H)     # what the real charts occupy

        # geometric normal of every face (for the optional sliver-normal blend):
        # a parasite chart is also a *sliver micro-facet* — measured on the
        # reference run, its normal deviates by 63 deg from its 3D neighbours, so
        # it catches the IBL differently and leaves a SHADING speck even once its
        # colour is fixed. Re-pointing its vertex normals at the surrounding
        # surface removes that speck. Positions/topology are never touched.
        fn = None
        if blend_sliver_normals and nrm is not None:
            t3 = pos[faces]
            fn = np.cross(t3[:, 1] - t3[:, 0], t3[:, 2] - t3[:, 0])
            ln = np.linalg.norm(fn, axis=1, keepdims=True)
            fn = fn / np.maximum(ln, 1e-12)
            nrm_out = nrm.astype(np.float32).copy()

        # 3D adjacency: welded vertex -> incident faces (CSR)
        weld = _weld(pos)
        wf_w = weld[faces].ravel()
        wf_f = np.repeat(np.arange(len(faces), dtype=np.int64), 3)
        o = np.argsort(wf_w, kind="stable")
        wf_w, wf_f = wf_w[o], wf_f[o]
        del o
        kept_face_ids = np.flatnonzero(~face_par)
        kdt = None
        if len(kept_face_ids):
            try:
                from scipy.spatial import cKDTree
                kdt = cKDTree(pos[faces[kept_face_ids]].mean(axis=1))
            except ImportError:
                kdt = None

        # per-texture centroid-texel lookup (a texture may be smaller than the atlas)
        cen = {}
        for i, img in images.items():
            ih, iw = img.shape[:2]
            c = np.floor(uv.astype(np.float64)[faces].mean(axis=1) * [iw, ih])
            cen[i] = np.clip(c, [0, 0], [iw - 1, ih - 1]).astype(np.int64)

        # patch allocator (relocate mode): patch big enough to survive the SMALLEST
        # texture bound to this texcoord (a 16px block at 8192 is still 4px at 2048)
        alloc = None
        if mode != "inplace":
            min_res = min(min(img.shape[:2]) for img in images.values())
            min_patch = int(max(4, np.ceil(2.0 * max(W, H) / max(1, min_res))))
            alloc = _PatchAllocator(coverage, n_par, min_patch)
            st["patch_px"] = alloc.patch
            st["free_patches"] = int(len(alloc.blocks))

        offs = np.array([(dy, dx) for dy in range(-pad, pad + 1)
                         for dx in range(-pad, pad + 1)], np.int64)
        s = float(np.clip(strength, 0.0, 1.0))
        uv_out = uv.astype(np.float32).copy()
        moved = []

        for k in np.flatnonzero(parasite):
            f = order[starts[k]:ends[k]]
            # --- 3D neighbourhood (never an atlas neighbourhood)
            welds = np.unique(weld[faces[f]].ravel())
            lo = np.searchsorted(wf_w, welds)
            hi = np.searchsorted(wf_w, welds, side="right")
            nb = np.concatenate([wf_f[a:b] for a, b in zip(lo, hi)]) if len(welds) else np.empty(0, np.int64)
            nb = np.unique(nb)
            nb = nb[~face_par[nb]]
            if len(nb) < 3 and kdt is not None and len(kept_face_ids):
                c3 = pos[faces[f]].mean(axis=1).mean(axis=0)
                _, near = kdt.query(c3, k=int(min(12, len(kept_face_ids))))
                nb = kept_face_ids[np.atleast_1d(near)]
            if not len(nb):
                st["islands_no_neighbour"] += 1
                continue

            # --- optional: blend the sliver's shading normal into the surface
            if fn is not None:
                n_ref = fn[nb].mean(axis=0)
                ln = float(np.linalg.norm(n_ref))
                if ln > 1e-6:
                    vids_n = np.unique(faces[f].ravel())
                    nrm_out[vids_n] = (n_ref / ln).astype(np.float32)
                    st["normals_blended"] += 1

            cc = cen[base_img][nb]
            ref = np.median(rgb[cc[:, 1], cc[:, 0]].astype(np.float32), axis=0)

            # --- current colour of the chart (its own texels)
            t = tri[f]
            pts = np.concatenate([t.reshape(-1, 2), t.mean(axis=1)])
            px = np.floor(pts).astype(np.int64)
            px[:, 0] = np.clip(px[:, 0], 0, W - 1)
            px[:, 1] = np.clip(px[:, 1], 0, H - 1)
            cur = np.median(rgb[px[:, 1], px[:, 0]].astype(np.float32), axis=0)
            if _lab_delta(np.round(cur), np.round(ref)) < tol:
                st["islands_skipped_clean"] += 1
                continue

            blk = alloc.take() if alloc is not None else None
            if blk is not None:
                # ---- RELOCATE: private flat patch in free space, painted per texture
                x0, y0 = blk
                p = alloc.patch
                for i, img in images.items():
                    ih, iw = img.shape[:2]
                    sx, sy = iw / W, ih / H
                    rx0, ry0 = int(x0 * sx), int(y0 * sy)
                    rx1, ry1 = max(rx0 + 1, int((x0 + p) * sx)), max(ry0 + 1, int((y0 + p) * sy))
                    cci = cen[i][nb]
                    val = np.median(img[cci[:, 1], cci[:, 0]].astype(np.float32), axis=0)
                    img[ry0:ry1, rx0:rx1] = np.round(val).astype(np.uint8)
                    if i == base_img:
                        px_purge += (ry1 - ry0) * (rx1 - rx0)
                # UVs -> small circle inside the patch core. A circle guarantees no
                # 3 distinct vertices are collinear, so no zero-area UV triangle is
                # created; r = 0.3p keeps the whole footprint (and its bilinear
                # neighbourhood) inside the flat patch while giving the chart enough
                # texel area that a second pass no longer classifies it as a parasite
                # (idempotency).
                vids = np.unique(faces[f].ravel())
                cx, cy = (x0 + p * 0.5), (y0 + p * 0.5)
                r = p * 0.30
                ang = 2.0 * np.pi * np.arange(len(vids)) / max(1, len(vids))
                uv_out[vids, 0] = ((cx + r * np.cos(ang)) / W).astype(np.float32)
                uv_out[vids, 1] = ((cy + r * np.sin(ang)) / H).astype(np.float32)
                moved.append(vids)
                st["islands_relocated"] += 1
                st["islands_purged"] += 1
            else:
                # ---- IN-PLACE: repaint the chart's own texels (bilinear footprint),
                #      never touching a texel owned by a real chart.
                if alloc is not None:
                    st["islands_unplaced"] += 1
                pxd = (px[:, None, :] + offs[None, :, ::-1]).reshape(-1, 2)
                pxd[:, 0] = np.clip(pxd[:, 0], 0, W - 1)
                pxd[:, 1] = np.clip(pxd[:, 1], 0, H - 1)
                pxd = np.unique(pxd, axis=0)
                pxd = pxd[coverage[pxd[:, 1], pxd[:, 0]] == 0]
                if not len(pxd):
                    continue
                old = rgb[pxd[:, 1], pxd[:, 0]].astype(np.float32)
                rgb[pxd[:, 1], pxd[:, 0]] = np.round(old * (1.0 - s) + ref[None, :] * s).astype(np.uint8)
                px_purge += len(pxd)
                st["islands_inplace"] += 1
                st["islands_purged"] += 1

        if moved:
            new_uv = uv_out
        if fn is not None and st["normals_blended"]:
            new_nrm = nrm_out
        if verbose:
            print(f"  [{base_img}] parasites={n_par} relocated={st['islands_relocated']} "
                  f"inplace={st['islands_inplace']} clean={st['islands_skipped_clean']} "
                  f"coverage={100.0 * coverage.mean():.1f}%", file=sys.stderr)
        del coverage

    # --- intra-island switching median (structurally cannot cross a frontier)
    px_intra = 0
    if intra_median and intra_median >= 3:
        kk = int(intra_median) | 1
        se = np.ones((kk, kk), np.uint8)
        s = float(np.clip(strength, 0.0, 1.0))
        for k in np.flatnonzero((isl_area >= float(intra_min_area)) & ~parasite):
            f = order[starts[k]:ends[k]]
            t = tri[f]
            x0 = int(max(0, np.floor(t[..., 0].min()) - kk))
            y0 = int(max(0, np.floor(t[..., 1].min()) - kk))
            x1 = int(min(W, np.ceil(t[..., 0].max()) + kk + 1))
            y1 = int(min(H, np.ceil(t[..., 1].max()) + kk + 1))
            if x1 - x0 < kk + 2 or y1 - y0 < kk + 2:
                continue
            mask = np.zeros((y1 - y0, x1 - x0), np.uint8)
            cv2.fillPoly(mask, list(np.round(t - [x0, y0]).astype(np.int32)), 1)
            interior = cv2.erode(mask, se, borderType=cv2.BORDER_CONSTANT, borderValue=0)
            if not interior.any():
                continue
            roi = np.ascontiguousarray(rgb[y0:y1, x0:x1])
            med = cv2.medianBlur(roi, kk)
            diff = np.abs(roi.astype(np.int16) - med.astype(np.int16)).max(axis=2)
            sel = (interior > 0) & (diff > int(impulse_tol))
            n = int(sel.sum())
            if not n:
                continue
            roi[sel] = np.round(roi[sel].astype(np.float32) * (1.0 - s)
                                + med[sel].astype(np.float32) * s).astype(np.uint8)
            rgb[y0:y1, x0:x1] = roi
            px_intra += n
            st["islands_intra_filtered"] += 1

    st["px_changed_purge"] = int(px_purge)
    st["px_changed_intra"] = int(px_intra)
    st["px_changed"] = int(px_purge + px_intra)
    st["seconds"] = round(time.time() - t0, 1)
    return st, new_uv, new_nrm


# -------------------------------------------------------------------------- API
def despeckle_glb(glb_path: str, output_path: str | None = None, *,
                  min_island_px: float = 6.0, strength: float = 1.0, tol: float = 8.0,
                  pad: int = 1, mode: str = "auto", intra_median: int = 3,
                  impulse_tol: int = 24, intra_min_area: float = 64.0,
                  blend_sliver_normals: bool = False,
                  analyze_only: bool = False, verbose: bool = False) -> dict:
    """Atlas-aware despeckle of a GLB. Positions/topology are never modified."""
    g = GLTF2().load(str(glb_path))
    blob = g.binary_blob()

    # Draco-compressed geometry: the UVs live inside the compressed payload, so the
    # islands cannot be segmented and (in relocate mode) the UVs could not be written
    # back without re-encoding. Refuse explicitly instead of crashing — the pipeline
    # must call this module BEFORE any Draco compression step.
    if "KHR_draco_mesh_compression" in (g.extensionsRequired or []):
        return {"ok": False, "schema": SCHEMA, "input": str(glb_path),
                "error": "KHR_draco_mesh_compression: run the despeckle BEFORE Draco "
                         "compression (no Draco decoder available in this venv)",
                "islands_total": 0, "islands_purged": 0, "px_changed": 0}

    def _tex_image(info):
        if info is None:
            return None
        t = g.textures[info.index]
        return None if t.source is None else t.source

    # material -> (baseColor image, texcoord set, all images on that texcoord)
    mat_info = {}
    for mi, mat in enumerate(g.materials or []):
        pbr = getattr(mat, "pbrMetallicRoughness", None)
        if pbr is None or pbr.baseColorTexture is None:
            continue
        base = _tex_image(pbr.baseColorTexture)
        if base is None:
            continue
        tc = int(getattr(pbr.baseColorTexture, "texCoord", 0) or 0)
        imgs = {base}
        for info in (pbr.metallicRoughnessTexture, mat.normalTexture,
                     mat.occlusionTexture, mat.emissiveTexture):
            if info is None:
                continue
            if int(getattr(info, "texCoord", 0) or 0) != tc:
                continue
            src = _tex_image(info)
            if src is not None:
                imgs.add(src)
        mat_info[mi] = (base, tc, sorted(imgs))

    groups = {}
    for mesh in g.meshes or []:
        for prim in mesh.primitives:
            if prim.material is None or prim.material not in mat_info:
                continue
            base, tc, imgs = mat_info[prim.material]
            attr = getattr(prim.attributes, f"TEXCOORD_{tc}", None)
            if attr is None or prim.indices is None or prim.attributes.POSITION is None:
                continue
            groups.setdefault(base, {"images": set(), "prims": []})
            groups[base]["images"].update(imgs)
            groups[base]["prims"].append((prim, attr))

    out = {"ok": True, "schema": SCHEMA, "input": str(glb_path), "mode": mode,
           "islands_total": 0, "islands_purged": 0, "px_changed": 0,
           "normals_blended": 0, "groups": []}
    if not groups:
        out["ok"] = False
        out["error"] = "no baseColorTexture / TEXCOORD found"
        return out

    bv_payload: dict[int, bytes] = {}
    touched_images: dict[int, np.ndarray] = {}

    def _patch_accessor(acc_idx, new_arr, old_arr, ncomp):
        """Rewrite the changed vertices of a float32 accessor, in place, byte-exact."""
        a = g.accessors[acc_idx]
        bv = g.bufferViews[a.bufferView]
        off = bv.byteOffset or 0
        buf = bytearray(bv_payload.get(a.bufferView, blob[off: off + bv.byteLength]))
        stride = bv.byteStride or 4 * ncomp
        base_off = a.byteOffset or 0
        fmt = "<" + "f" * ncomp
        for vi in np.flatnonzero(np.any(new_arr != old_arr, axis=1)):
            o = base_off + int(vi) * stride
            buf[o: o + 4 * ncomp] = struct.pack(fmt, *(float(x) for x in new_arr[vi]))
        bv_payload[a.bufferView] = bytes(buf)
        a.min = [float(new_arr[:, c].min()) for c in range(ncomp)]
        a.max = [float(new_arr[:, c].max()) for c in range(ncomp)]

    for base_img, grp in groups.items():
        uvs, poss, nrms, faces, voff, spans = [], [], [], [], 0, []
        has_nrm = all(p.attributes.NORMAL is not None for p, _ in grp["prims"])
        try:
            images = {i: _decode_image(g, blob, i).copy() for i in sorted(grp["images"])}
            for prim, attr in grp["prims"]:
                uv = _read_accessor(g, blob, attr).astype(np.float32)
                pos = _read_accessor(g, blob, prim.attributes.POSITION).astype(np.float32)
                idx = _read_accessor(g, blob, prim.indices).reshape(-1, 3).astype(np.int64)
                uvs.append(uv)
                poss.append(pos)
                faces.append(idx + voff)
                if has_nrm:
                    nrms.append(_read_accessor(g, blob, prim.attributes.NORMAL).astype(np.float32))
                spans.append((attr, prim.attributes.NORMAL, voff, len(uv)))
                voff += len(uv)
        except (_Unreadable, RuntimeError) as exc:   # skip this group, never crash the run
            out["groups"].append({"image": base_img, "skipped": str(exc),
                                  "islands_total": 0, "islands_purged": 0, "px_changed": 0,
                                  "normals_blended": 0})
            continue
        uv = np.concatenate(uvs)
        pos = np.concatenate(poss)
        f = np.concatenate(faces)
        nrm = np.concatenate(nrms) if has_nrm else None

        def _writable(acc):
            return (acc is not None and g.accessors[acc].componentType == 5126
                    and not g.accessors[acc].normalized)

        uv_writable = all(_writable(a) for a, _, _, _ in spans)
        nrm_writable = has_nrm and all(_writable(nn) for _, nn, _, _ in spans)
        eff_mode = mode
        if mode == "auto":
            eff_mode = "relocate" if uv_writable else "inplace"
        if eff_mode == "relocate" and not uv_writable:
            eff_mode = "inplace"

        stg, new_uv, new_nrm = _process_group(
            images, base_img, uv, pos, f, nrm if nrm_writable else None,
            min_island_px=min_island_px, strength=strength, tol=tol, pad=pad,
            mode=eff_mode, intra_median=intra_median, impulse_tol=impulse_tol,
            intra_min_area=intra_min_area, blend_sliver_normals=blend_sliver_normals,
            verbose=verbose)
        stg["image"] = base_img
        stg["mode"] = eff_mode
        stg["uv_rewritten"] = bool(new_uv is not None)
        stg["normals_rewritten"] = bool(new_nrm is not None)
        out["groups"].append(stg)
        out["islands_total"] += stg["islands_total"]
        out["islands_purged"] += stg["islands_purged"]
        out["px_changed"] += stg["px_changed"]
        out["normals_blended"] += stg["normals_blended"]

        if analyze_only or (stg["px_changed"] == 0 and new_uv is None and new_nrm is None):
            continue
        if stg["px_changed"]:
            for i, img in images.items():
                touched_images[i] = img
        for acc_uv, acc_n, voff0, n in spans:
            if new_uv is not None:
                _patch_accessor(acc_uv, new_uv[voff0: voff0 + n], uv[voff0: voff0 + n], 2)
            if new_nrm is not None:
                _patch_accessor(acc_n, new_nrm[voff0: voff0 + n], nrm[voff0: voff0 + n], 3)

    if analyze_only or not output_path:
        out["output"] = None
        return out

    if touched_images:
        for i, img in touched_images.items():
            bv_payload[g.images[i].bufferView] = _encode_png(img)
            g.images[i].mimeType = "image/png"
        _write_glb(g, blob, bv_payload, str(output_path))
    else:                                           # strict no-op -> byte copy
        Path(output_path).write_bytes(Path(glb_path).read_bytes())
    out["output"] = str(output_path)
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Atlas-aware despeckle (TRELLIS micro-island mouchetis)")
    ap.add_argument("--glb", required=True)
    ap.add_argument("--output")
    ap.add_argument("--min-island-px", type=float, default=6.0,
                    help="island area in TEXELS below which the chart is a parasite (default 6)")
    ap.add_argument("--strength", type=float, default=1.0, help="0..1 blend of the correction")
    ap.add_argument("--tol", type=float, default=8.0,
                    help="Lab dE76 above which a parasite chart is deemed wrong (no-op below)")
    ap.add_argument("--pad", type=int, default=1, help="texel dilation (bilinear footprint), inplace mode")
    ap.add_argument("--mode", choices=("auto", "relocate", "inplace"), default="auto")
    ap.add_argument("--intra-median", type=int, default=3,
                    help="kernel of the intra-island switching median (0 = off)")
    ap.add_argument("--no-intra-median", action="store_true")
    ap.add_argument("--impulse-tol", type=int, default=24,
                    help="0-255 deviation above which a texel is an impulse (salt & pepper)")
    ap.add_argument("--intra-min-area", type=float, default=64.0,
                    help="min island area in texels to run the intra-island median")
    ap.add_argument("--blend-sliver-normals", action="store_true",
                    help="also re-point the shading NORMAL of the parasite charts at the "
                         "surrounding surface (they are sliver micro-facets tilted ~63 deg, "
                         "which leaves a SHADING speck even once the colour is fixed). "
                         "Positions/topology stay untouched. Off by default.")
    ap.add_argument("--analyze-only", action="store_true")
    ap.add_argument("--verbose", action="store_true")
    a = ap.parse_args(argv)

    if not a.analyze_only and not a.output:
        print(json.dumps({"ok": False, "error": "--output required (or --analyze-only)"}))
        return 2
    try:
        res = despeckle_glb(a.glb, a.output, min_island_px=a.min_island_px,
                            strength=a.strength, tol=a.tol, pad=a.pad, mode=a.mode,
                            intra_median=0 if a.no_intra_median else a.intra_median,
                            impulse_tol=a.impulse_tol, intra_min_area=a.intra_min_area,
                            blend_sliver_normals=a.blend_sliver_normals,
                            analyze_only=a.analyze_only, verbose=a.verbose)
    except Exception as exc:                        # noqa: BLE001 - CLI contract is JSON
        print(json.dumps({"ok": False, "error": f"{type(exc).__name__}: {exc}"}))
        return 1
    print(json.dumps(res))
    print("AURORA_DESPECKLE_ATLAS_RESULT:" + json.dumps(res), flush=True)
    return 0 if res.get("ok") else 1


if __name__ == "__main__":
    sys.exit(main())
