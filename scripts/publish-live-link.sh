#!/usr/bin/env bash
# Publie l'ETAT du studio dans le repo aurora-live (README, section <!--STATUS-->) et pousse sur GitHub :
#  - OUVERT  : affiche l'adresse publique en cours (tunnel Cloudflare)
#  - FERME   : affiche une page maintenance + contacts
# Mode : "open" | "closed" | "auto" (auto = teste si le bridge, cible du
# tunnel, repond sur 127.0.0.1:3001). Defaut auto.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LIVE_REPO="${AURORA_LIVE_REPO:-$ROOT_DIR/../aurora-live}"
URL_FILE="$ROOT_DIR/tunnel.txt"
LIVE_TUNNEL_FILE="$LIVE_REPO/tunnel.txt"
MODE="${1:-auto}"

[ -d "$LIVE_REPO/.git" ] || { echo "[publish] $LIVE_REPO absent"; exit 0; }

if [ "$MODE" = "auto" ]; then
  # Le tunnel route vers le bridge :3001 (pas l'UI Vite :1420). C'est lui qui
  # rend l'URL publique joignable ; s'il tombe, éviter de publier 'open'.
  if curl -s -m 5 -o /dev/null "http://127.0.0.1:3001/api/health" 2>/dev/null; then MODE="open"; else MODE="closed"; fi
fi

STAMP="$(date '+%Y-%m-%d %H:%M')"
if [ "$MODE" = "open" ] && [ -f "$URL_FILE" ] && [ -s "$URL_FILE" ]; then
  URL="$(tr -d '[:space:]' < "$URL_FILE")"
  if [[ ! "$URL" =~ ^https://[a-z0-9-]+\.trycloudflare\.com/?$ ]]; then
    echo "[publish] URL de tunnel invalide: $URL" >&2
    exit 1
  fi
  BLOCK="🟢 **Ouvert !** Accès en direct : **[$URL]($URL)**

_Mis à jour le $STAMP. Le lien n'est valable que quand mon PC est allumé._"
  TUNNEL_CONTENT="$URL"$'\n'
  MSG="Studio ouvert — $STAMP"
else
  BLOCK="🔴 **Fermé pour le moment** — en maintenance / réparation, ou simplement éteint.

Pour toute question ou plus d'infos, contactez-moi : Snap \`jrabuteau.py\` · Instagram \`world_of_juan23\` · Mail \`rabuteaujuandavid@gmail.com\`.

_Mis à jour le $STAMP._"
  # Un telephone qui lit le fichier brut ne doit jamais recuperer une URL
  # perimee apres l'arret du studio.
  TUNNEL_CONTENT=""
  MSG="Studio ferme — $STAMP"
fi

python3 - "$LIVE_REPO/README.md" "$LIVE_TUNNEL_FILE" "$BLOCK" "$TUNNEL_CONTENT" <<'PY'
import sys, re
path, tunnel_path, block, tunnel_content = sys.argv[1:]
s = open(path, encoding="utf-8").read()
s = re.sub(r"<!--STATUS-->.*?<!--/STATUS-->",
          "<!--STATUS-->\n%s\n<!--/STATUS-->" % block, s, flags=re.S)
open(path, "w", encoding="utf-8").write(s)
open(tunnel_path, "w", encoding="utf-8").write(tunnel_content)
PY

cd "$LIVE_REPO" || exit 0
git add -- README.md tunnel.txt
if git diff --cached --quiet -- README.md tunnel.txt; then
  echo "[publish] etat inchange ($MODE)"
else
  git -c user.name="Juan Rabuteau" -c user.email="rabuteaujuandavid@gmail.com" \
    commit --only -q -m "$MSG" -- README.md tunnel.txt
  git push -q origin main && echo "[publish] etat publie: $MODE" || echo "[publish] push echoue"
fi
