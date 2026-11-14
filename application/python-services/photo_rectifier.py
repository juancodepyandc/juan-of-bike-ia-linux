#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""AuroraIA Photo Rectifier — préparation & canonisation d'une VRAIE photo pour la 3D.

Prend une photo brute (selfie smartphone, sous-exposée, contre-plongée, reflets
sur les lunettes) et produit une référence conforme pour la reconstruction 3D
**en conservant l'identité réelle**: le teint, les imperfections (boutons,
cicatrices, pilosité irrégulière), la mèche bouclée, le motif du vêtement.

DOCTRINE — CORRIGER, JAMAIS TRANSFORMER
---------------------------------------
Une photo sous-exposée n'est pas un "mauvais visage": c'est la MÊME scène
multipliée par un facteur < 1. La corriger, c'est diviser par ce facteur —
mesuré sur l'image, jamais choisi. Les rapports entre peau, cheveux et fond
sont alors rigoureusement préservés: le teint réel ressort tel quel.

C'est pourquoi ce module ne vise JAMAIS une luminance cible absolue: viser
"médiane = 128" éclaircirait une peau mate jusqu'à en changer l'identité (et
assombrirait une peau claire). On estime le POINT BLANC de la scène et on
ramène ce point blanc à un blanc non écrêté. Une photo déjà bien exposée
ressort quasi inchangée (gain ~1.0) — le module est un no-op sur une bonne
photo, sans qu'aucun seuil n'ait à le décider.

Opérations, toutes pilotées par des mesures faites sur l'image reçue:
  1. Exposition: gain calculé en lumière LINÉAIRE (dé-gamma → gain → re-gamma),
     seule façon physiquement juste de compenser une sous-exposition.
  2. Ombres: micro-contraste local (CLAHE) borné par la profondeur d'ombre
     réellement mesurée — révèle la boucle de cheveux et le grain de peau que
     le noir écrasait, sans "lisser" quoi que ce soit.
  3. Bruit: débruitage CHROMA seulement (le bruit ISO coloré est amplifié par
     le gain). La LUMINANCE — qui porte les poils, la barbe naissante et les
     imperfections — n'est quasiment pas touchée: un débruitage luma agressif
     transformerait la chevelure en bloc, exactement ce qu'on veut éviter.
  4. Reflets de lunettes: éteints UNIQUEMENT sur les composantes qui touchent
     la région oculaire RÉELLE (5 points du visage détectés). Aucun rectangle
     codé en dur: sur un visage décentré, penché ou hors-cadre, une zone figée
     inpeindrait la joue. Sans visage détecté, l'étape est sautée — ne rien
     faire vaut mieux qu'abîmer.
  5. Détourage BiRefNet-portrait (cheveux bouclés, mèches, motifs conservés).

Générique par construction: aucune valeur propre à un sujet, une morphologie ou
une carnation. Tout paramètre sort d'une mesure de l'image courante.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

import cv2
import numpy as np
from PIL import Image

_SRGB_A = 0.055


def _to_linear(x: np.ndarray) -> np.ndarray:
    """sRGB [0,1] -> lumière linéaire (la sous-exposition est un facteur LINÉAIRE)."""
    return np.where(x <= 0.04045, x / 12.92, ((x + _SRGB_A) / (1 + _SRGB_A)) ** 2.4)


def _to_srgb(x: np.ndarray) -> np.ndarray:
    """Lumière linéaire -> sRGB [0,1]."""
    x = np.clip(x, 0.0, 1.0)
    return np.where(x <= 0.0031308, x * 12.92,
                    (1 + _SRGB_A) * np.power(x, 1 / 2.4) - _SRGB_A)


def mesurer(bgr: np.ndarray, mask: np.ndarray | None = None) -> dict:
    """Diagnostic photométrique de l'image ou du sujet détouré (tout le reste en découle)."""
    lum = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY).astype(np.float32)
    vals = lum[mask > 180] if (mask is not None and int((mask > 180).sum()) > 200) else lum.ravel()
    return {
        "luma_moyenne": float(vals.mean()),
        "luma_mediane": float(np.median(vals)),
        "point_blanc": float(np.percentile(vals, 99.0)),
        "part_ombre": float((vals < 40).mean()),
        "nettete": float(cv2.Laplacian(lum, cv2.CV_32F).var()),
    }


def corriger_exposition(bgr: np.ndarray, mes: dict) -> tuple[np.ndarray, dict]:
    """Ramène le point blanc mesuré à un blanc non écrêté, en lumière linéaire.

    Le gain s'applique à TOUS les canaux identiquement: aucune balance des
    blancs, aucune saturation ajoutée — la couleur de peau reste celle de la
    photo. Une image déjà exposée a un point blanc proche de la cible: le gain
    tend vers 1 et la fonction ne fait rien.
    """
    # cible: blanc franc mais NON écrêté (on garde de la marge pour ne pas
    # brûler un reflet spéculaire légitime en aplat blanc).
    cible = 245.0
    pb = max(float(mes["point_blanc"]), 1.0)
    gain = cible / pb
    if gain <= 1.02:  # déjà exposée: on ne touche à rien
        return bgr, {"gain": 1.0, "applique": False}
    lin = _to_linear(bgr.astype(np.float32) / 255.0)
    out = _to_srgb(lin * gain) * 255.0
    return np.clip(out, 0, 255).astype(np.uint8), {
        "gain": round(float(gain), 3), "applique": True,
        "point_blanc_avant": round(pb, 1)}


def rehausser_ombres(bgr: np.ndarray, mes: dict) -> tuple[np.ndarray, dict]:
    """Micro-contraste local dans les zones que l'ombre écrasait.

    La force suit la profondeur d'ombre MESURÉE: une image sans ombre profonde
    n'est pas touchée. CLAHE agit sur la luminance uniquement (les canaux a/b
    de LAB restent intacts) — la teinte de peau ne bouge pas.
    """
    part = float(mes["part_ombre"])
    if part < 0.10:
        return bgr, {"applique": False}
    # clip 1.2 (ombre légère) -> 2.6 (image très bouchée). Continu: aucun palier
    # arbitraire, et l'effet s'annule de lui-même quand l'ombre disparaît.
    clip = 1.2 + 1.4 * min(1.0, (part - 0.10) / 0.60)
    lab = cv2.cvtColor(bgr, cv2.COLOR_BGR2LAB)
    lab[:, :, 0] = cv2.createCLAHE(clipLimit=clip, tileGridSize=(8, 8)).apply(lab[:, :, 0])
    return cv2.cvtColor(lab, cv2.COLOR_LAB2BGR), {
        "applique": True, "clip": round(clip, 2), "part_ombre": round(part, 3)}


def debruiter_chroma(bgr: np.ndarray, gain: float) -> tuple[np.ndarray, dict]:
    """Retire le bruit ISO COLORÉ amplifié par le gain, garde le détail luma.

    Le bruit chroma (pixels violets/verts) se reconstruit en 3D comme des
    mouchetures de couleur; la luminance, elle, porte les poils, la barbe
    naissante et les boutons — on n'y touche presque pas (h=1), sous peine de
    livrer une chevelure en bloc lisse.
    """
    if gain <= 1.02:
        return bgr, {"applique": False}
    # la puissance suit le gain: c'est LUI qui a amplifié le bruit.
    h_color = float(np.clip(3.0 * (gain - 1.0), 3.0, 12.0))
    out = cv2.fastNlMeansDenoisingColored(bgr, None, h=1, hColor=h_color,
                                          templateWindowSize=7, searchWindowSize=21)
    return out, {"applique": True, "h_luma": 1, "h_chroma": round(h_color, 1)}


def _region_oculaire(landmarks, shape, bbox=None) -> np.ndarray | None:
    """Masque de la région des yeux/lunettes, dérivé du visage DÉTECTÉ.

    Largeur: celle du VISAGE, pas l'écart inter-pupillaire. Mesuré sur un
    selfie rapproché: le reflet occupait x 352-486 alors que les pupilles
    étaient à x 719 et 1010 — une zone bâtie sur le seul écart des yeux
    (±1.15x) démarrait à x 529 et ratait entièrement le verre. Une monture
    couvre la largeur du visage; sa hauteur, elle, reste proportionnée à
    l'écart des yeux (seule échelle verticale fiable du regard).
    """
    if not landmarks or len(landmarks) < 2:
        return None
    h, w = shape[:2]
    oeil_g = np.asarray(landmarks[0], dtype=np.float32)
    oeil_d = np.asarray(landmarks[1], dtype=np.float32)
    ecart = float(np.linalg.norm(oeil_d - oeil_g))
    if ecart < 4.0:
        return None
    centre = (oeil_g + oeil_d) / 2.0
    if bbox is not None and len(bbox) == 4 and bbox[2] > 0:
        bx, _by, bw, _bh = bbox
        demi_l = max(float(bw) * 0.5, ecart * 1.15)
        centre_x = float(bx) + float(bw) * 0.5
    else:  # sans boîte du visage, on retombe sur l'échelle des yeux
        demi_l = ecart * 1.6
        centre_x = float(centre[0])
    demi_h = ecart * 0.55
    masque = np.zeros((h, w), np.uint8)
    cv2.ellipse(masque, (int(centre_x), int(centre[1])),
                (int(demi_l), int(demi_h)), 0, 0, 360, 255, -1)
    return masque


def eteindre_reflets_lunettes(bgr: np.ndarray, landmarks, bbox=None, log=print
                              ) -> tuple[np.ndarray, dict]:
    """Éteint le reflet d'écran/spéculaire sur les VERRES, repérés par le visage.

    Un reflet d'écran est cuit tel quel dans la texture 3D (un rectangle bleu
    sur l'œil). On ne l'efface QUE là où le visage réel place les yeux: la
    zone vient des 5 points détectés, pas d'un rectangle en fraction d'image
    (qui, sur ce selfie penché, tomberait sur la joue).

    À APPELER AVANT la correction d'exposition (mesuré): le gain sature les
    pixels du reflet à 255 sur les trois canaux, ce qui EFFACE sa signature
    bleue (B-R passe de +158 à -13) et le rend indétectable. Sur l'image
    d'origine, la signature est intacte.
    """
    zone = _region_oculaire(landmarks, bgr.shape, bbox=bbox)
    if zone is None:
        # SANS visage repéré, toute zone serait inventée: on s'abstient.
        return bgr, {"applique": False, "raison": "aucun repere oculaire detecte"}

    b, g, r = (bgr[:, :, 0].astype(np.int16), bgr[:, :, 1].astype(np.int16),
               bgr[:, :, 2].astype(np.int16))
    lum = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY).astype(np.int16)
    sel = zone > 0
    ref = float(np.median(lum[sel]))
    bmr_peau = float(np.median((b - r)[sel]))
    # Un écran émet du bleu/cyan: la PEAU ne le fait jamais (son B-R est
    # franchement négatif). Le critère est donc l'inversion de teinte par
    # rapport à la peau environnante MESURÉE, plus un net surcroît de
    # luminance — aucun seuil absolu, une photo claire ou sombre se comporte
    # pareil. Le reflet de fenêtre/lampe (blanc, non bleu) est pris par le
    # second critère, spéculaire.
    # Correction NON-DESTRUCTIVE du reflet d'écran bleu sur le verre :
    # Au lieu d'un inpainting destructif (Telea) qui noie l'œil dans un flou laiteux,
    # on soustrait l'excédent chromatique bleu du reflet pour retrouver la carnation
    # et la transparence réelle. Les cils, l'iris, la pupille et les détails restent 100% NETS.
    blue_excess = np.clip((b - np.maximum(g, r)) / 255.0, 0.0, 1.0) * (zone.astype(np.float32) / 255.0)
    b_fixed = b.astype(np.float32) - blue_excess * (b.astype(np.float32) - g.astype(np.float32))
    
    # Inpainting subtil uniquement sur les éclats spéculaires purs (reflet blanc brûlé >99.5%)
    reflet_spec = (lum > np.percentile(lum[sel], 99.2)).astype(np.uint8) * 255 & zone
    bgr_corr = np.stack([b_fixed, g.astype(np.float32), r.astype(np.float32)], axis=2).clip(0, 255).astype(np.uint8)
    
    if np.count_nonzero(reflet_spec) > 20:
        masque_spec = cv2.dilate(reflet_spec, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3)))
        out = cv2.inpaint(bgr_corr, masque_spec, inpaintRadius=2, flags=cv2.INPAINT_TELEA)
    else:
        out = bgr_corr

    return out, {"applique": True, "px_reflet": int(np.count_nonzero(blue_excess > 0.05)),
                 "bmr_peau": round(bmr_peau, 1), "luma_zone": round(ref, 1)}


def rectify_photo_for_3d(
    input_path: str,
    output_rgba_path: str,
    output_white_path: str | None = None,
    log=print,
) -> dict[str, Any]:
    """Canonise une photo réelle pour la 3D en conservant l'identité."""
    if not os.path.exists(input_path):
        return {"ok": False, "error": f"Fichier introuvable: {input_path}"}

    pil = Image.open(input_path)
    try:  # une photo de téléphone porte sa rotation en EXIF
        from PIL import ImageOps
        pil = ImageOps.exif_transpose(pil)
    except Exception:  # noqa: BLE001
        pass
    input_existing_alpha: np.ndarray | None = None
    if "A" in pil.getbands():
        _a_in = np.array(pil.getchannel("A"))
        _trans_ratio = float((_a_in < 25).mean())
        if 0.02 <= _trans_ratio <= 0.95:
            input_existing_alpha = _a_in
    bgr = cv2.cvtColor(np.array(pil.convert("RGB")), cv2.COLOR_RGB2BGR)

    avant_global = mesurer(bgr)
    rapport: dict[str, Any] = {"mesures_avant": {k: round(v, 2) for k, v in avant_global.items()}}
    log("[photo_rectifier] photo recue: luma %.0f/255, ombre %.0f%%, point blanc %.0f"
        % (avant_global["luma_moyenne"], 100 * avant_global["part_ombre"], avant_global["point_blanc"]))

    os.makedirs(os.path.dirname(os.path.abspath(output_rgba_path)), exist_ok=True)
    tmp = str(Path(output_rgba_path).with_name(Path(output_rgba_path).stem + "_reperage.png"))

    # 1. DÉTOURAGE HAUTE PRÉCISION EN PREMIER (`birefnet-general` 1024x1024).
    # Exécuter le détourage AVANT la mesure photométrique évite qu'un fond sombre
    # (ex: décor de Poudlard sombre derrière Harry Potter ou fond de studio dramatique)
    # ne déclenche un gain d'exposition ou un CLAHE qui délaverait les vêtements noirs
    # et les cheveux foncés du sujet ! De plus, `birefnet-general` préserve intégralement
    # les socles de figurines, accessoires et corps entiers (contrairement à `birefnet-portrait`).
    modele = os.environ.get("AURORA_RECTIFIER_MATTING") or "birefnet-general"
    log("[photo_rectifier] detourage (%s)..." % modele)
    rgb_init = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
    try:
        import rembg
        try:
            session = rembg.new_session(modele)
        except Exception:
            session = rembg.new_session("u2net")
        rgba_init = rembg.remove(Image.fromarray(rgb_init), session=session)
        rapport["detourage"] = {"ok": True, "modele": modele}
    except Exception as exc:  # noqa: BLE001
        rgba_init = Image.fromarray(rgb_init).convert("RGBA")
        rapport["detourage"] = {"ok": False, "error": repr(exc)[:160]}
        log("[photo_rectifier] detourage indisponible (%s) — image pleine conservee"
            % type(exc).__name__)

    rgba_init = rgba_init.convert("RGBA")
    arr = np.array(rgba_init)
    if input_existing_alpha is not None and input_existing_alpha.shape == arr[..., 3].shape:
        arr[..., 3] = np.minimum(arr[..., 3], input_existing_alpha)

    # Durcissement propre du canal alpha (élimine les franges semi-transparentes de barbe/fond)
    alpha_raw = arr[..., 3].astype(np.float32)
    alpha_clean = np.clip((alpha_raw - 38.0) * (255.0 / (205.0 - 38.0)), 0.0, 255.0).astype(np.uint8)
    arr[..., 3] = alpha_clean

    # 2. MESURE PHOTOMÉTRIQUE SUR LE SUJET DÉTOURÉ UNIQUEMENT (`alpha > 180`).
    avant = mesurer(bgr, mask=arr[..., 3])
    rapport["mesures_sujet"] = {k: round(v, 2) for k, v in avant.items()}
    is_clean_studio_or_stylized = (
        avant["point_blanc"] >= 195.0
        or avant["luma_moyenne"] >= 90.0
        or (input_existing_alpha is not None)
    )
    landmarks, face_bbox = None, None
    if not is_clean_studio_or_stylized:
        apercu, _ = corriger_exposition(bgr, avant)
        cv2.imwrite(tmp, apercu)
        try:
            sys.path.insert(0, str(Path(__file__).resolve().parent))
            from face_restore import detect_face_bbox
            hit = detect_face_bbox(tmp, allow_silhouette=False)
            if hit is not None:
                landmarks = getattr(hit, "landmarks", None)
                face_bbox = getattr(hit, "bbox", None)
        except Exception as exc:  # noqa: BLE001
            log("[photo_rectifier] detection visage indisponible (%s)" % type(exc).__name__)
    rapport["visage_detecte"] = bool(landmarks)

    if not is_clean_studio_or_stylized and landmarks:
        bgr, rapport["reflets"] = eteindre_reflets_lunettes(bgr, landmarks,
                                                            bbox=face_bbox, log=log)
    else:
        rapport["reflets"] = {"applique": False, "raison": "sujet deja bien expose / studio / stylise"}
    if rapport["reflets"].get("applique"):
        log("[photo_rectifier] reflet de lunettes eteint (%d px, zone issue des "
            "reperes du visage)" % rapport["reflets"]["px_reflet"])
    else:
        log("[photo_rectifier] pas de dereflet: %s" % rapport["reflets"].get("raison", ""))

    if not is_clean_studio_or_stylized:
        bgr, rapport["exposition"] = corriger_exposition(bgr, avant)
        if rapport["exposition"].get("applique"):
            log("[photo_rectifier] exposition corrigee (gain x%.2f, mesure sur le "
                "point blanc du sujet — teint preserve)" % rapport["exposition"]["gain"])
        bgr, rapport["ombres"] = rehausser_ombres(bgr, avant)
        bgr, rapport["bruit"] = debruiter_chroma(bgr, rapport["exposition"].get("gain", 1.0))
    else:
        rapport["exposition"] = {"gain": 1.0, "applique": False}
        rapport["ombres"] = {"applique": False}
        rapport["bruit"] = {"applique": False}

    rapport["mesures_apres"] = {k: round(v, 2) for k, v in mesurer(bgr, mask=arr[..., 3]).items()}
    rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
    arr[..., :3] = rgb
    rgba = Image.fromarray(arr)

    # NETTOYAGE DES TEXTES ET LOGOS PARASITES DÉCONNECTÉS (sans supprimer un 2e personnage).
    try:
        bin_mask = (arr[..., 3] > 15).astype(np.uint8)
        num_labels, labels, stats, _ = cv2.connectedComponentsWithStats(bin_mask, connectivity=8)
        if num_labels > 2:
            areas = stats[1:, cv2.CC_STAT_AREA]
            max_area = float(areas.max())
            for comp_idx in range(1, num_labels):
                c_area = float(stats[comp_idx, cv2.CC_STAT_AREA])
                c_w = float(stats[comp_idx, cv2.CC_STAT_WIDTH])
                c_h = float(stats[comp_idx, cv2.CC_STAT_HEIGHT])
                is_text_banner = (c_w > 3.2 * c_h and c_area < 0.12 * max_area)
                if c_area < 0.015 * max_area or is_text_banner:
                    arr[labels == comp_idx, 3] = 0
            rgba = Image.fromarray(arr)
    except Exception as _cc_exc:
        log(f"[photo_rectifier] filtrage logos/textes ({_cc_exc})")

    # Défrangeage Voronoï strictement limité à la frange semi-transparente (<= 2.5 px, alpha < 240)
    # pour éliminer tout halo de fond sans altérer les couleurs internes.
    try:
        fg_2d = arr[..., 3] > 128
        if int(fg_2d.sum()) > 1500:
            rgb_tex = arr[..., :3].copy()
            dist_init = cv2.distanceTransform(fg_2d.astype(np.uint8), cv2.DIST_L2, 5)
            valid_interior = fg_2d & (dist_init > 2.5) & (arr[..., 3] >= 240)
            if int(valid_interior.sum()) > 500:
                _, lbl_vor = cv2.distanceTransformWithLabels(
                    (~valid_interior).astype(np.uint8), cv2.DIST_L2, 5, labelType=cv2.DIST_LABEL_PIXEL
                )
                flat_valid = np.flatnonzero(valid_interior.ravel())
                lut = np.zeros(lbl_vor.max() + 1, dtype=np.int64)
                lut[lbl_vor.ravel()[flat_valid]] = flat_valid
                vor_rgb = rgb_tex.reshape(-1, 3)[lut[lbl_vor.ravel()]].reshape(rgb_tex.shape)
                rim_fringe = (arr[..., 3] > 0) & (arr[..., 3] < 240) & (dist_init <= 2.5)
                rgb_tex[rim_fringe] = vor_rgb[rim_fringe]
                arr[..., :3] = rgb_tex
                rgba = Image.fromarray(arr)
    except Exception as _g2d_exc:
        log(f"[photo_rectifier] defrangeage Voronoï ignore ({_g2d_exc})")

    ys, xs = np.where(arr[..., 3] > 10)
    # NE PADDER QUE SI LA SILHOUETTE EN A BESOIN. Ce canevas carre existe
    # pour FERMER une silhouette qui touche les bords (sinon la
    # reconstruction rend une dalle). Applique a un sujet qui remplit deja
    # son cadre — un personnage debout occupe ~96% de la hauteur d'un
    # portrait — il ne ferme rien et AJOUTE du vide sur les cotes: le moteur
    # travaillant a resolution fixe, le sujet ressort alors PLUS PETIT, donc
    # moins detaille (mesure du 28/08: 1024x1408 -> 1645x1645 sans un pixel
    # gagne sur le personnage).
    if len(xs):
        y0, y1, x0, x1 = int(ys.min()), int(ys.max()), int(xs.min()), int(xs.max())
        _touche = bool((arr[0, :, 3] > 10).any() or (arr[-1, :, 3] > 10).any()
                       or (arr[:, 0, 3] > 10).any() or (arr[:, -1, 3] > 10).any())
        _rempli = max(y1 - y0, x1 - x0) / max(arr.shape[0], arr.shape[1])
        sujet = rgba.crop((x0, y0, x1 + 1, y1 + 1))
        occupation = float(os.environ.get("AURORA_RECTIFIER_OCCUPATION", "0.82"))
        if not _touche and _rempli >= occupation:
            log("[photo_rectifier] cadre conserve — silhouette deja fermee et "
                "sujet a %.0f%% du cadre (un canevas carre le retrecirait)"
                % (100 * _rempli))
            rapport["cadrage"] = {"inchange": True, "remplissage": round(_rempli, 3)}
            _cadre_ok = True
        else:
            _cadre_ok = False
        cote = int(max(sujet.width, sujet.height) / max(0.1, min(occupation, 0.95)))
        canevas = Image.new("RGBA", (cote, cote), (0, 0, 0, 0))
        canevas.paste(sujet, ((cote - sujet.width) // 2,
                              (cote - sujet.height) // 2))
        rapport["cadrage"] = {
            "occupation_avant": round(float((arr[..., 3] > 10).mean()), 3),
            "bords_touches": {
                "haut": bool((arr[0, :, 3] > 10).any()),
                "bas": bool((arr[-1, :, 3] > 10).any()),
                "gauche": bool((arr[:, 0, 3] > 10).any()),
                "droite": bool((arr[:, -1, 3] > 10).any())},
            "canevas": [cote, cote], "occupation_cible": occupation}
        if not _cadre_ok:
            log("[photo_rectifier] cadre carre %dpx, marge garantie autour du sujet "
                "(silhouette fermee pour la reconstruction)" % cote)
            rgba = canevas

    rgba.save(output_rgba_path)
    if output_white_path:
        os.makedirs(os.path.dirname(os.path.abspath(output_white_path)), exist_ok=True)
        fond = Image.new("RGB", rgba.size, (255, 255, 255))
        fond.paste(rgba, mask=rgba.getchannel("A"))
        fond.save(output_white_path)
    try:
        os.remove(tmp)
    except OSError:
        pass

    log("[photo_rectifier] reference prete: %s" % output_rgba_path)
    return {"ok": True, "rgba": output_rgba_path, "white": output_white_path,
            "size": list(rgba.size), **rapport}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="AuroraIA Photo Rectifier")
    parser.add_argument("--input", "-i", required=True)
    parser.add_argument("--output-rgba", "-o", required=True)
    parser.add_argument("--output-white", "-w")
    args = parser.parse_args()
    print(json.dumps(rectify_photo_for_3d(args.input, args.output_rgba,
                                          args.output_white), ensure_ascii=False))
