"""Batch re-render existing aurora-hunyuan packs with the upgraded pipeline:
   1. aurora_rebake.py applies Reinhard color transfer from input.png to the
      GLB's baseColorTexture, producing pbr_<name>_proc_rebake.glb.
   2. aurora_animate.py re-renders hero / orbit / animated using the new HDRI
      world + lowered light energies, against the rebaked GLB.

Usage:
    python aurora_rerender.py [--packs pack1 pack2 ...] [--all-aurora] [--dry-run]

By default targets only packs we generated in this aurora-hunyuan session
(matched against PACK_ALLOWLIST). Use --all-aurora to walk every pbr_*_pack
under application/output/3d/ (will skip procedural packs whose GLB doesn't
have a baseColorTexture). Always rebuilds in-place, replacing hero.png,
orbit.mp4, animated.mp4 of each pack.
"""
from __future__ import annotations

import argparse
import json
import logging
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parent
AURORA = Path(r"C:\Users\Juan\Desktop\ia\AuroraIA-v2")
BLENDER = AURORA / "application" / "_blender" / "blender-4.2.12-windows-x64" / "blender.exe"
OUTPUT_ROOT = AURORA / "application" / "output" / "3d"

PACK_ALLOWLIST = {
    "pbr_vintage_leather_armchair_pack",
    "pbr_steampunk_clockwork_dragon_pack",
    "pbr_crystal_lantern_fog_pack",
    "pbr_wizard_luminous_staff_pack",
    "pbr_anglerfish_bioluminescent_pack",
    "pbr_cyberpunk_hover_bike_pack",
    "pbr_samurai_golden_sunset_pack",
    "pbr_jungle_temple_ruins_pack",
    "pbr_hummingbird_glowing_flower_pack",
    "pbr_vintage_pocket_watch_pack",
    "pbr_treasure_chest_gems_pack",
}

log = logging.getLogger("rerender")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")


def run_rebake(pack: Path, python_exe: Path) -> bool:
    rebake_script = REPO / "aurora_rebake.py"
    cmd = [str(python_exe), str(rebake_script), str(pack)]
    log.info(f"[rebake] {pack.name}")
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        if res.returncode != 0:
            log.error(f"  rebake failed rc={res.returncode}: {res.stderr.strip()[-500:]}")
            return False
        return True
    except subprocess.TimeoutExpired:
        log.error("  rebake timeout")
        return False


def run_animate(pack: Path) -> bool:
    glb_in = pack / next((p.name for p in pack.glob("pbr_*_proc_rebake.glb")), "")
    if not glb_in.exists():
        glb_orig = next(iter(pack.glob("pbr_*_proc.glb")), None)
        if glb_orig is None:
            log.error(f"  no GLB found in {pack}")
            return False
        glb_in = glb_orig
    profile = pack / "profile.json"
    if not profile.exists():
        log.error(f"  no profile.json in {pack}")
        return False
    cmd = [str(BLENDER), "--background", "--python", str(REPO / "aurora_animate.py"),
            "--", str(glb_in), str(profile), str(pack)]
    log.info(f"[animate] {pack.name} <- {glb_in.name}")
    try:
        t0 = time.time()
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=1800)
        elapsed = time.time() - t0
        if res.returncode != 0:
            log.error(f"  animate failed rc={res.returncode} after {elapsed:.0f}s: {res.stderr[-500:]}")
            return False
        log.info(f"  animate done in {elapsed:.0f}s")
        return True
    except subprocess.TimeoutExpired:
        log.error("  animate timeout 30min")
        return False


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--packs", nargs="+", help="explicit pack names (default: PACK_ALLOWLIST)")
    ap.add_argument("--all-aurora", action="store_true", help="walk all pbr_*_pack")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--skip-rebake", action="store_true", help="only re-render, skip color rebake")
    ap.add_argument("--python", default=str(REPO / "venv" / "Scripts" / "python.exe"))
    args = ap.parse_args()

    if args.packs:
        targets = [OUTPUT_ROOT / p for p in args.packs]
    elif args.all_aurora:
        targets = [p for p in OUTPUT_ROOT.iterdir() if p.is_dir() and p.name.startswith("pbr_") and p.name.endswith("_pack")]
    else:
        targets = [OUTPUT_ROOT / n for n in PACK_ALLOWLIST if (OUTPUT_ROOT / n).exists()]

    log.info(f"target {len(targets)} pack(s)")
    if args.dry_run:
        for p in targets:
            log.info(f"  would process {p.name}")
        return 0

    successes: list[str] = []
    failures: list[str] = []
    for pack in targets:
        if not pack.exists():
            log.warning(f"skip missing {pack.name}")
            continue
        log.info(f"=== {pack.name} ===")
        if not args.skip_rebake:
            if not (pack / "input.png").exists():
                log.warning(f"  no input.png, skipping rebake")
            else:
                run_rebake(pack, Path(args.python))
        if run_animate(pack):
            successes.append(pack.name)
        else:
            failures.append(pack.name)
    log.info(f"=== done: {len(successes)} ok, {len(failures)} failed ===")
    if failures:
        log.warning(f"failed: {failures}")
    return 0 if not failures else 1


if __name__ == "__main__":
    sys.exit(main())
