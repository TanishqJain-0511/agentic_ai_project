"""
Compliance Agent — Phase 9

A LangGraph StateGraph that enforces portfolio compliance deterministically.
No LLM involved — embodies "rules decide" from the project philosophy.

Loop:
  compute_allocation → check_compliance → (passed or max_iter) → END
                                        ↓ violations remain
                                   fix_allocation → check_compliance → ...
"""

from typing import TypedDict, List

from langgraph.graph import StateGraph, END
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.models.risk_assessment import RiskAssessment
from backend.app.schemas.policy import PolicyCheckRequest
from backend.app.services.policy_engine import check_policy

MAX_ITERATIONS = 5

_TIER_ALLOCATIONS = {
    "Safest":   {"equity": 20.0, "debt": 75.0, "gold": 5.0},
    "Safer":    {"equity": 40.0, "debt": 55.0, "gold": 5.0},
    "Riskier":  {"equity": 65.0, "debt": 25.0, "gold": 10.0},
    "Riskiest": {"equity": 85.0, "debt":  5.0, "gold": 10.0},
}


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


def create_compliance_agent(db: AsyncSession):
    """
    Factory that returns a compiled compliance agent bound to a DB session.
    The compute_allocation node captures `db` as a closure.
    """

    # ── Node 1: Compute initial allocation ───────────────────────────────────
    async def compute_allocation_node(state: ComplianceState) -> dict:
        result = await db.execute(select(RiskAssessment).where(RiskAssessment.user_id == state["user_id"]))

        assessment = result.scalar_one_or_none()

        risk_tier = assessment.risk_tier if assessment and assessment.risk_tier else "Safer"


        base = _TIER_ALLOCATIONS[risk_tier].copy()
        equity, debt, gold = base["equity"], base["debt"], base["gold"]

        # Apply horizon equity cap (mirrors allocation_service logic)
        cap = _equity_cap(state["goal_horizon_years"])
        if cap is not None and equity > cap:
            debt += equity - cap
            equity = cap

        return {
            "equity_pct": equity,
            "debt_pct": debt,
            "gold_pct": gold,
            "risk_tier": risk_tier,
        }

    # ── Node 2: Run policy check ──────────────────────────────────────────────
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

    # ── Node 3: Deterministically fix violations ──────────────────────────────
    def fix_allocation_node(state: ComplianceState) -> dict:
        equity = state["equity_pct"]
        debt = state["debt_pct"]
        gold = state["gold_pct"]

        for v in state["violations"]:
            asset = v["asset"]
            rule_type = v["rule_type"]
            limit = v["limit"]

            if rule_type == "max":
                # Asset exceeds cap — trim it and add excess to debt
                if asset == "equity_pct":
                    excess = equity - limit
                    equity = limit
                    debt += excess
                elif asset == "debt_pct":
                    excess = debt - limit
                    debt = limit
                    equity += excess
                elif asset == "gold_pct":
                    excess = gold - limit
                    gold = limit
                    equity += excess

            elif rule_type == "min":
                # Asset below floor — top it up by taking from equity first
                if asset == "debt_pct":
                    shortfall = limit - debt
                    debt = limit
                    if equity >= shortfall:
                        equity -= shortfall
                    else:
                        gold -= (shortfall - equity)
                        equity = 0.0
                elif asset == "gold_pct":
                    shortfall = limit - gold
                    gold = limit
                    if equity >= shortfall:
                        equity -= shortfall
                    else:
                        debt -= (shortfall - equity)
                        equity = 0.0

        # Clamp negatives defensively
        equity = max(0.0, round(equity, 2))
        debt = max(0.0, round(debt, 2))
        gold = max(0.0, round(gold, 2))

        # Normalise to 100 if floating-point drift crept in
        total = equity + debt + gold
        if total > 0 and abs(total - 100.0) > 0.01:
            factor = 100.0 / total
            equity = round(equity * factor, 2)
            debt = round(debt * factor, 2)
            gold = round(100.0 - equity - debt, 2)

        return {"equity_pct": equity, "debt_pct": debt, "gold_pct": gold}

    # ── Router ────────────────────────────────────────────────────────────────
    def route_after_check(state: ComplianceState) -> str:
        if state["passed"] or state["iteration"] >= MAX_ITERATIONS:
            return "done"
        return "fix"

    # ── Build the graph ───────────────────────────────────────────────────────
    graph = StateGraph(ComplianceState)
    graph.add_node("compute_allocation", compute_allocation_node)
    graph.add_node("check_compliance", check_compliance_node)
    graph.add_node("fix_allocation", fix_allocation_node)

    graph.set_entry_point("compute_allocation")
    graph.add_edge("compute_allocation", "check_compliance")
    graph.add_conditional_edges("check_compliance",route_after_check,
                                {"fix": "fix_allocation", "done": END},
    )
    graph.add_edge("fix_allocation", "check_compliance")

    return graph.compile()


def _equity_cap(years: int):
    if years < 3:
        return 30.0
    elif years < 5:
        return 50.0
    return None
