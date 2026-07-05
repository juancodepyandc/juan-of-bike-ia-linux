#!/bin/bash
set -euo pipefail

echo ""
echo "=============================================="
echo "  AuroraIA-v2 RunPod A100 bootstrap"
echo "=============================================="
echo ""

export DEBIAN_FRONTEND=noninteractive
export PATH="/usr/local/bin:/usr/bin:/bin:$PATH"

WORKSPACE="${AURORA_WORKSPACE:-/workspace/aurora}"
OUTPUT="${AURORA_OUTPUT:-/workspace/output}"
MODELS="${AURORA_MODELS:-/workspace/models}"
COMFYUI_DIR="${COMFYUI_DIR:-/workspace/comfyui}"

echo "[1/8] Verification GPU..."
nvidia-smi || {
  echo "ERREUR: nvidia-smi indisponible. Ce bootstrap est pour NVIDIA/CUDA."
  exit 1
}

echo "[2/8] Paquets systeme..."
apt-get update
apt-get install -y \
  build-essential \
  ca-certificates \
  curl \
  ffmpeg \
  git \
  gnupg \
  lsb-release \
  python3-venv \
  unzip \
  wget \
  xz-utils \
  zstd

echo "[3/8] Node.js..."
if ! command -v node >/dev/null 2>&1 || ! command -v npm >/dev/null 2>&1; then
  curl -fsSL https://deb.nodesource.com/setup_20.x | bash -
  apt-get install -y nodejs
fi
node -v
npm -v

echo "[4/8] Python/pip..."
python -m pip install --upgrade pip setuptools wheel

echo "[5/8] Ollama..."
if ! command -v ollama >/dev/null 2>&1; then
  curl -fsSL https://ollama.com/install.sh | sh
fi
export PATH="/usr/local/bin:/usr/bin:/bin:$PATH"
which ollama
ollama --version || true

echo "[6/8] ComfyUI..."
if [ ! -f "$COMFYUI_DIR/main.py" ]; then
  rm -rf "$COMFYUI_DIR"
  git clone --depth 1 https://github.com/comfyanonymous/ComfyUI.git "$COMFYUI_DIR"
fi
python -m pip install -r "$COMFYUI_DIR/requirements.txt"

echo "[7/8] Dossiers persistants..."
mkdir -p "$OUTPUT" "$MODELS"
mkdir -p "$OUTPUT"/{images,videos,models3d,voice,temp,saves}
mkdir -p "$MODELS"/{ollama,comfyui/checkpoints,comfyui/clip,comfyui/vae}
mkdir -p "$MODELS"/cache/{huggingface/hub,huggingface/transformers,huggingface/datasets,torch,xdg,u2net}
echo "aurora-volume-ok-$(date +%s)" > /workspace/VOLUME_CHECK.txt
cat /workspace/VOLUME_CHECK.txt

echo "[8/8] Projet AuroraIA-v2..."
cd "$WORKSPACE"
find . -name "*.sh" -type f -exec sed -i 's/\r$//' {} \;
sed -i '1s/^\xEF\xBB\xBF//' cloud/start.sh
chmod +x cloud/start.sh
npm install
python -m pip install -r cloud/requirements.txt
bash -n cloud/start.sh

echo ""
echo "=============================================="
echo "  Bootstrap termine. Lancement AuroraIA-v2..."
echo "=============================================="
echo ""

export AURORA_WORKSPACE="$WORKSPACE"
export AURORA_OUTPUT="$OUTPUT"
export AURORA_MODELS="$MODELS"
export COMFYUI_DIR="$COMFYUI_DIR"
export HF_HOME="$MODELS/cache/huggingface"
export HF_HUB_CACHE="$MODELS/cache/huggingface/hub"
export HUGGINGFACE_HUB_CACHE="$MODELS/cache/huggingface/hub"
export TRANSFORMERS_CACHE="$MODELS/cache/huggingface/transformers"
export HF_DATASETS_CACHE="$MODELS/cache/huggingface/datasets"
export TORCH_HOME="$MODELS/cache/torch"
export XDG_CACHE_HOME="$MODELS/cache/xdg"
export U2NET_HOME="$MODELS/cache/u2net"
exec bash cloud/start.sh
