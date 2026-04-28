from __future__ import annotations

import logging

from deepeval.metrics import (
    AnswerRelevancyMetric,
    FaithfulnessMetric,
    HallucinationMetric,
)
from deepeval.test_case import LLMTestCase

from agent.observability.langfuse_callbacks import get_langfuse_client

logger = logging.getLogger(__name__)

_JUDGE_MODEL = "claude-sonnet-4-6"
_THRESHOLD = 0.7


async def score_crew_output(
    question: str,
    answer: str,
    retrieval_context: list[str],
    trace_id: str,
) -> dict[str, float]:
    test_case = LLMTestCase(
        input=question,
        actual_output=answer,
        retrieval_context=retrieval_context or [""],
        context=retrieval_context or [""],
    )

    metrics = {
        "faithfulness": FaithfulnessMetric(
            threshold=_THRESHOLD, model=_JUDGE_MODEL, include_reason=False, async_mode=False
        ),
        "relevance": AnswerRelevancyMetric(
            threshold=_THRESHOLD, model=_JUDGE_MODEL, include_reason=False, async_mode=False
        ),
        "hallucination": HallucinationMetric(
            threshold=_THRESHOLD, model=_JUDGE_MODEL, include_reason=False, async_mode=False
        ),
    }

    scores: dict[str, float] = {}
    client = get_langfuse_client()

    for name, metric in metrics.items():
        try:
            metric.measure(test_case)
            scores[name] = float(metric.score or 0.0)
            if trace_id:
                client.score(trace_id=trace_id, name=name, value=scores[name])
            logger.info("deepeval: metric=%s score=%.3f", name, scores[name])
        except Exception as exc:  # noqa: BLE001
            logger.warning("deepeval: metric=%s failed err=%s", name, exc)
            scores[name] = 0.0

    return scores
