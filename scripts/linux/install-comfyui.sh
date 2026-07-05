#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
COMFY_PARENT="${AURORA_COMFY_PARENT:-$ROOT_DIR/modele}"
COMFY_DIR="$COMFY_PARENT/comfyui"
REPO_URL="${AURORA_COMFY_REPO:-https://github.com/comfy-org/ComfyUI.git}"
TORCH_INDEX="${AURORA_TORCH_INDEX:-https://download.pytorch.org/whl/cu128}"

if [ "$(uname -s)" != "Linux" ]; then
  echo "This script must run on Linux." >&2
  exit 1
fi

mkdir -p "$COMFY_PARENT"

if [ -d "$COMFY_DIR/.git" ]; then
  echo "[1/4] Updating ComfyUI"
  git -C "$COMFY_DIR" pull --ff-only || git -C "$COMFY_DIR" pull --rebase
elif [ -d "$COMFY_DIR" ] && [ -f "$COMFY_DIR/main.py" ]; then
  echo "[1/4] Existing ComfyUI directory found: $COMFY_DIR"
else
  echo "[1/4] Cloning ComfyUI"
  git clone "$REPO_URL" "$COMFY_DIR"
fi

echo "[2/4] ComfyUI venv"
python3 -m venv "$COMFY_DIR/venv"
# shellcheck disable=SC1091
. "$COMFY_DIR/venv/bin/activate"
python -m pip install --upgrade pip setuptools wheel

echo "[3/4] PyTorch for ComfyUI"
if [ "${AURORA_TORCH_NIGHTLY:-0}" = "1" ]; then
  python -m pip install --pre torch torchvision torchaudio --index-url https://download.pytorch.org/whl/nightly/cu128
else
  python -m pip install torch torchvision torchaudio --index-url "$TORCH_INDEX"
fi

echo "[4/4] ComfyUI requirements"
python -m pip install -r "$COMFY_DIR/requirements.txt"
python -m pip install xformers --extra-index-url "$TORCH_INDEX" \
  || echo "Warning: xformers unavailable; ComfyUI can run without it."

cat > "$COMFY_DIR/.aurora-installed" <<EOF
installed_at=$(date -Iseconds)
repo=$REPO_URL
torch_index=$TORCH_INDEX
EOF

echo "ComfyUI installed at $COMFY_DIR"
