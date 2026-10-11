#!/usr/bin/env bash
# Surveille le bridge via son tunnel PUBLIC et son adresse ; publie les
# changements et retente les pushes refusés à chaque cycle.
# 31/07: l'URL n'etait publiee qu'UNE fois au demarrage — a chaque relance de
# l'app le tunnel change d'adresse et GitHub gardait l'ancienne (constate:
# fichier phi-match-... vs tunnel reel characterization-...). Le watcher
# relit desormais le log cloudflared EN DIRECT et republie des que ca bouge.
set -uo pipefail
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PUB="$ROOT_DIR/scripts/publish-live-link.sh"
TUNNEL_CHECKER="$ROOT_DIR/scripts/verify-tunnel-url.sh"
URL_FILE="$ROOT_DIR/tunnel.txt"
LEGACY_URL_FILE="$ROOT_DIR/tunnel_url.txt"
CF_LOG="${TMPDIR:-/tmp}/auroraia/cloudflared.log"
LAST_URL=""
cleanup(){ bash "$PUB" auto >/dev/null 2>&1 || true; exit 0; }
trap cleanup TERM INT HUP
while true; do
  # Vérifier le trajet public complet, pas seulement un processus local.
  if bash "$TUNNEL_CHECKER" "$(cat "$URL_FILE" 2>/dev/null)" 1 >/dev/null 2>&1; then STATE=open; else STATE=closed; fi
  URL="$(grep -aoE 'https://[a-z0-9-]+\.trycloudflare\.com' "$CF_LOG" 2>/dev/null | tail -1)"
  if [ -n "$URL" ] && [ "$URL" != "$LAST_URL" ]; then
    if bash "$TUNNEL_CHECKER" "$URL" 15 >/dev/null; then
      printf '%s\n' "$URL" > "$URL_FILE"
      printf '%s\n' "$URL" > "$LEGACY_URL_FILE"
      STATE=open  # the new public URL was verified in this cycle
      LAST_URL="$URL"
    else
      echo "[watcher] tunnel non joignable; nouvel essai dans 60 s."
    fi
  fi
  # Retry every cycle, including a previously failed push. The publisher
  # coalesces unchanged heartbeats for four minutes.
  if ! bash "$PUB" "$STATE"; then
    echo "[watcher] publication aurora-live echouee; nouvel essai dans 60 s."
  fi
  sleep 60
done
