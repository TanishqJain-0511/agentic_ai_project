from pydantic import BaseModel
from datetime import datetime
from typing import Dict, Any, Optional, List, Literal


# All 5 questions must match SCORING keys in risk_scoring_service.py
QUESTIONNAIRE_QUESTIONS = [
    {
        "key": "market_drop_reaction",
        "text": "If your portfolio dropped 20% overnight, what would you do?",
        "options": [
            {"value": "buy_more", "label": "Buy more — this is a great opportunity"},
            {"value": "hold",     "label": "Hold — wait for it to recover"},
            {"value": "sell",     "label": "Sell — I can't afford to lose more"},
        ],
    },
    {
        "key": "investment_experience",
        "text": "How would you describe your investment experience?",
        "options": [
            {"value": "expert",       "label": "Expert — I actively manage a diversified portfolio"},
            {"value": "intermediate", "label": "Intermediate — I have invested in mutual funds or stocks"},
            {"value": "beginner",     "label": "Beginner — I am just starting out"},
        ],
    },
    {
        "key": "primary_goal",
        "text": "What is your primary investment goal?",
        "options": [
            {"value": "wealth_growth",        "label": "Grow my wealth aggressively"},
            {"value": "balanced",             "label": "Balance growth and safety"},
            {"value": "capital_preservation", "label": "Preserve my capital above all"},
        ],
    },
    {
        "key": "loss_tolerance_percent",
        "text": "What is the maximum portfolio loss you could tolerate in a single year?",
        "options": [
            {"value": ">20",   "label": "More than 20% — I can stomach big swings"},
            {"value": "10-20", "label": "10–20% — I can handle moderate losses"},
            {"value": "<10",   "label": "Less than 10% — I need to stay close to my principal"},
        ],
    },
    {
        "key": "investment_knowledge",
        "text": "How would you rate your knowledge of financial markets and investment products?",
        "options": [
            {"value": "high",   "label": "High — I understand equities, debt, derivatives, etc."},
            {"value": "medium", "label": "Medium — I know the basics of mutual funds and stocks"},
            {"value": "low",    "label": "Low — I am not very familiar with investments"},
        ],
    },
]


class QuestionOption(BaseModel):
    value: str
    label: str


class QuestionnaireQuestion(BaseModel):
    key: str
    text: str
    options: List[QuestionOption]


class QuestionsResponse(BaseModel):
    questions: List[QuestionnaireQuestion]


# Typed answers model — gives Swagger dropdowns for each field
class QuestionnaireAnswers(BaseModel):
    market_drop_reaction:   Literal["buy_more", "hold", "sell"]
    investment_experience:  Literal["expert", "intermediate", "beginner"]
    primary_goal:           Literal["wealth_growth", "balanced", "capital_preservation"]
    loss_tolerance_percent: Literal[">20", "10-20", "<10"]
    investment_knowledge:   Literal["high", "medium", "low"]


class RiskAssessmentCreate(BaseModel):
    user_id: int
    questionnaire_answers: QuestionnaireAnswers

    model_config = {
        "json_schema_extra": {
            "example": {
                "user_id": 1,
                "questionnaire_answers": {
                    "market_drop_reaction": "hold",
                    "investment_experience": "beginner",
                    "primary_goal": "balanced",
                    "loss_tolerance_percent": "10-20",
                    "investment_knowledge": "medium",
                },
            }
        }
    }


class RiskAssessmentResponse(BaseModel):
    id: int
    user_id: int
    questionnaire_answers: Dict[str, Any]
    risk_score: Optional[int] = None
    risk_tier: Optional[str] = None
    created_at: datetime
    modified_at: datetime

    class Config:
        from_attributes = True