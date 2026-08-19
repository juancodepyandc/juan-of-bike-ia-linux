#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""selection_sujet — ne reconstruire QUE ce que l'utilisateur veut.

Demande du 30/07: sur la photo fournie, pouvoir isoler le sujet reel — juste
la tete, juste l'objet pose sur la table — au lieu de laisser la
reconstruction avaler toute la scene (parasites, decor, mains, fond).

Trois modes, du plus autonome au plus fiable:
  1. AUTO      : aucune indication -> le sujet principal est detoure tout seul
                 (l'image sans modification "se debrouille").
  2. CLIC      : l'utilisateur pointe l'objet -> on segmente la region qui
                 contient ce point (croissance de region sur couleur+contours),
                 puis on recadre dessus.
  3. CADRE     : l'utilisateur trace un rectangle -> recadrage strict, c'est le
                 mode le plus previsible et le filet de securite quand la
                 reconnaissance se trompe.

Sortie: une image RGBA detouree (fond transparent), prete pour la chaine 3D
(le pipeline aplatit lui-meme l'alpha avant reconstruction).

Usage:
  python selection_sujet.py --image photo.webp --sortie sujet.png            # auto
  python selection_sujet.py --image photo.webp --sortie s.png --clic 0.42,0.31
  python selection_sujet.py --image photo.webp --sortie s.png --cadre 0.1,0.2,0.6,0.8
Les coordonnees sont NORMALISEES (0..1) pour etre independantes de l'affichage.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path


def _charger(chemin: str):
    from PIL import Image
    im = Image.open(chemin)
    # tout format: webp/avif/heic/png/jpg... et on PRESERVE l'alpha existant
    return im.convert("RGBA") if "A" in im.getbands() else im.convert("RGB")


def _detourer_auto(im):
    """Sujet principal, sans indication."""
    import numpy as np
    try:
        from rembg import remove
        # ALPHA MATTING (31/07, constate: le detourage mangeait les CHEVEUX).
        # Le matting affine la frontiere sur les zones fines (meches, poils)
        # au lieu d'un masque binaire brutal.
        try:
            out = remove(im.convert("RGB"), alpha_matting=True,
                         alpha_matting_foreground_threshold=240,
                         alpha_matting_background_threshold=15,
                         alpha_matting_erode_size=5)
        except Exception:  # noqa: BLE001 - PYMATTING PLANTE (Cholesky
            # non defini-positif) sur certaines images: masque simple.
            out = remove(im.convert("RGB"))
        a = np.asarray(out)
        if a.shape[2] == 4 and (a[..., 3] > 10).mean() > 0.005:
            return out
    except Exception:  # noqa: BLE001
        pass
    # repli sans modele: ce qui s'ecarte de la couleur des coins
    from PIL import Image
    arr = np.asarray(im.convert("RGB")).astype(np.float32)
    h, w = arr.shape[:2]
    c = max(4, min(h, w) // 32)
    coins = np.concatenate([arr[:c, :c].reshape(-1, 3), arr[:c, -c:].reshape(-1, 3),
                            arr[-c:, :c].reshape(-1, 3), arr[-c:, -c:].reshape(-1, 3)])
    fond = np.median(coins, axis=0)
    masque = (np.abs(arr - fond).sum(axis=2) > 45).astype(np.uint8) * 255
    rgba = np.dstack([arr.astype(np.uint8), masque])
    return Image.fromarray(rgba, "RGBA")


def _segmenter_clic(im, x: float, y: float):
    """Region contenant le point pointe (couleur + contours, sans modele)."""
    import cv2
    import numpy as np
    from PIL import Image
    rgb = np.asarray(im.convert("RGB"))
    h, w = rgb.shape[:2]
    px, py = int(round(x * (w - 1))), int(round(y * (h - 1)))
    # GrabCut initialise autour du clic: c'est ce qui distingue un objet de
    # son support (l'objet SUR la table, pas la table).
    masque = np.zeros((h, w), np.uint8)
    marge_x, marge_y = int(w * 0.28), int(h * 0.28)
    rect = (max(px - marge_x, 0), max(py - marge_y, 0),
            min(2 * marge_x, w - max(px - marge_x, 0)),
            min(2 * marge_y, h - max(py - marge_y, 0)))
    bgd, fgd = np.zeros((1, 65), np.float64), np.zeros((1, 65), np.float64)
    try:
        cv2.grabCut(rgb, masque, rect, bgd, fgd, 5, cv2.GC_INIT_WITH_RECT)
        # le point clique est du sujet, par definition
        cv2.circle(masque, (px, py), max(3, min(h, w) // 60), cv2.GC_FGD, -1)
        cv2.grabCut(rgb, masque, None, bgd, fgd, 3, cv2.GC_INIT_WITH_MASK)
    except Exception:  # noqa: BLE001
        return None
    alpha = np.where((masque == cv2.GC_FGD) | (masque == cv2.GC_PR_FGD), 255, 0).astype(np.uint8)
    if alpha.mean() < 2:
        return None
    # ne garder que la piece qui contient le clic (pas les taches lointaines)
    n, lab = cv2.connectedComponents(alpha)
    if n > 1 and lab[py, px] > 0:
        alpha = np.where(lab == lab[py, px], 255, 0).astype(np.uint8)
    return Image.fromarray(np.dstack([rgb, alpha]), "RGBA")


def _recadrer_cadre(im, x0: float, y0: float, x1: float, y1: float):
    w, h = im.size
    boite = (int(min(x0, x1) * w), int(min(y0, y1) * h),
             int(max(x0, x1) * w), int(max(y0, y1) * h))
    if boite[2] - boite[0] < 8 or boite[3] - boite[1] < 8:
        return None
    return im.crop(boite)


def _rogner_sur_alpha(im, marge: float = 0.06):
    import numpy as np
    a = np.asarray(im)
    if a.shape[2] < 4:
        return im
    ys, xs = np.nonzero(a[..., 3] > 12)
    if len(xs) < 30:
        return im
    mx = int((xs.max() - xs.min()) * marge) + 2
    my = int((ys.max() - ys.min()) * marge) + 2
    h, w = a.shape[:2]
    return im.crop((max(int(xs.min()) - mx, 0), max(int(ys.min()) - my, 0),
                    min(int(xs.max()) + mx, w), min(int(ys.max()) + my, h)))


def selectionner(image: str, sortie: str, clic=None, cadre=None,
                 detourer: bool = True) -> dict:
    im = _charger(image)
    mode, note = "auto", ""
    if cadre:
        rec = _recadrer_cadre(im, *cadre)
        if rec is None:
            return {"ok": False, "error": "cadre trop petit"}
        im, mode = rec, "cadre"
        if detourer:
            im = _detourer_auto(im)
    elif clic:
        seg = _segmenter_clic(im, *clic)
        if seg is None:
            # le manuel reste le filet: on recadre autour du clic
            x, y = clic
            im = _recadrer_cadre(im, max(x - .25, 0), max(y - .25, 0),
                                 min(x + .25, 1), min(y + .25, 1)) or im
            im, mode = _detourer_auto(im), "clic_repli_cadre"
            note = "segmentation incertaine -> recadrage autour du point"
        else:
            im, mode = seg, "clic"
    elif detourer:
        im = _detourer_auto(im)
    im = _rogner_sur_alpha(im)
    Path(sortie).parent.mkdir(parents=True, exist_ok=True)
    im.save(sortie)
    return {"ok": True, "mode": mode, "sortie": sortie,
            "taille": list(im.size), "note": note}


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--image", required=True)
    ap.add_argument("--sortie", required=True)
    ap.add_argument("--clic", default=None, help="x,y normalises 0..1")
    ap.add_argument("--cadre", default=None, help="x0,y0,x1,y1 normalises 0..1")
    ap.add_argument("--sans-detourage", action="store_true")
    a = ap.parse_args()
    _clic = tuple(float(v) for v in a.clic.split(",")) if a.clic else None
    _cadre = tuple(float(v) for v in a.cadre.split(",")) if a.cadre else None
    print(json.dumps(selectionner(a.image, a.sortie, _clic, _cadre,
                                  not a.sans_detourage), ensure_ascii=False))
