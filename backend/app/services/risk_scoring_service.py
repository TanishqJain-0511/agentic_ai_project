from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.services.risk_assessment_service import get_risk_assessment_by_user_id
from backend.app.schemas.risk_score import RiskScoreRequest


async def compute_risk_score(db: AsyncSession, data: RiskScoreRequest) -> dict:
    age_score = _age_score(data.age)
    horizon_score = _horizon_score(data.goal_horizon_years)
    income_score = _income_score(data.income_stability)

    assessment = await get_risk_assessment_by_user_id(db, data.user_id)

    questionnaire_score = _questionnaire_score(
        assessment.questionnaire_answers if assessment else {}
    )

    total_score = age_score + horizon_score + income_score + questionnaire_score
    tier = _risk_tier(total_score)

    if assessment:
        assessment.risk_score = total_score
        assessment.risk_tier = tier
        await db.commit()
        await db.refresh(assessment)

    return {
        "user_id": data.user_id,
        "risk_score": total_score,
        "risk_tier": tier,
        "score_breakdown": {
            "age_score": age_score,
            "horizon_score": horizon_score,
            "income_score": income_score,
            "questionnaire_score": questionnaire_score,
        },
    }


def _age_score(age: int) -> int:
    if age < 30:
        return 30
    elif age < 40:
        return 25
    elif age < 50:
        return 20
    elif age < 60:
        return 10
    return 5


def _horizon_score(years: int) -> int:
    if years > 10:
        return 30
    elif years >= 7:
        return 25
    elif years >= 5:
        return 20
    elif years >= 3:
        return 10
    return 5


def _income_score(stability: str) -> int:
    return {"stable": 20, "semi_stable": 12, "variable": 6}.get(stability, 0)


def _questionnaire_score(answers: dict) -> int:
    SCORING = {
        "market_drop_reaction":   {"buy_more": 4, "hold": 2, "sell": 0},
        "investment_experience":  {"expert": 4, "intermediate": 2, "beginner": 0},
        "primary_goal":           {"wealth_growth": 4, "balanced": 2, "capital_preservation": 0},
        "loss_tolerance_percent": {">20": 4, "10-20": 2, "<10": 0},
        "investment_knowledge":   {"high": 4, "medium": 2, "low": 0},
    }
    total = 0
    for question, score_map in SCORING.items():
        total += score_map.get(answers.get(question), 0)
    return total


def _risk_tier(score: int) -> str:
    if score <= 25:
        return "Safest"
    elif score <= 50:
        return "Safer"
    elif score <= 75:
        return "Riskier"
    return "Riskiest"
