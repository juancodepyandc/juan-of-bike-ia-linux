"""
restart_tunnel.py — kill cloudflared + relance + capture la nouvelle URL.

Pourquoi : cloudflared --url génère une URL trycloudflare.com aléatoire à
chaque démarrage. Si le tunnel a été redémarré (crash, reboot, kill manuel)
sans que start-aurora.sh soit relancé, le `tunnel.txt` du repo
contient une URL morte qui ne résout plus.

update-aurora.bat appelle ce script pour :
  1. tuer tout cloudflared.exe en cours
  2. lancer un nouveau cloudflared --url http://localhost:3001 en arrière-plan
  3. sniffer son stdout pendant ~15s pour capturer la ligne contenant
     "https://*.trycloudflare.com"
  4. écrire l'URL trouvée dans tunnel.txt + l'afficher en gros

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

import shutil as _shutil
import sys as _sys

REPO_ROOT = Path(__file__).resolve().parent
_IS_WINDOWS = _sys.platform.startswith("win")
# Cross-plateforme: sur Linux/mac, cloudflared est dans le PATH (pas de .exe).
if _IS_WINDOWS:
    CLOUDFLARED = str(REPO_ROOT / "tools" / "cloudflared.exe")
else:
    CLOUDFLARED = _shutil.which("cloudflared") or str(REPO_ROOT / "tools" / "cloudflared")
TUNNEL_URL_FILE = REPO_ROOT / "tunnel.txt"
LEGACY_TUNNEL_URL_FILE = REPO_ROOT / "tunnel_url.txt"
URL_RE = re.compile(r"https://[a-z0-9-]+\.trycloudflare\.com")
WAIT_SECONDS = 20.0


def kill_existing_cloudflared() -> int:
    """Kill all running cloudflared processes. Returns count killed."""
    killed = 0
    if not _IS_WINDOWS:
        # Linux/mac: pkill par nom de process.
        try:
            r = subprocess.run(["pkill", "-f", "cloudflared tunnel"], capture_output=True, timeout=10)
            killed = 1 if r.returncode == 0 else 0
        except Exception as e:  # noqa: BLE001
            print(f"[!] pkill cloudflared failed: {e}", flush=True)
        return killed
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
    if not CLOUDFLARED or not Path(CLOUDFLARED).exists():
        print(f"[x] cloudflared introuvable: {CLOUDFLARED}", flush=True)
        print(f"    Sur Linux: installe cloudflared (dans le PATH) ou place le binaire dans tools/.", flush=True)
        return 1

    print(f"[1/3] kill cloudflared en cours...", flush=True)
    killed = kill_existing_cloudflared()
    print(f"      {killed} process(es) terminé(s)", flush=True)
    time.sleep(1.0)

    print(f"[2/3] start cloudflared tunnel --protocol http2 --url http://127.0.0.1:3001", flush=True)
    log_path = Path(os.environ.get("TMPDIR", "/tmp")) / "cloudflared.log"
    log_file = open(log_path, "w+", encoding="utf-8")
    proc = subprocess.Popen(
        [str(CLOUDFLARED), "tunnel", "--protocol", "http2", "--url", "http://127.0.0.1:3001"],
        stdout=log_file, stderr=subprocess.STDOUT,
        start_new_session=True if not _IS_WINDOWS else False,
        creationflags=getattr(subprocess, 'CREATE_NEW_PROCESS_GROUP', 0) if _IS_WINDOWS else 0,
    )

    found_url: str | None = None
    deadline = time.time() + WAIT_SECONDS

    print(f"[3/3] sniff stdout pendant {WAIT_SECONDS:.0f}s pour trouver l'URL...", flush=True)

    read_pos = 0
    while time.time() < deadline and not found_url:
        time.sleep(0.4)
        try:
            log_file.seek(read_pos)
            lines = log_file.readlines()
            read_pos = log_file.tell()
            for line in lines:
                line = line.rstrip()
                if not line:
                    continue
                print(f"  cf> {line}", flush=True)
                m = URL_RE.search(line)
                if m and not found_url:
                    found_url = m.group(0)
        except Exception:
            pass

    if not found_url:
        print(f"[x] Aucune URL trycloudflare.com trouvée dans la sortie cloudflared en {WAIT_SECONDS:.0f}s", flush=True)
        print(f"    Le bridge :3001 tourne-t-il ? (start-aurora.bat lance Bridge avant Tunnel)", flush=True)
        return 2

    # Read the previous URL to skip the public-repository update if unchanged.
    previous = ""
    try:
        if TUNNEL_URL_FILE.exists():
            previous = TUNNEL_URL_FILE.read_text(encoding='utf-8').strip().splitlines()[0]
    except OSError:
        pass

    try:
        TUNNEL_URL_FILE.write_text(found_url + "\n", encoding='utf-8')
        LEGACY_TUNNEL_URL_FILE.write_text(found_url + "\n", encoding='utf-8')
    except Exception as e:
        print(f"[!] échec écriture tunnel.txt: {e}", flush=True)

    # Publish the URL to the public aurora-live repository. The source file
    # stays local to AuroraIA; publish-live-link.sh copies it into
    # aurora-live/tunnel.txt and updates the landing README atomically.
    if previous != found_url:
        print(f"[+] tunnel URL changée ({previous or '∅'} → {found_url}), publication aurora-live", flush=True)
        try:
            p = subprocess.run(
                ["bash", str(REPO_ROOT / "scripts" / "publish-live-link.sh"), "open"],
                capture_output=True, text=True, timeout=45,
            )
            if p.returncode == 0:
                print(f"  aurora-live mis à jour", flush=True)
            else:
                print(f"  publication échec (best-effort): {p.stderr.strip()[:200] or p.stdout.strip()[:200]}", flush=True)
        except Exception as e:
            print(f"  publication ignoree (best-effort): {e}", flush=True)
    else:
        print(f"[=] tunnel URL inchangée ({found_url}), pas de push", flush=True)

    print("", flush=True)
    print("=" * 60, flush=True)
    print(f"  NOUVELLE URL TUNNEL :", flush=True)
    print(f"  {found_url}", flush=True)
    print("=" * 60, flush=True)
    print(f"  Sauvegardée dans tunnel.txt + publiée dans aurora-live.", flush=True)
    print(f"  Le process cloudflared reste actif en arrière-plan.", flush=True)
    print(f"  Ouvre cette URL dans ton navigateur (Ctrl+F5 si onglet ancien).", flush=True)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        sys.exit(130)
