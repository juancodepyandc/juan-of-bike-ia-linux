#!/usr/bin/env python
"""Logger de stabilite : ecrit RAM/VRAM/temp/power GPU toutes les 2 s avec
flush immediat. But : si le PC BSOD pendant un test 3D, les dernieres lignes
du fichier montrent l'etat memoire JUSTE avant le crash (preuve reelle).

Usage: python mem_monitor.py <logfile> [intervalle_s]
"""
import subprocess
import sys
import time
from pathlib import Path

try:
    import psutil
except ImportError:
    psutil = None

logf = Path(sys.argv[1] if len(sys.argv) > 1 else "stability_monitor.log")
interval = float(sys.argv[2]) if len(sys.argv) > 2 else 2.0

QUERY = "memory.used,memory.total,utilization.gpu,temperature.gpu,power.draw"

with logf.open("a", buffering=1, encoding="utf-8") as f:
    f.write(f"# monitor start {time.strftime('%Y-%m-%d %H:%M:%S')} interval={interval}s\n")
    f.flush()
    peak_ram = 0.0
    peak_vram = 0.0
    while True:
        ts = time.strftime("%H:%M:%S")
        try:
            out = subprocess.run(
                ["nvidia-smi", f"--query-gpu={QUERY}",
                 "--format=csv,noheader,nounits"],
                capture_output=True, text=True, timeout=5,
            ).stdout.strip().replace("\n", " | ")
        except Exception as exc:  # noqa: BLE001
            out = f"gpu_err:{exc}"
        if psutil:
            vm = psutil.virtual_memory()
            ram_used = vm.used / 1e9
            ram_free = vm.available / 1e9
            peak_ram = max(peak_ram, ram_used)
            ram = f"ram_used={ram_used:.1f}G ram_free={ram_free:.1f}G pct={vm.percent} peak_ram={peak_ram:.1f}G"
        else:
            ram = "ram=?(no psutil)"
        # parse vram used for peak
        try:
            vram_used = float(out.split(",")[0])
            peak_vram = max(peak_vram, vram_used)
            ram += f" peak_vram={peak_vram:.0f}MiB"
        except Exception:  # noqa: BLE001
            pass
        f.write(f"{ts} gpu[{out}] {ram}\n")
        f.flush()
        time.sleep(interval)
