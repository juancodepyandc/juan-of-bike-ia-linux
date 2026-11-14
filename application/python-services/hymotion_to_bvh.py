#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""hymotion_to_bvh — sortie HY-Motion (SMPL-X / WoodenMesh 52 os) -> BVH + matrices SO(3).

HY-Motion rend un `.npz` : `poses (T,156)` en axe-angle (52 articulations :
22 corps + 15 main gauche + 15 main droite), `trans (T,3)`, `Rh (T,3)` et `betas (1,16)`.

Points critiques :
  1. Ne JAMAIS moyenner linéairement des vecteurs axe-angle `poses` autour de +-pi :
     l'antipodalité (theta, n) ~ (2pi - theta, -n) provoque un retournement brutal de 360°
     (norme -> 0 au passage de pi). Le lissage temporel C2 est effectué sur la variété S^3
     des quaternions unitaires avec continuité d'hémisphère (q_t . q_{t-1} >= 0).
  2. Exporte `<out_bvh>.smplx_data.npz` contenant les matrices de rotation globales SO(3)
     exactes `global_rot_mats (T, 52, 3, 3)`, `joints_world (T, 52, 3)` et `j_template (52, 3)`
     calculées sur le squelette canonique WoodenMesh de HY-Motion-1.0, permettant à
     `mia_mocap_retarget.py` d'appliquer un retargeting SO(3) complet (swing + twist/roulis
     axial + 30 phalanges) sans distorsion.

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
HY_ROOT = Path(os.environ.get(
    "AURORA_HYMOTION_ROOT",
    Path.home() / ".local/share/auroraia/external/HY-Motion"))
WOODEN_DIR = HY_ROOT / "scripts" / "gradio" / "static" / "assets" / "dump_wooden"

BODY_JOINTS = 22


def _aa_to_quat_np(aa):
    """Axe-angle (..., 3) -> quaternion unitaire (..., 4) [w, x, y, z]."""
    import numpy as np
    angle = np.linalg.norm(aa, axis=-1, keepdims=True)
    half = 0.5 * angle
    small = angle < 1e-7
    scale = np.where(small, 0.5, np.sin(half) / np.where(small, 1.0, angle))
    w = np.cos(half)
    xyz = aa * scale
    q = np.concatenate([w, xyz], axis=-1).astype(np.float32)
    q /= np.maximum(np.linalg.norm(q, axis=-1, keepdims=True), 1e-8)
    return q


def _quat_to_aa_np(q):
    """Quaternion unitaire (..., 4) [w, x, y, z] -> axe-angle (..., 3)."""
    import numpy as np
    q = q / np.maximum(np.linalg.norm(q, axis=-1, keepdims=True), 1e-8)
    # Choisir l'hémisphère w >= 0 pour un angle dans [0, pi]
    q = np.where(q[..., :1] < 0.0, -q, q)
    w = np.clip(q[..., 0:1], -1.0, 1.0)
    xyz = q[..., 1:4]
    sin_half = np.linalg.norm(xyz, axis=-1, keepdims=True)
    angle = 2.0 * np.arctan2(sin_half, w)
    small = sin_half < 1e-7
    axis = np.where(small, xyz, xyz / np.where(small, 1.0, sin_half))
    return (axis * angle).astype(np.float32)


def _quat_to_mat_np(q):
    """Quaternion unitaire (..., 4) [w, x, y, z] -> matrice de rotation SO(3) (..., 3, 3)."""
    import numpy as np
    q = q / np.maximum(np.linalg.norm(q, axis=-1, keepdims=True), 1e-8)
    w, x, y, z = q[..., 0], q[..., 1], q[..., 2], q[..., 3]
    xx, yy, zz = x * x, y * y, z * z
    xy, xz, yz = x * y, x * z, y * z
    wx, wy, wz = w * x, w * y, w * z
    m = np.empty(q.shape[:-1] + (3, 3), dtype=np.float32)
    m[..., 0, 0] = 1.0 - 2.0 * (yy + zz)
    m[..., 0, 1] = 2.0 * (xy - wz)
    m[..., 0, 2] = 2.0 * (xz + wy)
    m[..., 1, 0] = 2.0 * (xy + wz)
    m[..., 1, 1] = 1.0 - 2.0 * (xx + zz)
    m[..., 1, 2] = 2.0 * (yz - wx)
    m[..., 2, 0] = 2.0 * (xz - wy)
    m[..., 2, 1] = 2.0 * (yz + wx)
    m[..., 2, 2] = 1.0 - 2.0 * (xx + yy)
    return m


def _smooth_poses_s3(poses_flat, trans):
    """Lissage temporel C2 sur S^3 avec continuité d'hémisphère (0 saut à +-pi)."""
    import numpy as np
    T = poses_flat.shape[0]
    n_joints = poses_flat.shape[1] // 3
    aa = poses_flat.reshape(T, n_joints, 3)
    quats = _aa_to_quat_np(aa)
    for t in range(1, T):
        dot = np.sum(quats[t] * quats[t - 1], axis=-1, keepdims=True)
        quats[t] = np.where(dot < 0.0, -quats[t], quats[t])
    if T >= 5:
        k = np.array([0.12, 0.24, 0.28, 0.24, 0.12], dtype=np.float32)
        q_pad = np.pad(quats, ((2, 2), (0, 0), (0, 0)), mode="edge")
        quats = sum(k[i] * q_pad[i:i + T] for i in range(5))
        quats /= np.maximum(np.linalg.norm(quats, axis=-1, keepdims=True), 1e-8)
        t_pad = np.pad(trans, ((2, 2), (0, 0)), mode="edge")
        trans = sum(k[i] * t_pad[i:i + T] for i in range(5)).astype(np.float32)
    local_mats = _quat_to_mat_np(quats)
    poses_smooth = _quat_to_aa_np(quats).reshape(T, n_joints * 3)
    return poses_smooth, trans, local_mats


def _compute_wooden_fk(local_mats, trans):
    """Cinématique directe exacte sur le squelette 52 os WoodenMesh de HY-Motion."""
    import numpy as np
    j_bin = WOODEN_DIR / "j_template.bin"
    k_bin = WOODEN_DIR / "kintree.bin"
    if not (j_bin.is_file() and k_bin.is_file()):
        return None
    j_template = np.frombuffer(j_bin.read_bytes(), dtype=np.float32).reshape(-1, 3).copy()
    parents = np.frombuffer(k_bin.read_bytes(), dtype=np.int32).copy()
    T, J = local_mats.shape[:2]
    rel_j = j_template.copy()
    rel_j[1:] = j_template[1:] - j_template[parents[1:]]

    global_mats = np.zeros_like(local_mats)
    joints_world = np.zeros((T, J, 3), dtype=np.float32)
    global_mats[:, 0] = local_mats[:, 0]
    joints_world[:, 0] = j_template[0] + trans

    for i in range(1, J):
        pi = int(parents[i])
        global_mats[:, i] = np.matmul(global_mats[:, pi], local_mats[:, i])
        joints_world[:, i] = joints_world[:, pi] + np.einsum("tij,j->ti", global_mats[:, pi], rel_j[i])

    return {
        "global_rot_mats": global_mats,
        "local_rot_mats": local_mats,
        "joints_world": joints_world,
        "j_template": j_template,
        "parents": parents,
        "trans": trans,
    }


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

    poses, trans, local_mats = _smooth_poses_s3(poses, trans)

    Path(out_bvh).parent.mkdir(parents=True, exist_ok=True)
    out_bvh = str(Path(out_bvh).resolve())
    smplx_data_npz = out_bvh + ".smplx_data.npz"
    fk_data = _compute_wooden_fk(local_mats, trans)
    if fk_data is not None:
        try:
            np.savez(smplx_data_npz, **fk_data)
        except Exception:
            pass

    body = _smplx.create(str(model_dir), model_type="smplx", gender=gender,
                         use_pca=False, flat_hand_mean=True, batch_size=T)
    with torch.no_grad():
        out = body(
            betas=torch.from_numpy(np.repeat(betas, T, axis=0)),
            global_orient=torch.from_numpy(poses[:, 0:3]),
            body_pose=torch.from_numpy(poses[:, 3:66]),
            left_hand_pose=torch.from_numpy(poses[:, 66:111]) if poses.shape[1] >= 111 else None,
            right_hand_pose=torch.from_numpy(poses[:, 111:156]) if poses.shape[1] >= 156 else None,
            transl=torch.from_numpy(trans),
        )
    all_joints = out.joints.numpy()[:, :55, :].astype(np.float32)  # (T, 55, 3)
    joints = all_joints[:, :BODY_JOINTS, :]                        # (T, 22, 3)

    smplx_joints_npy = out_bvh + ".smplx_joints.npy"
    try:
        np.save(smplx_joints_npy, fk_data["joints_world"] if fk_data is not None else all_joints)
    except Exception:
        pass

    sys.path.insert(0, str(MOMASK_DIR))
    try:
        from visualization.joints2bvh import Joint2BVHConvertor
    except Exception as exc:  # noqa: BLE001
        npy = str(Path(out_bvh).with_suffix(".joints.npy"))
        np.save(npy, joints)
        return {"ok": True, "format": "joints_npy", "file": npy,
                "smplx_joints_file": smplx_joints_npy,
                "smplx_data_file": smplx_data_npz,
                "frames": T, "joints": int(joints.shape[1]),
                "note": "joints2bvh indisponible (%s) — positions brutes livrees"
                        % str(exc)[:80]}

    _cwd = os.getcwd()
    try:
        os.chdir(str(MOMASK_DIR))
        conv = Joint2BVHConvertor()
        conv.convert(joints, out_bvh, iterations=20, foot_ik=True)
    finally:
        os.chdir(_cwd)
    if not Path(out_bvh).is_file():
        return {"ok": False, "error": "le convertisseur n'a ecrit aucun BVH"}
    try:
        import re as _re_bvh
        bvh_txt = Path(out_bvh).read_text(encoding="utf-8")
        frame_dt = 1.0 / float(max(1, int(fps)))
        bvh_txt = _re_bvh.sub(
            r"Frame Time:\s*[0-9.]+",
            f"Frame Time: {frame_dt:.6f}",
            bvh_txt,
            count=1,
        )
        Path(out_bvh).write_text(bvh_txt, encoding="utf-8")
    except Exception:
        pass
    return {"ok": True, "format": "bvh", "file": out_bvh,
            "smplx_joints_file": smplx_joints_npy,
            "smplx_data_file": smplx_data_npz,
            "frames": T, "joints": int(joints.shape[1]), "fps": fps, "gender": gender}


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
