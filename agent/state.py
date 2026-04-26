from __future__ import annotations

from typing import Annotated, Literal
from langgraph.graph.message import add_messages
from pydantic import BaseModel


class AgentState(BaseModel):
    messages: Annotated[list, add_messages]
    query_type: Literal["type1_sql", "type2_kpi_sql", "type3_hybrid"] | None = None
    kpi_name: str | None = None
    kpi_context: str | None = None
    sql_result: list[dict] | None = None
    final_answer: str | None = None
