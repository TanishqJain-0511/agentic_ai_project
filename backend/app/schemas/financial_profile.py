from pydantic import BaseModel, Field
from datetime import datetime

class FinancialProfileBase(BaseModel):
    annual_income: float = Field(..., ge=0, description="Annual income in INR")
    monthly_expenses: float = Field(..., ge=0, description="Monthly expenses in INR")
    total_cash_savings: float = Field(..., ge=0, description="Total cash savings in INR")
    total_existing_investments: float = Field(..., ge=0, description="Total existing investments in INR")
    total_debt: float = Field(..., ge=0, description="Total outstanding debt in INR")

class FinancialProfileCreate(FinancialProfileBase):
    user_id: int

class FinancialProfileResponse(FinancialProfileBase):
    id: int
    user_id: int
    created_at: datetime
    modified_at: datetime

    class Config:
        from_attributes = True