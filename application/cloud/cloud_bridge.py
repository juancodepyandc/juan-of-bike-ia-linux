"""
AuroraIA-v2 Cloud Bridge
Remplace les appels Tauri IPC par une API HTTP.
Proxy Ollama + ComfyUI + execution Python + filesystem + voix.
Port par defaut: 3101 (3001 est parfois reserve par RunPod/nginx).
"""

import asyncio
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from uuid import uuid4

import httpx
import uvicorn
from fastapi import FastAPI, Request, Response, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

WORKSPACE = Path(os.environ.get("AURORA_WORKSPACE", "/workspace/aurora"))
OUTPUT = Path(os.environ.get("AURORA_OUTPUT", "/workspace/output"))
MODELS = Path(os.environ.get("AURORA_MODELS", "/workspace/models"))
PYTHON_SERVICES = WORKSPACE / "python-services"
OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://127.0.0.1:11434")
COMFY_URL = os.environ.get("COMFY_URL", "http://127.0.0.1:8188")
COMFYUI_DIR = Path(os.environ.get("COMFYUI_DIR", "/workspace/comfyui"))

# Headers that must NOT be forwarded to upstream services (Ollama, ComfyUI).
# The browser sends Origin/Referer pointing at the RunPod proxy URL, which
# Ollama and ComfyUI reject with 403 because they only trust localhost.
_PROXY_STRIP_HEADERS = frozenset({
    "host", "content-length", "transfer-encoding",
    "origin", "referer", "cookie", "sec-fetch-site", "sec-fetch-mode",
    "sec-fetch-dest", "sec-ch-ua", "sec-ch-ua-mobile", "sec-ch-ua-platform",
})

app = FastAPI(title="AuroraIA Cloud Bridge", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["Content-Disposition"],
)

# ---------------------------------------------------------------------------
# Progress tracking (global, for onPythonProgress polling)
# ---------------------------------------------------------------------------

_progress_events: list[str] = []
_progress_lock = asyncio.Lock()


async def _push_progress(event: str):
    async with _progress_lock:
        _progress_events.append(event)
        if len(_progress_events) > 500:
            _progress_events[:] = _progress_events[-200:]


def _python_service_env() -> dict[str, str]:
    env = {**os.environ, "PYTHONUNBUFFERED": "1"}
    cache_root = MODELS / "cache"
    env.setdefault("AURORA_MODELS", str(MODELS))
    env.setdefault("COMFYUI_DIR", str(COMFYUI_DIR))
    env.setdefault("HF_HOME", str(cache_root / "huggingface"))
    env.setdefault("HF_HUB_CACHE", str(cache_root / "huggingface" / "hub"))
    env.setdefault("HUGGINGFACE_HUB_CACHE", str(cache_root / "huggingface" / "hub"))
    env.setdefault("TRANSFORMERS_CACHE", str(cache_root / "huggingface" / "transformers"))
    env.setdefault("HF_DATASETS_CACHE", str(cache_root / "huggingface" / "datasets"))
    env.setdefault("TORCH_HOME", str(cache_root / "torch"))
    env.setdefault("XDG_CACHE_HOME", str(cache_root / "xdg"))
    env.setdefault("U2NET_HOME", str(cache_root / "u2net"))
    return env


@app.get("/api/python/progress")
async def get_progress(since: int = 0):
    async with _progress_lock:
        return {"events": _progress_events[since:], "cursor": len(_progress_events)}


# ---------------------------------------------------------------------------
# 1. Hardware detection + Cloud tier
# ---------------------------------------------------------------------------

def _detect_gpu():
    try:
        import torch
        if torch.cuda.is_available():
            return {
                "name": torch.cuda.get_device_name(0),
                "vram_gb": round(torch.cuda.get_device_properties(0).total_mem / 1e9, 1),
                "vram_free_gb": round(torch.cuda.mem_get_info(0)[0] / 1e9, 1),
            }
    except Exception:
        pass

    try:
        out = subprocess.check_output(
            [
                "nvidia-smi",
                "--query-gpu=name,memory.total,memory.free",
                "--format=csv,noheader,nounits",
            ],
            text=True,
            timeout=5,
        ).strip().splitlines()[0]
        name, total_mb, free_mb = [part.strip() for part in out.split(",", 2)]
        return {
            "name": name,
            "vram_gb": round(float(total_mb) / 1024, 1),
            "vram_free_gb": round(float(free_mb) / 1024, 1),
        }
    except Exception:
        pass

    return {"name": "CPU", "vram_gb": 0, "vram_free_gb": 0}


@app.get("/api/hardware")
async def get_hardware():
    gpu = _detect_gpu()
    try:
        ram_gb = round(os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES") / 1e9, 1)
    except Exception:
        ram_gb = 0
    try:
        cpu_name = "Cloud CPU"
        with open("/proc/cpuinfo") as f:
            for line in f:
                if "model name" in line:
                    cpu_name = line.split(":")[1].strip()
                    break
    except Exception:
        cpu_name = "Cloud CPU"

    return {
        "os": "Linux (RunPod Cloud)",
        "cpu": cpu_name,
        "cores": os.cpu_count() or 8,
        "ram_gb": ram_gb,
        "gpu": gpu["name"],
        "vram_gb": gpu["vram_gb"],
        "vram_free_gb": gpu["vram_free_gb"],
    }


@app.get("/api/cloud/tier")
async def get_cloud_tier():
    """Retourne le tier GPU (low/mid/high) et les modeles recommandes."""
    gpu = _detect_gpu()
    vram = gpu["vram_gb"]

    if vram >= 70:
        tier = "high"
        models = {
            "main": "llama4:scout",
            "code": "qwen3-coder:30b-a3b-q8_0",
            "vision": "qwen3-vl:30b",
            "image": "flux1-dev-fp8.safetensors",
            "video": "Wan-AI/Wan2.2-T2V-A14B-Diffusers",
            "threeD": "tencent/Hunyuan3D-2.1",
            "stt": "mistralai/Voxtral-Small-24B-2507",
            "tts": "hexgrad/Kokoro-82M",
        }
    elif vram >= 40:
        tier = "mid"
        models = {
            "main": "qwen3:30b",
            "code": "qwen3-coder:30b-a3b-q4_K_M",
            "vision": "qwen3-vl:30b",
            "image": "flux1-dev-fp8.safetensors",
            "video": "Wan-AI/Wan2.2-T2V-A14B-Diffusers",
            "threeD": "tencent/Hunyuan3D-2.1",
            "stt": "mistralai/Voxtral-Small-24B-2507",
            "tts": "hexgrad/Kokoro-82M",
        }
    else:
        tier = "low"
        models = {
            "main": "qwen3:14b-q8_0",
            "code": "qwen2.5-coder:14b-q8_0",
            "vision": "qwen3-vl:8b",
            "image": "flux1-schnell-fp8.safetensors",
            "video": "Lightricks/LTX-Video",
            "threeD": "tencent/Hunyuan3D-2.1",
            "stt": "openai/whisper-large-v3",
            "tts": "hexgrad/Kokoro-82M",
        }

    return {
        "tier": tier,
        "gpu": gpu["name"],
        "vram_gb": vram,
        "models": models,
    }


# ---------------------------------------------------------------------------
# 2. Ollama reverse proxy
# ---------------------------------------------------------------------------

@app.api_route("/proxy/ollama/{path:path}", methods=["GET", "POST", "DELETE", "PUT"])
async def proxy_ollama(path: str, request: Request):
    url = f"{OLLAMA_URL}/{path}"
    if str(request.query_params):
        url += f"?{request.query_params}"

    body = await request.body()
    headers = {
        k: v for k, v in request.headers.items()
        if k.lower() not in _PROXY_STRIP_HEADERS
    }

    is_stream = b'"stream":true' in body or b'"stream": true' in body

    if is_stream:
        # Keep-alive: a producer task streams Ollama into an asyncio.Queue, while
        # the response generator emits a newline every 10 seconds if no real chunk
        # has landed yet. This prevents Cloudflare / RunPod from killing the
        # connection with a 524 during Ollama's cold model load.
        # Newlines are valid ndjson separators and are ignored by the client
        # assembler which only parses non-empty JSON frames.
        async def heartbeat_or_payload():
            q: asyncio.Queue[bytes | None] = asyncio.Queue()

            async def producer():
                client = httpx.AsyncClient(timeout=httpx.Timeout(1800, connect=15))
                try:
                    req = client.build_request(request.method, url, content=body, headers=headers)
                    resp = await client.send(req, stream=True)
                    async for chunk in resp.aiter_bytes():
                        await q.put(chunk)
                except Exception as exc:
                    await q.put(f'{{"error":"proxy failed: {type(exc).__name__}"}}\n'.encode())
                finally:
                    await q.put(None)
                    await client.aclose()

            task = asyncio.create_task(producer())
            try:
                # Send the first heartbeat immediately so tunnels flush headers.
                yield b"\n"
                while True:
                    try:
                        chunk = await asyncio.wait_for(q.get(), timeout=10)
                    except asyncio.TimeoutError:
                        yield b"\n"
                        continue
                    if chunk is None:
                        break
                    yield chunk
            finally:
                task.cancel()

        return StreamingResponse(
            heartbeat_or_payload(),
            media_type="application/x-ndjson",
            headers={
                "X-Accel-Buffering": "no",  # nginx: disable response buffering
                "Cache-Control": "no-cache, no-transform",
                "Connection": "keep-alive",
            },
        )

    async with httpx.AsyncClient(timeout=httpx.Timeout(600, connect=15)) as client:
        resp = await client.request(request.method, url, content=body, headers=headers)
        return Response(
            content=resp.content,
            status_code=resp.status_code,
            media_type=resp.headers.get("content-type", "application/json"),
        )


# ---------------------------------------------------------------------------
# 3. ComfyUI reverse proxy
# ---------------------------------------------------------------------------

@app.api_route("/proxy/comfy/{path:path}", methods=["GET", "POST", "DELETE", "PUT"])
async def proxy_comfy(path: str, request: Request):
    url = f"{COMFY_URL}/{path}"
    if str(request.query_params):
        url += f"?{request.query_params}"

    body = await request.body()
    headers = {
        k: v for k, v in request.headers.items()
        if k.lower() not in _PROXY_STRIP_HEADERS
    }

    async with httpx.AsyncClient(timeout=httpx.Timeout(600, connect=15)) as client:
        resp = await client.request(request.method, url, content=body, headers=headers)
        return Response(
            content=resp.content,
            status_code=resp.status_code,
            media_type=resp.headers.get("content-type"),
        )


# ---------------------------------------------------------------------------
# 4. Python script execution (avec streaming progress)
# ---------------------------------------------------------------------------

@app.post("/api/python/run")
async def run_python_script(request: dict):
    """Execute un script python-services/ avec streaming PROGRESS."""
    script_name = request.get("scriptPath", "")
    args = request.get("args", [])

    # Securite : restreindre aux scripts dans python-services/
    script_path = PYTHON_SERVICES / Path(script_name).name
    if not script_path.exists():
        # Essayer le chemin complet si c'est un chemin absolu du workspace
        if Path(script_name).exists():
            script_path = Path(script_name)
        else:
            return JSONResponse(
                {"error": f"Script introuvable: {script_name}", "output": ""},
                status_code=404,
            )

    async with _progress_lock:
        _progress_events.clear()

    proc = await asyncio.create_subprocess_exec(
        sys.executable, str(script_path), *[str(a) for a in args],
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        cwd=str(WORKSPACE),
        env=_python_service_env(),
    )

    stdout_lines: list[str] = []

    async def _read_stdout():
        while True:
            line = await proc.stdout.readline()
            if not line:
                break
            text = line.decode("utf-8", errors="replace").rstrip()
            stdout_lines.append(text)
            if text.startswith("PROGRESS:"):
                await _push_progress(text)

    await _read_stdout()
    await proc.wait()

    stderr_data = (await proc.stderr.read()).decode("utf-8", errors="replace")
    full_output = "\n".join(stdout_lines)

    return {
        "output": full_output,
        "error": stderr_data,
        "exitCode": proc.returncode,
    }


# ---------------------------------------------------------------------------
# 5. Workspace commands
# ---------------------------------------------------------------------------

@app.post("/api/command/run")
async def run_command(request: dict):
    executable = request.get("executable", "")
    args = request.get("args", [])
    cwd = request.get("cwd", str(WORKSPACE))
    timeout_ms = request.get("timeoutMs", 120000)

    try:
        proc = await asyncio.create_subprocess_exec(
            executable, *[str(a) for a in args],
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=cwd,
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout_ms / 1000)
        output = stdout.decode("utf-8", errors="replace") + stderr.decode("utf-8", errors="replace")
        return {
            "ok": proc.returncode == 0,
            "exitCode": proc.returncode,
            "output": output,
            "command": f"{executable} {' '.join(str(a) for a in args)}",
        }
    except asyncio.TimeoutError:
        return {"ok": False, "exitCode": -1, "output": "Timeout", "command": executable}
    except Exception as e:
        return {"ok": False, "exitCode": -1, "output": str(e), "command": executable}


@app.post("/api/command/spawn")
async def spawn_command(request: dict):
    executable = request.get("executable", "")
    args = request.get("args", [])
    cwd = request.get("cwd", str(WORKSPACE))

    try:
        proc = await asyncio.create_subprocess_exec(
            executable, *[str(a) for a in args],
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
            cwd=cwd,
        )
        return {
            "ok": True,
            "pid": proc.pid,
            "command": f"{executable} {' '.join(str(a) for a in args)}",
            "stdoutLog": None,
            "stderrLog": None,
        }
    except Exception as e:
        return {"ok": False, "pid": 0, "command": executable, "stdoutLog": None, "stderrLog": None}


# ---------------------------------------------------------------------------
# 6. Filesystem operations
# ---------------------------------------------------------------------------

@app.post("/api/fs/exists")
async def fs_exists(request: dict):
    return {"exists": Path(request["path"]).exists()}


@app.post("/api/fs/mkdir")
async def fs_mkdir(request: dict):
    Path(request["path"]).mkdir(parents=True, exist_ok=True)
    return {"ok": True}


@app.post("/api/fs/read-text")
async def fs_read_text(request: dict):
    p = Path(request["path"])
    if not p.exists():
        return JSONResponse({"error": "Fichier introuvable"}, status_code=404)
    return {"content": p.read_text(encoding="utf-8", errors="replace")}


@app.post("/api/fs/write-text")
async def fs_write_text(request: dict):
    p = Path(request["path"])
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(request["content"], encoding="utf-8")
    return {"ok": True}


@app.post("/api/fs/write-binary")
async def fs_write_binary(request: dict):
    p = Path(request["path"])
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(bytes(request["bytes"]))
    return {"ok": True}


@app.post("/api/fs/read-binary")
async def fs_read_binary(request: dict):
    p = Path(request["path"])
    if not p.exists():
        return JSONResponse({"error": "Fichier introuvable"}, status_code=404)
    return {"bytes": list(p.read_bytes())}


@app.get("/api/fs/workspace-path")
async def get_workspace_path():
    return {"path": str(WORKSPACE)}


# ---------------------------------------------------------------------------
# 7. Voice STT
# ---------------------------------------------------------------------------

@app.post("/api/voice/stt")
async def voice_stt(audio: UploadFile = File(...)):
    temp_dir = OUTPUT / "temp"
    temp_dir.mkdir(parents=True, exist_ok=True)
    temp_path = temp_dir / f"stt_{uuid4().hex[:8]}.webm"

    content = await audio.read()
    temp_path.write_bytes(content)

    try:
        proc = await asyncio.create_subprocess_exec(
            sys.executable, str(PYTHON_SERVICES / "voice_service.py"),
            "--mode", "stt", "--audio", str(temp_path),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=str(WORKSPACE),
            env=_python_service_env(),
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=120)
        output = stdout.decode("utf-8", errors="replace")

        for line in reversed(output.strip().split("\n")):
            line = line.strip()
            if line.startswith("{"):
                try:
                    result = json.loads(line)
                    if result.get("text"):
                        return result
                except json.JSONDecodeError:
                    pass

        return {"ok": False, "text": "", "error": f"STT sans resultat: {output[:300]}"}
    except asyncio.TimeoutError:
        return {"ok": False, "text": "", "error": "STT timeout (120s)"}
    finally:
        temp_path.unlink(missing_ok=True)


# ---------------------------------------------------------------------------
# 8. Voice TTS
# ---------------------------------------------------------------------------

@app.post("/api/voice/tts")
async def voice_tts(request: dict):
    text = request.get("text", "")
    lang = request.get("lang", "fr")

    temp_dir = OUTPUT / "temp"
    temp_dir.mkdir(parents=True, exist_ok=True)
    output_path = temp_dir / f"tts_{uuid4().hex[:8]}.wav"

    try:
        proc = await asyncio.create_subprocess_exec(
            sys.executable, str(PYTHON_SERVICES / "voice_service.py"),
            "--mode", "tts",
            "--text", text,
            "--output", str(output_path),
            "--lang", lang,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=str(WORKSPACE),
            env=_python_service_env(),
        )
        await asyncio.wait_for(proc.communicate(), timeout=60)

        if output_path.exists() and output_path.stat().st_size > 0:
            return FileResponse(str(output_path), media_type="audio/wav")

        return JSONResponse({"error": "TTS n'a produit aucun audio"}, status_code=500)
    except asyncio.TimeoutError:
        return JSONResponse({"error": "TTS timeout (60s)"}, status_code=500)


# ---------------------------------------------------------------------------
# 8b. Web helpers — text snippets + real image download with fallback pipeline
# ---------------------------------------------------------------------------

import base64
import re as _re
import urllib.parse as _urlparse


def _strip_html(raw: str) -> str:
    return _re.sub(r"<[^>]+>", " ", raw or "").replace("&amp;", "&").replace("&quot;", '"').strip()


async def _duckduckgo_search_html(query: str, limit: int = 6) -> list[dict]:
    """Scrape DuckDuckGo's HTML results for snippet-only text. Best-effort, no key."""
    q = _urlparse.quote(query)
    url = f"https://html.duckduckgo.com/html/?q={q}"
    async with httpx.AsyncClient(timeout=8, headers={"User-Agent": "Mozilla/5.0 (compatible; AuroraIA/2.0)"}) as c:
        try:
            resp = await c.get(url)
            if resp.status_code != 200:
                return []
            html = resp.text
        except Exception:
            return []
    results: list[dict] = []
    for m in _re.finditer(r'class="result__title"[^>]*>\s*<a[^>]*href="([^"]+)"[^>]*>(.*?)</a>', html, _re.S):
        link = m.group(1)
        title = _strip_html(m.group(2))[:120]
        if title and link:
            results.append({"title": title, "url": link})
        if len(results) >= limit:
            break
    return results


@app.post("/api/web/search")
async def web_search(request: dict):
    query = (request.get("query") or "").strip()
    limit = int(request.get("limit") or 6)
    if not query:
        return {"results": "", "items": []}
    items = await _duckduckgo_search_html(query, limit=limit)
    flat = "\n".join(f"{i+1}. {it['title']} — {it['url']}" for i, it in enumerate(items))
    return {"results": flat, "items": items}


_IMAGE_CACHE: dict[str, dict] = {}


async def _fetch_image_bytes(target: str) -> tuple[bytes | None, str | None]:
    try:
        async with httpx.AsyncClient(timeout=20, follow_redirects=True,
                                     headers={"User-Agent": "Mozilla/5.0 AuroraIA"}) as c:
            r = await c.get(target)
            if r.status_code == 200 and r.content and len(r.content) > 1024:
                ct = r.headers.get("content-type", "image/jpeg").split(";")[0].strip()
                return r.content, ct or "image/jpeg"
    except Exception:
        pass
    return None, None


@app.post("/api/web/image")
async def web_image(request: dict):
    """Search for an image matching `query` and return it as a data URL.

    Strategy (best-effort):
      1. LoremFlickr (returns a random relevant photo).
      2. Fallback: pull the first direct image link that appears in a DuckDuckGo
         image search HTML. Since those are brittle, LoremFlickr is tried first.

    Always returns {"ok": bool, "dataUrl": "data:image/...;base64,...", "source": "..."}.
    The frontend stores the returned dataUrl directly as assets/images/<name>.txt and
    the prompt injects it in the <img src="..."> — so the HTML is fully offline-safe
    and can never 404, regardless of where the user saves the project later.
    """
    query = (request.get("query") or "").strip()
    if not query:
        return JSONResponse({"ok": False, "error": "empty query"}, status_code=400)

    cache_key = query.lower()
    cached = _IMAGE_CACHE.get(cache_key)
    if cached:
        return cached

    # LoremFlickr
    width = int(request.get("width") or 1200)
    height = int(request.get("height") or 800)
    candidates = [
        f"https://loremflickr.com/{width}/{height}/{_urlparse.quote(query)}",
    ]
    for cand in candidates:
        raw, ct = await _fetch_image_bytes(cand)
        if raw and ct:
            data_url = f"data:{ct};base64,{base64.b64encode(raw).decode('ascii')}"
            payload = {"ok": True, "dataUrl": data_url, "source": cand, "bytes": len(raw)}
            _IMAGE_CACHE[cache_key] = payload
            if len(_IMAGE_CACHE) > 128:
                _IMAGE_CACHE.pop(next(iter(_IMAGE_CACHE)))
            return payload

    return JSONResponse({"ok": False, "error": "no image found via LoremFlickr"}, status_code=502)


# ---------------------------------------------------------------------------
# 9. Service status
# ---------------------------------------------------------------------------

@app.get("/api/services/status")
async def services_status():
    ollama_ok = False
    comfy_ok = False
    async with httpx.AsyncClient(timeout=5) as client:
        try:
            r = await client.get(f"{OLLAMA_URL}/api/tags")
            ollama_ok = r.status_code == 200
        except Exception:
            pass
        try:
            r = await client.get(f"{COMFY_URL}/system_stats")
            comfy_ok = r.status_code == 200
        except Exception:
            pass
    return {"ollama": ollama_ok, "comfyui": comfy_ok}


@app.get("/api/comfyui/status")
async def comfyui_status():
    """Etat instantane de ComfyUI — compatible avec ensureComfyUIRunning() cote frontend."""
    comfy_ok = False
    async with httpx.AsyncClient(timeout=3) as client:
        try:
            r = await client.get(f"{COMFY_URL}/system_stats")
            comfy_ok = r.status_code == 200
        except Exception:
            pass
    return {"ok": True, "running": comfy_ok, "port": 8188}


_comfy_start_lock = asyncio.Lock()


async def _ping_comfy(timeout_s: float = 3.0) -> bool:
    try:
        async with httpx.AsyncClient(timeout=timeout_s) as client:
            r = await client.get(f"{COMFY_URL}/system_stats")
            return r.status_code == 200
    except Exception:
        return False


async def _spawn_comfy_process() -> tuple[bool, str]:
    """Lance `python main.py --listen 0.0.0.0 --port 8188` depuis COMFYUI_DIR.

    Retourne (ok, detail). Si ComfyUI est deja actif, renvoie (True, "...").
    """
    main_py = COMFYUI_DIR / "main.py"
    if not main_py.exists():
        return False, f"ComfyUI introuvable: {main_py} absent (COMFYUI_DIR={COMFYUI_DIR})."

    log_path = Path("/tmp/comfyui.log") if os.name != "nt" else (OUTPUT / "temp" / "comfyui.log")
    log_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        with open(log_path, "ab") as log_fp:
            log_fp.write(b"\n[bridge] start comfyui " + time.strftime("%Y-%m-%d %H:%M:%S").encode() + b"\n")
            await asyncio.create_subprocess_exec(
                sys.executable, str(main_py),
                "--listen", "0.0.0.0",
                "--port", "8188",
                "--enable-cors-header", "*",
                stdout=log_fp,
                stderr=log_fp,
                cwd=str(COMFYUI_DIR),
                env={**os.environ, "PYTHONUNBUFFERED": "1"},
            )
    except Exception as exc:
        return False, f"Echec spawn ComfyUI: {type(exc).__name__}: {exc}"

    return True, f"ComfyUI spawn declenche (log: {log_path})."


@app.post("/api/comfyui/start")
async def comfyui_start():
    """Demarre ComfyUI si absent. Idempotent: renvoie ready:true si deja actif.

    Fait un spawn de `python main.py --listen 0.0.0.0 --port 8188` dans COMFYUI_DIR,
    puis attend jusqu a 90 secondes que /system_stats reponde.
    """
    if await _ping_comfy(3.0):
        return {"ok": True, "ready": True, "port": 8188, "detail": "deja actif"}

    async with _comfy_start_lock:
        if await _ping_comfy(3.0):
            return {"ok": True, "ready": True, "port": 8188, "detail": "deja actif (apres lock)"}

        spawned, detail = await _spawn_comfy_process()
        if not spawned:
            return JSONResponse(
                {"ok": False, "ready": False, "error": detail},
                status_code=500,
            )

        for _ in range(45):
            await asyncio.sleep(2)
            if await _ping_comfy(2.0):
                await _push_progress("PROGRESS:comfyui:ComfyUI pret (auto-start)")
                return {"ok": True, "ready": True, "port": 8188, "detail": detail}

        try:
            tail_path = Path("/tmp/comfyui.log")
            tail = tail_path.read_text(errors="replace").splitlines()[-20:] if tail_path.exists() else []
        except Exception:
            tail = []
        return JSONResponse(
            {
                "ok": False, "ready": False,
                "error": "ComfyUI a ete lance mais ne repond pas sur /system_stats apres 90 secondes.",
                "log_tail": tail,
            },
            status_code=504,
        )


# ---------------------------------------------------------------------------
# 10. Runtime stubs (services geres par start.sh)
# ---------------------------------------------------------------------------

def _normalize_ollama_name(name: str) -> str:
    return (name or "").strip().removesuffix(":latest")


async def _ollama_model_names() -> list[str]:
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(f"{OLLAMA_URL}/api/tags")
        resp.raise_for_status()
        data = resp.json()
    return [
        str(model.get("name", "")).strip()
        for model in data.get("models", [])
        if model.get("name")
    ]


async def _ensure_ollama_model(model: str) -> dict:
    model = (model or "").strip()
    if not model:
        return {"ok": True, "detail": "Aucun modele Ollama demande."}

    installed = await _ollama_model_names()
    installed_normalized = {_normalize_ollama_name(name) for name in installed}
    if _normalize_ollama_name(model) in installed_normalized:
        return {"ok": True, "detail": f"{model} deja present dans Ollama."}

    await _push_progress(f"PROGRESS:ollama:Telechargement modele Ollama {model}...")
    try:
        proc = await asyncio.create_subprocess_exec(
            "ollama", "pull", model,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=str(WORKSPACE),
            env={**os.environ, "OLLAMA_MODELS": os.environ.get("OLLAMA_MODELS", str(OUTPUT.parent / "models" / "ollama"))},
        )
    except FileNotFoundError:
        return {"ok": False, "detail": "ollama introuvable dans le PATH du Cloud Bridge."}

    stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=7200)
    if proc.returncode != 0:
        output = (
            stdout.decode("utf-8", errors="replace")
            + stderr.decode("utf-8", errors="replace")
        ).strip()
        return {
            "ok": False,
            "detail": f"Pull Ollama echoue pour {model}: {output[-800:]}",
        }

    await _push_progress(f"PROGRESS:ollama:Modele {model} pret.")
    return {"ok": True, "detail": f"{model} telecharge et pret."}

def _build_service_info(
    service_id: str,
    is_running: bool,
    detail: str = "",
) -> dict:
    """Return a dict matching the TypeScript RuntimeServiceInfo shape."""
    comfy_path = str(COMFYUI_DIR) if service_id == "comfyui" else None
    return {
        "id": service_id,
        "label": "Ollama" if service_id == "ollama" else "ComfyUI",
        "available": True,
        "running": is_running,
        "startedByApp": False,
        "progress": 100 if is_running else 0,
        "detail": detail or ("Cloud managed by start.sh" if is_running else "Service pas encore pret"),
        "path": comfy_path,
        "processId": None,
    }


@app.post("/api/runtime/ensure-service")
async def runtime_ensure_service(request: dict):
    service = request.get("service", "unknown")
    status = await services_status()
    if service == "ollama":
        return _build_service_info(
            "ollama",
            status["ollama"],
            f"Listening on {OLLAMA_URL}" if status["ollama"] else "Ollama ne repond pas encore sur le cloud.",
        )
    if service == "comfyui":
        return _build_service_info(
            "comfyui",
            status["comfyui"],
            f"Listening on {COMFY_URL}" if status["comfyui"] else "ComfyUI ne repond pas encore sur le cloud.",
        )
    return {
        "id": service,
        "label": service,
        "available": False,
        "running": False,
        "startedByApp": False,
        "progress": 0,
        "detail": f"Service inconnu: {service}",
        "path": None,
        "processId": None,
    }


@app.post("/api/runtime/prepare-model")
async def runtime_prepare_model(request: dict):
    model = request.get("model") or request.get("name") or request.get("target") or ""
    try:
        return await _ensure_ollama_model(str(model))
    except asyncio.TimeoutError:
        return {"ok": False, "detail": f"Timeout pendant le pull Ollama de {model}."}
    except Exception as exc:
        return {"ok": False, "detail": f"Preparation modele Ollama echouee: {exc}"}


@app.get("/api/runtime/inspect")
async def runtime_inspect():
    status = await services_status()
    return [
        _build_service_info("ollama", status["ollama"], f"Listening on {OLLAMA_URL}" if status["ollama"] else "Ollama pas encore pret"),
        _build_service_info("comfyui", status["comfyui"], f"Listening on {COMFY_URL}" if status["comfyui"] else "ComfyUI pas encore pret"),
    ]


@app.get("/api/runtime/privilege")
async def runtime_privilege():
    return {"isAdmin": True, "canElevate": False, "detail": "Cloud root access"}


# ---------------------------------------------------------------------------
# 11. Asset serving
# ---------------------------------------------------------------------------

@app.get("/api/asset/{path:path}")
async def serve_asset(path: str):
    for base in [OUTPUT, WORKSPACE]:
        file_path = base / path
        if file_path.exists() and file_path.is_file():
            return FileResponse(str(file_path))

    return JSONResponse({"error": f"Asset introuvable: {path}"}, status_code=404)


# ---------------------------------------------------------------------------
# 12. Download / List results
# ---------------------------------------------------------------------------

RESULT_CATEGORIES = ["images", "videos", "models3d", "voice", "saves"]


@app.get("/api/download/list")
async def list_results():
    results = {}
    for cat in RESULT_CATEGORIES:
        cat_path = OUTPUT / cat
        if cat_path.exists():
            files = []
            for f in sorted(cat_path.iterdir(), key=lambda x: x.stat().st_mtime, reverse=True):
                if f.is_file():
                    files.append({
                        "name": f.name,
                        "size": f.stat().st_size,
                        "modified": f.stat().st_mtime,
                    })
            results[cat] = files

    comfy_output = COMFYUI_DIR / "output"
    if comfy_output.exists():
        image_files = results.setdefault("images", [])
        known_names = {item["name"] for item in image_files}
        for f in sorted(comfy_output.iterdir(), key=lambda x: x.stat().st_mtime, reverse=True):
            if f.is_file() and f.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp"} and f.name not in known_names:
                image_files.append({
                    "name": f.name,
                    "size": f.stat().st_size,
                    "modified": f.stat().st_mtime,
                    "source": "comfyui",
                })
    return results


@app.get("/api/download/{category}/{filename}")
async def download_result(category: str, filename: str):
    file_path = OUTPUT / category / filename
    if category == "images" and not file_path.exists():
        comfy_file_path = COMFYUI_DIR / "output" / filename
        if comfy_file_path.exists():
            file_path = comfy_file_path
    if not file_path.exists():
        return JSONResponse({"error": "Fichier introuvable"}, status_code=404)
    return FileResponse(
        str(file_path),
        filename=filename,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# ---------------------------------------------------------------------------
# 13. Health check
# ---------------------------------------------------------------------------

@app.get("/api/health")
async def health():
    gpu = _detect_gpu()
    return {
        "status": "ok",
        "gpu": gpu["name"],
        "vram_gb": gpu["vram_gb"],
        "workspace": str(WORKSPACE),
        "output": str(OUTPUT),
    }


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    for d in [OUTPUT / cat for cat in RESULT_CATEGORIES] + [OUTPUT / "temp"]:
        d.mkdir(parents=True, exist_ok=True)

    print(f"[CloudBridge] Workspace: {WORKSPACE}")
    print(f"[CloudBridge] Output:    {OUTPUT}")
    print(f"[CloudBridge] Ollama:    {OLLAMA_URL}")
    print(f"[CloudBridge] ComfyUI:   {COMFY_URL}")

    bridge_port = int(os.environ.get("AURORA_BRIDGE_PORT", "3101"))
    uvicorn.run(app, host="0.0.0.0", port=bridge_port, log_level="info")
