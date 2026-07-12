"""motion_baker — bake aurora.motion.v1 descriptors into Blender NLA actions.

The TS side (application/src/services/motionSerializer.ts) emits a JSON
descriptor of the form:

    {
      "schema": "aurora.motion.v1",
      "id": "character.walk_cycle",
      "loop": true,
      "fps": 24,
      "duration_seconds": 1.0,
      "frame_count": 24,
      "primitives": [
        { "kind": "gait", "target": "legs", "amplitude": 30, ... },
        ...
      ]
    }

This module compiles that descriptor into a list of BoneInstruction dicts
that the bpy-side apply_compiled_motion() then turns into real keyframes
on the Rigify-generated armature. The pure compile_motion_payload() layer
is bpy-free so it can be unit tested via `python motion_baker.py --self-test`.

Wire to rigify_autorig.py:
  - rigify_autorig.py accepts --motion <json_path>
  - reads the JSON, calls compile_motion_payload(motion)
  - inside the embedded Blender script, calls apply_compiled_motion(rig, compiled)
  - exports the GLB with export_animations=True (already on)

Pure: top-level imports here are stdlib only. bpy is imported lazily inside
apply_compiled_motion() so this file is import-safe outside Blender.
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from typing import Any, Dict, List, Optional

# ---------------------------------------------------------------------------
#  TARGET -> BONE NAME RESOLUTION (Rigify default human metarig naming)
# ---------------------------------------------------------------------------
# Rigify generates control bones with the naming used below. If the rig is
# generated from a custom metarig the names may differ — apply_compiled_motion
# logs a warning and skips bones that don't exist instead of crashing.

TARGET_TO_BONES: Dict[str, List[str]] = {
    # Locomotion — v112: switched to DEF- deform bones. Rigify's FK/IK
    # switch is not always reachable (no custom-props exposed on the
    # generated rig in some 5.1 builds), so keyframing FK bones leaves
    # the mesh static because the DEF bones only follow IK. Targeting
    # DEF bones directly (with their constraints muted upstream) makes
    # the animation drive the mesh unconditionally. See
    # memory/pipeline-deformation-3d.md.
    "legs": ["DEF-thigh.L", "DEF-thigh.R", "DEF-shin.L", "DEF-shin.R", "DEF-foot.L", "DEF-foot.R"],
    "left_leg": ["DEF-thigh.L", "DEF-shin.L", "DEF-foot.L"],
    "right_leg": ["DEF-thigh.R", "DEF-shin.R", "DEF-foot.R"],
    "right_knee": ["DEF-thigh.R", "DEF-shin.R"],
    "hips_knees": ["DEF-thigh.L", "DEF-thigh.R", "DEF-shin.L", "DEF-shin.R", "DEF-spine"],

    # Upper body — v112: arms drive via IK targets (hand_ik.L/R) with
    # location keyframes, NOT DEF rotation. Reason: Rigify's arm-bone
    # local axes are twist/abduction after A-pose adjustment, so rotating
    # DEF-upper_arm on any single Euler axis either twists the mesh into
    # the torso (X) or flaps the arm out (Z). The IK target sweeps the
    # HAND forward/back and Rigify's IK chain rebuilds the shoulder-elbow
    # curve naturally.
    "arms": ["hand_ik.L", "hand_ik.R"],
    "left_arm": ["hand_ik.L"],
    "right_arm": ["hand_ik.R"],
    "right_arm_raised": ["hand_ik.R"],
    "hands": ["DEF-hand.L", "DEF-hand.R"],

    # Torso / pelvis
    "torso": ["torso", "spine_fk.001", "spine_fk.002"],
    "chest": ["chest"],
    "pelvis": ["torso"],
    "hips": ["torso"],

    # Whole body — v112: crawl / four-point gait uses DEF- for legs
    # (which we can rotate directly) + hand_ik for arms (IK sweep).
    "body": ["root"],
    "arms_legs": [
        "DEF-thigh.L", "DEF-thigh.R", "DEF-shin.L", "DEF-shin.R",
        "hand_ik.L", "hand_ik.R",
    ],

    # v77zt: quadruped (Rigify basic_quadruped metarig). Front legs reuse
    # the upper_arm/forearm/hand chain (anatomically the front leg of a
    # quadruped is the equivalent of an arm); hind legs use thigh/shin/foot.
    "front_legs": ["upper_arm_fk.L", "upper_arm_fk.R", "forearm_fk.L", "forearm_fk.R"],
    "hind_legs": ["thigh_fk.L", "thigh_fk.R", "shin_fk.L", "shin_fk.R"],
    "back_legs": ["thigh_fk.L", "thigh_fk.R", "shin_fk.L", "shin_fk.R"],
    "all_four_legs": [
        "thigh_fk.L", "thigh_fk.R", "shin_fk.L", "shin_fk.R",
        "upper_arm_fk.L", "upper_arm_fk.R", "forearm_fk.L", "forearm_fk.R",
    ],
    "tail": ["tail_fk", "tail_fk.001", "tail_fk.002", "tail_fk.003", "tail_fk.004"],
    "ears": ["ear.L", "ear.R", "ear_fk.L", "ear_fk.R"],
    "snout": ["face_snout", "snout"],
    "head": ["head_fk", "head"],
    "neck": ["neck_fk", "neck"],

    # Non-rigify (mechanism / vehicle / creature) — empty list means "object root"
    "drive_gear": [],
    "driven_gear": [],
    "drive_pulley": [],
    "driven_pulley": [],
    "belt": [],
    "rod": [],
    "leaf": [],
    "crank": [],
    "rocker": [],
    "wheels": [],
    "rotors": [],
    "wings": [],  # Creature wings have no rigify equivalent
}


# ---------------------------------------------------------------------------
#  PURE COMPILER (testable without bpy)
# ---------------------------------------------------------------------------

# A BoneInstruction is a dict of the form:
#   {
#     "bone": "thigh_fk.L",
#     "channel": "rotation_euler" | "location" | "scale",
#     "axis_index": 0 | 1 | 2,           # x=0, y=1, z=2
#     "samples": [(frame:int, value:float), ...],  # absolute keyframe values
#     "interpolation": "BEZIER" | "LINEAR",
#     "source_kind": "gait" | "rotate" | ...,      # for diagnostics
#     "source_target": "legs" | ...
#   }


def _axis_to_index(axis: Optional[str]) -> int:
    if axis == "x":
        return 0
    if axis == "y":
        return 1
    if axis == "z":
        return 2
    # "auto" / None → default to x for rotations, z for translations (caller decides)
    return 0


def _phase_for_bone(bone_name: str) -> float:
    """Returns 0.0 for left / drive bones, 0.5 for right / driven bones.

    Used to alternate bilateral motion (walk: L leg forward while R is back).
    """
    if bone_name.endswith(".R") or "right" in bone_name.lower() or "driven" in bone_name.lower():
        return 0.5
    return 0.0


def _resolve_target(target: Optional[str]) -> List[str]:
    if not target:
        return []
    return list(TARGET_TO_BONES.get(target, []))


_QUADRUPED_TARGETS = {"front_legs", "hind_legs", "back_legs", "all_four_legs"}


def _is_arm_bone(bone: str) -> bool:
    b = bone.lower()
    # matches upper_arm, forearm, hand, hand_ik in all Rigify prefixes
    # (DEF-, MCH-, ORG-, plain FK/IK controls).
    return ("arm" in b) or ("hand" in b)


def _is_shin_bone(bone: str) -> bool:
    b = bone.lower()
    return ("shin" in b) or ("forearm" in b)


def _is_foot_bone(bone: str) -> bool:
    b = bone.lower()
    # Rigify bones exist as DEF-foot.L, foot_ik.L, foot_fk.L, toe_ik.L etc.
    # We match by substring so any prefix is accepted (DEF-, MCH-, ORG-, none).
    return ("foot" in b) or ("toe" in b) or ("ankle" in b)


def _gait_phase_for_bone(bone: str, target: Optional[str]) -> float:
    """Phase (in cycles, 0..1) of a bone in a believable gait cycle.

    Biomechanics encoded here (this is what made the old walk look robotic):
      • Bilateral alternation: left vs right offset by 0.5 (L leg forward
        while R leg is back).
      • Contralateral arm swing: the arm counter-swings the SAME-side leg —
        so an arm bone gets +0.5 on top of its left/right phase (right arm
        forward when right leg is back).
      • Quadruped diagonal trot: hind legs offset +0.5 from front legs of
        the same side → front-left moves with hind-right.
      • Knee lag: the shin/lower segment trails the thigh by ~0.08 cycle
        (heel-strike → the knee keeps extending a beat after the hip).
    """
    is_quadruped = target in _QUADRUPED_TARGETS
    side = 0.5 if (bone.endswith(".R") or "right" in bone.lower() or "driven" in bone.lower()) else 0.0
    ph = side
    if _is_arm_bone(bone) and not is_quadruped:
        # contralateral arm swing — but in a quadruped the "arm" bones ARE the
        # front legs (anatomically), so they follow leg phasing, not arm-swing.
        ph += 0.5
    if is_quadruped and (("thigh" in bone.lower()) or ("shin" in bone.lower())):
        ph += 0.5  # hind legs trot diagonally to front legs
    if _is_shin_bone(bone):
        ph += 0.08  # knee/lower-segment lag behind the upper segment
    return ph % 1.0


def _compile_gait(p: Dict[str, Any], fps: int, frame_count: int) -> List[Dict[str, Any]]:
    """gait: cyclic locomotion (bipedal walk/run, quadruped trot). Each
    leg/arm bone sweeps around its hinge axis with a biomechanically-correct
    phase (bilateral alternation + contralateral arm swing + knee lag +
    quadruped diagonal). Lower segments (shin/forearm/foot) swing with a
    reduced amplitude so the limb articulates instead of swinging like a
    stiff pendulum.

    v112 — two channels depending on bone kind:
      • LEGS on DEF- bones — rotation around local X (index 0). Bone points
        DOWN so local X = walking-forward direction; rotation = the swing.
      • ARMS on hand_ik.L/R — LOCATION on world-forward axis (index 1).
        The IK target sweeps the hand back and forth by a small distance
        (~14 cm) and Rigify's arm IK chain rebuilds the shoulder-elbow
        pose. Reason: DEF-upper_arm's local Euler axes are twist/abduction
        after the A-pose adjustment; no single-axis rotation gives a clean
        forward/back arm swing, but sweeping the IK target does.
    """
    target = p.get("target")
    bones = _resolve_target(target)
    if not bones:
        return []
    amplitude_deg = float(p.get("amplitude") or 30)
    amplitude_rad = math.radians(amplitude_deg)
    freq_hz = float(p.get("frequency_hz") or 1.0)
    is_quadruped = target in _QUADRUPED_TARGETS
    out: List[Dict[str, Any]] = []
    # Physical peak sweep for a walking arm hand (meters). Real humans swing
    # the hand ~15–25 cm forward-back at normal walking pace; we scale this
    # by the source amplitude (25° → 0.14 m, 50° → 0.28 m) so faster gaits
    # produce bigger arm sweeps.
    arm_ik_reach = 0.14 * max(0.5, amplitude_deg / 25.0)
    for bone in bones:
        phase = _gait_phase_for_bone(bone, target)
        is_shin = _is_shin_bone(bone)
        is_foot = _is_foot_bone(bone)
        is_arm = _is_arm_bone(bone) and not is_quadruped
        is_ik_target = bone.endswith("_ik.L") or bone.endswith("_ik.R") or bone.endswith("_ik")

        if is_ik_target and is_arm:
            # IK target sweep: hand moves forward/back on Y (walking axis).
            channel = "location"
            axis_idx = 1  # world-forward axis on Rigify's IK pose-bone frame
            samples: List[tuple] = []
            for f in range(1, frame_count + 1):
                t = (f - 1) / fps
                s = math.sin(2 * math.pi * freq_hz * t + 2 * math.pi * phase)
                samples.append((f, arm_ik_reach * s))
            out.append({
                "bone": bone,
                "channel": channel,
                "axis_index": axis_idx,
                "samples": samples,
                "interpolation": "BEZIER",
                "source_kind": "gait",
                "source_target": target,
            })
            continue

        if is_foot:
            amp = amplitude_rad * 0.38
        elif is_shin:
            amp = amplitude_rad * 0.9
        else:
            amp = amplitude_rad
        axis_idx = 0
        samples = []
        for f in range(1, frame_count + 1):
            t = (f - 1) / fps
            s = math.sin(2 * math.pi * freq_hz * t + 2 * math.pi * phase)
            if is_shin and not is_quadruped:
                # knee flexion — only bends inward, never hyperextends
                value = -amp * (0.10 + 0.90 * max(0.0, s))
            elif is_foot and not is_quadruped:
                # foot roll — heel-strike + toe-off
                value = amp * (0.30 * s + 0.25 * max(0.0, -s))
            else:
                value = amp * s
            samples.append((f, value))
        out.append({
            "bone": bone,
            "channel": "rotation_euler",
            "axis_index": axis_idx,
            "samples": samples,
            "interpolation": "BEZIER",
            "source_kind": "gait",
            "source_target": target,
        })
    return out


def _compile_oscillate(p: Dict[str, Any], fps: int, frame_count: int) -> List[Dict[str, Any]]:
    """oscillate: back-and-forth around a center on the chosen axis.

    Used for hip sway, knee bounce, applaud (hand contact rebound),
    pelvis vertical bounce. Translation if amplitude < 1 (meters), else
    treated as degrees rotation.
    """
    bones = _resolve_target(p.get("target"))
    if not bones:
        return []
    amplitude = float(p.get("amplitude") or 5)
    freq_hz = float(p.get("frequency_hz") or 1.0)
    axis_idx = _axis_to_index(p.get("axis"))
    is_translation = abs(amplitude) < 1.0
    if not is_translation:
        amplitude = math.radians(amplitude)
    out: List[Dict[str, Any]] = []
    for bone in bones:
        samples = []
        for f in range(1, frame_count + 1):
            t = (f - 1) / fps
            value = amplitude * math.sin(2 * math.pi * freq_hz * t)
            samples.append((f, value))
        out.append({
            "bone": bone,
            "channel": "location" if is_translation else "rotation_euler",
            "axis_index": axis_idx,
            "samples": samples,
            "interpolation": "BEZIER",
            "source_kind": "oscillate",
            "source_target": p.get("target"),
        })
    return out


def _compile_rotate(p: Dict[str, Any], fps: int, frame_count: int) -> List[Dict[str, Any]]:
    """rotate: continuous rotation around an axis. Used for mechanism gears,
    pulleys, wheels, rotors. Value goes 0 → 2π (full revolution) over the
    cycle, then resets if loop=true.
    """
    target = p.get("target") or "body"
    bones = _resolve_target(target)
    amplitude_deg = float(p.get("amplitude") or 360)
    amplitude_rad = math.radians(amplitude_deg)
    axis_idx = _axis_to_index(p.get("axis"))
    out: List[Dict[str, Any]] = []
    bone_list = bones if bones else ["__object_root__"]
    target_str = (target or "").lower()
    for bone in bone_list:
        phase = _phase_for_bone(bone)
        # driven gears rotate opposite to driver — flip sign
        sign = -1.0 if ("driven" in (bone or "").lower() or "driven" in target_str) else 1.0
        samples = []
        for f in range(1, frame_count + 1):
            t = (f - 1) / frame_count
            value = sign * amplitude_rad * (t + phase)
            samples.append((f, value))
        out.append({
            "bone": bone,
            "channel": "rotation_euler",
            "axis_index": axis_idx,
            "samples": samples,
            "interpolation": "LINEAR",
            "source_kind": "rotate",
            "source_target": target,
        })
    return out


def _compile_translate(p: Dict[str, Any], fps: int, frame_count: int) -> List[Dict[str, Any]]:
    """translate: linear translation along an axis. Used for vehicle roll
    forward, belt loop, actuator rod extension.
    """
    target = p.get("target") or "body"
    bones = _resolve_target(target)
    amplitude = float(p.get("amplitude") or 1.0)
    axis_idx = _axis_to_index(p.get("axis"))
    out: List[Dict[str, Any]] = []
    bone_list = bones if bones else ["__object_root__"]
    for bone in bone_list:
        samples = []
        for f in range(1, frame_count + 1):
            t = (f - 1) / frame_count
            value = amplitude * t
            samples.append((f, value))
        out.append({
            "bone": bone,
            "channel": "location",
            "axis_index": axis_idx,
            "samples": samples,
            "interpolation": "LINEAR",
            "source_kind": "translate",
            "source_target": target,
        })
    return out


def _compile_swing(p: Dict[str, Any], fps: int, frame_count: int) -> List[Dict[str, Any]]:
    """swing: pendulum-like rotation. 0 → max → 0 → -max → 0 over a cycle."""
    return _compile_oscillate(
        {**p, "amplitude": float(p.get("amplitude") or 90)},
        fps, frame_count,
    )


def _compile_extend(p: Dict[str, Any], fps: int, frame_count: int) -> List[Dict[str, Any]]:
    """extend: actuator stroke. 0 → max → 0 over a cycle."""
    target = p.get("target") or "rod"
    bones = _resolve_target(target)
    amplitude = float(p.get("amplitude") or 0.3)
    axis_idx = _axis_to_index(p.get("axis"))
    out: List[Dict[str, Any]] = []
    bone_list = bones if bones else ["__object_root__"]
    for bone in bone_list:
        samples = []
        for f in range(1, frame_count + 1):
            t = (f - 1) / frame_count
            # triangle wave: 0 → 1 → 0
            value = amplitude * (1 - abs(2 * t - 1))
            samples.append((f, value))
        out.append({
            "bone": bone,
            "channel": "location",
            "axis_index": axis_idx,
            "samples": samples,
            "interpolation": "BEZIER",
            "source_kind": "extend",
            "source_target": target,
        })
    return out


def _compile_loop_path(p: Dict[str, Any], fps: int, frame_count: int) -> List[Dict[str, Any]]:
    """loop_path: closed-loop translation (belt around pulleys). For now
    this is a marker instruction; the bpy side reads source_kind=loop_path
    and applies a follow-curve modifier instead of plain keyframes.
    """
    return [{
        "bone": "__object_root__",
        "channel": "follow_curve",
        "axis_index": 0,
        "samples": [(1, 0.0), (frame_count, 1.0)],
        "interpolation": "LINEAR",
        "source_kind": "loop_path",
        "source_target": p.get("target"),
    }]


def _compile_gesture(p: Dict[str, Any], fps: int, frame_count: int) -> List[Dict[str, Any]]:
    """gesture: upper-body movement with arm + hand keyframes."""
    target = p.get("target") or "right_arm"
    bones = _resolve_target(target)
    if not bones:
        return []
    amplitude_deg = float(p.get("amplitude") or 30)
    amplitude_rad = math.radians(amplitude_deg)
    freq_hz = float(p.get("frequency_hz") or 1.0)
    out: List[Dict[str, Any]] = []
    for i, bone in enumerate(bones):
        per_bone_amp = amplitude_rad / max(1, (i + 1))  # taper toward extremities
        samples = []
        for f in range(1, frame_count + 1):
            t = (f - 1) / fps
            value = per_bone_amp * math.sin(2 * math.pi * freq_hz * t)
            samples.append((f, value))
        out.append({
            "bone": bone,
            "channel": "rotation_euler",
            "axis_index": 2,  # gestures rotate around Z (lateral)
            "samples": samples,
            "interpolation": "BEZIER",
            "source_kind": "gesture",
            "source_target": target,
        })
    return out


def _compile_jump(p: Dict[str, Any], fps: int, frame_count: int) -> List[Dict[str, Any]]:
    """jump: ballistic root-bone vertical translation."""
    amplitude = float(p.get("amplitude") or 1.0)
    axis_idx = 1  # Y is vertical in Blender's default convention
    samples = []
    for f in range(1, frame_count + 1):
        t = (f - 1) / max(1, frame_count - 1)
        # parabolic: peak at mid-frame
        value = amplitude * 4 * t * (1 - t)
        samples.append((f, value))
    return [{
        "bone": "root",
        "channel": "location",
        "axis_index": axis_idx,
        "samples": samples,
        "interpolation": "BEZIER",
        "source_kind": "jump",
        "source_target": p.get("target") or "root",
    }]


def _compile_crouch(p: Dict[str, Any], fps: int, frame_count: int) -> List[Dict[str, Any]]:
    """crouch: knee/hip flexion. Uses leg bones with rotation around X."""
    target = p.get("target") or "legs"
    bones = _resolve_target(target)
    if not bones:
        return []
    amplitude_deg = float(p.get("amplitude") or 60)
    amplitude_rad = math.radians(amplitude_deg)
    out: List[Dict[str, Any]] = []
    for bone in bones:
        sign = 1.0 if "shin" in bone else -0.5  # shins flex more than thighs
        samples = []
        for f in range(1, frame_count + 1):
            t = (f - 1) / max(1, frame_count - 1)
            # Hold pose: ramp in, hold, ramp out
            ramp = min(1.0, t * 4) * min(1.0, (1 - t) * 4)
            value = sign * amplitude_rad * ramp
            samples.append((f, value))
        out.append({
            "bone": bone,
            "channel": "rotation_euler",
            "axis_index": 0,
            "samples": samples,
            "interpolation": "BEZIER",
            "source_kind": "crouch",
            "source_target": target,
        })
    return out


def _compile_lunge(p: Dict[str, Any], fps: int, frame_count: int) -> List[Dict[str, Any]]:
    """lunge: forward thrust (kick / punch). Single-shot extension + retraction."""
    target = p.get("target") or "right_arm"
    bones = _resolve_target(target)
    if not bones:
        return []
    amplitude_deg = float(p.get("amplitude") or 90)
    amplitude_rad = math.radians(amplitude_deg)
    out: List[Dict[str, Any]] = []
    for bone in bones:
        samples = []
        for f in range(1, frame_count + 1):
            t = (f - 1) / max(1, frame_count - 1)
            # ease-out then return: 0 → 1 → 0 with peak at 60%
            if t < 0.6:
                v = amplitude_rad * (t / 0.6) ** 0.7
            else:
                v = amplitude_rad * (1 - (t - 0.6) / 0.4) ** 0.7
            samples.append((f, v))
        out.append({
            "bone": bone,
            "channel": "rotation_euler",
            "axis_index": 0,
            "samples": samples,
            "interpolation": "BEZIER",
            "source_kind": "lunge",
            "source_target": target,
        })
    return out


def _compile_flap(p: Dict[str, Any], fps: int, frame_count: int) -> List[Dict[str, Any]]:
    """flap: wing oscillation. Falls back to upper_arm bones if available, or
    object root rotation Z otherwise (creature with no Rigify rig)."""
    target = p.get("target") or "wings"
    bones = _resolve_target(target)
    if not bones:
        bones = ["__object_root__"]
    amplitude_deg = float(p.get("amplitude") or 60)
    amplitude_rad = math.radians(amplitude_deg)
    freq_hz = float(p.get("frequency_hz") or 3.0)
    out: List[Dict[str, Any]] = []
    for bone in bones:
        samples = []
        for f in range(1, frame_count + 1):
            t = (f - 1) / fps
            value = amplitude_rad * math.sin(2 * math.pi * freq_hz * t)
            samples.append((f, value))
        out.append({
            "bone": bone,
            "channel": "rotation_euler",
            "axis_index": 2,
            "samples": samples,
            "interpolation": "BEZIER",
            "source_kind": "flap",
            "source_target": target,
        })
    return out


def _compile_breathe(p: Dict[str, Any], fps: int, frame_count: int) -> List[Dict[str, Any]]:
    """breathe: chest scale / micro motion."""
    target = p.get("target") or "chest"
    bones = _resolve_target(target) or ["chest"]
    amplitude = float(p.get("amplitude") or 0.02)
    freq_hz = float(p.get("frequency_hz") or 0.25)
    out: List[Dict[str, Any]] = []
    for bone in bones:
        samples = []
        for f in range(1, frame_count + 1):
            t = (f - 1) / fps
            value = 1.0 + amplitude * math.sin(2 * math.pi * freq_hz * t)
            samples.append((f, value))
        out.append({
            "bone": bone,
            "channel": "scale",
            "axis_index": 1,  # Y is forward/depth — chest expands depth-wise
            "samples": samples,
            "interpolation": "BEZIER",
            "source_kind": "breathe",
            "source_target": target,
        })
    return out


def _compile_custom_pose(p: Dict[str, Any], fps: int, frame_count: int) -> List[Dict[str, Any]]:
    """custom_pose: free-text fallback. Holds the rest pose with a 1-frame
    marker keyframe carrying the description in source_target so the bpy
    layer can attach it as a pose marker for human review."""
    description = p.get("description") or "custom pose"
    return [{
        "bone": "root",
        "channel": "marker",
        "axis_index": 0,
        "samples": [(1, 0.0)],
        "interpolation": "LINEAR",
        "source_kind": "custom_pose",
        "source_target": description[:120],
    }]


def _compile_preset_ref(p: Dict[str, Any], fps: int, frame_count: int) -> List[Dict[str, Any]]:
    """Expand parser preset references into real aurora.motion.v1 primitives."""
    preset_id = str(p.get("source_target") or "")
    modifiers = p.get("modifiers") or {}
    speed_mul = float(modifiers.get("speedMul") or 1.0)
    amp_mul = float(modifiers.get("amplitudeMul") or 1.0)
    height_mul = float(modifiers.get("heightMul") or 1.0)

    if preset_id == "character.walk_cycle":
        return (
            _compile_gait({
                "target": "legs",
                "axis": "x",
                "amplitude": 30 * amp_mul,
                "frequency_hz": 1.0 * speed_mul,
            }, fps, frame_count)
            + _compile_gait({
                "target": "arms",
                "axis": "x",
                "amplitude": 24 * amp_mul,
                "frequency_hz": 1.0 * speed_mul,
            }, fps, frame_count)
            + _compile_oscillate({
                "target": "pelvis",
                "axis": "z",
                "amplitude": 0.035 * height_mul,
                "frequency_hz": 2.0 * speed_mul,
            }, fps, frame_count)
            + _compile_oscillate({
                "target": "torso",
                "axis": "z",
                "amplitude": 4 * amp_mul,
                "frequency_hz": 1.0 * speed_mul,
            }, fps, frame_count)
        )

    if preset_id == "character.run_cycle":
        return (
            _compile_gait({
                "target": "legs",
                "axis": "x",
                "amplitude": 42 * amp_mul,
                "frequency_hz": 1.7 * speed_mul,
            }, fps, frame_count)
            + _compile_gait({
                "target": "arms",
                "axis": "x",
                "amplitude": 34 * amp_mul,
                "frequency_hz": 1.7 * speed_mul,
            }, fps, frame_count)
            + _compile_oscillate({
                "target": "pelvis",
                "axis": "z",
                "amplitude": 0.055 * height_mul,
                "frequency_hz": 3.4 * speed_mul,
            }, fps, frame_count)
        )

    if preset_id == "character.idle":
        # Aurora: idle ARTICULEE. L'ancien preset n'animait que le torse (respiration) ->
        # tete/cou/bras figes -> percu comme statique. On ajoute un balayage lent de la tete,
        # un petit hochement de cou et un leger ballant de bras. Dans _compile_oscillate,
        # amplitude >= 1.0 = DEGRES (rotation par os); < 1.0 = translation. Cibles deja
        # mappees (TARGET_TO_BONES: head/neck/arms) -> bake par os, pas transform globale.
        return (
            _compile_breathe({
                "target": "torso",
                "axis": "z",
                "amplitude": 0.025 * height_mul,
                "frequency_hz": 0.35 * speed_mul,
            }, fps, frame_count)
            + _compile_oscillate({
                "target": "head",
                "axis": "y",
                "amplitude": 5.0,
                "frequency_hz": 0.16 * speed_mul,
            }, fps, frame_count)
            + _compile_oscillate({
                "target": "neck",
                "axis": "x",
                "amplitude": 2.5,
                "frequency_hz": 0.22 * speed_mul,
            }, fps, frame_count)
            + _compile_oscillate({
                "target": "arms",
                "axis": "x",
                "amplitude": 2.0,
                "frequency_hz": 0.2 * speed_mul,
            }, fps, frame_count)
        )

    return _compile_custom_pose({
        "description": preset_id or str(p.get("source_target") or "preset_ref"),
    }, fps, frame_count)


_COMPILER_DISPATCH = {
    "preset_ref": _compile_preset_ref,
    "gait": _compile_gait,
    "oscillate": _compile_oscillate,
    "rotate": _compile_rotate,
    "translate": _compile_translate,
    "swing": _compile_swing,
    "extend": _compile_extend,
    "loop_path": _compile_loop_path,
    "gesture": _compile_gesture,
    "jump": _compile_jump,
    "crouch": _compile_crouch,
    "lunge": _compile_lunge,
    "flap": _compile_flap,
    "breathe": _compile_breathe,
    "custom_pose": _compile_custom_pose,
}


def compile_motion_payload(motion: Dict[str, Any]) -> Dict[str, Any]:
    """Pure entry point: takes a parsed aurora.motion.v1 dict, returns a
    compiled payload {"id", "loop", "fps", "frame_count", "instructions"}.
    """
    if not isinstance(motion, dict) or motion.get("schema") != "aurora.motion.v1":
        raise ValueError("expected aurora.motion.v1 schema, got: %r" % motion.get("schema"))

    fps = int(motion.get("fps") or 24)
    frame_count = int(motion.get("frame_count") or 24)
    if frame_count < 1:
        frame_count = 1

    instructions: List[Dict[str, Any]] = []
    for primitive in motion.get("primitives", []):
        kind = primitive.get("kind")
        compiler = _COMPILER_DISPATCH.get(kind)
        if compiler is None:
            instructions.append({
                "bone": "root",
                "channel": "marker",
                "axis_index": 0,
                "samples": [(1, 0.0)],
                "interpolation": "LINEAR",
                "source_kind": "unknown:" + str(kind),
                "source_target": str(primitive.get("target") or ""),
            })
            continue
        instructions.extend(compiler(primitive, fps, frame_count))

    return {
        "id": motion.get("id"),
        "label": motion.get("label"),
        "loop": bool(motion.get("loop")),
        "fps": fps,
        "frame_count": frame_count,
        "instruction_count": len(instructions),
        "instructions": instructions,
    }


# ---------------------------------------------------------------------------
#  bpy LAYER (Blender-only)
# ---------------------------------------------------------------------------

def _bind_action_slot(owner, action, id_type: str = "OBJECT"):
    """Blender 5.0+ layered Action API: an Action carries FCurves inside a
    Layer->Strip->ChannelBag(slot). Legacy `action.fcurves` was removed.

    This helper:
      1) creates or reuses an OBJECT slot on `action`,
      2) binds it to the owner's animation_data.action_slot,
      3) ensures a KEYFRAME strip exists so callers can grab the ChannelBag.
    Returns the bound slot (or None on Blender 4.x where slots don't exist).
    """
    slot = None
    if hasattr(action, "slots"):
        try:
            slot = action.slots.new(id_type=id_type, name=owner.name)
        except Exception:
            slot = action.slots[0] if len(action.slots) > 0 else None
        if slot is not None and hasattr(owner.animation_data, "action_slot"):
            try:
                owner.animation_data.action_slot = slot
            except Exception:
                pass
    if hasattr(action, "layers") and len(action.layers) == 0:
        layer = action.layers.new("Layer")
        layer.strips.new(type="KEYFRAME")
    return slot


def _get_action_fcurves(action, slot=None):
    """Return the FCurve collection for `action`, transparent to the 5.x
    layered API vs 4.x legacy. Mirrors motion_intent_bpy_runner._get_action_fcurves.

    On 5.x we walk action.layers[0].strips[0].channelbag(slot, ensure=True).fcurves.
    On 4.x we fall back to action.fcurves.
    """
    if hasattr(action, "layers"):
        try:
            layer = action.layers[0] if len(action.layers) > 0 else action.layers.new("Layer")
            strip = layer.strips[0] if len(layer.strips) > 0 else layer.strips.new(type="KEYFRAME")
            if hasattr(strip, "channelbag"):
                if slot is None and hasattr(action, "slots") and len(action.slots) > 0:
                    slot = action.slots[0]
                cb = strip.channelbag(slot, ensure=True)
                if cb is not None:
                    return cb.fcurves
        except Exception:
            pass
    # Blender 4.x legacy fallback
    if hasattr(action, "fcurves"):
        return action.fcurves
    return []


def _keyframe_pose_bone(pose_bone, channel: str, axis_index: int, samples) -> int:
    applied = 0
    for frame, value in samples:
        if channel == "rotation_euler":
            pose_bone.rotation_mode = "XYZ"
            cur = list(pose_bone.rotation_euler)
            cur[axis_index] = value
            pose_bone.rotation_euler = cur
            pose_bone.keyframe_insert(data_path="rotation_euler", index=axis_index, frame=frame)
        elif channel == "location":
            cur = list(pose_bone.location)
            cur[axis_index] = value
            pose_bone.location = cur
            pose_bone.keyframe_insert(data_path="location", index=axis_index, frame=frame)
        elif channel == "scale":
            cur = list(pose_bone.scale)
            cur[axis_index] = value
            pose_bone.scale = cur
            pose_bone.keyframe_insert(data_path="scale", index=axis_index, frame=frame)
        applied += 1
    return applied


def _keyframe_object(obj, channel: str, axis_index: int, samples) -> int:
    """v77zq: keyframe a plain object (non-armature) directly. Used for
    mechanism rotate/translate/extend/swing where the moving body has no
    rig — gear, pulley, hinge leaf, actuator rod, etc."""
    applied = 0
    for frame, value in samples:
        if channel == "rotation_euler":
            obj.rotation_mode = "XYZ"
            cur = list(obj.rotation_euler)
            cur[axis_index] = value
            obj.rotation_euler = cur
            obj.keyframe_insert(data_path="rotation_euler", index=axis_index, frame=frame)
        elif channel == "location":
            cur = list(obj.location)
            cur[axis_index] = value
            obj.location = cur
            obj.keyframe_insert(data_path="location", index=axis_index, frame=frame)
        elif channel == "scale":
            cur = list(obj.scale)
            cur[axis_index] = value
            obj.scale = cur
            obj.keyframe_insert(data_path="scale", index=axis_index, frame=frame)
        applied += 1
    return applied


def _normalize_token(s: str) -> str:
    return (s or "").lower().replace(" ", "_").replace("-", "_")


# v77zs: targets that semantically refer to a *collection* of meshes — when
# matched, every object in the scene whose name contains the token receives
# the same keyframe. Singular targets ("drive_gear", "rod", "leaf") still
# resolve to the first match only so they don't accidentally drive unrelated
# meshes.
_PLURAL_OBJECT_TARGETS = {
    "wheels", "rotors", "gears", "pulleys", "belts", "legs", "arms",
    "hands", "wings", "fans", "fan_blades", "blades", "tracks",
    "knees", "shoulders", "elbows", "fingers",
}


def _is_plural_target(target_str: str) -> bool:
    """Decide whether a target name should match all matching meshes (e.g.
    'wheels' on a 4-wheeled vehicle) or just the first ('drive_gear')."""
    token = _normalize_token(target_str)
    if not token:
        return False
    if token in _PLURAL_OBJECT_TARGETS:
        return True
    # Heuristic fallback: tokens ending in 's' (and longer than 3 chars) are
    # very likely plural — covers user-introduced names like 'thrusters',
    # 'rollers', 'spokes' without hardcoding every variant.
    if len(token) > 3 and token.endswith("s") and not token.endswith("ss"):
        return True
    return False


def _resolve_object_root_targets(target_str: str, fallback_object, scene_objects) -> List[Any]:
    """v77zs: returns ALL meshes whose name contains the target token. For
    plural targets ('wheels'/'gears'/'arms'/...) the caller iterates over
    the full list so a single primitive animates every matching mesh in
    sync (4 wheels rotate together, every gear in a train rotates).

    Singular targets ('drive_gear', 'rod', 'leaf') still resolve to one
    object — the caller picks the first.

    Plural-token stem fallback: when the target is plural ('wheels') and
    nothing matched the literal token, retry with the singular stem
    ('wheel') so meshes named wheel_FL/FR/RL/RR are picked up.

    Falls back to a single-element list with the caller-provided
    fallback_object when nothing matches. Returns [] if neither resolves.
    """
    if target_str:
        token = _normalize_token(target_str)
        candidate_tokens = [token]
        # Plural-stem fallback: 'wheels' → also try 'wheel'.
        if _is_plural_target(target_str) and token.endswith("s") and len(token) > 3:
            candidate_tokens.append(token[:-1])

        for tk in candidate_tokens:
            matches: List[Any] = []
            for obj in scene_objects:
                if obj.type != "MESH":
                    continue
                if tk in _normalize_token(obj.name):
                    matches.append(obj)
            if matches:
                return matches

    if fallback_object is not None:
        return [fallback_object]
    return []


def _resolve_object_root_target(target_str: str, fallback_object, scene_objects) -> Any:
    """Backwards-compat single-object resolver — returns the first match.
    Kept so external callers that imported this directly from v77zq still
    work."""
    matches = _resolve_object_root_targets(target_str, fallback_object, scene_objects)
    return matches[0] if matches else None


def apply_compiled_motion(rig_object, compiled: Dict[str, Any], fallback_object=None) -> Dict[str, Any]:
    """Applies compiled motion to a Rigify-generated armature object.

    v77zq: when an instruction targets `__object_root__` (mechanism rotate /
    translate / extend / swing), the keyframes are now baked onto the
    matching mesh in the scene. Resolution order:
       1) a mesh whose name contains the target token (e.g. 'drive_gear' on
          an object literally named 'driveGear')
       2) the caller-provided fallback_object
       3) skip with warning

    Returns a report dict {"applied": int, "skipped": int, "warnings": [..]}.
    bpy is imported lazily so this file remains import-safe outside Blender.
    """
    import bpy  # noqa: WPS433 (lazy import is intentional)

    fps = compiled.get("fps", 24)
    frame_count = compiled.get("frame_count", 24)
    loop = compiled.get("loop", False)

    bpy.context.scene.render.fps = fps
    bpy.context.scene.frame_start = 1
    bpy.context.scene.frame_end = frame_count

    has_armature = rig_object is not None and rig_object.type == "ARMATURE"

    action_name = "aurora_" + (compiled.get("id") or "motion").replace(".", "_")

    # Action lives on the armature when present, otherwise on the fallback
    # mesh — bpy requires animation_data on whatever object owns the action.
    action_owner = rig_object if has_armature else fallback_object
    if action_owner is None:
        return {
            "applied": 0,
            "skipped": 0,
            "warnings": ["no rig and no fallback object — nothing to keyframe"],
        }
    if not action_owner.animation_data:
        action_owner.animation_data_create()
    action = bpy.data.actions.new(name=action_name)
    action_owner.animation_data.action = action
    # Blender 5.0+ layered API: bind a slot on the action so keyframes can
    # be routed via the ChannelBag. Without this the exporter still sees
    # the keys (they were inserted via keyframe_insert) but any code path
    # that walks `action.fcurves` raises AttributeError.
    owner_slot = _bind_action_slot(action_owner, action, id_type="OBJECT")

    if has_armature:
        bpy.context.view_layer.objects.active = rig_object
        bpy.ops.object.mode_set(mode="POSE")

        # v112: MUTE Rigify constraints on every DEF- bone we're about to
        # keyframe. Rigify's default output has DEF- bones driven by
        # COPY_TRANSFORMS constraints from MCH- (mechanism) bones that read
        # from the FK OR IK chain based on an IK_FK slider — but that slider
        # is a custom-property whose exposure varies across Rigify versions
        # (in 5.1 it is often unreachable via pose_bone.keys()). Muting the
        # constraints turns DEF- bones into raw pose bones so our keyframes
        # drive them unconditionally, and the mesh (which is skinned to DEF-
        # bones) follows.
        target_def_bones = set()
        for _ins in compiled.get("instructions", []):
            _bn = _ins.get("bone") or ""
            if _bn.startswith("DEF-") or _bn.startswith("DEF_"):
                target_def_bones.add(_bn)
        _muted = 0
        for _bn in target_def_bones:
            _pb = rig_object.pose.bones.get(_bn)
            if _pb is None:
                continue
            for _c in _pb.constraints:
                if not _c.mute:
                    _c.mute = True
                    _muted += 1
        if _muted:
            print("MOTION_BAKE_INFO: muted %d Rigify constraints on %d DEF- bones"
                  % (_muted, len(target_def_bones)))

    applied = 0
    skipped = 0
    warnings: List[str] = []
    scene_objects = list(bpy.context.scene.objects)
    object_actions: Dict[str, Any] = {}
    object_slots: Dict[str, Any] = {}

    for ins in compiled.get("instructions", []):
        bone_name = ins.get("bone")
        channel = ins.get("channel")
        axis_index = ins.get("axis_index", 0)
        interp = ins.get("interpolation", "BEZIER")
        target_str = ins.get("source_target") or ""
        samples = ins.get("samples", [])

        if channel == "marker":
            try:
                mk = action.pose_markers.new(name=target_str or "custom")
                mk.frame = 1
                applied += 1
            except Exception as exc:  # pragma: no cover
                warnings.append(f"marker insert failed: {exc}")
            continue

        if channel == "follow_curve":
            warnings.append(f"follow_curve not yet wired ({target_str})")
            skipped += 1
            continue

        # Bone-targeted instruction → use the armature pose bone path.
        if bone_name and bone_name != "__object_root__" and has_armature:
            pose_bone = rig_object.pose.bones.get(bone_name)
            if pose_bone is None:
                warnings.append(f"bone not found in rig: {bone_name}")
                skipped += 1
                continue
            applied += _keyframe_pose_bone(pose_bone, channel, axis_index, samples)
            fcurves = _get_action_fcurves(action, owner_slot)
            for fcu in fcurves:
                if fcu.data_path.endswith(channel) and fcu.array_index == axis_index:
                    for kp in fcu.keyframe_points:
                        kp.interpolation = interp
            continue

        # __object_root__ instruction → mesh-direct keyframing.
        # v77zs: resolves to ALL matching meshes when the target is plural
        # ('wheels' on a 4-wheeled car, 'gears' on a multi-gear train).
        plural = _is_plural_target(target_str)
        if plural:
            target_objs = _resolve_object_root_targets(target_str, fallback_object, scene_objects)
        else:
            target_objs = _resolve_object_root_targets(target_str, fallback_object, scene_objects)[:1]
        if not target_objs:
            warnings.append(f"no object resolved for target='{target_str}', skipping")
            skipped += 1
            continue

        for target_obj in target_objs:
            # Each non-armature target gets its own action since Blender's
            # animation_data is per-object.
            if target_obj is action_owner:
                target_action = action
            else:
                target_action = object_actions.get(target_obj.name)
                if target_action is None:
                    if not target_obj.animation_data:
                        target_obj.animation_data_create()
                    target_action = bpy.data.actions.new(
                        name=f"{action_name}__{target_obj.name}",
                    )
                    target_obj.animation_data.action = target_action
                    object_actions[target_obj.name] = target_action
                    object_slots[target_obj.name] = _bind_action_slot(
                        target_obj, target_action, id_type="OBJECT",
                    )

            if has_armature:
                # Need OBJECT mode to keyframe non-armature transforms.
                bpy.ops.object.mode_set(mode="OBJECT")
            applied += _keyframe_object(target_obj, channel, axis_index, samples)
            if has_armature:
                bpy.context.view_layer.objects.active = rig_object
                bpy.ops.object.mode_set(mode="POSE")

            slot_for_target = owner_slot if target_obj is action_owner else object_slots.get(target_obj.name)
            fcurves_t = _get_action_fcurves(target_action, slot_for_target)
            for fcu in fcurves_t:
                if fcu.data_path.endswith(channel) and fcu.array_index == axis_index:
                    for kp in fcu.keyframe_points:
                        kp.interpolation = interp

    # Push primary action to NLA strip if loop=true.
    if loop and action_owner.animation_data:
        try:
            track = action_owner.animation_data.nla_tracks.new()
            track.name = "aurora_motion_loop"
            strip = track.strips.new(action.name, 1, action)
            strip.repeat = 4
        except Exception as exc:  # pragma: no cover (Blender-side)
            warnings.append(f"NLA push failed: {exc}")

    if has_armature:
        bpy.ops.object.mode_set(mode="OBJECT")

    return {
        "applied": applied,
        "skipped": skipped,
        "warnings": warnings,
        "action": action_name,
        "mechanism_actions": list(object_actions.keys()),
    }


def apply_compiled_motion_to_object(target_object, compiled: Dict[str, Any]) -> Dict[str, Any]:
    """v77zq: convenience for pure-mechanism cases (no armature). Equivalent
    to calling apply_compiled_motion(None, compiled, fallback_object=target_object).
    Used by the procedural pipeline (gears, pulleys, actuators) that doesn't
    go through Rigify."""
    return apply_compiled_motion(None, compiled, fallback_object=target_object)


# ---------------------------------------------------------------------------
#  CLI: --self-test exercises only the pure layer
# ---------------------------------------------------------------------------

def _self_test() -> int:
    """Smoke test: feed sample descriptors through compile_motion_payload
    and assert structural invariants. No bpy. Used in CI."""
    failures: List[str] = []

    walk = {
        "schema": "aurora.motion.v1",
        "id": "character.walk_cycle",
        "label": "Marcher",
        "source": "preset",
        "loop": True,
        "fps": 24,
        "duration_seconds": 1.0,
        "frame_count": 24,
        "primitives": [
            {"kind": "gait", "target": "legs", "axis": "x", "amplitude": 30, "frequency_hz": 1.0,
             "duration_seconds": 1.0, "description": "leg swing"},
            {"kind": "gait", "target": "arms", "axis": "x", "amplitude": 25, "frequency_hz": 1.0,
             "duration_seconds": 1.0, "description": "arm swing"},
            {"kind": "oscillate", "target": "pelvis", "axis": "y", "amplitude": 0.04,
             "frequency_hz": 2.0, "duration_seconds": 1.0, "description": "bounce"},
        ],
    }
    out = compile_motion_payload(walk)
    if out["fps"] != 24:
        failures.append("walk fps not 24")
    if out["frame_count"] != 24:
        failures.append("walk frame_count not 24")
    if out["instruction_count"] < 6:
        failures.append("walk too few instructions: %d" % out["instruction_count"])
    if not all("samples" in i for i in out["instructions"]):
        failures.append("walk instruction missing samples")
    if not any(i["bone"].endswith(".L") for i in out["instructions"]):
        failures.append("walk no left-side bones")
    if not any(i["bone"].endswith(".R") for i in out["instructions"]):
        failures.append("walk no right-side bones")

    gear = {
        "schema": "aurora.motion.v1",
        "id": "mechanism.gear_mesh_rotate",
        "label": "Engrenage",
        "source": "preset",
        "loop": True,
        "fps": 24,
        "duration_seconds": 2.0,
        "frame_count": 48,
        "primitives": [
            {"kind": "rotate", "target": "drive_gear", "axis": "z", "amplitude": 360,
             "frequency_hz": 0.5, "duration_seconds": 2.0, "description": "driver"},
            {"kind": "rotate", "target": "driven_gear", "axis": "z", "amplitude": 360,
             "frequency_hz": 0.5, "duration_seconds": 2.0, "description": "follows"},
        ],
    }
    out = compile_motion_payload(gear)
    rotate_inst = [i for i in out["instructions"] if i["source_kind"] == "rotate"]
    if len(rotate_inst) < 2:
        failures.append("gear: too few rotate instructions")
    # Verify driven gear has opposite-sign samples
    driven = [i for i in rotate_inst if "driven" in (i["source_target"] or "")]
    if driven and driven[0]["samples"][1][1] >= 0:
        failures.append("driven gear samples should be negative")

    custom = {
        "schema": "aurora.motion.v1",
        "id": "custom.parsed",
        "label": "Marcher → Saut",
        "source": "custom",
        "loop": False,
        "fps": 24,
        "duration_seconds": 2.4,
        "frame_count": 58,
        "primitives": [
            {"kind": "gait", "target": "legs", "axis": "x", "amplitude": 30,
             "frequency_hz": 1.0, "duration_seconds": 1.0, "description": ""},
            {"kind": "jump", "target": None, "axis": "y", "amplitude": 1.2,
             "frequency_hz": None, "duration_seconds": 1.4, "description": ""},
        ],
    }
    out = compile_motion_payload(custom)
    if out["loop"]:
        failures.append("custom motion should be non-looping")
    has_jump = any(i["source_kind"] == "jump" for i in out["instructions"])
    if not has_jump:
        failures.append("custom missing jump instruction")

    # bad schema rejection
    try:
        compile_motion_payload({"schema": "wrong"})
        failures.append("did not reject wrong schema")
    except ValueError:
        pass

    # v77zq: validate mechanism instructions still carry __object_root__
    # bone tag so apply_compiled_motion can route them to mesh-direct
    # keyframing instead of skipping with a warning.
    out = compile_motion_payload(gear)
    object_root_count = sum(1 for i in out["instructions"] if i["bone"] == "__object_root__")
    if object_root_count != 2:
        failures.append("gear: expected 2 __object_root__ instructions, got %d" % object_root_count)
    # Mechanism rotate instructions must produce non-zero spin samples so
    # the mesh-direct baker has actual rotation to keyframe.
    for inst in out["instructions"]:
        if inst["source_kind"] == "rotate":
            last_value = inst["samples"][-1][1] if inst["samples"] else 0
            if abs(last_value) < 1e-6:
                failures.append(f"rotate instruction {inst['source_target']}: last sample is zero")

    # v77zq: validate that piston/extend produces a triangle wave
    # (0 → max → 0) so the mesh-direct baker animates a real stroke.
    piston = {
        "schema": "aurora.motion.v1",
        "id": "mechanism.piston_stroke",
        "label": "Verin",
        "source": "preset",
        "loop": True,
        "fps": 24,
        "duration_seconds": 2.0,
        "frame_count": 48,
        "primitives": [
            {"kind": "extend", "target": "rod", "axis": "z", "amplitude": 0.3,
             "frequency_hz": 0.5, "duration_seconds": 2.0, "description": "stroke"},
        ],
    }
    out = compile_motion_payload(piston)
    extend_inst = [i for i in out["instructions"] if i["source_kind"] == "extend"]
    if not extend_inst:
        failures.append("piston: missing extend instruction")
    else:
        samples = extend_inst[0]["samples"]
        # Triangle wave starts at 0, peaks at mid, returns to 0
        first_v = samples[0][1]
        mid_v = samples[len(samples) // 2][1]
        last_v = samples[-1][1]
        if first_v > 0.05 or last_v > 0.05:
            failures.append(f"piston: triangle wave should start/end at 0, got {first_v}/{last_v}")
        if mid_v < 0.2:
            failures.append(f"piston: mid sample should approach amplitude=0.3, got {mid_v}")

    # v77zs: validate plural-target detection + multi-mesh resolution
    # against bpy-free stub objects so we exercise the actual lookup path.
    class _StubObj:
        def __init__(self, name: str, obj_type: str = "MESH"):
            self.name = name
            self.type = obj_type

    if not _is_plural_target("wheels"):
        failures.append("'wheels' should be plural target")
    if not _is_plural_target("gears"):
        failures.append("'gears' should be plural target")
    if not _is_plural_target("legs"):
        failures.append("'legs' should be plural target")
    if _is_plural_target("drive_gear"):
        failures.append("'drive_gear' should be singular")
    if _is_plural_target("rod"):
        failures.append("'rod' should be singular")
    if _is_plural_target(""):
        failures.append("empty target should be singular (no match)")

    # 4-wheel vehicle scene
    scene = [
        _StubObj("car_body"),
        _StubObj("wheel_FL"),
        _StubObj("wheel_FR"),
        _StubObj("wheel_RL"),
        _StubObj("wheel_RR"),
    ]
    # v77zs: plural 'wheels' should auto-fallback to singular stem 'wheel'
    # so meshes named wheel_FL/FR/RL/RR all get matched on a single primitive.
    matches_plural = _resolve_object_root_targets("wheels", None, scene)
    if len(matches_plural) != 4:
        failures.append(f"plural 'wheels' should auto-stem to 'wheel' and match 4, got {len(matches_plural)}")
    matches_singular = _resolve_object_root_targets("wheel", None, scene)
    if len(matches_singular) != 4:
        failures.append(f"'wheel' should match 4 wheels, got {len(matches_singular)}")

    # Multi-gear train
    gear_scene = [
        _StubObj("housing"),
        _StubObj("gear_1"),
        _StubObj("gear_2"),
        _StubObj("gear_3"),
    ]
    gears = _resolve_object_root_targets("gear", None, gear_scene)
    if len(gears) != 3:
        failures.append(f"'gear' should match 3 gears, got {len(gears)}")

    # Singular targeting: 'drive_gear' should match one specific mesh
    specific_scene = [
        _StubObj("drive_gear"),
        _StubObj("driven_gear"),
        _StubObj("intermediate_gear"),
    ]
    drive = _resolve_object_root_targets("drive_gear", None, specific_scene)
    if len(drive) != 1 or drive[0].name != "drive_gear":
        failures.append(f"'drive_gear' singular should match exactly drive_gear, got {[o.name for o in drive]}")

    # Fallback when nothing matches and fallback_object provided
    fallback = _StubObj("default_mesh")
    fb = _resolve_object_root_targets("nonexistent_token", fallback, scene)
    if len(fb) != 1 or fb[0] is not fallback:
        failures.append("missing-target should fall back to fallback_object")

    # Empty when nothing matches and no fallback
    empty = _resolve_object_root_targets("nonexistent_token", None, scene)
    if empty:
        failures.append("missing-target with no fallback should return []")

    # Non-mesh objects skipped
    mixed_scene = [
        _StubObj("camera_main", obj_type="CAMERA"),
        _StubObj("light_key", obj_type="LIGHT"),
        _StubObj("gear_1"),
    ]
    only_meshes = _resolve_object_root_targets("gear", None, mixed_scene)
    if len(only_meshes) != 1 or only_meshes[0].name != "gear_1":
        failures.append(f"non-mesh objects should be skipped, got {[o.name for o in only_meshes]}")

    if failures:
        print("SELF_TEST_FAIL:", failures, file=sys.stderr)
        return 1
    print("SELF_TEST_OK: %d test cases passed" % 13)
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--motion", help="path to aurora.motion.v1 JSON file")
    ap.add_argument("--self-test", action="store_true", help="run pure-layer smoke test")
    ap.add_argument("--dry-compile", action="store_true",
                    help="compile and print instructions to stdout without bpy")
    args = ap.parse_args()

    if args.self_test:
        return _self_test()

    if args.motion and args.dry_compile:
        with open(args.motion, "r", encoding="utf-8") as fp:
            motion = json.load(fp)
        compiled = compile_motion_payload(motion)
        print(json.dumps(compiled, default=lambda o: list(o) if isinstance(o, tuple) else o,
                         indent=2))
        return 0

    print("usage: motion_baker.py [--self-test | --motion <path> --dry-compile]",
          file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
