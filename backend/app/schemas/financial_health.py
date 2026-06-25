from pydantic import BaseModel


class FinancialHealthResponse(BaseModel):
    user_id: int
    net_worth: float              # cash_savings + existing_investments - total_debt
    monthly_surplus: float        # (annual_income / 12) - monthly_expenses
    savings_rate: float           # percentage: (monthly_surplus / monthly_income) * 100
    debt_to_income_ratio: float   # percentage: (total_debt / annual_income) * 100
    emergency_fund_months: float  # total_cash_savings / monthly_expenses
    savings_rate_status: str      # "high" | "normal" | "low"
    debt_to_income_status: str    # "healthy" | "normal" | "unhealthy"
    emergency_fund_status: str    # "adequate" | "low" | "critical"
