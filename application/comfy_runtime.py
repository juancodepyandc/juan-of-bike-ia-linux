"""Select ComfyUI memory options and coordinate GPU VRAM with Ollama."""
from __future__ import annotations

import json
import os
from pathlib import Path
import shlex
import subprocess
import sys
import urllib.request


def gpu_status() -> dict[str, object]:
    """Return live NVIDIA GPU, driver, kernel and VRAM availability."""
    kernel = os.uname().release if hasattr(os, "uname") else "unknown"
    try:
        result = subprocess.run(
            [
                "nvidia-smi",
                "--query-gpu=name,driver_version,memory.total,memory.used,memory.free",
                "--format=csv,noheader,nounits",
            ],
            capture_output=True,
            text=True,
            timeout=5,
            check=True,
        )
        lines = [line.strip() for line in result.stdout.splitlines() if line.strip()]
        if not lines:
            return {"available": False, "kernel": kernel, "gpus": []}
        gpus = []
        for line in lines:
            parts = [p.strip() for p in line.split(",")]
            if len(parts) >= 5:
                gpus.append({
                    "name": parts[0],
                    "driver_version": parts[1],
                    "total_vram_mib": int(parts[2]),
                    "used_vram_mib": int(parts[3]),
                    "free_vram_mib": int(parts[4]),
                })
        return {
            "available": len(gpus) > 0,
            "kernel": kernel,
            "gpu_name": gpus[0]["name"] if gpus else None,
            "driver_version": gpus[0]["driver_version"] if gpus else None,
            "total_vram_mib": sum(g["total_vram_mib"] for g in gpus),
            "used_vram_mib": sum(g["used_vram_mib"] for g in gpus),
            "free_vram_mib": sum(g["free_vram_mib"] for g in gpus),
            "gpus": gpus,
        }
    except (OSError, ValueError, subprocess.SubprocessError):
        return {"available": False, "kernel": kernel, "gpus": []}


def reclaim_ollama_vram(ollama_url: str | None = None) -> list[str]:
    """Unload currently resident Ollama models (keep_alive=0) to free GPU VRAM before heavy 3D/Image jobs."""
    base = (ollama_url or os.environ.get("OLLAMA_URL", "http://127.0.0.1:11434")).rstrip("/")
    unloaded: list[str] = []
    try:
        with urllib.request.urlopen(f"{base}/api/ps", timeout=5) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        for item in data.get("models", []):
            name = item.get("name") or item.get("model")
            if not isinstance(name, str) or not name:
                continue
            payload = json.dumps({"model": name, "keep_alive": 0}).encode("utf-8")
            req = urllib.request.Request(
                f"{base}/api/generate",
                data=payload,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            try:
                with urllib.request.urlopen(req, timeout=10):
                    unloaded.append(name)
            except OSError:
                continue
    except (OSError, ValueError):
        pass
    return unloaded


def memory_args(comfy_dir: Path) -> list[str]:
    """Keep FLUX.2 GGUF dequantization within a small CUDA device's budget."""
    override = os.environ.get("AURORA_COMFY_ARGS")
    if override is not None:
        return shlex.split(override)
    try:
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=memory.total", "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=5, check=True,
        )
        totals = [int(line.strip()) for line in result.stdout.splitlines() if line.strip()]
        if not totals or min(totals) > 20480:
            return []
        supported = (comfy_dir / "comfy" / "cli_args.py").read_text(encoding="utf-8")
    except (OSError, ValueError, subprocess.SubprocessError):
        return []
    options = []
    for flag in ("--novram", "--disable-cuda-malloc", "--disable-async-offload"):
        if flag in supported:
            options.append(flag)
    if "--reserve-vram" in supported:
        options.extend(["--reserve-vram", "1.5"])
    return options


if __name__ == "__main__":
    # One argument per line, suitable for bash mapfile without eval.
    print("\n".join(memory_args(Path(sys.argv[1]))))

