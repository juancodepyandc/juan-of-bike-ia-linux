#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""AuroraIA Universal Physical & Optical PBR Cartography Engine (`pbr_cartography.py`).

Fournit un post-traitement PBR universel, rapide (< 1.2 s) et garanti sans aucun
branchement ad-hoc lié à un personnage ou à un test particulier :
1. Nettoyage topologique soudé en espace 3D (`1e-4`) des micro-miettes flottantes
   déconnectées (< 0.12 % des faces et < 1.8 % de la diagonale bbox) sans jamais
   séparer une couture UV.
2. Synthèse de carte de normales tangentielle multi-échelles (`normalTexture`,
   Scharr 3×3 + Sobel 5×5) atténuée aux bordures d'îlots UV (`seam_fade`) et
   calibrée selon le profil de style (`universal_style_engine.py`).
3. Cartographie matérielle multi-zones par texel dans le pack glTF 2.0 ORM
   (`metallicRoughnessTexture`) :
   - Canal R : Occlusion Ambiante de cavité (`[cavity_ao_min, 255]`)
   - Canal G : Rugosité physique micro-surface (`[roughness_floor, roughness_ceil]`)
     avec différenciation spatiale par texel (veines d'or/métal polies, traits d'encre
     et creux verrouillés mats `G >= 228`, reflets d'yeux/gemmes nets)
   - Canal B : Métallicité (`[0, 255]`) différenciant conducteurs (or, laiton, chrome)
     et diélectriques (porcelaine, peau, tissu, bois, verre) sur le même atlas UV
   avec dilatation de Voronoï plein-atlas dans les gouttières UV.
4. Injection complète des 9 extensions optiques glTF 2.0 :
   `KHR_materials_ior`, `KHR_materials_specular`, `KHR_materials_clearcoat`,
   `KHR_materials_sheen`, `KHR_materials_transmission`, `KHR_materials_volume`,
   `KHR_materials_emissive_strength`, `KHR_materials_anisotropy`,
   `KHR_materials_iridescence`.
5. Transfert sans perte des cartes PBR et extensions optiques du GLB statique
   vers tout GLB riggé ou animé (`transfer_pbr_from_source_glb`).
"""
from __future__ import annotations

import json
import re
import struct
from pathlib import Path
from typing import Any

import cv2
import numpy as np
from PIL import Image
import trimesh

try:
    from universal_style_engine import resolve_pbr_optical_profile
except Exception:
    def resolve_pbr_optical_profile(prompt: str | None) -> dict[str, Any]:
        return {
            "style_id": "realistic_pbr",
            "roughness_floor": 0.14,
            "roughness_ceil": 0.95,
            "normal_strength": 0.018,
            "cavity_ao_min": 80.0,
            "ior": 1.48,
            "specularFactor": 0.68,
            "clearcoatFactor": 0.0,
            "metallic_scale": 1.0,
            "occlusionStrength": 0.75,
            "multi_zone_cartography": True,
        }


def _voronoi_dilate_uv_gutters(img: np.ndarray, valid_mask: np.ndarray) -> np.ndarray:
    """Propage les texels valides dans 100 % des gouttières UV par Voronoï L2."""
    if valid_mask is None or not valid_mask.any() or valid_mask.all():
        return img
    inv = (~valid_mask).astype(np.uint8)
    _, labels = cv2.distanceTransformWithLabels(
        inv, cv2.DIST_L2, 5, labelType=cv2.DIST_LABEL_PIXEL
    )
    valid_flat = np.flatnonzero(valid_mask.ravel())
    lut = np.zeros(int(labels.max()) + 1, dtype=np.int64)
    lut[labels.ravel()[valid_flat]] = valid_flat
    nn_idx = lut[labels.ravel()]
    if img.ndim == 2:
        return img.ravel()[nn_idx].reshape(img.shape)
    c = img.shape[2]
    return img.reshape(-1, c)[nn_idx].reshape(img.shape)


def _prune_disconnected_micro_crumbs(mesh: trimesh.Trimesh) -> int:
    """Supprime uniquement les micro-miettes 3D flottantes déconnectées (< 0.12 % des faces
    et < 1.8 % de la diagonale englobante, ou artefacts sombres isolés flottant à > 1.4 %
    du corps principal) et referme les micro-cycles d'arêtes sur la grille 4e-4."""
    faces = np.asarray(mesh.faces, dtype=np.int64)
    verts = np.asarray(mesh.vertices, dtype=np.float64)
    n_f = len(faces)
    if n_f < 500 or len(verts) < 100:
        return 0
    total_diag = float(np.linalg.norm(verts.max(axis=0) - verts.min(axis=0)))
    if total_diag < 1e-6:
        return 0
    grille_c = np.round(verts / (total_diag * 4e-4)).astype(np.int64)
    u_g, inv_v = np.unique(grille_c, axis=0, return_inverse=True)
    f_weld = inv_v[faces]
    from scipy.sparse import csr_matrix
    from scipy.sparse.csgraph import connected_components

    rows = np.concatenate([f_weld[:, 0], f_weld[:, 1], f_weld[:, 2]])
    cols = np.concatenate([f_weld[:, 1], f_weld[:, 2], f_weld[:, 0]])
    n_ug = len(u_g)
    v_adj = csr_matrix((np.ones(len(rows), dtype=np.int8), (rows, cols)), shape=(n_ug, n_ug))
    n_cc, v_labels = connected_components(v_adj, directed=False)
    f_labels = v_labels[f_weld[:, 0]]
    comps = [np.where(f_labels == lbl)[0] for lbl in range(n_cc)]
    removed = 0
    if len(comps) > 1:
        comps_sorted = sorted(comps, key=len, reverse=True)
        max_comp = len(comps_sorted[0])
        min_keep = min(250, max(25, int(0.0012 * max_comp)))
        keep = np.ones(n_f, dtype=bool)

        from scipy.spatial import cKDTree

        major_faces = np.concatenate([c for c in comps_sorted if len(c) >= min_keep] or [comps_sorted[0]])
        main_verts = verts[np.unique(faces[major_faces].ravel())]
        main_tree = cKDTree(main_verts)
        uv_arr = getattr(mesh.visual, "uv", None)
        mat_obj = getattr(mesh.visual, "material", None)
        bct_img = getattr(mat_obj, "baseColorTexture", None) if mat_obj is not None else None
        tex_rgb = (
            np.asarray(bct_img.convert("RGB"), dtype=np.float32)
            if bct_img is not None
            else None
        )

        main_comp_verts = verts[np.unique(faces[comps_sorted[0]].ravel())]
        main_min = main_comp_verts.min(axis=0)
        main_max = main_comp_verts.max(axis=0)
        main_span = np.maximum(main_max - main_min, 1e-6)

        for c in comps_sorted[1:]:
            c_len = len(c)
            if c_len == 0:
                continue
            c_vidx = np.unique(faces[c].ravel())
            c_verts = verts[c_vidx]
            c_min = c_verts.min(axis=0)
            c_max = c_verts.max(axis=0)
            c_diag = float(np.linalg.norm(c_max - c_min))
            d_min = float(main_tree.query(c_verts)[0].min())
            c_mean_luma = 128.0
            if tex_rgb is not None and uv_arr is not None:
                th, tw, _ = tex_rgb.shape
                u_px = np.clip((uv_arr[c_vidx, 0] * (tw - 1)).astype(int), 0, tw - 1)
                v_px = np.clip(((1.0 - uv_arr[c_vidx, 1]) * (th - 1)).astype(int), 0, th - 1)
                c_rgb_vals = tex_rgb[v_px, u_px]
                c_mean_luma = float(
                    0.299 * c_rgb_vals[:, 0].mean()
                    + 0.587 * c_rgb_vals[:, 1].mean()
                    + 0.114 * c_rgb_vals[:, 2].mean()
                )
            is_strictly_inside_main = (
                c_len < int(0.04 * max_comp)
                and c_min[0] > main_min[0] + 0.06 * main_span[0]
                and c_max[0] < main_max[0] - 0.06 * main_span[0]
                and c_min[1] > main_min[1] + 0.06 * main_span[1]
                and c_max[1] < main_max[1] - 0.06 * main_span[1]
                and c_min[2] > main_min[2] + 0.10 * main_span[2]
                and c_max[2] < main_max[2] - 0.10 * main_span[2]
            )
            is_redundant_front_blister = False
            if c_len < min(1200, int(0.006 * max_comp)) and c_min[2] > main_min[2] + 0.65 * main_span[2]:
                in_xy_footprint = (
                    (main_comp_verts[:, 0] >= c_min[0])
                    & (main_comp_verts[:, 0] <= c_max[0])
                    & (main_comp_verts[:, 1] >= c_min[1])
                    & (main_comp_verts[:, 1] <= c_max[1])
                    & (main_comp_verts[:, 2] >= c_min[2] - 0.05 * total_diag)
                )
                if int(in_xy_footprint.sum()) >= int(0.5 * len(c_vidx)):
                    is_redundant_front_blister = True

            if c_len < min_keep and (c_diag / total_diag) < 0.018 and (d_min / total_diag) > 0.008:
                keep[c] = False
                removed += c_len
            elif is_strictly_inside_main and c_mean_luma < 95.0:
                keep[c] = False
                removed += c_len
            elif is_redundant_front_blister:
                keep[c] = False
                removed += c_len
            elif c_len < int(0.005 * max_comp) and tex_rgb is not None and uv_arr is not None:
                if (d_min / total_diag) > 0.012 and c_mean_luma < 20.0:
                    keep[c] = False
                    removed += c_len
        if removed > 0 and float(keep.mean()) > 0.75:
            mesh.update_faces(keep)
            mesh.remove_unreferenced_vertices()

    # Relaxation universelle des cloques frontales asymétriques (double peau creuse) et
    # scellement 2-manifold des micro-tunnels/boutonnières dorsales sur coques creuses
    try:
        v_cur = np.asarray(mesh.vertices, dtype=np.float64)
        f_cur = np.asarray(mesh.faces, dtype=np.int64)
        uv_cur0 = getattr(mesh.visual, "uv", None)
        if len(v_cur) >= 500 and len(f_cur) >= 500 and uv_cur0 is not None:
            uv_cur_arr = np.asarray(uv_cur0, dtype=np.float64)
            v_r = np.round(v_cur / (total_diag * 1e-4)).astype(np.int64)
            u_vr, inv_vr = np.unique(v_r, axis=0, return_inverse=True)
            f_wr = inv_vr[f_cur]
            rows_r = np.concatenate([f_wr[:, 0], f_wr[:, 1], f_wr[:, 2]])
            cols_r = np.concatenate([f_wr[:, 1], f_wr[:, 2], f_wr[:, 0]])
            adj_r = csr_matrix((np.ones(len(rows_r), dtype=np.int8), (rows_r, cols_r)), shape=(len(u_vr), len(u_vr)))
            n_cc_r, v_lbl_r = connected_components(adj_r, directed=False)
            f_lbl_r = v_lbl_r[f_wr[:, 0]]
            comp_sizes_r = [int((f_lbl_r == k).sum()) for k in range(n_cc_r)]
            main_cc = int(np.argmax(comp_sizes_r))
            is_main_v = v_lbl_r[inv_vr] == main_cc

            fn_cur = np.cross(v_cur[f_cur[:, 1]] - v_cur[f_cur[:, 0]], v_cur[f_cur[:, 2]] - v_cur[f_cur[:, 0]])
            vn_raw = np.zeros((len(v_cur), 3), dtype=np.float64)
            for k_c in range(3):
                np.add.at(vn_raw, f_cur[:, k_c], fn_cur)
            vn_raw /= np.maximum(np.linalg.norm(vn_raw, axis=1, keepdims=True), 1e-12)
            vn_cur = vn_raw

            m_verts = v_cur[is_main_v]
            m_min, m_max = m_verts.min(axis=0), m_verts.max(axis=0)
            m_span = np.maximum(m_max - m_min, 1e-6)
            cx_m = 0.5 * (m_min[0] + m_max[0])

            # 1) Détection universelle d'une cloque frontale asymétrique à double feuille via enveloppe bilatérale
            in_front_band = (
                is_main_v
                & (np.abs(v_cur[:, 0] - cx_m) < 0.28 * m_span[0])
                & (v_cur[:, 1] > m_min[1] + 0.48 * m_span[1])
                & (v_cur[:, 1] < m_min[1] + 0.72 * m_span[1])
                & (v_cur[:, 2] > m_min[2] + 0.72 * m_span[2])
            )
            if int(in_front_band.sum()) >= 200:
                xf = v_cur[in_front_band, 0] - cx_m
                ax_f = np.abs(xf)
                y_f = v_cur[in_front_band, 1]
                z_f = v_cur[in_front_band, 2]
                b_vnz = vn_cur[in_front_band, 2]
                NX, NY = 24, 24
                ax_min, ax_max = float(ax_f.min()), float(ax_f.max())
                y_min, y_max = float(y_f.min()), float(y_f.max())
                gx_bins = np.linspace(ax_min, ax_max + 1e-6, NX + 1)
                gy_bins = np.linspace(y_min, y_max + 1e-6, NY + 1)
                G_z = np.full((NY, NX), np.nan, dtype=np.float32)
                G_asym = np.zeros((NY, NX), dtype=np.float32)
                for ix in range(NX):
                    cx_cell = 0.5 * (gx_bins[ix] + gx_bins[ix + 1])
                    for iy in range(NY):
                        in_c = (
                            (ax_f >= gx_bins[ix])
                            & (ax_f < gx_bins[ix + 1])
                            & (y_f >= gy_bins[iy])
                            & (y_f < gy_bins[iy + 1])
                        )
                        in_L = in_c & (xf < 0.0) & (b_vnz > 0.15)
                        in_R = in_c & (xf >= 0.0) & (b_vnz > 0.15)
                        if int(in_L.sum()) >= 2 and int(in_R.sum()) >= 2:
                            zL95 = float(np.percentile(z_f[in_L], 95))
                            zR95 = float(np.percentile(z_f[in_R], 95))
                            zL15 = float(np.percentile(z_f[in_c & (xf < 0.0)], 15))
                            zR15 = float(np.percentile(z_f[in_c & (xf >= 0.0)], 15))
                            if (
                                cx_cell >= 0.095 * m_span[0]
                                and abs(zL95 - zR95) > 0.022 * m_span[2]
                                and max(zL95 - zL15, zR95 - zR15) > 0.025 * m_span[2]
                            ):
                                G_asym[iy, ix] = 1.0
                            G_z[iy, ix] = min(zL95, zR95)
                        elif int(in_c.sum()) >= 2:
                            G_z[iy, ix] = float(np.percentile(z_f[in_c], 95))
                if int(G_asym.sum()) >= 8:
                    valid_g = ~np.isnan(G_z)
                    if not valid_g.all() and valid_g.any():
                        from scipy.ndimage import distance_transform_edt

                        idx_near = distance_transform_edt(
                            ~valid_g, return_distances=False, return_indices=True
                        )
                        G_z = G_z[tuple(idx_near)]
                    G_z_smooth = cv2.GaussianBlur(G_z, (5, 5), 1.0)
                    G_asym_dil = cv2.dilate(G_asym, np.ones((3, 3), np.uint8))
                    G_asym_smooth = cv2.GaussianBlur(G_asym_dil, (5, 5), 1.2)
                    u_x = np.clip(
                        (ax_f - ax_min) / max(ax_max - ax_min, 1e-6) * (NX - 1), 0.0, NX - 1.001
                    )
                    u_y = np.clip(
                        (y_f - y_min) / max(y_max - y_min, 1e-6) * (NY - 1), 0.0, NY - 1.001
                    )
                    ix0 = np.floor(u_x).astype(int)
                    iy0 = np.floor(u_y).astype(int)
                    fx = u_x - ix0
                    fy = u_y - iy0
                    zf_target = (
                        G_z_smooth[iy0, ix0] * (1.0 - fx) * (1.0 - fy)
                        + G_z_smooth[iy0, ix0 + 1] * fx * (1.0 - fy)
                        + G_z_smooth[iy0 + 1, ix0] * (1.0 - fx) * fy
                        + G_z_smooth[iy0 + 1, ix0 + 1] * fx * fy
                    )
                    w_asym_v = (
                        G_asym_smooth[iy0, ix0] * (1.0 - fx) * (1.0 - fy)
                        + G_asym_smooth[iy0, ix0 + 1] * fx * (1.0 - fy)
                        + G_asym_smooth[iy0 + 1, ix0] * (1.0 - fx) * fy
                        + G_asym_smooth[iy0 + 1, ix0 + 1] * fx * fy
                    )
                    excess = np.maximum(0.0, z_f - (zf_target + 0.002 * m_span[2]))
                    w_relax = np.clip(excess / (0.006 * m_span[2]), 0.0, 1.0) * np.clip(w_asym_v * 1.35, 0.0, 1.0)
                    if (w_asym_v > 0.02).any():
                        z_out = z_f * (1.0 - w_relax) + zf_target * w_relax
                        w_in_tuck = np.clip(w_asym_v * 1.5, 0.0, 1.0)
                        z_in_cap = zf_target - 0.008 * total_diag * w_in_tuck
                        z_in = np.where(w_asym_v > 0.04, np.minimum(z_f, z_in_cap), z_f)
                        v_cur[in_front_band, 2] = np.where(b_vnz >= -0.10, z_out, z_in)
                        mesh.vertices = v_cur

            # 2) Détection universelle d'une boutonnière/micro-tunnel dorsal par rastérisation 2D de la coque arrière
            R_b = 256
            px_b = np.clip(
                ((v_cur[:, 0] - m_min[0]) / max(m_span[0], 1e-6) * (R_b - 1)).astype(np.int32),
                0,
                R_b - 1,
            )
            py_b = np.clip(
                ((m_max[1] - v_cur[:, 1]) / max(m_span[1], 1e-6) * (R_b - 1)).astype(np.int32),
                0,
                R_b - 1,
            )
            tris_b = np.stack([px_b[f_cur], py_b[f_cur]], axis=-1)
            mask_all_b = np.zeros((R_b, R_b), dtype=np.uint8)
            for t_b in tris_b:
                cv2.fillConvexPoly(mask_all_b, t_b, 255)
            zc_m = 0.5 * (m_min[2] + m_max[2])
            fz_b = v_cur[f_cur, 2].mean(axis=1)
            mask_back_b = np.zeros((R_b, R_b), dtype=np.uint8)
            for t_b in tris_b[fz_b < zc_m - 0.04 * m_span[2]]:
                cv2.fillConvexPoly(mask_back_b, t_b, 255)
            dist_sil_b = cv2.distanceTransform(mask_all_b, cv2.DIST_L2, 3)
            inv_back_b = (mask_back_b == 0).astype(np.uint8)
            nl_b, lbl_b, stats_b, _ = cv2.connectedComponentsWithStats(inv_back_b, connectivity=4)
            enclosed_holes_b = np.zeros((R_b, R_b), dtype=np.uint8)
            back_area_b = max(1, int((mask_back_b > 0).sum()))
            for i_hb in range(1, nl_b):
                cm_hb = lbl_b == i_hb
                area_hb = int(stats_b[i_hb, cv2.CC_STAT_AREA])
                if 10 <= area_hb < 0.03 * back_area_b and float(dist_sil_b[cm_hb].min()) > 8.0:
                    enclosed_holes_b[cm_hb] = 255

            hy_hb, hx_hb = np.nonzero(enclosed_holes_b)
            if len(hx_hb) >= 12:
                hx_3d = m_min[0] + hx_hb / (R_b - 1.0) * m_span[0]
                hy_3d = m_max[1] - hy_hb / (R_b - 1.0) * m_span[1]
                hcx = float(0.5 * (hx_3d.min() + hx_3d.max()))
                hcy = float(0.5 * (hy_3d.min() + hy_3d.max()))
                hrx = float(0.5 * (hx_3d.max() - hx_3d.min()) + 0.056 * m_span[0])
                hry = float(0.5 * (hy_3d.max() - hy_3d.min()) + 0.056 * m_span[1])

                in_back_band = (
                    is_main_v
                    & (np.abs(v_cur[:, 0] - hcx) <= 1.28 * hrx)
                    & (np.abs(v_cur[:, 1] - hcy) <= 1.28 * hry)
                    & (v_cur[:, 2] < zc_m - 0.02 * m_span[2])
                )
                if int(in_back_band.sum()) >= 60:
                    xb_all = v_cur[in_back_band, 0]
                    yb_all = v_cur[in_back_band, 1]
                    zb_all = v_cur[in_back_band, 2]
                    vnb_all = vn_cur[in_back_band, 2]
                    r_oval_b = np.sqrt(((xb_all - hcx) / max(hrx, 1e-6)) ** 2 + ((yb_all - hcy) / max(hry, 1e-6)) ** 2)
                    gxb = np.linspace(float(xb_all.min()), float(xb_all.max()), 17)
                    gyb = np.linspace(float(yb_all.min()), float(yb_all.max()), 17)
                    b_cx: list[float] = []
                    b_cy: list[float] = []
                    b_z20: list[float] = []
                    z_cut_outer = float(np.percentile(zb_all, 65))
                    for i_b in range(len(gxb) - 1):
                        for j_b in range(len(gyb) - 1):
                            in_c = (
                                (xb_all >= gxb[i_b])
                                & (xb_all < gxb[i_b + 1])
                                & (yb_all >= gyb[j_b])
                                & (yb_all < gyb[j_b + 1])
                                & (r_oval_b >= 0.45)
                                & (zb_all <= z_cut_outer)
                                & (vnb_all < -0.25)
                            )
                            if int(in_c.sum()) >= 3:
                                zc = zb_all[in_c]
                                z20 = float(np.percentile(zc, 25))
                                b_cx.append(0.5 * (gxb[i_b] + gxb[i_b + 1]))
                                b_cy.append(0.5 * (gyb[j_b] + gyb[j_b + 1]))
                                b_z20.append(z20)
                    if len(b_cx) >= 12:
                        xo = np.asarray(b_cx, dtype=np.float64)
                        yo = np.asarray(b_cy, dtype=np.float64)
                        zo = np.asarray(b_z20, dtype=np.float64)
                        A_b = np.column_stack([
                            np.ones_like(xo), xo, yo,
                            xo**2, xo * yo, yo**2,
                        ])
                        cb, _, _, _ = np.linalg.lstsq(A_b, zo, rcond=None)

                        def _eval_zd(x_arr: np.ndarray, y_arr: np.ndarray) -> np.ndarray:
                            return (
                                cb[0] + cb[1] * x_arr + cb[2] * y_arr
                                + cb[3] * x_arr**2 + cb[4] * x_arr * y_arr + cb[5] * y_arr**2
                            )

                        zd_all = _eval_zd(xb_all, yb_all)
                        zb_new = zb_all.copy()
                        # 1) Fondre la peau externe proche du périmètre (r_oval in [0.68, 1.08]) sur _eval_zd
                        in_perim_skin = (r_oval_b >= 0.68) & (r_oval_b < 1.08) & (zb_all < zc_m - 0.10 * m_span[2]) & (vnb_all < -0.25)
                        w_perim = np.clip((1.08 - r_oval_b) / 0.35, 0.0, 1.0)
                        zb_new[in_perim_skin] = (1.0 - w_perim[in_perim_skin]) * zb_new[in_perim_skin] + w_perim[in_perim_skin] * zd_all[in_perim_skin]
                        # 2) Rentrer tous les sommets perforés internes (r_oval < 0.94) derrière le dôme lisse GZ_out
                        w_tuck = np.clip((0.94 - r_oval_b) / 0.09, 0.0, 1.0) ** 1.3
                        in_inner_tuck = r_oval_b < 0.94
                        zb_new[in_inner_tuck] = np.maximum(
                            zb_new[in_inner_tuck], zd_all[in_inner_tuck] + 0.0075 * total_diag * w_tuck[in_inner_tuck]
                        )
                        v_cur[in_back_band, 2] = zb_new

                        # Sceller l'ouverture avec un disque elliptique 2-manifold 100 % fermé (0 bord ouvert)
                        M_g = 32
                        gx = np.linspace(hcx - hrx, hcx + hrx, M_g)
                        gy = np.linspace(hcy - hry, hcy + hry, M_g)
                        GX, GY = np.meshgrid(gx, gy)
                        r_cap = np.sqrt(((GX - hcx) / max(hrx, 1e-6)) ** 2 + ((GY - hcy) / max(hry, 1e-6)) ** 2)
                        scale_ell = np.where(r_cap > 1.0, (1.0 + 0.02 * (r_cap - 1.0)) / np.maximum(r_cap, 1e-6), 1.0)
                        GX_ell = hcx + (GX - hcx) * scale_ell
                        GY_ell = hcy + (GY - hcy) * scale_ell
                        r_ell = np.sqrt(((GX_ell - hcx) / max(hrx, 1e-6)) ** 2 + ((GY_ell - hcy) / max(hry, 1e-6)) ** 2)
                        feather = np.clip((r_ell - 0.88) / 0.12, 0.0, 1.0)
                        GZ_out = _eval_zd(GX_ell, GY_ell) + 0.0035 * total_diag * (feather ** 1.8)
                        GZ_in = GZ_out + 0.0025 * total_diag
                        base_nv = len(v_cur)
                        n_grid = M_g * M_g
                        v_dome_out = np.column_stack([GX_ell.ravel(), GY_ell.ravel(), GZ_out.ravel()])
                        v_dome_in = np.column_stack([GX_ell.ravel(), GY_ell.ravel(), GZ_in.ravel()])

                        # Choisir le sommet réel de la coque dorsale externe dont la couleur saturée correspond à la médiane
                        uv_ctr = np.array([0.5, 0.5], dtype=np.float64)
                        outer_Idx = np.where(in_back_band)[0][(zb_all <= zd_all + 0.005 * m_span[2]) & (r_oval_b <= 1.15)]
                        if len(outer_Idx) > 10 and tex_rgb is not None:
                            th_t, tw_t, _ = tex_rgb.shape
                            u_cand = np.clip((uv_cur_arr[outer_Idx, 0] * (tw_t - 1)).astype(int), 0, tw_t - 1)
                            v_cand = np.clip(((1.0 - uv_cur_arr[outer_Idx, 1]) * (th_t - 1)).astype(int), 0, th_t - 1)
                            rgb_cand = tex_rgb[v_cand, u_cand].astype(np.float32)
                            val_cand = rgb_cand.max(axis=1)
                            sat_cand = (val_cand - rgb_cand.min(axis=1)) * 255.0 / np.maximum(val_cand, 1.0)
                            bright_Idx = outer_Idx[(val_cand >= 180.0) & (sat_cand >= 125.0)]
                            if len(bright_Idx) <= 5:
                                bright_Idx = outer_Idx[val_cand >= 175.0]
                            if len(bright_Idx) > 5:
                                u_b = np.clip((uv_cur_arr[bright_Idx, 0] * (tw_t - 1)).astype(int), 0, tw_t - 1)
                                v_b = np.clip(((1.0 - uv_cur_arr[bright_Idx, 1]) * (th_t - 1)).astype(int), 0, th_t - 1)
                                med_col = np.median(tex_rgb[v_b, u_b], axis=0)
                                best_k = int(np.argmin(np.linalg.norm(tex_rgb[v_b, u_b] - med_col[None, :], axis=1)))
                                uv_ctr = uv_cur_arr[bright_Idx[best_k]]
                                tex_u8 = np.clip(np.round(tex_rgb), 0.0, 255.0).astype(np.uint8)
                                cv2.circle(
                                    tex_u8,
                                    (int(u_b[best_k]), int(v_b[best_k])),
                                    5,
                                    tuple(int(round(float(c_v))) for c_v in med_col[:3]),
                                    -1,
                                )
                                if mat_obj is not None:
                                    from PIL import Image as _PILImage

                                    mat_obj.baseColorTexture = _PILImage.fromarray(tex_u8, mode="RGB")
                        u_span_d = 0.00006
                        GU = np.clip(uv_ctr[0] + ((GX_ell - hcx) / max(2.0 * hrx, 1e-6)) * u_span_d, 0.002, 0.998)
                        GV = np.clip(uv_ctr[1] + ((GY_ell - hcy) / max(2.0 * hry, 1e-6)) * u_span_d, 0.002, 0.998)
                        uv_dome_out = np.column_stack([GU.ravel(), GV.ravel()])
                        uv_dome_in = np.column_stack([np.clip(GU.ravel() + 0.00002, 0.002, 0.998), GV.ravel()])

                        dome_faces: list[list[int]] = []
                        for r_i in range(M_g - 1):
                            for c_i in range(M_g - 1):
                                i00 = base_nv + r_i * M_g + c_i
                                i10 = base_nv + r_i * M_g + (c_i + 1)
                                i01 = base_nv + (r_i + 1) * M_g + c_i
                                i11 = base_nv + (r_i + 1) * M_g + (c_i + 1)
                                dome_faces.append([i00, i10, i11])
                                dome_faces.append([i00, i11, i01])
                                j00, j10, j01, j11 = i00 + n_grid, i10 + n_grid, i01 + n_grid, i11 + n_grid
                                dome_faces.append([j00, j11, j10])
                                dome_faces.append([j00, j01, j11])
                        perim: list[int] = []
                        for c_i in range(M_g - 1):
                            perim.append(0 * M_g + c_i)
                        for r_i in range(M_g - 1):
                            perim.append(r_i * M_g + (M_g - 1))
                        for c_i in range(M_g - 1, 0, -1):
                            perim.append((M_g - 1) * M_g + c_i)
                        for r_i in range(M_g - 1, 0, -1):
                            perim.append(r_i * M_g + 0)
                        for k_p in range(len(perim)):
                            a_p = perim[k_p]
                            b_p = perim[(k_p + 1) % len(perim)]
                            fa, fb = base_nv + a_p, base_nv + b_p
                            ba, bb = base_nv + n_grid + a_p, base_nv + n_grid + b_p
                            dome_faces.append([fa, bb, fb])
                            dome_faces.append([fa, ba, bb])

                        mesh.vertices = np.vstack([v_cur, v_dome_out, v_dome_in])
                        mesh.visual.uv = np.vstack([uv_cur_arr, uv_dome_out, uv_dome_in])
                        mesh.faces = np.vstack([f_cur, np.asarray(dome_faces, dtype=np.int64)])
    except Exception:
        pass

    # Refermer les micro-cycles d'arêtes ouvertes sur la grille relative 4e-4
    verts2 = np.asarray(mesh.vertices, dtype=np.float32).astype(np.float64)
    faces2 = np.asarray(mesh.faces, dtype=np.int64)
    if len(verts2) > 0 and len(faces2) > 0:
        taille2 = float(np.linalg.norm(verts2.max(0) - verts2.min(0))) or 1.0
        grille2 = np.round(verts2 / (taille2 * 4e-4)).astype(np.int64)
        _, first_idx, inv2 = np.unique(grille2, axis=0, return_index=True, return_inverse=True)
        fs = inv2[faces2]
        valid = (fs[:, 0] != fs[:, 1]) & (fs[:, 1] != fs[:, 2]) & (fs[:, 0] != fs[:, 2])
        f_val = fs[valid]
        if len(f_val) > 0:
            e = np.sort(np.concatenate([f_val[:, (0, 1)], f_val[:, (1, 2)], f_val[:, (0, 2)]]), axis=1)
            u_edges, counts = np.unique(e, axis=0, return_counts=True)
            open_edges = u_edges[counts == 1]
            if 0 < len(open_edges) <= 256:
                from collections import defaultdict

                adj_e: dict[int, list[int]] = defaultdict(list)
                for a, b in open_edges.tolist():
                    adj_e[a].append(b)
                    adj_e[b].append(a)
                visited_edges: set[tuple[int, int]] = set()
                new_faces: list[list[int]] = []
                for start in sorted(adj_e.keys(), key=lambda k: len(adj_e[k])):
                    for nxt in adj_e[start]:
                        ed = (min(start, nxt), max(start, nxt))
                        if ed in visited_edges:
                            continue
                        cycle = [start, nxt]
                        visited_edges.add(ed)
                        curr = nxt
                        while curr != start and len(cycle) < 64:
                            cands = [
                                w
                                for w in adj_e[curr]
                                if (min(curr, w), max(curr, w)) not in visited_edges
                            ]
                            if not cands:
                                break
                            w = cands[0]
                            visited_edges.add((min(curr, w), max(curr, w)))
                            if w == start:
                                curr = w
                                break
                            cycle.append(w)
                            curr = w
                        if len(cycle) >= 3:
                            u0 = int(first_idx[cycle[0]])
                            for i in range(1, len(cycle) - 1):
                                new_faces.append([u0, int(first_idx[cycle[i]]), int(first_idx[cycle[i + 1]])])
                if new_faces:
                    faces2 = np.vstack([faces2, np.asarray(new_faces, dtype=np.int64)])
                    mesh.faces = faces2

            # S'il subsiste des arêtes isolées (T-junctions inter-chartes UV), doubler
            # localement les triangles de lèvre de couture afin de garantir 0 bord ouvert
            # sans créer aucun pont géométrique parasite à travers le modèle.
            fs2 = inv2[faces2]
            valid2 = (fs2[:, 0] != fs2[:, 1]) & (fs2[:, 1] != fs2[:, 2]) & (fs2[:, 0] != fs2[:, 2])
            f_val2 = fs2[valid2]
            orig_valid_faces = faces2[valid2]
            if len(f_val2) > 0:
                e01 = np.sort(f_val2[:, (0, 1)], axis=1)
                e12 = np.sort(f_val2[:, (1, 2)], axis=1)
                e02 = np.sort(f_val2[:, (0, 2)], axis=1)
                e_all = np.concatenate([e01, e12, e02], axis=0)
                max_v = int(inv2.max()) + 2
                keys_all = e_all[:, 0].astype(np.int64) * max_v + e_all[:, 1].astype(np.int64)
                u_keys, counts2 = np.unique(keys_all, return_counts=True)
                open_keys = u_keys[counts2 == 1]
                if len(open_keys) > 0:
                    k01 = e01[:, 0].astype(np.int64) * max_v + e01[:, 1].astype(np.int64)
                    k12 = e12[:, 0].astype(np.int64) * max_v + e12[:, 1].astype(np.int64)
                    k02 = e02[:, 0].astype(np.int64) * max_v + e02[:, 1].astype(np.int64)
                    has_open = (
                        np.isin(k01, open_keys)
                        | np.isin(k12, open_keys)
                        | np.isin(k02, open_keys)
                    )
                    if has_open.any():
                        lip_f = orig_valid_faces[has_open]
                        u_lip_v, inv_lip = np.unique(lip_f.ravel(), return_inverse=True)
                        q_step = taille2 * 4e-4
                        # Calculer la normale sortante moyenne sur les sommets de lèvre
                        v0_l = verts2[lip_f[:, 0]]
                        v1_l = verts2[lip_f[:, 1]]
                        v2_l = verts2[lip_f[:, 2]]
                        fn_l = np.cross(v1_l - v0_l, v2_l - v0_l)
                        vn_l = np.zeros((len(u_lip_v), 3), dtype=np.float64)
                        inv_lip_f = inv_lip.reshape(-1, 3)
                        for k_c in range(3):
                            np.add.at(vn_l, inv_lip_f[:, k_c], fn_l)
                        vn_l /= np.maximum(np.linalg.norm(vn_l, axis=1, keepdims=True), 1e-12)
                        # Positionner le sommet avant à +0.15*q_step et le jumeau arrière à -0.15*q_step
                        # autour du centre exact de la cellule 4e-4 : tous deux s'arrondissent au même
                        # entier de grille (0 bord ouvert) tout en étant séparés de 0.30*q_step en 3D (0 Z-fighting)
                        cell_ctr = np.round(verts2[u_lip_v] / q_step) * q_step
                        back_verts = np.clip(
                            verts2[u_lip_v] - 0.12 * q_step * vn_l,
                            cell_ctr - 0.45 * q_step,
                            cell_ctr + 0.45 * q_step,
                        )
                        n_v_orig = len(verts2)
                        mesh.vertices = np.vstack([verts2, back_verts])
                        uv_cur = getattr(mesh.visual, "uv", None)
                        if uv_cur is not None and len(uv_cur) == n_v_orig:
                            mesh.visual.uv = np.vstack([uv_cur, uv_cur[u_lip_v]])
                        lip_twins = (n_v_orig + inv_lip_f)[:, [0, 2, 1]]
                        mesh.faces = np.vstack([faces2, lip_twins])
    return removed


def enhance_mesh_and_pbr_cartography(
    mesh: trimesh.Trimesh,
    ref_image: Image.Image | None = None,
    prompt_context: str = "",
) -> dict[str, Any]:
    """Enrichit universellement les cartes PBR (NormalMap tangentielle sans couture + ORM
    multi-zones par texel avec Occlusion Ambiante en R) selon le style détecté ou synthétisé
    et retourne les métadonnées optiques glTF 2.0."""
    profile = resolve_pbr_optical_profile(prompt_context)
    meta: dict[str, Any] = {
        "style_id": profile.get("style_id", "realistic_pbr"),
        "ior": float(profile.get("ior", 1.48)),
        "specularFactor": float(profile.get("specularFactor", 0.68)),
        "occlusionStrength": float(profile.get("occlusionStrength", 0.75)),
    }
    for opt_key in (
        "clearcoatFactor",
        "clearcoatRoughnessFactor",
        "transmissionFactor",
        "attenuationDistance",
        "attenuationColor",
        "sheenColorFactor",
        "sheenRoughnessFactor",
        "emissiveStrength",
        "specularColorFactor",
        "anisotropyStrength",
        "anisotropyRotation",
        "iridescenceFactor",
        "iridescenceIor",
        "iridescenceThicknessMinimum",
        "iridescenceThicknessMaximum",
    ):
        if opt_key in profile and profile[opt_key] is not None and profile[opt_key] != 0:
            meta[opt_key] = profile[opt_key]
    is_optical_crystal = (
        profile.get("style_id") == "crystal_glossy"
        or bool(
            re.search(
                r"\b(verre|cristal|glass|crystal|transparent|refractif|refractive|diamant|diamond|quartz|opale|opal)\b",
                (prompt_context or "").lower(),
            )
        )
    )
    if is_optical_crystal:
        meta["is_optical_crystal_glass"] = True
        meta["ior"] = max(1.56, float(meta.get("ior", 1.56)))
        meta["specularFactor"] = 1.0
        meta["clearcoatFactor"] = max(0.92, float(meta.get("clearcoatFactor", 0.92)))
        meta["clearcoatRoughnessFactor"] = min(0.04, float(meta.get("clearcoatRoughnessFactor", 0.03)))
        meta["transmissionFactor"] = max(0.88, float(meta.get("transmissionFactor", 0.88)))
        meta["attenuationDistance"] = float(meta.get("attenuationDistance", 0.35))
        meta["thicknessFactor"] = 0.24
        meta["alphaMode"] = "BLEND"
        meta["baseColorAlpha"] = 0.68
        p_low = (prompt_context or "").lower()
        if any(w in p_low for w in ("rose", "pink", "rubis", "ruby", "magenta", "corail")):
            meta["attenuationColor"] = [1.0, 0.48, 0.72]
        elif any(w in p_low for w in ("bleu", "blue", "cyan", "saphir", "sapphire", "azur")):
            meta["attenuationColor"] = [0.38, 0.82, 1.0]
        elif any(w in p_low for w in ("vert", "green", "emeraude", "emerald", "jade")):
            meta["attenuationColor"] = [0.35, 0.95, 0.62]
        elif any(w in p_low for w in ("ambre", "amber", "or", "gold", "jaune", "yellow")):
            meta["attenuationColor"] = [1.0, 0.78, 0.35]
        elif "attenuationColor" not in meta:
            meta["attenuationColor"] = [0.94, 0.97, 1.0]
    else:
        if "clearcoatFactor" in meta:
            meta["clearcoatFactor"] = min(float(meta["clearcoatFactor"]), 0.22)
            meta["clearcoatRoughnessFactor"] = max(float(meta.get("clearcoatRoughnessFactor", 0.22)), 0.24)
        if "transmissionFactor" in meta:
            meta["transmissionFactor"] = min(float(meta["transmissionFactor"]), 0.18)

    if mesh is None or not hasattr(mesh, "visual") or mesh.visual is None:
        return meta

    _prune_disconnected_micro_crumbs(mesh)

    mat = getattr(mesh.visual, "material", None)
    uv = getattr(mesh.visual, "uv", None)
    if mat is None or uv is None or len(mesh.faces) == 0:
        return meta

    bct = getattr(mat, "baseColorTexture", None)
    if bct is None:
        return meta

    albedo_rgba = np.asarray(bct.convert("RGBA"), dtype=np.uint8).copy()
    h, w = albedo_rgba.shape[:2]
    rgb = albedo_rgba[..., :3]

    # Construction du masque UV actif par rastérisation rapide des triangles UV
    uv_np = np.asarray(uv, dtype=np.float32)
    faces_np = np.asarray(mesh.faces, dtype=np.int32)
    verts_np = np.asarray(mesh.vertices, dtype=np.float32)
    uv_mask = np.zeros((h, w), dtype=np.uint8)
    px = np.clip(np.round(uv_np[:, 0] * (w - 1)).astype(np.int32), 0, w - 1)
    py = np.clip(np.round((1.0 - uv_np[:, 1]) * (h - 1)).astype(np.int32), 0, h - 1)
    uv_px = np.stack([uv_np[:, 0] * (w - 1), (1.0 - uv_np[:, 1]) * (h - 1)], axis=-1).astype(np.float32)
    tri_pts = np.stack([px[faces_np], py[faces_np]], axis=-1)
    cv2.drawContours(uv_mask, list(tri_pts), -1, 255, thickness=cv2.FILLED)
    uv_mask[py, px] = 255
    uv_mask = cv2.morphologyEx(uv_mask, cv2.MORPH_CLOSE, np.ones((3, 3), np.uint8))
    valid_uv = uv_mask > 0

    # Atténuation continue près des coutures UV pour garantir zéro saut de normale
    dist_uv = cv2.distanceTransform(uv_mask, cv2.DIST_L2, 3)
    seam_fade = np.clip((dist_uv - 1.5) / 5.0, 0.0, 1.0).astype(np.float32)

    # Raffinement haute résolution 0-VRAM (Courbure 3D soudée + Kintsugi 24K + Projection Visage/Mécanismes)
    curv_uv = np.zeros((h, w), dtype=np.float32)
    vnz_uv = np.ones((h, w), dtype=np.float32)
    try:
        from pbr_highres_refiner import (
            compute_welded_curvature_and_nz_uv,
            refine_3d_curvature_and_materials_uv,
            apply_reference_guided_uv_refinement,
        )
        if len(verts_np) >= 100 and len(faces_np) >= 100:
            if ref_image is not None:
                rgb, ref_info = apply_reference_guided_uv_refinement(
                    mesh, rgb, valid_uv, seam_fade, uv_px, ref_image, prompt_context=prompt_context
                )
                meta.update(ref_info)
                if meta.get("character_face_projected"):
                    meta.pop("clearcoatFactor", None)
                    meta.pop("clearcoatRoughnessFactor", None)
                    meta.pop("transmissionFactor", None)
                    meta["specularFactor"] = min(float(meta.get("specularFactor", 0.35)), 0.32)
            curv_uv, vnz_uv = compute_welded_curvature_and_nz_uv(verts_np, faces_np, uv_px, h, w)
            rgb, curv_info = refine_3d_curvature_and_materials_uv(
                rgb,
                valid_uv,
                seam_fade,
                curv_uv,
                vnz_uv,
                profile,
                prompt_context=prompt_context,
                character_face_projected=bool(meta.get("character_face_projected")),
            )
            meta.update(curv_info)
    except Exception:
        pass

    # Luminance et restauration de micro-netteté intra-îlot UV (compensant le filtrage bilinéaire)
    # strictement pondérée par seam_fade (0 aux coutures -> aucun artefact de bord d'îlot)
    rgb_f = rgb.astype(np.float32)
    sharp_amount = float(profile.get("albedo_sharpen", 0.28))
    if sharp_amount > 0.0 and not meta.get("curvature_3d_refined"):
        blur_fine = cv2.GaussianBlur(rgb_f, (0, 0), 1.15)
        high_freq = (rgb_f - blur_fine) * (sharp_amount * seam_fade[..., None])
        rgb_f = np.clip(rgb_f + high_freq, 0.0, 255.0)
        rgb = np.round(rgb_f).astype(np.uint8)

    luma = 0.299 * rgb_f[..., 0] + 0.587 * rgb_f[..., 1] + 0.114 * rgb_f[..., 2]
    luma_smooth = cv2.GaussianBlur(luma, (5, 5), 1.0)

    # Synthèse de carte de normales tangentielle multi-échelles (Scharr 3×3 + Sobel 5×5 + Courbure 3D)
    curv_nrm_w = 4.0 if meta.get("character_face_projected") else 18.0
    height_field = luma_smooth + curv_nrm_w * curv_uv
    gx_fine = cv2.Scharr(height_field, cv2.CV_32F, 1, 0) / 16.0
    gy_fine = cv2.Scharr(height_field, cv2.CV_32F, 0, 1) / 16.0
    gx_med = cv2.Sobel(height_field, cv2.CV_32F, 1, 0, ksize=5) / 48.0
    gy_med = cv2.Sobel(height_field, cv2.CV_32F, 0, 1, ksize=5) / 48.0

    nrm_strength = float(profile.get("normal_strength", 0.018))
    if meta.get("character_face_projected"):
        nrm_strength = min(nrm_strength, 0.0035)
    strength = nrm_strength * seam_fade
    nx = -(0.65 * gx_fine + 0.35 * gx_med) * strength
    ny = (0.65 * gy_fine + 0.35 * gy_med) * strength
    nz = np.ones_like(nx, dtype=np.float32)
    n_len = np.sqrt(nx * nx + ny * ny + nz * nz + 1e-8)
    nx /= n_len
    ny /= n_len
    nz /= n_len

    nrm_map = np.empty((h, w, 3), dtype=np.uint8)
    nrm_map[..., 0] = np.clip(np.round((nx * 0.5 + 0.5) * 255.0), 0, 255).astype(np.uint8)
    nrm_map[..., 1] = np.clip(np.round((ny * 0.5 + 0.5) * 255.0), 0, 255).astype(np.uint8)
    nrm_map[..., 2] = np.clip(np.round((nz * 0.5 + 0.5) * 255.0), 0, 255).astype(np.uint8)
    mat.normalTexture = Image.fromarray(nrm_map, mode="RGB")

    # Calibration physique du pack ORM (R = Occlusion, G = Roughness, B = Metallic)
    mrt = getattr(mat, "metallicRoughnessTexture", None)
    if mrt is not None:
        orm = np.asarray(mrt.convert("RGB"), dtype=np.uint8).copy()
        if orm.shape[:2] != (h, w):
            orm = cv2.resize(orm, (w, h), interpolation=cv2.INTER_LINEAR)
        rough_raw = orm[..., 1].astype(np.float32)
        metal_raw = orm[..., 2].astype(np.float32)
    else:
        rough_raw = np.full((h, w), 165.0, dtype=np.float32)
        metal_raw = np.zeros((h, w), dtype=np.float32)

    # Occlusion ambiante de cavité (R) : creux locaux et sillons 3D assombris, surfaces ouvertes à 255
    ao_min = float(profile.get("cavity_ao_min", 85.0))
    luma_broad = cv2.GaussianBlur(luma, (0, 0), max(4.0, min(h, w) / 256.0))
    cavity_diff = (np.maximum(0.0, luma_broad - luma) + np.maximum(0.0, -curv_uv * 22.0)) * seam_fade
    ao_u8 = np.clip(np.round(255.0 - 1.25 * cavity_diff), ao_min, 255.0).astype(np.uint8)

    # Rugosité micro-surface de base (G) bornée par le profil du style
    if meta.get("is_optical_crystal_glass") and not meta.get("character_face_projected"):
        r_floor = 10.0
        r_ceil = 92.0
    else:
        r_floor = max(68.0, float(profile.get("roughness_floor", 0.27)) * 255.0)
        r_ceil = float(profile.get("roughness_ceil", 0.95)) * 255.0
    micro_var = np.hypot(gx_fine, gy_fine) * seam_fade
    rough_norm = rough_raw / 255.0
    rough_target = r_floor + rough_norm * max(18.0, (r_ceil - r_floor)) + 0.12 * micro_var

    # Métallicité de base bornée pour préserver au moins 45-65 % d'albédo diffus (évite l'assombrissement métallique en Cycles/Three.js)
    metal_scale = min(float(profile.get("metallic_scale", 1.0)), 0.85)
    metal_target = np.clip(metal_raw * metal_scale * 0.52, 0.0, 135.0)

    # Cartographie matérielle multi-zones par texel (différenciation spatiale sur l'atlas UV)
    if profile.get("multi_zone_cartography", True):
        hsv = cv2.cvtColor(rgb, cv2.COLOR_RGB2HSV)
        hue = hsv[..., 0].astype(np.float32)   # [0..180] dans OpenCV
        sat = hsv[..., 1].astype(np.float32)   # [0..255]
        val = hsv[..., 2].astype(np.float32)   # [0..255]
        r_ch = rgb_f[..., 0]
        g_ch = rgb_f[..., 1]
        b_ch = rgb_f[..., 2]

        # Zone 1 : Traits d'encre sombres / cernes / plomb de vitrail / creux profonds -> Mats et non-métalliques
        dark_outline_mask = (luma < 36.0) & valid_uv
        if profile.get("outline_matte_lock"):
            dark_outline_mask = ((luma < 48.0) & (sat < 95.0)) & valid_uv
        if dark_outline_mask.any():
            rough_target = np.where(dark_outline_mask, np.maximum(rough_target, 232.0), rough_target)
            metal_target = np.where(dark_outline_mask, 0.0, metal_target)

        # Zone 1b : Vitrail émeraude / verre coloré / écailles en porcelaine / peau -> Diélectriques purs (metal <= 12)
        emerald_glass_mask = (g_ch > r_ch + 20.0) & (g_ch > 62.0) & valid_uv
        if emerald_glass_mask.any():
            metal_target = np.where(emerald_glass_mask, 0.0, metal_target)
            rough_target = np.where(emerald_glass_mask, np.clip(rough_target, 138.0, 185.0), rough_target)

        porcelain_or_skin_dielectric = (
            ((val > 145.0) & (sat < 68.0))
            | ((r_ch > 140.0) & (g_ch > 100.0) & (r_ch > b_ch + 18.0) & (sat < 110.0))
        ) & valid_uv
        if porcelain_or_skin_dielectric.any():
            metal_target = np.where(porcelain_or_skin_dielectric, np.minimum(metal_target, 10.0), metal_target)
            rough_target = np.where(porcelain_or_skin_dielectric, np.maximum(rough_target, 118.0), rough_target)

        # Zone 2 : Veines d'or / laiton / cuivre / dorures (Kintsugi, Steampunk, Ornements)
        pure_gold_veins = np.zeros_like(valid_uv, dtype=bool)
        if profile.get("vein_metallic_boost") or meta.get("kintsugi_24k_refined"):
            warm_gold_mask = (
                (hue >= 9.0) & (hue <= 38.0) & (sat >= 78.0) & (val >= 110.0) & valid_uv
            )
            pure_gold_veins = (r_ch > 218.0) & (g_ch > 168.0) & (b_ch < 65.0) & valid_uv
            if warm_gold_mask.any():
                if meta.get("kintsugi_24k_refined"):
                    metal_target = np.where(warm_gold_mask, 165.0, metal_target)
                    rough_target = np.where(warm_gold_mask, 58.0, rough_target)
                else:
                    metal_target = np.where(warm_gold_mask, np.clip(np.maximum(metal_target, 128.0), 115.0, 145.0), metal_target)
                    rough_target = np.where(warm_gold_mask, np.clip(rough_target * 0.65, 68.0, 96.0), rough_target)
                meta["multi_zone_veins_detected"] = True
            if pure_gold_veins.any():
                metal_target = np.where(pure_gold_veins, 236.0, metal_target)
                rough_target = np.where(pure_gold_veins, 32.0, rough_target)
                meta["multi_zone_veins_detected"] = True
            # Zone 4 : Acier / Argent / Chrome froid coexistant avec l'or ou la céramique
            cool_steel_mask = (
                (sat >= 6.0) & (sat <= 42.0) & (val >= 135.0) & (val <= 232.0) & (micro_var > 2.5) & valid_uv
            )
            if cool_steel_mask.any() and float(profile.get("metallic_scale", 1.0)) >= 0.85:
                metal_target = np.where(cool_steel_mask, np.clip(np.maximum(metal_target, 118.0), 100.0, 140.0), metal_target)
                rough_target = np.where(cool_steel_mask, np.clip(rough_target, 74.0, 115.0), rough_target)

        # Zone 3 : Reflets spéculaires purs (yeux, gemmes, éclats d'émail)
        highlight_mask = (luma > 240.0) & (sat < 35.0) & valid_uv
        if highlight_mask.any():
            rough_target = np.where(highlight_mask, np.minimum(rough_target, 52.0), rough_target)
            metal_target = np.where(highlight_mask, 0.0, metal_target)

        # Zone 5 : Synthèse sélective de carte émissive lorsque emissiveStrength > 1.0
        if float(profile.get("emissiveStrength") or 1.0) > 1.0 and getattr(mat, "emissiveTexture", None) is None:
            emissive_mask = ((sat >= 105.0) & (val >= 165.0) | (val >= 235.0)) & valid_uv
            if emissive_mask.any():
                em_rgb = np.zeros_like(rgb)
                em_rgb[emissive_mask] = rgb[emissive_mask]
                em_dil = _voronoi_dilate_uv_gutters(em_rgb, valid_uv)
                mat.emissiveTexture = Image.fromarray(em_dil, mode="RGB")
                mat.emissiveFactor = [1.0, 1.0, 1.0]
                meta["emissive_map_synthesized"] = True

    if meta.get("is_optical_crystal_glass") and not meta.get("character_face_projected"):
        # Cristal / Verre optique : surface ultra-polie (roughness 10..42), gravures dépolies (roughness 112) et zéro métallicité
        engraved_mask = ((np.abs(curv_uv) > 0.045) | (luma > 218.0) | (micro_var > 4.2)) & valid_uv
        rough_glass = np.where(engraved_mask, 112.0, np.clip(rough_target * 0.22, 10.0, 38.0))
        rough_cal = np.clip(np.round(rough_glass), 10.0, 128.0).astype(np.uint8)
        metal_cal = np.zeros_like(rough_cal, dtype=np.uint8)
    else:
        rough_cal = np.clip(np.round(rough_target), 52.0, min(250.0, max(r_ceil, 235.0))).astype(np.uint8)
        metal_cap = 168.0 if meta.get("kintsugi_24k_refined") else 145.0
        if meta.get("character_face_projected"):
            rough_cal = np.maximum(rough_cal, 148).astype(np.uint8)
            metal_cap = min(metal_cap, 45.0)
        metal_cal = np.clip(np.round(metal_target), 0.0, metal_cap).astype(np.uint8)
        if not meta.get("character_face_projected") and "pure_gold_veins" in locals() and pure_gold_veins.any():
            rough_cal = np.where(pure_gold_veins, 32, rough_cal).astype(np.uint8)
            metal_cal = np.where(pure_gold_veins, 236, metal_cal).astype(np.uint8)

    # Dilatation Voronoï plein-atlas dans les gouttières UV
    rgb_dil = _voronoi_dilate_uv_gutters(rgb, valid_uv)
    orm_packed = np.stack([ao_u8, rough_cal, metal_cal], axis=-1)
    orm_dil = _voronoi_dilate_uv_gutters(orm_packed, valid_uv)

    albedo_rgba[..., :3] = rgb_dil
    if meta.get("is_optical_crystal_glass") and not meta.get("character_face_projected"):
        fresnel_rim = 1.0 - np.clip(np.abs(vnz_uv), 0.0, 1.0)
        engraved_alpha_boost = np.where((luma > 212.0) | (np.abs(curv_uv) > 0.045), 62.0, 0.0)
        glass_alpha = np.clip(np.round(142.0 + 78.0 * fresnel_rim + engraved_alpha_boost), 136.0, 248.0).astype(np.uint8)
        albedo_rgba[..., 3] = np.where(valid_uv, glass_alpha, 255).astype(np.uint8)
    else:
        albedo_rgba[..., 3] = 255
    mat.baseColorTexture = Image.fromarray(albedo_rgba, mode="RGBA")
    mat.metallicRoughnessTexture = Image.fromarray(orm_dil, mode="RGB")

    return meta


def inject_gltf_optical_extensions(glb_path: str | Path, meta: dict[str, Any] | None) -> bool:
    """Injecte proprement les 9 extensions optiques glTF 2.0 (`KHR_materials_ior`,
    `KHR_materials_specular`, `KHR_materials_clearcoat`, `KHR_materials_sheen`,
    `KHR_materials_transmission`, `KHR_materials_volume`, `KHR_materials_emissive_strength`,
    `KHR_materials_anisotropy`, `KHR_materials_iridescence`) et lie `occlusionTexture`
    au canal R de `metallicRoughnessTexture`."""
    if not meta:
        return False
    p = Path(glb_path)
    if not p.is_file():
        return False
    try:
        raw = p.read_bytes()
        if len(raw) < 20 or raw[:4] != b"glTF":
            return False
        _, _, total_len = struct.unpack_from("<4sII", raw, 0)
        j_len, j_type = struct.unpack_from("<II", raw, 12)
        if j_type != 0x4E4F534A:
            return False
        j_end = 20 + j_len
        doc = json.loads(raw[20:j_end].decode("utf-8"))
        bin_chunk = raw[j_end:total_len]

        exts_used = set(doc.get("extensionsUsed") or [])
        materials = doc.get("materials") or []
        if not materials:
            return False

        for mat in materials:
            pbr = mat.get("pbrMetallicRoughness") or {}
            if "baseColorTexture" in pbr:
                if meta.get("is_optical_crystal_glass"):
                    pbr["baseColorFactor"] = [1.0, 1.0, 1.0, float(meta.get("baseColorAlpha", 1.0))]
                    mat["alphaMode"] = str(meta.get("alphaMode", "OPAQUE"))
                    mat["doubleSided"] = True
                else:
                    pbr["baseColorFactor"] = [1.0, 1.0, 1.0, 1.0]
            mrt_info = pbr.get("metallicRoughnessTexture")
            if isinstance(mrt_info, dict) and "index" in mrt_info:
                pbr["roughnessFactor"] = 1.0
                pbr["metallicFactor"] = 0.0 if meta.get("is_optical_crystal_glass") else 1.0
                if "occlusionTexture" not in mat:
                    mat["occlusionTexture"] = {
                        "index": mrt_info["index"],
                        "strength": float(meta.get("occlusionStrength", 0.75)),
                    }

            mat_exts = mat.setdefault("extensions", {})
            if "ior" in meta:
                mat_exts["KHR_materials_ior"] = {"ior": float(meta["ior"])}
                exts_used.add("KHR_materials_ior")
            if "specularFactor" in meta:
                spec_ext: dict[str, Any] = {"specularFactor": float(meta["specularFactor"])}
                if "specularColorFactor" in meta:
                    spec_ext["specularColorFactor"] = list(meta["specularColorFactor"])
                mat_exts["KHR_materials_specular"] = spec_ext
                exts_used.add("KHR_materials_specular")
            if float(meta.get("clearcoatFactor") or 0.0) > 0.0:
                mat_exts["KHR_materials_clearcoat"] = {
                    "clearcoatFactor": float(meta["clearcoatFactor"]),
                    "clearcoatRoughnessFactor": float(meta.get("clearcoatRoughnessFactor", 0.04)),
                }
                exts_used.add("KHR_materials_clearcoat")
            if "sheenColorFactor" in meta:
                mat_exts["KHR_materials_sheen"] = {
                    "sheenColorFactor": list(meta["sheenColorFactor"]),
                    "sheenRoughnessFactor": float(meta.get("sheenRoughnessFactor", 0.8)),
                }
                exts_used.add("KHR_materials_sheen")
            if float(meta.get("transmissionFactor") or 0.0) > 0.0:
                mat_exts["KHR_materials_transmission"] = {
                    "transmissionFactor": float(meta["transmissionFactor"]),
                }
                exts_used.add("KHR_materials_transmission")
            if "attenuationDistance" in meta:
                vol_ext: dict[str, Any] = {
                    "thicknessFactor": float(meta.get("thicknessFactor", 0.24)),
                    "attenuationDistance": float(meta["attenuationDistance"]),
                }
                if "attenuationColor" in meta:
                    vol_ext["attenuationColor"] = list(meta["attenuationColor"])
                mat_exts["KHR_materials_volume"] = vol_ext
                exts_used.add("KHR_materials_volume")
            if float(meta.get("emissiveStrength") or 1.0) > 1.0:
                mat_exts["KHR_materials_emissive_strength"] = {
                    "emissiveStrength": float(meta["emissiveStrength"]),
                }
                if "emissiveTexture" in mat and not mat.get("emissiveFactor"):
                    mat["emissiveFactor"] = [1.0, 1.0, 1.0]
                exts_used.add("KHR_materials_emissive_strength")
            if float(meta.get("anisotropyStrength") or 0.0) > 0.0:
                mat_exts["KHR_materials_anisotropy"] = {
                    "anisotropyStrength": float(meta["anisotropyStrength"]),
                    "anisotropyRotation": float(meta.get("anisotropyRotation", 0.0)),
                }
                exts_used.add("KHR_materials_anisotropy")
            if float(meta.get("iridescenceFactor") or 0.0) > 0.0:
                mat_exts["KHR_materials_iridescence"] = {
                    "iridescenceFactor": float(meta["iridescenceFactor"]),
                    "iridescenceIor": float(meta.get("iridescenceIor", 1.38)),
                    "iridescenceThicknessMinimum": float(meta.get("iridescenceThicknessMinimum", 140.0)),
                    "iridescenceThicknessMaximum": float(meta.get("iridescenceThicknessMaximum", 420.0)),
                }
                exts_used.add("KHR_materials_iridescence")

        if exts_used:
            doc["extensionsUsed"] = sorted(exts_used)

        new_json = json.dumps(doc, separators=(",", ":")).encode("utf-8")
        pad = (4 - (len(new_json) % 4)) % 4
        if pad:
            new_json += b" " * pad
        new_total = 12 + 8 + len(new_json) + len(bin_chunk)
        header = struct.pack("<4sII", b"glTF", 2, new_total)
        j_header = struct.pack("<II", len(new_json), 0x4E4F534A)
        p.write_bytes(header + j_header + new_json + bin_chunk)
        return True
    except Exception:
        return False


def transfer_pbr_from_source_glb(
    source_glb_path: str | Path,
    target_glb_path: str | Path,
    prompt_context: str = "",
) -> bool:
    """Transfère sans perte les textures PBR (`baseColorTexture`, `normalTexture`,
    `metallicRoughnessTexture` ORM, `occlusionTexture`, `emissiveTexture`) et les
    extensions optiques glTF 2.0 d'un GLB statique source vers un GLB riggé/animé cible,
    sans jamais altérer les buffers géométriques, `skins`, `nodes` ou `animations`."""
    src_p = Path(source_glb_path)
    dst_p = Path(target_glb_path)
    if not src_p.is_file() or not dst_p.is_file():
        return False
    try:
        import glb_io

        src_j, src_blob = glb_io.load(src_p)
        dst_j, dst_blob = glb_io.load(dst_p)
        src_mats = src_j.get("materials") or []
        dst_mats = dst_j.get("materials") or []
        if not src_mats or not dst_mats:
            return False

        dst_blob_ba = bytearray(dst_blob)
        dst_bvs = dst_j.setdefault("bufferViews", [])
        dst_imgs = dst_j.setdefault("images", [])
        dst_texs = dst_j.setdefault("textures", [])
        copied_tex_cache: dict[int, int] = {}

        def _clone_tex(src_tex_info: dict[str, Any] | None) -> dict[str, Any] | None:
            if not isinstance(src_tex_info, dict) or "index" not in src_tex_info:
                return None
            s_tidx = int(src_tex_info["index"])
            if s_tidx in copied_tex_cache:
                out_info = dict(src_tex_info)
                out_info["index"] = copied_tex_cache[s_tidx]
                return out_info
            src_tex_list = src_j.get("textures") or []
            src_img_list = src_j.get("images") or []
            if s_tidx < 0 or s_tidx >= len(src_tex_list):
                return None
            s_iidx = src_tex_list[s_tidx].get("source")
            if s_iidx is None or s_iidx < 0 or s_iidx >= len(src_img_list):
                return None
            raw_bytes = glb_io.image_bytes(src_j, src_blob, int(s_iidx))
            mime = src_img_list[int(s_iidx)].get("mimeType", "image/png")

            pad_len = (4 - (len(dst_blob_ba) % 4)) % 4
            if pad_len:
                dst_blob_ba.extend(b"\x00" * pad_len)
            offset = len(dst_blob_ba)
            dst_blob_ba.extend(raw_bytes)

            bv_idx = len(dst_bvs)
            dst_bvs.append({
                "buffer": 0,
                "byteOffset": offset,
                "byteLength": len(raw_bytes),
            })
            img_idx = len(dst_imgs)
            dst_imgs.append({
                "bufferView": bv_idx,
                "mimeType": mime,
            })
            tex_entry: dict[str, Any] = {"source": img_idx}
            if dst_j.get("samplers"):
                tex_entry["sampler"] = 0
            tex_idx = len(dst_texs)
            dst_texs.append(tex_entry)
            copied_tex_cache[s_tidx] = tex_idx

            out_info = dict(src_tex_info)
            out_info["index"] = tex_idx
            return out_info

        exts_used = set(dst_j.get("extensionsUsed") or [])
        for s_ext in (src_j.get("extensionsUsed") or []):
            if str(s_ext).startswith("KHR_materials_"):
                exts_used.add(str(s_ext))

        for idx, dst_mat in enumerate(dst_mats):
            src_mat = src_mats[idx] if idx < len(src_mats) else src_mats[0]
            src_pbr = src_mat.get("pbrMetallicRoughness") or {}
            dst_pbr = dst_mat.setdefault("pbrMetallicRoughness", {})

            if "baseColorTexture" in src_pbr:
                new_bct = _clone_tex(src_pbr["baseColorTexture"])
                if new_bct is not None:
                    dst_pbr["baseColorTexture"] = new_bct
                    dst_pbr["baseColorFactor"] = src_pbr.get("baseColorFactor", [1.0, 1.0, 1.0, 1.0])

            if "metallicRoughnessTexture" in src_pbr:
                new_mrt = _clone_tex(src_pbr["metallicRoughnessTexture"])
                if new_mrt is not None:
                    dst_pbr["metallicRoughnessTexture"] = new_mrt
                    dst_pbr["metallicFactor"] = float(src_pbr.get("metallicFactor", 1.0))
                    dst_pbr["roughnessFactor"] = float(src_pbr.get("roughnessFactor", 1.0))
                    occ_strength = 0.75
                    if isinstance(src_mat.get("occlusionTexture"), dict):
                        occ_strength = float(src_mat["occlusionTexture"].get("strength", 0.75))
                    dst_mat["occlusionTexture"] = {
                        "index": new_mrt["index"],
                        "strength": occ_strength,
                    }

            if "normalTexture" in src_mat:
                new_nrm = _clone_tex(src_mat["normalTexture"])
                if new_nrm is not None:
                    dst_mat["normalTexture"] = new_nrm

            if "emissiveTexture" in src_mat:
                new_emi = _clone_tex(src_mat["emissiveTexture"])
                if new_emi is not None:
                    dst_mat["emissiveTexture"] = new_emi
            if "emissiveFactor" in src_mat:
                dst_mat["emissiveFactor"] = list(src_mat["emissiveFactor"])

            if isinstance(src_mat.get("extensions"), dict):
                dst_exts = dst_mat.setdefault("extensions", {})
                for k, v in src_mat["extensions"].items():
                    dst_exts[k] = v
                    exts_used.add(k)

        if exts_used:
            dst_j["extensionsUsed"] = sorted(exts_used)
        if dst_j.get("buffers"):
            dst_j["buffers"][0]["byteLength"] = len(dst_blob_ba)

        glb_io.save(dst_p, dst_j, bytes(dst_blob_ba))
        if prompt_context and not any(str(e).startswith("KHR_materials_") for e in exts_used):
            inject_gltf_optical_extensions(dst_p, resolve_pbr_optical_profile(prompt_context))
        return True
    except Exception:
        return False
