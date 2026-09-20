#!/usr/bin/env python3
"""Measure real image package production, or explicitly test simulated packaging.

Dimensions, category, files and measured metadata are checked. Subject fidelity,
photorealism, OCR, anatomy and visual consistency require separate evaluation.
"""

import argparse
from datetime import datetime, timezone
import json
import math
import statistics
import time
from pathlib import Path
from PIL import Image

from image_module_engine import generate_image_manifest

BENCHMARK_PROMPTS = [
    # 1. Photo-realism
    {
        "prompt": "photo portrait macro 85mm d'un artisan bijoutier examinant un diamant avec sa loupe d'horloger",
        "expected_category": "photo_realistic",
        "expected_dir": "perso",
        "min_width": 832,
        "min_height": 1024,
    },
    # 2. Game Assets: Pixel Art
    {
        "prompt": "sprite pixel art 16-bit d'un chevalier avec armure d'argent et bouclier dore",
        "expected_category": "game_asset_pixel_art",
        "expected_dir": "assets",
        "check_pixel_grid": True,
    },
    # 3. Game Assets: Isometric 3D Prop
    {
        "prompt": "tour de garde medievale en pierre taille vue isometrique 3d pour un rts",
        "expected_category": "game_asset_isometric",
        "expected_dir": "assets",
        "check_iso": True,
    },
    # 4. Game Assets: UI Icon
    {
        "prompt": "elixir de vie potion magique rougeoyante pour icone d inventaire rpg",
        "expected_category": "game_asset_icon_ui",
        "expected_dir": "assets",
        "check_ui": True,
    },
    # 5. Game Assets: Seamless Tileable Texture
    {
        "prompt": "texture sol pave de donjon en pierre antique seamless tileable",
        "expected_category": "game_asset_texture",
        "expected_dir": "assets",
        "check_tileable": True,
    },
    # 6. Developed Style: Pixar 3D
    {
        "prompt": "un jeune dragonceau curieux et amical style animation pixar 3d",
        "expected_category": "stylized_pixar_3d",
        "expected_dir": "perso",
    },
    # 7. Developed Style: Anime Ghibli
    {
        "prompt": "train vapeur traversant une prairie fleurie sous les nuages d ete style anime ghibli",
        "expected_category": "stylized_anime_ghibli",
        "expected_dir": "decor",
    },
    # 8. Developed Style: Manga Ink N&B
    {
        "prompt": "duel au sommet entre deux maitres d arts martiaux planche manga noir et blanc trames",
        "expected_category": "stylized_manga_ink",
        "expected_dir": "perso",
    },
    # 9. Developed Style: Cyberpunk
    {
        "prompt": "marche clandestin cyberpunk dans une ruelle de neo tokyo sous la pluie et les neons",
        "expected_category": "stylized_cyberpunk",
        "expected_dir": "decor",
    },
]

def validate_manifest(manifest, case, *, simulate):
    """Validate a real package contract without claiming semantic image quality."""
    if manifest["category"] != case["expected_category"]:
        raise ValueError(f"Category mismatch: {manifest['category']} != {case['expected_category']}")
    if manifest["main_category"] != case["expected_dir"]:
        raise ValueError(f"Output category mismatch: {manifest['main_category']} != {case['expected_dir']}")
    files = manifest["package_files"]
    image_path = Path(files["master_image"])
    metadata_path = Path(files["metadata_file"])
    if not image_path.is_file() or not metadata_path.is_file():
        raise ValueError("Missing master image or metadata")
    expected_status = "SIMULATED_NOT_EVALUATED" if simulate else "MEASURED_NOT_EVALUATED"
    metrics = manifest["quality_assurance_metrics"]
    if metrics["status"] != expected_status:
        raise ValueError(f"Unexpected measurement status: {metrics['status']}")
    simulated_engine = manifest["generation_params"]["engine"] == "simulation"
    if simulated_engine != simulate:
        raise ValueError("Simulation and requested inference mode do not match")
    with Image.open(image_path) as image:
        image.load()
        width, height = image.size
    dimensions = manifest["dimensions"]
    if (width, height) != (dimensions["width"], dimensions["height"]):
        raise ValueError("Actual dimensions differ from metadata")
    if width < case.get("min_width", 1) or height < case.get("min_height", 1):
        raise ValueError("Image resolution is below the requested minimum")
    if not metrics["dominant_palette_hex"]:
        raise ValueError("Missing measured palette")
    return {"image": str(image_path), "metadata": str(metadata_path),
            "width": width, "height": height, "measurements": metrics}


def run_benchmark(output_dir, *, simulate=False, limit=None, seed=42):
    """Measure package production. Simulation is an explicit structural smoke test."""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    cases = BENCHMARK_PROMPTS[:limit] if limit is not None else BENCHMARK_PROMPTS
    results = []
    for index, case in enumerate(cases):
        started = time.perf_counter()
        result = {"prompt": case["prompt"], "seed": seed + index,
                  "category": case["expected_category"], "semantic_evaluation": "NOT_EVALUATED"}
        try:
            manifest = generate_image_manifest(
                case["prompt"], output_dir=output_dir / f"case_{index + 1:02d}",
                seed=seed + index, use_comfy=not simulate,
            )
            result.update(validate_manifest(manifest, case, simulate=simulate))
            result["status"] = "STRUCTURE_VALID"
        except Exception as error:
            result.update(status="FAILED", error=f"{type(error).__name__}: {error}")
        result["wall_ms"] = round((time.perf_counter() - started) * 1000, 2)
        results.append(result)
        print(f"[{index + 1}/{len(cases)}] {result['status']} {result['category']} ({result['wall_ms']} ms)")
    durations = sorted(row["wall_ms"] for row in results if row["status"] == "STRUCTURE_VALID")
    report = {
        "mode": "SIMULATION_STRUCTURE_ONLY" if simulate else "REAL_INFERENCE",
        "semantic_evaluation": "NOT_EVALUATED", "seed": seed,
        "valid_packages": len(durations), "total_cases": len(cases),
        "median_wall_ms": statistics.median(durations) if durations else None,
        "p95_wall_ms": durations[math.ceil(0.95 * len(durations)) - 1] if durations else None,
        "cases": results,
    }
    destination = output_dir / "benchmark.json"
    destination.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Report: {destination}. Visual fidelity has not been evaluated.")
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--simulate", action="store_true", help="Validate packaging without GPU inference")
    mode.add_argument("--real", action="store_true", help="Run real ComfyUI inference (default)")
    parser.add_argument("--limit", type=int, default=len(BENCHMARK_PROMPTS))
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--output-dir", type=Path, default=Path("audit/benchmarks/image") / datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ"))
    args = parser.parse_args()
    if not 1 <= args.limit <= len(BENCHMARK_PROMPTS):
        parser.error(f"--limit must be between 1 and {len(BENCHMARK_PROMPTS)}")
    report = run_benchmark(args.output_dir, simulate=args.simulate, limit=args.limit, seed=args.seed)
    return 0 if report["valid_packages"] == report["total_cases"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
