#!/usr/bin/env python3
"""Render-in-the-loop visual audit for Aurora Code.

Runs the CDP helper across the canonical WS9 breakpoints, then enriches the
computed-style report with pixel-derived contrast samples from each screenshot.
Outputs the `aurora.code.visual-render-audit/1` JSON schema consumed by the app.
"""

from __future__ import annotations

import json
import math
import subprocess
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
CDP_HELPER = ROOT / "python-services" / "aurora_code" / "cdp_drive.mjs"


def _luminance(rgb: tuple[int, int, int]) -> float:
  def channel(value: int) -> float:
    scaled = value / 255.0
    return scaled / 12.92 if scaled <= 0.03928 else ((scaled + 0.055) / 1.055) ** 2.4

  r, g, b = rgb
  return 0.2126 * channel(r) + 0.7152 * channel(g) + 0.0722 * channel(b)


def _contrast(a: float, b: float) -> float:
  hi = max(a, b)
  lo = min(a, b)
  return (hi + 0.05) / (lo + 0.05)


def _percentile(values: list[float], ratio: float) -> float:
  if not values:
    return 0.0
  index = max(0, min(len(values) - 1, round((len(values) - 1) * ratio)))
  return values[index]


def _pixel_contrast_samples(viewport: dict[str, Any]) -> list[dict[str, Any]]:
  try:
    from PIL import Image
  except Exception:
    return []

  screenshot_path = viewport.get("screenshotPath")
  if not screenshot_path:
    return []

  path = Path(str(screenshot_path))
  if not path.exists():
    return []

  try:
    image = Image.open(path).convert("RGB")
  except Exception:
    return []

  width, height = image.size
  out: list[dict[str, Any]] = []
  for sample in (viewport.get("contrastSamples") or [])[:24]:
    rect = sample.get("rect") or {}
    x = max(0, min(width - 1, int(rect.get("x", 0))))
    y = max(0, min(height - 1, int(rect.get("y", 0))))
    w = max(1, min(width - x, int(rect.get("width", 1))))
    h = max(1, min(height - y, int(rect.get("height", 1))))
    crop = image.crop((x, y, x + w, y + h))
    pixels = list(crop.getdata())
    if len(pixels) > 5000:
      step = max(1, len(pixels) // 5000)
      pixels = pixels[::step]

    luminances = sorted(_luminance(pixel) for pixel in pixels)
    low = _percentile(luminances, 0.08)
    high = _percentile(luminances, 0.92)
    ratio = _contrast(low, high)
    if not math.isfinite(ratio):
      continue
    out.append({
      "ratio": round(ratio, 2),
      "source": "pixel",
      "viewport": viewport.get("viewport") or f"{width}x{height}",
      "label": sample.get("label") or "text",
    })
  return out


def run_audit(url: str, out_dir: Path, wait_ms: int = 2500) -> dict[str, Any]:
  out_dir.mkdir(parents=True, exist_ok=True)
  proc = subprocess.run(
    ["node", str(CDP_HELPER), "audit", url, str(out_dir), str(wait_ms)],
    check=False,
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
    text=True,
    timeout=max(20, wait_ms / 1000 * 8 + 30),
  )
  if proc.returncode != 0:
    return {
      "schemaVersion": "aurora.code.visual-render-audit/1",
      "url": url,
      "viewports": [],
      "error": (proc.stderr or proc.stdout or f"cdp rc={proc.returncode}")[-2000:],
    }

  try:
    report = json.loads(proc.stdout)
  except Exception as exc:
    return {
      "schemaVersion": "aurora.code.visual-render-audit/1",
      "url": url,
      "viewports": [],
      "error": f"invalid cdp json: {exc}",
    }

  for viewport in report.get("viewports") or []:
    pixel_samples = _pixel_contrast_samples(viewport)
    if pixel_samples:
      viewport["contrastSamples"] = pixel_samples + list(viewport.get("contrastSamples") or [])

  return report


def main(argv: list[str]) -> int:
  if len(argv) < 3:
    print("usage: visual_render_audit.py <url> <out_dir> [wait_ms]", file=sys.stderr)
    return 2
  url = argv[1]
  out_dir = Path(argv[2])
  wait_ms = int(argv[3]) if len(argv) > 3 else 2500
  print(json.dumps(run_audit(url, out_dir, wait_ms), ensure_ascii=False))
  return 0


if __name__ == "__main__":
  raise SystemExit(main(sys.argv))
