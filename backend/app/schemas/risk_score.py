from pydantic import BaseModel, Field
from typing import Dict


class RiskScoreRequest(BaseModel):
    user_id: int
    age: int = Field(..., ge=18, le=100)
    goal_horizon_years: int = Field(..., ge=1, description="Years until the primary goal")
    income_stability: str = Field(..., description="stable | semi_stable | variable")


class RiskScoreResponse(BaseModel):
    user_id: int
    risk_score: int          # 0-100
    risk_tier: str           # Safest | Safer | Riskier | Riskiest
    score_breakdown: Dict[str, int]
