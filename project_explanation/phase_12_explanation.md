# Phase 12 — Explanation Generator: Full Deep Dive

---

## What is this phase doing conceptually?

This is where "LLM explains, rules decide" culminates. Every previous phase computed something deterministically:
- Phase 3: financial health numbers
- Phase 4: risk score and tier
- Phase 5/9: asset allocation percentages
- Phase 10: success probability

Phase 12 takes all these computed verdicts and asks the LLM to **narrate them** in plain English for a first-time Indian mutual fund investor.

The LLM doesn't compute, decide, or verify anything. It only translates already-correct structured data into natural language. If Ollama is unavailable, the numbers are still correct — only the plain-English explanation is missing. This is the right failure mode: degraded UX, not degraded financial accuracy.

---

## Architecture

```
POST /explain
Body: { risk_tier, risk_score, equity_pct, debt_pct, gold_pct,
        goal_horizon_years, horizon_capped, simulation_success_probability,
        compliance_passed, compliance_violations, ... }
         ↓
generate_explanation(data)
         │
         ├── _build_user_prompt(data) → structured text prompt
         ├── ChatOllama(model="llama3.2:3b")
         └── await llm.ainvoke([SystemMessage, HumanMessage])
                    ↓
         ExplanationResponse(explanation="...", status="success")
```

No graph. No tools. No loop. Just a single LLM call: SystemMessage + HumanMessage → plain text response.

---

## Concept 1: The System Prompt as Behavioural Constraints

```python
_SYSTEM_PROMPT = """You are a friendly, knowledgeable Indian wealth advisor.
Your job is to explain a pre-computed investment recommendation in plain English.

Rules:
- Keep the explanation to 4–6 sentences.
- Never change or question the numbers — they are computed by trusted financial rules.
- Use simple language suitable for a first-time Indian mutual fund investor.
- Mention rupee amounts in lakhs or crores where appropriate.
- Do not use jargon. Do not give generic disclaimers.
- End with one actionable takeaway."""
```

This is a module-level constant — loaded once, reused on every request.

**Every rule is a constraint on LLM behaviour**:

- `"4–6 sentences"` — prevents the LLM from writing a 2-page essay or a 1-sentence non-answer
- `"Never change or question the numbers"` — the most important rule. Without it, the LLM might say "this allocation seems aggressive, let me suggest..." — which would violate the "rules decide" philosophy
- `"Simple language"` — prevents jargon (alpha, beta, Sharpe ratio, duration risk)
- `"Mention rupee amounts in lakhs or crores"` — domain-specific formatting for Indian investors
- `"No generic disclaimers"` — prevents boilerplate ("This is not financial advice...") which reduces the explanation's usefulness
- `"One actionable takeaway"` — ensures the explanation ends with something concrete the user can do

---

## Concept 2: _build_user_prompt — Structured Data → Natural Language Input

```python
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

    lines.append("\nPlease explain this recommendation to the investor in plain English.")
    return "\n".join(lines)
```

This function converts structured data into a bullet-point style human turn for the LLM. The pattern is deliberate: give the LLM **all facts** it needs as structured text, then ask it to explain.

**Why conditional fields?** Not every call to `/explain` will have all fields. A user who skipped the simulation step won't have `simulation_success_probability`. The optional fields are only added if provided — the prompt adapts to whatever data is available.

**`{data.goal_target_amount:,.0f}`** — Python format spec: `,` inserts comma separators, `.0f` rounds to no decimal places. `5000000` becomes `"5,000,000"`. Combined with the `₹` prefix and LLM's instruction to use lakhs/crores, the LLM will say "₹50 lakhs" naturally.

**The horizon_capped note** — this is pre-written context that tells the LLM *why* equity was reduced. Without it, the LLM would see "Riskiest tier, 30% equity" and be confused (Riskiest should be 85%). The note prevents incorrect narration.

**Compliance violations** — if the compliance agent resolved violations, they're listed. The LLM might say: "Your allocation was adjusted to comply with regulatory guidelines — specifically, equity was capped to protect your investment."

---

## Concept 3: ChatOllama and ainvoke

```python
async def generate_explanation(data: ExplanationRequest) -> ExplanationResponse:
    llm = ChatOllama(model="llama3.2:3b", base_url=settings.OLLAMA_HOST)
    user_prompt = _build_user_prompt(data)

    response = await llm.ainvoke([
        SystemMessage(content=_SYSTEM_PROMPT),
        HumanMessage(content=user_prompt),
    ])
```

`ChatOllama` is created per request (unlike Phase 7 where the agent is created per request but the LLM object is created once). This is fine for a single-call pattern — no reuse across calls in the same request.

`await llm.ainvoke([...])` — async invocation. Sends the message list to Ollama, waits for the complete response, returns an `AIMessage`.

Two messages only — no `ToolMessage`, no loop:
- `SystemMessage` — the LLM's persona and constraints
- `HumanMessage` — the structured data + request to explain

`response.content.strip()` extracts the plain text from the `AIMessage` and removes leading/trailing whitespace.

### Why llama3.2:3b specifically?

The explanation task is simple: read structured data, write 4–6 sentences. A 3 billion parameter model is sufficient. The 8B model (used in Phase 7) is overkill for this task and 2–3x slower. For a local, zero-cost deployment, choosing the smallest capable model matters.

---

## Concept 4: Graceful Degradation

```python
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
```

Same pattern as Phase 7. Three response states:

| status | Meaning |
|--------|---------|
| `"success"` | Ollama is running, explanation generated |
| `"ollama_unavailable"` | Ollama process not running — tell user how to start it |
| `"error"` | Some other exception — surface the error message |

The API never returns HTTP 500. The frontend (Phase 13) can always display something — either the explanation or a clear message about why it's unavailable. All computed numbers (risk score, allocation, simulation) remain valid regardless of Ollama's status.

---

## How Phase 12 sits in the full workflow

```
Phase 3 → financial health metrics
Phase 4 → risk_score=88, risk_tier="Riskiest"
Phase 9 → equity=30%, debt=60%, gold=10%, horizon_capped=True
Phase 10 → success_probability=68%, p50=₹48L
Phase 12 →
  ExplanationRequest:
    risk_tier="Riskiest", risk_score=88,
    equity_pct=30, debt_pct=60, gold_pct=10,
    goal_horizon_years=2, horizon_capped=True,
    simulation_success_probability=68.0,
    goal_target_amount=5000000,
    compliance_passed=True
  →
  LLM output:
  "Based on your strong risk profile and 2-year goal, our system recommends a conservative
  allocation of 30% equity, 60% debt, and 10% gold. Although your risk score of 88/100
  (Riskiest tier) would normally suggest higher equity exposure, your short 2-year timeline
  means we've reduced equity to protect your capital from market volatility close to your
  goal date. The Monte Carlo simulation shows a 68% probability of reaching your ₹50L target
  — to improve this, consider increasing your monthly SIP or extending your horizon by a year
  or two. Start by setting up your SIP in a large-cap fund and a short-duration debt fund
  through any SEBI-registered mutual fund platform."
```

---

## End-to-end request flow

```
POST /explain
Body: { "risk_tier": "Safer", "risk_score": 55, "equity_pct": 40,
        "debt_pct": 55, "gold_pct": 5, "goal_horizon_years": 8,
        "horizon_capped": false,
        "simulation_success_probability": 82.0,
        "compliance_passed": true }
         │
         ▼
generate_explanation(data)
         │
         ├── _build_user_prompt(data) →
         │   "Risk Profile: Safer (score 55/100)
         │    Recommended Allocation: 40% Equity, 55% Debt, 5% Gold
         │    Investment Horizon: 8 years
         │    Monte Carlo Simulation: 82.0% probability of reaching the goal in 8 years.
         │    Compliance Check: PASSED
         │    Please explain this recommendation to the investor in plain English."
         │
         ├── ChatOllama(model="llama3.2:3b")
         ├── await llm.ainvoke([SystemMessage(_SYSTEM_PROMPT), HumanMessage(user_prompt)])
         │       → HTTP POST to ollama serve at localhost:11434
         │       → Ollama runs inference (2–5 seconds for 3B model on CPU)
         │       → Returns AIMessage with 4–6 sentence explanation
         │
         ├── response.content.strip() → plain text
         │
         ▼
{
  "explanation": "Your Safer risk profile reflects a balanced approach to investing ...",
  "status": "success"
}
```
