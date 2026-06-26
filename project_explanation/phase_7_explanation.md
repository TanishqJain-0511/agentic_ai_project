# Phase 7 — Fund Research Agent: Full Deep Dive

---

## What is this phase doing conceptually?

Phases 1–6 were all **deterministic** — math and rules. You give inputs, you get outputs. No intelligence.

Phase 7 introduces the **first real AI agent**: given a portfolio allocation (e.g. 60% equity, 30% debt, 10% gold) 
and a risk tier, the LLM autonomously decides which tools to call, in what order, 
how many times — to find actual mutual funds from your database. 
This is **agentic behavior** — the LLM controls its own execution loop.

---

## The 3-file architecture

```
Request (POST /mutual-fund-research)
        ↓
main.py  →  mutual_fund_research_service.py  →  mutual_fund_research_agent.py
              (builds the prompt)                 (LangGraph + Ollama + Tools)
```

---

## LangGraph — Detailed Explanation

### What is LangGraph?

LangGraph is a library built on top of LangChain for building **stateful, multi-step agents** as directed graphs. 
Think of it as a state machine where:

- **Nodes** = units of work (call the LLM, execute tools, run logic)
- **Edges** = connections between nodes (always go here, or conditionally go here)
- **State** = a shared data object that every node can read from and write to

It solves a core problem with simple LLM chains: chains are linear (A → B → C). 
Agents need loops — the LLM calls a tool, reads the result, decides to call another tool, reads that result, and so on. 
LangGraph handles this loop natively.

### Core concepts

#### 1. State

```python
class AgentState(TypedDict):
    messages: Annotated[List[BaseMessage], operator.add]
```

State is the "memory" of the graph. Every node receives the current state and returns an update to it.

`TypedDict` makes it a typed dictionary — so `state["messages"]` is type-checked.

`Annotated[List[BaseMessage], operator.add]` is the key part:
- `List[BaseMessage]` — the type of the field
- `operator.add` — the **reducer** function: tells LangGraph how to merge updates

When a node returns `{"messages": [new_message]}`, LangGraph doesn't replace the whole list 
— it calls `operator.add(existing_list, [new_message])` which is list concatenation. 
So messages always accumulate, never get overwritten.

If you used `operator.add` on integers it would be normal addition. For lists it's concatenation. 
This is how LangGraph handles different merge strategies per field.

#### 2. StateGraph

```python
graph = StateGraph(AgentState)
```

`StateGraph` is the graph builder. You pass it the state schema so it knows what fields exist and how to merge them.

#### 3. Nodes

```python
graph.add_node("agent", agent_node)
graph.add_node("tools", tool_node)
```

A node is any callable that receives `state` and returns a dict of updates. The key is the node name — used when adding edges.

Your two nodes:
- `"agent"` — calls the LLM. Reads full message history, returns LLM's response.
- `"tools"` — executes any tool calls in the last message. Returns tool results as ToolMessages.

#### 4. Entry point

```python
graph.set_entry_point("agent")
```

Which node runs first when `graph.invoke(initial_state)` is called. Always the `"agent"` node here.

#### 5. Edges — Static

```python
graph.add_edge("tools", "agent")
```

After `"tools"` runs, always go to `"agent"`. No condition — always. This is the return path of the loop.

#### 6. Edges — Conditional

```python
graph.add_conditional_edges("agent", should_continue)
```

After `"agent"` runs, call `should_continue(state)`. Its return value is a string node name (or `END`) that determines where to go.

```python
def should_continue(state: AgentState) -> str:
    last = state["messages"][-1]
    if getattr(last, "tool_calls", None):
        return "tools"
    return END
```

- If the LLM returned tool calls → go to `"tools"` node
- If the LLM returned plain text (final answer) → `END` (stop the graph)

`END` is a special string constant from LangGraph that terminates execution.

#### 7. Compiling

```python
return graph.compile()
```

Validates the graph (checks for unreachable nodes, missing entry points, etc.) and returns a `CompiledGraph` 
— a runnable object with `.invoke()`, `.stream()`, and `.astream()` methods.

### The execution loop visualised

```
graph.invoke({"messages": [SystemMessage, HumanMessage]})
        │
        ▼
  ┌─── agent_node ──────────────────────────────────────────────┐
  │    Sends full message history to LLM                        │
  │    LLM responds with AIMessage                              │
  │      Case A: AIMessage has tool_calls → [search_funds(...)] │
  │      Case B: AIMessage has plain text → "My recommendation" │
  └─────────────────────────────────────────────────────────────┘
        │
        ▼
  should_continue(state)
        │
        ├── tool_calls present? ──► tools node
        │                               │
        │    ToolNode reads tool_calls  │
        │    Executes each function     │
        │    Wraps results as           │
        │    ToolMessage objects        │
        │    Returns to state           │
        │                               │
        │         ◄─────────────────────┘
        │         (loop back to agent)
        │
        └── no tool_calls? ──► END
                                │
                          Return final state
```

### Message types in LangChain

Every item in `state["messages"]` is a subclass of `BaseMessage`:

| Type            | Created by | Contains                                                                          |
|-----------------|------------|-----------------------------------------------------------------------------------|
| `SystemMessage` | You        | Instructions/persona for the LLM                                                  |
| `HumanMessage`  | You        | The user's request                                                                |
| `AIMessage`     | LLM        | LLM's response — either `content` (text) or `tool_calls` (list of function calls) |
| `ToolMessage`   | ToolNode   | Result of a tool execution, linked to its `tool_call_id`                          |

The LLM sees the full message history on every call — this is its "working memory" for the current task.

### ToolNode — What it does internally

```python
tool_node = ToolNode(tools)
```

`ToolNode` is LangGraph's prebuilt tool executor. When it receives state where the last message has `tool_calls`, it:

1. Reads `last_message.tool_calls` — a list like 
`[{"name": "search_funds_by_category", "args": {"category": "Large Cap"}, "id": "call_abc123"}]`
2. Looks up the tool by name in the provided `tools` list
3. Calls `tool_function(**args)`
4. Wraps the return value in a `ToolMessage(content=result, tool_call_id="call_abc123")`
5. Returns `{"messages": [ToolMessage, ToolMessage, ...]}` — one per tool call

The `tool_call_id` links each result back to the specific call that generated it — 
the LLM uses this to correlate results when multiple tools are called in parallel.

### bind_tools — How the LLM knows about tools

```python
llm_with_tools = llm.bind_tools(tools)
```

`bind_tools` serialises each tool's schema into a format Ollama understands:

```json
{
  "name": "search_funds_by_category",
  "description": "Search mutual funds in the database by category. Valid categories: ...",
  "parameters": {
    "type": "object",
    "properties": {
      "category": {"type": "string"}
    },
    "required": ["category"]
  }
}
```

This schema is prepended to every LLM call. 
The model reads it and decides whether to call a tool (returns structured JSON in `tool_calls`) or write a final 
answer (returns plain text in `content`). The model never actually executes the tool — it just says 
"call this function with these args" and LangGraph does the rest.

### The @tool decorator

```python
@tool
def search_funds_by_category(category: str) -> str:
    """Search mutual funds in the database by category.
    Valid categories: Large Cap, Mid Cap, Small Cap..."""
```

`@tool` does three things:
1. **Name**: uses the function name (`search_funds_by_category`)
2. **Description**: uses the docstring — this is what the LLM reads to understand when to use the tool
3. **Schema**: introspects the function signature (`category: str`) to generate the JSON schema

The docstring is critical — it's not just documentation, it's a **prompt to the LLM**. 
"Use this first before broadening the search" is an instruction the LLM follows at runtime.

### Closures — why tools are defined inside the factory

```python
def create_mutual_fund_research_agent(db: Session):
    @tool
    def search_funds_by_category(category: str) -> str:
        funds = db.query(MutualFund)...   # 'db' captured from outer scope
```

The tools are defined *inside* `create_mutual_fund_research_agent` so they **close over** the `db` variable. 
This means each tool carries a reference to the specific session from the HTTP request that created it.

Why not use a global session? SQLAlchemy sessions are not thread-safe. 
If two requests share a session, you get race conditions. By creating a fresh agent (and fresh tool closures) per 
request, each request gets its own isolated session. When the request ends, `get_db()` closes the session cleanly.

---

## File 1: `mutual_fund_research_agent.py` — Line by Line

### Imports

```python
import operator
```
Python's built-in `operator` module. Used for `operator.add` — the list concatenation function `(a, b) -> a + b`. 
This is how LangGraph merges new messages into the state.

```python
from typing import Annotated, List
```
- `List` — for type hints (`List[BaseMessage]`)
- `Annotated` — attaches metadata to a type. Here it attaches `operator.add` as the reducer for the `messages` field.

```python
from langchain_core.messages import BaseMessage
```
Base class for all LangChain message types: `HumanMessage`, `AIMessage`, `ToolMessage`, `SystemMessage`. The state stores a list of these.

```python
from langchain_core.tools import tool
```
Decorator that converts a plain Python function into a LangChain tool — adds name, description (from docstring), and input schema (from type hints).

```python
from langchain_ollama import ChatOllama
```
LangChain's wrapper for Ollama. Handles HTTP calls to `ollama serve`. Makes Ollama behave like any other LangChain chat model.

```python
from langgraph.graph import END, StateGraph
```
- `StateGraph` — the graph builder class
- `END` — sentinel string meaning "stop the graph"

```python
from langgraph.prebuilt import ToolNode
```
Prebuilt node that reads `tool_calls` from the last AI message, executes each tool, and returns results as `ToolMessage` objects.

```python
from sqlalchemy.orm import Session
```
SQLAlchemy session type — used for type hinting only.

```python
from typing import TypedDict
```
Python's typed dictionary base — lets you define dict shapes with type checking.

```python
from backend.app.config import settings
from backend.app.models.mutual_fund import MutualFund
```
Your app config (for `OLLAMA_HOST`) and the ORM model for querying funds.

### Agent State

```python
class AgentState(TypedDict):
    messages: Annotated[List[BaseMessage], operator.add]
```

The shared memory object passed between every node. Has one field: `messages` — a growing list of all messages in the conversation.

`Annotated[List[BaseMessage], operator.add]` tells LangGraph: when a node returns `{"messages": [new_msg]}`, 
append it to the existing list (don't replace it). This is what makes the conversation history accumulate correctly.

State evolution over one full run:
```
Initial:  [SystemMessage, HumanMessage]
Round 1:  [SystemMessage, HumanMessage, AIMessage(tool_calls=[search_funds...])]
Round 2:  [..., ToolMessage("100001: Axis Bluechip...")]
Round 3:  [..., AIMessage(tool_calls=[get_fund_details("100001")])]
Round 4:  [..., ToolMessage("Name: Axis Bluechip\nCategory: Large Cap...")]
Round 5:  [..., AIMessage("For your Safer profile, I recommend: Axis Bluechip...")]
```

### Factory Function

```python
def create_mutual_fund_research_agent(db: Session):
```

Takes a DB session, returns a compiled LangGraph. Called once per HTTP request. 
Tools are defined inside it so they capture `db` in their closures.

### Tool 1: search_funds_by_category

```python
@tool
def search_funds_by_category(category: str) -> str:
    """Search mutual funds in the database by category.
    Valid categories: Large Cap, Mid Cap, Small Cap, Flexi Cap, Index, Gilt, Gold, Hybrid.
    Use this first before broadening the search."""
```

`@tool` converts this to a LangChain tool. The docstring is the LLM's instruction — 
"Use this first" tells the model the preferred order of tool usage.

```python
    funds = db.query(MutualFund).filter(MutualFund.category == category).all()
```
Standard SQLAlchemy: `SELECT * FROM mutual_funds WHERE category = ?`

```python
    if not funds:
        return f"No funds found for category '{category}'. Try search_funds_by_risk_grade instead."
```
The return value becomes a `ToolMessage` the LLM reads. 
"Try search_funds_by_risk_grade instead" is **prompt engineering inside the tool** — 
it tells the LLM exactly what to do next when this tool finds nothing.

```python
    lines = [
        f"{f.scheme_code}: {f.scheme_name} | Expense: {f.expense_ratio}% | NAV: ₹{f.nav}"
        for f in funds
    ]
    return "\n".join(lines)
```
Formats results compactly. Scheme codes are included so the LLM can pass them to `get_fund_details` in the next step.

### Tool 2: search_funds_by_risk_grade

The fallback tool. Used when a category search returns nothing. The docstring says 
"Broaden the search when category returns no results" — explicitly marking it as a fallback so the LLM doesn't use it first.

### Tool 3: get_fund_details

```python
@tool
def get_fund_details(scheme_code: str) -> str:
    """Get full details for a specific fund by its scheme code.
    Use this to verify a fund before recommending it."""
```

The verification step. After finding candidate scheme codes from search tools, 
the LLM calls this to get full details before finalising recommendations.
"Verify before recommending" in the docstring enforces this pattern.

```python
    fund = db.query(MutualFund).filter(MutualFund.scheme_code == scheme_code).first()
```
`.first()` instead of `.all()` — scheme codes are unique, we only need one row.

### Wiring Tools to LLM

```python
tools = [search_funds_by_category, search_funds_by_risk_grade, get_fund_details]
tool_node = ToolNode(tools)
```
`ToolNode` wraps all 3 tools. When the LLM calls any of them, `ToolNode` dispatches to the right function and returns results.

```python
llm = ChatOllama(model="llama3.2:3b", base_url=settings.OLLAMA_HOST)
llm_with_tools = llm.bind_tools(tools)
```
- `ChatOllama` connects to local Ollama
- `.bind_tools(tools)` serialises tool schemas and attaches them to every LLM call

### Agent Node

```python
def agent_node(state: AgentState) -> dict:
    response = llm_with_tools.invoke(state["messages"])
    return {"messages": [response]}
```

The "think" step. Sends full message history to Ollama. 
Gets back an `AIMessage` with either `tool_calls` (wants to call a tool) or plain text (final answer). 
Returns it — LangGraph appends it to state via `operator.add`.

### Router Function

```python
def should_continue(state: AgentState) -> str:
    last = state["messages"][-1]
    if getattr(last, "tool_calls", None):
        return "tools"
    return END
```

Decision logic after `agent_node`. Checks the last message:
- Has `tool_calls` → LLM wants to use a tool → route to `"tools"`
- No `tool_calls` → LLM wrote a final answer → `END`

`getattr(last, "tool_calls", None)` — safe attribute access. Plain text `AIMessage` objects don't have `tool_calls`, so this returns `None` for them.

### Building and Compiling the Graph

```python
graph = StateGraph(AgentState)
graph.add_node("agent", agent_node)
graph.add_node("tools", tool_node)
graph.set_entry_point("agent")
graph.add_conditional_edges("agent", should_continue)
graph.add_edge("tools", "agent")
return graph.compile()
```

| Line                                              | What it does                                         |
|---------------------------------------------------|------------------------------------------------------|
| `StateGraph(AgentState)`                          | Creates graph with state schema                      |
| `add_node("agent", agent_node)`                   | Registers the LLM-calling node                       |
| `add_node("tools", tool_node)`                    | Registers the tool-executing node                    |
| `set_entry_point("agent")`                        | Graph always starts at agent                         |
| `add_conditional_edges("agent", should_continue)` | After agent: route based on should_continue's return |
| `add_edge("tools", "agent")`                      | After tools: always return to agent                  |
| `graph.compile()`                                 | Validate + return runnable graph                     |

---

## File 2: `mutual_fund_research_service.py` — Line by Line

### System Prompt

```python
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
3. Use get_fund_details on all the candidate funds to verify before recommending.
4. Prefer funds with lower expense ratios when selecting between similar options.
5. Recommend exactly top 2 funds per asset class.
6. End with a clear summary listing recommended scheme codes and names. And why they were chosen"""
```

Module-level constant — loaded once at import time, not recreated per request.

The system prompt gives the LLM:
- **Persona**: "mutual fund research agent for Indian retail investors"
- **Search strategy**: maps risk tier + asset class to the right category. Encodes domain knowledge so the LLM doesn't guess.
- **Numbered rules**: explicit constraints on behavior (use category first, verify before recommending, prefer lower expense ratios, end with a summary).

This goes in as a `SystemMessage` — the LLM treats it as the highest-priority instruction framing the whole conversation.

### run_mutual_fund_research

```python
agent = create_mutual_fund_research_agent(db)
```
Calls the factory — creates a fresh compiled graph with the DB session captured in tool closures.

```python
user_message = (
    f"Find mutual funds for this portfolio allocation:\n"
    f"  Equity: {data.equity_pct}%\n"
    f"  Debt:   {data.debt_pct}%\n"
    f"  Gold:   {data.gold_pct}%\n"
    f"  Risk Tier: {data.risk_tier}\n\n"
    f"Search funds for each asset class. Broaden if needed. "
    f"End with your final recommendations."
)
```
The human turn. Gives the LLM the allocation numbers from Phase 5's output. The LLM reads this, 
consults the system prompt's search strategy, and starts calling tools.

```python
result = agent.invoke({
    "messages": [
        SystemMessage(content=_SYSTEM_PROMPT),
        HumanMessage(content=user_message),
    ]
})
```
Starts the graph with initial state of 2 messages. The graph runs its agent/tools loop until `END`. Returns the final state dict.

```python
"agent_response": result["messages"][-1].content,
```
The last message in the final state is always the LLM's concluding `AIMessage`. `.content` extracts the plain text recommendation string.

```python
except Exception as e:
    error_str = str(e).lower()
    if "connection" in error_str or "refused" in error_str or "connect" in error_str:
        status = "ollama_unavailable"
```
Graceful degradation. If Ollama isn't running, returns a clean JSON with `status: "ollama_unavailable"` instead of a 500 error. The API stays usable even without Ollama.

---

## File 3: `schemas/mutual_fund_research.py`

```python
class MutualFundResearchRequest(BaseModel):
    user_id: int
    equity_pct: float
    debt_pct: float
    gold_pct: float
    risk_tier: str    # Safest | Safer | Riskier | Riskiest
```

What you POST to `/mutual-fund-research`. The numbers come directly from Phase 5's (Allocation Engine) output — this is the natural chaining between phases.

```python
class MutualFundResearchResponse(BaseModel):
    ...
    agent_response: str   # The LLM's full text recommendation
    status: str           # success | ollama_unavailable | error
```

`agent_response` is unstructured text from the LLM. Phase 12 (Explanation Generator) will structure and refine this for the frontend.

---

## End-to-end request flow

```
POST /mutual-fund-research
Body: { equity_pct: 60, debt_pct: 30, gold_pct: 10, risk_tier: "Safer" }
           │
           ▼
main.py → run_mutual_fund_research(db, data)
           │
           ├─ creates agent (graph with DB session)
           ├─ builds SystemMessage + HumanMessage
           └─ agent.invoke(initial_state)
                    │
                    ▼
           ROUND 1: agent_node
           LLM: "I need Large Cap funds for equity (Safer tier)"
           → AIMessage(tool_calls=[search_funds_by_category("Large Cap")])
                    │
           should_continue → "tools"
                    │
                    ▼
           ROUND 1: tool_node
           Executes search_funds_by_category("Large Cap")
           → ToolMessage("100001: Axis Bluechip | Expense: 0.54% | NAV: ₹42.3")
                    │
           always → "agent"
                    │
                    ▼
           ROUND 2: agent_node
           LLM: "Let me verify Axis Bluechip before recommending"
           → AIMessage(tool_calls=[get_fund_details("100001")])
                    │
           should_continue → "tools"
                    │
                    ▼
           ROUND 2: tool_node
           Executes get_fund_details("100001")
           → ToolMessage("Name: Axis Bluechip\nCategory: Large Cap\nExpense: 0.54%...")
                    │
           always → "agent"
                    │
                    ▼
           ROUND 3: agent_node
           LLM: "I have enough info, writing final recommendation"
           → AIMessage("For your Safer profile:\nEquity: Axis Bluechip (100001)...")
                    │
           should_continue → END
                    │
                    ▼
           Final state returned
           service extracts result["messages"][-1].content
           returns MutualFundResearchResponse(agent_response=..., status="success")
```