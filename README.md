# InfoAgent

> Natural language business intelligence for C-Level executives, powered by a multi-agent LangGraph pipeline over a PostgreSQL Star Schema data warehouse.

---

## Overview

InfoAgent lets executives at a Brazilian technology retail company ask questions like "What is the gross profit margin for Smartphones this week vs last week?" or "Is there a stockout risk for PlayStation 5 at our mall locations this weekend?" and receive structured, KPI-grounded answers in real time — without writing a single line of SQL.

Each incoming question is classified by Claude and routed through one of three execution paths: a pure SQL path for straightforward aggregations, a KPI-formula-grounded SQL path that retrieves the exact KPI definition from a Qdrant vector store before generating the query, and a hybrid path that composes SQL results with qualitative RAG context into an executive-grade Insight / Evidence / Recommendation response. Every answer includes a Chain of Thought stream in the Chainlit UI that shows the routing decision, tool calls, and query results as they happen.

The system is designed for safe, read-only access to the data warehouse. Two independent enforcement layers — a PostgreSQL `infoagent_readonly` user with no write permissions and an application-level regex guard that rejects any statement that is not a bare `SELECT` — ensure that no agent execution path can mutate data, regardless of what the language model generates.

---

## Architecture

### Query Routing (LangGraph)

```
Executive Question
        |
        v
  Chainlit UI (app.py)
        |
        v
  LangGraph Graph
        |
        v
  [classify] ── Claude JSON call ──> query_type + kpi_name
        |
        +──────────────────────────────────────────+
        |                    |                     |
        v                    v                     v
  type1_sql          type2_kpi_sql          type3_hybrid
  [sql_agent]        [sql_agent]          [hybrid_agent]
  pure SQL           SQL + KPI context    SQL + RAG synthesis
  from Qdrant pre-fetch                  -> Insight/Evidence/
                                            Recommendation
        |                    |                     |
        +────────────────────+─────────────────────+
                             |
                             v
                           END
                    (answer streamed to UI)
```

- **type1_sql**: question is a direct aggregation with no KPI formula dependency.
- **type2_kpi_sql**: question references a named KPI (e.g., gross profit margin, sell-through rate). The classifier pre-fetches the KPI formula from Qdrant and injects it into the SQL agent context before query generation.
- **type3_hybrid**: question requires both quantitative data and qualitative business context (e.g., "does the stockout risk justify an emergency order?"). The hybrid agent runs sql_agent and rag_agent sequentially, then synthesizes both into a structured executive response.

### Docker Compose Stack (5 services)

```
+------------------+     +------------------+     +-------------------+
|    postgres:15   |     |  qdrant:latest   |     | shadowtraffic     |
|  Star Schema DB  |     |  Vector Store    |     | (seed, one-shot)  |
|  port 5432       |     |  port 6333       |     |                   |
+--------+---------+     +--------+---------+     +-------------------+
         |                        |
         |    +-------------------+
         |    |
         v    v
+--------+----+-------+     +-------------------+
|  app (Chainlit UI)  |     | qdrant-ingest     |
|  port 8000          |     | (seed, one-shot)  |
|  LangGraph + agents |     |                   |
+---------------------+     +-------------------+
```

Startup order is enforced via `depends_on` with `condition: service_healthy` and `condition: service_completed_successfully`. The `app` service only starts after Qdrant is healthy and `qdrant-ingest` has finished indexing the knowledge documents.

---

## Quick Start

### Prerequisites

- Docker Desktop (or Docker Engine + Compose plugin)
- Python 3.11 or higher (for local development only; not required for the Docker stack)
- An Anthropic API key with access to `claude-sonnet-4-6`

### 1. Configure environment variables

```
cp .env.example .env
```

Open `.env` and set your Anthropic API key:

```
ANTHROPIC_API_KEY=sk-ant-...
```

The remaining variables in `.env.example` have working defaults for local development and do not need to be changed unless you want to use a non-default database password.

### 2. Start the full stack

```
make up
```

This runs `docker compose up -d --wait`, which starts all five services and waits for all health checks to pass. On first run, Docker pulls the base images and ShadowTraffic generates and inserts 160,000 rows into PostgreSQL. Allow 3–5 minutes on first run; subsequent starts are faster because volumes are persisted.

### 3. Open the executive chat interface

Navigate to `http://localhost:8000` in your browser.

You will see the InfoAgent welcome screen. Type any business question in natural language. Example questions from the Chainlit welcome screen:

- "What were the sales figures for yesterday?"
- "What is the gross profit margin for Smartphones this week vs last week?"
- "Is there a stockout risk for PlayStation 5 at our mall locations this weekend?"
- "Which 5 stores had the lowest Notebook sales this quarter?"

### 4. Stop and clean up

```
make down
```

This runs `docker compose down -v`, which stops all containers and removes the named volumes. Use this when you want a full reset including the seeded database.

---

## Features

- **3-type intelligent routing**: LangGraph classifies every question and dispatches to the optimal execution path — pure SQL, KPI-grounded SQL, or hybrid SQL + RAG — rather than applying a single strategy to all question types.
- **Qdrant KPI grounding**: Type 2 queries retrieve the exact KPI formula from a Qdrant collection before generating SQL, eliminating hallucinated formulas for metrics like gross profit margin, sell-through rate, and inventory coverage days.
- **Real-time Chain of Thought streaming**: The Chainlit UI uses `astream_events` v2 with LangGraph to stream node-level events — routing decision, tool calls, SQL queries, and retrieved context — as they happen, giving executives visibility into how every answer was derived.
- **Double READ-ONLY enforcement**: A PostgreSQL `infoagent_readonly` database user (no INSERT / UPDATE / DELETE / DDL grants) combined with an application-level regex guard that rejects any statement not matching a bare `SELECT` pattern. Two independent layers mean a prompt injection that bypasses one layer is still stopped by the other.
- **Pydantic validation on all data models**: All six Star Schema models (2 fact tables, 4 dimension tables) have Pydantic v2 validators. The seed loader runs a post-load validation pass and reports any constraint violations before the application starts.
- **Seasonal synthetic data**: ShadowTraffic generates 100,000 `fato_vendas` rows and 60,000 `fato_estoque` rows with realistic Brazilian retail seasonal patterns (Black Friday, holiday peaks, weekday/weekend variation) using weighted generators.
- **10 KPIs documented in the knowledge base**: The Qdrant collection contains three Markdown knowledge documents — KPI definitions (10 KPIs with formulas), a data dictionary (table and column descriptions), and 13 few-shot SQL examples — all indexed via LlamaIndex with HuggingFace BGE-small embeddings.
- **Fully mocked test suite**: Seven test files covering all 10 acceptance criteria using `unittest.mock`, keeping tests fast and dependency-free (no live database required to run `make test`).

---

## Project Structure

```
Swift-Decision-Data/
├── agent/                        LangGraph agent layer
│   ├── graph.py                  StateGraph definition: classify -> type1/type2/type3 -> END
│   ├── state.py                  AgentState TypedDict (query, query_type, kpi_context, sql_result, final_answer)
│   ├── config.yaml               Model, Qdrant, and database configuration
│   ├── nodes/
│   │   ├── classifier.py         Claude JSON call; extracts query_type and kpi_name
│   │   ├── sql_agent.py          10-iteration tool_use loop with direct psycopg2 readonly connection
│   │   ├── rag_agent.py          Qdrant similarity retrieval + Claude synthesis
│   │   └── hybrid_agent.py       Sequential sql_agent + rag_agent -> Insight/Evidence/Recommendation
│   └── prompts/                  Prompt text files for each agent node
│
├── ingest/                       Data layer
│   ├── models/                   Pydantic v2 Star Schema models
│   │   ├── fato_vendas.py        Sales fact table model (100K rows)
│   │   ├── fato_estoque.py       Inventory fact table model (60K rows)
│   │   ├── dim_produto.py        Product dimension with DepartamentoEnum
│   │   ├── dim_cliente.py        Customer dimension with CategoriaClienteEnum, GeneroEnum
│   │   ├── dim_loja.py           Store dimension
│   │   └── dim_tempo.py          Time dimension
│   ├── sql/
│   │   ├── schema.sql            6-table DDL with FK constraints and 5 indexes
│   │   └── create_readonly_user.sql  Idempotent infoagent_readonly user creation
│   ├── shadowtraffic/            ShadowTraffic JSON configs for synthetic data generation
│   │   ├── dims.json             Dimension tables (100 rows each)
│   │   ├── fato_vendas.json      Sales facts with seasonal patterns (100K rows)
│   │   └── fato_estoque.json     Inventory facts (60K rows)
│   └── loaders/
│       └── seed.py               Post-load Pydantic validation with tabular report
│
├── contextualize/                Vector store layer
│   ├── knowledge/
│   │   ├── kpi_definitions.md    10 KPI formulas (gross profit margin, sell-through rate, etc.)
│   │   ├── data_dictionary.md    Table and column descriptions for all 6 schema objects
│   │   └── few_shot_examples.md  13 annotated SQL examples for KPI and hybrid queries
│   ├── qdrant_ingest/
│   │   └── ingest.py             LlamaIndex + HuggingFace BGE-small indexing pipeline
│   └── mcp_server/               MCP stdio server (3 tools, SHA-256 query log, 500-row cap)
│
├── ui/                           Chainlit executive chat interface
│   ├── app.py                    astream_events CoT streaming, on_chain_start/end event handling
│   ├── chainlit.md               Welcome screen with example executive questions
│   └── Dockerfile                UI container image
│
├── tests/                        Test suite (fully mocked, no live dependencies)
│   ├── conftest.py               Shared fixtures
│   ├── test_acceptance.py        AT-001 through AT-010 acceptance criteria
│   ├── test_classifier.py        Classifier node unit tests
│   ├── test_loader.py            Seed loader validation tests
│   ├── test_mcp_tools.py         MCP server tool tests
│   ├── test_models.py            Pydantic model validator tests
│   └── test_sql_agent.py         SQL agent node and READ-ONLY guard tests
│
├── docker-compose.yml            5-service stack with ordered startup and health checks
├── Dockerfile                    Application container image (seed and qdrant-ingest services)
├── pyproject.toml                Project metadata, dependencies, ruff and mypy configuration
├── Makefile                      Developer commands (up, down, seed, dev, test, lint, format)
└── .env.example                  Required environment variables template
```

---

## Development

All developer commands are defined in the `Makefile`. Run them from the project root.

| Command | Description |
|---------|-------------|
| `make up` | Start the full Docker Compose stack in detached mode and wait for all health checks to pass. |
| `make down` | Stop all containers and remove named volumes (`postgres_data`, `qdrant_data`). Full reset. |
| `make seed` | Start the stack (if not running), then run `python -m ingest.loaders.seed` locally for post-load Pydantic validation with a tabular report. Requires `pip install -e .` to have been run. |
| `make dev` | Start the stack and then run Chainlit in watch mode (`chainlit run ui/app.py --watch`) for live-reload development of the UI and agent code. |
| `make test` | Run the full test suite with `pytest tests/ -v`. No live database or Qdrant instance required; all tests use mocks. |
| `make lint` | Run `ruff check .` to check for code style and import issues across all packages. |
| `make format` | Run `ruff format .` to auto-format all Python files. |

### Local development setup

```
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env
make up
make dev
```

The `make dev` target starts the Docker stack (PostgreSQL + Qdrant + ShadowTraffic seed + Qdrant ingest) and then launches Chainlit locally with `--watch`. Changes to files in `agent/`, `ui/`, and `contextualize/` will trigger a Chainlit reload.

---

## Testing

```
make test
```

The test suite uses `pytest` with `asyncio_mode = "auto"` (configured in `pyproject.toml`). All tests use `unittest.mock` and do not require a running database or Qdrant instance.

### Test files and coverage

| File | What it covers |
|------|---------------|
| `tests/test_acceptance.py` | All 10 acceptance criteria (AT-001 through AT-010): routing structure, Pydantic validation, classifier output for all three query types, READ-ONLY guard rejection of mutating statements, AgentState fields, model importability, MCP tool names, ClassifierOutput schema. |
| `tests/test_classifier.py` | Classifier node: correct `query_type` output for type1, type2, and type3 inputs; KPI name extraction; JSON-only output parsing. |
| `tests/test_loader.py` | Seed loader: Pydantic validation on valid and invalid rows; post-load report structure. |
| `tests/test_mcp_tools.py` | MCP server: `list_tools` returns the three expected tool names; tool call routing. |
| `tests/test_models.py` | All six Pydantic models: field types, enum constraints, and validator rejection of out-of-range or null values. |
| `tests/test_sql_agent.py` | SQL agent node: tool_use loop execution; READ-ONLY regex guard rejection of DELETE, INSERT, DROP, UPDATE, ALTER, CREATE, and TRUNCATE statements; `json.dumps(default=str)` serialization of Decimal and datetime values. |

### Running a specific test

```
pytest tests/test_acceptance.py -v
pytest tests/test_sql_agent.py::test_readonly_guard_rejects_delete -v
```

---

## Configuration

### Environment variables

Copy `.env.example` to `.env` and fill in the values before running `make up` or `make dev`.

| Variable | Required | Description |
|----------|----------|-------------|
| `ANTHROPIC_API_KEY` | Yes | Anthropic API key with access to `claude-sonnet-4-6`. |
| `POSTGRES_ADMIN_URL` | Yes (seed only) | Full connection URL for the admin user. Used only by `seed.py` for DDL and validation; not used by the app at runtime. |
| `POSTGRES_READONLY_URL` | Yes | Full connection URL for the `infoagent_readonly` user. This is the only database connection the agent layer uses at runtime. |
| `POSTGRES_DB` | Yes (Compose) | Database name. Used by `docker-compose.yml` to initialize the PostgreSQL container. Default: `infoagent`. |
| `POSTGRES_USER` | Yes (Compose) | Admin username for the PostgreSQL container. Default: `infoagent_admin`. |
| `POSTGRES_PASSWORD` | Yes (Compose) | Admin password. Default: `changeme` — change this for any non-local deployment. |
| `POSTGRES_READONLY_PASSWORD` | Yes (Compose) | Password for the `infoagent_readonly` user. Default: `readonly_changeme`. |

### Agent configuration (`agent/config.yaml`)

| Setting | Value | Description |
|---------|-------|-------------|
| `anthropic.model` | `claude-sonnet-4-6` | Model used by all agent nodes (classifier, SQL agent, RAG agent, hybrid agent). |
| `anthropic.max_tokens` | `4096` | Maximum tokens per Claude response. |
| `anthropic.temperature` | `0.0` | Deterministic outputs for SQL generation and classification. |
| `qdrant.collection` | `infoagent_knowledge` | Qdrant collection name containing all three knowledge documents. |
| `qdrant.top_k` | `3` | Number of chunks retrieved per Qdrant similarity search. |

---

## Security

### READ-ONLY enforcement

InfoAgent uses two independent enforcement layers to guarantee that no agent execution path can modify the data warehouse:

**Layer 1 — PostgreSQL database user**

The `infoagent_readonly` user is created by `ingest/sql/create_readonly_user.sql` at container initialization time. This user is granted `CONNECT` on the database and `SELECT` on all tables in the `public` schema. No `INSERT`, `UPDATE`, `DELETE`, `TRUNCATE`, or DDL grants are issued. The `app` service connects exclusively as this user via `POSTGRES_READONLY_URL`. The admin user credentials (`POSTGRES_ADMIN_URL`) are never passed to the app container.

**Layer 2 — Application-level SELECT guard**

The SQL agent node applies a regex guard to every statement it is about to execute. Any statement that does not begin with `SELECT` (case-insensitive, after stripping leading whitespace) is rejected at the application layer before it reaches the database connection. This guard catches prompt injection attempts that could generate `DELETE`, `INSERT`, `DROP`, `UPDATE`, `ALTER`, `CREATE`, or `TRUNCATE` statements. Acceptance test AT-006 validates rejection of all seven mutating statement types.

Together, these layers mean that even if a language model generates a mutating SQL statement — whether through a prompt injection, model error, or unexpected input — it will be blocked by the application guard before touching the database connection, and blocked again at the database layer if it somehow reached the connection.

---

## Data

### Star Schema

The data warehouse follows a classic Star Schema with two fact tables and four dimension tables.

| Table | Type | Rows | Description |
|-------|------|------|-------------|
| `fato_vendas` | Fact | 100,000 | Sales transactions: product, customer, store, date, quantity, unit price, total value, discount, and holiday flag. |
| `fato_estoque` | Fact | 60,000 | Inventory snapshots: product, store, date, quantity on hand, reorder point, and stock-out flag. |
| `dim_produto` | Dimension | 100 | Products with department (Smartphones, Notebooks, TVs, etc.), brand, and unit cost. |
| `dim_cliente` | Dimension | 100 | Customers with category (VIP, Standard, Occasional) and demographic attributes. |
| `dim_loja` | Dimension | 100 | Stores with location type (mall, street, outlet) and region. |
| `dim_tempo` | Dimension | 100 | Date dimension with weekday flags, holiday flags, and fiscal period attributes. |

### Synthetic data generation

Data is generated by [ShadowTraffic](https://shadowtraffic.io/) using three JSON configuration files in `ingest/shadowtraffic/`. ShadowTraffic writes directly to PostgreSQL. The generation follows strict foreign-key order: dimension tables are seeded first, then `fato_vendas`, then `fato_estoque`. Each row in the fact tables references a valid primary key in all four dimension tables.

The `fato_vendas` configuration uses weighted generators to produce seasonal patterns: higher sales volumes during November–December (Black Friday and Christmas), elevated weekend traffic, and a `flg_feriado` (holiday flag) correlated with sales spikes. This makes the synthetic data suitable for demonstrating KPI trend analysis and anomaly detection queries.

After ShadowTraffic completes, the `seed` service in Docker Compose runs `python -m ingest.loaders.seed`, which reads a sample of rows from each table, validates them against the corresponding Pydantic models, and prints a tabular validation report. Zero validation errors is a success criterion for the stack startup.

### Knowledge base (Qdrant)

Three Markdown documents are indexed into the `infoagent_knowledge` Qdrant collection at startup by the `qdrant-ingest` service:

| Document | Contents |
|----------|----------|
| `kpi_definitions.md` | 10 KPI formulas with definitions: gross profit margin, net revenue, sell-through rate, inventory coverage days, average ticket, return rate, and others. Used by the Type 2 classifier path to inject the correct formula before SQL generation. |
| `data_dictionary.md` | Descriptions of all 6 tables and their columns, including data types, nullable constraints, and business meaning. |
| `few_shot_examples.md` | 13 annotated SQL examples covering all three query types, used as retrieval context for complex and KPI-grounded queries. |

Indexing uses LlamaIndex with `BAAI/bge-small-en-v1.5` HuggingFace embeddings (768-dimensional). The `qdrant-ingest` service runs once at startup and exits; the vector store data is persisted in the `qdrant_data` Docker volume.

---

## License

See the repository root for license information.
