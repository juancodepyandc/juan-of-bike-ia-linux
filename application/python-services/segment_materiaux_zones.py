#!/usr/bin/env python3
"""Segmente un GLB texture en zones de matiere (verre / liquide / metal) et
ecrit une primitive + un vrai materiau par zone.

Pourquoi ce module existe: `glb_material_writer` pose les extensions sur UN
materiau, et masque la transmission par texture. Mais `ior`, `thickness`,
`attenuationColor` et `metallicFactor` sont des scalaires PAR MATERIAU: ils ne
sont pas masquables. Un sujet verre + liquide + or ne peut donc pas etre rendu
par un materiau unique, quel que soit le masque. Il faut decouper la geometrie.

Methode:
  1. couleur par triangle, echantillonnee dans l'atlas a PLEINE resolution
     (convention glTF: v croit vers le BAS, ne pas retourner comme en OpenGL);
  2. etiquette initiale par saturation + hauteur;
  3. soudure des sommets dedoubles -> vrai voisinage triangle-triangle;
  4. vote majoritaire sur le voisinage -> supprime le confetti;
  5. une primitive par zone, partageant les memes accesseurs de sommets.

Usage:
  python segment_materiaux_zones.py --glb E.glb --out S.glb [--seuil-sat 0.22]
     [--y-or -0.04] [--liquide-couleur 0.98,0.79,0.40] [--liquide-distance 0.19]
"""
from __future__ import annotations
import argparse, copy, io, sys
from pathlib import Path

import numpy as np
import scipy.sparse as sp
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent))
import glb_io

Image.MAX_IMAGE_PIXELS = None
VERRE, LIQ, OR = 0, 1, 2
NOM = {VERRE: "verre", LIQ: "liquide", OR: "or"}


def couleur_par_triangle(j, blob, F, UV):
    """Mediane des 3 sommets + centroide, dans l'atlas plein. Robuste au gutter."""
    src = j["textures"][j["materials"][0]["pbrMetallicRoughness"]
                        ["baseColorTexture"]["index"]]["source"]
    T = np.asarray(Image.open(io.BytesIO(glb_io.image_bytes(j, blob, src))).convert("RGB"))
    R = T.shape[0]

    def ech(uv):
        px = np.clip((uv[:, 0] % 1.0) * (R - 1), 0, R - 1).astype(np.int32)
        py = np.clip((uv[:, 1] % 1.0) * (R - 1), 0, R - 1).astype(np.int32)  # glTF: pas de flip
        return T[py, px].astype(np.float32) / 255.0

    uvs = UV[F]
    C = np.median(np.stack([ech(uvs[:, 0]), ech(uvs[:, 1]),
                            ech(uvs[:, 2]), ech(uvs.mean(1))], 0), axis=0)
    del T
    mx, mn = C.max(1), C.min(1)
    S = np.where(mx > 1e-6, (mx - mn) / np.maximum(mx, 1e-6), 0.0)
    return C, S, mx


def voisinage(P, F):
    """Soude les sommets dedoubles puis rend l'adjacence triangle-triangle."""
    q = (P.max(0) - P.min(0)).max() * 1e-4
    _, inv = np.unique(np.round(P / q).astype(np.int64), axis=0, return_inverse=True)
    Fw = inv[F]
    n = len(F)
    e = np.sort(np.concatenate([Fw[:, [0, 1]], Fw[:, [1, 2]], Fw[:, [2, 0]]]), axis=1)
    tri = np.tile(np.arange(n), 3)
    _, eid = np.unique(e, axis=0, return_inverse=True)
    o = np.argsort(eid, kind="stable")
    a, b = [], []
    for g in np.split(tri[o], np.flatnonzero(np.diff(eid[o])) + 1):
        if len(g) == 2:
            a.append(g[0]); b.append(g[1])
        elif 2 < len(g) <= 6:
            for i in range(len(g)):
                for k in range(i + 1, len(g)):
                    a.append(g[i]); b.append(g[k])
    a, b = np.array(a), np.array(b)
    A = sp.coo_matrix((np.ones(len(a) * 2),
                       (np.concatenate([a, b]), np.concatenate([b, a]))),
                      shape=(n, n)).tocsr()
    return A, int(inv.max()) + 1


def lisse(lab, A, n, tours=8):
    """Vote majoritaire: un triangle isole prend l'etiquette de ses voisins."""
    for _ in range(tours):
        oh = np.zeros((n, 3), np.float32)
        oh[np.arange(n), lab] = 1.0
        nouveau = (A @ oh + oh * 0.9).argmax(1).astype(np.int8)
        chg = int((nouveau != lab).sum())
        lab = nouveau
        if chg < n // 2000:
            break
    return lab


def segmente(glb, out, seuil_sat=0.22, y_or=-0.04, coque=False, alpha_verre=0.38,
             rendu="universel", epaisseur_verre=0.12,
             liq_couleur=(0.98, 0.79, 0.40), liq_distance=0.45, liq_epaisseur=0.11):
    j, blob = glb_io.load(glb)
    pr = j["meshes"][0]["primitives"][0]
    P = glb_io.accessor(j, blob, pr["attributes"]["POSITION"]).astype(np.float32)
    UV = glb_io.accessor(j, blob, pr["attributes"]["TEXCOORD_0"]).astype(np.float32)
    F = glb_io.accessor(j, blob, pr["indices"]).astype(np.int64).reshape(-1, 3)
    n = len(F)

    _, S, _ = couleur_par_triangle(j, blob, F, UV)
    Y = P[F][:, :, 1].mean(1)
    lab = np.full(n, VERRE, np.int8)
    sat = S >= seuil_sat
    lab[sat & (Y < y_or)] = VERRE if coque else LIQ
    lab[sat & (Y >= y_or)] = OR

    A, nsoud = voisinage(P, F)
    print("sommets %d -> %d apres soudure" % (len(P), nsoud), flush=True)
    lab = lisse(lab, A, n)
    print("zones:", {NOM[k]: int((lab == k).sum()) for k in NOM}, flush=True)

    bin_extra = bytearray(blob)

    def ajoute_indices(idx):
        arr = idx.astype(np.uint32).tobytes()
        while len(bin_extra) % 4:
            bin_extra.append(0)
        off = len(bin_extra)
        bin_extra.extend(arr)
        j["bufferViews"].append({"buffer": 0, "byteOffset": off,
                                 "byteLength": len(arr), "target": 34963})
        j["accessors"].append({"bufferView": len(j["bufferViews"]) - 1,
                               "componentType": 5125, "count": int(len(idx)),
                               "type": "SCALAR"})
        return len(j["accessors"]) - 1

    btex = j["materials"][0]["pbrMetallicRoughness"].get("baseColorTexture")
    # En mode coque, un VOLUME de liquide sera ajoute a l'interieur: la coque doit
    # alors etre INCOLORE. Garder l'atlas y recollerait l'ambre peint sur la paroi
    # — exactement le defaut qu'on cherche a supprimer.
    btex_verre = None if coque else btex
    DEF = {
        # On GARDE la baseColorTexture sur les 3 zones: c'est le REPLI. Un
        # visualiseur qui ne calcule pas KHR_materials_transmission n'affiche que
        # la couleur de base — sans texture il ne reste qu'un blanc uni, donc un
        # resultat PIRE que l'opaque d'origine (ni verre, ni liquide visible).
        # L'atlas portant deja l'ambre, l'absorption doit rester douce sous peine
        # de doubler l'assombrissement et de virer au chocolat.
        VERRE: {"name": "aurora_verre",
                "pbrMetallicRoughness": ({"baseColorTexture": btex_verre} if btex_verre else {}) | {
                    # LA TEINTE EST LA CLE. Un verre BLANC melange en alpha donne du
                    # LAIT, pas du verre: c'est ce qui delavait tout et faisait
                    # disparaitre le relief. Un gris-bleu leger blende comme du vrai
                    # verre, dans les DEUX familles de moteurs.
                    "baseColorFactor": [1.0, 1.0, 1.0, 1.0] if rendu == "cristal"
                    else [0.55, 0.62, 0.70, float(alpha_verre)],
                    "metallicFactor": 0.0,
                    "roughnessFactor": 0.02 if rendu == "cristal" else 0.06},
                # DOUBLE FACE OBLIGATOIRE: le maillage TRELLIS a des faces mal
                # orientees. En simple face elles sont eliminees par le culling
                # et la coque parait CASSEE, surtout vue de dos.
                "doubleSided": True,
                # rendu=universel (defaut) -> alphaMode BLEND avec une teinte legere.
                #   Marche partout: les moteurs qui gerent KHR_materials_transmission
                #   (three.js/ModelView, Blender) donnent du cristal, ceux qui
                #   l'ignorent (f3d/VTK) donnent du verre teinte lisible.
                # rendu=cristal -> alphaMode OPAQUE, blanc pur. Legerement plus net
                #   sur un moteur a transmission, mais BLOC BLANC OPAQUE partout
                #   ailleurs. A ne choisir que si la cible gere la transmission.
                "alphaMode": "OPAQUE" if rendu == "cristal" else "BLEND",
                "extensions": {"KHR_materials_transmission": {"transmissionFactor": 1.0},
                               "KHR_materials_ior": {"ior": 1.58},
                               "KHR_materials_specular": {"specularFactor": 1.0},
                               # thickness fait le CRISTAL: c'est la profondeur
                               # refractive. Trop bas (0.025) = film plat sans relief.
                               "KHR_materials_volume": {
                                   "thicknessFactor": float(epaisseur_verre),
                                   "attenuationDistance": 2.5,
                                   "attenuationColor": [0.93, 0.97, 1.0]}}},
        # LIQUIDE OPAQUE, ET C'EST VOULU. three.js ne peint que les objets
        # OPAQUES dans la cible de transmission (WebGLRenderer:
        # `renderObjects(opaqueObjects, ...)`). Un liquide lui-meme transmissif
        # n'entre donc JAMAIS dans ce que le verre laisse voir: il devient
        # litteralement invisible a travers le flacon. Il garde son atlas ambre,
        # une rugosite basse et un vernis: en temps reel il se lit comme un
        # liquide, et il reste visible dans un moteur a rayons.
        LIQ: {"name": "aurora_liquide",
              "pbrMetallicRoughness": {"baseColorTexture": btex,
                                       "baseColorFactor": [1, 1, 1, 1],
                                       "metallicFactor": 0.0, "roughnessFactor": 0.12},
              "doubleSided": False,
              "extensions": {"KHR_materials_ior": {"ior": 1.45},
                             "KHR_materials_specular": {"specularFactor": 1.0},
                             "KHR_materials_clearcoat": {"clearcoatFactor": 0.6,
                                                         "clearcoatRoughnessFactor": 0.05}}},
        OR: {"name": "aurora_or",
             "pbrMetallicRoughness": {"baseColorTexture": btex, "baseColorFactor": [1, 1, 1, 1],
                                      "metallicFactor": 1.0, "roughnessFactor": 0.18},
             "doubleSided": False},
    }

    prims = []
    for k in (VERRE, LIQ, OR):
        sel = np.flatnonzero(lab == k)
        if not len(sel):
            continue
        ai = ajoute_indices(F[sel].ravel())
        j["materials"].append(copy.deepcopy(DEF[k]))
        prims.append({"attributes": pr["attributes"], "indices": ai,
                      "material": len(j["materials"]) - 1})
        print("  %-8s %7d triangles" % (NOM[k], len(sel)), flush=True)

    j["meshes"][0]["primitives"] = prims
    j["extensionsUsed"] = sorted(set(j.get("extensionsUsed", [])) | {
        "KHR_materials_transmission", "KHR_materials_ior", "KHR_materials_volume",
        "KHR_materials_specular", "KHR_materials_clearcoat"})
    taille = glb_io.save(out, j, bytes(bin_extra))
    print("ECRIT %s (%.1f Mo) — passer glb_elaguer.py pour retirer le poids mort"
          % (out, taille / 1e6), flush=True)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--glb", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--rendu", choices=["universel", "cristal"], default="universel",
                    help="universel (defaut) = verre legerement teinte en alphaMode "
                         "BLEND: cristal dans les moteurs a transmission, verre lisible "
                         "dans les autres (f3d/VTK). cristal = blanc pur en alphaMode "
                         "OPAQUE, un cheveu plus net mais BLOC BLANC OPAQUE dans tout "
                         "moteur sans transmission.")
    ap.add_argument("--epaisseur-verre", type=float, default=0.12, dest="epaisseur_verre",
                    help="thicknessFactor du verre en mode cristal: c'est lui qui donne "
                         "la profondeur refractive. Trop bas = verre plat.")
    ap.add_argument("--alpha-verre", type=float, default=0.38, dest="alpha_verre",
                    help="opacite de repli du verre pour les visualiseurs sans "
                         "transmission (f3d/VTK...). Sans effet sur three.js.")
    ap.add_argument("--coque", action="store_true",
                    help="ne produit que verre + or (la zone ambree redevient du verre "
                         "incolore); a utiliser avec liquide_interieur.py")
    ap.add_argument("--seuil-sat", type=float, default=0.22, dest="seuil_sat")
    ap.add_argument("--y-or", type=float, default=-0.04, dest="y_or",
                    help="hauteur au-dessus de laquelle une zone saturee est du metal")
    ap.add_argument("--liquide-couleur", default="0.98,0.79,0.40", dest="liq_couleur")
    ap.add_argument("--liquide-distance", type=float, default=0.45, dest="liq_distance",
                    help="attenuationDistance, en UNITES DU MODELE (cale-la sur "
                         "l'epaisseur traversee, pas sur une valeur absolue)")
    a = ap.parse_args()
    segmente(a.glb, a.out, a.seuil_sat, a.y_or, a.coque, a.alpha_verre, a.rendu,
             a.epaisseur_verre,
             tuple(float(x) for x in a.liq_couleur.split(",")), a.liq_distance)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
