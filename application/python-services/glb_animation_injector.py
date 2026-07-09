#!/usr/bin/env python
"""Aurora — patch a rigged GLB with a real glTF animation block.

Why this exists: rigify_autorig produces rigged GLBs (skins + skeleton
nodes) but the Blender 5.1 glTF I/O exporter's active-action mode
silently drops cross-object actions assigned by motion_baker, leaving
exported files with `animations=[]`. A web-side viewer (Three.js,
model-viewer) loads the mesh statically.

This script doesn't re-run Blender. It opens the existing GLB, walks
the glTF JSON + binary chunks, and injects a synthetic glTF animation
that targets the root node with a Y-axis rotation cycle (or a
translate/scale primitive selected by --motion-kind). Output: same GLB
with animations.length >= 1, ready for Three.js to play.

Schema: aurora.glb_inject.v1.

Usage:
    python glb_animation_injector.py \\
        --input  cat3_meca_RIGGED.glb \\
        --output cat3_meca_RIGGED_anim.glb \\
        --motion-kind rotate_y \\
        --duration 4.0
"""

from __future__ import annotations

import argparse
import json
import math
import struct
import sys
from pathlib import Path


CHUNK_JSON = 0x4E4F534A   # 'JSON'
CHUNK_BIN  = 0x004E4942   # 'BIN\0'

# Component types per glTF 2.0 §3.6.2.2 — only FLOAT (5126) needed here.
COMPONENT_FLOAT = 5126


BONE_KEYWORDS_HUMANOID = {
    "thigh.L":     ("thigh.l",),
    "thigh.R":     ("thigh.r",),
    "upper_arm.L": ("upper_arm.l", "upperarm.l"),
    "upper_arm.R": ("upper_arm.r", "upperarm.r"),
    # v80ab — knee + elbow flexion enriches the walk cycle (foot lifts as
    # knee bends, arm swing has elbow flex). All Rigify-template rigs from
    # rigify_autorig produce these bones.
    "shin.L":     ("shin.l",),
    "shin.R":     ("shin.r",),
    "forearm.L":  ("forearm.l",),
    "forearm.R":  ("forearm.r",),
}


def _find_humanoid_bones(gltf: dict) -> dict[str, int]:
    """Locate Rigify-style bone node indices by exact name match (case-
    insensitive). Returns {logical_name: node_index} for bones found.
    Filters out tweak / MCH / VIS / DEF / ORG variants — only the
    main deformer bone is useful for top-level animation."""
    nodes = gltf.get("nodes") or []
    found: dict[str, int] = {}
    for i, n in enumerate(nodes):
        name = (n.get("name") or "").lower()
        if any(t in name for t in ("tweak", "mch-", "vis_", "def-", "org-")):
            continue
        for logical, aliases in BONE_KEYWORDS_HUMANOID.items():
            if name in aliases:
                found.setdefault(logical, i)
    return found


def _quat_x(angle_rad: float) -> tuple[float, float, float, float]:
    """Rotation quaternion around +X axis (xyzw order, glTF convention)."""
    half = angle_rad / 2.0
    return (math.sin(half), 0.0, 0.0, math.cos(half))


def _build_keyframe_floats(motion_kind: str, duration: float, fps: int = 30) -> tuple[bytes, bytes, list, str, int]:
    """Generate keyframe times + values for a chosen motion. Returns
    (times_bytes, values_bytes, value_per_keyframe_count, target_path, n_frames).

    motion_kind:
       rotate_y  — quaternion rotation around Y, full 360° in `duration` (target='rotation')
       bob       — translation Y oscillation +/- 0.05 m (target='translation')
       breathe   — uniform scale oscillation 1.00 → 1.04 (target='scale')
    """
    n = max(2, int(duration * fps))
    times = [i * (duration / (n - 1)) for i in range(n)]

    if motion_kind == "rotate_y":
        # Quaternion (xyzw) rotating around +Y, full 360° over duration.
        values: list[tuple[float, float, float, float]] = []
        for t in times:
            angle = 2.0 * math.pi * (t / duration)
            half = angle / 2.0
            values.append((0.0, math.sin(half), 0.0, math.cos(half)))
        comp = 4
        path = "rotation"
    elif motion_kind == "bob":
        values = [(0.0, 0.05 * math.sin(2.0 * math.pi * t / duration), 0.0)
                  for t in times]
        comp = 3
        path = "translation"
    elif motion_kind == "breathe":
        values = [(1.0 + 0.04 * math.sin(2.0 * math.pi * t / duration),) * 3
                  for t in times]
        comp = 3
        path = "scale"
    else:
        raise ValueError(f"unknown motion_kind: {motion_kind}")

    times_bytes = b"".join(struct.pack("<f", t) for t in times)
    flat: list[float] = []
    for v in values:
        flat.extend(v)
    values_bytes = b"".join(struct.pack("<f", x) for x in flat)
    return times_bytes, values_bytes, comp, path, n


def _emit_glb(gltf: dict, bin_blob: bytes, version: int, output_path: Path) -> int:
    """Re-emit a GLB from the patched JSON + binary chunks. Returns total size."""
    new_json = json.dumps(gltf, separators=(",", ":")).encode("utf-8")
    json_pad = (4 - (len(new_json) % 4)) % 4
    new_json_padded = new_json + (b" " * json_pad)
    bin_pad = (4 - (len(bin_blob) % 4)) % 4
    new_bin_padded = bin_blob + (b"\x00" * bin_pad)
    total = 12 + 8 + len(new_json_padded) + 8 + len(new_bin_padded)
    out = bytearray()
    out += b"glTF"
    out += struct.pack("<II", version, total)
    out += struct.pack("<II", len(new_json_padded), CHUNK_JSON)
    out += new_json_padded
    out += struct.pack("<II", len(new_bin_padded), CHUNK_BIN)
    out += new_bin_padded
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(bytes(out))
    return total


def _inject_per_part_rotate(gltf: dict, bin_blob: bytes, version: int,
                            output_path: Path, duration: float) -> dict:
    """v80ak — one rotation channel per top-level scene node. Designed for
    mesh_part_split outputs (k=4 clusters → 4 nodes, each with its own
    translation = cluster centroid). Each part rotates around its own pivot
    in alternating directions, breaking the 'rigid chassis' illusion."""
    chans_spec = _build_per_part_rotation_channels(gltf, duration)
    if not chans_spec:
        return {"ok": False, "error": "no top-level nodes to animate"}

    pad_before = (4 - (len(bin_blob) % 4)) % 4
    new_bin = bin_blob + (b"\x00" * pad_before)
    bvs = gltf.setdefault("bufferViews", [])
    accs = gltf.setdefault("accessors", [])
    samplers: list[dict] = []
    channels: list[dict] = []

    for ch in chans_spec:
        # Times accessor
        t_offset = len(new_bin)
        new_bin += ch["times"]
        pad = (4 - (len(new_bin) % 4)) % 4
        new_bin += b"\x00" * pad
        bv_t = len(bvs)
        bvs.append({"buffer": 0, "byteOffset": t_offset,
                    "byteLength": len(ch["times"])})
        acc_t = len(accs)
        accs.append({
            "bufferView": bv_t, "componentType": COMPONENT_FLOAT,
            "count": ch["n"], "type": "SCALAR",
            "min": [0.0], "max": [duration],
        })
        # Values accessor
        v_offset = len(new_bin)
        new_bin += ch["values"]
        pad = (4 - (len(new_bin) % 4)) % 4
        new_bin += b"\x00" * pad
        bv_v = len(bvs)
        bvs.append({"buffer": 0, "byteOffset": v_offset,
                    "byteLength": len(ch["values"])})
        acc_v = len(accs)
        accs.append({
            "bufferView": bv_v, "componentType": COMPONENT_FLOAT,
            "count": ch["n"], "type": "VEC4",
        })
        sampler_idx = len(samplers)
        samplers.append({"input": acc_t, "output": acc_v,
                         "interpolation": "LINEAR"})
        channels.append({
            "sampler": sampler_idx,
            "target": {"node": ch["target_node_index"], "path": "rotation"},
        })

    if not gltf.get("buffers"):
        gltf["buffers"] = [{"byteLength": 0}]
    gltf["buffers"][0]["byteLength"] = len(new_bin)

    anim_idx = len(gltf.setdefault("animations", []))
    gltf["animations"].append({
        "name": "aurora_inject_gear_train_split_rotate",
        "samplers": samplers,
        "channels": channels,
    })

    size = _emit_glb(gltf, new_bin, version, output_path)
    return {
        "ok": True,
        "schema": "aurora.glb_inject.v1",
        "output": str(output_path),
        "motion_kind": "gear_train_split_rotate",
        "duration_s": duration,
        "n_channels": len(channels),
        "parts_animated": [c["target_name"] for c in chans_spec],
        "size_bytes": size,
        "animations_now": anim_idx + 1,
    }


def _inject_walk_humanoid(gltf: dict, bin_blob: bytes, version: int,
                          output_path: Path, duration: float) -> dict:
    """Multi-channel injection: drives 4 Rigify bones (thigh.L/R, upper_arm.L/R)
    at phase-offset oscillations to produce a real walk cycle. Falls back to
    rotate_y on root if the named bones are not found."""
    bones = _find_humanoid_bones(gltf)
    if not bones or len(bones) < 2:
        # No Rigify bones found — fall back to single-channel rotate_y
        # so even non-humanoid rigs still get *some* visible motion.
        times_bytes, values_bytes, comp_count, anim_path, n_frames = (
            _build_keyframe_floats("rotate_y", duration)
        )
        return _inject_single_channel(
            gltf, bin_blob, version, output_path,
            times_bytes, values_bytes, comp_count, anim_path, n_frames,
            target_node_index=None,
            anim_name="aurora_inject_walk_humanoid_fallback",
        )

    channels_spec = _build_walk_humanoid_channels(duration)
    # Filter to channels whose bone is present in this rig
    active = [c for c in channels_spec if c["bone"] in bones]

    # Append all channel data into bin, build accessors + bufferViews
    pad_before = (4 - (len(bin_blob) % 4)) % 4
    new_bin = bin_blob + (b"\x00" * pad_before)
    bvs = gltf.setdefault("bufferViews", [])
    accs = gltf.setdefault("accessors", [])
    samplers: list[dict] = []
    channels: list[dict] = []

    for ch in active:
        # Times
        t_offset = len(new_bin)
        new_bin += ch["times"]
        pad = (4 - (len(new_bin) % 4)) % 4
        new_bin += b"\x00" * pad
        bv_t = len(bvs)
        bvs.append({"buffer": 0, "byteOffset": t_offset, "byteLength": len(ch["times"])})
        acc_t = len(accs)
        accs.append({
            "bufferView": bv_t, "componentType": COMPONENT_FLOAT,
            "count": ch["n"], "type": "SCALAR",
            "min": [0.0], "max": [duration],
        })
        # Values
        v_offset = len(new_bin)
        new_bin += ch["values"]
        pad = (4 - (len(new_bin) % 4)) % 4
        new_bin += b"\x00" * pad
        bv_v = len(bvs)
        bvs.append({"buffer": 0, "byteOffset": v_offset, "byteLength": len(ch["values"])})
        acc_v = len(accs)
        accs.append({
            "bufferView": bv_v, "componentType": COMPONENT_FLOAT,
            "count": ch["n"], "type": "VEC4" if ch["comp"] == 4 else "VEC3",
        })

        sampler_idx = len(samplers)
        samplers.append({"input": acc_t, "output": acc_v, "interpolation": "LINEAR"})
        channels.append({
            "sampler": sampler_idx,
            "target": {"node": bones[ch["bone"]], "path": ch["path"]},
        })

    if not gltf.get("buffers"):
        gltf["buffers"] = [{"byteLength": 0}]
    gltf["buffers"][0]["byteLength"] = len(new_bin)

    anim_idx = len(gltf.setdefault("animations", []))
    gltf["animations"].append({
        "name": "aurora_inject_walk_humanoid",
        "samplers": samplers,
        "channels": channels,
    })

    size = _emit_glb(gltf, new_bin, version, output_path)
    return {
        "ok": True,
        "schema": "aurora.glb_inject.v1",
        "output": str(output_path),
        "motion_kind": "walk_humanoid",
        "duration_s": duration,
        "bones_animated": list(bones.keys()),
        "n_channels": len(channels),
        "size_bytes": size,
        "animations_now": anim_idx + 1,
    }


def _inject_single_channel(gltf, bin_blob, version, output_path,
                           times_bytes, values_bytes, comp_count,
                           anim_path, n_frames,
                           target_node_index=None,
                           anim_name=None,
                           duration=None):
    """Fallback / shared path for single-channel root-targeted injection.
    Pulled out of inject() so walk_humanoid's fallback can re-use it."""
    pad_before = (4 - (len(bin_blob) % 4)) % 4
    new_bin = bin_blob + (b"\x00" * pad_before)
    times_offset = len(new_bin)
    new_bin += times_bytes
    pad = (4 - (len(new_bin) % 4)) % 4
    new_bin += b"\x00" * pad
    values_offset = len(new_bin)
    new_bin += values_bytes
    pad = (4 - (len(new_bin) % 4)) % 4
    new_bin += b"\x00" * pad

    if not gltf.get("buffers"):
        gltf["buffers"] = [{"byteLength": 0}]
    gltf["buffers"][0]["byteLength"] = len(new_bin)

    bvs = gltf.setdefault("bufferViews", [])
    bv_t = len(bvs)
    bvs.append({"buffer": 0, "byteOffset": times_offset, "byteLength": len(times_bytes)})
    bv_v = len(bvs)
    bvs.append({"buffer": 0, "byteOffset": values_offset, "byteLength": len(values_bytes)})

    accs = gltf.setdefault("accessors", [])
    acc_t = len(accs)
    accs.append({
        "bufferView": bv_t, "componentType": COMPONENT_FLOAT,
        "count": n_frames, "type": "SCALAR",
        "min": [0.0], "max": [duration if duration else 4.0],
    })
    acc_v = len(accs)
    accs.append({
        "bufferView": bv_v, "componentType": COMPONENT_FLOAT,
        "count": n_frames, "type": "VEC4" if comp_count == 4 else "VEC3",
    })

    if target_node_index is None:
        scene_idx = gltf.get("scene", 0)
        scenes = gltf.get("scenes") or []
        if scenes and scenes[scene_idx].get("nodes"):
            target_node_index = scenes[scene_idx]["nodes"][0]
        else:
            target_node_index = 0

    anim_idx = len(gltf.setdefault("animations", []))
    gltf["animations"].append({
        "name": anim_name or f"aurora_inject_{anim_path}",
        "samplers": [{"input": acc_t, "output": acc_v, "interpolation": "LINEAR"}],
        "channels": [{
            "sampler": 0,
            "target": {"node": target_node_index, "path": anim_path},
        }],
    })

    size = _emit_glb(gltf, new_bin, version, output_path)
    return {
        "ok": True,
        "schema": "aurora.glb_inject.v1",
        "output": str(output_path),
        "n_frames": n_frames,
        "target_node_index": target_node_index,
        "animation_path": anim_path,
        "size_bytes": size,
        "animations_now": anim_idx + 1,
    }


def _build_per_part_rotation_channels(gltf: dict, duration: float, fps: int = 30) -> list[dict]:
    """v80ak — for assets produced by mesh_part_split (one node per cluster
    each with its own translation = cluster centroid), drive each top-level
    node's local Y rotation independently. Adjacent parts get opposite
    spin signs so the result reads as 'gears meshing' not 'whole chassis
    spinning together'.

    Returns a list of {target_node_index, times, values, comp, path} dicts
    ready to be wired into the glTF animation arrays."""
    nodes = gltf.get("nodes") or []
    scenes = gltf.get("scenes") or []
    scene_idx = gltf.get("scene", 0)
    root_indices = (scenes[scene_idx].get("nodes") if scenes else None) or list(range(len(nodes)))

    n = max(2, int(duration * fps))
    times = [i * (duration / (n - 1)) for i in range(n)]
    times_bytes = b"".join(struct.pack("<f", t) for t in times)

    channels: list[dict] = []
    # Each top-level node gets its own rotation track. Frequencies alternate
    # so neighbouring gears mesh in opposite directions at compatible speeds.
    for slot, node_idx in enumerate(root_indices):
        if node_idx >= len(nodes):
            continue
        # Cycle 1.0 → 1.5 → 0.75 → 2.0 → … so parts visibly differ
        omega_per_cycle = (2.0 * math.pi) * (1.0 + 0.25 * (slot % 4))
        sign = 1.0 if (slot % 2 == 0) else -1.0
        out_floats: list[float] = []
        for t in times:
            angle = sign * omega_per_cycle * (t / duration)
            half = angle / 2.0
            out_floats.extend((0.0, math.sin(half), 0.0, math.cos(half)))
        values_bytes = b"".join(struct.pack("<f", x) for x in out_floats)
        channels.append({
            "target_node_index": int(node_idx),
            "target_name": nodes[node_idx].get("name", f"node_{node_idx}"),
            "times": times_bytes, "values": values_bytes,
            "n": n, "comp": 4, "path": "rotation",
        })
    return channels


def _build_walk_humanoid_channels(duration: float, fps: int = 30) -> list[dict]:
    """Build phase-offset rotation tracks for a Rigify humanoid walk.

    8 channels (2 per limb pair, 4 limb pairs):
       thigh.L      → +X rotation phase 0      ±20° (forward swing)
       thigh.R      → +X rotation phase π      (180° offset, opposite leg)
       shin.L       → +X rotation phase π/2    knee bends as foot lifts
       shin.R       → +X rotation phase 3π/2   (offset by π from shin.L)
       upper_arm.L  → +X rotation phase π      mirrors thigh.R (opposite arm-leg sync)
       upper_arm.R  → +X rotation phase 0      mirrors thigh.L
       forearm.L    → +X rotation phase 3π/2   elbow bends with arm swing
       forearm.R    → +X rotation phase π/2

    Knee/elbow flexion uses HALF the amplitude of hip/shoulder so the joint
    visibly bends without overshooting. Returns a list of {bone, times,
    values, comp, path} dicts."""
    n = max(2, int(duration * fps))
    times = [i * (duration / (n - 1)) for i in range(n)]
    times_bytes = b"".join(struct.pack("<f", t) for t in times)
    omega = 2.0 * math.pi / duration
    amp_main = math.radians(20.0)   # hip / shoulder swing
    amp_flex = math.radians(15.0)   # knee / elbow flex (one-direction-biased below)

    def _vals(phase: float, amp: float, bias: float = 0.0) -> bytes:
        """bias adds a constant offset so flexion bones bend rather than
        oscillate symmetrically (knees only bend forward, elbows only flex)."""
        out: list[float] = []
        for t in times:
            angle = bias + amp * math.sin(omega * t + phase)
            q = _quat_x(angle)
            out.extend(q)
        return b"".join(struct.pack("<f", x) for x in out)

    return [
        # Hips
        {"bone": "thigh.L",     "times": times_bytes, "values": _vals(0.0, amp_main),
         "n": n, "comp": 4, "path": "rotation"},
        {"bone": "thigh.R",     "times": times_bytes, "values": _vals(math.pi, amp_main),
         "n": n, "comp": 4, "path": "rotation"},
        # Knees (biased so they only bend forward — leg goes straight then bends)
        {"bone": "shin.L",      "times": times_bytes,
         "values": _vals(math.pi / 2.0, amp_flex, bias=-amp_flex),
         "n": n, "comp": 4, "path": "rotation"},
        {"bone": "shin.R",      "times": times_bytes,
         "values": _vals(3.0 * math.pi / 2.0, amp_flex, bias=-amp_flex),
         "n": n, "comp": 4, "path": "rotation"},
        # Shoulders
        {"bone": "upper_arm.L", "times": times_bytes, "values": _vals(math.pi, amp_main),
         "n": n, "comp": 4, "path": "rotation"},
        {"bone": "upper_arm.R", "times": times_bytes, "values": _vals(0.0, amp_main),
         "n": n, "comp": 4, "path": "rotation"},
        # Elbows (biased forward like knees)
        {"bone": "forearm.L",   "times": times_bytes,
         "values": _vals(3.0 * math.pi / 2.0, amp_flex, bias=-amp_flex),
         "n": n, "comp": 4, "path": "rotation"},
        {"bone": "forearm.R",   "times": times_bytes,
         "values": _vals(math.pi / 2.0, amp_flex, bias=-amp_flex),
         "n": n, "comp": 4, "path": "rotation"},
    ]


def _find_morph_target_node(gltf: dict, target_node_index: int | None) -> tuple[int | None, int]:
    nodes = gltf.get("nodes") or []
    meshes = gltf.get("meshes") or []

    def _target_count(node) -> int:
        mesh_idx = node.get("mesh")
        if mesh_idx is None or mesh_idx >= len(meshes):
            return 0
        prims = meshes[mesh_idx].get("primitives") or []
        if not prims:
            return 0
        return len(prims[0].get("targets") or [])

    if target_node_index is not None and target_node_index < len(nodes):
        return target_node_index, _target_count(nodes[target_node_index])
    for i, node in enumerate(nodes):
        n = _target_count(node)
        if n > 0:
            return i, n
    return None, 0


def _inject_weights(gltf: dict, bin_blob: bytes, version: int,
                    output_path: Path, duration: float,
                    target_node_index: int | None, fps: int = 30) -> dict:
    node_idx, n_targets = _find_morph_target_node(gltf, target_node_index)
    if node_idx is None or n_targets <= 0:
        return {"ok": False,
                "error": "no node with morph targets found (weights path needs mesh.primitives[0].targets)"}

    n = max(2, int(duration * fps))
    times = [i * (duration / (n - 1)) for i in range(n)]
    times_bytes = b"".join(struct.pack("<f", t) for t in times)
    flat: list[float] = []
    for t in times:
        cycle = (t / duration) % 1.0
        for k in range(n_targets):
            d = abs((cycle * n_targets) - k) % n_targets
            d = min(d, n_targets - d)
            flat.append(max(0.0, 1.0 - d))
    values_bytes = b"".join(struct.pack("<f", x) for x in flat)

    pad_before = (4 - (len(bin_blob) % 4)) % 4
    new_bin = bin_blob + (b"\x00" * pad_before)
    bvs = gltf.setdefault("bufferViews", [])
    accs = gltf.setdefault("accessors", [])

    t_offset = len(new_bin)
    new_bin += times_bytes
    new_bin += b"\x00" * ((4 - (len(new_bin) % 4)) % 4)
    bv_t = len(bvs)
    bvs.append({"buffer": 0, "byteOffset": t_offset, "byteLength": len(times_bytes)})
    acc_t = len(accs)
    accs.append({
        "bufferView": bv_t, "componentType": COMPONENT_FLOAT,
        "count": n, "type": "SCALAR",
        "min": [0.0], "max": [duration],
    })

    v_offset = len(new_bin)
    new_bin += values_bytes
    new_bin += b"\x00" * ((4 - (len(new_bin) % 4)) % 4)
    bv_v = len(bvs)
    bvs.append({"buffer": 0, "byteOffset": v_offset, "byteLength": len(values_bytes)})
    acc_v = len(accs)
    accs.append({
        "bufferView": bv_v, "componentType": COMPONENT_FLOAT,
        "count": n * n_targets, "type": "SCALAR",
    })

    if not gltf.get("buffers"):
        gltf["buffers"] = [{"byteLength": 0}]
    gltf["buffers"][0]["byteLength"] = len(new_bin)

    anim_idx = len(gltf.setdefault("animations", []))
    gltf["animations"].append({
        "name": "aurora_inject_weights",
        "samplers": [{"input": acc_t, "output": acc_v, "interpolation": "LINEAR"}],
        "channels": [{
            "sampler": 0,
            "target": {"node": node_idx, "path": "weights"},
        }],
    })

    size = _emit_glb(gltf, new_bin, version, output_path)
    return {
        "ok": True,
        "schema": "aurora.glb_inject.v1",
        "output": str(output_path),
        "motion_kind": "weights",
        "duration_s": duration,
        "n_frames": n,
        "n_morph_targets": n_targets,
        "target_node_index": node_idx,
        "animation_path": "weights",
        "size_bytes": size,
        "animations_now": anim_idx + 1,
    }


def inject(input_path: Path, output_path: Path, *,
           motion_kind: str = "rotate_y", duration: float = 4.0,
           target_node_index: int | None = None) -> dict:
    """Patch a GLB with a glTF animation block. Returns a report dict."""
    raw = input_path.read_bytes()
    if raw[:4] != b"glTF":
        return {"ok": False, "error": "not a glb (missing glTF magic)"}

    # Header: magic(4) + version(4) + length(4) = 12 bytes
    version, total_len = struct.unpack_from("<II", raw, 4)
    cursor = 12

    json_chunk_len, json_chunk_type = struct.unpack_from("<II", raw, cursor)
    cursor += 8
    if json_chunk_type != CHUNK_JSON:
        return {"ok": False, "error": "first chunk is not JSON"}
    json_blob = raw[cursor:cursor + json_chunk_len].rstrip(b"\x00")
    cursor += json_chunk_len
    gltf = json.loads(json_blob)

    bin_blob = b""
    if cursor < len(raw):
        bin_chunk_len, bin_chunk_type = struct.unpack_from("<II", raw, cursor)
        cursor += 8
        if bin_chunk_type == CHUNK_BIN:
            bin_blob = raw[cursor:cursor + bin_chunk_len]

    # walk_humanoid takes a different path: multi-channel with bone-name
    # discovery. Falls through to the single-channel path for everything else.
    if motion_kind == "walk_humanoid":
        return _inject_walk_humanoid(gltf, bin_blob, version, output_path, duration)

    # gear_train_split_rotate: one rotation channel per top-level scene node.
    # Designed for mesh_part_split outputs where each cluster is its own node.
    # Result reads as parts moving relative to each other rather than a
    # single rigid block rotating.
    if motion_kind == "gear_train_split_rotate":
        return _inject_per_part_rotate(gltf, bin_blob, version, output_path, duration)

    if motion_kind == "weights":
        return _inject_weights(gltf, bin_blob, version, output_path, duration,
                               target_node_index)

    # Generate keyframe data
    times_bytes, values_bytes, comp_count, anim_path, n_frames = (
        _build_keyframe_floats(motion_kind, duration)
    )

    # Pad bin to 4-byte boundary before appending
    pad_before = (4 - (len(bin_blob) % 4)) % 4
    bin_blob_padded = bin_blob + (b"\x00" * pad_before)

    times_offset = len(bin_blob_padded)
    times_len = len(times_bytes)
    pad_after_times = (4 - (times_len % 4)) % 4
    values_offset = times_offset + times_len + pad_after_times
    values_len = len(values_bytes)
    pad_after_values = (4 - (values_len % 4)) % 4
    new_bin = (bin_blob_padded
               + times_bytes + (b"\x00" * pad_after_times)
               + values_bytes + (b"\x00" * pad_after_values))

    # Buffer 0: extend its byteLength
    if not gltf.get("buffers"):
        gltf["buffers"] = [{"byteLength": 0}]
    gltf["buffers"][0]["byteLength"] = len(new_bin)

    # Two new bufferViews
    bvs = gltf.setdefault("bufferViews", [])
    bv_times_idx = len(bvs)
    bvs.append({
        "buffer": 0, "byteOffset": times_offset, "byteLength": times_len,
    })
    bv_values_idx = len(bvs)
    bvs.append({
        "buffer": 0, "byteOffset": values_offset, "byteLength": values_len,
    })

    # Two new accessors
    accs = gltf.setdefault("accessors", [])
    acc_times_idx = len(accs)
    accs.append({
        "bufferView": bv_times_idx,
        "componentType": COMPONENT_FLOAT,
        "count": n_frames,
        "type": "SCALAR",
        "min": [0.0],
        "max": [duration],
    })
    acc_values_idx = len(accs)
    accs.append({
        "bufferView": bv_values_idx,
        "componentType": COMPONENT_FLOAT,
        "count": n_frames,
        "type": "VEC4" if comp_count == 4 else "VEC3",
    })

    # Pick target node — default to scene's first root node
    if target_node_index is None:
        scene_idx = gltf.get("scene", 0)
        scenes = gltf.get("scenes") or []
        if scenes and scenes[scene_idx].get("nodes"):
            target_node_index = scenes[scene_idx]["nodes"][0]
        else:
            target_node_index = 0

    # New animation
    anims = gltf.setdefault("animations", [])
    anim_idx = len(anims)
    anims.append({
        "name": f"aurora_inject_{motion_kind}",
        "samplers": [{
            "input":  acc_times_idx,
            "output": acc_values_idx,
            "interpolation": "LINEAR",
        }],
        "channels": [{
            "sampler": 0,
            "target": {"node": target_node_index, "path": anim_path},
        }],
    })

    # Re-emit GLB
    new_json = json.dumps(gltf, separators=(",", ":")).encode("utf-8")
    json_pad = (4 - (len(new_json) % 4)) % 4
    new_json_padded = new_json + (b" " * json_pad)
    bin_pad = (4 - (len(new_bin) % 4)) % 4
    new_bin_padded = new_bin + (b"\x00" * bin_pad)

    total = (
        12  # GLB header
        + 8 + len(new_json_padded)
        + 8 + len(new_bin_padded)
    )
    out = bytearray()
    out += b"glTF"
    out += struct.pack("<II", version, total)
    out += struct.pack("<II", len(new_json_padded), CHUNK_JSON)
    out += new_json_padded
    out += struct.pack("<II", len(new_bin_padded), CHUNK_BIN)
    out += new_bin_padded

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(bytes(out))
    return {
        "ok": True,
        "schema": "aurora.glb_inject.v1",
        "input":  str(input_path),
        "output": str(output_path),
        "motion_kind": motion_kind,
        "duration_s": duration,
        "n_frames": n_frames,
        "target_node_index": target_node_index,
        "animation_path": anim_path,
        "size_bytes": len(out),
        "animations_now": anim_idx + 1,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="Aurora glTF animation injector")
    ap.add_argument("--input", required=True)
    ap.add_argument("--output", required=True)
    ap.add_argument("--motion-kind", default="rotate_y",
                    choices=["rotate_y", "bob", "breathe", "walk_humanoid",
                             "gear_train_split_rotate", "weights"])
    ap.add_argument("--duration", type=float, default=4.0)
    ap.add_argument("--target-node", type=int, default=None)
    ap.add_argument("--pretty", action="store_true")
    args = ap.parse_args()
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
    except (AttributeError, ValueError):
        pass

    res = inject(
        Path(args.input), Path(args.output),
        motion_kind=args.motion_kind, duration=args.duration,
        target_node_index=args.target_node,
    )
    if args.pretty and res.get("ok"):
        if "n_channels" in res:
            targets = res.get("bones_animated") or res.get("parts_animated") or []
            targets_str = ", ".join(targets[:4]) + (
                f" (+{len(targets) - 4} more)" if len(targets) > 4 else "")
            sys.stdout.write(
                f"OK · {res['motion_kind']} · {res['n_channels']} channels "
                f"[{targets_str}] over {res['duration_s']}s · "
                f"{res['animations_now']} animation(s) now in {res['output']}\n"
            )
        else:
            sys.stdout.write(
                f"OK · {res['motion_kind']} on node {res['target_node_index']} "
                f"({res['n_frames']} frames over {res['duration_s']}s) · "
                f"{res['animations_now']} animation(s) now in {res['output']}\n"
            )
    else:
        sys.stdout.write(json.dumps(res, indent=2, ensure_ascii=True) + "\n")
    return 0 if res.get("ok") else 1


if __name__ == "__main__":
    sys.exit(main())
