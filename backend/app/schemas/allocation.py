from pydantic import BaseModel, Field


class AllocationRequest(BaseModel):
    user_id: int
    goal_horizon_years: int = Field(..., ge=1, description="Years until the primary goal")


class AllocationResponse(BaseModel):
    user_id: int
    risk_tier: str
    goal_horizon_years: int
    equity_pct: float
    debt_pct: float
    gold_pct: float
    horizon_capped: bool   # True if equity was reduced due to short goal horizon
