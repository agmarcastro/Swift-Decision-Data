from __future__ import annotations

import json
import logging
import os
import re
import time
from pathlib import Path

import anthropic
import psycopg2
import psycopg2.extensions
from psycopg2.extras import RealDictCursor

from agent.state import AgentState

logger = logging.getLogger(__name__)

PROMPT_PATH = Path(__file__).parent.parent / "prompts" / "sql_agent.txt"
MODEL = "claude-sonnet-4-6"
ALLOWED_STMT = re.compile(r"^\s*SELECT\b", re.IGNORECASE)
ROW_CAP = 500
MAX_ITERATIONS = 10

TOOLS = [
    {
        "name": "list_tables",
        "description": "List all tables in the public schema of the PostgreSQL database.",
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "describe_schema",
        "description": "Return column names, data types, and nullability for a given table.",
        "input_schema": {
            "type": "object",
            "properties": {"table_name": {"type": "string"}},
            "required": ["table_name"],
        },
    },
    {
        "name": "execute_read_only_query",
        "description": "Execute a SELECT statement. Only SELECT is permitted. Returns at most 500 rows.",
        "input_schema": {
            "type": "object",
            "properties": {"sql": {"type": "string"}},
            "required": ["sql"],
        },
    },
]


def _execute_tool(name: str, arguments: dict, conn: psycopg2.extensions.connection) -> str:
    match name:
        case "list_tables":
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT table_name FROM information_schema.tables "
                    "WHERE table_schema = 'public' ORDER BY table_name"
                )
                return str([row[0] for row in cur.fetchall()])

        case "describe_schema":
            table = arguments["table_name"].lower()
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT column_name, data_type, is_nullable "
                    "FROM information_schema.columns "
                    "WHERE table_name = %s ORDER BY ordinal_position",
                    (table,),
                )
                return str(cur.fetchall())

        case "execute_read_only_query":
            sql = arguments["sql"]
            if not ALLOWED_STMT.match(sql):
                raise ValueError("Only SELECT statements are permitted.")
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(sql)
                rows = cur.fetchmany(ROW_CAP)
                return json.dumps([dict(r) for r in rows], default=str)

        case _:
            raise ValueError(f"Unknown tool: {name}")


def sql_agent_node(state: AgentState) -> dict:
    """LangGraph node: generate + execute SQL using Claude tool_use loop."""
    started = time.perf_counter()
    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

    try:
        conn = psycopg2.connect(os.environ["POSTGRES_READONLY_URL"])
        conn.autocommit = True
    except Exception as exc:
        logger.error("sql_agent_node: failed to connect to Postgres err=%s", exc)
        return {
            "sql_result": None,
            "final_answer": "I could not connect to the analytics database. Please try again shortly.",
        }

    system_prompt = PROMPT_PATH.read_text()
    if state.kpi_context:
        system_prompt = system_prompt.replace("{kpi_context}", state.kpi_context)
    else:
        system_prompt = system_prompt.replace(
            "{kpi_context}", "(No KPI context needed for this query)"
        )

    user_message = state.messages[-1].content if state.messages else ""
    messages: list[dict] = [{"role": "user", "content": user_message}]

    sql_result: list[dict] | None = None
    final_answer: str = ""

    try:
        for iteration in range(MAX_ITERATIONS):
            try:
                response = client.messages.create(
                    model=MODEL,
                    max_tokens=4096,
                    system=system_prompt,
                    tools=TOOLS,
                    messages=messages,
                )
            except (anthropic.RateLimitError, anthropic.APITimeoutError) as exc:
                logger.error(
                    "sql_agent_node: anthropic error iter=%d type=%s err=%s",
                    iteration,
                    type(exc).__name__,
                    exc,
                )
                final_answer = (
                    "The language model is temporarily unavailable "
                    "(rate limit or timeout). Please retry in a moment."
                )
                break

            if response.stop_reason == "end_turn":
                text_parts = [b.text for b in response.content if hasattr(b, "text")]
                final_answer = "\n".join(text_parts)
                logger.info("sql_agent_node: end_turn after iter=%d", iteration)
                break

            if response.stop_reason == "tool_use":
                tool_results = []
                for block in response.content:
                    if block.type == "tool_use":
                        tool_started = time.perf_counter()
                        try:
                            result = _execute_tool(block.name, block.input, conn)
                            if block.name == "execute_read_only_query":
                                try:
                                    sql_result = json.loads(result)
                                except Exception:
                                    sql_result = [{"result": result}]
                            tool_elapsed_ms = (time.perf_counter() - tool_started) * 1000
                            logger.info(
                                "sql_agent_node: tool=%s success elapsed_ms=%.1f",
                                block.name,
                                tool_elapsed_ms,
                            )
                        except Exception as exc:
                            result = f"Error: {exc}"
                            logger.warning("sql_agent_node: tool=%s error=%s", block.name, exc)

                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": result,
                        })

                messages.append({"role": "assistant", "content": response.content})
                messages.append({"role": "user", "content": tool_results})
            else:
                logger.info(
                    "sql_agent_node: stop_reason=%s — exiting loop", response.stop_reason
                )
                break
        else:
            logger.warning("sql_agent_node: hit MAX_ITERATIONS=%d", MAX_ITERATIONS)
            if not final_answer:
                final_answer = (
                    "I was unable to converge on an answer within the iteration budget."
                )
    finally:
        conn.close()

    elapsed_ms = (time.perf_counter() - started) * 1000
    logger.info("sql_agent_node: total elapsed_ms=%.1f", elapsed_ms)

    return {"sql_result": sql_result, "final_answer": final_answer}
