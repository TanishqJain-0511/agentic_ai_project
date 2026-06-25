from sqlalchemy import Column, Integer, DateTime, Float, ForeignKey, func
from backend.app.db.database import Base
from sqlalchemy.orm import relationship


class FinancialProfile(Base):

    __tablename__ = "financial_profiles"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, unique=True)
    annual_income = Column(Float, nullable=False)
    monthly_expenses = Column(Float, nullable=False)
    total_cash_savings = Column(Float, nullable=False)
    total_existing_investments = Column(Float, nullable=False)
    total_debt = Column(Float, nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=func.now())
    modified_at = Column(DateTime(timezone=True), nullable=False, default=func.now(), onupdate=func.now())

    user = relationship(
        "User",
        back_populates="financial_profile"
    )