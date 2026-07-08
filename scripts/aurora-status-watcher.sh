#!/usr/bin/env bash
# Surveille le studio (127.0.0.1:1420) et publie l'etat sur le repo aurora-live a chaque changement.
# Publie "ferme" quand le studio s'arrete (arret de l'app ou du watcher).
set -uo pipefail
PUB="/home/juan/AuroraIA/scripts/publish-live-link.sh"
LAST=""
cleanup(){ bash "$PUB" closed >/dev/null 2>&1 || true; exit 0; }
trap cleanup TERM INT HUP
while true; do
  if curl -s -m 5 -o /dev/null "http://127.0.0.1:1420/" 2>/dev/null; then STATE=open; else STATE=closed; fi
  if [ "$STATE" != "$LAST" ]; then bash "$PUB" "$STATE" >/dev/null 2>&1 || true; LAST="$STATE"; fi
  sleep 60
done
