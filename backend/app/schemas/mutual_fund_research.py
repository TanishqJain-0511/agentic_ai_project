from pydantic import BaseModel


class MutualFundResearchRequest(BaseModel):
    user_id: int
    equity_pct: float
    debt_pct: float
    gold_pct: float
    risk_tier: str    # Safest | Safer | Riskier | Riskiest


class MutualFundResearchResponse(BaseModel):
    user_id: int
    risk_tier: str
    equity_pct: float
    debt_pct: float
    gold_pct: float
    agent_response: str
    status: str       # success | ollama_unavailable | error
