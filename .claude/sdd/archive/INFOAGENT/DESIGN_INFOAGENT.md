# DESIGN: InfoAgent

> Technical design for implementing the InfoAgent multi-agent executive intelligence system.

## Metadata

| Attribute | Value |
|-----------|-------|
| **Feature** | INFOAGENT |
| **Date** | 2026-04-25 |
| **Author** | design-agent |
| **DEFINE** | [DEFINE_INFOAGENT.md](./DEFINE_INFOAGENT.md) |
| **Status** | ✅ Built (2026-04-25) |

---

## Architecture Overview

```text
┌─────────────────────────────────────────────────────────────────────────┐
│                        InfoAgent — Full Stack                           │
├──────────────────────┬──────────────────────┬───────────────────────────┤
│    LAYER 1: INGEST   │ LAYER 2: CONTEXTUALIZE│    LAYER 3: AGENT + UI   │
│                      │                       │                           │
│  ShadowTraffic       │  kpi_definitions.md   │  Executive                │
│  JSON Config         │  data_dictionary.md   │  Question                 │
│       │              │  few_shot_examples.md │      │                    │
│       ▼              │       │               │      ▼                    │
│  stdout / file       │       ▼               │  Chainlit UI              │
│       │              │  Qdrant Ingest        │  (Chain of Thought)       │
│       ▼              │  (LlamaIndex)         │      │                    │
│  Pydantic            │       │               │      ▼                    │
│  Validation          │       ▼               │  LangGraph Graph          │
│       │              │  Qdrant Vector Store  │  ┌─ classify_query ─┐     │
│       ▼              │  (Knowledge Base)     │  │                  │     │
│  PostgreSQL          │                       │  type1  type2  type3│    │
│  (Star Schema)       │  MCP Server           │  │       │       │   │    │
│       │              │  ┌─ list_tables() ─┐  │  ▼       ▼       ▼   │    │
│       └──────────────┼──│ describe_schema()│──┤sql    sql+rag hybrid│   │
│                      │  │ exec_read_only() ─┘  │  agent  agent  agent│   │
│                      │  └──────────────────┘  │  │       │       │   │    │
│                      │           │             │  └───────┴───────┘   │    │
│                      │           ▼             │          │            │    │
│                      │    Claude tool_use      │          ▼            │    │
│                      │    (Anthropic API)      │       Result          │    │
└──────────────────────┴──────────────────────┴──────────────────────────┘
         ▲                                                 │
         └─────────── docker-compose.yml ─────────────────┘
              PostgreSQL + Qdrant + MCP Server + Chainlit
```

---

## Components

| Component | Purpose | Technology | Layer |
|-----------|---------|------------|-------|
| ShadowTraffic configs | Generate synthetic retail dataset | ShadowTraffic JSON | INGEST |
| Pydantic models | Validate data + LLM outputs (shared) | Pydantic v2 | INGEST (shared) |
| PostgreSQL loader | Validate → Insert into DW | psycopg2 + Pydantic | INGEST |
| SQL schema + DDL | Define Star Schema + read-only user | PostgreSQL SQL files | INGEST |
| Knowledge documents | KPI definitions, data dictionary, few-shot examples | Markdown files | CONTEXTUALIZE |
| Qdrant ingest pipeline | Embed and index knowledge documents | LlamaIndex + Qdrant | CONTEXTUALIZE |
| MCP server | Expose PostgreSQL tools to Claude via MCP protocol | MCP Python SDK + psycopg2 | CONTEXTUALIZE |
| LangGraph routing graph | Orchestrate agent routing and state | LangGraph | AGENT |
| Classifier node | Classify query as Type 1/2/3 | Claude + prompt | AGENT |
| SQL Agent node | Generate and execute PostgreSQL queries | Claude tool_use + MCP | AGENT |
| RAG Agent node | Retrieve KPI context from Qdrant | LlamaIndex + Claude | AGENT |
| Hybrid Agent node | SQL result + RAG enrichment | SQL Agent + RAG Agent | AGENT |
| System prompts | AgentSpec for each agent node | Plain text prompt files | AGENT |
| Chainlit app | Executive chat UI with real-time CoT | Chainlit | UI |
| docker-compose.yml | Orchestrate all services | Docker Compose v3.9 | INFRA |

---

## Key Decisions

### Decision 1: ShadowTraffic stdout → Pydantic Loader → PostgreSQL

| Attribute | Value |
|-----------|-------|
| **Status** | Accepted |
| **Date** | 2026-04-25 |

**Context:** The INGEST layer needs to generate synthetic data AND validate 100% of it via Pydantic (FR-007). Assumption A-001 questioned whether ShadowTraffic can write directly to PostgreSQL.

**Choice:** ShadowTraffic writes JSON to stdout/file. A Python loader reads the output, validates each record through Pydantic models, and inserts clean records into PostgreSQL. Invalid records are logged and skipped.

**Rationale:** This pattern is correct regardless of ShadowTraffic's connector support — Pydantic validation is a hard requirement (FR-007), so an intermediate step is needed either way. The loader gives explicit control over batch size, error handling, and transaction boundaries.

**Alternatives Rejected:**
1. ShadowTraffic → PostgreSQL direct connector — bypasses Pydantic validation, defeats FR-007
2. ShadowTraffic → Kafka → consumer → PostgreSQL — adds Kafka broker to docker-compose with no benefit for a seed-once workload

**Consequences:** Slightly longer seed time (Python vs. direct JDBC), but full validation coverage and simpler dependency graph.

---

### Decision 2: LangGraph Routing Graph with 3-Node Conditional Dispatch

| Attribute | Value |
|-----------|-------|
| **Status** | Accepted |
| **Date** | 2026-04-25 |

**Context:** The 13 sample executive questions fall into 3 distinct types: Pure SQL (Type 1), KPI-grounded SQL requiring Qdrant context before query generation (Type 2), and Hybrid SQL + qualitative enrichment (Type 3). A binary SQL-vs-RAG router cannot handle this.

**Choice:** A `classify_query` node uses Claude to classify the incoming question into one of the 3 types, then LangGraph conditional edges dispatch to the appropriate agent node. For Type 2, the classifier also pre-fetches the relevant KPI definition from Qdrant and injects it into the graph state before the SQL Agent runs.

**Rationale:** LangGraph's `StateGraph` with `add_conditional_edges` is a direct model of this routing logic. State is carried across nodes (query type, KPI context, SQL result) without requiring agent-to-agent message passing.

**Alternatives Rejected:**
1. CrewAI sequential crew — cannot branch on runtime conditions without custom task logic
2. Single LLM call with full context — token-inefficient; mixing classification + SQL generation + RAG into one call reduces accuracy
3. Rule-based keyword routing — fragile against paraphrasing; LLM-based classification generalises better

**Consequences:** More boilerplate graph definition code; graph state schema must be kept in sync across nodes.

---

### Decision 3: MCP Server as the Exclusive SQL Execution Bridge

| Attribute | Value |
|-----------|-------|
| **Status** | Accepted |
| **Date** | 2026-04-25 |

**Context:** The SQL Agent needs to inspect the schema and execute queries against PostgreSQL. It could connect directly via psycopg2, or go through the MCP server.

**Choice:** All database access from the AGENT layer goes exclusively through the MCP server. The MCP server connects as `infoagent_readonly` and enforces READ-ONLY at both the application layer (reject non-SELECT) and the database layer (PostgreSQL user permissions).

**Rationale:** Double enforcement of READ-ONLY (application + DB user) satisfies the security constraint. The MCP server is a natural abstraction point — Claude's `tool_use` API maps directly to the MCP tool interface. This also enables future tool additions (e.g., `list_views()`, `explain_query()`) without changing the agent code.

**Alternatives Rejected:**
1. Direct psycopg2 from agent — READ-ONLY enforcement would be application-only (single layer), easier to bypass
2. REST API wrapper — adds HTTP overhead and a custom protocol vs. the MCP standard

**Consequences:** Additional service in docker-compose; MCP server startup must be healthy before agent layer starts.

---

### Decision 4: Shared Pydantic Models Package

| Attribute | Value |
|-----------|-------|
| **Status** | Accepted |
| **Date** | 2026-04-25 |

**Context:** The Star Schema models are needed in three places: INGEST (data validation), CONTEXTUALIZE (schema introspection for MCP describe_schema), and AGENT (structured output validation for LLM responses).

**Choice:** All Pydantic models live in `ingest/models/` and are imported by all other layers as a package dependency. The `ingest` package is installed as an editable local package via `pyproject.toml`.

**Rationale:** Single source of truth for the data schema. A field type change (e.g., QUANTIDADE from int to Decimal) is made once and propagates to all layers automatically.

**Alternatives Rejected:**
1. Duplicate models per layer — drift risk; three separate definitions of FATO_VENDAS will diverge
2. Generated models from DB schema at runtime — adds complexity; requires live DB for agent startup

**Consequences:** Breaking schema changes require coordinated update; `ingest` must be in PYTHONPATH for all containers.

---

### Decision 5: Prompt-Based Query Classification (not Rule-Based)

| Attribute | Value |
|-----------|-------|
| **Status** | Accepted |
| **Date** | 2026-04-25 |

**Context:** The classifier node must distinguish between Type 1 (Pure SQL), Type 2 (KPI-grounded SQL), and Type 3 (Hybrid) queries. This could be done with keyword matching or with an LLM call.

**Choice:** The classifier uses a single Claude call with a structured output (Pydantic `ClassifierOutput`) and a system prompt that includes the 9 KPI names as classification signals. It returns `query_type` + `kpi_name` (if applicable) + `confidence`.

**Rationale:** The 13 sample questions show that type cannot be reliably determined by keywords alone (e.g., "What is our attachment rate?" requires knowing that "attachment rate" is a KPI, not a generic aggregation). Claude with few-shot examples generalises better to novel phrasings.

**Alternatives Rejected:**
1. Keyword matching on KPI names — brittle; fails on paraphrased questions ("cross-sell rate" vs "attachment rate")
2. Embedding similarity to sample questions — requires a separate embedding model at classification time

**Consequences:** One extra Claude API call per user query for classification; adds ~300-500ms to latency. Acceptable given executive use case.

---

### Decision 6: Qdrant over pgvector or ChromaDB

| Attribute | Value |
|-----------|-------|
| **Status** | Accepted |
| **Date** | 2026-04-25 |

**Context:** The CONTEXTUALIZE layer needs a vector store for KPI definitions, data dictionary, and few-shot examples.

**Choice:** Qdrant running in Docker.

**Rationale:** Qdrant has an official Docker image, a first-class Python client, and native LlamaIndex integration. The knowledge base is small (< 50 documents), so performance differences vs. alternatives are negligible — the differentiator is operational simplicity.

**Alternatives Rejected:**
1. pgvector — would co-locate vectors with relational data in PostgreSQL; complicates the read-only user architecture
2. ChromaDB — no first-class LlamaIndex integration at time of design; local persistence is less mature

**Consequences:** Additional Docker service; Qdrant collection must be seeded before the agent layer starts.

---

## File Manifest

| # | File | Action | Purpose | Agent | Dependencies |
|---|------|--------|---------|-------|--------------|
| 1 | `docker-compose.yml` | Create | Orchestrate all 5 services | @infra-deployer | 3, 8, 28, 36 |
| 2 | `Makefile` | Create | `seed`, `dev`, `test`, `lint` targets | (general) | None |
| 3 | `pyproject.toml` | Create | Python project + editable ingest install | (general) | None |
| 4 | `.env.example` | Create | Environment variables template | (general) | None |
| **INGEST layer** | | | | | |
| 5 | `ingest/__init__.py` | Create | Package marker | (general) | None |
| 6 | `ingest/models/__init__.py` | Create | Re-export all models | (general) | 7–12 |
| 7 | `ingest/models/fato_vendas.py` | Create | ModeloFatoVendas with validators | @python-developer | None |
| 8 | `ingest/models/fato_estoque.py` | Create | ModeloFatoEstoque | @python-developer | None |
| 9 | `ingest/models/dim_produto.py` | Create | ModeloDimProduto with DEPARTAMENTO enum | @python-developer | None |
| 10 | `ingest/models/dim_cliente.py` | Create | ModeloDimCliente with CATEGORIA_CLUBE enum | @python-developer | None |
| 11 | `ingest/models/dim_loja.py` | Create | ModeloDimLoja | @python-developer | None |
| 12 | `ingest/models/dim_tempo.py` | Create | ModeloDimTempo with FLG_FERIADO | @python-developer | None |
| 13 | `ingest/sql/schema.sql` | Create | DDL for all 6 tables + indexes | @dw-specialist | None |
| 14 | `ingest/sql/create_readonly_user.sql` | Create | CREATE USER infoagent_readonly + GRANT SELECT | @dw-specialist | 13 |
| 15 | `ingest/shadowtraffic/dims.json` | Create | ShadowTraffic generators for all 4 dim tables | @shadowtraffic-specialist | None |
| 16 | `ingest/shadowtraffic/fato_vendas.json` | Create | ShadowTraffic generator for FATO_VENDAS (100K rows, seasonal) | @shadowtraffic-specialist | 15 |
| 17 | `ingest/shadowtraffic/fato_estoque.json` | Create | ShadowTraffic generator for FATO_ESTOQUE (inventory positions) | @shadowtraffic-specialist | 15 |
| 18 | `ingest/loaders/postgres_loader.py` | Create | Read ShadowTraffic JSON → Pydantic validate → psycopg2 insert | @python-developer | 7–12 |
| 19 | `ingest/loaders/seed.py` | Create | CLI entrypoint: `python -m ingest.loaders.seed` | @python-developer | 18 |
| **CONTEXTUALIZE layer** | | | | | |
| 20 | `contextualize/__init__.py` | Create | Package marker | (general) | None |
| 21 | `contextualize/knowledge/kpi_definitions.md` | Create | 9 KPI definitions with formulas and column mappings | @llm-specialist | None |
| 22 | `contextualize/knowledge/data_dictionary.md` | Create | Column definitions for all 6 tables | @dw-specialist | 13 |
| 23 | `contextualize/knowledge/few_shot_examples.md` | Create | 13 executive questions + expected SQL queries | @llm-specialist | 13 |
| 24 | `contextualize/qdrant_ingest/ingest.py` | Create | Embed and upsert knowledge docs into Qdrant | @ai-data-engineer | 21–23 |
| 25 | `contextualize/mcp_server/server.py` | Create | MCP server entry point (stdio transport) | @ai-data-engineer | 14, 26 |
| 26 | `contextualize/mcp_server/tools.py` | Create | list_tables, describe_schema, execute_read_only_query | @ai-data-engineer | 14 |
| 27 | `contextualize/mcp_server/Dockerfile` | Create | Container for MCP server | @infra-deployer | 25, 26 |
| **AGENT layer** | | | | | |
| 28 | `agent/__init__.py` | Create | Package marker | (general) | None |
| 29 | `agent/state.py` | Create | AgentState TypedDict for LangGraph | @python-developer | 7–12 |
| 30 | `agent/graph.py` | Create | LangGraph StateGraph with conditional edges | @genai-architect | 29, 31–34 |
| 31 | `agent/nodes/classifier.py` | Create | classify_query node + ClassifierOutput Pydantic model | @genai-architect | 29 |
| 32 | `agent/nodes/sql_agent.py` | Create | SQL generation + MCP tool execution node | @genai-architect | 29, 7–12 |
| 33 | `agent/nodes/rag_agent.py` | Create | Qdrant retrieval + Claude synthesis node | @genai-architect | 29 |
| 34 | `agent/nodes/hybrid_agent.py` | Create | SQL result + RAG enrichment node | @genai-architect | 32, 33 |
| 35 | `agent/prompts/classifier.txt` | Create | System prompt: query type classification with KPI names | @llm-specialist | 21 |
| 36 | `agent/prompts/sql_agent.txt` | Create | System prompt: READ-ONLY SQL expert with few-shot examples | @llm-specialist | 23 |
| 37 | `agent/prompts/rag_agent.txt` | Create | System prompt: KPI context retrieval and explanation | @llm-specialist | 21 |
| 38 | `agent/prompts/hybrid_agent.txt` | Create | System prompt: synthesise SQL result with business context | @llm-specialist | None |
| 39 | `agent/config.yaml` | Create | Model, token limits, MCP server URL, Qdrant config | (general) | None |
| **UI layer** | | | | | |
| 40 | `ui/__init__.py` | Create | Package marker | (general) | None |
| 41 | `ui/app.py` | Create | Chainlit app: on_message handler + CoT streaming | @genai-architect | 30 |
| 42 | `ui/Dockerfile` | Create | Container for Chainlit app | @infra-deployer | 41 |
| 43 | `ui/chainlit.md` | Create | Chainlit welcome screen content | (general) | None |
| **Tests** | | | | | |
| 44 | `tests/__init__.py` | Create | Package marker | (general) | None |
| 45 | `tests/test_models.py` | Create | Unit tests for all 6 Pydantic models + validators | @test-generator | 7–12 |
| 46 | `tests/test_loader.py` | Create | Unit + integration tests for postgres_loader | @test-generator | 18 |
| 47 | `tests/test_mcp_tools.py` | Create | Unit tests for MCP tools + READ-ONLY enforcement | @test-generator | 26 |
| 48 | `tests/test_classifier.py` | Create | Unit tests for classify_query with all 3 query types | @test-generator | 31 |
| 49 | `tests/test_sql_agent.py` | Create | Integration tests: 13 sample questions → SQL results | @test-generator | 32 |
| 50 | `tests/test_acceptance.py` | Create | E2E acceptance tests AT-001 through AT-010 | @test-generator | 30, 41 |
| 51 | `tests/conftest.py` | Create | pytest fixtures: test DB, seeded Qdrant, mock MCP | @test-generator | 18, 24 |

**Total Files:** 51

---

## Agent Assignment Rationale

> Agents discovered from `.claude/agents/` directory scan.

| Agent | Files Assigned | Why This Agent |
|-------|----------------|----------------|
| @shadowtraffic-specialist | 15, 16, 17 | Expert in ShadowTraffic JSON DSL, generators, state machines, and cross-table relationships |
| @python-developer | 7–12, 18, 19, 29 | Python data models, dataclasses, type hints, generators, psycopg2 patterns |
| @dw-specialist | 13, 14, 22 | Star Schema DDL, PostgreSQL indexing, user permission design |
| @ai-data-engineer | 24, 25, 26, 27 | Data pipeline code, Qdrant ingestion, MCP server implementation |
| @llm-specialist | 21, 23, 35, 36, 37, 38 | System prompt engineering, few-shot examples, KPI documentation |
| @genai-architect | 30, 31, 32, 33, 34, 41 | Multi-agent orchestration, LangGraph graph design, Chainlit integration |
| @infra-deployer | 1, 27, 42 | Docker Compose, Dockerfile, service health checks |
| @test-generator | 44–51 | pytest, fixtures, integration tests, acceptance tests |
| (general) | 2, 3, 4, 5, 6, 20, 28, 39, 40, 43, 44 | Package markers, config files, no specialist required |

---

## Code Patterns

### Pattern 1: Pydantic Star Schema Model

```python
# ingest/models/fato_vendas.py
from decimal import Decimal
from datetime import date
from pydantic import BaseModel, Field, field_validator, model_validator

class ModeloFatoVendas(BaseModel):
    id_venda: int
    id_produto: int
    id_cliente: int
    id_loja: int
    id_tempo: int
    data_venda: date
    quantidade: int = Field(gt=0)
    valor_unitario: Decimal = Field(gt=0, decimal_places=2)
    valor_total: Decimal = Field(gt=0, decimal_places=2)
    custo_total: Decimal = Field(ge=0, decimal_places=2)
    valor_desconto: Decimal = Field(ge=0, decimal_places=2)

    @model_validator(mode="after")
    def check_valor_total_consistency(self) -> "ModeloFatoVendas":
        expected = self.quantidade * self.valor_unitario - self.valor_desconto
        if abs(self.valor_total - expected) > Decimal("0.02"):
            raise ValueError(
                f"valor_total {self.valor_total} inconsistent with "
                f"quantidade × valor_unitario - desconto = {expected}"
            )
        return self
```

### Pattern 2: Postgres Loader with Pydantic Validation

```python
# ingest/loaders/postgres_loader.py
import json
import logging
from pathlib import Path
from typing import Type
import psycopg2
from psycopg2.extras import execute_batch
from pydantic import BaseModel, ValidationError

logger = logging.getLogger(__name__)

def load_table(
    conn: psycopg2.extensions.connection,
    json_path: Path,
    model: Type[BaseModel],
    table: str,
    batch_size: int = 1000,
) -> dict[str, int]:
    records, errors = [], 0
    with open(json_path) as f:
        for line in f:
            try:
                records.append(model.model_validate_json(line).model_dump())
            except ValidationError as e:
                errors += 1
                logger.warning("Validation error, skipping record: %s", e)
    with conn.cursor() as cur:
        cols = list(records[0].keys())
        placeholders = ",".join(["%s"] * len(cols))
        sql = f"INSERT INTO {table} ({','.join(cols)}) VALUES ({placeholders})"
        execute_batch(cur, sql, [list(r.values()) for r in records], page_size=batch_size)
    conn.commit()
    return {"inserted": len(records), "rejected": errors}
```

### Pattern 3: LangGraph State and Routing Graph

```python
# agent/state.py
from typing import Annotated, Literal
from langgraph.graph.message import add_messages
from pydantic import BaseModel

class AgentState(BaseModel):
    messages: Annotated[list, add_messages]
    query_type: Literal["type1_sql", "type2_kpi_sql", "type3_hybrid"] | None = None
    kpi_context: str | None = None      # pre-fetched for Type 2
    sql_result: list[dict] | None = None
    final_answer: str | None = None

# agent/graph.py
from langgraph.graph import StateGraph, END
from agent.state import AgentState
from agent.nodes.classifier import classify_query
from agent.nodes.sql_agent import sql_agent_node
from agent.nodes.rag_agent import rag_agent_node
from agent.nodes.hybrid_agent import hybrid_agent_node

def route_query(state: AgentState) -> str:
    return state.query_type

graph_builder = StateGraph(AgentState)
graph_builder.add_node("classify", classify_query)
graph_builder.add_node("sql_agent", sql_agent_node)
graph_builder.add_node("rag_agent", rag_agent_node)
graph_builder.add_node("hybrid_agent", hybrid_agent_node)
graph_builder.set_entry_point("classify")
graph_builder.add_conditional_edges(
    "classify",
    route_query,
    {
        "type1_sql": "sql_agent",
        "type2_kpi_sql": "sql_agent",
        "type3_hybrid": "hybrid_agent",
    },
)
graph_builder.add_edge("sql_agent", END)
graph_builder.add_edge("rag_agent", END)
graph_builder.add_edge("hybrid_agent", END)
graph = graph_builder.compile()
```

### Pattern 4: MCP Server Tool — READ-ONLY Enforcement

```python
# contextualize/mcp_server/tools.py
import re
import psycopg2
from mcp.server import Server
from mcp.types import Tool, TextContent

ALLOWED_STMT = re.compile(r"^\s*SELECT\b", re.IGNORECASE)

def register_tools(app: Server, conn: psycopg2.extensions.connection) -> None:

    @app.call_tool()
    async def call_tool(name: str, arguments: dict) -> list[TextContent]:
        match name:
            case "list_tables":
                with conn.cursor() as cur:
                    cur.execute(
                        "SELECT table_name FROM information_schema.tables "
                        "WHERE table_schema = 'public' ORDER BY table_name"
                    )
                    tables = [row[0] for row in cur.fetchall()]
                return [TextContent(type="text", text=str(tables))]

            case "describe_schema":
                table_name = arguments["table_name"].upper()
                with conn.cursor() as cur:
                    cur.execute(
                        "SELECT column_name, data_type, is_nullable "
                        "FROM information_schema.columns "
                        "WHERE table_name = %s ORDER BY ordinal_position",
                        (table_name.lower(),),
                    )
                    cols = cur.fetchall()
                return [TextContent(type="text", text=str(cols))]

            case "execute_read_only_query":
                sql = arguments["sql"]
                if not ALLOWED_STMT.match(sql):
                    raise ValueError("Only SELECT statements are permitted.")
                with conn.cursor() as cur:
                    cur.execute(sql)
                    rows = cur.fetchmany(500)  # hard cap
                    cols = [d[0] for d in cur.description]
                return [TextContent(type="text", text=str([dict(zip(cols, r)) for r in rows]))]
```

### Pattern 5: Chainlit + LangGraph Streaming (Chain of Thought)

```python
# ui/app.py
import chainlit as cl
from agent.graph import graph
from agent.state import AgentState

@cl.on_message
async def on_message(message: cl.Message) -> None:
    state = AgentState(messages=[{"role": "user", "content": message.content}])

    async with cl.Step(name="Classifying query", type="tool") as step:
        async for event in graph.astream_events(state.model_dump(), version="v2"):
            if event["event"] == "on_chain_start":
                node = event.get("name", "")
                if node in ("classify", "sql_agent", "rag_agent", "hybrid_agent"):
                    step.name = f"Running: {node}"
                    await step.update()
            elif event["event"] == "on_chain_end":
                output = event.get("data", {}).get("output", {})
                if final := output.get("final_answer"):
                    await cl.Message(content=final).send()
```

### Pattern 6: config.yaml Structure

```yaml
# agent/config.yaml
anthropic:
  model: claude-sonnet-4-6
  max_tokens: 4096
  temperature: 0.0          # deterministic SQL generation

mcp:
  server_url: http://mcp-server:8080
  timeout_seconds: 30

qdrant:
  host: qdrant
  port: 6333
  collection: infoagent_knowledge
  top_k: 3                  # top KPI definitions to retrieve

shadowtraffic:
  output_dir: /tmp/shadowtraffic
  seed_counts:
    fato_vendas: 100000
    fato_estoque: 60000     # ~60% of product-store combos have inventory

database:
  host: postgres
  port: 5432
  name: infoagent
  readonly_user: infoagent_readonly
```

---

## Data Flow

```text
=== SEED PHASE (once at startup) ===

1. ShadowTraffic runs with dims.json + fato_vendas.json + fato_estoque.json
   │  Outputs: /tmp/shadowtraffic/dim_produto.jsonl, fato_vendas.jsonl, etc.
   ▼
2. `make seed` runs ingest/loaders/seed.py
   │  For each table:
   │    → Open JSONL file line by line
   │    → Validate each record via Pydantic model
   │    → Batch insert via psycopg2 execute_batch (page_size=1000)
   │    → Log rejected records
   ▼
3. PostgreSQL: all 6 tables populated (~160K total rows)
   │  Schema: ingest/sql/schema.sql
   │  Security: infoagent_readonly user has SELECT only
   ▼
4. Qdrant ingest: contextualize/qdrant_ingest/ingest.py
   │  Reads kpi_definitions.md, data_dictionary.md, few_shot_examples.md
   │  Embeds with LlamaIndex (OpenAI or local embedding model)
   │  Upserts into Qdrant collection "infoagent_knowledge"
   ▼
5. Stack ready: `docker compose up --wait` returns all-healthy

=== QUERY PHASE (per executive question) ===

6. Executive types question in Chainlit UI
   ▼
7. Chainlit on_message → creates AgentState, invokes graph.astream_events()
   ▼
8. classify_query node:
   │  → Claude call with classifier.txt system prompt
   │  → Returns ClassifierOutput: {query_type, kpi_name?, confidence}
   │  → If Type 2: fetch KPI definition from Qdrant, store in state.kpi_context
   ▼
9. Conditional edge routes to:
   ├── type1_sql  → sql_agent_node
   │     → list_tables() via MCP
   │     → describe_schema(table) via MCP
   │     → Claude generates SELECT with sql_agent.txt prompt
   │     → execute_read_only_query(sql) via MCP
   │     → Pydantic validates result structure
   │     → state.final_answer = formatted result
   │
   ├── type2_kpi_sql → sql_agent_node (same as above, but state.kpi_context injected into prompt)
   │
   └── type3_hybrid → hybrid_agent_node
         → Calls sql_agent_node sub-graph for numeric result
         → Calls rag_agent_node for qualitative context
         → Claude synthesises both into final_answer
   ▼
10. Chainlit renders final_answer as table/chart + CoT panel shows full traversal
```

---

## Integration Points

| External System | Integration Type | Authentication | Notes |
|-----------------|-----------------|----------------|-------|
| Anthropic API | Python SDK (`anthropic`) | `ANTHROPIC_API_KEY` env var | Used by classifier, sql_agent, rag_agent, hybrid_agent nodes |
| PostgreSQL | psycopg2 (ingest loader) | `POSTGRES_ADMIN_URL` env var | Admin user for seeding only |
| PostgreSQL | psycopg2 via MCP server | `POSTGRES_READONLY_URL` env var | Read-only user for all agent queries |
| Qdrant | LlamaIndex QdrantVectorStore + qdrant-client | No auth (local Docker) | Collection: `infoagent_knowledge` |
| ShadowTraffic | Docker container, stdout JSON | N/A | Runs once during seed; no ongoing connection |

---

## Testing Strategy

| Test Type | Scope | Files | Tools | Coverage Goal | Maps to AT |
|-----------|-------|-------|-------|---------------|------------|
| Unit | Pydantic models + validators | `tests/test_models.py` | pytest | 100% validator paths | AT-002 |
| Unit | Postgres loader error handling | `tests/test_loader.py` | pytest + tmp SQLite | Reject/accept paths | AT-002 |
| Unit | MCP READ-ONLY enforcement | `tests/test_mcp_tools.py` | pytest + mock conn | All 3 tools + rejection | AT-006 |
| Unit | Query classifier output | `tests/test_classifier.py` | pytest + Claude mock | All 3 query types | AT-003–005 |
| Integration | SQL Agent: 13 sample questions | `tests/test_sql_agent.py` | pytest + Docker DB | All 13 questions correct | AT-003, 004, 010 |
| Integration | MCP schema inspection | `tests/test_mcp_tools.py` | pytest + Docker DB | All 6 tables described | AT-009 |
| E2E | Full stack acceptance tests | `tests/test_acceptance.py` | pytest + docker compose | AT-001 through AT-010 | All |
| Manual | Chainlit CoT display | — | Browser | CoT panel visible | AT-007 |

**Test Fixtures Strategy (conftest.py):**
- `pg_conn` — pytest fixture: spins up test PostgreSQL via testcontainers, seeds minimal data
- `qdrant_client` — pytest fixture: spins up local Qdrant via testcontainers, indexes 9 KPIs
- `mock_mcp` — pytest fixture: mock MCP client for unit tests that don't need live DB

---

## Error Handling

| Error Type | Location | Handling Strategy | Retry? |
|------------|----------|-------------------|--------|
| Pydantic ValidationError during seed | `postgres_loader.py` | Log warning, skip record, continue batch | No |
| MCP tool receives non-SELECT SQL | `tools.py` | Raise `ValueError`, agent returns "I cannot modify data" | No |
| Anthropic API rate limit | All agent nodes | Catch `anthropic.RateLimitError`, return user-friendly message | Yes (1 retry with backoff) |
| Anthropic API timeout | All agent nodes | Catch `anthropic.APITimeoutError`, return timeout message | Yes (1 retry) |
| Qdrant collection not found | `rag_agent.py` | Catch `QdrantException`, log error, skip RAG context | No |
| PostgreSQL connection refused | MCP server startup | Docker healthcheck retries; compose `depends_on: condition: service_healthy` | Via Docker |
| LangGraph node exception | `graph.py` | Catch at graph level, return error state, Chainlit shows error message | No |

---

## Configuration

| Config Key | Type | Default | Description |
|------------|------|---------|-------------|
| `ANTHROPIC_API_KEY` | env | — | Required. Anthropic API key |
| `POSTGRES_ADMIN_URL` | env | — | Required for seeding. Admin DB connection |
| `POSTGRES_READONLY_URL` | env | — | Required for MCP server. Read-only DB connection |
| `anthropic.model` | yaml | `claude-sonnet-4-6` | LLM model for all agent nodes |
| `anthropic.max_tokens` | yaml | `4096` | Max tokens per agent call |
| `anthropic.temperature` | yaml | `0.0` | Deterministic SQL generation |
| `mcp.timeout_seconds` | yaml | `30` | MCP tool call timeout |
| `qdrant.top_k` | yaml | `3` | Number of KPI definitions to retrieve per query |
| `shadowtraffic.seed_counts.fato_vendas` | yaml | `100000` | Target row count for sales fact table |

---

## Security Considerations

- `infoagent_readonly` PostgreSQL user is provisioned by `create_readonly_user.sql` with `GRANT SELECT` only — no INSERT, UPDATE, DELETE, DDL
- MCP server validates all SQL with regex before execution: `^SELECT\b` (application-level guard)
- `ANTHROPIC_API_KEY` is injected via Docker environment variable, never written to config files or committed
- `.env.example` documents required env vars; `.env` is gitignored
- No user-supplied data is ever interpolated directly into SQL strings — parameterised queries only in the MCP tools
- SQL Agent system prompt explicitly instructs: "You are a READ-ONLY analyst. Never write INSERT, UPDATE, DELETE, DROP, or any DDL."
- MCP server hard-caps query results at 500 rows to prevent runaway aggregations

---

## Observability

| Aspect | Implementation |
|--------|----------------|
| Logging | Python `logging` module, structured JSON to stdout via `python-json-logger`; all agent nodes log query type, node name, duration |
| LangGraph trace | `graph.astream_events()` yields all node start/end events; Chainlit CoT panel displays these in real-time |
| Seed metrics | `seed.py` prints table-level insert/reject counts to stdout at completion |
| MCP tool calls | Each tool call logs: tool name, SQL hash (not full SQL), duration, row count returned |

---

## Revision History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | 2026-04-25 | design-agent | Initial version from DEFINE_INFOAGENT.md |

---

## Next Step

**Ready for:** `/build .claude/sdd/features/DESIGN_INFOAGENT.md`
