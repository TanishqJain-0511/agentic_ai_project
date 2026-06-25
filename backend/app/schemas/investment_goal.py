from pydantic import BaseModel, Field
from datetime import datetime, date


class InvestmentGoalBase(BaseModel):
    goal_name: str = Field(...,description="Name of the investment goal")
    target_amount: float = Field(...,ge=0,description="Target amount in INR")
    target_date: date = Field(...,description="Target date for achieving goal")
    goal_priority: int = Field(...,ge=1,description="Priority of the goal")


class InvestmentGoalCreate(InvestmentGoalBase):
    user_id: int


class InvestmentGoalResponse(InvestmentGoalBase):
    id: int
    user_id: int
    created_at: datetime
    modified_at: datetime

    class Config:
        from_attributes = True