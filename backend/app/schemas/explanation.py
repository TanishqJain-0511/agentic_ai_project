from pydantic import BaseModel, Field
from typing import List, Optional


class ExplanationRequest(BaseModel):
    # Risk profile
    risk_tier: str = Field(..., description="Safest | Safer | Riskier | Riskiest")
    risk_score: int = Field(..., ge=0, le=100)

    # Portfolio allocation
    equity_pct: float
    debt_pct: float
    gold_pct: float

    # Goal context
    goal_horizon_years: int = Field(..., ge=1)
    horizon_capped: bool = Field(default=False)

    # Simulation result (optional)
    simulation_success_probability: Optional[float] = None   # 0–100 %
    goal_target_amount: Optional[float] = None
    monthly_sip: Optional[float] = None

    # Compliance result (optional)
    compliance_passed: Optional[bool] = None
    compliance_violations: Optional[List[str]] = None

    # User context (optional)
    user_id: Optional[int] = None
    user_age: Optional[int] = None


class ExplanationResponse(BaseModel):
    explanation: str
    status: str     # "success" | "ollama_unavailable" | "error"
