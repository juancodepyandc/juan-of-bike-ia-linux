"""Aurora multi-scene loop with critic-driven prompt refinement.

For each scene in a queue:
    attempt 1..MAX_RETRIES:
        run pipeline_hunyuan_realistic.run_one(prompt, name)
        critique the pack
        if score >= min_score: success, commit, next scene
        else: refine prompt, delete generated assets, retry

State persisted in <REPO>/aurora_state.json so it can resume after Ctrl+C.

CLI:
    python aurora_loop.py --queue scenes.json --min-score 0.7 --max-retries 3
    python aurora_loop.py --prompt "a single test prompt" --name test_scene
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path

from aurora_classify import classify
from aurora_critic import evaluate, refine_prompt
import pipeline_hunyuan_realistic as pipeline
import aurora_vision_research as vision

REPO = Path(__file__).resolve().parent
AURORA = Path(r"C:\Users\Juan\Desktop\ia\AuroraIA-v2")
STATE = REPO / "aurora_state.json"

log = logging.getLogger("loop")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")


DEFAULT_QUEUE: list[dict[str, str]] = [
    {"prompt": "a steampunk brass mechanical clockwork dragon with spinning gears, intricate copper pipes",
      "name": "steampunk_clockwork_dragon"},
    {"prompt": "a glowing crystal lantern floating in fog at night, mystic",
      "name": "crystal_lantern_fog"},
    {"prompt": "an ancient stone temple in lush jungle, mossy, weathered ruins",
      "name": "jungle_temple_ruins"},
    {"prompt": "a samurai warrior in golden lacquered armor, dramatic sunset",
      "name": "samurai_golden_sunset"},
    {"prompt": "a futuristic neon cyberpunk hover bike, magenta and cyan accents, rain wet street",
      "name": "cyberpunk_hover_bike"},
    {"prompt": "a wise old wizard with a luminous staff, swirling magical particles around him",
      "name": "wizard_luminous_staff"},
    {"prompt": "a deep sea anglerfish with bioluminescent lure, dark ocean depth",
      "name": "anglerfish_bioluminescent"},
    {"prompt": "a vintage leather armchair, studio product shot, soft shadows",
      "name": "vintage_leather_armchair"},
]


@dataclass
class Attempt:
    prompt: str
    score: float
    flags: list
    passed: bool


def load_state() -> dict:
    if STATE.exists():
        return json.loads(STATE.read_text(encoding="utf-8"))
    return {"completed": [], "failed": [], "attempts": {}}


def save_state(state: dict) -> None:
    STATE.write_text(json.dumps(state, indent=2, ensure_ascii=False), encoding="utf-8")


def git_commit_pack(pack_dir: Path, scene_name: str, score: float) -> None:
    """Force-add the pack (application/output/ is in .gitignore) and commit."""
    try:
        subprocess.run(["git", "-C", str(AURORA), "add", "-f", str(pack_dir)],
                       check=False, capture_output=True)
        msg = f"feat: {scene_name} Hunyuan3D PBR pack (score {score:.2f})"
        rc = subprocess.run(
            ["git", "-C", str(AURORA), "commit", "-m", msg],
            check=False, capture_output=True, text=True,
        )
        if rc.returncode == 0:
            log.info(f"git: committed {scene_name}")
        else:
            log.warning(f"git commit rc={rc.returncode}: stderr={rc.stderr.strip()[:200]} stdout={rc.stdout.strip()[:200]}")
    except Exception as e:
        log.warning(f"git commit failed: {e}")


def clean_pack(pack_dir: Path, keep_input: bool = True) -> None:
    if not pack_dir.exists():
        return
    if keep_input:
        for child in pack_dir.iterdir():
            if child.name in {"input.png", "input_nobg.png"}:
                continue
            if child.is_file():
                child.unlink()
            else:
                shutil.rmtree(child, ignore_errors=True)
    else:
        shutil.rmtree(pack_dir, ignore_errors=True)


def process_scene(prompt: str, name: str, min_score: float, max_retries: int, state: dict) -> bool:
    history = state["attempts"].setdefault(name, [])
    current_prompt = prompt

    character_name = vision.identify_character_in_prompt(current_prompt)
    reference_images = []
    if character_name:
        log.info(f"Identified known character '{character_name}' in prompt. Initiating Vision Research...")
        reference_images = vision.fetch_reference_images(character_name, Path("application/output/references"), max_images=1)
        expanded_traits = ""
        if reference_images:
            expanded_traits = vision.extract_visual_traits(reference_images[0], character_name)
        else:
            log.warning(f"No references found. Using LLM internal knowledge for visual traits of {character_name}...")
            expanded_traits = vision.generate_visual_traits_from_knowledge(character_name)
            
        if expanded_traits:
            log.info(f"VLM/LLM Extracted Traits: {expanded_traits[:200]}...")
            
            # If the user included photorealistic but the LLM output anime style, strip photorealistic to avoid cosplayers!
            if "anime style" in expanded_traits.lower() and "photorealistic" in current_prompt.lower():
                current_prompt = current_prompt.replace("photorealistic", "").replace("  ", " ")
                log.info("Stripped 'photorealistic' from prompt because character is anime style.")
                
            current_prompt = f"{current_prompt}, character traits: {expanded_traits}"

    for attempt_idx in range(1, max_retries + 1):
        log.info(f"=== {name} attempt {attempt_idx}/{max_retries} ===")
        log.info(f"prompt: {current_prompt}")
        t0 = time.time()
        
        device = "cpu" if os.environ.get("AURORA_SAFE_MODE", "0") == "1" else "cuda"
        
        # Step 1: Generate image only first
        profile = classify(current_prompt, name)
        pack_dir = pipeline.OUTPUT_ROOT / f"pbr_{profile.name}_pack"
        pack_dir.mkdir(parents=True, exist_ok=True)
        img_path = pack_dir / "input.png"
        
        if img_path.exists():
            log.info(f"User provided a manual image at {img_path}. Applying VLM Researcher strategy...")
            try:
                # We analyze the user's image to extract its exact traits to recreate a clean 3/4 view
                expanded_traits = vision.extract_visual_traits(img_path, character_name or name)
                log.info(f"VLM analyzed user image: {expanded_traits[:200]}...")
                enhanced_prompt = f"isometric 3/4 view, full body shot, pristine solid white background, highly detailed 3D asset, sharp focus, albedo textures, no shadows, masterpiece, {current_prompt}, {expanded_traits}"
                
                # We rename the original image so it's not overwritten, but we keep it for reference
                user_img_backup = pack_dir / "input_user_original.png"
                if not user_img_backup.exists():
                    img_path.rename(user_img_backup)
                    
                log.info("Generating pristine 3/4 view from user's image traits to avoid double-face and baked lighting...")
                pipeline.generate_image(enhanced_prompt, img_path, seed=42 + attempt_idx, device=device)
            except Exception as e:
                log.exception(f"VLM Researcher generation failed: {e}")
                history.append({"attempt": attempt_idx, "error": str(e)})
                continue
        else:
            enhanced_prompt = "isometric 3/4 view, full body shot from head to toe, entire body visible, legs and feet clearly visible in frame, pristine solid white background, highly detailed 3D asset, sharp focus, masterpiece, albedo textures, no shadows, " + profile.prompt_image
            try:
                pipeline.generate_image(enhanced_prompt, img_path, seed=42 + attempt_idx, device=device)
            except Exception as e:
                log.exception(f"Image generation failed: {e}")
                history.append({"attempt": attempt_idx, "error": str(e)})
                continue

        # Step 2: VLM Verification
        vlm_passed = True
        vlm_critique = "No references to check against."
        vlm_score = 1.0
        
        if reference_images and img_path.exists():
            eval_res = vision.evaluate_fidelity(reference_images[0], img_path, character_name)
            vlm_passed = eval_res["passed"]
            vlm_score = eval_res["score"]
            vlm_critique = eval_res["critique"]
            log.info(f"VLM Evaluation: passed={vlm_passed}, score={vlm_score}, critique={vlm_critique[:150]}...")
            
            if not vlm_passed:
                log.warning(f"VLM rejected image. Critique: {vlm_critique}")
                # Use critique to refine prompt
                current_prompt = f"{current_prompt}. Fixes needed: {vlm_critique}"
                clean_pack(pack_dir, keep_input=True)
                history.append({"attempt": attempt_idx, "score": vlm_score, "passed": False, "critique": vlm_critique})
                save_state(state)
                continue

        # Step 3: Run full pipeline (Image exists, so it will skip image gen and do 3D)
        try:
            pack_dir = pipeline.run_one(current_prompt, name, device=device)
        except Exception as e:
            log.exception(f"pipeline 3D raised on {name} attempt {attempt_idx}: {e}")
            history.append({"attempt": attempt_idx, "prompt": current_prompt, "error": str(e)})
            save_state(state)
            continue
            
        crit = evaluate(pack_dir, min_score)
        
        # Override structural critique with VLM critique if we have references
        if reference_images:
            crit["passed"] = crit["passed"] and vlm_passed
            crit["score"] = min(crit["score"], vlm_score)
            crit["flags"].append("vlm_evaluated")
            
        elapsed = round(time.time() - t0, 1)
        history.append({
            "attempt": attempt_idx,
            "prompt": current_prompt,
            "score": crit["score"],
            "flags": crit["flags"],
            "passed": crit["passed"],
            "elapsed_s": elapsed,
        })
        save_state(state)
        log.info(f"=== {name} attempt {attempt_idx}: score={crit['score']:.3f} passed={crit['passed']} "
                  f"flags={crit['flags']} elapsed={elapsed}s ===")
        log.info(f"=== {name} OUTPUT PATHS ===")
        for item in sorted(pack_dir.iterdir()):
            if item.is_file():
                log.info(f"  {item}")
        log.info(f"=== /{name} OUTPUT PATHS ===")
        if crit["passed"]:
            git_commit_pack(pack_dir, name, crit["score"])
            return True
        if attempt_idx == max_retries:
            log.warning(f"=== {name} exhausted retries; keeping best result ===")
            git_commit_pack(pack_dir, name, crit["score"])
            return False
        refined = crit.get("suggested_prompt") or refine_prompt({"prompt_original": current_prompt}, crit["flags"])
        if refined == current_prompt:
            log.warning(f"=== {name} refiner produced same prompt; stopping ===")
            git_commit_pack(pack_dir, name, crit["score"])
            return False
        current_prompt = refined
        clean_pack(pack_dir, keep_input=True)
    return False


def run_queue(queue: list[dict[str, str]], min_score: float, max_retries: int) -> int:
    state = load_state()
    successes = 0
    for entry in queue:
        name = entry["name"]
        if name in state["completed"]:
            log.info(f"skip {name}: already completed")
            successes += 1
            continue
        prompt = entry["prompt"]
        ok = process_scene(prompt, name, min_score, max_retries, state)
        if ok:
            state["completed"].append(name)
            successes += 1
        else:
            state["failed"].append(name)
        save_state(state)
    log.info(f"=== queue done: {successes}/{len(queue)} succeeded ===")
    return 0 if successes == len(queue) else 1


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--queue", type=Path, help="JSON list of {prompt, name}")
    ap.add_argument("--prompt", type=str)
    ap.add_argument("--name", type=str)
    ap.add_argument("--min-score", type=float, default=0.65)
    ap.add_argument("--max-retries", type=int, default=3)
    ap.add_argument("--default-queue", action="store_true",
                     help="run the built-in DEFAULT_QUEUE if no --queue provided")
    args = ap.parse_args()

    if args.prompt:
        queue = [{"prompt": args.prompt, "name": args.name or classify(args.prompt).name}]
    elif args.queue:
        queue = json.loads(args.queue.read_text(encoding="utf-8"))
    elif args.default_queue:
        queue = DEFAULT_QUEUE
    else:
        log.error("provide --prompt, --queue or --default-queue")
        return 2
    return run_queue(queue, args.min_score, args.max_retries)


if __name__ == "__main__":
    sys.exit(main())
