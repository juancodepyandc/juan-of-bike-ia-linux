"""Aurora critic: scores a generated pack and proposes prompt refinements.

Inputs: a pack dir containing hero.png, GLB, mesh_meta.json, profile.json.
Outputs: critique.json with flags, score [0..1], suggested_prompt (str or None).

Score weights:
    mesh density        25 %
    texture coverage    25 %
    exposure & contrast 20 %
    silhouette coverage 15 %
    classification confidence 15 %

A score below `min_score` (default 0.65) triggers a prompt refinement suggestion.
The refiner is keyword-based: it appends hints addressing the specific flags.
"""
from __future__ import annotations

import argparse
import json
import logging
import re
import sys
from pathlib import Path

from PIL import Image
import numpy as np


def _mesh_sanity(glb_path: Path) -> dict:
    """Detect shape pathologies: extreme aspect ratio (plank/needle), cubical
    bbox (box), too few disconnected components (good) or many tiny floaters
    (artifacts), and a "blockiness" proxy via face-area variance.
    """
    try:
        import trimesh
    except ImportError:
        return {"available": False}
    try:
        scene = trimesh.load(str(glb_path), force=None)
        if isinstance(scene, trimesh.Scene):
            geos = list(scene.geometry.values())
            mesh = trimesh.util.concatenate(geos) if len(geos) > 1 else geos[0]
        else:
            mesh = scene
        bbox = mesh.bounding_box.extents
        dims = sorted(float(d) for d in bbox)
        smallest, mid, largest = dims
        aspect = largest / max(smallest, 1e-6)
        # Analyse purement geometrique: on neutralise la texture avant le
        # decoupage, sinon `split()` la recopie pour CHAQUE composante.
        try:
            from trimesh.visual import ColorVisuals as _CV
            mesh.visual = _CV(mesh=mesh)
        except Exception:
            pass
        components = mesh.split(only_watertight=False)
        main_face_count = max((len(c.faces) for c in components), default=0)
        floaters = sum(1 for c in components if len(c.faces) < main_face_count * 0.005 and len(c.faces) > 0)
        face_areas = mesh.area_faces if hasattr(mesh, "area_faces") else np.array([])
        if face_areas.size > 0:
            ratio_p95_p50 = float(np.percentile(face_areas, 95) / max(np.percentile(face_areas, 50), 1e-9))
        else:
            ratio_p95_p50 = 0.0
        return {
            "available": True,
            "aspect_ratio": round(aspect, 2),
            "bbox": [round(d, 3) for d in dims],
            "components": len(components),
            "floaters": floaters,
            "face_size_p95_p50": round(ratio_p95_p50, 2),
        }
    except Exception as e:
        return {"available": False, "error": str(e)[:200]}

log = logging.getLogger("critic")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")


def _texture_coverage(img_path: Path, k: int = 8) -> float:
    """Estimate texture coverage via per-channel std + unique color count."""
    img = Image.open(img_path).convert("RGB").resize((128, 128))
    arr = np.asarray(img, dtype=np.float32) / 255.0
    std_mean = float(arr.reshape(-1, 3).std(axis=0).mean())
    flat = arr.reshape(-1, 3)
    quant = (flat * 32).astype(np.int32)
    keys = quant[:, 0] * 1024 + quant[:, 1] * 32 + quant[:, 2]
    unique = float(len(np.unique(keys))) / (32 * 32 * 32)
    score = min(1.0, std_mean * 4 + unique * 6)
    return round(score, 3)


def _exposure(img_path: Path) -> dict[str, float]:
    img = Image.open(img_path).convert("L").resize((128, 128))
    arr = np.asarray(img, dtype=np.float32) / 255.0
    mean = float(arr.mean())
    std = float(arr.std())
    return {"mean": round(mean, 3), "std": round(std, 3)}


def _silhouette_ratio(img_path: Path, tol: int = 40) -> float:
    """Fraction of foreground pixels. Auto-detects bg from corner sampling
    instead of hard-coding studio_clean grey: moods like dramatic_night,
    cyberpunk, etc. use different world backgrounds and the old hard-coded
    (217,217,224) caused 100% silhouette ratio everywhere except studio.
    """
    img = Image.open(img_path).convert("RGB").resize((256, 256))
    arr = np.asarray(img, dtype=np.int32)
    corner_samples = np.concatenate([
        arr[:8, :8].reshape(-1, 3),
        arr[:8, -8:].reshape(-1, 3),
        arr[-8:, :8].reshape(-1, 3),
        arr[-8:, -8:].reshape(-1, 3),
    ])
    bg = np.median(corner_samples, axis=0).astype(np.int32)
    diff = np.abs(arr - bg).sum(axis=-1)
    fg = (diff > tol).sum()
    return round(float(fg) / (256 * 256), 3)


def evaluate(pack_dir: Path, min_score: float = 0.65) -> dict:
    hero = pack_dir / "hero.png"
    glb_meta_p = pack_dir / "mesh_meta.json"
    profile_p = pack_dir / "profile.json"

    flags: list[str] = []
    sub_scores: dict[str, float] = {}

    mesh_density = 0.0
    if glb_meta_p.exists():
        mm = json.loads(glb_meta_p.read_text())
        faces = mm.get("faces", 0)
        mesh_density = min(1.0, faces / 400_000.0)
        if faces < 50_000:
            flags.append("low_mesh_density")
    else:
        flags.append("missing_mesh_meta")
    sub_scores["mesh_density"] = round(mesh_density, 3)

    texture = 0.0
    exposure = {"mean": 0.5, "std": 0.0}
    silhouette = 0.0
    if hero.exists():
        texture = _texture_coverage(hero)
        if texture < 0.35:
            flags.append("flat_texture")
        exposure = _exposure(hero)
        if exposure["mean"] < 0.18:
            flags.append("underexposed")
        elif exposure["mean"] > 0.82:
            flags.append("overexposed")
        if exposure["std"] < 0.08:
            flags.append("low_contrast")
        silhouette = _silhouette_ratio(hero)
        if silhouette < 0.08:
            flags.append("subject_too_small_or_missing")
        elif silhouette > 0.85:
            flags.append("subject_fills_frame")
    else:
        flags.append("missing_hero_render")
    sub_scores["texture_coverage"] = texture
    sub_scores["exposure_quality"] = round(min(1.0, exposure["std"] * 3 + (1 - abs(0.5 - exposure["mean"]) * 1.4)), 3)
    sub_scores["silhouette"] = round(min(1.0, 1.0 if 0.18 <= silhouette <= 0.65 else max(0.0, 1.0 - abs(silhouette - 0.4) * 1.8)), 3)

    confidence = 0.5
    profile: dict = {}
    if profile_p.exists():
        profile = json.loads(profile_p.read_text())
        confidence = float(profile.get("confidence", 0.5))
    sub_scores["classifier_confidence"] = confidence

    glb_candidates = sorted(pack_dir.glob("pbr_*_proc.glb"))
    shape = {"available": False}
    if glb_candidates:
        shape = _mesh_sanity(glb_candidates[0])
        if shape.get("available"):
            aspect = shape.get("aspect_ratio", 1.0)
            if aspect > 8.0:
                flags.append("shape_plank_aspect")
            elif aspect < 1.15:
                flags.append("shape_cubical")
            if shape.get("floaters", 0) > 3:
                flags.append("artifacts_floaters")
            if shape.get("components", 1) > 8:
                flags.append("mesh_disconnected")
            if shape.get("face_size_p95_p50", 0) > 25:
                flags.append("face_variance_high_possibly_blocky")

    score = (
        sub_scores["mesh_density"] * 0.25
        + sub_scores["texture_coverage"] * 0.25
        + sub_scores["exposure_quality"] * 0.20
        + sub_scores["silhouette"] * 0.15
        + sub_scores["classifier_confidence"] * 0.15
    )
    score = round(score, 3)

    suggested_prompt = refine_prompt(profile, flags) if score < min_score else None

    critique = {
        "score": score,
        "min_score": min_score,
        "passed": score >= min_score,
        "flags": flags,
        "sub_scores": sub_scores,
        "exposure": exposure,
        "silhouette": silhouette,
        "shape": shape,
        "suggested_prompt": suggested_prompt,
    }
    (pack_dir / "critique.json").write_text(json.dumps(critique, indent=2, ensure_ascii=False))
    return critique


def refine_prompt(profile: dict, flags: list[str]) -> str:
    prompt = profile.get("prompt_original", "")
    additions: list[str] = []
    if "low_mesh_density" in flags:
        additions.append("high detail surface, intricate geometry")
    if "flat_texture" in flags:
        additions.append("rich varied color palette, distinct material zones, surface wear")
    if "underexposed" in flags:
        additions.append("well-lit, bright key light, no harsh shadows")
    if "overexposed" in flags:
        additions.append("balanced exposure, no blown highlights, dramatic shadows")
    if "low_contrast" in flags:
        additions.append("strong contrast, deep shadows, bright highlights")
    if "subject_too_small_or_missing" in flags:
        additions.append("close-up, fills frame, centered, isolated on plain background")
    if "subject_fills_frame" in flags:
        additions.append("medium shot, full subject visible, room around subject")
    if "shape_plank_aspect" in flags:
        additions.append("balanced volumetric form, not flat, three-dimensional silhouette")
    if "shape_cubical" in flags:
        additions.append("organic varied silhouette, not boxy, distinct features")
    if "artifacts_floaters" in flags:
        additions.append("single connected subject, no loose debris")
    if "mesh_disconnected" in flags:
        additions.append("single coherent subject, fully connected")
    if "face_variance_high_possibly_blocky" in flags:
        additions.append("smooth detailed surface, no flat planes")
    if not additions:
        additions.append("more photorealistic, higher fidelity")
    cleaned = re.sub(r",\s*,", ",", prompt).strip(", ")
    return cleaned + ", " + ", ".join(additions)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("pack", type=Path)
    ap.add_argument("--min-score", type=float, default=0.65)
    args = ap.parse_args()
    critique = evaluate(args.pack, args.min_score)
    print(json.dumps(critique, indent=2, ensure_ascii=False))
    return 0 if critique["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
