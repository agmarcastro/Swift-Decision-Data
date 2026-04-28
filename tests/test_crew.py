from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import yaml


AGENTS_YAML = Path(__file__).parent.parent / "agent" / "crews" / "agents.yaml"
TASKS_YAML = Path(__file__).parent.parent / "agent" / "crews" / "tasks.yaml"


def test_agents_yaml_has_three_agents() -> None:
    cfg = yaml.safe_load(AGENTS_YAML.read_text(encoding="utf-8"))
    assert set(cfg.keys()) == {"analyst", "researcher", "reporter"}


def test_tasks_yaml_has_three_tasks() -> None:
    cfg = yaml.safe_load(TASKS_YAML.read_text(encoding="utf-8"))
    assert set(cfg.keys()) == {"analyst_task", "research_task", "reporter_task"}


def test_reporter_task_has_context() -> None:
    cfg = yaml.safe_load(TASKS_YAML.read_text(encoding="utf-8"))
    ctx = cfg["reporter_task"].get("context", [])
    assert "analyst_task" in ctx
    assert "research_task" in ctx


def test_all_agents_have_pt_br_llm() -> None:
    cfg = yaml.safe_load(AGENTS_YAML.read_text(encoding="utf-8"))
    for name, spec in cfg.items():
        assert spec["llm"] == "anthropic/claude-sonnet-4-6", f"{name} has wrong LLM"


def test_analyst_uses_sql_tool_and_researcher_uses_rag_tool() -> None:
    from agent.crews.crew import _TOOL_REGISTRY

    assert any(t.name == "sql_tool" for t in _TOOL_REGISTRY["analyst"])
    assert any(t.name == "rag_tool" for t in _TOOL_REGISTRY["researcher"])
    assert _TOOL_REGISTRY["reporter"] == []


@pytest.mark.asyncio
async def test_kickoff_crew_returns_triple(monkeypatch) -> None:
    monkeypatch.setenv("LANGFUSE_PUBLIC_KEY", "pk-test")
    monkeypatch.setenv("LANGFUSE_SECRET_KEY", "sk-test")

    mock_crew = MagicMock()
    mock_crew.kickoff_async = AsyncMock(return_value="Resposta executiva sintetizada.")

    mock_task = MagicMock()
    mock_task.agent.role = "Pesquisador de Voz do Cliente"
    mock_task.output = "Sentimento negativo predominante."

    mock_lf_client = MagicMock()
    mock_lf_client.get_current_trace_id.return_value = "trace-123"

    with (
        patch("agent.crews.crew.Crew", return_value=mock_crew),
        patch("agent.crews.crew._build_agents", return_value={}),
        patch("agent.crews.crew._build_tasks", return_value=[mock_task]),
        patch("agent.crews.crew.get_langfuse_client", return_value=mock_lf_client),
        patch("agent.crews.crew.init_crewai_otel"),
    ):
        from agent.crews.crew import kickoff_crew

        answer, ctx, trace_id = await kickoff_crew("Pergunta híbrida sobre estoque e avaliações")

    assert isinstance(answer, str)
    assert isinstance(ctx, list)
    assert isinstance(trace_id, str)
