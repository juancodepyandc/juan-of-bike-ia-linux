"""mocap_bake_bpy — Blender-side BVH retarget + gait polish.

Runs INSIDE a Blender instance. The caller (rigify_autorig.py's embedded
script, or a standalone Blender invocation) is expected to:
  1. Have already imported a rigged mesh + generated its Rigify rig
  2. Provide the Rigify armature object, the mesh objects, and the ground z
  3. Pass the ``.bvh`` filepath produced by MoMask

We then:
  * Register the external ``retarget_bvh`` addon (a.k.a. MakeWalk, Thomas
    Larsson, https://bitbucket.org/Diffeomorphic/retarget_bvh) — it lives at
    ``$AURORA_RETARGET_BVH_PATH`` or ``~/.local/share/auroraia/external/retarget_bvh``.
  * Force ``BvhData.prefs`` to a SimpleNamespace so ``BS()`` returns sane
    defaults in headless mode (registration outside Blender's addon prefs
    system leaves ``prefs=None`` and every ``BS().foo`` access explodes).
  * Set ``mcpRna(scn).SourceRig = 'Automatic'`` and ``TargetRig = 'Automatic'``
    so the auto-detector handles both the SMPL-style source (MoMask/HumanML3D)
    and the Rigify target — no known-rigs JSON edit needed.
  * Invoke ``bpy.ops.mcp.load_and_retarget(filepath=BVH, useNLA=False)``.
  * Apply the gait polish: neck limit rotation, foot ground clamp, finger curl,
    optional arm-swing amplification.

Public entrypoint: ``run_mocap_bake(rig, bvh_path, orig_mesh_names, ground_z,
mesh_fallback, arm_swing_boost)``.
"""
from __future__ import annotations

import math
import os
import sys
import types

# bpy is only importable inside a running Blender. Import lazily so the file
# still passes `python -m py_compile`.
if "bpy" in sys.modules or os.environ.get("AURORA_INSIDE_BLENDER"):
    import bpy  # type: ignore
    import mathutils  # type: ignore
else:  # pragma: no cover - typechecking convenience
    bpy = None  # type: ignore
    mathutils = None  # type: ignore


DEFAULT_RETARGET_HOME = os.path.expanduser("~/.local/share/auroraia/external")


def _register_retarget_bvh() -> str:
    """Make sure the retarget_bvh addon is registered.

    Returns the path to the addon root. Raises RuntimeError on failure.
    """
    ext_root = os.environ.get("AURORA_RETARGET_BVH_EXT_ROOT") or DEFAULT_RETARGET_HOME
    if ext_root not in sys.path:
        sys.path.insert(0, ext_root)
    # Import the addon package as a regular module tree
    import importlib
    try:
        pkg = importlib.import_module("retarget_bvh")
    except Exception as exc:  # pragma: no cover - env misconfig
        raise RuntimeError(
            f"retarget_bvh addon not importable from {ext_root}: {exc}"
        ) from exc

    # register submodules — the addon expects manual registration when we skip
    # bpy.ops.preferences.addon_enable (blender_manifest.toml is 5.1+ only).
    try:
        pkg.register()
    except Exception as exc:
        # tolerate "already registered"
        if "already" not in str(exc).lower():
            raise RuntimeError(f"retarget_bvh register() failed: {exc}") from exc

    # Force BS() to a sane default. When registration goes through the addon
    # preferences UI, prefs is filled by Blender; in manual/headless mode it
    # stays None and any BS().foo access throws.
    from retarget_bvh.bsettings import BD  # type: ignore

    if BD.prefs is None:
        BD.prefs = types.SimpleNamespace(
            verbose=False,
            useLimits=False,
            useUnlock=False,
            ignoreLeafBones=False,
            useBlenderBvh=True,
            useNativeFbx=False,
        )
    return os.path.join(ext_root, "retarget_bvh")


def _select_rig(rig):
    """Deselect all + select rig + make active, tolerating any starting mode.

    retarget_bvh leaves us in POSE mode with a non-rig active object in some
    cases; ``bpy.ops.object.select_all`` then throws ``context is incorrect``.
    We bypass ops and drive selection through direct attribute writes.
    """
    # First force OBJECT mode via a temp_override tied to the rig itself so
    # mode_set doesn't require an already-good context.
    try:
        with bpy.context.temp_override(
            active_object=rig, object=rig, selected_objects=[rig]
        ):
            if bpy.context.mode != "OBJECT":
                bpy.ops.object.mode_set(mode="OBJECT")
    except Exception:
        pass
    # Now scan every selectable object in the view layer and clear selection.
    for o in list(bpy.context.view_layer.objects):
        try:
            if o.select_get():
                o.select_set(False)
        except Exception:
            pass
    rig.select_set(True)
    bpy.context.view_layer.objects.active = rig


def _to_object_mode(rig=None):
    """Force OBJECT mode; works even when the current context is broken."""
    if bpy.context.mode == "OBJECT":
        return
    if rig is not None:
        try:
            with bpy.context.temp_override(
                active_object=rig, object=rig, selected_objects=[rig]
            ):
                bpy.ops.object.mode_set(mode="OBJECT")
                return
        except Exception:
            pass
    try:
        bpy.ops.object.mode_set(mode="OBJECT")
    except Exception:
        pass


def _to_pose_mode(rig):
    _select_rig(rig)
    if bpy.context.mode != "POSE":
        try:
            with bpy.context.temp_override(
                active_object=rig, object=rig, selected_objects=[rig]
            ):
                bpy.ops.object.mode_set(mode="POSE")
        except Exception:
            bpy.ops.object.mode_set(mode="POSE")


def amplify_bvh_arm_swing(src: str, dst: str, factor: float = 1.6) -> dict:
    """Amplify arm swing DIRECTLY at the BVH source (before retarget).

    Why this matters: retarget_bvh transfers Euler rotations from BVH joints
    to Rigify pose bones; Rigify FK controls then feed the DEF-arm bones that
    deform the mesh. On the way, Rigify's IK auto-solver + FK->DEF chain
    dampens the signal, and MoMask/HumanML3D-trained MoMask itself often
    outputs walks with 5-6 cm wrist swing (below what reads as "swinging").
    Amplifying at the pose fcurve level is fragile (rotation_mode differs
    between rigs, quaternion component scaling is not a valid rotation
    amplification). Amplifying at the BVH source is unambiguous: every
    rotation is an explicit Euler angle in the joint's local frame; scaling
    each rotation channel away from its median value stretches the pose
    without changing its axes.

    ``factor > 1.0`` broadens the swing; ``factor = 1.0`` is a no-op.

    Returns a report dict with the delta amp per joint.
    """
    if factor <= 1.001:
        # no-op: copy the file so the caller can pass ``dst`` uniformly
        with open(src, "r", encoding="utf-8", errors="replace") as _in:
            data = _in.read()
        with open(dst, "w", encoding="utf-8") as _out:
            _out.write(data)
        return {"factor": factor, "amplified_joints": [], "noop": True}

    import numpy as _np

    # target joints — HumanML3D/MoMask BVH names. LeftShoulder is the
    # collar bone (small motion). LeftArm is the upper arm bone (the main
    # swing carrier — 90% of visible arm motion comes from here).
    targets = {
        "LeftArm": 1.0,
        "RightArm": 1.0,
        "LeftShoulder": 0.6,   # dampen collar since Shoulder+Arm compound
        "RightShoulder": 0.6,
        "LeftForeArm": 0.7,    # elbow follows shoulder swing partially
        "RightForeArm": 0.7,
    }

    lines = open(src, "r", encoding="utf-8", errors="replace").read().splitlines()

    # Parse hierarchy: build joint_name -> (start_col, n_channels).
    # BVH order: root has 6 channels, each JOINT has 3 (or 6). We scan and
    # accumulate channel counts in the order joints appear in the header.
    joint_stack = []
    joint_start = {}   # name -> starting column in the motion frame
    joint_nch = {}     # name -> number of channels
    joint_chan_order = {}  # name -> list of channel names (in order)
    col = 0
    header_end_idx = None
    for i, ln in enumerate(lines):
        s = ln.strip()
        if s == "MOTION":
            header_end_idx = i
            break
        if s.startswith("ROOT ") or s.startswith("JOINT "):
            name = s.split(None, 1)[1].strip()
            joint_stack.append(name)
        elif s.startswith("CHANNELS "):
            parts = s.split()
            nch = int(parts[1])
            chans = parts[2:2 + nch]
            name = joint_stack[-1] if joint_stack else "ROOT"
            joint_start[name] = col
            joint_nch[name] = nch
            joint_chan_order[name] = chans
            col += nch
        elif s == "}":
            if joint_stack:
                joint_stack.pop()

    if header_end_idx is None:
        raise RuntimeError("BVH: no MOTION section found")

    # Read motion rows into a numpy matrix
    motion_lines = []
    header_lines = lines[:header_end_idx + 1]
    for ln in lines[header_end_idx + 1:]:
        if ln.strip().startswith("Frames:") or ln.strip().startswith("Frame Time:") or ln.strip() == "":
            header_lines.append(ln)
            continue
        motion_lines.append(ln)
    if not motion_lines:
        raise RuntimeError("BVH: empty MOTION block")

    # Build matrix, tolerate ragged rows by truncating to shortest length
    rows = []
    ncols_all = col
    for ln in motion_lines:
        toks = ln.split()
        if len(toks) < ncols_all:
            # bad line — skip; we'll pad-drop the trailing rows later
            continue
        rows.append([float(t) for t in toks[:ncols_all]])
    if not rows:
        raise RuntimeError("BVH: no parseable motion rows")
    M = _np.array(rows, dtype=_np.float64)  # (T, ncols_all)

    report_amp = []
    for jname, mult in targets.items():
        if jname not in joint_start:
            continue
        start = joint_start[jname]
        nch = joint_nch[jname]
        chans = joint_chan_order[jname]
        # only amplify rotation channels (not position)
        for ci, chan in enumerate(chans):
            if "rotation" not in chan.lower() and not chan.lower().endswith("rot"):
                continue
            column = start + ci
            values = M[:, column]
            # centre around median (robust) then scale
            med = float(_np.median(values))
            local_factor = 1.0 + (factor - 1.0) * mult
            new_vals = med + (values - med) * local_factor
            # clip to sane rotation range (BVH is degrees, walks stay within
            # +/- 60 deg per axis; clamping avoids the amplified pose from
            # gimbal-flipping the arm through the torso).
            new_vals = _np.clip(new_vals, med - 55.0, med + 55.0)
            M[:, column] = new_vals
        report_amp.append((jname, local_factor))

    # Write back
    out_lines = list(header_lines)
    for r in M:
        out_lines.append("\t".join("%.6f" % v for v in r))
    with open(dst, "w", encoding="utf-8") as _out:
        _out.write("\n".join(out_lines))
    return {
        "factor": factor,
        "amplified_joints": report_amp,
        "T": int(M.shape[0]),
        "cols": int(M.shape[1]),
    }


def sanitize_bvh_root(src: str, dst: str, lock_yaw: bool = True) -> None:
    """Zero out ROOT translation channels (and optionally yaw drift).

    Retarget_bvh maps the source Hips translation onto Rigify's ``torso``
    control, and the accumulated 4-5 m of world walk drags the upper-body
    controls with it — spine/head/arms end up stretched by the same offset
    while the pose (rotations) walks correctly. Zeroing the translation
    turns the clip into a WALK-IN-PLACE cycle: the arms still swing, the
    legs still stride, the pelvis still bobs, but there's no global drift.
    That's the industry-standard shape for a rig walk cycle and it renders
    identically under a camera framed on the character.

    ``lock_yaw`` additionally DETRENDS the ROOT Y-rotation channel (yaw): we
    subtract the linear trend so the character's average heading stays
    constant across the clip. The MoMask training set contains gentle
    heading changes; without detrending the previewed character slowly
    turns from side view into back view over 8 seconds, which reads as
    "rotating in place" instead of "walking forward". Local pelvis yaw
    wobble (the natural 5° oscillation each stride) is preserved.

    Confirmed 2026-07-13: with translation kept, frame 100 of ``repeat2``
    exploded the shirt/head; with translation zeroed, the same clip renders
    cleanly with a visible arm swing (see /tmp/auroraia/mocap_test/frames_v7_zerot).
    """
    lines = open(src, "r", encoding="utf-8", errors="replace").read().splitlines()
    # First, extract the sequence of root Y-rotations so we can compute the
    # linear trend to subtract. BVH root channel order is per the header —
    # standard SMPL export uses ``Xpos Ypos Zpos Zrot Yrot Xrot``.
    motion = False
    root_yrots: list[float] = []
    frame_indices: list[int] = []
    for i, ln in enumerate(lines):
        if ln.strip() == "MOTION":
            motion = True
            continue
        if not motion:
            continue
        s = ln.strip()
        if s.startswith("Frames:") or s.startswith("Frame Time:") or s == "":
            continue
        toks = ln.split()
        if len(toks) >= 6:
            try:
                root_yrots.append(float(toks[4]))
                frame_indices.append(i)
            except ValueError:
                pass

    yaw_slope = 0.0
    yaw_intercept = 0.0
    if lock_yaw and len(root_yrots) > 8:
        import numpy as _np

        y = _np.array(root_yrots, dtype=_np.float64)
        # Unwrap so a jump from +179 -> -179 doesn't fake a huge trend.
        y = _np.unwrap(y * _np.pi / 180.0) * 180.0 / _np.pi
        x = _np.arange(len(y))
        # linear fit y = slope*x + intercept
        A = _np.vstack([x, _np.ones_like(x)]).T
        yaw_slope, yaw_intercept = _np.linalg.lstsq(A, y, rcond=None)[0]

    # Now rewrite the file
    out = []
    motion = False
    kframe = 0
    for ln in lines:
        if not motion:
            out.append(ln)
            if ln.strip() == "MOTION":
                motion = True
            continue
        s = ln.strip()
        if s.startswith("Frames:") or s.startswith("Frame Time:") or s == "":
            out.append(ln)
            continue
        toks = ln.split()
        if len(toks) >= 6:
            toks[0] = "0.0"
            toks[1] = "0.0"
            toks[2] = "0.0"
            if lock_yaw and root_yrots:
                # subtract the linear trend from root Y-rotation
                try:
                    raw = float(toks[4])
                    corrected = raw - (yaw_slope * kframe)  # trend only
                    toks[4] = "%.6f" % corrected
                except ValueError:
                    pass
            kframe += 1
        out.append("\t".join(toks))
    with open(dst, "w", encoding="utf-8") as f:
        f.write("\n".join(out))


def _load_and_retarget(rig, bvh_path: str, use_nla: bool = False,
                       target_rig: str = "") -> None:
    """Wrap mcp.load_and_retarget with the required scene/context setup."""
    from retarget_bvh.bsettings import mcpRna  # type: ignore

    scn = bpy.context.scene
    mcpRna(scn).SourceRig = "Automatic"
    mcpRna(scn).TargetRig = "Automatic"
    mcpRna(scn).SourceTPose = "Default"
    mcpRna(scn).TargetTPose = "Default"

    _to_object_mode()
    _select_rig(rig)

    kwargs = {"filepath": bvh_path, "useNLA": use_nla}
    if target_rig:
        # Squelette cible CONNU de l'addon (known_rigs/*.json): la devinette
        # automatique se perd sur les rigs Mixamo sans doigts (MIA) — «Top of
        # spine LeftToeBase has 0 children» — alors que la table Mixamo mappe
        # exactement ces os. useAutoTarget=False sinon la devinette re-ecrase
        # le choix.
        try:
            from retarget_bvh.bsettings import BD as _BD  # type: ignore
            _BD.ensureTargetInited(scn)
            mcpRna(scn).TargetRig = target_rig
            kwargs["useAutoTarget"] = False
            print("MOCAP_INFO: cible forcee '%s' (auto-detect coupe)" % target_rig)
        except Exception as _te:  # noqa: BLE001
            print("MOCAP_INFO: cible forcee '%s' indisponible (%r) -> auto"
                  % (target_rig, _te))
            mcpRna(scn).TargetRig = "Automatic"

    try:
        # retarget_bvh raises MocapMessage("...retargeted") as a soft signal on
        # success in older builds; wrap so the caller doesn't crash on it.
        bpy.ops.mcp.load_and_retarget(**kwargs)
    except RuntimeError as exc:
        # Diffeomorphic uses raise MocapMessage on success in some versions —
        # the message contains "retargeted" or "BVH file(s) retargeted".
        msg = str(exc).lower()
        if "retargeted" in msg or "mocap" in msg:
            pass
        else:
            raise
    # Piege verifie: sur echec d'auto-detection l'addon imprime «*** BVH
    # Retargeter Error ***» et TERMINE sans lever — l'echec passait pour un
    # succes et on cuisait 1 frame de pose de repos (statue livree). Le
    # retarget doit avoir depose une action couvrant plusieurs frames.
    act = rig.animation_data.action if rig.animation_data else None
    xs = [kp.co.x for fc in (act.fcurves if act else []) for kp in fc.keyframe_points]
    span = (max(xs) - min(xs)) if xs else 0.0
    if span < 2.0:
        raise RuntimeError(
            "retarget sans effet (action=%s, portee=%.1f frame(s)) — echec "
            "silencieux de l'addon" % (act.name if act else "aucune", span))


def _amplify_arm_swing(rig, factor: float = 1.4) -> int:
    """Multiply the DEF-upper_arm.L/R rotation deltas by ``factor``.

    Retargeted BVHs from MoMask sometimes come out with a subtle arm swing
    because the source SMPL rest arms hang slightly forward. We scan the
    fcurves and scale keyframe values away from their frame-1 baseline.
    """
    if factor <= 1.001:
        return 0
    if not rig.animation_data or not rig.animation_data.action:
        return 0
    act = rig.animation_data.action
    fcurves = _iter_action_fcurves(act)
    targets = {"upper_arm_fk.L", "upper_arm_fk.R", "upper_arm.L", "upper_arm.R"}
    modified = 0
    for fc in fcurves:
        dp = fc.data_path
        if "rotation" not in dp:
            continue
        # find the bone name inside pose.bones["..."].rotation_...
        bone = None
        try:
            l = dp.index('"')
            r = dp.index('"', l + 1)
            bone = dp[l + 1 : r]
        except ValueError:
            continue
        if bone not in targets:
            continue
        if len(fc.keyframe_points) < 2:
            continue
        baseline = fc.keyframe_points[0].co.y
        for kp in fc.keyframe_points:
            kp.co.y = baseline + (kp.co.y - baseline) * factor
            kp.handle_left.y = baseline + (kp.handle_left.y - baseline) * factor
            kp.handle_right.y = baseline + (kp.handle_right.y - baseline) * factor
        fc.update()
        modified += 1
    return modified


def _iter_action_fcurves(action):
    """Blender 4.4 & 5.x action layered-slots compatibility."""
    # Legacy (< 4.4): action.fcurves works.
    fcs = getattr(action, "fcurves", None)
    if fcs and len(fcs):
        return list(fcs)
    # Layered (5.x): traverse channelbags
    out = []
    for layer in getattr(action, "layers", []) or []:
        for strip in getattr(layer, "strips", []) or []:
            for cb in getattr(strip, "channelbags", []) or []:
                for fc in getattr(cb, "fcurves", []) or []:
                    out.append(fc)
    return out


def _apply_neck_limit(rig) -> bool:
    _to_pose_mode(rig)
    neck = (
        rig.pose.bones.get("neck")
        or rig.pose.bones.get("neck_fk")
        or rig.pose.bones.get("neck.001")
    )
    if neck is None:
        return False
    if any(c.type == "LIMIT_ROTATION" for c in neck.constraints):
        return True
    lr = neck.constraints.new(type="LIMIT_ROTATION")
    lr.owner_space = "LOCAL"
    lr.use_limit_x = True
    lr.min_x = math.radians(-14.0)
    lr.max_x = math.radians(22.0)
    lr.use_limit_z = True
    lr.min_z = math.radians(-20.0)
    lr.max_z = math.radians(20.0)
    return True


def _apply_foot_ground_clamp(rig) -> int:
    """Prevent foot_ik from dipping below the mesh ground by pinning min z.

    Real ground is the ``ground_z`` argv (world Z of the mesh minimum), but
    the foot_ik target is in the rig LOCAL frame. Setting min_y = 0 in LOCAL
    keeps the foot from sliding backwards under the rest pose. For genuine
    floor-lock we lean on the ROOT VERTICAL BOUNCE below plus foot_ik
    LIMIT_LOCATION.
    """
    _to_pose_mode(rig)
    added = 0
    for side in ("L", "R"):
        foot = rig.pose.bones.get(f"foot_ik.{side}") or rig.pose.bones.get(f"foot.{side}")
        if foot is None:
            continue
        if any(c.type == "LIMIT_LOCATION" for c in foot.constraints):
            continue
        ll = foot.constraints.new(type="LIMIT_LOCATION")
        ll.owner_space = "LOCAL"
        ll.use_min_y = True
        ll.min_y = 0.0
        added += 1
    return added


def _bake_finger_curl(rig) -> int:
    """Curl fingers so open-hand MoMask output doesn't read as starfish.

    We keyframe DEF- finger bones at frame 1 with a mild curl. When the
    retarget action doesn't touch these bones (it doesn't), the value holds
    for the whole clip.
    """
    _to_pose_mode(rig)
    stems = ("def-f_index", "def-f_middle", "def-f_ring", "def-f_pinky", "def-thumb")
    curl_by_seg = {"01": 0.22, "02": 0.55, "03": 0.60}
    thumb_by_seg = {"01": 0.08, "02": 0.30, "03": 0.35}
    curled = 0
    for pb in rig.pose.bones:
        n = pb.name.lower()
        if not any(n.startswith(s) for s in stems):
            continue
        seg = None
        for s in (".01.", ".02.", ".03."):
            if s in n:
                seg = s[1:3]
                break
        if seg is None:
            continue
        c = (thumb_by_seg if "thumb" in n else curl_by_seg).get(seg, 0.0)
        if c == 0.0:
            continue
        for _c in pb.constraints:
            _c.mute = True
        pb.rotation_mode = "XYZ"
        pb.rotation_euler.x = c
        try:
            pb.keyframe_insert(data_path="rotation_euler", index=0, frame=1)
            curled += 1
        except Exception:
            pass
    return curled


def _foot_lock_per_frame(rig, ground_z: float, frame_start: int, frame_end: int) -> int:
    """Sink-proof foot lock across a walk clip.

    We iterate the action, and for each frame where a foot IK target would go
    below ``ground_z`` in world Z, we lift it back up and rekey. Runs after
    the LIMIT_LOCATION constraint so we know the local floor is 0.
    """
    _to_pose_mode(rig)
    corrections = 0
    depsgraph = bpy.context.evaluated_depsgraph_get()
    for side in ("L", "R"):
        foot = rig.pose.bones.get(f"foot_ik.{side}") or rig.pose.bones.get(f"foot.{side}")
        if foot is None:
            continue
        for f in range(frame_start, frame_end + 1):
            bpy.context.scene.frame_set(f)
            depsgraph.update()
            world_head = rig.matrix_world @ foot.head
            if world_head.z < ground_z - 0.005:
                # lift in world; convert delta to local
                dz = (ground_z - world_head.z) + 0.002
                # nudge in local frame — foot_ik local Y is up-ish for Rigify
                foot.location.y += dz
                try:
                    foot.keyframe_insert(data_path="location", frame=f)
                    corrections += 1
                except Exception:
                    pass
    return corrections


def _root_bounce(rig, frame_count: int, fps: int) -> int:
    """Add a subtle sinusoidal head bob if the retarget didn't already."""
    torso = rig.pose.bones.get("torso") or rig.pose.bones.get("spine_fk")
    if torso is None:
        return 0
    # Skip if any keyframe on torso.location[2] already exists
    if rig.animation_data and rig.animation_data.action:
        for fc in _iter_action_fcurves(rig.animation_data.action):
            if torso.name in fc.data_path and "location" in fc.data_path and fc.array_index == 2:
                return 0
    torso.rotation_mode = "XYZ"
    torso.location.z = 0.0
    for f in range(1, frame_count + 1):
        t = (f - 1) / max(1, fps)
        torso.location.z = 0.010 * math.sin(2 * math.pi * 2.0 * t)
        torso.keyframe_insert(data_path="location", index=2, frame=f)
    return frame_count


def _clamp_mixamo_spine(rig) -> int:
    """Bake-clamp the Mixamo spine/neck rotation keyframes to a physiological
    range. Retargeting a HumanML3D/MoMask BVH onto a Mixamo skeleton over-rotates
    the spine chain (Spine1/Spine2 up to 100+deg vs ~10deg natural) because the
    source and Mixamo spine rest orientations differ, folding the waist and
    shattering the torso mesh. We slerp each over-limit keyframe quaternion back
    toward identity, capping the angle, and bake it into the keys so it survives
    glTF export (constraints are not evaluated by three.js). No-op on non-Mixamo
    rigs (bones absent) and on already-natural motion."""
    import mathutils
    act = rig.animation_data.action if rig.animation_data else None
    if not act:
        return 0
    limits = {
        "mixamorig:Spine": 12.0, "mixamorig:Spine1": 12.0, "mixamorig:Spine2": 10.0,
        "mixamorig:Neck": 22.0, "mixamorig:Head": 18.0,
    }
    total = 0
    for name, max_deg in limits.items():
        pb = rig.pose.bones.get(name)
        if not pb:
            continue
        dp = pb.path_from_id("rotation_quaternion")
        fcs = {fc.array_index: fc for fc in act.fcurves if fc.data_path == dp}
        if len(fcs) < 4:
            continue
        maxr = math.radians(max_deg)
        kmap = {i: {int(round(kp.co.x)): kp for kp in fcs[i].keyframe_points} for i in range(4)}
        for f in sorted(kmap[0].keys()):
            q = mathutils.Quaternion((fcs[0].evaluate(f), fcs[1].evaluate(f),
                                      fcs[2].evaluate(f), fcs[3].evaluate(f)))
            q.normalize()
            if q.angle > maxr and q.angle > 1e-4:
                qc = mathutils.Quaternion().slerp(q, maxr / q.angle)
                for i, val in enumerate((qc.w, qc.x, qc.y, qc.z)):
                    if f in kmap[i]:
                        kmap[i][f].co.y = val
                total += 1
        for fc in fcs.values():
            fc.update()
    return total


def run_mocap_bake(
    rig,
    bvh_path: str,
    orig_mesh_names,
    ground_z: float,
    mesh_fallback=None,
    arm_swing_boost: float = 1.3,
    per_frame_foot_lock: bool = True,
) -> dict:
    """Retarget a BVH onto ``rig`` and apply the gait polish. Returns a report."""
    report = {"bvh": bvh_path, "steps": {}}

    _register_retarget_bvh()

    # STEP 1: BVH-source arm swing amplification. MoMask walks often produce
    # 5-6 cm wrist swing; on a mesh with damped skinning that reads as "no
    # swing at all". Amplifying the source Euler angles at the arm/shoulder
    # joints stretches the swing WITHOUT changing rotation axes, which is
    # unambiguous (unlike quaternion component scaling at the pose level).
    # See ``amplify_bvh_arm_swing`` docstring.
    _arm_amp = float(os.environ.get("AURORA_MOCAP_BVH_ARM_AMP", "1.6"))
    if _arm_amp > 1.001:
        try:
            import tempfile as _tf
            amplified = _tf.NamedTemporaryFile(suffix="_armswing.bvh", delete=False).name
            _rep = amplify_bvh_arm_swing(bvh_path, amplified, factor=_arm_amp)
            bvh_path = amplified
            report["steps"]["bvh_arm_swing_amp"] = _rep
        except Exception as exc:
            report["steps"]["bvh_arm_swing_amp_error"] = str(exc)

    # STEP 2: sanitize the BVH — strip root translation. On a RIGIFY rig the Hips
    # BVH channel drives the torso IK and a ~5m path shatters the shirt/hair, so we
    # zero it (walk-in-place). BUT on a MIXAMO rig the Hips is just the rigid root:
    # translating it moves the whole body, no shatter — and zeroing it is exactly
    # what makes the planted foot SKATE 1.5m (treadmill without a belt). Since the
    # torso shatter is now prevented by _clamp_mixamo_spine, we KEEP the root
    # translation on Mixamo -> the stance foot stays planted, no skating (the
    # character advances forward, which is the physically correct walk).
    _is_mixamo = any("mixamo" in b.name.lower() for b in rig.data.bones)
    _keep_root = os.environ.get("AURORA_MOCAP_KEEP_ROOT_TRANS", "0") == "1" or _is_mixamo
    if _keep_root:
        report["steps"]["sanitize_bvh"] = "root_translation_KEPT (mixamo anti-skate)" if _is_mixamo else "root_translation_kept (env)"
    if not _keep_root:
        import tempfile as _tf
        sanitized = _tf.NamedTemporaryFile(suffix="_inplace.bvh", delete=False).name
        try:
            lock_yaw = os.environ.get("AURORA_MOCAP_LOCK_YAW", "1") != "0"
            sanitize_bvh_root(bvh_path, sanitized, lock_yaw=lock_yaw)
            bvh_path = sanitized
            report["steps"]["sanitize_bvh"] = (
                "root_translation_zeroed" + (",yaw_detrended" if lock_yaw else "")
            )
        except Exception as exc:
            report["steps"]["sanitize_bvh_error"] = str(exc)

    _load_and_retarget(rig, bvh_path, use_nla=False,
                       target_rig="Mixamo" if _is_mixamo else "")
    report["steps"]["retarget"] = "ok"

    # Mixamo spine clamp (fixes waist shatter when a MoMask BVH is retargeted
    # onto a MIA/Mixamo rig — see _clamp_mixamo_spine). No-op on Rigify rigs.
    try:
        report["steps"]["mixamo_spine_clamp"] = _clamp_mixamo_spine(rig)
    except Exception as exc:
        report["steps"]["mixamo_spine_clamp_error"] = str(exc)

    # Neck / feet / fingers polish
    try:
        report["steps"]["neck_limit"] = _apply_neck_limit(rig)
    except Exception as exc:
        report["steps"]["neck_limit_error"] = str(exc)
    try:
        report["steps"]["foot_ground_clamp"] = _apply_foot_ground_clamp(rig)
    except Exception as exc:
        report["steps"]["foot_ground_clamp_error"] = str(exc)
    try:
        report["steps"]["finger_curl"] = _bake_finger_curl(rig)
    except Exception as exc:
        report["steps"]["finger_curl_error"] = str(exc)

    # Arm swing amplification
    try:
        n = _amplify_arm_swing(rig, factor=arm_swing_boost)
        report["steps"]["arm_swing_boost"] = {"factor": arm_swing_boost, "fcurves": n}
    except Exception as exc:
        report["steps"]["arm_swing_boost_error"] = str(exc)

    # Per-frame foot lock (kills the passing-foot float).
    # Use the retargeted action's fcurves ALONE — scn.frame_end defaults to 250
    # in a fresh scene which would tack on 55 frames of dead space at the end.
    scn = bpy.context.scene
    f0, f1 = 1, 1
    if rig.animation_data and rig.animation_data.action:
        try:
            fcs = _iter_action_fcurves(rig.animation_data.action)
            all_kx = [int(kp.co.x) for fc in fcs for kp in fc.keyframe_points]
            if all_kx:
                f0 = max(1, min(all_kx))
                f1 = max(all_kx)
        except Exception:
            pass
    scn.frame_start = f0
    scn.frame_end = f1
    report["frame_range"] = [f0, f1]

    if per_frame_foot_lock:
        try:
            fixes = _foot_lock_per_frame(rig, ground_z, f0, f1)
            report["steps"]["foot_lock_per_frame"] = fixes
        except Exception as exc:
            report["steps"]["foot_lock_per_frame_error"] = str(exc)

    # Skip _root_bounce for now — MoMask already has natural pelvis bounce.
    _to_object_mode()
    return report
