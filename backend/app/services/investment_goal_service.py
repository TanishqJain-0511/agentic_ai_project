from sqlalchemy.orm import Session
from backend.app.models.investment_goal import InvestmentGoal
from backend.app.schemas.investment_goal import InvestmentGoalCreate


def create_investment_goal(db: Session, goal_data: InvestmentGoalCreate):
    new_goal = InvestmentGoal(**goal_data.model_dump())
    db.add(new_goal)
    db.commit()
    db.refresh(new_goal)
    return new_goal


def get_investment_goals_by_user_id(db: Session, user_id: int):
    return (
        db.query(InvestmentGoal)
        .filter(InvestmentGoal.user_id == user_id)
        .all()
    )


def get_investment_goal_by_id(db: Session, goal_id: int):
    return (
        db.query(InvestmentGoal)
        .filter(InvestmentGoal.id == goal_id)
        .first()
    )