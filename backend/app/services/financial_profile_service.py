from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.models.financial_profile import FinancialProfile
from backend.app.schemas.financial_profile import FinancialProfileCreate


async def create_financial_profile(db: AsyncSession, financial_profile_data: FinancialProfileCreate):
    new_profile = FinancialProfile(**financial_profile_data.model_dump())
    db.add(new_profile)
    await db.commit()
    await db.refresh(new_profile)
    return new_profile


async def get_all_financial_profile(db: AsyncSession):
    result = await db.execute(select(FinancialProfile))
    return result.scalars().all()


async def get_financial_profile_by_user_id(db: AsyncSession, user_id: int):
    result = await db.execute(
        select(FinancialProfile).where(FinancialProfile.user_id == user_id)
    )
    return result.scalar_one_or_none()
