# BRAINSTORM: InfoAgent

> Exploratory session to clarify intent and approach before requirements capture

## Metadata

| Attribute | Value |
|-----------|-------|
| **Feature** | INFOAGENT |
| **Date** | 2026-04-25 |
| **Author** | brainstorm-agent |
| **Status** | ✅ Complete (Defined — see DEFINE_INFOAGENT.md) |

---

## Initial Idea

**Raw Input:** Create InfoAgent project — a multi-agent AI system that translates natural language business questions into precise SQL queries and RAG-grounded answers, delivered through a chat interface for C-Level executives.

**Context Gathered:**
- Full kickoff document analyzed into `notes/summary-requirements.md` (15 decisions, 13 FRs, 6 NFRs, 10 open questions)
- Star Schema (2 fact tables + 4 dimension tables) fully specified in PostgreSQL/ANSI SQL
- 3-layer architecture already decided: INGEST → CONTEXTUALIZE → AGENT
- Tech stack largely decided except LLM provider and orchestration framework
- Knowledge Base available: ShadowTraffic, Pydantic, CrewAI, DW patterns

**Technical Context Observed (for Define):**

| Aspect | Observation | Implication |
|--------|-------------|-------------|
| Likely Location | Monorepo: `ingest/`, `contextualize/`, `agent/`, `ui/` | Single repo, one `docker compose up` |
| Relevant KB Domains | shadowtraffic, pydantic, dw, crewai | Patterns to consult during build |
| IaC Patterns | Docker Compose for dev; no cloud IaC decided | Infrastructure is local-first for MVP |

---

## Discovery Questions & Answers

| # | Question | Answer | Impact |
|---|----------|--------|--------|
| 1 | Where to start for MVP? | **(a) Bottom-up — INGEST first** | Data quality is the foundation; no AI work until data flows correctly through Pydantic validation |
| 2 | Target data scale for synthetic dataset? | **(b) Medium/demo-ready** — ~100K rows FATO_VENDAS, 1-2 years, seasonal patterns | ShadowTraffic needs state machines for seasonal spikes; FLG_FERIADO must drive realistic holiday data |
| 3 | LLM provider? | **(b) Anthropic (Claude Sonnet/Opus)** | Claude's native `tool_use` API maps cleanly onto MCP server tools; strong SQL reasoning; structured outputs via Pydantic |

---

## Sample Data Inventory

> Both executive question examples and KPI definitions are available — high-value for LLM grounding.

### Executive Questions (13 confirmed samples)

| # | Question | Query Type | Key Tables |
|---|----------|-----------|------------|
| 1 | What were the sales figures for yesterday? | Type 1 — Pure SQL | FATO_VENDAS, DIM_TEMPO |
| 2 | What was the gross profit margin for Smartphones over the past week vs preceding week? | Type 2 — KPI SQL | FATO_VENDAS, DIM_PRODUTO, DIM_TEMPO |
| 3 | What is the total capital tied up in inventory for TV/Audio at stores [X]? | Type 1 — Pure SQL | FATO_ESTOQUE, DIM_PRODUTO, DIM_LOJA |
| 4 | Which 5 stores had the lowest Notebook sales this quarter + managers? | Type 1 — Pure SQL | FATO_VENDAS, DIM_LOJA, DIM_PRODUTO, DIM_TEMPO |
| 5 | What is the overall sales performance? | Type 1 — Pure SQL | FATO_VENDAS |
| 6 | Did the flagship store outperform the average during the last holiday? | Type 1 — SQL + FLG_FERIADO | FATO_VENDAS, DIM_LOJA, DIM_TEMPO |
| 7 | Which 3 Computing subcategories generated losses or <10% margin last month? | Type 2 — KPI SQL | FATO_VENDAS, DIM_PRODUTO, DIM_TEMPO |
| 8 | Is there a stockout risk for PS5 at mall locations heading into this weekend? | Type 1 — Threshold SQL | FATO_ESTOQUE, DIM_PRODUTO, DIM_LOJA, DIM_TEMPO |
| 9 | Yesterday's Home Appliances sales were R$ [X], a [Y]% increase over previous day | Type 1 — Report validation | FATO_VENDAS, DIM_PRODUTO, DIM_TEMPO |
| 10 | What is our attachment rate (cross-sell rate) within the Mobile category? | Type 2 — KPI SQL | FATO_VENDAS, DIM_PRODUTO |
| 11 | Customers who bought Premium Smartphones — how many added headphones or cases? | Type 1 — Cohort SQL | FATO_VENDAS, DIM_PRODUTO, DIM_CLIENTE |
| 12 | What is the financial impact of Inverter Refrigerators on total revenue this month? | Type 2 — KPI SQL | FATO_VENDAS, DIM_PRODUTO, DIM_TEMPO |
| 13 | Does inventory turnover at mall locations justify their showroom space? | Type 3 — Hybrid SQL+RAG | FATO_ESTOQUE, DIM_LOJA + Qdrant (DSI definition) |

**Query Type Classification:**
- **Type 1 — Pure SQL:** Straightforward aggregation, filtered by dimension attributes. SQL Agent handles alone.
- **Type 2 — KPI-grounded SQL:** Requires Qdrant KPI definitions before SQL can be written (e.g., GMROI formula). RAG context injected into SQL Agent prompt.
- **Type 3 — Hybrid:** SQL result + qualitative judgment requiring business rules from Qdrant.

### KPI Definitions (9 confirmed — Qdrant seed content)

| KPI | Formula | Source Tables |
|-----|---------|---------------|
| Gross Profit Margin (%) | (Total Revenue - COGS) / Total Revenue | FATO_VENDAS (VALOR_TOTAL, CUSTO_TOTAL) |
| GMROI | Gross Margin / Average Inventory Cost | FATO_VENDAS, FATO_ESTOQUE |
| Category Revenue Share (%) | Category Revenue / Total Revenue | FATO_VENDAS, DIM_PRODUTO |
| Inventory Turnover / DSI | (Avg Inventory / COGS) × 365 | FATO_ESTOQUE, FATO_VENDAS |
| Out-of-Stock (OOS) Rate (%) | Items with zero inventory / Total active SKUs | FATO_ESTOQUE, DIM_PRODUTO |
| Sell-Through Rate (%) | Total Units Sold / Total Units Received | FATO_VENDAS, FATO_ESTOQUE |
| Average Order Value (AOV) | Total Revenue / Total Transactions | FATO_VENDAS |
| Units Per Transaction (UPT) | Total Units Sold / Total Transactions | FATO_VENDAS |
| Loyalty Program Contribution (%) | Revenue from Loyalty Members / Total Revenue | FATO_VENDAS, DIM_CLIENTE |

**How samples will be used:**
- KPI definitions → seeded verbatim into Qdrant as the RAG knowledge base
- Executive questions → few-shot examples in SQL Agent system prompt for query style grounding
- Type classification → defines routing logic in the LangGraph classifier node
- KPI formulas → map directly to FATO_VENDAS columns (VALOR_TOTAL, CUSTO_TOTAL, VALOR_UNITARIO) for query construction validation

---

## Approaches Explored

### Approach A: Layered Monorepo + LangGraph ⭐ Recommended

**Description:** Single Python monorepo with 4 clearly separated modules (`ingest/`, `contextualize/`, `agent/`, `ui/`). LangGraph orchestrates a routing graph with conditional edges for the 3 query types. Claude's `tool_use` connects to the MCP server.

**Pros:**
- `docker compose up` spins the entire stack — PostgreSQL + ShadowTraffic + Qdrant + MCP + Chainlit
- LangGraph's conditional edges map exactly to the 3 query types (Type 1 → SQL, Type 2 → RAG→SQL, Type 3 → SQL+RAG)
- Stateful conversations via LangGraph state — executives can ask follow-ups ("And last year?")
- Each layer is independently testable before integration
- Graph traversal can be streamed directly to Chainlit's Chain of Thought panel

**Cons:**
- LangGraph has more initial boilerplate than CrewAI
- Steeper learning curve for the routing graph definition

**Why Recommended:** The 3 query type classification (discovered from sample questions) requires conditional routing that LangGraph handles natively. CrewAI's crew model would require workarounds for the same logic.

---

### Approach B: Monorepo + CrewAI

**Description:** Same directory structure but uses CrewAI for agent orchestration. Agents defined as crew "roles".

**Pros:**
- Faster to write initial agent configuration (declarative role definitions)
- Lower boilerplate for simple sequential agent flows

**Cons:**
- CrewAI's sequential/hierarchical processes are not well-suited to conditional routing (the core requirement)
- Less mature Anthropic `tool_use` integration than LangGraph
- Crew memory doesn't carry conversation context as naturally across follow-up questions

---

### Approach C: Notebooks-first Prototype

**Description:** Validate each layer in Jupyter notebooks before writing production code.

**Pros:**
- Fastest initial feedback loop
- Easy to share intermediate results with stakeholders

**Cons:**
- High risk of prototype code becoming production code
- Hard to Docker-ify or modularise after the fact
- Not appropriate when architecture is already well-defined (this project is)

---

## Selected Approach

| Attribute | Value |
|-----------|-------|
| **Chosen** | Approach A — Layered Monorepo + LangGraph |
| **User Confirmation** | 2026-04-25 |
| **Reasoning** | Bottom-up build order + 3 query types requiring conditional routing + stateful executive conversations |

---

## Component Breakdown (Validated)

### Layer 1 — INGEST (`ingest/`)

| Component | Technology | Responsibility |
|-----------|------------|----------------|
| `shadowtraffic/` | ShadowTraffic JSON | ~100K FATO_VENDAS rows, 2 years, seasonal spikes via FLG_FERIADO state machine |
| `models/` | Pydantic v2 | 6 models (ModeloFatoVendas, ModeloFatoEstoque, ModeloDimProduto, ModeloDimCliente, ModeloDimLoja, ModeloDimTempo) — shared across all layers |
| `loaders/` | psycopg2 + Pydantic | Validate ShadowTraffic output → insert into PostgreSQL |
| `docker-compose.yml` | Docker | PostgreSQL + ShadowTraffic services; `make seed` to populate |

### Layer 2 — CONTEXTUALIZE (`contextualize/`)

| Component | Technology | Responsibility |
|-----------|------------|----------------|
| `mcp_server/` | MCP Python SDK | Exposes `list_tables()`, `describe_schema()`, `execute_read_only_query()` to Claude |
| `qdrant_ingest/` | Qdrant + LlamaIndex | Seeds 9 KPI definitions, data dictionary, store org chart into vector store |
| `kpi_definitions.md` | Markdown | Source of truth for all 9 KPIs — owned by business analysts, ingested into Qdrant |
| `few_shot_examples.md` | Markdown | 13 executive questions + expected SQL — injected into SQL Agent system prompt |

### Layer 3 — AGENT (`agent/`)

| Component | Technology | Responsibility |
|-----------|------------|----------------|
| `graph.py` | LangGraph | Routing graph: `classify_query` node → conditional edge → `sql_agent` / `rag_agent` / `hybrid_agent` |
| `sql_agent.py` | LangGraph + Claude tool_use | Inspects schema via MCP, writes PostgreSQL query, validates output with Pydantic |
| `rag_agent.py` | LangGraph + LlamaIndex | Retrieves KPI context from Qdrant for metric/context questions |
| `hybrid_agent.py` | SQL + RAG | Runs SQL then enriches with RAG context (e.g., "does inventory turnover justify showroom space?") |
| `prompts/` | Anthropic system prompts | AgentSpec: SQL Agent (READ-ONLY guardrail + few-shot SQL), RAG Agent, Router classifier |

### Layer 4 — UI (`ui/`)

| Component | Technology | Responsibility |
|-----------|------------|----------------|
| `app.py` | Chainlit | Executive chat; streams LangGraph traversal as Chain of Thought; renders tables + Plotly charts |

---

## Key Decisions Made

| # | Decision | Rationale | Alternative Rejected |
|---|----------|-----------|----------------------|
| 1 | Build bottom-up (INGEST first) | Data quality is the foundation — AI output is only as good as the data it queries | Top-down (AGENT first) — risky to build UI before data is validated |
| 2 | LangGraph over CrewAI | 3 query types require conditional routing graph; LangGraph is native fit | CrewAI — better for sequential role-based crews, not conditional routing |
| 3 | Anthropic Claude as LLM | Native `tool_use` maps to MCP tools; strong SQL reasoning; Pydantic structured outputs | OpenAI, Gemini, local models |
| 4 | Hybrid Agent for Type 3 queries | Questions like "does DSI justify showroom space" need SQL result + RAG qualitative enrichment | SQL Agent alone — can't provide business context judgment |
| 5 | Medium data scale (100K rows, 2 years) | Demo-ready with realistic seasonal patterns; validates query performance without over-engineering | Small (not convincing for exec demo), Large (premature for MVP) |

---

## Features Removed (YAGNI)

| Feature | Reason Removed | Can Add Later? |
|---------|----------------|----------------|
| Customer sentiment analysis (vector embeddings of reviews) | No sentiment data source defined in Star Schema or kickoff — would require a new data pipeline | Yes — Phase 2 |
| Multi-tenant auth / SSO for Chainlit | MVP is dev/demo environment; auth adds significant complexity with no demo value | Yes — Phase 3 (production hardening) |
| Real-time streaming query results | Executive questions are analytical — batch responses with CoT display are sufficient | Yes |
| Query result caching (Redis) | Premature optimisation before latency baselines are measured | Maybe — after latency profiling |
| Multi-language UI (PT + EN toggle) | Kickoff content is in Portuguese; one language is sufficient for MVP | Yes |
| Write/DDL access for agents | READ-ONLY is a hard security requirement; write access adds risk with no value | No — by design, never |

---

## Incremental Validations

| Section | Presented | User Feedback | Adjusted? |
|---------|-----------|---------------|-----------|
| Architecture concept (3 approaches) | ✅ 2026-04-25 | Selected Approach A | No adjustment needed |
| Component breakdown (4 layers) | ✅ 2026-04-25 | "I'm satisfied!" | No adjustment needed |

---

## Suggested Requirements for /define

### Problem Statement (Draft)
C-Level executives at a technology retail company need real-time answers to business questions without requiring SQL knowledge — InfoAgent must translate natural language into precise PostgreSQL queries and KPI-grounded responses, eliminating the latency between a critical question and an executive decision.

### Target Users (Draft)

| User | Pain Point |
|------|------------|
| C-Level Executives | Cannot query the DW directly; wait hours for analyst reports |
| Data / Engineering Team | Build and maintain the 3-layer pipeline and agent system |
| Business Analysts | Own KPI definitions that must be kept in sync with Qdrant |

### Success Criteria (Draft)

- [ ] `docker compose up` starts the full stack in < 5 minutes
- [ ] All 6 Pydantic models pass 100% of ShadowTraffic-generated data without validation errors
- [ ] All 13 sample executive questions return correct SQL results
- [ ] Type 2 (KPI) questions never hallucinate metric definitions (validated against Qdrant ground truth)
- [ ] Type 3 (Hybrid) questions return SQL result + enriched business context
- [ ] Chainlit displays agent Chain of Thought in real-time for every query
- [ ] SQL Agent is strictly READ-ONLY (enforced at DB user level)
- [ ] ShadowTraffic generates ~100K FATO_VENDAS rows with realistic seasonal patterns

### Constraints Identified

- SQL Agent must be READ-ONLY at both application and database user level
- Claude (`claude-sonnet-4-6` or `claude-opus-4-7`) is the only LLM provider
- Development environment must run entirely on Docker Compose (no cloud dependencies for INGEST + CONTEXTUALIZE layers)
- Pydantic models are shared across all layers — breaking changes must be coordinated

### Out of Scope (Confirmed)

- Customer sentiment analysis / review embeddings (no data source)
- Production auth / SSO (deferred to Phase 3)
- Write or DDL access to PostgreSQL from any agent
- Real-time streaming data ingestion (ShadowTraffic seeds once, not continuous)
- Cloud deployment / IaC (local Docker only for MVP)

---

## Session Summary

| Metric | Value |
|--------|-------|
| Questions Asked | 4 (3 discovery + 1 sample collection) |
| Approaches Explored | 3 |
| Features Removed (YAGNI) | 6 |
| Validations Completed | 2 |
| Key Decisions Resolved | 5 (build order, orchestration, LLM, hybrid agent, data scale) |

---

## Next Step

**Ready for:** `/define .claude/sdd/features/BRAINSTORM_INFOAGENT.md`
