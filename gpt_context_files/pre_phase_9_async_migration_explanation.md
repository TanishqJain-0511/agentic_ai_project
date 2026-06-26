# Pre-Phase 9 — Async DB Stack Migration: Full Deep Dive

---

## What happened and why

Before Phase 9, every database call in the application was **synchronous** — using `psycopg2-binary` as the driver and 
`Session` (not `AsyncSession`) from SQLAlchemy. Services like `get_users` called `db.execute()` without `await`.

Phase 9 introduced the **Compliance Agent** — a LangGraph graph where nodes are `async def`. 
LangGraph requires a fully async callstack: `await agent.ainvoke()`, which means every function it calls must also be async. 
The `compliance_agent.py` has a node (`compute_allocation_node`) that queries the database — this means the DB layer had to be async too.

Rather than having a mixed sync/async codebase (messy and error-prone), we migrated the entire stack:

```
Before: psycopg2 + Session + sync services
After:  asyncpg + AsyncSession + async services
```

---

## Concept 1: Why sync DB blocks async FastAPI

FastAPI runs on an async event loop (via Uvicorn). The event loop is single-threaded — it runs one coroutine at a time, switching between them whenever a coroutine `await`s something.

If you do a **blocking** operation (like a sync database query via psycopg2), you don't yield control to the event loop — you block the thread entirely. While your request waits for the DB, no other request can run. This eliminates the concurrency benefit of async.

```
Event loop thread:
  ┌─────────────────────────────────────────────┐
  │ Request A starts                            │
  │ db.execute(SELECT ...) ← sync, BLOCKS       │
  │ ... event loop is stuck here ...            │  ← Request B cannot run
  │ Result returns, Request A continues         │
  │ Request A finishes                          │
  │ Request B starts (finally)                  │
  └─────────────────────────────────────────────┘
```

With async:
```
Event loop thread:
  ┌─────────────────────────────────────────────┐
  │ Request A starts                            │
  │ await db.execute(SELECT ...)                │
  │   ← yields control to event loop           │
  │   Request B starts running here            │
  │   Request B awaits its DB call             │
  │   Request A's DB result arrives            │
  │ Request A continues                         │
  │ ...                                         │
  └─────────────────────────────────────────────┘
```

Both requests make progress concurrently without threading.

---

## Concept 2: asyncpg vs psycopg2

`psycopg2-binary` is a C extension that wraps libpq (PostgreSQL's C client library). It's synchronous by nature.

`asyncpg` is a pure-Python async PostgreSQL driver written from scratch for `asyncio`. It speaks the PostgreSQL 
wire protocol directly without libpq. It's also significantly faster than psycopg2 for most workloads.

The URL scheme changes to tell SQLAlchemy which driver to use:

```python
# Before
"postgresql+psycopg2://user:pass@host/db"

# After
"postgresql+asyncpg://user:pass@host/db"
```

The `database.py` handles this transformation automatically:

```python
_raw_url = settings.DATABASE_URL
if _raw_url.startswith("postgresql+psycopg2://"):
    _async_url = _raw_url.replace("postgresql+psycopg2://", "postgresql+asyncpg://", 1)
elif _raw_url.startswith("postgresql://"):
    _async_url = _raw_url.replace("postgresql://", "postgresql+asyncpg://", 1)
else:
    _async_url = _raw_url
```

This normalises whatever URL format is in `.env` to the asyncpg dialect. You can keep `postgresql://` in `.env` and the code upgrades it automatically.

---

## Concept 3: create_async_engine

```python
# Before
from sqlalchemy import create_engine
engine = create_engine(DATABASE_URL)

# After
from sqlalchemy.ext.asyncio import create_async_engine
engine = create_async_engine(_async_url, echo=False)
```

`create_async_engine` creates an engine backed by asyncpg. 
All operations on this engine (`engine.connect()`, `engine.begin()`) return async context managers that you `await`.

`echo=False` — suppresses SQL logging. `echo=True` during development prints every SQL statement — useful for debugging but verbose in production.

---

## Concept 4: async_sessionmaker

```python
# Before
from sqlalchemy.orm import sessionmaker
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# After
from sqlalchemy.ext.asyncio import async_sessionmaker
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)
```

`async_sessionmaker` is the async version of `sessionmaker`. The `autocommit=False, autoflush=False` options from 
the sync version are the defaults in async — no need to specify them.

`expire_on_commit=False` — after an async commit, SQLAlchemy would normally expire all loaded objects 
(so the next attribute access triggers a new SELECT). Since we close the session immediately after returning from 
a service, we need the objects to stay readable. `expire_on_commit=False` keeps attribute values in memory.

---

## Concept 5: async get_db() — Async Generator

```python
# Before
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# After
async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        yield session
```

`async def get_db()` with `yield` makes it an **async generator function**. FastAPI handles async generators in 
`Depends()` the same way it handles sync generators.

`async with AsyncSessionLocal() as session:` — uses the async context manager protocol. 
On entry: creates a session. 
On exit: automatically closes the session (and rolls back uncommitted transactions if an exception occurred).

The `finally: db.close()` from the sync version is replaced by the `async with` context manager — cleaner and exception-safe.

### Why AsyncGenerator type hint?

```python
async def get_db() -> AsyncGenerator[AsyncSession, None]:
```

`AsyncGenerator[YieldType, SendType]` — this function yields `AsyncSession` objects and 
accepts `None` as sent values (the standard for generators used with `Depends`). 
The type hint is for IDE auto-complete and type checking; FastAPI doesn't use it at runtime.

---

## Concept 6: async def lifespan

```python
# Before (using @app.on_event which is deprecated)
@app.on_event("startup")
async def startup():
    await init_db()

# After
from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield
    await engine.dispose()

app = FastAPI(lifespan=lifespan)
```

`@asynccontextmanager` converts an async generator function into an async context manager. 
Code before `yield` = startup. Code after `yield` = shutdown.

`await engine.dispose()` — gracefully closes all connections in the pool on shutdown. 
Without this, open connections are dropped when the process exits, which can cause PostgreSQL to log errors.

This is the modern FastAPI pattern (the old `@app.on_event` is deprecated since FastAPI 0.93).

---

## Concept 7: How all services changed

The changes across all 8 service files follow the same pattern:

```python
# Before (sync)
from sqlalchemy.orm import Session

def create_user(db: Session, user: UserCreate):
    new_user = User(name=user.name, email=user.email)
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return new_user

def get_users(db: Session):
    return db.query(User).all()

# After (async)
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

async def create_user(db: AsyncSession, user: UserCreate):
    new_user = User(name=user.name, email=user.email)
    db.add(new_user)
    await db.commit()
    await db.refresh(new_user)
    return new_user

async def get_users(db: AsyncSession):
    result = await db.execute(select(User))
    return result.scalars().all()
```

Three changes per service:
1. `Session` → `AsyncSession`
2. `def` → `async def`
3. `db.commit()`, `db.refresh()`, `db.execute()` get `await`

The **query syntax** also changes fundamentally:
- Sync: `db.query(User).filter(User.id == user_id).first()` — ORM-style query builder
- Async: `await db.execute(select(User).where(User.id == user_id))` 
- then `result.scalar_one_or_none()` — Core Expression Language style

The async SQLAlchemy doesn't support the old `.query()` API directly. 
You must use `select()` from SQLAlchemy Core and call `db.execute(select_statement)`.

---

## Concept 8: init_db async

```python
# Before
def init_db():
    Base.metadata.create_all(bind=engine)

# After
async def init_db():
    async with engine.begin() as conn:
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        await conn.run_sync(Base.metadata.create_all)
```

`engine.begin()` opens a connection and starts a transaction (auto-commits on success, rolls back on exception).

`await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))` — executes raw SQL async. 
This enables pgvector (needed for Phase 11).

`await conn.run_sync(Base.metadata.create_all)` — the `create_all` method is synchronous 
(SQLAlchemy's schema creation API hasn't been made async). `run_sync` runs a synchronous callable 
inside the async connection — it's the bridge between the sync schema API and the async connection.

---

## Impact summary

| Component         | Before                        | After                              |
|-------------------|-------------------------------|------------------------------------|
| Driver            | psycopg2-binary               | asyncpg                            |
| URL scheme        | `postgresql://`               | `postgresql+asyncpg://`            |
| Engine            | `create_engine`               | `create_async_engine`              |
| Session factory   | `sessionmaker`                | `async_sessionmaker`               |
| Session type      | `Session`                     | `AsyncSession`                     |
| get_db            | `def get_db()`                | `async def get_db()`               |
| Service functions | `def func(db: Session)`       | `async def func(db: AsyncSession)` |
| DB calls          | `db.execute(...)`             | `await db.execute(...)`            |
| Query API         | `db.query(Model).filter(...)` | `select(Model).where(...)`         |
| Startup           | `@app.on_event("startup")`    | `@asynccontextmanager lifespan`    |
| Commit            | `db.commit()`                 | `await db.commit()`                |

No change to:
- ORM models (same Column/relationship definitions)
- Pydantic schemas
- Route definitions in `main.py` (endpoints were already `async def`)
- Business logic within services (the math and rules didn't change)
