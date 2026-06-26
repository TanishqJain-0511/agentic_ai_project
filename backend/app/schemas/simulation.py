from pydantic import BaseModel, Field
from typing import Optional


class SimulationRequest(BaseModel):
    # Portfolio allocation
    equity_pct: float = Field(..., ge=0, le=100)
    debt_pct: float = Field(..., ge=0, le=100)
    gold_pct: float = Field(..., ge=0, le=100)

    # Investment parameters
    initial_investment: float = Field(..., ge=0, description="Lump-sum investment today (₹)")
    monthly_sip: float = Field(..., ge=0, description="Monthly SIP contribution (₹)")
    goal_target_amount: float = Field(..., gt=0, description="Target corpus at horizon (₹)")
    goal_horizon_years: int = Field(..., ge=1, le=50)

    # Simulation config
    n_simulations: int = Field(default=1000, ge=100, le=5000)

    # Optional user context (for logging/tracing)
    user_id: Optional[int] = None


class SimulationResponse(BaseModel):
    # Core result
    success_probability: float           # 0–100 %
    goal_target_amount: float

    # Percentile projections of final portfolio value
    p10_final_value: float
    p25_final_value: float
    p50_final_value: float               # median
    p75_final_value: float
    p90_final_value: float

    # Simulation metadata
    scenarios_run: int
    goal_horizon_years: int
    initial_investment: float
    monthly_sip: float

    # Asset class return assumptions used
    equity_annual_return_pct: float
    debt_annual_return_pct: float
    gold_annual_return_pct: float
