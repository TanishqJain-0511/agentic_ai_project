from sqlalchemy import Column, Integer, String
from sqlalchemy.orm import relationship
from backend.app.db.database import Base


class User(Base):

    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    email = Column(String, unique=True, nullable=False)

    financial_profile = relationship(
        "FinancialProfile",
        back_populates="user",
        uselist=False
    )

    investment_goals = relationship(
        "InvestmentGoal",
        back_populates="user"
    )

    risk_assessment = relationship(
        "RiskAssessment",
        back_populates="user",
        uselist=False,
    )