from __future__ import annotations

from unittest.mock import MagicMock, patch


def test_get_langfuse_handler_returns_callback_handler(monkeypatch) -> None:
    monkeypatch.setenv("LANGFUSE_PUBLIC_KEY", "pk-test")
    monkeypatch.setenv("LANGFUSE_SECRET_KEY", "sk-test")
    monkeypatch.setenv("LANGFUSE_HOST", "http://localhost:3000")

    mock_handler = MagicMock()

    with (
        patch("agent.observability.langfuse_callbacks.Langfuse"),
        patch("agent.observability.langfuse_callbacks.CallbackHandler", return_value=mock_handler),
    ):
        from agent.observability import langfuse_callbacks

        langfuse_callbacks.get_langfuse_client.cache_clear()
        handler = langfuse_callbacks.get_langfuse_handler()

    assert handler is mock_handler


def test_init_crewai_otel_is_idempotent(monkeypatch) -> None:
    monkeypatch.setenv("LANGFUSE_PUBLIC_KEY", "pk-test")
    monkeypatch.setenv("LANGFUSE_SECRET_KEY", "sk-test")

    mock_openlit = MagicMock()
    mock_client = MagicMock()
    mock_client._otel_tracer = MagicMock()

    with (
        patch("agent.observability.langfuse_callbacks.Langfuse", return_value=mock_client),
        patch.dict("sys.modules", {"openlit": mock_openlit}),
    ):
        import importlib
        from agent.observability import langfuse_callbacks

        langfuse_callbacks.get_langfuse_client.cache_clear()
        langfuse_callbacks._otel_initialised = False

        langfuse_callbacks.init_crewai_otel()
        langfuse_callbacks.init_crewai_otel()

    assert mock_openlit.init.call_count <= 1
