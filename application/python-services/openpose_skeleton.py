#!/usr/bin/env python
"""Canonical OpenPose (COCO-18) skeleton renderer for FLUX ControlNet pose
control — no preprocessor needed, we DRAW the target A-pose ourselves.

Why: the multi-view turnaround audit blocks realistic full-body humans because
FLUX (text-only) won't reliably hold a strict A-pose with arms clearly away from
the torso across 4 consistent views. Feeding a hard OpenPose skeleton to the
Shakker FLUX Union ControlNet (type "openpose") forces the pose → the reference
passes the audit → multi-view Hunyuan3D gets a clean, riggable human mesh.

The drawing matches controlnet_aux.draw_bodypose (COCO-18 keypoint order, the
canonical 18 limb colors, limbs as filled tapered polygons on black) so the
ControlNet recognises it as a genuine OpenPose map.

Schema: aurora.openpose_skeleton.v1
"""

from __future__ import annotations

import argparse
import math
import sys
from pathlib import Path

# COCO-18 keypoint order (controlnet_aux):
# 0 nose 1 neck 2 Rsho 3 Relb 4 Rwri 5 Lsho 6 Lelb 7 Lwri
# 8 Rhip 9 Rkne 10 Rank 11 Lhip 12 Lkne 13 Lank 14 Reye 15 Leye 16 Rear 17 Lear
LIMB_SEQ = [
    (1, 2), (1, 5), (2, 3), (3, 4), (5, 6), (6, 7), (1, 8), (8, 9),
    (9, 10), (1, 11), (11, 12), (12, 13), (1, 0), (0, 14), (14, 16),
    (0, 15), (15, 17),
]
COLORS = [
    (255, 0, 0), (255, 85, 0), (255, 170, 0), (255, 255, 0), (170, 255, 0),
    (85, 255, 0), (0, 255, 0), (0, 255, 85), (0, 255, 170), (0, 255, 255),
    (0, 170, 255), (0, 85, 255), (0, 0, 255), (85, 0, 255), (170, 0, 255),
    (255, 0, 255), (255, 0, 170), (255, 0, 85),
]

# Normalized wide A/T-pose keypoints (x right, y down) — full body, arms spread
# well out and up so the wrists/hands stay far from the hips with a clear gap on
# each side, and legs parted with a gap between the thighs. This is the rig-ready
# bind pose: limbs must NOT touch the body, otherwise the image-to-3D mesh fuses
# the hand into the hip (unriggable — the fused piece flies out when the arm
# lifts). `None` = keypoint absent (not drawn) for that view.
_APOSE_FRONT = {
    0: (0.500, 0.135), 1: (0.500, 0.210),
    2: (0.424, 0.232), 3: (0.336, 0.300), 4: (0.246, 0.362),
    5: (0.576, 0.232), 6: (0.664, 0.300), 7: (0.754, 0.362),
    8: (0.460, 0.500), 9: (0.440, 0.660), 10: (0.424, 0.808),
    11: (0.540, 0.500), 12: (0.560, 0.660), 13: (0.576, 0.808),
    14: (0.484, 0.126), 15: (0.516, 0.126), 16: (0.462, 0.138), 17: (0.538, 0.138),
}


def _mirror(pose: dict) -> dict:
    return {k: (None if v is None else (1.0 - v[0], v[1])) for k, v in pose.items()}


def _apose_back() -> dict:
    # Same limbs, mirrored, face keypoints removed (back of head).
    back = _mirror(_APOSE_FRONT)
    for face_kp in (0, 14, 15, 16, 17):
        back[face_kp] = None
    # neck stays; nose absent → the head limb (1->0) and face limbs drop out.
    return back


def _apose_profile(facing_left: bool) -> dict:
    # Side view: body on a near-vertical line, one near arm forward, far arm
    # tucked. Only the near-side limbs are drawn so it reads as a true profile.
    cx = 0.50
    fwd = -0.06 if facing_left else 0.06          # face/forward direction
    near = 0.045 if facing_left else -0.045       # near-arm offset
    pose = {
        0: (cx + fwd, 0.112), 1: (cx, 0.200),
        2: (cx + near, 0.225), 3: (cx + near + fwd * 0.8, 0.345), 4: (cx + near + fwd * 1.6, 0.455),
        5: None, 6: None, 7: None,                # far arm hidden behind body
        8: (cx + near * 0.5, 0.500), 9: (cx + near * 0.4 + fwd * 0.4, 0.650), 10: (cx + fwd * 0.9, 0.800),
        11: None, 12: None, 13: None,             # far leg mostly occluded
        14: (cx + fwd * 1.3, 0.126), 15: None,
        16: (cx + fwd * 0.2, 0.138), 17: None,
    }
    return pose


POSES = {
    "front": _APOSE_FRONT,
    "back": _apose_back(),
    "left": _apose_profile(facing_left=True),
    "right": _apose_profile(facing_left=False),
}


def render_pose(view: str, size: int = 1024, stickwidth: int = 4) -> "object":
    """Render the OpenPose A-pose skeleton for a view as a PIL RGB image
    (colored skeleton on black, controlnet_aux-compatible)."""
    from PIL import Image, ImageDraw  # noqa: WPS433

    pose = POSES.get(view)
    if pose is None:
        raise ValueError(f"unknown view {view!r}; expected one of {list(POSES)}")

    img = Image.new("RGB", (size, size), (0, 0, 0))
    draw = ImageDraw.Draw(img)
    sw = max(2, int(stickwidth * size / 256))

    def px(kp):
        v = pose.get(kp)
        return None if v is None else (v[0] * size, v[1] * size)

    # Limbs first (tapered polygon between joints, like draw_bodypose).
    for i, (a, b) in enumerate(LIMB_SEQ):
        pa, pb = px(a), px(b)
        if pa is None or pb is None:
            continue
        mx, my = (pa[0] + pb[0]) / 2, (pa[1] + pb[1]) / 2
        length = math.hypot(pa[0] - pb[0], pa[1] - pb[1])
        angle = math.degrees(math.atan2(pa[1] - pb[1], pa[0] - pb[0]))
        # Approximate the openpose ellipse-limb with a rotated rectangle polygon.
        poly = _ellipse_polygon(mx, my, length / 2, sw, angle)
        draw.polygon(poly, fill=COLORS[i % len(COLORS)])

    # Keypoints as filled circles.
    for kp in range(18):
        p = px(kp)
        if p is None:
            continue
        r = sw
        draw.ellipse([p[0] - r, p[1] - r, p[0] + r, p[1] + r], fill=COLORS[kp % len(COLORS)])

    return img


def _ellipse_polygon(cx, cy, half_len, half_w, angle_deg, steps=24):
    pts = []
    a = math.radians(angle_deg)
    ca, sa = math.cos(a), math.sin(a)
    for k in range(steps):
        t = 2 * math.pi * k / steps
        ex = half_len * math.cos(t)
        ey = half_w * math.sin(t)
        pts.append((cx + ex * ca - ey * sa, cy + ex * sa + ey * ca))
    return pts


def write_pose(view: str, dest: str | Path, size: int = 1024) -> str:
    img = render_pose(view, size=size)
    dest = Path(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    img.save(dest)
    return str(dest)


def main() -> int:
    ap = argparse.ArgumentParser(description="Render an OpenPose A-pose skeleton")
    ap.add_argument("--view", required=True, choices=list(POSES))
    ap.add_argument("--output", required=True)
    ap.add_argument("--size", type=int, default=1024)
    args = ap.parse_args()
    out = write_pose(args.view, args.output, size=args.size)
    sys.stdout.write(out + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
