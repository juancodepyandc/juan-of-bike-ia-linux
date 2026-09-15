#!/usr/bin/env python3
"""Fabrique un VOLUME DE LIQUIDE a l'interieur d'un flacon reconstruit.

Pourquoi: TRELLIS (comme tout reconstructeur d'image) produit un SOLIDE — une
seule peau exterieure, sans cavite. Colorier en ambre la zone ventrale de cette
peau ne donne pas un liquide: ca donne de la peinture COLLEE A LA PAROI. Aucun
reglage de materiau ne rattrape ca, c'est un manque de geometrie.

Ce module ajoute la geometrie manquante: un corps de revolution ferme, place a
l'interieur de la coque, avec une surface plane au niveau du liquide. La coque
devient du verre incolore, et la couleur vient enfin de DERRIERE la paroi.

Le rayon suit un percentile du rayon exterieur mesure par tranche de hauteur
(pas le maximum: sinon le liquide deborderait dans les pattes et les bras).

Usage:
  python liquide_interieur.py --glb entree.glb --out sortie.glb
      [--niveau -0.07] [--fond -0.455] [--serrage 0.82]
      [--couleur 0.80,0.45,0.10]
"""
from __future__ import annotations
import argparse, io, json, sys
from pathlib import Path

import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent))
import glb_io

Image.MAX_IMAGE_PIXELS = None


def _rayon_exterieur(P, y_bas, y_haut, nY, nT, pct=85.0):
    """Rayon de la paroi par (tranche de hauteur, secteur angulaire).

    Un percentile haut, pas le maximum: le maillage TRELLIS traine des eclats
    isoles hors de la coque qui feraient exploser le rayon d'un secteur.
    """
    y = P[:, 1]
    dedans = (y >= y_bas) & (y < y_haut)
    y = y[dedans]
    x, z = P[dedans, 0], P[dedans, 2]
    r = np.hypot(x, z)
    th = np.mod(np.arctan2(z, x), 2.0 * np.pi)

    iy = np.clip(((y - y_bas) / (y_haut - y_bas) * nY).astype(int), 0, nY - 1)
    it = np.clip((th / (2.0 * np.pi) * nT).astype(int), 0, nT - 1)
    bid = iy * nT + it

    ordre = np.lexsort((r, bid))
    b_s, r_s = bid[ordre], r[ordre]
    tous = np.arange(nY * nT)
    deb = np.searchsorted(b_s, tous, "left")
    fin = np.searchsorted(b_s, tous, "right")
    n = fin - deb
    pick = deb + ((pct / 100.0) * np.maximum(n - 1, 0)).astype(int)
    val = np.where(n > 0, r_s[np.clip(pick, 0, max(len(r_s) - 1, 0))], np.nan)
    R = val.reshape(nY, nT)

    # bouche les secteurs vides: d'abord en angle (circulaire), puis en hauteur
    for i in range(nY):
        ligne = R[i]
        bon = ~np.isnan(ligne)
        if bon.sum() >= 2:
            idx = np.arange(nT)
            etendu = np.concatenate([idx[bon] - nT, idx[bon], idx[bon] + nT])
            vals = np.tile(ligne[bon], 3)
            R[i] = np.interp(idx, etendu, vals)
    for k in range(nT):
        col = R[:, k]
        bon = ~np.isnan(col)
        if bon.sum() >= 2:
            R[:, k] = np.interp(np.arange(nY), np.arange(nY)[bon], col[bon])
    R = np.nan_to_num(R, nan=float(np.nanmedian(R)) if np.isfinite(np.nanmedian(R)) else 0.1)

    # lissage: circulaire en angle, bords tenus en hauteur
    ka = np.ones(9) / 9.0
    R = np.apply_along_axis(lambda l: np.convolve(np.concatenate([l[-4:], l, l[:4]]), ka, "valid"), 1, R)
    ky = np.ones(5) / 5.0
    R = np.apply_along_axis(lambda c: np.convolve(np.pad(c, 2, mode="edge"), ky, "valid"), 0, R)
    ys = y_bas + (np.arange(nY) + 0.5) * (y_haut - y_bas) / nY
    return ys, R


def volume_liquide(P, niveau, fond, serrage, nY=110, nT=128, percentile=85.0,
                   epaisseur=0.052, plafond=0.94):
    """Volume ferme qui EPOUSE la paroi interieure, avec surface plane au niveau.

    Un corps de revolution circulaire ne marche pas: le lapin n'est pas rond.
    A l'arriere, ou la paroi est plus pres de l'axe, un liquide circulaire vient
    buter dans le verre et la coque parait cassee. Le rayon suit donc la section
    reelle, MOINS une epaisseur de verre absolue, et se plafonne au rayon median
    de la tranche pour ne pas s'engouffrer dans les pattes et les bras qui
    depassent.
    """
    ys, Rext = _rayon_exterieur(P, fond, niveau, nY, nT, percentile)
    Rmed = np.median(Rext, axis=1, keepdims=True)
    R = np.minimum(Rext * serrage - epaisseur, Rmed * plafond)
    R = np.maximum(R, 1e-3)

    nA = min(20, nY // 3)
    t = np.linspace(0.0, 1.0, nA)[:, None]
    R[:nA] *= np.sqrt(np.clip(1.0 - (1.0 - t) ** 2, 0.03, 1.0))

    th = np.linspace(0.0, 2.0 * np.pi, nT, endpoint=False)
    ct, st = np.cos(th), np.sin(th)
    V = np.zeros((nY * nT + 2, 3), np.float32)
    for i in range(nY):
        V[i * nT:(i + 1) * nT, 0] = R[i] * ct
        V[i * nT:(i + 1) * nT, 1] = ys[i]
        V[i * nT:(i + 1) * nT, 2] = R[i] * st
    c_bas, c_haut = nY * nT, nY * nT + 1
    V[c_bas] = (0.0, ys[0] - float(R[0].mean()) * 0.12, 0.0)
    V[c_haut] = (0.0, niveau, 0.0)

    F = []
    for i in range(nY - 1):
        a, b = i * nT, (i + 1) * nT
        for k in range(nT):
            k2 = (k + 1) % nT
            F.append((a + k, b + k, b + k2))
            F.append((a + k, b + k2, a + k2))
    for k in range(nT):
        F.append((c_bas, (k + 1) % nT, k))
    haut = (nY - 1) * nT
    for k in range(nT):
        F.append((c_haut, haut + k, haut + (k + 1) % nT))
    F = np.asarray(F, np.uint32)

    # normales lissees: somme des normales de faces, ponderee par leur aire
    N = np.zeros_like(V)
    tri = V[F.astype(np.int64)]
    nf = np.cross(tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0])
    for c in range(3):
        np.add.at(N, F[:, c].astype(np.int64), nf)
    L = np.linalg.norm(N, axis=1, keepdims=True)
    N = np.where(L > 1e-12, N / np.maximum(L, 1e-12), np.array([0.0, 1.0, 0.0]))
    return V, N.astype(np.float32), F


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--glb", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--niveau", type=float, default=-0.07, help="hauteur de la surface du liquide")
    ap.add_argument("--fond", type=float, default=-0.455)
    ap.add_argument("--serrage", type=float, default=0.97,
                    help="fraction du rayon interieur: <1 laisse l'epaisseur de verre")
    ap.add_argument("--percentile", type=float, default=85.0)
    ap.add_argument("--plafond", type=float, default=0.94,
                    help="rayon max du liquide en multiple du rayon median de la "
                         "tranche: <=1 laisse un lisere de verre clair la ou le "
                         "sujet deborde (pattes, bras)")
    ap.add_argument("--epaisseur", type=float, default=0.052,
                    help="epaisseur de verre laissee, en unites du modele")
    ap.add_argument("--couleur", default="0.55,0.20,0.015",
                    help="ambre du parfum, en RGB LINEAIRE. Un liquide opaque sature vers le blanc sous une lumiere vive: il faut le prendre nettement plus sombre que la couleur percue voulue.")
    a = ap.parse_args()

    j, blob = glb_io.load(a.glb)
    prims = j["meshes"][0]["primitives"]
    P = glb_io.accessor(j, blob, prims[0]["attributes"]["POSITION"]).astype(np.float32)

    V, N, F = volume_liquide(P, a.niveau, a.fond, a.serrage, percentile=a.percentile,
                            epaisseur=a.epaisseur, plafond=a.plafond)
    print("volume de liquide: %d sommets, %d triangles, niveau %+.3f, fond %+.3f"
          % (len(V), len(F), a.niveau, a.fond), flush=True)

    bin_extra = bytearray(blob)

    def ajoute(arr, ctype, typ, mini=None, maxi=None, target=None):
        raw = arr.tobytes()
        while len(bin_extra) % 4:
            bin_extra.append(0)
        off = len(bin_extra)
        bin_extra.extend(raw)
        bv = {"buffer": 0, "byteOffset": off, "byteLength": len(raw)}
        if target:
            bv["target"] = target
        j["bufferViews"].append(bv)
        acc = {"bufferView": len(j["bufferViews"]) - 1, "componentType": ctype,
               "count": int(arr.shape[0]), "type": typ}
        if mini is not None:
            acc["min"] = mini; acc["max"] = maxi
        j["accessors"].append(acc)
        return len(j["accessors"]) - 1

    a_pos = ajoute(V.astype(np.float32), 5126, "VEC3",
                   V.min(0).tolist(), V.max(0).tolist(), 34962)
    a_nor = ajoute(N.astype(np.float32), 5126, "VEC3", target=34962)
    a_idx = ajoute(F.ravel().astype(np.uint32), 5125, "SCALAR", target=34963)

    # LIQUIDE OPAQUE: three.js ne peint que les objets opaques dans la cible de
    # transmission, un liquide transmissif serait invisible a travers le verre.
    coul = [float(x) for x in a.couleur.split(",")]
    j["materials"].append({
        "name": "aurora_liquide_volume",
        "pbrMetallicRoughness": {"baseColorFactor": coul + [1.0],
                                 "metallicFactor": 0.0, "roughnessFactor": 0.16},
        "doubleSided": False,
        "extensions": {"KHR_materials_specular": {"specularFactor": 1.0},
                       "KHR_materials_ior": {"ior": 1.42},
                       "KHR_materials_clearcoat": {"clearcoatFactor": 0.22,
                                                   "clearcoatRoughnessFactor": 0.06}},
    })
    prims.append({"attributes": {"POSITION": a_pos, "NORMAL": a_nor},
                  "indices": a_idx, "material": len(j["materials"]) - 1})

    j["extensionsUsed"] = sorted(set(j.get("extensionsUsed", [])) |
                                 {"KHR_materials_specular", "KHR_materials_ior",
                                  "KHR_materials_clearcoat"})
    n = glb_io.save(a.out, j, bytes(bin_extra))
    print("ECRIT %s (%.1f Mo, %d primitives)" % (a.out, n / 1e6, len(prims)), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
