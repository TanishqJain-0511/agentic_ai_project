from sqlalchemy import Column, Integer, DateTime, String, ForeignKey, func, Float, Date
from backend.app.db.database import Base
from sqlalchemy.orm import relationship


class InvestmentGoal(Base):

    __tablename__ = "investment_goals"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    goal_name = Column(String, nullable=False)
    target_amount = Column(Float, nullable=False)
    target_date = Column(Date, nullable=False)
    goal_priority = Column(Integer, nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=func.now())
    modified_at = Column(DateTime(timezone=True), nullable=False, default=func.now(), onupdate=func.now())

    user = relationship(
        "User",
        back_populates="investment_goals"
    )