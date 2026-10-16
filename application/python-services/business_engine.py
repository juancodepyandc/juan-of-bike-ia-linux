#!/usr/bin/env python3
"""CLI & Agent Tool wrapper for Aurora Business Intelligence.

Allows any Aurora mission agent (`business-ceo`, `business-quant`, `business-risk-manager`, etc.)
to run Walk-Forward simulations, 13-step multi-agent council deliberations, viability analyses,
and Kaggle/Colab quota inspections via `run_tool` or `run_command`.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from business_intelligence import (  # noqa: E402
    evaluate_unit_economics_and_viability,
    fetch_market_quotes,
    get_business_store,
    inspect_kaggle_colab_compute_quotas,
    run_13_step_council_deliberation,
    run_advanced_policy_training,
    run_monte_carlo_and_walk_forward,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Aurora Business Intelligence Engine (Lab & Live)")
    parser.add_argument(
        "--mode",
        choices=["deliberate", "simulate", "viability", "train", "quotes", "quotas"],
        default="deliberate",
    )
    parser.add_argument("--capital", type=float, default=10_000.0, help="Capital virtuel ou opérationnel en EUR")
    parser.add_argument("--strategy", type=str, default="hybrid_venture_and_etf")
    parser.add_argument("--horizon", type=int, default=24)
    parser.add_argument("--episodes", type=int, default=40)
    parser.add_argument("--objective", type=str, default="Maximiser la création de valeur ajustée au risque et la survie économique.")
    parser.add_argument("--payload-json", type=str, default="{}")
    args = parser.parse_args()

    store = get_business_store(ROOT)

    if args.mode == "quotes":
        out = fetch_market_quotes(allow_network=True)
    elif args.mode == "quotas":
        out = inspect_kaggle_colab_compute_quotas(ROOT)
    elif args.mode == "simulate":
        out = run_monte_carlo_and_walk_forward(
            capital_eur=args.capital,
            strategy_id=args.strategy,
            horizon_months=args.horizon,
            num_simulations=40,
        )
        store.record_simulation(out)
    elif args.mode == "train":
        out = run_advanced_policy_training(
            store=store,
            capital_eur=args.capital,
            episodes=args.episodes,
            horizon_months=args.horizon,
        )
    elif args.mode == "viability":
        payload = json.loads(args.payload_json or "{}")
        payload.setdefault("capital_eur", args.capital)
        out = evaluate_unit_economics_and_viability(payload)
    else:
        out = run_13_step_council_deliberation(
            capital_eur=args.capital,
            objective=args.objective,
            horizon_months=args.horizon,
        )
        store.record_decision(out, mode="AGENT_TOOL_DELIBERATION")

    print(json.dumps(out, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
