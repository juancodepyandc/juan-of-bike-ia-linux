#!/usr/bin/env python3
"""Etalonnage commun a tout un film : les plans doivent partager une lumiere.

LE DEFAUT QU'IL CORRIGE
-----------------------
Chaque plan est genere independamment. Meme avec la meme description de lieu et
le meme style, Wan rend un plan legerement plus chaud, le suivant plus froid,
un troisieme plus contraste. Isolement chaque plan est correct ; mis bout a
bout, l'oeil lit une rupture a chaque coupe — « aucune reelle coherence entre
les scenes ». Aucun reglage de generation ne corrige cela, parce que le defaut
n'existe QUE dans la relation entre les plans.

En production, c'est le role de l'etalonnage : on ramene tous les plans sur une
meme reference. Ici la reference est la MEDIANE du film lui-meme (et non le
premier plan, qui pourrait etre l'aberrant) : le film se cale sur son propre
centre de gravite.

POURQUOI UNE CORRECTION PARTIELLE
---------------------------------
Aligner totalement les statistiques effacerait les variations VOULUES — un plan
en contre-jour doit rester plus chaud qu'un plan a l'ombre. On corrige donc
d'une fraction (0,65 par defaut) : assez pour supprimer la rupture, pas assez
pour aplatir la mise en lumiere.

Usage :
  python film_grade.py --measure plan1.mp4 plan2.mp4
  python film_grade.py --harmonise plan1.mp4 plan2.mp4 --out-dir etalonnes/
"""

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

# Fraction de l'ecart corrige. 1.0 = alignement total (aplatit la mise en
# lumiere), 0.0 = aucun effet.
DEFAULT_STRENGTH = 0.65
# Nombre d'images echantillonnees par plan pour la mesure : au-dela, la mesure
# ne bouge plus et le cout grimpe.
SAMPLE_FRAMES = 12
# Garde-fou : au-dela, ce n'est plus une harmonisation mais une recolorisation,
# signe que les plans n'ont rien a voir (lieux differents) — on s'abstient.
MAX_GAIN = 1.35
MIN_GAIN = 0.74
# Plafond du decalage de moyenne. Mesure sur un film reel : l'ecart entre le
# plan le plus clair et le plus sombre atteignait 0,52 sur 1. Combler un tel
# ecart d'un coup ecraserait les hautes lumieres du plan sombre (tout ce qui
# depasse 1 - decalage devient blanc). On rapproche donc de 12 % au maximum :
# assez pour effacer la rupture a la coupe, pas assez pour detruire une image.
MAX_OFFSET = 0.12


def emit(stage: str, detail: str = ""):
    print(f"PROGRESS:{stage}:{detail}", flush=True)


def _ffmpeg() -> str:
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        return shutil.which("ffmpeg") or "ffmpeg"


def measure_shot(path: str, samples: int = SAMPLE_FRAMES) -> dict:
    """Moyenne et ecart-type par canal, sur des images reparties dans le plan.

    On echantillonne au lieu de tout lire : la dominante d'un plan est stable,
    et lire 150 images pour la mesurer coute sans rien apporter.
    """
    try:
        import cv2
        import numpy as np
    except Exception as exc:
        return {"ok": False, "error": f"opencv/numpy absents: {str(exc)[:100]}"}

    cap = cv2.VideoCapture(str(path))
    if not cap.isOpened():
        return {"ok": False, "error": f"illisible: {path}"}
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    if total <= 0:
        cap.release()
        return {"ok": False, "error": f"aucune image: {path}"}

    idxs = [int(total * (i + 0.5) / samples) for i in range(min(samples, total))]
    means, stds = [], []
    for i in idxs:
        cap.set(cv2.CAP_PROP_POS_FRAMES, i)
        ok, frame = cap.read()
        if not ok or frame is None:
            continue
        f = frame.astype("float32") / 255.0
        means.append(f.reshape(-1, 3).mean(axis=0))
        stds.append(f.reshape(-1, 3).std(axis=0))
    cap.release()
    if not means:
        return {"ok": False, "error": f"aucune image lisible: {path}"}

    import numpy as np
    return {
        "ok": True,
        "path": str(path),
        "frames": total,
        # BGR (convention OpenCV) -> on garde l'ordre, la correction est
        # appliquee dans le meme espace.
        "mean": [float(x) for x in np.mean(means, axis=0)],
        "std": [float(x) for x in np.mean(stds, axis=0)],
    }


def film_reference(measures: list) -> dict:
    """Centre de gravite du film : la mediane, pas la moyenne.

    Si un plan sur quatre part dans une dominante, la moyenne le suit a moitie
    et contamine les trois autres ; la mediane l'ignore.
    """
    import numpy as np
    good = [m for m in measures if m.get("ok")]
    if not good:
        return {"ok": False, "error": "aucune mesure exploitable"}
    return {
        "ok": True,
        "mean": [float(x) for x in np.median([m["mean"] for m in good], axis=0)],
        "std": [float(x) for x in np.median([m["std"] for m in good], axis=0)],
        "shots": len(good),
    }


def correction_for(measure: dict, reference: dict,
                   strength: float = DEFAULT_STRENGTH) -> dict:
    """Gain et decalage par canal ramenant partiellement le plan sur la reference.

    out = gain * in + offset, avec gain qui rapproche l'ecart-type et offset qui
    rapproche la moyenne. `strength` dose l'ensemble.
    """
    gains, offsets = [], []
    for c in range(3):
        m, s = measure["mean"][c], max(measure["std"][c], 1e-4)
        mr, sr = reference["mean"][c], max(reference["std"][c], 1e-4)
        g = 1.0 + strength * ((sr / s) - 1.0)
        g = max(MIN_GAIN, min(MAX_GAIN, g))
        shift = strength * (mr - m)
        shift = max(-MAX_OFFSET, min(MAX_OFFSET, shift))
        target_m = m + shift
        gains.append(g)
        offsets.append(target_m - g * m)
    return {"gain": gains, "offset": offsets}


def is_noop(correction: dict, tolerance: float = 0.012) -> bool:
    """Correction imperceptible : ne pas reencoder pour rien.

    Reencoder coute une generation de perte de qualite ; si le plan est deja
    dans la lumiere du film, on le laisse tel quel.
    """
    return all(abs(g - 1.0) <= tolerance for g in correction["gain"]) and \
        all(abs(o) <= tolerance for o in correction["offset"])


def _filter_string(correction: dict) -> str:
    """Traduit gain/offset en filtre ffmpeg.

    `colorlevels` applique une rampe lineaire par canal. On resout les bornes
    d'entree qui donnent 0 et 1 en sortie : imin = -offset/gain,
    imax = (1 - offset)/gain. ffmpeg accepte des bornes hors [0,1], ce qui
    permet d'exprimer un gain < 1 comme un > 1.
    """
    # ffmpeg nomme les canaux r/g/b ; OpenCV mesure en BGR -> on reordonne.
    b, g_, r = correction["gain"]
    ob, og, orr = correction["offset"]
    parts = []
    for name, gain, off in (("r", r, orr), ("g", g_, og), ("b", b, ob)):
        imin = -off / gain
        imax = (1.0 - off) / gain
        imin = max(-1.0, min(1.0, imin))
        imax = max(-1.0, min(1.0, imax))
        if imax - imin < 1e-3:
            imax = imin + 1e-3
        parts.append(f"{name}imin={imin:.5f}:{name}imax={imax:.5f}")
    return "colorlevels=" + ":".join(parts)


def apply_correction(path: str, correction: dict, output_mp4: str,
                     crf: int = 16) -> dict:
    """Reencode le plan avec la correction. L'audio est copie sans retouche."""
    vf = _filter_string(correction) + ",format=yuv420p"
    cmd = [_ffmpeg(), "-v", "error", "-y", "-i", str(path),
           "-vf", vf, "-c:v", "libx264", "-crf", str(crf), "-preset", "slow",
           "-c:a", "copy", str(output_mp4)]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=1800)
    if proc.returncode != 0 or not Path(output_mp4).exists():
        return {"ok": False, "error": (proc.stderr or "")[-300:]}
    return {"ok": True, "mp4": str(output_mp4), "filter": vf}


def harmonise(shot_files: list, out_dir: str,
              strength: float = DEFAULT_STRENGTH) -> dict:
    """Ramene tous les plans sur la lumiere mediane du film.

    Ne remplace JAMAIS un plan par un echec : si la mesure ou le reencodage
    echoue, le plan d'origine est conserve tel quel.
    """
    measures = [measure_shot(p) for p in shot_files]
    failed = [m.get("error") for m in measures if not m.get("ok")]
    ref = film_reference(measures)
    if not ref.get("ok"):
        return {"ok": False, "error": ref.get("error"), "files": list(shot_files)}

    Path(out_dir).mkdir(parents=True, exist_ok=True)
    out_files, applied, skipped = [], 0, 0
    for path, m in zip(shot_files, measures):
        if not m.get("ok"):
            out_files.append(path)
            skipped += 1
            continue
        corr = correction_for(m, ref, strength)
        if is_noop(corr):
            out_files.append(path)
            skipped += 1
            continue
        dst = Path(out_dir) / (Path(path).stem + "_etalonne.mp4")
        res = apply_correction(path, corr, str(dst))
        if res.get("ok"):
            out_files.append(str(dst))
            applied += 1
        else:
            emit("grade_warn", f"{Path(path).name}: {str(res.get('error'))[:100]}")
            out_files.append(path)
            skipped += 1

    emit("grade", f"{applied} plan(s) harmonise(s), {skipped} inchange(s) "
                  f"(force {strength})")
    return {"ok": True, "files": out_files, "applied": applied,
            "skipped": skipped, "reference": ref,
            "measure_errors": failed}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--measure", nargs="+")
    ap.add_argument("--harmonise", nargs="+")
    ap.add_argument("--out-dir", default="")
    ap.add_argument("--strength", type=float, default=DEFAULT_STRENGTH)
    args = ap.parse_args()

    if args.measure:
        ms = [measure_shot(p) for p in args.measure]
        print(json.dumps({"measures": ms, "reference": film_reference(ms)},
                         ensure_ascii=False, indent=2), flush=True)
        return 0
    if args.harmonise:
        out = args.out_dir or str(Path(args.harmonise[0]).parent / "etalonnes")
        res = harmonise(args.harmonise, out, args.strength)
        print(json.dumps(res, ensure_ascii=False), flush=True)
        return 0 if res.get("ok") else 1
    print(json.dumps({"ok": False, "error": "--measure ou --harmonise requis"}))
    return 1


if __name__ == "__main__":
    sys.exit(main())
