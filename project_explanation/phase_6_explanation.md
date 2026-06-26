# Phase 6 — Fund Data Layer: Full Deep Dive

---

## What is this phase doing conceptually?

Phases 3–5 are entirely about the investor — their finances, risk profile, and allocation. Phase 6 shifts focus to the **investment universe** — the actual mutual funds available to invest in.

The fund data layer has three responsibilities:
1. **Sync**: fetch live NAV and metadata for curated funds from the MFAPI.in public API
2. **Store**: upsert fund data into a `mutual_funds` PostgreSQL table
3. **Serve**: expose filtered queries so Phase 7's agent can search by category and risk grade

This is the first phase that makes **external HTTP calls** to a live API.

---

## Why curated funds, not all 8000+ AMFI funds?

India has over 8000 active mutual fund schemes. Fetching and storing all of them would be impractical (minutes of sync time, hundreds of MB of data) and unnecessary — retail investors don't need 8000 choices.

Instead, `backend/app/data/mutual_fund_metadata.json` contains 10 hand-picked funds across all major categories:

```
Large Cap, Mid Cap, Small Cap, Flexi Cap, Index, Gilt, Gold, Hybrid
```

This curation approach:
- Makes sync fast (10 API calls, not 8000)
- Provides a clean representative universe for the Phase 7 agent
- Can be easily extended (add more entries to the JSON file)

The JSON file provides metadata that MFAPI doesn't return: `category`, `risk_grade`, `expense_ratio`, `aum_in_crores`. MFAPI only returns name and NAV history.

---

## The MutualFund ORM Model

```python
class MutualFund(Base):
    __tablename__ = "mutual_funds"

    id            = Column(Integer, primary_key=True, index=True)
    scheme_code   = Column(String, unique=True, nullable=False, index=True)
    scheme_name   = Column(String, nullable=False)
    net_asset_value = Column(Float, nullable=True)
    nav_date      = Column(String, nullable=True)
    category      = Column(String, nullable=True)      # Large Cap, Mid Cap, Gilt, Gold...
    risk_grade    = Column(String, nullable=True)      # Low | Moderate | High | Very High
    expense_ratio = Column(Float, nullable=True)       # percentage (e.g. 0.54)
    aum_in_crores = Column(Float, nullable=True)       # AUM in Indian crores (₹)
    last_updated  = Column(DateTime(timezone=True), nullable=True,
                           default=func.now(), onupdate=func.now())
```

`scheme_code` is the fund's AMFI code — a unique identifier used across all mutual fund platforms and regulators. It's the primary lookup key (hence `unique=True` and `index=True`).

`net_asset_value` is nullable because the MFAPI call might fail for a specific fund — we don't want the whole sync to fail if one fund has no data.

`nav_date` is stored as `String` (not `Date`) because MFAPI returns dates as strings like `"30-Jun-2025"` — parsing them would add complexity without benefit here.

---

## Concept: Async HTTP with httpx

The original `requests` library is synchronous — it blocks the event loop while waiting for a response. In an async FastAPI application, you need an async HTTP client.

`httpx` is the async-native equivalent of `requests`. It has an identical API but supports `async with` and `await`:

```python
async with httpx.AsyncClient() as client:
    resp = await client.get(f"{MFAPI_BASE}/{scheme_code}", timeout=10)
    resp.raise_for_status()
    data = resp.json()
```

`async with httpx.AsyncClient()` — creates a client that reuses TCP connections across multiple requests (connection pooling). More efficient than creating a new client per request.

`timeout=10` — if the MFAPI doesn't respond within 10 seconds, raises `httpx.TimeoutException`. Without a timeout, a hung request would wait indefinitely.

`resp.raise_for_status()` — raises `httpx.HTTPStatusError` for 4xx/5xx responses. Combined with the outer `try/except Exception: return None` in `_fetch_fund`, any failed fund simply returns `None` without crashing the sync.

---

## Concept: asyncio.Semaphore — Concurrency Control

Fetching 10 funds one by one sequentially would take ~10 × network latency. Fetching all 10 simultaneously (fire all requests at once) could hit rate limits or overwhelm the API.

A `Semaphore` is the solution — it allows at most N concurrent operations at a time:

```python
_MAX_CONCURRENT = 10
semaphore = asyncio.Semaphore(_MAX_CONCURRENT)

async def _fetch_fund(client, semaphore, scheme_code, meta):
    async with semaphore:    # blocks if 10 requests are already in-flight
        resp = await client.get(...)
```

`async with semaphore:` — acquires a slot. If 10 slots are already taken, this coroutine pauses until one finishes. When the `async with` block exits, the slot is released.

With `_MAX_CONCURRENT = 10` and only 10 funds total, all requests run concurrently — the semaphore is effectively non-blocking here. It's in place for when the fund list grows beyond 10.

---

## Concept: asyncio.gather — Fan-out Concurrent Execution

```python
results = await asyncio.gather(
    *[
        _fetch_fund(client, semaphore, scheme_code, meta)
        for scheme_code, meta in metadata.items()
    ]
)
```

`asyncio.gather(*coroutines)` runs all coroutines concurrently and returns a list of their results in the same order as the input. The `*` unpacks the list comprehension into positional arguments.

This is the "fan-out" pattern:
1. Create all 10 `_fetch_fund` coroutines
2. Submit them all to the event loop simultaneously
3. Wait for all to complete
4. Collect results

Total time ≈ max(individual latency) instead of sum(individual latency).

---

## The Upsert Pattern

An "upsert" is insert-or-update: if the record exists, update it; if not, create it. SQLAlchemy doesn't have a built-in upsert method, so we implement it manually:

```python
# Step 1: fetch existing funds in one query
existing_result = await db.execute(
    select(MutualFund).where(MutualFund.scheme_code.in_(scheme_codes))
)
existing = {f.scheme_code: f for f in existing_result.scalars().all()}

# Step 2: for each fetched fund, update or create
for fund_data in fetched:
    fund = existing.get(fund_data["scheme_code"])
    if fund:
        # Update existing: set each attribute
        for key, value in fund_data.items():
            setattr(fund, key, value)
    else:
        # Create new
        db.add(MutualFund(**fund_data))

await db.commit()
```

**Why not query one by one?** `select(...).where(...in_(scheme_codes))` fetches all existing funds in a single SQL query. Querying inside the loop (`for each fund: SELECT WHERE scheme_code = ?`) would be N separate queries — the N+1 query problem.

**Why `setattr`?** When updating, we iterate over the dict and set attributes dynamically — `setattr(fund, "net_asset_value", 42.5)` is equivalent to `fund.net_asset_value = 42.5`. This handles all fields without writing them out individually.

**Why not use PostgreSQL's `ON CONFLICT DO UPDATE`?** We could use `insert(...).on_conflict_do_update(...)` from SQLAlchemy's dialect-specific API. But the manual approach is more readable, database-agnostic, and doesn't require understanding PostgreSQL-specific SQL syntax.

---

## Query Filtering

```python
async def get_all_mutual_funds(
    db: AsyncSession,
    category: Optional[str] = None,
    risk_grade: Optional[str] = None,
):
    query = select(MutualFund)
    if category:
        query = query.where(MutualFund.category == category)
    if risk_grade:
        query = query.where(MutualFund.risk_grade == risk_grade)
    result = await db.execute(query)
    return result.scalars().all()
```

Query building is composable — you start with `select(MutualFund)` and add `.where()` clauses only when filters are provided. No filter = return all funds. Both filters = AND condition.

In the endpoint:

```python
@app.get("/mutual-funds")
async def get_all_mutual_funds_endpoint(
    category: Optional[str] = None,
    risk_grade: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
):
    return await get_all_mutual_funds(db, category=category, risk_grade=risk_grade)
```

FastAPI automatically reads `category` and `risk_grade` from URL query parameters. `GET /mutual-funds?category=Large+Cap` → `category="Large Cap"`.

---

## End-to-end: POST /mutual-funds/sync

```
POST /mutual-funds/sync
         │
         ▼
sync_mutual_funds(db)
         │
         ├── _load_curated_metadata()
         │       opens mutual_fund_metadata.json
         │       returns dict: {"119598": {"category": "Large Cap", ...}, ...}
         │
         ├── _fetch_all_funds(metadata)
         │       creates asyncio.Semaphore(10)
         │       creates httpx.AsyncClient
         │       asyncio.gather(
         │           _fetch_fund(client, sem, "119598", meta_for_119598),
         │           _fetch_fund(client, sem, "100016", meta_for_100016),
         │           ... 10 total, all running concurrently
         │       )
         │       Each _fetch_fund:
         │           GET https://api.mfapi.in/mf/119598
         │           → {"meta": {"scheme_name": "Axis Bluechip Fund - Growth"},
         │              "data": [{"nav": "42.3", "date": "25-Jun-2025"}, ...]}
         │           returns {scheme_code, scheme_name, net_asset_value, nav_date,
         │                    category, risk_grade, expense_ratio, aum_in_crores}
         │
         ├── scheme_codes = ["119598", "100016", ...]
         ├── SELECT mutual_funds WHERE scheme_code IN (...)
         │       → existing dict {scheme_code: MutualFund object}
         │
         ├── For each fund_data:
         │       if exists → setattr each field (UPDATE)
         │       else → db.add(MutualFund(...)) (INSERT)
         │
         ├── await db.commit()
         │
         ▼
{"synced": 10, "failed": 0, "message": "Sync complete. 10 funds updated, 0 failed."}
```
