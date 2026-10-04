"""Select ComfyUI memory options for local, bridge and service launches."""
from __future__ import annotations

import os
from pathlib import Path
import shlex
import subprocess
import sys


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
