"""motion_score — score MoMask ``joints.npy`` files on gait quality.

The MoMask ``run_gen.py`` outputs T x 22 x 3 joint tensors in HumanML3D
skeleton order (Y up). We score each candidate on measurable geometric
features so the pipeline can curate: generate N candidates, score, keep the
best. Pure numpy, no rendering, sub-second per candidate.

HumanML3D joint indices (SMPL-based)::

    0=pelvis 1=L_hip 2=R_hip 3=spine1 4=L_knee 5=R_knee 6=spine2
    7=L_ankle 8=R_ankle 9=spine3 10=L_foot 11=R_foot 12=neck
    13=L_collar 14=R_collar 15=head 16=L_shoulder 17=R_shoulder
    18=L_elbow 19=R_elbow 20=L_wrist 21=R_wrist

Score = weighted composite of:
  * ``wrists_down`` — arms hang below shoulders (rejects hand-raised walks)
  * ``arms_swing`` — amplitude of wrists' forward motion relative to shoulders,
    normalised by shoulder width. Higher = ampler swing (up to a cap).
  * ``alternation`` — Pearson correlation of L vs R foot vertical over time,
    inverted (walk should have anti-phase foot lift).
  * ``planted`` — fraction of frames where the LOWEST foot is close to the
    lowest y in the sequence (foot planted, no floating).
  * ``forward_progress`` — root horizontal displacement over the clip, in
    metres. Anything above ~3 m over ~200 frames = a real walk.
  * ``head_upright`` — head - neck vertical vector aligns with world Y.
  * ``no_head_dive`` — head y stays above shoulder y throughout (rejects the
    ~-50 deg neck-dive artefact of joints2bvh).
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np

# Joint indices — see docstring above.
J_PELVIS = 0
J_L_ANKLE, J_R_ANKLE = 7, 8
J_L_FOOT, J_R_FOOT = 10, 11
J_NECK = 12
J_HEAD = 15
J_L_SHOULDER, J_R_SHOULDER = 16, 17
J_L_WRIST, J_R_WRIST = 20, 21


def _clip01(x: float) -> float:
    return float(max(0.0, min(1.0, x)))


def _forward_axis(joints: np.ndarray) -> np.ndarray:
    """Direction the character walks, in world XZ.

    Robust to short clips: falls back to the pelvis' Z-forward if the root
    barely moves (idle/turn-in-place).
    """
    root = joints[:, J_PELVIS, :]
    delta = root[-1] - root[0]
    horiz = np.array([delta[0], 0.0, delta[2]])
    n = np.linalg.norm(horiz)
    if n < 0.05:
        # too short — use the frame-averaged shoulder-across x pelvis-forward
        shoulder_dir = joints[:, J_L_SHOULDER, :] - joints[:, J_R_SHOULDER, :]
        m = shoulder_dir.mean(axis=0)
        m[1] = 0.0
        # forward = up cross (shoulder_across)
        fwd = np.cross(np.array([0.0, 1.0, 0.0]), m)
        n2 = np.linalg.norm(fwd)
        return fwd / n2 if n2 > 1e-6 else np.array([0.0, 0.0, 1.0])
    return horiz / n


def score_joints(joints: np.ndarray) -> Dict[str, Any]:
    """Score a single T x 22 x 3 tensor. Returns a dict of metrics + composite.

    All metrics are in [0, 1] where 1 = better. ``composite`` is a weighted sum.
    """
    if joints.ndim != 3 or joints.shape[1] < 22 or joints.shape[2] != 3:
        raise ValueError(f"joints shape must be T x 22+ x 3, got {joints.shape}")

    T = joints.shape[0]
    fwd = _forward_axis(joints)  # world XZ direction of travel

    # ---------------- feet planted + alternation ----------------
    ly = joints[:, J_L_FOOT, 1]
    ry = joints[:, J_R_FOOT, 1]
    ground = min(ly.min(), ry.min())
    lowest_per_frame = np.minimum(ly, ry)
    planted_thresh = 0.05  # 5cm above the sequence ground
    planted_frac = float(np.mean(lowest_per_frame - ground < planted_thresh))

    if T > 4:
        # normalise then correlate — anti-phase (correlation < 0) is what a
        # gait wants; map [-1..0..+1] to [1..0.5..0] with a soft slope.
        ly_c = ly - ly.mean()
        ry_c = ry - ry.mean()
        denom = float(np.sqrt((ly_c ** 2).sum() * (ry_c ** 2).sum())) + 1e-8
        corr = float((ly_c * ry_c).sum() / denom)
        alt = _clip01(0.5 - 0.5 * corr)  # -1 -> 1, +1 -> 0
    else:
        alt = 0.5

    # ---------------- arm swing amplitude ----------------
    # Local wrist forward position = wrist projected on the walk-forward axis,
    # relative to the shoulder projection. Std over frames = swing amplitude.
    def _local_forward(joint_i, shoulder_i):
        w = joints[:, joint_i, :]
        s = joints[:, shoulder_i, :]
        rel = w - s
        return rel @ fwd  # (T,)

    l_swing = _local_forward(J_L_WRIST, J_L_SHOULDER)
    r_swing = _local_forward(J_R_WRIST, J_R_SHOULDER)
    swing_amp = 0.5 * (l_swing.std() + r_swing.std())
    # 0.20 m is a big natural swing at walking speed; 0.05 is minimal.
    arms_swing = _clip01((swing_amp - 0.05) / (0.20 - 0.05))

    # ---------------- wrists below shoulders ----------------
    wrists_y = 0.5 * (joints[:, J_L_WRIST, 1] + joints[:, J_R_WRIST, 1])
    shoulders_y = 0.5 * (joints[:, J_L_SHOULDER, 1] + joints[:, J_R_SHOULDER, 1])
    below = np.mean(wrists_y < shoulders_y - 0.02)  # 2cm margin
    wrists_down = _clip01(below)

    # ---------------- head upright / no dive ----------------
    head_vec = joints[:, J_HEAD, :] - joints[:, J_NECK, :]
    hvn = head_vec / (np.linalg.norm(head_vec, axis=1, keepdims=True) + 1e-8)
    head_upright = _clip01(hvn[:, 1].mean())  # mean Y component
    head_above_shoulders = np.mean(joints[:, J_HEAD, 1] > shoulders_y + 0.05)
    no_head_dive = _clip01(head_above_shoulders)

    # ---------------- forward progress ----------------
    root = joints[:, J_PELVIS, :]
    horiz_path = np.linalg.norm(root[-1, [0, 2]] - root[0, [0, 2]])
    forward_progress = _clip01(horiz_path / 3.0)  # 3 m is plenty for a walk

    # ---------------- pelvis rhythm ----------------
    # Real walking gives a small bob (~2 cm). No bob at all reads as sliding.
    py = root[:, 1]
    py_c = py - py.mean()
    bob = _clip01(0.5 * py_c.std() / 0.03)  # 3 cm std = full score
    if T < 20:
        bob = 0.5

    # ---------------- composite ----------------
    weights = {
        "wrists_down": 1.0,
        "no_head_dive": 1.0,
        "planted": 1.5,        # foot planting is what "no floating" means
        "arms_swing": 1.8,     # AMPLE arm swing is the top ask
        "alternation": 1.0,
        "forward_progress": 1.0,
        "head_upright": 0.8,
        "bob": 0.4,
    }
    parts = {
        "wrists_down": wrists_down,
        "no_head_dive": no_head_dive,
        "planted": planted_frac,
        "arms_swing": arms_swing,
        "alternation": alt,
        "forward_progress": forward_progress,
        "head_upright": head_upright,
        "bob": bob,
    }
    total_w = sum(weights.values())
    composite = sum(weights[k] * parts[k] for k in parts) / total_w

    return {
        "composite": float(composite),
        "metrics": {k: float(v) for k, v in parts.items()},
        "raw": {
            "swing_amp_m": float(swing_amp),
            "path_m": float(horiz_path),
            "T": int(T),
            "foot_alt_corr": float(corr) if T > 4 else None,
        },
    }


def score_file(path: str) -> Dict[str, Any]:
    j = np.load(path)
    r = score_joints(j)
    r["path"] = path
    return r


def score_candidates(candidates: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    scored: List[Dict[str, Any]] = []
    for c in candidates:
        p = c.get("joints_ik") or c.get("joints")
        if not p:
            continue
        try:
            s = score_file(p)
        except Exception as exc:
            s = {"error": str(exc), "path": p, "composite": -1.0}
        s.update({k: c[k] for k in ("index", "length", "bvh_ik") if k in c})
        scored.append(s)
    scored.sort(key=lambda r: r.get("composite", -1.0), reverse=True)
    return scored


def _cli() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("paths", nargs="+", help="joints.npy files to score")
    args = ap.parse_args()
    for p in args.paths:
        r = score_file(p)
        print(json.dumps(r, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(_cli())
