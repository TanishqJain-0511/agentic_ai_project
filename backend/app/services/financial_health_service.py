from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.services.financial_profile_service import get_financial_profile_by_user_id


async def compute_financial_health(db: AsyncSession, user_id: int):
    profile = await get_financial_profile_by_user_id(db, user_id)
    if not profile:
        return None

    monthly_income = profile.annual_income / 12
    monthly_surplus = monthly_income - profile.monthly_expenses

    net_worth = (
        profile.total_cash_savings
        + profile.total_existing_investments
        - profile.total_debt
    )

    savings_rate = (monthly_surplus / monthly_income * 100) if monthly_income > 0 else 0.0
    debt_to_income_ratio = (
        profile.total_debt / profile.annual_income * 100
    ) if profile.annual_income > 0 else 0.0
    emergency_fund_months = (
        profile.total_cash_savings / profile.monthly_expenses
        if profile.monthly_expenses > 0
        else 0.0
    )

    return {
        "user_id": user_id,
        "net_worth": round(net_worth, 2),
        "monthly_surplus": round(monthly_surplus, 2),
        "savings_rate": round(savings_rate, 2),
        "debt_to_income_ratio": round(debt_to_income_ratio, 2),
        "emergency_fund_months": round(emergency_fund_months, 2),
        "savings_rate_status": _savings_rate_status(savings_rate),
        "debt_to_income_status": _dti_status(debt_to_income_ratio),
        "emergency_fund_status": _emergency_fund_status(emergency_fund_months),
    }


def _savings_rate_status(rate: float) -> str:
    if rate >= 20:
        return "high"
    elif rate >= 10:
        return "normal"
    return "low"


def _dti_status(dti: float) -> str:
    if dti < 36:
        return "healthy"
    elif dti <= 50:
        return "normal"
    return "unhealthy"


def _emergency_fund_status(months: float) -> str:
    if months >= 6:
        return "adequate"
    elif months >= 3:
        return "low"
    return "critical"
