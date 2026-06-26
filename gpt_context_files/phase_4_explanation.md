# Phase 4 — Risk Scoring Service: Full Deep Dive

---

## What is this phase doing conceptually?

Phase 3 computed how healthy a person's finances are right now. Phase 4 computes how much risk they **should** take with their investments going forward.

Risk tolerance is a function of two different things:
1. **Objective factors** — age, investment horizon, income stability. These are facts about the person's situation that constrain how much risk they can afford.
2. **Subjective factors** — questionnaire answers. How they emotionally and psychologically respond to market volatility and losses.

The scoring system combines both into a single 0–100 score that maps to one of four tiers: Safest, Safer, Riskier, Riskiest. That tier then drives the allocation engine (Phase 5) which determines the equity/debt/gold split.

---

## Scoring Architecture

```
POST /risk-score
Body: { user_id, age, goal_horizon_years, income_stability }
         ↓
compute_risk_score(db, data)
         │
         ├── _age_score(age)                  → max 30 pts
         ├── _horizon_score(years)             → max 30 pts
         ├── _income_score(stability)          → max 20 pts
         └── _questionnaire_score(answers)     → max 20 pts
                   │
                   reads risk_assessments table (Phase 2 stored answers)
         │
         total_score = sum of 4 components (0–100)
         tier        = _risk_tier(total_score)
         │
         SIDE EFFECT: writes risk_score + risk_tier back to risk_assessments table
         │
         ▼
{ user_id, risk_score, risk_tier, score_breakdown }
```

---

## The 4 Scoring Components

### Component 1: Age Score (max 30 pts)

```python
def _age_score(age: int) -> int:
    if age < 30:   return 30
    elif age < 40: return 25
    elif age < 50: return 20
    elif age < 60: return 10
    return 5
```

**Why age drives risk capacity**: Younger investors have more time to recover from market downturns. A 25-year-old who loses 50% of their portfolio has 30+ years to recover. A 60-year-old with the same loss has far fewer years before needing that money.

Age is the single largest component (30 pts) — it's the most objective and impactful constraint. A 60-year-old with all the risk appetite in the world still shouldn't be 100% in small-cap stocks near retirement.

### Component 2: Goal Horizon Score (max 30 pts)

```python
def _horizon_score(years: int) -> int:
    if years > 10:   return 30
    elif years >= 7: return 25
    elif years >= 5: return 20
    elif years >= 3: return 10
    return 5
```

**Why horizon matters independently of age**: A 50-year-old saving for a goal 15 years away (retirement at 65) can take more equity risk than a 30-year-old saving for a house down payment in 2 years. The goal's time horizon, not just the person's age, determines how much short-term volatility is acceptable.

Tied with age at 30 pts — both are objective, structural constraints on risk capacity.

### Component 3: Income Stability Score (max 20 pts)

```python
def _income_score(stability: str) -> int:
    return {"stable": 20, "semi_stable": 12, "variable": 6}.get(stability, 0)
```

**Why income stability matters**: A government employee (stable) can tolerate watching their portfolio drop 30% because their income is secure and they won't be forced to sell. A freelancer (variable) might need to liquidate investments in a bad month to cover expenses — forcing a sale at the worst time. Variable income requires a larger safety buffer and lower risk allocation.

Three levels, 20 pts max. The `.get(stability, 0)` default handles unexpected input gracefully.

### Component 4: Questionnaire Score (max 20 pts)

```python
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
```

5 questions × 4 pts max = 20 pts. Each question tests a different dimension of psychological risk tolerance.

`answers.get(question)` — safely reads the answer for each question key. Returns `None` if the key is missing.

`score_map.get(answers.get(question), 0)` — if the answer is `None` or an unexpected value, defaults to 0 pts. Forgiving of bad data.

**Why questionnaire is only 20%**: Psychological self-assessment is valuable but unreliable — people overestimate their risk tolerance in bull markets and underestimate it in bear markets. The three objective factors (age, horizon, income) get 80% of the weight because they're factual constraints, not opinions.

---

## Tier Assignment

```python
def _risk_tier(score: int) -> str:
    if score <= 25:  return "Safest"
    elif score <= 50: return "Safer"
    elif score <= 75: return "Riskier"
    return "Riskiest"
```

| Score  | Tier     | Typical investor                                                   |
|--------|----------|--------------------------------------------------------------------|
| 0–25   | Safest   | Age 55+, short horizon, variable income, capital preservation goal |
| 26–50  | Safer    | Middle-aged, medium horizon, stable income, balanced goal          |
| 51–75  | Riskier  | 30s-40s, 7+ year horizon, stable income, growth goal               |
| 76–100 | Riskiest | Under 30, 10+ year horizon, stable income, aggressive growth       |

These tiers feed directly into Phase 5's allocation lookup table.

---

## The Critical Side Effect: Writing Back to DB

```python
    if assessment:
        assessment.risk_score = total_score
        assessment.risk_tier = tier
        await db.commit()
        await db.refresh(assessment)
```

This is the most important thing Phase 4 does beyond computing the score. The `risk_score` and `risk_tier` fields on `RiskAssessment` (which were `NULL` after Phase 2) are now populated.

**Why write to DB?** Phase 5 (Allocation Engine) needs the risk tier to compute the portfolio split. Rather than recomputing it every time, Phase 5 just reads `risk_tier` from the `risk_assessments` table. Writing it once here makes it persistent and available to all downstream phases.

**Why not just return the score and have Phase 5 compute it?** That would couple Phase 5 to re-running Phase 4 logic. Storing the computed tier creates a clean handoff: compute once, use everywhere.

---

## The score_breakdown field

```python
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
```

`score_breakdown` exists for transparency. The Streamlit frontend (Phase 13) uses it to render a breakdown bar chart showing the user which factors contributed most to their risk score. It also helps during debugging — if a score looks wrong, you can see exactly which component caused it.

---

## End-to-end request flow

```
POST /risk-score
Body: { "user_id": 1, "age": 28, "goal_horizon_years": 12, "income_stability": "stable" }
         │
         ▼
compute_risk_score(db, data)
         │
         ├── _age_score(28)       = 30  (age < 30 → max)
         ├── _horizon_score(12)   = 30  (years > 10 → max)
         ├── _income_score("stable") = 20  (stable → max)
         │
         ├── get_risk_assessment_by_user_id(db, 1)
         │       → assessment with questionnaire_answers:
         │         {"market_drop_reaction": "hold",
         │          "investment_experience": "beginner",
         │          "primary_goal": "balanced",
         │          "loss_tolerance_percent": "10-20",
         │          "investment_knowledge": "medium"}
         │
         ├── _questionnaire_score(answers):
         │       market_drop_reaction → "hold" → 2
         │       investment_experience → "beginner" → 0
         │       primary_goal → "balanced" → 2
         │       loss_tolerance_percent → "10-20" → 2
         │       investment_knowledge → "medium" → 2
         │       total = 8
         │
         ├── total_score = 30 + 30 + 20 + 8 = 88
         ├── tier = "Riskiest" (88 > 75)
         │
         ├── assessment.risk_score = 88
         ├── assessment.risk_tier  = "Riskiest"
         ├── await db.commit()  ← WRITES BACK
         │
         ▼
{
  "user_id": 1,
  "risk_score": 88,
  "risk_tier": "Riskiest",
  "score_breakdown": {
    "age_score": 30,
    "horizon_score": 30,
    "income_score": 20,
    "questionnaire_score": 8
  }
}
```

A 28-year-old with a 12-year horizon and stable income scores maximum objective points (80/80) despite moderate questionnaire answers (8/20). The objective factors dominate — as designed.
