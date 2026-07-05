"""Network ops for the cyber lab: DNS, TLS cert, WHOIS, HTTP headers, port scan.

All offensive probes (port scan, traceroute) are restricted to loopback and
RFC1918 private networks by `_safety.assert_private`.
"""
from __future__ import annotations

import argparse
import json
import socket
import ssl
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

REQUIRED = {
    "dns": "dnspython",
    "whois": "python-whois",
    "cryptography": "cryptography",
    "requests": "requests",
}


def ensure_deps() -> None:
    missing = []
    for import_name, pip_name in REQUIRED.items():
        try:
            __import__(import_name)
        except ImportError:
            missing.append(pip_name)
    if missing:
        print(f"PROGRESS:install:Installing {', '.join(missing)}", flush=True)
        subprocess.check_call(
            [sys.executable, "-m", "pip", "install", "--quiet", *missing],
            stdout=subprocess.DEVNULL,
        )


ensure_deps()

sys.path.insert(0, str(Path(__file__).parent))
from _safety import (  # noqa: E402
    MAX_PORT_SCAN_SECONDS,
    assert_private,
    check_time_budget,
    sanitize_ports,
)


# --- DNS ---------------------------------------------------------------------

def dns_lookup(domain: str) -> dict:
    import dns.resolver

    kinds = ["A", "AAAA", "MX", "TXT", "NS", "CNAME", "SOA"]
    out: dict = {"domain": domain, "records": {}}
    for k in kinds:
        try:
            answers = dns.resolver.resolve(domain, k, lifetime=6)
            out["records"][k] = [r.to_text() for r in answers]
        except Exception as exc:  # noqa: BLE001 — best effort per record
            out["records"][k] = {"error": type(exc).__name__}
    return out


# --- TLS certificate ---------------------------------------------------------

def tls_cert(host: str, port: int = 443) -> dict:
    from cryptography import x509
    from cryptography.hazmat.backends import default_backend

    pem = ssl.get_server_certificate((host, port), timeout=8)
    cert = x509.load_pem_x509_certificate(pem.encode(), default_backend())

    def _name(n):
        return ", ".join(f"{a.oid._name}={a.value}" for a in n)

    try:
        sans = cert.extensions.get_extension_for_class(
            x509.SubjectAlternativeName,
        ).value.get_values_for_type(x509.DNSName)
    except x509.ExtensionNotFound:
        sans = []

    return {
        "host": host,
        "port": port,
        "subject": _name(cert.subject),
        "issuer": _name(cert.issuer),
        "not_before": cert.not_valid_before_utc.isoformat(),
        "not_after": cert.not_valid_after_utc.isoformat(),
        "serial": hex(cert.serial_number),
        "signature_algo": cert.signature_algorithm_oid._name,
        "version": cert.version.name,
        "sans": sans,
        "days_left": (cert.not_valid_after_utc - datetime.now(timezone.utc)).days,
        "pem": pem,
    }


# --- WHOIS -------------------------------------------------------------------

def whois_lookup(domain: str) -> dict:
    import whois

    info = whois.whois(domain)

    def _ser(v):
        if isinstance(v, list):
            return [_ser(x) for x in v]
        if isinstance(v, datetime):
            return v.isoformat()
        return v

    return {k: _ser(v) for k, v in dict(info).items() if v is not None}


# --- HTTP headers inspector --------------------------------------------------

SECURITY_HEADERS = [
    "Content-Security-Policy",
    "Strict-Transport-Security",
    "X-Frame-Options",
    "X-Content-Type-Options",
    "Referrer-Policy",
    "Permissions-Policy",
    "Cross-Origin-Opener-Policy",
    "Cross-Origin-Embedder-Policy",
    "Cross-Origin-Resource-Policy",
]


def http_headers(url: str) -> dict:
    import requests

    r = requests.get(url, timeout=10, allow_redirects=True, headers={"User-Agent": "AuroraCyberLab/1.0"})
    got = {k: v for k, v in r.headers.items()}
    got_lower = {k.lower() for k in got}
    missing = [h for h in SECURITY_HEADERS if h.lower() not in got_lower]
    present = [h for h in SECURITY_HEADERS if h.lower() in got_lower]
    security_score = round((len(present) / len(SECURITY_HEADERS)) * 100)
    return {
        "url": r.url,
        "status": r.status_code,
        "headers": got,
        "present": present,
        "missing": missing,
        "securityScore": security_score,
        "missing_security_headers": missing,
        "ttfb_ms": int(r.elapsed.total_seconds() * 1000),
    }


# --- Port scan (restricted) --------------------------------------------------

COMMON_PORTS = [21, 22, 23, 25, 53, 80, 110, 143, 443, 445, 3306, 3389, 5432, 6379, 8080, 8443]


def port_scan(target: str, ports: list[int] | None = None, timeout: float = 0.5) -> dict:
    ip = assert_private(target)
    ports = sanitize_ports(ports or COMMON_PORTS)
    timeout = max(0.05, min(float(timeout), 2.0))
    started = time.monotonic()
    open_ports: list[dict] = []
    closed: list[int] = []
    for p in ports:
        check_time_budget(started, MAX_PORT_SCAN_SECONDS, "port scan")
        try:
            with socket.create_connection((ip, p), timeout=timeout) as s:
                banner = ""
                try:
                    s.settimeout(0.3)
                    banner = s.recv(128).decode("utf-8", errors="replace").strip()
                except OSError:
                    pass
                try:
                    service = socket.getservbyport(p)
                except OSError:
                    service = ""
                open_ports.append({"port": p, "service": service, "banner": banner})
        except OSError:
            closed.append(p)
    duration_ms = int((time.monotonic() - started) * 1000)
    return {
        "target": target,
        "ip": ip,
        "open": open_ports,
        "openPorts": open_ports,
        "closed": closed,
        "totalScanned": len(ports),
        "durationMs": duration_ms,
    }


# --- Traceroute --------------------------------------------------------------

def traceroute(target: str, max_hops: int = 20) -> dict:
    """UDP traceroute, local-only. Uses raw sockets where available, otherwise
    falls back to the system `tracert`/`traceroute` binary on the private IP."""
    ip = assert_private(target)
    max_hops = max(1, min(int(max_hops), 30))
    cmd = ["tracert", "-d", "-h", str(max_hops), ip] if sys.platform == "win32" else ["traceroute", "-n", "-m", str(max_hops), ip]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=30, check=False)
        return {"target": target, "ip": ip, "output": proc.stdout or proc.stderr}
    except FileNotFoundError:
        return {"target": target, "ip": ip, "output": "(binary traceroute/tracert absent)"}


# --- Pedagogical pcap generator ---------------------------------------------

def generate_pcap_demo() -> dict:
    """Build a synthetic 'packet capture' structure for display in the UI."""
    return {
        "packets": [
            {
                "no": 1, "time": 0.0,
                "src": "192.168.1.42", "dst": "192.168.1.1",
                "proto": "ARP", "info": "Who has 192.168.1.1? Tell 192.168.1.42",
                "layers": {"ethernet": "broadcast", "arp": "request"},
            },
            {
                "no": 2, "time": 0.002,
                "src": "192.168.1.1", "dst": "192.168.1.42",
                "proto": "ARP", "info": "192.168.1.1 is at aa:bb:cc:dd:ee:ff",
                "layers": {"ethernet": "unicast", "arp": "reply"},
            },
            {
                "no": 3, "time": 0.15,
                "src": "192.168.1.42", "dst": "1.1.1.1",
                "proto": "DNS", "info": "Standard query A example.com",
                "layers": {"ethernet": "unicast", "ip": "udp", "udp": "53", "dns": "query"},
            },
            {
                "no": 4, "time": 0.19,
                "src": "1.1.1.1", "dst": "192.168.1.42",
                "proto": "DNS", "info": "Response A 93.184.216.34",
                "layers": {"ethernet": "unicast", "ip": "udp", "udp": "53", "dns": "response"},
            },
            {
                "no": 5, "time": 0.22,
                "src": "192.168.1.42", "dst": "93.184.216.34",
                "proto": "TCP", "info": "SYN → 443",
                "layers": {"ethernet": "unicast", "ip": "tcp", "tcp": "SYN"},
            },
            {
                "no": 6, "time": 0.31,
                "src": "93.184.216.34", "dst": "192.168.1.42",
                "proto": "TCP", "info": "SYN+ACK",
                "layers": {"ethernet": "unicast", "ip": "tcp", "tcp": "SYN+ACK"},
            },
            {
                "no": 7, "time": 0.32,
                "src": "192.168.1.42", "dst": "93.184.216.34",
                "proto": "TLS", "info": "Client Hello (TLS 1.3)",
                "layers": {"ethernet": "unicast", "ip": "tcp", "tls": "handshake"},
            },
        ],
    }


# --- CLI --------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_dns = sub.add_parser("dns")
    p_dns.add_argument("domain")

    p_tls = sub.add_parser("tls")
    p_tls.add_argument("host")
    p_tls.add_argument("--port", type=int, default=443)

    p_whois = sub.add_parser("whois")
    p_whois.add_argument("domain")

    p_http = sub.add_parser("http")
    p_http.add_argument("url")

    p_scan = sub.add_parser("scan")
    p_scan.add_argument("target")
    p_scan.add_argument("--ports", default="")

    p_tr = sub.add_parser("traceroute")
    p_tr.add_argument("target")

    sub.add_parser("pcap-demo")

    args = parser.parse_args()
    try:
        if args.cmd == "dns":
            out = dns_lookup(args.domain)
        elif args.cmd == "tls":
            out = tls_cert(args.host, args.port)
        elif args.cmd == "whois":
            out = whois_lookup(args.domain)
        elif args.cmd == "http":
            out = http_headers(args.url)
        elif args.cmd == "scan":
            ports = [int(p) for p in args.ports.split(",") if p.strip()] or None
            out = port_scan(args.target, ports)
        elif args.cmd == "traceroute":
            out = traceroute(args.target)
        elif args.cmd == "pcap-demo":
            out = generate_pcap_demo()
        else:
            raise SystemExit(2)
        print(json.dumps(out, default=str, ensure_ascii=False))
    except Exception as exc:  # noqa: BLE001 — surface any failure as JSON
        print(json.dumps({"error": str(exc), "type": type(exc).__name__}))
        raise SystemExit(1)


if __name__ == "__main__":
    main()
