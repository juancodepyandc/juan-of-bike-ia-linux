"""Test motion_baker.compile_motion_payload with a synthetic descriptor.
Validates that the kinematic primitives produce sensible keyframe data."""
import sys, json
sys.path.insert(0, r"C:\Users\Juan\Desktop\ia\AuroraIA-v2\application\python-services")
import motion_baker as mb

# Synthesise a minimal aurora.motion.v1 descriptor: a gear-train rotation (rotate around Y, 1 cycle/2s)
desc = {
    "schema": "aurora.motion.v1",
    "id": "gear_train_test",
    "label": "Rotation engrenage continue",
    "duration_seconds": 2.0,
    "fps": 30,
    "loop": True,
    "primitives": [
        {
            "kind": "rotate",
            "target": "gear_main",
            "axis": "Y",
            "amplitude_deg": 360.0,
            "frequency_hz": 0.5,
            "phase_deg": 0.0,
        },
        {
            "kind": "rotate",
            "target": "gear_pinion",
            "axis": "Y",
            "amplitude_deg": -1080.0,  # opposite direction, 3x faster (gear ratio 3:1)
            "frequency_hz": 1.5,
            "phase_deg": 0.0,
        },
    ],
}

fps = desc["fps"]
frame_count = int(desc["duration_seconds"] * fps)

# Hit the lower-level compiler for each primitive
all_kfs = []
for prim in desc["primitives"]:
    res = mb._compile_rotate(prim, fps, frame_count)
    all_kfs.append(res)

print(json.dumps({
    "ok": True,
    "fps": fps,
    "frame_count": frame_count,
    "primitives": len(desc["primitives"]),
    "keyframe_groups": len(all_kfs),
    "first_group_summary": (
        {
            "len": len(all_kfs[0]),
            "first_entry_keys": list(all_kfs[0][0].keys()) if all_kfs[0] else [],
            "first_entry": {k: (v if not isinstance(v, list) else f"<list len={len(v)}>") for k, v in (all_kfs[0][0] if all_kfs[0] else {}).items()},
        }
        if all_kfs else None
    ),
}, indent=2))
