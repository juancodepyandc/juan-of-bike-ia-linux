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

import argparse
import json
import logging
import os
import re
import shutil
import socket
import subprocess
import sys
import time
import urllib.request
from dataclasses import asdict
from datetime import datetime
from pathlib import Path

from aurora_code_enrich import EnrichedPrompt, enrich
from aurora_code_validators import validate as run_validator, complexity_check
from aurora_code_remote import (
    Target, deploy as remote_deploy, enrich_for_target,
    load_targets, remote_validate_node, remote_validate_python,
    remote_validate_static_web,
)

REPO = Path(__file__).resolve().parent
AURORA = Path(r"C:\Users\Juan\Desktop\ia\AuroraIA-v2")
OUTPUT_ROOT = AURORA / "application" / "output" / "code-loop"
OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)

OLLAMA_URL = "http://localhost:11434"
CODE_MODEL = os.environ.get("AURORA_CODE_MODEL", "qwen3-coder:30b-a3b-q4_K_M")
VISION_MODEL = os.environ.get("AURORA_VISION_MODEL", "qwen3-vl:30b")

STATE_FILE = REPO / "code_loop_state.json"

log = logging.getLogger("code-loop")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")


# ---------------------------------------------------------------------------
# Progress halo
# ---------------------------------------------------------------------------

_HALO_FRAMES = ["[       ]", "[=      ]", "[==     ]", "[===    ]", "[====   ]",
                 "[=====  ]", "[====== ]", "[=======]", "[ ======]", "[  =====]",
                 "[   ====]", "[    ===]", "[     ==]", "[      =]"]

class Halo:
    def __init__(self) -> None:
        self.i = 0
        self.last_emit = 0.0

    def tick(self, phase: str, scene: str = "", score: float | None = None) -> None:
        now = time.time()
        if now - self.last_emit < 0.12:
            return
        self.last_emit = now
        frame = _HALO_FRAMES[self.i % len(_HALO_FRAMES)]
        self.i += 1
        score_s = f" score={score:.2f}" if score is not None else ""
        msg = f"\r{frame} {scene[:24]:24}  {phase[:48]:48}{score_s}  "
        sys.stderr.write(msg)
        sys.stderr.flush()

    def done(self) -> None:
        sys.stderr.write("\n")
        sys.stderr.flush()


halo = Halo()


# ---------------------------------------------------------------------------
# Ollama integration
# ---------------------------------------------------------------------------

def ollama_chat(model: str, system: str, user: str, scene: str = "",
                  on_token: callable | None = None,
                  num_ctx: int = 32768,
                  num_predict: int = 12000,
                  temperature: float = 0.4,
                  hard_char_cap: int = 60000) -> str:
    """Stream chat completion from Ollama. num_predict caps output tokens so
    runaway generations stop. hard_char_cap is a python-side safety belt that
    aborts the stream if the model ignores num_predict.
    """
    body = {
        "model": model,
        "messages": [{"role": "system", "content": system},
                      {"role": "user", "content": user}],
        "stream": True,
        "options": {"num_ctx": num_ctx, "num_predict": num_predict,
                      "temperature": temperature,
                      "stop": ["\n\nEND_OF_PROJECT", "\n\n## END\n"]},
    }
    req = urllib.request.Request(
        f"{OLLAMA_URL}/api/chat",
        data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    out: list[str] = []
    with urllib.request.urlopen(req, timeout=600) as resp:
        for raw in resp:
            line = raw.decode("utf-8", errors="ignore").strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            chunk = obj.get("message", {}).get("content", "")
            if chunk:
                out.append(chunk)
                total = sum(len(c) for c in out)
                halo.tick(f"gen {total:>5}c", scene=scene)
                if on_token:
                    on_token(chunk)
                if total > hard_char_cap:
                    log.warning(f"[ollama] hard_char_cap {hard_char_cap} hit, stopping stream")
                    break
            if obj.get("done"):
                break
    return "".join(out)


def ollama_vision_chat(model: str, system: str, user: str, image_path: Path) -> str:
    """One-shot vision chat with an attached image (base64)."""
    import base64
    img_b64 = base64.b64encode(image_path.read_bytes()).decode("ascii")
    body = {
        "model": model,
        "messages": [{"role": "system", "content": system},
                      {"role": "user", "content": user, "images": [img_b64]}],
        "stream": False,
        "options": {"temperature": 0.1},
    }
    req = urllib.request.Request(
        f"{OLLAMA_URL}/api/chat",
        data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=180) as resp:
        obj = json.loads(resp.read().decode("utf-8"))
    return obj.get("message", {}).get("content", "")


# ---------------------------------------------------------------------------
# File extraction
# ---------------------------------------------------------------------------

_FILE_TAG = re.compile(r'<FILE\s+path="([^"]+)"\s*>(.*?)</FILE>', re.DOTALL)


def _guess_filename(lang: str, body: str, idx: int) -> str:
    """Infer a likely filename from a code block when the model forgot to
    label it. Handles the common cases we see in qwen3-coder output."""
    b = body.strip()
    lower_head = b[:300].lower()
    if lang in ("json",) or b.startswith("{"):
        if '"name"' in lower_head and '"scripts"' in lower_head and '"dependencies"' in lower_head:
            return "package.json"
        if '"compileroptions"' in lower_head.replace(" ", ""):
            return "tsconfig.json" if "tsconfig.node" not in lower_head else "tsconfig.node.json"
        return f"file_{idx}.json"
    if lang in ("tsx",) or "react" in lower_head and ("export default" in b or "function" in b):
        if "ReactDOM" in b or "createRoot" in b:
            return "src/main.tsx"
        return "src/App.tsx"
    if lang in ("ts",):
        return f"src/file_{idx}.ts"
    if lang in ("js", "javascript", "mjs"):
        if "require('express')" in b or 'require("express")' in b or "import express" in b:
            return "server.js" if "app.listen" in b else "index.js"
        return f"file_{idx}.js"
    if lang in ("html",) or "<!doctype html" in lower_head or "<html" in lower_head:
        return "index.html"
    if lang in ("css",) or "{" in b and ":" in b and ";" in b and "function" not in b[:200]:
        return "style.css" if idx == 0 else "src/index.css"
    if lang in ("py", "python",):
        if "if __name__" in b or "argparse" in b:
            return "main.py"
        return f"file_{idx}.py"
    if lang in ("bash", "sh"):
        return "run.sh"
    if lang in ("md", "markdown") or b.lstrip().startswith("#"):
        return "README.md"
    return f"file_{idx}.{lang or 'txt'}"


def extract_files(text: str) -> list[tuple[str, str]]:
    """Parse <FILE path="..."> blocks. Falls back to labeled markdown fences,
    then to language-only fences with filename inference from content.
    """
    files: list[tuple[str, str]] = []
    for m in _FILE_TAG.finditer(text):
        path = m.group(1).strip().strip("/")
        if path:
            files.append((path, m.group(2).strip("\n")))
    if files:
        return files

    # Labeled fences first: ```html title="index.html" / ```html "src/x.ts"
    md_labeled = re.compile(
        r"```(\w+)?\s*(?:title=|filename=|file=|path=)\"?([^\"\n]+\.[a-z]+)\"?\n(.*?)```",
        re.DOTALL | re.IGNORECASE,
    )
    for m in md_labeled.finditer(text):
        path = m.group(2).strip().strip("/").strip()
        files.append((path, m.group(3)))
    if files:
        return files

    # Bare fences with language: infer filename from content.
    md_bare = re.compile(r"```([A-Za-z0-9_+-]*)\s*\n(.*?)```", re.DOTALL)
    used: set[str] = set()
    for idx, m in enumerate(md_bare.finditer(text)):
        lang = (m.group(1) or "").lower()
        body = m.group(2)
        if len(body.strip()) < 4:
            continue
        path = _guess_filename(lang, body, idx)
        # avoid duplicate stable filenames -> add index suffix
        if path in used:
            stem, _, ext = path.rpartition(".")
            path = f"{stem}_{idx}.{ext}" if stem else f"{path}_{idx}"
        used.add(path)
        files.append((path, body))
    return files


def write_project(files: list[tuple[str, str]], project_dir: Path) -> int:
    project_dir.mkdir(parents=True, exist_ok=True)
    n = 0
    for rel, content in files:
        # safety: no escape from project dir
        safe = Path(rel).as_posix().replace("..", "_").lstrip("/")
        if not safe:
            continue
        out = project_dir / safe
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(content, encoding="utf-8")
        n += 1
    return n


# ---------------------------------------------------------------------------
# Preview validation
# ---------------------------------------------------------------------------

def _free_port() -> int:
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


def serve_static(project_dir: Path, port: int) -> subprocess.Popen:
    return subprocess.Popen(
        [sys.executable, "-m", "http.server", str(port), "--bind", "127.0.0.1"],
        cwd=str(project_dir),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def cdp_screenshot(url: str, out_png: Path, viewport: tuple[int, int] = (1280, 800),
                     wait_ms: int = 2500) -> tuple[bool, dict | None]:
    """Drive CDP via the helper. Returns (ok, runtime_report). The helper now
    captures console errors, exceptions, failed requests, canvas presence, body
    text length and prints them as JSON on stdout in addition to writing the PNG.
    """
    helper = REPO / "cdp_drive.mjs"
    if not helper.exists():
        log.warning(f"cdp_drive.mjs not found at {helper}")
        return False, None
    cmd = ["node", str(helper), "screenshot", url, str(out_png), str(viewport[0]),
           str(viewport[1]), str(wait_ms)]
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=90)
        report = None
        if res.stdout.strip():
            try:
                report = json.loads(res.stdout.strip().splitlines()[-1])
            except json.JSONDecodeError:
                pass
        if res.returncode != 0:
            log.warning(f"cdp_screenshot rc={res.returncode}: {res.stderr[-300:]}")
            return out_png.exists(), report
        return out_png.exists(), report
    except subprocess.TimeoutExpired:
        log.warning("cdp_screenshot timeout")
        return False, None


def syntax_check_files(project_dir: Path, files: list[tuple[str, str]]) -> dict:
    """Cheap syntax sanity per language. No execution."""
    flags = []
    for rel, _ in files:
        path = project_dir / rel
        if not path.exists():
            continue
        ext = path.suffix.lower()
        try:
            if ext == ".html":
                txt = path.read_text(encoding="utf-8")
                if "<html" not in txt.lower():
                    flags.append(f"{rel}: no <html> tag")
                if txt.count("<") < 5:
                    flags.append(f"{rel}: too few tags")
            elif ext == ".css":
                txt = path.read_text(encoding="utf-8")
                opens = txt.count("{")
                closes = txt.count("}")
                if opens != closes:
                    flags.append(f"{rel}: brace mismatch {opens}/{closes}")
            elif ext == ".js" or ext == ".mjs" or ext == ".ts" or ext == ".tsx":
                txt = path.read_text(encoding="utf-8")
                if txt.count("{") != txt.count("}"):
                    flags.append(f"{rel}: brace mismatch")
            elif ext == ".py":
                txt = path.read_text(encoding="utf-8")
                try:
                    compile(txt, str(path), "exec")
                except SyntaxError as e:
                    flags.append(f"{rel}: py syntax line {e.lineno}: {e.msg}")
        except Exception:
            pass
    return {"flags": flags, "passed": len(flags) == 0}


def score_preview_vision(image_path: Path, prompt: str) -> dict:
    """Ask qwen3-vl to rate the preview vs the original prompt (0..10)."""
    sys_msg = (
        "You are an expert code reviewer. Look at the screenshot of a webpage generated "
        "from a prompt. Rate how well it fulfills the prompt on these axes (0..10 each): "
        "fidelity to prompt, visual polish, layout quality, content completeness. "
        "Return STRICT JSON: {\"fidelity\":N,\"polish\":N,\"layout\":N,\"completeness\":N,"
        "\"notes\":\"<short>\"}"
    )
    user = f"Original prompt: {prompt!r}\nRate the screenshot."
    try:
        raw = ollama_vision_chat(VISION_MODEL, sys_msg, user, image_path)
        m = re.search(r"\{.*?\}", raw, re.DOTALL)
        if not m:
            return {"available": False, "raw": raw[:200]}
        return {"available": True, **json.loads(m.group(0))}
    except Exception as e:
        return {"available": False, "error": str(e)[:200]}


# ---------------------------------------------------------------------------
# Slug + paths
# ---------------------------------------------------------------------------

def slugify(text: str, maxlen: int = 48) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return s[:maxlen] or "scene"


def make_pack_dir(prompt: str, name: str | None) -> Path:
    iso = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
    slug = name or slugify(prompt)
    return OUTPUT_ROOT / f"{iso}-{slug}"


# ---------------------------------------------------------------------------
# State
# ---------------------------------------------------------------------------

def load_state() -> dict:
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    return {"completed": [], "failed": [], "attempts": {}}


def save_state(state: dict) -> None:
    STATE_FILE.write_text(json.dumps(state, indent=2, ensure_ascii=False), encoding="utf-8")


# ---------------------------------------------------------------------------
# Main scene runner
# ---------------------------------------------------------------------------

def process_scene(prompt: str, name: str | None, min_score: float, max_retries: int,
                    state: dict, target: Target | None = None) -> bool:
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
                port = _free_port()
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
                    server.terminate()
                    try:
                        server.wait(timeout=3)
                    except subprocess.TimeoutExpired:
                        server.kill()
        elif enriched.project_type.startswith("static_web"):
            index_html = project_dir / "index.html"
            if index_html.exists():
                halo.tick("serving preview", scene=scene_id)
                port = _free_port()
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
                target: Target | None = None) -> int:
    state = load_state()
    n_ok = 0
    for idx, entry in enumerate(queue, 1):
        scene_id = entry.get("name") or slugify(entry["prompt"])
        if scene_id in state["completed"]:
            log.info(f"[{idx}/{len(queue)}] skip {scene_id}: already completed")
            n_ok += 1
            continue
        log.info(f"[{idx}/{len(queue)}] === {scene_id} ===")
        # per-entry target override possible: entry["target"] = "my-pi"
        entry_target = target
        if entry.get("target") and entry_target is None:
            tgts = load_targets()
            entry_target = tgts.get(entry["target"])
        ok = process_scene(entry["prompt"], entry.get("name"), min_score, max_retries,
                            state, target=entry_target)
        if ok:
            state["completed"].append(scene_id)
            n_ok += 1
        else:
            if scene_id not in state["failed"]:
                state["failed"].append(scene_id)
        save_state(state)
    log.info(f"=== queue done: {n_ok}/{len(queue)} succeeded ===")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--queue", type=Path)
    ap.add_argument("--prompt", type=str)
    ap.add_argument("--name", type=str)
    ap.add_argument("--min-score", type=float, default=0.65)
    ap.add_argument("--max-retries", type=int, default=2)
    ap.add_argument("--target", type=str, default=None,
                     help="remote target name from ~/.aurora_code_targets.json (deploy + validate over SSH)")
    args = ap.parse_args()

    target = None
    if args.target:
        targets = load_targets()
        target = targets.get(args.target)
        if target is None:
            log.error(f"unknown target {args.target}. Available: {list(targets)}")
            return 2
        log.info(f"target locked: {args.target} ({target.remote()})")

    if args.prompt:
        queue = [{"prompt": args.prompt, "name": args.name}]
    elif args.queue:
        queue = json.loads(args.queue.read_text(encoding="utf-8"))
    else:
        log.error("provide --prompt or --queue")
        return 2
    return run_queue(queue, args.min_score, args.max_retries, target=target)


if __name__ == "__main__":
    sys.exit(main())
