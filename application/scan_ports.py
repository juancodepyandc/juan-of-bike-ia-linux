#!/usr/bin/env python3
import socket
import sys

def scan_ports(target, timeout=1.0):
    open_ports = []
    common_ports = [21, 22, 23, 25, 53, 80, 110, 143, 443, 465, 587, 993, 995, 3306, 5432, 8080]
    
    try:
        ip = socket.gethostbyname(target)
    except Exception as e:
        return f"Erreur résolution DNS: {e}"

    print(f"Scan de {target} ({ip})...")
    for port in common_ports:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        result = sock.connect_ex((ip, port))
        if result == 0:
            open_ports.append(port)
        sock.close()
    
    return ip, open_ports

if __name__ == "__main__":
    target = "site-rep.vercel.app"
    import os
    output_dir = os.path.expanduser("~/Desktop/test_ia")
    os.makedirs(output_dir, exist_ok=True)

    result = scan_ports(target)
    if isinstance(result, str):
        report = f"Scan échoué: {result}\n"
    else:
        ip, open_ports = result
        ports_str = ', '.join(map(str, open_ports)) or "aucun"
        report = f"""Rapport de scan des ports - site-rep.vercel.app
================================================
Target IP: {ip}
Ports ouverts: {ports_str}
Date: $(date)
"""

    with open(os.path.join(output_dir, "rapport_scan_ports.txt"), "w") as f:
        f.write(report.replace("$(date)", __import__('datetime').datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
    
    print(report)
