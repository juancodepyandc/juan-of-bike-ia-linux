#!/usr/bin/env bash
# Met à jour le lien public (tunnel Cloudflare) dans le repo aurora-live et le pousse sur GitHub,
# pour que l'adresse en cours soit toujours visible en ligne. Appelé par start-aurora après le tunnel.
set -uo pipefail

AURORA_DIR="/home/juan/AuroraIA"
LIVE_REPO="/home/juan/aurora-live"
URL_FILE="$AURORA_DIR/tunnel_url.txt"

[ -f "$URL_FILE" ] || { echo "[publish] pas de tunnel_url.txt — rien à publier"; exit 0; }
URL="$(tr -d '[:space:]' < "$URL_FILE")"
[ -n "$URL" ] || { echo "[publish] URL vide"; exit 0; }
[ -d "$LIVE_REPO/.git" ] || { echo "[publish] $LIVE_REPO n'est pas un repo git"; exit 0; }

STAMP="$(date '+%Y-%m-%d %H:%M')"
BLOCK="**👉 [$URL]($URL)**

_En ligne — mis à jour le $STAMP._"

# remplace le contenu entre les marqueurs <!--LIVE--> et <!--/LIVE-->
python3 - "$LIVE_REPO/README.md" "$BLOCK" <<'PY'
import sys, re
path, block = sys.argv[1], sys.argv[2]
s = open(path, encoding="utf-8").read()
s = re.sub(r"<!--LIVE-->.*?<!--/LIVE-->",
          "<!--LIVE-->\n%s\n<!--/LIVE-->" % block, s, flags=re.S)
open(path, "w", encoding="utf-8").write(s)
PY

cd "$LIVE_REPO" || exit 0
git add -A
if git diff --cached --quiet; then
  echo "[publish] lien inchangé"
else
  git commit -q -m "Mise à jour du lien en direct ($STAMP)"
  git push -q origin main 2>/dev/null && echo "[publish] lien publié : $URL" || echo "[publish] push échoué (vérifie la connexion GitHub)"
fi
