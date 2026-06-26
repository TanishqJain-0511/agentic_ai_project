from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.agents.compliance_agent import create_compliance_agent
from backend.app.schemas.compliance import ComplianceRequest, ComplianceResponse, AllocationSnapshot


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

    violation_descriptions = [v["description"] for v in result["violations"]]

    return ComplianceResponse(
        user_id=data.user_id,
        goal_horizon_years=data.goal_horizon_years,
        final_allocation=AllocationSnapshot(
            equity_pct=result["equity_pct"],
            debt_pct=result["debt_pct"],
            gold_pct=result["gold_pct"],
            risk_tier=result["risk_tier"],
            violations=violation_descriptions,
            passed=result["passed"],
        ),
        iterations=result["iteration"],
        converged=result["passed"],
    )
