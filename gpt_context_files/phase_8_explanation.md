# Phase 8 — Policy Engine: Full Deep Dive

---

## What is this phase doing conceptually?

Phase 5 computes an allocation. Phase 8 **validates** it. The policy engine takes an allocation (equity_pct, debt_pct, gold_pct), a risk tier, and a goal horizon, then checks it against a set of SEBI-inspired compliance rules to determine if any are violated.

This is not the same as Phase 9 (Compliance Agent). Phase 8 is a **pure evaluator** — it tells you which rules are violated, but doesn't fix anything. Phase 9 wraps Phase 8 in a loop that fixes violations automatically. Understanding Phase 8 is prerequisite to understanding Phase 9.

The key design: rules live in a YAML file, not in Python code. The policy engine reads the YAML and evaluates it. To add a new rule, you edit the YAML — no code changes required.

---

## The YAML Rules File

```yaml
# backend/app/policies/rules.yaml
rules:
  - id: safest_equity_cap
    description: "Safest tier: equity must not exceed 25%"
    asset: equity_pct
    rule_type: max
    limit: 25.0
    applies_to_tiers: ["Safest"]

  - id: safer_equity_cap
    description: "Safer tier: equity must not exceed 55%"
    asset: equity_pct
    rule_type: max
    limit: 55.0
    applies_to_tiers: ["Safer"]

  - id: riskier_equity_cap
    description: "Riskier tier: equity must not exceed 70%"
    asset: equity_pct
    rule_type: max
    limit: 70.0
    applies_to_tiers: ["Riskier"]

  - id: riskiest_equity_cap
    description: "Riskiest tier: equity must not exceed 90%"
    asset: equity_pct
    rule_type: max
    limit: 90.0
    applies_to_tiers: ["Riskiest"]

  - id: global_debt_floor
    description: "All tiers: debt must be at least 5%"
    asset: debt_pct
    rule_type: min
    limit: 5.0
    # No applies_to_tiers → applies to all tiers

  - id: global_gold_floor
    description: "All tiers: gold must be at least 3%"
    asset: gold_pct
    rule_type: min
    limit: 3.0
    # No applies_to_tiers → applies to all tiers

  - id: horizon_short_equity_cap
    description: "Horizon < 3 years: equity must not exceed 30%"
    asset: equity_pct
    rule_type: max
    limit: 30.0
    applies_when_horizon_lt: 3

  - id: horizon_medium_equity_cap
    description: "Horizon < 5 years: equity must not exceed 50%"
    asset: equity_pct
    rule_type: max
    limit: 50.0
    applies_when_horizon_lt: 5
```

### Rule structure

Each rule is a dict with these fields:

| Field | Type | Purpose |
|-------|------|---------|
| `id` | str | Unique identifier — appears in violation reports |
| `description` | str | Human-readable explanation |
| `asset` | str | Which allocation field: `equity_pct`, `debt_pct`, `gold_pct` |
| `rule_type` | str | `"max"` (cap) or `"min"` (floor) |
| `limit` | float | The threshold value |
| `applies_to_tiers` | list[str] | Optional — only check this rule for these tiers |
| `applies_when_horizon_lt` | int | Optional — only check if horizon < this value |

### Why YAML, not hardcoded Python?

**Separation of concerns**: Financial rules are business logic that regulators can change. YAML allows a non-developer to add or modify rules without touching Python code.

**Readability**: A compliance officer can read and verify the YAML file. They cannot easily read the equivalent Python if/elif chains.

**Single source of truth**: Rules are in one file, not scattered across services. Phase 8's engine and Phase 9's agent both use the same rules.

---

## Policy Engine: Loading Rules Once

```python
_RULES_PATH = os.path.join(os.path.dirname(__file__), "..", "policies", "rules.yaml")

with open(_RULES_PATH, "r") as _f:
    _RULES: List[dict] = yaml.safe_load(_f)["rules"]
```

This runs at **module import time** — once when the application starts, not on every request. `_RULES` is a module-level list of dicts that's shared across all requests.

`yaml.safe_load()` parses the YAML into Python objects without executing arbitrary code (unlike `yaml.load()`). The `["rules"]` extracts the list of rules from the top-level `rules:` key.

`os.path.dirname(__file__)` — the directory containing `policy_engine.py`. This makes the path relative to the file's location, so the engine works regardless of the current working directory when the server starts.

**Performance advantage**: YAML parsing (file I/O + string parsing) happens once at startup. If rules were read from a file per request, each `POST /policy-check` call would do unnecessary I/O.

---

## Rule Applicability Filtering

```python
def _rule_applies(rule: dict, data: PolicyCheckRequest) -> bool:
    # Tier filter
    tiers = rule.get("applies_to_tiers")
    if tiers and data.risk_tier not in tiers:
        return False

    # Horizon filter
    horizon_lt = rule.get("applies_when_horizon_lt")
    if horizon_lt is not None and data.goal_horizon_years >= horizon_lt:
        return False

    return True
```

Before evaluating a rule, we check if it applies to this specific request.

**Tier filter**: `rule.get("applies_to_tiers")` returns `None` if the key is absent (no tier restriction) or a list like `["Safest"]`. If the list exists and the request's risk_tier is not in it, skip this rule.

**Horizon filter**: `applies_when_horizon_lt: 3` means "only apply if horizon < 3". `rule.get("applies_when_horizon_lt")` returns `None` for rules without this key. `if horizon_lt is not None and data.goal_horizon_years >= horizon_lt` — if the horizon threshold exists and the actual horizon is >= it, the rule doesn't apply.

**Example**: `horizon_short_equity_cap` has `applies_when_horizon_lt: 3`. For a 5-year horizon, `5 >= 3` → rule doesn't apply. For a 2-year horizon, `2 >= 3` is False → condition not triggered → `_rule_applies` returns True → rule is checked.

---

## Rule Evaluation Loop

```python
def check_policy(data: PolicyCheckRequest) -> PolicyCheckResponse:
    allocation = {
        "equity_pct": data.equity_pct,
        "debt_pct":   data.debt_pct,
        "gold_pct":   data.gold_pct,
    }
    violations: List[PolicyViolation] = []

    for rule in _RULES:
        if not _rule_applies(rule, data):
            continue

        asset    = rule["asset"]
        actual   = allocation[asset]
        limit    = float(rule["limit"])
        rule_type = rule["rule_type"]

        breached = (rule_type == "max" and actual > limit) or \
                   (rule_type == "min" and actual < limit)

        if breached:
            violations.append(PolicyViolation(
                rule_id=rule["id"],
                description=rule["description"],
                asset=asset,
                rule_type=rule_type,
                limit=limit,
                actual=actual,
            ))
```

**The `allocation` dict** maps field names (`"equity_pct"`) to values. This lets us do `allocation[rule["asset"]]` — a dynamic lookup using the rule's `asset` field as the key. No if/elif per asset class needed.

**Breach condition**:
- `max` rule: violated if `actual > limit` (equity is too high)
- `min` rule: violated if `actual < limit` (debt or gold is too low)

**PolicyViolation** records everything needed to understand and fix the violation: which rule, which asset, what the limit is, what the actual value is.

---

## The Total Sanity Check

```python
total = data.equity_pct + data.debt_pct + data.gold_pct
if abs(total - 100.0) > 0.5:
    violations.append(PolicyViolation(
        rule_id="total_allocation_check",
        description=f"equity + debt + gold must equal 100% (got {total:.1f}%)",
        asset="total",
        rule_type="exact",
        limit=100.0,
        actual=total,
    ))
```

This is an internal sanity check, not a business rule. Any allocation that doesn't sum to ~100% is malformed. The `abs(total - 100.0) > 0.5` tolerance allows for minor floating-point imprecision (e.g., 99.99 + 0.01 = 99.9999... which rounds to 100.00).

This check is hardcoded (not in the YAML) because it's a mathematical invariant, not a financial policy.

---

## Schema: PolicyViolation and PolicyCheckResponse

```python
class PolicyViolation(BaseModel):
    rule_id: str
    description: str
    asset: str
    rule_type: str       # "max" or "min"
    limit: float
    actual: float

class PolicyCheckResponse(BaseModel):
    passed: bool
    violations_count: int
    violations: List[PolicyViolation]
```

`passed = len(violations) == 0` — true only if no rules were violated. Phase 9 reads this `passed` flag to decide whether to fix the allocation or terminate.

`violations_count` is redundant (`len(violations)`) but makes the response self-documenting — consumers don't need to call `len()` on the violations list.

---

## Why this has no DB dependency

```python
@app.post("/policy-check", response_model=PolicyCheckResponse)
async def policy_check_endpoint(data: PolicyCheckRequest):
    return check_policy(data)    # No `db` parameter!
```

The policy engine is **stateless** — all rules are loaded into memory at startup, and all inputs come from the request body. No database read needed. This makes it:

1. **Fast** — no I/O on the hot path
2. **Testable** — you can call `check_policy()` directly in unit tests without a DB
3. **Pure** — the same inputs always produce the same outputs

This is also why the compliance agent (Phase 9) can call `check_policy()` in a loop without worrying about DB connection overhead.

---

## End-to-end request flow

```
POST /policy-check
Body: {
  "equity_pct": 85.0,
  "debt_pct": 5.0,
  "gold_pct": 10.0,
  "risk_tier": "Safer",
  "goal_horizon_years": 8
}
         │
         ▼
check_policy(data)
         │
         ├── Rule: safest_equity_cap → applies_to_tiers=["Safest"] → Safer not in list → SKIP
         ├── Rule: safer_equity_cap  → applies_to_tiers=["Safer"] → ✓ applies
         │         equity_pct=85 > limit=55 → VIOLATION
         │         PolicyViolation(rule_id="safer_equity_cap", actual=85, limit=55)
         │
         ├── Rule: riskier_equity_cap → applies_to_tiers=["Riskier"] → SKIP
         ├── Rule: riskiest_equity_cap → applies_to_tiers=["Riskiest"] → SKIP
         │
         ├── Rule: global_debt_floor → no tier filter → ✓ applies
         │         debt_pct=5.0 < limit=5.0? → 5.0 < 5.0 is False → NO violation
         │
         ├── Rule: global_gold_floor → no tier filter → ✓ applies
         │         gold_pct=10.0 < limit=3.0? → False → NO violation
         │
         ├── Rule: horizon_short_equity_cap → applies_when_horizon_lt=3
         │         goal_horizon_years=8 >= 3 → SKIP
         │
         ├── Rule: horizon_medium_equity_cap → applies_when_horizon_lt=5
         │         goal_horizon_years=8 >= 5 → SKIP
         │
         ├── Total check: 85+5+10=100 → abs(100-100)=0 < 0.5 → NO violation
         │
         ▼
{
  "passed": false,
  "violations_count": 1,
  "violations": [
    {
      "rule_id": "safer_equity_cap",
      "description": "Safer tier: equity must not exceed 55%",
      "asset": "equity_pct",
      "rule_type": "max",
      "limit": 55.0,
      "actual": 85.0
    }
  ]
}
```

An allocation built for "Riskiest" submitted under "Safer" tier catches a single equity cap violation. Phase 9's fix_allocation node would then trim equity from 85 → 55 and add the 30% excess to debt.
