#!/usr/bin/env bash
# Valide qu'un quick tunnel Cloudflare route vraiment vers le bridge Aurora.
# Certaines box DNS repondent NXDOMAIN pour *.trycloudflare.com alors que
# l'adresse est parfaitement accessible depuis Internet. Dans ce cas on
# verifie aussi avec les IP obtenues aupres du DNS public Cloudflare.
set -euo pipefail

URL="${1:-}"
TIMEOUT_SECONDS="${2:-45}"

if [[ ! "$URL" =~ ^https://[a-z0-9-]+\.trycloudflare\.com/?$ ]]; then
  echo "[tunnel] URL invalide: $URL" >&2
  exit 2
fi
if [[ ! "$TIMEOUT_SECONDS" =~ ^[0-9]+$ ]] || [ "$TIMEOUT_SECONDS" -lt 1 ]; then
  echo "[tunnel] delai invalide: $TIMEOUT_SECONDS" >&2
  exit 2
fi

HOST="${URL#https://}"
HOST="${HOST%%/*}"
HEALTH_URL="${URL%/}/api/health"

is_aurora_health() {
  python3 -c 'import json, sys
try:
    data = json.load(sys.stdin)
    ready = isinstance(data, dict) and data.get("ok") is True and data.get("service") == "aurora-bridge"
except (ValueError, OSError):
    ready = False
sys.exit(0 if ready else 1)'
}

try_request() {
  # Cas normal : le resolv.conf local sait deja resoudre trycloudflare.com.
  if curl -fsS -m 5 "$HEALTH_URL" 2>/dev/null | is_aurora_health; then
    return 0
  fi

  # Fallback indispensable quand le DNS de la box bloque le wildcard
  # trycloudflare.com. `--resolve` garde le Host/SNI HTTPS original.
  local edge_ip
  if command -v dig >/dev/null 2>&1; then
    while IFS= read -r edge_ip; do
      [[ "$edge_ip" =~ ^([0-9]{1,3}\.){3}[0-9]{1,3}$ ]] || continue
      if curl -fsS -m 5 --resolve "$HOST:443:$edge_ip" "$HEALTH_URL" 2>/dev/null | is_aurora_health; then
        return 0
      fi
    done < <(dig +short @1.1.1.1 "$HOST" A 2>/dev/null)
  else
    # Fallback sans dnsutils/dig : DNS-over-HTTPS Cloudflare, puis Python
    # standard pour extraire les IPv4 de la reponse JSON.
    while IFS= read -r edge_ip; do
      [[ "$edge_ip" =~ ^([0-9]{1,3}\.){3}[0-9]{1,3}$ ]] || continue
      if curl -fsS -m 5 --resolve "$HOST:443:$edge_ip" "$HEALTH_URL" 2>/dev/null | is_aurora_health; then
        return 0
      fi
    done < <(
      curl -fsS -m 8 -H 'accept: application/dns-json' \
        "https://cloudflare-dns.com/dns-query?name=$HOST&type=A" 2>/dev/null \
        | python3 -c 'import json, sys; print("\n".join(str(x.get("data", "")) for x in json.load(sys.stdin).get("Answer", [])))' 2>/dev/null
    )
  fi
  return 1
}

for _attempt in $(seq 1 "$TIMEOUT_SECONDS"); do
  if try_request; then
    echo "[tunnel] URL publique verifiee: $URL"
    exit 0
  fi
  sleep 1
done

echo "[tunnel] URL non joignable apres ${TIMEOUT_SECONDS}s: $URL" >&2
exit 1
