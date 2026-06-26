from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.services.risk_assessment_service import get_risk_assessment_by_user_id
from backend.app.schemas.allocation import AllocationRequest

_TIER_ALLOCATIONS = {
    "Safest":   {"equity": 20.0, "debt": 75.0, "gold": 5.0},
    "Safer":    {"equity": 40.0, "debt": 55.0, "gold": 5.0},
    "Riskier":  {"equity": 65.0, "debt": 25.0, "gold": 10.0},
    "Riskiest": {"equity": 85.0, "debt":  5.0, "gold": 10.0},
}


async def compute_allocation(db: AsyncSession, data: AllocationRequest) -> dict:
    assessment = await get_risk_assessment_by_user_id(db, data.user_id)
    risk_tier = (
        assessment.risk_tier
        if assessment and assessment.risk_tier
        else "Safer"
    )

    base = _TIER_ALLOCATIONS[risk_tier].copy()
    equity = base["equity"]
    debt = base["debt"]
    gold = base["gold"]

    horizon_capped = False
    cap = _equity_cap(data.goal_horizon_years)
    if cap is not None and equity > cap:
        excess = equity - cap
        equity = cap
        debt = debt + excess
        horizon_capped = True

    return {
        "user_id": data.user_id,
        "risk_tier": risk_tier,
        "goal_horizon_years": data.goal_horizon_years,
        "equity_pct": equity,
        "debt_pct": debt,
        "gold_pct": gold,
        "horizon_capped": horizon_capped,
    }


def _equity_cap(years: int):
    if years < 3:
        return 30.0
    elif years < 5:
        return 50.0
    return None
