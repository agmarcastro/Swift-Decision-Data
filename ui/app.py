from __future__ import annotations

import logging

import chainlit as cl

from agent.graph import graph
from agent.state import AgentState

logger = logging.getLogger(__name__)

_NODE_NAMES = {"classify", "sql_agent", "rag_agent", "hybrid_agent"}


@cl.on_chat_start
async def on_chat_start() -> None:
    await cl.Message(
        content=(
            "Welcome to **InfoAgent** — your AI retail intelligence assistant.\n\n"
            "Ask me anything about sales performance, inventory, KPIs, or store operations."
        )
    ).send()


@cl.on_message
async def on_message(message: cl.Message) -> None:
    state = AgentState(messages=[{"role": "user", "content": message.content}])

    answered = False

    async with cl.Step(name="Classifying query", type="tool") as step:
        async for event in graph.astream_events(state.model_dump(), version="v2"):
            kind = event.get("event", "")
            node = event.get("name", "")

            if kind == "on_chain_start" and node in _NODE_NAMES:
                step.name = f"Running: {node}"
                await step.update()

            elif kind == "on_chain_end":
                output = event.get("data", {}).get("output", {}) or {}
                final = output.get("final_answer") if isinstance(output, dict) else None
                if final:
                    await cl.Message(content=final).send()
                    answered = True
                    return

    if answered:
        return

    try:
        result = await graph.ainvoke(state.model_dump())
        final = result.get("final_answer", "I was unable to answer your question.")
    except Exception as exc:
        logger.exception("on_message: graph invocation failed err=%s", exc)
        final = "An unexpected error occurred while processing your question."

    await cl.Message(content=final).send()
