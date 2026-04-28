from __future__ import annotations

import os
from pathlib import Path

from langchain_anthropic import ChatAnthropic
from langgraph.prebuilt import create_react_agent

from agent.tools import sql_tool, rag_tool
from agent.observability.langfuse_callbacks import get_langfuse_handler

_SYSTEM_PROMPT = (Path(__file__).parent / "prompts" / "react_system.txt").read_text(
    encoding="utf-8"
)


def build_react_agent():
    model = ChatAnthropic(
        model="claude-sonnet-4-6",
        temperature=0.0,
        max_tokens=4096,
        api_key=os.environ["ANTHROPIC_API_KEY"],
    )
    return create_react_agent(
        model=model,
        tools=[sql_tool, rag_tool],
        prompt=_SYSTEM_PROMPT,
    )


async def ainvoke_react(question: str) -> str:
    agent = build_react_agent()
    handler = get_langfuse_handler()
    result = await agent.ainvoke(
        {"messages": [{"role": "user", "content": question}]},
        config={"callbacks": [handler], "metadata": {"framework": "langchain_react"}},
    )
    return result["messages"][-1].content
