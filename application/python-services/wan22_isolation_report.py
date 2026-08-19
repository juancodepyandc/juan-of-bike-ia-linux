"""Lit application/output/video/wan22_isolation/manifest.json et sort une
synthèse chiffrée par campagne.

Usage :
    /home/juan/AuroraIA/application/.venv/bin/python \\
        /home/juan/AuroraIA/application/python-services/wan22_isolation_report.py
"""
from __future__ import annotations

import json
from pathlib import Path
from collections import defaultdict

MANIFEST = Path("/home/juan/AuroraIA/application/output/video/wan22_isolation/manifest.json")


def _fmt(x, digits=4):
    if x is None:
        return "N/A"
    if isinstance(x, float):
        return f"{x:.{digits}f}"
    return str(x)


def main():
    if not MANIFEST.exists():
        print(f"NO MANIFEST at {MANIFEST}")
        return
    entries = json.loads(MANIFEST.read_text(encoding="utf-8"))
    if not entries:
        print("empty manifest")
        return

    print(f"# Rapport isolation Wan2.2 TI2V-5B — {len(entries)} runs\n")

    # Group by campaign
    by_camp = defaultdict(list)
    for e in entries:
        by_camp[e.get("campaign", "?")].append(e)

    for camp, runs in by_camp.items():
        if camp == "smoke":
            continue  # skip the harness check
        print(f"\n## Campagne : {camp}  ({len(runs)} runs)\n")
        header = ("run_id", "swept", "elapsed_s", "vram_GB",
                  "laplacian_var", "motion_amp", "seam_delta", "size_kB", "ffprobe_dim")
        print("| " + " | ".join(header) + " |")
        print("|" + "|".join(["-" * (len(h) + 2) for h in header]) + "|")
        for e in sorted(runs, key=lambda x: (str(x.get("swept_value") or ""))):
            swept = f"{e.get('swept_key')}={e.get('swept_value')}"
            ff = e.get("ffprobe") or {}
            dim = f"{ff.get('width')}x{ff.get('height')}@{_fmt(ff.get('fps'),1)}fps × {ff.get('nb_frames')}f"
            row = (
                e.get("run_id", "")[:24],
                swept[:30],
                _fmt(e.get("elapsed_seconds"), 1),
                _fmt(e.get("peak_vram_bytes", 0) / 1024**3, 2),
                _fmt((e.get("metrics") or {}).get("middle_frame_laplacian_var"), 2),
                _fmt((e.get("metrics") or {}).get("motion_amplitude"), 5),
                _fmt((e.get("metrics") or {}).get("shot_seam_delta"), 5),
                _fmt(ff.get("file_size", 0) / 1024, 1),
                dim,
            )
            print("| " + " | ".join(str(c) for c in row) + " |")

    # Verdict block
    print("\n\n## Analyse synthétique\n")

    # Steps effect
    step_runs = sorted([e for e in entries if e.get("campaign") == "steps"],
                       key=lambda x: x.get("swept_value") or 0)
    baseline_runs = [e for e in entries if e.get("campaign") == "baseline"]
    if step_runs and baseline_runs:
        b = baseline_runs[0]
        steps_all = [b] + step_runs
        # Insert baseline as 30-step reference
        print("### Effet de num_inference_steps (baseline=30)")
        print("| steps | elapsed | laplacian | motion_amp |")
        print("|-------|---------|-----------|------------|")
        for r in sorted(steps_all, key=lambda x: x.get("params", {}).get("num_inference_steps", 0)):
            print(f"| {r.get('params',{}).get('num_inference_steps')} "
                  f"| {_fmt(r.get('elapsed_seconds'),1)}s "
                  f"| {_fmt((r.get('metrics') or {}).get('middle_frame_laplacian_var'),2)} "
                  f"| {_fmt((r.get('metrics') or {}).get('motion_amplitude'),5)} |")
        print()

    # Guidance effect
    gu = sorted([e for e in entries if e.get("campaign") == "guidance"],
                key=lambda x: x.get("swept_value") or 0)
    if gu and baseline_runs:
        print("### Effet de guidance_scale (baseline=4.5)")
        print("| guidance | elapsed | laplacian | motion_amp |")
        print("|----------|---------|-----------|------------|")
        for r in sorted([baseline_runs[0]] + gu,
                        key=lambda x: x.get("params", {}).get("guidance_scale", 0)):
            print(f"| {r.get('params',{}).get('guidance_scale')} "
                  f"| {_fmt(r.get('elapsed_seconds'),1)}s "
                  f"| {_fmt((r.get('metrics') or {}).get('middle_frame_laplacian_var'),2)} "
                  f"| {_fmt((r.get('metrics') or {}).get('motion_amplitude'),5)} |")
        print()

    # Seed variance
    se = sorted([e for e in entries if e.get("campaign") == "seed"],
                key=lambda x: x.get("swept_value") or 0)
    if se and baseline_runs:
        print("### Variance sur seed (baseline seed=1031)")
        print("| seed | elapsed | laplacian | motion_amp |")
        print("|------|---------|-----------|------------|")
        for r in sorted([baseline_runs[0]] + se,
                        key=lambda x: x.get("params", {}).get("seed", 0)):
            print(f"| {r.get('params',{}).get('seed')} "
                  f"| {_fmt(r.get('elapsed_seconds'),1)}s "
                  f"| {_fmt((r.get('metrics') or {}).get('middle_frame_laplacian_var'),2)} "
                  f"| {_fmt((r.get('metrics') or {}).get('motion_amplitude'),5)} |")

        # variance across runs
        laps = [ (r.get('metrics') or {}).get('middle_frame_laplacian_var')
                 for r in [baseline_runs[0]] + se
                 if (r.get('metrics') or {}).get('middle_frame_laplacian_var') is not None]
        amps = [ (r.get('metrics') or {}).get('motion_amplitude')
                 for r in [baseline_runs[0]] + se
                 if (r.get('metrics') or {}).get('motion_amplitude') is not None]
        if laps:
            avg_l = sum(laps)/len(laps); rng_l = max(laps)-min(laps)
            print(f"\n**Variance laplacian sur {len(laps)} seeds** : moyenne {avg_l:.1f}, range {rng_l:.1f} → coef {rng_l/max(1,avg_l)*100:.1f}%")
        if amps:
            avg_a = sum(amps)/len(amps); rng_a = max(amps)-min(amps)
            print(f"**Variance motion_amp sur {len(amps)} seeds** : moyenne {avg_a:.5f}, range {rng_a:.5f} → coef {rng_a/max(1e-9,avg_a)*100:.1f}%")

    # Continuity
    co = [e for e in entries if e.get("campaign") == "continuity"]
    if co:
        print("\n### Continuité inter-plans")
        for r in co:
            seam = (r.get("metrics") or {}).get("shot_seam_delta")
            print(f"- {r.get('swept_value')} : seam_delta = {_fmt(seam,5)}"
                  f" | motion_amp = {_fmt((r.get('metrics') or {}).get('motion_amplitude'),5)}")
        # Compare anchored vs unanchored
        anchored = next((r for r in co if "anchored_on_A" in str(r.get("swept_value") or "")), None)
        unanch = next((r for r in co if "unanchored" in str(r.get("swept_value") or "")), None)
        if anchored and unanch:
            a_seam = (anchored.get("metrics") or {}).get("shot_seam_delta")
            u_seam = (unanch.get("metrics") or {}).get("shot_seam_delta")
            if a_seam is not None and u_seam is not None:
                delta_pct = (u_seam - a_seam) / max(1e-9, u_seam) * 100
                verdict = ("l'ancrage réduit la couture" if a_seam < u_seam
                           else "l'ancrage N'A PAS réduit la couture (préoccupant)")
                print(f"\n**Verdict continuité** : ancré={_fmt(a_seam,5)}, "
                      f"non-ancré={_fmt(u_seam,5)} → {verdict} ({delta_pct:+.1f}% de réduction)")


if __name__ == "__main__":
    main()
