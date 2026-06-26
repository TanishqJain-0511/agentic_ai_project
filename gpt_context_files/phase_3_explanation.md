# Phase 3 — Financial Health Engine: Full Deep Dive

---

## What is this phase doing conceptually?

Phase 3 is the first **computation layer** — no data is collected here, just read and transformed. Given a user's financial profile (income, expenses, savings, debt, investments), the engine computes five standard metrics that measure financial wellbeing.

This is pure math. No LLM, no rules engine, no agent. A single service function reads one row from the database and outputs five numbers with status labels.

The output feeds into the Streamlit frontend (Phase 13) as a health dashboard, and provides context for the risk scoring (Phase 4) and explanation (Phase 12).

---

## The 5 Financial Health Metrics

### 1. Net Worth

```
net_worth = total_cash_savings + total_existing_investments − total_debt
```

The most fundamental measure of financial health: what you own minus what you owe. Can be negative (liabilities exceed assets) — common for young people with student loans or home loans.

### 2. Monthly Surplus

```
monthly_income  = annual_income / 12
monthly_surplus = monthly_income − monthly_expenses
```

How much money is left over each month after paying all expenses. Negative surplus means spending more than earning — a critical warning sign. This is the raw material for SIP investments.

### 3. Savings Rate

```
savings_rate = (monthly_surplus / monthly_income) × 100
```

Surplus expressed as a percentage of income. A savings rate of 20%+ means the person saves ₹1 out of every ₹5 earned — considered strong. Below 10% is a warning.

Industry benchmarks:
- `≥ 20%` → `"high"` — financially disciplined
- `10–19%` → `"normal"` — average
- `< 10%` → `"low"` — needs attention

### 4. Debt-to-Income Ratio (DTI)

```
dti = (total_debt / annual_income) × 100
```

Total outstanding debt as a percentage of annual income. Note: this is total outstanding debt, not monthly payment — so a ₹50L home loan vs ₹12L annual salary gives 417% DTI. Indian mortgage lenders typically allow DTI (monthly EMI basis) up to 40-50%.

Our simplified thresholds:
- `< 36%` → `"healthy"` — conservative debt load
- `36–50%` → `"normal"` — manageable
- `> 50%` → `"unhealthy"` — high debt burden

### 5. Emergency Fund Months

```
emergency_fund_months = total_cash_savings / monthly_expenses
```

How many months of expenses can be covered by liquid savings alone (cash savings, not investments — investments can't be instantly liquidated). The standard financial planning advice is 3–6 months.

- `≥ 6` → `"adequate"` — well-covered against emergencies
- `3–5` → `"low"` — some buffer but not ideal
- `< 3` → `"critical"` — vulnerable to any income disruption

---

## File Architecture

```
GET /financial-health/{user_id}
         ↓
main.py → financial_health_service.compute_financial_health(db, user_id)
                   │
                   ├── reads FinancialProfile via financial_profile_service
                   ├── computes 5 metrics (pure math)
                   └── calls 3 helper functions for status labels
```

Two files:
- `schemas/financial_health.py` — `FinancialHealthResponse`
- `services/financial_health_service.py` — `compute_financial_health()` + 3 status helpers

---

## Service: compute_financial_health — Line by Line

```python
async def compute_financial_health(db: AsyncSession, user_id: int):
    profile = await get_financial_profile_by_user_id(db, user_id)
    if not profile:
        return None
```

Delegates DB access to `financial_profile_service`. Returns `None` if the user has no profile — the endpoint returns a 404 in that case. The service itself doesn't raise HTTP exceptions (that's the endpoint's job).

```python
    monthly_income  = profile.annual_income / 12
    monthly_surplus = monthly_income - profile.monthly_expenses
```

Straight division. `annual_income` is always provided, so no division-by-zero risk here.

```python
    net_worth = (
        profile.total_cash_savings
        + profile.total_existing_investments
        - profile.total_debt
    )
```

Simple arithmetic. No risk of division by zero.

```python
    savings_rate = (monthly_surplus / monthly_income * 100) if monthly_income > 0 else 0.0
```

Guard against `monthly_income = 0` (annual_income = 0). Without the guard, Python raises `ZeroDivisionError`. The `if ... else 0.0` is a defensive pattern used wherever division occurs.

```python
    debt_to_income_ratio = (
        profile.total_debt / profile.annual_income * 100
    ) if profile.annual_income > 0 else 0.0
```

Same guard. `total_debt = 0` is fine (numerator is zero, result is 0% DTI).

```python
    emergency_fund_months = (
        profile.total_cash_savings / profile.monthly_expenses
        if profile.monthly_expenses > 0
        else 0.0
    )
```

Guard against `monthly_expenses = 0`. If someone reports zero expenses, we return 0 months rather than infinity.

```python
    return {
        "user_id": user_id,
        "net_worth": round(net_worth, 2),
        ...
        "savings_rate_status": _savings_rate_status(savings_rate),
        "debt_to_income_status": _dti_status(debt_to_income_ratio),
        "emergency_fund_status": _emergency_fund_status(emergency_fund_months),
    }
```

`round(..., 2)` — financial figures displayed to 2 decimal places. The status labels are strings computed by private helper functions.

---

## The 3 Status Helper Functions

```python
def _savings_rate_status(rate: float) -> str:
    if rate >= 20:
        return "high"
    elif rate >= 10:
        return "normal"
    return "low"
```

Private functions (prefixed `_`) — not imported anywhere outside this module. The thresholds are hardcoded constants based on common financial planning heuristics.

Each helper has the same structure: a series of ordered conditions, returning a string label. The order matters — conditions are evaluated from most favourable down to least favourable.

---

## Schema: FinancialHealthResponse

```python
class FinancialHealthResponse(BaseModel):
    user_id: int
    net_worth: float
    monthly_surplus: float
    savings_rate: float
    debt_to_income_ratio: float
    emergency_fund_months: float
    savings_rate_status: str      # "high" | "normal" | "low"
    debt_to_income_status: str    # "healthy" | "normal" | "unhealthy"
    emergency_fund_status: str    # "adequate" | "low" | "critical"
```

No `from_attributes = True` needed — the service returns a plain `dict`, not an ORM object. Pydantic can read from dicts directly.

The status fields are `str` — Pydantic doesn't enforce which string values are valid (no `Literal` types). In production you'd use `Literal["high", "normal", "low"]` to get validation.

---

## Why this is "no side effects"

Unlike Phase 4 (which writes `risk_score` and `risk_tier` back to the database), Phase 3 is **read-only**. `compute_financial_health` calls `get_financial_profile_by_user_id`, reads the profile, does math, and returns a dict. Nothing is written to the database.

This is intentional — financial health metrics are derived values, not stored values. Every time you request them, they're recomputed from the raw stored data. This means if the user updates their financial profile, the health metrics automatically reflect the new values without any extra work.

---

## End-to-end request flow

```
GET /financial-health/1
         │
         ▼
compute_financial_health(db, user_id=1)
         │
         ├── get_financial_profile_by_user_id(db, 1)
         │       SELECT * FROM financial_profiles WHERE user_id = 1
         │       → profile (annual_income=720000, monthly_expenses=30000,
         │                  total_cash_savings=150000, total_existing_investments=200000,
         │                  total_debt=500000)
         │
         ├── monthly_income  = 720000 / 12 = 60000
         ├── monthly_surplus = 60000 - 30000 = 30000
         ├── net_worth       = 150000 + 200000 - 500000 = -150000
         ├── savings_rate    = 30000 / 60000 * 100 = 50.0%
         ├── dti             = 500000 / 720000 * 100 = 69.4%
         ├── emergency_fund  = 150000 / 30000 = 5.0 months
         │
         ├── savings_rate_status = "high" (50% ≥ 20%)
         ├── dti_status          = "unhealthy" (69.4% > 50%)
         ├── emergency_status    = "low" (5.0 months: ≥ 3 but < 6)
         │
         ▼
{
  "user_id": 1,
  "net_worth": -150000.0,
  "monthly_surplus": 30000.0,
  "savings_rate": 50.0,
  "debt_to_income_ratio": 69.44,
  "emergency_fund_months": 5.0,
  "savings_rate_status": "high",
  "debt_to_income_status": "unhealthy",
  "emergency_fund_status": "low"
}
```

A person with 50% savings rate, high debt load, and 5 months emergency fund — a common profile for someone with an active home loan. The metrics flag the high DTI while acknowledging the strong savings behaviour.
