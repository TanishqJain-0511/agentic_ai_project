# System Design — Agentic Wealth Management Copilot

> **High-level view**: how the user experiences the system end-to-end,
> what each layer is responsible for, and where external services plug in.

---

## Mermaid Diagram

```mermaid
flowchart TD
    U(["👤 Indian Retail Investor"])

    subgraph FE ["🖥️  Streamlit Frontend  •  localhost:8501"]
        direction LR
        P0["🏠 Home\nCreate / Load User"]
        P1["📊 Financial Profile\nIncome · Savings · Debt"]
        P2["🎯 Risk Assessment\nQuestionnaire + Score"]
        P3["📈 Allocation\nCompliance Agent"]
        P4["🔢 Simulation\nMonte Carlo SIP planner"]
        P5["💬 Explanation\nOllama plain-English"]
        P0 --> P1 --> P2 --> P3 --> P4 --> P5
    end

    subgraph BE ["⚙️  FastAPI Backend  •  localhost:8000  •  20+ async endpoints"]

        subgraph RULES ["🟢 Deterministic Engine  (Rules Decide)"]
            FH["Financial Health\nPhase 3"]
            RS["Risk Scoring\nPhase 4 · 4-component · 100-pt"]
            AE["Allocation Engine\nPhase 5 · Tier lookup + horizon cap"]
            PE["Policy Engine\nPhase 8 · YAML · 8 SEBI-inspired rules"]
            MC["Monte Carlo\nPhase 10 · NumPy · 1000–5000 scenarios"]
        end

        subgraph AG ["🔵 Agentic Layer  (LangGraph)"]
            CA["Compliance Agent\nPhase 9 · 3 nodes · deterministic loop\nno LLM"]
            FRA["Fund Research Agent\nPhase 7 · ChatOllama · 3 async tool closures\nLLM chooses tools"]
        end

        subgraph RAGL ["🟠 RAG Layer"]
            ING["POST /rag/ingest\nchunk → embed → pgvector"]
            RET["POST /rag/retrieve\nquery → embed → cosine search"]
        end

        EXP["Explanation Generator\nPhase 12 · single ChatOllama call\nnarrates computed verdicts"]

    end

    subgraph STORE ["🗄️  PostgreSQL 17  (asyncpg + pgvector)"]
        DB1[("Core Tables\nusers\nfinancial_profiles\ninvestment_goals\nrisk_assessments")]
        DB2[("mutual_funds\nscheme_code · nav · category\nrisk_grade · expense_ratio")]
        DB3[("document_chunks\n384-dim vector column\npgvector cosine <=>")]
    end

    subgraph LOCAL ["🏠 Local Services  (zero cloud cost)"]
        OL["🦙 Ollama\nllama3.1  →  fund research\nllama3.2:3b  →  explanation"]
        EM["🔢 sentence-transformers\nBAAI/bge-small-en-v1.5\n384-dim · lazy-loaded"]
    end

    EXT["🌐 MFAPI.in\nLive NAV data\nasync httpx + asyncio.Semaphore"]

    %% User flow
    U -->|"browser · port 8501"| FE
    FE -->|"HTTP requests\napi_client.py"| BE

    %% Backend → Storage
    RULES --> DB1
    RULES --> DB2
    CA --> DB1
    FRA -->|"DB tool closures\nSELECT mutual_funds"| DB2
    ING --> DB3
    RET -->|"cosine distance <=>"| DB3

    %% Backend → Local
    FRA --> OL
    EXP --> OL
    ING --> EM
    RET --> EM

    %% External sync
    BE -->|"POST /mutual-funds/sync"| EXT
    EXT -->|"upsert NAV + metadata"| DB2

    %% Styling
    style RULES fill:#e8f5e9,stroke:#388e3c,color:#1b5e20
    style AG   fill:#e3f2fd,stroke:#1976d2,color:#0d47a1
    style RAGL fill:#fff3e0,stroke:#f57c00,color:#e65100
    style LOCAL fill:#f3e5f5,stroke:#7b1fa2,color:#4a148c
    style EXT  fill:#fce4ec,stroke:#c62828,color:#b71c1c
```

---

## ASCII Fallback

```
┌────────────────────────────────────────────────────────────────────────────┐
│                      AGENTIC WEALTH MANAGEMENT COPILOT                     │
│                        "LLM explains, rules decide"                        │
└────────────────────────────────────────────────────────────────────────────┘

  👤 Indian Retail Investor
         │
         │  browser  localhost:8501
         ▼
┌──────────────────────────────────────────────────────────────────┐
│  STREAMLIT FRONTEND                                              │
│                                                                  │
│  [🏠 Home] → [📊 Financial] → [🎯 Risk] → [📈 Alloc] → [🔢 Sim] → [💬 Explain]  │
│   Create         Profile        Assessment  Compliance  Monte      Ollama    │
│   / Load User    + Health       + Score     Agent       Carlo      Narration │
└──────────────────────────────────────────────────────────────────┘
         │
         │  HTTP  api_client.py  localhost:8000
         ▼
┌──────────────────────────────────────────────────────────────────┐
│  FASTAPI BACKEND  (Uvicorn ASGI · 20+ async endpoints)           │
│                                                                  │
│  ┌────────────────────────────────────┐                          │
│  │  🟢 DETERMINISTIC ENGINE           │   Rules decide.          │
│  │  Financial Health  Phase 3         │   All computations are   │
│  │  Risk Scoring      Phase 4         │   pure math + lookup     │
│  │  Allocation        Phase 5         │   tables + YAML rules.   │
│  │  Policy Engine     Phase 8         │   No LLM involvement.    │
│  │  Monte Carlo       Phase 10        │                          │
│  └────────────────────────────────────┘                          │
│                                                                  │
│  ┌────────────────────────────────────┐                          │
│  │  🔵 AGENTIC LAYER  (LangGraph)     │                          │
│  │                                    │                          │
│  │  Compliance Agent  Phase 9         │   3-node StateGraph.     │
│  │  compute→check→fix→converge        │   No LLM. Deterministic  │
│  │                                    │   violation repair loop. │
│  │  Fund Research Agent  Phase 7      │   ChatOllama + 3 async   │
│  │  agent↔tools loop                  │   DB tool closures.      │
│  └────────────────────────────────────┘                          │
│                                                                  │
│  ┌────────────────────────────────────┐                          │
│  │  🟠 RAG LAYER  Phase 11            │   LLM explains.          │
│  │  /rag/ingest  /rag/retrieve        │   Chunk → embed →        │
│  │                                    │   pgvector cosine <=>    │
│  └────────────────────────────────────┘                          │
│                                                                  │
│  🟣 Explanation Generator  Phase 12  single ChatOllama call      │
└──────────────────────────────────────────────────────────────────┘
         │                         │                        │
         ▼                         ▼                        ▼
┌──────────────────┐    ┌─────────────────┐    ┌────────────────────┐
│ PostgreSQL 17    │    │ 🦙 Ollama (local)│    │  🌐 MFAPI.in       │
│ + pgvector       │    │                 │    │  Live NAV Data     │
│                  │    │ llama3.1        │    │  async httpx       │
│ users            │    │ (fund research) │    │  asyncio.Semaphore │
│ financial_...    │    │                 │    │  10 curated funds  │
│ risk_assess...   │    │ llama3.2:3b     │    │                    │
│ mutual_funds     │    │ (explanation)   │    └────────────────────┘
│ document_chunks  │    └─────────────────┘
│ (384-dim vecs)   │
│ asyncpg driver   │    ┌─────────────────────────────┐
└──────────────────┘    │ 🔢 sentence-transformers     │
                        │ BAAI/bge-small-en-v1.5       │
                        │ 384-dim · locally run        │
                        │ lazy-loaded on first use     │
                        └─────────────────────────────┘
```

---

## Phase → Responsibility Mapping

| Phase  | Component                         | Responsible For                              | LLM?    |
|--------|-----------------------------------|----------------------------------------------|---------|
| 1      | FastAPI + Docker + SQLAlchemy     | Infrastructure scaffold                      | No      |
| 2      | ORM models + CRUD services        | Data persistence layer                       | No      |
| 3      | `financial_health_service`        | Net worth, savings rate, DTI, emergency fund | No      |
| 4      | `risk_scoring_service`            | 4-component risk score → tier                | No      |
| 5      | `allocation_service`              | Tier lookup + horizon cap                    | No      |
| 6      | `mutual_fund_data_service`        | async httpx sync from MFAPI.in               | No      |
| 7      | `fund_research_agent` (LangGraph) | LLM picks funds from DB via tools            | **Yes** |
| 8      | `policy_engine`                   | YAML rule evaluation                         | No      |
| Pre-9  | Async DB migration                | psycopg2 → asyncpg                           | No      |
| 9      | `compliance_agent` (LangGraph)    | Deterministic compute→check→fix loop         | No      |
| 10     | `simulation_service`              | NumPy Monte Carlo, success probability       | No      |
| 11     | `rag_service` + pgvector          | Document chunk ingestion + retrieval         | No      |
| 12     | `explanation_service`             | Narrate verdicts in plain English            | **Yes** |
| 13     | Streamlit frontend                | 5-page UI, session state, api_client         | No      |

**LLM is used in exactly 2 of 14 components** — and in both cases it only narrates or retrieves, never decides.

---

## Key Design Decisions

| Decision        | Choice                     | Rationale                                                                      |
|-----------------|----------------------------|--------------------------------------------------------------------------------|
| LLM role        | Narration + retrieval only | "LLM explains, rules decide" — financial decisions must be auditable           |
| Database        | PostgreSQL + pgvector      | Single infrastructure component handles both structured data and vector search |
| LLM runtime     | Ollama (local)             | Zero API cost, data privacy, no rate limits                                    |
| Async driver    | asyncpg (not psycopg2)     | Non-blocking I/O across the full ASGI stack                                    |
| Agent loop      | LangGraph StateGraph       | Explicit state machine for predictable, debuggable agent behaviour             |
| Embedding model | BAAI/bge-small-en-v1.5     | 384-dim — fast local inference, sufficient quality for financial text          |
| Rules storage   | YAML (not Python)          | Financial rules readable by compliance team without code changes               |
