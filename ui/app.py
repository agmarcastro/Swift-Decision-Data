from __future__ import annotations

import logging
import re

import chainlit as cl
from langchain_core.messages import AIMessage, ToolMessage

from agent.crews.crew import kickoff_crew
from agent.observability.deepeval_scorer import score_crew_output
from agent.observability.langfuse_callbacks import get_langfuse_handler
from agent.react_agent import build_react_agent

logger = logging.getLogger(__name__)

_NUMERIC_HINTS = re.compile(
    r"\b(vendas|estoque|margem|giro|faturamento|quanto|total|ranking)\b", re.IGNORECASE
)
_OPINION_HINTS = re.compile(
    r"\b(reclama|opini|sentimento|satisfa|review|avalia|elogi)\w*", re.IGNORECASE
)


def _needs_crew(question: str) -> bool:
    return bool(_NUMERIC_HINTS.search(question)) and bool(_OPINION_HINTS.search(question))


@cl.on_chat_start
async def on_chat_start() -> None:
    await cl.Message(
        content=(
            "Bem-vindo(a) ao **InfoAgent** — seu assistente executivo de inteligência "
            "de varejo. Pergunte sobre vendas, estoque, KPIs ou opiniões dos clientes."
        )
    ).send()


@cl.on_message
async def on_message(message: cl.Message) -> None:
    question = message.content

    if _needs_crew(question):
        async with cl.Step(name="Equipe CrewAI: Analista + Pesquisador + Relator", type="tool") as step:
            step.input = question
            try:
                answer, retrieval_ctx, trace_id = await kickoff_crew(question)
            except Exception as exc:
                logger.exception("kickoff_crew failed: %s", exc)
                await cl.Message(content="O serviço de IA está temporariamente indisponível.").send()
                return
            step.output = answer

        async with cl.Step(name="Avaliando qualidade da resposta (DeepEval)", type="tool") as eval_step:
            scores = await score_crew_output(
                question=question,
                answer=answer,
                retrieval_context=retrieval_ctx,
                trace_id=trace_id,
            )
            eval_step.output = (
                f"Faithfulness: {scores['faithfulness']:.2f} | "
                f"Relevance: {scores['relevance']:.2f} | "
                f"Hallucination: {scores['hallucination']:.2f}"
            )

        await cl.Message(content=answer).send()
        return

    agent = build_react_agent()
    handler = get_langfuse_handler()
    final_text = ""

    try:
        async for event in agent.astream(
            {"messages": [{"role": "user", "content": question}]},
            config={"callbacks": [handler], "metadata": {"framework": "langchain_react"}},
            stream_mode="updates",
        ):
            for _node_name, payload in event.items():
                messages = payload.get("messages", [])
                for msg in messages:
                    if isinstance(msg, AIMessage) and msg.tool_calls:
                        for tc in msg.tool_calls:
                            async with cl.Step(name=f"Ferramenta: {tc['name']}", type="tool") as step:
                                step.input = str(tc.get("args", {}))
                    elif isinstance(msg, ToolMessage):
                        async with cl.Step(name=f"Resultado: {msg.name}", type="tool") as step:
                            step.output = msg.content[:2000]
                    elif isinstance(msg, AIMessage) and not msg.tool_calls:
                        final_text = msg.content
    except Exception as exc:
        logger.exception("react agent failed: %s", exc)
        await cl.Message(content="O serviço de IA está temporariamente indisponível.").send()
        return

    await cl.Message(content=final_text or "Não consegui responder sua pergunta.").send()
