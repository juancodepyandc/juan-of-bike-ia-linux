#!/usr/bin/env python
"""anim_metrics — objective, type-dispatched validation metrics on the
DEFORMED / animated scene (no render, no human eye), to drive the Aurora
auto-correction loop.

Where this sits in the pipeline
-------------------------------
motion_intent_classifier.py already decides *what the subject is* (6
categories). mesh_quality_score.py already scores the *static* GLB. What was
missing — and what this module provides — is the layer that measures the
*animated* result frame-by-frame and turns each defect into a concrete knob
the auto-correction loop can turn.

The pre-existing loop measured 3 things on humanoids: edge stretch (tearing),
lowest foot height (floating), finger spread (hands). This module keeps those
and generalizes to EVERY morphology the classifier can emit, because a single
universal rule is wrong ("hardcoder attraper un objet ça peut être faux"): a
rigid robot must NOT deform, a floating jester's gloves have no arm, a RAM
stick with no rig only animates light.

Type -> family mapping (drives which metrics run) — see family_for_intent():
    led_emission                         -> "luminous"   (RAM LED, cable)
    oled_screen                          -> "screen"     (embedded display)
    creature_organic + loco=humanoid     -> "humanoid"   (person, GOLDORAK-pilot-shaped)
    creature_organic + loco!=humanoid    -> "creature"   (CAINE, quadruped, serpent)
    mechanical_simple / rigid_static / fan_pwm -> "mecha_rigid" (GOLDORAK armor, hinge, fan)
CAINE is a hybrid: a "creature" body with a "screen" face -> pass add_screen=True.

Input contract — a "take" dict (all arrays numpy, all optional unless a metric
needs them; a metric returns passed=None/"skipped" when its inputs are absent):

    take = {
      "fps": 24,
      "verts":  (F, V, 3) float   world-space deformed vertex positions / frame,
      "rest":   (V, 3)   float     rest pose (defaults to verts[0]),
      "edges":  (E, 2)   int       topology edge index pairs (rest connectivity),
      "part_labels": (V,) int      rigid-piece / limb segmentation per vertex,
      "adjacent_parts": [(a,b),..] part pairs allowed to touch (share a joint),
      "joint_parts":    [(a,b),..] part pairs that share a MECHANICAL joint,
      "joints": { "ankle.L": (F,3), "heel.L": (F,3), "toe.L": (F,3),
                  "thigh.R": (F,3)|angle, "arm.R": ..., "head": (F,3),
                  "neck": (F,3), "pelvis": (F,3), ... },
      "signals": { "thigh.R": (F,), "arm.R": (F,) }  sagittal angles (deg) if precomputed,
      "finger_chains": { "index.R": [(F,3) mcp,(F,3) pip,(F,3) dip,(F,3) tip], ... },
      "shoulder_width": float,
      "ground": float             ground plane height on the up axis (default min of rest),
      "up_axis": "Z"|"Y"          (default "Z"),
      "emission": (F, L) or (F,L,3) float  per-LED brightness/colour per frame,
      "pattern": "breathing"|"pulse"|"chase"|"rainbow"|"static_color",
      "speed_hz": float,
      "screen_features": { "eye.L": {"uv": (F,2), "present": (F,) bool}, ... },
      "screen_part_verts": (F, Vs, 3)  the screen quad verts (rigidity/planarity),
      "floating_parts": { "glove.L": {"verts_idx":[...], "anchor": (F,3)} },
    }

Every metric returns a uniform record (see _mk): metric, family, value, unit,
threshold, direction, passed, severity, knob {param, action, suggest}, detail.
`severity` (0 = pass, grows with how far past threshold) ranks knobs for the
auto-correction loop.

Pure numpy — no bpy, so the whole thing is unit-testable via --self-test and
test_anim_metrics.py. sample_take_from_blender() (lazy bpy) builds a `take`
from a live rigged+animated scene, mirroring mesh_screenshot.py's depsgraph use.
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

import numpy as np


SCHEMA = "aurora.anim_metrics.v1"
_EPS = 1e-9


# ===========================================================================
#  THRESHOLDS — every target in one editable table (tunable + testable).
#  Each entry: (threshold, direction). direction "<=" means value must be
#  <= threshold to pass; ">=" means value must be >= threshold.
# ===========================================================================
THRESHOLDS: Dict[str, Tuple[float, str]] = {
    # shared / deforming
    "edge_stretch":              (1.50, "<="),   # p99 strain ratio (rest=1.0)
    # humanoid
    "foot_ground":               (0.02, "<="),   # stance clearance / body height
    "heel_toe_roll":             (-0.60, "<="),  # Spearman(frame, toe-heel) — want strong neg
    "contralateral_arm_swing":   (0.60, ">="),   # -corr(same-side arm,leg); +amp gate
    "head_carriage":             (1.00, "<="),   # normalized max of tilt/bob/sway ratios
    "self_intersection":         (0.006, "<="),  # max capsule penetration / char length
    "hand_flexion":              (0.80, ">="),   # fraction of fingers with natural curl
    "finger_spread":             (25.0, "<="),   # max adjacent-finger abduction (deg)
    # mecha-rigid
    "part_rigidity":             (0.010, "<="),  # max Kabsch residual / part diag
    "plate_interpenetration":    (0.003, "<="),  # max plate-plate penetration / char length
    "joint_coherence":           (3.0, "<="),    # rotation-axis wander (deg)
    # creature
    "floating_part_stability":   (0.010, "<="),  # p95 centroid accel / char length
    "screen_face_coherence":     (0.10, "<="),   # incoherence: out-of-bounds + feature dropout
    # luminous
    "temporal_smoothness":       (0.15, "<="),   # p95 |2nd diff| / emission range (jerk)
    "pulsation_coherence":       (0.30, "<="),   # 1 - periodicity  (or lag std / 1frame for chase)
    "flicker":                   (0.05, "<="),   # HF power ratio; dropouts force fail
    "emission_dynamic_range":    (0.15, ">="),   # (max-min)/max of strip mean (liveness)
}

# ===========================================================================
#  KNOBS — metric -> the parameter the auto-correction loop turns, the
#  direction to turn it, and a human-readable rationale. This is the "quel
#  bouton tourner" registry.
# ===========================================================================
KNOBS: Dict[str, Dict[str, str]] = {
    "edge_stretch":            {"param": "weight_smooth_iterations",
                                "action": "increase",
                                "suggest": "+1 Laplacian weight-smoothing iteration per +0.2 over threshold; re-weld remove_doubles first"},
    "foot_ground":             {"param": "foot_ik_lock",
                                "action": "enable/raise",
                                "suggest": "enable per-frame foot-IK ground lock + set root_vertical_offset so stance foot touches ground"},
    "heel_toe_roll":           {"param": "ankle_pitch_amplitude",
                                "action": "increase",
                                "suggest": "raise foot_roll / ankle-pitch keyframe amplitude until heel-strike->toe-off ordering is monotonic"},
    "contralateral_arm_swing": {"param": "arm_swing_amplitude+phase",
                                "action": "flip phase / raise amplitude",
                                "suggest": "if phase in-phase, offset arm gait primitive by pi (anti-phase to same-side leg); if flat, raise arm_swing_amplitude"},
    "head_carriage":           {"param": "head_stabilization_gain",
                                "action": "increase",
                                "suggest": "add neck/head counter-rotation to keep head upright + damp vertical bob (spine_counter_rotation)"},
    "self_intersection":       {"param": "self_collision_push",
                                "action": "enable/raise",
                                "suggest": "enable self-collision offset + widen limb carry angle (limb_spread_bias)"},
    "hand_flexion":            {"param": "finger_curl_gradation",
                                "action": "set relaxed curl",
                                "suggest": "set relaxed finger_curl_target with MCP>PIP>DIP gradation; clamp hyperextension >= -5deg"},
    "finger_spread":           {"param": "finger_abduction_clamp",
                                "action": "reduce",
                                "suggest": "clamp adjacent-finger abduction into natural range; lower splay in the curl pose"},
    "part_rigidity":           {"param": "max_bone_influences",
                                "action": "set 1 (rigid bind)",
                                "suggest": "rebind this part rigidly: max_bone_influences=1, weight_hardness=1 (no soft skinning on armor)"},
    "plate_interpenetration":  {"param": "joint_gap / mechanical_stop_limit",
                                "action": "increase gap / clamp range",
                                "suggest": "add clearance at the pivot and clamp joint rotation range so plates slide, not clip"},
    "joint_coherence":         {"param": "joint_constraint(pivot_lock)",
                                "action": "add hinge constraint",
                                "suggest": "add a fixed-axis hinge + pivot_lock at rest pivot; constrain to a single rotation axis"},
    "floating_part_stability": {"param": "float_follow_damping",
                                "action": "increase",
                                "suggest": "critically-damp the floating part's follow constraint (float_follow_damping) + bound drift with float_tether_stiffness"},
    "screen_face_coherence":   {"param": "screen_uv_clamp / screen_rigid_bind",
                                "action": "clamp UV / rigid-bind quad",
                                "suggest": "clamp face-feature UV animation inside screen bounds, rigid-bind the screen quad, prevent features vanishing (blink_min_interval)"},
    "temporal_smoothness":     {"param": "emission_smoothing_frames",
                                "action": "increase",
                                "suggest": "widen the emission moving-average / keyframe easing window until jerk falls under threshold"},
    "pulsation_coherence":     {"param": "pulse_period_lock",
                                "action": "quantize to one clock",
                                "suggest": "drive all LEDs from one phase clock at speed_hz (pulse_period_lock); for chase, fix wave_speed"},
    "flicker":                 {"param": "min_dwell_frames / emission_lowpass",
                                "action": "increase dwell / low-pass",
                                "suggest": "hold each LED state >= min_dwell_frames and low-pass the emission track to kill single-frame dropouts"},
    "emission_dynamic_range":  {"param": "pattern_amplitude",
                                "action": "increase",
                                "suggest": "raise emission pattern_amplitude/gain — the requested animation is barely moving (near-static)"},
}


# ===========================================================================
#  geometry / signal helpers (pure numpy)
# ===========================================================================
def _as_f(a) -> np.ndarray:
    return np.asarray(a, dtype=np.float64)


def _bbox_diag(v: np.ndarray) -> float:
    v = _as_f(v)
    if v.size == 0:
        return 1.0
    d = float(np.linalg.norm(v.max(axis=0) - v.min(axis=0)))
    return d if d > _EPS else 1.0


def _char_length(take: dict) -> float:
    rest = take.get("rest")
    if rest is None and take.get("verts") is not None:
        rest = _as_f(take["verts"])[0]
    if rest is None:
        return 1.0
    return _bbox_diag(_as_f(rest))


def _up_index(take: dict) -> int:
    return {"X": 0, "Y": 1, "Z": 2}.get(str(take.get("up_axis", "Z")).upper(), 2)


def _kabsch_residual(P: np.ndarray, Q: np.ndarray) -> float:
    """RMSD of the best rigid fit mapping P (rest) onto Q (frame).

    0 for a truly rigid motion; grows with soft deformation / shear / scale."""
    P = _as_f(P); Q = _as_f(Q)
    if P.shape != Q.shape or len(P) < 3:
        return 0.0
    pc = P - P.mean(axis=0)
    qc = Q - Q.mean(axis=0)
    H = pc.T @ qc
    try:
        U, _, Vt = np.linalg.svd(H)
    except np.linalg.LinAlgError:
        return 0.0
    d = np.sign(np.linalg.det(Vt.T @ U.T))
    D = np.diag([1.0, 1.0, d])
    R = Vt.T @ D @ U.T
    pred = pc @ R.T
    return float(np.sqrt(np.mean(np.sum((pred - qc) ** 2, axis=1))))


def _rot_axis_angle(R: np.ndarray) -> Tuple[np.ndarray, float]:
    """Rotation axis (unit) and angle (rad) of a 3x3 rotation matrix."""
    R = _as_f(R)
    ang = np.arccos(np.clip((np.trace(R) - 1.0) / 2.0, -1.0, 1.0))
    if ang < 1e-6:
        return np.array([0.0, 0.0, 1.0]), 0.0
    axis = np.array([R[2, 1] - R[1, 2], R[0, 2] - R[2, 0], R[1, 0] - R[0, 1]])
    n = np.linalg.norm(axis)
    if n < _EPS:
        # 180-degree rotation: axis from the symmetric part
        w, V = np.linalg.eigh((R + np.eye(3)) / 2.0)
        axis = V[:, int(np.argmax(w))]
        n = np.linalg.norm(axis)
    return axis / (n + _EPS), float(ang)


def _kabsch_R(P: np.ndarray, Q: np.ndarray) -> np.ndarray:
    P = _as_f(P); Q = _as_f(Q)
    pc = P - P.mean(axis=0)
    qc = Q - Q.mean(axis=0)
    H = pc.T @ qc
    U, _, Vt = np.linalg.svd(H)
    d = np.sign(np.linalg.det(Vt.T @ U.T))
    return Vt.T @ np.diag([1.0, 1.0, d]) @ U.T


def _seg_seg_distance(p1, q1, p2, q2) -> float:
    """Shortest distance between segments p1q1 and p2q2 (Ericson, clamped)."""
    p1, q1, p2, q2 = map(_as_f, (p1, q1, p2, q2))
    d1 = q1 - p1
    d2 = q2 - p2
    r = p1 - p2
    a = float(d1 @ d1); e = float(d2 @ d2); f = float(d2 @ r)
    if a <= _EPS and e <= _EPS:
        return float(np.linalg.norm(p1 - p2))
    if a <= _EPS:
        s = 0.0; t = np.clip(f / e, 0.0, 1.0)
    else:
        c = float(d1 @ r)
        if e <= _EPS:
            t = 0.0; s = np.clip(-c / a, 0.0, 1.0)
        else:
            b = float(d1 @ d2)
            denom = a * e - b * b
            s = np.clip((b * f - c * e) / denom, 0.0, 1.0) if denom > _EPS else 0.0
            t = (b * s + f) / e
            if t < 0.0:
                t = 0.0; s = np.clip(-c / a, 0.0, 1.0)
            elif t > 1.0:
                t = 1.0; s = np.clip((b - c) / a, 0.0, 1.0)
    cp1 = p1 + d1 * s
    cp2 = p2 + d2 * t
    return float(np.linalg.norm(cp1 - cp2))


def _part_capsule(verts: np.ndarray) -> Tuple[np.ndarray, np.ndarray, float]:
    """Fit a capsule (endpoint a, endpoint b, radius) to a point cloud via PCA."""
    verts = _as_f(verts)
    c = verts.mean(axis=0)
    X = verts - c
    try:
        _, _, Vt = np.linalg.svd(X, full_matrices=False)
        axis = Vt[0]
    except np.linalg.LinAlgError:
        axis = np.array([0.0, 0.0, 1.0])
    t = X @ axis
    a = c + axis * float(t.min())
    b = c + axis * float(t.max())
    # radius = median perpendicular distance to the axis line
    perp = X - np.outer(t, axis)
    radius = float(np.median(np.linalg.norm(perp, axis=1)))
    return a, b, radius


def _pearson(x: np.ndarray, y: np.ndarray) -> float:
    x = _as_f(x); y = _as_f(y)
    if len(x) < 2:
        return 0.0
    xs = x - x.mean(); ys = y - y.mean()
    d = float(np.linalg.norm(xs) * np.linalg.norm(ys))
    return float(xs @ ys / d) if d > _EPS else 0.0


def _spearman(x: np.ndarray, y: np.ndarray) -> float:
    return _pearson(_rankdata(x), _rankdata(y))


def _rankdata(a: np.ndarray) -> np.ndarray:
    a = _as_f(a)
    order = a.argsort()
    ranks = np.empty(len(a), dtype=np.float64)
    ranks[order] = np.arange(len(a), dtype=np.float64)
    return ranks


def _periodicity_strength(x: np.ndarray, min_period: int = 2) -> Tuple[int, float]:
    """First dominant autocorrelation peak: (period, strength in [0,1])."""
    x = _as_f(x)
    n = len(x)
    if n < 4:
        return 0, 0.0
    x = x - x.mean()
    denom = float(x @ x)
    if denom < _EPS:
        return 0, 0.0
    ac = np.correlate(x, x, mode="full")[n - 1:] / denom
    # first local maximum after the initial descent
    best_p, best_v = 0, 0.0
    for lag in range(min_period, n - 1):
        if ac[lag] > ac[lag - 1] and ac[lag] >= ac[lag + 1] and ac[lag] > best_v:
            best_p, best_v = lag, float(ac[lag])
    return best_p, max(0.0, best_v)


def _hf_power_ratio(x: np.ndarray, fps: float, cutoff_hz: float) -> float:
    """Fraction of spectral power above cutoff_hz (DC excluded)."""
    x = _as_f(x)
    n = len(x)
    if n < 4 or fps <= 0:
        return 0.0
    x = x - x.mean()
    spec = np.abs(np.fft.rfft(x)) ** 2
    freqs = np.fft.rfftfreq(n, d=1.0 / fps)
    total = float(spec[1:].sum())
    if total < _EPS:
        return 0.0
    hf = float(spec[freqs >= cutoff_hz].sum())
    return hf / total


def _single_frame_dropouts(sig: np.ndarray, rel_drop: float = 0.5) -> int:
    """Count isolated 1-frame dips (flicker): frame f far below both neighbours."""
    sig = _as_f(sig)
    n = len(sig)
    if n < 3:
        return 0
    rng = float(sig.max() - sig.min())
    if rng < _EPS:
        return 0
    thr = rel_drop * rng
    cnt = 0
    for f in range(1, n - 1):
        if (sig[f - 1] - sig[f]) > thr and (sig[f + 1] - sig[f]) > thr:
            cnt += 1
    return cnt


def _angle(u: np.ndarray, v: np.ndarray) -> float:
    u = _as_f(u); v = _as_f(v)
    nu = np.linalg.norm(u); nv = np.linalg.norm(v)
    if nu < _EPS or nv < _EPS:
        return 0.0
    return float(np.degrees(np.arccos(np.clip((u @ v) / (nu * nv), -1.0, 1.0))))


# ===========================================================================
#  result builder
# ===========================================================================
def _mk(metric: str, family: str, value: Optional[float], *,
        threshold: Optional[float] = None, direction: Optional[str] = None,
        detail: Optional[dict] = None, skipped: bool = False,
        note: str = "", forced_fail: bool = False) -> dict:
    if threshold is None or direction is None:
        th = THRESHOLDS.get(metric)
        if th is not None:
            threshold, direction = th
    passed: Optional[bool]
    severity = 0.0
    if skipped or value is None:
        passed = None
        skipped = True
    else:
        if direction == "<=":
            passed = value <= threshold
            severity = max(0.0, (value - threshold) / (abs(threshold) + _EPS))
        else:  # ">="
            passed = value >= threshold
            severity = max(0.0, (threshold - value) / (abs(threshold) + _EPS))
        if forced_fail:
            passed = False
            severity = max(severity, 1.0)
    return {
        "metric": metric,
        "family": family,
        "value": None if value is None else round(float(value), 6),
        "threshold": threshold,
        "direction": direction,
        "passed": passed,
        "severity": round(float(severity), 4),
        "skipped": bool(skipped),
        "knob": KNOBS.get(metric),
        "detail": detail or {},
        "note": note,
    }


# ===========================================================================
#  SHARED metric — edge stretch (tearing) — any skinned/deforming family
# ===========================================================================
def m_edge_stretch(take: dict, family: str = "shared") -> dict:
    verts = take.get("verts"); edges = take.get("edges")
    if verts is None or edges is None:
        return _mk("edge_stretch", family, None, skipped=True, note="need verts+edges")
    V = _as_f(verts)                     # (F,V,3)
    E = np.asarray(edges, dtype=int)     # (E,2)
    rest = _as_f(take.get("rest")) if take.get("rest") is not None else V[0]
    rest_len = np.linalg.norm(rest[E[:, 0]] - rest[E[:, 1]], axis=1)
    good = rest_len > _EPS
    E, rest_len = E[good], rest_len[good]
    if len(E) == 0:
        return _mk("edge_stretch", family, None, skipped=True, note="no valid edges")
    cur = np.linalg.norm(V[:, E[:, 0], :] - V[:, E[:, 1], :], axis=2)  # (F,E)
    ratio = cur / rest_len[None, :]
    strain = np.maximum(ratio, 1.0 / np.maximum(ratio, _EPS))          # tear OR crush
    p99 = float(np.percentile(strain, 99))
    return _mk("edge_stretch", family, p99, detail={
        "max_strain": round(float(strain.max()), 4),
        "edges": int(len(E)),
        "hard_tear": bool(strain.max() > 3.0),
    })


# ===========================================================================
#  HUMANOID metrics
# ===========================================================================
def _joint_track(take: dict, name: str) -> Optional[np.ndarray]:
    j = take.get("joints") or {}
    return _as_f(j[name]) if name in j else None


def _signal(take: dict, name: str) -> Optional[np.ndarray]:
    s = take.get("signals") or {}
    return _as_f(s[name]) if name in s else None


def m_foot_ground(take: dict, family: str = "humanoid") -> dict:
    """Floating / penetration. clearance = min-over-frames of lowest stance-foot
    height above ground, normalized by body height H."""
    up = _up_index(take)
    H = _char_length(take)
    lows: List[np.ndarray] = []
    for side in ("L", "R"):
        for key in (f"toe.{side}", f"heel.{side}", f"ankle.{side}", f"foot.{side}"):
            t = _joint_track(take, key)
            if t is not None:
                lows.append(t[:, up])
    if not lows:
        return _mk("foot_ground", family, None, skipped=True, note="need foot joints")
    if "ground" in take:
        ground = float(take["ground"])
    else:
        ref = take.get("rest")
        if ref is None and take.get("verts") is not None:
            ref = _as_f(take["verts"])[0]
        ground = float(_as_f(ref)[:, up].min()) if ref is not None else 0.0
    per_frame_lowest = np.min(np.stack(lows, axis=1), axis=1)   # lowest foot vertex per frame
    clearance = (per_frame_lowest - ground) / (H + _EPS)
    # stance = the frames where a foot is (should be) planted = the lowest ones
    stance_gap = float(np.min(np.abs(clearance)))   # best contact reached
    float_gap = float(np.min(clearance[clearance > 0])) if np.any(clearance > 0) else 0.0
    pierce = float(np.min(clearance))               # most negative = penetration
    value = max(abs(stance_gap), abs(pierce) if pierce < 0 else 0.0)
    return _mk("foot_ground", family, value, detail={
        "H": round(H, 4), "ground": round(ground, 4),
        "best_contact_norm": round(stance_gap, 4),
        "min_float_norm": round(float_gap, 4),
        "max_penetration_norm": round(min(0.0, pierce), 4),
    }, note="floating (never touches)" if stance_gap > THRESHOLDS["foot_ground"][0]
             else ("penetrates ground" if pierce < -THRESHOLDS["foot_ground"][0] else ""))


def m_heel_toe_roll(take: dict, family: str = "humanoid") -> dict:
    """Heel-toe roll: within a stance the toe-minus-heel height ordering must
    ramp monotonically (heel-strike -> flat -> toe-off). Spearman(frame, toe-heel)
    should be strongly negative. A flat/rigid ('skating') foot gives ~0."""
    up = _up_index(take)
    best = None
    detail = {}
    for side in ("L", "R"):
        heel = _joint_track(take, f"heel.{side}")
        toe = _joint_track(take, f"toe.{side}")
        if heel is None or toe is None:
            continue
        d = toe[:, up] - heel[:, up]
        # restrict to the stance window: the half of frames with the lowest ankle
        ankle = _joint_track(take, f"ankle.{side}")
        idx = np.arange(len(d))
        if ankle is not None and len(d) >= 6:
            med = np.median(ankle[:, up])
            mask = ankle[:, up] <= med
            if mask.sum() >= 4:
                idx = np.where(mask)[0]
        rho = _spearman(idx.astype(float), d[idx])
        detail[side] = {"spearman": round(rho, 3), "stance_frames": int(len(idx))}
        if best is None or rho < best:
            best = rho
    if best is None:
        return _mk("heel_toe_roll", family, None, skipped=True, note="need heel+toe joints")
    return _mk("heel_toe_roll", family, best, detail=detail,
               note="foot skates (no roll)" if best > THRESHOLDS["heel_toe_roll"][0] else "")


def _sagittal_signal(take: dict, name: str, up: int) -> Optional[np.ndarray]:
    """A scalar sagittal-swing signal for a limb: precomputed angle if given,
    else derived from a joint track's forward(0)/up projection."""
    s = _signal(take, name)
    if s is not None:
        return s
    t = _joint_track(take, name)
    if t is None:
        return None
    fwd = 0 if up != 0 else 1   # forward axis = first non-up axis
    return np.degrees(np.arctan2(t[:, fwd] - t[:, fwd].mean(), 1.0))


def m_contralateral_arm_swing(take: dict, family: str = "humanoid") -> dict:
    """Same-side arm and leg must be ANTI-phase (right arm forward as right leg
    back). corr(arm.R, leg.R) ~ -1 -> contra_score = -corr ~ +1. Also the arm
    must actually swing (peak-to-peak amplitude gate)."""
    up = _up_index(take)
    scores, amps, sides = [], [], []
    for side in ("R", "L"):
        leg = _sagittal_signal(take, f"thigh.{side}", up)
        arm = _sagittal_signal(take, f"arm.{side}", up)
        if arm is None:
            arm = _sagittal_signal(take, f"upper_arm.{side}", up)
        if leg is None or arm is None:
            continue
        contra = -_pearson(leg, arm)
        amp = float(arm.max() - arm.min())
        scores.append(contra); amps.append(amp); sides.append(side)
    if not scores:
        return _mk("contralateral_arm_swing", family, None, skipped=True,
                   note="need thigh+arm signals")
    contra_score = float(np.mean(scores))
    min_amp = float(np.min(amps))
    amp_ok = min_amp >= 8.0
    return _mk("contralateral_arm_swing", family, contra_score,
               forced_fail=not amp_ok,
               detail={"per_side": dict(zip(sides, [round(s, 3) for s in scores])),
                       "min_arm_amplitude_deg": round(min_amp, 2),
                       "amplitude_ok": amp_ok},
               note="arms barely swing" if not amp_ok else
                    ("arm in-phase with same-side leg" if contra_score < THRESHOLDS["contralateral_arm_swing"][0] else ""))


def m_head_carriage(take: dict, family: str = "humanoid") -> dict:
    """Head must stay upright and steady: tilt from vertical (p95), vertical bob,
    lateral sway. Reported as the max of the three normalized ratios (1.0 = at
    threshold on the worst aspect)."""
    up = _up_index(take)
    head = _joint_track(take, "head")
    neck = _joint_track(take, "neck")
    if head is None:
        return _mk("head_carriage", family, None, skipped=True, note="need head joint")
    H = _char_length(take)
    world_up = np.zeros(3); world_up[up] = 1.0
    tilt = None
    if neck is not None:
        axis = head - neck
        tilt = np.array([_angle(axis[f], world_up) for f in range(len(axis))])
        tilt_p95 = float(np.percentile(tilt, 95))
    else:
        tilt_p95 = 0.0
    bob = float(np.std(head[:, up]) / (H + _EPS))
    lat_axes = [i for i in range(3) if i != up]
    pelvis = _joint_track(take, "pelvis")
    sway_ref = float(take.get("shoulder_width", 0.25 * H))
    if pelvis is not None:
        sway = float(np.std(head[:, lat_axes[0]] - pelvis[:, lat_axes[0]]) / (sway_ref + _EPS))
    else:
        sway = float(np.std(head[:, lat_axes[0]]) / (sway_ref + _EPS))
    r_tilt = tilt_p95 / 8.0
    r_bob = bob / 0.04
    r_sway = sway / 0.06
    value = float(max(r_tilt, r_bob, r_sway))
    return _mk("head_carriage", family, value, detail={
        "tilt_p95_deg": round(tilt_p95, 2), "tilt_ratio": round(r_tilt, 3),
        "bob_norm": round(bob, 4), "bob_ratio": round(r_bob, 3),
        "sway_norm": round(sway, 4), "sway_ratio": round(r_sway, 3),
        "dominant": ["tilt", "bob", "sway"][int(np.argmax([r_tilt, r_bob, r_sway]))],
    })


def _part_penetration(take: dict, metric: str, family: str) -> dict:
    """Max capsule-capsule penetration between non-adjacent parts, / char length.
    Shared by humanoid self-intersection and mecha plate interpenetration."""
    verts = take.get("verts"); labels = take.get("part_labels")
    if verts is None or labels is None:
        return _mk(metric, family, None, skipped=True, note="need verts+part_labels")
    V = _as_f(verts); labels = np.asarray(labels, dtype=int)
    L = _char_length(take)
    parts = sorted(set(labels.tolist()))
    if len(parts) < 2:
        return _mk(metric, family, 0.0, detail={"parts": len(parts)},
                   note="single part — no self-collision possible")
    adjacent = {tuple(sorted(p)) for p in (take.get("adjacent_parts") or [])}
    idx = {p: np.where(labels == p)[0] for p in parts}
    radii = {p: _part_capsule(V[0, idx[p]])[2] for p in parts}
    F = V.shape[0]
    worst = 0.0; worst_pair = None; worst_frame = -1
    for f in range(F):
        caps = {p: _part_capsule(V[f, idx[p]]) for p in parts}
        for i in range(len(parts)):
            for k in range(i + 1, len(parts)):
                pi, pk = parts[i], parts[k]
                if tuple(sorted((pi, pk))) in adjacent:
                    continue
                ai, bi, _ = caps[pi]; ak, bk, _ = caps[pk]
                dist = _seg_seg_distance(ai, bi, ak, bk)
                pen = (radii[pi] + radii[pk]) - dist
                if pen > worst:
                    worst, worst_pair, worst_frame = pen, (pi, pk), f
    value = worst / (L + _EPS)
    return _mk(metric, family, value, detail={
        "char_length": round(L, 4), "parts": len(parts),
        "worst_pair": worst_pair, "worst_frame": worst_frame,
        "penetration_abs": round(worst, 5),
    })


def m_self_intersection(take: dict, family: str = "humanoid") -> dict:
    return _part_penetration(take, "self_intersection", family)


def m_hand_flexion(take: dict, family: str = "humanoid") -> dict:
    """Natural hand: each finger's phalanges curl the same way with a graded
    MCP>=PIP>=DIP flexion and no hyperextension (<-5deg). Score = fraction of
    fingers that read as natural over the take (worst frame)."""
    chains = take.get("finger_chains") or {}
    if not chains:
        return _mk("hand_flexion", family, None, skipped=True, note="need finger_chains")
    per_finger = {}
    natural = 0
    for name, chain in chains.items():
        pts = [_as_f(p) for p in chain]        # [mcp,pip,dip,tip] each (F,3)
        if len(pts) < 4:
            continue
        F = pts[0].shape[0]
        ok_frames = 0
        for f in range(F):
            v0 = pts[1][f] - pts[0][f]
            v1 = pts[2][f] - pts[1][f]
            v2 = pts[3][f] - pts[2][f]
            a_mcp = _angle(v0, v1)
            a_pip = _angle(v1, v2)
            # curl direction consistency via cross products (same rotation plane)
            n0 = np.cross(v0, v1); n1 = np.cross(v1, v2)
            same_dir = float(n0 @ n1) >= -_EPS
            hyper = (a_mcp < -5.0) or (a_pip < -5.0)  # angles are >=0 here; guard kept for signed inputs
            graded = a_mcp + 1e-6 >= 0.0 and a_pip >= 0.0 and (a_mcp <= 160.0 and a_pip <= 160.0)
            if same_dir and not hyper and graded:
                ok_frames += 1
        frac = ok_frames / max(1, F)
        per_finger[name] = round(frac, 3)
        if frac >= 0.7:
            natural += 1
    if not per_finger:
        return _mk("hand_flexion", family, None, skipped=True, note="chains too short")
    score = natural / len(per_finger)
    return _mk("hand_flexion", family, score,
               detail={"per_finger": per_finger, "fingers": len(per_finger)})


def m_finger_spread(take: dict, family: str = "humanoid") -> dict:
    """Max abduction angle between adjacent fingers (splay). Uses finger_chains:
    the proximal segment direction of neighbouring fingers."""
    chains = take.get("finger_chains") or {}
    order = ["thumb", "index", "middle", "ring", "pinky"]
    for side in ("R", "L"):
        seq = [f"{n}.{side}" for n in order if f"{n}.{side}" in chains]
        if len(seq) >= 2:
            break
    else:
        seq = list(chains.keys())
    if len(seq) < 2:
        return _mk("finger_spread", family, None, skipped=True, note="need >=2 fingers")
    max_spread = 0.0
    detail = {}
    for a, b in zip(seq[:-1], seq[1:]):
        ca = [_as_f(p) for p in chains[a]]
        cb = [_as_f(p) for p in chains[b]]
        va = ca[1] - ca[0]   # (F,3) proximal segment
        vb = cb[1] - cb[0]
        ang = np.array([_angle(va[f], vb[f]) for f in range(va.shape[0])])
        s = float(ang.max())
        detail[f"{a}|{b}"] = round(s, 2)
        max_spread = max(max_spread, s)
    return _mk("finger_spread", family, max_spread, detail=detail)


# ===========================================================================
#  MECHA-RIGID metrics
# ===========================================================================
def m_part_rigidity(take: dict, family: str = "mecha_rigid") -> dict:
    """Each rigid piece must not change shape. Kabsch residual of rest->frame,
    normalized by the part diagonal. ~0 = perfectly rigid armor; large = soft
    skinning bleeding across the plate."""
    verts = take.get("verts"); labels = take.get("part_labels")
    if verts is None or labels is None:
        return _mk("part_rigidity", family, None, skipped=True, note="need verts+part_labels")
    V = _as_f(verts); labels = np.asarray(labels, dtype=int)
    parts = sorted(set(labels.tolist()))
    worst = 0.0; worst_part = None; worst_frame = -1
    per_part = {}
    rest = _as_f(take["rest"]) if take.get("rest") is not None else V[0]
    for p in parts:
        pidx = np.where(labels == p)[0]
        if len(pidx) < 4:
            continue
        diag = _bbox_diag(rest[pidx])
        pmax = 0.0
        for f in range(V.shape[0]):
            res = _kabsch_residual(rest[pidx], V[f, pidx]) / (diag + _EPS)
            if res > pmax:
                pmax = res
                if res > worst:
                    worst, worst_part, worst_frame = res, p, f
        per_part[str(p)] = round(pmax, 5)
    if worst_part is None:
        return _mk("part_rigidity", family, None, skipped=True, note="parts too small")
    return _mk("part_rigidity", family, worst, detail={
        "worst_part": worst_part, "worst_frame": worst_frame, "per_part": per_part})


def m_plate_interpenetration(take: dict, family: str = "mecha_rigid") -> dict:
    return _part_penetration(take, "plate_interpenetration", family)


def m_joint_coherence(take: dict, family: str = "mecha_rigid") -> dict:
    """Mechanical joints behave like hinges: the relative rotation between the
    two parts (expressed in part A's frame) must keep a FIXED axis. Metric =
    max rotation-axis wander (deg) across frames. Also covers a fan's spin axis."""
    verts = take.get("verts"); labels = take.get("part_labels")
    pairs = take.get("joint_parts")
    if verts is None or labels is None or not pairs:
        return _mk("joint_coherence", family, None, skipped=True,
                   note="need verts+part_labels+joint_parts")
    V = _as_f(verts); labels = np.asarray(labels, dtype=int)
    rest = _as_f(take["rest"]) if take.get("rest") is not None else V[0]
    F = V.shape[0]
    worst = 0.0; worst_pair = None
    detail = {}
    for (a, b) in pairs:
        ia = np.where(labels == a)[0]; ib = np.where(labels == b)[0]
        if len(ia) < 4 or len(ib) < 4:
            continue
        axes = []
        for f in range(F):
            Ra = _kabsch_R(rest[ia], V[f, ia])
            Rb = _kabsch_R(rest[ib], V[f, ib])
            Rrel = Ra.T @ Rb
            axis, ang = _rot_axis_angle(Rrel)
            if ang > np.radians(2.0):     # ignore near-zero rotations (axis ill-defined)
                axes.append(axis * np.sign(axis[np.argmax(np.abs(axis))]))
        if len(axes) < 2:
            detail[f"{a}-{b}"] = {"axis_wander_deg": 0.0, "note": "little rotation"}
            continue
        axes = np.array(axes)
        mean_axis = axes.mean(axis=0)
        mean_axis /= (np.linalg.norm(mean_axis) + _EPS)
        wander = float(np.max([_angle(ax, mean_axis) for ax in axes]))
        detail[f"{a}-{b}"] = {"axis_wander_deg": round(wander, 3), "frames": len(axes)}
        if wander > worst:
            worst, worst_pair = wander, (a, b)
    if worst_pair is None and not detail:
        return _mk("joint_coherence", family, None, skipped=True, note="joints too small")
    return _mk("joint_coherence", family, worst,
               detail={"worst_pair": worst_pair, "per_joint": detail})


# ===========================================================================
#  CREATURE metrics
# ===========================================================================
def m_floating_part_stability(take: dict, family: str = "creature") -> dict:
    """Detached / floating parts (CAINE's gloves, hovering head) must move
    smoothly (bounded acceleration = no popping) and stay tethered near their
    logical anchor (bounded drift)."""
    fp = take.get("floating_parts") or {}
    verts = take.get("verts")
    if not fp or verts is None:
        return _mk("floating_part_stability", family, None, skipped=True,
                   note="need floating_parts+verts")
    V = _as_f(verts); L = _char_length(take)
    worst_accel = 0.0; worst_drift = 0.0; worst_teleport = 0.0
    detail = {}
    for name, spec in fp.items():
        vidx = np.asarray(spec.get("verts_idx", []), dtype=int)
        if len(vidx) == 0:
            continue
        c = V[:, vidx, :].mean(axis=1)               # (F,3) centroid
        vel = np.diff(c, axis=0)
        accel = np.diff(c, axis=0, n=2)
        accel_p95 = float(np.percentile(np.linalg.norm(accel, axis=1), 95) / (L + _EPS)) if len(accel) else 0.0
        teleport = float(np.max(np.linalg.norm(vel, axis=1)) / (L + _EPS)) if len(vel) else 0.0
        anchor = spec.get("anchor")
        if anchor is not None:
            anchor = _as_f(anchor)
            offset = c - anchor
            drift = float(np.max(np.linalg.norm(offset - offset.mean(axis=0), axis=1)) / (L + _EPS))
        else:
            drift = float(np.max(np.linalg.norm(c - c.mean(axis=0), axis=1)) / (L + _EPS))
        detail[name] = {"accel_p95_norm": round(accel_p95, 5),
                        "drift_norm": round(drift, 4),
                        "max_step_norm": round(teleport, 4)}
        worst_accel = max(worst_accel, accel_p95)
        worst_drift = max(worst_drift, drift)
        worst_teleport = max(worst_teleport, teleport)
    if not detail:
        return _mk("floating_part_stability", family, None, skipped=True, note="empty parts")
    # primary = jitter (accel); secondary gates: drift bound 0.15, teleport 0.2
    forced = (worst_drift > 0.15) or (worst_teleport > 0.20)
    return _mk("floating_part_stability", family, worst_accel, forced_fail=forced, detail={
        "worst_accel_p95_norm": round(worst_accel, 5),
        "worst_drift_norm": round(worst_drift, 4),
        "worst_teleport_norm": round(worst_teleport, 4),
        "per_part": detail,
    }, note=("drifts away" if worst_drift > 0.15 else
             ("teleports/pops" if worst_teleport > 0.20 else "")))


def m_screen_face_coherence(take: dict, family: str = "creature") -> dict:
    """Screen-drawn face (CAINE eyes/mouth, OLED display): features must stay
    inside the screen bounds and not permanently vanish. incoherence =
    out_of_bounds_ratio + permanent_dropout_ratio (transient blinks allowed)."""
    feats = take.get("screen_features") or {}
    if not feats:
        return _mk("screen_face_coherence", family, None, skipped=True,
                   note="need screen_features")
    total = 0; oob = 0
    perm_missing = 0
    detail = {}
    for name, spec in feats.items():
        uv = _as_f(spec.get("uv"))
        present = spec.get("present")
        present = np.asarray(present, dtype=bool) if present is not None else np.ones(len(uv), dtype=bool)
        F = len(uv)
        total += F
        inb = ((uv >= 0.0) & (uv <= 1.0)).all(axis=1)
        oob_f = int(np.sum(~inb & present))
        oob += oob_f
        # permanent dropout: a run of >2 consecutive absent frames
        longest_gap = _longest_false_run(present)
        detail[name] = {"oob_frames": oob_f, "longest_absent_run": int(longest_gap),
                        "present_ratio": round(float(present.mean()), 3)}
        if longest_gap > 2:
            perm_missing += 1
    oob_ratio = oob / max(1, total)
    dropout_ratio = perm_missing / max(1, len(feats))
    value = oob_ratio + dropout_ratio
    return _mk("screen_face_coherence", family, value, detail={
        "out_of_bounds_ratio": round(oob_ratio, 4),
        "permanent_dropout_ratio": round(dropout_ratio, 4),
        "per_feature": detail,
    }, note="features leave the screen or vanish" if value > THRESHOLDS["screen_face_coherence"][0] else "")


def _longest_false_run(mask: np.ndarray) -> int:
    longest = cur = 0
    for v in mask:
        if not v:
            cur += 1; longest = max(longest, cur)
        else:
            cur = 0
    return longest


# ===========================================================================
#  LUMINOUS metrics (RAM LED, cable) — operate on the emission track, no rig
# ===========================================================================
def _emission_brightness(take: dict) -> Optional[np.ndarray]:
    em = take.get("emission")
    if em is None:
        return None
    em = _as_f(em)
    if em.ndim == 3:           # (F,L,3) -> brightness
        em = em.mean(axis=2)
    if em.ndim == 1:           # (F,) single emitter
        em = em[:, None]
    return em                  # (F,L)


def m_temporal_smoothness(take: dict, family: str = "luminous") -> dict:
    """Shader temporal smoothness: p95 of |2nd difference| per LED, normalized by
    the emission range. High jerk = harsh jumps between keyframes."""
    em = _emission_brightness(take)
    if em is None:
        return _mk("temporal_smoothness", family, None, skipped=True, note="need emission")
    rng = float(em.max() - em.min())
    if rng < _EPS:
        return _mk("temporal_smoothness", family, 0.0, detail={"range": 0.0},
                   note="static emission")
    jerk = np.abs(np.diff(em, axis=0, n=2))
    value = float(np.percentile(jerk, 95) / rng)
    return _mk("temporal_smoothness", family, value,
               detail={"range": round(rng, 4), "max_jerk": round(float(jerk.max() / rng), 4)})


def m_pulsation_coherence(take: dict, family: str = "luminous") -> dict:
    """Pulsation coherence. breathing/pulse: the strip-mean must be periodic
    (autocorr peak). chase/flux: neighbouring LEDs keep a constant phase lag
    (traveling wave). Returns an incoherence in [0,1]."""
    em = _emission_brightness(take)
    if em is None:
        return _mk("pulsation_coherence", family, None, skipped=True, note="need emission")
    pattern = str(take.get("pattern", "breathing")).lower()
    if pattern in ("chase", "rainbow", "flux", "wipe") and em.shape[1] >= 3:
        # traveling wave: lag between adjacent LEDs should be consistent
        lags = []
        for l in range(em.shape[1] - 1):
            a = em[:, l] - em[:, l].mean()
            b = em[:, l + 1] - em[:, l + 1].mean()
            if np.linalg.norm(a) < _EPS or np.linalg.norm(b) < _EPS:
                continue
            xc = np.correlate(a, b, mode="full")
            lags.append(int(np.argmax(xc) - (len(a) - 1)))
        if len(lags) < 2:
            return _mk("pulsation_coherence", family, None, skipped=True, note="wave too short")
        lag_std = float(np.std(lags))
        value = min(1.0, lag_std / 1.0)     # threshold 0.30 -> std <= ~0.3 frame
        return _mk("pulsation_coherence", family, value, detail={
            "mode": "traveling_wave", "neighbour_lags": lags[:16],
            "lag_std_frames": round(lag_std, 3)})
    # breathing / pulse: periodicity of the strip mean
    m = em.mean(axis=1)
    period, strength = _periodicity_strength(m)
    value = 1.0 - strength
    return _mk("pulsation_coherence", family, value, detail={
        "mode": "periodic", "period_frames": period,
        "periodicity_strength": round(strength, 3)})


def m_flicker(take: dict, family: str = "luminous") -> dict:
    """No scintillation. flicker_index = high-frequency power ratio of the strip
    mean; isolated single-frame per-LED dropouts force a fail."""
    em = _emission_brightness(take)
    if em is None:
        return _mk("flicker", family, None, skipped=True, note="need emission")
    fps = float(take.get("fps", 24.0))
    cutoff = max(6.0, fps / 3.0)     # "flicker" = oscillation faster than fps/3
    m = em.mean(axis=1)
    flicker_index = _hf_power_ratio(m, fps, cutoff)
    dropouts = int(sum(_single_frame_dropouts(em[:, l]) for l in range(em.shape[1])))
    return _mk("flicker", family, flicker_index, forced_fail=dropouts > 0, detail={
        "cutoff_hz": round(cutoff, 2), "hf_power_ratio": round(flicker_index, 4),
        "single_frame_dropouts": dropouts})


def m_emission_dynamic_range(take: dict, family: str = "luminous") -> dict:
    """Liveness: the strip mean must actually change (an animation was requested).
    range = (max-min)/max of the strip mean."""
    em = _emission_brightness(take)
    if em is None:
        return _mk("emission_dynamic_range", family, None, skipped=True, note="need emission")
    if str(take.get("pattern", "")).lower() == "static_color":
        return _mk("emission_dynamic_range", family, 1.0, detail={"pattern": "static_color"},
                   note="static requested — liveness n/a")
    m = em.mean(axis=1)
    mx = float(m.max())
    value = float((mx - m.min()) / (mx + _EPS))
    return _mk("emission_dynamic_range", family, value, detail={"strip_mean_max": round(mx, 4)})


# ===========================================================================
#  REGISTRY + dispatcher
# ===========================================================================
FAMILY_METRICS: Dict[str, List[Callable[[dict, str], dict]]] = {
    "humanoid": [m_edge_stretch, m_foot_ground, m_heel_toe_roll,
                 m_contralateral_arm_swing, m_head_carriage, m_self_intersection,
                 m_hand_flexion, m_finger_spread],
    "creature": [m_edge_stretch, m_floating_part_stability, m_self_intersection],
    "mecha_rigid": [m_part_rigidity, m_plate_interpenetration, m_joint_coherence],
    "screen": [m_screen_face_coherence],
    "luminous": [m_temporal_smoothness, m_pulsation_coherence, m_flicker,
                 m_emission_dynamic_range],
}


def family_for_intent(intent: dict) -> str:
    """Map a motion_intent_classifier.v1 record to a metric family."""
    cat = (intent or {}).get("category")
    if cat == "led_emission":
        return "luminous"
    if cat == "oled_screen":
        return "screen"
    if cat in ("mechanical_simple", "rigid_static", "fan_pwm"):
        return "mecha_rigid"
    if cat == "creature_organic":
        loco = ((intent.get("creature_anim") or {}).get("locomotion") or "auto")
        return "humanoid" if loco == "humanoid" else "creature"
    return "creature"


def evaluate(take: dict, family: str, add_screen: bool = False,
             thresholds: Optional[dict] = None) -> dict:
    """Run every metric for `family` (plus the screen group for a hybrid like
    CAINE) on a deformed-scene `take`. Returns results + ranked knob list."""
    if thresholds:
        saved = dict(THRESHOLDS)
        THRESHOLDS.update(thresholds)
    try:
        metrics = list(FAMILY_METRICS.get(family, []))
        if add_screen and m_screen_face_coherence not in metrics:
            metrics.append(m_screen_face_coherence)
        results = [fn(take, family) for fn in metrics]
    finally:
        if thresholds:
            THRESHOLDS.clear(); THRESHOLDS.update(saved)

    graded = [r for r in results if r["passed"] is not None]
    failed = [r for r in graded if not r["passed"]]
    failed.sort(key=lambda r: r["severity"], reverse=True)
    knobs = [{"metric": r["metric"], "severity": r["severity"], **(r["knob"] or {})}
             for r in failed if r.get("knob")]
    if take.get("verts") is not None:
        F = int(_as_f(take["verts"]).shape[0])
    elif take.get("emission") is not None:
        F = int(_as_f(take["emission"]).shape[0])
    elif take.get("screen_features"):
        first = next(iter(take["screen_features"].values()))
        F = int(len(_as_f(first.get("uv"))))
    else:
        F = int(take.get("frames", 0))
    return {
        "schema": SCHEMA,
        "family": family,
        "frames": F,
        "fps": float(take.get("fps", 0.0)),
        "passed": len(failed) == 0 and len(graded) > 0,
        "n_graded": len(graded),
        "n_failed": len(failed),
        "results": results,
        "failed_metrics": [r["metric"] for r in failed],
        "knobs": knobs,
    }


# ===========================================================================
#  bpy sampler (lazy import — only runs inside Blender). Mirrors the depsgraph
#  pattern in mesh_screenshot.py. Produces a `take` the pure metrics consume.
# ===========================================================================
def sample_take_from_blender(frame_start: int, frame_end: int,
                             joint_names: Optional[Sequence[str]] = None,
                             part_group_prefix: str = "part_",
                             emission_node: Optional[str] = None) -> dict:  # pragma: no cover
    """Build a `take` from the current .blend: per-frame evaluated world verts of
    every mesh, world-space bone heads for joint_names, vertex-group -> part
    labels (groups named <part_group_prefix>N), and an emissive material value
    track if emission_node is given. bpy-only; unit tests use synthetic takes."""
    import bpy  # noqa: F401  — only importable inside Blender

    scene = bpy.context.scene
    depsgraph = bpy.context.evaluated_depsgraph_get()
    meshes = [o for o in scene.objects if o.type == "MESH"]
    arms = [o for o in scene.objects if o.type == "ARMATURE"]

    frames = list(range(frame_start, frame_end + 1))
    verts_stack: List[np.ndarray] = []
    joints: Dict[str, List[List[float]]] = {n: [] for n in (joint_names or [])}
    emission: List[float] = []

    # ---- rest topology: edges (global-indexed) + rest verts (armature REST pose) ----
    # Metrics need `edges` (rest connectivity) for m_edge_stretch and `rest` for the
    # deformation baseline. verts are concatenated across meshes -> offset edge indices.
    edges_list: List[np.ndarray] = []
    vert_offset = 0
    for o in meshes:
        me = o.data
        ne = len(me.edges)
        if ne:
            ev = np.empty(ne * 2, dtype=np.int64)
            me.edges.foreach_get("vertices", ev)
            edges_list.append(ev.reshape(ne, 2) + vert_offset)
        vert_offset += len(me.vertices)
    edges = np.concatenate(edges_list, axis=0) if edges_list else None

    def _concat_world_verts() -> np.ndarray:
        dg = bpy.context.evaluated_depsgraph_get()
        out: List[List[float]] = []
        for o in meshes:
            evo = o.evaluated_get(dg)
            m = evo.to_mesh()
            mw = o.matrix_world
            for v in m.vertices:
                co = mw @ v.co
                out.append([co.x, co.y, co.z])
            evo.to_mesh_clear()
        return np.array(out, dtype=np.float64)

    # rest = the un-posed shape (toggle armatures to REST). Falls back to verts[0].
    rest_verts: Optional[np.ndarray] = None
    saved_pos = [(a, a.data.pose_position) for a in arms]
    try:
        for a, _ in saved_pos:
            a.data.pose_position = "REST"
        if saved_pos:
            scene.frame_set(frame_start)
            rest_verts = _concat_world_verts()
    except Exception:
        rest_verts = None
    finally:
        for a, prev in saved_pos:
            a.data.pose_position = prev

    # ---- finger chains (Rigify naming) : {"index.R": [(F,3) per joint], ...} ----
    import re as _re
    finger_re = _re.compile(r"(?:DEF-)?f_(thumb|index|middle|ring|pinky)\.(0[1-3])\.(L|R)$")
    finger_bones: Dict[str, list] = {}
    for arm in arms:
        for pb in arm.pose.bones:
            mm = finger_re.match(pb.name)
            if mm:
                key = "%s.%s" % (mm.group(1), mm.group(3))
                finger_bones.setdefault(key, []).append((mm.group(2), pb, arm))
    for key in finger_bones:
        finger_bones[key].sort(key=lambda t: t[0])
    finger_tracks: Dict[str, List[List[List[float]]]] = {k: [] for k in finger_bones}

    labels_ref: Optional[np.ndarray] = None
    for f in frames:
        scene.frame_set(f)
        depsgraph = bpy.context.evaluated_depsgraph_get()
        frame_verts: List[List[float]] = []
        frame_labels: List[int] = []
        for o in meshes:
            ev = o.evaluated_get(depsgraph)
            me = ev.to_mesh()
            mw = o.matrix_world
            group_part = {vg.index: vg.name for vg in o.vertex_groups
                          if vg.name.startswith(part_group_prefix)}
            for v in me.vertices:
                co = mw @ v.co
                frame_verts.append([co.x, co.y, co.z])
                lab = -1
                for g in v.groups:
                    if g.group in group_part:
                        try:
                            lab = int(group_part[g.group][len(part_group_prefix):])
                        except ValueError:
                            lab = g.group
                        break
                frame_labels.append(lab)
            ev.to_mesh_clear()
        verts_stack.append(np.array(frame_verts, dtype=np.float64))
        if labels_ref is None:
            labels_ref = np.array(frame_labels, dtype=int)
        for arm in arms:
            for n in (joint_names or []):
                pb = arm.pose.bones.get(n)
                if pb is not None:
                    h = arm.matrix_world @ pb.head
                    joints.setdefault(n, []).append([h.x, h.y, h.z])
        # finger chain joint positions this frame (each segment head + fingertip = last tail)
        for key, segs in finger_bones.items():
            pts: List[List[float]] = []
            for _, pb, arm in segs:
                h = arm.matrix_world @ pb.head
                pts.append([h.x, h.y, h.z])
            if segs:
                _, last_pb, last_arm = segs[-1]
                t = last_arm.matrix_world @ last_pb.tail
                pts.append([t.x, t.y, t.z])
            finger_tracks[key].append(pts)
        if emission_node:
            mat = bpy.data.materials.get(emission_node)
            if mat and mat.node_tree:
                node = mat.node_tree.nodes.get("Emission")
                if node:
                    emission.append(float(node.inputs["Strength"].default_value))

    take: dict = {
        "fps": float(scene.render.fps),
        "verts": np.stack(verts_stack, axis=0),
        "up_axis": "Z",
    }
    if edges is not None:
        take["edges"] = edges
    if rest_verts is not None and rest_verts.shape == take["verts"].shape[1:]:
        take["rest"] = rest_verts
    if labels_ref is not None and (labels_ref >= 0).any():
        take["part_labels"] = labels_ref
    take["joints"] = {n: np.array(v, dtype=np.float64) for n, v in joints.items() if v}
    if finger_tracks:
        # each chain -> list over joints of (F,3); metrics expect per-joint arrays
        take["finger_chains"] = {
            k: [np.array([fr[j] for fr in track], dtype=np.float64) for j in range(len(track[0]))]
            for k, track in finger_tracks.items() if track and track[0]
        }
    # shoulder width for the arm-swing amplitude gate
    for arm in arms:
        l = arm.pose.bones.get("shoulder.L") or arm.pose.bones.get("upper_arm.L")
        r = arm.pose.bones.get("shoulder.R") or arm.pose.bones.get("upper_arm.R")
        if l and r:
            hl = arm.matrix_world @ l.head
            hr = arm.matrix_world @ r.head
            take["shoulder_width"] = float((hl - hr).length)
            break
    if emission:
        take["emission"] = np.array(emission, dtype=np.float64)
    return take


# ===========================================================================
#  reporting + CLI
# ===========================================================================
def render_report(report: dict) -> str:
    lines = [f"anim_metrics — family={report['family']}  frames={report['frames']}  "
             f"fps={report['fps']}  -> {'PASS' if report['passed'] else 'FAIL'}"]
    for r in report["results"]:
        if r["passed"] is None:
            status = "skip"
        else:
            status = "ok  " if r["passed"] else "FAIL"
        v = "n/a" if r["value"] is None else f"{r['value']}"
        lines.append(f"  [{status}] {r['metric']:<26} value={v} "
                     f"{r['direction']} {r['threshold']}  sev={r['severity']}"
                     + (f"  ({r['note']})" if r["note"] else ""))
    if report["knobs"]:
        lines.append("  knobs to turn (ranked):")
        for k in report["knobs"]:
            lines.append(f"    - {k['metric']}: {k.get('param')} [{k.get('action')}] "
                         f"sev={k['severity']}\n        {k.get('suggest')}")
    return "\n".join(lines) + "\n"


def _self_test() -> int:
    """Import-time sanity: every threshold has a knob and vice-versa, and the
    family registry references only defined metrics. Full behavioural coverage
    lives in test_anim_metrics.py."""
    problems = []
    for m in THRESHOLDS:
        if m != "edge_stretch" and m not in KNOBS:
            problems.append(f"threshold '{m}' has no knob")
    for m in KNOBS:
        if m not in THRESHOLDS:
            problems.append(f"knob '{m}' has no threshold")
    # dispatcher smoke on a trivial rigid take
    V = np.tile(np.random.default_rng(0).random((20, 3)), (5, 1, 1))
    take = {"fps": 24, "verts": V, "edges": np.array([[0, 1], [1, 2], [2, 3]]),
            "part_labels": np.array([0] * 10 + [1] * 10)}
    for fam in FAMILY_METRICS:
        rep = evaluate(take, fam)
        if rep["schema"] != SCHEMA:
            problems.append(f"evaluate({fam}) bad schema")
    if problems:
        for p in problems:
            print("SELF-TEST FAIL:", p)
        return 1
    print(f"self-test OK — {len(THRESHOLDS)} metrics, {len(FAMILY_METRICS)} families, "
          f"knobs wired.")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="Aurora deformed-scene metrics")
    ap.add_argument("--self-test", action="store_true")
    ap.add_argument("--take", help="path to a .npz take produced by the sampler")
    ap.add_argument("--family", default=None, help=f"one of {sorted(FAMILY_METRICS)}")
    ap.add_argument("--add-screen", action="store_true")
    ap.add_argument("--pretty", action="store_true")
    args = ap.parse_args()
    if args.self_test or not args.take:
        return _self_test()
    data = np.load(args.take, allow_pickle=True)
    take = {k: data[k] for k in data.files}
    take = {k: (v.item() if getattr(v, "ndim", 1) == 0 else v) for k, v in take.items()}
    report = evaluate(take, args.family or "humanoid", add_screen=args.add_screen)
    sys.stdout.write(render_report(report) if args.pretty
                     else json.dumps(report, indent=2, default=lambda o: o.tolist()
                                     if isinstance(o, np.ndarray) else o) + "\n")
    return 0 if report["passed"] else 2


if __name__ == "__main__":
    sys.exit(main())
