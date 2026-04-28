from __future__ import annotations

from pathlib import Path

import yaml
from crewai import Agent, Crew, Process, Task
from langfuse import observe

from agent.observability.langfuse_callbacks import init_crewai_otel, get_langfuse_client
from agent.tools import sql_tool, rag_tool

_AGENTS_YAML = Path(__file__).parent / "agents.yaml"
_TASKS_YAML = Path(__file__).parent / "tasks.yaml"

_TOOL_REGISTRY = {
    "analyst": [sql_tool],
    "researcher": [rag_tool],
    "reporter": [],
}


def _build_agents() -> dict[str, Agent]:
    cfg = yaml.safe_load(_AGENTS_YAML.read_text(encoding="utf-8"))
    return {
        name: Agent(
            role=spec["role"],
            goal=spec["goal"],
            backstory=spec["backstory"],
            llm=spec["llm"],
            max_iter=spec.get("max_iter", 10),
            allow_delegation=spec.get("allow_delegation", False),
            tools=_TOOL_REGISTRY.get(name, []),
            verbose=spec.get("verbose", False),
        )
        for name, spec in cfg.items()
    }


def _build_tasks(agents: dict[str, Agent]) -> list[Task]:
    cfg = yaml.safe_load(_TASKS_YAML.read_text(encoding="utf-8"))
    tasks: dict[str, Task] = {}
    for name, spec in cfg.items():
        tasks[name] = Task(
            description=spec["description"],
            expected_output=spec["expected_output"],
            agent=agents[spec["agent"]],
            context=[tasks[c] for c in spec.get("context", [])],
        )
    return list(tasks.values())


@observe(name="crew_kickoff")
async def kickoff_crew(question: str) -> tuple[str, list[str], str]:
    init_crewai_otel()
    agents = _build_agents()
    tasks = _build_tasks(agents)
    crew = Crew(
        agents=list(agents.values()),
        tasks=tasks,
        process=Process.sequential,
        verbose=False,
    )
    result = await crew.kickoff_async(inputs={"question": question})
    final_answer = str(result)

    research_output = ""
    for t in tasks:
        if t.agent.role.startswith("Pesquisador"):
            research_output = str(t.output) if t.output else ""

    trace_id = get_langfuse_client().get_current_trace_id() or ""
    return final_answer, [research_output] if research_output else [], trace_id
