#!/usr/bin/env python3
"""Animer une IMAGE IMPORTEE sans deformer les visages.

Le probleme, precisement : un modele video ne "protege" pas un visage. Il
regenere chaque pixel. Un visage se deforme quand il occupe trop peu de pixels
DANS LA RESOLUTION DE GENERATION — pas dans l'image source. Une photo 4000x3000
dont le visage fait 900 px semble confortable, mais si la generation tourne a
960x536, ce visage ne fait plus ~130 px, et en dessous de ce seuil le modele
n'a plus assez de surface pour tenir les traits : les yeux fusionnent, la bouche
derive, l'identite part.

Ce module traite la cause au lieu de rafistoler l'effet :

  1. il MESURE le visage (mediapipe, Apache 2.0 — et non InsightFace qui est
     non-commercial) dans l'image source ;
  2. il PROJETTE sa taille dans la resolution de generation reelle ;
  3. si le visage passe sous le seuil de securite, il agit AVANT de generer :
     recadrage sur le sujet, ou montee de la resolution de generation, ou refus
     explicite — jamais un rendu lance en sachant qu'il va casser ;
  4. il impose une grammaire de mouvement SURE (l'amplitude du mouvement est le
     second facteur de deformation : une rotation de tete rapide detruit un
     visage la ou une derive de camera lente le preserve).

Aucun texte n'est ajoute a l'image (contrat + negative prompt).

Usage :
  python image_to_motion.py --image photo.jpg --output anim.mp4 --motion doux
  python image_to_motion.py --image photo.jpg --output anim.mp4 --check-only
"""

import argparse
import json
import math
import os
import subprocess
import sys

WORKSPACE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VIDEO_GENERATE = os.path.join(WORKSPACE, "python-services", "video_generate.py")

# Seuil mesure : en dessous de ~120 px de cote dans la frame GENEREE, les
# modeles de la famille Wan perdent la structure du visage (yeux fusionnes,
# bouche instable). 160 px est confortable, 200 px est sur.
FACE_MIN_PX = 120
FACE_GOOD_PX = 160
FACE_SAFE_PX = 200

# Grammaire de mouvement classee par risque pour un visage.
MOTIONS = {
    "statique": {
        "prompt": "The camera holds completely still. Only subtle ambient life: "
                  "faint breathing, tiny hair movement, slow light shift.",
        "risk": 0.0,
    },
    "doux": {
        "prompt": "Very slow gentle camera push-in. The subject stays centered "
                  "and keeps the same pose, only breathing and micro-expressions.",
        "risk": 0.15,
    },
    "parallaxe": {
        "prompt": "Slow lateral camera drift revealing depth between foreground "
                  "and background. The subject keeps the same pose and facing.",
        "risk": 0.3,
    },
    "vent": {
        "prompt": "The camera holds nearly still while hair and fabric move "
                  "softly in a light breeze. The face keeps its expression.",
        "risk": 0.25,
    },
    "vivant": {
        "prompt": "The subject makes one small natural movement, a slight head "
                  "turn and a soft blink, while the camera drifts slowly.",
        "risk": 0.55,
    },
    "cinematique": {
        "prompt": "Slow cinematic orbit around the subject with shallow depth "
                  "of field. The subject keeps the same pose and expression.",
        "risk": 0.7,
    },
}

NO_TEXT_NEGATIVE = (
    "text, caption, subtitle, watermark, logo, letters, words, typography, signature"
)
FACE_NEGATIVE = (
    "deformed face, distorted facial features, melting face, asymmetric eyes, "
    "merged eyes, extra eyes, warped mouth, changing identity, morphing face, "
    "plastic skin, uncanny face, extra fingers, deformed hands"
)


def emit(stage, detail=""):
    print(f"PROGRESS:{stage}:{detail}", flush=True)


FACE_MODEL = os.path.join(WORKSPACE, "python-services", "_models",
                          "blaze_face_short_range.tflite")


def detect_faces(image_path):
    """Retourne ((largeur, hauteur), [(x, y, w, h, score)]) en pixels source.

    Detecteur : BlazeFace via l'API `mediapipe.tasks` (ce build de mediapipe
    n'expose PAS l'ancienne API `mp.solutions`). Choix delibere de mediapipe
    plutot qu'InsightFace : InsightFace livre ses modeles pre-entraines sous
    licence *non-commercial research only*, ce qui contaminerait le profil
    commercial. BlazeFace est Apache 2.0.
    """
    import cv2
    import mediapipe as mp
    from mediapipe.tasks.python import vision, BaseOptions

    img = cv2.imread(image_path)
    if img is None:
        raise RuntimeError(f"image illisible : {image_path}")
    h, w = img.shape[:2]
    rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)

    if not os.path.exists(FACE_MODEL):
        raise RuntimeError(
            f"modele de detection absent : {FACE_MODEL}. "
            "Telecharger blaze_face_short_range.tflite depuis "
            "storage.googleapis.com/mediapipe-models/face_detector/"
        )

    detector = vision.FaceDetector.create_from_options(
        vision.FaceDetectorOptions(
            base_options=BaseOptions(model_asset_path=FACE_MODEL),
            min_detection_confidence=0.4,
        )
    )
    faces = []

    def _detect(sub_rgb, off_x=0, off_y=0):
        out = []
        res = detector.detect(
            mp.Image(image_format=mp.ImageFormat.SRGB, data=np.ascontiguousarray(sub_rgb))
        )
        for d in (res.detections or []):
            bb = d.bounding_box
            score = d.categories[0].score if d.categories else 0.0
            out.append((max(0, bb.origin_x + off_x), max(0, bb.origin_y + off_y),
                        max(1, bb.width), max(1, bb.height), float(score)))
        return out

    import numpy as np

    try:
        faces = _detect(rgb)

        # BlazeFace "short range" redimensionne son entree en 128x128 : un
        # visage occupant moins de ~5 % de la largeur devient quelques pixels
        # et devient indetectable. C'est PRECISEMENT le cas dangereux (petit
        # visage dans une grande photo = celui qui se deforme le plus en
        # generation), donc on ne peut pas se contenter de "aucun visage".
        # Repli : detection par tuiles chevauchantes.
        if not faces and min(w, h) >= 512:
            # grilles de plus en plus fines : un visage a 3-4 % de la largeur
            # totale n'est detectable que dans une tuile ou il occupe >15 %.
            for grid in (2, 3, 4, 6):
                tw, th = w // grid, h // grid
                ov_x, ov_y = tw // 4, th // 4
                found = []
                for gy in range(grid):
                    for gx in range(grid):
                        x0 = max(0, gx * tw - ov_x)
                        y0 = max(0, gy * th - ov_y)
                        x1 = min(w, (gx + 1) * tw + ov_x)
                        y1 = min(h, (gy + 1) * th + ov_y)
                        found += _detect(rgb[y0:y1, x0:x1], x0, y0)
                if found:
                    # deduplication : on garde le meilleur score par zone
                    found.sort(key=lambda f: -f[4])
                    kept = []
                    for f in found:
                        if all(abs(f[0] - k[0]) > k[2] * 0.5 or
                               abs(f[1] - k[1]) > k[3] * 0.5 for k in kept):
                            kept.append(f)
                    faces = kept
                    break
    finally:
        # mediapipe leve une TypeError dans son __del__ a la fermeture de
        # l'interpreteur ; on ferme explicitement et on absorbe.
        try:
            detector.close()
        except Exception:
            pass
    return (w, h), faces


def generation_size(src_w, src_h, target_mpix):
    """Resolution de generation reelle : surface plafonnee, ratio conserve,
    dimensions multiples de 32 (exigence des modeles de diffusion)."""
    ratio = math.sqrt(target_mpix * 1e6 / max(1, src_w * src_h))
    gw = max(256, int(src_w * ratio))
    gh = max(256, int(src_h * ratio))
    return gw - gw % 32, gh - gh % 32


def analyse(image_path, target_mpix, motion):
    (sw, sh), faces = detect_faces(image_path)
    gw, gh = generation_size(sw, sh, target_mpix)
    scale = gw / sw

    report = {
        "source_resolution": f"{sw}x{sh}",
        "generation_resolution": f"{gw}x{gh}",
        "scale_source_to_generation": round(scale, 4),
        "faces_detected": len(faces),
        "faces": [],
        "motion": motion,
        "motion_risk": MOTIONS[motion]["risk"],
    }

    worst = None
    for (x, y, fw, fh, score) in faces:
        face_px_src = min(fw, fh)
        face_px_gen = face_px_src * scale
        verdict = ("sur" if face_px_gen >= FACE_SAFE_PX else
                   "bon" if face_px_gen >= FACE_GOOD_PX else
                   "limite" if face_px_gen >= FACE_MIN_PX else "insuffisant")
        report["faces"].append({
            "box_source": [x, y, fw, fh],
            "confidence": round(score, 3),
            "face_px_source": face_px_src,
            "face_px_generation": round(face_px_gen, 1),
            "verdict": verdict,
        })
        if worst is None or face_px_gen < worst:
            worst = face_px_gen

    report["smallest_face_px_generation"] = round(worst, 1) if worst else None

    warnings = []
    if not faces:
        report["face_verdict"] = "aucun_visage"
        warnings.append(
            "Aucun visage detecte : la garde faciale ne s'applique pas. "
            "Si l'image contient pourtant un visage (profil marque, masque, "
            "stylisation forte), traite le resultat avec prudence."
        )
    else:
        if worst >= FACE_SAFE_PX:
            report["face_verdict"] = "sur"
        elif worst >= FACE_GOOD_PX:
            report["face_verdict"] = "bon"
        elif worst >= FACE_MIN_PX:
            report["face_verdict"] = "limite"
            warnings.append(
                f"Le plus petit visage fera {worst:.0f} px en generation "
                f"(confortable a partir de {FACE_GOOD_PX}). Deformation possible : "
                "recadre plus serre, ou monte --target-mpix."
            )
        else:
            report["face_verdict"] = "insuffisant"
            warnings.append(
                f"Le plus petit visage ne fera que {worst:.0f} px en generation, "
                f"sous le seuil de {FACE_MIN_PX} px. La deformation est PROBABLE. "
                "Recadre sur le sujet (--crop-to-face) ou monte --target-mpix."
            )
        if MOTIONS[motion]["risk"] >= 0.5 and worst < FACE_SAFE_PX:
            warnings.append(
                f"Le mouvement '{motion}' est ample (risque "
                f"{MOTIONS[motion]['risk']}) alors que le visage est sous "
                f"{FACE_SAFE_PX} px : prefere 'doux' ou 'statique'."
            )
    report["warnings"] = warnings
    return report


def crop_to_face(image_path, out_path, faces, src_wh, margin=2.2):
    """Recadre autour des visages pour leur donner plus de surface.

    C'est le levier le plus efficace et le moins couteux : recadrer x2 double
    la taille du visage dans la frame generee, sans rien changer au modele.
    """
    from PIL import Image

    sw, sh = src_wh
    xs = [f[0] for f in faces]
    ys = [f[1] for f in faces]
    xe = [f[0] + f[2] for f in faces]
    ye = [f[1] + f[3] for f in faces]
    cx, cy = (min(xs) + max(xe)) / 2, (min(ys) + max(ye)) / 2
    fw, fh = max(xe) - min(xs), max(ye) - min(ys)
    half = max(fw, fh) * margin / 2
    # on garde le ratio de l'image d'origine
    ratio = sw / sh
    hw = half * max(1.0, ratio)
    hh = half * max(1.0, 1 / ratio)
    x0, y0 = int(max(0, cx - hw)), int(max(0, cy - hh))
    x1, y1 = int(min(sw, cx + hw)), int(min(sh, cy + hh))
    if x1 - x0 < 64 or y1 - y0 < 64:
        return image_path
    Image.open(image_path).convert("RGB").crop((x0, y0, x1, y1)).save(out_path)
    return out_path


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--image", required=True)
    ap.add_argument("--output", default="")
    ap.add_argument("--prompt", default="", help="ce qui doit se passer (optionnel)")
    ap.add_argument("--motion", default="doux", choices=sorted(MOTIONS))
    ap.add_argument("--seconds", type=float, default=4.0)
    ap.add_argument("--target-mpix", type=float, default=0.51,
                    help="surface de generation (0.51 = mesure du pipeline)")
    ap.add_argument("--quality-mode", default="premium",
                    choices=["auto", "balanced", "premium"])
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--crop-to-face", action="store_true",
                    help="recadre sur le sujet pour agrandir le visage")
    ap.add_argument("--auto-protect", action="store_true", default=True,
                    help="recadre et adoucit le mouvement automatiquement si besoin")
    ap.add_argument("--allow-text", action="store_true")
    ap.add_argument("--check-only", action="store_true",
                    help="analyse la faisabilite sans rien generer")
    args = ap.parse_args()

    image = os.path.abspath(args.image)
    if not os.path.exists(image):
        print(json.dumps({"ok": False, "error": f"introuvable : {image}"}))
        return 1

    emit("analyse", "detection et mesure des visages")
    report = analyse(image, args.target_mpix, args.motion)
    (sw, sh), faces = detect_faces(image)

    motion = args.motion
    used_image = image
    actions = []

    # Protection automatique : on agit AVANT de bruler du GPU.
    if args.auto_protect and faces:
        if report["face_verdict"] in {"insuffisant", "limite"} or args.crop_to_face:
            cropped = os.path.splitext(image)[0] + "_crop_visage.png"
            new_img = crop_to_face(image, cropped, faces, (sw, sh))
            if new_img != image:
                used_image = new_img
                actions.append(f"recadrage sur le sujet -> {os.path.basename(new_img)}")
                report = analyse(used_image, args.target_mpix, motion)
        if report["face_verdict"] in {"insuffisant", "limite"} and \
                MOTIONS[motion]["risk"] > 0.2:
            motion = "doux" if report["face_verdict"] == "limite" else "statique"
            actions.append(f"mouvement adouci -> '{motion}' (visage fragile)")
            report["motion"] = motion
            report["motion_risk"] = MOTIONS[motion]["risk"]

    report["auto_actions"] = actions
    report["image_used"] = used_image

    if args.check_only:
        print(json.dumps({"ok": True, "check_only": True, **report},
                         ensure_ascii=False, indent=2))
        return 0

    if report["face_verdict"] == "insuffisant":
        print(json.dumps({
            "ok": False,
            "error": "visage trop petit pour une animation sans deformation",
            "conseil": "recadre sur le sujet, ou augmente --target-mpix",
            **report}, ensure_ascii=False, indent=2))
        return 2

    out = os.path.abspath(args.output or (os.path.splitext(image)[0] + "_anime.mp4"))
    gw, gh = [int(v) for v in report["generation_resolution"].split("x")]
    frames = max(25, min(97, int(round(args.seconds * 24))))

    subject = args.prompt.strip() or "the subject of the reference image"
    prompt = (
        f"{subject}. {MOTIONS[motion]['prompt']} "
        "Preserve the exact identity, facial features, proportions, clothing "
        "and colors of the reference image. Photographic continuity with the "
        "reference. No text of any kind in frame."
    )
    negative = FACE_NEGATIVE + ", " + (
        "" if args.allow_text else NO_TEXT_NEGATIVE)

    cmd = [sys.executable, VIDEO_GENERATE,
           "--prompt", prompt,
           "--negative_prompt", negative,
           "--image", used_image,
           "--output", out,
           "--thumbnail", os.path.splitext(out)[0] + ".png",
           "--width", str(gw), "--height", str(gh),
           "--num_frames", str(frames),
           "--vram_gb", "16",
           "--quality_mode", args.quality_mode,
           "--motion_interp", "1"]
    if args.seed:
        cmd += ["--seed", str(args.seed)]

    emit("generation", f"i2v {gw}x{gh}, {frames} frames, mouvement '{motion}'")
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=14400)
    tail = (proc.stdout or "").strip().split("\n")
    gen = {}
    for line in reversed(tail):
        line = line.strip()
        if line.startswith("{"):
            try:
                gen = json.loads(line)
                break
            except Exception:
                pass

    result = {
        "ok": bool(gen.get("ok")) and os.path.exists(out),
        "path": out if os.path.exists(out) else None,
        "face_guard": report,
        "motion_used": motion,
        "generation": {k: gen.get(k) for k in
                       ("strategy", "model", "elapsed_seconds", "validation_summary")},
        "text_in_frame": bool(args.allow_text),
    }
    if not result["ok"]:
        result["error"] = gen.get("error") or (proc.stderr or "")[-800:]
    emit("done", out)
    print(json.dumps(result, ensure_ascii=False))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
