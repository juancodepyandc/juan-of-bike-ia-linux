"""Où part l'émission, et vers où : lu sur l'image de référence, reporté sur le modèle reconstruit.

16/11/2026 (flacon lapin) : la brume partait du « devant à 88 % de la hauteur » — le front du lapin — alors que
la référence montrait le jet sortant de la pompe, entre les oreilles, vers la droite. Le peintre de la
référence dessine l'émission demandée (brume, fumée, vapeur, flamme, jet) ; la reconstruction n'en garde que
l'objet. L'image dit donc où est la bouche et quelle direction prend la matière :
1. l'objet est détouré (BiRefNet, comme pour la reconstruction) ;
2. le fond est un champ lisse : un polynôme de degré 2 ajusté par moindres carrés robustes sur les pixels hors
   objet (les pixels de matière émise, aberrants, sont écartés itérativement) ;
3. la matière émise est ce qui s'écarte du fond hors de l'objet ; on garde la composante connexe la plus
   lourde qui touche l'objet (une ombre portée au sol est sous l'objet et ne touche que sa base : elle est
   exclue si la matière part du haut) ;
4. la direction est l'axe du tronçon de matière proche de l'objet ; la bouche est POINTÉE par le modèle de
   vision local (qwen3-vl, ancrage en coordonnées 0-1000) : en image, un jet passe souvent DEVANT une autre
   partie de l'objet (l'oreille du lapin) et le premier contact n'est pas la source. Sans vision, la bouche est
   le sommet du cône prolongé (la largeur d'un jet croît linéairement depuis sa bouche) ;
5. report sur le modèle : la boîte de l'objet détouré correspond à la vue de face du modèle (+Z vers la caméra,
   Y en haut) ; la profondeur est celle des sommets du modèle sous le point.
Aucun sujet, aucune coordonnée n'est écrit ici : seulement des mesures sur l'image et le maillage.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image
from scipy import ndimage

COTE_ANALYSE = 384          # pixels du plus grand côté pour l'analyse (le fond et la matière sont lisses)
POINTEUR = os.environ.get("AURORA_VLM_POINTEUR", "qwen3-vl:8b-instruct")
OLLAMA = os.environ.get("OLLAMA_HOST", "http://127.0.0.1:11434").rstrip("/")
# ce que la vision doit pointer, par matière émise (vocabulaire fermé du contrat, jamais un sujet)
BOUCHE = {"brume": "the nozzle opening where the mist (spray) leaves the object",
          "vapeur": "the place where the steam rises from the object",
          "fumee": "the opening where the smoke leaves the object",
          "flamme": "the point where the flame starts (wick or burner)",
          "jet_liquide": "the spout where the liquid jet leaves the object",
          "gouttes": "the point where the drops fall from the object"}


def pointer_bouche(reference: str | Path, type_: str) -> tuple[float, float] | None:
    """La bouche de l'émission en pixels de l'image, pointée par le modèle de vision local ; None s'il ne répond pas."""
    import base64
    import io
    import json
    import urllib.request
    if type_ not in BOUCHE or not POINTEUR:
        return None
    image = Image.open(reference).convert("RGB")
    W, H = image.size
    tampon = io.BytesIO()
    image.resize((768, int(768 * H / W))).save(tampon, "PNG")
    question = (f"Locate {BOUCHE[type_]}. Answer only JSON: {{\"x\": <0-1000>, \"y\": <0-1000>}} with coordinates "
                "normalized to 0-1000, (0,0) being the top-left corner and (1000,1000) the bottom-right corner.")
    corps = {"model": POINTEUR, "prompt": question, "images": [base64.b64encode(tampon.getvalue()).decode()],
             "stream": False, "format": "json", "options": {"temperature": 0}, "keep_alive": "30s"}
    try:
        requete = urllib.request.Request(f"{OLLAMA}/api/generate", json.dumps(corps).encode(),
                                         {"Content-Type": "application/json"})
        reponse = json.load(urllib.request.urlopen(requete, timeout=180))
        point = json.loads(reponse.get("response") or "{}")
        x, y = float(point["x"]), float(point["y"])
    except Exception:
        return None
    if not (0.0 <= x <= 1000.0 and 0.0 <= y <= 1000.0):
        return None
    return x * W / 1000.0, y * H / 1000.0


def _masque_objet(image: Image.Image) -> np.ndarray:
    from rembg import new_session, remove
    masque = remove(image, session=new_session("birefnet-general"), only_mask=True)
    return np.asarray(masque, dtype=np.float32) / 255.0 > 0.5


def _fond_lisse(rgb: np.ndarray, hors_objet: np.ndarray) -> np.ndarray:
    h, w, _ = rgb.shape
    y, x = np.mgrid[0:h, 0:w].astype(np.float32)
    x, y = x / w - 0.5, y / h - 0.5
    base = np.stack([np.ones_like(x), x, y, x * x, x * y, y * y], axis=-1).reshape(-1, 6)
    cible = rgb.reshape(-1, 3)
    garde = hors_objet.reshape(-1).copy()
    coef = np.zeros((6, 3), np.float32)
    for _ in range(4):                                         # moindres carrés repondérés : la matière émise sort
        coef, *_ = np.linalg.lstsq(base[garde], cible[garde], rcond=None)
        ecart = np.abs(cible - base @ coef).sum(axis=1)
        seuil = np.quantile(ecart[garde], 0.7) * 1.5 + 1e-3
        garde = hors_objet.reshape(-1) & (ecart < seuil)
    return (base @ coef).reshape(h, w, 3)


def _sommet_du_cone(pts: np.ndarray, poids: np.ndarray, contact: np.ndarray, axe: np.ndarray,
                    objet: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Un jet s'élargit linéairement depuis sa bouche (cône d'ouverture constante) : la largeur mesurée le long de
    son axe, prolongée jusqu'à zéro, donne la bouche — même quand le jet passe DEVANT une autre partie de l'objet
    (l'oreille du lapin), là où le premier contact image n'est pas la source. L'axe est celui du tronçon proche."""
    perp = np.array([-axe[1], axe[0]])
    rel = pts - contact
    s_, t_ = rel @ axe, rel @ perp
    longueur = float(np.quantile(s_, 0.95))
    if longueur <= 4.0:
        return contact, axe
    proche = (s_ >= 0) & (s_ <= 0.45 * longueur)
    if proche.sum() > 20:                                      # axe du tronçon proche (le nuage lointain dérive)
        q = rel[proche]
        wq = poids[proche]
        m = (q * wq[:, None]).sum(axis=0) / wq.sum()
        cov = ((q - m) * wq[:, None]).T @ (q - m) / wq.sum()
        valeurs, vecteurs = np.linalg.eigh(cov)
        a = vecteurs[:, -1] * (1.0 if vecteurs[:, -1] @ axe >= 0 else -1.0)
        if a @ axe > 0.8:
            axe, perp = a, np.array([-a[1], a[0]])
            s_, t_ = rel @ axe, rel @ perp
    bornes = np.linspace(0.0, 0.45 * longueur, 10)
    centres, largeurs, decalages = [], [], []
    for a, b in zip(bornes[:-1], bornes[1:]):
        dans = (s_ >= a) & (s_ < b)
        if dans.sum() < 6:
            continue
        w = poids[dans]
        moy = float((t_[dans] * w).sum() / w.sum())
        ecart_type = float(np.sqrt(((t_[dans] - moy) ** 2 * w).sum() / w.sum()))
        centres.append(0.5 * (a + b))
        largeurs.append(ecart_type)
        decalages.append(moy)
    if len(centres) < 3:
        return contact, axe
    pente, origine = np.polyfit(centres, largeurs, 1)
    if pente <= 1e-3:
        return contact, axe
    recul = -origine / pente                                   # où la largeur s'annule (négatif : derrière le contact)
    h_objet = float(np.ptp(np.nonzero(objet)[0])) + 1.0
    recul = float(np.clip(recul, -0.25 * h_objet, 0.0))
    decalage = float(np.polyval(np.polyfit(centres, decalages, 1), recul))
    return contact + recul * axe + decalage * perp, axe


def reperer(reference: str | Path, type_: str = "brume", *, masque: np.ndarray | None = None,
            vision: bool = True) -> dict[str, Any] | None:
    """Bouche et direction de l'émission dans l'image (pixels de l'image d'origine), ou None si rien n'est vu."""
    image = Image.open(reference).convert("RGB")
    W, H = image.size
    k = COTE_ANALYSE / max(W, H)
    petite = image.resize((max(8, int(W * k)), max(8, int(H * k))), Image.LANCZOS)
    rgb = np.asarray(petite, dtype=np.float32) / 255.0
    objet = masque if masque is not None else _masque_objet(image)
    objet = np.asarray(Image.fromarray(objet.astype(np.uint8) * 255).resize(petite.size, Image.NEAREST)) > 127
    if objet.sum() < 50:
        return None
    voisinage = ndimage.binary_dilation(objet, iterations=3)
    fond = _fond_lisse(rgb, ~voisinage)
    ecart = np.abs(rgb - fond).sum(axis=-1)
    ecart = ndimage.gaussian_filter(ecart, 1.5)
    hors = ~voisinage
    bruit = np.median(np.abs(ecart[hors] - np.median(ecart[hors]))) * 1.4826 + 1e-4
    matiere = hors & (ecart > max(0.06, np.median(ecart[hors]) + 4.0 * bruit))
    etiquettes, n = ndimage.label(matiere)
    if n == 0:
        return None
    contact_zone = ndimage.binary_dilation(objet, iterations=6) & ~voisinage
    ys_o, xs_o = np.nonzero(objet)
    bas_objet = ys_o.max()
    hauteur_objet = ys_o.max() - ys_o.min() + 1
    meilleur, poids_max = None, 0.0
    for i in range(1, n + 1):
        comp = etiquettes == i
        touche = comp & contact_zone
        if not touche.any():
            continue
        yc = np.nonzero(touche)[0].mean()
        poids = float(ecart[comp].sum())
        # une ombre portée touche l'objet par sa base et s'étale au sol : elle ne porte pas l'émission
        if yc > bas_objet - 0.08 * hauteur_objet and np.nonzero(comp)[0].mean() > bas_objet - 0.1 * hauteur_objet:
            continue
        if poids > poids_max:
            meilleur, poids_max = i, poids
    if meilleur is None:
        return None
    comp = etiquettes == meilleur
    touche = comp & contact_zone
    ys, xs = np.nonzero(touche)
    contact = np.array([xs.mean(), ys.mean()])
    ys_m, xs_m = np.nonzero(comp)
    poids_m = ecart[comp]
    pts = np.stack([xs_m, ys_m], axis=1).astype(np.float64)
    centre = (pts * poids_m[:, None]).sum(axis=0) / poids_m.sum()
    axe = centre - contact
    if float(np.linalg.norm(axe)) < 2.0:
        return None
    axe /= np.linalg.norm(axe)
    sommet, axe = _sommet_du_cone(pts, poids_m, contact, axe, objet)
    x0, x1, y0, y1 = xs_o.min(), xs_o.max() + 1, ys_o.min(), ys_o.max() + 1
    bouche, source = sommet / k, "cone"
    pointe = pointer_bouche(reference, type_) if vision else None
    if pointe is not None:
        # la vision n'est crue que si elle pointe sur l'objet (ou tout contre) et en amont de la matière
        px, py = int(round(pointe[0] * k)), int(round(pointe[1] * k))
        proche = ndimage.binary_dilation(objet, iterations=max(3, int(0.03 * max(objet.shape))))
        en_amont = (np.array([pointe[0] * k, pointe[1] * k]) - centre) @ axe < 0
        if 0 <= py < proche.shape[0] and 0 <= px < proche.shape[1] and proche[py, px] and en_amont:
            bouche, source = np.asarray(pointe), "vision"
    return {"bouche_px": np.round(bouche, 1).tolist(), "source_bouche": source,
            "direction_image": np.round(axe, 4).tolist(),
            "boite_objet_px": [round(float(v) / k, 1) for v in (x0, y0, x1, y1)],
            "part_image": round(float(comp.mean()), 4), "contraste": round(float(poids_m.mean()), 4),
            "taille_image": [W, H]}


def vers_modele(reperage: dict[str, Any], sommets: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Bouche et direction en coordonnées du modèle (vue de face : +X à droite, +Y en haut, +Z vers la caméra)."""
    mn, mx = sommets.min(axis=0), sommets.max(axis=0)
    x0, y0, x1, y1 = reperage["boite_objet_px"]
    u, v = reperage["bouche_px"]
    sx = (mx[0] - mn[0]) / max(1e-6, x1 - x0)
    sy = (mx[1] - mn[1]) / max(1e-6, y1 - y0)
    x = mn[0] + (u - x0) * sx
    y = mx[1] - (v - y0) * sy
    taille = float((mx - mn).max())
    pres = np.linalg.norm(sommets[:, :2] - np.array([x, y]), axis=1)
    rayon = 0.03 * taille
    proches = sommets[pres < rayon]
    if len(proches) < 3:                                       # la bouche est au bord : le plus proche sommet
        proches = sommets[np.argsort(pres)[:32]]
    z = float(np.median(proches[:, 2]))
    du, dv = reperage["direction_image"]
    direction = np.array([du * sx, -dv * sy, 0.0])
    direction /= np.linalg.norm(direction) or 1.0
    bouche = np.array([x, y, z])
    # la matière sort de la surface de l'émetteur tournée vers le jet : la bouche y est portée
    avance = (proches - bouche) @ direction
    bouche = bouche + max(0.0, float(np.quantile(avance, 0.9))) * direction
    return bouche, direction
