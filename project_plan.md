# Agentic Wealth Management Copilot - Implementation Roadmap

## Goal

Build the project incrementally, starting with deterministic financial
logic and adding AI/agentic components only after the core
recommendation engine works.

------------------------------------------------------------------------

# Phase 0: Understand the Architecture (1--2 Days)

## Core Business Flow

User → Financial Profile → Risk Score → Allocation → Fund Selection →
Compliance Check → Simulation → Explanation

### Guiding Principle

**LLM explains, rules decide.**

-   Financial decisions must be deterministic.
-   AI is only used for explanation and retrieval.
-   Never allow an LLM to directly decide allocations or compliance
    outcomes.

------------------------------------------------------------------------

# Phase 1: Project Setup

## Backend

-   FastAPI
-   PostgreSQL
-   SQLAlchemy
-   Alembic
-   Pydantic

## Frontend

-   React

## Infrastructure

-   Docker

## Folder Structure

``` text
wealth-copilot/

backend/
├── app/
│   ├── api/
│   ├── services/
│   ├── models/
│   ├── schemas/
│   ├── db/
│   ├── utils/
│   └── main.py

frontend/

docker-compose.yml
README.md
```

### Deliverable

`docker compose up` launches the backend and Swagger docs are
accessible.

------------------------------------------------------------------------

# Phase 2: Database Design

Create the following tables:

-   users
-   financial_profiles
-   goals
-   risk_assessments
-   fund_metadata
-   recommendations
-   policy_violations

### Deliverable

Create APIs:

-   POST /users
-   POST /financial-profile
-   POST /goals

------------------------------------------------------------------------

# Phase 3: Financial Health Engine

Implement:

-   Savings Rate
-   Debt-to-Income Ratio (DTI)
-   Emergency Fund Months
-   Net Worth

### Deliverable

Endpoint:

`POST /financial-health`

Returns:

-   net_worth
-   dti
-   savings_rate
-   emergency_months

------------------------------------------------------------------------

# Phase 4: Risk Scoring Service

Inputs:

-   Age
-   Goal Horizon
-   Income Stability
-   Risk Questionnaire

Output:

-   Risk Score
-   Risk Tier

Suggested tiers:

-   Safest
-   Safer
-   Riskier
-   Riskiest

### Deliverable

`POST /risk-score`

------------------------------------------------------------------------

# Phase 5: Allocation Engine

Create deterministic allocation rules.

Example:

  Risk Tier   Equity   Debt
  ----------- -------- ------
  Safest      20%      80%
  Safer       40%      60%
  Riskier     70%      30%
  Riskiest    90%      10%

Adjust allocations based on goal horizon.

### Deliverable

Portfolio allocation recommendation.

------------------------------------------------------------------------

# Phase 6: Fund Data Layer

Integrate:

-   MFAPI.in

Store:

-   Scheme Code
-   Scheme Name
-   NAV
-   Date

Create curated metadata:

-   Expense Ratio
-   AUM
-   Category
-   Risk Grade

### Deliverable

`GET /funds`

Returns real mutual fund data.

------------------------------------------------------------------------

# Phase 7: Fund Research Agent

First genuine agent.

Tools:

1.  Fund Metadata Search
2.  Factsheet Search
3.  MFAPI Lookup

Behavior:

-   Search matching funds
-   If insufficient results, broaden search
-   Retrieve factsheets for borderline cases

### Deliverable

Allocation → Recommended funds.

------------------------------------------------------------------------

# Phase 8: Policy Engine

Implement YAML-driven rules.

Example:

``` yaml
max_equity_under_3_year_goal: 40
max_smallcap_exposure: 20
max_single_fund_allocation: 30
min_emergency_fund_months: 6
```

### Deliverable

Policy validation service.

------------------------------------------------------------------------

# Phase 9: Compliance Agent

Second genuine agent.

Flow:

Allocation → Policy Check → Violation? → Revise Allocation → Recheck →
Pass

Implement using LangGraph conditional loops.

### Deliverable

Compliance audit trail.

------------------------------------------------------------------------

# Phase 10: Monte Carlo Simulation

Use:

-   NumPy
-   SciPy

Run:

-   1000+ simulations

Output:

-   Goal Success Probability

### Deliverable

Simulation API and visualization.

------------------------------------------------------------------------

# Phase 11: RAG Knowledge Base

Documents:

-   AMFI Factsheets
-   SEBI Circulars

Pipeline:

PDF → Chunking → Embedding → pgvector → Retrieval → LLM

### Deliverable

Grounded fund explanations.

------------------------------------------------------------------------

# Phase 12: Explanation Generator

Model:

-   Ollama
-   Llama 3.1 8B

Input:

-   Risk score
-   Allocation
-   Selected funds
-   Compliance result
-   Simulation result

Output:

Plain-English recommendation.

### Deliverable

Human-readable investment explanation.

------------------------------------------------------------------------

# Phase 13: React Frontend

Pages:

-   Login
-   Financial Profile
-   Goal Creation
-   Risk Assessment
-   Recommendation Dashboard

### Deliverable

End-to-end user workflow.

------------------------------------------------------------------------

# Phase 14: Monitoring & Rebalancing

Tools:

-   Celery
-   Redis

Scheduled Jobs:

-   Weekly portfolio review
-   Monthly goal progress review

### Deliverable

Automated monitoring system.

------------------------------------------------------------------------

# Phase 15: Evaluation & Observability

Tools:

-   Langfuse
-   Ragas
-   DeepEval

Track:

-   Hallucination Score
-   Retrieval Quality
-   Recommendation Consistency
-   Latency

### Deliverable

Production-grade observability.

------------------------------------------------------------------------

# Recommended Build Order

1.  FastAPI Skeleton
2.  PostgreSQL Setup
3.  User APIs
4.  Financial Profile APIs
5.  Financial Health Engine
6.  Risk Scoring Service
7.  Allocation Engine
8.  Fund Metadata Database
9.  MFAPI Integration
10. Recommendation API
11. Policy Engine
12. Compliance Agent
13. Monte Carlo Simulation
14. RAG Knowledge Base
15. Ollama Integration
16. Explanation Generator
17. React Frontend
18. Langfuse
19. Evaluation Framework

## Milestone

By Step 10, the project should already function as a complete
deterministic wealth-management recommendation engine.

All GenAI and agentic capabilities should be layered on top afterward.
