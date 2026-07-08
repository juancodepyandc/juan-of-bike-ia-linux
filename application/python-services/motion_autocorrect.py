"""motion_autocorrect — closes the animation self-correction loop.

WHAT WAS MISSING (verified against the real code)
    anim_metrics.py is a complete objective JUDGE (evaluate() -> ranked `knobs`) and it can
    sample a `take` from Blender (sample_take_from_blender), but NOTHING in the runtime calls
    it: after a successful bake (bridge_server.py ~:12768 / motion_intent_bpy_runner export
    ~:1367) the GLB is returned WITHOUT ever measuring the deformed animation. The loop is open.

    Also the sampler stores joints under *literal bone names*, while the metrics want *logical
    keys* ("heel.L", "toe.L", "head", "pelvis", "thigh.R"...). Rigify names differ. This module
    owns that Rigify->take mapping and wires: sample -> map -> family -> evaluate -> knobs, and
    the loop that turns the top knob into a motion_baker param change and re-bakes.

USAGE (inside Blender, after a bake, before glTF export)
    import motion_autocorrect as mac
    report = mac.evaluate_current_scene(f0, f1, intent=intent, morphology_profile=prof)
    # report["passed"], report["knobs"] (ranked), report["results"]
    # then: mac.apply_top_knob(motion_params, report["knobs"]) -> re-bake -> re-evaluate

Pure-python except evaluate_current_scene (needs bpy via anim_metrics.sample_take_from_blender).
Self-test needs no Blender: python motion_autocorrect.py --self-test
"""
from __future__ import annotations

import argparse
import sys
from typing import Optional

import anim_metrics


# --- Rigify control-bone name  ->  metric `take` logical joint key -------------
# Rigify (armature_human_metarig_add -> rigify_generate) exposes these control bones.
# The metrics contract (anim_metrics.py:29-57) wants the logical keys on the right.
RIGIFY_JOINT_MAP = {
    "head": "head", "neck": "neck", "spine_fk.003": "chest", "spine": "pelvis",
    "torso": "pelvis_ctrl",
    "thigh_fk.L": "thigh.L", "thigh_fk.R": "thigh.R",
    "shin_fk.L": "shin.L", "shin_fk.R": "shin.R",
    "foot_fk.L": "ankle.L", "foot_fk.R": "ankle.R",
    "toe_fk.L": "toe.L", "toe_fk.R": "toe.R",
    "heel.02.L": "heel.L", "heel.02.R": "heel.R",
    "upper_arm_fk.L": "arm.L", "upper_arm_fk.R": "arm.R",
    "forearm_fk.L": "forearm.L", "forearm_fk.R": "forearm.R",
    "shoulder.L": "shoulder.L", "shoulder.R": "shoulder.R",
}
# fallbacks tried when the *_fk control isn't present (deform rig / plain metarig)
RIGIFY_FALLBACKS = {
    "thigh.L": ("DEF-thigh.L", "thigh.L"), "thigh.R": ("DEF-thigh.R", "thigh.R"),
    "shin.L": ("DEF-shin.L", "shin.L"), "shin.R": ("DEF-shin.R", "shin.R"),
    "ankle.L": ("DEF-foot.L", "foot.L"), "ankle.R": ("DEF-foot.R", "foot.R"),
    "toe.L": ("DEF-toe.L", "toe.L"), "toe.R": ("DEF-toe.R", "toe.R"),
    "arm.L": ("DEF-upper_arm.L", "upper_arm.L"), "arm.R": ("DEF-upper_arm.R", "upper_arm.R"),
    "pelvis": ("spine", "DEF-spine", "hips"),
    "head": ("head", "DEF-head"), "neck": ("neck", "DEF-neck"),
    "heel.L": ("heel.02.L", "foot.L"), "heel.R": ("heel.02.R", "foot.R"),
}

# which logical joints each family actually needs (so we only sample what matters)
FAMILY_JOINT_KEYS = {
    "humanoid": ["head", "neck", "pelvis", "heel.L", "heel.R", "toe.L", "toe.R",
                 "ankle.L", "ankle.R", "thigh.L", "thigh.R", "arm.L", "arm.R"],
    "creature": ["head", "pelvis"],
    "mecha_rigid": [],
    "screen": [],
    "luminous": [],
}


def family_for(intent: Optional[dict] = None, morphology_profile: Optional[dict] = None) -> str:
    """Metric family. Geometry (morphology) wins over the prompt-only intent (fixes the
    Goldorak 'humanoid'->soft-skin melt). Falls back to anim_metrics.family_for_intent."""
    if morphology_profile:
        fam = morphology_profile.get("metric_family")
        if fam in anim_metrics.FAMILY_METRICS:
            return fam
    return anim_metrics.family_for_intent(intent or {})


def _resolve_bone(arm, logical_key: str) -> Optional[str]:
    """Find the actual bone name in `arm` for a logical joint key, trying fallbacks."""
    # reverse map: logical -> rigify control candidates
    candidates = [k for k, v in RIGIFY_JOINT_MAP.items() if v == logical_key]
    candidates += list(RIGIFY_FALLBACKS.get(logical_key, ()))
    candidates.append(logical_key)
    for c in candidates:
        if c in arm.pose.bones:
            return c
    return None


def evaluate_current_scene(frame_start: int, frame_end: int, *,
                           family: Optional[str] = None,
                           intent: Optional[dict] = None,
                           morphology_profile: Optional[dict] = None,
                           emission_material: Optional[str] = None,
                           thresholds: Optional[dict] = None) -> dict:  # pragma: no cover
    """THE bridge: sample the deformed animation from the live Blender scene, map Rigify bones
    to the metric contract, run the right metric family, return the ranked report. bpy-only."""
    import bpy
    fam = family or family_for(intent, morphology_profile)
    add_screen = bool((morphology_profile or {}).get("sub_flags", {}).get("face_is_screen"))

    arms = [o for o in bpy.context.scene.objects if o.type == "ARMATURE"]
    # resolve the logical joints this family needs to actual bone names present in the rig
    want = FAMILY_JOINT_KEYS.get(fam, [])
    bone_to_logical: dict = {}
    for arm in arms:
        for key in want:
            bn = _resolve_bone(arm, key)
            if bn and bn not in bone_to_logical:
                bone_to_logical[bn] = key

    take = anim_metrics.sample_take_from_blender(
        frame_start, frame_end,
        joint_names=list(bone_to_logical.keys()) or None,
        emission_node=emission_material,
    )
    # rename sampled joints from bone names to the logical keys the metrics expect
    if take.get("joints"):
        take["joints"] = {bone_to_logical.get(n, n): v for n, v in take["joints"].items()}

    report = anim_metrics.evaluate(take, fam, add_screen=add_screen, thresholds=thresholds)
    report["family_source"] = "morphology" if (morphology_profile and report["family"] ==
                                               (morphology_profile or {}).get("metric_family")) else "intent"
    return report


# --- knob -> motion_baker parameter application (closes the loop) --------------
# Each anim_metrics knob names a real param (anim_metrics.KNOBS). We translate the top
# failing knob into a change on the aurora.motion.v1 payload that motion_baker consumes,
# then the caller re-bakes. Conservative step sizes; monotone; capped.
KNOB_TO_MOTION = {
    "arm_swing_amplitude": ("amplitudeMul", 1.35, "arms"),
    "ankle_pitch_amplitude": ("ankle_pitch", 1.4, "legs"),
    "head_stabilization_gain": ("head_damping", 1.5, "head"),
    "weight_smooth_iterations": ("weight_smooth_iterations", 1.6, "skin"),
    "finger_curl_gradation": ("finger_curl", 1.0, "hands"),
    "finger_abduction_clamp": ("finger_abduction_clamp", 0.6, "hands"),
    "foot_ik_lock": ("foot_ik_lock", True, "legs"),
    "max_bone_influences": ("max_bone_influences", 1, "skin"),
    "pattern_amplitude": ("emission_amplitude", 1.4, "led"),
    "emission_smoothing_frames": ("emission_smoothing_frames", 1.5, "led"),
    "min_dwell_frames": ("min_dwell_frames", 1.5, "led"),
    "pulse_period_lock": ("pulse_period_lock", True, "led"),
    "screen_uv_clamp": ("screen_rigid_bind", True, "screen"),
    "joint_gap": ("joint_gap", 1.3, "mecha"),
    "mechanical_stop_limit": ("mechanical_stop_limit", 1.0, "mecha"),
}


def apply_top_knob(motion_params: dict, knobs: list) -> Optional[dict]:
    """Turn the highest-severity knob into a change on the motion params dict (mutated + returned).
    Returns the applied {param, from, to} or None if no actionable knob. The caller re-bakes."""
    for k in knobs or []:
        param = k.get("param")
        rule = KNOB_TO_MOTION.get(param)
        if not rule:
            continue
        key, op, _grp = rule
        old = motion_params.get(key)
        if isinstance(op, bool):
            new = op
        elif old is None:
            new = op if isinstance(op, (int, float)) else 1.0
        elif isinstance(op, float):
            new = round(min(old * op, old * 4.0), 4) if old else op
        else:
            new = old + op
        motion_params[key] = new
        return {"param": param, "key": key, "from": old, "to": new, "metric": k.get("metric")}
    return None


def autocorrect(bake_fn, frame_start: int, frame_end: int, *,
                intent: Optional[dict] = None, morphology_profile: Optional[dict] = None,
                max_rounds: int = 4) -> dict:  # pragma: no cover
    """Closed loop: bake(params) -> evaluate_current_scene -> if failed, turn top knob -> re-bake.
    `bake_fn(params)` applies the motion to the live scene (e.g. motion_baker.apply_compiled_motion
    of a payload derived from params). Keeps the best-scoring round (anti-regression). bpy-only."""
    params: dict = dict((intent or {}).get("motion_params", {}))
    history = []
    best = None
    for rnd in range(max_rounds):
        bake_fn(params)
        rep = evaluate_current_scene(frame_start, frame_end, intent=intent,
                                     morphology_profile=morphology_profile)
        score = rep["n_graded"] - rep["n_failed"]
        history.append({"round": rnd, "passed": rep["passed"], "failed": rep["failed_metrics"],
                        "params": dict(params)})
        if best is None or score > best["score"]:
            best = {"score": score, "round": rnd, "params": dict(params), "report": rep}
        if rep["passed"]:
            break
        applied = apply_top_knob(params, rep["knobs"])
        history[-1]["applied"] = applied
        if applied is None:
            break                                  # no actionable knob -> stop honestly
    return {"best": best, "rounds": history}


# ------------------------------------------------------------- self-test ------

def _self_test() -> int:
    # family routing: geometry (morphology) overrides the prompt.
    goldorak_intent = {"category": "creature_organic", "creature_anim": {"locomotion": "humanoid"}}
    prof = {"metric_family": "mecha_rigid", "sub_flags": {}}
    assert family_for(goldorak_intent, prof) == "mecha_rigid", "Goldorak must not be humanoid"
    assert family_for(goldorak_intent, None) == "humanoid", "no morphology -> prompt path"
    assert family_for({"category": "led_emission"}, None) == "luminous"
    # knob application turns a real param and is monotone + capped
    knobs = [{"metric": "contralateral_arm_swing", "severity": 2.0, "param": "arm_swing_amplitude"}]
    p = {"amplitudeMul": 1.0}
    a = apply_top_knob(p, knobs)
    assert a and p["amplitudeMul"] > 1.0 and a["key"] == "amplitudeMul"
    # a bool knob (foot lock) sets the flag
    p2 = {}
    apply_top_knob(p2, [{"metric": "foot_ground", "param": "foot_ik_lock"}])
    assert p2.get("foot_ik_lock") is True
    # unknown knob -> no crash, no change
    assert apply_top_knob({}, [{"param": "nonexistent"}]) is None
    print("motion_autocorrect self-test OK — family routing + knob application wired.")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--self-test", action="store_true")
    a = ap.parse_args()
    if a.self_test:
        return _self_test()
    ap.error("nothing to do (use --self-test; evaluate_current_scene runs inside Blender)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
