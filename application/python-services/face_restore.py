"""Restauration / super-resolution du VISAGE (leve le plafond RC3).

Probleme (RC3): la reference FLUX est un plein-pied 1024x1024 -> le visage n'y
fait que ~100-150 px. Le rendu ortho plein-corps de mesh_sanitize ne capture le
visage qu'a ~200 px. Aucun detail facial credible ne peut en sortir: le plafond
est en ENTREE, pas dans l'atlas.

Ce module remonte ce plafond:
  1. detect_face_bbox()   : YuNet (cv2.FaceDetectorYN, ONNX, CPU) + fallbacks.
  2. restore_face()       : crop tete -> restauration GFPGANv1.4 (prior facial)
                            + upscale Real-ESRGAN x4 -> tete a ~1024 px.
  3. restore_in_frame()   : MEME cadrage, visage restaure sur place (c'est CETTE
                            fonction que mesh_sanitize doit appeler sur sa vue
                            tete, car la projection UV depend du cadrage).

ANTI-HALLUCINATION (exigence: on veut le MEME visage, plus net -- pas un autre).
Quatre verrous, dans cet ordre:
  1. l'image reelle upscalee (Real-ESRGAN) n'est JAMAIS deformee ni resamplee:
     elle reste la base. Le prior ne fait qu'AJOUTER du micro-detail par-dessus.
  2. le prior GFPGAN est RECALE (flot optique dense) sur la geometrie reelle: on
     lui prend sa texture, jamais sa geometrie (sinon: traits deplaces, halos).
  3. seule la bande de frequence que le reel ne contient PHYSIQUEMENT pas est
     empruntee au prior (coupure calee sur le facteur d'agrandissement reel), en
     LUMINANCE uniquement (le teint reste exactement celui du reel) et avec une
     amplitude bornee (HALO_CLIP).
  4. garde-fou mesure: SFace (cv2.FaceRecognizerSF) compare l'embedding du visage
     d'origine et du visage produit par le prior. Si cosine < min_identity, le
     prior est REJETE et on retombe sur Real-ESRGAN seul. Le score est toujours
     renvoye dans le JSON (identity_cosine; seuil "meme personne" SFace = 0.363).

Poids (telecharges une seule fois, caches hors du repo):
  $AURORA_FACE_CKPT_DIR (defaut ~/.cache/aurora/face_restore)
    - face_detection_yunet_2023mar.onnx      (232 Ko, opencv_zoo)
    - face_recognition_sface_2021dec.onnx    (38 Mo, opencv_zoo)
    - GFPGANv1.4.pth                         (349 Mo, TencentARC)
  Real-ESRGAN est deja dans le repo:
    application/python-services/_hy3dpaint/ckpt/RealESRGAN_x4plus.pth

Tout tourne sur CPU (aucun appel GPU). Chargement des .pth via `spandrel`
(pas de basicsr/realesrgan: incompatibles avec torch 2.x + torchvision recent).

CLI:
    python face_restore.py --image ref.png --output face_hi.png
    -> {"ok": true, "bbox": [x,y,w,h], "out": "...", "scale": 5.1, ...}
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.request
from dataclasses import dataclass
from typing import Optional, Tuple

import cv2
import numpy as np

# --------------------------------------------------------------------------
# Poids
# --------------------------------------------------------------------------

_HERE = os.path.dirname(os.path.abspath(__file__))
ESRGAN_CKPT = os.path.join(_HERE, "_hy3dpaint", "ckpt", "RealESRGAN_x4plus.pth")

_ASSETS = {
    "face_detection_yunet_2023mar.onnx": (
        "https://media.githubusercontent.com/media/opencv/opencv_zoo/main/"
        "models/face_detection_yunet/face_detection_yunet_2023mar.onnx",
        200_000,
    ),
    "face_recognition_sface_2021dec.onnx": (
        "https://media.githubusercontent.com/media/opencv/opencv_zoo/main/"
        "models/face_recognition_sface/face_recognition_sface_2021dec.onnx",
        30_000_000,
    ),
    "GFPGANv1.4.pth": (
        "https://github.com/TencentARC/GFPGAN/releases/download/v1.3.0/GFPGANv1.4.pth",
        300_000_000,
    ),
}


def ckpt_dir() -> str:
    d = os.environ.get("AURORA_FACE_CKPT_DIR") or os.path.expanduser(
        "~/.cache/aurora/face_restore"
    )
    os.makedirs(d, exist_ok=True)
    return d


def ensure_asset(name: str, allow_download: bool = True) -> Optional[str]:
    """Retourne le chemin d'un poids, le telecharge si absent. None si indispo."""
    path = os.path.join(ckpt_dir(), name)
    url, min_size = _ASSETS[name]
    if os.path.isfile(path) and os.path.getsize(path) >= min_size:
        return path
    if not allow_download or os.environ.get("AURORA_FACE_OFFLINE") == "1":
        return None
    try:
        tmp = path + ".part"
        req = urllib.request.Request(url, headers={"User-Agent": "AuroraIA/1.0"})
        with urllib.request.urlopen(req, timeout=120) as r, open(tmp, "wb") as f:
            while True:
                chunk = r.read(1 << 20)
                if not chunk:
                    break
                f.write(chunk)
        if os.path.getsize(tmp) < min_size:  # page HTML d'erreur / pointeur LFS
            os.remove(tmp)
            return None
        os.replace(tmp, path)
        return path
    except Exception as exc:  # pragma: no cover - reseau
        sys.stderr.write("[face_restore] telechargement %s echoue: %s\n" % (name, exc))
        return None


# --------------------------------------------------------------------------
# Detection
# --------------------------------------------------------------------------

# Gabarit FFHQ 5 points (espace 512x512) attendu par GFPGAN.
# Ordre: oeil gauche-image, oeil droit-image, nez, coin bouche gauche, coin droit.
FFHQ_TEMPLATE_512 = np.array(
    [
        [192.98138, 239.94708],
        [318.90277, 240.19366],
        [256.63416, 314.01935],
        [201.26117, 371.41043],
        [313.08905, 371.15118],
    ],
    dtype=np.float32,
)


@dataclass
class FaceHit:
    bbox: Tuple[int, int, int, int]  # x, y, w, h (pixels image source)
    landmarks: list  # 5 x [x, y]  (ordre FFHQ, coords image source)
    score: float
    method: str


def _src_bgr(img: np.ndarray) -> np.ndarray:
    """Canaux BGR d'ORIGINE (sans compositing alpha) -> base de l'image de sortie.

    _to_bgr() aplatit l'alpha sur un gris neutre: parfait pour la DETECTION et pour
    le recadrage du prior, mais destructeur pour la sortie (il ecraserait le RGB des
    zones transparentes d'un rendu film_transparent). La sortie doit repartir des
    octets d'origine.
    """
    if img.ndim == 2:
        return cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
    return img[:, :, :3].copy()


def _to_bgr(img: np.ndarray) -> np.ndarray:
    """BGRA/gris -> BGR, alpha composite sur gris neutre (rendus film_transparent)."""
    if img.ndim == 2:
        return cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
    if img.shape[2] == 4:
        a = img[:, :, 3:4].astype(np.float32) / 255.0
        bg = np.full(img[:, :, :3].shape, 127.0, np.float32)
        return (img[:, :, :3].astype(np.float32) * a + bg * (1 - a)).astype(np.uint8)
    return img


def _yunet_detect(bgr: np.ndarray, conf: float, model: str) -> list:
    h, w = bgr.shape[:2]
    det = cv2.FaceDetectorYN.create(model, "", (w, h), conf, 0.3, 5000)
    _, faces = det.detect(bgr)
    if faces is None:
        return []
    out = []
    for f in faces:
        x, y, fw, fh = [float(v) for v in f[:4]]
        lmk = np.array(f[4:14], dtype=np.float32).reshape(5, 2).tolist()
        out.append(
            FaceHit(
                bbox=(int(round(x)), int(round(y)), int(round(fw)), int(round(fh))),
                landmarks=lmk,
                score=float(f[-1]),
                method="yunet",
            )
        )
    return out


def detect_face_bbox(
    image_path: str,
    conf: float = 0.6,
    allow_download: bool = True,
    allow_silhouette: bool = False,
) -> Optional[FaceHit]:
    """Detecte le visage principal (le plus grand) sur une reference plein-pied.

    Strategie: YuNet a l'echelle native, puis retente sur une image 2x/4x agrandie
    (un visage de 100 px dans un plein-pied 1024 est a la limite basse du detecteur).

    allow_silhouette: repli geometrique (la tete = sommet de la silhouette) quand YuNet
    echoue. A n'activer QUE si l'appelant sait que le sujet est un humain (visage
    stylise, de profil, ...). Sur un objet quelconque (une fontaine) ce repli
    inventerait une "tete": il est donc DESACTIVE par defaut -> None, et l'appelant
    saute simplement l'etape visage.
    """
    raw = cv2.imread(image_path, cv2.IMREAD_UNCHANGED)
    if raw is None:
        raise FileNotFoundError(image_path)
    bgr = _to_bgr(raw)

    model = ensure_asset("face_detection_yunet_2023mar.onnx", allow_download)
    if model:
        best: Optional[FaceHit] = None
        best_score = -1.0
        # Agrandir sert aux PETITS visages (100 px dans un plein-pied); REDUIRE
        # sert aux gros plans, et manquait: sur un selfie ou la tete remplit le
        # cadre, YuNet a l'echelle native rendait un visage decale (mesure:
        # score 0.63, yeux places 180 px trop bas, sur le nez/la bouche) tandis
        # que la meme image reduite donne 0.93 et des yeux justes. On garde donc
        # l'echelle qui INSPIRE LE PLUS CONFIANCE, au lieu de s'arreter a la
        # premiere qui detecte quelque chose.
        for sc in (1.0, 0.5, 0.25, 2.0, 4.0):
            probe = bgr
            if sc != 1.0:
                interp = cv2.INTER_AREA if sc < 1.0 else cv2.INTER_CUBIC
                probe = cv2.resize(bgr, None, fx=sc, fy=sc, interpolation=interp)
            if min(probe.shape[:2]) < 64:
                continue
            try:
                hits = _yunet_detect(probe, conf, model)
            except cv2.error:
                continue
            # au sein d'une echelle, le sujet principal reste le plus GRAND
            cand: Optional[FaceHit] = None
            for hit in hits:
                if cand is None or hit.bbox[2] * hit.bbox[3] > cand.bbox[2] * cand.bbox[3]:
                    cand = hit
            if cand is None or cand.score <= best_score:
                continue
            x, y, w, h = cand.bbox
            best = FaceHit(
                bbox=(int(round(x / sc)), int(round(y / sc)),
                      int(round(w / sc)), int(round(h / sc))),
                landmarks=[[p[0] / sc, p[1] / sc] for p in cand.landmarks],
                score=cand.score,
                method="yunet@x%g" % sc,
            )
            best_score = cand.score
            if best_score >= 0.90:  # detection franche: inutile de continuer
                break
        if best is not None:
            return best

    if not allow_silhouette:
        return None
    return _fallback_head_from_silhouette(raw, bgr)


def _fallback_head_from_silhouette(raw: np.ndarray, bgr: np.ndarray) -> Optional[FaceHit]:
    """Sans detecteur: la tete est le sommet de la silhouette (prior plein-pied).

    Utilise le canal alpha si present (rendus Blender film_transparent), sinon un
    masque foreground par difference avec la couleur de fond dominante des bords.
    """
    h, w = bgr.shape[:2]
    if raw.ndim == 3 and raw.shape[2] == 4:
        mask = (raw[:, :, 3] > 16).astype(np.uint8)
    else:
        border = np.concatenate(
            [bgr[0, :], bgr[-1, :], bgr[:, 0], bgr[:, -1]], axis=0
        ).astype(np.float32)
        bg = np.median(border, axis=0)
        dist = np.linalg.norm(bgr.astype(np.float32) - bg, axis=2)
        mask = (dist > 30).astype(np.uint8)
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, np.ones((5, 5), np.uint8))
    ys, xs = np.nonzero(mask)
    if ys.size < 64:
        return None
    top = int(ys.min())
    body_h = int(ys.max()) - top
    if body_h < 32:
        return None
    # tete ~ 1/7.5 de la hauteur du corps (canon anatomique)
    head_h = max(16, int(round(body_h / 7.5)))
    band = mask[top : top + head_h, :]
    bxs = np.nonzero(band.any(axis=0))[0]
    if bxs.size == 0:
        return None
    x0, x1 = int(bxs.min()), int(bxs.max())
    # le visage occupe la moitie basse de la tete
    fy = top + int(head_h * 0.35)
    fh = max(12, int(head_h * 0.6))
    fw = max(12, x1 - x0)
    return FaceHit(
        bbox=(x0, fy, fw, fh),
        landmarks=[],  # pas de landmarks -> pas d'alignement GFPGAN possible
        score=0.0,
        method="silhouette",
    )


# --------------------------------------------------------------------------
# Modeles (charges paresseusement, caches au niveau module)
# --------------------------------------------------------------------------

_MODELS: dict = {}


def _load_spandrel(path: str, key: str):
    if key in _MODELS:
        return _MODELS[key]
    try:
        import torch
        from spandrel import ModelLoader

        torch.set_grad_enabled(False)
        m = ModelLoader(device="cpu").load_from_file(path)
        m.eval()
        _MODELS[key] = m
        return m
    except Exception as exc:
        sys.stderr.write("[face_restore] modele %s indisponible: %s\n" % (key, exc))
        _MODELS[key] = None
        return None


def _esrgan():
    if not os.path.isfile(ESRGAN_CKPT):
        return None
    return _load_spandrel(ESRGAN_CKPT, "esrgan")


def _gfpgan(allow_download: bool = True):
    p = ensure_asset("GFPGANv1.4.pth", allow_download)
    return _load_spandrel(p, "gfpgan") if p else None


def _run(model, bgr: np.ndarray, signed: bool) -> np.ndarray:
    """Inference spandrel sur une image BGR uint8. signed=True -> domaine [-1,1] (GFPGAN)."""
    import torch

    rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB).astype(np.float32) / 255.0
    t = torch.from_numpy(rgb).permute(2, 0, 1).unsqueeze(0)
    if signed:
        t = t * 2.0 - 1.0
    with torch.no_grad():
        out = model(t)
    if signed:
        out = (out + 1.0) / 2.0
    out = out.clamp(0, 1)[0].permute(1, 2, 0).numpy()
    return cv2.cvtColor((out * 255.0 + 0.5).astype(np.uint8), cv2.COLOR_RGB2BGR)


def _upscale(bgr: np.ndarray, target: int) -> Tuple[np.ndarray, str]:
    """Real-ESRGAN x4 (avec repli Lanczos+unsharp) puis resize exact a `target`."""
    m = _esrgan()
    method = "lanczos+unsharp"
    out = bgr
    if m is not None and max(bgr.shape[:2]) > ESRGAN_MAX_IN:
        m = None  # entree trop grosse pour le CPU (on n'upscale que des crops de tete)
    if m is not None:
        try:
            out = _run(m, bgr, signed=False)  # x4
            method = "realesrgan_x4"
            # crop tres petit: un second passage x4 evite un resize purement flou
            while max(out.shape[:2]) * 2 < target:
                out = _run(m, out, signed=False)
                method = "realesrgan_x4x4"
        except Exception as exc:
            sys.stderr.write("[face_restore] esrgan echec: %s\n" % exc)
            out = bgr
            method = "lanczos+unsharp"
    if out.shape[0] != target or out.shape[1] != target:
        interp = cv2.INTER_AREA if out.shape[0] > target else cv2.INTER_LANCZOS4
        out = cv2.resize(out, (target, target), interpolation=interp)
    if method != "realesrgan_x4":
        blur = cv2.GaussianBlur(out, (0, 0), 2.0)
        out = cv2.addWeighted(out, 1.6, blur, -0.6, 0)
    return out, method


# --------------------------------------------------------------------------
# Identite (garde-fou anti-hallucination)
# --------------------------------------------------------------------------


def _sface():
    if "sface" in _MODELS:
        return _MODELS["sface"]
    p = ensure_asset("face_recognition_sface_2021dec.onnx")
    m = None
    if p:
        try:
            m = cv2.FaceRecognizerSF.create(p, "")
        except Exception as exc:
            sys.stderr.write("[face_restore] sface indisponible: %s\n" % exc)
    _MODELS["sface"] = m
    return m


def identity_cosine(face_a: np.ndarray, face_b: np.ndarray) -> Optional[float]:
    """Similarite cosinus SFace entre deux visages ALIGNES (meme cadrage, BGR).

    SFace: > 0.363 = meme personne (seuil officiel opencv_zoo).
    """
    m = _sface()
    if m is None:
        return None
    try:
        a = m.feature(cv2.resize(face_a, (112, 112), interpolation=cv2.INTER_AREA))
        b = m.feature(cv2.resize(face_b, (112, 112), interpolation=cv2.INTER_AREA))
        return float(m.match(a, b, cv2.FaceRecognizerSF_FR_COSINE))
    except Exception:
        return None


# --------------------------------------------------------------------------
# Coeur: restauration du visage aligne
# --------------------------------------------------------------------------


HI = 2048  # espace de travail "visage aligne haute resolution" (4 x GFPGAN)
HALO_CLIP = 26.0  # amplitude max (niveaux L*) du detail injecte par le prior
CHROMA_CLIP = 22.0  # amplitude max (a*/b*) de la correction de chrominance du prior
ESRGAN_MAX_IN = 1024  # au-dela, Real-ESRGAN x4 sur CPU coute des minutes -> Lanczos


def _register_prior(real: np.ndarray, prior: np.ndarray, max_shift: float) -> np.ndarray:
    """Recale le prior sur la GEOMETRIE REELLE (flot optique dense, CPU).

    GFPGAN reconstruit un visage plausible mais deplace legerement les traits
    (paupieres, levres). Injecter tel quel ses hautes frequences produit des halos
    et des doubles contours (detail pose a cote de l'arete reelle).
    On deforme donc le prior pour qu'il epouse EXACTEMENT le visage reel: on ne
    garde de lui que la TEXTURE, jamais la geometrie -> zero derive d'identite.
    """
    try:
        dis = cv2.DISOpticalFlow_create(cv2.DISOPTICAL_FLOW_PRESET_MEDIUM)
    except Exception:
        return prior
    # le reel est flou: on estime le flot sur des versions lissees comparables
    gr = cv2.GaussianBlur(cv2.cvtColor(real, cv2.COLOR_BGR2GRAY), (0, 0), 3.0)
    gp = cv2.GaussianBlur(cv2.cvtColor(prior, cv2.COLOR_BGR2GRAY), (0, 0), 3.0)
    flow = dis.calc(gr, gp, None)  # reel -> prior
    mag = np.linalg.norm(flow, axis=2, keepdims=True)
    scale = np.minimum(1.0, max_shift / np.maximum(mag, 1e-6))
    flow = flow * scale  # bride les deplacements aberrants
    flow = cv2.GaussianBlur(flow, (0, 0), 2.0)
    h, w = real.shape[:2]
    gx, gy = np.meshgrid(np.arange(w, dtype=np.float32), np.arange(h, dtype=np.float32))
    return cv2.remap(
        prior, gx + flow[:, :, 0], gy + flow[:, :, 1],
        cv2.INTER_LANCZOS4, borderMode=cv2.BORDER_REPLICATE,
    )


def _align_affine(hit: FaceHit) -> Optional[np.ndarray]:
    """Affine 2x3 image -> visage aligne 512 (gabarit FFHQ)."""
    if len(hit.landmarks) != 5:
        return None
    src = np.array(hit.landmarks, dtype=np.float32)
    affine, _ = cv2.estimateAffinePartial2D(src, FFHQ_TEMPLATE_512, method=cv2.LMEDS)
    return affine


def _face_mask_hi(feather: float = 0.05) -> np.ndarray:
    """Masque ovale doux du visage dans l'espace aligne HI (evite toute couture)."""
    m = np.zeros((HI, HI), np.float32)
    c = HI / 512.0
    cv2.ellipse(
        m, (int(256 * c), int(300 * c)), (int(168 * c), int(216 * c)), 0, 0, 360, 1.0, -1
    )
    return cv2.GaussianBlur(m, (0, 0), feather * HI)


def _prior_face(
    bgr: np.ndarray, hit: FaceHit, min_identity: float, allow_download: bool
) -> Tuple[Optional[np.ndarray], Optional[np.ndarray], dict]:
    """Visage restaure par le prior GFPGAN, re-durci a HI. (prior_hi, A_hi, infos)."""
    info = {"prior": None, "identity_cosine": None, "prior_rejected": None,
            "face_upscale": None, "registered": False}

    A = _align_affine(hit)
    if A is None:
        return None, None, info  # pas de landmarks -> ESRGAN seul

    aligned = cv2.warpAffine(
        bgr, A, (512, 512), flags=cv2.INTER_LANCZOS4, borderMode=cv2.BORDER_REFLECT
    )
    g = _gfpgan(allow_download)
    if g is None:
        return None, None, info
    try:
        prior512 = _run(g, aligned, signed=True)  # GFPGAN: domaine [-1, 1]
    except Exception as exc:
        sys.stderr.write("[face_restore] gfpgan echec: %s\n" % exc)
        return None, None, info

    # garde-fou identite: le prior a-t-il fabrique un AUTRE visage ?
    cos = identity_cosine(aligned, prior512)
    info["identity_cosine"] = cos
    info["prior"] = "gfpgan_v1.4"
    if cos is not None and cos < min_identity:
        info["prior_rejected"] = "identity_cosine %.3f < %.3f" % (cos, min_identity)
        return None, None, info

    # GFPGAN est fige a 512, en dessous de la resolution du visage en sortie:
    # on le re-durcit a HI (Real-ESRGAN) sinon on ne ferait que le re-flouter.
    prior_hi, _ = _upscale(prior512, HI)
    k = float(HI) / 512.0
    A_hi = A.copy()
    A_hi[:2, :] *= k  # image source -> aligne HI
    return prior_hi, A_hi, info


def _inject_face_detail(
    base: np.ndarray,
    prior_hi: np.ndarray,
    A_hi: np.ndarray,
    C: np.ndarray,
    sigma: float,
    fidelity: float,
    detail: float,
    suppress: float,
    chroma: float = 0.0,
) -> Tuple[np.ndarray, dict]:
    """Injecte le micro-detail du prior DANS l'image de sortie, sans jamais la resampler.

    `base` (Real-ESRGAN, geometrie et couleurs REELLES) n'est jamais deformee: on lui
    ajoute seulement un differentiel de HAUTES frequences pris sur le prior recale.
    fidelity=1 => les basses/moyennes frequences (donc l'identite, le teint, la forme
    des traits) restent celles du reel, au pixel pres.

    `chroma` (0..1) autorise en plus une correction de CHROMINANCE vers le prior. Par
    defaut nul: sur une photo reelle, la carnation du reel fait foi. Mais sur un mesh
    genere, certains defauts sont PUREMENT chromatiques - les yeux sortent en taches
    bleuatres - et aucune correction de luminance ne peut les rattraper. On l'active
    alors, sous garde du cosinus d'identite.
    """
    oh, ow = base.shape[:2]
    Ah3 = np.vstack([A_hi, [0, 0, 1]]).astype(np.float64)
    M = (C @ np.linalg.inv(Ah3))[:2]  # aligne HI -> espace de sortie

    # anti-crenelage avant reduction (HI -> sortie est une reduction)
    shrink = float(np.sqrt(abs(M[0, 0] * M[1, 1] - M[0, 1] * M[1, 0])))
    src = prior_hi
    if shrink < 0.9:
        src = cv2.GaussianBlur(prior_hi, (0, 0), 0.5 / max(shrink, 1e-3))
    prior_out = cv2.warpAffine(
        src, M, (ow, oh), flags=cv2.INTER_LANCZOS4, borderMode=cv2.BORDER_REPLICATE
    )
    mask = cv2.warpAffine(_face_mask_hi(), M, (ow, oh), flags=cv2.INTER_LINEAR)

    ys, xs = np.nonzero(mask > 0.004)
    if ys.size == 0:
        return base, {"registered": False}
    y0, y1 = int(ys.min()), int(ys.max()) + 1
    x0, x1 = int(xs.min()), int(xs.max()) + 1

    b = base[y0:y1, x0:x1]
    p = prior_out[y0:y1, x0:x1]
    m = mask[y0:y1, x0:x1][..., None]

    # le prior epouse la geometrie REELLE (sinon: halos et doubles contours)
    p = _register_prior(b, p, max_shift=0.03 * max(y1 - y0, x1 - x0))

    # Le detail est injecte en LUMINANCE seule: la chrominance (teint) reste
    # strictement celle du reel -> aucun liseré colore, aucune derive de carnation.
    bl = cv2.cvtColor(b, cv2.COLOR_BGR2LAB).astype(np.float32)
    pl = cv2.cvtColor(p, cv2.COLOR_BGR2LAB).astype(np.float32)
    bL, pL = bl[:, :, 0], pl[:, :, 0]
    lp_b = cv2.GaussianBlur(bL, (0, 0), sigma)
    lp_p = cv2.GaussianBlur(pL, (0, 0), sigma)

    # + micro-structure du prior (cils, paupieres, levres, dents: ce que le reel n'a PAS)
    # - une part du haut-de-bande invente par ESRGAN sur la peau (evite le sur-piquage)
    # + correction basse frequence residuelle si fidelity < 1
    delta = (
        detail * (pL - lp_p)
        - suppress * (bL - lp_b)
        + (1.0 - fidelity) * (lp_p - lp_b)
    )
    # bride les residus aberrants (un ecart local enorme = le prior a INVENTE une
    # structure absente du reel -> halo). On borne son amplitude.
    lim = float(HALO_CLIP)
    delta = np.clip(delta, -lim, lim)

    bl[:, :, 0] = np.clip(bL + m[:, :, 0] * delta, 0, 255)
    if chroma > 0.0:
        # Correction de chrominance vers le prior. Elle est bornee: on ne remplace pas
        # la carnation, on la tire vers celle du prior la ou le reel est aberrant (les
        # yeux d'un mesh genere sortent bleuatres et aucun ecart de LUMINANCE ne peut
        # les corriger). L'ecart est clampe pour qu'un prior mal recale ne repeigne pas
        # tout le visage.
        w_c = (chroma * m[:, :, 0])[..., None]
        dab = np.clip(pl[:, :, 1:] - bl[:, :, 1:], -CHROMA_CLIP, CHROMA_CLIP)
        bl[:, :, 1:] = np.clip(bl[:, :, 1:] + w_c * dab, 0, 255)
    conv = cv2.cvtColor(bl.astype(np.uint8), cv2.COLOR_LAB2BGR).astype(np.float32)
    # re-fondu explicite par le masque: hors du visage les octets d'origine sont
    # conserves A L'IDENTIQUE (l'aller-retour LAB introduirait sinon un bruit de
    # quantification +-2 sur tout le rectangle -> une vue de bake ne doit pas bouger
    # d'un pixel en dehors du visage).
    out = base.copy()
    out[y0:y1, x0:x1] = np.clip(
        conv * m + b.astype(np.float32) * (1.0 - m), 0, 255
    ).astype(np.uint8)
    return out, {"registered": True}


# --------------------------------------------------------------------------
# API publique
# --------------------------------------------------------------------------


def head_box(
    hit: FaceHit, img_w: int, img_h: int, margin: float = 1.9
) -> Tuple[int, int, int]:
    """Boite CARREE de la TETE (cheveux + menton + amorce de cou) -> (x, y, size).

    C'est ce cadrage qui doit servir de cadrage de camera ortho serree sur la tete.
    """
    x, y, w, h = hit.bbox
    cx, cy = x + w / 2.0, y + h / 2.0
    size = int(round(max(w, h) * margin))
    size = max(16, min(size, min(img_w, img_h)))
    # la tete deborde vers le HAUT (cheveux, crane): on remonte le centre
    cy -= h * 0.12
    hx = int(round(cx - size / 2.0))
    hy = int(round(cy - size / 2.0))
    hx = max(0, min(hx, img_w - size))
    hy = max(0, min(hy, img_h - size))
    return hx, hy, size


def _detail_floor(gray: np.ndarray) -> float:
    """MESURE l'echelle (px) en dessous de laquelle l'image n'a plus de vraie structure.

    On ne peut pas deduire la coupure du seul facteur de redimensionnement: la vue tete
    de mesh_sanitize est rendue a 2048 mais sa TEXTURE ne porte que ~200 px de visage
    (deja etiree, donc molle) -> son plancher de detail est ~5x plus grossier que son
    pas de pixel. On le mesure donc directement: plus petit sigma de flou qui detruit
    encore une part significative de l'energie haute frequence.

    Le seuil est bas (5% de l'energie HF): une image FLOUE a un genou net dans son
    spectre (l'estimation y est insensible au seuil), alors qu'une image NETTE a un
    spectre en loi de puissance -- un seuil eleve y surestimerait le plancher et
    laisserait le prior deborder sur des frequences que le reel possede vraiment.
    Calibre sur les deux regimes: photo nette -> 1.0 px, rendu etire -> 3.0 px.
    """
    g = gray.astype(np.float32)
    ref = float(np.mean((g - cv2.GaussianBlur(g, (0, 0), 8.0)) ** 2))
    if ref < 1e-6:
        return 8.0  # zone plate (aucun detail) -> coupure large
    for s in (0.6, 0.8, 1.0, 1.3, 1.6, 2.0, 2.5, 3.0, 4.0, 5.0, 6.0):
        e = float(np.mean((g - cv2.GaussianBlur(g, (0, 0), s)) ** 2))
        if e >= 0.05 * ref:
            return s
    return 6.0


def _sigma_out(bgr: np.ndarray, hit: FaceHit, out_scale: float) -> float:
    """Coupure frequentielle = PLANCHER DE DETAIL REEL, exprime en pixels de sortie.

    En dessous de cette echelle l'image reelle ne contient RIEN (c'est le plafond RC3):
    c'est exactement, et seulement, la bande que le prior a le droit de remplir.
    """
    x, y, w, h = hit.bbox
    H, W = bgr.shape[:2]
    x0, y0 = max(0, x), max(0, y)
    x1, y1 = min(W, x + w), min(H, y + h)
    roi = bgr[y0:y1, x0:x1]
    if roi.size == 0:
        return float(np.clip(0.6 * out_scale, 1.0, 24.0))
    floor_px = _detail_floor(cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY))
    return float(np.clip(floor_px * out_scale, 1.0, 24.0))


def _apply_prior(
    bgr: np.ndarray,
    base: np.ndarray,
    C: np.ndarray,
    hit: Optional[FaceHit],
    out_scale: float,
    fidelity: float,
    detail: float,
    suppress: float,
    min_identity: float,
    allow_download: bool,
    chroma: float = 0.0,
) -> Tuple[np.ndarray, dict]:
    """Chaine complete du prior facial sur une image de sortie deja upscalee."""
    info = {"prior": None, "identity_cosine": None, "prior_rejected": None,
            "face_upscale": None, "registered": False, "merge_sigma": None}
    if hit is None:
        return base, info
    prior_hi, A_hi, info = _prior_face(bgr, hit, min_identity, allow_download)
    if prior_hi is None or A_hi is None:
        return base, info
    sigma = _sigma_out(bgr, hit, out_scale)
    info["merge_sigma"] = round(sigma, 2)
    out, reg = _inject_face_detail(
        base, prior_hi, A_hi, C, sigma, fidelity, detail, suppress, chroma
    )
    info.update(reg)
    return out, info


def restore_face(
    image_path: str,
    out_path: str,
    target: int = 1024,
    margin: float = 1.9,
    fidelity: float = 0.95,
    detail: float = 0.85,
    suppress: float = 0.30,
    min_identity: float = 0.40,
    allow_download: bool = True,
    allow_silhouette: bool = False,
) -> dict:
    """Crope la TETE d'une reference plein-pied, la restaure et l'upscale a `target`.

    Retourne un dict serialisable JSON contenant tout le mapping necessaire a la
    re-injection (cf. `head_box_norm`: cadrage normalise dans l'image source).
    """
    raw = cv2.imread(image_path, cv2.IMREAD_UNCHANGED)
    if raw is None:
        raise FileNotFoundError(image_path)
    bgr = _to_bgr(raw)      # detection / alignement du prior
    src = _src_bgr(raw)     # base de la sortie (RGB d'origine)
    H, W = bgr.shape[:2]

    hit = detect_face_bbox(
        image_path, allow_download=allow_download, allow_silhouette=allow_silhouette
    )
    if hit is None:
        return {"ok": False, "error": "aucun visage detecte", "image": image_path}

    hx, hy, hs = head_box(hit, W, H, margin)
    crop = src[hy : hy + hs, hx : hx + hs]

    # 1) base fidele: la tete reelle, upscalee (Real-ESRGAN x4)
    base, up_method = _upscale(crop, target)
    scale = float(target) / float(hs)

    # C: image source -> espace de sortie (crop tete mis a l'echelle)
    C = np.array(
        [[scale, 0, -hx * scale], [0, scale, -hy * scale], [0, 0, 1]], dtype=np.float64
    )

    # 2) micro-detail du prior facial (GFPGAN) injecte dans la base, sans la deformer
    out, info = _apply_prior(
        bgr, base, C, hit, scale, fidelity, detail, suppress, min_identity, allow_download
    )

    # alpha eventuel (rendus transparents): on la conserve, upscalee
    if raw.ndim == 3 and raw.shape[2] == 4:
        a = raw[hy : hy + hs, hx : hx + hs, 3]
        a = cv2.resize(a, (target, target), interpolation=cv2.INTER_LANCZOS4)
        out = np.dstack([out, a])

    os.makedirs(os.path.dirname(os.path.abspath(out_path)) or ".", exist_ok=True)
    cv2.imwrite(out_path, out)

    return {
        "ok": True,
        "image": image_path,
        "out": out_path,
        "image_size": [W, H],
        "bbox": list(hit.bbox),
        "landmarks": [[round(p[0], 2), round(p[1], 2)] for p in hit.landmarks],
        "detector": hit.method,
        "detect_score": round(hit.score, 3),
        "head_box": [hx, hy, hs, hs],
        # cadrage normalise (u0, v0, u1, v1) dans l'image source -> camera ortho tete
        "head_box_norm": [
            round(hx / W, 6),
            round(hy / H, 6),
            round((hx + hs) / W, 6),
            round((hy + hs) / H, 6),
        ],
        "face_px_in": int(max(hit.bbox[2], hit.bbox[3])),
        "face_px_out": int(round(max(hit.bbox[2], hit.bbox[3]) * scale)),
        "target": target,
        "scale": round(scale, 3),
        "upscaler": up_method,
        "restorer": info["prior"] if info["prior_rejected"] is None else None,
        "identity_cosine": (
            round(info["identity_cosine"], 4)
            if info["identity_cosine"] is not None
            else None
        ),
        "prior_rejected": info["prior_rejected"],
        "merge_sigma": info.get("merge_sigma"),
        "fidelity": fidelity,
    }


def restore_in_frame(
    image_path: str,
    out_path: str,
    upscale: int = 2,
    fidelity: float = 0.95,
    detail: float = 0.85,
    suppress: float = 0.30,
    min_identity: float = 0.40,
    allow_download: bool = True,
    allow_silhouette: bool = False,
    chroma: float = 0.0,
) -> dict:
    """Restaure le visage EN CONSERVANT LE CADRAGE (image entiere, agrandie x`upscale`).

    C'est l'entree de mesh_sanitize: la projection UV d'une vue est calculee a
    partir de la camera (coords normalisees), donc l'image de bake peut etre
    agrandie mais son CADRAGE doit rester identique. Retourne le meme mapping.
    """
    raw = cv2.imread(image_path, cv2.IMREAD_UNCHANGED)
    if raw is None:
        raise FileNotFoundError(image_path)
    bgr = _to_bgr(raw)      # detection / alignement du prior
    src = _src_bgr(raw)     # base de la sortie (RGB d'origine, alpha non aplatie)
    H, W = bgr.shape[:2]
    TW, TH = W * upscale, H * upscale

    hit = detect_face_bbox(
        image_path, allow_download=allow_download, allow_silhouette=allow_silhouette
    )

    if upscale > 1:
        full = cv2.resize(src, (TW, TH), interpolation=cv2.INTER_LANCZOS4)
        up_method = "lanczos"
        # Real-ESRGAN uniquement sur la REGION TETE: seule elle nous interesse, et
        # un x4 CPU sur un cadre 2048 entier couterait des minutes pour rien.
        m = _esrgan()
        if m is not None and hit is not None:
            hx, hy, hs = head_box(hit, W, H, margin=2.2)
            crop = src[hy : hy + hs, hx : hx + hs]
            if max(crop.shape[:2]) <= ESRGAN_MAX_IN:
                try:
                    up = _run(m, crop, signed=False)  # x4
                    ts = hs * upscale
                    interp = (
                        cv2.INTER_AREA if up.shape[0] > ts else cv2.INTER_LANCZOS4
                    )
                    up = cv2.resize(up, (ts, ts), interpolation=interp)
                    # recollage en fondu (evite une couture de nettete au bord)
                    fm = np.zeros((ts, ts), np.float32)
                    pad = max(2, int(ts * 0.04))
                    fm[pad:-pad, pad:-pad] = 1.0
                    fm = cv2.GaussianBlur(fm, (0, 0), pad * 0.5)[..., None]
                    ox, oy = hx * upscale, hy * upscale
                    dst = full[oy : oy + ts, ox : ox + ts].astype(np.float32)
                    full[oy : oy + ts, ox : ox + ts] = (
                        up.astype(np.float32) * fm + dst * (1.0 - fm)
                    ).astype(np.uint8)
                    up_method = "realesrgan_x4(tete)"
                except Exception as exc:
                    sys.stderr.write("[face_restore] esrgan tete echec: %s\n" % exc)
    else:
        full = src.copy()
        up_method = "none"

    # C: image source -> image agrandie (cadrage strictement identique)
    C = np.array([[upscale, 0, 0], [0, upscale, 0], [0, 0, 1]], dtype=np.float64)
    full, info = _apply_prior(
        bgr, full, C, hit, float(upscale), fidelity, detail, suppress, min_identity,
        allow_download, chroma
    )

    if raw.ndim == 3 and raw.shape[2] == 4:
        a = cv2.resize(raw[:, :, 3], (TW, TH), interpolation=cv2.INTER_LANCZOS4)
        full = np.dstack([full, a])

    os.makedirs(os.path.dirname(os.path.abspath(out_path)) or ".", exist_ok=True)
    cv2.imwrite(out_path, full)

    res = {
        "ok": True,
        "image": image_path,
        "out": out_path,
        "image_size": [W, H],
        "out_size": [TW, TH],
        "scale": float(upscale),
        "framing": "preserved",
        "upscaler": up_method,
        "detector": hit.method if hit else None,
        "bbox": list(hit.bbox) if hit else None,
        "restorer": info["prior"] if info["prior_rejected"] is None else None,
        "identity_cosine": (
            round(info["identity_cosine"], 4)
            if info["identity_cosine"] is not None
            else None
        ),
        "prior_rejected": info["prior_rejected"],
        "merge_sigma": info.get("merge_sigma"),
    }
    return res


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Restauration/super-resolution du visage")
    ap.add_argument("--image", required=True, help="reference plein-pied (ou rendu)")
    ap.add_argument("--output", required=True, help="PNG de sortie")
    ap.add_argument(
        "--mode",
        choices=("crop", "inframe"),
        default="crop",
        help="crop: tete cropee a --target ; inframe: cadrage preserve (bake mesh_sanitize)",
    )
    ap.add_argument("--target", type=int, default=1024)
    ap.add_argument("--upscale", type=int, default=2, help="mode inframe: facteur")
    ap.add_argument("--margin", type=float, default=1.9)
    ap.add_argument(
        "--fidelity",
        type=float,
        default=0.95,
        help="1.0 = basses frequences 100%% reelles (aucune derive d'identite)",
    )
    ap.add_argument("--detail", type=float, default=0.85)
    ap.add_argument("--suppress", type=float, default=0.30)
    ap.add_argument("--min-identity", type=float, default=0.40)
    ap.add_argument("--offline", action="store_true")
    ap.add_argument(
        "--allow-silhouette",
        action="store_true",
        help="repli tete=sommet de silhouette si YuNet echoue (sujet humain CONNU)",
    )
    a = ap.parse_args(argv)

    kw = dict(
        fidelity=a.fidelity,
        detail=a.detail,
        suppress=a.suppress,
        min_identity=a.min_identity,
        allow_download=not a.offline,
        allow_silhouette=a.allow_silhouette,
    )
    try:
        if a.mode == "crop":
            res = restore_face(
                a.image, a.output, target=a.target, margin=a.margin, **kw
            )
        else:
            res = restore_in_frame(a.image, a.output, upscale=a.upscale, **kw)
    except Exception as exc:
        res = {"ok": False, "error": "%s: %s" % (type(exc).__name__, exc)}

    print(json.dumps(res, ensure_ascii=False))
    return 0 if res.get("ok") else 1


if __name__ == "__main__":
    sys.exit(main())
