"""Runtime Ollama, CDP et vision de la boucle autonome Code."""

from __future__ import annotations

import json
import logging
import os
import re
import socket
import subprocess
import sys
import time
import urllib.request
from pathlib import Path
from typing import Callable


REPO = Path(__file__).resolve().parent
OLLAMA_URL = "http://localhost:11434"
CODE_MODEL = os.environ.get("AURORA_CODE_MODEL", "qwen3-coder-next:q4_K_M")
VISION_MODEL = os.environ.get("AURORA_VISION_MODEL", "qwen3-vl:30b")
log = logging.getLogger("code-loop")

_HALO_FRAMES = [
    "[       ]", "[=      ]", "[==     ]", "[===    ]", "[====   ]", "[=====  ]", "[====== ]",
    "[=======]", "[ ======]", "[  =====]", "[   ====]", "[    ===]", "[     ==]", "[      =]",
]


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
        sys.stderr.write(f"\r{frame} {scene[:24]:24}  {phase[:48]:48}{score_s}  ")
        sys.stderr.flush()

    def done(self) -> None:
        sys.stderr.write("\n")
        sys.stderr.flush()


halo = Halo()


def ollama_chat(
    model: str,
    system: str,
    user: str,
    scene: str = "",
    on_token: Callable[[str], None] | None = None,
    num_ctx: int = 65536,
    num_predict: int = 32000,
    temperature: float = 0.4,
    hard_char_cap: int = 150000,
) -> str:
    """Stream a bounded chat completion from Ollama."""
    body = {
        "model": model,
        "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
        "stream": True,
        "options": {
            "num_ctx": num_ctx,
            "num_predict": num_predict,
            "temperature": temperature,
            "stop": ["\n\nEND_OF_PROJECT", "\n\n## END\n"],
        },
    }
    request = urllib.request.Request(
        f"{OLLAMA_URL}/api/chat",
        data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    chunks: list[str] = []
    total = 0
    with urllib.request.urlopen(request, timeout=600) as response:
        for raw in response:
            line = raw.decode("utf-8", errors="ignore").strip()
            if not line:
                continue
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                continue
            chunk = payload.get("message", {}).get("content", "")
            if chunk:
                chunks.append(chunk)
                total += len(chunk)
                halo.tick(f"gen {total:>5}c", scene=scene)
                if on_token:
                    on_token(chunk)
                if total > hard_char_cap:
                    log.warning("[ollama] hard_char_cap %s hit, stopping stream", hard_char_cap)
                    break
            if payload.get("done"):
                break
    return "".join(chunks)


def ollama_vision_chat(model: str, system: str, user: str, image_path: Path) -> str:
    import base64

    body = {
        "model": model,
        "messages": [{
            "role": "system",
            "content": system,
        }, {
            "role": "user",
            "content": user,
            "images": [base64.b64encode(image_path.read_bytes()).decode("ascii")],
        }],
        "stream": False,
        "options": {"temperature": 0.1},
    }
    request = urllib.request.Request(
        f"{OLLAMA_URL}/api/chat",
        data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=180) as response:
        payload = json.loads(response.read().decode("utf-8"))
    return payload.get("message", {}).get("content", "")


def free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def serve_static(project_dir: Path, port: int) -> subprocess.Popen:
    return subprocess.Popen(
        [sys.executable, "-m", "http.server", str(port), "--bind", "127.0.0.1"],
        cwd=str(project_dir),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def cdp_screenshot(
    url: str,
    out_png: Path,
    viewport: tuple[int, int] = (1280, 800),
    wait_ms: int = 2500,
) -> tuple[bool, dict | None]:
    """Capture a rendered page and its runtime report through the CDP helper."""
    helper = REPO / "cdp_drive.mjs"
    if not helper.exists():
        log.warning("cdp_drive.mjs not found at %s", helper)
        return False, None
    command = [
        "node", str(helper), "screenshot", url, str(out_png),
        str(viewport[0]), str(viewport[1]), str(wait_ms),
    ]
    try:
        result = subprocess.run(command, capture_output=True, text=True, timeout=90)
        report = None
        if result.stdout.strip():
            try:
                report = json.loads(result.stdout.strip().splitlines()[-1])
            except json.JSONDecodeError:
                pass
        if result.returncode != 0:
            log.warning("cdp_screenshot rc=%s: %s", result.returncode, result.stderr[-300:])
            return out_png.exists(), report
        return out_png.exists(), report
    except subprocess.TimeoutExpired:
        log.warning("cdp_screenshot timeout")
        return False, None


def score_preview_vision(image_path: Path, prompt: str) -> dict:
    system = (
        "You are an expert code reviewer. Rate this rendered webpage from 0 to 10 for fidelity, "
        "visual polish, layout quality, and content completeness. Return strict JSON: "
        '{"fidelity":N,"polish":N,"layout":N,"completeness":N,"notes":"short"}'
    )
    try:
        raw = ollama_vision_chat(VISION_MODEL, system, f"Original prompt: {prompt!r}\nRate the screenshot.", image_path)
        match = re.search(r"\{.*?\}", raw, re.DOTALL)
        if not match:
            return {"available": False, "raw": raw[:200]}
        return {"available": True, **json.loads(match.group(0))}
    except Exception as error:
        return {"available": False, "error": str(error)[:200]}
