#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
APP_DIR="$ROOT_DIR/application"
MARKER="$APP_DIR/.aurora-linux-ready"
LOG_DIR="$APP_DIR/logs"
LOG_FILE="$LOG_DIR/aurora-first-run.log"
MAX_QUALITY=1
INSTALL_NVIDIA=0
FORCE=0
WITH_TRELLIS2=1

for arg in "$@"; do
  case "$arg" in
    --max-quality) MAX_QUALITY=1; WITH_TRELLIS2=1 ;;
    --balanced) MAX_QUALITY=0; WITH_TRELLIS2=0 ;;
    --with-trellis2) WITH_TRELLIS2=1 ;;
    --no-trellis2) WITH_TRELLIS2=0 ;;
    --install-nvidia-driver) INSTALL_NVIDIA=1 ;;
    --force) FORCE=1 ;;
    -h|--help)
      cat <<'EOF'
Usage: bash scripts/linux/aurora-first-run.sh [--max-quality|--balanced] [--with-trellis2|--no-trellis2] [--install-nvidia-driver] [--force]

Checks and installs the AuroraIA Linux runtime from the repository scripts.
This is the entry point used by the Tauri first launch check.
EOF
      exit 0
      ;;
    *) echo "Unknown option: $arg" >&2; exit 2 ;;
  esac
done

if [ "$(uname -s)" != "Linux" ]; then
  echo "Aurora first-run is Linux-only." >&2
  exit 1
fi

mkdir -p "$LOG_DIR"
exec > >(tee -a "$LOG_FILE") 2>&1

echo "== AuroraIA Linux first-run =="
echo "root=$ROOT_DIR"
echo "date=$(date -Iseconds)"

missing_cmds=()
for cmd in git curl python3 node npm cargo rustc blender cloudflared ollama nvidia-smi; do
  if ! command -v "$cmd" >/dev/null 2>&1; then
    missing_cmds+=("$cmd")
  fi
done

need_bootstrap=0
if [ "${#missing_cmds[@]}" -gt 0 ]; then
  need_bootstrap=1
  echo "Missing host commands: ${missing_cmds[*]}"
fi

if [ "$FORCE" = "1" ] || [ "$need_bootstrap" = "1" ]; then
  bootstrap_args=()
  if [ "$INSTALL_NVIDIA" = "1" ] || ! command -v nvidia-smi >/dev/null 2>&1; then
    bootstrap_args+=(--install-nvidia-driver)
  fi
  echo "Running bootstrap-ubuntu2404.sh ${bootstrap_args[*]:-}"
  bash "$ROOT_DIR/scripts/linux/bootstrap-ubuntu2404.sh" "${bootstrap_args[@]}"
else
  echo "Host bootstrap looks installed."
fi

stack_args=(--with-hunyuan --with-comfyui)
if [ "$MAX_QUALITY" = "1" ]; then
  stack_args+=(--prefetch-models --max-quality)
fi

need_stack=0
[ -d "$APP_DIR/node_modules" ] || need_stack=1
[ -x "$APP_DIR/.venv/bin/python" ] || need_stack=1
[ -f "$ROOT_DIR/modele/comfyui/main.py" ] || need_stack=1

if [ "$FORCE" = "1" ] || [ "$need_stack" = "1" ]; then
  echo "Running install-aurora-stack.sh ${stack_args[*]}"
  bash "$ROOT_DIR/scripts/linux/install-aurora-stack.sh" "${stack_args[@]}"
else
  echo "Application stack looks installed."
fi

if command -v ollama >/dev/null 2>&1; then
  profile="balanced"
  [ "$MAX_QUALITY" = "1" ] && profile="max-quality"
  echo "Preparing Ollama models: $profile"
  bash "$ROOT_DIR/scripts/linux/install-ollama-models.sh" "$profile" || true
fi

if [ "$WITH_TRELLIS2" = "1" ]; then
  echo "Preparing TRELLIS.2 experimental runtime"
  bash "$ROOT_DIR/scripts/linux/install-trellis2.sh" \
    || echo "Warning: TRELLIS.2 install failed. AuroraIA stays usable with Hunyuan3D 2.1 + Blender; see $LOG_FILE."
fi

echo "Verifying Linux stack"
bash "$ROOT_DIR/scripts/linux/verify-linux-stack.sh"

cat > "$MARKER" <<EOF
ready_at=$(date -Iseconds)
profile=$([ "$MAX_QUALITY" = "1" ] && echo max-quality || echo balanced)
trellis2=$WITH_TRELLIS2
log=$LOG_FILE
EOF

echo "AuroraIA Linux runtime ready."
