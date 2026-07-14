#!/usr/bin/env bash
# Compare la NETTETE DU VISAGE de deux GLB a travers le VRAI viewer (gros plan tete).
# AZ0 = azimut de la vraie face (donne par face_refine: front_azimuth).
# Usage: AZ0=45 compare_head.sh <avant.glb> <apres.glb>
set -e
cd "$(dirname "$0")"
A="$1"; B="$2"
export AZ0="${AZ0:-0}"
HEAD=1 node drive_view.mjs "$A" /tmp/cmp_head/avant avant >/dev/null
HEAD=1 node drive_view.mjs "$B" /tmp/cmp_head/apres apres >/dev/null
/home/juan/AuroraIA/application/.venv/bin/python - <<'PY'
import cv2, numpy as np, os, sys
sys.path.insert(0, "/home/juan/AuroraIA/application/python-services")
import face_restore

for ang in ("face", "a30", "aneg30"):
    pa = f"/tmp/cmp_head/avant/avant_{ang}.png"
    pb = f"/tmp/cmp_head/apres/apres_{ang}.png"
    if not (os.path.exists(pa) and os.path.exists(pb)):
        continue
    a = cv2.imread(pa); b = cv2.imread(pb)
    ga = cv2.cvtColor(a, cv2.COLOR_BGR2GRAY); gb = cv2.cvtColor(b, cv2.COLOR_BGR2GRAY)
    # zone de mesure = le VISAGE detecte (pas tout le crane: les cheveux et le col
    # ne sont pas touches et diluent la mesure)
    hit = face_restore.detect_face_bbox(pa, allow_silhouette=False)
    if hit is not None:
        x, y, w, h = [int(v) for v in hit.bbox]
        pad = int(0.15 * max(w, h))
        x0, y0 = max(0, x - pad), max(0, y - pad)
        x1, y1 = min(ga.shape[1], x + w + pad), min(ga.shape[0], y + h + pad)
        m = np.zeros(ga.shape, np.uint8); m[y0:y1, x0:x1] = 1
        zone = f"visage {x1-x0}x{y1-y0}px"
    else:
        m = (ga > 12).astype(np.uint8); zone = "sujet (aucun visage detecte)"
    la = cv2.Laplacian(ga, cv2.CV_64F); lb = cv2.Laplacian(gb, cv2.CV_64F)
    sa = la[m > 0].var(); sb = lb[m > 0].var()
    d = cv2.absdiff(a, b).max(axis=2)
    dz = d[m > 0]
    print(f"{ang:7s} [{zone}] nettete {sa:7.1f} -> {sb:7.1f}  ({100*(sb-sa)/max(sa,1e-6):+5.1f}%) | "
          f"pixels changes>8: {100.0*(dz>8).mean():5.2f}%  ecart moyen {dz.mean():.2f}/255")
PY
