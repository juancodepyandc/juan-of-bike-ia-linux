#!/bin/bash
set -e

echo ""
echo "=============================================="
echo "  AuroraIA-v2 Cloud â€” Demarrage"
echo "=============================================="
echo ""

WORKSPACE="${AURORA_WORKSPACE:-/workspace/aurora}"
OUTPUT="${AURORA_OUTPUT:-/workspace/output}"
MODELS="${AURORA_MODELS:-/workspace/models}"
COMFYUI_DIR="${COMFYUI_DIR:-/workspace/comfyui}"
BRIDGE_PORT="${AURORA_BRIDGE_PORT:-3101}"
FRONTEND_PORT="${AURORA_FRONTEND_PORT:-8888}"
KEEP_ALIVE_MONITOR="${AURORA_KEEP_ALIVE_MONITOR:-0}"

export PATH="/usr/local/bin:/usr/bin:/bin:$PATH"

wait_http_service() {
  local label="$1"
  local url="$2"
  local log_file="$3"
  local attempts="${4:-90}"

  for _ in $(seq 1 "$attempts"); do
    if curl -sf "$url" >/dev/null 2>&1; then
      echo "  $label pret"
      return 0
    fi
    sleep 2
  done

  echo "ERREUR: $label ne repond pas sur $url. Dernieres lignes:"
  tail -n 80 "$log_file" 2>/dev/null || true
  exit 1
}

if ! command -v ollama >/dev/null 2>&1; then
  echo "ERREUR: ollama introuvable. Installe d'abord zstd puis Ollama:"
  echo "  apt-get update && apt-get install -y zstd curl ca-certificates"
  echo "  curl -fsSL https://ollama.com/install.sh | sh"
  exit 1
fi

if ! command -v node >/dev/null 2>&1 || ! command -v npm >/dev/null 2>&1; then
  echo "ERREUR: node/npm introuvable. Installe Node.js avant de lancer AuroraIA-v2."
  exit 1
fi

if [ ! -f "$COMFYUI_DIR/main.py" ] && [ -f "/opt/comfyui/main.py" ]; then
  COMFYUI_DIR="/opt/comfyui"
fi

if [ ! -f "$COMFYUI_DIR/main.py" ]; then
  echo "ERREUR: ComfyUI introuvable dans $COMFYUI_DIR."
  echo "Installe-le avec:"
  echo "  git clone --depth 1 https://github.com/comfyanonymous/ComfyUI.git /workspace/comfyui"
  echo "  python -m pip install -r /workspace/comfyui/requirements.txt"
  exit 1
fi

echo "Nettoyage des anciens services AuroraIA..."
pkill -f "vite --host .*1420" 2>/dev/null || true
pkill -f "vite --host .*8888" 2>/dev/null || true
pkill -f "cloud/cloud_bridge.py" 2>/dev/null || true
pkill -f "python cloud_bridge.py" 2>/dev/null || true
pkill -f "python main.py --listen .*8188" 2>/dev/null || true
sleep 2

# ---- Dossiers persistants (Network Volume) ----
mkdir -p "$OUTPUT"/{images,videos,models3d,voice,temp,saves}
mkdir -p "$MODELS"/{ollama,comfyui/checkpoints,comfyui/unet,comfyui/clip,comfyui/vae}
mkdir -p "$MODELS"/cache/{huggingface/hub,huggingface/transformers,huggingface/datasets,torch,xdg,u2net}

export AURORA_MODELS="$MODELS"
export OLLAMA_MODELS="$MODELS/ollama"
export OLLAMA_ORIGINS="*"
export HF_HOME="$MODELS/cache/huggingface"
export HF_HUB_CACHE="$MODELS/cache/huggingface/hub"
export HUGGINGFACE_HUB_CACHE="$MODELS/cache/huggingface/hub"
export TRANSFORMERS_CACHE="$MODELS/cache/huggingface/transformers"
export HF_DATASETS_CACHE="$MODELS/cache/huggingface/datasets"
export TORCH_HOME="$MODELS/cache/torch"
export XDG_CACHE_HOME="$MODELS/cache/xdg"
export U2NET_HOME="$MODELS/cache/u2net"

# ---- Liens symboliques ComfyUI â†’ volume ----
link_comfy_dir() {
  local target="$COMFYUI_DIR/models/$1"
  local source="$MODELS/comfyui/$1"
  if [ ! -L "$target" ]; then
    rm -rf "$target" 2>/dev/null || true
    ln -sf "$source" "$target"
    echo "  Lien: $target -> $source"
  fi
}

link_comfy_dir "checkpoints"
link_comfy_dir "unet"
link_comfy_dir "clip"
link_comfy_dir "vae"

download_file() {
  local label="$1"
  local url="$2"
  local destination="$3"
  local min_bytes="${4:-1024}"

  if [ -s "$destination" ] && [ "$(stat -Lc%s "$destination" 2>/dev/null || echo 0)" -ge "$min_bytes" ]; then
    echo "  $label deja present"
    return 0
  fi

  rm -f "$destination" "$destination.tmp"
  mkdir -p "$(dirname "$destination")"
  echo "  Telechargement $label..."
  wget -q --show-progress -O "$destination.tmp" "$url"

  if [ ! -s "$destination.tmp" ] || [ "$(stat -Lc%s "$destination.tmp" 2>/dev/null || echo 0)" -lt "$min_bytes" ]; then
    rm -f "$destination.tmp"
    echo "ERREUR: telechargement invalide pour $label depuis $url"
    exit 1
  fi

  mv "$destination.tmp" "$destination"
}

# ================================================================
# 1. OLLAMA
# ================================================================
echo "[1/5] Demarrage Ollama..."
if curl -sf http://127.0.0.1:11434/api/tags > /dev/null 2>&1; then
  OLLAMA_PID="$(pgrep -f 'ollama serve' | head -1 || true)"
  echo "  Ollama deja pret (PID ${OLLAMA_PID:-existant})"
else
  nohup ollama serve > /tmp/ollama.log 2>&1 &
  OLLAMA_PID=$!
fi

# Attendre qu'Ollama reponde
for i in $(seq 1 30); do
  if curl -sf http://127.0.0.1:11434/api/tags > /dev/null 2>&1; then
    echo "  Ollama pret (PID $OLLAMA_PID)"
    break
  fi
  sleep 1
done

# ================================================================
# 2. MODELES OLLAMA (pull si absent du volume)
# ================================================================
echo "[2/5] Verification modeles Ollama..."

pull_if_missing() {
  if ! ollama list 2>/dev/null | grep -q "^$1"; then
    echo "  Pull $1 (premiere fois, cache sur le volume)..."
    ollama pull "$1"
  else
    echo "  $1 â€” deja present"
  fi
}

# Detecter le tier GPU
if ! command -v nvidia-smi >/dev/null 2>&1; then
  if command -v rocm-smi >/dev/null 2>&1 || command -v rocminfo >/dev/null 2>&1; then
    echo "  AMD/ROCm detecte: ce demarrage cloud est configure pour NVIDIA/CUDA."
    echo "  Pour AuroraIA-v2 stable, utilise un GPU NVIDIA A100/H100/RTX PRO."
  else
    echo "  Aucun nvidia-smi detecte: impossible de classer proprement le GPU cloud."
  fi
fi

GPU_COUNT=$(nvidia-smi --query-gpu=name --format=csv,noheader 2>/dev/null | wc -l | tr -d ' ')
VRAM_MB=$(nvidia-smi --query-gpu=memory.total --format=csv,noheader,nounits 2>/dev/null | head -1 || echo "0")
VRAM_GB=$((VRAM_MB / 1024))
echo "  GPU count detecte: ${GPU_COUNT:-0}"
echo "  GPU VRAM detectee: ${VRAM_GB}GB"

if [ "${GPU_COUNT:-0}" -gt 1 ]; then
  echo "  Attention: AuroraIA-v2 utilise un seul GPU par tache lourde pour le moment."
  echo "  Le tier cloud est donc base sur la VRAM du GPU 0, pas sur la VRAM totale cumulee."
fi

if [ "$VRAM_GB" -ge 70 ]; then
  echo "  Tier: HIGH (A100 80GB)"
  pull_if_missing "llama4:scout"
  pull_if_missing "qwen3-coder:30b-a3b-q8_0"
  pull_if_missing "qwen3-vl:30b"
elif [ "$VRAM_GB" -ge 40 ]; then
  echo "  Tier: MID (A40/A6000 48GB) - qwen3:30b pour un meilleur rapport qualite/latence/stockage"
  # Sur 48GB, qwen3:30b evite l'offload CPU lourd et le cache disque massif de llama4:scout.
  export OLLAMA_NUM_PARALLEL=1
  pull_if_missing "qwen3:30b"
  pull_if_missing "qwen3-coder:30b-a3b-q4_K_M"
  pull_if_missing "qwen3-vl:30b"
else
  echo "  Tier: LOW (24GB)"
  pull_if_missing "qwen3:14b"
  pull_if_missing "qwen2.5-coder:14b"
  pull_if_missing "qwen3-vl:8b"
fi

# ================================================================
# 3. COMFYUI
# ================================================================
echo "[3/5] Demarrage ComfyUI..."

# Telecharger/modeler les fichiers FLUX aux emplacements utilises par le workflow.
FLUX_UNET="$MODELS/comfyui/unet/flux1-dev-fp8.safetensors"
LEGACY_FLUX_CKPT="$MODELS/comfyui/checkpoints/flux1-dev-fp8.safetensors"
if [ ! -s "$FLUX_UNET" ] && [ -s "$LEGACY_FLUX_CKPT" ]; then
  echo "  Reutilisation FLUX checkpoint vers UNET..."
  ln -sf "$LEGACY_FLUX_CKPT" "$FLUX_UNET"
fi
download_file "FLUX dev fp8 (~16GB, premiere fois)" \
  "https://huggingface.co/Comfy-Org/flux1-dev/resolve/main/flux1-dev-fp8.safetensors" \
  "$FLUX_UNET" \
  1000000000

CLIP_MODEL="$MODELS/comfyui/clip/clip_l.safetensors"
download_file "CLIP-L" \
  "https://huggingface.co/comfyanonymous/flux_text_encoders/resolve/main/clip_l.safetensors" \
  "$CLIP_MODEL" \
  100000000

T5_MODEL="$MODELS/comfyui/clip/t5xxl_fp8_e4m3fn.safetensors"
download_file "T5-XXL fp8" \
  "https://huggingface.co/comfyanonymous/flux_text_encoders/resolve/main/t5xxl_fp8_e4m3fn.safetensors" \
  "$T5_MODEL" \
  1000000000

VAE_MODEL="$MODELS/comfyui/vae/ae.safetensors"
download_file "VAE FLUX ae" \
  "https://huggingface.co/Comfy-Org/Lumina_Image_2.0_Repackaged/resolve/main/split_files/vae/ae.safetensors" \
  "$VAE_MODEL" \
  100000000

cd "$COMFYUI_DIR"
nohup python main.py --listen 0.0.0.0 --port 8188 --force-fp16 --enable-cors-header "*" > /tmp/comfyui.log 2>&1 &
COMFY_PID=$!
echo "  ComfyUI demarre (PID $COMFY_PID)"
cd "$WORKSPACE"

# ================================================================
# 4. CLOUD BRIDGE
# ================================================================
echo "[4/5] Demarrage Cloud Bridge..."

pip install -q -r cloud/requirements.txt 2>/dev/null || true

export AURORA_WORKSPACE="$WORKSPACE"
export AURORA_OUTPUT="$OUTPUT"
export AURORA_MODELS="$MODELS"
export AURORA_BRIDGE_PORT="$BRIDGE_PORT"
export COMFYUI_DIR="$COMFYUI_DIR"
nohup python cloud/cloud_bridge.py > /tmp/cloud_bridge.log 2>&1 &
BRIDGE_PID=$!
echo "  Cloud Bridge demarre (PID $BRIDGE_PID, port $BRIDGE_PORT)"

# ================================================================
# 5. FRONTEND VITE
# ================================================================
echo "[5/5] Demarrage Frontend..."

export VITE_CLOUD_MODE=true
export VITE_BRIDGE_URL=http://127.0.0.1:$BRIDGE_PORT
export AURORA_FRONTEND_PORT="$FRONTEND_PORT"
nohup npm run start:cloud > /tmp/vite.log 2>&1 &
VITE_PID=$!
echo "  Vite demarre (PID $VITE_PID, port $FRONTEND_PORT)"

# Attendre que tout soit pret avant de rendre la main a l'utilisateur.
wait_http_service "ComfyUI" "http://127.0.0.1:8188/system_stats" "/tmp/comfyui.log" 90
wait_http_service "Cloud Bridge" "http://127.0.0.1:$BRIDGE_PORT/api/health" "/tmp/cloud_bridge.log" 45
wait_http_service "Frontend" "http://127.0.0.1:$FRONTEND_PORT" "/tmp/vite.log" 45

# ================================================================
# AFFICHAGE FINAL
# ================================================================
POD_ID="${RUNPOD_POD_ID:-<POD_ID>}"

echo ""
echo "=============================================="
echo "  AuroraIA-v2 Cloud â€” PRET"
echo "=============================================="
echo ""
echo "  GPU        : $(nvidia-smi --query-gpu=name --format=csv,noheader 2>/dev/null || echo 'N/A')"
echo "  VRAM       : ${VRAM_GB}GB"
echo "  Tier       : $([ $VRAM_GB -ge 70 ] && echo 'HIGH' || ([ $VRAM_GB -ge 40 ] && echo 'MID' || echo 'LOW'))"
echo ""
echo "  Frontend   : https://${POD_ID}-${FRONTEND_PORT}.proxy.runpod.net"
echo "  Bridge     : port $BRIDGE_PORT (interne)"
echo "  Ollama     : port 11434 (interne)"
echo "  ComfyUI    : port 8188 (interne)"
echo ""
echo "  Logs:"
echo "    tail -f /tmp/ollama.log"
echo "    tail -f /tmp/comfyui.log"
echo "    tail -f /tmp/cloud_bridge.log"
echo "    tail -f /tmp/vite.log"
echo ""
echo "=============================================="

echo ""
echo "  Verification locale rapide:"
if curl -sf http://127.0.0.1:$BRIDGE_PORT/api/health >/dev/null 2>&1; then
  echo "    Bridge $BRIDGE_PORT : OK"
else
  echo "    Bridge $BRIDGE_PORT : en attente ou erreur (voir /tmp/cloud_bridge.log)"
fi

if curl -sf http://127.0.0.1:$FRONTEND_PORT >/dev/null 2>&1; then
  echo "    Frontend $FRONTEND_PORT : OK"
else
echo "    Frontend $FRONTEND_PORT : en attente ou erreur (voir /tmp/vite.log)"
fi

if [ "$KEEP_ALIVE_MONITOR" != "1" ]; then
  echo ""
  echo "  Mode detache: les services restent actifs apres fermeture du shell."
  echo "  Pour garder la surveillance au premier plan:"
  echo "    export AURORA_KEEP_ALIVE_MONITOR=1"
  echo "    bash cloud/start.sh"
  echo ""
  exit 0
fi

echo ""
echo "  Surveillance active. Ctrl+C pour arreter proprement avant Stop Pod."
echo ""

check_http_service() {
  local label="$1"
  local url="$2"
  local log_file="$3"

  for _ in 1 2 3; do
    if curl -sf "$url" >/dev/null 2>&1; then
      return 0
    fi
    sleep 2
  done

  echo "ERREUR: $label ne repond plus sur $url. Dernieres lignes:"
  tail -n 80 "$log_file" 2>/dev/null || true
  exit 1
}

while true; do
  check_http_service "Ollama" "http://127.0.0.1:11434/api/tags" "/tmp/ollama.log"
  check_http_service "ComfyUI" "http://127.0.0.1:8188/system_stats" "/tmp/comfyui.log"
  check_http_service "Cloud Bridge" "http://127.0.0.1:$BRIDGE_PORT/api/health" "/tmp/cloud_bridge.log"
  check_http_service "Frontend Vite" "http://127.0.0.1:$FRONTEND_PORT" "/tmp/vite.log"
  sleep 10
done
