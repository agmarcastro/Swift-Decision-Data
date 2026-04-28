from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.fixture
def env_vars(monkeypatch) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
    monkeypatch.setenv("POSTGRES_READONLY_URL", "postgresql://x:x@localhost/x")
    monkeypatch.setenv("QDRANT_HOST", "localhost")
    monkeypatch.setenv("LANGFUSE_PUBLIC_KEY", "pk-test")
    monkeypatch.setenv("LANGFUSE_SECRET_KEY", "sk-test")


def test_build_react_agent_returns_runnable(env_vars, monkeypatch) -> None:
    mock_agent = MagicMock()

    with (
        patch("agent.react_agent.ChatAnthropic"),
        patch("agent.react_agent.create_react_agent", return_value=mock_agent),
        patch("agent.react_agent.get_langfuse_handler"),
    ):
        from agent.react_agent import build_react_agent

        agent = build_react_agent()
        assert agent is mock_agent


@pytest.mark.asyncio
async def test_ainvoke_react_returns_last_message_content(env_vars, monkeypatch) -> None:
    from langchain_core.messages import AIMessage

    final_msg = AIMessage(content="Vendas totais: R$ 1.234,00")
    mock_result = {"messages": [AIMessage(content="intermediate"), final_msg]}

    mock_agent = MagicMock()
    mock_agent.ainvoke = AsyncMock(return_value=mock_result)

    with (
        patch("agent.react_agent.ChatAnthropic"),
        patch("agent.react_agent.create_react_agent", return_value=mock_agent),
        patch("agent.react_agent.get_langfuse_handler", return_value=MagicMock()),
    ):
        from agent.react_agent import ainvoke_react

        answer = await ainvoke_react("Qual o total de vendas ontem?")
    assert "Vendas" in answer or "R$" in answer or answer == "Vendas totais: R$ 1.234,00"
