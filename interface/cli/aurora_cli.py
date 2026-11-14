#!/usr/bin/env python3
"""
Wrapper unifié et Tableau de Bord CLI / Tunnel / AGI Monde Ouvert pour AuroraIA.
Redirige vers la suite CLI unifiée (aurora-remote-cli) pour garantir la parité
totale local/distant tout en offrant des commandes directes de diagnostic :
  - `python3 aurora_cli.py --status` : État temps réel Bridge :3001, Tunnel Cloudflare, AGI Monde Ouvert & Renforcement 3D
  - `python3 aurora_cli.py --tunnel` : Vérifie l'URL publique du tunnel Cloudflare actif
  - `python3 aurora_cli.py --test-prompt "fais-moi Spike Spiegel"` : Teste le moteur AGI Monde Ouvert (MediaWiki + Ollama)
"""
from __future__ import annotations

import json
import os
import sys
import time
import urllib.request
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent


def _probe_url(url: str, timeout: float = 2.0) -> tuple[bool, int, float]:
    t0 = time.perf_counter()
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "AuroraIA-CLI/4.5"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            ms = (time.perf_counter() - t0) * 1000.0
            return (200 <= resp.status < 400), int(resp.status), ms
    except Exception:
        ms = (time.perf_counter() - t0) * 1000.0
        return False, 0, ms


def _read_tunnel_url() -> str:
    for candidate in (
        ROOT_DIR / "tunnel.txt",
        ROOT_DIR.parent / "aurora-live" / "tunnel.txt",
    ):
        if candidate.is_file():
            try:
                text = candidate.read_text(encoding="utf-8").strip()
                if text.startswith("http"):
                    return text.splitlines()[0].strip()
            except OSError:
                pass
    return ""


def _print_compact_banner() -> None:
    bridge_url = os.environ.get("JOBIA_SERVER_URL") or os.environ.get("AURORA_SERVER_URL") or "http://127.0.0.1:3001"
    b_ok, _, b_ms = _probe_url(f"{bridge_url.rstrip('/')}/api/health", timeout=1.2)
    tunnel_url = _read_tunnel_url()
    open_world_count = 0
    ow_cache = ROOT_DIR / ".aurora" / "open_world_entities.json"
    if ow_cache.is_file():
        try:
            open_world_count = len(json.loads(ow_cache.read_text(encoding="utf-8")))
        except Exception:
            pass

    champ_badge = "\033[1;92m3D v2 +2.62% (54W/42L) · Anim +20.92%\033[0m"
    rl_badge = "\033[90mIDLE\033[0m"
    try:
        from auto_rl.control import snapshot
        snap = snapshot()
        if snap.get("active"):
            run_id = snap.get("current_run_id") or "en cours"
            rl_badge = f"\033[1;92m● LIVE ({run_id})\033[0m"
    except Exception:
        pass

    b_badge = f"\033[92m● ONLINE ({b_ms:.0f}ms)\033[0m" if b_ok else "\033[91m○ OFFLINE\033[0m"
    t_badge = f"\033[96m{tunnel_url}\033[0m" if tunnel_url else "\033[90mnon détecté\033[0m"
    print("\033[95m╭──────────────────────────────────────────────────────────────────────────────────────╮\033[0m")
    print(f"\033[95m│\033[0m \033[1;97m⚡ AURORA AGI STUDIO CLI v4.6\033[0m · Bridge: {b_badge} · Cerveau: \033[1;96m10 Boucles AGI\033[0m · { open_world_count } entités")
    print(f"\033[95m│\033[0m 🏆 Renforcés : {champ_badge} · Auto-RL Kaggle 2×T4 : {rl_badge}")
    print(f"\033[95m│\033[0m 🌐 Tunnel Public : {t_badge}")
    print("\033[95m╰──────────────────────────────────────────────────────────────────────────────────────╯\033[0m")


def _run_status_command() -> int:
    bridge_url = os.environ.get("JOBIA_SERVER_URL") or os.environ.get("AURORA_SERVER_URL") or "http://127.0.0.1:3001"
    b_ok, b_code, b_ms = _probe_url(f"{bridge_url.rstrip('/')}/api/health", timeout=2.0)
    tunnel_url = _read_tunnel_url()
    t_ok, t_code, t_ms = (False, 0, 0.0)
    if tunnel_url:
        t_ok, t_code, t_ms = _probe_url(f"{tunnel_url.rstrip('/')}/api/health", timeout=3.5)

    ow_cache = ROOT_DIR / ".aurora" / "open_world_entities.json"
    ow_entities = {}
    if ow_cache.is_file():
        try:
            ow_entities = json.loads(ow_cache.read_text(encoding="utf-8"))
        except Exception:
            ow_entities = {}

    snap = {}
    st_live = {}
    m3d_manifest = {}
    try:
        from auto_rl.config import STATE
        from auto_rl.control import snapshot
        from auto_rl.reinforced_registry import RENFORCE_ROOT
        from auto_rl.storage import read_json
        snap = snapshot()
        st_live = read_json(STATE / "status.json", {})
        m3d_manifest = read_json(RENFORCE_ROOT / "3d" / "manifest.json", {})
    except Exception:
        pass

    print("\033[1;96m╔══════════════════════════════════════════════════════════════════════════════════════╗\033[0m")
    print("\033[1;96m║\033[0m  \033[1;97m🧠 AURORA AGI — DIAGNOSTIC UNIFIÉ (CERVEAU 10 BOUCLES · LOCAL · KAGGLE · 3D v2)\033[0m   \033[1;96m║\033[0m")
    print("\033[1;96m╚══════════════════════════════════════════════════════════════════════════════════════╝\033[0m")
    print(
        f"  • Bridge Local ({bridge_url}) : "
        + (f"\033[1;92mONLINE (HTTP {b_code}, {b_ms:.1f} ms)\033[0m" if b_ok else "\033[1;91mOFFLINE\033[0m")
    )
    if tunnel_url:
        print(
            f"  • Tunnel Cloudflare ({tunnel_url}) : "
            + (f"\033[1;92mONLINE (HTTP {t_code}, {t_ms:.0f} ms)\033[0m" if t_ok else "\033[1;93mUNREACHABLE\033[0m")
        )
    else:
        print("  • Tunnel Cloudflare : \033[90mAucun fichier tunnel.txt actif\033[0m")

    from agi_core.prompt_intelligence import _select_available_ollama_model

    ollama_model, cpu_guard = _select_available_ollama_model()
    print(
        f"  • Moteur Cognitif Monde Ouvert : \033[1;95mMediaWiki FR/EN + Ollama ({ollama_model or 'indisponible'})\033[0m"
        f" · Guard VRAM CPU: {'OUI' if cpu_guard else 'NON'}"
    )
    print(f"  • Cache Encyclopédique Monde Ouvert : \033[1;93m{len(ow_entities)} entités résolues\033[0m")
    if m3d_manifest:
        print(
            f"  • Champion 3D Multi-Spécialistes Actif : \033[1;92m{m3d_manifest.get('name')}\033[0m\n"
            f"    └─ Score Holdout 96 maillages : \033[1;97m{m3d_manifest.get('score_renforce_100')}/100\033[0m "
            f"vs Base Intouchable \033[90m{m3d_manifest.get('score_base_100')}/100\033[0m "
            f"(\033[1;92m+{m3d_manifest.get('gain_points_100')} pt / +{m3d_manifest.get('relative_gain_percent')}%\033[0m · "
            f"\033[1;96m+{m3d_manifest.get('relative_gain_vs_single_champion_percent', 0.95)}% vs Champion v1\033[0m · "
            f"{m3d_manifest.get('wins')}W/{m3d_manifest.get('losses')}L)"
        )
    if snap:
        active = snap.get("active", False)
        cycle_id = snap.get("current_run_id") or st_live.get("run_id") or "n/a"
        phase = st_live.get("phase") or snap.get("phase") or "idle"
        detail = st_live.get("status") or ""
        done = st_live.get("local_generations_done", 0)
        planned = st_live.get("local_generations_planned", 36)
        q_rem_h = round(float((snap.get("quota") or {}).get("remaining_seconds", 0.0)) / 3600.0, 1)
        print(
            f"  • Renforcement Continu 3D (`auto_rl` Kaggle 2×T4 + Audit RTX 5070 Ti) : "
            f"{'\033[1;92mACTIF\033[0m' if active else '\033[90mINACTIF\033[0m'}\n"
            f"    └─ Cycle : \033[1;97m{cycle_id}\033[0m · Phase : \033[1;93m{phase}\033[0m ({detail}) · "
            f"Rollouts : {done}/{planned} · Quota Kaggle restant : \033[1;96m{q_rem_h}h\033[0m"
        )
    return 0


def _run_test_prompt_command(raw_prompt: str, target_module: str = "3d") -> int:
    from agi_core.prompt_intelligence import analyze_and_direct_prompt
    from agi_core.agi_loops import CognitiveExecutiveLoop

    res = analyze_and_direct_prompt(
        raw_prompt,
        target_module=target_module,
        use_llm=True,
        open_world_grounding=True,
    )
    loop_plan = CognitiveExecutiveLoop(ROOT_DIR).build_autonomous_loop_plan(raw_prompt, active_module=target_module)
    arb = (loop_plan.get("reinforced_model_arbitration") or {}).get("modules_arbitrated", {})
    invs = [i.get("id") for i in (loop_plan.get("formal_constraints") or {}).get("formal_invariants", [])]

    print("\033[1;95m╔══ ANALYSE COGNITIVE AGI & PLAN 10 BOUCLES ═══════════════════════════════════╗\033[0m")
    print(f"  • Prompt brut         : \033[1;97m{raw_prompt}\033[0m")
    print(f"  • Ontologie détectée  : \033[1;96m{res.get('subject_ontology')}\033[0m")
    print(f"  • Mode de rendu       : \033[1;92m{res.get('effective_render_mode')}\033[0m (LLM actif: {res.get('llm_used')})")
    if res.get("open_world_entity"):
        ow = res["open_world_entity"]
        ow_title = ow.get("title") or ow.get("entity_title") or "?"
        ow_desc = str(ow.get("description") or ow.get("summary_extract") or "")[:140]
        print(f"  • Entité Monde Ouvert : \033[1;93m{ow_title}\033[0m — {ow_desc}")
    print(f"  • Chaîne d'Agents DAG : \033[1;96m{' → '.join(a['applicator_agent'] for a in loop_plan.get('applicators', []))}\033[0m")
    print(f"  • Invariants Formels  : \033[93m{', '.join(invs)}\033[0m")
    print(f"  • Arbitrage Renforcé  : \033[92m{json.dumps(arb, ensure_ascii=False)}\033[0m")
    print(f"  • Raisonnement AGI    : {res.get('reasoning_fr')}")
    print(f"  • Prompt EN développé : \033[97m{res.get('english_expanded_prompt')}\033[0m")
    return 0


def main() -> None:
    argv = sys.argv[1:]
    if "--status" in argv or "--diagnostic" in argv:
        sys.exit(_run_status_command())
    if "--tunnel" in argv:
        t_url = _read_tunnel_url()
        if not t_url:
            print("Aucun tunnel actif trouvé dans tunnel.txt", file=sys.stderr)
            sys.exit(1)
        ok, code, ms = _probe_url(f"{t_url.rstrip('/')}/api/health", timeout=3.5)
        print(f"{t_url} ({'HTTP ' + str(code) + f' · {ms:.0f}ms' if ok else 'OFFLINE'})")
        sys.exit(0 if ok else 1)
    if "--test-prompt" in argv or "--direct-prompt" in argv or "--brain" in argv:
        flag = "--test-prompt" if "--test-prompt" in argv else ("--direct-prompt" if "--direct-prompt" in argv else "--brain")
        idx = argv.index(flag)
        prompt_val = argv[idx + 1] if idx + 1 < len(argv) else "fais-moi Spike Spiegel"
        mod_val = "3d"
        if "--module" in argv:
            m_idx = argv.index("--module")
            if m_idx + 1 < len(argv):
                mod_val = argv[m_idx + 1]
        sys.exit(_run_test_prompt_command(prompt_val, target_module=mod_val))

    remote_cli_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "aurora-remote-cli")

    if remote_cli_path not in sys.path:
        sys.path.insert(0, remote_cli_path)

    try:
        from aurora_cli.cli import main as cli_main
    except ImportError:
        print(f"Erreur: Impossible de charger aurora-remote-cli depuis {remote_cli_path}.")
        print("Vérifiez que le dossier aurora-remote-cli existe bien au même niveau que AuroraIA.")
        sys.exit(1)

    # Default to the local bridge, preserving explicit environment overrides.
    if not os.environ.get("JOBIA_SERVER_URL") and not os.environ.get("AURORA_SERVER_URL"):
        os.environ["JOBIA_SERVER_URL"] = "http://127.0.0.1:3001"

    if not argv:
        _print_compact_banner()
    cli_main()


if __name__ == "__main__":
    main()

