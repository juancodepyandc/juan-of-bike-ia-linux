"""Small, reversible resource actions used before expensive local jobs."""

import os
import shutil
import subprocess


def release_ollama_models():
    """Unload resident Ollama models while keeping the service available."""
    binary = shutil.which("ollama")
    if not binary:
        return []
    try:
        listed = subprocess.run([binary, "ps"], capture_output=True, text=True,
                                timeout=5, check=False)
    except OSError:
        return []
    tags = []
    for line in (listed.stdout or "").splitlines()[1:]:
        fields = line.split()
        if fields:
            tags.append(fields[0])
    for tag in tags:
        subprocess.run([binary, "stop", tag], capture_output=True, text=True,
                       timeout=30, check=False)
    return tags


def configure_torch_memory():
    os.environ.setdefault("PYTORCH_CUDA_ALLOC_CONF",
                          "expandable_segments:True,max_split_size_mb:128")
    os.environ.setdefault("TORCH_CUDNN_V8_API_LRU_CACHE_LIMIT", "0")
