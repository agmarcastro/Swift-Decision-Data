# InfoAgent — Consolidated Requirements & Architecture

> **Generated:** 2026-04-24 | **Source:** `01 - kickoff.md`
> **Confidence:** 0.82 (STANDARD — single source, no speaker attribution, no explicit dates)
> **Single source of truth for the InfoAgent project**

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Key Decisions](#2-key-decisions)
3. [Functional Requirements](#3-functional-requirements)
4. [Non-Functional Requirements](#4-non-functional-requirements)
5. [Architecture](#5-architecture)
6. [Data Schema](#6-data-schema)
7. [Action Items](#7-action-items)
8. [Blockers & Risks](#8-blockers--risks)
9. [Open Questions](#9-open-questions)
10. [Stakeholders & Roles](#10-stakeholders--roles)
11. [Success Metrics](#11-success-metrics)
12. [Appendix — Source Index](#12-appendix--source-index)

---

## 1. Executive Summary

| Aspect | Details |
|--------|---------|
| **Project** | InfoAgent — multi-agent AI system for executive decision support |
| **Business Problem** | Cognitive and technical latency between a critical business question and executive decision-making |
| **Solution** | NL→SQL router agent backed by a PostgreSQL data warehouse + RAG semantic layer, delivered via a Chainlit chat UI |
| **Data Foundation** | Synthetic retail dataset (Star Schema) generated with ShadowTraffic, containerised with Docker |
| **Critical Principle** | Tactical agility — executives must get answers in real-time, not hours |

---

## 2. Key Decisions

### 2.1 Business Decisions

| # | Decision | Owner | Source | Status |
|---|----------|-------|--------|--------|
| D1 | The primary persona is C-Level executives, not analysts or engineers | TBD | kickoff | Approved |
| D2 | System must answer two distinct query types: precise figures (SQL) and sentiment/context (RAG) | TBD | kickoff | Approved |
| D3 | Synthetic data will be used for development before real DW connection | TBD | kickoff | Approved |

### 2.2 Technical Decisions

| # | Decision | Owner | Source | Status |
|---|----------|-------|--------|--------|
| D4 | Star Schema with ANSI SQL / PostgreSQL dialect as the DW target | TBD | kickoff | Approved |
| D5 | ShadowTraffic for synthetic data generation | TBD | kickoff | Approved |
| D6 | Docker to containerise PostgreSQL + ShadowTraffic for local dev | TBD | kickoff | Approved |
| D7 | Pydantic as the bidirectional validation layer (data ingestion + LLM structured outputs) | TBD | kickoff | Approved |
| D8 | Qdrant as the vector store for metadata and business rules RAG | TBD | kickoff | Approved |
| D9 | LlamaIndex for RAG pipeline construction and context injection | TBD | kickoff | Approved |
| D10 | Model Context Protocol (MCP) as the execution bridge between LLM and PostgreSQL | TBD | kickoff | Approved |
| D11 | LangChain or CrewAI for agent orchestration and routing | TBD | kickoff | Pending (either/or not resolved) |
| D12 | Chainlit as the executive-facing chat interface | TBD | kickoff | Approved |

### 2.3 Architectural Decisions

| # | Decision | Owner | Source | Status |
|---|----------|-------|--------|--------|
| D13 | Three-layer pipeline: INGEST → CONTEXTUALIZE → AGENT | TBD | kickoff | Approved |
| D14 | Router Agent pattern: single entry point delegates to specialist sub-agents | TBD | kickoff | Approved |
| D15 | SQL Agent must be READ-ONLY with no write/DDL access to PostgreSQL | TBD | kickoff | Approved |

---

## 3. Functional Requirements

| ID | Requirement | Priority | Layer | Source |
|----|-------------|----------|-------|--------|
| FR-001 | System shall translate natural language business questions into PostgreSQL queries | P0-Critical | AGENT | kickoff |
| FR-002 | System shall route queries to either SQL Agent (figures) or RAG Agent (context/sentiment) | P0-Critical | AGENT | kickoff |
| FR-003 | SQL Agent shall use MCP server to dynamically inspect table schema before generating queries | P1-High | AGENT | kickoff |
| FR-004 | RAG Agent shall retrieve semantic context from Qdrant before responding to metric questions | P1-High | AGENT | kickoff |
| FR-005 | System shall generate a synthetic retail dataset using ShadowTraffic matching the Star Schema | P0-Critical | INGEST | kickoff |
| FR-006 | ShadowTraffic + PostgreSQL shall be packaged and runnable via Docker Compose | P1-High | INGEST | kickoff |
| FR-007 | Pydantic models shall validate all ShadowTraffic-generated data prior to DB insertion | P1-High | INGEST | kickoff |
| FR-008 | Pydantic models shall validate all LLM structured output responses | P1-High | AGENT | kickoff |
| FR-009 | Qdrant shall contain the data dictionary, KPI calculation rules, and store org chart | P1-High | CONTEXTUALIZE | kickoff |
| FR-010 | MCP Server shall expose `list_tables()`, `describe_schema(table)`, and `execute_read_only_query(sql)` tools | P0-Critical | CONTEXTUALIZE | kickoff |
| FR-011 | Chainlit UI shall display agent Chain of Thought in real-time (schema fetch, SQL write, validation, results) | P1-High | AGENT | kickoff |
| FR-012 | Chainlit UI shall render query results as tables and charts within the chat interface | P1-High | AGENT | kickoff |
| FR-013 | Each agent shall have a dedicated System Prompt and guardrails defined via AgentSpec | P1-High | AGENT | kickoff |

---

## 4. Non-Functional Requirements

| ID | Requirement | Type | Priority | Source |
|----|-------------|------|----------|--------|
| NFR-001 | SQL Agent queries must be optimised for low latency (real-time executive experience) | Performance | P0-Critical | kickoff |
| NFR-002 | SQL Agent must operate in strictly READ-ONLY mode against PostgreSQL | Security | P0-Critical | kickoff |
| NFR-003 | The dev environment must be reproducible and spinnable in minutes via Docker | Reliability | P1-High | kickoff |
| NFR-004 | Semantic context must be injected before LLM attempts SQL generation (hallucination prevention) | Accuracy | P0-Critical | kickoff |
| NFR-005 | Data validation must be bidirectional: at ingestion and at LLM output | Data Integrity | P1-High | kickoff |
| NFR-006 | System must prevent the LLM from conflating business metrics (e.g. gross profit ≠ total revenue) | Accuracy | P0-Critical | kickoff |

---

## 5. Architecture

### 5.1 High-Level Pipeline

```
┌─────────────────────────────────────────────────────────────────────┐
│                        InfoAgent Pipeline                           │
│                                                                     │
│  ┌──────────────┐    ┌───────────────────┐    ┌──────────────────┐  │
│  │    INGEST    │───▶│  CONTEXTUALIZE    │───▶│     AGENT        │  │
│  │              │    │                   │    │                  │  │
│  │ ShadowTraffic│    │ Qdrant (vectors)  │    │ Router Agent     │  │
│  │     │        │    │ LlamaIndex (RAG)  │    │   ├─ SQL Agent   │  │
│  │     ▼        │    │ MCP Server        │    │   └─ RAG Agent   │  │
│  │ Pydantic     │    │  (PostgreSQL      │    │                  │  │
│  │ Validation   │    │   bridge)         │    │ Chainlit UI      │  │
│  │     │        │    │                   │    │ (Chain of        │  │
│  │     ▼        │    │                   │    │  Thought)        │  │
│  │ PostgreSQL   │    │                   │    │                  │  │
│  │ (Docker)     │    │                   │    │                  │  │
│  └──────────────┘    └───────────────────┘    └──────────────────┘  │
└─────────────────────────────────────────────────────────────────────┘
```

### 5.2 Component Details

```
COMPONENT: INGEST layer
+- Technologies: ShadowTraffic, PostgreSQL, Docker, Pydantic
+- Purpose:      Simulate company DW with synthetic retail data; validate integrity
+- Rationale:    Isolated, reproducible dev env without needing real production data
+- Deliverables: docker-compose.yml, ShadowTraffic config, Pydantic schema models

COMPONENT: CONTEXTUALIZE layer
+- Technologies: Qdrant, LlamaIndex, Model Context Protocol (MCP)
+- Purpose:      Give the LLM business awareness + safe DB access
+- Rationale:    Prevents hallucinations by grounding SQL generation in real schema
                 and business rule context before any query is written
+- Deliverables: Qdrant ingestion pipeline, MCP server with 3 tools, RAG retriever

COMPONENT: AGENT layer
+- Technologies: LangChain / CrewAI, Chainlit, AgentSpec (System Prompts)
+- Purpose:      Orchestrate specialist agents; deliver executive chat interface
+- Rationale:    Router pattern separates concerns; Chainlit exposes CoT for trust
+- Deliverables: Router Agent, SQL Agent, RAG Agent, Chainlit app, AgentSpec configs
```

### 5.3 Agent Data Flow

```
Executive Question
       │
       ▼
  Router Agent
  (LangChain/CrewAI)
       │
       ├──[Precise figures?]──────────▶ SQL Agent
       │                                    │
       │                                    ├─ MCP: describe_schema()
       │                                    ├─ MCP: list_tables()
       │                                    ├─ Generate PostgreSQL query
       │                                    ├─ Pydantic: validate output
       │                                    └─ MCP: execute_read_only_query()
       │
       └──[Context/metrics/sentiment?]──▶ RAG Agent
                                              │
                                              ├─ LlamaIndex: retrieve context
                                              ├─ Qdrant: fetch business rules
                                              └─ Return grounded explanation
                                                       │
                                                       ▼
                                               Chainlit UI
                                          (Chain of Thought + Results)
```

### 5.4 MCP Server Interface

| Tool | Signature | Access Level |
|------|-----------|--------------|
| `list_tables()` | `() → list[str]` | READ |
| `describe_schema(table)` | `(table: str) → dict` | READ |
| `execute_read_only_query(sql)` | `(sql: str) → list[dict]` | READ-ONLY |

---

## 6. Data Schema

### 6.1 Star Schema — Fact Tables

| Table | Columns | Description |
|-------|---------|-------------|
| **FATO_VENDAS** | ID_VENDA, ID_PRODUTO, ID_CLIENTE, ID_LOJA, ID_TEMPO, DATA_VENDA, QUANTIDADE, VALOR_UNITARIO, VALOR_TOTAL, CUSTO_TOTAL, VALOR_DESCONTO | Sales transactions fact table |
| **FATO_ESTOQUE** | ID_PRODUTO, ID_LOJA, DATA_POSICAO, QTD_DISPONIVEL, QTD_TRANSITO | Inventory position fact table |

### 6.2 Star Schema — Dimension Tables

| Table | Columns | Enumerations |
|-------|---------|-------------|
| **DIM_PRODUTO** | ID_PRODUTO, SKU, NOME_PRODUTO, MARCA, DEPARTAMENTO, CATEGORIA | DEPARTAMENTO: Computing, Telephony, TV/Audio, Gaming, Home Appliances, Printing |
| **DIM_CLIENTE** | ID_CLIENTE, CATEGORIA_CLUBE_INFO, ESTADO, CIDADE, GENERO, FAIXA_ETARIA | CATEGORIA_CLUBE_INFO: Bronze, Silver, Gold |
| **DIM_LOJA** | ID_LOJA, NOME_LOJA, REGIAO, GERENTE | — |
| **DIM_TEMPO** | ID_TEMPO, DATA, DIA_SEMANA, MES, ANO, FLG_FERIADO | FLG_FERIADO: boolean holiday flag |

### 6.3 Pydantic Models Required

| Model Name | Maps To |
|------------|---------|
| `ModeloFatoVendas` | FATO_VENDAS |
| `ModeloFatoEstoque` | FATO_ESTOQUE |
| `ModeloDimProduto` | DIM_PRODUTO |
| `ModeloDimCliente` | DIM_CLIENTE |
| `ModeloDimLoja` | DIM_LOJA |
| `ModeloDimTempo` | DIM_TEMPO |

---

## 7. Action Items

> Owner is TBD for all items — no individual assignments were made in the source document.

### By Layer

**INGEST**
- [ ] **TBD**: Design and implement ShadowTraffic configuration for all 6 Star Schema tables
- [ ] **TBD**: Create `docker-compose.yml` packaging PostgreSQL + ShadowTraffic
- [ ] **TBD**: Implement all 6 Pydantic models mirroring the Star Schema
- [ ] **TBD**: Implement ingestion pipeline that validates data through Pydantic before DB insert
- [ ] **TBD**: Implement Pydantic structured output models for LLM responses

**CONTEXTUALIZE**
- [ ] **TBD**: Write and ingest data dictionary into Qdrant
- [ ] **TBD**: Document and ingest KPI calculation rules (e.g., VALOR_DESCONTO definition)
- [ ] **TBD**: Write and ingest store organisational chart into Qdrant
- [ ] **TBD**: Build LlamaIndex RAG retrieval pipeline over Qdrant
- [ ] **TBD**: Implement MCP Server with `list_tables()`, `describe_schema()`, `execute_read_only_query()`
- [ ] **TBD**: Enforce READ-ONLY access at the MCP server layer

**AGENT**
- [ ] **TBD**: Choose and configure orchestration framework (LangChain vs. CrewAI — decision pending)
- [ ] **TBD**: Implement Router Agent with routing logic for SQL vs. RAG queries
- [ ] **TBD**: Implement SQL Agent with MCP integration and Pydantic output validation
- [ ] **TBD**: Implement RAG (Business Rules) Agent with Qdrant/LlamaIndex integration
- [ ] **TBD**: Write AgentSpec System Prompts and guardrails for each agent
- [ ] **TBD**: Develop Chainlit interface with real-time Chain of Thought display
- [ ] **TBD**: Implement results rendering (tables and charts) in Chainlit

---

## 8. Blockers & Risks

| # | Type | Description | Impact | Mitigation |
|---|------|-------------|--------|------------|
| R1 | Risk | LLM may hallucinate SQL using wrong metric definitions (e.g., gross profit vs. revenue) | HIGH — wrong executive decisions | Inject Qdrant semantic context before every SQL generation step |
| R2 | Risk | LangChain vs. CrewAI decision unresolved — may affect agent design patterns | MEDIUM — rework if decided late | Decide framework before AGENT layer implementation begins |
| R3 | Risk | Pydantic validation gaps could allow malformed data into PostgreSQL | HIGH — corrupts DW and downstream queries | Validate 100% of ShadowTraffic output; add integration tests |
| R4 | Risk | MCP server misconfiguration could allow write/DDL queries | CRITICAL — data loss | Enforce READ-ONLY at DB user level, not just application level |
| R5 | Risk | Synthetic data may not reflect realistic distributions (e.g., skewed sales) | MEDIUM — system works in dev but fails on real data | Define statistical profiles for ShadowTraffic generators |
| R6 | Risk | Chain of Thought display may expose internal agent reasoning to unintended audiences | LOW-MEDIUM | Add access controls to Chainlit; scope CoT visibility by role |
| R7 | Blocker | No LLM provider specified — system cannot be built without this decision | HIGH | Resolve LLM provider before CONTEXTUALIZE and AGENT layers start |

---

## 9. Open Questions

| # | Question | Context | Priority |
|---|----------|---------|----------|
| Q1 | Which LLM provider and model will be used? (OpenAI, Anthropic, Gemini, local?) | Entire AGENT layer depends on this — prompt format, structured outputs, and latency SLAs differ per provider | HIGH |
| Q2 | How will customer sentiment/vector data be generated? | Obj 2 mentions sentiment analysis via vectors, but no sentiment data exists in the Star Schema | HIGH |
| Q3 | What is the authentication and authorisation model for the Chainlit UI? | C-Level executives need secure access; no auth design is documented | HIGH |
| Q4 | What is the target deployment environment? (local dev only, cloud, on-prem?) | Docker is specified for dev, but production deployment is undefined | MEDIUM |
| Q5 | Will LangChain or CrewAI be used for orchestration? | Both are listed as options — this affects the agent design pattern significantly | HIGH |
| Q6 | How are KPI calculation rules currently documented? Who owns them? | They must be ingested into Qdrant but their source format is unknown | MEDIUM |
| Q7 | What volume of synthetic data should ShadowTraffic generate? (rows per table, time range) | Needed to define realistic ShadowTraffic generator configs | MEDIUM |
| Q8 | Will the system connect to a real production DW after the synthetic phase? | Pydantic models and MCP server should be designed with this migration in mind | MEDIUM |
| Q9 | What charting library will Chainlit use for result visualisation? (built-in Plotly, custom?) | Affects UI implementation and data formatting from agents | LOW |
| Q10 | Are there compliance or data governance requirements for what executives can query? | READ-ONLY is specified, but row-level security and data masking are not addressed | MEDIUM |

---

## 10. Stakeholders & Roles

| Persona | Role | Responsibilities | Notes |
|---------|------|-----------------|-------|
| C-Level Executives | End Users | Pose natural language business questions; consume results and charts | Non-technical; expect sub-second answers |
| Data / Engineering Team | Builders | Design schema, build pipeline layers, configure agents | Implied owners of all action items |
| Business Analysts (implied) | Knowledge Owners | Own KPI definitions and business rules to be ingested into Qdrant | Must supply data dictionary content |

### RACI Matrix

| Component | Responsible | Accountable | Consulted | Informed |
|-----------|-------------|-------------|-----------|---------|
| ShadowTraffic + Docker setup | Engineering | Engineering | — | Executives |
| Pydantic models | Engineering | Engineering | Business Analysts | — |
| Qdrant / RAG pipeline | Engineering | Engineering | Business Analysts | — |
| MCP Server | Engineering | Engineering | — | — |
| Agent orchestration | Engineering | Engineering | — | Executives |
| Chainlit UI | Engineering | Engineering | Executives | Executives |
| KPI rules documentation | Business Analysts | Business Analysts | Engineering | — |

---

## 11. Success Metrics

| Metric | Target | Description | Measurement Method |
|--------|--------|-------------|-------------------|
| SQL query latency | Real-time (TBD ms) | Time from executive question to displayed result | Chainlit timestamp delta |
| SQL generation accuracy | High (TBD %) | Percentage of generated SQL queries that return correct results | Manual evaluation set |
| Hallucination rate | 0% on known metrics | LLM must never confuse defined KPIs | Regression test suite against Qdrant-grounded answers |
| Data validation pass rate | 100% | All ShadowTraffic data must pass Pydantic validation | CI pipeline check |
| Dev environment startup time | < minutes | `docker compose up` to working state | Measured in CI |

---

## 12. Appendix — Source Index

| # | Document | Date | Type | Key Topics |
|---|----------|------|------|------------|
| 1 | `01 - kickoff.md` | 2026-04-24 | Kickoff / Spec | Product vision, 3-layer architecture, Star Schema, technology stack |

### Decision Log (Chronological)

| Date | Decision | Status |
|------|----------|--------|
| 2026-04-24 | Three-layer pipeline: INGEST → CONTEXTUALIZE → AGENT | Approved |
| 2026-04-24 | PostgreSQL + ANSI SQL as DW target | Approved |
| 2026-04-24 | ShadowTraffic for synthetic data generation | Approved |
| 2026-04-24 | Docker containerisation of dev environment | Approved |
| 2026-04-24 | Pydantic as bidirectional validation layer | Approved |
| 2026-04-24 | Qdrant + LlamaIndex for semantic RAG layer | Approved |
| 2026-04-24 | MCP as PostgreSQL execution bridge | Approved |
| 2026-04-24 | Chainlit as executive chat interface | Approved |
| 2026-04-24 | LangChain **or** CrewAI for orchestration | **Pending** |
| 2026-04-24 | LLM provider | **Not decided** |

---

*Document version: 1.0.0 — Generated from kickoff analysis on 2026-04-24*
