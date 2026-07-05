#!/usr/bin/env bash
set -euo pipefail

PROFILE="${1:-balanced}"
case "$PROFILE" in
  --max-quality) PROFILE="max-quality" ;;
  --balanced) PROFILE="balanced" ;;
esac

if ! command -v ollama >/dev/null 2>&1; then
  echo "ollama is missing. Install it first from https://ollama.com/download/linux" >&2
  exit 1
fi

pull() {
  local model="$1"
  echo "[ollama] $model"
  ollama pull "$model" || echo "Warning: could not pull $model"
}

pull qwen3:14b
pull qwen3:30b-a3b-instruct-2507-q4_K_M
pull qwen3-vl:8b
pull qwen3-coder:30b

case "$PROFILE" in
  balanced)
    pull qwen3-coder:30b
    ;;
  max-quality|max)
    pull qwen3-vl:30b
    pull qwen3-coder:30b
    pull qwen3-coder-next:q4_K_M
    pull gemma3:27b
    ;;
  *)
    echo "Unknown profile: $PROFILE (use balanced or max-quality)" >&2
    exit 2
    ;;
esac

ollama list
