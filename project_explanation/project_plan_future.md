# Future Project Plan — Agentic Wealth Management Copilot

> This document covers Phases 14–17: the next layer of features built on top of the completed
> Phases 1–13 (backend, RAG, agents, Monte Carlo, Streamlit frontend).
> All decisions here were confirmed interactively with the user.

---

## Phase 14: JWT Authentication + Login Page

**Goal**: Secure every Streamlit page behind a proper login wall. No more "anyone can access user_id=1".

### Why now
Right now there is zero auth — any user can load any user_id. Adding auth before the portfolio tracker and company research makes those features actually safe.

### Backend changes

#### New model: `backend/app/models/user.py` (update)
Add a `hashed_password` column to the existing `User` model.

```python
hashed_password: Mapped[str] = mapped_column(String, nullable=False)
```

#### New dependencies
```
passlib[bcrypt]    # password hashing
python-jose[cryptography]  # JWT encode/decode
```

#### New endpoints
| Method | Endpoint | Description |
|---|---|---|
| POST | `/auth/register` | Create user with hashed password, return JWT |
| POST | `/auth/login` | Verify credentials, return access + refresh token |
| POST | `/auth/refresh` | Exchange refresh token for new access token |
| GET | `/auth/me` | Return current user from JWT (protected) |

#### JWT design
- Algorithm: HS256
- Access token TTL: 30 minutes
- Refresh token TTL: 7 days
- Secret: `JWT_SECRET` in `.env`
- Claims: `sub` (user_id), `exp`, `iat`

#### New service: `backend/app/services/auth_service.py`
- `hash_password(plain: str) -> str` — bcrypt
- `verify_password(plain: str, hashed: str) -> bool`
- `create_access_token(user_id: int) -> str`
- `create_refresh_token(user_id: int) -> str`
- `decode_token(token: str) -> dict` — raises 401 on invalid/expired
- `get_current_user(token: ..., db: ...) -> User` — FastAPI dependency

#### New schema: `backend/app/schemas/auth.py`
- `RegisterRequest` — email, password, full_name
- `LoginRequest` — email, password
- `TokenResponse` — access_token, refresh_token, token_type

### Frontend changes

#### `frontend/pages/0_Login.py` (new — first page)
- Two tabs: **Login** / **Register**
- Login: email + password → POST `/auth/login` → store `access_token` in `st.session_state`
- Register: email + full_name + password → POST `/auth/register` → auto-login
- On success: `st.switch_page("pages/1_Financial_Profile.py")`

#### All existing pages: add auth guard at top
```python
if "access_token" not in st.session_state:
    st.switch_page("pages/0_Login.py")
```

#### `frontend/api_client.py` (update)
- Add `Authorization: Bearer {token}` header to all requests
- Add `refresh_token()` call on 401 response before retrying

### Acceptance criteria
- Unauthenticated users land on login page
- Tokens stored in `st.session_state` (lost on browser close — by design)
- All existing endpoints continue to work unchanged (auth is additive)
- Passwords never stored in plaintext

---

## Phase 15: Hybrid Search with RRF Fusion

**Goal**: Upgrade `POST /rag/retrieve` from pure vector search to BM25 + pgvector hybrid, fused with Reciprocal Rank Fusion (RRF). Better recall for exact-term queries (fund names, ticker symbols, SEBI rule IDs).

### Why now
Pure cosine similarity misses documents that are semantically distant but lexically exact (e.g., "HDFC Flexi Cap Fund" as a search term). BM25 handles this. RRF combines both rankings without needing a score normalisation step.

### Architecture

```
Query
  │
  ├──► BM25 index (pg_trgm or separate BM25 table) ──► ranked list A (top-50)
  │
  └──► pgvector cosine search ──────────────────────► ranked list B (top-50)
                                                              │
                                                         RRF Fusion
                                                              │
                                                        top-k results
```

### Implementation options

**Option A — pg_trgm (PostgreSQL built-in, simplest)**
- Enable `pg_trgm` extension
- Add GIN trigram index on `content` column of `document_chunks`
- BM25 approximated via trigram similarity (`similarity()` function)
- No extra infra, all inside existing PostgreSQL

**Option B — BM25 table (accurate)**
- Maintain a separate `bm25_index` table with term frequencies
- Update on every ingest
- More accurate but more code

**Recommended: Option A** — pg_trgm is good enough for this scale. Add a TODO for Option B if recall problems appear.

### RRF formula
```
RRF_score(doc, A, B) = 1/(k + rank_A(doc)) + 1/(k + rank_B(doc))
where k = 60 (standard constant)
```

### Code changes

#### `backend/app/db/init_db.py` (update)
```python
await conn.execute(text("CREATE EXTENSION IF NOT EXISTS pg_trgm;"))
```

#### `backend/app/models/document_chunk.py` (update)
Add GIN index on `content`, plus new fields:
```python
__table_args__ = (
    Index("ix_document_chunk_content_trgm", "content", postgresql_using="gin",
          postgresql_ops={"content": "gin_trgm_ops"}),
)

# New columns to add:
source_id: Mapped[str] = mapped_column(String, nullable=True, index=True)  # stable ID for a document (UUID or slug)
source_url: Mapped[str] = mapped_column(String, nullable=True)              # original URL of the ingested document
modified_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=func.now(), onupdate=func.now())
```

**Re-ingestion behaviour**: when a document is updated and re-ingested, delete existing chunks by `source_id` (not `source_name`). `source_name` is a human-readable label and may change; `source_id` is the stable key that uniquely identifies the document across updates.

#### `backend/app/services/rag_service.py` (update `retrieve_chunks`)
Replace single vector query with:
1. BM25 query: `SELECT id, content, ... FROM document_chunks WHERE content % :query ORDER BY similarity(content, :query) DESC LIMIT 50`
2. Vector query: existing cosine search, LIMIT 50
3. Python-side RRF fusion on the union of both result sets
4. Return top-k by RRF score

#### `backend/app/schemas/rag.py` (update)
Add `search_mode: Literal["vector", "bm25", "hybrid"] = "hybrid"` to `RAGRetrieveRequest`.

### Acceptance criteria
- `/rag/retrieve` returns `search_mode` in response
- Hybrid mode outperforms vector-only on exact fund name queries
- Fallback to vector-only if pg_trgm not available

---

## Phase 16: Company Research Agent

**Goal**: On-demand LangGraph agent that researches an Indian listed company using web scraping, NSE/BSE APIs, and Wikipedia/public filings, then stores the summary into the RAG knowledge base for future cross-company queries.

### Architecture

```
POST /company-research
         │
         ▼
  CompanyResearchAgent (LangGraph StateGraph)
         │
    ┌────┴──────────────────────────────────┐
    │                                       │
    ▼                                       ▼
tool: get_nse_fundamentals         tool: scrape_news_moneycontrol
  └─ PE, PB, ROE, debt ratio           └─ latest 10 headlines + snippets
    52w high/low, market cap
    │
    ▼
tool: get_analyst_ratings
  └─ scrape ET Markets / public
     consensus ratings page
    │
    ▼
tool: get_wikipedia_summary
  └─ company business description
     (fallback: first 500 chars)
    │
    ▼
LLM (llama3.2:3b)
  └─ synthesize into structured
     research report (markdown)
    │
    ▼
ingest_to_rag()
  └─ chunk + embed + store in
     document_chunks (pgvector)
    │
    ▼
Return CompanyResearchResponse
```

### Data sources per tool

| Tool | Source | Method | Data |
|---|---|---|---|
| `get_nse_fundamentals` | NSE India JSON API | `httpx.get` | PE, PB, ROE, debt/equity, 52w H/L, market cap, sector |
| `scrape_news_moneycontrol` | MoneyControl news page | `httpx` + `BeautifulSoup` | Latest 10 headlines + timestamps |
| `get_analyst_ratings` | ET Markets / screener.in | `httpx` + `BeautifulSoup` | Buy/Hold/Sell count, target price |
| `get_wikipedia_summary` | Wikipedia API (`/api/rest_v1/page/summary/`) | `httpx.get` | Business description paragraph |

### New files

```
backend/app/agents/company_research_agent.py   ← LangGraph StateGraph
backend/app/schemas/company_research.py        ← Request/Response Pydantic models
backend/app/services/company_research_service.py ← run_company_research()
backend/app/scrapers/
    nse_scraper.py                             ← NSE API wrapper
    moneycontrol_scraper.py                    ← MoneyControl news scraper
    et_markets_scraper.py                      ← ET Markets analyst ratings
    wikipedia_scraper.py                       ← Wikipedia summary
```

### Agent state (LangGraph)

```python
class CompanyResearchState(TypedDict):
    company_name: str
    nse_symbol: str
    fundamentals: dict          # from NSE
    news_headlines: list[str]   # from MoneyControl
    analyst_ratings: dict       # from ET Markets
    wiki_summary: str           # from Wikipedia
    research_report: str        # LLM synthesis
    rag_chunk_ids: list[int]    # IDs of stored chunks
    error: str | None
```

### Graph nodes
1. `resolve_symbol` — map company_name → NSE symbol (local lookup dict + NSE search API)
2. `parallel_data_fetch` — all 4 scraper tools run (sequential in v1, async in v2)
3. `synthesize_report` — LLM call: given fundamentals + news + ratings + wiki → markdown report
4. `store_in_rag` — call `ingest_document()` with report text, source="company_research", metadata={"symbol": ...}

### New endpoint

| Method | Endpoint | Description |
|---|---|---|
| POST | `/company-research` | Research a company, store in RAG, return report |

**Request:**
```json
{
  "company_name": "Infosys",
  "nse_symbol": "INFY",       // optional — auto-resolved if omitted
  "persist_to_rag": true       // default true
}
```

**Response:**
```json
{
  "company_name": "Infosys",
  "nse_symbol": "INFY",
  "fundamentals": { "pe": 24.3, "pb": 6.1, "roe": 31.2, "debt_equity": 0.04 },
  "analyst_consensus": { "buy": 18, "hold": 8, "sell": 2, "target_price": 1820 },
  "news_summary": ["Infosys Q4 profit up 11%...", "..."],
  "research_report": "## Infosys (INFY) — Research Summary\n...",
  "rag_chunk_ids": [42, 43, 44],
  "status": "success"
}
```

### New Streamlit page: `frontend/pages/6_Company_Research.py`
- Text input: company name (with NSE symbol hint)
- "Research" button → POST `/company-research`
- Display: fundamentals table, analyst rating bar, news headlines, full markdown report
- Show "Saved to knowledge base" confirmation with chunk IDs
- Graceful degradation if Ollama or scrapers are down

### New dependencies
```
httpx           # async HTTP (replaces requests for scrapers)
beautifulsoup4  # HTML parsing
lxml            # fast BS4 parser
```

### Acceptance criteria
- Agent resolves INFY, TCS, RELIANCE correctly
- Fundamentals populated from NSE API without hallucination
- Report stored in pgvector and retrievable via `/rag/retrieve`
- Graceful partial results if one scraper fails (others continue)
- Ollama unavailable → skip LLM synthesis, return raw data only

---

## Phase 17: Portfolio Tracker

**Goal**: Let users upload their existing mutual fund / stock holdings (CSV or manual entry), then compare their real allocation against the system's recommended allocation and show gap analysis.

### Why this is valuable
The system recommends equity/debt/gold splits but has no idea what the user currently holds. This phase closes the loop: "You hold 80% equity but your risk profile says 60% — here's what to rebalance."

### Input methods

**Option A — CSV upload**
Expected columns: `scheme_name`, `units`, `nav`, `current_value`, `category` (Equity/Debt/Gold)

**Option B — Manual entry**
Table-style form in Streamlit: add rows for each holding.

**Both options supported in v1.**

### New model: `backend/app/models/portfolio_holding.py`
```
PortfolioHolding
├── id (PK)
├── user_id (FK → users)
├── holding_type: "mutual_fund" | "stock" | "gold_etf" | "other"
├── name: str
├── category: "equity" | "debt" | "gold"
├── current_value: Decimal
├── units: Decimal (nullable)
├── nav: Decimal (nullable)
├── created_at, modified_at
```

### New endpoints
| Method | Endpoint | Description |
|---|---|---|
| POST | `/portfolio/upload-csv` | Parse CSV, store holdings |
| POST | `/portfolio/holdings` | Add single holding manually |
| GET | `/portfolio/{user_id}/holdings` | List all holdings |
| DELETE | `/portfolio/holdings/{holding_id}` | Remove a holding |
| GET | `/portfolio/{user_id}/analysis` | Gap analysis vs recommended allocation |

### Gap analysis logic (`portfolio_analysis_service.py`)
1. Fetch user's holdings from DB → compute actual equity/debt/gold split by current_value
2. Fetch recommended allocation from `/allocation` (already computed, stored in session or re-computed)
3. Compute delta: `gap = recommended_pct - actual_pct` for each asset class
4. Classify each gap: `overweight` (actual > recommended + 5%), `underweight` (actual < recommended - 5%), `on_track`
5. Generate rebalancing suggestion: "Shift ₹X from equity to debt funds"

### Response shape
```json
{
  "actual_allocation": { "equity_pct": 78.5, "debt_pct": 16.2, "gold_pct": 5.3 },
  "recommended_allocation": { "equity_pct": 60.0, "debt_pct": 35.0, "gold_pct": 5.0 },
  "gaps": [
    { "asset_class": "equity", "gap_pct": -18.5, "status": "overweight",
      "action": "Reduce equity by ₹1,85,000 (~18.5% of ₹10L portfolio)" },
    { "asset_class": "debt", "gap_pct": +18.8, "status": "underweight",
      "action": "Increase debt by ₹1,88,000" },
    { "asset_class": "gold", "gap_pct": -0.3, "status": "on_track", "action": null }
  ],
  "total_portfolio_value": 1000000.0
}
```

### New Streamlit page: `frontend/pages/7_Portfolio_Tracker.py`
- Tab 1 — Upload CSV: file uploader + preview table + confirm button
- Tab 2 — Manual Entry: add/remove holding rows
- After save: show current vs recommended allocation as side-by-side pie charts
- Gap table: color-coded (red = overweight, amber = underweight, green = on_track)
- Rebalancing suggestions list

### Acceptance criteria
- CSV with 5 rows imports in < 2 seconds
- Gap calculation is deterministic (same inputs → same output, no LLM involved)
- Rebalancing amounts sum correctly to zero net change
- Works even if user has no holdings yet (shows empty state gracefully)

---

## Dependency Summary (new packages across all phases)

```
# Phase 14 — Auth
passlib[bcrypt]
python-jose[cryptography]

# Phase 15 — Hybrid Search
# No new packages — pg_trgm is built into PostgreSQL

# Phase 16 — Company Research
httpx
beautifulsoup4
lxml

# Phase 17 — Portfolio Tracker
# No new packages
```

---

## Suggested Build Order

```
Phase 14 (Auth)           ← do first — gates everything behind login
     │
     ▼
Phase 15 (Hybrid Search)  ← quick win, pure backend, no new infra
     │
     ▼
Phase 16 (Company Research) ← biggest phase, builds on RAG + auth
     │
     ▼
Phase 17 (Portfolio Tracker) ← closes the loop, most user-visible value
```

---

## Open Questions / Future Considerations

- **Rate limiting on scrapers**: MoneyControl may block frequent scrapes. Add retry + backoff + randomised User-Agent rotation. Consider caching research results for 24h.
- **Symbol resolution**: NSE has ~1800 listed companies. Build a local `nse_symbols.json` lookup to avoid an API call per search.
- **Portfolio CSV format**: Brokers (Zerodha, Groww, Kite) export CSVs in different formats. May need per-broker parsers.
- **Refresh token rotation**: Phase 14 implements basic JWT. Add sliding refresh window in a future security hardening pass.
- **Phase 18 (Evaluation)**: Ragas + DeepEval for RAG pipeline quality scoring — especially important once company research is feeding production queries into the knowledge base.