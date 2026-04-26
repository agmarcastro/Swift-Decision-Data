# DEFINE: InfoAgent

> Multi-agent AI system that translates natural language executive questions into precise PostgreSQL queries and KPI-grounded answers via a real-time chat interface.

## Metadata

| Attribute | Value |
|-----------|-------|
| **Feature** | INFOAGENT |
| **Date** | 2026-04-25 |
| **Author** | define-agent |
| **Status** | ✅ Complete (Built — see BUILD_REPORT_INFOAGENT.md) |
| **Clarity Score** | 14/15 |
| **Source** | `BRAINSTORM_INFOAGENT.md` |

---

## Problem Statement

C-Level executives at a technology retail company cannot access the Data Warehouse without technical SQL knowledge, forcing them to wait hours for analyst-generated reports — InfoAgent eliminates this latency by routing natural language questions to either a SQL Agent (precise figures) or a RAG Agent (KPI context and business rules), returning answers in real-time through an executive chat interface.

---

## Target Users

| User | Role | Pain Point |
|------|------|------------|
| C-Level Executives | Primary end users | Cannot query the DW directly; wait hours for analyst reports; need tactical answers in real-time |
| Data / Engineering Team | Builders and maintainers | Responsible for all 3 pipeline layers (INGEST → CONTEXTUALIZE → AGENT) and their integration |
| Business Analysts | KPI definition owners | Own the business rules and metric definitions that must stay in sync with the Qdrant knowledge base |

---

## Goals

| Priority | Goal |
|----------|------|
| **MUST** | Translate natural language business questions into valid PostgreSQL queries via the SQL Agent |
| **MUST** | Return KPI-grounded answers by retrieving metric definitions from Qdrant before generating SQL |
| **MUST** | Validate 100% of synthetic data with Pydantic before it reaches PostgreSQL |
| **MUST** | Run the full stack (PostgreSQL + ShadowTraffic + Qdrant + MCP + Chainlit) with `docker compose up` |
| **MUST** | Enforce SQL Agent READ-ONLY access at the database user level |
| **SHOULD** | Display LangGraph Chain of Thought in real-time in the Chainlit interface |
| **SHOULD** | Handle Type 3 Hybrid queries (SQL result enriched with RAG business context) |
| **SHOULD** | Generate ~100K FATO_VENDAS rows with realistic 2-year seasonal patterns via ShadowTraffic |
| **COULD** | Render query results as Plotly charts (in addition to tables) in Chainlit |
| **COULD** | Maintain stateful conversation context so executives can ask follow-up questions |

---

## Success Criteria

- [ ] `docker compose up` brings the full stack to a ready state in under 5 minutes
- [ ] All 6 Pydantic models (Fato + Dim tables) pass 100% of ShadowTraffic-generated records without validation errors
- [ ] ShadowTraffic generates ≥ 100K rows in FATO_VENDAS with statistically observable seasonal spikes on holiday dates (FLG_FERIADO)
- [ ] All 13 sample executive questions produce SQL results that match expected values (verified manually)
- [ ] Type 2 KPI questions (e.g., Gross Profit Margin, GMROI) use Qdrant-retrieved formula definitions, not LLM-hallucinated ones
- [ ] Type 3 Hybrid questions (e.g., "does inventory turnover justify showroom space?") return SQL numeric result + Qdrant-grounded qualitative context
- [ ] SQL Agent never executes INSERT, UPDATE, DELETE, or DDL statements (blocked at database user level)
- [ ] Chainlit displays the routing decision, tool calls, and SQL query in real-time before showing the final result

---

## Acceptance Tests

| ID | Scenario | Given | When | Then |
|----|----------|-------|------|------|
| AT-001 | Full stack starts cleanly | Docker is installed, no previous containers running | `docker compose up` is executed | All services are healthy; `make seed` populates all 6 tables; no Pydantic validation errors |
| AT-002 | Pydantic blocks invalid data | PostgreSQL is running; ShadowTraffic generates a record with negative QUANTIDADE | The ingest loader processes the record | Validation error is raised, record is rejected, error is logged, no bad data written to DB |
| AT-003 | Type 1 — Pure SQL query | Full stack running with seeded data | Executive asks "What were the sales figures for yesterday?" | LangGraph classifies as Type 1; SQL Agent generates valid SELECT; Chainlit displays VALOR_TOTAL sum in a table |
| AT-004 | Type 2 — KPI-grounded SQL query | Qdrant has Gross Profit Margin definition indexed | Executive asks "What was the gross profit margin for Smartphones last week vs the preceding week?" | RAG retrieves KPI definition; SQL Agent uses (VALOR_TOTAL - CUSTO_TOTAL) / VALOR_TOTAL formula; comparative result displayed |
| AT-005 | Type 3 — Hybrid query | Both seeded DW and Qdrant DSI definition are available | Executive asks "Does inventory turnover at mall locations justify the showroom space?" | SQL Agent calculates DSI for mall stores; Hybrid Agent enriches with Qdrant business context; final answer includes both number and interpretation |
| AT-006 | READ-ONLY enforcement | SQL Agent is connected to a read-only PostgreSQL user | Any agent attempts `INSERT INTO fato_vendas ...` | Database rejects with permission error; agent surfaces appropriate message; no data is modified |
| AT-007 | Chain of Thought visible | Chainlit is running and connected to LangGraph | Executive submits any query | CoT panel shows: classify_query → route decision → MCP tool calls → SQL generated → result |
| AT-008 | Seasonal data distribution | ShadowTraffic configured with FLG_FERIADO state machine | Query: `SELECT AVG(VALOR_TOTAL) ... GROUP BY FLG_FERIADO` | Holiday days show statistically higher average VALOR_TOTAL than non-holiday days |
| AT-009 | MCP schema inspection | MCP server is running; PostgreSQL has all 6 tables | SQL Agent calls `describe_schema('FATO_VENDAS')` | Returns column names, types, and constraints matching the Star Schema spec |
| AT-010 | Loyalty contribution KPI | Qdrant has Loyalty Program Contribution definition | Executive asks "What is our loyalty program contribution this month?" | RAG retrieves formula; SQL Agent joins FATO_VENDAS + DIM_CLIENTE on CATEGORIA_CLUBE_INFO; correct percentage returned |

---

## Out of Scope

- **Customer sentiment analysis / review embeddings** — no sentiment data source exists in the Star Schema; deferred to Phase 2
- **Production authentication / SSO for Chainlit** — MVP is a dev/demo environment; auth hardening deferred to Phase 3
- **Write or DDL access to PostgreSQL from any agent** — READ-ONLY is a permanent security constraint, not a deferral
- **Real-time streaming data ingestion** — ShadowTraffic seeds the database once at startup; continuous ingestion is out of scope
- **Cloud deployment / IaC (Terraform, Terragrunt, GCP)** — local Docker Compose only for MVP; cloud deployment deferred
- **Multi-language UI (PT + EN toggle)** — single language sufficient for MVP demo
- **Query result caching (Redis or equivalent)** — premature optimisation before latency baselines are measured

---

## Constraints

| Type | Constraint | Impact |
|------|------------|--------|
| Technical | LLM is Anthropic Claude only (`claude-sonnet-4-6` or `claude-opus-4-7`) | All prompt design must use Anthropic `tool_use` API format; no OpenAI-style function calling |
| Technical | Pydantic models are shared across all 3 layers | Breaking schema changes require coordinated update across `ingest/`, `contextualize/`, and `agent/` |
| Security | SQL Agent must be READ-ONLY at PostgreSQL user level (not just application level) | A dedicated `infoagent_readonly` DB user must be provisioned; MCP server connects as this user |
| Infrastructure | Full stack runs on Docker Compose only (no cloud dependencies for MVP) | All services (PostgreSQL, Qdrant, MCP server, Chainlit) must be containerised with public or local images |
| Data | ShadowTraffic generates synthetic data only; no real production data is used | Data distributions must be explicitly configured to be realistic (seasonal patterns, category mix) |

---

## Technical Context

| Aspect | Value | Notes |
|--------|-------|-------|
| **Deployment Location** | Monorepo root: `ingest/`, `contextualize/`, `agent/`, `ui/` | Single repo, one `docker-compose.yml` at root |
| **KB Domains** | `shadowtraffic`, `pydantic`, `dw`, `crewai` (reference only) | ShadowTraffic for data gen; Pydantic for validation; DW for schema patterns; CrewAI KB consulted for agent design patterns even though LangGraph is used |
| **IaC Impact** | Docker Compose only — no Terraform/Terragrunt for MVP | No cloud resources provisioned; all services run locally via `docker compose up` |

---

## Assumptions

| ID | Assumption | If Wrong, Impact | Validated? |
|----|------------|------------------|------------|
| A-001 | ShadowTraffic supports direct PostgreSQL output (not Kafka-only) | Would need an intermediate ETL step: ShadowTraffic → Kafka → consumer → PostgreSQL, adding significant complexity | [ ] |
| A-002 | Claude `tool_use` API integrates with the MCP Python SDK without adapter code | Would need a manual tool-dispatch layer between LangGraph ToolNode and MCP server | [ ] |
| A-003 | Qdrant local Docker image (latest) is compatible with LlamaIndex vector store client | May need to pin a specific Qdrant version; breaking changes in Qdrant gRPC API are documented | [ ] |
| A-004 | 100K rows in FATO_VENDAS produces query response times < 10s without custom indexing | Would need PostgreSQL index tuning (composite indexes on ID_TEMPO + ID_PRODUTO) before demo | [ ] |
| A-005 | LangGraph async streaming is compatible with Chainlit's `cl.Message` async event model | Would need a polling/adapter pattern instead of native streaming for Chain of Thought display | [ ] |
| A-006 | The 13 sample executive questions cover the representative distribution of real query types | Router Agent may misclassify novel question patterns not present in few-shot examples | [x] Partially — confirmed as real executive questions by user |
| A-007 | ShadowTraffic state machines can model seasonal sales patterns using FLG_FERIADO as a driver | May need to generate holiday flags independently and join them to ShadowTraffic output post-hoc | [ ] |

**Critical assumptions to validate before Design phase:**
- **A-001** (ShadowTraffic → PostgreSQL) — determines INGEST layer architecture
- **A-002** (Claude tool_use + MCP SDK) — determines AGENT layer integration pattern

---

## Clarity Score Breakdown

| Element | Score (0-3) | Notes |
|---------|-------------|-------|
| Problem | 3 | Single sentence, names who, what, and the measured impact (hours of wait time) |
| Users | 3 | 3 personas with explicit pain points and responsibilities |
| Goals | 2 | MoSCoW prioritised; COULD goals are aspirational — acceptable for MVP planning |
| Success | 3 | 8 measurable criteria with specific thresholds (100K rows, 5 min startup, 100% validation) |
| Scope | 3 | 7 explicit out-of-scope items with deferral rationale |
| **Total** | **14/15** | |

---

## Open Questions

None blocking — ready for Design.

The following are tracked as unvalidated assumptions (see Assumptions table):
- A-001: Confirm ShadowTraffic → PostgreSQL direct output before designing INGEST loader
- A-002: Spike test Claude `tool_use` + MCP Python SDK integration before designing AGENT layer

---

## Revision History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | 2026-04-25 | define-agent | Initial version from BRAINSTORM_INFOAGENT.md |

---

## Next Step

**Ready for:** `/build .claude/sdd/features/DESIGN_INFOAGENT.md`
