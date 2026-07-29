#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""hymotion_to_bvh — sortie HY-Motion (SMPL-X) -> BVH exploitable par le rig.

HY-Motion rend un `.npz` SMPL-X: `poses (T,156)` en axe-angle (52 articulations:
corps, mains, machoire, yeux), `trans (T,3)`, `Rh (T,3)` et `betas (1,16)`.
Aucun outil du projet ne lit ce format. Le BVH, lui, est lu partout — c'est ce
que produit deja MoMask et ce que `retarget_bvh` sait reprojeter sur un
squelette quelconque.

Le pont: SMPL-X (le modele de corps installe) transforme poses+betas en
POSITIONS d'articulations, puis `joints2bvh` de momask-codes ecrit le BVH. On
ne reinvente donc ni le squelette ni l'ecriture BVH — on relie deux outils
deja presents.

Usage:
    python hymotion_to_bvh.py --npz <motion.npz> --output <sortie.bvh> [--fps 30]
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

SMPLX_DIR = Path(os.environ.get(
    "AURORA_SMPLX_DIR",
    Path.home() / ".local/share/auroraia/external/smplx/models"))
MOMASK_DIR = Path(os.environ.get(
    "AURORA_MOMASK_DIR",
    Path.home() / ".local/share/auroraia/external/momask-codes"))

# Les 22 premieres articulations SMPL-X sont le CORPS. Les suivantes sont les
# mains et le visage: un BVH de locomotion n'en a pas besoin et elles font
# exploser la taille du fichier pour rien.
BODY_JOINTS = 22


def convert(npz_path: str, out_bvh: str, fps: int = 30) -> dict:
    try:
        import numpy as np
        import torch
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": "numpy/torch indisponibles: %r" % (exc,)}
    try:
        import smplx as _smplx
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": "paquet smplx absent: %r" % (exc,)}

    d = np.load(npz_path, allow_pickle=True)
    for key in ("poses", "trans", "betas"):
        if key not in d.files:
            return {"ok": False, "error": "champ '%s' absent du npz" % key}
    poses = np.asarray(d["poses"], dtype=np.float32)      # (T, 156)
    trans = np.asarray(d["trans"], dtype=np.float32)      # (T, 3)
    betas = np.asarray(d["betas"], dtype=np.float32).reshape(1, -1)[:, :10]
    T = poses.shape[0]
    if T < 2:
        return {"ok": False, "error": "sequence trop courte (%d image)" % T}

    model_dir = SMPLX_DIR
    if not (model_dir / "smplx").is_dir():
        return {"ok": False, "error": "modeles SMPL-X introuvables sous %s" % model_dir}

    gender = "neutral"
    try:
        g = str(d["gender"][0]) if "gender" in d.files else "neutral"
        gender = g if g in ("neutral", "male", "female") else "neutral"
    except Exception:  # noqa: BLE001
        pass

    body = _smplx.create(str(model_dir), model_type="smplx", gender=gender,
                         use_pca=False, flat_hand_mean=True, batch_size=T)
    with torch.no_grad():
        out = body(
            betas=torch.from_numpy(np.repeat(betas, T, axis=0)),
            global_orient=torch.from_numpy(poses[:, 0:3]),
            body_pose=torch.from_numpy(poses[:, 3:66]),
            transl=torch.from_numpy(trans),
        )
    joints = out.joints.numpy()[:, :BODY_JOINTS, :]   # (T, 22, 3)

    sys.path.insert(0, str(MOMASK_DIR))
    try:
        from visualization.joints2bvh import Joint2BVHConvertor
    except Exception as exc:  # noqa: BLE001
        # Sans le convertisseur, on rend quand meme les positions: elles
        # suffisent a piloter un squelette et valent mieux que rien.
        npy = str(Path(out_bvh).with_suffix(".joints.npy"))
        np.save(npy, joints)
        return {"ok": True, "format": "joints_npy", "file": npy,
                "frames": T, "joints": int(joints.shape[1]),
                "note": "joints2bvh indisponible (%s) — positions brutes livrees"
                        % str(exc)[:80]}

    Path(out_bvh).parent.mkdir(parents=True, exist_ok=True)
    out_bvh = str(Path(out_bvh).resolve())
    # joints2bvh charge son gabarit par un chemin RELATIF
    # ('./visualization/data/template.bvh'): il faut donc etre dans son dossier,
    # et rendre le chemin de sortie absolu avant de bouger.
    _cwd = os.getcwd()
    try:
        os.chdir(str(MOMASK_DIR))
        conv = Joint2BVHConvertor()
        conv.convert(joints, out_bvh, iterations=10, foot_ik=True)
    finally:
        os.chdir(_cwd)
    if not Path(out_bvh).is_file():
        return {"ok": False, "error": "le convertisseur n'a ecrit aucun BVH"}
    return {"ok": True, "format": "bvh", "file": out_bvh, "frames": T,
            "joints": int(joints.shape[1]), "fps": fps, "gender": gender}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--npz", required=True)
    ap.add_argument("--output", required=True)
    ap.add_argument("--fps", type=int, default=30)
    a = ap.parse_args()
    r = convert(a.npz, a.output, a.fps)
    print(json.dumps(r, ensure_ascii=False))
    return 0 if r.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
