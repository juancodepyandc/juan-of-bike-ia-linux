#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_DIR="$ROOT_DIR/application"
LOG_DIR="${TMPDIR:-/tmp}/auroraia"

mkdir -p "$LOG_DIR"

# Serialize cooperating launches without letting long-lived children retain
# the lock. Existing services and missions continue while another launch waits.
if command -v flock >/dev/null 2>&1 && [ "${AURORA_LAUNCH_LOCKED:-0}" != "1" ]; then
  exec flock --close --wait 300 "$LOG_DIR/launch.lock" \
    env AURORA_LAUNCH_LOCKED=1 bash "$ROOT_DIR/start-aurora.sh"
fi

LAUNCH_RUNTIME="$ROOT_DIR/scripts/launch_runtime.py"

wait_for_http() {
  local label="$1"
  local url="$2"
  local timeout_seconds="$3"
  local attempt

  for attempt in $(seq 1 "$timeout_seconds"); do
    if curl -fsS -m 3 -o /dev/null "$url" 2>/dev/null; then
      echo "      $label pret: $url"
      return 0
    fi
    sleep 1
  done

  echo "      ERREUR: $label ne repond pas apres ${timeout_seconds}s: $url" >&2
  return 1
}

bridge_is_running() {
  "$APP_PY" - <<'PY'
import json
import sys
import urllib.request

try:
    with urllib.request.urlopen("http://127.0.0.1:3001/api/health", timeout=2) as response:
        data = json.load(response)
    ready = isinstance(data, dict) and data.get("ok") is True and data.get("service") == "aurora-bridge"
except (OSError, ValueError):
    ready = False
sys.exit(0 if ready else 1)
PY
}

daemon_is_running() {
  "$APP_PY" - "$ROOT_DIR" <<'PY'
import sys
sys.path.insert(0, sys.argv[1])
from agi_core.bus import probe_sync

sys.exit(0 if probe_sync(timeout=2).get("ok") is True else 1)
PY
}

wait_for_protocol() {
  local label="$1" probe="$2" deadline=$((SECONDS + $3))
  while [ "$SECONDS" -lt "$deadline" ]; do
    if "$probe"; then
      echo "      $label prêt (protocole vérifié)."
      return 0
    fi
    sleep 1
  done
  echo "      ERREUR: $label supervisé ne devient pas prêt après ${3}s." >&2
  return 1
}

run_agi_supervisor() {
  # Another launcher/systemd may finish starting the daemon between probes.
  # Reuse its protocol endpoint instead of repeatedly losing the port race.
  while true; do
    if daemon_is_running; then
      echo "Démon AGI existant réutilisé; superviseur local arrêté." >> "$LOG_DIR/agi_daemon.log"
      return 0
    fi
    echo "Démarrage du démon AGI..." >> "$LOG_DIR/agi_daemon.log"
    if (cd "$ROOT_DIR" && exec "$APP_PY" aurora_agi_daemon.py >> "$LOG_DIR/agi_daemon.log" 2>&1); then
      echo "Arrêt propre (code 0)" >> "$LOG_DIR/agi_daemon.log"
      return 0
    else
      local exit_code=$?
      if daemon_is_running; then
        echo "Démon AGI existant réutilisé après sortie du processus local; aucun redémarrage." >> "$LOG_DIR/agi_daemon.log"
        return 0
      fi
      echo "ERREUR CRITIQUE AGI: Crash avec le code $exit_code." >> "$LOG_DIR/agi_daemon.log"
      echo "Tentative de redémarrage dans 5 secondes..." >> "$LOG_DIR/agi_daemon.log"
      sleep 5
    fi
  done
}

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
# 31/07: 10m gardait CHAQUE modele (vision 19 Go incluse) resident pendant
# que TRELLIS debordait en RAM — c'etait la cause du « Ollama n'a pas libere
# les modeles avant le swap » observe 3 fois. 60s suffit au confort de la
# conversation; les generations 3D/image font de toute facon leur eviction
# explicite aux points chauds.
export OLLAMA_KEEP_ALIVE="${OLLAMA_KEEP_ALIVE:-60s}"
export PYTORCH_CUDA_ALLOC_CONF="${PYTORCH_CUDA_ALLOC_CONF:-expandable_segments:True}"
export TOKENIZERS_PARALLELISM="${TOKENIZERS_PARALLELISM:-false}"

echo "[1/5] Ollama"
if curl -fsS -m 3 -o /dev/null http://127.0.0.1:11434/api/version 2>/dev/null; then
  echo "      Ollama existant réutilisé."
elif command -v ollama >/dev/null 2>&1; then
  (ollama serve >"$LOG_DIR/ollama.log" 2>&1 &)
  wait_for_http "Ollama" "http://127.0.0.1:11434/api/version" 30
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

if curl -fsS -m 3 -o /dev/null http://127.0.0.1:8188/system_stats 2>/dev/null; then
  echo "      ComfyUI existant réutilisé."
elif [ -z "${AURORA_COMFY_ARGS+x}" ] && \
     [ "$(systemctl --user show aurora-comfyui.service -p LoadState --value 2>/dev/null || true)" = "loaded" ]; then
  # Preserve the installed unit's memory limits and restart policy.
  systemctl --user start aurora-comfyui.service
elif [ -n "$COMFY_DIR" ]; then
  if [ -x "$COMFY_DIR/venv/bin/python" ]; then
    COMFY_PY="$COMFY_DIR/venv/bin/python"
  else
    COMFY_PY="python3"
  fi
  COMFY_MEMORY_ARGS=()
  while IFS= read -r arg; do
    [ -z "$arg" ] || COMFY_MEMORY_ARGS+=("$arg")
  done < <("$APP_PY" "$APP_DIR/comfy_runtime.py" "$COMFY_DIR")
  (
    cd "$COMFY_DIR"
    exec "$COMFY_PY" main.py --listen 127.0.0.1 --port 8188 "${COMFY_MEMORY_ARGS[@]}"
  ) >"$LOG_DIR/comfyui.log" 2>&1 &
else
  echo "ComfyUI introuvable sous modele/comfyui; il sera lance a la demande si installe plus tard."
fi

echo "[3/5] Bridge Python"
if systemctl --user is-active --quiet aurora-bridge.service 2>/dev/null; then
  wait_for_protocol "Bridge supervisé" bridge_is_running 30
fi
if bridge_is_running; then
  echo "      Bridge existant réutilisé (API Aurora vérifiée)."
else
  (
    cd "$APP_DIR"
    # A service manager can have completed startup since the first probe.
    if bridge_is_running; then
      echo "Bridge existant réutilisé (API Aurora vérifiée)."
      exit 0
    fi
    exec "$APP_PY" bridge_server.py
  ) >"$LOG_DIR/bridge.log" 2>&1 &
fi

echo "[3.5/5] Cerveau AGI (J.O.B.I.A. Core)"
if systemctl --user is-active --quiet aurora-daemon.service 2>/dev/null; then
  wait_for_protocol "Démon AGI supervisé" daemon_is_running 30
fi
if daemon_is_running; then
  echo "      Démon AGI existant réutilisé (protocole IPC vérifié)."
else
  run_agi_supervisor &
  AGI_PID=$!
  echo "      AGI Daemon lancé en arrière-plan (PID: $AGI_PID, logs: $LOG_DIR/agi_daemon.log)"
fi

echo "[4/5] Interface (build + Vite)"
# 30/07: `npm` n'etait PAS dans le PATH de ce script (installe via nvm) ->
# la ligne echouait EN SILENCE, Vite ne demarrait jamais et l'application
# affichait le bundle `dist/` FIGE (celui du 26/07). Tout correctif d'UI
# semblait donc ignore. On resout node/npm explicitement, et on
# Vérifie les sources et les artefacts avant de reconstruire.
if ! command -v npm >/dev/null 2>&1; then
  for _n in "$HOME"/.nvm/versions/node/*/bin /usr/local/bin /usr/bin /opt/node/bin; do
    if [ -x "$_n/npm" ]; then PATH="$_n:$PATH"; export PATH; break; fi
  done
fi
if command -v npm >/dev/null 2>&1; then
  echo "      npm: $(command -v npm) ($(npm -v 2>/dev/null))"
  if "$APP_PY" "$LAUNCH_RUNTIME" build-current web --cache "$LOG_DIR/web-build.json"; then
    echo "      Interface compilée à jour (sources et artefacts vérifiés)."
  else
    if (cd "$APP_DIR" && npm run build >"$LOG_DIR/vite-build.log" 2>&1); then
      "$APP_PY" "$LAUNCH_RUNTIME" mark-build web --cache "$LOG_DIR/web-build.json"
      echo "      interface reconstruite"
    else
      echo "      ERREUR: build interface échoué, voir $LOG_DIR/vite-build.log" >&2
      exit 1
    fi
  fi
  if curl -fsS -m 3 -o /dev/null http://127.0.0.1:1420/ 2>/dev/null; then
    echo "      Interface Vite existante réutilisée."
  else
    (
      cd "$APP_DIR"
      exec npm run dev:web
    ) >"$LOG_DIR/vite.log" 2>&1 &
  fi
  # 30/07: l'app native est un binaire Tauri RELEASE — l'interface y est
  # INCORPOREE a la compilation. Reconstruire dist/ ne suffit PAS: si le
  # binaire est plus vieux que l'interface, on le recompile, sinon
  # l'utilisateur voit une UI perimee (6 jours d'ecart mesures, aucune
  # correction visible).
  _BIN="$APP_DIR/src-tauri/target/release/juan-of-bike-ia"
  if ! "$APP_PY" "$LAUNCH_RUNTIME" build-current native --cache "$LOG_DIR/native-build.json"; then
    echo "      binaire natif perime — recompilation Tauri (quelques minutes)..."
    [ -f "$HOME/.cargo/env" ] && . "$HOME/.cargo/env"
    if (cd "$APP_DIR" && npx tauri build --no-bundle >"$LOG_DIR/tauri-build.log" 2>&1); then
      # Tauri's beforeBuildCommand also rebuilds dist.
      "$APP_PY" "$LAUNCH_RUNTIME" mark-build web --cache "$LOG_DIR/web-build.json"
      "$APP_PY" "$LAUNCH_RUNTIME" mark-build native --cache "$LOG_DIR/native-build.json"
      echo "      binaire natif reconstruit"
    else
      echo "      ERREUR: recompilation native échouée, voir $LOG_DIR/tauri-build.log" >&2
      exit 1
    fi
  else
    echo "      Binaire natif à jour (Rust, bundle et binaire vérifiés)."
  fi
else
  echo "      ATTENTION: npm introuvable — l'interface restera sur le dernier build."
  echo "      (installez Node, ou ajoutez npm au PATH; sans lui aucun correctif d'UI n'apparait)"
fi

if ! wait_for_http "Bridge" "http://127.0.0.1:3001/api/health" 30; then
  bash "$ROOT_DIR/scripts/publish-live-link.sh" closed || true
  echo "Aurora reste locale, mais le tunnel n'est pas publie car le bridge est indisponible."
  exit 1
fi
if ! wait_for_http "Interface" "http://127.0.0.1:1420/" 30; then
  bash "$ROOT_DIR/scripts/publish-live-link.sh" closed || true
  echo "Aurora reste locale, mais le tunnel n'est pas publie car Vite est indisponible."
  exit 1
fi

echo "[5/5] Cloudflared"
# Linux est maintenant aligne sur le demarrage Aurora complet : le tunnel est
# actif par defaut. AURORA_START_TUNNEL=0 permet un lancement strictement local.
if [ "${AURORA_START_TUNNEL:-1}" = "1" ]; then
  if command -v cloudflared >/dev/null 2>&1; then
    EXISTING_TUNNEL_PIDS="$("$APP_PY" "$LAUNCH_RUNTIME" process-ids tunnel)"
    EXISTING_TUNNEL_URL="$(tr -d '[:space:]' < "$ROOT_DIR/tunnel.txt" 2>/dev/null || true)"
    if [ -n "$EXISTING_TUNNEL_PIDS" ] && [ -n "$EXISTING_TUNNEL_URL" ] && \
       bash "$ROOT_DIR/scripts/verify-tunnel-url.sh" "$EXISTING_TUNNEL_URL" 3; then
      echo "      Tunnel existant réutilisé : $EXISTING_TUNNEL_URL"
    else
      # Only terminate this user's tunnel targeting Aurora's bridge.
      for _pid in $EXISTING_TUNNEL_PIDS; do
        kill -TERM "$_pid" 2>/dev/null || true
      done
      : > "$LOG_DIR/cloudflared.log"
      # Le bridge proxyfie Vite et reste disponible pendant une reconstruction
      # de l'interface, exactement comme le point d'entree Aurora attendu.
      setsid cloudflared tunnel --url http://127.0.0.1:3001 >"$LOG_DIR/cloudflared.log" 2>&1 </dev/null &
      echo "  Tunnel demarre, recuperation de l'adresse publique..."
      TUN_URL=""
      for _i in $(seq 1 30); do
        TUN_URL="$(grep -am1 -oE 'https://[a-z0-9-]+\.trycloudflare\.com' "$LOG_DIR/cloudflared.log" 2>/dev/null || true)"
        [ -n "$TUN_URL" ] && break
        sleep 2
      done
      if [ -n "$TUN_URL" ]; then
        # Ne publie jamais une URL qui vient seulement d'etre annoncee par
        # cloudflared mais ne route pas encore vers Aurora. La verification
        # connait le DNS public Cloudflare, utile si la box filtre ce domaine.
        if bash "$ROOT_DIR/scripts/verify-tunnel-url.sh" "$TUN_URL" 45; then
          # tunnel.txt reste la source locale du bridge. Le script de publication
          # le copie dans aurora-live/tunnel.txt et met aussi le README a jour.
          printf '%s\n' "$TUN_URL" > "$ROOT_DIR/tunnel.txt"
          # Compatibilite avec les anciens outils qui lisaient encore ce nom.
          # Les deux fichiers locaux affichent donc toujours la MEME URL.
          printf '%s\n' "$TUN_URL" > "$ROOT_DIR/tunnel_url.txt"
          echo
          echo "  ========================================"
          echo "  URL TELEPHONE : $TUN_URL"
          echo "  GitHub        : https://github.com/juancodepyandc/aurora-live"
          echo "  URL brute     : https://raw.githubusercontent.com/juancodepyandc/aurora-live/main/tunnel.txt"
          echo "  ========================================"
          TUN_HOST="${TUN_URL#https://}"
          TUN_HOST="${TUN_HOST%%/*}"
          if ! getent ahostsv4 "$TUN_HOST" >/dev/null 2>&1; then
            echo "  NOTE DNS : ta box ne resout pas ce domaine. L'URL est verifiee"
            echo "  via DNS public; pour ce PC, utilise DNS 1.1.1.1 ou 8.8.8.8."
          fi
          bash "$ROOT_DIR/scripts/publish-live-link.sh" open \
            || echo "  (tunnel.txt mis a jour localement, publication aurora-live echouee)"
        else
          : > "$ROOT_DIR/tunnel.txt"
          : > "$ROOT_DIR/tunnel_url.txt"
          bash "$ROOT_DIR/scripts/publish-live-link.sh" closed || true
          echo "  Tunnel genere mais non joignable : non publie sur aurora-live."
        fi
      else
        echo "  Adresse du tunnel non recuperee (voir $LOG_DIR/cloudflared.log)."
      fi
    fi
  else
    echo "  cloudflared introuvable; lance scripts/linux/bootstrap-ubuntu2404.sh sur Linux."
  fi
else
  echo "  Tunnel non lance (AURORA_START_TUNNEL=0)."
fi

# Surveillance de l'etat -> publie "ouvert/ferme" sur le repo aurora-live automatiquement
if [ "${AURORA_START_TUNNEL:-1}" = "1" ] && [ -x "$ROOT_DIR/scripts/aurora-status-watcher.sh" ]; then
  if [ -n "$("$APP_PY" "$LAUNCH_RUNTIME" process-ids watcher)" ]; then
    echo "      Surveillance existante réutilisée."
  else
    setsid bash "$ROOT_DIR/scripts/aurora-status-watcher.sh" >"$LOG_DIR/status-watcher.log" 2>&1 </dev/null &
    echo "  Surveillance etat: active (repo aurora-live tenu a jour ouvert/ferme)"
  fi
fi

echo "Aurora demarre:"
echo "  UI      http://127.0.0.1:1420"
echo "  Bridge  http://127.0.0.1:3001"
echo "  Logs    $LOG_DIR"
