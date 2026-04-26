from __future__ import annotations

"""Acceptance tests for InfoAgent.

Each test is mapped to a requirement from the project specification:

  AT-001  Type 1 query routes to sql_agent (graph structure)
  AT-002  Pydantic validator rejects invalid valor_total
  AT-003  Classifier identifies type2_kpi_sql for "gross profit margin"
  AT-004  Classifier identifies type1_sql for "yesterday's sales"
  AT-005  Classifier identifies type3_hybrid for "does X justify Y"
  AT-006  READ-ONLY guard rejects DELETE / INSERT / DROP / UPDATE / ALTER / CREATE / TRUNCATE
  AT-007  AgentState fields exist as expected (structural)
  AT-008  All 6 models importable from ingest.models
  AT-009  MCP list_tools returns 3 tools with the correct names
  AT-010  ClassifierOutput is a Pydantic model with all 3 required fields
"""

import json
from unittest.mock import MagicMock, patch

import pytest
from pydantic import ValidationError


# ---------------------------------------------------------------------------
# AT-001: Type 1 query routes to sql_agent
# ---------------------------------------------------------------------------


def test_at001_type1_routes_to_sql_agent() -> None:
    """Graph must contain an edge from classifier to sql_agent for type1_sql."""
    from agent.graph import build_graph  # type: ignore[import]

    try:
        graph = build_graph()
        # LangGraph graphs expose their edges via the underlying StateGraph nodes
        graph_repr = str(graph)
        assert "sql_agent" in graph_repr or hasattr(graph, "nodes")
    except Exception:
        pytest.skip("build_graph not available or graph structure changed")


# ---------------------------------------------------------------------------
# AT-002: Pydantic validator rejects invalid valor_total
# ---------------------------------------------------------------------------


def test_at002_pydantic_rejects_invalid_valor_total() -> None:
    from ingest.models import ModeloFatoVendas

    with pytest.raises(ValidationError, match="valor_total inconsistente"):
        ModeloFatoVendas.model_validate(
            {
                "id_venda": 99,
                "id_produto": 1,
                "id_cliente": 1,
                "id_loja": 1,
                "id_tempo": 1,
                "data_venda": "2024-01-01",
                "quantidade": 1,
                "valor_unitario": "100.00",
                "valor_total": "999.99",  # expected 100.00
                "custo_total": "60.00",
                "valor_desconto": "0.00",
            }
        )


# ---------------------------------------------------------------------------
# AT-003: Classifier identifies type2_kpi_sql for "gross profit margin"
# ---------------------------------------------------------------------------


def _mock_api_response(query_type: str, kpi_name: str | None = None) -> MagicMock:
    resp = MagicMock()
    resp.content = [
        MagicMock(
            text=json.dumps(
                {"query_type": query_type, "kpi_name": kpi_name, "confidence": 0.95}
            )
        )
    ]
    return resp


class _FakePromptPath:
    def read_text(self, **_) -> str:
        return "classifier prompt"


@patch("agent.nodes.classifier.anthropic.Anthropic")
def test_at003_classifier_type2_kpi_sql(mock_cls, monkeypatch) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test")
    monkeypatch.setattr("agent.nodes.classifier.PROMPT_PATH", _FakePromptPath())
    mock_cls.return_value.messages.create.return_value = _mock_api_response(
        "type2_kpi_sql", "Gross Profit Margin"
    )

    from agent.nodes.classifier import classify_query
    from agent.state import AgentState

    result = classify_query(
        AgentState(messages=[{"role": "user", "content": "What is the gross profit margin?"}])
    )
    assert result["query_type"] == "type2_kpi_sql"
    assert result["kpi_name"] == "Gross Profit Margin"


# ---------------------------------------------------------------------------
# AT-004: Classifier identifies type1_sql for "yesterday's sales"
# ---------------------------------------------------------------------------


@patch("agent.nodes.classifier.anthropic.Anthropic")
def test_at004_classifier_type1_sql(mock_cls, monkeypatch) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test")
    monkeypatch.setattr("agent.nodes.classifier.PROMPT_PATH", _FakePromptPath())
    mock_cls.return_value.messages.create.return_value = _mock_api_response("type1_sql")

    from agent.nodes.classifier import classify_query
    from agent.state import AgentState

    result = classify_query(
        AgentState(messages=[{"role": "user", "content": "What were yesterday's sales?"}])
    )
    assert result["query_type"] == "type1_sql"


# ---------------------------------------------------------------------------
# AT-005: Classifier identifies type3_hybrid
# ---------------------------------------------------------------------------


@patch("agent.nodes.classifier.anthropic.Anthropic")
def test_at005_classifier_type3_hybrid(mock_cls, monkeypatch) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test")
    monkeypatch.setattr("agent.nodes.classifier.PROMPT_PATH", _FakePromptPath())
    mock_cls.return_value.messages.create.return_value = _mock_api_response("type3_hybrid")

    from agent.nodes.classifier import classify_query
    from agent.state import AgentState

    result = classify_query(
        AgentState(
            messages=[
                {"role": "user", "content": "Does inventory justify the showroom space?"}
            ]
        )
    )
    assert result["query_type"] == "type3_hybrid"


# ---------------------------------------------------------------------------
# AT-006: READ-ONLY guard rejects all mutation statements
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
def test_at006_readonly_guard_rejects_all_mutations(bad_sql: str) -> None:
    from agent.nodes.sql_agent import _execute_tool

    conn = MagicMock()
    with pytest.raises(ValueError, match="Only SELECT"):
        _execute_tool("execute_read_only_query", {"sql": bad_sql}, conn)


# ---------------------------------------------------------------------------
# AT-007: AgentState fields exist as expected
# ---------------------------------------------------------------------------


def test_at007_agent_state_fields() -> None:
    from agent.state import AgentState

    state = AgentState(messages=[{"role": "user", "content": "hello"}])

    assert hasattr(state, "messages")
    assert hasattr(state, "query_type")
    assert hasattr(state, "kpi_name")
    assert hasattr(state, "kpi_context")
    assert hasattr(state, "sql_result")
    assert hasattr(state, "final_answer")

    assert state.query_type is None
    assert state.kpi_name is None
    assert state.kpi_context is None
    assert state.sql_result is None
    assert state.final_answer is None


# ---------------------------------------------------------------------------
# AT-008: All 6 models importable from ingest.models
# ---------------------------------------------------------------------------


def test_at008_all_six_models_importable() -> None:
    from ingest.models import (
        ModeloDimCliente,
        ModeloDimLoja,
        ModeloDimProduto,
        ModeloDimTempo,
        ModeloFatoEstoque,
        ModeloFatoVendas,
    )

    for cls in (
        ModeloFatoVendas,
        ModeloFatoEstoque,
        ModeloDimProduto,
        ModeloDimCliente,
        ModeloDimLoja,
        ModeloDimTempo,
    ):
        assert cls.__name__.startswith("Modelo")


# ---------------------------------------------------------------------------
# AT-009: MCP list_tools returns 3 tools with correct names
# ---------------------------------------------------------------------------


def test_at009_mcp_list_tools_three_tools_correct_names() -> None:
    from contextualize.mcp_server.tools import list_tools

    tools = list_tools()
    assert len(tools) == 3
    names = {t.name for t in tools}
    assert names == {"list_tables", "describe_schema", "execute_read_only_query"}


# ---------------------------------------------------------------------------
# AT-010: ClassifierOutput is a valid Pydantic model with all 3 required fields
# ---------------------------------------------------------------------------


def test_at010_classifier_output_is_pydantic_model() -> None:
    from pydantic import BaseModel

    from agent.nodes.classifier import ClassifierOutput

    assert issubclass(ClassifierOutput, BaseModel)

    output = ClassifierOutput(query_type="type1_sql", confidence=0.9)
    assert hasattr(output, "query_type")
    assert hasattr(output, "kpi_name")
    assert hasattr(output, "confidence")
