from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.models.risk_assessment import RiskAssessment
from backend.app.schemas.risk_assessment import RiskAssessmentCreate


async def create_risk_assessment(db: AsyncSession, data: RiskAssessmentCreate):
    new_assessment = RiskAssessment(**data.model_dump())
    db.add(new_assessment)
    await db.commit()
    await db.refresh(new_assessment)
    return new_assessment


async def get_risk_assessment_by_user_id(db: AsyncSession, user_id: int):
    result = await db.execute(
        select(RiskAssessment).where(RiskAssessment.user_id == user_id)
    )
    return result.scalar_one_or_none()
