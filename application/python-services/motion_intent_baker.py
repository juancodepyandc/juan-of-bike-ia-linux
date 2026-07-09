#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""motion_intent_baker -- consume aurora.motion-intent.v1 and bake the
appropriate animation onto a GLB.

This is a THIN orchestrator. The bpy-side work lives in
motion_intent_bpy_runner.py (so the runner can keep its own docstrings
without breaking host-side parsing).

Eight categories handled (see the runner for details):
  - led_emission     -> emission FCurve animation
  - fan_pwm          -> rotation_euler keyframes
  - oled_screen      -> base color FCurves on screen-tagged material
  - creature_organic -> Rigify limb gait/breathing; locomotion refuses fake bob fallback
  - mechanical_simple-> single-DoF keyframes
  - rigid_static     -> NO animation (explicit clear)
  - fluid_flow       -> procedural water surface + morph-target ripple loop
  - gas_volume       -> crossed smoke cards + billow morphs + TRS rise loop

CLI:
    python motion_intent_baker.py --intent intent.json --input mesh.glb \
        --output mesh_anim.glb [--fps 24] [--blender PATH]

Returns: JSON on stdout summarising what was baked.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


BLENDER_CANDIDATES = [
    r"C:\Program Files\Blender Foundation\Blender 5.1\blender.exe",
    r"C:\Program Files\Blender Foundation\Blender 5.0\blender.exe",
    r"C:\Program Files\Blender Foundation\Blender 4.4\blender.exe",
    r"C:\Program Files\Blender Foundation\Blender 4.3\blender.exe",
    "/usr/bin/blender",
    "blender",
]


def _find_blender() -> Optional[str]:
    for cand in BLENDER_CANDIDATES:
        if os.path.isfile(cand):
            return cand
        which = shutil.which(cand)
        if which:
            return which
    return None


def _validate_intent(intent: Dict[str, Any]) -> None:
    if not isinstance(intent, dict):
        raise ValueError("intent must be a dict")
    if intent.get("schema") != "aurora.motion-intent.v1":
        raise ValueError("expected schema=aurora.motion-intent.v1, got %r"
                         % intent.get("schema"))
    cat = intent.get("category")
    valid = {"led_emission", "fan_pwm", "oled_screen",
             "creature_organic", "mechanical_simple", "rigid_static",
             "fluid_flow", "gas_volume"}
    if cat not in valid:
        raise ValueError("unknown category: %r" % cat)


def _generate_oled_png_sequence(intent: Dict[str, Any], out_dir: str,
                                frame_count: int = 60) -> Optional[Dict[str, Any]]:
    """iter5.B: render a PNG sequence for an OLED screen using Pillow.

    `intent.screen_anim.content_type` (or legacy `content_kind`) drives the look:
      - text_scroll    : monospace text scrolling horizontally
      - icon_rotation  : rotating mock icons (CPU/RAM/FAN)
      - system_stats   : CPU% bar + temp text + ascii spark
      - mixed          : alternates text + icon every N frames
      - logo_loop      : pulsing logo (legacy alias)
      - temperature_dash, icon_carousel : legacy aliases

    Returns dict with png_count and dir, or None if Pillow is unavailable.
    """
    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError:
        return None

    s = intent.get("screen_anim") or {}
    content_type = s.get("content_type") or s.get("content_kind") or "text_scroll"
    res = s.get("resolution_px") or [256, 128]
    if not isinstance(res, (list, tuple)) or len(res) != 2:
        res = [256, 128]
    w, h = int(res[0]), int(res[1])
    # iter21 SEC: clamp degenerate resolutions. The classifier sometimes
    # returns symbolic [2,1] (aspect ratio, not pixels) which crashes Pillow
    # rectangle/text drawing once h//3 or w-16 go negative. Anything below
    # 64x32 is too small for legible content; force a sensible default.
    if w < 64 or h < 32:
        w, h = 256, 128
    text = s.get("text") or "AURORA AURORA AURORA"

    os.makedirs(out_dir, exist_ok=True)
    # Try to grab a monospace font; fallback to Pillow default
    font = None
    for font_name in ("consola.ttf", "DejaVuSansMono.ttf", "cour.ttf"):
        try:
            font = ImageFont.truetype(font_name, max(12, h // 4))
            break
        except (OSError, IOError):
            continue
    if font is None:
        font = ImageFont.load_default()

    # Aliases -> canonical
    canonical = content_type
    if canonical in ("logo_loop", "icon_carousel"):
        canonical = "icon_rotation"
    if canonical in ("temperature_dash",):
        canonical = "system_stats"
    if canonical in ("brand", "brand_logo", "logo"):
        canonical = "brand_logo"
    if canonical not in ("text_scroll", "icon_rotation", "system_stats",
                         "mixed", "brand_logo"):
        canonical = "text_scroll"

    bg = (0, 8, 16, 255)        # near-black with very faint blue
    fg = (32, 240, 255, 255)    # cyan OLED
    accent = (255, 180, 32, 255)  # amber for warnings

    # Build a wide scroll text once
    scroll_text = text + "  ·  X870E HERO  ·  65C  ·  60% LOAD  ·  3200RPM  ·  "
    scroll_bbox = font.getbbox(scroll_text)
    text_w = scroll_bbox[2] - scroll_bbox[0]
    if text_w == 0:
        text_w = w

    saved = []
    for i in range(frame_count):
        img = Image.new("RGB", (w, h), bg[:3])
        draw = ImageDraw.Draw(img)
        t = i / float(frame_count)

        if canonical == "text_scroll":
            offset = int((-t * text_w) % text_w)
            # Draw the scrolling text twice so it wraps seamlessly
            draw.text((-offset, h // 4), scroll_text, font=font, fill=fg[:3])
            draw.text((-offset + text_w, h // 4), scroll_text, font=font, fill=fg[:3])
        elif canonical == "icon_rotation":
            icons = [("CPU", "65C"), ("RAM", "60%"), ("FAN", "3200"), ("GPU", "70C")]
            icon_idx = i % len(icons)
            label, val = icons[icon_idx]
            draw.text((w // 8, h // 8), label, font=font, fill=accent[:3])
            big_font = font
            try:
                big_font = ImageFont.truetype(font.path if hasattr(font, "path") else "consola.ttf",
                                              max(20, h // 2))
            except Exception:
                big_font = font
            draw.text((w // 8, h // 2), val, font=big_font, fill=fg[:3])
        elif canonical == "system_stats":
            cpu = 35 + int(25 * (math.sin(t * 6.28) + 1) / 2.0)
            temp = 55 + int(15 * (math.sin(t * 6.28 * 0.5) + 1) / 2.0)
            bar_w = int((w - 16) * cpu / 100.0)
            draw.rectangle((8, h // 3, 8 + bar_w, h // 3 + h // 8), fill=fg[:3])
            draw.rectangle((8, h // 3, w - 8, h // 3 + h // 8), outline=fg[:3])
            draw.text((8, 4), "CPU %3d%%" % cpu, font=font, fill=fg[:3])
            draw.text((w // 2, 4), "T %2dC" % temp, font=font, fill=accent[:3])
            # Mini sparkline
            spark = "_..-+oOo+-..__..-+oOo+-..__..-+"
            offset = int((t * len(spark)) % len(spark))
            draw.text((8, h - h // 3),
                      (spark + spark)[offset:offset + 16],
                      font=font, fill=fg[:3])
        elif canonical == "brand_logo":
            # Pulsing brand logo with rotating accent ring — recognisable
            # branding instead of generic system_stats. Uses the screen text
            # the orchestrator deduced from the prompt (e.g. "X870E HERO").
            big_font = font
            try:
                big_font = ImageFont.truetype(
                    font.path if hasattr(font, "path") else "consola.ttf",
                    max(20, h // 2),
                )
            except Exception:
                big_font = font
            bbox = big_font.getbbox(text)
            tw = bbox[2] - bbox[0]
            th = bbox[3] - bbox[1]
            # Pulse: brightness modulates (sin) so the logo "breathes"
            pulse = 0.55 + 0.45 * (math.sin(t * 6.28) + 1) / 2.0
            logo_color = (int(fg[0] * pulse), int(fg[1] * pulse),
                          int(fg[2] * pulse))
            # Center the brand text
            tx = max(0, (w - tw) // 2)
            ty = max(0, (h - th) // 2 - 4)
            draw.text((tx, ty), text, font=big_font, fill=logo_color)
            # Rotating accent dot around centre — confirms the loop animates
            cx, cy = w // 2, h - h // 6
            r = h // 8
            ang = t * 6.28
            dx = int(r * math.cos(ang))
            dy = int(r * math.sin(ang))
            draw.ellipse((cx + dx - 3, cy + dy - 3,
                          cx + dx + 3, cy + dy + 3), fill=accent[:3])
        elif canonical == "mixed":
            # Alternate every quarter of the loop
            seg = int(t * 4) % 4
            if seg == 0:
                offset = int((-t * text_w) % text_w)
                draw.text((-offset, h // 4), scroll_text, font=font, fill=fg[:3])
                draw.text((-offset + text_w, h // 4), scroll_text, font=font, fill=fg[:3])
            elif seg == 1:
                draw.text((w // 8, h // 4), "CPU", font=font, fill=accent[:3])
                draw.text((w // 8, h // 2), "65C", font=font, fill=fg[:3])
            elif seg == 2:
                cpu = 35 + int(25 * (math.sin(t * 6.28) + 1) / 2.0)
                bar_w = int((w - 16) * cpu / 100.0)
                draw.rectangle((8, h // 3, 8 + bar_w, h // 3 + h // 8), fill=fg[:3])
                draw.text((8, 4), "CPU %3d%%" % cpu, font=font, fill=fg[:3])
            else:
                draw.text((w // 4, h // 3), "AURORA", font=font, fill=fg[:3])
        else:
            draw.text((w // 4, h // 4), "AURORA", font=font, fill=fg[:3])

        path = os.path.join(out_dir, "frame_%04d.png" % i)
        img.save(path)
        saved.append(path)

    # iter5.B v2: stitch frames into a single horizontal flipbook atlas so
    # the Blender side can wire it onto a Mapping-node UV pipeline that
    # round-trips through glTF (image_user.frame_offset is NOT serialisable
    # by the glTF exporter, but a single PNG with animated UV scroll IS).
    atlas_path = os.path.join(out_dir, "_atlas.png")
    try:
        atlas = Image.new("RGB", (w * len(saved), h), bg[:3])
        for i, p in enumerate(saved):
            with Image.open(p) as im:
                atlas.paste(im, (i * w, 0))
        atlas.save(atlas_path)
        with open(os.path.join(out_dir, "_atlas.json"), "w", encoding="utf-8") as f:
            json.dump({"frame_count": len(saved), "frame_w": w, "frame_h": h}, f)
    except Exception:
        atlas_path = None

    return {
        "dir": out_dir,
        "png_count": len(saved),
        "content_type": canonical,
        "resolution_px": [w, h],
        "first_kb": round(os.path.getsize(saved[0]) / 1024.0, 1) if saved else 0,
        "atlas_path": atlas_path,
        "atlas_kb": round(os.path.getsize(atlas_path) / 1024.0, 1) if atlas_path and os.path.isfile(atlas_path) else 0,
    }


def bake_intent(intent_path: str, input_glb: str, output_glb: str,
                fps: int = 24, blender_path: Optional[str] = None) -> Dict[str, Any]:
    bpath = blender_path or _find_blender()
    if not bpath:
        # Pure-Python no-op fallback for CI boxes without Blender.
        if os.path.abspath(input_glb) != os.path.abspath(output_glb):
            shutil.copyfile(input_glb, output_glb)
        return {
            "ok": False,
            "fallback": "blender_not_found",
            "intent_path": intent_path,
            "input_glb": input_glb,
            "output_glb": output_glb,
            "note": "Blender 5.0+ recommended; copied input to output as no-op.",
        }

    runner = Path(__file__).parent / "motion_intent_bpy_runner.py"
    if not runner.is_file():
        return {"ok": False, "error": "motion_intent_bpy_runner.py missing"}

    # iter5.B: if intent is oled_screen, generate PNG sequence first (host Pillow)
    png_seq_dir = ""
    png_seq_info: Optional[Dict[str, Any]] = None
    try:
        with open(intent_path, "r", encoding="utf-8") as f:
            intent_payload = json.load(f)
    except Exception:
        intent_payload = {}
    if isinstance(intent_payload, dict) and intent_payload.get("category") == "oled_screen":
        seq_root = os.path.join(
            os.path.dirname(os.path.abspath(output_glb)) or tempfile.gettempdir(),
            "oled_seq_" + os.path.basename(output_glb).replace(".glb", ""),
        )
        png_seq_info = _generate_oled_png_sequence(intent_payload, seq_root, frame_count=60)
        if png_seq_info:
            png_seq_dir = png_seq_info["dir"]

    cmd = [bpath, "--background", "--python", str(runner), "--",
           "--intent", intent_path, "--input", input_glb,
           "--output", output_glb, "--fps", str(fps)]
    env = os.environ.copy()
    if png_seq_dir:
        env["AURORA_OLED_PNG_SEQ_DIR"] = png_seq_dir
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=600, env=env)
    out = proc.stdout

    parsed: Dict[str, Any] = {"ok": False}
    if "AURORA_RESULT_BEGIN" in out and "AURORA_RESULT_END" in out:
        seg = out.split("AURORA_RESULT_BEGIN", 1)[1] \
                 .split("AURORA_RESULT_END", 1)[0].strip()
        try:
            parsed = json.loads(seg)
            parsed["ok"] = "error" not in parsed
        except json.JSONDecodeError as exc:
            parsed = {"ok": False, "error": "result parse failed: %s" % exc,
                      "raw": seg[:400]}
    else:
        parsed = {"ok": False,
                  "error": "bpy runner did not emit a result block",
                  "stderr_tail": (proc.stderr or "")[-400:]}

    parsed["returncode"] = proc.returncode
    parsed["blender"] = bpath
    if png_seq_info:
        parsed["png_sequence"] = png_seq_info
    return parsed


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--intent", required=True)
    ap.add_argument("--input", required=True)
    ap.add_argument("--output", required=True)
    ap.add_argument("--fps", type=int, default=24)
    ap.add_argument("--blender", default=None)
    args = ap.parse_args()

    with open(args.intent, "r", encoding="utf-8") as f:
        intent = json.load(f)
    _validate_intent(intent)

    result = bake_intent(args.intent, args.input, args.output,
                         args.fps, args.blender)
    print(json.dumps(result, indent=2))
    return 0 if result.get("ok") else 2


if __name__ == "__main__":
    sys.exit(main())
