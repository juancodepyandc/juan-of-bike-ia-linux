#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""motion_video_learn — apprend un mouvement NOMME depuis une VRAIE exécution.

Un modèle texte→mouvement IMAGINE un geste plausible; il ne REPRODUIT pas une
chorégraphie précise (vérifié: « macarena » générée = balancement quelconque,
« accroupi-frappe-bond » lu comme du ski). La montée en gamme: pour un
mouvement nommé, on regarde quelqu'un le faire.

Chaîne (aucune liste en dur, n'importe quel mouvement):
  1. yt-dlp cherche une video de démonstration (« <nom> dance tutorial »...),
     la plus courte exploitable en premier;
  2. MediaPipe Pose (33 repères monde, CPU) sur la vidéo entière (bornée);
  3. sélection de la FENÊTRE la plus dansante: la fenêtre glissante de la
     durée cible où la vitesse moyenne des articulations est maximale —
     saute l'intro parlée d'un tutoriel sans rien coder du contenu;
  4. 33 repères → 22 articulations SMPL (bassin/colonne interpolés), lissage;
  5. joints2bvh (momask) écrit le BVH — le MÊME écrivain que la voie
     HY-Motion, donc le même retarget derrière;
  6. le BVH est STOCKÉ dans les connaissances (~/.local/share/auroraia/
     connaissances/mouvements/<cle>.bvh) et l'entrée mémoire mise à jour:
     appris une fois, réutilisé à vie (30 ms au lieu de minutes).

Usage: python motion_video_learn.py --name macarena [--duration 8]
Sortie JSON: {ok, bvh, video, fenetre_s, frames}
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import tempfile
from pathlib import Path

CONNAISSANCES = Path(os.environ.get(
    "AURORA_CONNAISSANCES",
    Path.home() / ".local/share/auroraia/connaissances"))
MOMASK_DIR = Path(os.environ.get(
    "AURORA_MOMASK_DIR",
    Path.home() / ".local/share/auroraia/external/momask-codes"))

# indices MediaPipe Pose
_MP = {"nez": 0, "ep_g": 11, "ep_d": 12, "coude_g": 13, "coude_d": 14,
       "poignet_g": 15, "poignet_d": 16, "hanche_g": 23, "hanche_d": 24,
       "genou_g": 25, "genou_d": 26, "cheville_g": 27, "cheville_d": 28,
       "pied_g": 31, "pied_d": 32}


def _cle(nom: str) -> str:
    return re.sub(r"[\s_-]+", "", (nom or "").lower())


def _candidats_videos(nom: str) -> list[dict]:
    """Liste (dedupliquee) de videos de demonstration candidates."""
    import yt_dlp

    requetes = ["%s dance tutorial" % nom, "how to do the %s dance" % nom,
                "%s dance" % nom]
    vus, cands = set(), []
    for req in requetes:
        try:
            with yt_dlp.YoutubeDL({"quiet": True, "no_warnings": True}) as ydl:
                info = ydl.extract_info("ytsearch5:%s" % req, download=False)
            for e in (info.get("entries") or []):
                if not e:
                    continue
                url = e.get("webpage_url")
                dur = float(e.get("duration") or 0)
                if url in vus or not (8 < dur < 300):
                    continue
                vus.add(url)
                cands.append({"url": url, "titre": e.get("title"), "duree": dur})
        except Exception:  # noqa: BLE001
            continue
    return cands[:6]


def _telecharger(url: str, dossier: Path, idx: int) -> str | None:
    import yt_dlp

    gabarit = str(dossier / ("demo%d.%%(ext)s" % idx))
    try:
        with yt_dlp.YoutubeDL({
                "quiet": True, "no_warnings": True,
                # h264 (avc1) d'abord: l'OpenCV local ne decode pas l'AV1
                "format": ("bv*[vcodec^=avc1][height<=720]/"
                           "b[vcodec^=avc1][height<=720]/"
                           "bv*[height<=720][ext=mp4]/b[height<=720]"),
                "outtmpl": gabarit, "noplaylist": True}) as ydl:
            ydl.download([url])
        fichiers = sorted(dossier.glob("demo%d.*" % idx))
        return str(fichiers[0]) if fichiers else None
    except Exception:  # noqa: BLE001
        return None


def _modele_pose() -> str:
    """Telecharge (une fois) le modele PoseLandmarker officiel."""
    import urllib.request
    dest = CONNAISSANCES / "modeles" / "pose_landmarker_full.task"
    if dest.is_file() and dest.stat().st_size > 1_000_000:
        return str(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    url = ("https://storage.googleapis.com/mediapipe-models/pose_landmarker/"
           "pose_landmarker_full/float16/latest/pose_landmarker_full.task")
    urllib.request.urlretrieve(url, str(dest))
    return str(dest)


def _poses_video(video: str, max_s: float = 120.0, fps_cible: float = 30.0):
    """(T, 33, 3) positions monde MediaPipe (API Tasks) + visibilite (T, 33)."""
    import cv2
    import numpy as np
    import mediapipe as mp
    from mediapipe.tasks import python as mp_python
    from mediapipe.tasks.python import vision

    opts = vision.PoseLandmarkerOptions(
        base_options=mp_python.BaseOptions(model_asset_path=_modele_pose()),
        running_mode=vision.RunningMode.VIDEO)
    pose = vision.PoseLandmarker.create_from_options(opts)
    cap = cv2.VideoCapture(video)
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    saut = max(1, int(round(fps / fps_cible)))
    pts, vis = [], []
    i = 0
    while True:
        ok, img = cap.read()
        if not ok or (i / fps) > max_s:
            break
        if i % saut == 0:
            im = mp.Image(image_format=mp.ImageFormat.SRGB,
                          data=cv2.cvtColor(img, cv2.COLOR_BGR2RGB))
            res = pose.detect_for_video(im, int(1000.0 * i / fps))
            monde = res.pose_world_landmarks
            if not monde:
                pts.append(None)
                vis.append(None)
            else:
                pts.append([(p.x, p.y, p.z) for p in monde[0]])
                vis.append([getattr(p, "visibility", 1.0) or 1.0
                            for p in monde[0]])
        i += 1
    cap.release()
    pose.close()
    # remplit les trous par interpolation lineaire
    n = len(pts)
    arr = np.zeros((n, 33, 3), dtype=np.float32)
    vi = np.zeros((n, 33), dtype=np.float32)
    dernier = None
    for t in range(n):
        if pts[t] is not None:
            arr[t] = pts[t]
            vi[t] = vis[t]
            dernier = t
        elif dernier is not None:
            arr[t] = arr[dernier]
    return arr, vi, fps / saut


def _validite(arr, vis):
    """Frame par frame: le squelette est-il PLAUSIBLE ?

    - visibilite des articulations coeur (epaules, hanches, genoux, chevilles);
    - hauteur cou-chevilles dans des bornes humaines (gros plan = jambes
      hallucinees, squelette ecrase);
    - continuite: un saut de bassin > 40 cm entre 2 frames = coupe de montage.
    """
    import numpy as np

    coeur = [_MP[k] for k in ("ep_g", "ep_d", "hanche_g", "hanche_d",
                              "genou_g", "genou_d", "cheville_g", "cheville_d")]
    ok_vis = vis[:, coeur].mean(axis=1) > 0.5
    cou = 0.5 * (arr[:, _MP["ep_g"]] + arr[:, _MP["ep_d"]])
    chev = 0.5 * (arr[:, _MP["cheville_g"]] + arr[:, _MP["cheville_d"]])
    haut = np.linalg.norm(cou - chev, axis=1)
    ok_haut = (haut > 0.75) & (haut < 1.9)
    bassin = 0.5 * (arr[:, _MP["hanche_g"]] + arr[:, _MP["hanche_d"]])
    saut = np.linalg.norm(np.diff(bassin, axis=0), axis=1)
    ok_cont = np.concatenate([[True], saut < 0.40])
    return ok_vis & ok_haut & ok_cont


def _fenetre_dansante(arr, vis, fps: float, duree_s: float) -> tuple[int, int]:
    """Fenêtre la plus dansante PARMI LES FRAMES VALIDES: l'energie des coupes
    de montage et des gros plans ne compte plus (c'etait elle qui gagnait —
    squelette froisse appris, verifie)."""
    import numpy as np

    valide = _validite(arr, vis)
    v = np.linalg.norm(np.diff(arr, axis=0), axis=2).mean(axis=1)
    v = np.where(valide[1:] & valide[:-1], np.minimum(v, 0.2), 0.0)
    L = max(8, int(round(duree_s * fps)))
    if len(v) <= L:
        return 0, len(arr)
    energie = np.convolve(v, np.ones(L), mode="valid")
    # au moins 80% de frames valides dans la fenetre
    poids = np.convolve(valide[:-1].astype(float), np.ones(L), mode="valid")
    energie[poids < 0.8 * L] = -1.0
    debut = int(energie.argmax())
    return debut, debut + L


def _os_constants(J) -> float:
    """Ecart-type relatif max des longueurs d'os: les os ne grandissent pas.
    > 0.18 = tracking casse (coupes, hallucination) -> sequence rejetee."""
    import numpy as np

    paires = [(0, 1), (0, 2), (1, 4), (2, 5), (4, 7), (5, 8), (12, 16),
              (12, 17), (16, 18), (17, 19), (18, 20), (19, 21), (0, 12)]
    pire = 0.0
    for a, b in paires:
        d = np.linalg.norm(J[:, a] - J[:, b], axis=1)
        m = float(d.mean()) or 1e-6
        pire = max(pire, float(d.std()) / m)
    return pire


def _vers_22_joints(arr):
    """(T, 33, 3) MediaPipe monde -> (T, 22, 3) ordre SMPL corps, Y vers le haut.

    MediaPipe: x droite, y BAS, z vers la camera; origine bassin. On passe en
    Y-haut. Colonne/cou synthétisés par interpolation bassin↔épaules (aucune
    classe de sujet: pures proportions du squelette détecté).
    """
    import numpy as np

    a = arr.copy()
    a[..., 1] *= -1.0   # Y vers le haut
    a[..., 2] *= -1.0
    g = lambda n: a[:, _MP[n]]                      # noqa: E731
    bassin = 0.5 * (g("hanche_g") + g("hanche_d"))
    cou = 0.5 * (g("ep_g") + g("ep_d"))
    tete = g("nez")
    def lerp(p, q, t):
        return p + (q - p) * t
    J = np.stack([
        bassin,                                     # 0 pelvis
        g("hanche_g"), g("hanche_d"),               # 1 2
        lerp(bassin, cou, 0.25),                    # 3 spine1
        g("genou_g"), g("genou_d"),                 # 4 5
        lerp(bassin, cou, 0.5),                     # 6 spine2
        g("cheville_g"), g("cheville_d"),           # 7 8
        lerp(bassin, cou, 0.75),                    # 9 spine3
        g("pied_g"), g("pied_d"),                   # 10 11
        cou,                                        # 12 neck
        lerp(cou, g("ep_g"), 0.5),                  # 13 collar_l
        lerp(cou, g("ep_d"), 0.5),                  # 14 collar_r
        lerp(cou, tete, 0.7),                       # 15 head
        g("ep_g"), g("ep_d"),                       # 16 17
        g("coude_g"), g("coude_d"),                 # 18 19
        g("poignet_g"), g("poignet_d"),             # 20 21
    ], axis=1).astype(np.float32)
    # NORMALISATION D'AXES: les coordonnees MediaPipe sont relatives a la
    # CAMERA du tutoriel (souvent inclinee) — sans redressement, le squelette
    # danse penche et le retarget fait CULBUTER le sujet (constate). Une seule
    # rotation globale: colonne moyenne -> +Y, ligne des hanches -> +X. Les
    # tours de la danse elle-meme sont preserves (rotation unique, pas par
    # frame).
    haut = (J[:, 12] - J[:, 0]).mean(axis=0)
    haut = haut / (np.linalg.norm(haut) or 1.0)
    droite = (J[:, 2] - J[:, 1]).mean(axis=0)
    droite = droite - haut * float(droite @ haut)
    droite = droite / (np.linalg.norm(droite) or 1.0)
    devant = np.cross(haut, droite)
    Rm = np.stack([droite, haut, devant], axis=0)   # monde -> repere corps
    J = J @ Rm.T
    # DEPART FACE CAMERA. Le retarget ecrit l'orientation racine DEPUIS le
    # BVH: canoniser le mesh ne suffit pas, le danseur repart dos a la camera
    # si la video le filmait ainsi (constate). On aligne le REGARD INITIAL
    # (direction cou->nez horizontale, moyenne des 30 premieres frames) sur
    # +Z — la danse garde ensuite ses propres tours.
    nez22 = (a[:, _MP["nez"]] @ Rm.T)
    cou22 = 0.5 * (J[:, 16] + J[:, 17])
    f = (nez22[:30] - cou22[:30]).mean(axis=0)
    f[1] = 0.0
    n = np.linalg.norm(f)
    if n > 1e-6:
        f = f / n
        ang = np.arctan2(f[0], f[2])
        c, s_ = np.cos(-ang), np.sin(-ang)
        Ry = np.array([[c, 0, s_], [0, 1, 0], [-s_, 0, c]], dtype=np.float32)
        J = J @ Ry.T
    # sol a zero: le minimum des pieds sur la sequence
    J[..., 1] -= float(J[:, (7, 8, 10, 11), 1].min())
    return J


def _lisser(J, fenetre: int = 5):
    import numpy as np
    if len(J) < fenetre + 2:
        return J
    noyau = np.ones(fenetre) / fenetre
    out = J.copy()
    for j in range(J.shape[1]):
        for c in range(3):
            out[:, j, c] = np.convolve(
                np.pad(J[:, j, c], fenetre // 2, mode="edge"),
                noyau, mode="valid")[:len(J)]
    return out


def learn(nom: str, duree_s: float = 8.0) -> dict:
    dossier = CONNAISSANCES / "mouvements" / _cle(nom)
    dossier.mkdir(parents=True, exist_ok=True)
    bvh_final = CONNAISSANCES / "mouvements" / ("%s.bvh" % _cle(nom))
    if bvh_final.is_file() and bvh_final.stat().st_size > 1000:
        return {"ok": True, "bvh": str(bvh_final), "source": "deja_appris"}

    essais = []
    J = None
    vid = {}
    for _i, _cand in enumerate(_candidats_videos(nom)):
        _f = _telecharger(_cand["url"], dossier, _i)
        if not _f:
            essais.append({"video": _cand["url"], "echec": "telechargement"})
            continue
        arr, vis, fps = _poses_video(_f)
        if len(arr) < 16:
            import shutil as _sh
            import subprocess as _sp
            if _sh.which("ffmpeg"):
                h264 = str(Path(_f).with_suffix("")) + "_h264.mp4"
                _sp.run(["ffmpeg", "-y", "-i", _f, "-c:v", "libx264",
                         "-preset", "fast", "-an", h264],
                        capture_output=True, timeout=600, check=False)
                if Path(h264).is_file() and Path(h264).stat().st_size > 10000:
                    arr, vis, fps = _poses_video(h264)
        if len(arr) < 16:
            essais.append({"video": _cand["url"], "echec": "pose introuvable"})
            continue
        d0, d1 = _fenetre_dansante(arr, vis, fps, duree_s)
        _J = _lisser(_vers_22_joints(arr[d0:d1]))
        _var_os = _os_constants(_J)
        if _var_os > 0.18:
            essais.append({"video": _cand["url"],
                           "echec": "os variables %.0f%%" % (100 * _var_os)})
            continue
        J = _J
        vid = {"url": _cand["url"], "titre": _cand["titre"]}
        break
    if J is None:
        return {"ok": False, "essais": essais,
                "error": "aucune video exploitable (%d essayees)" % len(essais)}

    sys.path.insert(0, str(MOMASK_DIR))
    _cwd = os.getcwd()
    try:
        os.chdir(str(MOMASK_DIR))   # joints2bvh charge son gabarit en relatif
        from visualization.joints2bvh import Joint2BVHConvertor
        conv = Joint2BVHConvertor()
        conv.convert(J, str(bvh_final), foot_ik=False)
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": "joints2bvh: %r" % (exc,)}
    finally:
        os.chdir(_cwd)
    if not bvh_final.is_file() or bvh_final.stat().st_size < 1000:
        return {"ok": False, "error": "BVH vide apres conversion"}

    # memorise: la prochaine fois, 30 ms
    try:
        mem = CONNAISSANCES / "mouvements.json"
        d = json.loads(mem.read_text(encoding="utf-8")) if mem.is_file() else {}
        e = d.get(_cle(nom)) or {}
        e.update({"bvh": str(bvh_final), "video": vid.get("url"),
                  "video_titre": vid.get("titre"),
                  "fenetre_s": [round(d0 / fps, 1), round(d1 / fps, 1)]})
        d[_cle(nom)] = e
        mem.write_text(json.dumps(d, ensure_ascii=False, indent=1),
                       encoding="utf-8")
    except Exception:  # noqa: BLE001
        pass
    return {"ok": True, "bvh": str(bvh_final), "video": vid.get("url"),
            "fenetre_s": [round(d0 / fps, 1), round(d1 / fps, 1)],
            "frames": int(len(J))}


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--name", required=True)
    ap.add_argument("--duration", type=float, default=8.0)
    a = ap.parse_args()
    print(json.dumps(learn(a.name, a.duration), ensure_ascii=False))
