"""Job asynchrone d'apercu des keyframes personnages du module Cinema."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys


HERE = Path(__file__).resolve().parent
APPLICATION_DIR = HERE.parent.parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

from cinema_pipeline import (  # noqa: E402
    pregenerate_character_keyframes,
    resolution_for_generation,
    validate_keyframe_with_vision,
)


def _asset_url(path: str) -> str:
    absolute = Path(path).resolve()
    try:
        relative = absolute.relative_to(APPLICATION_DIR)
        encoded_path = relative.as_posix()
    except ValueError:
        encoded_path = absolute.as_posix()
    return f"/api/asset/{encoded_path}"


def build_preview(storyboard: dict, work_dir: Path) -> dict:
    characters = {
        c.get("name", ""): c
        for c in storyboard.get("characters", [])
        if c.get("name")
    }
    if not characters:
        return {
            "ok": True,
            "char_quality": {},
            "warnings": [],
            "message": "Aucun personnage a previsualiser.",
        }

    style = storyboard.get("style", "realistic")
    aspect = storyboard.get("aspect", "16:9")
    resolution = storyboard.get("resolution", "720p")
    gen_w, gen_h, _ = resolution_for_generation(resolution, aspect)
    keyframes = pregenerate_character_keyframes(
        characters,
        work_dir,
        style,
        gen_w,
        gen_h,
    )

    char_quality = {}
    warnings = []
    for name, path in keyframes.items():
        description = (characters[name].get("description") or "").strip()
        if not description:
            check = {
                "score": None,
                "reason": "Description canonique absente : keyframe non notee.",
                "ok": False,
                "graded": False,
            }
        else:
            raw_check = validate_keyframe_with_vision(path, description)
            vision_skipped = str(raw_check.get("reason", "")).startswith("vision skip:")
            if vision_skipped:
                check = {
                    "score": None,
                    "reason": raw_check.get("reason"),
                    "ok": False,
                    "graded": False,
                }
                warnings.append({
                    "code": "vision_qa_unavailable",
                    "character": name,
                    "message": raw_check.get("reason"),
                    "impact": "keyframe generee mais non validee",
                })
            else:
                check = {**raw_check, "graded": True}

        char_quality[name] = {
            **check,
            "keyframe_path": str(Path(path).resolve()),
            "keyframe_url": _asset_url(path),
        }

    return {
        "ok": True,
        "char_quality": char_quality,
        "warnings": warnings,
        "qa_coverage": {
            "graded": sum(1 for item in char_quality.values() if item.get("graded")),
            "total": len(char_quality),
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--storyboard", required=True)
    parser.add_argument("--work-dir", required=True)
    parser.add_argument("--output-json", required=True)
    args = parser.parse_args()

    storyboard = json.loads(
        Path(args.storyboard).read_text(encoding="utf-8-sig"),
    )
    work_dir = Path(args.work_dir)
    work_dir.mkdir(parents=True, exist_ok=True)

    try:
        result = build_preview(storyboard, work_dir)
    except Exception as exc:
        result = {
            "ok": False,
            "error": f"{type(exc).__name__}: {str(exc)[:500]}",
            "warnings": [{
                "code": "keyframe_preview_failed",
                "message": str(exc)[:500],
                "impact": "aucune validation pre-rendu disponible",
            }],
        }

    Path(args.output_json).write_text(
        json.dumps(result, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(json.dumps(result, ensure_ascii=False), flush=True)
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
