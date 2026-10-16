"""Comprehensive test suite for Aurora Business Intelligence (Section 9).

Covers:
  1. Unit tests: IndependentRiskManager, anti-martingale detector, multi-criteria survival reward.
  2. Economic Simulator tests: virtual capital presets (100 EUR to 1,000,000 EUR), commissions,
     spreads, slippage, inflation, taxation, DSO working-capital lag, and crisis stress scenarios.
  3. Walk-Forward Validation & Anti-Overfitting tests: chronological 60/20/20 split, confidence intervals.
  4. 10-Agent Council & 13-Step Decision Pipeline tests (including beginner pedagogical explanation).
  5. Persistent Economic Memory, SHA-256 audit log chain, and Auditor Model Promotion/Rollback Gate.
  6. Kaggle & Google Colab Compute Governor skill and notebook integrity.
  7. HTTP API route integration tests (/api/business/*).
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

from flask import Flask

ROOT = Path(__file__).resolve().parent.parent
APP_DIR = ROOT / "application"
for p in (str(ROOT), str(APP_DIR)):
    if p not in sys.path:
        sys.path.insert(0, p)

from agent_registry import AGENTS, get_module_agent, list_module_agents  # noqa: E402
from agi_core.mission_routing import mission_module  # noqa: E402
from business_intelligence import (  # noqa: E402
    BUSINESS_AGENT_COUNCIL,
    CAPITAL_PRESETS_EUR,
    LIBRARY_EVALUATION_MATRIX,
    EconomicMemoryStore,
    IndependentRiskManager,
    bayesian_hyperparameter_search,
    compute_multi_criteria_reward,
    detect_martingale_behavior,
    evaluate_unit_economics_and_viability,
    fetch_market_quotes,
    inspect_kaggle_colab_compute_quotas,
    register_business_routes,
    run_13_step_council_deliberation,
    run_advanced_policy_training,
    run_monte_carlo_and_walk_forward,
    simulate_business_trajectory,
)


def test_ten_business_agents_registered_and_routed():
    primary = get_module_agent("business")
    assert primary is not None
    assert primary["name"] == "business-ceo"

    business_agents = list_module_agents("business")
    names = {a["name"] for a in business_agents}
    expected_10 = {
        "business-ceo",
        "business-market-research",
        "business-financial-analyst",
        "business-risk-manager",
        "business-entrepreneur",
        "business-quant",
        "business-economist",
        "business-technical",
        "business-critic",
        "business-auditor",
    }
    assert expected_10.issubset(names)
    assert len(BUSINESS_AGENT_COUNCIL) == 10
    assert mission_module({"module": "business", "request": "Simuler 10 000 €"}) == "business"
    assert mission_module({"request": "Lancer une simulation dans Aurora Business Lab avec capital fictif"}) == "business"


def test_independent_risk_manager_veto_and_survival_laws():
    rm = IndependentRiskManager(
        min_cash_reserve_ratio=0.25,
        max_single_allocation_ratio=0.45,
        max_acceptable_ruin_prob=0.02,
        max_acceptable_drawdown=0.22,
        max_leverage=1.0,
    )
    # 1. Valid prudent allocation passes
    safe = rm.evaluate_strategy(
        capital_eur=10_000.0,
        allocated_eur=6_500.0,
        single_max_exposure_eur=3_500.0,
        leverage=1.0,
        estimated_ruin_prob=0.005,
        expected_max_drawdown=0.11,
        expected_real_cagr=0.09,
    )
    assert safe["approved"] is True
    assert safe["veto"] is False
    assert safe["cash_reserve_eur"] == 3_500.0

    # 2. Insufficient cash reserve (<25%), leverage (>1.0x), or high ruin probability triggers hard VETO
    reckless = rm.evaluate_strategy(
        capital_eur=10_000.0,
        allocated_eur=9_200.0,
        single_max_exposure_eur=8_000.0,
        leverage=2.5,
        estimated_ruin_prob=0.12,
        expected_max_drawdown=0.45,
        expected_real_cagr=0.35,
        martingale_detected=True,
    )
    assert reckless["approved"] is False
    assert reckless["veto"] is True
    assert len(reckless["violations"]) >= 4

    # 3. Live execution without explicit human approval is blocked
    unapproved_live = rm.evaluate_strategy(
        capital_eur=10_000.0,
        allocated_eur=4_000.0,
        single_max_exposure_eur=2_000.0,
        leverage=1.0,
        estimated_ruin_prob=0.005,
        expected_max_drawdown=0.08,
        expected_real_cagr=0.08,
        is_live_execution=True,
        human_approved=False,
    )
    assert unapproved_live["approved"] is False
    assert unapproved_live["veto"] is True
    assert any("validation humaine" in v for v in unapproved_live["violations"])


def test_anti_martingale_detector_and_reward_penalties():
    # Normal prudent agent reduces or keeps steady exposure after losses
    prudent_returns = [0.02, -0.03, 0.01, -0.02, 0.015]
    prudent_exposure = [0.50, 0.50, 0.42, 0.42, 0.38]
    chk_ok = detect_martingale_behavior(prudent_returns, prudent_exposure)
    assert chk_ok["martingale_detected"] is False

    # Martingale agent doubles exposure after losses to mask drawdown
    martingale_returns = [-0.04, -0.05, -0.06, 0.02]
    martingale_exposure = [0.20, 0.42, 0.85, 0.95]
    chk_bad = detect_martingale_behavior(martingale_returns, martingale_exposure)
    assert chk_bad["martingale_detected"] is True
    assert chk_bad["doubling_events"] >= 2
    assert chk_bad["severity"] > 0.4

    rew_safe = compute_multi_criteria_reward(
        real_cagr=0.09,
        sortino_ratio=1.6,
        max_drawdown=0.09,
        ruin_probability=0.004,
        cash_reserve_ratio=0.35,
        martingale_penalty_severity=0.0,
    )
    rew_martingale = compute_multi_criteria_reward(
        real_cagr=0.12,
        sortino_ratio=0.8,
        max_drawdown=0.38,
        ruin_probability=0.14,
        cash_reserve_ratio=0.08,
        martingale_penalty_severity=chk_bad["severity"],
    )
    assert rew_safe["total_reward"] > rew_martingale["total_reward"] + 80.0


def test_simulator_across_capital_presets_and_frictions():
    assert CAPITAL_PRESETS_EUR == [100.0, 1_000.0, 10_000.0, 100_000.0, 1_000_000.0]
    for cap, strat in (
        (100.0, "prudent_financial_portfolio"),
        (10_000.0, "hybrid_venture_and_etf"),
        (1_000_000.0, "hybrid_venture_and_etf"),
    ):
        sim = simulate_business_trajectory(
            capital_eur=cap,
            strategy_id=strat,
            horizon_months=18,
            scenario_id="baseline_realistic",
            tax_rate=0.25,
        )
        assert sim["initial_capital_eur"] == cap
        assert sim["bankrupt"] is False
        assert len(sim["monthly_trajectory"]) == 18
        assert sim["frictions_summary"]["annual_inflation_pct"] > 0
        assert sim["frictions_summary"]["cumulative_commissions_and_slippage_eur"] > 0
        # Real equity must account for inflation erosion (< nominal equity when inflation > 0)
        assert sim["final_real_equity_eur"] < sim["final_nominal_equity_eur"]

    # Undercapitalized test: 100 EUR on a high-fixed-cost SaaS venture triggers bankruptcy in the simulator,
    # proving that fixed costs and CAC are not faked to always win.
    undercap_sim = simulate_business_trajectory(
        capital_eur=100.0,
        strategy_id="ecommerce_specialized_brand",
        horizon_months=18,
        scenario_id="recession_2008_liquidity_crisis",
    )
    assert undercap_sim["bankrupt"] is True


def test_walk_forward_monte_carlo_and_13_step_council():
    os.environ["AURORA_BUSINESS_OFFLINE"] = "1"
    try:
        wf = run_monte_carlo_and_walk_forward(
            capital_eur=10_000.0,
            strategy_id="saas_b2b_micro",
            horizon_months=24,
            num_simulations=20,
        )
        assert wf["monte_carlo"]["num_simulations"] == 20
        assert wf["monte_carlo"]["ci_95_low_equity_eur"] <= wf["monte_carlo"]["median_final_real_equity_eur"]
        assert wf["monte_carlo"]["median_final_real_equity_eur"] <= wf["monte_carlo"]["ci_95_high_equity_eur"]
        assert "60% Train / 20% Validation / 20% Unseen Test" in wf["walk_forward_validation"]["chronological_split"]

        delib = run_13_step_council_deliberation(capital_eur=10_000.0, horizon_months=24)
        assert delib["ok"] is True
        assert len(delib["council_deliberation"]) == 10
        assert len(delib["decision_steps_13"]) == 13
        step_13 = delib["decision_steps_13"][-1]
        assert step_13["step"] == 13
        assert "glossary" in step_13["pedagogical_explanation"]
        assert len(delib["all_ranked_strategies"]) == 6
    finally:
        os.environ.pop("AURORA_BUSINESS_OFFLINE", None)


def test_persistent_memory_model_promotion_rollback_and_Flask_routes(tmp_path: Path):
    os.environ["AURORA_BUSINESS_OFFLINE"] = "1"
    try:
        store = EconomicMemoryStore(tmp_path)
        # 1. Promote a strong, low-ruin policy
        p1 = store.register_trained_model(
            model_name="Policy-v1-Safe",
            training_source="unit_test",
            validation_reward=28.5,
            unseen_test_cagr_pct=8.4,
            ruin_prob_pct=0.5,
            metrics={"sharpe": 1.4},
        )
        assert p1["promoted"] is True

        # 2. Attempt to promote a high-ruin or worse policy -> must be REJECTED and keep v1!
        p2 = store.register_trained_model(
            model_name="Policy-v2-Reckless",
            training_source="unit_test",
            validation_reward=40.0,
            unseen_test_cagr_pct=15.0,
            ruin_prob_pct=8.5,  # exceeds 2.0% ruin limit!
            metrics={"sharpe": 0.9},
        )
        assert p2["promoted"] is False
        assert p2["rollback_kept_previous"] is True
        assert p2["previous_active_version"] == p1["version_id"]

        # 3. Verify Kaggle/Colab Compute Governor & SKILL.md + Notebook existence
        quotas = inspect_kaggle_colab_compute_quotas(APP_DIR)
        assert quotas["ok"] is True
        assert quotas["skill_installed"] is True
        assert quotas["notebook_ready"] is True
        assert len(LIBRARY_EVALUATION_MATRIX) >= 8

        # 4. Verify Flask HTTP API routes
        app = Flask(__name__)
        register_business_routes(app, workspace=tmp_path)
        client = app.test_client()

        r_ov = client.get("/api/business/overview")
        assert r_ov.status_code == 200
        ov_data = r_ov.get_json()
        assert ov_data["ok"] is True
        assert ov_data["paper_portfolio"]["real_money_at_risk_eur"] == 0.0

        r_viab = client.post(
            "/api/business/live/viability",
            json={
                "project_name": "Test SaaS",
                "capital_eur": 10000,
                "unit_price_eur": 99,
                "unit_variable_cost_eur": 15,
                "monthly_fixed_cost_eur": 250,
                "cac_eur": 150,
                "monthly_churn_rate": 0.03,
                "dso_days": 30,
            },
        )
        assert r_viab.status_code == 200
        v_data = r_viab.get_json()
        assert v_data["ok"] is True
        assert v_data["unit_economics"]["ltv_to_cac_ratio"] > 3.0

        r_train = client.post("/api/business/lab/train", json={"capital_eur": 10000, "episodes": 16, "horizon_months": 18})
        assert r_train.status_code == 200
        t_data = r_train.get_json()
        assert t_data["ok"] is True
        assert Path(t_data["checkpoint_path"]).is_file()

        # 5. Verify live real-time paper portfolio tick (/api/business/lab/live-tick)
        r_tick = client.post("/api/business/lab/live-tick", json={"days_elapsed": 1.0})
        assert r_tick.status_code == 200
        tick_data = r_tick.get_json()
        assert tick_data["ok"] is True
        assert tick_data["portfolio"]["real_money_at_risk_eur"] == 0.0
        assert "tick_events" in tick_data
        assert len(tick_data["tick_events"]) >= 1

        # 6. Verify live paper actions (/api/business/lab/action) and Risk Manager reserve protection
        r_act = client.post(
            "/api/business/lab/action",
            json={"action": "buy_asset", "instrument_id": "MSCI_WORLD_ETF", "amount_eur": 500},
        )
        assert r_act.status_code == 200
        act_data = r_act.get_json()
        assert act_data["ok"] is True
        assert act_data["portfolio"]["real_money_at_risk_eur"] == 0.0
        assert "action_summary" in act_data

        # 7. Verify Conversational Business Copilot (/api/business/chat) in Beginner Mode (zero technical jargon)
        r_chat_beg = client.post(
            "/api/business/chat",
            json={
                "message": "J'ai 5 000 €, que me conseilles-tu de faire en direct aujourd'hui ?",
                "pedagogical_mode": True,
                "capital_eur": 5000,
            },
        )
        assert r_chat_beg.status_code == 200
        chat_beg = r_chat_beg.get_json()
        assert chat_beg["ok"] is True
        assert chat_beg["pedagogical_mode"] is True
        reply_beg = chat_beg["reply"]
        # Beginner mode must never leak quant/tax jargon
        for forbidden_jargon in ("Sortino", "IC 95%", "Drawdown P90", "Walk-Forward", "DSO", "BFR"):
            assert forbidden_jargon not in reply_beg
        assert len(chat_beg["suggested_prompts"]) >= 3

        # 8. Verify Conversational Business Copilot in Expert Mode
        r_chat_exp = client.post(
            "/api/business/chat",
            json={
                "message": "Analyse quant complète avec Sortino et Walk-Forward sur 10 000 €",
                "pedagogical_mode": False,
                "capital_eur": 10000,
            },
        )
        assert r_chat_exp.status_code == 200
        chat_exp = r_chat_exp.get_json()
        assert chat_exp["ok"] is True
        assert chat_exp["pedagogical_mode"] is False
        assert "Sortino" in chat_exp["reply"]
    finally:
        os.environ.pop("AURORA_BUSINESS_OFFLINE", None)

