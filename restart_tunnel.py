"""
restart_tunnel.py — kill cloudflared + relance + capture la nouvelle URL.

Pourquoi : cloudflared --url génère une URL trycloudflare.com aléatoire à
chaque démarrage. Si le tunnel a été redémarré (crash, reboot, kill manuel)
sans que start-aurora.bat soit relancé, le `tunnel_url.txt` du repo
contient une URL morte qui ne résout plus.

update-aurora.bat appelle ce script pour :
  1. tuer tout cloudflared.exe en cours
  2. lancer un nouveau cloudflared --url http://localhost:3001 en arrière-plan
  3. sniffer son stdout pendant ~15s pour capturer la ligne contenant
     "https://*.trycloudflare.com"
  4. écrire l'URL trouvée dans tunnel_url.txt + l'afficher en gros

Le bridge_server.py reste sur :3001, le tunnel pointe dessus, Vite tourne
en proxy via le bridge sur :1420.
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
import threading
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent
CLOUDFLARED = REPO_ROOT / "tools" / "cloudflared.exe"
TUNNEL_URL_FILE = REPO_ROOT / "tunnel_url.txt"
URL_RE = re.compile(r"https://[a-z0-9-]+\.trycloudflare\.com")
WAIT_SECONDS = 20.0


def kill_existing_cloudflared() -> int:
    """Kill all running cloudflared.exe processes. Returns count killed."""
    killed = 0
    try:
        # Windows-specific: tasklist + taskkill
        out = subprocess.run(
            ["tasklist", "/FI", "IMAGENAME eq cloudflared.exe", "/FO", "CSV", "/NH"],
            capture_output=True, text=True, timeout=10,
        )
        for line in out.stdout.splitlines():
            line = line.strip().strip('"')
            if not line or "cloudflared" not in line.lower():
                continue
            parts = [p.strip().strip('"') for p in line.split(',')]
            if len(parts) >= 2:
                pid = parts[1]
                try:
                    subprocess.run(["taskkill", "/F", "/PID", pid], capture_output=True, timeout=5)
                    killed += 1
                except Exception:
                    pass
    except Exception as e:
        print(f"[!] kill_existing_cloudflared failed: {e}", flush=True)
    return killed


def main() -> int:
    if not CLOUDFLARED.exists():
        print(f"[x] cloudflared introuvable: {CLOUDFLARED}", flush=True)
        return 1

    print(f"[1/3] kill cloudflared.exe en cours...", flush=True)
    killed = kill_existing_cloudflared()
    print(f"      {killed} process(es) terminé(s)", flush=True)
    time.sleep(1.0)

    print(f"[2/3] start cloudflared tunnel --url http://localhost:3001", flush=True)
    proc = subprocess.Popen(
        [str(CLOUDFLARED), "tunnel", "--url", "http://localhost:3001"],
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        text=True, encoding='utf-8', errors='replace',
        bufsize=1,
        # CREATE_NEW_PROCESS_GROUP so the parent bat closing doesn't kill it
        creationflags=getattr(subprocess, 'CREATE_NEW_PROCESS_GROUP', 0),
    )

    found_url: str | None = None
    deadline = time.time() + WAIT_SECONDS

    print(f"[3/3] sniff stdout pendant {WAIT_SECONDS:.0f}s pour trouver l'URL...", flush=True)

    def reader():
        nonlocal found_url
        try:
            assert proc.stdout is not None
            for line in proc.stdout:
                line = line.rstrip()
                if not line:
                    continue
                # Print ALL cloudflared output so the user sees what's happening
                print(f"  cf> {line}", flush=True)
                m = URL_RE.search(line)
                if m and not found_url:
                    found_url = m.group(0)
        except Exception:
            pass

    t = threading.Thread(target=reader, daemon=True)
    t.start()

    while time.time() < deadline and not found_url:
        time.sleep(0.3)

    if not found_url:
        print(f"[x] Aucune URL trycloudflare.com trouvée dans la sortie cloudflared en {WAIT_SECONDS:.0f}s", flush=True)
        print(f"    Le bridge :3001 tourne-t-il ? (start-aurora.bat lance Bridge avant Tunnel)", flush=True)
        return 2

    # Read the previous URL to skip the auto-commit if nothing changed.
    previous = ""
    try:
        if TUNNEL_URL_FILE.exists():
            previous = TUNNEL_URL_FILE.read_text(encoding='utf-8').strip().splitlines()[0]
    except OSError:
        pass

    try:
        TUNNEL_URL_FILE.write_text(found_url + "\n", encoding='utf-8')
    except Exception as e:
        print(f"[!] échec écriture tunnel_url.txt: {e}", flush=True)

    # Auto-commit + push the URL change so any future Claude session sees
    # the live URL via SessionStart hook (which reads tunnel_url.txt) and
    # knows where to probe. Best-effort: a failed push doesn't fail the
    # tunnel restart (already running locally).
    if previous != found_url:
        print(f"[+] tunnel URL changée ({previous or '∅'} → {found_url}), push origin/main", flush=True)
        try:
            subprocess.run(
                ["git", "-C", str(REPO_ROOT), "add", "tunnel_url.txt"],
                capture_output=True, timeout=10,
            )
            commit_msg = f"tunnel: {found_url}"
            r = subprocess.run(
                ["git", "-C", str(REPO_ROOT), "commit", "-m", commit_msg],
                capture_output=True, text=True, timeout=15,
            )
            if r.returncode == 0:
                p = subprocess.run(
                    ["git", "-C", str(REPO_ROOT), "push", "origin", "main"],
                    capture_output=True, text=True, timeout=30,
                )
                if p.returncode == 0:
                    print(f"  push OK", flush=True)
                else:
                    print(f"  push échec (best-effort): {p.stderr.strip()[:200]}", flush=True)
            else:
                # commit can fail if nothing staged or hook rejects — non-fatal
                print(f"  commit non fait: {r.stderr.strip()[:200] or r.stdout.strip()[:200]}", flush=True)
        except Exception as e:
            print(f"  auto-push skipped (best-effort): {e}", flush=True)
    else:
        print(f"[=] tunnel URL inchangée ({found_url}), pas de push", flush=True)

    print("", flush=True)
    print("=" * 60, flush=True)
    print(f"  NOUVELLE URL TUNNEL :", flush=True)
    print(f"  {found_url}", flush=True)
    print("=" * 60, flush=True)
    print(f"  Sauvegardée dans tunnel_url.txt + commitée sur main.", flush=True)
    print(f"  Le process cloudflared reste actif en arrière-plan.", flush=True)
    print(f"  Ouvre cette URL dans ton navigateur (Ctrl+F5 si onglet ancien).", flush=True)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        sys.exit(130)
