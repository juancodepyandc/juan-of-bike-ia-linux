#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_DIR="$ROOT_DIR/application"
LOG_DIR="${TMPDIR:-/tmp}/auroraia"

mkdir -p "$LOG_DIR"

if [ "$(uname -s)" = "Linux" ] && [ "${AURORA_SKIP_FIRST_RUN:-0}" != "1" ]; then
  if [ ! -f "$APP_DIR/.aurora-linux-ready" ]; then
    echo "[0/5] First-run Linux initialization"
    bash "$ROOT_DIR/scripts/linux/aurora-first-run.sh" --max-quality
  fi
fi

if [ -x "$APP_DIR/.venv/bin/python" ]; then
  APP_PY="$APP_DIR/.venv/bin/python"
elif [ -x "$ROOT_DIR/.venv/bin/python" ]; then
  APP_PY="$ROOT_DIR/.venv/bin/python"
else
  APP_PY="python3"
fi

export OLLAMA_MAX_LOADED_MODELS="${OLLAMA_MAX_LOADED_MODELS:-1}"
export OLLAMA_NUM_PARALLEL="${OLLAMA_NUM_PARALLEL:-1}"
export OLLAMA_KEEP_ALIVE="${OLLAMA_KEEP_ALIVE:-10m}"
export PYTORCH_CUDA_ALLOC_CONF="${PYTORCH_CUDA_ALLOC_CONF:-expandable_segments:True}"
export TOKENIZERS_PARALLELISM="${TOKENIZERS_PARALLELISM:-false}"

echo "[1/5] Ollama"
if command -v ollama >/dev/null 2>&1; then
  (ollama serve >"$LOG_DIR/ollama.log" 2>&1 &)
else
  echo "ollama introuvable dans PATH"
fi

echo "[2/5] ComfyUI"
COMFY_DIR=""
if [ -f "$ROOT_DIR/modele/comfyui/comfyui/main.py" ]; then
  COMFY_DIR="$ROOT_DIR/modele/comfyui/comfyui"
elif [ -f "$ROOT_DIR/modele/comfyui/main.py" ]; then
  COMFY_DIR="$ROOT_DIR/modele/comfyui"
fi

if [ -n "$COMFY_DIR" ]; then
  if [ -x "$COMFY_DIR/venv/bin/python" ]; then
    COMFY_PY="$COMFY_DIR/venv/bin/python"
  else
    COMFY_PY="python3"
  fi
  (cd "$COMFY_DIR" && "$COMFY_PY" main.py --listen 127.0.0.1 --port 8188 >"$LOG_DIR/comfyui.log" 2>&1 &)
else
  echo "ComfyUI introuvable sous modele/comfyui; il sera lance a la demande si installe plus tard."
fi

echo "[3/5] Bridge Python"
(cd "$APP_DIR" && "$APP_PY" bridge_server.py >"$LOG_DIR/bridge.log" 2>&1 &)

echo "[4/5] Vite"
(cd "$APP_DIR" && npm run dev:web >"$LOG_DIR/vite.log" 2>&1 &)

echo "[5/5] Cloudflared"
if [ "${AURORA_START_TUNNEL:-0}" = "1" ]; then
  if command -v cloudflared >/dev/null 2>&1; then
    pkill -f "cloudflared tunnel" 2>/dev/null || true
    : > "$LOG_DIR/cloudflared.log"
    setsid cloudflared tunnel --url http://127.0.0.1:1420 >"$LOG_DIR/cloudflared.log" 2>&1 </dev/null &
    echo "  Tunnel demarre, recuperation de l'adresse publique..."
    TUN_URL=""
    for _i in $(seq 1 30); do
      TUN_URL="$(grep -aoE 'https://[a-z0-9-]+\.trycloudflare\.com' "$LOG_DIR/cloudflared.log" 2>/dev/null | head -1)"
      [ -n "$TUN_URL" ] && break
      sleep 2
    done
    if [ -n "$TUN_URL" ]; then
      echo "$TUN_URL" > "$ROOT_DIR/tunnel_url.txt"
      echo "  Lien public: $TUN_URL"
      # publie le lien sur GitHub (aurora-live) pour qu'il soit toujours a jour en ligne
      bash "$ROOT_DIR/scripts/publish-live-link.sh" || echo "  (publication du lien ignoree)"
    else
      echo "  Adresse du tunnel non recuperee (voir $LOG_DIR/cloudflared.log)."
    fi
  else
    echo "  cloudflared introuvable; lance scripts/linux/bootstrap-ubuntu2404.sh sur Linux."
  fi
else
  echo "  Tunnel non lance. Utilise AURORA_START_TUNNEL=1 ./start-aurora.sh si besoin."
fi

# Surveillance de l'etat -> publie "ouvert/ferme" sur le repo aurora-live automatiquement
if [ -x "$ROOT_DIR/scripts/aurora-status-watcher.sh" ]; then
  pkill -f "aurora-status-watcher.sh" 2>/dev/null || true
  setsid bash "$ROOT_DIR/scripts/aurora-status-watcher.sh" >"$LOG_DIR/status-watcher.log" 2>&1 </dev/null &
  echo "  Surveillance etat: active (repo aurora-live tenu a jour ouvert/ferme)"
fi

echo "Aurora demarre:"
echo "  UI      http://127.0.0.1:1420"
echo "  Bridge  http://127.0.0.1:3001"
echo "  Logs    $LOG_DIR"
