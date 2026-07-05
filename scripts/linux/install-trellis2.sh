#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
EXTERNAL_DIR="${AURORA_EXTERNAL_DIR:-$HOME/.local/share/auroraia/external}"
TRELLIS_DIR="$EXTERNAL_DIR/TRELLIS.2"
ENV_NAME="${TRELLIS2_ENV_NAME:-trellis2}"

if [ "$(uname -s)" != "Linux" ]; then
  echo "TRELLIS.2 is intended to be installed from Linux." >&2
  exit 1
fi

mkdir -p "$EXTERNAL_DIR"

if command -v nvidia-smi >/dev/null 2>&1; then
  vram_mb="$(nvidia-smi --query-gpu=memory.total --format=csv,noheader,nounits | head -n 1 | tr -d ' ')"
  if [ "${vram_mb:-0}" -lt 24000 ]; then
    echo "Warning: TRELLIS.2 upstream lists 24GB VRAM minimum; this GPU reports ${vram_mb}MB."
    echo "The install can succeed, but full local inference is not guaranteed on RTX 5070 Ti 16GB."
  fi
fi

ensure_conda() {
  if command -v conda >/dev/null 2>&1; then
    # shellcheck disable=SC1091
    . "$(conda info --base)/etc/profile.d/conda.sh"
    return
  fi

  local conda_dir="$HOME/.local/opt/miniforge3"
  if [ ! -x "$conda_dir/bin/conda" ]; then
    local tmp
    tmp="$(mktemp -d)"
    curl -fL https://github.com/conda-forge/miniforge/releases/latest/download/Miniforge3-Linux-x86_64.sh -o "$tmp/miniforge.sh"
    bash "$tmp/miniforge.sh" -b -p "$conda_dir"
    rm -rf "$tmp"
  fi
  # shellcheck disable=SC1091
  . "$conda_dir/etc/profile.d/conda.sh"
}

echo "[1/5] Conda"
ensure_conda

echo "[2/5] Clone TRELLIS.2"
if [ -d "$TRELLIS_DIR/.git" ]; then
  git -C "$TRELLIS_DIR" pull --ff-only
  git -C "$TRELLIS_DIR" submodule update --init --recursive
else
  git clone --recursive https://github.com/microsoft/TRELLIS.2.git "$TRELLIS_DIR"
fi

echo "[3/5] Create env $ENV_NAME"
if ! conda env list | awk '{print $1}' | grep -qx "$ENV_NAME"; then
  conda create -y -n "$ENV_NAME" python=3.10
fi
conda activate "$ENV_NAME"
python -m pip install --upgrade pip setuptools wheel

echo "[4/5] PyTorch Blackwell CUDA 12.8"
python -m pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu128

echo "[5/5] TRELLIS.2 dependencies and CUDA extensions"
export CUDA_HOME="${CUDA_HOME:-/usr/local/cuda-12.8}"
if [ ! -d "$CUDA_HOME" ] && [ -d /usr/local/cuda-12.4 ]; then
  export CUDA_HOME=/usr/local/cuda-12.4
fi
export PATH="$CUDA_HOME/bin:$PATH"
export TORCH_CUDA_ARCH_LIST="${TORCH_CUDA_ARCH_LIST:-12.0}"
export PYTORCH_CUDA_ALLOC_CONF="${PYTORCH_CUDA_ALLOC_CONF:-expandable_segments:True}"
export MAX_JOBS="${MAX_JOBS:-$(nproc)}"

(
  cd "$TRELLIS_DIR"
  . ./setup.sh --basic --flash-attn --nvdiffrast --nvdiffrec --cumesh --o-voxel --flexgemm
)

python - <<'PY'
import torch
print("torch", torch.__version__, "cuda", torch.version.cuda)
print("cuda available", torch.cuda.is_available())
print("arch list", torch.cuda.get_arch_list() if torch.cuda.is_available() else [])
PY

cat > "$ROOT_DIR/.env.trellis2.example" <<EOF
TRELLIS2_DIR=$TRELLIS_DIR
TRELLIS2_ENV_NAME=$ENV_NAME
PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True
TORCH_CUDA_ARCH_LIST=12.0
EOF

echo "TRELLIS.2 installed in $TRELLIS_DIR"
echo "Activate later with: conda activate $ENV_NAME"
