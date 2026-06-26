import operator
from typing import Annotated, List

from langchain_core.messages import BaseMessage
from langchain_core.tools import tool
from langchain_ollama import ChatOllama
from langgraph.graph import END, StateGraph
from langgraph.prebuilt import ToolNode
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from typing import TypedDict

from backend.app.config import settings
from backend.app.models.mutual_fund import MutualFund


class AgentState(TypedDict):
    messages: Annotated[List[BaseMessage], operator.add]


def create_mutual_fund_research_agent(db: AsyncSession):
    """
    Factory that returns a compiled LangGraph agent bound to the given DB session.
    Tools are async closures capturing the session.
    """

    @tool
    async def search_funds_by_category(category: str) -> str:
        """Search mutual funds in the database by category.
        Valid categories: Large Cap, Mid Cap, Small Cap, Flexi Cap, Index, Gilt, Gold, Hybrid.
        Use this first before broadening the search."""
        result = await db.execute(
            select(MutualFund).where(MutualFund.category == category)
        )
        funds = result.scalars().all()
        if not funds:
            return f"No funds found for category '{category}'. Try search_funds_by_risk_grade instead."
        lines = [
            f"{f.scheme_code}: {f.scheme_name} | Expense: {f.expense_ratio}% | NAV: ₹{f.net_asset_value}"
            for f in funds
        ]
        return "\n".join(lines)

    @tool
    async def search_funds_by_risk_grade(risk_grade: str) -> str:
        """Broaden the search when category returns no results. Search by risk grade.
        Valid risk grades: Low, Moderate, High, Very High."""
        result = await db.execute(
            select(MutualFund).where(MutualFund.risk_grade == risk_grade)
        )
        funds = result.scalars().all()
        if not funds:
            return f"No funds found for risk grade '{risk_grade}'."
        lines = [
            f"{f.scheme_code}: {f.scheme_name} | Category: {f.category} | Expense: {f.expense_ratio}%"
            for f in funds
        ]
        return "\n".join(lines)

    @tool
    async def get_fund_details(scheme_code: str) -> str:
        """Get full details for a specific fund by its scheme code.
        Use this to verify a fund before recommending it."""
        result = await db.execute(
            select(MutualFund).where(MutualFund.scheme_code == scheme_code)
        )
        fund = result.scalar_one_or_none()
        if not fund:
            return f"Fund '{scheme_code}' not found in database."
        return (
            f"Name: {fund.scheme_name}\n"
            f"Category: {fund.category}\n"
            f"Risk Grade: {fund.risk_grade}\n"
            f"NAV: ₹{fund.net_asset_value} (as of {fund.nav_date})\n"
            f"Expense Ratio: {fund.expense_ratio}%\n"
            f"AUM: ₹{fund.aum_in_crores} Cr"
        )

    tools = [search_funds_by_category, search_funds_by_risk_grade, get_fund_details]
    tool_node = ToolNode(tools)

    llm = ChatOllama(model="llama3.2:3b", base_url=settings.OLLAMA_HOST)
    llm_with_tools = llm.bind_tools(tools)

    async def agent_node(state: AgentState) -> dict:
        response = await llm_with_tools.ainvoke(state["messages"])
        return {"messages": [response]}

    def should_continue(state: AgentState) -> str:
        last = state["messages"][-1]
        if getattr(last, "tool_calls", None):
            return "tools"
        return END

    graph = StateGraph(AgentState)
    graph.add_node("agent", agent_node)
    graph.add_node("tools", tool_node)
    graph.set_entry_point("agent")
    graph.add_edge("tools", "agent")
    graph.add_conditional_edges("agent", should_continue)

    return graph.compile()
