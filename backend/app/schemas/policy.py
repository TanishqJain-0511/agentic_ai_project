from typing import List
from pydantic import BaseModel, Field


class PolicyCheckRequest(BaseModel):
    equity_pct: float = Field(..., ge=0, le=100)
    debt_pct: float = Field(..., ge=0, le=100)
    gold_pct: float = Field(..., ge=0, le=100)
    risk_tier: str = Field(..., description="Safest | Safer | Riskier | Riskiest")
    goal_horizon_years: int = Field(..., ge=1)


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
