# Phase 9 — Compliance Agent: Full Deep Dive

---

## What is this phase doing conceptually?

Phase 7 built a LangGraph agent where the **LLM** decides which tools to call. Phase 9 builds a LangGraph agent where **no LLM is involved** — every decision is deterministic.

The compliance agent solves a real problem: Phase 5's allocation might violate the SEBI-inspired rules from Phase 8. Calling Phase 5 then Phase 8 and hoping for the best isn't enough — if violations exist, someone has to fix them. Phase 9 is that someone.

The agent runs a **convergence loop**:
1. Compute allocation (Phase 5 logic)
2. Check it against rules (Phase 8 logic)
3. If violations: fix the allocation deterministically
4. Re-check — repeat until clean or hit MAX_ITERATIONS

This embodies "rules decide" — the entire compliance workflow is a state machine driven by mathematical rules, not LLM judgement.

---

## How Phase 9 compares to Phase 7

| | Phase 7 (Fund Research) | Phase 9 (Compliance) |
|---|---|---|
| Has LLM? | Yes — ChatOllama | No — pure deterministic |
| State | `messages: List[BaseMessage]` | Full typed state dict |
| Loop driver | LLM's `tool_calls` output | Deterministic violation check |
| Node count | 2 (agent + tools) | 3 (compute + check + fix) |
| Exit condition | LLM returns plain text | violations=[] OR max iterations |
| DB access? | Yes (via tool closures) | Yes (node 1 reads risk tier) |
| Non-deterministic? | Yes (LLM output varies) | No (same inputs → same output) |

---

## ComplianceState — Typed Dict, Not Message List

Phase 7's state was just `{"messages": [...]}`. Phase 9's state carries multiple typed fields representing the full portfolio state at each iteration:

```python
class ComplianceState(TypedDict):
    user_id: int
    goal_horizon_years: int
    equity_pct: float
    debt_pct: float
    gold_pct: float
    risk_tier: str
    violations: List[dict]   # raw PolicyViolation dicts
    iteration: int
    passed: bool
```

Every node receives the entire state and returns only the fields it updates. LangGraph merges the returned dict into the current state.

Unlike Phase 7's `Annotated[List, operator.add]` (message accumulation), Phase 9's fields are **replaced** on each update — there's no custom reducer. A node returning `{"equity_pct": 30.0}` replaces the old `equity_pct` value entirely.

`iteration` is a counter that increments in `check_compliance_node`. `passed` is updated after each policy check. `violations` is the list of violations from the last check — the fix node reads it to know what to repair.

---

## The Graph Structure

```
[Entry]
compute_allocation_node
    ↓
check_compliance_node
    ↓
route_after_check()
    │
    ├─ "done" (passed=True OR iteration≥5) ──► END
    │
    └─ "fix" (violations remain) ──► fix_allocation_node
                                            ↓
                                     check_compliance_node
                                            ↓
                                     route_after_check()
                                            ...
```

The loop is `check_compliance → fix_allocation → check_compliance → ...`. The entry point (`compute_allocation`) only runs once at the start.

---

## Node 1: compute_allocation_node

```python
async def compute_allocation_node(state: ComplianceState) -> dict:
    result = await db.execute(
        select(RiskAssessment).where(RiskAssessment.user_id == state["user_id"])
    )
    assessment = result.scalar_one_or_none()

    risk_tier = (
        assessment.risk_tier
        if assessment and assessment.risk_tier
        else "Safer"
    )

    base = _TIER_ALLOCATIONS[risk_tier].copy()
    equity, debt, gold = base["equity"], base["debt"], base["gold"]

    cap = _equity_cap(state["goal_horizon_years"])
    if cap is not None and equity > cap:
        debt += equity - cap
        equity = cap

    return {"equity_pct": equity, "debt_pct": debt, "gold_pct": gold, "risk_tier": risk_tier}
```

This replicates Phase 5's `compute_allocation` logic exactly — reads risk tier from DB, looks up base allocation, applies horizon cap. It's an `async def` because it awaits a DB query.

Why duplicate Phase 5's logic instead of calling `compute_allocation` directly? Because `compute_allocation` is a standalone service function that takes a `data: AllocationRequest` object. Inside the agent, we have the state dict — calling the service would require constructing a schema object. The duplication is intentional for clarity.

The `db` captured via closure (same pattern as Phase 7):

```python
def create_compliance_agent(db: AsyncSession):
    async def compute_allocation_node(state: ComplianceState) -> dict:
        result = await db.execute(...)  # db is captured from outer scope
```

---

## Node 2: check_compliance_node

```python
def check_compliance_node(state: ComplianceState) -> dict:
    req = PolicyCheckRequest(
        equity_pct=state["equity_pct"],
        debt_pct=state["debt_pct"],
        gold_pct=state["gold_pct"],
        risk_tier=state["risk_tier"],
        goal_horizon_years=state["goal_horizon_years"],
    )
    response = check_policy(req)
    return {
        "violations": [v.model_dump() for v in response.violations],
        "passed": response.passed,
        "iteration": state["iteration"] + 1,
    }
```

This is a **sync** function (no `async def`) — Phase 8's `check_policy()` is synchronous (no I/O, pure computation). In LangGraph, sync nodes are allowed alongside async nodes.

Constructs a `PolicyCheckRequest` from the current state, calls the policy engine, and returns updated `violations`, `passed`, and incremented `iteration`.

`v.model_dump()` — converts `PolicyViolation` Pydantic objects to plain dicts for storage in the state (TypedDict requires serialisable values). The `fix_allocation_node` reads `v["asset"]`, `v["rule_type"]`, `v["limit"]` from these dicts.

`"iteration": state["iteration"] + 1` — increments the counter. After `MAX_ITERATIONS = 5` checks, the router terminates even if violations remain.

---

## The Router

```python
def route_after_check(state: ComplianceState) -> str:
    if state["passed"] or state["iteration"] >= MAX_ITERATIONS:
        return "done"
    return "fix"
```

Two exit conditions:
- `state["passed"]` — all rules satisfied, clean allocation found
- `state["iteration"] >= MAX_ITERATIONS` — safety valve, prevents infinite loops

The returned strings `"done"` and `"fix"` are node names in the conditional edge mapping:

```python
graph.add_conditional_edges(
    "check_compliance",
    route_after_check,
    {"fix": "fix_allocation", "done": END},
)
```

`"done"` → `END` (LangGraph sentinel). `"fix"` → `"fix_allocation"`.

---

## Node 3: fix_allocation_node — Deterministic Repair

```python
def fix_allocation_node(state: ComplianceState) -> dict:
    equity = state["equity_pct"]
    debt   = state["debt_pct"]
    gold   = state["gold_pct"]

    for v in state["violations"]:
        asset     = v["asset"]
        rule_type = v["rule_type"]
        limit     = v["limit"]

        if rule_type == "max":
            if asset == "equity_pct":
                excess = equity - limit
                equity = limit
                debt  += excess       # excess equity → debt
            elif asset == "debt_pct":
                excess = debt - limit
                debt   = limit
                equity += excess      # excess debt → equity
            elif asset == "gold_pct":
                excess = gold - limit
                gold   = limit
                equity += excess      # excess gold → equity

        elif rule_type == "min":
            if asset == "debt_pct":
                shortfall = limit - debt
                debt = limit
                if equity >= shortfall:
                    equity -= shortfall   # take from equity first
                else:
                    gold -= (shortfall - equity)   # then from gold
                    equity = 0.0
            elif asset == "gold_pct":
                shortfall = limit - gold
                gold = limit
                if equity >= shortfall:
                    equity -= shortfall
                else:
                    debt -= (shortfall - equity)
                    equity = 0.0
```

**The repair strategy**:

For `max` violations (asset exceeds cap):
- Trim the asset to the limit
- Add the excess to debt (debt is the "shock absorber")
- Exception: if debt itself is capped, add excess to equity

For `min` violations (asset below floor):
- Top up the asset to the floor
- Take the shortfall from equity first (equity has the most room)
- If equity is insufficient, take from gold/debt

**Why equity as the primary source for mins?** Equity has the most slack — it's the largest allocation in most tiers. Taking from equity also tends to move the portfolio in a safer direction (less equity = safer), which rarely creates new violations.

**Floating-point defensive code**:

```python
equity = max(0.0, round(equity, 2))
debt   = max(0.0, round(debt,   2))
gold   = max(0.0, round(gold,   2))

total = equity + debt + gold
if total > 0 and abs(total - 100.0) > 0.01:
    factor = 100.0 / total
    equity = round(equity * factor, 2)
    debt   = round(debt   * factor, 2)
    gold   = round(100.0 - equity - debt, 2)
```

`max(0.0, ...)` — clamps to zero. Multiple violations might push an asset below zero (e.g., taking from equity twice). This prevents negative allocations.

Normalisation — after multiple repairs, floating-point arithmetic can produce totals like 99.97 or 100.03. The normalisation step rescales all three to sum exactly to 100.

---

## Why MAX_ITERATIONS = 5?

Each iteration is: 1 policy check + 1 fix. Each fix should resolve at least one violation. With 8 rules and 3 assets, the maximum meaningful violations in a single check is ~5–6. So 5 iterations is sufficient for any realistic allocation.

The cap also protects against pathological inputs where violations conflict with each other (e.g., a rule requiring equity > 50% and another requiring equity < 30% — impossible to satisfy both). In such cases, the agent terminates and `converged = False` in the response.

---

## Building the Graph

```python
graph = StateGraph(ComplianceState)
graph.add_node("compute_allocation", compute_allocation_node)
graph.add_node("check_compliance", check_compliance_node)
graph.add_node("fix_allocation", fix_allocation_node)

graph.set_entry_point("compute_allocation")
graph.add_edge("compute_allocation", "check_compliance")  # always: compute → check
graph.add_conditional_edges(
    "check_compliance",
    route_after_check,
    {"fix": "fix_allocation", "done": END},
)
graph.add_edge("fix_allocation", "check_compliance")     # always: fix → check

return graph.compile()
```

`add_conditional_edges` with a mapping dict is Phase 9's addition vs Phase 7. In Phase 7, `should_continue` returned either `"tools"` or `END` directly. Here, the router returns `"done"` or `"fix"` — the mapping translates those to actual node names (or `END`). This is cleaner than having the router function know about `END`.

---

## compliance_service.py — Wiring it Together

```python
async def run_compliance_agent(db: AsyncSession, data: ComplianceRequest) -> ComplianceResponse:
    agent = create_compliance_agent(db)

    initial_state = {
        "user_id": data.user_id,
        "goal_horizon_years": data.goal_horizon_years,
        "equity_pct": 0.0,
        "debt_pct": 0.0,
        "gold_pct": 0.0,
        "risk_tier": "",
        "violations": [],
        "iteration": 0,
        "passed": False,
    }

    result = await agent.ainvoke(initial_state)
```

Initial state zeros — `compute_allocation_node` overwrites them in the first step. `iteration=0` and `passed=False` are the starting conditions for the router.

`await agent.ainvoke(initial_state)` — async invocation. Phase 7 used `.ainvoke()` too. Returns the final state dict after the graph terminates.

```python
    return ComplianceResponse(
        user_id=data.user_id,
        goal_horizon_years=data.goal_horizon_years,
        final_allocation=AllocationSnapshot(
            equity_pct=result["equity_pct"],
            ...
            passed=result["passed"],
        ),
        iterations=result["iteration"],
        converged=result["passed"],    # converged = passed (same thing)
    )
```

`converged` in the response is the same as `passed`. `converged=False` means the agent hit MAX_ITERATIONS without finding a clean allocation — the caller should treat the result as approximate.

---

## End-to-end request flow

```
POST /compliance-check
Body: { "user_id": 1, "goal_horizon_years": 2 }
         │
         ▼
run_compliance_agent(db, data)
         │
         ├── create_compliance_agent(db) → compiled LangGraph
         │
         ├── agent.ainvoke(initial_state)
         │       │
         │       ▼
         │  ITERATION 1:
         │  compute_allocation_node:
         │    SELECT risk_assessments WHERE user_id=1 → risk_tier="Riskiest"
         │    base = {equity:85, debt:5, gold:10}
         │    _equity_cap(2) = 30 → equity=30, debt=60, gold=10
         │    returns {equity_pct:30, debt_pct:60, gold_pct:10, risk_tier:"Riskiest"}
         │       │
         │  check_compliance_node:
         │    check_policy(equity=30, debt=60, gold=10, tier="Riskiest", horizon=2)
         │    horizon_short_equity_cap: 30 > 30? → No violation
         │    global_debt_floor: 60 < 5? → No
         │    global_gold_floor: 10 < 3? → No
         │    riskiest_equity_cap: 30 > 90? → No
         │    total: 30+60+10=100 → OK
         │    → passed=True, violations=[], iteration=1
         │       │
         │  route_after_check: passed=True → "done" → END
         │
         ├── result = final state
         │
         ▼
{
  "user_id": 1,
  "goal_horizon_years": 2,
  "final_allocation": {
    "equity_pct": 30.0,
    "debt_pct": 60.0,
    "gold_pct": 10.0,
    "risk_tier": "Riskiest",
    "violations": [],
    "passed": true
  },
  "iterations": 1,
  "converged": true
}
```

Phase 5's horizon cap already produced a compliant allocation — the agent converges in a single iteration. A scenario requiring multiple iterations would occur if someone POSTed a manually-crafted allocation that violates multiple rules.
