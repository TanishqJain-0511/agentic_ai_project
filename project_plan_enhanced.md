# Agentic Wealth Management Copilot - Implementation Roadmap

## Goal

Build the project incrementally, starting with deterministic financial
logic and adding AI/agentic components only after the core
recommendation engine works.

------------------------------------------------------------------------

# Phase 0: Understand the Architecture 

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
# Phase 1: Backend Foundations & Infrastructure

## Objective

Build a production-style backend foundation before implementing any wealth-management logic.

The goal of Phase 1 was not to build financial features, but to understand how a backend application works end-to-end:

```text
Client
  ↓
FastAPI
  ↓
Validation
  ↓
Business Logic
  ↓
Database Layer
  ↓
PostgreSQL
```

By the end of this phase, the application should be capable of receiving requests, validating data, storing it in PostgreSQL, retrieving it, and running entirely through Docker.

---

# What We Built

## 1. FastAPI Application

### What We Did

Created a FastAPI application and started it using Uvicorn.

Implemented basic endpoints such as:

```http
GET /
GET /hello/{name}
GET /square/{num}
```

### Why We Did It

Before building business features, we needed a backend framework capable of:

- Receiving HTTP requests
- Returning responses
- Exposing APIs
- Generating API documentation

### Concepts Learned

- FastAPI
- Routing
- Request/Response lifecycle
- Uvicorn
- ASGI applications

---

## 2. Swagger / OpenAPI

### What We Did

Used:

```text
/docs
/openapi.json
```

### Why We Did It

To test APIs without building a frontend.

Swagger allows:

- Sending requests
- Inspecting responses
- Viewing API contracts

### Concepts Learned

- OpenAPI
- API documentation
- Interactive API testing

---

## 3. PostgreSQL in Docker

### What We Did

Created a PostgreSQL container using Docker.

Verified it was running using:

```bash
docker ps
```

Connected to it using:

```bash
docker exec -it wealth_postgres psql -U postgres -d wealth_db
```

### Why We Did It

We need persistent storage for:

- Users
- Financial Profiles
- Goals
- Risk Assessments
- Recommendations

Docker ensures everyone runs the same database setup.

### Concepts Learned

- Docker Images
- Containers
- Volumes
- Port Mapping
- Database Containers

---

## 4. SQLAlchemy Setup

### What We Did

Configured:

```python
engine
SessionLocal
Base
```

inside:

```text
app/db/database.py
```

### Why We Did It

SQLAlchemy acts as a bridge between:

```text
Python Objects
      ↓
SQL Queries
      ↓
PostgreSQL
```

Without it we would need to write SQL manually.

### Concepts Learned

- ORM
- Engine
- Sessions
- Declarative Models
- Database Connections

---

## 5. Database Connectivity Check

### What We Did

Created:

```http
GET /health
```

which verifies database connectivity.

### Why We Did It

Before building features we needed to ensure:

```text
FastAPI
      ↓
PostgreSQL
```

communication works correctly.

### Concepts Learned

- Connection Testing
- Health Checks
- Database Availability

---

## 6. First ORM Model

### What We Did

Created:

```python
class User(Base)
```

with fields:

```text
id
name
email
```

### Why We Did It

To learn how database tables are represented as Python classes.

### Concepts Learned

- ORM Mapping
- Primary Keys
- Constraints
- Unique Fields
- Table Definitions

---

## 7. Table Creation

### What We Did

Generated database tables using:

```python
Base.metadata.create_all()
```

Verified using:

```sql
\dt
```

inside PostgreSQL.

### Why We Did It

To understand how ORM models become physical database tables.

### Concepts Learned

- Schema Creation
- ORM → SQL Translation
- Database Metadata

---

## 8. Database Sessions

### What We Did

Created:

```python
get_db()
```

which creates and closes sessions automatically.

### Why We Did It

Every request should receive its own database session.

Without proper session management:

- Connections leak
- Resources are wasted
- Applications become unstable

### Concepts Learned

- Session Lifecycle
- Connection Management
- Resource Cleanup

---

## 9. Dependency Injection

### What We Did

Used:

```python
Depends(get_db)
```

inside endpoints.

### Why We Did It

To automatically provide database sessions to routes.

Instead of manually creating sessions everywhere.

### Concepts Learned

- Dependency Injection
- FastAPI Architecture
- Reusable Components

---

## 10. Pydantic Schemas

### What We Did

Created:

```python
UserCreate
UserResponse
```

schemas.

### Why We Did It

Database models and API contracts serve different purposes.

Schemas handle:

- Validation
- Serialization
- API Inputs
- API Outputs

### Concepts Learned

- Data Validation
- Request Models
- Response Models

---

## 11. First CRUD APIs

### What We Did

Implemented:

```http
POST /users
GET /users
GET /users/{id}
```

### Why We Did It

To understand the complete backend flow:

```text
Request
  ↓
Validation
  ↓
Business Logic
  ↓
Database
  ↓
Response
```

### Concepts Learned

- CRUD Operations
- Querying Data
- Filtering Data
- Database Persistence

---

## 12. Service Layer

### What We Did

Moved database/business logic into:

```text
services/user_service.py
```

### Why We Did It

To separate:

```text
API Layer
```

from

```text
Business Logic Layer
```

This keeps the application maintainable as it grows.

### Concepts Learned

- Separation of Concerns
- Layered Architecture
- Reusable Business Logic

---

## 13. Environment Variables

### What We Did

Created:

```text
.env
```

and moved configuration outside code.

### Why We Did It

Different environments require different settings:

```text
Development
Staging
Production
```

Configuration should not be hardcoded.

### Concepts Learned

- Configuration Management
- Environment Variables
- Secure Application Setup

---

## 14. Dockerized Backend

### What We Did

Created:

```text
Dockerfile
docker-compose.yml
```

for the FastAPI application.

### Why We Did It

To package:

```text
Code
Dependencies
Runtime
```

into a portable unit.

### Concepts Learned

- Dockerfiles
- Containerized Applications
- Multi-Service Systems

---

# APIs Completed

```http
GET /
GET /hello/{name}
GET /square/{num}
GET /health

POST /users
GET /users
GET /users/{id}
```

---

# Architecture Achieved

```text
Client
   ↓
FastAPI Endpoint
   ↓
Pydantic Validation
   ↓
Service Layer
   ↓
SQLAlchemy Session
   ↓
PostgreSQL
```

---

# Phase 1 Completion Criteria

✅ FastAPI Running

✅ Swagger Available

✅ PostgreSQL Running

✅ Docker Setup

✅ SQLAlchemy Configured

✅ User Table Created

✅ Session Management

✅ Dependency Injection

✅ Pydantic Validation

✅ CRUD APIs

✅ Service Layer

✅ Environment Configuration

✅ Backend Dockerization

------------------------------------------------------------------------------------------------------------------------------

------------------------------------------------------------------------------------------------------------------------------

---------------------------------------------------------------------------------------------------

# Phase 2: Core Wealth Management Data Model ✅ COMPLETE

## Objective

Build the foundational financial entities required by the wealth-management system.

No recommendations, risk scoring, or simulations are performed yet.

The goal is to collect and persist all financial information needed by later phases.

---

# Step 1: Financial Profile Model

Create:

```text
financial_profiles
```

table.

Fields:

```text
id
user_id
annual_income
monthly_expenses
cash_savings
existing_investments
total_debt
emergency_fund
created_at
```

Learn:

- Foreign Keys
- One-to-One Relationships
- SQLAlchemy Relationships

Build:

```http
POST /financial-profile
GET /financial-profile/{user_id}
```

---

# Step 2: Goal Model

Create:

```text
goals
```
table.

Fields:

```text
id
user_id
goal_name
target_amount
target_date
priority
created_at
```

Examples:

- Retirement
- House Purchase
- Education
- Vacation

Learn:

- One-to-Many Relationships
- User → Multiple Goals

Build:

```http
POST /goals
GET /goals/{user_id}
```

---

# Step 3: Risk Assessment Model

Create:

```text
risk_assessments
```

table.

Fields:

```text
id
user_id
risk_score
risk_tier
questionnaire_answers
created_at
```

Learn:

- Structured Data Storage
- Relationship Modeling

Build:

```http
POST /risk-assessment
GET /risk-assessment/{user_id}
```

---

# Step 4: Service Layer Expansion

Create:

```text
financial_profile_service.py
goal_service.py
risk_assessment_service.py
```

Move all business logic into services.

---

# Step 5: Relationship Modeling

Implement:

```text
User
 ├── Financial Profile
 ├── Goal 1
 ├── Goal 2
 ├── Goal 3
 └── Risk Assessment
```

Learn:

- Foreign Keys
- Relationships
- ORM Navigation

Examples:

```python
user.goals
goal.user
user.financial_profile
```

---

# Phase 2 Deliverables

## Database Tables

```text
users
financial_profiles
goals
risk_assessments
```

## APIs

```http
POST /financial-profile
GET /financial-profile/{user_id}

POST /goals
GET /goals/{user_id}

POST /risk-assessment
GET /risk-assessment/{user_id}
```

## Architecture

```text
Models
Schemas
Services
API Routes
Relationships
```

## Milestone

At the end of Phase 2, the application contains all user financial data required to build:

- Financial Health Engine (Phase 3)
- Risk Scoring Engine (Phase 4)
- Allocation Engine (Phase 5)

------------------------------------------------------------------------

# Phase 3: Financial Health Engine ✅ COMPLETE

Implement:

-   Savings Rate
-   Debt-to-Income Ratio (DTI)
-   Emergency Fund Months
-   Net Worth

## What Was Built

### Files Created

```text
backend/app/schemas/financial_health.py      ← FinancialHealthResponse schema
backend/app/services/financial_health_service.py  ← compute_financial_health() + status helpers
```

### Computations

| Metric                 | Formula                                           |
|------------------------|---------------------------------------------------|
| net_worth              | cash_savings + existing_investments - total_debt  |
| monthly_surplus        | (annual_income / 12) - monthly_expenses           |
| savings_rate           | (monthly_surplus / monthly_income) × 100          |
| dti                    | (total_debt / annual_income) × 100                |
| emergency_fund_months  | total_cash_savings / monthly_expenses             |

### Status Labels (for explanation layer later)

| Metric                 | Thresholds                                   |
|------------------------|----------------------------------------------|
| savings_rate_status    | high ≥ 20% · normal ≥ 10% · low < 10%          |
| dti_status             | healthy < 36% · moderate 36–50% · high > 50% |
| emergency_fund_status  | adequate ≥ 6 months · low 3–6 · critical < 3 |

### Deliverable

Endpoint:

`GET /financial-health/{user_id}`

Returns:

-   net_worth
-   monthly_surplus
-   savings_rate + savings_rate_status
-   dti + dti_status
-   emergency_fund_months + emergency_fund_status

------------------------------------------------------------------------

# Phase 4: Risk Scoring Service ✅ COMPLETE

Inputs:

-   Age
-   Goal Horizon
-   Income Stability
-   Risk Questionnaire (fetched from DB via user_id)

Output:

-   Risk Score (0–100)
-   Risk Tier

## What Was Built

### Files Created

```text
backend/app/schemas/risk_score.py          ← RiskScoreRequest, RiskScoreResponse
backend/app/services/risk_scoring_service.py  ← compute_risk_score() + helpers
```

### Scoring Breakdown (max 100 pts)

| Component | Max pts | Logic |
|---|---|---|
| Age | 30 | <30→30, <40→25, <50→20, <60→10, 60+→5 |
| Goal horizon | 30 | >10yr→30, ≥7→25, ≥5→20, ≥3→10, <3→5 |
| Income stability | 20 | stable→20, semi_stable→12, variable→6 |
| Questionnaire | 20 | 5 questions × 4 pts each |

### Questionnaire Keys (stored in risk_assessments.questionnaire_answers)

| Key | Accepted Values |
|---|---|
| market_drop_reaction | buy_more · hold · sell |
| investment_experience | expert · intermediate · beginner |
| primary_goal | wealth_growth · balanced · capital_preservation |
| loss_tolerance_percent | >20 · 10-20 · <10 |
| investment_knowledge | high · medium · low |

### Risk Tiers

| Score | Tier |
|---|---|
| 0–25 | Safest |
| 26–50 | Safer |
| 51–75 | Riskier |
| 76–100 | Riskiest |

### Side Effect

Persists computed `risk_score` and `risk_tier` back into the `risk_assessments` row for the user.

### Deliverable

`POST /risk-score`

Body: user_id, age, goal_horizon_years, income_stability

Returns: risk_score, risk_tier, score_breakdown

------------------------------------------------------------------------

# Phase 5: Allocation Engine ✅ COMPLETE

Create deterministic allocation rules.

## What Was Built

### Files Created

```text
backend/app/schemas/allocation.py         ← AllocationRequest, AllocationResponse
backend/app/services/allocation_service.py  ← compute_allocation() + _equity_cap()
```

### Base Allocations by Risk Tier

| Risk Tier | Equity | Debt | Gold |
|---|---|---|---|
| Safest | 20% | 75% | 5% |
| Safer | 40% | 55% | 5% |
| Riskier | 70% | 25% | 5% |
| Riskiest | 90% | 5% | 5% |

### Horizon Cap (equity ceiling for short goals)

| Goal Horizon | Equity Cap | Reason |
|---|---|---|
| < 3 years | 30% | Cannot afford volatility near goal date |
| 3–5 years | 50% | Moderate protection needed |
| ≥ 5 years | No cap | Sufficient time to recover |

When equity is capped, the excess is moved to debt. `horizon_capped: true` is returned to signal this adjustment was made.

### Deliverable

`POST /allocation`

Body: user_id, goal_horizon_years

Returns: equity_pct, debt_pct, gold_pct, risk_tier, horizon_capped

------------------------------------------------------------------------

# Phase 6: Fund Data Layer ✅ COMPLETE

## What Was Built

### Files Created

```text
backend/app/models/mutual_fund.py          ← MutualFund ORM model
backend/app/data/fund_metadata.json        ← Curated metadata for 10 funds
backend/app/schemas/fund.py                ← FundResponse, FundSyncResponse
backend/app/services/fund_data_service.py  ← sync_funds(), get_all_funds(), get_fund_by_scheme_code()
```

### MutualFund Table Columns

| Column | Type | Source |
|---|---|---|
| scheme_code | String (unique) | MFAPI / metadata |
| scheme_name | String | MFAPI live fetch |
| nav | Float | MFAPI live fetch |
| nav_date | String | MFAPI live fetch |
| category | String | fund_metadata.json |
| risk_grade | String | fund_metadata.json |
| expense_ratio | Float | fund_metadata.json |
| aum | Float (crores) | fund_metadata.json |
| last_updated | DateTime | auto on upsert |

### Curated Fund List (fund_metadata.json)

10 funds across categories: Flexi Cap, Large Cap, Mid Cap, Small Cap, Hybrid, Index, Gilt, Gold

### Sync Logic

`POST /funds/sync` — for each scheme_code in metadata:
1. Hits `https://api.mfapi.in/mf/{scheme_code}` for live scheme_name + NAV
2. Merges with curated expense_ratio, AUM, category, risk_grade
3. Upserts into `mutual_funds` table (update if exists, insert if new)
4. Skips gracefully on network/API failure

### Endpoints

| Endpoint | Description |
|---|---|
| `POST /funds/sync` | Fetch live NAV from MFAPI, upsert into DB |
| `GET /funds` | List all funds (optional ?category= and ?risk_grade= filters) |
| `GET /funds/{scheme_code}` | Get single fund by scheme code |

### Dependency Added

`requests` added to requirements.txt (rebuild Docker image before testing)

------------------------------------------------------------------------

# Phase 7: Fund Research Agent ✅ COMPLETE

First genuine agent. Uses LangGraph + Ollama (Llama 3.1) with tool-calling.

## What Was Built

### Files Created

```text
backend/app/agents/__init__.py
backend/app/agents/fund_research_agent.py   ← LangGraph graph + 3 tools
backend/app/schemas/fund_research.py        ← FundResearchRequest, FundResearchResponse
backend/app/services/fund_research_service.py ← run_fund_research() with error handling
```

### LangGraph Graph Structure

```
START → agent_node → (tool_calls?) → tool_node → agent_node (loop)
                   → (no tool_calls) → END
```

### Tools (closures bound to DB session)

| Tool | Purpose |
|---|---|
| `search_funds_by_category(category)` | Primary search — queries mutual_funds by category |
| `search_funds_by_risk_grade(risk_grade)` | Broadened search — used when category returns 0 results |
| `get_fund_details(scheme_code)` | Verify a specific fund before recommending |

### Search Strategy (in system prompt)

| Asset Class | Risk Tier | Try First | Broaden To |
|---|---|---|---|
| Equity | Safest/Safer | Large Cap → Index | risk_grade=Very High |
| Equity | Riskier | Mid Cap → Flexi Cap | risk_grade=Very High |
| Equity | Riskiest | Small Cap → Mid Cap | risk_grade=Very High |
| Debt | Any | Gilt | risk_grade=Moderate |
| Gold | Any | Gold | risk_grade=High |

### Error Handling

- If Ollama is unreachable → returns `status: "ollama_unavailable"` with setup instructions
- Any other error → returns `status: "error"` with error message
- Never raises HTTP 500 — always returns a structured response

### Deliverable

`POST /fund-research`

Body: user_id, equity_pct, debt_pct, gold_pct, risk_tier

Returns: agent_response (LLM text with recommendations), status

### Dependencies Added

```
langgraph
langchain
langchain-core
langchain-ollama
```

### To Activate

```bash
# 1. Rebuild Docker image (new deps)
docker-compose down && docker-compose up --build

# 2. Start Ollama separately (not in Docker yet)
ollama serve
ollama pull llama3.1

# 3. Update OLLAMA_HOST in .env if needed
```

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
