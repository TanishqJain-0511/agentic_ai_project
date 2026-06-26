"""
Explanation Generator — Phase 12

Takes all computed verdicts (risk score, allocation, compliance, simulation)
and narrates them in plain English using Ollama (llama3.2:3b).

Philosophy: "LLM explains, rules decide."
The LLM never changes any numbers — it only puts already-computed verdicts
into language that an Indian retail investor can understand.
"""

from langchain_ollama import ChatOllama
from langchain_core.messages import HumanMessage, SystemMessage

from backend.app.config import settings
from backend.app.schemas.explanation import ExplanationRequest, ExplanationResponse

_SYSTEM_PROMPT = """You are a friendly, knowledgeable Indian wealth advisor.
Your job is to explain a pre-computed investment recommendation in plain English.

Rules:
- Keep the explanation to 4–6 sentences.
- Never change or question the numbers — they are computed by trusted financial rules.
- Use simple language suitable for a first-time Indian mutual fund investor.
- Mention rupee amounts in lakhs or crores where appropriate.
- Do not use jargon. Do not give generic disclaimers.
- End with one actionable takeaway."""


def _build_user_prompt(data: ExplanationRequest) -> str:
    lines = [
        f"Risk Profile: {data.risk_tier} (score {data.risk_score}/100)",
        f"Recommended Allocation: {data.equity_pct}% Equity, {data.debt_pct}% Debt, {data.gold_pct}% Gold",
        f"Investment Horizon: {data.goal_horizon_years} years",
    ]

    if data.horizon_capped:
        lines.append(
            "Note: Equity was reduced from the base allocation because the goal horizon is short — "
            "this protects against market volatility near the goal date."
        )

    if data.user_age is not None:
        lines.append(f"Investor Age: {data.user_age}")

    if data.goal_target_amount is not None:
        lines.append(f"Goal Target: ₹{data.goal_target_amount:,.0f}")

    if data.monthly_sip is not None:
        lines.append(f"Monthly SIP: ₹{data.monthly_sip:,.0f}")

    if data.simulation_success_probability is not None:
        lines.append(
            f"Monte Carlo Simulation: {data.simulation_success_probability:.1f}% probability of "
            f"reaching the goal in {data.goal_horizon_years} years."
        )

    if data.compliance_passed is not None:
        status = "PASSED" if data.compliance_passed else "FAILED"
        lines.append(f"Compliance Check: {status}")
        if data.compliance_violations:
            lines.append(f"Violations resolved: {'; '.join(data.compliance_violations)}")

    lines.append(
        "\nPlease explain this recommendation to the investor in plain English."
    )
    return "\n".join(lines)


async def generate_explanation(data: ExplanationRequest) -> ExplanationResponse:
    try:
        llm = ChatOllama(model="llama3.2:3b", base_url=settings.OLLAMA_HOST)
        user_prompt = _build_user_prompt(data)

        response = await llm.ainvoke([
            SystemMessage(content=_SYSTEM_PROMPT),
            HumanMessage(content=user_prompt),
        ])

        return ExplanationResponse(
            explanation=response.content.strip(),
            status="success",
        )

    except Exception as e:
        error_str = str(e).lower()
        if "connection" in error_str or "refused" in error_str or "connect" in error_str:
            return ExplanationResponse(
                explanation=(
                    "Ollama is not running. Start it with: "
                    "ollama serve && ollama pull llama3.2:3b"
                ),
                status="ollama_unavailable",
            )
        return ExplanationResponse(
            explanation=f"Explanation unavailable: {e}",
            status="error",
        )
