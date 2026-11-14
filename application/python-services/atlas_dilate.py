#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""atlas_dilate — remplit les gouttières de l'atlas albedo par dilatation.

Le bake TRELLIS.2 laisse entre les îlots UV des gouttières de bruit sombre.
L'échantillonnage bilinéaire/mipmap tombe dedans aux coutures -> le modèle
rendu est constellé de MOUCHETURES sombres (vérifié: Pikachu 25/07, "poivré"
sur tout le corps). Remède standard de l'industrie: étendre la couleur des
îlots dans les gouttières (dilatation). Ici en une passe exacte:
  1. masque des pixels VALIDES = rasterisation des triangles UV du GLB;
  2. pour chaque pixel de gouttière, couleur du pixel valide LE PLUS PROCHE
     (cv2.distanceTransform avec labels, O(n));
  3. ré-empaquetage du PNG dans le GLB (octets seulement, rien d'autre bouge).

Général: tout GLB à atlas unique ou multiple, toute résolution.
Usage: python atlas_dilate.py --glb in.glb [--out out.glb]
"""
from __future__ import annotations

import argparse
import io
import json

import numpy as np


def _uv_valid_mask(g, mesh_img_idx: int, taille: tuple[int, int]) -> np.ndarray:
    """Masque bool (H, W) des texels couverts par au moins un triangle UV."""
    import cv2

    H, W = taille
    blob = g.binary_blob()

    def _acc_array(idx):
        acc = g.accessors[idx]
        bv = g.bufferViews[acc.bufferView]
        comp = {5120: np.int8, 5121: np.uint8, 5122: np.int16,
                5123: np.uint16, 5125: np.uint32, 5126: np.float32}[acc.componentType]
        ncomp = {"SCALAR": 1, "VEC2": 2, "VEC3": 3, "VEC4": 4}[acc.type]
        off = (bv.byteOffset or 0) + (acc.byteOffset or 0)
        a = np.frombuffer(blob, dtype=comp, count=acc.count * ncomp, offset=off)
        return a.reshape(acc.count, ncomp)

    masque = np.zeros((H, W), dtype=np.uint8)
    for mesh in g.meshes:
        for prim in mesh.primitives:
            attrs = prim.attributes
            if attrs.TEXCOORD_0 is None or prim.indices is None:
                continue
            # ne rasterise que les primitives qui pointent vers CETTE image
            try:
                mat = g.materials[prim.material]
                ti = mat.pbrMetallicRoughness.baseColorTexture.index
                if g.textures[ti].source != mesh_img_idx:
                    continue
            except Exception:  # noqa: BLE001
                pass
            uv = _acc_array(attrs.TEXCOORD_0).astype(np.float64)
            idx = _acc_array(prim.indices).reshape(-1)
            tris = uv[idx].reshape(-1, 3, 2)
            pts = np.empty_like(tris, dtype=np.float64)
            pts[..., 0] = tris[..., 0] * (W - 1)
            pts[..., 1] = tris[..., 1] * (H - 1)
            pts_i = np.round(pts).astype(np.int32)
            # fillPoly par paquets (une liste geante = un seul appel C)
            cv2.fillPoly(masque, list(pts_i), 1)
    return masque.astype(bool)


def _dilater_sans_pygltflib(glb_path: str, out_path: str) -> dict:
    """Fallback sans pygltflib utilisant glb_io + trimesh + OpenCV."""
    import cv2
    from PIL import Image
    import trimesh
    import glb_io

    m = trimesh.load(glb_path, force="mesh", process=False)
    vis = getattr(m, "visual", None)
    uv = getattr(vis, "uv", None)
    f = getattr(m, "faces", None)
    if uv is None or f is None or len(f) == 0:
        return {"ok": True, "note": "pas d'UV a dilater"}
    uv = np.asarray(uv, dtype=np.float64)
    f = np.asarray(f, dtype=np.int64)

    j, blob = glb_io.load(glb_path)
    images = j.get("images") or []
    if not images:
        return {"ok": True, "note": "aucune image dans le GLB"}

    rapport = {"ok": True, "images": [], "backend": "glb_io"}
    tris = uv[f]
    for idx_img in range(len(images)):
        try:
            raw_bytes = glb_io.image_bytes(j, blob, idx_img)
            im = Image.open(io.BytesIO(raw_bytes)).convert("RGB")
            a = np.asarray(im, dtype=np.uint8).copy()
            H, W = a.shape[:2]
            masque = np.zeros((H, W), dtype=np.uint8)
            pts = np.empty_like(tris, dtype=np.float64)
            pts[..., 0] = tris[..., 0] * (W - 1)
            pts[..., 1] = (1.0 - tris[..., 1]) * (H - 1)
            cv2.fillPoly(masque, list(np.round(pts).astype(np.int32)), 1)
            valide = masque.astype(bool)
            couverture = float(valide.mean())
            if couverture < 0.02 or couverture > 0.995:
                continue
            _med = cv2.medianBlur(a, 5)
            _ecart = np.abs(a.astype(np.int16) - _med.astype(np.int16)).max(axis=2)
            _mouchetures = valide & (_ecart > 40)
            if _mouchetures.any():
                a = np.where(_mouchetures[..., None], _med, a).astype(np.uint8)
            _, labels = cv2.distanceTransformWithLabels(
                (~valide).astype(np.uint8), cv2.DIST_L2, 3, labelType=cv2.DIST_LABEL_PIXEL
            )
            plats = np.flatnonzero(valide.ravel())
            corresp = np.zeros(labels.max() + 1, dtype=np.int64)
            corresp[labels.ravel()[plats]] = plats
            rempli = a.reshape(-1, 3)[corresp[labels.ravel()]].reshape(a.shape)
            sortie = np.where(valide[..., None], a, rempli).astype(np.uint8)
            buf = io.BytesIO()
            Image.fromarray(sortie).save(buf, format="PNG")
            # Remplacer uniquement la premiere image (baseColorTexture) ou via trimesh si unique
            if idx_img == 0 and getattr(vis, "material", None) is not None:
                vis.material.baseColorTexture = Image.fromarray(sortie)
                rapport["images"].append({"image": idx_img, "couverture": round(couverture, 3)})
        except Exception:
            continue
    if rapport["images"]:
        m.export(out_path)
    elif out_path != glb_path:
        import shutil
        shutil.copyfile(glb_path, out_path)
    return rapport


def dilater(glb_path: str, out_path: str | None = None) -> dict:
    import cv2
    from PIL import Image
    out_path = out_path or glb_path
    try:
        from pygltflib import GLTF2
    except ImportError:
        return _dilater_sans_pygltflib(glb_path, out_path)
    g = GLTF2().load(glb_path)
    blob = g.binary_blob()
    rapport = {"ok": True, "images": []}
    nouveaux: dict[int, bytes] = {}
    for i, img in enumerate(g.images or []):
        if img.bufferView is None:
            continue
        bv = g.bufferViews[img.bufferView]
        data = blob[bv.byteOffset:bv.byteOffset + bv.byteLength]
        im = Image.open(io.BytesIO(data)).convert("RGB")
        a = np.asarray(im)
        H, W = a.shape[:2]
        # le masque UV etait cherche pour CETTE image; les cartes normal/ORM/
        # emissive partagent les MEMES UV que l'albedo de leur materiau: sans
        # ca elles etaient "sautees" (couverture 0) et gardaient leurs
        # gouttieres -> taches sombres au rendu.
        valide = _uv_valid_mask(g, i, (H, W))
        if valide.mean() < 0.02:
            for _alt in range(len(g.images or [])):
                if _alt == i:
                    continue
                _m = _uv_valid_mask(g, _alt, (H, W))
                if _m.mean() > 0.05:
                    valide = _m
                    break
        couverture = float(valide.mean())
        if couverture < 0.02 or couverture > 0.995:
            rapport["images"].append({"image": i, "saut": True,
                                      "couverture": round(couverture, 3)})
            continue
        # DESPECKLAGE. La dilatation ci-dessous ne traite QUE les texels
        # NOIRS (gouttieres non peintes) — un texel deja peint mais d'une
        # COULEUR ABERRANTE isolee (bake normal/AO/projection sur une
        # geometrie a des dizaines de milliers de micro-ilots) n'est jamais
        # touche (verifie: mouchetures noires ET colorees visibles sur les
        # ailes d'un rendu 256 echantillons, donc PAS du bruit de rendu).
        # Filtre median LOCAL, applique seulement aux texels qui s'ecartent
        # fort de leur voisinage immediat DEJA VALIDE — un outlier ponctuel,
        # jamais une grande zone de couleur legitime (bordee par construction).
        _med = cv2.medianBlur(a, 5)
        _ecart = np.abs(a.astype(np.int16) - _med.astype(np.int16)).max(axis=2)
        _mouchetures = valide & (_ecart > 40)
        if _mouchetures.any():
            a = np.where(_mouchetures[..., None], _med, a).astype(np.uint8)
            rapport.setdefault("despeckle", {})[i] = int(_mouchetures.sum())
        # pixel valide le plus proche pour chaque texel de gouttiere
        dist, labels = cv2.distanceTransformWithLabels(
            (~valide).astype(np.uint8), cv2.DIST_L2, 3,
            labelType=cv2.DIST_LABEL_PIXEL)
        # index du pixel valide correspondant a chaque label
        plats = np.flatnonzero(valide.ravel())
        # labels numerotes dans l'ordre des pixels valides rencontres
        corresp = np.zeros(labels.max() + 1, dtype=np.int64)
        corresp[labels.ravel()[plats]] = plats
        rempli = a.reshape(-1, 3)[corresp[labels.ravel()]].reshape(a.shape)
        sortie = np.where(valide[..., None], a, rempli)
        buf = io.BytesIO()
        Image.fromarray(sortie.astype(np.uint8)).save(buf, format="PNG")
        nouveaux[img.bufferView] = buf.getvalue()
        rapport["images"].append({"image": i, "couverture": round(couverture, 3),
                                  "octets": len(nouveaux[img.bufferView])})
    if not nouveaux:
        rapport["note"] = "aucun atlas modifie"
        g.save(out_path) if out_path != glb_path else None
        return rapport
    # reconstruire le blob binaire avec les PNG remplaces
    ordre = sorted(range(len(g.bufferViews)),
                   key=lambda k: g.bufferViews[k].byteOffset or 0)
    morceaux, offset = [], 0
    anciens = {k: (g.bufferViews[k].byteOffset or 0, g.bufferViews[k].byteLength)
               for k in ordre}
    for k in ordre:
        bv = g.bufferViews[k]
        data = (nouveaux.get(k)
                or blob[anciens[k][0]:anciens[k][0] + anciens[k][1]])
        pad = (4 - offset % 4) % 4
        morceaux.append(b"\x00" * pad)
        offset += pad
        bv.byteOffset = offset
        bv.byteLength = len(data)
        morceaux.append(data)
        offset += len(data)
    nouveau_blob = b"".join(morceaux)
    g.buffers[0].byteLength = len(nouveau_blob)
    g.set_binary_blob(nouveau_blob)
    g.save(out_path)
    rapport["sortie"] = out_path
    return rapport


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--glb", required=True)
    ap.add_argument("--out", default=None)
    a = ap.parse_args()
    print(json.dumps(dilater(a.glb, a.out), ensure_ascii=False))
