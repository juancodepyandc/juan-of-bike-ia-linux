#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""pose_analyse — mesures deterministes sur la reference AVANT derivation.

Etape 5 du plan toutes-poses (01/08): l'arbre de decision a besoin de faits
mesures, pas de suppositions:
  - angle de l'axe principal du sujet (PCA du masque alpha) -> pose canonique
    ou couchee/penchee, et stabilite de cette mesure (sujet quasi-carre = PCA
    instable, on ne redresse pas);
  - sujet tronque (l'alpha touche un bord du cadre sur une portion nette);
  - sujet plein-cadre (quasi aucune marge);
  - part de la tete estimee geometriquement (tiers superieur tres dense =
    portrait serre) — le VLM confirme, ceci n'est qu'un indice rapide.

Zero modele supplementaire: l'alpha vient de rembg (deja installe), tout le
reste est du numpy.
"""
from __future__ import annotations

import json
import sys


def _alpha(im):
    import numpy as np
    if "A" in im.getbands():
        a = np.asarray(im.getchannel("A"), dtype=np.uint8)
        if int(a.max()) - int(a.min()) > 8:
            return a
    from rembg import remove
    try:
        out = remove(im.convert("RGB"), alpha_matting=True,
                     alpha_matting_foreground_threshold=240,
                     alpha_matting_background_threshold=15,
                     alpha_matting_erode_size=5)
    except Exception:  # noqa: BLE001 - PYMATTING PLANTE: masque simple
        out = remove(im.convert("RGB"))
    import numpy as np
    return np.asarray(out.getchannel("A"), dtype=np.uint8)


def analyser(image_path: str) -> dict:
    import numpy as np
    from PIL import Image, ImageOps

    im = ImageOps.exif_transpose(Image.open(image_path))
    a = _alpha(im)
    h, w = a.shape
    m = a > 32
    n = int(m.sum())
    if n < 500:
        return {"ok": False, "error": "sujet introuvable (alpha vide)"}

    ys, xs = np.nonzero(m)
    # --- PCA de l'axe principal ---
    pts = np.stack([xs - xs.mean(), ys - ys.mean()]).astype(np.float64)
    cov = pts @ pts.T / n
    val, vec = np.linalg.eigh(cov)
    # plus grande valeur propre = axe principal; angle vs la VERTICALE image
    ax = vec[:, int(np.argmax(val))]
    import math
    angle_vertical = math.degrees(math.atan2(ax[0], ax[1]))
    if angle_vertical > 90:
        angle_vertical -= 180
    if angle_vertical < -90:
        angle_vertical += 180
    allongement = float(np.sqrt(max(val) / (min(val) + 1e-9)))
    pca_stable = allongement > 1.25   # sujet quasi carre = angle sans sens

    # --- troncature: l'alpha touche-t-il les bords ? ---
    bords = {
        "haut": float(m[0, :].mean()), "bas": float(m[-1, :].mean()),
        "gauche": float(m[:, 0].mean()), "droite": float(m[:, -1].mean()),
    }
    tronque = any(v > 0.05 for v in bords.values())
    # plein cadre: la boite du sujet occupe presque toute l'image
    occupation = float((xs.max() - xs.min()) * (ys.max() - ys.min()) / (w * h))
    plein_cadre = occupation > 0.95

    # --- indice « portrait serre »: densite du tiers superieur du sujet ---
    y0, y1 = int(ys.min()), int(ys.max())
    tiers = max(1, (y1 - y0) // 3)
    haut = m[y0:y0 + tiers, :].sum() / n
    portrait_serre_indice = bool(haut > 0.45 and occupation > 0.35)

    return {
        "ok": True,
        "angle_vertical_deg": round(angle_vertical, 1),
        "pose_canonique": bool(abs(angle_vertical) <= 28.0),
        "pca_stable": pca_stable,
        "allongement": round(allongement, 2),
        "tronque": tronque, "bords": {k: round(v, 3) for k, v in bords.items()},
        "plein_cadre": plein_cadre,
        "occupation": round(occupation, 3),
        "portrait_serre_indice": portrait_serre_indice,
    }


if __name__ == "__main__":
    print(json.dumps(analyser(sys.argv[1]), ensure_ascii=False))
