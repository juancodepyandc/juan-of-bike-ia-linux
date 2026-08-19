#!/usr/bin/env bash
# Point d'entree de l'icone Linux AuroraIA : le terminal conserve les
# diagnostics et affiche l'URL telephone verifiee avant d'ouvrir Tauri.
set -u

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
APP_BIN="$ROOT_DIR/application/src-tauri/target/release/juan-of-bike-ia"

echo
echo "========================================"
echo "  AURORA IA — lancement Linux"
echo "========================================"
echo

if ! AURORA_START_TUNNEL=1 bash "$ROOT_DIR/start-aurora.sh"; then
  echo
  echo "[ERREUR] Le lancement complet a echoue. Consulte les lignes ci-dessus."
  echo "Logs : ${TMPDIR:-/tmp}/auroraia"
  read -r -p "Appuie sur Entree pour fermer ce terminal..." _
  exit 1
fi

echo
if [ -s "$ROOT_DIR/tunnel.txt" ]; then
  TUNNEL_URL="$(tr -d '[:space:]' < "$ROOT_DIR/tunnel.txt")"
  echo "URL telephone verifiee : $TUNNEL_URL"
  echo "GitHub aurora-live    : https://github.com/juancodepyandc/aurora-live"
else
  echo "[ATTENTION] Aucune URL publique valide n'a ete produite."
fi

if [ ! -x "$APP_BIN" ]; then
  echo "[ERREUR] Binaire Tauri absent : $APP_BIN"
  read -r -p "Appuie sur Entree pour fermer ce terminal..." _
  exit 1
fi

echo
echo "Ouverture de l'application native AuroraIA..."
exec "$APP_BIN"
