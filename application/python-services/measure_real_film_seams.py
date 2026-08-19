"""Mesure les seam_delta réels entre plans consécutifs d'un film cinema_pipeline.

Contrairement au banc d'isolation qui construit synthétiquement A/B, ici on
lit les .mp4 EFFECTIVEMENT rendus par cinema_pipeline dans son job dir, on
prend la dernière frame de chaque plan et la première du suivant, on mesure
|last(N) - first(N+1)| en niveaux [0..1]. C'est le vrai chiffre — celui qui
correspond à ce que l'œil voit à la coupe.

Rapporte aussi, pour chaque transition :
- si le plan N+1 a bénéficié d'un anchor tenseur (existence du sibling
  `<basename>_lastframe.png` sur disque),
- si le triplet extract_keyframes_triplet a effectivement produit tensor_lastframe.

Usage :
    /home/juan/AuroraIA/application/.venv/bin/python \\
        /home/juan/AuroraIA/application/python-services/measure_real_film_seams.py \\
        --job 828ffe68bf9a4a48
    ou --job-dir /chemin/vers/job_XXX/
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE / "cinema"))


def _measure_seam(prev_mp4: Path, next_mp4: Path) -> float | None:
    import cv2
    if not prev_mp4.exists() or not next_mp4.exists():
        return None
    c1 = cv2.VideoCapture(str(prev_mp4))
    c2 = cv2.VideoCapture(str(next_mp4))
    try:
        n1 = int(c1.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
        if n1 == 0:
            return None
        c1.set(cv2.CAP_PROP_POS_FRAMES, n1 - 1)
        ok1, f1 = c1.read()
        c2.set(cv2.CAP_PROP_POS_FRAMES, 0)
        ok2, f2 = c2.read()
        if not ok1 or not ok2:
            return None
        if f1.shape != f2.shape:
            f2 = cv2.resize(f2, (f1.shape[1], f1.shape[0]))
        import numpy as np
        a = f1.astype("float32") / 255.0
        b = f2.astype("float32") / 255.0
        return float(np.abs(a - b).mean())
    finally:
        c1.release()
        c2.release()


def _find_shot_mp4s(job_dir: Path) -> list[Path]:
    """Ordre stable : shot_01_*.mp4, shot_02_*.mp4, ...

    Priorité aux fichiers montés (`_synced.mp4` pour les plans lipsyncés)
    quand ils existent, sinon `_silent.mp4` — c'est l'ordre exact de ce que
    l'utilisateur voit à la coupe entre plans.
    """
    all_shots: dict[int, Path] = {}
    for mp4 in sorted(job_dir.glob("shot_*_silent.mp4")):
        try:
            n = int(mp4.stem.split("_")[1])
        except (ValueError, IndexError):
            continue
        all_shots[n] = mp4
    # override with _synced.mp4 when present (lipsynced version wins)
    for mp4 in sorted(job_dir.glob("shot_*_synced.mp4")):
        try:
            n = int(mp4.stem.split("_")[1])
        except (ValueError, IndexError):
            continue
        all_shots[n] = mp4
    return [all_shots[k] for k in sorted(all_shots)]


def _tensor_lastframe_status(mp4: Path) -> str:
    """Vérifie la présence du sibling `_lastframe.png` (dump tenseur du worker
    vidéo, ajouté par le patch du 2026-08-07 dans video_generate.py). Retourne
    'present', 'absent', ou 'unreadable'."""
    sibling = mp4.with_suffix("").as_posix() + "_lastframe.png"
    p = Path(sibling)
    if p.exists() and p.stat().st_size > 0:
        return "present"
    return "absent"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--job", type=str, default=None, help="job id (job_dir dérivé de temp/cinema/)")
    ap.add_argument("--job-dir", type=str, default=None, help="chemin absolu du job dir")
    args = ap.parse_args()

    if args.job_dir:
        job_dir = Path(args.job_dir)
    elif args.job:
        job_dir = Path("/home/juan/AuroraIA/application/temp/cinema") / f"job_{args.job}"
    else:
        print("--job or --job-dir required", file=sys.stderr)
        sys.exit(2)

    if not job_dir.exists():
        print(f"job dir not found: {job_dir}", file=sys.stderr)
        sys.exit(3)

    shots = _find_shot_mp4s(job_dir)
    if len(shots) < 2:
        print(f"only {len(shots)} shot mp4(s) found — need at least 2 to measure a seam", file=sys.stderr)
        sys.exit(4)

    print(f"# Mesure des seams réels — job {job_dir.name}")
    print(f"# {len(shots)} plans détectés")
    print()
    print(f"| plan | fichier | tensor_lastframe.png |")
    print(f"|------|---------|----------------------|")
    for s in shots:
        print(f"| {s.stem} | {s.name} | {_tensor_lastframe_status(s)} |")
    print()
    print(f"| transition | seam_delta | ancre A→B disponible pour B |")
    print(f"|------------|-----------|-----------------------------|")
    total = 0.0
    n = 0
    for a, b in zip(shots, shots[1:]):
        seam = _measure_seam(a, b)
        anchor = _tensor_lastframe_status(a)  # what B could have anchored ON
        s = f"{seam:.5f}" if seam is not None else "N/A"
        print(f"| {a.stem} → {b.stem} | {s} | {anchor} |")
        if seam is not None:
            total += seam
            n += 1
    if n > 0:
        print()
        print(f"**seam moyen sur {n} transitions : {total/n:.5f}**")

    # Cross-check contre la mesure isolation (2026-08-07 prod_continuity):
    print()
    print("Rappel banc d'isolation prod (832×480×65f×60steps, plan A→B) :")
    print("  ancré tensor video[-1] : 0.01048")
    print("  ancré end naïf         : 0.01777")
    print("  ancré sharp_end        : 0.02732")
    print("  aucun ancrage          : 0.02781")


if __name__ == "__main__":
    main()
