#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
APP_DIR="$ROOT_DIR/application"
FAIL=0

check_cmd() {
  local name="$1"
  if command -v "$name" >/dev/null 2>&1; then
    echo "OK   $name: $(command -v "$name")"
  else
    echo "MISS $name"
    FAIL=1
  fi
}

echo "[1/6] Commands"
for cmd in git node npm python3 cargo rustc blender cloudflared ollama nvidia-smi; do
  check_cmd "$cmd"
done

echo "[2/6] Versions"
node --version || true
npm --version || true
rustc --version || true
cargo --version || true
blender --version | head -n 2 || true
cloudflared --version || true
ollama --version || true
nvidia-smi || true

echo "[3/6] Python/Torch"
if [ -x "$APP_DIR/.venv/bin/python" ]; then
  PY="$APP_DIR/.venv/bin/python"
else
  PY="python3"
fi

"$PY" - <<'PY' || FAIL=1
import importlib.util

required = ["torch", "diffusers", "transformers", "accelerate", "flask", "trimesh", "huggingface_hub"]
for name in required:
    print(("OK   " if importlib.util.find_spec(name) else "MISS ") + name)

import torch
print("torch", torch.__version__)
print("torch cuda", torch.version.cuda)
print("cuda available", torch.cuda.is_available())
if torch.cuda.is_available():
    print("gpu", torch.cuda.get_device_name(0))
    print("arch list", torch.cuda.get_arch_list())
    if "sm_120" not in torch.cuda.get_arch_list() and "compute_120" not in torch.cuda.get_arch_list():
        raise SystemExit("Blackwell sm_120/compute_120 not present in PyTorch arch list")
PY

echo "[4/6] Repo cleanliness"
tracked_outputs="$(git -C "$ROOT_DIR" ls-files application/output output .claude/test-outputs application/public/_pbr_test application/_cuda_home application/dist-cowork-check | wc -l | tr -d ' ')"
if [ "$tracked_outputs" = "0" ]; then
  echo "OK   no generated outputs tracked"
else
  echo "FAIL generated outputs still tracked: $tracked_outputs"
  FAIL=1
fi

large_tracked="$(git -C "$ROOT_DIR" ls-files '*.safetensors' '*.ckpt' '*.pth' '*.gguf' '*.bin' 'modele/*' | wc -l | tr -d ' ')"
if [ "$large_tracked" = "0" ]; then
  echo "OK   no model weights tracked"
else
  echo "FAIL model weights tracked: $large_tracked"
  FAIL=1
fi

echo "[5/6] App compile surface"
npm --prefix "$APP_DIR" run build

echo "[5b/6] External runtimes"
if [ -f "$ROOT_DIR/modele/comfyui/main.py" ]; then
  echo "OK   ComfyUI: $ROOT_DIR/modele/comfyui"
else
  echo "MISS ComfyUI under modele/comfyui"
  FAIL=1
fi

if [ -d "${AURORA_EXTERNAL_DIR:-$HOME/.local/share/auroraia/external}/Hunyuan3D-2.1" ]; then
  echo "OK   Hunyuan3D-2.1 external runtime"
else
  echo "MISS Hunyuan3D-2.1 external runtime"
  FAIL=1
fi

if [ -d "${AURORA_EXTERNAL_DIR:-$HOME/.local/share/auroraia/external}/TRELLIS.2" ]; then
  echo "OK   TRELLIS.2 external runtime"
else
  echo "WARN TRELLIS.2 external runtime missing (experimental on 16GB VRAM)"
fi

echo "[6/6] Result"
if [ "$FAIL" = "0" ]; then
  echo "AuroraIA Linux stack looks ready."
else
  echo "AuroraIA Linux stack has missing pieces above."
  exit 1
fi
