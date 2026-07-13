"""Build a side-by-side comparison sheet: MIA (bottom) vs Rigify baseline (top).

Grid: 4 columns × 2 rows. Frames 0, 2, 4, 6 of an 8-frame walk cycle.
"""
from __future__ import annotations

import os
from PIL import Image, ImageDraw, ImageFont

BASE_DIR = "/home/juan/AuroraIA/scratchpad"
FRAMES = [0, 2, 4, 6]
COL_W, COL_H = 360, 540  # scaled down from 720x1080
OUT = os.path.join(BASE_DIR, "walk_comparison_baseline_vs_mia.png")


def load_and_resize(path: str) -> Image.Image:
    im = Image.open(path).convert("RGB")
    return im.resize((COL_W, COL_H), Image.LANCZOS)


TOP_LABEL = "BASELINE  (Rigify, DEF-driven, proxy 50k weights)"
BOT_LABEL = "MIA       (Make-It-Animatable, anatomical skinning, kept A-pose)"


def annotate(im: Image.Image, text: str) -> Image.Image:
    d = ImageDraw.Draw(im)
    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 14)
    except Exception:
        font = ImageFont.load_default()
    d.rectangle((0, 0, im.width, 20), fill=(0, 0, 0))
    d.text((6, 3), text, fill=(255, 255, 255), font=font)
    return im


def main() -> None:
    header_h = 28
    total_w = COL_W * len(FRAMES)
    total_h = header_h + COL_H * 2 + header_h  # 2 rows + top header + row-title
    canvas = Image.new("RGB", (total_w, total_h + 20), (240, 240, 240))
    d = ImageDraw.Draw(canvas)
    try:
        font_big = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 16)
        font_lbl = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 12)
    except Exception:
        font_big = ImageFont.load_default()
        font_lbl = ImageFont.load_default()

    # Top strip: baseline row title
    d.rectangle((0, 0, total_w, header_h), fill=(160, 30, 30))
    d.text((10, 6), TOP_LABEL + "  —  same 45° arm swing, same walk keyframes", fill=(255, 255, 255), font=font_big)

    for col, fi in enumerate(FRAMES):
        path = os.path.join(BASE_DIR, f"walk_baseline/baseline_walk_frame_{fi:02d}.png")
        if not os.path.isfile(path):
            print(f"MISSING {path}")
            continue
        im = load_and_resize(path)
        annotate(im, f"frame {fi}")
        canvas.paste(im, (col * COL_W, header_h))

    # Middle strip: MIA row title
    y_mid = header_h + COL_H
    d.rectangle((0, y_mid, total_w, y_mid + header_h), fill=(30, 110, 60))
    d.text((10, y_mid + 6), BOT_LABEL + "  —  same 45° arm swing, skin='keep' (no re-bind)", fill=(255, 255, 255), font=font_big)

    for col, fi in enumerate(FRAMES):
        path = os.path.join(BASE_DIR, f"walk_mia_apose/mia_apose_walk_frame_{fi:02d}.png")
        if not os.path.isfile(path):
            print(f"MISSING {path}")
            continue
        im = load_and_resize(path)
        annotate(im, f"frame {fi}")
        canvas.paste(im, (col * COL_W, y_mid + header_h))

    canvas.save(OUT, "PNG", optimize=True)
    print(f"WROTE {OUT}  size={canvas.size}")


if __name__ == "__main__":
    main()
