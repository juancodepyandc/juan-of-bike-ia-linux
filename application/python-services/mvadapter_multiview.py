"""mvadapter_multiview.py — vues cohérentes d'un sujet pour la reconstruction multi-vues.

Une seule image est AMBIGUE en profondeur: TRELLIS.2 mono-vue reconstruit mal tout
ce qui sort de la pose canonique (un humain ASSIS ressort penche en avant ou
effondre; le DOS et les MAINS sont hallucines). L'etat de l'art (PSHuman, MExECON)
et la doc TRELLIS le disent: plus il y a de vues, moins il y a d'ambiguite.

Le piege: des vues generees INDEPENDAMMENT (img2img "vue de dos") ne sont pas
coherentes entre elles -> fusion incoherente -> double-visage. Il faut de VRAIES
vues multi-angles du MEME sujet. MV-Adapter (i2mv) fait exactement ca: depuis une
image, il diffuse 6 vues GEOMETRIQUEMENT COHERENTES (meme personne, meme pose,
memes vetements) autour de l'objet. On les donne ensuite a TRELLIS.2 multi-vues.

Verifie: un homme assis, mono-vue = penche/effondre; multi-vues MV-Adapter = assis
propre sous tous les angles (cuisses horizontales, tibias verticaux, pieds au sol).

Sort les vues supplementaires nommees `<ref_stem>_v2.png`, `<ref_stem>_v3.png`, ...
que le pipeline passe a TRELLIS.2 quand AURORA_TRELLIS2_MULTIVIEW=1.

Usage:
    python mvadapter_multiview.py <front.png> --out-dir DIR --stem RUN [--text "..."]
"""

from __future__ import annotations

import json
import os
import subprocess
import sys

MV_ROOT = os.path.expanduser("~/.local/share/auroraia/external/MV-Adapter")
MV_PY = os.environ.get(
    "AURORA_MVADAPTER_PY",
    os.path.expanduser("~/.local/opt/miniforge3/envs/mvadapter/bin/python"))
# angles produits par MV-Adapter i2mv (deg): face, 3/4, profil, dos, profil, 3/4
_AZ = [0, 45, 90, 180, 270, 315]


def available() -> bool:
    return (os.path.isdir(MV_ROOT)
            and os.path.isfile(os.path.join(MV_ROOT, "scripts", "inference_i2mv_sdxl.py"))
            and os.path.isfile(MV_PY))


def _split_strip(strip_png: str, out_dir: str, stem: str, pick: list) -> list:
    """Decoupe la bande MV-Adapter (6 vues cote a cote) et ecrit les vues choisies.

    `pick`: indices de vues a garder comme vues SUPPLEMENTAIRES (v2, v3, ...). La vue
    0 (face) n'est PAS reecrite: elle reste la reference d'origine.
    """
    import cv2

    im = cv2.imread(strip_png)
    if im is None:
        return []
    h = im.shape[0]
    n = max(1, im.shape[1] // h)
    outs = []
    for slot, vi in enumerate(pick, start=2):
        if vi >= n:
            continue
        view = im[:, vi * h:(vi + 1) * h]
        p = os.path.join(out_dir, "%s_v%d.png" % (stem, slot))
        cv2.imwrite(p, view)
        outs.append(p)
    return outs


def generate(front_png: str, out_dir: str, stem: str, text: str = "",
             steps: int = 40, seed: int = 42,
             pick: list | None = None) -> dict:
    """Genere les vues coherentes et ecrit <stem>_v2.png, <stem>_v3.png, ...

    pick: quelles vues (indices 0..5) garder comme supplementaires. Defaut: profil
    (2) et dos (3) - le couple qui apporte le plus d'info a TRELLIS (profondeur
    laterale + face cachee). On peut en ajouter (3/4=1) si on veut plus de vues.
    """
    if not available():
        return {"ok": False, "error": "MV-Adapter indisponible (%s)" % MV_ROOT}
    if pick is None:
        pick = [2, 3]
    os.makedirs(out_dir, exist_ok=True)
    strip = os.path.join(out_dir, "%s_mvstrip.png" % stem)
    env = {**os.environ,
           "CUDA_HOME": os.environ.get("CUDA_HOME", "/usr/local/cuda-12.8"),
           "HF_HOME": os.environ.get("HF_HOME", os.path.expanduser("~/.cache/huggingface")),
           "PYTHONPATH": MV_ROOT}
    cmd = [MV_PY, os.path.join(MV_ROOT, "scripts", "inference_i2mv_sdxl.py"),
           "--image", os.path.abspath(front_png),
           "--text", text or "high quality, photorealistic, plain background",
           "--output", strip,
           "--num_inference_steps", str(steps), "--seed", str(seed)]
    try:
        r = subprocess.run(cmd, cwd=MV_ROOT, env=env, capture_output=True,
                           text=True, timeout=1200)
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": "i2mv subprocess: %r" % exc}
    if not os.path.isfile(strip):
        tail = (r.stderr or r.stdout or "")[-300:]
        return {"ok": False, "error": "i2mv sans sortie: %s" % tail}
    views = _split_strip(strip, out_dir, stem, pick)
    if not views:
        return {"ok": False, "error": "decoupage des vues echoue"}
    return {"ok": True, "views": views, "strip": strip,
            "azimuths": [_AZ[i] for i in pick if i < len(_AZ)]}


def main() -> int:
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("front")
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--stem", required=True)
    ap.add_argument("--text", default="")
    ap.add_argument("--steps", type=int, default=40)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--pick", type=int, nargs="+", default=[2, 3])
    a = ap.parse_args()
    r = generate(a.front, a.out_dir, a.stem, a.text, a.steps, a.seed, a.pick)
    print("AURORA_MVADAPTER_RESULT " + json.dumps(r))
    return 0 if r.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
