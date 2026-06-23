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

# Phase 2: Core Wealth Management Data Model

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
