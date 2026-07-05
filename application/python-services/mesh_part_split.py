#!/usr/bin/env python
"""Aurora — split a single-component mesh into independently-animatable parts.

The user's complaint: "le chassis entier qui bouge en tournant sauter ou
autre mais c'est pas ça la demande normalement il est sensé bouger comme
il le faut". The root cause is upstream: Hunyuan3D 2.1 fuses everything
into a single watertight component (verified via trimesh.split → 1
component on every Cat). Real connected-component splitting yields
nothing to split.

This module uses geometric clustering as a substitute: k-means on
vertex positions partitions the mesh into k spatially-coherent regions.
Each region becomes a separate glTF mesh + node, with the centroid
becoming its translation pivot. Result: a downstream animation injector
can rotate each region around its own centroid, producing relative
motion between sub-parts (the "gears spinning in opposite directions"
behavior you'd expect from a mechanical asset).

This is a heuristic — it doesn't recover the original semantic parts
that Hunyuan never separated. But it gives the asset enough internal
structure to animate plausibly, instead of "single rigid blob rotating
as one chunk".

Schema: aurora.mesh_part_split.v1.

Usage:
    python mesh_part_split.py --input cat3_meca_mesh_textured.glb \\
        --output cat3_meca_split.glb --k 4 --pretty
"""

from __future__ import annotations

import argparse
import json
import struct
import sys
from pathlib import Path


def _read_source_metadata(input_path: Path) -> tuple[dict, list[bytes]]:
    """Read the source GLB's glTF JSON + binary chunk, then resolve any
    embedded image bufferViews into raw bytes. Returns (gltf_json, [image_bytes_per_image]).
    Returns ({}, []) on any read error."""
    try:
        raw = input_path.read_bytes()
        if raw[:4] != b"glTF":
            return {}, []
        json_len, _ = struct.unpack_from("<II", raw, 12)
        json_blob = raw[20:20 + json_len].rstrip(b"\x00")
        gltf = json.loads(json_blob)
        # The bin chunk follows
        bin_chunk_offset = 20 + ((json_len + 3) & ~3)
        bin_len, bin_type = struct.unpack_from("<II", raw, bin_chunk_offset)
        bin_blob = raw[bin_chunk_offset + 8:bin_chunk_offset + 8 + bin_len]
        # Resolve images
        out_images: list[bytes] = []
        bvs = gltf.get("bufferViews") or []
        for img in gltf.get("images") or []:
            bv_idx = img.get("bufferView")
            if bv_idx is None:
                out_images.append(b"")
                continue
            bv = bvs[bv_idx]
            off = bv.get("byteOffset", 0)
            length = bv.get("byteLength", 0)
            out_images.append(bin_blob[off:off + length])
        return gltf, out_images
    except (OSError, ValueError, KeyError, IndexError):
        return {}, []


def _emit_glb(gltf: dict, bin_blob: bytes, output_path: Path) -> int:
    new_json = json.dumps(gltf, separators=(",", ":")).encode("utf-8")
    json_pad = (4 - (len(new_json) % 4)) % 4
    new_json_padded = new_json + (b" " * json_pad)
    bin_pad = (4 - (len(bin_blob) % 4)) % 4
    new_bin_padded = bin_blob + (b"\x00" * bin_pad)
    total = 12 + 8 + len(new_json_padded) + 8 + len(new_bin_padded)
    out = bytearray()
    out += b"glTF"
    out += struct.pack("<II", 2, total)
    out += struct.pack("<II", len(new_json_padded), 0x4E4F534A)
    out += new_json_padded
    out += struct.pack("<II", len(new_bin_padded), 0x004E4942)
    out += new_bin_padded
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(bytes(out))
    return total


def _kmeans_lloyd(points, k: int, n_iter: int = 12, seed: int = 42):
    """Tiny Lloyd's k-means in pure numpy — no sklearn dep. Returns
    (labels (N,), centroids (k,3))."""
    import numpy as np
    rng = np.random.default_rng(seed)
    # k-means++ seeding for stable initial centroids
    n = len(points)
    centroid_indices = [int(rng.integers(0, n))]
    for _ in range(k - 1):
        chosen = points[centroid_indices]
        # squared distance from each point to nearest existing centroid
        d2 = ((points[:, None, :] - chosen[None, :, :]) ** 2).sum(-1).min(-1)
        if d2.sum() <= 0:
            centroid_indices.append(int(rng.integers(0, n)))
            continue
        probs = d2 / d2.sum()
        nxt = int(rng.choice(n, p=probs))
        centroid_indices.append(nxt)
    centroids = points[centroid_indices].copy()

    labels = np.zeros(n, dtype=np.int32)
    for _ in range(n_iter):
        # assign
        diffs = points[:, None, :] - centroids[None, :, :]
        d2 = (diffs * diffs).sum(-1)
        new_labels = d2.argmin(axis=1).astype(np.int32)
        if (new_labels == labels).all():
            labels = new_labels
            break
        labels = new_labels
        # update
        for j in range(k):
            mask = labels == j
            if mask.any():
                centroids[j] = points[mask].mean(axis=0)
    return labels, centroids


def split(input_path: Path, output_path: Path, k: int = 4) -> dict:
    """Split a single-mesh GLB into k spatially-clustered sub-meshes.
    Output GLB has k meshes + k nodes (one per cluster), each with its
    own translation set to the cluster centroid so child rotation is
    relative to the part center. Never raises."""
    if not input_path.is_file():
        return {"ok": False, "error": f"input not found: {input_path}"}
    try:
        import trimesh
        import numpy as np
    except ImportError as exc:
        return {"ok": False, "error": f"missing dep: {exc}"}

    try:
        m = trimesh.load(input_path, force="mesh")
    except Exception as exc:
        return {"ok": False, "error": f"load failed: {exc}"}

    # Read the source glTF JSON so we can carry its materials/textures/images/
    # samplers arrays + their backing image bytes into the split output.
    src_gltf, src_image_bytes = _read_source_metadata(input_path)
    src_materials = src_gltf.get("materials") or []
    src_textures = src_gltf.get("textures") or []
    src_samplers = src_gltf.get("samplers") or []

    verts = np.asarray(m.vertices, dtype=np.float32)
    faces = np.asarray(m.faces, dtype=np.uint32)
    n_v = len(verts)
    n_f = len(faces)
    if n_v == 0 or n_f == 0:
        return {"ok": False, "error": "empty mesh"}
    if n_v < k:
        return {"ok": False, "error": f"too few vertices ({n_v}) for k={k}"}

    # Read original UVs and material if present (we want to preserve them
    # per-cluster). Fall back to sampling per-vertex if absent.
    has_uv = False
    uvs = None
    if hasattr(m.visual, "uv") and m.visual.uv is not None and len(m.visual.uv) == n_v:
        uvs = np.asarray(m.visual.uv, dtype=np.float32)
        has_uv = True

    # k-means on vertex positions
    labels, centroids = _kmeans_lloyd(verts, k=k)

    # Each face is assigned to the cluster of the majority of its 3 verts.
    # Faces with all-3-verts in the same cluster are "clean"; mixed faces
    # are assigned to the dominant cluster (any tie → first vertex's cluster).
    face_labels = np.zeros(n_f, dtype=np.int32)
    fv_labels = labels[faces]
    for i in range(n_f):
        # mode of 3 ints — small enough for direct loop or vectorized counting
        a, b, c = fv_labels[i]
        if a == b or a == c:
            face_labels[i] = a
        elif b == c:
            face_labels[i] = b
        else:
            face_labels[i] = a  # all 3 distinct → pick first

    # Build per-cluster geometry
    bin_parts: list[bytes] = []
    accs: list[dict] = []
    bvs: list[dict] = []
    meshes_json: list[dict] = []
    nodes_json: list[dict] = []

    def _add_buffer(buf: bytes) -> tuple[int, int]:
        pad = (4 - (len(buf) % 4)) % 4
        offset = sum(len(p) for p in bin_parts)
        bin_parts.append(buf)
        if pad:
            bin_parts.append(b"\x00" * pad)
        return offset, len(buf)

    cluster_stats: list[dict] = []
    for cluster_id in range(k):
        face_mask = face_labels == cluster_id
        cluster_faces = faces[face_mask]
        if len(cluster_faces) == 0:
            cluster_stats.append({"cluster": cluster_id, "n_faces": 0, "skipped": True})
            continue

        # Compact vertices: only keep vertices referenced by this cluster's faces
        used_v = np.unique(cluster_faces)
        vmap = -np.ones(n_v, dtype=np.int32)
        vmap[used_v] = np.arange(len(used_v), dtype=np.int32)
        local_faces = vmap[cluster_faces]
        local_verts = verts[used_v]
        local_uvs = uvs[used_v] if has_uv else None

        # Centroid of this cluster's geometry — used as the node translation
        # so the part's own rotation/scale animations pivot around its center.
        center = centroids[cluster_id].astype(np.float32)
        local_verts_centered = local_verts - center

        # Add buffers
        pos_off, pos_size = _add_buffer(local_verts_centered.astype(np.float32).tobytes())
        bv_pos = len(bvs)
        bvs.append({"buffer": 0, "byteOffset": pos_off, "byteLength": pos_size})
        accs.append({
            "bufferView": bv_pos, "componentType": 5126,
            "count": len(local_verts_centered), "type": "VEC3",
            "min": local_verts_centered.min(axis=0).tolist(),
            "max": local_verts_centered.max(axis=0).tolist(),
        })
        acc_pos = len(accs) - 1

        attrs = {"POSITION": acc_pos}

        if has_uv:
            uv_off, uv_size = _add_buffer(local_uvs.astype(np.float32).tobytes())
            bv_uv = len(bvs)
            bvs.append({"buffer": 0, "byteOffset": uv_off, "byteLength": uv_size})
            accs.append({
                "bufferView": bv_uv, "componentType": 5126,
                "count": len(local_uvs), "type": "VEC2",
            })
            attrs["TEXCOORD_0"] = len(accs) - 1

        idx_off, idx_size = _add_buffer(local_faces.astype(np.uint32).tobytes())
        bv_idx = len(bvs)
        bvs.append({"buffer": 0, "byteOffset": idx_off, "byteLength": idx_size})
        accs.append({
            "bufferView": bv_idx, "componentType": 5125,
            "count": int(local_faces.size), "type": "SCALAR",
        })
        acc_idx = len(accs) - 1

        prim = {"attributes": attrs, "indices": acc_idx, "mode": 4}
        # Re-bind the source material if it had one (covers the textured
        # input case so each split part keeps its baseColorTexture binding).
        if src_materials:
            prim["material"] = 0
        meshes_json.append({
            "name": f"part_{cluster_id}",
            "primitives": [prim],
        })

        nodes_json.append({
            "name": f"part_{cluster_id}_node",
            "mesh": len(meshes_json) - 1,
            "translation": center.tolist(),
        })

        cluster_stats.append({
            "cluster": cluster_id,
            "n_faces": int(len(cluster_faces)),
            "n_verts": int(len(used_v)),
            "centroid": center.tolist(),
        })

    if not meshes_json:
        return {"ok": False, "error": "no non-empty clusters produced"}

    # Append the source's images (PNG bytes) into our binary chunk so each
    # textured part shares the same atlas without duplicating bytes per part.
    embedded_images: list[dict] = []
    if src_image_bytes:
        for img_bytes in src_image_bytes:
            if not img_bytes:
                embedded_images.append({})
                continue
            img_off, img_size = _add_buffer(img_bytes)
            bv_img = len(bvs)
            bvs.append({"buffer": 0, "byteOffset": img_off, "byteLength": img_size})
            mime = "image/png"
            if img_bytes[:3] == b"\xff\xd8\xff":
                mime = "image/jpeg"
            embedded_images.append({"bufferView": bv_img, "mimeType": mime})

    bin_blob = b"".join(bin_parts)

    gltf = {
        "asset": {"version": "2.0", "generator": "aurora.mesh_part_split.v1"},
        "scene": 0,
        "scenes": [{"nodes": list(range(len(nodes_json)))}],
        "nodes": nodes_json,
        "meshes": meshes_json,
        "accessors": accs,
        "bufferViews": bvs,
        "buffers": [{"byteLength": 0}],  # patched below after concat
    }
    if src_materials:
        gltf["materials"] = src_materials
    if src_textures:
        gltf["textures"] = src_textures
    if src_samplers:
        gltf["samplers"] = src_samplers
    if embedded_images:
        gltf["images"] = embedded_images

    gltf["buffers"] = [{"byteLength": len(bin_blob)}]

    size = _emit_glb(gltf, bin_blob, output_path)
    parts_real = sum(1 for s in cluster_stats if not s.get("skipped"))
    return {
        "ok": True,
        "schema": "aurora.mesh_part_split.v1",
        "input": str(input_path),
        "output": str(output_path),
        "k_requested": int(k),
        "parts_produced": parts_real,
        "parts_count": parts_real,  # alias used by visual_audit
        "cluster_stats": cluster_stats,
        "size_bytes": int(size),
        "n_total_faces": int(n_f),
        "n_total_verts": int(n_v),
        "uv_preserved": has_uv,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="Aurora mesh part splitter")
    ap.add_argument("--input", required=True)
    ap.add_argument("--output", required=True)
    ap.add_argument("--k", type=int, default=4)
    ap.add_argument("--pretty", action="store_true")
    args = ap.parse_args()
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
    except (AttributeError, ValueError):
        pass

    res = split(Path(args.input), Path(args.output), args.k)
    if args.pretty and res.get("ok"):
        sys.stdout.write(
            f"OK · k={res['k_requested']} → {res['parts_produced']} parts · "
            f"{res['n_total_verts']:,} verts / {res['n_total_faces']:,} faces · "
            f"out {res['size_bytes'] / 1e6:.1f} MB · uv={res['uv_preserved']}\n"
            f"  → {res['output']}\n"
        )
        for s in res["cluster_stats"]:
            if s.get("skipped"):
                continue
            c = s["centroid"]
            sys.stdout.write(
                f"    part_{s['cluster']}: verts={s['n_verts']:,} faces={s['n_faces']:,} "
                f"centroid=[{c[0]:.2f}, {c[1]:.2f}, {c[2]:.2f}]\n"
            )
    else:
        sys.stdout.write(json.dumps(res, indent=2, ensure_ascii=True) + "\n")
    return 0 if res.get("ok") else 1


if __name__ == "__main__":
    sys.exit(main())
