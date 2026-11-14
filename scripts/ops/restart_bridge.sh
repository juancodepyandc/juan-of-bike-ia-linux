#!/bin/bash
# Relance le pont Aurora (bridge_server.py, port 3001) en conservant l'environnement
# et le journal du pont en place : start-aurora.sh exporte des variables (Ollama,
# PyTorch, verrou de lancement) qu'une relance « à nu » perdrait.
# Refuse de couper le pont tant qu'un travail Python y tourne, sauf --force.
set -u
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
APP="$ROOT/application"
PY="$APP/.venv/bin/python"
URL="http://127.0.0.1:3001/api/health"
FORCE=0
[ "${1:-}" = "--force" ] && FORCE=1

if [ ! -x "$PY" ]; then
  echo "ERREUR: interpréteur introuvable: $PY" >&2
  exit 2
fi
if ! "$PY" -c "import ast,sys; ast.parse(open(sys.argv[1], encoding='utf-8').read())" "$APP/bridge_server.py"; then
  echo "ERREUR: bridge_server.py ne se lit pas ; le pont en place est conservé." >&2
  exit 2
fi

pid="$(pgrep -f "bridge_server.py" | head -n 1)"
log="${TMPDIR:-/tmp}/auroraia/bridge.log"
envs=()
if [ -n "$pid" ] && [ -r "/proc/$pid/environ" ]; then
  running="$(curl -fsS -m 5 "$URL" 2>/dev/null | "$PY" -c "import json,sys; print(json.load(sys.stdin).get('pythonJobs',{}).get('running',0))" 2>/dev/null || echo "?")"
  if [ "$running" != "0" ] && [ "$FORCE" != "1" ]; then
    echo "REFUS: $running travail(aux) en cours sur le pont (ou état illisible). Relancer avec --force pour couper quand même." >&2
    exit 3
  fi
  mapfile -d '' envs < "/proc/$pid/environ"
  current_log="$(readlink "/proc/$pid/fd/1" 2>/dev/null || true)"
  case "$current_log" in /*.log) log="$current_log" ;; esac
  kill -TERM "$pid" 2>/dev/null
  for _ in $(seq 1 20); do
    kill -0 "$pid" 2>/dev/null || break
    sleep 0.5
  done
  kill -0 "$pid" 2>/dev/null && kill -KILL "$pid" 2>/dev/null
fi

mkdir -p "$(dirname "$log")"
cd "$APP" || exit 2
if [ "${#envs[@]}" -gt 0 ]; then
  setsid env -i "${envs[@]}" "$PY" bridge_server.py >>"$log" 2>&1 </dev/null &
else
  setsid "$PY" bridge_server.py >>"$log" 2>&1 </dev/null &
fi

for _ in $(seq 1 90); do
  if curl -fsS -m 2 -o /dev/null "$URL" 2>/dev/null; then
    echo "Pont relancé (pid $(pgrep -f "bridge_server.py" | head -n 1)), journal: $log"
    exit 0
  fi
  sleep 1
done
echo "ERREUR: le pont ne répond pas après 90 s ; voir $log" >&2
tail -n 25 "$log" >&2
exit 1
