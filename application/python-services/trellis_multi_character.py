#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""trellis_multi_character.py — Detection et reconstruction 3D par personnage
pour les scenes multi-personnages cote a cote (ex: Zig et Sharko).

Pourquoi :
Quand une image de reference contient 2 ou 3 personnages distincts cote a cote,
un passage unique dans TRELLIS.2 gaspille >70 % de la grille voxel sur le vide
entre eux, relie leurs pieds par une dalle noire parasite et reduit la
resolution faciale par 4.

Ce module :
  1. Detecte si la reference RGBA contient 2 ou 3 personnages cote a cote
     (composantes connexes d'aire >= 12 % et de hauteur >= 45 %, ou separees
     par un couloir vertical vide dans les 85 % superieurs si leurs socles se
     touchent en bas).
  2. Extrait chaque personnage dans son propre carre RGBA 1024x1024 haute
     resolution en conservant ses proportions relatives et sa position 2D.
  3. Apres reconstruction TRELLIS.2 individuelle de chaque personnage, dilate
     chaque atlas individuel (gouttieres propres), balaie les confettis
     flottants, puis assemble les maillages 3D cote a cote sur le meme plan de
     sol avec un atlas PBR 4096x4096 unifie sans couture ni collision.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import cv2
import numpy as np
from PIL import Image


def detect_and_crop_characters(ref_png_path: str | Path, out_dir: str | Path, run_id: str) -> list[dict[str, Any]]:
    """Retourne une liste de dicts (2 ou 3 personnages tries de gauche a droite)
    ou [] s'il s'agit d'un sujet unique."""
    ref_p = Path(ref_png_path)
    out_p = Path(out_dir)
    if not ref_p.is_file():
        return []
    try:
        im = Image.open(str(ref_p)).convert("RGBA")
        rgba = np.asarray(im, dtype=np.uint8)
    except Exception:
        return []

    H, W = rgba.shape[:2]
    alpha = rgba[:, :, 3]
    if float((alpha < 128).mean()) > 0.05:
        fg = (alpha > 96).astype(np.uint8)
    else:
        fg = (rgba[:, :, :3].min(axis=2) < 240).astype(np.uint8)

    tot_fg = int(fg.sum())
    if tot_fg < 1500:
        return []

    ys_all, xs_all = np.nonzero(fg)
    y_min_all, y_max_all = int(ys_all.min()), int(ys_all.max())
    x_min_all, x_max_all = int(xs_all.min()), int(xs_all.max())
    H_tot = max(1, y_max_all - y_min_all + 1)
    W_tot = max(1, x_max_all - x_min_all + 1)

    num_labels, labels, stats, _ = cv2.connectedComponentsWithStats(fg, connectivity=8)
    comp_masks: list[np.ndarray] = []
    for i in range(1, num_labels):
        area = int(stats[i, cv2.CC_STAT_AREA])
        hc = int(stats[i, cv2.CC_STAT_HEIGHT])
        if area >= 0.12 * tot_fg and hc >= 0.45 * H_tot:
            comp_masks.append(labels == i)

    # Cas ou deux personnages cote a cote ont leurs socles ou pieds qui se
    # touchent legerement tout en bas, mais leurs corps sont separes par un
    # couloir vertical vide sur les 82 % superieurs de la hauteur :
    if len(comp_masks) == 1 and W_tot >= 0.65 * H_tot:
        y_upper_end = y_min_all + int(0.82 * H_tot)
        upper_strip = fg[y_min_all:y_upper_end, x_min_all:x_max_all + 1]
        col_sums = upper_strip.sum(axis=0)
        # Chercher une vallee quasi-vide dans le tiers central [25%, 75%]
        c0 = int(0.25 * W_tot)
        c1 = int(0.75 * W_tot)
        if c1 > c0 + 10:
            mid_cols = col_sums[c0:c1]
            zero_cols = np.where(mid_cols <= 2)[0]
            if len(zero_cols) >= 6:
                split_x = x_min_all + c0 + int(np.median(zero_cols))
                m_left = (fg > 0).copy()
                m_left[:, split_x:] = False
                m_right = (fg > 0).copy()
                m_right[:, :split_x] = False
                if m_left.sum() >= 0.15 * tot_fg and m_right.sum() >= 0.15 * tot_fg:
                    comp_masks = [m_left, m_right]

    if not (2 <= len(comp_masks) <= 3):
        return []

    # Calculer les boites et trier de gauche a droite
    infos_raw: list[dict[str, Any]] = []
    for m in comp_masks:
        ys, xs = np.nonzero(m)
        if len(xs) < 200:
            continue
        x0, x1 = int(xs.min()), int(xs.max())
        y0, y1 = int(ys.min()), int(ys.max())
        hc = y1 - y0 + 1
        wc = x1 - x0 + 1
        if hc < 0.45 * H_tot or int(m.sum()) < 0.12 * tot_fg:
            continue
        infos_raw.append({
            "mask": m,
            "x0": x0, "x1": x1, "y0": y0, "y1": y1,
            "wc": wc, "hc": hc,
            "x_center": 0.5 * (x0 + x1),
        })

    if not (2 <= len(infos_raw) <= 3):
        return []

    infos_raw.sort(key=lambda d: d["x_center"])

    # Verifier que les personnages sont bien cote a cote (faible chevauchement X)
    for idx in range(len(infos_raw) - 1):
        a = infos_raw[idx]
        b = infos_raw[idx + 1]
        overlap_x = min(a["x1"], b["x1"]) - max(a["x0"], b["x0"])
        if overlap_x > 0.12 * min(a["wc"], b["wc"]):
            return []

    out_p.mkdir(parents=True, exist_ok=True)
    k_dil = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
    results: list[dict[str, Any]] = []
    x_center_all = 0.5 * (x_min_all + x_max_all)

    for idx, item in enumerate(infos_raw):
        m_dil = cv2.dilate(item["mask"].astype(np.uint8), k_dil, iterations=1) > 0
        # Exclure les pixels appartenant franchement aux autres personnages
        other_mask = np.zeros_like(item["mask"], dtype=bool)
        for j, other in enumerate(infos_raw):
            if j != idx:
                other_mask |= other["mask"]
        keep = m_dil & (~other_mask) & (alpha > 8 if float((alpha < 128).mean()) > 0.05 else (fg > 0))

        char_rgba = np.zeros_like(rgba)
        char_rgba[keep] = rgba[keep]
        x0, x1, y0, y1 = item["x0"], item["x1"], item["y0"], item["y1"]
        crop = char_rgba[y0:y1 + 1, x0:x1 + 1]
        ch, cw = crop.shape[:2]

        # Placer au centre d'un canevas carre 1024x1024 avec 8% de marge
        side = int(max(ch, cw) * 1.16)
        side = max(side, 64)
        canvas = np.zeros((side, side, 4), dtype=np.uint8)
        oy = (side - ch) // 2
        ox = (side - cw) // 2
        canvas[oy:oy + ch, ox:ox + cw] = crop
        pil_char = Image.fromarray(canvas, mode="RGBA").resize(
            (1024, 1024), Image.Resampling.LANCZOS
        )
        # Suppression propre d'une eventuelle ombre portee grise au sol sans alterer
        # les couleurs sombres (truffe, yeux, encrage) ni eroder la silhouette
        try:
            c_arr = np.asarray(pil_char, dtype=np.uint8).copy()
            c_a = c_arr[..., 3]
            c_rgb = c_arr[..., :3].astype(np.float32)
            c_sat = c_rgb.max(axis=2) - c_rgb.min(axis=2)
            c_luma = 0.299 * c_rgb[..., 0] + 0.587 * c_rgb[..., 1] + 0.114 * c_rgb[..., 2]
            yy_c, _ = np.mgrid[0:1024, 0:1024]
            floor_sh = (yy_c > 885) & (c_sat < 24) & (c_luma > 135) & (c_luma < 245)
            fg_c = (c_a > 128) & (~floor_sh)
            c_arr[..., :3] = np.where(fg_c[..., None], c_arr[..., :3], 0)
            c_arr[..., 3] = np.where(fg_c, c_a, 0).astype(np.uint8)
            pil_char = Image.fromarray(c_arr, mode="RGBA")
        except Exception:
            pass
        char_ref_path = out_p / f"{run_id}_char{idx}_ref.png"
        pil_char.save(str(char_ref_path))

        results.append({
            "index": idx,
            "ref_path": str(char_ref_path),
            "glb_path": str(out_p / f"{run_id}_char{idx}.glb"),
            "x_center_rel": (item["x_center"] - x_center_all) / float(H_tot),
            "y_min_rel": (y_max_all - y1) / float(H_tot),
            "h_rel": float(item["hc"]) / float(H_tot),
            "w_rel": float(item["wc"]) / float(H_tot),
        })

    return results


def exporter_personnage_place(source: str | Path, cible: str | Path, scale: float, translation: list[float]) -> None:
    """Copie le GLB d'un personnage (textures PBR intactes) sous un nœud racine qui le met à sa
    place dans la scène fusionnée : v' = scale · v + translation, comme dans `merge_character_glbs`."""
    import glb_io
    doc, blob = glb_io.load(str(source))
    scenes = doc.get("scenes") or [{"nodes": list(range(len(doc.get("nodes") or [])))}]
    scene_index = int(doc.get("scene", 0) or 0)
    racines = list(scenes[scene_index].get("nodes") or [])
    doc.setdefault("nodes", []).append({"name": Path(str(cible)).stem, "children": racines,
                                        "translation": [float(t) for t in translation],
                                        "scale": [float(scale)] * 3})
    scenes[scene_index]["nodes"] = [len(doc["nodes"]) - 1]
    doc["scenes"] = scenes
    doc["scene"] = scene_index
    glb_io.save(str(cible), doc, blob)


def merge_character_glbs(char_infos: list[dict[str, Any]], out_glb_path: str | Path) -> dict[str, Any]:
    """Assemble les GLB individuels des personnages cote a cote dans un unique
    GLB texturé (atlas PBR 4096x4096 unifie)."""
    import trimesh
    from trimesh.visual import TextureVisuals
    from trimesh.visual.material import PBRMaterial

    n = len(char_infos)
    if n == 0:
        return {"ok": False, "error": "aucun personnage a fusionner"}

    atlas_h = 4096
    atlas_w = 4096 * n
    comb_base = Image.new("RGB", (atlas_w, atlas_h), (200, 200, 200))
    comb_mr = Image.new("RGB", (atlas_w, atlas_h), (255, 180, 0))
    comb_norm = Image.new("RGB", (atlas_w, atlas_h), (128, 128, 255))
    has_mr = False
    has_norm = False

    meshes_v: list[np.ndarray] = []
    meshes_f: list[np.ndarray] = []
    meshes_uv: list[np.ndarray] = []
    v_offset = 0
    # Placement de chaque personnage dans la scène fusionnée (échelle puis translation) : il sert
    # à livrer chaque personnage À SA PLACE, pour l'animer seul puis le recomposer (15/11/2026).
    placements: list[dict[str, Any]] = []

    for i, info in enumerate(char_infos):
        gpath = info["glb_path"]
        if not os.path.isfile(gpath):
            return {"ok": False, "error": f"GLB personnage {i} manquant: {gpath}"}

        m = trimesh.load(gpath, force="mesh", process=False)
        v = np.asarray(m.vertices, dtype=np.float64).copy()
        f = np.asarray(m.faces, dtype=np.int64).copy()
        if len(v) == 0 or len(f) == 0:
            return {"ok": False, "error": f"GLB personnage {i} vide"}

        vis = getattr(m, "visual", None)
        uv = getattr(vis, "uv", None)
        if uv is None or len(uv) != len(v):
            uv = np.zeros((len(v), 2), dtype=np.float64)
        else:
            uv = np.asarray(uv, dtype=np.float64).copy()

        mat = getattr(vis, "material", None)
        im_b_arr: np.ndarray | None = None
        if mat is not None:
            bct = getattr(mat, "baseColorTexture", None) or getattr(mat, "image", None)
            if bct is not None:
                im_b = bct.convert("RGB")
                if im_b.size != (4096, atlas_h):
                    im_b = im_b.resize((4096, atlas_h), Image.Resampling.BILINEAR)
                im_b_arr = np.asarray(im_b, dtype=np.uint8).copy()

        # 1) Suppression des galettes d'ombre au sol et micro-débris géométriques
        try:
            ref_m = trimesh.Trimesh(vertices=v.copy(), faces=f.copy(), process=False)
            ref_m.merge_vertices()
            comps = trimesh.graph.connected_components(
                ref_m.face_adjacency, min_len=1, nodes=np.arange(len(ref_m.faces))
            )
            if len(comps) > 1:
                keep_f = np.zeros(len(f), dtype=bool)
                y_all_min = float(v[:, 1].min())
                y_all_span = max(float(v[:, 1].max() - y_all_min), 1e-6)
                for c_idx in comps:
                    if len(c_idx) < 1500:
                        continue
                    fc_c = v[f[c_idx]].mean(axis=1)
                    cy_span = float(fc_c[:, 1].max() - fc_c[:, 1].min())
                    cy_max = float(fc_c[:, 1].max())
                    # Exclure une galette plate d'ombre posée tout en bas
                    if cy_span < 0.03 * y_all_span and (cy_max - y_all_min) < 0.06 * y_all_span:
                        continue
                    keep_f[c_idx] = True
                if keep_f.any():
                    f = f[keep_f]
        except Exception:
            pass

        # 3) Orientation cohérente des normales vers l'extérieur
        if len(f) > 0:
            fc_all = v[f].mean(axis=1)
            c_cent = fc_all.mean(axis=0)
            v0, v1, v2 = v[f[:, 0]], v[f[:, 1]], v[f[:, 2]]
            fn = np.cross(v1 - v0, v2 - v0)
            inward = ((fc_all - c_cent) * fn).sum(axis=1) < 0
            if float(inward.mean()) > 0.25:
                f[inward] = f[inward][:, [0, 2, 1]]

        # 4) Dilatation OpenCV des gouttières UV + despeckle médian par tuile 4096x4096
        if im_b_arr is not None and len(f) > 0:
            try:
                th, tw = im_b_arr.shape[:2]
                mask_uv = np.zeros((th, tw), dtype=np.uint8)
                tris_uv = uv[f]
                pts_uv = np.stack(
                    [tris_uv[..., 0] * (tw - 1), (1.0 - tris_uv[..., 1]) * (th - 1)],
                    axis=-1,
                )
                cv2.fillPoly(mask_uv, list(np.round(pts_uv).astype(np.int32)), 1)
                valide = mask_uv > 0
                if 0.01 < float(valide.mean()) < 0.999:
                    med = cv2.medianBlur(im_b_arr, 5)
                    diff = np.abs(im_b_arr.astype(np.int16) - med.astype(np.int16)).max(axis=2)
                    im_b_arr = np.where((valide & (diff > 35))[..., None], med, im_b_arr).astype(np.uint8)
                    _, labels = cv2.distanceTransformWithLabels(
                        (~valide).astype(np.uint8), cv2.DIST_L2, 3, labelType=cv2.DIST_LABEL_PIXEL
                    )
                    plats = np.flatnonzero(valide.ravel())
                    corresp = np.zeros(labels.max() + 1, dtype=np.int64)
                    corresp[labels.ravel()[plats]] = plats
                    rempli = im_b_arr.reshape(-1, 3)[corresp[labels.ravel()]].reshape(im_b_arr.shape)
                    im_b_arr = np.where(valide[..., None], im_b_arr, rempli)
            except Exception:
                pass

        vmin = v.min(axis=0)
        vmax = v.max(axis=0)
        h3 = max(float(vmax[1] - vmin[1]), 1e-6)
        scale = float(info.get("h_rel", 1.0)) / h3
        v *= scale

        vmin = v.min(axis=0)
        vmax = v.max(axis=0)
        cx = 0.5 * (vmin[0] + vmax[0])
        cz = 0.5 * (vmin[2] + vmax[2])
        translation = [float(info.get("x_center_rel", 0.0)) - cx, float(info.get("y_min_rel", 0.0)) - vmin[1], -cz]
        v[:, 0] += translation[0]
        v[:, 1] += translation[1]
        v[:, 2] += translation[2]
        placements.append({"index": i, "source": gpath, "scale": scale, "translation": translation})

        meshes_v.append(v)
        meshes_f.append(f)

        # Correspondance exacte 1:1 avec la tuile 4096x4096 collees a (i * 4096, 0) :
        # aucun decalage d'echelle (0.992/0.004 decalait les ilots UV de 8 px !)
        u_clip = np.clip(uv[:, 0], 0.0, 1.0)
        v_clip = np.clip(uv[:, 1], 0.0, 1.0)
        uv[:, 0] = (float(i) + u_clip) / float(n)
        uv[:, 1] = v_clip
        meshes_uv.append(uv)

        x_strip0 = i * 4096
        strip_w = 4096

        if im_b_arr is not None:
            comb_base.paste(Image.fromarray(im_b_arr), (x_strip0, 0))
        if mat is not None:
            mrt = getattr(mat, "metallicRoughnessTexture", None)
            if mrt is not None:
                has_mr = True
                im_m = mrt.convert("RGB")
                if im_m.size != (strip_w, atlas_h):
                    im_m = im_m.resize((strip_w, atlas_h), Image.Resampling.BILINEAR)
                comb_mr.paste(im_m, (x_strip0, 0))
            nt = getattr(mat, "normalTexture", None)
            if nt is not None:
                has_norm = True
                im_n = nt.convert("RGB")
                if im_n.size != (strip_w, atlas_h):
                    im_n = im_n.resize((strip_w, atlas_h), Image.Resampling.BILINEAR)
                comb_norm.paste(im_n, (x_strip0, 0))

    # Garantir un leger espace libre (0.03) en X entre boites englobantes
    # adjacentes pour empecher toute collision des bras/nageoires en 3D
    for i in range(len(meshes_v) - 1):
        max_x_left = float(meshes_v[i][:, 0].max())
        min_x_right = float(meshes_v[i + 1][:, 0].min())
        min_gap = 0.03
        if max_x_left + min_gap > min_x_right:
            shift = 0.5 * (max_x_left + min_gap - min_x_right)
            for k in range(i + 1):
                meshes_v[k][:, 0] -= shift
                placements[k]["translation"][0] -= shift
            for k in range(i + 1, len(meshes_v)):
                meshes_v[k][:, 0] += shift
                placements[k]["translation"][0] += shift

    all_v = np.concatenate(meshes_v, axis=0)
    all_f_list: list[np.ndarray] = []
    v_off = 0
    for v_arr, f_arr in zip(meshes_v, meshes_f):
        all_f_list.append(f_arr + v_off)
        v_off += len(v_arr)
    all_f = np.concatenate(all_f_list, axis=0)
    all_uv = np.concatenate(meshes_uv, axis=0)

    # Centrer et normaliser dans la boite [-0.5, 0.5]
    bmin = all_v.min(axis=0)
    bmax = all_v.max(axis=0)
    center = 0.5 * (bmin + bmax)
    extent = max(float((bmax - bmin).max()), 1e-6)
    all_v = (all_v - center) / extent
    # la même normalisation pour chaque personnage livré seul : v' = (s·v + t − centre) / étendue
    for place in placements:
        place["scale"] = float(place["scale"]) / extent
        place["translation"] = [float((t - c) / extent) for t, c in zip(place["translation"], center)]

    pbr_kwargs: dict[str, Any] = {
        "baseColorTexture": comb_base,
        "metallicFactor": 1.0 if has_mr else 0.0,
        "roughnessFactor": 1.0 if has_mr else 0.65,
        "doubleSided": True,
    }
    if has_mr:
        pbr_kwargs["metallicRoughnessTexture"] = comb_mr
    if has_norm:
        pbr_kwargs["normalTexture"] = comb_norm

    mat_out = PBRMaterial(**pbr_kwargs)
    vis_out = TextureVisuals(uv=all_uv, material=mat_out)
    mesh_out = trimesh.Trimesh(vertices=all_v, faces=all_f, visual=vis_out, process=False)
    _pbr_meta = None
    try:
        from pbr_cartography import enhance_mesh_and_pbr_cartography, inject_gltf_optical_extensions
        _pbr_meta = enhance_mesh_and_pbr_cartography(
            mesh_out,
            prompt_context=os.environ.get("AURORA_PROMPT_CONTEXT", ""),
        )
    except Exception:
        pass
    Path(out_glb_path).parent.mkdir(parents=True, exist_ok=True)
    mesh_out.export(str(out_glb_path))
    if _pbr_meta:
        try:
            from pbr_cartography import inject_gltf_optical_extensions
            inject_gltf_optical_extensions(str(out_glb_path), _pbr_meta)
        except Exception:
            pass

    # Chaque personnage, à sa place, AVANT le nettoyage des fichiers individuels ci-dessous (le
    # premier essai du 15/11/2026 exportait après : FileNotFoundError, aucun personnage livré).
    import shutil as _shutil_p
    personnages = []
    for place in placements:
        base = Path(str(out_glb_path))
        cible = base.with_name(f"{base.stem}_personnage_{place['index'] + 1}.glb")
        try:
            exporter_personnage_place(place["source"], cible, place["scale"], place["translation"])
            ref_src = Path(str(char_infos[place["index"]].get("ref_path") or ""))
            ref_cible = None
            if ref_src.is_file():
                ref_cible = base.with_name(f"{base.stem}_personnage_{place['index'] + 1}_reference{ref_src.suffix}")
                _shutil_p.copy2(ref_src, ref_cible)
            personnages.append({"index": place["index"], "glb": str(cible),
                                "reference": str(ref_cible) if ref_cible else None,
                                "scale": place["scale"], "translation": place["translation"]})
        except Exception as exc:  # noqa: BLE001 — la scène fusionnée reste livrée, le manque est dit
            personnages.append({"index": place["index"], "glb": None, "erreur": repr(exc)[:200]})

    for info in char_infos:
        for _tmp_k in ("glb_path", "ref_path"):
            _tp = info.get(_tmp_k)
            if _tp:
                Path(_tp).unlink(missing_ok=True)
                if str(_tp).endswith(".glb"):
                    Path(str(_tp)[:-4] + ".ply").unlink(missing_ok=True)

    return {
        "ok": True,
        "faces": int(len(all_f)),
        "verts": int(len(all_v)),
        "characters": n,
        "quality": "1024_cascade_multi_entity",
        "personnages": personnages,
    }
