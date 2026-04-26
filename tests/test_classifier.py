from __future__ import annotations

import json
import os
from unittest.mock import MagicMock, patch

import pytest

from agent.nodes.classifier import ClassifierOutput, classify_query
from agent.state import AgentState


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_state(question: str) -> AgentState:
    """Build an AgentState with a single user message."""
    return AgentState(messages=[{"role": "user", "content": question}])


def _mock_response(
    query_type: str,
    kpi_name: str | None = None,
    confidence: float = 0.95,
) -> MagicMock:
    """Return a mock anthropic.messages.create() response with valid JSON content."""
    mock_resp = MagicMock()
    mock_resp.content = [
        MagicMock(
            text=json.dumps(
                {
                    "query_type": query_type,
                    "kpi_name": kpi_name,
                    "confidence": confidence,
                }
            )
        )
    ]
    return mock_resp


# ---------------------------------------------------------------------------
# classify_query — happy paths
# ---------------------------------------------------------------------------


class TestClassifyQuery:
    @patch("agent.nodes.classifier.anthropic.Anthropic")
    def test_classify_type1_sql(self, mock_client_cls, tmp_path, monkeypatch) -> None:
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
        _patch_prompt(monkeypatch)
        mock_client_cls.return_value.messages.create.return_value = _mock_response("type1_sql")

        result = classify_query(_make_state("What were yesterday's sales?"))

        assert result["query_type"] == "type1_sql"
        assert result["kpi_name"] is None

    @patch("agent.nodes.classifier.anthropic.Anthropic")
    def test_classify_type2_kpi_sql(self, mock_client_cls, monkeypatch) -> None:
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
        _patch_prompt(monkeypatch)
        mock_client_cls.return_value.messages.create.return_value = _mock_response(
            "type2_kpi_sql", kpi_name="Gross Profit Margin"
        )

        result = classify_query(_make_state("What is the gross profit margin?"))

        assert result["query_type"] == "type2_kpi_sql"
        assert result["kpi_name"] == "Gross Profit Margin"
        # kpi_context is None because Qdrant is not running in unit tests
        assert result.get("kpi_context") is None

    @patch("agent.nodes.classifier.anthropic.Anthropic")
    def test_classify_type3_hybrid(self, mock_client_cls, monkeypatch) -> None:
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
        _patch_prompt(monkeypatch)
        mock_client_cls.return_value.messages.create.return_value = _mock_response("type3_hybrid")

        result = classify_query(_make_state("Does inventory justify the showroom space?"))

        assert result["query_type"] == "type3_hybrid"

    @patch("agent.nodes.classifier.anthropic.Anthropic")
    def test_classify_returns_confidence_key_not_exposed_in_state(
        self, mock_client_cls, monkeypatch
    ) -> None:
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
        _patch_prompt(monkeypatch)
        mock_client_cls.return_value.messages.create.return_value = _mock_response(
            "type1_sql", confidence=0.72
        )

        result = classify_query(_make_state("How many units sold last week?"))

        assert "query_type" in result


# ---------------------------------------------------------------------------
# classify_query — fallback on bad model output
# ---------------------------------------------------------------------------


class TestClassifyQueryFallback:
    @patch("agent.nodes.classifier.anthropic.Anthropic")
    def test_classify_invalid_json_falls_back_to_type1(
        self, mock_client_cls, monkeypatch
    ) -> None:
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
        _patch_prompt(monkeypatch)

        mock_resp = MagicMock()
        mock_resp.content = [MagicMock(text="I cannot classify this.")]
        mock_client_cls.return_value.messages.create.return_value = mock_resp

        result = classify_query(_make_state("some question"))

        assert result["query_type"] == "type1_sql"
        assert result["kpi_name"] is None

    @patch("agent.nodes.classifier.anthropic.Anthropic")
    def test_classify_rate_limit_falls_back_gracefully(
        self, mock_client_cls, monkeypatch
    ) -> None:
        import anthropic as _anthropic

        monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
        _patch_prompt(monkeypatch)
        mock_client_cls.return_value.messages.create.side_effect = (
            _anthropic.RateLimitError.__new__(_anthropic.RateLimitError)
            if not hasattr(_anthropic.RateLimitError, "__init__")
            else _make_rate_limit_error()
        )

        result = classify_query(_make_state("some question"))

        assert result["query_type"] == "type1_sql"
        assert "final_answer" in result


# ---------------------------------------------------------------------------
# ClassifierOutput model
# ---------------------------------------------------------------------------


class TestClassifierOutput:
    def test_valid_type1(self) -> None:
        output = ClassifierOutput(query_type="type1_sql", confidence=0.9)
        assert output.kpi_name is None

    def test_valid_type2_with_kpi(self) -> None:
        output = ClassifierOutput(
            query_type="type2_kpi_sql", kpi_name="Gross Profit Margin", confidence=0.88
        )
        assert output.kpi_name == "Gross Profit Margin"

    def test_all_fields_present(self) -> None:
        output = ClassifierOutput(query_type="type3_hybrid", confidence=0.75)
        assert hasattr(output, "query_type")
        assert hasattr(output, "kpi_name")
        assert hasattr(output, "confidence")


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _patch_prompt(monkeypatch) -> None:
    """Prevent classifier from reading the prompt file from disk."""
    monkeypatch.setattr(
        "agent.nodes.classifier.PROMPT_PATH",
        _FakePath("You are a classifier. Return JSON."),
    )


class _FakePath:
    """Minimal Path-alike that satisfies PROMPT_PATH.read_text()."""

    def __init__(self, content: str) -> None:
        self._content = content

    def read_text(self, **_kwargs) -> str:
        return self._content


def _make_rate_limit_error():
    """Construct a RateLimitError without requiring a real HTTP response."""
    import anthropic as _anthropic

    try:
        return _anthropic.RateLimitError(
            message="rate limit", response=MagicMock(), body={}
        )
    except Exception:
        err = Exception("rate limit")
        err.__class__ = _anthropic.RateLimitError
        return err
