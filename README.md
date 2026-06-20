# Agentic Wealth Management Copilot

A personal finance and mutual fund recommendation system that assesses a user's
financial health, determines a risk profile, constructs a portfolio, selects
real funds, validates compliance against a policy engine, simulates goal
outcomes via Monte Carlo, and explains every recommendation in plain English —
while keeping deterministic rules in control of every high-stakes decision.

This README is written to carry full project context: what this is, why each
piece exists, what was rejected and why, and what's left to decide. It is
meant to be read by a future version of the author, by an interviewer, or by
a collaborator picking this up cold.

---

## 1. Why this project exists

This is a portfolio project built to demonstrate AI Engineer / GenAI Engineer
capability for the 2025–2026 hiring cycle, leveraging hands-on background in
LLM systems, RAG, and production AI infrastructure from enterprise RFP/sales
tooling (GTM Buddy).

The design goal is **not** to maximize buzzword density. It is to build a
system where every "agent," every guardrail, and every retrieval pipeline is
load-bearing — i.e. removing it would break something real, not just remove a
keyword from a resume. This document explicitly tracks where that standard
was applied and what got cut as a result.

### The filtering test

Before any component is labeled "agent," it must pass this test:

> **Would a single LLM call or a deterministic script suffice?**
> If yes, it is a pipeline stage or a service — not an agent.

A genuine agent makes a decision about what to do next based on intermediate
state: which tool to call, whether to retry, whether to broaden a query,
whether to escalate. A sequence of steps that always runs start-to-finish in
the same order, even if each step calls an LLM, is a **pipeline**, not a
multi-agent system. Mislabeling pipeline stages as agents is treated as a
credibility risk with technical interviewers, not a free win.

---

## 2. Project history — how we got here

This project went through several rounds of design and self-correction. That
history is preserved here deliberately, because the corrections are as
informative as the final design.

1. **Initial concept**: a simple mutual fund recommender — take in income,
   loans, EMIs, existing investments, ask the user to self-select a risk
   tier (4 options: Safest / Safer / Riskier / Riskiest), validate the choice,
   then filter and show 3 matching funds.

2. **First architecture pass** (separate, broader effort): a 13-keyword-category
   multi-agent RFP/enterprise system with input guardrails, intent classification,
   a multi-LLM sensitivity router (air-gapped self-hosted vs. cloud), hybrid
   retrieval, fine-tuning, hallucination evaluation, HITL queues, and full
   LLMOps tooling. This became the **reference keyword/architecture map**, not
   this project's literal design — most of those pieces don't have a genuine
   need in a personal finance tool (no multi-tenant confidential-data boundary,
   no HITL approver role, no SOC2/HIPAA-relevant data).

3. **Convergence**: the finance project absorbed the legitimate, transferable
   ideas from that broader map — RAG, hybrid retrieval, evaluation,
   observability, guardrails — while rejecting what didn't fit (multi-LLM
   sensitivity routing, RBAC/compliance theater, MCP, full HITL).

4. **"Final" agentic plan submitted for review**: an 8-step pipeline where
   nearly every step was labeled "Agent" (Risk Assessment Agent, Financial
   Health Agent, Portfolio Allocation Agent, Fund Research Agent, Compliance
   Agent, Monte Carlo Agent, Explanation Agent, Monitoring Agent). On
   scrutiny, this failed the filtering test for 6 of those 8 — most were
   deterministic functions or rule checks with no decision loop. Relabeled
   honestly: **2 real agents** (Fund Research, Compliance) **+ 1 policy
   guardrail + 9 pipeline stages/services**.

5. **Explainer chatbot proposal**: a "screenshot anything, ask what this
   means" feature. The screenshot/OCR mechanism was rejected — the backend
   already knows exactly what's on screen (it rendered it), so passing
   structured session state directly is strictly more accurate, cheaper, and
   faster than re-deriving the same numbers from an image. The user-facing
   feature (ask-anything explainer) was approved in concept as a context-
   routing agent, but **left out of the locked architecture** at the user's
   request — noted here in case it's revisited.

6. **Three additions proposed**: Market Regime Agent, Portfolio Review Agent,
   Recommendation Memory. All three passed scrutiny as conceptually sound but
   were scoped as **future prospects**, not v1, because each requires new
   data sourcing or new entry points that would meaningfully expand build
   time.

7. **Constraint surfaced late, applied retroactively**: no budget for paid
   LLM APIs. This changed five concrete decisions — see §6.

---

## 3. Core architectural principle: "LLM explains, rules decide"

This is the single most load-bearing design decision in the project, and the
one most likely to come up in an interview as a direct question
("how do you stop the LLM from hallucinating a financial recommendation?").

The rule: **deterministic logic makes every decision that affects money or
risk** (allocation %, pass/fail compliance, risk tier, simulation outputs).
The LLM is only ever used to **narrate a verdict that was already reached**
by rules, or to **decide which already-computed context to retrieve** before
narrating. It is never the thing computing the allocation, never the thing
deciding pass/fail on compliance, and never the source of the probability
number shown to the user.

This makes hallucination a UX/explanation-quality problem, not a financial-
risk problem — a wrong sentence is bad, but it can't produce a wrong
recommendation, because the recommendation was never the LLM's to make.

---

## 4. Final architecture

**Legend:** 🔧 pipeline stage / service · 🤖 genuine agent (real decision loop)
· 🛡️ policy / guardrail · 🔮 future prospect (designed, not built in v1)

### Core pipeline

| # | Step | Type | What it does | Stack / technique |
|---|------|------|---------------|--------------------|
| 1 | User Authentication | 🔧 | Persist identity across sessions | FastAPI, JWT, PostgreSQL |
| 2 | Financial Profile Intake | 🔧 | Compute net worth, savings rate, disposable income, DTI ratio, emergency-fund-months from income/EMIs/credit card dues/savings | FastAPI, Postgres (`financial_profiles`, versioned) |
| 3 | Goal Creation | 🔧 | Capture goal type, target amount, target date, current savings, monthly SIP | Postgres (`goals`) |
| 4 | Risk Scoring Service | 🔧 | Weighted score from age, horizon, quiz answers, income stability → suggested tier (Safest/Safer/Riskier/Riskiest); user can override | Deterministic scoring function, no LLM |
| 5 | Financial Health Check | 🔧 | Validate readiness to invest: emergency fund, debt burden, cash flow, savings rate | Rule engine, no LLM |
| 6 | Allocation Engine | 🔧 | Equity/debt/gold split from goal horizon + risk score + health status | Deterministic allocation function/lookup table |
| 7 | **Fund Research Agent** | 🤖 | Finds suitable funds; **decides** to broaden its query if too few matches, **decides** when to pull a factsheet via RAG for a borderline fund | Tool-calling, hybrid retrieval (BM25 + dense + RRF + cross-encoder rerank), MFAPI.in live data, curated metadata JSON |
| 8 | Investment Policy Engine | 🛡️ | Declarative limits: max equity for short-horizon goals, max single-fund allocation, max sector/smallcap exposure, min emergency-fund months | YAML rules-as-config, no LLM |
| 9 | **Compliance Agent** | 🤖 | Checks proposal against Policy Engine; on violation, **feeds back** to step 6, triggers revised allocation, **rechecks** — loops until pass or max retries | LangGraph conditional edge + checkpointing, audit log per attempt |
| 10 | Monte Carlo Simulation | 🔧 | 1000+ simulated scenarios → goal-success probability, calibrated from real historical index/debt return data | NumPy/SciPy |
| 11 | Explanation Generator | 🔧 | Plain-English narrative of the verdicts already computed in steps 4–10 | Single LLM call (local, open model), Pydantic-validated output |
| 12 | Portfolio Recommendation | 🔧 | Final display: allocation, funds, expected outcome, goal-success probability | React, `recommendations` table |
| 13 | Monitoring & Rebalancing | 🔧 | Scheduled (weekly/monthly): portfolio drift, goal progress, policy re-check | Celery + Redis |

### Why only 2 of 13 steps are agents

Steps 4, 5, 6, 10, 11 each take a fixed input and produce output through a
formula or single LLM call — no branching on intermediate state, no retry, no
tool selection. Steps 7 and 9 are different in kind: step 7 changes its own
behavior based on what it finds (broaden the search, or don't), and step 9
explicitly loops back into an earlier step based on what it discovers. That
difference — branching based on intermediate results, not just sequential
hand-off — is what "agent" should mean here, and is the line this project
holds even under the temptation to label more steps that way.

### Cross-cutting layers

**RAG Knowledge Base** (feeds step 7)
Real AMFI fund factsheets and SEBI investor-guideline PDFs — not a
conceptual placeholder. Chunked (fixed + semantic), embedded with an open
embedding model, stored in pgvector. This was a deliberate choice over using
the curated metadata JSON alone, specifically to avoid building something
labeled "RAG" that's actually just a database lookup.

**Evaluation Framework** (wraps steps 7, 9, 10, 11)
- Groundedness / faithfulness: was the explanation supported by retrieved evidence?
- Hallucination scoring on the Explanation Generator's output
- **Recommendation consistency**: re-run the identical financial profile
  multiple times, measure variance in allocation and fund selection — this
  metric exists specifically because non-determinism is a real problem in
  this domain, not a theoretical one
- Tools: Ragas, DeepEval (configured to use the local model as judge, not a
  paid API — see §6)

**Observability** (wraps every step)
- Self-hosted Langfuse: prompt versioning, cost/latency tracking, trace logging
- LangGraph's own checkpointing for the step 9 retry loop
- Audit logs: every compliance check, every recommendation, every policy violation

**Infrastructure**
Docker, GitHub Actions (CI/CD), PostgreSQL, pgvector, Redis, Celery, Ollama
(local model serving)

---

## 5. Data sources

| Source | Provides | Why this and not an alternative |
|---|---|---|
| MFAPI.in (`api.mfapi.in`) | Live scheme list, scheme metadata, daily NAV history for Indian mutual funds | Free, no-auth, no rate limiting, updated daily — confirmed alive and functional during planning. There is no free, stable, rich-metadata real-time alternative, so this is paired with curated data rather than relied on alone. |
| Curated metadata (self-maintained JSON/CSV) | Risk grade, expense ratio, fund category, AUM, fund age — fields MFAPI does not provide | Realistic engineering pattern: even production fintech apps cache slow-changing metadata rather than depending on a live feed for it. ~40–60 well-known funds across Equity/Debt categories is enough for v1. |
| AMFI fund factsheets (real PDFs) | Source documents for the RAG knowledge base | Public, downloadable per fund house. Used instead of a synthetic/placeholder corpus specifically to avoid a RAG layer that doesn't actually retrieve anything meaningful. |
| SEBI investor-guideline circulars (real PDFs) | Regulatory context for the RAG knowledge base and for grounding compliance explanations | Public documents on sebi.gov.in. |
| Historical index/debt returns | Calibration source for Monte Carlo's return/volatility assumptions | Used instead of arbitrary assumed distributions — the project is explicit in its own documentation about exactly which historical series and time window calibrate the simulation, since "what did you assume and why" is a near-certain interview question. |

**v1 fund universe scope: Equity + Debt only.** Hybrid, ELSS, and Index fund
categories are deliberately excluded from v1 to keep the filter/scoring logic
provably correct on a smaller surface before expanding category coverage.

---

## 6. Open-source constraint — what changed and why

No budget for paid LLM/API services. This is treated as a hard constraint,
not a temporary one, and it changed five concrete decisions versus the
original draft architecture:

| Component | Originally assumed | Now | Why |
|---|---|---|---|
| LLM serving (Explanation Generator, Fund Research Agent reasoning) | Cloud API (GPT-4o / Claude / Gemini) | Open model (e.g. Llama 3.1 8B class) served locally via **Ollama** | No per-call cost; also makes Ollama load-bearing rather than a vestigial stack entry that nothing actually uses |
| Cross-encoder reranker | Cohere rerank API | Open cross-encoder (e.g. BAAI/bge-reranker-base) via sentence-transformers | Same retrieval quality pattern, zero API cost |
| Embeddings | OpenAI / Cohere embeddings | Open embedding model (e.g. BAAI/bge-small-en or intfloat/e5-base) | Runs locally, compatible with pgvector |
| Evaluation LLM-judge (Ragas / DeepEval) | Default judge (commonly OpenAI under the hood) | Same libraries, pointed at the local Ollama model as judge | Avoids hidden API dependency inside an "open-source" eval stack — **this needs to be explicitly verified** when wiring up Ragas/DeepEval config, since defaults vary by version |
| Observability | LangSmith | Self-hosted **Langfuse** | LangSmith's free tier is cloud-hosted SaaS, not self-hostable; Langfuse is open source and covers both tracing and prompt versioning in one tool |

**Hardware sizing for the local model has not yet been finalized** — this is
an open item, not a decision. An 8B-class model via Ollama is the working
assumption; actual feasibility depends on available RAM/VRAM and should be
confirmed before implementation begins.

---

## 7. Future prospects (designed, explicitly not in v1)

These three were scrutinized and approved in concept, but deliberately scoped
out of v1 because each adds either new data-sourcing problems or new entry
points that would meaningfully expand build time. They are documented here
so the design intent isn't lost, and so "what would you build next" has a
ready, specific answer in an interview.

### 🔮 Market Regime Agent
Adjusts the equity ceiling that the Allocation Engine (step 6) produces,
before the Policy Engine (step 8) enforces it — bull market → raise the
equity ceiling, bear market → raise debt allocation. Uses macroeconomic data
(rates, index trend, volatility) and shows its reasoning.

**Honest agent test**: this only earns the 🤖 label if it has to *resolve
conflicting signals* (e.g. momentum says bull, volatility says risk-off). If
it's implemented as a fixed threshold check, it's a 🔧 service — the README
for whatever gets built should say plainly which one it is.

**Open risk**: requires a continuous live macro-data feed, which is a new
sourcing problem layered on top of the fund-data sourcing problem already
solved for v1.

### 🔮 Portfolio Review Agent
A second entry point: instead of building a portfolio from scratch, the user
uploads an existing one. The agent interprets the holdings (parses fund
names/codes, maps them to the metadata DB, flags ambiguous entries — this
interpretation step is the genuinely agentic part), then reuses the existing
**Policy Engine** for concentration/overlap checks and the existing **Fund
Research Agent + Explanation Generator** for improvement suggestions.

High reuse, low new-build cost relative to value — likely the first future
feature worth building after v1 ships.

### 🔮 Recommendation Memory
A structured table (`recommendation_outcomes`: recommendation_id, action
taken — accepted/rejected/modified, timestamp) that feeds back into the Fund
Research Agent's filtering (e.g. deprioritize fund types the user has
rejected twice) and the Explanation Generator's context.

Deliberately structured memory, not vector/semantic memory — chosen because
it has a specific, falsifiable purpose (does accept/reject history change
future output?) and is demonstrable with a clear before/after, rather than
"we embedded everything" with no clear retrieval trigger.

### Rejected, not deferred: Explainer Agent (screenshot-based)
A "screenshot any screen, ask what this means" chatbot was proposed and
partially scrutinized. The **concept** (ask-anything explainer grounded in
the user's own session data) was approved as sound and would be a legitimate
context-routing agent — deciding which upstream step's output is relevant to
a given question before answering (e.g. "why this fund" → step 7's filter
criteria; "why 81%" → step 10's simulation inputs; "what's DTI" → no
retrieval needed, static definition).

The **screenshot/OCR mechanism specifically** was rejected on technical
grounds, not deferred: the backend already has the exact structured data
that's on screen, so re-deriving it from an image is strictly worse on
accuracy, cost, and latency than passing the real session state directly.

This was ultimately **left out of the locked v1 architecture entirely** at
the user's request. It is recorded here, distinctly from the three approved
future prospects above, in case it's revisited later — if it is, the
context-routing version (not the screenshot version) is the one with a
defensible design.

### Explicitly rejected, not revisited
- **Knowledge Graph / Neo4j** — academically interesting, low ROI against
  build-time cost for this specific user journey
- **Multi-LLM sensitivity router** (air-gapped self-hosted vs. cloud, by
  data sensitivity) — carried over conceptually from a different project's
  architecture; rejected here because there's no real internal-confidential-
  data boundary in a single-user personal finance app
- **SOC2 / HIPAA compliance framing** — wrong domain (HIPAA is health data)
- **MCP protocol** — no real multi-tool external ecosystem need in this project
- **Full HITL (human-in-the-loop) review queue** — no human-approver role
  exists in a personal finance app's actual workflow

---

## 8. Data model (high-level)

- `users` — auth identity
- `financial_profiles` — versioned/timestamped snapshots of income, EMIs,
  credit card dues, existing investments, emergency fund; computed fields
  (net worth, savings rate, DTI, emergency-fund-months) stored alongside raw inputs
- `goals` — goal type, target amount, target date, current savings, monthly SIP
- `risk_assessments` — quiz answers, computed tier, user-overridden tier, timestamp
- `fund_metadata` — curated dataset: scheme code, category, risk grade,
  expense ratio, AUM, fund age
- `nav_cache` — scheme code, NAV, date (refreshed from MFAPI.in)
- `recommendations` — which funds were shown, for which assessment, when
- `policy_violations` (audit) — every compliance check attempt, pass/fail, reason
- *(future)* `recommendation_outcomes` — accept/reject/modify actions tied to past recommendations

---

## 9. Open items / not yet decided

These are tracked explicitly so they don't get silently assumed during
implementation:

1. **Hardware sizing** for the local Ollama-served model — not yet confirmed
   against actual available RAM/VRAM.
2. **Ragas/DeepEval judge configuration** — needs explicit verification that
   the local-model-as-judge path works cleanly in the library versions used;
   defaults often assume an OpenAI-compatible endpoint.
3. **Exact risk-scoring weights, DTI thresholds, and allocation-by-tier
   lookup table** — designed at the concept level (§4, step 4 and step 6) but
   not yet specified numerically.
4. **Exact Policy Engine YAML values** (max equity %, max single-fund %, max
   sector exposure %, min emergency-fund months) — referenced conceptually,
   not yet finalized.
5. **Monte Carlo's exact calibration source** — which historical index/debt
   series and what time window, specifically.
6. **Max retry count** for the Compliance Agent's revise-and-recheck loop
   before it gives up and surfaces a hard failure to the user.

---

## 10. Tech stack summary

**Frontend**: React
**Backend**: FastAPI, JWT, Pydantic
**Database**: PostgreSQL, pgvector
**Cache / Queue**: Redis, Celery
**Agentic orchestration**: LangGraph (compliance retry loop specifically)
**Retrieval**: BM25 + open dense embeddings + RRF + open cross-encoder reranker
**LLM serving**: Ollama (local, open model)
**Evaluation**: Ragas, DeepEval (local-model-judge configured)
**Observability**: self-hosted Langfuse, audit logs
**Infra**: Docker, GitHub Actions
**External data**: MFAPI.in, curated fund metadata, AMFI factsheets, SEBI circulars

**Cost profile**: zero ongoing API cost by design — every component that
would otherwise depend on a paid service has a verified open-source
substitute (see §6 for the substitution table and rationale).
