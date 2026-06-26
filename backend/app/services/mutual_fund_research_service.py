from langchain_core.messages import HumanMessage, SystemMessage
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.agents.mutual_fund_research_agent import create_mutual_fund_research_agent
from backend.app.schemas.mutual_fund_research import MutualFundResearchRequest

_SYSTEM_PROMPT = """You are a mutual fund research agent for Indian retail investors.
Find suitable mutual funds from the database for the given portfolio allocation.

Search strategy by asset class:
- Equity (Safest/Safer risk tier): search Large Cap, then Index
- Equity (Riskier risk tier): search Mid Cap, then Flexi Cap
- Equity (Riskiest risk tier): search Small Cap, then Mid Cap
- Debt: search Gilt
- Gold: search Gold

Rules:
1. Always start with search_funds_by_category for each asset class.
2. If a category returns no results, broaden using search_funds_by_risk_grade.
3. Use get_fund_details on 1-2 candidate funds to verify before recommending.
4. Prefer funds with lower expense ratios when selecting between similar options.
5. Recommend exactly 1-2 funds per asset class.
6. End with a clear summary listing recommended scheme codes and names."""


async def run_mutual_fund_research(db: AsyncSession, data: MutualFundResearchRequest) -> dict:
    try:
        agent = create_mutual_fund_research_agent(db)

        user_message = (
            f"Find mutual funds for this portfolio allocation:\n"
            f"  Equity: {data.equity_pct}%\n"
            f"  Debt:   {data.debt_pct}%\n"
            f"  Gold:   {data.gold_pct}%\n"
            f"  Risk Tier: {data.risk_tier}\n\n"
            f"Search funds for each asset class. Broaden if needed. "
            f"End with your final recommendations."
        )

        result = await agent.ainvoke({
            "messages": [
                SystemMessage(content=_SYSTEM_PROMPT),
                HumanMessage(content=user_message),
            ]
        })

        return {
            "user_id": data.user_id,
            "risk_tier": data.risk_tier,
            "equity_pct": data.equity_pct,
            "debt_pct": data.debt_pct,
            "gold_pct": data.gold_pct,
            "agent_response": result["messages"][-1].content,
            "status": "success",
        }

    except Exception as e:
        error_str = str(e).lower()
        if "connection" in error_str or "refused" in error_str or "connect" in error_str:
            msg = (
                "Ollama is not running. "
                "Start it with: ollama serve && ollama pull llama3.1"
            )
            status = "ollama_unavailable"
        else:
            msg = f"Agent error: {e}"
            status = "error"

        return {
            "user_id": data.user_id,
            "risk_tier": data.risk_tier,
            "equity_pct": data.equity_pct,
            "debt_pct": data.debt_pct,
            "gold_pct": data.gold_pct,
            "agent_response": msg,
            "status": status,
        }
