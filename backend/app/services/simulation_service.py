"""
Monte Carlo Simulation Service — Phase 10

Simulates portfolio growth across N scenarios using monthly compounding.
Asset class return assumptions are calibrated to Indian market long-run averages.

Philosophy: pure NumPy, no randomness seeding by default (production behaviour).
Each call draws fresh random samples to reflect genuine uncertainty.
"""

import numpy as np
from backend.app.schemas.simulation import SimulationRequest, SimulationResponse

# ── Indian market annual return assumptions ───────────────────────────────────
# Equity: BSE Sensex / Nifty 50 long-run average ~12%, std ~20%
# Debt:   Gilt / short-duration fund average ~7%, std ~3%
# Gold:   Domestic gold price CAGR ~8%, std ~12%
_ASSET_RETURNS = {
    "equity": {"mean": 0.12, "std": 0.20},
    "debt":   {"mean": 0.07, "std": 0.03},
    "gold":   {"mean": 0.08, "std": 0.12},
}


def run_simulation(data: SimulationRequest) -> SimulationResponse:
    """
    Runs N Monte Carlo scenarios with monthly granularity.

    Each month:
      1. A weighted portfolio return is sampled from normal distributions.
      2. The SIP contribution is added.
    Final corpus after goal_horizon_years is recorded per scenario.
    Success = scenarios where final corpus >= goal_target_amount.
    """
    n = data.n_simulations
    months = data.goal_horizon_years * 12

    eq_w = data.equity_pct / 100.0
    db_w = data.debt_pct / 100.0
    gd_w = data.gold_pct / 100.0

    # Convert annual params to monthly
    eq_mu  = _ASSET_RETURNS["equity"]["mean"] / 12
    eq_sig = _ASSET_RETURNS["equity"]["std"]  / np.sqrt(12)
    db_mu  = _ASSET_RETURNS["debt"]["mean"]   / 12
    db_sig = _ASSET_RETURNS["debt"]["std"]    / np.sqrt(12)
    gd_mu  = _ASSET_RETURNS["gold"]["mean"]   / 12
    gd_sig = _ASSET_RETURNS["gold"]["std"]    / np.sqrt(12)

    # Shape: (n_simulations, months) — sample all returns upfront for efficiency
    eq_returns = np.random.normal(eq_mu, eq_sig, (n, months))
    db_returns = np.random.normal(db_mu, db_sig, (n, months))
    gd_returns = np.random.normal(gd_mu, gd_sig, (n, months))

    # Weighted portfolio monthly return per scenario per month
    portfolio_returns = (
        eq_w * eq_returns +
        db_w * db_returns +
        gd_w * gd_returns
    )   # shape: (n, months)

    # Simulate portfolio value month by month
    corpus = np.full(n, data.initial_investment, dtype=np.float64)

    for m in range(months):
        corpus = corpus * (1 + portfolio_returns[:, m]) + data.monthly_sip

    success_count = np.sum(corpus >= data.goal_target_amount)
    success_prob = float(success_count / n * 100)

    return SimulationResponse(
        success_probability=round(success_prob, 2),
        goal_target_amount=data.goal_target_amount,
        p10_final_value=round(float(np.percentile(corpus, 10)), 2),
        p25_final_value=round(float(np.percentile(corpus, 25)), 2),
        p50_final_value=round(float(np.percentile(corpus, 50)), 2),
        p75_final_value=round(float(np.percentile(corpus, 75)), 2),
        p90_final_value=round(float(np.percentile(corpus, 90)), 2),
        scenarios_run=n,
        goal_horizon_years=data.goal_horizon_years,
        initial_investment=data.initial_investment,
        monthly_sip=data.monthly_sip,
        equity_annual_return_pct=_ASSET_RETURNS["equity"]["mean"] * 100,
        debt_annual_return_pct=_ASSET_RETURNS["debt"]["mean"] * 100,
        gold_annual_return_pct=_ASSET_RETURNS["gold"]["mean"] * 100,
    )
