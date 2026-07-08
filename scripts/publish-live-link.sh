#!/usr/bin/env bash
# Publie l'ETAT du studio dans le repo aurora-live (README, section <!--STATUS-->) et pousse sur GitHub :
#  - OUVERT  : affiche l'adresse publique en cours (tunnel Cloudflare)
#  - FERME   : affiche une page maintenance + contacts
# Mode : "open" | "closed" | "auto" (auto = teste si l'app repond sur 127.0.0.1:1420). Defaut auto.
set -uo pipefail

AURORA_DIR="/home/juan/AuroraIA"
LIVE_REPO="/home/juan/aurora-live"
URL_FILE="$AURORA_DIR/tunnel_url.txt"
MODE="${1:-auto}"

[ -d "$LIVE_REPO/.git" ] || { echo "[publish] $LIVE_REPO absent"; exit 0; }

if [ "$MODE" = "auto" ]; then
  if curl -s -m 5 -o /dev/null "http://127.0.0.1:1420/" 2>/dev/null; then MODE="open"; else MODE="closed"; fi
fi

STAMP="$(date '+%Y-%m-%d %H:%M')"
if [ "$MODE" = "open" ] && [ -f "$URL_FILE" ] && [ -s "$URL_FILE" ]; then
  URL="$(tr -d '[:space:]' < "$URL_FILE")"
  BLOCK="🟢 **Ouvert !** Accès en direct : **[$URL]($URL)**

_Mis à jour le $STAMP. Le lien n'est valable que quand mon PC est allumé._"
  MSG="Studio ouvert — $STAMP"
else
  BLOCK="🔴 **Fermé pour le moment** — en maintenance / réparation, ou simplement éteint.

Pour toute question ou plus d'infos, contactez-moi : Snap \`jrabuteau.py\` · Instagram \`world_of_juan23\` · Mail \`rabuteaujuandavid@gmail.com\`.

_Mis à jour le $STAMP._"
  MSG="Studio ferme — $STAMP"
fi

python3 - "$LIVE_REPO/README.md" "$BLOCK" <<'PY'
import sys, re
path, block = sys.argv[1], sys.argv[2]
s = open(path, encoding="utf-8").read()
s = re.sub(r"<!--STATUS-->.*?<!--/STATUS-->",
          "<!--STATUS-->\n%s\n<!--/STATUS-->" % block, s, flags=re.S)
open(path, "w", encoding="utf-8").write(s)
PY

cd "$LIVE_REPO" || exit 0
git add -A
if git diff --cached --quiet; then
  echo "[publish] etat inchange ($MODE)"
else
  git -c user.name="Juan Rabuteau" -c user.email="rabuteaujuandavid@gmail.com" commit -q -m "$MSG"
  git push -q origin main 2>/dev/null && echo "[publish] etat publie: $MODE" || echo "[publish] push echoue"
fi
