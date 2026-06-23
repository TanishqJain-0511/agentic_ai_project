from sqlalchemy import Column, Integer, String, DateTime, Float, ForeignKey
from backend.app.db.database import Base

class User(Base):

    __tablename__ = "financial_profile"
    id = Column(Integer, primary_key=True, index=True)
    user_id = ForeignKey("users.id")
    annual_income = Column(Integer, nullable=False)
    monthly_expenses = Column(Integer, nullable=False)
    total_cash_savings = Column(Integer, nullable=False)
    total_existing_investments = Column(Integer, nullable=False)
    total_debt = Column(Integer, nullable=False)
    created_at = DateTime