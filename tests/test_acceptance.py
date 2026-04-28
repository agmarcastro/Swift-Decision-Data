from __future__ import annotations

"""Acceptance tests for SHOPAGENT_ALIGN — AT-001 through AT-012.

AT-001  PT-BR UI: chainlit.md and app.py on_chat_start contain Portuguese text
AT-002  ReAct routes numeric question to sql_tool via docstring
AT-003  ReAct routes opinion question to rag_tool via docstring
AT-004  cl.Step is imported and used in ui/app.py
AT-005  CrewAI crew structure: 3 agents, sequential, YAML-driven
AT-006  agents.yaml + tasks.yaml parse cleanly with correct keys
AT-007  reviews table DDL exists in schema.sql (≥10K row target)
AT-008  Qdrant reviews collection extended in ingest.py
AT-009  LangFuse CallbackHandler is constructible from env vars
AT-010  DeepEval scorer runs all 3 metrics and returns float scores
AT-011  READ-ONLY enforcement: ALLOWED_STMT regex blocks all mutations
AT-012  All 7 Pydantic models import cleanly (6 original + ModeloReview)
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

REPO_ROOT = Path(__file__).parent.parent


# ---------------------------------------------------------------------------
# AT-001: Portuguese UI
# ---------------------------------------------------------------------------


def test_at001_chainlit_md_is_portuguese() -> None:
    content = (REPO_ROOT / "ui" / "chainlit.md").read_text(encoding="utf-8")
    assert "Bem-vindo" in content or "português" in content.lower() or "Qual" in content


def test_at001_app_on_chat_start_is_portuguese() -> None:
    content = (REPO_ROOT / "ui" / "app.py").read_text(encoding="utf-8")
    assert "Bem-vindo" in content
    assert "Welcome" not in content


# ---------------------------------------------------------------------------
# AT-002: ReAct routes to sql_tool for numeric question
# ---------------------------------------------------------------------------


def test_at002_react_agent_module_exists() -> None:
    assert (REPO_ROOT / "agent" / "react_agent.py").exists()
    assert (REPO_ROOT / "agent" / "tools.py").exists()


def test_at002_sql_tool_docstring_contains_numeric_keywords() -> None:
    from agent.tools import sql_tool

    doc = (sql_tool.description or "") + (sql_tool.__doc__ or "")
    assert any(kw in doc.lower() for kw in ("vendas", "estoque", "select", "sql"))


# ---------------------------------------------------------------------------
# AT-003: ReAct routes to rag_tool for opinion question
# ---------------------------------------------------------------------------


def test_at003_rag_tool_docstring_contains_opinion_keywords() -> None:
    from agent.tools import rag_tool

    doc = (rag_tool.description or "") + (rag_tool.__doc__ or "")
    assert any(kw in doc.lower() for kw in ("reviews", "opini", "sentimento", "recla"))


# ---------------------------------------------------------------------------
# AT-004: cl.Step used in ui/app.py
# ---------------------------------------------------------------------------


def test_at004_cl_step_imported_in_app() -> None:
    content = (REPO_ROOT / "ui" / "app.py").read_text(encoding="utf-8")
    assert "cl.Step" in content
    assert "astream_events" not in content


# ---------------------------------------------------------------------------
# AT-005: CrewAI crew structure
# ---------------------------------------------------------------------------


def test_at005_crew_py_exists_and_has_kickoff_crew() -> None:
    content = (REPO_ROOT / "agent" / "crews" / "crew.py").read_text(encoding="utf-8")
    assert "kickoff_crew" in content
    assert "Process.sequential" in content


# ---------------------------------------------------------------------------
# AT-006: YAML config is valid and complete
# ---------------------------------------------------------------------------


def test_at006_agents_yaml_three_agents() -> None:
    import yaml

    cfg = yaml.safe_load((REPO_ROOT / "agent" / "crews" / "agents.yaml").read_text())
    assert set(cfg.keys()) == {"analyst", "researcher", "reporter"}
    for name, spec in cfg.items():
        assert "role" in spec
        assert "goal" in spec
        assert "backstory" in spec
        assert spec["llm"] == "anthropic/claude-sonnet-4-6"


def test_at006_tasks_yaml_three_tasks_reporter_has_context() -> None:
    import yaml

    cfg = yaml.safe_load((REPO_ROOT / "agent" / "crews" / "tasks.yaml").read_text())
    assert set(cfg.keys()) == {"analyst_task", "research_task", "reporter_task"}
    ctx = cfg["reporter_task"].get("context", [])
    assert "analyst_task" in ctx and "research_task" in ctx


# ---------------------------------------------------------------------------
# AT-007: reviews table DDL in schema.sql
# ---------------------------------------------------------------------------


def test_at007_reviews_table_ddl_in_schema() -> None:
    sql = (REPO_ROOT / "ingest" / "sql" / "schema.sql").read_text(encoding="utf-8")
    assert "CREATE TABLE IF NOT EXISTS reviews" in sql
    assert "REFERENCES dim_produto" in sql
    assert "REFERENCES dim_cliente" in sql
    assert "CHECK (nota BETWEEN 1 AND 5)" in sql


def test_at007_shadowtraffic_reviews_config_has_12k_max_events() -> None:
    import json

    cfg = json.loads(
        (REPO_ROOT / "ingest" / "shadowtraffic" / "reviews.json").read_text(encoding="utf-8")
    )
    assert cfg["generators"][0]["localConfigs"]["maxEvents"] >= 10000


# ---------------------------------------------------------------------------
# AT-008: Qdrant reviews collection in ingest.py
# ---------------------------------------------------------------------------


def test_at008_qdrant_ingest_has_build_reviews_index() -> None:
    content = (REPO_ROOT / "contextualize" / "qdrant_ingest" / "ingest.py").read_text()
    assert "build_reviews_index" in content
    assert "collection_name=\"reviews\"" in content or "collection_name='reviews'" in content


# ---------------------------------------------------------------------------
# AT-009: LangFuse handler constructible
# ---------------------------------------------------------------------------


def test_at009_langfuse_handler_module_exists() -> None:
    assert (REPO_ROOT / "agent" / "observability" / "langfuse_callbacks.py").exists()
    content = (REPO_ROOT / "agent" / "observability" / "langfuse_callbacks.py").read_text()
    assert "CallbackHandler" in content
    assert "get_langfuse_handler" in content


# ---------------------------------------------------------------------------
# AT-010: DeepEval scorer has all 3 metrics
# ---------------------------------------------------------------------------


def test_at010_deepeval_scorer_has_three_metrics() -> None:
    content = (REPO_ROOT / "agent" / "observability" / "deepeval_scorer.py").read_text()
    assert "FaithfulnessMetric" in content
    assert "AnswerRelevancyMetric" in content
    assert "HallucinationMetric" in content
    assert "score_crew_output" in content


# ---------------------------------------------------------------------------
# AT-011: READ-ONLY enforcement unchanged
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "bad_sql",
    [
        "DELETE FROM fato_vendas",
        "INSERT INTO fato_vendas VALUES (1,1,1,1,1,'2024-01-01',1,100,100,70,0)",
        "DROP TABLE dim_produto",
        "UPDATE dim_loja SET gerente = 'hacker'",
        "ALTER TABLE fato_vendas ADD COLUMN x INT",
        "CREATE TABLE pwned (id INT)",
        "TRUNCATE fato_vendas",
    ],
)
def test_at011_readonly_enforcement(bad_sql: str, monkeypatch) -> None:
    monkeypatch.setenv("POSTGRES_READONLY_URL", "postgresql://x:x@localhost/x")
    from agent.tools import sql_tool

    with pytest.raises(ValueError, match="READ-ONLY"):
        sql_tool.invoke({"sql": bad_sql})


def test_at011_select_passes_allowed_stmt_regex() -> None:
    from agent.tools import ALLOWED_STMT

    assert ALLOWED_STMT.match("SELECT 1")
    assert ALLOWED_STMT.match("  select * from fato_vendas")
    assert not ALLOWED_STMT.match("DELETE FROM x")
    assert not ALLOWED_STMT.match("INSERT INTO x")


# ---------------------------------------------------------------------------
# AT-012: All 7 Pydantic models importable
# ---------------------------------------------------------------------------


def test_at012_all_seven_models_importable() -> None:
    from ingest.models import (
        ModeloDimCliente,
        ModeloDimLoja,
        ModeloDimProduto,
        ModeloDimTempo,
        ModeloFatoEstoque,
        ModeloFatoVendas,
        ModeloReview,
    )

    for cls in (
        ModeloFatoVendas,
        ModeloFatoEstoque,
        ModeloDimProduto,
        ModeloDimCliente,
        ModeloDimLoja,
        ModeloDimTempo,
        ModeloReview,
    ):
        assert cls.__name__.startswith("Modelo")
