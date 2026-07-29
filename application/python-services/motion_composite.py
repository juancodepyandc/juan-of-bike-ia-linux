#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""motion_composite — compose une piste CORPS et une piste EFFET en un rendu.

Le planificateur (motion_timeline_planner) detecte une demande composite comme
"un guerrier qui attaque avec une flamme": une piste corps (le personnage
anime, dans un GLB) et une piste effet (le feu, qui ne tient pas dans un GLB).
Ce module les reunit dans UNE scene Blender et rend la sequence — la seule
facon de les voir ensemble, puisqu'aucun GLB ne porte un volume.

Verifie: le personnage ET le feu apparaissent dans les memes images (mesure de
pixels sujet + pixels chauds).

Usage:
    python motion_composite.py --character <anime.glb> --effect fire \
        --output-dir <dir> [--engulf]
"""
from __future__ import annotations
import argparse, json, os, shutil, subprocess, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SCRIPT = HERE / "motion_composite_blender.py"


def _blender() -> str:
    envb = os.environ.get("AURORA_BLENDER")
    if envb:
        return envb
    local = os.path.expanduser("~/.local/bin/blender")
    if os.path.isfile(local):
        return local
    return shutil.which("blender") or "blender"


def compose(character_glb: str, effect: str, output_dir: str = "",  # noqa
            engulf: bool = False, timeout_s: int = 1200) -> dict:
    if not os.path.isfile(character_glb):
        return {"ok": False, "error": "GLB du personnage introuvable"}
    out = Path(output_dir); out.mkdir(parents=True, exist_ok=True)
    eff = (effect or "fire") + ("_engulf" if engulf else "")
    cmd = [_blender(), "--background", "--python", str(SCRIPT), "--",
           os.path.abspath(character_glb), str(out), eff]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout_s)
    except subprocess.TimeoutExpired:
        return {"ok": False, "error": "composition: delai depasse"}
    imgs = sorted(str(p) for p in out.glob("*.png"))
    if "COMPOSE_OK" not in (proc.stdout or "") or not imgs:
        return {"ok": False, "error": (proc.stdout or proc.stderr or "")[-300:]}
    return {"ok": True, "images": len(imgs), "dossier": str(out),
            "effet": effect, "voie": "rendu"}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--character", required=True)
    ap.add_argument("--effect", default="fire")
    ap.add_argument("--output-dir", required=True, dest="output_dir")
    ap.add_argument("--engulf", action="store_true")
    a = ap.parse_args()
    r = compose(a.character, a.effect, a.output_dir, a.engulf)
    print(json.dumps(r, ensure_ascii=False))
    return 0 if r.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
