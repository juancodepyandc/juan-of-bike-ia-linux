#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""hymotion_generate — texte libre -> mouvement humain (HY-Motion 1.0).

Pourquoi ce module existe: la bibliotheque de prefixages couvre 28 gestes
nommes (marcher, courir, s'asseoir, frapper...). Tout ce qui sort de cette
liste — un mouvement invente, une choregraphie decrite en trois phrases, un
enchainement precis — ne trouvait AUCUNE correspondance et ne produisait rien.
HY-Motion genere le mouvement directement depuis la description, sans
vocabulaire a maintenir.

Deux pieges evites:
  - le `requirements.txt` du depot epingle `torch==2.5.1`, qui NE CONNAIT PAS
    l'architecture Blackwell (sm_120). On utilise l'interpreteur de l'app, qui
    a torch 2.11+cu128 avec sm_120. Ne jamais suivre l'epinglage.
  - la reecriture de texte et l'estimation de duree appellent un Qwen3-8B
    supplementaire (plusieurs Go). On les desactive: la description de
    l'utilisateur est deja ce qu'il veut, et la duree lui appartient.

Usage:
    python hymotion_generate.py --prompt "un homme esquive puis contre-attaque" \
        --output-dir <dir> [--duration 4.0] [--seeds 1] [--cfg 5.0]

Sortie: JSON sur stdout {ok, files[], elapsed_s, ...}.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

HY_ROOT = Path(os.environ.get(
    "AURORA_HYMOTION_ROOT",
    Path.home() / ".local/share/auroraia/external/HY-Motion"))
REPO_ROOT = Path(__file__).resolve().parents[2]


def _python() -> str:
    """Interpreteur qui a torch cu128 (Blackwell), pas celui du depot."""
    env = os.environ.get("AURORA_HYMOTION_PY")
    if env:
        return env
    venv = REPO_ROOT / "application" / ".venv" / "bin" / "python"
    return str(venv) if venv.is_file() else sys.executable


def _model_path() -> Path | None:
    """Checkpoint HY-Motion, ou None s'il n'est pas la."""
    for cand in (HY_ROOT / "ckpts" / "tencent" / "HY-Motion-1.0",
                 HY_ROOT / "ckpts" / "HY-Motion-1.0"):
        if (cand / "latest.ckpt").is_file():
            return cand
    return None


def available() -> tuple[bool, str]:
    if not (HY_ROOT / "local_infer.py").is_file():
        return False, "HY-Motion absent (%s)" % HY_ROOT
    if _model_path() is None:
        return False, "checkpoint HY-Motion introuvable sous %s/ckpts" % HY_ROOT
    return True, ""


def generate(prompt: str, output_dir: str, *, duration: float = 4.0,
             seeds: int = 1, cfg_scale: float = 5.0,
             timeout_s: int = 1800) -> dict:
    ok, why = available()
    if not ok:
        return {"ok": False, "error": why}
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    # local_infer lit un DOSSIER de fichiers texte, pas un prompt direct.
    # Syntaxe native "texte#duree": sans suffixe c'est 150 frames (~5 s) —
    # une sequence complete (macarena ~12-16 s) etait TRONQUEE au premier
    # geste. La duree vient de la structure du geste (resolveur), pas d'une
    # constante.
    tmp = Path(tempfile.mkdtemp(prefix="hymotion_txt_"))
    _ligne = " ".join(prompt.strip().split())
    if duration and float(duration) > 0:
        # le suffixe est en FRAMES ENTIERES a 30 fps (int(split[1]) cote
        # local_infer — "#6.0" levait ValueError et tuait la generation).
        _ligne += "#%d" % int(round(max(1.0, min(float(duration), 30.0)) * 30))
    (tmp / "0.txt").write_text(_ligne + "\n", encoding="utf-8")

    env = {**os.environ,
           "PYTHONPATH": str(HY_ROOT),
           # 4-BIT PAR DEFAUT sur cette carte: l'encodeur Qwen3-8B en bf16
           # (16 Go) ne tient pas a cote du modele de mouvement sur 15,46 Go
           # de VRAM — OOM constate en production (Pikachu 24/07: "failed to
           # allocate 96 MiB"). Le 4-bit est le seul mode verifie de bout en
           # bout ici. AURORA_LLM_4BIT=0 pour le desactiver sur plus grosse carte.
           "AURORA_LLM_4BIT": os.environ.get("AURORA_LLM_4BIT", "1"),
           # HY-Motion a besoin de DEUX encodeurs de texte (CLIP-L et Qwen3-8B).
           # A 0 il les cherche dans ckpts/ et echoue si on ne les y a pas
           # copies a la main; a 1 il les tire de HuggingFace et les met dans le
           # cache commun — c'est aussi ce qui explique le "26 Go" annonce par
           # le depot alors que le modele de mouvement lui-meme ne pese que 4,17.
           "USE_HF_MODELS": os.environ.get("USE_HF_MODELS", "1"),
           "HF_HOME": os.environ.get(
               "HF_HOME", str(Path.home() / ".cache" / "huggingface"))}
    cmd = [_python(), str(REPO_ROOT / "auto_rl" / "hymotion_infer.py"),
           "--model_path", str(_model_path()),
           "--input_text_dir", str(tmp),
           "--output_dir", str(out),
           "--cfg_scale", str(cfg_scale),
           "--num_seeds", str(max(1, int(seeds))),
           # sans ces deux drapeaux, un LLM supplementaire est charge
           "--disable_rewrite", "--disable_duration_est"]

    t0 = time.time()
    try:
        proc = subprocess.run(cmd, cwd=str(HY_ROOT), env=env,
                              capture_output=True, text=True, timeout=timeout_s)
    except subprocess.TimeoutExpired:
        return {"ok": False, "error": "HY-Motion: delai depasse (%ds)" % timeout_s}
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": "HY-Motion: %r" % (exc,)}

    files = sorted(str(p) for p in out.rglob("*")
                   if p.is_file() and p.suffix.lower() in
                   (".bvh", ".npy", ".npz", ".fbx", ".json"))
    if proc.returncode != 0 and not files:
        tail = (proc.stderr or proc.stdout or "")[-600:]
        return {"ok": False, "error": "HY-Motion a echoue: %s" % tail,
                "elapsed_s": round(time.time() - t0, 1)}
    if not files:
        return {"ok": False, "error": "HY-Motion n'a produit aucun fichier",
                "elapsed_s": round(time.time() - t0, 1)}
    return {"ok": True, "files": files, "prompt": prompt,
            "duration_s": duration, "elapsed_s": round(time.time() - t0, 1)}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--prompt")
    ap.add_argument("--output-dir", dest="output_dir")
    ap.add_argument("--duration", type=float, default=4.0)
    ap.add_argument("--seeds", type=int, default=1)
    ap.add_argument("--cfg", type=float, default=5.0, dest="cfg_scale")
    ap.add_argument("--check", action="store_true",
                    help="verifie seulement la disponibilite")
    a = ap.parse_args()
    if a.check:
        # --check n'a besoin d'aucun prompt: il repond juste "utilisable ou non".
        ok, why = available()
        print(json.dumps({"ok": ok, "error": why or None,
                          "root": str(HY_ROOT),
                          "model_path": str(_model_path() or "")},
                         ensure_ascii=False))
        return 0 if ok else 1
    if not a.prompt or not a.output_dir:
        ap.error("--prompt et --output-dir sont requis (sauf avec --check)")
    res = generate(a.prompt, a.output_dir, duration=a.duration,
                   seeds=a.seeds, cfg_scale=a.cfg_scale)
    print(json.dumps(res, ensure_ascii=False))
    return 0 if res.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
