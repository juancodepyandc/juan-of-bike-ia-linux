import socket
import httpx

_orig = socket.getaddrinfo

def patch_dns(host, port, family=0, type=0, proto=0, flags=0):
    if host.endswith(".trycloudflare.com"):
        print(f"Intercepted DNS for {host}")
        # Resolve via Cloudflare DoH (1.1.1.1) or Google
        r = httpx.get(f"https://cloudflare-dns.com/dns-query?name={host}&type=A", headers={"accept": "application/dns-json"})
        ip = r.json()["Answer"][0]["data"]
        print(f"Resolved to {ip}")
        return _orig(ip, port, family, type, proto, flags)
    return _orig(host, port, family, type, proto, flags)

socket.getaddrinfo = patch_dns

# Now test httpx
try:
    r = httpx.get("https://spell-usa-varying-generate.trycloudflare.com/api/cli/status")
    print("SUCCESS", r.status_code)
except Exception as e:
    print("ERROR", e)
