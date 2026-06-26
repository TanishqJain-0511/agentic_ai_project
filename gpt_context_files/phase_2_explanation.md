# Phase 2 — Core Data Model: Full Deep Dive

---

## What is this phase doing conceptually?

Phase 2 defines the **data layer** — the tables, relationships, validation schemas, and CRUD services that every future phase reads from or writes to. If Phase 1 is the foundation (infrastructure), Phase 2 is the concrete walls (data model).

The four entities:
- **User** — who is using the system
- **FinancialProfile** — their income, expenses, savings, debt (1:1 with User)
- **RiskAssessment** — their questionnaire answers + computed score/tier (1:1 with User)
- **InvestmentGoal** — their financial goals (1:N with User — a user can have many goals)

Every computation in Phases 3–12 reads from one or more of these tables.

---

## Entity Relationship

```
users (1)
├── (1:1) financial_profiles    — annual_income, monthly_expenses, total_cash_savings,
│                                  total_existing_investments, total_debt
├── (1:1) risk_assessments      — questionnaire_answers (JSON), risk_score, risk_tier
└── (1:N) investment_goals      — goal_name, target_amount, target_date, goal_priority
```

The 1:1 relationships use `UNIQUE` constraints on `user_id` — PostgreSQL enforces that only one financial profile and one risk assessment can exist per user.

---

## Concept 1: SQLAlchemy ORM models

An ORM model is a Python class that maps to a database table. SQLAlchemy reads the class definition and knows: what table name to use, what columns exist, what types they are, and what constraints to apply.

### User model

```python
class User(Base):
    __tablename__ = "users"

    id    = Column(Integer, primary_key=True, index=True)
    name  = Column(String, nullable=False)
    email = Column(String, unique=True, nullable=False)

    financial_profile = relationship("FinancialProfile", back_populates="user", uselist=False)
    investment_goals  = relationship("InvestmentGoal", back_populates="user")
    risk_assessment   = relationship("RiskAssessment", back_populates="user", uselist=False)
```

`__tablename__` — the actual PostgreSQL table name. `"users"` maps to the `users` table.

`Column(Integer, primary_key=True, index=True)` — auto-incrementing integer PK. `index=True` creates a B-tree index on `id` for fast lookups.

`Column(String, unique=True, nullable=False)` — `unique=True` creates a UNIQUE constraint in PostgreSQL (duplicate emails rejected at the DB level, not just application level).

### Relationships

```python
financial_profile = relationship("FinancialProfile", back_populates="user", uselist=False)
```

`relationship()` tells SQLAlchemy that `User` has an associated `FinancialProfile`. This doesn't add a column — it's a Python-level convenience attribute that lazy-loads the related object when accessed.

`back_populates="user"` — both sides of the relationship reference each other. On `FinancialProfile`, there's `relationship("User", back_populates="financial_profile")`. They're linked by name.

`uselist=False` — critical for 1:1 relationships. Without it, `user.financial_profile` would be a list. With `uselist=False`, it's a single object (or `None`).

For the 1:N `investment_goals`, there's no `uselist=False` — `user.investment_goals` is a list.

---

## Concept 2: FinancialProfile — Timestamps and ForeignKey

```python
class FinancialProfile(Base):
    __tablename__ = "financial_profiles"

    id                        = Column(Integer, primary_key=True, index=True)
    user_id                   = Column(Integer, ForeignKey("users.id"), nullable=False, unique=True)
    annual_income             = Column(Float, nullable=False)
    monthly_expenses          = Column(Float, nullable=False)
    total_cash_savings        = Column(Float, nullable=False)
    total_existing_investments = Column(Float, nullable=False)
    total_debt                = Column(Float, nullable=False)
    created_at  = Column(DateTime(timezone=True), nullable=False, default=func.now())
    modified_at = Column(DateTime(timezone=True), nullable=False, default=func.now(),
                         onupdate=func.now())
```

### ForeignKey

`ForeignKey("users.id")` creates a foreign key constraint — `financial_profiles.user_id` must reference an existing `users.id`. Attempts to create a profile for a non-existent user are rejected by PostgreSQL.

`unique=True` on `user_id` enforces the 1:1 constraint — only one financial profile per user.

### Timestamps

`DateTime(timezone=True)` — always store timestamps with timezone info (UTC). Without it, you lose the ability to correctly interpret times across timezones.

`default=func.now()` — `func.now()` calls PostgreSQL's `NOW()` function at insert time. This happens server-side, so the timestamp is always correct regardless of the application server's clock.

`onupdate=func.now()` on `modified_at` — automatically updates to the current time on every UPDATE operation. No application code needed.

---

## Concept 3: RiskAssessment — JSON column

```python
class RiskAssessment(Base):
    __tablename__ = "risk_assessments"

    id                   = Column(Integer, primary_key=True, index=True)
    user_id              = Column(Integer, ForeignKey("users.id"), nullable=False, unique=True)
    questionnaire_answers = Column(JSON, nullable=False)
    risk_score           = Column(Integer, nullable=True)   # computed later by Phase 4
    risk_tier            = Column(String, nullable=True)    # computed later by Phase 4
    created_at           = Column(DateTime(timezone=True), nullable=False, default=func.now())
    modified_at          = Column(DateTime(timezone=True), nullable=False, default=func.now(),
                                  onupdate=func.now())
```

### JSON column

`questionnaire_answers` stores a Python dict as JSON in PostgreSQL. The questionnaire structure can evolve without a schema migration — you just store whatever dict the application sends.

The stored value looks like:
```json
{
  "market_drop_reaction": "hold",
  "investment_experience": "intermediate",
  "primary_goal": "balanced",
  "loss_tolerance_percent": "10-20",
  "investment_knowledge": "medium"
}
```

### Nullable risk_score and risk_tier

These are intentionally `nullable=True`. The assessment is created when the user submits questionnaire answers — at that point, `risk_score` and `risk_tier` are `None`. Phase 4 (Risk Scoring Service) computes them and writes them back. This two-step pattern (create raw → compute score) decouples data collection from computation.

---

## Concept 4: InvestmentGoal — 1:N relationship

```python
class InvestmentGoal(Base):
    __tablename__ = "investment_goals"

    id            = Column(Integer, primary_key=True, index=True)
    user_id       = Column(Integer, ForeignKey("users.id"), nullable=False)
    # No unique=True on user_id — a user can have many goals
    goal_name     = Column(String, nullable=False)
    target_amount = Column(Float, nullable=False)
    target_date   = Column(Date, nullable=False)
    goal_priority = Column(Integer, nullable=False)  # 1 = highest
    created_at    = Column(DateTime(timezone=True), ...)
    modified_at   = Column(DateTime(timezone=True), ...)
```

`user_id` has `ForeignKey` but no `unique=True` — a user can have multiple goals (retirement, house down payment, child education, etc.).

`goal_priority` is an integer where 1 = most important. Allocation and simulation would prioritise goal 1 if budget is limited.

---

## Concept 5: Pydantic schemas — Why they're separate from ORM models

A common question: why have both `models/user.py` (SQLAlchemy) and `schemas/user.py` (Pydantic)? They look similar but serve different purposes.

| | SQLAlchemy model | Pydantic schema |
|---|---|---|
| Purpose | Map to DB table | Validate HTTP request/response |
| Used by | Services (DB I/O) | Endpoints (HTTP I/O) |
| Fields | Everything in the table | Only what the API exposes |
| Behaviour | Lazy-loads relationships | Pure data validation |

Example: `User` ORM model has relationships (`financial_profile`, `investment_goals`). `UserResponse` schema exposes only `id`, `name`, `email` — you don't want to accidentally return every related object in every user response.

```python
# schemas/user.py
class UserCreate(BaseModel):
    name: str = Field(..., description="Full name of the user")
    email: EmailStr = Field(..., description="Unique email address")

class UserResponse(BaseModel):
    id: int
    name: str
    email: EmailStr

    class Config:
        from_attributes = True
```

`from_attributes = True` (Pydantic v2) — tells Pydantic it can read attribute values from ORM objects (not just dicts). Without it, passing a SQLAlchemy `User` object to `UserResponse` would fail.

`EmailStr` — Pydantic validates this is a properly formatted email address. Invalid emails are rejected before reaching the service layer.

---

## Concept 6: CRUD service pattern

Every entity has a service file with create/get functions. The pattern is identical across all entities:

```python
# services/user_service.py
async def create_user(db: AsyncSession, user: UserCreate):
    new_user = User(name=user.name, email=user.email)
    db.add(new_user)
    await db.commit()
    await db.refresh(new_user)
    return new_user

async def get_users(db: AsyncSession):
    result = await db.execute(select(User))
    return result.scalars().all()

async def get_user_by_id(db: AsyncSession, user_id: int):
    result = await db.execute(select(User).where(User.id == user_id))
    return result.scalar_one_or_none()
```

### create_user line by line

`User(name=user.name, email=user.email)` — creates an ORM object in memory. Not in the DB yet.

`db.add(new_user)` — marks the object for insertion. Still not in the DB — it's in the session's "pending" state.

`await db.commit()` — flushes all pending changes to the DB and commits the transaction. `INSERT INTO users ...` runs here. The `id` is now populated (auto-generated by PostgreSQL).

`await db.refresh(new_user)` — after commit, the object's attributes might be stale (especially `id`, `created_at`, `modified_at` which are DB-generated). `refresh()` re-fetches the row from the DB and updates the in-memory object.

### get_users pattern

`select(User)` — generates `SELECT * FROM users`.

`await db.execute(...)` — runs the query, returns a `CursorResult`.

`result.scalars().all()` — `.scalars()` extracts the first column of each row (the `User` object when selecting a model). `.all()` returns a list.

### get_user_by_id

`select(User).where(User.id == user_id)` — generates `SELECT * FROM users WHERE id = ?`.

`result.scalar_one_or_none()` — returns the single result, or `None` if no row matched. Raises an exception if multiple rows match (shouldn't happen since `id` is a primary key).

---

## Concept 7: model_dump() in risk_assessment create

```python
async def create_risk_assessment(db: AsyncSession, data: RiskAssessmentCreate):
    new_assessment = RiskAssessment(**data.model_dump())
```

`data.model_dump()` converts the Pydantic object to a dict:
```python
{
    "user_id": 1,
    "questionnaire_answers": {"market_drop_reaction": "hold", ...}
}
```

`**data.model_dump()` unpacks that dict as keyword arguments into `RiskAssessment(...)`. This works when the Pydantic field names match the ORM column names exactly.

Note: `questionnaire_answers` in `RiskAssessmentCreate` is a typed `QuestionnaireAnswers` Pydantic model. When `model_dump()` is called, it serialises it to a plain dict — which is what the JSON column stores.

---

## Concept 8: The QUESTIONNAIRE_QUESTIONS constant

```python
QUESTIONNAIRE_QUESTIONS = [
    {
        "key": "market_drop_reaction",
        "text": "If your portfolio dropped 20% overnight, what would you do?",
        "options": [
            {"value": "buy_more", "label": "Buy more — this is a great opportunity"},
            {"value": "hold",     "label": "Hold — wait for it to recover"},
            {"value": "sell",     "label": "Sell — I can't afford to lose more"},
        ],
    },
    ...
]
```

This is the canonical definition of the questionnaire. It's defined in `schemas/risk_assessment.py` (not the model) because it's presentation data — the API exposes it via `GET /risk-assessment/questions` so the frontend can render the form dynamically.

The values (`"buy_more"`, `"hold"`, `"sell"`) are the string keys used in Phase 4's scoring table:

```python
"market_drop_reaction": {"buy_more": 4, "hold": 2, "sell": 0}
```

The questionnaire schema and scoring table must stay in sync — a mismatch means the scoring service can't find answers.

---

## End-to-end request flows

### POST /users

```
POST /users
Body: {"name": "Rahul Sharma", "email": "rahul@example.com"}
         │
         ▼
FastAPI validates body → UserCreate(name="Rahul Sharma", email="rahul@example.com")
         │ (EmailStr validates email format)
         ▼
create_user(db, user) called
         │
         ├── User(name="Rahul Sharma", email="rahul@example.com") — in memory
         ├── db.add(new_user) — pending
         ├── await db.commit() — INSERT INTO users ... → id=1 assigned
         └── await db.refresh(new_user) — object now has id=1, etc.
         │
         ▼
FastAPI serialises ORM object → UserResponse(id=1, name="Rahul Sharma", email="rahul@example.com")
         │
         ▼
HTTP 200 {"id": 1, "name": "Rahul Sharma", "email": "rahul@example.com"}
```

### POST /risk-assessment

```
POST /risk-assessment
Body: {
  "user_id": 1,
  "questionnaire_answers": {
    "market_drop_reaction": "hold",
    "investment_experience": "beginner",
    ...
  }
}
         │
         ▼
FastAPI validates → RiskAssessmentCreate
  (QuestionnaireAnswers uses Literal types — invalid values rejected)
         │
         ▼
create_risk_assessment(db, data)
  data.model_dump() → {"user_id": 1, "questionnaire_answers": {...}}
  RiskAssessment(**...) → ORM object
  risk_score=None, risk_tier=None (not computed yet)
  db.add → commit → refresh
         │
         ▼
RiskAssessmentResponse returned
  risk_score: null, risk_tier: null (computed later by Phase 4)
```
