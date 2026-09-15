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


def _clean_bg_white(bgr):
    """Detoure le sujet (rembg u2net) et le pose sur fond BLANC uni.

    Les vues generees par MV-Adapter ont des fonds sales (taches grises/noires):
    TRELLIS les integre dans la reconstruction -> artefacts (tete, silhouette).
    Fond blanc = meme convention que la reference FLUX. Desactivable:
    AURORA_MV_CLEAN_BG=0. Best-effort: en cas d'echec on garde la vue brute.
    """
    if os.environ.get("AURORA_MV_CLEAN_BG", "1") != "1":
        return bgr
    try:
        import cv2
        import numpy as np
        from rembg import new_session, remove
        global _REMBG_SESSION  # noqa: WPS420 (reutilise entre vues)
        try:
            _REMBG_SESSION
        except NameError:
            _REMBG_SESSION = new_session("u2net")
        rgba = remove(cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB),
                      session=_REMBG_SESSION)
        alpha = rgba[:, :, 3:4].astype("float32") / 255.0
        # GARDE-FOU ANTI-AMPUTATION. Sur une vue deja abimee, rembg ne trouve
        # plus de sujet net et mange des morceaux (constate: vue de profil
        # reduite a une tache jaune trouee, donnee telle quelle a TRELLIS).
        # Si le detourage supprime plus de la moitie de ce qui n'etait pas du
        # fond, ou ne laisse presque rien, on rend la vue BRUTE: une vue avec un
        # fond sale reste exploitable, une vue amputee ne l'est pas.
        _cov = float((alpha > 0.5).mean())
        if _cov < 0.02:
            return bgr
        _rgbf = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB).astype("float32")
        _nonwhite = (_rgbf.min(axis=2) < 235)
        # AMPUTATION vs NETTOYAGE: l'ancien critere comparait le retrait a TOUT
        # le non-blanc — un fond DAMIER (imitation de transparence, ~50% de
        # l'image) faisait passer le nettoyage legitime pour une amputation et
        # la vue restait brute -> rejetee "bords sales" -> mono-vue -> erosion.
        # On ne compte desormais que les retraits de pixels VIFS (satures ou
        # sombres) DANS la boite du sujet: le damier gris clair desature n'en
        # fait pas partie.
        _keep = alpha[:, :, 0] > 0.5
        _ys, _xs = np.nonzero(_keep)
        if len(_xs) < 50:
            return bgr
        _boite = np.zeros_like(_keep)
        _boite[_ys.min():_ys.max() + 1, _xs.min():_xs.max() + 1] = True
        _sat = _rgbf.max(axis=2) - _rgbf.min(axis=2)
        _vif = _nonwhite & ~((_sat < 25) & (_rgbf.mean(axis=2) > 150))
        _retire_vif = float((_vif & ~_keep & _boite).sum())
        _amput = _retire_vif / max(float((_vif & _boite).sum()), 1.0)
        if _amput > 0.35:
            return bgr
        # ETAPE 2b (01/08): l'ALPHA est conserve — le composite blanc jetait
        # le matting et TRELLIS re-detourait a l'aveugle (silhouette fausse).
        return cv2.cvtColor(rgba, cv2.COLOR_RGBA2BGRA)
    except Exception:  # noqa: BLE001
        return bgr


def _split_strip(strip_png: str, out_dir: str, stem: str, pick: list) -> list:
    """Decoupe la bande MV-Adapter (6 vues cote a cote) et ecrit les vues choisies.

    `pick`: indices de vues a garder comme vues SUPPLEMENTAIRES (v2, v3, ...). La vue
    0 (face) n'est PAS reecrite: elle reste la reference d'origine. Chaque vue gardee
    est detouree sur fond blanc (voir _clean_bg_white).
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
        view = _clean_bg_white(im[:, vi * h:(vi + 1) * h])
        p = os.path.join(out_dir, "%s_v%d.png" % (stem, slot))
        cv2.imwrite(p, view)
        outs.append(p)
    return outs


def generate(front_png: str, out_dir: str, stem: str, text: str = "",
             pose_desc: str = "", photo_reelle: bool = False,
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
        # le 4e cote (270 deg) est DEJA calcule dans le strip et etait jete:
        # le flanc/bras gauche restait infere donc lisse ("bras fondus").
        # Cout de calcul nul.
        pick = [2, 3, 4]
    os.makedirs(out_dir, exist_ok=True)
    strip = os.path.join(out_dir, "%s_mvstrip.png" % stem)
    env = {**os.environ,
           "CUDA_HOME": os.environ.get("CUDA_HOME", "/usr/local/cuda-12.8"),
           "HF_HOME": os.environ.get("HF_HOME", os.path.expanduser("~/.cache/huggingface")),
           "PYTHONPATH": MV_ROOT}
    # PAS de PYTORCH_CUDA_ALLOC_CONF=expandable_segments ici: sur ce driver (open
    # kernel module), les tenseurs partent en RAM HOTE au lieu de la VRAM (mesure:
    # VRAM<800M, anon 19.8G -> OOM). Sans: VRAM 11.9G reelle, RAM ~8G.
    env.pop("PYTORCH_CUDA_ALLOC_CONF", None)
    # Offload CPU par defaut: le script vendor plein-GPU culmine a 15.8/16.3 Go
    # (bureau prive de VRAM -> affichage fige). Le runner offload garde UN module
    # a la fois sur le GPU (~5-7 Go), sortie identique. AURORA_MVADAPTER_OFFLOAD=0
    # pour revenir au vendor plein-GPU.
    if os.environ.get("AURORA_MVADAPTER_OFFLOAD", "1") == "1":
        _script = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                               "mvadapter_i2mv_offload.py")
        env["MV_ROOT"] = MV_ROOT
    else:
        _script = os.path.join(MV_ROOT, "scripts", "inference_i2mv_sdxl.py")
    # ANCRAGE DE POSE. Sans lui, i2mv derive vers d'autres poses canoniques du
    # personnage (Sonic debout -> vues de dos EN BOULE, constate sur 3 lots) et
    # assombrit les couleurs. On ancre: meme pose que la reference, debout,
    # couleurs vives, fond uni.
    # 31/07 (recherche): l'ancre FIGEE "standing pose" contredisait la photo
    # (personne allongee) — a CFG 3.0 le texte gagne et i2mv fabrique une
    # AUTRE personne debout. L'ancre decrit desormais la POSE REELLE (fournie
    # par le VLM du pipeline), et les mots "bright vivid colors / studio
    # lighting" ne s'appliquent qu'aux references synthetiques, jamais aux
    # photos reelles.
    _pose = pose_desc.strip() or "exact same pose as the reference"
    _style = ("" if photo_reelle
              else "bright vivid colors, even studio lighting, ")
    _anchor = ("same person, same face, same clothing, %s, full body, %s"
               "plain white background" % (_pose, _style))
    _text = ("%s, %s" % (text, _anchor)) if text else ("high quality, %s" % _anchor)
    cmd = [MV_PY, _script,
           "--image", os.path.abspath(front_png),
           "--text", _text,
           "--output", strip,
           "--num_inference_steps", str(steps), "--seed", str(seed)]
    # leviers anti-derive (etape 4/8b): renforcement de la reference pilote
    # par le pipeline via env, sans changer la signature partout.
    _rs = os.environ.get("AURORA_MV_REF_SCALE")
    if _rs:
        cmd += ["--reference_conditioning_scale", _rs]
    _gs = os.environ.get("AURORA_MV_GUIDANCE")
    if _gs:
        cmd += ["--guidance_scale", _gs]
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
    r = generate(a.front, a.out_dir, a.stem, text=a.text, steps=a.steps,
                 seed=a.seed, pick=a.pick)
    print("AURORA_MVADAPTER_RESULT " + json.dumps(r))
    return 0 if r.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
