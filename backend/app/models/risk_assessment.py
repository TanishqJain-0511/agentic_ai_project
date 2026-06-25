from sqlalchemy import JSON, Column, Integer, DateTime, String, ForeignKey, func
from sqlalchemy.orm import relationship
from backend.app.db.database import Base


class RiskAssessment(Base):

    __tablename__ = "risk_assessments"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, unique=True)
    questionnaire_answers = Column(JSON, nullable=False) # dict of questions as key and answers as value
    risk_score = Column(Integer, nullable=True)
    risk_tier = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=func.now())
    modified_at = Column(DateTime(timezone=True), nullable=False, default=func.now(),onupdate=func.now())

    user = relationship(
        "User",
        back_populates="risk_assessment"
    )