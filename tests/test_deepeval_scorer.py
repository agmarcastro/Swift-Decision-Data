from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.mark.asyncio
async def test_three_scores_posted_to_langfuse(monkeypatch) -> None:
    monkeypatch.setenv("LANGFUSE_PUBLIC_KEY", "pk-test")
    monkeypatch.setenv("LANGFUSE_SECRET_KEY", "sk-test")

    mock_metric = MagicMock()
    mock_metric.measure.return_value = None
    mock_metric.score = 0.85

    mock_lf_client = MagicMock()
    mock_lf_client.score.return_value = None

    with (
        patch("agent.observability.deepeval_scorer.FaithfulnessMetric", return_value=mock_metric),
        patch("agent.observability.deepeval_scorer.AnswerRelevancyMetric", return_value=mock_metric),
        patch("agent.observability.deepeval_scorer.HallucinationMetric", return_value=mock_metric),
        patch("agent.observability.deepeval_scorer.get_langfuse_client", return_value=mock_lf_client),
    ):
        from agent.observability.deepeval_scorer import score_crew_output

        scores = await score_crew_output(
            question="Qual o sentimento dos clientes?",
            answer="Sentimento predominantemente positivo.",
            retrieval_context=["Review positiva exemplo."],
            trace_id="trace-abc-123",
        )

    assert set(scores.keys()) == {"faithfulness", "relevance", "hallucination"}
    assert mock_lf_client.score.call_count == 3
    for name, val in scores.items():
        assert isinstance(val, float)


@pytest.mark.asyncio
async def test_metric_failure_sets_score_to_zero(monkeypatch) -> None:
    monkeypatch.setenv("LANGFUSE_PUBLIC_KEY", "pk-test")
    monkeypatch.setenv("LANGFUSE_SECRET_KEY", "sk-test")

    failing_metric = MagicMock()
    failing_metric.measure.side_effect = RuntimeError("LLM judge unavailable")
    failing_metric.score = None

    mock_lf_client = MagicMock()

    with (
        patch("agent.observability.deepeval_scorer.FaithfulnessMetric", return_value=failing_metric),
        patch("agent.observability.deepeval_scorer.AnswerRelevancyMetric", return_value=failing_metric),
        patch("agent.observability.deepeval_scorer.HallucinationMetric", return_value=failing_metric),
        patch("agent.observability.deepeval_scorer.get_langfuse_client", return_value=mock_lf_client),
    ):
        from agent.observability.deepeval_scorer import score_crew_output

        scores = await score_crew_output(
            question="q",
            answer="a",
            retrieval_context=[],
            trace_id="",
        )

    assert all(v == 0.0 for v in scores.values())
