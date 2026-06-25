from sqlalchemy.orm import Session
from backend.app.models.risk_assessment import RiskAssessment
from backend.app.schemas.risk_assessment import RiskAssessmentCreate


def create_risk_assessment(db: Session, data: RiskAssessmentCreate):
    new_assessment = RiskAssessment(**data.model_dump())
    db.add(new_assessment)
    db.commit()
    db.refresh(new_assessment)
    return new_assessment


def get_risk_assessment_by_user_id(db: Session, user_id: int):
    return (
        db.query(RiskAssessment)
        .filter(RiskAssessment.user_id == user_id)
        .first()
    )
