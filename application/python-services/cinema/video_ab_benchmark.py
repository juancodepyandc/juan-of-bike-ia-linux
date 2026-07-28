"""Harnais A/B vidéo reproductible et honnête.

Chaque variante reçoit exactement le même prompt, seed, negative prompt,
dimensions, nombre de frames et image de référence. Les moteurs s'exécutent
en série dans la file GPU du bridge. Un gagnant n'est annoncé que si la QA
vision a réellement mesuré les sorties.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path


CINEMA_DIR = Path(__file__).resolve().parent
SERVICES_DIR = CINEMA_DIR.parent
WORKSPACE = SERVICES_DIR.parent
VIDEO_SCRIPT = SERVICES_DIR / "video_generate.py"

sys.path.insert(0, str(CINEMA_DIR))
from cinema_pipeline import check_temporal_coherence, validate_rendered_shot


def emit(stage: str, detail: str) -> None:
    print(f"PROGRESS:{stage}:{detail}", flush=True)


def last_json_line(raw: str) -> dict | None:
    for line in reversed((raw or "").splitlines()):
        line = line.strip()
        if not (line.startswith("{") and line.endswith("}")):
            continue
        try:
            value = json.loads(line)
            if isinstance(value, dict):
                return value
        except Exception:
            continue
    return None


def atomic_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".partial")
    temp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(temp, path)


def build_variant_command(spec: dict, variant: str, output: Path) -> list[str]:
    cmd = [
        sys.executable,
        str(VIDEO_SCRIPT),
        "--prompt", str(spec["prompt"]),
        "--output", str(output),
        "--width", str(int(spec["width"])),
        "--height", str(int(spec["height"])),
        "--num_frames", str(int(spec["num_frames"])),
        "--seed", str(int(spec["seed"])),
        "--negative_prompt", str(spec.get("negative_prompt") or ""),
        "--quality_mode", "premium",
        "--model_mode", "quality",
        "--motion_interp", "0",
        "--force_strategy", variant,
    ]
    image = str(spec.get("image") or "").strip()
    if image:
        cmd.extend(["--image", image])
    return cmd


def run_variant(command: list[str]) -> tuple[int, str]:
    proc = subprocess.Popen(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        bufsize=1,
    )
    lines = []
    for line in proc.stdout or []:
        clean = line.rstrip()
        lines.append(clean)
        if clean.startswith(("PROGRESS:", "THUMBNAIL:", "SAVED:", "{")):
            print(clean, flush=True)
    return proc.wait(), "\n".join(lines)


def measured_score(qa: dict, temporal: dict) -> tuple[float | None, float]:
    dimensions = [
        qa.get("score"),
        qa.get("physics_score"),
        qa.get("identity_score"),
        qa.get("action_score"),
    ]
    measured = [
        value for value in dimensions
        if isinstance(value, (int, float)) and not isinstance(value, bool)
    ]
    temporal_ok = temporal.get("ok")
    coverage = (len(measured) + int(isinstance(temporal_ok, bool))) / 5.0
    if len(measured) != 4:
        return None, coverage
    vision_pct = sum(float(value) for value in measured) / 4.0 * 10.0
    if isinstance(temporal_ok, bool):
        return vision_pct * 0.85 + (100.0 if temporal_ok else 0.0) * 0.15, coverage
    return vision_pct, coverage


def normalize_spec(raw: dict) -> dict:
    prompt = str(raw.get("prompt") or "").strip()
    if not prompt:
        raise ValueError("prompt A/B manquant")
    variants = raw.get("variants") or ["wan5b", "ltx"]
    if isinstance(variants, str):
        variants = [item.strip() for item in variants.split(",") if item.strip()]
    variants = [str(item).strip().lower() for item in variants if str(item).strip()]
    if not variants:
        raise ValueError("aucune variante A/B")
    if len(variants) > 4:
        raise ValueError("maximum 4 variantes par campagne")
    image = str(raw.get("image") or "").strip()
    if image and not Path(image).is_file():
        raise ValueError(f"image de reference absente: {image}")
    return {
        "prompt": prompt,
        "negative_prompt": str(raw.get("negative_prompt") or (
            "identity drift, deformed anatomy, extra limbs, fused fingers, "
            "warped face, flicker, jump cut, text, watermark"
        )),
        "width": max(320, min(1280, int(raw.get("width") or 832))),
        "height": max(320, min(720, int(raw.get("height") or 480))),
        "num_frames": max(25, min(97, int(raw.get("num_frames") or 49))),
        "seed": int(raw.get("seed") if raw.get("seed") is not None else 424242),
        "image": image,
        "variants": variants,
        "style": str(raw.get("style") or "cinematic"),
        "character_description": str(raw.get("character_description") or ""),
        "action_contract": str(raw.get("action_contract") or prompt),
    }


def run_benchmark(spec: dict, output_dir: Path, plan_only: bool = False) -> dict:
    output_dir.mkdir(parents=True, exist_ok=True)
    report_path = output_dir / "report.json"
    report = {
        "ok": False,
        "kind": "video_ab_benchmark",
        "profile": "personal_quality_first",
        "spec": spec,
        "started_at": time.time(),
        "variants": [],
        "winner": None,
        "selection_graded": False,
        "report": str(report_path),
    }
    if plan_only:
        report["ok"] = True
        report["plan_only"] = True
        report["commands"] = [
            build_variant_command(spec, variant, output_dir / f"{index:02d}_{variant}.mp4")
            for index, variant in enumerate(spec["variants"], 1)
        ]
        atomic_json(report_path, report)
        return report

    for index, variant in enumerate(spec["variants"], 1):
        output = output_dir / f"{index:02d}_{variant}.mp4"
        command = build_variant_command(spec, variant, output)
        emit("ab_variant", f"{index}/{len(spec['variants'])} · {variant}")
        started = time.time()
        exit_code, stdout = run_variant(command)
        render = last_json_line(stdout) or {
            "ok": False,
            "error": "sortie video_generate non JSON",
        }
        item = {
            "variant": variant,
            "exit_code": exit_code,
            "elapsed_s": round(time.time() - started, 2),
            "render": render,
            "output": str(output),
            "qa": None,
            "temporal": None,
            "score_pct": None,
            "coverage_pct": 0.0,
        }
        if exit_code == 0 and render.get("ok") and output.is_file():
            frames_dir = output_dir / f"frames_{index:02d}_{variant}"
            frames_dir.mkdir(parents=True, exist_ok=True)
            qa = validate_rendered_shot(
                str(output),
                frames_dir,
                index,
                spec["prompt"],
                spec["style"],
                character_desc=spec["character_description"],
                action_contract=spec["action_contract"],
            )
            temporal = check_temporal_coherence(str(output))
            score, coverage = measured_score(qa, temporal)
            item.update({
                "qa": qa,
                "temporal": temporal,
                "score_pct": round(score, 2) if score is not None else None,
                "coverage_pct": round(coverage * 100.0, 1),
            })
        report["variants"].append(item)
        atomic_json(report_path, report)

    rendered = [
        item for item in report["variants"]
        if item["render"].get("ok") and Path(item["output"]).is_file()
    ]
    graded = [
        item for item in rendered
        if item.get("score_pct") is not None and item.get("coverage_pct", 0) >= 80
    ]
    if graded:
        ranked = sorted(graded, key=lambda item: float(item["score_pct"]), reverse=True)
        report["winner"] = ranked[0]["variant"]
        report["ranking"] = [
            {"variant": item["variant"], "score_pct": item["score_pct"]}
            for item in ranked
        ]
        report["selection_graded"] = len(graded) == len(spec["variants"])
        if not report["selection_graded"]:
            report["warning"] = (
                "Gagnant provisoire parmi les variantes réellement notées; "
                "au moins une variante a échoué ou manque de couverture QA."
            )
    else:
        report["warning"] = (
            "Aucun gagnant annoncé: QA vision absente ou couverture insuffisante. "
            "Les fichiers rendus restent disponibles pour visionnage humain."
        )
    report["ok"] = bool(rendered)
    report["finished_at"] = time.time()
    atomic_json(report_path, report)
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--spec", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--plan-only", action="store_true")
    args = parser.parse_args()
    try:
        raw = json.loads(Path(args.spec).read_text(encoding="utf-8-sig"))
        spec = normalize_spec(raw)
        result = run_benchmark(spec, Path(args.output_dir), plan_only=args.plan_only)
    except Exception as exc:
        result = {
            "ok": False,
            "kind": "video_ab_benchmark",
            "error": f"{type(exc).__name__}: {str(exc)[:500]}",
        }
    print(json.dumps(result, ensure_ascii=False), flush=True)
    raise SystemExit(0 if result.get("ok") else 1)


if __name__ == "__main__":
    main()
