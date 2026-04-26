from __future__ import annotations

import logging

from langgraph.graph import END, StateGraph

from agent.nodes.classifier import classify_query
from agent.nodes.hybrid_agent import hybrid_agent_node
from agent.nodes.rag_agent import rag_agent_node
from agent.nodes.sql_agent import sql_agent_node
from agent.state import AgentState

logger = logging.getLogger(__name__)


def _route_query(state: AgentState) -> str:
    return state.query_type or "type1_sql"


_builder = StateGraph(AgentState)
_builder.add_node("classify", classify_query)
_builder.add_node("sql_agent", sql_agent_node)
_builder.add_node("rag_agent", rag_agent_node)
_builder.add_node("hybrid_agent", hybrid_agent_node)
_builder.set_entry_point("classify")
_builder.add_conditional_edges(
    "classify",
    _route_query,
    {
        "type1_sql": "sql_agent",
        "type2_kpi_sql": "sql_agent",
        "type3_hybrid": "hybrid_agent",
    },
)
_builder.add_edge("sql_agent", END)
_builder.add_edge("rag_agent", END)
_builder.add_edge("hybrid_agent", END)

graph = _builder.compile()
