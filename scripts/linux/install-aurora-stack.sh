#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
APP_DIR="$ROOT_DIR/application"
WITH_HUNYUAN=0
WITH_COMFYUI=1
PREFETCH_MODELS=0

for arg in "$@"; do
  case "$arg" in
    --with-hunyuan) WITH_HUNYUAN=1 ;;
    --with-comfyui) WITH_COMFYUI=1 ;;
    --no-comfyui) WITH_COMFYUI=0 ;;
    --prefetch-models) PREFETCH_MODELS=1 ;;
    --max-quality) WITH_HUNYUAN=1; WITH_COMFYUI=1; PREFETCH_MODELS=1 ;;
    -h|--help)
      cat <<'EOF'
Usage: bash scripts/linux/install-aurora-stack.sh [--with-hunyuan] [--with-comfyui|--no-comfyui] [--prefetch-models] [--max-quality]

Installs AuroraIA application dependencies on Linux:
npm, Python venv, PyTorch CUDA 12.8, Python services, ComfyUI and Playwright Chromium.
EOF
      exit 0
      ;;
    *) echo "Unknown option: $arg" >&2; exit 2 ;;
  esac
done

if [ "$(uname -s)" != "Linux" ]; then
  echo "This script must run on Linux." >&2
  exit 1
fi

export NVM_DIR="$HOME/.nvm"
if [ -s "$NVM_DIR/nvm.sh" ]; then
  # shellcheck disable=SC1091
  . "$NVM_DIR/nvm.sh"
fi

export PYTORCH_CUDA_ALLOC_CONF="${PYTORCH_CUDA_ALLOC_CONF:-expandable_segments:True}"
export TOKENIZERS_PARALLELISM="${TOKENIZERS_PARALLELISM:-false}"
export HF_HUB_ENABLE_HF_TRANSFER="${HF_HUB_ENABLE_HF_TRANSFER:-1}"

echo "[1/6] Node dependencies"
npm --prefix "$APP_DIR" install

echo "[2/6] Python venv"
python3 -m venv "$APP_DIR/.venv"
# shellcheck disable=SC1091
. "$APP_DIR/.venv/bin/activate"
python -m pip install --upgrade pip setuptools wheel

echo "[3/6] PyTorch CUDA 12.8 for Blackwell"
if [ "${AURORA_TORCH_NIGHTLY:-0}" = "1" ]; then
  python -m pip install --pre torch torchvision torchaudio --index-url https://download.pytorch.org/whl/nightly/cu128
else
  python -m pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu128
fi

echo "[4/6] Aurora Python services"
python -m pip install -r "$APP_DIR/python-services/requirements.txt"
python -m pip install \
  hf_transfer 'huggingface_hub[cli]' pymeshlab pygltflib PyYAML einops omegaconf rembg onnxruntime
python -m pip install xformers --extra-index-url https://download.pytorch.org/whl/cu128 \
  || echo "Warning: xformers wheel unavailable; Aurora can run without it."
python -m playwright install chromium

echo "[5/7] ComfyUI runtime"
if [ "$WITH_COMFYUI" = "1" ]; then
  bash "$ROOT_DIR/scripts/linux/install-comfyui.sh"
else
  echo "Skipped. ComfyUI is required for image/drawing/video workflows; use --with-comfyui later."
fi

echo "[6/7] Optional Hunyuan3D runtime"
if [ "$WITH_HUNYUAN" = "1" ]; then
  bash "$ROOT_DIR/scripts/linux/install-hunyuan3d.sh"
else
  echo "Skipped. Add --with-hunyuan or --max-quality to install the external Hunyuan3D runtime."
fi

echo "[7/7] Optional model cache"
if [ "$PREFETCH_MODELS" = "1" ]; then
  python - <<'PY'
from huggingface_hub import snapshot_download

required_repos = [
    "tencent/Hunyuan3D-2.1",
    "tencent/Hunyuan3D-2",
    "tencent/Hunyuan3D-2mv",
    "black-forest-labs/FLUX.1-schnell",
    "Lightricks/LTX-Video",
    "Wan-AI/Wan2.2-TI2V-5B-Diffusers",
]

quality_repos = [
    "black-forest-labs/FLUX.1-dev-FP8",
    "Wan-AI/Wan2.2-T2V-A14B-Diffusers",
    "Wan-AI/Wan2.2-I2V-A14B-Diffusers",
]

for repo in required_repos:
    print(f"[hf] {repo}")
    snapshot_download(repo_id=repo, resume_download=True)

for repo in quality_repos:
    print(f"[hf optional quality] {repo}")
    try:
        snapshot_download(repo_id=repo, resume_download=True)
    except Exception as exc:
        print(f"[warn] optional model not cached: {repo}: {exc}")
PY
else
  echo "Skipped. Add --prefetch-models or --max-quality when disk/time are ready."
fi

echo "Aurora stack installed. Run: bash scripts/linux/verify-linux-stack.sh"
