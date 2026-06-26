# Phase 10 — Monte Carlo Simulation: Full Deep Dive

---

## What is this phase doing conceptually?

Phases 3–9 compute what the investor should do. Phase 10 answers: **if they follow this plan, will they actually reach their goal?**

A simple CAGR projection says: "with 12% annual equity return, ₹1L invested for 10 years becomes ₹3.1L". But this assumes returns are constant — they're not. Some years equity returns 35%, some years it returns -20%. The sequence of returns matters enormously. A string of bad years early in the investment period can devastate an otherwise sound plan.

Monte Carlo simulation addresses this by running **thousands of parallel scenarios**, each with randomly sampled returns drawn from realistic distributions. The result is not a single projected number but a **distribution of outcomes** — and the percentage of scenarios where the portfolio reaches the target is the **success probability**.

---

## Why Monte Carlo over simple projection?

```
Simple CAGR projection:
  ₹1L at 12% for 10 years = ₹1L × 1.12^10 = ₹3.10L
  This number has zero uncertainty. It assumes 12% every single year.

Monte Carlo:
  Scenario 1: returns are [-5%, 20%, 8%, 35%, 2%, ...] → final: ₹2.80L
  Scenario 2: returns are [18%, -15%, 25%, 12%, ...] → final: ₹3.45L
  Scenario 3: returns are [3%, 1%, -20%, 8%, 5%, ...] → final: ₹2.10L
  ...1000 scenarios...
  Fraction reaching ₹3L target = 68% → success probability = 68%
```

Monte Carlo gives you the distribution, not a point estimate. The p10 value (10th percentile) is the pessimistic case — 90% of scenarios do better. The p90 is the optimistic case.

---

## Indian Market Assumptions

```python
_ASSET_RETURNS = {
    "equity": {"mean": 0.12, "std": 0.20},
    "debt":   {"mean": 0.07, "std": 0.03},
    "gold":   {"mean": 0.08, "std": 0.12},
}
```

**Equity (Nifty 50 / Sensex long-run)**: 12% mean annual return, 20% standard deviation. The 20% std captures the wild swings of Indian equity markets — a crash of -40% is within 2 standard deviations.

**Debt (Gilt / short-duration)**: 7% mean, 3% std. Debt is stable — government bonds barely fluctuate. The low std reflects this predictability.

**Gold (domestic price CAGR)**: 8% mean, 12% std. Gold is more volatile than debt but less than equity. It's often negatively correlated with equity — it rises during market stress.

These are **annual** figures. The simulation runs monthly, so they must be converted.

---

## Annual → Monthly Parameter Conversion

```python
eq_mu  = _ASSET_RETURNS["equity"]["mean"] / 12
eq_sig = _ASSET_RETURNS["equity"]["std"]  / np.sqrt(12)
```

**Mean conversion**: Annual mean / 12 = monthly mean. ₹100 at 12% annual = ₹112 after 12 months. Monthly: ₹100 × (1 + 0.01)^12 ≈ ₹112.68. For small rates, `mean/12` is a good approximation (exact formula is `(1 + annual)^(1/12) - 1`, but the approximation is sufficient here).

**Standard deviation conversion**: Annual std / √12 = monthly std. This comes from the statistical property that if monthly returns are independent and identically distributed:

```
Var(annual) = 12 × Var(monthly)   [sum of 12 independent variances]
Std(annual) = √12 × Std(monthly)
∴ Std(monthly) = Std(annual) / √12
```

This is only exact for additive (arithmetic) returns, but for the magnitudes involved it's a reasonable approximation.

---

## NumPy Vectorisation — The Core Computation

The key performance insight: instead of running 1000 Python loops one by one, we use NumPy to compute all 1000 scenarios simultaneously via matrix operations.

```python
n = data.n_simulations      # e.g. 1000
months = data.goal_horizon_years * 12   # e.g. 120 for 10 years

# Shape: (n_simulations, months) — all returns sampled upfront
eq_returns = np.random.normal(eq_mu, eq_sig, (n, months))
db_returns = np.random.normal(db_mu, db_sig, (n, months))
gd_returns = np.random.normal(gd_mu, gd_sig, (n, months))
```

`np.random.normal(mean, std, shape)` generates a matrix of shape `(1000, 120)` = 120,000 random return values from a normal distribution, all in one call.

Each row is one scenario's 120 monthly returns. Each column is one month's returns across all 1000 scenarios.

```python
portfolio_returns = (
    eq_w * eq_returns +
    db_w * db_returns +
    gd_w * gd_returns
)   # shape: (1000, 120)
```

Element-wise weighted sum. If equity=60%, debt=30%, gold=10%:
- Monthly portfolio return = 0.6 × equity_return + 0.3 × debt_return + 0.1 × gold_return

This produces a `(1000, 120)` matrix where each element is the weighted portfolio monthly return for that scenario-month combination.

---

## The Simulation Loop

```python
corpus = np.full(n, data.initial_investment, dtype=np.float64)

for m in range(months):
    corpus = corpus * (1 + portfolio_returns[:, m]) + data.monthly_sip
```

`corpus` starts as a vector of 1000 identical values (`initial_investment`). Shape: `(1000,)`.

Each month `m`:
- `portfolio_returns[:, m]` — column `m` of the returns matrix. Shape: `(1000,)`. One return per scenario for this month.
- `corpus * (1 + portfolio_returns[:, m])` — compound the corpus by this month's return. Shape: `(1000,)`.
- `+ data.monthly_sip` — add the SIP contribution. Same for all 1000 scenarios (SIP is deterministic).

After 120 iterations, `corpus` contains 1000 final values — one per scenario.

**Why a loop instead of a single matrix operation?** The month-by-month compounding is inherently sequential — month 2 depends on month 1's corpus. You can't vectorise across the time dimension for this reason. You can vectorise across scenarios (the 1000 dimension) — and that's exactly what we do with `corpus * (1 + portfolio_returns[:, m])`.

---

## Success Probability and Percentiles

```python
success_count = np.sum(corpus >= data.goal_target_amount)
success_prob  = float(success_count / n * 100)
```

Count the scenarios where the final corpus reached the target. Divide by total scenarios to get a fraction. Multiply by 100 for a percentage.

```python
p10_final_value = round(float(np.percentile(corpus, 10)), 2)
p25_final_value = round(float(np.percentile(corpus, 25)), 2)
p50_final_value = round(float(np.percentile(corpus, 50)), 2)
p75_final_value = round(float(np.percentile(corpus, 75)), 2)
p90_final_value = round(float(np.percentile(corpus, 90)), 2)
```

`np.percentile(corpus, 10)` — the value below which 10% of scenarios fall. If p10 = ₹2.5L, it means even in the worst 10% of scenarios, you'd still end up with ₹2.5L.

**Interpreting the percentiles**:
- `p10` — pessimistic case (bad luck, poor returns)
- `p50` — median outcome (expected central case)
- `p90` — optimistic case (good returns sequence)

The Streamlit frontend (Phase 13) visualises these as a bar chart with the target amount marked — so you can see at a glance whether the p50 outcome clears the goal.

---

## Why the simulation is not seeded

```python
# No np.random.seed() call
eq_returns = np.random.normal(eq_mu, eq_sig, (n, months))
```

Production Monte Carlo simulations should not be seeded. Seeding produces the same results every run — which would give false confidence (users would always see the same probability). Each call to `POST /simulate` should draw fresh random samples to reflect genuine uncertainty.

For unit tests, you would seed: `np.random.seed(42)` before calling `run_simulation` to make tests deterministic.

---

## No DB dependency

```python
@app.post("/simulate", response_model=SimulationResponse)
async def simulate_endpoint(data: SimulationRequest):
    return run_simulation(data)   # No db parameter!
```

The simulation is entirely stateless — inputs come from the request body, outputs are computed in memory. No database reads or writes. This makes it the fastest endpoint in the application — just NumPy math.

`run_simulation` is also sync (`def`, not `async def`). FastAPI handles sync route functions by running them in a threadpool, preventing the event loop from blocking. Pure CPU-bound NumPy operations are fast enough (~50ms for 1000 scenarios) that this isn't a concern.

---

## End-to-end request flow

```
POST /simulate
Body: {
  "equity_pct": 65.0, "debt_pct": 25.0, "gold_pct": 10.0,
  "initial_investment": 100000,
  "monthly_sip": 10000,
  "goal_target_amount": 5000000,
  "goal_horizon_years": 10,
  "n_simulations": 1000
}
         │
         ▼
run_simulation(data)
         │
         ├── months = 10 × 12 = 120
         ├── eq_w=0.65, db_w=0.25, gd_w=0.10
         │
         ├── eq_mu=0.12/12=0.01, eq_sig=0.20/√12≈0.0577
         ├── db_mu=0.07/12≈0.0058, db_sig=0.03/√12≈0.00866
         ├── gd_mu=0.08/12≈0.0067, gd_sig=0.12/√12≈0.0346
         │
         ├── eq_returns = np.random.normal(0.01, 0.0577, (1000, 120))
         ├── db_returns = np.random.normal(0.0058, 0.00866, (1000, 120))
         ├── gd_returns = np.random.normal(0.0067, 0.0346, (1000, 120))
         │
         ├── portfolio_returns = 0.65×eq + 0.25×db + 0.10×gd  shape:(1000,120)
         │
         ├── corpus = [100000, 100000, ..., 100000]  shape:(1000,)
         ├── for m in range(120):
         │       corpus = corpus × (1 + portfolio_returns[:,m]) + 10000
         │
         ├── corpus shape:(1000,) — 1000 final values
         ├── success_count = sum(corpus >= 5000000)  e.g. 680
         ├── success_prob = 680/1000 × 100 = 68.0%
         │
         ├── p10 = np.percentile(corpus, 10)  e.g. 3200000
         ├── p50 = np.percentile(corpus, 50)  e.g. 4800000
         ├── p90 = np.percentile(corpus, 90)  e.g. 7100000
         │
         ▼
{
  "success_probability": 68.0,
  "goal_target_amount": 5000000,
  "p10_final_value": 3200000.0,
  "p25_final_value": 3900000.0,
  "p50_final_value": 4800000.0,
  "p75_final_value": 5900000.0,
  "p90_final_value": 7100000.0,
  "scenarios_run": 1000,
  "goal_horizon_years": 10,
  ...
}
```

A 68% success probability means: in 680 out of 1000 simulated futures, this SIP plan reaches ₹50L in 10 years. The p50 of ₹48L is below the ₹50L target — meaning in the median scenario, the investor falls slightly short. To improve: increase SIP, increase horizon, or accept higher equity allocation.
