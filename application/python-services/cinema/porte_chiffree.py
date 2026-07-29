#!/usr/bin/env python3
"""Porte de qualite CHIFFREE : mesurer avant de juger.

POURQUOI ELLE EXISTE
--------------------
Le juge VLM est bruite. Mesure sur un film reel : le meme plan, images
identiques, note act=7, puis 6, puis 10 (accepte), puis 5 en post-audio — ce qui
a fait echouer le film entier. Deux causes distinctes :
  - la temperature 0.1 SANS graine : trop chaude pour etre reproductible, trop
    froide pour qu'un vote apporte du signal ;
  - le repli silencieux vers un modele plus petit qui, mesure, renvoie du VIDE a
    chaque appel.
On ne corrige pas un juge bruite en le relancant : on le remplace, pour tout ce
qui est mesurable, par des CHIFFRES.

CE QUE CETTE PORTE MESURE, ET CE QU'ELLE NE MESURE PAS
------------------------------------------------------
Elle mesure ce qui a une definition objective :
  - la CONSTANCE : le plan 9 appartient-il au meme film que le plan 1 ?
    -> cosinus DINOv2 contre la signature MEDIANE du film.
    Piege evite : comparer a un PORTRAIT studio ne mesure PAS l'identite mais
    le cadrage — mesure sur quatre plans reels, un personnage parfaitement
    reconnaissable obtenait 0,17 a 0,35, parce que l'embedding encode toute
    l'image et que le decor y pese plus que le sujet.
  - la DERIVE INTERNE : la derniere image ressemble-t-elle encore a la premiere ?
    -> le meme embedding, debut contre fin du plan.
  - la COULEUR : le plan est-il dans la lumiere du film ?
    -> delta-E CIE76 en Lab contre la mediane des plans deja acceptes.
  - le MOUVEMENT : le plan bouge-t-il vraiment ?
    -> amplitude inter-images ; une photo sonorisee mesure < 1.

Elle ne mesure PAS ce qui demande du sens : « l'action demandee a-t-elle lieu »,
« le decor est-il le bon ». Ces questions restent au VLM — mais en second, et
seulement sur les plans que les chiffres ont laisses passer. Un juge qui se
prononce sur cinq criteres se trompe cinq fois plus souvent qu'un juge qui se
prononce sur un seul.

Usage :
  python porte_chiffree.py --check
  python porte_chiffree.py --mesurer plan.mp4 --reference natsu.png
  python porte_chiffree.py --film plan1.mp4 plan2.mp4 plan3.mp4
"""

import argparse
import json
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
WORKSPACE = HERE.parent.parent

# Seuils. Volontairement permissifs : cette porte doit attraper les ruptures
# franches (un autre personnage, un plan fige, une teinte qui saute), pas
# arbitrer des nuances — c'est le role du juge VLM, ensuite.
# Constance : chaque plan contre la signature MEDIANE du film. Ce n'est pas une
# comparaison a un portrait — mesure faite : un plan en situation obtient 0,17 a
# 0,35 face a un portrait studio alors que le personnage est parfait. L'embedding
# encode toute l'image, donc le decor pese plus que le sujet.
SEUIL_CONSTANCE = 0.45
SEUIL_DERIVE_INTERNE = 0.60  # cosinus entre premiere et derniere image du plan
SEUIL_DELTA_E = 18.0         # delta-E CIE76 contre la mediane du film
SEUIL_MOUVEMENT = 1.0        # amplitude inter-images (0,58 = fige, 2,5 = S2V)

_MODELE = {"extracteur": None}


def emit(stage: str, detail: str = ""):
    print(f"PROGRESS:{stage}:{detail}", flush=True)


def _extracteur():
    """DINOv2-base, sur CPU. 0,35 Go, et surtout : il ne dispute pas la carte.

    Le choix du CPU n'est pas un compromis mais une condition : la porte tourne
    entre deux plans, exactement quand le generateur veut la VRAM. Une porte qui
    provoque un OOM ne protege rien.
    """
    if _MODELE["extracteur"] is not None:
        return _MODELE["extracteur"]
    try:
        import torch
        from transformers import AutoImageProcessor, AutoModel
        nom = os.environ.get("AURORA_PORTE_MODELE", "facebook/dinov2-base")
        proc = AutoImageProcessor.from_pretrained(nom)
        modele = AutoModel.from_pretrained(nom).eval()
        _MODELE["extracteur"] = (proc, modele, torch)
    except Exception as exc:
        emit("porte_warn", f"DINOv2 indisponible: {str(exc)[:120]}")
        _MODELE["extracteur"] = False
    return _MODELE["extracteur"]


def _images_du_plan(video_path: str, combien: int = 5):
    """Images reparties dans le plan, en RGB."""
    try:
        import cv2
    except Exception:
        return []
    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        return []
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    if total < 1:
        cap.release()
        return []
    idxs = [int(total * i / max(1, combien - 1)) for i in range(combien)]
    idxs = [min(max(0, i), total - 1) for i in idxs]
    out = []
    for i in idxs:
        cap.set(cv2.CAP_PROP_POS_FRAMES, i)
        ok, frame = cap.read()
        if ok and frame is not None:
            out.append(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
    cap.release()
    return out


def empreinte_visuelle(image_rgb):
    """Embedding DINOv2 normalise d'une image, ou None."""
    ext = _extracteur()
    if not ext:
        return None
    proc, modele, torch = ext
    try:
        from PIL import Image
        import numpy as np
        pil = Image.fromarray(image_rgb)
        entrees = proc(images=pil, return_tensors="pt")
        with torch.no_grad():
            sortie = modele(**entrees)
        v = sortie.last_hidden_state[:, 0].squeeze().numpy()
        return v / (float((v ** 2).sum()) ** 0.5 + 1e-8)
    except Exception:
        return None


def similarite(a, b) -> float:
    if a is None or b is None:
        return -1.0
    return float((a * b).sum())


def couleur_lab(image_rgb):
    """Moyenne Lab de l'image — la base du delta-E."""
    try:
        import cv2
        import numpy as np
        lab = cv2.cvtColor(image_rgb, cv2.COLOR_RGB2LAB).astype("float32")
        return np.array([lab[..., 0].mean(), lab[..., 1].mean(),
                         lab[..., 2].mean()])
    except Exception:
        return None


def delta_e(lab_a, lab_b) -> float:
    """Delta-E CIE76 : distance euclidienne en Lab.

    Suffisant ici : on cherche une rupture visible entre deux plans, pas une
    tolerance d'imprimerie. Un delta-E de 2,3 est le seuil de perception ; a 18
    on est tres au-dela d'un ecart discutable.
    """
    if lab_a is None or lab_b is None:
        return -1.0
    return float((((lab_a - lab_b) ** 2).sum()) ** 0.5)


def amplitude_mouvement(video_path: str, echantillons: int = 24):
    """Amplitude moyenne entre images consecutives. < 1 = photo sonorisee."""
    try:
        import cv2
        import numpy as np
    except Exception:
        return None
    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        return None
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    if total < 2:
        cap.release()
        return None
    pas = max(1, total // max(2, echantillons))
    prec, ecarts = None, []
    for i in range(0, total, pas):
        cap.set(cv2.CAP_PROP_POS_FRAMES, i)
        ok, frame = cap.read()
        if not ok or frame is None:
            continue
        gris = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY).astype("float32")
        if prec is not None:
            ecarts.append(float(np.abs(gris - prec).mean()))
        prec = gris
    cap.release()
    return round(sum(ecarts) / len(ecarts), 2) if ecarts else None


def mesurer_plan(video_path: str, reference_png: str = "",
                 lab_film=None, empreinte_film=None) -> dict:
    """Toutes les mesures d'un plan, sans aucun jugement.

    `graded` distingue « mesure et conforme » de « pas mesurable » — une porte
    qui ne peut pas mesurer ne doit jamais fabriquer un verdict, dans un sens
    comme dans l'autre.
    """
    images = _images_du_plan(video_path)
    if not images:
        return {"ok": False, "graded": False,
                "raison": f"plan illisible: {video_path}"}

    mesures = {"plan": os.path.basename(str(video_path))}
    defauts = []

    mesures["mouvement"] = amplitude_mouvement(video_path)
    if mesures["mouvement"] is not None and mesures["mouvement"] < SEUIL_MOUVEMENT:
        defauts.append(f"plan quasi fige ({mesures['mouvement']})")

    emp_debut = empreinte_visuelle(images[0])
    emp_fin = empreinte_visuelle(images[-1])
    if emp_debut is not None and emp_fin is not None:
        d = similarite(emp_debut, emp_fin)
        mesures["derive_interne"] = round(d, 3)
        if d < SEUIL_DERIVE_INTERNE:
            defauts.append(f"le plan derive sur sa duree ({d:.2f})")

    # v94b — CE CRITERE MESURAIT LE CADRAGE, PAS L'IDENTITE.
    # Compare a un PORTRAIT STUDIO sur fond uni, un plan en situation obtenait
    # 0,17 a 0,35 de similarite DINOv2 — mesure sur quatre plans reels dont le
    # personnage etait pourtant parfaitement reconnaissable. L'embedding CLS
    # encode TOUTE l'image : le decor, l'echelle et la composition pesent plus
    # que le sujet. Le seuil aurait donc refuse des plans corrects et laisse
    # passer un mauvais plan bien cadre.
    # Ce qui compte pour « aucune coherence entre les scenes », c'est la
    # constance d'un plan a l'autre : on compare donc chaque plan a la
    # SIGNATURE MEDIANE DU FILM, calculee sur les plans eux-memes.
    if empreinte_film is not None:
        sims = [similarite(empreinte_film, empreinte_visuelle(im))
                for im in images]
        sims = [s for s in sims if s >= 0]
        if sims:
            mesures["constance"] = round(sum(sims) / len(sims), 3)
            if mesures["constance"] < SEUIL_CONSTANCE:
                defauts.append(f"plan visuellement etranger au reste du film "
                               f"({mesures['constance']:.2f})")

    lab_plan = couleur_lab(images[len(images) // 2])
    if lab_plan is not None:
        mesures["lab"] = [round(float(x), 1) for x in lab_plan]
        if lab_film is not None:
            de = delta_e(lab_plan, lab_film)
            mesures["delta_e"] = round(de, 1)
            if de > SEUIL_DELTA_E:
                defauts.append(f"couleur hors du film (delta-E {de:.0f})")

    mesures["ok"] = not defauts
    mesures["graded"] = True
    mesures["defauts"] = defauts
    return mesures


def lumiere_du_film(videos: list):
    """Lab MEDIAN du film : son centre de gravite colorimetrique.

    La mediane et non la moyenne — si un plan sur quatre part dans une
    dominante, la moyenne le suit a moitie et contamine le verdict des trois
    autres.
    """
    try:
        import numpy as np
    except Exception:
        return None
    labs = []
    for v in videos:
        ims = _images_du_plan(v, combien=3)
        for im in ims:
            lab = couleur_lab(im)
            if lab is not None:
                labs.append(lab)
    return np.median(labs, axis=0) if labs else None


def signature_du_film(videos: list):
    """Empreinte visuelle MEDIANE du film — son apparence de reference.

    Mediane et non moyenne : si un plan sur quatre part ailleurs, la moyenne le
    suit a moitie et disculpe le plan fautif en accusant les autres.
    """
    try:
        import numpy as np
    except Exception:
        return None
    emps = []
    for v in videos:
        for im in _images_du_plan(v, combien=3):
            e = empreinte_visuelle(im)
            if e is not None:
                emps.append(e)
    if not emps:
        return None
    med = np.median(emps, axis=0)
    return med / (float((med ** 2).sum()) ** 0.5 + 1e-8)


def mesurer_film(videos: list, reference_png: str = "") -> dict:
    """Passe tout le film a la porte, plan par plan, contre sa propre lumiere."""
    lab_film = lumiere_du_film(videos)
    emp_film = signature_du_film(videos)
    plans = [mesurer_plan(v, reference_png, lab_film, emp_film) for v in videos]
    mesures = [p for p in plans if p.get("graded")]
    refuses = [p for p in mesures if not p.get("ok")]
    emit("porte_chiffree",
         f"{len(mesures)}/{len(videos)} plan(s) mesures, {len(refuses)} hors seuils")
    return {
        "ok": not refuses,
        "plans": plans,
        "refuses": [{"plan": p["plan"], "defauts": p["defauts"]} for p in refuses],
        "lumiere_film": [round(float(x), 1) for x in lab_film] if lab_film is not None else None,
        "seuils": {"constance": SEUIL_CONSTANCE,
                   "derive_interne": SEUIL_DERIVE_INTERNE,
                   "delta_e": SEUIL_DELTA_E,
                   "mouvement": SEUIL_MOUVEMENT},
    }


def check() -> dict:
    etat = {"opencv": False, "dinov2": False, "torch": False}
    try:
        import cv2  # noqa: F401
        etat["opencv"] = True
    except Exception:
        pass
    try:
        import torch  # noqa: F401
        etat["torch"] = True
    except Exception:
        pass
    etat["dinov2"] = bool(_extracteur())
    etat["ok"] = etat["opencv"] and etat["dinov2"]
    return etat


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--mesurer")
    ap.add_argument("--film", nargs="+")
    ap.add_argument("--reference", default="")
    args = ap.parse_args()

    if args.check:
        print(json.dumps(check(), ensure_ascii=False), flush=True)
        return 0
    if args.mesurer:
        r = mesurer_plan(args.mesurer, args.reference)
        print(json.dumps(r, ensure_ascii=False), flush=True)
        return 0 if r.get("ok") else 1
    if args.film:
        r = mesurer_film(args.film, args.reference)
        print(json.dumps(r, ensure_ascii=False, indent=2), flush=True)
        return 0 if r.get("ok") else 1
    print(json.dumps({"ok": False, "error": "--mesurer, --film ou --check requis"}))
    return 1


if __name__ == "__main__":
    sys.exit(main())
