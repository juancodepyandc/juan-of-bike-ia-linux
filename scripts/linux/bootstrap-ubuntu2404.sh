#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
INSTALL_NVIDIA=0
INSTALL_BLENDER=1

for arg in "$@"; do
  case "$arg" in
    --install-nvidia-driver) INSTALL_NVIDIA=1 ;;
    --no-blender) INSTALL_BLENDER=0 ;;
    -h|--help)
      cat <<'EOF'
Usage: bash scripts/linux/bootstrap-ubuntu2404.sh [--install-nvidia-driver] [--no-blender]

Installs the Linux host toolchain for AuroraIA on Ubuntu 24.04 LTS:
apt build deps, Node 24, Rust, cloudflared, Git LFS and official Blender.
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

if [ -r /etc/os-release ]; then
  . /etc/os-release
  if [ "${ID:-}" != "ubuntu" ] || [ "${VERSION_ID:-}" != "24.04" ]; then
    echo "Warning: recommended target is Ubuntu 24.04 LTS; detected ${PRETTY_NAME:-unknown}."
  fi
fi

echo "[1/7] Apt dependencies"
sudo apt-get update
sudo apt-get install -y \
  ca-certificates curl gnupg lsb-release git git-lfs jq unzip xz-utils bzip2 \
  build-essential pkg-config cmake ninja-build patchelf lsof ffmpeg \
  python3 python3-dev python3-venv python3-pip \
  libssl-dev libgtk-3-dev libwebkit2gtk-4.1-dev libjavascriptcoregtk-4.1-dev \
  libsoup-3.0-dev libayatana-appindicator3-dev librsvg2-dev \
  libgl1 libglib2.0-0 libx11-6 libxext6 libxrender1 libsm6 libxrandr2 \
  libxinerama1 libxcursor1 libxi6 libxxf86vm1 libfontconfig1 xvfb

git lfs install

echo "[2/7] Cloudflared"
sudo mkdir -p --mode=0755 /usr/share/keyrings
curl -fsSL https://pkg.cloudflare.com/cloudflare-main.gpg | sudo tee /usr/share/keyrings/cloudflare-main.gpg >/dev/null
echo 'deb [signed-by=/usr/share/keyrings/cloudflare-main.gpg] https://pkg.cloudflare.com/cloudflared noble main' \
  | sudo tee /etc/apt/sources.list.d/cloudflared.list >/dev/null
sudo apt-get update
sudo apt-get install -y cloudflared

echo "[3/7] Node 24 via nvm"
export NVM_DIR="$HOME/.nvm"
if [ ! -s "$NVM_DIR/nvm.sh" ]; then
  curl -fsSL https://raw.githubusercontent.com/nvm-sh/nvm/v0.40.3/install.sh | bash
fi
# shellcheck disable=SC1091
. "$NVM_DIR/nvm.sh"
nvm install 24
nvm alias default 24

echo "[4/7] Rust stable"
if ! command -v rustup >/dev/null 2>&1; then
  curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y
fi
# shellcheck disable=SC1091
. "$HOME/.cargo/env"
rustup default stable
rustup component add rustfmt clippy || true

echo "[5/7] NVIDIA driver"
if [ "$INSTALL_NVIDIA" = "1" ]; then
  sudo apt-get install -y ubuntu-drivers-common
  sudo ubuntu-drivers install || sudo ubuntu-drivers autoinstall
  echo "Driver installed or updated. Reboot before running CUDA/Torch verification."
else
  echo "Skipped. Run again with --install-nvidia-driver after installing Ubuntu if nvidia-smi is missing."
fi

install_blender() {
  local version="${BLENDER_VERSION:-5.1.1}"
  local major_minor="${version%.*}"
  local archive="blender-${version}-linux-x64.tar.xz"
  local url="${BLENDER_URL:-https://download.blender.org/release/Blender${major_minor}/${archive}}"
  local tmp
  tmp="$(mktemp -d)"
  mkdir -p "$HOME/.local/opt" "$HOME/.local/bin"
  echo "Downloading $url"
  if curl -fL "$url" -o "$tmp/$archive"; then
    tar -xf "$tmp/$archive" -C "$HOME/.local/opt"
    ln -sfn "$HOME/.local/opt/blender-${version}-linux-x64/blender" "$HOME/.local/bin/blender"
    echo "Blender linked at $HOME/.local/bin/blender"
  else
    echo "Official Blender download failed; falling back to Ubuntu package."
    sudo apt-get install -y blender
  fi
  rm -rf "$tmp"
}

echo "[6/7] Blender"
if [ "$INSTALL_BLENDER" = "1" ]; then
  install_blender
else
  echo "Skipped."
fi

echo "[7/8] Ollama"
if command -v ollama >/dev/null 2>&1; then
  ollama --version || true
else
  curl -fsSL https://ollama.com/install.sh | sh
fi

echo "[8/8] Host summary"
echo "Repo: $ROOT_DIR"
command -v node && node --version
command -v npm && npm --version
command -v rustc && rustc --version
command -v cargo && cargo --version
command -v cloudflared && cloudflared --version || true
command -v ollama && ollama --version || true
command -v blender && blender --version | head -n 2 || true
command -v nvidia-smi && nvidia-smi || true

echo "Next:"
echo "  bash scripts/linux/install-aurora-stack.sh --with-hunyuan --with-comfyui"
echo "  bash scripts/linux/verify-linux-stack.sh"
