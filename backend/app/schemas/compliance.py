from typing import List
from pydantic import BaseModel, Field


class ComplianceRequest(BaseModel):
    user_id: int
    goal_horizon_years: int = Field(..., ge=1)


class AllocationSnapshot(BaseModel):
    equity_pct: float
    debt_pct: float
    gold_pct: float
    risk_tier: str
    violations: List[str]
    passed: bool


class ComplianceResponse(BaseModel):
    user_id: int
    goal_horizon_years: int
    final_allocation: AllocationSnapshot
    iterations: int
    converged: bool   # False if hit MAX_ITERATIONS without a passing allocation
