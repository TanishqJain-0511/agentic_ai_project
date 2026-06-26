# Phase 1 — Infrastructure: Full Deep Dive

---

## What is this phase doing conceptually?

Before writing a single line of financial logic, you need a running server that can accept HTTP requests and talk to a database. Phase 1 is entirely about infrastructure — no business logic, no financial math. Just: "can we stand up a web server backed by PostgreSQL, running inside Docker, with a clean project structure that every future phase builds on?"

Every architectural decision here — the layered folder structure, how SQLAlchemy sessions work, why Docker Compose — pays dividends across all 13 phases. Get this wrong and everything after is unstable.

---

## The 3-layer architecture

```
HTTP Request
    ↓
FastAPI (Uvicorn ASGI server)
    ↓
SQLAlchemy (ORM + Session)
    ↓
asyncpg driver
    ↓
PostgreSQL (in Docker container)
```

Every request enters at FastAPI, gets a SQLAlchemy session injected, uses that session to talk to PostgreSQL, and the session is cleaned up when the request ends.

---

## Concept 1: ASGI vs WSGI — Why FastAPI needs Uvicorn

### The old world: WSGI

Traditional Python web frameworks (Flask, Django) use **WSGI** (Web Server Gateway Interface). WSGI is synchronous — one request at a time per thread. If a request is waiting for a database query, the thread blocks. You need multiple threads/processes to handle concurrency.

### The new world: ASGI

**ASGI** (Asynchronous Server Gateway Interface) is the async equivalent. Instead of blocking while waiting for I/O, an ASGI server can suspend the current coroutine and run other requests. One process can handle thousands of concurrent connections efficiently.

FastAPI is an **ASGI framework** — it requires an ASGI server to run. That server is **Uvicorn**.

```
Browser → Uvicorn (ASGI server) → FastAPI (ASGI app) → your endpoint functions
```

Uvicorn listens on a port, accepts connections, and calls FastAPI's `__call__` method for each request. FastAPI routes it to the right endpoint function. The `async def` in endpoint functions is not optional — it's what makes this non-blocking.

### Why this matters for us

All services, endpoints, and database calls in this project are `async def`. The whole stack is async from top to bottom:

```
async def endpoint → async def service → await db.execute(...)
```

If you had used a sync driver (psycopg2 + sync SQLAlchemy), all those awaits would block the event loop and you'd lose the concurrency benefit entirely. That's why we later migrate to asyncpg.

---

## Concept 2: FastAPI — What it gives you

```python
from fastapi import FastAPI

app = FastAPI()

@app.get("/")
async def root():
    return {"message": "running"}
```

FastAPI does three things that matter:

### 1. Routing

`@app.get("/")` registers a route. FastAPI maps `GET /` → `root()`. It supports path parameters (`/users/{user_id}`), query parameters (`?category=`), and request bodies (via Pydantic).

### 2. Automatic serialisation

Return a dict or a Pydantic model — FastAPI serialises it to JSON automatically. Set `response_model=UserResponse` and FastAPI validates and filters the response shape.

### 3. OpenAPI/Swagger generation

Every endpoint you define appears in `/docs` automatically. FastAPI reads your type hints and Pydantic schemas to build the OpenAPI spec. This is why type hints are not optional — they're what generates the documentation.

---

## Concept 3: Docker and Docker Compose

### Why Docker?

You need PostgreSQL running locally. Without Docker, you'd install it manually, configure it, and it would conflict with other projects. Docker runs PostgreSQL in an isolated container — the rest of your machine is unaffected.

### Image vs Container

```
Image = blueprint (immutable template)
Container = running instance of an image
```

`postgres:17` is the image. `wealth_postgres` is the container running from it. You can have multiple containers from the same image.

### Volume

```yaml
volumes:
  - postgres_data:/var/lib/postgresql/data
```

By default, when a container stops, its filesystem is gone. A **volume** mounts a persistent directory. PostgreSQL stores data at `/var/lib/postgresql/data` inside the container — the volume maps that to `postgres_data` on the host. Your data survives container restarts.

### Port mapping

```yaml
ports:
  - "5432:5432"
```

Format: `"host_port:container_port"`. PostgreSQL listens on 5432 inside the container. `5432:5432` exposes it on the same port on your host machine. Your Python code connects to `localhost:5432` and Docker routes it to the container.

### docker-compose.yml structure

```yaml
services:
  postgres:
    image: postgres:17
    container_name: wealth_postgres
    environment:
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: postgres
      POSTGRES_DB: wealth_db
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data

  backend:
    build: .
    ports:
      - "8000:8000"
    depends_on:
      - postgres
    environment:
      - DATABASE_URL=postgresql+asyncpg://postgres:postgres@postgres:5432/wealth_db

volumes:
  postgres_data:
```

`depends_on` means Docker starts postgres before backend. Inside the Docker network, services reach each other by **service name** (`postgres`), not `localhost`. That's why `DATABASE_URL` uses `@postgres:5432` not `@localhost:5432` when running inside Docker.

---

## Concept 4: SQLAlchemy — The 3 core objects

The entire database layer is built on three objects defined in `database.py`.

### The Engine

```python
engine = create_async_engine(_async_url, echo=False)
```

The engine is a **connection factory** — it manages a pool of database connections but doesn't hold one open permanently. When you need a connection, it gives you one from the pool; when you're done, it returns it to the pool. `echo=False` suppresses SQL logging in production.

The engine lives for the lifetime of the application (created once at startup).

### The SessionFactory

```python
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)
```

`async_sessionmaker` is a factory for creating `AsyncSession` objects. Each `AsyncSession` is a **unit of work** — it tracks changes you've made (added objects, modified objects) and flushes them to the database when you commit.

`expire_on_commit=False` is important: by default, after a commit, SQLAlchemy expires all loaded objects (so the next access hits the DB again). Since we return ORM objects directly from service functions and the session is closed shortly after, we need the objects to stay usable — `expire_on_commit=False` keeps them populated.

### Base

```python
Base = declarative_base()
```

`Base` is the registry for all ORM models. Every model class that inherits from `Base` is registered in `Base.metadata`. When you call `Base.metadata.create_all(engine)`, SQLAlchemy looks at all registered models and creates their tables.

This is why `models/__init__.py` must import all models:

```python
# models/__init__.py
from backend.app.models.user import User
from backend.app.models.financial_profile import FinancialProfile
# ... etc
```

If a model isn't imported before `create_all`, SQLAlchemy doesn't know it exists and the table won't be created.

---

## Concept 5: get_db() — Dependency Injection pattern

```python
async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        yield session
```

This is an **async generator function** — a function that uses `yield` inside `async def`. It produces a value (the session) and then resumes after `yield` to clean up.

The `async with AsyncSessionLocal() as session:` block:
- Creates a session when entered
- Yields it to the endpoint
- Automatically closes it when exited (even if an exception occurs)

In FastAPI:

```python
@app.get("/users")
async def get_all_users(db: AsyncSession = Depends(get_db)):
    return await get_users(db)
```

`Depends(get_db)` tells FastAPI: before calling this endpoint, call `get_db()`, get the yielded value, and pass it as `db`. After the endpoint returns, FastAPI resumes the generator (closing the session).

One session per request. No shared state between requests. Thread-safe.

---

## Concept 6: pydantic-settings — Configuration

```python
# config.py
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    DATABASE_URL: str
    OLLAMA_HOST: str = "http://localhost:11434"

    class Config:
        env_file = ".env"

settings = Settings()
```

`BaseSettings` reads from environment variables and `.env` files automatically. `DATABASE_URL` has no default — if it's not in `.env` or the environment, startup fails with a clear error. `OLLAMA_HOST` has a default so it's optional.

The `.env` file:

```
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/wealth_db
```

Never commit `.env` to git — it contains credentials.

---

## Concept 7: init_db — Table creation on startup

```python
# init_db.py
async def init_db():
    async with engine.begin() as conn:
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        await conn.run_sync(Base.metadata.create_all)
```

Called once at application startup (via the `lifespan` context manager in `main.py`).

- `engine.begin()` opens a connection and starts a transaction
- `CREATE EXTENSION IF NOT EXISTS vector` enables pgvector (idempotent — safe to re-run)
- `conn.run_sync(Base.metadata.create_all)` runs the synchronous `create_all` inside the async connection — necessary because SQLAlchemy's schema creation API is synchronous

`create_all` is idempotent — it only creates tables that don't exist yet. Safe to run on every startup.

### Why not Alembic?

Alembic is the proper migration tool — it tracks schema changes and applies them incrementally. `create_all` is simpler but loses the ability to modify existing tables (it won't add a new column to an existing table). For a project in active development, Alembic is the right tool eventually. For early-phase development where you can drop and recreate the database freely, `create_all` is fast and simple.

---

## Concept 8: The lifespan pattern

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()    # startup: runs before first request
    yield              # application runs here
    await engine.dispose()  # shutdown: runs after last request

app = FastAPI(lifespan=lifespan)
```

FastAPI's `lifespan` parameter accepts an async context manager. Code before `yield` runs at startup; code after `yield` runs at shutdown.

`engine.dispose()` closes all connections in the pool when the app shuts down — clean teardown.

---

## Project Structure and Why

```
backend/app/
├── main.py          ← FastAPI app + all endpoint definitions
├── config.py        ← Settings (reads .env)
├── db/
│   ├── database.py  ← engine, AsyncSessionLocal, Base, get_db()
│   └── init_db.py   ← Base.metadata.create_all()
├── models/          ← SQLAlchemy ORM classes (DB tables)
│   └── __init__.py  ← Must import all models for init_db discovery
├── schemas/         ← Pydantic models (request/response validation)
├── services/        ← Business logic
├── agents/          ← LangGraph agents (future phases)
├── policies/        ← YAML rules (future phases)
└── utils/           ← Shared utility functions
```

**The golden rule**: business logic lives in `services/`, never in `main.py` endpoints. Endpoints are thin — they validate input (via Pydantic), call a service, and return the result. This makes services testable independently of HTTP.

---

## End-to-end request flow (Phase 1 example)

```
Browser: GET /health
          │
          ▼
Uvicorn receives HTTP request
          │
          ▼
FastAPI routes to health_check()
          │
          ▼
async def health_check():
    async with engine.connect() as connection:
        await connection.execute(text("SELECT 1"))
    return {"api": "healthy", "database": "healthy"}
          │
          ▼
FastAPI serialises dict → JSON
          │
          ▼
Uvicorn sends HTTP 200 response
```

The `SELECT 1` is a lightweight query that verifies the database connection is alive without touching any application tables. If PostgreSQL is down, the `except` block catches the error and returns `"database": "unhealthy"` — the API stays up even when the DB is not.
