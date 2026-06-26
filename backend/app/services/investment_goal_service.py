from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.models.investment_goal import InvestmentGoal
from backend.app.schemas.investment_goal import InvestmentGoalCreate


async def create_investment_goal(db: AsyncSession, goal_data: InvestmentGoalCreate):
    new_goal = InvestmentGoal(**goal_data.model_dump())
    db.add(new_goal)
    await db.commit()
    await db.refresh(new_goal)
    return new_goal


async def get_investment_goals_by_user_id(db: AsyncSession, user_id: int):
    result = await db.execute(
        select(InvestmentGoal).where(InvestmentGoal.user_id == user_id)
    )
    return result.scalars().all()


async def get_investment_goal_by_id(db: AsyncSession, goal_id: int):
    result = await db.execute(
        select(InvestmentGoal).where(InvestmentGoal.id == goal_id)
    )
    return result.scalar_one_or_none()
