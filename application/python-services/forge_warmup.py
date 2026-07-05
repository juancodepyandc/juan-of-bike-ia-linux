"""forge_warmup — trigger model downloads for the segment pipeline.

Submits a throw-away ComfyUI workflow that loads GroundingDINO + SAM + BiRefNet
and runs them against a 512x512 solid image. On first run the nodes auto-
download their weights (~3.5 GB total) into the ComfyUI models/ folder, which
means the FIRST real Forge run no longer hangs for 10+ minutes.

Run once after installing the custom nodes:
  python forge_warmup.py
"""
import json
import os
import sys
import time
import urllib.parse
import urllib.request
import uuid

COMFY_URL = os.environ.get("COMFY_URL", "http://127.0.0.1:8188")


def emit(pct: int, detail: str) -> None:
    print(f"PROGRESS:{pct}:{detail}", flush=True)


def post(path: str, payload: dict, timeout: int = 30) -> dict:
    data = json.dumps(payload).encode()
    req = urllib.request.Request(
        f"{COMFY_URL}{path}", data=data,
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())


def poll(prompt_id: str, timeout: int = 1800) -> dict:
    start = time.time()
    last_status = ""
    while time.time() - start < timeout:
        try:
            with urllib.request.urlopen(f"{COMFY_URL}/history/{prompt_id}", timeout=5) as r:
                hist = json.loads(r.read())
                if prompt_id in hist:
                    return hist[prompt_id]
        except Exception:
            pass
        try:
            with urllib.request.urlopen(f"{COMFY_URL}/queue", timeout=5) as r:
                q = json.loads(r.read())
                running = q.get("queue_running", [])
                if running:
                    status = f"running ({int(time.time() - start)}s)"
                    if status != last_status:
                        emit(min(5 + int((time.time() - start) / 30), 90), status)
                        last_status = status
        except Exception:
            pass
        time.sleep(2.0)
    raise TimeoutError(f"warmup timeout after {timeout}s")


def main() -> int:
    # Submit a tiny workflow that just loads the three models (they download
    # on demand the first time) and runs one trivial forward pass.
    workflow = {
        "prompt": {
            "1": {
                "class_type": "EmptyImage",
                "inputs": {"width": 512, "height": 512, "batch_size": 1, "color": 0xFFFFFF},
            },
            "2": {
                "class_type": "GroundingDinoModelLoader (segment anything)",
                "inputs": {"model_name": "GroundingDINO_SwinT_OGC (694MB)"},
            },
            "3": {
                "class_type": "SAMModelLoader (segment anything)",
                "inputs": {"model_name": "sam_vit_h (2.56GB)"},
            },
            "4": {
                "class_type": "GroundingDinoSAMSegment (segment anything)",
                "inputs": {
                    "sam_model": ["3", 0],
                    "grounding_dino_model": ["2", 0],
                    "image": ["1", 0],
                    "prompt": "a circle",
                    "threshold": 0.30,
                },
            },
            "5": {
                "class_type": "BiRefNetRMBG",
                "inputs": {"image": ["1", 0], "model": "BiRefNet-general"},
            },
            "6": {
                "class_type": "SaveImage",
                "inputs": {"images": ["4", 0], "filename_prefix": "forge_warmup"},
            },
        },
        "client_id": uuid.uuid4().hex,
    }
    emit(1, "Queueing warmup workflow (downloads ~3.5 GB on first run)")
    try:
        submit = post("/prompt", workflow)
        prompt_id = submit.get("prompt_id")
        if not prompt_id:
            print(json.dumps({"ok": False, "error": f"no prompt_id: {submit}"}))
            return 1
        emit(2, f"prompt_id={prompt_id}")
        hist = poll(prompt_id, timeout=2400)
        status = hist.get("status", {}).get("status_str") or "done"
        emit(100, f"warmup {status}")
        print(json.dumps({"ok": True, "prompt_id": prompt_id, "status": status}))
        return 0
    except Exception as e:
        print(json.dumps({"ok": False, "error": f"{type(e).__name__}: {e}"}))
        return 1


if __name__ == "__main__":
    sys.exit(main())
