# Phase 5 — Allocation Engine: Full Deep Dive

---

## What is this phase doing conceptually?

Phase 4 told us **how much risk** the investor should take (Safest / Safer / Riskier / Riskiest). Phase 5 translates that abstract risk tier into **concrete percentages** across three asset classes: equity, debt, and gold.

This is purely deterministic — no LLM, no agent, no YAML rules. Just two pieces of logic:

1. **Base allocation lookup**: each risk tier maps to a fixed equity/debt/gold split
2. **Horizon cap**: if the goal is less than 5 years away, equity is capped regardless of risk tier

The output of Phase 5 (equity_pct, debt_pct, gold_pct) is the direct input to Phases 7, 8, 9, 10, 11, 12 — it's the central output of the deterministic engine.

---

## The Base Allocation Table

```python
_TIER_ALLOCATIONS = {
    "Safest":   {"equity": 20.0, "debt": 75.0, "gold": 5.0},
    "Safer":    {"equity": 40.0, "debt": 55.0, "gold": 5.0},
    "Riskier":  {"equity": 65.0, "debt": 25.0, "gold": 10.0},
    "Riskiest": {"equity": 85.0, "debt":  5.0, "gold": 10.0},
}
```

**Why a lookup table, not a formula?** Formulas for allocation (like `equity = risk_score × 0.85`) produce continuous values. In practice, financial advisors use discrete tiers because the differences within a tier are not meaningful enough to warrant different portfolios. A score of 51 vs 75 both produce "Riskier" — and the allocation for both is 65% equity. Discrete tiers also make the system auditable and explainable.

**Why these specific percentages?**

- `Safest (20/75/5)`: Capital preservation — heavily debt-weighted. For retirees or those with very short horizons who cannot afford losses.
- `Safer (40/55/5)`: Balanced — more equity for moderate growth, still majority debt for stability.
- `Riskier (65/25/10)`: Growth-oriented — equity-majority with meaningful gold allocation as a hedge.
- `Riskiest (85/5/10)`: Aggressive growth — maximum equity, minimal debt floor, gold as diversifier.

**Why gold in every tier?** Gold has low correlation with equity and debt — it tends to rise when both fall (flight to safety). Even a 5% gold allocation meaningfully reduces portfolio volatility without significantly dragging returns.

**Why always at least 5% debt for Riskiest?** Pure equity portfolios are too volatile and require extreme psychological fortitude. Even the most aggressive tier keeps 5% in debt as a liquidity buffer and volatility dampener.

---

## The Horizon Cap

```python
def _equity_cap(years: int):
    if years < 3:  return 30.0
    if years < 5:  return 50.0
    return None    # no cap
```

**The problem this solves**: Market cycles typically take 3–7 years to complete. If your goal is 2 years away and you're 85% in equity, a market crash in year 1 could devastate your corpus right before you need it. You wouldn't have time to wait for a recovery.

**How it works**:

```python
cap = _equity_cap(data.goal_horizon_years)
if cap is not None and equity > cap:
    excess = equity - cap
    equity = cap
    debt = debt + excess    # excess equity → goes to debt
    horizon_capped = True
```

The excess equity doesn't disappear — it moves to debt. This preserves the total = 100% invariant. Gold is never touched by horizon capping (gold is already at floor allocation).

**Example**: A "Riskiest" investor (85% equity) with a 2-year goal:
- Cap = 30%
- Excess = 85 − 30 = 55%
- Result: equity=30%, debt=5%+55%=60%, gold=10%
- `horizon_capped = True` — the frontend shows a note explaining why equity was reduced

**`return None` means no cap**: For horizons ≥ 5 years, `_equity_cap` returns `None`, and the `if cap is not None` check means the base allocation is used unchanged.

---

## DB Lookup: Reading the Risk Tier

```python
async def compute_allocation(db: AsyncSession, data: AllocationRequest) -> dict:
    assessment = await get_risk_assessment_by_user_id(db, data.user_id)
    risk_tier = (
        assessment.risk_tier
        if assessment and assessment.risk_tier
        else "Safer"
    )
```

Phase 5 doesn't recompute the risk tier — it reads it from the database (where Phase 4 wrote it). This is the clean handoff between phases.

`else "Safer"` — defensive default. If the user hasn't completed Phase 4 yet (no risk assessment, or risk_tier is NULL), the system defaults to "Safer". This is a conservative choice — it's better to start with a balanced allocation than to crash or refuse to work.

---

## horizon_capped flag

```python
return {
    ...
    "horizon_capped": horizon_capped,
}
```

This boolean tells the consumer whether equity was reduced from the base allocation. Phase 12 (Explanation Generator) uses it to add a note: "Equity was reduced because your goal horizon is short." Without this flag, the user would wonder why their "Riskiest" profile got 30% equity.

---

## End-to-end request flow

```
POST /allocation
Body: { "user_id": 1, "goal_horizon_years": 2 }
         │
         ▼
compute_allocation(db, data)
         │
         ├── get_risk_assessment_by_user_id(db, 1)
         │       → assessment.risk_tier = "Riskiest"
         │
         ├── base = {"equity": 85.0, "debt": 5.0, "gold": 10.0}
         │
         ├── _equity_cap(2) → 30.0
         ├── equity (85.0) > cap (30.0):
         │       excess = 85.0 - 30.0 = 55.0
         │       equity = 30.0
         │       debt   = 5.0 + 55.0 = 60.0
         │       horizon_capped = True
         │
         ▼
{
  "user_id": 1,
  "risk_tier": "Riskiest",
  "goal_horizon_years": 2,
  "equity_pct": 30.0,
  "debt_pct": 60.0,
  "gold_pct": 10.0,
  "horizon_capped": true
}
```

```
POST /allocation
Body: { "user_id": 1, "goal_horizon_years": 15 }
         │
         ▼
         ├── base = {"equity": 85.0, "debt": 5.0, "gold": 10.0}
         ├── _equity_cap(15) → None
         ├── No cap applied
         │
         ▼
{
  "equity_pct": 85.0,
  "debt_pct": 5.0,
  "gold_pct": 10.0,
  "horizon_capped": false
}
```

The same "Riskiest" investor gets 85% equity for a 15-year goal but only 30% equity for a 2-year goal. The risk tier doesn't change — the horizon changes what's appropriate.

---

## Why Phase 9 (Compliance Agent) replaces this endpoint

Phase 5 (`POST /allocation`) computes allocation and applies the horizon cap — but it doesn't verify the result against the full set of SEBI-inspired rules. Phase 9 (`POST /compliance-check`) runs Phase 5's logic internally as its first step, then feeds the allocation through the policy engine (Phase 8) in a loop until it passes all rules.

In practice, the Streamlit frontend uses `POST /compliance-check` (Phase 9), not `POST /allocation` (Phase 5), for the actual user-facing workflow. Phase 5 exists as a standalone endpoint for testing and for understanding the allocation logic independently of compliance checking.
