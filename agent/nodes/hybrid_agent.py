from __future__ import annotations

import logging
import os
import time
from pathlib import Path

import anthropic

from agent.nodes.rag_agent import rag_agent_node
from agent.nodes.sql_agent import sql_agent_node
from agent.state import AgentState

logger = logging.getLogger(__name__)

PROMPT_PATH = Path(__file__).parent.parent / "prompts" / "hybrid_agent.txt"
MODEL = "claude-sonnet-4-6"


def hybrid_agent_node(state: AgentState) -> dict:
    """LangGraph node: SQL result + RAG enrichment -> executive synthesis."""
    started = time.perf_counter()

    sql_updates = sql_agent_node(state)
    logger.info("hybrid_agent_node: sql sub-node complete")

    rag_updates = rag_agent_node(state)
    logger.info("hybrid_agent_node: rag sub-node complete")

    user_message = state.messages[-1].content if state.messages else ""

    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    system_prompt = PROMPT_PATH.read_text()

    synthesis_prompt = (
        f"original_question: {user_message}\n\n"
        f"sql_result: {sql_updates.get('sql_result')}\n\n"
        f"rag_context: {rag_updates.get('kpi_context', '')}"
    )

    try:
        response = client.messages.create(
            model=MODEL,
            max_tokens=512,
            system=system_prompt,
            messages=[{"role": "user", "content": synthesis_prompt}],
        )
        final_answer = response.content[0].text
    except (anthropic.RateLimitError, anthropic.APITimeoutError) as exc:
        logger.error(
            "hybrid_agent_node: anthropic error type=%s err=%s", type(exc).__name__, exc
        )
        final_answer = (
            "I gathered the data but the language model is temporarily unavailable "
            "for synthesis (rate limit or timeout). Please retry in a moment."
        )

    elapsed_ms = (time.perf_counter() - started) * 1000
    logger.info("hybrid_agent_node: total elapsed_ms=%.1f", elapsed_ms)

    return {
        "sql_result": sql_updates.get("sql_result"),
        "final_answer": final_answer,
    }
