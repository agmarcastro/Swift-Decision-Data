# InfoAgent — Execution & Deployment Guide

> **Project:** InfoAgent — Multi-Agent Executive Intelligence System
> **Stack:** Python 3.11 · LangChain/CrewAI · Anthropic Claude · PostgreSQL · Qdrant · Chainlit · LangFuse
> **Last updated:** 2026-04-28

---

## Table of Contents

1. [Architecture Overview](#1-architecture-overview)
2. [Prerequisites](#2-prerequisites)
3. [Environment Configuration](#3-environment-configuration)
4. [Local Development — Full Stack](#4-local-development--full-stack)
5. [Startup Sequence Explained](#5-startup-sequence-explained)
6. [Running the Application Locally](#6-running-the-application-locally)
7. [Running Tests](#7-running-tests)
8. [Observability — LangFuse](#8-observability--langfuse)
9. [Production Deployment](#9-production-deployment)
10. [Common Issues & Fixes](#10-common-issues--fixes)
11. [Key Service Ports Reference](#11-key-service-ports-reference)

---

## 1. Architecture Overview

InfoAgent is a **three-layer pipeline** — each layer must be operational before the next can run:

```
┌──────────────┐    ┌───────────────────┐    ┌──────────────────┐
│    INGEST    │───▶│  CONTEXTUALIZE    │───▶│     AGENT        │
│              │    │                   │    │                  │
│ ShadowTraffic│    │ Qdrant (vectors)  │    │ ReAct Agent      │
│ PostgreSQL   │    │ LlamaIndex (RAG)  │    │ + CrewAI Crew    │
│ Pydantic     │    │                   │    │ Chainlit UI      │
└──────────────┘    └───────────────────┘    └──────────────────┘
```

**Data flow for a user question:**
```
User Question → Chainlit UI
  → _needs_crew()? 
      YES → CrewAI (Analyst + Researcher + Reporter) → answer + DeepEval scoring
      NO  → ReAct Agent (LangChain) → sql_tool / rag_tool → answer
```

**Two tools available to the agent:**
- `sql_tool` — executes READ-ONLY SELECT queries against the PostgreSQL Star Schema
- `rag_tool` — semantic search across two Qdrant collections (`infoagent_knowledge`, `reviews`)

---

## 2. Prerequisites

### 2.1 Required Software

| Tool | Minimum Version | Purpose |
|------|----------------|---------|
| Python | 3.11 | Runtime |
| Docker Desktop | 24+ | All services |
| Docker Compose | v2 (bundled with Docker Desktop) | Orchestration |
| Git | Any | Source control |

### 2.2 Required Credentials

| Credential | Where to obtain |
|------------|----------------|
| `ANTHROPIC_API_KEY` | console.anthropic.com → API Keys |
| `LANGFUSE_PUBLIC_KEY` | LangFuse UI → Settings → API Keys (generated after first login) |
| `LANGFUSE_SECRET_KEY` | Same as above |

> **Note:** The HuggingFace embedding model (`BAAI/bge-small-en-v1.5`) downloads automatically on first run — no API key required for embeddings.

### 2.3 System Resources (Recommended)

- RAM: 8 GB minimum (16 GB recommended — PostgreSQL + Qdrant + Chainlit + LangFuse all run simultaneously)
- Disk: 5 GB free (Docker images + Qdrant vector storage + PostgreSQL data)
- Network: Internet access for `docker pull` and Anthropic API calls

---

## 3. Environment Configuration

### 3.1 Create the `.env` file

Copy the example file and fill in your secrets:

```bash
cp .env.example .env
```

Then edit `.env` with real values:

```dotenv
# Anthropic — required for the agent layer
ANTHROPIC_API_KEY=sk-ant-YOUR_KEY_HERE

# PostgreSQL — admin user (used by seed validation and Qdrant ingest)
POSTGRES_ADMIN_URL=postgresql://infoagent_admin:changeme@localhost:5432/infoagent

# PostgreSQL — read-only user (used by the agent's sql_tool)
POSTGRES_READONLY_URL=postgresql://infoagent_readonly:readonly_changeme@localhost:5432/infoagent

# PostgreSQL credentials (picked up by docker-compose)
POSTGRES_DB=infoagent
POSTGRES_USER=infoagent_admin
POSTGRES_PASSWORD=changeme
POSTGRES_READONLY_PASSWORD=readonly_changeme

# LangFuse — observability (generate keys from the LangFuse UI on first login)
LANGFUSE_HOST=http://langfuse:3000
LANGFUSE_PUBLIC_KEY=pk-lf-YOUR_KEY
LANGFUSE_SECRET_KEY=sk-lf-YOUR_KEY
LANGFUSE_NEXTAUTH_SECRET=choose_a_strong_secret
LANGFUSE_SALT=choose_a_salt_value
```

> **Security note for production:** Never commit `.env` to git. The `.gitignore` already excludes it.

---

## 4. Local Development — Full Stack

### 4.1 Install Python dependencies

```bash
pip install -e ".[dev]"
```

This installs all runtime and development dependencies declared in `pyproject.toml` (Pydantic, LangChain, CrewAI, LlamaIndex, Qdrant client, Chainlit, LangFuse, pytest, ruff, etc.).

### 4.2 Start the full Docker stack

```bash
make up
```

This runs `docker compose up -d --wait` which:
1. Pulls all images on first run
2. Starts `postgres` and `qdrant` and waits for their health checks to pass
3. Runs `shadowtraffic` (generates ~172,100 rows of synthetic data) — exits when done
4. Runs `seed` (validates row counts) — exits when done
5. Runs `qdrant-ingest` (embeds knowledge docs + reviews into Qdrant) — exits when done
6. Starts `langfuse` (observability dashboard)
7. Starts `app` (Chainlit UI)

**Expected first-run time:** 5–10 minutes (image pulls + data generation + embedding).

**Verify all services are healthy:**

```bash
docker compose ps
```

All long-running services (`postgres`, `qdrant`, `langfuse`, `app`) should show `healthy` or `running`.

### 4.3 Tear down the stack

```bash
make down
```

This removes all containers **and all named volumes** (PostgreSQL data, Qdrant storage). The next `make up` will re-seed from scratch.

> To stop containers without deleting volumes, use: `docker compose down` (no `-v` flag).

---

## 5. Startup Sequence Explained

Understanding the dependency chain avoids confusion when individual services fail:

```
postgres ──────────────────────────────────────────────┐
  └─(healthy)─▶ shadowtraffic (generates data, exits)  │
                  └─(completed)─▶ seed (validates, exits)
                  └─(completed)─▶ qdrant-ingest (embeds, exits)
qdrant ────────────────────────────────────────────────┤
  └─(healthy)─▶ qdrant-ingest (embeds, exits)          │
                                                        │
postgres + qdrant + qdrant-ingest ──────────────────────▶ app (Chainlit)
postgres ────────────────────────────────────────────────▶ langfuse
```

**Key insight:** `app` will not start until `qdrant-ingest` completes successfully. If embedding fails (e.g., network issue downloading the HuggingFace model), `app` will not come up.

---

## 6. Running the Application Locally

### 6.1 Option A — Via Docker (recommended for testing the full stack)

After `make up`, the Chainlit UI is available at:

```
http://localhost:8000
```

### 6.2 Option B — Via Makefile (hot-reload development)

```bash
make dev
```

This runs `chainlit run ui/app.py --watch`, which hot-reloads on file changes. Requires the Docker stack to be up (`make up`) since it connects to the containerized PostgreSQL and Qdrant.

### 6.3 Option C — Directly with Chainlit

```bash
# Ensure the Docker stack is running first
make up

# Export env vars if not already in shell
export $(cat .env | grep -v '^#' | xargs)

# Override Qdrant host to localhost (outside Docker)
export QDRANT_HOST=localhost

chainlit run ui/app.py --host 0.0.0.0 --port 8000
```

### 6.4 Example questions to test

The agent routes questions automatically based on content:

| Question type | Example |
|--------------|---------|
| SQL (figures) | "Qual foi o faturamento total em março?" |
| RAG (KPIs/rules) | "Como é calculada a margem bruta?" |
| CrewAI (hybrid: figures + opinion) | "Quais foram as vendas de Gaming e quais as reclamações dos clientes?" |

---

## 7. Running Tests

### 7.1 Unit tests (no services required)

```bash
make test
# or equivalently:
pytest tests/ -v
```

All unit tests mock external services (PostgreSQL, Qdrant, Anthropic API). No `.env` required.

### 7.2 Lint and format

```bash
make lint      # ruff check .
make format    # ruff format .
```

### 7.3 Individual test files

```bash
# Pydantic model validation
pytest tests/test_models.py -v

# Data loader logic
pytest tests/test_loader.py -v

# MCP tools (read-only guard, tool catalogue)
pytest tests/test_mcp_tools.py -v

# ReAct agent integration
pytest tests/test_react_agent.py -v

# CrewAI crew
pytest tests/test_crew.py -v

# LangFuse observability callbacks
pytest tests/test_langfuse_handler.py -v

# DeepEval quality scorer
pytest tests/test_deepeval_scorer.py -v

# Acceptance criteria (AT-001 through AT-010)
pytest tests/test_acceptance.py -v
```

### 7.4 Integration tests (requires running Docker stack)

```bash
make up
pytest tests/ -m integration -v
make down
```

### 7.5 CI pipeline pattern

```bash
ruff check .
pytest tests/ -m "not integration" -v
```

---

## 8. Observability — LangFuse

LangFuse traces every agent invocation (ReAct + CrewAI) and provides quality scores from DeepEval.

**Access the dashboard:**

```
http://localhost:3000
```

**First login:** Create an account on the local LangFuse instance. Then go to **Settings → API Keys** and generate `LANGFUSE_PUBLIC_KEY` / `LANGFUSE_SECRET_KEY`. Update your `.env` with these values and restart the `app` service:

```bash
docker compose restart app
```

**What is traced:**
- Every ReAct agent run with tool calls (`sql_tool`, `rag_tool`)
- Every CrewAI crew kickoff with per-agent steps
- DeepEval scores: Faithfulness, Relevance, Hallucination (appended to traces)

---

## 9. Production Deployment

The current architecture uses Docker Compose, which is suited for single-server or small-team deployments. The services map cleanly to managed cloud equivalents for scale.

### 9.1 Recommended Production Service Mapping

| Local service | Production equivalent |
|--------------|----------------------|
| `postgres` (Docker) | AWS RDS / GCP Cloud SQL / Azure Database for PostgreSQL |
| `qdrant` (Docker) | Qdrant Cloud (qdrant.io) or self-hosted on a VM |
| `app` (Chainlit) | Docker container on GCP Cloud Run / AWS ECS / Azure Container Apps |
| `langfuse` (Docker) | LangFuse Cloud (langfuse.com) or self-hosted |
| ShadowTraffic | Replace with real production data ingestion pipeline |

### 9.2 Step-by-Step Production Deployment

#### Step 1 — Provision infrastructure

Provision (or confirm access to):
- A managed PostgreSQL instance (PostgreSQL 15+)
- A Qdrant cluster or Qdrant Cloud collection
- A container registry (e.g., Docker Hub, GCR, ECR)
- A container hosting platform (Cloud Run, ECS, etc.)

#### Step 2 — Prepare the production database

Run the DDL against your production PostgreSQL instance:

```bash
psql $PROD_POSTGRES_ADMIN_URL -f ingest/sql/schema.sql
psql $PROD_POSTGRES_ADMIN_URL -f ingest/sql/create_readonly_user.sql
```

> For LangFuse: run `ingest/sql/03_langfuse_db.sql` only if hosting LangFuse yourself on the same PostgreSQL instance.

#### Step 3 — Seed the Qdrant knowledge base

Run the Qdrant ingest against your production Qdrant instance:

```bash
QDRANT_HOST=your-qdrant-host \
QDRANT_PORT=6333 \
QDRANT_COLLECTION=infoagent_knowledge \
POSTGRES_ADMIN_URL=postgresql://... \
python -m contextualize.qdrant_ingest.ingest
```

This is idempotent — safe to re-run when knowledge documents are updated.

#### Step 4 — Build and push the Docker image

```bash
# Build the UI/app image
docker build -f ui/Dockerfile -t your-registry/infoagent-app:latest .

# Push to registry
docker push your-registry/infoagent-app:latest
```

#### Step 5 — Set production environment variables

The `app` container requires these environment variables at runtime:

```dotenv
ANTHROPIC_API_KEY=sk-ant-...
POSTGRES_READONLY_URL=postgresql://infoagent_readonly:PASSWORD@prod-host:5432/infoagent
QDRANT_HOST=your-qdrant-host
QDRANT_PORT=6333
LANGFUSE_HOST=https://cloud.langfuse.com   # or your self-hosted URL
LANGFUSE_PUBLIC_KEY=pk-lf-...
LANGFUSE_SECRET_KEY=sk-lf-...
```

> Inject these via your cloud platform's secrets manager (AWS Secrets Manager, GCP Secret Manager, Azure Key Vault) — never hard-code them in the image.

#### Step 6 — Deploy the container

**Example — GCP Cloud Run:**

```bash
gcloud run deploy infoagent-app \
  --image your-registry/infoagent-app:latest \
  --platform managed \
  --region us-central1 \
  --port 8000 \
  --set-secrets ANTHROPIC_API_KEY=infoagent-anthropic-key:latest \
  --set-env-vars POSTGRES_READONLY_URL=postgresql://...,QDRANT_HOST=...,QDRANT_PORT=6333 \
  --allow-unauthenticated
```

**Example — Docker Compose on a VM (simplest production path):**

```bash
# On the production VM
git clone <repo>
cd Swift-Decision-Data
cp .env.example .env
# Edit .env with production credentials
# Point POSTGRES_ADMIN_URL / POSTGRES_READONLY_URL to managed PostgreSQL
# Point QDRANT_HOST to managed Qdrant
# Remove shadowtraffic / seed / qdrant-ingest services from docker-compose.yml
#   (or override with docker-compose.prod.yml)
docker compose up -d app langfuse
```

#### Step 7 — Verify deployment health

The `app` service exposes a health endpoint:

```bash
curl http://your-production-host:8000/healthz
```

Expected response: HTTP 200.

#### Step 8 — Configure authentication (recommended)

The current Chainlit app has no authentication. For C-Level executive access, configure one of:

- **Chainlit built-in auth** — add `@cl.password_auth_callback` or `@cl.oauth_callback` to `ui/app.py`
- **Reverse proxy auth** — put NGINX/Traefik with OAuth2 Proxy in front of the container
- **Cloud platform IAM** — use Cloud Run IAM for Google-account-based access control

### 9.3 Production Checklist

```
[ ] ANTHROPIC_API_KEY in secrets manager (not in .env file)
[ ] LANGFUSE keys in secrets manager
[ ] PostgreSQL read-only user password rotated from default
[ ] Qdrant knowledge base seeded with production knowledge docs
[ ] reviews Qdrant collection seeded from real customer review data
[ ] app container health check passing
[ ] LangFuse traces flowing and DeepEval scores appearing
[ ] Authentication configured for the Chainlit UI
[ ] SQL read-only enforcement verified (only SELECT allowed)
[ ] Monitoring/alerting on the app container health check
```

---

## 10. Common Issues & Fixes

### `app` container not starting

**Cause:** `qdrant-ingest` failed, which blocks `app` from starting.

**Fix:**
```bash
docker compose logs qdrant-ingest
```

Common sub-causes:
- Qdrant not healthy yet → wait and retry `docker compose up -d --wait`
- HuggingFace model download failed (no internet) → check network connectivity
- Missing knowledge files in `contextualize/knowledge/` → restore from git

### `sql_tool` returns "Erro ao conectar ao banco"

**Cause:** `POSTGRES_READONLY_URL` is incorrect or the read-only user was not created.

**Fix:**
```bash
# Verify the read-only user exists
psql $POSTGRES_ADMIN_URL -c "\du infoagent_readonly"

# If missing, re-run the SQL
psql $POSTGRES_ADMIN_URL -f ingest/sql/create_readonly_user.sql
```

### `rag_tool` returns "Nenhum trecho relevante encontrado"

**Cause:** The Qdrant collections are empty — `qdrant-ingest` did not run successfully.

**Fix:**
```bash
# Re-run the ingest manually
docker compose run --rm qdrant-ingest
```

### LangFuse traces not appearing

**Cause:** `LANGFUSE_PUBLIC_KEY` / `LANGFUSE_SECRET_KEY` are not set or point to wrong host.

**Fix:** Log into `http://localhost:3000`, regenerate API keys, update `.env`, then:
```bash
docker compose restart app
```

### ShadowTraffic exits with an error

**Cause:** License not accepted or incompatible config schema.

**Fix:**
```bash
docker compose logs shadowtraffic
```

Ensure `LICENSE_ACCEPTED: "true"` is set in `docker-compose.yml` (already set by default).

### `ANTHROPIC_API_KEY` not set

**Symptom:** `KeyError: 'ANTHROPIC_API_KEY'` in `app` logs.

**Fix:** Ensure the variable is exported in `.env` and `docker-compose.yml` passes it through (already wired for the `app` service).

---

## 11. Key Service Ports Reference

| Service | Local port | Purpose |
|---------|-----------|---------|
| Chainlit UI | `8000` | Executive chat interface |
| LangFuse | `3000` | Observability dashboard |
| PostgreSQL | `5432` | Relational data warehouse |
| Qdrant | `6333` | Vector store (REST API) |

---

*Guide version: 1.0.0 — Generated 2026-04-28*
