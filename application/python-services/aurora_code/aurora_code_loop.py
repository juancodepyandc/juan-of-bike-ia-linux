"""Aurora code-generation autonomous loop.

For each prompt in the queue:
  1. enrich(prompt) -> EnrichedPrompt with project_type + system
  2. POST to Ollama /api/chat with qwen3-coder:30b, stream tokens to terminal
  3. parse <FILE path="..."> tags from the response into a project tree
  4. write to application/output/code-loop/<iso>-<slug>/project/
  5. for web outputs: spawn local http.server, drive headless Chrome via CDP,
     screenshot to preview.png, optionally ask qwen3-vl to rate it
  6. score = fidelity(syntax checks) + visual(qwen3-vl 0..10)
  7. retry up to N if score < threshold

Progress halo: a single-line ANSI bar updated per phase.

Usage:
    python aurora_code_loop.py --queue queue_pages.json
    python aurora_code_loop.py --prompt "tesla cybertruck page" --name tesla
"""
from __future__ import annotations

import json
import logging
import subprocess
import time
from dataclasses import asdict
from datetime import datetime

from aurora_code_enrich import EnrichedPrompt, enrich
from aurora_code_validators import validate as run_validator, complexity_check
from aurora_code_remote import (
    Target, deploy as remote_deploy, enrich_for_target,
    remote_validate_node, remote_validate_python,
    remote_validate_static_web,
)
from code_loop_files import extract_files, make_pack_dir, slugify, syntax_check_files, write_project
from code_loop_runtime import CODE_MODEL, cdp_screenshot, free_port, halo, ollama_chat, score_preview_vision, serve_static
from code_loop_state import load_state, save_state

log = logging.getLogger("code-loop")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")


# ---------------------------------------------------------------------------
# Main scene runner
# ---------------------------------------------------------------------------

def process_scene(prompt: str, name: str | None, min_score: float, max_retries: int,
                    state: dict, target: Target | None = None, use_tunnel: bool = False) -> bool:
    scene_id = name or slugify(prompt)
    history = state["attempts"].setdefault(scene_id, [])
    current_prompt = prompt

    for attempt in range(1, max_retries + 1):
        halo.tick("classifying", scene=scene_id)
        enriched = enrich(current_prompt)
        # if a remote target is set, append platform-specific hints so the LLM
        # generates code that runs on the target (Pi GPIO, ARMv7, etc.)
        if target is not None:
            enriched.enriched = enriched.enriched + enrich_for_target(target)
        log.info(f"=== {scene_id} attempt {attempt}/{max_retries} type={enriched.project_type}"
                  + (f" target={target.name}" if target else "") + " ===")

        pack = make_pack_dir(current_prompt, name)
        pack.mkdir(parents=True, exist_ok=True)
        project_dir = pack / "project"

        # metadata
        meta = {
            "module": "code",
            "prompt": current_prompt,
            "project_type": enriched.project_type,
            "model": CODE_MODEL,
            "attempt": attempt,
            "started_at": datetime.now().isoformat(),
        }
        (pack / "enrichment.json").write_text(json.dumps(asdict(enriched), indent=2,
                                                            ensure_ascii=False), encoding="utf-8")

        halo.tick(f"gen via {CODE_MODEL}", scene=scene_id)
        t0 = time.time()
        try:
            response = ollama_chat(CODE_MODEL, enriched.system, enriched.enriched, scene=scene_id)
        except Exception as e:
            log.error(f"  Ollama call failed: {e}")
            history.append({"attempt": attempt, "error": str(e)[:200]})
            save_state(state)
            continue
        gen_t = time.time() - t0
        meta["gen_s"] = round(gen_t, 1)
        meta["response_chars"] = len(response)
        (pack / "response.txt").write_text(response, encoding="utf-8")

        halo.tick("parsing files", scene=scene_id)
        files = extract_files(response)
        if not files:
            log.error(f"  no files extracted from response ({len(response)}c)")
            history.append({"attempt": attempt, "error": "no_files_extracted",
                              "elapsed_s": round(gen_t, 1)})
            save_state(state)
            continue
        n_written = write_project(files, project_dir)
        meta["files_count"] = n_written
        log.info(f"  wrote {n_written} files in {gen_t:.1f}s")

        # complexity floor: if output too small/few-files, do a 2nd pass asking
        # the model to expand specific files
        complexity = complexity_check(pack, enriched.project_type, n_written)
        meta["complexity"] = complexity
        if complexity["needs_expansion"]:
            halo.tick("multi-pass expand", scene=scene_id)
            log.info(f"  complexity below floor: {complexity['flags']} -> expanding")
            expand_user = (
                f"The previous output is too sparse: {complexity['flags']}. "
                f"You produced {complexity['files']} files totaling "
                f"{complexity['total_bytes']} bytes. Expand and complete the project "
                f"so it fulfills the brief at production quality. Use the same "
                f"<FILE path=\"...\"></FILE> output contract, and INCLUDE the entire "
                f"updated file set (not a diff). Original brief:\n\n{enriched.enriched}"
            )
            t1 = time.time()
            try:
                response2 = ollama_chat(CODE_MODEL, enriched.system, expand_user, scene=scene_id)
                files2 = extract_files(response2)
                if files2:
                    n_written = write_project(files2, project_dir)
                    files = files2
                    response = response + "\n\n=== PASS 2 ===\n\n" + response2
                    (pack / "response.txt").write_text(response, encoding="utf-8")
                    meta["pass2_s"] = round(time.time() - t1, 1)
                    meta["files_count"] = n_written
                    log.info(f"  pass2 wrote {n_written} files in {meta['pass2_s']:.1f}s")
            except Exception as e:
                log.warning(f"  pass2 failed: {e}")
                meta["pass2_error"] = str(e)[:200]

        halo.tick("syntax check", scene=scene_id)
        syntax = syntax_check_files(project_dir, files)
        meta["syntax"] = syntax

        # preview validation: react_vite builds first, static_web serves dir,
        # other types skip web preview and rely on validator dispatcher.
        vision = None
        preview_ok = False
        runtime_report: dict | None = None
        validator_result: dict | None = None

        if enriched.project_type == "react_vite":
            halo.tick("npm install + build", scene=scene_id)
            validator_result = run_validator(enriched.project_type, pack)
            meta["validator"] = validator_result
            dist = project_dir / "dist"
            serve_dir = dist if validator_result.get("ok") else project_dir
            index_in_dir = (dist / "index.html") if (dist / "index.html").exists() else \
                            (project_dir / "index.html")
            if index_in_dir.exists():
                halo.tick("serving preview", scene=scene_id)
                port = free_port()
                server = serve_static(serve_dir, port)
                try:
                    time.sleep(1.2)
                    url = f"http://127.0.0.1:{port}/index.html"
                    preview_path = pack / "preview.png"
                    halo.tick(f"CDP :{port}", scene=scene_id)
                    ok, runtime_report = cdp_screenshot(url, preview_path)
                    if ok:
                        preview_ok = True
                        halo.tick("vision scoring", scene=scene_id)
                        vision = score_preview_vision(preview_path, prompt)
                        meta["vision"] = vision
                finally:
                    if use_tunnel:
                        halo.tick("launching localtunnel", scene=scene_id)
                        print("\n\n>>> 🚀 LAUNCHING TUNNEL FOR MANUAL UI TESTING 🚀 <<<")
                        print(f">>> Server is running locally on http://127.0.0.1:{port} <<<")
                        print(">>> Press CTRL+C to close the tunnel and server when done testing <<<\n")
                        try:
                            # Use npx to run localtunnel and expose the port
                            subprocess.run(["npx", "-y", "localtunnel", "--port", str(port)], cwd=str(serve_dir))
                        except KeyboardInterrupt:
                            print("\nTunnel closed by user.")
                    server.terminate()
                    try:
                        server.wait(timeout=3)
                    except subprocess.TimeoutExpired:
                        server.kill()
        elif enriched.project_type.startswith("static_web"):
            index_html = project_dir / "index.html"
            if index_html.exists():
                halo.tick("serving preview", scene=scene_id)
                port = free_port()
                server = serve_static(project_dir, port)
                try:
                    time.sleep(1.2)
                    url = f"http://127.0.0.1:{port}/index.html"
                    preview_path = pack / "preview.png"
                    halo.tick(f"CDP :{port}", scene=scene_id)
                    ok, runtime_report = cdp_screenshot(url, preview_path)
                    if ok:
                        preview_ok = True
                        halo.tick("vision scoring", scene=scene_id)
                        vision = score_preview_vision(preview_path, prompt)
                        meta["vision"] = vision
                finally:
                    if use_tunnel:
                        halo.tick("launching localtunnel", scene=scene_id)
                        print("\n\n>>> 🚀 LAUNCHING TUNNEL FOR MANUAL UI TESTING 🚀 <<<")
                        print(f">>> Server is running locally on http://127.0.0.1:{port}/index.html <<<")
                        print(">>> Press CTRL+C to close the tunnel and server when done testing <<<\n")
                        try:
                            subprocess.run(["npx", "-y", "localtunnel", "--port", str(port)], cwd=str(project_dir))
                        except KeyboardInterrupt:
                            print("\nTunnel closed by user.")
                    server.terminate()
                    try:
                        server.wait(timeout=3)
                    except subprocess.TimeoutExpired:
                        server.kill()
            validator_result = run_validator(enriched.project_type, pack, runtime_report)
            meta["validator"] = validator_result
        else:
            # python_cli / node_express / native_* — type-specific validator only
            halo.tick(f"validate {enriched.project_type}", scene=scene_id)
            validator_result = run_validator(enriched.project_type, pack)
            meta["validator"] = validator_result

        # if a remote target is configured, deploy + remote-validate now
        if target is not None and n_written > 0:
            halo.tick(f"scp -> {target.name}", scene=scene_id)
            dep = remote_deploy(target, project_dir, scene_id)
            meta["remote_deploy"] = dep
            if dep.get("ok"):
                halo.tick(f"remote validate on {target.name}", scene=scene_id)
                if enriched.project_type == "python_cli":
                    py_files = [p.name for p in project_dir.glob("*.py")]
                    entry = "main.py" if "main.py" in py_files else (py_files[0] if py_files else "main.py")
                    meta["remote_validate"] = remote_validate_python(target, scene_id, entry=entry)
                elif enriched.project_type == "node_express":
                    meta["remote_validate"] = remote_validate_node(target, scene_id)
                elif enriched.project_type.startswith("static_web") or enriched.project_type == "react_vite":
                    meta["remote_validate"] = remote_validate_static_web(target, scene_id)
                else:
                    meta["remote_validate"] = {"ok": True, "note": "no remote check defined for type"}

        # score: combine syntax + vision + validator + preview_ok
        # weighting depends on whether vision was applicable for this type
        syntax_score = 1.0 if syntax["passed"] else max(0.0, 1.0 - len(syntax["flags"]) * 0.15)
        vis_score: float | None = None
        if vision and vision.get("available"):
            vs = [vision.get(k, 0) for k in ("fidelity", "polish", "layout", "completeness")]
            vis_score = sum(vs) / 40.0
        val_score = validator_result["score"] if validator_result else 0.5
        # complexity penalty is only meaningful for visual types; APIs and CLIs
        # are intentionally small.
        is_visual = (enriched.project_type.startswith("static_web")
                       or enriched.project_type == "react_vite")
        complexity_penalty = 0.0
        if complexity.get("needs_expansion") and is_visual:
            complexity_penalty = 0.10

        if is_visual and vis_score is not None:
            preview_w = 0.10 if preview_ok else 0.0
            score = (0.25 * syntax_score + 0.35 * vis_score + 0.30 * val_score
                       + preview_w - complexity_penalty)
        elif is_visual and vis_score is None:
            score = (0.30 * syntax_score + 0.60 * val_score
                       + (0.10 if preview_ok else 0.0) - complexity_penalty)
        else:
            # API / CLI / native: no vision, validator is the truth
            score = 0.30 * syntax_score + 0.70 * val_score
        score = round(max(0.0, min(1.0, score)), 3)
        meta["score"] = score
        meta["finished_at"] = datetime.now().isoformat()
        (pack / "metadata.json").write_text(json.dumps(meta, indent=2, ensure_ascii=False),
                                              encoding="utf-8")

        history.append({"attempt": attempt, "score": score, "files": n_written,
                          "syntax_passed": syntax["passed"], "preview_ok": preview_ok,
                          "elapsed_s": round(time.time() - t0, 1)})
        save_state(state)
        halo.done()
        log.info(f"=== {scene_id} attempt {attempt}: score={score:.3f} files={n_written} ===")
        log.info("OUTPUTS:")
        for p in sorted(pack.rglob("*")):
            if p.is_file():
                log.info(f"  {p}  ({p.stat().st_size / 1024:.1f} KB)")

        # Meta-loop: even if we pass the gate, if score is below the
        # "expert" bar (0.85), trigger a self-critique pass that asks the LLM
        # to review its own output and the run an improvement pass. This is
        # what separates "passes the test" from "principal-engineer quality".
        EXPERT_BAR = 0.85
        if (score >= min_score and syntax["passed"]
                and score < EXPERT_BAR and attempt < max_retries
                and (enriched.project_type.startswith("static_web")
                     or enriched.project_type == "react_vite")):
            halo.tick("self-critique", scene=scene_id)
            critique_user = (
                f"Here is the project you just shipped (response below). It works (score "
                f"{score:.2f}) but it is NOT yet at principal-engineer level. Acting as a "
                f"strict senior reviewer, list the TOP 6 concrete improvements (visual polish, "
                f"motion, depth, hierarchy, content density, accessibility, performance). "
                f"Be specific: 'add a hero gradient + scroll-reveal on sections', not 'make "
                f"it nicer'. Then output a single line: NEEDS_REGEN=true if rework is worth "
                f"it, NEEDS_REGEN=false otherwise.\n\nOriginal brief:\n{prompt}\n\nYour output:\n"
                f"{response[:6000]}"
            )
            try:
                critique = ollama_chat(CODE_MODEL, enriched.system, critique_user,
                                         scene=scene_id, num_predict=2000)
                meta["self_critique"] = critique[:3000]
                (pack / "self_critique.txt").write_text(critique, encoding="utf-8")
                if "NEEDS_REGEN=true" in critique.upper():
                    log.info(f"=== {scene_id} self-critique requests regen at attempt {attempt+1} ===")
                    current_prompt = (
                        prompt + "\n\nThe previous attempt was OK but below expert level. "
                        "Address THIS feedback in the next version:\n" + critique[:2500]
                    )
                    save_state(state)
                    continue
            except Exception as e:
                log.warning(f"self-critique failed: {e}")
        if score >= min_score and syntax["passed"]:
            return True
        if attempt == max_retries:
            return False
        # refine: build corrective hints from all signals collected
        notes = []
        if not syntax["passed"]:
            notes.append(f"fix syntax: {'; '.join(syntax['flags'][:5])}")
        if validator_result and not validator_result.get("ok"):
            vflags = validator_result.get("flags", [])
            if vflags:
                notes.append(f"fix runtime/build: {'; '.join(vflags[:5])}")
        if runtime_report and runtime_report.get("ok"):
            errs = runtime_report.get("exceptions", [])
            if errs:
                notes.append("fix JS exceptions: " + "; ".join(
                    f"{e.get('text','')[:60]}" for e in errs[:3]
                ))
        if vision and vision.get("available") and vision.get("polish", 10) < 6:
            notes.append("improve visual polish, layout, animation, hierarchy")
        if vision and vision.get("available") and vision.get("completeness", 10) < 6:
            notes.append("add missing sections, more content, more depth")
        if complexity.get("needs_expansion"):
            notes.append("expand: more files, longer code, richer interactions")
        if not preview_ok and enriched.project_type.startswith("static_web"):
            notes.append("ensure index.html renders standalone with no errors")
        current_prompt = prompt + " — corrections: " + " | ".join(notes)
    return False


def run_queue(queue: list[dict], min_score: float, max_retries: int,
                target: Target | None = None, use_tunnel: bool = False) -> int:
    from code_loop_cli import run_queue as run_cli_queue
    return run_cli_queue(
        queue, min_score, max_retries, process_scene,
        target=target, use_tunnel=use_tunnel,
    )


def main() -> int:
    from code_loop_cli import main as run_cli
    return run_cli(process_scene)


if __name__ == "__main__":
    raise SystemExit(main())
