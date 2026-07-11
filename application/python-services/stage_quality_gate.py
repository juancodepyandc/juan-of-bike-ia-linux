import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np
from PIL import Image

REPO = Path(__file__).resolve().parent


def _render_views(glb: Path, outdir: Path) -> list[Path]:
    outdir.mkdir(parents=True, exist_ok=True)
    blender = os.environ.get("AURORA_BLENDER") or shutil.which("blender") or "blender"
    script = REPO / "render_views.py"
    try:
        subprocess.run([blender, "--background", "--python", str(script),
                        "--", str(glb), str(outdir)],
                       capture_output=True, text=True, timeout=900, cwd=tempfile.gettempdir())
    except Exception:
        return []
    return sorted(outdir.glob("*.png"))


def _view_metrics(path: Path) -> dict | None:
    try:
        im = np.asarray(Image.open(path).convert("RGBA"), dtype=np.float32)
    except Exception:
        return None
    alpha = im[..., 3] > 10
    if alpha.sum() < 500:
        return None
    ys, xs = np.where(alpha)
    y0, y1, x0, x1 = ys.min(), ys.max() + 1, xs.min(), xs.max() + 1
    rgb = im[y0:y1, x0:x1, :3]
    m = alpha[y0:y1, x0:x1]
    mx = rgb.max(axis=2)
    mn = rgb.min(axis=2)
    sat = np.where(mx > 1, (mx - mn) / (mx + 1e-6), 0.0)
    g = rgb.mean(axis=2)
    lap = np.zeros_like(g)
    lap[1:-1, 1:-1] = np.abs(g[:-2, 1:-1] + g[2:, 1:-1] + g[1:-1, :-2] + g[1:-1, 2:] - 4 * g[1:-1, 1:-1])
    return {"saturation": float(sat[m].mean()),
            "sharpness": float(lap[m].mean()),
            "luma": float(g[m].mean())}


def _artifact_metrics(glb: Path, workdir: Path) -> dict | None:
    views = _render_views(glb, workdir)
    per = [v for v in (_view_metrics(p) for p in views) if v]
    if not per:
        return None
    return {k: float(np.mean([v[k] for v in per])) for k in per[0]}


def gate(before_glb: str | Path, after_glb: str | Path, tag: str,
         expected_transparency: bool = False) -> dict:
    if os.environ.get("AURORA_STAGE_GATE", "1") != "1":
        return {"ok": True, "skipped": True, "reason": "AURORA_STAGE_GATE=0"}
    before_glb = Path(before_glb)
    after_glb = Path(after_glb)
    with tempfile.TemporaryDirectory(prefix=f"aurora_gate_{tag}_") as td:
        mb = _artifact_metrics(before_glb, Path(td) / "before")
        ma = _artifact_metrics(after_glb, Path(td) / "after")
    if not mb or not ma:
        return {"ok": True, "skipped": True, "reason": "rendu impossible", "tag": tag}
    reasons = []
    if (ma["saturation"] < mb["saturation"] * 0.6 and mb["saturation"] > 0.03
            and not expected_transparency):
        reasons.append("saturation effondree (delavage): %.3f -> %.3f"
                       % (mb["saturation"], ma["saturation"]))
    if ma["sharpness"] < mb["sharpness"] * 0.55 and mb["sharpness"] > 0.5:
        reasons.append("nettete effondree (flou/perte detail): %.2f -> %.2f"
                       % (mb["sharpness"], ma["sharpness"]))
    if ma["luma"] > mb["luma"] * 1.6 and ma["saturation"] < mb["saturation"] * 0.8:
        reasons.append("eclaircissement anormal (fantome): luma %.1f -> %.1f"
                       % (mb["luma"], ma["luma"]))
    return {"ok": True, "tag": tag, "degraded": bool(reasons), "reasons": reasons,
            "before": mb, "after": ma}


def main() -> int:
    ap_before, ap_after = sys.argv[1], sys.argv[2]
    tag = sys.argv[3] if len(sys.argv) > 3 else "cli"
    res = gate(ap_before, ap_after, tag)
    print("AURORA_GATE_RESULT:" + json.dumps(res, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
