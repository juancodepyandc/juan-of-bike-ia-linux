#!/usr/bin/env bash
# Publish only a verified public bridge; failed pushes remain retryable.
set -euo pipefail
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LIVE_REPO="${AURORA_LIVE_REPO:-$ROOT_DIR/../aurora-live}"
MODE="${1:-auto}"
case "$MODE" in auto|open|closed) ;; *) echo '[publish] invalid mode' >&2; exit 2 ;; esac
[ -d "$LIVE_REPO/.git" ] || { echo '[publish] discovery repository missing' >&2; exit 1; }
# Serialize local publishers, including shutdown vs watcher. flock is optional
# only because this compatibility entry is for Bash; the monitor is portable.
exec 9>"$LIVE_REPO/.git/aurora-publish.lock"
if command -v flock >/dev/null 2>&1; then flock -w 30 9 || exit 1; fi
cd "$LIVE_REPO"
# Push previously committed state first. Do not silently lose a failed push.
git fetch -q origin main
git -c user.name="Aurora availability" -c user.email="41898282+github-actions[bot]@users.noreply.github.com" rebase -X theirs origin/main
URL="$(tr -d '[:space:]' < "$ROOT_DIR/tunnel.txt")"
# Use the existing public-DNS fallback locally, and strict JSON service check.
if [ "$MODE" != closed ]; then
  if ! bash "$ROOT_DIR/scripts/verify-tunnel-url.sh" "$URL" 1 >/dev/null 2>&1; then MODE=closed; fi
fi
# closed never probes; auto/open independently verify the public endpoint.
python3 - "$LIVE_REPO" "$MODE" "$URL" <<'PYTHON'
import importlib.util, pathlib, sys
repo, mode, url = sys.argv[1:]
spec = importlib.util.spec_from_file_location('status_check', pathlib.Path(repo) / 'status_check.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
print(module.update(repo, mode, url, checker=lambda _: mode != 'closed'))
PYTHON
git add -- README.md tunnel.txt status.json
if ! git diff --cached --quiet -- README.md tunnel.txt status.json; then
  git -c user.name='Juan Rabuteau' -c user.email='rabuteaujuandavid@gmail.com' commit --only -q -m 'Verify Aurora public availability' -- README.md tunnel.txt status.json
fi
git push -q origin main
echo '[publish] state published'
